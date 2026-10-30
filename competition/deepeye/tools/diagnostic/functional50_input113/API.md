# B117 Original Scan Input Normalizer

Status: **SOURCE ONLY**. The candidate module has not been imported, compiled,
executed, or tested. This API is a pure byte-to-data boundary, not a producer,
physical adapter, current-source assertion, or acceptance record.

## Contract

- Task: `DEEPEYE-IMPLEMENTATION-20261014/v1`.
- Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01-H15, pinned at
  `f5989cd5defce561f9ba98e6b18fc2682945f0a2`.
- Canonical requirements SHA-256:
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
- H01-H15, both H12 paths, original29, final 100 MHz, 1 percent, and 100 ms
  remain unchanged. None is established by this software API.
- Node A alone operates the physical board. `SOFTWARE_FAKE_CSR` and other
  software-only evidence remain distinguishable from real board evidence.

## Public Boundary

```text
normalize_external_original_scan_v1(
    request_bytes: bytes,
    source_scan_bytes: bytes,
    companion_bytes: exactly four bytes objects
) -> NormalizedExternalScanV1

physical_start(*args, **kwargs) -> fixed STOP dictionary
```

The normalizer performs no I/O, imports no legacy decoder or fixture, accepts no
callback/device handle/authority boolean, and preserves the exact request,
source, and four companion byte strings. It accepts one request, one scan, and
exactly four ordered lanes.

## Request Envelope

The request is one strict UTF-8 JSON object with exactly these top-level keys:

```text
schema, task, source_provenance, source_payload, scan, lineage,
association, companions
```

`schema` is `B113_EXTERNAL_ORIGINAL_SCAN_REQUEST_V1`. Every nested object has an
exact key set; unknown and missing keys are refused.

| Area | Required content and limits |
|---|---|
| `task` | Exact task ID/version 1 and fixed requirements SHA-256. `work_id` is caller-supplied printable ASCII, 1..192 bytes. |
| `source_provenance.class` | `NEW_ORIGINAL_LIVE_ROOT`, `HISTORICAL_ORIGINAL`, or `SYNTHETIC_TEST`, copied only as a declaration. |
| `source_provenance.mapping_state` | Only `B_NEUTRAL_AWAITING_A_MAPPING`. |
| `source_payload` | Opaque ASCII format label, exact body length 1..1048576, and matching SHA-256. |
| `scan` | One uint63 scan ID, exact uint63 origin/acquisition QPC, printable ASCII clock ID, and four lanes. |
| `lane.raw_sample_uint16` | Null only for invalid lanes; valid values preserve all 0..65535 values without truncation. |
| `lane.root_quality_uint16` | Opaque uint16, copied without inference. |
| `lane.mapped_flags` | Supplied booleans `valid`, `saturated`, `held`, `source_fault`; never inferred from quality or sample value. |
| `lane.staged_quality_uint4` | Exactly `valid + 2*saturated + 4*held + 8*source_fault`, range 0..15. |
| `lineage` | Caller-supplied operation/request/commit/build/boot/session/tag/trigger/generation/sequence fields, bounded and copied. |
| `association` | Caller-supplied profile/binding/e/source-context/timestamp/quality/receiver/evaluation/clock/freshness fields, bounded and copied. |
| `companions` | Exactly channels 0..3, each 1..262144 bytes; bodies are complete opaque byte strings in channel order. |

Limits are inclusive: request 1..262144 bytes; source 1..1048576 bytes; four
companions 4..1048576 bytes total; all input 1..2097152 bytes; JSON depth 12;
any string 1024 UTF-8 bytes. JSON floats, NaN/Infinity, duplicate keys, BOM,
invalid UTF-8, surrogate text, and integers outside the bounded schema range are
refused. The four companions are not interpreted as any invented A schema.

## Temporal Gate

`scan.clock_domain_id`, `association.receiver_clock_id`, and
`association.evaluation_clock_id` must all be printable ASCII and exactly equal.
This declared equality is checked **before any timestamp comparison or
subtraction**. It does not prove synchronization, calibration, a common source,
or physical simultaneity.

Only after that gate are these computed:

- Acquisition QPC equals `origin_qpc_ns + acquisition_tick_us*1000 +
  acquisition_remainder_ns` without uint63 overflow.
- Every lane acquisition equals the one scan acquisition.
- A valid lane source equals `origin_qpc_ns + source_tick_us*1000 +
  source_remainder_ns`, is not after acquisition, and `held` equals strict
  `source_qpc_ns < acquisition_qpc_ns`.
- `origin_qpc_ns <= acquisition_qpc_ns <= receiver_qpc_ns <=
  evaluation_now_qpc_ns`.
- All lanes share the lineage session and one view; frame sequences are
  uint16 values strictly increasing without wrap.

For valid lanes only, declared-clock age is
`evaluation_now_qpc_ns - source_qpc_ns`. `freshness_limit_ns` is fixed to
`100000000`; the age is classified with an inclusive `<= 100000000` boundary.
Every freshness record carries `declared_clock_only=true` and
`clock_domain_authenticated=false`. Invalid lanes have null age and
`NOT_APPLICABLE_INVALID`, not a fabricated age.

