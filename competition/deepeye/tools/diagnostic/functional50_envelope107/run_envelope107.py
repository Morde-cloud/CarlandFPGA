"""Compact outer native Job envelope. No default CLI/vendor invocation.

Main-selected source107; imports/runtime need a separate main release.
Only new owned Job/process handles may be terminated. No retry or deletion.
"""
import ctypes
from ctypes import wintypes as w
import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import time

REPO=Path('D:/pynq/CarlandFPGA')
WINDOWS_SHA='3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3'
OWNED_SHA='1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692'
FLAGS=0x2000|0x200|0x8  # KILL_ON_JOB_CLOSE | JOB_MEMORY | ACTIVE_PROCESS
BUILD_LIMITS=dict(mode='build',wall_seconds=7260,memory_bytes=8*1024**3,active_processes=64,
                  output_bytes=2*1024**3,poll_seconds=1.,drain_seconds=5.,terminate_seconds=5.,launcher_wait_seconds=5.)


def need(ok,why):
    if not ok:raise ValueError(why)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,sort_keys=True,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj


def validate_limits(limits):
    need(type(limits) is dict and set(limits)==set(BUILD_LIMITS),'explicit complete limits required')
    for key in set(limits)-{'mode'}:
        value=limits[key];need(type(value) in (int,float) and math.isfinite(value) and value>0,'finite positive '+key)
    for key in ('memory_bytes','active_processes','output_bytes'):need(type(limits[key]) is int,'integer '+key)
    if limits['mode']=='build':need(limits==BUILD_LIMITS,'exact main build limits required')
    else:
        need(limits['mode']=='software_test','explicit build/software_test mode only')
        need(limits['wall_seconds']<=15 and limits['memory_bytes'] in (256*1024**2,512*1024**2) and
             limits['active_processes']==8 and limits['output_bytes']==1024**2,'small main-selected software test limits only')
        need(.01<=limits['poll_seconds']<=1 and all(limits[k]<=5 for k in ('drain_seconds','terminate_seconds','launcher_wait_seconds')),'bounded test sampling/cleanup')
    need(limits['wall_seconds']>sum(limits[k] for k in ('drain_seconds','terminate_seconds','launcher_wait_seconds')),'positive live-work budget after cleanup reservation')
    return dict(limits)


