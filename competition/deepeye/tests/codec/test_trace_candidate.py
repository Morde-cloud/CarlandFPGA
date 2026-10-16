'''Unit tests for the offline TRACE candidate revision 1 (candidate only).

Task DEEPEYE-IMPLEMENTATION-20261014/v1; work
B-TRACE-OFFLINE-PAYLOAD-20261017-05-v1, implementing the B main decision spec
sha256 7bc33ebc28c9f08e200c539a1a59c07b42b36211cb49b08ac449875bf75f9a73 on
base commit c5d079c24e45d97d6bd8181a7414a64c7c110860.

Contract DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804; design
1011259415a0916054eb580687612580bc1e5f09.

These are design-time software checks for the B-side candidate serializer.
They define no production transport and make no compression, latency, board
or system acceptance claim.  The golden byte vectors in
golden/codec/trace_candidate_vectors.json include eight vectors hand-derived
by the B main; this file never derives those expected bytes from the
implementation under test, it only checks agreement with the committed file.

Run from the worktree root:
  python -B -m unittest discover -s competition/deepeye/tests/codec -v
'''

import binascii
import enum
import hashlib
import json
import pathlib
import struct
import sys
import unittest

_HERE = pathlib.Path(__file__).resolve()
_DEEPEYE = _HERE.parents[2]
sys.path.insert(0, str(_DEEPEYE / 'golden' / 'codec'))

import codec_reference as inner  # noqa: E402
import trace_candidate as trace  # noqa: E402

VECTORS_PATH = _DEEPEYE / 'golden' / 'codec' / 'trace_candidate_vectors.json'
CODEC_PATH = _DEEPEYE / 'golden' / 'codec' / 'codec_reference.py'
INNER_VECTORS_PATH = _DEEPEYE / 'golden' / 'codec' / 'known_vectors.json'
CODEC_SHA256 = '2e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5'
INNER_VECTORS_SHA256 = 'c1eee67b73b8cdd449ac72b2a77c78f714eaf448b1216b16296488881ac10e99'

BINDING = {'session': 0x01020304, 'config_epoch': 2, 'e': 0}


def load_vectors():
    return json.loads(VECTORS_PATH.read_text(encoding='utf-8'))


def make_point(index, tick, value, held_origin=None, saturated=False,
               fault=False, invalid=False):
    if invalid:
        return {'index': index, 'tick_ms': tick, 'value': None, 'valid': False,
                'saturated': False, 'held': False, 'source_fault': fault,
                'source_tick_ms': None}
    source = held_origin if held_origin is not None else tick
    return {'index': index, 'tick_ms': tick, 'value': value, 'valid': True,
            'saturated': saturated, 'held': held_origin is not None,
            'source_fault': fault, 'source_tick_ms': source}


def flat_points(count, value=100, index_step=1, tick_step=10):
    return [make_point(i * index_step, i * tick_step, value)
            for i in range(count)]


def scalar_oracle(values, e):
    step = 2 * e + 1
    decoded = [values[0]]
    previous = values[0]
    for value in values[1:]:
        quotient = (value - previous + e) // step
        reconstructed = previous + quotient * step
        if reconstructed > 65535:
            reconstructed = 65535
        elif reconstructed < 0:
            reconstructed = 0
        decoded.append(reconstructed)
        previous = reconstructed
    return decoded


class ManualVectorTests(unittest.TestCase):
    '''Eight B-main hand-derived vectors copied verbatim into the vector file.'''

    def setUp(self):
        self.vectors = load_vectors()['manual_vectors']['vectors']

    def test_manual_vector_source_hash_is_recorded(self):
        recorded = load_vectors()['manual_vectors']['source_sha256']
        self.assertEqual(
            recorded,
            '36b8e3fdb53e3c8fc911cc44b4f4151d62863d2e05b189f68c42fefe869b2d24')

    def test_decode_payload_restores_expected_points(self):
        for vector in self.vectors:
            with self.subTest(vector=vector['name']):
                record = trace.decode_payload(
                    bytes.fromhex(vector['payload_hex']), vector['binding'])
                self.assertEqual(record['points'], vector['expected_points'])
                self.assertEqual(record['channel'], vector['channel'])

    def test_decode_frame_restores_expected_points_and_sequence(self):
        for vector in self.vectors:
            with self.subTest(vector=vector['name']):
                record = trace.decode_frame(
                    bytes.fromhex(vector['frame_hex']), vector['binding'])
                self.assertEqual(record['points'], vector['expected_points'])
                self.assertEqual(record['sequence'], vector['sequence'])

    def test_encoder_reproduces_golden_bytes(self):
        for vector in self.vectors:
            with self.subTest(vector=vector['name']):
                payload = trace.encode_payload(vector['points'],
                                               vector['binding'],
                                               vector['channel'])
                self.assertEqual(payload.hex(), vector['payload_hex'])
                frame = trace.encode_frame(vector['points'], vector['binding'],
                                           vector['channel'],
                                           vector['sequence'])
                self.assertEqual(frame.hex(), vector['frame_hex'])

    def test_ledger_matches_documented_numbers(self):
        for vector in self.vectors:
            with self.subTest(vector=vector['name']):
                ledger = trace.decode_frame(
                    bytes.fromhex(vector['frame_hex']),
                    vector['binding'])['ledger']
                self.assertEqual(ledger['payload_bytes'], vector['payload_bytes'])
                self.assertEqual(ledger['metadata_bytes'],
                                 vector['metadata_bytes'])
                self.assertEqual(ledger['stored_code_bytes'], vector['code_bytes'])
                self.assertEqual(ledger['significant_bits'],
                                 vector['significant_bits'])
                self.assertEqual(ledger['padding_bits'], vector['padding_bits'])
                self.assertEqual(ledger['frame_bytes'], vector['frame_bytes'])
                self.assertEqual(ledger['line_bits_8n1'], vector['line_bits_8N1'])
                self.assertEqual(ledger['frame_bytes'],
                                 ledger['payload_bytes']
                                 + ledger['outer_overhead_bytes'])
                self.assertEqual(ledger['line_bits_8n1'],
                                 10 * ledger['frame_bytes'])
                self.assertEqual(ledger['payload_bytes'],
                                 ledger['metadata_bytes']
                                 + ledger['stored_code_bytes'])
                self.assertEqual(ledger['padding_bits'],
                                 8 * ledger['stored_code_bytes']
                                 - ledger['significant_bits'])
                self.assertEqual(ledger['selected_raw_bytes'],
                                 2 * ledger['value_count'])

    def test_stored_ledger_matches_recorded_fields(self):
        for vector in self.vectors:
            with self.subTest(vector=vector['name']):
                self.assertEqual(vector['byte_ledger']['payload_bytes'],
                                 vector['payload_bytes'])
                self.assertTrue(vector['implementation_reproduction']
                                ['payload_matches_main_bytes'])
                self.assertTrue(vector['implementation_reproduction']
                                ['frame_matches_main_bytes'])

    def test_manual_revision_and_settings_shape(self):
        for vector in self.vectors:
            with self.subTest(vector=vector['name']):
                payload = bytes.fromhex(vector['payload_hex'])
                self.assertEqual(payload[0], 1)
                settings = payload[1]
                self.assertLessEqual(settings & 0x07, 4)
                if settings & 0x08:
                    self.assertEqual(settings >> 4, 0)


