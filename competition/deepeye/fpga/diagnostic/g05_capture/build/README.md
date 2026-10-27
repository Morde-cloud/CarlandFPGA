# G05 build preparation and pinned DDR resolution

Task DEEPEYE-IMPLEMENTATION-20261014/v1; preparation work
B-G05-BUILD-PREP-20261026-59-v1. Main01a13b55-095b-7461-8dd5-5476a130bd82 owns
source acceptance and later build authorization. This directory and its peer
`tools/diagnostic/g05_capture/build/` contain new tooling only. Mapper, engine,
AXI and prior build sources remain read-only. No old build/suite is replayed.

H01-H15 revision1 fixed requirements SHA256:
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`;
contract f5989cd5defce561f9ba98e6b18fc2682945f0a2, frozen design
1011259415a0916054eb580687612580bc1e5f09. Both PC_DIRECT and FPGA-output control
paths remain required; this private diagnostic grants no motion authority.

## Offline preparation

Run the new `build_g05.py --out <new-directory> --contract-json <fixed-contract>`.
The default mode is `prepare`; it cannot call Vivado. It hashes installed
Vivado2026.1 executable files without launching them, checks the original TUL
board/preset/pins/image hashes and 771 preset parameters, and records the full
DDR parameter family and the pinned installed named-memory model below. It snapshots these inputs, the eight tooling files,
and only the two immutable control3d primitives. It does not snapshot or claim
acceptance of changing mapper/engine/AXI sources. Missing acceptance/CDC/build
authorization are explicit in PREPARATION.json. The generated acceptance
template has accepted=false and null unresolved values.

The candidate A IO-map and XDC are read and hash checked in full; only six entries
are selected for the new XDC. Outputs yaw/pitch/speed use W14/Y14/T11; independent
inputs use V16/W16/V12, all bank34 LVCMOS33. No J3/analog/RS485 assignments or
internal PWM feedback connections are made.

## Separate future full-build gate

`--mode build` requires both `--source-acceptance` and `--authorization`, supplied
by main under a new build work/operation. Source acceptance schema1 requires:

- task_id/task_version, director_thread_id, accepted=true, fixed requirements
  hash/frozen_design, and exact 40-digit source_commit attested by main;
- sources: all six exact product-relative paths listed in build_g05.py, each
  SHA256, including the mapper's required `.svh`; the two primitive hashes
  must retain their immutable values;
- build_files: all eight exact tooling paths and SHA256;
- cdc_bindings: each of the three capture ports maps to three distinct exact
  final hierarchy FF D-pin names; no wildcard or guessed default is accepted;
- cdc_source_review: path, SHA256 and reviewed_by=main for the exact-source review.

Separate authorization requires authorized=true, action=full_g05_diagnostic_build,
the same task/director/contract/source_commit, the source-acceptance file SHA256,
a new work_id different from this preparation job, operation_id, and exact new
output_directory. It must explicitly acknowledge the three named unresolved
physical bounds: external_output_propagation, input_flight_time,
physical_cross_channel_skew. The output must be a new directory under
`competition/deepeye/evidence/diagnostic/g05-capture/`. Existing output is never
reused, even after failure. Main's source-commit attestation is recorded as such;
the script verifies actual source bytes against its accepted SHA map.

At a later authorized run, all six files are copied into one private flat
snapshot. The sole allowed include is the mapper's exact colocated header.
Vivado imports the header as an actual package file and verifies packaged source
bytes and header colocation before synthesis. Include search cannot fall back
to changing external source directories. The generated per-run config is never
created in offline preparation.

The new project lives at `<run>/g05_diag/project`, BD `g05_diag`, top
`g05_diag_wrapper`; IP `carlandfpga.local:diagnostic:deepeye_g05_axi:1.0`, instance
`g05_diag_0`. The unchanged TUL preset and pinned named-model resolution configure DDR; FCLK0 is100MHz. Reset comes
from PS FCLK_RESET0_N via proc_sys_reset; its derived active-low parameter and
pin polarity are checked after BD validation. A new 4KiB aperture is allocated
and discovered from BD/HWH; no old overlay base or private offset0x2c is reused.

## Timing and HWH guards

### DDR check repair, work B-G05-DDR-CHECK-REPAIR-20261026-59-v1

Main's original R1 stopped before synthesis/bitstream when the literal TUL
T_RC=50.625 differed from the installed named-model value48.91. R1 and its
failure/process evidence remain unchanged. This repair runs only new offline
XML and mocked Tcl controls; a fresh R2 needs main's independent acceptance,
updated tooling hashes and separate authorization. It does not accept DDR or
physical-board behavior.

Production resolution requires both exact source hashes:

- TUL preset.xml: `18528f84aea4da503cdb3104f7706fabfb3b6ad09b78b25199cc316afa4c8cfe`.
- Installed `data/PS/7series/data/zynqconfig/ddr/ddr_preset.xml` under the selected
  Vivado root: `73566a941b442804a9c6b0eb42385b6c1cb82f12e354c138f8868005b91c52ed`.

The one named entry must have selector `pcw_uiparam_ddr_partno`, exact name
`MT41J256M16 RE-125`, and strength8. Its13 unique set keys must be the same13
unique disable keys, all in the board's72 DDR keys. Ten values must match the
board literals; exactly these three may differ:

| Field | TUL literal | Named model |
|---|---|---|
| T_RC | 50.625 | 48.91 |
| T_RCD | 13.125 | 7 |
| T_RP | 13.125 | 7 |

No unit conversion or numeric tolerance is applied. T_RC has explicit ns
metadata; T_RP is described in clock cycles; T_RCD's unit remains unproven.
T_RAS_MIN is unchanged, but its metadata name says ns while its description
also says cycles. These gaps are recorded, not resolved by inference.

Preparation keeps all771 raw board parameters in `ps7_preset_parameters.json`,
all72 literals in `ddr_literal.json`, all72 resolved values in
`ddr_resolved.json`, and complete selected-entry/count/difference/source-hash
provenance in `ddr_resolution.json`. It copies the raw vendor XML to
`inputs/vendor_ddr_preset.xml`. Before launch, both raw source snapshots and
every generated DDR table are reverified; the installed vendor hash is checked
again. The copies are included in `LAUNCH_INPUTS.json` and the existing
postprocess hash verification. The eight-file tooling acceptance list is
unchanged; the new `test_ddr_resolution.py` is a separate targeted test source.
The exact public DOCTYPE declaration in the pinned vendor XML is removed only
from the parser copy; no DTD is fetched or loaded. The raw XML stays intact.
Unexpected declarations and entity definitions are rejected.

The Tcl gate checks all72 exact strings after board/FCLK configuration and
again immediately after `validate_bd_design`, before target generation. Each
reached stage writes `<stage>_ddr72.tcl` (lossless Tcl data), a complete TSV,
and a differences TSV before raising a mismatch. Differences include the
three accepted changes from board literals as well as any unexpected result.
Missing/extra keys, unreadable properties, altered values or inventory errors
fail closed. A failed validation still gets the second table, and its original
error is retained separately in `bd_validation_status.tcl`. An earlier gate
failure stops execution: a later unreached stage has no fabricated table.

Run the new offline controls with the same Python used for preparation:
`test_ddr_resolution.py --inputs <directory-with-tul_preset.xml-and-vendor_ddr_preset.xml>
--tcl <build_g05.tcl> --output <new-directory>`.
The explicit mutated-XML parser helper bypasses digest checks only for labeled
test fixtures; no CLI option selects it for preparation/build. Tests use a
local Tcl interpreter with mocked properties and never invoke Vivado.

### Existing timing and HWH requirements

Only package/IOSTANDARD constraints are initially added. After synthesis the
CDC Tcl resolves every supplied pin exactly, verifies ASYNC_REG sequential
cells and actual100MHz clocks, checks external-only first-stage fanout and the
three-stage chain. It excludes only each external input-to-own-first-D path.
Later stages remain timed. Missing/changed pins, broad fanout or wrong chains
stop the run. No guessed external delay, PL clock or blanket false path is used.

Output propagation, input flight time, PCB/jumper cross-channel skew and actual
board/wiring remain unmeasured. Internal timing checks and reports do not prove
full G05/B06 timing. Main must review check_timing/unconstrained-path, CDC,
exceptions, DRC, methodology, route and min/max timing reports. The proposed
Tcl/packaging flow itself has not been executed in Vivado during preparation.

HWH verification checks unique VLNV/instance, 4KiB aligned span matching actual
BD mapping, 32-bit AXI and12-bit addresses, connected FCLK0/net100MHz, active-low
reset chain and all six exact independent external connections. It requires
the complete DDR/FIXED_IO port membership and rejects extra PL ports. Stale PS
GP0 descriptive FREQ_HZ is not substituted for connected PORT clock evidence.
Synthetic parser fixtures carry TEST_FIXTURE=synthetic-not-hardware and cannot
pass production verification; parser tests never become actual HWH evidence.

## Process and evidence

The new owned_process.py copies only the hash-pinned original Win32 accounting
functions; it has no old build entrypoint. A hidden suspended launch joins its
new job before resuming. Success needs both launcher exit0 and observed whole
job ActiveProcesses=0 while its handle remains open. Query/termination/timeout
failures remain failures after cleanup. Only that original owned job can be
terminated. No service, peer, board or credential operations are present.

Future output preserves full stdout/stderr, parent and every child synthesis
journal/log, versions, actual source/tool/board/constraint snapshots and every
artifact hash. Same-run paired bit/HWH, DCPs, raw synthesis run inventory and an
exact unique run completion marker are required. Failures remain in place with
automatic_retry=false. No synthesis, implementation, bitstream, physical-board
or formal product acceptance is claimed by this preparation.
# Constraint checks after synthesis

The package XDC contains only twelve declarative assignments. Procedural checks
run in the build Tcl after `open_run synth_1`: each of the six exact port names
must have the intended direction, package pin, LVCMOS33, bonded pin and bank34.
An unsupported procedural XDC warning in R2 was a real failed constraint
application and is retained; the new checks do not waive it.

For CDC stages2/3, the checker separately verifies a unique direct previous-FF
Q driver on D and the previous-FF C timing startpoint returned by Vivado.
`all_fanin -startpoints_only` is a timing query, not a Q-net driver query. All
nine exact FF names, ASYNC_REG, actual100MHz clocks, distinct chains, and the
sole external-input-to-first-D exception remain mandatory. Intervening logic,
extra drivers or wrong launch registers are rejected. The FPGA RTL is unchanged.

The original R2 full build failed before route/bit; a top-only checkpoint query
contained four unresolved black boxes, and an expanded linked-netlist query
timed out after preserving the pitch-chain facts. These historical runs are
not promoted to passing builds. Each new build must execute the complete
checks and retain its own reports. External propagation/skew and board timing
remain unmeasured.



## R12 packaged immutable PWM reference

R11 stopped before synthesis because hierarchy-driven IP import omitted the
unused original atomic PWM reference. R12 explicitly adds only that accepted
file to synthesis/simulation file groups, preserving the exact six-source set
and existing byte-by-byte verification. The G05-private STOP-factored PWM body
is inside engine.sv; the immutable original file is retained as a reference,
not claimed as instantiated hardware. No missing-input gate is relaxed. All
source/config/CDC/timing/DRC checks remain mandatory for the next actual build.
