"""New coordinator parser counterexamples; no vendor/product suite execution."""
from pathlib import Path
import hashlib, importlib.util, json, sys, subprocess, socket
from datetime import datetime, timezone

sys.dont_write_bytecode=True
O=Path(__file__).parent
W=Path(r"D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014")
source=W/"competition/deepeye/tools/control3d/run_first_capture_deadline.py"
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(source.read_bytes())=="a78779ae94f72f183eedfb994a8d6f645258d3289881ec2511cf5afe5143d9eb"
snap=O/"runner_final_snapshot.py"
with snap.open("xb") as f:f.write(source.read_bytes())
groups=["obs","cancel","reset","restart","priority","held","terminal","latch","random"]
def normal():
    lines=["DEEPEYE_FC_RUN width=1 kind=standalone"]
    lines += [f"DEEPEYE_FC_SCENARIO id=s{i} width=1 group={g} budget=1 obs=0 checks=1 status=pass" for i,g in enumerate(groups)]
    lines += ["DEEPEYE_FC_SUMMARY width=1 kind=standalone scenarios=9 checks=9 failures=0 groups="+",".join(f"{g}:1" for g in groups),
              "DEEPEYE_FC_FINISH width=1 status=PASS"]
    return lines
def mutant():
    lines=normal()
    lines.insert(1,"DEEPEYE_FC_CHECK_FAIL width=1 scenario=s0 phase=post waiting dut=1 ref=0")
    lines[2]=lines[2].removesuffix("pass")+"fail"
    lines[-2]=lines[-2].replace("failures=0","failures=1")
    lines[-1]=lines[-1].removesuffix("PASS")+"FAIL"
    lines.append("** Fatal: DEEPEYE_FC_BEHAVIOR_FAIL width=1 failures=1")
    return lines
def guard():
    return ["DEEPEYE_FC_RUN width=0 kind=guard",
            "DEEPEYE_FIRST_CAPTURE_INVALID_PARAM BUDGET_W=0 SAFE_BUDGET_W=1",
            "** Fatal: DEEPEYE_FIRST_CAPTURE_INVALID_PARAM unsupported width"]
bases={"normal":normal(),"guard":guard(),"mutant":mutant()}
cases=[]
def add(name,kind,lines,expected,exit_code=0,timeout=False):
    cases.append({"name":name,"kind":kind,"text":"\n".join(lines)+"\n",
                  "expected_accept":expected,"exit_code":exit_code,"timed_out":timeout})
for kind,base in bases.items():
    add(kind+"-minimal-positive",kind,base,True)
    add(kind+"-ModelSim-prefix-positive",kind,["# "+l for l in base],True)
    add(kind+"-nonzero-exit",kind,base,False,exit_code=1)
    add(kind+"-timeout",kind,base,False,timeout=True)
    add(kind+"-explicit-modelsim-error",kind,base+["** Error: unrelated load failure"],False)
    add(kind+"-plain-error",kind,base+["Error: unrelated load failure"],False)
    add(kind+"-plain-fatal",kind,base+["Fatal: unrelated runtime failure"],False)
    for value in (1,2,7):
        # Normal completion tolerates no errors; guard/mutant have one expected own fatal.
        expected=(kind in {"guard","mutant"} and value==1)
        add(kind+f"-error-tally-{value}",kind,base+[f"Errors: {value}, Warnings: 0"],expected)
    add(kind+"-conflicting-tallies",kind,base+["Errors: 0, Warnings: 0","Errors: 7, Warnings: 0"],False)
    add(kind+"-warning-control",kind,base+["Warning: arbitrary warning"],True)
for pos in range(3):
    seq=guard();seq.insert(pos,"ERROR: unrelated prepare failure")
    add(f"guard-plain-error-position-{pos}","guard",seq,False)
add("guard-missing-own-fatal","guard",guard()[:-1],False)
add("guard-wrong-param","guard",[l.replace("SAFE_BUDGET_W=1","SAFE_BUDGET_W=32") for l in guard()],False)
add("normal-finish-before-summary","normal",normal()[:-2]+normal()[-2:][::-1],False)
add("mutant-no-numeric-difference","mutant",[l.replace("dut=1 ref=0","dut=0 ref=0") for l in mutant()],False)

freeze={"at_utc":datetime.now(timezone.utc).isoformat(),"source_sha256":sha(snap.read_bytes()),
        "independence":"Coordinator-designed expected cases after source inspection, not pre-source blind oracle. No author expected-value code imported.",
        "cases":cases}
with (O/"PARSER_CASES_FROZEN.json").open("x",encoding="utf-8") as f:json.dump(freeze,f,indent=2)
spec=importlib.util.spec_from_file_location("op18_exact_runner_for_review",snap)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
attempts=[]
def forbidden(*a,**k):
    attempts.append(repr(a));raise RuntimeError("No process/network allowed in parser probe")
subprocess.Popen=forbidden
socket.socket=forbidden
results=[]
logdir=O/"parser-cases";logdir.mkdir(exist_ok=False)
for i,case in enumerate(cases):
    logfile=logdir/f"{i:03d}-{case['name']}.log"
    with logfile.open("x",encoding="utf-8",newline="\n") as f:f.write(case["text"])
    args=(case["text"],0 if case["kind"]=="guard" else 1)
    if case["kind"]=="normal":
        value=module.qualify_normal_log(*args,"standalone",set(groups),case["exit_code"],case["timed_out"])
    else:
        value=getattr(module,"qualify_"+case["kind"]+"_log")(*args,case["exit_code"],case["timed_out"])
    results.append({"index":i,"name":case["name"],"kind":case["kind"],"expected":case["expected_accept"],
                    "accepted":value[0],"reasons":value[2],"match":bool(value[0])==case["expected_accept"],
                    "log_path":str(logfile),"log_sha256":sha(logfile.read_bytes())})
report={"source":str(source),"source_sha256":sha(snap.read_bytes()),"source_snapshot":str(snap),
        "cases":len(results),"expected_accept_controls":sum(c["expected_accept"] for c in cases),
        "unexpected_accepts":[r for r in results if not r["match"] and r["accepted"]],
        "unexpected_rejects":[r for r in results if not r["match"] and not r["accepted"]],
        "blocked_process_network_attempts":attempts,"results":results}
with (O/"PARSER_PROBE_RESULT.json").open("x",encoding="utf-8") as f:json.dump(report,f,indent=2)
print(json.dumps({k:v for k,v in report.items() if k not in ("results",)},indent=2))
