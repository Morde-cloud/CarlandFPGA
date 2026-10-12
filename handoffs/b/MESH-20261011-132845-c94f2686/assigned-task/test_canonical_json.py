#!/usr/bin/env python3
"""Tests for the canonical-JSON fixture validator.

Every expected byte sequence in this file is written out explicitly (or is
built only with str.encode("utf-8")) so the expectations never come from the
code under test.
"""

import os
import pathlib
import subprocess
import sys
import unittest

import canonical_json as cj

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

OK_UNICODE_KEYS = (
    b'{"z":0,"\xc3\xa9":1,"\xe4\xb8\xad":2,"\xef\xbf\xbd":3,'
    b'"\xf0\x90\x80\x80":4,"\xf0\x9f\x98\x80":5}\n'
)
BAD_KEY_ORDER_UTF16 = (
    b'{"z":0,"\xc3\xa9":1,"\xe4\xb8\xad":2,"\xf0\x90\x80\x80":4,'
    b'"\xef\xbf\xbd":3,"\xf0\x9f\x98\x80":5}\n'
)
OK_NO_NORMALIZATION = b'{"a":"e\xcc\x81","b":"\xc3\xa9"}\n'
OK_ESCAPED_NEWLINE = b'{"a":"x\\ny"}\n'
BAD_RAW_NEWLINE = b'{"a":"x\ny"}\n'

FIXTURE_CASES = {
    "ok_basic.json": (b'{"a":1,"b":[true,null]}\n', None),
    "ok_empty_object.json": (b"{}\n", None),
    "ok_top_level_array.json": (b"[1,2,3]\n", None),
    "ok_nested.json": (b'{"a":{},"z":{"b":[1,2,{"c":"d"}]}}\n', None),
    "ok_unicode_keys.json": (OK_UNICODE_KEYS, None),
    "ok_escaped_newline.json": (OK_ESCAPED_NEWLINE, None),
    "ok_numbers.json": (
        b'{"big":123456789012345678901234567890,"f":1.5,"i":-7}\n',
        None,
    ),
    "ok_no_normalization.json": (OK_NO_NORMALIZATION, None),
    "bad_bom.json": (b'\xef\xbb\xbf{"a":1}\n', "E_BOM"),
    "bad_invalid_utf8.json": (b'{"a":"\xff"}\n', "E_UTF8"),
    "bad_duplicate_key.json": (b'{"a":1,"a":2}\n', "E_DUPKEY"),
    "bad_duplicate_key_nested.json": (b'{"o":{"k":1,"k":2}}\n', "E_DUPKEY"),
    "bad_nan.json": (b'{"a":NaN}\n', "E_NONFINITE"),
    "bad_negative_infinity.json": (b"[-Infinity]\n", "E_NONFINITE"),
    "bad_surrogate_value.json": (b'{"a":"\\ud800"}\n', "E_SURROGATE"),
    "bad_surrogate_key.json": (b'{"\\udfff":1}\n', "E_SURROGATE"),
    "bad_not_json.json": (b'{"a":1\n', "E_JSON"),
    "bad_raw_newline_in_string.json": (BAD_RAW_NEWLINE, "E_JSON"),
    "bad_whitespace_space.json": (b'{"a": 1}\n', "E_CANONICAL"),
    "bad_whitespace_pretty.json": (b'{\n  "a": 1\n}\n', "E_CANONICAL"),
    "bad_missing_terminal_lf.json": (b'{"a":1}', "E_NEWLINE"),
    "bad_doubled_terminal_lf.json": (b'{"a":1}\n\n', "E_NEWLINE"),
    "bad_crlf_terminal.json": (b'{"a":1}\r\n', "E_NEWLINE"),
    "bad_key_order_utf16.json": (BAD_KEY_ORDER_UTF16, "E_CANONICAL"),
    "bad_escaped_unicode.json": (b'{"a":"\\u0041"}\n', "E_CANONICAL"),
}


class FixtureFilesTest(unittest.TestCase):
    def test_on_disk_fixture_bytes_match_explicit_literals(self):
        for name in FIXTURE_CASES:
            with self.subTest(fixture=name):
                self.assertEqual((FIXTURES / name).read_bytes(), FIXTURE_CASES[name][0])

    def test_fixture_validation_results(self):
        for name in FIXTURE_CASES:
            with self.subTest(fixture=name):
                failure = cj.validate_path(str(FIXTURES / name))
                expected_code = FIXTURE_CASES[name][1]
                if expected_code is None:
                    self.assertIsNone(failure)
                else:
                    self.assertIsNotNone(failure)
                    self.assertEqual(failure[0], expected_code)


