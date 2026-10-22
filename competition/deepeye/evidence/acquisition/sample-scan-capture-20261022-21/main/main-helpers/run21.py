"""Actual hidden Python invocation receipts; fresh names only."""
import argparse,hashlib,json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014';O=Path(__file__).parent
M=W/'competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/main'
S=W/'competition/deepeye/tools/acquisition/main_verify_sample_scan_capture.py'
sha=lambda b:hashlib.sha256(b).hexdigest()
def save(p,d):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(d,f,indent=2);f.write('\n')
def main():
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--case',required=True);p.add_argument('--dut');p.add_argument('--expect-mismatch',action='store_true');a=p.parse_args()
    assert a.name.replace('-','').replace('_','').isalnum()
    argv=[sys.executable,'-B','-X','utf8',str(S),'--root',str(W),'--out',str(M/a.name),'--case',a.case]
    if a.dut:argv+=['--dut',a.dut]
    if a.expect_mismatch:argv+=['--expect-mismatch']
    d={'argv':argv,'cwd':str(O),'source_sha256':sha(S.read_bytes()),'started':datetime.now(timezone.utc).isoformat()};save(O/(a.name+'.intent.json'),d)
    t=time.monotonic();proc=subprocess.Popen(argv,cwd=O,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
    stdout,stderr=proc.communicate();(O/(a.name+'.stdout.txt')).write_bytes(stdout);(O/(a.name+'.stderr.txt')).write_bytes(stderr)
    d.update(pid=proc.pid,exit_code=proc.returncode,elapsed_seconds=time.monotonic()-t,ended=datetime.now(timezone.utc).isoformat(),stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),source_after_sha256=sha(S.read_bytes()))
    save(O/(a.name+'.process.json'),d);print(json.dumps(d));print(stdout.decode('utf-8',errors='replace')[-5000:]);print(stderr.decode('utf-8',errors='replace')[-5000:]);return proc.returncode
if __name__=='__main__':sys.exit(main())
