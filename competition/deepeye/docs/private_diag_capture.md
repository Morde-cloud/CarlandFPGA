# Private source4 diagnostic collector

DEEPEYE-IMPLEMENTATION-20261014/v1, work
`B-MINIMAL-PL-COLLECTOR-20261025-55-v1`. B main
`01a13b55-095b-7461-8dd5-5476a130bd82` owns decisions and acceptance.
Only A may operate PYNQ-Z2. B tests use explicitly injected fake MMIO and
overlay objects. They establish software behavior only.

The unchanged human scope is `DEEPEYE-HUMAN-LOCK-20261014/revision1`,
H01–H15, canonical requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
pinned at `f5989cd5defce561f9ba98e6b18fc2682945f0a2`. Frozen design:
`1011259415a0916054eb580687612580bc1e5f09`. This private exercise changes
no public ABI, observation stream or motion grant. All 29 formal acceptance
items, R03, full H12, real sensor acquisition, causal freshness, PC AI and
the complete product remain `not_run` or unestablished by this collector.

## Prerequisites and format binding

Main final binding is now recorded at
`evidence/diagnostic/b56/main-final-binding-01/RESULT.json`.
The actual paired build manifest SHA256 is
`e906b1517d328e05b123346ea71c0c5c7c6552be7baa31dde2eb42833f0ef13a`.
The default offline CLI passed on that actual package. Separately, the
collector's recorded transactions were replayed against the exact RTL:
518 AXI transactions, 2484 checks, three scans and twelve lanes passed.
This does not run PYNQ or establish physical timing/freshness. The historical
draft read provenance below and original raw result wording are retained.

There was no accepted actual bit/HWH package when this collector was authored.
Before delivery or A execution the quality main must bind its final slice53
RTL and slice54 build wrapper/manifest formats. The collector implements the
slice54 draft read at these hashes; original draft bytes are snapshotted in
`evidence/diagnostic/private-collector-20261025-55/author/inputs/`:

| Draft | SHA256 |
| --- | --- |
| `tools/diagnostic/build_private_diag.py` | `1c5d89207985097ac18af6c0d93ff0562189dc877c77c2cf0e0023d9e1fc8d02` |
| `docs/private_diag_build.md` | `6d1daeb73c12b04beaafd968d13a49b3763dc17fe40c23e9599fe149bde06fcc` |

No finality or acceptance of concurrent workers is implied. A supplies the
exact independently selected SHA256 of canonical `ARTIFACT_MANIFEST.json`.
A mutable filename, a sender path or a self-declared identity is insufficient.
This is a local operator guard, not authentication or proof of the loaded PL.
A still needs its assigned operation authorization and a bound full run/session/
nonce ledger. The nonzero 32-bit tag is only a reference to that ledger; it
does not replace it or prove global tag uniqueness.

The package retains the sender's build-relative layout. Absolute `path`
properties in records are provenance only; the receiver never opens them.
Required records are same-build bit/HWH, routed DCP, BD mapping, completion,
tool version, constraints, six route reports, PROCESS/PREPARATION, five exact
RTL snapshots and both build scripts. Each selected record's size/hash is
checked; all five source hashes and four fixed dependency pins are checked.
Other inventory entries are not claimed as rehashed. The canonical manifest
must declare `completed_build_pending_main_review`, matching task/work/design/
contract, consistent `artifacts`/`files` records, and no formal/board acceptance.
`PROCESS.json` requires exit0, confirmed termination and no timeout/error.
`VIVADO_COMPLETE.json` supplies the build run ID. These checks cannot replace
the main's build review or prove that a user-created manifest describes a real
Vivado execution.

HWH is parsed from the exact hashed bytes with ElementTree. DTDs/entities,
NUL/UTF16 XML, oversized files, ambiguous private instances/ranges and a
mismatching BD mapping are rejected. The required instance is `private_diag_0`,
VLNV `carlandfpga.local:diagnostic:deepeye_private_axi_diag:1.0`, one aligned
4KiB `S_AXI` range. The base comes from HWH, never a magic host address.
JSON rejects duplicate keys and NaN/Infinity. Selected files are bounded to
256MiB each, 512MiB total; JSON 8MiB and HWH 16MiB. Paths with symlinks,
junctions, hardlinks or aliases are rejected. The new output must be disjoint
from the package and fixture and cannot already exist.

## Exact input schema

The only fixture schema is shown below; unknown fields are rejected at every
input object. Integers must be JSON integers, not booleans, strings or floats.
There are 1–16 scans; every array has exactly four entries. Values are uint16,
original QPC ticks uint64 and opaque qualities uint8. No truth coordinates,
map seeds, route information or new timestamps belong here.

```json
{
  "schema_version": 1,
  "source_id": 4,
  "source": "software_fixture",
  "topology_id": 2,
  "a_reference": {
    "run_id": "A-full-run-ledger-id",
    "session_id": "A-full-session-ledger-id",
    "nonce": "A-full-nonce-reference"
  },
  "tag": 1234567,
  "scans": [{
    "values": [0, 1, 32768, 65535],
    "original_host_qpc_ns": [0, 9007199254740993, 9223372036854775815, 18446744073709551615],
    "qualities": [0, 1, 127, 255]
  }]
}
```

The numbers above illustrate integer boundaries and are not a live observation.
A must supply original generation QPC values, unchanged. The collector never
creates, translates or replaces them. Source4 remains a raw software fixture;
tag, sequence, counter and identity consistency do not establish device-bounded
causal observation freshness. Host clock mapping is not implemented.

