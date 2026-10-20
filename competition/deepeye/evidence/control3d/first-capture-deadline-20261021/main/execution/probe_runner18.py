"""Run frozen independent parser expectations against an exact source snapshot."""
from pathlib import Path
import hashlib,json,importlib.util,sys
O=Path(__file__).resolve().parent
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
E=W/"competition/deepeye/evidence/control3d/first-capture-deadline-20261021/main"
name=sys.argv[1]
assert name.replace("-","").isalnum()
D=E/name;D.mkdir(exist_ok=False)
source=W/"competition/deepeye/tools/control3d/run_first_capture_deadline.py"
data=source.read_bytes();snapshot=D/"runner.py";snapshot.write_bytes(data)
spec=importlib.util.spec_from_file_location("candidate",snapshot);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
frozen=E/"RUNNER_PROBES_FREEZE.json";f=json.loads(frozen.read_bytes());rows=[]
for c in f["normal"]:
    try:
        accept,parsed,reasons=m.parse_normal_log(c["text"],c["width"],c["kind"],set(c["groups"]))
    except Exception as e:accept=False;reasons=[repr(e)]
    rows.append({"name":c["name"],"expected":c["expected_accept"],"actual":accept,"matches":accept==c["expected_accept"],"reasons":reasons})
for c in f["guard"]:
    try:accept,parsed,reasons=m.parse_guard_log(c["text"],c["width"])
    except Exception as e:accept=False;reasons=[repr(e)]
    rows.append({"name":c["name"],"expected":c["expected_accept"],"actual":accept,"matches":accept==c["expected_accept"],"reasons":reasons})
r={"status":"PASS" if all(x["matches"] for x in rows) else "FAIL","cases":len(rows),"mismatches":[x for x in rows if not x["matches"]],
   "source_sha256":hashlib.sha256(data).hexdigest(),"frozen_sha256":hashlib.sha256(frozen.read_bytes()).hexdigest(),"cases_detail":rows}
(D/"RESULT.json").write_text(json.dumps(r,indent=2),encoding="utf-8")
print(json.dumps({k:v for k,v in r.items() if k!="cases_detail"}))