class CodeSelectionTests(unittest.TestCase):
    '''Canonical mode/k selection and the documented inner-codec difference.'''

    def test_all_e_round_trip(self):
        for e in (0, 1, 2, 4, 8):
            bind = dict(BINDING, e=e)
            points = [make_point(i * 3, 1000 + i * 10, 1000 + i * 3)
                      for i in range(8)]
            with self.subTest(e=e):
                payload = trace.encode_payload(points, bind, 1)
                self.assertEqual(payload[1] & 0x07, trace.E_CODE[e])
                record = trace.decode_payload(payload, bind)
                self.assertEqual(record['e'], e)
                if e == 0:
                    self.assertEqual(record['points'], points)
                else:
                    error = max(abs(r['value'] - s['value'])
                                for r, s in zip(record['points'], points))
                    self.assertLessEqual(error, e)

    def test_rice_decode_matches_scalar_oracle(self):
        values = [1000 + i * 3 for i in range(8)]
        points = [make_point(i * 3, 1000 + i * 10, values[i])
                  for i in range(8)]
        for e in (1, 2, 4, 8):
            bind = dict(BINDING, e=e)
            with self.subTest(e=e):
                record = trace.decode_payload(
                    trace.encode_payload(points, bind, 1), bind)
                self.assertEqual([p['value'] for p in record['points']],
                                 scalar_oracle(values, e))

    def test_stored_byte_tie_raw_wins_vs_inner_bit_rule(self):
        points = [make_point(0, 0, 0), make_point(1, 10, 64)]
        payload = trace.encode_payload(points, BINDING, 0)
        record = trace.decode_payload(payload, BINDING)
        self.assertEqual(record['mode'], 'raw')
        self.assertEqual(record['significant_bits'], 32)
        self.assertEqual(record['ledger']['stored_code_bytes'], 4)
        self.assertEqual(record['ledger']['selected_raw_bytes'], 4)
        inner_fixture = inner.encode_block([0, 64], 0)
        self.assertEqual(inner_fixture['mode'], 'rice')
        self.assertEqual(inner_fixture['k'], 6)
        self.assertEqual(inner_fixture['valid_bit_count'], 25)
        self.assertNotEqual(bytes.fromhex(inner_fixture['payload_hex']),
                            payload[25:])

    def test_triple_stored_tie_stays_raw(self):
        points = [make_point(0, 0, 0), make_point(1, 10, 2048),
                  make_point(2, 20, 4096)]
        record = trace.decode_payload(trace.encode_payload(points, BINDING, 0),
                                      BINDING)
        self.assertEqual(record['mode'], 'raw')
        self.assertEqual(record['significant_bits'], 48)
        # Inner bit rule keeps rice (28 body bits < 32 raw bits) while the
        # candidate stored-byte rule ties at 6 bytes and stays RAW.
        inner_fixture = inner.encode_block([0, 2048, 4096], 0)
        self.assertEqual(inner_fixture['mode'], 'rice')
        self.assertEqual(inner_fixture['k'], 11)
        self.assertEqual(inner_fixture['valid_bit_count'], 44)

    def test_single_point_is_raw(self):
        for points in ([make_point(7, 1000, 1234)],
                       [make_point(7, 1000, 5, held_origin=900)],
                       [make_point(7, 100000, 9, held_origin=0)]):
            with self.subTest(tick=points[0]['tick_ms']):
                record = trace.decode_payload(
                    trace.encode_payload(points, BINDING, 0), BINDING)
                self.assertEqual(record['mode'], 'raw')
                self.assertEqual(record['k'], 0)

    def test_rice_selected_when_strictly_byte_better(self):
        points = [make_point(10 + i, 1000 + 10 * i, 100) for i in range(3)]
        record = trace.decode_payload(trace.encode_payload(points, BINDING, 1),
                                      BINDING)
        self.assertEqual(record['mode'], 'rice')
        self.assertEqual(record['k'], 0)
        self.assertEqual(record['significant_bits'], 18)

    def test_noncanonical_k_rejected_in_code(self):
        points = [make_point(10 + i, 1000 + 10 * i, 100) for i in range(3)]
        payload = bytearray(trace.encode_payload(points, BINDING, 1))
        payload[1] = 0x10
        payload[4] = 20
        payload[-1] = 0xA0
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_payload(bytes(payload), BINDING)
        self.assertIn('noncanonical', str(context.exception))


