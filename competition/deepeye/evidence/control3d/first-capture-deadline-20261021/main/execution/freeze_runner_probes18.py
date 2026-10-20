"""Freeze protocol expectations independently before main modifications."""
from pathlib import Path
import json,hashlib
from datetime import datetime,timezone
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
E=W/"competition/deepeye/evidence/control3d/first-capture-deadline-20261021/main"
groups=["obs","cancel","reset","restart","priority","held","terminal","latch","random"]
lines=["DEEPEYE_FC_RUN width=1 kind=standalone"]
lines += [f"DEEPEYE_FC_SCENARIO id=s{i} width=1 group={g} budget=1 obs=1 checks=1 status=pass" for i,g in enumerate(groups)]
lines += ["DEEPEYE_FC_SUMMARY width=1 kind=standalone scenarios=9 checks=9 failures=0 groups="+",".join(g+":1" for g in groups),
          "DEEPEYE_FC_FINISH width=1 status=PASS"]
base="\n".join(lines)+"\n"
cases=[]
def add(name,text,expected):cases.append({"name":name,"text":text,"expected_accept":expected,"width":1,"kind":"standalone","groups":groups})
add("synthetic-protocol-control",base,True)
add("modelsim-prefix-control","\n".join("# "+l for l in lines)+"\n",True)
add("crlf-control",base.replace("\n","\r\n"),True)
for prefix in ("NOT_","## ","#","#\t","prefix "):
    add("prefix-"+prefix.encode().hex(),"\n".join(prefix+l for l in lines)+"\n",False)
add("finish-before-run","\n".join([lines[-1],*lines[:-1]])+"\n",False)
add("summary-before-scenarios","\n".join([lines[0],lines[-2],*lines[1:-2],lines[-1]])+"\n",False)
add("scenario-after-finish","\n".join([lines[0],*lines[2:],lines[1]])+"\n",False)
add("duplicate-summary",base+lines[-2]+"\n",False)
add("conflicting-summary",base+lines[-2].replace("checks=9","checks=10")+"\n",False)
add("duplicate-finish",base+lines[-1]+"\n",False)
add("missing-finish","\n".join(lines[:-1])+"\n",False)
add("missing-run","\n".join(lines[1:])+"\n",False)
add("missing-scenario","\n".join([lines[0],*lines[2:]])+"\n",False)
add("unrelated-fatal",base+"# ** Fatal: unrelated\n",False)
add("unrelated-error",base+"# ** Error: unrelated\n",False)
add("incomplete-summary",base.replace(" failures=0",""),False)
add("wrong-group",base.replace("group=obs","group=unknown"),False)
add("duplicate-id",base.replace("id=s1","id=s0"),False)
add("nonpositive-check",base.replace("checks=1 status","checks=0 status",1),False)
add("empty-all-groups","\n".join([lines[0],"DEEPEYE_FC_SUMMARY width=1 kind=standalone scenarios=0 checks=0 failures=0 groups="+",".join(g+":0" for g in groups),lines[-1]])+"\n",False)
add("one-empty-group","\n".join([lines[0],*lines[2:-2],lines[-2].replace("scenarios=9 checks=9","scenarios=8 checks=8").replace("obs:1","obs:0"),lines[-1]])+"\n",False)
add("unicode-digits",base.translate(str.maketrans("0123456789","٠١٢٣٤٥٦٧٨٩")),False)
add("trailing-record-garbage",base.replace("status=PASS","status=PASS garbage"),False)
guards=[]
for width,safe in ((0,1),(33,32),(1,1),(32,32)):
    text=f"DEEPEYE_FC_RUN width={width} kind=guard\nDEEPEYE_FIRST_CAPTURE_INVALID_PARAM BUDGET_W={width} SAFE_BUDGET_W={safe}\n** Fatal: DEEPEYE_FIRST_CAPTURE_INVALID_PARAM unsupported width\n"
    for name,body,accept in (
        ("exact",text,width in (0,33)),
        ("reversed",text.splitlines()[0]+"\n"+text.splitlines()[2]+"\n"+text.splitlines()[1]+"\n",False),
        ("extra-fatal",text+"** Fatal: unrelated\n",False),
        ("duplicate-diagnostic",text+text.splitlines()[1]+"\n",False),
        ("prefixed","\n".join("## "+l for l in text.splitlines())+"\n",False)):
        guards.append({"name":f"guard-{width}-{name}","width":width,"text":body,"expected_accept":accept})
data={"at_utc":datetime.now(timezone.utc).isoformat(),"basis":"independent synthetic protocol fixtures, not simulation results",
      "normal":cases,"guard":guards,"source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
p=E/"RUNNER_PROBES_FREEZE.json"
with p.open("x",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=2)
print(json.dumps({"path":str(p),"normal":len(cases),"guard":len(guards),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}))
