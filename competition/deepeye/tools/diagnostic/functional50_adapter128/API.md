# Adapter128: original scan to TRACE94 data and intents

Source phase only. No candidate imports or test/runtime execution occurred in
work `B-DEEPEYE-ORIGINAL-TRACE94-ADAPTER-20261031-128`. Main owns independent
review, freezing and the separately selected first test operation129.

The module performs no MMIO, device discovery, PYNQ, load, clock, network,
vendor, subprocess or callback execution. Fixed Python dependencies are read
and hash-checked at import from the repository/snapshot root. The normalizer
and codec then operate on data only. Relative intents do not grant physical,
source, producer, clock, same-boot, load, Root/BOOT, H12 or product authority.
A alone supplies the original physical producer and executes effects.

H01–H15 remain fixed at contract `f5989cd5defce561f9ba98e6b18fc2682945f0a2`,
requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, and
freeze `1011259415a0916054eb580687612580bc1e5f09`. All29, both H12 paths,
full game-grade 3D/UI, collisions, editable/free layouts/views/faces, equal
gates/full passage, hidden truth, causal observations, online3D, substantive
PC AI, final100MHz and1%/100ms remain unchanged and unaccepted here.

## Original input and representability

`prepare_bytes(request_bytes, source_scan_bytes, companion_bytes,
build_binding=...)` accepts exactly the original input113 byte arguments.
`prepare_normalized(normalized, build_binding=...)` accepts the exact pinned
`NormalizedExternalScanV1` type and re-normalizes its retained byte arguments;
its mutable dictionaries and old authority fields are not trusted or propagated.
Both return `Preparation(status, reason, original, plan,
authority_not_evaluated)`. `original` retains exact request/source/four full
companion byte strings. `original.inventory()` is metadata, never a substitute
for those bodies. Refusals return `REFUSED_WITH_ORIGINAL_BYTES` and `plan=None`.
Non-byte arguments and companion input cardinality other than four are structurally refused before materializing their containers, without invoking caller methods. Ordinary byte-data refusals retain the complete original bodies.

No historic104 commit, `SOFTWARE_FAKE_CSR` kind, fake plan, invented source
identity, or reconstructed legacy profile is needed. Provenance classes remain
caller declarations. Plan/correlation data has `authority_not_evaluated`, not
an unconditional current eligibility, STOP, core or command decision.

The unchanged input113 normalizer checks the exact envelope, bounds, duplicate
JSON keys, four ordered lanes, common acquisition/session/view, strictly
increasing nonwrapping frame sequence, exact uint63 origin/time equations,
remainders0..999 and declared equal clock IDs. Its declared equality is not
measured synchronization. Adapter128 checks all lanes before a reducer exists
or any write can be yielded:

| Input field | TRACE94 / codec mapping |
|---|---|
| valid `raw_sample_uint16` | Exact count0..4095.4096..65535 refused; never scaled/truncated. |
| invalid raw sample | Remains `None` in retained input and decoded facts; the actual PUSH register uses the specified zero padding. |
| valid zero | Exact integer0 with valid bit set, distinct from invalid and an invalid FIFO peek. |
| `root_quality_uint16` | Retained opaque0..65535; no invented relation to flags or legacy uint8 quality. |
| `mapped_flags` | Exact valid/saturated/held/source_fault booleans from113. |
| `staged_quality_uint4` | Exact valid +2*saturated +4*held +8*source_fault; separate from opaque root quality. |
| acquisition/source times | Exact original QPC and relative ticks/remainders retained. Invalid source remains null; BIND uses specified zero placeholders only. |
| profile / E | `TRACE-PAYLOAD-1US-PRIVATE-v2`, E=0 only. |
| held source | Requires source tick_us < acquisition tick_us as well as original113 nanosecond ordering. Held within the same relative microsecond is refused without rebasing. |

The E=0 limit comes from corrected94 RTL line421 `.assoc_e(4'd0)` (nearby
singleton count1) and the held limit from unchanged `trace_candidate.py`
lines208–216 `_check_point` plus its strict payload held-age checks. Pins bind
actual files: RTL
`d7f9526e17b8e899eddd35c590a7d2028c429ebed6a1151675c70c9d520d69f1`;
codec `a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642`.
No RTL or codec bytes changed. The prepared tests exercise arbitrary external
numeric values and opaque companions rather than matching historical fixtures.

## Build and operation association

`build_binding` is an exact plain dictionary with four bounded string fields:

```
canonical_build_id_full_sha256
source_closure_file_sha256
operation_id
request_hash
```

