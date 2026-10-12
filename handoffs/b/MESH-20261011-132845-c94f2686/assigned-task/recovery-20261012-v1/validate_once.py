"""Capture one new verification run without changing preserved inputs/logs."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent


def digest(path):
    raw = path.read_bytes()
    return {"size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def check_preserved():
    inventory = json.loads((HERE / "preserved-inventory.json").read_text())
    for record in inventory["files"]:
        if digest(ORIGINAL / record["path"]) != {
                k: record[k] for k in ("size", "sha256")}:
            raise ValueError("preserved input changed: " + record["path"])
    return inventory["count"]


def main():
    count = check_preserved()
    output = HERE / "validation"
    output.mkdir(exist_ok=False)  # Do not overwrite or replay a completed run.
    env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    good = sorted("../fixtures/" + p.name for p in (ORIGINAL / "fixtures").glob("ok_*.json"))
    bad = sorted("../fixtures/" + p.name for p in (ORIGINAL / "fixtures").glob("bad_*.json"))
    runs = [
        ("version", [sys.executable, "--version"], 0),
        ("unittest", [sys.executable, "-B", "test_recovery.py", "-v"], 0),
        ("valid", [sys.executable, "-B", "canonical_json.py", *good], 0),
        ("invalid", [sys.executable, "-B", "canonical_json.py", *bad], 1),
        ("overflow_mixed", [sys.executable, "-B", "canonical_json.py",
                            "overflow.json", "../fixtures/ok_basic.json"], 1),
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
    summary = {"records": records, "preserved_files_checked": count,
               "preserved_files_checked_after": check_preserved(),
               "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1",
               "passed": all(r["exit_code"] == r["expected_exit_code"] for r in records)}
    with (output / "summary.json").open("x", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
