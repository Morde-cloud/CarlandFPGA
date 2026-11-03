"""One offline control run, guarded by the quality main's explicit freeze.

--freeze is JSON {"files": {"repo/relative/path": "sha256", ...}}.
No hardware, simulator binary, network, or native application is used.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[3]
PRIVATE=REPO/'.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-88/follower-tests'
REQUIRED={f'output/drill-live-link-20261104/drill_live_link/{x}.py' for x in ('__init__','model','follower','session_client')}


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',required=True);ap.add_argument('--run-id',required=True)
    args=ap.parse_args()
    if not args.run_id.replace('-','').isalnum():raise ValueError('plain unique run ID required')
    freeze_path=Path(args.freeze).resolve();freeze=json.loads(freeze_path.read_text(encoding='utf-8-sig'))
    pins=freeze['files']
    if not REQUIRED.issubset(pins):raise ValueError('freeze must pin all four package sources')
    for name,expected in pins.items():
        p=(REPO/name).resolve()
        if not p.is_relative_to(REPO) or digest(p)!=expected:raise ValueError('freeze mismatch: '+name)
    out=PRIVATE/args.run_id;out.mkdir(parents=True,exist_ok=False)
    command=[sys.executable,'-B','-X','utf8',str(Path(__file__).with_name('test_follow_controls.py'))]
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    proc=subprocess.run(command,cwd=REPO,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
    (out/'stdout.txt').write_bytes(proc.stdout);(out/'stderr.txt').write_bytes(proc.stderr)
    after={name:digest(REPO/name) for name in pins}
    record={'run_id':args.run_id,'started_utc':started,'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'argv':command,'cwd':str(REPO),'python':sys.version,'exit_code':proc.returncode,
            'freeze_path':str(freeze_path),'freeze_sha256':digest(freeze_path),'source_before':pins,'source_after':after,
            'frozen_sources_unchanged':after==pins,'test_sha256':digest(Path(__file__).with_name('test_follow_controls.py')),
            'stdout_sha256':digest(out/'stdout.txt'),'stderr_sha256':digest(out/'stderr.txt'),
            'requirements_revision':2,'requirements_ids':[f'H{i:02d}' for i in range(1,16)],
            'requirements_sha256':'2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d',
            'scope':'synthetic offline controls only; no hardware, physical acceptance, FPGA or RPM measurement'}
    (out/'RUN.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False,indent=2))
    sys.stdout.buffer.write(proc.stdout);sys.stderr.buffer.write(proc.stderr)
    return proc.returncode if after==pins else 125


if __name__=='__main__':sys.exit(main())
