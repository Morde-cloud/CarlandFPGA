"""Pure original-byte planning and TRACE94 frame correlation; no authority gate."""
from dataclasses import dataclass
import binascii
import copy
import hashlib
import json
import struct
from dependencies128 import input113, codec, INPUT_SHA, CODEC_SHA

WORK_ID = 'B-DEEPEYE-ORIGINAL-TRACE94-ADAPTER-20261031-128'
PROFILE = 'TRACE-PAYLOAD-1US-PRIVATE-v2'
U32 = (1 << 32) - 1
AUTHORITY = 'NOT_EVALUATED_BY_THIS_ADAPTER'

class Refused(ValueError):
    pass

def need(value, code):
    if not value:
        raise Refused(code)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def hex_digest(value, digits):
    return type(value) is str and len(value) == digits and all(c in '0123456789abcdef' for c in value)

@dataclass(frozen=True)
class OriginalBytes:
    request: bytes
    source: bytes
    companions: tuple

    def inventory(self):
        return {'request_bytes': len(self.request), 'source_bytes': len(self.source),
                'companion_bytes': [len(x) for x in self.companions],
                'request_sha256': digest(self.request), 'source_sha256': digest(self.source),
                'companion_sha256': [digest(x) for x in self.companions]}

@dataclass(frozen=True)
class Preparation:
    status: str
    reason: str | None
    original: OriginalBytes
    plan: object
    authority_not_evaluated: str = AUTHORITY

class Plan:
    """Detached snapshot; public facts are copies, original bodies remain bytes."""
    def __init__(self, original, normalized, build_binding):
        self.original = original
        self._scan = copy.deepcopy(normalized.scan)
        self._lineage = copy.deepcopy(normalized.lineage)
        self._association = copy.deepcopy(normalized.association)
        self._provenance = copy.deepcopy(normalized.provenance)
        self._build = copy.deepcopy(build_binding)

    def facts(self):
        return validated_plan(self)._facts()

    def _facts(self):
        return {'status': 'TRACE94_REPRESENTABLE_DATA', 'scan': copy.deepcopy(self._scan),
                'lineage': copy.deepcopy(self._lineage), 'association': copy.deepcopy(self._association),
                'declared_provenance': copy.deepcopy(self._provenance),
                'build_binding': copy.deepcopy(self._build), 'original_inventory': self.original.inventory(),
                'authority_not_evaluated': AUTHORITY,
                'source_numerical_semantics': 'OPAQUE_NOT_INTERPRETED',
                'companion_semantics': 'OPAQUE_NOT_INTERPRETED',
                'clock_relationship': 'CALLER_DECLARED_EQUAL_ONLY',
                'build_digest_relationship': 'DECLARED_CANONICAL_DIGEST_PREFIX_MATCH_ONLY',
                'closure_contents_verified': False,
                'input_normalizer_sha256': INPUT_SHA, 'codec_sha256': CODEC_SHA}

