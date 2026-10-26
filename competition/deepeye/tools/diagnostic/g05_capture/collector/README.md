# Bounded G05 collector — R2 pin/layout update

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; work
`B-G05-BOUNDED-COLLECTOR-20261026-59-v1`. Canonical author
`01a16ecb-340d-7e22-8a53-184264edb47d`; original main
`01a13b55-095b-7461-8dd5-5476a130bd82` owns independent acceptance.
The original bounded collector foundation was accepted by main at its exact
baseline pins. The subsequent bounded assignment
`B-G05-COLLECTOR-R2-PINS-20261026-59-v1` owns only collector.py, pins.py,
fixtures_author.py, this README and new test_r2_pins.py, with evidence under
`g05-capture-20261026-59/collector-r2-pins/`. It changes exact build pins and
launch layout only. Main retains independent acceptance; no commit/publication,
service changes or device operation are part of this assignment.

H01–H15/revision1 were read and verified at
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, canonical requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen design `1011259415a0916054eb580687612580bc1e5f09` remains unchanged.
This private diagnostic never grants motion: `movement_authorized=false`.
It does not close G05, fullH12, R03 or any formal acceptance card.

## Current evidence boundary

Only new synthetic/software controls were run on B, without PYNQ imports.
There is no accepted real package or board receipt from this author task.
Main reported R1 stopped before synthesis/bitstream because the literal DDR
preset check found derived T_RC48.91 versus raw preset50.625; its whole job
reached zero active processes. That is main's report, not an author build run.
R2 source acceptance names commit `c3d8595550eaa9b10f9d22b139788664a6501077`.
Its six RTL and five other build pins remain unchanged. The only three updated
build pins, verified against exact Git bytes and R2 MAIN_SOURCE_ACCEPTANCE.json,
are:

| Build file | SHA256 |
| --- | --- |
| build_g05.tcl | `6daddfcbbaf1e14f717aebcbb25e5299a5c82328a6dc9c3106de2094c5c451e8` |
| build_g05.py | `749a91e48da0d4597b6fa7cab1edf54334f4171a3ffcd67db3060a603a855061` |
| README.md | `1aeba291f95edec7c808970024c1227ca3dde2b4c371355577c72e903c7c7acc` |

The exact launch set additionally requires `inputs/vendor_ddr_preset.xml`,
pinned to `73566a941b442804a9c6b0eb42385b6c1cb82f12e354c138f8868005b91c52ed`,
and `inputs/ddr_literal.json`, `inputs/ddr_resolved.json`,
`inputs/ddr_resolution.json`. The existing `ps7_preset_parameters.json` and
`ddr_expected.tcl` remain required. No wildcard or generalized extra-input
allowance is added. The vendor XML is opaque hash-checked and snapshotted data;
it is not JSON. Derived DDR JSON bytes remain bound to the main-selected
manifest and same-run launch records, not independently reinterpreted by a
second DDR resolver in the collector.

The protocol, HWH guard, transport, STOP cleanup and runtime authorization
remain unchanged. Future pin/layout changes still require exact main input
and collector review. The running R2 build and its eventual actual package
are main-owned and are not read, invoked or validated by this task.

`test_r2_pins.py` runs only new offline marked-package controls. Its fixture
combines pinned actual sources/vendor XML with captured DDR resolver outputs
from the completed offline repair evidence. Those real input bytes do not
make the synthetic bit/HWH/completion/authorization into actual build proof;
`TEST_FIXTURE=synthetic-not-authority`, synthetic HWH and explicit offline mode
remain mandatory. Production mode rejects these packages. The test does not
run prior collector/RTL suites or import PYNQ. Main tests the real R2 package
separately after the build completes.

`protocol_pinned.py` is a byte-for-byte copy of parent `protocol.py`, SHA256
`cc54438dff2107037b9d0bfa2ed8c434cee62d55416081023b41922d05f7ed9c`.
`hwh_guard_pinned.py` is the exact build guard, SHA256
`1993f0b4d8d6c44d59642f9b2cfa1884c9ec814c7100ed560a734cf4b6c3562b`.
They are verified, snapshotted and loaded from those same bytes. The collector
does not reimplement or relax the parent's decoder, curvature, identity or TTL
rules. In particular `event-applied >= max(raw_ends)+8` remains mandatory.

