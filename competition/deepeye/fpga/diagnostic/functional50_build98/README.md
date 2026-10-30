# Functional50 builder source completion 99S

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, recovery work
`B-DEEPEYE-FUNCTIONAL50-BUILDER-RECOVERY-20261031-99S`. This directory retains
the selected source98 builder names/schema and completes its stopped partial
files under a new lease. Original98 timed out after 3600s and was interrupted
and closed; its eight original files and failure inventory remain preserved by
the main in `build98-stopped-original`. This work does not replay that job.

**SOURCE ONLY. Every executable check listed in CHECKS_UNEXECUTED.json is
NOT_RUN.** No candidate import, syntax check, test, Tcl interpreter, simulator,
Vivado probe/build, board, network or Git mutation ran in 99S. File reads,
source edits, contract-data hashing and source/dependency byte inventories are
the only evidence produced here. The main owns difficult decisions, review,
acceptance, concrete launch identity and Git.

H01–H15 remain mandatory under DEEPEYE-HUMAN-LOCK-20261014/revision1. Fixed
requirements SHA256 is
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, contract pin
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, freeze
`1011259415a0916054eb580687612580bc1e5f09`. Full game-grade 3D/UI, hollow edge
cube, solid volume collisions, free camera/layouts/entry and exit faces, equal
blue/red gates with complete passage, hidden truth, device-bounded causal
observations, online 3D decisions, substantive PC AI and both complete H12
paths remain required. Original100MHz, final1%/100ms, all29 and R20/R21 failures
retain their original scope. Only A operates the board.

## Selected architecture and pins

One PYNQ-Z2 `xc7z020clg400-1` design uses PS7 5.5 FCLK0=50MHz/20ns, GP0,
one AXI interconnect with two masters and both slaves/reset in that same
domain. FCLK1–3 and unused PS AXI interfaces are disabled. Reset polarity
must propagate as `C_EXT_RESET_HIGH=0` and `ext_reset_in=ACTIVE_LOW` after BD
validation; the propagate-only property is never set by hand. The original
72 literal/resolved DDR preset comparisons and pinned vendor/tool inputs remain.

The two private IPs are `g05_50_0` / VLNV
`carlandfpga.local:diagnostic:deepeye_g05_axi_50:1.0` and `trace50_0` / VLNV
`carlandfpga.local:diagnostic:deepeye_trace50_axi:1.0`. Each has a separate
aligned, nonoverlapping 4KiB aperture discovered from actual BD/HWH metadata;
there is no fixed-base assumption. G05 retains magic `0x47303550`, layout2.
TRACE retains magic `0x54353046`, layout1, raw source4/SOFTWARE_FIXTURE, an
actual internal TX→RX path at 1Mbaud and a bounded 4096-byte FIFO. This does not
prove an external UART/RS485 link, physical ADC or production authority.

Only six scalar PL pins are selected: yaw/pitch/speed outputs W14/Y14/T11 and
captures V16/W16/V12, LVCMOS33, bank34. There are no extra external UART pins.
The production73 top remains unchanged and held. A must separately confirm
physical pin availability/electrical wiring before a bounded board operation.

TRACE HWH BUILD_ID must equal the nonzero128-bit value in BD_MAPPING and the
frozen closure. Unchanged G05 has **no BUILD_ID parameter or register**. Its
exact source/VLNV and the same-run BIT/HWH manifest supply linkage; no per-G05
BUILD_ID or MMIO observation is fabricated. Magic/layout values returned by
the HWH verifier are structural labels, not board register reads. The verifier
retains intrinsic PS memory entries without a guessed CPU-memory allowlist or
whole-CPU/PS interrupt certification. It rejects extra selected-GP0 peripherals.

## Closure, approval and command contracts

`closure_template.json` stays unfrozen and build-disabled. Nineteen RTL/header
sources retain exact existing pins; only the selected94 path has null pins in
this template. `DEPENDENCY_PINS.json` lists all20 paths, the seven executable
tooling files and read-only reference/tool/helper pins. No source/header is
substituted or patched. A frozen closure must resolve94 to positive exact bytes
and lowercase64-hex SHA256 matching the actual file, completed review95,
`actual_95_result_sha256`, `main_review_sha256`, and
`review_95.source94={path,bytes,sha256}`. Every executable tooling byte must
also match. The main creates the frozen record; this worker does not.

BUILD_ID is the first128 bits of the canonical source/tooling/architecture/CDC
policy digest; retain the full256-bit digest. The canonical payload excludes
the closure file's own hash and dynamic netlist names. No hash is written into
the unchanged94/G05 source. Dynamic actual-netlist evidence remains separately
bound to this run and BUILD_ID, avoiding a circular dependency.

