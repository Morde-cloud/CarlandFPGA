#!/usr/bin/env python3
"""Strict standalone author runner for the operation-25 UART receiver."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path


PRODUCT_ROOT = Path(__file__).resolve().parents[2]
RTL_SOURCE = PRODUCT_ROOT / "fpga/transport/deepeye_uart_rx.sv"
TB_SOURCE = PRODUCT_ROOT / "tests/rtl/transport/tb_uart_rx.sv"
EVIDENCE_ROOT = (
    PRODUCT_ROOT / "evidence/transport/uart-rx-20261023-25/author"
)

STAT_KEYS = (
    "frames",
    "retired",
    "overruns",
    "framing",
    "false_starts",
    "aborted",
)
STAT_ROW = re.compile(r"TB_STAT ([a-z_]+)=([0-9]+)")
CASE_BEGIN = re.compile(r"CASE_BEGIN name=([a-z0-9_]+)")
CASE_END = re.compile(
    r"CASE_END name=([a-z0-9_]+) status=(pass|fail) checks=([0-9]+)"
)
SUMMARY_ROW = re.compile(
    r"TB_SUMMARY cases=([0-9]+) pass=([0-9]+) fail=([0-9]+) "
    r"checks=([0-9]+)"
)
BEGIN_ROW = re.compile(r"TB_BEGIN tb=([a-z0-9_]+)")
END_PASS = "TB_END pass"


def suite(top, cases, stats, min_checks, guard=None, defines=()):
    return {
        "top": top,
        "cases": list(cases),
        "stats": list(stats),
        "min_checks": min_checks,
        "guard": guard,
        "defines": list(defines),
    }


ALL_CASES = ["reset_idle", "all_byte_values", "bad_stop_recovery"]
SUITES = {
    "all_160_10": suite(
        "tb_uart_rx_all_160_10", ALL_CASES, [257, 257, 0, 1, 0, 0], 45964
    ),
    "all_1000_53": suite(
        "tb_uart_rx_all_1000_53", ALL_CASES, [257, 257, 0, 1, 0, 0], 45964
    ),
    "all_97_5": suite(
        "tb_uart_rx_all_97_5", ALL_CASES, [257, 257, 0, 1, 0, 0], 45964
    ),
    "protocol": suite(
        "tb_uart_rx_protocol",
        [
            "reset_idle",
            "qualified_idle",
            "false_start",
            "bad_stop_long_low",
            "bad_stop_retire_collision",
            "back_to_back",
            "back_to_back_immediate_stop",
            "output_stall_overrun_refill",
            "error_preserves_pending",
        ],
        [1, 1, 0, 1, 0, 0],
        4064,
    ),
    "abort": suite(
        "tb_uart_rx_abort",
        [
            "reset_idle",
            "cancel_each_phase_pending",
            "reset_each_phase_pending",
            "idle_cancel_slot",
            "terminal_cancel_with_ready",
            "reset_over_cancel_pending",
            "held_abort_pending",
        ],
        [1, 0, 0, 0, 0, 2],
        14175,
    ),
    "stat_w2_min": suite(
        "tb_uart_rx_stat_w2_min", ["reset_idle", "saturation"], [3, 3, 3, 3, 3, 3], 2874
    ),
    "default_9600": suite(
        "tb_uart_rx_default_9600", ["reset_idle", "default_frames"], [2, 2, 0, 0, 0, 0], 390
    ),
    "baud_300": suite(
        "tb_uart_rx_baud_300", ["reset_idle", "baud300_frame"], [1, 1, 0, 0, 0, 0], 212
    ),
    "baud_1200": suite(
        "tb_uart_rx_baud_1200", ["reset_idle", "baud1200_frames"], [2, 2, 0, 0, 0, 0], 390
    ),
    "guard_clock15": suite(
        "tb_uart_rx_guard",
        [],
        [],
        0,
        guard="CLOCK_HZ",
        defines=("G_CLOCK=15", "G_BAUD=1", "G_STAT_W=32"),
    ),
    "guard_baud0": suite(
        "tb_uart_rx_guard",
        [],
        [],
        0,
        guard="BAUD",
        defines=("G_CLOCK=160", "G_BAUD=0", "G_STAT_W=32"),
    ),
    "guard_baud_high": suite(
        "tb_uart_rx_guard",
        [],
        [],
        0,
        guard="BAUD",
        defines=("G_CLOCK=160", "G_BAUD=11", "G_STAT_W=32"),
    ),
    "guard_stat1": suite(
        "tb_uart_rx_guard",
        [],
        [],
        0,
        guard="STAT_W",
        defines=("G_CLOCK=160", "G_BAUD=10", "G_STAT_W=1"),
    ),
    "guard_stat33": suite(
        "tb_uart_rx_guard",
        [],
        [],
        0,
        guard="STAT_W",
        defines=("G_CLOCK=160", "G_BAUD=10", "G_STAT_W=33"),
    ),
    "guard_priority": suite(
        "tb_uart_rx_guard",
        [],
        [],
        0,
        guard="CLOCK_HZ",
        defines=("G_CLOCK=15", "G_BAUD=0", "G_STAT_W=1"),
    ),
}


def sha256_path(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def normalized_lines(raw):
    text = raw.decode("utf-8", errors="replace")
    result = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            stripped = stripped[2:]
        elif stripped.startswith("#"):
            stripped = stripped[1:].lstrip()
        result.append(stripped)
    return result


def command_record_key(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def command_metadata(record):
    return {
        key: value
        for key, value in record.items()
        if key not in ("stdout_bytes", "stderr_bytes")
    }


def run_command(attempt, name, argv, cwd, env, timeout):
    record_dir = attempt / "commands" / command_record_key(name)
    record_dir.mkdir(parents=True, exist_ok=False)
    stdout_path = record_dir / "stdout.bin"
    stderr_path = record_dir / "stderr.bin"
    write_json(
        record_dir / "argv.json",
        {"argv": [str(item) for item in argv], "cwd": str(cwd)},
    )
    (record_dir / "cwd.txt").write_text(str(cwd) + "\n", encoding="utf-8", newline="\n")

    started = time.monotonic()
    timed_out = False
    process_error = None
    exit_code = None
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
            process = subprocess.Popen(
                [str(item) for item in argv],
                cwd=str(cwd),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                creationflags=creationflags,
            )
            try:
                exit_code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                process.wait()
    except OSError as error:
        process_error = f"{type(error).__name__}: {error}"
        stdout_path.touch(exist_ok=True)
        stderr_path.touch(exist_ok=True)

    duration = time.monotonic() - started
    (record_dir / "exit.txt").write_text(
        "timeout\n" if timed_out else f"{exit_code}\n", encoding="ascii", newline="\n"
    )
    (record_dir / "timeout.txt").write_text(
        ("true\n" if timed_out else "false\n"), encoding="ascii", newline="\n"
    )
    stdout_bytes = stdout_path.read_bytes()
    stderr_bytes = stderr_path.read_bytes()
    record = {
        "name": name,
        "argv": [str(item) for item in argv],
        "cwd": str(cwd),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 6),
        "process_error": process_error,
        "stdout": str(stdout_path),
        "stdout_sha256": hashlib.sha256(stdout_bytes).hexdigest(),
        "stderr": str(stderr_path),
        "stderr_sha256": hashlib.sha256(stderr_bytes).hexdigest(),
    }
    write_json(record_dir / "command.json", record)
    record["stdout_bytes"] = stdout_bytes
    record["stderr_bytes"] = stderr_bytes
    return record


def ordinary_output_problems(lines):
    problems = []
    for line in lines:
        if line.startswith("** Error") or line.startswith("** Warning"):
            problems.append(f"ModelSim diagnostic: {line}")
        if line.startswith("** Fatal"):
            problems.append(f"unexpected fatal: {line}")
        if line.startswith("Error:") or line.startswith("Warning:"):
            problems.append(f"tool diagnostic: {line}")
        for label, pattern in (
            ("errors", r"\bErrors:\s*([0-9]+)"),
            ("warnings", r"\bWarnings:\s*([0-9]+)"),
        ):
            match = re.search(pattern, line)
            if match and int(match.group(1)) != 0:
                problems.append(f"nonzero {label} tally: {line}")
    return problems


def parse_normal(name, spec, result, log_bytes):
    lines = normalized_lines(log_bytes)
    problems = ordinary_output_problems(lines)
    structured = [
        line
        for line in lines
        if line.startswith("TB_") or line.startswith("CASE_") or line.startswith("CHECK_")
    ]

    begin_rows = [line for line in structured if BEGIN_ROW.fullmatch(line)]
    if len(begin_rows) != 1:
        problems.append(f"TB_BEGIN count={len(begin_rows)}")
    elif BEGIN_ROW.fullmatch(begin_rows[0]).group(1) != spec["top"]:
        problems.append(f"TB_BEGIN tb mismatch: {begin_rows[0]}")

    end_rows = [line for line in structured if line == END_PASS]
    end_fail_rows = [line for line in structured if line == "TB_END fail"]
    if len(end_rows) != 1 or end_fail_rows:
        problems.append(f"TB_END pass count={len(end_rows)} fail_count={len(end_fail_rows)}")

    case_begin_rows = [line for line in structured if line.startswith("CASE_BEGIN")]
    case_end_rows = [line for line in structured if line.startswith("CASE_END")]
    begin_names = []
    end_names = []
    for line in case_begin_rows:
        match = CASE_BEGIN.fullmatch(line)
        if not match:
            problems.append(f"ambiguous CASE_BEGIN: {line}")
        else:
            begin_names.append(match.group(1))
    for line in case_end_rows:
        match = CASE_END.fullmatch(line)
        if not match:
            problems.append(f"ambiguous CASE_END: {line}")
        else:
            end_names.append(match.group(1))
            if match.group(2) != "pass" or int(match.group(3)) == 0:
                problems.append(f"failed or empty CASE_END: {line}")
    if begin_names != spec["cases"]:
        problems.append(f"CASE_BEGIN sequence={begin_names}")
    if end_names != spec["cases"]:
        problems.append(f"CASE_END sequence={end_names}")
    case_index = 0
    case_active = False
    for line in structured:
        begin_match = CASE_BEGIN.fullmatch(line)
        end_match = CASE_END.fullmatch(line)
        if begin_match:
            if case_active or case_index >= len(spec["cases"]):
                problems.append(f"misaligned CASE_BEGIN: {line}")
            elif begin_match.group(1) != spec["cases"][case_index]:
                problems.append(f"unexpected CASE_BEGIN: {line}")
            case_active = True
        elif end_match:
            if not case_active or case_index >= len(spec["cases"]):
                problems.append(f"misaligned CASE_END: {line}")
            elif end_match.group(1) != spec["cases"][case_index]:
                problems.append(f"unexpected CASE_END: {line}")
            case_active = False
            case_index += 1
    if case_active or case_index != len(spec["cases"]):
        problems.append("unclosed CASE scope")

    stat_rows = []
    for line in structured:
        if line.startswith("TB_STAT"):
            match = STAT_ROW.fullmatch(line)
            if not match:
                problems.append(f"ambiguous TB_STAT: {line}")
            else:
                stat_rows.append((match.group(1), int(match.group(2))))
    if [key for key, _ in stat_rows] != list(STAT_KEYS):
        problems.append(f"TB_STAT keys={[key for key, _ in stat_rows]}")
    actual_stats = [value for _, value in stat_rows]
    if actual_stats != spec["stats"]:
        problems.append(f"TB_STAT values={actual_stats} expected={spec['stats']}")

    summary_rows = [line for line in structured if line.startswith("TB_SUMMARY")]
    if len(summary_rows) != 1:
        problems.append(f"TB_SUMMARY count={len(summary_rows)}")
        summary = None
    else:
        match = SUMMARY_ROW.fullmatch(summary_rows[0])
        if not match:
            problems.append(f"ambiguous TB_SUMMARY: {summary_rows[0]}")
            summary = None
        else:
            summary = tuple(int(value) for value in match.groups())
            cases, passed, failed, checks = summary
            if cases != len(spec["cases"]):
                problems.append(f"summary cases={cases} expected={len(spec['cases'])}")
            if failed != 0 or passed != cases:
                problems.append(f"summary non-pass tallies={summary}")
            case_total = sum(int(CASE_END.fullmatch(row).group(3)) for row in case_end_rows if CASE_END.fullmatch(row))
            if checks != case_total:
                problems.append(f"summary check total={checks} case sum={case_total}")
            if checks < spec["min_checks"]:
                problems.append(f"summary checks={checks} below {spec['min_checks']}")

    for line in structured:
        if line == END_PASS:
            continue
        if BEGIN_ROW.fullmatch(line):
            continue
        if CASE_BEGIN.fullmatch(line) or CASE_END.fullmatch(line):
            continue
        if STAT_ROW.fullmatch(line) or SUMMARY_ROW.fullmatch(line):
            continue
        problems.append(f"unknown or ambiguous marker: {line}")
    if any(line.startswith("CHECK_FAIL") for line in structured):
        problems.append("CHECK_FAIL present")

    expected_sequence = ["TB_BEGIN"] + ["CASE"] * (2 * len(spec["cases"]))
    expected_sequence += ["TB_STAT"] * len(STAT_KEYS) + ["TB_SUMMARY", "TB_END"]
    actual_sequence = []
    for line in structured:
        if BEGIN_ROW.fullmatch(line):
            actual_sequence.append("TB_BEGIN")
        elif line.startswith("CASE_"):
            actual_sequence.append("CASE")
        elif line.startswith("TB_STAT"):
            actual_sequence.append("TB_STAT")
        elif line.startswith("TB_SUMMARY"):
            actual_sequence.append("TB_SUMMARY")
        elif line == END_PASS:
            actual_sequence.append("TB_END")
    if actual_sequence != expected_sequence:
        problems.append(f"marker order={actual_sequence}")

    result["transcript_lines"] = len(lines)
    result["summary"] = summary
    result["stats"] = dict(stat_rows)
    result["case_count"] = len(begin_names)
    result["problems"] = problems
    return not problems


def parse_guard(spec, result, log_bytes):
    lines = normalized_lines(log_bytes)
    expected_message = f"deepeye_uart_rx: {spec['guard']} out of range"
    other_messages = [
        f"deepeye_uart_rx: {param} out of range"
        for param in ("CLOCK_HZ", "BAUD", "STAT_W")
        if param != spec["guard"]
    ]
    matching = sum(line.count(expected_message) for line in lines)
    problems = []
    for line in lines:
        if line.startswith(("TB_", "CASE_", "CHECK_")):
            problems.append(f"unexpected guard marker: {line}")
    if matching != 1:
        problems.append(f"expected fatal message count={matching}")
    for message in other_messages:
        if any(message in line for line in lines):
            problems.append(f"wrong guard message: {message}")
    if any("GUARD_TB_UNEXPECTED_NO_FATAL" in line for line in lines):
        problems.append("guard testbench reached normal finish")

    error_tallies = []
    warning_tallies = []
    fatal_rows = []
    for line in lines:
        match = re.search(r"\bErrors:\s*([0-9]+)", line)
        if match:
            error_tallies.append(int(match.group(1)))
        match = re.search(r"\bWarnings:\s*([0-9]+)", line)
        if match:
            warning_tallies.append(int(match.group(1)))
        if line.startswith("** Fatal"):
            fatal_rows.append(line)
        elif line.startswith("** Error") or line.startswith("** Warning"):
            problems.append(f"unexpected diagnostic: {line}")
        elif line.startswith("Error:") or line.startswith("Warning:"):
            problems.append(f"unexpected tool diagnostic: {line}")
    if error_tallies:
        if any(value != 1 for value in error_tallies):
            problems.append(f"error tallies={error_tallies}")
    elif len(fatal_rows) != 1:
        problems.append(f"fatal rows={len(fatal_rows)} without error tally")
    if any(value != 0 for value in warning_tallies):
        problems.append(f"warning tallies={warning_tallies}")
    if len(fatal_rows) != 1:
        problems.append(f"fatal row count={len(fatal_rows)}")

    result["expected_fatal"] = expected_message
    result["error_tallies"] = error_tallies
    result["warning_tallies"] = warning_tallies
    result["fatal_rows"] = fatal_rows
    result["problems"] = problems
    return not problems


def run_suite(attempt, name, spec, env, modelsim_root, timeout):
    suite_dir = attempt / "suites" / name
    suite_dir.mkdir(parents=True, exist_ok=False)
    source_dir = suite_dir / "source"
    source_dir.mkdir()
    rtl_snapshot = source_dir / "deepeye_uart_rx.sv"
    tb_snapshot = source_dir / "tb_uart_rx.sv"
    rtl_bytes = RTL_SOURCE.read_bytes()
    tb_bytes = TB_SOURCE.read_bytes()
    rtl_snapshot.write_bytes(rtl_bytes)
    tb_snapshot.write_bytes(tb_bytes)
    rtl_hash = hashlib.sha256(rtl_bytes).hexdigest()
    tb_hash = hashlib.sha256(tb_bytes).hexdigest()
    (source_dir / "sha256.txt").write_text(
        f"{rtl_hash}  deepeye_uart_rx.sv\n{tb_hash}  tb_uart_rx.sv\n",
        encoding="ascii",
        newline="\n",
    )
    work_dir = suite_dir / "work"
    work_dir.mkdir()
    result = {
        "suite": name,
        "top": spec["top"],
        "passed": False,
        "rtl_sha256": rtl_hash,
        "tb_sha256": tb_hash,
        "expected_cases": spec["cases"],
        "expected_stats": spec["stats"],
        "expected_min_checks": spec["min_checks"],
        "expected_guard": spec["guard"],
        "commands": [],
    }

    vlib = run_command(
        attempt,
        f"{name}/01-vlib-work",
        [modelsim_root / "vlib.exe", "work"],
        work_dir,
        env,
        timeout,
    )
    result["commands"].append(command_metadata(vlib))
    vlib_problems = ordinary_output_problems(
        normalized_lines(vlib["stdout_bytes"] + b"\n" + vlib["stderr_bytes"])
    )
    if vlib["exit_code"] != 0 or vlib["timed_out"] or vlib["process_error"]:
        vlib_problems.append("vlib work did not succeed")
    if vlib_problems:
        result["problems"] = vlib_problems
        write_json(suite_dir / "result.json", result)
        return result

    vlog_argv = [modelsim_root / "vlog.exe", "-sv", "-work", "work"]
    vlog_argv += [f"+define+{define}" for define in spec["defines"]]
    vlog_argv += [rtl_snapshot, tb_snapshot]
    vlog = run_command(
        attempt, f"{name}/02-vlog", vlog_argv, work_dir, env, timeout
    )
    result["commands"].append(command_metadata(vlog))
    vlog_problems = ordinary_output_problems(
        normalized_lines(vlog["stdout_bytes"] + b"\n" + vlog["stderr_bytes"])
    )
    if vlog["exit_code"] != 0 or vlog["timed_out"] or vlog["process_error"]:
        vlog_problems.append("vlog did not succeed")
    if vlog_problems:
        result["problems"] = vlog_problems
        write_json(suite_dir / "result.json", result)
        return result

    log_path = work_dir / "vsim.log"
    vsim_argv = [
        modelsim_root / "vsim.exe",
        "-c",
        "-l",
        "vsim.log",
        "-do",
        "run -all; quit -f",
        spec["top"],
    ]
    vsim = run_command(
        attempt, f"{name}/03-vsim", vsim_argv, work_dir, env, timeout
    )
    result["commands"].append(command_metadata(vsim))
    if vsim["timed_out"] or vsim["process_error"]:
        result["problems"] = ["vsim timed out or failed to start"]
        write_json(suite_dir / "result.json", result)
        return result
    if not log_path.is_file() or log_path.stat().st_size == 0:
        result["problems"] = ["vsim.log missing or empty"]
        write_json(suite_dir / "result.json", result)
        return result
    log_bytes = log_path.read_bytes()
    log_copy = suite_dir / "vsim-log.txt"
    log_copy.write_bytes(log_bytes)
    result["vsim_log"] = str(log_path)
    result["vsim_log_sha256"] = hashlib.sha256(log_bytes).hexdigest()
    result["vsim_log_copy"] = str(log_copy)

    if spec["guard"] is None:
        if vsim["exit_code"] != 0:
            result["problems"] = [f"ordinary vsim exit={vsim['exit_code']}"]
        else:
            result["passed"] = parse_normal(name, spec, result, log_bytes)
    else:
        # ModelSim 10.7 returns zero after a simulation-only $fatal in batch
        # mode. The exact fatal and the tool's one-error tally are authoritative.
        result["passed"] = parse_guard(spec, result, log_bytes)

    if spec["guard"] is None:
        channel_problems = ordinary_output_problems(
            normalized_lines(vsim["stdout_bytes"] + b"\n" + vsim["stderr_bytes"])
        )
        if channel_problems:
            result["passed"] = False
            result.setdefault("problems", []).extend(channel_problems)

    source_unchanged = (
        sha256_path(RTL_SOURCE) == result["rtl_sha256"]
        and sha256_path(TB_SOURCE) == result["tb_sha256"]
    )
    result["source_unchanged_after_suite"] = source_unchanged
    if not source_unchanged:
        result["passed"] = False
        result.setdefault("problems", []).append("source changed during suite")
    write_json(suite_dir / "result.json", result)
    return result


def check_versions(attempt, env, modelsim_root, timeout):
    tools = {}
    outputs = []
    for tool in ("vlib.exe", "vlog.exe", "vsim.exe"):
        executable = modelsim_root / tool
        version_cwd = attempt / "tool-versions" / tool.replace(".exe", "")
        version_cwd.mkdir(parents=True, exist_ok=True)
        record = run_command(
            attempt,
            f"tool-versions/{tool}",
            [executable, "-version"],
            version_cwd,
            env,
            min(timeout, 120),
        )
        raw = record["stdout_bytes"] + b"\n" + record["stderr_bytes"]
        outputs.append(raw)
        tools[tool] = {
            "path": str(executable),
            "sha256": sha256_path(executable) if executable.is_file() else None,
            "exit_code": record["exit_code"],
            "timed_out": record["timed_out"],
            "stdout_sha256": record["stdout_sha256"],
            "stderr_sha256": record["stderr_sha256"],
            "version_text": raw.decode("utf-8", errors="replace"),
        }
    combined = b"\n".join(outputs).decode("utf-8", errors="replace")
    modelsim_10_7 = bool(re.search(r"ModelSim\b.*\b10\.7\b", combined, re.DOTALL))
    return tools, modelsim_10_7


def printable_result(result):
    lines = [f"suite={result['suite']} pass={str(result['passed']).lower()}"]
    if result.get("summary") is not None:
        lines.append(f"summary={result['summary']}")
    if result.get("stats") is not None:
        lines.append(f"stats={result['stats']}")
    for problem in result.get("problems", []):
        lines.append(f"problem={problem}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", help="new author attempt id")
    parser.add_argument(
        "--suite",
        action="append",
        choices=list(SUITES),
        help="suite to run; repeat to select more than one",
    )
    parser.add_argument(
        "--modelsim-root",
        default=os.environ.get("MODELSIM_ROOT", r"D:/modelsim1/win64"),
    )
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        for name in SUITES:
            print(name)
        return 0
    if not args.attempt:
        parser.error("--attempt is required unless --list is used")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.attempt):
        parser.error("attempt id must contain only letters, digits, dot, underscore, or hyphen")
    if not RTL_SOURCE.is_file() or not TB_SOURCE.is_file():
        print("author source missing", file=sys.stderr)
        return 2
    modelsim_root = Path(args.modelsim_root).resolve()
    for tool in ("vlib.exe", "vlog.exe", "vsim.exe"):
        if not (modelsim_root / tool).is_file():
            print(f"missing tool: {modelsim_root / tool}", file=sys.stderr)
            return 2

    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    attempt = EVIDENCE_ROOT / f"attempt-{args.attempt}"
    try:
        attempt.mkdir(exist_ok=False)
    except FileExistsError:
        print(f"refusing to overwrite existing attempt: {attempt}", file=sys.stderr)
        return 2

    tmp_dir = attempt / "env" / "tmp"
    cache_dir = attempt / "env" / "pycache"
    tmp_dir.mkdir(parents=True)
    cache_dir.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "TEMP": str(tmp_dir),
            "TMP": str(tmp_dir),
            "TMPDIR": str(tmp_dir),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPYCACHEPREFIX": str(cache_dir),
        }
    )

    selected = args.suite or list(SUITES)
    runner_bytes = Path(__file__).read_bytes()
    source_root = attempt / "source-initial"
    source_root.mkdir()
    (source_root / "deepeye_uart_rx.sv").write_bytes(RTL_SOURCE.read_bytes())
    (source_root / "tb_uart_rx.sv").write_bytes(TB_SOURCE.read_bytes())
    (source_root / "run_uart_rx.py").write_bytes(runner_bytes)
    initial_hashes = {
        "rtl_sha256": sha256_path(RTL_SOURCE),
        "tb_sha256": sha256_path(TB_SOURCE),
        "runner_sha256": hashlib.sha256(runner_bytes).hexdigest(),
    }
    write_json(attempt / "runner-command.json", {"argv": sys.argv, "cwd": os.getcwd()})
    write_json(
        attempt / "environment.json",
        {
            "attempt": args.attempt,
            "modelsim_root": str(modelsim_root),
            "timeout_seconds": args.timeout,
            "selected_suites": selected,
            "product_root": str(PRODUCT_ROOT),
            "source_hashes": initial_hashes,
            "owned_temp": {key: env[key] for key in ("TEMP", "TMP", "TMPDIR")},
            "python_no_bytecode": env["PYTHONDONTWRITEBYTECODE"],
            "python_cache_prefix": env["PYTHONPYCACHEPREFIX"],
        },
    )

    summary = {
        "attempt": args.attempt,
        "status": "running",
        "passed": False,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_hashes": initial_hashes,
        "suites": [],
    }
    exit_code = 1
    try:
        tools, modelsim_10_7 = check_versions(attempt, env, modelsim_root, args.timeout)
        summary["modelsim_10_7"] = modelsim_10_7
        summary["tools"] = tools
        if not modelsim_10_7:
            summary["status"] = "toolchain-version-failed"
            summary["error"] = "ModelSim 10.7 version string not observed"
        else:
            for name in selected:
                result = run_suite(attempt, name, SUITES[name], env, modelsim_root, args.timeout)
                summary["suites"].append(result)
                print(printable_result(result), flush=True)
                if not result["passed"]:
                    break
            all_passed = len(summary["suites"]) == len(selected) and all(
                item["passed"] for item in summary["suites"]
            )
            source_unchanged = (
                sha256_path(RTL_SOURCE) == initial_hashes["rtl_sha256"]
                and sha256_path(TB_SOURCE) == initial_hashes["tb_sha256"]
                and sha256_path(Path(__file__)) == initial_hashes["runner_sha256"]
            )
            summary["source_unchanged_after_run"] = source_unchanged
            summary["passed"] = all_passed and source_unchanged
            summary["status"] = "pass" if summary["passed"] else "fail"
            exit_code = 0 if summary["passed"] else 1
    except Exception:
        summary["status"] = "error"
        summary["error"] = traceback.format_exc()
        exit_code = 1

    summary["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_json(attempt / "summary.json", summary)
    (attempt / "summary.txt").write_text(
        "\n".join(
            [
                f"attempt={args.attempt}",
                f"status={summary['status']}",
                f"passed={str(summary['passed']).lower()}",
                f"suites_run={len(summary['suites'])}",
                f"suites_requested={len(selected)}",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
