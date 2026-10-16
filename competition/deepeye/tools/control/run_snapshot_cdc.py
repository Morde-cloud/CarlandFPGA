#!/usr/bin/env python3
"""Portable fail-closed ModelSim runner for the B snapshot CDC candidate.

Work: B-SNAPSHOT-CDC-CANDIDATE-20261017-06-v1
Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15); requirements
SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
Frozen design 1011259415a0916054eb580687612580bc1e5f09. Public ABI is
A-owned. Candidate fixtures only: no register map, no motion authority, no
synthesis/timing/CDC sign-off and no board result.

Behavior
  - Refuses a pre-existing --out directory BEFORE creating anything.
  - Runs vlib/vlog/vsim with argument arrays (no shell), bounded subprocess
    timeouts, raw stdout/stderr, argv, exit codes and sha256 of tools,
    sources and every transcript.
  - Compiles the candidate RTL and testbench into a fresh 'work' library and
    elaborates the testbench at each requested WIDTH via -gWIDTH.
  - Uses a real .do macro file per run: ModelSim 10.7 ignores onerror/onbreak
    inside inline -do command strings, so a zero process exit alone is not
    trusted; the runner fail-closed checks the exact TB_DONE marker, per-case
    TB_CASE counts, the TB_SUMMARY ledger (accepted == delivered +
    discarded), the absence of '** Error:'/'** Fatal:' in positive
    transcripts, and event-line counts matching the summary counters.
  - Negative controls that MUST fail exactly as expected (a negative control
    that passes fails this runner):
      watchdog hang   -> exit 7, TB_WATCHDOG_TIMEOUT, no TB_DONE
      WIDTH=1025 bounds -> exit 7, bounds messages, no TB_DONE
      WIDTH=0 probe     -> recorded hard elaboration failure, never TB_DONE

Usage
  python run_snapshot_cdc.py --out DIR [--widths 1,32,256,1024]
        [--modelsim-root DIR] [--timeout-seconds N] [--public-evidence DIR]
        [--spec PATH]

Exit codes: 0 = all required runs passed and both negative controls failed as
required; 1 = a required run failed or a negative control misbehaved;
2 = usage or environment error before simulation.
"""

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
WORK_ID = "B-SNAPSHOT-CDC-CANDIDATE-20261017-06-v1"
CONTRACT = {
    "contract": "DEEPEYE-HUMAN-LOCK-20261014",
    "revision": 1,
    "requirements_ids": ["H%02d" % i for i in range(1, 16)],
    "requirements_sha256": "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
    "contract_commit": "f5989cd5defce561f9ba98e6b18fc2682945f0a2",
    "design_commit": "1011259415a0916054eb580687612580bc1e5f09",
}

DEFAULT_WIDTHS = [1, 32, 256, 1024]
REQUIRED_WIDTHS = {1, 32, 256, 1024}
DEFAULT_MODELSIM_ROOT = pathlib.Path("D:/modelsim1/win64")
MAX_TIMEOUT_SECONDS = 60
POSITIVE_RUN_BOUND_NS = 600000
NEGATIVE_HANG_BOUND_NS = 1500000
WATCHDOG_NEG_WIDTH = 32

DIRECTED_CASES = [
    ("startup", 1, 1, 0),
    ("payload_stall", 1, 1, 0),
    ("consecutive", 8, 8, 0),
    ("dst_clock_stop", 2, 2, 0),
    ("src_clock_stop", 3, 3, 0),
    ("held_high_valid_across_reset", 1, 1, 0),
    ("reset_idle", 3, 3, 0),
    ("reset_inflight_request", 2, 1, 1),
    ("reset_valid_pending_stall", 2, 1, 1),
    ("reset_dst_clock_stopped", 2, 1, 1),
    ("reset_src_clock_stopped", 2, 1, 1),
    ("reset_dst_only_stalled", 2, 1, 1),
    ("reset_dst_only_inflight_request", 2, 1, 1),
]
DIRECTED_ACC = sum(case[1] for case in DIRECTED_CASES)
DIRECTED_DEL = sum(case[2] for case in DIRECTED_CASES)
DIRECTED_DISC = sum(case[3] for case in DIRECTED_CASES)

