# Existing physical baseline and UART evidence audit

Work `B-PHYSICAL-BASELINE-UART-EVIDENCE-20261104-247`, implementation task v1. Canonical child `/root/physical_uart_evidence247` validated job `child-3bb15c7368d94ae0a8fcca501d3039c0` before project execution. Writes remain inside this review directory. No hardware, network, tests, vendor builds or product edits were performed. Main alone makes integration and acceptance decisions.

All H01–H15 revision2 were read. Canonical requirements hash independently equals fixed `2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d`. Fixed reference is commit `817b355887c14cfa9c5d830c8589684f994af082`; local Git object comparison was unavailable (`git show`128, `ls-tree`: not a tree object), so no commit-content equality is claimed. Historical revision1 hash `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804` remains historical. Only human H07/H10 amendments apply. Initial-only slider constraint remains intact: physical following must read actual accepted speed and must never set the initial slider, live AI cap or virtual generation.

## Artifacts and deployment

Read-only collection command `.local/venv/Scripts/python.exe -B output/drill-live-link-20261104/review/collect_audit.py` returned0. `evidence-inventory.json` contains individual paths, expected/actual hashes and HWH fields. Parent baseline pins9/9, MCU build entries18/18, overlay artifacts6/6, reports14/14, source entries6/6, build inputs6/6 and copied inputs3/3 match. These checks establish file identity only.

| Artifact | SHA256 |
|---|---|
| MTR4 motor_runtime/build/motor_probe.out | 69c5c57e6f896b879bb41a73d4f114180e11a9f16a8894eae6b035893848841f |
| run-20261103-195848/artifacts/mcu_link.bit | f283f498ab2f7acaa19719640bb6f4856b8ba5a6662c88a5ec02a3cbddf163b9 |
| Same run mcu_link.hwh | 2a574bd60bde1fea5cf5936be9403f6afe39a0eb808ba2a03782f73058366206 |

Paths in this report are relative to `output/drill-demo-code-20261025/` unless explicitly stated. `motor_runtime/evidence/mtr4-flash-vmoff-20261103-2247.json`, `/stages/1`, records historical DSLite MAIN-only programming/verification, exit0, exact MTR4 image and successful verification. Build manifest candidate-only flags describe the build stage; they do not negate the separate later deployment receipt. `motor_runtime/evidence/HUMAN_ACCEPTANCE_MTR4.json` records visible25→50→75→50→25→OFF speed differences and stopped observation, without product callback or FPGA acceptance.

Latest stored observation is `motor_runtime/evidence/v9-final-default500-20261103.json`, `/final`: signature0x4d545234, state3, last_seq296, armed0, motorOFF, bus_errors0, yaw2089/pitch1958. `gimbal_smoothness_v9/STATUS.json` records VM disconnected. These are historical observations, not proof of present power/boot/sequence. Never assume next sequence297 after a reset or unknown interval. Motor runtime's older seq200/next201 is superseded historical state. RPM, voltage/frequency, current and thermal margin remain unmeasured.

## UART build and limits

Historical `overlay/run-20261103-195848/COMMAND.json` and `RESULT.json` record Vivado2022.1 Build3526262, batch command, exit0 and generated matched artifacts. Device xc7z020clg400-1. HWH XML and routed reports agree: mcu_uart/AXI UARTLite2.0,0x43C00000..0x43C0FFFF,100MHz,1152008N1. Routed report clock is10ns; board preset's read-only GP0 metadata10MHz is separately documented and must not be mistaken for the actual100MHz propagated UART clock.

`pmod_uart.xdc`, implemented constraints and `reports/exact_uart_ports.tsv` agree: output uart_txd=Y18/PMODA1→G3507 PB7 RX; input uart_rxd=Y19/PMODA2←PB6 TX; LVCMOS33, RX pullup, PMODA5 common GND. Runtime profile is hardware_confirmed=false and product_overlay_merged=false. XDS110/PC and FPGA must not simultaneously drive PB7.

