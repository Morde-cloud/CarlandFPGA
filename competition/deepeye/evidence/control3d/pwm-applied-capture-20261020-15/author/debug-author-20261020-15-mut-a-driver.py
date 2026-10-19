import subprocess, pathlib, time, json, hashlib, re
root = pathlib.Path(r"D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014")
out = root / "competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author/debug-author-20261020-15-mut-a"
out.mkdir(parents=True, exist_ok=False)
workroot = out/"work"; workroot.mkdir()
vlib = r"D:\modelsim1\win64\vlib.exe"; vlog = r"D:\modelsim1\win64\vlog.exe"; vsim = r"D:\modelsim1\win64\vsim.exe"
atomic=str(root/"competition/deepeye/fpga/control3d/deepeye_atomic_pwm.sv")
cap=str(root/"competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv")
tb=str(root/"competition/deepeye/tests/rtl/control3d/tb_pwm_applied_capture.sv")
rtl_text=(root/"competition/deepeye/fpga/control3d/deepeye_pwm_applied_capture.sv").read_text(encoding="utf-8")
ob="rst || stop || transfer_now || g_pending || !g_running"
muts={
 "m1_delayed_T":[(ob,"rst || stop || g_pending || !g_running")],
 "m2_same_tag_retain":[(ob,"rst || stop || (transfer_now && (cfg_tag != expected_tag_q)) || (g_pending && (cfg_tag != expected_tag_q)) || !g_running"),("assign capture_rearm = capture_arm;","assign capture_rearm = capture_arm && (cfg_tag != expected_tag_q);")],
 "m3_mismatch_admitted":[("assign out_valid = transport_window && c_armed && !raw_fault &&\n                       c_out_valid && raw_equal;","assign out_valid = transport_window && c_armed && !raw_fault &&\n                       c_out_valid;")],
 "m4_no_rearm":[("assign capture_rearm = capture_arm;","assign capture_rearm = 1'b0;")],
}
def run(name, argv, cwd):
    so=(out/f"{name}.stdout.txt").open("wb"); se=(out/f"{name}.stderr.txt").open("wb")
    p=subprocess.run(argv,cwd=cwd,stdout=so,stderr=se); so.close(); se.close(); return p.returncode
for mid,reps in muts.items():
    text=rtl_text
    for old,new in reps:
        c=text.count(old); assert c==1,(mid,c,old[:40]); text=text.replace(old,new)
    d=out/mid; d.mkdir()
    mp=d/"deepeye_pwm_applied_capture.sv"; mp.write_text(text,encoding="utf-8")
    w=workroot/mid; w.mkdir()
    assert run(mid+"-vlib",[vlib,"lib"],w)==0
    rc=run(mid+"-vlog",[vlog,"-sv","-work","lib",atomic,cap,str(mp),tb],w)
    vtext=(out/f"{mid}-vlog.stdout.txt").read_text(encoding="utf-8",errors="replace")
    print(mid,"vlog",rc,"Errors: 0" in vtext)
    group={"m1_delayed_T":21,"m2_same_tag_retain":13,"m3_mismatch_admitted":22,"m4_no_rearm":30}[mid]
    rc=run(f"{mid}-g{group}",[vsim,"-c","-work","lib","-do","run -all; quit -f","-gCOUNT_W=4","-gWITNESS_W=8","-gTAG_W=8",f"-gTEST_GROUP={group}","-gLOOPBACK=0","tb_pwm_applied_capture"],w)
    txt=(out/f"{mid}-g{group}.stdout.txt").read_text(encoding="utf-8",errors="replace")
    print(mid,group,"rc",rc,"PASS" if "TB_PASS" in txt else "FAIL",[l for l in txt.splitlines() if "MISMATCH" in l][:4],"CODE7_OBSERVED" in txt)
# m4 also rejected on g13
w=workroot/"m4_no_rearm"
rc=run("m4_no_rearm-g13",[vsim,"-c","-work","lib","-do","run -all; quit -f","-gCOUNT_W=4","-gWITNESS_W=8","-gTAG_W=8","-gTEST_GROUP=13","-gLOOPBACK=0","tb_pwm_applied_capture"],w)
txt=(out/"m4_no_rearm-g13.stdout.txt").read_text(encoding="utf-8",errors="replace")
print("m4 g13","rc",rc,"PASS" if "TB_PASS" in txt else "FAIL",[l for l in txt.splitlines() if "MISMATCH" in l][:3])