class Basic(ctypes.Structure):
    _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',w.DWORD),
        ('min_working_set',ctypes.c_size_t),('max_working_set',ctypes.c_size_t),('active_processes',w.DWORD),
        ('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]


class Extended(ctypes.Structure):
    _fields_=[('basic',Basic),('io',ctypes.c_ulonglong*6),('process_memory',ctypes.c_size_t),
        ('job_memory',ctypes.c_size_t),('peak_process_memory',ctypes.c_size_t),('peak_job_memory',ctypes.c_size_t)]


class NativeLimits:
    def __init__(self,job,limits):
        self.job,self.limits=job,limits;self.query=job.kernel.QueryInformationJobObject
        self.query.argtypes=[w.HANDLE,ctypes.c_int,w.LPVOID,w.DWORD,ctypes.POINTER(w.DWORD)];self.query.restype=w.BOOL
    def install(self):
        data=Extended();data.basic.flags=FLAGS;data.basic.active_processes=self.limits['active_processes'];data.job_memory=self.limits['memory_bytes']
        if not self.job.kernel.SetInformationJobObject(self.job.handle,9,ctypes.byref(data),ctypes.sizeof(data)):raise ctypes.WinError(ctypes.get_last_error())
        return self.read()
    def read(self):
        need(self.job.handle is not None,'Job must remain open through limit observation')
        data=Extended();size=w.DWORD()
        if not self.query(self.job.handle,9,ctypes.byref(data),ctypes.sizeof(data),ctypes.byref(size)):raise ctypes.WinError(ctypes.get_last_error())
        need(size.value==ctypes.sizeof(data),'complete class9 limit readback required')
        need(data.basic.flags==FLAGS and data.basic.active_processes==self.limits['active_processes'] and
             data.job_memory==self.limits['memory_bytes'],'native limit readback differs; BREAKAWAY/extra flags forbidden')
        return dict(flags=int(data.basic.flags),job_memory_limit=int(data.job_memory),active_process_limit=int(data.basic.active_processes),
            peak_job_committed_bytes=int(data.peak_job_memory),peak_process_committed_bytes=int(data.peak_process_memory),returned_bytes=int(size.value))


def output_size(roots):
    total=0;seen=set()
    for root in roots:
        if not root.exists():continue
        for directory,dirs,files in os.walk(root,followlinks=False):
            for name in dirs+files:
                path=Path(directory)/name;info=path.lstat()
                need(not info.st_file_attributes & 0x400,'output reparse point forbidden; do not traverse outside owned roots')
                if name in files:
                    key=(info.st_dev,info.st_ino)
                    if key not in seen:total+=info.st_size;seen.add(key)
    return total


def run_envelope(argv,envelope_dir,build_output_dir,windows_job_path,owned_path,limits):
    started=time.monotonic()
    limits=validate_limits(limits)
    aggregate_deadline=started+limits['wall_seconds']
    live_deadline=aggregate_deadline-sum(limits[k] for k in ('drain_seconds','terminate_seconds','launcher_wait_seconds'))
    remaining=lambda:max(0.,aggregate_deadline-time.monotonic())
    need(os.name=='nt','Windows native Job required')
    need(type(argv) is list and 1<=len(argv)<=128 and all(type(x) is str and x and '\x00' not in x for x in argv),'explicit finite argv strings required')
    need(sum(map(len,argv))<=32768,'bounded command line required')
    need(Path(argv[0]).is_absolute() and Path(argv[0]).name.lower() not in {'cmd.exe','powershell.exe','pwsh.exe','mshta.exe','wscript.exe','cscript.exe','sc.exe','schtasks.exe','ssh.exe'},'no shell/service/elevation launcher')
    need(Path(envelope_dir).is_absolute() and Path(build_output_dir).is_absolute(),'explicit absolute envelope/build paths required')
    envelope,build=Path(envelope_dir).resolve(),Path(build_output_dir).resolve();root=REPO.resolve()
    need(envelope.is_relative_to(root) and build.is_relative_to(root) and envelope!=root and build!=root,'repo-contained exact new roots required')
    need(not envelope.is_relative_to(build) and not build.is_relative_to(envelope),'envelope/build roots must be disjoint, not equal/ancestors')
    need(not envelope.exists() and not build.exists(),'preexisting envelope/build path refused without mutation')
    windows_job_path,owned_path=Path(windows_job_path).resolve(),Path(owned_path).resolve()
    need(sha(windows_job_path)==WINDOWS_SHA and sha(owned_path)==OWNED_SHA,'unchanged native helper pins required')
    envelope.mkdir(parents=True,exist_ok=False)  # Build output is NOT created/reserved here.
    result=dict(schema='FUNCTIONAL50_ENVELOPE107_RESULT_V1',status='failed',argv=list(argv),envelope_dir=str(envelope),build_output_dir=str(build),
        limits=limits,started_utc=utc(),source_sha256=sha(__file__),windows_job_sha256=sha(windows_job_path),owned_sha256=sha(owned_path),
        shell=False,hidden=True,job_attached_before_resume=False,job_terminal_confirmed=False,job_query_failed=False,
        output_bound='sampled aggregate bytes; overshoot possible, not an OS disk quota',memory_bound='Job committed memory, not resident RAM or immediate termination',
        build_path='intent-bound absent target; inner builder owns exclusive mkdir; no OS path reservation',samples=[],
        aggregate_nominal_seconds=limits['wall_seconds'],live_budget_seconds=live_deadline-started,
        deadline_kind='nominal aggregate incl cleanup reserve; host scheduling/bookkeeping is not hard real-time')
    job=accounting=native=process=None;reason=None;launcher_end=None
    try:
        save(envelope/'INTENT.json',dict(result,state='STARTING_UNKNOWN_BEFORE_LAUNCH'))
        original=module(owned_path,'envelope107_pinned_owned');win=module(windows_job_path,'envelope107_pinned_windows')
        with (envelope/'stdout.bin').open('xb') as stdout,(envelope/'stderr.bin').open('xb') as stderr:
            try:
                job=win.WindowsJob();accounting=original._WinJobAccounting(job);native=NativeLimits(job,limits)
                result['native_caps_before_launch']=native.install();save(envelope/'CAPS_BEFORE_LAUNCH.json',result['native_caps_before_launch'])
                need(not build.exists(),'build path appeared before launch; refuse without reuse')
                result['native_caps_immediately_before_launch']=native.read()
                need(time.monotonic()<live_deadline,'live budget exhausted before launch')
                process=subprocess.Popen(argv,cwd=root,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,shell=False,
                    creationflags=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP|0x4)
                result['launcher_pid']=process.pid;save(envelope/'PROCESS_CREATED_SUSPENDED.json',result)
                job.attach_and_resume(process);result['job_attached_before_resume']=True
                save(envelope/'STARTED.json',dict(launcher_pid=process.pid,at_utc=utc(),attached_before_resume=True))
                while True:
                    now=time.monotonic();code=process.poll()
                    if code is not None and launcher_end is None:launcher_end=now
                    counts=original._sample_owned_job(accounting,result,'monitor_outer_including_nested')
                    if counts is None:raise RuntimeError('outer Job accounting query failed')
                    try:caps=native.read()
                    except BaseException:result['job_query_failed']=True;raise
                    amount=output_size((envelope,build))
                    result['samples'].append(dict(elapsed_seconds=now-started,aggregate_remaining_seconds=remaining(),accounting=counts,limits=caps,output_bytes=amount,launcher_exit=code))
                    if code is not None and code!=0:reason='launcher_nonzero_exit';break
                    if amount>limits['output_bytes']:reason='sampled_output_limit';break
                    if counts['active_processes']==0:break
                    if now>=live_deadline:reason='live_work_deadline_with_cleanup_reserve';break
                    if launcher_end is not None and now-launcher_end>=limits['drain_seconds']:reason='launcher_exit_with_live_descendants_after_drain';break
                    time.sleep(min(limits['poll_seconds'],max(0.,live_deadline-now)))
            except BaseException as error:
                result['error']=type(error).__name__+': '+str(error);reason=reason or 'query_output_launch_or_attach_error'
            finally:
                workload_end=time.monotonic();result['workload_elapsed_seconds']=workload_end-started;result['stop_reason']=reason
                if process is not None and not result['job_attached_before_resume'] and process.poll() is None:
                    try:process.kill();process.wait(timeout=min(limits['launcher_wait_seconds'],remaining()));result['original_unattached_handle_cleanup']=True
                    except BaseException as error:result['original_unattached_handle_cleanup_error']=repr(error)
                if accounting is not None:
                    budget=remaining();wait_reserve=min(limits['launcher_wait_seconds'],budget)
                    available=max(0.,budget-wait_reserve)
                    drain_budget=min(limits['drain_seconds'],available) if reason is None else 0.
                    terminate_budget=min(limits['terminate_seconds'],max(0.,available-drain_budget))
                    result['cleanup_allocated_budgets']=dict(remaining_before_helper=budget,launcher_wait_reserved=wait_reserve,
                        helper_drain=drain_budget,helper_terminate=terminate_budget)
                    try:original._finish_owned_job(accounting,result,reason,drain_budget,terminate_budget)
                    except BaseException as error:result['job_terminal_confirmed']=False;result['terminal_observation_error']=repr(error)
                if native is not None:
                    try:result['native_caps_before_close']=native.read()
                    except BaseException as error:result['job_query_failed']=True;result['job_terminal_confirmed']=False;result['final_caps_error']=repr(error)
                if job is not None:
                    try:
                        result['job_closed']=bool(job.kernel.CloseHandle(job.handle))
                        if result['job_closed']:job.handle=None
                        else:result['job_close_error']=str(ctypes.WinError(ctypes.get_last_error()))
                    except BaseException as error:result['job_close_error']=repr(error)
                if process is not None:
                    try:process.wait(timeout=min(limits['launcher_wait_seconds'],remaining()))
                    except BaseException as error:result['launcher_wait_error']=repr(error)
                result['cleanup_elapsed_seconds']=time.monotonic()-workload_end
    except BaseException as error:result['outer_error']=type(error).__name__+': '+str(error)
    finally:
        result.update(completed_utc=utc(),elapsed_seconds=time.monotonic()-started,launcher_exit=process.poll() if process is not None else None)
        result['aggregate_remaining_seconds']=remaining();result['nominal_deadline_breached']=time.monotonic()>aggregate_deadline
        result['termination_confirmed']=bool(result['job_attached_before_resume'] and result['launcher_exit'] is not None and
            result.get('job_terminal_confirmed') and result.get('job_empty_observed_before_close') and result.get('job_closed') and not result['job_query_failed'])
        result['status']='completed' if result['termination_confirmed'] and result['launcher_exit']==0 and reason is None and not result.get('error') and not result.get('outer_error') and not result['nominal_deadline_breached'] else 'failed'
        try:
            result['final_output_bytes_before_RESULT']=output_size((envelope,build))
            result['final_output_limit_exceeded']=result['final_output_bytes_before_RESULT']>limits['output_bytes']
            if result['final_output_limit_exceeded']:result['status']='failed'
        except BaseException as error:result['output_after_error']=repr(error);result['final_output_limit_exceeded']=None;result['status']='failed'
        result['raw_files']={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in (envelope/'stdout.bin',envelope/'stderr.bin') if p.exists()}
        save(envelope/'RESULT.json',result)
    return result
