"""Freeze independent literal tool query matrix and entry oracle before author dispatch."""
import hashlib,json,subprocess,sys,shutil,time
from pathlib import Path
from datetime import datetime,timezone
O=Path(__file__).parent;R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014'
M=W/'competition/deepeye/evidence/acquisition/sample-scan-toolcheck-20261022-22/main'
D=R/'.local/deployment/node-b/evidence/main-continuation-20261019-v1/sample-scan-capture-20261022-21'
def sha(b):return hashlib.sha256(b).hexdigest()
def put(p,v):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
M.mkdir(parents=True,exist_ok=False);(M/'inputs').mkdir()
source=W/'competition/deepeye/tools/acquisition/run_sample_scan_capture.py'
b=source.read_bytes();assert sha(b)=='99748d791432cd0090e92b1e383670200fc3ead59ad3a6795af72f876e6d6b66'
(M/'inputs/original_runner.py').write_bytes(b)
(M/'inputs/immutable_scope.json').write_bytes((O/'inputs/immutable_scope.json').read_bytes())
for p in [O/'inputs/NEXT_REPAIR_SCOPE_20261022_22.md',O/'inputs/COMPLETED_REVIEW_DECISION.json',O/'inputs/FINDING_OP21_TOOLCHECK_ERROR01.json']:(M/'inputs'/p.name).write_bytes(p.read_bytes())
for name in ['version-controls-01','version-entry-01']:
    shutil.copytree(D/name,M/'coordinator-red'/name)
