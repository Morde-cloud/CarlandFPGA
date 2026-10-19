#!/usr/bin/env python3
"""Fail-closed ModelSim runner for the internal atomic PWM candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
WORK_ID = "B-ATOMIC-PWM-RTL-20261020-12-v1"
OPERATION_ID = "B-DEEPEYE-PWM-ATOMIC-20261020-12"
CONTRACT = {
    "id": "DEEPEYE-HUMAN-LOCK-20261014",
    "revision": 1,
    "requirements": [f"H{i:02d}" for i in range(1, 16)],
    "requirements_sha256":
        "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
    "contract_commit": "f5989cd5defce561f9ba98e6b18fc2682945f0a2",
    "frozen_design": "1011259415a0916054eb580687612580bc1e5f09",
}
EXPECTED_SPEC_SHA256 = (
    "04851894139aebc6c6c0a740d9e1d8d6a732333da98f7da3f6a2ed635c3bb87c"
)
DEFAULT_SEED = "123456789"
REQUIRED_COVER = [
    "boundary_positions_8",
    "same_edge_bypass_checked",
    "invalid_inputs_each_field",
    "held_valid_busy_checked",
    "reset_stop_overlap_checked",
    "period_up_and_down",
    "tag_atomicity_checked",
    "width2_legal_tuples_exhaustive",
    "width2_frame_counts",
    "tag64_boundary_values",
    "unsigned_highbit32_partial",
    "candidate_2m_complete_frame",
    "deterministic_random_12000",
    "default_complete_frames",
    "busy_held_valid_observed",
    "accepted_atomicity_traffic",
    "rejected_invalid_traffic",
    "atomic_apply_traffic",
    "reset_stop_flush_traffic",
    "public_port_checks_above_one_million",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def within(child: Path, parent: Path) -> bool:
    child_text = os.path.normcase(os.path.realpath(str(child)))
    parent_text = os.path.normcase(os.path.realpath(str(parent)))
    try:
        return os.path.commonpath([child_text, parent_text]) == parent_text
    except ValueError:
        return False


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def command_text(argv: list[str]) -> str:
    return subprocess.list2cmdline([str(item) for item in argv])


def process_output_bytes(value: bytes | str | None) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8", errors="replace")


def run_command(
    label: str,
    argv: list[str],
    cwd: Path,
    logs_dir: Path,
    output_root: Path,
    child_env: dict[str, str],
    timeout_seconds: int,
) -> dict:
    sequence = len(run_command.records) + 1
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", label)
    prefix = f"{sequence:02d}_{safe_label}"
    stdout_path = logs_dir / f"{prefix}.stdout.txt"
    stderr_path = logs_dir / f"{prefix}.stderr.txt"
    exit_path = logs_dir / f"{prefix}.exit_code.txt"
    record = {
        "label": label,
        "argv": [str(item) for item in argv],
        "command": command_text(argv),
        "cwd": str(cwd),
        "started_at_utc": utc_now(),
        "timeout_seconds": timeout_seconds,
        "timed_out": False,
        "returncode": None,
        "error": None,
    }
    started = datetime.now(timezone.utc)
    stdout = b""
    stderr = b""
    try:
        completed = subprocess.run(
            [str(item) for item in argv],
            cwd=str(cwd),
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
        )
        stdout = completed.stdout or b""
        stderr = completed.stderr or b""
        record["returncode"] = completed.returncode
    except subprocess.TimeoutExpired as exc:
        record["timed_out"] = True
        record["error"] = "timeout"
        stdout = process_output_bytes(exc.stdout)
        stderr = process_output_bytes(exc.stderr)
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    finished = datetime.now(timezone.utc)
    record["finished_at_utc"] = finished.isoformat()
    record["elapsed_seconds"] = round((finished - started).total_seconds(), 6)
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    exit_text = "timeout" if record["timed_out"] else (
        "null" if record["returncode"] is None else str(record["returncode"])
    )
    exit_path.write_text(exit_text + "\n", encoding="ascii")
    record["stdout"] = str(stdout_path.relative_to(output_root))
    record["stderr"] = str(stderr_path.relative_to(output_root))
    record["exit_code_file"] = str(exit_path.relative_to(output_root))
    record["stdout_sha256"] = sha256_file(stdout_path)
    record["stderr_sha256"] = sha256_file(stderr_path)
    record["exit_code_sha256"] = sha256_file(exit_path)
    run_command.records.append(record)
    return record


run_command.records = []


GUARD_CASES = ((1, 32), (33, 32), (32, 0), (32, 65))
EXPECTED_FROZEN_SCOPE_SHA256 = (
    "7d23a7a1023379bed18b81b794ab4cfaf364d7e1652511a3f382bdce2ec6d95c"
)
EXPECTED_REVIEW_DECISION_SHA256 = (
    "75b72a4279e36b7f9ff29ae9fa4738e6aa238665cb735ee82296e6c81d86e288"
)
ATTRIBUTION = (
    "The frame-boundary atomic update is a B internal design choice for this "
    "bounded increment, not a quoted frozen public ABI."
)
SUMMARY_MINIMUMS = {
    "cases": 9,
    "pass": 9,
    "fail": 0,
    "checks": 1_000_000,
    "default_frames": 200,
    "w2_frames": 198,
    "tag64_frames": 1,
    "accepted": 301,
    "rejected": 51,
    "applied": 101,
    "aborted": 51,
}
COUNTS_EXACT = {
    "boundary": 8,
    "bypass": 1,
    "period": 2,
    "tag": 3,
    "w2": 99,
    "tag64": 4,
    "highbit": 2,
    "long": 2_000_000,
    "random": 12_000,
}
COUNTS_MINIMUMS = {
    "invalid": 8,
    "held": 3,
    "overlaps": 7,
    "busy": 101,
}


class RunnerError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RunnerError(message)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the candidate atomic PWM RTL and fail closed on evidence."
    )
    parser.add_argument("--owned-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--rtl", required=True, type=Path)
    parser.add_argument("--testbench", required=True, type=Path)
    parser.add_argument("--vlib", required=True, type=Path)
    parser.add_argument("--vlog", required=True, type=Path)
    parser.add_argument("--vsim", required=True, type=Path)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--expected-modelsim-version", default="10.7")
    parser.add_argument("--version-timeout", type=int, default=60)
    parser.add_argument("--compile-timeout", type=int, default=300)
    parser.add_argument("--sim-timeout", type=int, default=900)
    parser.add_argument("--guard-timeout", type=int, default=120)
    args = parser.parse_args(argv)

    for name in ("version_timeout", "compile_timeout", "sim_timeout", "guard_timeout"):
        require(getattr(args, name) > 0, f"{name} must be positive")
    require(re.fullmatch(r"[0-9]+", args.seed) is not None,
            "seed must be a non-negative decimal %d value")
    require(1 <= int(args.seed) <= 2_147_483_647,
            "seed must fit a positive signed 32-bit integer")
    require(re.fullmatch(r"[0-9]+(?:\.[0-9]+)*",
                         args.expected_modelsim_version) is not None,
            "expected ModelSim version must be a decimal version")
    return args


def resolve_existing_file(path: Path, label: str) -> Path:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise RunnerError(f"{label} does not resolve: {path}: {exc}") from exc
    require(resolved.is_file(), f"{label} is not a regular file: {resolved}")
    return resolved


def validate_paths(args: argparse.Namespace) -> dict[str, Path]:
    try:
        owned_root = args.owned_root.expanduser().resolve(strict=True)
    except OSError as exc:
        raise RunnerError(f"owned root does not resolve: {args.owned_root}: {exc}") from exc
    require(owned_root.is_dir(), f"owned root is not a directory: {owned_root}")

    output_candidate = args.output.expanduser()
    if not output_candidate.is_absolute():
        output_candidate = Path.cwd() / output_candidate
    output = output_candidate.resolve(strict=False)
    require(not os.path.lexists(str(output)),
            f"output already exists and will not be overwritten: {output}")
    try:
        output_parent = output.parent.resolve(strict=True)
    except OSError as exc:
        raise RunnerError(f"output parent does not resolve: {output.parent}: {exc}") from exc
    require(output_parent.is_dir(), f"output parent is not a directory: {output_parent}")
    output = output_parent / output.name
    require(output != owned_root, "output must not be the owned root")
    require(within(output, owned_root), "output must be strictly inside --owned-root")
    require(within(output_parent, owned_root),
            "output parent must be inside --owned-root")

    requested = {
        "rtl": args.rtl,
        "testbench": args.testbench,
        "vlib": args.vlib,
        "vlog": args.vlog,
        "vsim": args.vsim,
    }
    resolved: dict[str, Path] = {}
    for label, path in requested.items():
        resolved[label] = resolve_existing_file(path, label)
        require(not within(resolved[label], output),
                f"{label} input aliases the new output tree")

    labels = list(resolved)
    for index, left in enumerate(labels):
        for right in labels[index + 1:]:
            try:
                aliased = os.path.samefile(resolved[left], resolved[right])
            except OSError as exc:
                raise RunnerError(
                    f"cannot compare {left}/{right} aliases: {exc}"
                ) from exc
            require(not aliased, f"aliased inputs are forbidden: {left} == {right}")

    return {
        **resolved,
        "owned_root": owned_root,
        "output": output,
    }


def create_output_tree(output: Path) -> tuple[Path, Path]:
    output.mkdir(mode=0o755, exist_ok=False)
    logs_dir = output / "logs"
    inputs_dir = output / "inputs"
    logs_dir.mkdir()
    inputs_dir.mkdir()
    return logs_dir, inputs_dir


def copy_and_hash(source: Path, destination: Path, label: str) -> dict:
    require(not os.path.lexists(str(destination)),
            f"snapshot destination already exists: {destination}")
    shutil.copyfile(source, destination)
    source_hash = sha256_file(source)
    copied_hash = sha256_file(destination)
    require(source_hash == copied_hash, f"{label} copy hash mismatch")
    return {
        "label": label,
        "source": str(source),
        "snapshot": str(destination),
        "size_bytes": destination.stat().st_size,
        "sha256": source_hash,
    }


def write_source_manifest(
    paths: dict[str, Path], inputs_dir: Path, output: Path
) -> dict:
    rtl_destination = inputs_dir / "rtl" / paths["rtl"].name
    tb_destination = inputs_dir / "testbench" / paths["testbench"].name
    runner_destination = inputs_dir / "runner" / Path(__file__).name
    for parent in (rtl_destination.parent, tb_destination.parent,
                   runner_destination.parent):
        parent.mkdir()
    manifest = {
        "generated_at_utc": utc_now(),
        "files": [
            copy_and_hash(paths["rtl"], rtl_destination, "rtl"),
            copy_and_hash(paths["testbench"], tb_destination, "testbench"),
            copy_and_hash(Path(__file__).resolve(), runner_destination, "runner"),
        ],
    }
    for item in manifest["files"]:
        snapshot = Path(item["snapshot"])
        require(within(snapshot, output), "source snapshot escaped output")
        item["snapshot"] = str(snapshot.relative_to(output))
    write_json(output / "source_manifest.json", manifest)
    return manifest


def discover_tools(paths: dict[str, Path], output: Path) -> dict:
    tools = {}
    for label in ("vlib", "vlog", "vsim"):
        tool_path = paths[label]
        tools[label] = {
            "path": str(tool_path),
            "size_bytes": tool_path.stat().st_size,
            "sha256": sha256_file(tool_path),
        }
    manifest = {
        "generated_at_utc": utc_now(),
        "discovery_scope": "path, size and SHA256 before any tool invocation",
        "tools": tools,
    }
    write_json(output / "tool_discovery.json", manifest)
    return manifest


def write_runner_start(args: argparse.Namespace, paths: dict[str, Path],
                       output: Path) -> None:
    payload = {
        "generated_at_utc": utc_now(),
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "work_id": WORK_ID,
        "operation_id": OPERATION_ID,
        "contract": CONTRACT,
        "expected_spec_sha256": EXPECTED_SPEC_SHA256,
        "expected_frozen_scope_sha256": EXPECTED_FROZEN_SCOPE_SHA256,
        "expected_review_decision_sha256": EXPECTED_REVIEW_DECISION_SHA256,
        "attribution": ATTRIBUTION,
        "scope_status": "scope-approved only; source/test author verification pending",
        "all_29_formal_cards": "not_run",
        "physical_board": "A-only",
        "vivado_or_synthesis": "not_run",
        "python_version": sys.version.split()[0],
        "cli": {
            "owned_root": str(paths["owned_root"]),
            "output": str(output),
            "rtl": str(paths["rtl"]),
            "testbench": str(paths["testbench"]),
            "vlib": str(paths["vlib"]),
            "vlog": str(paths["vlog"]),
            "vsim": str(paths["vsim"]),
            "seed": args.seed,
            "expected_modelsim_version": args.expected_modelsim_version,
        },
    }
    write_json(output / "runner_start.json", payload)


def read_record_text(record: dict, output: Path) -> str:
    chunks = []
    for key in ("stdout", "stderr"):
        relative = Path(record[key])
        path = output / relative
        require(within(path, output), f"raw log escaped output: {path}")
        require(path.is_file(), f"raw log missing: {path}")
        chunks.append(path.read_bytes().decode("utf-8", errors="replace"))
    return "".join(chunks)


def require_clean_process(record: dict, label: str) -> str:
    require(record["error"] is None, f"{label} launch failed: {record['error']}")
    require(not record["timed_out"], f"{label} timed out")
    require(record["returncode"] == 0,
            f"{label} returned nonzero exit code: {record['returncode']}")
    return str(record["stdout"])


def require_zero_errors(text: str, label: str) -> None:
    require(
        re.search(r"(?m)^[ \t]*Errors:[ \t]*0,[ \t]*Warnings:[ \t]*0[ \t]*\r?$",
                  text) is not None,
        f"{label} did not report Errors: 0, Warnings: 0",
    )
    require(
        re.search(r"(?m)^[ \t]*#?[ \t]*\*\*[ \t]*(?:Error|Fatal)",
                  text) is None,
        f"{label} contains a simulator error/fatal marker",
    )


def run_tool_versions(
    args: argparse.Namespace,
    paths: dict[str, Path],
    output: Path,
    logs_dir: Path,
    child_env: dict[str, str],
) -> dict:
    versions = {}
    for label in ("vlog", "vsim"):
        record = run_command(
            f"{label}_version",
            [paths[label], "-version"],
            output,
            logs_dir,
            output,
            child_env,
            args.version_timeout,
        )
        require_clean_process(record, f"{label} version")
        text = read_record_text(record, output)
        version_pattern = rf"\b{label}\s+{re.escape(args.expected_modelsim_version)}\b"
        require(re.search(version_pattern, text) is not None,
                f"{label} did not report expected version {args.expected_modelsim_version}")
        first_line = next((line.strip() for line in text.splitlines()
                           if line.strip()), "")
        versions[label] = {
            "version_command": [str(paths[label]), "-version"],
            "first_line": first_line,
            "exit_code": record["returncode"],
            "stdout": record["stdout"],
            "stderr": record["stderr"],
        }
    payload = {
        "generated_at_utc": utc_now(),
        "vlib_version_option": "not invoked; ModelSim 10.7 vlib -version reports usage",
        "versions": versions,
    }
    write_json(output / "tool_versions.json", payload)
    return payload


def parse_named_integers(line: str, label: str) -> dict[str, int]:
    pairs = re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=(-?[0-9]+)", line)
    require(pairs, f"{label} has no integer key/value fields")
    keys = [key for key, _ in pairs]
    require(len(keys) == len(set(keys)), f"{label} repeats a key")
    return {key: int(value) for key, value in pairs}


def parse_main_transcript(text: str, seed: str) -> dict:
    failure_markers = (
        "APWM_CHECK_FAIL",
        "APWM_CASE_FAIL",
        "APWM_FAIL",
        "APWM_WATCHDOG_TIMEOUT",
        "** Fatal",
        "** Error",
    )
    for marker in failure_markers:
        require(marker not in text, f"simulation transcript contains {marker}")

    seed_lines = re.findall(r"(?m)^[ \t]*#?[ \t]*APWM_SEED[ \t]+(-?[0-9]+)[ \t]*\r?$",
                            text)
    require(len(seed_lines) == 1, "expected exactly one APWM_SEED line")
    require(int(seed_lines[0]) == int(seed), "simulation seed marker differs from CLI")

    cover_lines = re.findall(
        r"(?m)^[ \t]*#?[ \t]*APWM_COVER[ \t]+([A-Za-z0-9_]+)[ \t]*\r?$",
        text,
    )
    require(len(cover_lines) == len(REQUIRED_COVER),
            "unexpected number of APWM_COVER lines")
    require(set(cover_lines) == set(REQUIRED_COVER),
            "coverage marker names do not match the required list")

    summary_lines = re.findall(
        r"(?m)^[ \t]*#?[ \t]*APWM_SUMMARY[ \t]+([^\r\n]+)\r?$", text
    )
    require(len(summary_lines) == 1, "expected exactly one APWM_SUMMARY line")
    summary = parse_named_integers(summary_lines[0], "APWM_SUMMARY")
    for key, expected in SUMMARY_MINIMUMS.items():
        require(key in summary, f"APWM_SUMMARY missing {key}")
        if key in ("cases", "pass", "fail"):
            require(summary[key] == expected,
                    f"APWM_SUMMARY {key}={summary[key]} expected {expected}")
        else:
            require(summary[key] >= expected,
                    f"APWM_SUMMARY {key}={summary[key]} below {expected}")

    counts_lines = re.findall(
        r"(?m)^[ \t]*#?[ \t]*APWM_COVER_COUNTS[ \t]+([^\r\n]+)\r?$", text
    )
    require(len(counts_lines) == 1, "expected exactly one APWM_COVER_COUNTS line")
    counts = parse_named_integers(counts_lines[0], "APWM_COVER_COUNTS")
    for key, expected in COUNTS_EXACT.items():
        require(counts.get(key) == expected,
                f"APWM_COVER_COUNTS {key}={counts.get(key)} expected {expected}")
    for key, minimum in COUNTS_MINIMUMS.items():
        require(counts.get(key) is not None and counts[key] >= minimum,
                f"APWM_COVER_COUNTS {key} below {minimum}")

    require(len(re.findall(r"(?m)^[ \t]*#?[ \t]*APWM_END[ \t]+pass[ \t]*\r?$",
                           text)) == 1,
            "missing or repeated APWM_END pass")
    require(len(re.findall(r"(?m)^[ \t]*#?[ \t]*APWM_DONE[ \t]*\r?$",
                           text)) == 1,
            "missing or repeated APWM_DONE")
    require_zero_errors(text, "main simulation")
    return {"seed": int(seed), "coverage": sorted(cover_lines),
            "summary": summary, "counts": counts}


def validate_replay(output: Path, seed: str) -> dict:
    replay = output / "replay_events.log"
    require(replay.is_file(), "replay_events.log was not produced")
    require(replay.stat().st_size <= 8 * 1024 * 1024,
            "replay_events.log exceeds the bounded 8 MiB evidence limit")
    text = replay.read_text(encoding="utf-8", errors="strict")
    lines = text.splitlines()
    expected_header = f"# ATOMIC_PWM_SEED {int(seed)}"
    require(lines and lines[0] == expected_header,
            "replay seed header missing or mismatched")
    step_count = sum(
        1 for line in lines
        if re.fullmatch(r"STEP[ \t]+[^\r\n]+", line) is not None
    )
    require(step_count == 12_000,
            f"replay contains {step_count} STEP vectors, expected 12000")
    require(len(lines) <= 20_000, "replay line count exceeds bounded evidence limit")
    return {
        "path": "replay_events.log",
        "size_bytes": replay.stat().st_size,
        "sha256": sha256_file(replay),
        "seed_header": expected_header,
        "step_count": step_count,
        "line_count": len(lines),
    }


def run_parameter_guards(
    args: argparse.Namespace,
    paths: dict[str, Path],
    output: Path,
    logs_dir: Path,
    child_env: dict[str, str],
) -> list[dict]:
    results = []
    for count_w, tag_w in GUARD_CASES:
        label = f"guard_invalid_COUNT_W_{count_w}_TAG_W_{tag_w}"
        argv = [
            paths["vsim"], "-c", "-onfinish", "stop", "-lib", "work",
            "deepeye_atomic_pwm", f"-gCOUNT_W={count_w}", f"-gTAG_W={tag_w}",
            "-do", "run -all; quit -f",
        ]
        record = run_command(
            label, argv, output, logs_dir, output, child_env, args.guard_timeout
        )
        require(record["error"] is None, f"{label} launch failed: {record['error']}")
        require(not record["timed_out"], f"{label} timed out")
        text = read_record_text(record, output)
        marker = f"ATOMIC_PWM_UNSUPPORTED_PARAMETERS COUNT_W={count_w} TAG_W={tag_w}"
        require(marker in text, f"{label} omitted the explicit parameter guard")
        require(("** Fatal:" in text) or ("** Error" in text),
                f"{label} did not fail")
        require("Time: 0 ns" in text, f"{label} did not fail at simulation time zero")
        require("APWM_DONE" not in text, f"{label} unexpectedly completed")
        results.append({
            "COUNT_W": count_w,
            "TAG_W": tag_w,
            "marker": marker,
            "failed_at_time_zero": True,
            "process_exit_code": record["returncode"],
            "process_exit_code_gated": False,
            "stdout": record["stdout"],
            "stderr": record["stderr"],
            "accepted_on_marker_instead_of_process_status": True,
        })
    write_json(output / "parameter_guards.json", {
        "generated_at_utc": utc_now(),
        "simulation_only": True,
        "cases": results,
    })
    return results


def execute_run(
    args: argparse.Namespace,
    paths: dict[str, Path],
    output: Path,
    logs_dir: Path,
    inputs_dir: Path,
    child_env: dict[str, str],
) -> dict:
    source_manifest = write_source_manifest(paths, inputs_dir, output)
    tool_discovery = discover_tools(paths, output)
    write_runner_start(args, paths, output)
    versions = run_tool_versions(args, paths, output, logs_dir, child_env)

    vlib_command = [paths["vlib"], "work"]
    vlib_record = run_command(
        "vlib_create_work", vlib_command, output, logs_dir, output, child_env,
        args.compile_timeout,
    )
    require_clean_process(vlib_record, "vlib")
    require((output / "work").is_dir(), "vlib did not create the work library")

    vlog_command = [
        paths["vlog"], "-sv", "-work", "work",
        paths["rtl"], paths["testbench"],
    ]
    vlog_record = run_command(
        "vlog_compile", vlog_command, output, logs_dir, output, child_env,
        args.compile_timeout,
    )
    require_clean_process(vlog_record, "vlog")
    require_zero_errors(read_record_text(vlog_record, output), "vlog compile")

    vsim_command = [
        paths["vsim"], "-c", "-onfinish", "stop", "-lib", "work",
        "tb_atomic_pwm", f"+ATOMIC_PWM_SEED={args.seed}",
        "-do", "run -all; quit -f",
    ]
    vsim_record = run_command(
        "vsim_main", vsim_command, output, logs_dir, output, child_env,
        args.sim_timeout,
    )
    require_clean_process(vsim_record, "vsim")
    vsim_text = read_record_text(vsim_record, output)
    parsed = parse_main_transcript(vsim_text, args.seed)
    replay = validate_replay(output, args.seed)
    guards = run_parameter_guards(args, paths, output, logs_dir, child_env)

    summary = {
        "generated_at_utc": utc_now(),
        "status": "pass",
        "author_verification_only": True,
        "independent_acceptance": False,
        "publication_performed": False,
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "work_id": WORK_ID,
        "operation_id": OPERATION_ID,
        "contract": CONTRACT,
        "normative_scope_sha256": EXPECTED_FROZEN_SCOPE_SHA256,
        "coordinator_decision_sha256": EXPECTED_REVIEW_DECISION_SHA256,
        "attribution": ATTRIBUTION,
        "tool_discovery": tool_discovery,
        "tool_versions": versions,
        "source_manifest": source_manifest,
        "main_simulation": parsed,
        "replay_vectors": replay,
        "parameter_guards": guards,
        "limitations": [
            "Author testcase success is not independent acceptance.",
            "Simulation only; no synthesis, implementation, timing, CDC/RDC or board result.",
            "The 32-bit high-bit case is a bounded partial observation, not a full 2^32-period run.",
            "All 29 formal cards remain not_run; physical-board work remains A-only.",
            "This is not a public ABI, register, pin, capture, stop-authority or motion grant.",
        ],
    }
    write_json(output / "run_summary.json", summary)
    return summary


def write_command_catalog(output: Path) -> None:
    write_json(output / "command_catalog.json", {
        "generated_at_utc": utc_now(),
        "record_count": len(run_command.records),
        "records": run_command.records,
    })


def file_hashes(output: Path, exclusions: set[str]) -> list[dict]:
    entries = []
    for path in sorted(output.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(output).as_posix()
        if relative in exclusions:
            continue
        entries.append({
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return entries


def finalize_evidence(output: Path, status_payload: dict) -> None:
    write_json(output / "RUN_STATUS.json", status_payload)
    manifest = {
        "generated_at_utc": utc_now(),
        "status": status_payload["status"],
        "author_verification_only": True,
        "not_a_publication": True,
        "not_independent_acceptance": True,
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "work_id": WORK_ID,
        "operation_id": OPERATION_ID,
        "files": file_hashes(
            output,
            {"AUTHOR_EVIDENCE_MANIFEST.json", "SHA256SUMS.txt"},
        ),
    }
    write_json(output / "AUTHOR_EVIDENCE_MANIFEST.json", manifest)
    sums_path = output / "SHA256SUMS.txt"
    lines = []
    for item in file_hashes(output, {"SHA256SUMS.txt"}):
        lines.append(f"{item['sha256']}  {item['path']}")
    sums_path.write_text("\n".join(lines) + "\n", encoding="ascii")


def main(argv: list[str] | None = None) -> int:
    run_command.records.clear()
    try:
        args = parse_args(argv)
        paths = validate_paths(args)
    except RunnerError as exc:
        print(f"ATOMIC_PWM_RUNNER_FAIL stage=arguments error={exc}", file=sys.stderr)
        return 2

    output = paths["output"]
    try:
        logs_dir, inputs_dir = create_output_tree(output)
    except Exception as exc:
        print(
            f"ATOMIC_PWM_RUNNER_FAIL stage=create_output path={output} "
            f"error={type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    child_env = os.environ.copy()
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    child_env["PYTHONUTF8"] = "1"
    try:
        summary = execute_run(
            args, paths, output, logs_dir, inputs_dir, child_env
        )
        write_command_catalog(output)
        summary["command_count"] = len(run_command.records)
        write_json(output / "run_summary.json", summary)
        finalize_evidence(output, {
            "status": "pass",
            "generated_at_utc": utc_now(),
            "message": "Candidate RTL passed all author checks.",
            "run_summary": "run_summary.json",
            "author_verification_only": True,
            "independent_acceptance": False,
        })
        counts = summary["main_simulation"]["summary"]
        print(
            "ATOMIC_PWM_RUNNER_PASS "
            f"output={output} checks={counts['checks']} "
            f"cases={counts['cases']} guards={len(summary['parameter_guards'])}"
        )
        return 0
    except Exception as exc:
        failure = {
            "status": "fail",
            "generated_at_utc": utc_now(),
            "stage": "author_verification",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "author_verification_only": True,
            "independent_acceptance": False,
            "publication_performed": False,
            "command_count": len(run_command.records),
        }
        try:
            write_command_catalog(output)
            finalize_evidence(output, failure)
        except Exception as evidence_exc:
            print(
                f"ATOMIC_PWM_RUNNER_FAIL output={output} "
                f"error={exc} evidence_finalize_error={evidence_exc}",
                file=sys.stderr,
            )
            return 1
        print(
            f"ATOMIC_PWM_RUNNER_FAIL output={output} "
            f"error={type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
