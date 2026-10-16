'''Reproducible generator for the candidate raw-vector and layout artifacts.

Task DEEPEYE-IMPLEMENTATION-20261014/v1; correction work
B-TRACE-CANONICAL-SOURCEAGE-CORRECTION-20261017-01-v1 over the original work
B-TRACE-OFFLINE-PAYLOAD-20261017-05-v1.  Contract
DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804; design
1011259415a0916054eb580687612580bc1e5f09.

Candidate-only: writes the B-side review artifacts trace_candidate_vectors.json
and trace_candidate_layout.json into an explicit --output-dir.  The eight
B-main hand-derived vectors are copied from the read-only main decision file
given with --manual (sha256 pinned and re-verified below); their expected bytes
are never derived from this implementation.  All synthetic points are software
fixtures with no relation to any hidden world layout or real source record.

Every path is explicit; this file never computes repository or private paths
from its own location and writes only inside --output-dir:
  <python> -B make_trace_vectors.py
      --golden <worktree>/competition/deepeye/golden/codec
      --manual <evidence>/main/main_manual_vectors.json
      --spec   <evidence>/main/main_candidate_spec.md
      --output-dir <fresh directory>
The generated trace_candidate_vectors.json / trace_candidate_layout.json are
then copied explicitly to golden/codec by the caller; the manual section keeps
its enriched byte_ledger/restored_points fields for the committed tests.
'''

import argparse
import binascii
import hashlib
import json
import struct
import sys
from pathlib import Path

PARSER = argparse.ArgumentParser(
    description='Generate the candidate trace vector and layout artifacts.')
PARSER.add_argument('--golden', required=True,
                    help='directory containing trace_candidate.py and codec_reference.py')
PARSER.add_argument('--manual', required=True,
                    help='read-only main_manual_vectors.json with the 8 hand-derived vectors')
PARSER.add_argument('--spec', required=True,
                    help='read-only main_candidate_spec.md')
PARSER.add_argument('--output-dir', required=True,
                    help='directory that receives trace_candidate_vectors.json and '
                         'trace_candidate_layout.json')
ARGS = PARSER.parse_args()
GOLDEN = Path(ARGS.golden).resolve()
MANUAL_PATH = Path(ARGS.manual).resolve()
SPEC_PATH = Path(ARGS.spec).resolve()
OUTPUT_DIR = Path(ARGS.output_dir).resolve()

sys.path.insert(0, str(GOLDEN))
import trace_candidate as tc  # noqa: E402
import codec_reference as inner  # noqa: E402

MAIN_VECTORS_SHA256 = '36b8e3fdb53e3c8fc911cc44b4f4151d62863d2e05b189f68c42fefe869b2d24'
SESSION = 0x01020304


def binding(e=0):
    return {'session': SESSION, 'config_epoch': 2, 'e': e}


def point(index, tick, value, held_origin=None, saturated=False, fault=False, invalid=False):
    if invalid:
        return {'index': index, 'tick_ms': tick, 'value': None, 'valid': False,
                'saturated': False, 'held': False, 'source_fault': fault,
                'source_tick_ms': None}
    source = held_origin if held_origin is not None else tick
    return {'index': index, 'tick_ms': tick, 'value': value, 'valid': True,
            'saturated': saturated, 'held': held_origin is not None,
            'source_fault': fault, 'source_tick_ms': source}


def case(case_id, group, bind, channel, start_sequence, points, notes):
    frames = tc.pack_channel(points, bind, channel, start_sequence)
    restored = []
    ledgers = []
    for frame in frames:
        record = tc.decode_frame(frame, bind)
        restored.extend(record['points'])
        ledgers.append(record['ledger'])
    aggregate = {
        'frame_count': len(frames),
        'payload_bytes_total': sum(entry['payload_bytes'] for entry in ledgers),
        'frame_bytes_total': sum(entry['frame_bytes'] for entry in ledgers),
        'line_bits_8n1_total': sum(entry['line_bits_8n1'] for entry in ledgers),
        'value_count_total': sum(entry['value_count'] for entry in ledgers),
        'selected_raw_bytes_total': sum(entry['selected_raw_bytes'] for entry in ledgers),
        'significant_bits_total': sum(entry['significant_bits'] for entry in ledgers),
        'stored_code_bytes_total': sum(entry['stored_code_bytes'] for entry in ledgers),
        'padding_bits_total': sum(entry['padding_bits'] for entry in ledgers),
        'metadata_bytes_total': sum(entry['metadata_bytes'] for entry in ledgers),
    }
    for frame in frames:
        assert len(frame) <= 46
    errors = [abs(restored_entry['value'] - source_entry['value'])
              for restored_entry, source_entry in zip(restored, points)
              if source_entry['valid'] and restored_entry['valid']]
    max_abs_error = max(errors) if len(errors) == len(points) else None
    return {
        'id': case_id,
        'group': group,
        'binding': dict(bind),
        'channel': channel,
        'start_sequence': start_sequence,
        'source_points': points,
        'frames_hex': [frame.hex() for frame in frames],
        'restored_points': restored,
        'ledger_per_frame': ledgers,
        'aggregate_ledger': aggregate,
        'max_abs_error': max_abs_error,
        'notes': notes,
    }


def expect_reject(callable_, needle, label):
    try:
        callable_()
    except tc.TraceError as error:
        text = str(error)
        assert needle in text, (label, needle, text)
        return text
    raise AssertionError('expected rejection not raised: ' + label)


