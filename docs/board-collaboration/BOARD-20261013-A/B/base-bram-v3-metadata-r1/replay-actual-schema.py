"""Host-only replay of A's actual schema plus complete HWH, using raw Git blobs.

Fetch the evidence commit first. No network, PYNQ import or hardware operations
are performed by this script. The BRAM/reset backends are the existing mocks.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import types
import unittest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", help="Replay this Git source, else working tree")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[5]
    source = "examples/board_collaboration/base_bram_board_test.py"
    evidence = "b395767272909229dd3acb289bd71a82ab8c4211"
    hwh_path = "docs/board-collaboration/BOARD-20261013-A/A/metadata-v3-readonly-preflight/base.hwh"
    hwh = subprocess.check_output(["git", "show", evidence + ":" + hwh_path], cwd=root)
    hwh_sha = hashlib.sha256(hwh).hexdigest()
    assert hwh_sha == "cbd90c84f3a46d1eba95dff7ba7d0079812f7e46641a08e2318c9928cd36ce8f"
    assert len(hwh) == 4558197
    spec = importlib.util.spec_from_file_location("actual_schema_tests", root / "tests/test_base_bram_board_test.py")
    tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tests)
    class ActualHwhTests(tests.BramTests):
        def setUp(self):
            super().setUp()
            self.bit.with_suffix(".hwh").write_bytes(hwh)
            self.hashes["hwh"] = hwh_sha

    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
        if args.source_commit:
            code = subprocess.check_output(["git", "show", args.source_commit + ":" + source], cwd=root)
            source_file = Path(directory) / "old_board_source.py"
            source_file.write_bytes(code)
            selected = types.ModuleType("selected_board_source")
            selected.__file__ = str(source_file)
            exec(compile(code, str(source_file), "exec"), selected.__dict__)
            tests.probe = selected
        else:
            code = (root / source).read_bytes()
        print(json.dumps({"evidence_kind": "host_mock", "A_evidence_commit": evidence,
                          "full_hwh_sha256": hwh_sha, "full_hwh_bytes": len(hwh),
                          "source": args.source_commit or "working_tree",
                          "source_sha256": hashlib.sha256(code).hexdigest()}, sort_keys=True))
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([
            ActualHwhTests("test_A_actual_memory_only_schema")]))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
