import pathlib
import subprocess
import sys

patch = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
result = subprocess.run(
    [sys.argv[2], "--codex-run-as-apply-patch", patch],
    cwd=sys.argv[3],
    check=False,
)
raise SystemExit(result.returncode)