## Exact Bytes And Labels

`NormalizedExternalScanV1` retains:

- `request_bytes`, `source_bytes`, and `companion_bytes` as the exact input bytes;
- exact source/companion metadata dictionaries containing those same byte strings;
- normalized scan, lineage, association, integrity, mapping, and authority data;
- `execution_route="PURE_UNBOUND_DATA"`.

`to_jsonable()` returns schema `B113_NORMALIZED_EXTERNAL_SCAN_V1`, declared
provenance, request hash, source/companion metadata without body bytes, scan,
lineage, association, integrity, mapping, authority, and the execution route.
Body bytes stay on the object; they are not silently reserialized or dropped
from the object.

Byte/hash consistency is not authentication. The following remain false:

```text
producer_authenticated
boot_authenticated
current_source_authenticated
clock_domain_authenticated
association_semantics_bound_to_companion_bytes
supplied_association_hashes_semantically_verified
supplied_lineage_request_hash_verified
source_numerical_association_verified
physical_start_authority
physical_ready
product_acceptance
```

Declared provenance classes are copied and marked `declared_only=true` and
`authenticated=false`. A declared original label does not mint Root, current,
boot, producer, load, clock, H12, or product authority.

`legacy_host103_numeric_compatible` is only a NON_AUTHORITY observation that
all valid raw values are at most 4095. Values 4096..65535 remain normalized
uint16 data and are never truncated or relabelled. No legacy adapter,
`to_fake_plan103`, old commit fabrication, Host103 import, or fake/current
mapping is created.

`staging_shape_ready` is data-shape-only. It is true only when at least one
lane is valid, every valid raw value is at most 4095, and both tag and 128-bit
build ID are nonzero. It never means current admission, monotonic device tag,
loaded build, authenticated boot, physical readiness, or acceptance.

`physical_start(...)` returns exactly:

```json
{"status":"STOP","provider":"A_ORIGINAL_PROVIDER_UNAVAILABLE","physical_start_authority":false,"product_acceptance":false}
```

It neither inspects nor invokes supplied arguments.

## Refusals

All validation failures raise `Refused`, a `ValueError` with stable `code` and
JSON `path` fields. Messages do not echo caller-controlled payload values.

```text
ACQUISITION_MISMATCH ASSOCIATION_E BODY_CONTAINER BODY_COUNT BODY_TYPE BOM
CLOCK_DOMAIN_MISMATCH COMPANION_CHANNEL COMPANION_LENGTH COMPANION_SHA
COMPANION_SIZE COMPANIONS_LENGTH ENUM FRAME_ORDER HELD_MISMATCH HEX_FORMAT
HEX_LENGTH INVALID_FLAGS INVALID_NULL INVALID_SOURCE JSON_DEPTH
JSON_DUPLICATE_KEY JSON_FLOAT JSON_INTEGER_RANGE JSON_NONFINITE JSON_SYNTAX
JSON_TYPE KEYS LANE_CHANNEL LANES_LENGTH PRINTABLE_ASCII QPC_EQUATION
QPC_OVERFLOW RANGE REQUEST_SIZE REQUEST_TYPE SESSION_MISMATCH SHA256_FORMAT
SHA256_LENGTH SOURCE_AFTER_ACQUISITION SOURCE_LENGTH SOURCE_SHA SOURCE_SIZE
SOURCE_TYPE STAGED_QUALITY STRING_RANGE STRING_SURROGATE TASK_ID
TASK_REQUIREMENTS TASK_VERSION TIMESTAMP_ORDER TOTAL_INPUT_SIZE TYPE UTF8
VALID_SAMPLE VALID_SOURCE VIEW_MISMATCH
```

Malformed/too-deep JSON is translated to `JSON_SYNTAX`/`JSON_DEPTH`; oversized
integers are bounded before conversion to `JSON_INTEGER_RANGE`.

## Future Focused Test Entry

This command is **proposed and not run** in the source phase. From this
directory, with a nonexistent output directory whose parent already exists:

```text
python test_input113.py --output <FRESH_TEST_OUTPUT>
```

The runner defines 33 in-memory cases, sets `sys.dont_write_bytecode=true`
before importing the candidate, creates only the supplied output directory with
exclusive `parents=False` semantics, writes only `RESULT.json`, and refuses an
existing output. It uses no subprocess, network, fixture import, board, MMIO,
overlay, SSH, SQL, service, credential, or publication path. Case summaries and
an embedded overall exit status are retained in `RESULT.json`.

Expected exit status: `0` all cases pass; `1` a case fails or the 60 second
runtime bound is exceeded; `2` setup/output refusal. The serialized result is
bounded below 4 MiB. A later main-owned execution assignment must choose a fresh
output directory and run it once under supervision.

## Non-Claims

This source does not establish A's exporter/custody schema, an A numerical
mapping, a current Root/BOOT, loaded build, authenticated producer, qualified
BIT/HWH, actual ADC or motion, either H12 path, final 100 MHz/1 percent/100 ms,
original29 completion, H01-H15 product acceptance, or physical readiness.
Build111 remains terminal-failed; no vendor launch or new build is implied.
