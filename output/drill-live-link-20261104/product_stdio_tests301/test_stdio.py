from pathlib import Path
import importlib.util
import io
import json
import sys
import tempfile
import unittest

D=Path(__file__).resolve().parents[1];sys.path.insert(0,str(D))
spec=importlib.util.spec_from_file_location('fixture301',D/'product_uart_tests284/test_product_uart_service.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
from product_uart_stdio import ExistingStreamSession, parse_line, serve_loaded_product

class Controls(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.clock=f.Clock();self.root=f.FakeRoot()
 def tearDown(self):
  if hasattr(self,'service'):
   try:self.service.close()
   except Exception:pass
  self.temp.cleanup()
 def attach(self,diagnostic=False):
  if diagnostic:self.root.mmio.feedback=False;self.root.mmio.result=3
  self.service=f.service.ProductUartService.attach(self.root,f.service.Profile(self.root.binding,'stdio301','MANUAL'),
   f.service.BTransfer('op284','stdio301','observed301',0,'7'*64,'DIAGNOSTIC_ONLY' if diagnostic else 'MOTION_READY'),Path(self.temp.name).resolve(),clock=self.clock,sleep=self.clock.sleep)
  return self.service
 def request(self,rid,op,**kw):return dict(session=self.service._session.session_id,request_id=rid,expires_ms=500,op=op,**kw)
 def test_legacy_handshake_diagnostic_only_and_STOP_reuse_on_EOF(self):
  s=self.attach(True);out=io.StringIO();requests=[self.request(1,'status'),self.request(2,'stop'),self.request(3,'stop')]
  self.assertEqual(serve_loaded_product(s,io.StringIO(''.join(json.dumps(x)+'\n' for x in requests)),out),0)
  rows=[json.loads(x) for x in out.getvalue().splitlines()]
  self.assertEqual(rows[0]['event'],'ready');self.assertEqual(rows[0]['service_event'],'uart_connected')
  self.assertIs(rows[0]['mcu_feedback_ready_observed'],False);self.assertIs(rows[0]['actuator_READY_authorized'],False)
  self.assertEqual([x['request_id'] for x in rows[1:]],[1,2,3]);self.assertTrue(rows[-1]['rpc_stop_result_reused'])
  self.assertEqual(rows[-1]['status']['seq'],rows[-2]['status']['seq']);self.assertFalse(rows[-1]['device_command_replayed'])
  self.assertEqual([x[3] for x in self.root.mmio.frames],[3,4,4,3])
 def test_original_expiry_is_not_regenerated_for_remote_pose(self):
  s=self.attach();stream=ExistingStreamSession(s);req=self.request(1,'pose',yaw_deg=1,pitch_deg=2,move_ms=500)
  req['expires_ms']=1;self.clock.now+=2
  with self.assertRaises(Exception):stream.dispatch(req)
  s.close();self.assertEqual([x[3] for x in self.root.mmio.frames],[3,4,3]);self.assertEqual(req['expires_ms'],1)
 def test_valid_pose_preserves_remote_request_and_expiry(self):
  s=self.attach();stream=ExistingStreamSession(s);req=self.request(19,'pose',yaw_deg=1,pitch_deg=2,move_ms=500,source_seq=7,observation_seq=8)
  before=dict(req);reply=stream.dispatch(req);self.assertEqual(req,before);self.assertEqual(reply['request_id'],19)
  self.assertEqual(self.root.mmio.frames[-1][3],2);self.assertEqual(reply['status']['target_yaw_cd'],100)
  s.close();self.assertEqual(sum(x[3]==3 for x in self.root.mmio.frames),2)
 def test_diagnostic_cannot_promote_motion_or_motor_permission(self):
  s=self.attach(True);stream=ExistingStreamSession(s)
  with self.assertRaises(Exception):stream.dispatch(self.request(1,'pose',yaw_deg=1,pitch_deg=1))
  s.close();self.assertFalse(any(x[3] in (1,2,5) for x in self.root.mmio.frames))
 def test_duplicate_JSON_or_nonfinite_closes_with_one_STOP(self):
  for line in ('{"op":"status","op":"motor"}', '{"speed_pct":NaN}'):
   with self.subTest(line=line),self.assertRaises(Exception):parse_line(line)
  s=self.attach();out=io.StringIO();code=serve_loaded_product(s,io.StringIO('{"op":"status","op":"motor"}\n'),out)
  self.assertEqual(code,1);self.assertEqual([x[3] for x in self.root.mmio.frames],[3,4,3])
  self.assertEqual(json.loads(out.getvalue().splitlines()[-1])['event'],'error')
 def test_cached_STOP_does_not_refresh_device_evidence_clock(self):
  s=self.attach();stream=ExistingStreamSession(s);first=stream.dispatch(self.request(1,'stop'));self.clock.now+=1
  second=stream.dispatch(self.request(2,'stop'));self.assertEqual(first['clock_ms'],second['clock_ms'])
  self.assertEqual(first['status'],second['status']);self.assertEqual(second['request_id'],2);self.assertTrue(second['rpc_stop_result_reused'])
  s.close();self.assertEqual([x[3] for x in self.root.mmio.frames],[3,4,3])
 def test_oversized_blank_line_read_is_bounded_before_strip_and_STOPS_once(self):
  class BoundedReader(io.StringIO):
   def __init__(self):super().__init__(' '*9000+'\n');self.limits=[]
   def __iter__(self):raise AssertionError('unbounded line iteration')
   def readline(self,size=-1):
    if size!=8193:raise AssertionError('bounded readline8193 required')
    self.limits.append(size);return super().readline(size)
  s=self.attach();reader=BoundedReader();out=io.StringIO()
  self.assertEqual(serve_loaded_product(s,reader,out),1)
  self.assertEqual(reader.limits,[8193])
  self.assertEqual([x[3] for x in self.root.mmio.frames],[3,4,3])
  self.assertEqual(json.loads(out.getvalue().splitlines()[-1])['error'],'bounded JSON command line')

if __name__=='__main__':unittest.main(verbosity=2)
