"""Bounded private source4 collector. Default: offline checks, no PYNQ import.

Only A may use --execute-a. An injected runtime is explicitly software evidence.
This is a diagnostic, never formal product or causal-observation acceptance.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import sys
import time
import xml.etree.ElementTree as ET

TASK = "DEEPEYE-IMPLEMENTATION-20261014"
WORK = "B-MINIMAL-PL-COLLECTOR-20261025-55-v1"
CONTRACT = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
DESIGN = "1011259415a0916054eb580687612580bc1e5f09"
INSTANCE = "private_diag_0"
VLNV = "carlandfpga.local:diagnostic:deepeye_private_axi_diag:1.0"
U32 = (1 << 32) - 1
SOURCES = (
    "fpga/acquisition/deepeye_buffered_scan_capture.sv",
    "fpga/acquisition/deepeye_sample_scan_capture.sv",
    "fpga/acquisition/deepeye_raw_scan_queue.sv",
    "fpga/acquisition/deepeye_scan_lane_stream.sv",
    "fpga/diagnostic/deepeye_private_axi_diag.sv",
)
PINS = (
    "c8a540db8122b8f5520582a0f1fa9be0c43cb54a62f03c7c4edc893906f28411",
    "fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d",
    "630e14803d82b3379517d91626de4ad7e7d3c509ad14363b3164031a5f633ee4",
    "b3c9d2024d9325191538cf08fec9a652ff8ff0ae316ec9af96078f85cf5be3cc",
)
BIT = "artifacts/private_diag.bit"
HWH = "artifacts/private_diag.hwh"
REQUIRED_ARTIFACTS = (
    BIT, HWH, "artifacts/private_diag_routed.dcp", "BD_MAPPING.json",
    "VIVADO_COMPLETE.json", "tool_version.txt", "constraints/private_diag.xdc",
    "reports/route_timing_summary.txt", "reports/route_check_timing.txt",
    "reports/route_utilization.txt", "reports/route_drc.txt",
    "reports/route_clocks.txt", "reports/route_status.txt",
)
RESULT_REGS = (0x80, 0x84, 0x88, 0x8C, 0x90, 0x94, 0x98, 0x9C, 0xA0, 0xA4)
READ_REGS = frozenset((0, 4, 8, 0x10, 0x14, 0x18, 0x1C, 0x20,
                      0x24, 0x28, 0x30, 0x34) + RESULT_REGS)
WRITE_REGS = frozenset((0x0C, 0x10, 0x40, 0x44, 0x48, 0x4C,
                       0x50, 0x54, 0x58, 0x5C, 0x60, 0x64, 0x68, 0x6C, 0x70))
MAX_JSON = 8 * 1024 * 1024
MAX_HWH = 16 * 1024 * 1024
MAX_FILE = 256 * 1024 * 1024
MAX_SELECTED_TOTAL = 512 * 1024 * 1024


class Rejected(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Rejected(message)


def uint(value, bits, name):
    require(type(value) is int and 0 <= value < (1 << bits), name + " must be uint" + str(bits))
    return value


def exact(value, keys, name):
    require(type(value) is dict and set(value) == set(keys), name + " fields mismatch")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sha_text(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "invalid SHA256")
    return value


def loads(data, name):
    require(len(data) <= MAX_JSON, name + " JSON too large")

    def pairs(items):
        obj = {}
        for key, value in items:
            require(key not in obj, name + " duplicate JSON key: " + key)
            obj[key] = value
        return obj

    def constant(value):
        raise Rejected(name + " nonfinite JSON number: " + value)

    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=constant)


def identifier(value, name):
    require(type(value) is str and 1 <= len(value) <= 256 and
            value == value.strip() and all(ord(c) >= 32 for c in value), name + " invalid")
    return value


@dataclass(frozen=True)
class Scan:
    values: tuple
    ticks: tuple
    qualities: tuple


@dataclass(frozen=True)
class Fixture:
    run_id: str
    session_id: str
    nonce: str
    tag: int
    scans: tuple


def fixture_from_bytes(data):
    obj = loads(data, "fixture")
    exact(obj, ("schema_version", "source_id", "source", "topology_id", "a_reference", "tag", "scans"), "fixture")
    require(uint(obj["schema_version"], 8, "schema_version") == 1, "fixture schema version")
    require(uint(obj["source_id"], 8, "source_id") == 4 and obj["source"] == "software_fixture", "source4 software_fixture only")
    require(uint(obj["topology_id"], 8, "topology_id") == 2, "topology2 only")
    ref = obj["a_reference"]
    exact(ref, ("run_id", "session_id", "nonce"), "a_reference")
    names = tuple(identifier(ref[k], k) for k in ("run_id", "session_id", "nonce"))
    tag = uint(obj["tag"], 32, "tag")
    require(tag != 0, "tag must be nonzero; A binds it to its full ledger")
    require(type(obj["scans"]) is list and 1 <= len(obj["scans"]) <= 16, "scans must contain 1..16 scans")
    scans = []
    for item in obj["scans"]:
        exact(item, ("values", "original_host_qpc_ns", "qualities"), "scan")
        arrays = []
        for key, bits in (("values", 16), ("original_host_qpc_ns", 64), ("qualities", 8)):
            values = item[key]
            require(type(values) is list and len(values) == 4, key + " must have exactly four values")
            arrays.append(tuple(uint(v, bits, key) for v in values))
        scans.append(Scan(*arrays))
    return Fixture(*names, tag, tuple(scans))


def no_links(path):
    """Reject symlinks/junctions in existing components; never follow an alias."""
    path = Path(os.path.abspath(path))
    for part in (path,) + tuple(path.parents):
        if part.exists() or part.is_symlink():
            stat = part.lstat()
            require(not part.is_symlink() and not (getattr(stat, "st_file_attributes", 0) & 0x400),
                    "symlink/reparse input or output: " + str(part))
    return path


def relative_name(value):
    require(type(value) is str and value and "\\" not in value and ":" not in value,
            "nonportable package path")
    p = PurePosixPath(value)
    require(not p.is_absolute() and all(x not in ("", ".", "..") for x in value.split("/")), "unsafe package path")
    return value


def number(value, name):
    if type(value) is int:
        return uint(value, 32, name)
    require(type(value) is str and re.fullmatch(r"0x[0-9a-fA-F]+|[0-9]+", value), name + " malformed")
    return uint(int(value, 16 if value.startswith("0x") else 10), 32, name)


@dataclass(frozen=True)
class Blob:
    name: str
    data: bytes
    digest: str


@dataclass(frozen=True)
class Validated:
    fixture: Fixture
    base: int
    span: int
    build_run_id: str
    manifest_sha256: str
    fixture_sha256: str
    blobs: tuple


class Reader:
    def __init__(self, output):
        self.output = output
        self.identities = set()
        self.total = 0

    def read(self, path, limit=MAX_FILE):
        p = no_links(path)
        require(p.is_file(), "missing regular input: " + str(p))
        require(not self.output.is_relative_to(p) and not p.is_relative_to(self.output), "output aliases input")
        with p.open("rb") as f:
            stat = os.fstat(f.fileno())
            identity = (stat.st_dev, stat.st_ino)
            require(identity not in self.identities and stat.st_nlink == 1, "input path/hardlink alias")
            require(0 < stat.st_size <= limit and self.total + stat.st_size <= MAX_SELECTED_TOTAL, "input size limit")
            data = f.read(limit + 1)
            after = os.fstat(f.fileno())
        require(len(data) == stat.st_size and len(data) <= limit and
                (stat.st_size, stat.st_mtime_ns, stat.st_ino) ==
                (after.st_size, after.st_mtime_ns, after.st_ino), "input changed during snapshot")
        self.identities.add(identity)
        self.total += len(data)
        return data


def hwh_identity(data, mapping):
    require(len(data) <= MAX_HWH, "HWH too large")
    # Decode before rejecting declarations so UTF16/32 cannot hide a DTD.
    require(b"\x00" not in data, "HWH must use UTF-8 compatible XML")
    require(not re.search(br"<!\s*(DOCTYPE|ENTITY)\b", data, re.I), "HWH DTD/entity forbidden")
    xml = ET.fromstring(data)
    require(sum(1 for _ in xml.iter()) <= 100000, "HWH element limit")
    modules = [m for m in xml.iter("MODULE") if m.get("FULLNAME", "").strip("/") == INSTANCE]
    require(len(modules) == 1 and modules[0].get("VLNV") == VLNV, "HWH private instance/VLNV mismatch")
    ranges = [r for r in xml.iter("MEMRANGE") if r.get("INSTANCE", "").strip("/") == INSTANCE]
    require(len(ranges) == 1 and ranges[0].get("SLAVEBUSINTERFACE") == "S_AXI", "HWH ambiguous private range")
    base = number(ranges[0].get("BASEVALUE"), "HWH base")
    high = number(ranges[0].get("HIGHVALUE"), "HWH high")
    require(base % 4096 == 0 and high - base + 1 == 4096, "HWH must have one aligned 4KiB range")
    require(type(mapping) is dict and number(mapping.get("base"), "BD base") == base and
            number(mapping.get("range"), "BD range") == 4096, "same-build BD_MAPPING differs from HWH")
    return base, 4096


def validate(package, manifest_path, expected_sha, fixture_path, output):
    package = no_links(package)
    output = no_links(output)
    require(package.is_dir() and not output.is_relative_to(package) and not package.is_relative_to(output),
            "output and package must be disjoint")
    manifest_path = no_links(manifest_path)
    require(manifest_path == package / "ARTIFACT_MANIFEST.json", "explicit canonical manifest path required")
    reader = Reader(output)
    manifest_bytes = reader.read(manifest_path, MAX_JSON)
    require(sha(manifest_bytes) == sha_text(expected_sha), "A-supplied exact manifest hash mismatch")
    m = loads(manifest_bytes, "manifest")
    require(type(m) is dict and m.get("status") == "completed_build_pending_main_review", "completed build status required")
    require(m.get("task_id") == TASK and type(m.get("task_version")) is int and m["task_version"] == 1 and
            m.get("work_id") == "B-MINIMAL-PL-BUILD-PREP-20261025-54-v1", "manifest task/work mismatch")
    require(m.get("requirements_sha256") == CONTRACT and m.get("requirement_ids") ==
            [f"H{i:02}" for i in range(1, 16)] and m.get("design_commit") == DESIGN, "contract/design mismatch")
    require(m.get("all_29_formal_acceptance") == "not_run" and m.get("physical_board") == "not_run; A-only", "build is not acceptance")
    pins = m.get("expected_rtl_sha256")
    exact(pins, SOURCES, "five-source SHA map")
    for name, expected in zip(SOURCES, PINS):
        require(pins[name] == expected, "fixed readonly RTL pin mismatch")
    for value in pins.values():
        sha_text(value)
    files, artifacts = m.get("files"), m.get("artifacts")
    require(type(files) is dict and 1 <= len(files) <= 20000 and type(artifacts) is dict, "missing bounded file inventory")
    for key in files:
        relative_name(key)
    selected = set(REQUIRED_ARTIFACTS) | {"PROCESS.json", "PREPARATION.json"}
    selected |= {"inputs/rtl/" + name for name in SOURCES}
    selected |= {"inputs/build_private_diag.py", "inputs/build_private_diag.tcl"}
    blobs = [Blob("ARTIFACT_MANIFEST.json", manifest_bytes, sha(manifest_bytes))]
    checked = {}
    for name in sorted(selected):
        require(name in files, "manifest missing selected file: " + name)
        rec = files[name]
        require(type(rec) is dict, "file record malformed")
        expected = sha_text(rec.get("sha256"))
        expected_size = uint(rec.get("bytes"), 64, "file bytes")
        # Absolute sender paths are provenance only, never receiver paths.
        if name in REQUIRED_ARTIFACTS:
            require(name in artifacts and artifacts[name] == rec, "artifact/file pairing mismatch: " + name)
        data = reader.read(package / name, MAX_HWH if name == HWH else (MAX_JSON if name.endswith(".json") else MAX_FILE))
        require(len(data) == expected_size and sha(data) == expected, "package hash/size mismatch: " + name)
        checked[name] = data
        blobs.append(Blob(name, data, expected))
    for key, name in (("process", "PROCESS.json"), ("inputs", "PREPARATION.json")):
        require(m.get(key) == files[name], "manifest proof pairing mismatch: " + name)
    for name in SOURCES:
        require(sha(checked["inputs/rtl/" + name]) == pins[name], "source snapshot differs from build pin")
    process = loads(checked["PROCESS.json"], "process")
    require(type(process) is dict and type(process.get("exit_code")) is int and process["exit_code"] == 0 and
            process.get("timed_out") is False and process.get("termination_confirmed") is True and
            not process.get("process_error"), "build process did not complete")
    complete = loads(checked["VIVADO_COMPLETE.json"], "completion")
    require(type(complete) is dict, "completion proof malformed")
    run_id = identifier(complete.get("run_id"), "build run_id")
    mapping = loads(checked["BD_MAPPING.json"], "mapping")
    base, span = hwh_identity(checked[HWH], mapping)
    private = m.get("private_ip")
    require(type(private) is dict and private.get("instance") == INSTANCE and private.get("vlnv") == VLNV and
            number(private.get("base"), "manifest base") == base and
            type(private.get("range")) is int and private["range"] == span, "manifest/HWH identity mismatch")
    fixture_bytes = reader.read(fixture_path, MAX_JSON)
    fixture = fixture_from_bytes(fixture_bytes)
    blobs.append(Blob("fixture.json", fixture_bytes, sha(fixture_bytes)))
    return Validated(fixture, base, span, run_id, sha(manifest_bytes), sha(fixture_bytes), tuple(blobs))


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")


def snapshot(validated, output):
    root = output / "snapshots"
    root.mkdir(exist_ok=False)
    for blob in validated.blobs:
        dest = root / blob.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("xb") as f:
            f.write(blob.data)
            f.flush()
            os.fsync(f.fileno())
    # Same stem in the same fresh directory: PYNQ reads this checked HWH.
    return root / BIT


class Journal:
    def __init__(self, path, clock):
        self.file = path.open("x", encoding="utf-8", newline="\n", buffering=1)
        self.clock = clock
        self.index = 0

    def event(self, event, **fields):
        rec = {"index": self.index, "event": event, "collector_monotonic_ns": int(self.clock() * 1000000000),
               "clock_role": "local execution timing; never original_host_qpc_ns", **fields}
        self.index += 1
        self.file.write(json.dumps(rec, sort_keys=True, allow_nan=False) + "\n")
        self.file.flush()

    def close(self):
        self.file.close()


class Bus:
    def __init__(self, mmio, journal):
        self.mmio, self.journal = mmio, journal

    def action(self, kind, offset, value=None):
        require(offset in (READ_REGS if kind == "read" else WRITE_REGS), "forbidden private offset")
        fields = {"operation": kind, "offset": hex(offset)}
        if kind == "write":
            fields["value"] = uint(value, 32, "MMIO word")
        self.journal.event("mmio_attempt", **fields)
        try:
            result = self.mmio.read(offset) if kind == "read" else self.mmio.write(offset, value)
            if kind == "read":
                fields["value"] = uint(result, 32, "MMIO read")
            self.journal.event("mmio_returned", **fields)
            return result
        except BaseException as exc:
            self.journal.event("mmio_failed", **fields, error=f"{type(exc).__name__}: {exc}")
            raise

    def read(self, offset):
        return self.action("read", offset)

    def write(self, offset, value):
        return self.action("write", offset, value)


class PynqRuntime:
    def __init__(self):
        # Reached only after validation, snapshots and the explicit A action.
        from pynq import MMIO, Overlay
        self.Overlay, self.MMIO = Overlay, MMIO

    def overlay(self, path):
        return self.Overlay(str(path), download=False)

    def mmio(self, base, span):
        return self.MMIO(base, span)


def check_overlay(overlay, validated):
    ips = overlay.ip_dict
    require(type(ips) is dict, "PYNQ ip_dict missing")
    matches = [(key, item) for key, item in ips.items() if key.strip("/") == INSTANCE or
               (type(item) is dict and str(item.get("fullpath", "")).strip("/") == INSTANCE)]
    require(len(matches) == 1, "PYNQ private instance ambiguous/missing")
    key, item = matches[0]
    require(type(item) is dict and key.strip("/") == INSTANCE and
            item.get("fullpath", "").strip("/") == INSTANCE and item.get("type") == VLNV and
            uint(item.get("phys_addr"), 32, "PYNQ base") == validated.base and
            uint(item.get("addr_range"), 32, "PYNQ range") == validated.span, "PYNQ metadata differs from checked HWH")


def wait_for(bus, predicate, clock, sleep, deadline, label, check_fault=True):
    for _ in range(30001):
        require(clock() < deadline, "timeout: " + label)
        status = bus.read(8)
        require(status & ~15 == 0, "unknown status bits")
        if check_fault:
            require(status & 8 == 0, "PL diagnostic fault")
        if predicate(status):
            return status
        sleep(0.001)
    raise Rejected("poll bound: " + label)


def counters(bus):
    return tuple(bus.read(offset) for offset in (0x24, 0x28, 0x30))


def session(bus, tag, generation, trigger):
    require((bus.read(0x14), bus.read(0x18), bus.read(0x1C)) == (tag, generation, trigger), "active session/generation/trigger changed")


def capture(bus, fixture, report, clock, sleep, poll_seconds, total_seconds):
    end = clock() + total_seconds

    def deadline():
        return min(end, clock() + poll_seconds)

    require(bus.read(0) == 0x44505953 and bus.read(4) == 0x00010000, "private magic/version mismatch")
    bus.write(0x0C, 1)
    wait_for(bus, lambda s: s & 7 == 0, clock, sleep, deadline(), "startup STOP")
    require(bus.read(0x14) == 0, "startup STOP active_tag not zero")
    old_generation = bus.read(0x18)
    require(old_generation < U32, "generation exhausted; no reset/reload retry")
    bus.write(0x10, fixture.tag)
    require(bus.read(0x10) == fixture.tag, "staged tag differs")
    bus.write(0x0C, 2)
    wait_for(bus, lambda s: s == 1, clock, sleep, deadline(), "START running")
    generation = old_generation + 1
    previous_trigger = bus.read(0x1C)
    session(bus, fixture.tag, generation, previous_trigger)
    baseline = counters(bus)
    scans = len(fixture.scans)
    require(all(b + inc <= U32 for b, inc in zip(baseline, (4 * scans, scans, 4 * scans))), "diagnostic counter exhaustion")
    report.update(generation=generation, baseline_counters=baseline, captures=[])
    for scan_index, scan in enumerate(fixture.scans):
        require(clock() < end, "total capture timeout")
        require(bus.read(8) == 1, "not idle before stage")
        session(bus, fixture.tag, generation, previous_trigger)
        require(previous_trigger < U32, "trigger id exhausted")
        for channel in range(4):
            bus.write(0x40 + channel * 4, scan.values[channel])
            bus.write(0x50 + channel * 8, scan.ticks[channel] & U32)
            bus.write(0x54 + channel * 8, scan.ticks[channel] >> 32)
        bus.write(0x70, sum(q << (8 * i) for i, q in enumerate(scan.qualities)))
        require(bus.read(8) == 1, "state changed while staging")
        session(bus, fixture.tag, generation, previous_trigger)
        bus.write(0x0C, 4)  # Exactly one TRIGGER attempt; failures are never replayed.
        trigger = bus.read(0x1C)
        require(trigger == previous_trigger + 1, "TRIGGER did not produce the next actual id")
        session(bus, fixture.tag, generation, trigger)
        for channel in range(4):
            wait_for(bus, lambda s: s == 7, clock, sleep, deadline(), "result lane")
            raw = tuple(bus.read(offset) for offset in RESULT_REGS)
            require(bus.read(8) == 7, "result_valid/status changed during read")
            session(bus, fixture.tag, generation, trigger)
            require(tuple(bus.read(offset) for offset in RESULT_REGS) == raw and bus.read(8) == 7,
                    "result changed before ACK")
            session(bus, fixture.tag, generation, trigger)
            expected = (scan.values[channel], channel | (scan.qualities[channel] << 8),
                        scan.ticks[channel] & U32, scan.ticks[channel] >> 32,
                        4 * scan_index, 4 * scan_index + 3, fixture.tag, trigger, generation)
            require(raw[:9] == expected, "raw lane data/channel/quality/QPC/sequence/session mismatch")
            expected_counts = (baseline[0] + 4 * (scan_index + 1), baseline[1] + scan_index + 1,
                               baseline[2] + 4 * scan_index + channel + 1)
            require(counters(bus) == expected_counts, "capture/queue/lane counters do not prove pipeline progress")
            record = {"scan_index": scan_index, "channel": channel, "value": raw[0],
                      "opaque_quality": raw[1] >> 8, "original_host_qpc_ns": (raw[3] << 32) | raw[2],
                      "first_seq": raw[4], "last_seq": raw[5], "tag": raw[6], "trigger_id": raw[7],
                      "generation": raw[8], "pl_result_latch_cycle_diagnostic": raw[9],
                      "pipeline_counters": expected_counts, "ack_returned": False}
            report["captures"].append(record)
            bus.write(0x0C, 8)  # One ACK per verified actual lane.
            record["ack_returned"] = True
        wait_for(bus, lambda s: s == 1, clock, sleep, deadline(), "four ACKs idle")
        session(bus, fixture.tag, generation, trigger)
        require(counters(bus) == expected_counts, "post-ACK counters changed")
        previous_trigger = trigger
    report["final_counters"] = counters(bus)


def collect(package, manifest, manifest_sha256, fixture_path, output, *, execute_a=False,
            runtime_factory=None, clock=time.monotonic, sleep=time.sleep,
            poll_seconds=2.0, total_seconds=60.0):
    require(type(execute_a) is bool, "explicit execution flag required")
    require(type(poll_seconds) in (int, float) and 0 < poll_seconds <= 10 and
            type(total_seconds) in (int, float) and 0 < total_seconds <= 180, "timeout bounds")
    require(execute_a or runtime_factory is None, "injected runtime requires explicit execution")
    out = no_links(output)
    require(not out.exists(), "output exists; exclusive new evidence directory required")
    for path in (package, manifest, fixture_path):
        p = no_links(path)
        require(not out.is_relative_to(p) and not p.is_relative_to(out), "output/input overlap")
    out.mkdir(parents=True, exist_ok=False)
    mode = "software_fake_runtime" if runtime_factory is not None else ("explicit_A_runtime" if execute_a else "offline_verification")
    result = {"task_id": TASK, "task_version": 1, "work_id": WORK, "mode": mode,
              "requirements_sha256": CONTRACT, "requirement_ids": [f"H{i:02}" for i in range(1, 16)],
              "formal_product_acceptance": "not_run", "all_29_formal_acceptance": "not_run",
              "R03": "not_run", "full_H12": "not_run", "causal_live_freshness": "not_established",
              "physical_board": "not_run" if mode != "explicit_A_runtime" else "A_runtime_requested; diagnostic_only",
              "automatic_retry": False, "status": "failed", "exit_code": 2,
              "cleanup": {"attempted": False, "confirmed": False, "reason": "MMIO not established"}}
    write_json(out / "INTENT.json", {**result, "package": str(package), "manifest": str(manifest),
                                   "fixture": str(fixture_path), "expected_manifest_sha256": manifest_sha256,
                                   "python": sys.version, "argv": sys.argv, "poll_seconds": poll_seconds,
                                   "total_seconds": total_seconds, "pid": os.getpid()})
    journal = Journal(out / "operations.jsonl", clock)
    bus = None
    primary = None
    try:
        verified = validate(package, manifest, manifest_sha256, fixture_path, out)
        bit_path = snapshot(verified, out)
        result["validation"] = {"manifest_sha256": verified.manifest_sha256,
                                "fixture_sha256": verified.fixture_sha256, "build_run_id": verified.build_run_id,
                                "instance": INSTANCE, "vlnv": VLNV, "base": hex(verified.base), "range": verified.span,
                                "a_reference": {"run_id": verified.fixture.run_id, "session_id": verified.fixture.session_id,
                                                "nonce": verified.fixture.nonce}, "tag": verified.fixture.tag,
                                "selected_snapshots": [{"path": b.name, "sha256": b.digest, "bytes": len(b.data)} for b in verified.blobs],
                                "manifest_format": "draft54 read hash recorded in author inputs; final main binding required"}
        journal.event("offline_validation_complete")
        if execute_a:
            journal.event("runtime_import_attempt")
            runtime = (runtime_factory or PynqRuntime)()
            journal.event("overlay_inspect_attempt", bit_snapshot=str(bit_path), download=False)
            overlay = runtime.overlay(bit_path)
            check_overlay(overlay, verified)
            journal.event("download_attempt", bit_snapshot=str(bit_path))
            overlay.download()  # One explicit download of fresh checked output bytes.
            journal.event("download_returned")
            check_overlay(overlay, verified)
            journal.event("mmio_construct_attempt", base=verified.base, span=verified.span)
            mmio = runtime.mmio(verified.base, verified.span)
            bus = Bus(mmio, journal)
            journal.event("mmio_established")
            capture(bus, verified.fixture, result, clock, sleep, poll_seconds, total_seconds)
            result["status"] = "software_fake_capture_complete" if runtime_factory else "private_diagnostic_capture_complete"
        else:
            result["status"] = "verified_offline_only"
        result["exit_code"] = 0
    except BaseException as exc:
        primary = exc
        result["error"] = {"type": type(exc).__name__, "message": str(exc)}
        journal.event("primary_failure", **result["error"])
    finally:
        if bus is not None:
            cleanup = {"attempted": True, "confirmed": False}
            # Keep a second signal from hiding the first failure during bounded STOP.
            handlers = {}
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    handlers[sig] = signal.signal(sig, signal.SIG_IGN)
                except ValueError:  # Library use outside the main thread.
                    pass
            try:
                bus.write(0x0C, 1)
                stop_status = wait_for(bus, lambda s: s & 7 == 0, clock, sleep,
                                       clock() + poll_seconds, "final STOP", check_fault=False)
                require(bus.read(0x14) == 0, "final STOP active_tag not zero")
                cleanup.update(confirmed=True, status=stop_status, active_tag=0)
            except BaseException as exc:
                cleanup["error"] = {"type": type(exc).__name__, "message": str(exc)}
                journal.event("stop_failure", **cleanup["error"])
                result["exit_code"] = 2
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
            result["cleanup"] = cleanup
        if primary is not None or result["exit_code"] != 0:
            result["status"] = "failed"
        journal.event("collector_finished", status=result["status"], exit_code=result["exit_code"])
        journal.close()
        write_json(out / "RESULT.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True, help="A's independently selected exact manifest bytes")
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="new directory outside package and inputs")
    parser.add_argument("--execute-a", action="store_true", help="A only: download once and perform private MMIO")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--total-seconds", type=float, default=60.0)
    args = parser.parse_args(argv)

    def interrupted(signum, frame):
        raise InterruptedError("signal " + str(signum) + "; STOP if MMIO established")

    handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        result = collect(args.package, args.manifest, args.manifest_sha256, args.fixture, args.out,
                         execute_a=args.execute_a, poll_seconds=args.poll_seconds, total_seconds=args.total_seconds)
        print(json.dumps({"status": result["status"], "exit_code": result["exit_code"], "out": str(args.out),
                          "formal_product_acceptance": "not_run"}))
        return result["exit_code"]
    except BaseException as exc:
        print(json.dumps({"status": "rejected_before_run", "error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 2
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
