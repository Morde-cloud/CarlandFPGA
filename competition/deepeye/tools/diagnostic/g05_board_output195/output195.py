"""B195 detached G05 output adapter. Never grants motion or touches hardware.

A trusted original callsite must independently retain load/BOOT/epoch/operation,
source/AI/Root/capture/release/clock custody and the final commit fence. Supplying
matching JSON, scalar deadlines or a PID to this function does not establish it.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[5]
DECODER_PATH = 'handoffs/b/B-DEEPEYE-G05P-CAPTURE-MOTION-DECODE-20261031-132/g05p_capture_decoder132.py'
DECODER_SHA256 = '163b9a3f03245a69515cd49e7583898e280b2a3783676843254d96ce907a3c5b'
CAP_KEYS = {'mapped_fpga', 'source', 'command', 'actor', 'health', 'session', 'previous_action'}
_DECODER = None


class Refused(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise Refused(reason)


def uint(value, high=(1 << 63)-1):
    need(type(value) is int and 0 <= value <= high, 'INTEGER_RANGE')
    return value


def decoder():
    global _DECODER
    if _DECODER is None:
        p = REPO / DECODER_PATH
        need(hashlib.sha256(p.read_bytes()).hexdigest() == DECODER_SHA256, 'DECODER_PIN')
        spec = importlib.util.spec_from_file_location('_b195_pinned_b132', p)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _DECODER = module
    return _DECODER


def command_words(*, yaw_q, pitch_q, profile, speed_code, ttl_ms, command_id, transport_tag):
    """Exact seven uint32 stage words. TTL is not a host deadline renewal."""
    for v in (yaw_q, pitch_q):
        need(type(v) is int and -15000 <= v <= 15000, 'AXIS_RANGE')
    for v in (profile, speed_code, ttl_ms, command_id, transport_tag):
        uint(v, 0xffffffff)
    need(command_id > 0, 'COMMAND_ZERO')
    try:
        decoder()._validate_mapper(yaw_q, pitch_q, speed_code, profile, ttl_ms, 'planned')
    except Exception as e:
        raise Refused('MAPPER_REJECTED') from e
    return (yaw_q & 0xffff, pitch_q & 0xffff, profile, speed_code,
            ttl_ms, command_id, transport_tag)


def _raw_json(hex_text):
    need(type(hex_text) is str and 0 < len(hex_text) <= 8192
         and len(hex_text) % 2 == 0 and re.fullmatch('[0-9a-f]+', hex_text), 'RAW_RECEIPT')
    def pairs(items):
        d = {}
        for k, v in items:
            need(k not in d, 'DUPLICATE_RAW_KEY')
            d[k] = v
        return d
    return json.loads(bytes.fromhex(hex_text), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Refused('NONFINITE')))


def release_readback(rows, *, cumulative_io, io_limit):
    """Check the original release method's five actual raw I/O records.

    Indices remain cumulative; this checker does not reconstruct or authenticate
    the preceding journal. A retains and verifies the complete original prefix.
    """
    uint(cumulative_io, 0xffffffff); uint(io_limit, 0xffffffff)
    need(0 < cumulative_io <= io_limit and type(rows) is list and len(rows) == 5,
         'RELEASE_INCOMPLETE')
    expected = [('read', 8, None), ('read', 16, None), ('write', 12, 5),
                ('read', 8, None), ('read', 16, None)]
    last_time = -1
    request = pid = None
    for i, (row, (kind, offset, value)) in enumerate(zip(rows, expected)):
        need(type(row) is dict and set(row) == {'index', 'started_raw_hex', 'returned_raw_hex'},
             'RELEASE_ROW_SCHEMA')
        a, z = _raw_json(row['started_raw_hex']), _raw_json(row['returned_raw_hex'])
        need(set(a) == {'request_id','io','kind','offset','value','pid','monotonic_ns'}
             and set(z) == {'request_id','io','kind','value','monotonic_ns'}, 'RELEASE_RAW_SCHEMA')
        index = cumulative_io - 4 + i
        uint(row['index'], 0xffffffff); uint(a['io'], 0xffffffff); uint(z['io'], 0xffffffff)
        need(index > 0 and row['index'] == a['io'] == z['io'] == index, 'RELEASE_INDEX')
        need(a['kind'] == z['kind'] == kind and a['offset'] == offset and a['value'] == value,
             'RELEASE_ACCESS')
        need(type(a['request_id']) is str and re.fullmatch('[A-Za-z0-9_-]{1,64}', a['request_id']),
             'RELEASE_REQUEST')
        uint(a['pid'], 0xffffffff); need(a['pid'] > 0, 'RELEASE_PID')
        if i == 0:
            request, pid = a['request_id'], a['pid']
        need(request == a['request_id'] == z['request_id'] and pid == a['pid'], 'RELEASE_IDENTITY')
        lo, hi = uint(a['monotonic_ns']), uint(z['monotonic_ns'])
        need(last_time <= lo <= hi, 'RELEASE_TIME_ORDER'); last_time = hi
        if kind == 'write':
            need(z['value'] is None, 'RELEASE_WRITE_READBACK')
        else:
            v = uint(z['value'], 0x7f if offset == 8 else 0xffffffff)
            if offset == 16:
                need(v == 0, 'RELEASE_FAULT')
            else:
                need(v & 1 and not v & 2, 'RELEASE_NOT_LIVE')
                need(bool(v & 0x20) == (i == 0), 'RELEASE_LATCH_STATE')
                if i == 3:
                    need(not v & 0x68, 'RELEASE_BUSY')
    return {'first_io': cumulative_io-4, 'last_io': cumulative_io,
            'request_id': request, 'board_monotonic_end_ns': last_time,
            'authentication': 'NOT_ESTABLISHED_BY_THIS_CHECKER'}


def inspect_output(request, *, expected_identity_words, expected_operation_id,
                   expected_command_words, observation_seq, frame_seq,
                   now_host_ns, step_ns, deadline_caps_ns, now_board_tick,
                   release_receipts, cumulative_io, io_limit,
                   effect_unknown=False, retired=False):
    """Return a measured target reference only, with no authority object.

    Full sequence widths are independent. No counter truncation, clock-domain
    inference, automatic replay or fallback to submitted command metadata.
    """
    need(type(effect_unknown) is bool and type(retired) is bool, 'STATE_TYPE')
    need(not effect_unknown, 'UNKNOWN_EFFECT_NO_REPLAY')
    need(not retired, 'STOP_OR_RETIRED')
    uint(observation_seq, 65535); uint(frame_seq, 65535)
    need(observation_seq > 0, 'OBSERVATION_ZERO')
    now, dt = uint(now_host_ns), uint(step_ns, 100_000_000)
    need(dt > 0, 'STEP_ZERO')
    need(type(deadline_caps_ns) is dict and set(deadline_caps_ns) == CAP_KEYS, 'DEADLINE_CAPS')
    caps = []
    for name, value in deadline_caps_ns.items():
        if value is None:
            need(name == 'previous_action', 'MISSING_DEADLINE')
        else:
            caps.append(uint(value))
    end = min(caps)
    need(now < end and now + dt <= end, 'STEP_CROSSES_ORIGINAL_DEADLINE')
    d = decoder().decode_request(request)
    need(d['status'] == 'DECODED_BRACKET_CORRELATED', 'CAPTURE_' + d['status'])
    original = d['preserved_input']['original_record']
    need(type(expected_identity_words) is tuple and len(expected_identity_words) == 13
         and list(expected_identity_words) == original['identity_words'], 'EXPECTED_IDENTITY')
    for value in expected_identity_words:
        uint(value, 0xffffffff)
    need(type(expected_operation_id) is str and expected_operation_id == original.get('operation_id'),
         'EXPECTED_OPERATION')
    decision = original['decision']
    words = command_words(yaw_q=decision['yaw_q'], pitch_q=decision['pitch_q'],
        profile=decision['profile'], speed_code=decision['speed'], ttl_ms=decision['ttl_ms'],
        command_id=original['command_id'], transport_tag=original['transport_tag'])
    need(type(expected_command_words) is tuple and len(expected_command_words) == 7
         and words == expected_command_words, 'EXPECTED_COMMAND')
    for value in expected_command_words:
        uint(value, 0xffffffff)
    held = d['facts']['capture_sequence']
    spans = d['preserved_input']['held_observations']
    before, after = spans['before'], spans['after']
    latest_before, latest_after = before.get('latest_seq'), after.get('latest_seq')
    need(type(latest_before) is int and type(latest_after) is int
         and held <= latest_before <= latest_after <= 0xffffffff, 'LATEST_SEQUENCE_ORDER')
    need(after['cycle_tick'] <= uint(now_board_tick) < original['deadline_tick'], 'BOARD_EXPIRED')
    released = release_readback(release_receipts, cumulative_io=cumulative_io, io_limit=io_limit)
    measured = d['facts']['measured_mapper_candidate']
    need(measured['speed_code'] > 0, 'ZERO_SPEED_IS_NOT_MOVEMENT')
    return dict(schema='B195_DETACHED_MEASURED_OUTPUT_REFERENCE_V1',
        status='MEASURED_REFERENCE_CONSISTENT', mode='FPGA_OUTPUT_REFERENCE',
        action_source='MEASURED_G05_CAPTURE', motion_authority=False,
        original_typed_A_callsite_required=True, physical_board_verified=False,
        formal_acceptance=False, operation_id=expected_operation_id,
        command_words=list(words), held_capture_seq=held,
        latest_result_seq_before=latest_before, latest_result_seq_after=latest_after,
        observation_seq=observation_seq, frame_seq=frame_seq,
        measured_target_codes={k: measured[k] for k in ('yaw_q','pitch_q','speed_code')},
        measured_pwm=d['facts']['pwm_channels'], nominal_metadata=decision,
        profile=decision['profile'], original_deadline_caps_ns=dict(deadline_caps_ns),
        reference_deadline_ns=end, proposed_step_ns=dt, release= released,
        cumulative_g05_io=cumulative_io,
        interpretation='Codes are decoded target references. Original motion acceleration/curvature/collision integration remains with A; no actual pose or instantaneous angular rate is inferred.')
