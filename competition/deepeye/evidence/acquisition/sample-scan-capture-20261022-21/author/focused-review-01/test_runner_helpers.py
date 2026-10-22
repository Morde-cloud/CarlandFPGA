from __future__ import annotations

import importlib.util
import os
from pathlib import Path

RUNNER = Path(r"D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/tools/acquisition/run_sample_scan_capture.py")
before = set(os.listdir(Path.cwd()))
spec = importlib.util.spec_from_file_location("sample_scan_runner_review", RUNNER)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
after = set(os.listdir(Path.cwd()))
assert before == after, (before, after)
assert not (RUNNER.parent / "__pycache__").exists()

checks = 0


def expect(label, actual, wanted):
    global checks
    checks += 1
    assert actual == wanted, f"{label}: expected={wanted!r} actual={actual!r}"


def expect_class(label, result, ok, classification=None):
    expect(label + "_ok", result["ok"], ok)
    if classification is not None:
        expect(label + "_classification", result.get("classification"), classification)
    if not ok:
        expect(label + "_has_reasons", bool(result["reasons"]), True)


compile_ok = "Errors: 0, Warnings: 0\n"
stats = ("SAMPLE_SCAN_STATS case=unit checks=1 errors=0 windows=1 events=4 "
         "scans=1 retired=1 discarded=0 order_errors=0 overruns=0 partial_len=0 "
         "occupied=0 armed=1 exhausted=0")
normal = f"{stats}\nSAMPLE_SCAN_PASS\n{compile_ok}"
expected_stats = {"events": 4, "scans": 1, "retired": 1, "discarded": 0,
                  "order_errors": 0, "overruns": 0, "partial_len": 0,
                  "occupied": 0, "armed": 1, "exhausted": 0}

expect_class("compile_ok", module.classify_compile(0, compile_ok, ""), True)
expect_class("compile_exit", module.classify_compile(1, compile_ok, ""), False)
expect_class("compile_missing_summary", module.classify_compile(0, "", ""), False)
expect_class("compile_warning", module.classify_compile(0, "** Warning: unit\n" + compile_ok, ""), False)
expect_class("compile_error", module.classify_compile(0, "** Error: unit\n" + compile_ok, ""), False)

expect_class("normal_ok", module.classify_simulation_output(0, normal, "", "unit", expected_stats), True)
expect_class("normal_exit", module.classify_simulation_output(1, normal, "", "unit", expected_stats), False)
expect_class("normal_duplicate_pass", module.classify_simulation_output(0, normal + "SAMPLE_SCAN_PASS\n", "", "unit", expected_stats), False)
expect_class("normal_duplicate_stats", module.classify_simulation_output(0, stats + "\n" + normal, "", "unit", expected_stats), False)
expect_class("normal_malformed_stats", module.classify_simulation_output(0, normal.replace(" armed=1", ""), "", "unit", expected_stats), False)
expect_class("normal_case_mismatch", module.classify_simulation_output(0, normal, "", "other", expected_stats), False)
expect_class("normal_tb_error", module.classify_simulation_output(0, normal.replace("errors=0", "errors=1"), "", "unit", expected_stats), False)
expect_class("normal_literal_error", module.classify_simulation_output(0, "# ** Error: injected\n" + normal, "", "unit", expected_stats), False)
expect_class("normal_warning", module.classify_simulation_output(0, "# ** Warning: injected\n" + normal, "", "unit", expected_stats), False)
expect_class("normal_identity", module.classify_simulation_output(0, normal.replace("events=4", "events=5"), "", "unit", expected_stats), False)
expect_class("normal_guard_fatal", module.classify_simulation_output(0, "# ** Fatal: deepeye_sample_scan_capture: SEQ_W out of range\n" + normal, "", "unit", expected_stats), False)

message = "deepeye_sample_scan_capture: SEQ_W out of range"
guard = f"# ** Fatal: {message}\n# Errors: 1, Warnings: 0\n"
healthy = "# GUARD_CONTROL_ALIVE\n# Errors: 0, Warnings: 0\n"