def load_manual_entries():
    path = MANUAL_PATH
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == MAIN_VECTORS_SHA256, digest
    document = json.loads(raw.decode('utf-8'))
    entries = []
    for vector in document['vectors']:
        bind = vector['binding']
        points = vector['points']
        payload = tc.encode_payload(points, bind, vector['channel'])
        frame = tc.encode_frame(points, bind, vector['channel'], vector['sequence'])
        assert payload.hex() == vector['payload_hex'], vector['name']
        assert frame.hex() == vector['frame_hex'], vector['name']
        decoded = tc.decode_frame(bytes.fromhex(vector['frame_hex']), bind)
        assert decoded['points'] == vector['expected_points'], vector['name']
        ledger = decoded['ledger']
        assert ledger['payload_bytes'] == vector['payload_bytes'], vector['name']
        assert ledger['metadata_bytes'] == vector['metadata_bytes'], vector['name']
        assert ledger['stored_code_bytes'] == vector['code_bytes'], vector['name']
        assert ledger['significant_bits'] == vector['significant_bits'], vector['name']
        assert ledger['padding_bits'] == vector['padding_bits'], vector['name']
        assert ledger['frame_bytes'] == vector['frame_bytes'], vector['name']
        assert ledger['line_bits_8n1'] == vector['line_bits_8N1'], vector['name']
        entry = dict(vector)
        entry['byte_ledger'] = ledger
        entry['restored_points'] = decoded['points']
        entry['implementation_reproduction'] = {
            'payload_matches_main_bytes': True,
            'frame_matches_main_bytes': True,
        }
        entries.append(entry)
    return entries


def cases_all_e():
    cases = []
    for e in (0, 1, 2, 4, 8):
        points = [point(i * 3, 1000 + i * 10, 1000 + i * 3) for i in range(8)]
        note = ('E%d closed loop; E0 exact, E>0 lossy by design with max error '
                'at most E; synthetic software fixture.' % e)
        cases.append(case('all_e_e%d' % e, 'all_e', binding(e), 1, 100 + e,
                          points, note))
    return cases


def cases_boundary():
    cases = []
    flat40 = [point(i, i * 10, 100) for i in range(40)]
    entry = case('boundary_exact_32B_40_flat', 'boundary', binding(0), 0, 0,
                 flat40, 'Longest fresh flat block inside the 32 B payload budget.')
    assert len(entry['frames_hex']) == 1
    assert len(bytes.fromhex(entry['frames_hex'][0])) == 46
    cases.append(entry)
    entry = case('boundary_42_flat_splits', 'boundary', binding(0), 0, 0,
                 [point(i, i * 10, 100) for i in range(42)],
                 '42 flat points need 33 B in one block, so the packer splits 41+1.')
    assert [len(bytes.fromhex(f)) for f in entry['frames_hex']] == [46, 37]
    cases.append(entry)
    singletons = [
        point(0, 100, 5),
        point(1, 200, None, invalid=True),
        point(5, 300, 7, held_origin=250),
        point(9, 100000, 9, held_origin=0),
    ]
    entry = case('boundary_singleton_forms', 'boundary', binding(0), 0, 0,
                 singletons,
                 'Fresh/invalid/held-short/held-long singletons; 23/21/25/31 B payloads.')
    assert [len(bytes.fromhex(f)) for f in entry['frames_hex']] == [37, 35, 39, 45]
    cases.append(entry)
    entry = case('boundary_invalid_128_single', 'boundary', binding(0), 3, 0,
                 [point(i, i * 10, None, fault=True, invalid=True) for i in range(128)],
                 'Quality-only invalid block, 128 points, zero code bytes.')
    assert len(entry['frames_hex']) == 1
    assert entry['ledger_per_frame'][0]['payload_bytes'] == 25
    cases.append(entry)
    return cases


def cases_mask():
    cases = []
    entry = case('mask_saturated_valid', 'mask', binding(0), 0, 0,
                 [point(i, i * 10, 65535, saturated=True) for i in range(3)],
                 'Saturated reported status on valid points, all values endpoint here.')
    cases.append(entry)
    entry = case('mask_fault_valid', 'mask', binding(0), 0, 0,
                 [point(i, i * 10, 7, fault=True) for i in range(3)],
                 'source_fault may coexist with valid blocks.')
    cases.append(entry)
    entry = case('mask_fault_invalid', 'mask', binding(0), 0, 2,
                 [point(i, i * 10, None, fault=True, invalid=True) for i in range(3)],
                 'source_fault may coexist with quality-only invalid blocks.')
    cases.append(entry)
    entry = case('mask_saturated_held', 'mask', binding(0), 0, 0,
                 [point(i, 1000 + i * 10, 300, held_origin=990, saturated=True,
                        fault=True) for i in range(3)],
                 'Held valid block with saturated and fault reported status.')
    cases.append(entry)
    mixed = []
    for i in range(6):
        mixed.append(point(i, i * 10, 55, fault=(i % 2 == 1)))
    entry = case('mask_split_on_flag_change', 'mask', binding(0), 0, 0, mixed,
                 'Alternating source_fault forces one split per change.')
    assert len(entry['frames_hex']) == 6
    cases.append(entry)
    entry = case('mask_saturated_not_endpoint', 'mask', binding(0), 0, 0,
                 [point(i, i * 10, value, saturated=True)
                  for i, value in enumerate([1234, 65535, 42])],
                 'Saturation is reported status only; non-endpoint values stay exact.')
    cases.append(entry)
    return cases


