"""New B77 controls: actual four triplet RTL frames to strict host decoder."""
import sys
sys.dont_write_bytecode=True
import argparse,binascii,copy,hashlib,json
from pathlib import Path
import multipoint_decoder as m
P=Path(__file__).resolve().parents[3];ROOT=P.parents[1]
INPUT=P/'golden/diagnostic/offboard_aggregate77/SYNTHETIC_raw12.json'
def load(p):return json.loads(p.read_text())
def sha(raw):return hashlib.sha256(raw).hexdigest()
def fixture():return load(INPUT)
def split_frames(out):
    wire=bytes.fromhex((out/'mode0/uart.hex').read_text());serial=bytes.fromhex((out/'mode0/serializer.hex').read_text());assert wire==serial
    packets=[];at=0
    while at<len(wire):
        assert wire[at:at+2]==b'\xa5\x5a';n=14+wire[at+4];p=wire[at:at+n];assert len(p)==n
        packets.append(p);at+=n
    assert len(packets)==4
    return packets
def companion(ch):
    f=fixture();c=dict(schema='B77_THREE_POINT_COMPANION_V1',evidence_kind='SYNTHETIC_FIXTURE',profile=m.PROFILE,
      origin_qpc_ns=f['origin_qpc_ns'],context=f['context'],receiver_qpc_ns=f['receiver_qpc_ns'],records=[copy.deepcopy(r) for r in f['records'] if r['channel']==ch])
    b=dict(profile=m.PROFILE,session_handle=0x12345678,view_handle=9,frame_seq=300+ch,e=0,channel=ch,companion_sha256=m.digest(c))
    return c,b,f['now_qpc_ns']
def decode(p,c,b,now):return m.decode(p,companion=c,binding=b,now_qpc_ns=now,repo_root=ROOT,enabled=True)
def with_crc(p):return p[:-2]+binascii.crc_hqx(p[2:-2],0xffff).to_bytes(2,'little')
def negative(name,source):
    p=split_frames(source)[0];c,b,now=companion(0)
    if name=='crc':p=p[:-1]+bytes([p[-1]^1])
    elif name=='partial':p=bytes.fromhex((source/'mode11/uart.hex').read_text())
    elif name=='count':p=bytearray(p);p[15]=2;p=with_crc(bytes(p))
    elif name=='metadata':p=bytearray(p);p[33]=5;p=with_crc(bytes(p))
    elif name=='identity':c['records'][1]['source_identity']['session_id']='WRONG-SYNTHETIC-SESSION'
    elif name=='quality':c['records'][1]['raw_quality']^=1
    elif name=='time':c['records'][1]['acquisition_qpc_ns']+=1;c['records'][1]['source_qpc_ns']+=1;c['records'][1]['remainder_ns']+=1
    elif name=='overflow':c['records'][2]['acquisition_qpc_ns']=1<<63
    elif name=='nonwrap':c['records'][2]['index']=1<<32
    elif name=='held':c['records'][1]['held']=True
    elif name=='value':c['records'][0]['original_value']=1
    elif name=='missing':c['records'].pop()
    elif name=='boolean_e':b['e']=False
    elif name=='boolean_channel':c['records'][0]['channel']=False
    else:raise ValueError(name)
    b['companion_sha256']=m.digest(c)
    try:decode(p,c,b,now)
    except ValueError as e:print(json.dumps(dict(expected_rejection=name,reason=str(e))));return 2
    print(json.dumps(dict(FALSE_ACCEPT=name)));return 0
def positive(source,out):
    out.mkdir();f=fixture();packets=split_frames(source)
    # Exact actual input lane stream and collector triplet provenance.
    lines=(source/'mode0/lanes.txt').read_text().splitlines();assert len(lines)==12
    for r,line in zip(f['records'],lines):
        assert list(map(int,line.split()))==[r[k] for k in ['channel','original_value','acquisition_qpc_ns','raw_quality','native_tag','native_first_seq','native_last_seq']]
    blocks=(source/'mode0/blocks.txt').read_text().splitlines();assert len(blocks)==4
    records=[]
    for ch,(packet,line) in enumerate(zip(packets,blocks)):
        c,b,now=companion(ch);rs=c['records'];v=line.split()
        assert int(v[0])==ch
        def packed(key,width):return sum(r[key]<<(width*i) for i,r in enumerate(rs))
        assert [int(x,16) for x in v[1:6]]==[packed('original_value',16),packed('acquisition_qpc_ns',64),packed('raw_quality',8),packed('native_first_seq',32),packed('native_last_seq',32)]
        assert list(map(int,v[6:]))==[17,ch,10000000,10000]
        result=decode(packet,c,b,now);assert len(result['points'])==3 and not result['core_ran'] and result['command']is None
        assert [p['decoded_value'] for p in result['points']]==[r['original_value'] for r in rs]
        envelope=dict(evidence_kind='SYNTHETIC_FIXTURE',binding=b,companion=c,now_qpc_ns=now)
        raw=m.canonical(envelope);(out/f'companion{ch}.json').write_bytes(raw);(out/f'wire{ch}.bin').write_bytes(packet)
        artifact=dict(schema='B77_SEMANTIC_FIXTURE_V1',evidence_kind='SYNTHETIC_FIXTURE',wire_frame_hex=packet.hex(),wire_sha256=sha(packet),wire_bytes=len(packet),
          companion_canonical_bytes=raw.decode(),companion_sha256=sha(raw),companion_length=len(raw),semantic_view=result,
          source_input_file=str(INPUT),source_input_sha256=sha(INPUT.read_bytes()),
          decoder_pins={str(Path(m.__file__)):sha(Path(m.__file__).read_bytes()),m.FIXED_PATH:m.FIXED_SHA},
          total_serialized_bytes=len(packet)+len(raw))
        (out/f'semantic{ch}.json').write_bytes(m.canonical(artifact)+b'\n');records.append(artifact)
    c,b,now=companion(0);stale=decode(packets[0],c,b,now+100000000);assert not stale['source_age_100ms_met'] and stale['command']is None
    assert sorted(p['index'] for r in records for p in r['semantic_view']['points'])==list(range(12))
    ledger=dict(schema='B77_AGGREGATE_RESULT_V1',evidence_kind='SYNTHETIC_FIXTURE',frames=4,points=12,
      wire_bytes=sum(r['wire_bytes'] for r in records),mandatory_companion_bytes=sum(r['companion_length'] for r in records),
      total_serialized_bytes=sum(r['total_serialized_bytes'] for r in records),raw_value_bytes=24,
      complete_synthetic_input_canonical_bytes=len(m.canonical(f)),source_age_stale_control=stale,
      per_frame=[dict(wire_bytes=r['wire_bytes'],companion_bytes=r['companion_length'],mode=r['semantic_view']['mode'],coding_ledger=r['semantic_view']['coding_ledger']) for r in records],
      compression_target='NOT_MET_OR_CLAIMED',acceptance='synthetic bounded fresh-only triplets; no ADC/BOOT/authentication/fullH12/final acceptance')
    (out/'RESULT.json').write_bytes(m.canonical(ledger)+b'\n');print(json.dumps(ledger));return 0
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--source',type=Path,required=True);a.add_argument('--out',type=Path);a.add_argument('--negative');n=a.parse_args()
    sys.exit(negative(n.negative,n.source)if n.negative else positive(n.source,n.out))
