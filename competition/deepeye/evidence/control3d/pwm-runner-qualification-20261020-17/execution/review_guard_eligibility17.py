"""Record main's child-test review finding before the bounded correction."""
from pathlib import Path
import datetime,hashlib,importlib.util,itertools,json
from unittest.mock import patch
O=Path(__file__).parent;W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
E=W/'competition/deepeye/evidence/control3d/pwm-runner-qualification-20261020-17';M=E/'main';D=M/'guard-eligibility-review';D.mkdir()
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
term=json.loads((O/'CHILD_TERMINAL.json').read_bytes())['result'][0]
assert term['status']=='completed' and term['terminal'] and not term['stale']
runner=W/'competition/deepeye/tools/control3d/run_pwm_applied_capture.py';test=W/'competition/deepeye/tests/control/test_pwm_applied_capture_runner.py'
assert sha(runner.read_bytes())=='0a6101a263fa3c69a8c1737fe965a255ef15aef3ae177fd98e813661a4be8e05'
assert sha(test.read_bytes())=='6cd5ba7f9d0b3ee5fdd188b56cbb564092d2a490a4c7d2e8b0bca8a480bb0082'
(D/'runner-before.py').write_bytes(runner.read_bytes());(D/'test-before.py').write_bytes(test.read_bytes())
s=importlib.util.spec_from_file_location('pre_eligibility_runner',runner);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def guard(c,w,t,sc,sw,st):
    return f'DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM COUNT_W={c} WITNESS_W={w} TAG_W={t} SAFE_COUNT_W={sc} SAFE_WITNESS_W={sw} SAFE_TAG_W={st}\n** Fatal: DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM unsupported widths\n'
cases=[]
for c,w,t in itertools.product((2,3,31,32),(2,3,63,64),(1,2,63,64)):
    cases.append({'kind':'guard','id':f'valid-{c}-{w}-{t}','spec':{'count_w':c,'witness_w':w,'tag_w':t},'stdout':guard(c,w,t,c,w,t),'stderr':'','exit':1,'expected':False})
for c,w,t,sc,sw,st in [(0,64,32,2,64,32),(-1,64,32,2,64,32),(33,64,32,32,64,32),(32,0,32,32,2,32),(32,-2,32,32,2,32),(32,65,32,32,64,32),(32,64,0,32,64,1),(32,64,-1,32,64,1),(32,64,65,32,64,64)]:
    cases.append({'kind':'guard','id':f'invalid-{c}-{w}-{t}','spec':{'count_w':c,'witness_w':w,'tag_w':t},'stdout':guard(c,w,t,sc,sw,st),'stderr':'','exit':1,'expected':True})
for bad in (True,False,0.0,1.0):
    cases.append({'kind':'guard','id':f'noninteger-{type(bad).__name__}-{bad}','spec':{'count_w':bad,'witness_w':64,'tag_w':32},'stdout':guard(int(bad),64,32,2,64,32),'stderr':'','exit':1,'expected':False})
for c in cases:
    c['stdout_sha256']=sha(c['stdout'].encode());c['stderr_sha256']=sha(c['stderr'].encode())
control=cases[0];(D/'case.stdout.txt').write_bytes(control['stdout'].encode());(D/'case.stderr.txt').write_bytes(b'')
with patch.object(m,'run_command',return_value={'exit':1,'synthetic':True}):
    observed=m.run_invalid(D,D,[],{'vsim':'NEVER_EXECUTE'},{'id':'case',**control['spec']},1)
assert observed['passed']
write(M/'SUPPLEMENTAL_EXPECTED_CASES.json',cases)
write(M/'GUARD_REQUEST_ELIGIBILITY_REVIEW.json',{
 'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'finding':'P17-GUARD-VALID-REQUEST',
 'child_job':term['job_id'],'child_terminal':'completed/nonstale; ownership actually released',
 'runner_before_sha256':sha(runner.read_bytes()),'test_before_sha256':sha(test.read_bytes()),
 'actual_control':control,'actual_result':observed,
 'issue':'The author healthy-guard table includes fully legal32/64/64 widths and expects PASS. A matched false guard for supported widths must fail the invalid-parameter test.',
 'decision':'Preserve author results/source; main adds explicit invalid-request eligibility and corrects only the newly added test control, preserving original23 method bytes. Reject noninteger width specs. This is within guard qualification; no RTL or public ABI change.',
 'supplemental_cases':len(cases),'supplemental_expected_accept':sum(c['expected'] for c in cases),
 'supplemental_cases_sha256':sha((M/'SUPPLEMENTAL_EXPECTED_CASES.json').read_bytes()),
 'independence':'New expectations frozen after main found the gap, before correcting source. Not part of the original1007-case freeze.'})
print(json.dumps({'finding':'P17-GUARD-VALID-REQUEST','actual_wrong_acceptance':observed['passed'],'supplemental_cases':len(cases),'supplemental_expected_accept':sum(c['expected'] for c in cases)}))
