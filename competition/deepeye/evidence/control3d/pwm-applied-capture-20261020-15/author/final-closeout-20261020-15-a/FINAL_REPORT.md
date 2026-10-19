# B op15 applied-capture author terminal report

- Task: DEEPEYE-IMPLEMENTATION-20261014/v1
- Work: B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1
- Operation: B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15
- Result: PASS (author-side local ModelSim simulation only)
- Parent product main: 01a13b55-095b-7461-8dd5-5476a130bd82
- Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1, H01-H15; requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804
- Frozen design: 1011259415a0916054eb580687612580bc1e5f09
- Worktree: D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014
- Branch: codex/b/deepeye-implementation-20261014
- HEAD: 7dd2c4108ee49cc6e0feb7c715d786f8b11a99c2
- Positive scenarios: 19 passed, 208667 samples, 100587 assertions, 476 records, zero mismatches
- Exhaustive small domain: 1394 legal triples, 450 eligible sampled records
- Negative behavior: 5 mutant runs, 9 exact invalid-parameter diagnostics
- ModelSim: Model Technology ModelSim SE-64 vlog 10.7 Compiler 2017.12 Dec  7 2017 / Model Technology ModelSim SE-64 vsim 10.7 Simulator 2017.12 Dec  7 2017
- Runner actual exit: 0

## Owned files

- competition/deepeye/fpga/control3d/deepeye_pwm_applied_capture.sv: d8c33ebad98acca113e18dbc5831643646663b946714af139d8b1637047356f3
- competition/deepeye/fpga/control3d/pwm_applied_capture_candidate.md: 825f3dff310fc3c8b2c94c22d5fa3b35559f20fc15f786555581712c2e9fe495
- competition/deepeye/tests/rtl/control3d/tb_pwm_applied_capture.sv: d31eb33a117fb3ea612ab50d2bffc6cd3ab8edc901337bff7f95e76809a2e0b5
- competition/deepeye/tools/control3d/run_pwm_applied_capture.py: 331b3a4aa4cc9baa3b378e27dc1accd50f2e2bce60ad50348b57603ccd17d18e
- competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author/: final tree hash in TERMINAL_MANIFEST.json

## Limitations

No Vivado synthesis, implementation, place-and-route, static timing, CDC/RDC, board or system
run was performed. All29 formal cards and G05 applied-command/full-cycle/system binding remain
not_run/unaccepted. Actual digital loopback is supplemental and explicitly named. Code7 is
demonstrated only on a deliberately faulty wrapper copy; it is not claimed reachable in the
correct normal composition. This report does not self-accept or claim publication.