live=M/'real-version-01';live.mkdir();versions={}
for tool in ['vlog','vsim']:
    exe=Path('D:/modelsim1/win64')/(tool+'.exe');argv=[str(exe),'-version']
    row={'argv':argv,'cwd':str(live),'at_utc':datetime.now(timezone.utc).isoformat(),'scope':'read-only actual vendor -version only','exe_sha256':sha(exe.read_bytes())}
    put(live/(tool+'.intent.json'),row);t=time.monotonic()
    proc=subprocess.Popen(argv,cwd=live,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
    out,err=proc.communicate(timeout=45)
    (live/(tool+'.stdout.bin')).write_bytes(out);(live/(tool+'.stderr.bin')).write_bytes(err)
    row.update(exit=proc.returncode,pid=proc.pid,elapsed=time.monotonic()-t,stdout_sha256=sha(out),stderr_sha256=sha(err));put(live/(tool+'.process.json'),row)
    assert proc.returncode==0 and err==b''
    expected=('Model Technology ModelSim SE-64 '+tool+' 10.7 '+('Compiler' if tool=='vlog' else 'Simulator')+' 2017.12 Dec  7 2017\r\n').encode()
    assert out==expected,(tool,out)
    versions[tool]=out.decode()
rows=[]
def add(tool,name,expected,stdout=None,stderr='',exit=0,timed_out=False,exception=None):
    rows.append({'id':tool+'-'+name,'tool':tool,'stdout':versions[tool] if stdout is None else stdout,'stderr':stderr,'exit':exit,'timed_out':timed_out,'exception':exception,'expected_ok':expected})
for tool in ['vlog','vsim']:
    b=versions[tool];other='vsim' if tool=='vlog' else 'vlog'
    add(tool,'real-crlf',True);add(tool,'lf',True,stdout=b.replace('\r\n','\n'))
    add(tool,'prefix-spaces',True,stdout=' \t# '+b.strip()+' \t\n')
    add(tool,'banner-stderr',True,stdout='',stderr=b)
    add(tool,'zero-tally-out',True,stdout=b+'Errors: 0, Warnings: 0\r\n')
    add(tool,'zero-tally-err',True,stderr='Errors: 0, Warnings: 0\n')
    for stream in ['stdout','stderr']:
        for i,msg in enumerate(['** Error: license failed','Error: failed','eRrOr: failed','** Warning: incompatible','warning: retry','FaTaL: stopped','# ** Error: bad','Errors: 1, Warnings: 0','Errors: 0, Warnings: 1','Errors: x, Warnings: 0','Errors: -1, Warnings: 0','Errors: 0, Warnings:','Errors: 0, Warnings: 0 junk','Errors: 0, Warnings: 0\nErrors: 1, Warnings: 0','Errors: 0, Warnings: 0\nErrors: 0, Warnings: 0','ERRORS: 0, WARNINGS: 0','Warnings: 0','Error code=0','** Fatal: hidden\x00tail']):
            add(tool,stream+'-diagnostic-%02d'%i,False,stdout=b+msg+'\n' if stream=='stdout' else b,stderr=msg+'\n' if stream=='stderr' else '')
    for name,value in [('missing',''),('bare-substring','a random 10.7 hint\n'),('generic-old-probe','ModelSim SE-64 10.7 / 2017.12\n'),('wrong-tool',versions[other]),('wrong-version',b.replace('10.7','10.70')),('older-version',b.replace('10.7','10.6')),('wrong-role',b.replace('Compiler','Simulator') if tool=='vlog' else b.replace('Simulator','Compiler')),('wrong-edition',b.replace('SE-64','PE')),('leading-text','not '+b),('trailing-text',b.strip()+' junk\n'),('duplicate',b+b),('conflict-version',b+b.replace('10.7','2020.4')),('conflict-tool',b+versions[other]),('release-missing',b.split(' 2017.12')[0]+'\n'),('embedded-newline',b.replace(' 10.7','\n10.7')),('split-error',b+'** Error\n: failure\n')]:add(tool,name,False,stdout=value)
    add(tool,'cross-stream-version',False,stderr=b.replace('10.7','10.6'))
    add(tool,'cross-stream-duplicate',False,stderr=b)
    add(tool,'exit7',False,exit=7);add(tool,'exit-none',False,exit=None)
    add(tool,'timeout',False,exit=None,timed_out=True)
    for kind in ['OSError','FileNotFoundError','TimeoutExpired']:add(tool,'exception-'+kind,False,exception=kind)
assert len({x['id'] for x in rows})==len(rows)
put(M/'LITERAL_MATRIX.json',{'scope':'Synthetic query results, literal independent expectations; no author test import','cases':rows})
selected=['directed','guard_seq_w_1','guard_healthy','mutant_loss_undercount_rejected']
old=W/'competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/author/final-all-01/results/cases'
fixtures=M/'entry-fixtures';fixtures.mkdir()
fixture_hashes={}
for name in selected:
    dest=fixtures/name;dest.mkdir()
    for tool in ['vlog','vsim']:
        for suffix in ['stdout.bin','stderr.bin','invocation.json']:
            p=old/name/(tool+'.'+suffix);raw=p.read_bytes();(dest/p.name).write_bytes(raw);fixture_hashes[str((dest/p.name).relative_to(M))]=sha(raw)
put(M/'ENTRY_ORACLE.json',{'cases':[{'id':x['id'],'expected_exit':0 if x['expected_ok'] else 'nonzero','expected_case_vendor_calls':8 if x['expected_ok'] else 0} for x in rows],'selection':selected,'fixture_hashes':fixture_hashes,'scope':'Fresh Python entry for every row, only _run_hidden seam substituted; known-good saved compile/simulation bytes replayed as explicit synthetic controls. Not vendor executions.'})
freeze={'at_utc':datetime.now(timezone.utc).isoformat(),'before_author_dispatch':True,'source_inspected':'old op21 runner only; no new patch exists','source_sha256':sha(source.read_bytes()),'matrix_sha256':sha((M/'LITERAL_MATRIX.json').read_bytes()),'entry_oracle_sha256':sha((M/'ENTRY_ORACLE.json').read_bytes()),'cases':len(rows),'positive':sum(x['expected_ok'] for x in rows),'negative':sum(not x['expected_ok'] for x in rows),'real_vendor_queries':2,'files':{str(p.relative_to(M)):sha(p.read_bytes()) for p in M.rglob('*') if p.is_file()},'parser_decision':'One exact tool/role/release banner across both streams; optional unique zero Errors/Warnings tally; reject any diagnostic, malformed or conflicting banner, nonzero exit, timeout or raised exception. Harmless trim and one # prefix accepted. No compile summary required.'}
put(M/'FREEZE.json',freeze)
print(json.dumps({k:v for k,v in freeze.items() if k!='files'}))
