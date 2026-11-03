"""Offline public-evidence adapter. No clock rebasing, live input or device IO."""
from dataclasses import dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

SCHEMA = 'deepeye.archival-display-record.v1'
REQUIREMENTS_SHA256 = '2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d'


def _need(ok, reason):
    if not ok:
        raise ValueError(reason)


def _text(value, cap=256):
    _need(type(value) is str and 0 < len(value) <= cap, 'bounded text')
    return value


def _hex(value, size):
    _need(type(value) is str and re.fullmatch('[0-9a-f]{%d}' % size, value), 'hex identity')
    return value


def _tick(value):
    _need(type(value) is str and re.fullmatch('0|[1-9][0-9]*', value), 'original decimal tick string')
    return value


def _uint(value):
    _need(type(value) is int and value >= 0, 'nonnegative integer')
    return value


def _boolean(value):
    _need(type(value) is bool, 'boolean')
    return value


def _number(value):
    _need(type(value) in (int, float) and math.isfinite(value), 'finite number')
    return value


def _vector(value, count):
    _need(type(value) is list and len(value) == count, 'vector shape')
    return [_number(x) for x in value]


def _copy(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _pose(value):
    _need(type(value) is dict, 'pose object')
    speed = _number(value['speed_m_s'])
    _need(speed >= 0, 'actual speed')
    return dict(position_m=_vector(value['position_m'], 3),
                orientation_xyzw=_vector(value['orientation_xyzw'], 4), speed_m_s=speed)


def _native(value):
    out = _pose(value)
    out.update(phase=_text(value['phase'], 64), ready=_boolean(value['ready']),
               running=_boolean(value['running']), tick_usec=_tick(value['tick_usec']),
               read_now_usec=_tick(value['read_now_usec']), revision=_tick(value['revision']))
    _need(type(value['fault']) is str and len(value['fault']) <= 256, 'fault text')
    _need(type(value['history']) is list and len(value['history']) <= 16, 'phase history')
    out.update(fault=value['fault'], history=[_text(x, 64) for x in value['history']],
               board_request_seq=_uint(value['board_request_seq']))
    receipt = value['board_receipt_sha256']
    _need(receipt == '' or re.fullmatch('[0-9a-f]{64}', receipt or '') is not None, 'receipt hash')
    out['board_receipt_sha256'] = receipt
    if 'target_speed_m_s' in value:
        out['target_speed_m_s'] = _number(value['target_speed_m_s'])
    return out


def _host(value):
    out = {k: _uint(value[k]) for k in ('send_qpc_ns', 'receive_qpc_ns')}
    interval = value['accepted_tick_qpc_interval_ns']
    _need(type(interval) is list and len(interval) == 2, 'accepted tick bracket')
    out['accepted_tick_qpc_interval_ns'] = [_uint(x) for x in interval]
    _need(out['send_qpc_ns'] <= out['receive_qpc_ns'] and interval[0] <= interval[1] <= out['receive_qpc_ns'], 'host-local chronology')
    return out


@dataclass(frozen=True)
class Context:
    operation_id: str
    world_epoch: str
    evidence_commit: str
    artifact_sha256: str
    artifact_name: str
    host_clock: str
    native_clock: str
    board_clock: str

    def __post_init__(self):
        for name in ('operation_id', 'world_epoch', 'artifact_name', 'host_clock', 'native_clock', 'board_clock'):
            _text(getattr(self, name))
        _hex(self.evidence_commit, 40)
        _hex(self.artifact_sha256, 64)
        _need(len({self.host_clock, self.native_clock, self.board_clock}) == 3, 'distinct clock domains')


def _record(kind, payload, context, pointer):
    _need(type(context) is Context, 'explicit archival context')
    return dict(schema=SCHEMA, kind=kind, authority='archival_read_only', live=False,
                may_drive=False, requirements_sha256=REQUIREMENTS_SHA256,
                provenance=dict(operation_id=context.operation_id, world_epoch=context.world_epoch,
                    evidence_commit=context.evidence_commit, commit_binding='caller_declared',
                    artifact_sha256=context.artifact_sha256, artifact_name=context.artifact_name,
                    record_pointer=_text(pointer, 512), clock_domains=dict(host=context.host_clock,
                    native=context.native_clock, board=context.board_clock)), payload=_copy(payload))


def _board(board_record):
    response = board_record['response']
    _need(type(response) is dict, 'board response')
    out = {k: response[k] for k in ('abi', 'op', 'status', 'boot_id', 'build_id', 'request_hash')}
    for key in out:
        _text(out[key])
    _hex(out['request_hash'], 64)
    out.update(request_seq=_uint(response['request_seq']), unknown=_boolean(response['unknown']))
    canonical = json.dumps(response, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')
    declared = _hex(board_record['response_sha256'], 64)
    _need(hashlib.sha256(canonical).hexdigest() == declared, 'canonical response SHA256')
    out.update(response_sha256=declared, hash_scope='canonical_JSON_without_newline',
               host_before_ns=_uint(board_record['host_before_ns']), host_returned_ns=_uint(board_record['host_returned_ns']))
    _need(out['host_before_ns'] <= out['host_returned_ns'], 'board-call host chronology')
    # Board absolute monotonic values stay in their own declared domain.
    r = response['result']
    result_keys = ('command_words', 'capture_words', 'measured', 'pwm_period', 'pwm_high',
                   'commit_before_monotonic_ns', 'returned_monotonic_ns',
                   'conservative_deadline_monotonic_ns', 'remaining_ns',
                   'stop_write_returned', 'status', 'fault', 'physical_zero_capture_proven')
    measured = {}
    for key in result_keys:
        if key not in r:
            continue
        value = r[key]
        if key == 'measured':
            names = ('action', 'yaw_q', 'pitch_q', 'speed_code', 'duration_ms')
            _need(type(value) is dict and all(type(value[n]) is int for n in names), 'measured command')
            measured[key] = {n: value[n] for n in names}
        elif key in ('command_words', 'capture_words', 'pwm_period', 'pwm_high'):
            size = {'command_words': 7, 'capture_words': 32, 'pwm_period': 3, 'pwm_high': 3}[key]
            _need(type(value) is list and len(value) == size, 'measurement words')
            measured[key] = [_uint(v) for v in value]
        elif key in ('stop_write_returned', 'physical_zero_capture_proven'):
            measured[key] = _boolean(value)
        else:
            measured[key] = _uint(value)
    out['measurement_or_stop'] = measured
    if 'host_deadline_qpc_ns' in board_record:
        out['host_deadline_qpc_ns'] = _uint(board_record['host_deadline_qpc_ns'])
    return out


def adapt_event(event, context, pointer='$'):
    """Adapt one original public event; unknown event types fail explicitly."""
    name = event['event']
    payload = dict(original_event=name, host_event_qpc_ns=_tick(event['host_qpc_ns']))
    if name == 'native-observed':
        sample = event['sample']
        payload.update(actual_pose=_native(sample['native']), host_sample=_host(sample['host']))
        kind = 'actual_pose'
    elif name == 'source-e4-correlated':
        source = event['public_observation']
        _need(source['world_epoch'] == context.world_epoch, 'source epoch')
        payload.update(public_pose=_pose(source), source_acquisition_qpc_ns=_tick(source['at_qpc_ns']),
                       source_completed_qpc_ns=_tick(source['completed_qpc_ns']),
                       source_record_sha256=_hex(source['source_record_sha256'], 64),
                       board_frame_sha256=_hex(source['board_frame_sha256'], 64),
                       segment_id=_text(source['segment_id']), quality=_uint(source['quality']))
        counts = source['channel_counts']
        _need(type(counts) is list and len(counts) == 4, 'four source channels')
        payload['channel_counts'] = [None if x is None else _uint(x) for x in counts]
        payload['actual_board'] = _board(event['actual_board'])
        kind = 'sensor_source'
    elif name == 'actual-pc-ai-completed':
        advice = event['advice']
        _need(advice['world_epoch'] == context.world_epoch, 'advice epoch')
        keys = ('status', 'reason', 'candidate_only', 'authorization', 'source_record_sha256',
                'board_frame_sha256', 'segment_id', 'source_acquisition_qpc_ns',
                'source_completed_qpc_ns', 'evaluated_qpc_ns', 'inference_completed_qpc_ns',
                'decoded_features', 'c3_observed', 'missing_feature_mask', 'quality', 'risk',
                'uncertainty', 'speed_limit_m_s', 'direction_world', 'target_direction_world')
        selected = {}
        for key in keys:
            if key not in advice:
                continue
            value = advice[key]
            if key in ('candidate_only', 'c3_observed'):
                selected[key] = _boolean(value)
            elif key in ('direction_world', 'target_direction_world'):
                selected[key] = _vector(value, 3)
            elif key == 'decoded_features':
                _need(type(value) is list and len(value) == 4, 'four decoded features')
                selected[key] = [None if x is None else _number(x) for x in value]
            elif key.endswith('_sha256'):
                selected[key] = _hex(value, 64)
            elif key.endswith('_qpc_ns'):
                selected[key] = _tick(value)
            elif key in ('missing_feature_mask', 'quality'):
                selected[key] = _uint(value)
            elif key in ('risk', 'uncertainty', 'speed_limit_m_s'):
                selected[key] = _number(value)
            else:
                selected[key] = _text(value)
        payload['advice'] = selected
        payload['source_pose'] = _pose(advice['source_pose'])
        payload['requested_command'] = _command(event['command'])
        kind = 'ai_candidate'
    elif name == 'actual-pwm-native-accepted':
        payload.update(requested_command=_command(event['command']), actual_board=_board(event['board']),
                       native_accepted=_boolean(event['native']['ok']), actual_pose=_native(event['native']['state']),
                       advice_source_acquisition_qpc_ns=(None if event.get('advice_source_acquisition_qpc_ns') is None
                           else _tick(event['advice_source_acquisition_qpc_ns'])))
        if 'initial_speed_latched' in event:
            payload['initial_preference'] = dict(latched=_boolean(event['initial_speed_latched']),
                                                latched_speed_m_s=_number(event['latched_initial_speed_m_s']))
        kind = 'actual_pwm'
    elif name == 'actual-board-init':
        r = event['response']
        payload['board_init'] = {k: _text(r[k]) for k in ('abi', 'op', 'status', 'boot_id', 'build_id',
                  'request_hash', 'scope_sha256', 'formal_acceptance')}
        payload['board_init'].update(initial_speed_code=_uint(r['initial_speed_code']), speed_applied=_boolean(r['speed_applied']))
        kind = 'board_init'
    else:
        raise ValueError('unsupported public event: ' + str(name)[:80])
    return _record(kind, payload, context, pointer)


def _command(value):
    out = {k: value[k] for k in ('yaw_q', 'pitch_q', 'speed_code')}
    _need(all(type(x) is int for x in out.values()) and out['speed_code'] >= 0, 'integer command')
    out['reason'] = _text(value['reason'])
    return out


def adapt_result(result, context, pointer='$'):
    _need(result['operation_id'] == context.operation_id and result['world_epoch'] == context.world_epoch, 'terminal operation/epoch')
    sample = result['arrival_native']
    close = result['board_close']
    stop = result.get('native_stop', {})
    error = result.get('native_stop_error')
    if error is not None:
        error = {k: _text(error[k]) for k in ('type', 'message')}
    payload = dict(reported_complete=_boolean(result['complete']), reported_arrival=_boolean(result['arrival']),
        actual_pose=_native(sample['native']), host_sample=_host(sample['host']),
        native_stop=dict(attempted=_boolean(result['native_stop_attempted']),
                         response_ok=None if 'ok' not in stop else _boolean(stop['ok']),
                         board_stop_acknowledged=None if 'board_stop_acknowledged' not in stop else _boolean(stop['board_stop_acknowledged']),
                         reason=None if result.get('native_stop_reason') is None else _text(result['native_stop_reason']), error=error),
        actual_board_stop=_board(result['board_stop']),
        connection_close=dict(exit_code=close['exit_code'], wait_confirmed=_boolean(close['wait_confirmed']),
            killed=_boolean(close['killed']), physical_zero_capture_proven=_boolean(close['physical_zero_capture_proven'])))
    _need(type(close['exit_code']) is int or close['exit_code'] is None, 'process exit code')
    return _record('terminal', payload, context, pointer)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--format', choices=('first-chain', 'phases', 'result'), required=True)
    for flag in ('operation-id', 'world-epoch', 'evidence-commit', 'host-clock', 'native-clock', 'board-clock'):
        parser.add_argument('--' + flag, required=True)
    args = parser.parse_args(argv)
    blob = args.input.read_bytes()
    _need(0 < len(blob) <= 2 * 1024 * 1024, 'bounded explicit public input')
    def invalid_number(value):
        raise ValueError('nonfinite JSON number: ' + value)
    def unique_object(pairs):
        out = {}
        for key, value in pairs:
            _need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    obj = json.loads(blob, parse_constant=invalid_number, object_pairs_hook=unique_object)
    context = Context(args.operation_id, args.world_epoch, args.evidence_commit,
        hashlib.sha256(blob).hexdigest(), args.input.name, args.host_clock, args.native_clock, args.board_clock)
    if args.format == 'first-chain':
        _need(type(obj) is list and len(obj) <= 32, 'bounded event list')
        records = [adapt_event(v, context, '$[%d]' % i) for i, v in enumerate(obj)]
    elif args.format == 'phases':
        _need(type(obj.get('first')) is dict and len(obj['first']) <= 16, 'phase dictionary')
        records = [adapt_event(v, context, '$.first.' + k) for k, v in obj['first'].items()]
        records.append(adapt_event(obj['last'], context, '$.last'))
    else:
        records = [adapt_result(obj, context)]
    # Construct every record before publishing any output; errors never yield a partial conversion.
    for record in records:
        print(json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
