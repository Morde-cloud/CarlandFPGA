'''Unit tests for the candidate integer inner-codec foundation (candidate only).

Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Work: B-CODEC-INTEGER-FOUNDATION-20261015-01-v1
Correction: B-CODEC-BYTE-ACCOUNTING-CORRECTION-20261016-02-v1 (payload
accounting regression tests).

Run from the worktree root:
  python -B -m unittest discover -s competition/deepeye/tests/codec -v

These are design-time software checks for the B-side candidate inner codec.
They define no TRACE byte layout and make no board, timing, interoperability
or acceptance claim.
'''

import argparse
import contextlib
import io
import json
import pathlib
import random
import sys
import tempfile
import unittest

_HERE = pathlib.Path(__file__).resolve()
_DEEPEYE = _HERE.parents[2]
sys.path.insert(0, str(_DEEPEYE / 'golden' / 'codec'))
sys.path.insert(0, str(_DEEPEYE / 'tools'))

import codec_reference as codec  # noqa: E402
import verify_codec_candidate as verifier  # noqa: E402

VECTORS_PATH = _DEEPEYE / 'golden' / 'codec' / 'known_vectors.json'


def scalar_oracle(samples, e):
    '''Independent scalar oracle, re-implemented here from the candidate rules.

    It never calls the codec module, so decoded streams are checked against a
    second implementation of the reconstruction rule, not a round trip only.
    '''
    step = 2 * e + 1
    decoded = [samples[0]]
    previous = samples[0]
    for x in samples[1:]:
        quotient = (x - previous + e) // step
        value = previous + quotient * step
        if value > 65535:
            value = 65535
        elif value < 0:
            value = 0
        decoded.append(value)
        previous = value
    return decoded


def expected_for_block(samples, e, fixture):
    '''Independent expectation: RAW is lossless, RICE follows the oracle.'''
    if fixture['mode'] == 'raw':
        return list(samples)
    return scalar_oracle(samples, e)


def load_vectors():
    return json.loads(VECTORS_PATH.read_text(encoding='utf-8'))


class SampleValidationTests(unittest.TestCase):
    def test_rejects_bool_samples(self):
        for bad in ([True], [0, False], [1, True, 2]):
            with self.assertRaises(codec.CodecError):
                codec.encode_block(bad, 0)

    def test_rejects_non_int_samples(self):
        for bad in ([1.0], ['5'], [None], [0, 2.5, 3]):
            with self.assertRaises(codec.CodecError):
                codec.encode_block(bad, 0)

    def test_rejects_out_of_range_samples(self):
        for bad in ([-1], [65536], [0, 70000], [4000000000]):
            with self.assertRaises(codec.CodecError):
                codec.encode_block(bad, 0)

    def test_rejects_empty_and_oversized_blocks(self):
        with self.assertRaises(codec.CodecError):
            codec.encode_block([], 0)
        with self.assertRaises(codec.CodecError):
            codec.encode_block([0] * 129, 0)

    def test_accepts_block_length_boundaries(self):
        block = [1234] * 128
        fixture = codec.encode_block(block, 0)
        self.assertEqual(fixture['sample_count'], 128)
        self.assertEqual(codec.decode_block(codec.encode_block([0], 0)), [0])
        self.assertEqual(codec.decode_block(codec.encode_block([65535], 0)), [65535])

    def test_rejects_illegal_e(self):
        for bad in (-1, 3, 5, 16, 0.5, '0', True, None):
            with self.assertRaises(codec.CodecError):
                codec.encode_block([0, 1], bad)

    def test_rejects_non_sequence_samples(self):
        for bad in ('0102', b'0102', 123, {'a': 1}):
            with self.assertRaises(codec.CodecError):
                codec.encode_block(bad, 0)


