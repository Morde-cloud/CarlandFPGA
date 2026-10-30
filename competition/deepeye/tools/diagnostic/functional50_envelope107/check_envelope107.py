"""ONE later main-released software validation attempt, four finite cases only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

MAIN='01a18824-4172-74e2-a13f-f3e3d1e3ed99'
WORK='B-DEEPEYE-FUNCTIONAL50-RESOURCE-RECOVERY-20261031-107'
CONTRACT='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2);f.write('\n')
def require(ok,why):
    if not ok:raise AssertionError(why)


def main():
    p=argparse.ArgumentParser();p.add_argument('--release',type=Path,required=True);p.add_argument('--pins',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();release=json.loads(a.release.read_text('utf-8-sig'));pins=json.loads(a.pins.read_text('utf-8'))
    require(release.get('schema')=='FUNCTIONAL50_107_SOFTWARE_RELEASE_V1' and release.get('main_thread_id')==MAIN and release.get('work_id')==WORK and
        release.get('software_only') is True and release.get('vendor_build') is False,'explicit main first software release required')
    require(release.get('input_pins_sha256')==sha(a.pins),'exact prepared pins')
    sources={str(p):sha(p) for p in Path(__file__).parent.iterdir() if p.is_file()}
    require(release.get('source_files')==sources,'main frozen exact107 sources')
    for row in pins['readonly_files']:require(sha(row['path'])==row['sha256'],'unchanged readonly/helper input')
    root=Path('D:/pynq/CarlandFPGA/.local/v107').resolve();out=a.out.resolve()
    require(out.is_relative_to(root) and not out.exists(),'new owned first-attempt evidence root')
    out.mkdir(parents=True,exist_ok=False);started=time.monotonic();deadline=started+60.
    result=dict(status='failed',work_id=WORK,source_commit=release['source_commit'],requirements_sha256=CONTRACT,source_before=sources,cases=[],
        evidence_kind='SOFTWARE_ONLY_HARMLESS_PROCESSES',vendor_build=False,board=False,A26_one_build_consumed=False)
    try:
        spec=importlib.util.spec_from_file_location('envelope107',Path(__file__).with_name('run_envelope107.py'))
        env=importlib.util.module_from_spec(spec);spec.loader.exec_module(env)
        owned=Path(pins['owned_path']);windows=Path(pins['windows_path']);child=Path(__file__).with_name('harmless_child107.py')
        for case,mode,wall,drain,terminate,wait in [('nested','benign',12.,2.,.5,.5),('nonzero','exit7',8.,.5,.5,.5),
                                                ('output','writer',8.,.5,.5,.5),('timeout','sleeper',3.,.2,.2,.2)]:
            require(time.monotonic()<deadline,'one60s aggregate software attempt exceeded')
            build=out/(case+'-child-output');envelope=out/(case+'-envelope')
            limits=dict(mode='software_test',wall_seconds=wall,memory_bytes=512*1024**2,active_processes=8,output_bytes=1024**2,
                poll_seconds=.05,drain_seconds=drain,terminate_seconds=terminate,launcher_wait_seconds=wait)
            argv=[sys.executable,'-B',str(child),'--mode',mode,'--build',str(build),'--owned',str(owned),'--windows',str(windows)]
            observed=env.run_envelope(argv,envelope,build,windows,owned,limits)
            row=dict(case=case,result_path=str(envelope/'RESULT.json'),result_sha256=sha(envelope/'RESULT.json'),status=observed['status'],
                     launcher_exit=observed['launcher_exit'],stop_reason=observed['stop_reason'])
            result['cases'].append(row);save(out/(case+'-observed.json'),observed)
            require(observed['termination_confirmed'] and observed['job_terminal_confirmed'] and observed['job_closed'] and observed['job_empty_observed_before_close'],case+' actual empty-before-close proof')
            caps=observed['native_caps_before_launch'];require((caps['flags'],caps['job_memory_limit'],caps['active_process_limit'])==(0x2208,512*1024**2,8),'actual native cap readback')
            require(not observed['nominal_deadline_breached'],case+' nominal aggregate deadline')
            require(observed['native_caps_before_close']['peak_job_committed_bytes']>0,case+' actual committed peak observed')
            if case=='nested':
                inner=json.loads((build/'INNER_RESULT.json').read_text('utf-8'))
                require(observed['status']=='completed' and observed['launcher_exit']==0 and inner['exit_code']==0 and inner['job_terminal_confirmed'] and inner['job_closed'],'benign nested Jobs completed')
                require(any(s['launcher_exit']==0 and s['accounting']['active_processes']>0 for s in observed['samples']),'outer accounts live nested descendants after launcher0')
                require(max(s['accounting']['total_processes'] for s in observed['samples'])>=3,'actual nested descendant total')
            elif case=='nonzero':require(observed['status']=='failed' and observed['launcher_exit']==7 and observed['stop_reason']=='launcher_nonzero_exit','expected actual exit7 retained')
            elif case=='output':require(observed['status']=='failed' and observed['stop_reason']=='sampled_output_limit' and any(s['output_bytes']>1024**2 for s in observed['samples']),'sampled1MiB output limit triggered')
            else:require(observed['status']=='failed' and observed['stop_reason']=='live_work_deadline_with_cleanup_reserve','actual bounded sleep timeout triggered')
            print(json.dumps(row),flush=True)
        require(time.monotonic()<=deadline,'one60s aggregate software attempt exceeded')
        result['status']='SOFTWARE_CONTROLS_COMPLETED_MAIN_REVIEW_PENDING'
    except BaseException:result['failure']=traceback.format_exc();print(result['failure'],flush=True)
    finally:
        after={}
        try:
            for p in Path(__file__).parent.iterdir():
                if p.is_file():
                    try:after[str(p)]=sha(p)
                    except Exception as error:after[str(p)]='UNOBSERVED:'+repr(error)
        except Exception as error:result['source_after_error']=repr(error)
        result['source_after']=after;result['source_changed']=after!=sources
        readonly_after=[]
        for row in pins['readonly_files']:
            try:readonly_after.append(dict(path=row['path'],sha256=sha(row['path']),changed=sha(row['path'])!=row['sha256']))
            except Exception as error:readonly_after.append(dict(path=row['path'],changed=True,error=repr(error)))
        result['readonly_after']=readonly_after
        if any(row['changed'] for row in readonly_after):result['status']='failed'
        if result['source_changed']:result['status']='failed'
        result['elapsed_seconds']=time.monotonic()-started;result['python_version']=sys.version;result['python_executable']=sys.executable
        save(out/'RESULT.json',result)
    return 0 if result['status']=='SOFTWARE_CONTROLS_COMPLETED_MAIN_REVIEW_PENDING' else 1


if __name__=='__main__':raise SystemExit(main())
