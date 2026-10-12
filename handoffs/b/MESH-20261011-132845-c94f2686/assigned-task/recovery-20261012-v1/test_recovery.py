"""Reuse the preserved 28 tests against the minimally corrected validator."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent
import canonical_json as corrected

spec = importlib.util.spec_from_file_location(
    "preserved_tests", ORIGINAL / "test_canonical_json.py")
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
legacy.cj = corrected
FixtureFilesTest = legacy.FixtureFilesTest
ValidateBytesTest = legacy.ValidateBytesTest


class CliTest(legacy.CliTest):
    def run_cli(self, *args):
        env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run(
            [sys.executable, "-B", str(HERE / "canonical_json.py"), *args],
            cwd=ORIGINAL, env=env, capture_output=True, timeout=30)


class RecoveryRegressionTest(unittest.TestCase):
    def test_exponent_overflow_is_rejected(self):
        for data in (b"1e999\n", b"-1e999\n", b'{"a":[1e999]}\n'):
            with self.subTest(data=data):
                self.assertEqual(corrected.validate_bytes(data)[0], "E_NONFINITE")

    def test_deep_json_is_rejected_without_traceback(self):
        data = b"[" * 2000 + b"0" + b"]" * 2000 + b"\n"
        self.assertEqual(corrected.validate_bytes(data)[0], "E_JSON")

    def test_cli_continues_after_overflow(self):
        result = subprocess.run(
            [sys.executable, "-B", "canonical_json.py", "overflow.json",
             "../fixtures/ok_basic.json"], cwd=HERE,
            env=dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1"),
            capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.stdout,
                         b"FAIL overflow.json E_NONFINITE non-finite number 1e999\n"
                         b"PASS ../fixtures/ok_basic.json\n")


if __name__ == "__main__":
    unittest.main()
