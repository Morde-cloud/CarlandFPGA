"""Freeze independently expected protocol cases before changing runner source."""
from pathlib import Path
import datetime,hashlib,importlib.util,itertools,json
from unittest.mock import patch
O=Path(__file__).parent;W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
E=W/'competition/deepeye/evidence/control3d/pwm-runner-qualification-20261020-17';M=E/'main';M.mkdir()
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
source=E/'inputs/run_pwm_applied_capture.py'
assert sha(source.read_bytes())=='b4ac06464af965999d35444f607fa6c7db537b80c340d39cbcc233ee2dce37b0'
s=importlib.util.spec_from_file_location('baseline17',source);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def invoke(module,kind,stdout,stderr,code,spec,d):
    d.mkdir(exist_ok=True)
    if kind=='guard':
        (d/'case.stdout.txt').write_bytes(stdout);(d/'case.stderr.txt').write_bytes(stderr)
        with patch.object(module,'run_command',return_value={'exit':code,'synthetic_process_receipt':True}),patch.object(module.subprocess,'run',side_effect=AssertionError('no process allowed')):
            r=module.run_invalid(d,d,[],{'vsim':'NEVER_EXECUTE'},{'id':'case',**spec},1)
        return r['passed'],r
    (d/'out').write_bytes(stdout);(d/'err').write_bytes(stderr)
    r=module.parse_tb_output(d/'out',d/'err')
    return module.positive_result(spec,{'record':{'exit':code},'parsed':r}),r
guardspec={'count_w':0,'witness_w':64,'tag_w':32}
positive={'id':'case','group':0,'loopback':0,'count_w':4,'witness_w':8,'tag_w':8}
red=[]
for name,kind,code,spec in [('030-invalid-count-zero.stdout.txt','guard',1,guardspec),('032-invalid-count-zero.stdout.txt','guard',1,guardspec),('026-case.stdout.txt','positive',0,positive)]:
    raw=(E/'inputs'/name).read_bytes()
    accepted,result=invoke(m,kind,raw,b'',code,spec,M/('red-'+name.split('-')[0]))
    assert accepted is True
    red.append({'input':name,'stdout_sha256':sha(raw),'stderr_sha256':sha(b''),'synthetic_exit':code,
                'expected_acceptance':False,'actual_acceptance':accepted,'actual_call':('run_invalid' if kind=='guard' else 'parse_tb_output+positive_result'),'result':result})
write(M/'BASELINE_RED.json',{'baseline_runner_sha256':sha(source.read_bytes()),'cases':red,'reproduced':3,'new_simulator_commands':0})
D='DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM COUNT_W=0 WITNESS_W=64 TAG_W=32 SAFE_COUNT_W=2 SAFE_WITNESS_W=64 SAFE_TAG_W=32'
F='** Fatal: DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM unsupported widths'
S='TB_STATS groups=1 cases=1 samples=29 assertions=206 records=2 raw_faults=0 failure_events=0 window_starts=1 handshakes=1 mismatches=0'
C7='CODE7_OBSERVED code=7 window_active=0 out_valid=0'
cases=[]
def add(kind,label,out,err,exit,spec,expected):
    cases.append({'id':f'{len(cases):04d}-{label}','kind':kind,'stdout':out,'stderr':err,'exit':exit,'spec':spec,'expected':expected,
                  'stdout_sha256':sha(out.encode()),'stderr_sha256':sha(err.encode())})
# Independent expected predicate follows DESIGN, not runner implementation.
for order,streams,prefix,code in itertools.product(((D,F),(F,D)),itertools.product((0,1),repeat=2),('','# ','NOT_','# NOT_','## ','banner '),(0,1,2,-1,'timeout','exception',True,False,None,0.0)):
    dest=['','']
    for line,stream in zip(order,streams):dest[stream]+=prefix+line+'\n'
    expected=order==(D,F) and streams==(0,0) and prefix in ('','# ') and type(code)is int and code in(0,1)
    add('guard','order-stream-prefix-exit',*dest,code,guardspec,expected)
for extra,pos,stream in itertools.product((D,F,D.replace('COUNT_W=0','COUNT_W=33',1),'** Error: unrelated','** Fatal: unrelated','APPLIED_CAPTURE_INVALID_GUARD_MISSING',S,'TB_PASS group=0 loopback=0'),range(3),(0,1)):
    out=[D,F];err=''
    if stream==0:out.insert(pos,extra)
    else:err=extra+'\n'
    add('guard','extra-diagnostic', '\n'.join(out)+'\n',err,1,guardspec,False)
for i,field in enumerate(D.split()[1:]):
    fields=D.split()
    for variant in (' '.join(fields[:i+1]+fields[i+2:]),D+' '+field,D.replace(field,field+'x'),D.replace(field,field.replace('=',' =')),D.replace(field,field.split('=')[0]+'='+'9'*5000)):
        add('guard','malformed-field',variant+'\n'+F+'\n','',1,guardspec,False)
for bad in ('+0','-0','00','٠','０','0.0'):
    add('guard','noncanonical-number',D.replace('COUNT_W=0','COUNT_W='+bad,1)+'\n'+F+'\n','',1,guardspec,False)
for sep in ('\r','\v','\f','\x1c','\x85','\u2028','\u2029'):
    add('guard','bad-line-framing',D+sep+F+sep,'',1,guardspec,False)
for newline,prefix in itertools.product(('\n','\r\n'),('','# ')):
    add('guard','healthy-framing',prefix+D+newline+prefix+F+newline,'',1,guardspec,True)
for group,loopback,count,placement,requested_group in itertools.product((0,1,8,13,21,22,29,30,31),(0,1),(0,1,2),('before','between','after','stderr'),('same','other')):
    records=[S,f'TB_PASS group={group} loopback={loopback}'];err=''
    if placement=='stderr':err=(C7+'\n')*count
    else:
        pos={'before':0,'between':1,'after':2}[placement];records[pos:pos]=[C7]*count
    spec={**positive,'group':group if requested_group=='same' else group+1,'loopback':loopback}
    expected=requested_group=='same' and ((group!=30 and count==0) or (group==30 and loopback==0 and count==1 and placement=='before'))
    add('positive','CODE7-group-cross','\n'.join(records)+'\n',err,0,spec,expected)
write(M/'FROZEN_CASES.json',cases)
write(M/'FREEZE.json',{'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'cases_sha256':sha((M/'FROZEN_CASES.json').read_bytes()),'design_sha256':sha((E/'DESIGN.md').read_bytes()),
 'baseline_runner_sha256':sha(source.read_bytes()),'cases':len(cases),'expected_accept':sum(c['expected'] for c in cases),
 'independence':'Main expected cases authored and frozen before changing runner and before inspecting child test additions. No runner import is used to derive expected results; baseline import only reproduces A negatives.',
 'actual_baseline_red_reproductions':3,'new_simulator_commands':0})
print(json.dumps({'cases':len(cases),'expected_accept':sum(c['expected'] for c in cases),'reproduced_A_red':3,'freeze_sha256':sha((M/'FREEZE.json').read_bytes())}))