class StructuralTests(unittest.TestCase):
    def test_fixture_records_exactly_the_candidate_fields(self):
        fixture = codec.encode_block([100, 101, 100, 99], 0)
        self.assertEqual(sorted(fixture.keys()),
                         ['e', 'k', 'mode', 'payload_hex', 'sample_count',
                          'valid_bit_count'])

    def test_anchor_is_the_exact_original_first_sample(self):
        for samples in ([0], [65535], [0, 1, 2], [65535, 65534, 0, 65535]):
            for e in codec.E_VALUES:
                fixture = codec.encode_block(samples, e)
                payload = bytes.fromhex(fixture['payload_hex'])
                self.assertEqual(int.from_bytes(payload[:2], 'big'), samples[0])

    def test_raw_payload_is_the_original_sample_bytes(self):
        for samples in ([0, 65535], [0, 65535, 0, 65535], verifier.noisy_samples()):
            fixture = codec.encode_block(samples, 0)
            self.assertEqual(fixture['mode'], 'raw')
            self.assertIsNone(fixture['k'])
            self.assertEqual(fixture['valid_bit_count'], 16 * len(samples))
            expected = b''.join(value.to_bytes(2, 'big') for value in samples)
            self.assertEqual(bytes.fromhex(fixture['payload_hex']), expected)
            self.assertEqual(codec.decode_block(fixture), samples)

    def test_unused_final_bits_are_zero_and_payload_is_minimal(self):
        fixtures = [
            codec.encode_block([0, 1, 2], 0),
            codec.encode_block([10, 0], 4),
            codec.encode_block([65535, 0, 12345], 8),
            codec.encode_block([0, 65535], 0),
        ]
        for fixture in fixtures:
            payload = bytes.fromhex(fixture['payload_hex'])
            valid = fixture['valid_bit_count']
            self.assertEqual((valid + 7) // 8, len(payload))
            for position in range(valid, 8 * len(payload)):
                bit = (payload[position >> 3] >> (7 - (position & 7))) & 1
                self.assertEqual(bit, 0)

    def test_predictor_resets_at_block_boundaries(self):
        for e in codec.E_VALUES:
            late = codec.encode_block([65535, 0, 30000], e)
            part = codec.split_blocks([0, 1, 2, 65535, 0, 30000], 3)[1]
            self.assertEqual(codec.encode_block(part, e), late)

    def test_blocks_decode_without_earlier_block_state(self):
        stream = [0, 1, 2, 65535, 0, 30000, 5, 5, 5]
        for e in codec.E_VALUES:
            blocks = codec.split_blocks(stream, 3)
            fixtures = [codec.encode_block(block, e) for block in blocks]
            decoded = codec.decode_blocks(fixtures)
            expected = []
            for block, fixture in zip(blocks, fixtures):
                expected.extend(expected_for_block(block, e, fixture))
            self.assertEqual(decoded, expected)

    def test_e0_is_lossless_for_seeded_blocks(self):
        rng = random.Random(4242)
        for _ in range(25):
            block = [rng.getrandbits(16) for _ in range(rng.randint(1, 128))]
            self.assertEqual(codec.decode_block(codec.encode_block(block, 0)), block)

    def test_raw_fallback_is_selected_and_lossless_for_big_steps(self):
        for samples, e in (([0, 65535], 0), ([0, 65535], 1), ([0, 65535], 2),
                           ([0, 65535, 0, 65535], 2)):
            fixture = codec.encode_block(samples, e)
            self.assertEqual(fixture['mode'], 'raw', samples)
            self.assertEqual(codec.decode_block(fixture), samples)


class SelectionPolicyTests(unittest.TestCase):
    def test_ties_choose_the_lowest_k(self):
        selection = codec.select_body_encoding([2, 2])
        self.assertEqual(selection['mode'], 'rice')
        self.assertEqual(selection['k'], 0)
        self.assertEqual(selection['body_bits'], 6)

    def test_raw_wins_a_tie_against_rice(self):
        selection = codec.select_body_encoding([26214])
        self.assertEqual(selection['mode'], 'raw')
        self.assertEqual(selection['best_rice_bits'], 16)

    def test_raw_is_chosen_when_rice_is_worse(self):
        selection = codec.select_body_encoding([131070])
        self.assertEqual(selection['mode'], 'raw')
        self.assertEqual(selection['best_rice_bits'], 19)

    def test_raw_is_chosen_when_no_k_is_legal(self):
        selection = codec.select_body_encoding([1 << 20])
        self.assertEqual(selection['mode'], 'raw')
        self.assertEqual(selection['legal_k'], [])
        self.assertIsNone(selection['best_rice_bits'])

    def test_quotient_cap_excludes_illegal_k_values(self):
        selection = codec.select_body_encoding([5000])
        self.assertEqual(selection['legal_k'], list(range(8, 16)))
        self.assertNotIn(7, selection['legal_k'])
        self.assertEqual(selection['k'], 11)
        self.assertEqual(selection['body_bits'], 14)

    def test_zigzag_known_values(self):
        cases = ((0, 0), (1, 2), (-1, 1), (2, 4), (-2, 3),
                 (65535, 131070), (-65535, 131069))
        for q, z in cases:
            self.assertEqual(codec.zigzag(q), z)
            self.assertEqual(codec.unzigzag(z), q)

    def test_zigzag_roundtrip(self):
        for q in range(-70000, 70001, 7):
            self.assertEqual(codec.unzigzag(codec.zigzag(q)), q)
            self.assertGreaterEqual(codec.zigzag(q), 0)

    def test_floor_division_quantization_and_saturation(self):
        cases = (
            ([10, 0], 0, [10, 0]),
            ([10, 0], 1, [10, 1]),
            ([10, 0], 2, [10, 0]),
            ([10, 0], 4, [10, 1]),
            ([10, 0], 8, [10, 0]),
            ([65530, 1], 8, [65530, 0]),
        )
        for samples, e, expected in cases:
            self.assertEqual(scalar_oracle(samples, e), expected)
            self.assertEqual(codec.decode_block(codec.encode_block(samples, e)),
                             expected)


class KnownVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = load_vectors()

    def test_vectors_file_is_reproducible_from_the_builder(self):
        self.assertEqual(self.vectors, verifier.build_vectors())

    def test_hand_vectors_match_frozen_fixture_and_expectation(self):
        for entry in self.vectors['hand_vectors']:
            samples = entry['samples']
            e = entry['e']
            fixture = entry['fixture']
            self.assertEqual(codec.encode_block(samples, e), fixture)
            decoded = codec.decode_block(fixture)
            self.assertEqual(decoded, entry['decoded'])
            self.assertEqual(decoded, expected_for_block(samples, e, fixture))
            self.assertEqual(entry['max_abs_error'],
                             max(abs(a - b) for a, b in zip(samples, decoded)))

    def test_raw_step_examples_select_raw_for_e0_e1_e2(self):
        for entry in self.vectors['raw_step_examples']:
            fixture = entry['fixture']
            self.assertEqual(codec.encode_block(entry['samples'], entry['e']), fixture)
            if entry['e'] in (0, 1, 2):
                self.assertEqual(fixture['mode'], 'raw', entry['id'])
            if fixture['mode'] == 'raw':
                self.assertEqual(codec.decode_block(fixture), entry['samples'])

    def test_noisy_example_is_raw_at_e0(self):
        entries = self.vectors['raw_noisy_examples']
        self.assertEqual(entries[0]['e'], 0)
        self.assertEqual(entries[0]['fixture']['mode'], 'raw')
        self.assertEqual(codec.decode_block(entries[0]['fixture']),
                         entries[0]['samples'])
        for entry in entries:
            self.assertEqual(codec.encode_block(entry['samples'], entry['e']),
                             entry['fixture'])

    def test_e0_vectors_are_lossless_against_the_original_samples(self):
        for collection in ('hand_vectors', 'raw_step_examples',
                           'raw_noisy_examples'):
            for entry in self.vectors[collection]:
                if entry['e'] == 0:
                    self.assertEqual(entry['decoded'], entry['samples'], entry['id'])


class FixtureRejectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = load_vectors()

    def test_every_malformed_vector_is_rejected_with_its_category(self):
        for case in self.vectors['malformed']:
            with self.assertRaises(codec.CodecError) as caught:
                codec.decode_block(case['fixture'])
            self.assertIn(case['expected_error_contains'], str(caught.exception),
                          case['id'])

    def test_decoder_rejects_non_dict_fixtures(self):
        for bad in (None, [], 'fixture', 7, 3.5):
            with self.assertRaises(codec.CodecError):
                codec.decode_block(bad)

    def test_decoder_rejects_missing_fixture_fields(self):
        base = codec.encode_block([0, 1, 2], 0)
        for key in list(base):
            fixture = dict(base)
            del fixture[key]
            with self.assertRaises(codec.CodecError, msg=key):
                codec.decode_block(fixture)

    def test_decoder_rejects_wrong_typed_fields(self):
        base = codec.encode_block([0, 1, 2], 0)
        for key, bad in (('mode', 7), ('e', '0'), ('k', '0'), ('sample_count', '3'),
                         ('valid_bit_count', '22'), ('payload_hex', 123)):
            fixture = dict(base)
            fixture[key] = bad
            with self.assertRaises(codec.CodecError, msg=key):
                codec.decode_block(fixture)


class NextBlockRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recovery = load_vectors()['next_block_recovery']

    def test_each_recovery_block_decodes_standalone_to_its_expectation(self):
        for block in self.recovery['blocks']:
            decoded = codec.decode_block(block['fixture'])
            self.assertEqual(decoded, block['decoded'])
            self.assertEqual(decoded, expected_for_block(block['samples'], block['e'],
                                                         block['fixture']))

    def test_valid_block_after_a_malformed_block_still_decodes(self):
        sequence = self.recovery['interleaved']['sequence']
        outcomes = []
        for fixture in sequence:
            try:
                codec.decode_block(fixture)
                outcomes.append('ok')
            except codec.CodecError:
                outcomes.append('reject')
        self.assertEqual(outcomes, ['ok', 'reject', 'ok'])
        self.assertEqual(codec.decode_block(sequence[2]),
                         codec.decode_block(self.recovery['blocks'][1]['fixture']))

    def test_recovery_does_not_need_any_earlier_block(self):
        later = self.recovery['blocks'][1]
        decoded_alone = codec.decode_block(later['fixture'])
        self.assertEqual(decoded_alone, later['decoded'])
        self.assertEqual(decoded_alone[0], later['samples'][0])


class RandomOracleAgreementTests(unittest.TestCase):
    def test_random_blocks_agree_with_the_independent_expectation(self):
        rng = random.Random(20261014)
        for e in codec.E_VALUES:
            for _ in range(150):
                size = rng.randint(1, 128)
                block = [rng.getrandbits(16) for _ in range(size)]
                fixture = codec.encode_block(block, e)
                decoded = codec.decode_block(fixture)
                self.assertEqual(decoded, expected_for_block(block, e, fixture))
                for original, value in zip(block, decoded):
                    self.assertLessEqual(abs(original - value), e)

    def test_error_bound_holds_over_a_seeded_stream(self):
        rng = random.Random(777)
        stream = [rng.getrandbits(16) for _ in range(5000)]
        for e in codec.E_VALUES:
            fixtures = codec.encode_blocks(stream, e, block_len=128)
            decoded = codec.decode_blocks(fixtures)
            self.assertEqual(len(decoded), len(stream))
            for original, value in zip(stream, decoded):
                self.assertLessEqual(abs(original - value), e)
            if e == 0:
                self.assertEqual(decoded, stream)

    def test_structured_patterns_agree_with_the_expectation(self):
        patterns = {
            'all_min': [0] * 128,
            'all_max': [65535] * 128,
            'plateau': [100] * 128,
            'alternating': [0, 65535] * 64,
            'ramp': [index % 65536 for index in range(128)],
            'sawtooth': [(index * 257) % 65536 for index in range(128)],
            'step_edges': [0] * 64 + [65535] * 64,
            'single_spike': [0] * 64 + [65535] + [0] * 63,
        }
        for name, block in patterns.items():
            for e in codec.E_VALUES:
                fixture = codec.encode_block(block, e)
                decoded = codec.decode_block(fixture)
                self.assertEqual(decoded, expected_for_block(block, e, fixture),
                                 name)


class BlockSplitTests(unittest.TestCase):
    def test_split_sizes_and_merge_roundtrip(self):
        stream = [index % 65536 for index in range(300)]
        for e in codec.E_VALUES:
            blocks = codec.split_blocks(stream, block_len=128)
            self.assertEqual([len(block) for block in blocks], [128, 128, 44])
            fixtures = [codec.encode_block(block, e) for block in blocks]
            decoded = codec.decode_blocks(fixtures)
            expected = []
            for block, fixture in zip(blocks, fixtures):
                expected.extend(expected_for_block(block, e, fixture))
            self.assertEqual(decoded, expected)

    def test_block_len_validation(self):
        for bad in (0, 129, True, '128'):
            with self.assertRaises(codec.CodecError):
                codec.split_blocks([0, 1], bad)
        self.assertEqual(len(codec.split_blocks([0] * 128, 128)), 1)

    def test_sample_sequence_validation(self):
        with self.assertRaises(codec.CodecError):
            codec.split_blocks([], 128)
        with self.assertRaises(codec.CodecError):
            codec.split_blocks([True], 128)
        with self.assertRaises(codec.CodecError):
            codec.encode_blocks([0, 70000], 0)

    def test_decode_blocks_rejects_non_sequence_input(self):
        for bad in (None, 'x', 5):
            with self.assertRaises(codec.CodecError):
                codec.decode_blocks(bad)


class PayloadAccountingTests(unittest.TestCase):
    '''Aggregate accounting must sum independently padded block payloads.

    Regression for B-CODEC-COUNT01: a stored block payload is
    ceil(valid_bit_count / 8) bytes with its own final-byte zero padding, so
    aggregating over independent blocks sums the per-block payload lengths
    instead of rounding the summed bit count once.
    '''

    def test_two_independent_17_bit_blocks_are_not_rounded_together(self):
        fixtures = [codec.encode_block([100, 100], 0),
                    codec.encode_block([100, 100], 0)]
        for fixture in fixtures:
            self.assertEqual(fixture['valid_bit_count'], 17)
            self.assertEqual(len(bytes.fromhex(fixture['payload_hex'])), 3)
        summary = verifier.accounting_summary(fixtures)
        self.assertEqual(summary['inner_codec_body_bits'], 34)
        self.assertEqual(summary['inner_codec_stored_bytes'], 6)
        self.assertEqual(summary['inner_codec_padding_bits'], 14)
        self.assertEqual((summary['inner_codec_body_bits'] + 7) // 8, 5)
        self.assertNotEqual(summary['inner_codec_stored_bytes'], 5)

    def test_per_block_ceiling_is_valid_for_every_independent_block(self):
        rng = random.Random(515)
        for e in codec.E_VALUES:
            for _ in range(10):
                block = [rng.getrandbits(16) for _ in range(rng.randint(1, 128))]
                fixture = codec.encode_block(block, e)
                payload_bytes = len(bytes.fromhex(fixture['payload_hex']))
                self.assertEqual(payload_bytes, (fixture['valid_bit_count'] + 7) // 8)
                summary = verifier.accounting_summary([fixture])
                self.assertEqual(summary['inner_codec_stored_bytes'], payload_bytes)
                self.assertEqual(summary['inner_codec_padding_bits'],
                                 8 * payload_bytes - fixture['valid_bit_count'])

    def test_raw_blocks_account_exactly_without_padding(self):
        for samples in ([0, 65535], [0, 65535, 0, 65535]):
            fixture = codec.encode_block(samples, 0)
            self.assertEqual(fixture['mode'], 'raw')
            summary = verifier.accounting_summary([fixture])
            self.assertEqual(summary['inner_codec_body_bits'], 16 * len(samples))
            self.assertEqual(summary['inner_codec_stored_bytes'], 2 * len(samples))
            self.assertEqual(summary['inner_codec_padding_bits'], 0)

    def test_singleton_anchor_blocks_account_exactly(self):
        fixtures = [codec.encode_block([value], 0) for value in (0, 100, 65535)]
        summary = verifier.accounting_summary(fixtures)
        self.assertEqual(summary['inner_codec_body_bits'], 48)
        self.assertEqual(summary['inner_codec_stored_bytes'], 6)
        self.assertEqual(summary['inner_codec_padding_bits'], 0)
        self.assertEqual(codec.decode_blocks(fixtures), [0, 100, 65535])

    def test_partial_final_block_is_counted_with_its_own_bytes(self):
        stream = [index % 65536 for index in range(300)]
        for e in codec.E_VALUES:
            blocks = codec.split_blocks(stream, 128)
            self.assertEqual([len(block) for block in blocks], [128, 128, 44])
            fixtures = [codec.encode_block(block, e) for block in blocks]
            summary = verifier.accounting_summary(fixtures)
            expected_bytes = sum(len(bytes.fromhex(fixture['payload_hex']))
                                 for fixture in fixtures)
            self.assertEqual(summary['inner_codec_stored_bytes'], expected_bytes)
            self.assertEqual(summary['inner_codec_body_bits'],
                             sum(fixture['valid_bit_count'] for fixture in fixtures))
            self.assertEqual(summary['inner_codec_padding_bits'],
                             8 * expected_bytes - summary['inner_codec_body_bits'])

    def test_all_e_aggregate_matches_sum_of_block_payloads(self):
        rng = random.Random(20261016)
        stream = [rng.getrandbits(16) for _ in range(777)]
        for e in codec.E_VALUES:
            fixtures = codec.encode_blocks(stream, e, block_len=64)
            summary = verifier.accounting_summary(fixtures)
            self.assertEqual(summary['inner_codec_stored_bytes'],
                             sum(len(bytes.fromhex(fixture['payload_hex']))
                                 for fixture in fixtures))
            self.assertEqual(summary['inner_codec_padding_bits'],
                             8 * summary['inner_codec_stored_bytes']
                             - summary['inner_codec_body_bits'])
            if e == 0:
                self.assertEqual(codec.decode_blocks(fixtures), stream)

    def test_run_million_records_the_sum_of_payload_lengths(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / 'run_small.json'
            args = argparse.Namespace(samples=257, seed=20261014, block_len=128,
                                      json_out=str(out))
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exit_code = verifier.cmd_run_million(args)
            self.assertEqual(exit_code, 0)
            result = json.loads(out.read_text(encoding='utf-8'))
        self.assertIn('stored_bytes=', buffer.getvalue())
        rng = random.Random(20261014)
        samples = [rng.getrandbits(16) for _ in range(257)]
        blocks = codec.split_blocks(samples, 128)
        self.assertEqual(result['block_count'], 3)
        self.assertEqual(result['last_block_len'], 1)
        for key, entry in result['per_e'].items():
            fixtures = [codec.encode_block(block, int(key)) for block in blocks]
            stored = sum(len(bytes.fromhex(fixture['payload_hex']))
                         for fixture in fixtures)
            bits = sum(fixture['valid_bit_count'] for fixture in fixtures)
            self.assertEqual(entry['inner_codec_body_bits'], bits)
            self.assertEqual(entry['inner_codec_stored_bytes'], stored)
            self.assertEqual(entry['inner_codec_padding_bits'], 8 * stored - bits)
            self.assertNotIn('inner_codec_body_bytes', entry)


if __name__ == '__main__':
    unittest.main()
