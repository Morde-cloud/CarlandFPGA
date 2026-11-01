import copy
import json
import pathlib
import sys
import unittest


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import g05p_capture_decoder132 as decoder


FIXTURE = HERE / "fixtures" / "valid32_synthetic.json"


def fresh_request():
    with FIXTURE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def set_command(request, *, yaw_q, pitch_q, speed, profile, ttl_ms):
    request = copy.deepcopy(request)
    words = request["raw_words"]
    words[3] = (speed << 8) | profile
    words[4] = ((pitch_q & 0xFFFF) << 16) | (yaw_q & 0xFFFF)
    words[5] = ttl_ms
    words[8] = words[6] + ttl_ms * decoder.TTL_TICKS_PER_MS
    words[9] = 0
    words[15] = decoder.YAW_PITCH_BASE + decoder.YAW_PITCH_STEP * yaw_q
    words[16] = decoder.YAW_PITCH_BASE + decoder.YAW_PITCH_STEP * pitch_q
    words[17] = decoder.SPEED_BASE + decoder.SPEED_STEP * speed
    record = request["original_record"]
    record["decision"] = {
        "yaw_q": yaw_q,
        "pitch_q": pitch_q,
        "profile": profile,
        "speed": speed,
        "ttl_ms": ttl_ms,
    }
    record["deadline_tick"] = words[8]
    return request


def set_period(request, period):
    request = copy.deepcopy(request)
    words = request["raw_words"]
    for index in range(3):
        words[12 + index] = period
        words[24 + 2 * index] = words[18 + 2 * index] + period
        words[25 + 2 * index] = 0
    return request


class ValidFixtureTests(unittest.TestCase):
    def test_hand_calculated_valid_fixture(self):
        result = decoder.decode_request(fresh_request())
        self.assertEqual(result["status"], "DECODED_PARTIAL_ASSOCIATION")
        self.assertEqual(result["refusal"], None)
        self.assertFalse(result["limits"]["motion_authority"])
        self.assertFalse(result["limits"]["formal_acceptance"])
        self.assertEqual(result["association"]["status"], "MECHANICALLY_MATCHED_AVAILABLE_FIELDS")
        self.assertFalse(result["association"]["full_identity_bound_to_capture"])
        self.assertFalse(result["association"]["authenticated"])
        self.assertIn("capture_sequence32", result["association"]["matching_dimensions"])
        self.assertIn("result64", result["association"]["matching_dimensions"])

        facts = result["facts"]
        self.assertEqual(facts["capture_sequence"], 1)
        self.assertEqual(facts["command_id"], 1)
        self.assertEqual(facts["transport_tag"], 4097)
        self.assertEqual(facts["session"], 2004318071)
        self.assertEqual(facts["magic"], "0x47303550")
        self.assertEqual(facts["timestamps"]["applied_tick"], 1000000)
        self.assertEqual(facts["timestamps"]["deadline_tick"], 6000000)
        self.assertEqual(facts["timestamps"]["result_tick"], 4000000)
        self.assertEqual(facts["timestamps"]["ttl_ticks"], 5000000)
        self.assertEqual([channel["period_ticks_sampled"] for channel in facts["pwm_channels"]],
                         [1000000, 1000000, 1000000])
        self.assertEqual([channel["high_ticks_sampled"] for channel in facts["pwm_channels"]],
                         [125800, 123400, 35000])
        self.assertEqual([channel["start_witness_tick_local"] for channel in facts["pwm_channels"]],
                         [100, 101, 100])
        self.assertEqual([channel["end_witness_tick_local"] for channel in facts["pwm_channels"]],
                         [1000100, 1000101, 1000100])
        self.assertEqual(facts["measured_mapper_candidate"]["yaw_q"], 100)
        self.assertEqual(facts["measured_mapper_candidate"]["pitch_q"], -200)
        self.assertEqual(facts["measured_mapper_candidate"]["speed_code"], 20)
        self.assertEqual(facts["measured_mapper_candidate"]["curvature_sum"], 50000)
        self.assertEqual(facts["measured_mapper_candidate"]["curvature_limit"], 51293849)

        mapped = result["mapped_target_reference"]
        self.assertEqual(mapped["yaw"]["target_rate_interval_ndeg_s"], [99875000, 100125000])
        self.assertEqual(mapped["pitch"]["target_rate_interval_ndeg_s"], [-200125000, -199875000])
        self.assertEqual(mapped["speed"]["target_speed_interval_nm_s"], [249975000, 250000000])
        self.assertTrue(mapped["speed"]["clip_to_mapper_domain"])
        self.assertEqual(mapped["discrete_mapper_candidate"]["target_speed_nm_s"], 250000000)
        self.assertEqual(mapped["interpretation"]["world_frame_transform"], "NOT_PROVIDED")

        encoded = json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.assertLessEqual(len(encoded), 65536)

    def test_original_record_null_is_facts_only(self):
        request = fresh_request()
        request["original_record"] = None
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "DECODED_FACTS_ONLY")
        self.assertEqual(result["association"]["mode"], "NONE")
        self.assertIsNotNone(result["facts"])
        self.assertFalse(result["limits"]["motion_authority"])

    def test_high_plus_one_tick_remains_in_mapper_tolerance(self):
        request = fresh_request()
        request["raw_words"][15] += 1
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "DECODED_PARTIAL_ASSOCIATION")
        self.assertEqual(result["facts"]["measured_mapper_candidate"]["yaw_q"], 100)


