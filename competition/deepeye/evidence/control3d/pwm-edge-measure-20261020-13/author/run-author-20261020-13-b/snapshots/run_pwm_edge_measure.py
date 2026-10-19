#!/usr/bin/env python3
"""Fail-closed local ModelSim runner for deepeye_pwm_edge_measure.

Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Work: B-PWM-EDGE-MEASURE-RTL-20261020-13-v1
Product operation: B-DEEPEYE-PWM-EDGE-MEASURE-20261020-13

This runner is an author-side, bounded digital-simulation evidence generator.
It does not claim synthesis, implementation, CDC/RDC, board, product or main
acceptance. It refuses to overwrite an existing output directory, keeps every
raw stdout/stderr byte and exit code, rejects compiler errors/warnings, missing
TB_PASS/TB_STATS markers and any mismatch in positive runs, requires the four
invalid-parameter time-zero fatal markers, and requires an isolated faulty-copy
mutant to be rejected at public ports. The original accepted RTL bytes are
hashed before and after the mutant run and must remain unchanged.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

OPERATION_ID = "B-DEEPEYE-PWM-EDGE-MEASURE-20261020-13"
WORK_ID = "B-PWM-EDGE-MEASURE-RTL-20261020-13-v1"
TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
CONTRACT_ID = "DEEPEYE-HUMAN-LOCK-20261014"
CONTRACT_REV = 1
REQUIREMENTS_SHA256 = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
CONTRACT_PIN = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
FROZEN_DESIGN = "1011259415a0916054eb580687612580bc1e5f09"
SCOPE_SHA256 = "cc7960d77300fcd46a2b8e6e5e0aca1adafc99842d172934ab77ca8d593b3a90"
SCOPE_FROZEN_SHA256 = "7cef6c82254b97c776ff3e6646f4cc19cecef2c1ed4c660395204cd7a8e8ade5"
DECISION_SHA256 = "1d527d7069a4f5a3041296f709ad58ba913d9066f8b64032acf57b9b58afd283"
CONSUMED_RECEIPT_SHA256 = "21f10e999c585d54441517be2d4f9dcccdbde6f3304493c096abcb511dc0175e"

EXPECTED_RTL_SUFFIX = "competition/deepeye/fpga/control3d/deepeye_pwm_edge_measure.sv"
EXPECTED_TB_SUFFIX = "competition/deepeye/tests/rtl/control3d/tb_pwm_edge_measure.sv"
EXPECTED_OWNED_SUFFIX = "competition/deepeye/evidence/control3d/pwm-edge-measure-20261020-13/author"

MUTATION_OLD = "slot_period_q <= age_q + 1'b1;"
MUTATION_NEW = "slot_period_q <= age_q + 2'd2;"

POSITIVE_CONFIGS = [
    {"name": "w2_t1",  "count_w": 2,  "tag_w": 1,  "smoke": False, "min_cycles": 15000, "min_groups": 14, "min_records": 12,  "min_random": 20000},
    {"name": "w2_t64", "count_w": 2,  "tag_w": 64, "smoke": True,  "min_cycles": 4000,  "min_groups": 13, "min_records": 12,  "min_random": 5000},
    {"name": "w3_t3",  "count_w": 3,  "tag_w": 3,  "smoke": False, "min_cycles": 15000, "min_groups": 14, "min_records": 84,  "min_random": 20000},
    {"name": "w4_t32", "count_w": 4,  "tag_w": 32, "smoke": False, "min_cycles": 18000, "min_groups": 14, "min_records": 420, "min_random": 20000},
    {"name": "w16_t64","count_w": 16, "tag_w": 64, "smoke": False, "min_cycles": 500000,"min_groups": 11, "min_records": 4,   "min_random": 20000},
    {"name": "w32_t1", "count_w": 32, "tag_w": 1,  "smoke": True,  "min_cycles": 5000,  "min_groups": 11, "min_records": 3,   "min_random": 5000},
    {"name": "w32_t64","count_w": 32, "tag_w": 64, "smoke": False, "min_cycles": 350000,"min_groups": 11, "min_records": 4,   "min_random": 20000},
]

INVALID_CONFIGS = [
    {"name": "invalid_w1_t32",  "count_w": 1,  "tag_w": 32},
    {"name": "invalid_w33_t32", "count_w": 33, "tag_w": 32},
    {"name": "invalid_w3_t0",   "count_w": 3,  "tag_w": 0},
    {"name": "invalid_w3_t65",  "count_w": 3,  "tag_w": 65},
]

MUTANT_CONFIG = {"name": "mutant_w3_t3", "count_w": 3, "tag_w": 3, "smoke": True}

ERROR_LINE_PATTERNS = [
    re.compile(r"^\s*#?\s*\*\*\s*Error", re.MULTILINE),
    re.compile(r"^\s*#?\s*\*\*\s*Fatal", re.MULTILINE),
    re.compile(r"^\s*#?\s*\*\*\s*Warning", re.MULTILINE),
    re.compile(r"\bFatal:"),
    re.compile(r"\bErrors:\s*(?!0\b)\d+"),
    re.compile(r"\bWarnings:\s*(?!0\b)\d+"),
]


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_required(path_text, label):
    path = Path(path_text).expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"{label} is not a file: {path}")
    return path


def suffix_ok(path, suffix):
    return path.as_posix().endswith(suffix)
def run_command(argv, cwd, logs_dir, name, timeout=900):
    started = utc_now()
    t0 = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            [str(item) for item in argv],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        rc = proc.returncode
        out = proc.stdout or b""
        err = proc.stderr or b""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        rc = None
        out = exc.stdout or b""
        err = exc.stderr or b""
    duration = round(time.monotonic() - t0, 3)
    stdout_path = logs_dir / f"{name}.stdout.txt"
    stderr_path = logs_dir / f"{name}.stderr.txt"
    stdout_path.write_bytes(out)
    stderr_path.write_bytes(err)
    record = {
        "name": name,
        "argv": [str(item) for item in argv],
        "cwd": str(cwd),
        "started_utc": started,
        "duration_s": duration,
        "timed_out": timed_out,
        "exit_code": rc,
        "stdout": stdout_path.name,
        "stderr": stderr_path.name,
        "stdout_bytes": len(out),
        "stderr_bytes": len(err),
        "stdout_sha256": sha256_bytes(out),
        "stderr_sha256": sha256_bytes(err),
    }
    write_json(logs_dir / f"{name}.command.json", record)
    return record, out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace")


def first_line_matching(text, pattern):
    for line in text.splitlines():
        if pattern.search(line):
            return line
    return ""


def has_error_like(text):
    return any(pattern.search(text) for pattern in ERROR_LINE_PATTERNS)


def parse_tb_stats(text):
    line = first_line_matching(text, re.compile(r"\bTB_STATS\b"))
    if not line:
        return None
    stats = {}
    for key, value in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)=(\d+)", line):
        stats[key] = int(value)
    return stats


def parse_tb_begin(text):
    line = first_line_matching(text, re.compile(r"\bTB_BEGIN\b"))
    if not line:
        return None
    found = {}
    for key in ("COUNT_W", "TAG_W", "SEED", "SMOKE"):
        match = re.search(rf"\b{key}=(\d+)", line)
        if match:
            found[key] = int(match.group(1))
    return found


def parse_fatal_marker(text):
    match = re.search(
        r"PWM_EDGE_UNSUPPORTED_PARAMETERS COUNT_W=(\d+) TAG_W=(\d+)", text
    )
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def check_compile_record(record, stdout, stderr):
    reasons = []
    if record["timed_out"]:
        reasons.append("compile timed out")
    if record["exit_code"] != 0:
        reasons.append(f"compile exit code {record['exit_code']}")
    combined = stdout + "\n" + stderr
    if not re.search(r"Errors:\s*0\b", combined):
        reasons.append("compile did not report Errors: 0")
    if not re.search(r"Warnings:\s*0\b", combined):
        reasons.append("compile did not report Warnings: 0")
    if has_error_like(combined):
        reasons.append("compile output contains an error/fatal pattern")
    return reasons
def parse_positive_run(record, stdout, stderr, cfg):
    reasons = []
    combined = stdout + "\n" + stderr
    if record["timed_out"]:
        reasons.append("simulation timed out")
    if record["exit_code"] != 0:
        reasons.append(f"simulation exit code {record['exit_code']}")
    begin = parse_tb_begin(stdout)
    if begin is None:
        reasons.append("missing TB_BEGIN")
    else:
        if begin.get("COUNT_W") != cfg["count_w"]:
            reasons.append(f"TB_BEGIN COUNT_W={begin.get('COUNT_W')} expected {cfg['count_w']}")
        if begin.get("TAG_W") != cfg["tag_w"]:
            reasons.append(f"TB_BEGIN TAG_W={begin.get('TAG_W')} expected {cfg['tag_w']}")
    if "TB_PASS" not in stdout:
        reasons.append("missing TB_PASS")
    if "TB_FAIL" in stdout:
        reasons.append("TB_FAIL present")
    if "MISMATCH" in stdout:
        reasons.append("MISMATCH present")
    if has_error_like(combined):
        reasons.append("output contains an error/fatal/warning pattern")
    stats = parse_tb_stats(stdout)
    if stats is None:
        reasons.append("missing TB_STATS")
    else:
        if stats.get("mismatches") != 0:
            reasons.append(f"TB_STATS mismatches={stats.get('mismatches')}")
        if stats.get("cycles", 0) < cfg["min_cycles"]:
            reasons.append(f"cycles {stats.get('cycles', 0)} < {cfg['min_cycles']}")
        if stats.get("groups", 0) < cfg["min_groups"]:
            reasons.append(f"groups {stats.get('groups', 0)} < {cfg['min_groups']}")
        if stats.get("records_checked", 0) < cfg["min_records"]:
            reasons.append(f"records_checked {stats.get('records_checked', 0)} < {cfg['min_records']}")
        if stats.get("random_cycles", 0) < cfg["min_random"]:
            reasons.append(f"random_cycles {stats.get('random_cycles', 0)} < {cfg['min_random']}")
        if stats.get("cycle_assertions", 0) < stats.get("cycles", 0) * 10:
            reasons.append("cycle_assertions fewer than 10 per sampled cycle")
    return {
        "name": cfg["name"],
        "count_w": cfg["count_w"],
        "tag_w": cfg["tag_w"],
        "smoke": cfg["smoke"],
        "positive": True,
        "passed": not reasons,
        "reasons": reasons,
        "stats": stats,
        "command": record,
    }


def parse_invalid_run(record, stdout, stderr, cfg):
    reasons = []
    combined = stdout + "\n" + stderr
    marker = parse_fatal_marker(stdout)
    if marker is None:
        reasons.append("missing PWM_EDGE_UNSUPPORTED_PARAMETERS marker")
    elif marker != (cfg["count_w"], cfg["tag_w"]):
        reasons.append(f"guard marker {marker} != expected ({cfg['count_w']}, {cfg['tag_w']})")
    exact_fatal = re.compile(
        rf"^#\s*\*\*\s*Fatal:\s*PWM_EDGE_UNSUPPORTED_PARAMETERS "
        rf"COUNT_W={cfg['count_w']} TAG_W={cfg['tag_w']}\s*$",
        re.MULTILINE,
    )
    exact_matches = exact_fatal.findall(stdout)
    if len(exact_matches) != 1:
        reasons.append(f"expected exactly one exact guard fatal line, found {len(exact_matches)}")
    if not re.search(r"^#\s+Time:\s*0 ps\b", stdout, re.MULTILINE):
        reasons.append("guard fatal was not observed at time 0 ps")
    if not re.search(r"^#\s+Errors:\s*1,\s*Warnings:\s*0\s*$", stdout, re.MULTILINE):
        reasons.append("guard summary is not exactly Errors: 1, Warnings: 0")
    if stderr.strip():
        reasons.append("invalid-parameter run wrote to stderr")
    if "TB_PASS" in stdout:
        reasons.append("invalid-parameter run printed TB_PASS")
    for unexpected_marker in ("TB_BEGIN", "TB_STATS", "TB_FAIL", "MISMATCH"):
        if unexpected_marker in stdout:
            reasons.append(f"invalid-parameter run printed {unexpected_marker}")
    sanitized = exact_fatal.sub("", stdout)
    sanitized = re.sub(
        r"^#\s+Errors:\s*1,\s*Warnings:\s*0\s*$",
        "",
        sanitized,
        flags=re.MULTILINE,
    )
    if has_error_like(sanitized):
        reasons.append("invalid-parameter run contains an unexpected error/fatal/warning pattern")
    if record["timed_out"]:
        reasons.append("guard simulation timed out")
    if record["exit_code"] != 0:
        reasons.append(f"guard simulation exit code {record['exit_code']}")
    return {
        "name": cfg["name"],
        "count_w": cfg["count_w"],
        "tag_w": cfg["tag_w"],
        "positive": False,
        "rejected": not reasons,
        "reasons": reasons,
        "guard_marker": marker,
        "command": record,
    }


def parse_mutant_run(record, stdout, stderr, cfg):
    reasons = []
    combined = stdout + "\n" + stderr
    if record["timed_out"]:
        reasons.append("mutant simulation timed out")
    begin = parse_tb_begin(stdout)
    if begin is None:
        reasons.append("mutant run did not reach TB_BEGIN")
    elif (begin.get("COUNT_W"), begin.get("TAG_W")) != (cfg["count_w"], cfg["tag_w"]):
        reasons.append("mutant TB_BEGIN parameter mismatch")
    if "MISMATCH" not in stdout:
        reasons.append("mutant was not rejected with MISMATCH")
    if "TB_FAIL" not in stdout:
        reasons.append("mutant did not print TB_FAIL")
    if "TB_PASS" in stdout:
        reasons.append("mutant printed TB_PASS")
    return {
        "name": cfg["name"],
        "count_w": cfg["count_w"],
        "tag_w": cfg["tag_w"],
        "rejected": not reasons,
        "reasons": reasons,
        "command": record,
    }
def is_generated_dir(rel_parts):
    for part in rel_parts:
        if part in ("work", "work_mutant"):
            return True
        if part.startswith("scratch-"):
            return True
    return False


def build_manifest(output_dir, snapshots, provenance):
    published = []
    retained = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(output_dir)
        rel_posix = rel.as_posix()
        if rel_posix in ("manifest.json", "SHA256SUMS.txt", "LOCAL_RETENTION.json"):
            continue
        item = {
            "path": rel_posix,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        if is_generated_dir(rel.parts):
            item["reason"] = "local generated ModelSim compiler/scratch artifact; retained, not in published manifest"
            retained.append(item)
        else:
            published.append(item)
    manifest = {
        "schema": 1,
        "operation_id": OPERATION_ID,
        "work_id": WORK_ID,
        "created_utc": utc_now(),
        "snapshots": snapshots,
        "provenance": provenance,
        "files": published,
        "file_count": len(published),
    }
    write_json(output_dir / "manifest.json", manifest)
    lines = [f"{item['sha256']}  {item['path']}" for item in published]
    (output_dir / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(
        output_dir / "LOCAL_RETENTION.json",
        {
            "schema": 1,
            "note": "Generated ModelSim libraries and scratch are retained locally; they are not part of the published manifest.",
            "retained_count": len(retained),
            "retained_files": retained,
        },
    )
    return manifest, retained


def provenance_checks():
    checks = []
    candidates = [
        (
            Path("D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/independent-capture-20261020-13/SCOPE.md"),
            SCOPE_SHA256,
            "normative_scope",
        ),
        (
            Path("D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/independent-capture-20261020-13/SCOPE_FROZEN.json"),
            SCOPE_FROZEN_SHA256,
            "scope_frozen_receipt",
        ),
        (
            Path("D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/main-continuation-20261019-v1/SCOPE_REVIEW_DECISION_20261020_13.json"),
            DECISION_SHA256,
            "coordinator_decision",
        ),
        (
            Path("D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/independent-capture-20261020-13/SCOPE_CONTINUE_CONSUMED.json"),
            CONSUMED_RECEIPT_SHA256,
            "main_scope_continue_readback",
        ),
    ]
    for path, expected, label in candidates:
        if path.is_file():
            actual = sha256_file(path)
            checks.append(
                {
                    "label": label,
                    "path": str(path),
                    "expected_sha256": expected,
                    "actual_sha256": actual,
                    "verified": actual == expected,
                }
            )
        else:
            checks.append(
                {
                    "label": label,
                    "path": str(path),
                    "expected_sha256": expected,
                    "actual_sha256": None,
                    "verified": False,
                    "note": "not present on this machine at run time",
                }
            )
    return checks


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rtl", default=EXPECTED_RTL_SUFFIX)
    parser.add_argument("--testbench", default=EXPECTED_TB_SUFFIX)
    parser.add_argument("--owned-root", default=EXPECTED_OWNED_SUFFIX)
    parser.add_argument("--output", required=True)
    parser.add_argument("--vlib", default="D:/modelsim1/win64/vlib.exe")
    parser.add_argument("--vlog", default="D:/modelsim1/win64/vlog.exe")
    parser.add_argument("--vsim", default="D:/modelsim1/win64/vsim.exe")
    parser.add_argument("--seed", type=int, default=20261020)
    parser.add_argument("--timeout", type=int, default=900)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    rtl = resolve_required(args.rtl, "RTL")
    tb = resolve_required(args.testbench, "testbench")
    owned_root = Path(args.owned_root).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    vlib = resolve_required(args.vlib, "vlib")
    vlog = resolve_required(args.vlog, "vlog")
    vsim = resolve_required(args.vsim, "vsim")

    if not suffix_ok(rtl, EXPECTED_RTL_SUFFIX):
        raise SystemExit(f"refusing RTL path outside the declared product path: {rtl}")
    if not suffix_ok(tb, EXPECTED_TB_SUFFIX):
        raise SystemExit(f"refusing testbench path outside the declared product path: {tb}")
    if not suffix_ok(owned_root, EXPECTED_OWNED_SUFFIX):
        raise SystemExit(f"refusing owned root outside the declared author evidence path: {owned_root}")
    if output == owned_root:
        raise SystemExit("output must be a fresh directory below the owned root")
    try:
        output.relative_to(owned_root)
    except ValueError:
        raise SystemExit(f"output is not below the owned root: {output}")
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {output}")
    for source in (rtl, tb):
        try:
            source.relative_to(output)
        except ValueError:
            pass
        else:
            raise SystemExit(f"input source is inside the output directory: {source}")

    owned_root.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=False, exist_ok=False)
    snapshots_dir = output / "snapshots"
    logs_dir = output / "logs"
    mutant_dir = output / "mutant"
    for directory in (snapshots_dir, logs_dir, mutant_dir):
        directory.mkdir(parents=True, exist_ok=False)

    rtl_hash_before = sha256_file(rtl)
    tb_hash = sha256_file(tb)
    runner_path = Path(__file__).resolve()
    runner_hash = sha256_file(runner_path)
    snapshot_rtl = snapshots_dir / rtl.name
    snapshot_tb = snapshots_dir / tb.name
    snapshot_runner = snapshots_dir / runner_path.name
    shutil.copyfile(rtl, snapshot_rtl)
    shutil.copyfile(tb, snapshot_tb)
    shutil.copyfile(runner_path, snapshot_runner)
    snapshots = {
        "rtl": {"path": snapshot_rtl.name, "source": str(rtl), "sha256": rtl_hash_before},
        "testbench": {"path": snapshot_tb.name, "source": str(tb), "sha256": tb_hash},
        "runner": {"path": snapshot_runner.name, "source": str(runner_path), "sha256": runner_hash},
    }
    provenance = provenance_checks()
    write_json(
        output / "inputs.json",
        {
            "schema": 1,
            "operation_id": OPERATION_ID,
            "work_id": WORK_ID,
            "created_utc": utc_now(),
            "contract": {
                "id": CONTRACT_ID,
                "revision": CONTRACT_REV,
                "requirements_sha256": REQUIREMENTS_SHA256,
                "pinned_commit": CONTRACT_PIN,
                "frozen_design": FROZEN_DESIGN,
                "scope_sha256": SCOPE_SHA256,
                "scope_frozen_sha256": SCOPE_FROZEN_SHA256,
                "coordinator_decision_sha256": DECISION_SHA256,
            },
            "snapshots": snapshots,
            "provenance": provenance,
        },
    )
    commands = []
    tool_records = []
    for name, tool, extra in (
        ("vlog_version", vlog, ["-version"]),
        ("vsim_version", vsim, ["-version"]),
        ("vlib_version", vlib, ["-version"]),
    ):
        record, out, err = run_command([tool] + extra, output, logs_dir, name, timeout=120)
        commands.append(record)
        tool_records.append(
            {
                "name": name,
                "binary": str(tool),
                "binary_sha256": sha256_file(tool),
                "exit_code": record["exit_code"],
                "stdout_first": first_line_matching(out, re.compile(r".*")),
            }
        )

    record, out, err = run_command([vlib, "work"], output, logs_dir, "vlib_work", timeout=args.timeout)
    commands.append(record)
    compile_record, compile_out, compile_err = run_command(
        [vlog, "-sv", "-work", "work", snapshot_rtl, snapshot_tb],
        output,
        logs_dir,
        "vlog_compile",
        timeout=args.timeout,
    )
    commands.append(compile_record)
    compile_reasons = check_compile_record(compile_record, compile_out, compile_err)
    if compile_reasons:
        write_json(
            output / "result.json",
            {
                "schema": 1,
                "operation_id": OPERATION_ID,
                "work_id": WORK_ID,
                "created_utc": utc_now(),
                "status": "failed",
                "stage": "compile",
                "reasons": compile_reasons,
                "commands": commands,
                "snapshots": snapshots,
            },
        )
        build_manifest(output, snapshots, provenance)
        print("FAILED compile: " + "; ".join(compile_reasons), file=sys.stderr)
        return 1

    positive_results = []
    for cfg in POSITIVE_CONFIGS:
        do_name = cfg["name"] + ".do"
        (logs_dir / do_name).write_text(
            "onerror {quit -code 1}\nrun -all\nquit -code 0\n", encoding="ascii"
        )
        runlog_name = cfg["name"] + ".runlog.txt"
        argv = [
            vsim,
            "-c",
            "-onfinish",
            "stop",
            "work.tb_pwm_edge_measure",
            f"-gCOUNT_W={cfg['count_w']}",
            f"-gTAG_W={cfg['tag_w']}",
            f"+SEED={args.seed}",
            f"+SMOKE={1 if cfg['smoke'] else 0}",
            f"+RUNLOG=logs/{runlog_name}",
            "-do",
            f"logs/{do_name}",
        ]
        record, out, err = run_command(argv, output, logs_dir, cfg["name"], timeout=args.timeout)
        commands.append(record)
        positive_results.append(parse_positive_run(record, out, err, cfg))

    invalid_results = []
    for cfg in INVALID_CONFIGS:
        do_name = cfg["name"] + ".do"
        (logs_dir / do_name).write_text(
            "onerror {quit -code 1}\nrun -all\nquit -code 0\n", encoding="ascii"
        )
        argv = [
            vsim,
            "-c",
            "-onfinish",
            "stop",
            "work.tb_pwm_edge_measure",
            f"-gCOUNT_W={cfg['count_w']}",
            f"-gTAG_W={cfg['tag_w']}",
            f"+SEED={args.seed}",
            "-do",
            f"logs/{do_name}",
        ]
        record, out, err = run_command(argv, output, logs_dir, cfg["name"], timeout=args.timeout)
        commands.append(record)
        invalid_results.append(parse_invalid_run(record, out, err, cfg))
    mutant_path = mutant_dir / "deepeye_pwm_edge_measure_mutant.sv"
    original_bytes = snapshot_rtl.read_bytes()
    old_bytes = MUTATION_OLD.encode("ascii")
    new_bytes = MUTATION_NEW.encode("ascii")
    mutation_count = original_bytes.count(old_bytes)
    mutant_ok = mutation_count == 1
    mutant_reasons = []
    if not mutant_ok:
        mutant_reasons.append(f"mutation target count {mutation_count} != 1")
        mutant_bytes = original_bytes
    else:
        mutant_bytes = original_bytes.replace(old_bytes, new_bytes)
    mutant_path.write_bytes(mutant_bytes)
    mutant_hash = sha256_file(mutant_path)
    write_json(
        mutant_dir / "mutation.json",
        {
            "schema": 1,
            "original_rtl_sha256": rtl_hash_before,
            "mutant_rtl_sha256": mutant_hash,
            "replacement_count": mutation_count,
            "old_text": MUTATION_OLD,
            "new_text": MUTATION_NEW,
            "purpose": "isolated off-by-one period mutant; must be rejected by public-port evidence",
        },
    )

    mutant_result = {
        "name": MUTANT_CONFIG["name"],
        "rejected": False,
        "reasons": mutant_reasons,
        "mutation_count": mutation_count,
        "mutant_sha256": mutant_hash,
        "command": None,
    }
    if mutation_count == 1:
        record, out, err = run_command(
            [vlib, "work_mutant"], output, logs_dir, "mutant_vlib", timeout=args.timeout
        )
        commands.append(record)
        mcompile, mout, merr = run_command(
            [vlog, "-sv", "-work", "work_mutant", mutant_path, snapshot_tb],
            output,
            logs_dir,
            "mutant_vlog",
            timeout=args.timeout,
        )
        commands.append(mcompile)
        mutant_compile_reasons = check_compile_record(mcompile, mout, merr)
        if mutant_compile_reasons:
            mutant_reasons.extend("mutant compile: " + item for item in mutant_compile_reasons)
        else:
            do_name = "mutant_w3_t3.do"
            (logs_dir / do_name).write_text(
                "onerror {quit -code 1}\nrun -all\nquit -code 0\n", encoding="ascii"
            )
            argv = [
                vsim,
                "-c",
                "-onfinish",
                "stop",
                "work_mutant.tb_pwm_edge_measure",
                f"-gCOUNT_W={MUTANT_CONFIG['count_w']}",
                f"-gTAG_W={MUTANT_CONFIG['tag_w']}",
                f"+SEED={args.seed}",
                f"+SMOKE={1 if MUTANT_CONFIG['smoke'] else 0}",
                "+RUNLOG=logs/mutant_w3_t3.runlog.txt",
                "-do",
                f"logs/{do_name}",
            ]
            mrecord, mstdout, mstderr = run_command(
                argv, output, logs_dir, MUTANT_CONFIG["name"], timeout=args.timeout
            )
            commands.append(mrecord)
            parsed = parse_mutant_run(mrecord, mstdout, mstderr, MUTANT_CONFIG)
            mutant_result.update(parsed)
            mutant_result["mutation_count"] = mutation_count
            mutant_result["mutant_sha256"] = mutant_hash
    mutant_ok = mutant_result.get("rejected", False) and not mutant_reasons
    mutant_result["rejected"] = mutant_ok
    if mutant_reasons:
        mutant_result["reasons"] = mutant_reasons

    rtl_hash_after = sha256_file(rtl)
    original_unchanged = rtl_hash_after == rtl_hash_before
    if not original_unchanged:
        mutant_ok = False
        mutant_result["reasons"] = list(mutant_result.get("reasons", [])) + [
            "original RTL hash changed during the run"
        ]

    all_positive = all(item["passed"] for item in positive_results)
    all_invalid = all(item["rejected"] for item in invalid_results)
    status = "passed" if (all_positive and all_invalid and mutant_ok and original_unchanged) else "failed"

    totals = {}
    for key in (
        "groups",
        "cases",
        "cycles",
        "cycle_assertions",
        "directed_checks",
        "records_checked",
        "records_generated",
        "handshakes",
        "overflow_events",
        "overrun_events",
        "random_cycles",
    ):
        totals[key] = sum(
            (item.get("stats") or {}).get(key, 0) for item in positive_results
        )

    result = {
        "schema": 1,
        "operation_id": OPERATION_ID,
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "work_id": WORK_ID,
        "kind": "author_local_modelsim_digital_suite",
        "created_utc": utc_now(),
        "status": status,
        "claim": "bounded local digital simulation only; not main acceptance, not product acceptance",
        "contract": {
            "id": CONTRACT_ID,
            "revision": CONTRACT_REV,
            "requirements_sha256": REQUIREMENTS_SHA256,
            "pinned_commit": CONTRACT_PIN,
            "frozen_design": FROZEN_DESIGN,
            "scope_sha256": SCOPE_SHA256,
            "scope_frozen_sha256": SCOPE_FROZEN_SHA256,
            "coordinator_decision_sha256": DECISION_SHA256,
        },
        "provenance": provenance,
        "snapshots": snapshots,
        "tools": {
            "records": tool_records,
            "vlog_binary_sha256": sha256_file(vlog),
            "vsim_binary_sha256": sha256_file(vsim),
            "vlib_binary_sha256": sha256_file(vlib),
        },
        "seed": args.seed,
        "positive_runs": positive_results,
        "invalid_parameter_runs": invalid_results,
        "mutant": mutant_result,
        "original_rtl_unchanged": original_unchanged,
        "original_rtl_sha256_before": rtl_hash_before,
        "original_rtl_sha256_after": rtl_hash_after,
        "totals": totals,
        "limitations": {
            "synthesis": "not_run_no_vivado_invoked_by_this_suite",
            "implementation": "not_run",
            "cdc_rdc": "not_run",
            "board": "not_run_A_only",
            "count_w32_max_period_observed": False,
            "count_w32_overflow_observed": False,
            "three_channel_same_period_capture": "not_supplied",
            "freshness_liveness_ttl": "not_supplied",
            "motion_authority": "not_supplied",
            "formal_cards": "29 not_run",
            "main_independent_acceptance": "pending",
            "product_acceptance": "not_claimed",
        },
        "commands": commands,
    }
    write_json(output / "result.json", result)
    manifest, retained = build_manifest(output, snapshots, provenance)

    print(
        "RESULT status=%s positive=%d/%d invalid=%d/%d mutant=%s totals=%s"
        % (
            status,
            sum(1 for item in positive_results if item["passed"]),
            len(positive_results),
            sum(1 for item in invalid_results if item["rejected"]),
            len(invalid_results),
            "rejected" if mutant_ok else "NOT_REJECTED",
            json.dumps(totals, sort_keys=True),
        )
    )
    print(f"OUTPUT {output}")
    print(f"MANIFEST {output / 'manifest.json'} files={manifest['file_count']} retained={len(retained)}")
    if status != "passed":
        for item in positive_results:
            if not item["passed"]:
                print(f"POSITIVE_FAIL {item['name']}: {item['reasons']}", file=sys.stderr)
        for item in invalid_results:
            if not item["rejected"]:
                print(f"INVALID_FAIL {item['name']}: {item['reasons']}", file=sys.stderr)
        if not mutant_ok:
            print(f"MUTANT_FAIL: {mutant_result.get('reasons')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
