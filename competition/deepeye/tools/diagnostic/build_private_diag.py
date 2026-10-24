"""Prepare, or explicitly authorize one private diagnostic Vivado build.

Preparation never launches Vivado. A build requires a separate main authorization
and the main's exact five-source SHA map. No retries or existing output reuse.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import types
import uuid
import xml.etree.ElementTree as ET

TASK = "DEEPEYE-IMPLEMENTATION-20261014"
WORK = "B-MINIMAL-PL-BUILD-PREP-20261025-54-v1"
MAIN = "01a13b55-095b-7461-8dd5-5476a130bd82"
CONTRACT = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
FROZEN_DESIGN = "1011259415a0916054eb580687612580bc1e5f09"
PRODUCT_HEAD = "323786cab808113e0bd75f7aab405fc957269ff6"
PART = "xc7z020clg400-1"
CREATE_SUSPENDED = 0x00000004  # Win32 CREATE_SUSPENDED; absent from Python subprocess exports.
VLNV = "carlandfpga.local:diagnostic:deepeye_private_axi_diag:1.0"
INSTANCE = "private_diag_0"
SOURCES = (
    "fpga/acquisition/deepeye_buffered_scan_capture.sv",
    "fpga/acquisition/deepeye_sample_scan_capture.sv",
    "fpga/acquisition/deepeye_raw_scan_queue.sv",
    "fpga/acquisition/deepeye_scan_lane_stream.sv",
    "fpga/diagnostic/deepeye_private_axi_diag.sv",
)
DEPENDENCIES = dict(zip(SOURCES[:4], (
    "c8a540db8122b8f5520582a0f1fa9be0c43cb54a62f03c7c4edc893906f28411",
    "fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d",
    "630e14803d82b3379517d91626de4ad7e7d3c509ad14363b3164031a5f633ee4",
    "b3c9d2024d9325191538cf08fec9a652ff8ff0ae316ec9af96078f85cf5be3cc",
)))
BOARD_HASHES = {
    "board.xml": "a565dcb39737d551cbbbb73c0053b973c40bb3dce2274943370d3032c0fea9ae",
    "preset.xml": "18528f84aea4da503cdb3104f7706fabfb3b6ad09b78b25199cc316afa4c8cfe",
    "part0_pins.xml": "3c809473938e135a925b563b5371c8687ee05c4089376e7318c0c56524cc8a0f",
    "pynq_z2.jpg": "54b4bb2da4a38a647d3df030ec13fe63e427235980ce9ae1ca44ce9a91af4546",
}
HELPER_SHA = "3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3"
TOOL_HASHES = {
    "bin/vivado.bat": "a5f91ee867cea61be4355caf9f7a784c6c34351c5c1d1618562ddda299e38a8b",
    "bin/unwrapped/win64.o/vivado.exe": "3a4e9e3f03d20cd1994dc2eff44566af7a10eaaae04429e9d460bffe3b0e86e4",
}


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(path):
    p = Path(path).resolve()
    return {"path": str(p), "bytes": p.stat().st_size, "sha256": digest(p)}


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def require(test, message):
    if not test:
        raise RuntimeError(message)


def copy_exact(source, target, expected=None):
    raw = Path(source).read_bytes()
    if expected is not None:
        require(hashlib.sha256(raw).hexdigest() == expected, f"source hash mismatch: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as f:
        f.write(raw)
    require(target.read_bytes() == raw, f"snapshot mismatch: {target}")
    return record(target)


def expected_map(path, building=False):
    supplied = load_json(path)
    require(isinstance(supplied, dict), "SHA map must be a JSON object")
    aliases = {Path(p).name: p for p in SOURCES}
    result = {}
    for key, value in supplied.items():
        canonical = key if key in SOURCES else aliases.get(key)
        require(canonical is not None and canonical not in result, f"unknown/duplicate source key: {key}")
        require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "invalid SHA256")
        result[canonical] = value
    required = set(SOURCES if building else SOURCES[:4])
    require(required <= result.keys() <= set(SOURCES), "main must supply all required RTL SHA256 values")
    for name, sha in DEPENDENCIES.items():
        require(result[name] == sha, f"parent dependency pin differs: {name}")
    return result


def verify_rtl(root, pins):
    result = {p: record(root / p) for p in pins}
    for p, sha in pins.items():
        require(result[p]["sha256"] == sha, f"RTL hash mismatch: {p}")
    return result


def verify_completion(stdout, stderr, run_id, complete):
    markers = [line for line in stdout.splitlines() if line.startswith("PRIVATE_DIAG_COMPLETE|")]
    require(markers == ["PRIVATE_DIAG_COMPLETE|" + run_id], "missing/duplicate/mismatched exact completion marker")
    require(complete.get("run_id") == run_id, "run identity mismatch")
    require(not re.search(r"^\s*ERROR:", stdout + "\n" + stderr, re.M), "Vivado ERROR recorded")


def tcl_literal(value):
    # Reject special path characters rather than interpolate executable Tcl.
    text = str(value).replace("\\", "/")
    require(not any(c in text for c in "{}\n\r\x00"), "unsupported Tcl literal")
    return "{" + text + "}"


def verify_authorization(path, map_path, pins):
    a = load_json(path)
    exact = {
        "task_id": TASK, "task_version": 1, "director_thread_id": MAIN,
        "work_id": WORK, "action": "full_private_diag_build",
        "accepted_rtl_sha256": pins[SOURCES[4]],
        "expected_sha_map_sha256": digest(map_path),
        "requirements_sha256": CONTRACT,
    }
    require(isinstance(a, dict), "authorization must be a JSON object")
    require(all(a.get(k) == v for k, v in exact.items()), "separate main build authorization missing/mismatched")
    require(a.get("authorized") is True and a.get("operation_id"), "main operation authorization required")
    return a


def prepare(root, out, pins, map_path, board_dir, tool_root, contract_path):
    require(not out.exists(), f"output already exists; no overwrite/retry: {out}")
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "INTENT.json", {
        "task_id": TASK, "task_version": 1, "work_id": WORK,
        "created_at_utc": utc(), "wrapper_pid": os.getpid(),
        "python": sys.executable, "python_version": platform.python_version(),
        "platform": platform.platform(), "parent_expected_map": record(map_path),
        "source_head_reference": PRODUCT_HEAD, "frozen_design": FROZEN_DESIGN,
        "requirements_sha256": CONTRACT, "requirement_ids": [f"H{i:02}" for i in range(1, 16)],
        "all_29_formal_acceptance": "not_run", "physical_board": "not_run; A-only",
    })
    contract = load_json(contract_path)
    canonical = json.dumps(contract["requirements"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    require(hashlib.sha256(canonical.encode()).hexdigest() == CONTRACT, "fixed human contract mismatch")
    require(contract["contract_id"] == "DEEPEYE-HUMAN-LOCK-20261014" and contract["revision"] == 1, "contract identity mismatch")
    copy_exact(contract_path, out / "inputs/immutable_scope.json")
    copy_exact(map_path, out / "inputs/parent_expected_sha_map.json")
    original = verify_rtl(root, pins)
    snapshots = {p: copy_exact(root / p, out / "inputs/rtl" / p, sha) for p, sha in pins.items()}
    (out / "inputs/rtl_sources.txt").write_text(
        "\n".join((out / "inputs/rtl" / p).as_posix() for p in SOURCES if p in pins) + "\n", encoding="utf-8")
    board_records = {}
    for name, sha in BOARD_HASHES.items():
        board_records[name] = {"original": record(board_dir / name), "snapshot": copy_exact(
            board_dir / name, out / "inputs/board_repo/pynq-z2/A.0" / name, sha)}
    board = ET.parse(board_dir / "board.xml").getroot()
    require(board.attrib["vendor"] == "tul.com.tw" and board.find("./components/component[@name='part0']").attrib["part_name"] == PART, "wrong board identity")
    preset = ET.parse(board_dir / "preset.xml").getroot()
    ps = preset.find("./ip_preset[@preset_proc_name='ps7_preset']/ip[@name='processing_system7']")
    require(ps is not None, "official ps7_preset missing")
    params = {p.attrib["name"]: p.attrib["value"] for p in ps.findall("./user_parameters/user_parameter")}
    require(len(params) == 771, "unexpected preset; main must review board source change")
    ddr = {k: v for k, v in params.items() if k.startswith("CONFIG.PCW_UIPARAM_DDR_") and any(
        n in k for n in ("PARTNO", "MEMORY_TYPE", "BUS_WIDTH", "DRAM_WIDTH", "FREQ_MHZ", "ROW_ADDR_COUNT", "COL_ADDR_COUNT", "BANK_ADDR_COUNT"))}
    require(len(ddr) >= 7, "incomplete DDR provenance")
    (out / "inputs/ddr_expected.tcl").write_text("set expected_ddr [dict create " + " ".join(
        tcl_literal(k) + " " + tcl_literal(v) for k, v in sorted(ddr.items())) + "]\n", encoding="utf-8")
    write_json(out / "inputs/ps7_preset_parameters.json", params)
    installed_ip = {}
    for directory, name, version in (("processing_system7_v5_5", "processing_system7", "5.5"),
                                     ("axi_interconnect_v2_1", "axi_interconnect", "2.1"),
                                     ("proc_sys_reset_v5_0", "proc_sys_reset", "5.0"),
                                     ("xlconstant_v1_1", "xlconstant", "1.1")):
        component = tool_root / "data/ip/xilinx" / directory / "component.xml"
        xml = ET.parse(component).getroot()
        ns = {"s": "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009"}
        identity = ":".join(xml.findtext("s:" + key, namespaces=ns) or "" for key in ("vendor", "library", "name", "version"))
        require(identity == f"xilinx.com:ip:{name}:{version}", "installed component identity mismatch")
        installed_ip[identity] = record(component)
    helper = root.parents[1] / "fpga_mesh/windows_job.py"
    helper_record = copy_exact(helper, out / "inputs/windows_job.py", HELPER_SHA)
    tcl = root / "fpga/diagnostic/build_private_diag.tcl"
    copy_exact(tcl, out / "inputs/build_private_diag.tcl")
    copy_exact(Path(__file__).resolve(), out / "inputs/build_private_diag.py")
    tools = {}
    for relative, sha in TOOL_HASHES.items():
        tools[relative] = record(tool_root / relative)
        require(tools[relative]["sha256"] == sha, f"tool hash mismatch: {relative}")
    summary = {
        "original_rtl": original, "rtl_snapshots": snapshots, "tools": tools,
        "board": board_records, "board_part": "tul.com.tw:pynq-z2:part0:1.0",
        "board_provenance": "Installed XilinxBoardStore 2022.1 TUL/pynq-z2/A.0; exact hashes fixed in wrapper",
        "board_preset_parameter_count": len(params), "ddr_expected": ddr,
        "installed_ip_component_xml": installed_ip,
        "ip_catalog_runtime": "not verified; the single readonly query required an open project and was not repeated",
        "preset_ddr_dqs_to_clk_delay": {k: v for k, v in params.items() if "UIPARAM_DDR_DQS_TO_CLK_DELAY" in k},
        "windows_job": helper_record, "requirements_sha256": CONTRACT,
        "missing_build_inputs": ([] if SOURCES[4] in pins else ["main accepted fifth RTL SHA256"]) + ["separate main build authorization"],
        "preparation": "complete", "synthesis": "not_run", "implementation": "not_run", "bitstream": "not_run", "physical_board": "not_run",
    }
    write_json(out / "PREPARATION.json", summary)
    return summary


class _WinJobAccounting:
    """Query/terminate only the still-open job created for this launch."""

    def __init__(self, job):
        class BasicAccounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_longlong) for name in (
                "TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")]
            _fields_ += [(name, wintypes.DWORD) for name in (
                "TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")]
        self.job, self.info_type = job, BasicAccounting
        self.query_api = job.kernel.QueryInformationJobObject
        self.query_api.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                   wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        self.query_api.restype = wintypes.BOOL
        self.terminate_api = job.kernel.TerminateJobObject
        self.terminate_api.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.terminate_api.restype = wintypes.BOOL

    def query(self):
        require(self.job.handle is not None, "job was closed before terminal observation")
        info, length = self.info_type(), wintypes.DWORD()
        if not self.query_api(self.job.handle, 1, ctypes.byref(info), ctypes.sizeof(info), ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        require(length.value == ctypes.sizeof(info), "incomplete job basic accounting")
        return {"active_processes": int(info.ActiveProcesses), "total_processes": int(info.TotalProcesses),
                "total_terminated_processes": int(info.TotalTerminatedProcesses), "returned_bytes": length.value}

    def terminate(self):
        require(self.job.handle is not None, "job was closed before explicit termination")
        if not self.terminate_api(self.job.handle, 0xE0000054):
            raise ctypes.WinError(ctypes.get_last_error())


def _sample_owned_job(accounting, result, phase):
    event = {"at_utc": utc(), "phase": phase}
    try:
        counts = accounting.query()
        require(counts["active_processes"] >= 0 and counts["total_processes"] >= counts["active_processes"],
                "invalid job accounting counts")
        event.update(counts)
        return counts
    except Exception as exc:
        event["error"] = f"{type(exc).__name__}: {exc}"
        result["job_query_failed"] = True  # Sticky: later zero cannot erase this failure.
        return None
    finally:
        result.setdefault("job_accounting", []).append(event)


def _wait_owned_job_empty(accounting, result, phase, seconds):
    deadline = time.monotonic() + seconds
    while True:
        counts = _sample_owned_job(accounting, result, phase)
        if counts is None:
            return False
        if counts["active_processes"] == 0:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(0.05, remaining))


def _finish_owned_job(accounting, result, reason, drain_seconds, terminate_seconds):
    """Keep the job open through bounded draining and explicit failure cleanup."""
    empty = False
    if reason is None:
        empty = _wait_owned_job_empty(accounting, result, "after_launcher_exit", drain_seconds)
        if not empty:
            reason = "job_accounting_failure" if result.get("job_query_failed") else "descendants_did_not_finish"
    if reason is not None:
        result["owned_job_error"] = reason
        termination = {"attempted": True, "reason": reason, "at_utc": utc(), "exit_code_requested": "0xE0000054"}
        try:
            accounting.terminate()
            termination["api_succeeded"] = True
        except Exception as exc:
            termination.update({"api_succeeded": False, "error": f"{type(exc).__name__}: {exc}"})
            result["job_termination_failed"] = True
        result["job_termination"] = termination
        empty = _wait_owned_job_empty(accounting, result, "after_explicit_termination", terminate_seconds)
    else:
        result["job_termination"] = {"attempted": False, "reason": "natural_job_completion"}
    result["job_empty_observed_before_close"] = empty
    result["job_terminal_confirmed"] = bool(empty and not result.get("job_query_failed")
                                              and not result.get("job_termination_failed"))
    result["job_terminal_state"] = "confirmed" if result["job_terminal_confirmed"] else "unknown"


def require_owned_success(process):
    require(process.get("exit_code") == 0 and process.get("launcher_exit_confirmed") is True
            and process.get("termination_confirmed") is True and process.get("job_terminal_confirmed") is True
            and not process.get("timed_out") and not process.get("process_error")
            and not process.get("owned_job_error") and not process.get("job_close_error"),
            "launcher success and whole owned-job terminal proof are both required")


def run_owned(argv, out, timeout, helper_path, *, job_drain_seconds=5.0, job_terminate_seconds=5.0):
    require(os.name == "nt", "Windows native job containment is required")
    require(digest(helper_path) == HELPER_SHA, "Windows job helper hash mismatch")
    module = types.ModuleType("private_diag_windows_job")
    exec(compile(helper_path.read_bytes(), str(helper_path), "exec"), module.__dict__)
    require(0 < timeout and 0 < job_drain_seconds <= 30 and 0 < job_terminate_seconds <= 30,
            "finite positive process/job wait bounds required")
    work, temp = out / "work", out / "tmp"
    work.mkdir(exist_ok=False)
    temp.mkdir(exist_ok=False)
    (out / "user_data").mkdir(exist_ok=False)
    env = os.environ.copy()
    overrides = {"TEMP": str(temp), "TMP": str(temp), "TMPDIR": str(temp),
                 "XILINX_LOCAL_USER_DATA": str(out / "user_data"), "PYTHONDONTWRITEBYTECODE": "1"}
    env.update(overrides)
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP | CREATE_SUSPENDED
    result = {"argv": argv, "command_line": subprocess.list2cmdline(argv), "cwd": str(work),
              "started_at_utc": utc(), "timeout_seconds": timeout, "creationflags": flags,
              "hidden": True, "shell": False, "wrapper_pid": os.getpid(),
              "environment_overrides": overrides, "terminal": "redirected binary stdout/stderr; no window",
              "helper": record(helper_path), "timed_out": False, "job_attached_before_resume": False,
              "job_drain_seconds": job_drain_seconds, "job_terminate_seconds": job_terminate_seconds,
              "job_terminal_confirmed": False, "job_terminal_state": "unknown"}
    process = job = accounting = None
    reason = None
    start = time.monotonic()
    try:
        with (out / "vivado.stdout.bin").open("xb") as stdout, (out / "vivado.stderr.bin").open("xb") as stderr:
            try:
                job = module.WindowsJob()
                accounting = _WinJobAccounting(job)
                process = subprocess.Popen(argv, cwd=work, env=env, stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, shell=False, creationflags=flags)
                result["original_pid"] = process.pid
                write_json(out / "PROCESS_STARTED.json", result)
                job.attach_and_resume(process)
                result["job_attached_before_resume"] = True
                if _sample_owned_job(accounting, result, "after_attach") is None:
                    reason = "job_accounting_failure"
                else:
                    try:
                        process.wait(timeout=timeout)
                        if process.returncode != 0:
                            reason = "launcher_nonzero_exit"
                    except subprocess.TimeoutExpired:
                        reason = "launcher_timeout"
                        result["timed_out"] = True
                        write_json(out / "TIMEOUT.json", {"at_utc": utc(), "original_pid": process.pid,
                                   "action": "TerminateJobObject on original open job, then observe ActiveProcesses=0"})
            except BaseException as exc:
                reason = "process_error"
                result["process_error"] = f"{type(exc).__name__}: {exc}"
            finally:
                if accounting is not None:
                    _finish_owned_job(accounting, result, reason, job_drain_seconds, job_terminate_seconds)
                if process is not None and process.poll() is None and not result["job_attached_before_resume"]:
                    # Only our original suspended Popen handle; no PID search or unrelated process.
                    result["unattached_launcher_cleanup"] = "terminate original Popen handle; whole-job state remains unknown"
                    process.kill()
                if job is not None:
                    result["job_close_called_at_utc"] = utc()
                    try:
                        job.close()  # Only after all terminal-accounting observations.
                        result["job_closed"] = job.handle is None
                    except Exception as exc:
                        result["job_close_error"] = f"{type(exc).__name__}: {exc}"
                if process is not None:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        result["launcher_wait_unconfirmed"] = True
    finally:
        launcher_exited = process is not None and process.poll() is not None
        result.update({"completed_at_utc": utc(), "elapsed_seconds": time.monotonic() - start,
                       "exit_code": process.poll() if process is not None else None,
                       "launcher_exit_confirmed": launcher_exited,
                       "termination_confirmed": bool(result["job_attached_before_resume"] and launcher_exited
                                                      and result["job_terminal_confirmed"]),
                       "stdout": record(out / "vivado.stdout.bin"),
                       "stderr": record(out / "vivado.stderr.bin")})
        write_json(out / "PROCESS.json", result)
    return result


def verify_hwh(path, mapping):
    xml = ET.parse(path).getroot()
    modules = [m for m in xml.iter("MODULE") if m.get("FULLNAME", "").strip("/") == INSTANCE]
    require(len(modules) == 1 and modules[0].get("VLNV") == VLNV, "HWH private IP identity mismatch")
    ranges = [r for r in xml.iter("MEMRANGE") if r.get("INSTANCE", "").strip("/") == INSTANCE
              and r.get("SLAVEBUSINTERFACE") == "S_AXI"]
    require(len(ranges) == 1, "HWH must expose exactly one private AXI range")
    r = ranges[0]
    base, high = int(r.attrib["BASEVALUE"], 0), int(r.attrib["HIGHVALUE"], 0)
    require(base == int(mapping["base"], 0) and high - base + 1 == 4096 == int(mapping["range"], 0),
            "HWH range differs from actual mapped BD segment")
    return {"instance": INSTANCE, "vlnv": VLNV, "base": hex(base), "range": 4096,
            "source": "same completed run BD mapping and generated HWH; no assumed host base"}


def build(root, out, pins, map_path, authorization, timeout):
    copy_exact(authorization, out / "inputs/main_build_authorization.json")
    # Exact originals AND snapshots are checked again immediately before launch.
    verify_authorization(authorization, map_path, pins)
    verify_rtl(root, pins)
    verify_rtl(out / "inputs/rtl", pins)
    inputs = load_json(out / "PREPARATION.json")
    for r in inputs["tools"].values():
        require(digest(r["path"]) == r["sha256"], "tool changed before launch")
    for r in inputs["board"].values():
        require(digest(r["snapshot"]["path"]) == r["snapshot"]["sha256"], "board snapshot changed")
    tcl = out / "inputs/build_private_diag.tcl"
    config = out / "inputs/build_config.tcl"
    run_id = uuid.uuid4().hex
    config.write_text("\n".join([
        "set run_root " + tcl_literal(out),
        "set run_id " + tcl_literal(run_id),
        "set source_list " + tcl_literal(out / "inputs/rtl_sources.txt"),
        "set board_repo " + tcl_literal(out / "inputs/board_repo"),
    ]) + "\n", encoding="utf-8")
    launcher = inputs["tools"]["bin/vivado.bat"]["path"]
    argv = [r"C:\Windows\System32\cmd.exe", "/d", "/c", launcher,
            "-mode", "batch", "-notrace", "-journal", str(out / "vivado.jou"),
            "-log", str(out / "vivado.log"), "-source", str(tcl), "-tclargs", str(config)]
    # Nothing capable of building runs between these final hash checks and Popen.
    verify_rtl(root, pins)
    verify_rtl(out / "inputs/rtl", pins)
    process = run_owned(argv, out, timeout, out / "inputs/windows_job.py")
    post_error = None
    try:
        verify_rtl(root, pins)
        verify_rtl(out / "inputs/rtl", pins)
    except Exception as exc:
        post_error = str(exc)
    write_json(out / "POST_SOURCE_CHECK.json", {"at_utc": utc(), "matched": post_error is None, "error": post_error})
    require(post_error is None, "source changed during build; artifacts rejected")
    require_owned_success(process)
    stdout = (out / "vivado.stdout.bin").read_bytes().decode("utf-8", "replace")
    stderr = (out / "vivado.stderr.bin").read_bytes().decode("utf-8", "replace")
    complete = load_json(out / "VIVADO_COMPLETE.json")
    verify_completion(stdout, stderr, run_id, complete)
    mapping = load_json(out / "BD_MAPPING.json")
    identity = verify_hwh(out / "artifacts/private_diag.hwh", mapping)
    required = ["artifacts/private_diag.bit", "artifacts/private_diag.hwh", "artifacts/private_diag_routed.dcp",
                "BD_MAPPING.json", "VIVADO_COMPLETE.json", "tool_version.txt", "constraints/private_diag.xdc",
                "reports/route_timing_summary.txt", "reports/route_check_timing.txt", "reports/route_utilization.txt",
                "reports/route_drc.txt", "reports/route_clocks.txt", "reports/route_status.txt"]
    artifacts = {p: record(out / p) for p in required}
    require(all(r["bytes"] > 0 for r in artifacts.values()), "empty build artifact/report")
    manifest = {"status": "completed_build_pending_main_review", "task_id": TASK, "task_version": 1, "work_id": WORK,
                "requirements_sha256": CONTRACT, "requirement_ids": [f"H{i:02}" for i in range(1, 16)],
                "design_commit": FROZEN_DESIGN, "source_head_reference": PRODUCT_HEAD,
                "expected_rtl_sha256": pins, "private_ip": identity, "artifacts": artifacts,
                "process": record(out / "PROCESS.json"), "inputs": record(out / "PREPARATION.json"),
                "files": {str(p.relative_to(out)).replace("\\", "/"): record(p) for p in sorted(out.rglob("*")) if p.is_file()},
                "all_29_formal_acceptance": "not_run", "physical_board": "not_run; A-only",
                "timing_drc_constraints": "reports require quality main review; no product acceptance claimed"}
    write_json(out / "ARTIFACT_MANIFEST.json", manifest)
    return manifest["status"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("prepare", "build"), default="prepare")
    p.add_argument("--product-root", type=Path, default=Path(__file__).resolve().parents[2])
    p.add_argument("--out", type=Path, required=True, help="new directory only")
    p.add_argument("--expected-sha-map", type=Path, required=True, help="parent-supplied map; five exact RTL for build")
    p.add_argument("--authorization", type=Path, help="separate main authorization; mandatory for build")
    p.add_argument("--contract-json", type=Path, required=True)
    p.add_argument("--board-dir", type=Path, default=Path("D:/pynq/AMD2026/2026.1/Vivado/data/boards/board_files/pynq-z2/A.0"))
    p.add_argument("--tool-root", type=Path, default=Path("D:/pynq/AMD2026/2026.1/Vivado"))
    p.add_argument("--timeout-seconds", type=int, default=7200)
    a = p.parse_args(argv)
    require(60 <= a.timeout_seconds <= 14400, "bounded timeout must be 60..14400 seconds")
    root, out = a.product_root.resolve(), a.out.resolve()
    require(root.is_dir(), "product root missing")
    require(out.is_relative_to(root / "evidence/diagnostic"), "output must be a new directory under product evidence/diagnostic")
    require(not out.exists(), "existing output is never reused")
    pins = expected_map(a.expected_sha_map, a.mode == "build")
    if a.mode == "build":
        require(a.authorization is not None, "separate main full-build authorization required")
        verify_authorization(a.authorization, a.expected_sha_map, pins)
    try:
        prepare(root, out, pins, a.expected_sha_map.resolve(), a.board_dir.resolve(), a.tool_root.resolve(), a.contract_json.resolve())
        status = "prepared_only"
        if a.mode == "build":
            status = build(root, out, pins, a.expected_sha_map.resolve(), a.authorization.resolve(), a.timeout_seconds)
        write_json(out / "RESULT.json", {"status": status, "at_utc": utc(), "full_build_executed": a.mode == "build",
                                        "requirements_sha256": CONTRACT, "formal_product_acceptance": "not_run"})
        print(json.dumps({"status": status, "out": str(out), "full_build_executed": a.mode == "build"}))
        return 0
    except BaseException as exc:
        if out.is_dir() and not (out / "FAILURE.json").exists():
            write_json(out / "FAILURE.json", {"at_utc": utc(), "error": f"{type(exc).__name__}: {exc}",
                                            "artifacts_accepted": False, "automatic_retry": False})
        raise


if __name__ == "__main__":
    raise SystemExit(main())
