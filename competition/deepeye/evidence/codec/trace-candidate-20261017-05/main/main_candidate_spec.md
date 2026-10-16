# B main decision: offline TRACE candidate revision 1

Task DEEPEYE-IMPLEMENTATION-20261014/v1; continuation
B-TRACE-CANDIDATE-CONTINUE-20261017-v1. This is a B proposal, NEVER a public ABI
freeze. A owns public schemas, the only production type7 enable decision and
the physical board. Existing A wire.py must continue rejecting type7. All
H01-H15 remain pinned at requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804,
design1011259415a0916054eb580687612580bc1e5f09. Base B commit
c5d079c24e45d97d6bd8181a7414a64c7c110860. A input commit
66aa291d7f01cc3cfefb8c30c4e8ad3aec6547bd. No side channels or motion API.

## Decision and scope

Enough information exists to implement and independently examine this complete
OFFLINE byte proposal. The unresolved fields below require A's later approval,
but do not prevent B producing concrete bytes for review. No implementation in
A/C files or A production decoder is authorized. Source/profile authentication,
calibration, runtime clock acquisition/error bounds, scheduling and C's input
adapter are not supplied by this serializer. Synthetic fixtures only.

One frame carries one channel (0..3), one constant set of quality flags and an
arithmetic progression of actual acquisition indices/ticks. Arbitrary sparse
input is represented by splitting, including one-point fallback. Indices are
actual source acquisition indices, NOT dense selected-point ordinals or frame
sequence numbers. They are uint32 within a session. They are compared per
channel; matching indices across channels do not by themselves prove common
sampling time. Each point retains its actual acquisition and source-update tick.
Four-channel/model grouping requires the source/profile agreement by A/C.

## Candidate wire layout

The existing ABI3 outer header is copied literally for OFFLINE fixture bytes:
`<2sBBBBHI`: magic A5 5A, version3, type7, payload length, config_epoch uint8,
frame sequence uint16, tick_ms uint32. The header tick is the low32 bits of the
FIRST acquisition tick in this candidate payload (a proposal, not TELEM/ACK
semantics). CRC16/CCITT-FALSE covers version through payload end, little-endian
CRC. Overhead14 bytes, payload<=32, frame<=46. No production transport/scanner.

All multi-byte numeric fields below, including anchor and RAW samples, are
little-endian. Rice residual bitstream remains MSB-first. This explicitly adapts
the existing inner-codec fixture's big-endian anchor/RAW word representation;
do not change that existing codec module or its vectors.

Fixed payload prefix =21 bytes:

|offset|bytes|field|
|---|---|---|
|0|1|candidate revision, exactly1; distinct from outer ABI version|
|1|1|bits0..2 E code:0->0,1->1,2->2,3->4,4->8;5..7 invalid. bit3 RAW. bits4..7 Rice k0..15; RAW requires k=0|
|2|1|bits0..1 channel0..3; bit2 valid; bit3 saturated; bit4 held; bit5 source_fault; bit6 long_source_tick; bit7 reserved0|
|3|1|point count1..128|
|4|1|significant code bits, includes16 anchor bits for any valid block|
|5|4|session uint32|
|9|4|first actual acquisition index uint32|
|13|8|first actual acquisition tick_ms uint64|

Following prefix, in order:

1. If count>1: index_stride uint16 and tick_stride_ms uint16, both1..65535.
   All points use first+i*stride. Reject any uint32-index/uint64-tick overflow.
   Count1 has no stride bytes. A nonuniform or larger gap requires a new block.
2. If held: source update origin is CONSTANT for the whole block. If first_tick
   minus source_tick is1..65535, long_source_tick=0 and encode that age in2 bytes.
   Otherwise long_source_tick=1 and encode the absolute source_tick uint64 in8
   bytes; require source_tick<first_tick and age>65535 (canonical long form).
   Later point ages are derived from their actual ticks and that fixed origin.
   If not held: long_source_tick=0, no extra source bytes, source_tick=acquisition
   tick for valid points. Invalid points have source_tick=None.
3. Code bytes: length=ceil(significant_bits/8), unused low bits of the last Rice
   byte zero. No trailing bytes. Nonvalid blocks have0 code bits/bytes and RAW,
   k0; no fictional sample/anchor is emitted. This quality-only representation
   is an explicit A approval item. Saturated/held/long must all be0 when invalid;
   source_fault may coexist with valid or invalid because it is reported source
   quality, not a runtime permission. No validity inferred from a numeric value.

The four quality flags are common to ALL points in the block, so the per-point
mask is recovered by expansion; split when any flag changes. For held blocks,
split when the source update origin changes. Saturated is reported status and
does not imply every value is an endpoint (A's vibration RMS has window-wide
saturation). The generic serializer does not claim the flags match a real source.

## Code and canonical behavior

Use the current exact-int B codec source SHA256
2e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5.
E0 exact; E1/2/4/8 closed-loop q=floor((x-prev+E)/(2E+1)), reconstructed/clamped
predictor, independent exact first anchor, ZigZag, Rice k0..15, unary<=31.
Whole-block RAW carries ORIGINAL uint16 values, so it is lossless at any E.

The full-payload candidate uses Rice ONLY when its padded code-byte count is
STRICTLY smaller than RAW's2*count bytes. RAW wins stored-byte ties, an explicit
proposal above the inner codec's bit-count choice. Metadata lengths are identical
for the two modes. Do not silently change the inner reference's selection rule.
Swap anchor/RAW words to little-endian when producing candidate wire bytes;
convert them back before calling the existing fixture decoder.