def cases_age_forms():
    cases = []
    held_same_origin = [point(i, 1000 + i * 10, 100, held_origin=950)
                        for i in range(3)]
    entry = case('age_held_short_multipoint', 'age_forms', binding(0), 0, 0,
                 held_same_origin,
                 'Held block, one constant source origin, short two-byte age 50.')
    assert len(entry['frames_hex']) == 1
    cases.append(entry)
    forms = [
        point(1, 10, 5),
        point(2, 1000, 6, held_origin=999),
        point(3, 70000, 7, held_origin=4465),
        point(4, 140000, 8, held_origin=74464),
        point(5, 200000, 9, held_origin=0),
    ]
    entry = case('age_forms_five_frames', 'age_forms', binding(0), 0, 0, forms,
                 'Ages 1/65535 use the short form, 65536/200000 the long form; '
                 'a fresh point stays extension-free.')
    assert len(entry['frames_hex']) == 5
    restored = entry['restored_points']
    assert [r['source_tick_ms'] for r in restored] == [10, 999, 4465, 74464, 0]
    cases.append(entry)
    old_origin = [point(7, 100000, 1234, held_origin=0)]
    entry = case('age_long_singleton_from_main_pattern', 'age_forms', binding(0),
                 0, 9, old_origin,
                 'Held long singleton mirroring the main pattern: 31 B payload, 45 B frame.')
    assert len(bytes.fromhex(entry['frames_hex'][0])) == 45
    cases.append(entry)
    return cases


def cases_tick_forms():
    cases = []
    rollover = [point(i + 1, 4294967290 + i * 10, 1) for i in range(4)]
    cases.append(case(
        'tick_low32_rollover_synthetic', 'tick_forms', binding(0), 0, 0, rollover,
        'Synthetic future-layout low32 rollover crossing; not an accepted '
        'current-source record (A reports ADC ticks at most 2**31-1, multiples of 10).'))
    high = [point(100 + i, (1 << 64) - 1001 + i * 10, 2) for i in range(10)]
    cases.append(case(
        'tick_uint64_high_synthetic', 'tick_forms', binding(0), 0, 0, high,
        'Synthetic future-layout uint64 ticks near the top of the range.'))
    near_index = [point((1 << 32) - 501 + i * 3, 1000 + i * 10, 3) for i in range(10)]
    cases.append(case(
        'index_uint32_high_synthetic', 'tick_forms', binding(0), 0, 0, near_index,
        'Synthetic indices near the top of uint32 with a small uniform stride.'))
    return cases


def cases_tie():
    cases = []
    pair = [point(0, 0, 0), point(1, 10, 64)]
    entry = case('tie_raw_wins_stored_bytes', 'tie', binding(0), 0, 0, pair,
                 'Stored-byte tie: candidate RAW (4 code bytes) wins; the inner '
                 'bit-count rule keeps rice k=6 with 25 significant bits, an '
                 'explicit documented difference.')
    entry['inner_codec_fixture'] = inner.encode_block([0, 64], 0)
    cases.append(entry)
    triple = [point(0, 0, 0), point(1, 10, 2048), point(2, 20, 4096)]
    entry = case('tie_raw_wins_triple', 'tie', binding(0), 0, 0, triple,
                 'Six-byte stored tie (best rice 44 bits in 6 bytes equals RAW '
                 '6 bytes); both the candidate byte rule and the inner bit rule '
                 'select RAW here.')
    entry['inner_codec_fixture'] = inner.encode_block([0, 2048, 4096], 0)
    cases.append(entry)
    return cases


TC01_MAIN_EXPECTED_FRAME = bytes.fromhex(
    'a55a03071d00000000000000011004041a0100000000000000000000000000000001000a0010274880a94b')


def cases_canonical_k():
    cases = []
    values = [10000, 10001, 10002, 10004]
    tc01_points = [point(i, i * 10, x) for i, x in enumerate(values)]
    entry = case('canonical_k_tc01_manual_expected', 'canonical_k',
                 {'session': 1, 'config_epoch': 0, 'e': 0}, 0, 0, tc01_points,
                 'TC01: ZigZag [2,2,4]; k0 costs 27 significant bits while k1/k2 '
                 'cost 26, so the minimum-significant-bit rule selects k1 and Rice '
                 '(4 stored bytes) beats RAW (8). Expected frame bytes copied '
                 'verbatim from the main portable regression check.')
    assert entry['frames_hex'][0] == TC01_MAIN_EXPECTED_FRAME.hex()
    assert entry['ledger_per_frame'][0]['significant_bits'] == 26
    assert entry['ledger_per_frame'][0]['stored_code_bytes'] == 4
    cases.append(entry)
    family = [0, 8, 16]
    family_points = [point(i, i * 10, x) for i, x in enumerate(family)]
    entry = case('canonical_k_padded_tie_family', 'canonical_k', binding(0),
                 0, 1, family_points,
                 'Family case: k2 (30 significant bits) and k3 (28) share 4 '
                 'padded code bytes, so the minimum-significant-bit rule must '
                 'choose k3; the rejected byte-minimizing rule chose k2.')
    assert entry['ledger_per_frame'][0]['significant_bits'] == 28
    assert entry['ledger_per_frame'][0]['stored_code_bytes'] == 4
    cases.append(entry)
    return cases


def cases_channels():
    cases = []
    channel0 = [point(1000 + i * 2, 1000 + i * 10, 200 + (i * 7) % 23)
                for i in range(128)]
    entry = case('channels4_ch0_128_fresh', 'channels_4x128', binding(0), 0, 0,
                 channel0,
                 'Channel 0: 128 fresh selected points, uniform index/tick strides.')
    assert entry['restored_points'] == channel0
    cases.append(entry)
    channel1 = [point(5000 + i * 2, 5000 + i * 10, 300 + (i * 5) % 17,
                      fault=(40 <= i < 80)) for i in range(128)]
    entry = case('channels4_ch1_128_fault_span', 'channels_4x128', binding(0), 1, 0,
                 channel1,
                 'Channel 1: 128 selected points with a source_fault span at 40..79.')
    assert entry['restored_points'] == channel1
    cases.append(entry)
    return cases


