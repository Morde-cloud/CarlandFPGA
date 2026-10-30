"""Private B77 three-point fresh-only semantic contract; no planner/control.

The unchanged fixed TRACE parser owns code interpretation. Hashes associate
synthetic records; they do not authenticate Root/BOOT/ADC or release movement.
"""
import sys
sys.dont_write_bytecode=True
import binascii,hashlib,importlib.util,json,re,struct
from pathlib import Path
PROFILE='B77-PRIVATE-THREE-FRESH-RELATIVE1US-V1'
FIXED_PATH='competition/deepeye/golden/codec/trace_candidate.py'
FIXED_SHA='a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642'
U63=(1<<63)-1;U32=(1<<32)-1
STABLE={'operation_id','kernel_boot_id','session_id','clock_domain_id','request_hash','tested_commit','build_manifest_sha256'}
IDENTITY=STABLE|{'source_record_sha256','capture_sha256','tag','generation','trigger_id','request_seq','capture_seq','source_admission_index'}
RECORD={'channel','index','native_tag','native_first_seq','native_last_seq','acquisition_qpc_ns','source_qpc_ns','remainder_ns','raw_quality','original_value','valid','held','source_identity'}
class Rejected(ValueError):pass
def need(ok,why):
    if not ok:raise Rejected(why)
