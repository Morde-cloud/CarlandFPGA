'''Bounded correction tests: TC01 two-stage k selection, TC02 short-age bound.

Task DEEPEYE-IMPLEMENTATION-20261014/v1; work
B-TRACE-CANONICAL-SOURCEAGE-CORRECTION-20261017-01-v1.  These checks cover the
two B main findings against the offline candidate serializer and are
design-time software checks only: no transport, board, compression, latency or
system acceptance claim is made.  The TC01 expected frame and the TC02
underflow frame below are copied verbatim from the parent portable regression
check (check_trace_regressions.py); they are never derived from this module.

Run from the worktree root:
  python -B -m unittest discover -s competition/deepeye/tests/codec -p test_trace_corrections.py -v
'''

import binascii
import json
import pathlib
import sys
import unittest

_HERE = pathlib.Path(__file__).resolve()
_DEEPEYE = _HERE.parents[2]
sys.path.insert(0, str(_DEEPEYE / 'golden' / 'codec'))

import codec_reference as inner  # noqa: E402
import trace_candidate as trace  # noqa: E402

VECTORS_PATH = _DEEPEYE / 'golden' / 'codec' / 'trace_candidate_vectors.json'

BINDING = {'session': 0x01020304, 'config_epoch': 2, 'e': 0}
TC01_BINDING = {'session': 1, 'config_epoch': 0, 'e': 0}

TC01_EXPECTED_FRAME = bytes.fromhex(
    'a55a03071d00000000000000011004041a0100000000000000000000000000000001000a0010274880a94b')
TC02_UNDERFLOW_FRAME = bytes.fromhex(
    'a55a030719020900e803000001081401100403020107000000e803000000000000e9036400a811')


def make_point(index, tick, value, held_origin=None):
    source = held_origin if held_origin is not None else tick
    return {'index': index, 'tick_ms': tick, 'value': value, 'valid': True,
            'saturated': False, 'held': held_origin is not None,
            'source_fault': False, 'source_tick_ms': source}


def residual_z(values, e):
    step = 2 * e + 1
    zs = []
    previous = values[0]
    for value in values[1:]:
        quotient = (value - previous + e) // step
        zs.append(2 * quotient if quotient >= 0 else -2 * quotient - 1)
        previous = previous + quotient * step
        if previous > 65535:
            previous = 65535
        elif previous < 0:
            previous = 0
    return zs


def two_stage_oracle(zs):
    '''Main-corrected rule: fewest significant bits (lowest k on ties), then
    stored bytes with RAW winning byte ties.'''
    best = None
    count = len(zs) + 1
    for k in range(16):
        total = 0
        for z in zs:
            if z >> k > 31:
                break
            total += (z >> k) + 1 + k
        else:
            bits = 16 + total
            if best is None or bits < best[0]:
                best = (bits, k)
    bits, k = best
    if (bits + 7) // 8 >= 2 * count:
        return ('raw', 0, 16 * count)
    return ('rice', k, bits)


def byte_min_oracle(zs):
    '''Rejected original rule: fewest stored bytes over k, then RAW on a tie.'''
    best = None
    count = len(zs) + 1
    for k in range(16):
        total = 0
        for z in zs:
            if z >> k > 31:
                break
            total += (z >> k) + 1 + k
        else:
            bits = 16 + total
            stored = (bits + 7) // 8
            if best is None or stored < best[0]:
                best = (stored, k, bits)
    stored, k, bits = best
    if stored >= 2 * count:
        return ('raw', 0, 16 * count)
    return ('rice', k, bits)


def patch_short_held(frame, first_tick, age):
    '''Rewrite first tick and short age in one encoded held-short frame.'''
    data = bytearray(frame)
    data[25:33] = first_tick.to_bytes(8, 'little')
    data[33:35] = age.to_bytes(2, 'little')
    data[8:12] = (first_tick & 0xFFFFFFFF).to_bytes(4, 'little')
    data[-2:] = binascii.crc_hqx(bytes(data[2:-2]), 0xFFFF).to_bytes(2, 'little')
    return bytes(data)


