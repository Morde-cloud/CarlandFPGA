"""Capture one bounded Python probe process with its real exit and raw streams."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys
O=Path(__file__).resolve().parent
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
E=W/"competition/deepeye/evidence/control3d/first-capture-runner-qualification-20261021-19"
P=Path("D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe")
name=sys.argv[1];expected=int(sys.argv[2]);assert name.replace("-","").isalnum()
out=E/name;assert not out.exists()
args=[str(P),"-B","-X","utf8",str(E/"verify19.py"),"--root",str(W),"--out",str(out),*sys.argv[3:]]
receipt=E/(name+".command.json")
record={"name":name,"argv":args,"cwd":str(W),"started_utc":datetime.now(timezone.utc).isoformat(),
 "verifier_sha256":hashlib.sha256((E/"verify19.py").read_bytes()).hexdigest(),"expected_exit":expected,"status":"running"}
with receipt.open("x",encoding="utf-8") as f:json.dump(record,f,indent=2)
r=subprocess.run(args,cwd=W,capture_output=True,creationflags=0x08000000)
for stream,data in (("stdout",r.stdout),("stderr",r.stderr)):
 with (E/(name+"."+stream+".txt")).open("xb") as f:f.write(data)
 record[stream+"_sha256"]=hashlib.sha256(data).hexdigest()
record.update(status="completed",exit_code=r.returncode,ended_utc=datetime.now(timezone.utc).isoformat())
receipt.write_text(json.dumps(record,indent=2),encoding="utf-8")
print(json.dumps(record))
print(r.stdout.decode(errors="replace")[-2000:]);print(r.stderr.decode(errors="replace")[-2000:])
assert r.returncode==expected