def cases_channels_part2():
    cases = []
    channel2 = []
    for i in range(128):
        tick = 90000 + i * 10
        index = 7000 + i * 2
        if i < 32:
            channel2.append(point(index, tick, 400, held_origin=89950))
        elif i < 64:
            channel2.append(point(index, tick, 400))
        elif i < 96:
            channel2.append(point(index, tick, 400, held_origin=90560))
        else:
            channel2.append(point(index, tick, 400))
    entry = case('channels4_ch2_128_held_spans', 'channels_4x128', binding(0), 2, 0,
                 channel2,
                 'Channel 2: 128 selected points with two held spans that use '
                 'different source origins.')
    assert entry['restored_points'] == channel2
    cases.append(entry)
    channel3 = []
    index = 20000
    tick = 200000
    for i in range(128):
        if i:
            if i < 50:
                index += 1
            elif i == 50:
                index += 1000
            elif i < 90:
                index += 1
            else:
                index += 7
            tick += 10
        channel3.append(point(index, tick, 500 + i % 3))
    entry = case('channels4_ch3_128_stride_segments', 'channels_4x128', binding(0),
                 3, 0, channel3,
                 'Channel 3: 128 selected points with two stride changes that '
                 'force fresh block starts.')
    assert entry['restored_points'] == channel3
    cases.append(entry)
    return cases


def mixed_pattern():
    points = []
    index = 0
    tick = 0
    for i in range(30):
        index += (1, 1, 2, 5, 300)[i % 5]
        tick += (10, 10, 25, 70000)[i % 4]
        selector = i % 6
        if selector == 0:
            points.append(point(index, tick, (i * 7) % 100))
        elif selector == 1:
            points.append(point(index, tick, (i * 11) % 100, saturated=True))
        elif selector == 2:
            points.append(point(index, tick, None, invalid=True))
        elif selector == 3:
            points.append(point(index, tick, (i * 13) % 100, fault=True))
        elif selector == 4:
            origin = tick - (3 if i % 2 else 60000)
            if 0 < origin < tick:
                points.append(point(index, tick, (i * 3) % 50, held_origin=origin))
            else:
                points.append(point(index, tick, (i * 3) % 50))
        else:
            points.append(point(index, tick, 55))
    return points


def cases_sparse():
    cases = []
    fallback = [point(0, 0, 1), point(1, 10, 2), point(5, 30, 3), point(9, 50, 4)]
    entry = case('sparse_pair_then_singletons', 'sparse_pack', binding(0), 0, 0,
                 fallback,
                 'Deltas 1/4/4: the first pair packs; the stride change forces a '
                 'fresh start, so two independently decodable frames result.')
    assert [len(bytes.fromhex(f)) for f in entry['frames_hex']] == [42, 42]
    assert entry['restored_points'] == fallback
    cases.append(entry)
    flat128 = [point(i, i * 10, 100) for i in range(128)]
    entry = case('sparse_flat_128_budget_split', 'sparse_pack', binding(0), 0, 0,
                 flat128,
                 '128 flat points split by the 32 B budget into four frames '
                 '41+41+41+5.')
    assert [len(bytes.fromhex(f)) for f in entry['frames_hex']] == [46, 46, 46, 42]
    assert entry['restored_points'] == flat128
    cases.append(entry)
    mixed = mixed_pattern()
    entry = case('sparse_quality_mix_30', 'sparse_pack', binding(0), 2, 0, mixed,
                 'Deterministic mix of fresh, saturated, invalid, fault and held '
                 'points at irregular spacing; greedy splits at flag, origin and '
                 'stride limits.')
    assert entry['restored_points'] == mixed
    cases.append(entry)
    return cases


def greedy_verification_entry():
    points = mixed_pattern()
    bind = binding(0)
    frames = tc.pack_channel(points, bind, 2, 0)
    position = 0
    verified = 0
    for frame in frames:
        record = tc.decode_frame(frame, bind)
        longest = 1
        for length in range(2, len(points) - position + 1):
            try:
                tc.encode_payload(points[position:position + length], bind, 2)
                longest = length
            except tc.TraceError:
                pass
        assert record['count'] == longest, (position, record['count'], longest)
        position += record['count']
        verified += 1
    return {
        'id': 'greedy_equals_brute_force_longest_prefix',
        'group': 'packer_verification',
        'binding': dict(bind),
        'channel': 2,
        'start_sequence': 0,
        'source_points': points,
        'frames_hex': [frame.hex() for frame in frames],
        'frame_count': len(frames),
        'verified_block_starts': verified,
        'notes': 'Exhaustive comparison of the greedy block lengths with a '
                 'brute-force longest-prefix search using only the public '
                 'encode_payload API, so the ascending search may stop at the '
                 'first failing length.',
    }


def capacity_entry():
    points = []
    index = 0
    tick = 0
    for i in range(60):
        index += i + 1
        tick += i * 10 + 10
        points.append(point(index, tick, 7))
    bind = binding(0)
    message = expect_reject(lambda: tc.pack_channel(points, bind, 0, 65530),
                            'no partial output', 'sequence capacity')
    frames = tc.pack_channel(points, bind, 0, 0)
    return {
        'id': 'sequence_capacity_rejection',
        'group': 'packer_verification',
        'binding': dict(bind),
        'channel': 0,
        'start_sequence': 65530,
        'source_points': points,
        'expect_error_contains': 'no partial output',
        'actual_error': message,
        'frame_count_at_zero': len(frames),
        'notes': 'Sixty points with strictly growing deltas force 30 frames; the '
                 'requested uint16 capacity 65530..65535 holds only six, so the '
                 'whole call is rejected instead of emitting a partial list.',
    }


