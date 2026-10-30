"""Default closed. Explicit software inspection/fake execution only."""
import argparse
import json
from pathlib import Path
from host103 import inspect_plan, physical_start, sha, strict_json, need

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]

def load_fixture():
    f=HERE/'fixtures'
    pins=strict_json((f/'pins.json').read_bytes())
    for name,row in pins['fixture_pins'].items():
        raw=(f/name).read_bytes();expected=row['copy']
        need(len(raw)==expected['bytes'] and sha(raw)==expected['sha256'],'frozen first104/106 fixture '+name)
    plan=strict_json((f/'plan.json').read_bytes());inspect_plan(plan)
    return plan,[(f/('frame%03d.bin'%i)).read_bytes() for i in range(4)],[(f/('companion%03d.json'%i)).read_bytes() for i in range(4)],pins

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',nargs='?',choices=('inspect','fake','physical'),default='physical')
    p.add_argument('--out',type=Path)
    args=p.parse_args()
    if args.mode=='physical':
        print(json.dumps(physical_start()));return 2
    plan,frames,companions,pins=load_fixture()
    if args.mode=='inspect':
        print(json.dumps(inspect_plan(plan)));return 0
    need(args.out is not None,'explicit new fake output directory required')
    from fake_csr103 import FakeExecution
    result=FakeExecution(plan,frames,companions,args.out).run(ROOT)
    print(json.dumps({'kind':result['kind'],'status':result['status'],'errors':result['errors'],
                      'result':str(args.out/'RESULT.json'),'physical_result':False}))
    return 0 if not result['errors'] else 1

if __name__=='__main__':raise SystemExit(main())
