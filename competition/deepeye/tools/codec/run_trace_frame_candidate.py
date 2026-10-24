"""Bounded candidate45 author simulation. No public ABI or hardware enable."""
from collections import Counter
from datetime import datetime, timezone
import argparse
import binascii
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
WORKTREE = ROOT.parents[1]
REPO = Path('D:/pynq/CarlandFPGA')
AUTHOR = ROOT / 'evidence/codec/trace-frame-candidate-20261024-45/author'
SPEC = REPO / '.local/deployment/node-b/evidence/trace-frame-candidate-20261024-45/MAIN_SPEC.md'
REQ = 'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
PINS = {
 'fpga/codec/deepeye_trace_payload_timing_candidate.sv':'0d5ba11fe199708f8376c718bbf3484431adc8dd6e847666451b1b5e873cec7b',
 'fpga/codec/deepeye_block_encoder.sv':'4cb79428ef89096742e293516c4696caf985048d8185f531fe92eaa485c8d532',
 'fpga/transport/deepeye_wire_serializer.sv':'efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885',
 'fpga/transport/deepeye_crc16_byte.sv':'8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f',
 'golden/codec/trace_candidate.py':'a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642',
 'golden/codec/codec_reference.py':'2e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5',
 'golden/codec/trace_candidate_vectors.json':'e9fb59aa20324ebdeffb25ac89f43e42a085b3d49cec3ee9104ff551d9409bf2',
}
OWN = ['fpga/codec/deepeye_trace_frame_candidate.sv','fpga/codec/trace_frame_candidate.md',
       'tests/rtl/codec/tb_trace_frame_candidate.sv','tools/codec/run_trace_frame_candidate.py']
CFG = [('count',8),('e',4),('session',32),('channel',2),('first_index',32),('first_tick',64),
       ('index_stride',16),('tick_stride',16),('valid_sample',1),('saturated',1),('held',1),
       ('source_fault',1),('source_tick',64),('epoch',8),('seq',16)]
IN = [('rst',1),('cancel',1),('cfg_valid',1),('cfg',266),('s_valid',1),('s_data',16),
      ('s_last',1),('out_ready',1),('result_ready',1)]
OUT = [('cfg_ready',1),('s_ready',1),('out_valid',1),('out_data',8),('out_last',1),
       ('out_count',6),('result_valid',1),('result_error',3),('result_bytes',6),('busy',1),
       ('wire_faulted',1),('wire_fault_event',1),('wire_fault_code',2)]

