# G05 build preparation — no build performed

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
DDR parameter family. It snapshots these inputs, the eight new tooling files,
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
`g05_diag_0`. The unchanged TUL preset configures DDR; FCLK0 is100MHz. Reset comes
from PS FCLK_RESET0_N via proc_sys_reset; its derived active-low parameter and
pin polarity are checked after BD validation. A new 4KiB aperture is allocated
and discovered from BD/HWH; no old overlay base or private offset0x2c is reused.

## Timing and HWH guards

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
