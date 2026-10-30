"""Future one-attempt fake-controls runner; source-only until main freeze/START."""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

sys.dont_write_bytecode=True
W=Path(__file__).resolve().parents[5]
REL='competition/deepeye/tools/diagnostic/functional50_host103/'
WORK='B-DEEPEYE-FUNCTIONAL50-BOUNDED-HOST-20261031-103'
HELPER='competition/deepeye/tools/diagnostic/g05_capture/build/owned_process.py'
JOB_HELPER='fpga_mesh/windows_job.py'
PINS={HELPER:'1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692',JOB_HELPER:'3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3'}
LIMIT=8*1024*1024

def need(ok,why):
    if not ok:raise RuntimeError(why)
def row(path):
    raw=path.read_bytes();return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
def write(path,value):
    with path.open('x',encoding='utf8') as f:json.dump(value,f,sort_keys=True,indent=2)
def size(out):return sum(p.stat().st_size for p in out.rglob('*') if p.is_file())

def inner(out):
    command=[sys.executable,'-B',str(W/(REL+'test_host103.py')),'--out',str(out/'fake-cases')]
    started=time.monotonic();timed=False;exceeded=False
    with (out/'controls.stdout.bin').open('xb') as stdout,(out/'controls.stderr.bin').open('xb') as stderr:
        p=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                           shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
        write(out/'COMMAND_STARTED.json',{'argv':command,'pid':p.pid,'seconds':25,'scope':'SOFTWARE_FAKE_CSR_ONLY'})
        while p.poll() is None:
            if time.monotonic()-started>=25:timed=True;p.kill()
            if size(out)>LIMIT-262144:exceeded=True;p.kill()
            time.sleep(.02)
    result={'argv':command,'exit_code':p.returncode,'timed_out':timed,'output_exceeded':exceeded,
            'elapsed_seconds':time.monotonic()-started,'stdout':row(out/'controls.stdout.bin'),'stderr':row(out/'controls.stderr.bin')}
    write(out/'COMMAND_RESULT.json',result)
    need(p.returncode==0 and not timed and not exceeded,'focused fake control command failed; stop without retry')
    summary=json.loads((out/'fake-cases/SUMMARY.json').read_bytes())
    need(summary['kind']=='SOFTWARE_FAKE_CSR' and summary['physical_result'] is False,'software scope')
    write(out/'INNER_RESULT.json',{'status':'FOCUSED_FAKE_CONTROLS_COMPLETED','summary':summary})
    return 0

def outer(out,freeze_path):
    out.mkdir(parents=True,exist_ok=False)
    freeze=json.loads(freeze_path.read_bytes())
    need(freeze['work_id']==WORK and freeze['runtime_scope']=='SOFTWARE_FAKE_CSR_ONLY','main freeze work/scope')
    pins=json.loads((W/(REL+'fixtures/pins.json')).read_bytes())
    specs={p.relative_to(W).as_posix():p for p in (W/REL).rglob('*') if p.is_file()}
    need(set(freeze['sources'])==set(specs),'exact main frozen host103 files')
    for rel,p in specs.items():
        r=row(p);expected=freeze['sources'][rel]
        need(r['sha256']==expected['sha256'] and r['bytes']==expected['bytes'],'main frozen source '+rel)
    dependencies=list(pins['source_pins'])+list(PINS)
    for rel in dependencies:
        p=W/rel;r=row(p)
        expected=PINS.get(rel) or pins['source_pins'][rel]['sha256']
        need(r['sha256']==expected,'immutable dependency '+rel)
        specs[rel]=p
    before={}
    for rel,p in specs.items():
        dest=out/'source'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
        before[rel]={'live':row(p),'snapshot':row(dest)}
    write(out/'SOURCE_BEFORE.json',before)
    (out/'MAIN_FREEZE.json').write_bytes(freeze_path.read_bytes())
    helper=out/'source'/HELPER
    spec=importlib.util.spec_from_file_location('host103_owned',helper);owned=importlib.util.module_from_spec(spec);spec.loader.exec_module(owned)
    jobdir=out/'owned_job';jobdir.mkdir()
    # 120s is a software-control Job bound. It does not certify hung A MMIO.
    job=owned.run_owned([sys.executable,'-B',str(out/'source'/(REL+'run103.py')),'--inner','--out',str(out)],
                        jobdir,120,out/'source'/JOB_HELPER,job_drain_seconds=5,job_terminate_seconds=5)
    write(out/'JOB_RESULT.json',job)
    after={rel:{'live':row(p),'snapshot':row(out/'source'/rel)} for rel,p in specs.items()}
    write(out/'SOURCE_AFTER.json',after)
    stable=before==after
    terminal=all(job.get(k) is True for k in ('job_attached_before_resume','launcher_exit_confirmed','job_empty_observed_before_close','job_terminal_confirmed','job_closed'))
    ok=job.get('exit_code')==0 and terminal and stable and (out/'INNER_RESULT.json').exists()
    result={'status':'FAKE_CONTROLS_COMPLETED_MAIN_REVIEW_PENDING' if ok else 'FAILED_PRESERVED_NO_RETRY',
            'work_id':WORK,'job':job,'sources_unchanged':stable,'job_terminal_empty_closed':terminal,
            'kind':'SOFTWARE_FAKE_CSR','physical_provider':'A_ORIGINAL_PROVIDER_UNAVAILABLE',
            'physical_result':False,'current_source_eligible':False,'command':None,'core_ran':False,'acceptance':False,
            'source_before':row(out/'SOURCE_BEFORE.json'),'source_after':row(out/'SOURCE_AFTER.json')}
    result['evidence']={p.relative_to(out).as_posix():row(p) for p in out.rglob('*') if p.is_file()}
    write(out/'RESULT.json',result);need(size(out)<=LIMIT,'8MiB total attempt evidence limit')
    print(json.dumps({'status':result['status'],'result':row(out/'RESULT.json'),'job_terminal':terminal}))
    return 0 if ok else 1

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--main-freeze',type=Path);p.add_argument('--inner',action='store_true');a=p.parse_args()
    try:
        if a.inner:return inner(a.out.resolve())
        need(a.main_freeze is not None,'explicit main source freeze and later START required')
        return outer(a.out.resolve(),a.main_freeze.resolve())
    except Exception:
        error=traceback.format_exc();print(error,file=sys.stderr)
        if a.out.exists():
            target=a.out/('INNER_FAILURE.json' if a.inner else 'OUTER_FAILURE.json')
            if not target.exists():write(target,{'error':error,'retry':False})
        return 1
if __name__=='__main__':raise SystemExit(main())
