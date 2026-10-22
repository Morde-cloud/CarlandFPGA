"""Focused main runner/parser negative cases; no vendor run is claimed."""
import importlib.util,hashlib,json,gzip
from pathlib import Path
M=Path(__file__).parent;W=M.parents[5]
S=W/'competition/deepeye/tools/acquisition/main_verify_sample_scan_capture.py'
spec=importlib.util.spec_from_file_location('main21_check',S);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
rows=[]
def check(label,want,got):
    assert bool(want)==bool(got),(label,want,got)
    rows.append({'case':label,'accepted':bool(got),'expected':bool(want)})
own='deepeye_sample_scan_capture: SEQ_W out of range'
good='ModelSim SE-64 10.7\nErrors: 0, Warnings: 0\n'
fatal='# ** Fatal: '+own+'\n# Time: 0 ps Iteration: 0 Instance: /main_guard_sample_scan_capture/dut\nErrors: 1, Warnings: 0\n'
check('ordinaryclean',True,not v.classify(0,False,good))
check('exactownfatal',True,not v.classify(0,False,fatal,own))
for exitcode in [-1,1,2,3,127]:
    for guard in [None,own]:check('nonzeroexit'+str(exitcode)+str(guard),False,not v.classify(exitcode,False,fatal if guard else good,guard))
for guard in [None,own]:check('timeout'+str(guard),False,not v.classify(0,True,fatal if guard else good,guard))
for bad in ['** Error: compile failed','** Warning: port size','** Fatal: foreign','Errors: 1, Warnings: 0','Errors: 0, Warnings: 1','Errors: 00, Warnings: 0','Errors: -1, Warnings: 0','warning','error','FATAL: hidden failure','Errors: 0, Warnings: 0 trailing']:
    check('diagnostic:'+bad,False,not v.classify(0,False,good+bad))
for bad in ['','NOT_** Fatal: '+own,fatal+fatal,fatal+'\n** Error: foreign',fatal+'\nErrors: 2, Warnings: 0',fatal+'\nMAIN_GUARD_MISSING',fatal+'\nMAIN_SAMPLE_SCAN_DONE',fatal.replace('SEQ_W','TAG_W'),fatal.replace('Errors: 1','Errors: 0')]:
    check('guardnegative:'+bad[:50],False,not v.classify(0,False,bad,own))
params={'seq':32,'tick':64,'tag':64,'stat':32};line='MAIN_SAMPLE_SCAN_DONE edges=17 SEQ_W=32 TICK_W=64 TAG_W=64 STAT_W=32'
for text in [line,'# '+line,line+'\r\n','unrelated\n'+line]:check('goodmarker:'+repr(text),True,v.marker(text,params,17))
for text in ['',line+line,line+'\n'+line,'NOT_'+line,line+' junk',line.replace('17','18'),line.replace('TAG_W=64','TAG_W=32'),line.replace('edges=17','edges=017'),line+'\n'+line.replace('17','18'),line.replace('STAT_W=32',''),line.replace('17','-17')]:check('badmarker:'+repr(text),False,v.marker(text,params,17))
# Independent finite-string characterization: every complete 0123 substring is
# one scan and the remaining suffix 0/01/012 is the only possible live partial.
freeze=json.loads((M/'frozen-inputs/FREEZE.json').read_bytes());meta=freeze['cases']['main64'];vectors=(M/'frozen-inputs/main64/vectors.hex').read_text().splitlines();expected=json.loads(gzip.decompress((M/'frozen-inputs/main64/expected.json.gz').read_bytes()))
count=0;channels=[];active=False
start=next(x[0] for x in meta['labels'] if '4096' in x[1]);end=next(x[0] for x in meta['labels'] if 'ready patterns' in x[1])
for i in range(start,end):
    x=[int(t,16) for t in vectors[i].split()]
    if x[2]:channels=[]
    elif x[4]:channels.append(str(x[5]))
    else:
        seq=''.join(channels);assert len(seq)==6
        scans=seq.count('0123');partial=max([n for n in range(1,4) if seq.endswith('012'[:n])]+[0]);lost=6-4*scans-partial
        post=expected[i][1];assert (post[15],post[8],post[17])==(scans,partial,lost),(seq,post)
        count+=1
assert count==4096
result={'runner_sha256':hashlib.sha256(S.read_bytes()).hexdigest(),'parser_process_cases':len(rows),'literal_finite_strings':count,'cases':rows,'scope':'Synthetic classifier checks and independent frozen-string audit only; not actual vendor runs.'}
out=M/'main-runner-qualification.json'
with out.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items() if k!='cases'}))
