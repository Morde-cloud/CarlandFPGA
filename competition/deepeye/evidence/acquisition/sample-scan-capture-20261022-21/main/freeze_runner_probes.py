"""Bounded independent probes after inspecting author runner; not blind review."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
M=Path(__file__).parent;W=M.parents[5];S=W/'competition/deepeye/tools/acquisition/run_sample_scan_capture.py';D=M/'runner-probes';D.mkdir(exist_ok=False)
b=S.read_bytes();(D/'inspected_runner.py').write_bytes(b)
stats={'events':14,'scans':3,'retired':2,'discarded':6,'order_errors':1,'overruns':1,'partial_len':0,'occupied':0,'armed':1,'exhausted':0}
body='case=directed checks=407 errors=0 windows=1 '+' '.join(k+'='+str(n) for k,n in stats.items())
good='SAMPLE_SCAN_STATS '+body+'\nSAMPLE_SCAN_PASS\nErrors: 0, Warnings: 0\n'
compilegood='Errors: 0, Warnings: 0\n';own='deepeye_sample_scan_capture: SEQ_W out of range'
fatal='** Fatal: '+own+'\nTime: 0 ps Iteration: 0 Instance: /tb_sample_scan_capture_guard/dut\nErrors: 1, Warnings: 0\n'
rows=[]
def add(name,fn,args,expected):rows.append({'name':name,'function':fn,'args':args,'expected_ok':expected})
def sim(name,text=good,stderr='',exit=0,ok=False):add(name,'classify_simulation_output',[exit,text,stderr,'directed',stats],ok)
sim('clean-lf',ok=True);sim('clean-crlf',good.replace('\n','\r\n'),ok=True)
for n in [-1,1,2,127]:sim('sim-exit-'+str(n),exit=n)
for text in ['** Error: runtime failure','error: runtime failure','ERROR: runtime failure','warning: uncertain','** Warning: uncertain','** Fatal: unexpected','fatal: unexpected','FATAL: unexpected','Errors: 1, Warnings: 0','Errors: 0, Warnings: 1','Errors: 0, Warnings: 0','Errors: 0, Warnings: 0 trailing']:
    sim('sim-stdout-'+text,good+text+'\n');sim('sim-stderr-'+text,stderr=text+'\n')
for label,text in [('substring-pass',good.replace('SAMPLE_SCAN_PASS','NOT_SAMPLE_SCAN_PASS')),('duplicate-pass',good+'SAMPLE_SCAN_PASS\n'),('trailing-pass',good.replace('SAMPLE_SCAN_PASS','SAMPLE_SCAN_PASS junk')),('malformed-extra-pass',good+'NOT_SAMPLE_SCAN_PASS\n'),('duplicate-stats',good+'SAMPLE_SCAN_STATS '+body+'\n'),('conflicting-stats',good+'SAMPLE_SCAN_STATS '+body.replace('events=14','events=15')+'\n'),('malformed-extra-stats',good+'NOT_SAMPLE_SCAN_STATS broken\n'),('trailing-stats',good.replace(body,body+' junk')),('missing-stats-key',good.replace(' scans=3','')),('duplicate-stats-key',good.replace(body,body+' events=14')),('wrong-case',good.replace('case=directed','case=wrong')),('no-checks',good.replace('checks=407','checks=0')),('no-windows',good.replace('windows=1','windows=0')),('tb-errors',good.replace('errors=0','errors=1')),('wrong-loss',good.replace('discarded=6','discarded=5')),('wrong-occupied',good.replace('occupied=0','occupied=2'))]:sim(label,text)
add('compile-clean','classify_compile',[0,compilegood,''],True)
for code in [-1,1,2,127]:add('compile-exit-'+str(code),'classify_compile',[code,compilegood,''],False)
for text in ['** Error: compiler','error: compiler','fatal: compiler','warning: compiler','** Fatal: compiler','Errors: 0, Warnings: 0 trailing','Errors: 0, Warnings: 1']:
    add('compile-stdout-'+text,'classify_compile',[0,compilegood+text+'\n',''],False)
    add('compile-stderr-'+text,'classify_compile',[0,compilegood,text+'\n'],False)
# B ModelSim main guard runs with exact run-all/quit-f reached the own DUT fatal
# and exited0. A foreign/nonzero tool exit is not an alternate successful guard.
def guard(name,text=fatal,stderr='',exit=0,ok=False):add(name,'classify_guard_output',[0,compilegood,'',exit,text,stderr,'SEQ_W',own],ok)
guard('actual-own-fatal-exit0',ok=True)
for code in [-1,1,2,127]:guard('foreign-guard-exit-'+str(code),exit=code)
for label,text in [('missing',''),('substring',fatal.replace('** Fatal:','NOT_** Fatal:')),('duplicate',fatal+fatal),('wrongfamily',fatal.replace('SEQ_W','TAG_W')),('trailing',fatal.replace(own,own+' junk')),('anotherfatal',fatal+'** Fatal: another\n'),('guard-tb-error',fatal+'** Error: bad\n'),('guard-tally-zero',fatal.replace('Errors: 1','Errors: 0')),('guard-tally-two',fatal.replace('Errors: 1','Errors: 2')),('guard-pass',fatal+'SAMPLE_SCAN_PASS\n')]:guard('guard-'+label,text)
for text in ['error: runtime','** Error: runtime','warning: runtime','Errors: 0, Warnings: 1']:guard('guard-stderr-'+text,stderr=text)
for name,selected,results,ok in [('aggregate-good',['directed'],{'directed':{'ok':True}},True),('aggregate-empty',[],{},False),('aggregate-duplicate',['directed','directed'],{'directed':{'ok':True}},False),('aggregate-missing',['directed'],{},False),('aggregate-extra',['directed'],{'directed':{'ok':True},'extra':{'ok':True}},False),('aggregate-failed',['directed'],{'directed':{'ok':False}},False),('aggregate-missing-ok',['directed'],{'directed':{}},False),('aggregate-truthy',['directed'],{'directed':{'ok':'yes'}},False)]:add(name,'aggregate_results',[selected,results],ok)
raw=(json.dumps(rows,indent=2)+'\n').encode();(D/'cases.json').write_bytes(raw)
with (D/'FREEZE.json').open('x',encoding='utf-8') as f:json.dump({'at_utc':datetime.now(timezone.utc).isoformat(),'inspected_runner_sha256':hashlib.sha256(b).hexdigest(),'cases_sha256':hashlib.sha256(raw).hexdigest(),'cases':len(rows),'scope':'Independent main authored after reading runner; synthetic classifier probes; not vendor executions. Own fatal exit0 based on eight actual main ModelSim guard receipts.'},f,indent=2);f.write('\n')
print(json.dumps({'cases':len(rows),'inspected_sha256':hashlib.sha256(b).hexdigest()}))
