import pathlib
import subprocess

base = pathlib.Path(r"D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\evidence\stream\encoded-frame-queue-20261022-20\author\patches")
src = base / "runner_source_v1.py"
patch_path = base / "runner_apply_v1.patch"
dst = "D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/tools/stream/run_encoded_frame_queue.py"
lines = src.read_text(encoding="utf-8").splitlines()
patch = "*** Begin Patch\n*** Add File: " + dst + "\n"
patch += "\n".join("+" + line for line in lines)
patch += "\n*** End Patch\n"
patch_path.write_text(patch, encoding="utf-8", newline="\n")
exe = r"D:\pynq\CarlandFPGA\.local\deployment\node-b\.local\node-b\codex-runtime\857d625d13925b9b5f7efcaa448d46a0c0c77246c307535d36a5d6d335573bff\codex.exe"
result = subprocess.run(
    [exe, "--codex-run-as-apply-patch", patch],
    capture_output=True,
    text=True,
)
print(result.stdout)
print(result.stderr)
raise SystemExit(result.returncode)