def malformed_entries():
    bind = binding(0)
    single = tc.encode_payload([point(7, 1000, 1234)], bind, 0)
    big = tc.encode_payload([point(i, 10 * i, 100) for i in range(41)], bind, 0)
    three = tc.encode_payload([point(10 + i, 1000 + 10 * i, 100) for i in range(3)],
                              bind, 1)
    held_short = tc.encode_payload([point(7, 1000, 5, held_origin=900)], bind, 0)
    held_long = tc.encode_payload([point(7, 70000, 5, held_origin=0)], bind, 0)
    invalid = tc.encode_payload([point(7, 1000, None, invalid=True)], bind, 3)
    prefix = three[:21]
    entries = []

    def add(entry_id, payload_bytes, needle):
        entries.append({'id': entry_id, 'payload_hex': payload_bytes.hex(),
                        'binding': dict(bind), 'expect_error_contains': needle})

    add('m01_payload_over_32B', big + b'\x00',
        'exceeds the 32 B candidate budget')
    add('m02_trailing_byte', single + b'\x00', 'length does not match')
    codec_swap = bytearray(three)
    codec_swap[1] = 0x10
    codec_swap[4] = 20
    codec_swap[-1] = 0xA0
    add('m03_noncanonical_k1_same_bytes', bytes(codec_swap), 'noncanonical')
    raw_claim = bytearray(prefix + bytes.fromhex('01000a00640064006400'))
    raw_claim[1] = 0x08
    raw_claim[4] = 48
    add('m04_raw_when_rice_strictly_better', bytes(raw_claim), 'noncanonical mode')
    pad = bytearray(three)
    pad[-1] |= 1
    add('m05_nonzero_padding', bytes(pad), 'padding bit')
    reserved = bytearray(single)
    reserved[2] |= 0x80
    add('m06_reserved_quality_bit', bytes(reserved), 'bit7')
    mismatch = bytearray(single)
    mismatch[1] = (mismatch[1] & 0xF8) | 1
    add('m07_e_mismatch', bytes(mismatch), 'binding.e')
    stride0 = bytearray(three)
    stride0[21:23] = b'\x00\x00'
    add('m08_zero_index_stride', bytes(stride0), 'index stride must be positive')
    overflow = bytearray(three)
    overflow[9:13] = struct.pack('<I', 0xFFFFFFFF)
    add('m09_index_overflow', bytes(overflow), 'overflows uint32')
    overflow = bytearray(three)
    overflow[13:21] = struct.pack('<Q', 0xFFFFFFFFFFFFFFF5)
    add('m10_tick_overflow', bytes(overflow), 'overflows uint64')
    bad_long = bytearray(held_long)
    bad_long[21:29] = struct.pack('<Q', 69900)
    add('m11_long_form_for_short_age', bytes(bad_long), 'not canonical')
    zero_age = bytearray(held_short)
    zero_age[21:23] = b'\x00\x00'
    add('m12_zero_short_age', bytes(zero_age), 'positive age')
    held_invalid = bytearray(invalid)
    held_invalid[2] |= 0x10
    held_invalid += b'\x01\x00'
    add('m13_invalid_with_held', bytes(held_invalid), 'cannot be held')
    count0 = bytearray(invalid)
    count0[3] = 0
    add('m14_count_zero', bytes(count0), 'point count 0')
    count129 = bytearray(invalid)
    count129[3] = 129
    add('m15_count_129', bytes(count129), 'point count 129')
    ecode = bytearray(single)
    ecode[1] = (ecode[1] & 0xF8) | 5
    add('m16_undefined_e_code', bytes(ecode), 'not defined')
    session = bytearray(single)
    session[5] ^= 1
    add('m17_session_mismatch', bytes(session), 'binding.session')
    raw_k = bytearray(single)
    raw_k[1] |= 0x10
    add('m18_raw_with_k', bytes(raw_k), 'require k=0')
    invalid_raw = bytearray(invalid)
    invalid_raw[1] &= ~8
    add('m19_invalid_without_raw', bytes(invalid_raw), 'RAW flag')
    truncated = bytearray(prefix + bytes.fromhex('01000a00640000'))
    truncated[4] = 18
    add('m20_truncated_unary', bytes(truncated), 'truncated')
    overlong = bytearray(prefix + bytes.fromhex('01000a0064000000000080'))
    overlong[3] = 2
    overlong[4] = 49
    add('m21_overlong_unary', bytes(overlong), 'overlong')
    add('m22_payload_shorter_than_prefix', b'', 'shorter than the 21 B prefix')
    underflow_age = bytearray(held_short)
    underflow_age[21:23] = struct.pack('<H', 1001)
    add('m23_short_age_exceeds_payload_tick', bytes(underflow_age),
        'exceeds the first tick')
    for entry in entries:
        expect_reject(
            lambda payload=entry['payload_hex']: tc.decode_payload(
                bytes.fromhex(payload), bind),
            entry['expect_error_contains'], entry['id'])
    return entries


