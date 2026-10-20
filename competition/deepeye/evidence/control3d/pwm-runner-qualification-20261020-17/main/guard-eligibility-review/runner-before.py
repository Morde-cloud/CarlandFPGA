#!/usr/bin/env python3
"""Portable fail-closed ModelSim runner for the op15 applied-capture wrapper.

Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Work: B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1
Operation: B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15

The runner snapshots every source/input byte before compilation, refuses to
overwrite an output directory, preserves stdout/stderr and exits for every
command, and creates isolated wrapper mutants in separate libraries. It needs
no private controller, scope, oracle, or old-suite file to reproduce the run.

This is author-side local simulation evidence only. It is not main acceptance,
synthesis, implementation, CDC/RDC, board, system, or product acceptance.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
WORK_ID = "B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1"
OPERATION_ID = "B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15"
CONTRACT_ID = "DEEPEYE-HUMAN-LOCK-20261014"
CONTRACT_REVISION = 1
CONTRACT_PIN = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
DESIGN_PIN = "1011259415a0916054eb580687612580bc1e5f09"
REQ_SHA = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
ATOMIC_SHA = "9dc8ecf96e59a2ae8467bda64572f62eb602d52db535733f236f64ff97c43428"
CAPTURE_SHA = "4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456"
REQUIREMENT_IDS = [f"H{i:02d}" for i in range(1, 16)]

HERE = Path(__file__).resolve()
WORKTREE = HERE.parents[4]
FILES = {
    "rtl": WORKTREE / "competition/deepeye/fpga/control3d/deepeye_pwm_applied_capture.sv",
    "tb": WORKTREE / "competition/deepeye/tests/rtl/control3d/tb_pwm_applied_capture.sv",
    "atomic": WORKTREE / "competition/deepeye/fpga/control3d/deepeye_atomic_pwm.sv",
    "capture": WORKTREE / "competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv",
    "candidate": WORKTREE / "competition/deepeye/fpga/control3d/pwm_applied_capture_candidate.md",
}
PROTECTED = WORKTREE / "handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json"
PROTECTED_SHA = "6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8"
DEFAULT_OUT = WORKTREE / "competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author/run-author-20261020-15-c"
DEFAULT_MODELSIM = Path("D:/modelsim1/win64")

# The current TB emits these exact whole-line records, optionally prefixed by
# ModelSim's "# ". Bound ASCII decimals before int conversion; \d also accepts
# non-ASCII numerals. This is a log protocol, not a search for success keywords.
STAT_KEYS = ("groups", "cases", "samples", "assertions", "records", "raw_faults",
             "failure_events", "window_starts", "handshakes", "mismatches")
DECIMAL = r"[0-9]{1,20}"
TB_STATS_RE = re.compile("TB_STATS " + " ".join(
    key + "=(" + DECIMAL + ")" for key in STAT_KEYS))
PASS_RE = re.compile(r"TB_PASS group=(" + DECIMAL + r") loopback=([01])")
FAIL_RE = re.compile(r"TB_FAIL group=(" + DECIMAL + r") mismatches=(" + DECIMAL + r")")
MISMATCH_RE = re.compile(
    r"MISMATCH sample=(" + DECIMAL + r") label=([A-Za-z0-9_]+)"
    r" expected=[0-9a-fA-FxXzZ]+ actual=[0-9a-fA-FxXzZ]+")
CODE7_LINE = "CODE7_OBSERVED code=7 window_active=0 out_valid=0"
FAIL_FATAL_LINE = "** Fatal: TB_FAIL public-port self-check"
SIM_ERROR_RE = re.compile(r"\*\*\s+(?:Error|Fatal):")
RESERVED = ("TB_STATS", "TB_PASS", "TB_FAIL", "MISMATCH", "CODE7_OBSERVED")
GUARD_TOKEN = "DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM"
GUARD_MISSING_TOKEN = "APPLIED_CAPTURE_INVALID_GUARD_MISSING"
GUARD_FATAL_LINE = "** Fatal: " + GUARD_TOKEN + " unsupported widths"
GUARD_KEYS = ("count_w", "witness_w", "tag_w",
              "safe_count_w", "safe_witness_w", "safe_tag_w")
SIGNED_CANONICAL = r"(?:0|-?[1-9][0-9]{0,19})"
UNSIGNED_CANONICAL = r"(?:0|[1-9][0-9]{0,19})"
INVALID_RE = re.compile(GUARD_TOKEN + " " + " ".join(
    key.upper() + "=(" + (SIGNED_CANONICAL if i < 3 else UNSIGNED_CANONICAL) + ")"
    for i, key in enumerate(GUARD_KEYS)))

POSITIVE_RUNS = [
    {"id": "g00-startup-controls", "group": 0, "count_w": 8, "witness_w": 16, "tag_w": 8, "loopback": 0, "trace": 1},
    {"id": "g01-exhaustive-w2", "group": 1, "count_w": 2, "witness_w": 8, "tag_w": 4, "loopback": 0},
    {"id": "g02-exhaustive-w3", "group": 2, "count_w": 3, "witness_w": 8, "tag_w": 5, "loopback": 0},
    {"id": "g03-faults-recovery", "group": 3, "count_w": 8, "witness_w": 8, "tag_w": 8, "loopback": 0},
    {"id": "g04-min-exhaustion", "group": 4, "count_w": 2, "witness_w": 2, "tag_w": 1, "loopback": 0},
    {"id": "g05-count16-boundaries", "group": 5, "count_w": 16, "witness_w": 32, "tag_w": 16, "loopback": 0},
    {"id": "g06-max-width-bounded", "group": 6, "count_w": 32, "witness_w": 64, "tag_w": 64, "loopback": 0},
    {"id": "g07-default-smoke", "group": 7, "count_w": 32, "witness_w": 64, "tag_w": 32, "loopback": 0},
    {"id": "g08-loopback-record", "group": 8, "count_w": 4, "witness_w": 16, "tag_w": 8, "loopback": 1},
    {"id": "g09-loopback-exhaustion", "group": 9, "count_w": 2, "witness_w": 2, "tag_w": 1, "loopback": 1},
    {"id": "g10-phase-controls", "group": 10, "count_w": 4, "witness_w": 8, "tag_w": 8, "loopback": 0},
    {"id": "g11-same-edge-fault", "group": 11, "count_w": 4, "witness_w": 4, "tag_w": 8, "loopback": 0, "trace": 1},
    {"id": "g12-future-waveform", "group": 12, "count_w": 4, "witness_w": 8, "tag_w": 8, "loopback": 0, "trace": 1},
    {"id": "g13-same-tag-boundaries", "group": 13, "count_w": 4, "witness_w": 8, "tag_w": 8, "loopback": 0, "trace": 1},
    {"id": "g14-control-at-handshake", "group": 14, "count_w": 4, "witness_w": 8, "tag_w": 8, "loopback": 0, "trace": 1},
    {"id": "g15-constant-missing-edges", "group": 15, "count_w": 8, "witness_w": 8, "tag_w": 8, "loopback": 0, "trace": 1},
    {"id": "g20-T-boundary-control", "group": 20, "count_w": 4, "witness_w": 8, "tag_w": 8, "loopback": 0},
    {"id": "g21-same-tag-control", "group": 21, "count_w": 4, "witness_w": 8, "tag_w": 8, "loopback": 0},
    {"id": "g22-mismatch-control", "group": 22, "count_w": 4, "witness_w": 8, "tag_w": 8, "loopback": 0},
]

INVALID_RUNS = [
    {"id": "invalid-count-zero", "count_w": 0, "witness_w": 64, "tag_w": 32},
    {"id": "invalid-count-negative", "count_w": -1, "witness_w": 64, "tag_w": 32},
    {"id": "invalid-count-high", "count_w": 33, "witness_w": 64, "tag_w": 32},
    {"id": "invalid-witness-zero", "count_w": 32, "witness_w": 0, "tag_w": 32},
    {"id": "invalid-witness-negative", "count_w": 32, "witness_w": -2, "tag_w": 32},
    {"id": "invalid-witness-high", "count_w": 32, "witness_w": 65, "tag_w": 32},
    {"id": "invalid-tag-zero", "count_w": 32, "witness_w": 64, "tag_w": 0},
    {"id": "invalid-tag-negative", "count_w": 32, "witness_w": 64, "tag_w": -1},
    {"id": "invalid-tag-high", "count_w": 32, "witness_w": 64, "tag_w": 65},
]

T_BOUNDARY_OLD = "rst || stop || transfer_now || g_pending || !g_running"
T_BOUNDARY_DELAYED = "rst || stop || g_pending || !g_running"
T_BOUNDARY_SAME_TAG = (
    "rst || stop || (transfer_now && (cfg_tag != expected_tag_q)) || "
    "(g_pending && (cfg_tag != expected_tag_q)) || !g_running"
)
REARM_LINE = "assign capture_rearm = capture_arm;"
OUT_VALID_OLD = (
    "assign out_valid = transport_window && c_armed && !raw_fault &&\n"
    "                       c_out_valid && raw_equal;"
)
OUT_VALID_MISMATCH = (
    "assign out_valid = transport_window && c_armed && !raw_fault &&\n"
    "                       c_out_valid;"
)

MUTANT_SPECS = [
    {
        "id": "m1-t-invalidation-delayed",
        "description": (
            "Combinational T guard omits transfer_now, so a pre-existing old "
            "matched slot is exported and handshaken on the transfer edge."
        ),
        "replacements": [(T_BOUNDARY_OLD, T_BOUNDARY_DELAYED)],
        "runs": [
            {
                "group": 21, "count_w": 4, "witness_w": 8, "tag_w": 8,
                "expect": "fail",
                "required_any": [
                    "T_suppresses_preexisting_out_valid",
                    "T_suppresses_old_handshake",
                ],
            }
        ],
    },
    {
        "id": "m2-same-tag-state-retained",
        "description": (
            "T/pending invalidation and rearm are made tag-dependent, so a "
            "same-tag reapplication retains and exports an interval that lacks "
            "a complete post-boundary cycle."
        ),
        "replacements": [
            (T_BOUNDARY_OLD, T_BOUNDARY_SAME_TAG),
            (REARM_LINE, "assign capture_rearm = capture_arm && (cfg_tag != expected_tag_q);"),
        ],
        "runs": [
            {
                "group": 13, "count_w": 4, "witness_w": 8, "tag_w": 8,
                "expect": "fail",
                "required_any": [
                    "same_tuple_T_suppresses_old_valid",
                    "same_tuple_T_no_old_handshake",
                    "same_tuple_T_clears_binding",
                    "same_tuple_no_spliced_old_interval",
                ],
            }
        ],
    },
    {
        "id": "m3-mismatch-admitted",
        "description": (
            "Raw/expected equality is removed from out_valid, so a mismatching "
            "raw slot becomes externally valid and handshakeable."
        ),
        "replacements": [(OUT_VALID_OLD, OUT_VALID_MISMATCH)],
        "runs": [
            {
                "group": 22, "count_w": 4, "witness_w": 8, "tag_w": 8,
                "expect": "fail",
                "required_any": [
                    "mismatch_control_not_external_valid",
                    "mismatch_control_no_handshake",
                ],
            }
        ],
    },
    {
        "id": "m4-no-capture-rearm",
        "description": (
            "Every rearm is suppressed. The correct design never reaches code7; "
            "this deliberately faulty copy exposes the defensive code7 path."
        ),
        "replacements": [(REARM_LINE, "assign capture_rearm = 1'b0;")],
        "runs": [
            {
                "group": 30, "count_w": 4, "witness_w": 8, "tag_w": 8,
                "expect": "pass_code7", "required_any": ["CODE7_OBSERVED"],
            },
            {
                "group": 13, "count_w": 4, "witness_w": 8, "tag_w": 8,
                "expect": "fail",
                "required_any": ["same_tuple_old_record", "same_tuple_window_start"],
            },
        ],
    },
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(cmd: list[str], cwd: Path, log_dir: Path, name: str, timeout: float,
                commands: list[dict]) -> dict:
    stdout_path = log_dir / f"{name}.stdout.txt"
    stderr_path = log_dir / f"{name}.stderr.txt"
    if stdout_path.exists() or stderr_path.exists():
        raise FileExistsError(f"refusing to overwrite log for {name}")
    started = utc_now()
    record = {
        "name": name,
        "argv": cmd,
        "cwd": str(cwd),
        "started_utc": started,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    }
    commands.append(record)
    with stdout_path.open("wb") as out_f, stderr_path.open("wb") as err_f:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(cwd),
                stdout=out_f,
                stderr=err_f,
                timeout=timeout,
                check=False,
            )
            record["exit"] = proc.returncode
        except subprocess.TimeoutExpired:
            record["exit"] = "timeout"
            record["timeout_s"] = timeout
        except Exception as exc:
            record["exit"] = "exception"
            record["exception"] = f"{type(exc).__name__}: {exc}"
    record["ended_utc"] = utc_now()
    record["stdout_sha256"] = sha256_file(stdout_path)
    record["stderr_sha256"] = sha256_file(stderr_path)
    return record


def completed_process(record: dict, expected_failure: bool = False) -> bool:
    """A marker never upgrades a timeout/exception or unexpected process exit.

    The expected-failure path permits ModelSim's completed exit0/exit1 fatal
    conventions only alongside the caller's exact diagnostic/counterexample.
    Normal PASS paths require completed exit0.
    """
    code = record.get("exit")
    return type(code) is int and code in ((0, 1) if expected_failure else (0,))


def parse_tb_output(stdout_path: Path, stderr_path: Path) -> dict:
    """Validate one complete TB outcome; preserve diagnostics on rejection.

    Duplicate records (even identical), unknown prefixes/suffixes, incomplete
    counters, conflicting terminal evidence, and records in stderr fail closed.
    Expected mutant failure additionally needs the TB's own fatal diagnostic.
    Simulator metadata after the terminal record is permitted; later errors
    are still examined. No line is silently selected as the authoritative one.
    """
    # Preserve line framing: splitlines()/universal-newline conversion would
    # also treat embedded CR, vertical tabs or Unicode separators as new lines.
    text = stdout_path.read_bytes().decode("utf-8", errors="replace")
    err = stderr_path.read_bytes().decode("utf-8", errors="replace")
    errors, stats_rows, outcomes, mismatches, code7, own_fatals = [], [], [], [], [], []
    simulator_errors = []
    if "\ufffd" in text or "\ufffd" in err:
        errors.append("invalid UTF-8 or replacement character in transcript")
    for index, line in enumerate(text.split("\n")):
        if line.endswith("\r"):
            line = line[:-1]
        body = line[2:] if line.startswith("# ") else line
        match = TB_STATS_RE.fullmatch(body)
        if match:
            stats_rows.append((index, dict(zip(STAT_KEYS, map(int, match.groups())))))
            continue
        match = PASS_RE.fullmatch(body)
        if match:
            outcomes.append((index, "pass", int(match[1]), int(match[2])))
            continue
        match = FAIL_RE.fullmatch(body)
        if match:
            outcomes.append((index, "fail", int(match[1]), int(match[2])))
            continue
        match = MISMATCH_RE.fullmatch(body)
        if match:
            mismatches.append((index, int(match[1]), match[2]))
            continue
        if body == CODE7_LINE:
            code7.append(index)
            continue
        if body == FAIL_FATAL_LINE:
            own_fatals.append(index)
            continue
        if any(token in body for token in RESERVED):
            errors.append(f"malformed or unexpected TB record at stdout line {index + 1}")
        if SIM_ERROR_RE.search(body):
            simulator_errors.append(f"stdout line {index + 1}: {body}")
    for index, line in enumerate(err.split("\n")):
        if any(token in line for token in RESERVED):
            errors.append(f"unexpected TB record at stderr line {index + 1}")
        if SIM_ERROR_RE.search(line):
            simulator_errors.append(f"stderr line {index + 1}: {line}")
    if len(stats_rows) != 1:
        errors.append(f"expected one complete TB_STATS row, got {len(stats_rows)}")
    if len(outcomes) != 1:
        errors.append(f"expected one terminal TB_PASS/TB_FAIL row, got {len(outcomes)}")
    stats = stats_rows[0][1] if len(stats_rows) == 1 else None
    terminal = None
    if len(outcomes) == 1:
        end, kind, group, value = outcomes[0]
        terminal = {"kind": kind, "group": group,
                    ("loopback" if kind == "pass" else "mismatches"): value}
        if stats is not None:
            start = stats_rows[0][0]
            if start >= end:
                errors.append("statistics must precede terminal outcome")
            if any(i >= start or sample > stats["samples"] for i, sample, _ in mismatches):
                errors.append("mismatch record outside sampled pre-statistics interval")
            if len(mismatches) != stats["mismatches"]:
                errors.append("mismatch records disagree with statistics")
            if any(i >= start for i in code7):
                errors.append("code7 observation must precede statistics")
            if kind == "pass" and stats["mismatches"] != 0:
                errors.append("PASS conflicts with nonzero mismatches")
            if kind == "fail" and (value == 0 or value != stats["mismatches"]):
                errors.append("FAIL count disagrees with positive mismatch count")
        if kind == "pass" and own_fatals:
            errors.append("PASS conflicts with TB fatal diagnostic")
        if kind == "fail" and (len(own_fatals) != 1 or own_fatals[0] <= end):
            errors.append("FAIL requires one subsequent TB fatal diagnostic")
        if code7 and (kind != "pass" or group != 30 or value != 0):
            errors.append("CODE7 is reserved for PASS group30 loopback0")
        if kind == "pass" and group == 30 and (value != 0 or len(code7) != 1):
            errors.append("PASS group30 requires one CODE7 observation and loopback0")
    if len(code7) > 1:
        errors.append("duplicate code7 observation")
    if simulator_errors:
        errors.append("unexpected simulator Error/Fatal diagnostic")
    valid = not errors
    return {
        "passed": valid and terminal is not None and terminal["kind"] == "pass",
        "failed": bool(errors) or (terminal is not None and terminal["kind"] == "fail"),
        "protocol_valid": valid,
        "protocol_errors": errors,
        "simulator_errors": simulator_errors,
        "terminal": terminal,
        "stats": stats,
        "mismatch_labels": [label for _, _, label in mismatches],
        "code7_observed": valid and len(code7) == 1,
        "stdout_tail": text[-4000:],
        "stderr_tail": err[-2000:],
    }


def parse_invalid_output(stdout_path: Path, stderr_path: Path) -> dict:
    """Recognize only one ordered invalid-width diagnostic/own-fatal pair.

    All protocol records belong to stdout. Other Error/Fatal diagnostics,
    duplicates, malformed guard records and ordinary TB outcomes invalidate
    this expected-failure qualification even if the process completed.
    """
    text = stdout_path.read_bytes().decode("utf-8", errors="replace")
    err = stderr_path.read_bytes().decode("utf-8", errors="replace")
    errors, diagnostics, fatals = [], [], []
    guard_missing = GUARD_MISSING_TOKEN in text or GUARD_MISSING_TOKEN in err
    tokens = (*RESERVED, GUARD_TOKEN, GUARD_MISSING_TOKEN)
    if "\ufffd" in text or "\ufffd" in err:
        errors.append("invalid UTF-8 or replacement character in transcript")
    for index, line in enumerate(text.split("\n")):
        if line.endswith("\r"):
            line = line[:-1]
        body = line[2:] if line.startswith("# ") else line
        match = INVALID_RE.fullmatch(body)
        if match:
            diagnostics.append((index, dict(zip(GUARD_KEYS, map(int, match.groups())))))
        elif body == GUARD_FATAL_LINE:
            fatals.append(index)
        else:
            if any(token in body for token in tokens):
                errors.append(f"malformed or unexpected guard record at stdout line {index + 1}")
            if SIM_ERROR_RE.search(body):
                errors.append(f"unexpected simulator Error/Fatal at stdout line {index + 1}")
    for index, line in enumerate(err.split("\n")):
        if any(token in line for token in tokens) or SIM_ERROR_RE.search(line):
            errors.append(f"unexpected guard record or Error/Fatal at stderr line {index + 1}")
    if len(diagnostics) != 1:
        errors.append(f"expected one complete guard diagnostic, got {len(diagnostics)}")
    if len(fatals) != 1:
        errors.append(f"expected one exact guard fatal, got {len(fatals)}")
    if len(diagnostics) == len(fatals) == 1 and diagnostics[0][0] >= fatals[0]:
        errors.append("guard diagnostic must precede its fatal")
    if guard_missing:
        errors.append("guard-missing marker present")
    return {
        "diagnostic": diagnostics[0][1] if len(diagnostics) == 1 else None,
        "own_fatal": len(fatals) == 1,
        "guard_missing": guard_missing,
        "protocol_valid": not errors,
        "protocol_errors": errors,
    }


def positive_result(spec: dict, result: dict) -> bool:
    parsed = result["parsed"]
    terminal = parsed["terminal"]
    return bool(completed_process(result["record"]) and parsed["passed"]
                and parsed["protocol_valid"] and not parsed["failed"]
                and terminal["group"] == spec["group"]
                and terminal["loopback"] == spec.get("loopback", 0))


def mutant_result(spec: dict, result: dict) -> bool:
    parsed = result["parsed"]
    if spec["expect"] == "pass_code7":
        return positive_result(spec, result) and parsed["code7_observed"]
    terminal = parsed["terminal"]
    return bool(spec["expect"] == "fail"
                and completed_process(result["record"], expected_failure=True)
                and parsed["protocol_valid"] and terminal["kind"] == "fail"
                and terminal["group"] == spec["group"]
                and any(label in parsed["mismatch_labels"] for label in spec["required_any"]))


def snapshot_sources(out: Path, paths: dict[str, Path], runner: Path) -> dict:
    snap = out / "source_snapshot"
    snap.mkdir(parents=True, exist_ok=False)
    manifest = {"files": {}, "runner": {"source_path": str(runner)}}
    for key, source in paths.items():
        destination = snap / f"{key}{source.suffix}"
        destination.write_bytes(source.read_bytes())
        manifest["files"][key] = {
            "source_path": str(source),
            "snapshot_name": destination.name,
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
        }
    runner_snapshot = snap / "run_pwm_applied_capture.py"
    runner_snapshot.write_bytes(runner.read_bytes())
    manifest["runner"]["snapshot_name"] = runner_snapshot.name
    manifest["runner"]["sha256"] = sha256_file(runner_snapshot)
    manifest["runner"]["bytes"] = runner_snapshot.stat().st_size
    return manifest


def discover_tools(modelsim_root: Path) -> dict[str, str]:
    tools = {}
    for name in ("vlib", "vlog", "vsim"):
        path = modelsim_root / f"{name}.exe"
        if not path.is_file():
            path = modelsim_root / name
        if not path.is_file():
            raise FileNotFoundError(f"ModelSim tool not found: {name} under {modelsim_root}")
        tools[name] = str(path)
    return tools


def compile_design(out: Path, logs: Path, commands: list[dict], tools: dict[str, str],
                   rtl_path: Path, tb_path: Path, atomic_path: Path, capture_path: Path,
                   timeout: float, label: str) -> tuple[Path, dict]:
    lib = out / label / "lib"
    lib.parent.mkdir(parents=True, exist_ok=False)
    vlib_record = run_command([tools["vlib"], "lib"], lib.parent, logs, f"{label}-vlib", timeout, commands)
    vlog_cmd = [
        tools["vlog"], "-sv", "-work", "lib",
        str(atomic_path), str(capture_path), str(rtl_path), str(tb_path),
    ]
    vlog_record = run_command(vlog_cmd, lib.parent, logs, f"{label}-vlog", timeout, commands)
    text = (logs / f"{label}-vlog.stdout.txt").read_text(encoding="utf-8", errors="replace")
    info = {
        "label": label,
        "vlib": vlib_record,
        "vlog": vlog_record,
        "compiled": (vlib_record["exit"] == 0 and vlog_record["exit"] == 0
                     and "Errors: 0" in text),
    }
    return lib.parent, info


def run_tb(lib_parent: Path, logs: Path, commands: list[dict], tools: dict[str, str],
           name: str, group: int, count_w: int, witness_w: int, tag_w: int,
           loopback: int, timeout: float, top: str = "tb_pwm_applied_capture",
           trace: int = 0) -> dict:
    log_file = logs / f"{name}.transcript.txt"
    wlf_file = logs / f"{name}.wlf"
    if log_file.exists() or wlf_file.exists():
        raise FileExistsError(f"refusing to overwrite simulator artifact for {name}")
    cmd = [
        tools["vsim"], "-c", "-work", "lib",
        "-l", str(log_file), "-wlf", str(wlf_file),
        "-do", "run -all; quit -f",
        f"-gCOUNT_W={count_w}", f"-gWITNESS_W={witness_w}", f"-gTAG_W={tag_w}",
        f"-gTEST_GROUP={group}", f"-gLOOPBACK={loopback}",
        f"-gTRACE={trace}", top,
    ]
    record = run_command(cmd, lib_parent, logs, name, timeout, commands)
    parsed = parse_tb_output(logs / f"{name}.stdout.txt", logs / f"{name}.stderr.txt")
    parsed["transcript"] = str(log_file)
    parsed["transcript_sha256"] = sha256_file(log_file) if log_file.is_file() else None
    parsed["wlf"] = str(wlf_file)
    parsed["wlf_sha256"] = sha256_file(wlf_file) if wlf_file.is_file() else None
    return {"record": record, "parsed": parsed}


def clamp_width(value: int, low: int, high: int) -> int:
    return low if value < low else (high if value > high else value)


def run_invalid(lib_parent: Path, logs: Path, commands: list[dict],
                tools: dict[str, str], spec: dict, timeout: float) -> dict:
    name = spec["id"]
    log_file = logs / f"{name}.transcript.txt"
    wlf_file = logs / f"{name}.wlf"
    if log_file.exists() or wlf_file.exists():
        raise FileExistsError(f"refusing to overwrite simulator artifact for {name}")
    cmd = [
        tools["vsim"], "-c", "-work", "lib",
        "-l", str(log_file), "-wlf", str(wlf_file),
        "-do", "run -all; quit -f",
        f"-gCOUNT_W={spec['count_w']}",
        f"-gWITNESS_W={spec['witness_w']}",
        f"-gTAG_W={spec['tag_w']}",
        "tb_invalid_applied_capture",
    ]
    record = run_command(cmd, lib_parent, logs, name, timeout, commands)
    parsed = parse_invalid_output(logs / f"{name}.stdout.txt", logs / f"{name}.stderr.txt")
    diagnostic = parsed["diagnostic"]
    expected = {
        "count_w": spec["count_w"],
        "witness_w": spec["witness_w"],
        "tag_w": spec["tag_w"],
        "safe_count_w": clamp_width(spec["count_w"], 2, 32),
        "safe_witness_w": clamp_width(spec["witness_w"], 2, 64),
        "safe_tag_w": clamp_width(spec["tag_w"], 1, 64),
    }
    exact = diagnostic is not None and diagnostic == expected
    return {
        "record": record,
        "diagnostic": diagnostic,
        "expected": expected,
        "guard_missing": parsed["guard_missing"],
        "diagnostic_exact": exact,
        "own_fatal": parsed["own_fatal"],
        "protocol_errors": parsed["protocol_errors"],
        "process_completed": completed_process(record, expected_failure=True),
        "passed": (exact and parsed["protocol_valid"]
                   and completed_process(record, expected_failure=True)),
        "transcript": str(log_file),
        "transcript_sha256": sha256_file(log_file) if log_file.is_file() else None,
        "wlf": str(wlf_file),
        "wlf_sha256": sha256_file(wlf_file) if wlf_file.is_file() else None,
    }


def input_hash_report() -> dict:
    report = {}
    for key, expected in (("atomic", ATOMIC_SHA), ("capture", CAPTURE_SHA)):
        actual = sha256_file(FILES[key])
        report[key] = {
            "path": str(FILES[key]),
            "expected": expected,
            "actual": actual,
            "match": actual == expected,
        }
    return report


def protected_report() -> dict:
    report = {
        "path": str(PROTECTED),
        "expected": PROTECTED_SHA,
        "present": PROTECTED.is_file(),
    }
    if report["present"]:
        actual = sha256_file(PROTECTED)
        report["actual"] = actual
        report["match"] = actual == PROTECTED_SHA
    return report


def make_mutant(spec: dict, rtl_text: str, destination: Path) -> list[dict]:
    text = rtl_text
    replacements = []
    for old, new in spec["replacements"]:
        count = text.count(old)
        if count != 1:
            raise RuntimeError(
                f"{spec['id']}: expected exactly one occurrence, found {count}: {old[:96]!r}"
            )
        text = text.replace(old, new)
        replacements.append({"old": old, "new": new, "occurrences": count})
    destination.parent.mkdir(parents=True, exist_ok=False)
    destination.write_text(text, encoding="utf-8", newline="\n")
    return replacements


def compile_summary(info: dict) -> dict:
    return {
        "label": info["label"],
        "compiled": info["compiled"],
        "vlib_exit": info["vlib"]["exit"],
        "vlog_exit": info["vlog"]["exit"],
        "vlib_stdout": info["vlib"]["stdout"],
        "vlib_stderr": info["vlib"]["stderr"],
        "vlog_stdout": info["vlog"]["stdout"],
        "vlog_stderr": info["vlog"]["stderr"],
    }


def positive_entry(spec: dict, result: dict) -> dict:
    parsed = result["parsed"]
    stats = parsed["stats"]
    passed = positive_result(spec, result)
    entry = {
        "id": spec["id"],
        "group": spec["group"],
        "generator": {
            "COUNT_W": spec["count_w"],
            "WITNESS_W": spec["witness_w"],
            "TAG_W": spec["tag_w"],
            "LOOPBACK": spec["loopback"],
        },
        "passed": passed,
        "protocol_errors": parsed["protocol_errors"],
        "terminal": parsed["terminal"],
        "exit": result["record"]["exit"],
        "stats": stats,
        "mismatch_labels": parsed["mismatch_labels"],
        "code7_observed": parsed["code7_observed"],
        "stdout": result["record"]["stdout"],
        "stderr": result["record"]["stderr"],
        "transcript": parsed["transcript"],
        "transcript_sha256": parsed["transcript_sha256"],
        "wlf": parsed["wlf"],
        "wlf_sha256": parsed["wlf_sha256"],
    }
    if not passed:
        entry["stdout_tail"] = parsed["stdout_tail"]
        entry["stderr_tail"] = parsed["stderr_tail"]
    return entry


def run_positive_suite(work: Path, logs: Path, commands: list[dict],
                       tools: dict[str, str], timeout: float) -> tuple[list[dict], dict]:
    results = []
    for spec in POSITIVE_RUNS:
        result = run_tb(
            work / "positive", logs, commands, tools,
            spec["id"], spec["group"], spec["count_w"], spec["witness_w"],
            spec["tag_w"], spec["loopback"], timeout,
            trace=spec.get("trace", 0),
        )
        results.append(positive_entry(spec, result))
    keys = ("cases", "samples", "assertions", "records", "raw_faults",
            "failure_events", "window_starts", "handshakes", "mismatches")
    totals = {key: sum((entry["stats"] or {}).get(key, 0) for entry in results)
              for key in keys}
    totals["scenarios"] = len(results)
    totals["groups"] = len(results)
    totals["passed_scenarios"] = sum(1 for entry in results if entry["passed"])
    return results, totals


def run_mutant_suite(out: Path, work: Path, logs: Path, commands: list[dict],
                     tools: dict[str, str], snapshot: dict[str, Path],
                     rtl_text: str, timeout: float) -> list[dict]:
    results = []
    for spec in MUTANT_SPECS:
        mutant_dir = out / "mutants" / spec["id"]
        mutant_path = mutant_dir / "deepeye_pwm_applied_capture.sv"
        replacements = make_mutant(spec, rtl_text, mutant_path)
        write_json(mutant_dir / "mutation.json", {
            "id": spec["id"],
            "description": spec["description"],
            "source_path": str(mutant_path),
            "sha256": sha256_file(mutant_path),
            "replacements": replacements,
        })
        lib_parent, info = compile_design(
            work, logs, commands, tools, mutant_path, snapshot["tb"],
            snapshot["atomic"], snapshot["capture"], timeout, f"mutant-{spec['id']}",
        )
        entry = {
            "id": spec["id"],
            "description": spec["description"],
            "source": str(mutant_path),
            "sha256": sha256_file(mutant_path),
            "replacements": replacements,
            "compile": compile_summary(info),
            "runs": [],
        }
        if not info["compiled"]:
            results.append(entry)
            continue
        for run_spec in spec["runs"]:
            name = f"{spec['id']}-g{run_spec['group']}"
            result = run_tb(
                lib_parent, logs, commands, tools, name, run_spec["group"],
                run_spec["count_w"], run_spec["witness_w"], run_spec["tag_w"],
                0, timeout,
            )
            parsed = result["parsed"]
            stats = parsed["stats"]
            labels = parsed["mismatch_labels"]
            run_entry = {
                "group": run_spec["group"],
                "expect": run_spec["expect"],
                "exit": result["record"]["exit"],
                "passed": parsed["passed"],
                "failed": parsed["failed"],
                "stats": stats,
                "mismatch_labels": labels,
                "code7_observed": parsed["code7_observed"],
                "stdout": result["record"]["stdout"],
                "stderr": result["record"]["stderr"],
                "transcript": parsed["transcript"],
                "transcript_sha256": parsed["transcript_sha256"],
                "wlf": parsed["wlf"],
                "wlf_sha256": parsed["wlf_sha256"],
            }
            if run_spec["expect"] == "fail":
                run_entry["rejected"] = mutant_result(run_spec, result)
            elif run_spec["expect"] == "pass_code7":
                run_entry["demonstrated"] = mutant_result(run_spec, result)
            run_entry["protocol_errors"] = parsed["protocol_errors"]
            run_entry["terminal"] = parsed["terminal"]
            if not run_entry.get("rejected", run_entry.get("demonstrated", False)):
                run_entry["stdout_tail"] = parsed["stdout_tail"]
                run_entry["stderr_tail"] = parsed["stderr_tail"]
            entry["runs"].append(run_entry)
        results.append(entry)
    return results


def run_invalid_suite(work: Path, logs: Path, commands: list[dict],
                      tools: dict[str, str], snapshot: dict[str, Path],
                      timeout: float) -> tuple[dict, list[dict]]:
    lib_parent, info = compile_design(
        work, logs, commands, tools, snapshot["rtl"], snapshot["tb"],
        snapshot["atomic"], snapshot["capture"], timeout, "invalid",
    )
    results = []
    if info["compiled"]:
        for spec in INVALID_RUNS:
            result = run_invalid(lib_parent, logs, commands, tools, spec, timeout)
            result["id"] = spec["id"]
            results.append(result)
    return compile_summary(info), results


def tree_records(root: Path, excluded: set[str]) -> tuple[list[dict], int]:
    records = []
    total_bytes = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        size = path.stat().st_size
        total_bytes += size
        records.append({
            "path": relative,
            "bytes": size,
            "sha256": sha256_file(path),
        })
    return records, total_bytes


def tree_sha256(records: list[dict]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(record["path"].encode("utf-8"))
        digest.update(b"\x00")
        digest.update(record["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def relative_to_worktree(path: Path) -> str:
    try:
        return path.resolve().relative_to(WORKTREE).as_posix()
    except ValueError:
        return str(path)


NOT_RUN = [
    "synthesis",
    "implementation",
    "place-and-route",
    "static timing",
    "CDC/RDC",
    "physical board operation",
    "system integration",
    "all29 formal acceptance cards",
    "G05 applied-command/full-cycle/system binding",
    "public register/TRACE type7/HWH/BOOT ABI",
    "physical frequency, clock, source, TTL, profile, curvature or motion authority",
]
LIMITATIONS = [
    "Author-side local ModelSim simulation only; no main acceptance is claimed.",
    "Actual digital loopback is supplemental and explicitly named; the primary source is independent sample_levels schedules.",
    "Code7 is demonstrated only on a deliberately faulty wrapper copy because the correct composition does not reach it.",
    "Maximum COUNT_W=32 and WITNESS_W=64 coverage is bounded observation, not a claim of full traversal.",
    "The 16-bit period 65535 record is fully observed; 65536 is an overflow observation, not a timing or frequency claim.",
    "Mutant rejection is public-port behavioral evidence, not proof against every possible fault.",
    "No Vivado synthesis or implementation was run because the toolchain is unavailable.",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the op15 applied-capture author suite with fail-closed evidence."
    )
    parser.add_argument("--modelsim-root", default=str(DEFAULT_MODELSIM))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args(argv)

    out = Path(args.out).resolve()
    if out.exists():
        print(f"REFUSE existing output directory: {out}")
        return 2
    missing = [f"{key}: {path}" for key, path in FILES.items() if not path.is_file()]
    if missing:
        print("MISSING required inputs:")
        for item in missing:
            print(f"  {item}")
        return 2

    out.mkdir(parents=True)
    logs = out / "logs"
    work = out / "work"
    logs.mkdir()
    work.mkdir()
    (out / "mutants").mkdir()
    commands: list[dict] = []
    failures: list[str] = []
    warnings: list[str] = []
    started = utc_now()
    summary: dict = {
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "work_id": WORK_ID,
        "operation_id": OPERATION_ID,
        "contract_id": CONTRACT_ID,
        "contract_revision": CONTRACT_REVISION,
        "contract_pin": CONTRACT_PIN,
        "design_pin": DESIGN_PIN,
        "requirements_sha256": REQ_SHA,
        "requirement_ids": REQUIREMENT_IDS,
        "baseline_commit": "7dd2c4108ee49cc6e0feb7c715d786f8b11a99c2",
        "worktree": str(WORKTREE),
        "python": sys.version,
        "platform": platform.platform(),
        "started_utc": started,
        "modelsim_root": str(Path(args.modelsim_root).resolve()),
        "timeout_seconds": args.timeout,
    }

    try:
        tools = discover_tools(Path(args.modelsim_root))
        summary["tools"] = tools
        run_command([tools["vlog"], "-version"], out, logs,
                    "tool-vlog-version", 60, commands)
        run_command([tools["vsim"], "-version"], out, logs,
                    "tool-vsim-version", 60, commands)
        summary["tool_versions"] = {
            "vlog": (logs / "tool-vlog-version.stdout.txt").read_text(
                encoding="utf-8", errors="replace").strip(),
            "vsim": (logs / "tool-vsim-version.stdout.txt").read_text(
                encoding="utf-8", errors="replace").strip(),
        }

        before = input_hash_report()
        summary["input_hashes_before"] = before
        if not all(item["match"] for item in before.values()):
            failures.append("immutable input hash mismatch before run")
        summary["protected_dirty_before"] = protected_report()
        if summary["protected_dirty_before"]["present"] and not summary["protected_dirty_before"].get("match", False):
            warnings.append("protected dirty handoff hash changed before run")

        summary["source_snapshot"] = snapshot_sources(out, FILES, HERE)
        snapshot = {
            key: out / "source_snapshot" / f"{key}{FILES[key].suffix}"
            for key in FILES
        }

        positive_lib, positive_info = compile_design(
            work, logs, commands, tools, snapshot["rtl"], snapshot["tb"],
            snapshot["atomic"], snapshot["capture"], args.timeout, "positive",
        )
        summary["positive_compile"] = compile_summary(positive_info)
        if not positive_info["compiled"]:
            failures.append("positive compilation failed")
            summary["positive"] = []
            summary["positive_totals"] = {
                key: 0 for key in (
                    "cases", "samples", "assertions", "records", "raw_faults",
                    "failure_events", "window_starts", "handshakes", "mismatches",
                    "scenarios", "groups", "passed_scenarios",
                )
            }
        else:
            positive, positive_totals = run_positive_suite(
                work, logs, commands, tools, args.timeout)
            summary["positive"] = positive
            summary["positive_totals"] = positive_totals
            exhaustive = [entry for entry in positive if entry["group"] in (1, 2)]
            summary["exhaustive_small_domain"] = {
                "legal_command_triples": sum(
                    entry["stats"]["cases"] for entry in exhaustive
                    if entry["stats"] is not None),
                "eligible_sampled_records": sum(
                    entry["stats"]["records"] for entry in exhaustive
                    if entry["stats"] is not None),
                "groups": ["exhaustive_count_w2_all_legal_tuples",
                           "exhaustive_count_w3_all_legal_tuples"],
            }
            for entry in positive:
                if not entry["passed"]:
                    failures.append(f"positive scenario failed: {entry['id']}")

        rtl_text = snapshot["rtl"].read_text(encoding="utf-8")
        mutants = run_mutant_suite(
            out, work, logs, commands, tools, snapshot, rtl_text, args.timeout)
        summary["mutants"] = mutants
        for entry in mutants:
            if not entry["compile"]["compiled"]:
                failures.append(f"mutant compilation failed: {entry['id']}")
                continue
            for run_entry in entry["runs"]:
                if run_entry["expect"] == "fail" and not run_entry.get("rejected", False):
                    failures.append(
                        f"mutant not rejected at public ports: {entry['id']} "
                        f"group {run_entry['group']}"
                    )
                if run_entry["expect"] == "pass_code7" and not run_entry.get("demonstrated", False):
                    failures.append(
                        f"code7 faulty-copy probe did not demonstrate code7: {entry['id']}"
                    )

        invalid_compile, invalid_runs = run_invalid_suite(
            work, logs, commands, tools, snapshot, args.timeout)
        summary["invalid_compile"] = invalid_compile
        summary["invalid_parameters"] = invalid_runs
        if not invalid_compile["compiled"]:
            failures.append("invalid-parameter compilation failed")
        for entry in invalid_runs:
            if not entry["passed"]:
                failures.append(
                    f"invalid-parameter diagnostic failed: {entry['id']} "
                    f"diagnostic={entry['diagnostic']} expected={entry['expected']}"
                )
        if len(invalid_runs) != len(INVALID_RUNS):
            failures.append("not every invalid-parameter case ran")

        after = input_hash_report()
        summary["input_hashes_after"] = after
        if not all(item["match"] for item in after.values()):
            failures.append("immutable input hash mismatch after run")
        summary["protected_dirty_after"] = protected_report()
        if summary["protected_dirty_after"]["present"] and not summary["protected_dirty_after"].get("match", False):
            warnings.append("protected dirty handoff hash changed after run")
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")
        summary["exception_traceback"] = traceback.format_exc()

    for command in commands:
        if type(command.get("exit")) is not int:
            failures.append(f"incomplete tool command: {command['name']} exit={command.get('exit')}")
    summary["ended_utc"] = utc_now()
    summary["commands"] = commands
    summary["command_count"] = len(commands)
    summary["failures"] = failures
    summary["warnings"] = warnings
    summary["result"] = "PASS" if not failures else "FAIL"
    summary["acceptance"] = (
        "Author-side local ModelSim simulation evidence only. Main acceptance, "
        "synthesis, implementation, CDC/RDC, board/system and all29 formal "
        "cards are not claimed."
    )
    summary["not_run"] = NOT_RUN
    summary["limitations"] = LIMITATIONS
    positive_totals = summary.get("positive_totals", {})
    mutant_runs = sum(len(entry.get("runs", [])) for entry in summary.get("mutants", []))
    scenario_total = (
        positive_totals.get("scenarios", 0)
        + mutant_runs
        + len(summary.get("invalid_parameters", []))
    )
    summary["scenario_counts"] = {
        "positive_scenarios": positive_totals.get("scenarios", 0),
        "mutant_runs": mutant_runs,
        "invalid_parameter_scenarios": len(summary.get("invalid_parameters", [])),
        "total": scenario_total,
    }
    write_json(out / "RUN_SUMMARY.json", summary)

    lines = [
        f"result={summary['result']}",
        f"positive_scenarios={positive_totals.get('scenarios', 0)} "
        f"passed={positive_totals.get('passed_scenarios', 0)}",
        f"samples={positive_totals.get('samples', 0)} "
        f"assertions={positive_totals.get('assertions', 0)} "
        f"records={positive_totals.get('records', 0)}",
        f"mutant_runs={mutant_runs} invalid_parameter_runs={len(summary.get('invalid_parameters', []))}",
        f"failures={len(failures)} warnings={len(warnings)}",
    ]
    console = "\n".join(lines) + "\n"
    (out / "RUNNER_CONSOLE.txt").write_text(console, encoding="utf-8")

    author_dir = out.parent
    run_relative = out.relative_to(author_dir).as_posix()
    excluded = {
        f"{run_relative}/EVIDENCE_TREE_MANIFEST.json",
        f"{run_relative}/TERMINAL_MANIFEST.json",
        f"{run_relative}/TERMINAL_MANIFEST.sha256.txt",
    }
    records, total_bytes = tree_records(author_dir, excluded)
    evidence_tree_sha = tree_sha256(records)
    tree_manifest_path = out / "EVIDENCE_TREE_MANIFEST.json"
    write_json(tree_manifest_path, {
        "root": str(author_dir),
        "excluded_from_tree": sorted(excluded),
        "file_count": len(records),
        "bytes": total_bytes,
        "tree_sha256": evidence_tree_sha,
        "files": records,
    })

    five_paths = {}
    for key in ("rtl", "candidate", "tb", "runner"):
        source = FILES[key] if key != "runner" else HERE
        five_paths[key] = {
            "path": relative_to_worktree(source),
            "absolute_path": str(source.resolve()),
            "bytes": source.stat().st_size,
            "sha256": sha256_file(source),
        }
    five_paths["evidence_author_dir"] = {
        "path": relative_to_worktree(author_dir),
        "absolute_path": str(author_dir),
        "file_count": len(records),
        "bytes": total_bytes,
        "tree_sha256": evidence_tree_sha,
        "tree_manifest": relative_to_worktree(tree_manifest_path),
        "tree_manifest_sha256": sha256_file(tree_manifest_path),
        "excluded_from_tree": sorted(excluded),
    }

    run_summary_path = out / "RUN_SUMMARY.json"
    terminal = {
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "work_id": WORK_ID,
        "operation_id": OPERATION_ID,
        "contract_id": CONTRACT_ID,
        "contract_revision": CONTRACT_REVISION,
        "contract_pin": CONTRACT_PIN,
        "design_pin": DESIGN_PIN,
        "requirements_sha256": REQ_SHA,
        "baseline_commit": "7dd2c4108ee49cc6e0feb7c715d786f8b11a99c2",
        "result": summary["result"],
        "five_paths": five_paths,
        "run_summary": {
            "path": relative_to_worktree(run_summary_path),
            "absolute_path": str(run_summary_path),
            "sha256": sha256_file(run_summary_path),
        },
        "positive_totals": positive_totals,
        "exhaustive_small_domain": summary.get("exhaustive_small_domain"),
        "scenario_counts": summary["scenario_counts"],
        "input_hashes": summary.get("input_hashes_after", summary.get("input_hashes_before")),
        "protected_dirty": summary.get("protected_dirty_after", summary.get("protected_dirty_before")),
        "failures": failures,
        "warnings": warnings,
        "not_run": NOT_RUN,
        "limitations": LIMITATIONS,
        "acceptance": summary["acceptance"],
        "generated_utc": utc_now(),
    }
    terminal_path = out / "TERMINAL_MANIFEST.json"
    write_json(terminal_path, terminal)
    (out / "TERMINAL_MANIFEST.sha256.txt").write_text(
        f"{sha256_file(terminal_path)}  TERMINAL_MANIFEST.json\n",
        encoding="utf-8",
    )
    print(console, end="")
    print(f"terminal_manifest={terminal_path}")
    print(f"terminal_manifest_sha256={sha256_file(terminal_path)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
