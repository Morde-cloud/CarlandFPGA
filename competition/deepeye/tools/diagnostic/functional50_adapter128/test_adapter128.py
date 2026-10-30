"""New affected pure adapter controls only; no old suite or physical producer."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct
import sys
import traceback
sys.dont_write_bytecode = True

def run(out):
    # Main owns supervision. No output reuse, child process, retry, or runner.
    out.mkdir(parents=False, exist_ok=False)
    rows = []
    try:
        from adapter128 import prepare_bytes, prepare_normalized, correlate_collected, Refused, digest, OriginalBytes
        from reducer128 import Reducer, LIMITS
        from dependencies128 import input113, codec

        def check(ok, label):
            if not ok:
                raise AssertionError(label)

        def refused(fn):
            try:
                fn()
            except (Refused, ValueError):
                return
            raise AssertionError('refusal expected')

        def original(values=(4095,0,None,17)):
            origin = 87123456789101; acq = origin+100991
            bodies = tuple(('opaque companion %d\r\n'%i).encode()+b'\x00' for i in range(4))
            source = b'original opaque exporter bytes\r\n\x00\xff'
            lanes = []
            for i,value in enumerate(values):
                valid = value is not None; held = valid and i == 0
                source_ns = origin+95123 if held else acq if valid else None
                flags = dict(valid=valid,saturated=valid and i==1,held=held,source_fault=i==2)
                lanes.append(dict(channel=i,raw_sample_uint16=value,root_quality_uint16=65535-i,
                    mapped_flags=flags,staged_quality_uint4=int(valid)+2*int(flags['saturated'])+4*int(held)+8*int(flags['source_fault']),
                    acquisition_qpc_ns=acq,acquisition_tick_us=100,acquisition_remainder_ns=991,
                    source_qpc_ns=source_ns,source_tick_us=None if not valid else 95 if held else 100,
                    source_remainder_ns=None if not valid else 123 if held else 991,
                    session=0x12345678,index=7+i*11,view=17,frame_seq=42+i*3))
            req={'schema':'B113_EXTERNAL_ORIGINAL_SCAN_REQUEST_V1',
                 'task':dict(task_id='DEEPEYE-IMPLEMENTATION-20261014',task_version=1,work_id='CONTROL128-EXTERNAL',requirements_sha256='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'),
                 'source_provenance':{'class':'NEW_ORIGINAL_LIVE_ROOT','declared_by':'CONTROL128-CALLER','source_note':'synthetic control of arbitrary external shape; no physical claim','mapping_state':'B_NEUTRAL_AWAITING_A_MAPPING'},
                 'source_payload':dict(format_label='opaque128',bytes=len(source),sha256=digest(source)),
                 'scan':dict(scan_id_uint63=987654321,origin_qpc_ns=origin,acquisition_qpc_ns=acq,clock_domain_id='DECLARED128',lanes=lanes),
                 'lineage':dict(operation_id='CONTROL128-OP',request_id='CONTROL128-REQ',request_hash='34'*32,tested_commit='56'*20,build_id_hex128='12'*16,boot_id='DECLARED-BOOT',session_id=0x12345678,tag=41,trigger_id=9,generation=3,request_seq=31,capture_seq=32),
                 'association':dict(profile_id='TRACE-PAYLOAD-1US-PRIVATE-v2',binding_receipt_id='DECLARED-BINDING',e=0,source_context_sha256='67'*32,timestamp_record_sha256='78'*32,quality_record_sha256='89'*32,receiver_qpc_ns=acq+1000,evaluation_now_qpc_ns=acq+2000,evaluation_clock_id='DECLARED128',receiver_clock_id='DECLARED128',freshness_limit_ns=100000000),
                 'companions':[dict(channel=i,format_label='opaque128',bytes=len(b),sha256=digest(b)) for i,b in enumerate(bodies)]}
            binding=dict(canonical_build_id_full_sha256='12'*32,source_closure_file_sha256='ab'*32,operation_id='CONTROL128-OP',request_hash='34'*32)
            return req,source,bodies,binding

        def prepare(data):
            req,source,bodies,binding = data
            raw = json.dumps(req,ensure_ascii=False,separators=(',',':')).encode()
            return prepare_bytes(raw,source,bodies,build_binding=binding)

        def retain(name, preparation, wire, facts):
            directory=out/name;directory.mkdir(exist_ok=False)
            files={'request.bin':preparation.original.request,
                   'source.bin':preparation.original.source,'wire.bin':wire}
            files.update({'companion%d.bin'%i:b for i,b in enumerate(preparation.original.companions)})
            for filename,raw in files.items():
                with (directory/filename).open('xb') as stream:stream.write(raw)
            with (directory/'facts.json').open('x',encoding='utf-8') as stream:
                json.dump(facts,stream,ensure_ascii=False,sort_keys=True,separators=(',',':'))

        def frames_for(plan):
            # New generated software control data using the unchanged codec.
            # This is not a UART, RTL, historical replay, or physical result.
            frames=[];results=[];total=19
            for lane in plan._scan['lanes']:
                point=dict(index=lane['index'],tick_ms=lane['acquisition_tick_us'],value=lane['raw_sample_uint16'],
                           source_tick_ms=lane['source_tick_us'],**lane['mapped_flags'])
                p=codec.encode_payload([point],dict(session=lane['session'],config_epoch=lane['view'],e=0),lane['channel'])
                p=bytes([2])+p[1:]
                h=struct.pack('<2sBBBBHI',b'\xa5\x5a',3,0xe4,len(p),lane['view'],lane['frame_seq'],lane['acquisition_tick_us'])
                frame=h+p+struct.pack('<H',binascii.crc_hqx(h[2:]+p,0xffff));frames.append(frame)
                results.append(dict(id=10+lane['channel'],bytes=len(frame),error=0,rx_before=total,rx_end=total+len(frame)))
                total+=len(frame)
            return frames,results

        def observation(intent, value=None, status=None):
            return dict(operation_id=intent['operation_id'],call_id=intent['call_id'],
                        status=status or ('confirmed_read' if intent['kind']=='read' else 'confirmed_write'),value=value,error_code=None)

        class Transcript:
            """New response transcript for this API; never invokes a bus."""
            def __init__(self, plan, *, dirty=False, wrap=False, stall=False):
                self.plan=plan;self.stage={};self.state=0;self.push=0;self.assoc=0
                self.frames,self.result_rows=frames_for(plan)
                self.fifo=[0xaa] if dirty else [];self.pop=0;self.rid=U32 if wrap else 9
                self.tag=0;self.rx=19;self.row=None;self.commands=[];self.stall=stall
            def answer(self,intent):
                off=intent['offset'];value=intent['value']
                if intent['kind']=='write':
                    if off!=0x080:self.stage[off]=value
                    else:
                        self.commands.append(value)
                        if value==1:self.state=1 if self.stall else 3;self.tag=self.stage[0x100]
                        elif value==2:self.push+=1;self.state=4 if self.push==4 else 3
                        elif value==3:
                            frame=self.frames[self.assoc];self.fifo.extend(frame);self.rid+=1
                            self.row=dict(id=self.rid,error=0,bytes=len(frame),refusal=0,rx_before=self.rx,rx_end=self.rx+len(frame));self.rx+=len(frame);self.state=7
                        elif value==4:self.assoc+=1;self.state=9 if self.assoc==4 else 4
                        elif value==5:self.state=0
                        elif value==8:self.fifo.pop(0);self.pop+=1
                        else:raise AssertionError('clear or unselected command')
                    return observation(intent)
                constants={0:0x54353046,4:1,8:4,12:50000000,16:1000000,20:4096}
                if off in constants:v=constants[off]
                elif 0x060<=off<=0x06c:v=(int(self.plan._lineage['build_id_hex128'],16)>>(8*(off-0x060)))&U32
                else:
                    status=2|(0x20 if not self.fifo else 0)|(0x10 if self.state==7 else 0)
                    values={0x018:self.state,0x01c:0,0x020:status,0x024:self.push,0x028:self.assoc,0x02c:self.tag,
                            0x030:len(self.fifo),0x034:self.rx,0x038:self.pop,0x040:self.rid,
                            0x070:0x100|self.fifo[0] if self.fifo else 0}
                    if self.row:values.update({0x044:0,0x048:self.row['bytes'],0x04c:0,0x050:self.row['rx_before'],0x07c:self.row['rx_end']})
                    v=values[off]
                return observation(intent,v)

        U32=(1<<32)-1
        def drive(r,t,change=None,not_attempted_arm=False):
            intent=r.advance(phase_elapsed_ns=0);seen=[]
            for _ in range(5000):
                if intent is None:return seen
                seen.append(intent)
                if not_attempted_arm and intent['kind']=='write' and intent['offset']==0x080 and intent['value']==1:
                    answer=observation(intent,status='not_attempted')
                else:
                    answer=t.answer(intent)
                if change is not None:answer=change(intent,answer)
                intent=r.advance(answer,phase_elapsed_ns=0)
            raise AssertionError('test transcript exceeded bounded expected calls')

        def case_external():
            p=prepare(original());check(p.plan is not None,'arbitrary external accepted')
            n=input113.normalize_external_original_scan_v1(p.original.request,p.original.source,p.original.companions)
            q=prepare_normalized(n,build_binding=original()[3]);check(q.plan is not None,'normalized entry')
            facts=p.plan.facts();check('current_source_eligible' not in facts and 'kind' not in facts and 'core_ran' not in facts,'no authority/fake coercion')
            check(p.plan._scan['lanes'][0]['root_quality_uint16']==65535,'opaque uint16 preserved')
            check(p.original.source==original()[1] and p.original.companions==original()[2],'full raw retained')

        def case_refusals():
            for mode in ('uint16','held_subus','e','time','quality','session','sequence','closure','request'):
                d=original();q=d[0];lane=q['scan']['lanes'][0]
                if mode=='uint16':lane['raw_sample_uint16']=65535
                elif mode=='held_subus':lane['source_tick_us']=100;lane['source_remainder_ns']=990;lane['source_qpc_ns']=q['scan']['origin_qpc_ns']+100990
                elif mode=='e':q['association']['e']=1
                elif mode=='time':lane['acquisition_remainder_ns']=990
                elif mode=='quality':lane['staged_quality_uint4']=0
                elif mode=='session':lane['session']+=1
                elif mode=='sequence':q['scan']['lanes'][3]['frame_seq']=0
                elif mode=='closure':d[3]['canonical_build_id_full_sha256']='ab'*32
                else:d[3]['request_hash']='ff'*32
                p=prepare(d);check(p.plan is None and p.status=='REFUSED_WITH_ORIGINAL_BYTES',mode)
                check(p.original.source==d[1] and p.original.companions==d[2],'refusal bytes '+mode)

        def case_frames():
            for sample,values in enumerate(((1,0,None,4095),(345,1234,2048,17),(None,None,None,None))):
                p=prepare(original(values));check(p.plan is not None,'variable numerical mapping')
                frames,result_rows=frames_for(p.plan);wire=b''.join(frames)
                out=correlate_collected(p.plan,wire,p.original.companions,result_rows)
                check(out['status']=='FOUR_FRAME_CORRELATION_CONSISTENT','numeric correlation')
                check([x['point']['value'] for x in out['frames']]==list(values),'null and valid zero distinct')
                check(out['mandatory_companion_bytes']==sum(map(len,p.original.companions)),'full companion cost')
                check(out['semantic_association']=='OPAQUE_NOT_VERIFIED','opaque is not semantic pass')
                retain('correlation%d'%sample,p,wire,{k:v for k,v in out.items() if k!='retained'})
                for damaged in (wire[:-1],wire+b'\x00',bytes([wire[0]^1])+wire[1:],wire[:-1]+bytes([wire[-1]^1])):
                    bad=correlate_collected(p.plan,damaged,p.original.companions,result_rows)
                    check(bad['status']=='REFUSED_WITH_ORIGINAL_BYTES' and bad['retained']['wire']==damaged,'damaged raw retained')
                bodies=list(p.original.companions);bodies[0]+=b'\x00'
                check(correlate_collected(p.plan,wire,bodies,result_rows)['status']=='REFUSED_WITH_ORIGINAL_BYTES','companion mismatch')
                changed=[dict(x) for x in result_rows];changed[2]['id']+=1
                check(correlate_collected(p.plan,wire,p.original.companions,changed)['status']=='REFUSED_WITH_ORIGINAL_BYTES','result identity')

        def case_sequence():
            p=prepare(original());r=Reducer(p.plan);t=Transcript(p.plan)
            r.begin();calls=drive(r,t);check(r.completed and not r.failed,'one scan complete')
            r.begin_collect();calls+=drive(r,t)
            check(bytes(r.prefix)==b''.join(t.frames),'exact zero-byte collect')
            check(correlate_collected(p.plan,bytes(r.prefix),p.original.companions,r.results)['status']=='FOUR_FRAME_CORRELATION_CONSISTENT','reducer results correlated')
            refused(r.begin);refused(r.begin_collect)
            r.begin_cleanup();calls+=drive(r,t);refused(r.begin_cleanup)
            check(t.commands.count(1)==1 and t.commands.count(2)==t.commands.count(3)==t.commands.count(4)==4 and t.commands.count(5)==1,'one-use commands')
            check(all(x['window']=='TRACE_HWH_RELATIVE' for x in calls),'TRACE-only offsets')
            saved=r.snapshot();saved.pop('original');saved['confirmed_wire_prefix_hex']=saved.pop('confirmed_wire_prefix').hex()
            retain('one_sequence',p,bytes(r.prefix),saved)

        def case_prearm():
            for scenario in ('dirty','wrap','identity'):
                p=prepare(original());r=Reducer(p.plan);t=Transcript(p.plan,dirty=scenario=='dirty',wrap=scenario=='wrap')
                r.begin()
                def alter(i,a):
                    if scenario=='identity' and i['offset']==0:a['value']=0
                    return a
                calls=drive(r,t,alter)
                check(r.failed and not any(x['kind']=='write' for x in calls),'preARM zero writes')
                refused(r.begin_cleanup);refused(r.begin_collect)

        def case_unknown():
            for target in ('arm_unknown','arm_not_attempted','pop_unknown','read_error'):
                p=prepare(original());r=Reducer(p.plan);t=Transcript(p.plan);r.begin()
                def alter(i,a):
                    if (target.startswith('arm') and i['kind']=='write' and i['offset']==0x080 and i['value']==1) or (target=='pop_unknown' and i['kind']=='write' and i['offset']==0x080 and i['value']==8) or (target=='read_error' and i['offset']==0):
                        return observation(i,status='not_attempted' if target=='arm_not_attempted' else 'error' if target=='read_error' else 'unknown')
                    return a
                drive(r,t,alter,not_attempted_arm=target=='arm_not_attempted')
                if target=='pop_unknown':r.begin_collect();drive(r,t,alter)
                check(r.failed,'unknown/error terminal sequence')
                if target in ('arm_not_attempted','read_error'):
                    check(not r.arm_attempt_owned,'not attempted ownership');refused(r.begin_cleanup)
                else:
                    check(r.arm_attempt_owned and r.unknown_effects,'owned unknown retained')
                    if target=='arm_unknown':refused(r.begin_collect)
                    if target=='pop_unknown':check(len(r.prefix)==0 and r.pending_peek is not None,'pending POP retained');refused(r.begin_collect)
                    r.begin_cleanup();drive(r,t);check(t.commands.count(5)==1,'owned cancel once')

        def case_identity():
            p=prepare(original());r=Reducer(p.plan);r.begin();i=r.advance(phase_elapsed_ns=0)
            wrong=observation(i,0x54353046);wrong['call_id']+=1
            refused(lambda:r.advance(wrong,phase_elapsed_ns=0));check(r.pending['call_id']==i['call_id'],'mismatched receipt not consumed')
            r.advance(observation(i,status='not_attempted'),phase_elapsed_ns=0)
            refused(lambda:r.advance(observation(i,0x54353046),phase_elapsed_ns=0));refused(r.begin)

        def case_budgets():
            p=prepare(original())
            for field,limit,stall in (('polls',1,True),('csr',2,False),('writes',1,False),('work_evidence',16384,False)):
                limits=dict(LIMITS);limits[field]=limit;r=Reducer(p.plan,limits=limits);t=Transcript(p.plan,stall=stall);r.begin();drive(r,t)
                check(r.failed and all(r.counts[k] <= limits[k] for k in r.counts) and
                      r.evidence_reserved['work'] <= limits['work_evidence'], 'bounded '+field)
            r=Reducer(p.plan);r.begin();check(r.advance(phase_elapsed_ns=LIMITS['work_ns']) is None and r.failed and r.counts['csr']==0,'deadline before effects')

        def case_consumer_snapshot():
            p=prepare(original());frames,result_rows=frames_for(p.plan);wire=b''.join(frames)
            p.plan._scan['lanes'][0]['raw_sample_uint16']=65535
            p.plan._lineage['operation_id']='MUTATED-CACHE'
            facts=p.plan.facts();check(facts['scan']['lanes'][0]['raw_sample_uint16']==4095 and
                                     facts['lineage']['operation_id']=='CONTROL128-OP','facts rebuilt from original bytes')
            r=Reducer(p.plan);check(r.plan._scan['lanes'][0]['raw_sample_uint16']==4095 and
                                  r.operation_id=='CONTROL128-OP','reducer rebuilt from original bytes')
            check(correlate_collected(p.plan,wire,p.original.companions,result_rows)['status']=='FOUR_FRAME_CORRELATION_CONSISTENT','correlation uses original snapshot')
            changed=json.loads(p.original.request);changed['scan']['lanes'][0]['raw_sample_uint16']=65535
            p.plan.original=OriginalBytes(json.dumps(changed,separators=(',',':')).encode(),p.original.source,p.original.companions)
            refused(lambda:Reducer(p.plan));refused(p.plan.facts)
            p=prepare(original());refused(lambda:prepare_bytes(p.original.request,p.original.source,p.original.companions+(b'extra',),build_binding=original()[3]))
            for key,value in [('refusal',1),('status',4)]:
                rows=[dict(x) for x in result_rows];rows[0][key]=value
                check(correlate_collected(p.plan,wire,p.original.companions,rows)['status']=='REFUSED_WITH_ORIGINAL_BYTES','inconsistent '+key)
            r=Reducer(p.plan);t=Transcript(p.plan);r.begin()
            def nonzero_refusal(i,a):
                if i['kind']=='read' and i['offset']==0x04c:a['value']=1
                return a
            drive(r,t,nonzero_refusal);check(r.failed and not r.completed and t.commands.count(4)==0,'nonzero refusal never ACKed as success')

        for name,fn in [('external_no_legacy_shape',case_external),('prewrite_representability_and_raw_refusals',case_refusals),('fourframe_crc_bytes_and_opaque_companions',case_frames),('one_scan_collect_and_consumed_interfaces',case_sequence),('prearm_dirty_identity_counter_headroom',case_prearm),('unknown_notattempted_error_and_owned_cleanup',case_unknown),('stable_call_identity_no_replay',case_identity),('finite_poll_call_write_evidence_time_budgets',case_budgets),('consumer_original_snapshot_and_result_refusal',case_consumer_snapshot)]:
            try:fn();rows.append({'name':name,'passed':True})
            except Exception as exc:rows.append({'name':name,'passed':False,'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
        code=0 if all(x['passed'] for x in rows) else 1
    except Exception:
        code=1;rows.append({'name':'setup_or_import','passed':False,'traceback':traceback.format_exc()})
    here=Path(__file__).resolve().parent
    pins=json.loads((here/'PINS.json').read_bytes())
    sources={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in here.iterdir() if p.is_file()}
    result={'kind':'NEW_AFFECTED_PURE_SOFTWARE_CONTROLS','exit_code':code,'groups':rows,'sources':sources,'dependency_pins':pins,
            'candidate_retry':False,'old_suites_executed':False,'physical_effects':False,'authority_not_evaluated':'NOT_EVALUATED_BY_THIS_ADAPTER'}
    raw=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2).encode()
    if len(raw)>524288:raise RuntimeError('bounded result exceeded')
    (out/'RESULT.json').write_bytes(raw)
    print(json.dumps({'groups':len(rows),'exit_code':code,'result_sha256':hashlib.sha256(raw).hexdigest()}))
    return code

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
    if not args.out.is_absolute():raise SystemExit('absolute new --out required')
    try:raise SystemExit(run(args.out))
    except FileExistsError:raise SystemExit(2)
