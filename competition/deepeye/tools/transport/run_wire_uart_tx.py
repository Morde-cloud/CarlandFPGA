#!/usr/bin/env python3
"""Strict author runner for deepeye_wire_uart_tx operation 30."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PRODUCT_ROOT = Path(__file__).resolve().parents[2]
WORKTREE = PRODUCT_ROOT.parent.parent
AUTHOR_ROOT = PRODUCT_ROOT / "evidence/transport/wire-uart-tx-20261024-30/author"
SCOPE = Path("D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/wire-uart-tx-20261024-30/SCOPE.md")
MODELSIM = Path("D:/modelsim1/win64")

EXPECTED_SCOPE_SHA256 = "aa830adf815fe2afee22ec13377834df1c74113d7795a038322006a150a883b4"
PINNED_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
DESIGN_COMMIT = "1011259415a0916054eb580687612580bc1e5f09"
EXPECTED_REQUIREMENTS_SHA256 = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
CONTRACT_REL = "docs/competition/deepeye-2026/immutable_scope.json"

OWNED_RELS = {
    "rtl": "fpga/transport/deepeye_wire_uart_tx.sv",
    "candidate": "fpga/transport/wire_uart_tx_candidate.md",
    "tb": "tests/rtl/transport/tb_wire_uart_tx.sv",
    "runner": "tools/transport/run_wire_uart_tx.py",
}

DEPENDENCIES = {
    "serializer": {
        "rel": "fpga/transport/deepeye_wire_serializer.sv",
        "sha256": "efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885",
    },
    "crc": {
        "rel": "fpga/transport/deepeye_crc16_byte.sv",
        "sha256": "8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f",
    },
    "frame_tx": {
        "rel": "fpga/transport/deepeye_uart_frame_tx.sv",
        "sha256": "83261e4c5a317500e224f5cd0e9ce538f067be24d3957dd98c7116425e706be3",
    },
    "uart_tx": {
        "rel": "fpga/transport/deepeye_uart_tx.sv",
        "sha256": "5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47",
    },
}

EXPECTED_CASE_CHECKS = [
    ("initial_reset", 41),
    ("packet_vectors", 5175),
    ("prepost_timing", 63),
    ("config_payload_cadence", 64),
    ("cfg_held_busy", 71),
    ("illegal_inputs", 104),
    ("abort_collect", 42),
    ("abort_transfer", 40),
    ("abort_pre", 43),
    ("abort_start", 45),
    ("abort_data", 45),
    ("abort_stop", 125),
    ("abort_post", 128),
    ("fractional_baud", 54),
    ("default_100mhz_9600", 50),
    ("counter_saturation", 190),
]
EXPECTED_CASES = [name for name, _ in EXPECTED_CASE_CHECKS]

EXPECTED_STAT_ORDER = [
    "vector_frames",
    "lengths_covered",
    "payload_byte_values_covered",
    "max_metadata_vectors",
    "bubble_vectors",
    "bubble_cycles",
    "packet_bytes_compared",
    "same_edge_config_payload_cases",
    "cfg_held_busy_frames",
    "illegal_length_cases",
    "illegal_last_cases",
    "fault_events_checked",
    "cancel_phase_cases",
    "reset_phase_cases",
    "held_cancel_sequences",
    "preamble_cycles",
    "postamble_cycles",
    "fractional_baud_frames",
    "default_baud_frames",
    "saturation_success_frames",
    "saturation_abort_frames",
    "expected_total_bytes",
]

GUARDS = [
    ("guard_clock_hz", "tb_wire_uart_tx_guard_clock_hz", "deepeye_wire_uart_tx: CLOCK_HZ out of range"),
    ("guard_baud", "tb_wire_uart_tx_guard_baud", "deepeye_wire_uart_tx: BAUD out of range"),
    ("guard_pre_cycles", "tb_wire_uart_tx_guard_pre_cycles", "deepeye_wire_uart_tx: PRE_CYCLES out of range"),
    ("guard_post_cycles", "tb_wire_uart_tx_guard_post_cycles", "deepeye_wire_uart_tx: POST_CYCLES out of range"),
    ("guard_stat_w", "tb_wire_uart_tx_guard_stat_w", "deepeye_wire_uart_tx: STAT_W out of range"),
]

DIAGNOSTIC_PATTERN = re.compile(r"\*\*\s+(Error|Warning|Fatal)\b", re.IGNORECASE)
TALLY_PATTERN = re.compile(r"Errors:\s*([0-9]+),\s*Warnings:\s*([0-9]+)")
MARKER_FAMILY_PATTERN = re.compile(r"(?:CASE_|TB_)[A-Z0-9_]*")
GUARD_FORBIDDEN_TOKENS = (
    "CHECK_FAIL",
    "GUARD_NOT_FIRED",
    "FALLBACK",
    "SUCCESS",
    "ALL_PASS",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def fail(message: str) -> None:
    raise RuntimeError(message)


def make_packet(type_byte: int, epoch: int, seq: int, tick: int, payload: bytes) -> bytes:
    covered = (
        bytes((0xA5, 0x5A, 0x03, type_byte, len(payload), epoch))
        + struct.pack("<H", seq)
        + struct.pack("<I", tick)
        + payload
    )
    crc = binascii.crc_hqx(covered[2:], 0xFFFF)
    return covered + struct.pack("<H", crc)


def generate_vectors(input_dir: Path) -> dict:
    vectors = []
    for length in range(32):
        payload = bytes(((length * 13 + offset * 7) & 0xFF) for offset in range(length))
        vectors.append(
            {
                "length": length,
                "type": length,
                "epoch": (0xF0 - length) & 0xFF,
                "seq": (length * 0x0101) & 0xFFFF,
                "tick": (0x10203040 + length * 0x01010101) & 0xFFFFFFFF,
                "payload": payload,
            }
        )

    for block in range(8):
        payload = bytes(range(block * 32, (block + 1) * 32))
        if block == 0:
            type_byte, epoch, seq, tick = 0xFF, 0xFF, 0xFFFF, 0xFFFFFFFF
        else:
            type_byte = 0x40 + block
            epoch = 0x80 + block
            seq = (0x2200 + block) & 0xFFFF
            tick = (0x8090A0B0 + block * 0x01010101) & 0xFFFFFFFF
        vectors.append(
            {
                "length": 32,
                "type": type_byte,
                "epoch": epoch,
                "seq": seq,
                "tick": tick,
                "payload": payload,
            }
        )

    meta_lines = []
    byte_values = []
    offset = 0
    manifest_vectors = []
    seen_payload = set()
    for index, vector in enumerate(vectors):
        packet = make_packet(
            vector["type"], vector["epoch"], vector["seq"], vector["tick"], vector["payload"]
        )
        if len(packet) != 14 + vector["length"]:
            fail("generated packet length mismatch")
        meta_lines.append(
            f"{index} {vector['length']} {vector['type']} {vector['epoch']} "
            f"{vector['seq']} {vector['tick']} {len(packet)} {offset}"
        )
        byte_values.extend(packet)
        seen_payload.update(vector["payload"])
        manifest_vectors.append(
            {
                "index": index,
                "length": vector["length"],
                "type": vector["type"],
                "epoch": vector["epoch"],
                "seq": vector["seq"],
                "tick": vector["tick"],
                "count": len(packet),
                "offset": offset,
                "packet_hex": packet.hex(),
                "packet_sha256": sha256_bytes(packet),
            }
        )
        offset += len(packet)

    if len(vectors) != 40 or len(seen_payload) != 256:
        fail("vector coverage construction failed")

    meta_path = input_dir / "vectors.meta"
    hex_path = input_dir / "vectors.hex"
    meta_path.write_text("\n".join(meta_lines) + "\n", encoding="ascii")
    hex_lines = []
    for pos in range(0, len(byte_values), 16):
        hex_lines.append(" ".join(f"{value:02x}" for value in byte_values[pos : pos + 16]))
    hex_path.write_text("\n".join(hex_lines) + "\n", encoding="ascii")

    max_meta = sum(
        1
        for vector in vectors
        if vector["type"] == 0xFF
        and vector["epoch"] == 0xFF
        and vector["seq"] == 0xFFFF
        and vector["tick"] == 0xFFFFFFFF
    )
    bubble_vectors = sum(1 for vector in vectors if vector["length"] > 1)
    bubble_count = sum(
        1
        for vector in vectors
        for index in range(vector["length"])
        if index + 1 < vector["length"] and index % 3 == 2
    )
    manifest = {
        "schema": "deepeye-independent-uart-vectors/v1",
        "implementation": "Python struct plus binascii.crc_hqx(seed=0xFFFF)",
        "crc_rule": "CRC covers version/type/len/epoch/seq/tick/payload after the A5 5A sync bytes",
        "vector_count": len(vectors),
        "lengths_covered": sorted({vector["length"] for vector in vectors}),
        "payload_byte_values_covered": len(seen_payload),
        "max_metadata_vectors": max_meta,
        "bubble_vectors": bubble_vectors,
        "bubble_cycles": bubble_count * 2,
        "expected_total_bytes": len(byte_values),
        "meta_path": str(meta_path),
        "hex_path": str(hex_path),
        "meta_sha256": sha256_file(meta_path),
        "hex_sha256": sha256_file(hex_path),
        "vectors": manifest_vectors,
    }
    write_json(input_dir / "vector-manifest.json", manifest)
    return manifest


class CommandRecorder:
    def __init__(self, attempt: Path, env: dict[str, str]):
        self.attempt = attempt
        self.env = env
        self.records = []

    def run(self, name: str, argv: list[str], cwd: Path, timeout: float = 1800.0) -> dict:
        out_dir = self.attempt / "commands" / name.replace("/", "_")
        out_dir.mkdir(parents=True, exist_ok=False)
        started = datetime.now(timezone.utc)
        timed_out = False
        process_error = None
        stdout = b""
        stderr = b""
        code = -1
        try:
            proc = subprocess.run(
                argv,
                cwd=str(cwd),
                env=self.env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            code = proc.returncode
            stdout = proc.stdout or b""
            stderr = proc.stderr or b""
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            code = -1
        except OSError as exc:
            process_error = f"{type(exc).__name__}: {exc}"
        ended = datetime.now(timezone.utc)

        (out_dir / "argv.json").write_text(json.dumps(argv, indent=2) + "\n", encoding="utf-8")
        (out_dir / "cwd.txt").write_text(str(cwd) + "\n", encoding="utf-8")
        (out_dir / "exit.txt").write_text(f"{code}\n", encoding="utf-8")
        (out_dir / "timeout.txt").write_text(f"{str(timed_out).lower()}\n", encoding="utf-8")
        (out_dir / "stdout.bin").write_bytes(stdout)
        (out_dir / "stderr.bin").write_bytes(stderr)
        record = {
            "name": name,
            "argv": argv,
            "cwd": str(cwd),
            "started_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_utc": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_seconds": round((ended - started).total_seconds(), 3),
            "exit_code": code,
            "timed_out": timed_out,
            "process_error": process_error,
            "stdout_path": str(out_dir / "stdout.bin"),
            "stdout_bytes": len(stdout),
            "stdout_sha256": sha256_bytes(stdout),
            "stderr_path": str(out_dir / "stderr.bin"),
            "stderr_bytes": len(stderr),
            "stderr_sha256": sha256_bytes(stderr),
            "exit_path": str(out_dir / "exit.txt"),
            "exit_sha256": sha256_file(out_dir / "exit.txt"),
            "timeout_path": str(out_dir / "timeout.txt"),
            "timeout_sha256": sha256_file(out_dir / "timeout.txt"),
        }
        write_json(out_dir / "command.json", record)
        self.records.append(record)
        return record


def normalized_log_lines(text: str) -> list[str]:
    return [re.sub(r"^#\s?", "", line.strip()) for line in text.splitlines()]


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
        fail(f"malformed/conflicting {label} diagnostic tally at line {index + 1}: {line!r}")
    if len(candidates) != 1:
        fail(f"{label} requires exactly one diagnostic tally, found {len(candidates)}")
    tally_index, tally_line = candidates[0]
    nonblank = [index for index, line in enumerate(lines) if line]
    if not nonblank or tally_index != nonblank[-1]:
        fail(f"{label} diagnostic tally is not the final nonblank line")
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
        fail(f"{label} diagnostics are {counts!r}, expected {expected!r}")

    diagnostics = [
        (index, line)
        for index, line in enumerate(normalized_log_lines(text))
        if DIAGNOSTIC_PATTERN.search(line)
    ]
    if allowed_fatal is None:
        if diagnostics:
            index, line = diagnostics[0]
            fail(f"{label} emitted forbidden diagnostic at line {index + 1}: {line!r}")
    else:
        exact_fatal = [line for _, line in diagnostics if line == allowed_fatal]
        if len(exact_fatal) != 1:
            fail(f"{label} requires exactly one allowed fatal, found {len(exact_fatal)}")
        forbidden = [(index, line) for index, line in diagnostics if line != allowed_fatal]
        if forbidden:
            index, line = forbidden[0]
            fail(f"{label} emitted additional diagnostic at line {index + 1}: {line!r}")
    return {"errors": counts[0], "warnings": counts[1]}


def build_positive_protocol_rows(expected_stats: dict[str, int]) -> list[str]:
    if list(expected_stats) != EXPECTED_STAT_ORDER:
        fail("expected TB_STAT values are not the complete exact ordered set")
    rows = []
    for name, checks in EXPECTED_CASE_CHECKS:
        rows.extend(
            [
                f"# CASE_BEGIN name={name}",
                f"# CASE_END name={name} status=pass checks={checks}",
            ]
        )
    rows.extend(
        f"# TB_STAT {name}={expected_stats[name]}" for name in EXPECTED_STAT_ORDER
    )
    total_checks = sum(checks for _, checks in EXPECTED_CASE_CHECKS)
    rows.extend(
        [
            f"# TB_SUMMARY cases={len(EXPECTED_CASE_CHECKS)} "
            f"pass={len(EXPECTED_CASE_CHECKS)} fail=0 checks={total_checks}",
            "# TB_END pass",
        ]
    )
    if len(rows) != len(set(rows)):
        fail("expected TX protocol rows are not unique")
    return rows


def parse_positive_log(log_path: Path, expected_stats: dict[str, int]) -> dict:
    text = log_path.read_text(encoding="utf-8", errors="replace")
    tally = validate_diagnostic_tally(text, (0, 0), "positive simulation")
    expected_rows = build_positive_protocol_rows(expected_stats)
    marker_rows = [
        (index, line)
        for index, line in enumerate(text.splitlines(), start=1)
        if MARKER_FAMILY_PATTERN.search(line)
    ]
    observed_rows = [line for _, line in marker_rows]
    if observed_rows != expected_rows:
        mismatch = next(
            (
                index
                for index, pair in enumerate(zip(observed_rows, expected_rows))
                if pair[0] != pair[1]
            ),
            min(len(observed_rows), len(expected_rows)),
        )
        if mismatch >= len(observed_rows):
            fail(
                f"missing ordered TX protocol row {mismatch + 1}: "
                f"{expected_rows[mismatch]!r}"
            )
        if mismatch >= len(expected_rows):
            line_number, line = marker_rows[mismatch]
            fail(
                f"unexpected TX marker-family line at log line {line_number}: {line!r}"
            )
        line_number, line = marker_rows[mismatch]
        fail(
            f"TX protocol row {mismatch + 1} mismatch at log line {line_number}: "
            f"expected {expected_rows[mismatch]!r}, observed {line!r}"
        )

    cases = [
        {"name": name, "status": "pass", "checks": checks}
        for name, checks in EXPECTED_CASE_CHECKS
    ]
    return {
        "cases": cases,
        "stats": dict(expected_stats),
        "summary": {
            "cases": len(cases),
            "pass": len(cases),
            "fail": 0,
            "checks": sum(checks for _, checks in EXPECTED_CASE_CHECKS),
        },
        "protocol_rows": expected_rows,
        "structured_rows": len(expected_rows) + 1,
        "tally": tally,
    }


def expected_stat_values(manifest: dict) -> dict[str, int]:
    vector_total = manifest["expected_total_bytes"]
    packet_compared = vector_total + 14 + 15 + 16 + 13 + 13 + 14 + 14
    return {
        "vector_frames": 40,
        "lengths_covered": 33,
        "payload_byte_values_covered": 256,
        "max_metadata_vectors": 1,
        "bubble_vectors": manifest["bubble_vectors"],
        "bubble_cycles": manifest["bubble_cycles"],
        "packet_bytes_compared": packet_compared,
        "same_edge_config_payload_cases": 1,
        "cfg_held_busy_frames": 1,
        "illegal_length_cases": 2,
        "illegal_last_cases": 1,
        "fault_events_checked": 3,
        "cancel_phase_cases": 7,
        "reset_phase_cases": 7,
        "held_cancel_sequences": 2,
        "preamble_cycles": 3,
        "postamble_cycles": 7,
        "fractional_baud_frames": 1,
        "default_baud_frames": 1,
        "saturation_success_frames": 4,
        "saturation_abort_frames": 4,
        "expected_total_bytes": vector_total,
    }


def parse_guard_log(path: Path, expected_message: str) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    normalized = normalized_log_lines(text)
    marker_rows = [line for line in normalized if MARKER_FAMILY_PATTERN.search(line)]
    if marker_rows:
        fail(f"guard log emitted success/fallback marker: {marker_rows[0]!r}")
    for line in normalized:
        upper = line.upper()
        for token in GUARD_FORBIDDEN_TOKENS:
            if token in upper:
                fail(f"guard log contains forbidden success/fallback token {token!r}")

    expected_line = f"** Fatal: {expected_message}"
    diagnostics = validate_diagnostic_tally(
        text,
        (1, 0),
        "guard simulation",
        allowed_fatal=expected_line,
    )
    forbidden_dependencies = [
        "deepeye_wire_serializer:",
        "deepeye_crc16_byte:",
        "deepeye_uart_frame_tx:",
        "deepeye_uart_tx:",
    ]
    for token in forbidden_dependencies:
        if token in text:
            fail("guard log contains a conflicting dependency/preemption diagnostic")
    return {
        "expected_message": expected_message,
        "fatal_line": f"# {expected_line}",
        "fatal_count": 1,
        "tally": diagnostics,
        "conflicting_diagnostics": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.attempt):
        fail("attempt name must be a simple path component")

    attempt = AUTHOR_ROOT / args.attempt
    if attempt.exists():
        fail(f"attempt already exists: {attempt}")
    attempt.mkdir(parents=True)
    (attempt / "commands").mkdir()
    (attempt / "env/tmp").mkdir(parents=True)
    (attempt / "env/pycache").mkdir(parents=True)
    (attempt / "work").mkdir()
    (attempt / "inputs/author-source").mkdir(parents=True)
    (attempt / "inputs/dependencies").mkdir(parents=True)
    (attempt / "inputs/vectors").mkdir(parents=True)

    env = os.environ.copy()
    env["TEMP"] = str(attempt / "env/tmp")
    env["TMP"] = str(attempt / "env/tmp")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(attempt / "env/pycache")

    started = utc_now()
    write_json(
        attempt / "runner-command.json",
        {"argv": sys.argv, "cwd": os.getcwd()},
    )

    scope_bytes = SCOPE.read_bytes()
    scope_hash = sha256_bytes(scope_bytes)
    if scope_hash != EXPECTED_SCOPE_SHA256:
        fail("scope hash mismatch")
    (attempt / "inputs/scope.snapshot.md").write_bytes(scope_bytes)

    contract_raw = subprocess.check_output(
        ["git", "-C", str(WORKTREE), "show", f"{PINNED_COMMIT}:{CONTRACT_REL}"],
        env=env,
    )
    (attempt / "inputs/contract.snapshot.json").write_bytes(contract_raw)
    contract = json.loads(contract_raw.decode("utf-8"))
    requirements = contract["requirements"]
    canonical = json.dumps(
        requirements, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    req_hash = sha256_bytes(canonical)
    if req_hash != EXPECTED_REQUIREMENTS_SHA256:
        fail("H01-H15 canonical requirements hash mismatch")
    if [item.get("id") for item in requirements] != [f"H{index:02d}" for index in range(1, 16)]:
        fail("H01-H15 ID set/order mismatch")

    design_check = subprocess.run(
        ["git", "-C", str(WORKTREE), "cat-file", "-e", f"{DESIGN_COMMIT}^{{commit}}"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if design_check.returncode != 0:
        fail("frozen design commit is absent")
    design_ancestor = subprocess.run(
        ["git", "-C", str(WORKTREE), "merge-base", "--is-ancestor", DESIGN_COMMIT, "HEAD"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if design_ancestor.returncode != 0:
        fail("frozen design commit is not an ancestor of HEAD")
    head = subprocess.check_output(
        ["git", "-C", str(WORKTREE), "rev-parse", "HEAD"], env=env
    ).decode("ascii").strip()

    dependency_records = {}
    for name, pin in DEPENDENCIES.items():
        live = PRODUCT_ROOT / pin["rel"]
        actual = sha256_file(live)
        if actual != pin["sha256"]:
            fail(f"dependency hash mismatch: {name}")
        snapshot = attempt / "inputs/dependencies" / live.name
        shutil.copyfile(live, snapshot)
        if sha256_file(snapshot) != actual:
            fail(f"dependency snapshot mismatch: {name}")
        dependency_records[name] = {
            "path": pin["rel"],
            "bytes": live.stat().st_size,
            "sha256": actual,
            "expected_sha256": pin["sha256"],
            "snapshot": str(snapshot),
        }

    source_records = {}
    author_dir = attempt / "inputs/author-source"
    for name, rel in OWNED_RELS.items():
        live = PRODUCT_ROOT / rel
        snapshot = author_dir / live.name
        shutil.copyfile(live, snapshot)
        source_records[name] = {
            "path": rel,
            "bytes": live.stat().st_size,
            "sha256": sha256_file(snapshot),
            "snapshot": str(snapshot),
        }
    source_records["crc_dependency_read_only"] = dependency_records["crc"]
    (author_dir / "sha256.txt").write_text(
        "".join(
            f"{record['sha256']}  {Path(record['snapshot']).name}\n"
            for record in source_records.values()
            if "snapshot" in record
        ),
        encoding="ascii",
    )

    vectors = generate_vectors(attempt / "inputs/vectors")
    stat_values = expected_stat_values(vectors)

    write_json(
        attempt / "inputs/contract-verification.json",
        {
            "pinned_commit": PINNED_COMMIT,
            "contract_path": CONTRACT_REL,
            "raw_sha256": sha256_bytes(contract_raw),
            "requirements_count": len(requirements),
            "requirements_ids": [item["id"] for item in requirements],
            "requirements_sha256": req_hash,
            "expected_requirements_sha256": EXPECTED_REQUIREMENTS_SHA256,
            "canonicalization": "json.dumps(requirements, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')",
            "passed": True,
            "design_commit": DESIGN_COMMIT,
            "design_commit_exists": True,
            "design_is_ancestor": True,
            "head_context": head,
        },
    )
    write_json(
        attempt / "inputs/scope-verification.json",
        {
            "path": str(SCOPE),
            "sha256": scope_hash,
            "expected_sha256": EXPECTED_SCOPE_SHA256,
            "matches": True,
        },
    )
    write_json(
        attempt / "environment.json",
        {
            "worktree_root": str(WORKTREE),
            "product_root": str(PRODUCT_ROOT),
            "modelsim_root": str(MODELSIM),
            "python": sys.executable,
            "TEMP": env["TEMP"],
            "TMP": env["TMP"],
            "PYTHONDONTWRITEBYTECODE": env["PYTHONDONTWRITEBYTECODE"],
            "python_cache_prefix": env["PYTHONPYCACHEPREFIX"],
            "modelsim_cwd": str(attempt / "work"),
            "timeout_seconds": 1800.0,
        },
    )

    recorder = CommandRecorder(attempt, env)
    work = attempt / "work"

    version_records = {}
    for tool in ("vlib.exe", "vlog.exe", "vsim.exe"):
        record = recorder.run(f"tool-versions/{tool}", [str(MODELSIM / tool), "-version"], work, 30.0)
        raw = (Path(record["stdout_path"]).read_bytes() + Path(record["stderr_path"]).read_bytes())
        version_records[tool] = {
            "path": str(MODELSIM / tool),
            "sha256": sha256_file(MODELSIM / tool),
            "exit_code": record["exit_code"],
            "timed_out": record["timed_out"],
            "stdout_sha256": record["stdout_sha256"],
            "stderr_sha256": record["stderr_sha256"],
            "version_text": raw.decode("utf-8", "replace"),
        }

    vlib_record = recorder.run("simulation/01-vlib-work", [str(MODELSIM / "vlib.exe"), "work"], work)
    if vlib_record["exit_code"] != 0 or vlib_record["timed_out"]:
        fail("vlib work failed")

    compile_files = [
        attempt / "inputs/dependencies" / "deepeye_crc16_byte.sv",
        attempt / "inputs/dependencies" / "deepeye_wire_serializer.sv",
        attempt / "inputs/dependencies" / "deepeye_uart_tx.sv",
        attempt / "inputs/dependencies" / "deepeye_uart_frame_tx.sv",
        attempt / "inputs/author-source" / "deepeye_wire_uart_tx.sv",
        attempt / "inputs/author-source" / "tb_wire_uart_tx.sv",
    ]
    compile_record = recorder.run(
        "simulation/02-vlog",
        [str(MODELSIM / "vlog.exe"), "-sv", "-work", "work", *[str(path) for path in compile_files]],
        work,
    )
    if compile_record["exit_code"] != 0 or compile_record["timed_out"]:
        fail("vlog failed")

    vector_args = [
        f"+VECTOR_META={attempt / 'inputs/vectors/vectors.meta'}",
        f"+VECTOR_HEX={attempt / 'inputs/vectors/vectors.hex'}",
    ]
    positive_record = recorder.run(
        "simulation/03-vsim",
        [
            str(MODELSIM / "vsim.exe"),
            "-c",
            "-l",
            "vsim.log",
            "-do",
            "run -all; quit -f",
            "tb_wire_uart_tx",
            *vector_args,
        ],
        work,
    )
    if positive_record["exit_code"] != 0 or positive_record["timed_out"]:
        fail("positive vsim failed")
    if not (work / "vsim.log").exists():
        fail("positive vsim log is missing")
    shutil.copyfile(work / "vsim.log", attempt / "vsim-log.txt")
    positive = parse_positive_log(attempt / "vsim-log.txt", stat_values)
    if positive["stats"] != stat_values:
        fail("TB_STAT values differ from independently computed expectations")

    guard_records = []
    for index, (name, top, message) in enumerate(GUARDS, start=1):
        log_name = f"{name}.log"
        record = recorder.run(
            f"guards/{index:02d}-{name}",
            [
                str(MODELSIM / "vsim.exe"),
                "-c",
                "-l",
                log_name,
                "-do",
                "run -all; quit -f",
                top,
            ],
            work,
        )
        if record["timed_out"] or record["exit_code"] not in (0, 1):
            fail(f"guard command failed unexpectedly: {name}")
        log_path = work / log_name
        if not log_path.exists():
            fail(f"guard log missing: {name}")
        shutil.copyfile(log_path, attempt / f"{name}-log.txt")
        parsed = parse_guard_log(attempt / f"{name}-log.txt", message)
        guard_records.append(
            {
                "name": name,
                "top": top,
                "command": record,
                "log": str(attempt / f"{name}-log.txt"),
                "log_sha256": sha256_file(attempt / f"{name}-log.txt"),
                **parsed,
            }
        )

    source_unchanged = True
    for name, rel in OWNED_RELS.items():
        if sha256_file(PRODUCT_ROOT / rel) != source_records[name]["sha256"]:
            source_unchanged = False
    for name, pin in DEPENDENCIES.items():
        if sha256_file(PRODUCT_ROOT / pin["rel"]) != pin["sha256"]:
            source_unchanged = False
    if not source_unchanged:
        fail("live source/dependency hash changed during execution")

    summary = {
        "schema": "deepeye-author-run/v1",
        "attempt": args.attempt,
        "status": "pass",
        "started_utc": started,
        "ended_utc": utc_now(),
        "scope": {
            "path": str(SCOPE),
            "sha256": scope_hash,
            "snapshot": str(attempt / "inputs/scope.snapshot.md"),
        },
        "contract": {
            "pinned_commit": PINNED_COMMIT,
            "requirements_sha256": req_hash,
            "expected_requirements_sha256": EXPECTED_REQUIREMENTS_SHA256,
            "contract_file_sha256": sha256_bytes(contract_raw),
        },
        "workspace": {"head_context": head, "design_commit": DESIGN_COMMIT},
        "sources": source_records,
        "dependencies": dependency_records,
        "vectors": {
            "manifest": str(attempt / "inputs/vectors/vector-manifest.json"),
            "manifest_sha256": sha256_file(attempt / "inputs/vectors/vector-manifest.json"),
            "meta_sha256": vectors["meta_sha256"],
            "hex_sha256": vectors["hex_sha256"],
            "vector_count": vectors["vector_count"],
            "expected_total_bytes": vectors["expected_total_bytes"],
        },
        "versions": version_records,
        "commands": recorder.records,
        "positive": positive,
        "expected_stats": stat_values,
        "guards": guard_records,
        "source_unchanged_after_run": source_unchanged,
    }
    write_json(attempt / "summary.json", summary)
    (attempt / "summary.txt").write_text(
        "attempt={}\nstatus=pass\ncases={}\npass={}\nfail={}\nchecks={}\nrunner_exit=0\n".format(
            args.attempt,
            positive["summary"]["cases"],
            positive["summary"]["pass"],
            positive["summary"]["fail"],
            positive["summary"]["checks"],
        ),
        encoding="utf-8",
    )
    print(
        f"status=pass attempt={args.attempt} cases={positive['summary']['cases']} "
        f"checks={positive['summary']['checks']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
