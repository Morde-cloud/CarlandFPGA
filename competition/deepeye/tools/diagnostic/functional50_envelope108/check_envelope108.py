"""ONE later main-released40s attempt. Only two NEW sampled-guard controls."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

MAIN='01a18824-4172-74e2-a13f-f3e3d1e3ed99'
WORK='B-DEEPEYE-FUNCTIONAL50-PROCESS-GUARD-20261031-108'
CONTRACT='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.write('\n')
def need(ok,why):
    if not ok:raise AssertionError(why)


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--pins',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();release=json.loads(a.release.read_text('utf-8-sig'));pins=json.loads(a.pins.read_text('utf-8'))
    need(release.get('schema')=='FUNCTIONAL50_108_SOFTWARE_RELEASE_V1' and release.get('main_thread_id')==MAIN and release.get('work_id')==WORK and
         release.get('software_only') is True and release.get('vendor_build') is False,'explicit main first software release required')
    need(release.get('input_pins_sha256')==sha(a.pins),'exact prepared pins')
    sources={str(p):sha(p) for p in Path(__file__).parent.iterdir() if p.is_file()}
    need(release.get('source_files')==sources,'main frozen exact108 sources')
    for row in pins['readonly_files']:need(sha(row['path'])==row['sha256'],'unchanged readonly input')
    out=a.out.resolve();need(out.is_relative_to(Path('D:/pynq/CarlandFPGA/.local/v108').resolve()) and not out.exists(),'new owned first-attempt root')
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic();deadline=started+40.
    result=dict(status='failed',work_id=WORK,requirements_sha256=CONTRACT,requirements_ids=['H%02d'%i for i in range(1,16)],
        source_commit=release['source_commit'],source_before=sources,cases=[],evidence_kind='SOFTWARE_ONLY_FINITE_NESTED_TOPOLOGY',
        vendor_build=False,board=False,A26_one_build_consumed=False,hard_aggregate_process_guarantee=False)
    try:
        spec=importlib.util.spec_from_file_location('envelope108',Path(__file__).with_name('run_envelope108.py'))
        env=importlib.util.module_from_spec(spec);spec.loader.exec_module(env)
        child=Path(__file__).with_name('harmless_child108.py');owned=Path(pins['owned_path']);windows=Path(pins['windows_path'])
        for case,threshold in [('benign_native16_sample16',16),('guard_native16_sample8',8)]:
            need(time.monotonic()<deadline,'one40s software attempt exceeded')
            build=out/(case+'-child-output');folder=out/(case+'-envelope')
            limits=dict(mode='software_test',wall_seconds=12.,memory_bytes=512*1024**2,active_processes=16,sampled_active_processes=threshold,
                output_bytes=1024**2,poll_seconds=.05,drain_seconds=2.,terminate_seconds=.5,launcher_wait_seconds=.5)
            argv=[sys.executable,'-B',str(child),'--mode','benign','--build',str(build),'--owned',str(owned),'--windows',str(windows)]
            v=env.run_envelope(argv,folder,build,windows,owned,limits)
            row=dict(case=case,result_path=str(folder/'RESULT.json'),result_sha256=sha(folder/'RESULT.json'),status=v['status'],launcher_exit=v['launcher_exit'],
                stop_reason=v['stop_reason'],observed_peak=v['observed_peak_aggregate_active_processes'],native_limit=v['native_caps_before_launch']['active_process_limit'],
                sampled_threshold=v['sampled_active_process_threshold'],sampled_exceeded=v['sampled_process_limit_exceeded'])
            result['cases'].append(row);save(out/(case+'-observed.json'),v)
            need(v['termination_confirmed'] and v['job_terminal_confirmed'] and v['job_empty_observed_before_close'] and v['job_closed'],'actual outer empty-before-close required')
            cap=v['native_caps_before_launch'];need((cap['flags'],cap['active_process_limit'],cap['job_memory_limit'])==(0x2208,16,512*1024**2),'exact native16/512MiB readback')
            need(v['native_caps_before_close']['active_process_limit']==16 and not v['nominal_deadline_breached'],'native16 unchanged and nominal12s aggregate')
            need(v['sampled_active_process_threshold']==threshold,'selected sampled threshold')
            if threshold==16:
                inner=json.loads((build/'INNER_RESULT.json').read_text('utf-8'))
                need(v['status']=='completed' and v['launcher_exit']==0 and not v['sampled_process_limit_exceeded'] and v['observed_peak_aggregate_active_processes']<=16,'benign sampled16 completion')
                need(inner['exit_code']==0 and inner['job_terminal_confirmed'] and inner['job_closed'],'benign nested inner Job empty/closed')
                need(any(s['launcher_exit']==0 and s['accounting']['active_processes']>0 for s in v['samples']),'actual nested descendants after launcher0')
            else:
                violations=[s for s in v['samples'] if s['accounting']['active_processes']>8]
                need(violations,'UNRESOLVED: actual topology did not exceed8; no workload enlargement or retry')
                need(v['status']=='failed' and v['stop_reason']=='sampled_aggregate_process_limit' and v['sampled_process_limit_exceeded'] and v['launcher_exit']!=0,'new sampled guard actually stops owned hierarchy')
                need(v.get('job_termination',{}).get('attempted') is True,'actual own Job termination required')
            print(json.dumps(row),flush=True)
        need(time.monotonic()<=deadline,'one40s software attempt exceeded')
        result['status']='NEW_SAMPLED_GUARD_CONTROLS_COMPLETED_MAIN_REVIEW_PENDING'
    except BaseException:result['failure']=traceback.format_exc();print(result['failure'],flush=True)
    finally:
        after={}
        try:
            for path in Path(__file__).parent.iterdir():
                if path.is_file():
                    try:after[str(path)]=sha(path)
                    except Exception as error:after[str(path)]='UNOBSERVED:'+repr(error)
        except Exception as error:result['source_after_error']=repr(error)
        result['source_after']=after;result['source_changed']=after!=sources
        readonly=[]
        for row in pins['readonly_files']:
            try:
                actual=sha(row['path']);readonly.append(dict(path=row['path'],sha256=actual,changed=actual!=row['sha256']))
            except Exception as error:readonly.append(dict(path=row['path'],changed=True,error=repr(error)))
        result['readonly_after']=readonly
        if result['source_changed'] or any(x['changed'] for x in readonly):result['status']='failed'
        result['elapsed_seconds']=time.monotonic()-started;result['python_version']=sys.version;result['python_executable']=sys.executable
        save(out/'RESULT.json',result)
    return 0 if result['status']=='NEW_SAMPLED_GUARD_CONTROLS_COMPLETED_MAIN_REVIEW_PENDING' else 1


if __name__=='__main__':raise SystemExit(main())
