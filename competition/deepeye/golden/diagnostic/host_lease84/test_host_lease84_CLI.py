"""Focused controls for the strict JSON source84 CLI."""

import hashlib
import json
import sys
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[3] / "tools" / "diagnostic" / "host_lease84"
sys.path.insert(0, str(SOURCE))
import host_lease84_cli as cli

T0, MAX = 1_000_000_000, (1 << 63) - 1
PAYLOAD = "a" * 64


def request(seq=1):
    return {
        "session": "session-b", "request_type": 0x0E, "seq": seq, "cmd_id": seq,
        "payload_sha256": PAYLOAD, "transaction_tag": f"tag-{seq}", "boot_id": "boot-1",
        "epoch": 7, "first_send_ns": T0, "original_ttl_ms": 12000, "profile": "STRESS_300",
        "context": {"text": "完整原始文本", "qpc": MAX - 9, "seq": seq},
    }


def ack(req, **changes):
    value = dict(req)
    value.update({"receipt_ns": T0 + 2_000_000_000, "phase": "CAPTURED",
                  "capture_complete": True, "fault": 0, "remaining_ttl_ms": 8000,
                  "usb_processing_bound_ns": 1_000_000,
                  "clock_error_bound_ns": 1_000_000, "raw_header_tick": 17})
    value.update(changes)
    return value


def payload(operations, mode="SYNTHETIC_FIXTURE"):
    value = {"schema": cli.INPUT_SCHEMA, "operations": operations}
    if mode is not None: value["mode"] = mode
    return value


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def run(value):
    output, code = cli.execute(encoded(value), "<memory>")
    return json.loads(output), code, output


