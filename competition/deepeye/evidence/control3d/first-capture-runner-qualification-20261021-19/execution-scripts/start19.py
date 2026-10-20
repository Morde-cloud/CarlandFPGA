from pathlib import Path
from datetime import datetime,timezone
import asyncio,hashlib,json,subprocess
from fpga_mesh.child_control import LocalControlFileClient
from fpga_mesh.project_cli import discovery
R=Path("D:/pynq/CarlandFPGA");O=Path(__file__).resolve().parent
W=R/".local/worktrees/deepeye-implementation-20261014"
C=R/".local/deployment/node-b/evidence/main-continuation-20261019-v1/first-capture-deadline-20261021-18/completed-review"
EP="competition/deepeye/evidence/control3d/first-capture-runner-qualification-20261021-19"
OP="B-DEEPEYE-FIRST-CAPTURE-RUNNER-QUALIFICATION-20261021-19"
WORK="B-FIRST-CAPTURE-RUNNER-QUALIFICATION-20261021-19-v1"
sha=lambda b:hashlib.sha256(b).hexdigest()
def put(p,v):
    with p.open("x",encoding="utf-8") as f:json.dump(v,f,ensure_ascii=False,indent=2)
def git(*a):return subprocess.check_output(["git","-c","core.longpaths=true","-C",str(W),*a])
assert not (O/"STARTED.json").exists()
pins={"COMPLETED_REVIEW_DECISION.json":"67413ae196d9bd528e5ccea7c5d01a948829be30d280b1f42e188a5a1fc1305b",
 "COMPLETED_REVIEW_CONSUMED.json":"b473402f3242593f4d11d9b4bb0cd0373a4b746f415f606ca6a7c8b9c9cbd88c",
 "REVIEW_FINDINGS.md":"1f109493aa55f4e7a58beee05c18ed9dab69625b081275e61041500a56e23fc6",
 "RUNNER_REPAIR_AUTHORIZATION.txt":"8ebed426ec2fd054924bc7d450108b2598503847a2e05875bf44861d1d971d65"}
for n,h in pins.items():assert sha((C/n).read_bytes())==h
d=json.loads((C/"COMPLETED_REVIEW_DECISION.json").read_bytes())
assert d["decision"]=="REVISE" and d["new_product_operation"]==OP
assert git("rev-parse","HEAD").decode().strip()==d["head"]
runner="competition/deepeye/tools/control3d/run_first_capture_deadline.py"
test="competition/deepeye/tests/control/test_first_capture_deadline_runner.py"
assert sha((W/runner).read_bytes())=="a78779ae94f72f183eedfb994a8d6f645258d3289881ec2511cf5afe5143d9eb"
assert not (W/EP).exists() and not (W/"handoffs/b"/OP).exists()
async def audit():
    c=LocalControlFileClient(discovery(R));h=await c.call("health",{});s=await c.call("status",{})
    assert h["node_id"]=="B"
    active=[j for j in s["jobs"] if not j["terminal"]]
    same=[j for j in s["jobs"] if j.get("work_id")==WORK]
    # No product workers are needed or authorized for this narrow main repair.
    assert not active and not same
    put(O/"OWNERSHIP_AUDIT.json",{"node_id":"B","active":[],"matching_work":[],"pool":s["pool"],"new_jobs":0})
asyncio.run(audit())
raw=git("show","f5989cd5defce561f9ba98e6b18fc2682945f0a2:docs/competition/deepeye-2026/immutable_scope.json")
contract=json.loads(raw)
req=sha(json.dumps(contract["requirements"],ensure_ascii=False,sort_keys=True,separators=(",",":")).encode())
assert req=="c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
tracked={p:sha((W/p).read_bytes()) for p in git("ls-files","-z").decode().split("\0") if p and (W/p).is_file()}
assert tracked["handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json"]=="6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8"
assert not git("diff","--cached","--name-only").strip()
put(O/"TRACKED_BEFORE.json",tracked)
turns=[]
for p in Path("C:/Users/15378/.codex/sessions").rglob("*01a13b55-095b-7461-8dd5-5476a130bd82*.jsonl"):
 for line in p.open(encoding="utf-8"):
  try:x=json.loads(line)
  except ValueError:continue
  if x.get("type")=="turn_context":
   v=x["payload"];turns.append(dict(timestamp=x["timestamp"],**{k:v.get(k) for k in ("turn_id","model","effort")}))