class ValidateBytesTest(unittest.TestCase):
    def test_valid_basic_bytes(self):
        self.assertIsNone(cj.validate_bytes(b'{"a":1,"b":[true,null]}\n'))

    def test_canonical_bytes_sort_keys(self):
        self.assertEqual(cj.canonical_bytes({"b": 1, "a": 2}), b'{"a":2,"b":1}\n')

    def test_unicode_key_order_is_code_point_order(self):
        value = {
            "\U00010000": 4,
            "\ufffd": 3,
            "z": 0,
            "\u4e2d": 2,
            "\u00e9": 1,
            "\U0001f600": 5,
        }
        self.assertEqual(cj.canonical_bytes(value), OK_UNICODE_KEYS)

    def test_utf16_key_order_is_rejected(self):
        self.assertEqual(cj.validate_bytes(BAD_KEY_ORDER_UTF16)[0], "E_CANONICAL")
        self.assertIsNone(cj.validate_bytes(OK_UNICODE_KEYS))

    def test_nested_objects_sorted_at_every_depth(self):
        self.assertEqual(
            cj.canonical_bytes({"z": {"b": [1, 2, {"y": 1, "x": 2}]}, "a": {}}),
            b'{"a":{},"z":{"b":[1,2,{"x":2,"y":1}]}}\n',
        )

    def test_no_unicode_normalization(self):
        self.assertEqual(
            cj.canonical_bytes({"a": "e\u0301", "b": "\u00e9"}),
            OK_NO_NORMALIZATION,
        )
        self.assertIsNone(cj.validate_bytes(OK_NO_NORMALIZATION))

    def test_escaped_newline_stays_escaped(self):
        self.assertEqual(cj.canonical_body_bytes({"a": "x\ny"}), b'{"a":"x\\ny"}')
        self.assertIsNone(cj.validate_bytes(OK_ESCAPED_NEWLINE))
        self.assertEqual(cj.validate_bytes(BAD_RAW_NEWLINE)[0], "E_JSON")

    def test_terminal_newline_variants(self):
        body = b'{"a":1}'
        self.assertIsNone(cj.validate_bytes(body + b"\n"))
        self.assertEqual(
            cj.validate_bytes(body), ("E_NEWLINE", "missing terminal lf")
        )
        self.assertEqual(
            cj.validate_bytes(body + b"\n\n"),
            ("E_NEWLINE", "doubled terminal lf"),
        )
        self.assertEqual(
            cj.validate_bytes(body + b"\r\n"),
            ("E_NEWLINE", "crlf terminal line ending"),
        )

    def test_whitespace_rejected(self):
        code, detail = cj.validate_bytes(b'{"a": 1}\n')
        self.assertEqual(code, "E_CANONICAL")
        self.assertTrue(
            detail.startswith("not canonical: first difference at byte offset 5 ("),
            detail,
        )

    def test_number_rendering_is_python_repr(self):
        self.assertIsNone(cj.validate_bytes(b"1.5\n"))
        self.assertEqual(cj.validate_bytes(b"1e2\n")[0], "E_CANONICAL")
        self.assertIsNone(
            cj.validate_bytes(
                b'{"big":123456789012345678901234567890,"f":1.5,"i":-7}\n'
            )
        )

    def test_top_level_scalars(self):
        self.assertIsNone(cj.validate_bytes(b"1\n"))
        self.assertIsNone(cj.validate_bytes(b"true\n"))
        self.assertIsNone(cj.validate_bytes(b'"x"\n'))

    def test_bom_rejected(self):
        self.assertEqual(
            cj.validate_bytes(b'\xef\xbb\xbf{"a":1}\n'),
            ("E_BOM", "utf-8 byte order mark at offset 0"),
        )

    def test_invalid_utf8_rejected(self):
        code, detail = cj.validate_bytes(b'{"a":"\xff"}\n')
        self.assertEqual(code, "E_UTF8")
        self.assertTrue(detail.startswith("invalid utf-8 byte at offset "), detail)

    def test_duplicate_keys_rejected(self):
        self.assertEqual(
            cj.validate_bytes(b'{"a":1,"a":2}\n'),
            ("E_DUPKEY", "duplicate object key 'a'"),
        )
        self.assertEqual(
            cj.validate_bytes(b'{"o":{"k":1,"k":2}}\n')[0], "E_DUPKEY"
        )

    def test_nonfinite_numbers_rejected(self):
        self.assertEqual(
            cj.validate_bytes(b'{"a":NaN}\n'),
            ("E_NONFINITE", "non-finite number NaN"),
        )
        self.assertEqual(
            cj.validate_bytes(b"[Infinity]\n"),
            ("E_NONFINITE", "non-finite number Infinity"),
        )
        self.assertEqual(
            cj.validate_bytes(b"[-Infinity]\n"),
            ("E_NONFINITE", "non-finite number -Infinity"),
        )

    def test_unpaired_surrogates_rejected(self):
        self.assertEqual(
            cj.validate_bytes(b'{"a":"\\ud800"}\n'),
            ("E_SURROGATE", "unpaired surrogate code point U+D800"),
        )
        self.assertEqual(
            cj.validate_bytes(b'{"\\udfff":1}\n'),
            ("E_SURROGATE", "unpaired surrogate code point U+DFFF"),
        )

    def test_escaped_surrogate_pair_is_reencoded_not_rejected(self):
        code, _detail = cj.validate_bytes(b'{"\\ud83d\\ude00":5}\n')
        self.assertEqual(code, "E_CANONICAL")
        self.assertIsNone(cj.validate_bytes('{"\U0001f600":5}\n'.encode("utf-8")))

    def test_invalid_json_rejected(self):
        code, detail = cj.validate_bytes(b'{"a":1\n')
        self.assertEqual(code, "E_JSON")
        self.assertTrue(detail.startswith("invalid json at line "), detail)
        self.assertEqual(
            detail, "invalid json at line 2 column 1: Expecting ',' delimiter"
        )
        self.assertEqual(cj.validate_bytes(b"")[0], "E_JSON")
        self.assertEqual(cj.validate_bytes(b"\n")[0], "E_JSON")

    def test_escaped_unicode_is_reencoded(self):
        self.assertEqual(cj.validate_bytes(b'{"a":"\\u0041"}\n')[0], "E_CANONICAL")
        self.assertIsNone(cj.validate_bytes(b'{"a":"A"}\n'))

    def test_io_error_code(self):
        failure = cj.validate_path(str(FIXTURES / "does_not_exist.json"))
        self.assertIsNotNone(failure)
        self.assertEqual(failure[0], "E_IO")


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        return subprocess.run(
            [sys.executable, "canonical_json.py", *args],
            cwd=str(HERE),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_accepts_valid_fixtures(self):
        result = self.run_cli("fixtures/ok_basic.json", "fixtures/ok_unicode_keys.json")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            result.stdout,
            b"PASS fixtures/ok_basic.json\nPASS fixtures/ok_unicode_keys.json\n",
        )
        self.assertEqual(result.stderr, b"")

    def test_mixed_valid_and_invalid_exits_one(self):
        result = self.run_cli(
            "fixtures/ok_nested.json",
            "fixtures/bad_crlf_terminal.json",
            "fixtures/bad_duplicate_key.json",
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            result.stdout,
            b"PASS fixtures/ok_nested.json\n"
            b"FAIL fixtures/bad_crlf_terminal.json E_NEWLINE crlf terminal line ending\n"
            b"FAIL fixtures/bad_duplicate_key.json E_DUPKEY duplicate object key 'a'\n",
        )
        self.assertEqual(result.stderr, b"")

    def test_all_invalid_exits_one(self):
        result = self.run_cli("fixtures/bad_bom.json", "fixtures/bad_nan.json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            result.stdout,
            b"FAIL fixtures/bad_bom.json E_BOM utf-8 byte order mark at offset 0\n"
            b"FAIL fixtures/bad_nan.json E_NONFINITE non-finite number NaN\n",
        )
        self.assertEqual(result.stderr, b"")

    def test_no_args_is_usage_error(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"usage: canonical_json.py PATH [PATH ...]\n")

    def test_missing_file_fails_with_io_code(self):
        result = self.run_cli("fixtures/does_not_exist.json")
        self.assertEqual(result.returncode, 1)
        self.assertTrue(
            result.stdout.startswith(
                b"FAIL fixtures/does_not_exist.json E_IO cannot read file: "
            ),
            result.stdout,
        )
        self.assertEqual(result.stderr, b"")

    def test_cli_is_read_only(self):
        path = FIXTURES / "ok_basic.json"
        before = path.read_bytes()
        self.run_cli("fixtures/ok_basic.json")
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
