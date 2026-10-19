"""Synthetic failure-injection of runner qualification; never invokes ModelSim.

Actual functions consume saved synthetic terminal states/text. A PASS marker is
insufficient after timeout/exception/nonzero normal execution; display-only
parameter text is insufficient without the wrapper's own fatal diagnostic.
"""
from pathlib import Path
import argparse,json,hashlib,importlib.util,datetime
ap=argparse.ArgumentParser();ap.add_argument('--runner',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();E=Path(__file__).parent
out=args.out.resolve();assert out.is_relative_to(E.resolve()) and not out.exists();out.mkdir()
source=out/'tested_runner.py';source.write_bytes(args.runner.read_bytes())
s=importlib.util.spec_from_file_location('runner_under_probe',source);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
cases=[]
spec={'id':'synthetic','group':0,'count_w':4,'witness_w':8,'tag_w':8,'loopback':0}
stats='TB_STATS groups=1 cases=1 samples=1 assertions=1 records=0 raw_faults=0 failure_events=0 window_starts=0 handshakes=0 mismatches=0\n'
for number,code in enumerate([0,1,2,'timeout','exception']):
 d=out/('positive-'+str(number));d.mkdir();text='TB_PASS\n'+stats;(d/'stdout.txt').write_text(text);(d/'stderr.txt').write_text('')
 parsed=m.parse_tb_output(d/'stdout.txt',d/'stderr.txt');parsed.update(transcript=None,transcript_sha256=None,wlf=None,wlf_sha256=None)
 rec={'exit':code,'stdout':str(d/'stdout.txt'),'stderr':str(d/'stderr.txt')};got=m.positive_entry(spec,{'record':rec,'parsed':parsed})['passed'];expect=type(code)is int and code==0
 cases.append({'kind':'positive_terminal_status','exit':code,'observed_pass':got,'expected_pass':expect,'matches':got==expect})
d=out/'positive-after-error';d.mkdir();(d/'stdout.txt').write_text('TB_PASS\n'+stats+'** Error: synthetic error after marker\n');(d/'stderr.txt').write_text('')
parsed=m.parse_tb_output(d/'stdout.txt',d/'stderr.txt');parsed.update(transcript=None,transcript_sha256=None,wlf=None,wlf_sha256=None)
got=m.positive_entry(spec,{'record':{'exit':0,'stdout':str(d/'stdout.txt'),'stderr':str(d/'stderr.txt')},'parsed':parsed})['passed'];cases.append({'kind':'positive_simulator_error_after_marker','observed_pass':got,'expected_pass':False,'matches':not got})
for code in [0,1,2,'timeout','exception']:
 for fatal in (False,True):
  name='guard-'+str(code)+'-'+str(int(fatal));d=out/name;d.mkdir();text='DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM COUNT_W=0 WITNESS_W=64 TAG_W=32 SAFE_COUNT_W=2 SAFE_WITNESS_W=64 SAFE_TAG_W=32\n'
  if fatal:text+='** Fatal: DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM unsupported widths\n'
  (d/(name+'.stdout.txt')).write_text(text);(d/(name+'.stderr.txt')).write_text('')
  m.run_command=lambda *a,**kw:{'exit':code,'synthetic':True}
  gs={'id':name,'count_w':0,'witness_w':64,'tag_w':32};got=m.run_invalid(d,d,[],{'vsim':'NEVER_EXECUTED'},gs,1)['passed'];expect=type(code)is int and code in(0,1) and fatal
  cases.append({'kind':'guard_terminal_and_fatal','exit':code,'own_fatal_present':fatal,'observed_pass':got,'expected_pass':expect,'matches':got==expect})
r={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'kind':'synthetic runner predicate failure injection; zero ModelSim commands','tested_runner_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'cases':cases,'mismatch_count':sum(not c['matches'] for c in cases),'status':'matches_fail_closed_contract' if all(c['matches'] for c in cases) else 'runner_qualification_defect_reproduced'}
(out/'result.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
