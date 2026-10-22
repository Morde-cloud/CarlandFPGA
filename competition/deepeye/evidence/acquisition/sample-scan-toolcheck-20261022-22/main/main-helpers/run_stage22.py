"""Save actual Python process receipts for independent op22 software checks."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
O=Path(__file__).parent;W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014');M=W/'competition/deepeye/evidence/acquisition/sample-scan-toolcheck-20261022-22/main'
p=argparse.ArgumentParser();p.add_argument('action',choices=['direct','entries','regression','unit']);a=p.parse_args()
source=W/'competition/deepeye/tools/acquisition/run_sample_scan_capture.py';test=W/'competition/deepeye/tests/acquisition/test_sample_scan_toolcheck.py';base=[sys.executable,'-B','-X','utf8']
if a.action in ['direct','entries']:argv=base+[str(M/'probe22.py'),a.action,'--source',str(source),'--out',str(M/('final-'+('entry' if a.action=='entries' else 'direct')+'-01')),'--root',str(W)]
elif a.action=='regression':argv=base+[str(O/'regression22.py'),'--source',str(source),'--name','regression-01']
else:argv=base+['-m','unittest','discover','-s',str(test.parent),'-p',test.name,'-v']
sha=lambda b:hashlib.sha256(b).hexdigest()
d=M/'main-processes';d.mkdir(exist_ok=True)
intent={'argv':argv,'cwd':str(M),'at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(source.read_bytes()),'test_sha256':sha(test.read_bytes()),'scope':'Python software checks only; no vendor compile/simulation allowed'}
env=os.environ.copy()
if a.action=='unit':
    temp=M/'main-unit-temp';temp.mkdir(exist_ok=False)
    env.update(TMP=str(temp),TEMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1')
    intent['explicit_temp_root']=str(temp)
with (d/(a.action+'.intent.json')).open('x',encoding='utf-8') as f:json.dump(intent,f,indent=2);f.write('\n')
t=time.monotonic();proc=subprocess.Popen(argv,cwd=M,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000);stdout,stderr=proc.communicate(timeout=600)
(d/(a.action+'.stdout.bin')).write_bytes(stdout);(d/(a.action+'.stderr.bin')).write_bytes(stderr)
result={**intent,'pid':proc.pid,'exit':proc.returncode,'elapsed':time.monotonic()-t,'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr),'source_unchanged':sha(source.read_bytes())==intent['source_sha256'],'test_unchanged':sha(test.read_bytes())==intent['test_sha256']}
with (d/(a.action+'.process.json')).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result));print(stdout.decode(errors='replace')[-3000:]);print(stderr.decode(errors='replace')[-3000:]);sys.exit(proc.returncode)
