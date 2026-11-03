"""Independent synthetic controls; no device, process, network or product authority.

H01-H15 rev2, fixed817b355; requirements SHA256
2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d.
Run only after main's explicit hash freeze. All native samples below are fabricated.
"""
import copy
import dataclasses
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from drill_live_link.model import FollowMapper, FollowError, Limits, project
from drill_live_link.follower import Follower

MS = 1_000_000
IDENTITY = (0., 0., 0., 1.)


def axis(axis_index, degrees):
    q = [0., 0., 0., math.cos(math.radians(degrees)/2)]
    q[axis_index] = math.sin(math.radians(degrees)/2)
    return tuple(q)


def mul(a, b):
    # Test fixture composition, not imported from the implementation.
    x,y,z,w = a; X,Y,Z,W = b
    return (w*X+x*W+y*Z-z*Y, w*Y-x*Z+y*W+z*X,
            w*Z+x*Y-y*X+z*W, w*W-x*X-y*Y-z*Z)


def sample(now=1_000*MS, *, seq=1, speed=.125, orientation=IDENTITY, age=2*MS):
    return {'run_id':'synthetic-controls248','source':'PC_DIRECT',
            'native': {'abi':'DEEPEYE-CONTINUOUS-NATIVE-794-v1',
            'tick_usec':'123456000', 'read_now_usec':'123457000',
            'deadline_usec':'124000000', 'revision':str(seq),
            'fault':'', 'ready':True, 'running':True, 'phase':'INSIDE',
            'orientation_xyzw':list(orientation), 'speed_m_s':speed,
            # Deliberately inconsistent decoys: only actual speed is legitimate.
            'target_speed_m_s':.25, 'speed_slider':100, 'initial_speed_m_s':.25},
            'host': {'send_qpc_ns':now-MS, 'receive_qpc_ns':now,
                     'accepted_tick_qpc_interval_ns':[now-age, now-MS]}}


def mapper(**kwargs):
    return FollowMapper('synthetic-controls248', 'PC_DIRECT', IDENTITY, **kwargs)


class Clock:
    def __init__(self): self.now=1_000*MS
    def __call__(self): return self.now
    def advance(self, ms): self.now += ms*MS


class FakeClient:
    """Explicitly synthetic baseline-shaped ACK, never a transport."""
    def __init__(self):
        self.calls=[]; self.fail_op=None; self.fail_result=None; self.raise_op=None
        self.seq=0;self.duty=0
    def _call(self, op, *args, **kwargs):
        self.calls.append((op,args,kwargs))
        if self.raise_op == op: raise OSError('synthetic unknown IO')
        if self.fail_op == op: return self.fail_result
        self.seq+=1
        if op=='motor': self.duty=0 if args[0]==0 else int(round(250+5*args[0]))
        if op=='stop': self.duty=0
        return {'event':op, 'declared_source':'PC_DIRECT',
                'status':{'seq':self.seq,'result_code':0, 'result':'OK',
                          'requested_duty_permille':self.duty,'armed':self.duty>0,
                          'last_joho_error':0,'yaw_feedback':{'fresh':True},
                          'pitch_feedback':{'fresh':True}},
                'simulation':True, 'measured_rpm':None}
    def pose(self, *args, **kwargs): return self._call('pose',*args,**kwargs)
    def motor(self, *args, **kwargs): return self._call('motor',*args,**kwargs)
    def keepalive(self): return self._call('keepalive')
    def stop(self): return self._call('stop')
    def count(self, op): return sum(c[0]==op for c in self.calls)


