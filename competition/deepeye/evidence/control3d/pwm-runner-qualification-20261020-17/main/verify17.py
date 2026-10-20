"""Main expected-case audit; Python only, no new simulator or hardware run."""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,subprocess,sys
from unittest.mock import patch
ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
args=ap.parse_args();W=args.root.resolve();D=args.out.resolve();D.mkdir()
E=W/'competition/deepeye/evidence/control3d/pwm-runner-qualification-20261020-17'
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def load(p,name):
    s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def invoke(module,kind,stdout,stderr,code,spec,d):
    d.mkdir(exist_ok=True)
    out=d/'case.stdout.txt';err=d/'case.stderr.txt';out.write_bytes(stdout);err.write_bytes(stderr)
    before=(sha(out.read_bytes()),sha(err.read_bytes()))
    record={'exit':code,'synthetic_process_receipt':True,'stdout':str(out),'stderr':str(err)}
    with patch.object(module.subprocess,'run',side_effect=AssertionError('no simulator/process allowed in classifier')):
        if kind=='guard':
            with patch.object(module,'run_command',return_value=record):
                result=module.run_invalid(d,d,[],{'vsim':'NEVER_EXECUTE'},{'id':'case',**spec},1)
            accepted=result['passed']
        else:
            result=module.parse_tb_output(out,err)
            accepted=module.positive_result(spec,{'record':record,'parsed':result})
    assert before==(sha(out.read_bytes()),sha(err.read_bytes()))
    return accepted,result
runner=W/'competition/deepeye/tools/control3d/run_pwm_applied_capture.py'
raw=runner.read_bytes();(D/'tested_runner.py').write_bytes(raw)
m=load(runner,'current_runner17');baseline=load(E/'inputs/run_pwm_applied_capture.py','baseline_runner17')
freeze=json.loads((E/'main/FREEZE.json').read_bytes())
assert sha((E/'main/FROZEN_CASES.json').read_bytes())==freeze['cases_sha256']
cases=json.loads((E/'main/FROZEN_CASES.json').read_bytes())
original_case_count=len(cases)
supplemental=json.loads((E/'main/GUARD_REQUEST_ELIGIBILITY_REVIEW.json').read_bytes())
assert sha((E/'main/SUPPLEMENTAL_EXPECTED_CASES.json').read_bytes())==supplemental['supplemental_cases_sha256']
cases+=json.loads((E/'main/SUPPLEMENTAL_EXPECTED_CASES.json').read_bytes())
results=[]
for c in cases:
    stdout=c['stdout'].encode();stderr=c['stderr'].encode()
    assert sha(stdout)==c['stdout_sha256'] and sha(stderr)==c['stderr_sha256']
    actual,r=invoke(m,c['kind'],stdout,stderr,c['exit'],c['spec'],D/'work')
    results.append({'id':c['id'],'expected':c['expected'],'accepted':actual,
                    'matches':actual==c['expected'],'input_stdout_sha256':sha(stdout),
                    'input_stderr_sha256':sha(stderr),'synthetic_exit':c['exit'],
                    'diagnostic':r.get('diagnostic'),'protocol_errors':r.get('protocol_errors')})
write(D/'INDEPENDENT_CASE_RESULTS.json',results)
exact=[]
for name,kind,code,spec in [
 ('030-invalid-count-zero.stdout.txt','guard',1,{'count_w':0,'witness_w':64,'tag_w':32}),
 ('032-invalid-count-zero.stdout.txt','guard',1,{'count_w':0,'witness_w':64,'tag_w':32}),
 ('026-case.stdout.txt','positive',0,{'group':0,'loopback':0})]:
    b=(E/'inputs'/name).read_bytes()
    old,old_result=invoke(baseline,kind,b,b'',code,spec,D/'exact-baseline')
    new,new_result=invoke(m,kind,b,b'',code,spec,D/'exact-current')
    exact.append({'input':name,'stdout_sha256':sha(b),'stderr_sha256':sha(b''),'synthetic_exit':code,
                  'baseline_accepted':old,'repaired_accepted':new,'baseline_result':old_result,'repaired_result':new_result})
write(D/'EXACT_A_BEFORE_AFTER.json',exact)
prior=[]
q=W/'competition/deepeye/evidence/control3d/pwm-runner-qualification-20261020-16/a-original/op15/review/qualification-repaired'
for name in ('substring-pass','duplicate-stats'):
    b=(q/(name+'.stdout.txt')).read_bytes();err=(q/(name+'.stderr.txt')).read_bytes()
    got,r=invoke(m,'positive',b,err,0,{'group':0,'loopback':0},D/'old-op16')
    prior.append({'name':name,'stdout_sha256':sha(b),'stderr_sha256':sha(err),'accepted':got,'protocol_errors':r['protocol_errors']})
