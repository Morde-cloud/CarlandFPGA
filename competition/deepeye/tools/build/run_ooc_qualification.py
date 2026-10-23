#!/usr/bin/env python3
"""Bounded B06 out-of-context synthesis qualification runner.

The runner consumes only Git blobs from one pinned commit and invokes one clean
Vivado batch process per top. It never implements, places, routes, programs a
board, edits RTL, waives warnings, commits, or publishes.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014/v1"
OPERATION_ID = "B-DEEPEYE-OOC-SYNTHESIS-20261024-33"
CONTRACT_ID = "DEEPEYE-HUMAN-LOCK-20261014/revision1"
CONTRACT_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
CONTRACT_SHA256 = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
CONTRACT_JSON_PATH = "docs/competition/deepeye-2026/immutable_scope.json"
DESIGN_COMMIT = "1011259415a0916054eb580687612580bc1e5f09"
SOURCE_COMMIT = "bbfb11439b35e0866a6d2486f3857b92ed6cf529"
HANDOFF_HEAD = "04e3a46eb1169afca0c133815a9b9f3da15d89f5"
SCOPE_SHA256 = "8e1286387eceaa121d659decb546c524785707f681a750a1e090221cfa8d8ca5"
PART = "xc7z020clg400-1"
DEFAULT_TOOL_ROOT = Path(r"D:\pynq\AMD2026\2026.1\Vivado")
VIVADO_BAT_SHA256 = "a5f91ee867cea61be4355caf9f7a784c6c34351c5c1d1618562ddda299e38a8b"
VIVADO_EXE_SHA256 = "3a4e9e3f03d20cd1994dc2eff44566af7a10eaaae04429e9d460bffe3b0e86e4"
NATIVE_CMD = Path(r"C:\Windows\System32\cmd.exe")
EXPECTED_VERSION = "2026.1"
SCOPE_MAILBOX_PATH = "competition/deepeye/rtl/deepeye_snapshot_mailbox.sv"


@dataclass(frozen=True)
class SourcePin:
    git_path: str
    module: str
    clock_mode: str
    blob: str
    size: int


PINS: tuple[SourcePin, ...] = (
    SourcePin("competition/deepeye/fpga/acquisition/deepeye_raw_scan_queue.sv", "deepeye_raw_scan_queue", "clock:clk", "7768438f960710b02eb98fd62523c5e0e77809bc", 6642),
    SourcePin("competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv", "deepeye_sample_scan_capture", "clock:clk", "72317ee23608af60da2da4de7ebb600b8732dd24", 17174),
    SourcePin("competition/deepeye/fpga/codec/deepeye_block_encoder.sv", "deepeye_block_encoder", "clock:clk", "62454c17e7934f7e4eca95062b1952dfdeeb0d8a", 21032),
    SourcePin("competition/deepeye/fpga/control3d/deepeye_atomic_pwm.sv", "deepeye_atomic_pwm", "clock:clk", "65d2f3137f3136c918657a19957e4c54d8220f33", 7983),
    SourcePin("competition/deepeye/fpga/control3d/deepeye_first_capture_deadline.sv", "deepeye_first_capture_deadline", "clock:clk", "b7eb5e32c124e7f2aa4b4f0618118b56bdf4794f", 6293),
    SourcePin("competition/deepeye/fpga/control3d/deepeye_pwm_applied_capture.sv", "deepeye_pwm_applied_capture", "clock:clk", "45b020f24dff3d36a702dabbc3064b213959aa28", 15841),
    SourcePin("competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv", "deepeye_pwm_coherent_capture", "clock:clk", "7b3444f889371b7fb7c71eee2aace402ee83690f", 17155),
    SourcePin("competition/deepeye/fpga/control3d/deepeye_pwm_edge_measure.sv", "deepeye_pwm_edge_measure", "clock:clk", "b0fa78e394919ad1ba28820ec47ad85af54ddf1b", 8384),
    SourcePin("competition/deepeye/fpga/stream/deepeye_block_stream.sv", "deepeye_block_stream", "clock:clk", "18579551131eb4991e310b14a1f43bf4323a1c03", 14493),
    SourcePin("competition/deepeye/fpga/stream/deepeye_encoded_frame_queue.sv", "deepeye_encoded_frame_queue", "clock:clk", "784915148a1c0e6bac81d2c60ab3d07105a33adc", 16640),
    SourcePin("competition/deepeye/fpga/transport/deepeye_crc16_byte.sv", "deepeye_crc16_byte", "none", "888e8f2f86bf8083b192ae63b294158a86bdf390", 1875),
    SourcePin("competition/deepeye/fpga/transport/deepeye_uart_frame_tx.sv", "deepeye_uart_frame_tx", "clock:clk", "fa1a790141da1e04ef6787465e7b45f660a015f9", 13807),
    SourcePin("competition/deepeye/fpga/transport/deepeye_uart_rx.sv", "deepeye_uart_rx", "clock:clk", "99443de80ed862f1070091d77f8f8ec3b2893c83", 11182),
    SourcePin("competition/deepeye/fpga/transport/deepeye_uart_tx.sv", "deepeye_uart_tx", "clock:clk", "9f70df5ee2d98a38dcf3afd8c0b383bb81cc9f57", 6811),
    SourcePin("competition/deepeye/fpga/transport/deepeye_uart_wire_rx.sv", "deepeye_uart_wire_rx", "clock:clk", "11a9b9fca26b02098dae0fd7866058fe9721f71c", 6763),
    SourcePin("competition/deepeye/fpga/transport/deepeye_wire_parser.sv", "deepeye_wire_parser", "clock:clk", "d1cbce67ccdb7cf824c871cb283edc75529543e4", 12258),
    SourcePin("competition/deepeye/fpga/transport/deepeye_wire_serializer.sv", "deepeye_wire_serializer", "clock:clk", "b36e3ca89724485531287e8c050dcf566dfbc262", 9705),
    SourcePin("competition/deepeye/fpga/transport/deepeye_wire_uart_tx.sv", "deepeye_wire_uart_tx", "clock:clk", "7a7faccbc80debccbad12a4d1179c5f23311f932", 10807),
    SourcePin("competition/deepeye/rtl/control/deepeye_snapshot_mailbox.sv", "deepeye_snapshot_mailbox", "dual_clock", "d117827487a3759a12f52b02b6ef62c5132d06ba", 5790),
)

assert len(PINS) == 19
assert len({pin.git_path for pin in PINS}) == 19

def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha1_git_blob(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def file_record(path: Path, base: Path | None = None) -> dict[str, Any]:
    data = path.read_bytes()
    record: dict[str, Any] = {
        "path": str(path),
        "relative_path": str(path.relative_to(base)) if base is not None else None,
        "size": len(data),
        "sha256": sha256_bytes(data),
    }
    return record


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_bytes(payload.encode("utf-8"))


def discover_repository() -> Path:
    script_dir = Path(__file__).resolve().parent
    process = subprocess.run(
        ["git", "-C", str(script_dir), "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError("not inside a Git worktree: " + process.stderr.decode("utf-8", "replace"))
    return Path(process.stdout.decode("utf-8").strip()).resolve()


def create_fresh_attempt(repository: Path, requested: str) -> Path:
    allowed_parent = (repository / "competition/deepeye/evidence/build/ooc-20261024-33/author").resolve()
    output = Path(requested)
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()
    else:
        output = output.resolve()
    if output.parent != allowed_parent or output == allowed_parent:
        raise RuntimeError(f"output must be one fresh child folder of {allowed_parent}")
    if output.exists():
        raise RuntimeError(f"refusing to reuse existing output folder: {output}")
    allowed_parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    return output


def initial_result(args: argparse.Namespace, repository: Path, attempt: Path) -> dict[str, Any]:
    return {
        "schema": "deepeye.b06.ooc-qualification/v2",
        "task_id": TASK_ID,
        "operation_id": OPERATION_ID,
        "contract": {
            "id": CONTRACT_ID,
            "commit": CONTRACT_COMMIT,
            "requirements_sha256_expected": CONTRACT_SHA256,
        },
        "design_commit": DESIGN_COMMIT,
        "scope": {
            "sha256_expected": SCOPE_SHA256,
            "path": "D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/b06-ooc-20261024-33/SCOPE.md",
        },
        "author": {
            "thread_id": args.author_thread,
            "turn_id": args.author_turn,
            "parent_thread_id": args.parent_thread,
            "parent_turn_id": args.parent_turn,
        },
        "repository": str(repository),
        "attempt_dir": str(attempt),
        "started_at_utc": utc_now(),
        "completed_at_utc": None,
        "overall_status": "in_progress",
        "completion_kind": "synthesis_artifacts_only",
        "engineering_acceptance": "not_claimed",
        "fatal_error": None,
        "git_commands": [],
        "contract_verification": None,
        "source": None,
        "tool": None,
        "harness": None,
        "environment_policy": {
            "preserves_parent_environment": True,
            "required_overrides": ["TEMP", "TMP", "TMPDIR", "XILINX_LOCAL_USER_DATA", "PYTHONDONTWRITEBYTECODE"],
            "owned_local_user_data": "fresh run cache directory",
            "cwd": "fresh run work directory",
            "hidden_process": True,
            "max_threads": 2,
        },
        "runs": [],
        "skipped": [],
        "totals": {
            "planned": len(PINS),
            "attempted": 0,
            "artifacts_complete": 0,
            "clean_drc": 0,
            "warning_bearing": 0,
            "failed": 0,
            "skipped": 0,
        },
        "not_run": [
            "place_design", "route_design", "write_bitstream", "write_hwh",
            "timing_closure", "cdc_rdc_signoff", "full_product_implementation",
            "physical_board", "system_test",
        ],
        "limitations": [
            "Out-of-context synthesis is not whole-design implementation or timing closure.",
            "Only a 10 ns clock is applied to the named top clock ports; input and output delays are unknown.",
            "DRC and timing reports are diagnostics and are not waivers or acceptance evidence.",
            "The combinational CRC top is intentionally left without a clock constraint.",
        ],
    }


def git_command(
    state: dict[str, Any],
    label: str,
    repository: Path,
    arguments: Sequence[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    argv = ["git", "-C", str(repository), *arguments]
    process = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    record: dict[str, Any] = {
        "label": label,
        "argv": argv,
        "exit_code": process.returncode,
        "stdout_size": len(process.stdout),
        "stdout_sha256": sha256_bytes(process.stdout),
        "stderr_size": len(process.stderr),
        "stderr_sha256": sha256_bytes(process.stderr),
    }
    if process.returncode != 0:
        record["stderr_text"] = process.stderr.decode("utf-8", "replace")
    state["git_commands"].append(record)
    if check and process.returncode != 0:
        raise RuntimeError(f"Git command failed ({label}): {record.get('stderr_text', '').strip()}")
    return process


def verify_contract(state: dict[str, Any], repository: Path) -> None:
    process = git_command(
        state,
        "read-pinned-immutable-scope",
        repository,
        ["show", f"{CONTRACT_COMMIT}:{CONTRACT_JSON_PATH}"],
    )
    document = json.loads(process.stdout.decode("utf-8"))
    requirements = document["requirements"]
    canonical = json.dumps(
        requirements,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    observed = sha256_bytes(canonical)
    if observed != CONTRACT_SHA256:
        raise RuntimeError(f"requirements SHA256 mismatch: expected {CONTRACT_SHA256}, observed {observed}")
    state["contract_verification"] = {
        "verified": True,
        "requirements_count": len(requirements),
        "requirements_sha256": observed,
    }


def parse_ls_tree(payload: bytes) -> dict[str, tuple[str, int]]:
    entries: dict[str, tuple[str, int]] = {}
    for raw_entry in payload.split(b"\0"):
        if not raw_entry:
            continue
        metadata, raw_path = raw_entry.split(b"\t", 1)
        fields = metadata.split()
        if len(fields) != 4:
            raise RuntimeError(f"unexpected git ls-tree entry: {metadata!r}")
        _mode, object_type, blob, size_text = fields
        if object_type != b"blob":
            raise RuntimeError(f"non-blob source entry: {raw_path!r}")
        entries[raw_path.decode("utf-8")] = (blob.decode("ascii"), int(size_text))
    return entries


def prepare_source_snapshot(state: dict[str, Any], repository: Path, attempt: Path) -> dict[str, Any]:
    if SOURCE_COMMIT != "bbfb11439b35e0866a6d2486f3857b92ed6cf529":
        raise RuntimeError("the source pin is not the frozen B06 commit")
    source_type = git_command(state, "source-object-type", repository, ["cat-file", "-t", SOURCE_COMMIT])
    if source_type.stdout.strip() != b"commit":
        raise RuntimeError("pinned source object is not a commit")
    resolved = git_command(state, "source-commit-resolve", repository, ["rev-parse", f"{SOURCE_COMMIT}^{{commit}}"])
    if resolved.stdout.decode("ascii").strip() != SOURCE_COMMIT:
        raise RuntimeError("source commit did not resolve exactly")
    git_command(state, "design-is-ancestor", repository, ["merge-base", "--is-ancestor", DESIGN_COMMIT, "HEAD"])
    git_command(state, "source-is-ancestor", repository, ["merge-base", "--is-ancestor", SOURCE_COMMIT, "HEAD"])
    git_command(state, "handoff-is-ancestor", repository, ["merge-base", "--is-ancestor", HANDOFF_HEAD, "HEAD"])

    handoff_parents = git_command(
        state,
        "handoff-head-parents",
        repository,
        ["rev-list", "--parents", "-n", "1", HANDOFF_HEAD],
    ).stdout.decode("ascii").split()
    if handoff_parents[:2] != [HANDOFF_HEAD, SOURCE_COMMIT]:
        raise RuntimeError("handoff head is not the direct child of the frozen source commit")

    scope_mailbox_probe = git_command(
        state,
        "scope-mailbox-path-probe",
        repository,
        ["cat-file", "-e", f"{SOURCE_COMMIT}:{SCOPE_MAILBOX_PATH}"],
        check=False,
    )
    if scope_mailbox_probe.returncode == 0:
        raise RuntimeError("scope mailbox path unexpectedly exists; inventory must be reviewed")

    tree_payload = git_command(
        state,
        "list-frozen-sv",
        repository,
        [
            "ls-tree", "-r", "-l", "-z", SOURCE_COMMIT, "--",
            "competition/deepeye/fpga",
            "competition/deepeye/rtl/control/deepeye_snapshot_mailbox.sv",
        ],
    ).stdout
    actual = {path: value for path, value in parse_ls_tree(tree_payload).items() if path.endswith(".sv")}
    expected = {pin.git_path: (pin.blob, pin.size) for pin in PINS}
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise RuntimeError(f"source inventory mismatch; missing={missing}, extra={extra}")
    for path, pinned in expected.items():
        if actual[path] != pinned:
            raise RuntimeError(f"source blob/size mismatch for {path}: {actual[path]} != {pinned}")

    snapshot_root = attempt / "source_snapshot"
    sources: list[dict[str, Any]] = []
    source_paths_for_tcl: list[str] = []
    for pin in PINS:
        raw = git_command(
            state,
            f"snapshot-{pin.module}",
            repository,
            ["show", f"{SOURCE_COMMIT}:{pin.git_path}"],
        ).stdout
        if len(raw) != pin.size or sha1_git_blob(raw) != pin.blob:
            raise RuntimeError(f"snapshot byte/hash mismatch for {pin.git_path}")
        relative = Path(pin.git_path).relative_to("competition/deepeye")
        destination = snapshot_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        source_paths_for_tcl.append(str(destination.resolve()))
        sources.append({
            "git_path": pin.git_path,
            "module": pin.module,
            "clock_mode": pin.clock_mode,
            "git_blob": pin.blob,
            "git_size": pin.size,
            "snapshot_path": str(destination.resolve()),
            "snapshot_size": len(raw),
            "snapshot_sha256": sha256_bytes(raw),
        })

    source_list = snapshot_root / "SOURCES.txt"
    source_list.write_bytes(("\n".join(source_paths_for_tcl) + "\n").encode("utf-8"))
    summary = {
        "commit": SOURCE_COMMIT,
        "handoff_head": HANDOFF_HEAD,
        "observed_head": git_command(state, "observed-head", repository, ["rev-parse", "HEAD"]).stdout.decode("ascii").strip(),
        "expected_count": len(PINS),
        "actual_count": len(sources),
        "scope_mailbox_path": SCOPE_MAILBOX_PATH,
        "scope_mailbox_path_tracked": False,
        "resolved_mailbox_path": "competition/deepeye/rtl/control/deepeye_snapshot_mailbox.sv",
        "scope_path_discrepancy": "The literal scope path does not exist at the frozen commit; the unique tracked mailbox path is used without RTL modification.",
        "source_list_path": str(source_list.resolve()),
        "source_list_sha256": sha256_bytes(source_list.read_bytes()),
        "modules": sources,
    }
    manifest_path = attempt / "SOURCE_MANIFEST.json"
    write_json(manifest_path, summary)
    summary["manifest_path"] = str(manifest_path)
    summary["manifest_sha256"] = sha256_bytes(manifest_path.read_bytes())
    return summary


def prepare_tool(tool_root_text: str) -> dict[str, Any]:
    tool_root = Path(tool_root_text).resolve()
    wrapper = tool_root / "bin/vivado.bat"
    executable = tool_root / "bin/unwrapped/win64.o/vivado.exe"
    for required in (wrapper, executable, NATIVE_CMD):
        if not required.is_file():
            raise RuntimeError(f"required tool path is missing: {required}")
    wrapper_record = file_record(wrapper)
    executable_record = file_record(executable)
    if wrapper_record["sha256"] != VIVADO_BAT_SHA256:
        raise RuntimeError("Vivado wrapper SHA256 does not match the exact frozen tool")
    if executable_record["sha256"] != VIVADO_EXE_SHA256:
        raise RuntimeError("Vivado executable SHA256 does not match the exact frozen tool")
    if str(NATIVE_CMD).lower() != r"c:\windows\system32\cmd.exe":
        raise RuntimeError("native cmd.exe path spelling changed")
    return {
        "root": str(tool_root),
        "wrapper": wrapper_record,
        "executable": executable_record,
        "native_cmd": file_record(NATIVE_CMD),
        "expected_version": EXPECTED_VERSION,
        "part": PART,
    }


def prepare_harness(repository: Path, attempt: Path) -> dict[str, Any]:
    tcl_source = repository / "competition/deepeye/fpga/build_qualification/ooc_qualification.tcl"
    tcl_snapshot = attempt / "harness/ooc_qualification.tcl"
    tcl_snapshot.parent.mkdir(parents=True, exist_ok=True)
    tcl_bytes = tcl_source.read_bytes()
    tcl_snapshot.write_bytes(tcl_bytes)
    runner_source = Path(__file__).resolve()
    return {
        "runner_path": str(runner_source),
        "runner_sha256": sha256_bytes(runner_source.read_bytes()),
        "tcl_source_path": str(tcl_source),
        "tcl_source_sha256": sha256_bytes(tcl_bytes),
        "tcl_snapshot_path": str(tcl_snapshot.resolve()),
        "tcl_snapshot_sha256": sha256_bytes(tcl_snapshot.read_bytes()),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


def launch_vivado(
    pin: SourcePin,
    run_index: int,
    attempt: Path,
    source_list: Path,
    harness: dict[str, Any],
    tool: dict[str, Any],
    timeout_seconds: int,
) -> tuple[dict[str, Any], bytes, bytes]:
    run_id = f"{run_index:02d}_{pin.module}"
    run_dir = attempt / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    under_review = [run_dir / "work", run_dir / "tmp", run_dir / "cache"]
    for path in under_review:
        path.mkdir(parents=True, exist_ok=False)

    tcl_path = Path(harness["tcl_snapshot_path"])
    wrapper = Path(tool["wrapper"]["path"])
    argv = [
        str(NATIVE_CMD),
        "/d",
        "/c",
        str(wrapper),
        "-mode",
        "batch",
        "-nojournal",
        "-nolog",
        "-notrace",
        "-source",
        str(tcl_path),
        "-tclargs",
        str(run_dir.resolve()),
        pin.module,
        str(source_list.resolve()),
        pin.clock_mode,
    ]
    child_env = os.environ.copy()
    child_env.update({
        "TEMP": str(under_review[1].resolve()),
        "TMP": str(under_review[1].resolve()),
        "TMPDIR": str(under_review[1].resolve()),
        "XILINX_LOCAL_USER_DATA": str(under_review[2].resolve()),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    started_utc = utc_now()
    started_monotonic = time.monotonic()
    process = subprocess.Popen(
        argv,
        cwd=str(under_review[0]),
        env=child_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        creationflags=creationflags,
    )
    timed_out = False
    kill_record: dict[str, Any] | None = None
    try:
        stdout_bytes, stderr_bytes = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/taskkill.exe"
        kill_process = subprocess.run(
            [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        kill_record = {
            "argv": [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
            "exit_code": kill_process.returncode,
            "stdout_sha256": sha256_bytes(kill_process.stdout),
            "stderr_sha256": sha256_bytes(kill_process.stderr),
            "stdout_text": kill_process.stdout.decode("utf-8", "replace"),
            "stderr_text": kill_process.stderr.decode("utf-8", "replace"),
        }
        stdout_bytes, stderr_bytes = process.communicate(timeout=60)
    completed_utc = utc_now()
    duration_seconds = round(time.monotonic() - started_monotonic, 6)

    stdout_path = run_dir / "vivado.stdout.bin"
    stderr_path = run_dir / "vivado.stderr.bin"
    stdout_path.write_bytes(stdout_bytes)
    stderr_path.write_bytes(stderr_bytes)
    process_record = {
        "run_id": run_id,
        "argv": argv,
        "command_line": subprocess.list2cmdline(argv),
        "executable": str(NATIVE_CMD),
        "wrapper": str(wrapper),
        "cwd": str(under_review[0].resolve()),
        "environment_overrides": {
            "TEMP": child_env["TEMP"],
            "TMP": child_env["TMP"],
            "TMPDIR": child_env["TMPDIR"],
            "XILINX_LOCAL_USER_DATA": child_env["XILINX_LOCAL_USER_DATA"],
            "PYTHONDONTWRITEBYTECODE": child_env["PYTHONDONTWRITEBYTECODE"],
        },
        "shell": False,
        "hidden": bool(creationflags & getattr(subprocess, "CREATE_NO_WINDOW", 0)),
        "creationflags": creationflags,
        "pid": process.pid,
        "started_at_utc": started_utc,
        "completed_at_utc": completed_utc,
        "duration_seconds": duration_seconds,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "exit_code": process.returncode,
        "timeout_kill": kill_record,
        "stdout": file_record(stdout_path),
        "stderr": file_record(stderr_path),
    }
    write_json(run_dir / "PROCESS.json", process_record)
    return process_record, stdout_bytes, stderr_bytes


def normalize_path_text(value: str) -> str:
    return os.path.normcase(os.path.normpath(str(Path(value).resolve())))


def same_path(observed: str, expected: Path) -> bool:
    try:
        return normalize_path_text(observed) == normalize_path_text(str(expected))
    except (OSError, ValueError):
        return False


def parse_marker_line(line: str) -> tuple[str, dict[str, str]]:
    parts = line.split("|")
    marker = parts[0]
    if not re.fullmatch(r"B06_OOC_[A-Z0-9_]+", marker):
        raise ValueError("invalid marker name")
    if len(parts) < 2:
        raise ValueError("marker has no fields")
    fields: dict[str, str] = {}
    for token in parts[1:]:
        if not re.fullmatch(r"[a-z][a-z0-9_]*=[^|\r\n]+", token):
            raise ValueError(f"invalid marker field {token!r}")
        key, value = token.split("=", 1)
        if key in fields:
            raise ValueError(f"duplicate marker field {key!r}")
        fields[key] = value
    return marker, fields


def parse_utilization(path: Path) -> dict[str, str]:
    summary: dict[str, str] = {}
    if not path.is_file():
        return summary
    pattern = re.compile(r"^\|\s*(Slice LUTs|Slice Registers|Block RAM Tile|DSPs|Bonded IOB)\s*\|\s*([0-9.]+)\s*\|")
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            summary[match.group(1)] = match.group(2)
    return summary


def validate_marker_stream(
    stdout_lines: list[str],
    *,
    run_id: str,
    pin: SourcePin,
    attempt: Path,
    cache_path: Path,
) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    parsed: list[tuple[str, dict[str, str], str]] = []
    for line_number, line in enumerate(stdout_lines, start=1):
        if line.startswith("B06_OOC_"):
            try:
                marker, fields = parse_marker_line(line)
            except ValueError as error:
                failures.append(f"malformed_marker:line={line_number}:{error}")
                continue
            parsed.append((marker, fields, line))
        elif "B06_OOC_" in line:
            failures.append(f"unanchored_marker_text:line={line_number}")

    raw_lines = [row[2] for row in parsed]
    for line, count in Counter(raw_lines).items():
        if count > 1:
            failures.append(f"duplicate_exact_marker_row:count={count}:{line}")

    kinds = [row[0] for row in parsed]
    expected_clock_ports = {"none": [], "clock:clk": ["clk"], "dual_clock": ["src_clk", "dst_clk"]}[pin.clock_mode]
    clock_marker = "B06_OOC_CLOCK_POLICY" if pin.clock_mode == "none" else "B06_OOC_CLOCK"
    expected_kinds = (
        ["B06_OOC_BEGIN", "B06_OOC_USER_DATA", "B06_OOC_VERSION", "B06_OOC_PART", "B06_OOC_THREADS"]
        + ["B06_OOC_SOURCE_READ"] * len(PINS)
        + ["B06_OOC_SOURCE_COUNT", "B06_OOC_SYNTH_BEGIN", "B06_OOC_SYNTH_DONE", "B06_OOC_DESIGN"]
        + [clock_marker] * max(1, len(expected_clock_ports))
        + ["B06_OOC_REPORT"] * 4
        + ["B06_OOC_CHECKPOINT", "B06_OOC_END"]
    )
    if kinds != expected_kinds:
        failures.append("marker_sequence_mismatch:" + ",".join(kinds))

    expected_sources = []
    for expected_pin in PINS:
        relative = Path(expected_pin.git_path).relative_to("competition/deepeye")
        expected_sources.append((attempt / "source_snapshot" / relative).resolve())
    report_paths = {
        "utilization": (attempt / "runs" / run_id / "reports/utilization.rpt").resolve(),
        "timing_summary": (attempt / "runs" / run_id / "reports/timing_summary.rpt").resolve(),
        "check_timing": (attempt / "runs" / run_id / "reports/check_timing.rpt").resolve(),
        "drc": (attempt / "runs" / run_id / "reports/drc.rpt").resolve(),
    }
    checkpoint_path = (attempt / "runs" / run_id / "ooc.dcp").resolve()
    summary: dict[str, Any] = {
        "marker_sequence": kinds,
        "source_reads": [],
        "clock_ports": [],
        "report_kinds": [],
        "report_paths": {},
        "checkpoint_path": None,
        "drc_violation_count": None,
        "end_status": None,
        "design_port_count": None,
    }
    if kinds != expected_kinds:
        return failures, summary

    rows = [row[1] for row in parsed]
    exact_fields = {
        "B06_OOC_BEGIN": {"run_id", "top", "clock_mode"},
        "B06_OOC_USER_DATA": {"mode", "path"},
        "B06_OOC_VERSION": {"value"},
        "B06_OOC_PART": {"requested", "matched"},
        "B06_OOC_THREADS": {"requested", "actual"},
        "B06_OOC_SOURCE_READ": {"index", "path"},
        "B06_OOC_SOURCE_COUNT": {"count"},
        "B06_OOC_SYNTH_BEGIN": {"top", "mode", "part"},
        "B06_OOC_SYNTH_DONE": {"top", "status"},
        "B06_OOC_DESIGN": {"part", "port_count"},
        "B06_OOC_CLOCK": {"name", "port", "period_ns", "status"},
        "B06_OOC_CLOCK_POLICY": {"mode", "reason", "constrained"},
        "B06_OOC_CHECKPOINT": {"status", "path"},
        "B06_OOC_END": {"run_id", "top", "status"},
    }
    for marker, fields, _line in parsed:
        if marker == "B06_OOC_REPORT":
            continue
        required = exact_fields.get(marker)
        if required is None:
            failures.append(f"unknown_marker_kind:{marker}")
        elif set(fields) != required:
            failures.append(f"marker_fields:{marker}:{sorted(fields)}")

    begin = rows[0]
    if begin.get("run_id") != run_id or begin.get("top") != pin.module or begin.get("clock_mode") != pin.clock_mode:
        failures.append("begin_identity_mismatch")
    user_data = rows[1]
    if user_data.get("mode") != "owned_cache" or not same_path(user_data.get("path", ""), cache_path):
        failures.append("local_user_data_cache_identity_mismatch")
    if rows[2].get("value") != EXPECTED_VERSION:
        failures.append("tool_version_mismatch")
    if rows[3] != {"requested": PART, "matched": "1"}:
        failures.append("part_marker_mismatch")
    if rows[4] != {"requested": "2", "actual": "2"}:
        failures.append("max_threads_marker_mismatch")

    source_offset = 5
    for offset, expected_path in enumerate(expected_sources, start=1):
        fields = rows[source_offset + offset - 1]
        summary["source_reads"].append(fields)
        if fields.get("index") != str(offset) or not same_path(fields.get("path", ""), expected_path):
            failures.append(f"source_read_identity_mismatch:index={offset}")
    source_count_index = source_offset + len(PINS)
    if rows[source_count_index].get("count") != str(len(PINS)):
        failures.append("source_count_mismatch")

    synth_begin = rows[source_count_index + 1]
    if synth_begin != {"top": pin.module, "mode": "out_of_context", "part": PART}:
        failures.append("synthesis_begin_identity_mismatch")
    synth_done = rows[source_count_index + 2]
    if synth_done != {"top": pin.module, "status": "complete"}:
        failures.append("synthesis_done_identity_mismatch")
    design = rows[source_count_index + 3]
    if design.get("part") != PART or not design.get("port_count", "").isdigit():
        failures.append("design_identity_mismatch")
    if design.get("port_count", "").isdigit():
        summary["design_port_count"] = int(design["port_count"])

    clock_start = source_count_index + 4
    if pin.clock_mode == "none":
        policy = rows[clock_start]
        if policy != {"mode": "none", "reason": "combinational_no_clock", "constrained": "0"}:
            failures.append("clock_policy_identity_mismatch")
    else:
        for offset, expected_port in enumerate(expected_clock_ports):
            fields = rows[clock_start + offset]
            summary["clock_ports"].append(fields)
            if fields != {
                "name": expected_port,
                "port": expected_port,
                "period_ns": "10.000",
                "status": "created",
            }:
                failures.append(f"clock_identity_mismatch:port={expected_port}")

    report_start = clock_start + max(1, len(expected_clock_ports))
    expected_report_kinds = ["utilization", "timing_summary", "check_timing", "drc"]
    for offset, expected_kind in enumerate(expected_report_kinds):
        fields = rows[report_start + offset]
        summary["report_kinds"].append(fields.get("kind"))
        expected_fields = {"kind", "status", "path"}
        if expected_kind in {"timing_summary", "check_timing"}:
            expected_fields.add("diagnostic_only")
        if expected_kind == "drc":
            expected_fields.add("violation_count")
        if set(fields) != expected_fields:
            failures.append(f"report_fields:{expected_kind}:{sorted(fields)}")
            continue
        if fields.get("kind") != expected_kind or fields.get("status") != "written":
            failures.append(f"report_identity_mismatch:{expected_kind}")
        expected_path = report_paths[expected_kind]
        summary["report_paths"][expected_kind] = fields.get("path")
        if not same_path(fields.get("path", ""), expected_path):
            failures.append(f"report_path_mismatch:{expected_kind}")
        if expected_kind in {"timing_summary", "check_timing"} and fields.get("diagnostic_only") != "1":
            failures.append(f"report_diagnostic_identity_mismatch:{expected_kind}")
        if expected_kind == "drc":
            violation_text = fields.get("violation_count", "")
            if not violation_text.isdigit():
                failures.append("drc_violation_count_invalid")
            else:
                summary["drc_violation_count"] = int(violation_text)

    checkpoint = rows[report_start + 4]
    summary["checkpoint_path"] = checkpoint.get("path")
    if checkpoint.get("status") != "written" or not same_path(checkpoint.get("path", ""), checkpoint_path):
        failures.append("checkpoint_identity_mismatch")
    end = rows[report_start + 5]
    if end != {"run_id": run_id, "top": pin.module, "status": "artifact_complete"}:
        failures.append("end_identity_mismatch")
    summary["end_status"] = end.get("status")
    return failures, summary


def engineering_findings(
    *,
    artifact_complete: bool,
    drc_violation_count: int | None,
    warning_count: int,
    critical_warning_count: int,
    latch_related_line_count: int,
    multidriver_related_line_count: int,
) -> dict[str, Any]:
    return {
        "artifact_complete": artifact_complete,
        "clean_drc": drc_violation_count == 0 if isinstance(drc_violation_count, int) else None,
        "drc_violation_count": drc_violation_count,
        "latch_related_line_count": latch_related_line_count,
        "multidriver_related_line_count": multidriver_related_line_count,
        "warning_count": warning_count,
        "critical_warning_count": critical_warning_count,
        "timing_acceptance": "not_assessed_diagnostic_only",
        "cdc_rdc_acceptance": "not_assessed_out_of_context",
        "product_acceptance": "not_claimed",
    }


def classify_run(
    pin: SourcePin,
    run_index: int,
    attempt: Path,
    process_record: dict[str, Any],
    stdout_bytes: bytes,
    stderr_bytes: bytes,
) -> dict[str, Any]:
    run_dir = attempt / "runs" / process_record["run_id"]
    stdout_text = stdout_bytes.decode("utf-8", "replace")
    stderr_text = stderr_bytes.decode("utf-8", "replace")
    stdout_lines = stdout_text.splitlines()
    stderr_lines = stderr_text.splitlines()
    cache_path = (run_dir / "cache").resolve()
    protocol_failures, marker_summary = validate_marker_stream(
        stdout_lines,
        run_id=process_record["run_id"],
        pin=pin,
        attempt=attempt,
        cache_path=cache_path,
    )
    stderr_marker_lines = [line for line in stderr_lines if "B06_OOC_" in line]
    if stderr_marker_lines:
        protocol_failures.append(f"marker_text_on_stderr:{len(stderr_marker_lines)}")
    marker_lines = [line for line in stdout_lines if "B06_OOC_" in line]

    all_message_lines = stdout_lines + stderr_lines
    warning_lines = [line for line in all_message_lines if line.lstrip().startswith("WARNING:")]
    critical_warning_lines = [line for line in all_message_lines if line.lstrip().startswith("CRITICAL WARNING:")]
    error_lines = [line for line in all_message_lines if line.lstrip().startswith(("ERROR:", "FATAL:"))]
    tcl_error_lines = [line for line in all_message_lines if line.startswith("B06_OOC_TCL_ERROR|")]
    latch_related_lines = [line for line in all_message_lines if "latch" in line.lower()]
    multidriver_related_lines = [
        line for line in all_message_lines
        if "multiple driver" in line.lower() or "multiple drivers" in line.lower() or "multi-driven" in line.lower()
    ]

    required_files = {
        "utilization_report": run_dir / "reports/utilization.rpt",
        "timing_summary_report": run_dir / "reports/timing_summary.rpt",
        "check_timing_report": run_dir / "reports/check_timing.rpt",
        "drc_report": run_dir / "reports/drc.rpt",
        "checkpoint": run_dir / "ooc.dcp",
    }
    output_records = {name: file_record(path) for name, path in required_files.items() if path.is_file() and path.stat().st_size > 0}
    missing_outputs = [name for name in required_files if name not in output_records]

    diagnostic_record = {
        "stdout_raw_path": str(run_dir / "vivado.stdout.bin"),
        "stdout_raw_sha256": sha256_bytes(stdout_bytes),
        "stderr_raw_path": str(run_dir / "vivado.stderr.bin"),
        "stderr_raw_sha256": sha256_bytes(stderr_bytes),
        "markers": marker_lines,
        "stderr_marker_text": stderr_marker_lines,
        "warnings": warning_lines,
        "critical_warnings": critical_warning_lines,
        "error_lines": error_lines,
        "tcl_error_lines": tcl_error_lines,
        "latch_related_lines": latch_related_lines,
        "multidriver_related_lines": multidriver_related_lines,
        "marker_validation_failures": protocol_failures,
    }
    diagnostics_path = run_dir / "DIAGNOSTICS.json"
    write_json(diagnostics_path, diagnostic_record)

    failures: list[str] = []
    if process_record["timed_out"]:
        failures.append("process_timeout")
    if process_record["exit_code"] != 0:
        failures.append(f"nonzero_exit:{process_record['exit_code']}")
    failures.extend(protocol_failures)
    if error_lines:
        failures.append(f"error_lines:{len(error_lines)}")
    if tcl_error_lines:
        failures.append(f"tcl_error_lines:{len(tcl_error_lines)}")
    if missing_outputs:
        failures.append("missing_required_outputs:" + ",".join(missing_outputs))

    status = "artifact_complete" if not failures else "failed"
    synthesis_started = "B06_OOC_SYNTH_BEGIN" in marker_summary["marker_sequence"]
    systemic_failure = status == "failed" and (not synthesis_started or process_record["timed_out"])
    drc_violation_count = marker_summary.get("drc_violation_count")
    findings = engineering_findings(
        artifact_complete=status == "artifact_complete",
        drc_violation_count=drc_violation_count,
        warning_count=len(warning_lines),
        critical_warning_count=len(critical_warning_lines),
        latch_related_line_count=len(latch_related_lines),
        multidriver_related_line_count=len(multidriver_related_lines),
    )
    source_snapshot_path = attempt / "source_snapshot" / Path(pin.git_path).relative_to("competition/deepeye")
    source_snapshot_record = file_record(source_snapshot_path)
    run_result = {
        "run_id": process_record["run_id"],
        "run_index": run_index,
        "top": pin.module,
        "source_git_path": pin.git_path,
        "source_git_blob": pin.blob,
        "source_size": pin.size,
        "source_snapshot_path": source_snapshot_record["path"],
        "source_sha256": source_snapshot_record["sha256"],
        "clock_mode": pin.clock_mode,
        "status": status,
        "synthesis_started": synthesis_started,
        "systemic_failure": systemic_failure,
        "failures": failures,
        "process_path": str((run_dir / "PROCESS.json").resolve()),
        "process_sha256": sha256_bytes((run_dir / "PROCESS.json").read_bytes()),
        "exit_code": process_record["exit_code"],
        "timed_out": process_record["timed_out"],
        "pid": process_record["pid"],
        "duration_seconds": process_record["duration_seconds"],
        "markers": {
            "sequence": marker_summary["marker_sequence"],
            "end_status": marker_summary["end_status"],
            "source_read": len(marker_summary["source_reads"]),
            "clocks": [row.get("port") for row in marker_summary["clock_ports"]],
            "reports": marker_summary["report_kinds"],
            "report_paths": marker_summary["report_paths"],
            "checkpoint_path": marker_summary["checkpoint_path"],
            "design_port_count": marker_summary["design_port_count"],
        },
        "diagnostics": {
            "warning_count": len(warning_lines),
            "critical_warning_count": len(critical_warning_lines),
            "error_line_count": len(error_lines),
            "drc_violation_count": drc_violation_count,
            "path": str(diagnostics_path.resolve()),
            "sha256": sha256_bytes(diagnostics_path.read_bytes()),
        },
        "engineering_findings": findings,
        "completion_kind": "synthesis_artifact_only",
        "engineering_acceptance": "not_claimed",
        "raw_process": process_record,
        "outputs": output_records,
        "utilization_summary": parse_utilization(required_files["utilization_report"]),
    }
    write_json(run_dir / "RUN.json", run_result)
    return run_result


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", default=SOURCE_COMMIT)
    parser.add_argument("--tool-root", default=str(DEFAULT_TOOL_ROOT))
    parser.add_argument("--output", required=True, help="fresh child folder under the owned author evidence directory")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--author-thread", required=True)
    parser.add_argument("--author-turn", required=True)
    parser.add_argument("--parent-thread", required=True)
    parser.add_argument("--parent-turn", required=True)
    args = parser.parse_args(argv)
    if args.source_commit != SOURCE_COMMIT:
        parser.error(f"--source-commit must be the frozen commit {SOURCE_COMMIT}")
    if not 30 <= args.timeout_seconds <= 1800:
        parser.error("--timeout-seconds must be in 30..1800")
    return args


def mark_skipped(result: dict[str, Any], reason: str) -> None:
    attempted_tops = {run["top"] for run in result["runs"]}
    result["skipped"] = [
        {"top": pin.module, "reason": reason}
        for pin in PINS
        if pin.module not in attempted_tops
    ]
    result["totals"]["skipped"] = len(result["skipped"])


def execute(args: argparse.Namespace) -> int:
    repository = discover_repository()
    attempt = create_fresh_attempt(repository, args.output)
    result = initial_result(args, repository, attempt)
    write_json(attempt / "RESULT.json", result)
    try:
        verify_contract(result, repository)
        result["source"] = prepare_source_snapshot(result, repository, attempt)
        result["tool"] = prepare_tool(args.tool_root)
        result["harness"] = prepare_harness(repository, attempt)
        write_json(attempt / "PREFLIGHT.json", {
            "contract": result["contract_verification"],
            "source": result["source"],
            "tool": result["tool"],
            "harness": result["harness"],
            "git_commands": result["git_commands"],
        })

        print(f"B06 source inventory: {result['source']['actual_count']} frozen Git blobs", flush=True)
        for pin in PINS:
            print(f"  {pin.module}: {pin.blob} {pin.size} {pin.clock_mode}", flush=True)

        stop_reason: str | None = None
        for run_index, pin in enumerate(PINS, start=1):
            print(f"B06 OOC run {run_index:02d}/{len(PINS)}: {pin.module}", flush=True)
            process_record, stdout_bytes, stderr_bytes = launch_vivado(
                pin,
                run_index,
                attempt,
                Path(result["source"]["source_list_path"]),
                result["harness"],
                result["tool"],
                args.timeout_seconds,
            )
            run_result = classify_run(pin, run_index, attempt, process_record, stdout_bytes, stderr_bytes)
            result["runs"].append(run_result)
            result["totals"]["attempted"] = len(result["runs"])
            result["totals"]["artifacts_complete"] = sum(run["status"] == "artifact_complete" for run in result["runs"])
            result["totals"]["clean_drc"] = sum(run["engineering_findings"]["clean_drc"] is True for run in result["runs"])
            result["totals"]["warning_bearing"] = sum(
                run["engineering_findings"]["warning_count"] > 0
                or run["engineering_findings"]["critical_warning_count"] > 0
                for run in result["runs"]
            )
            result["totals"]["failed"] = sum(run["status"] == "failed" for run in result["runs"])
            write_json(attempt / "RESULT.json", result)
            print(
                f"B06 OOC run {run_index:02d} {run_result['status']} exit={run_result['exit_code']} "
                f"warnings={run_result['diagnostics']['warning_count']} "
                f"critical={run_result['diagnostics']['critical_warning_count']}",
                flush=True,
            )
            if run_result["systemic_failure"]:
                stop_reason = f"systemic failure in {pin.module}; no further tops started"
                break

        if stop_reason is not None:
            mark_skipped(result, stop_reason)
        else:
            result["skipped"] = []
            result["totals"]["skipped"] = 0
        if (
            result["totals"]["artifacts_complete"] == len(PINS)
            and result["totals"]["failed"] == 0
            and result["totals"]["skipped"] == 0
        ):
            result["overall_status"] = "artifacts_complete"
        else:
            result["overall_status"] = "failed"
    except Exception as error:  # Preserve an exact failed author attempt.
        result["fatal_error"] = f"{type(error).__name__}: {error}"
        result["overall_status"] = "failed"
        mark_skipped(result, "not started after runner failure")
    finally:
        result["completed_at_utc"] = utc_now()
        result["execution"] = {
            "sequential": True,
            "one_new_process_per_top": True,
            "rerun_or_attached_process": False,
            "source_read_from_git_snapshots": True,
            "implementation_or_board_tool_invoked": False,
            "engineering_acceptance": "not_claimed",
        }
        write_json(attempt / "RESULT.json", result)

    print(json.dumps({
        "attempt_dir": str(attempt),
        "overall_status": result["overall_status"],
        "totals": result["totals"],
        "fatal_error": result["fatal_error"],
    }, ensure_ascii=False), flush=True)
    return 0 if result["overall_status"] == "artifacts_complete" else 1


def main() -> int:
    args = parse_arguments()
    try:
        return execute(args)
    except Exception as error:
        print(f"B06 runner setup failure: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
