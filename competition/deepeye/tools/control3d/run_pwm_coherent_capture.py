#!/usr/bin/env python3
"""Fail-closed ModelSim runner for the op14 coherent-capture candidate.

Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Work: B-PWM-COHERENT-CAPTURE-RTL-20261020-14-v1
Operation: B-DEEPEYE-PWM-COHERENT-CAPTURE-20261020-14

The runner never overwrites an output directory. It snapshots and hashes the
authored RTL/TB/runner and the frozen scope inputs, compiles from the snapshots,
runs every positive group in a fresh work library, runs all invalid-parameter
guards, then builds and runs two isolated mutants in separate libraries.

This is author-side local ModelSim evidence only. It is not main acceptance,
synthesis, implementation, CDC/RDC, board, system or product acceptance.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
OPERATION_ID = "B-DEEPEYE-PWM-COHERENT-CAPTURE-20261020-14"
WORK_ID = "B-PWM-COHERENT-CAPTURE-RTL-20261020-14-v1"
BASELINE_HEAD = "732a58ba60c7cce0027d683e912d986453755843"
CONTRACT_ID = "DEEPEYE-HUMAN-LOCK-20261014"
CONTRACT_REVISION = 1
CONTRACT_PIN = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
DESIGN_PIN = "1011259415a0916054eb580687612580bc1e5f09"
REQ_SHA = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
SCOPE_SHA = "f2d8ed287848e536b140629f3f30f7105d2171a6cc0c00be2186d09c9115331d"
FROZEN_SHA = "0a8992e32b30e1b084f7392c2941b42e1b3814048d6cd0139f669189353f4eea"
DECISION_SHA = "2290a3e5f69d55f02036d318ac6953e8b0081694c253ff02d65e26461c6b6c99"
PROTECTED_SHA = "6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8"

HERE = Path(__file__).resolve()
WORKTREE = HERE.parents[4]
RTL = WORKTREE / "competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv"
TB = WORKTREE / "competition/deepeye/tests/rtl/control3d/tb_pwm_coherent_capture.sv"
CONTRACT_JSON = WORKTREE / "docs/competition/deepeye-2026/immutable_scope.json"
CONTRACT_MD = WORKTREE / "docs/competition/deepeye-2026/immutable_scope.md"
PROTECTED = WORKTREE / "handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json"

NODE_B = Path("D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence")
SCOPE = NODE_B / "independent-coherent-capture-20261020-14/SCOPE.md"
FROZEN = NODE_B / "independent-coherent-capture-20261020-14/SCOPE_FROZEN.json"
CONSUMED = NODE_B / "independent-coherent-capture-20261020-14/SCOPE_CONTINUE_CONSUMED.json"
DECISION = NODE_B / "main-continuation-20261019-v1/SCOPE_REVIEW_DECISION_20261020_14.json"
DECISION_CONSUMED = NODE_B / "main-continuation-20261019-v1/SCOPE_REVIEW_CONSUMED_20261020_14.json"

GROUP_END_RE = re.compile(
    r"GROUP_END\s+(\S+)\s+cases=(\d+)\s+samples=(\d+)\s+assertions=(\d+)\s+"
    r"mismatches=(\d+)\s+records=(\d+)\s+fault_events=(\d+)"
)
TB_STATS_RE = re.compile(
    r"TB_STATS\s+groups=(\d+)\s+cases=(\d+)\s+samples=(\d+)\s+assertions=(\d+)\s+"
    r"records=(\d+)\s+fault_events=(\d+)\s+mismatches=(\d+)"
)
MISMATCH_RE = re.compile(r"MISMATCH\s+sample=\S+\s+label=(\S+)")

POSITIVE = [
    {
        "id": "g00-main-controls-negatives-queue-priority",
        "group": 0, "count_w": 4, "witness_w": 8, "tag_w": 8,
        "groups": {
            "controls_tags_and_abort_phases": 10,
            "negative_coherence_and_recovery": 6,
            "one_slot_transport_and_fault_priority": 7,
            "period_before_incoherent_with_stalled_record": 1,
        },
        "stats": (4, 24, 211, 1116, 19, 16, 0),
    },
    {
        "id": "g01-exhaustive-count-w2-plus-saturation",
        "group": 1, "count_w": 2, "witness_w": 8, "tag_w": 4,
        "groups": {
            "exhaustive_count_w2_legal_high_triples": 9,
            "fault_count_saturation": 6,
        },
        "stats": (2, 15, 77, 454, 9, 7, 0),
    },
    {
        "id": "g02-exhaustive-count-w3",
        "group": 2, "count_w": 3, "witness_w": 8, "tag_w": 5,
        "groups": {"exhaustive_count_w3_legal_high_triples": 441},
        "stats": (1, 441, 4042, 24988, 441, 0, 0),
    },
    {
        "id": "g03-count-w16-full-period-boundaries",
        "group": 3, "count_w": 16, "witness_w": 32, "tag_w": 16,
        "groups": {"count_w16_full_period_boundaries": 3},
        "stats": (1, 3, 163856, 655475, 3, 1, 0),
    },
    {
        "id": "g04-min-widths-witness-w2",
        "group": 4, "count_w": 2, "witness_w": 2, "tag_w": 1,
        "groups": {"count_w2_witness_w2_exhaustion": 2},
        "stats": (1, 2, 18, 88, 1, 2, 0),
    },
    {
        "id": "g05-max-widths-bounded",
        "group": 5, "count_w": 32, "witness_w": 64, "tag_w": 64,
        "groups": {"count_w32_witness_w64_tag_w64": 3},
        "stats": (1, 3, 21, 144, 3, 0, 0),
    },
    {
        "id": "g06-deterministic-random-schedule",
        "group": 6, "count_w": 8, "witness_w": 16, "tag_w": 16,
        "groups": {"deterministic_random_three_lane_schedule": 128},
        "stats": (1, 128, 2407, 12588, 128, 0, 0),
    },
    {
        "id": "g09-small-boundaries",
        "group": 9, "count_w": 2, "witness_w": 3, "tag_w": 3,
        "groups": {"small_literal_period_and_witness": 5},
        "stats": (1, 5, 44, 153, 3, 5, 0),
    },
    {
        "id": "g10-default-parameter-smoke",
        "group": 10, "count_w": None, "witness_w": None, "tag_w": None,
        "groups": {"default_parameter_smoke": 1},
        "stats": (1, 1, 8, 52, 1, 0, 0),
    },
    {
        "id": "g11-count-w3-period-overflow",
        "group": 11, "count_w": 3, "witness_w": 8, "tag_w": 4,
        "groups": {"count_w3_period_overflow": 3},
        "stats": (1, 3, 40, 138, 3, 2, 0),
    },
    {
        "id": "g12-witness-w3-exhaustion",
        "group": 12, "count_w": 3, "witness_w": 3, "tag_w": 1,
        "groups": {"witness_w3_namespace_exhaustion": 3},
        "stats": (1, 3, 38, 133, 2, 3, 0),
    },
]

INVALID_TOPS = [
    ("tb_invalid_count_zero", "COUNT_W=0"),
    ("tb_invalid_count_negative", "COUNT_W=-1"),
    ("tb_invalid_count_high", "COUNT_W=33"),
    ("tb_invalid_witness_zero", "WITNESS_W=0"),
    ("tb_invalid_witness_negative", "WITNESS_W=-1"),
    ("tb_invalid_witness_high", "WITNESS_W=65"),
    ("tb_invalid_tag_zero", "TAG_W=0"),
    ("tb_invalid_tag_negative", "TAG_W=-1"),
    ("tb_invalid_tag_high", "TAG_W=65"),
]

MUTANTS = [
    {
        "id": "relaxed-common-start",
        "file": "relaxed_common_start.sv",
        "group": 8,
        "old": "                        if (rise_mask == RISE_ALL) begin // MUTATION_IDLE_RELAXED_COMMON",
        "new": "                        if (rise_mask != RISE_NONE) begin // MUTATION_IDLE_RELAXED_COMMON",
        "must_mismatch": "mutant_relaxed_subset_start.events",
    },
    {
        "id": "retain-partial-on-subset",
        "file": "retain_partial_on_subset.sv",
        "group": 7,
        "old": "                            partial_valid_q    <= 1'b0; // MUTATION_ABORT_PARTIAL",
        "new": "                            partial_valid_q    <= partial_valid_q; // MUTATION_ABORT_PARTIAL",
        "must_mismatch": "mutant_mixed_no_record.valid",
    },
]

COMMAND_SEQ = 0
COMMANDS: list[dict] = []


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def run_command(
    out: Path,
    logs: Path,
    name: str,
    argv: list[str],
    cwd: Path,
    timeout: float,
) -> tuple[dict, str]:
    global COMMAND_SEQ
    COMMAND_SEQ += 1
    stdout_path = logs / f"{name}.stdout.txt"
    stderr_path = logs / f"{name}.stderr.txt"
    started = utc_now()
    start = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            [str(item) for item in argv],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        stdout_b, stderr_b, exit_code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as exc:
        stdout_b = exc.stdout or b""
        stderr_b = exc.stderr or b""
        exit_code = None
        timed_out = True
    ended = utc_now()
    duration = round(time.monotonic() - start, 3)
    stdout_path.write_bytes(stdout_b)
    stderr_path.write_bytes(stderr_b)
    record = {
        "seq": COMMAND_SEQ,
        "name": name,
        "argv": [str(item) for item in argv],
        "cwd": str(cwd),
        "started_utc": started,
        "ended_utc": ended,
        "duration_s": duration,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout": relative(stdout_path, out),
        "stderr": relative(stderr_path, out),
        "stdout_sha256": sha256_bytes(stdout_b),
        "stderr_sha256": sha256_bytes(stderr_b),
        "stdout_bytes": len(stdout_b),
        "stderr_bytes": len(stderr_b),
    }
    COMMANDS.append(record)
    with (out / "commands.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    text = stdout_b.decode("utf-8", "replace") + "\n" + stderr_b.decode("utf-8", "replace")
    return record, text


def verify_inputs(out: Path, logs: Path, timeout: float) -> dict:
    checks: list[dict] = []
    failures: list[str] = []

    def check(label: str, path: Path, expected: str | None = None) -> str:
        if not path.is_file():
            failures.append(f"missing input {label}: {path}")
            return ""
        actual = sha256_file(path)
        checks.append(
            {
                "label": label,
                "path": str(path),
                "sha256": actual,
                "expected_sha256": expected,
                "bytes": path.stat().st_size,
                "matches": expected is None or actual == expected,
            }
        )
        if expected is not None and actual != expected:
            failures.append(f"{label} hash {actual} != {expected}")
        return actual

    check("scope", SCOPE, SCOPE_SHA)
    check("scope_frozen", FROZEN, FROZEN_SHA)
    check("scope_review_decision", DECISION, DECISION_SHA)
    check("scope_continue_consumed", CONSUMED)
    check("scope_review_consumed", DECISION_CONSUMED)
    check("protected_dirty_codec_input", PROTECTED, PROTECTED_SHA)

    contract = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    requirements = contract.get("requirements")
    if not isinstance(requirements, list):
        failures.append("contract requirements is not a list")
        requirements = []
    canonical = json.dumps(
        requirements, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    req_hash = sha256_bytes(canonical)
    checks.append(
        {
            "label": "canonical_requirements",
            "path": str(CONTRACT_JSON),
            "sha256": req_hash,
            "expected_sha256": REQ_SHA,
            "bytes": len(canonical),
            "matches": req_hash == REQ_SHA,
            "rule": "json.dumps(requirements, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode('utf-8')",
        }
    )
    if req_hash != REQ_SHA:
        failures.append(f"canonical requirements hash {req_hash} != {REQ_SHA}")
    if contract.get("requirements_sha256") != REQ_SHA:
        failures.append("contract embedded requirements_sha256 differs")
    expected_ids = [f"H{index:02d}" for index in range(1, 16)]
    actual_ids = [item.get("id") for item in requirements if isinstance(item, dict)]
    if actual_ids != expected_ids:
        failures.append(f"contract requirement ids {actual_ids} != {expected_ids}")

    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    if decision.get("decision") != "CONTINUE":
        failures.append("scope review decision is not CONTINUE")
    for key, expected in (
        ("task_version", TASK_VERSION),
        ("product_operation_id", OPERATION_ID),
        ("execution_work_id", WORK_ID),
        ("baseline_head", BASELINE_HEAD),
    ):
        if decision.get(key) != expected:
            failures.append(f"decision {key}={decision.get(key)!r} != {expected!r}")
    authorization = decision.get("authorization", {})
    if (
        authorization.get("task_id") != TASK_ID
        or authorization.get("task_version") != TASK_VERSION
        or authorization.get("work_id") != WORK_ID
    ):
        failures.append("decision authorization IDs differ")
    if decision.get("contract", {}).get("requirements_sha256") != REQ_SHA:
        failures.append("decision contract requirements hash differs")
    if decision.get("contract", {}).get("pin") != CONTRACT_PIN:
        failures.append("decision contract pin differs")
    if decision.get("contract", {}).get("design") != DESIGN_PIN:
        failures.append("decision design pin differs")
    if decision.get("spec", {}).get("sha256") != SCOPE_SHA:
        failures.append("decision scope hash differs")
    if decision.get("frozen_receipt", {}).get("sha256") != FROZEN_SHA:
        failures.append("decision frozen receipt hash differs")

    consumed = json.loads(CONSUMED.read_text(encoding="utf-8"))
    if consumed.get("decision") != "CONTINUE" or consumed.get("actual_completed_result_consumed") is not True:
        failures.append("scope CONTINUE was not actually consumed")
    for key, expected in (
        ("task_id", TASK_ID),
        ("task_version", TASK_VERSION),
        ("operation_id", OPERATION_ID),
        ("work_id", WORK_ID),
        ("decision_sha256", DECISION_SHA),
        ("spec_sha256", SCOPE_SHA),
        ("frozen_receipt_sha256", FROZEN_SHA),
    ):
        if consumed.get(key) != expected:
            failures.append(f"consumed {key}={consumed.get(key)!r} != {expected!r}")

    git = shutil.which("git")
    if git is None:
        failures.append("git executable not found")
        head = ""
    else:
        head_record, head_text = run_command(
            out, logs, "git-rev-parse-HEAD", [git, "rev-parse", "HEAD"], WORKTREE, timeout
        )
        head = head_text.strip().splitlines()[0] if head_text.strip() else ""
        if head_record["exit_code"] != 0 or head != BASELINE_HEAD:
            failures.append(f"worktree HEAD {head!r} != {BASELINE_HEAD}")
        for label, commit in (("contract_pin", CONTRACT_PIN), ("design_pin", DESIGN_PIN)):
            record, _ = run_command(
                out, logs, f"git-cat-file-{label}", [git, "cat-file", "-e", f"{commit}^{{commit}}"], WORKTREE, timeout
            )
            if record["exit_code"] != 0:
                failures.append(f"git object missing for {label}: {commit}")
        status_record, _ = run_command(
            out, logs, "git-status-porcelain", [git, "status", "--porcelain"], WORKTREE, timeout
        )
        if status_record["exit_code"] != 0:
            failures.append("git status failed")

    return {
        "checks": checks,
        "failures": failures,
        "head": head,
        "contract": {
            "id": CONTRACT_ID,
            "revision": CONTRACT_REVISION,
            "pin": CONTRACT_PIN,
            "design": DESIGN_PIN,
            "requirements_ids": expected_ids,
            "requirements_sha256": req_hash,
        },
    }


def snapshot_inputs(out: Path) -> dict:
    source_dir = out / "sources"
    input_dir = out / "inputs"
    source_items = [("rtl", RTL), ("tb", TB), ("runner", HERE)]
    input_items = [
        ("scope", SCOPE),
        ("scope_frozen", FROZEN),
        ("scope_review_decision", DECISION),
        ("scope_continue_consumed", CONSUMED),
        ("scope_review_consumed", DECISION_CONSUMED),
        ("contract_json", CONTRACT_JSON),
        ("contract_md", CONTRACT_MD),
    ]
    manifest = {"sources": [], "inputs": []}
    for role, source in source_items:
        destination = source_dir / source.name
        shutil.copyfile(source, destination)
        manifest["sources"].append(
            {
                "role": role,
                "origin_path": str(source),
                "snapshot_path": relative(destination, out),
                "sha256": sha256_file(destination),
                "bytes": destination.stat().st_size,
            }
        )
    for role, source in input_items:
        destination = input_dir / source.name
        shutil.copyfile(source, destination)
        manifest["inputs"].append(
            {
                "role": role,
                "origin_path": str(source),
                "snapshot_path": relative(destination, out),
                "sha256": sha256_file(destination),
                "bytes": destination.stat().st_size,
            }
        )
    write_json(out / "source_manifest.json", manifest)
    return manifest

def collect_toolchain(out: Path, logs: Path, modelsim_root: Path, timeout: float) -> dict:
    tools: dict[str, dict] = {}
    versions: dict[str, dict] = {}
    for name in ("vlib", "vlog", "vsim"):
        path = modelsim_root / f"{name}.exe"
        if not path.is_file():
            raise RuntimeError(f"missing ModelSim tool: {path}")
        tools[name] = {
            "path": str(path),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    for name, extra in (("vlog", ["-version"]), ("vsim", ["-version"]), ("vlib", ["-version"])):
        record, text = run_command(out, logs, f"tool-{name}-version", [tools[name]["path"], *extra], out, timeout)
        versions[name] = {
            "command_record_seq": record["seq"],
            "exit_code": record["exit_code"],
            "text": text.strip(),
        }
    return {
        "modelsim_root": str(modelsim_root),
        "tools": tools,
        "versions": versions,
        "observed_product": "ModelSim SE-64 10.7, compiler/simulator 2017.12",
    }


def compile_library(out: Path, logs: Path, tools: dict, name: str, rtl: Path, tb: Path, timeout: float) -> Path:
    library = out / name
    if library.exists():
        raise RuntimeError(f"work library already exists: {library}")
    vlib_record, _ = run_command(out, logs, f"{name}-vlib", [tools["vlib"]["path"], str(library)], out, timeout)
    if vlib_record["exit_code"] != 0:
        raise RuntimeError(f"vlib failed for {name}")
    vlog_record, vlog_text = run_command(
        out,
        logs,
        f"{name}-vlog",
        [tools["vlog"]["path"], "-work", str(library), str(rtl), str(tb)],
        out,
        timeout,
    )
    if vlog_record["exit_code"] != 0:
        raise RuntimeError(f"vlog exit {vlog_record['exit_code']} for {name}")
    if "Errors: 0" not in vlog_text or "Warnings: 0" not in vlog_text:
        raise RuntimeError(f"vlog did not report zero errors/warnings for {name}")
    return library


def parse_group_lines(text: str) -> tuple[list[dict], dict | None]:
    groups: list[dict] = []
    for match in GROUP_END_RE.finditer(text):
        groups.append(
            {
                "name": match.group(1),
                "cases": int(match.group(2)),
                "samples": int(match.group(3)),
                "assertions": int(match.group(4)),
                "mismatches": int(match.group(5)),
                "records": int(match.group(6)),
                "fault_events": int(match.group(7)),
            }
        )
    stats_match = TB_STATS_RE.search(text)
    stats = None
    if stats_match:
        stats = {
            "groups": int(stats_match.group(1)),
            "cases": int(stats_match.group(2)),
            "samples": int(stats_match.group(3)),
            "assertions": int(stats_match.group(4)),
            "records": int(stats_match.group(5)),
            "fault_events": int(stats_match.group(6)),
            "mismatches": int(stats_match.group(7)),
        }
    return groups, stats


def run_positive(out: Path, logs: Path, tools: dict, library: Path, spec: dict, timeout: float) -> dict:
    transcript = logs / f"{spec['id']}.transcript"
    argv = [
        tools["vsim"]["path"],
        "-c",
        "-onfinish",
        "stop",
        f"{library.name}.tb_pwm_coherent_capture",
        "-do",
        "run -all; quit -code 0",
        "-l",
        str(transcript),
    ]
    if spec["count_w"] is not None:
        argv.extend(
            [
                f"-gCOUNT_W={spec['count_w']}",
                f"-gWITNESS_W={spec['witness_w']}",
                f"-gTAG_W={spec['tag_w']}",
                f"-gTEST_GROUP={spec['group']}",
            ]
        )
    else:
        argv.append(f"-gTEST_GROUP={spec['group']}")
    record, text = run_command(out, logs, spec["id"], argv, out, timeout)
    groups, stats = parse_group_lines(text)
    failures: list[str] = []
    if record["exit_code"] != 0:
        failures.append(f"vsim exit {record['exit_code']}")
    if "TB_PASS" not in text:
        failures.append("TB_PASS missing")
    if "TB_FAIL" in text:
        failures.append("TB_FAIL observed")
    if "MISMATCH" in text:
        failures.append("MISMATCH observed")
    if stats is None:
        failures.append("TB_STATS missing")
    else:
        expected = spec["stats"]
        actual = (
            stats["groups"], stats["cases"], stats["samples"], stats["assertions"],
            stats["records"], stats["fault_events"], stats["mismatches"],
        )
        if actual != expected:
            failures.append(f"TB_STATS {actual} != {expected}")
        if stats["mismatches"] != 0:
            failures.append("nonzero TB mismatches")
    observed_names = [group["name"] for group in groups]
    if observed_names != list(spec["groups"].keys()):
        failures.append(f"group names {observed_names} != {list(spec['groups'].keys())}")
    for group in groups:
        expected_cases = spec["groups"].get(group["name"])
        if expected_cases is None:
            continue
        if group["cases"] != expected_cases:
            failures.append(f"{group['name']} cases {group['cases']} != {expected_cases}")
        if group["mismatches"] != 0:
            failures.append(f"{group['name']} mismatches {group['mismatches']}")
    if "Errors: 0, Warnings: 0" not in text:
        failures.append("vsim did not report zero errors/warnings")
    return {
        "id": spec["id"],
        "group": spec["group"],
        "parameters": {
            "COUNT_W": spec["count_w"], "WITNESS_W": spec["witness_w"], "TAG_W": spec["tag_w"],
            "source": "defaults" if spec["count_w"] is None else "explicit",
        },
        "command_seq": record["seq"],
        "exit_code": record["exit_code"],
        "groups": groups,
        "stats": stats,
        "failures": failures,
        "passed": not failures,
    }


def run_invalid_guards(out: Path, logs: Path, tools: dict, library: Path, timeout: float) -> list[dict]:
    results: list[dict] = []
    for top, needle in INVALID_TOPS:
        transcript = logs / f"{top}.transcript"
        argv = [
            tools["vsim"]["path"], "-c", "-onfinish", "stop",
            f"{library.name}.{top}", "-do", "run -all; quit -code 0",
            "-l", str(transcript),
        ]
        record, text = run_command(out, logs, top, argv, out, timeout)
        fatal = "** Fatal: DEEPEYE_COHERENT_INVALID_PARAM" in text
        guard_missing = "INVALID_CONFIG_GUARD_MISSING" in text
        diagnostic = "DEEPEYE_COHERENT_INVALID_PARAM" in text
        needle_seen = needle in text
        failures: list[str] = []
        if not fatal:
            failures.append("time-zero DEEPEYE_COHERENT_INVALID_PARAM fatal missing")
        if not diagnostic:
            failures.append("explicit invalid-parameter diagnostic missing")
        if guard_missing:
            failures.append("invalid guard did not fail closed")
        if not needle_seen:
            failures.append(f"diagnostic does not contain {needle}")
        results.append(
            {
                "top": top,
                "expected_parameter_text": needle,
                "command_seq": record["seq"],
                "exit_code": record["exit_code"],
                "modelSim_fatal": fatal,
                "diagnostic_present": diagnostic,
                "guard_missing_fatal": guard_missing,
                "failures": failures,
                "passed": not failures,
            }
        )
    return results

def make_mutants(out: Path, source_manifest: dict) -> list[dict]:
    rtl_source = next(item for item in source_manifest["sources"] if item["role"] == "rtl")
    original = (out / rtl_source["snapshot_path"]).read_text(encoding="utf-8")
    mutant_dir = out / "mutants"
    results: list[dict] = []
    for spec in MUTANTS:
        count = original.count(spec["old"])
        if count != 1:
            raise RuntimeError(f"mutation {spec['id']} matched {count} lines, expected 1")
        mutated = original.replace(spec["old"], spec["new"], 1)
        path = mutant_dir / spec["file"]
        path.write_text(mutated, encoding="utf-8")
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(True), mutated.splitlines(True),
                fromfile="original.sv", tofile=spec["file"],
            )
        )
        diff_path = mutant_dir / f"{spec['id']}.diff"
        diff_path.write_text(diff, encoding="utf-8")
        results.append(
            {
                "id": spec["id"],
                "path": relative(path, out),
                "sha256": sha256_file(path),
                "original_sha256": sha256_file(out / rtl_source["snapshot_path"]),
                "diff_path": relative(diff_path, out),
                "diff_sha256": sha256_file(diff_path),
                "match_count": count,
            }
        )
    return results


def run_mutant(
    out: Path, logs: Path, tools: dict, spec: dict, mutant: dict, tb: Path, timeout: float
) -> dict:
    library = compile_library(
        out, logs, tools, f"work_mutant_{spec['id'].replace('-', '_')}",
        out / mutant["path"], tb, timeout,
    )
    transcript = logs / f"mutant-{spec['id']}.transcript"
    argv = [
        tools["vsim"]["path"], "-c", "-onfinish", "stop",
        f"{library.name}.tb_pwm_coherent_capture",
        "-do", "run -all; quit -code 0",
        "-l", str(transcript),
        "-gCOUNT_W=8", "-gWITNESS_W=8", "-gTAG_W=8",
        f"-gTEST_GROUP={spec['group']}",
    ]
    record, text = run_command(out, logs, f"mutant-{spec['id']}", argv, out, timeout)
    groups, stats = parse_group_lines(text)
    mismatch_labels = MISMATCH_RE.findall(text)
    failures: list[str] = []
    if "TB_FAIL" not in text:
        failures.append("TB_FAIL missing")
    if "TB_PASS" in text:
        failures.append("mutant unexpectedly passed")
    if not mismatch_labels:
        failures.append("no public-port MISMATCH")
    if spec["must_mismatch"] not in mismatch_labels:
        failures.append(f"required mismatch {spec['must_mismatch']} missing")
    if stats is None or stats["mismatches"] < 1:
        failures.append("no nonzero TB mismatch count")
    if "Warnings: 0" not in text:
        failures.append("mutant run reported a warning")
    return {
        "id": spec["id"],
        "group": spec["group"],
        "parameters": {"COUNT_W": 8, "WITNESS_W": 8, "TAG_W": 8, "source": "explicit"},
        "command_seq": record["seq"],
        "exit_code": record["exit_code"],
        "groups": groups,
        "stats": stats,
        "mismatch_labels": mismatch_labels,
        "vsim_errors_expected_for_TB_FAIL": "Errors: 1" in text,
        "failures": failures,
        "passed": not failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="fresh output directory; must not exist")
    parser.add_argument("--modelsim-root", default="D:/modelsim1/win64")
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args(argv)

    out = Path(args.out).resolve()
    if out.exists():
        print(f"REFUSED: output directory exists: {out}", file=sys.stderr)
        return 2
    out.mkdir(parents=True)
    logs = out / "logs"
    logs.mkdir()
    for name in ("sources", "inputs", "mutants"):
        (out / name).mkdir()

    started = utc_now()
    manifest: dict = {
        "schema": 1,
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "operation_id": OPERATION_ID,
        "work_id": WORK_ID,
        "status": "RUNNING",
        "started_utc": started,
        "baseline_head": BASELINE_HEAD,
        "host": {
            "platform": platform.platform(),
            "python": sys.version,
            "cwd": str(WORKTREE),
        },
        "limits": {
            "author_evidence_only": True,
            "main_or_product_acceptance": "not_claimed",
        },
    }
    failures: list[str] = []
    try:
        inputs = verify_inputs(out, logs, args.timeout)
        failures.extend(inputs["failures"])
        sources = snapshot_inputs(out)
        tools = collect_toolchain(out, logs, Path(args.modelsim_root), args.timeout)
        manifest.update({"inputs": inputs, "sources": sources, "toolchain": tools})
        if failures:
            raise RuntimeError("input verification failed")
        tool_paths = tools["tools"]

        rtl_snapshot = out / next(item["snapshot_path"] for item in sources["sources"] if item["role"] == "rtl")
        tb_snapshot = out / next(item["snapshot_path"] for item in sources["sources"] if item["role"] == "tb")
        positive_library = compile_library(out, logs, tool_paths, "work_positive", rtl_snapshot, tb_snapshot, args.timeout)
        positive_results = [
            run_positive(out, logs, tool_paths, positive_library, spec, args.timeout) for spec in POSITIVE
        ]
        invalid_results = run_invalid_guards(out, logs, tool_paths, positive_library, args.timeout)
        mutant_files = make_mutants(out, sources)
        mutant_results = [
            run_mutant(
                out, logs, tool_paths, spec,
                next(item for item in mutant_files if item["id"] == spec["id"]),
                tb_snapshot, args.timeout,
            )
            for spec in MUTANTS
        ]

        original_rtl_after = sha256_file(rtl_snapshot)
        original_worktree_after = sha256_file(RTL)
        original_hash = next(item["sha256"] for item in sources["sources"] if item["role"] == "rtl")
        if original_rtl_after != original_hash:
            failures.append("snapshot RTL changed during mutant runs")
        if original_worktree_after != original_hash:
            failures.append("worktree RTL changed during runs")
        for result in positive_results:
            failures.extend(f"{result['id']}: {item}" for item in result["failures"])
        for result in invalid_results:
            failures.extend(f"{result['top']}: {item}" for item in result["failures"])
        for result in mutant_results:
            failures.extend(f"{result['id']}: {item}" for item in result["failures"])

        w2 = next(
            (group["cases"] for result in positive_results for group in result["groups"]
             if group["name"] == "exhaustive_count_w2_legal_high_triples"), None
        )
        w3 = next(
            (group["cases"] for result in positive_results for group in result["groups"]
             if group["name"] == "exhaustive_count_w3_legal_high_triples"), None
        )
        if w2 != 9 or w3 != 441:
            failures.append(f"exhaustive coverage {w2}+{w3} != 9+441")

        totals = {
            "positive_runs": len(positive_results),
            "positive_groups": sum(len(result["groups"]) for result in positive_results),
            "positive_cases": sum(result["stats"]["cases"] for result in positive_results if result["stats"]),
            "positive_samples": sum(result["stats"]["samples"] for result in positive_results if result["stats"]),
            "positive_assertions": sum(result["stats"]["assertions"] for result in positive_results if result["stats"]),
            "positive_records": sum(result["stats"]["records"] for result in positive_results if result["stats"]),
            "positive_fault_events": sum(result["stats"]["fault_events"] for result in positive_results if result["stats"]),
            "positive_mismatches": sum(result["stats"]["mismatches"] for result in positive_results if result["stats"]),
            "invalid_guards": len(invalid_results),
            "invalid_guards_passed": sum(1 for item in invalid_results if item["passed"]),
            "mutants": len(mutant_results),
            "mutants_rejected_at_public_ports": sum(1 for item in mutant_results if item["passed"]),
            "exhaustive_w2_tuples": w2,
            "exhaustive_w3_tuples": w3,
            "exhaustive_total": (w2 or 0) + (w3 or 0),
        }
        status = "PASS" if not failures else "FAIL"
        manifest.update(
            {
                "status": status,
                "ended_utc": utc_now(),
                "positive_runs": positive_results,
                "invalid_guard_runs": invalid_results,
                "mutant_files": mutant_files,
                "mutant_runs": mutant_results,
                "original_rtl_sha256_after": original_rtl_after,
                "worktree_rtl_sha256_after": original_worktree_after,
                "totals": totals,
                "failures": failures,
                "limitations": {
                    "synthesis": "blocked_no_vivado_not_run",
                    "implementation": "blocked_no_vivado_not_run",
                    "board": "not_run_A_only",
                    "cdc_rdc": "not_run",
                    "formal_cards": "29 not_run",
                    "full_G05_B06_R03": "not_run_unaccepted",
                    "public_ABI_TRACE_type7": "not_opened",
                    "pins_hwh_boot_clock_source_ttl_profile_curvature_motion_authority": "not_run",
                    "physical_capture": "not_claimed",
                    "sampled_transition_liveness_command_applied": "not_claimed",
                    "count_w32_witness_w64": "bounded_observations_only_no_full_traversal",
                    "modelsim_cli_exit_note": "vsim returns 0 after $fatal/TB_FAIL under the recorded -do script; failure is established by the explicit fatal/TB_FAIL public-port log, not by process exit code",
                    "author_evidence_only": "not main acceptance, not product acceptance",
                },
            }
        )
        write_json(out / "run_manifest.json", manifest)
        write_json(
            out / "summary.json",
            {
                "status": status,
                "operation_id": OPERATION_ID,
                "work_id": WORK_ID,
                "totals": totals,
                "failures": failures,
                "run_manifest": "run_manifest.json",
                "run_manifest_sha256": sha256_file(out / "run_manifest.json"),
            },
        )
        (out / "commands.json").write_text(
            json.dumps(COMMANDS, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": status, "totals": totals, "failures": failures}, ensure_ascii=False, indent=2))
        return 0 if status == "PASS" else 1
    except Exception as exc:
        failures.append(f"runner exception: {type(exc).__name__}: {exc}")
        manifest.update(
            {
                "status": "FAIL",
                "ended_utc": utc_now(),
                "failures": failures,
                "exception": f"{type(exc).__name__}: {exc}",
            }
        )
        write_json(out / "run_manifest.json", manifest)
        (out / "commands.json").write_text(
            json.dumps(COMMANDS, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": "FAIL", "failures": failures}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
