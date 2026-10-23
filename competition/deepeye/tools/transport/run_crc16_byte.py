#!/usr/bin/env python3
"""Strict standalone author runner for the CRC16/CCITT-FALSE byte primitive."""

from __future__ import annotations

import argparse
import binascii
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
WORKTREE_ROOT = Path(__file__).resolve().parents[4]
MAIN_WORKSPACE_ROOT = WORKTREE_ROOT.parent.parent.parent
RTL_SOURCE = PRODUCT_ROOT / "fpga/transport/deepeye_crc16_byte.sv"
TB_SOURCE = PRODUCT_ROOT / "tests/rtl/transport/tb_crc16_byte.sv"
CANDIDATE_SOURCE = PRODUCT_ROOT / "fpga/transport/crc16_byte_candidate.md"
RUNNER_SOURCE = Path(__file__).resolve()
EVIDENCE_ROOT = (
    PRODUCT_ROOT / "evidence/transport/crc16-byte-20261024-27/author"
)
CONTRACT_PATH = WORKTREE_ROOT / "docs/competition/deepeye-2026/immutable_scope.json"
DEFAULT_SCOPE = (
    MAIN_WORKSPACE_ROOT
    / ".local/deployment/node-b/evidence/crc16-byte-20261024-27/SCOPE.md"
)

CONTRACT_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
CONTRACT_REL = "docs/competition/deepeye-2026/immutable_scope.json"
EXPECTED_SCOPE_SHA256 = (
    "dcef9850df99376b3fdb5b5c505505005a433629f8e6a01bc660630961de489a"
)
EXPECTED_REQUIREMENTS_SHA256 = (
    "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
)
EXPECTED_DESIGN_COMMIT = "1011259415a0916054eb580687612580bc1e5f09"
EXPECTED_BASE_HEAD = "b90fcbc58cdd7f3bf53fb6931dbdd47cd55afc8a"

EXPECTED_CASES = [
    "standard_vector",
    "zero_length_caller_seed",
    "all_values_seed_matrix",
    "all_states_selected_bytes",
    "stream_concatenation",
    "bit_order_contrast",
    "external_library_spots",
]
EXPECTED_STATS = [
    ("standard_bytes", 9),
    ("empty_seed_calls", 0),
    ("seed_matrix_vectors", 1536),
    ("state_byte_vectors", 196608),
    ("stream_bytes", 256),
    ("contrast_vectors", 4),
    ("external_vectors", 16),
]
EXPECTED_CHECKS = 198437

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


