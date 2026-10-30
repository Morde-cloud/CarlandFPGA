"""One NEW focused SOFTWARE_FAKE_CSR set; run only after explicit main START."""
import argparse
import json
from pathlib import Path
from host103 import DEFAULT_LIMITS, Refused, canonical, inspect_hwh, physical_start, need
from fake_csr103 import FakeCSR, FakeExecution
from cli103 import load_fixture, ROOT

def expect_refused(fn):
    try:fn()
    except (Refused,ValueError):return
    raise AssertionError('expected refusal')

def audit(fake):
    entries=[]
    for phase in ('work','cleanup'):
        path=fake.evidence.root/(phase+'.jsonl')
        if path.exists():entries.extend(json.loads(line) for line in path.read_text().splitlines())
    intents=[x for x in entries if x.get('event')=='INTENT']
    outcomes=[x for x in entries if x.get('event') in ('RETURN','EFFECT_UNKNOWN')]
    need(len(intents)==len(outcomes)==len(fake.bus.calls),'exact pre-effect intents/outcomes')
    need([x['id'] for x in intents]==[x['id'] for x in outcomes],'exact attempt association')
    need(fake.bus.commands.count(1)<=1 and fake.bus.commands.count(5)<=1,'no ARM/CANCEL replay')
    need(all(x not in (6,7) for x in fake.bus.commands),'no clear fault/FIFO')
    need(all(kind!='write' or offset not in (0x00c,) for kind,offset,value in fake.bus.calls),'no G05 write')
    need(sum(p.stat().st_size for p in fake.evidence.root.iterdir() if p.is_file())<=8388608,'case evidence bound')

