"""Focused controls for the source83 structural host lease ledger."""

import sys
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[3] / "tools" / "diagnostic" / "host_lease83"
sys.path.insert(0, str(SOURCE))
import host_lease83 as hl

T0, MAX = 1_000_000_000, hl.U63_MAX
PAYLOAD = "a" * 64


def request(seq=1, *, first_send_ns=T0, original_ttl_ms=12000,
            profile="STRESS_300", **changes):
    value = {
        "session": "session-b", "request_type": hl.REQUEST_TYPE, "seq": seq,
        "cmd_id": seq, "payload_sha256": PAYLOAD, "transaction_tag": f"tag-{seq}",
        "boot_id": "boot-1", "epoch": 7, "first_send_ns": first_send_ns,
        "original_ttl_ms": original_ttl_ms, "profile": profile,
        "context": {"text": "原始完整文本", "qpc": MAX - 9, "seq": seq},
    }
    value.update(changes)
    return value


def ack(req, *, receipt_ns=T0 + 2_000_000_000, remaining_ttl_ms=8000,
        phase="CAPTURED", capture_complete=True, fault=0,
        usb_processing_bound_ns=1_000_000, clock_error_bound_ns=1_000_000,
        **changes):
    value = dict(req)
    value.update({
        "receipt_ns": receipt_ns, "phase": phase, "capture_complete": capture_complete,
        "fault": fault, "remaining_ttl_ms": remaining_ttl_ms,
        "usb_processing_bound_ns": usb_processing_bound_ns,
        "clock_error_bound_ns": clock_error_bound_ns,
    })
    value.update(changes)
    return value


def started(seq=1, **changes):
    ledger = hl.HostLeaseLedger(mode=hl.SYNTHETIC_FIXTURE)
    original = request(seq=seq, **changes)
    registration = ledger.register(original)
    assert registration["status"] == "REGISTERED"
    return ledger, original, registration


