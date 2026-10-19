# Operation14 independent shared-edge capture review

This directory records bounded digital verification of a new shared three-lane
capture state machine. A record needs one observed common rising start, each
lane's first falling edge strictly inside that interval, and a common rising
end. The start/end witnesses are local sample indices since explicit rearm.
They are not BOOT, host time, an applied-command proof or motion authorization.

The main froze its absolute-event-index reference and six vector files before
reading the author RTL. `oracle_frozen.json` records that boundary. RLE compresses
identical complete input/expected-output rows; the testbench checks every
repetition at public ports. No generator model, author model or hierarchical
internal-state access supplies the expected measurement.

Actual main ModelSim SE-64 10.7 simulation checked 800,870 sampled edges in six
configurations and 65,156 RLE rows. It exhausts 450 legal COUNT_W2/3 period/high
triples, repeats nine under a shorter witness window, and adds 48,000 random
samples. COUNT_W16 observes periods through65,535 and overflow65,536; small
WITNESS_W2/3 really exhaust the namespace. COUNT_W32/WITNESS_W64 runs are bounded,
not maximum-width traversal. Eleven invalid parameter triples reached the
explicit DUT time-zero diagnostic, including zero/negative representatives.

`run-01` retains the initial main harness failure: all six positive cases passed,
but the diagnostic parser wrongly required parameter values on the fatal line.
The RTL printed exact values immediately before its own fatal. `HARNESS_CORRECTION.json`
and the diff document the corrected parser; the oracle, all vectors and testbench
are unchanged. `run-02` requires that exact display plus the exact DUT fatal,
so an unrelated elaboration failure does not count as rejection. The simulator
returns zero for these stopped fatal runs; acceptance uses the actual diagnostic.

The two isolated mutants relax the shared R1 requirement and retain a stale slot
over rearm. Both fail at actual public ports; original RTL bytes are preserved.
See `negative_controls.json`. `ACCEPTANCE.json` and `author_audit.json` record
terminal source matching and final main judgment separately from author claims.

Reproduce in a fresh output directory from the product worktree:

```powershell
python -B -X utf8 competition/deepeye/tools/control3d/main_verify_pwm_coherent_capture.py --rtl competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv --tb competition/deepeye/tests/rtl/control3d/main_tb_pwm_coherent_capture.sv --frozen competition/deepeye/evidence/control3d/pwm-coherent-capture-20261020-14/main/frozen-harness02 --out competition/deepeye/evidence/control3d/pwm-coherent-capture-20261020-14/main/review-fresh --owned-root competition/deepeye/evidence/control3d/pwm-coherent-capture-20261020-14/main
```

Use `--tool` for the local ModelSim binary directory; the recorded B installation
is D:/modelsim1/win64. Preserve original failed outputs; do not reuse an output
directory. The test runner copies exact input sources before simulation.

Only synchronous binary sampled behavior is covered. An old queued record may
remain transportable after acquisition halts. Full G05 after-application capture,
source/session/request/control_epoch binding, real clocks/freshness/TTL/profile,
public TRACE/register/HWH/BOOT ABI, asynchronous capture, CDC/RDC, synthesis,
implementation and both complete control paths remain open. All29 formal cards
remain not_run/unaccepted; physical board A-only. H01-H15 contract
DEEPEYE-HUMAN-LOCK-20261014/revision1 requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 and frozen design
1011259415a0916054eb580687612580bc1e5f09 are unchanged.