## Offline CLI and package selection

Run with the current reviewed collector files together in this directory:

```text
python -B collector.py --package /one/explicit/build-package \
  --expected-manifest-sha256 <main-selected-64-lowercase-hex> \
  --fixture /one/new-operation.json --output /new/private/output
```

Default exit0 means `validated_offline_only`; no runtime import/download/MMIO
has occurred. Missing `ARTIFACT_MANIFEST.json`, an unfinished preparation,
unknown format/source/tool hash, or mismatched fixture fails before import.
The output must be new and disjoint from package, fixture and authorization.
No existing attempt is resumed, overwritten or automatically retried.

Only `--synthetic-test-only` permits **marked** synthetic metadata/HWH for
offline parser controls. It cannot combine with `--execute-on-a`. Production
validation rejects synthetic provenance. No test generates a real build claim.

The verifier accepts the existing build schema, including its pending-main-review
status; this is package validation, not independent build acceptance. The
expected manifest hash must come from main/A's trusted operation handoff.
It binds main source acceptance/commit, separate build authorization, exact
six-source and eight-tool hashes, the exact launch-input set, raw completion
marker, BD mapping, and paired `artifacts/g05_diag.bit`/`.hwh`. The actual base
and span derive solely from the verified HWH/BD, with the pinned structural
guard requiring the G05 identity, 100MHz clock/reset and six external nets.
It does not use the old overlay name, old base or offset0x2c.

Every consumed package file is hash/size-checked and copied from the bytes
actually read. Metadata's original absolute paths are informational and never
opened. There is no recursive scan of the vendor/build tree. Selected launch
inputs, six RTL snapshots, pair, fixture, manifest and trusted parser bytes
remain under `snapshots/`. The main-attested commit is retained; the collector
does not independently reconstruct a Git tree or authenticate a signature.

| Bound | Limit |
| --- | --- |
| JSON/config/source file | 1MiB |
| HWH | 8MiB; no DTD/entity |
| Bitstream | 1KiB..16MiB |
| Exact pinned board JPEG | 4MiB (actual reference is3,840,574bytes) |
| Each raw build stdout/stderr | 8MiB; may be empty |
| Consumed files/combined bytes | 128 / 64MiB |
| Manifest index entries/declared bytes | 4096 / 8GiB |
| Launch index | <=96 entries plus exact expected set |

Unselected indexed files are not reread or claimed independently verified.
All index names are checked for traversal/case aliases/reserved paths; all
consumed paths reject symlinks, junctions/reparse points and hardlinks. Reads
request `fstat_size+1`, never the large class limit, preserving work57's memory
fix. Descriptor/path identity, size and mtime are checked around each read.

All semantically used JSON uses the parent's duplicate-key, float/exponent,
nonfinite and integer-type guards. Two **opaque, hash-checked references** are
not decoded: `PROCESS.json` contains real fractional elapsed times, and the
exact pinned candidate pin map contains fractional analog voltage references.
Neither supplies command, clock, base, identity or authorization decisions.
Actual mapping is validated from BD/HWH. These bytes are preserved unchanged.

## Operation fixture and A authorization

`schema.json` describes fixture and A authorization fields. The fixture keys
are exactly the parent's `prepare.py` keys. It contains1..16 fixed commands,
strictly increasing32bit command IDs, one profile for the session, and full
run256/nonce128/session32 identity. TTL/payload values remain unchanged. A valid
short TTL may expire before any capture; the collector never extends it.

Execution additionally requires both `--execute-on-a` and `--authorization`
pointing to a strict local A operation authorization. It must match task,
contract, operation/run/nonce/session, expected manifest, main source commit
and the **original fixture byte hash**. It explicitly acknowledges reviewed
build, fresh operation/reset and confirmed board100MHz; validity is at most
900seconds. A owns the external fresh-operation/reset ledger. This is a
caller-authorized boundary, not cryptographic machine identity or replay
prevention across resets. Hostname is not used as proof of nodeA.

