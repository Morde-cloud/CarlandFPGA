"""99T bounded native Job runner source. Use only after explicit main release.

Pinned original helpers stay unchanged. Their WindowsJob and whole-Job
accounting/closure implementation is reused; this wrapper adds live output,
command and whole-suite limits. No unrelated process/PID action exists.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

WINDOWS_SHA='3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3'
OWNED_SHA='1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692'


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def run(argv,directory,*,owned_path,windows_path,whole_deadline,evidence_root,sha):
    if sha(owned_path)!=OWNED_SHA or sha(windows_path)!=WINDOWS_SHA:raise RuntimeError('unchanged pinned native helper bytes required')
    original=load(owned_path,'gate99t_original_owned');win=load(windows_path,'gate99t_original_windows')
    directory.mkdir(exist_ok=False);work=directory/'work';work.mkdir();temp=directory/'tmp';temp.mkdir()
    remaining=whole_deadline-time.monotonic();timeout=min(25.,remaining-11.)
    if timeout<=0:raise TimeoutError('whole120s bound leaves no command/closure budget')
    result=dict(argv=argv,cwd=str(work),timeout_seconds=timeout,command_cap_seconds=25,whole_cap_seconds=120,output_cap_bytes=8*1024*1024,
        owned_helper_sha256=sha(owned_path),windows_helper_sha256=sha(windows_path),shell=False,hidden=True,
        job_attached_before_resume=False,job_terminal_confirmed=False,timed_out=False,output_exceeded=False)
    job=process=accounting=None;reason=None;started=time.monotonic()
    env=os.environ.copy();env.update(TEMP=str(temp),TMP=str(temp),PYTHONDONTWRITEBYTECODE='1')
    try:
        with (directory/'stdout.bin').open('xb') as stdout,(directory/'stderr.bin').open('xb') as stderr:
            try:
                job=win.WindowsJob();accounting=original._WinJobAccounting(job)
                process=subprocess.Popen(argv,cwd=work,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,shell=False,
                    creationflags=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP|0x4)
                result['pid']=process.pid
                (directory/'STARTED.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
                job.attach_and_resume(process);result['job_attached_before_resume']=True
                initial=original._sample_owned_job(accounting,result,'after_attach')
                if initial is None:raise RuntimeError('initial owned Job accounting failed')
                deadline=min(started+timeout,whole_deadline-10.)
                while process.poll() is None:
                    amount=sum(p.stat().st_size for p in evidence_root.rglob('*') if p.is_file())
                    if amount>8*1024*1024:result['output_exceeded']=True;reason='output_budget';break
                    if time.monotonic()>=deadline:result['timed_out']=True;reason='command_or_whole_deadline';break
                    time.sleep(.025)
                if reason is None and process.returncode!=0:reason='launcher_nonzero_exit'
                if sum(p.stat().st_size for p in evidence_root.rglob('*') if p.is_file())>8*1024*1024:
                    result['output_exceeded']=True;reason='output_budget'
            except BaseException as error:
                result['runner_error']=type(error).__name__+': '+str(error);reason='runner_error'
            finally:
                if accounting is not None:original._finish_owned_job(accounting,result,reason,5.,5.)
                if process is not None and process.poll() is None and not result['job_attached_before_resume']:
                    process.kill();result['unattached_original_handle_terminated']=True
                if job is not None:
                    job.close();result['job_closed']=job.handle is None
                if process is not None:
                    try:process.wait(timeout=5.)
                    except subprocess.TimeoutExpired:result['launcher_exit_unconfirmed']=True
    finally:
        result.update(elapsed_seconds=time.monotonic()-started,exit_code=process.poll() if process is not None else None,
            stdout_sha256=sha(directory/'stdout.bin'),stderr_sha256=sha(directory/'stderr.bin'),whole_deadline_remaining=whole_deadline-time.monotonic())
        (directory/'PROCESS.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    if not (result['exit_code']==0 and result['job_terminal_confirmed'] and result.get('job_closed') and
            not result['timed_out'] and not result['output_exceeded'] and not result.get('runner_error')):
        raise RuntimeError('99T command failed; stop without retry: '+str(directory/'PROCESS.json'))
    return result
