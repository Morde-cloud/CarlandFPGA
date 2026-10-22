import argparse,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
O=Path(__file__).parent;W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args()
sha=lambda b:hashlib.sha256(b).hexdigest()
before=json.loads((O/'tracked-before.json').read_bytes());changes=[]
for rel,h in before.items():
    f=W/rel;current=sha(f.read_bytes()) if f.is_file() else None
    if current!=h:changes.append({'path':rel,'before':h,'after':current})
new=set(subprocess.check_output(['git','-c','core.longpaths=true','ls-files','--others','--exclude-standard','-z'],cwd=W).decode().split('\0'))-set(json.loads((O/'untracked-before.json').read_bytes()))-{''}
c=json.loads((O/'CONSUMED.json').read_bytes());owned=[Path(p).resolve() for p in c['author_ownership']+c['main_ownership']]
bad=[p for p in sorted(new) if not any((W/p).resolve()==q or (W/p).resolve().is_relative_to(q) for q in owned)]
protected=sha((W/'handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json').read_bytes())
r={'at_utc':datetime.now(timezone.utc).isoformat(),'old_tracked_count':len(before),'changes':changes,'unexpected_new_untracked':bad,'new_untracked_count':len(new),'protected_sha256':protected}
out=O/(a.name+'.json')
with out.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2);f.write('\n')
assert len(changes)==1 and changes[0]['path']=='competition/deepeye/tools/acquisition/run_sample_scan_capture.py'
assert not bad and protected=='6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8'
print(json.dumps({'receipt':str(out),'sha256':sha(out.read_bytes()),'old_tracked':len(before),'expected_runner_change':changes,'new_untracked':len(new)}))
