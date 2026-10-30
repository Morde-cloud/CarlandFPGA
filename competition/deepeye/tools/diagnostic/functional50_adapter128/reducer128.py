"""Bounded TRACE-relative intent/reducer; A alone persists and executes effects."""
import copy
from adapter128 import Plan, Refused, need, U32, AUTHORITY, validated_plan

LIMITS = {'csr':65536, 'polls':2048, 'writes':128, 'pops':4096, 'pop_stages':4096,
          'cleanup_polls':256, 'work_ns':10000000000, 'cleanup_ns':2000000000,
          'work_evidence':6291456, 'cleanup_evidence':1048576, 'final_evidence':1048576}

def read(off, label, poll=False):
    return {'kind':'read','offset':off,'value':None,'label':label,'poll':poll}

def write(off, value, label):
    need(type(value) is int and 0 <= value <= U32, 'WRITE_UINT32')
    return {'kind':'write','offset':off,'value':value,'label':label,'poll':False}

class Reducer:
    """One pending intent at a time; each observation consumes it exactly once.

    Yielding an intent is not proof that it was attempted. A must reserve and
    persist intent+outcome space before effects, then submit its original outcome.
    All offsets are relative to the HWH-selected TRACE window, never G05.
    """
    def __init__(self, plan, *, limits=None):
        self.plan = validated_plan(plan)
        need(limits is None or type(limits) is dict, 'PLAIN_LIMITS_REQUIRED')
        self.limits = dict(LIMITS if limits is None else limits)
        need(set(self.limits) == set(LIMITS), 'LIMIT_KEYS')
        need(all(type(v) is int and 0 < v <= LIMITS[k] for k,v in self.limits.items()), 'LIMIT_CAN_ONLY_DECREASE')
        # Finalization is an independently reserved partition, not spendable
        # work space. Complete original bodies are charged to work before ARM.
        need(self.limits['final_evidence'] == LIMITS['final_evidence'], 'FINAL_RESERVE_FIXED')
        self.counts = {k:0 for k in ('csr','polls','writes','pops','pop_stages','cleanup_polls')}
        original = self.plan.original
        self.evidence_reserved = {'work': len(original.request)+len(original.source)+sum(map(len,original.companions))+4096,
                                  'cleanup':0, 'final':1048576}
        need(self.evidence_reserved['work'] <= self.limits['work_evidence'], 'INPUT_EVIDENCE_RESERVATION')
        self.operation_id = self.plan._lineage['operation_id']
        self.pending = None; self.call_id = 0; self.events = []
        self.phase = None; self.generator = None; self.phase_elapsed_ns = {'work':0,'cleanup':0}
        self.start_consumed = self.collect_consumed = self.cancel_consumed = False
        self.arm_attempt_owned = False; self.unknown_effects = False
        self.completed = False; self.quiescent = False; self.failed = False
        self.errors = []; self.results = []; self.prefix = bytearray()
        self.pending_peek = None; self.last_pop_id = None; self.unread_count = None

    def begin(self):
        need(not self.start_consumed and self.generator is None and self.pending is None, 'START_CONSUMED')
        self.start_consumed = True; self.phase = 'work'; self.generator = self._scan()

    def begin_collect(self):
        need(self.start_consumed and self.arm_attempt_owned and not self.collect_consumed and self.generator is None and self.pending is None, 'COLLECTION_UNAVAILABLE_OR_CONSUMED')
        need(self.completed or self.quiescent, 'COLLECTION_REQUIRES_OBSERVED_QUIESCENCE')
        self.collect_consumed = True
        self.phase = 'work' if self.completed and not self.failed else 'cleanup'
        self.generator = self._collect()

    def begin_cleanup(self):
        need(self.pending is None and self.generator is None, 'OUTSTANDING_OPERATION_MUST_BE_RESOLVED')
        need(self.arm_attempt_owned and not self.cancel_consumed, 'NO_OWNED_ARM_OR_CANCEL_CONSUMED')
        self.cancel_consumed = True; self.phase = 'cleanup'; self.generator = self._cancel()

    def _fail(self, reason):
        self.failed = True; self.errors.append(reason)
        if self.pending_peek is not None:
            self.unknown_effects = True
        self.generator = None

    def advance(self, observation=None, *, phase_elapsed_ns):
        """Return next intent or None. No MMIO/callback/time reading occurs.

        phase_elapsed_ns is A's nondecreasing elapsed observation for this
        partition. It bounds scheduling, not a hung in-flight MMIO operation.
        Outcomes are retained even if the reported deadline has expired.
        """
        need(self.phase is not None, 'BEGIN_REQUIRED')
        need(type(phase_elapsed_ns) is int and phase_elapsed_ns >= self.phase_elapsed_ns[self.phase], 'MONOTONIC_ELAPSED_REQUIRED')
        self.phase_elapsed_ns[self.phase] = phase_elapsed_ns
        value = None
        if self.pending is not None:
            intent = self.pending
            need(type(observation) is dict and set(observation) == {'operation_id','call_id','status','value','error_code'}, 'OBSERVATION_FIELDS')
            need(type(observation['operation_id']) is str and type(observation['call_id']) is int and
                 observation['operation_id'] == self.operation_id and observation['call_id'] == intent['call_id'], 'OBSERVATION_IDENTITY')
            status = observation['status']
            need(type(status) is str and status in ('confirmed_read','confirmed_write','error','unknown','not_attempted'), 'OBSERVATION_STATUS')
            need(observation['error_code'] is None or (type(observation['error_code']) is str and len(observation['error_code']) <= 96), 'BOUNDED_ERROR_CODE')
            if status == 'confirmed_read':
                need(intent['kind'] == 'read' and type(observation['value']) is int and 0 <= observation['value'] <= U32 and observation['error_code'] is None, 'CONFIRMED_READ_FIELDS')
            elif status == 'confirmed_write':
                need(intent['kind'] == 'write' and observation['value'] is None and observation['error_code'] is None, 'CONFIRMED_WRITE_FIELDS')
            else:
                need(observation['value'] is None, 'FAILURE_VALUE_MUST_BE_NULL')
            self.events.append({'observation':copy.deepcopy(observation)})
            self.pending = None
            if intent['kind'] == 'write' and intent['offset'] == 0x080 and intent['value'] == 1 and status != 'not_attempted':
                self.arm_attempt_owned = True
                self.quiescent = False
            if status in ('unknown','error','not_attempted'):
                if status == 'unknown' or (status == 'error' and intent['kind'] == 'write'):
                    self.unknown_effects = True
                self._fail('OPERATION_'+status.upper())
                return None
            value = observation['value']
        else:
            need(observation is None, 'NO_PENDING_OBSERVATION')
        if self.generator is None:
            return None
        try:
            intent = self.generator.send(value)
            need(self.phase_elapsed_ns[self.phase] < self.limits[self.phase+'_ns'], 'PHASE_TIME_BUDGET')
            changes = {'csr':1}
            if intent['poll']:
                changes['polls' if self.phase == 'work' else 'cleanup_polls'] = 1
            if intent['kind'] == 'write':
                if intent['offset'] == 0x164:
                    changes['pop_stages'] = 1
                elif intent['offset'] == 0x080 and intent['value'] == 8:
                    changes['pops'] = 1
                else:
                    changes['writes'] = 1
            for key, delta in changes.items():
                need(self.counts[key]+delta <= self.limits[key], 'LOGICAL_'+key.upper()+'_BUDGET')
            need(self.evidence_reserved[self.phase]+2048 <= self.limits[self.phase+'_evidence'], 'LOGICAL_EVIDENCE_BUDGET')
            self.evidence_reserved[self.phase] += 2048
            for key, delta in changes.items():
                self.counts[key] += delta
            self.call_id += 1
            intent.update({'operation_id':self.operation_id,'call_id':self.call_id,
                           'window':'TRACE_HWH_RELATIVE','phase':self.phase,
                           'reserve_and_persist_before_effect_bytes':2048,
                           'phase_deadline_ns':self.limits[self.phase+'_ns']})
            self.pending = copy.deepcopy(intent)
            self.events.append({'intent':copy.deepcopy(intent)})
            return intent
        except StopIteration:
            self.generator = None
            return None
        except Refused as exc:
            self._fail(str(exc))
            return None

    def snapshot(self):
        return {'authority_not_evaluated':AUTHORITY,'operation_id':self.operation_id,
                'original':self.plan.original,'build_binding':copy.deepcopy(self.plan._build),
                'counters':dict(self.counts),'evidence_reserved':dict(self.evidence_reserved),
                'start_consumed':self.start_consumed,'collect_consumed':self.collect_consumed,
                'cancel_consumed':self.cancel_consumed,'arm_attempt_owned':self.arm_attempt_owned,
                'unknown_effects':self.unknown_effects,'completed':self.completed,'quiescent':self.quiescent,
                'failed':self.failed,'errors':list(self.errors),'results':copy.deepcopy(self.results),
                'confirmed_wire_prefix':bytes(self.prefix),'pending_peek':self.pending_peek,
                'last_confirmed_pop_id':self.last_pop_id,'last_observed_unread_count':self.unread_count,
                'outstanding_intent':copy.deepcopy(self.pending),'events':copy.deepcopy(self.events),
                'time_observations':'CALLER_REPORTED_NOT_HUNG_MMIO_PROOF'}

    def _quiet(self):
        state = yield read(0x018,'state')
        status = yield read(0x020,'status')
        need(state in (0,9) and status & 2 and not status & 0x14, 'NOT_QUIESCENT_CANCEL_OR_COMPLETE')
        self.quiescent = True
        return state

    def _wait(self, target):
        # advance reserves finite CSR/poll/evidence budgets for every iteration.
        while True:
            fault = yield read(0x01c,'fault')
            need(fault == 0, 'STICKY_FAULT')
            state = yield read(0x018,'progress',True)
            if state == target:
                return
            need(state in range(1,10), 'UNEXPECTED_CANCEL_OR_STATE')

    def _scan(self):
        for off, val in ((0,0x54353046),(4,1),(8,4),(12,50000000),(16,1000000),(20,4096)):
            observed = yield read(off,'identity')
            need(observed == val, 'TRACE_IDENTITY')
        build = int(self.plan._lineage['build_id_hex128'],16)
        for i in range(4):
            observed = yield read(0x060+4*i,'BUILD_ID')
            need(observed == ((build>>(32*i))&U32), 'TRACE_BUILD_ID')
        state = yield from self._quiet()
        need(state == 0, 'INITIAL_STATE_NOT_CANCEL')
        fault = yield read(0x01c,'initial fault')
        count = yield read(0x030,'initial FIFO count')
        empty = yield read(0x020,'initial empty flag')
        prior_tag = yield read(0x02c,'prior ARM tag')
        prior_result = yield read(0x040,'prior result ID')
        prior_pop = yield read(0x038,'prior POP ID')
        prior_rx = yield read(0x034,'prior RX total')
        need(fault == 0 and count == 0 and empty & 0x20, 'DIRTY_PREARM')
        need(self.plan._lineage['tag'] > prior_tag, 'ARM_TAG_WRAP_OR_REUSE')
        need(prior_result <= U32-4 and prior_pop <= U32-252 and prior_rx <= U32-252, 'PREARM_COUNTER_HEADROOM')
        origin = self.plan._scan['origin_qpc_ns']
        for off,val in ((0x100,self.plan._lineage['tag']),(0x104,origin&U32),(0x108,origin>>32)):
            yield write(off,val,'ARM staging')
        yield write(0x080,1,'ARM')
        self.quiescent = False
        yield from self._wait(3)
        accepted = yield read(0x02c,'accepted tag')
        need(accepted == self.plan._lineage['tag'], 'ARM_TAG_READBACK')
        for lane in self.plan._scan['lanes']:
            acq = lane['acquisition_qpc_ns']
            for off,val in ((0x110,lane['channel']),(0x114,lane['raw_sample_uint16'] if lane['raw_sample_uint16'] is not None else 0),
                            (0x118,acq&U32),(0x11c,acq>>32),(0x120,lane['staged_quality_uint4'])):
                yield write(off,val,'PUSH staging')
            yield write(0x080,2,'PUSH')
            next_lane = yield read(0x024,'next PUSH')
            need(next_lane == lane['channel']+1, 'PUSH_READBACK')
        yield from self._wait(4)
        previous_id = prior_result; previous_end = prior_rx
        for lane in self.plan._scan['lanes']:
            source = lane['source_qpc_ns'] or 0
            values = (lane['session'],lane['index'],lane['acquisition_tick_us'],lane['acquisition_remainder_ns'],
                      source&U32,source>>32,lane['source_tick_us'] or 0,lane['source_remainder_ns'] or 0,lane['view'],lane['frame_seq'])
            for i,val in enumerate(values):
                yield write(0x130+4*i,val,'BIND staging')
            yield write(0x080,3,'BIND')
            yield from self._wait(7)
            row = {}
            for key,off in (('id',0x040),('error',0x044),('bytes',0x048),('refusal',0x04c),('rx_before',0x050),('rx_end',0x07c),('status',0x020)):
                row[key] = yield read(off,'result '+key)
            row['channel'] = lane['channel']; row['frame_seq'] = lane['frame_seq']
            self.results.append(row)
            need(row['id'] == previous_id+1 and row['error'] == 0 and row['refusal'] == 0 and
                 0 < row['bytes'] <= 63, 'RESULT_ID_ERROR_LENGTH_REFUSAL')
            need(row['rx_before'] == previous_end and row['rx_end'] == row['rx_before']+row['bytes'] and row['rx_end'] <= U32, 'RESULT_RX_CONTINUITY')
            need(row['status'] & 0x10 and not row['status'] & 4, 'RESULT_VISIBLE_RX_IDLE')
            previous_id = row['id']; previous_end = row['rx_end']
            yield write(0x160,row['id'],'ACK staging')
            yield write(0x080,4,'ACK')
            yield from self._wait(9 if lane['channel']==3 else 4)
            next_assoc = yield read(0x028,'next association')
            need(next_assoc == lane['channel']+1, 'ACK_READBACK')
        need(sum(r['bytes'] for r in self.results) <= 252, 'WIRE_BOUND')
        self.completed = True

    def _collect(self):
        yield from self._quiet()
        self.unread_count = yield read(0x030,'FIFO count')
        need(self.unread_count <= 4096, 'RETAINED_BOUND')
        if self.completed and not self.failed:
            need(self.unread_count == sum(r['bytes'] for r in self.results) and self.unread_count <= 252, 'COMPLETE_FIFO_COUNT')
        self.last_pop_id = yield read(0x038,'initial POP ID')
        need(self.last_pop_id <= U32-self.unread_count, 'POP_WRAP')
        for _ in range(self.unread_count):
            peek = yield read(0x070,'peek')
            need(0x100 <= peek <= 0x1ff, 'PEEK_VALID')
            self.pending_peek = peek&255
            expected = self.last_pop_id+1
            yield write(0x164,expected,'POP staging')
            yield write(0x080,8,'POP')
            actual = yield read(0x038,'POP ID')
            count = yield read(0x030,'POP count')
            need(actual == expected and count == self.unread_count-1, 'POP_READBACK')
            self.prefix.append(self.pending_peek); self.pending_peek = None
            self.last_pop_id = actual; self.unread_count = count

    def _cancel(self):
        yield write(0x080,5,'CANCEL')
        while True:
            state = yield read(0x018,'cancel state',True)
            status = yield read(0x020,'cancel status')
            if state == 0 and status & 2 and not status & 0x14:
                self.quiescent = True
                return
