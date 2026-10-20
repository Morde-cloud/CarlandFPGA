"""Independent qualification of complete real mutant logs plus negative fixtures."""
from pathlib import Path
import json,hashlib,importlib.util,sys,re
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
E=W/"competition/deepeye/evidence/control3d/first-capture-deadline-20261021"
D=E/"main"/sys.argv[1];D.mkdir(exist_ok=False)
source=W/"competition/deepeye/tools/control3d/run_first_capture_deadline.py"
(D/"runner.py").write_bytes(source.read_bytes())
spec=importlib.util.spec_from_file_location("candidate",D/"runner.py");m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=E/"author/run-mutants-final-01/mutants/deadline-off-by-one/w01/sim.log"
raw=p.read_bytes();base=raw.decode();(D/"saved-real-mutant.log").write_bytes(raw)
lines=base.splitlines(True)
changes=[
 ("real-mutant-control",base,True),
 ("missing-finish","".join(l for l in lines if "DEEPEYE_FC_FINISH" not in l),False),
 ("missing-summary","".join(l for l in lines if "DEEPEYE_FC_SUMMARY" not in l),False),
 ("missing-fatal","".join(l for l in lines if "** Fatal:" not in l),False),
 ("duplicate-summary",base+next(l for l in lines if "DEEPEYE_FC_SUMMARY" in l),False),
 ("load-error",base+"# ** Error: Error loading design\n",False),
 ("extra-unrelated-error",base+"# ** Error: unrelated\n",False),
 ("non-numeric-X",base.replace("waiting dut=1 ref=0","waiting dut=x ref=0",1),False),
 ("false-counterexample",base.replace("waiting dut=1 ref=0","waiting dut=0 ref=0",1),False),
 ("wrong-fatal-count",base.replace("BEHAVIOR_FAIL width=1 failures=1623","BEHAVIOR_FAIL width=1 failures=1624"),False),
 ("wrong-summary-count",base.replace("checks=59688 failures=1623","checks=59688 failures=1624"),False),
 ("duplicate-finish",base+next(l for l in lines if "DEEPEYE_FC_FINISH" in l),False),
 ("prefixed-checks",base.replace("# DEEPEYE_FC_CHECK_FAIL","# BAD_DEEPEYE_FC_CHECK_FAIL"),False),
 ("empty-check-record","DEEPEYE_FC_RUN width=1 kind=standalone\nDEEPEYE_FC_CHECK_FAIL nonsense\n",False),
]
frozen={"source_log_sha256":hashlib.sha256(raw).hexdigest(),"expected":[{"name":n,"text_sha256":hashlib.sha256(t.encode()).hexdigest(),"accept":e} for n,t,e in changes]}
(D/"EXPECTED.json").write_text(json.dumps(frozen,indent=2),encoding="utf-8")
rows=[]
for name,text,expected in changes:
 try:actual,parsed,reasons=m.parse_mutant_log(text,1)
 except Exception as e:actual=False;reasons=[repr(e)]
 rows.append({"name":name,"expected":expected,"actual":actual,"matches":expected==actual,"reasons":reasons})
result={"status":"PASS" if all(r["matches"] for r in rows) else "FAIL","source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"cases":len(rows),"rows":rows}
(D/"RESULT.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result))
