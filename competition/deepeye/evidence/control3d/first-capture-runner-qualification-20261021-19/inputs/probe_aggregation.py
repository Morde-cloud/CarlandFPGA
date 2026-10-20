"""Synthetic orchestration probe, explicitly NOT a simulator/RTL mutant run."""
from pathlib import Path
import importlib.util, json, hashlib, sys, subprocess
from datetime import datetime,timezone
sys.dont_write_bytecode=True
O=Path(__file__).parent
W=Path(r"D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014")
spec=importlib.util.spec_from_file_location("op18_runner_aggregate_probe",O/"runner_final_snapshot.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
frozen=json.loads((O/"PARSER_CASES_FROZEN.json").read_bytes())
good=next(c["text"] for c in frozen["cases"] if c["name"]=="mutant-minimal-positive")
cases=[("all-good",None,True),("one-foreign-error","foreign_error",False),
       ("one-abnormal-exit","abnormal_exit",False),("one-timeout","timeout",False)]
with (O/"AGGREGATION_CASES_FROZEN.json").open("x",encoding="utf-8") as f:
    json.dump({"at_utc":datetime.now(timezone.utc).isoformat(),"cases":cases,
       "kind":"Synthetic orchestration seam only; compile/ModelSim calls replaced with local data stubs; no real RTL execution.",
       "expectation":"An unrelated failure in one selected width must not disappear into overall success because another width supplied a target hit."},f,indent=2)
attempts=[]
def forbidden(*a,**kw): attempts.append(repr(a));raise RuntimeError("No subprocess allowed")
subprocess.Popen=forbidden
results=[]
for label,bad,expected in cases:
    out=O/"aggregation-cases"/label
    out.mkdir(parents=True,exist_ok=False)
    m.compile_case=lambda *a,**k:{"ok":True,"probe_stub":True}
    def simulated(case_dir,modelsim_dir,top,generic,value,timeout):
        text=good.replace("width=1",f"width={value}")
        selected=(case_dir.parent.name=="cancel-ignored" and value==2)
        rc=0;timed=False
        if selected:
            if bad=="foreign_error": text+="** Error: unrelated simulator runtime failure\n"
            if bad=="abnormal_exit": rc=17
            if bad=="timeout": timed=True
        (case_dir/"sim.log").write_text(text,encoding="utf-8",newline="\n")
        return {"exit_code":rc,"timed_out":timed,"probe_stub":True}
    m.run_vsim_case=simulated
    entries=m.mutant_cases(W,Path("UNUSED_NO_VENDOR_TOOL"),out,1)
    accepted=all(x["ok"] for x in entries)
    result={"name":label,"expected":expected,"accepted":accepted,"match":accepted==expected,
            "case_ok":[{"mutant":x["mutant"],"aggregate":x["ok"],"widths":[{"width":y["width"],"ok":y["ok"],"reasons":y["reasons"]} for y in x["records"]]} for x in entries]}
    (out/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    results.append(result)
report={"source_sha256":hashlib.sha256((O/"runner_final_snapshot.py").read_bytes()).hexdigest(),
        "synthetic_only":True,"vendor_invocations":0,"blocked_subprocess_attempts":attempts,
        "cases":len(cases),"unexpected_accepts":sum(not r["match"] and r["accepted"] for r in results),"results":results}
(O/"AGGREGATION_PROBE_RESULT.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))