class NullAndCardinalityTests(unittest.TestCase):
    def test_missing_original_record_key_is_input_rejection(self):
        request = fresh_request()
        del request["original_record"]
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "INPUT_REJECTED")
        self.assertEqual(result["refusal"]["code"], "REQUEST_FIELDS")
        self.assertTrue(result["preserved_input"]["raw_words_preserved"])
        self.assertEqual(result["preserved_input"]["raw_words"], request["raw_words"])

    def test_null_word_is_not_zero(self):
        request = fresh_request()
        request["raw_words"][15] = None
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "INPUT_REJECTED")
        self.assertEqual(result["refusal"]["code"], "RAW_WORD_TYPE")
        self.assertTrue(result["preserved_input"]["raw_words_preserved"])
        self.assertIsNone(result["preserved_input"]["raw_words"][15])

    def test_zero_capture_sequence_is_numeric_but_capture_refusal(self):
        request = fresh_request()
        request["raw_words"][0] = 0
        request["original_record"]["capture_seq"] = 0
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_CAPTURE")
        self.assertEqual(result["refusal"]["code"], "CAPTURE_SEQUENCE")
        self.assertEqual(result["preserved_input"]["raw_words"][0], 0)

    def test_boolean_word_is_rejected(self):
        request = fresh_request()
        request["raw_words"][15] = True
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "INPUT_REJECTED")
        self.assertEqual(result["refusal"]["code"], "RAW_WORD_TYPE")

    def test_wrong_raw_cardinality_preserves_available_words(self):
        request = fresh_request()
        request["raw_words"] = request["raw_words"][:-1]
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "INPUT_REJECTED")
        self.assertEqual(result["refusal"]["code"], "RAW_CARDINALITY")
        self.assertTrue(result["preserved_input"]["raw_words_preserved"])
        self.assertEqual(len(result["preserved_input"]["raw_words"]), 31)

    def test_empty_original_record_is_association_refusal_not_null(self):
        request = fresh_request()
        request["original_record"] = {}
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "RECORD_MISSING_FIELDS")
        self.assertIsNotNone(result["facts"])

    def test_extra_request_field_is_rejected_before_key_traversal(self):
        request = fresh_request()
        request["extra"] = "bounded"
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "INPUT_REJECTED")
        self.assertEqual(result["refusal"]["code"], "REQUEST_FIELDS")
        self.assertTrue(result["preserved_input"]["raw_words_preserved"])

    def test_non_string_request_key_is_rejected_before_set_operations(self):
        request = fresh_request()
        request[1] = request.pop("schema")
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "INPUT_REJECTED")
        self.assertEqual(result["refusal"]["code"], "REQUEST_FIELDS")
        self.assertTrue(result["preserved_input"]["raw_words_preserved"])

    def test_oversized_record_is_bounded_input_refusal(self):
        request = fresh_request()
        request["original_record"] = {f"field_{index}": 0 for index in range(33)}
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "INPUT_REJECTED")
        self.assertEqual(result["refusal"]["code"], "RECORD_BOUNDS")
        self.assertTrue(result["preserved_input"]["raw_words_preserved"])
        self.assertFalse(result["preserved_input"]["original_record_preserved"])

    def test_record_preservation_budget_keeps_result_bounded(self):
        request = fresh_request()
        request["original_record"] = {
            f"field_{index}": ["x" * 128 for _ in range(8)] for index in range(32)
        }
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "INPUT_REJECTED")
        self.assertEqual(result["refusal"]["code"], "RECORD_BOUNDS")
        self.assertFalse(result["preserved_input"]["original_record_preserved"])
        encoded = json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.assertLessEqual(len(encoded), 65536)

    def test_huge_raw_integer_keeps_refusal_bounded(self):
        request = fresh_request()
        request["raw_words"][0] = 10 ** 10_000
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "INPUT_REJECTED")
        self.assertEqual(result["refusal"]["code"], "RAW_WORD_TYPE")
        self.assertFalse(result["preserved_input"]["raw_words_preserved"])
        encoded = json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.assertLessEqual(len(encoded), 65536)

    def test_huge_record_integer_keeps_refusal_bounded(self):
        request = fresh_request()
        request["original_record"]["applied_tick"] = 10 ** 10_000
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "INPUT_REJECTED")
        self.assertEqual(result["refusal"]["code"], "RECORD_BOUNDS")
        self.assertTrue(result["preserved_input"]["raw_words_preserved"])
        self.assertFalse(result["preserved_input"]["original_record_preserved"])
        encoded = json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.assertLessEqual(len(encoded), 65536)


