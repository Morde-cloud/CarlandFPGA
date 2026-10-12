#!/usr/bin/env python3
"""Capture byte-exact evidence logs for this assigned-task deliverable set.

Writes under logs/:
  <run>.stdout.txt / <run>.stderr.txt   raw subprocess stdout/stderr bytes
  evidence_summary.txt                  argv, cwd, interpreter, exit codes, hashes

The captured runs include rejected CLI cases. Exit code 1 on an all-invalid
or mixed input set is the expected successful negative outcome; a problem is
reported as matched=no / mismatches>0, never as a nonzero CLI verdict alone.
"""

import hashlib
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
LOGS = HERE / "logs"
PYTHON = sys.executable

OPERATION_ID = "MESH-20261011-132845-c94f2686:B:git-handoff-v1"
REQUEST_HASH = "d48ba6f3c27522978a8a93716b967ab93f7a0820b37657481f7d380dda047d0f"

ALL_VALID = [
    "fixtures/ok_basic.json",
    "fixtures/ok_empty_object.json",
    "fixtures/ok_top_level_array.json",
    "fixtures/ok_nested.json",
    "fixtures/ok_unicode_keys.json",
    "fixtures/ok_escaped_newline.json",
    "fixtures/ok_numbers.json",
    "fixtures/ok_no_normalization.json",
]

ALL_INVALID = [
    "fixtures/bad_bom.json",
    "fixtures/bad_invalid_utf8.json",
    "fixtures/bad_duplicate_key.json",
    "fixtures/bad_duplicate_key_nested.json",
    "fixtures/bad_nan.json",
    "fixtures/bad_negative_infinity.json",
    "fixtures/bad_surrogate_value.json",
    "fixtures/bad_surrogate_key.json",
    "fixtures/bad_not_json.json",
    "fixtures/bad_raw_newline_in_string.json",
    "fixtures/bad_whitespace_space.json",
    "fixtures/bad_whitespace_pretty.json",
    "fixtures/bad_missing_terminal_lf.json",
    "fixtures/bad_doubled_terminal_lf.json",
    "fixtures/bad_crlf_terminal.json",
    "fixtures/bad_key_order_utf16.json",
    "fixtures/bad_escaped_unicode.json",
]

_VERSION_PROBE = (
    "import platform, sys\n"
    "print('sys.version=' + sys.version.replace(chr(10), ' '))\n"
    "print('sys.executable=' + sys.executable)\n"
    "print('platform=' + platform.platform())\n"
    "print('utf8_mode=' + str(sys.flags.utf8_mode))\n"
    "print('filesystem_encoding=' + sys.getfilesystemencoding())\n"
)

FIXED_FILES = [
    ".gitattributes",
    ".gitignore",
    "README.md",
    "canonical_json.py",
    "fixtures/generate_fixtures.py",
    "run_evidence.py",
    "test_canonical_json.py",
]

RUNS = [
    ("generate_fixtures", [PYTHON, "fixtures/generate_fixtures.py"], 0),
    ("tool_version", [PYTHON, "-c", _VERSION_PROBE], 0),
    ("unittest", [PYTHON, "-m", "unittest", "-v", "test_canonical_json"], 0),
    ("cli_all_valid", [PYTHON, "canonical_json.py"] + ALL_VALID, 0),
    ("cli_all_invalid", [PYTHON, "canonical_json.py"] + ALL_INVALID, 1),
    (
        "cli_mixed",
        [
            PYTHON,
            "canonical_json.py",
            "fixtures/ok_unicode_keys.json",
            "fixtures/bad_crlf_terminal.json",
            "fixtures/bad_duplicate_key.json",
        ],
        1,
    ),
    ("cli_no_args", [PYTHON, "canonical_json.py"], 2),
    (
        "cli_missing_file",
        [PYTHON, "canonical_json.py", "fixtures/does_not_exist.json"],
        1,
    ),
]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    LOGS.mkdir(exist_ok=True)
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cwd = str(HERE)

    fixture_files = sorted(
        "fixtures/" + path.name for path in (HERE / "fixtures").glob("*.json")
    )
    expected_fixtures = sorted(ALL_VALID + ALL_INVALID)
    failures = 0
    if fixture_files != expected_fixtures:
        failures += 1
        print("FIXTURE SET MISMATCH: %r != %r" % (fixture_files, expected_fixtures))

    lines = []
    lines.append("# Evidence summary: bounded fixture validator")
    lines.append("operation_id=%s" % OPERATION_ID)
    lines.append("assignment_request_hash=%s" % REQUEST_HASH)
    lines.append("runner_argv=%s" % json.dumps(sys.argv))
    lines.append("cwd=%s" % cwd)
    lines.append("python=%s" % PYTHON)
    lines.append("child_env_PYTHONUTF8=%s" % env["PYTHONUTF8"])
    lines.append("child_env_PYTHONDONTWRITEBYTECODE=%s" % env["PYTHONDONTWRITEBYTECODE"])
    lines.append("expected_runner_exit=0")
    lines.append("")

    for name, argv, expected_code in RUNS:
        result = subprocess.run(
            argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        (LOGS / (name + ".stdout.txt")).write_bytes(result.stdout)
        (LOGS / (name + ".stderr.txt")).write_bytes(result.stderr)
        matched = result.returncode == expected_code
        if not matched:
            failures += 1
        print(
            "[%s] %s exit=%d expected=%d"
            % ("OK" if matched else "MISMATCH", name, result.returncode, expected_code)
        )
        lines.append("run=%s" % name)
        lines.append("  argv=%s" % json.dumps(argv))
        lines.append("  cwd=%s" % cwd)
        lines.append("  exit_code=%d" % result.returncode)
        lines.append("  expected_exit_code=%d" % expected_code)
        lines.append("  matched=%s" % ("yes" if matched else "no"))
        lines.append(
            "  stdout=logs/%s.stdout.txt bytes=%d sha256=%s"
            % (name, len(result.stdout), sha256(result.stdout))
        )
        lines.append(
            "  stderr=logs/%s.stderr.txt bytes=%d sha256=%s"
            % (name, len(result.stderr), sha256(result.stderr))
        )

    lines.append("")
    lines.append("# Deliverable byte audit (sha256 of exact on-disk bytes)")
    audit_files = FIXED_FILES + sorted(
        "fixtures/" + path.name for path in (HERE / "fixtures").glob("*.json")
    )
    for relative in audit_files:
        path = HERE / relative
        if not path.is_file():
            failures += 1
            lines.append("%s MISSING" % relative)
            continue
        data = path.read_bytes()
        lines.append(
            "%s size=%d sha256=%s head=%r"
            % (relative, len(data), sha256(data), data[:32])
        )

    lines.append("")
    lines.append("# Captured log hashes")
    for path in sorted(LOGS.glob("*.txt")):
        if path.name == "evidence_summary.txt":
            continue
        data = path.read_bytes()
        lines.append("logs/%s size=%d sha256=%s" % (path.name, len(data), sha256(data)))

    lines.append("")
    lines.append("mismatches=%d" % failures)
    (LOGS / "evidence_summary.txt").write_bytes(
        ("\n".join(lines) + "\n").encode("utf-8")
    )
    print("mismatches=%d" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
