"""NEW87 focused unmodified A-reference calls, no original suite or hardware."""
import argparse,json,sys
from fractions import Fraction
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import boot_profile

def plain(v):
    if isinstance(v,Fraction):return str(v)
    if isinstance(v,dict):return {k:plain(a) for k,a in v.items()}
    if isinstance(v,list):return [plain(a) for a in v]
    return v
def main():
    a=argparse.ArgumentParser();a.add_argument('--phase',choices=['counterexample','adjacent'],required=True);a.add_argument('--doc',required=True);a.add_argument('--out',required=True);n=a.parse_args()
    doc=json.loads(Path(n.doc).read_bytes());assert doc['hardware_enable_eligible'] is False
    allcases=[('fast_early_deadline','fast_9600',0,100),('fast_at_deadline','fast_9600',210,210),('fast_ready_before_slot_but_after_deadline','fast_9600',100,200),('stress_early_deadline','stress_300',0,2000),('stress_at_deadline','stress_300',2050,2050)]
    if n.phase=='adjacent':allcases=[('fast_valid_before_slot','fast_9600',209,250),('stress_valid_before_slot','stress_300',2049,3000),('fast_defer_before_deadline','fast_9600',211,711),('fast_deferred_equals_deadline','fast_9600',211,710),('fast_already_late_and_expired','fast_9600',1000,900)]
    results=[]
    for name,profile,ready,deadline in allcases:
        result=boot_profile.late_candidate_action(doc,profile,ready,deadline)
        if result['action']=='send':start=Fraction(result['start_ms'])
        elif result['action']=='defer':start=Fraction(result['deferred_start_ms'])
        else:start=None
        violation=start is not None and start>=deadline
        results.append({'case':name,'profile':profile,'ready_ms':ready,'deadline_ms':deadline,'actual':plain(result),'would_start_at_or_after_deadline':violation,'reference_only_no_actual_send':True})
    violations=sum(r['would_start_at_or_after_deadline'] for r in results)
    if n.phase=='counterexample':assert violations==5
    else:
        assert violations==0
        assert [r['actual']['action'] for r in results]==['send','send','defer','stop','stop']
    out={'phase':n.phase,'source_commit':'aeac3c8d0321c35d497d2abee39897c978d586ca','actual_function':'unmodified boot_profile.late_candidate_action','cases':results,'observed_violations':violations,'profile_hardware_enable_eligible':False,'actual_send':False,'product_acceptance':False}
    with Path(n.out).open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(out,ensure_ascii=False))
    return 4 if n.phase=='counterexample' else 0
if __name__=='__main__':raise SystemExit(main())