class StrictCliControls(unittest.TestCase):
    def test_explicit_synthetic_positive_and_cost_receipts(self):
        original = request()
        value = payload([
            {"op": "register", "request": original},
            {"op": "ack", "ack": ack(original)},
            {"op": "evaluate_deadline", "request": original,
             "now_ns": T0 + 2_000_000_000},
        ])
        result, code, raw = run(value)
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "POSITIVE")
        self.assertEqual(result["operations"][-1]["result"]["status"], "LEASE")
        self.assertEqual(result["operations"][-1]["result"]["original_context"]
                         ["text"], "完整原始文本")
        self.assertEqual(result["input"]["raw_bytes"], len(encoded(value)))
        self.assertEqual(result["input"]["raw_sha256"],
                         hashlib.sha256(encoded(value)).hexdigest())
        self.assertLessEqual(len(raw), cli.MAX_OUTPUT_BYTES)

    def test_production_default_is_unavailable(self):
        original = request()
        value = payload([{"op": "register", "request": original},
                         {"op": "evaluate_deadline", "request": original,
                          "now_ns": T0 + 2_000_000_000}], mode=None)
        result, code, _ = run(value)
        self.assertEqual(code, 3)
        self.assertEqual(result["mode"], "PRODUCTION")
        self.assertTrue(all(item["result"]["status"] == "INPUT_UNAVAILABLE"
                            for item in result["operations"]))
        self.assertFalse(result["authority"]["send"])
        self.assertFalse(result["authority"]["hardware"])

    def test_missing_ack_field_is_refused_exit_two(self):
        original = request()
        broken = ack(original)
        del broken["fault"]
        result, code, _ = run(payload([
            {"op": "register", "request": original},
            {"op": "ack", "ack": broken},
        ]))
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["operations"][-1]["result"]["code"], "ACK_MISSING")

    def test_duplicate_json_key_is_refused(self):
        raw = (b'{"schema":"' + cli.INPUT_SCHEMA.encode() + b'",'
               b'"schema":"' + cli.INPUT_SCHEMA.encode() + b'","operations":[]}')
        output, code = cli.execute(raw, "<duplicate>")
        result = json.loads(output)
        self.assertEqual(code, 2)
        self.assertEqual(result["code"], "DUPLICATE_JSON_KEY")

    def test_float_and_nonfinite_json_are_refused(self):
        prefix = ('{"schema":"' + cli.INPUT_SCHEMA + '","mode":"SYNTHETIC_FIXTURE",'
                  '"operations":[{"op":"evaluate_deadline","now_ns":')
        for literal, code_name in (("1.5", "FLOAT_FORBIDDEN"),
                                   ("NaN", "NONFINITE_FORBIDDEN"),
                                   ("Infinity", "NONFINITE_FORBIDDEN")):
            raw = (prefix + literal + ',"request":{}}]}').encode()
            output, code = cli.execute(raw, "<number>")
            result = json.loads(output)
            self.assertEqual(code, 2)
            self.assertEqual(result["code"], code_name)

    def test_escaped_surrogate_is_refused_without_traceback(self):
        raw = (b'{"schema":"' + cli.INPUT_SCHEMA.encode() +
               b'","mode":"SYNTHETIC_FIXTURE","operations":[{"op":"' +
               bytes([92]) + b'ud800"}]}')
        output, code = cli.execute(raw, "<surrogate>")
        result = json.loads(output)
        self.assertEqual(code, 2)
        self.assertEqual(result["code"], "UNICODE_ENCODING")

    def test_bool_as_integer_is_refused(self):
        bad = request(seq=True)
        result, code, _ = run(payload([{"op": "register", "request": bad}]))
        self.assertEqual(code, 2)
        self.assertEqual(result["operations"][0]["result"]["code"], "SEQ_TYPE")

    def test_unknown_schema_mode_field_and_capacity_are_refused(self):
        original = request()
        cases = [
            ({**payload([{"op": "register", "request": original}]),
              "schema": "other"}, "INPUT_SCHEMA_UNSUPPORTED"),
            (payload([{"op": "register", "request": original}], mode="OTHER"),
             "MODE_UNSUPPORTED"),
            ({**payload([{"op": "register", "request": original}]), "extra": 1},
             "INPUT_UNKNOWN_FIELD"),
            (payload([{"op": "disable"}] * 17), "OPERATIONS_COUNT"),
        ]
        for value, code_name in cases:
            with self.subTest(code=code_name):
                result, code, _ = run(value)
                self.assertEqual(code, 2)
                self.assertEqual(result["code"], code_name)

    def test_input_and_operation_bounds(self):
        result, code = cli.execute(b" " * (cli.MAX_INPUT_BYTES + 1), "<large>")
        decoded = json.loads(result)
        self.assertEqual(code, 2)
        self.assertEqual(decoded["code"], "INPUT_TOO_LARGE")
        original = request()
        output, code = cli.execute(encoded(payload([
            {"op": "register", "request": original},
            {"op": "ack", "ack": ack(original)},
        ])), "<ack-only>")
        self.assertEqual(code, 3)
        self.assertLessEqual(len(output), cli.MAX_OUTPUT_BYTES)

    def test_disable_then_query_never_authorizes(self):
        original = request()
        result, code, _ = run(payload([
            {"op": "register", "request": original},
            {"op": "ack", "ack": ack(original)},
            {"op": "disable"},
            {"op": "evaluate_deadline", "request": original,
             "now_ns": T0 + 2_000_000_000},
        ]))
        self.assertEqual(code, 3)
        self.assertEqual(result["operations"][-1]["result"]["reason"], "LEDGER_DISABLED")
        self.assertFalse(result["operations"][-1]["result"]["action_authorized"])

    def test_terminate_new_boot_is_supported_and_unavailable(self):
        original = request()
        result, code, _ = run(payload([
            {"op": "register", "request": original},
            {"op": "terminate", "request": original, "at_ns": T0 + 1_000_000_000,
             "reason": "NEW_BOOT", "newer_boot_id": "boot-2"},
        ]))
        self.assertEqual(code, 3)
        self.assertEqual(result["operations"][-1]["result"]["terminal"], "NEW_BOOT")

    def test_deterministic_output_and_canonical_receipts(self):
        original = request()
        value = payload([
            {"op": "register", "request": original},
            {"op": "ack", "ack": ack(original)},
            {"op": "evaluate_deadline", "request": original,
             "now_ns": T0 + 2_000_000_000},
        ])
        first, code_one, raw_one = run(value)
        second, code_two, raw_two = run(value)
        self.assertEqual((code_one, code_two), (0, 0))
        self.assertEqual(raw_one, raw_two)
        canonical = lambda item: json.dumps(
            item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        core = {key: value for key, value in first.items() if key != "payload_canonical"}
        digest = canonical(core)
        self.assertEqual(first["payload_canonical"],
                         {"bytes": len(digest),
                          "sha256": hashlib.sha256(digest).hexdigest()})
        for item in first["operations"]:
            result_bytes = canonical(item["result"])
            self.assertEqual(item["result_canonical_bytes"], len(result_bytes))
            self.assertEqual(item["result_canonical_sha256"],
                             hashlib.sha256(result_bytes).hexdigest())


if __name__ == "__main__":
    unittest.main()
