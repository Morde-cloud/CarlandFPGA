"""B52 bounded ModelSim fixture and independent public-event checker.

No product imports, old scorers, internal DUT references, board access or Git.
Payload and wire goldens are the disclosed frozen main49 vectors. The Python
checker independently decodes the logged public TX/line transitions, calculates
CRC, checks receiver fields/retirement and replays public status accounting.
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback

TASK = "DEEPEYE-IMPLEMENTATION-20261014"
WORK = "B-TRACE-UART-LOOPBACK-20261024-52-v1"
OP = "B-DEEPEYE-TRACE-UART-LOOPBACK-20261024-52"
JOB = "child-339924e78417402e98f6e80c324363f9"
AGENT = "01a16e87-3891-7a12-8a9d-9e52aa6d18bc"
CONTRACT = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
VECTOR_SHA = "a5a4497eb12012530c6a3296ca5f7855c4e5f8617eba661ca3f137e713c6c5bd"
FROZEN = "1011259415a0916054eb580687612580bc1e5f09"
PINS = {
    "fpga/codec/deepeye_trace_uart_candidate.sv": "8aec895f3f3d71254d63cc6b4e73dd866cb81f2c42b24a54e11b2b3dd52f08b0",
    "fpga/codec/deepeye_trace_frame_candidate.sv": "ceff0930c2403eabe73bdd8a8cfe7bbb868ca33029d026a6a240c8d50a06a5cc",
    "fpga/codec/deepeye_trace_payload_timing_candidate.sv": "0d5ba11fe199708f8376c718bbf3484431adc8dd6e847666451b1b5e873cec7b",
    "fpga/codec/deepeye_block_encoder.sv": "4cb79428ef89096742e293516c4696caf985048d8185f531fe92eaa485c8d532",
    "fpga/transport/deepeye_wire_serializer.sv": "efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885",
    "fpga/transport/deepeye_crc16_byte.sv": "8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f",
    "fpga/transport/deepeye_uart_tx.sv": "5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47",
    "fpga/transport/deepeye_uart_wire_rx.sv": "b6abab4e1be54ee61bd45e4d7adfcfea8db39f7574d3ce2ae7b7030ff74ade2c",
    "fpga/transport/deepeye_uart_rx.sv": "935f5d02008535fd5da75b7dc80696d14b03bd54d85f8b52fbf12c1e0504f08f",
    "fpga/transport/deepeye_wire_parser.sv": "7806c5d08785b96eae3708d9fd6d6002ef82faa4416a1f7244da73bece552649",
}
TB = "tests/rtl/transport/tb_trace_uart_loopback.sv"
RUNNER = "tools/transport/run_trace_uart_loopback.py"
DOC = "fpga/transport/trace_uart_loopback_fixture.md"
AUTHOR = "evidence/transport/trace-uart-loopback-20261024-52/author"
VECTORS = "evidence/codec/trace-uart-candidate-20261024-49/main/preinspection-01/main_vectors.json"
PROFILES = [(16, 1, 1, 0), (33, 2, 0, 0), (100, 3, 0, 0), (100000000, 9600, 0, 1)]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf8")


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def crc16(data):
    crc = 65535
    for byte in data:
        for shift in range(7, -1, -1):
            outgoing = (crc >> 15) ^ ((byte >> shift) & 1)
            crc = (crc << 1) & 65535
            if outgoing:
                crc ^= 0x1021
    return crc


def default_case():
    # Explicit extra stimulus: quality-invalid single observation, no samples.
    # 21 metadata bytes + 14 framing bytes is the shortest legal frame here.
    cfg = dict(count=1, e=0, session=0x78563412, channel=2, index=17,
               tick=100000, index_stride=0, tick_stride=0, valid=0,
               saturated=0, held=0, source_fault=0, source_tick=0)
    payload = [1, 8, 2, 1, 0] + list(cfg["session"].to_bytes(4, "little"))
    payload += list(cfg["index"].to_bytes(4, "little")) + list(cfg["tick"].to_bytes(8, "little"))
    wire = [165, 90, 3, 7, 21, 0x52, 0x24, 0x10] + list((100000).to_bytes(4, "little")) + payload
    wire += list(crc16(wire[2:]).to_bytes(2, "little"))
    require(len(wire) == 35, "default frame construction")
    return dict(id=65534, name="explicit-default-invalid-quality-n1", cfg=cfg, samples=[],
                bad_last=None, expected=dict(error=0, tick=100000, bytes=payload),
                epoch=0x52, seq=0x1024, frame=wire, result_bytes=35)


def vector_text(cases):
    lines = []
    for c in cases:
        q = c["cfg"]
        fields = [c["id"]] + [q[k] for k in ("count", "e", "session", "channel", "index", "tick", "index_stride", "tick_stride", "valid", "saturated", "held", "source_fault", "source_tick")]
        fields += [c["epoch"], c["seq"], c["bad_last"] if c["bad_last"] is not None else 0xffffffff,
                   c["expected"]["error"], len(c["frame"]), len(c["samples"])]
        fields += c["samples"] + c["frame"]
        lines.append(" ".join(f"{v:x}" for v in fields))
    return ("\n".join(lines) + "\n").encode("ascii")


def run_process(argv, cwd: Path, prefix: Path, timeout=240):
    # Hidden console processes only. Every actual launch has intent, PID and exit.
    prefix.parent.mkdir(parents=True, exist_ok=True)
    info = dict(argv=[str(s) for s in argv], cwd=str(cwd), parent_pid=os.getpid(),
                started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), timeout_seconds=timeout)
    write_json(prefix.with_suffix(".intent.json"), info)
    start = time.monotonic()
    with prefix.with_suffix(".stdout.bin").open("wb") as out, prefix.with_suffix(".stderr.bin").open("wb") as err:
        proc = subprocess.Popen(info["argv"], cwd=cwd, stdout=out, stderr=err,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        info["pid"] = proc.pid
        write_json(prefix.with_suffix(".started.json"), info)
        try:
            info["exit_code"] = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            info["exit_code"] = proc.wait()
            info["timed_out"] = True
    info["duration_seconds"] = time.monotonic() - start
    info["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    for stream in ("stdout", "stderr"):
        p = prefix.with_suffix(f".{stream}.bin")
        info[stream] = dict(path=str(p), bytes=p.stat().st_size, sha256=digest(p.read_bytes()))
    write_json(prefix.with_suffix(".process.json"), info)
    return info


def clean_text(raw):
    require(not any(v < 32 and v not in (10, 13) for v in raw) and 127 not in raw,
            "control byte in saved log")
    require(b"\r" not in raw.replace(b"\r\n", b""), "lone CR")
    text = raw.decode("utf8")
    require(text.endswith("\n"), "truncated final line")
    return text.replace("\r\n", "\n").splitlines()


def check_transcript(raw, clock, baud, binding, tb_path, tb_line, runs, cycles, os_exit):
    require(os_exit == 0, "OS exit nonzero")
    lines = clean_text(raw)
    error_footers = [m for line in lines if (m := re.fullmatch(r"# Errors: (\d+), Warnings: (\d+)", line))]
    require(len(error_footers) == 1, "unique anchored ModelSim statistics required")
    require(error_footers[0].groups() == ("0", "0"), "ModelSim errors/warnings even with OS zero")
    patterns = {
        "begin": rf"# TRACE52_BEGIN clock={clock} baud={baud} bind={binding}",
        "done": rf"# TRACE52_DONE clock={clock} baud={baud} runs={runs} cycles={cycles} time_ns=(\d+) bind={binding}",
        "finish": r"# \*\* Note: \$finish\s+: (.+)\((\d+)\)",
        "time": r"#    Time: ([0-9]+(?:\.[0-9]+)?) (ps|ns|us|ms|sec)  Iteration: 1  Instance: /tb_trace_uart_loopback",
        "end": r"# End time: (\d{2}:\d{2}:\d{2} on [A-Z][a-z]{2} \d{1,2},\d{4}), Elapsed time: (\d+):([0-5]\d):([0-5]\d)",
        "stats": r"# Errors: (\d+), Warnings: (\d+)",
    }
    reserved = re.compile(r"TRACE52_|\$finish|Time:|End time:|Errors:|Warnings:")
    found = {}
    for index, line in enumerate(lines):
        if not reserved.search(line):
            continue
        matches = [(k, re.fullmatch(p, line)) for k, p in patterns.items()]
        matches = [(k, m) for k, m in matches if m]
        require(len(matches) == 1, f"unanchored or unknown reserved transcript line: {line[:160]}")
        key, match = matches[0]
        require(key not in found, f"duplicate transcript {key}")
        found[key] = (index, match)
    require(set(found) == set(patterns), "missing transcript marker/footer")
    require([found[k][0] for k in patterns] == sorted(found[k][0] for k in patterns), "transcript order")
    require(found["stats"][0] == len(lines) - 1, "stray transcript footer")
    require([found[k][0] for k in ("finish", "time", "end", "stats")] == list(range(found["finish"][0], len(lines))), "nonconsecutive finish footer")
    require(found["stats"][1].groups() == ("0", "0"), "ModelSim errors/warnings even with OS zero")
    finish = found["finish"][1]
    require(Path(finish[1]).resolve() == tb_path.resolve() and int(finish[2]) == tb_line, "finish file/line binding")
    ns = int(found["done"][1][1])
    require(ns == cycles * 10, "marker time/cycle mismatch")
    timing = found["time"][1]
    scale = dict(ps=Decimal("0.001"), ns=Decimal(1), us=Decimal(1000), ms=Decimal(1000000), sec=Decimal(1000000000))
    require(Decimal(timing[1]) * scale[timing[2]] == ns, "simulator finish time mismatch")
    dt.datetime.strptime(found["end"][1][1], "%H:%M:%S on %b %d,%Y")


# Raw records are deliberately compact; all accepted line shapes are explicit.
N = r"[0-9]+"
I = r"-?[0-9]+"
RAW = {
    "H": rf"H ({N}) ({N}) ([0-9a-f]{{64}})",
    "N": rf"N ({N}) ({N}) ({N}) ({N}) ([0-3]) ({I}) ({I}) ({I})",
    "K": "K " + " ".join([f"({N})"] * 16),
    "C": rf"C ({N}) ({N}) ([0-9a-f]{{2}}) ([0-9a-f]) ([0-9a-f]{{8}}) ([0-9a-f]) ([0-9a-f]{{8}}) ([0-9a-f]{{16}}) ([0-9a-f]{{4}}) ([0-9a-f]{{4}}) ([01]) ([01]) ([01]) ([01]) ([0-9a-f]{{16}}) ([0-9a-f]{{2}}) ([0-9a-f]{{4}})",
    "S": rf"S ({N}) ({N}) ({N}) ([0-9a-f]{{4}}) ([01])",
    "W": rf"W ({N}) ({I}) ([01]) ([01]) ([01]) ([01])",
    "B": rf"B ({N}) ({N}) ({N})",
    "D": rf"D ({N}) ({N}) ({N})",
    "V": rf"V ({N}) ({N}) ([0-9a-f]{{2}}) ([0-9a-f]{{2}}) ([0-9a-f]{{4}}) ([0-9a-f]{{8}}) ({N}) ([0-9a-f]{{64}})",
    "R": rf"R ({N}) ({N}) ([0-9a-f]{{2}}) ([0-9a-f]{{2}}) ([0-9a-f]{{4}}) ([0-9a-f]{{8}}) ({N}) ([0-9a-f]{{64}})",
    "U": rf"U ({N}) ({N}) ([0-7]) ({N})",
    "T": rf"T ({N}) ({N}) ([0-7]) ({N})",
    "E": rf"E ({N}) ({N}) ([0-3])",
    "L": rf"L ({N}) ({N}) ([0-7])",
    "F": rf"F ({N}) ({N}) 12 3 ({N}) ({N})",
    "G": rf"G ({N}) ({I}) ([01]) ([01])",
    "M": rf"M ({N}) ({N})",
    "A": rf"A ({N}) ({N}) ([01]) ([0-4]) ({I}) ([01]) ([01]) ([01])",
    "I": rf"I ({N}) ({N}) 0 0 0 0",
    "Z": "Z " + " ".join([f"({N})"] * 10),
    "Q": "Q " + " ".join([f"({N})"] * 15),
    "END": rf"END ({N}) ([0-9a-f]{{64}})",
}


def check_events(raw, cases, clock, baud, binding, extended, default_only):
    lines = clean_text(raw)
    parsed = []
    for no, line in enumerate(lines, 1):
        key = line.split(" ", 1)[0]
        m = re.fullmatch(RAW.get(key, r"(?!)"), line)
        require(m is not None, f"raw grammar line {no}: {line[:120]}")
        parsed.append((key, m.groups()))
    require(parsed[0] == ("H", (str(clock), str(baud), binding)), "raw source binding")
    require(sum(k == "H" for k, _ in parsed) == 1 and sum(k == "Q" for k, _ in parsed) == 1 and sum(k == "END" for k, _ in parsed) == 1, "raw unique header/stat/footer")
    require(parsed[-2][0] == "Q" and parsed[-1][0] == "END", "raw footer placement")
    summary = list(map(int, parsed[-2][1]))
    cycles = summary[-1]
    require(parsed[-1] == ("END", (str(cycles), binding)), "raw footer binding/cycles")
    runs = []
    wire = []
    previous_cycle = 0
    for key, args in parsed[1:-2]:
        now = int(args[0])
        require(previous_cycle <= now <= cycles, "raw event cycle order")
        previous_cycle = now
        if key == "N":
            require(int(args[1]) == len(runs), "run sequence")
            runs.append(dict(n=list(map(int, args)), events={}))
        if key == "W":
            wire.append(tuple(map(int, args)))
        if len(args) > 1 and int(args[1]) >= 0:
            require(runs and int(args[1]) == len(runs) - 1, "event run identity")
            runs[-1]["events"].setdefault(key, []).append(args)
        else:
            require(key in ("W", "G"), "event before run")
    require(len(runs) == summary[0], "raw run total")
    wire_cycles = [w[0] for w in wire]

    def wire_at(cycle):
        index = bisect.bisect_right(wire_cycles, cycle) - 1
        require(index >= 0, "missing wire prefix")
        return wire[index][2:]

    totals = [0] * 8
    categories = [0] * 5  # normal,error,abort,recovery,corruption
    abort_matrix = set()
    details = []
    for run in runs:
        start, rid, selection, cid, mode, kind, stage, phase = run["n"]
        ev = run["events"]
        c = cases[selection]
        expected = c["expected"]
        frame = c["frame"]
        err = expected["error"]
        require(cid == c["id"] and len(ev.get("C", [])) == 1 and len(ev.get("M", [])) == 1, f"config admission/binding run {rid}")
        cfg = c["cfg"]
        config_values = [cfg[k] for k in ("count", "e", "session", "channel", "index", "tick", "index_stride", "tick_stride", "valid", "saturated", "held", "source_fault", "source_tick")] + [c["epoch"], c["seq"]]
        require([int(s, 16) for s in ev["C"][0][2:]] == config_values, f"config values run {rid}")
        ss = ev.get("S", [])
        for index, s in enumerate(ss):
            require(int(s[2]) == index and index < len(c["samples"]) and int(s[3], 16) == c["samples"][index], "sample values/order")
            last = index == cfg["count"] - 1
            if index == c["bad_last"]:
                last = not last
            require(int(s[4]) == last, "sample last")
        begins = [(int(x[0]), int(x[2])) for x in ev.get("B", [])]
        dones = [(int(x[0]), int(x[2])) for x in ev.get("D", [])]
        require([x[1] for x in begins] == list(range(len(begins))) and [x[1] for x in dones] == list(range(len(dones))), "byte index order")
        byte_cycles = (10 * clock + baud - 1) // baud
        for t, index in dones:
            require(index < len(begins) and t == begins[index][0] + byte_cycles, "byte duration")
        for (t, index), (nxt, _) in zip(begins, begins[1:]):
            require(nxt > t + byte_cycles, "overlapping byte starts")
        a = ev.get("A", [])
        cutoff = int(a[0][0]) + 1 if a else None
        require(len(a) == (mode == 2), "abort uniqueness")

        def expected_wire(t):
            candidates = [(bt, index) for bt, index in begins if bt <= t]
            if not candidates or (cutoff is not None and t >= cutoff):
                return (1, 0, 1, 0)
            bt, index = candidates[-1]
            elapsed = t - bt
            p = sum(elapsed >= (k * clock + baud - 1) // baud for k in range(1, 11))
            require(index < len(frame), "unexpected byte for error")
            bit = 0 if p == 0 else ((frame[index] >> (p - 1)) & 1) if p < 9 else 1
            flip = int(mode == 1 and index == 12 and (4 * clock + baud - 1) // baud <= elapsed < (5 * clock + baud - 1) // baud)
            return bit, int(p < 10), bit ^ flip, flip

        for w in ev.get("W", []):
            require(tuple(map(int, w[2:])) == expected_wire(int(w[0])), f"public wire mismatch run {rid} cycle {w[0]}")
        decoded = []
        received = []
        for bt, index in begins:
            require(index < len(frame), "byte beyond frame")
            end = min(bt + byte_cycles, cutoff - 1) if cutoff is not None else bt + byte_cycles
            points = {bt, end}
            for k in range(1, 11):
                boundary = bt + (k * clock + baud - 1) // baud
                points.update(t for t in (boundary - 1, boundary) if bt <= t <= end)
            for t in points:
                require(wire_at(t) == expected_wire(t), f"missing/stray wire edge run {rid} byte {index} cycle {t}")
            if bt + byte_cycles <= end:
                bits = [wire_at(bt + ((2 * k + 3) * clock + 2 * baud - 1) // (2 * baud)) for k in range(8)]
                decoded.append(sum(w[0] << k for k, w in enumerate(bits)))
                received.append(sum(w[2] << k for k, w in enumerate(bits)))
        require(decoded == frame[:len(decoded)], "independent UART data decode")
        packets = ev.get("V", [])
        retirements = ev.get("R", [])
        for p in packets + retirements:
            fields = [int(s, 16) for s in p[2:6]] + [int(p[6])]
            require(fields == [7, c["epoch"], c["seq"], expected["tick"], len(expected["bytes"])], "RX public fields")
            require(int(p[7], 16).to_bytes(32, "little") == bytes(expected["bytes"]) + bytes(32 - len(expected["bytes"])), "RX payload/zero tail")
        reports = ev.get("T", [])
        offers = ev.get("U", [])
        for report in reports + offers:
            require(list(map(int, report[2:])) == [err, len(frame)], "TX result values")
        require(len(offers) <= 1 and len(packets) <= 1 and len(retirements) <= 1 and len(reports) <= 1, "duplicate result/candidate")
        errors = ev.get("E", [])
        require(not ev.get("L"), "line error")
        krecords = ev.get("K", [])
        tags = {int(k[2]): list(map(int, k[3:])) for k in krecords}
        require(len(tags) == len(krecords) and set(tags) == ({0, 1, 2, 3} if mode == 2 else {0, 3}), "counter snapshot shape")
        if mode == 2:
            categories[2] += 1
            require(selection == 3 and not reports and not errors, "abort fixture scope")
            require(len(ev.get("I", [])) == 1, "immediate mask evidence")
            require(tuple(map(int, a[0][2:5])) == (kind, stage, phase), "abort phase binding")
            if stage == 0:
                require(len(ss) == 1 and not begins, "sample-feed abort location")
            elif stage in (1, 2):
                byte = 0 if stage == 1 else len(frame) - 1
                require(begins[-1][1] == byte and int(a[0][0]) - begins[-1][0] == (phase * clock + baud - 1) // baud + (clock // baud) // 4, "abort byte/bit cycle")
            else:
                require(len(packets) == 1 and len(retirements) == (stage == 4), "pending/already-retired distinction")
            abort_matrix.add((kind, stage, phase))
            stop_cycles = [t + 3 + (19 * clock + 2 * baud - 1) // (2 * baud) for t, _ in begins]
            pre = tags[0][:]
            pre[0] += sum(t < cutoff for t in stop_cycles)
            pre[1] += sum(t + 1 < cutoff for t in stop_cycles)
            pre[6] += sum(t + 1 < cutoff for t in stop_cycles)
            pre[7] += len(packets)
            pre[8] += len(retirements)
            require(tags[1] == pre, f"abort prefix public counters run {rid}: {tags[1]} != {pre}")
            post = tags[1][:]
            if kind == 0:
                post = [0] * 13
            else:
                post[5] += int(a[0][5]) + post[0] - post[1]
                post[12] += int(bool(int(a[0][6]) or int(a[0][7])))
            require(tags[2] == post and tags[3] == post, "reset/cancel active-edge accounting")
        else:
            require(len(reports) == len(offers) == 1, "one TX report")
            require(int(reports[0][0]) >= int(offers[0][0]) + 5, "independent TX report hold")
            require(len(begins) == len(dones) == len(frame), "complete frame byte counts")
            require(len(ss) == (len(c["samples"]) if cfg["valid"] and err != 1 else 0), "sample consumption count")
            delta = [len(frame), len(frame), 0, 0, 0, 0, len(frame), 0, 0, 0, 0, 0, 0]
            if err:
                categories[1] += 1
                require(not begins and not packets and not retirements and not errors, "error 1..3 emitted UART/RX")
            elif mode == 1:
                categories[4] += 1
                require(not packets and not retirements and [int(x[2]) for x in errors] == [3], "CRC rejection event/candidate")
                require(len(ev.get("F", [])) == 1, "corruption interval uniqueness")
                f = ev["F"][0]
                start_bit = begins[12][0] + (4 * clock + baud - 1) // baud
                end_bit = begins[12][0] + (5 * clock + baud - 1) // baud
                require(list(map(int, f[2:])) == [start_bit, end_bit] and int(f[0]) == start_bit, "corruption exact bit/cycle")
                mutated = frame[:];mutated[12] ^= 8
                require(received == mutated and crc16(received[2:-2]) != int.from_bytes(bytes(received[-2:]), "little"), "independent corrupted CRC")
                delta[11] = 1
            else:
                categories[3 if mode == 3 else 0] += 1
                require(len(packets) == len(retirements) == 1 and not errors, "one accepted RX candidate/retirement")
                require(int(retirements[0][0]) >= int(packets[0][0]) + len(frame) * byte_cycles + 16, "RX whole-frame hold")
                require(received == frame and crc16(received[2:-2]) == int.from_bytes(bytes(received[-2:]), "little"), "independent clean CRC")
                delta[7] = delta[8] = 1
            require(tags[3] == [x + y for x, y in zip(tags[0], delta)], f"RX final counters run {rid}")
        local = [len(begins), len(dones), len(ss), len(packets), len(retirements), len(reports), sum(int(x[2]) == 3 for x in errors), len(ev.get("L", []))]
        require(len(ev.get("Z", [])) == 1 and list(map(int, ev["Z"][0][2:])) == local, "per-run totals")
        totals = [x + y for x, y in zip(totals, local)]
        details.append(dict(run=rid, case=cid, mode=mode, abort_kind=kind, stage=stage, phase=phase, byte_starts=len(begins), byte_completions=len(dones), samples=len(ss), candidates=len(packets), retired=len(retirements), reports=len(reports), crc_errors=local[6], before=tags[0], after=tags[3], abort_pre=tags.get(1), abort_post=tags.get(2)))
    require(summary == [len(runs)] + categories + totals + [cycles], "profile statistic totals")
    if default_only:
        require([r["n"][2] for r in runs] == [53], "default-only stimulus")
    else:
        require([r["n"][2] for r in runs[:53]] == list(range(53)), "all53 vector coverage")
        require(len(runs) == (147 if extended else 53), "profile run coverage")
    if extended:
        matrix = {(k, s, p) for k in range(2) for s in (1, 2) for p in range(10)}
        matrix |= {(k, s, -1) for k in range(2) for s in (0, 3, 4)}
        require(abort_matrix == matrix, "abort matrix coverage")
        for index, run in enumerate(runs):
            if run["n"][4] in (1, 2):
                require(runs[index + 1]["n"][2:5] == [3, 24, 3], "fresh recovery after abort/corruption")
    else:
        require(not abort_matrix and categories[4] == 0, "bounded baseline extras")
    return dict(clock=clock, baud=baud, runs=len(runs), categories=dict(zip(("normal", "error", "abort", "recovery", "corruption"), categories)), totals=dict(zip(("byte_starts", "byte_completions", "samples", "candidates", "retired", "reports", "crc_errors", "line_errors"), totals)), cycles=cycles, details=details)


def load_bound(manifest_path):
    attempt = manifest_path.parent
    manifest = json.loads(manifest_path.read_text("utf8"))
    require(digest(canonical(manifest["bound"])) == manifest["binding"], "manifest binding")
    for relative, sha in manifest["bound"]["files"].items():
        require(digest((attempt / relative).read_bytes()) == sha, f"snapshot file binding {relative}")
    original = json.loads((attempt / "inputs/main_vectors.json").read_text("utf8"))
    return attempt, manifest, original["cases"] + [default_case()]


def check_profile(manifest_path, profile_path, stdout_override=None, events_override=None):
    attempt, manifest, cases = load_bound(manifest_path)
    profile = json.loads(profile_path.read_text("utf8"))
    clock, baud, extended, default_only = profile["parameters"]
    raw = (profile_path.parent / "events.log").read_bytes() if events_override is None else events_override
    result = check_events(raw, cases, clock, baud, manifest["binding"], extended, default_only)
    proc = json.loads((profile_path.parent / "vsim.process.json").read_text("utf8"))
    stdout = (profile_path.parent / "vsim.stdout.bin").read_bytes() if stdout_override is None else stdout_override
    tb = attempt / "inputs" / TB
    finish_lines = [n for n, line in enumerate(tb.read_text("utf8").splitlines(), 1) if line.strip() == "$finish;"]
    require(len(finish_lines) == 1, "fixture unique finish")
    check_transcript(stdout, clock, baud, manifest["binding"], tb, finish_lines[0], result["runs"], result["cycles"], proc["exit_code"])
    require((profile_path.parent / "vsim.stderr.bin").stat().st_size == 0, "simulator stderr")
    transcript = (profile_path.parent / "transcript.log").read_bytes()
    saved_stdout = (profile_path.parent / "vsim.stdout.bin").read_bytes()
    startup = b"Reading D:/modelsim1/tcl/vsim/pref.tcl\r\n\r\n# 10.7\r\n\r\n"
    require(saved_stdout == transcript or saved_stdout == startup + transcript, "stdout/transcript agreement including exact 10.7 startup prefix")
    check_transcript(transcript, clock, baud, manifest["binding"], tb, finish_lines[0], result["runs"], result["cycles"], proc["exit_code"])
    return result


def negative_campaign(manifest, profile):
    folder = profile.parent
    stdout = (folder / "vsim.stdout.bin").read_bytes()
    raw = (folder / "events.log").read_bytes()
    nl = b"\r\n" if b"\r\n" in stdout else b"\n"
    s = stdout.splitlines(keepends=True)
    def line_matching(needle):
        return next(x for x in s if needle in x)
    marker = line_matching(b"# TRACE52_DONE")
    footer = line_matching(b"# Errors:")
    timing = line_matching(b"#    Time:")
    mutations = [
        ("marker-substring", "stdout", stdout.replace(marker, b"prefix " + marker)),
        ("missing-marker-prefix", "stdout", stdout.replace(marker, marker[2:])),
        ("duplicate-marker", "stdout", stdout.replace(marker, marker + marker)),
        ("duplicate-stat", "stdout", stdout.replace(footer, footer + footer)),
        ("conflicting-stat", "stdout", stdout.replace(footer, footer + b"# Errors: 1, Warnings: 0" + nl)),
        ("os0-error-stat", "stdout", stdout.replace(footer, b"# Errors: 1, Warnings: 0" + nl)),
        ("source-binding", "stdout", stdout.replace(b"bind=", b"bind=0", 1)),
        ("stray-timing", "stdout", stdout.replace(timing, timing + b"prefix Time: 1 ns" + nl)),
        ("finish-line", "stdout", stdout.replace(b".sv(", b".sv(9", 1)),
        ("finish-file", "stdout", stdout.replace(b"tb_trace_uart_loopback.sv(", b"other.sv(", 1)),
        ("control-byte", "stdout", stdout + b"\x00"),
        ("truncation", "stdout", stdout[:-5]),
        ("extra-footer", "stdout", stdout + b"# extra" + nl),
        ("raw-header-binding", "events", raw.replace(b"H 16 1 ", b"H 16 1 0", 1)),
        ("raw-event-substring", "events", raw.replace(b"\nB ", b"\nprefix B ", 1)),
        ("raw-control", "events", raw + b"\x1b"),
        ("raw-truncation", "events", raw[:-80]),
    ]
    q = next(x for x in raw.splitlines(keepends=True) if x.startswith(b"Q "))
    mutations.append(("raw-duplicate-stat", "events", raw.replace(q, q + q)))
    records = []
    for name, stream, mutated in mutations:
        try:
            check_profile(manifest, profile, stdout_override=mutated if stream == "stdout" else None, events_override=mutated if stream == "events" else None)
        except (ValueError, UnicodeError) as exc:
            records.append(dict(name=name, stream=stream, base_sha256=digest(stdout if stream == "stdout" else raw), mutated_sha256=digest(mutated), rejected=True, reason=str(exc), recipe_index=len(records)))
        else:
            raise ValueError(f"saved-log negative accepted: {name}")
    return records


def actual_error_probe(tools, library_cwd, output, binding, tb):
    output.mkdir()
    # Load the existing valid testbench but reject an invalid duration before
    # advancing simulation. Tcl catch permits the explicit zero OS exit.
    # This reads no hierarchical state and changes no DUT or product source.
    p = run_process([tools / "vsim.exe", "-c", "-work", "work", "-l", output / "transcript.log",
                     "tb_trace_uart_loopback", "-do", "catch {run TRACE52_invalid_time}; quit -f -code 0"],
                    library_cwd, output / "vsim", 30)
    out = (output / "vsim.stdout.bin").read_bytes()
    stats = re.findall(rb"(?m)^# Errors: (\d+), Warnings: (\d+)\r?$", out)
    require(p["exit_code"] == 0 and len(stats) == 1 and int(stats[0][0]) > 0,
            "actual OS0/error-positive probe did not produce required evidence")
    try:
        check_transcript(out, 16, 1, binding, tb, 1, 147, 1, 0)
    except ValueError as exc:
        require(str(exc) == "ModelSim errors/warnings even with OS zero", "actual error-positive rejection reason")
        record = dict(os_exit=0, errors=int(stats[0][0]), warnings=int(stats[0][1]), rejected=True, reason=str(exc), no_simulation_time_advance=True)
        write_json(output / "REJECTION.json", record)
        return record
    raise ValueError("actual OS0 error-positive log accepted")


def finish_saved_attempt(root, attempt_name):
    """Explicit repair-2 completion; never replay a passed ModelSim profile."""
    require(os.environ.get("CODEX_THREAD_ID") == AGENT, "wrong canonical executor")
    require(attempt_name == "attempt-02", "repair 2 is bound to inspected attempt-02")
    base = root / AUTHOR / attempt_name
    output = root / AUTHOR / "repair-02"
    require(not output.exists(), "repair evidence exists; no automatic replay")
    output.mkdir()
    start = time.monotonic()
    write_json(output / "runner.started.json", dict(pid=os.getpid(), argv=sys.argv, cwd=os.getcwd(), executable=sys.executable,
               started_utc=dt.datetime.now(dt.timezone.utc).isoformat(), bounded_repair_cycle=2))
    prior = json.loads((base / "RESULT.json").read_text("utf8"))
    result = {k: v for k, v in prior.items() if k not in ("status", "error", "duration_seconds")}
    result.update(status="failed", reused_simulation_attempt=attempt_name, replayed_simulation_profiles=0,
                  original_failure_preserved=str(base / "RESULT.json"))
    try:
        require(prior["error"] == "actual OS0/error-positive probe did not produce required evidence", "saved failure scope changed")
        saved_hashes = json.loads((base / "EVIDENCE_HASHES.json").read_text("utf8"))
        for relative, entry in saved_hashes.items():
            require(digest((base / relative).read_bytes()) == entry["sha256"], f"preserved evidence changed: {relative}")
        _, bound, _ = load_bound(base / "MANIFEST.json")
        require((root / TB).read_bytes() == (base / "inputs" / TB).read_bytes(), "testbench changed; cannot reuse prior simulation")
        final_files = {}
        for relative in (TB, RUNNER, DOC):
            data = (root / relative).read_bytes()
            target = output / "inputs" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            final_files[relative] = digest(data)
        write_json(output / "REPAIR_MANIFEST.json", dict(base_manifest_sha256=digest((base / "MANIFEST.json").read_bytes()),
                   base_binding=bound["binding"], base_evidence_hashes_sha256=digest((base / "EVIDENCE_HASHES.json").read_bytes()),
                   final_owned_files=final_files, reused_testbench_sha256=final_files[TB], only_new_process="OS-zero/error-positive diagnostic", repair_cycle=2))
        verified = []
        for clock, baud, _, _ in PROFILES:
            profile = base / f"ratio-{clock}-{baud}/PROFILE.json"
            checked = check_profile(base / "MANIFEST.json", profile)
            require(checked == json.loads((profile.parent / "CHECK.json").read_text("utf8")), "saved independent-check result changed")
            verified.append(checked)
        negatives = negative_campaign(base / "MANIFEST.json", base / "ratio-16-1/PROFILE.json")
        write_json(output / "SAVED_LOG_NEGATIVES.json", dict(base_attempt=attempt_name, deterministic_recipe_source="inputs/" + RUNNER,
                   cases=negatives, no_new_DUT_simulation=True))
        probe = actual_error_probe(Path("D:/modelsim1/win64"), base, output / "actual-os0-errors", bound["binding"], base / "inputs" / TB)
        for relative, sha in PINS.items():
            require(digest((root / relative).read_bytes()) == sha, f"immutable dependency changed: {relative}")
        result.update(status="bounded_fixture_verified_pending_main_review", profiles=[{k: v for k, v in r.items() if k != "details"} for r in verified],
                      saved_log_negatives=len(negatives), actual_os0_error_positive=probe, dependencies_unchanged=True,
                      final_owned_files=final_files, repair_cycles_used=2, testbench_unchanged_from_verified_attempt=True)
    except Exception as exc:
        result["error"] = str(exc)
        (output / "failure.txt").write_text(traceback.format_exc(), encoding="utf8")
    result["duration_seconds"] = time.monotonic() - start
    write_json(output / "RESULT.json", result)
    write_json(output / "EVIDENCE_HASHES.json", {p.relative_to(output).as_posix(): dict(sha256=digest(p.read_bytes()), bytes=p.stat().st_size)
               for p in output.rglob("*") if p.is_file()})
    print(json.dumps(dict(status=result["status"], result=str(output / "RESULT.json"), error=result.get("error"))), flush=True)
    return 0 if result["status"] != "failed" else 1


def execute(root, attempt_name):
    require(os.environ.get("CODEX_THREAD_ID") == AGENT, "wrong canonical executor")
    attempt = root / AUTHOR / attempt_name
    require(not attempt.exists(), "attempt already exists; no automatic replay")
    attempt.mkdir(parents=True)
    started = time.monotonic()
    write_json(attempt / "runner.started.json", dict(pid=os.getpid(), argv=sys.argv, cwd=os.getcwd(), executable=sys.executable, started_utc=dt.datetime.now(dt.timezone.utc).isoformat()))
    result = dict(task_id=TASK, task_version=1, work_id=WORK, operation_id=OP, job_id=JOB, agent_id=AGENT, status="failed", formal29="not_run", B01="not_run", B03="not_run", B06="not_run", R03="not_run", fullproduct="not_run", physicalboard="not_run; A-only", synthesis="not_run", implementation="not_run", ooc50="separate ownership; not read or awaited")
    try:
        repo = Path("D:/pynq/CarlandFPGA")
        files = {}
        for relative, sha in {**PINS, TB: None, RUNNER: None, DOC: None}.items():
            src = root / relative
            content = src.read_bytes()
            actual = digest(content)
            require(sha is None or actual == sha, f"immutable dependency hash: {relative}")
            target = attempt / "inputs" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            files[target.relative_to(attempt).as_posix()] = actual
        vector_bytes = (root / VECTORS).read_bytes()
        require(digest(vector_bytes) == VECTOR_SHA, "frozen vectors hash")
        (attempt / "inputs/main_vectors.json").write_bytes(vector_bytes)
        files["inputs/main_vectors.json"] = VECTOR_SHA
        cases = json.loads(vector_bytes)["cases"]
        require(len(cases) == 53 and cases[3]["id"] == 24, "frozen vector identities")
        all_cases = cases + [default_case()]
        for c in cases:
            require(not c["frame"] or crc16(c["frame"][2:-2]) == int.from_bytes(bytes(c["frame"][-2:]), "little"), "frozen CRC golden consistency")
        data = vector_text(all_cases)
        (attempt / "inputs/vectors.txt").write_bytes(data)
        files["inputs/vectors.txt"] = digest(data)
        lockdir = repo / ".local/deployment/node-b/implementation-app-bridge/inputs/lock/docs/competition/deepeye-2026"
        for name in ("immutable_scope.json", "immutable_scope.md"):
            data = (lockdir / name).read_bytes()
            (attempt / "inputs" / name).write_bytes(data)
            files["inputs/" + name] = digest(data)
        contract = json.loads((attempt / "inputs/immutable_scope.json").read_text("utf8"))
        require(digest(canonical(contract["requirements"])) == CONTRACT, "fixed human requirements hash")
        require([r["id"] for r in contract["requirements"]] == [f"H{i:02}" for i in range(1, 16)], "H01-H15")
        spec = repo / ".local/deployment/node-b/evidence/trace-uart-loopback-20261024-52/MAIN_SPEC.md"
        (attempt / "inputs/MAIN_SPEC.md").write_bytes(spec.read_bytes())
        files["inputs/MAIN_SPEC.md"] = digest(spec.read_bytes())
        own_rollouts = list((Path.home() / ".codex/sessions/2026/10/24").glob(f"*{AGENT}.jsonl"))
        require(len(own_rollouts) == 1, "actual runtime rollout unavailable")
        turns = [j["payload"] for line in own_rollouts[0].read_text("utf8").splitlines() if (j := json.loads(line)).get("type") == "turn_context"]
        require(turns, "actual turn metadata unavailable")
        turn = turns[-1]
        actor = dict(thread_id=AGENT, turn_id=turn["turn_id"], model=turn["model"], effort=turn["effort"], evidence_source=str(own_rollouts[0]))
        bound = dict(task_id=TASK, task_version=1, work_id=WORK, operation_id=OP, files=files, actor=actor,
                     contract_id="DEEPEYE-HUMAN-LOCK-20261014", revision=1, requirements_sha256=CONTRACT,
                     requirement_ids=[f"H{i:02}" for i in range(1, 16)], contract_commit="f5989cd5defce561f9ba98e6b18fc2682945f0a2", frozen_design=FROZEN,
                     vector_reuse="main49 frozen 53 payload/CRC goldens; not a new codec oracle", default_extra=default_case(), profiles=PROFILES)
        binding = digest(canonical(bound))
        manifest = attempt / "MANIFEST.json"
        write_json(manifest, dict(bound=bound, binding=binding))
        result.update(actor=actor, binding=binding, requirements_sha256=CONTRACT, requirement_ids=bound["requirement_ids"], contract_commit=bound["contract_commit"], frozen_design=FROZEN)
        tools = Path("D:/modelsim1/win64")
        hashes = {}
        for executable in ("vsim.exe", "vlog.exe", "vlib.exe"):
            hashes[executable] = digest((tools / executable).read_bytes())
            if executable != "vlib.exe":
                p = run_process([tools / executable, "-version"], attempt, attempt / f"tools/{executable}-version", 30)
                require(p["exit_code"] == 0, "tool version launch failed")
        hashes["python"] = digest(Path(sys.executable).read_bytes())
        write_json(attempt / "TOOLS.json", dict(paths={x: str(tools / x) for x in hashes if x != "python"}, hashes=hashes, python=sys.version, executable=sys.executable))
        lib = attempt / "work"
        p = run_process([tools / "vlib.exe", lib], attempt, attempt / "compile/vlib", 30)
        require(p["exit_code"] == 0, "vlib failed")
        sources = [attempt / "inputs" / name for name in PINS] + [attempt / "inputs" / TB]
        p = run_process([tools / "vlog.exe", "-sv", "-work", lib, *sources], attempt, attempt / "compile/vlog", 60)
        compile_out = (attempt / "compile/vlog.stdout.bin").read_bytes()
        require(p["exit_code"] == 0 and re.search(rb"(?m)^Errors: 0, Warnings: 0\r?$", compile_out), "vlog errors/warnings (preserved)")
        results = []
        for clock, baud, extended, default_only in PROFILES:
            folder = attempt / f"ratio-{clock}-{baud}"
            folder.mkdir()
            profile = folder / "PROFILE.json"
            write_json(profile, dict(parameters=[clock, baud, extended, default_only]))
            command = [tools / "vsim.exe", "-c", "-work", "work", "-l", folder / "transcript.log",
                       f"-gCLOCK_HZ={clock}", f"-gBAUD={baud}", f"-gEXTENDED={extended}", f"-gDEFAULT_ONLY={default_only}", "tb_trace_uart_loopback",
                       "+VECTORS=" + (attempt / "inputs/vectors.txt").as_posix(), "+EVENTS=" + (folder / "events.log").as_posix(), "+BIND=" + binding,
                       "-do", "onerror {quit -f -code 2}; onbreak {quit -f -code 3}; run -all; quit -f -code 0"]
            p = run_process(command, attempt, folder / "vsim", 240)
            require(p["exit_code"] == 0, f"ModelSim process failed at {clock}/{baud}; original preserved")
            checker = attempt / "inputs" / RUNNER
            p = run_process([sys.executable, "-X", "utf8", checker, "--check", "--manifest", manifest, "--profile", profile], folder, folder / "python-check", 60)
            require(p["exit_code"] == 0, f"public-event check failed at {clock}/{baud}; original preserved")
            scored = json.loads((folder / "CHECK.json").read_text("utf8"))
            results.append(scored)
            print(f"TRACE52_PROFILE_VERIFIED clock={clock} baud={baud} runs={scored['runs']} cycles={scored['cycles']}", flush=True)
        negatives = negative_campaign(manifest, attempt / "ratio-16-1/PROFILE.json")
        write_json(attempt / "SAVED_LOG_NEGATIVES.json", dict(base_stdout="ratio-16-1/vsim.stdout.bin", base_events="ratio-16-1/events.log", deterministic_recipe_source="inputs/" + RUNNER, cases=negatives))
        # Fresh actual ModelSim OS-zero/error-positive process; not an old guard campaign.
        actual_error_probe(tools, attempt, attempt / "actual-os0-errors", binding, attempt / "inputs" / TB)
        for path, sha in PINS.items():
            require(digest((root / path).read_bytes()) == sha, f"dependency changed during execution: {path}")
        result.update(status="bounded_fixture_verified_pending_main_review", profiles=[{k: v for k, v in r.items() if k != "details"} for r in results], saved_log_negatives=len(negatives), actual_os0_error_positive=True, dependencies_unchanged=True)
    except Exception as exc:
        result["error"] = str(exc)
        (attempt / "failure.txt").write_text(traceback.format_exc(), encoding="utf8")
    result["duration_seconds"] = time.monotonic() - started
    write_json(attempt / "RESULT.json", result)
    evidence_files = {p.relative_to(attempt).as_posix(): dict(sha256=digest(p.read_bytes()), bytes=p.stat().st_size) for p in attempt.rglob("*") if p.is_file() and "work" not in p.relative_to(attempt).parts}
    write_json(attempt / "EVIDENCE_HASHES.json", evidence_files)
    print(json.dumps(dict(status=result["status"], result=str(attempt / "RESULT.json"), error=result.get("error")), ensure_ascii=False), flush=True)
    return 0 if result["status"] != "failed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt")
    parser.add_argument("--finish-attempt", help="explicit bounded repair-2 finalization of preserved attempt-02")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args()
    if args.finish_attempt:
        return finish_saved_attempt(Path(__file__).resolve().parents[2], args.finish_attempt)
    if args.check:
        try:
            result = check_profile(args.manifest.resolve(), args.profile.resolve())
            write_json(args.profile.parent / "CHECK.json", result)
            print(json.dumps({k: v for k, v in result.items() if k != "details"}))
            return 0
        except Exception:
            traceback.print_exc()
            return 1
    require(args.attempt is not None and re.fullmatch(r"attempt-[0-9]{2}", args.attempt), "explicit fresh attempt required")
    return execute(Path(__file__).resolve().parents[2], args.attempt)


if __name__ == "__main__":
    raise SystemExit(main())
