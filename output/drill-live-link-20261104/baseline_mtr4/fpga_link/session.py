"""V8-compatible display session with durable sequences and finite pose commands."""
from __future__ import annotations
import dataclasses
import json
import math
import os
from pathlib import Path
import struct
import time
import uuid

from pc.codec import crc16_ccitt_false, decode_reply, SOURCE_TO_CODE

UINT32_MAX = 0xFFFFFFFF
DEFAULT_MOVE_MS = 500  # Human accepted small and60deg/35deg dual-axis trials.


class LinkError(RuntimeError):
    pass


class SequenceJournal:
    """Reserve before transmit. A crash may skip a seq, but never reuse a frame."""
    def __init__(self, path, initialize=None):
        self.path = Path(path)
        if self.path.exists():
            if initialize is not None:
                raise LinkError('sequence journal exists; refusing to overwrite')
            record = json.loads(self.path.read_text(encoding='utf8'))
            self.next_seq = record['next_seq']
        else:
            if type(initialize) is not int or not 1 <= initialize <= UINT32_MAX:
                raise LinkError('first use requires explicit initial sequence after MCU reset')
            self.next_seq = initialize
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Caller holds the single-process lock before constructing journal.
            with self.path.open('x', encoding='utf8') as f:
                json.dump({'next_seq': initialize}, f)
                f.flush()
                os.fsync(f.fileno())
        if type(self.next_seq) is not int or not 1 <= self.next_seq <= UINT32_MAX + 1:
            raise LinkError('invalid sequence journal; do not reset it automatically')

    def reserve(self):
        if self.next_seq > UINT32_MAX:
            raise LinkError('sequence exhausted; MCU reset and new journal required')
        seq = self.next_seq
        temp = self.path.with_suffix(self.path.suffix + '.new')
        with temp.open('w', encoding='utf8') as f:
            json.dump({'next_seq': seq + 1}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, self.path)
        self.next_seq = seq + 1
        return seq


def encode(op, seq, source, yaw=0, pitch=0, ms=0, source_seq=0, observation_seq=0):
    if type(seq) is not int or not 1 <= seq <= UINT32_MAX:
        raise LinkError('invalid MCU sequence')
    frame = bytearray(32)
    frame[:4] = bytes([0xD3, 0x4C, 1, op])
    struct.pack_into('<I', frame, 4, seq)
    frame[8] = SOURCE_TO_CODE[source]
    if op == 2:
        if not -9000 <= yaw <= 9000 or not -4500 <= pitch <= 6800 or not 100 <= ms <= 1000:
            raise LinkError('V8 target outside calibrated display range')
        struct.pack_into('<hh', frame, 10, yaw, pitch)
        struct.pack_into('<HII', frame, 18, ms, source_seq, observation_seq)
    struct.pack_into('<H', frame, 30, crc16_ccitt_false(frame[:30]))
    return bytes(frame)


