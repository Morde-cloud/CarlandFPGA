"""Host-only, fault-injected tests; no PYNQ installation or board access."""

from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

SOURCE = Path(__file__).resolve().parents[1] / "examples/board_collaboration/base_bram_board_test.py"
spec = importlib.util.spec_from_file_location("base_bram_board_test", SOURCE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
IDENTITY = {"operation_id": probe.OPERATION_ID, "request_hash": "a" * 64,
            "code_commit": "b" * 40, "tested_commit": "c" * 40}
HWH = """<SYSTEM><MODULES>
<MODULE FULLNAME="/iop_pmoda/mb_bram_ctrl" INSTANCE="iop_pmoda_mb_bram_ctrl"
 VLNV="xilinx.com:ip:axi_bram_ctrl:4.1"><PARAMETERS>
 <PARAMETER NAME="C_S_AXI_BASEADDR" VALUE="0x40000000"/>
 <PARAMETER NAME="C_S_AXI_HIGHADDR" VALUE="0x4000FFFF"/>
</PARAMETERS></MODULE>
<MODULE FULLNAME="/processing_system7_0" MODTYPE="processing_system7">
<MEMRANGES><MEMRANGE INSTANCE="iop_pmoda_mb_bram_ctrl" MASTERBUSINTERFACE="M_AXI_GP0"
 SLAVEBUSINTERFACE="S_AXI" MEMTYPE="MEMORY" ADDRESSBLOCK="Mem0"
 BASEVALUE="0x40000000" HIGHVALUE="0x4000FFFF"/></MEMRANGES>
</MODULE></MODULES></SYSTEM>"""


class FakeHardware:
    def __init__(self):
        self.events, self.reads, self.writes = [], 0, 0
        self.memory = {0xFC00 + 4 * i: 0x12340000 + i for i in range(16)}
        self.original = self.memory.copy()
        self.fail_reads, self.fail_writes = {}, {}
        self.bad_read = None
        self.alias = False
        self.value, self.direction = 0, "out"
        self.initial = None
        self.checks = 0
        self.fail_checks = set()
        self.unholdable_after_write = False
        self.ip_dict = {probe.IP_NAME: {"type": "xilinx.com:ip:axi_bram_ctrl:4.1",
                        "phys_addr": 0x40000000, "addr_range": 0x10000,
                        "fullpath": probe.IP_NAME}}
        self.gpio_dict = {probe.RESET_NAME: {"index": 0, "pins": {
            "mb_iop_pmoda_reset/Dout", "iop_pmoda/rst_clk_wiz_1_100M/aux_reset_in"}}}
        self.mem_dict = {}
        self.module = SimpleNamespace(
            __version__="3.0.1", __file__="host_mock/pynq/__init__.py",
            PL=SimpleNamespace(bitfile_name=None, timestamp=None),
            Overlay=Mock(side_effect=self.load), MMIO=Mock(return_value=self),
            GPIO=SimpleNamespace(get_gpio_pin=Mock(return_value=906)))

    def load(self, name):
        self.events.append(("load", name))
        self.module.PL.bitfile_name = name
        self.module.PL.timestamp = "mock-load"
        return self

    def is_loaded(self):
        return True

    def read(self, offset):
        assert self.value == 1, "MMIO while reset released"
        assert offset in self.original, "Access outside assigned 16 words"
        self.reads += 1
        self.events.append(("read", offset))
        if self.reads in self.fail_reads:
            raise self.fail_reads[self.reads]
        if self.reads == self.bad_read:
            return 0xDEADBEEF
        return self.memory[0xFC00 if self.alias else offset]

    def write(self, offset, value):
        assert self.value == 1, "MMIO while reset released"
        assert offset in self.original and type(value) is int
        self.writes += 1
        self.events.append(("write", offset, value))
        if self.writes in self.fail_writes:
            # A failed write may still have changed memory.
            self.memory[offset] = 0xBAD
            raise self.fail_writes[self.writes]
        self.memory[0xFC00 if self.alias else offset] = value

    def reset_factory(self, pin):
        self.events.append(("reset_resolve", pin))
        return self

    def snapshot(self):
        self.initial = {"value": self.value, "direction": self.direction, "exported": True}
        return self.initial.copy()

    def hold(self):
        self.events.append(("hold",))
        self.value, self.direction = 1, "out"
        self.check_high()

    def check_high(self):
        self.checks += 1
        if self.checks in self.fail_checks or (self.unholdable_after_write and self.writes):
            self.value = 0
            raise RuntimeError("injected reset loss")
        assert self.value == 1 and self.direction == "out"

    def restore(self):
        self.events.append(("reset_restore",))
        self.value, self.direction = self.initial["value"], self.initial["direction"]
        return {"value": self.value, "direction": self.direction}

    def release_export(self):
        self.events.append(("release_export",))


class BramTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.bit = Path(self.temp.name) / "base.bit"
        self.bit.write_bytes(b"host fake bit")
        self.bit.with_suffix(".hwh").write_bytes(HWH.encode("ascii"))
        self.hashes = {k: hashlib.sha256(p.read_bytes()).hexdigest()
                       for k, p in (("bit", self.bit), ("hwh", self.bit.with_suffix(".hwh")))}
        self.hw = FakeHardware()

    def run_probe(self):
        return probe.execute(self.bit, IDENTITY, pynq_module=self.hw.module,
                             reset_factory=self.hw.reset_factory,
                             expected_hashes=self.hashes, evidence_kind="host_mock")

    def test_384_reads_batch_order_patterns_and_restoration(self):
        result = self.run_probe()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["matching_samples"], 384)
        self.assertEqual(result["evidence_kind"], "host_mock")
        self.assertEqual(result["task_version"], 3)
        self.assertEqual(result["work_id"], "B-metadata-compat-v3")
        self.assertEqual(result["operation_id"], "BOARD-20261013-A:B:base-bram-v3-metadata-r1")
        self.assertEqual(result["pre_load_overlay"]["identity_status"], "unknown")
        self.assertFalse(result["original_configuration_restored"])
        self.hw.module.Overlay.assert_called_once_with(str(self.bit))
        self.hw.module.MMIO.assert_called_once_with(0x40000000, 0x10000)
        self.hw.module.GPIO.get_gpio_pin.assert_called_once_with(0)
        memory_ops = [e for e in self.hw.events if e[0] in ("read", "write")]
        self.assertEqual([e[0] for e in memory_ops[:16]], ["read"] * 16)
        for batch in range(24):
            actual = memory_ops[16 + batch * 32:16 + (batch + 1) * 32]
            self.assertEqual([e[0] for e in actual], ["write"] * 16 + ["read"] * 16)
        rng = random.Random(0x20261013)
        golden = [[0] * 16, [0xFFFFFFFF] * 16, [0x55555555] * 16, [0xAAAAAAAA] * 16,
                  [0xA5A50000 | i for i in range(16)],
                  [0x5A5AFFFF - i for i in range(16)], [2 ** i for i in range(16)],
                  [rng.getrandbits(32) for _ in range(16)]]
        self.assertEqual([s["expected"] for s in result["samples"]], sum(golden, []) * 3)
        self.assertEqual(self.hw.memory, self.hw.original)
        self.assertEqual([e[0] for e in memory_ops[-32:]], ["write"] * 16 + ["read"] * 16)
        self.assertEqual(self.hw.events[-2:], [("reset_restore",), ("release_export",)])
        self.assertEqual((self.hw.reads, self.hw.writes), (416, 400))
        self.assertEqual(self.hw.value, 0)
        self.assertTrue(all(e["passed"] for e in result["restoration"]["words"]))
        json.dumps(result)

    def test_initial_reset_one_is_restored(self):
        self.hw.value = 1
        self.assertEqual(self.run_probe()["status"], "passed")
        self.assertEqual(self.hw.value, 1)

    def test_memory_only_runtime_schema_is_supported(self):
        memory = self.hw.ip_dict.pop(probe.IP_NAME)
        memory.update(type="DDR4", memtype="MEMORY", base_address=0x40000000,
                      size=0x10000, mem_id="S_AXI", streaming=False)
        self.hw.mem_dict[probe.IP_NAME] = memory
        result = self.run_probe()
        diagnostic = {"errors": result["errors"], "samples": len(result["samples"]),
                      "mmio_calls": self.hw.module.MMIO.call_count,
                      "bram_reads": self.hw.reads, "bram_writes": self.hw.writes,
                      "reset_events": [e for e in self.hw.events if e[0].startswith("reset")
                                       or e[0] in ("hold", "release_export")]}
        self.assertEqual(result["status"], "passed", json.dumps(diagnostic))
        self.assertEqual(result["matching_samples"], 384)
        self.assertTrue(result["restoration"]["bram_restored"])
        self.assertEqual((self.hw.reads, self.hw.writes), (416, 400))
        self.assertEqual(result["source"]["vlnv"], "xilinx.com:ip:axi_bram_ctrl:4.1")
        self.assertEqual(result["source"]["identity_source"], "hash_checked_hwh")
        self.assertEqual(result["source"]["runtime_entries"][0]["runtime_type"], "DDR4")

    def test_memory_xrt_address_pair_and_matching_duplicate_tables(self):
        for xrt_only in (False, True):
            with self.subTest(xrt_only=xrt_only):
                self.hw = FakeHardware()
                entry = dict(self.hw.ip_dict[probe.IP_NAME], type="DDR4",
                             base_address=0x40000000, size=0x10000)
                if xrt_only:
                    self.hw.ip_dict.clear()
                    del entry["phys_addr"], entry["addr_range"]
                self.hw.mem_dict[probe.IP_NAME] = entry
                result = self.run_probe()
                self.assertEqual(result["status"], "passed")
                self.assertEqual(len(result["source"]["runtime_entries"]), 1 if xrt_only else 2)
                self.hw.module.MMIO.assert_called_once_with(0x40000000, 0x10000)

    def test_runtime_memory_conflicts_fail_before_reset_or_mmio(self):
        cases = [({"base_address": 0x40010000}, ()), ({"size": 0x1000}, ()),
                 ({"addr_range": 0x1000}, ()), ({"phys_addr": True}, ()),
                 ({"fullpath": "another/bram"}, ()), ({"type": "axi_gpio"}, ()),
                 ({"streaming": True}, ()), ({"memtype": "STREAM"}, ()),
                 ({"memtype": "REGISTER"}, ()), ({"mem_id": "OTHER"}, ()),
                 ({}, ("size",)), ({}, ("phys_addr",)), ({}, ("fullpath",)),
                 ({}, ("phys_addr", "addr_range", "base_address", "size"))]
        for updates, missing in cases:
            with self.subTest(updates=updates, missing=missing):
                self.hw = FakeHardware()
                # Even a valid ip_dict entry must not hide a conflicting memory entry.
                entry = dict(self.hw.ip_dict[probe.IP_NAME], type="DDR4",
                             base_address=0x40000000, size=0x10000)
                entry.update(updates)
                for key in missing:
                    del entry[key]
                self.hw.mem_dict[probe.IP_NAME] = entry
                result = self.run_probe()
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["errors"][0]["phase"], "metadata")
                self.hw.module.MMIO.assert_not_called()
                self.assertFalse(any(e[0] == "reset_resolve" for e in self.hw.events))
                self.assertEqual(self.hw.writes, 0)

    def test_runtime_alias_and_wrong_reset_net_are_rejected(self):
        for fault in ("alias", "reset_pins"):
            self.hw = FakeHardware()
            if fault == "alias":
                self.hw.mem_dict["alias"] = dict(self.hw.ip_dict[probe.IP_NAME])
            else:
                self.hw.gpio_dict[probe.RESET_NAME]["pins"] = {"other/reset"}
            self.assertEqual(self.run_probe()["status"], "failed")
            self.hw.module.MMIO.assert_not_called()
            self.assertFalse(any(e[0] == "reset_resolve" for e in self.hw.events))

    def test_hwh_identity_and_ps_mapping_reject_wrong_or_ambiguous_hardware(self):
        faults = ("vlnv", "path", "duplicate", "range", "missing_parameter",
                  "duplicate_parameter", "ps_missing", "ps_range", "ps_instance",
                  "ps_master", "ps_duplicate", "ps_memtype")
        for fault in faults:
            with self.subTest(fault=fault):
                self.hw = FakeHardware()
                root = ET.fromstring(HWH)
                modules = root.find("MODULES")
                target, ps = list(modules)
                mapping = ps.find(".//MEMRANGE")
                if fault == "vlnv": target.set("VLNV", "xilinx.com:ip:axi_gpio:2.0")
                elif fault == "path": target.set("FULLNAME", "/another/mb_bram_ctrl")
                elif fault == "duplicate": modules.append(ET.fromstring(ET.tostring(target)))
                elif fault == "range": target.find("./PARAMETERS/PARAMETER").set("VALUE", "0x40010000")
                elif fault == "missing_parameter": target.find("PARAMETERS").clear()
                elif fault == "duplicate_parameter":
                    target.find("PARAMETERS").append(ET.fromstring(ET.tostring(target.find("./PARAMETERS/PARAMETER"))))
                elif fault == "ps_missing": modules.remove(ps)
                elif fault == "ps_range": mapping.set("HIGHVALUE", "0x4001FFFF")
                elif fault == "ps_instance": mapping.set("INSTANCE", "other_bram")
                elif fault == "ps_master": mapping.set("MASTERBUSINTERFACE", "M_AXI_GP1")
                elif fault == "ps_duplicate": ps.find("MEMRANGES").append(ET.fromstring(ET.tostring(mapping)))
                elif fault == "ps_memtype": mapping.set("MEMTYPE", "REGISTER")
                data = ET.tostring(root)
                self.bit.with_suffix(".hwh").write_bytes(data)
                # Rebind the synthetic fixture hash to exercise structural checks.
                self.hashes["hwh"] = hashlib.sha256(data).hexdigest()
                result = self.run_probe()
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["errors"][0]["phase"], "hwh_metadata")
                self.hw.module.Overlay.assert_not_called()
                self.hw.module.MMIO.assert_not_called()
                self.assertEqual(self.hw.events, [])

    def test_linux_gpio_is_resolved_dynamically_for_A_pin_960(self):
        self.hw.module.GPIO.get_gpio_pin.return_value = 960
        result = self.run_probe()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["source"]["reset_linux_gpio"], 960)
        self.assertIn(("reset_resolve", 960), self.hw.events)

    def test_initial_input_direction_is_restored(self):
        self.hw.direction = "in"
        self.assertEqual(self.run_probe()["status"], "passed")
        self.assertEqual(self.hw.direction, "in")

    def test_corrupt_read_fails_without_replacing_observation_with_written_value(self):
        self.hw.bad_read = 17
        r = self.run_probe()
        self.assertEqual((r["status"], r["matching_samples"]), ("failed", 383))
        self.assertEqual(r["samples"][0]["observed"], 0xDEADBEEF)
        self.assertTrue(r["restoration"]["bram_restored"])

    def test_address_alias_fault_is_detected_by_batch_writes(self):
        self.hw.alias = True
        r = self.run_probe()
        self.assertEqual(r["status"], "failed")
        self.assertLess(r["matching_samples"], 384)

    def test_wrong_or_missing_metadata_aborts_before_reset_or_mmio(self):
        for key, wrong in (("type", "xilinx.com:ip:axi_gpio:2.0"), ("phys_addr", 0x40010000),
                           ("addr_range", 0x1000), ("phys_addr", True), ("fullpath", "other")):
            with self.subTest(key=key, wrong=wrong):
                self.hw = FakeHardware()
                self.hw.ip_dict[probe.IP_NAME][key] = wrong
                r = self.run_probe()
                self.assertEqual(r["errors"][0]["phase"], "metadata")
                self.hw.module.MMIO.assert_not_called()
                self.assertFalse(any(e[0] == "reset_resolve" for e in self.hw.events))
        for missing in ("ip", "reset"):
            self.hw = FakeHardware()
            (self.hw.ip_dict if missing == "ip" else self.hw.gpio_dict).clear()
            self.assertEqual(self.run_probe()["status"], "failed")
            self.hw.module.MMIO.assert_not_called()

    def test_unconfirmed_reset_index_is_rejected(self):
        for index in (True, -1, 1, 64, "0"):
            with self.subTest(index=index):
                self.hw = FakeHardware()
                self.hw.gpio_dict[probe.RESET_NAME]["index"] = index
                self.assertEqual(self.run_probe()["errors"][0]["phase"], "metadata")

    def test_partial_snapshot_never_writes_bram(self):
        self.hw.fail_reads[3] = OSError("snapshot")
        r = self.run_probe()
        self.assertEqual(self.hw.writes, 0)
        self.assertEqual(r["status"], "failed")
        self.assertTrue(r["restoration"]["reset_restored"])

    def test_body_write_read_and_keyboard_errors_restore_before_reset(self):
        for fault in ("write", "read", "interrupt"):
            with self.subTest(fault=fault):
                self.hw = FakeHardware()
                if fault == "write":
                    self.hw.fail_writes[5] = OSError("write may have partially succeeded")
                else:
                    self.hw.fail_reads[20] = KeyboardInterrupt() if fault == "interrupt" else OSError("read")
                r = self.run_probe()
                self.assertEqual(r["status"], "failed")
                self.assertEqual(self.hw.memory, self.hw.original)
                self.assertTrue(r["restoration"]["bram_restored"])
                self.assertTrue(r["restoration"]["reset_restored"])
                self.assertEqual(self.hw.value, 0)

    def test_cleanup_failure_attempts_all_words_but_never_releases_reset(self):
        for fault in ("write", "read"):
            with self.subTest(fault=fault):
                self.hw = FakeHardware()
                if fault == "write":
                    self.hw.fail_writes[385] = OSError("restore write")
                else:
                    self.hw.fail_reads[401] = OSError("restore read")
                r = self.run_probe()
                self.assertEqual((self.hw.reads, self.hw.writes), (416, 400))
                self.assertEqual(r["status"], "failed")
                self.assertTrue(r["restoration"]["reset_restore_withheld"])
                self.assertTrue(r["restoration"]["reset_held_after_failure"])
                self.assertEqual(self.hw.value, 1)
                self.assertNotIn(("reset_restore",), self.hw.events)
                self.assertNotIn(("release_export",), self.hw.events)

    def test_initial_assert_failure_has_no_mmio_and_restores_reset(self):
        self.hw.fail_checks.add(1)
        r = self.run_probe()
        self.hw.module.MMIO.assert_not_called()
        self.assertTrue(r["restoration"]["reset_restored"])
        self.assertEqual(r["status"], "failed")

    def test_reset_drop_is_reasserted_before_cleanup(self):
        self.hw.fail_checks.add(4)
        r = self.run_probe()
        self.assertEqual(r["status"], "failed")
        self.assertEqual(self.hw.memory, self.hw.original)
        self.assertEqual(self.hw.value, 0)

    def test_unholdable_reset_prevents_racing_bram_cleanup(self):
        self.hw.unholdable_after_write = True
        r = self.run_probe()
        self.assertEqual(self.hw.writes, 16)
        self.assertTrue(r["restoration"]["reset_restore_withheld"])
        self.assertFalse(r["restoration"]["reset_held_after_failure"])
        self.assertEqual(r["status"], "failed")

    def test_reset_restore_error_cannot_pass(self):
        self.hw.restore = Mock(side_effect=OSError("restore reset"))
        r = self.run_probe()
        self.assertEqual(r["status"], "failed")
        self.assertFalse(r["restoration"]["reset_restored"])

    def test_hash_and_missing_file_fail_before_overlay(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                self.hw = FakeHardware()
                if missing:
                    self.bit.with_suffix(".hwh").unlink()
                else:
                    self.bit.with_suffix(".hwh").write_bytes(b"changed")
                r = self.run_probe()
                self.hw.module.Overlay.assert_not_called()
                self.assertEqual(r["errors"][0]["phase"], "input_validation")
                json.dumps(r)

    def test_overlay_exception_is_reported_without_reset(self):
        self.hw.module.Overlay.side_effect = OSError("load failed")
        self.assertEqual(self.run_probe()["errors"][0]["phase"], "overlay_load")
        self.assertFalse(any(e[0] == "reset_resolve" for e in self.hw.events))

    def arguments(self, output):
        return ["--bitstream", str(self.bit), "--output", str(output),
                "--operation-id", probe.OPERATION_ID, "--request-hash", "a" * 64,
                "--code-commit", "b" * 40, "--tested-commit", "c" * 40]

    def test_existing_output_is_untouched_and_runner_never_called(self):
        output = Path(self.temp.name) / "existing.json"
        output.write_bytes(b"immutable")
        runner = Mock()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(probe.main(self.arguments(output), runner), 2)
        runner.assert_not_called()
        self.assertEqual(output.read_bytes(), b"immutable")

    def test_cli_json_and_exit_codes_match_outcome(self):
        for fail in (False, True):
            self.hw = FakeHardware()
            if fail:
                self.hw.bad_read = 17
            output = Path(self.temp.name) / (str(fail) + ".json")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = probe.main(self.arguments(output), lambda *a: self.run_probe())
            self.assertEqual(rc, int(fail))
            self.assertEqual(json.loads(stdout.getvalue()), json.loads(output.read_text()))


class SysfsTests(unittest.TestCase):
    def test_capture_high_and_restore_direction_value_without_out_low_glitch(self):
        for initial_direction, initial_value in (("out", 0), ("out", 1), ("in", 0)):
            with self.subTest(initial_direction=initial_direction, initial_value=initial_value):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    gpio = root / "gpio906"
                    gpio.mkdir()
                    for name, value in (("direction", initial_direction), ("value", initial_value), ("active_low", 0)):
                        (gpio / name).write_text(str(value))
                    reset = probe.SysfsReset(906, root)
                    writes = []

                    def write(name, value):
                        writes.append((name, value))
                        if name == "direction" and value in ("high", "low"):
                            (gpio / "direction").write_text("out")
                            (gpio / "value").write_text("1" if value == "high" else "0")
                        else:
                            (gpio / name).write_text(str(value))

                    reset._write = write
                    initial = reset.snapshot()
                    self.assertEqual(writes, [])
                    self.assertEqual(initial["observation_point"],
                                     "post_load_existing_export_sysfs_observation")
                    self.assertFalse(initial["pre_export_output_latch_known"])
                    reset.hold()
                    self.assertEqual(writes[0], ("direction", "high"))
                    reset.restore()
                    self.assertEqual(reset.value(), initial_value)
                    self.assertEqual(reset._read("direction"), initial_direction)
                    self.assertTrue(initial["exported"])
                    reset.release_export()
                    self.assertFalse((root / "unexport").exists())

    def test_unexported_gpio_initial_state_is_observed_only_after_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_write = Path.write_text
            calls = []

            def write(path, value, *args, **kwargs):
                calls.append((path.name, str(value)))
                if path == root / "export":
                    gpio = root / "gpio960"
                    gpio.mkdir()
                    for name, data in (("direction", "out"), ("value", "1"), ("active_low", "0")):
                        original_write(gpio / name, data)
                elif path.name == "direction" and value in ("high", "low"):
                    original_write(path.parent / "value", "1" if value == "high" else "0")
                    value = "out"
                return original_write(path, value, *args, **kwargs)

            reset = probe.SysfsReset(960, root)
            with patch.object(Path, "write_text", write):
                initial = reset.snapshot()
                self.assertEqual(calls, [("export", "960")])
                self.assertEqual(initial["observation_point"],
                                 "post_load_post_export_sysfs_observation")
                self.assertFalse(initial["pre_export_output_latch_known"])
                self.assertFalse(initial["exported"])
                self.assertEqual(initial["value"], 1)
                self.assertEqual(initial["value_source"], str(root / "gpio960/value"))
                reset.hold()
                reset.restore()
                reset.release_export()
            self.assertEqual(calls[-1], ("unexport", "960"))
            self.assertEqual((root / "gpio960/value").read_text(), "1")

    def test_new_export_is_released_and_active_low_fails_before_direction_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original_write = Path.write_text

            def write(path, value, *args, **kwargs):
                if path == root / "export":
                    gpio = root / "gpio906"
                    gpio.mkdir()
                    for name, data in (("direction", "out"), ("value", "0"), ("active_low", "1")):
                        original_write(gpio / name, data)
                return original_write(path, value, *args, **kwargs)

            reset = probe.SysfsReset(906, root)
            with patch.object(Path, "write_text", write):
                with self.assertRaisesRegex(ValueError, "Inverted"):
                    reset.snapshot()
                reset.release_export()
            self.assertTrue(reset.newly_exported)
            self.assertIsNone(reset.initial)
            self.assertEqual((root / "gpio906/direction").read_text(), "out")
            self.assertEqual((root / "unexport").read_text(), "906")


if __name__ == "__main__":
    unittest.main()
