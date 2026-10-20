"""Freeze bounded main-owned parser repair and reproduce exact A negatives."""
from pathlib import Path
import datetime, hashlib, importlib.util, json, shutil, subprocess
O=Path(__file__).parent
W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
EP='competition/deepeye/evidence/control3d/pwm-runner-qualification-20261020-16'
E=W/EP
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def git(*args):return subprocess.check_output(['git','-C',str(W),*args])
assert git('rev-parse','HEAD').decode().strip()=='df82af1bc91d01aeb9adee19f48c0890dfc1ac5b'
assert not git('diff','--cached','--name-only').strip()
runner='competition/deepeye/tools/control3d/run_pwm_applied_capture.py'
test='competition/deepeye/tests/control/test_pwm_applied_capture_runner.py'
assert sha((W/runner).read_bytes())=='83f192c70ab48427e70a0dc66662e4a24a66be90633a454a82e179a6a79ddf98'
assert not (W/test).exists()
contract=json.loads((O/'contract-pinned.json').read_bytes())
assert sha(json.dumps(contract['requirements'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())=='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
E.mkdir()
shutil.copytree(O/'a-fixture-files',E/'a-original')
old=W/'competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/main'
for name in ('runner-qualification-red','runner-qualification-terminal-red','runner-qualification-green'):
    shutil.copytree(old/name,E/'prior-b'/name)
(E/'runner-before.py').write_bytes((W/runner).read_bytes())
tracked=[]
for p in git('ls-files','-z').decode().split('\0'):
    if p and (W/p).is_file():
        tracked.append({'path':p,'sha256':sha((W/p).read_bytes())})
write(O/'TRACKED_BEFORE.json',tracked)
scope={
 'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,
 'work_id':'B-PWM-RUNNER-QUALIFICATION-20261020-16-v1',
 'operation_id':'B-DEEPEYE-PWM-RUNNER-QUALIFICATION-20261020-16',
 'owner_thread':'01a13b55-095b-7461-8dd5-5476a130bd82',
 'current_turn_id':'not independently obtained',
 'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'baseline':git('rev-parse','HEAD').decode().strip(),
 'ownership':[runner,test,EP+'/**','handoffs/b/B-DEEPEYE-PWM-RUNNER-QUALIFICATION-20261020-16/**'],
 'execution':'Quality main implements and evaluates the critical parser change directly; fresh child_status shows zero active jobs, zero instances,90 historical jobs. No new delegation.',
 'contract_id':'DEEPEYE-HUMAN-LOCK-20261014','revision':1,
 'contract_pin':'f5989cd5defce561f9ba98e6b18fc2682945f0a2',
 'requirements_sha256':'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804',
 'requirements_ids':[f'H{i:02d}' for i in range(1,16)],
 'design_pin':'1011259415a0916054eb580687612580bc1e5f09',
 'authority':'A matched PR30 comment6281218043 requests B-owned parser repair under existing implementation ownership.',
 'design':'Exactly one complete ASCII stats row then exactly one whole-line PASS/FAIL with optional known # prefix; bind group/loopback; validate mismatch count and labels; reject malformed/duplicate/conflicting terminal evidence and simulator errors on normal paths. Preserve process-exit checks.',
 'validation':'Original A two negatives before/after; canonical positive/negative transcript tests and process-status injection; classify exact saved 47-command suite without invoking ModelSim.',
 'limits':'No RTL/TB/old oracle/old evidence edits; no full B15 simulator replay, new board run, ABI/TTL/BOOT/motion authority. All29 formal cards not_run.',
 'prior_review':'Op15 coordinator wait actually failed with usage limit; no ACCEPT, no automatic resubmission. Independent A review is the current actionable input.',
 'local_preparation_failures':[
  'A tree GET succeeded once; local output-directory collision then aborted before blob reads. Recovery consumed saved tree and fetched only remaining blobs.',
  'One long inline PowerShell preparation command failed parsing before script creation/network. Replaced by apply_patch. Neither failure is a product test result.'
 ]}
write(E/'SCOPE.json',scope)
s=importlib.util.spec_from_file_location('original_runner',E/'runner-before.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
q=E/'a-original/op15/review/qualification-repaired'
spec={'id':'A-negative','group':0,'loopback':0,'count_w':4,'witness_w':8,'tag_w':8}
cases=[]
for name in ('substring-pass','duplicate-stats'):
    stdout=q/(name+'.stdout.txt');stderr=q/(name+'.stderr.txt')
    parsed=m.parse_tb_output(stdout,stderr)
    parsed.update(transcript=None,transcript_sha256=None,wlf=None,wlf_sha256=None)
    got=m.positive_entry(spec,{'parsed':parsed,'record':{'exit':0,'stdout':str(stdout),'stderr':str(stderr)}})['passed']
    assert got is True
    cases.append({'name':name,'observed_accepted':got,'expected_accepted':False,
                  'stdout_sha256':sha(stdout.read_bytes()),'stderr_sha256':sha(stderr.read_bytes())})
write(E/'RED.json',{'source_sha256':sha((E/'runner-before.py').read_bytes()),'synthetic_only':True,'cases':cases,'reproduced_defects':2})
print(json.dumps({'scope':str(E/'SCOPE.json'),'red_reproduced':2,'protected_tracked_files':len(tracked)}))
