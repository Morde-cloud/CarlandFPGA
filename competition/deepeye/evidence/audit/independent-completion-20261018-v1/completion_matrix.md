# B independent completion audit — 2026-10-18

Task DEEPEYE-IMPLEMENTATION-20261014/v1; work B-INDEPENDENT-COMPLETION-AUDIT-20261018-v1.
Base PR30 head 781be78d9da77a75ea711cf690eeea6523733d3a. The final taskbook and execution plan at 1011259415a0916054eb580687612580bc1e5f09 assign exactly eight root cards to B. Contract f5989cd5defce561f9ba98e6b18fc2682945f0a2, H01–H15 canonical requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 was recomputed. Six normative source files are byte-identical to the frozen design. See audit_inputs.json for Git blob/source hashes and literal card text.

**B independent work is incomplete.** No root card is marked passed. Existing candidate acceptance is narrower than formal card acceptance; an external root-card dependency does not prohibit independent local implementation.

| Card | Existing implementation and main-reviewed evidence | Local work still possible/required | Actual external dependency |
|---|---|---|---|
| B01 codec | uint16 closed-loop E=0/1/2/4/8 reference; bounded Rice/RAW; corrected aggregate bytes/scalar boundary. TRACE<=32B candidate, raw vectors and strict receiver reviewed in operations01/04/05. Existing million-sample software run and later targeted corrections are historical evidence, not rerun here. | No synthesizable codec existed at the audited head. Implement buffered integer block encoder, then RTL framing/selection integration and independent decode/stream verification. | A approval of public TRACE/sample/source/tick layout; C independent decode of fixed source; A formal B01 acceptance. |
| B02 acquisition | No product acquisition/XADC/input-stream/DMA/PS recorder files in the tracked product source. Capture model is actuator feedback, not ADC acquisition. | Build bounded sample ordering/ID/tick/quality and loss-reporting primitives, then actual XADC/DMA/PS modules and local RTL fault/reset tests. | A01 actual ADC fixture/calibration, R03 source/clock/sample contract, A pins/platform/HWH and 600s board acquisition. |
| B03 stream/reset | Operation06 isolated one-entry snapshot mailbox: main-reviewed digital RTL, reset/backpressure/stop-clock cases and negative controls. | Full codec block stream, finite queues, TLAST/length, overflow/accounting, half-frame reset and multi-block recovery remain absent. Mailbox success is not stream-suite success. | A integration clocks/reset contracts and physical CDC/RDC constraints; final implemented timing/board evidence. |
| B04 link/scheduler | Offline TRACE packing, byte ledger and rejection only. No Q0/Q1/Q2 scheduler or UART/RS485 product endpoint. | Implement bounded queue policies, complete local UART/framer/recovery and scheduler fixtures; protocol scanner tests and exact line/idle/retry accounting. | A frozen BOOT/profile slot offsets, response/guard/USB bounds; C peer implementation; A actual 8N1/turnaround/event measurements. |
| B05 control | Operation02 capture/snapshot Python model; operation06 opaque mailbox; operation07 declarative29-register/51-field proposal, static review only. | Session/observe/TTL state machine, block-atomic CONFIG, STOP/clear/enable, actual register bank, fault logic and stale-response counterexamples still need RTL and local verification. A candidate must not be treated as frozen ABI. | A approval of field/reset/access/WSTRB, enum/BOOT/clock/source binding and real PGA calibration; A physical GPIO/GAIN/TTL tests. |
| B06 build | No complete DeepEye top, build.tcl, XDC, bit/hwh or implemented timing/DRC/resource reports. | Integrate B modules; author reproducible build constraints/scripts once clocks/pins are assigned. Current preflight finds ModelSim but no Vivado; synthesis/implementation is blocked by tool availability as well as missing design. | A R02 hardware/pin/platform facts and eventual board_modules execution. Do not inherit old unrelated BRAM evidence. |
| G01 assets | Operation03 source factory:0.80m PDC drill, five closed obstacle kinds,12 cube edges;622 engine checks; main45-component topology/containment review and11 actual images. Candidate collision shapes disabled. | Remaining local art quality/material/readability refinement, accurate current catalog status, resource packaging/export and integration-facing checks. Procedural editable source exists; full final asset pack/game-grade acceptance is not complete. | A-owned engine project, gates/editor/viewer/physics integration and verify_game orchestration; whole-application acceptance. |
| G05 three-axis feedback | Python three-channel association/capture model, integer PWM candidate equations and opaque mailbox; no actual three-channel output/capture or CONTROL3D endpoint RTL. | Implement atomic frame update, independent edge capture/decoding and complete-period association; curvature/TTL/profile logic and local three-axis fault tests. | A physical pin/IO/clock/tolerance/profile freeze and measured loopback; C broker interop; rebuilt B06 exact new RTL; A board_control3d. |

Additional B responsibilities: G02 asset-picking review is read-only against A editor; A04 independent release rebuild/review requires the eventual exact release package. Neither is complete and neither grants B ownership of A/C code. B owns integration of its shared top, while A owns shared ABI/schema and the physical board.

H01–H15 final observable behavior remains outstanding: a runnable full game-grade 3D/UI, free camera/edit/random scene creation, equal gates and complete rigid-volume passage, hidden truth with causal measured observations, substantive online PC AI, and both PC_DIRECT and FPGA-output paths. Assets, still images, numerical candidates, tests or requirement mappings cannot substitute for that application. A owns G02/G03/G07/G08 and the physics/authority files; C owns AI/planning/broker. Their participation is required for whole-system acceptance, but does not justify leaving B's local RTL absent.

## Selected real increment

Implement a synthesizable single-clock bounded **integer inner-block encoder**, a B01/B03 building block. Its math and fixture byte order are already pinned; it requires neither board access nor A's still-open TRACE/public register freeze. It replaces an actual implementation gap with a testable hardware module. It deliberately produces the existing internal block format; TRACE outer metadata/little-endian word packing and public scheduling remain a separate future adapter. The main will independently verify observable RTL ports and exact output bytes, backpressure, invalid lengths/config, cancellation/reset and block recovery. Synthesis/timing and formal B01 remain unaccepted.

New operation B-DEEPEYE-BLOCK-ENCODER-20261018-08; worker work B-BLOCK-ENCODER-RTL-20261018-08-v1. One product Flash/max at most; unrelated runtime repair ownership remains untouched. Detailed fixed interface and completion criteria are in ../../codec/block-encoder-20261018-08/main/main_block_encoder_spec.md. No historical passing tests or old side effects are replayed by this audit.

Budget: this explicit new human instruction revokes the prior internal35%/unavailable-reading dispatch block. No claim that API capacity is unlimited. Quality, ownership, single product Flash and all H01–H15 remain unchanged.

## Delivered increment after this audit

Operation B-DEEPEYE-BLOCK-ENCODER-20261018-08 now adds the actual bounded integer
block encoder RTL and portable simulation tooling. Main rejected the worker's
original776-case result on BE01, corrected the unary writer width and added52
forced long-unary cases. Final828 regression cases and1559 independent cases
passed. This closes only the selected local submodule gap; every root card
above remains incomplete. The next input-ready B step is finite stream/queue
and block/reset integration; public TRACE/host/profile acceptance remains a
separate A/C dependency. See [exact evidence](../../codec/block-encoder-20261018-08/main/readme.md).
