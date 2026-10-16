'''Candidate verifier for the DeepEye integer inner-codec foundation.

Work: B-CODEC-INTEGER-FOUNDATION-20261015-01-v1
Correction: B-CODEC-BYTE-ACCOUNTING-CORRECTION-20261016-02-v1 (aggregate
byte accounting only; see the Byte accounting paragraph below).
Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15).

Candidate-only tool.  It builds the deterministic candidate vector file,
verifies vectors plus every rejection case, and runs the deterministic
1,000,000-sample check (seed 20261014).  It defines no TRACE byte layout and
makes no compression, latency, interoperability or acceptance claim.

Byte accounting: one stored block payload is ceil(valid_bit_count / 8) bytes
including the zero padding of its final byte, so that ceiling formula is valid
per block only.  An aggregate stored-byte count is the sum of the
independently padded block payload lengths (sum_i ceil(bits_i / 8)); it is not
ceil(sum_i bits_i / 8), which would describe one continuous bitstream.  The
run-million result exposes exact valid bits, stored bytes and padding bits
separately.

Commands:
  emit-vectors  --out PATH      write the deterministic candidate vector file
  check-vectors --vectors PATH  verify vectors, rejections and block recovery
  run-million   --samples N --seed S --block-len L [--json-out PATH]

Exit codes: 0 ok, 1 verification failure, 2 usage error.
'''

import argparse
import hashlib
import json
import pathlib
import platform
import random
import sys

_HERE = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[1] / 'golden' / 'codec'))
import codec_reference as codec  # noqa: E402

TASK = {'task_id': 'DEEPEYE-IMPLEMENTATION-20261014', 'task_version': 1}
WORK_ID = 'B-CODEC-INTEGER-FOUNDATION-20261015-01-v1'
CONTRACT = {
    'contract': 'DEEPEYE-HUMAN-LOCK-20261014',
    'revision': 1,
    'requirements_ids': ['H%02d' % index for index in range(1, 16)],
    'requirements_sha256': 'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804',
    'contract_commit': 'f5989cd5defce561f9ba98e6b18fc2682945f0a2',
    'design_commit': '1011259415a0916054eb580687612580bc1e5f09',
}


