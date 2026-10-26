"""Run only the NEW work59 author benches; preserve every attempt, never retry.

Writes only a new directory below the assigned private engine evidence root.
Windows ModelSim processes launch hidden/suspended into an owned kill-on-close job.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import types

PINS = {
    "deepeye_atomic_pwm.sv": "9dc8ecf96e59a2ae8467bda64572f62eb602d52db535733f236f64ff97c43428",
    "deepeye_pwm_coherent_capture.sv": "4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456",
}
CONTRACT = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
HELPER_SHA = "3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3"

def record(path):
    b=path.read_bytes()
    return {"path":str(path),"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()}

def write_json(path,obj):
    with path.open("x",encoding="utf-8",newline="\n") as f:json.dump(obj,f,indent=2);f.write("\n")

def snapshot(source,dest):
    b=source.read_bytes();dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open("xb") as f:f.write(b)
    return {"original":str(source),**record(dest)}

def run_one(argv,cwd,name,timeout,helper):
    rec={"argv":argv,"cwd":str(cwd),"started_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
         "timeout_seconds":timeout,"hidden":True,"shell":False,"automatic_retry":False}
    write_json(cwd/(name+".intent.json"),rec)
    job=helper.WindowsJob();p=None;started=time.monotonic()
    try:
        with (cwd/(name+".stdout.txt")).open("xb") as out,(cwd/(name+".stderr.txt")).open("xb") as err:
            p=subprocess.Popen(argv,cwd=cwd,stdin=subprocess.DEVNULL,stdout=out,stderr=err,shell=False,
                               creationflags=subprocess.CREATE_NO_WINDOW|4)
            rec["pid"]=p.pid;job.attach_and_resume(p);rec["attached_before_resume"]=True
            try:rec["exit_code"]=p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                rec["timed_out"]=True;job.close();rec["exit_code"]=p.wait(timeout=10)
    except BaseException as exc:
        rec["error"]=f"{type(exc).__name__}: {exc}"
        job.close()
        if p is not None and p.poll() is None:p.kill();p.wait(timeout=10)
    finally:
        job.close();rec["job_closed"]=True
        rec["elapsed_seconds"]=time.monotonic()-started
        rec["finished_at_utc"]=dt.datetime.now(dt.timezone.utc).isoformat()
        for key in ("stdout","stderr"):
            path=cwd/(name+"."+key+".txt")
            if path.exists():rec[key]=record(path)
        write_json(cwd/(name+".process.json"),rec)
    text=(cwd/(name+".stdout.txt")).read_text(encoding="utf-8",errors="replace")+"\n"+(cwd/(name+".stderr.txt")).read_text(encoding="utf-8",errors="replace")
    print(json.dumps({"step":name,"exit_code":rec.get("exit_code"),"pid":rec.get("pid"),"seconds":rec["elapsed_seconds"]}),flush=True)
    if rec.get("exit_code")!=0 or rec.get("timed_out") or rec.get("error"):
        raise RuntimeError("tool process failed: "+name)
    if re.search(r"\*\*\s+(?:Error|Fatal):|Errors:\s*[1-9][0-9]*",text):
        raise RuntimeError("tool error diagnostic: "+name)
    return text

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--modes",nargs="+",choices=("small","production","fault_injection","boundary"),default=["small","production","fault_injection","boundary"])
    a=p.parse_args();repo=a.repo.resolve();out=a.output.resolve()
    owner=repo/".local/deployment/node-b/evidence/g05-capture-20261026-59/engine"
    if out==owner or not out.is_relative_to(owner) or out.exists():raise RuntimeError("new assigned engine evidence directory required")
    out.mkdir(parents=True,exist_ok=False)
    own=Path(__file__).resolve().parent;product=own.parents[3]
    sources=[product/"fpga/control3d"/name for name in PINS]
    sources += [own/"deepeye_g05_capture_engine.sv",own/"tb_g05_capture_engine.sv",own/"tb_g05_capture_exhaustion.sv",own/"tb_g05_capture_boundaries.sv"]
    pins={str(s):record(s) for s in sources}
    for s in sources[:2]:
        if pins[str(s)]["sha256"]!=PINS[s.name]:raise RuntimeError("readonly dependency pin mismatch")
    helper_path=repo/"fpga_mesh/windows_job.py"
    if record(helper_path)["sha256"]!=HELPER_SHA:raise RuntimeError("Windows job helper differs")
    snapshots={s.name:snapshot(s,out/"sources"/s.name) for s in sources}
    snapshot(Path(__file__).resolve(),out/"sources/run_engine_author.py")
    snapshot(helper_path,out/"sources/windows_job.py")
    helper=types.ModuleType("work59_windows_job")
    exec(compile((out/"sources/windows_job.py").read_bytes(),str(helper_path),"exec"),helper.__dict__)
    contract=subprocess.check_output(["git","show","f5989cd5defce561f9ba98e6b18fc2682945f0a2:docs/competition/deepeye-2026/immutable_scope.json"],cwd=repo)
    obj=json.loads(contract)
    if hashlib.sha256(json.dumps(obj["requirements"],ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()!=CONTRACT:raise RuntimeError("human contract differs")
    with (out/"sources/immutable_scope.json").open("xb") as f:f.write(contract)
    for name in ("ENGINE_ASSIGNMENT.md","MAIN_DESIGN_DECISION.md"):
        snapshot(owner.parent/name,out/"sources"/name)
    toolroot=Path("D:/modelsim1/win64")
    tools={name:record(toolroot/(name+".exe")) for name in ("vlib","vlog","vsim")}
    write_json(out/"INTENT.json",{"task_id":"DEEPEYE-IMPLEMENTATION-20261014","task_version":1,
        "work_id":"B-G05-EXTERNAL-ENGINE-20261026-59-v1","requirements_sha256":CONTRACT,
        "requirement_ids":[f"H{i:02}" for i in range(1,16)],"python":sys.version,"argv":sys.argv,
        "sources":pins,"snapshots":snapshots,"tools":tools,"modes":a.modes,
        "board":"not_run; A-only","synthesis":"not_run","acceptance":"main_only"})
    summaries=[]
    try:
        for tool in ("vlog","vsim"):
            run_one([str(toolroot/(tool+".exe")),"-version"],out,tool+"-version",30,helper)
        for mode in a.modes:
            directory=out/mode;directory.mkdir()
            run_one([str(toolroot/"vlib.exe"),"work"],directory,"vlib",30,helper)
            bench=("tb_g05_capture_exhaustion" if mode=="fault_injection" else
                   "tb_g05_capture_boundaries" if mode=="boundary" else "tb_g05_capture_engine")
            compile_sources=[out/"sources"/s.name for s in sources[:3]]+[out/"sources"/(bench+".sv")]
            run_one([str(toolroot/"vlog.exe"),"-sv","-work","work"]+[str(s) for s in compile_sources],directory,"vlog",60,helper)
            signals=("rst stop cfg_valid cfg_ready cfg_period cfg_highs cfg_ttl_ticks cfg_tag capture_async_i pwm_o "
                     "accepted rejected applied running pending halted fault_code applied_tick deadline_tick active_tag "
                     "result_valid result_seq result_tag result_tick result_periods result_highs result_starts result_ends").split()
            do="onerror {quit -f -code 2}\nonbreak {quit -f -code 3}\nvcd file public_waveforms.vcd\n"
            do+="vcd add "+" ".join("/"+bench+"/"+s for s in signals)+"\nrun -all\nquit -f -code 0\n"
            with (directory/"run.do").open("x",encoding="utf-8") as f:f.write(do)
            text=run_one([str(toolroot/"vsim.exe"),"-c","-voptargs=+acc","-wlf","simulation.wlf","-l","transcript.log","work."+bench,"+MODE="+mode,"-do","run.do"],directory,"vsim",240 if mode=="production" else 60,helper)
            markers=re.findall(r"^#?\s*G05_ENGINE_AUTHOR_DONE mode=(\w+) cases=(\d+) checks=(\d+) failures=0\s*$",text,re.M)
            if len(markers)!=1 or markers[0][0]!=mode:raise RuntimeError("missing/duplicate/wrong final marker "+mode)
            if "G05_ENGINE_AUTHOR_FAIL" in text or "G05_EXHAUSTION_FAIL" in text:raise RuntimeError("failed author assertion")
            summaries.append({"mode":mode,"cases":int(markers[0][1]),"checks":int(markers[0][2]),"exit_code":0,
                              "waveforms":record(directory/"public_waveforms.vcd"),"transcript":record(directory/"transcript.log")})
        if pins!={str(s):record(s) for s in sources}:raise RuntimeError("input source changed during execution")
        write_json(out/"RESULT.json",{"status":"author_simulation_complete_pending_main_review","summaries":summaries,
                   "source_pins":pins,"physical_board":"not_run; A-only","synthesis":"not_run","all29":"not_run",
                   "R03":"not_run","full_H12":"not_run","requirements_sha256":CONTRACT})
        print(json.dumps({"status":"author_simulation_complete_pending_main_review","summaries":summaries}),flush=True)
        return 0
    except BaseException as exc:
        write_json(out/"FAILURE.json",{"error":f"{type(exc).__name__}: {exc}","completed_modes":summaries,"automatic_retry":False})
        print(str(exc),file=sys.stderr,flush=True)
        return 1

if __name__=="__main__":raise SystemExit(main())
