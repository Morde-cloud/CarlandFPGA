"""Reentrant input and lifecycle probes independently authored by B main."""
import argparse,importlib.util,json,sys,unittest
from collections.abc import Mapping
p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args();sp=importlib.util.spec_from_file_location('model',a.source);m=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m;sp.loader.exec_module(m)
def ctx():return dict(session=9,boot_digest='b'*64,config_epoch=0,control_epoch=1,request_seq=2)
def val():return dict(yaw_q=0,pitch_q=0,speed_code=1,wire_capture_seq=1,sample_tick=100,yaw_period=10,pitch_period=10,speed_period=10,quality=15,gain_code=0,ratio_q8_8=256,ratio_valid=True,motion_profile=1,last_observed_sequence=1)
def make():
 x=m.RegisterTransactionModel(dict(fixture_id='main-adversarial',identity=1,rate_codes=[1],sensor_profiles=[1],motion_profiles=[1],apply_blocks=[1],queue_capacity=2,clock_id='fixture-clock'));x.set_context(ctx());x.set_cdc(True,False);x.set_fixture_gates(True,True)
 for off,v in ((16,0x10000),(24,1),(28,0),(32,1)):x.write(off,v)
 x.write(20,0);x.block_boundary(1);return x
class CallbackMapping(Mapping):
 def __init__(self,data,callback):self.data=data;self.callback=callback;self.fired=False
 def __iter__(self):return iter(self.data)
 def __len__(self):return len(self.data)
 def __getitem__(self,key):
  if not self.fired:self.fired=True;self.callback()
  return self.data[key]
class Adversarial(unittest.TestCase):
 def test_callback_revocation_never_publishes(self):
  for name,action in [('STOP',lambda x:x.write(8,1)),('fault',lambda x:x.raise_fault(1)),('newcycle',lambda x:x.begin_capture(2)),('context',lambda x:x.set_context({**ctx(),'config_epoch':1,'request_seq':3})),('offline',lambda x:x.set_cdc(False,False)),('reset',lambda x:x.reset())]:
   with self.subTest(action=name):
    x=make();t=x.begin_capture(1);v=CallbackMapping(val(),lambda:action(x))
    try:x.complete_capture(t,v)
    except ValueError:pass
    self.assertEqual(x.read(12)&(8|16|512),0,'revoked callback republished capture')
    with self.assertRaises(ValueError):x.write(8,8)
 def test_new_session_and_boot_cannot_carry_enable_or_config(self):
  for change in ({'session':10},{'boot_digest':'c'*64}):
   with self.subTest(change=change):
    x=make();x.write(8,4);x.set_context({**ctx(),**change});self.assertEqual(x.read(12)&1025,1)
    with self.assertRaises(ValueError):x.write(8,4)
    with self.assertRaises(ValueError):x.begin_capture(1)
 def test_losing_gate_revokes_enabled_fixture(self):
  x=make();x.write(8,4);x.set_fixture_gates(False,True);self.assertEqual(x.read(12)&1025,1)
 def test_cdc_revokes_pending_even_before_any_capture(self):
  x=make();x.write(20,1);x.set_cdc(False,False);self.assertEqual(x.read(12)&256,0)
  x.block_boundary(1);self.assertEqual(x.inspect()['context']['config_epoch'],1)
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Adversarial));print(json.dumps({'tests':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'scope':'offline fixture lifecycle only'}));raise SystemExit(not r.wasSuccessful())