def scalar_oracle(samples, e):
    '''Independent scalar oracle for the candidate reconstruction rule.

    Re-implemented from the candidate rules; it deliberately does not call
    the codec module, so encode/decode results are checked against a second
    implementation instead of a round trip only.
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


def expected_reconstruction(samples, e, mode):
    '''Independent expectation for one candidate block.

    RAW stores the original remaining samples, so a RAW block must
    reproduce the original samples exactly (lossless bypass).  A RICE block
    follows the scalar oracle reconstruction of the quantized residuals.
    '''
    if mode == 'raw':
        return list(samples)
    return scalar_oracle(samples, e)


def error_stats(samples, decoded):
    '''Per-sample error counters against the original x values.'''
    count = 0
    max_abs = 0
    total_abs = 0
    for original, value in zip(samples, decoded):
        error = abs(original - value)
        if error:
            count += 1
        if error > max_abs:
            max_abs = error
        total_abs += error
    return {'error_samples': count, 'max_abs_error': max_abs, 'sum_abs_error': total_abs}


def accounting_summary(fixtures):
    '''Aggregate stored-byte accounting over independent candidate blocks.

    Every block payload is stored with its own final-byte zero padding:
    stored bytes per block = ceil(valid_bit_count / 8).  The aggregate is
    the sum of those block payload lengths; it is not
    ceil(sum(valid_bit_count) / 8) of one continuous bitstream.
    '''
    body_bits = 0
    stored_bytes = 0
    for fixture in fixtures:
        valid_bit_count = fixture['valid_bit_count']
        payload_bytes = len(bytes.fromhex(fixture['payload_hex']))
        if payload_bytes != (valid_bit_count + 7) // 8:
            raise AssertionError('block payload is not a minimal stored block')
        body_bits += valid_bit_count
        stored_bytes += payload_bytes
    return {
        'inner_codec_body_bits': body_bits,
        'inner_codec_stored_bytes': stored_bytes,
        'inner_codec_padding_bits': 8 * stored_bytes - body_bits,
    }


def fixture_entry(entry_id, samples, e):
    '''Build one frozen vector entry (fixture + independently decoded values).'''
    fixture = codec.encode_block(samples, e)
    decoded = codec.decode_block(fixture)
    expected = expected_reconstruction(samples, e, fixture['mode'])
    if decoded != expected:
        raise SystemExit('fatal: decoder differs from the independent expectation '
                         'for %s' % entry_id)
    return {
        'id': entry_id,
        'samples': list(samples),
        'e': e,
        'fixture': fixture,
        'decoded': decoded,
        'max_abs_error': max(abs(a - b) for a, b in zip(samples, decoded)),
    }


HAND_VECTOR_SAMPLES = [
    ('hv01_zero_one_two', [0, 1, 2]),
    ('hv02_top_top_minus_one_zero_top', [65535, 65534, 0, 65535]),
    ('hv03_plateau', [100, 101, 100, 99]),
]

RAW_STEP_SAMPLES = [
    ('raw_step_0_to_max', [0, 65535]),
    ('raw_alternating_0_max', [0, 65535, 0, 65535]),
]


def noisy_samples(count=16):
    '''Deterministic messy full-range example (fixed LCG, 16 samples).'''
    state = 20261014
    values = []
    for _ in range(count):
        state = (state * 1103515245 + 12345) & 0xFFFFFFFF
        values.append((state >> 8) & 0xFFFF)
    return values


def build_malformed_vectors():
    '''Hand-built malformed fixtures derived from the [0,1,2] E=0 fixture.

    The base fixture is rice k=0, valid_bit_count=22, payload 000024
    (anchor 16 zero bits, two residuals 001 001, two zero padding bits).
    Every case must be rejected deterministically by decode_block.
    '''
    base = codec.encode_block([0, 1, 2], 0)
    rows = [
        ('m01_truncated_before_second_residual',
         {'valid_bit_count': 19, 'payload_hex': '000020'}, 'truncated'),
        ('m02_extra_bits_after_final_sample',
         {'valid_bit_count': 23}, 'extra bits'),
        ('m03_declared_count_too_small',
         {'sample_count': 2}, 'extra bits'),
        ('m04_nonzero_padding_bit',
         {'payload_hex': '000025'}, 'nonzero padding'),
        ('m05_excess_payload_bytes',
         {'payload_hex': '00002400'}, 'excess bytes'),
        ('m06_illegal_k_16',
         {'k': 16}, 'outside 0..15'),
        ('m07_rice_k_null',
         {'k': None}, 'k must be an int'),
        ('m08_illegal_e_3',
         {'e': 3}, 'not in'),
        ('m09_e_bool_true',
         {'e': True}, 'must be an int'),
        ('m10_sample_count_zero',
         {'sample_count': 0}, 'outside 1..'),
        ('m11_sample_count_129',
         {'sample_count': 129}, 'outside 1..'),
        ('m12_sample_count_bool',
         {'sample_count': True}, 'must be an int'),
        ('m13_valid_bits_below_anchor',
         {'valid_bit_count': 8, 'payload_hex': '00'}, 'anchor'),
        ('m14_valid_bits_above_payload',
         {'valid_bit_count': 25}, 'exceeds'),
        ('m15_empty_payload',
         {'valid_bit_count': 16, 'payload_hex': ''}, 'exceeds'),
        ('m16_odd_payload_hex_length',
         {'payload_hex': '00002'}, 'even number of digits'),
        ('m17_non_hex_payload_digit',
         {'payload_hex': '00002g'}, 'non-hex'),
        ('m18_bad_mode',
         {'mode': 'ricee'}, 'mode must be'),
        ('m19_valid_bit_count_bool',
         {'valid_bit_count': True}, 'must be an int'),
        ('m20_k_bool',
         {'k': True}, 'must be an int'),
    ]
    cases = []
    for case_id, patch, expected in rows:
        fixture = dict(base)
        fixture.update(patch)
        cases.append({'id': case_id, 'fixture': fixture,
                      'expected_error_contains': expected})
    cases.append({'id': 'm21_overlong_unary_32_zeroes',
                  'fixture': {'mode': 'rice', 'e': 0, 'k': 0, 'sample_count': 2,
                              'valid_bit_count': 49, 'payload_hex': '00000000000080'},
                  'expected_error_contains': 'overlong unary'})
    cases.append({'id': 'm22_truncated_mid_unary',
                  'fixture': {'mode': 'rice', 'e': 0, 'k': 0, 'sample_count': 2,
                              'valid_bit_count': 21, 'payload_hex': '000000'},
                  'expected_error_contains': 'truncated'})
    cases.append({'id': 'm23_raw_with_k_zero',
                  'fixture': {'mode': 'raw', 'e': 0, 'k': 0, 'sample_count': 2,
                              'valid_bit_count': 32, 'payload_hex': '00000000'},
                  'expected_error_contains': 'k=null'})
    cases.append({'id': 'm24_raw_truncated',
                  'fixture': {'mode': 'raw', 'e': 0, 'k': None, 'sample_count': 3,
                              'valid_bit_count': 32, 'payload_hex': '00000001'},
                  'expected_error_contains': 'truncated'})
    cases.append({'id': 'm25_raw_extra_bits_declared_one',
                  'fixture': {'mode': 'raw', 'e': 0, 'k': None, 'sample_count': 1,
                              'valid_bit_count': 24, 'payload_hex': '000100'},
                  'expected_error_contains': 'extra bits'})
    return cases


def build_vectors():
    '''Build the complete deterministic candidate vector file content.'''
    vectors = {
        'schema': 1,
        'name': 'deepeye-integer-inner-codec-candidate-v1',
        'status': 'candidate-only',
        'work_id': WORK_ID,
        'task': dict(TASK),
        'contract': dict(CONTRACT),
        'scope_note': ('Inner codec block body only.  This is not the TRACE byte '
                       'layout; no production encoder, public schema, payload offset, '
                       'tick, mask, block id, saturation or 32-byte total accounting '
                       'rule is defined here and no acceptance is claimed.'),
        'oracle_note': ('RICE blocks decode to the independent scalar oracle '
                        're-implemented in this tool from the candidate rules; RAW '
                        'blocks must reproduce the original samples exactly.  The '
                        'unit tests re-implement the same expectation separately.'),
        'hand_vectors': [],
        'raw_step_examples': [],
        'raw_noisy_examples': [],
        'malformed': build_malformed_vectors(),
        'next_block_recovery': {},
    }
    for entry_id, samples in HAND_VECTOR_SAMPLES:
        for e in codec.E_VALUES:
            vectors['hand_vectors'].append(
                fixture_entry('%s-e%d' % (entry_id, e), samples, e))
    for entry_id, samples in RAW_STEP_SAMPLES:
        for e in codec.E_VALUES:
            entry = fixture_entry('%s-e%d' % (entry_id, e), samples, e)
            vectors['raw_step_examples'].append(entry)
            if e in (0, 1, 2) and entry['fixture']['mode'] != 'raw':
                raise SystemExit('fatal: expected RAW fallback for %s at E=%d'
                                 % (entry_id, e))
    noisy = noisy_samples()
    for e in codec.E_VALUES:
        vectors['raw_noisy_examples'].append(
            fixture_entry('raw_noisy_lcg-e%d' % e, noisy, e))
    if vectors['raw_noisy_examples'][0]['fixture']['mode'] != 'raw':
        raise SystemExit('fatal: expected RAW fallback for the noisy example at E=0')
    recovery_rows = [
        ('rb1_plateau_zero_start', [0, 1, 2], 0),
        ('rb2_absolute_top_anchor', [65535, 0, 30000], 2),
        ('rb3_flat_after_step', [5, 5, 5, 5], 8),
    ]
    blocks = []
    for entry_id, samples, e in recovery_rows:
        fixture = codec.encode_block(samples, e)
        decoded = codec.decode_block(fixture)
        if decoded != scalar_oracle(samples, e):
            raise SystemExit('fatal: recovery oracle mismatch for %s' % entry_id)
        blocks.append({'id': entry_id, 'samples': samples, 'e': e,
                       'fixture': fixture, 'decoded': decoded})
    malformed_reference = [case for case in vectors['malformed']
                           if case['id'] == 'm05_excess_payload_bytes'][0]
    vectors['next_block_recovery'] = {
        'note': ('Blocks are independent: every block starts with an absolute '
                 'uint16 anchor and resets the predictor, so a later block never '
                 'needs any earlier block state, even after a rejected block.'),
        'blocks': blocks,
        'interleaved': {
            'description': 'valid, malformed, valid; the last block must still decode',
            'sequence': [blocks[0]['fixture'], dict(malformed_reference['fixture']),
                         blocks[1]['fixture']],
            'expected': ['ok', 'reject', 'ok'],
            'decoded': [blocks[0]['decoded'], None, blocks[1]['decoded']],
        },
    }
    return vectors


def cmd_emit_vectors(args):
    vectors = build_vectors()
    text = json.dumps(vectors, ensure_ascii=True, indent=2, sort_keys=True) + '\n'
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8', newline='\n')
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    print('emitted: %s (%d bytes, sha256 %s)' % (out, len(text.encode('utf-8')), digest))
    print('hand_vectors=%d raw_step_examples=%d raw_noisy_examples=%d malformed=%d'
          % (len(vectors['hand_vectors']), len(vectors['raw_step_examples']),
             len(vectors['raw_noisy_examples']), len(vectors['malformed'])))
    return 0


def cmd_check_vectors(args):
    path = pathlib.Path(args.vectors)
    raw_bytes = path.read_bytes()
    loaded = json.loads(raw_bytes.decode('utf-8'))
    fresh = build_vectors()
    problems = []
    if json.dumps(loaded, sort_keys=True) != json.dumps(fresh, sort_keys=True):
        problems.append('vector file content differs from a fresh deterministic build')
    checked = 0
    for collection in ('hand_vectors', 'raw_step_examples', 'raw_noisy_examples'):
        for entry in loaded.get(collection, []):
            checked += 1
            samples = entry['samples']
            e = entry['e']
            decoded = codec.decode_block(entry['fixture'])
            if decoded != entry['decoded']:
                problems.append('%s: decoded values differ from the frozen file'
                                % entry['id'])
            expected = expected_reconstruction(samples, e, entry['fixture']['mode'])
            if decoded != expected:
                problems.append('%s: decoded values differ from the independent '
                                'expectation' % entry['id'])
            if codec.encode_block(samples, e) != entry['fixture']:
                problems.append('%s: fixture is not what the reference encoder produces'
                                % entry['id'])
    for case in loaded.get('malformed', []):
        checked += 1
        try:
            codec.decode_block(case['fixture'])
        except codec.CodecError as exc:
            if case['expected_error_contains'] not in str(exc):
                problems.append('%s: rejection message lacks %r'
                                % (case['id'], case['expected_error_contains']))
        else:
            problems.append('%s: malformed fixture was accepted' % case['id'])
    recovery = loaded.get('next_block_recovery', {})
    for block in recovery.get('blocks', []):
        checked += 1
        if codec.decode_block(block['fixture']) != block['decoded']:
            problems.append('%s: recovery block decoded differently' % block['id'])
    interleaved = recovery.get('interleaved', {})
    sequence = interleaved.get('sequence', [])
    expected = interleaved.get('expected', [])
    if len(sequence) != len(expected):
        problems.append('recovery sequence and expected status lists differ in length')
    else:
        for index, (fixture, status) in enumerate(zip(sequence, expected)):
            checked += 1
            try:
                codec.decode_block(fixture)
                observed = 'ok'
            except codec.CodecError:
                observed = 'reject'
            if observed != status:
                problems.append('recovery sequence[%d]: expected %s, observed %s'
                                % (index, status, observed))
    print('vector file: %s' % path)
    print('vector file sha256: %s' % hashlib.sha256(raw_bytes).hexdigest())
    print('entries checked: %d' % checked)
    print('hand_vectors=%d raw_step_examples=%d raw_noisy_examples=%d malformed=%d '
          'recovery_blocks=%d'
          % (len(loaded.get('hand_vectors', [])), len(loaded.get('raw_step_examples', [])),
             len(loaded.get('raw_noisy_examples', [])), len(loaded.get('malformed', [])),
             len(recovery.get('blocks', []))))
    if problems:
        for problem in problems:
            print('FAIL: %s' % problem)
        print('vector check FAILED with %d problem(s)' % len(problems))
        return 1
    print('vector check passed: fresh-build identity, decode/oracle agreement, '
          'all rejections, block recovery')
    return 0


def cmd_run_million(args):
    if args.samples < 1:
        print('samples must be >= 1')
        return 2
    print('python: %s' % sys.version.replace('\n', ' '))
    print('platform: %s' % platform.platform())
    print('generator: random.Random(seed).getrandbits(16); samples=%d seed=%d block_len=%d'
          % (args.samples, args.seed, args.block_len))
    rng = random.Random(args.seed)
    samples = [rng.getrandbits(16) for _ in range(args.samples)]
    packed = bytearray()
    for value in samples:
        packed += value.to_bytes(2, 'big')
    samples_sha = hashlib.sha256(bytes(packed)).hexdigest()
    blocks = codec.split_blocks(samples, args.block_len)
    print('blocks: %d (last block %d sample(s))' % (len(blocks), len(blocks[-1])))
    print('samples sha256 (big-endian uint16 stream): %s' % samples_sha)
    per_e = {}
    for e in codec.E_VALUES:
        fixtures = [codec.encode_block(block, e) for block in blocks]
        decoded = []
        for fixture in fixtures:
            decoded.extend(codec.decode_block(fixture))
        expected = []
        for block, fixture in zip(blocks, fixtures):
            expected.extend(expected_reconstruction(block, e, fixture['mode']))
        if decoded != expected:
            raise SystemExit('fatal: decoder/expectation mismatch at E=%d' % e)
        stats = error_stats(samples, decoded)
        raw_blocks = 0
        rice_blocks = 0
        max_unary = 0
        k_histogram = {}
        valid_bits = 0
        body_bits = 0
        step = 2 * e + 1
        for block, fixture in zip(blocks, fixtures):
            valid_bits += fixture['valid_bit_count']
            body_bits += fixture['valid_bit_count'] - 16
            if fixture['mode'] == 'raw':
                raw_blocks += 1
                continue
            rice_blocks += 1
            k = fixture['k']
            key = 'k%d' % k
            k_histogram[key] = k_histogram.get(key, 0) + 1
            previous = block[0]
            for x in block[1:]:
                quotient = (x - previous + e) // step
                zig = 2 * quotient if quotient >= 0 else -2 * quotient - 1
                unary = zig >> k
                if unary > max_unary:
                    max_unary = unary
                value = previous + quotient * step
                if value > 65535:
                    value = 65535
                elif value < 0:
                    value = 0
                previous = value
        accounting = accounting_summary(fixtures)
        if accounting['inner_codec_body_bits'] != valid_bits:
            raise AssertionError('internal aggregate bit accounting mismatch')
        entry = {
            'e': e,
            'raw_blocks': raw_blocks,
            'rice_blocks': rice_blocks,
            'max_unary_quotient': max_unary if rice_blocks else None,
            'k_histogram': k_histogram,
            'inner_codec_body_bits': valid_bits,
            'inner_codec_stored_bytes': accounting['inner_codec_stored_bytes'],
            'inner_codec_padding_bits': accounting['inner_codec_padding_bits'],
            'residual_body_bits': body_bits,
            'identity_with_blockwise_expectation': True,
        }
        entry.update(stats)
        per_e[str(e)] = entry
        print('E=%d raw_blocks=%d rice_blocks=%d error_samples=%d max_abs_error=%d '
              'max_unary=%s valid_bits=%d stored_bytes=%d padding_bits=%d'
              % (e, raw_blocks, rice_blocks, stats['error_samples'],
                 stats['max_abs_error'], 'n/a' if not rice_blocks else str(max_unary),
                 valid_bits, accounting['inner_codec_stored_bytes'],
                 accounting['inner_codec_padding_bits']))
    result = {
        'schema': 1,
        'work_id': WORK_ID,
        'task': dict(TASK),
        'contract': dict(CONTRACT),
        'samples': args.samples,
        'seed': args.seed,
        'block_len': args.block_len,
        'block_count': len(blocks),
        'last_block_len': len(blocks[-1]),
        'samples_sha256_big_endian_uint16': samples_sha,
        'original_sample_bytes': 2 * args.samples,
        'anchor_bits_total': 16 * len(blocks),
        'per_e': per_e,
        'expectation_note': ('RAW blocks reproduce the original samples exactly; RICE '
                             'blocks follow the independent scalar oracle.'),
        'byte_accounting_note': ('inner_codec_stored_bytes sums the independently '
                                 'padded block payload lengths, sum_i ceil(valid_bits_i / 8); '
                                 'it is not ceil(sum_i valid_bits_i / 8) and implies no '
                                 'single continuous bitstream or accepted TRACE layout. '
                                 'inner_codec_padding_bits = 8 * stored_bytes - body_bits.'),
        'trace_total_bytes': 'unavailable_pending_accepted_layout',
        'claims': {'compression_ratio': 'not_claimed', 'latency': 'not_claimed'},
    }
    if args.json_out:
        out = pathlib.Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + '\n'
        out.write_text(text, encoding='utf-8', newline='\n')
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        print('json written: %s (%d bytes, sha256 %s)'
              % (out, len(text.encode('utf-8')), digest))
    print('no compression-ratio, latency, interoperability or acceptance claim is made')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    emit = sub.add_parser('emit-vectors', help='write the candidate vector file')
    emit.add_argument('--out', required=True)
    check = sub.add_parser('check-vectors', help='verify a candidate vector file')
    check.add_argument('--vectors', required=True)
    run = sub.add_parser('run-million', help='deterministic large-sample check')
    run.add_argument('--samples', type=int, default=1000000)
    run.add_argument('--seed', type=int, default=20261014)
    run.add_argument('--block-len', type=int, default=128)
    run.add_argument('--json-out', default=None)
    args = parser.parse_args(argv)
    if args.command == 'emit-vectors':
        return cmd_emit_vectors(args)
    if args.command == 'check-vectors':
        return cmd_check_vectors(args)
    return cmd_run_million(args)


if __name__ == '__main__':
    raise SystemExit(main())