class BoundaryTests(unittest.TestCase):
    def test_exact_32B_payload_and_46B_frame(self):
        points = flat_points(41)
        payload = trace.encode_payload(points, BINDING, 0)
        frame = trace.encode_frame(points, BINDING, 0, 9)
        self.assertEqual(len(payload), 32)
        self.assertEqual(len(frame), 46)

    def test_33B_payload_rejected(self):
        with self.assertRaises(trace.TraceError) as context:
            trace.encode_payload(flat_points(42), BINDING, 0)
        self.assertIn('candidate budget', str(context.exception))

    def test_oversize_block_rejected_before_uint8_bits(self):
        values = [0 if position % 2 == 0 else 65535 for position in range(128)]
        points = [make_point(position, 1000 + 10 * position, values[position])
                  for position in range(128)]
        with self.assertRaises(trace.TraceError) as context:
            trace.encode_payload(points, BINDING, 0)
        self.assertIn('exceed the uint8 field', str(context.exception))

    def test_packer_splits_42_flat(self):
        points = flat_points(42)
        frames = trace.pack_channel(points, BINDING, 0, 0)
        self.assertEqual([len(frame) for frame in frames], [46, 37])
        restored = []
        for frame in frames:
            restored.extend(trace.decode_frame(frame, BINDING)['points'])
        self.assertEqual(restored, points)

    def test_singleton_payload_sizes(self):
        fresh = trace.encode_payload([make_point(7, 1000, 1234)], BINDING, 0)
        invalid = trace.encode_payload(
            [make_point(7, 1000, None, invalid=True)], BINDING, 0)
        held_short = trace.encode_payload(
            [make_point(7, 1000, 5, held_origin=900)], BINDING, 0)
        held_long = trace.encode_payload(
            [make_point(7, 100000, 9, held_origin=0)], BINDING, 0)
        self.assertEqual(len(fresh), 23)
        self.assertEqual(len(invalid), 21)
        self.assertEqual(len(held_short), 25)
        self.assertEqual(len(held_long), 31)

    def test_invalid_128_single_block(self):
        points = [make_point(i, i * 10, None, fault=True, invalid=True)
                  for i in range(128)]
        frames = trace.pack_channel(points, BINDING, 3, 0)
        self.assertEqual(len(frames), 1)
        record = trace.decode_frame(frames[0], BINDING)
        self.assertEqual(record['count'], 128)
        self.assertEqual(record['ledger']['payload_bytes'], 25)
        self.assertEqual(record['ledger']['stored_code_bytes'], 0)
        self.assertEqual(record['points'], points)

    def test_gap_larger_than_stride_range_splits(self):
        points = [make_point(0, 0, 5), make_point(70000, 70000, 6),
                  make_point(140001, 140001, 7)]
        frames = trace.pack_channel(points, BINDING, 0, 0)
        self.assertEqual(len(frames), 3)
        restored = []
        for frame in frames:
            restored.extend(trace.decode_frame(frame, BINDING)['points'])
        self.assertEqual(restored, points)

    def test_pack_requires_strict_increase(self):
        with self.assertRaises(trace.TraceError):
            trace.pack_channel([make_point(0, 0, 1), make_point(0, 10, 2)],
                               BINDING, 0, 0)
        with self.assertRaises(trace.TraceError):
            trace.pack_channel([make_point(5, 50, 1), make_point(4, 40, 2)],
                               BINDING, 0, 0)

    def test_uint32_index_and_uint64_tick_high_range(self):
        points = [make_point((1 << 32) - 501 + i * 3, (1 << 64) - 1001 + i * 10, 3)
                  for i in range(10)]
        frames = trace.pack_channel(points, BINDING, 0, 0)
        restored = []
        for frame in frames:
            restored.extend(trace.decode_frame(frame, BINDING)['points'])
        self.assertEqual(restored, points)

    def test_low32_tick_rollover_restores_uint64_ticks(self):
        points = [make_point(i + 1, 4294967290 + i * 10, 1) for i in range(4)]
        frames = trace.pack_channel(points, BINDING, 0, 0)
        restored = []
        for frame in frames:
            record = trace.decode_frame(frame, BINDING)
            header_tick = struct.unpack_from('<I', frame, 8)[0]
            self.assertEqual(header_tick, record['first_tick_ms'] & 0xFFFFFFFF)
            restored.extend(record['points'])
        self.assertEqual(restored, points)


class WireFormatTests(unittest.TestCase):
    def test_anchor_and_raw_words_are_little_endian(self):
        points = [make_point(0, 0, 0x1234), make_point(1, 10, 0xABCD)]
        payload = trace.encode_payload(points, BINDING, 0)
        code = payload[25:]
        self.assertEqual(code[:2], b'\x34\x12')
        self.assertEqual(code[2:4], b'\xcd\xab')

    def test_header_fields_and_crc(self):
        points = [make_point(7, 1000, 1234)]
        frame = trace.encode_frame(points, BINDING, 0, 9)
        self.assertEqual(frame[:2], b'\xa5\x5a')
        self.assertEqual(frame[2], 3)
        self.assertEqual(frame[3], 7)
        self.assertEqual(frame[4], len(frame) - 14)
        self.assertEqual(frame[5], 2)
        self.assertEqual(struct.unpack_from('<H', frame, 6)[0], 9)
        self.assertEqual(struct.unpack_from('<I', frame, 8)[0], 1000)
        stored_crc = struct.unpack_from('<H', frame, len(frame) - 2)[0]
        self.assertEqual(stored_crc, binascii.crc_hqx(frame[2:-2], 0xFFFF))

    def test_quality_flags_expand_to_every_point(self):
        points = [make_point(i, i * 10, 65535, saturated=True, fault=True)
                  for i in range(3)]
        record = trace.decode_payload(trace.encode_payload(points, BINDING, 0),
                                      BINDING)
        for point in record['points']:
            self.assertTrue(point['valid'])
            self.assertTrue(point['saturated'])
            self.assertTrue(point['source_fault'])
            self.assertFalse(point['held'])


