from pathlib import Path
import datetime,hashlib,json,subprocess,sys
W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
M=W/'competition/deepeye/evidence/control3d/pwm-runner-qualification-20261020-17/main'
name=sys.argv[1];out=M/name;assert not out.exists()
cmd=[sys.executable,'-B','-X','utf8',str(M/'verify17.py'),'--root',str(W),'--out',str(out)]
started=datetime.datetime.now(datetime.timezone.utc).isoformat()
p=subprocess.run(cmd,cwd=W,capture_output=True,timeout=120)
sha=lambda b:hashlib.sha256(b).hexdigest()
with (M/(name+'.stdout.txt')).open('xb') as f:f.write(p.stdout)
with (M/(name+'.stderr.txt')).open('xb') as f:f.write(p.stderr)
with (M/(name+'.command.json')).open('x',encoding='utf-8') as f:json.dump({
 'argv':cmd,'cwd':str(W),'started_utc':started,'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'exit_code':p.returncode,'stdout_sha256':sha(p.stdout),'stderr_sha256':sha(p.stderr),
 'verifier_sha256':sha((M/'verify17.py').read_bytes())},f,indent=2)
print(p.stdout.decode(errors='replace'));print(p.stderr.decode(errors='replace')[-2500:]);sys.exit(p.returncode)
