"""B74: actual saved RTL UART bytes into the existing strict semantic decoder.

Companion JSON is actually serialized to a file and counted in full for EACH
frame, including opaque quality, ns time, binding and full original identity.
No planner, Root API, board, network or command/control path is called.
"""
import sys
sys.dont_write_bytecode=True
import argparse,binascii,copy,hashlib,importlib.util,json
from pathlib import Path

P=Path(__file__).resolve().parents[3]
HOST=P/'tools/diagnostic/g05_capture/additive50_source_candidate/deepeye_transport50_source_candidate.py'
INPUT=P/'golden/diagnostic/offboard_codec74/SYNTHETIC_raw4.json'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def digest(obj):return sha(canonical(obj))
def load_host():
    spec=importlib.util.spec_from_file_location('b74_existing_host',HOST)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def fixture():return json.loads(INPUT.read_text(encoding='utf-8'))
def companions(m,ch):
    f=fixture();identity=f['source_identity'];origin=f['origin_qpc_ns']
    acquisitions=[f['acquisition_qpc_ns'][ch]]; sources=[f['source_qpc_ns'][ch]]
    values=[f['raw_uint16'][ch]];indices=[f['sample_indices'][ch]]
    rawq={str(c):f['opaque_quality_uint8'][c] for c in range(4)}
    mapped=f['mapped_flags_by_channel'];context=digest(identity)
    p=dict(profile_id=m.PROFILE_ID,origin_mode=m.ORIGIN_MODE,origin_receipt_id='SYNTHETIC-ORIGIN-NOT-ROOT-AUTH',
           origin_qpc_ns=origin,source_identity=identity,original_acquisition_qpc_ns=acquisitions,
           original_source_qpc_ns=sources,original_values=values,original_indices=indices,
           raw_quality_by_channel=rawq,mapped_flags_by_channel=mapped,
           timestamp_record_sha256=digest(dict(origin_qpc_ns=origin,acquisition_qpc_ns=acquisitions,
             source_qpc_ns=sources,original_values=values,original_indices=indices,source_context_sha256=context)),
           quality_record_sha256=digest(dict(raw_quality_by_channel=rawq,mapped_flags_by_channel=mapped,source_context_sha256=context)),
           receiver_qpc_ns=origin+50_000_000)
    b=dict(kind='B_PRIVATE_TRANSPORT_BINDING_PROPOSED_V1',receipt_id='SYNTHETIC-BINDING-'+str(ch),
           profile_id=m.PROFILE_ID,session_handle=0x12345678,view_handle=7,frame_seq=200+ch,e=0,
           source_context_sha256=context)
    return b,p,origin+60_000_000
def frames(simdir):
    wire=bytes.fromhex((simdir/'mode0/uart.hex').read_text())
    serial=bytes.fromhex((simdir/'mode0/serializer.hex').read_text())
    assert wire==serial,'External UART differs from accepted serializer bytes'
    result=[];offset=0
    while offset<len(wire):
        assert wire[offset:offset+2]==b'\xa5\x5a'
        n=14+wire[offset+4];frame=wire[offset:offset+n];assert len(frame)==n
        result.append(frame);offset+=n
    assert len(result)==4 and len(wire)==150
    return result
def crc(packet):
    return packet[:-2]+binascii.crc_hqx(packet[2:-2],0xffff).to_bytes(2,'little')
def decode(m,packet,b,p,now):
    return m.decode_transport(packet,binding=b,profile=p,now_qpc_ns=now,enabled=True,repo_root=P.parents[1])
def reject_case(name,simdir):
    m=load_host();packet=frames(simdir)[0];b,p,now=companions(m,0)
    if name=='crc':packet=packet[:-1]+bytes([packet[-1]^1])
    elif name=='partial':packet=bytes.fromhex((simdir/'mode1/uart.hex').read_text())
    elif name=='identity':b['source_context_sha256']='0'*64
    elif name=='quality':p['raw_quality_by_channel']['0']=256
    elif name=='quality_flags':
        p['mapped_flags_by_channel']['0']['held']=True
        p['quality_record_sha256']=digest(dict(raw_quality_by_channel=p['raw_quality_by_channel'],mapped_flags_by_channel=p['mapped_flags_by_channel'],source_context_sha256=b['source_context_sha256']))
    elif name=='time':p['original_acquisition_qpc_ns'][0]+=1000
    elif name=='u63_overflow':p['original_acquisition_qpc_ns'][0]=1<<63
    elif name=='nonwrap':b['frame_seq']=65536
    elif name=='wrong_index':p['original_indices'][0]+=1
    elif name=='relative_overflow':
        packet=bytearray(packet);packet[25:33]=(1<<32).to_bytes(8,'little');packet=crc(bytes(packet))
    else:raise ValueError(name)
    if name in ('time','wrong_index'):
        p['timestamp_record_sha256']=digest(dict(origin_qpc_ns=p['origin_qpc_ns'],acquisition_qpc_ns=p['original_acquisition_qpc_ns'],
          source_qpc_ns=p['original_source_qpc_ns'],original_values=p['original_values'],original_indices=p['original_indices'],source_context_sha256=b['source_context_sha256']))
    try:decode(m,packet,b,p,now)
    except (ValueError,AssertionError) as e:
        print(json.dumps(dict(expected_rejection=name,error_type=type(e).__name__,reason=str(e))))
        return 2  # Actual negative CLI process fails, no display-only pass.
    print(json.dumps(dict(FALSE_ACCEPT=name)));return 0
