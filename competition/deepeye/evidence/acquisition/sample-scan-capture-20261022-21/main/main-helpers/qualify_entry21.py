import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014';M=W/'competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/main'
p=argparse.ArgumentParser();p.add_argument('--runner',required=True);p.add_argument('--name',required=True);a=p.parse_args();d=M/a.name;d.mkdir(exist_ok=False)
runner=Path(a.runner).resolve();helper=M/'entry_probe.py';records=[]
for scenario,expected in [('good',0),('sim-error',1),('compile-error',1),('sim-exit',1),('timeout',1),('guard-substring',1),('mixed-selection',1),('duplicate-selection',2)]:
    argv=[sys.executable,'-B','-X','utf8',str(helper),'--runner',str(runner),'--scenario',scenario,'--out',str(d/scenario)]
    t=time.monotonic();rec={'scenario':scenario,'argv':argv,'cwd':str(d),'started':datetime.now(timezone.utc).isoformat(),'expected_exit':expected,'runner_sha256':hashlib.sha256(runner.read_bytes()).hexdigest(),'helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest()}
    proc=subprocess.Popen(argv,cwd=d,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000);stdout,stderr=proc.communicate(timeout=60)
    (d/(scenario+'.stdout.txt')).write_bytes(stdout);(d/(scenario+'.stderr.txt')).write_bytes(stderr)
    rec.update(pid=proc.pid,exit_code=proc.returncode,elapsed_seconds=time.monotonic()-t,stdout_sha256=hashlib.sha256(stdout).hexdigest(),stderr_sha256=hashlib.sha256(stderr).hexdigest());records.append(rec)
    with (d/(scenario+'.process.json')).open('x',encoding='utf-8') as f:json.dump(rec,f,indent=2);f.write('\n')
    assert proc.returncode==expected,(scenario,proc.returncode,stdout,stderr)
with (d/'RESULT.json').open('x',encoding='utf-8') as f:json.dump({'scope':'eight real Python entrypoint processes, synthetic vendor seam; no vendor execution','processes':records},f,indent=2);f.write('\n')
print(json.dumps({'processes':len(records),'exit_codes':[r['exit_code'] for r in records],'scope':'Python processes only; synthetic vendor seam'}))
