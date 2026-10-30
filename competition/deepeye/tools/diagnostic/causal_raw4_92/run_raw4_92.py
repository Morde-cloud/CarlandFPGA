"""One fresh B92 fixture-to-UART ModelSim operation with whole-Job evidence.

The production path stays closed. This runner executes the NEW bench against
unchanged existing RTL, the real strict host decoder, and pure adapter controls.
It never calls Root, admission, planner, board, network, Git, Vivado, or a
service. Every native attempt is bounded and preserved.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

ROOT = Path("D:/pynq/CarlandFPGA")
W = ROOT / ".local/worktrees/deepeye-implementation-20261014"
D = W / "competition/deepeye"
P = ROOT / ".local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-74"
EVIDENCE_ROOT = P / "raw4-worker92"
TOOLS = Path("D:/modelsim1/win64")
NEW = D / "tools/diagnostic/causal_raw4_92"
GOLD = D / "golden/diagnostic/causal_raw4_92"
OWNED_PROCESS = D / "tools/diagnostic/g05_capture/build/owned_process.py"
WINDOWS_JOB = W / "fpga_mesh/windows_job.py"
PINS_INPUT = P / "source-inputs/A4dc-raw4-92/PINS.json"
CONTRACT_INPUT = P / "immutable_scope_pinned.json"

TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
WORK_ID = "B-DEEPEYE-CAUSAL-RAW4-CHAIN-TRANSPORT-20261030-82"
THREAD_ID = None
JOB_ID = "child-82010e1d7a2e4f4c9b07d58c84013246"
INSTANCE_ID = "deepseek-b-84"
REQUIREMENTS_SHA256 = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
FREEZE = "1011259415a0916054eb580687612580bc1e5f09"
CONTRACT_PIN = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
SOURCE_COMMIT = "4dc91fd24531b3df53fc916e8b7f509ad524592c"
SOURCE_TREE = "f48acf33ba4a4a81499826c44851663119dcd17b"
OUTPUT_LIMIT = 8 * 1024 * 1024
COMMAND_LIMIT = 25
JOB_LIMIT = 120

COMPILE_RELS = [
    "competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv",
    "competition/deepeye/fpga/acquisition/deepeye_raw_scan_queue.sv",
    "competition/deepeye/fpga/acquisition/deepeye_buffered_scan_capture.sv",
    "competition/deepeye/fpga/acquisition/deepeye_scan_lane_stream.sv",
    "competition/deepeye/fpga/codec/deepeye_block_encoder.sv",
    "competition/deepeye/fpga/codec/deepeye_trace_payload_candidate.sv",
    "competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_payload_1us_candidate.sv",
    "competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_uart_50mhz_candidate.sv",
    "competition/deepeye/fpga/transport/deepeye_crc16_byte.sv",
    "competition/deepeye/fpga/transport/deepeye_wire_serializer.sv",
    "competition/deepeye/fpga/transport/deepeye_uart_tx.sv",
    "competition/deepeye/fpga/diagnostic/offboard_codec74/deepeye_SYNTHETIC_codec74_fixture.sv",
    "competition/deepeye/fpga/diagnostic/causal_raw4_92/tb_CAUSAL_RAW4_92.sv",
]

READONLY_EXPECTED = {
    "competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv": "fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d",
    "competition/deepeye/fpga/acquisition/deepeye_raw_scan_queue.sv": "630e14803d82b3379517d91626de4ad7e7d3c509ad14363b3164031a5f633ee4",
    "competition/deepeye/fpga/acquisition/deepeye_buffered_scan_capture.sv": "c8a540db8122b8f5520582a0f1fa9be0c43cb54a62f03c7c4edc893906f28411",
    "competition/deepeye/fpga/acquisition/deepeye_scan_lane_stream.sv": "b3c9d2024d9325191538cf08fec9a652ff8ff0ae316ec9af96078f85cf5be3cc",
    "competition/deepeye/fpga/codec/deepeye_block_encoder.sv": "4cb79428ef89096742e293516c4696caf985048d8185f531fe92eaa485c8d532",
    "competition/deepeye/fpga/codec/deepeye_trace_payload_candidate.sv": "fb64ace453c451838110c81bf6cb4a815a96fb2668e28a306ff699beca5acef6",
    "competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_payload_1us_candidate.sv": "5ebe65dfe0844aab62365e8664507f153cb75ff47b3c8d4e10f45356e94147a8",
    "competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_uart_50mhz_candidate.sv": "41ea63819c892ec67fe92d6e9338a771d5f93f60d0976e895f18bc97966283d2",
    "competition/deepeye/fpga/transport/deepeye_crc16_byte.sv": "8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f",
    "competition/deepeye/fpga/transport/deepeye_wire_serializer.sv": "efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885",
    "competition/deepeye/fpga/transport/deepeye_uart_tx.sv": "5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47",
    "competition/deepeye/fpga/diagnostic/offboard_codec74/deepeye_SYNTHETIC_codec74_fixture.sv": "409ee484113fa4006eb27e12554a4db57708df5e7dadf269548f546d03931a6a",
    "competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_integration_50mhz_candidate.sv": "957f696429c39fed5c41dc83df88fa78ab2a294a57c1a834ef0f0ef81b7ae2dd",
    "competition/deepeye/golden/codec/trace_candidate.py": "a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642",
    "competition/deepeye/tools/diagnostic/g05_capture/additive50_source_candidate/deepeye_transport50_source_candidate.py": "1f4da870d9c885a3cc6156c30d2170e21001187392a59a19172c059c9ab0c768",
    "competition/deepeye/tools/diagnostic/g05_capture/build/owned_process.py": "1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692",
    "fpga_mesh/windows_job.py": "3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3",
}

SELECTED_RELS = [
    "competition/deepeye/fpga/diagnostic/causal_raw4_92/tb_CAUSAL_RAW4_92.sv",
    "competition/deepeye/tools/diagnostic/causal_raw4_92/raw4_adapter92.py",
    "competition/deepeye/tools/diagnostic/causal_raw4_92/prepare_fixture92.py",
    "competition/deepeye/tools/diagnostic/causal_raw4_92/negative_controls92.py",
    "competition/deepeye/tools/diagnostic/causal_raw4_92/semantic_checks92.py",
    "competition/deepeye/tools/diagnostic/causal_raw4_92/run_raw4_92.py",
    "competition/deepeye/golden/diagnostic/causal_raw4_92/test_raw4_92.py",
    "competition/deepeye/golden/diagnostic/causal_raw4_92/README.md",
]

ADAPTER_CASES = [
    "unknown_key", "bool_int", "nonfinite", "duplicate_json", "gap", "backfill",
    "em_partial", "held_mismatch", "invalid_count", "valid_count_none",
    "sat_invalid", "quality_bit11", "quality_high_bits", "fault_mismatch",
    "c3_early", "too_many", "u63_overflow", "duplicate_record", "invalid_em_hold",
    "source_hash_bad", "counts_tuple",
]

SEMANTIC_CASES = [
    "crc", "partial", "identity", "quality_flags", "time", "u63_overflow",
    "nonwrap", "wrong_index", "relative_overflow", "null_to_zero", "zero_to_null",
    "false_fresh_held", "refreshed_source", "quality_byte", "zero_source",
    "wrong_view", "wrong_e", "cancel_partial",
]

PRE_RUN_REVIEW_CORRECTIONS = [
    "wrong-identity lane expectation corrected from 16'd1000 to the record-6 channel-0 count 16'd1100",
    "mode2 now proves at least one UART byte had already been emitted before cancellation",
    "mode4 added as an intentional fatal runner-negative exit",
    "valid-lane source-age comparison simplified without changing semantics",
    "cancel-partial parsing now consumes only complete prefix frames and cannot lose the first frame",
    "relative_overflow acceptance reason now includes the pinned relative view count/tick refusal",
    "the main 3038-byte wire value is now measured and explained, never used as a pass condition",
    "two NEW test-only assertions were corrected after preserved preflight failures; no production implementation source changed",
]


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def record(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": digest_bytes(raw)}


def write_new_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def require(test, message):
    if not test:
        raise RuntimeError(message)


def output_bytes(out):
    return sum(path.stat().st_size for path in Path(out).rglob("*") if path.is_file())


def source_specs():
    specs = {}
    for rel in list(COMPILE_RELS) + SELECTED_RELS + list(READONLY_EXPECTED):
        path = W / rel
        require(path.is_file(), "required source missing: " + rel)
        specs[rel] = path
    for path in (PINS_INPUT, CONTRACT_INPUT):
        require(path.is_file(), "required pinned input missing: " + str(path))
        specs[path.relative_to(ROOT).as_posix()] = path
    return specs


def record_selected():
    return {rel: record(W / rel) for rel in SELECTED_RELS}


def verify_contract():
    raw = CONTRACT_INPUT.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    ids = [item["id"] for item in value["requirements"]]
    require(ids == ["H%02d" % number for number in range(1, 16)], "pinned H01-H15 IDs changed")
    requirements = canonical(value["requirements"])
    actual = digest_bytes(requirements)
    require(actual == REQUIREMENTS_SHA256, "fixed requirements SHA256 mismatch")
    require(value.get("contract_id") == "DEEPEYE-HUMAN-LOCK-20261014", "contract id mismatch")
    require(value.get("revision") == 1, "contract revision mismatch")
    return {
        "contract_id": value["contract_id"], "revision": value["revision"],
        "requirements_ids": ids, "requirements_sha256": actual,
        "expected_requirements_sha256": REQUIREMENTS_SHA256,
        "canonical_requirements_bytes": len(requirements),
        "pinned_commit": CONTRACT_PIN, "freeze": FREEZE,
        "file": record(CONTRACT_INPUT),
    }


def verify_pins():
    raw = PINS_INPUT.read_bytes()
    entries = json.loads(raw.decode("utf-8"))
    require(type(entries) is list and len(entries) == 12, "pinned input blob count is not 12")
    checked = []
    seen = set()
    for item in entries:
        path = Path(item["local"]).resolve()
        raw_file = path.read_bytes()
        git_blob = hashlib.sha1(b"blob " + str(len(raw_file)).encode("ascii") + b"\0" + raw_file).hexdigest()
        require(item["commit"] == SOURCE_COMMIT, "pinned commit mismatch")
        require(item["bytes"] == len(raw_file), "pinned input bytes mismatch: " + item["path"])
        require(item["sha256"] == digest_bytes(raw_file), "pinned input SHA256 mismatch: " + item["path"])
        require(item["git_oid"] == git_blob, "pinned input Git blob mismatch: " + item["path"])
        require(item["path"] not in seen, "duplicate pinned input path")
        seen.add(item["path"])
        checked.append({"path": item["path"], "bytes": len(raw_file),
                        "sha256": item["sha256"], "git_blob_oid": git_blob})
    return {
        "pins_file": record(PINS_INPUT), "commit": SOURCE_COMMIT,
        "supplied_tree": SOURCE_TREE, "blob_count": len(checked), "blobs": checked,
        "all_12_verified": True,
        "tree_object_note": "supplied A pin; commit/tree objects unavailable locally",
        "actual_A20_privacy_whitelisted_records_received": False,
    }


def verify_readonly():
    rows = {}
    for rel, expected in READONLY_EXPECTED.items():
        row = record(W / rel)
        require(row["sha256"] == expected, "read-only source changed: " + rel)
        row["expected_sha256"] = expected
        row["match"] = True
        rows[rel] = row
    return rows


def tool_pins():
    return {str(TOOLS / (name + ".exe")): record(TOOLS / (name + ".exe"))
            for name in ("vmap", "vlib", "vlog", "vsim")}


def snapshot_source(out, specs):
    snapshot = out / "source"
    rows = {}
    for key, path in specs.items():
        dest = snapshot / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        raw = path.read_bytes()
        dest.write_bytes(raw)
        rows[key] = {"source_path": str(Path(path).resolve()), "snapshot": str(dest.resolve()),
                     "bytes": len(raw), "sha256": digest_bytes(raw)}
    write_new_json(out / "SOURCE_BEFORE.json", rows)
    return rows


def verify_snapshot(specs, pins):
    for key, path in specs.items():
        raw = Path(path).read_bytes()
        require(key in pins, "snapshot key missing: " + key)
        require(len(raw) == pins[key]["bytes"] and digest_bytes(raw) == pins[key]["sha256"],
                "live source differs from pre-run snapshot: " + key)
        snap = Path(pins[key]["snapshot"]).read_bytes()
        require(snap == raw, "snapshot bytes differ from live source: " + key)
    return {key: digest_bytes(Path(path).read_bytes()) for key, path in specs.items()}


def combined_text(commands, name):
    values = []
    for suffix in ("stdout.bin", "stderr.bin"):
        path = commands / (name + "." + suffix)
        values.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(values)


def command(out_root, commands, name, argv, cwd, expected_exit):
    argv = [str(value) for value in argv]
    row = {"argv": argv, "cwd": str(Path(cwd)), "expected_exit": expected_exit,
           "timeout_seconds": COMMAND_LIMIT, "started_utc": utc()}
    started = time.monotonic()
    timed_out = False
    output_exceeded = False
    stdout_path = commands / (name + ".stdout.bin")
    stderr_path = commands / (name + ".stderr.bin")
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=stdout, stderr=stderr, shell=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        row["pid"] = process.pid
        write_new_json(commands / (name + ".STARTED.json"), row)
        while process.poll() is None:
            if time.monotonic() - started >= COMMAND_LIMIT:
                timed_out = True
                process.kill()
            if output_bytes(out_root) >= OUTPUT_LIMIT:
                output_exceeded = True
                process.kill()
            time.sleep(0.02)
        row["exit_code"] = process.poll()
    row.update({"elapsed_seconds": time.monotonic() - started, "ended_utc": utc(),
                "timed_out": timed_out, "output_limit_exceeded": output_exceeded,
                "stdout": record(stdout_path), "stderr": record(stderr_path)})
    write_new_json(commands / (name + ".json"), row)
    require(not timed_out, "native timeout: " + name)
    require(not output_exceeded, "8 MiB attempt output bound: " + name)
    require(row["exit_code"] == expected_exit,
            "native exit %s != %s: %s" % (row["exit_code"], expected_exit, name))
    return row


def read_hex(path):
    return bytes.fromhex("".join(Path(path).read_text(encoding="ascii").split()))


def negative_expectation(stdout_text, case):
    objects = []
    for line in stdout_text.splitlines():
        if line.startswith("{"):
            objects.append(json.loads(line))
    require(objects and objects[-1].get("expected_rejection") == case,
            "negative did not report expected refusal: " + case)
    require("unexpected_rejection" not in stdout_text and "FALSE_ACCEPT" not in stdout_text,
            "negative refusal was not exact: " + case)
    return objects[-1]


def parse_mode(out, mode, expected_frames, expected_exit):
    dest = out / ("mode%d" % mode)
    log_text = (dest / "modelsim.log").read_text(encoding="utf-8", errors="replace")
    events = (dest / "events.txt").read_text(encoding="utf-8", errors="replace")
    uart = read_hex(dest / "uart.hex")
    serial = read_hex(dest / "serializer.hex")
    if mode == 4:
        require(expected_exit == 4 and "B92_INTENTIONAL_RUNNER_NEGATIVE" in log_text,
                "mode4 intentional fatal evidence missing")
        require("B92_SYNTHETIC_DONE" not in log_text, "mode4 unexpectedly completed")
        return {"mode": 4, "exit": expected_exit, "intentional_fatal": True,
                "uart_bytes": len(uart), "serializer_bytes": len(serial),
                "log": record(dest / "modelsim.log"), "events": record(dest / "events.txt")}
    require("B92_SYNTHETIC_DONE mode=%d" % mode in log_text,
            "mode%d exact completion marker missing" % mode)
    require("** Fatal:" not in log_text and "** Error:" not in log_text,
            "mode%d simulator failure marker" % mode)
    require("Errors: 0" in log_text, "mode%d simulator error count nonzero" % mode)
    done = re.findall(r"(?m)^DONE (\d+) (\d+) (\d+) (\d+)$", events)
    require(len(done) == 1, "mode%d DONE count mismatch" % mode)
    cycles, uart_n, serial_n, frames = map(int, done[0])
    require(frames == expected_frames, "mode%d frame count mismatch" % mode)
    require(uart_n == len(uart) and serial_n == len(serial), "mode%d hex byte count mismatch" % mode)
    require(events.count("\nFRAME ") + (1 if events.startswith("FRAME ") else 0) == expected_frames,
            "mode%d FRAME event count mismatch" % mode)
    if mode in (0, 1, 3):
        require(uart == serial, "mode%d UART line differs from serializer bytes" % mode)
    if mode == 2:
        require(uart == serial[:len(uart)], "mode2 UART is not the serializer prefix")
        require("CANCEL_PARTIAL " in events and "NO_REPLAY " in events,
                "mode2 cancel/no-replay evidence missing")
    if mode == 0:
        require(events.count("NULL_FRAME ") == 9, "mode0 null count mismatch")
        require(events.count("ZERO_FRAME ") == 11, "mode0 C3 zero count mismatch")
        require(events.count("HELD_FRAME ") == 48, "mode0 held count mismatch")
    if mode == 1:
        for marker in ("NULL_BACKPRESSURE ", "HELD_BACKPRESSURE ",
                       "ZERO_BACKPRESSURE ", "WRONG_IDENTITY_REFUSED "):
            require(marker in events, "mode1 missing marker: " + marker)
    if mode == 3:
        require("QPC_OVERFLOW_REFUSED" in events and not uart and not serial,
                "mode3 overflow refusal evidence mismatch")
    return {"mode": mode, "exit": expected_exit, "cycles": cycles,
            "uart_bytes": len(uart), "serializer_bytes": len(serial), "frames": frames,
            "uart_equals_serializer": uart == serial,
            "log": record(dest / "modelsim.log"), "events": record(dest / "events.txt"),
            "uart": record(dest / "uart.hex"), "serializer": record(dest / "serializer.hex")}


def prior_evidence(output):
    rows = {}
    output = Path(output).resolve()
    if not EVIDENCE_ROOT.exists():
        return rows
    for path in sorted(EVIDENCE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        resolved = path.resolve()
        try:
            resolved.relative_to(output)
            continue
        except ValueError:
            pass
        rows[resolved.relative_to(EVIDENCE_ROOT.resolve()).as_posix()] = record(resolved)
    return rows


def run_inner(out, phase):
    require(phase == "official", "only the fresh official phase is supported")
    specs = source_specs()
    contract = verify_contract()
    pins = verify_pins()
    readonly = verify_readonly()
    source_before = json.loads((out / "SOURCE_BEFORE.json").read_text(encoding="utf-8"))
    verify_snapshot(specs, source_before)
    sim = out / "sim"
    commands = out / "commands"
    sim.mkdir(exist_ok=False)
    commands.mkdir(exist_ok=False)
    write_new_json(out / "ATTEMPT_STARTED.json", {
        "schema": "B92_ATTEMPT_STARTED_V1", "task_id": TASK_ID, "task_version": TASK_VERSION,
        "work_id": WORK_ID, "job_id": JOB_ID, "instance_id": INSTANCE_ID,
        "started_utc": utc(), "runtime_started": True,
        "contract": contract, "pins": pins, "readonly": readonly,
        "note": "STARTED.json existed before any runtime; this marker precedes native commands",
    })
    rows = []
    stages = []

    rows.append(command(out, commands, "00-pure-tests", [sys.executable, "-B", GOLD / "test_raw4_92.py"], sim, 0))
    tests_text = combined_text(commands, "00-pure-tests")
    match = re.search(r"Ran (\d+) tests", tests_text)
    require(match is not None and int(match.group(1)) >= 9 and re.search(r"(?m)^OK$", tests_text),
            "pure test completion missing")
    stages.append({"stage": "pure_tests", "at_utc": utc(),
                   "tests": int(match.group(1)), "status": "OK"})

    fixture = out / "fixture"
    rows.append(command(out, commands, "01-fixture", [sys.executable, "-B", NEW / "prepare_fixture92.py",
                                                      "--out", fixture], sim, 0))
    projection = fixture / "PROJECTION_COUNTS_ONLY_92.json"
    require(projection.is_file(), "fixture projection missing")
    stages.append({"stage": "fixture", "at_utc": utc(), "projection": record(projection)})

    adapter_rows = []
    for case in ADAPTER_CASES:
        name = "02-adapter-negative-" + case
        row = command(out, commands, name, [sys.executable, "-B", NEW / "negative_controls92.py",
                                            "--case", case], sim, 2)
        expected = negative_expectation((commands / (name + ".stdout.bin")).read_text(
            encoding="utf-8", errors="replace"), case)
        adapter_rows.append({"case": case, "expected_exit": 2, "actual_exit": row["exit_code"],
                             "reason": expected.get("reason"), "stdout": row["stdout"]})
        rows.append(row)
    stages.append({"stage": "adapter_negatives", "at_utc": utc(), "cases": len(adapter_rows)})

    for tool in ("vlog", "vsim", "vmap"):
        rows.append(command(out, commands, "03-" + tool + "-version",
                            [TOOLS / (tool + ".exe"), "-version"], sim, 0))
    rows.append(command(out, commands, "03-vmap", [TOOLS / "vmap.exe", "-c"], sim, 0))
    rows.append(command(out, commands, "03-vlib", [TOOLS / "vlib.exe", "work"], sim, 0))
    rows.append(command(out, commands, "03-compile", [TOOLS / "vlog.exe", "-sv", "-work", "work",
        *[W / rel for rel in COMPILE_RELS]], sim, 0))
    compile_text = combined_text(commands, "03-compile")
    require("Errors: 0" in compile_text and "** Error:" not in compile_text,
            "compile failed after native exit 0")
    stages.append({"stage": "compile", "at_utc": utc(),
                   "stdout": record(commands / "03-compile.stdout.bin"),
                   "stderr": record(commands / "03-compile.stderr.bin")})

    build_manifest = {
        "schema": "B92_BUILD_MANIFEST_V1", "fixture_kind": "MODELLED_SHAPES_FROM_PINNED_PUBLIC_CONTRACTS",
        "compile_sources": {rel: digest_bytes((W / rel).read_bytes()) for rel in COMPILE_RELS},
        "tool_binaries": {name: row["sha256"] for name, row in tool_pins().items()},
        "compile_stdout_sha256": digest_bytes((commands / "03-compile.stdout.bin").read_bytes()),
        "compile_stderr_sha256": digest_bytes((commands / "03-compile.stderr.bin").read_bytes()),
        "note": "digital simulation source/compile manifest; not a bitstream/HWH/physical capture proof",
    }
    build_raw = canonical(build_manifest)
    build_sha = digest_bytes(build_raw)
    (out / "BUILD_MANIFEST.json").write_bytes(canonical(build_manifest) + b"\n")
    (out / "BUILD_MANIFEST.sha256").write_text(build_sha + "\n", encoding="ascii", newline="\n")

    dofile = out / "run.do"
    dofile.write_text(
        "onerror {quit -code 3 -force}\n"
        "onbreak {\n"
        "if {[examine -radix decimal /tb_CAUSAL_RAW4_92/completed] == 1} {quit -code 0 -force}\n"
        "quit -code 4 -force\n"
        "}\n"
        "run -all\n"
        "if {[examine -radix decimal /tb_CAUSAL_RAW4_92/completed] == 1} {quit -code 0 -force}\n"
        "quit -code 4 -force\n", encoding="ascii", newline="\n")

    modes = []
    for mode, frames, expected_exit in ((0, 80, 0), (1, 28, 0), (2, 24, 0),
                                        (3, 0, 0), (4, None, 4)):
        dest = out / ("mode%d" % mode)
        dest.mkdir()
        argv = [TOOLS / "vsim.exe", "-c", "-voptargs=+acc", "-onfinish", "stop",
                "-wlf", dest / "wave.wlf", "-l", dest / "modelsim.log",
                "work.tb_CAUSAL_RAW4_92", "+OUT=" + dest.as_posix(), "+MODE=" + str(mode),
                "-do", "do " + dofile.as_posix()]
        row = command(out, commands, "04-mode%d" % mode, argv, sim, expected_exit)
        rows.append(row)
        modes.append(parse_mode(out, mode, frames, expected_exit))
    stages.append({"stage": "modes", "at_utc": utc(),
                   "summary": [{key: value for key, value in item.items()
                                if key not in ("log", "events", "uart", "serializer")}
                               for item in modes]})

    semantic_out = out / "semantic-positive"
    rows.append(command(out, commands, "05-semantic-positive",
                        [sys.executable, "-B", NEW / "semantic_checks92.py",
                         "--simdir", out, "--projection", projection,
                         "--build-manifest-sha256", build_sha, "--out", semantic_out], sim, 0))
    semantic = json.loads((semantic_out / "SEMANTIC_RESULT.json").read_text(encoding="utf-8"))
    require(semantic["schema"] == "B92_SEMANTIC_POSITIVE_V1", "semantic positive schema")
    require(semantic["frames"] == 80, "semantic positive frame count")
    require(semantic["counts"] == {"invalid_frames": 9, "valid_c3_zero_frames": 11,
                                   "fresh_valid_frames": 23, "held_valid_frames": 48},
            "semantic positive counts")
    require(semantic["uart_equals_serializer"] is True, "semantic UART line mismatch")
    require(semantic["all_invalid_decoded_none"] is True and
            semantic["all_valid_c3_zero_decoded_zero"] is True and
            semantic["all_valid_points_stale"] is True, "semantic null/zero/staleness check")
    require(semantic["source_identity_is_fixture_namespace"] is True, "fixture identity missing")
    require(semantic["cost"]["total_serialized_bytes"] ==
            semantic["cost"]["wire_bytes"] + semantic["cost"]["mandatory_companion_bytes"],
            "complete serialized cost arithmetic")
    stages.append({"stage": "semantic_positive", "at_utc": utc(),
                   "frames": semantic["frames"], "actual_wire_bytes": semantic["actual_wire_bytes"],
                   "companion_bytes": semantic["cost"]["mandatory_companion_bytes"],
                   "total_serialized_bytes": semantic["cost"]["total_serialized_bytes"]})

    semantic_rows = []
    for case in SEMANTIC_CASES:
        name = "06-semantic-negative-" + case
        argv = [sys.executable, "-B", NEW / "semantic_checks92.py",
                "--simdir", out, "--projection", projection,
                "--build-manifest-sha256", build_sha, "--negative", case]
        if case == "cancel_partial":
            argv += ["--partial-dir", out / "mode2"]
        row = command(out, commands, name, argv, sim, 2)
        expected = negative_expectation((commands / (name + ".stdout.bin")).read_text(
            encoding="utf-8", errors="replace"), case)
        semantic_rows.append({"case": case, "expected_exit": 2, "actual_exit": row["exit_code"],
                              "reason": expected.get("reason"), "stdout": row["stdout"]})
        rows.append(row)
    stages.append({"stage": "semantic_negatives", "at_utc": utc(), "cases": len(semantic_rows)})

    verify_snapshot(specs, source_before)
    require(output_bytes(out) < OUTPUT_LIMIT - 131072, "attempt output leaves no RESULT headroom")
    stages.append({"stage": "source_after", "at_utc": utc(), "unchanged": True})
    inner = {
        "schema": "B92_INNER_RESULT_V1", "status": "PASS",
        "task_id": TASK_ID, "task_version": TASK_VERSION, "work_id": WORK_ID,
        "job_id": JOB_ID, "instance_id": INSTANCE_ID, "thread_id": THREAD_ID,
        "contract": contract, "pins": pins, "readonly_modules": readonly,
        "tool_binaries": tool_pins(),
        "build_manifest": record(out / "BUILD_MANIFEST.json"), "build_manifest_sha256": build_sha,
        "stages": stages, "modes": modes, "semantic": semantic,
        "adapter_negatives": adapter_rows, "semantic_negatives": semantic_rows,
        "commands": rows, "command_limit_seconds": COMMAND_LIMIT,
        "job_limit_seconds": JOB_LIMIT, "output_limit_bytes": OUTPUT_LIMIT,
        "no_vlib_version_probe": True, "no_old_suite_replay": True,
        "completed_utc": utc(),
    }
    write_new_json(out / "INNER_RESULT.json", inner)
    print(json.dumps({"status": "PASS", "frames": semantic["frames"],
                      "wire_bytes": semantic["actual_wire_bytes"],
                      "companion_bytes": semantic["cost"]["mandatory_companion_bytes"]},
                     ensure_ascii=False, sort_keys=True))
    return 0


def job_terminal(job):
    return bool(job.get("job_attached_before_resume") is True
                and job.get("launcher_exit_confirmed") is True
                and job.get("job_empty_observed_before_close") is True
                and job.get("job_terminal_confirmed") is True
                and job.get("job_terminal_state") == "confirmed"
                and job.get("job_closed") is True
                and not job.get("timed_out")
                and not job.get("process_error")
                and not job.get("job_query_failed")
                and not job.get("job_termination_failed")
                and not job.get("job_close_error"))


def load_owned_process():
    spec = importlib.util.spec_from_file_location("b92_owned_process", OWNED_PROCESS)
    require(spec is not None and spec.loader is not None, "owned_process loader")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_outer(out, phase):
    require(phase == "official", "only the fresh official phase is supported")
    out.mkdir(parents=True, exist_ok=False)
    specs = source_specs()
    contract = verify_contract()
    pins = verify_pins()
    readonly = verify_readonly()
    pins_before = snapshot_source(out, specs)
    write_new_json(out / "CONTRACT_PIN.json", contract)
    write_new_json(out / "INPUT_PINS.json", pins)
    write_new_json(out / "READONLY_MODULES_BEFORE.json", readonly)
    write_new_json(out / "PRE_RUN_REVIEW_CORRECTIONS.json", {
        "schema": "B92_PRE_RUN_REVIEW_CORRECTIONS_V1",
        "corrections": PRE_RUN_REVIEW_CORRECTIONS,
        "prior_implementation_repairs": "3/3 preserved under raw4-worker92/repairs",
        "official_modelsim_attempts_before_this_run": 0,
    })
    owned = load_owned_process()
    job_dir = out / "owned_job"
    job_dir.mkdir()
    snapshot_runner = Path(pins_before[
        "competition/deepeye/tools/diagnostic/causal_raw4_92/run_raw4_92.py"]["snapshot"])
    snapshot_helper = Path(pins_before["fpga_mesh/windows_job.py"]["snapshot"])
    argv = [str(Path(sys.executable)), "-B", str(snapshot_runner),
            "--phase", "official", "--inner", "--out", str(out)]
    job = owned.run_owned(argv, job_dir, JOB_LIMIT, snapshot_helper,
                          job_drain_seconds=5, job_terminate_seconds=5)
    write_new_json(out / "JOB_RESULT.json", job)
    after = verify_snapshot(specs, pins_before)
    write_new_json(out / "SOURCE_AFTER.json", after)
    readonly_after = verify_readonly()
    require(readonly_after == readonly, "read-only module hash changed across attempt")
    inner_path = out / "INNER_RESULT.json"
    inner = json.loads(inner_path.read_text(encoding="utf-8")) if inner_path.exists() else None
    failure = None
    try:
        owned.require_owned_success(job)
        require(job_terminal(job), "whole owned Job terminal-empty-closed proof missing")
        require(inner is not None and inner.get("status") == "PASS", "inner result did not pass")
        require(all(after[key] == pins_before[key]["sha256"] for key in specs),
                "source changed across measured attempt")
    except Exception:
        failure = traceback.format_exc()
    status = "BOUNDED_FIXTURE_SLICE_PASSED_MAIN_AUDIT_PENDING" if failure is None else "FAILED_PRESERVED"
    selected = record_selected()
    semantic = inner.get("semantic") if inner else None
    adapter_negatives = inner.get("adapter_negatives", []) if inner else []
    semantic_negatives = inner.get("semantic_negatives", []) if inner else []
    evidence = prior_evidence(out)
    result = {
        "schema": "B92_RESULT_V1", "status": status,
        "task_id": TASK_ID, "task_version": TASK_VERSION, "work_id": WORK_ID,
        "thread_id": THREAD_ID, "thread_note": "controller job has no separate App thread id; not invented",
        "job_id": JOB_ID, "instance_id": INSTANCE_ID,
        "phase": phase, "started_utc": job.get("started_at_utc"),
        "completed_utc": utc(), "contract": contract, "pins": pins,
        "source_snapshot_kind": "uncommitted exact file bytes; no later commit claimed tested",
        "source_before": pins_before, "source_after": after,
        "selected_source_files": selected,
        "original_module_readonly_hashes": readonly_after,
        "source_changed_during_attempt": not all(after[key] == pins_before[key]["sha256"] for key in specs),
        "stages": inner.get("stages", []) if inner else [],
        "modes": inner.get("modes", []) if inner else [],
        "semantic_positive": semantic,
        "full_serialized_cost": semantic.get("cost") if semantic else None,
        "actual_wire_bytes": semantic.get("actual_wire_bytes") if semantic else None,
        "reference_wire_bytes": semantic.get("reference_wire_bytes") if semantic else None,
        "wire_delta": semantic.get("wire_delta") if semantic else None,
        "wire_explanation": semantic.get("wire_explanation") if semantic else None,
        "negative_exits": {
            "adapter": adapter_negatives, "semantic_decoder": semantic_negatives,
        },
        "commands": inner.get("commands", []) if inner else [],
        "job": job, "job_terminal_empty_closed": job_terminal(job),
        "inner": inner, "failure": failure,
        "prior_failures_and_repairs": {
            "implementation_repairs_preserved": "raw4-worker92/repairs/repair-01..03; budget 3/3",
            "preflight_pure_test_failures_preserved": "raw4-worker92/preflight-92; two test-only expectation/selector failures before first official ModelSim attempt",
            "pre_run_review_corrections": PRE_RUN_REVIEW_CORRECTIONS,
        },
        "unavailable_gates": {
            "actual_A_privacy_whitelisted_20_records": "NOT_RECEIVED",
            "actual_A_Root": "UNAVAILABLE", "native_em_receipt": "UNAVAILABLE",
            "admission": "UNAVAILABLE", "boot": "UNAVAILABLE",
            "physical_capture": "UNAVAILABLE", "action": "UNAVAILABLE",
            "current_source_eligible": False, "production_default": "CLOSED",
            "board": "NOT_RUN; A only", "synthesis": "NOT_RUN", "implementation": "NOT_RUN",
            "routing": "NOT_RUN", "clock_100mhz": "NOT_ACCEPTED",
            "full_H12": "NOT_PASSED", "all_29": "NOT_PASSED",
            "public_150B_8s_or_compression_ratio": "NOT_ACCEPTED",
        },
        "fixture_label": "MODELLED_SHAPES_FROM_PINNED_PUBLIC_CONTRACTS",
        "acceptance": "bounded fixture slice only; parent and A independent audit required",
    }
    write_new_json(out / "EVIDENCE_MANIFEST.json", evidence)
    evidence_now = {path.relative_to(out).as_posix(): record(path)
                    for path in sorted(out.rglob("*")) if path.is_file()}
    result["evidence_files"] = evidence_now
    result["prior_evidence_files"] = evidence
    require(output_bytes(out) < OUTPUT_LIMIT - 32768, "final evidence exceeds bound before RESULT")
    write_new_json(out / "RESULT.json", result)
    (out / "RESULT.sha256").write_text(record(out / "RESULT.json")["sha256"] + "\n",
                                       encoding="ascii", newline="\n")
    require(output_bytes(out) <= OUTPUT_LIMIT, "final evidence exceeds 8 MiB")
    print(json.dumps({"status": status, "result": str((out / "RESULT.json").resolve()),
                      "job_terminal": job_terminal(job),
                      "failure": failure is not None}, ensure_ascii=False, sort_keys=True))
    return 0 if failure is None else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("official",), default="official")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--inner", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    try:
        if args.inner:
            return run_inner(out, args.phase)
        return run_outer(out, args.phase)
    except Exception:
        error = traceback.format_exc()
        print(error, file=sys.stderr)
        if out.exists() and args.inner and not (out / "INNER_FAILURE.json").exists():
            try:
                write_new_json(out / "INNER_FAILURE.json", {"at_utc": utc(), "error": error})
            except Exception:
                pass
        elif out.exists() and not (out / "RESULT.json").exists():
            try:
                write_new_json(out / "OUTER_FAILURE.json", {"at_utc": utc(), "error": error})
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
