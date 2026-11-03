"""One A95B-focused offboard software fixture; no model/Root/board execution."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import binascii
import sys
from output195 import REPO, command_words, inspect_output, Refused


def fresh():
    # New fixture, full32-bit held seq deliberately differs from uint16 frame seq.
    words=[65539,7,4103,(20<<8)|1,((-200 & 65535)<<16)|100,1000,
           1000000,0,51000000,0,4000000,0,1000000,1000000,1000000,
           125800,123400,35000,100,0,101,0,100,0,1000100,0,1000101,0,1000100,0,77,0x47303550]
    original=dict(schema='B132_ORIGINAL_RECORD_V1',identity_words=list(range(11,23))+[77],
        status_before=0x15,status_after=0x35,fault_before=0,fault_after=0,command_id=7,
        transport_tag=4103,decision=dict(yaw_q=100,pitch_q=-200,profile=1,speed=20,ttl_ms=1000),
        applied_tick=1000000,deadline_tick=51000000,result_tick=4000000,capture_seq=65539,
        previous_capture_seq=65538,previous_command_id=6,operation_id='B195-SOFTWARE-FIXTURE-NOT-BOARD')
    def held(cycle,latest):return dict(identity_words=original['identity_words'][:],magic=0x47303550,
        layout=2,status=0x35,fault=0,command_id=7,transport_tag=4103,applied_tick=1000000,
        deadline_tick=51000000,held_capture_seq=65539,cycle_tick=cycle,latest_seq=latest)
    request=dict(schema='B132_G05P_CAPTURE_DECODE_REQUEST_V1',layout=2,raw_words=words,
                 original_record=original,held_observations=dict(before=held(4010000,65540),after=held(4020000,65541)))
    def encode(d):return json.dumps(d,sort_keys=True,separators=(',',':')).encode().hex()
    release=[]
    for i,(kind,off,val,result) in enumerate([('read',8,None,0x35),('read',16,None,0),
                                           ('write',12,5,None),('read',8,None,0x15),('read',16,None,0)]):
        n=96+i;a=dict(request_id='tx-fixture-release',io=n,kind=kind,offset=off,value=val,pid=1234,monotonic_ns=1000+2*i)
        z=dict(request_id=a['request_id'],io=n,kind=kind,value=result,monotonic_ns=1001+2*i)
        release.append(dict(index=n,started_raw_hex=encode(a),returned_raw_hex=encode(z)))
    args=dict(expected_identity_words=tuple(original['identity_words']),expected_operation_id=original['operation_id'],
        expected_command_words=(100,(-200)&65535,1,20,1000,7,4103),observation_seq=21,frame_seq=3,
        now_host_ns=100000000,step_ns=100000000,
        deadline_caps_ns=dict(mapped_fpga=1000000000,source=800000000,command=500000000,
                             actor=900000000,health=700000000,session=2000000000,previous_action=None),
        now_board_tick=4100000,release_receipts=release,cumulative_io=100,io_limit=2048)
    return request,args


def singleton():
    p=REPO/'competition/deepeye/golden/codec/trace_candidate.py'
    assert hashlib.sha256(p.read_bytes()).hexdigest()=='a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642'
    spec=importlib.util.spec_from_file_location('_b195_exact_codec',p);codec=importlib.util.module_from_spec(spec);sys.modules[spec.name]=codec;spec.loader.exec_module(codec)
    wire=bytearray();decoded=[];binding=dict(session=77,config_epoch=2,e=0)
    for channel,value in enumerate((0,4095,1234,None)):
        point=dict(index=21,tick_ms=100,value=value,valid=value is not None,saturated=False,
                   held=False,source_fault=False,source_tick_ms=100 if value is not None else None)
        body=codec.encode_payload([point],binding,channel);payload=bytes([2])+body[1:]
        header=struct.pack('<2sBBBBHI',b'\xa5\x5a',3,0xe4,len(payload),2,100+channel,100)
        frame=header+payload+struct.pack('<H',binascii.crc_hqx(header[2:]+payload,0xffff));wire.extend(frame)
        assert binascii.crc_hqx(frame[2:-2],0xffff)==int.from_bytes(frame[-2:],'little')
        got=codec.decode_payload(bytes([1])+payload[1:],binding);assert got['channel']==channel and got['count']==1
        decoded.append(got['points'][0]['value'])
    assert decoded==[0,4095,1234,None] and len(wire)==146
    return dict(wire_hex=wire.hex(),wire_bytes=len(wire),channel_counts=decoded,quality_validity_mask=7,
                missing_mask=8,mode='RAW',scope='synthetic singletons; not a real source/physical/custody result')


def run(out):
    out.mkdir(exist_ok=False);request,args=fresh();results=[]
    positive=inspect_output(request,**args)
    assert positive['held_capture_seq']==65539 and positive['frame_seq']==3
    assert positive['latest_result_seq_after']==65541 and positive['motion_authority'] is False
    assert positive['measured_target_codes']==dict(yaw_q=100,pitch_q=-200,speed_code=20)
    results.append(dict(id='FULL32_HELD_LATEST_ADVANCE_MEASURED',passed=True))
    def reject(name,change):
        r,a=copy.deepcopy(request),copy.deepcopy(args);change(r,a)
        try:inspect_output(r,**a)
        except Refused as e:results.append(dict(id=name,passed=True,refusal=str(e)))
        else:raise AssertionError(name+' incorrectly accepted')
    reject('NOMINAL_ECHO_CANNOT_REPLACE_MEASURED',lambda r,a:r['raw_words'].__setitem__(15,125808))
    reject('WRONG_EXTERNAL_NONCE',lambda r,a:r['held_observations']['after']['identity_words'].__setitem__(8,999))
    reject('WRONG_OPERATION',lambda r,a:a.__setitem__('expected_operation_id','other'))
    reject('WRONG_COMMAND',lambda r,a:a.__setitem__('expected_command_words',(100,65336,1,20,1000,8,4103)))
    reject('LATEST_REGRESSION',lambda r,a:r['held_observations']['after'].__setitem__('latest_seq',65538))
    reject('BOARD_EXPIRED',lambda r,a:a.__setitem__('now_board_tick',51000000))
    reject('WHOLE_STEP_CROSSES_SOURCE_CAP',lambda r,a:a['deadline_caps_ns'].__setitem__('source',199999999))
    reject('STOP_RETIRED',lambda r,a:a.__setitem__('retired',True))
    reject('UNKNOWN_APPLY_NO_REPLAY',lambda r,a:a.__setitem__('effect_unknown',True))
    reject('RELEASE_ACK_MISSING',lambda r,a:a.__setitem__('release_receipts',[]))
    reject('RELEASE_CUMULATIVE_INDEX_GAP',lambda r,a:a['release_receipts'][3].__setitem__('index',1))
    reject('FRAME16_OVERFLOW_NO_TRUNCATION',lambda r,a:a.__setitem__('frame_seq',65539))
    packet=singleton();results.append(dict(id='CURRENT_SINGLETON_Q7_C3_NULL_RAW146',passed=True))
    for name,data in [('request.json',request),('constraints.json',args),('measured_reference.json',positive),('singleton.json',packet)]:
        (out/name).write_text(json.dumps(data,indent=2)+'\n',encoding='utf8')
    result=dict(kind='SOFTWARE_FIXTURE_ONLY',cases=results,passed=len(results),physical_board=False,
                original_A_authority_executed=False,model_actor_vendor=False,formal_acceptance=False)
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