def prepare_bytes(request_bytes, source_scan_bytes, companion_bytes, *, build_binding):
    # Invalid object types are rejected without invoking caller methods. Exact
    # byte arguments, including refused input, are retained without reserializing.
    need(type(request_bytes) is bytes and type(source_scan_bytes) is bytes, 'EXACT_BYTES_REQUIRED')
    need(type(companion_bytes) in (list, tuple) and len(companion_bytes) == 4 and
         all(type(x) is bytes for x in companion_bytes), 'EXACT_FOUR_COMPANION_BYTES_REQUIRED')
    original = OriginalBytes(request_bytes, source_scan_bytes, tuple(companion_bytes))
    try:
        n = input113.normalize_external_original_scan_v1(request_bytes, source_scan_bytes, original.companions)
        need(type(build_binding) is dict and set(build_binding) == {
            'canonical_build_id_full_sha256', 'source_closure_file_sha256', 'operation_id', 'request_hash'}, 'BUILD_BINDING_FIELDS')
        b = build_binding
        need(all(type(v) is str and len(v) <= 192 for v in b.values()), 'BUILD_BINDING_PLAIN_STRINGS')
        need(hex_digest(b['canonical_build_id_full_sha256'], 64) and hex_digest(b['source_closure_file_sha256'], 64), 'BUILD_HASH_FORMAT')
        need(b['operation_id'] == n.lineage['operation_id'] and b['request_hash'] == n.lineage['request_hash'], 'OPERATION_REQUEST_CORRELATION')
        need(b['canonical_build_id_full_sha256'][:32] == n.lineage['build_id_hex128'] and int(n.lineage['build_id_hex128'], 16) != 0, 'BUILD_ID_PREFIX')
        need(n.lineage['tag'] > 0, 'NONZERO_ARM_TAG')
        need(n.association['profile_id'] == PROFILE and n.association['e'] == 0, 'TRACE94_FIXED_PROFILE_E0')
        # The normalizer already checks exact63-bit sums, common acquisition,
        # ordered lanes, common session/view, flags and nonwrapping sequences.
        for lane in n.scan['lanes']:
            value = lane['raw_sample_uint16']
            need(value is None or value <= 4095, 'UINT16_NOT_REPRESENTABLE_AS_CODEC_UINT12')
            if lane['mapped_flags']['held']:
                need(lane['source_tick_us'] < lane['acquisition_tick_us'], 'HELD_SUBMICROSECOND_NOT_REPRESENTABLE')
        return Preparation('TRACE94_PLAN_PREPARED', None, original, Plan(original, n, b))
    except (input113.Refused, Refused) as exc:
        return Preparation('REFUSED_WITH_ORIGINAL_BYTES', str(exc), original, None)

def prepare_normalized(normalized, *, build_binding):
    need(type(normalized) is input113.NormalizedExternalScanV1, 'EXACT_INPUT113_RECORD_REQUIRED')
    # Re-normalize retained bytes; mutable dictionaries and old authority fields
    # are neither trusted nor propagated as authority assertions.
    return prepare_bytes(normalized.request_bytes, normalized.source_bytes,
                         normalized.companion_bytes, build_binding=build_binding)

def validated_plan(plan):
    """Rebuild consumer state from original bytes, never from mutable caches.

    This rechecks representability and declared relationships. It does not
    authenticate those bytes or grant any producer, clock or physical authority.
    """
    need(type(plan) is Plan and type(plan.original) is OriginalBytes, 'PREPARED_PLAN_REQUIRED')
    original = plan.original
    prepared = prepare_bytes(original.request, original.source, original.companions,
                             build_binding=plan._build)
    need(prepared.plan is not None, 'PLAN_ORIGINAL_BYTES_REFUSED: ' + str(prepared.reason))
    return prepared.plan