Read-only runtime facts must show Linux, ARM (`armv7l`, `armv8l`, `aarch64`),
euid0 and installed PYNQ3.0.1. Distribution metadata lookup does not import
PYNQ. Only after all validation, snapshots, authorization and a flushed/fsynced
`RUNTIME_INTENT.json` can `from pynq import MMIO, Overlay` run.

Overlay construction uses the checked **output snapshot** filename with
`download=False`. Its actual `ip_dict` must identify one unique matching G05
instance/fullpath/type/base/span before the one explicit `download()` call.
The pair is rehashed from the fresh snapshots before construction/download;
original unchecked source paths are never reread. Metadata is checked again
after download, then MMIO is constructed. Receipt fields distinguish attempted
and returned overlay/download/MMIO calls. A returned download is not a physical
capture proof. If MMIO construction never returns, STOP is not falsely claimed.

The Linux output directory requests mode0700 and snapshots mode0400; files and
events are flushed/fsynced. This assumes the caller controls that directory and
the installed interpreter/runtime. An adversarial same-UID process is not
cryptographically excluded; OS/storage power-loss guarantees are not asserted.

## Transport and cleanup

`run_transport()` takes narrow `read32`, `write32`, monotonic clock, sleep,
event journal and record sink functions. One fresh identity is written before
BEGIN1. Each original command stages seven words, sends COMMIT2 once, waits for
true application (running, no pending/inflight, actual tag/command and advanced
application tick), then waits for eligible capture. It sends LATCH4 and reads
status/fault, all13 identity words, command, all32 record words, then status,
fault, full identity, command and **held** record sequence at0x300.

The exact parent `validate_readback` checks those bytes. Capture sequence must
increase strictly across the fixed command list. The full raw readback is
durably serialized before ACK5. The underlying latest sequence at0x1c is not
substituted for the held record. Only after ACK clears the latch does staging
continue. No ENABLE, duplicate COMMIT, retry or failed/unknown write replay is
performed. Skew/missing/expired/faulted/changed-session data ends failure.

Bounds: <=16 requested captures, <=4096 total polls, <=20000 native transport
calls, default30seconds (CLI1..180), sleep1ms between polls. Each operation makes
at most one native read/write call; a returned operation taking>250ms fails.
Durable logging time counts against that budget. Slow hardware/SD may therefore
fail; TTL is never adjusted. Python **cannot interrupt a hung kernel MMIO call**,
nor impose these transport bounds on PYNQ import/Overlay/download. A must retain
its external operation supervision; this collector launches no timeout worker.

Once MMIO exists, `finally` attempts STOP3 exactly once, even after CTRL-C,
clock failure, command/read exceptions, event or record serialization failure.
Unknown writes are never repeated. STOP status polling is limited to64 pairs
and1second when a valid clock is available. It requires retired status with
running/pending/latest/latch/inflight clear. These are logical output-dead
indications, not physical pin measurements; `physical_outputs_observed=false`.

**GC01 correction:** the original code sampled the clock before attempting
STOP and could suppress the write. Original bytes and main's exact software
repro are preserved. Timing sampling is now guarded; it cannot suppress the
raw STOP. `write_attempted` is set immediately before the call, separately from
`write_returned`. Initial exception, regression, NaN or infinity is retained
in `timing_errors`; even if STOP returns and status looks retired, cleanup and
bounded time remain unconfirmed. A second cleanup entry never repeats an
attempted write. Primary error, cleanup error and cleanup-log/receipt errors
remain separate. Runtime exit0 requires every capture plus verified STOP.

## Author controls and limitations

`run_author.py` snapshots the Python files and runs new groups in a fresh
private evidence directory, retaining exact command, PID, exit, raw output and
source hashes. It never replays old35/510 tests, RTL benches or builds.
Controls use marked synthetic packages/HWH and direct simulated MMIO.
Windows junction rejection is tested; creating a Windows symbolic link failed
with privilege1314 and remains preserved. Linux symlink/race behavior and ARM
runtime execution are not established by those B tests.

The private author result/index binds actual completed groups and retained
failed attempts. Independent main review, an actual accepted new package,
PYNQ3.0.1 metadata compatibility, A runtime and physical wiring/clock/capture
proof remain required. Do not interpret offline exit0 or fake-MMIO success as
hardware readiness, source freshness, public BOOT verification or motion authority.
