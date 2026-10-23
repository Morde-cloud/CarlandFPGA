#!/usr/bin/env python3
"""Strict fail-closed ModelSim runner for deepeye_uart_tx.

Work: B-UART-TX-20261023-24-v1
Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Operation: B-DEEPEYE-UART-TX-20261023-24

Each invocation creates a new attempt directory below the author evidence
root.  ModelSim runs with that attempt directory as its cwd and with TEMP/TMP
inside the same author evidence tree.  Source snapshots, exact argv/cwd,
process exits, timeout state and separate raw stdout/stderr bytes are retained.

Ordinary suites require one exact begin row, one exact summary row, one exact
end row, an exact ordered case list, matching per-case check totals, zero
ModelSim errors/warnings, and the expected final counters.  The only permitted
nonzero-error run is each guard suite's own exact time-zero fatal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

OPERATION_ID = "B-DEEPEYE-UART-TX-20261023-24"
TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
WORK_ID = "B-UART-TX-20261023-24-v1"
MODEL = "deepseek-flash"
REASONING_EFFORT = "max"
BASE_HEAD = "f49e30d2cf9a82b1a8f7963768ad3520f68dbd47"
FROZEN_DESIGN = "1011259415a0916054eb580687612580bc1e5f09"
CONTRACT_ID = "DEEPEYE-HUMAN-LOCK-20261014/revision1"
CONTRACT_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
EXPECTED_REQUIREMENTS_SHA256 = (
    "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
)

PRODUCT_ROOT = Path(__file__).resolve().parents[4]
EVIDENCE_ROOT = (
    PRODUCT_ROOT
    / "competition/deepeye/evidence/transport/uart-tx-20261023-24/author"
)
CONTRACT_REL = Path("docs/competition/deepeye-2026/immutable_scope.json")
TOOL_DIR_DEFAULT = Path(r"D:\modelsim1\win64")

AUTHOR_FILES = {
    "rtl": Path("competition/deepeye/fpga/transport/deepeye_uart_tx.sv"),
    "tb": Path("competition/deepeye/tests/rtl/transport/tb_uart_tx.sv"),
    "runner": Path("competition/deepeye/tools/transport/run_uart_tx.py"),
    "candidate": Path("competition/deepeye/fpga/transport/uart_tx_candidate.md"),
}
COMPILE_FILES = ["rtl", "tb"]

ALL_CASES = ["reset_idle", "long_idle", "all_byte_values", "busy_perturbation"]
CANCEL_CASES = [
    "reset_idle",
    "cancel_each_phase",
    "reset_each_phase",
    "cancel_idle",
    "reset_over_cancel",
    "two_aborts",
]

SUITES = {
    "ratio97_11": {
        "kind": "ordinary",
        "top": "tb_uart_tx_ratio_97_11",
        "cases": ALL_CASES,
        "min_checks": 20000,
        "final": {"accepted": 257, "completed": 257, "aborted": 0},
    },
    "ratio31_3": {
        "kind": "ordinary",
        "top": "tb_uart_tx_ratio_31_3",
        "cases": ALL_CASES,
        "min_checks": 24000,
        "final": {"accepted": 257, "completed": 257, "aborted": 0},
    },
    "min_ratio2_1": {
        "kind": "ordinary",
        "top": "tb_uart_tx_min_ratio",
        "cases": ALL_CASES,
        "min_checks": 4500,
        "final": {"accepted": 257, "completed": 257, "aborted": 0},
    },
    "cancel_reset": {
        "kind": "ordinary",
        "top": "tb_uart_tx_cancel_reset",
        "cases": CANCEL_CASES,
        "min_checks": 2500,
        "final": {"accepted": 3, "completed": 1, "aborted": 2},
    },
    "sustained": {
        "kind": "ordinary",
        "top": "tb_uart_tx_sustained",
        "cases": ["reset_idle", "sustained_offer"],
        "min_checks": 5000,
        "final": {"accepted": 64, "completed": 64, "aborted": 0},
    },
    "default_9600": {
        "kind": "ordinary",
        "top": "tb_uart_tx_default_9600",
        "cases": ["reset_idle", "default_frame"],
        "min_checks": 80,
        "final": {"accepted": 3, "completed": 3, "aborted": 0},
    },
    "baud300": {
        "kind": "ordinary",
        "top": "tb_uart_tx_baud_300",
        "cases": ["reset_idle", "baud300_frame"],
        "min_checks": 60,
        "final": {"accepted": 2, "completed": 2, "aborted": 0},
    },
    "baud1200": {
        "kind": "ordinary",
        "top": "tb_uart_tx_baud_1200",
        "cases": ["reset_idle", "baud1200_frame"],
        "min_checks": 80,
        "final": {"accepted": 3, "completed": 3, "aborted": 0},
    },
    "stat_w2": {
        "kind": "ordinary",
        "top": "tb_uart_tx_stat_w2",
        "cases": ["reset_idle", "stat_saturation"],
        "min_checks": 500,
        "final": {"accepted": 3, "completed": 3, "aborted": 3},
    },
    "guard_clock": {
        "kind": "guard",
        "top": "tb_uart_tx_guard",
        "defines": {"G_CLOCK": "-1", "G_BAUD": "0", "G_STAT_W": "1"},
        "fatal": "deepeye_uart_tx: CLOCK_HZ out of range",
    },
    "guard_baud_low": {
        "kind": "guard",
        "top": "tb_uart_tx_guard",
        "defines": {"G_CLOCK": "97", "G_BAUD": "0", "G_STAT_W": "1"},
        "fatal": "deepeye_uart_tx: BAUD out of range",
    },
    "guard_baud_high": {
        "kind": "guard",
        "top": "tb_uart_tx_guard",
        "defines": {"G_CLOCK": "2", "G_BAUD": "2", "G_STAT_W": "32"},
        "fatal": "deepeye_uart_tx: BAUD out of range",
    },
    "guard_stat_low": {
        "kind": "guard",
        "top": "tb_uart_tx_guard",
        "defines": {"G_CLOCK": "97", "G_BAUD": "11", "G_STAT_W": "1"},
        "fatal": "deepeye_uart_tx: STAT_W out of range",
    },
    "guard_stat_high": {
        "kind": "guard",
        "top": "tb_uart_tx_guard",
        "defines": {"G_CLOCK": "97", "G_BAUD": "11", "G_STAT_W": "33"},
        "fatal": "deepeye_uart_tx: STAT_W out of range",
    },
}

TALLY_RE = re.compile(
    r"^[ \t]*(?:#[ \t]*)?Errors:[ \t]*(\d+),[ \t]*Warnings:[ \t]*(\d+)[ \t\r]*$",
    re.MULTILINE,
)
DIAGNOSTIC_RE = re.compile(r"^\*\*[ \t]+(?:Error|Warning|Fatal)\b")
FATAL_RE = re.compile(r"^\*\*[ \t]+Fatal:[ \t]*(.*?)[ \t]*$")
TB_BEGIN_RE = re.compile(r"^TB_BEGIN[ \t]+tb=([A-Za-z0-9_]+)$")
TB_END_RE = re.compile(r"^TB_END[ \t]+(pass|fail)$")
TB_SUMMARY_RE = re.compile(
    r"^TB_SUMMARY[ \t]+cases=(\d+)[ \t]+pass=(\d+)[ \t]+fail=(\d+)"
    r"[ \t]+checks=(\d+)$"
)
CASE_BEGIN_RE = re.compile(r"^CASE_BEGIN[ \t]+name=([A-Za-z0-9_]+)$")
CASE_END_RE = re.compile(
    r"^CASE_END[ \t]+name=([A-Za-z0-9_]+)[ \t]+status=(pass|fail)"
    r"[ \t]+checks=(\d+)$"
)
TB_STAT_RE = re.compile(r"^TB_STAT[ \t]+(accepted|completed|aborted)=(\d+)$")


class SetupError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))
        handle.write("\n")


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def decode_raw(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def combined_text(step_dir: Path) -> str:
    return (
        decode_raw(read_bytes(step_dir / "stdout.bin"))
        + "\n"
        + decode_raw(read_bytes(step_dir / "stderr.bin"))
    )


def add_check(checks: list[dict], name: str, passed: bool, detail: str = "") -> bool:
    checks.append({"name": name, "pass": bool(passed), "detail": detail})
    return bool(passed)


def checks_pass(checks: list[dict], start: int = 0) -> bool:
    return all(item["pass"] for item in checks[start:])


def normalize_row(raw: str) -> str:
    text = raw.strip()
    if text.startswith("#"):
        text = text[1:].strip()
    return text


def run_process(argv: list[str], cwd: Path, step_dir: Path, timeout_s: int) -> dict:
    step_dir.mkdir(parents=False, exist_ok=False)
    temp_dir = step_dir / "tmp"
    temp_dir.mkdir()
    pycache_dir = temp_dir / "pycache"
    env = os.environ.copy()
    env["TEMP"] = str(temp_dir.resolve())
    env["TMP"] = str(temp_dir.resolve())
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(pycache_dir.resolve())

    started_at = utc_now()
    write_json(
        step_dir / "command.json",
        {
            "argv": argv,
            "cwd": str(cwd.resolve()),
            "timeout_s": timeout_s,
            "started_at": started_at,
            "environment": {
                "TEMP": env["TEMP"],
                "TMP": env["TMP"],
                "PYTHONDONTWRITEBYTECODE": env["PYTHONDONTWRITEBYTECODE"],
                "PYTHONPYCACHEPREFIX": env["PYTHONPYCACHEPREFIX"],
            },
        },
    )

    stdout_path = step_dir / "stdout.bin"
    stderr_path = step_dir / "stderr.bin"
    start = time.monotonic()
    returncode = None
    timed_out = False
    spawn_error = None
    with stdout_path.open("xb") as stdout_handle, stderr_path.open("xb") as stderr_handle:
        try:
            process = subprocess.Popen(
                argv,
                cwd=str(cwd),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            spawn_error = f"{type(exc).__name__}: {exc}"
        else:
            try:
                returncode = process.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                try:
                    returncode = process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    returncode = None

    duration_s = round(time.monotonic() - start, 3)
    record = {
        "argv": argv,
        "cwd": str(cwd.resolve()),
        "timeout_s": timeout_s,
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_s": duration_s,
        "timed_out": timed_out,
        "returncode": returncode,
        "spawn_error": spawn_error,
        "stdout": str(stdout_path.resolve()),
        "stderr": str(stderr_path.resolve()),
        "stdout_bytes": stdout_path.stat().st_size,
        "stderr_bytes": stderr_path.stat().st_size,
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
    }
    write_json(step_dir / "process.json", record)
    return record


def classify_process(record: dict, checks: list[dict], prefix: str) -> None:
    add_check(checks, f"{prefix}-spawn", record["spawn_error"] is None, str(record["spawn_error"]))
    add_check(checks, f"{prefix}-timeout", not record["timed_out"], "")
    add_check(checks, f"{prefix}-exit", record["returncode"] == 0, f"returncode={record['returncode']}")


def tally_values(text: str) -> list[tuple[int, int]]:
    return [(int(error), int(warning)) for error, warning in TALLY_RE.findall(text)]


def classify_compile(text: str, checks: list[dict], prefix: str) -> bool:
    start = len(checks)
    bad = [
        normalize_row(line)
        for line in text.splitlines()
        if DIAGNOSTIC_RE.match(normalize_row(line))
        or "Error loading design" in normalize_row(line)
        or "Failed to" in normalize_row(line)
    ]
    add_check(checks, f"{prefix}-no-model-error", not bad, repr(bad))
    tallies = tally_values(text)
    add_check(checks, f"{prefix}-tally-unique", len(tallies) == 1, repr(tallies))
    if len(tallies) == 1:
        add_check(checks, f"{prefix}-tally-zero", tallies[0] == (0, 0), repr(tallies[0]))
    else:
        add_check(checks, f"{prefix}-tally-zero", False, "missing or ambiguous tally")
    return checks_pass(checks, start)


def parse_ordinary(text: str, spec: dict, checks: list[dict]) -> dict:
    start = len(checks)
    begins: list[str] = []
    summaries: list[tuple[int, int, int, int]] = []
    ends: list[str] = []
    case_begins: list[str] = []
    case_ends: list[tuple[str, str, int]] = []
    stats: dict[str, int] = {}
    duplicate_stats: set[str] = set()
    check_fail_rows: list[str] = []
    malformed: list[str] = []
    open_case = None

    for raw in text.splitlines():
        row = normalize_row(raw)
        if not row:
            continue
        if row.startswith("CHECK_FAIL"):
            check_fail_rows.append(row)
            continue
        if row.startswith(("TB_", "CASE_", "GUARD_")):
            match = TB_BEGIN_RE.fullmatch(row)
            if match:
                begins.append(match.group(1))
                continue
            match = TB_END_RE.fullmatch(row)
            if match:
                ends.append(match.group(1))
                continue
            match = TB_SUMMARY_RE.fullmatch(row)
            if match:
                summaries.append(tuple(int(value) for value in match.groups()))
                continue
            match = CASE_BEGIN_RE.fullmatch(row)
            if match:
                name = match.group(1)
                case_begins.append(name)
                if open_case is not None or name in [item[0] for item in case_ends]:
                    malformed.append(row)
                else:
                    open_case = name
                continue
            match = CASE_END_RE.fullmatch(row)
            if match:
                name, status, count = match.group(1), match.group(2), int(match.group(3))
                case_ends.append((name, status, count))
                if open_case != name:
                    malformed.append(row)
                open_case = None
                continue
            match = TB_STAT_RE.fullmatch(row)
            if match:
                key, value = match.group(1), int(match.group(2))
                if key in stats:
                    duplicate_stats.add(key)
                stats[key] = value
                continue
            malformed.append(row)

    add_check(checks, "run-marker-malformed", not malformed, repr(malformed[:8]))
    add_check(checks, "run-check-fail-rows", not check_fail_rows, repr(check_fail_rows[:8]))
    add_check(checks, "run-tb-begin-unique", len(begins) == 1 and begins[0] == spec["top"], repr(begins))
    add_check(checks, "run-tb-end-unique", len(ends) == 1 and ends[0] == "pass", repr(ends))
    add_check(checks, "run-summary-unique", len(summaries) == 1, repr(summaries))
    add_check(checks, "run-case-open-closed", open_case is None, repr(open_case))
    add_check(checks, "run-case-begins-exact", case_begins == spec["cases"], repr(case_begins))
    add_check(
        checks,
        "run-case-ends-exact",
        [item[0] for item in case_ends] == spec["cases"],
        repr([item[0] for item in case_ends]),
    )
    add_check(checks, "run-case-status-pass", all(item[1] == "pass" for item in case_ends), repr(case_ends))
    add_check(checks, "run-case-checks-positive", all(item[2] > 0 for item in case_ends), repr(case_ends))

    case_checks_total = sum(item[2] for item in case_ends)
    summary_record = None
    if len(summaries) == 1:
        summary_cases, summary_pass, summary_fail, summary_checks = summaries[0]
        summary_record = {
            "cases": summary_cases,
            "pass": summary_pass,
            "fail": summary_fail,
            "checks": summary_checks,
        }
        add_check(
            checks,
            "run-summary-cases",
            summary_cases == len(spec["cases"]) and summary_pass == len(spec["cases"]) and summary_fail == 0,
            repr(summaries[0]),
        )
        add_check(checks, "run-summary-check-sum", summary_checks == case_checks_total, f"{summary_checks} != {case_checks_total}")
        add_check(checks, "run-min-checks", summary_checks >= spec["min_checks"], f"{summary_checks} < {spec['min_checks']}")
    else:
        add_check(checks, "run-summary-cases", False, "summary missing")
        add_check(checks, "run-summary-check-sum", False, "summary missing")
        add_check(checks, "run-min-checks", False, "summary missing")

    expected_stats = spec["final"]
    add_check(checks, "run-stats-present", set(stats) == set(expected_stats), repr(stats))
    add_check(checks, "run-stats-unique", not duplicate_stats, repr(sorted(duplicate_stats)))
    for key, value in expected_stats.items():
        add_check(checks, f"run-final-{key}", stats.get(key) == value, f"actual={stats.get(key)} expected={value}")

    return {
        "tb_begin": begins,
        "tb_end": ends,
        "summary": summary_record,
        "case_begins": case_begins,
        "case_ends": [{"name": name, "status": status, "checks": count} for name, status, count in case_ends],
        "case_checks_total": case_checks_total,
        "stats": stats,
        "classification_pass": checks_pass(checks, start),
    }


def parse_guard(text: str, spec: dict, checks: list[dict]) -> dict:
    start = len(checks)
    rows = [normalize_row(line) for line in text.splitlines() if normalize_row(line)]
    fatals = []
    bad_diagnostics = []
    markers = []
    for row in rows:
        if row.startswith(("TB_", "CASE_", "CHECK_FAIL", "GUARD_")):
            markers.append(row)
        match = FATAL_RE.fullmatch(row)
        if match:
            fatals.append(match.group(1))
        elif DIAGNOSTIC_RE.match(row):
            bad_diagnostics.append(row)

    add_check(checks, "guard-fatal-unique", len(fatals) == 1, repr(fatals))
    if len(fatals) == 1:
        add_check(checks, "guard-fatal-exact", fatals[0] == spec["fatal"], repr(fatals[0]))
    else:
        add_check(checks, "guard-fatal-exact", False, "missing or ambiguous fatal")
    add_check(checks, "guard-no-other-diagnostic", not bad_diagnostics, repr(bad_diagnostics[:8]))
    add_check(checks, "guard-no-tb-marker", not markers, repr(markers[:8]))
    tallies = tally_values(text)
    add_check(checks, "guard-tally-unique", len(tallies) == 1, repr(tallies))
    if len(tallies) == 1:
        add_check(checks, "guard-tally-own-fatal", tallies[0] == (1, 0), repr(tallies[0]))
    else:
        add_check(checks, "guard-tally-own-fatal", False, "missing or ambiguous tally")
    return {
        "fatal": fatals,
        "markers": markers,
        "tally": tallies,
        "classification_pass": checks_pass(checks, start),
    }


def snapshot_sources(suite_dir: Path) -> list[dict]:
    snapshot_dir = suite_dir / "sources"
    snapshot_dir.mkdir(parents=False, exist_ok=False)
    records = []
    for key in COMPILE_FILES:
        source = PRODUCT_ROOT / AUTHOR_FILES[key]
        if not source.is_file():
            raise SetupError(f"missing source: {source}")
        data = read_bytes(source)
        snapshot = snapshot_dir / source.name
        with snapshot.open("xb") as handle:
            handle.write(data)
        records.append(
            {
                "key": key,
                "filename": snapshot.name,
                "source": str(source),
                "snapshot": str(snapshot),
                "source_sha256": sha256_file(source),
                "snapshot_sha256": sha256_file(snapshot),
                "bytes": len(data),
            }
        )
    return records


def execute_suite(
    name: str,
    spec: dict,
    out_dir: Path,
    tool_dir: Path,
    timeout_s: int,
) -> dict:
    suite_dir = out_dir / "suites" / name
    suite_dir.mkdir(parents=False, exist_ok=False)
    steps_dir = suite_dir / "steps"
    steps_dir.mkdir()
    checks: list[dict] = []
    result = {
        "name": name,
        "kind": spec["kind"],
        "status": "fail",
        "started_at": utc_now(),
        "suite_dir": str(suite_dir),
        "checks": checks,
    }

    try:
        snapshots = snapshot_sources(suite_dir)
        result["sources"] = snapshots
        for record in snapshots:
            add_check(
                checks,
                f"source-{record['key']}-snapshot-hash",
                record["source_sha256"] == record["snapshot_sha256"],
                record["snapshot_sha256"],
            )
        if not checks_pass(checks):
            raise SetupError("source snapshot check failed")

        vlib = run_process([str(tool_dir / "vlib.exe"), "work"], suite_dir, steps_dir / "01-vlib", timeout_s)
        result["vlib"] = vlib
        classify_process(vlib, checks, "vlib")
        vlib_text = combined_text(steps_dir / "01-vlib")
        bad_vlib = [
            normalize_row(line)
            for line in vlib_text.splitlines()
            if DIAGNOSTIC_RE.match(normalize_row(line)) or "Error loading design" in normalize_row(line)
        ]
        add_check(checks, "vlib-no-model-error", not bad_vlib, repr(bad_vlib))
        add_check(checks, "vlib-work-directory", (suite_dir / "work").is_dir(), str(suite_dir / "work"))
        if not checks_pass(checks):
            raise SetupError("vlib check failed")

        vlog_argv = [str(tool_dir / "vlog.exe"), "-sv", "-work", "work"]
        for macro, value in spec.get("defines", {}).items():
            vlog_argv.append(f"+define+{macro}={value}")
        vlog_argv.extend(f"sources/{record['filename']}" for record in snapshots)
        vlog = run_process(vlog_argv, suite_dir, steps_dir / "02-vlog", timeout_s)
        result["vlog"] = vlog
        classify_process(vlog, checks, "vlog")
        compile_pass = classify_compile(combined_text(steps_dir / "02-vlog"), checks, "compile")
        result["compile_pass"] = compile_pass
        if not compile_pass or not checks_pass(checks):
            raise SetupError("compile check failed")

        vsim_argv = [
            str(tool_dir / "vsim.exe"),
            "-c",
            "-do",
            "run -all; quit -f",
            "-l",
            "vsim.log",
            spec["top"],
        ]
        vsim = run_process(vsim_argv, suite_dir, steps_dir / "03-vsim", timeout_s)
        result["vsim"] = vsim
        classify_process(vsim, checks, "vsim")
        vsim_text = combined_text(steps_dir / "03-vsim")
        vsim_log = suite_dir / "vsim.log"
        if vsim_log.is_file():
            result["vsim_log"] = {
                "path": str(vsim_log),
                "bytes": vsim_log.stat().st_size,
                "sha256": sha256_file(vsim_log),
            }
        else:
            add_check(checks, "vsim-log-present", False, str(vsim_log))

        tallies = tally_values(vsim_text)
        add_check(checks, "run-tally-unique", len(tallies) == 1, repr(tallies))
        if spec["kind"] == "ordinary":
            add_check(checks, "run-tally-zero", len(tallies) == 1 and tallies[0] == (0, 0), repr(tallies))
            bad = [
                normalize_row(line)
                for line in vsim_text.splitlines()
                if DIAGNOSTIC_RE.match(normalize_row(line)) or "Error loading design" in normalize_row(line)
            ]
            add_check(checks, "run-no-model-error", not bad, repr(bad[:8]))
            result["run"] = parse_ordinary(vsim_text, spec, checks)
        else:
            result["run"] = parse_guard(vsim_text, spec, checks)

        for record in snapshots:
            current_hash = sha256_file(PRODUCT_ROOT / AUTHOR_FILES[record["key"]])
            add_check(
                checks,
                f"source-{record['key']}-unchanged",
                current_hash == record["source_sha256"],
                f"actual={current_hash} snapshot={record['source_sha256']}",
            )
        result["status"] = "pass" if checks_pass(checks) else "fail"
    except Exception:
        exception_text = traceback.format_exc()
        with (suite_dir / "EXCEPTION.txt").open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(exception_text)
        add_check(checks, "suite-exception", False, exception_text.splitlines()[-1])
        result["exception"] = exception_text
        result["status"] = "fail"
    finally:
        result["finished_at"] = utc_now()
        result["failed_checks"] = sum(1 for item in checks if not item["pass"])
        write_json(suite_dir / "suite_result.json", result)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-id", required=True, help="fresh suffix below author/attempt-<id>")
    parser.add_argument("--tool-dir", default=str(TOOL_DIR_DEFAULT))
    parser.add_argument("--timeout", type=int, default=300, help="seconds per subprocess")
    parser.add_argument(
        "--suite",
        action="append",
        choices=list(SUITES),
        help="run only the selected suite; repeatable; default is every suite",
    )
    return parser.parse_args(argv)


def verify_contract(checks: list[dict]) -> dict:
    path = PRODUCT_ROOT / CONTRACT_REL
    if not path.is_file():
        add_check(checks, "contract-file", False, str(path))
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    requirements = data.get("requirements")
    encoded = json.dumps(
        requirements,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    actual = hashlib.sha256(encoded).hexdigest()
    add_check(checks, "contract-id", data.get("contract_id") == "DEEPEYE-HUMAN-LOCK-20261014" and data.get("revision") == 1, str(data.get("contract_id")))
    add_check(checks, "contract-requirement-count", len(requirements) == 15, str(len(requirements)))
    add_check(checks, "contract-requirement-ids", [item.get("id") for item in requirements] == [f"H{index:02d}" for index in range(1, 16)], "")
    add_check(checks, "contract-requirements-sha256", actual == EXPECTED_REQUIREMENTS_SHA256, actual)
    return {
        "path": str(path.resolve()),
        "file_sha256": sha256_file(path),
        "requirements_sha256": actual,
        "requirement_count": len(requirements),
        "contract_id": f"{data.get('contract_id')}/revision{data.get('revision')}",
        "pinned_contract_commit": CONTRACT_COMMIT,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.timeout < 1:
        print("ERROR: timeout must be positive", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.attempt_id):
        print("ERROR: unsafe attempt id", file=sys.stderr)
        return 2

    out_dir = EVIDENCE_ROOT / f"attempt-{args.attempt_id}"
    if out_dir.exists():
        print(f"ERROR: attempt output already exists: {out_dir}", file=sys.stderr)
        return 2
    if out_dir.parent.resolve() != EVIDENCE_ROOT.resolve():
        print("ERROR: output escaped author evidence root", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=False)

    console_path = out_dir / "RUNNER_CONSOLE.txt"
    console_handle = console_path.open("x", encoding="utf-8", newline="\n")

    def log_line(text: str) -> None:
        print(text, flush=True)
        console_handle.write(text + "\n")
        console_handle.flush()

    started_at = utc_now()
    start_monotonic = time.monotonic()
    selected = args.suite if args.suite else list(SUITES)
    checks: list[dict] = []
    result: dict = {
        "schema": 1,
        "status": "fail",
        "operation_id": OPERATION_ID,
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "work_id": WORK_ID,
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "base_head": BASE_HEAD,
        "frozen_design": FROZEN_DESIGN,
        "contract_id": CONTRACT_ID,
        "attempt_id": args.attempt_id,
        "out_dir": str(out_dir.resolve()),
        "started_at": started_at,
        "python": sys.version,
        "platform": platform.platform(),
        "argv": sys.argv,
        "cwd": str(Path.cwd()),
        "selected_suites": selected,
        "global_checks": checks,
        "suites": {},
        "limits": [
            "RTL simulation only; no synthesis, implementation, timing, CDC/RDC or hardware result.",
            "Author evidence is not independent main acceptance or a public ABI claim.",
            "Guard suites intentionally expect the module's own exact time-zero fatal and ModelSim's resulting one-error tally.",
            "No UART pin, clock calibration, direction enable, reception, framing or board path is tested.",
        ],
    }
    exit_code = 1
    try:
        log_line(f"RUNNER_BEGIN operation={OPERATION_ID} attempt={args.attempt_id}")
        startup_temp = Path(os.environ.get("TEMP", "")).resolve()
        startup_tmp = Path(os.environ.get("TMP", "")).resolve()
        add_check(checks, "startup-python-no-bytecode", os.environ.get("PYTHONDONTWRITEBYTECODE") == "1", os.environ.get("PYTHONDONTWRITEBYTECODE", ""))
        add_check(checks, "startup-temp-owned", startup_temp.is_relative_to(EVIDENCE_ROOT.resolve()), str(startup_temp))
        add_check(checks, "startup-tmp-owned", startup_tmp.is_relative_to(EVIDENCE_ROOT.resolve()), str(startup_tmp))
        add_check(checks, "output-under-author", out_dir.resolve().is_relative_to(EVIDENCE_ROOT.resolve()), str(out_dir.resolve()))
        if not checks_pass(checks):
            raise SetupError("startup environment must keep no-bytecode and TEMP/TMP under author evidence")

        contract = verify_contract(checks)
        result["contract"] = contract
        if not checks_pass(checks):
            raise SetupError("frozen contract verification failed")

        author_hashes = {}
        for key, rel in AUTHOR_FILES.items():
            path = PRODUCT_ROOT / rel
            if not path.is_file():
                add_check(checks, f"author-file-{key}", False, str(path))
                continue
            author_hashes[key] = {
                "path": str(path.resolve()),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        add_check(checks, "author-files-complete", set(author_hashes) == set(AUTHOR_FILES), repr(sorted(author_hashes)))
        result["author_files_at_start"] = author_hashes
        if not checks_pass(checks):
            raise SetupError("author file set incomplete")

        tool_dir = Path(args.tool_dir).expanduser().resolve()
        tool_records = {}
        for exe_name in ["vlib.exe", "vlog.exe", "vsim.exe"]:
            path = tool_dir / exe_name
            exists = path.is_file()
            add_check(checks, f"tool-exists-{exe_name}", exists, str(path))
            if exists:
                tool_records[exe_name] = {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
        result["toolchain"] = tool_records
        if not checks_pass(checks):
            raise SetupError("required ModelSim executable missing")

        toolchain_dir = out_dir / "toolchain"
        toolchain_dir.mkdir()
        for exe_name in ["vlog.exe", "vsim.exe"]:
            step_dir = toolchain_dir / f"{exe_name}-version"
            record = run_process([str(tool_dir / exe_name), "-version"], toolchain_dir, step_dir, 30)
            classify_process(record, checks, f"version-{exe_name}")
            version_text = combined_text(step_dir)
            add_check(checks, f"version-{exe_name}-modeltech", "Model Technology" in version_text, version_text.strip())
            tool_records[exe_name]["version_output"] = version_text.strip()

        git_exe = shutil.which("git")
        # Git HEAD is context; actual per-run snapshots/hashes bind tested bytes.
        result["git_context"] = {"available": False, "historical_base": BASE_HEAD,
                                 "role": "provenance_only_not_test_gate"}
        if git_exe:
            git_step = toolchain_dir / "git-head"
            git_record = run_process([git_exe, "-C", str(PRODUCT_ROOT), "rev-parse", "HEAD"], PRODUCT_ROOT, git_step, 30)
            git_text = combined_text(git_step).strip()
            result["git_context"].update(
                available=git_record["returncode"] == 0 and re.fullmatch(r"[0-9a-f]{40}", git_text) is not None,
                observed_output=git_text, process=git_record,
            )
        if not checks_pass(checks):
            raise SetupError("toolchain or repository preflight failed")

        (out_dir / "suites").mkdir()
        for suite_name in selected:
            log_line(f"RUN_SUITE_BEGIN name={suite_name}")
            suite_result = execute_suite(suite_name, SUITES[suite_name], out_dir, tool_dir, args.timeout)
            result["suites"][suite_name] = suite_result
            log_line(
                f"RUN_SUITE_END name={suite_name} status={suite_result['status']} "
                f"failed_checks={suite_result.get('failed_checks', -1)}"
            )

        end_hashes = {}
        for key, rel in AUTHOR_FILES.items():
            path = PRODUCT_ROOT / rel
            end_hashes[key] = sha256_file(path) if path.is_file() else None
        result["author_files_at_end"] = end_hashes
        add_check(checks, "author-files-unchanged-during-run", end_hashes == {key: value["sha256"] for key, value in author_hashes.items()}, "")
        if not checks_pass(checks):
            raise SetupError("author files changed during the run")
    except Exception:
        exception_text = traceback.format_exc()
        with (out_dir / "EXCEPTION.txt").open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(exception_text)
        add_check(checks, "runner-setup", False, exception_text.splitlines()[-1])
        log_line("RUNNER_EXCEPTION " + exception_text.splitlines()[-1])

    suite_pass = bool(result["suites"]) and all(
        suite.get("status") == "pass" for suite in result["suites"].values()
    )
    all_selected_ran = len(result["suites"]) == len(selected)
    result["status"] = "pass" if checks_pass(checks) and suite_pass and all_selected_ran else "fail"
    result["finished_at"] = utc_now()
    result["duration_s"] = round(time.monotonic() - start_monotonic, 3)
    result["selected_suites_ran"] = all_selected_ran
    result["failed_global_checks"] = sum(1 for item in checks if not item["pass"])
    write_json(out_dir / "result.json", result)
    log_line(f"RUNNER_RESULT status={result['status']} attempt={args.attempt_id}")
    exit_code = 0 if result["status"] == "pass" else 1
    console_handle.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
