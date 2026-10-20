# Operation17: invalid-parameter guard and CODE7 qualification

A's review of operation16 at `f7736ac737d1c7b256974beb1574b94096819270` identified two existing P2 issues: invalid-parameter guard qualification accepted prefixed records or an additional unrelated Fatal, and ordinary group0 accepted the dedicated CODE7 observation. These are runner predicate defects, not newly established RTL regressions.

The exact A input bytes from commit `c77ee6460cc8dad527c4a7c5dad050c62a9be990`, comment6289372823 and archive manifest `096e27e8652cef8cc05abcdceca9689bd426fd73bb60a76d40abf7f7571fdaac` are retained under `inputs/`. No second download was needed: the previously collected bytes were independently rehashed and compared with their fixed Git blob IDs. `main/BASELINE_RED.json` and `main/check-02/EXACT_A_BEFORE_AFTER.json` record actual Python calls accepting all three on the original runner and rejecting them on the repaired runner.

Guard qualification now requires exactly one complete six-field diagnostic, then exactly one exact own-fatal on stdout. Only the literal optional `# ` prefix and LF/CRLF framing are allowed. Duplicate/conflicting/malformed records, additional Error/Fatal diagnostics, misplaced stderr records and the guard-missing marker reject. Signed input widths and nonnegative safe widths have bounded canonical ASCII decimal spelling. Values must match the requested unsupported integer widths and their clamps, and the actual process must have completed with integer exit0 or exit1.

CODE7 is permitted exactly once before statistics only for PASS group30/loopback0. That dedicated PASS also requires the observation. Ordinary group0 without CODE7 and the dedicated group30 control with CODE7 remain accepted; other groups, loopback1, failure outcomes, duplicates, malformed or misplaced observations reject.

Main independently designed and implemented the runner changes. A single Flash/max child authored seven added test methods in exclusive test/evidence ownership. Main consumed its completed/nonstale result before taking over those files. Main then found one incorrect new healthy-control expectation: a fully supported32/64/64 request was expected to pass when the DUT emitted a guard failure. The child result and candidate source remain intact. Main recorded that actual wrong acceptance, froze77 additional expectations, added unsupported-request eligibility, corrected only this new control and added one test method. Original23 method source bodies are unchanged. Main is not presented as a separate independent implementer of its own source.

Final source: runner SHA256 `b6735257dbfc107a14791ec69cb7386f306d0408173acf9466a0f69c93c30b94`; test SHA256 `f8d4d5633949f8583e2d25b2622b3a67b30a05880bd84c2788e327c440516a34`.

Final actual Python results:

- 31 unittest methods pass in the worktree and again in a minimal directory containing only runner/test files with the same relative layout.
- The exact archived original23-method test file passes against the final runner.
- 1007 expected cases were frozen before the first implementation;77 supplemental cases were frozen before the request-eligibility correction. All1084 match their independent expectations, including82 accepting controls. The two freezes and their chronology remain separate.
- All three exact A counterexamples reject, and the two original operation16 negative fixtures remain rejected.
- The original47-command B15 suite's94 stdout/stderr streams still match their raw hashes. All33 saved scenarios retain expected classifications:19 positives,4 expected-failure mutant runs,1 faulty-copy CODE7 run,9 parameter guards. The208667 sampled edges are reused historical data, not new execution.

Reproduce from the checkout with a fresh output directory:

```text
python -B competition/deepeye/tests/control/test_pwm_applied_capture_runner.py
python -B competition/deepeye/evidence/control3d/pwm-runner-qualification-20261020-17/main/verify17.py --root . --out <new-directory>
```

The first command is portable with only the runner and test files. The second also needs the committed frozen cases, exact A inputs and referenced old operation15/16 evidence. It runs Python only and prohibits simulator calls in classifier invocations. Main command argv, exits and raw logs are under `main/check-02*` and `main/final-tests/`. `main/AUTHOR_AUDIT.json` records the four retained author runs and corrects the author's declared test byte count: actual candidate24934 bytes, rather than24879. Its source hash was correct.

All intermediate results, baseline failures, author source snapshots and old evidence remain. The first child request was rejected before admission because it used absolute ownership paths; a supported health read confirmed no job before the project-relative correction. This was an admission correction, not duplicate execution. Local tool-entrypoint errors and the original op15 quota failure remain in private receipts; no failed controller resume or unknown side effect was replayed.

Only runner/test and new operation17 evidence/handoff paths change. RTL/TB, prior08–16 artifacts, the protected dirty codec input and untracked simulator libraries remain untouched. There is no new ModelSim/Vivado/synthesis/implementation/CDC/RDC/board/system result. A's OOC statement was read as a report; its synthesis source was not audited here. All29/G05/B06/R03/board/system remain `not_run`; no public ABI/TRACE/register/HWH/BOOT/clock/source/TTL/profile/curvature/motion authority is granted.

H01–H15 / DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, contract pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, frozen design `1011259415a0916054eb580687612580bc1e5f09` remain fixed. Only A operates the physical board.