class HostLeaseSourceControls(unittest.TestCase):
    def test_delayed_ack_8s_keeps_12s_original_cap(self):
        ledger, original, registration = started()
        recorded = ledger.ack(ack(original, receipt_ns=T0 + 8_000_000_000))
        result = ledger.evaluate_deadline(original, T0 + 8_000_000_000)
        self.assertEqual(registration["original_cap_ns"], T0 + 12_000_000_000)
        self.assertEqual(recorded["reason"], "EXPLICIT_DEADLINE_QUERY_REQUIRED")
        self.assertEqual(result["deadline_ns"], registration["original_cap_ns"])
        self.assertEqual(result["remaining_ns"], 4_000_000_000)
        self.assertEqual(result["status"], "LEASE")

    def test_lost_first_ack_and_state_do_not_move_origin(self):
        ledger, original, registration = started()
        duplicate = ledger.register(original)
        result = ledger.ack(ack(original, receipt_ns=T0 + 6_000_000_000,
                                remaining_ttl_ms=4000))
        self.assertEqual(duplicate["status"], "DUPLICATE")
        self.assertFalse(duplicate["sent"])
        self.assertEqual(result["first_send_ns"], T0)
        self.assertEqual(result["original_ttl_ms"], 12000)
        self.assertEqual(result["original_cap_ns"], registration["original_cap_ns"])
        self.assertEqual(result["transaction_tag"], "tag-1")

    def test_later_ack_cannot_extend_short_deadline(self):
        ledger, original, _ = started()
        first = ledger.ack(ack(original, receipt_ns=T0 + 1_100_000_000,
                               remaining_ttl_ms=2000))
        second = ledger.ack(ack(original, receipt_ns=T0 + 1_500_000_000,
                                remaining_ttl_ms=10000))
        query = ledger.evaluate_deadline(original, T0 + 1_500_000_000)
        self.assertEqual(second["deadline_ns"], first["deadline_ns"])
        self.assertEqual(query["deadline_ns"], first["deadline_ns"])
        self.assertGreater(query["remaining_ns"], 0)

    def test_duplicate_ack_adds_no_record_and_cannot_extend(self):
        ledger, original, _ = started()
        first, duplicate = ledger.ack(ack(original)), ledger.ack(ack(original))
        query = ledger.evaluate_deadline(original, T0 + 2_000_000_000)
        self.assertEqual(duplicate["status"], "DUPLICATE_ACK")
        self.assertEqual(duplicate["ack_count"], 1)
        self.assertEqual(duplicate["deadline_ns"], first["deadline_ns"])
        self.assertEqual(query["deadline_ns"], first["deadline_ns"])

    def test_cancel_and_fault_never_revive(self):
        ledger, original, _ = started()
        canceled = ledger.terminate(original, at_ns=T0 + 1_000_000_000, reason="CANCEL")
        after = ledger.ack(ack(original, receipt_ns=T0 + 2_000_000_000))
        faulted, fault_original, _ = started(seq=2)
        fault = faulted.ack(ack(fault_original, receipt_ns=T0 + 1_000_000_000, fault=1))
        after_fault = faulted.ack(ack(fault_original, receipt_ns=T0 + 2_000_000_000))
        query = ledger.evaluate_deadline(original, T0 + 2_000_000_000)
        self.assertEqual(canceled["terminal"], "CANCEL")
        self.assertEqual(after["terminal"], "CANCEL")
        self.assertEqual(after["status"], "INPUT_UNAVAILABLE")
        self.assertEqual(fault["terminal"], "FAULT")
        self.assertEqual(after_fault["terminal"], "FAULT")
        self.assertEqual(query["status"], "INPUT_UNAVAILABLE")

    def test_original_cap_expiry_is_terminal(self):
        ledger, original, _ = started()
        result = ledger.ack(ack(original, receipt_ns=T0 + 12_000_000_000,
                                remaining_ttl_ms=12000))
        self.assertEqual(result["terminal"], "EXPIRED")
        self.assertEqual(result["status"], "INPUT_UNAVAILABLE")
        self.assertEqual(ledger.evaluate_deadline(
            original, T0 + 12_000_000_000)["terminal"], "EXPIRED")

    def test_new_boot_and_newer_epoch_invalidate(self):
        ledger = hl.HostLeaseLedger(mode=hl.SYNTHETIC_FIXTURE)
        first, second = request(seq=1), request(seq=2)
        ledger.register(first); ledger.register(second)
        boot = ledger.terminate(first, at_ns=T0 + 1_100_000_000,
                                reason="NEW_BOOT", newer_boot_id="boot-2")
        epoch = ledger.terminate(second, at_ns=T0 + 1_200_000_000,
                                 reason="EPOCH", newer_epoch=8)
        after = ledger.ack(ack(first, receipt_ns=T0 + 1_300_000_000))
        self.assertEqual((boot["terminal"], epoch["terminal"]), ("NEW_BOOT", "EPOCH"))
        self.assertEqual(after["status"], "INPUT_UNAVAILABLE")

    def test_zero_remaining_has_no_grace(self):
        ledger, original, _ = started()
        result = ledger.ack(ack(original, remaining_ttl_ms=0))
        self.assertEqual(result["terminal"], "EXPIRED")
        self.assertEqual(result["status"], "INPUT_UNAVAILABLE")

    def test_exact_serialization_and_bounds_leave_zero_window(self):
        ledger, original, _ = started()
        result = ledger.ack(ack(original, remaining_ttl_ms=1134,
                                usb_processing_bound_ns=666_666,
                                clock_error_bound_ns=0))
        self.assertEqual(result["terminal"], "EXPIRED")
        self.assertEqual(result["status"], "INPUT_UNAVAILABLE")

    def test_serialization_ceilings_at_both_bauds(self):
        self.assertEqual(hl.wire_ns(300), 1_133_333_334)
        self.assertEqual(hl.wire_ns(9600), 35_416_667)
        with self.assertRaises(hl.Refused):
            hl.wire_ns(115200)

    def test_missing_bounds_are_unavailable_and_negative_refused(self):
        ledger, original, _ = started()
        missing = ledger.ack(ack(original, usb_processing_bound_ns=None,
                                 clock_error_bound_ns=None))
        self.assertEqual(missing["reason"], "BOUNDS_UNAVAILABLE")
        self.assertIsNone(missing["deadline_ns"])
        self.assertIsNone(missing["terminal"])
        with self.assertRaises(hl.Refused):
            ledger.ack(ack(original, receipt_ns=T0 + 3_000_000_000,
                           usb_processing_bound_ns=-1))

    def test_wrong_full_identity_refused_while_disabled(self):
        ledger, original, _ = started()
        ledger.disable()
        self.assertEqual(ledger.ack(ack(original))["status"], "INPUT_UNAVAILABLE")
        baseline = ack(original, receipt_ns=T0 + 4_000_000_000)
        mutations = {
            "session": "other", "request_type": 0x0F, "seq": 2, "cmd_id": 99,
            "payload_sha256": "b" * 64, "transaction_tag": "other",
            "boot_id": "boot-2", "epoch": 8, "first_send_ns": T0 + 1,
            "original_ttl_ms": 11999, "profile": "FAST_9600",
            "context": {"text": "changed", "qpc": MAX - 9, "seq": 1},
        }
        for field, value in mutations.items():
            with self.subTest(field=field), self.assertRaises(hl.Refused):
                ledger.ack({**baseline, field: value})

    def test_strict_types_nan_custom_and_oversized_context(self):
        with self.assertRaises(hl.Refused):
            hl.HostLeaseLedger(mode=hl.SYNTHETIC_FIXTURE).register(request(seq=True))
        with self.assertRaises(hl.Refused):
            hl.HostLeaseLedger(mode=1)
        ledger, original, _ = started()
        with self.assertRaises(hl.Refused):
            ledger.ack(ack(original, receipt_ns=2.0))
        with self.assertRaises(hl.Refused):
            ledger.ack(ack(original, capture_complete=1))
        for bad in ({"bad": float("nan")}, {"bad": object()}, {"text": "x" * 4097}):
            with self.subTest(bad=type(next(iter(bad.values())))), self.assertRaises(hl.Refused):
                hl.HostLeaseLedger(mode=hl.SYNTHETIC_FIXTURE).register(request(context=bad))

    def test_large_uint63_context_and_times_are_not_masked(self):
        first = MAX - 100_000_000_000
        context = {"qpc": MAX, "origin": first, "text": "large-original"}
        ledger, original, registration = started(first_send_ns=first, context=context)
        recorded = ledger.ack(ack(original, receipt_ns=first + 8_000_000_000))
        result = ledger.evaluate_deadline(original, first + 8_000_000_000)
        self.assertEqual(registration["context"]["qpc"], MAX)
        self.assertEqual(registration["original_context"]["qpc"], MAX)
        self.assertEqual(registration["context"]["text"], "large-original")
        self.assertEqual(registration["first_send_ns"], first)
        self.assertEqual(registration["original_cap_ns"], first + 12_000_000_000)
        self.assertEqual(recorded["deadline_ns"], first + 12_000_000_000)
        self.assertEqual(result["deadline_ns"], first + 12_000_000_000)

    def test_uint63_overflow_and_timestamp_regression_refused(self):
        with self.assertRaises(hl.Refused):
            hl.HostLeaseLedger(mode=hl.SYNTHETIC_FIXTURE).register(
                request(first_send_ns=MAX - 1_000_000))
        ledger, original, _ = started()
        ledger.ack(ack(original, receipt_ns=T0 + 2_000_000_000))
        with self.assertRaises(hl.Refused):
            ledger.register(request(seq=2, first_send_ns=T0 + 1_000_000_000))

    def test_transaction_16_and_ack_8_capacity_no_eviction(self):
        ledger = hl.HostLeaseLedger(mode=hl.SYNTHETIC_FIXTURE)
        requests = [request(seq=i) for i in range(1, 17)]
        for value in requests:
            ledger.register(value)
        with self.assertRaises(hl.Refused):
            ledger.register(request(seq=17))
        for offset in range(8):
            result = ledger.ack(ack(requests[0], receipt_ns=T0 + 2_000_000_000 + offset))
            self.assertEqual(result["status"], "INPUT_UNAVAILABLE")
            self.assertTrue(result["captured_eligible"])
        with self.assertRaises(hl.Refused):
            ledger.ack(ack(requests[0], receipt_ns=T0 + 2_000_000_008))
        self.assertEqual(result["ack_count"], 8)

    def test_accepted_applied_and_incomplete_capture_are_insufficient(self):
        ledger, original, _ = started()
        for offset, phase, complete in (
            (1, "ACCEPTED", True), (2, "APPLIED", True), (3, "CAPTURED", False)
        ):
            result = ledger.ack(ack(original, receipt_ns=T0 + offset * 100_000_000,
                                    phase=phase, capture_complete=complete))
            self.assertEqual(result["status"], "INPUT_UNAVAILABLE")
            self.assertIsNone(result["terminal"])
        recorded = ledger.ack(ack(original, receipt_ns=T0 + 500_000_000))
        good = ledger.evaluate_deadline(original, T0 + 600_000_000)
        self.assertEqual(recorded["reason"], "EXPLICIT_DEADLINE_QUERY_REQUIRED")
        self.assertEqual(good["status"], "LEASE")

    def test_production_default_is_always_unavailable(self):
        original = request()
        ledger = hl.HostLeaseLedger()
        registration = ledger.register(original)
        result = ledger.ack(ack(original))
        query = ledger.evaluate_deadline(original, T0 + 2_000_000_000)
        self.assertEqual(registration["status"], "INPUT_UNAVAILABLE")
        self.assertEqual(result["status"], "INPUT_UNAVAILABLE")
        self.assertEqual(query["status"], "INPUT_UNAVAILABLE")
        self.assertFalse(query["sent"])
        self.assertFalse(query["physical_acceptance"])
        self.assertFalse(query["action_authorized"])

    def test_missing_required_ack_fields_are_refused_not_keyerror(self):
        ledger, original, _ = started()
        for field in ("receipt_ns", "phase", "capture_complete", "fault",
                      "remaining_ttl_ms"):
            value = ack(original)
            del value[field]
            with self.subTest(field=field), self.assertRaises(hl.Refused) as caught:
                ledger.ack(value)
            self.assertEqual(caught.exception.code, "ACK_MISSING")
        unknown = ack(original, surprise_field=1)
        with self.assertRaises(hl.Refused) as caught:
            ledger.ack(unknown)
        self.assertEqual(caught.exception.code, "ACK_UNKNOWN_FIELD")

    def test_explicit_deadline_boundary_and_regression(self):
        ledger, original, _ = started()
        recorded = ledger.ack(ack(original))
        deadline = recorded["deadline_ns"]
        before = ledger.evaluate_deadline(original, deadline - 1)
        at = ledger.evaluate_deadline(original, deadline)
        self.assertEqual(before["status"], "LEASE")
        self.assertEqual(before["remaining_ns"], 1)
        self.assertEqual(at["status"], "INPUT_UNAVAILABLE")
        self.assertEqual(at["terminal"], "EXPIRED")
        self.assertEqual(at["deadline_ns"], deadline)
        with self.assertRaises(hl.Refused) as caught:
            ledger.evaluate_deadline(original, deadline - 1)
        self.assertEqual(caught.exception.code, "TIME_REGRESSION")

    def test_query_validation_remains_strict_while_disabled(self):
        ledger, original, _ = started()
        ledger.disable()
        for query, now in (({**original, "session": "other"}, T0),
                           (original, True), (original, T0 - 1)):
            with self.subTest(now=now), self.assertRaises(hl.Refused):
                ledger.evaluate_deadline(query, now)
        self.assertEqual(ledger.evaluate_deadline(original, T0 + 1)["reason"],
                         "LEDGER_DISABLED")

    def test_stopped_and_rejected_phase_are_terminal(self):
        for seq, phase in ((1, "STOPPED"), (2, "REJECTED")):
            ledger, original, _ = started(seq=seq)
            stopped = ledger.ack(ack(original, receipt_ns=T0 + 1_000_000_000,
                                     phase=phase))
            later = ledger.ack(ack(original, receipt_ns=T0 + 1_100_000_000))
            query = ledger.evaluate_deadline(original, T0 + 1_100_000_000)
            self.assertEqual(stopped["terminal"], phase)
            self.assertEqual(later["terminal"], phase)
            self.assertEqual(query["terminal"], phase)

    def test_capture_loss_is_permanent(self):
        ledger, original, _ = started()
        ledger.ack(ack(original, receipt_ns=T0 + 1_000_000_000))
        lost = ledger.ack(ack(original, receipt_ns=T0 + 1_100_000_000,
                              capture_complete=False))
        later = ledger.ack(ack(original, receipt_ns=T0 + 1_200_000_000))
        query = ledger.evaluate_deadline(original, T0 + 1_200_000_000)
        self.assertEqual(lost["terminal"], "CAPTURE_LOST")
        self.assertEqual(later["terminal"], "CAPTURE_LOST")
        self.assertEqual(query["terminal"], "CAPTURE_LOST")
        self.assertNotEqual(query["status"], "LEASE")

    def test_phase_regression_after_capture_is_permanent(self):
        ledger, original, _ = started()
        ledger.ack(ack(original, receipt_ns=T0 + 1_000_000_000))
        regressed = ledger.ack(ack(original, receipt_ns=T0 + 1_100_000_000,
                                   phase="APPLIED"))
        later = ledger.ack(ack(original, receipt_ns=T0 + 1_200_000_000))
        self.assertEqual(regressed["terminal"], "PHASE_REGRESSION")
        self.assertEqual(later["terminal"], "PHASE_REGRESSION")
        self.assertEqual(ledger.evaluate_deadline(original, T0 + 1_200_000_000)
                         ["status"], "INPUT_UNAVAILABLE")

    def test_bounds_loss_after_capture_is_permanent(self):
        ledger, original, _ = started()
        ledger.ack(ack(original, receipt_ns=T0 + 1_000_000_000))
        lost = ledger.ack(ack(original, receipt_ns=T0 + 1_100_000_000,
                              usb_processing_bound_ns=None))
        later = ledger.ack(ack(original, receipt_ns=T0 + 1_200_000_000))
        self.assertEqual(lost["terminal"], "BOUNDS_UNAVAILABLE")
        self.assertEqual(later["terminal"], "BOUNDS_UNAVAILABLE")
        self.assertEqual(ledger.evaluate_deadline(original, T0 + 1_200_000_000)
                         ["terminal"], "BOUNDS_UNAVAILABLE")

    def test_missing_bounds_before_capture_may_become_available(self):
        ledger, original, _ = started()
        missing = ledger.ack(ack(original, receipt_ns=T0 + 1_000_000_000,
                                 usb_processing_bound_ns=None,
                                 clock_error_bound_ns=None))
        recorded = ledger.ack(ack(original, receipt_ns=T0 + 1_100_000_000))
        query = ledger.evaluate_deadline(original, T0 + 1_200_000_000)
        self.assertIsNone(missing["terminal"])
        self.assertEqual(recorded["reason"], "EXPLICIT_DEADLINE_QUERY_REQUIRED")
        self.assertEqual(query["status"], "LEASE")

    def test_checked_uint63_deductions_and_receipt_addition(self):
        ledger, original, _ = started()
        with self.assertRaises(hl.Refused) as caught:
            ledger.ack(ack(original, usb_processing_bound_ns=MAX,
                           clock_error_bound_ns=1))
        self.assertEqual(caught.exception.code, "UINT63_OVERFLOW")
        self.assertEqual(ledger.ack(ack(original))["ack_count"], 1)
        first = MAX - 20_000_000_000
        high, high_original, _ = started(seq=2, first_send_ns=first)
        with self.assertRaises(hl.Refused) as caught:
            high.ack(ack(high_original, receipt_ns=MAX - 100,
                         remaining_ttl_ms=8000))
        self.assertEqual(caught.exception.code, "UINT63_OVERFLOW")

    def test_raw_header_ticks_are_retained_separately(self):
        ledger, original, _ = started()
        first = ledger.ack(ack(original, raw_header_tick=MAX))
        second = ledger.ack(ack(original, receipt_ns=T0 + 2_100_000_000,
                                raw_header_tick=7))
        query = ledger.evaluate_deadline(original, T0 + 2_200_000_000)
        self.assertEqual(first["status"], "INPUT_UNAVAILABLE")
        self.assertEqual(second["raw_header_ticks"], [MAX, 7])
        self.assertEqual(query["raw_header_ticks"], [MAX, 7])
        self.assertNotIn("clock_origin", query)

    def test_phase_names_only_no_numeric_abi(self):
        ledger, original, _ = started()
        for phase in ("STOP", "captured", 2, True):
            with self.subTest(phase=phase), self.assertRaises(hl.Refused):
                ledger.ack(ack(original, phase=phase))
        self.assertEqual(ledger.evaluate_deadline(original, T0 + 1)["terminal"], None)

    def test_old_duplicate_never_revives_after_expiry(self):
        ledger, original, _ = started()
        ledger.ack(ack(original))
        duplicate = ledger.ack(ack(original))
        expired = ledger.evaluate_deadline(original, T0 + 12_000_000_000)
        replay = ledger.ack(ack(original))
        self.assertEqual(duplicate["status"], "DUPLICATE_ACK")
        self.assertEqual(expired["terminal"], "EXPIRED")
        self.assertEqual(replay["status"], "INPUT_UNAVAILABLE")
        self.assertEqual(replay["terminal"], "EXPIRED")

    def test_supersession_and_disable_never_authorize(self):
        ledger, original, _ = started()
        superseded = ledger.terminate(original, at_ns=T0 + 1_000_000_000,
                                      reason="SUPERSEDED")
        self.assertEqual(superseded["terminal"], "SUPERSEDED")
        disabled, disabled_original, _ = started(seq=2)
        disabled.disable()
        self.assertEqual(disabled.evaluate_deadline(disabled_original, T0 + 1)
                         ["reason"], "LEDGER_DISABLED")
        self.assertFalse(disabled.evaluate_deadline(disabled_original, T0 + 2)
                         ["action_authorized"])


if __name__ == "__main__":
    unittest.main()