class VectorDrivenTests(unittest.TestCase):
    '''Every committed synthetic vector regenerates exactly.'''

    def setUp(self):
        self.document = load_vectors()

    def test_every_synthetic_vector_regenerates(self):
        for entry in self.document['synthetic_vectors']:
            with self.subTest(entry=entry['id']):
                frames = trace.pack_channel(entry['source_points'],
                                            entry['binding'],
                                            entry['channel'],
                                            entry['start_sequence'])
                self.assertEqual([frame.hex() for frame in frames],
                                 entry['frames_hex'])
                restored = []
                for frame in frames:
                    restored.extend(trace.decode_frame(frame,
                                                       entry['binding'])['points'])
                self.assertEqual(restored, entry['restored_points'])

    def test_vector_ledgers_recompute(self):
        for entry in self.document['synthetic_vectors']:
            with self.subTest(entry=entry['id']):
                for frame_hex, recorded in zip(entry['frames_hex'],
                                               entry['ledger_per_frame']):
                    ledger = trace.decode_frame(
                        bytes.fromhex(frame_hex), entry['binding'])['ledger']
                    self.assertEqual(ledger, recorded)

    def test_aggregate_ledgers_sum(self):
        keys = ('payload_bytes', 'frame_bytes', 'line_bits_8n1', 'value_count',
                'selected_raw_bytes', 'significant_bits', 'stored_code_bytes',
                'padding_bits', 'metadata_bytes')
        for entry in self.document['synthetic_vectors']:
            with self.subTest(entry=entry['id']):
                aggregate = entry['aggregate_ledger']
                self.assertEqual(aggregate['frame_count'],
                                 len(entry['ledger_per_frame']))
                for key in keys:
                    self.assertEqual(
                        aggregate[key + '_total'],
                        sum(ledger[key] for ledger in entry['ledger_per_frame']))

    def test_packer_verification_vector_reproduces(self):
        entries = [entry for entry in self.document['packer_verification']
                   if entry['id'] == 'greedy_equals_brute_force_longest_prefix']
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        frames = trace.pack_channel(entry['source_points'], entry['binding'],
                                    entry['channel'], entry['start_sequence'])
        self.assertEqual([frame.hex() for frame in frames], entry['frames_hex'])

    def test_sequence_capacity_vector_reproduces(self):
        entries = [entry for entry in self.document['packer_verification']
                   if entry['id'] == 'sequence_capacity_rejection']
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        with self.assertRaises(trace.TraceError) as context:
            trace.pack_channel(entry['source_points'], entry['binding'],
                               entry['channel'], entry['start_sequence'])
        self.assertIn(entry['expect_error_contains'], str(context.exception))
        frames = trace.pack_channel(entry['source_points'], entry['binding'],
                                    entry['channel'], 0)
        self.assertEqual(len(frames), entry['frame_count_at_zero'])

    def test_malformed_payload_vectors_rejected(self):
        for entry in self.document['malformed_payloads']:
            with self.subTest(entry=entry['id']):
                with self.assertRaises(trace.TraceError) as context:
                    trace.decode_payload(bytes.fromhex(entry['payload_hex']),
                                         entry['binding'])
                self.assertIn(entry['expect_error_contains'],
                              str(context.exception))

    def test_malformed_frame_vectors_rejected(self):
        for entry in self.document['malformed_frames']:
            with self.subTest(entry=entry['id']):
                with self.assertRaises(trace.TraceError) as context:
                    trace.decode_frame(bytes.fromhex(entry['frame_hex']),
                                       entry['binding'])
                self.assertIn(entry['expect_error_contains'],
                              str(context.exception))

    def test_channel_4x128_vectors_present_and_bounded(self):
        entries = [entry for entry in self.document['synthetic_vectors']
                   if entry['group'] == 'channels_4x128']
        self.assertEqual(len(entries), 4)
        self.assertEqual(sorted(entry['channel'] for entry in entries),
                         [0, 1, 2, 3])
        for entry in entries:
            self.assertEqual(len(entry['source_points']), 128)
            for frame_hex in entry['frames_hex']:
                self.assertLessEqual(len(bytes.fromhex(frame_hex)), 46)

    def test_required_vector_groups_present(self):
        groups = {entry['group']
                  for entry in self.document['synthetic_vectors']}
        for group in ('all_e', 'boundary', 'mask', 'age_forms', 'tick_forms',
                      'tie', 'sparse_pack', 'channels_4x128'):
            self.assertIn(group, groups)

    def test_contract_block_pinned(self):
        contract = self.document['contract']
        self.assertEqual(contract['requirements_sha256'],
                         'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804')
        self.assertEqual(contract['contract_commit'],
                         'f5989cd5defce561f9ba98e6b18fc2682945f0a2')
        self.assertEqual(self.document['design_commit'],
                         '1011259415a0916054eb580687612580bc1e5f09')
        self.assertEqual(self.document['base_commit'],
                         'c5d079c24e45d97d6bd8181a7414a64c7c110860')