turn=sorted(turns,key=lambda x:x["timestamp"])[-1]
assert turn["model"]=="gpt-6-astra" and turn["effort"]=="ultra"
E=W/EP;(E/"inputs").mkdir(parents=True,exist_ok=False)
(E/"inputs/immutable_scope.json").write_bytes(raw)
selected=list(pins)+["PARSER_CASES_FROZEN.json","PARSER_PROBE_RESULT.json","PARSER_PROBE_COMMAND.json",
 "AGGREGATION_CASES_FROZEN.json","AGGREGATION_PROBE_RESULT.json","AGGREGATION_PROBE_COMMAND.json",
 "probe_runner_independent.py","probe_aggregation.py","parser-probe.stdout.txt","parser-probe.stderr.txt",
 "aggregation-probe.stdout.txt","aggregation-probe.stderr.txt","runner_final_snapshot.py"]
consumed=json.loads((C/"COMPLETED_REVIEW_CONSUMED.json").read_bytes())
known={Path(r["path"]).name:r["sha256"] for r in consumed["review_references"]}
inputs=[]
for n in selected:
 b=(C/n).read_bytes()
 if n in known:assert sha(b)==known[n],n
 (E/"inputs"/n).write_bytes(b)
 inputs.append({"source":str(C/n),"path":(E/"inputs"/n).relative_to(W).as_posix(),"sha256":sha(b),"pinned":n in pins or n in known})
for directory in ("parser-cases","aggregation-cases"):
 for p in sorted((C/directory).rglob("*")):
  if p.is_file():
   target=E/"inputs"/p.relative_to(C);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
   inputs.append({"source":str(p),"path":target.relative_to(W).as_posix(),"sha256":sha(p.read_bytes()),"pinned":False})
put(E/"inputs/SOURCE_INDEX.json",inputs)
(E/"inputs/original_test.py").write_bytes((W/test).read_bytes())
put(O/"STARTED.json",{"at_utc":datetime.now(timezone.utc).isoformat(),"task_id":"DEEPEYE-IMPLEMENTATION-20261014","task_version":1,
 "work_id":"B-FIRST-CAPTURE-DEADLINE-RUNNER-REVISE-20261021-19-v1","main_execution_work":WORK,"operation_id":OP,
 "instruction_operation":"B-FIRST-CAPTURE-DEADLINE-RUNNER-REVISE-20261021-19-DIRECTOR",
 "result_event":"B-FIRST-CAPTURE-RUNNER-QUALIFICATION-20261021-19-RESULT-v1",
 "thread_id":"01a13b55-095b-7461-8dd5-5476a130bd82","actual_turn":turn,"baseline":d["head"],"decision":"REVISE","decision_pins":pins,
 "ownership":[runner,test,EP+"/","handoffs/b/"+OP+"/"],"private_ownership":str(O),"new_workers":0,
 "requirements_sha256":req,"requirement_ids":[r["id"] for r in contract["requirements"]],"contract_pin":"f5989cd5defce561f9ba98e6b18fc2682945f0a2","design":"1011259415a0916054eb580687612580bc1e5f09",
 "expectations":"Freeze exact coordinator43+4 and supplemental accounting/outcome expectations before runner edits. Existing Python/new regression/portable runs only;21historical logs read-only. No simulator, vendor tool, old RTL/oracle/vector/manifest change.",
 "return_target":"01a154de-abd8-7590-b9a3-2819249458e3"})
print(json.dumps({"actual_turn":turn,"tracked_files":len(tracked),"input_files":len(inputs),"requirements_sha256":req,"status":"consumed_scope_recorded_no_code_change"}))
