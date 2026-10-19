import subprocess, pathlib, sys, json, time
root = pathlib.Path(r"D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014")
out = root / "competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author/debug-author-20261020-15-g11-a"
out.mkdir(parents=True, exist_ok=False)
work = out / "work"; work.mkdir()
vlib = r"D:\modelsim1\win64\vlib.exe"; vlog = r"D:\modelsim1\win64\vlog.exe"; vsim = r"D:\modelsim1\win64\vsim.exe"
files = [str(root/"competition/deepeye/fpga/control3d/deepeye_atomic_pwm.sv"), str(root/"competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv"), str(root/"competition/deepeye/fpga/control3d/deepeye_pwm_applied_capture.sv"), str(root/"competition/deepeye/tests/rtl/control3d/tb_pwm_applied_capture.sv")]
def run(name, argv):
    so=(out/f"{name}.stdout.txt").open("wb"); se=(out/f"{name}.stderr.txt").open("wb")
    t=time.time(); p=subprocess.run(argv, cwd=work, stdout=so, stderr=se); so.close(); se.close()
    print(name, p.returncode, round(time.time()-t,1))
run("vlib",[vlib,"lib"])
run("vlog",[vlog,"-sv","-work","lib"]+files)
for g,cw,ww,tw in [(11,4,4,8),(12,4,8,8),(13,4,8,8),(14,4,8,8)]:
    run(f"g{g}",[vsim,"-c","-work","lib","-do","run -all; quit -f",f"-gCOUNT_W={cw}",f"-gWITNESS_W={ww}",f"-gTAG_W={tw}",f"-gTEST_GROUP={g}","-gLOOPBACK=0","tb_pwm_applied_capture"])
for g in (11,12,13,14):
    txt=(out/f"g{g}.stdout.txt").read_text(encoding="utf-8",errors="replace")
    print("== g",g,"PASS" if "TB_PASS" in txt else "FAIL", [l for l in txt.splitlines() if "MISMATCH" in l or "TB_STATS" in l or "GROUP_END" in l][-4:])