class TwoStageSelectionTests(unittest.TestCase):
    '''TC01: Rice k by minimum significant bits, then stored-byte mode check.'''

    def test_tc01_main_hand_derived_frame(self):
        values = [10000, 10001, 10002, 10004]
        points = [make_point(i, i * 10, v) for i, v in enumerate(values)]
        frame = trace.encode_frame(points, TC01_BINDING, 0, 0)
        self.assertEqual(frame, TC01_EXPECTED_FRAME)
        record = trace.decode_frame(TC01_EXPECTED_FRAME, TC01_BINDING)
        self.assertEqual(record['mode'], 'rice')
        self.assertEqual(record['k'], 1)
        self.assertEqual(record['significant_bits'], 26)
        self.assertEqual(record['ledger']['stored_code_bytes'], 4)
        self.assertEqual(record['ledger']['padding_bits'], 6)
        self.assertEqual(record['ledger']['payload_bytes'], 29)
        self.assertEqual(record['ledger']['frame_bytes'], 43)

    def test_family_equal_padded_bytes_distinct_bits(self):
        families = [
            ('tc01_manual_case', [10000, 10001, 10002, 10004], 0),
            ('padded_tie_k2_vs_k3', [0, 8, 16], 0),
            ('padded_tie_k8_vs_k9', [0, 500, 1000], 0),
            ('padded_tie_k11_plus', [0, 4096, 8192], 0),
            ('agreeing_flat', [100, 100, 100], 1),
        ]
        for name, values, e in families:
            with self.subTest(name=name):
                zs = residual_z(values, e)
                expected = two_stage_oracle(zs)
                bind = dict(BINDING, e=e)
                points = [make_point(i, i * 10, v) for i, v in enumerate(values)]
                record = trace.decode_payload(
                    trace.encode_payload(points, bind, 0), bind)
                self.assertEqual((record['mode'], record['k'],
                                  record['significant_bits']), expected)
        for values, e in (([10000, 10001, 10002, 10004], 0),
                          ([0, 8, 16], 0),
                          ([0, 500, 1000], 0)):
            with self.subTest(discriminating=values):
                zs = residual_z(values, e)
                self.assertNotEqual(two_stage_oracle(zs), byte_min_oracle(zs))

    def test_inner_codec_k_agrees_when_rice_is_kept(self):
        cases = [([10000, 10001, 10002, 10004], 0),
                 ([0, 8, 16], 0),
                 ([0, 500, 1000], 0),
                 ([0, 4096, 8192], 0),
                 ([100, 100, 100], 1),
                 ([1000 + i * 3 for i in range(8)], 2),
                 ([0, 64], 0),
                 ([0, 2048, 4096], 0)]
        for values, e in cases:
            with self.subTest(values=values, e=e):
                bind = dict(BINDING, e=e)
                points = [make_point(i, i * 10, v) for i, v in enumerate(values)]
                record = trace.decode_payload(
                    trace.encode_payload(points, bind, 0), bind)
                fixture = inner.encode_block(values, e)
                if record['mode'] == 'rice':
                    self.assertEqual(fixture['mode'], 'rice')
                    self.assertEqual(fixture['k'], record['k'])
                    self.assertEqual(fixture['valid_bit_count'],
                                     record['significant_bits'])
                elif fixture['mode'] == 'rice':
                    # Documented byte-tie difference: RAW is stored although
                    # the inner bit rule keeps Rice; stored bytes coincide.
                    self.assertEqual((fixture['valid_bit_count'] + 7) // 8,
                                     record['ledger']['selected_raw_bytes'])