The first is specifically the full256 digest defined by the pinned
`functional50_contract.compute_build_id`: SHA256 over its
`canonical_closure_payload`, excluding derived BUILD_ID fields and the closure
file's own hash. Its first32 hex characters must equal input113's nonzero
`lineage.build_id_hex128`. The second is the SHA256 of the actual serialized
`source_closure.json` file bytes. It is a different namespace and is retained
separately. Operation/request identities must exactly match input113 lineage;
the request hash is not substituted for either build hash.

Adapter128 checks a **declared canonical-digest prefix relationship** only.
It does not receive or validate the closure file, recompute the canonical
closure, authenticate request identity, or claim actual loading. A/main must
verify original closure content with the existing contract, retain the file,
and associate all three digest namespaces with actual same-boot/load evidence.
`closure_contents_verified=false` and the explicit declaration label make
this limitation machine-readable. PINS distinguishes the source contract/hash
and tested dependency commits from any new build artifact.

## Reducer protocol for A

Construct `Reducer(preparation.plan, limits=None)`, call `begin()` once, then:

```
intent = reducer.advance(phase_elapsed_ns=work_elapsed_ns)
# A reserves and persists the original intent plus bounded response space.
# A alone performs the selected TRACE-relative read32/write32 once.
intent = reducer.advance(observation, phase_elapsed_ns=work_elapsed_ns)
```

Each intent contains stable `operation_id`, monotonically increasing `call_id`,
`kind`, TRACE-relative aligned `offset`, full32 `value` or null, `label`, `poll`,
`window=TRACE_HWH_RELATIVE`, phase, deadline, and a2048-byte evidence reservation.
There is at most one pending call. A maps only the exact aligned4KiB TRACE
window from its verified HWH; the second G05 window must remain distinct and
nonoverlapping. No bases are guessed by this module. Static HWH structure and
CSR constants do not prove currently loaded image, actual PS clock or source.

Observation has exactly `operation_id`, `call_id`, `status`, `value`,
`error_code`. Status is one of:

| Status | Meaning to this reducer |
|---|---|
| `confirmed_read` | Exact uint32 returned for the pending read. |
| `confirmed_write` | A reports completed pending write; value/error_code null. |
| `error` | Original call returned an error; error_code is null or bounded96 characters. Write effects stay conservatively unknown. |
| `unknown` | Completion/effects are unknown. Capability is consumed, never reissued. |
| `not_attempted` | A did not call the device. This intent is still consumed; no automatic retry. |

Mismatched/replayed call identities are refused and cannot advance the sequence.
They do not silently resolve a pending call. A must submit the actual outcome
or explicit unknown for that original call before cleanup. These are data
records, not authentication or a caller-supplied verified-boolean gate.
One-use state belongs to this reducer instance. A must also fence the original
operation durably across process restarts or construction of another instance;
this transport-free module cannot supply that cross-process ownership authority.

Initial identity/BUILD_ID and dirty-state checks are read-only. The nonzero
tag must exceed the last tag; result/POP/RX counters need enough nonwrapping
headroom for one scan. Dirty/identity/input refusal emits no writes and cannot
start cleanup or collection. Four fresh PUSH, four fresh BIND/result/ACK and
strictly correlated result ID/RX totals complete one scan. There is no rearm,
reset, CLEAR_FAULT or CLEAR_FIFO. G05 writes, including G05 STOP, are zero.

After the scan finishes, `begin_collect()` may be called once. The reducer
observes CANCEL/COMPLETE, quiescence and RXidle before reading FIFO count and
destructive POP. Each peek requires bit8 independently of byte value. It stages
the next POP ID, emits one POP, then confirms both ID and count before appending
the byte. Unknown/failed POP or budget exhaustion retains confirmed prefix,
pending peek, last confirmed POP ID and last observed unread count. It does not
pad/trim/clear or begin a second collection.

Cleanup ownership is established by an original attempted ARM observation,
including unknown/error, never just by yielding an ARM intent. An unattempted
ARM has no ownership. `begin_cleanup()` requires no unresolved intent, owned
ARM and an unused CANCEL. It emits at most one CANCEL and polls boundedly for
actual reported quiescence. Unknown ARM invalidates earlier preflight quiet
observations. A failure before collection may collect once only after observed
quiescence. No process exit or CANCEL issuance alone proves FPGA stopped.

`snapshot()` preserves the full original bytes, declared build association,
actual logical counters, events, errors, results, pending intent, unknown state,
confirmed prefix and last observations. It is an in-memory data object; A must
serialize/persist it and original bodies according to its own bounded executor.

