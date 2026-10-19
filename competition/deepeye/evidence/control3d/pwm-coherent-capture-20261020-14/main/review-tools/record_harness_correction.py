from pathlib import Path
import ast,datetime,hashlib,json,difflib
O=Path(__file__).parent;W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014');M=W/'competition/deepeye/evidence/control3d/pwm-coherent-capture-20261020-14/main'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=M/'frozen-oracle/runner.py';new=W/'competition/deepeye/tools/control3d/main_verify_pwm_coherent_capture.py'
assert sha(old)=='3cafe531fa0dab2ffb937f57ed1e107ad44cb1e7287da200028323392c774ac5'
assert sha(new)=='89919ae706090d0b78eb8df2d4f731a4454c97947da509162fc3200f59ad1de6'
def parts(p):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in ['Reference','stimuli','vector_bytes']}
assert parts(old)==parts(new)
vectors=[]
for p in (M/'frozen-oracle').glob('*.vectors.txt'):
 assert p.read_bytes()==(M/'frozen-harness02'/p.name).read_bytes()==(M/'run-01'/p.name).read_bytes()
 vectors.append({'name':p.name,'sha256':sha(p)})
assert len(vectors)==6
r=json.loads((M/'run-01/result.json').read_bytes());assert r['status']=='failed' and all(x['passed'] for x in r['runs'])
receipt={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'finding':'MAIN14-DIAGNOSTIC01','decision':'Harness-only correction; no change to oracle, stimuli, expected ports, testbench or RTL','original_failure':'The checker required exact parameter values on the fatal line. DUT emits a preceding exact parameter display then its own explicit fatal at time zero. That satisfies the frozen contract.','replacement':'Require exact DUT fatal marker AND exact parameter display before that fatal; unrelated compile/elaboration failure does not qualify.','original_frozen_sha256':sha(M/'frozen-oracle/result.json'),'original_main_run_sha256':sha(M/'run-01/result.json'),'original_runner_sha256':sha(old),'corrected_runner_sha256':sha(new),'main_tb_sha256':sha(M/'frozen-oracle/tb.sv'),'AST_reference_stimuli_vectors_identical':True,'vectors':vectors,'chronology':'Original oracle_frozen.json was read and confirmed before first author RTL read in tool df4153. This correction and frozen-harness02 were made AFTER that read. No pre-author chronology is claimed for harness02.','source_snapshot_during_active_child_sha256':r['rtl_sha256'],'not_terminal_acceptance':True}
with (M/'HARNESS_CORRECTION.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
(M/'harness-correction.diff').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),new.read_text().splitlines(True),fromfile='frozen-oracle/runner.py',tofile='corrected-runner.py')),encoding='utf-8')
print(json.dumps({'correction_sha256':sha(M/'HARNESS_CORRECTION.json'),'vectors':len(vectors)}))
