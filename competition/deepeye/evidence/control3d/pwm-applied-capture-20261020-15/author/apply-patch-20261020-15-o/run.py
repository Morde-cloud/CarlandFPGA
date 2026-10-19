import subprocess, pathlib
p=pathlib.Path(r"competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author/apply-patch-20261020-15-o/o.patch")
r=subprocess.run([r"C:\Users\15378\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe","--codex-run-as-apply-patch",p.read_text(encoding="utf-8")],cwd=r"D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014",capture_output=True)
print(r.returncode); print(r.stdout.decode("utf-8","replace")); print(r.stderr.decode("utf-8","replace"))