def run(out):
    out.mkdir(parents=True,exist_ok=False)
    plan,frames,companions,pins=load_fixture()
    results=[]
    # No handle/proof/callback inspection can open physical access.
    class ForbiddenHandle:
        def __getattribute__(self,name):raise AssertionError('physical path inspected forged handle')
    bus=FakeCSR(plan,frames)
    closed=physical_start(ForbiddenHandle(),verified=True,provider=lambda:bus)
    need(closed['input_status']=='A_ORIGINAL_PROVIDER_UNAVAILABLE' and not bus.calls,'missing physical proof zero MMIO')
    bad=out/'wrong.hwh';bad.write_bytes(b'<EDKSYSTEM VIVADOVERSION="wrong"/>')
    expect_refused(lambda:inspect_hwh(bad,{},plan['build_id'],ROOT,pins['source_pins']))
    need(not bus.calls,'wrong HWH zero MMIO')
    results.append({'case':'wrongHWH_and_missing_physical_proof','passed':True,'MMIO_attempts':0,'physical':closed})
    prearm_rows=[]
    for scenario in ('dirty_prearm','wrong_identity','wrong_build'):
        prearm=FakeExecution(plan,frames,companions,out/scenario,scenario=scenario)
        r=prearm.run(ROOT);audit(prearm)
        need(r['errors'] and not r['arm_effect_attempted'] and not r['cancel_consumed'] and not r['collect_consumed'],'pre-ARM refusal has no owned cleanup/collect')
        need(not any(call[0]=='write' for call in prearm.bus.calls),'pre-ARM refusal zero writes')
        if scenario=='dirty_prearm':need(list(prearm.bus.fifo)==[0xaa],'unrelated prior FIFO preserved')
        prearm_rows.append({'scenario':scenario,'result':r})
    for key in ('wire','retained','frames','nominal_parent_seconds'):
        limits=dict(DEFAULT_LIMITS);limits[key]-=1
        expect_refused(lambda:FakeExecution(plan,frames,companions,out/('invalid-limit-'+key),limits=limits))
        need(not (out/('invalid-limit-'+key)).exists(),'immutable limit refusal precedes output/effects')
    results.append({'case':'preARM_refusals_and_fixed_scope','passed':True,'rows':prearm_rows})
    arm_unknown=FakeExecution(plan,frames,companions,out/'unknown_arm',scenario='unknown_arm')
    r=arm_unknown.run(ROOT);audit(arm_unknown)
    need(r['unknown_effects'] and r['arm_effect_attempted'] and arm_unknown.bus.commands.count(1)==1 and arm_unknown.bus.commands.count(5)==1,'owned ambiguous ARM retains unknown and one cleanup')
    results.append({'case':'ambiguous_ARM_owned_cleanup','passed':True,'result':r})
    normal=FakeExecution(plan,frames,companions,out/'normal')
    r=normal.run(ROOT);audit(normal)
    need(not r['errors'] and r['decoded']['frames']==4,'one fake scan decoded')
    need(bytes(normal.sequence.confirmed_prefix)==b''.join(frames),'peek valid zero preserved exactly')
    need(0 in normal.sequence.confirmed_prefix,'fixture includes valid byte zero')
    need(normal.bus.commands.count(1)==1 and normal.bus.commands.count(2)==4 and normal.bus.commands.count(3)==4 and normal.bus.commands.count(4)==4,'exact scan command counts')
    need(normal.bus.commands.count(8)==len(b''.join(frames)),'one POP per byte')
    before=len(normal.bus.calls)
    expect_refused(normal.start);expect_refused(normal.collect)
    need(len(normal.bus.calls)==before,'duplicate start/collect zero new effects')
    results.append({'case':'consumed_start_peekzero_exact_collect_duplicates','passed':True,'result':r})
    partial=FakeExecution(plan,frames,companions,out/'partial',scenario='partial_cancel')
    r=partial.run(ROOT);audit(partial)
    need(r['errors'] and r['confirmed_prefix_bytes']==1 and r['decoded'] is None and r['collect_consumed'],'partial cancel retained once')
    need(bytes(partial.sequence.confirmed_prefix)==frames[0][:1] and partial.bus.commands.count(5)==1,'exact partial prefix and one cancel')
    results.append({'case':'partial_cancel','passed':True,'result':r})
    overflow=FakeExecution(plan,frames,companions,out/'overflow',scenario='overflow')
    r=overflow.run(ROOT);audit(overflow)
    need(r['errors'] and overflow.bus.fault==2 and r['decoded'] is None,'sticky overflow not success')
    need(0<r['confirmed_prefix_bytes']<4096 and len(overflow.bus.fifo)>0,'bounded drain leaves unread FIFO')
    need(r['confirmed_prefix_bytes']<=overflow.bus.pop_id<=r['confirmed_prefix_bytes']+1,'confirmed overflow prefix and at most one pending POP')
    if overflow.bus.pop_id!=r['confirmed_prefix_bytes']:
        need(r['pending_observed_byte'] is not None and r['unknown_effects'],'unconfirmed overflow POP preserved')
    results.append({'case':'overflow_cleanup_evidence_exhaustion','passed':True,'result':r})
    unknown=FakeExecution(plan,frames,companions,out/'unknown',scenario='unknown_pop')
    r=unknown.run(ROOT);audit(unknown)
    need(r['unknown_effects'] and r['pending_observed_byte']==frames[0][0] and r['confirmed_prefix_bytes']==0,'ambiguous POP evidence')
    need(unknown.bus.commands.count(8)==1 and unknown.bus.pop_id==1,'unknown POP not replayed')
    results.append({'case':'ambiguous_POP_consumes_collection','passed':True,'result':r})
    timed=FakeExecution(plan,frames,companions,out/'time',scenario='time_pop')
    r=timed.run(ROOT);audit(timed)
    need(r['errors'] and r['unknown_effects'] and r['confirmed_prefix_bytes']==0 and timed.bus.pop_id==1,'deadline preserves unconfirmed POP')
    need(timed.bus.commands.count(8)==1 and timed.bus.commands.count(5)==1,'deadline no retry; separate cleanup')
    results.append({'case':'work_time_budget_partial_unknown','passed':True,'result':r})
    limits=dict(DEFAULT_LIMITS);limits['work_evidence']=512*1024
    limited=FakeExecution(plan,frames,companions,out/'evidence',limits=limits)
    r=limited.run(ROOT);audit(limited)
    need(r['errors'] and 0<r['confirmed_prefix_bytes']<len(b''.join(frames)) and len(limited.bus.fifo)>0,'work evidence bound retains prefix and unread FIFO')
    need(limited.sequence.collect_consumed and limited.bus.commands.count(5)==1,'no second drain after evidence refusal')
    results.append({'case':'work_evidence_budget_partial','passed':True,'result':r})
    summary={'status':'FOCUSED_FAKE_CONTROLS_COMPLETED_MAIN_REVIEW_PENDING','kind':'SOFTWARE_FAKE_CSR',
             'cases':results,'physical_result':False,'current_source_eligible':False,'core_ran':False,'command':None,
             'old_groups_reexecuted':False,'board':False,'acceptance':False}
    (out/'SUMMARY.json').write_bytes(canonical(summary))
    print(json.dumps({'cases':len(results),'status':summary['status'],'kind':summary['kind']}))
    return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    raise SystemExit(run(p.parse_args().out))
