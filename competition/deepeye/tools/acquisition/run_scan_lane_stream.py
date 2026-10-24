#!/usr/bin/env python3
"""Bounded author simulation for candidate44; transaction fixtures, public traces.

No synthesis, capture qualification, ABI/admission policy or product acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
AUTHOR = ROOT / "evidence/acquisition/scan-lane-stream-20261024-44/author"
TOOLS = Path("D:/modelsim1/win64")
TASK = "DEEPEYE-IMPLEMENTATION-20261014/version1"
WORK = "B-SCAN-LANE-STREAM-20261024-44-v1"
OP = "B-DEEPEYE-SCAN-LANE-STREAM-20261024-44"
CONTRACT = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
PINS = {
    "fpga/acquisition/deepeye_buffered_scan_capture.sv": "c8a540db8122b8f5520582a0f1fa9be0c43cb54a62f03c7c4edc893906f28411",
    "fpga/acquisition/deepeye_sample_scan_capture.sv": "fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d",
    "fpga/acquisition/deepeye_raw_scan_queue.sv": "630e14803d82b3379517d91626de4ad7e7d3c509ad14363b3164031a5f633ee4",
    "fpga/acquisition/buffered_scan_capture_candidate.md": "c36d01bb248250ff83642dc44e6d236ebaf11e623bc0e2348f41fe8e3f0c8fdd",
}
PROTECTED = ROOT.parents[1] / "handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json"
PROTECTED_SHA = "6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8"
NEW = ["fpga/acquisition/deepeye_scan_lane_stream.sv",
       "tests/rtl/acquisition/tb_scan_lane_stream.sv",
       "tools/acquisition/run_scan_lane_stream.py",
       "fpga/acquisition/scan_lane_stream_candidate.md"]
N = r"(?:0|[1-9][0-9]*)"
FIELDS = ("mode cycles checks records lanes reloads in_stalls out_stalls reset cancel "
          "discarded lane0 lane1 lane2 lane3").split()
SUMMARY = re.compile(r"# SL_SUMMARY " + " ".join(k + "=(" + N + ")" for k in FIELDS))
ROW = re.compile(r"(" + N + r") (PRE|POST) (" + N + r") ([01]{4}) ([01]) ([01]) "
                 r"([0-9a-f]{112}) ([0-9a-fxXzZ]{112}) ([0-9a-f]{47}) "
                 r"([0-9a-fxXzZ]{47}) ([0-9a-f]{32}) (" + N + r") ([01])")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1048576), b""):
            h.update(b)
    return h.hexdigest()


def save(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def require(ok, msg):
    if not ok:
        raise ValueError(msg)


def cat(parts):
    value = 0
    for field, width in parts:
        require(0 <= field < 1 << width, "fixture field width")
        value = (value << width) | field
    return value


def record(data, ticks, quality, first, last, tag):
    # Static field/lane tuple construction from input records, no clocked state.
    packed = (sum(v << (16*j) for j, v in enumerate(data))
              | sum(v << (64*j+64) for j, v in enumerate(ticks))
              | sum(v << (8*j+320) for j, v in enumerate(quality))
              | first << 352 | last << 384 | tag << 416)
    lanes = [cat([(j, 2), (data[j], 16), (ticks[j], 64), (quality[j], 8),
                  (first, 32), (last, 32), (tag, 32), (int(j == 3), 1)]) for j in range(4)]
    return dict(data=data, ticks=ticks, quality=quality, first=first, last=last, tag=tag,
                packed=f"{packed:0112x}", lanes=[f"{v:047x}" for v in lanes])


def producer(ur=0, stop=0, rearm=0, qc=0, strobe=0, tag=0, ch=0, data=0, tick=0, quality=0):
    return cat([(ur, 1), (stop, 1), (rearm, 1), (qc, 1), (strobe, 1),
                (tag, 32), (ch, 2), (data, 16), (tick, 64), (quality, 8)])


def standalone_fixture():
    rng = random.Random(0x2026102444)
    recs = [record([0]*4, [0]*4, [0]*4, 0, 0, 0),
            record([65535]*4, [(1 << 64)-1]*4, [255]*4, 0xffffffff, 0xffffffff, 0xffffffff),
            record([0, 65535, 0xaaaa, 0x5555], [1 << 63, 1, (1 << 64)-1, 0],
                   [0, 255, 0x55, 0xaa], 0xffffffff, 0, 0xa55a5aa5)]
    for i in range(509):
        recs.append(record([rng.getrandbits(16) for _ in range(4)],
                           [rng.getrandbits(64) for _ in range(4)],
                           [rng.getrandbits(8) for _ in range(4)],
                           rng.getrandbits(32), rng.getrandbits(32),
                           0xffffffff if i % 2 else 0))
    rows = []

    def emit(scenario, rst=0, cancel=0, valid=0, ready=0, rid=None):
        rid = (len(rows) * 17) % len(recs) if rid is None else rid
        rows.append([scenario, rst*8+cancel*4+valid*2+ready, rid, producer(ur=1)])

    emit(0, rst=1)
    emit(1)
    # Continuous offered records force atomic final-lane replacement.
    for i in range(96):
        emit(2, valid=1, ready=1, rid=i % 3)
    for _ in range(4):
        emit(3, ready=1)
    for ctl in ("rst", "cancel"):
        for lane in range(4):
            for stalled in (0, 1):
                sid = 10 + (ctl == "cancel")*8 + 2*lane + stalled
                emit(sid, valid=1, rid=1 if lane % 2 else 2)
                for _ in range(lane):
                    emit(sid, valid=1, ready=1)
                for _ in range(3*stalled):
                    emit(sid, valid=1)
                emit(sid, valid=1, ready=1, **{ctl: 1})
                emit(sid, valid=1, rid=2 if lane % 2 else 1)
                for _ in range(4):
                    emit(sid, ready=1)
                emit(sid)
    emit(30, cancel=1, valid=1, ready=1)
    emit(30, rst=1, cancel=1, valid=1, ready=1)
    for _ in range(5000):
        emit(40, rst=int(rng.randrange(83) == 0), cancel=int(rng.randrange(79) == 0),
             valid=int(rng.randrange(5) != 0), ready=int(rng.randrange(4) != 0),
             rid=rng.randrange(len(recs)))
    emit(50, rst=1, valid=1, ready=1)
    emit(50, valid=1, rid=2)
    for _ in range(4):
        emit(50, ready=1)
    emit(50)
    return dict(mode=0, seed="0x2026102444", records=recs, stream=[], rows=rows,
                disclosure="Direct record/lane vectors and finite handshake mix; opaque bounds deliberately include first > last.")


def integration_fixture():
    recs, rows, stream = [], [], []
    tag = 0

    def emit(scenario, ready=0, rst=0, cancel=0, rid=0, **up):
        rows.append([scenario, rst*8+cancel*4+ready, rid, producer(tag=tag, **up)])

    def scan(first, ready, scenario):
        k = len(recs)
        r = record([((k+1)*0x1234 ^ (j*0x5555)) & 65535 for j in range(4)],
                   [((1 << 64)-1 - k*101 - j*0x100000001) for j in range(4)],
                   [[0, 255, 0x55, 0xaa][(k+j) % 4] for j in range(4)], first, first+3, tag)
        recs.append(r)
        stream.append(k)
        for j in range(4):
            emit(scenario, ready, rid=k, strobe=1, ch=j, data=r["data"][j],
                 tick=r["ticks"][j], quality=r["quality"][j])
        for _ in range(2):
            emit(scenario, ready, rid=k)

    emit(100, rst=1, ur=1)
    emit(100)
    tag = 0xffffffff
    emit(101, rearm=1)
    for k in range(6):
        scan(4*k, int(k >= 2), 102)
    for _ in range(40):
        emit(103, 1)
    scan(24, 0, 104)
    scan(28, 0, 104)
    emit(105, stop=1)  # Capture controls do not cancel the held/queued records.
    tag = 0
    emit(105, rearm=1)
    scan(0, 0, 106)
    scan(4, 0, 106)
    emit(107, 1)
    emit(107, 1, cancel=1)  # Discard only serializer's remaining three lanes.
    for _ in range(40):
        emit(108, 1)
    tag = 0xa55a5aa5
    emit(109, rearm=1)
    scan(0, 0, 109)
    for _ in range(8):
        emit(109)
    emit(110, qc=1)  # Upstream queue is empty; held44 tuple must persist.
    for _ in range(8):
        emit(110, 1)
    emit(111, rst=1, ur=1)
    emit(111)
    tag = 0x80000001
    emit(112, rearm=1)
    scan(0, 1, 112)
    scan(4, 1, 112)
    for _ in range(24):
        emit(113, 1)
    return dict(mode=1, records=recs, stream=stream, rows=rows,
                disclosure="Reuses published39 capture/queue behavior and fixtures' literal sequence bounds. Only boundary transport/field preservation is checked; no new capture proof or sequence/tag/quality policy.")


def write_fixture(folder, fixture):
    folder.mkdir()
    save(folder / "fixture.json", fixture)
    lines = [f"{len(fixture['records'])} {len(fixture['stream'])} {len(fixture['rows'])}"]
    lines += [" ".join([r["packed"], *r["lanes"]]) for r in fixture["records"]]
    lines += [str(i) for i in fixture["stream"]]
    lines += [f"{s} {c:x} {r} {p:032x}" for s, c, r, p in fixture["rows"]]
    (folder / "stimulus.txt").write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    require((folder / "stimulus.txt").read_text(encoding="ascii").splitlines() == lines, "saved fixture differs")
    return folder / "stimulus.txt"


def clean_lines(text):
    require(not re.search(r"[\x00-\x09\x0b\x0c\x0e-\x1f\x7f]", text), "control byte")
    require(not re.search(r"\r(?!\n)", text), "bare CR")
    lines = text.replace("\r\n", "\n").split("\n")
    if lines[-1] == "":
        lines.pop()
    return lines


def terminal_stats(text, mode, cycles, tb_path, finish_line):
    lines = clean_lines(text)
    summaries = [i for i, line in enumerate(lines) if line.startswith("# SL_SUMMARY")]
    require(len(summaries) == 1, "unique anchored summary")
    at = summaries[0]
    m = SUMMARY.fullmatch(lines[at])
    require(m is not None, "exact summary labels/order/numeric grammar")
    require(len(lines) == at+6, "exact terminal footer and no trailing lines")
    stats = dict(zip(FIELDS, map(int, m.groups())))
    require(stats["mode"] == mode and stats["cycles"] == cycles, "summary mode/cycles fixture tie")
    require(lines[at+1] == f"# SL_DONE mode={mode} PASS", "unique ordered completion")
    for i, line in enumerate(lines):
        if "SL_" in line:
            require(i in (at, at+1), "unknown/prefix/conflicting completion marker")
        require(not re.search(r"\*\* (?:Error|Fatal|Warning)|SL_FAIL", line), "vendor/test failure")
    start_rows = [i for i, line in enumerate(lines) if "Start time:" in line]
    require(len(start_rows) == 1 and start_rows[0] < at, "unique prefix Start time: token")
    reserved = {
        "$finish": at+2, "Time:": at+3, "Iteration:": at+3, "Instance:": at+3,
        "End time:": at+4, "Elapsed time:": at+4, "Errors:": at+5, "Warnings:": at+5,
        "Start time:": start_rows[0],
    }
    for token, expected_row in reserved.items():
        occurrences = [i for i, line in enumerate(lines) for _ in range(line.count(token))]
        require(occurrences == [expected_row], "unique anchored provenance token " + token)
    note = re.fullmatch(r"# \*\* Note: \$finish\s+: (.+)\(([1-9][0-9]*)\)", lines[at+2])
    require(note is not None, "finish provenance grammar")
    norm = lambda p: str(p).replace("\\", "/").casefold()
    require(norm(note[1]) == norm(tb_path) and int(note[2]) == finish_line, "actual TB finish file/line")
    require(lines[at+3] == f"#    Time: {cycles*10} ns  Iteration: 1  Instance: /tb_scan_lane_stream", "actual finish time/instance")
    stamp = r"([0-9]{2}:[0-9]{2}:[0-9]{2} on [A-Z][a-z]{2} [ 0-9][0-9],[0-9]{4})"
    starts = [re.fullmatch(r"# Start time: " + stamp, line) for line in lines[:at]]
    starts = [m for m in starts if m]
    end = re.fullmatch(r"# End time: " + stamp + r", Elapsed time: ([0-9]+):([0-5][0-9]):([0-5][0-9])", lines[at+4])
    require(len(starts) == 1 and end is not None, "start/end provenance")
    start_at = datetime.strptime(starts[0][1], "%H:%M:%S on %b %d,%Y")
    end_at = datetime.strptime(end[1], "%H:%M:%S on %b %d,%Y")
    require((end_at-start_at).total_seconds() == 3600*int(end[2])+60*int(end[3])+int(end[4]), "elapsed time agreement")
    require(lines[at+5] == "# Errors: 0, Warnings: 0", "clean final vendor counters")
    return stats


def check_trace(trace_lines, fixture):
    pending = deque()
    stats = Counter(mode=fixture["mode"], cycles=len(fixture["rows"]))
    coverage = Counter()
    stream_index = 0
    last_stalled = False
    it = iter(trace_lines)
    for ci, (scenario, controls, offer_id, producer_bits) in enumerate(fixture["rows"], 1):
        for phase in ("PRE", "POST"):
            raw = next(it, None)
            require(raw is not None, f"missing trace {ci}/{phase}")
            require(raw.endswith("\n"), f"unterminated/bare-CR trace {ci}/{phase}")
            line = raw[:-1].removesuffix("\r")
            m = ROW.fullmatch(line)
            require(m is not None, f"trace grammar {ci}/{phase}")
            cyc, ph, sid, ctl, ir, ov, mi, ri, mo, ro, up, rid, ol = m.groups()
            require((int(cyc), ph, int(sid), int(rid), int(up, 16)) ==
                    (ci, phase, scenario, offer_id, producer_bits), "trace order/fixture inputs")
            rst, cancel, iv, ready = map(int, ctl)
            require((rst, cancel, ready) == (controls >> 3, (controls >> 2) & 1, controls & 1), "trace control fixture")
            if fixture["mode"] == 0:
                require(iv == ((controls >> 1) & 1), "standalone input-valid fixture")
                require(ri == fixture["records"][offer_id]["packed"], "standalone offered record fixture")
            ir, ov, ol = int(ir), int(ov), int(ol)
            masked_in, masked_out = int(mi, 16), int(mo, 16)
            require(masked_in < 1 << 448 and masked_out < 1 << 187, "trace packed width")
            require(masked_in == (int(ri, 16) if iv and not re.search("[xXzZ]", ri) else 0), "input mask/raw equality")
            require(not iv or not re.search("[xXzZ]", ri), "unknown valid input")
            require(masked_out == (int(ro, 16) if ov and not re.search("[xXzZ]", ro) else 0), "output mask/raw equality")
            require(not ov or not re.search("[xXzZ]", ro), "unknown valid output")
            active = bool(pending) and not (rst or cancel)
            wanted_last = int(active and (pending[0] & 1) == 1)
            wanted_ready = int(not (rst or cancel) and (not pending or (ready and wanted_last)))
            require((ov, ir, ol) == (int(active), wanted_ready, wanted_last), f"transaction endpoint mismatch {ci}/{phase}")
            if ov:
                require(masked_out == pending[0], f"transaction lane/opaque fields {ci}/{phase}")
            stats["checks"] += 1
            if phase == "POST":
                continue
            stats["reset"] += rst
            stats["cancel"] += cancel
            stats["in_stalls"] += int(iv and not ir)
            stats["out_stalls"] += int(ov and not ready)
            if rst or cancel:
                for label, flag in (("rst", rst), ("cancel", cancel)):
                    if flag and pending:
                        coverage[f"abort_{label}_lane_{pending[0] >> 185}"] += 1
                        if last_stalled:
                            coverage[f"abort_{label}_stalled_lane_{pending[0] >> 185}"] += 1
                stats["discarded"] += len(pending)
                pending.clear()
            else:
                if ov and ready:
                    lane = pending.popleft() >> 185
                    stats["lanes"] += 1
                    stats[f"lane{lane}"] += 1
                if iv and ir:
                    if fixture["mode"] == 0:
                        expected_id = offer_id
                    else:
                        require(stream_index < len(fixture["stream"]), "extra integrated record")
                        expected_id = fixture["stream"][stream_index]
                        stream_index += 1
                    r = fixture["records"][expected_id]
                    require(mi == r["packed"] and ri == r["packed"], "accepted record vs independent fixture")
                    require(not pending, "multiple record slots")
                    pending.extend(int(v, 16) for v in r["lanes"])
                    stats["records"] += 1
                    stats["reloads"] += int(ov and ready and ol)
            last_stalled = bool(ov and not ready)
    require(next(it, None) is None, "extra trace rows")
    require(not pending and 4*stats["records"] == stats["lanes"]+stats["discarded"], "terminal transaction conservation")
    require(fixture["mode"] == 0 or stream_index == len(fixture["stream"]), "integrated stream completeness")
    for k in ("records", "lanes", "reloads", "in_stalls", "out_stalls", "reset", "lane0", "lane1", "lane2", "lane3"):
        require(stats[k] > 0, "missing coverage " + k)
    if fixture["mode"] == 0:
        for ctl in ("rst", "cancel"):
            for lane in range(4):
                for label in (f"abort_{ctl}_lane_{lane}", f"abort_{ctl}_stalled_lane_{lane}"):
                    require(coverage[label] > 0, "missing " + label)
    return {k: stats[k] for k in FIELDS}, dict(coverage)


def check_saved(text, trace_lines, fixture, tb_path, finish_line):
    claimed = terminal_stats(text, fixture["mode"], len(fixture["rows"]), tb_path, finish_line)
    observed, coverage = check_trace(trace_lines, fixture)
    require(claimed == observed, "summary vs actual trace/fixture counters " + str((claimed, observed)))
    return dict(stats=observed, coverage=coverage)


def qualify(folder, baseline, trace_path, fixture, tb_path, finish_line):
    folder.mkdir()
    traces = trace_path.read_text(encoding="ascii").splitlines(keepends=True)
    lines = clean_lines(baseline)
    at = next(i for i, v in enumerate(lines) if v.startswith("# SL_SUMMARY"))
    mutations = {
        "missing_done": lambda a: a[:at+1]+a[at+2:],
        "duplicate_done": lambda a: a[:at+2]+[a[at+1]]+a[at+2:],
        "conflicting_done": lambda a: a[:at+1]+[a[at+1].replace("PASS", "FAIL")]+a[at+2:],
        "prefixed_done": lambda a: a[:at+1]+["prefix " + a[at+1]]+a[at+2:],
        "duplicate_summary": lambda a: a[:at]+[a[at]]+a[at:],
        "unknown_label": lambda a: a[:at]+[a[at].replace(" checks=", " arbitrary=")]+a[at+1:],
        "reordered_labels": lambda a: a[:at]+[re.sub(r"cycles=(\d+) checks=(\d+)", r"checks=\2 cycles=\1", a[at])]+a[at+1:],
        "conflicting_counter": lambda a: a[:at]+[re.sub(r"records=(\d+)", lambda m: "records="+str(int(m[1])+1), a[at])]+a[at+1:],
        "incorrect_cycle_count": lambda a: a[:at]+[re.sub(r"cycles=(\d+)", lambda m: "cycles="+str(int(m[1])+1), a[at])]+a[at+1:],
        "footer": lambda a: a+["# unsolicited footer"],
        "missing_vendor_footer": lambda a: a[:-1],
        "vendor_error": lambda a: a[:-1]+["# Errors: 1, Warnings: 0"],
        "wrong_finish_line": lambda a: a[:at+2]+[a[at+2].replace(f"({finish_line})", f"({finish_line+1})")]+a[at+3:],
        "wrong_finish_time": lambda a: a[:at+3]+[a[at+3].replace(f"{len(fixture['rows'])*10} ns", "1 ns")]+a[at+4:],
        "wrong_finish_instance": lambda a: a[:at+3]+[a[at+3]+"/other"]+a[at+4:],
        "trailing_control_byte": lambda a: a[:-1]+[a[-1]+"\x00"],
        "tab_in_marker": lambda a: a[:at+1]+[a[at+1].replace(" mode", "\tmode")]+a[at+2:],
    }
    # Exercise every summary field's numeric equality, even when PASS is intact.
    for name in FIELDS:
        def mutate(a, name=name):
            changed = re.sub(r"\b"+name+r"=(\d+)", lambda m: name+"="+str(int(m[1])+1), a[at])
            return a[:at]+[changed]+a[at+1:]
        mutations["counter_"+name] = mutate
    # Reserved provenance literals must be unique across the entire transcript,
    # including malformed substrings and duplicates before the terminal block.
    start_at = next(i for i, line in enumerate(lines) if line.startswith("# Start time: "))
    for label, token, index in (
        ("finish", "$finish", at+2), ("time", "Time:", at+3),
        ("iteration", "Iteration:", at+3), ("instance", "Instance:", at+3),
        ("end", "End time:", at+4), ("elapsed", "Elapsed time:", at+4),
        ("errors", "Errors:", at+5), ("warnings", "Warnings:", at+5),
        ("start", "Start time:", start_at),
    ):
        for variant in (
            "prepend_same", "prepend_conflict", "interleave_same", "interleave_conflict",
            "append_same", "append_conflict", "substring_early", "leading_altered",
            "trailing_altered", "inline_duplicate", "nul", "bare_cr", "relocated",
        ):
            def mutate_provenance(a, index=index, token=token, variant=variant):
                original = a[index]
                if variant.startswith(("prepend_", "interleave_", "append_")):
                    pos = 0 if variant.startswith("prepend_") else at if variant.startswith("interleave_") else len(a)
                    extra = original.replace(token, token+"CONFLICT", 1) if variant.endswith("_conflict") else original
                    return a[:pos]+[extra]+a[pos:]
                if variant == "substring_early":
                    return ["untrusted<"+token+">fragment"]+a
                if variant == "relocated":
                    remaining = a[:index]+a[index+1:]
                    return [original]+remaining if index == len(a)-1 else remaining+[original]
                replacement = {
                    "leading_altered": "prefix "+original,
                    "trailing_altered": original+" suffix",
                    "inline_duplicate": original+" "+token,
                    "nul": original+"\x00", "bare_cr": original+"\rfragment",
                }[variant]
                return a[:index]+[replacement]+a[index+1:]
            mutations[label+"_"+variant] = mutate_provenance
    cases = []
    for name, mutate in mutations.items():
        altered = "\n".join(mutate(lines)) + "\n"
        raw_path = folder / (name + ".log")
        raw_path.write_bytes(altered.encode("utf-8"))
        try:
            check_saved(altered, iter(traces), fixture, tb_path, finish_line)
        except ValueError as e:
            cases.append(dict(name=name, rejected=True, error=str(e), raw=str(raw_path), sha256=sha(raw_path)))
        else:
            raise ValueError("false accept: " + name)
    changed = traces.copy()
    # Change a valid lane's data while retaining grammar, markers and counters.
    idx = next(i for i, line in enumerate(changed) if ROW.fullmatch(line.rstrip("\n\r"))[6] == "1")
    parts = changed[idx].split()
    parts[8] = f"{int(parts[8],16) ^ (1 << 100):047x}"
    parts[9] = parts[8]
    changed[idx] = " ".join(parts) + "\n"
    trace_cases = {
        "wrong_lane_tuple": (changed, dict(index=idx, replacement=changed[idx])),
        "missing_trace_row": (traces[1:], dict(remove_index=0)),
        "duplicate_trace_row": ([traces[0]]+traces, dict(insert_index=0, value=traces[0])),
        "extra_trace_row": (traces+[traces[-1]], dict(append=traces[-1])),
        "control_byte_trace": ([traces[0].replace(" PRE ", " PRE\x00 ")]+traces[1:], dict(index=0, replacement=traces[0].replace(" PRE ", " PRE\x00 "))),
    }
    for name, (altered, recipe) in trace_cases.items():
        try:
            check_saved(baseline, iter(altered), fixture, tb_path, finish_line)
        except ValueError as e:
            cases.append(dict(name=name, rejected=True, error=str(e), trace_base=str(trace_path),
                              trace_sha256=sha(trace_path), recipe=recipe))
        else:
            raise ValueError("false accept: " + name)
    crlf = "\r\n".join(lines)+"\r\n"
    check_saved(crlf, iter(traces), fixture, tb_path, finish_line)
    (folder / "positive-crlf.log").write_bytes(crlf.encode("utf-8"))
    unicode_path = str(Path(tb_path).parent / "语法正例" / Path(tb_path).name).replace("\\", "/")
    unicode_text = baseline.replace(str(tb_path).replace("\\", "/"), unicode_path)
    require(unicode_text != baseline, "Unicode grammar probe replaced actual path")
    check_saved(unicode_text, iter(traces), fixture, unicode_path, finish_line)
    (folder / "positive-unicode-grammar-only.log").write_bytes(unicode_text.encode("utf-8"))
    result = dict(negative_count=len(cases), false_accepts=0, negatives=cases,
                  positives=["unchanged actual transcript/trace", "CRLF transcript", "offline Unicode finish-path grammar only"],
                  limitation="Unicode probe is saved-log grammar only, not a vendor Unicode filesystem execution.")
    save(folder / "qualification.json", result)
    return dict(negative_count=len(cases), false_accepts=0, positive_count=3)


def run_process(out, name, argv, cwd, timeout=180):
    log = out / "processes"
    log.mkdir(exist_ok=True)
    meta = dict(argv=list(map(str, argv)), cwd=str(cwd), started_utc=datetime.now(timezone.utc).isoformat())
    before = time.monotonic()
    with (log / (name+".stdout.log")).open("wb") as stdout, (log / (name+".stderr.log")).open("wb") as stderr:
        proc = subprocess.Popen(meta["argv"], cwd=cwd, stdout=stdout, stderr=stderr, shell=False)
        meta["pid"] = proc.pid
        save(log / (name+".running.json"), meta)
        try:
            meta["exit_code"] = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            meta["exit_code"] = proc.wait()
            meta["timeout"] = True
    meta.update(ended_utc=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-before)
    meta["stdout"] = dict(path=str(log / (name+".stdout.log")), sha256=sha(log / (name+".stdout.log")))
    meta["stderr"] = dict(path=str(log / (name+".stderr.log")), sha256=sha(log / (name+".stderr.log")))
    save(log / (name+".json"), meta)
    require(meta["exit_code"] == 0 and not meta.get("timeout"), "process failed " + name)
    return meta


def execute(out):
    require(out.resolve().is_relative_to(AUTHOR.resolve()), "output must stay in exclusive author directory")
    out.mkdir(parents=True, exist_ok=False)
    result = dict(task=TASK, work=WORK, operation=OP, agent_id="01a16a34-b419-7942-9a7b-2b033142446b",
                  contract_requirements_sha256=CONTRACT, contract_ids=[f"H{i:02d}" for i in range(1,16)],
                  formal_cards={"total":29,"not_run":29}, parent_acceptance="pending independent main review",
                  synthesis="not_run", board="not_run", status="running", functional_repair_cycle=2,
                  python=dict(executable=sys.executable, version=sys.version, sha256=sha(sys.executable)))
    save(out / "RESULT.json", result)
    try:
        require(sha(PROTECTED) == PROTECTED_SHA, "protected worktree-root input differs")
        result["protected_input"] = dict(path=str(PROTECTED), before_sha256=sha(PROTECTED))
        for rel, expected in PINS.items():
            require(sha(ROOT/rel) == expected, "read-only pin differs " + rel)
        src = out / "source"
        src.mkdir()
        source_hashes = {}
        for rel in NEW + list(PINS):
            target = src / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/rel).read_bytes())
            source_hashes[rel] = dict(path=str(ROOT/rel), snapshot=str(target), sha256=sha(target))
        result["sources"] = source_hashes
        result["tool_hashes"] = {name:dict(path=str(TOOLS/(name+".exe")), sha256=sha(TOOLS/(name+".exe"))) for name in ("vlib","vmap","vlog","vsim")}
        tb = ROOT / NEW[1]
        finish_lines = [i for i, line in enumerate(tb.read_text(encoding="utf-8").splitlines(), 1) if "$finish;" in line]
        require(len(finish_lines) == 1, "unique actual TB finish source")
        result["finish_provenance"] = dict(path=str(tb).replace("\\","/"), line=finish_lines[0], iteration=1)
        sim = out / "sim"
        sim.mkdir()
        processes = []
        for name in ("vlog","vsim"):
            processes.append(run_process(out, name+"-version", [TOOLS/(name+".exe"), "-version"], sim))
        processes.append(run_process(out, "vmap-local", [TOOLS/"vmap.exe", "-c"], sim))
        processes.append(run_process(out, "vlib", [TOOLS/"vlib.exe", "work"], sim))
        processes.append(run_process(out, "vmap-work", [TOOLS/"vmap.exe", "work", "work"], sim))
        compile_sources = [ROOT / rel for rel in (NEW[0], *list(PINS)[:3], NEW[1])]
        processes.append(run_process(out, "vlog", [TOOLS/"vlog.exe", "-sv", "-work", "work", *compile_sources], sim))
        result["modes"] = []
        for fixture in (standalone_fixture(), integration_fixture()):
            folder = out / ("standalone" if fixture["mode"] == 0 else "integration39")
            stimulus = write_fixture(folder, fixture)
            trace_path = folder / "public.trace"
            transcript = folder / "modelsim.log"
            argv = [TOOLS/"vsim.exe", "-c", "-onfinish", "exit", "-wlf", folder/"wave.wlf",
                    "-l", transcript, "work.tb_scan_lane_stream", f"+MODE={fixture['mode']}",
                    "+INPUT="+str(stimulus), "+TRACE="+str(trace_path), "-do", "run -all; quit -f"]
            processes.append(run_process(out, "vsim-"+str(fixture["mode"]), argv, sim))
            text = transcript.read_bytes().decode("utf-8")
            with trace_path.open(encoding="ascii", newline="") as trace:
                checked = check_saved(text, trace, fixture, tb, finish_lines[0])
            save(folder / "checked.json", checked)
            qualification = qualify(folder/"qualifier", text, trace_path, fixture, tb, finish_lines[0])
            result["modes"].append(dict(mode=fixture["mode"], **checked, qualification=qualification,
                                        files={p.name:dict(path=str(p),sha256=sha(p)) for p in
                                               (folder/"fixture.json", stimulus, trace_path, transcript)}))
        for rel, entry in source_hashes.items():
            require(sha(ROOT/rel) == entry["sha256"], "source changed during run " + rel)
        require(sha(PROTECTED) == PROTECTED_SHA, "protected input changed during run")
        result["protected_input"]["after_sha256"] = sha(PROTECTED)
        result["processes"] = processes
        result["status"] = "pass"
    except Exception as e:
        result["status"] = "failed_preserved"
        result["error"] = type(e).__name__ + ": " + str(e)
        save(out / "RESULT.json", result)
        raise
    save(out / "RESULT.json", result)
    print(json.dumps(dict(status=result["status"], result=str(out/"RESULT.json"),
                          stats=[m["stats"] for m in result["modes"]]), ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    execute(parser.parse_args().out)