def sha(data): return hashlib.sha256(data).hexdigest()
def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as f: f.write(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def pack(values,layout):
    n=0
    for key,width in layout:
        value=int(values[key])
        if not 0<=value<1<<width: raise ValueError('field out of range: '+key)
        n=(n<<width)|value
    return n
def unpack(value,layout):
    result={}
    for key,width in reversed(layout): result[key]=value&((1<<width)-1);value>>=width
    if value: raise ValueError('nonzero padding bits')
    return result
def load_golden(path):
    spec=importlib.util.spec_from_file_location('candidate45_published_payload',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module

def make_case(golden,name,points,binding,channel=0,sequence=0):
    first=points[0]; count=len(points)
    cfg=dict(count=count,e=binding['e'],session=binding['session'],channel=channel,
        first_index=first['index'],first_tick=first['tick_ms'],
        index_stride=points[1]['index']-first['index'] if count>1 else 0,
        tick_stride=points[1]['tick_ms']-first['tick_ms'] if count>1 else 0,
        valid_sample=int(first['valid']),saturated=int(first['saturated']),held=int(first['held']),
        source_fault=int(first['source_fault']),source_tick=first['source_tick_ms'] if first['valid'] else 0,
        epoch=binding['config_epoch'],seq=sequence)
    payload=golden.encode_payload(points,binding,channel)
    # Payload oracle is explicitly reused. Header/CRC are independently formed.
    header=b'\xa5\x5a\x03\x07'+bytes([len(payload),cfg['epoch']])+struct.pack('<HI',sequence,cfg['first_tick']&0xffffffff)
    frame=header+payload+struct.pack('<H',binascii.crc_hqx(header[2:]+payload,0xffff))
    return dict(name=name,cfg=cfg,samples=[p['value'] for p in points] if first['valid'] else [],
        last_mode=0,abort_at=-1,abort_kind=0,error=0,payload_hex=payload.hex(),frame_hex=frame.hex())

def points(values,tick=0x12345678abcdef01,index=123456,held_age=0,valid=True):
    return [dict(index=index+i,tick_ms=tick+10*i,value=value if valid else None,valid=valid,
        saturated=False,held=bool(held_age),source_fault=False,
        source_tick_ms=tick-held_age if held_age else (tick+10*i if valid else None)) for i,value in enumerate(values)]

def baseline_cases(golden,vectors):
    bind=dict(session=0x89abcdef,config_epoch=0xa7,e=0)
    warm=make_case(golden,'warmup_quality_only',points([0],valid=False),bind,2,0x39)
    profile=make_case(golden,'public_timing_profile',points([1000,1001,1002]),bind,3,0x7362)
    cases=[warm,profile]
    for vector in vectors['manual_vectors']['vectors']:
        cases.append(make_case(golden,'published_'+vector['name'],vector['points'],vector['binding'],vector['channel'],vector.get('sequence',0)))
    for vector in vectors['synthetic_vectors']:
        offset=0
        for part,ledger in enumerate(vector['ledger_per_frame']):
            count=ledger['count'];segment=vector['source_points'][offset:offset+count];offset+=count
            cases.append(make_case(golden,f"published_{vector['id']}_{part}",segment,vector['binding'],vector['channel'],vector['start_sequence']+part))
        if offset!=len(vector['source_points']):raise ValueError('published segment ledger incomplete')
    for e in [0,1,2,4,8]:
        b=dict(bind,e=e)
        cases.append(make_case(golden,f'e{e}_rice',points([1000,1001,1002]),b,e%4,100+e))
        cases.append(make_case(golden,f'e{e}_raw_single',points([65535]),b,e%4,200+e))
    cases.append(make_case(golden,'byte_tie_retains_original_raw',points([0,64]),bind,1,0xfedc))
    for age in [1,65535,65536]:
        cases.append(make_case(golden,f'held_age_{age}',points([0xabcd],held_age=age),bind,2,age&65535))
    cases.append(make_case(golden,'payload_exact32',points([65535]*41),bind,0,0x2828))
    cases.append(make_case(golden,'maximum_header_bytes',points([0x8001],tick=(1<<64)-1,index=(1<<32)-1),dict(bind,config_epoch=255),3,65535))
    def error_case(name,error,changes=None,last_mode=0,samples=None):
        c=copy.deepcopy(profile);c.update(name=name,error=error,frame_hex='',payload_hex='',last_mode=last_mode)
        c['cfg'].update(changes or {})
        if error==1:c['samples']=[]
        if samples is not None:c['samples']=samples
        cases.append(c)
    for name,changes in [
        ('count_zero',{'count':0}),('count129',{'count':129}),('bad_e',{'e':3}),
        ('single_stride',{'count':1,'index_stride':1}),('bad_invalid_quality',{'valid_sample':0,'held':1}),
        ('held_not_older',{'held':1,'source_tick':profile['cfg']['first_tick']}),
        ('unheld_wrong_source',{'source_tick':0}),('index_overflow',{'first_index':0xffffffff}),
        ('tick_overflow',{'first_tick':(1<<64)-1,'source_tick':(1<<64)-1})]:
        error_case(name,1,changes)
    error_case('early_last',2,last_mode=1)
    error_case('missing_last',2,last_mode=2)
    error_case('budget_raw33',3,{'count':4},samples=[0,65535,0,65535])
    error_case('budget_rice33',3,{'count':42},samples=[65535]*42)
    for i,c in enumerate(cases): c['id']=i
    if not any(len(bytes.fromhex(c['payload_hex']))==32 for c in cases):raise ValueError('no 32-byte boundary')
    return cases

def controls_cases(baseline,checks):
    profile=baseline[1];timing=checks['case_checks'][1]['timing']
    accepted=timing['cfg_local'];first=timing['first_out_local'];length=len(bytes.fromhex(profile['payload_hex']))
    targets={'new_cfg':-2,'preflight1':1,'preflight2':2,'preflight3':3,
        'load':timing['sample_locals'][1]-accepted,'metadata':first-length-1-accepted,
        'feed':first-length//2-accepted,'frame_header':timing['byte_locals'][3]-accepted,
        'frame_payload':timing['byte_locals'][12+length//2]-accepted,
        'frame_crc':timing['byte_locals'][12+length]-accepted,
        'frame_last':timing['byte_locals'][-1]-accepted,'report':timing['first_result_local']-accepted}
    cases=[copy.deepcopy(baseline[0])]
    for kind in [1,2]:
        for label,offset in targets.items():
            c=copy.deepcopy(profile);c.update(name=('reset_' if kind==1 else 'cancel_')+label,abort_kind=kind,abort_at=offset)
            cases.append(c)
            fresh=copy.deepcopy(profile);fresh['name']='fresh_after_'+c['name']
            fresh['cfg'].update(epoch=(17+len(cases))&255,seq=50000+len(cases))
            payload=bytes.fromhex(fresh['payload_hex'])
            header=b'\xa5\x5a\x03\x07'+bytes([len(payload),fresh['cfg']['epoch']])+struct.pack('<HI',fresh['cfg']['seq'],fresh['cfg']['first_tick']&0xffffffff)
            fresh['frame_hex']=(header+payload+struct.pack('<H',binascii.crc_hqx(header[2:]+payload,0xffff))).hex()
            cases.append(fresh)
    for i,c in enumerate(cases):c['id']=i
    return cases,dict(targets=targets,profile_case=profile['id'],baseline_timing=timing,
        derivation='public pre-edge config/sample/output/result timings; metadata=first_out-payload_length-1; FEED window inferred from fixed serializer buffering, no internal probes')

def check_case(case,rows):
    frame=bytes.fromhex(case['frame_hex']); sample_index=byte_index=0
    accepted=False;active=False;aborted=False;result_count=0
    stats=Counter();timing=dict(cfg_local=None,sample_locals=[],byte_locals=[],first_out_local=None,first_result_local=None)
    out_stalls=Counter();result_stalls=0;last_stalled_out=last_stalled_result=None
    live_changes=0; gaps=0
    for phase,local,gap,x,y in rows:
        control=bool(x['rst'] or x['cancel'])
        if any(y[k] for k in ['wire_faulted','wire_fault_event','wire_fault_code']):raise ValueError('unexpected reachable serializer fault')
        if control and any(y[k] for k in ['cfg_ready','s_ready','out_valid','out_last','result_valid']):raise ValueError('reset/cancel handshake not masked')
        if y['cfg_ready'] and y['busy']:raise ValueError('config credit while busy')
        if not control and y['busy']!=int(active):raise ValueError('busy differs from public transaction/report lifetime')
        if phase=='post' and control and y['busy']:raise ValueError('control did not synchronously clear top')
        if y['s_ready'] and (not active or y['out_valid'] or y['result_valid']):raise ValueError('sample credit outside wait-meta transaction')
        if gap:
            if any(y[k] for k in ['out_valid','result_valid','s_ready','busy']):raise ValueError('stale/duplicate output in fresh gap')
            if phase=='pre':gaps+=1
        if phase=='pre':
            if last_stalled_out is not None and not control and (y['out_valid'],y['out_data'],y['out_last'],y['out_count'])!=last_stalled_out:raise ValueError('framed output changed under stall')
            if last_stalled_result is not None and not control and (y['result_valid'],y['result_error'],y['result_bytes'])!=last_stalled_result:raise ValueError('result changed under stall')
            if control:
                if not case['abort_kind'] or (x['rst'],x['cancel'])!=((1,0) if case['abort_kind']==1 else (0,1)):raise ValueError('unexpected control kind')
                if (case['abort_at']==-2 and local!=0) or (case['abort_at']!=-2 and (timing['cfg_local'] is None or local-timing['cfg_local']!=case['abort_at'])):raise ValueError('control not at derived window')
            if accepted and x['cfg']!=pack(case['cfg'],CFG):live_changes+=1
        if y['out_valid']:
            if not active or case['error'] or byte_index>=len(frame):raise ValueError('early/extra/error frame byte')
            if sample_index!=len(case['samples']):raise ValueError('partial packet before samples validated')
            if (y['out_data'],y['out_last'],y['out_count'])!=(frame[byte_index],int(byte_index==len(frame)-1),len(frame)):raise ValueError(f"frame content/order/count differs at {case['name']} byte {byte_index}")
            if phase=='pre' and timing['first_out_local'] is None:timing['first_out_local']=local
        if y['result_valid']:
            if not active or (y['result_error'],y['result_bytes'])!=(case['error'],0 if case['error'] else len(frame)):raise ValueError('wrong/extra result')
            if not case['error'] and byte_index!=len(frame):raise ValueError('success reported before final frame retirement')
            if phase=='pre' and timing['first_result_local'] is None:timing['first_result_local']=local
        if phase=='pre':
            if x['cfg_valid'] and y['cfg_ready']:
                if accepted or x['cfg']!=pack(case['cfg'],CFG):raise ValueError('repeated/mismatched config acceptance')
                accepted=active=True;timing['cfg_local']=local;stats['cfg']+=1
            if x['s_valid'] and y['s_ready']:
                expected_last=int(sample_index==0) if case['last_mode']==1 else (0 if case['last_mode']==2 else int(sample_index==len(case['samples'])-1))
                if sample_index>=len(case['samples']) or (x['s_data'],x['s_last'])!=(case['samples'][sample_index],expected_last):raise ValueError('sample order/data/last mismatch')
                sample_index+=1;stats['samples']+=1;timing['sample_locals'].append(local)
            if y['out_valid']:
                if x['out_ready']:
                    if out_stalls[byte_index]<2:raise ValueError('frame byte not stalled twice')
                    timing['byte_locals'].append(local);byte_index+=1;stats['bytes']+=1
                else:out_stalls[byte_index]+=1
            if y['result_valid']:
                if x['result_ready']:
                    if result_stalls<3:raise ValueError('result not held for three stalls')
                    result_count+=1;stats['results']+=1;active=False
                else:result_stalls+=1
            if control:aborted=True;active=False;stats['controls']+=1
            last_stalled_out=(1,y['out_data'],y['out_last'],y['out_count']) if y['out_valid'] and not x['out_ready'] else None
            last_stalled_result=(1,y['result_error'],y['result_bytes']) if y['result_valid'] and not x['result_ready'] else None
    if gaps!=5:raise ValueError('missing five post-case recovery/duplicate checks')
    if case['abort_kind']:
        if not aborted or result_count or stats['controls']!=1:raise ValueError('abort produced a completion or was not exercised')
    else:
        expected_samples=1 if case['last_mode']==1 else len(case['samples'])
        if not accepted or aborted or result_count!=1 or byte_index!=(0 if case['error'] else len(frame)) or sample_index!=expected_samples:raise ValueError('incomplete transaction disposition')
    return dict(id=case['id'],name=case['name'],stats=dict(stats),timing=timing,
        bytes_retired=byte_index,result_count=result_count,aborted=aborted,live_cfg_changes=live_changes)

TRACE=re.compile(r'F45_TRACE cycle=([0-9]+) case=([0-9]+) local=([0-9]+) gap=([01]) phase=(pre|post) time=([0-9]+) inputs=([0-9a-f]{73}) outputs=([0-9a-f]{9})',re.I)
DONE=re.compile(r'F45_DONE cases=([0-9]+) cycles=([0-9]+) records=([0-9]+) cfg=([0-9]+) samples=([0-9]+) bytes=([0-9]+) results=([0-9]+) controls=([0-9]+)')

def qualify(raw,cases,tb_path,tb_hash):
    source=tb_path.read_bytes()
    if sha(source)!=tb_hash:raise ValueError('declared TB source hash differs')
    finish=[i for i,line in enumerate(source.decode().splitlines(),1) if re.fullmatch(r'\s*\$finish;\s*',line)]
    if len(finish)!=1:raise ValueError('ambiguous finish provenance')
    expected_path=tb_path.resolve().as_posix()
    text=raw.decode('utf-8','strict')
    if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u2028\u2029]',text):raise ValueError('forbidden control byte/separator')
    reduced=text.replace('\r\n','')
    if '\r' in reduced or ('\r\n' in text and '\n' in reduced):raise ValueError('malformed/mixed line endings')
    text=text.replace('\r\n','\n')
    if not text.endswith('\n'):raise ValueError('truncated transcript')
    state='header';started=ended=None;case_index=0;rows=[];checks=[];records=0;stats=Counter();last_pre=None;last_local=-1
    wall=r'([0-9]{2}:[0-9]{2}:[0-9]{2} on [A-Z][a-z]{2} [0-9]{1,2},[0-9]{4})'
    for rawline in text.split('\n')[:-1]:
        reserved=('F45_' in rawline or any(s in rawline for s in ['Start time:','$finish','End time:',
            'Errors:','Warnings:','Break at ','Stopped at ','Instance:','Time:','Iteration:','Elapsed time:']))
        if reserved and not rawline.startswith('# '):raise ValueError('reserved record requires exact simulator # prefix')
        line=rawline[2:] if rawline.startswith('# ') else rawline
        if re.search(r'\*\* (Error|Fatal|Warning)|F45_BAD_|F45_SHORT_|F45_EXTRA_|F45_CASE_TIMEOUT',line):raise ValueError('vendor/TB error: '+line)
        if state=='complete':raise ValueError('trailing or duplicate footer data')
        if state in ['final','finish','time','break','stopped','end']:
            if not rawline.startswith('# '):raise ValueError('malformed footer prefix')
            if state=='final':
                m=re.fullmatch(r'\*\* Note: \$finish    : (.+)\(([0-9]+)\)',line)
                if not m or m[1].replace('\\','/')!=expected_path or int(m[2])!=finish[0]:raise ValueError('wrong/missing pinned finish location')
                state='finish'
            elif state=='finish':
                m=re.fullmatch(r'   Time: ([0-9]+) ns  Iteration: 0  Instance: /tb_trace_frame_candidate',line)
                if not m or int(m[1])!=16+10*(records//2-1):raise ValueError('finish time/instance conflicts with trace')
                state='time'
            elif state in ['time','break']:
                name='Break' if state=='time' else 'Stopped'
                m=re.fullmatch(name+r' at (.+) line ([0-9]+)',line)
                if not m or m[1].replace('\\','/')!=expected_path or int(m[2])!=finish[0]:raise ValueError('wrong '+name+' location')
                state='break' if state=='time' else 'stopped'
            elif state=='stopped':
                m=re.fullmatch('End time: '+wall+r', Elapsed time: ([0-9]+):([0-9]{2}):([0-9]{2})',line)
                if not m or int(m[3])>=60 or int(m[4])>=60:raise ValueError('invalid End marker')
                ended=datetime.strptime(m[1],'%H:%M:%S on %b %d,%Y')
                if (ended-started).total_seconds()!=int(m[2])*3600+int(m[3])*60+int(m[4]):raise ValueError('Start/End elapsed conflict')
                state='end'
            else:
                if line!='Errors: 0, Warnings: 0':raise ValueError('nonzero/missing simulator summary')
                state='complete'
            continue
        if 'Start time:' in line:
            m=re.fullmatch('Start time: '+wall,line)
            if state!='header' or started is not None or not m:raise ValueError('duplicate/malformed Start marker')
            started=datetime.strptime(m[1],'%H:%M:%S on %b %d,%Y');continue
        if any(s in line for s in ['$finish','End time:','Errors:','Warnings:','Break at ','Stopped at ','Instance:','Time:','Iteration:','Elapsed time:']):raise ValueError('out-of-order terminal marker')
        if 'F45_' not in line:
            if state!='header':raise ValueError('unexpected data in trace')
            continue
        if line==f'F45_BEGIN cases={len(cases)}':
            if state!='header' or started is None:raise ValueError('duplicate/out-of-order BEGIN')
            state='cases'
        elif line==f'F45_CASE_BEGIN id={case_index}':
            if state!='cases' or case_index>=len(cases):raise ValueError('out-of-order case begin')
            rows=[];last_local=-1;state='case'
        elif m:=TRACE.fullmatch(line):
            if state!='case':raise ValueError('trace outside case')
            cycle,cid,local,gap,time_ns=map(int,[m[1],m[2],m[3],m[4],m[6]]);phase=m[5]
            expected_phase='pre' if records%2==0 else 'post'
            if (cycle,cid,phase,time_ns)!=(records//2,case_index,expected_phase,11+10*(records//2)+(5 if phase=='post' else 0)):raise ValueError('trace cycle/case/phase/time order')
            x=unpack(int(m[7],16),IN);y=unpack(int(m[8],16),OUT)
            if phase=='pre':
                if local!=last_local+1:raise ValueError('duplicate/conflicting local trace row')
                last_local=local;last_pre=(local,gap,x)
            elif (local,gap,x)!=last_pre:raise ValueError('pre/post input history differs')
            rows.append((phase,local,gap,x,y));records+=1
        elif case_index<len(cases) and line==f"F45_CASE_END id={case_index} reason={'control' if cases[case_index]['abort_kind'] else 'result'}":
            if state!='case' or records%2:raise ValueError('incomplete/duplicate case end')
            checked=check_case(cases[case_index],rows);checks.append(checked);stats.update(checked['stats']);case_index+=1;state='cases'
        elif m:=DONE.fullmatch(line):
            expected=[len(cases),records//2,records,*[stats[k] for k in ['cfg','samples','bytes','results','controls']]]
            if state!='cases' or case_index!=len(cases) or list(map(int,m.groups()))!=expected:raise ValueError('DONE statistics conflict with raw public handshakes')
            state='done'
        elif line=='F45_FINAL result=PASS':
            if state!='done':raise ValueError('duplicate/out-of-order FINAL')
            state='final'
        else:raise ValueError('malformed/substring/conflicting reserved marker: '+line)
    if state!='complete':raise ValueError('incomplete trace/simulator termination')
    return dict(cases=len(cases),cycles=records//2,records=records,stats=dict(stats),case_checks=checks,
        golden_scope='published payload only; independently packed header + binascii CRC',
        fault_guard='structurally unreachable via correct public42/28 streams; not forced or dynamically covered',
        simulator_termination=dict(tb_source=str(tb_path),tb_sha256=tb_hash,finish_line=finish[0],errors=0,warnings=0))

class Commands:
    def __init__(self,out):self.out=out;self.records=[]
    def run(self,label,argv,cwd,timeout=60):
        directory=self.out/'commands';directory.mkdir(exist_ok=True)
        stem=f'{len(self.records)+1:02d}-{label}'
        stdout=directory/(stem+'.stdout.bin');stderr=directory/(stem+'.stderr.bin')
        record=dict(label=label,argv=list(map(str,argv)),cwd=str(cwd),started_utc=datetime.now(timezone.utc).isoformat(),hidden=True,timeout_seconds=timeout)
        self.records.append(record)
        si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=subprocess.SW_HIDE
        with stdout.open('xb') as output,stderr.open('xb') as error:
            p=subprocess.Popen(record['argv'],cwd=cwd,stdin=subprocess.DEVNULL,stdout=output,stderr=error,startupinfo=si,creationflags=subprocess.CREATE_NO_WINDOW)
            record['pid']=p.pid;record['parent_pid']=os.getpid()
            try:record['exit_code']=p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                record['timed_out']=True;p.kill();record['exit_code']=p.wait()
        record.update(finished_utc=datetime.now(timezone.utc).isoformat(),stdout=str(stdout),stderr=str(stderr),stdout_sha256=sha(stdout.read_bytes()),stderr_sha256=sha(stderr.read_bytes()))
        save(directory/(stem+'.json'),record)
        if record['exit_code']!=0 or record.get('timed_out'):raise RuntimeError(f"{label} exit {record['exit_code']}; raw files {stem}")
        return stdout.read_bytes()

def scenario(out,name,cases,commands,compile_dir,tb,tb_hash):
    directory=out/name;directory.mkdir(exist_ok=False)
    save(directory/'cases.json',cases)
    data=''
    for case in cases:
        data+=f"{case['id']} {pack(case['cfg'],CFG):067x} {len(case['samples'])} {case['last_mode']} {case['abort_at']} {case['abort_kind']}\n"
        data+=''.join(f'{s:04x}\n' for s in case['samples'])
    stimulus=directory/'input.txt';stimulus.write_text(data,encoding='ascii')
    macro=directory/'run.do';macro.write_text('onerror {quit -code 2}\nrun -all\nquit -code 0\n',encoding='ascii')
    raw=commands.run(name+'-vsim',[Path('D:/modelsim1/win64/vsim.exe'),'-c','-t','1ns','-onfinish','stop',
        '-lib','work','tb_trace_frame_candidate','+INPUT='+stimulus.resolve().as_posix(),'+CASES='+str(len(cases)),
        '-l',directory/'transcript.log','-wlf',directory/'waves.wlf','-do','do {'+macro.resolve().as_posix()+'}'],compile_dir,120)
    checked=qualify(raw,cases,tb,tb_hash)
    save(directory/'checks.json',checked)
    save(directory/'raw_provenance.json',dict(stdout=commands.records[-1]['stdout'],sha256=sha(raw),input_sha256=sha(stimulus.read_bytes()),tb_sha256=tb_hash))
    print(json.dumps(dict(event='scenario_checked',name=name,cases=checked['cases'],cycles=checked['cycles'],records=checked['records'])),flush=True)
    return raw,checked

def negatives(out,raw,cases,tb,tb_hash):
    directory=out/'negative-controls';directory.mkdir(exist_ok=False)
    lines=raw.decode('utf-8').splitlines(keepends=True)
    positions={kind:next(i for i,line in enumerate(lines) if line.startswith('# F45_'+kind)) for kind in ['BEGIN','CASE_BEGIN','TRACE','CASE_END','DONE','FINAL']}
    mutations={}
    base_lines=raw.splitlines(keepends=True)
    base_path=directory/'base.stdout.bin'
    with base_path.open('xb') as f:f.write(raw)
    base_hash=sha(raw)
    def store(name,data):
        modified=data.splitlines(keepends=True);prefix=0
        while prefix<min(len(base_lines),len(modified)) and base_lines[prefix]==modified[prefix]:prefix+=1
        suffix=0
        while suffix<min(len(base_lines)-prefix,len(modified)-prefix) and base_lines[-1-suffix]==modified[-1-suffix]:suffix+=1
        end=len(modified)-suffix
        mutations[name]=dict(name=name,operation='splice_lines',index=prefix,
            delete_lines=len(base_lines)-prefix-suffix,replacement_hex=b''.join(modified[prefix:end]).hex(),
            base_path=str(base_path),base_sha256=base_hash,mutated_sha256=sha(data),bytes=len(data),expected='reject')
    def change(name,func):
        modified=list(lines);func(modified);store(name,''.join(modified).encode())
    for kind in ['BEGIN','CASE_BEGIN','CASE_END','DONE','FINAL']:
        i=positions[kind]
        change('duplicate_'+kind.lower(),lambda ls,i=i:ls.insert(i,ls[i]))
        change('prefix_'+kind.lower(),lambda ls,i=i:ls.__setitem__(i,'prefix '+ls[i]))
        change('suffix_'+kind.lower(),lambda ls,i=i:ls.__setitem__(i,ls[i].rstrip('\r\n')+' suffix\r\n'))
    i=positions['TRACE']
    change('duplicate_trace_row',lambda ls:ls.insert(i,ls[i]))
    change('conflicting_trace_row',lambda ls:ls.__setitem__(i,ls[i].replace('cycle=0','cycle=1')))
    i=positions['DONE']
    change('conflicting_done_bytes',lambda ls:ls.__setitem__(i,re.sub(r'bytes=\d+','bytes=1',ls[i])))
    change('missing_done',lambda ls:ls.pop(i))
    i=next(i for i,line in enumerate(lines) if line.startswith('# ** Note: $finish'))
    change('wrong_finish_source',lambda ls:ls.__setitem__(i,ls[i].replace('tb_trace_frame_candidate.sv','other_source.sv')))
    change('duplicate_finish',lambda ls:ls.insert(i,ls[i]))
    change('missing_finish',lambda ls:ls.pop(i))
    i=next(i for i,line in enumerate(lines) if line.startswith('# Errors:'))
    change('nonzero_error_footer',lambda ls:ls.__setitem__(i,'# Errors: 1, Warnings: 0\r\n'))
    change('duplicate_conflicting_footer',lambda ls:ls.append('# Errors: 9, Warnings: 0\r\n'))
    byte_line=None
    for i,line in enumerate(lines):
        m=TRACE.fullmatch(line[2:].rstrip('\r\n')) if line.startswith('# ') else None
        if m and unpack(int(m[8],16),OUT)['out_valid']:
            byte_line=i;break
    if byte_line is None:raise ValueError('no actual output byte for negative derivation')
    def corrupt_byte(ls):
        line=ls[byte_line];m=re.search(r'outputs=([0-9a-f]{9})',line);y=unpack(int(m[1],16),OUT);y['out_data']^=1
        ls[byte_line]=line[:m.start(1)]+f'{pack(y,OUT):09x}'+line[m.end(1):]
    change('corrupt_actual_framed_byte',corrupt_byte)
    for name,data in dict(nul=raw+b'\0\r\n',invalid_utf8=raw+b'\xff\r\n',truncated_footer=raw[:raw.index(b'# ** Note: $finish')],truncated_bytes=raw[:-7],trailing_plain=raw+b'trailing\r\n').items():store(name,data)
    markers=['F45_BEGIN','F45_CASE_BEGIN','F45_TRACE','F45_CASE_END','F45_DONE','F45_FINAL','Start time:',
        '** Note: $finish','   Time:','Break at ','Stopped at ','End time:','Errors:']
    for marker in markers:
        i=next(i for i,line in enumerate(lines) if line.startswith('# '+marker))
        for label,prefix in [('missing',''),('tab','#\t'),('leading_space',' # '),('no_space','#')]:
            change('prefix_'+label+'_'+marker.replace(' ','_').replace(':','').replace('*','').replace('$',''),
                lambda ls,i=i,prefix=prefix:ls.__setitem__(i,prefix+ls[i][2:]))
    begin=positions['BEGIN']
    for marker,value in [('Time:','999 ns'),('Iteration:','9'),('Elapsed time:','99:00:00')]:
        for label,index in [('before_begin',begin),('after_footer',len(lines))]:
            change('out_of_order_'+marker.replace(' ','_').replace(':','')+'_'+label,
                lambda ls,index=index,marker=marker,value=value:ls.insert(index,'# '+marker+' '+value+'\r\n'))
    recipes=list(mutations.values())
    save(directory/'recipes.json',dict(base_path=str(base_path),base_sha256=base_hash,
        semantics='zero-based byte splitlines(keepends=True), replace delete_lines with bytes.fromhex(replacement_hex)',recipes=recipes))
    if sha(base_path.read_bytes())!=base_hash:raise ValueError('saved negative-control base changed')
    results=[]
    for recipe in recipes:
        parts=list(base_lines);index=recipe['index']
        parts[index:index+recipe['delete_lines']]=[bytes.fromhex(recipe['replacement_hex'])]
        data=b''.join(parts)
        if sha(data)!=recipe['mutated_sha256']:raise ValueError('negative recipe reconstruction differs')
        row=dict(name=recipe['name'],sha256=sha(data),recipe_path=str(directory/'recipes.json'),base_sha256=base_hash,bytes=len(data))
        try:qualify(data,cases,tb,tb_hash)
        except ValueError as exc:row.update(rejected=True,error=str(exc))
        else:row.update(rejected=False)
        results.append(row)
    save(directory/'RESULT.json',results)
    if not all(x['rejected'] for x in results):raise ValueError('negative checker admitted malformed saved log')
    normalized=raw.replace(b'\r\n',b'\n')
    (directory/'positive_lf.stdout.bin').write_bytes(normalized)
    qualify((directory/'positive_lf.stdout.bin').read_bytes(),cases,tb,tb_hash)
    return dict(total=len(results),rejected=len(results),positive_lf_passed=True,
        derivation='actual saved baseline; exact byte-hashed compact splice recipes retained, one base copy, no full log per probe')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=AUTHOR/'attempt-01');args=parser.parse_args()
    out=args.out.resolve()
    if not out.is_relative_to(AUTHOR.resolve()) or out==AUTHOR.resolve() or out.exists():raise ValueError('require new exclusive owned output child; input aliases/preexisting output refused')
    out.mkdir(parents=True,exist_ok=False);commands=Commands(out)
    result=dict(schema='deepeye.trace-frame.author.v1',task_id='DEEPEYE-IMPLEMENTATION-20261014/v1',
        work_id='B-TRACE-FRAME-CANDIDATE-20261024-45-v1',operation_id='B-DEEPEYE-TRACE-FRAME-CANDIDATE-20261024-45',
        canonical_agent_id='01a16a27-3458-7103-a4ab-cd06fd084da7',job_id='child-8e67b7c2a9b545dcbb8d7315c1ace65f',
        main_agent_id='01a13b55-095b-7461-8dd5-5476a130bd82',requirements_ids=[f'H{i:02d}' for i in range(1,16)],
        requirements_sha256=REQ,contract_commit='f5989cd5defce561f9ba98e6b18fc2682945f0a2',
        frozen_design='1011259415a0916054eb580687612580bc1e5f09',status='running',
        started_utc=datetime.now(timezone.utc).isoformat(),python_executable=sys.executable,python_version=sys.version,
        pid=os.getpid(),parent_pid=os.getppid(),argv=sys.argv,formal_cards=dict(count=29,status='not_run'),
        authority='bounded author implementation; main retains independent evaluation/acceptance',
        public_type7_enabled=False,hardware_enable_eligible=False,board='not_run',synthesis='not_run',source_authenticity='not_claimed')
    protected={rel:ROOT/rel for rel in PINS}
    protected['MAIN_SPEC.md']=SPEC
    protected['dirty_codec_input.json']=WORKTREE/'handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json'
    sources={**protected,**{rel:ROOT/rel for rel in OWN}}
    before={}
    try:
        for rel,path in sources.items():
            if not path.is_file() or path.is_symlink():raise ValueError('missing/symlink source '+rel)
            data=path.read_bytes();before[rel]=sha(data)
            # The dirty user input is fingerprinted but not copied/distributed.
            if rel!='dirty_codec_input.json':
                dest=out/'inputs'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        save(out/'source_pins_before.json',before)
        for rel,pin in PINS.items():
            if before[rel]!=pin:raise ValueError('published source pin differs: '+rel)
        if before['dirty_codec_input.json']!='6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8':raise ValueError('original dirty codec input pin differs')
        if before['MAIN_SPEC.md']!='4d73379b986648b9480d648de1cc8ec4bd4515d8b56994749488671705f443c6':raise ValueError('main specification pin differs')
        contract=commands.run('contract',['git','show','f5989cd5defce561f9ba98e6b18fc2682945f0a2:docs/competition/deepeye-2026/immutable_scope.json'],WORKTREE)
        requirements=json.loads(contract)['requirements']
        if sha(json.dumps(requirements,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())!=REQ:raise ValueError('fixed human contract requirements hash differs')
        (out/'inputs/immutable_scope.json').write_bytes(contract)
        result['actual_head_at_start']=commands.run('head',['git','rev-parse','HEAD'],WORKTREE).decode().strip()
        model=load_golden(out/'inputs/golden/codec/trace_candidate.py')
        cases=baseline_cases(model,json.loads((out/'inputs/golden/codec/trace_candidate_vectors.json').read_text(encoding='utf-8')))
        result['baseline_case_count']=len(cases)
        compile_dir=out/'compile';compile_dir.mkdir()
        vendor=Path('D:/modelsim1/win64')
        result['tool_executable_sha256']={name:sha((vendor/(name+'.exe')).read_bytes()) for name in ['vlib','vlog','vsim']}
        commands.run('vlog-version',[vendor/'vlog.exe','-version'],compile_dir)
        commands.run('vsim-version',[vendor/'vsim.exe','-version'],compile_dir)
        commands.run('vlib',[vendor/'vlib.exe','work'],compile_dir)
        rtl=['fpga/codec/deepeye_block_encoder.sv','fpga/codec/deepeye_trace_payload_timing_candidate.sv',
             'fpga/transport/deepeye_crc16_byte.sv','fpga/transport/deepeye_wire_serializer.sv',OWN[0],OWN[2]]
        compiled=commands.run('vlog',[vendor/'vlog.exe','-sv','-work','work',*[out/'inputs'/rel for rel in rtl]],compile_dir)
        if re.search(rb'\*\* (Warning|Error|Fatal)',compiled):raise ValueError('unexpected compiler diagnostic')
        tb=out/'inputs'/OWN[2];tb_hash=before[OWN[2]]
        raw,checked=scenario(out,'baseline',cases,commands,compile_dir,tb,tb_hash)
        result['baseline_checks']=checked
        control_cases,windows=controls_cases(cases,checked)
        windows['actual_baseline_stdout_sha256']=sha(raw)
        save(out/'public_timing_window_derivation.json',windows)
        controls_raw,controls_checked=scenario(out,'controls',control_cases,commands,compile_dir,tb,tb_hash)
        result['control_checks']=controls_checked
        result['checker_negative_controls']=negatives(out,raw,cases,tb,tb_hash)
        result['coverage']=dict(e_values=sorted({c['cfg']['e'] for c in cases if c['error']==0}),
            payload_lengths=sorted({len(bytes.fromhex(c['payload_hex'])) for c in cases if c['error']==0}),
            errors=sorted({c['error'] for c in cases}),control_targets=windows['targets'],
            aborted_cases=sum(c['abort_kind']!=0 for c in control_cases),fresh_successful_recoveries=sum(c['name'].startswith('fresh_after_') for c in control_cases),
            all_four_channels=sorted({c['cfg']['channel'] for c in cases if c['error']==0}),
            frame_byte_stalls='at least two for every retired byte',result_stalls='at least three for every acknowledged result',
            fault_guard='not dynamically reached; no internal forces; structural guard disclosed')
        if result['coverage']['e_values']!=[0,1,2,4,8] or result['coverage']['all_four_channels']!=[0,1,2,3]:raise ValueError('required E/channel coverage missing')
        result['status']='bounded_author_checks_passed_pending_main'
    except Exception as exc:
        result.update(status='failed',error_type=type(exc).__name__,error=str(exc))
        (out/'exception.stderr.txt').write_text(traceback.format_exc(),encoding='utf-8')
    finally:
        after={rel:sha(path.read_bytes()) for rel,path in sources.items() if path.is_file()}
        save(out/'source_pins_after.json',after)
        result.update(source_pins_before=before,source_pins_after=after,all_protected_and_owned_sources_unchanged=bool(before) and before==after,commands=commands.records,finished_utc=datetime.now(timezone.utc).isoformat())
        if before!=after:result.update(status='failed',pin_error='source bytes changed during execution')
        save(out/'RESULT.json',result)
        save(out/'artifact_sha256.json',{p.relative_to(out).as_posix():sha(p.read_bytes()) for p in sorted(out.rglob('*')) if p.is_file()})
    print(json.dumps(dict(status=result['status'],error=result.get('error'),evidence=str(out))),flush=True)
    return 0 if result['status']=='bounded_author_checks_passed_pending_main' else 1

if __name__=='__main__':raise SystemExit(main())
