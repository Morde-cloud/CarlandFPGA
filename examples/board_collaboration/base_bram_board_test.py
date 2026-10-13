#!/usr/bin/env python3
"""One-shot base-overlay AXI BRAM check. Only the authorized A board owner runs it.

MMIO observations are hardware reads, not driver caches. Cleanup restores the
post-load BRAM snapshot before releasing MicroBlaze reset. The previous FPGA
configuration is recorded, not restored. SIGKILL/power loss can prevent cleanup.
"""

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import platform
import random
import re
import sys

TASK_ID = "BOARD-20261013-A-B"
OPERATION_ID = "BOARD-20261013-A:B:base-bram-v2"
IP_NAME = "iop_pmoda/mb_bram_ctrl"
RESET_NAME = "mb_iop_pmoda_reset"
OFFSET, WORDS, ROUNDS = 0xFC00, 16, 3
EXPECTED_HASHES = {
    "bit": "ecabdcb5d483c75335ab6f043824a2386971c7b0ffd6e3315f24860bf5088eb6",
    "hwh": "cbd90c84f3a46d1eba95dff7ba7d0079812f7e46641a08e2318c9928cd36ce8f",
}
CAUGHT = (Exception, KeyboardInterrupt)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def patterns():
    rng = random.Random(0x20261013)
    tagged = [0xA5A50000 | i for i in range(WORDS)]
    return [
        ("zero", [0] * WORDS), ("ones", [0xFFFFFFFF] * WORDS),
        ("55", [0x55555555] * WORDS), ("aa", [0xAAAAAAAA] * WORDS),
        ("index", tagged), ("inverse", [v ^ 0xFFFFFFFF for v in tagged]),
        ("walking_one", [1 << i for i in range(WORDS)]),
        ("random_20261013", [rng.getrandbits(32) for _ in range(WORDS)]),
    ]


def metadata(overlay):
    ip = overlay.ip_dict[IP_NAME]
    if (ip.get("type") != "xilinx.com:ip:axi_bram_ctrl:4.1"
            or type(ip.get("phys_addr")) is not int or ip["phys_addr"] != 0x40000000
            or type(ip.get("addr_range")) is not int or ip["addr_range"] != 0x10000
            or ip.get("fullpath", IP_NAME) != IP_NAME):
        raise ValueError("BRAM metadata does not match the authorized 64 KiB AXI BRAM")
    index = overlay.gpio_dict[RESET_NAME]["index"]
    if type(index) is not int or index != 0:
        raise ValueError("Reset GPIO metadata differs from A's confirmed index 0")
    return {"ip": IP_NAME, "vlnv": ip["type"], "phys_addr": ip["phys_addr"],
            "addr_range": ip["addr_range"], "reset_name": RESET_NAME,
            "reset_index": index, "read_api": "pynq.MMIO.read"}


class SysfsReset:
    """Use GPIO.get_gpio_pin's result; never construct a mutating GPIO driver."""

    def __init__(self, pin, root=Path("/sys/class/gpio")):
        if type(pin) is not int or pin < 0:
            raise ValueError("Invalid resolved Linux GPIO number")
        self.pin, self.root = pin, Path(root)
        self.path = self.root / ("gpio" + str(pin))
        self.newly_exported = False
        self.initial = None

    def _read(self, name):
        return (self.path / name).read_text(encoding="ascii").strip()

    def _write(self, name, value):
        (self.path / name).write_text(str(value), encoding="ascii")

    def value(self):
        value = self._read("value")
        if value not in ("0", "1"):
            raise ValueError("Reset GPIO value is not binary")
        return int(value)

    def snapshot(self):
        if not self.path.exists():
            (self.root / "export").write_text(str(self.pin), encoding="ascii")
            self.newly_exported = True
        if (self.path / "active_low").exists() and self._read("active_low") != "0":
            raise ValueError("Inverted reset GPIO is not authorized")
        direction = self._read("direction")
        if direction not in ("in", "out"):
            raise ValueError("Reset GPIO direction is unavailable")
        self.initial = {"value": self.value(), "direction": direction,
                        "exported": not self.newly_exported,
                        "value_source": str(self.path / "value")}
        return dict(self.initial)

    def check_high(self):
        if self.value() != 1 or self._read("direction") != "out":
            raise RuntimeError("MicroBlaze reset is not asserted as output high")

    def hold(self):
        # Linux sysfs 'high' sets direction and initial value without a low pulse.
        self._write("direction", "high")
        self.check_high()

    def restore(self):
        initial = self.initial
        self._write("direction", "high" if initial["value"] else "low")
        if initial["direction"] == "in":
            self._write("direction", "in")
        observed = {"value": self.value(), "direction": self._read("direction")}
        if any(observed[k] != initial[k] for k in observed):
            raise RuntimeError("Reset restoration readback mismatch: " + str(observed))
        return observed

    def release_export(self):
        if self.newly_exported:
            (self.root / "unexport").write_text(str(self.pin), encoding="ascii")


