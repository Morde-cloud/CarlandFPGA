"""Assemble NEW82 evidence without modifying RTL, bench, runner, or run artifacts."""
import datetime as dt
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path("D:/pynq/CarlandFPGA")
W = ROOT / ".local/worktrees/deepeye-implementation-20261014"
P = ROOT / ".local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-74"
BOX = P / "safety-worker82"
RED = BOX / "RUN_RED_BASELINE_V3"
GREEN = BOX / "RUN_GREEN_V2"
RESULT = BOX / "RESULT.json"
MANIFEST = BOX / "FILES_SHA256.json"
REQUIREMENTS_SHA256 = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def record(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": sha(raw)}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def require(test, message):
    if not test:
        raise RuntimeError(message)


def commands(run):
    rows = []
    for path in sorted((run / "commands").glob("*.json")):
        if path.name.endswith(".STARTED.json"):
            continue
        item = load(path)
        rows.append({
            "name": path.stem, "argv": item["argv"], "cwd": item["cwd"],
            "exit_code": item["exit_code"], "expected_exit": item["expected_exit"],
            "timeout_seconds": item["timeout_seconds"], "timed_out": item["timed_out"],
            "stdout": item["stdout"], "stderr": item["stderr"],
        })
    return rows


def job_summary(run):
    path = run / "JOB_RESULT.json"
    job = load(path)
    return {
        "record": record(path),
        "exit_code": job.get("exit_code"), "owned_job_error": job.get("owned_job_error"),
        "launcher_exit_confirmed": job.get("launcher_exit_confirmed"),
        "job_attached_before_resume": job.get("job_attached_before_resume"),
        "job_empty_observed_before_close": job.get("job_empty_observed_before_close"),
        "job_terminal_confirmed": job.get("job_terminal_confirmed"),
        "job_terminal_state": job.get("job_terminal_state"), "job_closed": job.get("job_closed"),
        "timed_out": job.get("timed_out"), "job_termination": job.get("job_termination"),
        "job_accounting": job.get("job_accounting"),
    }


def recovery_slice(text):
    start = text.index("    task automatic case_recovery")
    end = text.index("    task automatic case_master_guard", start)
    return text[start:end]


def failed_attempt(name, cause):
    root = BOX / name
    item = {"name": name, "cause": cause, "directory": str(root.resolve()), "preserved": True}
    for filename in ("JOB_RESULT.json", "INNER_FAILURE.json", "OUTER_FAILURE.json",
                     "red/pins.csv", "red/modelsim.log", "green/pins.csv", "green/modelsim.log"):
        path = root / filename
        if path.exists():
            item[filename] = record(path)
    return item


def main():
    require(not RESULT.exists(), "RESULT.json already exists")
    require(not MANIFEST.exists(), "FILES_SHA256.json already exists")
    red_result = load(RED / "RESULT.json")
    green_result = load(GREEN / "RESULT.json")
    require(red_result["status"] == "RED_CONFIRMED_OLD_SOURCE_RECOVERY_BUG", "RED status changed")
    require(green_result["status"] == "GREEN_PASS", "GREEN status changed")
    require(red_result["job_terminal_empty_closed"] is True, "RED Job not terminal")
    require(green_result["job_terminal_empty_closed"] is True, "GREEN Job not terminal")
    require(green_result["source_before"]["dut80.sv"]["sha256"] ==
            green_result["source_after"]["dut80.sv"]["sha256"] ==
            "831429ca560df90fc16ef5fbc7b236d3e82e35071892012ad3c4702981ac1d3d",
            "GREEN DUT source pin mismatch")
    require(green_result["source_after"]["master76.sv"]["sha256"] ==
            "442b0ccd85f0e974b38f6c8e8624e016e724580fe1a56ba09684e78996cb9ccd",
            "master76 changed")

    red_tb = (RED / "source/tb82.sv").read_text(encoding="utf-8")
    green_tb = (GREEN / "source/tb82.sv").read_text(encoding="utf-8")
    red_recovery = recovery_slice(red_tb).encode("utf-8")
    green_recovery = recovery_slice(green_tb).encode("utf-8")
    require(red_recovery == green_recovery, "RED/GREEN recovery control code differs")
    diff = list(difflib.unified_diff(red_tb.splitlines(), green_tb.splitlines(),
                                     fromfile="red-v3", tofile="green-v2", lineterm=""))
    plus = [line for line in diff if line.startswith("+") and not line.startswith("+++")]
    minus = [line for line in diff if line.startswith("-") and not line.startswith("---")]
    require(len(plus) == 1 and len(minus) == 1 and "case_id = 6" in minus[0]
            and "case_id = 7" in plus[0], "unexpected RED/GREEN testbench difference")

    deliverables = {
        "rtl80_current": record(W / "competition/deepeye/fpga/diagnostic/r04_gain80/deepeye_mcp6s21_safety_arbiter_candidate.sv"),
        "readme80_unchanged": record(W / "competition/deepeye/fpga/diagnostic/r04_gain80/README.md"),
        "vectors80_unexecuted_unchanged": record(W / "competition/deepeye/fpga/diagnostic/r04_gain80/vectors_UNEXECUTED.json"),
        "tb82": record(W / "competition/deepeye/fpga/diagnostic/r04_gain82/tb_r04_gain82.sv"),
        "runner82": record(W / "competition/deepeye/tools/diagnostic/r04_gain82/run_r04_gain82.py"),
        "summary82": record(Path(__file__).resolve()),
        "master76_readonly": record(W / "competition/deepeye/fpga/diagnostic/r04_gain76/deepeye_mcp6s21_write_candidate.sv"),
        "started82": record(BOX / "STARTED.json"),
        "main_review82": record(P / "SAFETY82_MAIN_REVIEW.json"),
        "immutable_scope_pinned": record(P / "immutable_scope_pinned.json"),
    }
    archive = {
        "rtl80_original": record(P / "safety82-original80/deepeye_mcp6s21_safety_arbiter_candidate.sv"),
        "readme80_original": record(P / "safety82-original80/README.md"),
        "vectors80_original": record(P / "safety82-original80/vectors_UNEXECUTED.json"),
    }
    evidence = {
        "red_v3_result": record(RED / "RESULT.json"),
        "red_v3_source_before": record(RED / "SOURCE_BEFORE.json"),
        "red_v3_pins": record(RED / "red/pins.csv"),
        "red_v3_modelsim_log": record(RED / "red/modelsim.log"),
        "red_v3_compile_stdout": record(RED / "commands/compile.stdout.bin"),
        "red_v3_vsim_stdout": record(RED / "commands/red-vsim.stdout.bin"),
        "green_v2_result": record(GREEN / "RESULT.json"),
        "green_v2_source_before": record(GREEN / "SOURCE_BEFORE.json"),
        "green_v2_pins": record(GREEN / "green/pins.csv"),
        "green_v2_modelsim_log": record(GREEN / "green/modelsim.log"),
        "green_v2_compile_stdout": record(GREEN / "commands/compile.stdout.bin"),
        "green_v2_vsim_stdout": record(GREEN / "commands/green-vsim.stdout.bin"),
    }
    failures = [
        failed_attempt("RUN_RED_BASELINE_V1",
                       "Before compile/sim: local vlib has no -version support and returns usage exit 1; preserved harness failure."),
        failed_attempt("RUN_RED_BASELINE_V2",
                       "Compile/sim reached, but bench waited host_ready before presenting a nonzero host tag; no RED oracle result."),
        failed_attempt("RUN_GREEN_V1",
                       "All 438 bench assertions passed, but output-labeled tag_faults with duplicate case id 6; runner classification rejected the duplicate label."),
    ]
    tool_banners = {}
    for name in ("vlog-version", "vsim-version", "vmap-version", "vlib-version-probe"):
        tool_banners[name] = (GREEN / "commands" / (name + ".stdout.bin")).read_text(
            encoding="utf-8", errors="replace").strip()
    result = {
        "schema": "deepeye-r04-gain82-final-result/v1",
        "status": "FOCUSED_DIGITAL_GREEN_PASS_PENDING_MAIN_INDEPENDENT_REVIEW",
        "task_id": "DEEPEYE-IMPLEMENTATION-20261014", "task_version": 1,
        "work_id": "B-R04-OVERRANGE-FUNCTIONAL-20261030-82",
        "thread_id": "01a18ce6-e447-7ba0-80be-09e9a58e4278",
        "job_id": "child-7c042de9d616469488cde6de0542f950", "instance_id": "deepseek-b-83",
        "main_thread_id": "01a18824-4172-74e2-a13f-f3e3d1e3ed99",
        "ownership": [
            ".local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-74/safety-worker82",
            "competition/deepeye/fpga/diagnostic/r04_gain80",
            "competition/deepeye/fpga/diagnostic/r04_gain82",
            "competition/deepeye/tools/diagnostic/r04_gain82",
        ],
        "prior_source_work": "B-R04-LOCAL-OVERRANGE-SOURCE-20261030-80",
        "requirements_sha256": REQUIREMENTS_SHA256,
        "requirements_verified": [f"H{number:02d}" for number in range(1, 16)],
        "contract_revision": 1, "contract_pin": "f5989cd5defce561f9ba98e6b18fc2682945f0a2",
        "tested_commit": None,
        "source_identity": "Exact local source snapshots only; Git HEAD was not used as evidence and no Git action was performed.",
        "selected_repair": {
            "file": "competition/deepeye/fpga/diagnostic/r04_gain80/deepeye_mcp6s21_safety_arbiter_candidate.sv",
            "line": 68,
            "before": "assign arm_fire = arm_rise && !armed_q && arm_space_ok;",
            "after": "assign arm_fire = arm_rise && (!armed_q || inhibit_q) && arm_space_ok;",
            "only_change_relative_to_original80": True,
            "arm_space_ok_unchanged": True, "tag_changed_policy_unchanged": True,
        },
        "source_hashes": {
            "before_original80": "e5a6fb00fcd3ac8ae4c2f2fb2a9793b2f35ea7b780ad3c7645d2be93ba52a036",
            "after_fixed80": "831429ca560df90fc16ef5fbc7b236d3e82e35071892012ad3c4702981ac1d3d",
            "master76_readonly": "442b0ccd85f0e974b38f6c8e8624e016e724580fe1a56ba09684e78996cb9ccd",
            "tb82_red_v3": red_result["source_before"]["tb82.sv"]["sha256"],
            "tb82_green_v2": green_result["source_before"]["tb82.sv"]["sha256"],
            "runner82": green_result["source_before"]["runner.py"]["sha256"],
        },
        "source_control_equivalence": {
            "recovery_task_identical_red_green": True,
            "recovery_task_bytes": len(red_recovery),
            "recovery_task_sha256": sha(red_recovery),
            "full_tb_diff_plus_lines": len(plus), "full_tb_diff_minus_lines": len(minus),
            "full_tb_diff_explanation": "Only tag_faults case_id logging changed 6->7 after baseline; the executed recovery control is byte-identical.",
            "diff": diff,
        },
        "baseline_red": {
            "run": str(RED.resolve()), "status": red_result["status"],
            "vsim_deliberate_exit": red_result["inner"]["vsim_exit"],
            "compile_zero_errors_warnings": red_result["inner"]["compile_zero_errors_warnings"],
            "markers": red_result["inner"]["markers"], "job": job_summary(RED),
            "commands": commands(RED),
        },
        "green": {
            "run": str(GREEN.resolve()), "status": green_result["status"],
            "vsim_exit": green_result["inner"]["vsim_exit"],
            "compile_zero_errors_warnings": green_result["inner"]["compile_zero_errors_warnings"],
            "markers": green_result["inner"]["markers"], "job": job_summary(GREEN),
            "commands": commands(GREEN), "tool_binary_sha256": green_result["inner"]["tool_binary_sha256"],
            "tool_banners": tool_banners,
            "checks": 438, "cycles": 44656, "starts": 14, "frames": 14,
        },
        "failed_attempts": failures,
        "repairs_used": [
            "Record vlib -version as unsupported usage probe with expected exit 1.",
            "Bench drives host tag/gain before waiting host_ready.",
            "Bench assigns unique tag_faults case id 7 (logging only).",
        ],
        "acceptance_evidence": {
            "actual_76_master_instantiated_no_stub": True,
            "external_observation_only_spi_cs_sck_si_and_public_results": True,
            "normal_words_observed_4004_4002_4001_fallback_4000": True,
            "host_result_backpressure_did_not_block_one_shot_gain0": True,
            "sustained_overrange_no_repeated_fallback": True,
            "release_no_auto_arm": True,
            "explicit_rising_arm_requires_both_slots_drained_overrange0_master_idle": True,
            "post_arm_host_valid0_observation_required": True,
            "old_held_host_valid_not_replayed": True,
            "active_host_cancel_keeps_original_tag_error_then_one_fallback": True,
            "fallback_cancel_or_disable_no_retry": True,
            "same_cycle_overrange_blocks_host_handshake": True,
            "zero_colliding_changed_tag_sticky_fault_blocks_spi": True,
            "reset_destroys_result_context_without_ack": True,
            "job_terminal_empty_closed_red_and_green": True,
            "bounded_each_command_25s_whole_job_150s_output_below_8mib": True,
        },
        "manual_corner_reasoning": {
            "arm_recovery": "Original RED left armed_q=1 and inhibit_q=1 after fallback and drains, so !armed_q blocked the explicit pulse. The selected fix permits only a rising arm when either unarmed or inhibited; every arm_space_ok guard still applies.",
            "cancel_disable": "cancel or enable=0 drives master cancel, clears armed/fallback_pending and host gate, returns a digital abort/error for an active original tag, and never retries automatically.",
            "fallback_with_held_host_slot": "fallback_choose does not depend on host_result_valid_q; the host slot is preserved, the safety slot is independent, and fallback_pending clears when the single safety command fires.",
            "colliding_or_changed_tags": "zero/equal host tag is not eligible, changed reserved tag while armed raises sticky identity fault, and no success payload is synthesized.",
            "same_cycle_overrange": "host_ready is combinationally false while overrange is high, so no host handshake is recorded; inhibit latches at the next edge.",
            "reset": "reset destroys master and wrapper slots/context, drives safe SPI pins and produces no post-reset ACK. Host must retain persistent UNKNOWN, especially for an aborted partial frame.",
        },
        "digital_meaning": {
            "error0": "16-edge digital frame completed; not proof of CS/register/RESULT, settling, analog gain, ADC effect, or safety.",
            "error1": "digital command refused/aborted or ended in error; a partial 16-edge abort may already have affected analog state, whose value remains UNKNOWN.",
        },
        "blocker": {
            "reserved_safety_tag": "No production reserved tag was assigned. Test tag 0x99 is synthetic only; zero/collision must fault. Production integration remains disabled and unarmed.",
            "physical_adc_and_overrange": "The overrange source/calibration/threshold/electrical provenance are not provided; only a candidate external-flag seam was tested.",
        },
        "not_run": [
            "natural master-result wrong-tag mismatch; it was not forced and is not evidenced",
            "physical ADC, calibration, threshold, overrange provenance, fake-ADC rejection on hardware",
            "analog gain, settling, 8-level sweep, 5 percent accuracy, ADC readback, register/RESULT effect",
            "R04, full H12, all-29-card acceptance, final 1 percent / 100 ms target",
            "100 MHz timing closure or clock constraints; 100 MHz remains an engineering assumption",
            "pinout, clocksetter, electrical level shifting, board, SSH, synthesis, implementation, bitstream",
            "old r04_gain78 suite replay, Git operations, services, SQL, queues, credentials, collector repin, Root planner",
        ],
        "unavailable_or_unaccepted": {
            "physical_adc": "unavailable", "overrange_provenance": "external flag absent",
            "analog_gain_actual": "unknown", "R04": "NOT_PASSED", "full_H12": "NOT_PASSED",
            "all_29": "NOT_PASSED", "100MHz_timing": "not established", "board": "not_run; A only",
        },
        "source80_unexecuted_vectors": "The original vectors_UNEXECUTED.json remains byte-identical and unexecuted as metadata; it is not a PASS. NEW82 execution evidence is separate.",
        "deliverables": deliverables, "original80_archive": archive, "evidence": evidence,
        "operator_actions_required": [], "desktop_round_required": [], "human_action_required": [],
        "main_action": "Independent review and acceptance remain main-owned; no group report was sent.",
        "completed_at_utc": utc(),
    }
    write_json(RESULT, result)

    manifest_files = []
    for path in sorted(BOX.rglob("*")):
        if path.is_file() and path.resolve() != MANIFEST.resolve():
            manifest_files.append(record(path))
    manifest = {
        "schema": "deepeye-r04-gain82-file-manifest/v1", "generated_at_utc": utc(),
        "root": str(BOX.resolve()), "excludes_itself": str(MANIFEST.resolve()),
        "file_count": len(manifest_files), "files": manifest_files,
    }
    write_json(MANIFEST, manifest)
    print(json.dumps({"result": record(RESULT), "manifest": record(MANIFEST),
                      "manifest_files": len(manifest_files)}, indent=2))


if __name__ == "__main__":
    main()
