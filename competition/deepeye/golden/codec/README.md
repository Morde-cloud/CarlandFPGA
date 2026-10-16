# DeepEye integer inner-codec candidate (candidate only)

Task: `DEEPEYE-IMPLEMENTATION-20261014/v1`
Work: `B-CODEC-INTEGER-FOUNDATION-20261015-01-v1`
Correction: `B-CODEC-BYTE-ACCOUNTING-CORRECTION-20261016-02-v1` (aggregate byte
accounting only; see "Byte accounting").
Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1` (H01-H15), requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Design commit `1011259415a0916054eb580687612580bc1e5f09`; lock commit
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`.

Status: candidate-only integer foundation for the inner codec block body.
It is not a production TRACE encoder and defines no public TRACE byte layout,
payload offset, tick, mask, block id, saturation rule or 32-byte accounting.
R03 stays blocked; B01 stays `not_run`; A alone operates the physical board.
Nothing here is an acceptance claim.

## Files

- `codec_reference.py` - candidate reference implementation (encoder, strict
  fixture decoder, selection helper).
- `integer_candidate_rules.json` - machine-readable candidate rule set.
- `known_vectors.json` - frozen candidate vectors: hand vectors for every E,
  RAW examples, malformed fixtures, next-block recovery; reproducible from the
  verifier tool.
- `../../tests/codec/test_codec_reference.py` - unittest suite.
- `../../tools/verify_codec_candidate.py` - deterministic vector builder,
  vector checker and the 1,000,000-sample run.
- `../../evidence/codec/integer-foundation-01/` - raw commands, exit codes,
  stdout/stderr captures and the machine-readable result.
- `../../evidence/codec/byte-accounting-correction-02/` - corrected aggregate
  byte-accounting evidence for
  `B-CODEC-BYTE-ACCOUNTING-CORRECTION-20261016-02-v1` (commands, captures,
  result).

## Candidate rules (summary)

1. Samples are uint16 scalars; bool/non-int/out-of-range values are rejected.
   A block has 1..128 samples and starts with the exact absolute uint16 anchor
   of its first sample; the predictor resets at every block start.
2. `D = 2E+1` with `E` in {0,1,2,4,8}; `q = (x - p + E) // D` uses
   mathematical floor division; `y = min(65535, max(0, p + q*D))`; `p = y`.
   E=0 is exact.
3. `z = 2q` for `q >= 0`, `z = -2q-1` otherwise. One Rice `k` in 0..15 is
   used per block, MSB-first: quotient zero bits, a one terminator, then k
   remainder bits. Quotient > 31 is illegal for that k; there is no escape.
4. Selection compares every legal Rice body bit count with RAW `16*(n-1)`
   bits; the minimum wins and ties choose the lowest k. RAW wins a tie with
   Rice or when no k is legal. A RAW body stores the original remaining uint16
   samples; the anchor is always the original first sample.
5. The candidate fixture stores `valid_bit_count` separately; unused low bits
   of the final payload byte must be zero. Truncation, nonzero padding, extra
   bits, illegal k/E, wrong decoded count and overlong unary are rejected.

`codec_reference.py` is the executable definition; `integer_candidate_rules.json`
is the reviewable mirror.

## Candidate fixture (candidate-internal, not a TRACE layout)

| field | meaning |
| --- | --- |
| mode | `rice` or `raw` |
| e | 0, 1, 2, 4, 8 |
| k | 0..15 for rice; null for raw |
| sample_count | 1..128 |
| valid_bit_count | significant payload bits (>= 16 for the anchor) |
| payload_hex | payload bytes as hex; final-byte bits past valid_bit_count are zero |


## Byte accounting

A stored block payload is `ceil(valid_bit_count / 8)` bytes: the final byte
holds zero padding beyond `valid_bit_count`. The per-block ceiling formula is
valid per block only. An aggregate over a block sequence is the **sum of the
per-block stored bytes** (`sum_i ceil(bits_i / 8)`), not
`ceil(sum_i bits_i / 8)`, which would describe one continuous bitstream. The
million-sample result exposes `inner_codec_body_bits` (exact significant
bits), `inner_codec_stored_bytes` (sum of block payload lengths) and
`inner_codec_padding_bits` (`8 * stored_bytes - body_bits`) separately. No
TRACE byte layout, block framing or 32-byte accounting rule is defined here.


## Verification

- Unit tests (software only), from the worktree root:
  `python -B -m unittest discover -s competition/deepeye/tests/codec -v`
- Vector check:
  `python -B competition/deepeye/tools/verify_codec_candidate.py check-vectors
  --vectors competition/deepeye/golden/codec/known_vectors.json`
  re-builds the file deterministically, decodes every vector, compares with an
  independent scalar oracle (RAW blocks must reproduce the original samples
  exactly) and exercises every rejection and recovery case.
- Deterministic sample run (seed 20261014, 1,000,000 samples, block length 128):
  `python -B competition/deepeye/tools/verify_codec_candidate.py run-million
  --samples 1000000 --seed 20261014 --block-len 128`
  Per-E error counts, max unary quotient, RAW/Rice block counts and inner
  codec-body byte counts are recorded under
  `evidence/codec/integer-foundation-01/`. Its aggregate byte counts are
  superseded by the corrected `byte-accounting-correction-02` run, which sums
  independently padded block payloads.
- Counters are facts only: no compression ratio, latency, interoperability,
  simulation, synthesis, implementation, board or system claim is made.

## Structural observations (recorded, not acceptance)

- E=0 reconstruction is exact; at E>0 the per-sample error is bounded by E on
  all seeded streams, and RAW blocks are always exact.
- For uint16 inputs the largest ZigZag value is 7710 at E=8 and 14564 at E=4,
  so a legal Rice body always exists below 16 bits per residual and RAW is
  never selected at E in {4,8}; the 1M run records the observed counts.
- Blocks are independent: the absolute anchor plus the predictor reset means a
  later block decodes without any earlier block, even after a rejected block.
- The Python reference uses arbitrary-precision integers; the difference
  intermediate must be at least 17-bit signed in any fixed-width follow-up.

## Unresolved - reported to B main, not decided here

TRACE tick semantics; tick/mask bit order and granularity; sparse selection
point ordinal vs acquisition index; block id; saturation; 32-byte total
accounting; payload offset and layout version; seq mapping; E/k signalling in
the outer format; channel multiplexing. R03 remains blocked.

## Proof states

software candidate tests: run (this work) | TRACE layout: not_run (R03) |
B01: not_run | simulation: not_run | synthesis: not_run | implementation:
not_run | board: not_run | system: not_run | compression ratio: not_claimed |
latency: not_claimed.
