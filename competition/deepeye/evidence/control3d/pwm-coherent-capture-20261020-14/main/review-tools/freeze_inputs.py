from pathlib import Path
import hashlib,json,datetime,subprocess,importlib.util,sys
R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014';O=Path(__file__).parent;E=W/'competition/deepeye/evidence/control3d/pwm-coherent-capture-20261020-14/main';I=E/'inputs';I.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();pins=[]
for src in [O/'SCOPE.md',O/'SCOPE_FROZEN.json',O/'SCOPE_CONTINUE_CONSUMED.json',O.parent/'main-continuation-20261019-v1/SCOPE_REVIEW_DECISION_20261020_14.json']:
 (I/src.name).write_bytes(src.read_bytes());pins.append({'file':src.name,'sha256':sha(src)})
for name in ['immutable_scope.md','immutable_scope.json']:
 raw=subprocess.check_output(['git','-C',str(W),'show','f5989cd5defce561f9ba98e6b18fc2682945f0a2:docs/competition/deepeye-2026/'+name]);(I/name).write_bytes(raw);pins.append({'file':name,'sha256':sha(I/name)})
doc=json.loads((I/'immutable_scope.json').read_bytes());h=hashlib.sha256(json.dumps(doc['requirements'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest();assert h=='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
source=W/'competition/deepeye/tools/control3d/main_verify_pwm_coherent_capture.py';s=importlib.util.spec_from_file_location('coherent_reference',source);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
checks=[];tag=(1<<64)-1
o=m.Reference(2,6,64);assert o.sample(reset=1)==[0]*19
assert o.sample(rearm=1,tag=tag)==[0,1]+[0]*17
o.sample(levels=7,ready=0);o.sample(levels=2,ready=0);o.sample(levels=0,ready=0)
assert o.sample(levels=7,ready=0)==[0,1,1,3,1,2,1,1,4,tag]+[0]*9
checks.append('Literal start1/falls2,3,2/end4 -> period3/high1,2,1/full64tag')
o.sample(levels=0,ready=0)
assert o.sample(levels=7,ready=1)==[1,1,1,2,1,1,1,4,6,tag]+[0]*9
checks.append('Old retire/new fill uses next actual common edges4/6')
assert o.sample(rearm=1,levels=7,ready=1,tag=0)==[0,1]+[0]*17
for _ in range(8):assert o.sample(levels=7)==[0,1]+[0]*17
checks.append('Rearm suppresses old handshake and high baseline cannot generate start/period')
o=m.Reference(2,2,64);o.sample(reset=1);o.sample(rearm=1,tag=tag)
o.sample(levels=7,ready=0);o.sample(levels=0,ready=0)
assert o.sample(levels=7,ready=0)==[0,1,1,2,1,1,1,1,3,tag]+[0]*9
assert o.sample(levels=7,ready=0)==[1,0,1,2,1,1,1,1,3,tag,0,0,1,0,0,0,1,0,1]
assert o.sample(levels=0,ready=1)==[1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,1]
checks.append('Last representable end3, next edge witness fault, stable queued record, unarmed retirement')
o=m.Reference(2,3,1);o.sample(reset=1);o.sample(rearm=1)
for _ in range(3):o.sample(levels=0)
o.sample(levels=7)
for _ in range(3):o.sample(levels=0)
x=o.sample(levels=7);assert x[1]==0 and x[10:14]==[0,0,1,0] and x[-1]==1
checks.append('At would-be tick8/elapsed4, witness fault outranks count overflow; no restart')
o=m.Reference(3,6,1);o.sample(reset=1);o.sample(rearm=1)
for i in range(18):
 x=o.sample(levels=1<<(i%3));assert x[2]==0
assert o.events['candidates']==0 and o.events['incoherent']>0
checks.append('Equal-period phase-shifted one-hot lanes never form a common interval')
f=json.loads((E/'frozen-oracle/result.json').read_bytes());assert sum(x['sampled_edges'] for x in f['runs'])==800870
r={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'actual_thread':'01a13b55-095b-7461-8dd5-5476a130bd82','actual_App_turn':'01a154e7-12a1-7e12-ad4a-c4e2577b93b9','requirements_sha256':h,'input_files':pins,'frozen_result_sha256':sha(E/'frozen-oracle/result.json'),'author_implementation_read':False,'freeze_before_author_read':True,'hand_checked_literal_cases':checks,'sampled_edges':800870,'RLE_rows':sum(x['rle_rows'] for x in f['runs']),'primary_small_width_tuples':450,'repeated_tuples_with_shorter_witness':9,'random_samples':48000,'child_job_id':'child-ee0aedf1c857468891297b79118e6232','simulation':'not_run_at_freeze','formal_cards':'29 not_run'}
with (E/'oracle_frozen.json').open('x',encoding='utf-8') as out:json.dump(r,out,indent=2)
print(json.dumps(r))
