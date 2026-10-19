from pathlib import Path
import json,hashlib,subprocess,datetime
R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014';E=W/'competition/deepeye/evidence/control3d/pwm-edge-measure-20261020-13/main';P=R/'.local/venv/Scripts/python.exe'
sha=lambda b:hashlib.sha256(b).hexdigest()
rtl=W/'competition/deepeye/fpga/control3d/deepeye_pwm_edge_measure.sv';original=rtl.read_bytes();assert sha(original)=='f285268a83e5853f760c69255ab50af623116493a889637c3186cbd2f9da2187'
assert (E/'run-02/dut.sv').read_bytes()==original
M=E/'mutants';M.mkdir(exist_ok=False)
old=b'slot_high_q   <= high_q;';assert original.count(old)==1
mutants={'high-plus-one':original.replace(old,b"slot_high_q   <= high_q + 1'b1;")}
start=original.index(b'end else if (rearm) begin');end=original.index(b'end else if (armed_q) begin');block=original[start:end]
old=b"slot_valid_q    <= 1'b0;";assert block.count(old)==1
block=block.replace(old,b'slot_valid_q    <= slot_valid_q;')
for before,after in [(b"slot_period_q   <= '0;",b'slot_period_q   <= slot_period_q;'),(b"slot_high_q     <= '0;",b'slot_high_q     <= slot_high_q;'),(b'slot_tag_q      <= TAG_ZERO;',b'slot_tag_q      <= slot_tag_q;')]:
 assert block.count(before)==1;block=block.replace(before,after)
mutants['rearm-stale-slot']=original[:start]+block+original[end:]
r={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_rtl_sha256':sha(original),'mutants':[],'extra_invalid_parameters':[]}
for label,data in mutants.items():
 path=M/(label+'.sv');path.write_bytes(data)
 cmd=[P,'-B','-X','utf8',W/'competition/deepeye/tools/control3d/main_verify_pwm_edge_measure.py','--rtl',path,'--tb',W/'competition/deepeye/tests/rtl/control3d/main_tb_pwm_edge_measure.sv','--frozen',E/'frozen-harness-03','--out',E/('negative-'+label),'--owned-root',E,'--cases','2:1','--negative']
 cp=subprocess.run([str(x) for x in cmd],cwd=W,capture_output=True,timeout=90);(M/(label+'.stdout.txt')).write_bytes(cp.stdout);(M/(label+'.stderr.txt')).write_bytes(cp.stderr)
 assert cp.returncode==0
 outcome=json.loads((E/('negative-'+label)/'result.json').read_bytes());assert outcome['status']=='expected_public_port_rejection'
 r['mutants'].append({'label':label,'mutant_sha256':sha(data),'command':[str(x) for x in cmd],'exit_code':cp.returncode,'result_sha256':sha((E/('negative-'+label)/'result.json').read_bytes()),'stdout_sha256':sha(cp.stdout),'stderr_sha256':sha(cp.stderr),'rejected_at_public_ports':True})
# Additional zero/negative width boundaries use already compiled final main harness.
for w,t in [(0,32),(-1,32),(3,-1)]:
 label='extra-invalid-%s-%s'%(w,t);cmd=['D:/modelsim1/win64/vsim.exe','-c','-onfinish','stop','work.main_tb_pwm_edge_measure','-gCOUNT_W='+str(w),'-gTAG_W='+str(t),'+VECTORS=w2_t1.vectors.txt','+TRACE='+label+'.ports.txt','-do','w2_t1.do']
 cp=subprocess.run(cmd,cwd=E/'run-02',capture_output=True,timeout=60);(M/(label+'.stdout.txt')).write_bytes(cp.stdout);(M/(label+'.stderr.txt')).write_bytes(cp.stderr)
 expected=('PWM_EDGE_UNSUPPORTED_PARAMETERS COUNT_W=%d TAG_W=%d'%(w,t)).encode();assert expected in cp.stdout and b'** Fatal:' in cp.stdout and b'MAIN_EDGE_MEASURE_PASS' not in cp.stdout
 r['extra_invalid_parameters'].append({'count_w':w,'tag_w':t,'explicit_guard':True,'command':cmd,'cwd':str(E/'run-02'),'exit_code':cp.returncode,'stdout_sha256':sha(cp.stdout),'stderr_sha256':sha(cp.stderr)})
assert rtl.read_bytes()==original;r.update(original_unchanged=True,status='passed')
with (E/'negative_controls.json').open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
print(json.dumps(r))
