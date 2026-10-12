"""New, exclusive evidence capture; preserves all 72 pre-existing files."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
VALIDATOR = "../recovery-20261012-v1/canonical_json.py"


def digest(path):
    raw = path.read_bytes()
    return {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def verify_baseline():
    baseline = json.loads((HERE / "baseline-inventory.json").read_text())
    for item in baseline["files"]:
        if digest(BASE / item["path"]) != {k: item[k] for k in ("size", "sha256")}:
            raise ValueError("preserved file changed: " + item["path"])
    return baseline["file_count"]


def main():
    count = verify_baseline()
    output = HERE / "validation"
    output.mkdir(exist_ok=False)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    good = sorted("../fixtures/" + p.name for p in (BASE / "fixtures").glob("ok_*.json"))
    bad = sorted("../fixtures/" + p.name for p in (BASE / "fixtures").glob("bad_*.json"))
    runs = [
        ("version", [sys.executable, "-c", "import sys; print(sys.version); print('recursion_limit=' + str(sys.getrecursionlimit()))"], 0),
        ("unittest", [sys.executable, "-B", "test_recovery.py", "-v"], 0),
        ("valid", [sys.executable, "-B", VALIDATOR, *good], 0),
        ("invalid", [sys.executable, "-B", VALIDATOR, *bad], 1),
        ("deep_valid", [sys.executable, "-B", VALIDATOR, "deep_2000.json"], 0),
        ("overflow_mixed", [sys.executable, "-B", VALIDATOR,
                            "../recovery-20261012-v1/overflow.json", "../fixtures/ok_basic.json"], 1),
    ]
    records = []
    for name, argv, expected in runs:
        started = datetime.now(timezone.utc).isoformat()
        result = subprocess.run(argv, cwd=HERE, env=env, capture_output=True, timeout=60)
        for stream in ("stdout", "stderr"):
            with (output / (name + "." + stream + ".txt")).open("xb") as f:
                f.write(getattr(result, stream))
        records.append({"name": name, "argv": argv, "cwd": str(HERE),
                        "started_at": started, "exit_code": result.returncode,
                        "expected_exit_code": expected,
                        "stdout": digest(output / (name + ".stdout.txt")),
                        "stderr": digest(output / (name + ".stderr.txt"))})
    summary = {"records": records, "preserved_files_before": count,
               "preserved_files_after": verify_baseline(),
               "environment": {"PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"},
               "passed": all(r["exit_code"] == r["expected_exit_code"] for r in records)}
    with (output / "summary.json").open("x", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