Historical routed timing WNS3.905ns/WHS0.032ns/WPWS4.020ns, no internal unconstrained endpoints, DRC0 and935/935 routable nets routed. CDC report has one CDC-3 informational four-stage RX synchronizer. Missing external RX input delay and TX output delay remain two TIMING-18 warnings; external electrical/timing measurements are absent. All14 listed routed reports exist and match hashes. No independent physical measurement or full RDC proof follows from those reports. MCU manifest retains TI5.1.1.LTS/SDK2.11 command paths but does not hash every SDK startup/header/library/compiler dependency; full reproducible toolchain closure is not claimed.

This is an isolated UART overlay. Loading it replaces PL; it is not the active product overlay. PYNQ runtime metadata parsing, board load, real SSH/header UART and product merge remain not_run in this evidence. Historical G3507 PC COM9 success is not actual PYNQ-path success. The path label in base DisplaySession.record is descriptive, not evidence that that route was exercised.

## Ordering and freshness

Source positions: `motor_runtime/variable_session.py:61`, `fpga_link/session.py:142`, `fpga_link/ssh_client.py:83`, `motor_runtime/motor_control.c:13` and `:25`, `motor_runtime/src/free_control.c:156`.

- Motor-OFF pose: STATUS→ARM→SET. Motor-ON pose: STATUS→STATUS→ARM→SET. One finite synchronous dual-ID target uses500ms default, explicit100..1000ms. ACK precedes actual servo dispatch and is not arrival evidence.
- Motor start: STATUS→ARM→MOTOR. Active update: STATUS→MOTOR. Active keepalive: STATUS→MOTOR, never ARM/SET. Same-source already-armed ARM does not refresh the motor-only deadline. Pose does not renew the motor lease.
- Motor default lease300ms (allowed100..500), servo freshness<=1000ms, software watchdog500ms. Heartbeat waits100ms and shares the call lock with pose; the board loop is serial. Four pose replies may each wait up to0.3s, so actual latency must leave renewal margin. Wire-only lower bounds are22.22ms for four32-byte request/reply exchanges at1152008N1, plus journal/network/device work. No new latency measurement was made.
- Keepalive can renew the last duty while accepted application data has stopped updating. Request expiry is transport/session age; source_seq/observation_seq are serialized but MCU logic does not establish their causal freshness. The new application adapter must enforce source epoch/age, mode/reset/pause/loss and explicit stop. Network traversal alone does not change PC_DIRECT into FPGA_OUTPUT.
- New-sequence equal poses reissue SET; no baseline equality filter exists. STOP/watchdog clears motor/software armed/pending state, but no servo cancellation frame is emitted, so already-issued finite servo motion may continue. Do not promise immediate physical servo arrest from a STOP acknowledgment.

These points are source inspection plus historical evidence, not new tests. `gimbal_smoothness_v9/review/audit-evidence.json` contains prior34-check real-C/fake-feedback timing results and host traces. Its1000ms host snapshot predates the default change. `gimbal_smoothness_v9/evidence/default500-checks.json` later records3+17+10 offline checks, returncode0, and its5 source hashes match current files. Older variable-checks has2 stale host hashes; older fpga_link latest-checks has5. Preserve their chronology rather than calling old manifests current. `historical-commands.json` copies27 command records, evidence paths, JSON positions and recorded exits/output; no listed historical command was rerun.

## Minimal A integration prerequisites

1. A checks current product BD/address/pin/clock/reset ownership, integrates equivalent UART into that product, then regenerates exact paired product BIT/HWH/reports. This standalone image must not overwrite active product PL as an assumed integration step.
2. Confirm actual crossed3.3V UART/common ground, exclusive PB6/PB7 ownership, present MCU identity/boot/sequence, power and observer. Preserve MTR4 image, calibrated ranges and saved center; no automatic flash/reset or old sequence reuse.
3. Bind only actual accepted orientation/speed through explicit reference/range/source freshness gates. Keep renewal independent of unchanged-target suppression; preserve failure latch/no replay and stop-on-loss. Do not change virtual control or initial-only speed semantics.
4. A collects actual PYNQ runtime metadata, UART/finite pose, concurrent motor+pose and loss-stop evidence against operation_id/request_hash/tested_commit and exact product artifact hashes. Main alone accepts results. Full-range combinations,68deg upper clearance, current physical concurrency and continuous product path remain unverified here.