class CaptureRefusalTests(unittest.TestCase):
    def test_magic_mismatch(self):
        request = fresh_request()
        request["raw_words"][31] ^= 1
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_CAPTURE")
        self.assertEqual(result["refusal"]["code"], "MAGIC_MISMATCH")

    def test_period_tolerance_accepts_one_and_rejects_two(self):
        accepted = decoder.decode_request(set_period(fresh_request(), 999999))
        self.assertEqual(accepted["status"], "DECODED_PARTIAL_ASSOCIATION")
        rejected = decoder.decode_request(set_period(fresh_request(), 999998))
        self.assertEqual(rejected["status"], "REFUSED_CAPTURE")
        self.assertEqual(rejected["refusal"]["code"], "PERIOD_TOLERANCE")

    def test_high_tolerance_rejects_two_ticks(self):
        request = fresh_request()
        request["raw_words"][15] += 2
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_CAPTURE")
        self.assertEqual(result["refusal"]["code"], "MEASURED_HIGH_MISMATCH")
        self.assertTrue(result["preserved_input"]["original_record_preserved"])

    def test_start_trio_span_rejects_two_ticks(self):
        request = fresh_request()
        request["raw_words"][20] = 102
        request["raw_words"][26] = 1000102
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_CAPTURE")
        self.assertEqual(result["refusal"]["code"], "START_TRIO_SPAN")

    def test_period_trio_one_tick_apart_is_accepted(self):
        request = fresh_request()
        request["raw_words"][12] = 999999
        request["raw_words"][13] = 1000000
        request["raw_words"][14] = 1000001
        request["raw_words"][18] = 101
        request["raw_words"][20] = 100
        request["raw_words"][22] = 100
        request["raw_words"][24] = 1000100
        request["raw_words"][26] = 1000100
        request["raw_words"][28] = 1000101
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "DECODED_PARTIAL_ASSOCIATION")
        self.assertEqual([channel["period_ticks_sampled"] for channel in result["facts"]["pwm_channels"]],
                         [999999, 1000000, 1000001])

    def test_nonzero_witness_upper_word_is_refused(self):
        for high_word in (19, 21, 23, 25, 27, 29):
            with self.subTest(high_word=high_word):
                request = fresh_request()
                request["raw_words"][high_word] = 1
                result = decoder.decode_request(request)
                self.assertEqual(result["status"], "REFUSED_CAPTURE")
                self.assertEqual(result["refusal"]["code"], "WITNESS_UPPER_WORD")

    def test_end_minus_start_must_equal_period(self):
        request = fresh_request()
        request["raw_words"][24] += 1
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_CAPTURE")
        self.assertEqual(result["refusal"]["code"], "WITNESS_PERIOD_MISMATCH")

    def test_wrong_profile_is_refused(self):
        request = set_command(fresh_request(), yaw_q=0, pitch_q=0, speed=1, profile=3, ttl_ms=100)
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_CAPTURE")
        self.assertEqual(result["refusal"]["code"], "PROFILE_UNSUPPORTED")

    def test_zero_speed_requires_zero_axes(self):
        request = set_command(fresh_request(), yaw_q=1, pitch_q=0, speed=0, profile=1, ttl_ms=100)
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_CAPTURE")
        self.assertEqual(result["refusal"]["code"], "ZERO_SPEED_AXES")

    def test_ttl_deadline_mismatch(self):
        request = fresh_request()
        request["raw_words"][8] += 1
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_CAPTURE")
        self.assertEqual(result["refusal"]["code"], "TTL_CYCLE_MISMATCH")

    def test_result_tick_must_cover_local_end(self):
        request = fresh_request()
        request["raw_words"][10] = 2000100
        request["original_record"]["result_tick"] = 2000100
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_CAPTURE")
        self.assertEqual(result["refusal"]["code"], "RESULT_CYCLE_BOUNDS")

    def test_external_phase_before_two_periods_is_accepted(self):
        request = fresh_request()
        request["raw_words"][10] = 2000108
        request["original_record"]["result_tick"] = 2000108
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "DECODED_PARTIAL_ASSOCIATION")
        self.assertEqual(result["facts"]["timestamps"]["result_tick"], 2000108)

    def test_result_tick_at_deadline_is_refused(self):
        request = fresh_request()
        request["raw_words"][10] = 6000000
        request["original_record"]["result_tick"] = 6000000
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_CAPTURE")
        self.assertEqual(result["refusal"]["code"], "RESULT_CYCLE_BOUNDS")


