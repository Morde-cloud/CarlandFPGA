# Independent single-channel raw PWM measurement review

Operation `B-DEEPEYE-PWM-EDGE-MEASURE-20261020-13`, task
`DEEPEYE-IMPLEMENTATION-20261014/v1`. This evidence concerns one synchronous
sampled digital input and one raw result slot. It supplies no physical clock,
asynchronous pin, synchronizer, waveform liveness or motion authority.

The independent Python reference computes differences of absolute sample-edge
indices R0/F0/R1 and maintains a separate result queue. It imports no author
model or PWM generator. `oracle_frozen.json` and `frozen-oracle/` record its
source, replay vectors, timestamp and hand-worked sanity cases before the main
read the author implementation. RLE combines only equal complete input and
expected-output rows. The testbench still checks every repeated clock edge;
its public-port trace records each checked run's length and ending edge.
COUNT_W2/3/4 cover all 129 representable legal period/high pairs. COUNT_W16
fully observes selected periods through 65,535 and overflow at 65,536. The
COUNT_W32 checks are bounded; a maximum 32-bit period/overflow is not executed.
The deterministic suite contains 1,253,606 sampled edges, including 60,000
randomly scheduled samples. These counts are neither independent commands nor
physical measurements.

With ModelSim available, run from the product worktree (use a fresh owned
output directory; the runner refuses to overwrite earlier evidence):

```powershell
& D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 `
  competition/deepeye/tools/control3d/main_verify_pwm_edge_measure.py `
  --rtl competition/deepeye/fpga/control3d/deepeye_pwm_edge_measure.sv `
  --tb competition/deepeye/tests/rtl/control3d/main_tb_pwm_edge_measure.sv `
  --frozen competition/deepeye/evidence/control3d/pwm-edge-measure-20261020-13/main/frozen-harness-03 `
  --out competition/deepeye/evidence/control3d/pwm-edge-measure-20261020-13/main/review-run `
  --owned-root competition/deepeye/evidence/control3d/pwm-edge-measure-20261020-13/main `
  --tool D:/modelsim1/win64
```

The runner records actual commands, tool versions, raw stdout/stderr, exit
codes, exact executed source, vectors and public-port logs. It compares the
replay to the frozen bytes and treats errors/fatals/missing markers as failure.
An isolated negative-control run is successful only when its altered source
produces the explicit public-port mismatch, not merely a compiler failure.
The terminal `ACCEPTANCE.json` is the decision; this reproducibility guide
alone is not a passed simulation.

An old complete record can remain transport-valid while later input overflows.
Loss pulses/stickies/saturation report the lost input; they do not make the old
record current. STOP/reset/rearm flush all old window state. Integration still
needs source/session/request/epoch and start/end timing, three-channel complete
same-period capture after applying a command, live-edge/freshness rules,
profile decoding, public ABI, clock/BOOT and final movement authority. No
zero/full-duty or absence watchdog behavior is invented by this primitive.

H01-H15, DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, frozen design
`1011259415a0916054eb580687612580bc1e5f09` remain unchanged. All 29 formal
cards, G05/B06/R03, board/system and CDC/RDC remain not_run/unaccepted.
Vivado was not found by the recorded local preflight, so synthesis and
implementation are blocked. A alone may operate the physical board.
