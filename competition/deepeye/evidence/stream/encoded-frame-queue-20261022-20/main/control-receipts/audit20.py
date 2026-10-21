"""Read-only precommit byte/ownership audit; invoke after terminal author work."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, gzip, hashlib, json, subprocess
R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014'
O=Path(__file__).resolve().parent
E=W/'competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20'
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);a=p.parse_args()
    target=O/(a.name+'.json');assert not target.exists()
    before=json.loads((O/'TRACKED_BEFORE.json').read_bytes())
    changed=[]
    for name,digest in before.items():
        path=W/name
        now=sha(path.read_bytes()) if path.is_file() else None
        if now!=digest:changed.append(dict(path=name,before=digest,after=now))
    raw=subprocess.check_output(['git','-c','core.longpaths=true','-C',str(W),'ls-files','--others','--exclude-standard','-z'])
    untracked={s.decode('utf-8') for s in raw.split(b'\0') if s}
    old_untracked=set(json.loads((O/'UNTRACKED_BEFORE.json').read_bytes()))
    consumed=json.loads((O/'CONSUMED.json').read_bytes())
    owners=[Path(s).resolve() for s in consumed['author_ownership']+consumed['main_ownership']]
    unexpected=[]
    for name in sorted(untracked-old_untracked):
        path=(W/name).resolve()
        if not any(path==owner or path.is_relative_to(owner) for owner in owners):unexpected.append(name)
    envelopes=[]
    for path in E.rglob('trace.txt.gz'):
        packed=path.read_bytes();raw=gzip.decompress(packed)
        original=path.with_suffix('')
        assert original.read_bytes()==raw,path
        envelopes.append(dict(path=path.relative_to(W).as_posix(),gzip_sha256=sha(packed),raw_sha256=sha(raw),raw_bytes=len(raw)))
    record=dict(at_utc=datetime.now(timezone.utc).isoformat(),tracked_count=len(before),tracked_changes=changed,
                unexpected_new_untracked=unexpected,raw_trace_envelopes=envelopes,
                protected_codec_sha256=sha((W/'handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json').read_bytes()))
    target.write_text(json.dumps(record,indent=2),encoding='utf-8')
    assert not changed and not unexpected,record
    assert record['protected_codec_sha256']=='6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8'
    print(json.dumps(dict(status='PASS',tracked_count=len(before),trace_envelopes=len(envelopes),receipt=str(target),sha256=sha(target.read_bytes()))))

if __name__=='__main__':main()
