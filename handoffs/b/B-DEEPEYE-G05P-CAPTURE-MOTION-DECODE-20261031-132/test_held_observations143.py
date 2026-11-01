"""Independent synthetic checks for retained observations and boundary conditions."""
import copy
import unittest

import g05p_capture_decoder132 as decoder
from test_g05p_capture_decoder132 import fresh_request


def bracket_request():
    request = fresh_request()
    # Independently specified readings in the synthetic scenario.
    before = dict(identity_words=list(range(11, 23)) + [2004318071], magic=0x47303550,
                  layout=2, status=53, fault=0, command_id=1, transport_tag=4097,
                  applied_tick=1000000, deadline_tick=6000000, held_capture_seq=1,
                  cycle_tick=4000001, latest_seq=2)
    after = copy.deepcopy(before)
    after.update(cycle_tick=4000060, latest_seq=3)
    request["held_observations"] = dict(before=before, after=after)
    return request


class HeldBankTests(unittest.TestCase):
    def test_held_sequence_survives_advancing_latest(self):
        result = decoder.decode_request(bracket_request())
        self.assertEqual(result["status"], "DECODED_BRACKET_CORRELATED")
        self.assertTrue(result["association"]["full_external_identity_matched"])
        self.assertFalse(result["limits"]["motion_authority"])
        self.assertEqual(result["limits"]["electrical_loopback"], "UNVERIFIED")

    def test_identity_and_lifetime_corruption(self):
        for field, value in (("identity_words", [1]*12+[2004318071]), ("fault", 2),
                             ("layout", 3), ("status", 21), ("transport_tag", 4098),
                             ("held_capture_seq", 2), ("cycle_tick", 6000000),
                             ("cycle_tick", 4000000), ("applied_tick", 1000001)):
            with self.subTest(field=field, value=value):
                request = bracket_request()
                request["held_observations"]["after"][field] = value
                result = decoder.decode_request(request)
                self.assertEqual(result["status"], "REFUSED_ASSOCIATION")
                self.assertEqual(result["preserved_input"]["raw_words"], request["raw_words"])
                self.assertEqual(result["preserved_input"]["held_observations"], request["held_observations"])
                self.assertIsNotNone(result["facts"])

    def test_missing_observation_cannot_correlate(self):
        request = bracket_request()
        del request["held_observations"]["before"]
        self.assertEqual(decoder.decode_request(request)["status"], "REFUSED_ASSOCIATION")

    def test_zero_local_witness_cannot_pass(self):
        request = fresh_request()
        request["raw_words"][18:24] = [0,0,1,0,0,0]
        request["raw_words"][24:30] = [1000000,0,1000001,0,1000000,0]
        self.assertEqual(decoder.decode_request(request)["refusal"]["code"], "WITNESS_PERIOD_MISMATCH")

    def test_measurement_tolerance_reaches_output(self):
        request = bracket_request()
        request["raw_words"][15] += 1
        result = decoder.decode_request(request)
        self.assertEqual(result["status"], "DECODED_BRACKET_CORRELATED")
        self.assertEqual(result["mapped_target_reference"]["yaw"]["target_rate_interval_ndeg_s"],
                         [100000000, 100250000])
        self.assertEqual(result["facts"]["pwm_channels"][0]["high_ticks_sampled"], 125801)

