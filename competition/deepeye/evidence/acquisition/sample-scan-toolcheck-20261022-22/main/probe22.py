"""Main independent query and actual-entry probes; every vendor call is synthetic."""
import argparse,hashlib,importlib.util,json,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
M=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def put(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def loadmod(source):
    spec=importlib.util.spec_from_file_location('isolated_scoped_runner',source);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod);return mod
def case_by_id(name):return next(c for c in json.loads((M/'LITERAL_MATRIX.json').read_bytes())['cases'] if c['id']==name)
def install_seam(mod,row,d):
    calls=[]
    def run(argv,cwd,timeout):
        tool=Path(argv[0]).stem;assert tool in ['vlog','vsim']
        version=argv[1:]==['-version']
        calls.append({'argv':argv,'cwd':str(cwd),'timeout':timeout,'kind':'synthetic-version' if version else 'synthetic-case','case':None if version else Path(cwd).name})
        (d/'seam_calls.json').write_text(json.dumps(calls,indent=2),encoding='utf-8')
        if version:
            if tool==row['tool']:
                stdout=row['stdout'].encode();stderr=row['stderr'].encode();exitcode=row['exit'];timedout=row['timed_out']
                kind=row.get('exception')
                if kind=='OSError':raise OSError('synthetic version launch failed')
                if kind=='FileNotFoundError':raise FileNotFoundError('synthetic missing version executable')
                if kind=='TimeoutExpired':raise subprocess.TimeoutExpired(argv,timeout,output=stdout,stderr=stderr)
            else:
                stdout=(M/'real-version-01'/(tool+'.stdout.bin')).read_bytes();stderr=b'';exitcode=0;timedout=False
        else:
            case=Path(cwd).name;fixture=M/'entry-fixtures'/case
            assert fixture.is_dir(),('Unexpected case, no vendor allowed',case)
            saved=json.loads((fixture/(tool+'.invocation.json')).read_bytes())
            stdout=(fixture/(tool+'.stdout.bin')).read_bytes();stderr=(fixture/(tool+'.stderr.bin')).read_bytes();exitcode=saved['exit'];timedout=saved['timed_out']
        return {'argv':argv,'cwd':str(cwd),'exit':exitcode,'timed_out':timedout,'elapsed_seconds':0,'stdout_bytes':stdout,'stderr_bytes':stderr}
    mod._run_hidden=run
    return calls
def direct(source,out):
    out.mkdir(exist_ok=False);records=[];mod=loadmod(source)
    for row in json.loads((M/'LITERAL_MATRIX.json').read_bytes())['cases']:
        d=out/row['id'];d.mkdir();calls=install_seam(mod,row,d);error=None;versions=None;reasons=None
        try:versions,reasons=mod._tool_version(Path('EXPLICIT_SYNTHETIC_VENDOR'),d);accepted=not reasons
        except Exception as exc:accepted=False;error=repr(exc)
        record={'id':row['id'],'expected_ok':row['expected_ok'],'actual_ok':accepted,'unhandled_exception':error,'reasons':reasons,'versions':versions,'calls':calls,'agrees':accepted==row['expected_ok'],'clean_failure_propagation':error is None}
        put(d/'OBSERVATION.json',record);records.append(record)
    result={'scope':'Actual _tool_version called with synthetic _run_hidden, no vendor process','source':str(source),'source_sha256':sha(source.read_bytes()),'cases':len(records),'mismatches':[r['id'] for r in records if not r['agrees']],'unhandled':[r['id'] for r in records if r['unhandled_exception']],'records':records}
    put(out/'RESULT.json',result);print(json.dumps({k:v for k,v in result.items() if k!='records'}))
def entry(source,case,out,root):
    out.mkdir(exist_ok=False);row=case_by_id(case);mod=loadmod(source);calls=install_seam(mod,row,out)
    fake=out/'explicit-synthetic-vendor';fake.mkdir()
    for tool in ['vlog','vsim']:(fake/(tool+'.exe')).write_bytes(b'explicit synthetic placeholder; never executed')
    selection=json.loads((M/'ENTRY_ORACLE.json').read_bytes())['selection']
    argv=['--root',str(root),'--out',str(out/'results'),'--modelsim',str(fake)]
    for name in selection:argv+=['--case',name]
    put(out/'ENTRY_INTENT.json',{'runner_sha256':sha(source.read_bytes()),'row':row,'argv':argv,'scope':'Actual Python main; all vendor calls intercepted; no vendor compile or simulation'})
    code=mod.main(argv);put(out/'RETURN.json',{'main_return':code,'calls':calls});return code
def entries(source,out,root):
    out.mkdir(exist_ok=False);records=[]
    for row in json.loads((M/'LITERAL_MATRIX.json').read_bytes())['cases']:
        name=row['id'];d=out/name
        argv=[sys.executable,'-B','-X','utf8',str(Path(__file__).resolve()),'entry','--source',str(source),'--out',str(d),'--case',name,'--root',str(root)]
        intent={'argv':argv,'cwd':str(out),'at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(source.read_bytes()),'helper_sha256':sha(Path(__file__).read_bytes()),'expected_exit':0 if row['expected_ok'] else 'nonzero','expected_case_calls':8 if row['expected_ok'] else 0}
        put(out/(name+'.intent.json'),intent);t=time.monotonic();proc=subprocess.Popen(argv,cwd=out,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
        stdout,stderr=proc.communicate(timeout=60)
        (out/(name+'.stdout.bin')).write_bytes(stdout);(out/(name+'.stderr.bin')).write_bytes(stderr)
        calls=json.loads((d/'seam_calls.json').read_bytes());casecalls=[c for c in calls if c['kind']=='synthetic-case']
        summary=json.loads((d/'results/summary.json').read_bytes()) if (d/'results/summary.json').exists() else None
        agrees=(proc.returncode==0 if row['expected_ok'] else proc.returncode!=0) and len(casecalls)==intent['expected_case_calls'] and summary is not None and summary['ok'] is row['expected_ok']
        if not row['expected_ok']:agrees=agrees and summary is not None and summary['results']=={} and bool(summary['reasons'])
        rec={**intent,'id':name,'pid':proc.pid,'exit':proc.returncode,'elapsed':time.monotonic()-t,'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr),'case_calls':len(casecalls),'summary_present':summary is not None,'summary_ok':None if summary is None else summary['ok'],'agrees':agrees}
        put(out/(name+'.process.json'),rec);records.append(rec)
    result={'scope':'Fresh actual Python processes with explicit synthetic vendor seam; no vendor compile/simulation','source_sha256':sha(source.read_bytes()),'processes':len(records),'mismatches':[r['id'] for r in records if not r['agrees']],'records':records}
    put(out/'RESULT.json',result);print(json.dumps({k:v for k,v in result.items() if k!='records'}))
p=argparse.ArgumentParser();p.add_argument('action',choices=['direct','entry','entries']);p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--case');p.add_argument('--root',type=Path);a=p.parse_args()
a.source=a.source.resolve();a.out=a.out.resolve()
if a.root is not None:a.root=a.root.resolve()
if a.action=='direct':direct(a.source,a.out)
elif a.action=='entries':entries(a.source,a.out,a.root)
else:sys.exit(entry(a.source,a.case,a.out,a.root))
