"""Bounded author simulation for the fixed capture/queue wrapper (operation 39).

The RTL reference chain tests wiring only. This runner checks complete public
traces with a separate record/list model, including control and counter effects.
No vendor state is forced, and no board, timing, formal or device claim is made.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
WORKTREE = ROOT.parents[1]
REPO = Path("D:/pynq/CarlandFPGA")
AUTHOR = ROOT / "evidence/acquisition/buffered-scan-20261024-39/author"
SPEC = REPO / ".local/deployment/node-b/evidence/buffered-scan-20261024-39/MAIN_SPEC.md"
AGENT = "01a16a27-3458-7103-a4ab-cd06fd084da7"
JOB = "child-c1ae159dfb104da5a007062cf42b3b3f"
BASE = "0885ed48b9edc48be7fd20135e8c141a485218d4"
CONTRACT_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
CONTRACT_HASH = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
SPEC_HASH = "aa7693c42946662c48b791ca9eda4fa6a01e5a3a5ef9c5b07fefd711b1163d04"
PINS = {
    "fpga/acquisition/deepeye_sample_scan_capture.sv":
        "fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d",
    "fpga/acquisition/deepeye_raw_scan_queue.sv":
        "630e14803d82b3379517d91626de4ad7e7d3c509ad14363b3164031a5f633ee4",
    "tests/rtl/acquisition/tb_raw_scan_queue.sv":
        "e38944f5340cd4f17c9f6a2481ed4150cf82d3902031dec3ac7f6db3790f0ad0",
}
OWN_SOURCES = [
    "fpga/acquisition/deepeye_buffered_scan_capture.sv",
    "fpga/acquisition/buffered_scan_capture_candidate.md",
    "tests/rtl/acquisition/tb_buffered_scan_capture.sv",
    "tools/acquisition/run_buffered_scan_capture.py",
]
INPUTS = [
    ("rst", 1), ("stop", 1), ("rearm", 1), ("queue_cancel", 1),
    ("sample_strobe", 1), ("rearm_tag", 32), ("sample_channel", 2),
    ("sample_data", 16), ("sample_tick", 64), ("sample_quality", 8), ("out_ready", 1),
]
CONTROL_OUTPUTS = [
    ("out_valid", 1), ("capture_armed", 1), ("capture_partial_len", 3),
    ("capture_next_seq", 32), ("capture_seq_exhausted", 1),
    ("capture_order_error_event", 1), ("capture_overrun_event", 1),
    ("capture_seq_exhaust_event", 1), ("capture_stat_events", 32),
    ("capture_stat_scans", 32), ("capture_stat_retired", 32),
    ("capture_stat_discarded_samples", 32), ("capture_stat_order_errors", 32),
    ("capture_stat_overruns", 32), ("queue_level", 3),
    ("queue_stat_accepted", 32), ("queue_stat_retired", 32), ("queue_stat_aborted", 32),
]
RECORD_OUTPUTS = [
    ("out_data", 64), ("out_ticks", 256), ("out_quality", 32),
    ("out_first_seq", 32), ("out_last_seq", 32), ("out_tag", 32),
]
MAX32 = (1 << 32) - 1
ZERO_RECORD = (0, 0, 0, 0, 0, 0)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def pack(values, layout):
    result = 0
    for name, width in layout:
        value = values[name]
        if not isinstance(value, int) or not 0 <= value < 1 << width:
            raise ValueError(f"invalid {name}: {value}")
        result = (result << width) | value
    return result


def guarded_output(path: Path) -> Path:
    """Never clobber, and never accept a source/input alias or escape."""
    resolved = path.resolve()
    allowed = AUTHOR.resolve()
    if not resolved.is_relative_to(allowed) or resolved == allowed:
        raise ValueError("output must be a new child directory of the owned author directory")
    inputs = [ROOT / rel for rel in (*PINS, *OWN_SOURCES)] + [SPEC]
    for source in inputs:
        source = source.resolve()
        if resolved == source or source.is_relative_to(resolved):
            raise ValueError("output aliases an input")
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"preexisting output refused: {path}")
    return resolved


@dataclass(frozen=True)
class Vector:
    label: str
    values: dict

    @property
    def encoded(self):
        return f"{pack(self.values, INPUTS):032x}"


def make_plan():
    vectors = []

    def add(label, **changes):
        i = len(vectors)
        ch = changes.get("sample_channel", 0)
        values = dict(rst=0, stop=0, rearm=0, queue_cancel=0, sample_strobe=0,
                      rearm_tag=0x89ABCDEF, sample_channel=ch,
                      sample_data=((i * 405 + ch * 1151) ^ 0x968D) & 0xFFFF,
                      sample_tick=(0xFEDCBA9800000000 ^ (i << 20)
                                   ^ (ch * 0x0101010101010101)) & ((1 << 64) - 1),
                      sample_quality=(i * 73 + ch * 37) & 255, out_ready=0)
        values.update(changes)
        vectors.append(Vector(label, values))

    def scan(label, ready=0):
        for ch in range(4):
            add(label, sample_strobe=1, sample_channel=ch, out_ready=ready)

    def reset_arm(label, tag=0x89ABCDEF):
        add(label, rst=1, sample_strobe=1, out_ready=1)
        add(label, rearm=1, rearm_tag=tag, sample_strobe=1)

    def drain(label, count=8):
        for _ in range(count):
            add(label, out_ready=1)

    reset_arm("normal")
    for _ in range(3):
        scan("normal", ready=1)
    drain("normal")
    for ch in [2, 0, 2, 0, 1, 0, 1, 2, 3, 1, 0, 1]:
        add("order_errors", sample_strobe=1, sample_channel=ch, out_ready=1)
    reset_arm("stop_preserves_queue")
    scan("stop_preserves_queue")
    add("stop_preserves_queue")
    add("stop_preserves_queue", sample_strobe=1, sample_channel=0)
    add("stop_preserves_queue", sample_strobe=1, sample_channel=1)
    add("stop_preserves_queue", stop=1, sample_strobe=1)
    drain("stop_preserves_queue")
    reset_arm("rearm_preserves_queue", 0xF1020304)
    scan("rearm_preserves_queue")
    add("rearm_preserves_queue")
    add("rearm_preserves_queue", rearm=1, rearm_tag=0x82E6A591)
    scan("rearm_preserves_queue")
    add("rearm_preserves_queue")
    drain("rearm_preserves_queue")
    reset_arm("cancel_pending_overrun")
    for _ in range(5):
        scan("cancel_pending_overrun")
        add("cancel_pending_overrun")
    scan("cancel_pending_overrun")
    for ch in [0, 1]:
        add("cancel_pending_overrun", sample_strobe=1, sample_channel=ch)
    add("cancel_pending_overrun", queue_cancel=1, sample_strobe=1, sample_channel=2)
    add("cancel_pending_overrun")
    add("cancel_pending_overrun", sample_strobe=1, sample_channel=3)
    drain("cancel_pending_overrun")
    reset_arm("simultaneous_push_pop")
    scan("simultaneous_push_pop")
    add("simultaneous_push_pop")
    scan("simultaneous_push_pop")
    add("simultaneous_push_pop", out_ready=1)
    drain("simultaneous_push_pop")
    # Every combination of reset/stop/rearm/cancel/strobe/ready is applied with
    # four queued records, a pending capture record and two partial samples.
    for mask in range(64):
        label = f"controls_{mask:02d}"
        reset_arm(label, 0xA0000000 | mask)
        for _ in range(5):
            scan(label)
            add(label)
        for ch in [0, 1]:
            add(label, sample_strobe=1, sample_channel=ch)
        changes = dict(zip(["rst", "stop", "rearm", "queue_cancel", "sample_strobe", "out_ready"],
                           [(mask >> (5 - bit)) & 1 for bit in range(6)]))
        add(label + "_matrix", **changes, sample_channel=2, rearm_tag=0xF0000000 | mask)
        drain(label)
        add(label, rearm=1, rearm_tag=0xC0000000 | mask)
        scan(label, ready=1)
        drain(label, 4)
    rng = random.Random(0x39C0FFEE)
    reset_arm("seeded_mix", 0xD15CA4D0)
    channel = 0
    for _ in range(640):
        if rng.random() < .08:
            channel = rng.randrange(4)
        strobe = int(rng.random() < .87)
        add("seeded_mix", rst=int(rng.random() < .004), stop=int(rng.random() < .012),
            rearm=int(rng.random() < .025), queue_cancel=int(rng.random() < .04),
            sample_strobe=strobe, sample_channel=channel, out_ready=int(rng.random() < .36),
            rearm_tag=rng.getrandbits(32))
        if strobe:
            channel = (channel + 1) % 4
    reset_arm("final_fresh_recovery", 0x76543210)
    scan("final_fresh_recovery", ready=1)
    drain("final_fresh_recovery")
    return vectors


class RecordModel:
    """Public transaction model: channel tuples, a pending record and a FIFO list.

    Bank copies exist only to check invalid/stale public data pins. They are not
    cleared by queue reset/cancel. The queue list independently checks live order.
    The original published TB model informed packing and pre-edge handshakes;
    its stop|rearm cancellation convention is explicitly NOT reused here.
    """
    def __init__(self):
        self.bank = [None] * 4
        self.queue = []
        self.head = self.tail = 0
        self.qstats = [0, 0, 0]  # accepted, retired, aborted
        self.coverage = Counter()
        self.matrix = set()
        self.dispositions = Counter()
        self.delivered = []
        self.reset_capture(False, 0)

    def reset_capture(self, armed, tag):
        self.armed, self.tag = int(armed), tag
        self.partial = []
        self.partial_first = self.sequence = 0
        self.exhausted = self.order_event = self.overrun_event = self.exhaust_event = 0
        self.slot = ZERO_RECORD
        self.slot_valid = False
        self.cstats = [0] * 6  # events, scans, retired, discarded, order errors, overruns

    @staticmethod
    def sat(value, inc=1):
        return min(MAX32, value + inc)

    def controls(self, v):
        return dict(zip([name for name, _ in CONTROL_OUTPUTS], [
            int(bool(self.queue) and not v["rst"] and not v["queue_cancel"]),
            self.armed, len(self.partial), self.sequence, self.exhausted,
            self.order_event, self.overrun_event, self.exhaust_event,
            *self.cstats, len(self.queue), *self.qstats,
        ]))

    def output(self, v):
        ctl = f"{pack(self.controls(v), CONTROL_OUTPUTS):083x}"
        record = self.bank[self.head]
        payload = "x" * 112 if record is None else f"{pack(dict(zip([n for n, _ in RECORD_OUTPUTS], record)), RECORD_OUTPUTS):0112x}"
        return ctl + payload

    def step(self, v, label):
        cov = self.coverage
        old_queue = list(self.queue)
        old_slot_valid, old_slot = self.slot_valid, self.slot
        old_partial = list(self.partial)
        old_sequence = self.sequence
        old_tag = self.tag
        if label.endswith("_matrix"):
            names = ["rst", "stop", "rearm", "queue_cancel", "sample_strobe", "out_ready"]
            self.matrix.add(tuple(v[n] for n in names))
        if len(self.queue) == 4:
            cov["queue_full_cycles"] += 1
        if self.queue and not v["out_ready"] and not v["rst"] and not v["queue_cancel"]:
            cov["queue_stall_cycles"] += 1
        capture_valid = old_slot_valid and not (v["rst"] or v["stop"] or v["rearm"])
        queue_ready = not v["rst"] and not v["queue_cancel"] and len(self.queue) < 4
        push = capture_valid and queue_ready
        pop = bool(self.queue) and not v["rst"] and not v["queue_cancel"] and v["out_ready"]
        if v["rst"]:
            cov["reset_with_queued"] += int(bool(self.queue))
            cov["reset_with_pending"] += int(old_slot_valid)
            cov["reset_with_partial"] += int(bool(old_partial))
            self.dispositions["queue_reset_records"] += len(self.queue)
            self.queue.clear()
            self.head = self.tail = 0
            self.qstats = [0, 0, 0]
        elif v["queue_cancel"]:
            cov["cancel_with_pending"] += int(old_slot_valid and not v["stop"] and not v["rearm"])
            cov["cancel_with_partial_sample"] += int(bool(old_partial) and v["sample_strobe"] and not v["stop"] and not v["rearm"])
            self.dispositions["queue_cancel_records"] += len(self.queue)
            self.qstats[2] = self.sat(self.qstats[2], len(self.queue))
            self.queue.clear()
            self.head = self.tail = 0
        else:
            if pop:
                record = self.queue.pop(0)
                assert record == self.bank[self.head], "FIFO list/bank order differs"
                self.delivered.append(list(record))
                self.head = (self.head + 1) % 4
                self.qstats[1] = self.sat(self.qstats[1])
                self.dispositions["queue_delivered_records"] += 1
                cov["queue_pop"] += 1
                cov["old_tag_delivered_after_rearm"] += int(record[-1] != old_tag and self.armed)
            if push:
                self.bank[self.tail] = old_slot
                self.queue.append(old_slot)
                self.tail = (self.tail + 1) % 4
                self.qstats[0] = self.sat(self.qstats[0])
                self.dispositions["queue_accepted_records"] += 1
                cov["queue_push"] += 1
            cov["simultaneous_push_pop"] += int(push and pop)
            cov["full_pop_without_same_edge_push"] += int(len(old_queue) == 4 and pop and not push and capture_valid)
        if old_queue and not v["out_ready"] and not v["queue_cancel"] and not v["rst"]:
            if v["stop"]:
                assert self.queue == old_queue
                cov["stop_preserves_queue"] += 1
            elif v["rearm"]:
                assert self.queue == old_queue
                cov["rearm_preserves_queue"] += 1
        if v["rst"] or v["stop"] or v["rearm"]:
            self.dispositions["capture_control_pending_records"] += int(old_slot_valid)
            self.dispositions["capture_control_partial_samples"] += len(old_partial)
            self.reset_capture(bool(v["rearm"] and not v["rst"] and not v["stop"]),
                               v["rearm_tag"] if v["rearm"] and not v["rst"] and not v["stop"] else 0)
            return
        self.order_event = self.overrun_event = self.exhaust_event = 0
        if push:
            self.slot_valid = False
            self.cstats[2] = self.sat(self.cstats[2])
        if not self.armed or not v["sample_strobe"]:
            return
        cov[f"sample_channel_{v['sample_channel']}"] += 1
        self.cstats[0] = self.sat(self.cstats[0])
        ch = v["sample_channel"]
        sample = (v["sample_data"], v["sample_tick"], v["sample_quality"])
        discard = 0
        complete = None
        if ch != len(self.partial):
            self.order_event = 1
            cov["order_error"] += 1
            discard = len(self.partial) + int(ch != 0)
            cov["partial_restart"] += int(bool(self.partial) and ch == 0)
            self.partial = []
            self.partial_first = 0
        if ch == 0:
            self.partial = [sample]
            self.partial_first = old_sequence
        elif not self.order_event:
            self.partial.append(sample)
            if ch == 3:
                lanes = self.partial
                complete = tuple(sum(lane[field] << (width * i) for i, lane in enumerate(lanes))
                                 for field, width in [(0, 16), (1, 64), (2, 8)])
                complete += (self.partial_first, (self.partial_first + 3) & MAX32, self.tag)
                self.partial = []
                self.partial_first = 0
        if complete is not None:
            cov["complete_scan"] += 1
            self.cstats[1] = self.sat(self.cstats[1])
            if old_slot_valid and not push:
                self.overrun_event = 1
                discard += 4
                cov["capture_overrun"] += 1
                self.dispositions["capture_overrun_records"] += 1
            else:
                self.slot = complete
                self.slot_valid = True
                self.dispositions["capture_completed_records"] += 1
        if old_sequence == MAX32:
            # Defined for completeness; fixed-width simulation never reaches it.
            self.armed = 0
            self.exhausted = self.exhaust_event = 1
            discard += len(self.partial)
            self.partial = []
            self.partial_first = 0
        else:
            self.sequence += 1
        self.cstats[3] = self.sat(self.cstats[3], discard)
        self.cstats[4] = self.sat(self.cstats[4], self.order_event)
        self.cstats[5] = self.sat(self.cstats[5], self.overrun_event)
        self.dispositions["capture_discarded_samples"] += discard


BEGIN = re.compile(r"SCAN_BEGIN cycles=([1-9][0-9]*) ports=24 bits=780")
TRACE = re.compile(r"SCAN_TRACE cycle=([0-9]+) phase=(pre|post) time=([0-9]+) inputs=([0-9a-f]{32}) dut=([0-9a-fx]{195}) ref=([0-9a-fx]{195})", re.I)
DONE = re.compile(r"SCAN_DONE cycles=([1-9][0-9]*) checks=([1-9][0-9]*) mismatch=0")
FINAL = "SCAN_FINAL result=PASS"


def parse_trace(raw: bytes, plan, *, finish_source=None):
    # A transcript cannot declare its own provenance. The default is the
    # retained actual attempt-03 compile input; a future run must explicitly
    # pass its own compile-input snapshot. Both it and the current TB must
    # have these independently pinned bytes. This requires local snapshots.
    tb_relative = "tests/rtl/acquisition/tb_buffered_scan_capture.sv"
    tb_sha256 = "53f4949732af0b913d28b0118c91f285510d020e466cb4a2f63bbab4ba5cf057"
    source = Path(finish_source) if finish_source is not None else AUTHOR / "attempt-03/inputs" / tb_relative
    try:
        source_bytes = source.read_bytes()
        current_tb_bytes = (ROOT / tb_relative).read_bytes()
    except OSError as exc:
        raise ValueError("declared pinned finish source is unavailable") from exc
    if sha(source_bytes) != tb_sha256 or sha(current_tb_bytes) != tb_sha256:
        raise ValueError("declared/current finish source differs from pinned TB bytes")
    finish_lines = [n for n, line in enumerate(source_bytes.decode("utf-8").splitlines(), 1)
                    if re.fullmatch(r"\s*\$finish;\s*", line)]
    if len(finish_lines) != 1:
        raise ValueError("pinned TB must have one declared finish statement")
    expected_source = source.resolve().as_posix()
    expected_line = finish_lines[0]
    expected_instance = "/tb_buffered_scan_capture"
    expected_finish_time = 16 + 10 * (len(plan) - 1)
    text = raw.decode("utf-8", errors="strict")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u2028\u2029]", text):
        raise ValueError("forbidden control/separator in transcript")
    crlf = "\r\n" in text
    without_crlf = text.replace("\r\n", "")
    if "\r" in without_crlf or (crlf and "\n" in without_crlf):
        raise ValueError("malformed/mixed transcript line endings")
    text = text.replace("\r\n", "\n")
    if not text.endswith("\n"):
        raise ValueError("truncated non-newline-terminated transcript")
    model = RecordModel()
    state, seen = "before", 0
    started = ended = None
    wall_pattern = r"([0-9]{2}:[0-9]{2}:[0-9]{2} on [A-Z][a-z]{2} [0-9]{1,2},[0-9]{4})"
    footer_states = {"final", "finish_note", "finish_time", "break", "stopped", "end"}
    for line_number, raw_line in enumerate(text.split("\n")[:-1], 1):
        line = raw_line[2:] if raw_line.startswith("# ") else raw_line
        if re.search(r"\*\* (?:Error|Fatal|Warning)|SCAN_MISMATCH|SCAN_BAD_|SCAN_SHORT_|SCAN_EXTRA_", line):
            raise ValueError(f"vendor/TB error on line {line_number}: {line}")
        if state == "complete":
            raise ValueError("trailing data or duplicate simulator footer")
        if state in footer_states:
            if not raw_line.startswith("# "):
                raise ValueError("malformed simulator footer prefix")
            if state == "final":
                match = re.fullmatch(r"\*\* Note: \$finish    : (.+)\(([1-9][0-9]*)\)", line)
                if (match is None or match[1].replace("\\", "/") != expected_source
                        or int(match[2]) != expected_line):
                    raise ValueError("missing/mismatched pinned finish source/line")
                state = "finish_note"
            elif state == "finish_note":
                match = re.fullmatch(r"   Time: ([0-9]+) ns  Iteration: 0  Instance: (/.+)", line)
                if (match is None or int(match[1]) != expected_finish_time
                        or match[2] != expected_instance):
                    raise ValueError("missing/conflicting finish time/iteration/instance")
                state = "finish_time"
            elif state in {"finish_time", "break"}:
                prefix = "Break" if state == "finish_time" else "Stopped"
                match = re.fullmatch(prefix + r" at (.+) line ([1-9][0-9]*)", line)
                if (match is None or match[1].replace("\\", "/") != expected_source
                        or int(match[2]) != expected_line):
                    raise ValueError("missing/conflicting " + prefix.lower() + " source/line")
                state = "break" if state == "finish_time" else "stopped"
            elif state == "stopped":
                match = re.fullmatch(r"End time: " + wall_pattern + r", Elapsed time: ([0-9]+):([0-9]{2}):([0-9]{2})", line)
                if match is None or int(match[3]) >= 60 or int(match[4]) >= 60:
                    raise ValueError("missing/malformed simulator end marker")
                ended = datetime.strptime(match[1], "%H:%M:%S on %b %d,%Y")
                elapsed = int(match[2]) * 3600 + int(match[3]) * 60 + int(match[4])
                if started is None or (ended - started).total_seconds() != elapsed:
                    raise ValueError("simulator start/end/elapsed times conflict")
                state = "end"
            elif state == "end":
                if line != "Errors: 0, Warnings: 0":
                    raise ValueError("missing/nonzero/malformed simulator error/warning summary")
                state = "complete"
            continue
        if "Start time:" in line:
            match = re.fullmatch(r"Start time: " + wall_pattern, line)
            if state != "before" or started is not None or match is None or not raw_line.startswith("# "):
                raise ValueError("missing/malformed/duplicate/out-of-order simulator start marker")
            started = datetime.strptime(match[1], "%H:%M:%S on %b %d,%Y")
            continue
        if any(marker in line for marker in ["$finish", "Break at ", "Stopped at ", "Time:", "Instance:", "End time:", "Errors:", "Warnings:"]):
            raise ValueError("unexpected/contradictory simulator terminal marker")
        if "SCAN_" not in line:
            if state != "before":
                raise ValueError("unexpected data within trace/terminal sequence")
            continue
        if BEGIN.fullmatch(line):
            if state != "before" or started is None or int(BEGIN.fullmatch(line)[1]) != len(plan):
                raise ValueError("duplicate/out-of-order/inconsistent begin")
            state = "tracing"
        elif (match := TRACE.fullmatch(line)) is not None:
            if state != "tracing" or seen >= 2 * len(plan):
                raise ValueError("unexpected/duplicate trace")
            index, phase = seen // 2, "pre" if seen % 2 == 0 else "post"
            vector = plan[index]
            if (int(match[1]), match[2], int(match[3]), match[4].lower()) != (
                    index, phase, 11 + 10 * index + (5 if phase == "post" else 0), vector.encoded):
                raise ValueError(f"trace order/time/input mismatch at record {seen}")
            if phase == "post":
                model.step(vector.values, vector.label)
            expected = model.output(vector.values)
            if match[5].lower() != expected or match[6].lower() != expected:
                raise ValueError(f"public outputs differ from transaction model at cycle {index} {phase}; expected={expected}, dut={match[5]}, ref={match[6]}")
            seen += 1
        elif (match := DONE.fullmatch(line)) is not None:
            if state != "tracing" or seen != 2 * len(plan):
                raise ValueError("duplicate/early/incomplete done")
            if int(match[1]) != seen // 2 or int(match[2]) != seen:
                raise ValueError("done statistics conflict with raw trace")
            state = "done"
        elif line == FINAL:
            if state != "done":
                raise ValueError("duplicate/out-of-order final")
            state = "final"
        else:
            raise ValueError(f"malformed/reserved marker on line {line_number}: {line}")
    if state != "complete":
        raise ValueError("missing completion or simulator termination; transcript truncated")
    if len(model.matrix) != 64:
        raise ValueError("control matrix incomplete")
    required = [f"sample_channel_{n}" for n in range(4)] + [
        "order_error", "partial_restart", "capture_overrun", "complete_scan", "queue_push",
        "queue_pop", "queue_full_cycles", "queue_stall_cycles", "simultaneous_push_pop",
        "full_pop_without_same_edge_push", "cancel_with_pending", "cancel_with_partial_sample",
        "stop_preserves_queue", "rearm_preserves_queue", "old_tag_delivered_after_rearm",
        "reset_with_queued", "reset_with_pending", "reset_with_partial",
    ]
    if any(model.coverage[name] == 0 for name in required):
        raise ValueError(f"missing exercised coverage: {[n for n in required if not model.coverage[n]]}")
    accepted = model.dispositions["queue_accepted_records"]
    disposed = sum(model.dispositions[n] for n in ["queue_delivered_records", "queue_cancel_records", "queue_reset_records"])
    if accepted != disposed + len(model.queue):
        raise ValueError("queue transaction disposition mismatch")
    completed = model.dispositions["capture_completed_records"]
    if completed != accepted + model.dispositions["capture_control_pending_records"] + int(model.slot_valid):
        raise ValueError("pending capture record disposition mismatch")
    return {
        "cycles": seen // 2, "trace_records": seen, "public_ports_each_record": 24,
        "public_output_bits_each_record": 780, "all_public_output_comparisons": seen * 24,
        "control_combinations": len(model.matrix), "coverage": dict(model.coverage),
        "dispositions": dict(model.dispositions), "final_public_counters": model.controls(plan[-1].values),
        "delivered_record_count": len(model.delivered),
        "delivered_records_sha256": sha(json.dumps(model.delivered, separators=(",", ":")).encode()),
        "fixed_32bit_sequence_exhaustion": "not_reached_not_forced",
        "model_scope": "public transaction, order, disposition, diagnostics and counters; reused direct RTL chain checks wiring only",
        "simulator_termination": {"qualified": True, "finish_source": expected_source,
            "finish_source_sha256": tb_sha256, "finish_line": expected_line,
            "finish_time_ns": expected_finish_time, "finish_instance": expected_instance,
            "start_time": started.isoformat(), "end_time": ended.isoformat(),
            "errors": 0, "warnings": 0, "line_endings": "CRLF" if crlf else "LF"},
    }


def negative_controls(raw, plan, out, *, finish_source=None):
    """Mutate the actual saved successful vendor stdout, never synthetic passes."""
    lines = raw.decode("utf-8").splitlines(keepends=True)
    positions = {kind: next(i for i, line in enumerate(lines) if line.startswith("# SCAN_" + kind))
                 for kind in ["BEGIN", "TRACE", "DONE", "FINAL"]}
    mutations = {}
    def change(name, fn):
        altered = list(lines)
        fn(altered)
        mutations[name] = "".join(altered).encode()
    for kind in ["BEGIN", "DONE", "FINAL"]:
        i = positions[kind]
        change("duplicate_" + kind.lower(), lambda ls, i=i: ls.insert(i, ls[i]))
        change("prefix_" + kind.lower(), lambda ls, i=i: ls.__setitem__(i, "prefix " + ls[i]))
        change("suffix_" + kind.lower(), lambda ls, i=i: ls.__setitem__(i, ls[i].rstrip("\r\n") + " suffix\n"))
        change("missing_" + kind.lower(), lambda ls, i=i: ls.pop(i))
    i = positions["TRACE"]
    change("missing_trace", lambda ls: ls.pop(i))
    change("duplicate_trace", lambda ls: ls.insert(i, ls[i]))
    change("trace_order", lambda ls: ls.__setitem__(i, ls[i].replace("cycle=0", "cycle=1")))
    change("trace_time", lambda ls: ls.__setitem__(i, ls[i].replace("time=11", "time=12")))
    change("trace_input", lambda ls: ls.__setitem__(i, re.sub(r"inputs=.", "inputs=f", ls[i])))
    change("trace_dut", lambda ls: ls.__setitem__(i, re.sub(r"dut=.", "dut=f", ls[i])))
    change("trace_reference", lambda ls: ls.__setitem__(i, re.sub(r"ref=.", "ref=f", ls[i])))
    change("trace_unknown_control", lambda ls: ls.__setitem__(i, re.sub(r"dut=.", "dut=x", ls[i])))
    change("trace_invalid_hex", lambda ls: ls.__setitem__(i, re.sub(r"dut=.", "dut=z", ls[i])))
    i = positions["DONE"]
    change("conflicting_done_cycles", lambda ls: ls.__setitem__(i, re.sub(r"cycles=\d+", "cycles=1", ls[i])))
    change("conflicting_done_checks", lambda ls: ls.__setitem__(i, re.sub(r"checks=\d+", "checks=1", ls[i])))
    change("conflicting_done_mismatch", lambda ls: ls.__setitem__(i, ls[i].replace("mismatch=0", "mismatch=1")))
    mutations["truncated_bytes"] = raw[:-7]
    mutations["truncated_during_trace"] = "".join(lines[:positions["TRACE"] + 10]).encode()
    results = []
    for name, data in mutations.items():
        path = out / (name + ".stdout.bin")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        try:
            parse_trace(data, plan, finish_source=finish_source)
        except (ValueError, AssertionError) as exc:
            results.append(dict(name=name, rejected=True, error=str(exc), sha256=sha(data)))
        else:
            results.append(dict(name=name, rejected=False, sha256=sha(data)))
    save_json(out / "RESULT.json", results)
    if not all(row["rejected"] for row in results):
        raise ValueError("parser admitted a negative control")
    return {"fixtures": len(results), "rejected": len(results), "derivation": "mutations of saved actual vsim stdout"}


class Commands:
    def __init__(self, out):
        self.out, self.records = out, []

    def run(self, label, argv, cwd, timeout=60):
        directory = self.out / "commands"
        directory.mkdir(exist_ok=True)
        stem = f"{len(self.records) + 1:02d}-{label}"
        stdout, stderr = directory / (stem + ".stdout.bin"), directory / (stem + ".stderr.bin")
        record = dict(label=label, argv=[str(a) for a in argv], cwd=str(cwd),
                      started_utc=datetime.now(timezone.utc).isoformat(), hidden=os.name == "nt",
                      timeout_seconds=timeout, stdout=str(stdout.relative_to(self.out)),
                      stderr=str(stderr.relative_to(self.out)))
        self.records.append(record)
        si = None
        flags = 0
        if os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            flags = subprocess.CREATE_NO_WINDOW
        with stdout.open("xb") as output, stderr.open("xb") as error:
            proc = subprocess.Popen(record["argv"], cwd=cwd, stdin=subprocess.DEVNULL,
                                    stdout=output, stderr=error, startupinfo=si, creationflags=flags)
            record["pid"] = proc.pid
            try:
                record["exit_code"] = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                record["exit_code"] = proc.wait()
                record["timed_out"] = True
        record.update(finished_utc=datetime.now(timezone.utc).isoformat(),
                      stdout_sha256=sha(stdout.read_bytes()), stderr_sha256=sha(stderr.read_bytes()))
        save_json(directory / (stem + ".json"), record)
        if record["exit_code"] != 0 or record.get("timed_out"):
            raise RuntimeError(f"{label} failed: exit {record['exit_code']}; inspect {stem}")
        return stdout.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=AUTHOR / "attempt-01")
    args = parser.parse_args()
    out = guarded_output(args.out)
    out.mkdir(parents=True, exist_ok=False)
    commands = Commands(out)
    result = dict(schema="deepeye.buffered-scan.author.v1", task="DEEPEYE-IMPLEMENTATION-20261014/v1",
                  work_id="B-BUFFERED-SCAN-CAPTURE-20261024-39-v1",
                  operation_id="B-DEEPEYE-BUFFERED-SCAN-CAPTURE-20261024-39",
                  canonical_agent_id=AGENT, job_id=JOB, base_commit=BASE,
                  started_utc=datetime.now(timezone.utc).isoformat(),
                  command_argv=sys.argv, python_executable=sys.executable,
                  python_version=sys.version, platform=platform.platform(), pid=os.getpid(),
                  model_authority="bounded implementation; main retains design/evaluation/acceptance",
                  requirements_ids=[f"H{n:02d}" for n in range(1, 16)],
                  requirements_sha256=CONTRACT_HASH, frozen_design="1011259415a0916054eb580687612580bc1e5f09",
                  formal_cards={f"card{n:02d}": "not_run" for n in range(1, 30)},
                  status="running", claims={"simulation": "pending", "synthesis": "not_run",
                                            "implementation": "not_run", "board": "not_run"})
    before = {}
    try:
        all_sources = {rel: ROOT / rel for rel in (*PINS, *OWN_SOURCES)}
        all_sources["MAIN_SPEC.md"] = SPEC
        for rel, path in all_sources.items():
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"missing/symlink input: {path}")
            data = path.read_bytes()
            before[rel] = sha(data)
            snapshot = out / "inputs" / rel
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(data)
        save_json(out / "source_pins_before.json", before)
        for rel, pin in PINS.items():
            if before[rel] != pin:
                raise ValueError(f"protected source changed: {rel}")
            blob = commands.run("pin-" + Path(rel).stem,
                                ["git", "show", BASE + ":competition/deepeye/" + rel], WORKTREE)
            if sha(blob) != pin:
                raise ValueError(f"base Git blob pin differs: {rel}")
        if before["MAIN_SPEC.md"] != SPEC_HASH:
            raise ValueError("main specification hash differs")
        for extension in ["json", "md"]:
            data = commands.run("contract-" + extension, ["git", "show", CONTRACT_COMMIT
                                + ":docs/competition/deepeye-2026/immutable_scope." + extension], WORKTREE)
            (out / "inputs" / ("immutable_scope." + extension)).write_bytes(data)
            if extension == "json":
                contract = json.loads(data)
                digest = sha(json.dumps(contract["requirements"], ensure_ascii=False,
                                        sort_keys=True, separators=(",", ":")).encode())
                if digest != CONTRACT_HASH or len(contract["requirements"]) != 15:
                    raise ValueError("fixed human contract requirements hash differs")
        commands.run("git-version", ["git", "--version"], WORKTREE)
        result["actual_head_at_start"] = commands.run("head", ["git", "rev-parse", "HEAD"], WORKTREE).decode().strip()
        plan = make_plan()
        save_json(out / "stimulus.json", [dict(label=v.label, **v.values) for v in plan])
        stimulus = out / "stimulus.hex"
        stimulus.write_text("".join(v.encoded + "\n" for v in plan), encoding="ascii")
        save_json(out / "public_trace_layout.json", {"inputs_msb_first": INPUTS,
                  "outputs_msb_first": CONTROL_OUTPUTS + RECORD_OUTPUTS,
                  "clock": "pre=0 at 11+10*cycle ns; post=1 at 16+10*cycle ns",
                  "unknown_data": "RAM is not reset; x only where the untouched bank has no prior write"})
        bin_dir = Path("D:/modelsim1/win64")
        result["tool_executable_sha256"] = {}
        for tool in ["vlib", "vlog", "vsim"]:
            exe = bin_dir / (tool + ".exe")
            result["tool_executable_sha256"][tool] = sha(exe.read_bytes())
            if tool != "vlib":
                commands.run(tool + "-version", [exe, "-version"], out)
        # This installation's vlib rejects -version; its failed query is kept
        # in attempt-01. Record actual executable metadata without inventing a
        # vlib banner from the version of another executable.
        commands.run("vendor-file-versions", ["powershell.exe", "-NoLogo", "-NoProfile",
                     "-NonInteractive", "-Command",
                     "Get-Item -LiteralPath 'D:/modelsim1/win64/vlib.exe','D:/modelsim1/win64/vlog.exe','D:/modelsim1/win64/vsim.exe' | ForEach-Object { [PSCustomObject]@{Path=$_.FullName;FileVersion=$_.VersionInfo.FileVersion;ProductVersion=$_.VersionInfo.ProductVersion} } | ConvertTo-Json"], out)
        library = out / "work"
        commands.run("vlib", [bin_dir / "vlib.exe", library], out)
        compiled = [out / "inputs" / rel for rel in [
            "fpga/acquisition/deepeye_sample_scan_capture.sv",
            "fpga/acquisition/deepeye_raw_scan_queue.sv",
            "fpga/acquisition/deepeye_buffered_scan_capture.sv",
            "tests/rtl/acquisition/tb_buffered_scan_capture.sv",
        ]]
        compiled_output = commands.run("vlog", [bin_dir / "vlog.exe", "-sv", "-work", library, *compiled], out)
        if re.search(rb"\*\* (?:Error|Fatal|Warning)", compiled_output):
            raise ValueError("unexpected compiler diagnostic")
        do_file = out / "run.do"
        do_file.write_text("onerror {quit -code 2}\nrun -all\nquit -code 0\n", encoding="ascii")
        raw = commands.run("vsim", [bin_dir / "vsim.exe", "-c", "-t", "1ns", "-onfinish", "stop",
                           "-lib", "work", "tb_buffered_scan_capture", "+STIMULUS=" + stimulus.as_posix(),
                           "+CYCLES=" + str(len(plan)), "-do", "do {" + do_file.as_posix() + "}"], out)
        # Parsing is performed only against the exact saved stdout bytes.
        finish_source = out / "inputs/tests/rtl/acquisition/tb_buffered_scan_capture.sv"
        result["checks"] = parse_trace(raw, plan, finish_source=finish_source)
        save_json(out / "trace_checks.json", result["checks"])
        result["parser_negative_controls"] = negative_controls(raw, plan, out / "parser-negative-controls", finish_source=finish_source)
        guard_checks = []
        for label, path in [("preexisting_output", out), ("owned_input_alias", ROOT / OWN_SOURCES[0]),
                            ("protected_input_alias", ROOT / next(iter(PINS))), ("outside_owned_root", AUTHOR.parent / "invalid")]:
            try:
                guarded_output(path)
            except (ValueError, FileExistsError) as exc:
                guard_checks.append(dict(label=label, rejected=True, error=str(exc)))
            else:
                raise ValueError("output guard admitted " + label)
        save_json(out / "output_guard_checks.json", guard_checks)
        result["output_guard_checks"] = guard_checks
        result["claims"]["simulation"] = "bounded_author_checks_passed"
        result["status"] = "bounded_author_checks_passed"
    except Exception as exc:
        result.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        (out / "exception.stderr.txt").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        after = {rel: sha(path.read_bytes()) for rel, path in
                 [(rel, ROOT / rel) for rel in (*PINS, *OWN_SOURCES)] + [("MAIN_SPEC.md", SPEC)] if path.is_file()}
        save_json(out / "source_pins_after.json", after)
        result["source_pins_before"] = before
        result["source_pins_after"] = after
        result["protected_and_source_inputs_unchanged"] = bool(before) and before == after
        if not result["protected_and_source_inputs_unchanged"]:
            result["status"] = "failed"
            result["source_mutation_error"] = "input pin changed during execution"
        result["commands"] = commands.records
        result["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save_json(out / "RESULT.json", result)
        artifacts = {str(p.relative_to(out)).replace("\\", "/"): sha(p.read_bytes())
                     for p in sorted(out.rglob("*")) if p.is_file()}
        save_json(out / "artifact_sha256.json", artifacts)
    print(json.dumps({"status": result["status"], "evidence": str(out), "error": result.get("error")}, ensure_ascii=False))
    return 0 if result["status"] == "bounded_author_checks_passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
