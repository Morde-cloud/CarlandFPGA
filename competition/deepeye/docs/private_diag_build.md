# Private source4 AXI diagnostic build

This entrypoint builds the minimal private PS/AXI digital diagnostic for
DEEPEYE-IMPLEMENTATION-20261014/v1 under the original
`B-LIVE-OBS-INTEGRATION-20261023-v1` dependency. B director
`01a13b55-095b-7461-8dd5-5476a130bd82` owns decisions and acceptance.
The four capture/queue/lane sources remain unchanged. The private AXI slave
provides staged software-fixture input, actual PL pipeline consumption, held
results and session-retiring STOP. Physical board operation belongs only to A.

The reviewed full build is recorded in
`evidence/diagnostic/b56/main-final-binding-01/RESULT.json`: Vivado 2026.1,
100MHz constraint, setup slack 0.470ns, hold slack 0.029ns, zero DRC and
methodology violations. The paired bit/HWH and final collector offline check
are bound there by exact hashes. This is a loadable diagnostic candidate;
actual PYNQ execution and the complete product remain unverified.

Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01–H15, is preserved.
Canonical requirements SHA256 is
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`;
frozen design is `1011259415a0916054eb580687612580bc1e5f09`.
The wrapper's source-head reference `323786cab808113e0bd75f7aab405fc957269ff6`
is a historical parent reference; the exact five-source map and handoff
commit identify the implemented source. This fixture does not establish any
of the 29 formal acceptance items, R03, full product behavior or board success.

## Design and preset

Vivado 2026.1 targets `xc7z020clg400-1`. The named BD is `private_diag`,
the top is `private_diag_wrapper`, and the packaged private IP is
`carlandfpga.local:diagnostic:deepeye_private_axi_diag:1.0`, instance
`private_diag_0`. Tcl packages unchanged RTL with explicit AXI4-Lite, clock,
active-low reset, and 4KiB address-block metadata. PS GP0 connects through
one AXI interconnect. Every fabric component uses the same 100MHz PS FCLK0.
`proc_sys_reset` receives active-low PS FCLK_RESET0_N with
`C_EXT_RESET_HIGH=0`; auxiliary/debug resets are tied inactive.
This read-only parameter is propagated from the connected PS reset and
asserted after BD validation. DDR/FIXED_IO member ports are explicitly
distinguished from extra external PL ports. Automatic address placement is
followed by an explicit 4096-byte mapped-segment size and actual readback.
`dcm_locked=1` represents the direct PS clock with no fabric MMCM/PLL.
The reset controller synchronizes release on that FCLK. This is not a CDC
or asynchronous-reset verification claim about slice53 RTL.

The only external interfaces are PS DDR and FIXED_IO. The board preset's
existing onboard MIO configuration is retained. No external PL clock,
PL pin, ADC, UART, PWM, public ABI, old overlay or reserved 0x2c is used.
`constraints/private_diag.xdc` names the intended constraint scope;
the actual PS IP supplies hard-PS pin/clock constraints. The flow exports
`constraints/implemented.xdc`, clock reports and timing checks for review.
It does not guess package pins, DDR timings, false paths or DRC exceptions.

The selected installed board directory is
`D:/pynq/AMD2026/2026.1/Vivado/data/boards/board_files/pynq-z2/A.0`.
Its bytes match the recorded XilinxBoardStore `2022.1`,
`boards/TUL/pynq-z2/A.0` source in
`D:/pynq/PYNQ-Z2-board-files/SOURCE.json`. No board files were installed or
updated by this worker. All four files are checked and snapshotted:

| File | SHA256 |
| --- | --- |
| board.xml | a565dcb39737d551cbbbb73c0053b973c40bb3dce2274943370d3032c0fea9ae |
| preset.xml | 18528f84aea4da503cdb3104f7706fabfb3b6ad09b78b25199cc316afa4c8cfe |
| part0_pins.xml | 3c809473938e135a925b563b5371c8687ee05c4089376e7318c0c56524cc8a0f |
| pynq_z2.jpg | 54b4bb2da4a38a647d3df030ec13fe63e427235980ce9ae1ca44ce9a91af4546 |

The `ps7_preset` contains 771 parameters. The preparation records all of
them, and the build checks selected DDR part/geometry/frequency parameters
against the actual PS after applying the board preset. Vivado 2026.1
compatibility of this preset still needs the separately authorized build.
The source contains DDR DQS-to-clock delays -0.051, -0.006, -0.009 and
-0.033 ns. Preserve those original preset values and any related PS warnings;
they have not been waived or proven harmless by this preparation.

The single bounded readonly Vivado query confirmed version2026.1, the target
part, and `tul.com.tw:pynq-z2:part0:1.0`, then exited1 because `get_ipdefs`
requires an open project. No project was created and the query was not
repeated. The four installed IP `component.xml` files were instead inspected
and their identities/hashes recorded. Runtime IP catalog availability,
packaging commands and preset compatibility await the authorized build.
Plain Tcl8.6 syntax and bytecode checks do not establish Vivado semantics.

## Inputs and commands

Run from `D:/pynq/CarlandFPGA` with the existing local Python. Commands below
use PowerShell variables only for readability. Use a genuinely new output
directory for every explicitly assigned execution; existing directories are
rejected and failed/unknown executions are not retried automatically.

```powershell
$product = 'D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye'
$contract = 'D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/b-integration-inventory-20261024/sources/f5989cd5defce561f9ba98e6b18fc2682945f0a2/docs/competition/deepeye-2026/immutable_scope.json'
& .local/venv/Scripts/python.exe -X utf8 "$product/tools/diagnostic/build_private_diag.py" --mode prepare --out "$product/evidence/diagnostic/private-build-20261025-54/main/prepare-01" --expected-sha-map '.local/deployment/node-b/evidence/minimal-pl-20261025-53/SOURCE_PINS.json' --contract-json $contract
```

`prepare` runs no Vivado process. A build needs the main's SHA map for
**exactly all five** RTL files in the wrapper's `SOURCES` list; keys may be
the listed product-relative paths or unique basenames. It must retain the
four exact `SOURCE_PINS.json` values. The fifth value must be the main's
accepted slice53 RTL hash, never the wrapper's self-selection of current HEAD.

The separately issued main authorization JSON must contain these exact
fields, plus a nonempty stable `operation_id` and `authorized: true`:

```json
{
  "task_id": "DEEPEYE-IMPLEMENTATION-20261014",
  "task_version": 1,
  "director_thread_id": "01a13b55-095b-7461-8dd5-5476a130bd82",
  "work_id": "B-MINIMAL-PL-BUILD-PREP-20261025-54-v1",
  "action": "full_private_diag_build",
  "accepted_rtl_sha256": "<main-accepted fifth RTL SHA256>",
  "expected_sha_map_sha256": "<SHA256 of exact five-source JSON file bytes>",
  "requirements_sha256": "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
  "operation_id": "<main-issued operation ID>",
  "authorized": true
}
```

Ready command after the main accepts slice53 and explicitly authorizes a
new build (the main supplies the three paths below):

```powershell
& .local/venv/Scripts/python.exe -X utf8 "$product/tools/diagnostic/build_private_diag.py" --mode build --out $newBuildOutput --expected-sha-map $mainFiveSourceMap --authorization $mainBuildAuthorization --contract-json $contract --timeout-seconds 7200
```

This JSON is a local explicit-action guard, not an identity/security boundary.
The operator still requires the assigned role, lease, file ownership and
main authorization. Preparation does not create such authorization.

## Execution evidence and receiver

The wrapper snapshots RTL, scripts, board files and the existing Windows Job
helper, hashes exact inputs, checks all five original and snapshot RTL files
immediately before launch and after completion, and rejects changed sources.
The helper is `fpga_mesh/windows_job.py`, exact SHA256
`3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3`.
The command launcher is hidden, suspended until attached to its kill-on-close
Windows Job, and bounded by one timeout. Original process identity, command,
environment overrides, binary stdout/stderr, journal, log, tool version,
exit/termination evidence and source hashes remain in the new output directory.
54R1 keeps that original job handle open after the launcher exits and queries
`QueryInformationJobObject(JobObjectBasicAccountingInformation)`. Launcher
exit and whole-job termination are separate fields. The normal path waits up
to five seconds for `ActiveProcesses=0`; lingering descendants, launcher
failure or timeout trigger explicit `TerminateJobObject`, followed by up to
five seconds of accounting observations before closing the job. Each sample
records active, total and terminated process counts and its observation phase.
Any query or termination API failure remains sticky `unknown`/false even if
a later sample shows zero. Closing a kill-on-close handle is a cleanup fallback
and cannot establish terminal proof. Build completion requires successful
launcher exit, confirmed whole-job terminal state and no forced-cleanup reason.
54R1 exercises short harmless local Python trees only; its evidence is under
`evidence/diagnostic/private-build-20261025-54/review-repair1/`. Original54
source bytes are preserved there, and original54 author evidence/Tcl remain
read-only. This repair does not authorize or execute a full Vivado build.
No automatic retry, overwrite, service operation or publication occurs.
Vivado `general.maxThreads=2` and synthesis `-jobs 2` limit tool concurrency.
On Windows, use a short, repository-contained immutable build snapshot.
The accepted execution used `.local/b56/competition/deepeye`; the original
long-path attempt failed while saving a generated context XDC. Exact copied
inputs and all original failures are retained, without changing global path
settings or altering product RTL.

Ordinary vendor warnings are retained. The board preset left the descriptive
`PCW_M_AXI_GP0_FREQMHZ` value at 10, causing a propagation warning; the actual
connected FCLK/GP0/private-IP port metadata and routed clock are 100MHz.
Do not use that descriptive value as a clock measurement. A must verify its
loaded runtime clock separately. The two implemented false paths come from
vendor XPM first-stage reset synchronizers; no custom timing waiver was added.

The flow packages IP, validates/maps the BD, generates the exact top,
synthesizes, optimizes, places, routes and writes the bitstream. It preserves
routed/synthesis checkpoints, timing summary, check_timing, resources, DRC,
clocks, route status, methodology, PS properties and constraints. Setup/hold
failure, DRC errors and command errors stop completion; critical warnings and
unconstrained-path checks remain visible for main review without suppression.

`BD_MAPPING.json` records Vivado's actual assigned absolute base and 4096-byte
range. The wrapper checks the same-run HWH's private instance/VLNV/range
against that mapping. Host software must discover this identity and base;
there is no hardcoded host base. A bit file surviving a failed run cannot
produce a completion manifest. Success also requires exit0, the unique run
marker, matching run identity, all nonempty reports and matching HWH.

The receiver needs `artifacts/private_diag.bit`, same-name
`artifacts/private_diag.hwh`, `ARTIFACT_MANIFEST.json`, the source snapshots,
and `inputs/build_private_diag.py` / `inputs/build_private_diag.tcl` entrypoints.
The manifest includes exact source, process, report and artifact hashes.
`completed_build_pending_main_review` is only build completion. All 29 formal
acceptance items and physical-board results remain `not_run` until their own
real executions and acceptance evidence.
