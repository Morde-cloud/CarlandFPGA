"""Main independent bus-level expectations; no worker test/oracle import."""
import argparse, importlib.util, json, random, sys, unittest
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',required=True);args=p.parse_args()
spec=importlib.util.spec_from_file_location('register_candidate',args.source);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
counts={}
def count(k,n=1):counts[k]=counts.get(k,0)+n
def domain():return dict(fixture_id='MAIN-only-synthetic',identity=0x12345678,rate_codes=[3,5],sensor_profiles=[4,8],motion_profiles=[2,6],apply_blocks=[7,9],queue_capacity=11,clock_id='MAIN-synthetic-clock')
def context():return dict(session=0x12345678,boot_digest='a'*64,config_epoch=0,control_epoch=3,request_seq=17)
def values(n=1):return dict(yaw_q=-15000,pitch_q=15000,speed_code=20,wire_capture_seq=n,sample_tick=(1<<32)+n,yaw_period=(1<<32)+7,pitch_period=2000000,speed_period=2000000,quality=15,gain_code=4,ratio_q8_8=512,ratio_valid=True,motion_profile=2,last_observed_sequence=65535)
def stage(x,seq=0,block=7):
    for a,d in ((0x10,(block<<16)|57),(0x18,3),(0x1c,2),(0x20,4)):x.write(a,d)
    x.write(0x14,seq)
def ready():
    x=m.RegisterTransactionModel(domain());x.set_context(context());x.set_cdc(True,False);x.set_fixture_gates(True,True);stage(x);x.block_boundary(7);return x
def latched():
    x=ready();t=x.begin_capture(1);x.complete_capture(t,values());x.write(8,8);return x,t