class AssociationRefusalTests(unittest.TestCase):
    def test_stale_session_is_refused_but_facts_and_raw_are_preserved(self):
        request = fresh_request()
        request["original_record"]["identity_words"][12] = 123
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "SESSION_MISMATCH")
        self.assertEqual(result["preserved_input"]["raw_words"], request["raw_words"])
        self.assertEqual(result["preserved_input"]["original_record"], request["original_record"])
        self.assertIsNotNone(result["facts"])
        self.assertEqual(result["facts"]["session"], 2004318071)

    def test_retired_status_is_refused(self):
        request = fresh_request()
        request["original_record"]["status_before"] |= 0x02
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "STATUS_RETIRED")

    def test_pre_latch_status_must_report_latest_eligible(self):
        request = fresh_request()
        request["original_record"]["status_before"] &= ~0x10
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "STATUS_NOT_LATCH_READY")

    def test_pre_latch_status_cannot_already_hold_a_capture(self):
        request = fresh_request()
        request["original_record"]["status_before"] |= 0x20
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "STATUS_LATCH_ALREADY_VALID")

    def test_post_latch_status_must_report_latch_valid(self):
        request = fresh_request()
        request["original_record"]["status_after"] &= ~0x20
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "STATUS_LATCH_NOT_HELD")

    def test_status_reserved_bit_is_refused(self):
        request = fresh_request()
        request["original_record"]["status_after"] |= 0x80
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "STATUS_RESERVED_BITS")

    def test_pending_status_is_refused(self):
        request = fresh_request()
        request["original_record"]["status_after"] |= 0x08
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "STATUS_PENDING")

    def test_missing_run_identity_is_refused(self):
        request = fresh_request()
        request["original_record"]["identity_words"][0:8] = [0] * 8
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "IDENTITY_RUN_ZERO")

    def test_missing_nonce_identity_is_refused(self):
        request = fresh_request()
        request["original_record"]["identity_words"][8:12] = [0] * 4
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "IDENTITY_NONCE_ZERO")

    def test_stale_capture_sequence_is_refused(self):
        request = fresh_request()
        request["original_record"]["previous_capture_seq"] = 1
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "CAPTURE_SEQUENCE_STALE")

    def test_capture_sequence_maximum_is_a_valid_last_sequence(self):
        request = fresh_request()
        request["raw_words"][0] = 0xFFFFFFFF
        request["original_record"]["capture_seq"] = 0xFFFFFFFF
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "DECODED_PARTIAL_ASSOCIATION")
        self.assertIsNone(result["refusal"])

    def test_stale_command_sequence_is_refused(self):
        request = fresh_request()
        request["original_record"]["previous_command_id"] = 1
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "COMMAND_SEQUENCE_STALE")

    def test_changed_transport_tag_is_refused(self):
        request = fresh_request()
        request["original_record"]["transport_tag"] = 4098
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "TAG_MISMATCH")

    def test_changed_result_tick_is_refused(self):
        request = fresh_request()
        request["original_record"]["result_tick"] = 4000001
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "RESULT_TICK_MISMATCH")

    def test_non_string_operation_id_is_refused(self):
        request = fresh_request()
        request["original_record"]["operation_id"] = 132
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
        self.assertEqual(result["refusal"]["code"], "OPERATION_ID")


