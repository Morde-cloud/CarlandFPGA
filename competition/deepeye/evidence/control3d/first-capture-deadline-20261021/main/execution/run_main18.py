"""Run one new independent public-port verification; persist outer receipts."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,subprocess,sys
O=Path(__file__).resolve().parent
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
P=Path("D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe")
E=W/"competition/deepeye/evidence/control3d/first-capture-deadline-20261021/main"
V=W/"competition/deepeye/tools/control3d/main_verify_first_capture_deadline.py"
name=sys.argv[1]
assert name.replace("-","").isalnum()
out=E/name
assert not out.exists()
args=[str(P),"-B","-X","utf8",str(V),"--root",str(W),"--out",str(out)]
if len(sys.argv)>2:args+=["--source",sys.argv[2]]
receipt=E/(name+".command.json")
assert not receipt.exists()
rec={"argv":args,"cwd":str(W),"started_utc":datetime.now(timezone.utc).isoformat(),
     "verifier_sha256":hashlib.sha256(V.read_bytes()).hexdigest(),"status":"running"}
with receipt.open("x",encoding="utf-8") as f:json.dump(rec,f,indent=2)
p=subprocess.run(args,cwd=W,capture_output=True,creationflags=0x08000000)
for key,data in (("stdout",p.stdout),("stderr",p.stderr)):
    with (E/(name+"."+key+".txt")).open("xb") as f:f.write(data)
    rec[key+"_sha256"]=hashlib.sha256(data).hexdigest()
rec.update(status="completed",exit_code=p.returncode,ended_utc=datetime.now(timezone.utc).isoformat())
receipt.write_text(json.dumps(rec,indent=2),encoding="utf-8")
print(json.dumps(rec))
print(p.stdout.decode("utf-8",errors="replace")[-5000:])
print(p.stderr.decode("utf-8",errors="replace")[-5000:])
sys.exit(p.returncode)