class MainReview(unittest.TestCase):
    def reject(self,fn,*a,**kw):
        with self.assertRaises(ValueError):fn(*a,**kw)
        count('expected_rejections')
    def test_initial_access(self):
        x=m.RegisterTransactionModel();self.assertEqual(x.read(12),1)
        for a in (8,20):self.assertEqual(x.read(a),0)
        self.reject(x.read,0)
        for a in (44,-4,2,0x74,1<<32,True):
            self.reject(x.read,a)
            for st in (0,15):self.reject(x.write,a,0,st)
        for a in (0,4,12,36,40,*range(0x30,0x74,4)):
            for st in (0,15):self.reject(x.write,a,0,st)
        for a in range(0x30,0x74,4):self.assertEqual(x.read(a),0)
        for a in (8,16,20,24,28,32):x.write(a,0xffffffff,0)
        self.assertEqual(x.read(12),1);count('accessible_words',28)
    def test_control_strobes(self):
        # Independent command truth table with READY state; STOP dominates all defined bits.
        for st in range(16):
            mask=sum(255<<(8*i) for i in range(4) if st>>i&1)
            for d in list(range(64))+[0x80000001,0x80000000,0x10001,0x10004,0xffffffff]:
                x=ready();x.write(8,4);effective=d&mask;stop=bool(st&1 and d&1)
                allowed=(not effective or stop and not(effective&~31) or st==15 and effective in (2,4,8,16))
                # CLEAR_FAULT in enabled state and LATCH without publication must reject.
                if effective in (2,8) and not stop:allowed=False
                try:x.write(8,d,st);success=True
                except ValueError:success=False
                self.assertEqual(success,allowed,(st,hex(d)))
                if stop:self.assertEqual(x.read(12)&1025,1,(st,d))
                else:self.assertEqual(x.read(12)&1025,1024,(st,d))
                self.assertEqual(x.read(12)&~0x00ff07ff,0);count('command_strobe_cases')
    def test_shadow_atomicity(self):
        rng=random.Random(1019);x=ready();expected={16:0x70039,24:3,28:2,32:4}
        for _ in range(3000):
            a=rng.choice(tuple(expected));st=rng.randrange(16);d=rng.getrandbits(32)
            if rng.randrange(2):d=rng.choice([0,1,2,3,4,5,8,0x70039,0x900ff])
            mask=sum(255<<(8*i) for i in range(4) if st>>i&1);new=(expected[a]&~mask)|(d&mask)
            ok=st==0 or (a==16 and new<=0xffffff and (new>>16) in (7,9) or a==24 and new in (3,5) or a==28 and new in (0,1,2,4,8) or a==32 and new in (4,8))
            try:x.write(a,d,st);success=True
            except ValueError:success=False
            self.assertEqual(success,ok,(a,d,st));expected[a]=new if ok else expected[a]
            self.assertEqual(x.read(a),expected[a]);count('shadow_reference_cases')
    def test_atomic_apply_zero_duplicate_stop(self):
        x=m.RegisterTransactionModel(domain());x.set_context(context());x.set_cdc(True,False);x.set_fixture_gates(True,True)
        stage(x,0);self.assertEqual(x.read(12)&256,256);self.reject(x.write,8,4)
        x.write(16,0x900aa);x.block_boundary(9);self.assertEqual(x.read(12)&256,256)
        x.block_boundary(7);self.assertEqual(x.read(12)&256,0);x.write(8,4)
        # restore original payload: seq0 duplicate must not create pending work or a second epoch.
        x.write(16,0x70039);x.write(20,0);self.assertEqual(x.read(12)&256,0)
        x.write(16,0x900aa);self.reject(x.write,20,0)
        x.write(20,1);x.write(8,1);self.assertEqual(x.read(12)&256,0)
        x.block_boundary(9);self.reject(x.write,20,1)
        x.reset();x.set_context({**context(),'config_epoch':1});x.set_cdc(True,False)
        for a,d in ((16,0x70039),(24,3),(28,2),(32,4)):x.write(a,d)
        self.reject(x.write,20,0);count('config_lifecycle_checks',12)
    def test_fault_separate_enable(self):
        x=ready();x.write(8,4);x.raise_fault(0x81);self.assertEqual(x.read(12)&0xff0003,0x810003)
        self.reject(x.write,8,6);self.reject(x.write,8,4)
        x.write(8,2);self.assertEqual(x.read(12)&0xff0003,1);x.write(8,4)
        self.assertEqual(x.read(12)&1025,1024)
    def test_apply_boundaries_and_zero_domains(self):
        for st in range(1,15):
            x=ready();self.reject(x.write,20,1,st);self.assertEqual(x.read(12)&256,0)
        x=ready();self.reject(x.write,20,65536);self.reject(x.write,20,True)
        x=m.RegisterTransactionModel(domain());x.set_context({**context(),'config_epoch':255})
        for a,d in ((16,0x70039),(24,3),(28,2),(32,4)):x.write(a,d)
        self.reject(x.write,20,0);self.assertEqual(x.read(12)&256,0)
        d=domain();d.update(rate_codes=[0],sensor_profiles=[0],apply_blocks=[0])
        x=m.RegisterTransactionModel(d);x.set_context(context());x.set_cdc(True,False);x.set_fixture_gates(True,True)
        self.reject(x.write,20,0)
        for a in (16,24,28,32):x.write(a,0)
        x.write(20,0);x.block_boundary(0);x.write(8,4);self.assertEqual(x.read(12)&1025,1024)
        count('apply_boundaries',19)
    def test_snapshot_words_and_aliases(self):
        x,t=latched();expected={0x30:0xffffc568,0x34:20,0x38:0x0e030011,0x3c:0x12345678,0x40:1,0x44:1,0x48:7,0x4c:1,0x50:1,0x54:15,0x58:4,0x5c:512,0x60:15000,0x64:2000000,0x68:2000000,0x6c:2,0x70:65535}
        for a,v in expected.items():self.assertEqual(x.read(a),v)
        r=x.read_snapshot();self.assertIsInstance(r,dict);r.clear()
        for a,v in expected.items():self.assertEqual(x.read(a),v)
        self.reject(x.complete_capture,t,values());count('snapshot_words',17)
    def test_random_capture_projection(self):
        rng=random.Random(20261019);x=ready()
        for n in range(128):
            v=values(n);v.update(yaw_q=rng.randint(-15000,15000),pitch_q=rng.randint(-15000,15000),speed_code=rng.randrange(21),sample_tick=(1<<40)+n,gain_code=rng.choice([0,1,2,4]),quality=rng.randrange(16),ratio_valid=bool(n%2),ratio_q8_8=rng.randrange(65536))
            t=x.begin_capture(n);x.complete_capture(t,v);x.write(8,8)
            for a,expected in ((48,v['yaw_q']&0xffffffff),(96,v['pitch_q']&0xffffffff),(52,v['speed_code']),(64,n),(68,256),(80,n),(84,v['quality']),(88,v['gain_code']),(92,v['ratio_q8_8'])):self.assertEqual(x.read(a),expected)
            self.assertEqual(bool(x.read(12)&512),v['ratio_valid']);x.read_snapshot();x.write(8,16);count('random_capture_projections')
    def test_revocation_at_every_read(self):
        actions=[('STOP',lambda x:x.write(8,1)),('fault',lambda x:x.raise_fault(1)),('reset',lambda x:x.reset()),('newcycle',lambda x:x.begin_capture(2)),('release',lambda x:x.write(8,16)),('offline',lambda x:x.set_cdc(False,False)),('busy',lambda x:x.set_cdc(True,True)),('context',lambda x:x.set_context({**context(),'config_epoch':1,'request_seq':18}))]
        for name,action in actions:
            for target in range(0x30,0x74,4):
                x,_=latched()
                def hook(a,obj):
                    if a==target:action(obj)
                self.reject(x.read_snapshot,hook)
                self.assertEqual(x.read(12)&(8|512),0);count('reader_revocation_interleavings')
        x,_=latched();self.reject(x.write,8,8);self.reject(x.read_snapshot)
    def test_late_tickets(self):
        for action in (lambda x:x.write(8,1),lambda x:x.raise_fault(1),lambda x:x.reset(),lambda x:x.begin_capture(2),lambda x:x.set_cdc(False,False),lambda x:x.set_context({**context(),'config_epoch':1,'request_seq':18})):
            x=ready();ticket=x.begin_capture(1);action(x);self.reject(x.complete_capture,ticket,values());self.assertEqual(x.read(12)&(8|16|512),0);count('stale_ticket_schedules')
        x=ready();other=ready();t=other.begin_capture(1);x.begin_capture(1);self.reject(x.complete_capture,t,values())
    def test_bad_capture_and_no_wrap(self):
        bad={'yaw_q':[-15001,15001,True],'pitch_q':[-15001,15001],'speed_code':[-1,21], 'wire_capture_seq':[-1,65536,True],'sample_tick':[-1,1<<64],'yaw_period':[-1,1<<64,0],'pitch_period':[-1,1<<32,0],'speed_period':[-1,1<<32,0],'quality':[-1,16,True],'gain_code':[3,8],'ratio_q8_8':[-1,65536],'ratio_valid':[1,None],'motion_profile':[1,256],'last_observed_sequence':[-1,65536]}
        for key,vs in bad.items():
            for v in vs:
                x=ready();t=x.begin_capture(1);self.reject(x.complete_capture,t,{**values(),key:v});self.assertEqual(x.read(12)&(8|16|512),0);count('invalid_capture_cases')
        x=ready();t=x.begin_capture(0xffffffff);x.complete_capture(t,values(65535));self.reject(x.begin_capture,0);self.reject(x.begin_capture,1<<32)
        x=ready();t=x.begin_capture(1);x.complete_capture(t,values(65535));t=x.begin_capture(2);self.reject(x.complete_capture,t,values(0))
        x=ready();t=x.begin_capture(1);x.complete_capture(t,values());t=x.begin_capture(2);self.reject(x.complete_capture,t,{**values(2),'sample_tick':0})
    def test_input_aliases_queue_and_strict_types(self):
        d=domain();c=context();x=m.RegisterTransactionModel(d);x.set_context(c);d['rate_codes'][0]=99;c['session']=0
        x.set_cdc(True,False);stage(x);x.block_boundary(7);t=x.begin_capture(1);v=values();x.complete_capture(t,v);v['yaw_q']=0;x.write(8,8);self.assertEqual(x.read(0x30),0xffffc568);self.assertEqual(x.read(0x3c),0x12345678)
        x.set_queue(11,65530,65531);x.set_queue(11,10,10);self.assertEqual(x.read(36),(11<<16)|11);self.assertEqual(x.read(40),0xffffffff)
        self.reject(x.set_queue,12);self.reject(x.set_queue,-1);self.reject(x.set_queue,1,-1,0)
        self.assertEqual(x.read(40),0xffffffff)
        for a,d,s in ((True,0,15),(8,True,15),(8,0,True),(8,-1,15),(8,1<<32,15),(8,0,16)) : self.reject(x.write,a,d,s)
        self.reject(x.set_context,{**context(),'config_epoch':1,'request_seq':16})
        self.reject(m.RegisterTransactionModel,{**domain(),'extra':1});self.reject(m.RegisterTransactionModel,{**domain(),'queue_capacity':True})
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(MainReview))
    print(json.dumps({'main_counts':counts,'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'software_fixture_only':True},sort_keys=True))
    raise SystemExit(not result.wasSuccessful())
