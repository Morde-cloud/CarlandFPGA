from pathlib import Path
import hashlib,json,subprocess,sys,datetime
E=Path(__file__).parent;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();old=E/'negative_controls_repair01.py';s=old.read_text()
needle='wire bad_replay = window_started_q && bad_saved_valid &&';assert needle in s
s=s.replace(needle,'wire bad_replay = !rst && !stop && window_started_q && bad_saved_valid &&')
s=s.replace("out=E/'negative-controls-repair01';out.mkdir()","out=E/'negative-controls-repair02';out.mkdir()")
dest=E/'negative_controls_repair02.py'
with dest.open('x',encoding='utf-8',newline='\n') as f:f.write(s)
r={'finding':'MAIN15-NEGATIVE-PREPARATION02','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'previous_runner_sha256':sha(old),'new_runner_sha256':sha(dest),'previous_result_sha256':sha(E/'negative-controls-repair01/result.json'),'reason':'The repaired same-tag mutant compiled but its intentionally added cache bypass exposed uninitialized X before the first sampled reset. This is not the required same-tag boundary counterexample. Add explicit reset/stop masking to the faulty cache bypass only. Do not change production RTL, frozen oracle/inputs/TB or accept the wrong counterexample. Preserve all prior failed preparations.'}
with (E/'NEGATIVE_PREPARATION_CORRECTION02.json').open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
cmd=[sys.executable,'-B','-X','utf8',str(dest)]
with (E/'negative-repair02.stdout.txt').open('xb') as out,(E/'negative-repair02.stderr.txt').open('xb') as err:p=subprocess.run(cmd,stdout=out,stderr=err)
with (E/'negative-repair02.command.json').open('x',encoding='utf-8') as f:json.dump({'command':cmd,'exit_code':p.returncode,'stdout_sha256':sha(E/'negative-repair02.stdout.txt'),'stderr_sha256':sha(E/'negative-repair02.stderr.txt')},f,indent=2)
print('exit',p.returncode);print((E/'negative-repair02.stdout.txt').read_text());print((E/'negative-repair02.stderr.txt').read_text());assert p.returncode==0