Decoder must reject noncanonical encodings, including nonoptimal k, RAW when
Rice is strictly byte-better, impossible residuals/saturation and nonzero pad.
A permitted deterministic method: decode valid values, run the same canonical
candidate selection on reconstructed values, and require mode/k/bits/code bytes
to match. The main and C will check with independent arithmetic/bit parsing;
B's own re-encode is not independent interoperability evidence.

Length accounting:
`payload =21 + (4 if n>1 else0) + source_extension(0/2/8) + code_bytes`.
The bound is checked AFTER every term and padding. A valid fresh single point
is23B payload/37B frame; held short is25/39; held long is31/45. Therefore every
valid singleton fits. Invalid singleton is21/35. Fresh RAW3 points cost31/45;
fresh41 equal valid points use56 significant bits/7code bytes, total32/46.
There is no claim of average compression, maximum throughput or slot legality.
The extra metadata can expand traffic substantially and must be reported.

## Proposed pure APIs and bounds

New B module golden/codec/trace_candidate.py; no network/process/board side effect.
Use exact built-in scalars/containers at ingress; reject bool as integer,
IntEnum/subclasses, extra/missing fields, nonbytes frame data. Snapshot primitive
input state; returned records must not alias receiver state or caller dictionaries.

Binding exact dictionary keys: session, config_epoch, e (unsigned32/unsigned8/E).
This is only an offline expected-binding fixture, NOT proof of BOOT/source trust.
Point exact dictionary keys: index,tick_ms,value,valid,saturated,held,source_fault,
source_tick_ms. Index unsigned32; ticks unsigned64; flags exact bool. Valid value
unsigned16; invalid value/source_tick=None. Held valid: source_tick<tick. Fresh
valid: source_tick==tick. Invalid: saturated=held=False. No hidden/future values.

- encode_payload(points,binding,channel) -> immutable bytes; count1..128, uniform
  flags/held origin, uniform positive representable strides, full bound. Does
  not split silently. Reject if too large or nonrepresentable.
- decode_payload(payload,binding) -> detached record including channel, points,
  significant bits/mode, first tick, and every component of the byte ledger.
- encode_frame(points,binding,channel,sequence) -> offline candidate bytes with
  exact outer CRC/header; no mutation/ENABLE of A wire module.
- decode_frame(packet,binding) -> detached decoded record plus outer sequence;
  exact length<=46, CRC/version/type/epoch/session/E/tick-low consistency checks.
- pack_channel(points,binding,channel,start_sequence) -> list of independently
  decodable frames, input1..128 points, indices and acquisition ticks strictly
  increasing. Greedily choose the longest legal fitting prefix, splitting at
  quality/held-origin/stride/gap/budget limits. No interpolation, dropped point,
  reordering or renumbering. Each block's first valid value is a new exact anchor.
  Do not emit partial output on insufficient16-bit sequence capacity; no wrap.
  An ascending-prefix search may stop at first size overflow because fixed-
  metadata and minimum Rice/RAW stored length are nondecreasing for a common
  prefix; verify this with independent exhaustive candidate-size tests.
- TraceReceiver(binding), accept(packet), close(), state_snapshot(). One immutable
  binding per instance; no reset/rebind API. close is terminal. Decoder validation
  occurs before state commit. Keep at most16 packet bytes by sequence plus four
  per-channel(last index,last tick) pairs. Global frame seq must increase without
  wrap; exact duplicates in cache return status duplicate and ZERO points, no
  renewed state. Same seq/different bytes conflict; old seq outside cache rejects.
  Future seq gaps may be accepted, never synthesize missing points. Per-channel
  first index and tick must both exceed that channel's previous last values.
  Bad CRC/payload/binding/conflict/order does not partially advance high waters.
  Outputs and state_snapshot are detached; caller mutation cannot change caches.
  A new session/epoch requires explicit authoritative new binding/receiver and
  closure of the old receiver by the integration owner. This offline class cannot
  attest that caller performed a real handshake or that session IDs are unique.

Full uint64 ticks restore low32 rollover without losing epoch bits. Index32 and
frame seq16 never wrap in a binding. A/C must decide actual source counter
origins and the authorized sequence mapping; proposal maps C uint64 acquisition
sequence to zero-extended index, qualified by binding+channel, never frame seq.
No runtime clock age, observation lease, motion authorization or AI feed here.

## Required independent review / output

Same exact commit: implementation, complete layout JSON+README, raw JSON vectors
(source points, bytes, expected restored points, full byte ledger), unit tests
and raw logs. Cover all E, modes/k, valid/invalid/saturation/held/fault, all4channels,
single/maximum blocks, irregular selection, uint bounds/tick-low rollover,
malformed metadata/body/length/CRC/padding/unary/noncanonical forms, next-frame
recovery, duplicate/conflict/late/session/epoch behavior and detached inputs/outputs.
Include handcrafted vectors supplied by main, four-channel128-selection synthetic
recovery and exact original/inner/payload/frame/10-bit-per-byte line counts.
Show stored-byte RAW tie behavior explicitly. No source or waveform borrowing
from hidden layout; all synthetic seeds/patterns labelled software_fixture.

A approval decisions: candidate field packing/revision; header first-tick rule;
per-channel acquisition-index meaning/C grouping; 64-bit clock origin/proof;
quality-only frames and uniform-mask splitting; held-source origin/short-long
form; byte-tie RAW policy and LE body adaptation; binding/sequence retirement;
full BOOT digest and actual TRACE scheduling/sliding-window budget. C independently
decodes approved candidate and adapts source/profile/physical units. These remain
explicit review gates, NOT reasons to claim R03 passed or to patch A files.
