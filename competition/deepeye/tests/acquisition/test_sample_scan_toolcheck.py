#!/usr/bin/env python3
'''Portable regressions for the op22 tool-version preflight repair.

Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Work: B-SAMPLE-SCAN-TOOLCHECK-REPAIR-20261022-22-v1
Product operation: B-DEEPEYE-SAMPLE-SCAN-TOOLCHECK-20261022-22
Defect: OP21-TOOLCHECK-ERROR01

Run from the worktree root:
  python -B -X utf8 -m unittest competition.deepeye.tests.acquisition.test_sample_scan_toolcheck -v

or directly:
  python -B -X utf8 competition/deepeye/tests/acquisition/test_sample_scan_toolcheck.py -v

No ModelSim process is started. Every vendor invocation is an explicit
synthetic seam. No private controller, service, credential or board access is
used. Temporary directories are created by tempfile and removed by unittest.
'''

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.dont_write_bytecode = True

RUNNER_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "tools"
    / "acquisition"
    / "run_sample_scan_capture.py"
)

VLOG_BANNER = "Model Technology ModelSim SE-64 vlog 10.7 Compiler 2017.12 Dec  7 2017"
VSIM_BANNER = "Model Technology ModelSim SE-64 vsim 10.7 Simulator 2017.12 Dec  7 2017"
VLOG_BANNER_CRLF = (VLOG_BANNER + "\r\n").encode("utf-8")
VSIM_BANNER_CRLF = (VSIM_BANNER + "\r\n").encode("utf-8")

