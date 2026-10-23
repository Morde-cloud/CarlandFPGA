#!/usr/bin/env python3
"""Strict fail-closed ModelSim 10.7 runner for deepeye_uart_frame_tx.

Work: B-UART-FRAME-TX-20261023-26-v1
Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Operation: B-DEEPEYE-UART-FRAME-TX-20261023-26

Every invocation creates a fresh attempt below the author evidence root.  Each
suite receives immutable source snapshots, its own ModelSim work library, and
its own TEMP/TMP/TMPDIR/cache directories.  The exact argv, cwd, process exit,
timeout state, separate raw stdout/stderr bytes and every relevant hash are
retained.  Ordinary suites require exact ordered markers, exact case checks,
zero ModelSim errors/warnings and exact final counters.  Guard suites require
only the module's own exact time-zero fatal.

The current Git HEAD is recorded as provenance and is deliberately not a test
gate.  Test validity is bound to the bytes snapshotted for this attempt.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

OPERATION_ID = "B-DEEPEYE-UART-FRAME-TX-20261023-26"
TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
WORK_ID = "B-UART-FRAME-TX-20261023-26-v1"
MODEL = "deepseek-v4.1-flash"
REASONING_EFFORT = "max"
BASE_HEAD = "b90fcbc58cdd7f3bf53fb6931dbdd47cd55afc8a"
FROZEN_DESIGN = "1011259415a0916054eb580687612580bc1e5f09"
CONTRACT_ID = "DEEPEYE-HUMAN-LOCK-20261014/revision1"
CONTRACT_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
EXPECTED_REQUIREMENTS_SHA256 = (
    "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
)
EXPECTED_SCOPE_SHA256 = (
    "10e51f7dc039468b79a95cc6bc66f731b8df6fce453f273004a93dd7693a97fd"
)
EXPECTED_TX_SHA256 = (
    "5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47"
)

PRODUCT_ROOT = Path(__file__).resolve().parents[4]
EVIDENCE_ROOT = (
    PRODUCT_ROOT
    / "competition/deepeye/evidence/transport/uart-frame-tx-20261023-26/author"
)
CONTRACT_REL = Path("docs/competition/deepeye-2026/immutable_scope.json")
SCOPE_REL = Path(
    ".local/deployment/node-b/evidence/uart-frame-tx-20261023-26/SCOPE.md"
)

DEPENDENCY_REL = Path("competition/deepeye/fpga/transport/deepeye_uart_tx.sv")
AUTHOR_FILES = {
    "rtl": Path(
        "competition/deepeye/fpga/transport/deepeye_uart_frame_tx.sv"
    ),
    "candidate": Path(
        "competition/deepeye/fpga/transport/uart_frame_tx_candidate.md"
    ),
    "tb": Path(
        "competition/deepeye/tests/rtl/transport/tb_uart_frame_tx.sv"
    ),
    "runner": Path(
        "competition/deepeye/tools/transport/run_uart_frame_tx.py"
    ),
}

ALL_LENGTHS_CASES = ["reset_idle", "all_lengths_1_64", "source_silence"]
ALL_BYTES_CASES = ["reset_idle", "all_byte_values"]
GUARDS_CASES = [
    "reset_idle",
    "unequal_guards",
    "raw_gaps",
    "no_same_edge_cfg_sample",
    "completion_no_credit",
]
MAX_GUARDS_CASES = ["reset_idle", "max_guards"]
FAULTS_CASES = [
    "reset_idle",
    "invalid_counts",
    "missing_final_last",
    "early_last",
    "sticky_recovery",
    "repeat_fault_event",
]
CANCEL_RESET_CASES = [
    "reset_idle",
    "cancel_receive",
    "cancel_seal_pre",
    "cancel_byte_between",
    "cancel_final_post",
    "reset_stages",
    "held_cancel_reset_priority",
    "cancel_retire_edge",
]
STAT2_CASES = ["reset_idle", "stat_saturation"]
EXAMPLE_CASES = ["reset_idle", "default_9600_example"]
BAUD300_CASES = ["reset_idle", "baud300_example"]
BAUD1200_CASES = ["reset_idle", "baud1200_example"]

SUITES = {
    "lengths": {
        "kind": "ordinary",
        "top": "tb_uart_frame_tx_lengths",
        "cases": ALL_LENGTHS_CASES,
        "min_checks": 1_300_000,
        "final": {"admitted": 65, "sent": 65, "aborted": 0, "faults": 0},
    },
    "all_bytes": {
        "kind": "ordinary",
        "top": "tb_uart_frame_tx_all_bytes",
        "cases": ALL_BYTES_CASES,
        "min_checks": 200_000,
        "final": {"admitted": 4, "sent": 4, "aborted": 0, "faults": 0},
    },
    "guards": {
        "kind": "ordinary",
        "top": "tb_uart_frame_tx_guards",
        "cases": GUARDS_CASES,
        "min_checks": 7_000,
        "final": {"admitted": 5, "sent": 5, "aborted": 0, "faults": 0},
    },
    "max_guards": {
        "kind": "ordinary",
        "top": "tb_uart_frame_tx_max_guards",
        "cases": MAX_GUARDS_CASES,
        "min_checks": 500,
        "final": {"admitted": 1, "sent": 1, "aborted": 0, "faults": 0},
    },
    "faults": {
        "kind": "ordinary",
        "top": "tb_uart_frame_tx_faults",
        "cases": FAULTS_CASES,
        "min_checks": 2_000,
        "final": {"admitted": 7, "sent": 1, "aborted": 6, "faults": 6},
    },
    "cancel_reset": {
        "kind": "ordinary",
        "top": "tb_uart_frame_tx_cancel_reset",
        "cases": CANCEL_RESET_CASES,
        "min_checks": 1_000,
        "final": {"admitted": 1, "sent": 0, "aborted": 1, "faults": 0},
    },
    "stat_w2": {
        "kind": "ordinary",
        "top": "tb_uart_frame_tx_stat_w2",
        "cases": STAT2_CASES,
        "min_checks": 4_000,
        "final": {"admitted": 3, "sent": 3, "aborted": 3, "faults": 3},
    },
    "default_9600": {
        "kind": "ordinary",
        "top": "tb_uart_frame_tx_default_9600",
        "cases": EXAMPLE_CASES,
        "min_checks": 800,
        "final": {"admitted": 1, "sent": 1, "aborted": 0, "faults": 0},
    },
    "baud300": {
        "kind": "ordinary",
        "top": "tb_uart_frame_tx_baud300",
        "cases": BAUD300_CASES,
        "min_checks": 500,
        "final": {"admitted": 1, "sent": 1, "aborted": 0, "faults": 0},
    },
    "baud1200": {
        "kind": "ordinary",
        "top": "tb_uart_frame_tx_baud1200",
        "cases": BAUD1200_CASES,
        "min_checks": 800,
        "final": {"admitted": 1, "sent": 1, "aborted": 0, "faults": 0},
    },
    "guard_clock": {
        "kind": "guard",
        "top": "tb_uart_frame_tx_guard_top",
        "defines": {
            "G_CLOCK_HZ": "1",
            "G_BAUD": "0",
            "G_PRE_CYCLES": "65536",
            "G_POST_CYCLES": "65536",
            "G_STAT_W": "1",
        },
        "fatal": "deepeye_uart_frame_tx: CLOCK_HZ out of range",
    },
    "guard_baud_low": {
        "kind": "guard",
        "top": "tb_uart_frame_tx_guard_top",
        "defines": {
            "G_CLOCK_HZ": "97",
            "G_BAUD": "0",
            "G_PRE_CYCLES": "65536",
            "G_POST_CYCLES": "65536",
            "G_STAT_W": "1",
        },
        "fatal": "deepeye_uart_frame_tx: BAUD out of range",
    },
    "guard_baud_high": {
        "kind": "guard",
        "top": "tb_uart_frame_tx_guard_top",
        "defines": {
            "G_CLOCK_HZ": "2",
            "G_BAUD": "2",
            "G_PRE_CYCLES": "65536",
            "G_POST_CYCLES": "65536",
            "G_STAT_W": "1",
        },
        "fatal": "deepeye_uart_frame_tx: BAUD out of range",
    },
    "guard_pre": {
        "kind": "guard",
        "top": "tb_uart_frame_tx_guard_top",
        "defines": {
            "G_CLOCK_HZ": "97",
            "G_BAUD": "11",
            "G_PRE_CYCLES": "65536",
            "G_POST_CYCLES": "65536",
            "G_STAT_W": "1",
        },
        "fatal": "deepeye_uart_frame_tx: PRE_CYCLES out of range",
    },
    "guard_post": {
        "kind": "guard",
        "top": "tb_uart_frame_tx_guard_top",
        "defines": {
            "G_CLOCK_HZ": "97",
            "G_BAUD": "11",
            "G_PRE_CYCLES": "0",
            "G_POST_CYCLES": "65536",
            "G_STAT_W": "1",
        },
        "fatal": "deepeye_uart_frame_tx: POST_CYCLES out of range",
    },
    "guard_stat_low": {
        "kind": "guard",
        "top": "tb_uart_frame_tx_guard_top",
        "defines": {
            "G_CLOCK_HZ": "97",
            "G_BAUD": "11",
            "G_PRE_CYCLES": "0",
            "G_POST_CYCLES": "0",
            "G_STAT_W": "1",
        },
        "fatal": "deepeye_uart_frame_tx: STAT_W out of range",
    },
    "guard_stat_high": {
        "kind": "guard",
        "top": "tb_uart_frame_tx_guard_top",
        "defines": {
            "G_CLOCK_HZ": "97",
            "G_BAUD": "11",
            "G_PRE_CYCLES": "0",
            "G_POST_CYCLES": "0",
            "G_STAT_W": "33",
        },
        "fatal": "deepeye_uart_frame_tx: STAT_W out of range",
    },
}

TALLY_RE = re.compile(
    r"^Errors:[ \t]*(\d+),[ \t]*Warnings:[ \t]*(\d+)[ \t]*$"
)
DIAGNOSTIC_RE = re.compile(r"^\*\*[ \t]+(?:Error|Warning|Fatal)\b")
ERROR_OR_WARNING_RE = re.compile(r"^\*\*[ \t]+(?:Error|Warning)\b")
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
TB_STAT_RE = re.compile(
    r"^TB_STAT[ \t]+admitted=(\d+)[ \t]+sent=(\d+)"
    r"[ \t]+aborted=(\d+)[ \t]+faults=(\d+)$"
)


class SetupError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def decode_raw(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def combined_text(step_dir: Path) -> str:
    return (
        decode_raw((step_dir / "stdout.bin").read_bytes())
        + "\n"
        + decode_raw((step_dir / "stderr.bin").read_bytes())
    )


def normalize_row(raw: str) -> str:
    text = raw.strip()
    if text.startswith("#"):
        text = text[1:].strip()
    return text


def add_check(checks: list[dict], name: str, passed: bool, detail: str = "") -> bool:
    checks.append({"name": name, "pass": bool(passed), "detail": str(detail)})
    return bool(passed)


def checks_pass(checks: list[dict], start: int = 0) -> bool:
    return all(item["pass"] for item in checks[start:])


def full_path(relative: Path) -> Path:
    return PRODUCT_ROOT / relative


def resolve_tool_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    discovered = shutil.which("vlog") or shutil.which("vlog.exe")
    if discovered:
        return Path(discovered).resolve().parent
    for variable in ("MODELSIM_HOME", "MODELSIM_ROOT"):
        value = os.environ.get(variable)
        if value:
            candidate = Path(value).expanduser()
            if (candidate / "win64" / "vlog.exe").is_file():
                return (candidate / "win64").resolve()
            return candidate.resolve()
    return Path(".")


def tool_path(tool_dir: Path, stem: str) -> Path:
    windows = tool_dir / f"{stem}.exe"
    if windows.is_file() or os.name == "nt":
        return windows
    return tool_dir / stem


def run_process(
    argv: list[str],
    cwd: Path,
    step_dir: Path,
    timeout_s: int,
    env_base: dict[str, str] | None = None,
) -> dict:
    step_dir.mkdir(parents=False, exist_ok=False)
    temp_dir = step_dir / "tmp"
    temp_dir.mkdir()
    pycache_dir = step_dir / "pycache"
    env = dict(env_base or os.environ)
    env["TEMP"] = str(temp_dir.resolve())
    env["TMP"] = str(temp_dir.resolve())
    env["TMPDIR"] = str(temp_dir.resolve())
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
                "TMPDIR": env["TMPDIR"],
                "PYTHONDONTWRITEBYTECODE": env["PYTHONDONTWRITEBYTECODE"],
                "PYTHONPYCACHEPREFIX": env["PYTHONPYCACHEPREFIX"],
            },
        },
    )

    stdout_path = step_dir / "stdout.bin"
    stderr_path = step_dir / "stderr.bin"
    started_monotonic = time.monotonic()
    returncode: int | None = None
    timed_out = False
    spawn_error: str | None = None
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

    duration_s = round(time.monotonic() - started_monotonic, 3)
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
    values: list[tuple[int, int]] = []
    for raw in text.splitlines():
        match = TALLY_RE.fullmatch(normalize_row(raw))
        if match:
            values.append((int(match.group(1)), int(match.group(2))))
    return values


def model_diagnostics(text: str, include_fatal: bool = True) -> list[str]:
    pattern = DIAGNOSTIC_RE if include_fatal else ERROR_OR_WARNING_RE
    result = []
    for raw in text.splitlines():
        row = normalize_row(raw)
        if pattern.match(row) or "Error loading design" in row or "Failed to" in row:
            result.append(row)
    return result


def classify_compile(text: str, checks: list[dict], prefix: str) -> bool:
    start = len(checks)
    bad = model_diagnostics(text, include_fatal=True)
    add_check(checks, f"{prefix}-no-model-error", not bad, repr(bad[:8]))
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
    open_case: str | None = None

    for raw in text.splitlines():
        row = normalize_row(raw)
        if not row:
            continue
        if row.startswith("CHECK_FAIL"):
            check_fail_rows.append(row)
            continue
        if not row.startswith(("TB_", "CASE_")):
            continue

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
            values = tuple(int(value) for value in match.groups())
            if stats:
                duplicate_stats.add("TB_STAT")
            stats = dict(zip(("admitted", "sent", "aborted", "faults"), values))
            continue
        malformed.append(row)

    marker_rows = [normalize_row(row) for row in text.splitlines() if normalize_row(row).startswith(("TB_", "CASE_"))]
    marker_order = [row.split()[0] for row in marker_rows]
    expected_order = ["TB_BEGIN"] + [tag for _ in spec["cases"] for tag in ("CASE_BEGIN", "CASE_END")] + ["TB_SUMMARY", "TB_STAT", "TB_END"]
    add_check(checks, "run-marker-order", marker_order == expected_order, repr(marker_order))
    add_check(checks, "run-marker-malformed", not malformed, repr(malformed[:8]))
    add_check(checks, "run-check-fail-rows", not check_fail_rows, repr(check_fail_rows[:8]))
    add_check(
        checks,
        "run-tb-begin-unique",
        len(begins) == 1 and begins[0] == spec["top"],
        repr(begins),
    )
    add_check(checks, "run-tb-end-unique", len(ends) == 1 and ends[0] == "pass", repr(ends))
    add_check(checks, "run-summary-unique", len(summaries) == 1, repr(summaries))
    add_check(checks, "run-case-open-closed", open_case is None, repr(open_case))
    add_check(
        checks,
        "run-case-begins-exact",
        case_begins == spec["cases"],
        repr(case_begins),
    )
    add_check(
        checks,
        "run-case-ends-exact",
        [item[0] for item in case_ends] == spec["cases"],
        repr(case_ends),
    )
    add_check(
        checks,
        "run-case-all-pass",
        all(item[1] == "pass" and item[2] > 0 for item in case_ends),
        repr(case_ends),
    )
    add_check(checks, "run-stat-keys", set(stats) == {"admitted", "sent", "aborted", "faults"}, repr(stats))
    add_check(checks, "run-stat-no-duplicates", not duplicate_stats, repr(sorted(duplicate_stats)))
    add_check(checks, "run-final-counters", stats == spec["final"], f"{stats!r} expected={spec['final']!r}")

    if len(summaries) == 1:
        summary_cases, summary_pass, summary_fail, summary_checks = summaries[0]
        add_check(checks, "run-summary-cases", summary_cases == len(spec["cases"]), repr(summaries[0]))
        add_check(checks, "run-summary-pass", summary_pass == len(spec["cases"]), repr(summaries[0]))
        add_check(checks, "run-summary-fail", summary_fail == 0, repr(summaries[0]))
        add_check(checks, "run-summary-min-checks", summary_checks >= spec["min_checks"], f"checks={summary_checks}")
        expected_checks = sum(item[2] for item in case_ends) + 1
        add_check(
            checks,
            "run-summary-check-total",
            summary_checks == expected_checks,
            f"summary={summary_checks} case_sum_plus_final={expected_checks}",
        )

    return {
        "begins": begins,
        "ends": ends,
        "summaries": summaries,
        "case_begins": case_begins,
        "case_ends": case_ends,
        "stats": stats,
        "check_fail_rows": check_fail_rows,
        "malformed": malformed,
        "status": "pass" if checks_pass(checks, start) else "fail",
    }


def parse_guard(text: str, spec: dict, checks: list[dict]) -> dict:
    start = len(checks)
    fatals: list[str] = []
    for raw in text.splitlines():
        match = FATAL_RE.fullmatch(normalize_row(raw))
        if match:
            fatals.append(match.group(1))
    tallies = tally_values(text)
    bad = model_diagnostics(text, include_fatal=False)
    add_check(checks, "guard-no-unexpected-diagnostic", not bad, repr(bad[:8]))
    add_check(checks, "guard-no-unexpected-marker", "GUARD_UNEXPECTED_NO_FATAL" not in text, "")
    add_check(checks, "guard-fatal-unique", len(fatals) == 1, repr(fatals))
    add_check(checks, "guard-fatal-exact", fatals == [spec["fatal"]], repr(fatals))
    add_check(checks, "guard-tally-unique", len(tallies) == 1, repr(tallies))
    add_check(checks, "guard-tally-expected", tallies == [(1, 0)], repr(tallies))
    return {
        "fatals": fatals,
        "tallies": tallies,
        "status": "pass" if checks_pass(checks, start) else "fail",
    }


def snapshot_sources(suite_dir: Path, checks: list[dict]) -> list[dict]:
    source_dir = suite_dir / "sources"
    source_dir.mkdir()
    records: list[dict] = []
    for key, relative in [
        ("dependency", DEPENDENCY_REL),
        ("rtl", AUTHOR_FILES["rtl"]),
        ("tb", AUTHOR_FILES["tb"]),
    ]:
        source = full_path(relative)
        if not source.is_file():
            add_check(checks, f"source-{key}-present", False, str(source))
            continue
        filename = source.name
        destination = source_dir / filename
        shutil.copyfile(source, destination)
        source_hash = sha256_file(source)
        snapshot_hash = sha256_file(destination)
        records.append(
            {
                "key": key,
                "relative_path": relative.as_posix(),
                "source_path": str(source.resolve()),
                "filename": filename,
                "bytes": source.stat().st_size,
                "source_sha256": source_hash,
                "snapshot_path": str(destination.resolve()),
                "snapshot_sha256": snapshot_hash,
            }
        )
    add_check(checks, "source-set-complete", {item["key"] for item in records} == {"dependency", "rtl", "tb"}, repr(records))
    if records:
        write_json(suite_dir / "source_manifest.json", records)
    return records


def verify_contract(toolchain_dir: Path, checks: list[dict]) -> dict:
    steps = toolchain_dir / "contract"
    steps.mkdir()
    git_exe = shutil.which("git")
    add_check(checks, "contract-git-present", git_exe is not None, str(git_exe))
    if not git_exe:
        return {}
    record = run_process(
        [git_exe, "-C", str(PRODUCT_ROOT), "show", f"{CONTRACT_COMMIT}:{CONTRACT_REL.as_posix()}"],
        PRODUCT_ROOT,
        steps / "git-show-pinned",
        30,
    )
    classify_process(record, checks, "contract-git-show")
    raw = (steps / "git-show-pinned" / "stdout.bin").read_bytes()
    if record["returncode"] != 0:
        return {}
    data = json.loads(raw.decode("utf-8"))
    requirements = data.get("requirements")
    canonical = json.dumps(
        requirements,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    actual = sha256_bytes(canonical)
    add_check(
        checks,
        "contract-id",
        data.get("contract_id") == "DEEPEYE-HUMAN-LOCK-20261014" and data.get("revision") == 1,
        str(data.get("contract_id")),
    )
    add_check(checks, "contract-requirement-count", len(requirements) == 15, str(len(requirements)))
    add_check(
        checks,
        "contract-requirement-ids",
        [item.get("id") for item in requirements] == [f"H{index:02d}" for index in range(1, 16)],
        "",
    )
    add_check(checks, "contract-requirements-sha256", actual == EXPECTED_REQUIREMENTS_SHA256, actual)
    return {
        "pinned_commit": CONTRACT_COMMIT,
        "relative_path": CONTRACT_REL.as_posix(),
        "raw_sha256": sha256_bytes(raw),
        "requirements_sha256": actual,
        "requirement_count": len(requirements),
        "contract_id": f"{data.get('contract_id')}/revision{data.get('revision')}",
        "git_show_step": str((steps / "git-show-pinned").resolve()),
    }


def verify_scope(checks: list[dict]) -> dict:
    candidates = [
        PRODUCT_ROOT.parents[2] / SCOPE_REL if len(PRODUCT_ROOT.parents) >= 3 else None,
        PRODUCT_ROOT / SCOPE_REL,
    ]
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            actual = sha256_file(candidate)
            add_check(checks, "operation-scope-sha256", actual == EXPECTED_SCOPE_SHA256, actual)
            return {
                "status": "verified" if actual == EXPECTED_SCOPE_SHA256 else "mismatch",
                "path": str(candidate.resolve()),
                "sha256": actual,
                "expected_sha256": EXPECTED_SCOPE_SHA256,
            }
    return {"status": "not_found_context_only", "expected_sha256": EXPECTED_SCOPE_SHA256}


def execute_suite(
    suite_name: str,
    spec: dict,
    out_dir: Path,
    tool_dir: Path,
    timeout_s: int,
) -> dict:
    checks: list[dict] = []
    suite_dir = out_dir / "suites" / suite_name
    suite_dir.mkdir(parents=True, exist_ok=False)
    steps_dir = suite_dir / "steps"
    steps_dir.mkdir()
    result: dict = {
        "schema": 1,
        "suite": suite_name,
        "kind": spec["kind"],
        "top": spec["top"],
        "status": "fail",
        "checks": checks,
        "started_at": utc_now(),
    }

    try:
        snapshots = snapshot_sources(suite_dir, checks)
        result["sources"] = snapshots
        dependency = next((item for item in snapshots if item["key"] == "dependency"), None)
        add_check(
            checks,
            "dependency-exact-sha256",
            dependency is not None and dependency["source_sha256"] == EXPECTED_TX_SHA256,
            "" if dependency is None else dependency["source_sha256"],
        )
        for record in snapshots:
            add_check(
                checks,
                f"source-{record['key']}-snapshot-hash",
                record["source_sha256"] == record["snapshot_sha256"],
                record["snapshot_sha256"],
            )
        if not checks_pass(checks):
            raise SetupError("source snapshot check failed")

        vlib = run_process([str(tool_path(tool_dir, "vlib")), "work"], suite_dir, steps_dir / "01-vlib", timeout_s)
        result["vlib"] = vlib
        classify_process(vlib, checks, "vlib")
        vlib_text = combined_text(steps_dir / "01-vlib")
        add_check(checks, "vlib-no-model-error", not model_diagnostics(vlib_text, include_fatal=True), repr(model_diagnostics(vlib_text, include_fatal=True)[:8]))
        add_check(checks, "vlib-work-directory", (suite_dir / "work").is_dir(), str(suite_dir / "work"))
        if not checks_pass(checks):
            raise SetupError("vlib check failed")

        vlog_argv = [str(tool_path(tool_dir, "vlog")), "-sv", "-work", "work"]
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
            str(tool_path(tool_dir, "vsim")),
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
        run_text = combined_text(steps_dir / "03-vsim")
        vsim_log = suite_dir / "vsim.log"
        if vsim_log.is_file():
            result["vsim_log"] = {
                "path": str(vsim_log.resolve()),
                "bytes": vsim_log.stat().st_size,
                "sha256": sha256_file(vsim_log),
            }
            add_check(checks, "vsim-log-hash", result["vsim_log"]["bytes"] > 0, repr(result["vsim_log"]))
        else:
            add_check(checks, "vsim-log-present", False, str(vsim_log))

        tallies = tally_values(run_text)
        add_check(checks, "run-tally-unique", len(tallies) == 1, repr(tallies))
        if spec["kind"] == "ordinary":
            add_check(checks, "run-tally-zero", tallies == [(0, 0)], repr(tallies))
            bad = model_diagnostics(run_text, include_fatal=True)
            add_check(checks, "run-no-model-error", not bad, repr(bad[:8]))
            result["run"] = parse_ordinary(run_text, spec, checks)
        else:
            result["run"] = parse_guard(run_text, spec, checks)

        for record in snapshots:
            current_hash = sha256_file(full_path(Path(record["relative_path"])))
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
    parser.add_argument("--tool-dir", default=None, help="directory containing vlib/vlog/vsim")
    parser.add_argument("--timeout", type=int, default=300, help="seconds per subprocess")
    parser.add_argument(
        "--suite",
        action="append",
        choices=list(SUITES),
        help="run only this suite; repeatable; default is every suite",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.timeout < 1:
        print("ERROR: timeout must be positive", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.attempt_id):
        print("ERROR: unsafe attempt id", file=sys.stderr)
        return 2

    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
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

    def log_line(value: str) -> None:
        print(value, flush=True)
        console_handle.write(value + "\n")
        console_handle.flush()

    started_at = utc_now()
    started_monotonic = time.monotonic()
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
            "Author evidence is not independent main acceptance or a public wire-format claim.",
            "Guard suites intentionally require the module's own exact time-zero fatal and one-error tally.",
            "The current Git HEAD is provenance, not a pass gate; attempt snapshots bind tested bytes.",
        ],
    }

    try:
        log_line(f"RUNNER_BEGIN operation={OPERATION_ID} attempt={args.attempt_id}")
        add_check(checks, "python-no-bytecode", sys.dont_write_bytecode, str(sys.dont_write_bytecode))
        add_check(checks, "output-under-author", out_dir.resolve().is_relative_to(EVIDENCE_ROOT.resolve()), str(out_dir.resolve()))

        tool_dir = resolve_tool_dir(args.tool_dir)
        tool_records: dict[str, dict] = {}
        for stem in ("vlib", "vlog", "vsim"):
            path = tool_path(tool_dir, stem)
            exists = path.is_file()
            add_check(checks, f"tool-exists-{stem}", exists, str(path))
            if exists:
                tool_records[stem] = {
                    "path": str(path.resolve()),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
        result["toolchain"] = tool_records
        if not checks_pass(checks):
            raise SetupError("required ModelSim executable missing")

        toolchain_dir = out_dir / "toolchain"
        toolchain_dir.mkdir()
        for stem in ("vlog", "vsim"):
            step_dir = toolchain_dir / f"{stem}-version"
            record = run_process([str(tool_path(tool_dir, stem)), "-version"], toolchain_dir, step_dir, 30)
            classify_process(record, checks, f"version-{stem}")
            version_text = combined_text(step_dir).strip()
            add_check(checks, f"version-{stem}-modeltech", "Model Technology" in version_text, version_text)
            add_check(checks, f"version-{stem}-10.7", "10.7" in version_text, version_text)
            tool_records[stem]["version_output"] = version_text

        result["contract"] = verify_contract(toolchain_dir, checks)
        result["scope"] = verify_scope(checks)

        author_hashes: dict[str, dict] = {}
        for key, relative in AUTHOR_FILES.items():
            path = full_path(relative)
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
            raise SetupError("contract or author file preflight failed")

        git_exe = shutil.which("git")
        result["git_context"] = {
            "available": False,
            "historical_base": BASE_HEAD,
            "role": "provenance_only_not_test_gate",
        }
        if git_exe:
            git_step = toolchain_dir / "git-head"
            git_record = run_process(
                [git_exe, "-C", str(PRODUCT_ROOT), "rev-parse", "HEAD"],
                PRODUCT_ROOT,
                git_step,
                30,
            )
            git_text = combined_text(git_step).strip()
            result["git_context"].update(
                available=git_record["returncode"] == 0 and re.fullmatch(r"[0-9a-f]{40}", git_text) is not None,
                observed_output=git_text,
                process=git_record,
            )

        for suite_name in selected:
            log_line(f"RUN_SUITE_BEGIN name={suite_name}")
            suite_result = execute_suite(suite_name, SUITES[suite_name], out_dir, tool_dir, args.timeout)
            result["suites"][suite_name] = suite_result
            log_line(
                f"RUN_SUITE_END name={suite_name} status={suite_result['status']} "
                f"failed_checks={suite_result.get('failed_checks', -1)}"
            )

        end_hashes = {}
        for key, relative in AUTHOR_FILES.items():
            path = full_path(relative)
            end_hashes[key] = sha256_file(path) if path.is_file() else None
        result["author_files_at_end"] = end_hashes
        add_check(
            checks,
            "author-files-unchanged-during-run",
            end_hashes == {key: value["sha256"] for key, value in author_hashes.items()},
            "",
        )
        if not checks_pass(checks):
            raise SetupError("author files changed during the run")
    except Exception:
        exception_text = traceback.format_exc()
        with (out_dir / "EXCEPTION.txt").open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(exception_text)
        add_check(checks, "runner-setup", False, exception_text.splitlines()[-1])
        log_line("RUNNER_EXCEPTION " + exception_text.splitlines()[-1])

    suites_ran = len(result["suites"]) == len(selected)
    suites_pass = all(item.get("status") == "pass" for item in result["suites"].values())
    result["status"] = "pass" if checks_pass(checks) and suites_ran and suites_pass else "fail"
    result["finished_at"] = utc_now()
    result["duration_s"] = round(time.monotonic() - started_monotonic, 3)
    result["selected_suites_ran"] = suites_ran
    result["failed_global_checks"] = sum(1 for item in checks if not item["pass"])
    write_json(out_dir / "result.json", result)
    log_line(f"RUNNER_RESULT status={result['status']} attempt={args.attempt_id}")
    console_handle.close()
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