def _integer(value, name, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise LinkError('%s must be integer %d..%d' % (name, lower, upper))
    return value


def _angle(value, name, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not lower <= value <= upper:
        raise LinkError('%s must be finite within %d..%d degrees' % (name, lower, upper))
    return int(round(value * 100))


class DisplaySession:
    def __init__(self, transport, journal, *, source='MANUAL', clock=time.monotonic, simulation=False):
        if source not in SOURCE_TO_CODE:
            raise LinkError('invalid declared action source')
        self.transport, self.journal, self.source = transport, journal, source
        self.clock, self.started = clock, clock()
        self.session_id = uuid.uuid4().hex
        self.request_id = 0
        self.failed = False
        self.simulation = simulation

    def clock_ms(self):
        return int((self.clock() - self.started) * 1000)

    def _send(self, op, yaw=0, pitch=0, ms=0, source_seq=0, observation_seq=0, require_ok=True, deadline_ms=None):
        seq = self.journal.reserve()
        if deadline_ms is not None and self.clock_ms() >= deadline_ms:
            raise LinkError('expired before UART dispatch; reserved sequence skipped')
        self.transport.write_frame(encode(op, seq, self.source, yaw, pitch, ms, source_seq, observation_seq))
        raw = self.transport.read_frame(0.3)
        if raw is None:
            raise LinkError('MCU reply timeout; no replay')
        reply = decode_reply(raw)
        if reply.seq != seq:
            raise LinkError('MCU reply sequence mismatch')
        if require_ok and reply.result_code:
            raise LinkError('MCU refused: ' + reply.result)
        return reply

    def stop(self):
        # STOP is best effort even after a rejected/partially transmitted request.
        return self._send(3, require_ok=False)

    def connect(self):
        try:
            self.stop()
            reply = self._send(4, require_ok=False)
            if reply.result_code == 6:
                raise LinkError('MCU high-water sequence is ahead of journal; reset MCU explicitly, never guess/replay')
            self._capabilities(reply)
            return self.record(reply, 'ready')
        except Exception:
            self.failed = True
            raise

    @staticmethod
    def _capabilities(reply):
        if not reply.gimbal_output_compiled_enabled or reply.requested_duty_permille:
            raise LinkError('V8/MTR2 gimbal capabilities and motorOFF required')

    @staticmethod
    def _fresh(reply):
        DisplaySession._capabilities(reply)
        if reply.last_joho_error != 0 or not reply.yaw_feedback.fresh or not reply.pitch_feedback.fresh:
            raise LinkError('both real gimbal positions must be fresh before ARM')

    def handle(self, request):
        if self.failed:
            raise LinkError('session fault latched; reconnect explicitly without replay')
        try:
            if not isinstance(request, dict):
                raise LinkError('JSON object required')
            op = request.get('op')
            fields = {'session', 'request_id', 'expires_ms', 'op'}
            if op == 'pose':
                fields |= {'yaw_deg','pitch_deg','move_ms','source_seq','observation_seq'}
            if op not in ('pose','home','status','stop') or set(request) - fields:
                raise LinkError('unsupported command/field; motor output is unavailable')
            if request.get('session') != self.session_id:
                raise LinkError('old or different SSH session')
            rid = _integer(request.get('request_id'), 'request_id', 1, UINT32_MAX)
            deadline = _integer(request.get('expires_ms'), 'expires_ms', 0, 2**53)
            if op != 'stop' and (rid <= self.request_id or not 0 < deadline - self.clock_ms() <= 1000):
                raise LinkError('duplicate/stale/expired request; never replayed')
            self.request_id = max(self.request_id, rid)
            yaw, pitch, ms, src, obs = 0, 0, DEFAULT_MOVE_MS, 0, 0
            if op == 'pose':
                yaw = _angle(request.get('yaw_deg'), 'yaw_deg', -90, 90)
                pitch = _angle(request.get('pitch_deg'), 'pitch_deg', -45, 68)
                ms = _integer(request.get('move_ms', DEFAULT_MOVE_MS), 'move_ms', 100, 1000)
                src = _integer(request.get('source_seq', 0), 'source_seq', 0, UINT32_MAX)
                obs = _integer(request.get('observation_seq', 0), 'observation_seq', 0, UINT32_MAX)
            if op in ('pose', 'home'):
                self._fresh(self._send(4, require_ok=False))
                self._fresh(self._send(1, deadline_ms=deadline))
                reply = self._send(2, yaw, pitch, ms, src, obs, deadline_ms=deadline)
            else:
                reply = self._send(3 if op == 'stop' else 4, require_ok=False)
            # Deadline also bounds command acceptance/reply time on the board.
            if op not in ('stop','status') and self.clock_ms() > deadline:
                raise LinkError('request expired during MCU exchange; stop, no retry')
            return self.record(reply, op)
        except Exception:
            self.failed = True
            try:
                self.stop()
            except Exception:
                pass
            raise

    def record(self, reply, event):
        return {'event':event, 'session':self.session_id, 'clock_ms':self.clock_ms(),
                'request_id':self.request_id, 'declared_source':self.source,
                'physical_path':'PC network SSH -> PYNQ PS -> AXI UARTLite in PL -> G3507 UART1',
                'simulation':self.simulation, 'status':dataclasses.asdict(reply),
                'motor_output':False, 'measured_rpm':None,
                'target_angles_are_commands':True, 'raw_feedback_is_measurement':not self.simulation,
                'uart_ack_is_not_arrival':True,
                'product_execution_gate_verified_by_this_adapter':False}


def strict_json(line):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise LinkError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid(value):
        raise LinkError('nonfinite JSON value: ' + value)
    return json.loads(line, object_pairs_hook=pairs, parse_constant=invalid)
