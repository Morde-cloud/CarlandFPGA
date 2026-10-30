"""NEW81 source controls; pure synthetic math, no ADC/analog acceptance."""
import copy,importlib.util,json,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[3]
s=importlib.util.spec_from_file_location('adc81',P/'tools/diagnostic/r04_adc79/adc_pair_evaluator.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
BASE=9007199254740993

def fixture():
    ctx=dict(tag=(1<<61)+9,epoch=(1<<60)+5,boot_id='original-BOOT-text',source_id='original-source-text',clock_id='original-QPC-ns',
             operation_id='SYNTHETIC-R04-81',session_id='original-session-文本',request_hash='ab'*32,root_context=dict(generation=(1<<59)+3))
    def record(i,t,a0):
        return dict(sample_id=i,acquisition_qpc=BASE+t,source_qpc=BASE+t,context=copy.deepcopy(ctx),
                    channel_indices=[0,1,2,3],channels=[a0,5000,6000,8192],quality=254,quality_eligible=True)
    return dict(schema=m.SCHEMA,mode=m.MODE,now_qpc_ns=BASE+500,
      calibration=dict(calibration_id='synthetic-calibration',full_scale_code=65535,a0_offset_code=0,a3_offset_code=0,qpc_hz=1000000000,clock_id=ctx['clock_id']),
      digital_receipt=dict(spi_complete=True,digital_complete_qpc=BASE+200,context=copy.deepcopy(ctx)),
      baseline_before=[record(1,100,8192)],after=[record(2,300,32768)])

def evaluate(f):return m.evaluate_synthetic_fixture(json.dumps(f,ensure_ascii=False))

class Controls(unittest.TestCase):
    def test_low_before_A3_high_raw_after_is_valid_synthetic_only(self):
        r=evaluate(fixture());self.assertEqual(r['status'],'SYNTHETIC_RATIO_AVAILABLE')
        self.assertEqual((r['ratio_numerator'],r['ratio_denominator']),(32768,8192))
        self.assertEqual((r['baseline_ratio_numerator'],r['baseline_ratio_denominator']),(8192,8192))
        self.assertIsNone(r['measured_gain_actual']);self.assertFalse(r['physical_acceptance']);self.assertFalse(r['commands_emitted'])
        raw=json.loads(r['record_ledger'][0]['canonical_json']);self.assertEqual(raw['acquisition_qpc'],BASE+100)
        self.assertEqual(raw['context'],fixture()['baseline_before'][0]['context']);self.assertEqual(raw['quality'],254)
    def test_now_age_not_only_acquisition_age(self):
        f=fixture();f['now_qpc_ns']=BASE+100000101
        self.assertEqual(evaluate(f)['reason'],'SOURCE_STALE_BEYOND_100MS')
    def test_100ms_boundary_inclusive(self):
        f=fixture();f['now_qpc_ns']=BASE+100000100
        self.assertEqual(evaluate(f)['status'],'SYNTHETIC_RATIO_AVAILABLE')
    def test_future_and_QPC_unit_domain(self):
        f=fixture();f['now_qpc_ns']=BASE+299;self.assertEqual(evaluate(f)['status'],'REFUSED')
        f=fixture();f['calibration']['qpc_hz']=1000;self.assertEqual(evaluate(f)['status'],'REFUSED')
    def test_valid_missing(self):
        for key in ['calibration','digital_receipt','now_qpc_ns']:
            f=fixture();f[key]=None;self.assertEqual(evaluate(f)['status'],'UNAVAILABLE')
        f=fixture();f['after']=[];self.assertEqual(evaluate(f)['status'],'UNAVAILABLE')
    def test_duplicate_even_without_receipt_or_after(self):
        f=fixture();f['digital_receipt']=None;f['after']=[];f['baseline_before']*=2
        self.assertEqual(evaluate(f)['reason'],'DUPLICATE_SAMPLE_ID')
    def test_context_mismatch_even_missing_calibration(self):
        f=fixture();f['calibration']=None;f['after'][0]['context']['root_context']['generation']+=1
        self.assertEqual(evaluate(f)['status'],'REFUSED')
    def test_wrong_clock_even_without_receipt(self):
        f=fixture();f['digital_receipt']=None;f['calibration']['clock_id']='other-original-clock'
        self.assertEqual(evaluate(f)['status'],'REFUSED')
    def test_invalid_order(self):
        for value in [BASE+199,BASE+200]:
            f=fixture();f['after'][0]['acquisition_qpc']=value;f['after'][0]['source_qpc']=value
            self.assertEqual(evaluate(f)['status'],'REFUSED')
        f=fixture();f['after'][0]['source_qpc']=BASE+301;self.assertEqual(evaluate(f)['status'],'REFUSED')
    def test_opaque_quality_and_explicit_ineligible(self):
        f=fixture();f['after'][0]['quality_eligible']=False;self.assertEqual(evaluate(f)['status'],'UNAVAILABLE')
        f=fixture();f['after'][0]['quality_eligible']=1;self.assertEqual(evaluate(f)['status'],'REFUSED')
    def test_zero_A3_saturation_and_no_fake_ratio(self):
        for index,value in [(3,0),(3,65535),(0,65535)]:
            f=fixture();f['after'][0]['channels'][index]=value;r=evaluate(f)
            self.assertEqual(r['status'],'UNAVAILABLE');self.assertIsNone(r['ratio_numerator'])
    def test_only_A0_after_window_raw_code_not_corrected(self):
        f=fixture();f['after'][0]['channels'][0]=15000;f['calibration']['a0_offset_code']=5000
        self.assertEqual(evaluate(f)['status'],'SYNTHETIC_RATIO_AVAILABLE')
        f=fixture();f['after'][0]['channels'][0]=8192;self.assertEqual(evaluate(f)['status'],'UNAVAILABLE')
    def test_bool_float_overflow_rejected(self):
        for value in [True,1.5,1<<63]:
            f=fixture();f['after'][0]['acquisition_qpc']=value;self.assertEqual(evaluate(f)['status'],'REFUSED')
        f=fixture();f['digital_receipt']['context']['tag']=True;self.assertEqual(evaluate(f)['status'],'REFUSED')
    def test_strict_channels_and_record_keys(self):
        f=fixture();f['after'][0]['channel_indices']=[0,3];self.assertEqual(evaluate(f)['status'],'REFUSED')
        f=fixture();f['after'][0]['unknown']=1;self.assertEqual(evaluate(f)['status'],'REFUSED')
    def test_capacity_no_eviction(self):
        f=fixture();f['after']*=16;self.assertEqual(evaluate(f)['reason'],'RECORD_CAPACITY_EXCEEDED')
    def test_json_duplicates_nan_custom_text(self):
        self.assertEqual(m.evaluate_synthetic_fixture('{"x":1,"x":2}')['status'],'REFUSED')
        self.assertEqual(m.evaluate_synthetic_fixture('{"x":NaN}')['status'],'REFUSED')
        self.assertEqual(m.evaluate_synthetic_fixture(object())['status'],'REFUSED')
    def test_incomplete_digital_receipt_is_not_gain_application(self):
        f=fixture();f['digital_receipt']['spi_complete']=False;self.assertEqual(evaluate(f)['status'],'UNAVAILABLE')
    def test_production_unavailable(self):
        r=m.production_entry();self.assertEqual(r['status'],'INPUT_UNAVAILABLE');self.assertIsNone(r['ratio_numerator'])
        self.assertFalse(r['synthetic']);self.assertFalse(r['commands_emitted'])

if __name__=='__main__':unittest.main(verbosity=2)