class MalformedCraftTests(unittest.TestCase):
    '''Hand-crafted malformed payloads and frames beyond the stored vectors.'''

    def setUp(self):
        self.single = trace.encode_payload([make_point(7, 1000, 1234)],
                                           BINDING, 0)
        self.flat41 = trace.encode_payload(flat_points(41), BINDING, 0)
        self.three = trace.encode_payload(
            [make_point(10 + i, 1000 + 10 * i, 100) for i in range(3)],
            BINDING, 1)

    def test_payload_length_bounds(self):
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(self.flat41 + b'\x00', BINDING)
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(self.single + b'\x00', BINDING)
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(b'', BINDING)

    def test_nonzero_padding_bit_rejected(self):
        payload = bytearray(self.three)
        payload[-1] |= 1
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_payload(bytes(payload), BINDING)
        self.assertIn('padding', str(context.exception))

    def test_unary_truncated_and_overlong(self):
        prefix = self.three[:21]
        truncated = bytearray(prefix + bytes.fromhex('01000a00640000'))
        truncated[4] = 18
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_payload(bytes(truncated), BINDING)
        self.assertIn('truncated', str(context.exception))
        overlong = bytearray(prefix + bytes.fromhex('01000a0064000000000080'))
        overlong[3] = 2
        overlong[4] = 49
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_payload(bytes(overlong), BINDING)
        self.assertIn('overlong', str(context.exception))

    def test_raw_claim_when_rice_strictly_better(self):
        raw_claim = bytearray(self.three[:21]
                              + bytes.fromhex('01000a00640064006400'))
        raw_claim[1] = 0x08
        raw_claim[4] = 48
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_payload(bytes(raw_claim), BINDING)
        self.assertIn('noncanonical mode', str(context.exception))

    def test_metadata_rejections(self):
        reserved = bytearray(self.single)
        reserved[2] |= 0x80
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(reserved), BINDING)
        e_mismatch = bytearray(self.single)
        e_mismatch[1] = (e_mismatch[1] & 0xF8) | 1
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(e_mismatch), BINDING)
        session = bytearray(self.single)
        session[5] ^= 1
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(session), BINDING)
        count_zero = bytearray(self.single)
        count_zero[3] = 0
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(count_zero), BINDING)
        count_high = bytearray(self.single)
        count_high[3] = 129
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(count_high), BINDING)
        stride_zero = bytearray(self.three)
        stride_zero[21:23] = b'\x00\x00'
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(stride_zero), BINDING)
        overflow = bytearray(self.three)
        overflow[9:13] = struct.pack('<I', 0xFFFFFFFF)
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(overflow), BINDING)
        overflow = bytearray(self.three)
        overflow[13:21] = struct.pack('<Q', 0xFFFFFFFFFFFFFFF5)
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(overflow), BINDING)
        raw_k = bytearray(self.single)
        raw_k[1] |= 0x10
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(raw_k), BINDING)

    def test_invalid_shape_rejections(self):
        invalid = trace.encode_payload(
            [make_point(7, 1000, None, invalid=True)], BINDING, 3)
        held_invalid = bytearray(invalid)
        held_invalid[2] |= 0x10
        held_invalid += b'\x01\x00'
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_payload(bytes(held_invalid), BINDING)
        self.assertIn('held', str(context.exception))
        no_raw = bytearray(invalid)
        no_raw[1] &= ~8
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(no_raw), BINDING)
        with_bits = bytearray(invalid)
        with_bits[4] = 16
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(with_bits), BINDING)
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(invalid + b'\x00', BINDING)

    def test_held_form_rejections(self):
        short = trace.encode_payload([make_point(7, 1000, 5, held_origin=900)],
                                     BINDING, 0)
        zero_age = bytearray(short)
        zero_age[21:23] = b'\x00\x00'
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(zero_age), BINDING)
        long_form = trace.encode_payload(
            [make_point(7, 70000, 5, held_origin=0)], BINDING, 0)
        bad_long = bytearray(long_form)
        bad_long[21:29] = struct.pack('<Q', 69900)
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(bad_long), BINDING)
        long_without_held = bytearray(short)
        long_without_held[2] |= 0x40
        trimmed = bytes(long_without_held[:21]) + bytes(long_without_held[23:])
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(trimmed, BINDING)

    def test_frame_header_rejections(self):
        frame = trace.encode_frame([make_point(0, 1000, 100)], BINDING, 0, 7)
        cases = []
        bad_magic = bytearray(frame)
        bad_magic[0:2] = b'\x00\x00'
        cases.append(('magic', bytes(bad_magic)))
        bad_version = bytearray(frame)
        bad_version[2] = 2
        cases.append(('version', bytes(bad_version)))
        bad_type = bytearray(frame)
        bad_type[3] = 6
        cases.append(('type', bytes(bad_type)))
        declared = bytearray(frame)
        declared[4] = 33
        cases.append(('declared length 33', bytes(declared)))
        mismatched = bytearray(frame)
        mismatched[4] = len(frame) - 14 + 1
        cases.append(('length mismatch', bytes(mismatched)))
        cases.append(('short header', b'\xa5\x5a\x03\x07'))
        cases.append(('oversize', frame + bytes(47 - len(frame))))
        for name, packet in cases:
            with self.subTest(case=name):
                with self.assertRaises(trace.TraceError):
                    trace.decode_frame(packet, BINDING)

    def test_frame_epoch_and_tick_low_consistency(self):
        frame = trace.encode_frame([make_point(0, 1000, 100)], BINDING, 0, 7)
        other_epoch = bytearray(frame)
        other_epoch[5] = 3
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_frame(bytes(other_epoch), BINDING)
        self.assertIn('epoch', str(context.exception))
        wrong_tick = bytearray(frame)
        struct.pack_into('<I', wrong_tick, 8, 1001)
        crc = binascii.crc_hqx(bytes(wrong_tick)[2:-2], 0xFFFF)
        struct.pack_into('<H', wrong_tick, len(frame) - 2, crc)
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_frame(bytes(wrong_tick), BINDING)
        self.assertIn('tick', str(context.exception))
        record = trace.decode_frame(frame, BINDING)
        self.assertEqual(record['first_tick_ms'], 1000)
        self.assertEqual(struct.unpack_from('<I', frame, 8)[0], 1000)
        self.assertEqual(record['sequence'], 7)


