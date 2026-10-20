"""Four controlled RTL alterations tested against main's pre-author vectors."""
from pathlib import Path
import hashlib,json,re,subprocess
from datetime import datetime,timezone
O=Path(__file__).resolve().parent
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
P=Path("D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe")
E=W/"competition/deepeye/evidence/control3d/first-capture-deadline-20261021/main"
src=E/"check-01/sources/deepeye_first_capture_deadline.sv"
base=src.read_text(encoding="utf-8")
assert hashlib.sha256(src.read_bytes()).hexdigest()==json.loads((E/"check-01/RESULT.json").read_bytes())["source_sha256"]
dest=E/"mutant-sources";dest.mkdir(exist_ok=False)
def replace(a,b):
    assert base.count(a)==1,a
    return base.replace(a,b)
edits={
 "off-by-one":replace("remaining_q       <= budget_cycles - 1'b1;","remaining_q       <= budget_cycles;"),
 "cancel-ignored":replace("if (rst || cancel) begin","if (rst) begin"),
 "late-revival":replace("// RETAIN_TERMINAL_STATE","""// Main mutation: revive an expired request without a fresh start.
                if (expired_q && observed) begin
                    expired_q <= 1'b0;
                    completed_q <= 1'b1;
                    completed_event_q <= 1'b1;
                end
                // RETAIN_TERMINAL_STATE"""),
}
pattern=r"if \(start\) begin\n\s*// WAIT_DUPLICATE_START_REJECT.*?end else if \(observed\) begin"
edits["renewal"],n=re.subn(pattern,"""if (start) begin
                waiting_q <= 1'b1;
                invalid_request_q <= 1'b0;
                remaining_q <= budget_cycles - 1'b1;
            end else if (observed) begin""",base,count=1,flags=re.S)
assert n==1
manifest={"at_utc":datetime.now(timezone.utc).isoformat(),"source_sha256":hashlib.sha256(src.read_bytes()).hexdigest(),"files":{}}
for name,text in edits.items():
    path=dest/(name+".sv")
    with path.open("x",encoding="utf-8",newline="\n") as f:f.write(text)
    manifest["files"][name]={"path":str(path.relative_to(W)),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
with (dest/"FROZEN.json").open("x",encoding="utf-8") as f:json.dump(manifest,f,indent=2)
results=[]
for name in edits:
    p=subprocess.run([str(P),"-B","-X","utf8",str(O/"run_main18.py"),"mutant-"+name,str(dest/(name+".sv"))],cwd=W,capture_output=True,creationflags=0x08000000)
    (dest/(name+".outer.stdout.txt")).write_bytes(p.stdout)
    (dest/(name+".outer.stderr.txt")).write_bytes(p.stderr)
    r=json.loads((E/("mutant-"+name)/"RESULT.json").read_bytes())
    cmds=json.loads((E/("mutant-"+name)/"COMMANDS.json").read_bytes())
    assert p.returncode==1 and r["status"]=="FAIL"
    assert len(cmds)==3 and all(c["exit_code"]==0 and not c["timeout"] for c in cmds)
    first=r["results"]["standalone-w1"]
    assert first["mismatches"]>0 and first["rows"]==1847
    results.append({"name":name,"numeric_mismatches":first["mismatches"],"first_mismatches":first["first_mismatches"],"actual_commands":3,"sim_exit":0,"oracle_exit":1})
with (dest/"RESULT.json").open("x",encoding="utf-8") as f:json.dump({"status":"PASS","mutants":results,"basis":"real independently compiled RTL; numeric public-port mismatch, no compile/X/error substitution"},f,indent=2)
print(json.dumps({"status":"PASS","mutants":[{"name":r["name"],"numeric_mismatches":r["numeric_mismatches"]} for r in results]}))