def canonical(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def digest(obj):return hashlib.sha256(canonical(obj)).hexdigest()
def uint(x,maxval,label):need(type(x)is int and 0<=x<=maxval,label);return x
def obj(x,keys,label):need(type(x)is dict and set(x)==keys,label);return x
def plain(x,depth=0,budget=None):
    if budget is None:budget=[4096]
    budget[0]-=1;need(depth<=12 and budget[0]>=0,'bounded JSON')
    need(type(x)in(type(None),bool,int,str,list,dict),'plain JSON types')
    if type(x)is str:need(len(x)<=192,'string bound')
    if type(x)is list:
        need(len(x)<=12,'list bound')
        for y in x:plain(y,depth+1,budget)
    if type(x)is dict:
        need(len(x)<=32 and all(type(k)is str for k in x),'dictionary bound')
        for k,y in x.items():plain(k,depth+1,budget);plain(y,depth+1,budget)
def identity(x):
    obj(x,IDENTITY,'full per-sample identity')
    for k in ['operation_id','kernel_boot_id','session_id','clock_domain_id']:
        need(type(x[k])is str and 1<=len(x[k])<=192 and all(32<=ord(c)<=126 for c in x[k]),'identity text')
    for k in ['request_hash','build_manifest_sha256','source_record_sha256','capture_sha256','tested_commit']:
        need(type(x[k])is str and re.fullmatch('[0-9a-f]{%d}'%(40 if k=='tested_commit' else 64),x[k])is not None,'identity hash')
    for k in IDENTITY-STABLE-{'source_record_sha256','capture_sha256'}:uint(x[k],U32,'identity '+k)
    need(all(x[k]>0 for k in ['tag','generation','request_seq']),'nonzero identity')
def fixed(root):
    p=Path(root)/FIXED_PATH;raw=p.read_bytes();need(hashlib.sha256(raw).hexdigest()==FIXED_SHA,'fixed decoder hash')
    s=importlib.util.spec_from_file_location('_b77_fixed_trace',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def decode(packet,*,companion=None,binding=None,now_qpc_ns=None,repo_root=None,enabled=False):
    need(type(enabled)is bool,'enabled bool')
    stop=dict(status='STOP',core_ran=False,command=None,authorization='none',authentication='NOT_ESTABLISHED_BY_JSON_OR_HASHES')
    if not enabled:return dict(stop,input_status='DISABLED')
    if companion is None or binding is None or now_qpc_ns is None or repo_root is None:return dict(stop,input_status='INPUT_UNAVAILABLE')
    need(type(packet)is bytes and 39<=len(packet)<=46,'bounded full packet')
    plain(companion);plain(binding)
    obj(companion,{'schema','evidence_kind','profile','origin_qpc_ns','context','receiver_qpc_ns','records'},'companion contract')
    need(companion['schema']=='B77_THREE_POINT_COMPANION_V1' and companion['profile']==PROFILE and companion['evidence_kind']=='SYNTHETIC_FIXTURE','private companion/profile')
    obj(binding,{'profile','session_handle','view_handle','frame_seq','e','channel','companion_sha256'},'binding contract')
    need(binding['profile']==PROFILE,'private binding profile')
    need(uint(binding['e'],8,'integer E')==0,'lossless private binding')
    need(binding['companion_sha256']==digest(companion),'complete companion binding')
    session=uint(binding['session_handle'],U32,'session handle');view=uint(binding['view_handle'],255,'view handle')
    seq=uint(binding['frame_seq'],65535,'nonwrapping frame sequence');channel=uint(binding['channel'],3,'channel')
    origin=uint(companion['origin_qpc_ns'],U63,'original origin')
    receiver=uint(companion['receiver_qpc_ns'],U63,'original receiver QPC');now=uint(now_qpc_ns,U63,'now QPC')
    context=obj(companion['context'],STABLE,'complete stable host context')
    records=companion['records'];need(type(records)is list and len(records)==3,'exactly three original records')
    for r in records:
        obj(r,RECORD,'original sample record');identity(r['source_identity'])
        need(all(r['source_identity'][k]==context[k] for k in STABLE),'stable source identity association')
        need(r['valid'] is True and r['held'] is False,'fresh valid only; held unsupported')
        need(uint(r['channel'],3,'integer record channel')==channel,'channel association')
        for k in ['index','native_tag','native_first_seq','native_last_seq']:uint(r[k],U32,k)
        need(r['native_tag']==r['source_identity']['tag'] and r['native_tag']>0,'native full tag association')
        need(r['native_first_seq']+3==r['native_last_seq'] and r['index']==r['native_first_seq']+channel,'native scan/index association')
        q=uint(r['acquisition_qpc_ns'],U63,'original acquisition QPC');s=uint(r['source_qpc_ns'],U63,'original source QPC')
        need(origin<=q<=receiver<=now and s==q,'original fresh clock ordering')
        need(type(r['remainder_ns'])is int and r['remainder_ns']==(q-origin)%1000,'original remainder')
        uint(r['raw_quality'],255,'opaque uint8 quality');uint(r['original_value'],65535,'original uint16 value')
    first=records[0]
    need(all(r['raw_quality']==first['raw_quality'] and r['native_tag']==first['native_tag'] for r in records),'uniform quality/tag')
    stride=records[1]['acquisition_qpc_ns']-first['acquisition_qpc_ns']
    need(1000<=stride<=65535000 and stride%1000==0,'regular nonzero uint16 microsecond stride')
    for i,r in enumerate(records):
        need(r['index']==first['index']+4*i and r['native_first_seq']==first['native_first_seq']+4*i,'nonwrapping native/index stride4')
        need(r['acquisition_qpc_ns']==first['acquisition_qpc_ns']+stride*i,'regular original ns progression')
        need((r['acquisition_qpc_ns']-origin)//1000<=U32,'relative tick overflow')
    magic,version,kind,length,epoch,sequence,tick=struct.unpack_from('<2sBBBBHI',packet)
    need(magic==b'\xa5\x5a' and version==3 and kind==0xe4,'private E4 wire header')
    need(len(packet)==14+length and length<=32 and epoch==view and sequence==seq,'wire length/identity')
    need(int.from_bytes(packet[-2:],'little')==binascii.crc_hqx(packet[2:-2],0xffff),'CRC')
    payload=packet[12:-2];need(payload[0]==2,'relative1us payload revision2')
    parsed=fixed(repo_root).decode_payload(b'\x01'+payload[1:],dict(session=session,config_epoch=view,e=0))
    need(parsed['count']==3 and parsed['channel']==channel and parsed['index_stride']==4 and parsed['tick_stride_ms']==stride//1000,'three-point coding metadata')
    need(parsed['valid'] and not parsed['held'] and not parsed['saturated'] and not parsed['source_fault'],'fresh wire flags')
    need(parsed['first_tick_ms']==tick,'outer exact first relative tick')
    points=[]
    for r,p in zip(records,parsed['points']):
        need(p['index']==r['index'] and p['tick_ms']==(r['acquisition_qpc_ns']-origin)//1000,'exact original sample association')
        need(p['source_tick_ms']==p['tick_ms'],'fresh source coding association')
        need(p['value']==r['original_value'],'actual decoded raw value mismatch')
        points.append(dict(index=p['index'],channel=channel,decoded_value=p['value'],original_value=r['original_value'],
            original_acquisition_qpc_ns=r['acquisition_qpc_ns'],original_source_qpc_ns=r['source_qpc_ns'],
            origin_qpc_ns=origin,remainder_ns=r['remainder_ns'],raw_quality_uint8=r['raw_quality'],source_identity=r['source_identity'],
            native_tag=r['native_tag'],native_first_seq=r['native_first_seq'],native_last_seq=r['native_last_seq'],source_age_ns=now-r['source_qpc_ns']))
    return dict(stop,input_status='TRANSPORT_STRUCTURAL_ONLY',profile=PROFILE,points=points,context=context,
        source_age_100ms_met=all(p['source_age_ns']<=100_000_000 for p in points),
        coding_ledger=parsed['ledger'],mode=parsed['mode'],frame_sha256=hashlib.sha256(packet).hexdigest())
