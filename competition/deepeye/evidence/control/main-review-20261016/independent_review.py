import argparse, hashlib, importlib.util, itertools, json, random, subprocess, sys
from pathlib import Path

parser=argparse.ArgumentParser();parser.add_argument('--output-root',required=True);parser.add_argument('--expect',choices=['defects','fixed'],required=True);args=parser.parse_args()
HERE=Path(__file__).resolve().parent;WT=HERE.parents[4];BASE=WT/'competition/deepeye'
OUT=Path(args.output_root).resolve();OUT.mkdir();src=BASE/'golden/control/capture_snapshot_reference.py'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source_sha=sha(src)
spec=importlib.util.spec_from_file_location('candidate',src);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
argv=[sys.executable,'-B','-X','utf8','-m','unittest','discover','-s','competition/deepeye/tests/control','-p','test_capture_snapshot.py','-v']
p=subprocess.run(argv,cwd=WT,capture_output=True,timeout=60)
(OUT/'baseline.stdout.txt').write_bytes(p.stdout);(OUT/'baseline.stderr.txt').write_bytes(p.stderr)
assert p.returncode==0,p.stderr.decode(errors='replace')
def model():
    x=m.CaptureSnapshotModel();x.begin_session(1);x.begin_epoch(0);x.enable();x.apply_request(1);return x
def ev(ch,batch=1,req=1,period=2000000,code=0):
    high=50000+1000*code if ch=='speed' else 250000+16*code
    return m.ChannelEvidence.create(ch,1,0,req,batch,period,high)
def publish(x,batch=1,req=1,codes=(0,0,0)):
    for ch,code in zip(('yaw','pitch','speed'),codes):x.submit_evidence(ev(ch,batch,req,code=code))
    return x.publish_snapshot()
def must_error(fn):
    try:fn()
    except m.ControlCandidateError:return
    raise AssertionError('required fail-closed exception missing')
findings=[]
class ForgedPeriod(int):
    def __sub__(self,other):return 0
x=model()
try:
    s=None
    for ch in ('yaw','pitch','speed'):x.submit_evidence(ev(ch,period=ForgedPeriod(0)))
    s=x.publish_snapshot()
    if x.eligibility and int(s.period_yaw)==0:findings.append({'id':'B-CONTROL-SCALAR05','period':int(s.period_yaw),'eligible':x.eligibility,'reproduction':'int subclass overrides subtraction; period 0 treated valid'})
except m.ValidationError:pass
x=model();s=publish(x);before=s.word_view();object.__setattr__(s,'yaw_q',12345);after=x.latest_published().word_view()
if after!=before:findings.append({'id':'B-CONTROL-OUTPUT06','before':before,'after':after,'mutated_history_consistent':x.words_consistent(after),'reproduction':'caller-retained publish_snapshot result aliases internal published/history'})
x=model();publish(x);reader=x.latest_published();before=x.begin_frozen_read().words;object.__setattr__(reader,'high_yaw',0);object.__setattr__(reader,'yaw_q',12345)
if x.begin_frozen_read().words!=before:findings.append({'id':'B-CONTROL-OUTPUT06-latest','reproduction':'latest_published returns internal snapshot; caller changes future frozen reads'})
counts={}
orders=list(itertools.permutations(('yaw','pitch','speed')))
for order in orders:
    for at in range(4):
        x=model();inputs=[ev(ch) for ch in order]
        for e in inputs[:at]:x.submit_evidence(e)
        x.stop('main-order')
        for e in inputs[at:]:must_error(lambda e=e:x.submit_evidence(e))
        must_error(x.publish_snapshot);assert not x.eligibility
        x.enable()
        for e in inputs:must_error(lambda e=e:x.submit_evidence(e))
        must_error(x.publish_snapshot);assert not x.eligibility
        x.apply_request(2);s=publish(x,2,2);assert s.batch_key.request_seq==2 and x.eligibility
counts['stop_positions_orders']=24
# Independently derive expected nearest legal PWM code and acceptance at +/-3.
n=0
for code in range(-15000,15001):
    for jitter in range(-3,4):
        result=m.classify_high_count('yaw',250000+16*code+jitter,2000000)
        assert result['decoded_code']==code
        assert result['accepted']==(abs(jitter)<=2)
        assert not result['hardware_enable_eligible'];n+=1
counts['angle_grid']=n
for code in range(21):
    for jitter in range(-3,4):
        result=m.classify_high_count('speed',50000+1000*code+jitter,2000000)
        assert result['decoded_code']==code and result['accepted']==(abs(jitter)<=2)
counts['speed_grid']=147
rng=random.Random(20261016)
for i in range(300):
    x=model();codes=(rng.randint(-15000,15000),rng.randint(-15000,15000),rng.randrange(21));order=orders[i%6];inputs={ch:ev(ch,code=codes[j]) for j,ch in enumerate(('yaw','pitch','speed'))}
    for ch in order:x.submit_evidence(inputs[ch])
    for e in inputs.values():object.__setattr__(e,'decoded_code',999999);object.__setattr__(e.batch_key,'request_seq',500)
    s=x.publish_snapshot();assert (s.yaw_q,s.pitch_q,s.speed_code)==codes and s.batch_key.as_tuple()==(1,0,1,1)
    old=x.begin_frozen_read();oldwords=old.words;x.stop();assert old.words==oldwords and not old.coherent
counts['random_ingress_aliases']=300
for event in ('stop','reset','fault','epoch','session','apply','cycle'):
    x=model();publish(x);f=x.begin_frozen_read();w=f.words
    if event=='stop':x.stop()
    elif event=='reset':x.reset()
    elif event=='fault':x.set_fault(0)
    elif event=='epoch':x.begin_epoch(1)
    elif event=='session':x.begin_session(2)
    elif event=='apply':x.apply_request(2)
    else:x.submit_evidence(ev('yaw',2))
    assert not f.coherent and w==f.words,(event,f.as_dict())
counts['revocation_events']=7
x=model()
for i in range(1,1001):publish(x,i,codes=(i,-i,i%21))
assert x.history_len<=8 and x.published_count==1000
counts['bounded_publications']=1000
if args.expect=='fixed':
    assert not findings,findings
    class IntSubclass(int):pass
    class StrSubclass(str):pass
    for f in [lambda:m.BatchKey(IntSubclass(1),0,1,1),lambda:ev('yaw',period=IntSubclass(2000000)),lambda:ev(StrSubclass('yaw')),lambda:m.CaptureSnapshotModel().begin_session(IntSubclass(1))]:must_error(f)
    x=model();s=publish(x);original=x.begin_frozen_read().words;object.__setattr__(s,'yaw_q',12345);assert x.begin_frozen_read().words==original
    r=x.latest_published();object.__setattr__(r,'yaw_q',12345);assert x.begin_frozen_read().words==original and x.words_consistent(original)
    counts['strict_subclass_output_checks']=6
else:assert len(findings)==3,findings
assert sha(src)==source_sha
result={'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'work_id':'B-CONTROL-MAIN-BOUNDARY-20261016-03','source_sha256':source_sha,'baseline':{'argv':argv,'exit':p.returncode,'stderr_sha256':sha(OUT/'baseline.stderr.txt')},'independent_counts':counts,'findings':findings,'decision':'reject' if findings else 'software_foundation_pass_only','not_claimed':['B05','R03','CDC','RTL','hardware','system']}
(OUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