def execute(bitstream, identity, *, pynq_module=None, reset_factory=SysfsReset,
            expected_hashes=EXPECTED_HASHES, evidence_kind="hardware"):
    """Return a JSON-safe report; dependencies are injectable for host mocks."""
    report = {
        "schema_version": 2, "task_id": TASK_ID, "task_version": 2,
        "work_id": "B-base-overlay-bramtest-v2", **identity,
        "started_utc": utc(), "evidence_kind": evidence_kind, "status": "failed",
        "runtime": {"python": platform.python_version(), "system": platform.system(),
                    "machine": platform.machine()},
        "files": {}, "samples": [], "errors": [], "expected_samples": 384,
        "restoration": {"words": [], "reset_restored": False,
                        "reset_restore_withheld": False},
        "original_configuration_restored": False,
    }
    reset, mmio, originals, mutated, active = None, None, [], False, None
    phase = "input_validation"

    def error(at, exc):
        item = {"phase": at, "type": type(exc).__name__, "message": str(exc)}
        report["errors"].append(item)
        return item

    def read_word(offset):
        value = int(mmio.read(offset))
        if not 0 <= value <= 0xFFFFFFFF:
            raise ValueError("MMIO returned a non-uint32 value")
        return value

    try:
        bit = Path(bitstream)
        if not bit.is_absolute() or bit.name != "base.bit":
            raise ValueError("An absolute existing base.bit path is required")
        for kind, path in (("bit", bit), ("hwh", bit.with_suffix(".hwh"))):
            observed = sha256(path)
            report["files"][kind] = {"path": str(path), "sha256": observed}
            if observed != expected_hashes[kind]:
                raise ValueError(kind + " SHA-256 does not match the authorized file")
        report["script_sha256"] = sha256(__file__)
        phase = "pynq_import"
        pynq = pynq_module or importlib.import_module("pynq")
        report["runtime"]["pynq"] = str(pynq.__version__)
        report["runtime"]["pynq_import_path"] = str(getattr(pynq, "__file__", "unknown"))

        def pl_identity():
            name, timestamp = pynq.PL.bitfile_name, pynq.PL.timestamp
            return {"bitfile_name": name, "timestamp": timestamp,
                    "identity_status": "known" if name else "unknown"}

        phase = "overlay_load"
        report["pre_load_overlay"] = pl_identity()
        overlay = pynq.Overlay(str(bit))  # Exactly one load; no BaseOverlay/hierarchy init.
        report["post_load_overlay"] = pl_identity()
        if not overlay.is_loaded():
            raise RuntimeError("Requested overlay is not loaded")
        phase = "metadata"
        source = report["source"] = metadata(overlay)
        pin = pynq.GPIO.get_gpio_pin(source["reset_index"])
        source["reset_linux_gpio"] = pin
        phase = "reset_snapshot"
        reset = reset_factory(pin)
        report["initial_reset"] = reset.snapshot()
        phase = "reset_assert"
        reset.hold()
        phase = "bram_snapshot"
        mmio = pynq.MMIO(source["phys_addr"], source["addr_range"])
        for i in range(WORDS):
            originals.append(read_word(OFFSET + 4 * i))
        report["original_words"] = originals.copy()
        reset.check_high()
        batches = patterns()
        for round_number in range(1, ROUNDS + 1):
            for batch_name, values in batches:
                active = None
                phase = "reset_before_batch"
                reset.check_high()
                batch = [{"round": round_number, "batch": batch_name, "index": i,
                          "offset": OFFSET + 4 * i,
                          "physical_address": source["phys_addr"] + OFFSET + 4 * i,
                          "read_source": "pynq.MMIO.read", "expected": value,
                          "observed": None, "passed": False, "write_completed": False}
                         for i, value in enumerate(values)]
                report["samples"].extend(batch)
                phase = "test_write"
                for active in batch:
                    mutated = True  # A raising write may still have changed hardware.
                    mmio.write(active["offset"], active["expected"])
                    active["write_completed"] = True
                active = None
                phase = "reset_after_writes"
                reset.check_high()
                phase = "test_read"
                for active in batch:
                    active["observed"] = read_word(active["offset"])
                    active["passed"] = active["observed"] == active["expected"]
                active = None
                phase = "reset_after_batch"
                reset.check_high()
    except CAUGHT as exc:
        item = error(phase, exc)
        if active is not None:
            active["error"] = item
    finally:
        restoration = report["restoration"]
        safe_to_release = not mutated
        if mutated and len(originals) == WORDS:
            entries = [{"index": i, "offset": OFFSET + 4 * i, "expected": value,
                        "physical_address": report["source"]["phys_addr"] + OFFSET + 4 * i,
                        "read_source": "pynq.MMIO.read",
                        "observed": None, "passed": False, "write_completed": False}
                       for i, value in enumerate(originals)]
            restoration["words"] = entries
            held = False
            try:
                reset.hold()
                held = True
            except CAUGHT as exc:
                error("restore_reset_assert", exc)
            if held:
                for entry in entries:
                    try:
                        mmio.write(entry["offset"], entry["expected"])
                        entry["write_completed"] = True
                    except CAUGHT as exc:
                        entry["write_error"] = error("restore_word_write", exc)
                for entry in entries:
                    try:
                        entry["observed"] = read_word(entry["offset"])
                        entry["passed"] = entry["observed"] == entry["expected"]
                    except CAUGHT as exc:
                        entry["read_error"] = error("restore_word_read", exc)
                try:
                    reset.check_high()
                except CAUGHT as exc:
                    held = False
                    error("restore_reset_hold", exc)
            safe_to_release = held and all(e["passed"] and e["write_completed"] for e in entries)
            restoration["bram_restored"] = safe_to_release
        if reset is not None:
            if safe_to_release:
                try:
                    if reset.initial is not None:
                        restoration["reset_observed"] = reset.restore()
                        restoration["reset_restored"] = True
                    reset.release_export()
                    restoration["export_state_restored"] = True
                except CAUGHT as exc:
                    restoration["reset_restored"] = False
                    error("restore_reset", exc)
            else:
                restoration["reset_restore_withheld"] = True
                error("restore_reset_withheld", RuntimeError("BRAM restoration unverified; keep reset asserted"))
                try:
                    reset.hold()
                    restoration["reset_held_after_failure"] = True
                except CAUGHT as exc:
                    restoration["reset_held_after_failure"] = False
                    error("restore_emergency_hold", exc)
        report["observed_samples"] = sum(s["observed"] is not None for s in report["samples"])
        report["matching_samples"] = sum(s["passed"] for s in report["samples"])
        if (len(report["samples"]) == 384 and report["matching_samples"] == 384
                and not report["errors"] and restoration.get("bram_restored")
                and restoration["reset_restored"] and restoration.get("export_state_restored")):
            report["status"] = "passed"
        report["finished_utc"] = utc()
    return report