class MaskAndAgeTests(unittest.TestCase):
    '''Quality-mask uniformity, held origin tracking and age-form bounds.'''

    def _pack_and_decode(self, points, channel=0):
        frames = trace.pack_channel(points, BINDING, channel, 0)
        return [trace.decode_frame(frame, BINDING) for frame in frames]

    def test_flag_change_splits(self):
        cases = [
            ('valid_to_invalid',
             [make_point(0, 1000, 100),
              make_point(1, 1010, None, invalid=True)],
             [(True, False, False, False), (False, False, False, False)]),
            ('invalid_to_valid',
             [make_point(0, 1000, None, invalid=True),
              make_point(1, 1010, 100)],
             [(False, False, False, False), (True, False, False, False)]),
            ('saturated_on',
             [make_point(0, 1000, 100),
              make_point(1, 1010, 65535, saturated=True)],
             [(True, False, False, False), (True, True, False, False)]),
            ('saturated_off',
             [make_point(0, 1000, 65535, saturated=True),
              make_point(1, 1010, 100)],
             [(True, True, False, False), (True, False, False, False)]),
            ('held_on',
             [make_point(0, 1000, 100),
              make_point(1, 1010, 100, held_origin=900)],
             [(True, False, False, False), (True, False, True, False)]),
            ('held_off',
             [make_point(0, 1000, 100, held_origin=900),
              make_point(1, 1010, 100)],
             [(True, False, True, False), (True, False, False, False)]),
            ('fault_on',
             [make_point(0, 1000, 100),
              make_point(1, 1010, 100, fault=True)],
             [(True, False, False, False), (True, False, False, True)]),
            ('fault_off',
             [make_point(0, 1000, 100, fault=True),
              make_point(1, 1010, 100)],
             [(True, False, False, True), (True, False, False, False)]),
        ]
        for name, points, expected in cases:
            with self.subTest(case=name):
                records = self._pack_and_decode(points)
                self.assertEqual(len(records), 2)
                seen = []
                for record in records:
                    flags = (record['valid'], record['saturated'],
                             record['held'], record['source_fault'])
                    seen.append(flags)
                    for point in record['points']:
                        self.assertEqual(
                            (point['valid'], point['saturated'],
                             point['held'], point['source_fault']), flags)
                self.assertEqual(seen, expected)
                self.assertEqual(
                    sum(len(record['points']) for record in records),
                    len(points))

    def test_origin_change_splits(self):
        points = [make_point(0, 1000, 100, held_origin=990),
                  make_point(1, 1010, 100, held_origin=980)]
        records = self._pack_and_decode(points)
        self.assertEqual(len(records), 2)
        self.assertTrue(all(record['held'] for record in records))
        self.assertEqual(records[0]['held_origin_tick_ms'], 990)
        self.assertEqual(records[1]['held_origin_tick_ms'], 980)
        self.assertEqual(records[0]['points'], [points[0]])
        self.assertEqual(records[1]['points'], [points[1]])

    def test_saturated_flag_does_not_imply_endpoint(self):
        points = [make_point(0, 1000, 1234, saturated=True),
                  make_point(1, 1010, 65535, saturated=True),
                  make_point(2, 1020, 42, saturated=True)]
        payload = trace.encode_payload(points, BINDING, 2)
        record = trace.decode_payload(payload, BINDING)
        self.assertEqual([point['value'] for point in record['points']],
                         [1234, 65535, 42])
        self.assertTrue(all(point['saturated'] for point in record['points']))
        self.assertEqual(len(trace.pack_channel(points, BINDING, 2, 0)), 1)

    def test_invalid_source_fault_round_trip(self):
        points = [make_point(0, 1000, None, invalid=True, fault=True),
                  make_point(1, 1010, None, invalid=True, fault=True)]
        payload = trace.encode_payload(points, BINDING, 3)
        record = trace.decode_payload(payload, BINDING)
        self.assertFalse(record['valid'])
        self.assertTrue(record['source_fault'])
        self.assertEqual(record['ledger']['value_count'], 0)
        self.assertEqual(record['ledger']['selected_raw_bytes'], 0)
        self.assertEqual(record['ledger']['stored_code_bytes'], 0)
        self.assertEqual(record['ledger']['significant_bits'], 0)
        self.assertEqual(record['points'], points)

    def test_invalid_flag_combinations_rejected(self):
        base = trace.encode_payload(
            [make_point(0, 1000, None, invalid=True)], BINDING, 0)
        saturated = bytearray(base)
        saturated[2] |= 0x08
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(bytes(saturated), BINDING)
        held = bytearray(base)
        held[2] |= 0x10
        held += b'\x01\x00'
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_payload(bytes(held), BINDING)
        self.assertIn('held', str(context.exception))
        bad_saturated = {'index': 0, 'tick_ms': 1000, 'value': None,
                         'valid': False, 'saturated': True, 'held': False,
                         'source_fault': False, 'source_tick_ms': None}
        with self.assertRaises(trace.TraceError):
            trace.encode_payload([bad_saturated], BINDING, 0)
        bad_held = dict(bad_saturated)
        bad_held['saturated'] = False
        bad_held['held'] = True
        with self.assertRaises(trace.TraceError):
            trace.encode_payload([bad_held], BINDING, 0)

    def test_held_age_boundaries(self):
        short_points = [make_point(0, 70000, 100, held_origin=4465)]
        short_payload = trace.encode_payload(short_points, BINDING, 0)
        self.assertEqual(len(short_payload), 25)
        short_record = trace.decode_payload(short_payload, BINDING)
        self.assertFalse(short_record['long_source_tick'])
        self.assertEqual(short_record['held_origin_tick_ms'], 4465)
        self.assertEqual(short_record['points'], short_points)
        long_points = [make_point(0, 70000, 100, held_origin=4464)]
        long_payload = trace.encode_payload(long_points, BINDING, 0)
        self.assertEqual(len(long_payload), 31)
        long_record = trace.decode_payload(long_payload, BINDING)
        self.assertTrue(long_record['long_source_tick'])
        self.assertEqual(long_record['held_origin_tick_ms'], 4464)
        self.assertEqual(long_record['points'], long_points)
        crafted = bytearray(long_payload)
        crafted[21:29] = struct.pack('<Q', 4465)
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_payload(bytes(crafted), BINDING)
        self.assertIn('canonical', str(context.exception))