def malformed_frames(manual):
    bind = manual[0]['binding']
    base = bytes.fromhex(manual[0]['frame_hex'])
    entries = []

    def add(entry_id, frame_bytes, needle):
        entries.append({'id': entry_id, 'frame_hex': frame_bytes.hex(),
                        'binding': dict(bind), 'expect_error_contains': needle})

    add('f01_bad_crc', base[:-1] + bytes([base[-1] ^ 1]), 'CRC mismatch')
    declared = bytearray(base)
    declared[4] += 1
    add('f02_declared_length_mismatch', bytes(declared), 'declared payload')
    add('f03_bad_magic', b'\x00\x00' + base[2:], 'magic')
    add('f04_bad_version', base[:2] + b'\x04' + base[3:], 'version')
    add('f05_bad_type', base[:3] + b'\x08' + base[4:], 'outer type')
    tick_low = bytearray(base)
    tick_low[8:12] = struct.pack('<I', 999)
    crc = binascii.crc_hqx(bytes(tick_low[2:-2]), 0xFFFF)
    tick_low[-2:] = struct.pack('<H', crc)
    add('f06_tick_low_mismatch', bytes(tick_low), 'low32')
    epoch = bytearray(base)
    epoch[5] = 3
    crc = binascii.crc_hqx(bytes(epoch[2:-2]), 0xFFFF)
    epoch[-2:] = struct.pack('<H', crc)
    add('f07_epoch_mismatch', bytes(epoch), 'config_epoch')
    add('f08_frame_over_46B', base + b'\x00' * 12, 'frame budget')
    add('f09_frame_below_minimum', base[:30], 'shorter than the smallest')
    underflow = bytes.fromhex(
        'a55a030719020900e803000001081401100403020107000000e803000000000000'
        'e9036400a811')
    add('f10_short_age_exceeds_tick_main', underflow, 'exceeds the first tick')
    held_base = tc.encode_frame([point(7, 1000, 5, held_origin=900)], bind, 0, 9)
    tick_zero = bytearray(held_base)
    tick_zero[25:33] = (0).to_bytes(8, 'little')
    tick_zero[33:35] = (1).to_bytes(2, 'little')
    tick_zero[8:12] = (0).to_bytes(4, 'little')
    tick_zero[-2:] = struct.pack('<H', binascii.crc_hqx(bytes(tick_zero[2:-2]),
                                                        0xFFFF))
    add('f11_short_age_one_over_tick_zero', bytes(tick_zero),
        'exceeds the first tick')
    for entry in entries:
        expect_reject(
            lambda frame=entry['frame_hex']: tc.decode_frame(
                bytes.fromhex(frame), bind),
            entry['expect_error_contains'], entry['id'])
    return entries


CONTRACT = {
    'contract': 'DEEPEYE-HUMAN-LOCK-20261014',
    'revision': 1,
    'contract_commit': 'f5989cd5defce561f9ba98e6b18fc2682945f0a2',
    'requirements_ids': ['H%02d' % number for number in range(1, 16)],
    'requirements_sha256':
        'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804',
}

LEDGER_DEFINITION = {
    'count': 'decoded point count of the block',
    'value_count': 'points with valid true (0 for quality-only blocks)',
    'selected_raw_bytes': '2 * value_count, the RAW body byte count the stored-byte '
                          'selection compared against',
    'significant_bits': 'code-section bits from the payload field, anchor included',
    'stored_code_bytes': 'actual code-section byte length, ceil(significant_bits / 8)',
    'padding_bits': '8 * stored_code_bytes - significant_bits, all zero',
    'metadata_bytes': '21 prefix + 4 strides + 0/2/8 held extension',
    'payload_bytes': 'metadata_bytes + stored_code_bytes',
    'outer_overhead_bytes': '12 header + 2 CRC = 14',
    'frame_bytes': 'payload_bytes + 14, at most 46',
    'line_bits_8n1': '10 * frame_bytes, one start bit and one stop bit per byte',
}


