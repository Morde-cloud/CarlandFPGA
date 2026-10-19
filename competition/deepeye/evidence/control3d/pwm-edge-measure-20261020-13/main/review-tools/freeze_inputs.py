from pathlib import Path
import hashlib,json,datetime,subprocess,importlib.util,sys
R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014';N=Path(__file__).resolve().parent
E=W/'competition/deepeye/evidence/control3d/pwm-edge-measure-20261020-13/main';I=E/'inputs';I.mkdir(exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
pins=[]
for src in [N/'SCOPE.md',N/'SCOPE_FROZEN.json',N/'SCOPE_CONTINUE_CONSUMED.json',N.parent/'main-continuation-20261019-v1/SCOPE_REVIEW_DECISION_20261020_13.json']:
 b=src.read_bytes();(I/src.name).write_bytes(b);pins.append({'file':src.name,'sha256':sha(b)})
for name in ['immutable_scope.md','immutable_scope.json']:
 b=subprocess.check_output(['git','-C',str(W),'show','f5989cd5defce561f9ba98e6b18fc2682945f0a2:docs/competition/deepeye-2026/'+name]);(I/name).write_bytes(b);pins.append({'file':name,'sha256':sha(b)})
d=json.loads((I/'immutable_scope.json').read_bytes());h=sha(json.dumps(d['requirements'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode());assert h=='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
f=E/'frozen-oracle/result.json';model=W/'competition/deepeye/tools/control3d/main_verify_pwm_edge_measure.py';spec=importlib.util.spec_from_file_location('edge_reference',model);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
checks=[]
# Literal hand-worked tuples: pre/armed/valid/period/high/tag/ov/rr/seen/seen/loss.
o=m.Reference(2,64)
assert o.sample(reset=1)==[0,0,0,0,0,0,0,0,0,0,0]
assert o.sample(rearm=1,tag=0xffffffffffffffff)==[0,1,0,0,0,0,0,0,0,0,0]
o.sample(level=1,ready=0);o.sample(level=0,ready=0)
assert o.sample(level=1,ready=0)==[0,1,1,2,1,0xffffffffffffffff,0,0,0,0,0]
checks.append('literal minimum-period and full64 tag')
o.sample(level=1,ready=0);o.sample(level=1,ready=0);o.sample(level=1,ready=0)
assert o.sample(level=1,ready=0)==[1,1,1,2,1,0xffffffffffffffff,1,0,1,0,1]
checks.append('old record preserved at elapsed4 > MAX3')
assert o.sample(rearm=1,level=1,tag=0)==[0,1,0,0,0,0,0,0,0,0,0]
for _ in range(10):assert o.sample(level=1)==[0,1,0,0,0,0,0,0,0,0,0]
checks.append('flush and high baseline do not create a start')
o.sample(level=0);o.sample(level=1);o.sample(level=0)
assert o.sample(level=0)==[0,1,0,0,0,0,0,0,0,0,0]
assert o.sample(level=1,ready=0)==[0,1,1,3,1,0,0,0,0,0,0]
checks.append('literal maximum3 period accepted')
o.sample(level=0,ready=0)
assert o.sample(level=1,ready=1)==[1,1,1,2,1,0,0,0,0,0,0]
checks.append('same-edge old retire and new fill')
assert o.sample(level=1,ready=1)==[1,1,0,0,0,0,0,0,0,0,0]
checks.append('consume without replacement zeroes payload')
receipt={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'requirements_sha256':h,'frozen_result_sha256':sha(f.read_bytes()),'input_files':pins,'oracle_hand_checked_cases':checks,'author_implementation_read':False,'freeze_before_author_read':True,'child_job_id':'child-7cc873906b4f4f56992d01d99ce71fcd','scope_decision':'CONTINUE','formal_cards':'29 not_run'}
with (E/'oracle_frozen.json').open('x',encoding='utf-8') as o:json.dump(receipt,o,indent=2)
print(json.dumps(receipt))
