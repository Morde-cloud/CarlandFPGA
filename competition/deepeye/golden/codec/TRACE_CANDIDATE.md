# Offline TRACE candidate revision 1 (B proposal, candidate only)

Task DEEPEYE-IMPLEMENTATION-20261014/v1; work B-TRACE-OFFLINE-PAYLOAD-20261017-05-v1,
corrected under B-TRACE-CANONICAL-SOURCEAGE-CORRECTION-20261017-01-v1 (TC01
two-stage Rice k selection, TC02 short held-age bound; wire fields unchanged).
Status: **candidate only, offline, B-side proposal**. This module emits and
parses candidate type7 fixture bytes for independent review. It is NOT a public
ABI freeze and defines no production transport, scanner, scheduling,
authentication, calibration or motion authorization. A alone owns the public
schema, the only production type7 enable decision and the physical board. The
existing A wire.py must keep rejecting type7; no A/C/public interface is
modified by this work. All input points in the shipped vectors are synthetic
software fixtures; no hidden world layout or real board record is represented.

Pinned facts:

- Contract DEEPEYE-HUMAN-LOCK-20261014 revision 1 (H01-H15), commit
  `f5989cd5defce561f9ba98e6b18fc2682945f0a2`; canonical requirements SHA256
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804` (hash the
  JSON `requirements` array only, with `ensure_ascii=False`, `sort_keys=True`,
  `separators=(',',':')`, UTF-8, compared against the fixed expected value).
- Design commit `1011259415a0916054eb580687612580bc1e5f09`; base B commit
  `c5d079c24e45d97d6bd8181a7414a64c7c110860`.
- B main decision spec `main_candidate_spec.md` SHA256
  `7bc33ebc28c9f08e200c539a1a59c07b42b36211cb49b08ac449875bf75f9a73`.
- Inner codec read-only pin: `codec_reference.py` SHA256
  `2e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5` and the
  61 frozen vectors `known_vectors.json` SHA256
  `c1eee67b73b8cdd449ac72b2a77c78f714eaf448b1216b16296488881ac10e99`. Both
  stay unchanged; their bytes are never reused as candidate bytes.
- Correction work B-TRACE-CANONICAL-SOURCEAGE-CORRECTION-20261017-01-v1:
  TC01 restored the inner codec's minimum-significant-bit Rice k rule as stage
  one, with the stored-byte Rice/RAW comparison as stage two; TC02 bounds the
  short held source age to 1 <= age <= first_tick so the uint64 origin cannot
  underflow. No wire field, offset or flag changed.

Files:

- `trace_candidate.py` - the pure serializer/receiver (no side effects).
- `trace_candidate_layout.json` - machine-readable offsets, lengths, flags,
  CRC parameters, canonicality and recovery rules, limitations, A gates.
- `trace_candidate_vectors.json` - raw vectors: 8 main hand-derived vectors
  copied verbatim (plus the enriched `byte_ledger`/`restored_points` fields the
  committed tests read), 32 synthetic vectors, 2 packer verification cases,
  23 malformed payloads, 11 malformed frames, per-block and aggregate ledgers.
- `TRACE_CANDIDATE.md` - this document.
- Tests: `competition/deepeye/tests/codec/test_trace_candidate.py` (72) and
  `test_trace_corrections.py` (10, TC01/TC02).
- Portable generator for the correction round:
  `competition/deepeye/evidence/codec/trace-candidate-20261017-05/correction1/make_trace_vectors.py`
  (explicit `--golden`/`--manual`/`--spec`/`--output-dir`; the read-only
  original generator stays at `.../worker/make_trace_vectors.py`).

## Outer frame

The existing ABI3 header is copied literally for offline fixture bytes:
`<2sBBBBHI` = 12 header bytes, then payload (21..32 bytes), then a
little-endian uint16 CRC; total frame <= 46 bytes; 14 bytes outer overhead.

| offset | bytes | field | rule |
|---|---|---|---|
| 0 | 2 | magic | `A5 5A` |
| 2 | 1 | version | 3 |
| 3 | 1 | type | 7 (candidate fixtures only; A wire.py keeps rejecting type7) |
| 4 | 1 | payload_len | declared payload 21..32; must equal actual length |
| 5 | 1 | config_epoch | must equal binding.config_epoch |
| 6 | 2 | sequence | little-endian uint16 frame sequence, not an acquisition index |
| 8 | 4 | tick_ms | little-endian uint32, the low 32 bits of the FIRST acquisition tick |
| 12 | n | payload | candidate payload, see below |
| 12+n | 2 | crc | CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflect, xor 0) over version byte through payload end, stored little-endian |

## Payload prefix (21 bytes)

| offset | bytes | field | rule |
|---|---|---|---|
| 0 | 1 | revision | candidate revision, exactly 1 |
| 1 | 1 | settings | bits0..2 E code (0->0, 1->1, 2->2, 3->4, 4->8; 5..7 invalid); bit3 RAW; bits4..7 Rice k 0..15, RAW requires k=0 |
| 2 | 1 | quality | bits0..1 channel 0..3; bit2 valid; bit3 saturated; bit4 held; bit5 source_fault; bit6 long_source_tick; bit7 reserved, must be 0 |
| 3 | 1 | count | point count 1..128 |
| 4 | 1 | significant bits | total code-section bits including the 16 anchor bits for valid blocks; 0 for invalid blocks |
| 5 | 4 | session | little-endian uint32, must equal binding.session |
| 9 | 4 | first index | little-endian uint32 actual acquisition index of the first point |
| 13 | 8 | first tick | little-endian uint64 actual acquisition tick of the first point |

Following the prefix, in order:

1. Strides (count > 1 only): index_stride uint16 and tick_stride_ms uint16,
   both 1..65535, little-endian. Every point is first + i*stride (uniform
   arithmetic progression). uint32 index and uint64 tick overflow is rejected.
   Count 1 carries no stride bytes; nonuniform spacing or a gap outside
   uint16 strata forces a new block.
2. Held source extension (held only): the source-update origin is CONSTANT for
   the whole block. If first_tick - origin is 1..65535, long_source_tick=0 and
   the 2-byte little-endian age is stored. If the age exceeds 65535,
   long_source_tick=1 and the absolute origin uint64 is stored in 8 bytes;
   require origin < first_tick and age > 65535 (canonical long form; the long
   form is rejected for an age that fits 16 bits). Later points derive their
   source tick from the fixed origin. Not held: no extra bytes.
3. Code section: ceil(significant_bits/8) bytes starting at a byte boundary.
   Anchor and RAW sample words are little-endian; Rice residual bits are
   MSB-first. Unused low bits of the final code byte must be zero. No trailing
   bytes. This adapts (does not modify) the inner fixture codec, whose anchor
   and RAW words are big-endian and whose module and vectors stay frozen.

Length accounting: payload = 21 + (4 if count>1 else 0) + (0/2/8 held source
extension) + code bytes, checked against the 32-byte budget after every term.
Examples: fresh valid RAW singleton 23 B payload / 37 B frame; held short
25/39; held long 31/45; invalid quality-only singleton 21/35; fresh RAW 3
points 31/45; 41 equal fresh points 56 significant bits / 7 code bytes /
32 B payload / 46 B frame.

## Value, quality and source semantics

One payload carries one channel (0..3), one constant mask of quality flags and
one arithmetic progression of actual acquisition indices and ticks. The four
quality flags (valid, saturated, held, source_fault) are common to every point
in the block, so the per-point mask is recovered by expansion; the packer
splits whenever any flag changes. For held blocks the packer also splits when
the source-update origin changes.

- Valid blocks: value uint16 per point. The first value is an exact anchor;
  subsequent Rice residuals use the E=0/1/2/4/8 closed loop, ZigZag coding,
  Rice k 0..15 with unary quotient <= 31, reconstruction clamping to 0..65535
  and a first anchor independent of any state. Whole-block RAW stores the
  original uint16 values and is lossless at any E.
- Invalid blocks are quality-only: zero significant bits/code bytes, the RAW
  flag with k=0, no anchor and no fabricated sample. Saturated, held and long
  must all be 0 when invalid; source_fault may coexist with valid or invalid
  because it is reported source quality, never a runtime permission.
- Saturation is a reported status only and never implies endpoint values (the
  vibration RMS source can be saturated across a whole window while individual
  values are not 0/65535). The vectors include a saturated non-endpoint case
  with values 1234, 65535, 42.
- Held: every point keeps its own actual acquisition tick while the source
  update origin is constant. The short form stores a 1..65535 age bounded by
  the first tick (1 <= age <= first_tick, so the uint64 origin cannot
  underflow; B main finding TC02); the long form stores the absolute origin
  and requires age > 65535. A long form whose age fits 16 bits is noncanonical
  and rejected.
- Invalid points carry value/source_tick None; a fresh valid point requires
  source_tick_ms == tick_ms; a held valid point requires source_tick_ms <
  tick_ms; saturated/held cannot be set on invalid points.

Current source versus synthetic future layout: A currently reports ADC tick
values of at most 2^31-1 that are multiples of 10, and its EM tick values are
multiples of 50 ms. The
uint64 tick vectors and low32 rollover vectors in this candidate are synthetic
future-layout proposals, not accepted current-source records. Index32 and
frame sequence16 never wrap inside one binding. A/C own the actual source
counter origins and the authorized sequence mapping; this proposal maps a C
uint64 acquisition sequence to a zero-extended index qualified by
binding+channel, never by frame sequence.

## Canonical mode/k selection (two-stage)

For each valid block the encoder computes the ZigZag residual list and then
applies two stages:

1. Stage 1 chooses the Rice k (0..15, unary quotient <= 31) with the FEWEST
   SIGNIFICANT BITS (16 anchor bits plus the body bits), ties choosing the
   lowest k. This is exactly the unchanged inner fixture codec's k rule.
2. Stage 2 keeps Rice only when its padded code-byte count is STRICTLY smaller
   than RAW's 2*count bytes; otherwise RAW wins, including every stored-byte
   tie. This remains the explicit difference from the inner codec, which keeps
   Rice on a bit tie below 16*(n-1) raw body bits.

- TC01 counterexample (B main finding, now fixed): values [10000, 10001,
  10002, 10004] at E0 give ZigZag [2, 2, 4]; k0 needs 27 significant bits
  while k1 needs 26 (k2 also 26, so the tie keeps k1), and 4 stored Rice bytes
  beat 8 RAW bytes. The rejected byte-minimizing rule had chosen k0 at 27 bits;
  the corrected frame is a committed vector and a unit test.
- Values [0, 8, 16], E0: k2 costs 30 significant bits and k3 costs 28, both in
  4 padded bytes; the minimum-significant-bit rule selects k3 while the
  rejected byte-minimizing rule selected k2.
- Values [0, 64], E0: stage 1 picks k=6 with 25 significant bits (k7 ties at
  25, lowest k wins, matching the inner codec); stage 2 sees 4 stored Rice
  bytes vs 4 RAW bytes, a stored-byte tie, so the candidate stays RAW with 32
  significant bits. Both produce 4 stored bytes here, but the bytes differ.
- Values [0, 2048, 4096], E0: best Rice k=11 with 44 significant bits -> 6
  stored bytes vs 6 RAW bytes, another stored-byte tie, so RAW with 48 bits.
- Three equal fresh values: Rice k=0 with 18 significant bits -> 3 stored
  bytes < 6 RAW bytes, so Rice is kept.

RAW stores the original values, so the tie policy is always lossless. The
decoder enforces canonicality: it re-derives the two-stage selection from the
decoded values and requires declared mode/k/significant-bits/code bytes to
match; nonzero padding bits, truncated/overlong unary, RAW when Rice is
strictly byte-better and nonoptimal k are all rejected.

## Byte ledger

Per block and aggregate: `count` (points), `value_count` (0 for invalid
blocks), `selected_raw_bytes` = 2*value_count, `significant_bits` (0 when
invalid), `stored_code_bytes` = ceil(significant_bits/8), `padding_bits` =
8*stored_code_bytes - significant_bits, `metadata_bytes` = 21 + strides +
held extension, `payload_bytes`, `outer_overhead_bytes` = 14, `frame_bytes` =
payload_bytes + 14, `line_bits_8n1` = 10*frame_bytes (8N1 UART line cost).

## Public APIs (pure, offline)

- `encode_payload(points, binding, channel) -> bytes`: one complete block,
  count 1..128; uniform flags and held origin; uniform representable strides;
  full 32-byte bound enforced; never splits silently.
- `decode_payload(payload, binding) -> dict`: detached record with channel,
  mode, k, e, flags, count, significant bits, first index/tick, strides,
  held origin, all reconstructed points and the full ledger. Strict length,
  metadata, canonicality and padding checks.
- `encode_frame(points, binding, channel, sequence) -> bytes`: payload plus the
  ABI3 header and CRC16/CCITT-FALSE frame; sequence uint16; header tick is the
  low 32 bits of the block first tick.
- `decode_frame(packet, binding) -> dict`: exact-bytes frame decode with
  length <= 46, magic/version/type, declared-length agreement, CRC,
  config_epoch, binding session/E and header-tick-low32 consistency; returns
  the payload record plus sequence and config_epoch.
- `pack_channel(points, binding, channel, start_sequence) -> [bytes]`: input
  1..128 points with strictly increasing indices AND ticks; greedily selects
  the longest legal fitting prefix and splits at quality, held-origin, stride,
  gap and budget limits; every point lands in exactly one frame; each block
  starts a fresh exact anchor; no interpolation, drop, reorder, renumber,
  partial output on insufficient uint16 sequence capacity and no wrap.
- `TraceReceiver(binding)`, `accept(packet)`, `close()`, `state_snapshot()`:
  bounded offline receiver, one immutable binding per instance, no rebind or
  reset API. See below.

## Receiver semantics

- State: at most 16 cached packet byte strings keyed by sequence, a global
  non-wrapping last sequence and four per-channel (last index, last tick)
  high-water pairs.
- Frame sequence must increase without wrap; an exact duplicate resident in
  the cache returns status duplicate with ZERO points and does not renew
  state; same sequence with different bytes is a conflict; an old sequence
  outside the 16-entry cache is rejected.
- Future sequence gaps are accepted and never synthesize missing points.
- Per channel, the first index and first tick of a new frame must both exceed
  that channel high water; matching indices across channels prove nothing.
- Decoder validation happens before any state commit: bad CRC/payload/
  binding, conflicts, stale sequences and channel-order violations never
  partially advance the caches or high waters.
- `close()` is terminal and idempotent; accept afterwards rejects.
- `state_snapshot()` and every accepted record are detached: caller mutation
  cannot change receiver state.
- A new session/epoch requires an explicit authoritative new binding/receiver
  and closure of the old receiver by the integration owner. This offline
  class cannot attest that a caller performed a real handshake, that session
  IDs are unique, or that bytes came from a trusted source; it makes no
  runtime authorization claim.

## Input strictness and detachment

All numeric inputs must be exact built-in ints and all flags exact bools;
binding and point mappings must be exact dicts with exact str keys; point
sequences must be exact list or tuple; payload/packet data must be exact
bytes. bool, IntEnum/int subclasses, dict/list/tuple/bytes subclasses and
str-subclass keys are rejected on type BEFORE any user operator (comparison,
equality, hash) could run. Oversize blocks are rejected before any uint8 bit
count serialization, so an intended candidate rejection never escapes as
struct.error. Inputs are snapshotted at call time and all returned records
are detached from caller and receiver state.

## Vector inventory (`trace_candidate_vectors.json`)

- `manual_vectors`: the 8 vectors hand-derived by the B main, copied verbatim
  from `main_manual_vectors.json` (SHA256
  `36b8e3fdb53e3c8fc911cc44b4f4151d62863d2e05b189f68c42fefe869b2d24`) with
  source points, binding/channel/sequence, payload and frame bytes, restored
  points and the byte ledger. Expected bytes were never derived from this
  implementation; the tests only check agreement with the committed file.
- `synthetic_vectors` (32, labelled software_fixture): all_e (5), boundary
  (4), mask (6), age_forms (3), tick_forms (3), tie (2), canonical_k (2: the
  TC01 hand-derived case plus the equal-padded-bytes family),
  channels_4x128 (4, four channels x 128 selected points), sparse_pack (3).
- `packer_verification` (2): greedy longest-prefix results checked against an
  exhaustive longest-fitting-prefix check from each block start; this is not a
  claim of globally optimal packing.
- `malformed_payloads` (23) and `malformed_frames` (11): exact injected defects
  and the expected rejection, covering declared/actual length mismatches,
  CRC corruption, epoch/session/E/tick-low mismatch, reserved bits, zero
  count, stride 0, progression overflow, zero/noncanonical/truncated/
  overlong unary, nonzero padding, RAW claimed when Rice is strictly
  byte-better, nonoptimal k, noncanonical long age, invalid-shape flags and
  trailing bytes, plus the TC02 short ages above the first tick (the main
  portable-check underflow frame copied verbatim and a crafted tick-0 age-1
  frame).
- Ledger: every vector carries the per-block ledger; the file carries the
  aggregate; the tests recompute both.

## Rejection and recovery summary

Payload rejects: length < 21 or > 32; revision != 1; reserved quality bit7;
E code 5..7; E != binding; RAW with k != 0; session mismatch; count 0 or
> 128; missing/zero strides; index/tick progression overflow; noncanonical
long age; long bit without held; short age 0 or above first_tick; invalid
block without RAW,
with bits != 0, saturated, held or trailing bytes; valid block with bits < 16
or length mismatch against metadata + code bytes; nonzero padding; truncated
or overlong unary; noncanonical mode/k/bits; code bytes not equal to the
canonical re-encoding; held source not preceding a tick.

Frame rejects: length < 35 or > 46; bad magic/version/type; declared payload
> 32; declared length mismatch; epoch mismatch; CRC mismatch; header tick not
the low32 of the first tick.

Receiver rejects: closed; conflict; stale outside cache; channel index or
tick order violation; any decoder rejection - all without partial state
commit. Recovery: a next frame with a higher sequence and a valid channel
water continues normally; duplicates are idempotent; a new session/epoch
requires a new receiver (integration owner closes the old one).

## Tests and how to run them

`competition/deepeye/tests/codec/test_trace_candidate.py` contains 72 tests:
manual-vector agreement (bytes, restored points, ledgers), code selection
(ties, k=0, Rice strictly better, noncanonical k), boundaries (32/33 B
payload, 46 B frame, 42-point split, singleton forms, gap splitting, uint32
index/uint64 tick, low32 rollover restore, oversize-block uint8 rejection
before bit serialization), wire format (LE anchor/RAW,
header/CRC, quality expansion), vector-driven re-generation and ledger
recomputation for all synthetic and malformed vectors, handcrafted malformed
cases (length/CRC/metadata/padding/unary/noncanonical), mask and age
behavior (8 flag-change splits, origin-change split, saturated non-endpoint,
invalid + fault, age form boundaries 65535 short / 65536 long), bounded
receiver behavior (duplicate zero points, conflict, stale outside cache,
future gap, per-channel order, CRC no-commit, terminal close, detached
outputs, 16-entry cache) and input strictness (exact types before operators,
str-subclass keys, bool/IntEnum/int-subclass traps, bounds) plus detached
inputs/records.

Run from the repository root (paths are resolved relative to this worktree;
no private controller path or parent fixture is required):

```
python -B -m unittest discover -s competition/deepeye/tests/codec -p test_trace_candidate.py -v
python -B -m unittest discover -s competition/deepeye/tests/codec -p test_trace_corrections.py -v
python -B -m unittest discover -s competition/deepeye/tests/codec -p test_codec_reference.py -v
python -B -m unittest discover -s competition/deepeye/tests/codec -p test_scalar_boundary.py -v
```

`test_trace_candidate.py` (72) and `test_trace_corrections.py` (10: the TC01
hand-derived frame, the equal-padded-bytes family with an independent
two-stage oracle, the inner-codec k crosscheck, and the TC02 age-bound and
receiver-atomicity cases) are the candidate suites; the last two are the
pre-existing 49 + 18 = 67 codec tests. All stay green and unchanged, and they
are the only suites this correction ran (no full historical suite was
executed).

## Limitations

- Candidate-only: no public ABI, no production transport/scanner, no board
  use, no A/C file changes; A wire.py keeps rejecting type7. No B01/R03/G01,
  CDC, live-integration, compression, latency, scheduling or system
  acceptance claim of any kind.
- The receiver is offline software: it cannot prove real handshakes, session
  uniqueness or source authenticity; binding is an expected-value fixture.
- The current A source reports ADC ticks <= 2^31-1 in multiples of 10, and
  its EM tick values are multiples of 50 ms; uint64/interleaved-span vectors
  are synthetic future-layout proposals, not measurements. C mapping (uint64 acquisition sequence ->
  zero-extended index qualified by session/channel, never frame sequence) is
  a proposal for A/C approval.
- High-water receiver checks reject legitimate interleaved or retransmitted
  older frames by design; integration must map real source behavior first.
- No average compression, throughput, slot legality or 100 Hz/continuous
  sampling is claimed; the 21-byte metadata can expand traffic versus naive
  packing.

## A approval gates (explicit, not passed)

Candidate field packing and revision; header first-tick rule;
per-channel acquisition-index meaning and C grouping; 64-bit clock origin and
proof; quality-only invalid frames and uniform-mask splitting; held-source
origin and short/long form; stored-byte RAW tie policy and little-endian body
adaptation; binding/sequence retirement; full BOOT digest; actual TRACE
scheduling and sliding-window budget. C decodes the approved candidate and
adapts source/profile physical units. These remain review gates and are not
reasons to claim R03 passed or to patch A files.

## Evidence

Implementation and test evidence for work B-TRACE-OFFLINE-PAYLOAD-20261017-05-v1
lives under `competition/deepeye/evidence/codec/trace-candidate-20261017-05/worker/`
(captured stdout/stderr, command records with exit codes and hashes, the
vector generator `make_trace_vectors.py`, result summary) with generator
captures under `worker/captures/`.

The bounded correction B-TRACE-CANONICAL-SOURCEAGE-CORRECTION-20261017-01-v1
adds `.../correction1/` next to it: the portable correction generator
`correction1/make_trace_vectors.py` (explicit `--golden`/`--manual`/`--spec`/
`--output-dir`; determinism verified across two fresh directories), raw
command captures, the parent regression runs on the rejected original (exit 1,
both findings) and on the corrected source (exit 0), the parent public audit
runs, and per-file hashes. The enriched `byte_ledger`/`restored_points` fields
inside `manual_vectors.vectors` are kept for the committed 72 tests; the pinned
`main_manual_vectors.json` values are all preserved exactly (verified with the
independent provenance check in the same evidence directory).

Reproduce the vector and layout artifacts from the repository root (no private
or `.local` path is needed; `--golden` points at the codec sources and the
pinned main copies live in the published `main/` directory):

```
python -B competition/deepeye/evidence/codec/trace-candidate-20261017-05/correction1/make_trace_vectors.py --golden competition/deepeye/golden/codec --manual competition/deepeye/evidence/codec/trace-candidate-20261017-05/main/main_manual_vectors.json --spec competition/deepeye/evidence/codec/trace-candidate-20261017-05/main/main_candidate_spec.md --output-dir <fresh-directory>
```

then copy the generated `trace_candidate_vectors.json` and
`trace_candidate_layout.json` to `golden/codec/` explicitly.