def run(simdir,out):
    out.mkdir(exist_ok=False);m=load_host();packets=frames(simdir);f=fixture();records=[]
    for ch,packet in enumerate(packets):
        b,p,now=companions(m,ch);c=dict(evidence_kind='SYNTHETIC_FIXTURE',binding=b,profile=p,now_qpc_ns=now)
        raw=canonical(c);(out/f'companion{ch}.json').write_bytes(raw)
        (out/f'wire{ch}.bin').write_bytes(packet)
        v=decode(m,packet,b,p,now);point=v['points'][0]
        # decoded_value is from ACTUAL RTL bytes, not companion original_value.
        assert point['decoded_value']==f['raw_uint16'][ch]
        assert point['original_acquisition_qpc_ns']==f['acquisition_qpc_ns'][ch]
        assert point['original_source_qpc_ns']==f['source_qpc_ns'][ch]
        assert point['remainder_ns']==(f['acquisition_qpc_ns'][ch]-f['origin_qpc_ns'])%1000
        assert v['raw_quality_uint8']=={str(i):f['opaque_quality_uint8'][i] for i in range(4)}
        assert v['source_identity']==f['source_identity']
        assert v['status']=='STOP' and v['core_ran'] is False and v['command'] is None
        record=dict(schema='B74_SEMANTIC_FIXTURE_V1',evidence_kind='SYNTHETIC_FIXTURE',channel=ch,
          wire_frame_hex=packet.hex(),wire_sha256=sha(packet),wire_bytes=len(packet),
          companion_canonical_bytes=raw.decode('utf-8'),companion_sha256=sha(raw),companion_length=len(raw),
          semantic_view=v,source_input_file=str(INPUT),source_input_sha256=sha(INPUT.read_bytes()),
          decoder_source_pins={str(HOST):sha(HOST.read_bytes()),m.DECODER_PATH:m.DECODER_SHA256},
          total_serialized_bytes=len(packet)+len(raw),production_release=False)
        (out/f'semantic{ch}.json').write_bytes(canonical(record)+b'\n');records.append(record)
    # Explicitly stale source retains the exact acquisition/source ns and STOP.
    b,p,now=companions(m,0);stale=decode(m,packets[0],b,p,now+100_000_000)
    assert stale['source_age_100ms_met'] is False and stale['command'] is None and not stale['core_ran']
    # A companion cannot make a changed original value equal actual RTL output.
    b,p,now=companions(m,0);p['original_values']=[1]
    p['timestamp_record_sha256']=digest(dict(origin_qpc_ns=p['origin_qpc_ns'],acquisition_qpc_ns=p['original_acquisition_qpc_ns'],
      source_qpc_ns=p['original_source_qpc_ns'],original_values=p['original_values'],original_indices=p['original_indices'],source_context_sha256=b['source_context_sha256']))
    mismatch=decode(m,packets[0],b,p,now)
    assert mismatch['points'][0]['decoded_value']==32769 and mismatch['points'][0]['original_value']==1
    assert not mismatch['lossy_decoded_values_match_original']
    ledger=dict(schema='B74_FOCUSED_SEMANTIC_RESULT_V1',evidence_kind='SYNTHETIC_FIXTURE',
      frames=4,wire_bytes=sum(r['wire_bytes'] for r in records),
      mandatory_companion_bytes=sum(r['companion_length'] for r in records),
      total_serialized_bytes=sum(r['total_serialized_bytes'] for r in records),
      original_raw_value_bytes=8,source_age_stale_refusal=stale,value_mismatch_control=mismatch,
      compression_target='NOT_MET_OR_CLAIMED',board='not_run; A only',aggregation='not_run; later operation',
      product_acceptance='pending quality main/A; no BOOT/authenticated ADC/production source gate proof')
    (out/'RESULT.json').write_bytes(canonical(ledger)+b'\n');print(json.dumps(ledger));return 0
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--simdir',type=Path,required=True);a.add_argument('--out',type=Path);a.add_argument('--negative');n=a.parse_args()
    sys.exit(reject_case(n.negative,n.simdir) if n.negative else run(n.simdir,n.out))
