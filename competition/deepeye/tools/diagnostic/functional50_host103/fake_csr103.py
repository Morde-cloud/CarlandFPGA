"""Explicit software fake only. Never imports or accepts a physical adapter."""
from collections import deque
from host103 import KIND, U32, TraceSequence, DEFAULT_LIMITS, Refused, need, canonical, decode_collected
from evidence103 import Evidence

class FakeUnknown(RuntimeError):
    pass

class FakeCSR:
    """Register-behavior control double; canned saved104 bytes, no RTL claim."""
    def __init__(self,plan,frames,scenario='normal'):
        need(scenario in ('normal','partial_cancel','overflow','unknown_pop','time_pop',
                         'unknown_arm','dirty_prearm','wrong_identity','wrong_build'),'explicit fake scenario')
        self.plan=plan;self.frames=list(frames);self.scenario=scenario
        self.stage={};self.fresh=set();self.state=0;self.fault=0
        self.push=0;self.assoc=0;self.tag=0;self.result_id=0;self.pop_id=0
        self.rx=0;self.rx_before=0;self.rx_end=0;self.result_bytes=0
        self.fifo=deque();self.calls=[];self.commands=[];self.now=0.0
        self.accessible=True;self.unknown_injected=False;self.aborted=0
        if scenario=='dirty_prearm':self.fifo.append(0xaa)

    def read32(self,offset):
        self.calls.append(('read',offset,None));self.now+=.00001
        constants={0:0x54353046,4:1,8:4,12:50000000,16:1000000,20:4096}
        if offset in constants:
            return constants[offset]^1 if self.scenario=='wrong_identity' and offset==0 else constants[offset]
        if 0x060<=offset<=0x06c:
            word=(int(self.plan['build_id'],16)>>(8*(offset-0x060)))&U32
            return word^1 if self.scenario=='wrong_build' and offset==0x060 else word
        status=2|(0x10 if self.state==7 else 0)|(0x20 if not self.fifo else 0)|(0x40 if len(self.fifo)==4096 else 0)|(0x80 if self.state==9 else 0)
        values={0x018:self.state,0x01c:self.fault,0x020:status,0x024:self.push,0x028:self.assoc,
                0x02c:self.tag,0x030:len(self.fifo),0x034:self.rx,0x038:self.pop_id,0x03c:0,
                0x040:self.result_id,0x044:0,0x048:self.result_bytes,0x04c:0,
                0x050:self.rx_before,0x054:self.aborted,0x078:int(self.aborted>0),0x07c:self.rx_end,
                0x070:(0x100|self.fifo[0]) if self.fifo else 0}
        need(offset in values,'unknown fake read')
        return values[offset]

    def write32(self,offset,value):
        self.calls.append(('write',offset,value));self.now+=.00001
        if offset!=0x080:
            need(offset in (0x100,0x104,0x108,0x110,0x114,0x118,0x11c,0x120,0x130,0x134,0x138,0x13c,
                            0x140,0x144,0x148,0x14c,0x150,0x154,0x160,0x164),'fake staging offset')
            self.stage[offset]=value;self.fresh.add(offset);return
        self.commands.append(value)
        if value==1:
            need(self.state==0 and not self.fifo and self.fault==0,'fake ARM eligibility')
            self._consume((0x100,0x104,0x108))
            need(self.stage[0x100]>self.tag,'fake ARM tag')
            self.tag=self.stage[0x100];self.state=3
            if self.scenario=='unknown_arm':
                raise FakeUnknown('software-injected ARM effect occurred; response lost')
        elif value==2:
            need(self.state==3 and self.push<4,'fake PUSH state')
            self._consume((0x110,0x114,0x118,0x11c,0x120))
            lane=self.plan['lanes'][self.push];acq=lane['acquisition_qpc_ns']
            expected=(self.push,lane['count'] if lane['count'] is not None else 0,acq&U32,acq>>32,lane['quality'])
            need(tuple(self.stage[k] for k in (0x110,0x114,0x118,0x11c,0x120))==expected,'fake exact PUSH words')
            self.push+=1;self.state=4 if self.push==4 else 3
        elif value==3:
            need(self.state==4 and self.assoc<4,'fake BIND state')
            self._consume(tuple(0x130+4*i for i in range(10)))
            lane=self.plan['lanes'][self.assoc];source=lane['source_qpc_ns'] or 0
            expected=(lane['session'],lane['index'],lane['acquisition_tick_us'],lane['acquisition_remainder_ns'],source&U32,
                      source>>32,lane['source_tick_us'] or 0,lane['source_remainder_ns'] or 0,lane['view'],lane['frame_seq'])
            need(tuple(self.stage[0x130+4*i] for i in range(10))==expected,'fake exact BIND words')
            packet=self.frames[self.assoc];self.rx_before=self.rx
            if self.scenario=='partial_cancel' and self.assoc==0:
                self.fifo.extend(packet[:1]);self.rx+=1;self.state=0;self.aborted+=1;return
            if self.scenario=='overflow' and self.assoc==0:
                self.fifo.extend(bytes(4096));self.rx+=4096;self.fault=2;self.state=0;return
            self.fifo.extend(packet);self.rx+=len(packet);self.rx_end=self.rx
            self.result_bytes=len(packet);self.result_id+=1;self.state=7
        elif value==4:
            need(self.state==7,'fake ACK state');self._consume((0x160,))
            need(self.stage[0x160]==self.result_id,'fake exact ACK')
            self.assoc+=1;self.state=9 if self.assoc==4 else 4
        elif value==5:
            self.state=0;self.fresh.clear()
        elif value==8:
            need(self.state in (0,9) and self.fifo,'fake POP eligibility');self._consume((0x164,))
            need(self.pop_id<U32 and self.stage[0x164]==self.pop_id+1,'fake POP exact ID')
            self.fifo.popleft();self.pop_id+=1
            if self.scenario=='unknown_pop' and not self.unknown_injected:
                self.unknown_injected=True;raise FakeUnknown('software-injected POP effect occurred; response lost')
            if self.scenario=='time_pop' and not self.unknown_injected:
                self.unknown_injected=True;self.now+=11.0
        else:
            raise Refused('fake forbids clear/reset/G05 commands')

    def _consume(self,offsets):
        need(set(offsets)<=self.fresh,'fake fresh staging')
        self.fresh.difference_update(offsets)