class ShortAgeUnderflowTests(unittest.TestCase):
    '''TC02: short held age must satisfy 1 <= age <= first_tick.'''

    def setUp(self):
        self.base = trace.encode_frame(
            [make_point(7, 1000, 5, held_origin=900)], BINDING, 0, 9)
        self.base_payload = trace.encode_payload(
            [make_point(7, 1000, 5, held_origin=900)], BINDING, 0)

    def test_tc02_main_underflow_frame_rejected(self):
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_frame(TC02_UNDERFLOW_FRAME, BINDING)
        self.assertIn('exceeds the first tick', str(context.exception))
        with self.assertRaises(trace.TraceError):
            trace.decode_payload(TC02_UNDERFLOW_FRAME[12:-2], BINDING)

    def test_age_above_tick_rejected_without_receiver_state_change(self):
        receiver = trace.TraceReceiver(BINDING)
        good = trace.encode_frame([make_point(0, 10, 7)], BINDING, 0, 5)
        receiver.accept(good)
        before = receiver.state_snapshot()
        with self.assertRaises(trace.TraceError):
            receiver.accept(TC02_UNDERFLOW_FRAME)
        self.assertEqual(receiver.state_snapshot(), before)
        self.assertEqual([seq for seq, _ in before['packet_cache']], [5])
        later = trace.encode_frame([make_point(5, 30, 8)], BINDING, 0, 10)
        self.assertEqual(receiver.accept(later)['status'], 'ok')

    def test_tick_zero_age_one_rejected(self):
        crafted = patch_short_held(self.base, 0, 1)
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_frame(crafted, BINDING)
        self.assertIn('exceeds the first tick', str(context.exception))
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_payload(crafted[12:-2], BINDING)
        self.assertIn('exceeds the first tick', str(context.exception))

    def test_age_equal_to_tick_allows_source_zero(self):
        for first_tick, age in ((1000, 1000), (65535, 65535)):
            with self.subTest(first_tick=first_tick):
                crafted = patch_short_held(self.base, first_tick, age)
                record = trace.decode_frame(crafted, BINDING)
                self.assertFalse(record['long_source_tick'])
                self.assertEqual(record['held_origin_tick_ms'], 0)
                self.assertEqual(record['points'][0]['source_tick_ms'], 0)
        encoded = trace.decode_payload(
            trace.encode_payload([make_point(7, 1000, 5, held_origin=0)],
                                 BINDING, 0), BINDING)
        self.assertEqual(encoded['held_origin_tick_ms'], 0)

    def test_short_max_age_and_canonical_long_age(self):
        short_payload = trace.encode_payload(
            [make_point(7, 65535, 5, held_origin=0)], BINDING, 0)
        self.assertEqual(len(short_payload), 25)
        short_record = trace.decode_payload(short_payload, BINDING)
        self.assertFalse(short_record['long_source_tick'])
        self.assertEqual(short_record['held_origin_tick_ms'], 0)
        long_payload = trace.encode_payload(
            [make_point(7, 65536, 5, held_origin=0)], BINDING, 0)
        self.assertEqual(len(long_payload), 31)
        long_record = trace.decode_payload(long_payload, BINDING)
        self.assertTrue(long_record['long_source_tick'])
        self.assertEqual(long_record['held_origin_tick_ms'], 0)

    def test_underflow_payload_rejected(self):
        payload = bytearray(self.base_payload)
        self.assertEqual(payload[13:21], (1000).to_bytes(8, 'little'))
        payload[21:23] = (1001).to_bytes(2, 'little')
        with self.assertRaises(trace.TraceError) as context:
            trace.decode_payload(bytes(payload), BINDING)
        self.assertIn('exceeds the first tick', str(context.exception))


class CorrectionsVectorTests(unittest.TestCase):
    '''The committed vectors carry the correction fixtures.'''

    def test_committed_vectors_include_tc01_and_tc02_fixtures(self):
        document = json.loads(VECTORS_PATH.read_text(encoding='utf-8'))
        synthetic = {entry['id']: entry
                     for entry in document['synthetic_vectors']}
        self.assertEqual(
            bytes.fromhex(synthetic['canonical_k_tc01_manual_expected']
                          ['frames_hex'][0]), TC01_EXPECTED_FRAME)
        frames = {entry['id']: entry
                  for entry in document['malformed_frames']}
        self.assertEqual(
            bytes.fromhex(frames['f10_short_age_exceeds_tick_main']
                          ['frame_hex']), TC02_UNDERFLOW_FRAME)
        self.assertIn('exceeds the first tick',
                      frames['f10_short_age_exceeds_tick_main']
                      ['expect_error_contains'])
        payloads = {entry['id']: entry
                    for entry in document['malformed_payloads']}
        self.assertIn('exceeds the first tick',
                      payloads['m23_short_age_exceeds_payload_tick']
                      ['expect_error_contains'])


if __name__ == '__main__':
    unittest.main()
