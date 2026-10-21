import hashlib
import pathlib
import subprocess

base = pathlib.Path(r"D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\evidence\stream\encoded-frame-queue-20261022-20\author\patches")
src = base / "runner_source_v1.py"
dst = "D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/tools/stream/run_encoded_frame_queue.py"
exe = r"D:\pynq\CarlandFPGA\.local\deployment\node-b\.local\node-b\codex-runtime\857d625d13925b9b5f7efcaa448d46a0c0c77246c307535d36a5d6d335573bff\codex.exe"
lines = src.read_text(encoding="utf-8").splitlines()
split = 517
patch1 = "*** Begin Patch\n*** Add File: " + dst + "\n"
patch1 += "\n".join("+" + line for line in lines[:split])
patch1 += "\n*** End Patch\n"
patch2 = "*** Begin Patch\n*** Update File: " + dst + "\n@@\n"
patch2 += "\n".join(" " + line for line in lines[split-2:split])
patch2 += "\n"
patch2 += "\n".join("+" + line for line in lines[split:])
patch2 += "\n*** End Patch\n"
(base / "runner_apply_v1a.patch").write_text(patch1, encoding="utf-8", newline="\n")
(base / "runner_apply_v1b.patch").write_text(patch2, encoding="utf-8", newline="\n")
for name, patch in (("a", patch1), ("b", patch2)):
    result = subprocess.run([exe, "--codex-run-as-apply-patch", patch], capture_output=True, text=True)
    print("PATCH_" + name.upper() + "_EXIT=" + str(result.returncode))
    print(result.stdout)
    print(result.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
final = pathlib.Path(r"D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\tools\stream\run_encoded_frame_queue.py")
source_bytes = src.read_bytes()
final_bytes = final.read_bytes()
print("SOURCE_SHA=" + hashlib.sha256(source_bytes).hexdigest())
print("FINAL_SHA=" + hashlib.sha256(final_bytes).hexdigest())
print("BYTES_EQUAL=" + str(source_bytes == final_bytes))
raise SystemExit(0 if source_bytes == final_bytes else 3)