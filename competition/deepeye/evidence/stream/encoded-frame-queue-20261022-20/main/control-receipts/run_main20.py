"""Bounded actual-process receipts for op20 main qualification only."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, subprocess, sys, time

R = Path('D:/pynq/CarlandFPGA')
W = R/'.local/worktrees/deepeye-implementation-20261014'
E = W/'competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20/main'
O = R/'.local/deployment/node-b/evidence/encoded-frame-queue-20261022-20'
S = W/'competition/deepeye/tools/stream/main_verify_encoded_frame_queue.py'
sha = lambda x: hashlib.sha256(x).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--name', required=True)
    p.add_argument('--mode', required=True)
    p.add_argument('--dut')
    p.add_argument('--expect-mismatch', action='store_true')
    a=p.parse_args()
    assert a.name.replace('-','').replace('_','').isalnum()
    receipt=O/(a.name+'.process.json')
    intent=O/(a.name+'.process.intent.json')
    assert not receipt.exists() and not intent.exists()
    out=E/a.name
    argv=[sys.executable,'-B','-X','utf8',str(S),'--root',str(W),'--out',str(out),'--mode',a.mode]
    if a.dut: argv+=['--dut',a.dut]
    if a.expect_mismatch: argv+=['--expect-mismatch']
    before=dict(argv=argv,cwd=str(O),source_sha256=sha(S.read_bytes()),started=datetime.now(timezone.utc).isoformat())
    intent.write_text(json.dumps(before,indent=2),encoding='utf-8')
    start=time.monotonic()
    process=subprocess.Popen(argv,cwd=O,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
    # The inner verifier bounds each actual tool invocation and retains its handle.
    stdout,stderr=process.communicate()
    (O/(a.name+'.stdout.bin')).write_bytes(stdout)
    (O/(a.name+'.stderr.bin')).write_bytes(stderr)
    record=dict(**before,pid=process.pid,exit_code=process.returncode,elapsed_seconds=time.monotonic()-start,
                ended=datetime.now(timezone.utc).isoformat(),stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),
                source_after_sha256=sha(S.read_bytes()),result_path=str(out/'RESULT.json'))
    receipt.write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record),flush=True)
    print(stdout.decode('utf-8',errors='replace')[-6000:])
    if process.returncode: print(stderr.decode('utf-8',errors='replace')[-8000:])
    return process.returncode

if __name__=='__main__': sys.exit(main())
