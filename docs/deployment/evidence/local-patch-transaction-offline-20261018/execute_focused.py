import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OUT=Path(__file__).resolve().parent
run_id,suite,*cases=sys.argv[1:]
assert run_id.replace('-','').isalnum() and suite in ('worker','independent','both','targeted')
command=[sys.executable,'-I','-B','-X','utf8',str(OUT/'run_focused_tests.py'),'--run',run_id,'--suite',suite]
for case in cases:command+=['--case',case]
record={'command':command,'cwd':'D:/pynq/CarlandFPGA/.local/worktrees/runtime-continuity-20261016','started_at':datetime.now(timezone.utc).isoformat(),'suite':suite}
start=time.monotonic()
with (OUT/(run_id+'.stdout.txt')).open('xb') as stdout,(OUT/(run_id+'.stderr.txt')).open('xb') as stderr:
    try:
        p=subprocess.run(command,cwd=record['cwd'],env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),stdout=stdout,stderr=stderr,timeout=180)
        record.update(exit_code=p.returncode,timed_out=False)
    except subprocess.TimeoutExpired:
        record.update(exit_code=None,timed_out=True)
record['elapsed_seconds']=round(time.monotonic()-start,3)
record['finished_at']=datetime.now(timezone.utc).isoformat()
with (OUT/(run_id+'.command.json')).open('xb') as f:f.write((json.dumps(record,indent=2)+'\n').encode())
print(json.dumps(record,indent=2))
raise SystemExit(record['exit_code'] if record['exit_code'] is not None else 124)