def layout_document():
    return {
        'schema': 1,
        'work_id': 'B-TRACE-OFFLINE-PAYLOAD-20261017-05-v1',
        'task': {'task_id': 'DEEPEYE-IMPLEMENTATION-20261014', 'task_version': 1},
        'contract': dict(CONTRACT),
        'design_commit': '1011259415a0916054eb580687612580bc1e5f09',
        'base_commit': 'c5d079c24e45d97d6bd8181a7414a64c7c110860',
        'main_spec_sha256':
            '7bc33ebc28c9f08e200c539a1a59c07b42b36211cb49b08ac449875bf75f9a73',
        'status': 'candidate_only_not_public_abi; A owns the public schema, the '
                  'only production type7 enable decision and the physical board',
        'proposal_revision': 1,
        'outer_frame': {
            'struct_format': '<2sBBBBHI',
            'header_bytes': 12,
            'crc_bytes': 2,
            'overhead_bytes': 14,
            'payload_max_bytes': 32,
            'frame_max_bytes': 46,
            'fields': [
                {'name': 'magic', 'offset': 0, 'bytes': 2, 'value': 'A5 5A'},
                {'name': 'version', 'offset': 2, 'bytes': 1, 'value': 3},
                {'name': 'type', 'offset': 3, 'bytes': 1, 'value': 7,
                 'notes': 'candidate fixtures only; the existing A wire.py must '
                          'keep rejecting type7'},
                {'name': 'payload_len', 'offset': 4, 'bytes': 1, 'range': '21..32'},
                {'name': 'config_epoch', 'offset': 5, 'bytes': 1,
                 'notes': 'must equal binding.config_epoch'},
                {'name': 'sequence', 'offset': 6, 'bytes': 2,
                 'encoding': 'little-endian uint16',
                 'notes': 'frame sequence, not an acquisition index; must increase '
                          'without wrap inside one binding'},
                {'name': 'tick_ms', 'offset': 8, 'bytes': 4,
                 'encoding': 'little-endian uint32',
                 'notes': 'low 32 bits of the FIRST acquisition tick in this '
                          'candidate payload'},
            ],
            'crc': {
                'algorithm': 'CRC-16/CCITT-FALSE',
                'poly': '0x1021', 'init': '0xFFFF', 'refin': False, 'refout': False,
                'xorout': 0,
                'coverage': 'version byte through the last payload byte',
                'storage': 'little-endian uint16 after the payload',
            },
        },
        'payload': {
            'prefix_bytes': 21,
            'fields': [
                {'name': 'revision', 'offset': 0, 'bytes': 1, 'value': 1,
                 'notes': 'candidate revision, distinct from the outer ABI version'},
                {'name': 'settings', 'offset': 1, 'bytes': 1,
                 'bits': {'0..2': 'E code 0 maps to 0, 1 to 1, 2 to 2, 3 to 4, '
                                  '4 to 8; 5..7 invalid',
                          '3': 'RAW flag, RAW requires k bits 0',
                          '4..7': 'Rice k 0..15'}},
                {'name': 'quality', 'offset': 2, 'bytes': 1,
                 'bits': {'0..1': 'channel 0..3', '2': 'valid', '3': 'saturated',
                          '4': 'held', '5': 'source_fault',
                          '6': 'long_source_tick', '7': 'reserved, must be 0'},
                 'notes': 'the four quality flags are common to every point of the '
                          'block; the per-point mask is recovered by expansion'},
                {'name': 'point_count', 'offset': 3, 'bytes': 1, 'range': '1..128'},
                {'name': 'significant_bits', 'offset': 4, 'bytes': 1,
                 'notes': 'includes the 16 anchor bits for any valid block; 0 for '
                          'quality-only invalid blocks'},
                {'name': 'session', 'offset': 5, 'bytes': 4,
                 'encoding': 'little-endian uint32',
                 'notes': 'must equal binding.session'},
                {'name': 'first_index', 'offset': 9, 'bytes': 4,
                 'encoding': 'little-endian uint32',
                 'notes': 'first ACTUAL acquisition index of the block'},
                {'name': 'first_tick_ms', 'offset': 13, 'bytes': 8,
                 'encoding': 'little-endian uint64',
                 'notes': 'first actual acquisition tick of the block'},
            ],
            'optional_strides': {
                'offset': 21,
                'bytes': 4,
                'present_when': 'point_count > 1',
                'fields': ['index_stride uint16 little-endian 1..65535',
                           'tick_stride_ms uint16 little-endian 1..65535'],
                'notes': 'every point sits at first + i * stride; uint32 index and '
                         'uint64 tick progression must not overflow',
            },
            'held_source_extension': {
                'offset': '21 + strides',
                'present_when': 'quality held bit is set',
                'short_form': {'bytes': 2, 'encoding': 'uint16 little-endian age',
                               'range': '1..65535', 'long_bit': 0,
                               'bound': 'age <= first_tick (the uint64 origin '
                                        'would underflow otherwise)'},
                'long_form': {'bytes': 8,
                              'encoding': 'uint64 little-endian absolute source tick',
                              'long_bit': 1,
                              'requires': 'source_tick < first_tick and '
                                          'first_tick - source_tick > 65535'},
                'notes': 'the source update origin is constant for the whole held '
                         'block; later point ages follow from their ticks',
            },
            'code_section': {
                'offset': '21 + strides + extension',
                'length': 'ceil(significant_bits / 8) bytes, 0 when invalid',
                'anchor': 'first sample, little-endian uint16',
                'raw_body': 'each later sample little-endian uint16',
                'rice_body': 'MSB-first bitstream after the anchor: quotient zero '
                             'bits then a one terminator, then k remainder bits',
                'padding': 'unused low bits of the final byte are zero',
            },
        },
        'canonicality': {
            'mode_selection': 'two-stage: stage 1 picks the Rice k with the fewest '
                              'significant bits, stage 2 keeps Rice only when its '
                              'padded code-byte count is strictly smaller than RAW '
                              '2*value_count bytes; a stored-byte tie selects RAW',
            'k_selection': 'fewest significant bits over legal k 0..15 with every '
                           'quotient at most 31; ties choose the lowest k - exactly '
                           'the unchanged inner codec k rule',
            'invalid_shape': 'quality-only invalid blocks carry zero significant '
                             'bits, no code bytes, RAW with k=0 and no anchor',
            'held_forms': 'short age 1..65535, long absolute source tick only when '
                          'the age exceeds 65535',
            'decode_checks': 'version, type, magic, exact length, CRC, config_epoch, '
                             'session, E versus binding, reserved bit, strides, '
                             'overflow, source forms, and a canonical re-encoding '
                             'byte comparison of the decoded values',
        },
        'recovery': {
            'packing': 'greedy longest legal prefix; split at quality change, held '
                       'origin change, stride change, gap, overflow or the 32 B '
                       'budget; every input point can become a singleton',
            'sequence_capacity': 'no partial output is returned when the uint16 '
                                 'sequence range cannot hold every frame; sequence '
                                 'never wraps',
            'receiver': 'at most 16 packets cached by sequence; exact duplicates '
                        'return status duplicate with zero points; the same sequence '
                        'with different bytes conflicts; a sequence no longer in the '
                        'cache is rejected; sequence gaps are accepted without '
                        'synthesizing points; per-channel first index and tick must '
                        'both exceed that channel high water; failures never '
                        'partially advance state',
        },
        'differences_from_inner_codec': {
            'body_order': 'candidate anchor and RAW words are little-endian; the '
                          'inner fixture uses MSB-first bit words',
            'mode_rule': 'both choose Rice k by fewest significant bits (ties '
                         'lowest k); the inner codec keeps Rice on a bit tie below '
                         'RAW bits while the candidate then compares STORED BYTES '
                         'of the whole code section and prefers RAW on a byte tie',
            'example': '[0, 64] at E0: inner fixture rice k=6, 25 significant bits, '
                       '4 stored bytes; candidate RAW, 32 significant bits, 4 stored '
                       'bytes',
        },
        'ledger_definition': dict(LEDGER_DEFINITION),
        'limitations': [
            'Candidate only; not a public ABI freeze and not implemented in any A/C '
            'file; A wire.py keeps rejecting type7.',
            'Extra metadata can expand traffic; no compression, throughput, latency '
            'or continuous-sampling claim is made.',
            'Indices are actual per-channel acquisition indices, never frame '
            'sequence numbers; equal indices across channels do not prove common '
            'sampling time.',
            'No source authentication, calibration, runtime clock acquisition, '
            'observation lease, motion authorization or AI feed is provided; the '
            'receiver cannot attest handshake, session uniqueness or trust.',
            'Saturation is reported status only and never implies endpoint values.',
            'The uint64 tick and low32 rollover vectors are synthetic future-layout '
            'proposals; A reports current ADC ticks at most 2**31-1, multiples of '
            '10, and EM tick values that are multiples of 50 ms.',
            'C must independently decode the approved candidate and adapt source, '
            'profile and physical units after A approval.',
        ],
        'a_approval_gates': [
            'candidate field packing and revision byte',
            'header tick rule: low 32 bits of the first acquisition tick',
            'per-channel acquisition index meaning and C four-channel grouping',
            '64-bit clock origin and its proof',
            'quality-only frames and uniform-mask splitting',
            'held source origin and short/long form canonicality',
            'stage-two stored-byte RAW tie policy and little-endian body adaptation',
            'binding and sequence retirement rules',
            'full BOOT digest and the actual TRACE scheduling and sliding-window '
            'budget',
        ],
    }


