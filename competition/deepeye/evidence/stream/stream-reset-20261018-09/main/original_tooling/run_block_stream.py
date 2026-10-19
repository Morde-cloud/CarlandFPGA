#!/usr/bin/env python3
"""Fail-closed ModelSim runner for the two-slot stream/reset candidate.

Work: B-STREAM-RESET-INTEGRATION-20261018-09-v1
Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Operation: B-DEEPEYE-STREAM-RESET-20261018-09
Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
Frozen design: 1011259415a0916054eb580687612580bc1e5f09.

This runner requires explicit core, wrapper, testbench, golden, spec, tool and
output paths.  It refuses a pre-existing output, aliased inputs, or an output
outside the caller-designated owned root.  Inputs are copied to a flat export
directory so paths containing spaces are exercised through argument arrays.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
WORK_ID = "B-STREAM-RESET-INTEGRATION-20261018-09-v1"
OPERATION_ID = "B-DEEPEYE-STREAM-RESET-20261018-09"
CONTRACT = {
    "contract": "DEEPEYE-HUMAN-LOCK-20261014",
    "revision": 1,
    "requirements_ids": ["H%02d" % i for i in range(1, 16)],
    "requirements_sha256": "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
    "contract_commit": "f5989cd5defce561f9ba98e6b18fc2682945f0a2",
    "design_commit": "1011259415a0916054eb580687612580bc1e5f09",
    "encoder_commit": "1c8ce8433b2adf5b50947b124f7397c603f7a978",
}
PINNED_CORE_SHA256 = "870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5"
PINNED_GOLDEN_SHA256 = "2e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5"
MAX_VECTORS = 64
MAX_SAMPLES = 128
MAX_BYTES = 256

COVER_MIN = {
    "all_e": 5,
    "raw": 1,
    "rice": 1,
    "n1": 1,
    "n128": 1,
    "concurrent_fill": 1,
    "fill_during_emit": 1,
    "queuefull_cycles": 4096,
    "meta_stall_cycles": 1000,
    "byte_stall_cycles": 1500,
    "backtoback_blocks": 12,
    "cfg_notready": 4096,
    "sample_notready": 1,
    "invalid_cfg": 1,
    "early_last": 1,
    "missing_last": 1,
    "partial_reset": 1,
    "partial_cancel": 1,
    "corefeed_cancel": 1,
    "meta_reset": 1,
    "meta_cancel": 1,
    "firstbyte_cancel": 1,
    "midbyte_cancel": 1,
    "finalbyte_cancel": 1,
    "heldcancel": 1,
    "alloc_retire": 1,
    "reset_recovery": 1,
    "cancel_recovery": 1,
    "pointer_wrap": 1,
    "saturation": 5,
    "random_schedule_cycles": 1024,
    "random_ready_stalls": 16,
    "random_valid_gaps": 100,
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def within(child, parent):
    child_s = os.path.normcase(os.path.realpath(str(child)))
    parent_s = os.path.normcase(os.path.realpath(str(parent)))
    try:
        return os.path.commonpath([child_s, parent_s]) == parent_s
    except ValueError:
        return False


def command_text(command):
    return subprocess.list2cmdline([str(item) for item in command])


def load_golden(path):
    spec = importlib.util.spec_from_file_location("deepeye_codec_golden_pinned", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import pinned golden reference")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_vector(cases, golden, label, samples, e):
    values = golden.check_samples(list(samples))
    e = golden.check_e(e)
    fixture = golden.encode_block(values, e)
    golden.decode_block(fixture)
    payload = bytes.fromhex(fixture["payload_hex"])
    expected_bytes = (fixture["valid_bit_count"] + 7) // 8
    if len(payload) != expected_bytes or len(payload) > MAX_BYTES:
        raise RuntimeError("golden payload accounting failed for %s" % label)
    if fixture["mode"] == "raw":
        raw = 1
        k = 0
    elif fixture["mode"] == "rice":
        raw = 0
        k = fixture["k"]
    else:
        raise RuntimeError("unexpected golden mode")
    if len(cases) >= MAX_VECTORS:
        raise RuntimeError("vector limit exceeded")
    cases.append({
        "label": label,
        "samples": values,
        "e": e,
        "raw": raw,
        "k": k,
        "bits": fixture["valid_bit_count"],
        "bytes": payload,
        "tag": 0x2000 + len(cases),
    })


def build_vectors(golden):
    cases = []
    for e in (0, 1, 2, 4, 8):
        add_vector(cases, golden, "n1-e%d" % e, [0x1234], e)
    up_step = [0, 65535]
    for e in (0, 1, 2, 4, 8):
        add_vector(cases, golden, "n2-step-e%d" % e, up_step, e)
    small = [0, 1, 2]
    for e in (0, 1, 2, 4, 8):
        add_vector(cases, golden, "n3-small-e%d" % e, small, e)
    top = [65535, 65534, 0, 65535]
    for e in (0, 1, 2, 4, 8):
        add_vector(cases, golden, "n4-top-e%d" % e, top, e)
    noisy16 = [1068, 65528, 42497, 37688, 5490, 34448, 60879, 53428,
               60039, 40003, 51841, 22441, 21125, 63485, 1683, 9955]
    for e in (0, 1, 2, 4, 8):
        add_vector(cases, golden, "n16-noisy-e%d" % e, noisy16, e)
    for e in (0, 1, 2, 4, 8):
        add_vector(cases, golden,
                   "n128-constant-e%d" % e,
                   [1000 + ((e * 37 + i * 3) & 0x1FFF) for i in range(128)], e)
    add_vector(cases, golden, "n128-saw-e0",
               [((i * 523) + (i * i * 17)) & 0xFFFF for i in range(128)], 0)
    add_vector(cases, golden, "n128-alternating-e0",
               [0 if (i & 1) else 65535 for i in range(128)], 0)
    state = 0x5A17
    pseudo = []
    for _ in range(128):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        pseudo.append((state >> 8) & 0xFFFF)
    add_vector(cases, golden, "n128-lcg-e0", pseudo, 0)
    add_vector(cases, golden, "n128-lcg-e8", pseudo, 8)
    add_vector(cases, golden, "n64-lcg-e1",
               pseudo[0:64], 1)
    if len(cases) > MAX_VECTORS:
        raise RuntimeError("too many vectors")
    if not any(item["raw"] == 1 for item in cases):
        raise RuntimeError("vector set has no RAW case")
    if not any(item["raw"] == 0 for item in cases):
        raise RuntimeError("vector set has no Rice case")
    if not any(len(item["samples"]) == 128 for item in cases):
        raise RuntimeError("vector set has no N128 case")
    return cases


def write_vectors(path, cases):
    with open(path, "w", encoding="ascii", newline="\n") as handle:
        handle.write("%d\n" % len(cases))
        for index, item in enumerate(cases):
            handle.write("%d %d %d %d %d %d %d %d\n" % (
                index, len(item["samples"]), item["e"], item["raw"], item["k"],
                item["bits"], len(item["bytes"]), item["tag"]))
            handle.write(" ".join(str(value) for value in item["samples"]) + "\n")
            handle.write(" ".join(str(value) for value in item["bytes"]) + "\n")


def run_tool(name, command, cwd, output, timeout):
    started = time.monotonic()
    try:
        process = subprocess.run(
            [str(item) for item in command],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        timed_out = False
        stdout = process.stdout
        stderr = process.stderr
        exit_code = process.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout = (error.stdout or "") if isinstance(error.stdout, str) else ""
        stderr = (error.stderr or "") if isinstance(error.stderr, str) else ""
        exit_code = None
    elapsed = time.monotonic() - started
    stdout_path = output / (name + ".stdout.log")
    stderr_path = output / (name + ".stderr.log")
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    record = {
        "name": name,
        "command": [str(item) for item in command],
        "command_line": command_text(command),
        "cwd": str(cwd),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "elapsed_seconds": round(elapsed, 3),
        "stdout": stdout_path.name,
        "stderr": stderr_path.name,
    }
    return record, stdout, stderr


def parse_transcript(text):
    summary = None
    match = re.search(
        r"TB_SUMMARY cases=(\d+) pass=(\d+) fail=(\d+) checks=(\d+) "
        r"cfg_hs=(\d+) sample_hs=(\d+) meta_hs=(\d+) data_hs=(\d+) "
        r"ok=(\d+) error=(\d+) whitebox=(\d+)", text)
    if match:
        names = ("cases", "pass", "fail", "checks", "cfg_hs", "sample_hs",
                 "meta_hs", "data_hs", "ok", "error", "whitebox")
        summary = {name: int(value) for name, value in zip(names, match.groups())}
    coverage = {}
    for match in re.finditer(r"^\s*(?:#\s*)?TB_COVER ([A-Za-z0-9_]+)=(\d+)\s*$",
                             text, re.MULTILINE):
        coverage[match.group(1)] = int(match.group(2))
    return summary, coverage


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True)
    parser.add_argument("--wrapper", required=True)
    parser.add_argument("--tb", required=True)
    parser.add_argument("--golden", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--owned-root", required=True)
    parser.add_argument("--vlib", required=True)
    parser.add_argument("--vlog", required=True)
    parser.add_argument("--vsim", required=True)
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args(argv)

    core = Path(args.core).resolve()
    wrapper = Path(args.wrapper).resolve()
    tb = Path(args.tb).resolve()
    golden = Path(args.golden).resolve()
    spec = Path(args.spec).resolve()
    output = Path(args.output).resolve()
    owned_root = Path(args.owned_root).resolve()
    vlib = Path(args.vlib).resolve()
    vlog = Path(args.vlog).resolve()
    vsim = Path(args.vsim).resolve()
    inputs = [core, wrapper, tb, golden, spec]

    for tool in (vlib, vlog, vsim):
        if not tool.is_file():
            print("ERROR missing tool: %s" % tool, file=sys.stderr)
            return 2
    for source in inputs:
        if not source.is_file():
            print("ERROR missing input: %s" % source, file=sys.stderr)
            return 2
    if output.exists():
        print("ERROR output already exists: %s" % output, file=sys.stderr)
        return 2
    if not within(output, owned_root):
        print("ERROR output outside owned root", file=sys.stderr)
        return 2
    if not output.parent.is_dir():
        print("ERROR output parent does not exist", file=sys.stderr)
        return 2
    resolved_inputs = [str(path) for path in inputs]
    if len(set(resolved_inputs)) != len(resolved_inputs):
        print("ERROR aliased input paths", file=sys.stderr)
        return 2
    for source in inputs:
        if within(output, source.parent) and output == source:
            print("ERROR output aliases input", file=sys.stderr)
            return 2
        if source == output or within(source, output):
            print("ERROR input inside output", file=sys.stderr)
            return 2

    core_hash = sha256_file(core)
    golden_hash = sha256_file(golden)
    if core_hash != PINNED_CORE_SHA256:
        print("ERROR core SHA256 mismatch", file=sys.stderr)
        return 2
    if golden_hash != PINNED_GOLDEN_SHA256:
        print("ERROR golden SHA256 mismatch", file=sys.stderr)
        return 2

    output.mkdir()
    export = output / "export"
    work = output / "work"
    export.mkdir()
    work.mkdir()
    names = {
        "core": core.name,
        "wrapper": wrapper.name,
        "tb": tb.name,
        "golden": golden.name,
        "spec": spec.name,
    }
    for key, source in (("core", core), ("wrapper", wrapper), ("tb", tb),
                        ("golden", golden), ("spec", spec)):
        shutil.copy2(source, export / names[key])
    copied_hashes = {key: sha256_file(export / name) for key, name in names.items()}
    if copied_hashes["core"] != PINNED_CORE_SHA256:
        raise RuntimeError("copied core hash changed")
    if copied_hashes["golden"] != PINNED_GOLDEN_SHA256:
        raise RuntimeError("copied golden hash changed")

    golden_module = load_golden(export / names["golden"])
    cases = build_vectors(golden_module)
    vector_path = export / "stimulus.vec"
    write_vectors(vector_path, cases)
    shutil.copy2(vector_path, output / "stimulus.vec")
    (output / "vector_manifest.json").write_text(
        json.dumps({
            "count": len(cases),
            "e_values": sorted(set(item["e"] for item in cases)),
            "raw_cases": sum(1 for item in cases if item["raw"]),
            "rice_cases": sum(1 for item in cases if not item["raw"]),
            "n1_cases": sum(1 for item in cases if len(item["samples"]) == 1),
            "n128_cases": sum(1 for item in cases if len(item["samples"]) == 128),
            "max_bytes": max(len(item["bytes"]) for item in cases),
            "labels": [item["label"] for item in cases],
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    do_path = output / "run.do"
    do_path.write_text(
        "onerror {quit -code 3}\n"
        "onbreak {quit -code 4}\n"
        "run -all\n"
        "quit -code 0\n",
        encoding="ascii")

    records = []
    version_record, version_out, version_err = run_tool(
        "version", [vsim, "-version"], output, output, min(args.timeout, 120))
    records.append(version_record)
    (output / "modelsim_version.txt").write_text(
        version_out + version_err, encoding="utf-8")

    commands = [
        ("vlib", [vlib, "work"]),
        ("vlog", [vlog, "-sv", "-work", "work", str(export / names["core"]),
                  str(export / names["wrapper"]), str(export / names["tb"])]),
        ("vsim", [vsim, "-c", "-do", str(do_path), "-l", str(output / "vsim.log"),
                  "tb_block_stream"]),
    ]
    failure = None
    try:
        for name, command in commands:
            record, stdout, stderr = run_tool(
                name, command, output, output, args.timeout)
            records.append(record)
            if record["timed_out"]:
                raise RuntimeError("%s timed out" % name)
            if record["exit_code"] != 0:
                raise RuntimeError("%s exit %s" % (name, record["exit_code"]))

        transcript_parts = []
        for filename in ("vsim.log", "vsim.stdout.log", "vsim.stderr.log"):
            path = output / filename
            if path.is_file():
                transcript_parts.append(path.read_text(encoding="utf-8", errors="replace"))
        transcript = "\n".join(transcript_parts)
        (output / "vsim.combined.log").write_text(transcript, encoding="utf-8")
        summary, coverage = parse_transcript(transcript)
        if "TB_DONE" not in transcript:
            failure = "missing TB_DONE"
        elif "TB_END pass" not in transcript:
            failure = "missing TB_END pass"
        elif re.search(r"TB_CHECK_FAIL|TB_END fail|TB_FAIL|TB_WATCHDOG_TIMEOUT|"
                       r"\*\* Error:|Fatal:", transcript,
                       re.IGNORECASE):
            failure = "negative diagnostic marker"
        elif summary is None:
            failure = "missing or malformed TB_SUMMARY"
        elif summary["fail"] != 0 or summary["pass"] != summary["cases"]:
            failure = "reported failing cases"
        elif summary["cases"] < 20 or summary["checks"] < 10000:
            failure = "insufficient case/check count"
        elif summary["whitebox"] < 5:
            failure = "insufficient whitebox boundary checks"
        elif "TB_WHITEBOX_BEGIN" not in transcript or "TB_WHITEBOX_END" not in transcript:
            failure = "whitebox section not explicitly separated"
        else:
            missing = [name for name in COVER_MIN if name not in coverage]
            low = [name for name, minimum in COVER_MIN.items()
                   if coverage.get(name, -1) < minimum]
            if missing:
                failure = "missing coverage markers: %s" % ",".join(missing)
            elif low:
                failure = "coverage below minimum: %s" % ",".join(low)
    except Exception as error:
        failure = str(error)

    status = "PASS" if failure is None else "FAIL"
    source_hashes = {
        "core": copied_hashes["core"],
        "wrapper": copied_hashes["wrapper"],
        "tb": copied_hashes["tb"],
        "golden": copied_hashes["golden"],
        "spec": copied_hashes["spec"],
        "runner": sha256_file(Path(__file__).resolve()),
    }
    summary_data = {
        "status": status,
        "failure": failure,
        "task_id": TASK_ID, "task_version": TASK_VERSION,
        "work_id": WORK_ID, "operation_id": OPERATION_ID,
        "contract": CONTRACT,
        "at_utc": utc_now(),
        "output": str(output),
        "source_hashes": source_hashes,
        "vector_count": len(cases),
        "summary": (parse_transcript((output / "vsim.combined.log").read_text(
            encoding="utf-8", errors="replace"))[0]
                    if (output / "vsim.combined.log").is_file() else None),
        "coverage": (parse_transcript((output / "vsim.combined.log").read_text(
            encoding="utf-8", errors="replace"))[1]
                     if (output / "vsim.combined.log").is_file() else {}),
        "commands": records,
        "limitations": [
            "simulation only; no synthesis, implementation, timing, resource, board or system result",
            "internal two-slot candidate only; not TRACE, a public ABI/register map, BOOT/tick source or motion authority",
            "reset/cancel are synchronous and external consumers must discard partially consumed frames",
            "counter boundary checks use whitebox hierarchical deposits and are not blackbox stream evidence",
        ],
    }
    (output / "run_summary.json").write_text(
        json.dumps(summary_data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    (output / "tool_runs.json").write_text(
        json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    publish = []
    for path in sorted(output.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(output).as_posix()
        if relative.startswith("work/") or path.suffix.lower() in (".wlf", ".vst"):
            continue
        if path.name in ("SHA256SUMS.txt", "publish_manifest.json"):
            continue
        publish.append({"path": relative, "sha256": sha256_file(path)})
    (output / "publish_manifest.json").write_text(
        json.dumps({"note": "main should curate this local list before publication",
                    "files": publish}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    (output / "SHA256SUMS.txt").write_text(
        "\n".join("%s  %s" % (item["sha256"], item["path"]) for item in publish) + "\n",
        encoding="ascii")

    print("status=%s cases=%s checks=%s failure=%s"
          % (status,
             summary_data["summary"]["cases"] if summary_data["summary"] else "?",
             summary_data["summary"]["checks"] if summary_data["summary"] else "?",
             failure if failure else "none"))
    print("summary=%s" % (output / "run_summary.json"))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
