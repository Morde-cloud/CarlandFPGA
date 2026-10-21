"""Actual Python entrypoint processes with explicit synthetic vendor seams."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.util,json,subprocess,sys,time
M=Path(__file__).resolve().parent;W=M.parents[5]
SOURCE=W/'competition/deepeye/tools/stream/run_encoded_frame_queue.py'
LOGS=M.parent/'author/run-final-01'
sha=lambda b:hashlib.sha256(b).hexdigest()
VARIANTS=['good','foreign-compile','foreign-guard','malformed-stat','missing-output','exit17','timeout','last-failed']

def one(name,out,source):
    spec=importlib.util.spec_from_file_location('probe_author_runner',source)
    r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    r.PRODUCT_ROOT=W;r.EVIDENCE_ROOT=out
    r.MODEL='synthetic-process-seam-not-inference';r.REASONING_EFFORT='not-applicable'
    calls=[]
    def process(argv,cwd,step_dir,timeout_s):
        step_dir.mkdir(parents=True,exist_ok=False)
        stage=step_dir.name;suite=cwd.name;stdout=b'';stderr=b''
        if stage=='git-head':stdout=(r.BASELINE_HEAD+'\n').encode()
        elif stage=='git-status':stdout=b''
        elif stage.endswith('-version'):stdout=b'Model Technology synthetic version seam\n'
        elif stage=='01-vlib':(cwd/'work').mkdir()
        elif stage in ('02-vlog','03-vsim'):
            logs=LOGS/suite/'steps'/stage
            stdout=(logs/'stdout.txt').read_bytes();stderr=(logs/'stderr.txt').read_bytes()
        record=dict(argv=list(map(str,argv)),cwd=str(cwd),returncode=0,timed_out=False,spawn_error=None,
                    synthetic_vendor_seam=True,timeout_s=timeout_s)
        if name=='foreign-compile' and suite=='standalone' and stage=='02-vlog':stdout+=b'error: injected foreign compiler error\n'
        if name=='foreign-guard' and suite=='guard-33' and stage=='03-vsim':stderr+=b'FATAL: injected unrelated guard error\n'
        if name=='malformed-stat' and suite=='standalone' and stage=='03-vsim':stdout+=b'TB_STAT checks=broken\n'
        if name in ('exit17','timeout') and suite=='standalone' and stage=='03-vsim':
            if name=='exit17':record['returncode']=17
            else:record['timed_out']=True
        if name=='last-failed' and suite=='guard-33' and stage=='03-vsim':record['returncode']=17
        if not (name=='missing-output' and suite=='standalone' and stage=='03-vsim'):
            (step_dir/'stdout.txt').write_bytes(stdout)
        (step_dir/'stderr.txt').write_bytes(stderr)
        r.write_json(step_dir/'process.json',record);calls.append(record);return record
    r.run_process=process
    exit_code=r.main(['--out',str(out/'run'),'--suite','standalone','--suite','guard-33'])
    (out/'SEAMS.json').write_text(json.dumps(dict(source_sha256=sha(source.read_bytes()),vendor_execution=False,calls=calls),indent=2),encoding='utf-8')
    return exit_code

def all_probes(out,source):
    out.mkdir(exist_ok=False);records=[]
    for name in VARIANTS:
        folder=out/name;folder.mkdir();argv=[sys.executable,'-B','-X','utf8',str(Path(__file__).resolve()),'--one',name,'--out',str(folder),'--source',str(source)]
        before=datetime.now(timezone.utc).isoformat();start=time.monotonic()
        process=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=W,creationflags=0x08000000)
        stdout,stderr=process.communicate(timeout=45)
        (folder/'python.stdout.bin').write_bytes(stdout);(folder/'python.stderr.bin').write_bytes(stderr)
        result=json.loads((folder/'run/RUN_RESULT.json').read_bytes())
        expected=0 if name=='good' else 1
        record=dict(name=name,argv=argv,pid=process.pid,started=before,elapsed_seconds=time.monotonic()-start,
                    actual_exit=process.returncode,expected_exit=expected,match=process.returncode==expected,
                    stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),source_sha256=sha(source.read_bytes()),
                    suite_status={k:v['status'] for k,v in result['suites'].items()},vendor_execution=False)
        (folder/'PYTHON_PROCESS.json').write_text(json.dumps(record,indent=2),encoding='utf-8');records.append(record)
    final=dict(cases=len(records),mismatches=sum(not r['match'] for r in records),records=records)
    (out/'RESULT.json').write_text(json.dumps(final,indent=2),encoding='utf-8')
    print(json.dumps(dict(cases=len(records),mismatches=final['mismatches'],exits=[r['actual_exit'] for r in records])))
    return int(final['mismatches']!=0)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--one',choices=VARIANTS);p.add_argument('--source',type=Path,default=SOURCE);a=p.parse_args()
    sys.exit(one(a.one,a.out.resolve(),a.source.resolve()) if a.one else all_probes(a.out.resolve(),a.source.resolve()))
