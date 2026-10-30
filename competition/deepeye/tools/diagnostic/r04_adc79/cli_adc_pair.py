"""Bounded synthetic file evaluator; status is a process result, never hardware I/O."""
import argparse,json,sys
from pathlib import Path
from adc_pair_evaluator import evaluate_synthetic_fixture,production_entry,MAX_JSON_BYTES
def main():
    a=argparse.ArgumentParser();a.add_argument('--input',type=Path);a.add_argument('--production',action='store_true');a.add_argument('--output',type=Path,required=True);n=a.parse_args()
    if n.production:
        result=production_entry()
    else:
        if n.input is None:a.error('explicit synthetic input required')
        with n.input.open('rb') as f:raw=f.read(MAX_JSON_BYTES+1)
        if len(raw)>MAX_JSON_BYTES:raise ValueError('input byte limit')
        result=evaluate_synthetic_fixture(raw.decode('utf-8'))
    encoded=(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    if len(encoded)>1024*1024:raise ValueError('output byte limit')
    with n.output.open('xb') as f:f.write(encoded)
    print(json.dumps({'status':result['status'],'physical_acceptance':False,'commands_emitted':False}))
    return 0 if result['status']=='SYNTHETIC_RATIO_AVAILABLE' else 2 if result['status']=='REFUSED' else 3
if __name__=='__main__':sys.exit(main())
