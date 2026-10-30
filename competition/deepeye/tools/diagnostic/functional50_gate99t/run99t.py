"""First attempt only. Main release must precede ANY candidate/Tcl execution."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time
import traceback
import owned_runner99t as runner

TASK='DEEPEYE-IMPLEMENTATION-20261014';WORK='B-DEEPEYE-FUNCTIONAL50-BUILDER-SOFTWARE-20261031-99T'
MAIN='01a18824-4172-74e2-a13f-f3e3d1e3ed99'
CONTRACT='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(p,value):
    with p.open('x',encoding='utf-8',newline='\n') as out:json.dump(value,out,ensure_ascii=False,indent=2);out.write('\n')
def require(ok,message):
    if not ok:raise RuntimeError(message)


def main():
    a=argparse.ArgumentParser();a.add_argument('--release',type=Path,required=True);a.add_argument('--pins',type=Path,required=True)
    a.add_argument('--repo',type=Path,required=True);a.add_argument('--product',type=Path,required=True);a.add_argument('--contract',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    args=a.parse_args();release=json.loads(args.release.read_text('utf-8-sig'));pins=json.loads(args.pins.read_text('utf-8'))
    require(release.get('schema')=='FUNCTIONAL50_99T_RUNTIME_RELEASE_V1' and release.get('task_id')==TASK and release.get('task_version')==1 and release.get('work_id')==WORK,'exact99T release identity')
    require(release.get('main_thread_id')==MAIN and release.get('software_only') is True and release.get('allow_candidate_import_and_plain_tcl') is True and
            release.get('vendor_build') is False and release.get('board') is False,'explicit main software-only release required')
    require(re.fullmatch('[0-9a-f]{40}',str(release.get('source_commit',''))) is not None,'main exact source commit required')
    require(release.get('input_pins_sha256')==sha(args.pins),'exact prepared input pins')
    require((release.get('command_seconds'),release.get('whole_seconds'),release.get('output_bytes'))==(25,120,8388608),'fixed runtime bounds')
    repo=args.repo.resolve();product=args.product.resolve();out=args.out.resolve()
    require(out.is_relative_to(repo/'.local/v99t') and not out.exists(),'fresh owned short output only; no retry/resume')
    require(product==repo/'.local/worktrees/deepeye-implementation-20261014/competition/deepeye','explicit selected W/product root')
    before={}
    expected={row['path']:row for row in pins['candidate_files']}
    require(release.get('candidate_files')=={p:r['sha256'] for p,r in expected.items()},'main must pin all31 candidate source/dependency bytes')
    for p,row in expected.items():
        require(sha(p)==row['sha256'] and Path(p).stat().st_size==row['bytes'],'candidate changed before first run: '+p);before[p]=row
    harness={p.name:sha(p) for p in Path(__file__).parent.iterdir() if p.is_file()}
    require(release.get('harness_files')==harness,'main must freeze exact harness bytes')
    for group in ('actual_reports','native_tcl_files','native_helpers'):
        for row in pins[group]:require(sha(row['path'])==row['sha256'],'readonly input/native bytes changed: '+row['path'])
    doc=json.loads(args.contract.read_text('utf-8-sig'))
    require(hashlib.sha256(json.dumps(doc['requirements'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==CONTRACT,'fixed human contract requirements')
    out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();deadline=started+120.
    result=dict(schema='FUNCTIONAL50_99T_RESULT_V1',status='UNEXPECTED_FAILURE_PRESERVED',task_id=TASK,task_version=1,work_id=WORK,
        requirements_sha256=CONTRACT,requirements_ids=['H%02d'%i for i in range(1,16)],source_commit=release['source_commit'],
        python_version=sys.version,python_executable=sys.executable,
        evidence_kind='SOFTWARE_CONTROLS_WITH_LABELLED_SYNTHETIC_FIXTURES',real_build=False,board=False,actual95=False,
        one_build_A26_consumed=False,commands=[],source_before=before,harness_files=harness,
        job_structure='Main-selected four sequential contained category Jobs under ONE aggregate120s attempt; CLI descendants inherit their category Job')
    try:
        save(out/'INTENT.json',dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),release_sha256=sha(args.release),pins_sha256=sha(args.pins),
            run_id=release.get('run_id'),source_commit=release['source_commit'],command25_whole120_output8MiB=True,retry=False,
            job_structure=result['job_structure']))
        shutil.copyfile(args.release,out/'MAIN_RELEASE.json');shutil.copyfile(args.pins,out/'PREPARED_INPUT_PINS.json')
        snapshots=out/'source_snapshot';snapshots.mkdir()
        for index,(p,row) in enumerate(sorted(before.items())):shutil.copyfile(p,snapshots/(str(index)+'_'+Path(p).name))
        helper_paths={row['role']:Path(row['path']) for row in pins['native_helpers']}
        for i,category in enumerate(('cli_contract','identity_cdc','timing_hwh','tcl_helpers'),1):
            category_out=out/('cases-'+category)
            argv=[sys.executable,'-B','-X','utf8',str(Path(__file__).with_name('gate_checks99t.py')),'--category',category,
                '--product',str(product),'--contract',str(args.contract.resolve()),'--pins',str(args.pins.resolve()),'--out',str(category_out)]
            process_directory=out/('%02d-'%i+category)
            try:
                r=runner.run(argv,process_directory,owned_path=helper_paths['owned_process'],windows_path=helper_paths['windows_job'],
                    whole_deadline=deadline,evidence_root=out,sha=sha)
            except BaseException as error:
                failed=dict(category=category,argv=argv,status='FAILED_CATEGORY_NO_RETRY',error=type(error).__name__+': '+str(error),
                            process_evidence=str(process_directory/'PROCESS.json'))
                process_path=process_directory/'PROCESS.json'
                if process_path.exists():
                    try:failed['process']=json.loads(process_path.read_text('utf-8'))
                    except Exception as read_error:failed['process_record_error']=repr(read_error)
                result['commands'].append(failed)
                raise
            r['category']=category;r['process_evidence']=str(process_directory/'PROCESS.json')
            result['commands'].append(r)
            summary=json.loads((category_out/'SUMMARY.json').read_text('utf-8'))
            require(summary['status']=='SOFTWARE_CASES_COMPLETED' and summary['cases']>0 and summary['assertions']>0,'exact category completion')
            print(json.dumps(dict(category=category,exit=r['exit_code'],job_empty_closed=True,summary=summary)),flush=True)
        require(time.monotonic()<=deadline,'whole-suite120s exceeded')
        result['status']='SOFTWARE_CONTROLS_COMPLETED_MAIN_REVIEW_PENDING'
    except BaseException:result['failure']=traceback.format_exc();print(result['failure'],flush=True)
    finally:
        # Always retain after observations, including a failed import/category/
        # launch. Failure is never permission to omit or heal changed sources.
        after={};changed=[]
        for p,row in before.items():
            try:
                observed=dict(path=p,bytes=Path(p).stat().st_size,sha256=sha(p))
                observed['changed']=observed['sha256']!=row['sha256'] or observed['bytes']!=row['bytes']
            except Exception as error:observed=dict(path=p,changed=True,error=repr(error))
            after[p]=observed
            if observed['changed']:changed.append(p)
        result['source_after']=after;result['source_changed_paths']=changed
        try:
            harness_after={p.name:sha(p) for p in Path(__file__).parent.iterdir() if p.is_file()}
            result['harness_after']=harness_after;result['harness_changed']=harness_after!=harness
        except Exception as error:result['harness_after_error']=repr(error);result['harness_changed']=True
        if changed or result['harness_changed']:
            result['status']='UNEXPECTED_FAILURE_PRESERVED'
            result['source_integrity_failure']='Candidate/harness changed or could not be observed; no retry'
        result['elapsed_seconds']=time.monotonic()-started
        save(out/'RESULT.json',result)
        save(out/'FILE_MANIFEST.json',{p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()})
    return 0 if result['status']=='SOFTWARE_CONTROLS_COMPLETED_MAIN_REVIEW_PENDING' else 1


if __name__=='__main__':raise SystemExit(main())
