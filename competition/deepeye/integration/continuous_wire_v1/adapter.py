"""Nonblocking state transitions for one Root-owned serial791 transport.

No IO, replay, reconnect, clock equality assumption, mission cap or motion grant.
Root authenticates load/source/transport, supplies clock uncertainty, journals
bytes, and enforces original native whole-volume/TTL/AI/source/Root/CAS fences.
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext
import hashlib
import json
import os
import re
import threading

ABI = 'DEEPEYE-LIVE-BOARD-791-v1'
SCOPE_SHA256 = '2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d'
LONG_TTL_BUILD = 'dc4e89ccf3db18c4f9871575efc399ba'
U32 = 0xffffffff
U63 = (1 << 63) - 1


class ProtocolError(ValueError):
    pass


def _need(ok, reason):
    if not ok:
        raise ProtocolError(reason)


def _int(v, lo=0, hi=U63):
    _need(type(v) is int and lo <= v <= hi, 'INTEGER_BOUND')
    return v


def _hex(v, width):
    _need(type(v) is str and re.fullmatch('[0-9a-f]{%d}' % width, v) is not None, 'HEX_ID')


def _raw(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def _json(raw):
    _need(type(raw) is bytes and 0 < len(raw) <= 32768 and raw.endswith(b'\n')
          and raw.count(b'\n') == 1, 'BOUNDED_RESPONSE_LINE')
    def pairs(items):
        out = {}
        for k, v in items:
            _need(k not in out, 'DUPLICATE_KEY')
            out[k] = v
        return out
    def nonfinite(_):
        raise ProtocolError('NONFINITE')
    return json.loads(raw.decode('utf8'), object_pairs_hook=pairs, parse_constant=nonfinite)


@dataclass(frozen=True)
class Binding:
    boot_id: str
    build_id: str
    request_hash: str
    session_id: int

    def __post_init__(self):
        _need(type(self.boot_id) is str and re.fullmatch('[A-Za-z0-9-]{1,64}', self.boot_id), 'BOOT_ID')
        _hex(self.build_id, 32)
        _hex(self.request_hash, 64)
        _int(self.session_id, 1, U32)


@dataclass(frozen=True, eq=False)
class Ticket:
    request_seq: int
    op: str
    raw: bytes


@dataclass(frozen=True)
class DetachedReply:
    op: str
    request_seq: int
    result_raw: bytes
    request_sha256: str
    response_sha256: str
    grant_deadline_ns: object
    authority: str = 'none'

    @property
    def result(self):
        return json.loads(self.result_raw)


def _quality(counts, q):
    _need(type(counts) is list and len(counts) == 4, 'FOUR_COUNTS')
    _int(q, 0, 0x10ff)
    _need(q & ~0x10ff == 0, 'QUALITY_NAMESPACE')
    for i, v in enumerate(counts):
        if v is not None:
            _int(v, 0, 4095)
        _need((v is not None) == bool(q & (1 << i)), 'VALIDITY_NULL')
        _need(v is not None or not q & (16 << i), 'NULL_SATURATION')
    _need(not q & 0x1000 or all(v is None for v in counts), 'FAULT_NULL')


def map_quality(counts, original_quality, adc_tick_ms, em_tick_ms):
    """Explicit old quality ->791 namespace; retain raw quality in Root evidence."""
    _int(original_quality, 0, 0x1fff)
    _int(adc_tick_ms, 0, U32 // 1000)
    _int(em_tick_ms, 0, adc_tick_ms)
    _need(not original_quality & 0x800, 'C3_HELD')
    _need(original_quality & 7 in (0, 7), 'EM_VALIDITY')
    expected = 0x700 if original_quality & 7 and em_tick_ms < adc_tick_ms else 0
    _need(original_quality & 0x700 == expected, 'EM_HELD_SOURCE_TIME')
    q = original_quality & 0x10ff
    _quality(counts, q)
    return q


def _curvature(speed):
    # Decimal PI upper bound makes floor conservative, never widens FAST ROM.
    with localcontext() as ctx:
        ctx.prec = 60
        pi_upper = Decimal('3.14159265358979323846264338327950288419716939937511')
        return int((Decimal(1125 * speed) / pi_upper) ** 2)


def _command(fields, maximum):
    _need(set(fields) == {'yaw_q', 'pitch_q', 'speed_code', 'duration_ms'}, 'APPLY_FIELDS')
    y = _int(fields['yaw_q'], -15000, 15000)
    p = _int(fields['pitch_q'], -15000, 15000)
    s = _int(fields['speed_code'], 0, 20)
    _int(fields['duration_ms'], 1, maximum)
    _need((s > 0 or y == p == 0) and y*y + p*p <= _curvature(s), 'FAST_CURVATURE')


class ContinuousWire:
    """One IO actor, at most one inflight; native/AI need not block on IO.

    mark_sent must precede any Root write attempt. Any subsequent uncertainty
    poisons this object permanently; Root's distinct safety tail is external.
    No command is automatically refreshed, stopped or resent by this module.
    """
    def __init__(self, binding, *, clock_error_ns=0, request_timeout_ns=4_000_000_000,
                 guard_ns=100_000_000, init_timeout_ns=30_000_000_000):
        _need(type(binding) is Binding, 'EXACT_BINDING')
        binding.__post_init__()
        self.binding = binding
        self.clock_error_ns = _int(clock_error_ns)
        self.request_timeout_ns = _int(request_timeout_ns, 1, 4_000_000_000)
        self.init_timeout_ns = _int(init_timeout_ns, 1, 30_000_000_000)
        self.guard_ns = _int(guard_ns, 100_000_000, 1_000_000_000)
        self.ready = self.closed = self.poisoned = False
        self.pending = None
        self.grant_deadline_ns = None
        self._seq = self._source = self._capture = 0
        self._em = -1
        self._sent = self._last_now = None
        self._init_prepared = False
        self._thread, self._pid = threading.get_ident(), os.getpid()
        self.failure = None

    def _owner(self):
        _need(threading.get_ident() == self._thread and os.getpid() == self._pid, 'SINGLE_IO_OWNER')
        _need(not self.poisoned and not self.closed, 'CLOSED_OR_UNKNOWN_NO_REPLAY')

    def _poison(self, reason):
        self.poisoned = True
        self.failure = reason
        self.pending = None
        self._sent = None

    def _time(self, now):
        _int(now)
        if self._last_now is not None and now < self._last_now:
            self._poison('CLOCK_REGRESSED')
            raise ProtocolError('CLOCK_REGRESSED')
        self._last_now = now

    def check_time(self, *, now_ns):
        self._owner()
        self._time(now_ns)
        limit = None
        if self._sent is not None:
            duration = self.init_timeout_ns if self.pending.op == 'init' else self.request_timeout_ns
            limit = self._sent + duration
        if self.grant_deadline_ns is not None:
            safe = self.grant_deadline_ns - self.guard_ns
            limit = safe if limit is None else min(limit, safe)
        if limit is not None and now_ns >= limit:
            self._poison('DEADLINE_OR_LINK_LOSS')
            raise ProtocolError('DEADLINE_OR_LINK_LOSS')

    def begin(self, op, *, now_ns, **fields):
        self.check_time(now_ns=now_ns)
        _need(self.pending is None, 'ONE_INFLIGHT')
        if op == 'init':
            _need(not self.ready and not self._init_prepared and not fields, 'INIT_ONCE')
            seq = 0
            fields = {k: getattr(self.binding, k) for k in ('boot_id', 'build_id', 'request_hash')}
        else:
            _need(self.ready and op in ('apply', 'sense', 'stop', 'shutdown'), 'READY_OPERATION')
            seq = _int(self._seq + 1, 1, U32)
            if op == 'apply':
                _command(fields, 12000 if self.binding.build_id == LONG_TTL_BUILD else 3000)
            elif op == 'sense':
                _need(set(fields) == {'source_seq','adc_tick_ms','em_tick_ms','counts','quality','source_digest'}, 'SENSE_FIELDS')
                _int(fields['source_seq'], self._source + 1, 65535 // 4)
                _int(fields['adc_tick_ms'], 0, U32 // 1000)
                _int(fields['em_tick_ms'], self._em + 1, fields['adc_tick_ms'])
                _quality(fields['counts'], fields['quality'])
                _hex(fields['source_digest'], 64)
            else:
                _need(not fields, 'TERMINAL_FIELDS')
            self._seq = seq  # Intrinsic uint bound, never reused after unsent cancellation.
        raw = _raw(dict(abi=ABI, op=op, request_seq=seq, **fields)) + b'\n'
        _need(len(raw) <= 16384, 'REQUEST_BOUND')
        self.pending = Ticket(seq, op, raw)
        if op == 'init':
            self._init_prepared = True
        return self.pending

    def _ticket(self, ticket):
        _need(type(ticket) is Ticket and self.pending is ticket, 'ORIGINAL_PENDING_TICKET')

    def mark_sent(self, ticket, *, now_ns):
        self.check_time(now_ns=now_ns)
        self._ticket(ticket)
        _need(self._sent is None, 'WRITE_ATTEMPT_ONCE')
        self._sent = now_ns

    def abort_unsent(self, ticket):
        self._owner()
        self._ticket(ticket)
        _need(self._sent is None, 'CANNOT_ABANDON_POSSIBLE_EFFECT')
        self.pending = None

    def fail(self, ticket, reason):
        self._owner()
        self._ticket(ticket)
        _need(type(reason) is str and 0 < len(reason) <= 192, 'FAILURE_REASON')
        self._poison(reason)

    def _capture_result(self, result, request):
        keys = {'command_words','capture_words','measured','pwm_period','pwm_high',
                'commit_before_monotonic_ns','returned_monotonic_ns',
                'conservative_deadline_monotonic_ns','remaining_ns'}
        _need(type(result) is dict and set(result) == keys, 'ACTUAL_CAPTURE_REQUIRED')
        y, p, s, ttl = (request[k] for k in ('yaw_q','pitch_q','speed_code','duration_ms'))
        command = [y & 65535, p & 65535, 1, s, ttl, request['request_seq'], request['request_seq']]
        _need(type(result['command_words']) is list and all(type(x) is int for x in result['command_words'])
              and result['command_words'] == command, 'APPLY_COMMAND_ASSOCIATION')
        w = result['capture_words']
        _need(type(w) is list and len(w) == 32, 'FULL32_CAPTURE')
        for value in w:
            _int(value, 0, U32)
        _need(w[0] > self._capture and w[1:6] == [command[5],command[6],(s<<8)|1,(command[1]<<16)|command[0],ttl]
              and w[30:] == [self.binding.session_id,0x47303550], 'CAPTURE_IDENTITY')
        u64 = lambda i: w[i] | w[i+1] << 32
        applied, deadline, captured = u64(6), u64(8), u64(10)
        _need(applied < captured < deadline and deadline-applied == ttl*50000, '50MHZ_TTL')
        starts, ends = [u64(18+2*i) for i in range(3)], [u64(24+2*i) for i in range(3)]
        for period, high, start, end, expected in zip(w[12:15],w[15:18],starts,ends,(125000+8*y,125000+8*p,25000+500*s)):
            _need(abs(period-1000000)<=1 and 0<high<period and abs(high-expected)<=1
                  and 0<start<end<=U32 and end-start==period, 'MEASURED_PWM_WITNESS')
        _need(max(starts)-min(starts)<=1 and max(ends)-min(ends)<=1
              and captured>=applied+max(ends), 'CAPTURE_CHRONOLOGY')
        measured = dict(action=1 if s else 0,yaw_q=y,pitch_q=p,speed_code=s,duration_ms=ttl)
        _need(type(result['measured']) is dict and all(type(v) is int for v in result['measured'].values())
              and result['measured'] == measured and result['pwm_period']==w[12:15]
              and result['pwm_high']==w[15:18], 'MEASURED_TARGET_MISMATCH')
        before = _int(result['commit_before_monotonic_ns'])
        returned = _int(result['returned_monotonic_ns'], before)
        board_deadline = _int(result['conservative_deadline_monotonic_ns'], returned+1)
        remaining = _int(result['remaining_ns'], 1, ttl*1000000)
        _need(board_deadline == before+ttl*1000000 and remaining == board_deadline-returned, 'BOARD_GRANT_RELATION')
        # Board absolute timestamps NEVER become PC timestamps. Debiting the
        # full observed RTT via the local send lower bound is conservative.
        local_deadline = _int(self._sent + remaining - self.clock_error_ns)
        _need(self._last_now < local_deadline-self.guard_ns, 'CAPTURE_RETURNED_TOO_LATE')
        return local_deadline, w[0]

    def finish(self, ticket, response_raw, *, now_ns):
        self._owner()
        self._ticket(ticket)
        _need(self._sent is not None, 'WRITE_INTENT_REQUIRED')
        try:
            self.check_time(now_ns=now_ns)
            response = _json(response_raw)
            _need(type(response) is dict and response.get('abi') == ABI
                  and response.get('status') == 'COMPLETE' and response.get('op') == ticket.op,
                  'COMPLETE_CORRELATED_RESPONSE_REQUIRED')
            _need(all(response.get(k)==getattr(self.binding,k) for k in ('boot_id','build_id','request_hash')), 'LOAD_BINDING')
            request = json.loads(ticket.raw)
            grant = self.grant_deadline_ns
            if ticket.op == 'init':
                _need(set(response)=={'abi','op','status','scope_sha256','boot_id','build_id','request_hash',
                                      'initial_speed_code','speed_applied','formal_acceptance'}
                      and type(response['initial_speed_code']) is int and response['initial_speed_code']==2
                      and response.get('scope_sha256') == SCOPE_SHA256 and response.get('speed_applied') is False
                      and response.get('formal_acceptance') == 'not_run', 'REV2_INIT_NO_MOTION')
                result = response
            else:
                _need(set(response)=={'abi','op','request_seq','status','unknown','boot_id','build_id','request_hash','io_count','result'}
                      and type(response['request_seq']) is int and response['request_seq']==ticket.request_seq
                      and response['unknown'] is False, 'ORIGINAL_RESPONSE_NOT_UNKNOWN')
                _int(response['io_count'], 0, 4096)
                result = response['result']
                _need(type(result) is dict, 'RESULT_SHAPE')
                if ticket.op == 'apply':
                    grant, capture = self._capture_result(result, request)
                    self._capture = capture
                elif ticket.op == 'sense':
                    _need(set(result)=={'wire_hex','decoded','result_rows','tag','source_digest','source_seq','correlation','quality','adc_tick_ms','em_tick_ms'}, 'SENSE_REPLY_FIELDS')
                    _need(all(type(result[k]) is int and result[k]==request[k] for k in ('source_seq','quality','adc_tick_ms','em_tick_ms'))
                          and result['source_digest']==request['source_digest'], 'SENSE_SOURCE_ASSOCIATION')
                    wire = result['wire_hex']
                    _need(type(wire) is str and 0<len(wire)<=504 and re.fullmatch('[0-9a-f]+',wire) and len(wire)%2==0
                          and type(result['decoded']) is list and len(result['decoded'])==4
                          and type(result['result_rows']) is list and len(result['result_rows'])==4, 'BOUNDED_FOUR_FRAME_REPLY')
                    _int(result['tag'], 1, U32)
                    _need(result['correlation']=='FOUR_FRAME_CRC_SOURCE_CONSISTENT', 'SERVER_CORRELATION_LABEL')
                    self._source, self._em = request['source_seq'], request['em_tick_ms']
                else:
                    _need(set(result)=={'stop_write_returned','status','fault','physical_zero_capture_proven'}
                          and result['stop_write_returned'] is True and result['physical_zero_capture_proven'] is False,
                          'TERMINAL_WRITE_NOT_ZERO_CAPTURE')
                    _int(result['status'],0,U32); _int(result['fault'],0,U32)
                    self.closed = True
                    grant = None
            reply = DetachedReply(ticket.op,ticket.request_seq,_raw(result),hashlib.sha256(ticket.raw[:-1]).hexdigest(),
                                  hashlib.sha256(response_raw).hexdigest(),grant)
            self.ready = True
            self.grant_deadline_ns = grant
            self.pending = self._sent = None
            return reply
        except BaseException as error:
            self._poison(type(error).__name__)
            if isinstance(error, ProtocolError):
                raise
            if isinstance(error, Exception):
                raise ProtocolError('UNKNOWN_RESPONSE_OR_INTERRUPTED_EFFECT') from error
            raise
