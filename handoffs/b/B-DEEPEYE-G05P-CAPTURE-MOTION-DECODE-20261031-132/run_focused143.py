"""Run the new G05-only suite and retain three examples from the real CLI entry."""
import argparse
import json
from pathlib import Path
import platform
import unittest

import g05p_capture_decoder132 as decoder
import test_g05p_capture_decoder132
import test_held_observations143


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    out = parser.parse_args().out
    if not out.is_absolute():
        parser.error("choose an absolute output directory")
    out.mkdir(exist_ok=False)
    modules = (test_g05p_capture_decoder132, test_held_observations143)
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in modules)
    with (out/"unittest.log").open("x", encoding="utf8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    request = test_held_observations143.bracket_request()
    cases = []
    for name, expected in (("held", "DECODED_BRACKET_CORRELATED"), ("expired", "REFUSED_ASSOCIATION"),
                           ("invalid_json", None)):
        if name == "expired":
            request["held_observations"]["after"]["cycle_tick"] = 6000000
        path = out/(name + ".json")
        path.write_text(json.dumps(request) if expected else '{"layout":2,"layout":3}', encoding="utf8")
        code = decoder.main(["--request", str(path), "--out", str(out/name)])
        data = json.loads((out/name/"decode_result.json").read_bytes()) if code == 0 else {}
        cases.append(dict(name=name, exit=code, status=data.get("status"), expected=expected,
                          passed=(code == (0 if expected else 2) and data.get("status") == expected)))
    summary = dict(python=platform.python_version(), tests=result.testsRun, failures=len(result.failures),
                   errors=len(result.errors), skips=len(result.skipped), cli=cases, input_source="synthetic",
                   passed=result.wasSuccessful() and not result.skipped and all(c["passed"] for c in cases))
    (out/"summary.json").write_text(json.dumps(summary,indent=2), encoding="utf8")
    print(json.dumps(summary))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