# Source/AST fingerprints of every existing function except _tool_version,
# captured from the op21 baseline 99748d791432cd0090e92b1e383670200fc3ead59ad3a6795af72f876e6d6b66.
PROTECTED_FUNCTIONS = {
    "_case": ("39c781e5155756c1937cae774963e558d7cda1a62e6c8e81be1a71fd23a44526", "7cb9c277801427c6d149113869b524b0cac4561b28ddf3b5eaa86f3f8925b93d"),
    "_count_lines": ("5ce96e38051d48d999c3e105ce8d27fdf128afb6ca4e507f675b9bffcaea5c42", "dd933a7ba9308210bb76a4e49e63716a276895625ee2838d45c3f41728319acb"),
    "_guard": ("7a44cb491760ce88682b29efe6f7034a35260e9c7e7f506d7855a560bf6fe027", "45a23394b8bed98b45f3b234cbc0dc6313b1a8037396ff92a50fd0e01cd634ee"),
    "_identity_reasons": ("6491a513927ab13f7014b94775d4bca1569b5f48115cdb710778e7f398f8f604", "1f2bef5fb3c77189407fa743996c0cecee988d05aa9e2d10c99ba3485a3b8f52"),
    "_lines": ("169e5737445ee9ff8d94120cf80f12d8f820baa91e4d9b0b728d5f45c3c00d64", "c17a8d02f94ebdd35e6bccd6e18c1a516c71b1f4b91842304db94dd601b59b19"),
    "_mismatch_tokens": ("9bcb7be1c9d1f2bd3d732ff2623e133897bc84c5f80e0de6b98de123db161d63", "b76be041fa10ff802f1b01b521f0d3c13ce4b046d6425ef1cb774b2b53d0f8df"),
    "_mutant": ("36b86cf25116bf5a06aef47af7e5db80c0ede4d5d07b2df64c15153d56d8d3d0", "e34a2973f53c1c503dc262cda01f20449a13c4884127fd4c1b6f867fb7f3b51f"),
    "_parse_args": ("831e1b86d7c9d39b7b175bd87b48f0fbd281bce6ea7272c4f1a70e95a28d6e99", "a3fc2fedd1a5a65f35a03c23a71c0cf7ad0e8d15c9235b86dee7853d32a9b14b"),
    "_persist_invocation": ("4e0c9c8f300011111e2fca09f5d874b35dcb2b31a12f66425ff340a146ae877e", "60a0c007b0bce710353e57ffd8170d6b188168fea7466ee44b7185aa6759a3d7"),
    "_result": ("a5cf8cef981bbd531ae6285e77ba24a59828add1811b750f83735ba65320aed9", "a9ef13ff2e7c2d5e5acac3c1e3c91ee142e98283d07a1d7dab91a59a198f7a4b"),
    "_run_hidden": ("45ec15731464b86031c18059219d2bbd02bec613b72470f718c3ff6d01c295e6", "b03460cb150494f9772ec64bc717a55fbfb04a41563a69726ad82e2980648358"),
    "_snapshot_inputs": ("0820462fa4edf497ae94f89ae88c44cbb9b2981b1b2907bfb645ca239a87718f", "134e42f5afddcdc9b5bc4d112aab374c008a7207c41ea46dc6efce729fb21055"),
    "_strict_diagnostics": ("f11579ac8f77e661eb1aca198be427438ca28154186676b7081de7b35d5f21c8", "17fc2a4f9906e9a3de29878088d07c76bdf75c3e8a422cb6383f814d8219b4ac"),
    "_structured_rows": ("1fd745866a64593378faf10aa6012e6753c29db0a5f21c7be728d43c13f66764", "d5ee88a550c8f334451b2d978e8730eac736f1856a1df1a3dc2332e9ccb9045b"),
    "_summary_counts": ("74e808d5a6769ae793afb7aa64877586a466a81e099fb8502200166d62e76ea0", "126706801ede08a6c235678c8ca22b28e6b74fd2f89606817e1c1e947a610fe1"),
    "_write_json": ("78cf2f5c6b8a940213e280355a22d3d0d7741b4ce6f7db018eea4dd1b83cc363", "b82e36691cc090841270b859fc24e2de760afc930a59a0b24fab86c224957fcf"),
    "_zero_summary": ("32a75db0944a92c4606b144a5df6873dc93d1adff87efd7d188ec46baf56e236", "59037460dbd2981a2b1a80e2c87e945285e81a029ec45a94d8abdd9248b8d509"),
    "aggregate_results": ("729a13c3ecc3bc23caad2918b0c0a87cc21edcce1f2a5a5fa42f4d8d3bdedf99", "d79556486dd1dbae00d674cb17a4e1e4b2fc699d70c3b91936a427a9961d9da8"),
    "classify_compile": ("9a939f2a13aeb2904ac404509d1cdc50214763c3e6ba21c9320c0ac1bcadcf11", "da5e8c706106e5dde9e536a34c6010045f965b5771f7d53d6a377e0de56914bb"),
    "classify_guard_output": ("3bbaad17a7e8ed3d92be9745b325681c74f84c9944f72a08e318c088231364d5", "678741915b8d0986cb22c97c13243127a7e5681f6eb5674edfcf57bf7c6a8b8a"),
    "classify_mutant_output": ("984289a048e2621231174272c51222ca8625c33392edd7bb43dc5b8c71331cda", "b7dac611d507c6ce60c1407f309d5d6471db415c435135af47c583ab5463dd72"),
    "classify_simulation_output": ("257a903c80abc866f736d034507de3203a8cc2e31a025574789e0702a486e578", "32323b65d0fb59fe4a23828a41f2b40b1f110603832d022c3a9ad02e4fc74c9b"),
    "main": ("af6141032c964760ed84d7a856afd37150a606d0f42cb814f75037f0b8dfcc56", "1eb666b09cfe812cbbfb29dbc7ec6bf2288763dcbda78a39d57f297f8781f31d"),
    "parse_stats": ("5a2f9cd4fdf14694e050d2dfbc1429de34a2e52f7a4e8101fb6c496e68daf603", "dcb3f8a646dedf6102a001a651e36d6ea783f947dbe43744a08407a529ec1837"),
    "run_case": ("de5dc11b7a813663054eb3ba61126ef44b111c2cbc5372f918b4a1f3dc0f4656", "74f1289ddbc61c9b5c52b0de10d6b4420dd1342ce1409a060d89f16af505d3fb"),
    "select_cases": ("605f51247ac5add440bffcf8a94d3a905d8e7ec8097c902b72958b5fad28c63b", "324d42ccf1fb9303e630b240dc8656c5193e930fb46d2ed2e5d34b0ebdb7b00e"),
    "sha256_file": ("13a058cb0c10286ac96cdaf4688b700c6dc30aff241dfc4fa03d4c781d6884f7", "cd39635ab16795a358fd995ac15dca3bba3e0f7a776d3e028a7df5af9b5819da"),
}

ORIGINAL_TOOL_VERSION_SOURCE_SHA256 = (
    "e82afb248c648a4d8ca6f402a84dade1f1a57bac9ca84aa16dc37b0b9b7a0d1a"
)
TOP_LEVEL_SHA256 = (
    "b8d19283cb2a020a19b3dc8d3e9812c590469875135050d07ffd7be6b568f60c"
)
EXPECTED_FUNCTION_SET = set(PROTECTED_FUNCTIONS) | {
    "_tool_version",
    "_version_failure_reasons",
    "_version_output_bytes",
}


