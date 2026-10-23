#!/usr/bin/env python3
"""Bounded ModelSim author fixture; no design or product acceptance authority.

Reuses the pinned published codec reference, never the main's oracle. All new
files (including vendor tool scratch files) are confined to the owned author
directory. Each invocation reserves a fresh numbered attempt and preserves it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import types
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parents[1]
AUTHOR = ROOT / "evidence/stream/buffered-block-stream-20261024-35/author"
SOURCE_COMMIT = "bbfb11439b35e0866a6d2486f3857b92ed6cf529"
CONTRACT_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
REQUIREMENTS_SHA = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
AGENT_ID = "01a16a27-3458-7103-a4ab-cd06fd084da7"
JOB_ID = "child-64ceef15f6da43d180d604be08e43c43"
WORK_ID = "B-BUFFERED-BLOCK-STREAM-20261024-35-native-recovery1"
PINS = {
    "fpga/codec/deepeye_block_encoder.sv":
        "870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5",
    "fpga/stream/deepeye_block_stream.sv":
        "c8f8c0d99769efc64a91402ee23e7157368ff90ec765db5c413f02546715fff4",
    "fpga/stream/deepeye_encoded_frame_queue.sv":
        "68f9b655794a722a5cb285ac1c87749ea7acea7dcd6c1650536d1f1094c2e76a",
    "golden/codec/codec_reference.py":
        "2e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5",
    "golden/codec/known_vectors.json":
        "c1eee67b73b8cdd449ac72b2a77c78f714eaf448b1216b16296488881ac10e99",
}
OWNED_SOURCES = (
    "fpga/stream/deepeye_buffered_block_stream.sv",
    "tests/rtl/stream/tb_buffered_block_stream.sv",
    "tools/stream/run_buffered_block_stream.py",
    "fpga/stream/buffered_block_stream_candidate.md",
)
PHASES = (
    "raw_fill", "encoding", "metadata_boundary", "encoded_fill",
    "output_stall", "final_data", "final_error_metadata",
)
# Counts follow the authored control flow; they are not inferred from a DUT log.
CASE_CHECKS = [
    ("valid_vectors", 3),
    ("error_order_duplicate_tags", 3),
    ("full_queue_frontend_backpressure", 5),
    ("final_data_metadata_same_edge_credit", 2),
    ("error_metadata_same_edge_credit", 2),
    ("full_error_metadata_retirement_bubble", 3),
]
CASE_CHECKS += [(f"{op}_{phase}", 6 if op == "cancel" else 5)
                for phase in PHASES for op in ("cancel", "reset")]
CASE_CHECKS += [("reset_over_cancel_priority", 5)]
PINNED_TB_SHA256 = "8b3cf8c310ad13ae63da7925f3a7a6dd853c1ed32195b24f2091606827a17933"
TB_RELATIVE_PATH = "tests/rtl/stream/tb_buffered_block_stream.sv"


class FixtureFailure(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def run_command(attempt, records, argv, timeout=60):
    """Persist raw streams and actual exit even on failure/timeout."""
    index = len(records) + 1
    stem = f"command-{index:02d}"
    rec = {
        "argv": [str(x) for x in argv], "cwd": str(attempt),
        "started_at": now(), "timeout_seconds": timeout,
        "hidden_window": os.name == "nt",
    }
    opts = {}
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        opts = {"startupinfo": si, "creationflags": subprocess.CREATE_NO_WINDOW}
    start = time.monotonic()
    try:
        proc = subprocess.Popen(rec["argv"], cwd=attempt,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                **opts)
        rec["pid"] = proc.pid
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            rec["timed_out"] = False
        except subprocess.TimeoutExpired:
            rec["timed_out"] = True
            if os.name == "nt":
                cleanup = subprocess.run(
                    ["taskkill.exe", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True, **opts, timeout=15)
                (attempt / f"{stem}.timeout-cleanup.stdout.bin").write_bytes(cleanup.stdout)
                (attempt / f"{stem}.timeout-cleanup.stderr.bin").write_bytes(cleanup.stderr)
                rec["cleanup_exit_code"] = cleanup.returncode
            else:
                proc.kill()
            stdout, stderr = proc.communicate(timeout=15)
        rec["exit_code"] = proc.returncode
    except OSError as exc:
        stdout, stderr = b"", str(exc).encode("utf-8")
        rec.update(exit_code=None, timed_out=False, launch_error=str(exc))
    rec.update(finished_at=now(), elapsed_seconds=time.monotonic() - start)
    for name, data in (("stdout", stdout), ("stderr", stderr)):
        path = attempt / f"{stem}.{name}.bin"
        path.write_bytes(data)
        rec[name] = {"path": str(path.relative_to(AUTHOR)),
                     "sha256": digest(data), "bytes": len(data)}
    records.append(rec)
    save_json(attempt / "commands.json", records)
    if rec["timed_out"] or rec["exit_code"] != 0:
        raise FixtureFailure(f"{stem}: exit={rec['exit_code']} timeout={rec['timed_out']}")
    return stdout, stderr


def reject_diagnostics(raw):
    text = raw.decode("utf-8", errors="strict")
    for line in text.splitlines():
        line = line[2:] if line.startswith("# ") else line
        # Protocol error outcomes are data, validated by the complete grammar.
        # A malformed BBS record still fails parse_suite; it is never ignored.
        if line.startswith("BBS_"):
            continue
        tally = re.fullmatch(r"(?:End time: .*? )?Errors: ([0-9]+), Warnings: ([0-9]+)", line)
        # ModelSim's end-time and diagnostic tally may occupy separate lines.
        if tally:
            if tuple(map(int, tally.groups())) != (0, 0):
                raise FixtureFailure("nonzero ModelSim diagnostic tally")
            continue
        if re.search(r"\b(?:warning|fatal|error)\b", line, re.IGNORECASE):
            raise FixtureFailure(f"ModelSim diagnostic: {line}")
        if re.search(r"Errors:\s*[1-9]|Warnings:\s*[1-9]", line):
            raise FixtureFailure(f"nonzero embedded tally: {line}")
    return text


def make_vectors():
    ref = types.ModuleType("published_codec_reference")
    ref.__file__ = str(ROOT / "golden/codec/codec_reference.py")
    exec(compile(Path(ref.__file__).read_bytes(), ref.__file__, "exec"), ref.__dict__)
    known = json.loads((ROOT / "golden/codec/known_vectors.json").read_bytes())
    vectors = []
    verified_known = 0

    def add(name, samples, e, count=None, error=0, lasts=None, fixture=None):
        nonlocal verified_known
        count = len(samples) if count is None else count
        if not error:
            computed = ref.encode_block(samples, e)
            if fixture is not None:
                if computed != fixture:
                    raise FixtureFailure(f"published fixture mismatch: {name}")
                verified_known += 1
            fixture = computed
            meta = {
                "count": count, "e": e, "raw": int(fixture["mode"] == "raw"),
                "k": fixture["k"] or 0, "bits": fixture["valid_bit_count"],
                "payload": list(bytes.fromhex(fixture["payload_hex"])),
            }
        else:
            meta = {"count": 0, "e": 0, "raw": 1, "k": 0, "bits": 0, "payload": []}
        vectors.append({
            "name": name, "samples": samples, "e": e, "count": count,
            "error": error,
            "lasts": lasts if lasts is not None else
                [int(i == len(samples) - 1) for i in range(len(samples))],
            "expected": meta,
        })

    add("single_anchor", [0x1234], 0)
    add("two_near", [90, 91], 1)
    add("long_raw_extrema", [0, 65535] * 64, 0)
    add("invalid_count_zero", [], 0, count=0, error=1)
    add("early_last", [12], 0, count=4, error=2, lasts=[1])
    add("late_last", [12, 13], 0, count=2, error=2, lasts=[0, 0])
    for ei, e in enumerate((0, 1, 2, 4, 8)):
        for ni, n in enumerate((1, 2, 127, 128)):
            pattern = (ei + ni) % 5
            if pattern == 0:
                values = [0] * n
            elif pattern == 1:
                values = [1000 + 11 * i for i in range(n)]
            elif pattern == 2:
                values = [32000 + (i % 17) * 123 if i % 34 < 17
                          else 32000 - (i % 17) * 123 for i in range(n)]
            elif pattern == 3:
                values = [0 if i % 2 == 0 else 65535 for i in range(n)]
            else:
                values = []
                state = 0x350024
                for _ in range(n):
                    state = (1664525 * state + 1013904223) & 0xFFFFFFFF
                    values.append(state >> 16)
            add(f"matrix_n{n}_e{e}_pattern{pattern}", values, e)
    for count in (129, 255):
        add(f"invalid_count_{count}", [], 0, count=count, error=1)
    for e in (3, 15):
        add(f"invalid_e_{e}", [], e, count=2, error=1)
    for group in ("hand_vectors", "raw_noisy_examples", "raw_step_examples"):
        for item in known[group]:
            add(item["id"], item["samples"], item["e"], fixture=item["fixture"])
    return vectors, verified_known


def write_include(path, vectors):
    lines = [
        "// Author expectations from the pinned published codec reference.",
        "localparam int V_SINGLE=0, V_SMALL=1, V_LONG=2, V_ERR=3;",
        f"localparam int V_TOTAL={len(vectors)};",
        "int v_count [0:V_TOTAL-1], v_e [0:V_TOTAL-1], v_error [0:V_TOTAL-1];",
        "int v_send [0:V_TOTAL-1], v_meta_count [0:V_TOTAL-1], v_meta_e [0:V_TOTAL-1];",
        "int v_raw [0:V_TOTAL-1], v_k [0:V_TOTAL-1], v_bits [0:V_TOTAL-1];",
        "int v_bytes [0:V_TOTAL-1];",
        "logic [15:0] v_samples [0:V_TOTAL-1][0:127];",
        "logic [7:0] v_payload [0:V_TOTAL-1][0:255];",
        "bit v_last [0:V_TOTAL-1][0:127];",
        "task automatic load_vectors;",
        "begin",
    ]
    for i, v in enumerate(vectors):
        meta = v["expected"]
        fields = {"count": v["count"], "e": v["e"], "error": v["error"],
                  "send": len(v["samples"]), "meta_count": meta["count"],
                  "meta_e": meta["e"], "raw": meta["raw"], "k": meta["k"],
                  "bits": meta["bits"], "bytes": len(meta["payload"])}
        lines += [f"v_{key}[{i}]={val};" for key, val in fields.items()]
        lines += [f"v_samples[{i}][{j}]=16'h{sample:04x}; v_last[{i}][{j}]={v['lasts'][j]};"
                  for j, sample in enumerate(v["samples"])]
        lines += [f"v_payload[{i}][{j}]=8'h{byte:02x};"
                  for j, byte in enumerate(meta["payload"])]
    lines += ["end", "endtask"]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def fixed_case_plan(vectors):
    """Expected checks/admissions from the pinned TB, never a candidate log.

    TB lines 546-666 define the first six cases; interruption_case and
    clear_once define the seven cancel/reset pairs; lines 673-683 define the
    final reset-priority case. Each tuple below is (check label, exact value).
    The supplied vectors are the published expectations, not DUT observations.
    """
    good = [i for i, v in enumerate(vectors) if not v["error"]]
    bad = [i for i, v in enumerate(vectors) if v["error"]]
    end = ("all_admissions_terminal", 0)

    def record(vid, tag, outcome, partial_meta=0, partial_bytes=0):
        return {"vector": vid, "tag": tag, "outcome": outcome,
                "partial_metadata": partial_meta, "partial_payload_bytes": partial_bytes}

    plan = [
        {"name": "valid_vectors",
         "records": [record(i, 0x3500 + i, "ok") for i in good],
         "checks": [("all_expected_encoded_bytes",
                     sum(len(vectors[i]["expected"]["payload"]) for i in good)),
                    ("raw_success_error_split", len(good)), end]},
        {"name": "error_order_duplicate_tags",
         "records": [record(0, 0xBBBB, "ok")] +
                    [r for i in bad for r in
                     (record(i, 0xBBBB, "error"), record(0, 0xBBBB, "ok"))],
         "checks": [("all_config_last_errors", len(bad)),
                    ("upstream_errors_are_frames", 0), end]},
        {"name": "full_queue_frontend_backpressure",
         "records": [record(0, 0x7777, "ok") for _ in range(5)],
         "checks": [("four_unique_bounded_residents", 4),
                    ("full_cfg_backpressure", 4),
                    ("old_full_final_data_no_same_edge_credit", 2),
                    ("fifth_admission_after_credit", 5), end]},
        {"name": "final_data_metadata_same_edge_credit",
         "records": [record(0, 0x6100, "ok"), record(3, 0x6101, "error")],
         "checks": [("old_one_simultaneous_final_data_metadata", 1), end]},
        {"name": "error_metadata_same_edge_credit",
         "records": [record(3, 0x6200, "error"), record(3, 0x6201, "error")],
         "checks": [("old_one_simultaneous_error_metadata", 1), end]},
        {"name": "full_error_metadata_retirement_bubble",
         "records": [record(3, 0x6300 + i, "error") for i in range(3)],
         "checks": [("old_full_error_no_same_edge_credit", 2),
                    ("next_edge_descriptor_credit", 3), end]},
    ]
    boundaries = (
        ("raw_fill_boundary", 1), ("encoding_public_boundary", 0),
        ("pre_metadata_transfer_boundary", 1),
        ("overlapping_same_block_reservations", 1),
        ("stalled_output_and_raw_fill", 2), ("final_data_boundary", 1),
        ("final_error_metadata_boundary", 1),
    )
    # Raw and encoded reservations overlap only during the encoded-fill case.
    abort_level_sum = (1, 1, 1, 2, 2, 1, 1)
    for phase, name in enumerate(PHASES):
        for operation in ("cancel", "reset"):
            vid = 2 if phase in (0, 1, 3) else 3 if phase in (2, 6) else 0
            # TB phase 4 accepts the SINGLE header and stalls its first byte.
            # Phase 5's wait_final accepts every byte except the final byte.
            partial_meta = int(phase in (4, 5))
            partial_bytes = (len(vectors[0]["expected"]["payload"]) - 1
                             if phase == 5 else 0)
            records = [record(vid, 0x8800 + phase, operation,
                              partial_meta, partial_bytes)]
            if phase == 4:
                records.append(record(2, 0x9904, operation))
            records.append(record(0, 0xFACE, "ok"))  # explicit post-clear reuse
            checks = [boundaries[phase], ("clear_has_actual_residency", 1),
                      ("clear_empties_both_stages", 0)]
            if operation == "reset":
                checks.append(("reset_priority_counters", 0))
            else:
                checks += [
                    ("cancel_separate_overlap_accounting", abort_level_sum[phase]),
                    ("cancel_preserves_stage_counters", 2 if phase == 4 else 1),
                ]
            plan.append({"name": f"{operation}_{name}", "records": records,
                         "checks": checks + [end]})
    total = sum(len(case["records"]) for case in plan) + 3
    plan.append({
        "name": "reset_over_cancel_priority",
        "records": [record(0, 0xFF00, "reset"), record(2, 0xFF01, "reset"),
                    record(0, 0xFACE, "ok")],
        "checks": [("clear_has_actual_residency", 1), ("clear_empties_both_stages", 0),
                   ("reset_priority_counters", 0),
                   ("every_admission_exactly_one_outcome", total), end],
    })
    if [(c["name"], len(c["checks"])) for c in plan] != CASE_CHECKS:
        raise FixtureFailure("fixed testcase/check plan conflicts with case declarations")
    return plan


def finish_cycle_basis(normalized_lines, tb_path):
    """Validate the saved ModelSim finish/time/trailer against the full TB pin.

    No controller layout is used. tb_path may point at an exact source copy on
    another node; log paths may have any drive/prefix and either separator.
    """
    source = Path(tb_path).read_bytes()
    if digest(source) != PINNED_TB_SHA256:
        raise FixtureFailure("full pinned testbench source hash mismatch")
    source_lines = source.decode("utf-8").splitlines()
    finish_lines = [i + 1 for i, line in enumerate(source_lines)
                    if line.strip() == "$finish;"]
    if len(finish_lines) != 1:
        raise FixtureFailure("pinned TB must have exactly one normal finish")
    finish_line = finish_lines[0]
    final_positions = [i for i, line in enumerate(normalized_lines)
                       if line == "BBS_FINAL result=PASS"]
    if len(final_positions) != 1:
        raise FixtureFailure("missing/duplicate final marker association")
    suffix = normalized_lines[final_positions[0] + 1:]
    # ModelSim 10.7's saved -onfinish stop envelope is six ordered whole lines.
    if len(suffix) != 6:
        raise FixtureFailure("missing/duplicate/unassociated finish or diagnostic trailer")
    note = re.fullmatch(r"\*\* Note: \$finish\s+: (.+)\(([0-9]+)\)", suffix[0])
    stamp = re.fullmatch(
        r"\s+Time: ([0-9]+) ns  Iteration: 1  Instance: /tb_buffered_block_stream",
        suffix[1])
    stopped = [re.fullmatch(fr"{kind} at (.+) line ([0-9]+)", suffix[i])
               for i, kind in ((2, "Break"), (3, "Stopped"))]
    end = re.fullmatch(
        r"End time: [0-9]{2}:[0-9]{2}:[0-9]{2} on "
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
        r"[0-9]{1,2},[0-9]{4}, Elapsed time: [0-9]+:[0-9]{2}:[0-9]{2}",
        suffix[4])
    if not note or not stamp or not all(stopped) or not end or suffix[5] != "Errors: 0, Warnings: 0":
        raise FixtureFailure("malformed anchored finish/time/trailer association")
    path = note[1].replace("\\", "/")
    if not path.endswith(TB_RELATIVE_PATH) or int(note[2]) != finish_line:
        raise FixtureFailure("finish does not identify the pinned TB/finish line")
    for match in stopped:
        if match[1].replace("\\", "/") != path or int(match[2]) != finish_line:
            raise FixtureFailure("break/stop record conflicts with finish source")
    finish_markers = [line for line in normalized_lines if "$finish" in line]
    time_markers = [line for line in normalized_lines if re.search(r"\bTime:", line)]
    trailer_markers = [line for line in normalized_lines if line.startswith("Errors:")]
    if finish_markers != [suffix[0]] or time_markers != [suffix[1]] or trailer_markers != [suffix[5]]:
        raise FixtureFailure("finish/time/diagnostic record is not unique")
    # Pinned TB: clk starts low; first falling edge is t=10ns. step() then
    # counts the rising edge at 15ns (#1) and returns at t=20ns. Every further
    # step returns 10ns later; no other timed waits occur in the driver.
    # Thus N observed steps finish at (N + 1)*10ns, not at N*10ns.
    finish_ns = int(stamp[1])
    if finish_ns < 20 or finish_ns % 10:
        raise FixtureFailure("finish time violates pinned 10ns step timeline")
    cycles = finish_ns // 10 - 1
    max_cycles = re.search(r"MAX_CYCLES = ([0-9_]+);", source.decode("utf-8"))
    if not max_cycles or cycles >= int(max_cycles[1].replace("_", "")):
        raise FixtureFailure("finish exceeds pinned watchdog horizon")
    return {"finish_time_ns": finish_ns, "clock_period_ns": 10,
            "initial_unobserved_periods": 1, "derived_invariant_cycles": cycles,
            "formula": "finish_time_ns // 10 - 1",
            "testbench_sha256": PINNED_TB_SHA256, "finish_source_line": finish_line}


def parse_suite(raw, vectors, *, tb_path=None):
    """Whole-line grammar: ordered suite/cases/checks/identities/terminal/diag."""
    text = reject_diagnostics(raw)
    plan = fixed_case_plan(vectors)
    normalized = [line[2:] if line.startswith("# ") else line
                  for line in text.splitlines() if line.strip()]
    lines = []
    for original in text.splitlines():
        line = original[2:] if original.startswith("# ") else original
        if "BBS_" in line:
            if not line.startswith("BBS_"):
                raise FixtureFailure("prefixed protocol marker")
            lines.append(line)
        elif re.search(r"\b(?:PASS|FAIL)\b", line):
            raise FixtureFailure("bare protocol trailer")
    if not lines or lines[0] != "BBS_SUITE_BEGIN version=1":
        raise FixtureFailure("missing/duplicate suite begin")
    pos = 1
    checks = 0
    admitted = {}
    completed = {}
    per_case = []
    for cid, (name, expected_checks) in enumerate(CASE_CHECKS):
        case_plan = plan[cid]
        case_start_id = len(admitted)
        expected = f"BBS_CASE_BEGIN case={cid} name={name}"
        if pos >= len(lines) or lines[pos] != expected:
            raise FixtureFailure(f"case order: expected {expected}")
        pos += 1
        local_checks = 0
        while pos < len(lines) and not lines[pos].startswith("BBS_CASE_END "):
            line = lines[pos]
            admit = re.fullmatch(r"BBS_ADMIT id=([0-9]+) case=([0-9]+) vector=([0-9]+) tag=([0-9]+)", line)
            term = re.fullmatch(r"BBS_TERMINAL id=([0-9]+) case=([0-9]+) outcome=(ok|error|cancel|reset)", line)
            check = re.fullmatch(r"BBS_CHECK seq=([0-9]+) case=([0-9]+) label=([a-z][a-z0-9_]*) observed=(-?[0-9]+) expected=(-?[0-9]+) result=PASS", line)
            if admit:
                ident, case, vid, tag = map(int, admit.groups())
                if case != cid or ident != len(admitted) or not 0 <= vid < len(vectors) or tag > 65535:
                    raise FixtureFailure("invalid admission identity")
                admitted[ident] = {"case": case, "vector": vid, "tag": tag}
            elif term:
                ident, case, outcome = term.groups()
                ident, case = int(ident), int(case)
                if case != cid or ident not in admitted or ident in completed:
                    raise FixtureFailure("duplicate/unadmitted terminal")
                if ident != len(completed):
                    raise FixtureFailure("out-of-order terminal")
                vec = vectors[admitted[ident]["vector"]]
                if outcome in ("ok", "error") and (outcome == "error") != bool(vec["error"]):
                    raise FixtureFailure("conflicting terminal outcome")
                completed[ident] = outcome
            elif check:
                seq, case = map(int, check.groups()[:2])
                if case != cid or seq != checks + 1:
                    raise FixtureFailure("duplicate/out-of-order check")
                label, observed, expected_value = check.groups()[2:]
                observed, expected_value = int(observed), int(expected_value)
                if observed != expected_value:
                    raise FixtureFailure("PASS check observed/expected values differ")
                if local_checks >= len(case_plan["checks"]) or (
                        label, expected_value) != case_plan["checks"][local_checks]:
                    raise FixtureFailure("check label/order/expected value conflicts with pinned TB plan")
                checks += 1
                local_checks += 1
            else:
                raise FixtureFailure(f"invalid/duplicate protocol record: {line}")
            pos += 1
        expected = f"BBS_CASE_END case={cid} name={name} checks={expected_checks} failures=0"
        if pos >= len(lines) or lines[pos] != expected or local_checks != expected_checks:
            raise FixtureFailure(f"case tally mismatch: {name}")
        if len(admitted) != len(completed):
            raise FixtureFailure("case ended with unresolved admissions")
        case_admissions = [admitted[i] for i in range(case_start_id, len(admitted))]
        expected_records = case_plan["records"]
        if len(case_admissions) != len(expected_records):
            raise FixtureFailure("case admissions conflict with pinned testcase plan")
        for offset, (actual, planned) in enumerate(zip(case_admissions, expected_records)):
            ident = case_start_id + offset
            if (actual["vector"], actual["tag"], completed[ident]) != (
                    planned["vector"], planned["tag"], planned["outcome"]):
                raise FixtureFailure("admission/outcome conflicts with pinned testcase plan")
        per_case.append({"case": cid, "name": name, "checks": local_checks})
        pos += 1
    if pos >= len(lines):
        raise FixtureFailure("missing suite tally")
    tally = re.fullmatch(r"BBS_SUITE_TALLY cases=([0-9]+) checks=([0-9]+) admissions=([0-9]+) terminals=([0-9]+) metadata=([0-9]+) payload_bytes=([0-9]+) invariant_cycles=([0-9]+)", lines[pos])
    if not tally:
        raise FixtureFailure("malformed suite tally")
    cases, reported_checks, admissions, terminals, metadata, payload, cycles = map(int, tally.groups())
    if (cases, reported_checks, admissions, terminals) != (
            len(CASE_CHECKS), checks, len(admitted), len(completed)) or cycles < 1:
        raise FixtureFailure("suite totals conflict")
    if lines[pos + 1:] != ["BBS_DIAG failures=0 watchdog=0 live=0", "BBS_FINAL result=PASS"]:
        raise FixtureFailure("missing/duplicate/suffixed final diagnostic")
    # All completed frames contribute their headers/expected payloads. Only
    # the explicitly planned interrupted output phases contribute partial IO.
    expected_metadata = 0
    expected_payload = 0
    partials = []
    planned_records = [r for case in plan for r in case["records"]]
    for ident, actual in admitted.items():
        outcome = completed[ident]
        if outcome in ("ok", "error"):
            expected_metadata += 1
            if outcome == "ok":
                expected_payload += len(vectors[actual["vector"]]["expected"]["payload"])
        else:
            planned = planned_records[ident]
            expected_metadata += planned["partial_metadata"]
            expected_payload += planned["partial_payload_bytes"]
            if planned["partial_metadata"] or planned["partial_payload_bytes"]:
                partials.append({"id": ident, "case": actual["case"],
                                 "metadata": planned["partial_metadata"],
                                 "payload_bytes": planned["partial_payload_bytes"]})
    if (metadata, payload) != (expected_metadata, expected_payload):
        raise FixtureFailure("metadata/payload tally conflicts with ledger and fixed phase plan")
    cycle_basis = finish_cycle_basis(normalized, tb_path or ROOT / TB_RELATIVE_PATH)
    if cycles != cycle_basis["derived_invariant_cycles"]:
        raise FixtureFailure("invariant cycle tally conflicts with independent finish time")
    return {
        "cases": per_case, "checks": checks, "admissions": admissions,
        "terminals": terminals, "metadata_observed": metadata,
        "payload_bytes_observed": payload, "invariant_cycles": cycles,
        "tally_derivation": {
            "metadata_from_ledger_and_phase_plan": expected_metadata,
            "payload_from_vectors_and_phase_plan": expected_payload,
            "interrupted_output_contributions": partials,
            "cycle_basis": cycle_basis,
        },
        "outcome_counts": {k: list(completed.values()).count(k)
                           for k in ("ok", "error", "cancel", "reset")},
        "admission_ledger": [
            {"id": ident, **value, "outcome": completed[ident]}
            for ident, value in admitted.items()],
    }


def parser_negative_controls(raw, vectors):
    """Reject mutated transcripts; these are parser tests, not DUT mutations."""
    text = raw.decode("utf-8")
    marker = "# BBS_FINAL result=PASS" if "# BBS_FINAL result=PASS" in text else "BBS_FINAL result=PASS"
    tests = {
        "prefixed_marker": text.replace(marker, "junk " + marker, 1),
        "suffixed_marker": text.replace(marker, marker + " junk", 1),
        "duplicate_final": text + "\n" + marker + "\n",
        "duplicate_field": text.replace("BBS_FINAL result=PASS", "BBS_FINAL result=PASS result=PASS", 1),
        "bare_trailer": text + "\n# PASS\n",
        "conflicting_result": text.replace("BBS_FINAL result=PASS", "BBS_FINAL result=FAIL", 1),
        "warning": text + "\n# ** Warning: synthetic parser probe\n",
        "fatal": text + "\n# ** Fatal: synthetic parser probe\n",
        "nonzero_diagnostics": text + "\n# Errors: 1, Warnings: 0\n",
        "duplicate_case": text.replace("BBS_CASE_BEGIN case=0 name=valid_vectors",
                                       "BBS_CASE_BEGIN case=0 name=valid_vectors\n# BBS_CASE_BEGIN case=0 name=valid_vectors", 1),
        "missing_terminal": re.sub(r"^.*BBS_TERMINAL id=0 .*\n", "", text, count=1, flags=re.M),
        "missing_diagnostic": text.replace("BBS_DIAG failures=0 watchdog=0 live=0", "", 1),
    }
    results = []
    for name, mutant in tests.items():
        try:
            parse_suite(mutant.encode("utf-8"), vectors)
        except (FixtureFailure, IndexError) as exc:
            results.append({"name": name, "rejected": True, "reason": str(exc)})
        else:
            raise FixtureFailure(f"parser accepted negative control {name}")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=int, required=True, choices=(1, 2, 3))
    parser.add_argument("--modelsim", type=Path, default=Path("D:/modelsim1/win64"))
    args = parser.parse_args()
    attempt = AUTHOR / f"attempt-{args.attempt:02d}"
    attempt.mkdir(parents=True, exist_ok=False)
    records = []
    result = {
        "status": "running", "started_at": now(), "task_id": "DEEPEYE-IMPLEMENTATION-20261014",
        "task_version": 1, "work_id": WORK_ID,
        "canonical_agent_id": AGENT_ID, "job_id": JOB_ID,
        "environment_thread_id": os.environ.get("CODEX_THREAD_ID"),
        "attempt": args.attempt, "simulation": "not_run",
        "requirements_ids": [f"H{i:02d}" for i in range(1, 16)],
        "requirements_sha256": REQUIREMENTS_SHA,
        "source_commit": SOURCE_COMMIT,
        "author_reference_reuse": "pinned published codec_reference.py + known_vectors.json",
        "acceptance": "not_run; quality main owns independent acceptance",
        "commands": [],
    }
    try:
        # Pin original bytes; no checkout, dependency editing, or main oracle.
        snapshots = attempt / "source"
        before = {}
        for rel in (*PINS, *OWNED_SOURCES):
            data = (ROOT / rel).read_bytes()
            before[rel] = digest(data)
            if rel in PINS and before[rel] != PINS[rel]:
                raise FixtureFailure(f"working pin mismatch {rel}")
            dest = snapshots / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        result["source_hashes_before"] = before
        for rel in PINS:
            out, err = run_command(attempt, records, [
                "git", "-C", str(REPO), "show",
                f"{SOURCE_COMMIT}:competition/deepeye/{rel}"])
            if err or digest(out) != PINS[rel]:
                raise FixtureFailure(f"Git blob pin mismatch {rel}")
        out, err = run_command(attempt, records, [
            "git", "-C", str(REPO), "show",
            f"{CONTRACT_COMMIT}:docs/competition/deepeye-2026/immutable_scope.json"])
        contract = json.loads(out)
        actual = digest(json.dumps(contract["requirements"], ensure_ascii=False,
                                   sort_keys=True, separators=(",", ":")).encode("utf-8"))
        if err or actual != REQUIREMENTS_SHA:
            raise FixtureFailure("fixed contract hash mismatch")
        result["verified_contract_sha256"] = actual
        vectors, known_count = make_vectors()
        save_json(attempt / "vectors.json", vectors)
        write_include(attempt / "bbs_vectors.svh", vectors)
        result.update(vectors=len(vectors), published_fixtures_verified=known_count,
                      vector_include_sha256=digest((attempt / "bbs_vectors.svh").read_bytes()))
        for exe in ("vlog.exe", "vsim.exe"):
            out, err = run_command(attempt, records, [args.modelsim / exe, "-version"], timeout=15)
            reject_diagnostics(out + err)
        run_command(attempt, records, [sys.executable, "--version"], timeout=15)
        out, err = run_command(attempt, records, [args.modelsim / "vlib.exe", "work"])
        reject_diagnostics(out + err)
        rtl = [ROOT / rel for rel in PINS if rel.endswith(".sv")]
        out, err = run_command(attempt, records, [
            args.modelsim / "vlog.exe", "-sv", "-work", "work",
            f"+incdir+{attempt.as_posix()}", *rtl,
            ROOT / OWNED_SOURCES[0], ROOT / OWNED_SOURCES[1]])
        reject_diagnostics(out + err)
        result["simulation"] = "running"
        # ModelSim 10.7 accepts onerror only inside a do-file, not inline -do.
        (attempt / "run.do").write_text(
            "onerror {quit -code 2}\nrun -all\nquit -code 0\n", encoding="ascii")
        out, err = run_command(attempt, records, [
            args.modelsim / "vsim.exe", "-c", "-onfinish", "stop",
            "-l", "vsim.transcript.txt", "work.tb_buffered_block_stream",
            "-do", "do run.do"])
        parsed = parse_suite(out + err, vectors)
        result["simulation"] = "passed"
        result["bounded_checks"] = parsed
        result["parser_negative_controls"] = parser_negative_controls(out + err, vectors)
        after = {rel: digest((ROOT / rel).read_bytes()) for rel in before}
        result["source_hashes_after"] = after
        if after != before:
            raise FixtureFailure("source changed during the attempt")
        result["status"] = "author_checks_passed"
    except Exception as exc:
        result.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        if result["simulation"] == "running":
            result["simulation"] = "failed"
    result.update(finished_at=now(), commands=records)
    save_json(attempt / "run-result.json", result)
    print(json.dumps({k: result.get(k) for k in
                      ("status", "simulation", "attempt", "vectors", "error")}))
    return 0 if result["status"] == "author_checks_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
