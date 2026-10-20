"""Audit existing operation19 results and preserve a bounded main decision."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, subprocess

O = Path(__file__).resolve().parent
W = Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
EP = "competition/deepeye/evidence/control3d/first-capture-runner-qualification-20261021-19"
E = W / EP
R = "competition/deepeye/tools/control3d/run_first_capture_deadline.py"
T = "competition/deepeye/tests/control/test_first_capture_deadline_runner.py"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_bytes())
def put(p, value):
    with p.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
def git(*args):
    return subprocess.check_output(["git", "-c", "core.longpaths=true", "-C", str(W), *args])

start = read(O / "STARTED.json")
assert git("rev-parse", "HEAD").decode().strip() == start["baseline"]
assert not git("diff", "--cached", "--name-only").strip()
before = read(O / "TRACKED_BEFORE.json")
changes = {p: {"before": h, "after": sha(W / p)} for p, h in before.items() if sha(W / p) != h}
assert set(changes) == {R, T} and len(before) == 5745
assert sha(W / "handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json") == "6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8"
inputs = read(E / "inputs/SOURCE_INDEX.json")
for row in inputs:
    assert sha(W / row["path"]) == row["sha256"]
for name, digest in start["decision_pins"].items():
    assert sha(E / "inputs" / name) == digest
assert read(E / "inputs/COMPLETED_REVIEW_DECISION.json")["decision"] == "REVISE"
freeze = read(E / "FREEZE.json")
for name, digest in freeze["files"].items():
    assert sha(E / name) == digest
assert sha(O / "freeze19.py") == freeze["main_source_sha256"]
assert sha(E / "verify19.py") == "0e73afec1d41b0d8b370742bf4ef3fddd9b8ac2b013b035081b9eb5064bd5921"
baseline, repaired = [read(E / label / "RESULT.json") for label in ("baseline", "repaired-01")]
assert baseline["coordinator_parser_misaccepts"] == 15 and baseline["coordinator_aggregate_misaccepts"] == 3
assert baseline["parser_mismatches"] == 585 and baseline["aggregation_mismatches"] == 30
assert baseline["aggregation_exceptions"] == 3
assert repaired["parser_cases"] == 874 and repaired["aggregation_cases"] == 40
for key in ("coordinator_parser_misaccepts", "coordinator_aggregate_misaccepts",
            "parser_mismatches", "aggregation_mismatches", "parser_exceptions", "aggregation_exceptions"):
    assert repaired[key] == 0
for value in (baseline, repaired):
    assert value["vendor_invocations"] == 0 and value["blocked_process_network_attempts"] == []
assert baseline["source_sha256"] == freeze["source_before_sha256"]
assert repaired["source_sha256"] == sha(W / R) == "283902fbb281bd313b553e2efbc622b49441c9250cded0461fa92bc700ad8eba"
checks = read(E / "final-checks/RESULT.json")
assert checks["status"] == "PASS" and checks["runner_sha256"] == sha(W / R)
assert checks["test_sha256"] == sha(W / T) == "1247a7c84fde50368ddf88d967e7b8d14468719da023b498d64014c63ebe8159"
assert checks["unit_methods"] == checks["portable_methods"] == 45
assert checks["original_methods_unchanged_and_run"] == 33
history = read(E / "final-checks/HISTORICAL_RECLASSIFICATION.json")
assert len(history) == 21 and all(row["accepted"] for row in history)
for row in history:
    assert sha(W / row["path"]) == row["sha256"]
for row in read(E / "final-checks/COMMANDS.json"):
    assert row["exit_code"] == row["expected_exit"]
    for stream in ("stdout", "stderr"):
        assert sha(E / "final-checks" / (row["name"] + "." + stream + ".txt")) == row[stream + "_sha256"]
for i, expected in enumerate((0, 0, 1, 1, 1, 1, 1, 1)):
    label = f"cli-{i:02d}"
    receipt = read(E / (label + ".command.json"))
    result = read(E / label / "CLI_RESULT.json")
    assert receipt["exit_code"] == result["actual_entrypoint_return"] == expected
    assert result["vendor_invocations"] == 0 and result["blocked_process_network_attempts"] == []
    for stream in ("stdout", "stderr"):
        assert sha(E / (label + "." + stream + ".txt")) == receipt[stream + "_sha256"]
for label in ("baseline", "repaired-01"):
    receipt = read(E / (label + ".command.json"))
    assert receipt["exit_code"] == 0
    for stream in ("stdout", "stderr"):
        assert sha(E / (label + "." + stream + ".txt")) == receipt[stream + "_sha256"]

scripts = E / "execution-scripts"
scripts.mkdir(exist_ok=False)
for name in ("start19.py", "freeze19.py", "run19.py", "check19.py", "accept19.py"):
    (scripts / name).write_bytes((O / name).read_bytes())
for name in ("STARTED.json", "OWNERSHIP_AUDIT.json", "TRACKED_BEFORE.json"):
    (scripts / name).write_bytes((O / name).read_bytes())
summary = {
    "at_utc": datetime.now(timezone.utc).isoformat(),
    "task_id": start["task_id"], "task_version": 1, "operation_id": start["operation_id"],
    "work_id": start["main_execution_work"], "thread_id": start["thread_id"], "actual_turn": start["actual_turn"],
    "decision": "MAIN_ACCEPT_BOUNDED_PYTHON_REPAIR_PENDING_COORDINATOR_REVIEW",
    "prior_operation18_coordinator_decision": "REVISE",
    "prior_decision_sha256": start["decision_pins"]["COMPLETED_REVIEW_DECISION.json"],
    "baseline": start["baseline"], "changed_sources": changes, "old_tracked_total": len(before),
    "old_tracked_unchanged": len(before) - len(changes), "coordinator_inputs_verified": len(inputs),
    "root_causes": ["FC18-P2-01 foreign plain/case-varied guard diagnostics",
                    "FC18-P2-02 malformed/conflicting/extra error tallies",
                    "FC18-P2-03 selected mutant execution errors masked by another width target hit"],
    "baseline_coordinator_misaccepts": {"parser": 15, "aggregation": 3},
    "baseline_all_mismatches": {"parser": 585, "aggregation": 30, "aggregation_exceptions": 3},
    "repaired": {"parser": 874, "aggregation": 40, "mismatches": 0, "exceptions": 0,
                 "unit_methods": 45, "portable_methods": 45, "unchanged_original_methods_run": 33,
                 "actual_python_cli_cases": 8, "readonly_historical_author_logs": 21},
    "test_seams": "Synthetic compiler/simulator output only; actual qualification, aggregation and CLI entrypoint execute.",
    "review_limit": "Main inspected findings/code then froze expectations before repair; main designed and evaluated repair, not blind or a separate implementer review.",
    "new_workers": 0, "new_ModelSim": 0, "new_Vivado": 0, "new_RTL_cases": 0,
    "requirements_sha256": start["requirements_sha256"], "requirement_ids": start["requirement_ids"],
    "contract_pin": start["contract_pin"], "design": start["design"],
    "formal_status": "all29/G05/B06/R03/board/system not_run; no ABI/BOOT/clock/physicalTTL/freshness/ENABLE/motion grant",
}
put(E / "ACCEPTANCE.json", summary)
readme = """# First-capture runner qualification, operation19

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
"""
with (E / "README.md").open("x", encoding="utf-8", newline="\n") as f:
    f.write(readme)
paths = [W / R, W / T] + sorted(p for p in E.rglob("*") if p.is_file())
assert not any("__pycache__" in p.parts for p in paths)
rows = [{"path": p.relative_to(W).as_posix(), "sha256": sha(p), "bytes": p.stat().st_size} for p in paths]
put(O / "SELECTED.json", {"root": str(W), "baseline": start["baseline"],
    "operation_id": start["operation_id"], "acceptance_sha256": sha(E / "ACCEPTANCE.json"), "files": rows})
print(json.dumps({"status": summary["decision"], "old_unchanged": 5743,
                  "selected_files": len(rows), "selected_bytes": sum(r["bytes"] for r in rows),
                  "acceptance_sha256": sha(E / "ACCEPTANCE.json")}))
