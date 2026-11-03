"""Independent synthetic Root791 controls; no transport or board execution.

DEEPEYE-IMPLEMENTATION-20261014/v1 / B-CONTINUOUS-WIRE-v2-INDEPENDENT-CONTROLS-221a.
H01-H15 revision2, pinned817b355887c14cfa9c5d830c8589684f994af082,
requirements2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d.
Capture fixtures are invented unit stimuli, never measured hardware evidence.
Sense fixtures exercise metadata envelopes, not independent E4 decoding.
"""
import copy
from dataclasses import FrozenInstanceError
import json
import threading
import unittest

from . import Binding, ContinuousWire, ProtocolError

ABI = 'DEEPEYE-LIVE-BOARD-791-v1'
SCOPE = '2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d'
BUILD = 'dc4e89ccf3db18c4f9871575efc399ba'
U32 = 0xffffffff


def line(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False).encode() + b'\n'


def binding(build=BUILD):
    return Binding('unit-boot-221', build, 'a' * 64, 73)


def initialized(**kwargs):
    b = binding(kwargs.pop('build', BUILD))
    w = ContinuousWire(b, **kwargs)
    t = w.begin('init', now_ns=0)
    w.mark_sent(t, now_ns=1)
    w.finish(t, line(init_reply(b)), now_ns=2)
    return w


def init_reply(b):
    return dict(abi=ABI, op='init', status='COMPLETE', scope_sha256=SCOPE,
                boot_id=b.boot_id, build_id=b.build_id, request_hash=b.request_hash,
                initial_speed_code=2, speed_applied=False, formal_acceptance='not_run')


def apply_fields(**kw):
    return dict(dict(yaw_q=0, pitch_q=0, speed_code=2, duration_ms=12000), **kw)


def capture(t, session=73, capture_id=None):
    r = json.loads(t.raw)
    y, p, s, ttl = [r[k] for k in ('yaw_q', 'pitch_q', 'speed_code', 'duration_ms')]
    seq = r['request_seq']
    command = [y & 65535, p & 65535, 1, s, ttl, seq, seq]
    w = [0] * 32
    w[:6] = [capture_id or seq, seq, seq, (s << 8) | 1,
             ((p & 65535) << 16) | (y & 65535), ttl]
    # Absolute board time intentionally far from local owner time.
    for i, v in ((6, 7_000_000_000), (8, 7_000_000_000 + ttl * 50000),
                 (10, 7_000_000_000 + 2_000_001)):
        w[i:i+2] = [v & U32, v >> 32]
    w[12:18] = [1_000_000] * 3 + [125000 + 8*y, 125000 + 8*p, 25000 + 500*s]
    for i in range(3):
        w[18+2*i:20+2*i] = [1_000_000, 0]
        w[24+2*i:26+2*i] = [2_000_000, 0]
    w[30:] = [session, 0x47303550]
    before = 900_000_000_000_000
    return dict(command_words=command, capture_words=w,
                measured=dict(action=1 if s else 0, yaw_q=y, pitch_q=p,
                              speed_code=s, duration_ms=ttl),
                pwm_period=w[12:15], pwm_high=w[15:18],
                commit_before_monotonic_ns=before,
                returned_monotonic_ns=before + 50_000_000,
                conservative_deadline_monotonic_ns=before + ttl * 1_000_000,
                remaining_ns=ttl * 1_000_000 - 50_000_000)


def response(w, t, result):
    return dict(abi=ABI, op=t.op, request_seq=t.request_seq, status='COMPLETE',
                unknown=False, boot_id=w.binding.boot_id, build_id=w.binding.build_id,
                request_hash=w.binding.request_hash, io_count=100, result=result)


def sense_fields(**kw):
    return dict(dict(source_seq=1, adc_tick_ms=1000, em_tick_ms=999,
                     counts=[3099, 2006, 2084, None], quality=7,
                     source_digest='b'*64), **kw)


def sense_result(t):
    r = json.loads(t.raw)
    # Deliberate envelope-only placeholders; no causal/E4 proof is inferred.
    return dict(wire_hex='a55a', decoded=[{} for _ in range(4)],
                result_rows=[{} for _ in range(4)], tag=t.request_seq,
                correlation='FOUR_FRAME_CRC_SOURCE_CONSISTENT',
                **{k: r[k] for k in ('source_seq', 'source_digest', 'quality',
                                     'adc_tick_ms', 'em_tick_ms')})