class TraceReceiverTests(unittest.TestCase):
    '''Bounded receiver: duplicates, conflicts, order, close and detachment.'''

    def make_frame(self, sequence, index=0, tick=1000, value=100, channel=0,
                   count=1):
        points = [make_point(index + offset, tick + 10 * offset,
                             value + offset)
                  for offset in range(count)]
        return trace.encode_frame(points, BINDING, channel, sequence)

    def test_duplicate_returns_zero_points(self):
        receiver = trace.TraceReceiver(BINDING)
        frame = self.make_frame(5)
        first = receiver.accept(frame)
        self.assertEqual(first['status'], 'ok')
        self.assertEqual(len(first['points']), 1)
        duplicate = receiver.accept(frame)
        self.assertEqual(duplicate['status'], 'duplicate')
        self.assertEqual(duplicate['sequence'], 5)
        self.assertEqual(duplicate['points'], [])
        snapshot = receiver.state_snapshot()
        self.assertEqual(snapshot['last_sequence'], 5)
        self.assertEqual(len(snapshot['packet_cache']), 1)

    def test_sequence_conflict_same_number(self):
        receiver = trace.TraceReceiver(BINDING)
        receiver.accept(self.make_frame(5, value=100))
        with self.assertRaises(trace.TraceError) as context:
            receiver.accept(self.make_frame(5, value=200))
        self.assertIn('conflict', str(context.exception))
        snapshot = receiver.state_snapshot()
        self.assertEqual(snapshot['last_sequence'], 5)
        self.assertEqual(len(snapshot['packet_cache']), 1)
        again = receiver.accept(self.make_frame(5, value=100))
        self.assertEqual(again['status'], 'duplicate')

    def test_stale_sequence_outside_cache_rejected(self):
        receiver = trace.TraceReceiver(BINDING)
        frames = [self.make_frame(sequence, index=10 * sequence,
                                  tick=1000 + 10 * sequence,
                                  value=100 + sequence)
                  for sequence in range(17)]
        for frame in frames:
            receiver.accept(frame)
        snapshot = receiver.state_snapshot()
        self.assertEqual(len(snapshot['packet_cache']), 16)
        self.assertEqual(snapshot['last_sequence'], 16)
        self.assertEqual([seq for seq, _ in snapshot['packet_cache']],
                         list(range(1, 17)))
        self.assertEqual(receiver.accept(frames[16])['status'], 'duplicate')
        with self.assertRaises(trace.TraceError) as context:
            receiver.accept(frames[0])
        self.assertIn('outside the cache', str(context.exception))

    def test_future_gap_accepted_without_synthesis(self):
        receiver = trace.TraceReceiver(BINDING)
        receiver.accept(self.make_frame(3, index=10, tick=100, channel=2))
        result = receiver.accept(self.make_frame(25, index=20, tick=200,
                                                 channel=2, count=2))
        self.assertEqual(result['status'], 'ok')
        self.assertEqual([point['index'] for point in result['points']],
                         [20, 21])
        snapshot = receiver.state_snapshot()
        self.assertEqual(snapshot['last_sequence'], 25)
        self.assertEqual(snapshot['channel_high_water'][2],
                         {'last_index': 21, 'last_tick_ms': 210})

    def test_channel_order_violations_do_not_commit(self):
        receiver = trace.TraceReceiver(BINDING)
        receiver.accept(self.make_frame(0, index=100, tick=1000, channel=1))
        before = receiver.state_snapshot()
        with self.assertRaises(trace.TraceError) as context:
            receiver.accept(self.make_frame(1, index=50, tick=2000, channel=1))
        self.assertIn('index order', str(context.exception))
        self.assertEqual(receiver.state_snapshot(), before)
        with self.assertRaises(trace.TraceError) as context:
            receiver.accept(self.make_frame(2, index=200, tick=500, channel=1))
        self.assertIn('tick order', str(context.exception))
        self.assertEqual(receiver.state_snapshot(), before)
        other = receiver.accept(self.make_frame(3, index=5, tick=5, channel=3))
        self.assertEqual(other['status'], 'ok')

    def test_bad_crc_does_not_advance_state(self):
        receiver = trace.TraceReceiver(BINDING)
        receiver.accept(self.make_frame(0))
        before = receiver.state_snapshot()
        corrupted = bytearray(self.make_frame(1, index=10, tick=1010))
        corrupted[-1] ^= 0xFF
        with self.assertRaises(trace.TraceError):
            receiver.accept(bytes(corrupted))
        self.assertEqual(receiver.state_snapshot(), before)

    def test_close_is_terminal_and_idempotent(self):
        receiver = trace.TraceReceiver(BINDING)
        receiver.accept(self.make_frame(0))
        receiver.close()
        receiver.close()
        snapshot = receiver.state_snapshot()
        self.assertTrue(snapshot['closed'])
        self.assertEqual(snapshot['last_sequence'], 0)
        with self.assertRaises(trace.TraceError) as context:
            receiver.accept(self.make_frame(1, index=10, tick=1010))
        self.assertIn('closed', str(context.exception))

    def test_receiver_outputs_are_detached(self):
        receiver = trace.TraceReceiver(BINDING)
        result = receiver.accept(self.make_frame(0, count=2))
        result['points'].clear()
        result['points'].append({'index': 999})
        result['ledger']['count'] = 999
        snapshot = receiver.state_snapshot()
        snapshot['packet_cache'].clear()
        snapshot['channel_high_water'][0]['last_index'] = -5
        snapshot['binding']['session'] = 0
        fresh = receiver.state_snapshot()
        self.assertEqual(len(fresh['packet_cache']), 1)
        self.assertEqual(fresh['channel_high_water'][0]['last_index'], 1)
        self.assertEqual(fresh['binding']['session'], BINDING['session'])
        again = receiver.accept(self.make_frame(0, count=2))
        self.assertEqual(again['status'], 'duplicate')


class EvilStr(str):
    '''str subclass whose equality raises; the type check must run first.'''

    __hash__ = str.__hash__

    def __eq__(self, other):
        raise AssertionError('str-subclass equality must not run')

    def __ne__(self, other):
        raise AssertionError('str-subclass inequality must not run')


class RaisingInt(int):
    '''int subclass whose comparisons raise; the type check must run first.'''

    def __lt__(self, other):
        raise AssertionError('int-subclass comparison must not run')

    def __le__(self, other):
        raise AssertionError('int-subclass comparison must not run')

    def __gt__(self, other):
        raise AssertionError('int-subclass comparison must not run')

    def __ge__(self, other):
        raise AssertionError('int-subclass comparison must not run')


class Flavour(enum.IntEnum):
    ZERO = 0
    ONE = 1


class IntDict(dict):
    pass


class IntList(list):
    pass


class IntBytes(bytes):
    pass


