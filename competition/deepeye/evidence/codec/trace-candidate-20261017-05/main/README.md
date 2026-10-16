# Main independent review: offline TRACE candidate

Task DEEPEYE-IMPLEMENTATION-20261014/v1. Operation
B-DEEPEYE-TRACE-CANDIDATE-20261017-05. This accepts only the complete **offline
candidate** serializer/decoder/packer and bounded replay model. A owns the final
public ABI and production type7 enable; C independent consumption is still due.
B01/R03/B05/G01 and simulation/synthesis/implementation/board/system remain
not_run. No motion, observation lease, real source or board authority is granted.

H01-H15: DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
design1011259415a0916054eb580687612580bc1e5f09. A input
66aa291d7f01cc3cfefb8c30c4e8ad3aec6547bd. Full 3D/UI, solid collision,
free camera/layouts, complete equal-gate passage, hidden truth, causal source,
online 3D PC AI and both control paths are retained. Physical board is A-only.

## Accepted scope and boundaries

The [candidate layout and APIs](../../../../golden/codec/TRACE_CANDIDATE.md)
define every payload byte/bit, independent anchor, E/RAW/Rice, actual acquisition
index/ticks, quality flags, source-update origin, padding and exact byte cost.
Payload<=32B and full frame<=46B. Irregular selection is split without invented
points; every valid singleton fits. Uint64/low32-rollover examples are synthetic
future-layout proposals, outside current A ADC tick bounds. Source authenticity,
physical-unit mapping, clock error bounds, C grouping/model adaptation, BOOT
digest, live transport and actual scheduling remain explicit approval gates.

The implementation is standalone Python arithmetic. It reproduces the pinned
inner codec equations but stores anchor/RAW words little-endian. Rice k minimizes
significant bits (lowest k on a bit tie); the subsequent mode comparison uses
padded bytes and RAW wins byte ties. The saved design spec described a possible
call into the inner fixture decoder; that call structure is not used. Independent
arithmetic/bit parsing below checks the actual standalone implementation.

## Rejection and correction

The original worker source passed72 unit tests, independently rerun by main, but
was rejected on two hand-computable cases. TC01 selected k0/27bits where the
unchanged inner convention requires k1/26bits. TC02 accepted age1001 at tick1000,
producing source_tick=-1 and advancing receiver state. Original bytes are under
`rejected-original/`; raw exit1 evidence is `main-original-negative.*`. This is
a preserved negative control, not a passing result. The current source rejects
the malformed time before state mutation and fixes k selection. TC03 also makes
fixture regeneration use explicit paths instead of B-private directory ancestry.
Main also added TC04: the generator requires a fresh output directory; existing
output and input-alias attempts are rejected with prior bytes unchanged. Its
pre-guard source is preserved in generator-before-output-guard.py. Main's own
initial vector audit assumed no enrichment fields; that assumption was refined
to preserve every pinned field exactly and independently check the three explicit
enrichments. Both reviewer versions/provenance are retained.
Historical worker generator/logs describe rejected bytes; current reproduction
uses `competition/deepeye/evidence/codec/trace-candidate-20261017-05/correction1/make_trace_vectors.py`. Old logs were not rewritten.

## Main validation

- 149 targeted codec unit tests pass; prior inner codec and61 original
  vector bytes remain unchanged.
- Independent oracle imports no product codec:8 manual vectors,800 arithmetic
  blocks,80 residual streams,40 exhaustive longest-prefix comparisons,35 uniform
  128-point profiles,5264 raw/re-CRC bit mutations, bounded receiver ordering,
  duplicate/conflict/close/alias checks and strict input type tests.
- 1792 independent per-frame byte ledgers checked. All four channels'
  128 selected synthetic points restore their exact index/tick/quality/source
  metadata; valid value errors respect E. At E0 the512-point sparse fixture is exact.
- Published fixture audit: {'manual': 8, 'independent_manual_enrichments': 8, 'independent_frame_ledgers': 118, 'synthetic_streams': 32, 'source_points': 994, 'packer_vectors': 2, 'malformed_rejected': 34}. Expected manual bytes are preserved verbatim;
  synthetic fixture generation uses the candidate, so its self-roundtrip is not
  counted as independent evidence. Main separately decodes and repacks every one.
- Minimal-directory generator reproduction produces byte-identical layout/vector
  JSON without a node-private tree. A fixed wire source still rejects type7:
  8 CRC agreements,16 direct rejections,48 HELLO recovery checks. The A check is
  compatibility/isolation evidence, not A acceptance of the new payload.

The independent sparse fixture has 968 selected valid raw
sample bytes, 636 stored code bytes, 6528 metadata
bytes, 3920 outer bytes and **11084 complete frame bytes**
(110840 8N1 line bits, 280 frames). Metadata dominates;
this is expansion, not a compression or real-time scheduling success. Flat128
points split41/41/41/5; short-held flat points split25-point blocks; long-held
points require singleton frames. See uniform-profile-ledgers.json in
`review-01/independent/`. All line counts exclude turns/guards/retries
because none were transmitted. No baud/latency/FPS result is inferred.

## Reproduce from repository root

Use new output paths; scripts preserve existing evidence.

```text
python -B -X utf8 -m unittest discover -s competition/deepeye/tests/codec -v
python -B -X utf8 competition/deepeye/evidence/codec/trace-candidate-20261017-05/main/main_trace_review.py --module competition/deepeye/golden/codec/trace_candidate.py --manual competition/deepeye/evidence/codec/trace-candidate-20261017-05/main/main_manual_vectors.json --output-root .local/new-trace-independent
python -B -X utf8 competition/deepeye/evidence/codec/trace-candidate-20261017-05/main/audit_public_trace_vectors.py --vectors competition/deepeye/golden/codec/trace_candidate_vectors.json --manual competition/deepeye/evidence/codec/trace-candidate-20261017-05/main/main_manual_vectors.json --output .local/new-trace-vector-audit.json
python -B -X utf8 competition/deepeye/evidence/codec/trace-candidate-20261017-05/correction1/make_trace_vectors.py --golden competition/deepeye/golden/codec --manual competition/deepeye/evidence/codec/trace-candidate-20261017-05/main/main_manual_vectors.json --spec competition/deepeye/evidence/codec/trace-candidate-20261017-05/main/main_candidate_spec.md --output-dir .local/new-trace-generated
python -B -X utf8 competition/deepeye/evidence/codec/trace-candidate-20261017-05/main/check_trace_regressions.py --module competition/deepeye/evidence/codec/trace-candidate-20261017-05/main/rejected-trace_candidate.py --output .local/new-trace-negative.json
```

The last command intentionally exits1 with two reproduced findings. For the
corrected positive control, point --module to golden/codec/trace_candidate.py
and use a different output path. `main-acceptance.json` binds the actual reviewed
source hash and all raw command captures; the operation manifest binds final
Git blobs. A/C feedback must identify operation/request_hash/tested_commit.