class AdapterControls(unittest.TestCase):
    def pending_apply(self, **kwargs):
        w = initialized()
        t = w.begin('apply', now_ns=10, **apply_fields(**kwargs))
        w.mark_sent(t, now_ns=20)
        return w, t, response(w, t, capture(t))

    def poison(self, w, t, raw, now=30):
        with self.assertRaises(ProtocolError):
            w.finish(t, raw, now_ns=now)
        self.assertTrue(w.poisoned)
        self.assertIsNone(w.pending)
        with self.assertRaises(ProtocolError):
            w.begin('stop', now_ns=now+1)

    def test_init_exact_original_no_seq_no_unknown(self):
        w = ContinuousWire(binding())
        t = w.begin('init', now_ns=0)
        self.assertEqual(t.request_seq, 0)
        self.assertTrue(t.raw.endswith(b'\n'))
        self.assertEqual(set(json.loads(t.raw)),
                         {'abi','op','request_seq','boot_id','build_id','request_hash'})
        with self.assertRaises(FrozenInstanceError):
            t.op = 'apply'
        w.mark_sent(t, now_ns=1)
        reply = w.finish(t, line(init_reply(w.binding)), now_ns=2)
        self.assertTrue(w.ready)
        self.assertIsNone(reply.grant_deadline_ns)
        self.assertIsNone(w.grant_deadline_ns)

    def test_init_wrong_scope_or_motion_or_extra_refused(self):
        for changes in ({'scope_sha256':'c'*64}, {'speed_applied':True},
                        {'speed_applied':0}, {'formal_acceptance':'PASS'},
                        {'request_seq':0}, {'unknown':False}, {'extra':1},
                        {'initial_speed_code':True}):
            with self.subTest(changes=changes):
                w = ContinuousWire(binding()); t = w.begin('init', now_ns=0)
                w.mark_sent(t, now_ns=1)
                r = init_reply(w.binding); r.update(changes)
                self.poison(w, t, line(r))

    def test_one_pending_and_one_owner(self):
        w, t, r = self.pending_apply()
        with self.assertRaises(ProtocolError):
            w.begin('sense', now_ns=21, **sense_fields())
        errors = []
        def foreign():
            try:
                w.check_time(now_ns=22)
            except ProtocolError as e:
                errors.append(str(e))
        th = threading.Thread(target=foreign); th.start(); th.join()
        self.assertEqual(len(errors), 1)
        self.assertIs(w.pending, t)
        w.finish(t, line(r), now_ns=30)

    def test_write_intent_once_and_ticket_identity(self):
        w = initialized(); t = w.begin('apply', now_ns=10, **apply_fields())
        with self.assertRaises(ProtocolError):
            w.finish(t, line(response(w,t,capture(t))), now_ns=11)
        with self.assertRaises(ProtocolError):
            w.mark_sent(copy.copy(t), now_ns=12)
        w.mark_sent(t, now_ns=13)
        with self.assertRaises(ProtocolError):
            w.mark_sent(t, now_ns=14)
        with self.assertRaises(ProtocolError):
            w.abort_unsent(t)
        w.fail(t, 'write uncertain')
        self.assertTrue(w.poisoned)
        with self.assertRaises(ProtocolError):
            w.mark_sent(t, now_ns=15)

    def test_abort_unsent_burns_sequence(self):
        w = initialized(); t = w.begin('apply', now_ns=10, **apply_fields())
        w.abort_unsent(t)
        t2 = w.begin('apply', now_ns=11, **apply_fields())
        self.assertEqual(t2.request_seq, t.request_seq + 1)

    def test_bad_json_lines_poison(self):
        raws = [b'', b'{}', b'{}\n\n', b'{\n}\n', b'null\n', b'[]\n',
                b'\xff\n', b'{"x":1,"x":2}\n', b'{"x":NaN}\n',
                b'{"x":Infinity}\n', b'{"x":-Infinity}\n', b'x'*32768+b'\n']
        for raw in raws:
            with self.subTest(raw=raw[:50]):
                w,t,_ = self.pending_apply(); self.poison(w,t,raw)

    def test_binding_op_seq_unknown_and_bool_refused(self):
        for changes in ({'boot_id':'other'}, {'build_id':'0'*32}, {'request_hash':'0'*64},
                        {'op':'sense'}, {'request_seq':2}, {'request_seq':True},
                        {'unknown':True}, {'unknown':0}, {'status':'UNKNOWN'},
                        {'io_count':True}, {'io_count':4097}, {'extra':1}):
            with self.subTest(changes=changes):
                w,t,r = self.pending_apply(); r.update(changes)
                self.poison(w,t,line(r))

    def test_duplicate_response_key_poison(self):
        w,t,r = self.pending_apply()
        raw = line(r).replace(b'"unknown":false', b'"unknown":false,"unknown":false')
        self.poison(w,t,raw)

    def test_detached_reply_mutation_no_authority_no_replay(self):
        w,t,r = self.pending_apply(); reply = w.finish(t,line(r),now_ns=30)
        first = reply.result; first['measured']['speed_code'] = 20
        self.assertEqual(reply.result['measured']['speed_code'], 2)
        self.assertEqual(reply.authority, 'none')
        with self.assertRaises(ProtocolError):
            w.finish(t,line(r),now_ns=31)

    def test_pause_then_resume_fresh_measured_pwm(self):
        w = initialized()
        for i,speed in enumerate((2,0,3),1):
            now = 1000*i
            t = w.begin('apply',now_ns=now-1,**apply_fields(speed_code=speed))
            w.mark_sent(t,now_ns=now)
            reply = w.finish(t,line(response(w,t,capture(t))),now_ns=now+1)
            self.assertEqual(reply.result['measured']['speed_code'],speed)
            self.assertEqual(reply.result['pwm_high'][2],25000+500*speed)
            self.assertFalse(w.closed)

    def test_init_abort_does_not_allow_second_load_attempt(self):
        w=ContinuousWire(binding());t=w.begin('init',now_ns=0)
        w.abort_unsent(t)
        with self.assertRaises(ProtocolError): w.begin('init',now_ns=1)

    def test_echo_only_and_missing_capture_refused(self):
        for result in ({'yaw_q':0,'pitch_q':0,'speed_code':2}, {}, {'measured':{}}):
            w,t,r = self.pending_apply(); r['result']=result
            self.poison(w,t,line(r))
        for key in capture(self.pending_apply()[1]):
            w,t,r = self.pending_apply(); del r['result'][key]
            self.poison(w,t,line(r))

    def test_capture_adversarial_witnesses(self):
        mutations = [(0,0),(1,2),(2,2),(3,1),(4,1),(5,3000),
                     (8,1),(10,1),(12,999998),(15,125003),
                     (18,0),(24,2000002),(30,74),(31,0)]
        for index,value in mutations:
            with self.subTest(index=index):
                w,t,r = self.pending_apply(); r['result']['capture_words'][index]=value
                self.poison(w,t,line(r))
        w,t,r = self.pending_apply(); r['result']['measured']['speed_code']=True
        self.poison(w,t,line(r))
        w,t,r = self.pending_apply(); r['result']['remaining_ns']+=1
        self.poison(w,t,line(r))

    def test_conservative_grant_and_exact_guard(self):
        w = initialized(clock_error_ns=123)
        t = w.begin('apply',now_ns=10,**apply_fields()); w.mark_sent(t,now_ns=20)
        r = response(w,t,capture(t)); reply=w.finish(t,line(r),now_ns=30)
        expected=20+r['result']['remaining_ns']-123
        self.assertEqual(reply.grant_deadline_ns,expected)
        self.assertLess(expected,r['result']['conservative_deadline_monotonic_ns'])
        w.check_time(now_ns=expected-100_000_001)
        with self.assertRaises(ProtocolError):
            w.check_time(now_ns=expected-100_000_000)
        self.assertTrue(w.poisoned)

    def test_late_return_clock_regression_and_timeout(self):
        w,t,r=self.pending_apply()
        self.poison(w,t,line(r),now=4_000_000_020)
        w,t,r=self.pending_apply(); self.poison(w,t,line(r),now=19)
        w,t,r=self.pending_apply(duration_ms=100)
        self.poison(w,t,line(r))  # remaining50ms cannot provide100ms guard
        w=initialized(); w.check_time(now_ns=100)
        with self.assertRaises(ProtocolError): w.check_time(now_ns=99)
        self.assertTrue(w.poisoned)

    def test_no_arbitrary_64_command_or_mission_cap(self):
        w=initialized()
        for i in range(1,130):
            now=i*1_000_000_000
            t=w.begin('apply',now_ns=now,**apply_fields())
            self.assertEqual(t.request_seq,i)
            w.mark_sent(t,now_ns=now+1)
            w.finish(t,line(response(w,t,capture(t))),now_ns=now+2)
            self.assertIsNone(w.pending)
        self.assertFalse(w.poisoned)

    def test_intrinsic_request_exhaustion_no_wrap(self):
        w=initialized(); w._seq=U32-1  # boundary seam, not billions of IOs
        t=w.begin('apply',now_ns=10,**apply_fields())
        self.assertEqual(t.request_seq,U32); w.abort_unsent(t)
        with self.assertRaises(ProtocolError):
            w.begin('apply',now_ns=11,**apply_fields())
        self.assertEqual(w._seq,U32)

    def test_intrinsic_source_and_microsecond_tick_bounds(self):
        for fields in (sense_fields(source_seq=16384),
                       sense_fields(adc_tick_ms=U32//1000+1),
                       sense_fields(adc_tick_ms=1000,em_tick_ms=1001)):
            w=initialized()
            with self.assertRaises(ProtocolError): w.begin('sense',now_ns=10,**fields)
        w=initialized()
        t=w.begin('sense',now_ns=10,**sense_fields(source_seq=16383,adc_tick_ms=U32//1000,em_tick_ms=U32//1000))
        w.mark_sent(t,now_ns=11); w.finish(t,line(response(w,t,sense_result(t))),now_ns=12)
        with self.assertRaises(ProtocolError):
            w.begin('sense',now_ns=13,**sense_fields(source_seq=16384))

    def test_sense_four_lane_null_and_fault_preserved(self):
        for counts,q in (([3099,2006,2084,None],7),([None]*4,4096),([4095,None,None,None],17)):
            w=initialized(); t=w.begin('sense',now_ns=10,**sense_fields(counts=counts,quality=q))
            self.assertEqual(json.loads(t.raw)['counts'],counts)
            self.assertEqual(json.loads(t.raw)['quality'],q)
            w.mark_sent(t,now_ns=11)
            reply=w.finish(t,line(response(w,t,sense_result(t))),now_ns=12)
            self.assertEqual(reply.result['quality'],q)

    def test_sense_illegal_quality_and_missing_c3_refused(self):
        for changes in ({'quality':15}, {'quality':0x1007}, {'quality':0x207},
                        {'quality':0x87}, {'counts':[1,2,3]},
                        {'counts':[1,2,3,0]}, {'counts':[True,2,3,None]},
                        {'source_seq':True}, {'counts':[4096,2,3,None]}):
            with self.subTest(changes=changes):
                w=initialized()
                with self.assertRaises(ProtocolError):
                    w.begin('sense',now_ns=10,**sense_fields(**changes))

    def test_sense_strict_source_and_em_history(self):
        w=initialized(); t=w.begin('sense',now_ns=10,**sense_fields())
        w.mark_sent(t,now_ns=11); w.finish(t,line(response(w,t,sense_result(t))),now_ns=12)
        for changes in ({'source_seq':1,'em_tick_ms':1000},
                        {'source_seq':2,'em_tick_ms':999}):
            with self.assertRaises(ProtocolError):
                w.begin('sense',now_ns=13,**sense_fields(**changes))

    def test_sense_response_metadata_mismatch_poison(self):
        for key,value in (('source_seq',2),('quality',15),('adc_tick_ms',1001),
                          ('em_tick_ms',998),('source_digest','c'*64),
                          ('wire_hex','00'*253),('decoded',[{},{}]),
                          ('result_rows',[]),('correlation','TRUST_ME')):
            w=initialized(); t=w.begin('sense',now_ns=10,**sense_fields())
            w.mark_sent(t,now_ns=11); r=response(w,t,sense_result(t));r['result'][key]=value
            self.poison(w,t,line(r))

    def test_apply_validation_curvature_pause_and_unknown_build(self):
        for changes in ({'yaw_q':True}, {'pitch_q':15001}, {'speed_code':21},
                        {'duration_ms':True}, {'duration_ms':0}, {'duration_ms':12001},
                        {'speed_code':0,'yaw_q':1},
                        {'yaw_q':6000,'pitch_q':6000,'speed_code':20}):
            w=initialized()
            with self.assertRaises(ProtocolError):
                w.begin('apply',now_ns=10,**apply_fields(**changes))
        w=initialized(build='1'*32)
        with self.assertRaises(ProtocolError):
            w.begin('apply',now_ns=10,**apply_fields(duration_ms=3001))
        t=w.begin('apply',now_ns=11,**apply_fields(duration_ms=3000))
        self.assertEqual(json.loads(t.raw)['duration_ms'],3000)

    def test_terminal_stop_distinct_from_pause(self):
        for op in ('stop','shutdown'):
            w=initialized();t=w.begin(op,now_ns=10);w.mark_sent(t,now_ns=11)
            result=dict(stop_write_returned=True,status=0,fault=0,physical_zero_capture_proven=False)
            reply=w.finish(t,line(response(w,t,result)),now_ns=12)
            self.assertTrue(w.closed)
            self.assertFalse(reply.result['physical_zero_capture_proven'])
            self.assertIsNone(w.grant_deadline_ns)
            with self.assertRaises(ProtocolError):
                w.begin('apply',now_ns=13,**apply_fields())


if __name__ == '__main__':
    unittest.main()
