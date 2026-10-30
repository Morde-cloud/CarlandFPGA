# B113 Original Numerical-Source Input Interface Proposal

Status: **PROPOSAL ONLY, AWAITING MAIN ARCHITECTURE DECISION**. No source,
import, syntax check, test, execution, board operation, service, network, SQL,
credential use, Git write, or publication occurred in this phase.

## Contract And Scope

- Task: `DEEPEYE-IMPLEMENTATION-20261014/v1`; work:
  `B-DEEPEYE-ORIGINAL-INPUT-INTERFACE-20261031-113`; main:
  `01a18824-4172-74e2-a13f-f3e3d1e3ed99`.
- Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1` at
  `f5989cd5defce561f9ba98e6b18fc2682945f0a2`. The independently recomputed
  canonical requirements hash from the raw Git JSON blob is
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
- Only a later explicit instruction from the same human may change H01-H15.
  Both H12 control paths, the original 29-gate set, final 100 MHz, 1%, and
  100 ms targets remain mandatory and unaccepted. A alone operates the board.

H01-H15 carried semantics: H01 game-grade 3D modeling/rendering/UI; H02 hollow
edge-only central cube; H03 solid drill/obstacle volumes and volume collision;
H04 interactive free camera while running or paused; H05 free/random editable
water/hard-rock and other layouts; H06 free legal entry/exit faces and points;
H07 equal blue/red gates and complete volume passage; H08 hidden initial truth
with causal observations only; H09 evidence-based causal sensing and original
signal constraints; H10 online 3D joint board/algorithm decisions; H11
substantive PC AI perception/mapping/planning; H12 both PC-direct control from
real board observations and PC-AI-to-FPGA-to-board output, each with honest
source/observation/timeliness evidence; H13 all demonstration and control
items remain hard acceptance gates; H14 every later main/session/child must
read and preserve this contract and pin; H15 only a new human instruction may
change it, while genuine blockers are reported rather than hidden.

## Evidence Read

| Dependency | Actual pin |
|---|---|
| A33 message result | `P/dependency111-event/RESULT.json`, 3599 bytes, SHA-256 `203074e313c1f779965e8ed60280780abed52f03792ebdc4757244337d4f4637` |
| Host103 main review | 6889 bytes, SHA-256 `16deb5151eabfe879b95980f58dac224a03e5f591796514014a480b6245ffe80` |
| Diagnostic source freeze | Host103 at `cb754311ec11bba5575b8dbf331f6c209b1fd49f`; reviewed 137 files/34 Git blobs, nine software groups passed |
| `functional50_host103/host103.py` | 15241 bytes, SHA-256 `2ba19c9c6de68b3ae0189166a663cc5999c07ce73a5227cd4095fa24d803f06b` |
| `raw4_adapter92.py` | 29312 bytes, SHA-256 `c9fd0714311d9ff38c38083e137aadca4e27c2992c057a1c304b1784e9b6e1a5` |
| Corrected 94 RTL | 44406 bytes, SHA-256 `d7f9526e17b8e899eddd35c590a7d2028c429ebed6a1151675c70c9d520d69f1` |
| 94 register map | 18005 bytes, SHA-256 `3ad9a9c1c6f7d69c173d471bb77ffcc6ead76490598a8da5efa0861600aa0c70` |
| Strict transport decoder | 12535 bytes, SHA-256 `1f4da870d9c885a3cc6156c30d2170e21001187392a59a19172c059c9ab0c768` |
| Decoder code section | 40546 bytes, SHA-256 `a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642` |

A33 requires a numerical-source API for **new original live Root values,
quality, and causal association**, not selection from retired hard-coded
arrays. The first actual RTL route remains `SOFTWARE_FIXTURE/source4`; it must
not mint production BOOT, ADC, motion, or H12 authority. B has not taken the
bytes or schemas of announced A actor `51c48...` or serial `105`; no API is
fetched, adopted, or invented from those announcements. Build111 at `.local/b111`
was not touched or imported; work112 is separate.

## Proposed Boundary

The only proposed public function is a pure byte-to-data normalizer, not an
executor:

```text
normalize_external_original_scan_v1(
    request_bytes: bytes,
    source_scan_bytes: bytes,
    companion_bytes: exactly four bytes objects
) -> NormalizedExternalScanV1
```

It accepts no callable, device handle, `verified` boolean, expected-authority
flag, or physical provider. It performs no I/O. Physical start remains
unconditionally `A_ORIGINAL_PROVIDER_UNAVAILABLE` until A supplies and the
quality main reviews a concrete producer/custody/load/clock/MMIO interface.

The wire envelope is one strict UTF-8 JSON request plus three body parts:
`source_scan`, and `companion000` through `companion003`. The request carries a
descriptor (format label, byte length, SHA-256) for every body part. The exact
body bytes are copied whole and never replaced by reserialized JSON.

### Fixed Limits

- Request JSON: 1..262144 bytes; UTF-8 without BOM; no duplicate object keys;
  no NaN/Infinity/floats; only null, bool, int, str, list, and dict.
- Original source-scan bytes: 1..1048576 bytes.
- Each companion: 1..262144 bytes; exactly four, ordered channels 0..3.
- All four companions together: 4..1048576 bytes.
- All input bytes together: at most 2097152 bytes.
- One request means one four-lane scan, one origin, one acquisition tick.
- Identifier strings are printable ASCII, 1..192 characters; notes are UTF-8
  up to 1024 characters. No unbounded metadata or arrays.

## Request Fields

The exact machine-readable field/type/limit table is in
`INTERFACE_PROPOSAL.json`. The principal fields are:

| Field | Type and limit | Rule |
|---|---|---|
| `schema` | string constant | `B113_EXTERNAL_ORIGINAL_SCAN_REQUEST_V1` |
| `task.task_id`, `task.work_id` | printable strings <=192 | copied, never normalized to a retired ID |
| `task.task_version` | integer 1 | exact |
| `task.requirements_sha256` | lowercase 64-hex | must equal the fixed contract hash |
| `source_provenance.class` | enum | `NEW_ORIGINAL_LIVE_ROOT`, `HISTORICAL_ORIGINAL`, or `SYNTHETIC_TEST` |
| `source_provenance.mapping_state` | enum | now only `B_NEUTRAL_AWAITING_A_MAPPING`; this is not authentication |
| `source_payload.format_label` | printable string <=192 | opaque label; B113 invents no A schema |
| `source_payload.bytes`, `.sha256` | integer 1..1048576; 64-hex | must match the supplied raw source body exactly |
| `scan.origin_qpc_ns` | integer 0..2^63-1 | copied exactly; never rebased |
| `scan.acquisition_qpc_ns` | integer 0..2^63-1 | common scan tick |
| `scan.lanes` | array of exactly four | ordered channels 0,1,2,3 |
| `lineage.*` | bounded exact fields | operation/request/commit/build/boot/session/tag/trigger copied from caller |
| `association.*` | bounded exact fields | profile/binding/receiver/evaluation/source-context data |
| `companions` | exactly four descriptors | channel/format/length/SHA-256 for complete opaque bytes |

Each lane contains `channel`, nullable `raw_sample_uint16`, opaque
`root_quality_uint16`, supplied `mapped_flags` (`valid`, `saturated`, `held`,
`source_fault`), supplied `staged_quality_uint4`, exact acquisition/source QPC
fields, tick and remainder fields, `session`, `index`, `view`, and `frame_seq`.
No flag is inferred from raw quality, count, saturation, or time.

Cross-field rules:

- `valid=true` permits an integer raw sample `0..65535`; zero is valid data.
  `valid=false` requires `raw_sample_uint16=null`, source QPC/tick/remainder
  all null, and saturated/held false. Invalid has no numeric zero surrogate.
- `staged_quality_uint4` is supplied and must equal
  `valid | saturated<<1 | held<<2 | source_fault<<3`; this is consistency
  checking, not quality inference.
- `origin + acquisition_tick_us*1000 + acquisition_remainder_ns` must equal
  the uint63 acquisition exactly, without overflow; all four lanes must use
  the one scan-level acquisition tick.
- For valid data, `origin + source_tick_us*1000 + source_remainder_ns` must
  equal the uint63 source exactly; source must not exceed acquisition; held
  must equal `source < acquisition`. Remainders are 0..999.
- `frame_seq` is 0..65535 and strictly increases across the four lanes. Result
  and POP IDs are downstream reducer-owned exact counters; callers cannot
  supply or reset them.
- `lineage.session_id` must match every lane session; lane views must agree.
  Tag zero or an all-zero build ID may be preserved as historical data but
  makes a record not staging-ready; no fallback value is invented.
- The association ordering is `origin <= acquisition <= receiver_qpc_ns <=
  evaluation_now_qpc_ns`. The 100 ms freshness result is computed and labelled;
  it is not turned into producer authentication.

## Authority Labels

The output keeps three independent dimensions:

1. **Declared source provenance**: new original, historical original, or
   synthetic test. It is caller-declared and unauthenticated.
2. **Execution route**: pure unbound data, `SOFTWARE_FAKE_CSR`, or
   `SOFTWARE_FIXTURE_SOURCE4`. Fake test execution is never physical evidence;
   source4 RTL remains a fixture route even when its input numbers are new.
3. **Authority evidence**: producer authentication, boot authentication,
   current-source eligibility, physical-start authority, and product acceptance
   all remain false until separately established.

Hashes establish byte consistency only. No declared lineage field is promoted
to current producer, loaded image, BOOT, ADC, motion, H12, or product proof.
Supplied association hashes remain opaque until A supplies a reviewed mapping;
the normalizer computes request, canonical-association, and companion-set
hashes for evidence, but those are consistency values, not authentication.
There is no `current_source_eligible` request field that a caller can set true.

## Mapping To Host103 And The 94 Endpoint

| Normalized input | Host103 pure plan | 94 staging |
|---|---|---|
| lineage tag | `arm_tag` | write `0x100`; ARM command `1` after clean CANCEL/quiescence |
| scan origin | `origin_qpc_ns` | write low `0x104`, high `0x108` with high bit 31 zero |
| lineage build ID | 32-hex `build_id` | expected at `0x060..0x06c`; zero refuses ARM |
| lane channel/value | lane `channel`, `count` | `0x110`, `0x114` (invalid padded with zero) |
| common acquisition | `acquisition_qpc_ns` | `0x118/0x11c` |
| supplied mapped flags | 4-bit `quality` | `0x120` |
| session/index | lane `session`, `index` | `0x130`, `0x134` |
| acquisition tick/remainder | matching lane fields | `0x138`, `0x13c` |
| source QPC/tick/remainder | matching lane fields | `0x140/0x144`, `0x148`, `0x14c`; invalid uses zeros |
| lane view/frame sequence | `view`, `frame_seq` | `0x150`, `0x154` |

Host103 then emits exactly four ordered PUSH, BIND, result/ACK observations,
one collect, exact nonwrapping result/POP IDs, and one-scan limits. The 94
register map independently confirms the same offsets and command gates. The
`source_kind` register is fixed at 4 (`SOFTWARE_FIXTURE`), so this path cannot
be labelled original RTL, production BOOT, ADC, motion, or final H12.

Host103 fake-kind restrictions that prevent direct physical use:

- `inspect_plan` requires `kind=SOFTWARE_FAKE_CSR`, an exact legacy plan key
  set, `original104_source_commit`, and a software provenance string.
- `TraceSequence.start` hard-codes source kind 4, 50 MHz, 1 Mbaud, and 4096-byte
  FIFO; `physical_start` always returns `A_ORIGINAL_PROVIDER_UNAVAILABLE`.
- `decode_collected` requires every companion to say
  `current_source_eligible=false`. Forcing new original data through it would
  either weaken the decoder or lie about current authority.
- Host103 validates numeric count as uint12 `0..4095`; 94 stages a 16-bit raw
  sample. B113 therefore preserves uint16 data at the neutral ABI and refuses
  silent truncation. A value above 4095 is not mapped to the unchanged Host103
  fake plan/current decoder profile without a new reviewed binding.
- `FakeExecution` accepts only its own `FakeCSR`; no caller callback or proof
  object is a physical enable.

The future adapter should be additive under
`functional50_input113/`. It can reuse pinned `host103.py` helpers
(`strict_json`, `canonical`, `uint`, `need`) and, where semantically valid,
the unchanged strict decoder. It must not edit Host103, copy retired arrays,
weaken the decoder, or construct a physical path. An optional
`to_fake_plan103` conversion may be used only for synthetic caller data and
must emit `SOFTWARE_FAKE_CSR`; original data must not be relabelled fake, and
fake data must not be relabelled original.

## Future Focused Acceptance Plan

After a separate explicit source permission and main freeze, create only the
new `functional50_input113` source/test set. Do not rerun Host103's nine old
groups, old RTL/model/PDE/codec/control suites, or the B111 vendor run.

One new focused normalization group with caller-provided synthetic bytes,
distinct from the old fixture, should cover: strict JSON/duplicate key/size
rejections; missing lineage metadata; one scan/four lanes/four companions;
uint16 bounds and no truncation above 4095; valid zero versus invalid null;
opaque quality with supplied flag consistency; null/zero/quality/time
contradictions; remainders 1000, source-after-acquisition, held mismatch,
origin/acquisition overflow and rebasing rejection; descriptor length/hash
mismatch; nonwrapping frame sequences; zero tag/build staging refusal without
fallback; historical/new/synthetic label separation; and no physical or current
authority from any boolean/hash. If a synthetic Host103 plan is checked, it is
pure intent mapping labelled `SOFTWARE_FAKE_CSR`, not execution.

## Genuine A Adapter Gaps

1. No concrete A-owned original exporter/custody schema has been received, so
   the structured relationship between source bytes, companions, quality, and
   lineage cannot be authenticated or parsed as A's schema.
2. No A mapping supplies how live Root values and causal association become
   B113 fields; B must not fabricate an envelope from actor/serial announcements.
3. No A proof makes build/boot/session/tag/trigger current or authentic; hashes
   and echoed IDs are consistency only.
4. No qualified same-run BIT/HWH, actual load/PS-clock observation, bounded or
   error-reported MMIO behavior, or A-selected physical record is available.
5. The current 94 RTL is source4 fixture only, with no production BOOT/ADC/
   motion or full H12; the strict decoder is a private relative-time profile and
   not a generic A-source parser.
6. No external G05 electrical/wiring confirmation, both real H12 paths, final
   100 MHz/1%/100 ms evidence, or original-29/H01-H15 product acceptance exists.

## Non-Claims

This proposal is not source authorization, an execute/START approval, a
physical adapter, a hardware bound, a current-producer assertion, or product
acceptance. A failed or unavailable A dependency must remain a labelled
blocker; no fallback or invented record is acceptable.
