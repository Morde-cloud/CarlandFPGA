"""Pure TRACE103 transaction sequence; physical entry is unconditionally closed.

No device, PYNQ, clock, process, network or physical-provider imports. A future
original adapter is not implemented or selectable by caller callback/object.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path

WORK_ID = 'B-DEEPEYE-FUNCTIONAL50-BOUNDED-HOST-20261031-103'
REQUIREMENTS = 'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
KIND = 'SOFTWARE_FAKE_CSR'
U32 = (1 << 32) - 1
U63 = (1 << 63) - 1
HOST_REL = 'competition/deepeye/tools/diagnostic/g05_capture/additive50_source_candidate/deepeye_transport50_source_candidate.py'
HOST_SHA = '1f4da870d9c885a3cc6156c30d2170e21001187392a59a19172c059c9ab0c768'
TRACE_REL = 'competition/deepeye/golden/codec/trace_candidate.py'
TRACE_SHA = 'a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642'
DEFAULT_LIMITS = {
    'wire': 252, 'retained': 4096, 'frames': 4, 'pops': 4096,
    'csr': 65536, 'polls': 2048, 'writes': 128, 'cleanup_polls': 256,
    'work_seconds': 10, 'cleanup_seconds': 2, 'nominal_parent_seconds': 15,
    'work_evidence': 6*1024*1024, 'cleanup_evidence': 1024*1024,
    'final_evidence': 1024*1024,
}

class Refused(ValueError):
    pass

def need(ok, message):
    if not ok:
        raise Refused(message)

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf8')

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def uint(value, upper, name):
    need(type(value) is int and 0 <= value <= upper, name)
    return value

def strict_json(raw, limit=262144):
    need(type(raw) is bytes and 0 < len(raw) <= limit, 'bounded JSON bytes')
    def pairs(items):
        d = {}
        for key, value in items:
            need(key not in d, 'duplicate JSON key')
            d[key] = value
        return d
    def constant(value):
        raise Refused('nonfinite JSON')
    return json.loads(raw.decode('utf8'), object_pairs_hook=pairs, parse_constant=constant)

def stop(reason):
    return {'status': 'STOP', 'input_status': reason, 'command': None,
            'core_ran': False, 'current_source_eligible': False,
            'physical_access_attempted': False, 'acceptance': False}

def physical_start(*args, **kwargs):
    """Do not inspect or invoke arbitrary supplied handles/proof objects."""
    return stop('A_ORIGINAL_PROVIDER_UNAVAILABLE')

def load_pinned(path, expected, name):
    need(sha(path.read_bytes()) == expected, 'pinned module bytes: ' + name)
    spec = importlib.util.spec_from_file_location(name, path)
    need(spec is not None and spec.loader is not None, 'module loader')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def inspect_hwh(hwh, mapping, build_id, repo_root, pins):
    """Explicit local file inspection only. This never opens an MMIO window."""
    root = Path(repo_root)
    rel = 'competition/deepeye/tools/diagnostic/functional50_build98/verify_functional50_hwh.py'
    contract = 'competition/deepeye/tools/diagnostic/functional50_build98/functional50_contract.py'
    need(sha((root / contract).read_bytes()) == pins[contract]['sha256'], 'HWH contract pin')
    module = load_pinned(root / rel, pins[rel]['sha256'], 'host103_hwh_inspector')
    result = module.verify_hwh(Path(hwh), mapping, build_id)
    return {'kind': 'STATIC_HWH_STRUCTURE_ONLY', 'result': result,
            'physical_provider': 'A_ORIGINAL_PROVIDER_UNAVAILABLE', 'current_source_eligible': False}

def inspect_plan(plan):
    need(type(plan) is dict and plan.get('kind') == KIND, 'explicit software fake plan')
    need(plan.get('requirements_sha256') == REQUIREMENTS, 'H01-H15 pin')
    need(len(canonical(plan)) <= 262144, 'plan byte budget')
    need(set(plan) == {'kind', 'requirements_sha256', 'origin_qpc_ns', 'arm_tag',
         'build_id', 'lanes', 'original104_source_commit', 'provenance'}, 'exact plan fields')
    origin = uint(plan['origin_qpc_ns'], U63, 'origin uint63')
    uint(plan['arm_tag'], U32, 'arm tag')
    need(plan['arm_tag'] > 0, 'nonzero arm tag')
    need(type(plan['build_id']) is str and len(plan['build_id']) == 32 and
         all(c in '0123456789abcdef' for c in plan['build_id']) and int(plan['build_id'],16)>0, 'fake BUILD_ID')
    need(type(plan['provenance']) is str and len(plan['provenance']) <= 1024, 'bounded provenance')
    need(type(plan['lanes']) is list and len(plan['lanes']) == 4, 'one four-lane scan')
    previous_seq = -1
    tick = None
    for i, lane in enumerate(plan['lanes']):
        need(type(lane) is dict and set(lane) == {'channel','count','quality','acquisition_qpc_ns',
             'acquisition_tick_us','acquisition_remainder_ns','source_qpc_ns','source_tick_us',
             'source_remainder_ns','session','index','view','frame_seq'}, 'exact lane fields')
        need(lane['channel'] == i and type(lane['channel']) is int, 'four ordered channels')
        quality = uint(lane['quality'],15,'local quality')
        valid, saturated, held = bool(quality&1), bool(quality&2), bool(quality&4)
        if valid:
            uint(lane['count'],4095,'count uint12')
        else:
            need(lane['count'] is None and not saturated and not held, 'invalid remains None')
        acq = uint(lane['acquisition_qpc_ns'],U63,'acquisition uint63')
        need(tick is None or acq == tick, 'common scan tick')
        tick = acq
        for k in ('session','index','acquisition_tick_us'):
            uint(lane[k],U32,k)
        uint(lane['view'],255,'view');uint(lane['frame_seq'],65535,'frame sequence')
        need(lane['frame_seq'] > previous_seq, 'strict nonwrapping frame sequence')
        previous_seq = lane['frame_seq']
        uint(lane['acquisition_remainder_ns'],999,'acquisition remainder')
        need(origin+lane['acquisition_tick_us']*1000+lane['acquisition_remainder_ns']==acq, 'exact acquisition origin')
        if valid:
            source=uint(lane['source_qpc_ns'],U63,'source uint63')
            uint(lane['source_tick_us'],U32,'source tick');uint(lane['source_remainder_ns'],999,'source remainder')
            need(origin+lane['source_tick_us']*1000+lane['source_remainder_ns']==source and
                 source<=acq and held==(source<acq), 'exact held/fresh source')
        else:
            need(all(lane[k] is None for k in ('source_qpc_ns','source_tick_us','source_remainder_ns')), 'null source fields')
    return {'status':'SOFTWARE_PLAN_INSPECTED','physical_provider':'A_ORIGINAL_PROVIDER_UNAVAILABLE',
            'plan_sha256':sha(canonical(plan)), 'frames':4,'normal_wire_limit':252}

def read(offset, label, poll=False):
    return {'kind':'read','offset':offset,'value':None,'label':label,'poll':poll,'pop_related':False}

def write(offset, value, label, pop_related=False):
    uint(value,U32,'write word')
    return {'kind':'write','offset':offset,'value':value,'label':label,'poll':False,'pop_related':pop_related}

class TraceSequence:
    """Generator of intents and reducer of returned observations; no effects."""
    def __init__(self, plan):
        inspect_plan(plan)
        self.plan = strict_json(canonical(plan))
        self.start_consumed = self.collect_consumed = self.cancel_consumed = False
        self.completed = self.quiescent = False
        self.results = []
        self.confirmed_prefix = bytearray()
        self.pending_byte = None
        self.last_pop_id = self.unread_count = None
        self.unknown_effects = False

    def _quiet(self):
        state = yield read(0x018,'state')
        status = yield read(0x020,'status')
        need(state in (0,9) and status&2 and not status&0x14, 'CANCEL/COMPLETE and quiescent/RXidle/no result')
        self.quiescent = True
        return state

    def _wait(self, target):
        while True:
            fault = yield read(0x01c,'sticky fault')
            need(fault==0, 'sticky fault')
            state = yield read(0x018,'progress',True)
            if state == target:
                return
            need(state != 0, 'unexpected CANCEL')

    def start(self):
        need(not self.start_consumed, 'start already consumed')
        self.start_consumed = True
        return self._start()

    def _start(self):
        expected={0:0x54353046,4:1,8:4,12:50000000,16:1000000,20:4096}
        for offset,value in expected.items():
            observed=yield read(offset,'identity')
            need(observed==value,'TRACE identity')
        build=int(self.plan['build_id'],16)
        for i in range(4):
            observed=yield read(0x060+4*i,'BUILD_ID')
            need(observed==((build>>(32*i))&U32),'TRACE BUILD_ID')
        state=yield from self._quiet()
        need(state==0,'clean initial CANCEL')
        fault=yield read(0x01c,'initial faults');count=yield read(0x030,'initial FIFO')
        need(fault==0 and count==0,'dirty device refused without cleanup')
        status=yield read(0x020,'initial empty status')
        need(status&0x20,'initial FIFO empty status')
        prior_tag=yield read(0x02c,'prior arm tag')
        need(self.plan['arm_tag']>prior_tag,'fresh arm tag')
        origin=self.plan['origin_qpc_ns']
        for offset,value in ((0x100,self.plan['arm_tag']),(0x104,origin&U32),(0x108,origin>>32)):
            yield write(offset,value,'ARM staging')
        yield write(0x080,1,'ARM once')
        yield from self._wait(3)
        tag=yield read(0x02c,'accepted arm tag');need(tag==self.plan['arm_tag'],'ARM accepted tag')
        for lane in self.plan['lanes']:
            acq=lane['acquisition_qpc_ns']
            for off,val in ((0x110,lane['channel']),(0x114,lane['count'] if lane['count'] is not None else 0),
                            (0x118,acq&U32),(0x11c,acq>>32),(0x120,lane['quality'])):
                yield write(off,val,'PUSH staging')
            yield write(0x080,2,'PUSH once')
            next_ch=yield read(0x024,'next push');need(next_ch==lane['channel']+1,'PUSH observation')
        yield from self._wait(4)
        previous_result=yield read(0x040,'prior result ID')
        for lane in self.plan['lanes']:
            source=lane['source_qpc_ns'] or 0
            values=(lane['session'],lane['index'],lane['acquisition_tick_us'],lane['acquisition_remainder_ns'],
                    source&U32,source>>32,lane['source_tick_us'] or 0,lane['source_remainder_ns'] or 0,lane['view'],lane['frame_seq'])
            for i,value in enumerate(values):
                yield write(0x130+4*i,value,'BIND staging')
            yield write(0x080,3,'BIND once')
            yield from self._wait(7)
            row={}
            for key,offset in (('id',0x040),('error',0x044),('bytes',0x048),('refusal',0x04c),('rx_before',0x050),('rx_end',0x07c),('status',0x020)):
                row[key]=yield read(offset,'result '+key)
            self.results.append(row)
            need(row['id']==previous_result+1 and row['id']<=U32,'exact result ID increment')
            need(row['error']==0 and 0<row['bytes']<=63 and row['rx_end']==row['rx_before']+row['bytes'] and
                 row['rx_end']<=U32 and row['status']&0x10 and not row['status']&4,'successful result wire/idle association')
            previous_result=row['id']
            yield write(0x160,row['id'],'ACK ID staging')
            yield write(0x080,4,'ACK once')
            yield from self._wait(9 if lane['channel']==3 else 4)
            next_ch=yield read(0x028,'next association');need(next_ch==lane['channel']+1,'ACK observation')
        need(sum(r['bytes'] for r in self.results)<=252,'normal wire byte ceiling')
        self.completed=True

    def collect(self):
        need(not self.collect_consumed,'collect already consumed')
        self.collect_consumed=True
        return self._collect()

    def _collect(self):
        yield from self._quiet()
        self.unread_count=yield read(0x030,'collect FIFO count')
        need(0<=self.unread_count<=4096,'FIFO retention bound')
        if self.completed:
            need(self.unread_count==sum(r['bytes'] for r in self.results) and self.unread_count<=252,'complete FIFO byte count')
        self.last_pop_id=yield read(0x038,'initial POP ID')
        initial=self.unread_count
        for _ in range(initial):
            peek=yield read(0x070,'non-destructive peek')
            need(peek&0x100 and peek<=0x1ff,'peek valid independent of byte zero')
            self.pending_byte=peek&255
            need(self.last_pop_id<U32,'POP ID cannot wrap')
            expected=self.last_pop_id+1
            yield write(0x164,expected,'POP ID staging',True)
            yield write(0x080,8,'POP once',True)
            actual=yield read(0x038,'POP ID observation')
            count=yield read(0x030,'POP count observation')
            need(actual==expected and count==self.unread_count-1,'exact POP/count observation')
            self.confirmed_prefix.append(self.pending_byte)
            self.pending_byte=None
            self.last_pop_id=actual
            self.unread_count=count

    def cancel(self):
        need(not self.cancel_consumed,'TRACE CANCEL already consumed')
        self.cancel_consumed=True
        return self._cancel()

    def _cancel(self):
        yield write(0x080,5,'TRACE CANCEL once')
        while True:
            state=yield read(0x018,'cancel state',True)
            status=yield read(0x020,'cancel status')
            if state==0 and status&2 and not status&0x14:
                self.quiescent=True
                return

def decode_collected(raw, companions, repo_root):
    """Use the unchanged strict decoder; mandatory companions are retained whole."""
    need(type(raw) is bytes and len(raw)<=252 and len(companions)==4,'normal one-scan decode bounds')
    root=Path(repo_root)
    need(sha((root/TRACE_REL).read_bytes())==TRACE_SHA,'unchanged trace decoder pin')
    host=load_pinned(root/HOST_REL,HOST_SHA,'host103_unchanged_decoder')
    frames=[];offset=0;views=[]
    for c_raw in companions:
        need(len(raw)-offset>=14,'complete frame header')
        length=raw[offset+4]+14
        need(length<=46 and offset+length<=len(raw),'bounded complete frame')
        frame=raw[offset:offset+length];offset+=length
        c=strict_json(c_raw)
        view=host.decode_transport(frame,binding=c['binding'],profile=c['profile'],
                                   now_qpc_ns=c['evaluation_now_qpc_ns'],enabled=True,repo_root=root)
        need(view['status']=='STOP' and view['core_ran'] is False and view['command'] is None,'strict STOP/no core/action')
        need(view['lossy_decoded_values_match_original'] is True,'actual wire value equals original')
        need(c['current_source_eligible'] is False,'retired source remains unavailable')
        frames.append(frame);views.append(view)
    need(offset==len(raw),'no trailing byte in complete scan')
    return {'kind':KIND,'frames':len(frames),'views':views,'wire_bytes':len(raw),
            'mandatory_companion_bytes':sum(map(len,companions)),
            'total_serialized_bytes':len(raw)+sum(map(len,companions)),
            'current_source_eligible':False,'core_ran':False,'command':None,'status':'STOP'}
