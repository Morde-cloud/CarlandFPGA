# First-capture runner qualification, operation19

This operation repairs three Python qualification defects found by the coordinator at operation18 head `6c1dbca6ec15d8bd3c7bc123cf839a2152869a9b`. The coordinator's operation18 decision remains **REVISE** in the original evidence and in `inputs/`. The new bounded main decision is in `ACCEPTANCE.json`; independent coordinator review of this repair is still pending.

The guard now rejects foreign plain/case-varied Error/Fatal diagnostics. A shared phase-aware tally validator accepts multiple legitimate stage-local zero tallies, requires normal counts to stay zero, and permits at most one own-fatal count after its matched fatal. Malformed, contradictory, premature or extra error counts fail. Mutant runs now have distinct target_hit, survived and execution_error outcomes: every selected run must be valid and each mutation class must have at least one target hit. A healthy survivor never counts as a hit.

Before editing, main saved the exact 43 parser and 4 aggregation probes from the coordinator and froze 831 supplemental parser and 36 supplemental aggregation cases. Main had inspected the implementation/findings: this is not a blind oracle. `baseline/RESULT.json` reproduces the coordinator's 15 parser misaccepts and 3 aggregation misaccepts. Across all frozen cases the old source has 585 parser mismatches and 30 aggregation mismatches, including 3 retained missing-file exceptions. `repaired-01/RESULT.json` has 874 parser and 40 aggregation cases with zero mismatches and exceptions. Expectations were not relaxed.

Actual Python checks in `final-checks/` pass 45 current unit methods, 45 methods in a minimal portable directory, and the unchanged original33 methods against the repaired runner. Eight new Python CLI processes execute the real runner entrypoint with explicitly synthetic compiler/simulator seams: two valid controls return0, all-survivors and five selected-run failure cases return1. The outer receipt-checking wrapper returns0 only after checking the inner exit. Generated mutant source copies are uncompiled synthetic orchestration artifacts, not new RTL tests. Process/network execution is forbidden inside these probes.

The 21 exact saved author logs listed in `final-checks/HISTORICAL_RECLASSIFICATION.json` were rehashed and classified read-only against the repaired runner. They are historical logs, not new ModelSim runs. No ModelSim, Vivado, board or new RTL suite was run. All old tracked files except the two authorized Python sources remain byte-identical (5743 of5745); the protected dirty codec input remains intact.

Reproduce Python units from the repository root:

```text
python -B competition/deepeye/tests/control/test_first_capture_deadline_runner.py -v
python -B competition/deepeye/evidence/control3d/first-capture-runner-qualification-20261021-19/verify19.py --root . --out <new-directory> --expect repaired
```

Use a fresh output directory. The verifier's frozen expectations and original coordinator inputs are adjacent to it. To exercise a CLI boundary, add `--cli w2-timeout` (expected process exit1), or `--cli all-targets` (exit0). `execution-scripts/` preserves exact local startup/freeze/wrapper/check/audit sources and receipts; local paths in those historical scripts are provenance, not prerequisites for the portable unit run.

Main designed and evaluated this Python repair. No separate implementer review or new functional RTL acceptance is claimed. Historical operation18 source, RTL/TB/oracle, vectors, failure logs, ACCEPTANCE and handoff remain unchanged. Its 132010+112 main simulation edges and four numeric RTL mutants retain their original scope. Prior operation17 acceptance does not accept operation18/19.

All29/G05/B06/R03/board/system remain not_run. No physicalTTL, source freshness, BOOT/clock, public TRACE/register/HWH ABI, ENABLE or motion authority is granted; no product STOP/PWM connection. New synthesis/implementation/timing/CDC/RDC remain not_run/blocked. A alone operates the physical board.

DEEPEYE-HUMAN-LOCK-20261014/revision1 H01–H15 requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`; contract pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`; design `1011259415a0916054eb580687612580bc1e5f09`. Full3D/UI/solid collisions/free camera/editable/random layouts/equal gates/full passage/hidden truth/causal observations/substantive online3D PC AI and both H12 control chains remain mandatory.
