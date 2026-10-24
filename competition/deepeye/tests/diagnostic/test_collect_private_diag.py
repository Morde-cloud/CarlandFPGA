"""SOFTWARE ONLY: fake overlay/MMIO, no PYNQ import, device or board access.

Fixtures and raw journals are retained under worker55's author ownership.
These tests do not verify RTL, PYNQ compatibility, synthesis, or hardware.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
AUTHOR = ROOT / "evidence/diagnostic/private-collector-20261025-55/author"
SPEC = importlib.util.spec_from_file_location("private_collector_under_test", ROOT / "tools/diagnostic/collect_private_diag.py")
c = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = c
SPEC.loader.exec_module(c)


def encoded(obj):
    return (json.dumps(obj, sort_keys=True) + "\n").encode()


def input_fixture(scans=2):
    return {"schema_version": 1, "source_id": 4, "source": "software_fixture", "topology_id": 2,
            "a_reference": {"run_id": "A-test-run-SOFTWARE-ONLY", "session_id": "A-test-session", "nonce": "A-ledger-nonce-reference"},
            "tag": 0xABCD1234,
            "scans": [{"values": [0, 1 + i, 32768, 65535],
                       "original_host_qpc_ns": [0, (1 << 53) + i + 1, (1 << 63) + 7 + i, (1 << 64) - 1],
                       "qualities": [0, 1, 127, 255]} for i in range(scans)]}


class FixturePackage:
    """Deliberately nondeployable .bit and XML, with real four readonly source pins."""
    def __init__(self, directory):
        self.root = directory
        self.package = directory / "package"
        self.package.mkdir()
        self.input = directory / "input.json"
        self.input.write_bytes(encoded(input_fixture()))
        self.manifest = self.package / "ARTIFACT_MANIFEST.json"
        self.base = 0x43C25000  # Arbitrary aligned fixture base; production must parse HWH.
        files = {name: b"SOFTWARE FIXTURE - NOT A REAL BUILD\n" for name in c.REQUIRED_ARTIFACTS}
        files[c.BIT] = b"FAKE BITSTREAM: software tests only; never load on a board\n"
        files[c.HWH] = (f'<SYSTEM><MODULES><MODULE FULLNAME="/private_diag_0" VLNV="{c.VLNV}"/>'
                        f'</MODULES><MEMRANGE INSTANCE="private_diag_0" SLAVEBUSINTERFACE="S_AXI" '
                        f'BASEVALUE="{hex(self.base)}" HIGHVALUE="{hex(self.base + 4095)}"/></SYSTEM>').encode()
        files["BD_MAPPING.json"] = encoded({"base": hex(self.base), "range": "0x1000"})
        files["VIVADO_COMPLETE.json"] = encoded({"run_id": "SOFTWARE-ONLY-build-id"})
        files["PROCESS.json"] = encoded({"exit_code": 0, "timed_out": False, "termination_confirmed": True})
        files["PREPARATION.json"] = encoded({"preparation": "SOFTWARE-ONLY-fixture"})
        files["inputs/build_private_diag.py"] = b"# SOFTWARE fixture wrapper, not executable build provenance\n"
        files["inputs/build_private_diag.tcl"] = b"# SOFTWARE fixture Tcl\n"
        pins = {}
        for index, name in enumerate(c.SOURCES):
            data = (ROOT / name).read_bytes() if index < 4 else b"// FAKE private RTL, SOFTWARE TEST ONLY\n"
            pins[name] = c.sha(data)
            files["inputs/rtl/" + name] = data
        self.m = {"status": "completed_build_pending_main_review", "task_id": c.TASK, "task_version": 1,
                  "work_id": "B-MINIMAL-PL-BUILD-PREP-20261025-54-v1", "requirements_sha256": c.CONTRACT,
                  "requirement_ids": [f"H{i:02}" for i in range(1, 16)], "design_commit": c.DESIGN,
                  "expected_rtl_sha256": pins,
                  "private_ip": {"instance": c.INSTANCE, "vlnv": c.VLNV, "base": hex(self.base), "range": 4096},
                  "all_29_formal_acceptance": "not_run", "physical_board": "not_run; A-only",
                  "files": {}, "artifacts": {}}
        for name, data in files.items():
            self.put(name, data)
        self.m["process"] = self.m["files"]["PROCESS.json"]
        self.m["inputs"] = self.m["files"]["PREPARATION.json"]
        self.save()

    def put(self, name, data):
        path = self.package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        rec = {"path": "Z:/sender-build/" + name, "bytes": len(data), "sha256": c.sha(data)}
        self.m["files"][name] = rec
        if name in c.REQUIRED_ARTIFACTS:
            self.m["artifacts"][name] = copy.deepcopy(rec)

    def save(self):
        self.manifest.write_bytes(encoded(self.m))
        self.digest = c.sha(self.manifest.read_bytes())


class SoftwareClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        self.value += 0.000001
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class FakeMMIO:
    """A scripted four-lane candidate, not RTL simulation or device emulation proof."""
    def __init__(self, fault=None):
        self.fault = fault
        self.running = False
        self.pending = False
        self.tag = 0
        self.staged_tag = 0
        self.generation = 10
        self.trigger = 7
        self.counts = [100, 200, 300]
        self.stage = {}
        self.channel = 0
        self.scan_index = -1
        self.words = ()
        self.transcript = []
        self.stop_attempts = 0
        self.trigger_attempts = 0
        self.ack_attempts = 0
        self.result_reads = 0

    def raw(self):
        ch = self.channel
        quality = (self.stage[0x70] >> (ch * 8)) & 255
        result = (self.stage[0x40 + 4 * ch], ch | (quality << 8),
                  self.stage[0x50 + 8 * ch], self.stage[0x54 + 8 * ch],
                  4 * self.scan_index, 4 * self.scan_index + 3, self.tag,
                  self.trigger, self.generation, 900 + ch)
        return result

    def read(self, offset):
        self.transcript.append(("read", offset))
        if offset == 0:
            return 0 if self.fault == "magic" else 0x44505953
        if offset == 4:
            return 0x00010000
        if offset == 8:
            return int(self.running) | (2 if self.pending else 0) | (4 if self.pending and self.fault != "timeout" else 0)
        if offset == 0x10:
            return self.staged_tag
        if offset == 0x14:
            return self.tag
        if offset == 0x18:
            return self.generation
        if offset == 0x1C:
            return self.trigger
        if offset in (0x24, 0x28, 0x30):
            return self.counts[(0x24, 0x28, 0x30).index(offset)]
        if offset in c.RESULT_REGS:
            self.result_reads += 1
            if self.fault == "interrupt":
                raise KeyboardInterrupt("software injected interruption after MMIO")
            result = self.raw()[c.RESULT_REGS.index(offset)]
            if self.fault == "field" and offset == 0x80:
                result ^= 1
            if self.fault == "stale_generation" and offset == 0xA0:
                result -= 1
            if self.fault == "unstable" and self.result_reads > 10 and offset == 0x80:
                result ^= 1
            if self.fault == "valid_drop" and offset == 0xA4:
                self.pending = False
            return result
        raise AssertionError("unexpected fake read " + hex(offset))

    def write(self, offset, value):
        self.transcript.append(("write", offset, value))
        if offset == 0x10:
            self.staged_tag = value
            return
        if offset != 0x0C:
            self.stage[offset] = value
            return
        if value == 1:
            self.stop_attempts += 1
            if self.fault in ("stop", "field_and_stop") and self.stop_attempts >= 2:
                raise RuntimeError("software final STOP failure")
            self.running = self.pending = False
            self.tag = 0
            self.stage.clear()
        elif value == 2:
            self.generation += 2 if self.fault == "wrong_start_generation" else 1
            self.tag = self.staged_tag
            self.running = self.fault != "start_timeout"
            if self.fault == "counter_exhaustion":
                self.counts[0] = c.U32
            if self.fault == "trigger_exhaustion":
                self.trigger = c.U32
        elif value == 4:
            self.trigger_attempts += 1
            self.trigger += 1
            self.scan_index += 1
            self.channel = 0
            self.pending = True
            self.counts[0] += 4
            self.counts[1] += 1
            self.counts[2] += 1
            if self.fault == "counters":
                self.counts[1] -= 1
            if self.fault == "field_and_stop":
                self.stage[0x40] ^= 1
            if self.fault == "unknown_trigger":
                raise RuntimeError("software exception after trigger effect; outcome unknown")
        elif value == 8:
            self.ack_attempts += 1
            self.channel += 1
            if self.channel == 4:
                self.pending = False
            else:
                self.counts[2] += 1
            if self.fault == "unknown_ack":
                raise RuntimeError("software exception after ACK effect; outcome unknown")
        else:
            raise AssertionError("unexpected fake command")


class FakeOverlay:
    def __init__(self, runtime):
        self.runtime = runtime
        self.ip_dict = {c.INSTANCE: {"fullpath": c.INSTANCE, "type": c.VLNV,
                                   "phys_addr": runtime.package.base, "addr_range": 4096}}
        if runtime.fault == "metadata":
            self.ip_dict[c.INSTANCE]["phys_addr"] += 4096

    def download(self):
        self.runtime.downloads += 1
        if self.runtime.fault == "download":
            raise RuntimeError("software download failure")


class FakeRuntime:
    def __init__(self, package, fault=None):
        self.package, self.fault = package, fault
        self.downloads = 0
        self.mmios = 0
        self.overlay_calls = 0
        self.bus = FakeMMIO(fault)
        self.bit_path = None

    def overlay(self, path):
        self.overlay_calls += 1
        self.bit_path = path
        assert path != self.package.package / c.BIT
        assert path.read_bytes().startswith(b"FAKE BITSTREAM")
        assert path.with_suffix(".hwh").read_bytes().startswith(b"<SYSTEM>")
        if self.fault == "changed_original":
            (self.package.package / c.BIT).write_bytes(b"UNVALIDATED MUTATED ORIGINAL")
            (self.package.package / c.HWH).write_bytes(b"UNVALIDATED MUTATED ORIGINAL")
            assert path.read_bytes().startswith(b"FAKE BITSTREAM")
            assert path.with_suffix(".hwh").read_bytes().startswith(b"<SYSTEM>")
        if self.fault == "overlay":
            raise RuntimeError("software overlay construction failure")
        return FakeOverlay(self)

    def mmio(self, base, span):
        self.mmios += 1
        assert (base, span) == (self.package.base, 4096)
        if self.fault == "mmio_init":
            raise RuntimeError("software MMIO construction failure")
        return self.bus


class CollectorTests(unittest.TestCase):
    def setUp(self):
        cases = AUTHOR / "software_cases"
        cases.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix=self._testMethodName + "-", dir=cases))
        self.p = FixturePackage(self.directory)

    def run_case(self, fault=None, out="output", digest=None, factory=None, execute=True):
        runtime = FakeRuntime(self.p, fault)
        clock = SoftwareClock()
        result = c.collect(self.p.package, self.p.manifest, digest or self.p.digest, self.p.input,
                           self.directory / out, execute_a=execute,
                           runtime_factory=(factory if factory is not None else lambda: runtime) if execute else None,
                           clock=clock, sleep=clock.sleep, poll_seconds=0.02, total_seconds=1)
        self.assertEqual(json.loads(json.dumps(result)), json.loads((self.directory / out / "RESULT.json").read_text()))
        return result, runtime

    def assert_failed_stopped(self, fault):
        result, runtime = self.run_case(fault)
        self.assertEqual(result["exit_code"], 2)
        self.assertTrue(result["cleanup"]["confirmed"])
        self.assertFalse(runtime.bus.running)
        return result, runtime

    def test_fresh_four_lane_candidate_and_exact_qpc(self):
        result, runtime = self.run_case()
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["status"], "software_fake_capture_complete")
        self.assertEqual(result["physical_board"], "not_run")
        self.assertEqual(result["formal_product_acceptance"], "not_run")
        self.assertEqual((runtime.downloads, runtime.mmios, runtime.bus.trigger_attempts, runtime.bus.ack_attempts), (1, 1, 2, 8))
        expected = input_fixture()["scans"]
        for i, record in enumerate(result["captures"]):
            scan, ch = i // 4, i % 4
            self.assertEqual(record["original_host_qpc_ns"], expected[scan]["original_host_qpc_ns"][ch])
            self.assertEqual(record["value"], expected[scan]["values"][ch])
            self.assertEqual(record["opaque_quality"], expected[scan]["qualities"][ch])
            self.assertEqual((record["first_seq"], record["last_seq"]), (4 * scan, 4 * scan + 3))
            self.assertTrue(record["ack_returned"])
        self.assertEqual(runtime.bus.stop_attempts, 2)
        stage = [x for x in runtime.bus.transcript if x[0] == "write" and x[1] not in (0x0C, 0x10)]
        self.assertEqual(len(stage), 26)
        self.assertNotIn(0x2C, [x[1] for x in runtime.bus.transcript])
        journal = [json.loads(line) for line in (self.directory / "output/operations.jsonl").read_text().splitlines()]
        calls = [x for x in journal if x["event"] == "mmio_attempt"]
        self.assertEqual(len(calls), len(runtime.bus.transcript))
        self.assertTrue(all("collector_monotonic_ns" in x and "clock_role" in x for x in journal))

    def test_offline_no_runtime_or_pynq_import(self):
        before = set(sys.modules)
        result, runtime = self.run_case(execute=False)
        self.assertEqual(result["status"], "verified_offline_only")
        self.assertEqual((runtime.overlay_calls, runtime.downloads, runtime.mmios), (0, 0, 0))
        self.assertNotIn("pynq", set(sys.modules) - before)
        self.assertFalse(result["cleanup"]["attempted"])

    def test_changed_original_uses_checked_output_snapshots(self):
        result, runtime = self.run_case("changed_original")
        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(runtime.bit_path.is_relative_to(self.directory / "output/snapshots"))
        self.assertNotEqual(runtime.bit_path.read_bytes(), (self.p.package / c.BIT).read_bytes())

    def test_input_exact_schema_and_ranges(self):
        mutations = [lambda o: o.update(tag=True), lambda o: o.update(tag=0), lambda o: o.update(tag=1 << 32),
                     lambda o: o.update(source_id=True), lambda o: o.update(source="live"),
                     lambda o: o.update(topology_id=1), lambda o: o.update(truth_coordinates=[1, 2, 3]),
                     lambda o: o.update(scans=[]), lambda o: o.update(scans=o["scans"] * 9),
                     lambda o: o["a_reference"].update(nonce=""),
                     lambda o: o["scans"][0].update(values=[1, 2, 3]),
                     lambda o: o["scans"][0].update(values=[True, 2, 3, 4]),
                     lambda o: o["scans"][0].update(values=[65536, 2, 3, 4]),
                     lambda o: o["scans"][0].update(qualities=[256, 2, 3, 4]),
                     lambda o: o["scans"][0].update(original_host_qpc_ns=[-1, 2, 3, 4]),
                     lambda o: o["scans"][0].update(original_host_qpc_ns=[1 << 64, 2, 3, 4]),
                     lambda o: o["scans"][0].update(original_host_qpc_ns=[1.0, 2, 3, 4]),
                     lambda o: o["scans"][0].update(qualities=["0", 2, 3, 4])]
        for mutation in mutations:
            value = input_fixture()
            mutation(value)
            with self.subTest(value=value):
                with self.assertRaises(c.Rejected):
                    c.fixture_from_bytes(encoded(value))
        for raw in (b'{"tag":1,"tag":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.assertRaises(c.Rejected):
                c.fixture_from_bytes(raw)

    def test_input_rejection_has_no_runtime_activity(self):
        self.p.input.write_bytes(b'{"duplicate":1,"duplicate":2}')
        result, runtime = self.run_case()
        self.assertEqual(result["exit_code"], 2)
        self.assertEqual((runtime.downloads, runtime.mmios, runtime.overlay_calls), (0, 0, 0))
        self.assertFalse(result["cleanup"]["attempted"])

    def test_manifest_exact_hash_failure_no_activity(self):
        result, runtime = self.run_case(digest="0" * 64)
        self.assertEqual(result["exit_code"], 2)
        self.assertEqual(runtime.overlay_calls, 0)

    def test_bit_hash_failure_no_activity(self):
        (self.p.package / c.BIT).write_bytes(b"changed")
        result, runtime = self.run_case()
        self.assertEqual(result["exit_code"], 2)
        self.assertEqual(runtime.overlay_calls, 0)

    def test_source_hash_failure(self):
        (self.p.package / "inputs/rtl" / c.SOURCES[0]).write_bytes(b"changed source")
        result, _ = self.run_case()
        self.assertIn("hash/size", result["error"]["message"])

    def test_declared_bit_pair_mismatch(self):
        self.p.m["artifacts"][c.BIT]["sha256"] = "0" * 64
        self.p.save()
        result, runtime = self.run_case()
        self.assertIn("pairing", result["error"]["message"])
        self.assertEqual(runtime.downloads, 0)

    def test_manifest_status_is_not_user_identity(self):
        self.p.m["status"] = "accepted"
        self.p.save()
        result, _ = self.run_case()
        self.assertEqual(result["exit_code"], 2)

    def test_fixed_source_pin_cannot_be_replaced_with_matching_bytes(self):
        name = c.SOURCES[0]
        self.p.put("inputs/rtl/" + name, b"new bytes")
        self.p.m["expected_rtl_sha256"][name] = c.sha(b"new bytes")
        self.p.save()
        result, _ = self.run_case()
        self.assertIn("fixed readonly", result["error"]["message"])

    def test_failed_build_process_rejected(self):
        self.p.put("PROCESS.json", encoded({"exit_code": 1, "timed_out": False, "termination_confirmed": True}))
        self.p.m["process"] = self.p.m["files"]["PROCESS.json"]
        self.p.save()
        result, runtime = self.run_case()
        self.assertIn("process", result["error"]["message"])
        self.assertEqual(runtime.overlay_calls, 0)

    def test_hwh_dtd_entities_utf16_and_wrong_identity(self):
        original = (self.p.package / c.HWH).read_bytes()
        cases = [b'<!DOCTYPE SYSTEM [<!ENTITY x "test">]>' + original,
                 original.decode().encode("utf-16"),
                 original.replace(c.VLNV.encode(), b"other:ip:name:1.0"),
                 original.replace(b"private_diag_0", b"other_0"),
                 original.replace(b"</SYSTEM>", original + b"</SYSTEM>"),
                 original.replace(hex(self.p.base + 4095).encode(), hex(self.p.base + 8191).encode())]
        for i, raw in enumerate(cases):
            self.p.put(c.HWH, raw)
            self.p.save()
            result, runtime = self.run_case(out="bad_hwh_" + str(i))
            self.assertEqual(result["exit_code"], 2)
            self.assertEqual(runtime.overlay_calls, 0)

    def test_same_build_mapping_mismatch(self):
        self.p.put("BD_MAPPING.json", encoded({"base": hex(self.p.base + 4096), "range": "0x1000"}))
        self.p.save()
        result, _ = self.run_case()
        self.assertIn("BD_MAPPING", result["error"]["message"])

    def test_package_traversal_rejected(self):
        self.p.m["files"]["../outside"] = self.p.m["files"][c.BIT]
        self.p.save()
        result, _ = self.run_case()
        self.assertIn("unsafe", result["error"]["message"])

    def test_output_overlap_and_exclusive_create(self):
        clock = SoftwareClock()
        with self.assertRaises(c.Rejected):
            c.collect(self.p.package, self.p.manifest, self.p.digest, self.p.input, self.p.package / "output", clock=clock)
        result, _ = self.run_case(execute=False)
        original = (self.directory / "output/RESULT.json").read_bytes()
        with self.assertRaises(c.Rejected):
            self.run_case(execute=False)
        self.assertEqual((self.directory / "output/RESULT.json").read_bytes(), original)
        self.assertEqual(result["exit_code"], 0)

    def test_hardlink_input_alias_rejected(self):
        target = self.directory / "bit_alias.bit"
        os.link(self.p.package / c.BIT, target)
        result, runtime = self.run_case()
        self.assertEqual(result["exit_code"], 2)
        self.assertIn("hardlink alias", result["error"]["message"])
        self.assertEqual(runtime.overlay_calls, 0)

    def test_symlink_input_alias_rejected(self):
        target = self.directory / "input_alias.json"
        try:
            target.symlink_to(self.p.input)
        except OSError as exc:
            self.skipTest("OS denied symlink creation: " + str(exc))
        with self.assertRaises(c.Rejected):
            c.collect(self.p.package, self.p.manifest, self.p.digest, target, self.directory / "output")

    def test_timeout_stops_without_retrigger(self):
        result, runtime = self.assert_failed_stopped("timeout")
        self.assertIn("timeout", result["error"]["message"])
        self.assertEqual((runtime.bus.trigger_attempts, runtime.bus.ack_attempts), (1, 0))

    def test_wrong_raw_field(self):
        _, runtime = self.assert_failed_stopped("field")
        self.assertEqual(runtime.bus.ack_attempts, 0)

    def test_stale_generation(self):
        self.assert_failed_stopped("stale_generation")

    def test_result_recheck_changes(self):
        result, runtime = self.assert_failed_stopped("unstable")
        self.assertIn("changed before ACK", result["error"]["message"])
        self.assertEqual(runtime.bus.ack_attempts, 0)

    def test_result_valid_drops(self):
        result, _ = self.assert_failed_stopped("valid_drop")
        self.assertIn("result_valid/status", result["error"]["message"])

    def test_counter_progress_required(self):
        result, runtime = self.assert_failed_stopped("counters")
        self.assertIn("pipeline progress", result["error"]["message"])
        self.assertEqual(runtime.bus.ack_attempts, 0)

    def test_final_stop_failure_separately_retained(self):
        result, runtime = self.run_case("stop")
        self.assertEqual(result["exit_code"], 2)
        self.assertFalse(result["cleanup"]["confirmed"])
        self.assertIn("STOP failure", result["cleanup"]["error"]["message"])
        self.assertEqual(runtime.bus.stop_attempts, 2)

    def test_primary_failure_not_hidden_by_stop_failure(self):
        result, _ = self.run_case("field_and_stop")
        self.assertIn("raw lane", result["error"]["message"])
        self.assertIn("STOP failure", result["cleanup"]["error"]["message"])

    def test_failure_before_import_has_no_fabricated_stop(self):
        def factory():
            raise ImportError("software import unavailable")
        result, runtime = self.run_case(factory=factory)
        self.assertEqual(result["error"]["type"], "ImportError")
        self.assertFalse(result["cleanup"]["attempted"])
        self.assertEqual(runtime.bus.stop_attempts, 0)

    def test_overlay_metadata_failure_before_download(self):
        result, runtime = self.run_case("metadata")
        self.assertEqual(result["exit_code"], 2)
        self.assertEqual((runtime.downloads, runtime.mmios, runtime.bus.stop_attempts), (0, 0, 0))

    def test_overlay_download_and_mmio_construction_failures(self):
        for fault in ("overlay", "download", "mmio_init"):
            result, runtime = self.run_case(fault, out=fault)
            self.assertEqual(result["exit_code"], 2)
            self.assertFalse(result["cleanup"]["attempted"])
            self.assertEqual(runtime.bus.stop_attempts, 0)

    def test_magic_failure_after_mmio_stops(self):
        self.assert_failed_stopped("magic")

    def test_interruption_after_mmio_stops(self):
        result, _ = self.assert_failed_stopped("interrupt")
        self.assertEqual(result["error"]["type"], "KeyboardInterrupt")

    def test_unknown_trigger_effect_not_replayed(self):
        result, runtime = self.assert_failed_stopped("unknown_trigger")
        self.assertEqual((runtime.bus.trigger_attempts, runtime.bus.ack_attempts), (1, 0))
        self.assertIn("outcome unknown", result["error"]["message"])

    def test_unknown_ack_effect_not_replayed(self):
        result, runtime = self.assert_failed_stopped("unknown_ack")
        self.assertEqual(runtime.bus.ack_attempts, 1)
        self.assertFalse(result["captures"][0]["ack_returned"])

    def test_start_generation_and_running_checked(self):
        for fault in ("wrong_start_generation", "start_timeout"):
            result, runtime = self.run_case(fault, out=fault)
            self.assertEqual(result["exit_code"], 2)
            self.assertTrue(result["cleanup"]["confirmed"])
            self.assertEqual(runtime.bus.trigger_attempts, 0)

    def test_counter_and_trigger_exhaustion_do_not_trigger(self):
        for fault in ("counter_exhaustion", "trigger_exhaustion"):
            result, runtime = self.run_case(fault, out=fault)
            self.assertEqual(result["exit_code"], 2)
            self.assertTrue(result["cleanup"]["confirmed"])
            self.assertEqual(runtime.bus.trigger_attempts, 0)

    def test_sixteen_scan_bound(self):
        self.p.input.write_bytes(encoded(input_fixture(scans=16)))
        result, runtime = self.run_case()
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual((len(result["captures"]), runtime.bus.trigger_attempts, runtime.bus.ack_attempts), (64, 16, 64))


if __name__ == "__main__":
    unittest.main(verbosity=2)