def correlate_collected(plan, wire, companions, result_rows):
    """Correlate complete raw E4 frames to this plan, not to historic fixtures.

    The unchanged trace code-section parser is used exactly as in the existing
    private transport wrapper (payload revision2 -> parser revision1 only).
    No synthetic legacy source identity or profile is constructed.
    """
    plan = validated_plan(plan)
    need(type(wire) is bytes, 'EXACT_WIRE_BYTES_REQUIRED')
    need(type(companions) in (tuple, list) and len(companions) <= 4 and
         all(type(x) is bytes for x in companions), 'BOUNDED_COMPANION_BYTES_REQUIRED')
    retained = {'wire': wire, 'companions': tuple(companions), 'original': plan.original}
    facts = {'authority_not_evaluated': AUTHORITY, 'retained': retained,
             'wire_bytes': len(wire), 'mandatory_companion_bytes': sum(map(len, companions)),
             'wire_and_mandatory_companion_bytes': len(wire) + sum(map(len, companions)),
             'source_semantics': 'OPAQUE_NOT_INTERPRETED', 'companion_semantics': 'OPAQUE_NOT_INTERPRETED',
             'parser': 'unchanged trace_candidate.decode_payload; E4/CRC envelope checked by adapter128',
             'codec_sha256': CODEC_SHA, 'legacy_transport_authority_view_used': False}
    try:
        need(tuple(companions) == plan.original.companions, 'COMPANION_BYTES_MISMATCH')
        need(0 < len(wire) <= 252, 'COMPLETE_SCAN_WIRE_BOUND')
        need(type(result_rows) in (list, tuple) and len(result_rows) == 4, 'FOUR_RESULT_ROWS_REQUIRED')
        frames = []; offset = 0; previous_id = None; previous_end = None
        for lane, row in zip(plan._scan['lanes'], result_rows):
            need(type(row) is dict and 5 <= len(row) <= 9 and
                 all(type(k) is str for k in row) and
                 all(type(row.get(k)) is int and 0 <= row[k] <= U32 for k in ('id','bytes','error','rx_before','rx_end')), 'RESULT_FIELDS')
            need(set(row) <= {'id','bytes','error','rx_before','rx_end','refusal','status','channel','frame_seq'} and
                 all(type(v) is int and 0 <= v <= U32 for v in row.values()), 'BOUNDED_RESULT_ROW')
            need(('channel' not in row or row['channel'] == lane['channel']) and
                 ('frame_seq' not in row or row['frame_seq'] == lane['frame_seq']), 'RESULT_CHANNEL_SEQUENCE')
            need(row['error'] == 0 and row['id'] > 0 and (previous_id is None or row['id'] == previous_id + 1), 'RESULT_ID_ERROR')
            need(row.get('refusal', 0) == 0 and
                 ('status' not in row or row['status'] & 0x10 and not row['status'] & 4), 'RESULT_REFUSAL_STATUS')
            need(row['rx_end'] == row['rx_before'] + row['bytes'] and (previous_end is None or row['rx_before'] == previous_end), 'RESULT_RX_ASSOCIATION')
            previous_id, previous_end = row['id'], row['rx_end']
            need(len(wire) - offset >= 14, 'TRUNCATED_HEADER')
            magic, version, kind, length, view, seq, tick = struct.unpack_from('<2sBBBBHI', wire, offset)
            size = length + 14
            need(magic == b'\xa5\x5a' and version == 3 and kind == 0xe4, 'OUTER_TYPE')
            need(21 <= length <= 32 and offset + size <= len(wire) and size == row['bytes'], 'FRAME_RESULT_LENGTH')
            frame = wire[offset:offset+size]; offset += size
            need(view == lane['view'] and seq == lane['frame_seq'] and tick == lane['acquisition_tick_us'], 'OUTER_CORRELATION')
            need(struct.unpack_from('<H', frame, size-2)[0] == binascii.crc_hqx(frame[2:-2], 0xffff), 'CRC')
            payload = frame[12:-2]; need(payload[0] == 2, 'PAYLOAD_REVISION')
            decoded = codec.decode_payload(bytes([1]) + payload[1:], {'session': lane['session'], 'config_epoch': lane['view'], 'e': 0})
            need(decoded['channel'] == lane['channel'] and decoded['count'] == 1, 'CHANNEL_SINGLETON')
            point = decoded['points'][0]
            need(point['index'] == lane['index'] and point['tick_ms'] == lane['acquisition_tick_us'], 'INDEX_TIME_CORRELATION')
            need(point['source_tick_ms'] == lane['source_tick_us'] and point['value'] == lane['raw_sample_uint16'], 'SOURCE_VALUE_CORRELATION')
            need(all(point[k] == lane['mapped_flags'][k] for k in ('valid','saturated','held','source_fault')), 'QUALITY_CORRELATION')
            frames.append({'channel': lane['channel'], 'result_id': row['id'], 'frame_seq': seq,
                           'frame_sha256': digest(frame), 'frame_bytes': size, 'point': point,
                           'original_lane': copy.deepcopy(lane), 'crc_consistent': True})
        need(offset == len(wire), 'EXTRA_WIRE_BYTES')
        return dict(facts, status='FOUR_FRAME_CORRELATION_CONSISTENT', frames=frames,
                    result_rows=copy.deepcopy(result_rows),
                    companion_byte_identity='MATCH', semantic_association='OPAQUE_NOT_VERIFIED')
    except (Refused, codec.TraceError) as exc:
        return dict(facts, status='REFUSED_WITH_ORIGINAL_BYTES', reason=str(exc), frames=[])
