"""Pinned Win32 whole-job helper copied into new G05 scope; no build CLI/import side effects."""
import ctypes
from ctypes import wintypes
import datetime as dt
import hashlib,json,os,subprocess,time,types
from pathlib import Path
CREATE_SUSPENDED=0x00000004
HELPER_SHA="3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3"
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

def require(test, message):
    if not test:
        raise RuntimeError(message)

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
        with (out / "process.stdout.bin").open("xb") as stdout, (out / "process.stderr.bin").open("xb") as stderr:
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
                       "stdout": record(out / "process.stdout.bin"),
                       "stderr": record(out / "process.stderr.bin")})
        write_json(out / "PROCESS.json", result)
    return result
