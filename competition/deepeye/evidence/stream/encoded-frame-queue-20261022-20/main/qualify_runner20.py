"""Frozen synthetic parser/process probes; these are not vendor executions."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.util,json,re
M=Path(__file__).resolve().parent
W=M.parents[5]
S=W/'competition/deepeye/tools/stream/run_encoded_frame_queue.py'
A=M.parent/'author/run-final-01'
sha=lambda b:hashlib.sha256(b).hexdigest()

def load(path):
    spec=importlib.util.spec_from_file_location('qualified_author_runner',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def freeze():
    root=M/'runner-qualification-02';root.mkdir(exist_ok=False)
    raw=S.read_bytes();(root/'author_runner_original.py').write_bytes(raw)
    r=load(S);cases=[];pins={}
    def add(name,kind,suite,text,expected,record=None):
        cases.append(dict(name=name,kind=kind,suite=suite,text=text,expected=expected,record=record))
    for suite,spec in r.SUITES.items():
        for stage,kind in [('02-vlog','compile'),('03-vsim',spec['kind'])]:
            folder=A/suite/'steps'/stage
            text=''
            for filename in ('stdout.txt','stderr.txt'):
                p=folder/filename;b=p.read_bytes();pins[str(p.relative_to(W))]=sha(b)
                # Match runner read_text universal-newline decoding, preserve raw pins.
                text+=b.decode('utf-8').replace('\r\n','\n').replace('\r','\n')+'\n'
            prefix=suite+'/'+kind
            add(prefix+'/real-control',kind,suite,text,True)
            for i,line in enumerate(['Error: foreign','error: foreign','# ERROR: foreign','** ERROR: foreign',
                '# ** fatal: foreign','FATAL: foreign','** Fatal: foreign','ERROR loading design',
                'Errors: +1, Warnings: 0','Errors: 1x, Warnings: 0','Errors: 1, Warnings: zero',
                'errors: 1, warnings: 0','Errors: 0, Warnings: 0 extra']):
                add(prefix+'/foreign-'+str(i),kind,suite,text+line+'\n',False)
            if kind=='ordinary':
                for i,line in enumerate(['TB_STAT final_level=x','TB_STAT checks=+0','TB_SUMMARY cases=x pass=0 fail=0 checks=0',
                    'CASE_END name=unknown status=pass checks=garbage','TB_END pass extra',
                    'TB_STAT checks=0','TB_END pass']):
                    add(prefix+'/extra-structured-'+str(i),kind,suite,text+line+'\n',False)
                add(prefix+'/substring',kind,suite,text.replace('TB_END pass','NOT_TB_END pass_SUFFIX'),False)
                add(prefix+'/missing-stat',kind,suite,re.sub(r'^.*TB_STAT checks=.*\n','',text,flags=re.M),False)
                add(prefix+'/missing-end',kind,suite,re.sub(r'^.*TB_END pass.*\n','',text,flags=re.M),False)
            elif kind=='guard':
                add(prefix+'/wrong-fatal',kind,suite,text.replace(spec['expected_fatal'],'UNRELATED_FATAL'),False)
    for name,record,expected in [
        ('process-good',dict(spawn_error=None,timed_out=False,returncode=0),True),
        ('process-exit',dict(spawn_error=None,timed_out=False,returncode=17),False),
        ('process-timeout',dict(spawn_error=None,timed_out=True,returncode=0),False),
        ('process-spawn',dict(spawn_error='denied',timed_out=False,returncode=0),False)]:
        add(name,'process','standalone','',expected,record)
    document=dict(at_utc=datetime.now(timezone.utc).isoformat(),author_runner_sha256=sha(raw),raw_log_pins=pins,
                  scope='Synthetic qualification, main inspected runner before selecting exact probes; no blind-review claim.',cases=cases)
    (root/'FROZEN_CASES.json').write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(status='frozen',cases=len(cases),sha256=sha((root/'FROZEN_CASES.json').read_bytes()))))

def run(out,source):
    out.mkdir(exist_ok=False);r=load(source);raw=source.read_bytes();(out/'runner_snapshot.py').write_bytes(raw)
    fixture=M/'runner-qualification-02/FROZEN_CASES.json';document=json.loads(fixture.read_bytes());results=[]
    for c in document['cases']:
        checks=[];exception=None
        try:
            if c['kind']=='process':r.classify_process(c['record'],checks,c['name'])
            elif c['kind']=='compile':r.classify_compile(c['text'],r.SUITES[c['suite']],checks,c['name'])
            elif c['kind']=='guard':r.classify_guard(c['text'],r.SUITES[c['suite']],checks,c['name'])
            else:r.classify_ordinary(c['text'],r.SUITES[c['suite']],checks,c['name'])
            accepted=bool(checks) and all(x['pass'] for x in checks)
        except Exception as e:exception=repr(e);accepted=None
        results.append(dict(name=c['name'],expected=c['expected'],accepted=accepted,exception=exception,
                            matches=accepted==c['expected'],failed_checks=[x['name'] for x in checks if not x['pass']]))
    result=dict(source_sha256=sha(raw),fixtures_sha256=sha(fixture.read_bytes()),cases=len(results),
                mismatches=sum(not x['matches'] for x in results),results=results)
    (out/'RESULT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='results'}))
    print(json.dumps([x['name'] for x in results if not x['matches']]))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--out',type=Path);p.add_argument('--source',type=Path,default=S);a=p.parse_args()
    if a.freeze:freeze()
    else:run(a.out,a.source)