RE_DONE = re.compile(rb"^(?:# )?TB_DONE width=(\d+)\r?$", re.M)
RE_CASE = re.compile(
    rb"^(?:# )?TB_CASE case=(\S+) width=(\d+) accepted=(\d+) delivered=(\d+)"
    rb" discarded=(\d+) errors=(\d+)\r?$",
    re.M,
)
RE_SUMMARY = re.compile(
    rb"^(?:# )?TB_SUMMARY width=(\d+) accepted=(\d+) delivered=(\d+) discarded=(\d+)"
    rb" directed_accepted=(\d+) directed_delivered=(\d+) directed_discarded=(\d+)"
    rb" soak_accepted=(\d+) soak_delivered=(\d+) soak_discarded=(\d+)"
    rb" flush_events=(\d+) src_reset_drops=(\d+) dst_reset_drops=(\d+)"
    rb" tb_errors=(\d+)\r?$",
    re.M,
)
RE_EVT = re.compile(rb"^(?:# )?TB_EVT case=(\S+) width=(\d+) kind=(accept|deliver|flush)\b", re.M)
RE_BOUND = re.compile(rb"^(?:# )?RUNNER_REACHED_BOUND (w\d\S*)\r?$", re.M)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Runner:
    def __init__(self, args):
        self.args = args
        self.out = pathlib.Path(args.out).resolve()
        self.timeout = args.timeout_seconds
        self.widths = args.widths
        self.records = []
        self.checks = []
        self.failures = []

    def check(self, run_name, name, ok, detail=""):
        entry = {"run": run_name, "check": name, "ok": bool(ok), "detail": detail}
        self.checks.append(entry)
        if not ok:
            self.failures.append("%s: %s %s" % (run_name, name, detail))
        return bool(ok)

    def run_command(self, name, argv, cwd):
        argv = [str(part) for part in argv]
        started = time.monotonic()
        timed_out = False
        try:
            proc = subprocess.run(argv, cwd=str(cwd), capture_output=True, timeout=self.timeout)
            code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            code = None
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
        wall = time.monotonic() - started
        (self.out / (name + ".stdout.txt")).write_bytes(stdout)
        (self.out / (name + ".stderr.txt")).write_bytes(stderr)
        record = {
            "name": name,
            "argv": argv,
            "cwd": str(cwd),
            "exit_code": code,
            "timed_out": timed_out,
            "wall_seconds": round(wall, 3),
            "at_utc": utc_now(),
            "stdout_sha256": sha256_bytes(stdout),
            "stderr_sha256": sha256_bytes(stderr),
        }
        (self.out / (name + ".command.json")).write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        self.records.append(record)
        print("[run] %-28s exit=%s timed_out=%s wall=%.2fs" % (name, code, timed_out, wall))
        return record, stdout, stderr

    def write_macro(self, name, body):
        macro = self.out / (name + ".do")
        with macro.open("x", encoding="ascii") as handle:
            handle.write(body)
        return macro

    def positive_checks(self, width, record, stdout, stderr):
        name = record["name"]
        self.check(name, "exit_code_zero", record["exit_code"] == 0,
                   "exit=%r" % (record["exit_code"],))
        self.check(name, "not_timed_out", not record["timed_out"])
        for channel, data in (("stdout", stdout), ("stderr", stderr)):
            self.check(name, channel + "_no_error_marker", b"** Error:" not in data)
            self.check(name, channel + "_no_fatal_marker", b"** Fatal:" not in data)
        marker = RE_BOUND.search(stdout)
        self.check(name, "runner_reached_bound", bool(marker),
                   "marker=%r" % (marker.group(1).decode() if marker else None,))
        done = RE_DONE.findall(stdout)
        self.check(name, "exact_tb_done_marker",
                   len(done) == 1 and int(done[0]) == width, "found=%r" % (done,))
        cases = {}
        for match in RE_CASE.finditer(stdout):
            cases[match.group(1).decode()] = tuple(
                int(match.group(index)) for index in range(2, 7))
        expected_names = [case[0] for case in DIRECTED_CASES] + ["random_soak"]
        self.check(name, "all_cases_reported", sorted(cases) == sorted(expected_names),
                   "reported=%d" % len(cases))
        for cname, exp_acc, exp_del, exp_disc in DIRECTED_CASES:
            seen = cases.get(cname)
            ok = (seen is not None and seen[0] == width and seen[1] == exp_acc
                  and seen[2] == exp_del and seen[3] == exp_disc and seen[4] == 0)
            self.check(name, "case_%s_counts" % cname, ok,
                       "seen=%r expected=(w=%d,acc=%d,del=%d,disc=%d,err=0)"
                       % (seen, width, exp_acc, exp_del, exp_disc))
        soak = cases.get("random_soak")
        self.check(name, "soak_ledger",
                   soak is not None and soak[0] == width and soak[1] == soak[2] + soak[3]
                   and soak[4] == 0, "seen=%r" % (soak,))
        self.check(name, "soak_min_transfers",
                   soak is not None and soak[1] >= 16, "seen=%r" % (soak,))
        summaries = RE_SUMMARY.findall(stdout)
        if not self.check(name, "single_summary", len(summaries) == 1,
                          "found=%d" % len(summaries)):
            return
        (sum_width, acc, dele, disc, dacc, ddel, ddisc, sacc, sdel, sdisc,
         flushes, sdrop, ddrop, terr) = (int(value) for value in summaries[0])
        self.check(name, "summary_width", sum_width == width)
        self.check(name, "summary_ledger", acc == dele + disc,
                   "acc=%d del=%d disc=%d" % (acc, dele, disc))
        self.check(name, "summary_directed_counts",
                   dacc == DIRECTED_ACC and ddel == DIRECTED_DEL and ddisc == DIRECTED_DISC,
                   "directed=(%d,%d,%d) expected=(%d,%d,%d)"
                   % (dacc, ddel, ddisc, DIRECTED_ACC, DIRECTED_DEL, DIRECTED_DISC))
        self.check(name, "summary_soak_chain",
                   dacc + sacc == acc and ddel + sdel == dele and ddisc + sdisc == disc)
        self.check(name, "summary_tb_errors_zero", terr == 0, "tb_errors=%d" % terr)
        self.check(name, "flush_events_min", flushes >= 8, "flush_events=%d" % flushes)
        self.check(name, "src_reset_drops_min", sdrop >= 6, "src_reset_drops=%d" % sdrop)
        self.check(name, "dst_reset_drops_min", ddrop >= 4, "dst_reset_drops=%d" % ddrop)
        events = {"accept": 0, "deliver": 0, "flush": 0}
        for match in RE_EVT.finditer(stdout):
            events[match.group(3).decode()] += 1
        self.check(name, "event_accept_count", events["accept"] == acc,
                   "events=%d summary=%d" % (events["accept"], acc))
        self.check(name, "event_deliver_count", events["deliver"] == dele,
                   "events=%d summary=%d" % (events["deliver"], dele))
        self.check(name, "event_flush_count", events["flush"] == flushes,
                   "events=%d summary=%d" % (events["flush"], flushes))

    def negative_watchdog_checks(self, record, stdout, stderr):
        name = record["name"]
        self.check(name, "negative_exit_7", record["exit_code"] == 7,
                   "exit=%r" % (record["exit_code"],))
        self.check(name, "negative_not_timed_out", not record["timed_out"])
        self.check(name, "negative_hang_armed", b"TB_NEG_HANG_ARMED" in stdout)
        self.check(name, "negative_watchdog_fatal",
                   b"** Fatal: TB_WATCHDOG_TIMEOUT" in stdout)
        self.check(name, "negative_no_tb_done", b"TB_DONE" not in stdout)
        self.check(name, "negative_no_runner_bound", not RE_BOUND.search(stdout))

    def negative_bounds_checks(self, record, stdout, stderr):
        name = record["name"]
        self.check(name, "negative_exit_7", record["exit_code"] == 7,
                   "exit=%r" % (record["exit_code"],))
        self.check(name, "negative_not_timed_out", not record["timed_out"])
        self.check(
            name, "negative_bounds_error",
            b"deepeye_snapshot_mailbox: WIDTH=1025 is outside the legal range 1..1024" in stdout,
        )
        self.check(name, "negative_bounds_fatal", b"WIDTH bounds violation" in stdout)
        self.check(name, "negative_no_guard_fire",
                   b"BOUNDS_NEGATIVE_DID_NOT_FIRE" not in stdout)
        self.check(name, "negative_no_tb_done", b"TB_DONE" not in stdout)
        self.check(name, "negative_no_runner_bound", not RE_BOUND.search(stdout))

    def probe_lower_bound_checks(self, record, stdout, stderr):
        name = record["name"]
        self.check(name, "probe_hard_failure", record["exit_code"] not in (0, None),
                   "exit=%r" % (record["exit_code"],))
        self.check(name, "probe_not_timed_out", not record["timed_out"])
        self.check(name, "probe_tool_error_marker",
                   b"** Error" in stdout or b"** Error" in stderr)
        self.check(name, "probe_no_tb_done", b"TB_DONE" not in stdout)


