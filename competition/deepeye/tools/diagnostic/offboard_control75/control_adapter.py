"""B75 private, offboard control seam. No planner, transport opening or authority.

H01-H15, DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
Production Root/BOOT/calibration integration is unavailable. Synthetic records
exercise lifecycle consistency only; their JSON is never authentication.
"""
from __future__ import annotations
import copy
import json
import os
import re
from pathlib import Path

U32 = (1 << 32) - 1
U63 = (1 << 63) - 1
U64 = (1 << 64) - 1
AGE_NS = 100_000_000
SYNTHETIC = 'SYNTHETIC_FIXTURE'
MAX_RECORDS = 16
MAX_BINDINGS = 8
MAX_CAPTURES = 16
TEXT_CONTEXT = {'operation_id', 'kernel_boot_id', 'session_id', 'clock_domain_id', 'action_id'}
HASH_CONTEXT = {'request_hash', 'build_manifest_sha256', 'source_record_sha256', 'capture_sha256'}
INT_CONTEXT = {'tag', 'generation', 'trigger_id', 'request_seq', 'capture_seq', 'source_admission_index', 'epoch'}


class Refused(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise Refused(message)


def uint(v, cap=U63):
    need(type(v) is int and 0 <= v <= cap, 'bounded integer required')
    return v


def canonical(value):
    """Bounded plain JSON only; retain exact strings and full integers."""
    count = [0]
    def check(v, depth=0):
        count[0] += 1
        need(depth <= 12 and count[0] <= 4096, 'bounded context required')
        need(type(v) in (dict, list, str, int, bool, type(None)), 'plain data required')
        if type(v) is dict:
            need(len(v) <= 64 and all(type(k) is str for k in v), 'plain keys required')
            for k, x in v.items(): check(k, depth+1); check(x, depth+1)
        elif type(v) is list:
            need(len(v) <= 64, 'bounded list required')
            for x in v: check(x, depth+1)
        elif type(v) is str: need(len(v) <= 1024, 'bounded string required')
        elif type(v) is int: need(-U63 <= v <= U63, 'full integer range required')
    check(value)
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    need(len(raw) <= 32768, 'bounded serialized context required')
    return raw


def durable_record(path, value):
    """Exclusive intent publication, flushed before caller performs a side effect."""
    raw = canonical(value)
    with Path(path).open('xb') as f:
        need(f.write(raw) == len(raw), 'short intent write')
        f.flush()
        os.fsync(f.fileno())


class ControlAdapter:
    """One bounded trusted host fixture; transport handles never authenticate it.

    The default instance has no production issuer. It cannot issue a command.
    Only synthetic_fixture() opens the separately labelled test path. Memory
    stores no replay action. Exclusive intent files fence later processes from
    repeating a send with the same intent path; restart recovery is unavailable.
    """
    def __init__(self):
        self.kind = 'PRODUCTION_UNAVAILABLE'
        self._context = None
        self._identity_words = None
        self._next_handle = 1
        self._next_command = 1
        self.records = {}
        self.bindings = []
        self.now_high = None
        self.semantic_observation = None

    @classmethod
    def synthetic_fixture(cls, context):
        obj = cls()
        obj.kind = SYNTHETIC
        obj._bind(context)
        return obj

    @property
    def context(self):
        return copy.deepcopy(self._context)

    @property
    def identity_words(self):
        return self._identity_words

    def _bind(self, context):
        need(type(context) is dict and set(context) == TEXT_CONTEXT | HASH_CONTEXT | INT_CONTEXT | {'tested_commit'},
             'fixed full original context schema required')
        raw = canonical(context)
        for k in TEXT_CONTEXT:
            need(type(context[k]) is str and 1 <= len(context[k]) <= 1024, 'full original context text required')
        for k in HASH_CONTEXT | {'tested_commit'}:
            need(type(context[k]) is str and re.fullmatch('[0-9a-f]{%d}' % (40 if k == 'tested_commit' else 64), context[k]) is not None,
                 'exact full context hash/commit required')
        for k in INT_CONTEXT: uint(context[k])
        need(len(self.bindings) < MAX_BINDINGS, 'binding capacity exhausted; never evict')
        need(self._next_handle + 12 <= U32, 'handle exhaustion; never wrap')
        words = tuple(range(self._next_handle, self._next_handle+13))
        self._next_handle += 13
        self._context = json.loads(raw)
        self._identity_words = words
        self.bindings.append(dict(context=copy.deepcopy(self.context), identity_words=list(words)))

    def _now(self, now):
        uint(now)
        need(self.now_high is None or now >= self.now_high, 'original QPC regression')
        self.now_high = now

    def ingest_semantic(self, artifact):
        """Retain the B74/source73 structural observation; never run a core."""
        canonical(artifact)
        need(type(artifact) is dict and artifact.get('schema') == 'B74_SEMANTIC_FIXTURE_V1', 'B74 schema required')
        view = artifact.get('semantic_view')
        need(type(view) is dict and view.get('status') == 'STOP' and view.get('core_ran') is False and view.get('command') is None,
             'structural STOP view required')
        need(type(view.get('source_identity')) is dict and type(view.get('points')) is list and 1 <= len(view['points']) <= 32,
             'original source_identity and points required')
        for point in view['points']:
            uint(point['original_acquisition_qpc_ns'])
            if point['original_source_qpc_ns'] is not None: uint(point['original_source_qpc_ns'])
        self.semantic_observation = copy.deepcopy(artifact)
        return dict(status='INPUT_UNAVAILABLE', command=None, core_ran=False,
                    structural_observation=copy.deepcopy(view), authentication='unavailable')

    def production_input(self, **untrusted_claims):
        # No real Root registry/BOOT/calibration/action issuer has been supplied.
        return dict(status='INPUT_UNAVAILABLE', command=None, core_ran=False,
                    missing=['real_BOOT', 'calibration', 'original_Root_action_and_receipt_binding'],
                    data_path_quiescent_is_motion_stop=False)

    def queue(self, *, original_source_qpc_ns, now_qpc_ns, decision):
        need(self.kind == SYNTHETIC, 'production INPUT_UNAVAILABLE')
        need(len(self.records) < MAX_RECORDS, 'record capacity exhausted; never evict')
        self._now(now_qpc_ns)
        source = uint(original_source_qpc_ns)
        need(0 <= now_qpc_ns-source <= AGE_NS, 'original source outside 100ms')
        need(type(decision) is dict and set(decision) == {'yaw_q','pitch_q','profile','speed','ttl_ms'}, 'explicit supplied command required')
        y,p,profile,speed,ttl = (decision[k] for k in ('yaw_q','pitch_q','profile','speed','ttl_ms'))
        need(all(type(x) is int for x in (y,p,profile,speed,ttl)), 'integer command required')
        need(profile in (1,2) and -15000 <= y <= 15000 and -15000 <= p <= 15000 and 0 <= speed <= 20,
             'mapper input domain')
        need(1 <= ttl <= (3000 if profile == 1 else 12000), 'mapper TTL domain')
        need(self._next_command <= U32 and self._next_handle <= U32, 'command/handle exhaustion; never wrap')
        key = self._next_command; self._next_command += 1
        tag = self._next_handle; self._next_handle += 1
        self.records[key] = dict(key=key, context=copy.deepcopy(self.context), identity_words=list(self.identity_words),
            command_id=key, transport_tag=tag, decision=copy.deepcopy(decision), source_qpc_ns=source,
            queued_qpc_ns=now_qpc_ns, state='QUEUED', eligible=True, send_attempted=False,
            digital_accepted=False, applied_tick=None, deadline_tick=None, captures={},
            digital_stop=None, host_receipt_ack=None, original_action_retirement=None,
            stop_required=False, invalidated=False, evidence_kind=self.kind)
        return key

    def hold(self, key):
        r = self.records[key]; need(r['state'] == 'QUEUED', 'only queued work can be held')
        r['state'] = 'HELD'

    def request_registers(self, key):
        r = self.records[key]; d = r['decision']
        need(r['eligible'] and not r['send_attempted'], 'old/sent request cannot be replayed')
        stage = [d['yaw_q'] & 65535, d['pitch_q'] & 65535, d['profile'], d['speed'],
                 d['ttl_ms'], r['command_id'], r['transport_tag']]
        return [(0x200+4*i, value) for i,value in enumerate(stage)] + [(0x00c, 2)]

    def begin_registers(self):
        need(self.kind == SYNTHETIC, 'production INPUT_UNAVAILABLE')
        return [(0x100+4*i, v) for i,v in enumerate(self.identity_words)] + [(0x00c, 1)]

    def send_once(self, key, *, now_qpc_ns, intent_path, send):
        r = self.records[key]
        self._now(now_qpc_ns)
        need(r['state'] in ('QUEUED','HELD') and r['eligible'] and not r['send_attempted'], 'no automatic replay')
        need(not any(old['invalidated'] and old['stop_required'] for old in self.records.values()),
             'STOP_REQUIRED for original invalidated side effects; no new downstream send')
        if not 0 <= now_qpc_ns-r['source_qpc_ns'] <= AGE_NS:
            r.update(state='CANCELLED_STALE', eligible=False)
            raise Refused('original source expired before send')
        regs = self.request_registers(key)
        # Sticky even if intent I/O or the callback fails. No inferred rollback.
        r.update(state='SEND_UNKNOWN', send_attempted=True, stop_required=True)
        durable_record(intent_path, dict(evidence_kind=self.kind, state='SEND_UNKNOWN', record=r,
                                        registers=[list(pair) for pair in regs]))
        send(regs)  # A return is transport information, not digital acceptance.
        return None

    def _exact(self, key, context, words, command_id, tag):
        r = self.records[key]
        need(type(words) in (tuple,list) and len(words) == 13 and
             all(type(v) is int and 0 < v <= U32 for v in words), '13 strictly typed issued uint32 handles required')
        need(canonical(context) == canonical(r['context']) and list(words) == r['identity_words'] and
             type(command_id) is int and 0 < command_id <= U32 and command_id == r['command_id'] and
             type(tag) is int and 0 < tag <= U32 and tag == r['transport_tag'],
             'exact original identity/issued handle association required')
        return r

    def digital_fact(self, key, *, context, identity_words, command_id, transport_tag, fact, **data):
        r = self._exact(key, context, identity_words, command_id, transport_tag)
        need(r['send_attempted'], 'no downstream fact before a send attempt')
        if fact == 'STOP':
            need(set(data)=={'terminal_status','pwm','fault','tick'}, 'exact terminal fields required')
            uint(data['terminal_status'],127);uint(data['pwm'],7);uint(data['fault'],255);uint(data['tick'],U64)
            need(data['terminal_status'] & 2 and not data['terminal_status'] & 0x7c and
                 data['pwm'] == 0 and data['fault'] in (2,6), 'exact digital STOP/expiry evidence required')
            if r['digital_stop'] is not None: need(r['digital_stop'] == data, 'changed terminal evidence')
            r['digital_stop'] = copy.deepcopy(data)
            r['eligible'] = False; r['state'] = 'DIGITAL_STOPPED'
            return
        need(r['eligible'], 'new BOOT/epoch/cancel invalidates downstream eligibility')
        if fact == 'ACCEPTED':
            need(not data, 'acceptance has no substituted host timestamp')
            r['digital_accepted'] = True
            if r['applied_tick'] is None: r['state'] = 'DIGITAL_ACCEPTED'
        elif fact == 'APPLIED':
            need(set(data)=={'applied_tick','deadline_tick'}, 'actual digital edge fields only')
            need(r['digital_accepted'], 'digital acceptance required')
            a,d = uint(data['applied_tick'],U64), uint(data['deadline_tick'],U64)
            need(d == a+r['decision']['ttl_ms']*50000, 'TTL must originate at actual applying edge')
            need(r['applied_tick'] in (None,a) and r['deadline_tick'] in (None,d), 'duplicate cannot renew applying-edge TTL')
            if r['applied_tick'] is None:
                r.update(applied_tick=a, deadline_tick=d, state='DIGITAL_APPLIED')
        elif fact == 'CAPTURED':
            need(set(data)=={'words'}, 'actual capture bank only')
            need(r['applied_tick'] is not None, 'actual application required')
            words = data['words']; need(type(words) is list and len(words) == 32, '32-word latched capture required')
            for v in words: uint(v,U32)
            d = r['decision']; u64=lambda i: words[i] | (words[i+1] << 32)
            need(words[1:3] == [r['command_id'],r['transport_tag']] and
                 words[3] == (d['speed'] << 8)|d['profile'] and
                 words[4] == ((d['pitch_q'] & 65535) << 16)|(d['yaw_q'] & 65535) and words[5] == d['ttl_ms'] and
                 words[30:] == [r['identity_words'][12],0x47303550], 'capture exact command/context required')
            need(u64(6) == r['applied_tick'] and u64(8) == r['deadline_tick'] and
                 r['applied_tick']+2_000_000 <= u64(10) < r['deadline_tick'], 'capture original time/TTL required')
            expected = [125000+8*d['yaw_q'],125000+8*d['pitch_q'],25000+500*d['speed']]
            need(words[12:15] == [1_000_000]*3 and all(abs(x-y)<=1 for x,y in zip(words[15:18],expected)), 'actual selected 50MHz mapping')
            need(all(u64(24+2*i)-u64(18+2*i) == 1_000_000 for i in range(3)), 'complete capture witnesses required')
            seq=words[0]; need(seq>0, 'nonzero capture sequence')
            old = r['captures'].get(str(seq))
            need(old is None or old == words, 'repeated result changed')
            need(old is not None or not r['captures'] or seq > max(map(int,r['captures'])), 'stale capture sequence')
            need(old is not None or len(r['captures']) < MAX_CAPTURES, 'capture capacity exhausted; never evict')
            r['captures'][str(seq)] = list(words); r['state'] = 'DIGITAL_CAPTURED'
        else: raise Refused('unknown digital fact')

    def cancel(self, key, reason):
        r=self.records[key]; need(type(reason) is str and 1 <= len(reason) <= 1024, 'bounded cancel reason required')
        need(r['original_action_retirement'] is None, 'already retired original action')
        r['eligible']=False; r['state']='STOP_REQUIRED' if r['send_attempted'] else 'CANCELLED_UNSENT'
        r['stop_required']=r['send_attempted']; r['invalidated']=True; r['cancel_reason']=reason

    def new_epoch(self, context):
        need(self.kind == SYNTHETIC, 'production INPUT_UNAVAILABLE')
        need(canonical(context) != canonical(self.context), 'actual new full context required')
        # Validate/capacity-check the new binding before invalidating old work.
        trial=ControlAdapter(); trial._bind(context)
        need(len(self.bindings) < MAX_BINDINGS and self._next_handle+12 <= U32, 'binding/handle capacity exhausted')
        for key,r in self.records.items():
            if r['eligible']: self.cancel(key,'new BOOT/epoch')
        self._bind(context)

    def original_receipt(self, key, record):
        r=self.records[key]
        need(type(record) is dict and set(record) == {'kind','evidence_kind','context','command_id','transport_tag','receipt_id'}, 'original receipt fields required')
        need(record['kind']=='HOST_RECEIPT_ACK' and record['evidence_kind']==self.kind==SYNTHETIC and
             type(record['receipt_id']) is str and record['receipt_id'], 'separate original host receipt required')
        self._exact(key,record['context'],r['identity_words'],record['command_id'],record['transport_tag'])
        need(r['send_attempted'], 'receipt before send')
        need(r['host_receipt_ack'] is None or r['host_receipt_ack']==record, 'changed original receipt')
        r['host_receipt_ack']=copy.deepcopy(record)

    def retire_original_action(self, key, record):
        r=self.records[key]
        need(type(record) is dict and set(record)=={'kind','evidence_kind','context','command_id','transport_tag','receipt_id','action_id','world_motion_stopped'}, 'original action fields required')
        need(record['kind']=='ORIGINAL_ACTION_RETIRED' and record['evidence_kind']==self.kind==SYNTHETIC and
             record['world_motion_stopped'] is True and type(record['action_id']) is str and record['action_id'], 'explicit original action retirement required')
        self._exact(key,record['context'],r['identity_words'],record['command_id'],record['transport_tag'])
        need(r['digital_stop'] is not None and r['host_receipt_ack'] is not None and
             record['receipt_id']==r['host_receipt_ack']['receipt_id'], 'digital STOP and exact original receipt still required')
        need(r['original_action_retirement'] is None or r['original_action_retirement']==record, 'changed original action retirement')
        r['original_action_retirement']=copy.deepcopy(record); r['stop_required']=False; r['state']='ORIGINAL_ACTION_RETIRED'

    def snapshot(self):
        return copy.deepcopy(dict(evidence_kind=self.kind, production=self.production_input(), bindings=self.bindings,
            records=self.records, structural_observation=self.semantic_observation,
            motion_authorized=False, actual_board='not_run', original_Root_action_records='unavailable'))
