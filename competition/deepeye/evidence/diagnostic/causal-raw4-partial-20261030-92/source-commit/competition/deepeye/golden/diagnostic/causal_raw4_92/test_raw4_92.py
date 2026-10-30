"""Pure B92 adapter/fixture regression tests. No RTL or host decoder is run here."""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[2] / "tools/diagnostic/causal_raw4_92"
sys.path.insert(0, str(TOOLS))

import prepare_fixture92 as fixture
import raw4_adapter92 as adapter
import semantic_checks92 as semantic


BUILD_SHA = "b" * 64


class Raw4Adapter92Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.projection = fixture.build_projection()
        cls.model = adapter.derive_model(cls.projection, build_manifest_sha256=BUILD_SHA)
        cls.summary = adapter.expected_summary(cls.model)

    def test_projection_is_counts_only_and_strict(self):
        self.assertEqual(set(self.projection), adapter.PROJECTION_KEYS)
        self.assertNotIn("channel_values", json.dumps(self.projection, sort_keys=True))
        self.assertEqual(len(self.projection["records"]), 20)
        for record in self.projection["records"]:
            self.assertEqual(set(record), adapter.RECORD_KEYS)
            self.assertEqual(len(record["channel_counts"]), 4)
        adapter.validate_projection(self.projection)

    def test_a70_shape_and_quality(self):
        self.assertEqual([r["adc_tick_ms"] for r in self.projection["records"]],
                         list(range(0, 200, 10)))
        self.assertEqual([r["em_tick_ms"] for r in self.projection["records"]],
                         [0] * 5 + [50] * 5 + [100] * 5 + [150] * 5)
        self.assertEqual([r["channel_counts"][3] for r in self.projection["records"]],
                         [None] * 9 + [0] * 11)
        self.assertEqual(self.summary["global_quality_values"], [7, 15, 1799, 1807])
        self.assertEqual(len(self.model["lanes"]), 80)
        self.assertEqual(self.summary["invalid_frames"], 9)
        self.assertEqual(self.summary["valid_c3_zero_frames"], 11)
        self.assertEqual(self.summary["fresh_valid_frames"], 23)
        self.assertEqual(self.summary["held_valid_frames"], 48)
        self.assertEqual(self.summary["reference_wire_bytes"], 3038)

    def test_lane_order_flags_and_times(self):
        self.assertEqual([lane["frame_seq"] for lane in self.model["lanes"]], list(range(80)))
        for position, lane in enumerate(self.model["lanes"]):
            record = position // 4
            channel = position % 4
            self.assertEqual(lane["record_index"], record)
            self.assertEqual(lane["channel"], channel)
            self.assertEqual(lane["acquisition_index"], record)
            self.assertEqual(lane["capture_first_seq"], record * 4)
            self.assertEqual(lane["capture_last_seq"], record * 4 + 3)
            self.assertEqual(lane["acquisition_qpc_ns"],
                             fixture.ORIGIN_QPC_NS + record * 10_000_000)
            self.assertEqual(lane["sample_data"], lane["count"] if lane["valid_sample"] else 0)
            if lane["valid_sample"]:
                expected_source = (fixture.ORIGIN_QPC_NS + fixture.record_shape(record)["em_tick_ms"] * 1_000_000
                                   if channel < 3 and lane["held"] else lane["acquisition_qpc_ns"])
                self.assertEqual(lane["source_qpc_ns"], expected_source)
                self.assertGreater(self.model["evaluation_now_qpc_ns"] - expected_source, 100_000_000)
                self.assertTrue(lane["stale_by_evaluation_time"])
            else:
                self.assertIsNone(lane["source_qpc_ns"])
                self.assertIsNone(lane["stale_by_evaluation_time"])

    def test_uint63_width_and_relative_time(self):
        self.assertGreater(self.model["origin_qpc_ns"], (1 << 32) - 1)
        self.assertLessEqual(self.model["origin_qpc_ns"], adapter.U63)
        for lane in self.model["lanes"]:
            self.assertEqual(lane["first_tick_us"],
                             (lane["acquisition_qpc_ns"] - self.model["origin_qpc_ns"]) // 1000)
            self.assertEqual(lane["first_remainder_ns"],
                             (lane["acquisition_qpc_ns"] - self.model["origin_qpc_ns"]) % 1000)

    def test_companion_preserves_null_zero_and_quality(self):
        pins = {"host_sha256": "1" * 64, "trace_sha256": "2" * 64}
        invalid = next(lane for lane in self.model["lanes"] if not lane["valid_sample"])
        zero = next(lane for lane in self.model["lanes"] if lane["valid_sample"] and
                    lane["channel"] == 3 and lane["count"] == 0)
        invalid_view = adapter.companion_for_lane(self.model, invalid, decoder_pins=pins)
        zero_view = adapter.companion_for_lane(self.model, zero, decoder_pins=pins)
        self.assertEqual(invalid_view["profile"]["original_values"], [None])
        self.assertEqual(invalid_view["original_source_qpc_ns"], None)
        self.assertEqual(zero_view["profile"]["original_values"], [0])
        self.assertTrue(zero_view["derived_flags"]["valid"])
        self.assertFalse(zero_view["derived_flags"]["held"])
        self.assertEqual(zero_view["global_quality_13bits"], 1807)
        fresh_zero = next(lane for lane in self.model["lanes"] if lane["valid_sample"] and
                          lane["channel"] == 3 and lane["count"] == 0 and
                          lane["adc_tick_ms"] == lane["em_tick_ms"])
        fresh_zero_view = adapter.companion_for_lane(self.model, fresh_zero, decoder_pins=pins)
        self.assertEqual(fresh_zero_view["global_quality_13bits"], 15)
        self.assertEqual(invalid_view["global_quality_13bits"], 7)
        self.assertFalse(invalid_view["current_source_eligible"])
        self.assertEqual(invalid_view["authority"]["current_source_eligible"], False)
        self.assertEqual(invalid_view["authority"]["actual_A_Root"], "UNAVAILABLE")
        self.assertEqual(invalid_view["fixture_transport_identity"]["label"], adapter.FIXTURE_KIND)
        self.assertEqual(invalid_view["binding"]["profile_id"], adapter.PROFILE_ID)
        self.assertEqual(invalid_view["profile"]["original_values"], [None])

    def test_cost_counts_every_companion_byte(self):
        wires = [lane["expected_wire_bytes"] for lane in self.model["lanes"]]
        companions = [len(adapter.canonical(adapter.companion_for_lane(
            self.model, lane, decoder_pins={"host_sha256": "1" * 64,
                                             "trace_sha256": "2" * 64})))
                      for lane in self.model["lanes"]]
        cost = adapter.cost_summary(self.model, wires, companions)
        self.assertEqual(cost["wire_bytes"], 3038)
        self.assertEqual(cost["mandatory_companion_bytes"], sum(companions))
        self.assertEqual(cost["total_serialized_bytes"], 3038 + sum(companions))
        self.assertEqual(cost["raw_value_only_bytes"], 142)
        self.assertEqual(cost["public_150b_or_8s_budget"], "NOT_ACCEPTED")

    def test_complete_prefix_does_not_lose_first_frame(self):
        frame = struct.pack("<2sBBBBHI", b"\xA5\x5A", 3, 0xE4, 0, 7, 1, 0) + b"\0\0"
        frames, offset = semantic.complete_frames_prefix(frame + frame + b"\xA5\x5A\x03")
        self.assertEqual(frames, [frame, frame])
        self.assertEqual(offset, 2 * len(frame))

    def test_duplicate_json_is_refused(self):
        with self.assertRaisesRegex(adapter.Rejected, "duplicate JSON key"):
            adapter.load_json_strict(b'{"schema":"a","schema":"b"}')

    def test_private_source_values_are_not_in_projection(self):
        private = json.dumps(fixture.build_private_records(), sort_keys=True)
        public = json.dumps(self.projection, sort_keys=True)
        self.assertIn("channel_values", private)
        self.assertNotIn('"channel_values"', public)


if __name__ == "__main__":
    unittest.main(verbosity=2)