def _load_runner():
    spec = importlib.util.spec_from_file_location("sample_scan_runner_op22_test", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load_runner()


def _validate(tool, stdout="", stderr="", exit_code=0, timed_out=False, exception=None):
    invocation = {
        "stdout_text": stdout,
        "stderr_text": stderr,
        "exit": exit_code,
        "timed_out": timed_out,
    }
    if exception is not None:
        invocation["exception_type"] = exception
        invocation["exception_message"] = "synthetic exception"
    return RUNNER._version_failure_reasons(tool, invocation)


def _invocation(tool, stdout=b"", stderr=b"", exit_code=0, timed_out=False, **extra):
    payload = {
        "argv": [f"{tool}.exe", "-version"],
        "cwd": ".",
        "exit": exit_code,
        "timed_out": timed_out,
        "elapsed_seconds": 0.01,
        "stdout_bytes": stdout,
        "stderr_bytes": stderr,
    }
    payload.update(extra)
    return payload


def _healthy_hidden(calls, stdout_map=None, stderr_map=None):
    stdout_map = stdout_map or {}
    stderr_map = stderr_map or {}
    def hidden(argv, cwd, timeout):
        tool = pathlib.Path(argv[0]).stem
        calls.append(tool)
        banner = VLOG_BANNER_CRLF if tool == "vlog" else VSIM_BANNER_CRLF
        return _invocation(
            tool,
            stdout_map.get(tool, banner),
            stderr_map.get(tool, b""),
            argv=argv,
            cwd=str(cwd),
        )
    return hidden


class VersionValidatorTests(unittest.TestCase):
    def assert_accepted(self, tool, stdout="", stderr=""):
        reasons = _validate(tool, stdout, stderr)
        self.assertEqual([], reasons)

    def assert_rejected(self, tool, stdout="", stderr="", *,
                        exit_code=0, timed_out=False, exception=None, contains=None):
        reasons = _validate(tool, stdout, stderr, exit_code, timed_out, exception)
        self.assertTrue(reasons, "expected rejection")
        if contains is not None:
            self.assertTrue(any(contains in reason for reason in reasons), reasons)

    def test_healthy_banner_variants(self):
        for tool, banner in (("vlog", VLOG_BANNER), ("vsim", VSIM_BANNER)):
            variants = {
                "crlf": (banner + "\r\n", ""),
                "lf": (banner + "\n", ""),
                "no_newline": (banner, ""),
                "prefix_spaces": (" \t# " + banner + " \t\n", ""),
                "banner_on_stderr": ("", banner + "\r\n"),
                "zero_tally_stdout": (banner + "\r\nErrors: 0, Warnings: 0\r\n", ""),
                "zero_tally_stderr": (banner + "\r\n", "Errors: 0, Warnings: 0\n"),
                "blank_lines": ("\n\n" + banner + "\n\n", "\n"),
                "one_space_date": (banner.replace("Dec  7", "Dec 7") + "\n", ""),
                "tab_date": (banner.replace("Dec  7", "Dec\t7") + "\n", ""),
            }
            for name, (stdout, stderr) in variants.items():
                with self.subTest(tool=tool, variant=name):
                    self.assert_accepted(tool, stdout, stderr)
    def test_explicit_diagnostics_rejected_on_each_stream(self):
        diagnostics = [
            "** Error: license failed",
            "Error: failed",
            "eRrOr: failed",
            "** Warning: incompatible",
            "warning: retry",
            "FaTaL: stopped",
            "# ** Error: bad",
            "** Fatal: hidden\x00tail",
        ]
        for tool, banner in (("vlog", VLOG_BANNER), ("vsim", VSIM_BANNER)):
            for diagnostic in diagnostics:
                for stream in ("stdout", "stderr"):
                    stdout = banner + "\n" + (diagnostic + "\n" if stream == "stdout" else "")
                    stderr = diagnostic + "\n" if stream == "stderr" else ""
                    with self.subTest(tool=tool, stream=stream, diagnostic=diagnostic):
                        reasons = _validate(tool, stdout, stderr)
                        self.assertTrue(reasons)
                        self.assertTrue(any("diagnostic" in reason for reason in reasons), reasons)

    def test_malformed_and_nonzero_summaries_rejected(self):
        bad_lines = [
            "Errors: 1, Warnings: 0",
            "Errors: 0, Warnings: 1",
            "Errors: x, Warnings: 0",
            "Errors: -1, Warnings: 0",
            "Errors: +1, Warnings: 0",
            "Errors: 0, Warnings:",
            "Errors: 0, Warnings: 0 junk",
            "Errors: 0, Warnings: 0.0",
            "ERRORS: 0, WARNINGS: 0",
            "Warnings: 0",
            "Error code=0",
        ]
        for tool, banner in (("vlog", VLOG_BANNER), ("vsim", VSIM_BANNER)):
            for line in bad_lines:
                with self.subTest(tool=tool, line=line):
                    self.assert_rejected(tool, banner + "\n" + line + "\n")
            duplicate = banner + "\nErrors: 0, Warnings: 0\nErrors: 0, Warnings: 0\n"
            conflicting = banner + "\nErrors: 0, Warnings: 0\nErrors: 1, Warnings: 0\n"
            both_streams = (
                banner + "\nErrors: 0, Warnings: 0\n",
                "Errors: 0, Warnings: 0\n",
            )
            with self.subTest(tool=tool, case="duplicate_identical"):
                self.assert_rejected(tool, duplicate)
            with self.subTest(tool=tool, case="duplicate_conflicting"):
                self.assert_rejected(tool, conflicting)
            with self.subTest(tool=tool, case="summary_on_both_streams"):
                self.assert_rejected(tool, both_streams[0], both_streams[1])

    def test_banner_identity_rejected(self):
        for tool, banner, other in (
            ("vlog", VLOG_BANNER, VSIM_BANNER),
            ("vsim", VSIM_BANNER, VLOG_BANNER),
        ):
            role = "Compiler" if tool == "vlog" else "Simulator"
            other_role = "Simulator" if role == "Compiler" else "Compiler"
            cases = {
                "wrong_tool": other + "\n",
                "wrong_version": banner.replace("10.7", "10.70") + "\n",
                "older_version": banner.replace("10.7", "10.6") + "\n",
                "wrong_role": banner.replace(role, other_role) + "\n",
                "wrong_edition": banner.replace("SE-64", "PE") + "\n",
                "leading_text": "not " + banner + "\n",
                "trailing_text": banner + " junk\n",
                "release_missing": f"Model Technology ModelSim SE-64 {tool} 10.7 {role}\n",
                "embedded_newline": banner.replace(f" {tool} ", f" {tool}\n") + "\n",
                "duplicate_identical": banner + "\n" + banner + "\n",
                "conflict_version": banner + "\n" + banner.replace("10.7", "2020.4") + "\n",
                "conflict_tool": banner + "\n" + other + "\n",
            }
            for name, stdout in cases.items():
                with self.subTest(tool=tool, case=name):
                    self.assert_rejected(tool, stdout)

    def test_missing_banner_and_bare_substring_rejected(self):
        for tool in ("vlog", "vsim"):
            with self.subTest(tool=tool, case="empty"):
                self.assert_rejected(tool, "")
            with self.subTest(tool=tool, case="bare_substring"):
                self.assert_rejected(tool, "a random 10.7 hint\n")
            with self.subTest(tool=tool, case="generic_old_probe"):
                self.assert_rejected(tool, "ModelSim SE-64 10.7 / 2017.12\n")

    def test_cross_stream_conflicts_rejected(self):
        for tool, banner in (("vlog", VLOG_BANNER), ("vsim", VSIM_BANNER)):
            with self.subTest(tool=tool, case="cross_stream_version"):
                self.assert_rejected(tool, banner + "\n", banner.replace("10.7", "10.6") + "\n")
            with self.subTest(tool=tool, case="cross_stream_duplicate"):
                self.assert_rejected(tool, banner + "\n", banner + "\n")

    def test_exit_timeout_and_exception_rejected(self):
        for tool, banner in (("vlog", VLOG_BANNER), ("vsim", VSIM_BANNER)):
            with self.subTest(tool=tool, case="exit7"):
                self.assert_rejected(tool, banner + "\n", exit_code=7, contains="exit was 7")
            with self.subTest(tool=tool, case="exit_none"):
                self.assert_rejected(tool, banner + "\n", exit_code=None, contains="exit was None")
            with self.subTest(tool=tool, case="exit_bool"):
                self.assert_rejected(tool, banner + "\n", exit_code=True, contains="exit was")
            with self.subTest(tool=tool, case="timeout"):
                self.assert_rejected(tool, banner + "\n", timed_out=True, contains="timed out")
            for exception in ("OSError", "FileNotFoundError", "TimeoutExpired"):
                with self.subTest(tool=tool, exception=exception):
                    self.assert_rejected(
                        tool, banner + "\n", exception=exception, contains=exception
                    )

    def test_prefix_and_summary_strictness(self):
        for tool, banner in (("vlog", VLOG_BANNER), ("vsim", VSIM_BANNER)):
            with self.subTest(tool=tool, case="double_hash"):
                self.assert_rejected(tool, "# # " + banner + "\n")
            with self.subTest(tool=tool, case="hash_no_space"):
                self.assert_rejected(tool, "#" + banner + "\n")
            with self.subTest(tool=tool, case="summary_hash_prefix"):
                self.assert_rejected(
                    tool, banner + "\n# Errors: 0, Warnings: 0\n"
                )
            with self.subTest(tool=tool, case="split_error"):
                self.assert_rejected(tool, banner + "\n** Error\n: failure\n")

    def test_reason_names_the_stream(self):
        reasons = _validate("vlog", VLOG_BANNER + "\n", "** Error: failed\n")
        self.assertTrue(any("stderr" in reason and "diagnostic" in reason for reason in reasons))
        reasons = _validate("vlog", VLOG_BANNER + "\n** Error: failed\n", "")
        self.assertTrue(any("stdout" in reason and "diagnostic" in reason for reason in reasons))


class ToolVersionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.out = base / "run"
        self.out.mkdir()
        self.modelsim = base / "modelsim"
        self.modelsim.mkdir()
        (self.modelsim / "vlog.exe").write_bytes(b"")
        (self.modelsim / "vsim.exe").write_bytes(b"")

    def tearDown(self):
        self.tmp.cleanup()

    def test_healthy_writes_raw_evidence(self):
        calls = []
        with mock.patch.object(RUNNER, "_run_hidden", side_effect=_healthy_hidden(calls)):
            versions, reasons = RUNNER._tool_version(self.modelsim, self.out)
        self.assertEqual([], reasons)
        self.assertEqual(["vlog", "vsim"], calls)
        self.assertTrue(versions["vlog"]["ok"])
        self.assertTrue(versions["vsim"]["ok"])
        self.assertEqual(VLOG_BANNER_CRLF, (self.out / "tool-check" / "vlog.stdout.bin").read_bytes())
        self.assertEqual(VSIM_BANNER_CRLF, (self.out / "tool-check" / "vsim.stdout.bin").read_bytes())
        self.assertEqual(b"", (self.out / "tool-check" / "vlog.stderr.bin").read_bytes())
        self.assertEqual(
            hashlib.sha256(VLOG_BANNER_CRLF).hexdigest(),
            versions["vlog"]["stdout_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(VSIM_BANNER_CRLF).hexdigest(),
            versions["vsim"]["stdout_sha256"],
        )
        self.assertIn(VLOG_BANNER, versions["vlog"]["text"])
        invocation = json.loads(
            (self.out / "tool-check" / "vlog.invocation.json").read_text(encoding="utf-8")
        )
        self.assertEqual("-version", invocation["argv"][1])
        self.assertEqual(0, invocation["exit"])
        self.assertFalse(invocation["timed_out"])
        payload = json.loads((self.out / "tool_versions.json").read_text(encoding="utf-8"))
        self.assertEqual({"vlog", "vsim"}, set(payload))
        self.assertTrue(payload["vlog"]["ok"])
        self.assertEqual([], payload["vlog"]["reasons"])

    def test_error_diagnostic_preserves_bytes_and_fails(self):
        calls = []
        bad_stdout = VLOG_BANNER_CRLF + b"** Error: license failed\n"
        hidden = _healthy_hidden(calls, stdout_map={"vlog": bad_stdout})
        with mock.patch.object(RUNNER, "_run_hidden", side_effect=hidden):
            versions, reasons = RUNNER._tool_version(self.modelsim, self.out)
        self.assertTrue(reasons)
        self.assertFalse(versions["vlog"]["ok"])
        self.assertTrue(versions["vsim"]["ok"])
        self.assertTrue(any("diagnostic" in reason for reason in versions["vlog"]["reasons"]))
        self.assertEqual(bad_stdout, (self.out / "tool-check" / "vlog.stdout.bin").read_bytes())
        self.assertEqual(
            hashlib.sha256(bad_stdout).hexdigest(),
            versions["vlog"]["stdout_sha256"],
        )
        self.assertEqual(["vlog", "vsim"], calls)
        self.assertTrue((self.out / "tool_versions.json").is_file())

    def test_raised_exceptions_are_evidence(self):
        calls = []
        def hidden(argv, cwd, timeout):
            tool = pathlib.Path(argv[0]).stem
            calls.append(tool)
            if tool == "vlog":
                raise OSError("spawn failed")
            raise FileNotFoundError("missing vsim")
        with mock.patch.object(RUNNER, "_run_hidden", side_effect=hidden):
            versions, reasons = RUNNER._tool_version(self.modelsim, self.out)
        self.assertEqual(["vlog", "vsim"], calls)
        self.assertTrue(any("OSError" in reason for reason in reasons), reasons)
        self.assertTrue(any("FileNotFoundError" in reason for reason in reasons), reasons)
        self.assertEqual("OSError", versions["vlog"]["exception_type"])
        self.assertEqual("FileNotFoundError", versions["vsim"]["exception_type"])
        self.assertFalse(versions["vlog"]["ok"])
        self.assertFalse(versions["vsim"]["ok"])
        self.assertEqual(b"", (self.out / "tool-check" / "vlog.stdout.bin").read_bytes())
        invocation = json.loads(
            (self.out / "tool-check" / "vlog.invocation.json").read_text(encoding="utf-8")
        )
        self.assertEqual("OSError", invocation["exception_type"])
        self.assertIsNone(invocation["exit"])
        self.assertFalse(invocation["timed_out"])
        self.assertTrue((self.out / "tool_versions.json").is_file())

    def test_raised_timeout_preserves_partial_bytes(self):
        calls = []
        def hidden(argv, cwd, timeout):
            tool = pathlib.Path(argv[0]).stem
            calls.append(tool)
            if tool == "vlog":
                raise subprocess.TimeoutExpired(
                    cmd=argv,
                    timeout=timeout,
                    output=VLOG_BANNER_CRLF,
                    stderr=b"** Warning: partial\n",
                )
            return _invocation(tool, VSIM_BANNER_CRLF, argv=argv, cwd=str(cwd))
        with mock.patch.object(RUNNER, "_run_hidden", side_effect=hidden):
            versions, reasons = RUNNER._tool_version(self.modelsim, self.out)
        self.assertEqual(["vlog", "vsim"], calls)
        self.assertTrue(any("TimeoutExpired" in reason for reason in reasons), reasons)
        self.assertTrue(any("timed out" in reason for reason in reasons), reasons)
        self.assertTrue(versions["vlog"]["timed_out"])
        self.assertEqual("TimeoutExpired", versions["vlog"]["exception_type"])
        self.assertEqual(
            VLOG_BANNER_CRLF,
            (self.out / "tool-check" / "vlog.stdout.bin").read_bytes(),
        )
        self.assertEqual(
            b"** Warning: partial\n",
            (self.out / "tool-check" / "vlog.stderr.bin").read_bytes(),
        )

    def test_internal_timeout_and_nonzero_exit_fail(self):
        calls = []
        def hidden(argv, cwd, timeout):
            tool = pathlib.Path(argv[0]).stem
            calls.append(tool)
            if tool == "vlog":
                return _invocation(
                    tool, VLOG_BANNER_CRLF, exit_code=None, timed_out=True,
                    argv=argv, cwd=str(cwd),
                )
            return _invocation(
                tool, VSIM_BANNER_CRLF, exit_code=7, argv=argv, cwd=str(cwd),
            )
        with mock.patch.object(RUNNER, "_run_hidden", side_effect=hidden):
            versions, reasons = RUNNER._tool_version(self.modelsim, self.out)
        self.assertEqual(["vlog", "vsim"], calls)
        self.assertTrue(versions["vlog"]["timed_out"])
        self.assertEqual(7, versions["vsim"]["exit"])
        self.assertFalse(versions["vlog"]["ok"])
        self.assertFalse(versions["vsim"]["ok"])
        self.assertTrue(any("timed out" in reason for reason in reasons), reasons)
        self.assertTrue(any("exit was 7" in reason for reason in reasons), reasons)
class UnchangedSemanticsTests(unittest.TestCase):
    def test_classify_compile_zero_summary(self):
        self.assertTrue(
            RUNNER.classify_compile(0, "Errors: 0, Warnings: 0\n", "")["ok"]
        )
        self.assertFalse(RUNNER.classify_compile(0, "** Error: failed\n", "")["ok"])
        self.assertFalse(
            RUNNER.classify_compile(1, "Errors: 0, Warnings: 0\n", "")["ok"]
        )

    def test_simulation_classification_healthy(self):
        stats = (
            "SAMPLE_SCAN_STATS case=directed checks=1 errors=0 windows=1 "
            "events=14 scans=3 retired=2 discarded=6 order_errors=1 "
            "overruns=1 partial_len=0 occupied=0 armed=1 exhausted=0"
        )
        stdout = (
            "SAMPLE_SCAN_PASS\n"
            + stats
            + "\nErrors: 0, Warnings: 0\n"
        )
        result = RUNNER.classify_simulation_output(
            0, stdout, "", "directed", RUNNER.EXPECTED_FINAL_STATS["directed"]
        )
        self.assertTrue(result["ok"], result["reasons"])
        bad = RUNNER.classify_simulation_output(
            0,
            "** Error: failed\n" + stdout,
            "",
            "directed",
            RUNNER.EXPECTED_FINAL_STATS["directed"],
        )
        self.assertFalse(bad["ok"])

    def test_selection_and_aggregation(self):
        selected = RUNNER.select_cases(["all"], ["directed"])
        self.assertEqual(["directed"], [entry["name"] for entry in selected])
        with self.assertRaises(ValueError):
            RUNNER.select_cases(["all"], ["directed", "directed"])
        passed = RUNNER.aggregate_results(
            ["directed"],
            {"directed": {"ok": True, "classification": "x", "reasons": []}},
        )
        self.assertTrue(passed["ok"])
        missing = RUNNER.aggregate_results(["directed"], {})
        self.assertFalse(missing["ok"])


class EntryPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.root = base / "root"
        (self.root / RUNNER.RTL_RELATIVE).parent.mkdir(parents=True, exist_ok=True)
        (self.root / RUNNER.RTL_RELATIVE).write_bytes(b"// synthetic RTL\n")
        (self.root / RUNNER.TB_RELATIVE).parent.mkdir(parents=True, exist_ok=True)
        (self.root / RUNNER.TB_RELATIVE).write_bytes(b"// synthetic TB\n")
        self.modelsim = base / "modelsim"
        self.modelsim.mkdir()
        (self.modelsim / "vlog.exe").write_bytes(b"")
        (self.modelsim / "vsim.exe").write_bytes(b"")
        self.out = base / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, hidden, case_calls):
        argv = [
            "--root", str(self.root),
            "--out", str(self.out),
            "--modelsim", str(self.modelsim),
            "--case", "directed",
        ]
        def fake_case(root, out, modelsim_dir, entry):
            case_calls.append(entry["name"])
            return {
                "ok": True,
                "reasons": [],
                "classification": "verified",
                "stats": None,
                "mismatches": None,
            }
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(RUNNER, "_run_hidden", side_effect=hidden):
            with mock.patch.object(RUNNER, "run_case", side_effect=fake_case):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = RUNNER.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_healthy_preflight_proceeds_and_runs_case(self):
        calls = []
        case_calls = []
        code, stdout, stderr = self._run(_healthy_hidden(calls), case_calls)
        self.assertEqual(0, code)
        self.assertIn("SAMPLE_SCAN_RUN_PASS", stdout)
        self.assertEqual("", stderr)
        self.assertEqual(["vlog", "vsim"], calls)
        self.assertEqual(["directed"], case_calls)
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertTrue(summary["ok"])
        self.assertEqual(["directed"], summary["selected"])
        self.assertTrue(summary["results"]["directed"]["ok"])

    def test_preflight_error_stops_all_case_work(self):
        calls = []
        case_calls = []
        bad_stdout = VLOG_BANNER_CRLF + b"** Error: license failed\n"
        hidden = _healthy_hidden(calls, stdout_map={"vlog": bad_stdout})
        code, stdout, stderr = self._run(hidden, case_calls)
        self.assertEqual(2, code)
        self.assertIn("SAMPLE_SCAN_RUN_FAIL", stdout)
        self.assertEqual([], case_calls)
        self.assertEqual(["vlog", "vsim"], calls)
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertFalse(summary["ok"])
        self.assertTrue(summary["reasons"])
        self.assertEqual({}, summary["results"])
        versions = json.loads((self.out / "tool_versions.json").read_text(encoding="utf-8"))
        self.assertFalse(versions["vlog"]["ok"])
        self.assertTrue(versions["vsim"]["ok"])
        self.assertEqual(bad_stdout, (self.out / "tool-check" / "vlog.stdout.bin").read_bytes())

    def test_preflight_error_on_vsim_stops_all_case_work(self):
        calls = []
        case_calls = []
        bad_stderr = b"** Warning: incompatible\n"
        hidden = _healthy_hidden(calls, stderr_map={"vsim": bad_stderr})
        code, stdout, stderr = self._run(hidden, case_calls)
        self.assertEqual(2, code)
        self.assertEqual([], case_calls)
        self.assertEqual(["vlog", "vsim"], calls)
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertFalse(summary["ok"])
        self.assertTrue(any("vsim" in reason for reason in summary["reasons"]))
        self.assertEqual(
            bad_stderr,
            (self.out / "tool-check" / "vsim.stderr.bin").read_bytes(),
        )

    def test_preflight_raised_oserror_stops_all_case_work(self):
        calls = []
        case_calls = []
        def hidden(argv, cwd, timeout):
            tool = pathlib.Path(argv[0]).stem
            calls.append(tool)
            if tool == "vlog":
                raise OSError("spawn failed")
            return _invocation(tool, VSIM_BANNER_CRLF, argv=argv, cwd=str(cwd))
        code, stdout, stderr = self._run(hidden, case_calls)
        self.assertEqual(2, code)
        self.assertEqual([], case_calls)
        self.assertEqual(["vlog", "vsim"], calls)
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertFalse(summary["ok"])
        self.assertTrue(any("OSError" in reason for reason in summary["reasons"]))
        versions = json.loads((self.out / "tool_versions.json").read_text(encoding="utf-8"))
        self.assertEqual("OSError", versions["vlog"]["exception_type"])
        self.assertTrue((self.out / "tool-check" / "vlog.stdout.bin").is_file())

    def test_preflight_timeout_stops_all_case_work(self):
        calls = []
        case_calls = []
        def hidden(argv, cwd, timeout):
            tool = pathlib.Path(argv[0]).stem
            calls.append(tool)
            if tool == "vlog":
                raise subprocess.TimeoutExpired(
                    cmd=argv, timeout=timeout, output=VLOG_BANNER_CRLF,
                    stderr=b"partial\n",
                )
            return _invocation(tool, VSIM_BANNER_CRLF, argv=argv, cwd=str(cwd))
        code, stdout, stderr = self._run(hidden, case_calls)
        self.assertEqual(2, code)
        self.assertEqual([], case_calls)
        self.assertEqual(["vlog", "vsim"], calls)
        summary = json.loads((self.out / "summary.json").read_text(encoding="utf-8"))
        self.assertFalse(summary["ok"])
        self.assertTrue(any("timed out" in reason for reason in summary["reasons"]))
        self.assertEqual(
            VLOG_BANNER_CRLF,
            (self.out / "tool-check" / "vlog.stdout.bin").read_bytes(),
        )
        self.assertEqual(
            b"partial\n",
            (self.out / "tool-check" / "vlog.stderr.bin").read_bytes(),
        )

    def test_healthy_zero_tally_on_stderr_proceeds(self):
        calls = []
        case_calls = []
        hidden = _healthy_hidden(
            calls,
            stderr_map={"vlog": b"Errors: 0, Warnings: 0\n"},
        )
        code, stdout, stderr = self._run(hidden, case_calls)
        self.assertEqual(0, code)
        self.assertIn("SAMPLE_SCAN_RUN_PASS", stdout)
        self.assertEqual(["directed"], case_calls)


class ProtectedSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = RUNNER_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.nodes = {}
        cls.top_level = []
        for node in cls.tree.body:
            segment = ast.get_source_segment(cls.source, node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cls.nodes[node.name] = node
            else:
                cls.top_level.append({
                    "kind": type(node).__name__,
                    "source_sha256": hashlib.sha256((segment or "").encode("utf-8")).hexdigest(),
                })

    def test_protected_functions_unchanged(self):
        for name, (source_sha, ast_sha) in PROTECTED_FUNCTIONS.items():
            with self.subTest(function=name):
                self.assertIn(name, self.nodes)
                node = self.nodes[name]
                segment = ast.get_source_segment(self.source, node) or ""
                self.assertEqual(source_sha, hashlib.sha256(segment.encode("utf-8")).hexdigest())
                self.assertEqual(
                    ast_sha,
                    hashlib.sha256(
                        ast.dump(node, include_attributes=False).encode("utf-8")
                    ).hexdigest(),
                )

    def test_tool_version_source_actually_changed(self):
        self.assertIn("_tool_version", self.nodes)
        segment = ast.get_source_segment(self.source, self.nodes["_tool_version"]) or ""
        self.assertNotEqual(
            ORIGINAL_TOOL_VERSION_SOURCE_SHA256,
            hashlib.sha256(segment.encode("utf-8")).hexdigest(),
        )

    def test_only_expected_function_set(self):
        self.assertEqual(EXPECTED_FUNCTION_SET, set(self.nodes))

    def test_top_level_unchanged(self):
        payload = json.dumps(
            self.top_level, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        self.assertEqual(TOP_LEVEL_SHA256, hashlib.sha256(payload).hexdigest())

    def test_tests_do_not_spawn_vendor_processes(self):
        tree = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                self.assertFalse(
                    func.value.id == "subprocess" and func.attr in {"run", "Popen"},
                    f"unexpected subprocess call at line {node.lineno}",
                )

    def test_tests_have_no_private_controller_imports(self):
        tree = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
        forbidden = ("fpga_mesh", "services", "feishu", "project_cli")
        self.assertFalse(
            [module for module in modules if module.startswith(forbidden)],
            modules,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