write(D/'ORIGINAL_OP16_NEGATIVES.json',prior)
old=W/'competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author/run-main-repaired-20261020-15-a'
summaryraw=(old/'RUN_SUMMARY.json').read_bytes();assert sha(summaryraw)=='1bc4a0db74686b8c6d5033052f4a626f9ba9d59cd5f954d43965a99754f4bf31'
summary=json.loads(summaryraw);commands={r['name']:r for r in summary['commands']};streams=[]
def stream(r,name):
    # Preserve Windows receipt identity while allowing portable checkout paths.
    p=old/'logs'/r[name].replace('\\','/').split('/')[-1];b=p.read_bytes()
    assert sha(b)==r[name+'_sha256']
    return p,b
for r in commands.values():
    for name in ('stdout','stderr'):
        p,b=stream(r,name);streams.append({'path':p.relative_to(W).as_posix(),'bytes':len(b),'sha256':sha(b),'command':r['name'],'original_exit':r['exit']})
def saved(name):
    rec=commands[name];out,_=stream(rec,'stdout');err,_=stream(rec,'stderr')
    parsed=m.parse_tb_output(out,err);return {'record':rec,'parsed':parsed}
classified=[]
for sp in m.POSITIVE_RUNS:
    result=saved(sp['id']);classified.append({'name':sp['id'],'kind':'positive','accepted':m.positive_result(sp,result),'stats':result['parsed']['stats'],'protocol_errors':result['parsed']['protocol_errors']})
for mutant in m.MUTANT_SPECS:
    for sp in mutant['runs']:
        name=mutant['id']+'-g'+str(sp['group']);result=saved(name)
        classified.append({'name':name,'kind':sp['expect'],'accepted':m.mutant_result(sp,result),'protocol_errors':result['parsed']['protocol_errors']})
for sp in m.INVALID_RUNS:
    rec=commands[sp['id']];_,out=stream(rec,'stdout');_,err=stream(rec,'stderr')
    got,result=invoke(m,'guard',out,err,rec['exit'],{k:v for k,v in sp.items() if k!='id'},D/'saved-guard')
    classified.append({'name':sp['id'],'kind':'guard','accepted':got,'protocol_errors':result['protocol_errors']})
write(D/'SAVED_STREAMS.json',streams)
write(D/'SAVED_33_CLASSIFICATION.json',{'summary_sha256':sha(summaryraw),'old_command_count':len(commands),'stream_count':len(streams),'scenarios':classified,'new_simulator_commands':0,'old_positive_samples':sum(r['stats']['samples'] for r in classified if r['kind']=='positive')})
# Run the exact unchanged original23 tests against the new runner in isolation.
portable=D/'original23';pr=portable/'competition/deepeye/tools/control3d/run_pwm_applied_capture.py';pt=portable/'competition/deepeye/tests/control/test_pwm_applied_capture_runner.py'
pr.parent.mkdir(parents=True);pt.parent.mkdir(parents=True);pr.write_bytes(raw);pt.write_bytes((E/'inputs/test_pwm_applied_capture_runner.py').read_bytes())
start=datetime.datetime.now(datetime.timezone.utc).isoformat();cmd=[sys.executable,'-B','-X','utf8',str(pt)]
p=subprocess.run(cmd,cwd=portable,capture_output=True,timeout=60)
(D/'original23.stdout.txt').write_bytes(p.stdout);(D/'original23.stderr.txt').write_bytes(p.stderr)
write(D/'ORIGINAL23_COMMAND.json',{'argv':cmd,'cwd':str(portable),'started_utc':start,'exit_code':p.returncode,
 'stdout_sha256':sha(p.stdout),'stderr_sha256':sha(p.stderr),'test_sha256':sha(pt.read_bytes()),'runner_sha256':sha(raw)})
assert runner.read_bytes()==raw
good=(all(r['matches'] for r in results) and all(r['baseline_accepted'] and not r['repaired_accepted'] for r in exact)
      and all(not r['accepted'] for r in prior) and all(r['accepted'] for r in classified) and p.returncode==0)
receipt={'status':'PASS' if good else 'FAIL','tested_runner_sha256':sha(raw),'frozen_cases_sha256':freeze['cases_sha256'],
 'original_frozen_case_count':original_case_count,'supplemental_cases':len(cases)-original_case_count,
 'supplemental_cases_sha256':supplemental['supplemental_cases_sha256'],
 'independent_cases':len(results),'independent_expected_accept':sum(c['expected'] for c in cases),
 'independent_mismatches':sum(not r['matches'] for r in results),'exact_A_baseline_accepts':sum(r['baseline_accepted'] for r in exact),
 'exact_A_repaired_rejects':sum(not r['repaired_accepted'] for r in exact),'original_op16_negatives_rejected':sum(not r['accepted'] for r in prior),
 'original23_exit':p.returncode,'original23_test_sha256':sha(pt.read_bytes()),
 'old_commands':len(commands),'old_streams':len(streams),'old_scenarios':len(classified),'old_scenarios_accepted':sum(r['accepted'] for r in classified),
 'new_ModelSim_commands':0,'new_hardware_commands':0}
write(D/'RESULT.json',receipt);print(json.dumps(receipt))
sys.exit(0 if good else 1)