expect_class("guard_ok", module.classify_guard_output(0, compile_ok, "", 0, guard, "", "SEQ_W", message), True, "dut_guard_rejected")
expect_class("guard_healthy", module.classify_guard_output(0, compile_ok, "", 0, healthy, "", "HEALTHY", None), True, "guard_healthy")
expect_class("guard_fake_tb", module.classify_guard_output(0, compile_ok, "", 0, "# ** Fatal: tb_sample_scan_capture: SEQ_W out of range\n# Errors: 1, Warnings: 0\n", "", "SEQ_W", message), False)
expect_class("guard_trailing", module.classify_guard_output(0, compile_ok, "", 0, guard.replace("out of range", "out of range extra"), "", "SEQ_W", message), False)
expect_class("guard_zero_errors", module.classify_guard_output(0, compile_ok, "", 0, guard.replace("Errors: 1", "Errors: 0"), "", "SEQ_W", message), False)
expect_class("guard_warning", module.classify_guard_output(0, compile_ok, "", 0, guard.replace("Warnings: 0", "Warnings: 1"), "", "SEQ_W", message), False)
expect_class("guard_alive", module.classify_guard_output(0, compile_ok, "", 0, healthy + guard, "", "SEQ_W", message), False)
expect_class("healthy_with_fatal", module.classify_guard_output(0, compile_ok, "", 0, healthy + guard, "", "HEALTHY", None), False)

mutant_stats = stats.replace("case=unit", "case=mutant_mix").replace("errors=0", "errors=2")
mutant = ("SAMPLE_SCAN_MISMATCH field=mutant_mix_scans expected=0 actual=1\n"
          "SAMPLE_SCAN_MISMATCH field=mutant_mix_valid expected=0 actual=1\n"
          f"{mutant_stats}\n# ** Fatal: tb_sample_scan_capture: case failed\n# Errors: 1, Warnings: 0\n")
required = [("mutant_mix_scans", 0, 1), ("mutant_mix_valid", 0, 1)]
expect_class("mutant_ok", module.classify_mutant_output(0, compile_ok, "", 0, mutant, "", "mutant_mix", required), True, "mutant_rejected")
expect_class("mutant_compile", module.classify_mutant_output(1, compile_ok, "", 0, mutant, "", "mutant_mix", required), False)
expect_class("mutant_missing_numeric", module.classify_mutant_output(0, compile_ok, "", 0, mutant.replace("actual=1", "actual=x", 1), "", "mutant_mix", required), False)
expect_class("mutant_no_failure_fatal", module.classify_mutant_output(0, compile_ok, "", 0, mutant.replace("case failed", "other failure"), "", "mutant_mix", required), False)
expect_class("mutant_pass_marker", module.classify_mutant_output(0, compile_ok, "", 0, "SAMPLE_SCAN_PASS\n" + mutant, "", "mutant_mix", required), False)
expect_class("mutant_guard_fatal", module.classify_mutant_output(0, compile_ok, "", 0, guard + mutant, "", "mutant_mix", required), False)
expect_class("mutant_warning", module.classify_mutant_output(0, compile_ok, "", 0, mutant.replace("Warnings: 0", "Warnings: 1"), "", "mutant_mix", required), False)

expect("select_all_count", len(module.select_cases(["all"], [])), 27)
expect("select_core_count", len(module.select_cases(["core"], [])), 16)
expect("select_guards_count", len(module.select_cases(["guards"], [])), 9)
expect("select_mutants_count", len(module.select_cases(["mutants"], [])), 2)
for label, suites, names in (
    ("select_unknown", ["core"], ["missing"]),
    ("select_duplicate", ["core"], ["directed", "directed"]),
    ("select_wrong_suite", ["core"], ["guard_seq_w_1"]),
):
    checks += 1
    try:
        module.select_cases(suites, names)
    except ValueError:
        pass
    else:
        raise AssertionError(f"{label}: expected ValueError")

good = {"a": {"ok": True}, "b": {"ok": True}}
expect_class("aggregate_ok", module.aggregate_results(["a", "b"], good), True)
expect_class("aggregate_missing", module.aggregate_results(["a", "b", "c"], good), False)
expect_class("aggregate_extra", module.aggregate_results(["a"], good), False)
expect_class("aggregate_failed", module.aggregate_results(["a", "b"], {"a": {"ok": True}, "b": {"ok": False}}), False)
expect_class("aggregate_empty", module.aggregate_results([], {}), False)
expect_class("aggregate_duplicate", module.aggregate_results(["a", "a"], {"a": {"ok": True}}), False)

print(f"RUNNER_HELPER_REVIEW_PASS checks={checks}")