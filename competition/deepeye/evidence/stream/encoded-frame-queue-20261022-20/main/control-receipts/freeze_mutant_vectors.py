from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
E=W/"competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20/main"
s=importlib.util.spec_from_file_location("independent_queue",E/"independent_model.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
D=E/"mutants";D.mkdir(exist_ok=False)
v=m.Vectors(D,32);v.phase="early_metadata_visibility_and_cancel_invalidation"
v.admit(4,tag=0xACED);v.step(iv=1,data=73)
v.idle(5,mr=0,ready=1)
v.cancel()
v.admit(3,tag=0x8123);v.feed(3,seed=3);v.step(mr=1);v.step(ready=1)
v.cancel()
v.admit(0,error=3,tag=0xACED);v.drain()
v.admit(2,tag=0x8123);v.feed(2,seed=201);v.drain()
r=v.close()
f={"at_utc":datetime.now(timezone.utc).isoformat(),"author_RTL_read":False,
   "choices":["publish success descriptor before complete byte sealing","ignore cancellation control invalidation while keeping abort gating"],
   "criteria":"Isolated actual compiled RTL variants; concrete numeric post-reset public-port mismatches with tool exits0; compile/X/parser/timeout are not behavioral kills.",
   "vectors":r,"files":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in D.iterdir() if p.is_file()}}
with (E/"MUTATION_PLAN.json").open("x",encoding="utf-8") as out:json.dump(f,out,indent=2)
print(json.dumps({"edges":r["edges"],"plan_sha256":hashlib.sha256((E/"MUTATION_PLAN.json").read_bytes()).hexdigest()}))
