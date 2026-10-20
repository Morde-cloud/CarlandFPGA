"""Run portable unit tests and reclassify saved logs; never launch ModelSim."""
from pathlib import Path
import argparse, datetime, hashlib, importlib.util, json, shutil, subprocess, sys
O=Path(__file__).parent;W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
E=W/'competition/deepeye/evidence/control3d/pwm-runner-qualification-20261020-16'
ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);args=ap.parse_args()
D=E/args.attempt;D.mkdir()
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
runner=W/'competition/deepeye/tools/control3d/run_pwm_applied_capture.py'
test=W/'competition/deepeye/tests/control/test_pwm_applied_capture_runner.py'
(D/'tested_runner.py').write_bytes(runner.read_bytes());(D/'tested_test.py').write_bytes(test.read_bytes())
commands=[]
def run(name,cmd,cwd):
    start=datetime.datetime.now(datetime.timezone.utc).isoformat()
    p=subprocess.run(list(map(str,cmd)),cwd=cwd,capture_output=True,timeout=60)
    (D/(name+'.stdout.txt')).write_bytes(p.stdout);(D/(name+'.stderr.txt')).write_bytes(p.stderr)
    commands.append({'name':name,'argv':list(map(str,cmd)),'cwd':str(cwd),'started_utc':start,
                     'ended_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     'exit_code':p.returncode,'stdout_sha256':sha(p.stdout),'stderr_sha256':sha(p.stderr)})
    write(D/'COMMANDS.json',commands)
    print(name,p.returncode,p.stderr.decode(errors='replace')[-2200:])
    return p.returncode
unit=run('unit',[sys.executable,'-B','-X','utf8',test],W)
portable=O/(args.attempt+'-portable');portable.mkdir()
pr=portable/runner.relative_to(W);pt=portable/test.relative_to(W)
pr.parent.mkdir(parents=True);pt.parent.mkdir(parents=True)
pr.write_bytes(runner.read_bytes());pt.write_bytes(test.read_bytes())
portable_exit=run('portable',[sys.executable,'-B','-X','utf8',pt],portable)
s=importlib.util.spec_from_file_location('qualification_runner',runner);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
spec={'id':'A-negative','group':0,'loopback':0,'count_w':4,'witness_w':8,'tag_w':8}
q=E/'a-original/op15/review/qualification-repaired';negatives=[]
for name in ('substring-pass','duplicate-stats'):
    out=q/(name+'.stdout.txt');err=q/(name+'.stderr.txt');parsed=m.parse_tb_output(out,err)
    negatives.append({'name':name,'stdout_sha256':sha(out.read_bytes()),'stderr_sha256':sha(err.read_bytes()),
                      'accepted':m.positive_result(spec,{'record':{'exit':0},'parsed':parsed}),
                      'protocol_errors':parsed['protocol_errors']})
write(D/'A_ORIGINAL_RECLASSIFIED.json',negatives)
old=W/'competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author/run-main-repaired-20261020-15-a'
summary=json.loads((old/'RUN_SUMMARY.json').read_bytes());assert len(summary['commands'])==47
assert sha((old/'RUN_SUMMARY.json').read_bytes())=='1bc4a0db74686b8c6d5033052f4a626f9ba9d59cd5f954d43965a99754f4bf31'
records={r['name']:r for r in summary['commands']}
for r in records.values():
    for stream in ('stdout','stderr'):
        assert sha(Path(r[stream]).read_bytes())==r[stream+'_sha256']
def result(name):
    r=records[name];p=m.parse_tb_output(Path(r['stdout']),Path(r['stderr']))
    p.update(transcript=None,transcript_sha256=None,wlf=None,wlf_sha256=None)
    return {'record':r,'parsed':p}
observations=[]
for sp in m.POSITIVE_RUNS:
    r=result(sp['id']);observations.append({'name':sp['id'],'kind':'positive','accepted':m.positive_entry(sp,r)['passed'],
                                          'stats':r['parsed']['stats'],'protocol_errors':r['parsed']['protocol_errors']})
for mutant in m.MUTANT_SPECS:
    for sp in mutant['runs']:
        name=mutant['id']+'-g'+str(sp['group']);r=result(name)
        observations.append({'name':name,'kind':sp['expect'],'accepted':m.mutant_result(sp,r),
                             'stats':r['parsed']['stats'],'protocol_errors':r['parsed']['protocol_errors']})
# run_invalid delegates subprocess exclusively through run_command. Substitute
# its already completed exact receipt; enforce that no subprocess is executed.
def no_execute(*a,**kw):raise AssertionError('ModelSim/process execution forbidden during saved-log classification')
with __import__('unittest.mock',fromlist=['patch']).patch.object(m.subprocess,'run',no_execute):
    for sp in m.INVALID_RUNS:
        m.run_command=lambda *a,sp=sp,**kw:records[sp['id']]
        # Existing transcript/WLF refusal protects original directories.
        # Copy only immutable stdout/stderr into a new owned classification dir.
        d=D/'guard-logs'/sp['id'];d.mkdir(parents=True)
        for stream in ('stdout','stderr'):
            (d/(sp['id']+'.'+stream+'.txt')).write_bytes(Path(records[sp['id']][stream]).read_bytes())
        got=m.run_invalid(d,d,[],{'vsim':'NEVER_EXECUTE'},sp,1)
        observations.append({'name':sp['id'],'kind':'guard','accepted':got['passed']})
write(D/'SAVED_RUN_RECLASSIFIED.json',{'origin_summary_sha256':sha((old/'RUN_SUMMARY.json').read_bytes()),
 'saved_commands':len(records),'saved_stdout_stderr_verified':2*len(records),'new_simulator_commands':0,
 'observations':observations,'failed_count':sum(not r['accepted'] for r in observations),
 'positive_samples':sum(r['stats']['samples'] for r in observations if r['kind']=='positive')})
outcome={'unit_exit':unit,'portable_exit':portable_exit,'exact_A_negatives_rejected':sum(not r['accepted'] for r in negatives),
         'saved_scenarios':len(observations),'saved_scenarios_accepted':sum(r['accepted'] for r in observations),
         'runner_sha256':sha(runner.read_bytes()),'test_sha256':sha(test.read_bytes()),
         'new_ModelSim_commands':0,'scope':'Python terminal qualification and existing-log reclassification only'}
write(D/'RESULT.json',outcome);print(json.dumps(outcome))
sys.exit(0 if unit==portable_exit==0 and all(not r['accepted'] for r in negatives) and all(r['accepted'] for r in observations) else 1)