class ProjectionControls(unittest.TestCase):
    def check(self, q, ref, expected):
        actual=project(q,ref)
        for a,e in zip(actual,expected): self.assertAlmostEqual(a,e,places=7)

    def test_manual_cardinal_forward_right_left_up_down(self):
        self.check(IDENTITY,IDENTITY,(0,0))
        self.check(axis(1,90),IDENTITY,(90,0))
        self.check(axis(1,-90),IDENTITY,(-90,0))
        self.check(axis(0,-30),IDENTITY,(0,30))
        self.check(axis(0,30),IDENTITY,(0,-30))

    def test_roll_and_quaternion_sign_do_not_change_forward(self):
        self.check(axis(2,74),IDENTITY,(0,0))
        q=mul(axis(1,35),axis(2,81))
        self.check(q,IDENTITY,(35,0))
        self.check(tuple(-v for v in q),IDENTITY,(35,0))

    def test_nonidentity_reference_including_roll(self):
        ref=mul(axis(1,40),axis(2,63))
        self.check(ref,ref,(0,0))
        self.check(mul(ref,axis(1,-25)),ref,(-25,0))
        self.check(mul(ref,axis(0,-20)),ref,(0,20))

    def test_vertical_heading_undefined(self):
        with self.assertRaises(FollowError): project(axis(0,-90),IDENTITY)

    def test_nonfinite_bool_and_nonunit_quaternions(self):
        for q in [(0,0,0,0),(0,0,0,2),(False,0,0,1),(float('nan'),0,0,1),
                  (0,0,float('inf'),1),[0,0,1],{'x':0}]:
            with self.subTest(q=q),self.assertRaises(FollowError): project(q,IDENTITY)


