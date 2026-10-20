"""Portable terminal-protocol failure injection; no simulator is invoked."""
from pathlib import Path
import importlib.util
import itertools
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / "tools/control3d/run_pwm_applied_capture.py"
spec = importlib.util.spec_from_file_location("applied_capture_runner", SOURCE)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

STATS = ("TB_STATS groups=1 cases=1 samples=29 assertions=206 records=2 "
         "raw_faults=0 failure_events=0 window_starts=3 handshakes=1 mismatches=0")
PASS = "TB_PASS group=0 loopback=0"
MISMATCH = "MISMATCH sample=10 label=wrong_boundary expected=0 actual=1"
FAIL = "TB_FAIL group=21 mismatches=1"
FATAL = "** Fatal: TB_FAIL public-port self-check"
CODE7 = "CODE7_OBSERVED code=7 window_active=0 out_valid=0"
NORMAL = {"id": "fixture", "group": 0, "loopback": 0,
          "count_w": 4, "witness_w": 8, "tag_w": 8}
NEGATIVE = {"group": 21, "expect": "fail", "required_any": ["wrong_boundary"]}


class TerminalProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def result(self, lines, *, prefix="# ", newline="\n", stderr="", code=0):
        stdout = (newline.join(prefix + line for line in lines) + newline).encode()
        (self.root / "out").write_bytes(stdout)
        (self.root / "err").write_text(stderr, encoding="utf-8")
        parsed = runner.parse_tb_output(self.root / "out", self.root / "err")
        parsed.update(transcript=None, transcript_sha256=None, wlf=None, wlf_sha256=None)
        return {"parsed": parsed, "record": {"exit": code,
                "stdout": str(self.root / "out"), "stderr": str(self.root / "err")}}

    def accepted(self, lines, **kw):
        return runner.positive_entry(NORMAL, self.result(lines, **kw))["passed"]

    @staticmethod
    def negative_lines():
        return [MISMATCH, STATS.replace("mismatches=0", "mismatches=1"), FAIL, FATAL]

    def test_current_positive_formats(self):
        for prefix, newline in itertools.product(("", "# "), ("\n", "\r\n")):
            with self.subTest(prefix=prefix, newline=newline):
                self.assertTrue(self.accepted([STATS, PASS, "** Note: $finish"], prefix=prefix, newline=newline))

    def test_exact_positive_process_status(self):
        for code in (0, 1, 2, -1, True, False, 0.0, None, "0", "timeout", "exception"):
            with self.subTest(code=repr(code)):
                self.assertEqual(self.accepted([STATS, PASS], code=code), type(code) is int and code == 0)

    def test_old_synthetic_bare_pass_is_not_current_tb_protocol(self):
        self.assertFalse(self.accepted(["TB_PASS", STATS], prefix=""))

    def test_substring_marker_is_not_pass(self):
        for marker in ("NOT_TB_PASS_MARKER", "X" + PASS, PASS + "X", "banner " + PASS,
                       PASS + " trailing", "# " + PASS, "\t" + PASS, " " + PASS):
            with self.subTest(marker=marker):
                self.assertFalse(self.accepted([STATS, marker]))

    def test_stats_cannot_hide_behind_prefix_or_suffix(self):
        for row in ("X" + STATS, STATS + "X", "\t" + STATS, STATS + " extra=0"):
            with self.subTest(row=row):
                self.assertFalse(self.accepted([row, PASS]))

    def test_both_original_a_negative_shapes(self):
        self.assertFalse(self.accepted(["NOT_TB_PASS_MARKER", STATS], prefix=""))
        self.assertFalse(self.accepted(["TB_PASS", STATS, STATS.replace("mismatches=0", "mismatches=1")], prefix=""))

    def test_duplicate_stats_even_if_identical(self):
        for fields in (STATS, STATS.replace("mismatches=0", "mismatches=1")):
            for rows in ([STATS, fields, PASS], [STATS, PASS, fields], [fields, STATS, PASS]):
                with self.subTest(rows=rows):
                    self.assertFalse(self.accepted(rows))

    def test_conflict_in_every_statistic_is_rejected(self):
        for token in STATS.split()[1:]:
            key, number = token.split("=")
            other = STATS.replace(token, key + "=" + str(int(number) + 1))
            with self.subTest(key=key):
                self.assertFalse(self.accepted([STATS, PASS, other]))

    def test_incomplete_duplicate_or_reordered_fields(self):
        fields = STATS.split()
        for i in range(1, len(fields)):
            variants = [fields[:i] + fields[i + 1:], fields + [fields[i]],
                        fields[:i] + [fields[i].replace("=", " =")] + fields[i + 1:]]
            for tokens in variants:
                with self.subTest(field=i, tokens=tokens):
                    self.assertFalse(self.accepted([" ".join(tokens), PASS]))
        self.assertFalse(self.accepted([" ".join([fields[0]] + list(reversed(fields[1:]))), PASS]))

    def test_numeric_grammar_is_ascii_bounded_unsigned(self):
        for value in ("-1", "+0", "0.0", "NaN", "٠", "０", "", "9" * 5000):
            with self.subTest(value=value[:20]):
                self.assertFalse(self.accepted([STATS.replace("cases=1", "cases=" + value), PASS]))
                self.assertFalse(self.accepted([STATS, PASS.replace("group=0", "group=" + value)]))

    def test_outcome_unique_and_ordered(self):
        for rows in ([PASS, STATS], [STATS], [PASS], [STATS, PASS, PASS],
                     [STATS, PASS, FAIL], [FAIL, STATS, PASS], [STATS, PASS, "TB_FAIL"]):
            with self.subTest(rows=rows):
                self.assertFalse(self.accepted(rows))

    def test_group_and_loopback_are_bound_to_requested_run(self):
        for terminal in ("TB_PASS group=1 loopback=0", "TB_PASS group=0 loopback=1",
                         "TB_PASS group=0 loopback=2", "TB_PASS group=0"):
            self.assertFalse(self.accepted([STATS, terminal]))
        result = self.result([STATS, "TB_PASS group=8 loopback=1"])
        self.assertTrue(runner.positive_result({**NORMAL, "group": 8, "loopback": 1}, result))

    def test_trailing_error_fatal_or_contradiction(self):
        for bad in ("** Error: later failure", "** Fatal: later failure", FATAL,
                    "TB_FAIL group=0 mismatches=1", "NOT_TB_PASS_MARKER"):
            for index in (0, 1, 2):
                rows = [STATS, PASS]
                rows.insert(index, bad)
                with self.subTest(bad=bad, index=index):
                    self.assertFalse(self.accepted(rows))
            self.assertFalse(self.accepted([STATS, PASS], stderr=bad))

    def test_stderr_cannot_supply_or_duplicate_terminal_records(self):
        for error in (STATS, PASS, FAIL, MISMATCH, CODE7):
            self.assertFalse(self.accepted([STATS, PASS], stderr=error))
        self.assertFalse(self.accepted([], stderr=STATS + "\n" + PASS))

    def test_nonzero_mismatch_cannot_pass(self):
        self.assertFalse(self.accepted([STATS.replace("mismatches=0", "mismatches=1"), PASS]))
        self.assertFalse(self.accepted([MISMATCH, STATS, PASS]))
        self.assertFalse(self.accepted([MISMATCH, STATS.replace("mismatches=0", "mismatches=1"), PASS]))

    def test_invalid_utf8_is_rejected(self):
        result = self.result([STATS, PASS])
        with (self.root / "out").open("ab") as f:
            f.write(b"\xff\n")
        parsed = runner.parse_tb_output(self.root / "out", self.root / "err")
        self.assertFalse(parsed["protocol_valid"])
        self.assertFalse(parsed["passed"])

    def test_only_lf_or_crlf_separates_protocol_records(self):
        for separator in ("\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029"):
            with self.subTest(separator=repr(separator)):
                self.assertFalse(self.accepted([STATS, PASS], newline=separator))
                self.assertFalse(self.accepted(["banner" + separator + STATS, PASS]))

    def test_valid_failure_requires_completed_expected_exit(self):
        for code in (0, 1, 2, -1, True, False, 0.0, None, "timeout", "exception"):
            with self.subTest(code=repr(code)):
                result = self.result(self.negative_lines(), code=code)
                self.assertEqual(runner.mutant_result(NEGATIVE, result), type(code) is int and code in (0, 1))
                self.assertFalse(runner.positive_result(NORMAL, result))

    def test_failure_count_and_label_must_match(self):
        rows = self.negative_lines()
        variants = [
            rows[1:], rows + [MISMATCH], [MISMATCH, *rows],
            [MISMATCH.replace("sample=10", "sample=30"), *rows[1:]],
            [MISMATCH.replace("wrong_boundary", "different_boundary"), *rows[1:]],
            [MISMATCH, rows[1], FAIL.replace("mismatches=1", "mismatches=0"), FATAL],
            [MISMATCH, rows[1], FAIL.replace("mismatches=1", "mismatches=2"), FATAL],
            [MISMATCH, rows[1], FAIL.replace("group=21", "group=22"), FATAL],
            [MISMATCH, rows[1].replace("mismatches=1", "mismatches=2"), FAIL, FATAL],
        ]
        for lines in variants:
            with self.subTest(lines=lines):
                self.assertFalse(runner.mutant_result(NEGATIVE, self.result(lines)))

    def test_mutant_cannot_pass_on_malformed_or_unrelated_failure(self):
        rows = self.negative_lines()
        for extra in (STATS, PASS, FAIL, "** Error: compilation failed", "** Fatal: unrelated", FATAL):
            self.assertFalse(runner.mutant_result(NEGATIVE, self.result(rows + [extra])))
        for i in range(len(rows)):
            changed = rows.copy()
            changed[i] = "NOT_" + changed[i]
            self.assertFalse(runner.mutant_result(NEGATIVE, self.result(changed)))
        self.assertFalse(runner.mutant_result(NEGATIVE, self.result(rows[:-1])))

    def test_failure_record_order(self):
        rows = self.negative_lines()
        for order in itertools.permutations(range(4)):
            with self.subTest(order=order):
                observed = runner.mutant_result(NEGATIVE, self.result([rows[i] for i in order]))
                self.assertEqual(observed, order == (0, 1, 2, 3))

    def test_code7_requires_exact_observation_and_own_group(self):
        probe = {"expect": "pass_code7", "group": 30, "required_any": ["CODE7_OBSERVED"]}
        terminal = "TB_PASS group=30 loopback=0"
        self.assertTrue(runner.mutant_result(probe, self.result([CODE7, STATS, terminal])))
        for rows in ([STATS, terminal], ["NOT_" + CODE7, STATS, terminal],
                     [CODE7 + " extra", STATS, terminal], [CODE7, CODE7, STATS, terminal],
                     [STATS, CODE7, terminal], [CODE7, STATS, PASS],
                     [CODE7.replace("code=7", "code=6"), STATS, terminal]):
            self.assertFalse(runner.mutant_result(probe, self.result(rows)))

    def test_original_invalid_width_guard_exit_and_fatal_requirements(self):
        diagnostic = ("DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM COUNT_W=0 WITNESS_W=64 TAG_W=32 "
                      "SAFE_COUNT_W=2 SAFE_WITNESS_W=64 SAFE_TAG_W=32\n")
        for code, fatal in itertools.product((0, 1, 2, "timeout", "exception"), (False, True)):
            with self.subTest(code=code, fatal=fatal):
                (self.root / "guard.stdout.txt").write_text(
                    diagnostic + ("** Fatal: DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM unsupported widths\n" if fatal else ""))
                (self.root / "guard.stderr.txt").write_text("")
                with patch.object(runner, "run_command", return_value={"exit": code}):
                    actual = runner.run_invalid(self.root, self.root, [], {"vsim": "NEVER_EXECUTE"},
                                                {"id": "guard", "count_w": 0, "witness_w": 64, "tag_w": 32}, 1)
                self.assertEqual(actual["passed"], type(code) is int and code in (0, 1) and fatal)


if __name__ == "__main__":
    unittest.main(verbosity=2)
