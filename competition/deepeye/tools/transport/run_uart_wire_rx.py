#!/usr/bin/env python3
"""Strict standalone author runner for deepeye_uart_wire_rx operation 31."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
TRANSPORT = ROOT / "competition/deepeye/fpga/transport"
TESTS = ROOT / "competition/deepeye/tests/rtl/transport"
EVIDENCE = (
    ROOT
    / "competition/deepeye/evidence/transport/uart-wire-rx-20261024-31/author"
)
SCOPE = (
    ROOT.parents[1]
    / "deployment/node-b/evidence/uart-wire-rx-20261024-31/SCOPE.md"
)
REPAIR_SCOPE = (
    ROOT.parents[1]
    / "deployment/node-b/evidence/uart-wire-rx-20261024-31/REPAIR1.md"
)
CONTRACT_JSON = ROOT / "docs/competition/deepeye-2026/immutable_scope.json"
CONTRACT_MD = ROOT / "docs/competition/deepeye-2026/immutable_scope.md"
TB = TESTS / "tb_uart_wire_rx.sv"
ATTEMPTS = EVIDENCE / "repair1" / "attempts"

MODELSIM = Path("D:/modelsim1/win64")
VLIB = MODELSIM / "vlib.exe"
VLOG = MODELSIM / "vlog.exe"
VSIM = MODELSIM / "vsim.exe"
PYTHON = Path("D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe")

EXPECTED_SCOPE_SHA = (
    "575bba8abfcacddcd6a445a0d56f0dacdca7e1bf976390b479dbff70c0f55a8b"
)
EXPECTED_REPAIR_SHA = (
    "aeec36032fcfd5bb6a36f4017d66d4fe3be5ae6cb213078977380af9fd2a03e1"
)
EXPECTED_REQUIREMENTS_SHA = (
    "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
)
EXPECTED_TB_SHA = (
    "3aca3b1bb4493cb45662b586383f608149b1ec925412e862a0e8d13be380eed0"
)
EXPECTED_DEPS = {
    "deepeye_uart_rx.sv": (
        "935f5d02008535fd5da75b7dc80696d14b03bd54d85f8b52fbf12c1e0504f08f"
    ),
    "deepeye_wire_parser.sv": (
        "7806c5d08785b96eae3708d9fd6d6002ef82faa4416a1f7244da73bece552649"
    ),
    "deepeye_crc16_byte.sv": (
        "8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f"
    ),
}
OWNED_INPUTS = [
    TRANSPORT / "deepeye_uart_wire_rx.sv",
    TRANSPORT / "uart_wire_rx_candidate.md",
    TESTS / "tb_uart_wire_rx.sv",
]
DEPENDENCY_INPUTS = [TRANSPORT / name for name in EXPECTED_DEPS]
FROZEN_DESIGN = "1011259415a0916054eb580687612580bc1e5f09"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_requirements_sha(value: dict) -> str:
    encoded = json.dumps(
        value["requirements"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(encoded)


def write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def write_json_new(path: Path, value: object) -> None:
    write_new(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


@dataclass(frozen=True)
class Suite:
    name: str
    suite_number: int
    clock_hz: int
    baud: int
    stat_w: int
    cases: tuple[tuple[str, int], ...]


DEFAULT_CASES = (("default_bounded", 52),)
FULL_CASES = tuple((f"len_{index}", 52) for index in range(33)) + (
    ("payload_all_bytes", 672),
    ("maxima_endianness", 52),
    ("adjacent_valid", 104),
    ("noise_prefix_recovery", 45),
    ("version_error_recovery", 64),
    ("length_error_recovery", 64),
    ("crc_error_recovery", 64),
    ("overrun_discard", 71),
    ("bad_stop_header", 66),
    ("bad_stop_payload", 66),
    ("bad_stop_crc", 66),
    ("false_start_header", 65),
    ("false_start_payload", 66),
    ("false_start_crc", 66),
    ("held_cancel_post_low", 61),
    ("retired_before_later_error", 14),
    ("cancel_idle", 57),
    ("cancel_header", 58),
    ("cancel_metadata", 58),
    ("cancel_payload", 58),
    ("cancel_crc", 58),
    ("cancel_completed", 59),
    ("reset_idle", 88),
    ("reset_header", 89),
    ("reset_metadata", 89),
    ("reset_payload", 89),
    ("reset_crc", 89),
    ("reset_completed", 90),
)
STAT2_CASES = (
    ("stat2_base_saturation", 161),
    ("stat2_version_saturation", 37),
    ("stat2_length_saturation", 37),
    ("stat2_crc_saturation", 37),
    ("stat2_false_start_saturation", 40),
    ("stat2_framing_saturation", 43),
    ("stat2_overrun_saturation", 58),
    ("stat2_all_saturated", 13),
)
SUITES = (
    Suite("default", 0, 100_000_000, 9_600, 32, DEFAULT_CASES),
    Suite("full", 1, 16_000_000, 500_000, 32, FULL_CASES),
    Suite("min_baud", 2, 16, 1, 32, (("min_baud_frame", 52),)),
    Suite(
        "fractional",
        3,
        16_000_000,
        115_200,
        32,
        (("fractional_baud_frame", 52),),
    ),
    Suite("stat2", 4, 16_000_000, 500_000, 2, STAT2_CASES),
)
GUARDS = (
    ("guard_clock_low", 15, 9_600, 32, "CLOCK_HZ"),
    ("guard_baud_low", 100_000_000, 0, 32, "BAUD"),
    ("guard_baud_high", 100_000_000, 6_250_001, 32, "BAUD"),
    ("guard_clock_priority", 15, 0, 1, "CLOCK_HZ"),
    ("guard_baud_priority", 100_000_000, 0, 1, "BAUD"),
    ("guard_stat_low", 100_000_000, 9_600, 1, "STAT_W"),
    ("guard_stat_high", 100_000_000, 9_600, 33, "STAT_W"),
)
EXPECTED_TOTAL_CASES = sum(len(suite.cases) for suite in SUITES)
EXPECTED_TOTAL_CHECKS = sum(
    checks for suite in SUITES for _, checks in suite.cases
)
EXPECTED_GUARDS = 7
EXPECTED_COMMANDS = 20
DIAGNOSTIC_PATTERN = re.compile(
    r"\*\*\s+(?:Error|Warning|Fatal)\b", re.IGNORECASE
)
TALLY_PATTERN = re.compile(r"Errors:\s*([0-9]+),\s*Warnings:\s*([0-9]+)")


class RunnerFailure(RuntimeError):
    pass


def create_attempt() -> Path:
    ATTEMPTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    base = ATTEMPTS / f"attempt-{stamp}-p{os.getpid()}"
    for suffix in range(100):
        candidate = base if suffix == 0 else Path(f"{base}-{suffix:02d}")
        try:
            candidate.mkdir()
            for child in ("inputs", "raw", "sim", "temp", "pycache"):
                (candidate / child).mkdir()
            return candidate
        except FileExistsError:
            continue
    raise RunnerFailure("could not allocate a fresh attempt directory")


def command_environment(attempt: Path) -> dict[str, str]:
    env = os.environ.copy()
    temp = str((attempt / "temp").resolve())
    cache = str((attempt / "pycache").resolve())
    env["TEMP"] = temp
    env["TMP"] = temp
    env["TMPDIR"] = temp
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = cache
    return env


def run_command(
    attempt: Path,
    index: int,
    label: str,
    argv: list[str],
    expected_exits: tuple[int, ...],
    timeout_s: float,
    kind: str = "command",
) -> dict:
    raw_dir = attempt / "raw" / f"{index:03d}_{label}"
    raw_dir.mkdir()
    started = utc_now()
    mono = time.monotonic()
    timed_out = False
    timeout_detail = ""
    try:
        completed = subprocess.run(
            argv,
            cwd=attempt / "sim",
            env=command_environment(attempt),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        returncode = None
        timeout_detail = f"timeout after {timeout_s:.3f}s"
    duration = time.monotonic() - mono
    write_new(raw_dir / "stdout.raw", stdout)
    write_new(raw_dir / "stderr.raw", stderr)
    record = {
        "index": index,
        "label": label,
        "kind": kind,
        "argv": argv,
        "cwd": str((attempt / "sim").resolve()),
        "started_utc": started,
        "duration_s": round(duration, 6),
        "timeout_s": timeout_s,
        "timed_out": timed_out,
        "timeout_detail": timeout_detail,
        "returncode": returncode,
        "expected_exits": list(expected_exits),
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "stdout_size": len(stdout),
        "stderr_size": len(stderr),
        "raw_stdout": str((raw_dir / "stdout.raw").relative_to(attempt)),
        "raw_stderr": str((raw_dir / "stderr.raw").relative_to(attempt)),
    }
    expected = (not timed_out) and (returncode in expected_exits)
    record["accepted_exit"] = expected
    write_json_new(raw_dir / "command.json", record)
    marker = "PASS" if expected else "FAIL"
    print(
        f"COMMAND {index:03d} {marker} {label} "
        f"exit={returncode} timeout={timed_out}"
    )
    return record


def combine_output(record: dict, attempt: Path) -> bytes:
    stdout = (attempt / record["raw_stdout"]).read_bytes()
    stderr = (attempt / record["raw_stderr"]).read_bytes()
    return stdout + (b"" if stdout.endswith(b"\n") else b"\n") + stderr


def snapshot_inputs(attempt: Path) -> dict:
    scope_bytes = SCOPE.read_bytes()
    scope_sha = sha256_bytes(scope_bytes)
    if scope_sha != EXPECTED_SCOPE_SHA:
        raise RunnerFailure(
            f"scope SHA mismatch: {scope_sha} != {EXPECTED_SCOPE_SHA}"
        )
    repair_bytes = REPAIR_SCOPE.read_bytes()
    repair_sha = sha256_bytes(repair_bytes)
    if repair_sha != EXPECTED_REPAIR_SHA:
        raise RunnerFailure(
            f"repair scope SHA mismatch: {repair_sha} != {EXPECTED_REPAIR_SHA}"
        )

    contract_bytes = CONTRACT_JSON.read_bytes()
    contract = json.loads(contract_bytes.decode("utf-8"))
    requirements = contract.get("requirements")
    if not isinstance(requirements, list) or len(requirements) != 15:
        raise RunnerFailure("contract requirements are not a 15-item array")
    requirement_ids = [str(item.get("id", "")) for item in requirements]
    expected_ids = [f"H{index:02d}" for index in range(1, 16)]
    if requirement_ids != expected_ids:
        raise RunnerFailure(
            f"requirements IDs/order mismatch: {requirement_ids!r}"
        )
    requirements_sha = canonical_requirements_sha(contract)
    if requirements_sha != EXPECTED_REQUIREMENTS_SHA:
        raise RunnerFailure(
            "canonical requirements SHA mismatch: "
            f"{requirements_sha} != {EXPECTED_REQUIREMENTS_SHA}"
        )

    inputs: list[tuple[Path, str, str | None]] = [
        (SCOPE, "scope", EXPECTED_SCOPE_SHA),
        (REPAIR_SCOPE, "repair_scope", EXPECTED_REPAIR_SHA),
        (CONTRACT_JSON, "contract_json", None),
        (CONTRACT_MD, "contract_md", None),
    ]
    inputs.extend(
        (
            path,
            "owned_source",
            EXPECTED_TB_SHA if path == TB else None,
        )
        for path in OWNED_INPUTS
    )
    inputs.append((Path(__file__).resolve(), "owned_source", None))
    inputs.extend(
        (path, "readonly_dependency", EXPECTED_DEPS[path.name])
        for path in DEPENDENCY_INPUTS
    )

    manifest = []
    used_names: set[str] = set()
    for path, role, expected_sha in inputs:
        data = path.read_bytes()
        actual_sha = sha256_bytes(data)
        if expected_sha is not None and actual_sha != expected_sha:
            raise RunnerFailure(
                f"read-only input SHA mismatch {path.name}: "
                f"{actual_sha} != {expected_sha}"
            )
        snapshot_name = path.name
        if snapshot_name in used_names:
            snapshot_name = f"{role}-{snapshot_name}"
        used_names.add(snapshot_name)
        snapshot = attempt / "inputs" / snapshot_name
        write_new(snapshot, data)
        manifest.append(
            {
                "role": role,
                "source_path": str(path.resolve()),
                "snapshot": str(snapshot.relative_to(attempt)),
                "sha256": actual_sha,
                "expected_sha256": expected_sha,
                "size": len(data),
            }
        )
    result = {
        "scope_sha256": scope_sha,
        "repair_scope_sha256": repair_sha,
        "requirements_sha256": requirements_sha,
        "requirements_ids": requirement_ids,
        "contract_raw_sha256": sha256_bytes(contract_bytes),
        "inputs": manifest,
    }
    write_json_new(attempt / "inputs_manifest.json", result)
    return result


def decode_output(data: bytes, label: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RunnerFailure(f"{label}: non-UTF-8 simulator output: {exc}") from exc


def normalize_sim_line(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith("#"):
        stripped = stripped[1:]
        if stripped.startswith(" "):
            stripped = stripped[1:]
    return stripped.strip()


def normalized_log_lines(text: str) -> list[str]:
    return [normalize_sim_line(line) for line in text.splitlines()]


def parse_diagnostic_tally(text: str, label: str) -> tuple[int, int]:
    lines = normalized_log_lines(text)
    candidates = [
        (index, line)
        for index, line in enumerate(lines)
        if "Errors:" in line or "Warnings:" in line
    ]
    malformed = [
        (index, line)
        for index, line in candidates
        if TALLY_PATTERN.fullmatch(line) is None
    ]
    if malformed:
        index, line = malformed[0]
        raise RunnerFailure(
            f"{label}: malformed/conflicting diagnostic tally at "
            f"log line {index + 1}: {line!r}"
        )
    if len(candidates) != 1:
        raise RunnerFailure(
            f"{label}: requires exactly one diagnostic tally, "
            f"found {len(candidates)}"
        )
    tally_index, tally_line = candidates[0]
    nonblank = [index for index, line in enumerate(lines) if line]
    if not nonblank or tally_index != nonblank[-1]:
        raise RunnerFailure(
            f"{label}: diagnostic tally is not the final nonblank line"
        )
    match = TALLY_PATTERN.fullmatch(tally_line)
    assert match is not None
    return int(match.group(1)), int(match.group(2))


def validate_diagnostic_tally(
    text: str,
    expected: tuple[int, int],
    label: str,
    allowed_fatal: str | None = None,
) -> dict[str, int]:
    counts = parse_diagnostic_tally(text, label)
    if counts != expected:
        raise RunnerFailure(
            f"{label}: diagnostics are {counts!r}, expected {expected!r}"
        )
    diagnostics = [
        (index, line)
        for index, line in enumerate(normalized_log_lines(text))
        if DIAGNOSTIC_PATTERN.search(line)
    ]
    if allowed_fatal is None:
        if diagnostics:
            index, line = diagnostics[0]
            raise RunnerFailure(
                f"{label}: forbidden diagnostic at log line {index + 1}: "
                f"{line!r}"
            )
    else:
        exact_fatal = [line for _, line in diagnostics if line == allowed_fatal]
        if len(exact_fatal) != 1:
            raise RunnerFailure(
                f"{label}: requires exactly one allowed fatal, "
                f"found {len(exact_fatal)}"
            )
        forbidden = [
            (index, line) for index, line in diagnostics if line != allowed_fatal
        ]
        if forbidden:
            index, line = forbidden[0]
            raise RunnerFailure(
                f"{label}: additional diagnostic at log line {index + 1}: "
                f"{line!r}"
            )
    return {"errors": counts[0], "warnings": counts[1]}


def marker_family_rows(text: str) -> list[tuple[int, str]]:
    return [
        (index, line)
        for index, line in enumerate(normalized_log_lines(text), start=1)
        if "WIRE_RX" in line
    ]


def expected_normal_markers(suite: Suite) -> list[str]:
    total_cases = len(suite.cases)
    total_checks = sum(checks for _, checks in suite.cases)
    rows = [
        f"WIRE_RX_BEGIN suite={suite.name} clock_hz={suite.clock_hz} "
        f"baud={suite.baud} stat_w={suite.stat_w}"
    ]
    rows.extend(
        f"WIRE_RX_CASE suite={suite.name} case={case} "
        f"checks={checks} status=PASS"
        for case, checks in suite.cases
    )
    rows.extend(
        [
            f"WIRE_RX_TALLY suite={suite.name} cases={total_cases} "
            f"checks={total_checks} failures=0",
            f"WIRE_RX_STATUS suite={suite.name} result=PASS",
        ]
    )
    if len(rows) != len(set(rows)):
        raise RunnerFailure(f"{suite.name}: expected marker rows are not unique")
    return rows


def require_normal_markers(text: str, suite: Suite, label: str) -> list[str]:
    expected = expected_normal_markers(suite)
    observed_rows = marker_family_rows(text)
    observed = [line for _, line in observed_rows]
    if observed == expected:
        return expected
    mismatch = next(
        (
            index
            for index, pair in enumerate(zip(observed, expected))
            if pair[0] != pair[1]
        ),
        min(len(observed), len(expected)),
    )
    if mismatch >= len(observed):
        raise RunnerFailure(
            f"{label}: missing ordered marker {mismatch + 1}: "
            f"{expected[mismatch]!r}"
        )
    if mismatch >= len(expected):
        line_number, line = observed_rows[mismatch]
        raise RunnerFailure(
            f"{label}: unexpected marker-family row at log line "
            f"{line_number}: {line!r}"
        )
    line_number, line = observed_rows[mismatch]
    raise RunnerFailure(
        f"{label}: marker {mismatch + 1} mismatch at log line {line_number}: "
        f"expected {expected[mismatch]!r}, observed {line!r}"
    )


def parse_normal_suite(
    data: bytes,
    suite: Suite,
    label: str,
) -> dict:
    text = decode_output(data, label)
    diagnostics = validate_diagnostic_tally(text, (0, 0), f"{label} simulation")
    markers = require_normal_markers(text, suite, label)
    total_checks = sum(checks for _, checks in suite.cases)
    return {
        "name": suite.name,
        "status": "PASS",
        "cases": len(suite.cases),
        "checks": total_checks,
        "failures": 0,
        "markers": markers,
        "marker_count": len(markers),
        "diagnostics": diagnostics,
    }


def parse_guard(
    data: bytes,
    label: str,
    expected_parameter: str,
) -> dict:
    text = decode_output(data, label)
    normalized = normalized_log_lines(text)
    marker_rows = [line for line in normalized if "WIRE_RX" in line]
    if marker_rows:
        raise RunnerFailure(f"{label}: testbench markers present in guard probe")
    for line in normalized:
        upper = line.upper()
        for token in ("FALLBACK", "SUCCESS", "GUARD_MISSING"):
            if token in upper:
                raise RunnerFailure(
                    f"{label}: forbidden guard success/fallback token {token!r}"
                )
    expected_message = (
        f"deepeye_uart_wire_rx: {expected_parameter} out of range"
    )
    expected_fatal = f"** Fatal: {expected_message}"
    diagnostics = validate_diagnostic_tally(
        text,
        (1, 0),
        f"{label} guard simulation",
        allowed_fatal=expected_fatal,
    )
    out_of_range = [
        (index, line)
        for index, line in enumerate(normalized, start=1)
        if "out of range" in line
    ]
    if not out_of_range:
        raise RunnerFailure(
            f"{label}: expected one {expected_parameter} guard, found none"
        )
    if len(out_of_range) != 1 or out_of_range[0][1] != expected_fatal:
        line_number, line = out_of_range[0]
        raise RunnerFailure(
            f"{label}: conflicting guard text at log line {line_number}: "
            f"{line!r}"
        )
    return {
        "status": "PASS",
        "expected_parameter": expected_parameter,
        "fatal_line": expected_fatal,
        "fatal_marker_count": 1,
        "marker_family_count": 0,
        "diagnostics": diagnostics,
    }


def require_version(
    attempt: Path,
    record: dict,
    product: str,
    min_version: str,
) -> None:
    text = decode_output(combine_output(record, attempt), record["label"])
    if f"{product} {min_version}" not in text:
        raise RunnerFailure(
            f"{record['label']}: expected {product} {min_version} in output"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--author-thread", default="")
    parser.add_argument("--author-turn", default="")
    args = parser.parse_args(argv)

    attempt = create_attempt()
    started_utc = utc_now()
    print(f"ATTEMPT {attempt}")
    meta = {
        "task_id": "DEEPEYE-IMPLEMENTATION-20261014",
        "task_version": 1,
        "operation_id": "B-DEEPEYE-UART-WIRE-RX-20261024-31",
        "scope_path": str(SCOPE.resolve()),
        "scope_sha256_expected": EXPECTED_SCOPE_SHA,
        "requirements_sha256_expected": EXPECTED_REQUIREMENTS_SHA,
        "frozen_design": FROZEN_DESIGN,
        "parent_thread": "01a13b55-095b-7461-8dd5-5476a130bd82",
        "parent_turn": "01a16933-edc1-7022-8e5f-25b4561a4ea5",
        "author_thread": args.author_thread,
        "author_turn": args.author_turn,
        "started_utc": started_utc,
        "runner": str(Path(__file__).resolve()),
        "argv": [sys.executable, str(Path(__file__).resolve()), *(argv or [])],
        "limits": {
            "all29_exhaustive": "not_run",
            "b04": "not_run",
            "r03": "not_run",
            "full_product": "not_run",
            "synthesis": "not_run",
            "implementation": "not_run",
            "timing": "not_run",
            "cdc_rdc": "not_run",
            "board": "not_run",
            "system": "not_run",
        },
    }
    write_json_new(attempt / "attempt_meta.json", meta)

    commands: list[dict] = []
    failure_reasons: list[str] = []
    suite_results: list[dict] = []
    guard_results: list[dict] = []
    input_manifest: dict = {}
    version_checks: dict[str, str] = {}
    command_index = 0

    def record(
        label: str,
        command_argv: list[str],
        expected_exits: tuple[int, ...],
        timeout_s: float,
        kind: str = "command",
    ) -> dict:
        nonlocal command_index
        item = run_command(
            attempt,
            command_index,
            label,
            command_argv,
            expected_exits,
            timeout_s,
            kind,
        )
        command_index += 1
        commands.append(item)
        return item

    try:
        input_manifest = snapshot_inputs(attempt)

        python_version = record(
            "python_version",
            [str(PYTHON), "-c", "import sys; print(sys.version); print(sys.executable)"],
            (0,),
            30,
            "tool_probe",
        )
        if not python_version["accepted_exit"]:
            failure_reasons.append("Python version probe failed")

        vlib_version = record(
            "vlib_version",
            [str(VLIB), "-version"],
            (0, 1),
            30,
            "tool_probe",
        )
        vlib_text = decode_output(
            combine_output(vlib_version, attempt), vlib_version["label"]
        )
        if (
            vlib_version["returncode"] != 1
            or not vlib_version["accepted_exit"]
            or "Usage: vlib" not in vlib_text
        ):
            failure_reasons.append(
                "vlib -version did not produce its observed usage/exit-1 probe"
            )
        else:
            version_checks["vlib"] = "usage-exit-1"

        vlog_version = record(
            "vlog_version", [str(VLOG), "-version"], (0,), 30, "tool_probe"
        )
        vsim_version = record(
            "vsim_version", [str(VSIM), "-version"], (0,), 30, "tool_probe"
        )
        if vlog_version["accepted_exit"]:
            require_version(attempt, vlog_version, "vlog", "10.7")
            version_checks["vlog"] = "10.7"
        else:
            failure_reasons.append("vlog version probe failed")
        if vsim_version["accepted_exit"]:
            require_version(attempt, vsim_version, "vsim", "10.7")
            version_checks["vsim"] = "10.7"
        else:
            failure_reasons.append("vsim version probe failed")

        git = shutil.which("git")
        if git is None:
            failure_reasons.append("git executable unavailable for design ancestry")
        else:
            head_record = record(
                "git_head",
                [git, "-C", str(ROOT), "rev-parse", "HEAD"],
                (0,),
                30,
                "git_probe",
            )
            ancestry_record = record(
                "git_design_ancestor",
                [
                    git,
                    "-C",
                    str(ROOT),
                    "merge-base",
                    "--is-ancestor",
                    FROZEN_DESIGN,
                    "HEAD",
                ],
                (0,),
                30,
                "git_probe",
            )
            if not head_record["accepted_exit"]:
                failure_reasons.append("could not read current HEAD")
            if not ancestry_record["accepted_exit"]:
                failure_reasons.append("frozen design is not an ancestor of HEAD")

        snapshot_by_name = {
            Path(item["source_path"]).name: attempt / item["snapshot"]
            for item in input_manifest["inputs"]
        }
        compile_sources = [
            snapshot_by_name["deepeye_crc16_byte.sv"],
            snapshot_by_name["deepeye_uart_rx.sv"],
            snapshot_by_name["deepeye_wire_parser.sv"],
            snapshot_by_name["deepeye_uart_wire_rx.sv"],
            snapshot_by_name["tb_uart_wire_rx.sv"],
        ]

        vlib_work = record(
            "vlib_work", [str(VLIB), "work"], (0,), 60, "compile"
        )
        compiled = vlib_work["accepted_exit"]
        if not compiled:
            failure_reasons.append("vlib work failed")
        else:
            vlog_compile = record(
                "vlog_compile",
                [
                    str(VLOG),
                    "-sv",
                    "-work",
                    "work",
                    *(str(path) for path in compile_sources),
                ],
                (0,),
                180,
                "compile",
            )
            compiled = vlog_compile["accepted_exit"]
            if not compiled:
                failure_reasons.append("SystemVerilog compilation failed")

        if compiled:
            for suite in SUITES:
                label = f"vsim_suite_{suite.name}"
                suite_record = record(
                    label,
                    [
                        str(VSIM),
                        "-c",
                        "tb_uart_wire_rx",
                        f"-gSUITE={suite.suite_number}",
                        f"-gCLOCK_HZ={suite.clock_hz}",
                        f"-gBAUD={suite.baud}",
                        f"-gSTAT_W={suite.stat_w}",
                        "-do",
                        "run -all; quit -f",
                    ],
                    (0,),
                    300,
                    "simulation",
                )
                if not suite_record["accepted_exit"]:
                    failure_reasons.append(
                        f"{suite.name}: simulation command rejected "
                        f"(exit={suite_record['returncode']}, "
                        f"timeout={suite_record['timed_out']})"
                    )
                    continue
                try:
                    suite_result = parse_normal_suite(
                        combine_output(suite_record, attempt),
                        suite,
                        suite.name,
                    )
                    suite_result["command_index"] = suite_record["index"]
                    suite_results.append(suite_result)
                except RunnerFailure as exc:
                    failure_reasons.append(str(exc))

            for guard_label, clock_hz, baud, stat_w, expected_parameter in GUARDS:
                guard_record = record(
                    f"vsim_{guard_label}",
                    [
                        str(VSIM),
                        "-c",
                        "tb_uart_wire_rx",
                        f"-gSUITE={5}",
                        f"-gCLOCK_HZ={clock_hz}",
                        f"-gBAUD={baud}",
                        f"-gSTAT_W={stat_w}",
                        "-do",
                        "run -all; quit -f",
                    ],
                    (0,),
                    120,
                    "guard_probe",
                )
                if not guard_record["accepted_exit"]:
                    failure_reasons.append(
                        f"{guard_label}: expected vsim/quit exit 0, got "
                        f"exit={guard_record['returncode']} "
                        f"timeout={guard_record['timed_out']}"
                    )
                    continue
                try:
                    guard_result = parse_guard(
                        combine_output(guard_record, attempt),
                        guard_label,
                        expected_parameter,
                    )
                    guard_result["label"] = guard_label
                    guard_result["command_index"] = guard_record["index"]
                    guard_results.append(guard_result)
                except RunnerFailure as exc:
                    failure_reasons.append(str(exc))
    except Exception as exc:  # preserve every incomplete attempt
        failure_reasons.append(f"{type(exc).__name__}: {exc}")

    total_cases = sum(item["cases"] for item in suite_results)
    total_checks = sum(item["checks"] for item in suite_results)
    if len(commands) != EXPECTED_COMMANDS:
        failure_reasons.append(
            f"command count {len(commands)} != {EXPECTED_COMMANDS}"
        )
    if len(suite_results) != len(SUITES):
        failure_reasons.append(
            f"passing suite count {len(suite_results)} != {len(SUITES)}"
        )
    if len(guard_results) != EXPECTED_GUARDS:
        failure_reasons.append(
            f"passing guard count {len(guard_results)} != {EXPECTED_GUARDS}"
        )
    if total_cases != EXPECTED_TOTAL_CASES:
        failure_reasons.append(
            f"case total {total_cases} != {EXPECTED_TOTAL_CASES}"
        )
    if total_checks != EXPECTED_TOTAL_CHECKS:
        failure_reasons.append(
            f"check total {total_checks} != {EXPECTED_TOTAL_CHECKS}"
        )
    status = "PASS" if not failure_reasons else "FAIL"
    summary = {
        "status": status,
        "failure_reasons": failure_reasons,
        "started_utc": started_utc,
        "finished_utc": utc_now(),
        "attempt": str(attempt),
        "meta": meta,
        "inputs": input_manifest,
        "version_checks": version_checks,
        "suite_results": suite_results,
        "guard_results": guard_results,
        "total_cases": total_cases,
        "total_checks": total_checks,
        "expected_totals": {
            "commands": EXPECTED_COMMANDS,
            "suites": len(SUITES),
            "cases": EXPECTED_TOTAL_CASES,
            "checks": EXPECTED_TOTAL_CHECKS,
            "guards": EXPECTED_GUARDS,
        },
        "commands": commands,
        "limitations": meta["limits"],
    }
    write_json_new(attempt / "summary.json", summary)
    summary_text = (
        f"RUN_STATUS {status}\n"
        f"ATTEMPT {attempt}\n"
        f"CASES {total_cases}\n"
        f"CHECKS {total_checks}\n"
        f"FAILURE_REASONS {len(failure_reasons)}\n"
        + "".join(f"FAIL {reason}\n" for reason in failure_reasons)
    )
    write_new(attempt / "RUN_SUMMARY.txt", summary_text.encode("utf-8"))
    print(
        f"RESULT {status} cases={total_cases} checks={total_checks} "
        f"failures={len(failure_reasons)}"
    )
    for reason in failure_reasons:
        print(f"FAIL {reason}")
    print(f"SUMMARY {attempt / 'summary.json'}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