## A commands and execution

Use Python 3.10+ stdlib for offline validation. Run the command below with A's
actual package, explicit manifest, A-selected hash and original input. The
output is a fresh directory outside the package and input paths:

```sh
python3 tools/diagnostic/collect_private_diag.py \
  --package /home/xilinx/private-diag-approved-build \
  --manifest /home/xilinx/private-diag-approved-build/ARTIFACT_MANIFEST.json \
  --manifest-sha256 <A-selected-exact-manifest-SHA256> \
  --fixture /home/xilinx/inputs/A-original-fixture.json \
  --out /home/xilinx/evidence/private-diag-offline-operation-id
```

This default imports no PYNQ, constructs no overlay/MMIO and accesses no device.
It writes validated snapshots and returns `verified_offline_only`. After the
main binds the final format, A reviews offline evidence and chooses the new
explicit hardware operation. On A's PYNQ PS with its supported PYNQ installation,
use the same explicit arguments with a new output and `--execute-a`:

```sh
python3 tools/diagnostic/collect_private_diag.py \
  --package /home/xilinx/private-diag-approved-build \
  --manifest /home/xilinx/private-diag-approved-build/ARTIFACT_MANIFEST.json \
  --manifest-sha256 <A-selected-exact-manifest-SHA256> \
  --fixture /home/xilinx/inputs/A-original-fixture.json \
  --out /home/xilinx/evidence/private-diag-hardware-operation-id \
  --execute-a --poll-seconds 2 --total-seconds 60
```

Replace angle-bracket placeholders before running. Never run this hardware
command on B/C. A checks current ownership, physical setup and package approval.
No existing overlay, reserved `0x2c`, public EVENT/BOOT/STATE/TRACE, ADC, UART,
CNN, production PC_DIRECT, full FPGA-output path or external I/O is exercised.

The collector copies the validated immutable bit/HWH byte snapshots into
`snapshots/artifacts/private_diag.bit` and `.hwh` in the fresh evidence directory.
Only that bit filename is passed to `Overlay(download=False)`. Metadata must
match fullpath, VLNV, HWH physical address and range before download and MMIO.
The original package filenames are never reread for loading. PYNQ then explicitly
downloads once; parsed metadata alone is not treated as loaded-hardware proof.

Once MMIO is established it checks hardware magic/version, issues STOP and
verifies stopped/no result/zero active tag, stages the nonzero ledger tag,
issues START once and verifies the new generation, active tag and running state.
Every scan writes all 13 full staging words, preserving each QPC low/high half.
TRIGGER is attempted once. Its actual next trigger ID and generation are read.
For each of four lanes, result_valid must remain stable around two raw-field
reads and session/status checks; data/channel/quality/QPC/first/last sequence,
tag, trigger and generation must match. Capture/queue/lane counter deltas must
be exactly 4/1/4 per scan, with lane progress checked before each ACK. The
baseline is read after START; counter exhaustion rejects the operation.
Each verified lane is ACKed once, followed by an idle check after the fourth.
`0xA4` is `PL_RESULT_LATCH_CYCLE`, a diagnostic cycle value, not acquisition time.

All polling uses collector-local monotonic time strictly for timeout/journaling.
The per-wait timeout is bounded to 10s, the total capture to 180s, and each poll
loop also has a fixed iteration bound. SIGINT/SIGTERM enter failure handling.
These software bounds cannot guarantee interruption of a stuck kernel MMIO or
PYNQ download call; a killed process/power loss cannot supply a STOP receipt.
No automatic reload, retrigger, ACK replay or operation retry exists.

## Evidence and exit meaning

Every MMIO call has a flushed attempt record before access and a returned/error
record after it in `operations.jsonl`. Timestamps are labeled collector-local
monotonic, separate from original QPC. An unmatched attempt is an unknown effect,
never implicit success. Read values, write values, partial verified lanes and
failures remain intact. `INTENT.json`, exact snapshots and `RESULT.json` retain
inputs, arguments, interpreter, selected hashes, full A references and status.

STOP is attempted in `finally` after any failure once MMIO exists, and on normal
completion. Stopped/no result/zero active tag are read back before
`cleanup.confirmed=true`. STOP failure is recorded separately from the primary
exception. Import, overlay, download or MMIO-construction failure does not invent
a STOP receipt. Unknown actions require main-reviewed recovery under a new
assignment; existing evidence directories are never overwritten.

Exit0 means only offline validation or a completed bounded private diagnostic,
as named in `RESULT.json`. It is never automatically a formal PASS. Exit2 means
rejection/failure, including cleanup failure. Runtime injection is always labeled
`software_fake_runtime`, `software_fake_capture_complete`, physical board
`not_run`. Even successful A execution provides only the explicit diagnostic
evidence; the quality main evaluates it with the A operation ledger.

Run software tests from the product root with bytecode writing disabled:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe' -X utf8 -B -m unittest discover -s tests/diagnostic -p test_collect_private_diag.py -v
```

Only fake overlays/MMIO are passed as explicit dependencies. Retained software
case directories under author evidence contain deliberately nondeployable fake
bit/HWH packages. Do not ship those fixtures as board packages. Real PYNQ parser
compatibility, actual RTL interaction, bit generation and all physical results
await their separate authorized executions and main acceptance.