def hex_argument(length):
    def validate(value):
        if not re.fullmatch("[0-9a-f]{" + str(length) + "}", value):
            raise argparse.ArgumentTypeError("Expected " + str(length) + " lowercase hex characters")
        return value
    return validate


def main(argv=None, runner=execute):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bitstream", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--operation-id", required=True, choices=[OPERATION_ID])
    parser.add_argument("--request-hash", required=True, type=hex_argument(64))
    parser.add_argument("--code-commit", required=True, type=hex_argument(40))
    parser.add_argument("--tested-commit", required=True, type=hex_argument(40))
    args = parser.parse_args(argv)
    identity = {k: getattr(args, k) for k in ("operation_id", "request_hash", "code_commit", "tested_commit")}
    try:
        output = Path(args.output).open("x", encoding="utf-8", newline="\n")
    except OSError as exc:
        print(json.dumps({**identity, "status": "failed", "error": str(exc), "phase": "output_reservation"}))
        return 2
    with output:
        # Libraries may print diagnostics; stdout remains one machine-readable JSON.
        with redirect_stdout(sys.stderr):
            result = runner(args.bitstream, identity)
        content = json.dumps(result, sort_keys=True, indent=2) + "\n"
        output.write(content)
        output.flush()
    print(content, end="")
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