class MappingControls(unittest.TestCase):
    def test_exact_run_source_binding_and_sample_envelope(self):
        for key,value in [('run_id','other-run'),('source','FPGA_OUTPUT'),('extra',1)]:
            s=sample();s[key]=value
            with self.subTest(key=key),self.assertRaises(FollowError): mapper().map(s,now_ns=1_000*MS)
        for key in ['run_id','source','native','host']:
            s=sample();del s[key]
            with self.subTest(missing=key),self.assertRaises(FollowError): mapper().map(s,now_ns=1_000*MS)

    def test_actual_speed_over_slider_and_no_authority(self):
        for speed,pct,duty in [(0,0,0),(.125,50,500),(.25,100,750)]:
            with self.subTest(speed=speed):
                s=sample(speed=speed); original=copy.deepcopy(s)
                t=mapper().map(s,now_ns=1_000*MS)
                self.assertEqual((t.speed_pct,t.duty_permille),(pct,duty))
                self.assertIsNone(t.measured_rpm)
                self.assertEqual(t.authority,'display_only_no_product_authority')
                self.assertEqual(s,original)
                with self.assertRaises(dataclasses.FrozenInstanceError): t.speed_pct=99

    def test_boundaries_and_explicit_out_of_range_no_clamping(self):
        for q in [axis(1,91),axis(1,-91),axis(0,46),axis(0,-69)]:
            s=sample(orientation=q); original=copy.deepcopy(s)
            with self.subTest(q=q),self.assertRaises(FollowError): mapper().map(s,now_ns=1_000*MS)
            self.assertEqual(s,original)
        t=mapper().map(sample(orientation=axis(1,89)),now_ns=1_000*MS)
        self.assertEqual(t.yaw_cd,8900)

    def test_restrictive_limits_and_invalid_types(self):
        for kw in [{'yaw_min_deg':-91},{'yaw_max_deg':91},{'pitch_min_deg':-46},
                   {'pitch_max_deg':69},{'maximum_duty_permille':751},
                   {'max_source_age_ns':250*MS+1},{'keepalive_period_ns':100*MS+1},
                   {'speed_reference_m_s':float('nan')},{'move_ms':True},
                   {'maximum_duty_permille':True},{'max_source_age_ns':1.5},
                   {'speed_reference_m_s':True}]:
            with self.subTest(kw=kw),self.assertRaises(FollowError): Limits(**kw)
        t=mapper(limits=Limits(yaw_min_deg=-20,yaw_max_deg=20,maximum_duty_permille=500)).map(sample(speed=.25),now_ns=1_000*MS)
        self.assertEqual((t.speed_pct,t.duty_permille),(50,500))
        with self.assertRaises(FollowError):
            mapper(limits=Limits(yaw_min_deg=-20,yaw_max_deg=20)).map(sample(orientation=axis(1,21)),now_ns=1_000*MS)

    def test_exact_native_tick_strings(self):
        for field in ['tick_usec','read_now_usec','deadline_usec','revision']:
            for bad in [True,123,'01','+1','1.0',' 1','١','-1','']:
                s=sample();s['native'][field]=bad
                with self.subTest(field=field,bad=bad),self.assertRaises(FollowError): mapper().map(s,now_ns=1_000*MS)

    def test_sampling_age_includes_original_acquisition(self):
        s=sample(age=250*MS)
        with self.assertRaises(FollowError): mapper().map(s,now_ns=1_000*MS)
        s=sample(age=249*MS);t=mapper().map(s,now_ns=1_000*MS)
        self.assertEqual(t.acquired_lower_ns,751*MS)
        self.assertEqual(t.valid_until_ns,1_001*MS)

    def test_receive_replay_revision_and_now_reversal(self):
        m=mapper();s=sample();m.map(s,now_ns=1_000*MS)
        with self.assertRaises(FollowError): m.map(s,now_ns=1_001*MS)
        m.map(sample(1_002*MS,seq=1),now_ns=1_002*MS) # equal revision legitimate readback
        with self.assertRaises(FollowError): m.map(sample(1_003*MS,seq=0),now_ns=1_003*MS)
        with self.assertRaises(FollowError): m.map(sample(999*MS),now_ns=999*MS)

    def test_bad_host_brackets_and_boolean_status(self):
        cases=[('send_qpc_ns',True),('receive_qpc_ns',1_001*MS),
               ('accepted_tick_qpc_interval_ns',[1_000*MS,999*MS]),
               ('accepted_tick_qpc_interval_ns',[1_001*MS,1_001*MS])]
        for key,value in cases:
            s=sample();s['host'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(FollowError): mapper().map(s,now_ns=1_000*MS)
        for key,value in [('speed_m_s',True),('speed_m_s',float('inf')),('running',1),('ready',1),('fault',False)]:
            s=sample();s['native'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(FollowError): mapper().map(s,now_ns=1_000*MS)

    def test_grant_conservative_without_clock_epoch_alias(self):
        # Native origin changed by a vast offset: only durations may be compared.
        a=sample();b=copy.deepcopy(a)
        for key in ['tick_usec','read_now_usec','deadline_usec']:
            b['native'][key]=str(int(b['native'][key])+9_000_000_000_000)
        self.assertEqual(mapper().map(a,now_ns=1_000*MS).valid_until_ns,
                         mapper().map(b,now_ns=1_000*MS).valid_until_ns)
        s=sample();s['native']['deadline_usec']='123458000' # 1ms remains, fully debited
        with self.assertRaises(FollowError): mapper().map(s,now_ns=1_000*MS)
        s=sample();s['native']['deadline_usec']='123507000'
        t=mapper().map(s,now_ns=1_000*MS)
        self.assertLess(t.valid_until_ns,1_049*MS)
        self.assertGreater(t.valid_until_ns,1_047*MS)

    def test_future_native_tick_expired_grant_and_no_running_authority(self):
        for field,value in [('tick_usec','123457001'),('deadline_usec','123457000'),
                            ('running',False),('speed_m_s',-.001),('speed_m_s',.251)]:
            s=sample();s['native'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(FollowError): mapper().map(s,now_ns=1_000*MS)

    def test_full_roundtrip_debits_grant(self):
        s=sample(age=200*MS);s['host']['send_qpc_ns']=850*MS
        s['native']['deadline_usec']='123557000' # 100ms native left, RTT150ms
        with self.assertRaises(FollowError):mapper().map(s,now_ns=1_000*MS)

    def test_minimum_duty_limit_cannot_advertise_zero_speed_with_positive_pwm(self):
        # Either explicit configuration refusal or a baseline-consistent command.
        try:limits=Limits(maximum_duty_permille=250)
        except FollowError:return
        t=mapper(limits=limits).map(sample(),now_ns=1_000*MS)
        self.assertEqual(t.duty_permille,0 if t.speed_pct==0 else round(250+5*t.speed_pct))

    def test_terminal_states_zero_without_moving(self):
        for key,val in [('fault','synthetic fault'),('ready',False),('phase','ARRIVED')]:
            s=sample();s['native'][key]=val
            t=mapper().map(s,now_ns=1_000*MS)
            self.assertTrue(t.terminal)
            self.assertEqual((t.yaw_cd,t.pitch_cd,t.speed_pct,t.duty_permille),(0,0,0,0))


class FollowerControls(unittest.TestCase):
    def setup_follower(self,motor=False):
        c=Clock();client=FakeClient();f=Follower(client,mapper(),motor_enabled=motor,clock_ns=c)
        return c,client,f

    def test_no_startup_io_push_is_latest_only(self):
        c,client,f=self.setup_follower()
        self.assertEqual(f.tick(),[]);self.assertEqual(client.calls,[])
        f.push(sample(c.now,orientation=axis(1,10)))
        c.advance(1);t=f.push(sample(c.now,seq=2,orientation=axis(1,20)))
        self.assertEqual(client.calls,[])
        f.tick()
        self.assertEqual(client.count('pose'),1);self.assertEqual(client.count('motor'),0)
        p=next(x for x in client.calls if x[0]=='pose')
        self.assertEqual(p[1],(20.,0.));self.assertEqual(p[2],dict(move_ms=500,source_seq=t.snapshot_seq,observation_seq=2))

    def test_motor_changed_only_and_pose_dedup(self):
        c,client,f=self.setup_follower(True)
        f.push(sample(c.now));f.tick();f.tick()
        self.assertEqual(client.count('motor'),1);self.assertEqual(client.count('pose'),1)
        c.advance(20);f.push(sample(c.now,seq=2));f.tick()
        self.assertEqual(client.count('motor'),1);self.assertEqual(client.count('pose'),1)
        c.advance(20);f.push(sample(c.now,seq=3,speed=0));f.tick()
        self.assertEqual(client.count('motor'),2)
        self.assertEqual([x[1] for x in client.calls if x[0]=='motor'],[(50.,),(0,)])

    def test_pose_500ms_throttle_and_latest_replacement(self):
        c,client,f=self.setup_follower()
        f.push(sample(c.now));f.tick()
        for i in range(1,6):
            c.advance(100);f.push(sample(c.now,seq=i+1,orientation=axis(1,i*5)));f.tick()
            self.assertEqual(client.count('pose'),1 if i<5 else 2)
        self.assertEqual([x[1] for x in client.calls if x[0]=='pose'],[(0.,0.),(25.,0.)])

    def test_lease_interval_only_while_actual_source_fresh(self):
        c,client,f=self.setup_follower(True);f.push(sample(c.now));f.tick()
        c.advance(99);f.tick();self.assertEqual(client.count('keepalive'),0)
        c.advance(1);f.tick();self.assertEqual(client.count('keepalive'),1)
        c.advance(100);f.tick();self.assertEqual(client.count('keepalive'),2)
        c.advance(48) # lower bracket at998ms => expiry1248ms
        with self.assertRaises(FollowError): f.tick()
        self.assertEqual(client.count('keepalive'),2);self.assertEqual(client.count('stop'),1)
        with self.assertRaises(FollowError): f.tick()
        with self.assertRaises(FollowError): f.push(sample(c.now,seq=2))
        self.assertEqual(client.count('stop'),1)

    def test_native_grant_expiry_preempts_remaining_source_lifetime(self):
        c,client,f=self.setup_follower(True)
        s=sample(c.now);s['native']['deadline_usec']='123507000'
        f.push(s);f.tick();c.advance(48)
        with self.assertRaises(FollowError):f.tick()
        self.assertEqual(client.count('keepalive'),0);self.assertEqual(client.count('stop'),1)

    def test_terminal_push_immediate_stop_once(self):
        for key,val in [('fault','bad'),('ready',False),('phase','ARRIVED')]:
            c,client,f=self.setup_follower(True);s=sample(c.now);s['native'][key]=val
            f.push(s);self.assertEqual([x[0] for x in client.calls],['stop'])
            f.stop();self.assertEqual(client.count('stop'),1)

    def test_exception_unknown_outcome_no_retry_and_stop_once(self):
        for op in ['motor','pose','keepalive']:
            c,client,f=self.setup_follower(True);client.raise_op=op;f.push(sample(c.now))
            if op=='keepalive': f.tick();c.advance(100)
            with self.subTest(op=op),self.assertRaises(OSError): f.tick()
            count=client.count(op)
            with self.assertRaises(FollowError): f.tick()
            self.assertEqual(client.count(op),count);self.assertEqual(client.count('stop'),1)

    def test_negative_unknown_response_latches_stop(self):
        for op in ['motor','pose','keepalive']:
            for result in [None,False,{}, {'status':{'result_code':1}}, {'status':{'result_code':True}}]:
                with self.subTest(op=op,result=result):
                    c,client,f=self.setup_follower(True)
                    if op=='keepalive': f.push(sample(c.now));f.tick();c.advance(100)
                    else: f.push(sample(c.now))
                    client.fail_op=op;client.fail_result=result
                    with self.assertRaises(Exception): f.tick()
                    self.assertTrue(f.stopped);self.assertEqual(client.count('stop'),1)
                    n=client.count(op)
                    with self.assertRaises(FollowError): f.tick()
                    self.assertEqual(client.count(op),n)

    def test_mtr4_ack_binding_capability_and_sequence_refusal(self):
        good=FakeClient().pose(0,0)
        cases=[]
        for field,value in [('event','motor'),('declared_source','FPGA_OUTPUT')]:
            v=copy.deepcopy(good);v[field]=value;cases.append(v)
        for field,value in [('seq',0),('seq',True),('result_code',True),
                            ('requested_duty_permille',500),('armed',1),
                            ('last_joho_error',1),('yaw_feedback',{'fresh':False}),
                            ('pitch_feedback',{'fresh':1})]:
            v=copy.deepcopy(good);v['status'][field]=value;cases.append(v)
        for response in cases:
            with self.subTest(response=response):
                c,client,f=self.setup_follower();f.push(sample(c.now))
                client.fail_op='pose';client.fail_result=response
                with self.assertRaises(Exception):f.tick()
                self.assertEqual(client.count('stop'),1)

    def test_replayed_ack_sequence_causes_stop(self):
        c,client,f=self.setup_follower();f.push(sample(c.now));f.tick()
        response=FakeClient().keepalive() # seq1 <= already-confirmed sequence
        c.advance(100);client.fail_op='keepalive';client.fail_result=response
        with self.assertRaises(Exception):f.tick()
        self.assertEqual(client.count('stop'),1)

    def test_replayed_or_invalid_source_stop_once(self):
        c,client,f=self.setup_follower();s=sample(c.now);f.push(s)
        with self.assertRaises(FollowError): f.push(s)
        self.assertEqual([x[0] for x in client.calls],['stop'])
        f.stop();self.assertEqual(client.count('stop'),1)

    def test_unknown_stop_itself_is_not_retried(self):
        c,client,f=self.setup_follower();client.raise_op='stop'
        s=sample(c.now);s['native']['fault']='synthetic fault'
        with self.assertRaises(OSError):f.push(s)
        self.assertTrue(f.stopped);self.assertEqual(client.count('stop'),1)
        f.stop();self.assertEqual(client.count('stop'),1)

    def test_expiry_during_motor_reply_prevents_pose_and_lease(self):
        c,client,f=self.setup_follower(True)
        original=client.motor
        def slow_motor(speed):
            result=original(speed);c.advance(250);return result
        client.motor=slow_motor
        f.push(sample(c.now))
        with self.assertRaises(FollowError):f.tick()
        self.assertEqual([x[0] for x in client.calls],['motor','stop'])

    def test_no_other_thread_dispatch(self):
        import threading
        c,client,f=self.setup_follower(True);f.push(sample(c.now));errors=[]
        def foreign_tick():
            try:f.tick()
            except Exception as error:errors.append(error)
        t=threading.Thread(target=foreign_tick);t.start();t.join()
        self.assertEqual(len(errors),1);self.assertEqual(client.calls,[])


class SessionAdapterControls(unittest.TestCase):
    def test_duration_deadline_and_no_open_on_constructor(self):
        from drill_live_link.session_client import SessionClient
        class Session:
            session_id='synthetic';request_id=10
            def __init__(self):self.requests=[]
            def clock_ms(self):return 123000
            def handle(self,request):
                self.requests.append(request);self.request_id=request['request_id'];return {'record':request}
        s=Session();c=SessionClient(s);self.assertEqual(s.requests,[])
        c.pose(12,-3,move_ms=500,source_seq=7,observation_seq=9)
        c.motor(50);c.keepalive();c.stop()
        self.assertEqual([r['op'] for r in s.requests],['pose','motor','keepalive','stop'])
        self.assertEqual([r['request_id'] for r in s.requests],[11,12,13,14])
        for r in s.requests:
            self.assertEqual(r['expires_ms'],123500);self.assertEqual(r['session'],'synthetic')
        self.assertEqual(s.requests[0]['source_seq'],7)
        self.assertEqual(s.requests[0]['observation_seq'],9)


if __name__=='__main__': unittest.main(verbosity=2)