## Bounds and producer obligations

One four-lane scan, one ARM, one collection, <=4frames/252 normal wire bytes,
4096 retained failure bytes,65536 CSR intents,2048 progress polls,128 non-POP
writes,4096 POP commands and4096 POP-ID stages. Cleanup has256 polls. Every
yield spends logical budgets first, including finite budgets for all loops.
An intent consumes its count even when A later reports not_attempted.

Work10s and cleanup2s use separately reported nondecreasing elapsed nanoseconds.
A supplies/enforces the original monotonic clock and finite MMIO/owned watchdog.
Nominal15s parent supervision is not a guarantee that a hung MMIO returns.
Already returned outcomes remain recordable after deadline; no subsequent
effect is scheduled past it. No local clock getter or physical call is hidden.

Logical evidence partitions are6MiB work +1MiB cleanup +1MiB final. Full input
bodies plus4096 metadata bytes are charged to work at construction; each call
reserves2048 bytes for bounded intent/outcome records. Final1MiB is fixed and
unavailable for more work. Only operational counters/time/work/cleanup evidence
limits may decrease. A must actually reserve/persist these artifacts before
effects; in-memory budgeting is not a durable-storage claim. Source/archive
storage is separate from link cost. All mandatory complete companion bytes are
counted with wire in correlation results, never reduced to hash-only cost.

## Collected-frame correlation

`correlate_collected(plan, wire_bytes, complete_companion_bytes, result_rows)`
returns correlation facts plus retained original/wire/companion bytes on both
success and refusal. Four result rows contain id/error/bytes/rx_before/rx_end;
the reducer provides actual observations plus channel/sequence fields. The
adapter checks IDs/nonwrapping RX continuity, exact lengths, four frames and no
extra bytes, ABI3/E4 identity, session/view/sequence, CRC, singleton channel,
count/value/quality/index/acquisition and source ticks against the frozen plan.

It uses the **unchanged** `trace_candidate.decode_payload` on revision2's code
section with only its revision byte mapped to1, the same code-section convention
as the existing strict private wrapper. Envelope/CRC checks are in adapter128.
The old `deepeye_transport50_source_candidate.decode_transport` authority view
is not called and no synthetic legacy profile is built. Its source is pinned
as the reference for that convention; the result names the parser actually used.
There is no new codec or encoder in the implementation.

Complete supplied companion bytes must equal those frozen by input113. This
proves byte identity only. Source format and companion semantics remain
`OPAQUE_NOT_INTERPRETED` / `OPAQUE_NOT_VERIFIED`, even when wire values match.
A must supply the original exporter/custody and semantic association; current
eligibility cannot be inferred from JSON, hashes, wire correlation or this API.

## Prepared test entry, not run

`python -B test_adapter128.py --out <absolute-new-directory>` uses exclusive
mkdir with an existing parent. It runs nine newly affected groups defined in
`TEST_PLAN.md`, writes structured `RESULT.json` with group results/overall exit,
exact source hashes and dependency pins, and emits a short stdout receipt.
The main-owned supervisor captures raw stdout/stderr. Normal exit0, any failed
group/import exit1, existing output exit2. No retry/subprocess/old-suite/board
operation. Expected result stays below512KiB, stdout is bounded, and no need
to increase main's15s/512MiB/native16/sample16/1MiB supervision was identified
by source inspection. This is a source estimate, not measured execution.

## Main130 pre-runtime correction

After actual author128 release, main preserved the exact original source commit437717d4d833450d1466030b8ce0034bf69f44db. Consumers now re-normalize retained original byte arguments and build binding when producing facts, constructing the reducer and correlating frames. Mutable cached scan/lineage dictionaries are not another input route; consumer state is reconstructed from original bytes. This is consistency only, not authenticity or durable ownership. Changed original bytes must independently satisfy the same representability checks.

Companion containers are bounded before traversal/copy. Correlation preserves a short supplied set as a mismatch refusal, while more than four is a structural refusal. Result-row field count is bounded. Nonzero refusal or an inconsistent supplied result status is rejected; the reducer never ACKs a nonzero-refusal result as success. Main added one affected boundary group and tightened logical budget assertions. No candidate runtime occurred during this correction phase; first129 remains main-selected after exact source freeze.

The new focused test also retains three exact software sample bundles and one complete compact intent/observation transcript for independent saved-byte review. All are explicitly synthetic data; no board or current-source claim.
