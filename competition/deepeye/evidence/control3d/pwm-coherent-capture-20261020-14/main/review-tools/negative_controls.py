from pathlib import Path
import datetime,hashlib,json,subprocess
O=Path(__file__).parent;R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014';M=W/'competition/deepeye/evidence/control3d/pwm-coherent-capture-20261020-14/main'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=M/'run-02/dut.sv';original=source.read_text();original_hash=sha(source)
runner=W/'competition/deepeye/tools/control3d/main_verify_pwm_coherent_capture.py';tb=W/'competition/deepeye/tests/rtl/control3d/main_tb_pwm_coherent_capture.sv';records=[]
needle='end else if (rise_mask != RISE_ALL) begin';assert original.count(needle)==1
relaxed=original.replace(needle,"end else if (1'b0) begin // MAIN MUTANT: every rising subset may close")
begin=original.index('end else if (rearm) begin');end=original.index('end else begin',begin)
segment=original[begin:end]
for field,old in [('slot_valid_q',"1'b0"),('slot_period_q','COUNT_ZERO'),('slot_high0_q','COUNT_ZERO'),('slot_high1_q','COUNT_ZERO'),('slot_high2_q','COUNT_ZERO'),('slot_start_q','WIT_ZERO'),('slot_end_q','WIT_ZERO'),('slot_tag_q','TAG_ZERO')]:
 import re
 pattern=rf'({field}\s*<=\s*){re.escape(old)};'
 segment,n=re.subn(pattern,rf'\g<1>{field}; // MAIN MUTANT: retain old queued field',segment);assert n==1,(field,n)
stale=original[:begin]+segment+original[end:]
for name,mutant,description in [('relaxed_common_R1',relaxed,'Treat any nonzero rising subset as shared completion after common R0; permits mixed end witnesses'),('stale_rearm_slot',stale,'Retain old whole result slot over rearm while combinational out_valid is temporarily suppressed')]:
 path=M/(name+'.sv');assert not path.exists();path.write_text(mutant,encoding='utf-8')
 out=M/('negative-'+name)
 args=[str(R/'.local/venv/Scripts/python.exe'),'-B','-X','utf8',str(runner),'--rtl',str(path),'--tb',str(tb),'--frozen',str(M/'frozen-harness02'),'--out',str(out),'--owned-root',str(M),'--cases','3:6:64','--negative']
 p=subprocess.run(args,cwd=W,capture_output=True,timeout=180)
 (M/(name+'.driver.stdout.txt')).write_bytes(p.stdout);(M/(name+'.driver.stderr.txt')).write_bytes(p.stderr)
 result=json.loads((out/'result.json').read_bytes());assert p.returncode==0 and result['status']=='expected_public_port_rejection'
 raw=(out/'c3_w6_t64.stdout.txt').read_bytes();assert b'PUBLIC_PORT_MISMATCH' in raw and b'MAIN_COHERENT_CAPTURE_PASS' not in raw
 records.append({'name':name,'description':description,'mutant_sha256':sha(path),'command':args,'driver_exit_code':p.returncode,'result_sha256':sha(out/'result.json'),'public_port_log_sha256':sha(out/'c3_w6_t64.stdout.txt'),'failure_lines':[s for s in raw.decode(errors='replace').splitlines() if 'PUBLIC_PORT_MISMATCH' in s]})
assert sha(source)==original_hash
receipt={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'passed','original_sha256':original_hash,'original_unchanged':True,'cases':records,'scope':'Two deliberately incorrect isolated copies rejected by actual main public-port simulation; not original RTL modifications or board evidence'}
with (M/'negative_controls.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
print(json.dumps(receipt))
