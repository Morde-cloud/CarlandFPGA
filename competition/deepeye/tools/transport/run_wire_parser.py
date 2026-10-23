#!/usr/bin/env python3
"""Strict, evidence-preserving ModelSim runner for deepeye_wire_parser.

Every invocation creates a fresh immutable attempt directory. No failed
attempt, raw process stream, command, or hash is deleted or rewritten.
"""

from __future__ import annotations

import argparse
import binascii
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014/v1"
ORIGINAL_WORK_ID = "B-WIRE-PARSER-20261024-29-v1"
WORK_ID = "B-WIRE-PARSER-RUNNER-QUALIFY-20261024-29-r2"
OPERATION_ID = "B-DEEPEYE-WIRE-PARSER-20261024-29"
FROZEN_DESIGN_COMMIT = "1011259415a0916054eb580687612580bc1e5f09"
CONTRACT_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
CONTRACT_PATH = "docs/competition/deepeye-2026/immutable_scope.json"
CONTRACT_REQUIREMENTS_SHA256 = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
ALLOWED_SCOPES = {
    "fdb76b1128882c15078f2d527456fc9296bd14e4a267beb714db7a50e760f9f3": "operation29_scope",
    "f52064bea4f078084a846b3f0b938834ed432cd913243a7d7b3b937a418381c6": "repair1_scope",
    "7470587189d6e423c27f7679d29196a424b704c7989ee73336699aaae9db425d": "runner_repair2_scope",
}
EXPECTED_CRC_SHA256 = "8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f"
EXPECTED_CONTEXT_BASE = "11e24d80ebf2acf822a7b45d3c3c346eb2a4d7cc"
EXPECTED_REQUIREMENT_IDS = ["H%02d" % number for number in range(1, 16)]
EXPECTED_CASES: List[Tuple[str, int]] = [
    ("reset_and_receiving", 37),
    ("lengths_0_32", 535),
    ("all_256_byte_values", 119),
    ("metadata_endian_and_maxima", 31),
    ("stdlib_crc_vectors", 697),
    ("noise_prefix_resync", 29),
    ("truncation_no_timeout", 26),
    ("corrupt_version", 28),
    ("corrupt_length", 26),
    ("corrupt_crc_no_rescan", 47),
    ("output_stall_input_hold", 85),
    ("retire_edge_no_credit", 28),
    ("zero_tail_reuse", 43),
    ("cancel_each_phase", 440),
    ("reset_each_phase", 616),
    ("small_stat_saturation", 35),
    ("error_pulse_and_recovery", 25),
    ("reset_cancel_priority", 36),
    ("sync_partial_abort_gates", 108),
    ("sync_error_abort_gates", 180),
    ("sync_output_abort_gates", 87),
]
HISTORICAL_18_CASES: List[Tuple[str, int]] = EXPECTED_CASES[:18]
FIXTURE_COUNT = 49
EXPECTED_TOTAL_CHECKS = sum(count for _, count in EXPECTED_CASES)
WIRE_PARSER_MARKER_FAMILY = "WIRE_PARSER_"
GUARD_FATAL_MESSAGE = "** Fatal: deepeye_wire_parser: STAT_W out of range"
DIAGNOSTIC_PATTERN = re.compile(r"\*\*\s+(Error|Warning|Fatal)\b")
TALLY_PATTERN = re.compile(r"^Errors:\s*(\d+),\s*Warnings:\s*(\d+)$")