def main():
    spec_digest = hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest()
    assert spec_digest == '7bc33ebc28c9f08e200c539a1a59c07b42b36211cb49b08ac449875bf75f9a73', spec_digest
    manual = load_manual_entries()
    synthetic = []
    synthetic.extend(cases_all_e())
    synthetic.extend(cases_boundary())
    synthetic.extend(cases_mask())
    synthetic.extend(cases_age_forms())
    synthetic.extend(cases_tick_forms())
    synthetic.extend(cases_tie())
    synthetic.extend(cases_canonical_k())
    synthetic.extend(cases_channels())
    synthetic.extend(cases_channels_part2())
    synthetic.extend(cases_sparse())
    verification = [greedy_verification_entry(), capacity_entry()]
    malformed = malformed_entries()
    frames_bad = malformed_frames(manual)
    document = {
        'schema': 1,
        'work_id': 'B-TRACE-OFFLINE-PAYLOAD-20261017-05-v1',
        'task': {'task_id': 'DEEPEYE-IMPLEMENTATION-20261014', 'task_version': 1},
        'contract': dict(CONTRACT),
        'design_commit': '1011259415a0916054eb580687612580bc1e5f09',
        'base_commit': 'c5d079c24e45d97d6bd8181a7414a64c7c110860',
        'status': 'candidate_only; offline B proposal; not a public ABI freeze',
        'correction_note': 'B-TRACE-CANONICAL-SOURCEAGE-CORRECTION-20261017-01-v1: '
                           'TC01 two-stage Rice k selection (minimum significant '
                           'bits first, then stored-byte Rice/RAW with RAW winning '
                           'byte ties) and TC02 short held source-age bound '
                           '1..first_tick. The 8 main manual vectors and their '
                           'expected bytes are unchanged; every synthetic vector '
                           'was regenerated by this generator.',
        'source_note': 'All source samples are synthetic software fixtures; no hidden '
                       'world layout or real source record is represented. The uint64 '
                       'tick and low32 rollover vectors are synthetic future-layout '
                       'proposals, not accepted current-source records (A reports ADC '
                       'ticks at most 2**31-1, multiples of 10, and EM tick values '
                       'that are multiples of 50 ms).',
        'manual_vectors': {
            'note': 'Eight vectors hand-derived by the B main independently of this '
                    'implementation; bytes copied verbatim and preserved. The '
                    'implementation was required to reproduce them without being '
                    'their derivation source.',
            'source_path': 'main_manual_vectors.json supplied explicitly with '
                           '--manual (sha256 verified against the pinned value)',
            'source_sha256': MAIN_VECTORS_SHA256,
            'vectors': manual,
        },
        'synthetic_vectors': synthetic,
        'packer_verification': verification,
        'malformed_payloads': malformed,
        'malformed_frames': frames_bad,
        'ledger_definition': dict(LEDGER_DEFINITION),
    }
    # A fresh directory is required so reruns cannot overwrite prior evidence.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    vectors_path = OUTPUT_DIR / 'trace_candidate_vectors.json'
    layout_path = OUTPUT_DIR / 'trace_candidate_layout.json'
    vectors_path.write_text(json.dumps(document, indent=1) + '\n',
                            encoding='utf-8', newline='\n')
    layout_path.write_text(json.dumps(layout_document(), indent=1) + '\n',
                           encoding='utf-8', newline='\n')
    summary = {
        'manual_vectors': len(manual),
        'synthetic_vectors': len(synthetic),
        'synthetic_groups': sorted(set(entry['group'] for entry in synthetic)),
        'packer_verification_entries': len(verification),
        'malformed_payloads': len(malformed),
        'malformed_frames': len(frames_bad),
        'vectors_json_bytes': vectors_path.stat().st_size,
        'layout_json_bytes': layout_path.stat().st_size,
        'vectors_json_sha256':
            hashlib.sha256(vectors_path.read_bytes()).hexdigest(),
        'layout_json_sha256':
            hashlib.sha256(layout_path.read_bytes()).hexdigest(),
    }
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
