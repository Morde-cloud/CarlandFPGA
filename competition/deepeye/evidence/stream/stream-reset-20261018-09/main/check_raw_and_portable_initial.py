import hashlib,importlib.util,json,shutil,subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent;W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
RUN=W/'competition/deepeye/tools/stream/run_block_stream.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p,name):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def save(p,j):
    with p.open('x',encoding='utf-8') as f:json.dump(j,f,indent=2);f.write('\n')
expected_out=b'\xff\r\nNUL\x00tail';expected_err=b'\x80\r\nerr'
program='import os;os.write(1,bytes([255,13,10,78,85,76,0,116,97,105,108]));os.write(2,bytes([128,13,10,101,114,114]))'
timeout_program='import os,time;os.write(1,b"partial\\r\\n");os.write(2,b"err\\r\\n");time.sleep(2)'
raw_results=[]
for name,path in [('original',H/'worker-original-tooling/run_block_stream.py'),('corrected',RUN)]:
    m=load(path,'runner_'+name);out=H/('raw-pipe-'+name);out.mkdir(exist_ok=False)
    a,_,_=m.run_tool('bytes',[sys.executable,'-B','-c',program],out,out,5)
    b,_,_=m.run_tool('timeout',[sys.executable,'-B','-c',timeout_program],out,out,0.35)
    raw_ok=(out/'bytes.stdout.log').read_bytes()==expected_out and (out/'bytes.stderr.log').read_bytes()==expected_err
    timeout_ok=(out/'timeout.stdout.log').read_bytes()==b'partial\r\n' and (out/'timeout.stderr.log').read_bytes()==b'err\r\n'
    assert a['exit_code']==0 and b['timed_out']
    assert raw_ok==(name=='corrected') and timeout_ok==(name=='corrected')
    result={'variant':name,'runner_sha256':sha(path),'byte_preserving':raw_ok,'timeout_partial_preserving':timeout_ok,'calls':[a,b]};save(out/'result.json',result);raw_results.append(result)
flat=H/'portable inputs with spaces';flat.mkdir(exist_ok=False)
inputs={'core':W/'competition/deepeye/fpga/codec/deepeye_block_encoder.sv','wrapper':W/'competition/deepeye/fpga/stream/deepeye_block_stream.sv','tb':W/'competition/deepeye/tests/stream/tb_block_stream.sv','golden':W/'competition/deepeye/golden/codec/codec_reference.py','spec':H/'main_stream_spec.md','runner':RUN}
for p in inputs.values():shutil.copyfile(p,flat/p.name)
before={p.name:sha(flat/p.name) for p in inputs.values()}
out=H/'portable output with spaces'
cmd=[sys.executable,'-B','-X','utf8',str(flat/RUN.name)]
for key in ['core','wrapper','tb','golden','spec']:cmd+=['--'+key,str(flat/inputs[key].name)]
cmd+=['--output',str(out),'--owned-root',str(H),'--timeout','60']
for tool in ['vlib','vlog','vsim']:cmd+=['--'+tool,'D:/modelsim1/win64/'+tool+'.exe']
def call(name,args):
    p=subprocess.run(args,cwd=flat,capture_output=True,timeout=65)
    (H/(name+'.stdout.txt')).write_bytes(p.stdout);(H/(name+'.stderr.txt')).write_bytes(p.stderr)
    row={'command':args,'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()};save(H/(name+'.json'),row);return row
row=call('main-portable-run',cmd);assert row['exit_code']==0
summary=json.loads((out/'run_summary.json').read_bytes());assert summary['status']=='PASS' and summary['summary']['cases']==54
snap={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()}
guard1=call('guard-existing-output',cmd);assert guard1['exit_code']==2
alias=cmd.copy();alias[alias.index('--tb')+1]=alias[alias.index('--wrapper')+1];alias[alias.index('--output')+1]=str(H/'alias-output-must-not-exist')
guard2=call('guard-input-alias',alias);assert guard2['exit_code']==2 and not (H/'alias-output-must-not-exist').exists()
assert snap=={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()}
assert before=={p.name:sha(flat/p.name) for p in inputs.values()}
for tool in summary['commands']:
    assert sha(out/tool['stdout'])==tool['stdout_sha256'] and sha(out/tool['stderr'])==tool['stderr_sha256']
receipt={'status':'PASS_RAW_BYTES_TIMEOUT_PORTABLE_AND_GUARDS','original_defect_reproduced':True,'raw_results':raw_results,'portable_cases':summary['summary']['cases'],'portable_checks':summary['summary']['checks'],'runner_sha256':sha(RUN),'wrapper_sha256':sha(inputs['wrapper']),'flat_inputs':before,'summary_sha256':sha(out/'run_summary.json'),'input_and_prior_output_bytes_preserved':True,'guard_exit_codes':[guard1['exit_code'],guard2['exit_code']]}
save(H/'PORTABILITY_AND_RAW_CAPTURE.json',receipt)
print(json.dumps({k:v for k,v in receipt.items() if k not in ('raw_results','flat_inputs')}))
