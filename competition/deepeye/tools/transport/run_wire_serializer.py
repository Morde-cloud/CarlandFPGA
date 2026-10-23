#!/usr/bin/env python3
"""Strict standalone author runner for the opaque wire serializer candidate."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time
import traceback
from pathlib import Path


PRODUCT_ROOT = Path(__file__).resolve().parents[2]
WORKTREE_ROOT = Path(__file__).resolve().parents[4]
MAIN_WORKSPACE_ROOT = WORKTREE_ROOT.parent.parent.parent
RTL_SOURCE = PRODUCT_ROOT / "fpga/transport/deepeye_wire_serializer.sv"
CRC_SOURCE = PRODUCT_ROOT / "fpga/transport/deepeye_crc16_byte.sv"
TB_SOURCE = PRODUCT_ROOT / "tests/rtl/transport/tb_wire_serializer.sv"
CANDIDATE_SOURCE = PRODUCT_ROOT / "fpga/transport/wire_serializer_candidate.md"
RUNNER_SOURCE = Path(__file__).resolve()
EVIDENCE_ROOT = (
    PRODUCT_ROOT / "evidence/transport/wire-serializer-20261024-28/author"
)
CONTRACT_PATH = WORKTREE_ROOT / "docs/competition/deepeye-2026/immutable_scope.json"
DEFAULT_SCOPE = (
    MAIN_WORKSPACE_ROOT
    / ".local/deployment/node-b/evidence/wire-serializer-20261024-28/SCOPE.md"
)
DEFAULT_REPAIR = (
    MAIN_WORKSPACE_ROOT
    / ".local/deployment/node-b/evidence/wire-serializer-20261024-28/REPAIR1.md"
)

CONTRACT_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
CONTRACT_REL = "docs/competition/deepeye-2026/immutable_scope.json"
REPAIR_ID = "B-WIRE-SERIALIZER-EVENT-REPAIR-20261024-28-r1"
EXPECTED_SCOPE_SHA256 = (
    "f2556d8c9cbd53f2fb9a6c50d357a2e0bd8cc60e9225a892189ddd948f6c54ec"
)
EXPECTED_REPAIR_SHA256 = (
    "f9b6310ac37887950df886725778a317a11cd49a0d5644151b7650d1e3ed5c2c"
)
EXPECTED_REQUIREMENTS_SHA256 = (
    "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
)
EXPECTED_CRC_SHA256 = (
    "8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f"
)
EXPECTED_DESIGN_COMMIT = "1011259415a0916054eb580687612580bc1e5f09"
EXPECTED_BASE_HEAD = "dfdb2b8120793ba816fd09cd8fc255953bbf73ac"

EXPECTED_CASES = [
    ("initial_reset", 13),
    ("length_and_byte_sweep", 17633),
    ("external_crc_spots", 672),
    ("stall_and_bubbles", 332),
    ("payload_faults", 84),
    ("illegal_length_faults", 78),
    ("cancel_phases", 336),
    ("reset_phases", 356),
    ("small_counter_saturation", 369),
    ("fault_event_boundary", 114),
    ("final_state", 26),
]
EXPECTED_STATS = [
    ("valid_frames", 46),
    ("lengths_covered", 33),
    ("byte_values_covered", 256),
    ("external_crc_vectors", 4),
    ("fault_cases", 7),
    ("fault_event_boundary_vectors", 3),
    ("cancel_phases", 5),
    ("reset_phases", 5),
    ("stall_cycles", 128),
    ("saturation_checks", 18),
    ("no_credit_checks", 1),
    ("max_field_vectors", 2),
    ("held_cancel_sequences", 11),
    ("reset_priority_checks", 1),
]
EXPECTED_CHECKS = 20013
EXPECTED_STRUCTURED_ROWS = 39

CASE_BEGIN = re.compile(r"CASE_BEGIN name=([a-z0-9_]+)")
CASE_END = re.compile(
    r"CASE_END name=([a-z0-9_]+) status=(pass|fail) checks=([0-9]+)"
)
STAT_ROW = re.compile(r"TB_STAT ([a-z_]+)=([0-9]+)")
BEGIN_ROW = re.compile(r"TB_BEGIN tb=([a-z0-9_]+)")
SUMMARY_ROW = re.compile(
    r"TB_SUMMARY cases=([0-9]+) pass=([0-9]+) fail=([0-9]+) "
    r"checks=([0-9]+)"
)


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_path(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
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
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            stripped = stripped[2:]
        elif stripped.startswith("#"):
            stripped = stripped[1:].lstrip()
        lines.append(stripped)
    return lines


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


def command_dir_name(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def command_metadata(record):
    return {
        key: value
        for key, value in record.items()
        if key not in ("stdout_bytes", "stderr_bytes")
    }


def run_command(attempt, name, argv, cwd, env, timeout):
    record_dir = attempt / "commands" / command_dir_name(name)
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
        "stdout_sha256": sha256_bytes(stdout_bytes),
        "stderr": str(stderr_path),
        "stderr_sha256": sha256_bytes(stderr_bytes),
    }
    write_json(record_dir / "command.json", record)
    record["stdout_bytes"] = stdout_bytes
    record["stderr_bytes"] = stderr_bytes
    return record


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
    return tools, bool(re.search(r"ModelSim\b.*\b10\.7\b", combined, re.DOTALL))


def git_run(args):
    return subprocess.run(
        ["git", *args],
        cwd=WORKTREE_ROOT,
        capture_output=True,
    )


def contract_check():
    show = git_run(["show", f"{CONTRACT_COMMIT}:{CONTRACT_REL}"])
    head = git_run(["rev-parse", "HEAD"])
    design = git_run(["cat-file", "-e", f"{EXPECTED_DESIGN_COMMIT}^{{commit}}"])
    ancestor = git_run(["merge-base", "--is-ancestor", CONTRACT_COMMIT, "HEAD"])
    base_exists = git_run(["cat-file", "-e", f"{EXPECTED_BASE_HEAD}^{{commit}}"])
    base_ancestor = git_run(["merge-base", "--is-ancestor", EXPECTED_BASE_HEAD, "HEAD"])
    parsed = None
    requirements_hash = None
    if show.returncode == 0:
        parsed = json.loads(show.stdout.decode("utf-8"))
        canonical = json.dumps(
            parsed["requirements"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        requirements_hash = sha256_bytes(canonical)
    contract_file_hash = sha256_bytes(show.stdout) if show.returncode == 0 else None
    current_contract_hash = sha256_path(CONTRACT_PATH) if CONTRACT_PATH.is_file() else None
    return {
        "contract_path": str(CONTRACT_PATH),
        "pinned_commit": CONTRACT_COMMIT,
        "show_exit": show.returncode,
        "show_stderr_utf8": show.stderr.decode("utf-8", errors="replace"),
        "contract_bytes": show.stdout,
        "contract_file_sha256": contract_file_hash,
        "current_contract_file_sha256": current_contract_hash,
        "contract_id": parsed.get("contract_id") if parsed else None,
        "revision": parsed.get("revision") if parsed else None,
        "ids": [item["id"] for item in parsed["requirements"]] if parsed else [],
        "requirements_sha256": requirements_hash,
        "pinned_is_ancestor": ancestor.returncode == 0,
        "head_exit": head.returncode,
        "head": head.stdout.decode("ascii", errors="replace").strip(),
        "head_stderr_utf8": head.stderr.decode("utf-8", errors="replace"),
        "design_commit": EXPECTED_DESIGN_COMMIT,
        "design_commit_exists": design.returncode == 0,
        "base_expected": EXPECTED_BASE_HEAD,
        "base_exists": base_exists.returncode == 0,
        "base_is_ancestor": base_ancestor.returncode == 0,
    }


def external_library_checks():
    cases = [
        (0x00, 0x00, 0x0000, 0x00000000, 0, b"", 0x50F6),
        (0xFF, 0xAA, 0xFFFF, 0xFFFFFFFF, 0, b"", 0x7D55),
        (0x01, 0x02, 0x1234, 0x89ABCDEF, 1, bytes((0x00,)), 0x9600),
        (0x05, 0x06, 0xABCD, 0x01020304, 3, bytes((0x31, 0x32, 0x33)), 0xA610),
    ]
    checked = []
    for typ, epoch, seq, tick, length, payload, expected in cases:
        covered = (
            bytes((0x03, typ, length, epoch))
            + struct.pack("<H", seq)
            + struct.pack("<I", tick)
            + payload
        )
        actual = binascii.crc_hqx(covered, 0xFFFF)
        checked.append(
            {
                "type": typ,
                "epoch": epoch,
                "seq": seq,
                "tick": tick,
                "len": length,
                "payload_hex": payload.hex(),
                "covered_hex": covered.hex(),
                "expected": expected,
                "library": actual,
                "match": actual == expected,
            }
        )
    sanity = binascii.crc_hqx(b"123456789", 0xFFFF)
    return {
        "implementation": "Python 3 binascii.crc_hqx",
        "standard_123456789": {"expected": 0x29B1, "library": sanity},
        "packet_cases": checked,
        "passed": sanity == 0x29B1 and all(item["match"] for item in checked),
    }


def parse_simulation(result, log_bytes):
    lines = normalized_lines(log_bytes)
    problems = ordinary_output_problems(lines)
    structured = [
        line
        for line in lines
        if line.startswith("TB_") or line.startswith("CASE_") or line.startswith("CHECK_")
    ]

    begins = [line for line in structured if BEGIN_ROW.fullmatch(line)]
    if len(begins) != 1:
        problems.append(f"TB_BEGIN count={len(begins)}")
    elif BEGIN_ROW.fullmatch(begins[0]).group(1) != "tb_wire_serializer":
        problems.append(f"TB_BEGIN mismatch: {begins[0]}")

    ends = [line for line in structured if line == "TB_END pass"]
    if len(ends) != 1:
        problems.append(f"TB_END pass count={len(ends)}")
    if any(line == "TB_END fail" for line in structured):
        problems.append("TB_END fail present")
    if any(line.startswith("CHECK_FAIL") for line in structured):
        problems.append("CHECK_FAIL present")

    case_index = 0
    case_active = False
    begin_names = []
    end_names = []
    case_rows = []
    for line in structured:
        begin = CASE_BEGIN.fullmatch(line)
        end = CASE_END.fullmatch(line)
        if begin:
            begin_names.append(begin.group(1))
            if case_active or case_index >= len(EXPECTED_CASES):
                problems.append(f"misaligned CASE_BEGIN: {line}")
            elif begin.group(1) != EXPECTED_CASES[case_index][0]:
                problems.append(f"unexpected CASE_BEGIN: {line}")
            case_active = True
        elif end:
            end_names.append(end.group(1))
            if not case_active or case_index >= len(EXPECTED_CASES):
                problems.append(f"misaligned CASE_END: {line}")
            elif end.group(1) != EXPECTED_CASES[case_index][0]:
                problems.append(f"unexpected CASE_END: {line}")
            if end.group(2) != "pass" or int(end.group(3)) != EXPECTED_CASES[case_index][1]:
                problems.append(f"failed or unexpected CASE_END: {line}")
            case_rows.append(
                {"name": end.group(1), "status": end.group(2), "checks": int(end.group(3))}
            )
            case_active = False
            case_index += 1
    if begin_names != [name for name, _ in EXPECTED_CASES]:
        problems.append(f"CASE_BEGIN sequence={begin_names}")
    if end_names != [name for name, _ in EXPECTED_CASES]:
        problems.append(f"CASE_END sequence={end_names}")
    if case_active or case_index != len(EXPECTED_CASES):
        problems.append("unclosed CASE scope")

    stats_rows = []
    for line in structured:
        if line.startswith("TB_STAT"):
            match = STAT_ROW.fullmatch(line)
            if not match:
                problems.append(f"ambiguous TB_STAT: {line}")
            else:
                stats_rows.append((match.group(1), int(match.group(2))))
    if stats_rows != EXPECTED_STATS:
        problems.append(f"TB_STAT rows={stats_rows} expected={EXPECTED_STATS}")

    summaries = [line for line in structured if line.startswith("TB_SUMMARY")]
    summary = None
    if len(summaries) != 1:
        problems.append(f"TB_SUMMARY count={len(summaries)}")
    else:
        match = SUMMARY_ROW.fullmatch(summaries[0])
        if not match:
            problems.append(f"ambiguous TB_SUMMARY: {summaries[0]}")
        else:
            summary = tuple(int(value) for value in match.groups())
            if summary != (len(EXPECTED_CASES), len(EXPECTED_CASES), 0, EXPECTED_CHECKS):
                problems.append(f"TB_SUMMARY values={summary}")

    recognized = 0
    for line in structured:
        if (
            line == "TB_END pass"
            or BEGIN_ROW.fullmatch(line)
            or CASE_BEGIN.fullmatch(line)
            or CASE_END.fullmatch(line)
            or STAT_ROW.fullmatch(line)
            or SUMMARY_ROW.fullmatch(line)
        ):
            recognized += 1
        else:
            problems.append(f"unknown or ambiguous marker: {line}")

    expected_sequence = ["TB_BEGIN"] + ["CASE"] * (2 * len(EXPECTED_CASES))
    expected_sequence += ["TB_STAT"] * len(EXPECTED_STATS)
    expected_sequence += ["TB_SUMMARY", "TB_END"]
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
        elif line == "TB_END pass":
            actual_sequence.append("TB_END")
    if actual_sequence != expected_sequence:
        problems.append(f"marker order={actual_sequence}")

    if len(structured) != EXPECTED_STRUCTURED_ROWS:
        problems.append(f"structured row count={len(structured)}")
    if lines.count("Errors: 0, Warnings: 0") != 1:
        problems.append("missing or duplicate zero error/warning tally")

    result["summary"] = summary
    result["stats"] = dict(stats_rows)
    result["cases"] = case_rows
    result["structured_rows"] = len(structured)
    result["problems"] = problems
    return not problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, help="new author attempt id")
    parser.add_argument(
        "--modelsim-root",
        default=os.environ.get("MODELSIM_ROOT", r"D:/modelsim1/win64"),
    )
    parser.add_argument(
        "--scope",
        default=os.environ.get("WIRE_SERIALIZER_SCOPE", str(DEFAULT_SCOPE)),
    )
    parser.add_argument(
        "--repair",
        default=os.environ.get("WIRE_SERIALIZER_REPAIR", str(DEFAULT_REPAIR)),
    )
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.attempt):
        parser.error("attempt id must contain only letters, digits, dot, underscore, or hyphen")
    for source in (RTL_SOURCE, CRC_SOURCE, TB_SOURCE, CANDIDATE_SOURCE, RUNNER_SOURCE):
        if not source.is_file():
            print(f"missing author source: {source}", file=sys.stderr)
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

    inputs = attempt / "inputs"
    source_inputs = inputs / "author-source"
    source_inputs.mkdir(parents=True)
    source_blobs = {
        "rtl": RTL_SOURCE.read_bytes(),
        "crc": CRC_SOURCE.read_bytes(),
        "tb": TB_SOURCE.read_bytes(),
        "candidate": CANDIDATE_SOURCE.read_bytes(),
        "runner": RUNNER_SOURCE.read_bytes(),
    }
    source_names = {
        "rtl": "deepeye_wire_serializer.sv",
        "crc": "deepeye_crc16_byte.sv",
        "tb": "tb_wire_serializer.sv",
        "candidate": "wire_serializer_candidate.md",
        "runner": "run_wire_serializer.py",
    }
    for key, blob in source_blobs.items():
        (source_inputs / source_names[key]).write_bytes(blob)
    initial_hashes = {key: sha256_bytes(blob) for key, blob in source_blobs.items()}
    (source_inputs / "sha256.txt").write_text(
        "".join(f"{initial_hashes[key]}  {source_names[key]}\n" for key in source_names),
        encoding="ascii",
        newline="\n",
    )

    contract = contract_check()
    (inputs / "contract.snapshot.json").write_bytes(contract["contract_bytes"])
    contract_public = {
        key: value
        for key, value in contract.items()
        if key != "contract_bytes"
    }
    contract_public["expected_requirements_sha256"] = EXPECTED_REQUIREMENTS_SHA256
    contract_public["passed"] = (
        contract["show_exit"] == 0
        and contract["contract_id"] == "DEEPEYE-HUMAN-LOCK-20261014"
        and contract["revision"] == 1
        and contract["ids"] == [f"H{i:02d}" for i in range(1, 16)]
        and contract["requirements_sha256"] == EXPECTED_REQUIREMENTS_SHA256
        and contract["pinned_is_ancestor"]
        and contract["design_commit_exists"]
        and contract["current_contract_file_sha256"] == contract["contract_file_sha256"]
    )
    write_json(inputs / "contract-verification.json", contract_public)

    scope_path = Path(args.scope)
    scope_public = {
        "path": str(scope_path),
        "expected_sha256": EXPECTED_SCOPE_SHA256,
        "available": scope_path.is_file(),
    }
    if scope_path.is_file():
        scope_bytes = scope_path.read_bytes()
        (inputs / "scope.snapshot.md").write_bytes(scope_bytes)
        scope_public["sha256"] = sha256_bytes(scope_bytes)
        scope_public["matches_expected"] = scope_public["sha256"] == EXPECTED_SCOPE_SHA256
    else:
        scope_public["sha256"] = None
        scope_public["matches_expected"] = None
        scope_public["absence_context_only"] = True
    write_json(inputs / "scope-verification.json", scope_public)

    repair_path = Path(args.repair)
    repair_public = {
        "repair_id": REPAIR_ID,
        "path": str(repair_path),
        "expected_sha256": EXPECTED_REPAIR_SHA256,
        "available": repair_path.is_file(),
    }
    if repair_path.is_file():
        repair_bytes = repair_path.read_bytes()
        (inputs / "repair1.snapshot.md").write_bytes(repair_bytes)
        repair_public["sha256"] = sha256_bytes(repair_bytes)
        repair_public["matches_expected"] = repair_public["sha256"] == EXPECTED_REPAIR_SHA256
    else:
        repair_public["sha256"] = None
        repair_public["matches_expected"] = False
    write_json(inputs / "repair1-verification.json", repair_public)

    library_checks = external_library_checks()
    write_json(inputs / "external-library-checks.json", library_checks)
    write_json(
        attempt / "environment.json",
        {
            "attempt": args.attempt,
            "product_root": str(PRODUCT_ROOT),
            "worktree_root": str(WORKTREE_ROOT),
            "modelsim_root": str(modelsim_root),
            "timeout_seconds": args.timeout,
            "source_hashes": initial_hashes,
            "expected_crc_sha256": EXPECTED_CRC_SHA256,
            "owned_temp": {key: env[key] for key in ("TEMP", "TMP", "TMPDIR")},
            "python_no_bytecode": env["PYTHONDONTWRITEBYTECODE"],
            "python_cache_prefix": env["PYTHONPYCACHEPREFIX"],
            "git_context": {
                "head": contract["head"],
                "expected_base": EXPECTED_BASE_HEAD,
                "base_exists": contract["base_exists"],
                "base_is_ancestor": contract["base_is_ancestor"],
                "context_only": True,
            },
            "contract": contract_public,
            "scope": scope_public,
            "repair": repair_public,
            "external_library_checks": library_checks,
        },
    )
    write_json(attempt / "runner-command.json", {"argv": sys.argv, "cwd": os.getcwd()})

    summary = {
        "attempt": args.attempt,
        "status": "running",
        "passed": False,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_hashes": initial_hashes,
        "expected_crc_sha256": EXPECTED_CRC_SHA256,
        "contract": contract_public,
        "scope": scope_public,
        "repair": repair_public,
        "external_library_checks": library_checks,
        "commands": [],
    }
    exit_code = 1
    try:
        if not contract_public["passed"]:
            summary["status"] = "contract-failed"
            summary["error"] = "pinned contract verification failed"
        elif scope_public["available"] and not scope_public["matches_expected"]:
            summary["status"] = "scope-failed"
            summary["error"] = "scope hash mismatch"
        elif not repair_public["available"] or not repair_public["matches_expected"]:
            summary["status"] = "repair-scope-failed"
            summary["error"] = "repair scope missing or hash mismatch"
        elif initial_hashes["crc"] != EXPECTED_CRC_SHA256:
            summary["status"] = "crc-dependency-failed"
            summary["error"] = "read-only CRC primitive hash mismatch"
        elif not library_checks["passed"]:
            summary["status"] = "library-crosscheck-failed"
            summary["error"] = "binascii.crc_hqx cross-check failed"
        else:
            tools, modelsim_10_7 = check_versions(attempt, env, modelsim_root, args.timeout)
            summary["tools"] = tools
            summary["modelsim_10_7"] = modelsim_10_7
            if not modelsim_10_7:
                summary["status"] = "toolchain-failed"
                summary["error"] = "ModelSim 10.7 not detected"
            else:
                work_dir = attempt / "work"
                work_dir.mkdir()
                vlib = run_command(
                    attempt,
                    "simulation/01-vlib-work",
                    [modelsim_root / "vlib.exe", "work"],
                    work_dir,
                    env,
                    args.timeout,
                )
                summary["commands"].append(command_metadata(vlib))
                if vlib["exit_code"] != 0 or vlib["timed_out"] or vlib["process_error"]:
                    summary["status"] = "vlib-failed"
                    summary["problems"] = ["vlib work did not succeed"]
                else:
                    vlog = run_command(
                        attempt,
                        "simulation/02-vlog",
                        [
                            modelsim_root / "vlog.exe",
                            "-sv",
                            "-work",
                            "work",
                            str(source_inputs / source_names["crc"]),
                            str(source_inputs / source_names["rtl"]),
                            str(source_inputs / source_names["tb"]),
                        ],
                        work_dir,
                        env,
                        args.timeout,
                    )
                    summary["commands"].append(command_metadata(vlog))
                    vlog_problems = ordinary_output_problems(
                        normalized_lines(vlog["stdout_bytes"] + b"\n" + vlog["stderr_bytes"])
                    )
                    if vlog["exit_code"] != 0 or vlog["timed_out"] or vlog["process_error"]:
                        vlog_problems.append("vlog did not succeed")
                    if vlog_problems:
                        summary["status"] = "vlog-failed"
                        summary["problems"] = vlog_problems
                    else:
                        log_path = work_dir / "vsim.log"
                        vsim = run_command(
                            attempt,
                            "simulation/03-vsim",
                            [
                                modelsim_root / "vsim.exe",
                                "-c",
                                "-l",
                                "vsim.log",
                                "-do",
                                "run -all; quit -f",
                                "tb_wire_serializer",
                            ],
                            work_dir,
                            env,
                            args.timeout,
                        )
                        summary["commands"].append(command_metadata(vsim))
                        if vsim["timed_out"] or vsim["process_error"]:
                            summary["status"] = "vsim-process-failed"
                            summary["problems"] = ["vsim timed out or failed to start"]
                        elif vsim["exit_code"] != 0:
                            summary["status"] = "vsim-failed"
                            summary["problems"] = [f"ordinary vsim exit={vsim['exit_code']}"]
                        elif not log_path.is_file() or log_path.stat().st_size == 0:
                            summary["status"] = "vsim-log-missing"
                            summary["problems"] = ["vsim.log missing or empty"]
                        else:
                            log_bytes = log_path.read_bytes()
                            log_copy = attempt / "vsim-log.txt"
                            log_copy.write_bytes(log_bytes)
                            result = {
                                "passed": False,
                                "summary": None,
                                "stats": None,
                                "cases": None,
                                "vsim_log": str(log_path),
                                "vsim_log_copy": str(log_copy),
                                "vsim_log_sha256": sha256_bytes(log_bytes),
                            }
                            result["passed"] = parse_simulation(result, log_bytes)
                            channel_problems = ordinary_output_problems(
                                normalized_lines(vsim["stdout_bytes"] + b"\n" + vsim["stderr_bytes"])
                            )
                            if channel_problems:
                                result["passed"] = False
                                result.setdefault("problems", []).extend(channel_problems)
                            summary["simulation_result"] = result

                            bad_log_path = work_dir / "vsim_bad_stat.log"
                            bad = run_command(
                                attempt,
                                "simulation/04-vsim-bad-stat",
                                [
                                    modelsim_root / "vsim.exe",
                                    "-c",
                                    "-l",
                                    "vsim_bad_stat.log",
                                    "-do",
                                    "run -all; quit -f",
                                    "tb_wire_serializer_bad_stat",
                                ],
                                work_dir,
                                env,
                                args.timeout,
                            )
                            summary["commands"].append(command_metadata(bad))
                            bad_bytes = bad["stdout_bytes"] + b"\n" + bad["stderr_bytes"]
                            bad_text = bad_bytes.decode("utf-8", errors="replace")
                            bad_passed = (
                                not bad["timed_out"]
                                and bad["process_error"] is None
                                and "** Fatal: deepeye_wire_serializer: STAT_W out of range" in bad_text
                                and "BAD_STAT_SENTINEL_REACHED" not in bad_text
                                and bad_log_path.is_file()
                            )
                            bad_record = {
                                "passed_expected_fatal": bad_passed,
                                "exit_code": bad["exit_code"],
                                "timed_out": bad["timed_out"],
                                "process_error": bad["process_error"],
                                "fatal_message_present": "** Fatal: deepeye_wire_serializer: STAT_W out of range" in bad_text,
                                "sentinel_absent": "BAD_STAT_SENTINEL_REACHED" not in bad_text,
                                "log_path": str(bad_log_path),
                                "log_sha256": sha256_bytes(bad_log_path.read_bytes()) if bad_log_path.is_file() else None,
                                "stdout_sha256": bad["stdout_sha256"],
                                "stderr_sha256": bad["stderr_sha256"],
                            }
                            if bad_log_path.is_file():
                                (attempt / "vsim-bad-stat-log.txt").write_bytes(bad_log_path.read_bytes())
                            summary["negative_parameter_probe"] = bad_record
                            if not bad_passed:
                                result["passed"] = False
                                result.setdefault("problems", []).append("STAT_W fatal probe failed")

                            summary["status"] = "pass" if result["passed"] else "simulation-failed"
                            if not result["passed"]:
                                summary["problems"] = result["problems"]

        source_unchanged = all(
            sha256_path(path) == initial_hashes[key]
            for key, path in (
                ("rtl", RTL_SOURCE),
                ("crc", CRC_SOURCE),
                ("tb", TB_SOURCE),
                ("candidate", CANDIDATE_SOURCE),
                ("runner", RUNNER_SOURCE),
            )
        )
        summary["source_unchanged_after_run"] = source_unchanged
        if not source_unchanged:
            summary["status"] = "source-changed"
            summary.setdefault("problems", []).append("author source changed during run")
        summary["passed"] = summary["status"] == "pass" and source_unchanged
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
                f"cases={summary.get('simulation_result', {}).get('summary')}",
                f"stats={summary.get('simulation_result', {}).get('stats')}",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
