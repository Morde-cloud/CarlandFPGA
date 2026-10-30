"""Focused software controls for B75; synthetic consistency, never Root proof."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

PRODUCT = Path(__file__).resolve().parents[3]
ADAPTER = PRODUCT/'tools/diagnostic/offboard_control75/control_adapter.py'
spec=importlib.util.spec_from_file_location('b75_adapter',ADAPTER)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CONTEXT=dict(operation_id='SYNTHETIC-B75-long-operation-not-truncated',kernel_boot_id='SYNTHETIC-boot-1',
    session_id='full-original-session-string',generation=(1<<62)+123,epoch=(1<<61)+3,
    trigger_id=(1<<60)+5,clock_domain_id='original-synthetic-QPC',action_id='original-synthetic-action',
    request_hash='a'*64,build_manifest_sha256='b'*64,source_record_sha256='c'*64,capture_sha256='d'*64,
    tested_commit='e'*40,tag=(1<<60)+15,request_seq=17,capture_seq=19,source_admission_index=23)
DECISION=dict(yaw_q=100,pitch_q=-200,profile=1,speed=20,ttl_ms=100)
NOW=(1<<62)+54321


def queued():
    a=m.ControlAdapter.synthetic_fixture(CONTEXT)
    k=a.queue(original_source_qpc_ns=NOW-99,now_qpc_ns=NOW,decision=DECISION)
    return a,k


def association(a,k):
    r=a.records[k]
    return dict(context=r['context'],identity_words=r['identity_words'],command_id=r['command_id'],transport_tag=r['transport_tag'])


def capture(a,k,seq=1):
    r=a.records[k]; d=r['decision']; w=[0]*32
    w[0:6]=[seq,r['command_id'],r['transport_tag'],d['speed']<<8|d['profile'],(d['pitch_q']&65535)<<16|(d['yaw_q']&65535),d['ttl_ms']]
    for i,v in [(6,100),(8,5000100),(10,2000110)]:w[i]=v
    w[12:18]=[1000000]*3+[125800,123400,35000]
    for i in range(3):w[18+2*i]=1000000;w[24+2*i]=2000000
    w[30:]=[r['identity_words'][12],0x47303550]
    return w


class Controls(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def sent(self):
        a,k=queued();a.send_once(k,now_qpc_ns=NOW,intent_path=self.root/'intent',send=lambda regs:None)
        return a,k
    def applied(self):
        a,k=self.sent();a.digital_fact(k,**association(a,k),fact='ACCEPTED')
        a.digital_fact(k,**association(a,k),fact='APPLIED',applied_tick=100,deadline_tick=5000100)
        return a,k
    def test_default_production_unavailable(self):
        a=m.ControlAdapter();self.assertIsNone(a.production_input(real_BOOT=True,calibration=True)['command'])
        with self.assertRaises(m.Refused):a.queue(original_source_qpc_ns=NOW,now_qpc_ns=NOW,decision=DECISION)
    def test_full_context_separate_handle_no_lowbits(self):
        a,k=queued();old=a.identity_words;new=dict(CONTEXT,generation=CONTEXT['generation']+(1<<32))
        a.new_epoch(new);self.assertTrue(set(old).isdisjoint(a.identity_words));self.assertEqual(a.bindings[0]['context'],CONTEXT)
        self.assertEqual(a.records[k]['state'],'CANCELLED_UNSENT')
    def test_unknown_before_sideeffect_and_no_replay(self):
        a,k=queued();seen=[]
        def fail(regs):
            self.assertEqual(a.records[k]['state'],'SEND_UNKNOWN')
            self.assertEqual(json.loads((self.root/'intent').read_text())['state'],'SEND_UNKNOWN')
            seen.append(regs);raise OSError('synthetic transport outcome unknown')
        with self.assertRaises(OSError):a.send_once(k,now_qpc_ns=NOW,intent_path=self.root/'intent',send=fail)
        with self.assertRaises(m.Refused):a.send_once(k,now_qpc_ns=NOW,intent_path=self.root/'retry',send=fail)
        self.assertEqual(len(seen),1)
    def test_duplicate_intent_path_is_not_replayed(self):
        a,k=queued();(self.root/'intent').write_bytes(b'old unknown intent')
        with self.assertRaises(FileExistsError):a.send_once(k,now_qpc_ns=NOW,intent_path=self.root/'intent',send=lambda _:self.fail('replay'))
        self.assertEqual(a.records[k]['state'],'SEND_UNKNOWN')
    def test_stale_at_queue_and_before_send(self):
        a,k=queued()
        with self.assertRaises(m.Refused):a.queue(original_source_qpc_ns=NOW-100000001,now_qpc_ns=NOW,decision=DECISION)
        with self.assertRaises(m.Refused):a.send_once(k,now_qpc_ns=NOW+100000000,intent_path=self.root/'intent',send=lambda _:self.fail('stale send'))
        self.assertFalse(a.records[k]['send_attempted'])
    def test_wrong_identity_rejected(self):
        a,k=self.sent();x=association(a,k);x['context']=dict(CONTEXT,session_id='other')
        with self.assertRaises(m.Refused):a.digital_fact(k,**x,fact='ACCEPTED')
        x=association(a,k);x['transport_tag']+=1
        with self.assertRaises(m.Refused):a.digital_fact(k,**x,fact='ACCEPTED')
    def test_repeat_result_and_ack_never_renew_TTL(self):
        a,k=self.applied();w=capture(a,k)
        for _ in range(2):a.digital_fact(k,**association(a,k),fact='CAPTURED',words=w)
        ack=self.ack(a,k)
        for _ in range(2):a.original_receipt(k,ack)
        self.assertEqual(a.records[k]['deadline_tick'],5000100)
        a.digital_fact(k,**association(a,k),fact='APPLIED',applied_tick=100,deadline_tick=5000100)
        self.assertEqual(a.records[k]['state'],'DIGITAL_CAPTURED')
        with self.assertRaises(m.Refused):a.digital_fact(k,**association(a,k),fact='APPLIED',applied_tick=101,deadline_tick=5000101)
        w[15]+=1
        with self.assertRaises(m.Refused):a.digital_fact(k,**association(a,k),fact='CAPTURED',words=w)
    def ack(self,a,k):
        r=a.records[k];return dict(kind='HOST_RECEIPT_ACK',evidence_kind=m.SYNTHETIC,context=r['context'],command_id=r['command_id'],transport_tag=r['transport_tag'],receipt_id='synthetic-original-receipt')
    def retired(self,a,k):
        return dict(self.ack(a,k),kind='ORIGINAL_ACTION_RETIRED',action_id='synthetic-original-action',world_motion_stopped=True)
    def test_ack_lost_stop_is_not_action_retirement(self):
        a,k=self.applied();a.digital_fact(k,**association(a,k),fact='STOP',terminal_status=3,pwm=0,fault=6,tick=200)
        self.assertTrue(a.records[k]['stop_required']);self.assertIsNone(a.records[k]['host_receipt_ack'])
        with self.assertRaises(m.Refused):a.retire_original_action(k,self.retired(a,k))
        a.original_receipt(k,self.ack(a,k));a.retire_original_action(k,self.retired(a,k))
        self.assertFalse(a.records[k]['stop_required'])
    def test_new_boot_invalidates_without_inventing_stop(self):
        a,k=self.applied();a.new_epoch(dict(CONTEXT,kernel_boot_id='new-synthetic-BOOT'))
        self.assertEqual(a.records[k]['state'],'STOP_REQUIRED');self.assertIsNone(a.records[k]['digital_stop'])
        with self.assertRaises(m.Refused):a.digital_fact(k,**association(a,k),fact='CAPTURED',words=capture(a,k))
        # Exact old STOP evidence is still necessary and can reconcile old work.
        a.digital_fact(k,**association(a,k),fact='STOP',terminal_status=3,pwm=0,fault=6,tick=201)
        self.assertTrue(a.records[k]['stop_required'])
        other=a.queue(original_source_qpc_ns=NOW,now_qpc_ns=NOW,decision=DECISION)
        with self.assertRaises(m.Refused):a.send_once(other,now_qpc_ns=NOW,intent_path=self.root/'new-epoch',send=lambda _:self.fail('old retirement unresolved'))
    def test_queued_held_cancel_and_data_quiescent(self):
        a,k=queued();a.hold(k);a.cancel(k,'explicit cancel')
        with self.assertRaises(m.Refused):a.send_once(k,now_qpc_ns=NOW,intent_path=self.root/'intent',send=lambda _:None)
        self.assertIsNone(a.records[k]['digital_stop']);self.assertIsNone(a.records[k]['original_action_retirement'])
    def test_expiry_is_digital_only(self):
        a,k=self.applied();a.digital_fact(k,**association(a,k),fact='STOP',terminal_status=3,pwm=0,fault=2,tick=5000100)
        self.assertIsNone(a.records[k]['host_receipt_ack']);self.assertTrue(a.records[k]['stop_required'])
    def test_source73_structural_view_retained(self):
        a=m.ControlAdapter();view=dict(status='STOP',core_ran=False,command=None,source_identity=CONTEXT,
            points=[dict(original_acquisition_qpc_ns=NOW,original_source_qpc_ns=NOW-99,decoded_value=65535)])
        out=a.ingest_semantic(dict(schema='B74_SEMANTIC_FIXTURE_V1',evidence_kind=m.SYNTHETIC,semantic_view=view))
        self.assertEqual(out['structural_observation'],view);self.assertIsNone(out['command'])
    def test_strict_handle_type_and_schema(self):
        a,k=self.sent();x=association(a,k);x['identity_words']=list(x['identity_words']);x['identity_words'][0]=True
        with self.assertRaises(m.Refused):a.digital_fact(k,**x,fact='ACCEPTED')
        with self.assertRaises(m.Refused):m.ControlAdapter.synthetic_fixture(dict(operation_id='partial'))
        external=a.context;external['session_id']='changed outside'
        self.assertEqual(a.context,CONTEXT)
    def test_capacities_refuse_without_eviction(self):
        a,k=queued()
        for _ in range(m.MAX_RECORDS-1):a.queue(original_source_qpc_ns=NOW,now_qpc_ns=NOW,decision=DECISION)
        with self.assertRaises(m.Refused):a.queue(original_source_qpc_ns=NOW,now_qpc_ns=NOW,decision=DECISION)
        self.assertEqual(len(a.records),m.MAX_RECORDS)
        for i in range(m.MAX_BINDINGS-1):a.new_epoch(dict(CONTEXT,epoch=i))
        with self.assertRaises(m.Refused):a.new_epoch(dict(CONTEXT,epoch=99))
        self.assertEqual(len(a.bindings),m.MAX_BINDINGS)
        a,k=self.applied()
        for seq in range(1,m.MAX_CAPTURES+1):a.digital_fact(k,**association(a,k),fact='CAPTURED',words=capture(a,k,seq))
        with self.assertRaises(m.Refused):a.digital_fact(k,**association(a,k),fact='CAPTURED',words=capture(a,k,m.MAX_CAPTURES+1))
        self.assertEqual(len(a.records[k]['captures']),m.MAX_CAPTURES)


if __name__=='__main__':unittest.main(verbosity=2)
