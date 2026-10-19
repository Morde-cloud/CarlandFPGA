from pathlib import Path
import hashlib,json,subprocess,sys,datetime
E=Path(__file__).parent;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
original=E/'negative_controls.py';s=original.read_text();old="aba=source.replace('endmodule',cache+'\\nendmodule')"
assert old in s
s=s.replace(old,"aba=source.replace('    assign cfg_ready      = g_cfg_ready;',cache+'\\n    assign cfg_ready      = g_cfg_ready;')")
s=s.replace("cases=[('late-transfer',late,start,target,'pre'),('same-tag-cache',aba,start,obs,'field=18'),('mismatch-admitted',mismatch,misstart,mis,'field=18')]","cases=[('same-tag-cache',aba,start,obs,'field=18'),('mismatch-admitted',mismatch,misstart,mis,'field=18')]")
s=s.replace("out=E/'negative-controls';out.mkdir()","out=E/'negative-controls-repair01';out.mkdir()")
s=s.replace("report['status']='three_actual_public_port_rejections'","report['status']='remaining_two_actual_public_port_rejections'")
dest=E/'negative_controls_repair01.py'
with dest.open('x',encoding='utf-8',newline='\n') as f:f.write(s)
r={'finding':'MAIN15-NEGATIVE-PREPARATION01','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_runner_sha256':sha(original),'repaired_runner_sha256':sha(dest),'original_result_sha256':sha(E/'negative-controls/result.json'),'reason':'Same-tag-cache faulty-copy declarations were below their first use; ModelSim10.7 compiled that copy with16 errors. Not counted as a valid negative control. Move the auxiliary cache declarations/always block before the first assign use. Keep correct DUT, model, frozen stimuli, TB and all original bytes unchanged. First late-transfer counterexample already completed and is not rerun.','original_correct_DUT_sha256':sha(E/'author-first-read/source.sv'),'frozen_receipt_sha256':sha(E/'frozen-oracle/result.json')}
with (E/'NEGATIVE_PREPARATION_CORRECTION.json').open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
cmd=[sys.executable,'-B','-X','utf8',str(dest)]
with (E/'negative-repair01.stdout.txt').open('xb') as out,(E/'negative-repair01.stderr.txt').open('xb') as err:p=subprocess.run(cmd,stdout=out,stderr=err)
with (E/'negative-repair01.command.json').open('x',encoding='utf-8') as f:json.dump({'command':cmd,'exit_code':p.returncode,'stdout_sha256':sha(E/'negative-repair01.stdout.txt'),'stderr_sha256':sha(E/'negative-repair01.stderr.txt')},f,indent=2)
print('exit',p.returncode);print((E/'negative-repair01.stdout.txt').read_text());print((E/'negative-repair01.stderr.txt').read_text());assert p.returncode==0
