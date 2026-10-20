#!/usr/bin/env python3
"""Run and qualify the author-side first-capture-deadline tests.

The runner is intentionally self-contained: it snapshots exact sources, records
tool versions and argv, executes ModelSim with hidden subprocesses, and applies
a strict line protocol. It rejects missing/duplicate/conflicting completion,
unrelated fatal/error lines, pseudo prefixes, unexpected exits and timeouts.

It does not import any main oracle, main vector, main testbench or old private
evidence. The author testbench has its own independent reference model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


RUN_RE = re.compile(r"^DEEPEYE_FC_RUN width=(\d+) kind=(standalone|composition|guard)$")
SCENARIO_RE = re.compile(
    r"^DEEPEYE_FC_SCENARIO id=([A-Za-z0-9_.:-]+) width=(\d+) "
    r"group=([a-z_]+) budget=(\d+) obs=(\d+) checks=(\d+) status=(pass|fail)$"
)
SUMMARY_RE = re.compile(
    r"^DEEPEYE_FC_SUMMARY width=(\d+) kind=(standalone|composition) "
    r"scenarios=(\d+) checks=(\d+) failures=(\d+) groups=([a-z_]+:\d+(?:,[a-z_]+:\d+)*)$"
)
FINISH_RE = re.compile(r"^DEEPEYE_FC_FINISH width=(\d+) status=(PASS|FAIL)$")
CHECK_FAIL_RE = re.compile(r"^DEEPEYE_FC_CHECK_FAIL ")
GUARD_PARAM_RE = re.compile(
    r"^DEEPEYE_FIRST_CAPTURE_INVALID_PARAM BUDGET_W=(-?\d+) SAFE_BUDGET_W=(-?\d+)$"
)
GUARD_FATAL_RE = re.compile(
    r"^(?:\*\*\s*Fatal:\s*)?DEEPEYE_FIRST_CAPTURE_INVALID_PARAM unsupported width$"
)
GUARD_ALIVE_RE = re.compile(r"^DEEPEYE_FC_GUARD_UNEXPECTED_ALIVE width=(\d+)$")

SMALL_GROUPS = {
    "obs", "cancel", "reset", "restart", "priority",
    "held", "terminal", "latch", "random",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_budget_width(width: int) -> int:
    if width < 1:
        return 1
    if width > 32:
        return 32
    return width


def max_budget_for_width(width: int) -> int:
    if width >= 32:
        return (1 << 32) - 1
    return (1 << width) - 1


def normalize_line(raw: str) -> str:
    line = raw.rstrip("\r\n")
    if line.startswith("# "):
        line = line[2:]
    return line


def iter_normalized(text: str):
    for raw in text.split("\n"):
        yield raw, normalize_line(raw)


def run_process(argv, cwd: Path, log_path: Path, timeout: float) -> dict:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    record = {
        "argv": [str(x) for x in argv],
        "cwd": str(cwd),
        "log": str(log_path),
        "started_utc": started,
        "timeout_seconds": timeout,
    }
    try:
        with log_path.open("wb") as log_file:
            proc = subprocess.Popen(
                [str(x) for x in argv],
                cwd=str(cwd),
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
            try:
                rc = proc.wait(timeout=timeout)
                timed_out = False
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                rc = None
                timed_out = True
    except OSError as exc:
        record.update({
            "ended_utc": utc_now(),
            "exit_code": None,
            "timed_out": False,
            "spawn_error": str(exc),
        })
        return record
    record.update({
        "ended_utc": utc_now(),
        "exit_code": rc,
        "timed_out": timed_out,
        "log_sha256": sha256_file(log_path) if log_path.exists() else None,
    })
    return record


def parse_groups(text: str) -> dict:
    groups = {}
    for item in text.split(","):
        name, count_text = item.split(":", 1)
        if name in groups:
            raise ValueError(f"duplicate group {name}")
        count = int(count_text)
        if count < 0:
            raise ValueError(f"negative group count {name}")
        groups[name] = count
    return groups


def parse_normal_log(text: str, width: int, kind: str, expected_groups: set) -> tuple[bool, dict, list[str]]:
    reasons = []
    phase = 0
    for _, line in iter_normalized(text):
        if RUN_RE.fullmatch(line):
            if phase != 0: reasons.append("RUN order")
            phase = 1
        elif SCENARIO_RE.fullmatch(line):
            if phase != 1: reasons.append("SCENARIO order")
        elif SUMMARY_RE.fullmatch(line):
            if phase != 1: reasons.append("SUMMARY order")
            phase = 2
        elif FINISH_RE.fullmatch(line):
            if phase != 2: reasons.append("FINISH order")
            phase = 3
    if type(width) is not int or not 1 <= width <= 32:
        reasons.append("unsupported normal width")
    runs = []
    summaries = []
    finishes = []
    scenarios = []
    check_fails = []
    malformed = []
    unrelated_errors = []

    for raw, line in iter_normalized(text):
        m = RUN_RE.match(line)
        if m:
            runs.append((int(m.group(1)), m.group(2)))
            continue
        m = SCENARIO_RE.match(line)
        if m:
            scenarios.append({
                "id": m.group(1), "width": int(m.group(2)), "group": m.group(3),
                "budget": int(m.group(4)), "obs": int(m.group(5)),
                "checks": int(m.group(6)), "status": m.group(7), "raw": raw,
            })
            continue
        m = SUMMARY_RE.match(line)
        if m:
            summaries.append({
                "width": int(m.group(1)), "kind": m.group(2),
                "scenarios": int(m.group(3)), "checks": int(m.group(4)),
                "failures": int(m.group(5)), "groups_text": m.group(6), "raw": raw,
            })
            continue
        m = FINISH_RE.match(line)
        if m:
            finishes.append((int(m.group(1)), m.group(2), raw))
            continue
        if CHECK_FAIL_RE.match(line):
            check_fails.append(line)
            continue
        if "DEEPEYE_FC_" in line:
            malformed.append(line)
        if re.search(r"(?i)\*\*\s*(error|fatal)\b", line):
            unrelated_errors.append(line)
        elif re.search(r"(?i)\b(fatal|error)\b", line) and not re.match(r"^Errors:\s*0\b", line):
            unrelated_errors.append(line)

    if len(runs) != 1:
        reasons.append(f"expected exactly one RUN, found {len(runs)}")
    elif runs[0] != (width, kind):
        reasons.append(f"RUN mismatch {runs[0]} expected {(width, kind)}")
    if len(summaries) != 1:
        reasons.append(f"expected exactly one SUMMARY, found {len(summaries)}")
    if len(finishes) != 1:
        reasons.append(f"expected exactly one FINISH, found {len(finishes)}")
    if check_fails:
        reasons.append(f"CHECK_FAIL present {len(check_fails)}")
    if malformed:
        reasons.append(f"malformed FC marker {len(malformed)}")
    if unrelated_errors:
        reasons.append(f"unrelated fatal/error {len(unrelated_errors)}")
    if finishes:
        fw, status, _ = finishes[0]
        if fw != width:
            reasons.append(f"FINISH width {fw} expected {width}")
        if status != "PASS":
            reasons.append(f"FINISH status {status}")

    scenario_ids = set()
    actual_group_counts = {}
    actual_check_sum = 0
    max_budget = max_budget_for_width(width)
    for s in scenarios:
        if s["id"] in scenario_ids:
            reasons.append(f"duplicate scenario id {s['id']}")
        scenario_ids.add(s["id"])
        if s["width"] != width:
            reasons.append(f"scenario {s['id']} width {s['width']} expected {width}")
        if s["group"] not in expected_groups:
            reasons.append(f"scenario {s['id']} group {s['group']} unexpected")
        if s["budget"] < 0 or s["budget"] > max_budget:
            reasons.append(f"scenario {s['id']} budget {s['budget']} out of range")
        if s["checks"] <= 0:
            reasons.append(f"scenario {s['id']} checks not positive")
        if s["status"] != "pass":
            reasons.append(f"scenario {s['id']} status {s['status']}")
        actual_group_counts[s["group"]] = actual_group_counts.get(s["group"], 0) + 1
        actual_check_sum += s["checks"]

    if summaries:
        summary = summaries[0]
        if summary["width"] != width:
            reasons.append(f"SUMMARY width {summary['width']} expected {width}")
        if summary["kind"] != kind:
            reasons.append(f"SUMMARY kind {summary['kind']} expected {kind}")
        try:
            summary_groups = parse_groups(summary["groups_text"])
        except ValueError as exc:
            summary_groups = {}
            reasons.append(f"SUMMARY groups malformed: {exc}")
        if set(summary_groups) != expected_groups:
            reasons.append(f"SUMMARY group set {sorted(summary_groups)} expected {sorted(expected_groups)}")
        if not scenarios or any(actual_group_counts.get(g, 0) <= 0 for g in expected_groups):
            reasons.append("required group must contain a scenario")
        if summary["checks"] <= 0:
            reasons.append("SUMMARY checks must be positive")
        if sum(summary_groups.values()) != summary["scenarios"]:
            reasons.append("SUMMARY group counts do not sum to scenarios")
        for group, count in summary_groups.items():
            if actual_group_counts.get(group, 0) != count:
                reasons.append(
                    f"SUMMARY group {group} count {count} actual {actual_group_counts.get(group, 0)}"
                )
        if summary["scenarios"] != len(scenarios):
            reasons.append(f"SUMMARY scenarios {summary['scenarios']} actual {len(scenarios)}")
        if summary["checks"] != actual_check_sum:
            reasons.append(f"SUMMARY checks {summary['checks']} actual {actual_check_sum}")
        if summary["failures"] != 0:
            reasons.append(f"SUMMARY failures {summary['failures']}")

    result = {
        "kind": kind,
        "width": width,
        "runs": len(runs),
        "summaries": len(summaries),
        "finishes": len(finishes),
        "scenarios": len(scenarios),
        "checks": actual_check_sum,
        "failures": 0 if not summaries else summaries[0]["failures"],
        "groups": actual_group_counts,
        "check_fail_lines": len(check_fails),
        "reasons": reasons,
    }
    return (len(reasons) == 0), result, reasons


def parse_guard_log(text: str, width: int) -> tuple[bool, dict, list[str]]:
    reasons = []
    if width not in (0, 33):
        reasons.append(f"guard width {width} is not an unsupported width 0/33")
    order = []
    for _, line in iter_normalized(text):
        if RUN_RE.fullmatch(line): order.append("run")
        elif GUARD_PARAM_RE.fullmatch(line): order.append("param")
        elif GUARD_FATAL_RE.fullmatch(line): order.append("fatal")
        elif "DEEPEYE_" in line: reasons.append("malformed guard protocol")
    if order != ["run", "param", "fatal"]:
        reasons.append("guard RUN/diagnostic/fatal order")
    safe_width = safe_budget_width(width)
    runs = []
    params = []
    fatals = []
    alive = []
    summaries = []
    finishes = []
    errors = []

    for raw, line in iter_normalized(text):
        m = RUN_RE.match(line)
        if m:
            runs.append((int(m.group(1)), m.group(2)))
            continue
        m = GUARD_PARAM_RE.match(line)
        if m:
            params.append((int(m.group(1)), int(m.group(2)), raw))
            continue
        if GUARD_FATAL_RE.match(line):
            fatals.append(line)
            continue
        m = GUARD_ALIVE_RE.match(line)
        if m:
            alive.append(int(m.group(1)))
            continue
        m = SUMMARY_RE.match(line)
        if m:
            summaries.append(line)
            continue
        m = FINISH_RE.match(line)
        if m:
            finishes.append(line)
            continue
        if re.search(r"(?i)\*\*\s*(error|fatal)\b", line):
            errors.append(line)

    if len(runs) != 1:
        reasons.append(f"guard expected one RUN, found {len(runs)}")
    elif runs[0] != (width, "guard"):
        reasons.append(f"guard RUN mismatch {runs[0]}")
    if len(params) != 1:
        reasons.append(f"guard expected one diagnostic, found {len(params)}")
    elif params[0][:2] != (width, safe_width):
        reasons.append(f"guard diagnostic values {params[0][:2]} expected {(width, safe_width)}")
    if len(fatals) != 1:
        reasons.append(f"guard expected one fatal text, found {len(fatals)}")
    if alive:
        reasons.append("guard reached unexpected live state")
    if summaries:
        reasons.append("guard produced SUMMARY")
    if finishes:
        reasons.append("guard produced FINISH")
    if errors:
        reasons.append(f"guard unexpected fatal/error lines {len(errors)}")

    result = {
        "kind": "guard",
        "width": width,
        "safe_width": safe_width,
        "params": [p[:2] for p in params],
        "fatals": len(fatals),
        "reasons": reasons,
    }
    return (len(reasons) == 0), result, reasons


def qualify_normal_log(
    text: str,
    width: int,
    kind: str,
    expected_groups: set,
    exit_code,
    timed_out: bool = False,
) -> tuple[bool, dict, list[str]]:
    ok, parsed, reasons = parse_normal_log(text, width, kind, expected_groups)
    reasons = list(reasons)
    if timed_out:
        reasons.append("simulation timeout")
    if type(exit_code) is not int or exit_code != 0:
        reasons.append(f"simulation exit {exit_code} expected 0")
    return (ok and not reasons), parsed, reasons


def qualify_guard_log(
    text: str,
    width: int,
    exit_code,
    timed_out: bool = False,
) -> tuple[bool, dict, list[str]]:
    ok, parsed, reasons = parse_guard_log(text, width)
    reasons = list(reasons)
    if timed_out:
        reasons.append("simulation timeout")
    if type(exit_code) is not int or exit_code != 0:
        reasons.append(f"guard exit {exit_code} expected 0 for ModelSim $fatal")
    return (ok and not reasons), parsed, reasons


def qualify_mutant_log(
    text: str,
    width: int,
    exit_code,
    timed_out: bool = False,
) -> tuple[bool, dict, list[str]]:
    ok, parsed, reasons = parse_mutant_log(text, width)
    reasons = list(reasons)
    if timed_out:
        reasons.append("mutant simulation timeout")
    if type(exit_code) is not int or exit_code != 0:
        reasons.append(f"mutant simulation exit {exit_code} unexpected")
    return (ok and not reasons), parsed, reasons


def parse_mutant_log(text: str, width: int) -> tuple[bool, dict, list[str]]:
    """Qualify complete numeric behavioral failures, never load failures or X."""
    reasons = []
    cleaned = []
    counts = {}
    finished_ids = set()
    failure_count = 0
    summaries = []
    fatals = []
    phase = 0
    fail_re = re.compile(
        r"DEEPEYE_FC_CHECK_FAIL width=([0-9]+) scenario=([A-Za-z0-9_.:-]+) "
        r"phase=post (?:(waiting|completed|expired|invalid_request|started_event|"
        r"completed_event|expired_event|invalid_request_event) dut=([01]) ref=([01])"
        r"|state-not-onehot-or-zero count=([2-4]))"
    )
    fatal_re = re.compile(
        r"\*\* Fatal: DEEPEYE_FC_BEHAVIOR_FAIL width=([0-9]+) failures=([0-9]+)"
    )
    for _, line in iter_normalized(text):
        run = RUN_RE.fullmatch(line)
        fail = fail_re.fullmatch(line)
        scenario = SCENARIO_RE.fullmatch(line)
        summary = SUMMARY_RE.fullmatch(line)
        finish = FINISH_RE.fullmatch(line)
        fatal = fatal_re.fullmatch(line)
        if run:
            if phase != 0:
                reasons.append("mutant RUN order")
            phase = 1
            cleaned.append(line)
        elif fail:
            fw, sid, signal, actual, reference, count = fail.groups()
            if phase != 1 or int(fw) != width or sid in finished_ids:
                reasons.append("CHECK_FAIL width/scenario/order")
            if signal is not None and actual == reference:
                reasons.append("CHECK_FAIL has no numeric mismatch")
            counts[sid] = counts.get(sid, 0) + 1
            failure_count += 1
        elif scenario:
            sid, sw, group, budget, obs, checks, status = scenario.groups()
            if (status == "fail") != (counts.get(sid, 0) > 0):
                reasons.append("scenario status disagrees with CHECK_FAIL")
            if counts.get(sid, 0) > int(checks):
                reasons.append("scenario failure count exceeds checks")
            finished_ids.add(sid)
            cleaned.append(line.removesuffix("fail") + "pass" if status == "fail" else line)
        elif summary:
            if phase != 1:
                reasons.append("mutant SUMMARY order")
            phase = 2
            summaries.append(int(summary.group(5)))
            cleaned.append(re.sub(r"failures=[0-9]+", "failures=0", line))
        elif finish:
            if phase != 2 or finish.group(2) != "FAIL":
                reasons.append("mutant FINISH order/status")
            phase = 3
            cleaned.append(line.removesuffix("FAIL") + "PASS")
        elif fatal:
            if phase != 3:
                reasons.append("mutant fatal order")
            phase = 4
            fatals.append((int(fatal.group(1)), int(fatal.group(2))))
        elif re.fullmatch(r"Errors: 1, Warnings: [0-9]+", line):
            # ModelSim includes the one own-fatal in its diagnostic tally.
            cleaned.append(line.replace("Errors: 1,", "Errors: 0,", 1))
        else:
            cleaned.append(line)
    if not failure_count:
        reasons.append("mutant produced no valid numeric CHECK_FAIL")
    if set(counts) - finished_ids:
        reasons.append("CHECK_FAIL has no completed scenario")
    if summaries != [failure_count] or fatals != [(width, failure_count)] or phase != 4:
        reasons.append("mutant requires one matching SUMMARY/FINISH/own-fatal")
    ok, parsed, normal_reasons = parse_normal_log(
        "\n".join(cleaned), width, "standalone", SMALL_GROUPS
    )
    reasons.extend(normal_reasons)
    result = {"kind": "mutant", "width": width, "check_fail_lines": failure_count,
              "summaries": len(summaries), "fatals": len(fatals),
              "scenarios": parsed["scenarios"], "reasons": reasons}
    return (ok and not reasons), result, reasons



def source_manifest(source_root: Path) -> list[dict]:
    rels = [
        "competition/deepeye/fpga/control3d/deepeye_first_capture_deadline.sv",
        "competition/deepeye/fpga/control3d/deepeye_atomic_pwm.sv",
        "competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv",
        "competition/deepeye/fpga/control3d/deepeye_pwm_applied_capture.sv",
        "competition/deepeye/tests/control/tb_first_capture_deadline.sv",
        "competition/deepeye/tools/control3d/run_first_capture_deadline.py",
        "competition/deepeye/tests/control/test_first_capture_deadline_runner.py",
        "competition/deepeye/fpga/control3d/first_capture_deadline_candidate.md",
    ]
    result = []
    for rel in rels:
        path = source_root / rel
        result.append({
            "relative": rel,
            "path": str(path),
            "exists": path.exists(),
            "sha256": sha256_file(path) if path.exists() else None,
            "size": path.stat().st_size if path.exists() else None,
        })
    return result


def snapshot_sources(source_root: Path, snapshot_dir: Path, manifest: list[dict]) -> list[dict]:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for entry in manifest:
        path = Path(entry["path"])
        if not path.exists():
            copied.append({**entry, "snapshot": None})
            continue
        target = snapshot_dir / path.name
        if target.exists():
            target = snapshot_dir / (path.stem + "-" + entry["sha256"][:12] + path.suffix)
        shutil.copy2(path, target)
        copied.append({
            **entry,
            "snapshot": str(target),
            "snapshot_sha256": sha256_file(target),
        })
    return copied


def capture_versions(modelsim_dir: Path, run_root: Path) -> dict:
    version_dir = run_root / "versions"
    version_dir.mkdir(parents=True, exist_ok=True)
    records = {}
    commands = {
        "vlog": [modelsim_dir / "vlog.exe", "-version"],
        "vsim": [modelsim_dir / "vsim.exe", "-version"],
        "python": [Path(sys.executable), "--version"],
    }
    for name, argv in commands.items():
        record = run_process(argv, version_dir, version_dir / f"{name}-version.log", 60)
        text = (version_dir / f"{name}-version.log").read_text(encoding="utf-8", errors="replace")
        record["text"] = text.strip()
        records[name] = record
    (run_root / "versions.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return records


def compile_case(case_dir: Path, modelsim_dir: Path, sources: list[Path], timeout: float) -> dict:
    work = case_dir / "work"
    work.mkdir(parents=True, exist_ok=False)
    vlib = run_process([modelsim_dir / "vlib.exe", "work"], work, case_dir / "vlib.log", timeout)
    if vlib.get("exit_code") != 0 or vlib.get("timed_out"):
        return {"ok": False, "vlib": vlib, "vlog": None, "reason": "vlib failed"}
    argv = [modelsim_dir / "vlog.exe", "-sv", "-work", "work"] + [str(p) for p in sources]
    vlog = run_process(argv, work, case_dir / "compile.log", timeout)
    log_text = (case_dir / "compile.log").read_text(encoding="utf-8", errors="replace")
    compile_error = bool(re.search(r"(?im)^\s*(?:#\s*)?\*\*\s*Error:", log_text))
    ok = (not vlog["timed_out"] and vlog["exit_code"] == 0 and not compile_error)
    return {
        "ok": ok,
        "vlib": vlib,
        "vlog": vlog,
        "compile_error": compile_error,
        "reason": None if ok else "compile failed",
    }


def run_vsim_case(
    case_dir: Path,
    modelsim_dir: Path,
    top: str,
    generic: str,
    value: int,
    timeout: float,
) -> dict:
    work = case_dir / "work"
    argv = [
        modelsim_dir / "vsim.exe",
        "-c",
        "-quiet",
        "-wlf", str(case_dir / "sim.wlf"),
        f"-g{generic}={value}",
        top,
        "-do", "run -all; quit -f",
    ]
    return run_process(argv, work, case_dir / "sim.log", timeout)


def write_case_record(case_dir: Path, record: dict) -> None:
    (case_dir / "case.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def run_one_case(
    case_root: Path,
    case_id: str,
    source_root: Path,
    modelsim_dir: Path,
    top: str,
    generic: str,
    value: int,
    kind: str,
    expected_groups: set | None,
    timeout: float,
    extra_sources: list[Path] | None = None,
) -> dict:
    case_dir = case_root / case_id
    case_dir.mkdir(parents=True, exist_ok=False)
    dut = source_root / "competition/deepeye/fpga/control3d/deepeye_first_capture_deadline.sv"
    tb = source_root / "competition/deepeye/tests/control/tb_first_capture_deadline.sv"
    sources = [dut, tb] + (extra_sources or [])
    compile_record = compile_case(case_dir, modelsim_dir, sources, timeout)
    record = {
        "case_id": case_id,
        "kind": kind,
        "top": top,
        "generic": generic,
        "generic_value": value,
        "compile": compile_record,
        "sim": None,
        "parse": None,
        "ok": False,
    }
    if not compile_record["ok"]:
        record["reasons"] = [compile_record["reason"]]
        write_case_record(case_dir, record)
        return record

    sim = run_vsim_case(case_dir, modelsim_dir, top, generic, value, timeout)
    record["sim"] = sim
    sim_text = (case_dir / "sim.log").read_text(encoding="utf-8", errors="replace")
    if sim["timed_out"]:
        record["reasons"] = ["simulation timeout"]
    elif kind == "guard":
        ok, parsed, reasons = qualify_guard_log(sim_text, value, sim["exit_code"], sim["timed_out"])
        record["parse"] = parsed
        record["reasons"] = reasons
        record["ok"] = bool(ok)
    else:
        ok, parsed, reasons = qualify_normal_log(
            sim_text, value, kind, expected_groups or set(), sim["exit_code"], sim["timed_out"]
        )
        record["parse"] = parsed
        record["reasons"] = reasons
        record["ok"] = bool(ok)
    write_case_record(case_dir, record)
    return record


def normal_cases(
    source_root: Path,
    modelsim_dir: Path,
    run_root: Path,
    timeout: float,
    only: set | None = None,
) -> list[dict]:
    old = [
        source_root / "competition/deepeye/fpga/control3d/deepeye_atomic_pwm.sv",
        source_root / "competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv",
        source_root / "competition/deepeye/fpga/control3d/deepeye_pwm_applied_capture.sv",
    ]
    specs = []
    for width in range(1, 6):
        specs.append((f"standalone-w{width:02d}", "tb_first_capture_deadline", "BUDGET_W", width, "standalone", SMALL_GROUPS, None))
    specs.append(("standalone-w32-prefix", "tb_first_capture_deadline", "BUDGET_W", 32, "standalone", {"prefix"}, None))
    specs.append(("composition", "tb_first_capture_deadline_composition", "DUT_BUDGET_W", 4, "composition", {"trace"}, old))
    specs.append(("guard-w00", "tb_first_capture_deadline_guard", "BUDGET_W", 0, "guard", None, None))
    specs.append(("guard-w33", "tb_first_capture_deadline_guard", "BUDGET_W", 33, "guard", None, None))
    records = []
    for case_id, top, generic, value, kind, groups, extra in specs:
        if only and case_id not in only:
            continue
        record = run_one_case(
            run_root, case_id, source_root, modelsim_dir, top, generic, value,
            kind, groups, timeout, extra,
        )
        records.append(record)
        print(f"{case_id}: {'PASS' if record['ok'] else 'FAIL'} {record.get('reasons', [])}")
    return records


MUTANT_SPECS = {
    "deadline-off-by-one": {
        "replace": [
            ("remaining_q       <= budget_cycles - 1'b1;",
             "remaining_q       <= budget_cycles;"),
        ],
    },
    "repeat-start-renewal": {
        "regex": (
            r"if \(start\) begin\n\s*// WAIT_DUPLICATE_START_REJECT.*?end else if \(observed\) begin",
            "if (start) begin\n"
            "                // WAIT_DUPLICATE_START_REJECT (mutant: renew)\n"
            "                waiting_q <= 1'b1;\n"
            "                invalid_request_q <= 1'b0;\n"
            "                remaining_q <= budget_cycles - 1'b1;\n"
            "            end else if (observed) begin",
        ),
    },
    "cancel-ignored": {
        "replace": [
            ("if (rst || cancel) begin", "if (rst) begin"),
        ],
    },
    "late-observed-resurrection": {
        "replace": [
            ("// RETAIN_TERMINAL_STATE\n",
             "// RETAIN_TERMINAL_STATE\n"
             "                if (observed) begin\n"
             "                    completed_q <= 1'b1;\n"
             "                    completed_event_q <= 1'b1;\n"
             "                end\n"),
        ],
    },
}


def make_mutant(source_text: str, spec: dict) -> str:
    text = source_text
    for old, new in spec.get("replace", []):
        count = text.count(old)
        if count != 1:
            raise ValueError(f"mutation anchor count {count} for {old!r}")
        text = text.replace(old, new, 1)
    if "regex" in spec:
        pattern, replacement = spec["regex"]
        text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
        if count != 1:
            raise ValueError(f"mutation regex count {count}")
    return text


def mutant_cases(source_root: Path, modelsim_dir: Path, run_root: Path, timeout: float) -> list[dict]:
    source_path = source_root / "competition/deepeye/fpga/control3d/deepeye_first_capture_deadline.sv"
    source_text = source_path.read_text(encoding="utf-8")
    tb = source_root / "competition/deepeye/tests/control/tb_first_capture_deadline.sv"
    results = []
    for name, spec in MUTANT_SPECS.items():
        mutant_root = run_root / name
        mutant_root.mkdir(parents=True, exist_ok=False)
        mutant_path = mutant_root / "dut_mutant.sv"
        try:
            mutant_text = make_mutant(source_text, spec)
        except ValueError as exc:
            results.append({"mutant": name, "ok": False, "reasons": [str(exc)]})
            print(f"{name}: FAIL {exc}")
            continue
        mutant_path.write_text(mutant_text, encoding="utf-8")
        mutant_records = []
        for width in (1, 2, 3):
            case_dir = mutant_root / f"w{width:02d}"
            case_dir.mkdir(parents=True, exist_ok=False)
            compile_record = compile_case(case_dir, modelsim_dir, [mutant_path, tb], timeout)
            record = {
                "mutant": name,
                "width": width,
                "compile": compile_record,
                "sim": None,
                "parse": None,
                "ok": False,
            }
            if not compile_record["ok"]:
                record["reasons"] = ["mutant compile failed; not a target hit"]
            else:
                sim = run_vsim_case(case_dir, modelsim_dir, "tb_first_capture_deadline", "BUDGET_W", width, timeout)
                record["sim"] = sim
                sim_text = (case_dir / "sim.log").read_text(encoding="utf-8", errors="replace")
                if sim["timed_out"]:
                    record["reasons"] = ["mutant simulation timeout"]
                else:
                    ok, parsed, reasons = qualify_mutant_log(
                        sim_text, width, sim["exit_code"], sim["timed_out"]
                    )
                    record["parse"] = parsed
                    record["reasons"] = reasons
                    record["ok"] = bool(ok)
            write_case_record(case_dir, record)
            mutant_records.append(record)
        hit = any(r["ok"] for r in mutant_records)
        compile_ok = all(r["compile"]["ok"] for r in mutant_records)
        results.append({
            "mutant": name,
            "ok": bool(hit and compile_ok),
            "hit_widths": [r["width"] for r in mutant_records if r["ok"]],
            "records": mutant_records,
            "reasons": [] if (hit and compile_ok) else ["mutant not behaviorally rejected"],
        })
        print(f"{name}: {'REJECTED' if hit and compile_ok else 'FAIL'} widths={[r['width'] for r in mutant_records if r['ok']]}")
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("normal", "mutants", "all"), default="all")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--source-root", default=str(Path(__file__).resolve().parents[4]))
    parser.add_argument("--modelsim-dir", default=r"D:/modelsim1/win64")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args(argv)
    allowed = {f"standalone-w{w:02d}" for w in range(1, 6)}
    allowed |= {"standalone-w32-prefix", "composition", "guard-w00", "guard-w33"}
    if args.only is not None and (
        not args.only or len(set(args.only)) != len(args.only)
        or not set(args.only) <= allowed or args.mode == "mutants"
    ):
        parser.error("--only requires unique known normal case IDs")
    import math
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be finite and positive")

    source_root = Path(args.source_root).resolve()
    modelsim_dir = Path(args.modelsim_dir).resolve()
    run_root = Path(args.run_root).resolve()
    if run_root.exists():
        parser.error(f"run root already exists: {run_root}")
    run_root.mkdir(parents=True)

    for exe in ("vlib.exe", "vlog.exe", "vsim.exe"):
        if not (modelsim_dir / exe).exists():
            parser.error(f"missing ModelSim executable: {modelsim_dir / exe}")

    started = utc_now()
    manifest = source_manifest(source_root)
    snapshots = snapshot_sources(source_root, run_root / "sources", manifest)
    execution_root = run_root / "execution-inputs"
    for entry in snapshots:
        if not entry["snapshot"]:
            parser.error(f"missing input {entry['relative']}")
        content = Path(entry["snapshot"]).read_bytes()
        if sha256_bytes(content) != entry["sha256"]:
            parser.error(f"input changed during snapshot {entry['relative']}")
        target = execution_root / entry["relative"]
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as f:
            f.write(content)
    versions = capture_versions(modelsim_dir, run_root)
    run_manifest = {
        "operation": "B-DEEPEYE-FIRST-CAPTURE-DEADLINE-20261021-18",
        "work_id": "B-FIRST-CAPTURE-DEADLINE-RTL-20261021-18-v1",
        "source_root": str(source_root),
        "run_root": str(run_root),
        "started_utc": started,
        "sources": snapshots,
        "versions": versions,
        "normal": [],
        "mutants": [],
    }
    (run_root / "RUN_MANIFEST.json").write_text(
        json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    ok = True
    if args.mode in ("normal", "all"):
        normal_records = normal_cases(
            execution_root, modelsim_dir, run_root, args.timeout,
            set(args.only) if args.only else None,
        )
        run_manifest["normal"] = normal_records
        ok = ok and all(r["ok"] for r in normal_records)
    if args.mode in ("mutants", "all"):
        mutant_records = mutant_cases(execution_root, modelsim_dir, run_root / "mutants", args.timeout)
        run_manifest["mutants"] = mutant_records
        ok = ok and all(r["ok"] for r in mutant_records)

    run_manifest["ended_utc"] = utc_now()
    run_manifest["ok"] = bool(ok)
    (run_root / "RUN_MANIFEST.json").write_text(
        json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"RUNNER {'PASS' if ok else 'FAIL'} root={run_root}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
