#!/usr/bin/env python3
"""Strict fail-closed ModelSim runner for deepeye_encoded_frame_queue.

Work: B-ENCODED-FRAME-QUEUE-RTL-20261022-20-v1
Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Operation: B-DEEPEYE-ENCODED-FRAME-QUEUE-20261022-20

The runner requires a fresh output directory inside the author evidence
directory.  Every compilation gets its own source snapshot and work library.
Raw stdout and stderr are preserved separately, together with argv, cwd, true
process exit status and timeout state.  Ordinary simulations must have exact
structured markers, every selected case must pass, and all check-count and
counter summaries must agree.  Guard simulations must emit exactly the
module's own fatal for STAT_W 0, 1 or 33, with no unrelated error or warning.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

OPERATION_ID = "B-DEEPEYE-ENCODED-FRAME-QUEUE-20261022-20"
TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
WORK_ID = "B-ENCODED-FRAME-QUEUE-RTL-20261022-20-v1"
BASELINE_HEAD = "aef19351f1836b23f9a714bc5626db4eb4df98c5"
MODEL = "deepseek-flash"
REASONING_EFFORT = "max"

TOOL_DIR_DEFAULT = Path(r"D:\modelsim1\win64")
PRODUCT_ROOT = Path(__file__).resolve().parents[4]
EVIDENCE_ROOT = (
    PRODUCT_ROOT
    / "competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20/author"
)

SOURCE_REL = {
    "queue": "competition/deepeye/fpga/stream/deepeye_encoded_frame_queue.sv",
    "tb": "competition/deepeye/tests/rtl/stream/tb_encoded_frame_queue.sv",
    "encoder": "competition/deepeye/fpga/codec/deepeye_block_encoder.sv",
    "stream": "competition/deepeye/fpga/stream/deepeye_block_stream.sv",
}

PINNED_HASHES = {
    "encoder": "870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5",
    "stream": "c8f8c0d99769efc64a91402ee23e7157368ff90ec765db5c413f02546715fff4",
}

MAIN_CASES = [
    "reset_idle",
    "single_success",
    "two_deep_stall",
    "no_same_edge_bypass",
    "full_old_level_no_credit",
    "framing_boundaries",
    "early_last_fault2",
    "missing_last_fault2",
    "invalid_framing_fault1",
    "upstream_error_forward",
    "fault_drains_older",
    "fault_event_single_pulse",
    "duplicate_aba_tags",
    "cancel_empty",
    "cancel_after_meta",
    "cancel_partial_payload",
    "cancel_sealed_output",
    "cancel_partial_output",
    "cancel_held_once",
    "reset_priority_over_cancel",
    "simultaneous_alloc_retire",
    "simultaneous_seal_retire",
    "pointer_wrap_many",
]

SMALL_CASES = ["saturation_statw2"]

COMPOSE_CASES = [
    "compose_two_raw_rice_stall",
    "compose_error_and_cancel",
    "compose_full_256",
]

MAIN_STATS = [
    "final_level",
    "final_stat_meta",
    "final_stat_in_bytes",
    "final_stat_retired",
    "final_stat_aborted",
    "final_stat_fault",
]
SMALL_STATS = [
    "final_stat_meta",
    "final_stat_in_bytes",
    "final_stat_retired",
    "final_stat_aborted",
    "final_stat_fault",
]
COMPOSE_STATS = [
    "final_queue_level",
    "final_queue_stat_meta",
    "final_queue_stat_in_bytes",
    "final_queue_stat_retired",
    "final_queue_stat_aborted",
    "final_queue_stat_fault",
]

SUITES = {
    "standalone": {
        "kind": "ordinary",
        "sources": ["queue", "tb"],
        "modules": ["deepeye_encoded_frame_queue", "tb_encoded_frame_queue"],
        "top": "tb_encoded_frame_queue",
        "tb_begin": "encoded_frame_queue",
        "cases": MAIN_CASES,
        "min_checks": 10000,
        "stats_keys": MAIN_STATS,
        "zero_stats": ["final_level"],
        "positive_stats": [
            "final_stat_meta",
            "final_stat_in_bytes",
            "final_stat_retired",
        ],
    },
    "small": {
        "kind": "ordinary",
        "sources": ["queue", "tb"],
        "modules": ["deepeye_encoded_frame_queue", "tb_encoded_frame_queue_small"],
        "top": "tb_encoded_frame_queue_small",
        "tb_begin": "encoded_frame_queue_small",
        "cases": SMALL_CASES,
        "min_checks": 190,
        "stats_keys": SMALL_STATS,
        "zero_stats": [],
        "positive_stats": [
            "final_stat_meta",
            "final_stat_in_bytes",
            "final_stat_aborted",
            "final_stat_fault",
        ],
    },
    "compose": {
        "kind": "ordinary",
        "sources": ["encoder", "stream", "queue", "tb"],
        "modules": [
            "deepeye_block_encoder",
            "deepeye_block_stream",
            "deepeye_encoded_frame_queue",
            "tb_encoded_frame_queue_compose",
        ],
        "top": "tb_encoded_frame_queue_compose",
        "tb_begin": "encoded_frame_queue_compose",
        "cases": COMPOSE_CASES,
        "min_checks": 1000,
        "stats_keys": COMPOSE_STATS,
        "zero_stats": ["final_queue_level"],
        "positive_stats": [
            "final_queue_stat_meta",
            "final_queue_stat_in_bytes",
            "final_queue_stat_retired",
        ],
    },
    "guard-0": {
        "kind": "guard",
        "sources": ["queue", "tb"],
        "modules": ["deepeye_encoded_frame_queue", "tb_encoded_frame_queue_guard"],
        "define": "0",
        "top": "tb_encoded_frame_queue_guard",
        "expected_fatal": "DEEPEYE_ENCODED_FRAME_QUEUE_INVALID_PARAM STAT_W=0",
    },
    "guard-1": {
        "kind": "guard",
        "sources": ["queue", "tb"],
        "modules": ["deepeye_encoded_frame_queue", "tb_encoded_frame_queue_guard"],
        "define": "1",
        "top": "tb_encoded_frame_queue_guard",
        "expected_fatal": "DEEPEYE_ENCODED_FRAME_QUEUE_INVALID_PARAM STAT_W=1",
    },
    "guard-33": {
        "kind": "guard",
        "sources": ["queue", "tb"],
        "modules": ["deepeye_encoded_frame_queue", "tb_encoded_frame_queue_guard"],
        "define": "33",
        "top": "tb_encoded_frame_queue_guard",
        "expected_fatal": "DEEPEYE_ENCODED_FRAME_QUEUE_INVALID_PARAM STAT_W=33",
    },
}

SUITE_ORDER = ["standalone", "small", "compose", "guard-0", "guard-1", "guard-33"]

TALLY_RE = re.compile(
    r"^[ \t]*#?[ \t]*Errors:[ \t]*(\d+),[ \t]*Warnings:[ \t]*(\d+)[ \t]*$", re.M
)
ERROR_RE = re.compile(r"^[ \t]*#?[ \t]*\*\*[ \t]*Error", re.M)
WARNING_RE = re.compile(r"^[ \t]*#?[ \t]*\*\*[ \t]*Warning", re.M)
FATAL_RE = re.compile(r"^[ \t]*#?[ \t]*\*\*[ \t]*Fatal:[ \t]*(.*?)[ \t]*$", re.M)
TB_BEGIN_RE = re.compile(r"^[ \t]*#?[ \t]*TB_BEGIN[ \t]+tb=([A-Za-z0-9_]+)[ \t]*$", re.M)
TB_END_RE = re.compile(r"^[ \t]*#?[ \t]*TB_END[ \t]+(pass|fail)[ \t]*$", re.M)
TB_SUMMARY_RE = re.compile(
    r"^[ \t]*#?[ \t]*TB_SUMMARY[ \t]+cases=(\d+)[ \t]+pass=(\d+)[ \t]+fail=(\d+)"
    r"[ \t]+checks=(\d+)[ \t]*$",
    re.M,
)
CASE_BEGIN_RE = re.compile(
    r"^[ \t]*#?[ \t]*CASE_BEGIN[ \t]+name=([A-Za-z0-9_]+)[ \t]*$", re.M
)
CASE_END_RE = re.compile(
    r"^[ \t]*#?[ \t]*CASE_END[ \t]+name=([A-Za-z0-9_]+)[ \t]+status=(pass|fail)"
    r"[ \t]+checks=(\d+)[ \t]*$",
    re.M,
)
TB_STAT_RE = re.compile(
    r"^[ \t]*#?[ \t]*TB_STAT[ \t]+([A-Za-z0-9_]+)=(\d+)[ \t]*$", re.M
)

CONSOLE_LINES: list[str] = []


class SetupError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log_line(text: str) -> None:
    CONSOLE_LINES.append(text)
    print(text, flush=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_raw(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def step_text(step_dir: Path) -> str:
    return read_raw(step_dir / "stdout.txt") + "\n" + read_raw(step_dir / "stderr.txt")


def add_check(checks: list[dict], name: str, ok: bool, detail: str = "") -> bool:
    checks.append({"name": name, "pass": bool(ok), "detail": detail})
    return bool(ok)


def local_pass(checks: list[dict], start: int) -> bool:
    return all(item["pass"] for item in checks[start:])


def strict_log_lines(text: str, spec: dict, kind: str) -> list[str]:
    """Reject diagnostic/record lines that the structured parsers cannot account for."""
    bad = []
    records = (TB_BEGIN_RE, TB_END_RE, TB_SUMMARY_RE, CASE_BEGIN_RE, CASE_END_RE, TB_STAT_RE)
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            line = line[1:].strip()
        if re.search(r"\b(?:errors?|fatal|warnings?)\b", line, re.I | re.ASCII):
            tally = re.fullmatch(r"Errors: (0|[1-9][0-9]*), Warnings: (0|[1-9][0-9]*)", line)
            own_fatal = kind == "guard" and line == "** Fatal: " + spec["expected_fatal"]
            if not tally and not own_fatal:
                bad.append(line)
        if re.match(r"(?:TB_BEGIN|TB_END|TB_SUMMARY|TB_STAT|CASE_BEGIN|CASE_END)\b", line, re.I | re.ASCII):
            if kind != "ordinary" or not line.isascii() or not any(pattern.fullmatch(line) for pattern in records):
                bad.append(line)
    return bad


def run_process(
    argv: list[str], cwd: Path, step_dir: Path, timeout_s: int
) -> dict:
    step_dir.mkdir(parents=False, exist_ok=False)
    started_at = utc_now()
    write_json(
        step_dir / "command.json",
        {
            "argv": [str(item) for item in argv],
            "cwd": str(cwd),
            "timeout_s": timeout_s,
            "started_at": started_at,
        },
    )
    stdout_path = step_dir / "stdout.txt"
    stderr_path = step_dir / "stderr.txt"
    stdout_path.write_bytes(b"")
    stderr_path.write_bytes(b"")
    start = time.monotonic()
    returncode = None
    timed_out = False
    spawn_error = None
    try:
        with stdout_path.open("wb") as stdout_handle, stderr_path.open(
            "wb"
        ) as stderr_handle:
            try:
                process = subprocess.Popen(
                    [str(item) for item in argv],
                    cwd=str(cwd),
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
    except OSError as exc:
        spawn_error = f"{type(exc).__name__}: {exc}"
    duration_s = round(time.monotonic() - start, 3)
    record = {
        "argv": [str(item) for item in argv],
        "cwd": str(cwd),
        "started_at": started_at,
        "finished_at": utc_now(),
        "duration_s": duration_s,
        "timeout_s": timeout_s,
        "timed_out": timed_out,
        "returncode": returncode,
        "spawn_error": spawn_error,
    }
    write_json(step_dir / "process.json", record)
    return record


def classify_process(
    record: dict, checks: list[dict], prefix: str, expected_exit: int = 0
) -> None:
    add_check(
        checks,
        f"{prefix}-spawn",
        record["spawn_error"] is None,
        str(record["spawn_error"]),
    )
    add_check(checks, f"{prefix}-timeout", not record["timed_out"], "")
    add_check(
        checks,
        f"{prefix}-exit",
        record["returncode"] == expected_exit,
        f"returncode={record['returncode']} expected={expected_exit}",
    )


def classify_compile(
    text: str, spec: dict, checks: list[dict], prefix: str
) -> bool:
    start = len(checks)
    invalid = strict_log_lines(text, spec, "compile")
    add_check(checks, f"{prefix}-strict-lines", not invalid, repr(invalid))
    tally = TALLY_RE.findall(text)
    add_check(
        checks,
        f"{prefix}-tally-unique",
        len(tally) == 1,
        f"count={len(tally)} values={tally}",
    )
    if len(tally) == 1:
        add_check(
            checks,
            f"{prefix}-tally-zero",
            tally[0] == ("0", "0"),
            f"values={tally[0]}",
        )
    add_check(
        checks,
        f"{prefix}-no-error",
        ERROR_RE.search(text) is None and "Error loading design" not in text,
        "",
    )
    add_check(
        checks,
        f"{prefix}-no-warning",
        WARNING_RE.search(text) is None,
        "",
    )
    top = spec["top"]
    add_check(
        checks,
        f"{prefix}-top-present",
        re.search(r"^[ \t]*" + re.escape(top) + r"[ \t]*$", text, re.M) is not None,
        f"top={top}",
    )
    missing = [name for name in spec["modules"] if f"-- Compiling module {name}" not in text]
    add_check(
        checks,
        f"{prefix}-modules",
        not missing,
        f"missing={missing}",
    )
    return local_pass(checks, start)


def classify_ordinary(
    text: str, spec: dict, checks: list[dict], prefix: str
) -> dict:
    start = len(checks)
    invalid = strict_log_lines(text, spec, "ordinary")
    add_check(checks, f"{prefix}-strict-lines", not invalid, repr(invalid))
    tally = TALLY_RE.findall(text)
    add_check(
        checks,
        f"{prefix}-tally-unique",
        len(tally) == 1,
        f"count={len(tally)} values={tally}",
    )
    if len(tally) == 1:
        add_check(
            checks,
            f"{prefix}-tally-zero",
            tally[0] == ("0", "0"),
            f"values={tally[0]}",
        )
    add_check(
        checks,
        f"{prefix}-no-error",
        ERROR_RE.search(text) is None and "Error loading design" not in text,
        "",
    )
    add_check(
        checks,
        f"{prefix}-no-warning",
        WARNING_RE.search(text) is None,
        "",
    )
    add_check(
        checks,
        f"{prefix}-no-fatal",
        FATAL_RE.search(text) is None,
        "",
    )
    add_check(
        checks,
        f"{prefix}-no-check-fail-marker",
        "TB_CHECK_FAIL" not in text,
        "",
    )

    begins = TB_BEGIN_RE.findall(text)
    add_check(
        checks,
        f"{prefix}-tb-begin-unique",
        begins == [spec["tb_begin"]],
        f"values={begins} expected={spec['tb_begin']}",
    )
    ends = TB_END_RE.findall(text)
    add_check(
        checks,
        f"{prefix}-tb-end-pass",
        ends == ["pass"],
        f"values={ends}",
    )

    summary = TB_SUMMARY_RE.findall(text)
    add_check(
        checks,
        f"{prefix}-summary-unique",
        len(summary) == 1,
        f"count={len(summary)} values={summary}",
    )
    summary_values = None
    if len(summary) == 1:
        summary_values = tuple(int(value) for value in summary[0])
        cases, passed, failed, summary_checks = summary_values
        add_check(
            checks,
            f"{prefix}-summary-counts",
            cases == len(spec["cases"]) and passed == cases and failed == 0,
            f"summary={summary_values} expected_cases={len(spec['cases'])}",
        )
        add_check(
            checks,
            f"{prefix}-summary-min-checks",
            summary_checks >= spec["min_checks"],
            f"checks={summary_checks} minimum={spec['min_checks']}",
        )

    case_begins = CASE_BEGIN_RE.findall(text)
    case_ends = CASE_END_RE.findall(text)
    add_check(
        checks,
        f"{prefix}-case-begin-sequence",
        case_begins == spec["cases"],
        f"begins={case_begins} expected={spec['cases']}",
    )
    add_check(
        checks,
        f"{prefix}-case-end-sequence",
        [item[0] for item in case_ends] == spec["cases"],
        f"ends={[item[0] for item in case_ends]}",
    )
    add_check(
        checks,
        f"{prefix}-case-all-pass",
        all(item[1] == "pass" for item in case_ends),
        f"statuses={[item[1] for item in case_ends]}",
    )
    case_checks = {item[0]: int(item[2]) for item in case_ends}
    add_check(
        checks,
        f"{prefix}-case-checks-positive",
        bool(case_checks) and all(value > 0 for value in case_checks.values()),
        f"case_checks={case_checks}",
    )
    if summary_values is not None:
        add_check(
            checks,
            f"{prefix}-case-check-sum",
            sum(case_checks.values()) == summary_values[3],
            f"sum={sum(case_checks.values())} summary={summary_values[3]}",
        )

    pairs = TB_STAT_RE.findall(text)
    names = [item[0] for item in pairs]
    add_check(
        checks,
        f"{prefix}-stat-unique",
        len(names) == len(set(names)),
        f"names={names}",
    )
    stats = {item[0]: int(item[1]) for item in pairs}
    expected_stats = {"cases", "checks", "failures", *spec["stats_keys"]}
    add_check(
        checks,
        f"{prefix}-stat-complete",
        set(stats) == expected_stats,
        f"actual={sorted(stats)} expected={sorted(expected_stats)}",
    )
    if set(stats) == expected_stats:
        add_check(
            checks,
            f"{prefix}-stat-failures-zero",
            stats["failures"] == 0,
            f"failures={stats['failures']}",
        )
        if summary_values is not None:
            add_check(
                checks,
                f"{prefix}-stat-cases-match",
                stats["cases"] == summary_values[0],
                f"stat_cases={stats['cases']} summary_cases={summary_values[0]}",
            )
            add_check(
                checks,
                f"{prefix}-stat-checks-match",
                stats["checks"] == summary_values[3],
                f"stat_checks={stats['checks']} summary_checks={summary_values[3]}",
            )
        for key in spec["zero_stats"]:
            add_check(
                checks,
                f"{prefix}-stat-zero-{key}",
                stats.get(key) == 0,
                f"{key}={stats.get(key)}",
            )
        add_check(
            checks,
            f"{prefix}-stat-positive",
            any(stats.get(key, 0) > 0 for key in spec["positive_stats"]),
            f"positive_keys={spec['positive_stats']} values={stats}",
        )

    return {
        "summary": summary_values,
        "case_checks": case_checks,
        "stats": stats,
        "classification_pass": local_pass(checks, start),
    }


def classify_guard(
    text: str, spec: dict, checks: list[dict], prefix: str
) -> dict:
    start = len(checks)
    invalid = strict_log_lines(text, spec, "guard")
    add_check(checks, f"{prefix}-strict-lines", not invalid, repr(invalid))
    fatal = FATAL_RE.findall(text)
    add_check(
        checks,
        f"{prefix}-fatal-unique",
        len(fatal) == 1,
        f"count={len(fatal)} values={fatal}",
    )
    if len(fatal) == 1:
        add_check(
            checks,
            f"{prefix}-fatal-exact",
            fatal[0] == spec["expected_fatal"],
            f"actual={fatal[0]!r} expected={spec['expected_fatal']!r}",
        )
    tally = TALLY_RE.findall(text)
    add_check(
        checks,
        f"{prefix}-tally-unique",
        len(tally) == 1,
        f"count={len(tally)} values={tally}",
    )
    if len(tally) == 1:
        add_check(
            checks,
            f"{prefix}-tally-guard",
            tally[0] == ("1", "0"),
            f"values={tally[0]} expected=(1, 0)",
        )
    add_check(
        checks,
        f"{prefix}-no-unrelated-error",
        ERROR_RE.search(text) is None and "Error loading design" not in text,
        "",
    )
    add_check(
        checks,
        f"{prefix}-no-warning",
        WARNING_RE.search(text) is None,
        "",
    )
    add_check(
        checks,
        f"{prefix}-no-unexpected-no-fatal",
        "GUARD_TB_UNEXPECTED_NO_FATAL" not in text,
        "",
    )
    add_check(
        checks,
        f"{prefix}-no-pass-claim",
        ("TB_END" not in text)
        and ("TB_SUMMARY" not in text)
        and ("CASE_END" not in text),
        "",
    )
    return {
        "fatal": fatal,
        "tally": tally,
        "classification_pass": local_pass(checks, start),
    }


def snapshot_sources(
    suite_dir: Path, keys: list[str], checks: list[dict], prefix: str
) -> list[dict]:
    snapshot_dir = suite_dir / "sources"
    snapshot_dir.mkdir(parents=False, exist_ok=False)
    records = []
    for key in keys:
        rel = SOURCE_REL[key]
        source = PRODUCT_ROOT / rel
        if not source.is_file():
            raise SetupError(f"missing source: {source}")
        original_hash = sha256_file(source)
        destination = snapshot_dir / source.name
        shutil.copyfile(source, destination)
        copied_hash = sha256_file(destination)
        add_check(
            checks,
            f"{prefix}-snapshot-{key}-hash",
            original_hash == copied_hash,
            f"source={source} snapshot={destination}",
        )
        records.append(
            {
                "key": key,
                "source_path": str(source),
                "snapshot_path": str(destination),
                "sha256": copied_hash,
                "bytes": destination.stat().st_size,
                "source_mtime_ns": source.stat().st_mtime_ns,
            }
        )
    write_json(
        suite_dir / "source_snapshot.json",
        {"sources": records, "at_utc": utc_now()},
    )
    return records


def execute_suite(
    name: str, spec: dict, out_dir: Path, tool_dir: Path, timeout_s: int
) -> dict:
    suite_dir = out_dir / name
    suite_dir.mkdir(parents=False, exist_ok=False)
    steps_dir = suite_dir / "steps"
    steps_dir.mkdir(parents=False, exist_ok=False)
    checks: list[dict] = []
    info: dict = {
        "suite": name,
        "kind": spec["kind"],
        "status": "fail",
        "checks": checks,
        "started_at": utc_now(),
    }
    try:
        snapshots = snapshot_sources(suite_dir, spec["sources"], checks, "source")
        info["source_snapshot"] = snapshots

        vlib = run_process(
            [str(tool_dir / "vlib.exe"), "work"], suite_dir, steps_dir / "01-vlib", timeout_s
        )
        info["vlib"] = vlib
        classify_process(vlib, checks, "vlib", expected_exit=0)
        add_check(
            checks,
            "vlib-work-directory",
            (suite_dir / "work").is_dir(),
            str(suite_dir / "work"),
        )
        if not all(item["pass"] for item in checks):
            info["status"] = "fail"
            return info

        vlog_argv = [str(tool_dir / "vlog.exe"), "-sv", "-work", "work"]
        if "define" in spec:
            vlog_argv.append(f"+define+GUARD_W={spec['define']}")
        vlog_argv.extend(f"sources/{Path(SOURCE_REL[key]).name}" for key in spec["sources"])
        vlog = run_process(vlog_argv, suite_dir, steps_dir / "02-vlog", timeout_s)
        info["vlog"] = vlog
        classify_process(vlog, checks, "vlog", expected_exit=0)
        compile_ok = classify_compile(step_text(steps_dir / "02-vlog"), spec, checks, "compile")
        info["compile_pass"] = compile_ok
        if not compile_ok:
            info["status"] = "fail"
            return info

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
        info["vsim"] = vsim
        classify_process(vsim, checks, "vsim", expected_exit=0)
        text = step_text(steps_dir / "03-vsim")
        if spec["kind"] == "ordinary":
            info["run"] = classify_ordinary(text, spec, checks, "run")
        else:
            info["run"] = classify_guard(text, spec, checks, "guard")
        info["status"] = "pass" if all(item["pass"] for item in checks) else "fail"
        return info
    except Exception:
        exception_text = traceback.format_exc()
        (suite_dir / "EXCEPTION.txt").write_text(exception_text, encoding="utf-8")
        add_check(checks, "suite-exception", False, exception_text.splitlines()[-1])
        info["exception"] = exception_text
        info["status"] = "fail"
        return info
    finally:
        info["finished_at"] = utc_now()


def collect_artifact_hashes(out_dir: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {"ARTIFACTS.json", "RUN_RESULT.json"}:
            continue
        hashes[path.relative_to(out_dir).as_posix()] = sha256_file(path)
    return hashes


def finalize(out_dir: Path, result: dict) -> int:
    result["finished_at"] = utc_now()
    (out_dir / "CONSOLE.txt").write_text(
        "\n".join(CONSOLE_LINES) + ("\n" if CONSOLE_LINES else ""), encoding="utf-8"
    )
    hashes = collect_artifact_hashes(out_dir)
    write_json(
        out_dir / "ARTIFACTS.json",
        {
            "schema": 1,
            "at_utc": utc_now(),
            "artifact_count": len(hashes),
            "artifacts": hashes,
        },
    )
    result["artifact_manifest"] = "ARTIFACTS.json"
    result["artifact_manifest_sha256"] = sha256_file(out_dir / "ARTIFACTS.json")
    result["artifact_count"] = len(hashes)
    result["artifact_hashes"] = hashes
    write_json(out_dir / "RUN_RESULT.json", result)
    log_line(
        "RUNNER_RESULT status=%s suites=%d checks_failed=%d artifacts=%d"
        % (
            result["status"],
            len(result.get("suites", {})),
            result.get("checks_failed", 0),
            len(hashes),
        )
    )
    print("RUN_RESULT=" + str(out_dir / "RUN_RESULT.json"), flush=True)
    if result["status"] == "pass":
        return 0
    return 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="fresh output directory")
    parser.add_argument(
        "--suite",
        action="append",
        choices=SUITE_ORDER,
        default=None,
        help="suite to run; repeatable (default: all)",
    )
    parser.add_argument("--tool-dir", default=str(TOOL_DIR_DEFAULT))
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    selected = args.suite if args.suite else SUITE_ORDER
    if len(selected) != len(set(selected)):
        parser.error("duplicate --suite values")
    args.suites = [name for name in SUITE_ORDER if name in set(selected)]
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out).expanduser().resolve()
    evidence_root = EVIDENCE_ROOT.resolve()
    if out_dir.exists():
        print(f"ERROR: output already exists: {out_dir}", file=sys.stderr)
        return 2
    if out_dir == evidence_root or not out_dir.is_relative_to(evidence_root):
        print(
            f"ERROR: output must be a fresh directory below {evidence_root}",
            file=sys.stderr,
        )
        return 2
    try:
        out_dir.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(f"ERROR: cannot create output: {exc}", file=sys.stderr)
        return 2

    started = time.monotonic()
    write_json(
        out_dir / "RUN_INVOCATION.json",
        {
            "schema": 1,
            "operation_id": OPERATION_ID,
            "task_id": TASK_ID,
            "task_version": TASK_VERSION,
            "work_id": WORK_ID,
            "model": MODEL,
            "reasoning_effort": REASONING_EFFORT,
            "argv": sys.argv,
            "cwd": str(Path.cwd()),
            "python": sys.version,
            "platform": platform.platform(),
            "product_root": str(PRODUCT_ROOT),
            "evidence_root": str(evidence_root),
            "out_dir": str(out_dir),
            "suite_order": args.suites,
            "started_at": utc_now(),
        },
    )

    global_checks: list[dict] = []
    result: dict = {
        "schema": 1,
        "status": "fail",
        "operation_id": OPERATION_ID,
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "work_id": WORK_ID,
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "product_root": str(PRODUCT_ROOT),
        "out_dir": str(out_dir),
        "baseline_head": BASELINE_HEAD,
        "started_at": utc_now(),
        "global_checks": global_checks,
        "suites": {},
        "limits": [
            "RTL simulation only; no synthesis, implementation, timing or board result.",
            "Author-directed tests are not independent main acceptance.",
            "All29/G05/B06/R03/board/system remain not_run.",
        ],
    }

    try:
        setup_dir = out_dir / "setup"
        setup_dir.mkdir(parents=False, exist_ok=False)
        for key in ["queue", "tb", "encoder", "stream"]:
            source = PRODUCT_ROOT / SOURCE_REL[key]
            add_check(
                global_checks,
                f"source-exists-{key}",
                source.is_file(),
                str(source),
            )
        if not all(item["pass"] for item in global_checks):
            raise SetupError("required source file missing")

        source_manifest = {}
        for key, rel in SOURCE_REL.items():
            source = PRODUCT_ROOT / rel
            source_manifest[key] = {
                "path": str(source),
                "sha256": sha256_file(source),
                "bytes": source.stat().st_size,
            }
        write_json(out_dir / "source_manifest.json", source_manifest)

        pinned = {}
        for key, expected in PINNED_HASHES.items():
            actual = source_manifest[key]["sha256"]
            pinned[key] = {"expected": expected, "actual": actual}
            add_check(
                global_checks,
                f"pinned-hash-{key}",
                actual == expected,
                f"actual={actual} expected={expected}",
            )
        write_json(out_dir / "pinned_hashes.json", pinned)

        git_head = run_process(
            ["git", "rev-parse", "HEAD"], PRODUCT_ROOT, setup_dir / "git-head", 30
        )
        git_head_text = read_raw(setup_dir / "git-head" / "stdout.txt").strip()
        add_check(
            global_checks,
            "git-head-process",
            git_head["returncode"] == 0 and not git_head["timed_out"],
            f"returncode={git_head['returncode']}",
        )
        add_check(
            global_checks,
            "git-head-baseline",
            git_head_text == BASELINE_HEAD,
            f"actual={git_head_text} expected={BASELINE_HEAD}",
        )
        result["actual_head"] = git_head_text
        run_process(
            ["git", "status", "--porcelain"],
            PRODUCT_ROOT,
            setup_dir / "git-status",
            30,
        )

        queue_text = read_raw(PRODUCT_ROOT / SOURCE_REL["queue"])
        exact_fatal = (
            '$fatal(1, "DEEPEYE_ENCODED_FRAME_QUEUE_INVALID_PARAM STAT_W=%0d", STAT_W);'
        )
        fatal_index = queue_text.find(exact_fatal)
        off_index = queue_text.rfind("// synthesis translate_off", 0, max(fatal_index, 0))
        on_index = queue_text.find("// synthesis translate_on", max(fatal_index, 0))
        add_check(
            global_checks,
            "guard-static-exact-fatal",
            fatal_index >= 0,
            exact_fatal,
        )
        add_check(
            global_checks,
            "guard-static-translate-off",
            fatal_index >= 0 and off_index >= 0 and off_index < fatal_index,
            f"off_index={off_index} fatal_index={fatal_index}",
        )
        add_check(
            global_checks,
            "guard-static-translate-on",
            fatal_index >= 0 and on_index > fatal_index,
            f"fatal_index={fatal_index} on_index={on_index}",
        )

        tool_dir = Path(args.tool_dir).expanduser().resolve()
        for exe_name in ["vlib.exe", "vlog.exe", "vsim.exe"]:
            add_check(
                global_checks,
                f"tool-exists-{exe_name}",
                (tool_dir / exe_name).is_file(),
                str(tool_dir / exe_name),
            )
        if not all(item["pass"] for item in global_checks):
            raise SetupError("global setup check failed")

        toolchain_dir = out_dir / "toolchain"
        toolchain_dir.mkdir(parents=False, exist_ok=False)
        version_records = {}
        for exe_name in ["vlog.exe", "vsim.exe"]:
            record = run_process(
                [str(tool_dir / exe_name), "-version"],
                out_dir,
                toolchain_dir / f"{exe_name}-version",
                30,
            )
            version_records[exe_name] = record
            version_text = step_text(toolchain_dir / f"{exe_name}-version")
            add_check(
                global_checks,
                f"tool-version-{exe_name}",
                record["returncode"] == 0
                and not record["timed_out"]
                and "Model Technology" in version_text,
                version_text.strip(),
            )
        write_json(out_dir / "toolchain.json", version_records)
        if not all(item["pass"] for item in global_checks):
            raise SetupError("toolchain version check failed")

        for suite_name in args.suites:
            log_line(f"RUN_SUITE_BEGIN name={suite_name}")
            suite_result = execute_suite(
                suite_name,
                SUITES[suite_name],
                out_dir,
                tool_dir,
                args.timeout,
            )
            result["suites"][suite_name] = suite_result
            log_line(
                "RUN_SUITE_END name=%s status=%s failed_checks=%d"
                % (
                    suite_name,
                    suite_result["status"],
                    sum(1 for item in suite_result["checks"] if not item["pass"]),
                )
            )

        all_checks = list(global_checks)
        for suite_result in result["suites"].values():
            all_checks.extend(suite_result["checks"])
        result["checks_run"] = len(all_checks)
        result["checks_failed"] = sum(1 for item in all_checks if not item["pass"])
        suites_pass = all(
            suite["status"] == "pass" for suite in result["suites"].values()
        )
        result["status"] = (
            "pass"
            if suites_pass
            and all(item["pass"] for item in global_checks)
            and len(result["suites"]) == len(args.suites)
            else "fail"
        )
        result["elapsed_s"] = round(time.monotonic() - started, 3)
        return finalize(out_dir, result)
    except Exception:
        exception_text = traceback.format_exc()
        (out_dir / "EXCEPTION.txt").write_text(exception_text, encoding="utf-8")
        add_check(global_checks, "runner-exception", False, exception_text.splitlines()[-1])
        result["exception"] = exception_text
        result["checks_run"] = len(global_checks)
        result["checks_failed"] = sum(1 for item in global_checks if not item["pass"])
        result["elapsed_s"] = round(time.monotonic() - started, 3)
        return finalize(out_dir, result)


if __name__ == "__main__":
    sys.exit(main())
