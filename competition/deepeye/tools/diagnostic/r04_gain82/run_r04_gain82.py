"""NEW82 bounded R04 safety-wrapper controls; no board, analog, or R04 claim."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path("D:/pynq/CarlandFPGA")
W = ROOT / ".local/worktrees/deepeye-implementation-20261014"
P = ROOT / ".local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-74"
TOOLS = Path("D:/modelsim1/win64")
ARCHIVE = P / "safety82-original80"
OUTPUT_LIMIT = 8 * 1024 * 1024
COMMAND_LIMIT = 25
JOB_LIMIT = 150
TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
WORK_ID = "B-R04-OVERRANGE-FUNCTIONAL-20261030-82"
REQUIREMENTS_SHA256 = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
MASTER_SHA256 = "442b0ccd85f0e974b38f6c8e8624e016e724580fe1a56ba09684e78996cb9ccd"
ORIGINAL_RTL_SHA256 = "e5a6fb00fcd3ac8ae4c2f2fb2a9793b2f35ea7b780ad3c7645d2be93ba52a036"
ORIGINAL_README_SHA256 = "659278585ccff5e344c29d872f53de2da384ec5f0ef67e7a2177e0064aea8e23"
ORIGINAL_VECTORS_SHA256 = "189382107db6e5aa451021780a29ba58c77f11f8f909e2b7408b68c50c415668"
OWNED_PROCESS_SHA256 = "1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692"
WINDOWS_JOB_SHA256 = "3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3"
OLD_LINE = b"    assign arm_fire = arm_rise && !armed_q && arm_space_ok;\n"
NEW_LINE = b"    assign arm_fire = arm_rise && (!armed_q || inhibit_q) && arm_space_ok;\n"


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def record(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": digest_bytes(raw)}


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def require(test, message):
    if not test:
        raise RuntimeError(message)


def output_bytes(out):
    return sum(path.stat().st_size for path in Path(out).rglob("*") if path.is_file())


def source_specs():
    return {
        "dut80.sv": W / "competition/deepeye/fpga/diagnostic/r04_gain80/deepeye_mcp6s21_safety_arbiter_candidate.sv",
        "master76.sv": W / "competition/deepeye/fpga/diagnostic/r04_gain76/deepeye_mcp6s21_write_candidate.sv",
        "tb82.sv": W / "competition/deepeye/fpga/diagnostic/r04_gain82/tb_r04_gain82.sv",
        "README80.md": W / "competition/deepeye/fpga/diagnostic/r04_gain80/README.md",
        "vectors80_UNEXECUTED.json": W / "competition/deepeye/fpga/diagnostic/r04_gain80/vectors_UNEXECUTED.json",
        "runner.py": Path(__file__).resolve(),
        "owned_process.py": W / "competition/deepeye/tools/diagnostic/g05_capture/build/owned_process.py",
        "windows_job.py": W / "fpga_mesh/windows_job.py",
        "immutable_scope_pinned.json": P / "immutable_scope_pinned.json",
        "SAFETY82_MAIN_REVIEW.json": P / "SAFETY82_MAIN_REVIEW.json",
    }


def verify_contract(path):
    raw = Path(path).read_bytes()
    value = json.loads(raw.decode("utf-8"))
    ids = [item["id"] for item in value["requirements"]]
    expected_ids = [f"H{number:02d}" for number in range(1, 16)]
    require(ids == expected_ids, "pinned H01-H15 IDs changed")
    canonical = json.dumps(value["requirements"], ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    actual = digest_bytes(canonical)
    require(actual == REQUIREMENTS_SHA256, "fixed requirements SHA256 mismatch")
    return {"requirements_sha256": actual, "requirements_ids": ids,
            "contract_id": value.get("contract_id"), "revision": value.get("revision")}


def verify_source(phase):
    paths = source_specs()
    archive_rtl = (ARCHIVE / "deepeye_mcp6s21_safety_arbiter_candidate.sv").read_bytes()
    archive_readme = (ARCHIVE / "README.md").read_bytes()
    archive_vectors = (ARCHIVE / "vectors_UNEXECUTED.json").read_bytes()
    require(digest_bytes(archive_rtl) == ORIGINAL_RTL_SHA256, "original80 RTL archive changed")
    require(digest_bytes(archive_readme) == ORIGINAL_README_SHA256, "original80 README archive changed")
    require(digest_bytes(archive_vectors) == ORIGINAL_VECTORS_SHA256, "original80 vectors archive changed")
    require(archive_rtl.count(OLD_LINE) == 1, "original80 arm_fire line missing or ambiguous")
    expected_repaired = archive_rtl.replace(OLD_LINE, NEW_LINE)
    current = paths["dut80.sv"].read_bytes()
    require((paths["README80.md"]).read_bytes() == archive_readme, "README80 changed without authorization")
    require((paths["vectors80_UNEXECUTED.json"]).read_bytes() == archive_vectors,
            "vectors80 changed without authorization")
    require((paths["master76.sv"]).read_bytes() and digest_bytes(paths["master76.sv"].read_bytes()) == MASTER_SHA256,
            "readonly master76 hash changed")
    if phase == "red":
        require(digest_bytes(current) == ORIGINAL_RTL_SHA256 and current == archive_rtl,
                "RED requires exact original80 source")
        relation = "exact_original80_archive"
    else:
        require(current == expected_repaired and digest_bytes(current) != ORIGINAL_RTL_SHA256,
                "GREEN requires only the selected arm_fire line repair")
        relation = "original80_archive_plus_only_arm_fire_inhibit_guard"
    return {
        "phase_relation": relation,
        "archive_rtl": record(ARCHIVE / "deepeye_mcp6s21_safety_arbiter_candidate.sv"),
        "expected_repaired_sha256": digest_bytes(expected_repaired),
        "only_authorized_rtl_line_changed": current == expected_repaired,
    }


def snapshot(out, phase):
    out.mkdir(parents=True, exist_ok=False)
    relation = verify_source(phase)
    snap = out / "source"
    snap.mkdir()
    pins = {}
    specs = source_specs()
    for name, path in specs.items():
        raw = path.read_bytes()
        (snap / name).write_bytes(raw)
        pins[name] = {"original": str(path.resolve()), "snapshot": str((snap / name).resolve()),
                      "bytes": len(raw), "sha256": digest_bytes(raw)}
    require(pins["master76.sv"]["sha256"] == MASTER_SHA256, "master76 snapshot mismatch")
    require(pins["owned_process.py"]["sha256"] == OWNED_PROCESS_SHA256, "owned_process helper hash mismatch")
    require(pins["windows_job.py"]["sha256"] == WINDOWS_JOB_SHA256, "windows_job helper hash mismatch")
    contract = verify_contract(snap / "immutable_scope_pinned.json")
    references = {
        "r04_gain78_runner_read_only": record(W / "competition/deepeye/tools/diagnostic/r04_gain78/run_focused.py"),
        "r04_gain78_tb_read_only": record(W / "competition/deepeye/fpga/diagnostic/r04_gain78/tb_r04_gain78.sv"),
    }
    return snap, pins, relation, contract, references


def tool_pins():
    return {name: record(TOOLS / (name + ".exe")) for name in ("vmap", "vlib", "vlog", "vsim")}


def command(out_root, command_dir, name, argv, cwd, expected_exit):
    argv = [str(value) for value in argv]
    cwd = Path(cwd)
    row = {"argv": argv, "cwd": str(cwd), "expected_exit": expected_exit,
           "timeout_seconds": COMMAND_LIMIT, "started_at_utc": utc()}
    started = time.monotonic()
    timed_out = False
    output_exceeded = False
    with (command_dir / (name + ".stdout.bin")).open("xb") as stdout, \
            (command_dir / (name + ".stderr.bin")).open("xb") as stderr:
        process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=stdout,
                                   stderr=stderr, shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
        row["pid"] = process.pid
        row["started_at_utc"] = utc()
        write_json(command_dir / (name + ".STARTED.json"), row)
        while process.poll() is None:
            if time.monotonic() - started >= COMMAND_LIMIT:
                timed_out = True
                process.kill()
            if output_bytes(out_root) >= OUTPUT_LIMIT:
                output_exceeded = True
                process.kill()
            time.sleep(0.02)
        row["exit_code"] = process.poll()
        row["elapsed_seconds"] = time.monotonic() - started
        row["timed_out"] = timed_out
        row["output_limit_exceeded"] = output_exceeded
        row["completed_at_utc"] = utc()
    row["stdout"] = record(command_dir / (name + ".stdout.bin"))
    row["stderr"] = record(command_dir / (name + ".stderr.bin"))
    write_json(command_dir / (name + ".json"), row)
    require(not timed_out, f"native command timeout: {name}")
    require(not output_exceeded, f"native command output limit: {name}")
    require(row["exit_code"] == expected_exit, f"native exit mismatch: {name} {row['exit_code']}")
    return row


def combined_text(command_dir, name):
    values = []
    for suffix in ("stdout.bin", "stderr.bin"):
        values.append((command_dir / (name + "." + suffix)).read_text(encoding="utf-8", errors="replace"))
    return "\n".join(values)


def marker_checks(phase, transcript, pins_text):
    all_text = transcript + "\n" + pins_text
    require("FAIL," not in pins_text, "bench failure marker present")
    require("** Fatal:" not in all_text, "fatal simulator marker present")
    if phase == "red":
        checks = {
            "red_confirmed": "RED_CONFIRMED" in pins_text and "R04_NEW82_RED_CONFIRMED" in transcript,
            "host_word_4004": re.search(r"(?m)^WORD,1,\d+,4004$", pins_text) is not None,
            "fallback_word_4000": re.search(r"(?m)^WORD,1,\d+,4000$", pins_text) is not None,
            "host_tag_0x11": re.search(r"(?m)^HOST_RESULT,1,\d+,0,17$", pins_text) is not None,
            "safety_tag_0x99": re.search(r"(?m)^SAFETY_RESULT,1,\d+,0,153$", pins_text) is not None,
            "no_green_claim": "GREEN_DONE" not in pins_text and "R04_NEW82_GREEN_PASS" not in transcript,
        }
    else:
        checks = {
            "green_done": "GREEN_DONE" in pins_text and "R04_NEW82_GREEN_PASS" in transcript,
            "all_eight_cases": all(pins_text.count(f"CASE_BEGIN,{case_id},") == 1 and
                                   pins_text.count(f"CASE_END,{case_id},") == 1
                                   for case_id in range(1, 9)),
            "host_word_4004": re.search(r"(?m)^WORD,\d+,\d+,4004$", pins_text) is not None,
            "host_word_4002": re.search(r"(?m)^WORD,\d+,\d+,4002$", pins_text) is not None,
            "host_word_4001": re.search(r"(?m)^WORD,\d+,\d+,4001$", pins_text) is not None,
            "fallback_word_4000": re.search(r"(?m)^WORD,\d+,\d+,4000$", pins_text) is not None,
            "host_tag_0x11": re.search(r"(?m)^HOST_RESULT,\d+,\d+,0,17$", pins_text) is not None,
            "host_tag_0x21": re.search(r"(?m)^HOST_RESULT,\d+,\d+,0,33$", pins_text) is not None,
            "host_tag_0x31": re.search(r"(?m)^HOST_RESULT,\d+,\d+,0,49$", pins_text) is not None,
            "host_abort_0x22": re.search(r"(?m)^HOST_RESULT,\d+,\d+,1,34$", pins_text) is not None,
            "safety_tag_0x99": re.search(r"(?m)^SAFETY_RESULT,\d+,\d+,0,153$", pins_text) is not None,
            "safety_abort_0x99": re.search(r"(?m)^SAFETY_RESULT,\d+,\d+,1,153$", pins_text) is not None,
            "no_red_claim": "RED_CONFIRMED" not in pins_text,
        }
    bad = [name for name, okay in checks.items() if not okay]
    require(not bad, "marker checks failed: " + ",".join(bad))
    return checks


def run_inner(out, phase):
    snap = out / "source"
    sim = out / "sim"
    commands = out / "commands"
    sim.mkdir(exist_ok=False)
    commands.mkdir(exist_ok=False)
    pins_before = {name: record(snap / name) for name in source_specs()}
    rows = []
    for tool in ("vlog", "vsim", "vmap"):
        rows.append(command(out, commands, tool + "-version", [TOOLS / (tool + ".exe"), "-version"], sim, 0))
    rows.append(command(out, commands, "vlib-version-probe", [TOOLS / "vlib.exe", "-version"], sim, 1))
    rows.append(command(out, commands, "vmap", [TOOLS / "vmap.exe", "-c"], sim, 0))
    rows.append(command(out, commands, "vlib", [TOOLS / "vlib.exe", "work"], sim, 0))
    rows.append(command(out, commands, "compile", [TOOLS / "vlog.exe", "-sv", "-work", "work",
        snap / "master76.sv", snap / "dut80.sv", snap / "tb82.sv"], sim, 0))
    compile_text = combined_text(commands, "compile")
    require("Errors: 0, Warnings: 0" in compile_text and "** Warning:" not in compile_text,
            "compile did not report zero errors and zero warnings")

    run_dir = out / ("red" if phase == "red" else "green")
    run_dir.mkdir()
    dofile = run_dir / "run.do"
    dofile.write_text("onerror {quit -code 3 -force}\n"
                      "onbreak {\n"
                      "if {[examine -radix decimal /tb_r04_gain82/completion_status] == 1} {quit -code 0 -force}\n"
                      "quit -code 4 -force\n"
                      "}\n"
                      "run -all\n"
                      "quit -code 4 -force\n", encoding="utf-8", newline="\n")
    sim_argv = [TOOLS / "vsim.exe", "-c", "-voptargs=+acc", "-onfinish", "stop",
                "-l", run_dir / "modelsim.log", "work.tb_r04_gain82",
                "+OUT=" + (run_dir / "pins.csv").as_posix()]
    if phase == "red":
        sim_argv.append("+RED=1")
    sim_argv.extend(["-do", "do " + dofile.as_posix()])
    expected = 4 if phase == "red" else 0
    sim_row = command(out, commands, phase + "-vsim", sim_argv, sim, expected)
    transcript = combined_text(commands, phase + "-vsim")
    if (run_dir / "modelsim.log").exists():
        transcript += "\n" + (run_dir / "modelsim.log").read_text(encoding="utf-8", errors="replace")
    pins_text = (run_dir / "pins.csv").read_text(encoding="utf-8", errors="replace")
    markers = marker_checks(phase, transcript, pins_text)
    pins_after = {name: record(snap / name) for name in source_specs()}
    require(pins_before == pins_after, "executed snapshot source changed during run")
    result = {
        "status": "RED_CONFIRMED_OLD_SOURCE_RECOVERY_BUG" if phase == "red" else "GREEN_PASS",
        "phase": phase, "oracle_nonzero": phase == "red", "vsim_exit": sim_row["exit_code"],
        "compile_zero_errors_warnings": True, "markers": markers,
        "source_snapshot_before": pins_before, "source_snapshot_after": pins_after,
        "tool_binary_sha256": tool_pins(), "commands": rows,
        "vlib_version_note": "vlib has no -version support; usage probe exit 1 preserved; binary hash and ModelSim 10.7 family banners recorded",
        "pins": str((run_dir / "pins.csv").resolve()),
        "modelsim_log": str((run_dir / "modelsim.log").resolve()),
        "not_analog": True, "r04_status": "NOT_PASSED",
    }
    write_json(out / "INNER_RESULT.json", result)
    print(json.dumps({"phase": phase, "status": result["status"], "vsim_exit": sim_row["exit_code"]}))
    return 2 if phase == "red" else 0


def job_terminal(job):
    return bool(job.get("job_attached_before_resume") is True
                and job.get("launcher_exit_confirmed") is True
                and job.get("job_empty_observed_before_close") is True
                and job.get("job_terminal_confirmed") is True
                and job.get("job_terminal_state") == "confirmed"
                and job.get("job_closed") is True
                and not job.get("timed_out")
                and not job.get("process_error")
                and not job.get("job_query_failed")
                and not job.get("job_termination_failed")
                and not job.get("job_close_error"))


def run_outer(out, phase):
    snap, pins_before, relation, contract, references = snapshot(out, phase)
    invocation = {"argv": [str(value) for value in sys.argv], "cwd": str(Path.cwd()),
                  "python": sys.version, "started_at_utc": utc(), "phase": phase,
                  "job_limit_seconds": JOB_LIMIT, "command_limit_seconds": COMMAND_LIMIT,
                  "output_limit_bytes": OUTPUT_LIMIT}
    write_json(out / "INVOCATION.json", invocation)
    write_json(out / "SOURCE_BEFORE.json", {
        "schema": "deepeye-r04-gain82-source-pins/v1", "phase": phase,
        "candidate_relation": relation, "contract": contract, "files": pins_before,
        "readonly_template_references": references,
        "tool_binaries": tool_pins(),
    })
    spec = importlib.util.spec_from_file_location("r04_gain82_owned", snap / "owned_process.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    job_dir = out / "job"
    job_dir.mkdir()
    argv = [str(sys.executable), "-B", str(snap / "runner.py"), "--phase", phase,
            "--inner", "--out", str(out)]
    job = module.run_owned(argv, job_dir, JOB_LIMIT, snap / "windows_job.py",
                           job_drain_seconds=5, job_terminate_seconds=5)
    write_json(out / "JOB_RESULT.json", job)
    require(job_terminal(job), "whole owned Job did not reach terminal-empty-closed")
    after = {}
    specs = source_specs()
    for name, path in specs.items():
        after[name] = record(path)
    require(all(after[name]["sha256"] == pins_before[name]["sha256"] for name in specs),
            "source changed across measured run")
    require(all(record(snap / name)["sha256"] == after[name]["sha256"] for name in specs),
            "snapshot differs from post-run source")
    inner_path = out / "INNER_RESULT.json"
    require(inner_path.exists(), "inner result missing")
    inner = json.loads(inner_path.read_text(encoding="utf-8"))
    if phase == "red":
        require(job.get("exit_code") == 2 and job.get("owned_job_error") == "launcher_nonzero_exit",
                "RED launcher did not preserve deliberate nonzero")
        require(inner.get("status") == "RED_CONFIRMED_OLD_SOURCE_RECOVERY_BUG",
                "RED status mismatch")
    else:
        module.require_owned_success(job)
        require(job.get("exit_code") == 0 and job.get("owned_job_error") is None,
                "GREEN launcher did not complete naturally")
        require(inner.get("status") == "GREEN_PASS", "GREEN status mismatch")
    after_relation = verify_source(phase)
    result = {
        "schema": "deepeye-r04-gain82-focused-result/v1",
        "task_id": TASK_ID, "task_version": TASK_VERSION, "work_id": WORK_ID,
        "thread_id": "01a18ce6-e447-7ba0-80be-09e9a58e4278",
        "job_id": "child-7c042de9d616469488cde6de0542f950",
        "instance_id": "deepseek-b-83", "requirements_sha256": REQUIREMENTS_SHA256,
        "contract": contract, "phase": phase, "inner": inner, "job": job,
        "job_terminal_empty_closed": job_terminal(job),
        "source_before": pins_before, "source_after": after,
        "source_relation_before": relation, "source_relation_after": after_relation,
        "source_changed_during_run": False,
        "status": "RED_CONFIRMED_OLD_SOURCE_RECOVERY_BUG" if phase == "red" else "GREEN_PASS",
        "execution_kind": "SYNTHETIC_DIGITAL_SEAM_WITH_ACTUAL_76_MASTER",
        "physical_adc": "unavailable", "overrange_provenance": "external flag absent",
        "analog_gain": "unknown", "r04": "NOT_PASSED", "full_h12": "NOT_PASSED",
        "all_29": "NOT_PASSED", "clock_100mhz": "engineering assumption only",
        "board": "not_run; A only", "git": "not_run; main owns",
        "not_run": ["natural master-result wrong-tag path without forcing internals",
                    "physical ADC/calibration/threshold and overrange provenance",
                    "analog gain/register/RESULT/settling effect",
                    "synthesis/place/route/timing/pins/clock constraints/board"],
        "completed_at_utc": utc(), "output_bytes_before_result": output_bytes(out),
    }
    require(result["output_bytes_before_result"] < OUTPUT_LIMIT - 65536,
            "bounded output lacks RESULT headroom")
    write_json(out / "RESULT.json", result)
    require(output_bytes(out) <= OUTPUT_LIMIT, "final evidence exceeds 8 MiB")
    print(json.dumps({"status": result["status"], "job_terminal": job_terminal(job),
                      "result": str((out / "RESULT.json").resolve())}))
    return 20 if phase == "red" else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("red", "green"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--inner", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    try:
        if args.inner:
            return run_inner(out, args.phase)
        return run_outer(out, args.phase)
    except Exception:
        error = traceback.format_exc()
        print(error, file=sys.stderr)
        if out.exists() and not (out / "INNER_FAILURE.json").exists() and args.inner:
            try:
                write_json(out / "INNER_FAILURE.json", {"at_utc": utc(), "phase": args.phase,
                                                       "error": error})
            except Exception:
                pass
        elif out.exists() and not (out / "RESULT.json").exists():
            try:
                write_json(out / "OUTER_FAILURE.json", {"at_utc": utc(), "phase": args.phase,
                                                        "error": error})
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
