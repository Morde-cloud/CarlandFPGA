"""Main acceptance audit; preserve old bytes and bind selected new evidence."""
from pathlib import Path
import datetime, hashlib, json, shutil, subprocess
O=Path(__file__).parent;W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
EP='competition/deepeye/evidence/control3d/pwm-runner-qualification-20261020-16';E=W/EP
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(p,x):
    with p.open('xb') as f:f.write((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def git(*a):return subprocess.check_output(['git','-C',str(W),*a])
runner='competition/deepeye/tools/control3d/run_pwm_applied_capture.py'
test='competition/deepeye/tests/control/test_pwm_applied_capture_runner.py'
result=json.loads((E/'check-02/RESULT.json').read_bytes())
assert result['unit_exit']==result['portable_exit']==0
assert result['exact_A_negatives_rejected']==2 and result['saved_scenarios_accepted']==33
assert result['runner_sha256']==sha((W/runner).read_bytes())=='b4ac06464af965999d35444f607fa6c7db537b80c340d39cbcc233ee2dce37b0'
assert result['test_sha256']==sha((W/test).read_bytes())=='1483b0ca72cf9d66f3c85eac17f3d81f6fccf51eab21deee0e3431b84620ecf8'
before=json.loads((O/'TRACKED_BEFORE.json').read_bytes());changed=[]
for r in before:
    assert (W/r['path']).is_file()
    if sha((W/r['path']).read_bytes())!=r['sha256']:changed.append(r['path'])
assert changed==[runner],changed
assert not git('diff','--cached','--name-only').strip()
assert git('rev-parse','HEAD').decode().strip()=='df82af1bc91d01aeb9adee19f48c0890dfc1ac5b'
write(E/'UNCHANGED_INPUTS.json',{'baseline':'df82af1bc91d01aeb9adee19f48c0890dfc1ac5b',
 'existing_tracked_files_rehashed':len(before),'changed_existing_files':changed,
 'unchanged_sha256_records':[r for r in before if r['path']!=runner],
 'protected_dirty_sha256':'6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8'})
fetched=json.loads((E/'a-original/FETCHED.json').read_bytes())
for r in fetched['files']:
    raw=(E/'a-original'/r['path']).read_bytes()
    assert sha(raw)==r['sha256']
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==r['git_blob']
assert sha((E/'a-original/manifest.json').read_bytes())=='bda421ebc3320450263c16fa9c3a40dca1524905d0c048f397647b305fed13d7'
old=W/'competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/main'
prior_count=0
for p in (E/'prior-b').rglob('*'):
    if p.is_file():
        assert p.read_bytes()==(old/p.relative_to(E/'prior-b')).read_bytes()
        prior_count+=1
consumed=[]
for p in sorted((O/'a-feedback').glob('*.response.json')):
    obj=json.loads(p.read_bytes())
    if obj.get('id') in (6280577242,6280866956,6281218043):
        consumed.append({'id':obj['id'],'url':obj['html_url'],'raw_response_sha256':sha(p.read_bytes()),
                         'body_sha256':sha(obj['body'].encode()),'body':obj['body']})
assert len(consumed)==3
write(E/'A_FEEDBACK_CONSUMED.json',{'comments':consumed,'meaning':'Actually read; not transport ACK or broad acceptance.',
 'op12_count_correction':'40 verified published +45 unavailable compiler-work; not85 verified published.',
 'current_A_dependency_report_only':'PR24 d4a3e76decb96948b618d27736dca9a66e205724 was reported by A; not independently adopted by B in this operation.'})
for commands_path in (E/'check-01/COMMANDS.json',E/'check-02/COMMANDS.json'):
    for command in json.loads(commands_path.read_bytes()):
        assert command['exit_code']==0
        for stream in ('stdout','stderr'):
            assert sha((commands_path.parent/(command['name']+'.'+stream+'.txt')).read_bytes())==command[stream+'_sha256']
(E/'execution').mkdir()
for name in ('prepare16.py','checks16.py','accept16.py'):
    (E/'execution'/name).write_bytes((O/name).read_bytes())
receipt={'decision':'ACCEPT_PYTHON_RUNNER_QUALIFICATION_ONLY',
 'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,
 'operation_id':'B-DEEPEYE-PWM-RUNNER-QUALIFICATION-20261020-16',
 'owner_thread':'01a13b55-095b-7461-8dd5-5476a130bd82',
 'review':'Critical implementation and acceptance performed directly by quality main; no separate new independent author/reviewer claimed.',
 'contract_id':'DEEPEYE-HUMAN-LOCK-20261014','revision':1,
 'requirements_sha256':'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804',
 'requirement_ids':[f'H{i:02d}' for i in range(1,16)],
 'source_sha256':result['runner_sha256'],'test_sha256':result['test_sha256'],
 'tests':{'unit_methods':23,'portable_methods':23,'original_A_red_reproductions':2,
          'original_A_negatives_rejected_after_repair':2,'saved_commands':47,
          'saved_stdout_stderr_hashes':94,'saved_scenarios_reclassified':33,
          'new_ModelSim_commands':0,'new_hardware_commands':0},
 'original_B_qualification_files_retained':prior_count,'original_A_files_rehashed':len(fetched['files']),
 'existing_tracked_files_unchanged':len(before)-1,'existing_tracked_files_changed':[runner],
 'historical_fixture_format':'Original bare TB_PASS synthetic normal fixture is no longer accepted; preserved unchanged. Canonical protocol tests cover the original process/error/fatal predicates.',
 'limits':['No RTL/TB/oracle changes','Saved simulator evidence reused, not new simulation',
           'No new independent RTL oracle','ABI/freshness/BOOT/motion/CDC/RDC/synthesis/implementation/board/system remain outside this increment',
           'All29 formal cards not_run; A-only board']}
write(E/'ACCEPTANCE.json',receipt)
files=[]
for p in sorted(E.rglob('*')):
    if p.is_file():
        assert '__pycache__' not in p.parts
        files.append({'path':p.relative_to(W).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
for path in (runner,test):
    files.append({'path':path,'bytes':(W/path).stat().st_size,'sha256':sha((W/path).read_bytes())})
write(O/'SELECTED.json',{'root':str(W),'baseline':'df82af1bc91d01aeb9adee19f48c0890dfc1ac5b','files':files})
print(json.dumps({'selected_files':len(files),'selected_bytes':sum(r['bytes'] for r in files),
 'unchanged_existing_tracked_files':len(before)-1,'A_files':len(fetched['files']),'old_B_files':prior_count,
 'acceptance_sha256':sha((E/'ACCEPTANCE.json').read_bytes())}))
