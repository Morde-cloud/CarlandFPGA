"""Explicit existing-stream facade for an already-attached PS UART service.

No SSH, listener, subprocess, PYNQ, native RPC, clock rebasing or hardware factory.
The PC validates its own live snapshots; only finite commands cross this stream.
"""
import hashlib
import json
from pathlib import Path

from product_uart_service import ProductUartService, ServiceError

EXPECTED_SERVICE_SHA256 = '3f8584b45c449883450c09401232428d5ef0012da181be726a4de5f3f4ed54d6'


def _need(ok, reason):
    if not ok:
        raise ServiceError(reason)


def parse_line(line):
    _need(type(line) is str and 0 < len(line) <= 8192, 'bounded JSON command line')
    def unique(pairs):
        value = {}
        for key, item in pairs:
            _need(key not in value, 'duplicate JSON key')
            value[key] = item
        return value
    def nonfinite(value):
        raise ServiceError('nonfinite JSON number: ' + value)
    value = json.loads(line, object_pairs_hook=unique, parse_constant=nonfinite)
    _need(type(value) is dict, 'command object required')
    return value


class ExistingStreamSession:
    def __init__(self, service):
        _need(type(service) is ProductUartService, 'already-attached typed UART service required')
        source = Path(__file__).with_name('product_uart_service.py')
        _need(hashlib.sha256(source.read_bytes()).hexdigest() == EXPECTED_SERVICE_SHA256,
              'reviewed product service bytes required')
        service._assert_current()
        _need(not getattr(service, '_existing_stream_claimed', False), 'one existing command stream')
        service._existing_stream_claimed = True
        self.service = service

    def welcome(self):
        self.service._assert_current()
        # Legacy ready labels transport establishment; separate actual feedback.
        value = dict(self.service.connection)
        value.update(event='ready', service_event='uart_connected',
                     clock_ms=self.service._session.clock_ms(),
                     source_clock_policy='PC snapshot QPC stays on PC; remote commands use PS relative deadlines',
                     keepalive_background=False)
        return value

    def dispatch(self, request):
        self.service._assert_current()
        try:
            _need(type(request) is dict, 'command object required')
            op = request.get('op')
            _need(op in ('status', 'stop', 'pose', 'home', 'motor', 'keepalive', 'delta', 'delta_keepalive', 'startup_prepare'), 'unsupported remote operation')
            if op not in ('status', 'stop'):
                self.service._require_motion()
            if op == 'stop':
                # Validate the same fixed STOP envelope, then reuse service's
                # single terminal device STOP across explicit STOP and EOF.
                _need(set(request) == {'session', 'request_id', 'expires_ms', 'op'}, 'STOP envelope')
                session = self.service._session
                _need(request['session'] == session.session_id, 'remote session mismatch')
                rid = request['request_id']; deadline = request['expires_ms']
                _need(type(rid) is int and 1 <= rid <= 0xffffffff, 'remote request id')
                _need(type(deadline) is int and 0 <= deadline <= 2**53, 'remote STOP deadline shape')
                # Emergency STOP, like the baseline, does not require freshness.
                session.request_id = max(session.request_id, rid)
                reused = self.service._stop_attempted
                reply = dict(self.service.stop('existing_stream_stop'))
                original_id = reply['request_id']
                reply.update(request_id=rid, rpc_stop_result_reused=reused,
                             original_stop_request_id=original_id,
                             device_command_replayed=False)
                return reply
            _need(not self.service._stop_attempted, 'terminal stream permits only cached STOP receipt')
            self.service._log('existing_stream_command_intent', request=request)
            # Preserve original session/request id/expires_ms. Calling the
            # convenience SessionClient here would create a fresh deadline.
            reply = self.service._session.handle(request)
            self.service._log('existing_stream_command_result', result=reply)
            return reply
        except BaseException:
            try:
                self.service.stop('existing_stream_failure')
            except BaseException:
                pass
            raise


def serve_loaded_product(service, reader, writer):
    """A calls after actual Root attach, on its sole UART IO actor thread.

    reader/writer are existing trusted text streams. This opens no transport.
    During this loop do not mix local convenience commands with remote ids.
    """
    stream = ExistingStreamSession(service)
    def send(value):
        writer.write(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')
        writer.flush()
    failed = False
    try:
        send(stream.welcome())
        while True:
            line = reader.readline(8193)
            if not line:
                break
            _need(type(line) is str and len(line) <= 8192, 'bounded JSON command line')
            if line.strip():
                send(stream.dispatch(parse_line(line)))
    except Exception as error:
        failed = True
        send(dict(event='error', error_type=type(error).__name__, error=str(error)[:256], retry=False))
    finally:
        try:
            service.close()
        except Exception as error:
            failed = True
            send(dict(event='terminal_error', error_type=type(error).__name__, error=str(error)[:256], retry=False))
    return 1 if failed else 0