class MapperBoundaryTests(unittest.TestCase):
    def test_fast_speed_one_curvature_boundary_accepts_358(self):
        request = set_command(fresh_request(), yaw_q=358, pitch_q=0, speed=1, profile=1, ttl_ms=100)
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "DECODED_PARTIAL_ASSOCIATION")
        self.assertEqual(result["facts"]["measured_mapper_candidate"]["curvature_sum"], 128164)
        self.assertEqual(result["facts"]["measured_mapper_candidate"]["curvature_limit"], 128234)
        self.assertEqual(result["mapped_target_reference"]["yaw"]["target_rate_interval_ndeg_s"],
                         [357875000, 358125000])

    def test_fast_speed_one_curvature_boundary_rejects_359(self):
        request = set_command(fresh_request(), yaw_q=359, pitch_q=0, speed=1, profile=1, ttl_ms=100)
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_CAPTURE")
        self.assertEqual(result["refusal"]["code"], "CURVATURE_ROM")

    def test_speed_zero_zero_axes_is_valid(self):
        request = set_command(fresh_request(), yaw_q=0, pitch_q=0, speed=0, profile=1, ttl_ms=100)
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "DECODED_PARTIAL_ASSOCIATION")
        self.assertEqual(result["facts"]["measured_mapper_candidate"]["speed_code"], 0)
        self.assertEqual(result["mapped_target_reference"]["speed"]["target_speed_interval_nm_s"],
                         [0, 25000])

    def test_profile_ttl_cap_is_enforced_by_mapper(self):
        request = set_command(fresh_request(), yaw_q=0, pitch_q=0, speed=1, profile=2, ttl_ms=12001)
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "REFUSED_CAPTURE")
        self.assertEqual(result["refusal"]["code"], "TTL_RANGE")

    def test_reported_output_uses_no_float(self):
        result = decoder.decode_request(fresh_request())

        def no_float(value):
            if isinstance(value, float):
                return False
            if isinstance(value, dict):
                return all(no_float(k) and no_float(v) for k, v in value.items())
            if isinstance(value, list):
                return all(no_float(v) for v in value)
            return True

        self.assertTrue(no_float(result))


if __name__ == "__main__":
    unittest.main()
