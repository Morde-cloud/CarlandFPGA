"""One focused check of actual retired-input UART bytes with unchanged decoders."""
from __future__ import annotations
import argparse, copy, importlib.util, json, struct, sys
from pathlib import Path
sys.dont_write_bytecode=True
W=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'causal_raw4_92'))
import raw4_adapter92 as a
HOST=W/'competition/deepeye/tools/diagnostic/g05_capture/additive50_source_candidate/deepeye_transport50_source_candidate.py'
TRACE=W/'competition/deepeye/golden/codec/trace_candidate.py'
def load(name,path,pin):
    a._need(a.sha256_bytes(path.read_bytes())==pin,'unchanged decoder pin')
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
def frames(raw):
    out=[];i=0
    while i<len(raw):
        a._need(len(raw)-i>=14,'complete outer header')
        magic,version,kind,n,view,seq,tick=struct.unpack_from('<2sBBBBHI',raw,i)
        a._need(magic==b'\xa5\x5a' and version==3 and kind==0xe4 and n<=32 and i+n+14<=len(raw),'outer frame bounds')
        out.append(raw[i:i+n+14]);i+=n+14
    return out
def run(out):
    host=load('b100_host',HOST,'1f4da870d9c885a3cc6156c30d2170e21001187392a59a19172c059c9ab0c768')
    trace=load('b100_trace',TRACE,'a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642')
    p=a.load_json_strict((out/'fixture/projection.json').read_bytes())
    model=a.transport_input(p,fixture_mode=a.RETIRED_KIND,build_manifest_sha256=a.sha256_bytes((out/'SOURCE_BEFORE.json').read_bytes()))
    pins={'host_sha256':a.sha256_bytes(HOST.read_bytes()),'trace_sha256':a.sha256_bytes(TRACE.read_bytes())}
    uart=bytes.fromhex((out/'mode0/uart.hex').read_text());serial=bytes.fromhex((out/'mode0/serializer.hex').read_text())
    a._need(uart==serial,'actual UART sampling equals serializer')
    packets=frames(uart);a._need(len(packets)==80,'exact 80 singleton frames')
    events=(out/'mode0/events.txt').read_text()
    a._need(events.count('RESULT_BACKPRESSURE ')==1 and events.count('WRONG_IDENTITY_REFUSED ')==1,'single held result and wrong association stall')
    dest=out/'decoded';dest.mkdir();rows=[];wl=[];cl=[];counts={'invalid':0,'valid_zero':0,'held':0,'fresh':0}
    def decode(packet,c): return host.decode_transport(packet,binding=c['binding'],profile=c['profile'],now_qpc_ns=c['evaluation_now_qpc_ns'],enabled=True,repo_root=W)
    for i,(packet,lane) in enumerate(zip(packets,model['lanes'])):
        c=a.companion_for_lane(model,lane,decoder_pins=pins);cr=a.canonical(c)
        (dest/('frame%03d.bin'%i)).write_bytes(packet);(dest/('companion%03d.json'%i)).write_bytes(cr)
        v=decode(packet,c);point=v['points'][0]
        raw=trace.decode_payload(bytes([1])+packet[13:-2],{'session':a.RETIRED_SESSION,'config_epoch':a.RETIRED_VIEW,'e':0})
        rp=raw['points'][0]
        header=struct.unpack_from('<2sBBBBHI',packet)
        a._need(header[4:]==(a.RETIRED_VIEW,i,lane['first_tick_us']),'outer view/sequence/tick')
        a._need(raw['count']==1 and len(raw['points'])==1,'actual singleton')
        a._need((packet[13]&7)==0,'actual E0')
        a._need(v['status']=='STOP' and v['core_ran'] is False and v['command'] is None,'structural STOP no action')
        a._need(v['source_identity']==model['identity'] and v['frame_sha256']==a.sha256_bytes(packet),'exact source identity/frame')
        a._need(point['decoded_value']==lane['count'] and point['original_value']==lane['count'] and rp['value']==lane['count'],'exact original counts/None')
        a._need(point['index']==lane['acquisition_index'] and point['relative_tick_us']==lane['first_tick_us'] and point['remainder_ns']==0,'original relative acquisition')
        a._need(point['original_acquisition_qpc_ns']==lane['acquisition_qpc_ns'] and point['original_source_qpc_ns']==lane['source_qpc_ns'],'exact original uint63 timestamp')
        a._need(rp['source_tick_ms']==lane['source_tick_us'],'unchanged code-section decoder relative us')
        flags=lane['record_flags'][lane['channel']]
        a._need(all(rp[k]==flags[k] for k in ('valid','saturated','held','source_fault')),'actual flags')
        a._need(v['raw_quality_uint8']=={str(k):lane['record_derived_bytes'][k] for k in range(4)},'all four opaque quality bytes')
        a._need(point['byte_exact_value'] is True and v['lossy_decoded_values_match_original'] is True and v['c29_uint12_values_possible'] is True,'exact value proof')
        a._need(c['current_source_eligible'] is False and c['authority']['current_source_eligible'] is False and c['retired_source_receipt']['retired'] is True,'retired remains ineligible')
        if lane['valid_sample']:
            a._need(point['source_age_ns']==model['evaluation_now_qpc_ns']-lane['source_qpc_ns'] and v['source_age_100ms_met'] is False,'fixture evaluation staleness')
            counts['held' if lane['held'] else 'fresh']+=1
            if lane['channel']==3: a._need(point['decoded_value']==0,'actual C3 valid zero');counts['valid_zero']+=1
        else:
            a._need(point['decoded_value'] is None and point['source_age_ns'] is None,'None cannot be data zero');counts['invalid']+=1
        wl.append(len(packet));cl.append(len(cr));rows.append({'frame':i,'record':lane['record_index'],'channel':lane['channel'],'decoded':point,'raw_flags':flags,'quality13':lane['quality13_uint16'],'wire_bytes':len(packet),'companion_bytes':len(cr),'wire_sha256':a.sha256_bytes(packet),'companion_sha256':a.sha256_bytes(cr),'source_record_sha256':lane['source_record_sha256'],'status':v['status'],'core_ran':v['core_ran'],'command':v['command'],'current_source_eligible':False})
    a._need(counts=={'invalid':9,'valid_zero':11,'held':48,'fresh':23},'actual decoded populations')
    # New retired-input boundary: invalid original companion rewritten to zero is refused.
    lane=model['lanes'][3];c=a.companion_for_lane(model,lane,decoder_pins=pins);c=copy.deepcopy(c)
    c['profile']['original_values']=[0];pr=c['profile'];b=c['binding']
    pr['timestamp_record_sha256']=a.digest({'origin_qpc_ns':pr['origin_qpc_ns'],'acquisition_qpc_ns':pr['original_acquisition_qpc_ns'],'source_qpc_ns':pr['original_source_qpc_ns'],'original_values':pr['original_values'],'original_indices':pr['original_indices'],'source_context_sha256':b['source_context_sha256']})
    try: decode(packets[3],c)
    except host.Rejected as exc:
        a._need('invalid data remains null' in str(exc),'exact None-to-zero refusal');negative={'case':'retired_None_to_zero','refused':True,'reason':str(exc)}
    else: raise RuntimeError('FALSE_ACCEPT retired None as zero')
    default=host.decode_transport(b'',enabled=True)
    a._need(default['input_status']=='INPUT_UNAVAILABLE' and default['command'] is None and default['core_ran'] is False,'unchanged host default unavailable')
    cost=a.cost_summary(model,wl,cl)
    result={'status':'FOCUSED_RUNTIME_CHECKS_COMPLETED_MAIN_REVIEW_PENDING','scope':'actual historical input RTL simulation; not board','frames':80,'counts':counts,'actual_wire_bytes':len(uart),'predicted_wire_bytes':3038,'wire_delta':len(uart)-3038,'cost':cost,'negative':negative,'default':default,'decoder_pins':pins,'origin_qpc_ns':model['origin_qpc_ns'],'origin_submicrosecond_ns':model['origin_qpc_ns']%1000,'relative_remainders_ns':[0],'quality13':sorted({l['quality13_uint16'] for l in model['lanes']}),'status_all':'STOP','core_ran':False,'command':None,'current_source_eligible':False,'full_Root_BOOT_admission_current_positive':False}
    (dest/'FRAMES_INDEX.json').write_bytes(a.canonical(rows));(out/'SEMANTIC_RESULT.json').write_bytes(a.canonical(result))
    print(json.dumps(result));return 0
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);raise SystemExit(run(p.parse_args().out))