class RunnerFailure(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(json_bytes(value))
    os.replace(temporary, path)


def decode_process_output(data: bytes) -> str:
    if not data:
        return ""
    if data.startswith(b"\xff\xfe"):
        return data.decode("utf-16-le", errors="replace")
    if len(data) >= 4 and data[1::2].count(0) > len(data) // 4:
        return data.decode("utf-16-le", errors="replace")
    return data.decode("utf-8", errors="replace")


def command_line(arguments: Sequence[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(arguments))
    import shlex
    return shlex.join(list(arguments))


def safe_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")
    return cleaned or "attempt"


def relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def normalized_log_lines(text: str) -> List[str]:
    return [re.sub(r"^#\s?", "", line.strip()) for line in text.splitlines()]


def validate_diagnostic_tally(
    text: str,
    expected: Tuple[int, int],
    label: str,
    allowed_fatal: Optional[str] = None,
) -> Dict[str, int]:
    lines = normalized_log_lines(text)
    tally_candidates = [
        (index, line)
        for index, line in enumerate(lines)
        if line.startswith("Errors:") or line.startswith("Warnings:") or "Errors:" in line or "Warnings:" in line
    ]
    malformed = [(index, line) for index, line in tally_candidates if TALLY_PATTERN.fullmatch(line) is None]
    if malformed:
        raise RunnerFailure("malformed/conflicting %s diagnostic tally at line %d: %r" % (
            label, malformed[0][0] + 1, malformed[0][1]))
    if len(tally_candidates) != 1:
        raise RunnerFailure("%s requires exactly one diagnostic tally, found %d" % (label, len(tally_candidates)))
    tally_index, tally_line = tally_candidates[0]
    nonblank = [index for index, line in enumerate(lines) if line]
    if not nonblank or tally_index != nonblank[-1]:
        raise RunnerFailure("%s diagnostic tally is not the final nonblank line" % label)
    match = TALLY_PATTERN.fullmatch(tally_line)
    assert match is not None
    counts = (int(match.group(1)), int(match.group(2)))
    if counts != expected:
        raise RunnerFailure("%s diagnostics are %r, expected %r" % (label, counts, expected))

    diagnostics = [(index, line) for index, line in enumerate(lines) if DIAGNOSTIC_PATTERN.search(line)]
    if allowed_fatal is None:
        if diagnostics:
            raise RunnerFailure("%s emitted forbidden diagnostic at line %d: %r" % (
                label, diagnostics[0][0] + 1, diagnostics[0][1]))
    else:
        exact_fatal = [line for _, line in diagnostics if line == allowed_fatal]
        if len(exact_fatal) != 1:
            raise RunnerFailure("%s requires exactly one allowed fatal, found %d" % (label, len(exact_fatal)))
        forbidden = [(index, line) for index, line in diagnostics if line != allowed_fatal]
        if forbidden:
            raise RunnerFailure("%s emitted additional diagnostic at line %d: %r" % (
                label, forbidden[0][0] + 1, forbidden[0][1]))
    return {"errors": counts[0], "warnings": counts[1]}


def parse_main_suite_log(text: str, expected_cases: Sequence[Tuple[str, int]]) -> Dict[str, Any]:
    if not expected_cases:
        raise RunnerFailure("per-case checkpoint table is empty")
    expected_rows: List[str] = []
    cases: List[Dict[str, Any]] = []
    total_checks = 0
    for index, (name, checks) in enumerate(expected_cases, start=1):
        if not re.fullmatch(r"[a-z0-9_]+", name) or checks <= 0:
            raise RunnerFailure("invalid checkpoint table row %d: %r" % (index, (name, checks)))
        expected_rows.extend([
            "WIRE_PARSER_CASE_BEGIN|%d|%s" % (index, name),
            "WIRE_PARSER_CASE_CHECKS|%d|%s|%d" % (index, name, checks),
            "WIRE_PARSER_CASE_END|%d|%s|PASS" % (index, name),
        ])
        cases.append({"index": index, "name": name, "checks": checks, "status": "PASS"})
        total_checks += checks
    expected_rows.extend([
        "WIRE_PARSER_SUMMARY|%d|%d|0|PASS" % (len(expected_cases), total_checks),
        "WIRE_PARSER_ALL_PASS",
    ])

    marker_rows = [
        (line_number, line)
        for line_number, line in enumerate(normalized_log_lines(text), start=1)
        if WIRE_PARSER_MARKER_FAMILY in line
    ]
    observed_rows = [line for _, line in marker_rows]
    if observed_rows != expected_rows:
        mismatch = next(
            (index for index, pair in enumerate(zip(observed_rows, expected_rows)) if pair[0] != pair[1]),
            min(len(observed_rows), len(expected_rows)),
        )
        if mismatch >= len(observed_rows):
            raise RunnerFailure("missing checkpoint protocol row %d: %r" % (mismatch + 1, expected_rows[mismatch]))
        if mismatch >= len(expected_rows):
            line_number, line = marker_rows[mismatch]
            raise RunnerFailure("unexpected checkpoint marker at log line %d: %r" % (line_number, line))
        line_number, line = marker_rows[mismatch]
        raise RunnerFailure("checkpoint protocol row %d mismatch at log line %d: expected %r, observed %r" % (
            mismatch + 1, line_number, expected_rows[mismatch], line))

    diagnostics = validate_diagnostic_tally(text, (0, 0), "directed suite")
    return {
        "status": "PASS",
        "case_count": len(cases),
        "check_count": total_checks,
        "error_count": 0,
        "cases": cases,
        "protocol_rows": expected_rows,
        "modelsim_diagnostics": diagnostics,
    }


def parse_guard_log(text: str) -> Dict[str, Any]:
    marker_rows = [line for line in normalized_log_lines(text) if WIRE_PARSER_MARKER_FAMILY in line]
    if marker_rows:
        raise RunnerFailure("STAT_W guard emitted success/fallback marker: %r" % (marker_rows[0],))
    diagnostics = validate_diagnostic_tally(text, (1, 0), "STAT_W guard", allowed_fatal=GUARD_FATAL_MESSAGE)
    return {
        "status": "PASS",
        "fatal_message": "deepeye_wire_parser: STAT_W out of range",
        "modelsim_diagnostics": diagnostics,
        "process_exit_semantics": "ModelSim 10.7 reports $fatal as Errors:1 and exits 0; exact message/error-count checked",
    }


def find_tool(binary_dir: Optional[str], base_name: str) -> Path:
    names = [base_name + ".exe", base_name] if os.name == "nt" else [base_name]
    if binary_dir:
        directory = Path(binary_dir).expanduser().resolve()
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return candidate.resolve()
        raise RunnerFailure("tool not found in MODELSIM_BIN: %s" % base_name)
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    raise RunnerFailure("tool not found on PATH: %s (set MODELSIM_BIN)" % base_name)


def bitwise_crc16_ccitt_false(data: bytes) -> int:
    value = 0xFFFF
    for byte in data:
        value ^= byte << 8
        for _ in range(8):
            if value & 0x8000:
                value = ((value << 1) ^ 0x1021) & 0xFFFF
            else:
                value = (value << 1) & 0xFFFF
    return value


class Lcg:
    def __init__(self, seed: int) -> None:
        self.state = seed & 0x7FFFFFFF

    def next_u32(self) -> int:
        self.state = (1103515245 * self.state + 12345) & 0x7FFFFFFF
        return self.state

    def randrange(self, limit: int) -> int:
        return self.next_u32() % limit

    def randbytes(self, count: int) -> bytes:
        return bytes((self.next_u32() >> 16) & 0xFF for _ in range(count))


class Runner:
    def __init__(self, arguments: argparse.Namespace) -> None:
        self.arguments = arguments
        self.repo_root = Path(__file__).resolve().parents[4]
        self.author_root = self.repo_root / "competition/deepeye/evidence/transport/wire-parser-20261024-29/author"
        self.attempt = self._create_attempt()
        self.inputs = self.attempt / "inputs"
        self.contract_dir = self.attempt / "contract"
        self.sim_dir = self.attempt / "sim"
        self.log_dir = self.attempt / "commands"
        self.temp_dir = self.attempt / "tmp"
        self.cache_dir = self.attempt / "cache"
        for directory in (self.inputs, self.contract_dir, self.sim_dir, self.log_dir, self.temp_dir, self.cache_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self.environment = self._build_environment()
        self.command_number = 0
        self.commands: List[Dict[str, Any]] = []
        self.records: Dict[str, Any] = {}
        self.started_at = utc_now()

        source_dir = self.repo_root / "competition/deepeye/fpga/transport"
        test_path = self.repo_root / "competition/deepeye/tests/rtl/transport/tb_wire_parser.sv"
        self.source_paths = {
            "parser": source_dir / "deepeye_wire_parser.sv",
            "crc": source_dir / "deepeye_crc16_byte.sv",
            "tb": test_path,
            "runner": Path(__file__).resolve(),
            "candidate_doc": source_dir / "wire_parser_candidate.md",
        }
        self.snapshot_paths = {
            "parser": self.inputs / "deepeye_wire_parser.sv",
            "crc": self.inputs / "deepeye_crc16_byte.sv",
            "tb": self.inputs / "tb_wire_parser.sv",
            "runner": self.inputs / "run_wire_parser.py",
            "candidate_doc": self.inputs / "wire_parser_candidate.md",
        }
        self.tools: Dict[str, Path] = {}
        self.fixture_path = self.inputs / "stdlib_crc_vectors.txt"

    def _create_attempt(self) -> Path:
        attempts = self.author_root / "attempts"
        attempts.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        label = safe_label(self.arguments.label)
        for suffix in range(1000):
            extra = "" if suffix == 0 else "-%03d" % suffix
            candidate = attempts / ("%s-%s-pid%d%s" % (label, stamp, os.getpid(), extra))
            try:
                candidate.mkdir(parents=False, exist_ok=False)
                return candidate
            except FileExistsError:
                continue
        raise RunnerFailure("cannot allocate a fresh attempt directory")

    def _build_environment(self) -> Dict[str, str]:
        environment = os.environ.copy()
        environment.update({
            "TEMP": str(self.temp_dir),
            "TMP": str(self.temp_dir),
            "TMPDIR": str(self.temp_dir),
            "MODELSIM_TMPDIR": str(self.temp_dir),
            "XDG_CACHE_HOME": str(self.cache_dir),
            "PYTHONPYCACHEPREFIX": str(self.cache_dir / "python"),
        })
        return environment

    def run_command(
        self,
        name: str,
        command: Sequence[str],
        expected_exit: Optional[int],
        timeout_seconds: float,
        cwd: Optional[Path] = None,
    ) -> Tuple[Dict[str, Any], bytes, bytes]:
        self.command_number += 1
        command_cwd = (cwd or self.sim_dir).resolve()
        prefix = "%02d_%s" % (self.command_number, safe_label(name))
        stdout_path = self.log_dir / (prefix + ".stdout.bin")
        stderr_path = self.log_dir / (prefix + ".stderr.bin")
        started_at = utc_now()
        monotonic_start = time.monotonic()
        timed_out = False
        before = list(self.commands)
        try:
            completed = subprocess.run(
                list(command),
                cwd=str(command_cwd),
                env=self.environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                check=False,
            )
            return_code: Optional[int] = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as failure:
            timed_out = True
            return_code = None
            stdout = failure.stdout or b""
            stderr = failure.stderr or b""
        duration = time.monotonic() - monotonic_start
        stdout_path.write_bytes(stdout)
        stderr_path.write_bytes(stderr)
        record: Dict[str, Any] = {
            "name": name,
            "argv": list(command),
            "command_line": command_line(command),
            "cwd": relpath(command_cwd, self.attempt),
            "started_utc": started_at,
            "finished_utc": utc_now(),
            "duration_seconds": round(duration, 6),
            "timed_out": timed_out,
            "timeout_seconds": timeout_seconds,
            "expected_exit": expected_exit,
            "actual_exit": return_code,
            "stdout_path": relpath(stdout_path, self.attempt),
            "stdout_sha256": sha256_bytes(stdout),
            "stdout_bytes": len(stdout),
            "stderr_path": relpath(stderr_path, self.attempt),
            "stderr_sha256": sha256_bytes(stderr),
            "stderr_bytes": len(stderr),
        }
        self.commands.append(record)
        if timed_out:
            raise RunnerFailure("command timed out: %s" % name)
        if expected_exit is not None and return_code != expected_exit:
            raise RunnerFailure("command %s exited %s, expected %s" % (name, return_code, expected_exit))
        assert len(self.commands) == len(before) + 1
        return record, stdout, stderr

    def verify_scope(self) -> None:
        if not self.arguments.scope_file:
            self.records["scope"] = {"provided": False, "hash": "not_provided"}
            return
        scope_path = Path(self.arguments.scope_file).expanduser().resolve()
        if not scope_path.is_file():
            raise RunnerFailure("scope file does not exist: %s" % scope_path)
        actual = sha256_file(scope_path)
        scope_kind = ALLOWED_SCOPES.get(actual)
        if scope_kind is None:
            raise RunnerFailure("scope SHA256 mismatch: %s" % actual)
        self.records["scope"] = {
            "provided": True,
            "path": str(scope_path),
            "sha256": actual,
            "recognized_kind": scope_kind,
            "allowed_scopes": ALLOWED_SCOPES,
        }

    def verify_contract(self) -> None:
        contract_path = self.contract_dir / "immutable_scope.json"
        _, raw, _ = self.run_command(
            "contract_git_show",
            ["git", "show", "%s:%s" % (CONTRACT_COMMIT, CONTRACT_PATH)],
            expected_exit=0,
            timeout_seconds=30,
            cwd=self.repo_root,
        )
        contract_path.write_bytes(raw)
        contract_hash = sha256_bytes(raw)
        try:
            document = json.loads(raw.decode("utf-8"))
        except Exception as failure:
            raise RunnerFailure("cannot decode pinned contract: %s" % failure)
        requirements = document.get("requirements")
        if not isinstance(requirements, list):
            raise RunnerFailure("pinned contract requirements is not a list")
        identifiers = [entry.get("id") if isinstance(entry, dict) else None for entry in requirements]
        if identifiers != EXPECTED_REQUIREMENT_IDS:
            raise RunnerFailure("pinned requirement IDs/order mismatch: %r" % identifiers)
        canonical = json.dumps(
            requirements,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        requirements_hash = sha256_bytes(canonical)
        if requirements_hash != CONTRACT_REQUIREMENTS_SHA256:
            raise RunnerFailure("requirements SHA256 mismatch: %s" % requirements_hash)
        if document.get("contract_id") != "DEEPEYE-HUMAN-LOCK-20261014" or document.get("revision") != 1:
            raise RunnerFailure("unexpected pinned contract identity or revision")
        self.records["contract"] = {
            "commit": CONTRACT_COMMIT,
            "path": CONTRACT_PATH,
            "raw_sha256": contract_hash,
            "requirements_sha256": requirements_hash,
            "expected_requirements_sha256": CONTRACT_REQUIREMENTS_SHA256,
            "requirement_ids": identifiers,
            "human_lock_revision": 1,
        }

    def record_git_context(self) -> None:
        _, head_bytes, _ = self.run_command(
            "git_head",
            ["git", "rev-parse", "HEAD"],
            expected_exit=0,
            timeout_seconds=30,
            cwd=self.repo_root,
        )
        _, status_bytes, _ = self.run_command(
            "git_status_context",
            ["git", "status", "--porcelain=v1", "--untracked-files=no"],
            expected_exit=0,
            timeout_seconds=30,
            cwd=self.repo_root,
        )
        head = head_bytes.decode("ascii", errors="replace").strip()
        status_text = status_bytes.decode("utf-8", errors="replace")
        self.records["git_context"] = {
            "head": head,
            "expected_context_base": EXPECTED_CONTEXT_BASE,
            "head_matches_context_base": head == EXPECTED_CONTEXT_BASE,
            "head_is_context_only": True,
            "tracked_status_sha256": sha256_bytes(status_bytes),
            "tracked_status_entry_count": len([line for line in status_text.splitlines() if line]),
            "private_scope_accessed": False,
            "main_tests_or_evidence_accessed": False,
        }

    def probe_tools(self) -> None:
        binary_dir = self.arguments.modelsim_bin or os.environ.get("MODELSIM_BIN")
        self.tools = {
            "vlib": find_tool(binary_dir, "vlib"),
            "vlog": find_tool(binary_dir, "vlog"),
            "vsim": find_tool(binary_dir, "vsim"),
        }
        tool_records: Dict[str, Any] = {}
        for name, path in self.tools.items():
            tool_records[name] = {
                "path": str(path),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        for name, flag in (("vlog", "-version"), ("vsim", "-version")):
            _, stdout, stderr = self.run_command(
                name + "_version",
                [str(self.tools[name]), flag],
                expected_exit=0,
                timeout_seconds=30,
            )
            text = (decode_process_output(stdout) + decode_process_output(stderr)).strip()
            if not text:
                raise RunnerFailure("%s produced no version text" % name)
            version_pattern = r"Model Technology ModelSim SE-64 %s 10\.7" % name
            if re.search(version_pattern, text) is None:
                raise RunnerFailure("%s is not the required ModelSim SE-64 10.7: %s" % (name, text))
            tool_records[name]["version_text"] = text
        tool_records["vlib"]["version_text"] = "not_supported_by_ModelSim10.7_vlib"
        self.records["tools"] = tool_records

    def snapshot_sources(self) -> None:
        source_records: Dict[str, Any] = {}
        for kind in ("parser", "crc", "tb", "runner", "candidate_doc"):
            source = self.source_paths[kind].resolve()
            if not source.is_file():
                raise RunnerFailure("missing source: %s" % source)
            source_hash = sha256_file(source)
            snapshot = self.snapshot_paths[kind]
            shutil.copyfile(source, snapshot)
            snapshot_hash = sha256_file(snapshot)
            if snapshot_hash != source_hash:
                raise RunnerFailure("snapshot hash mismatch for %s" % kind)
            try:
                snapshot.chmod(0o444)
            except OSError:
                pass
            source_records[kind] = {
                "source_path": str(source),
                "snapshot_path": relpath(snapshot, self.attempt),
                "sha256": snapshot_hash,
                "size_bytes": snapshot.stat().st_size,
            }
        crc_hash = source_records["crc"]["sha256"]
        if crc_hash != EXPECTED_CRC_SHA256:
            raise RunnerFailure("read-only CRC dependency SHA256 mismatch: %s" % crc_hash)
        self.records["sources"] = source_records

    def generate_fixtures(self) -> None:
        known_vector = b"123456789"
        if binascii.crc_hqx(known_vector, 0xFFFF) != 0x29B1:
            raise RunnerFailure("stdlib CRC known-vector check failed")
        rows: List[Tuple[Dict[str, Any], bytes]] = []
        for length in range(33):
            frame_type = (0xC0 + length) & 0xFF
            epoch = (0x40 + length) & 0xFF
            seq = (0x2200 + length) & 0xFFFF
            tick = (0x10203040 + length) & 0xFFFFFFFF
            payload = bytes(((length * 9 + index * 13) & 0xFF) for index in range(length))
            rows.append((self._fixture_row(length, frame_type, epoch, seq, tick, payload), payload))
        generator = Lcg(29)
        for _ in range(16):
            length = generator.randrange(33)
            frame_type = generator.randrange(256)
            epoch = generator.randrange(256)
            seq = generator.randrange(65536)
            tick = generator.randrange(1 << 32)
            payload = generator.randbytes(length)
            rows.append((self._fixture_row(length, frame_type, epoch, seq, tick, payload), payload))
        if len(rows) != FIXTURE_COUNT:
            raise RunnerFailure("fixture count mismatch")
        lines = [str(len(rows))]
        for row, payload in rows:
            padded = payload + bytes(32 - len(payload))
            lines.append("%d %02x %02x %04x %08x %s %04x" % (
                row["length"],
                row["type"],
                row["epoch"],
                row["seq"],
                row["tick"],
                padded[::-1].hex(),
                row["crc"],
            ))
        fixture_bytes = ("\n".join(lines) + "\n").encode("ascii")
        self.fixture_path.write_bytes(fixture_bytes)
        manifest = {
            "count": len(rows),
            "known_vector_123456789": "29b1",
            "encoding": "ASCII; payload is reversed to byte-lane order for $fscanf",
            "fixture_sha256": sha256_bytes(fixture_bytes),
            "rows": [row for row, _ in rows],
        }
        write_json(self.inputs / "fixtures_manifest.json", manifest)
        self.records["fixtures"] = {
            "path": relpath(self.fixture_path, self.attempt),
            "sha256": sha256_bytes(fixture_bytes),
            "count": len(rows),
            "known_vector_123456789": "29b1",
            "manifest_sha256": sha256_file(self.inputs / "fixtures_manifest.json"),
        }

    @staticmethod
    def _fixture_row(length: int, frame_type: int, epoch: int, seq: int, tick: int, payload: bytes) -> Dict[str, Any]:
        if len(payload) != length:
            raise RunnerFailure("fixture payload length mismatch")
        covered = bytes([
            3,
            frame_type,
            length,
            epoch,
            seq & 0xFF,
            (seq >> 8) & 0xFF,
            tick & 0xFF,
            (tick >> 8) & 0xFF,
            (tick >> 16) & 0xFF,
            (tick >> 24) & 0xFF,
        ]) + payload
        stdlib_crc = binascii.crc_hqx(covered, 0xFFFF)
        independent_crc = bitwise_crc16_ccitt_false(covered)
        if stdlib_crc != independent_crc:
            raise RunnerFailure("stdlib and independent CRC disagree")
        return {
            "length": length,
            "type": frame_type,
            "epoch": epoch,
            "seq": seq,
            "tick": tick,
            "payload_hex": payload.hex(),
            "crc": stdlib_crc,
        }

    def compile_and_simulate(self) -> None:
        timeout = self.arguments.timeout
        self.run_command("vlib_work", [str(self.tools["vlib"]), "work"], expected_exit=0, timeout_seconds=timeout)
        compile_command = [
            str(self.tools["vlog"]),
            "-sv",
            "-work",
            "work",
            str(self.snapshot_paths["crc"]),
            str(self.snapshot_paths["parser"]),
            str(self.snapshot_paths["tb"]),
        ]
        _, compile_stdout, compile_stderr = self.run_command(
            "vlog_compile",
            compile_command,
            expected_exit=0,
            timeout_seconds=timeout,
        )
        compile_text = decode_process_output(compile_stdout) + decode_process_output(compile_stderr)
        compile_diagnostics = validate_diagnostic_tally(compile_text, (0, 0), "vlog compile")
        self.records["compile"] = {"diagnostics": compile_diagnostics}

        main_command = [
            str(self.tools["vsim"]),
            "-c",
            "-do",
            "run -all; quit -f",
            "work.tb_wire_parser",
            "+FIXTURES=%s" % self.fixture_path,
        ]
        _, main_stdout, main_stderr = self.run_command(
            "vsim_main_directed",
            main_command,
            expected_exit=0,
            timeout_seconds=timeout,
        )
        main_text = decode_process_output(main_stdout) + decode_process_output(main_stderr)
        self.records["main_suite"] = self._parse_main_suite(main_text)

        guards: Dict[str, Any] = {}
        for width, top_name, label in (
            ("1", "tb_wire_parser_guard1", "guard_stat_w_1"),
            ("33", "tb_wire_parser_guard33", "guard_stat_w_33"),
        ):
            guard_command = [
                str(self.tools["vsim"]),
                "-c",
                "-do",
                "run -all; quit -f",
                "work." + top_name,
            ]
            _, guard_stdout, guard_stderr = self.run_command(
                label,
                guard_command,
                expected_exit=0,
                timeout_seconds=timeout,
            )
            guard_text = decode_process_output(guard_stdout) + decode_process_output(guard_stderr)
            guards[width] = self._parse_guard(guard_text)
        self.records["guards"] = guards

    def _parse_main_suite(self, text: str, expected_cases: Optional[Sequence[Tuple[str, int]]] = None) -> Dict[str, Any]:
        return parse_main_suite_log(text, expected_cases if expected_cases is not None else EXPECTED_CASES)

    @staticmethod
    def _parse_guard(text: str) -> Dict[str, Any]:
        return parse_guard_log(text)

    def execute(self) -> None:
        self.verify_scope()
        self.verify_contract()
        self.record_git_context()
        self.probe_tools()
        self.snapshot_sources()
        self.generate_fixtures()
        self.compile_and_simulate()

    def write_manifest(self, status: str, failure: Optional[str] = None) -> Path:
        result = {
            "schema": 1,
            "task_id": TASK_ID,
            "work_id": WORK_ID,
            "original_work_id": ORIGINAL_WORK_ID,
            "operation_id": OPERATION_ID,
            "frozen_design_commit": FROZEN_DESIGN_COMMIT,
            "attempt_label": self.arguments.label,
            "attempt_path": str(self.attempt),
            "started_utc": self.started_at,
            "finished_utc": utc_now(),
            "status": status,
            "failure": failure,
            "session_context": {
                "child_thread_id": self.arguments.thread_id or os.environ.get("CODEX_THREAD_ID") or "not_provided",
                "child_turn_id": self.arguments.turn_id or "not_provided",
                "parent_thread_id": self.arguments.parent_thread_id or "not_provided",
                "parent_turn_id": self.arguments.parent_turn_id or "not_provided",
            },
            "environment": {
                "attempt_cwd": str(self.attempt),
                "sim_cwd": str(self.sim_dir),
                "TEMP": self.environment["TEMP"],
                "TMP": self.environment["TMP"],
                "TMPDIR": self.environment["TMPDIR"],
                "MODELSIM_TMPDIR": self.environment["MODELSIM_TMPDIR"],
                "XDG_CACHE_HOME": self.environment["XDG_CACHE_HOME"],
                "PYTHONPYCACHEPREFIX": self.environment["PYTHONPYCACHEPREFIX"],
                "HOME": self.environment.get("HOME", "not_set"),
                "HOME_source": "inherited_process_environment",
                "isolated_variables": [
                    "TEMP", "TMP", "TMPDIR", "MODELSIM_TMPDIR",
                    "XDG_CACHE_HOME", "PYTHONPYCACHEPREFIX",
                ],
                "all_temp_cache_and_simulator_paths_owned": True,
                "all_home_state_inside_attempt": False,
            },
            "records": self.records,
            "commands": self.commands,
            "claims": {
                "directed_simulation": "run" if status == "PASS" else "failed_or_incomplete",
                "synthesis": "not_run",
                "implementation": "not_run",
                "cdc_rdc": "not_run",
                "board": "not_run",
                "system": "not_run",
                "all29": "not_run",
                "b04": "not_run",
                "r03": "not_run",
                "full_product": "not_run",
            },
        }
        path = self.attempt / "attempt.json"
        write_json(path, result)
        return path


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the deepeye_wire_parser ModelSim 10.7 evidence suite")
    parser.add_argument("--label", default="directed", help="attempt label prefix")
    parser.add_argument("--modelsim-bin", default=None, help="directory containing vlib, vlog, and vsim")
    parser.add_argument("--scope-file", default=None, help="operation scope file whose exact hash is checked")
    parser.add_argument("--timeout", type=float, default=180.0, help="per-command timeout in seconds")
    parser.add_argument("--thread-id", default=None, help="actual execution child thread ID")
    parser.add_argument("--turn-id", default=None, help="actual execution child turn ID")
    parser.add_argument("--parent-thread-id", default=None, help="authorizing parent thread ID")
    parser.add_argument("--parent-turn-id", default=None, help="authorizing parent turn ID")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = build_argument_parser().parse_args(argv)
    runner: Optional[Runner] = None
    status = "FAIL"
    failure_text: Optional[str] = None
    try:
        runner = Runner(arguments)
        runner.execute()
        status = "PASS"
    except Exception as failure:
        failure_text = "%s: %s" % (type(failure).__name__, failure)
        if runner is not None:
            runner.records["traceback"] = traceback.format_exc()
    if runner is None:
        print("wired_parser_runner: unable to allocate attempt: %s" % failure_text, file=sys.stderr)
        return 1
    manifest_path = runner.write_manifest(status, failure_text)
    if status == "PASS":
        print("wire_parser_runner: PASS %s" % manifest_path)
        return 0
    print("wire_parser_runner: FAIL %s" % manifest_path, file=sys.stderr)
    if failure_text:
        print(failure_text, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