class FakeExecution:
    def __init__(self,plan,frames,companions,output,scenario='normal',limits=None):
        self.bus=FakeCSR(plan,frames,scenario)
        self.sequence=TraceSequence(plan)
        self.evidence=Evidence(output,plan,limits)
        self.limits=self.evidence.limits;self.companions=list(companions)
        self.counts={'csr':0,'polls':0,'writes':0,'pops':0,'pop_stages':0,'cleanup_polls':0}
        self.work_start=self.bus.now;self.cleanup_start=None;self.errors=[];self.cleanup='NOT_ATTEMPTED'
        self.arm_effect_attempted=False
        self.decode=None

    def drive(self,generator,phase):
        need(type(self.bus) is FakeCSR,'only exact SOFTWARE_FAKE_CSR executor')
        returned=None
        while True:
            try:intent=generator.send(returned)
            except StopIteration:return
            is_pop=intent['kind']=='write' and intent['pop_related']
            is_pop_cmd=is_pop and intent['offset']==0x080
            is_pop_stage=is_pop and intent['offset']==0x164
            deadline=self.work_start+self.limits['work_seconds'] if phase=='work' else self.cleanup_start+self.limits['cleanup_seconds']
            need(self.bus.now<deadline,phase+' time budget')
            need(self.counts['csr']<self.limits['csr'],'CSR attempt budget')
            if intent['poll']:
                key='polls' if phase=='work' else 'cleanup_polls'
                need(self.counts[key]<self.limits[key],'poll budget')
            if is_pop_cmd:need(self.counts['pops']<self.limits['pops'],'POP command budget')
            if is_pop_stage:need(self.counts['pop_stages']<self.limits['pops'],'POP staging budget')
            if intent['kind']=='write' and not is_pop:need(self.counts['writes']<self.limits['writes'],'write budget')
            token=self.evidence.before(phase,intent,self.counts)
            self.counts['csr']+=1
            if intent['poll']:self.counts['polls' if phase=='work' else 'cleanup_polls']+=1
            if is_pop_cmd:self.counts['pops']+=1
            if is_pop_stage:self.counts['pop_stages']+=1
            if intent['kind']=='write' and not is_pop:self.counts['writes']+=1
            try:
                if intent['kind']=='write' and intent['offset']==0x080 and intent['value']==1:
                    # Set only after budgets and the intent file write succeed,
                    # immediately before our own ARM attempt. This software fake
                    # does not claim crash-proof physical-device journaling.
                    self.arm_effect_attempted=True
                returned=self.bus.read32(intent['offset']) if intent['kind']=='read' else self.bus.write32(intent['offset'],intent['value'])
            except Exception as exc:
                self.sequence.unknown_effects=True
                self.evidence.after(phase,token,error=type(exc).__name__+': '+str(exc)[:512])
                raise
            self.evidence.after(phase,token,value=returned)

    def start(self):
        generator=self.sequence.start()
        self.evidence.emit('work',{'event':'START_CONSUMED','kind':KIND})
        self.drive(generator,'work')

    def collect(self,phase='work'):
        generator=self.sequence.collect()
        self.evidence.emit(phase,{'event':'COLLECT_CONSUMED','kind':KIND})
        self.drive(generator,phase)

    def cleanup_once(self):
        if not self.arm_effect_attempted:
            self.cleanup='NOT_OWNED_PREARM_NO_WRITES'
            return
        if self.sequence.cancel_consumed:return
        self.cleanup_start=self.bus.now
        try:
            need(self.bus.accessible,'fake transport inaccessible')
            generator=self.sequence.cancel()
            self.evidence.emit('cleanup',{'event':'TRACE_CANCEL_CONSUMED','kind':KIND})
            self.drive(generator,'cleanup')
            self.cleanup='OBSERVED_QUIESCENT_SOFTWARE_FAKE'
        except Exception as exc:
            self.cleanup='UNKNOWN_OR_FAILED'
            self.errors.append('cleanup: '+str(exc)[:512])

    def run(self,repo_root):
        try:
            self.start()
            self.collect()
            self.decode=decode_collected(bytes(self.sequence.confirmed_prefix),self.companions,repo_root)
        except Exception as exc:
            self.errors.append(type(exc).__name__+': '+str(exc)[:512])
            if self.sequence.pending_byte is not None:self.sequence.unknown_effects=True
        finally:
            self.cleanup_once()
        # A failure before collect may drain once only after successful CANCEL
        # and actual fake quiescence. Never restart an exhausted/ambiguous drain.
        if self.errors and self.arm_effect_attempted and not self.sequence.collect_consumed and self.cleanup=='OBSERVED_QUIESCENT_SOFTWARE_FAKE':
            try:self.collect('cleanup')
            except Exception as exc:
                self.errors.append('partial drain: '+str(exc)[:512])
                if self.sequence.pending_byte is not None:self.sequence.unknown_effects=True
        prefix=bytes(self.sequence.confirmed_prefix)
        self.evidence.file('final','collected-prefix.bin',prefix,4096)
        for i,raw in enumerate(self.companions):
            self.evidence.file('final','companion%03d.json'%i,raw,65536)
        result={'kind':KIND,'status':'STOP','command':None,'core_ran':False,'current_source_eligible':False,
                'errors':self.errors,'cleanup':self.cleanup,'decoded':self.decode,'start_consumed':self.sequence.start_consumed,
                'collect_consumed':self.sequence.collect_consumed,'cancel_consumed':self.sequence.cancel_consumed,
                'arm_effect_attempted':self.arm_effect_attempted,
                'confirmed_prefix_bytes':len(prefix),'pending_observed_byte':self.sequence.pending_byte,
                'last_confirmed_pop_id':self.sequence.last_pop_id,'last_observed_unread_count':self.sequence.unread_count,
                'unknown_effects':self.sequence.unknown_effects,'counters':self.counts,
                'retained_wire_prefix_bytes':len(prefix),'mandatory_companion_bytes':sum(map(len,self.companions)),
                'serialized_prefix_and_mandatory_companion_bytes':len(prefix)+sum(map(len,self.companions)),
                'physical_result':False,'limits':self.limits,'parent15s_is_not_hung_MMIO_bound':True}
        return self.evidence.finalize(result)
