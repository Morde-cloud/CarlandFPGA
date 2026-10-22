"""Read-only comparison to pre-author tracked bytes and exact write ownership."""
import argparse,gzip,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014';O=Path(__file__).parent
E=W/'competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21'
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args();target=O/(a.name+'.json');assert not target.exists()
    before=json.loads((O/'tracked-before.json').read_bytes());c=json.loads((O/'CONSUMED.json').read_bytes());changes=[]
    for name,h in before.items():
        f=W/name;current=sha(f.read_bytes()) if f.is_file() else None
        if current!=h:changes.append({'path':name,'before':h,'after':current})
    raw=subprocess.check_output(['git','-c','core.longpaths=true','ls-files','--others','--exclude-standard','-z'],cwd=W)
    new={s.decode() for s in raw.split(b'\0') if s}-set(json.loads((O/'untracked-before.json').read_bytes()))
    ownership=[(W/p).resolve() for p in c['new_product_paths_absent']]
    bad=[p for p in sorted(new) if not any((W/p).resolve()==own or (W/p).resolve().is_relative_to(own) for own in ownership)]
    envelopes=[]
    for f in E.rglob('trace.txt.gz'):
        raw=gzip.decompress(f.read_bytes());assert f.with_suffix('').read_bytes()==raw
        envelopes.append({'path':f.relative_to(W).as_posix(),'raw_sha256':sha(raw),'raw_bytes':len(raw),'gzip_sha256':sha(f.read_bytes())})
    d={'at_utc':datetime.now(timezone.utc).isoformat(),'old_tracked_count':len(before),'old_tracked_changes':changes,'new_untracked_count':len(new),'unexpected_new_untracked':bad,'trace_envelopes':envelopes,'protected_sha256':sha((W/'handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json').read_bytes())}
    with target.open('x',encoding='utf-8') as f:json.dump(d,f,indent=2);f.write('\n')
    assert not changes and not bad,d
    assert d['protected_sha256']=='6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8'
    print(json.dumps({'receipt':str(target),'sha256':sha(target.read_bytes()),'old_tracked':len(before),'new_untracked':len(new),'trace_envelopes':len(envelopes)}))
if __name__=='__main__':main()
