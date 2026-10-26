"""Run only new collector controls once in a new assigned evidence directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--groups',nargs='+',choices=('stopclock','package','transport','runtime'),required=True);a=p.parse_args()
    repo=a.repo.resolve();out=a.out.resolve();owner=repo/'.local/deployment/node-b/evidence/g05-capture-20261026-59/collector-author'
    assert out.is_relative_to(owner) and out!=owner and not out.exists()
    out.mkdir(parents=True,exist_ok=False);sources=out/'sources';sources.mkdir()
    here=Path(__file__).resolve().parent;pins={}
    for source in sorted(here.glob('*.py')):
        raw=source.read_bytes();(sources/source.name).write_bytes(raw);pins[source.name]=hashlib.sha256(raw).hexdigest()
    cmd=[sys.executable,'-B','-X','utf8',str(sources/'test_author.py'),'--out',str(out/'controls'),
         '--repo',str(repo),'--product',str(repo/'.local/worktrees/deepeye-implementation-20261014/competition/deepeye'),'--groups',*a.groups]
    rec={'argv':cmd,'cwd':str(repo),'source_pins':pins,'started_unix_ns':time.time_ns(),'automatic_retry':False,'timeout_seconds':120}
    (out/'INTENT.json').write_text(json.dumps(rec,indent=2))
    with (out/'stdout.txt').open('xb') as stdout,(out/'stderr.txt').open('xb') as stderr:
        proc=subprocess.Popen(cmd,cwd=repo,stdout=stdout,stderr=stderr,stdin=subprocess.DEVNULL,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        rec['pid']=proc.pid
        try:rec['exit_code']=proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            rec['timed_out']=True;proc.kill();rec['exit_code']=proc.wait(timeout=10)
    rec['finished_unix_ns']=time.time_ns();rec['launcher_exit_confirmed']=proc.poll() is not None
    # Tests launch no background processes; their sole child git show is bounded
    # contract retrieval. No whole-job containment claim is made by this runner.
    for key in ('stdout','stderr'):
        raw=(out/(key+'.txt')).read_bytes();rec[key]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    rec['source_unchanged']=pins=={n:hashlib.sha256((here/n).read_bytes()).hexdigest() for n in pins}
    (out/'PROCESS.json').write_text(json.dumps(rec,indent=2))
    print(json.dumps(rec),flush=True)
    return 0 if rec['exit_code']==0 and rec['source_unchanged'] and not rec.get('timed_out') else 1


if __name__=='__main__':raise SystemExit(main())