class InputStrictnessTests(unittest.TestCase):
    '''Exact-type input discipline before any caller operator could run.'''

    def test_binding_must_be_exact_dict(self):
        points = [make_point(0, 1000, 100)]
        for bad in ([], IntDict(BINDING), 'binding', None, 7):
            with self.subTest(kind=type(bad).__name__):
                with self.assertRaises(trace.TraceError):
                    trace.encode_payload(points, bad, 0)

    def test_point_sequence_types(self):
        point = make_point(0, 1000, 100)
        with self.assertRaises(trace.TraceError):
            trace.encode_payload(IntList([point]), BINDING, 0)
        with self.assertRaises(trace.TraceError):
            trace.encode_payload((item for item in [point]), BINDING, 0)
        with self.assertRaises(trace.TraceError):
            trace.encode_payload({0: point}, BINDING, 0)
        with self.assertRaises(trace.TraceError):
            trace.encode_payload([], BINDING, 0)
        self.assertEqual(trace.encode_payload((point,), BINDING, 0),
                         trace.encode_payload([point], BINDING, 0))

    def test_point_mappings_and_keys(self):
        point = make_point(0, 1000, 100)
        with self.assertRaises(trace.TraceError):
            trace.encode_payload([IntDict(point)], BINDING, 0)
        with self.assertRaises(trace.TraceError):
            trace.encode_payload(['not a dict'], BINDING, 0)
        extra = dict(point)
        extra['unexpected'] = 1
        with self.assertRaises(trace.TraceError):
            trace.encode_payload([extra], BINDING, 0)
        missing = dict(point)
        del missing['source_tick_ms']
        with self.assertRaises(trace.TraceError):
            trace.encode_payload([missing], BINDING, 0)

    def test_str_subclass_keys_rejected_before_equality(self):
        evil_binding = {EvilStr('session'): 1, EvilStr('config_epoch'): 2,
                        EvilStr('e'): 0}
        with self.assertRaises(trace.TraceError) as context:
            trace.encode_payload([make_point(0, 1000, 100)], evil_binding, 0)
        self.assertIn('non-str key', str(context.exception))
        point = make_point(0, 1000, 100)
        evil_point = {EvilStr(key): value for key, value in point.items()}
        with self.assertRaises(trace.TraceError) as context:
            trace.encode_payload([evil_point], BINDING, 0)
        self.assertIn('non-str key', str(context.exception))

    def test_exact_scalar_types_before_operators(self):
        point = make_point(0, 1000, 100)
        for bad in (True, False, RaisingInt(5), Flavour.ONE, 1.0, '1'):
            with self.subTest(index=repr(bad)):
                mutated = dict(point)
                mutated['index'] = bad
                with self.assertRaises(trace.TraceError):
                    trace.encode_payload([mutated], BINDING, 0)
        for field in ('tick_ms', 'value'):
            mutated = dict(point)
            mutated[field] = Flavour.ONE
            with self.assertRaises(trace.TraceError):
                trace.encode_payload([mutated], BINDING, 0)
        for field in ('valid', 'saturated', 'held', 'source_fault'):
            mutated = dict(point)
            mutated[field] = 1
            with self.assertRaises(trace.TraceError):
                trace.encode_payload([mutated], BINDING, 0)
        mutated = dict(point)
        mutated['tick_ms'] = RaisingInt(1000)
        with self.assertRaises(trace.TraceError):
            trace.encode_payload([mutated], BINDING, 0)

    def test_channel_and_sequence_bounds(self):
        points = [make_point(0, 1000, 100)]
        for bad in (-1, 4, True, Flavour.ZERO, 2 ** 31):
            with self.subTest(channel=repr(bad)):
                with self.assertRaises(trace.TraceError):
                    trace.encode_frame(points, BINDING, bad, 0)
        with self.assertRaises(trace.TraceError):
            trace.encode_frame(points, BINDING, 0, 65536)
        with self.assertRaises(trace.TraceError):
            trace.encode_frame(points, BINDING, 0, -1)
        with self.assertRaises(trace.TraceError):
            trace.pack_channel(points, BINDING, 0, Flavour.ONE)
        frame = trace.encode_frame(points, BINDING, 3, 65535)
        record = trace.decode_frame(frame, BINDING)
        self.assertEqual(record['sequence'], 65535)
        self.assertEqual(record['channel'], 3)

    def test_binding_scalar_bounds(self):
        points = [make_point(0, 1000, 100)]
        for bad_binding in (
                {'session': 2 ** 32, 'config_epoch': 0, 'e': 0},
                {'session': -1, 'config_epoch': 0, 'e': 0},
                {'session': 0, 'config_epoch': 256, 'e': 0},
                {'session': 0, 'config_epoch': 0, 'e': 3},
                {'session': True, 'config_epoch': 0, 'e': 0},
                {'session': 0, 'config_epoch': 0, 'e': RaisingInt(0)}):
            with self.subTest(binding=repr(bad_binding)):
                with self.assertRaises(trace.TraceError):
                    trace.encode_payload(points, bad_binding, 0)

    def test_payload_and_packet_must_be_exact_bytes(self):
        frame = trace.encode_frame([make_point(0, 1000, 100)], BINDING, 0, 0)
        payload = frame[12:-2]
        for bad in (bytearray(payload), IntBytes(payload),
                    memoryview(payload), payload.hex(), list(payload)):
            with self.subTest(kind=type(bad).__name__):
                with self.assertRaises(trace.TraceError):
                    trace.decode_payload(bad, BINDING)
                with self.assertRaises(trace.TraceError):
                    trace.decode_frame(bad, BINDING)
        record = trace.decode_payload(payload, BINDING)
        self.assertEqual(record['channel'], 0)
        self.assertEqual(trace.decode_frame(frame, BINDING)['sequence'], 0)

    def test_source_tick_consistency(self):
        fresh = make_point(0, 1000, 100)
        fresh['source_tick_ms'] = 999
        with self.assertRaises(trace.TraceError):
            trace.encode_payload([fresh], BINDING, 0)
        held = make_point(0, 1000, 100, held_origin=999)
        held['source_tick_ms'] = 1000
        with self.assertRaises(trace.TraceError):
            trace.encode_payload([held], BINDING, 0)
        invalid = {'index': 0, 'tick_ms': 1000, 'value': 5, 'valid': False,
                   'saturated': False, 'held': False, 'source_fault': False,
                   'source_tick_ms': None}
        with self.assertRaises(trace.TraceError):
            trace.encode_payload([invalid], BINDING, 0)
        stray_source = dict(invalid)
        stray_source['value'] = None
        stray_source['source_tick_ms'] = 1000
        with self.assertRaises(trace.TraceError):
            trace.encode_payload([stray_source], BINDING, 0)


class DetachedStateTests(unittest.TestCase):
    '''Caller mutation must never reach encoder state or returned records.'''

    def test_encoder_reads_current_inputs_and_leaves_them_untouched(self):
        binding = dict(BINDING)
        point = make_point(0, 1000, 100)
        points = [point]
        before = json.dumps([binding, points], sort_keys=True)
        payload = trace.encode_payload(points, binding, 0)
        self.assertEqual(json.dumps([binding, points], sort_keys=True), before)
        self.assertEqual(
            trace.decode_payload(payload, BINDING)['points'][0]['value'], 100)
        point['value'] = 200
        different = trace.encode_payload(points, binding, 0)
        self.assertNotEqual(different, payload)
        points.append(make_point(1, 1010, 120))
        extended = trace.encode_payload(points, binding, 0)
        self.assertEqual(len(trace.decode_payload(extended, BINDING)['points']),
                         2)

    def test_decoded_records_are_detached(self):
        payload = trace.encode_payload(
            [make_point(0, 1000, 100), make_point(1, 1010, 110)], BINDING, 1)
        first = trace.decode_payload(payload, BINDING)
        first['points'].clear()
        first['ledger']['count'] = 999
        first['points'] = None
        second = trace.decode_payload(payload, BINDING)
        self.assertEqual(len(second['points']), 2)
        self.assertEqual(second['ledger']['count'], 2)
        second['points'][0]['value'] = 5
        second['ledger']['selected_raw_bytes'] = 0
        third = trace.decode_payload(payload, BINDING)
        self.assertEqual(third['points'][0]['value'], 100)
        self.assertEqual(third['ledger']['selected_raw_bytes'], 4)

    def test_manual_vectors_are_not_mutated_by_round_trip(self):
        vectors = load_vectors()['manual_vectors']['vectors']
        before = json.dumps(vectors, sort_keys=True)
        for vector in vectors:
            trace.decode_payload(bytes.fromhex(vector['payload_hex']),
                                 vector['binding'])
            trace.encode_payload(vector['points'], vector['binding'],
                                 vector['channel'])
        self.assertEqual(json.dumps(vectors, sort_keys=True), before)
