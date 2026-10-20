"""Actual Python regressions/portable runs and read-only historical log replay."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,importlib.util,json,subprocess
O=Path(__file__).resolve().parent
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
E=W/"competition/deepeye/evidence/control3d/first-capture-runner-qualification-20261021-19"
OLD=W/"competition/deepeye/evidence/control3d/first-capture-deadline-20261021"
D=E/"final-checks";D.mkdir(exist_ok=False)
P=Path("D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe")
R="competition/deepeye/tools/control3d/run_first_capture_deadline.py"
T="competition/deepeye/tests/control/test_first_capture_deadline_runner.py"
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
records=[]
def command(name,args,cwd,expected=0):
    start=datetime.now(timezone.utc).isoformat()
    p=subprocess.run(list(map(str,args)),cwd=cwd,capture_output=True,creationflags=0x08000000,timeout=60)
    (D/(name+".stdout.txt")).write_bytes(p.stdout);(D/(name+".stderr.txt")).write_bytes(p.stderr)
    record={"name":name,"argv":list(map(str,args)),"cwd":str(cwd),"started_utc":start,"ended_utc":datetime.now(timezone.utc).isoformat(),
        "exit_code":p.returncode,"expected_exit":expected,"stdout_sha256":hashlib.sha256(p.stdout).hexdigest(),"stderr_sha256":hashlib.sha256(p.stderr).hexdigest()}
    records.append(record);(D/"COMMANDS.json").write_text(json.dumps(records,indent=2),encoding="utf-8")
    assert p.returncode==expected,(name,p.stderr.decode()[-5000:])
    return p
def methods(p):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(p.read_text())) if isinstance(n,ast.FunctionDef) and n.name.startswith("test_")}
old=methods(E/"inputs/original_test.py");current=methods(W/T)
assert len(old)==33 and len(current)==45 and all(current[n]==v for n,v in old.items())
command("python-version",[P,"--version"],W)
command("unit",[P,"-B","-X","utf8",W/T,"-v"],W)
for folder,original in (("portable",False),("original33",True)):
    target=D/folder
    for path in (R,T):
        dest=target/path;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes((E/"inputs/original_test.py" if original and path==T else W/path).read_bytes())
    command(folder,[P,"-B","-X","utf8",target/T,"-v"],target)
spec=importlib.util.spec_from_file_location("fixed_runner",W/R);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
historical=[]
for folder in ("run-normal-final-01","run-mutants-final-01"):
    path=OLD/"author"/folder/"RUN_MANIFEST.json";manifest=json.loads(path.read_bytes())
    rows=manifest["normal"] or [r for g in manifest["mutants"] for r in g["records"]]
    for row in rows:
        sim=row["sim"];log=Path(sim["log"]);assert sha(log)==sim["log_sha256"]
        text=log.read_text();kind=row.get("kind","mutant");width=row.get("generic_value",row.get("width"))
        if kind=="guard":value=m.qualify_guard_log(text,width,sim["exit_code"],sim["timed_out"])
        elif kind=="mutant":value=m.qualify_mutant_log(text,width,sim["exit_code"],sim["timed_out"])
        else:value=m.qualify_normal_log(text,width,kind,{"trace"} if kind=="composition" else {"prefix"} if width==32 else m.SMALL_GROUPS,sim["exit_code"],sim["timed_out"])
        assert value[0],(kind,width,value[2][:10])
        historical.append({"path":str(log.relative_to(W)),"sha256":sha(log),"bytes":log.stat().st_size,"kind":kind,"width":width,
                           "accepted":value[0],"parsed":value[1],"evidence_kind":"read-only historical log reclassification; no new simulation"})
assert len(historical)==21
(D/"HISTORICAL_RECLASSIFICATION.json").write_text(json.dumps(historical,indent=2),encoding="utf-8")
cli=[("all-targets",0),("one-survivor",0),("all-survivors",1),("w2-foreign_error",1),
     ("w2-abnormal_exit",1),("w2-timeout",1),("w2-missing_finish",1),("w2-missing_file",1)]
cli_records=[]
for i,(name,expected) in enumerate(cli):
    label=f"cli-{i:02d}"
    command(label,[P,"-B","-X","utf8",O/"run19.py",label,str(expected),"--cli",name],W)
    receipt=json.loads((E/(label+".command.json")).read_bytes())
    result=json.loads((E/label/"CLI_RESULT.json").read_bytes())
    assert receipt["exit_code"]==result["actual_entrypoint_return"]==expected
    assert result["vendor_invocations"]==0 and not result["blocked_process_network_attempts"]
    cli_records.append({"name":name,"actual_exit":expected,"synthetic_tool_seam":True,"receipt":str((E/(label+".command.json")).relative_to(W))})
result={"status":"PASS","runner_sha256":sha(W/R),"test_sha256":sha(W/T),"unit_methods":45,"portable_methods":45,
        "original_methods_unchanged_and_run":33,"historical_author_logs":21,"cli_cases":cli_records,"new_ModelSim_invocations":0,
        "new_Vivado_invocations":0,"new_RTL_cases":0}
(D/"RESULT.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result))
