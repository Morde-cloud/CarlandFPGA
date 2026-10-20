"""Bounded post-review tests, real-log classification and source-bound runner run."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,importlib.util,json,subprocess
O=Path(__file__).resolve().parent
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
P=Path("D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe")
E=W/"competition/deepeye/evidence/control3d/first-capture-deadline-20261021"
D=E/"main/final-checks";D.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
runner_rel="competition/deepeye/tools/control3d/run_first_capture_deadline.py"
test_rel="competition/deepeye/tests/control/test_first_capture_deadline_runner.py"
runner=W/runner_rel;test=W/test_rel;records=[]
def command(name,args,cwd,expected=0):
    start=datetime.now(timezone.utc).isoformat()
    p=subprocess.run(list(map(str,args)),cwd=cwd,capture_output=True,creationflags=0x08000000)
    (D/(name+".stdout.txt")).write_bytes(p.stdout);(D/(name+".stderr.txt")).write_bytes(p.stderr)
    r={"name":name,"argv":list(map(str,args)),"cwd":str(cwd),"started_utc":start,"ended_utc":datetime.now(timezone.utc).isoformat(),
       "exit_code":p.returncode,"expected_exit":expected,"stdout_sha256":hashlib.sha256(p.stdout).hexdigest(),"stderr_sha256":hashlib.sha256(p.stderr).hexdigest()}
    records.append(r);(D/"COMMANDS.json").write_text(json.dumps(records,indent=2),encoding="utf-8")
    assert p.returncode==expected,(name,p.stderr.decode()[-5000:])
    return p
def methods(path):
    return {node.name:ast.dump(node,include_attributes=False) for node in ast.walk(ast.parse(path.read_text())) if isinstance(node,ast.FunctionDef) and node.name.startswith("test_")}
old=methods(E/"main/takeover/test_first_capture_deadline_runner.py");new=methods(test)
unchanged=[n for n in old if old[n]==new.get(n)]
assert len(old)==24 and len(new)==33 and len(unchanged)==23
command("unit",[P,"-B","-X","utf8",test,"-v"],W)
portable=D/"portable"
for path in (runner_rel,test_rel):
    dst=portable/path;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes((W/path).read_bytes())
command("portable",[P,"-B","-X","utf8",portable/test_rel,"-v"],portable)
spec=importlib.util.spec_from_file_location("reviewed_runner",runner);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
classified=[];inputs=[]
for folder in ("run-normal-final-01","run-mutants-final-01"):
    manifest=E/"author"/folder/"RUN_MANIFEST.json"
    data=json.loads(manifest.read_bytes())
    for s in data["sources"]:
        snapshot=Path(s["snapshot"])
        assert sha(snapshot)==s["snapshot_sha256"]==s["sha256"]
        inputs.append({"path":str(snapshot.relative_to(W)),"sha256":sha(snapshot)})
    rows=data["normal"] if data["normal"] else [r for item in data["mutants"] for r in item["records"]]
    for r in rows:
        for stage in ("vlib","vlog"):
            c=r["compile"][stage];assert c["exit_code"]==0 and not c["timed_out"]
            assert sha(Path(c["log"]))==c["log_sha256"]
        sim=r["sim"];path=Path(sim["log"]);assert sha(path)==sim["log_sha256"]
        text=path.read_text();kind=r.get("kind","mutant");width=r.get("generic_value",r.get("width"))
        if kind=="guard":ok,parsed,reasons=m.qualify_guard_log(text,width,sim["exit_code"],sim["timed_out"])
        elif kind=="mutant":ok,parsed,reasons=m.qualify_mutant_log(text,width,sim["exit_code"],sim["timed_out"])
        else:
            groups={"trace"} if kind=="composition" else {"prefix"} if width==32 else m.SMALL_GROUPS
            ok,parsed,reasons=m.qualify_normal_log(text,width,kind,groups,sim["exit_code"],sim["timed_out"])
        assert ok,(folder,r.get("case_id",r.get("mutant")),reasons[:10])
        classified.append({"kind":kind,"width":width,"log":str(path.relative_to(W)),"sha256":sha(path),"parsed":parsed})
(D/"SAVED_AUTHOR_RECLASSIFICATION.json").write_text(json.dumps({"cases":classified,"input_snapshots":inputs},indent=2),encoding="utf-8")
# A new bounded execution qualifies the changed snapshot/selection runner path.
command("runner-real",[P,"-B","-X","utf8",runner,"--mode","normal","--source-root",W,
                      "--run-root",D/"runner-real","--only","standalone-w01","guard-w00","guard-w33"],W)
live=json.loads((D/"runner-real/RUN_MANIFEST.json").read_bytes())
assert live["ok"] and len(live["normal"])==3
for row in live["normal"]:
    assert all("execution-inputs" in s for s in row["compile"]["vlog"]["argv"][4:])
    assert row["ok"]
result={"status":"PASS","unit_methods":len(new),"portable_methods":len(new),"original_methods_unchanged":len(unchanged),
        "author_scenarios_reclassified":len(classified),"fresh_runner_cases":3,
        "runner_sha256":sha(runner),"test_sha256":sha(test),"rtl_sha256":sha(W/"competition/deepeye/fpga/control3d/deepeye_first_capture_deadline.sv")}
(D/"RESULT.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result))