The default driver mode is `inspect`. Future `prepare` can create only an
exclusive new output, with no vendor run. Future `build` requires explicit
`--closure`, `--approval`, `--run-id`, `--operation-id`, `--work-id`,
`--contract-json` and `--out`. Run/operation/work are bounded identifiers and
must match the one-use main launch record exactly. An existing output is
refused without writing failure files into it. Only output created by that
invocation may receive its failure/manifest records.

A's authentic conditional scope is
`A-GEN4-B50-ONEBUILD-RELEASE-20261031-26`. A26 permits one future bounded
offboard build after actual95 completion and final source/clock/CDC/constraint
review; no extra A checkpoint is required after those conditions. It does not
authorize runtime in 99S. The B launch operation is distinct from A26. Approval
must bind task/version, exact B work/operation/run, output, source commit,
closure hash, BUILD_ID, limits, time fields and the received A scope. Its nested
`a_selection.operation_id/a_message_id/a_message_sha256` must match the frozen
closure's received A26 selection. The main attestation repeats those bindings
as `a_operation_id/a_message_id/a_message_sha256`, verifies the actual A message
and records main identity/review hash/UTC time. JSON consistency is not cloud
authority. The main supplies the concrete B103 launch after all gates.

The future command interfaces, all **unexecuted here**, are:

```text
tools/diagnostic/functional50_build98/build_functional50.py
  --mode inspect|prepare|build [arguments above]
tools/diagnostic/functional50_build98/verify_functional50_closure.py
  --product-root ... --contract-json ... --closure ... --mode auto|template|frozen
tools/diagnostic/functional50_build98/verify_functional50_hwh.py
  --hwh ... --mapping ... --expected-build-id ...
  [--timing-gate ... --check-timing ...]
```

`verify_hwh(path,mapping,expected_build_id)` and
`verify_timing_gate(path,check_timing)` are the builder's read-only APIs. The
timing API reads `route_timing_summary.txt` from the same report directory.

## Actual-netlist CDC and timing gates

Main amendment1 selects only `ACTUAL_NETLIST_THREE_FF_V1`: fixed three capture
ports, three FF stages and 20ns. Prelaunch `cdc_bindings` is null; frozen closure
requires the fixed policy and a main CDC source-review hash, not invented names.
During the one future build, discovery follows each exact scalar port's sole
FF-D fanout and two successive actual Q→D fanouts. The full guard requires
nine distinct ASYNC_REG FFs, direct data drivers, expected startpoints and the
same actual20ns clock. Names are exact dictionary lookups; numeric vector
brackets are retained literally and unsafe Tcl/wildcard names are refused.

Only after complete graph validation does the guard apply exactly three
external-port→first-D false paths. Stages2/3, internal TX/RX and AXI remain
timed. `CDC_BINDINGS_ACTUAL.json` records the synth graph with run/build IDs.
After route the graph is rediscovered, compared and revalidated with exception
application disabled; `CDC_BINDINGS_ROUTED.json` must match. No guessed-pin
fallback, extra discovery synthesis, retarget or automatic retry exists.
Python checks both records and parses only generated simple exact
`set_false_path -from [get_ports literal] -to [get_pins literal]` commands in
implemented.xdc. Extra options/endpoints, through paths, wildcard/global delay
exceptions, duplicate or mismatching names are refused.

Tcl reads exactly one Design Timing Summary row from the same routed report.
It does not treat TNS/THS as per-TIMING_PATH properties. Missing, duplicate,
unsupported, nonfinite, negative or violating values fail closed, with raw
reports retained. WNS/TNS/WHS/THS and failing counts are checked before
write_bitstream; pulse-width metrics, clocks, DRC, no-unconstrained and CDC gates
remain separate. Independent Python parsing compares JSON with those actual
report bytes and records their hashes. No missing metric becomes zero. The
two existing2026.1 report parser controls and all malformed/synthetic controls
are future checks, NOT_RUN in99S; old failed R20/R21 results are never upgraded.

## Remaining gates and A-only follow-up

Actual95 results and main review, reviewed exact source/tooling freeze, first
software/parser controls, actual CDC discovery, one-use build identity, vendor
execution, routed reports and a matched BIT/HWH pair are not established by
this source correction. Vendor API/schema compatibility is unverified here.
Existing suspended-launch Windows Job/thread/time bounds remain pinned, and
every actual failure must retain raw output/process closure without replay.

Only after the main accepts the exact pair may A separately choose a bounded
board operation: inspect current actual BOOT/load outcome once; discover both
HWH bases; read actual magic/layout/TRACE BUILD_ID; explicitly ARM the fixture;
stage at most two raw4 scans with original uint63 QPC/quality/null/held data;
retain all returned/partial bytes for the strict decoder. G05 loopback waits
actual wiring confirmation and its own bounded capture/TTL. On exit perform
one explicit TRACE cancel and one G05 STOP, retaining each unknown outcome;
neither implies host ACK, world-motion STOP or original action retirement.
No B board/SSH/clock-getter/setter/collector repin is authorized.
