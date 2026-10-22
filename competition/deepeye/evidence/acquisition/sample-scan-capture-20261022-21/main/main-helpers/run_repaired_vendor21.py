from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys,time
R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014';M=W/'competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/main';O=Path(__file__).parent
D=M/'repaired-vendor-01';D.mkdir(exist_ok=False);S=W/'competition/deepeye/tools/acquisition/run_sample_scan_capture.py';sha=lambda b:hashlib.sha256(b).hexdigest()
argv=[sys.executable,'-B','-X','utf8',str(S),'--root',str(W),'--out',str(D/'results'),'--modelsim','D:/modelsim1/win64']
for c in ['directed','guard_seq_w_1','guard_healthy','mutant_loss_undercount_rejected']:argv+=['--case',c]
r={'argv':argv,'cwd':str(D),'started':datetime.now(timezone.utc).isoformat(),'runner_sha256':sha(S.read_bytes()),'scope':'actual new op21 ModelSim selected dispatch through repaired Python runner; remaining unchanged author27 are reclassified without replay'}
with (D/'PROCESS_INTENT.json').open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
t=time.monotonic();p=subprocess.Popen(argv,cwd=D,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000);stdout,stderr=p.communicate()
(D/'runner.stdout.txt').write_bytes(stdout);(D/'runner.stderr.txt').write_bytes(stderr);r.update(pid=p.pid,exit_code=p.returncode,elapsed_seconds=time.monotonic()-t,ended=datetime.now(timezone.utc).isoformat(),stdout_sha256=sha(stdout),stderr_sha256=sha(stderr))
with (D/'PROCESS.json').open('x',encoding='utf-8') as f:json.dump(r,f,indent=2);f.write('\n')
print(json.dumps(r));print(stdout.decode('utf-8',errors='replace'));print(stderr.decode('utf-8',errors='replace'));sys.exit(p.returncode)
