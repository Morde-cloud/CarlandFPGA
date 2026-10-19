# Internal actual-application capture validation

This evidence concerns one synchronous digital wrapper of immutable generator12
and coherent-capture14. A configuration transfer immediately invalidates an old
window. The wrapper observes the generator's registered actual-applied event on
the following edge, takes a sampled baseline, and requires a new common R0 and
complete common R1 interval. Each high count comes from that lane's actual first
fall. Expected active parameters are comparison-only. Repeated tags/tuples do
not preserve old windows. No public ABI or physical/motion authority is created.

`oracle_frozen.json` predates the first author15 implementation read recorded in
`author-first-read/receipt.json`. The independent Python model uses absolute
frame deadlines and absolute sample-event indices. It does not import an author
model. `frozen-oracle-prep01` is the earlier successful preparation; the final
freeze uses maximum-period generator commands in the long overflow cases to
reduce incidental trace changes while still observing every raw counter edge.
Both preparations and their distinct inputs are retained. The final model,
testbench and vectors are unchanged throughout the main RTL run.

The main ModelSim SE-64 10.7 run checks 492,440 individual edges stored as 83,462
RLE rows, all 34 public observations per repeated edge. It enumerates 1,394 legal
small-width parameter configurations: 450 measurable and 944 ineligible. These
are configuration instances across widths, not globally distinct numeric tuples.
The six parameter sets are `2:6:1,3:6:64,2:2:64,3:3:32,16:18:64,32:64:64` for
COUNT/WITNESS/TAG. Coverage includes independent wrong/phase-shifted/missing
samples, actual digital loopback, transfer/application/slot races, same-tag ABA,
reset/STOP, mismatch, overrun, witness exhaustion and actual-application recovery.
It observes representative16-bit period65535 and raw overflow65536 in full;
32-bit count/64-bit witness tests are bounded. Code7 is a defensive invariant,
not claimed reachable in the correct composition. Eleven unsupported-parameter
cases require the wrapper's explicit diagnostic and exact supplied values.

From the repository root, with Python and ModelSim paths suited to the host,
run the following in a **new** owned output directory. `--tool` is optional on B
and defaults to `D:/modelsim1/win64`. No private controller file is required.

```text
python -B -X utf8 competition/deepeye/tools/control3d/main_verify_pwm_applied_capture.py --rtl competition/deepeye/fpga/control3d/deepeye_pwm_applied_capture.sv --generator competition/deepeye/fpga/control3d/deepeye_atomic_pwm.sv --capture competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv --tb competition/deepeye/tests/rtl/control3d/main_tb_pwm_applied_capture.sv --out competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/main/reproduce-new --owned-root competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/main --frozen competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/main/frozen-oracle
```

Three isolated faulty copies have actual public-port counterexamples. The input
segments are exact reset-bounded subsets selected from the pre-author frozen
vector file, with no input/expected-value changes and all34 fields still checked:

- `negative-controls/late-transfer`: delays invalidation until registered
  accepted/rejected and incorrectly exposes the old record before a transfer.
- `negative-controls-repair02/same-tag-cache`: caches an old raw record and
  incorrectly replays it after a same-tag application before a new complete cycle.
- `negative-controls-repair02/mismatch-admitted`: incorrectly allows a completed
  raw measurement that differs from the applied tuple.

Each directory contains the correct source, faulty source, two immutable inputs,
TB, selected vectors, command file and raw logs. To reproduce a counterexample,
copy those inputs to a fresh directory; run its recorded `vlib`, `vlog` and `vsim`
commands there. Compile/run `correct.sv` first, then recompile `mutant.sv` and run
the same public-port TB. A simulator exit0 can still contain `$fatal` under this
tool's command-file behavior: acceptance requires the exact PASS/error markers,
not exit code alone. `NEGATIVE_CONTROLS_ACCEPTED.json` binds the actual results.

The first same-tag copy failed to compile because its added declarations were
after their first use. The next copy compiled but exposed X before sampled reset.
Neither is counted as the required counterexample. Both failed preparations,
their original sources/logs and the two correction records remain. The final
copy masks reset/STOP and reaches the intended same-tag boundary failure. These
changes affect isolated deliberately faulty test copies only; production RTL,
frozen main oracle/inputs/TB and historical12/14 inputs are unchanged.

The latest local tool discovery found ModelSim and no Vivado. Synthesis and
implementation remain blocked; CDC/RDC, physical board, G05/B06/R03, system and
all29 formal acceptance cards remain not_run/unaccepted. Board access is A-only.
No authenticated source/session/request/control_epoch/capture_seq, host time,
freshness, TTL/profile/curvature, public TRACE/register/HWH/BOOT or complete
PC_DIRECT/FPGA-output path is established by this increment.

H01-H15, DEEPEYE-HUMAN-LOCK-20261014/revision1 remain pinned at
f5989cd5defce561f9ba98e6b18fc2682945f0a2; requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
design1011259415a0916054eb580687612580bc1e5f09. Historical op13's15 missing original
404 responses and op14's unavailable early author temporary preparation history
remain disclosed. This new evidence does not recreate or upgrade that history.

Main review rejected the original author runner qualification:13 of16 synthetic cases could upgrade timeout/exception/nonzero exit, simulator Error, or a display without the exact own fatal. After actual child completion, main changed only runner qualification; the same16 probes all pass and a fresh47-command author suite passed19 positive scenarios/208667 sampled edges/100587 assertion invocations/476 records,9 exact guards and5 mutant runs. Four mutant runs are intended behavioral rejections; the fifth is a deliberately faulty code7 demonstration, not normal-design coverage. Original runner, red probes, final run-c and every repair record are retained. No production RTL or independent main input/model/TB changed.

Author g15-b had no pre-run snapshot. Its later source/timestamp reconstruction is retained as historical context only, not proof of exact pre-run bytes. Final run-c and main repaired run have actual pre-run snapshots.

Author accidentally created root lib cache142B and failed-compile transcript602B outside its five paths; then moved them into owned evidence with hashes. Main verified surviving bytes. This scope deviation is disclosed, not retroactively authorized; no restoration/replay was attempted.

Original run-c tree manifest raced externally redirected stdout. Initial manifest bytes are preserved; child later reclosed its terminal tree. Main verified the actual final2683-file tree. Fresh main repaired run redirects its outer streams outside the hashed author tree.

Main cancellation request encountered already completed child. No cancellation occurred; final terminal completed/nonstale consumed before main repair; idle pool reclaimed0.

Old op13 missing15 original404 response bytes and op14 missing early temporary author history remain unchanged and are not recovered by op15.