def contract_check():
    show = subprocess.run(
        ["git", "show", f"{CONTRACT_COMMIT}:{CONTRACT_REL}"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
    )
    design = subprocess.run(
        ["git", "cat-file", "-e", f"{EXPECTED_DESIGN_COMMIT}^{{commit}}"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
    )
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CONTRACT_COMMIT, "HEAD"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
    )
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
    return {
        "contract_path": str(CONTRACT_PATH),
        "pinned_commit": CONTRACT_COMMIT,
        "show_exit": show.returncode,
        "show_stderr_utf8": show.stderr.decode("utf-8", errors="replace"),
        "contract_bytes": show.stdout,
        "contract_file_sha256": sha256_bytes(show.stdout),
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
    }


def external_library_checks():
    spots = [
        (0x0000, 0x00, 0x0000),
        (0x0000, 0x01, 0x1021),
        (0x0000, 0x80, 0x9188),
        (0x0000, 0xA5, 0xE54F),
        (0x0000, 0xFF, 0x1EF0),
        (0xFFFF, 0x00, 0xE1F0),
        (0xFFFF, 0x01, 0xF1D1),
        (0xFFFF, 0x80, 0x7078),
        (0xFFFF, 0xA5, 0x04BF),
        (0xFFFF, 0xFF, 0xFF00),
        (0x1021, 0x00, 0x3331),
        (0x1021, 0x01, 0x2310),
        (0x1021, 0x80, 0xA2B9),
        (0x1021, 0xA5, 0xD67E),
        (0x1021, 0xFF, 0x2DC1),
        (0xA5C3, 0x00, 0x264F),
    ]
    checked = []
    for seed, value, expected in spots:
        actual = binascii.crc_hqx(bytes((value,)), seed)
        checked.append(
            {
                "seed": seed,
                "data": value,
                "expected": expected,
                "library": actual,
                "match": actual == expected,
            }
        )
    return {
        "implementation": "Python 3 binascii.crc_hqx",
        "standard": {
            "expected": 0x29B1,
            "library": binascii.crc_hqx(b"123456789", 0xFFFF),
        },
        "empty": {
            "expected": 0xFFFF,
            "library": binascii.crc_hqx(b"", 0xFFFF),
        },
        "stream_0_255": {
            "expected": 0x3FBD,
            "library": binascii.crc_hqx(bytes(range(256)), 0xFFFF),
        },
        "spots": checked,
        "passed": (
            binascii.crc_hqx(b"123456789", 0xFFFF) == 0x29B1
            and binascii.crc_hqx(b"", 0xFFFF) == 0xFFFF
            and binascii.crc_hqx(bytes(range(256)), 0xFFFF) == 0x3FBD
            and all(item["match"] for item in checked)
        ),
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
    elif BEGIN_ROW.fullmatch(begins[0]).group(1) != "tb_crc16_byte":
        problems.append(f"TB_BEGIN mismatch: {begins[0]}")

    if sum(line == "TB_END pass" for line in structured) != 1:
        problems.append("TB_END pass is not unique")
    if any(line == "TB_END fail" for line in structured):
        problems.append("TB_END fail present")

    case_index = 0
    case_active = False
    begin_names = []
    end_names = []
    for line in structured:
        begin = CASE_BEGIN.fullmatch(line)
        end = CASE_END.fullmatch(line)
        if begin:
            begin_names.append(begin.group(1))
            if case_active or case_index >= len(EXPECTED_CASES):
                problems.append(f"misaligned CASE_BEGIN: {line}")
            elif begin.group(1) != EXPECTED_CASES[case_index]:
                problems.append(f"unexpected CASE_BEGIN: {line}")
            case_active = True
        elif end:
            end_names.append(end.group(1))
            if not case_active or case_index >= len(EXPECTED_CASES):
                problems.append(f"misaligned CASE_END: {line}")
            elif end.group(1) != EXPECTED_CASES[case_index]:
                problems.append(f"unexpected CASE_END: {line}")
            if end.group(2) != "pass" or int(end.group(3)) == 0:
                problems.append(f"failed or empty CASE_END: {line}")
            case_active = False
            case_index += 1
    if begin_names != EXPECTED_CASES:
        problems.append(f"CASE_BEGIN sequence={begin_names}")
    if end_names != EXPECTED_CASES:
        problems.append(f"CASE_END sequence={end_names}")
    if case_active or case_index != len(EXPECTED_CASES):
        problems.append("unclosed CASE scope")

    stats = []
    for line in structured:
        if line.startswith("TB_STAT"):
            match = STAT_ROW.fullmatch(line)
            if not match:
                problems.append(f"ambiguous TB_STAT: {line}")
            else:
                stats.append((match.group(1), int(match.group(2))))
    if stats != EXPECTED_STATS:
        problems.append(f"TB_STAT rows={stats} expected={EXPECTED_STATS}")

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

    case_check_total = sum(int(CASE_END.fullmatch(row).group(3)) for row in structured if CASE_END.fullmatch(row))
    if case_check_total != EXPECTED_CHECKS:
        problems.append(f"case check total={case_check_total} expected={EXPECTED_CHECKS}")

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
    if any(line.startswith("CHECK_FAIL") for line in structured):
        problems.append("CHECK_FAIL present")

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

    result["summary"] = summary
    result["stats"] = dict(stats)
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
    parser.add_argument("--scope", default=os.environ.get("CRC16_SCOPE", str(DEFAULT_SCOPE)))
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.attempt):
        parser.error("attempt id must contain only letters, digits, dot, underscore, or hyphen")
    for source in (RTL_SOURCE, TB_SOURCE, CANDIDATE_SOURCE, RUNNER_SOURCE):
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
        "tb": TB_SOURCE.read_bytes(),
        "candidate": CANDIDATE_SOURCE.read_bytes(),
        "runner": RUNNER_SOURCE.read_bytes(),
    }
    source_names = {
        "rtl": "deepeye_crc16_byte.sv",
        "tb": "tb_crc16_byte.sv",
        "candidate": "crc16_byte_candidate.md",
        "runner": "run_crc16_byte.py",
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
    contract_public["current_contract_file_sha256"] = (
        sha256_path(CONTRACT_PATH) if CONTRACT_PATH.is_file() else None
    )
    contract_public["passed"] = (
        contract["show_exit"] == 0
        and contract["contract_id"] == "DEEPEYE-HUMAN-LOCK-20261014"
        and contract["revision"] == 1
        and contract["ids"] == [f"H{i:02d}" for i in range(1, 16)]
        and contract["requirements_sha256"] == EXPECTED_REQUIREMENTS_SHA256
        and contract["pinned_is_ancestor"]
        and contract["design_commit_exists"]
        and contract_public["current_contract_file_sha256"] == contract["contract_file_sha256"]
    )
    write_json(inputs / "contract-verification.json", contract_public)

    scope_path = Path(args.scope)
    scope_public = {"path": str(scope_path), "expected_sha256": EXPECTED_SCOPE_SHA256, "available": scope_path.is_file()}
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
            "owned_temp": {key: env[key] for key in ("TEMP", "TMP", "TMPDIR")},
            "python_no_bytecode": env["PYTHONDONTWRITEBYTECODE"],
            "python_cache_prefix": env["PYTHONPYCACHEPREFIX"],
            "git_context": {"head": contract["head"], "expected_base": EXPECTED_BASE_HEAD, "context_only": True},
            "contract": contract_public,
            "scope": scope_public,
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
        "contract": contract_public,
        "scope": scope_public,
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
        elif not library_checks["passed"]:
            summary["status"] = "library-crosscheck-failed"
            summary["error"] = "binascii.crc_hqx cross-check failed"
        else:
            tools, modelsim_10_7 = check_versions(attempt, env, modelsim_root, args.timeout)
            summary["tools"] = tools
            summary["modelsim_10_7"] = modelsim_10_7
            if not modelsim_10_7:
                summary["status"] = "toolchain-version-failed"
                summary["error"] = "ModelSim 10.7 version string not observed"
            else:
                work_dir = attempt / "work"
                work_dir.mkdir()
                vlib = run_command(
                    attempt, "simulation/01-vlib-work", [modelsim_root / "vlib.exe", "work"], work_dir, env, args.timeout
                )
                summary["commands"].append(command_metadata(vlib))
                if vlib["exit_code"] != 0 or vlib["timed_out"] or vlib["process_error"]:
                    summary["status"] = "vlib-failed"
                    summary["problems"] = ordinary_output_problems(
                        normalized_lines(vlib["stdout_bytes"] + b"\n" + vlib["stderr_bytes"])
                    ) + ["vlib work did not succeed"]
                else:
                    vlog = run_command(
                        attempt,
                        "simulation/02-vlog",
                        [
                            modelsim_root / "vlog.exe",
                            "-sv",
                            "-work",
                            "work",
                            source_inputs / source_names["rtl"],
                            source_inputs / source_names["tb"],
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
                                "tb_crc16_byte",
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
                            summary["status"] = "pass" if result["passed"] else "simulation-failed"
                            if not result["passed"]:
                                summary["problems"] = result["problems"]

            source_unchanged = all(
                sha256_path(path) == initial_hashes[key]
                for key, path in (
                    ("rtl", RTL_SOURCE),
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