def collect_public(out, public_arg, result):
    public = pathlib.Path(public_arg).resolve()
    targets = []
    for record in result["run_records"]:
        for suffix in ("stdout.txt", "stderr.txt", "command.json", "do"):
            candidate = out / ("%s.%s" % (record["name"], suffix))
            if candidate.exists():
                targets.append(candidate)
    targets.append(out / "runner-start.json")
    targets.append(out / "runner-result.json")
    extract = out / "events-extract.txt"
    parts = []
    select_tokens = (
        b"TB_EVT ", b"TB_CASE", b"TB_SUMMARY", b"TB_DONE", b"TB_END", b"TB_ERROR",
        b"RUNNER_REACHED_BOUND", b"TB_NEG_HANG_ARMED", b"TB_WATCHDOG_TIMEOUT",
        b"is outside the legal range 1..1024", b"WIDTH bounds violation",
        b"BOUNDS_NEGATIVE_DID_NOT_FIRE",
    )
    for record in result["run_records"]:
        stdout_path = out / ("%s.stdout.txt" % record["name"])
        data = stdout_path.read_bytes() if stdout_path.exists() else b""
        selected = [line for line in data.splitlines()
                    if any(token in line for token in select_tokens)]
        parts.append("=== %s (%d selected lines) ===\n"
                     % (record["name"], len(selected)))
        for line in selected:
            parts.append(line.decode("utf-8", "replace") + "\n")
    extract.write_text("".join(parts), encoding="utf-8")
    targets.append(extract)

    preexisting = [target.name for target in targets if (public / target.name).exists()]
    manifest_path = public / "manifest.json"
    if manifest_path.exists():
        preexisting.append(manifest_path.name)
    if preexisting:
        raise RuntimeError("public evidence targets already exist: %s" % preexisting)
    public.mkdir(parents=True, exist_ok=True)
    manifest = {
        "status": result["status"],
        "work_id": result["work_id"],
        "task_id": result["task_id"],
        "task_version": result["task_version"],
        "copied_at_utc": utc_now(),
        "source_out_dir": str(out),
        "sources": result["sources"],
        "tools": result["tools"],
        "expected": result["expected"],
        "limitations": result["limitations"],
        "files": [],
    }
    for target in targets:
        data = target.read_bytes()
        (public / target.name).write_bytes(data)
        manifest["files"].append(
            {"name": target.name, "bytes": len(data), "sha256": sha256_bytes(data)})
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="fail-closed ModelSim runner for the B snapshot CDC candidate")
    parser.add_argument("--out", required=True,
                        help="fresh output directory; must not exist yet")
    parser.add_argument("--widths", default=",".join(str(w) for w in DEFAULT_WIDTHS))
    parser.add_argument("--modelsim-root", default=str(DEFAULT_MODELSIM_ROOT))
    parser.add_argument("--timeout-seconds", type=int, default=MAX_TIMEOUT_SECONDS)
    parser.add_argument("--public-evidence", default=None)
    parser.add_argument("--spec", default=None)
    parser.add_argument("--rtl", default=None)
    parser.add_argument("--tb", default=None)
    args = parser.parse_args(argv)

    try:
        widths = [int(part) for part in args.widths.split(",") if part.strip()]
    except ValueError:
        print("usage error: --widths must be comma-separated integers", file=sys.stderr)
        return 2
    if not widths or any(width < 1 or width > 1024 for width in widths):
        print("usage error: widths must lie within the legal range 1..1024",
              file=sys.stderr)
        return 2
    missing = sorted(REQUIRED_WIDTHS - set(widths))
    if missing:
        print("usage error: required widths missing: %s" % missing, file=sys.stderr)
        return 2
    if not 1 <= args.timeout_seconds <= MAX_TIMEOUT_SECONDS:
        print("usage error: --timeout-seconds must be within 1..%d"
              % MAX_TIMEOUT_SECONDS, file=sys.stderr)
        return 2

    out = pathlib.Path(args.out).resolve()
    if out.exists():
        print("refusing pre-existing --out directory: %s" % out, file=sys.stderr)
        return 2

    here = pathlib.Path(__file__).resolve()
    deepeye = here.parents[2]
    rtl = pathlib.Path(args.rtl).resolve() if args.rtl else (
        deepeye / "rtl" / "control" / "deepeye_snapshot_mailbox.sv")
    tb = pathlib.Path(args.tb).resolve() if args.tb else (
        deepeye / "tests" / "control" / "rtl" / "tb_snapshot_mailbox.sv")
    root = pathlib.Path(args.modelsim_root)
    tools = {stem: root / (stem + ".exe") for stem in ("vlib", "vlog", "vsim")}

    for label, path in (("rtl", rtl), ("tb", tb)) + tuple(
            (stem, tools[stem]) for stem in tools):
        if not path.is_file():
            print("environment error: missing %s: %s" % (label, path), file=sys.stderr)
            return 2

    spec_info = None
    if args.spec:
        spec_path = pathlib.Path(args.spec).resolve()
        if not spec_path.is_file():
            print("environment error: missing --spec file: %s" % spec_path,
                  file=sys.stderr)
            return 2
        spec_info = {"path": str(spec_path), "sha256": sha256_file(spec_path)}

    runner = Runner(args)
    out.mkdir(parents=True)
    print("fresh output directory: %s" % out)

    tool_hashes = {stem: sha256_file(path) for stem, path in tools.items()}
    source_hashes = {
        "rtl": {"path": str(rtl), "sha256": sha256_file(rtl)},
        "tb": {"path": str(tb), "sha256": sha256_file(tb)},
        "runner": {"path": str(here), "sha256": sha256_file(here)},
    }
    start_record = {
        "task_id": TASK_ID, "task_version": TASK_VERSION, "work_id": WORK_ID,
        "contract": CONTRACT, "at_utc": utc_now(),
        "out_dir": str(out), "out_dir_created_fresh": True,
        "widths": widths, "required_widths": sorted(REQUIRED_WIDTHS),
        "modelsim_root": str(root), "timeout_seconds": runner.timeout,
        "tool_hashes": tool_hashes, "sources": source_hashes, "spec": spec_info,
        "positive_run_bound_ns": POSITIVE_RUN_BOUND_NS,
        "negative_hang_bound_ns": NEGATIVE_HANG_BOUND_NS,
        "tb_watchdog_ns": 1200000,
        "note": "candidate RTL fixtures only; no synthesis/timing/CDC sign-off and no board result",
    }
    (out / "runner-start.json").write_text(
        json.dumps(start_record, indent=2) + "\n", encoding="utf-8")

    version_records = {}
    for stem in ("vlog", "vsim"):
        record, stdout, _ = runner.run_command(
            stem + "-version", [tools[stem], "-version"], out)
        runner.check(stem + "-version", "exit_code_zero",
                     record["exit_code"] == 0, "exit=%r" % (record["exit_code"],))
        version_records[stem] = stdout.decode("utf-8", "replace").strip()

    record, _, _ = runner.run_command("vlib-work", [tools["vlib"], "work"], out)
    runner.check("vlib-work", "exit_code_zero",
                 record["exit_code"] == 0, "exit=%r" % (record["exit_code"],))
    runner.check("vlib-work", "work_library_created", (out / "work").is_dir())

    record, stdout, stderr = runner.run_command(
        "vlog-compile",
        [tools["vlog"], "-sv", "-work", "work", str(rtl), str(tb)], out)
    runner.check("vlog-compile", "exit_code_zero",
                 record["exit_code"] == 0, "exit=%r" % (record["exit_code"],))
    errors_match = re.search(rb"Errors:\s*(\d+)", stdout)
    runner.check("vlog-compile", "zero_compile_errors",
                 errors_match is not None and int(errors_match.group(1)) == 0,
                 "errors=%r" % (errors_match.group(1).decode() if errors_match else None,))
    runner.check("vlog-compile", "no_error_marker",
                 b"** Error" not in stdout and b"** Error" not in stderr)
    runner.check("vlog-compile", "tb_top_listed",
                 b"Top level modules:" in stdout and b"tb_snapshot_mailbox" in stdout)

    for width in widths:
        macro = runner.write_macro(
            "positive_w%d" % width,
            "onerror {quit -force -code 8}\n"
            "onbreak {quit -force -code 7}\n"
            "run %d ns\n" % POSITIVE_RUN_BOUND_NS +
            'puts "RUNNER_REACHED_BOUND w%d"\n' % width +
            "quit -force -code 0\n")
        record, stdout, stderr = runner.run_command(
            "positive_w%d" % width,
            [tools["vsim"], "-c", "-voptargs=+acc", "-onfinish", "stop",
             "-gWIDTH=%d" % width, "work.tb_snapshot_mailbox", "-do", str(macro)], out)
        runner.positive_checks(width, record, stdout, stderr)

    macro = runner.write_macro(
        "negative_watchdog",
        "onerror {quit -force -code 8}\n"
        "onbreak {quit -force -code 7}\n"
        "run %d ns\n" % NEGATIVE_HANG_BOUND_NS +
        'puts "RUNNER_REACHED_BOUND wneg"\n'
        "quit -force -code 0\n")
    record, stdout, stderr = runner.run_command(
        "negative_watchdog",
        [tools["vsim"], "-c", "-voptargs=+acc", "-onfinish", "stop", "+tb_neg_hang",
         "-gWIDTH=%d" % WATCHDOG_NEG_WIDTH, "work.tb_snapshot_mailbox", "-do", str(macro)], out)
    runner.negative_watchdog_checks(record, stdout, stderr)

    macro = runner.write_macro(
        "negative_bounds",
        "onerror {quit -force -code 8}\n"
        "onbreak {quit -force -code 7}\n"
        "run 10000 ns\n"
        'puts "RUNNER_REACHED_BOUND wbounds"\n'
        "quit -force -code 0\n")
    record, stdout, stderr = runner.run_command(
        "negative_bounds",
        [tools["vsim"], "-c", "-voptargs=+acc", "-onfinish", "stop",
         "work.snapshot_mailbox_width_bounds_negative", "-do", str(macro)], out)
    runner.negative_bounds_checks(record, stdout, stderr)

    macro = runner.write_macro(
        "probe_lower_bound_zero",
        "onerror {quit -force -code 8}\n"
        "onbreak {quit -force -code 7}\n"
        "run 10000 ns\n"
        'puts "RUNNER_REACHED_BOUND wprobebounds"\n'
        "quit -force -code 0\n")
    record, stdout, stderr = runner.run_command(
        "probe_lower_bound_zero",
        [tools["vsim"], "-c", "-voptargs=+acc", "-onfinish", "stop",
         "-gBOUNDS_WIDTH=0", "work.snapshot_mailbox_width_bounds_negative",
         "-do", str(macro)], out)
    runner.probe_lower_bound_checks(record, stdout, stderr)

    status = "PASS" if not runner.failures else "FAIL"
    result = {
        "status": status,
        "task_id": TASK_ID, "task_version": TASK_VERSION, "work_id": WORK_ID,
        "contract": CONTRACT, "at_utc": utc_now(),
        "out_dir": str(out), "widths": widths,
        "sources": source_hashes, "spec": spec_info,
        "tools": {"root": str(root), "hashes": tool_hashes,
                  "versions": version_records},
        "expected": {
            "directed_accepted": DIRECTED_ACC,
            "directed_delivered": DIRECTED_DEL,
            "directed_discarded": DIRECTED_DISC,
            "required_widths": sorted(REQUIRED_WIDTHS),
            "soak_min_transfers": 16,
            "positive_run_bound_ns": POSITIVE_RUN_BOUND_NS,
        },
        "run_records": runner.records,
        "checks": runner.checks,
        "failures": runner.failures,
        "negative_controls": {
            "watchdog_hang": "must exit 7 with ** Fatal: TB_WATCHDOG_TIMEOUT and no TB_DONE",
            "width_bounds": "must exit 7 with the WIDTH=1025 bounds messages and no TB_DONE",
            "lower_bound_zero_probe": "recorded hard elaboration failure; never TB_DONE",
        },
        "limitations": [
            "digital RTL fixture only; metastability, analog glitches and reset-pulse width are not modeled",
            "no synthesis, implementation, timing closure, CDC/RDC sign-off, MTBF, B05/R03 or board result",
            "physical integration gate of SNAPSHOT_CDC_CANDIDATE.md (both resets into the shared flush network, delay/skew bounds, reviewed CDC topology) still applies",
            "WIDTH=0 cannot elaborate in portable SystemVerilog (zero-width declarations / zero replication); the upper-bound violation executes the same elaboration guard",
        ],
        "product_simulation": True,
        "synthesis": False,
        "board": False,
    }
    (out / "runner-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print("status=%s checks=%d failures=%d"
          % (status, len(runner.checks), len(runner.failures)))
    for failure in runner.failures:
        print("FAIL: %s" % failure)

    if args.public_evidence:
        try:
            manifest = collect_public(out, args.public_evidence, result)
            print("public evidence: %d files -> %s"
                  % (len(manifest["files"]), args.public_evidence))
        except RuntimeError as exc:
            print("public evidence error: %s" % exc, file=sys.stderr)
            return 1

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
