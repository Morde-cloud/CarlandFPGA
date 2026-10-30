"""Finite software-only child modes. No vendor, network or board code."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['benign','nested_host','leaf','exit7','writer','sleeper'],required=True)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--owned',type=Path,required=True);p.add_argument('--windows',type=Path,required=True)
    a=p.parse_args()
    if a.mode in ('benign','exit7','writer','sleeper'):a.build.mkdir(parents=True,exist_ok=False)
    print('SOFTWARE_ONLY_CHILD107 '+a.mode,flush=True)
    if a.mode=='benign':
        argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--mode','nested_host','--build',str(a.build),'--owned',str(a.owned),'--windows',str(a.windows)]
        subprocess.Popen(argv,stdin=subprocess.DEVNULL,shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+4.
        while not (a.build/'leaf_ready.txt').exists():
            if time.monotonic()>=deadline:raise TimeoutError('finite nested-leaf ready wait')
            time.sleep(.01)
        print('OUTER_LAUNCHER_EXIT0_WHILE_NESTED_LEAF_LIVE',flush=True);return 0
    if a.mode=='nested_host':
        assert hashlib.sha256(a.owned.read_bytes()).hexdigest()=='1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692'
        spec=importlib.util.spec_from_file_location('pinned_inner_owned',a.owned);owned=importlib.util.module_from_spec(spec);spec.loader.exec_module(owned)
        folder=a.build/'inner_job';folder.mkdir()
        argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--mode','leaf','--build',str(a.build),'--owned',str(a.owned),'--windows',str(a.windows)]
        result=owned.run_owned(argv,folder,5.,a.windows,job_drain_seconds=.5,job_terminate_seconds=.5)
        (a.build/'INNER_RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        return 0 if result.get('exit_code')==0 and result.get('job_terminal_confirmed') and result.get('job_closed') else 9
    if a.mode=='leaf':
        (a.build/'leaf_ready.txt').write_text('SOFTWARE_ONLY_NESTED_LEAF_READY',encoding='ascii');time.sleep(.8);return 0
    if a.mode=='exit7':return 7
    if a.mode=='writer':
        for _ in range(16):sys.stdout.buffer.write(b'x'*131072);sys.stdout.buffer.flush();time.sleep(.05)
        return 0  # At most2MiB; no unbounded writer.
    if a.mode=='sleeper':time.sleep(10.);return 0


if __name__=='__main__':raise SystemExit(main())
