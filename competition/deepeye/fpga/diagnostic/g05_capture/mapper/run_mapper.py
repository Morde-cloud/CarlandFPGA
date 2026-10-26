"""Bounded, local ModelSim-only runner; preserves every command and full job exit proof."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import traceback

REPO = Path('D:/pynq/CarlandFPGA')
SOURCE = REPO/'.local/worktrees/deepeye-implementation-20261014/competition/deepeye/fpga/diagnostic/g05_capture/mapper'
EVIDENCE = REPO/'.local/deployment/node-b/evidence/g05-capture-20261026-59/mapper'
TOOLS = Path('D:/modelsim1/win64')
HELPER_SHA = '3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3'
ENUMS = REPO/'.local/deployment/node-b/evidence/task-resume-20261026/a-g05-extra-inputs/files/competition/deepeye/docs/enums.json'
ASSIGNMENT = REPO/'.local/deployment/node-b/evidence/g05-capture-20261026-59/MAPPER_ASSIGNMENT.md'
LOCK = REPO/'.local/deployment/node-b/evidence/b-integration-inventory-20261024/sources/f5989cd5defce561f9ba98e6b18fc2682945f0a2/docs/competition/deepeye-2026/immutable_scope.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,ensure_ascii=False)
        stream.write('\n')


class Accounting(ctypes.Structure):
    _fields_ = [(name,ctypes.c_longlong) for name in
        ('TotalUserTime','TotalKernelTime','ThisPeriodTotalUserTime','ThisPeriodTotalKernelTime')]
    _fields_ += [(name,wintypes.DWORD) for name in
        ('TotalPageFaultCount','TotalProcesses','ActiveProcesses','TotalTerminatedProcesses')]


def run_owned(job_type, argv, cwd, outdir, label, env, timeout=90):
    record={'argv':[str(x) for x in argv],'cwd':str(cwd),
        'started_utc':datetime.now(timezone.utc).isoformat(),'timeout_seconds':timeout,
        'creation_flags':['CREATE_SUSPENDED','CREATE_NO_WINDOW'],
        'observations':[],'errors':[],'termination_requested':False}
    start=time.monotonic()
    job=job_type()
    k=job.kernel
    k.QueryInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,wintypes.LPVOID,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
    k.QueryInformationJobObject.restype=wintypes.BOOL
    k.TerminateJobObject.argtypes=[wintypes.HANDLE,wintypes.UINT]
    k.TerminateJobObject.restype=wintypes.BOOL
    def account():
        info=Accounting(); returned=wintypes.DWORD()
        if not k.QueryInformationJobObject(job.handle,1,ctypes.byref(info),ctypes.sizeof(info),ctypes.byref(returned)):
            raise ctypes.WinError(ctypes.get_last_error())
        assert returned.value == ctypes.sizeof(info)
        value={'elapsed':round(time.monotonic()-start,6),'total':info.TotalProcesses,
               'active':info.ActiveProcesses,'terminated':info.TotalTerminatedProcesses}
        record['observations'].append(value)
        return info.ActiveProcesses
    proc=None
    attached=False
    try:
        with (outdir/(label+'.stdout.log')).open('xb') as stdout, (outdir/(label+'.stderr.log')).open('xb') as stderr:
            proc=subprocess.Popen([str(x) for x in argv],cwd=str(cwd),env=env,stdin=subprocess.DEVNULL,
                stdout=stdout,stderr=stderr,creationflags=0x00000004|0x08000000)
            record['pid']=proc.pid
            job.attach_and_resume(proc)
            attached=True
            account()
            try:
                record['exit_code']=proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                record['errors'].append('parent_timeout')
            if record['errors']:
                record['termination_requested']=True
                if not k.TerminateJobObject(job.handle,0xE0000059):
                    raise ctypes.WinError(ctypes.get_last_error())
            deadline=time.monotonic()+8
            while account()!=0 and time.monotonic()<deadline:
                time.sleep(0.05)
            if record['observations'][-1]['active']!=0:
                record['errors'].append('owned_descendants_not_terminal')
                record['termination_requested']=True
                if not k.TerminateJobObject(job.handle,0xE0000059):
                    raise ctypes.WinError(ctypes.get_last_error())
                deadline=time.monotonic()+8
                while account()!=0 and time.monotonic()<deadline:
                    time.sleep(0.05)
            record['exit_code']=proc.wait(timeout=8)
            record['whole_owned_job_terminal']=account()==0
    except BaseException:
        record['errors'].append(traceback.format_exc())
        if proc is not None and proc.poll() is None and not attached:
            # Only the just-created original suspended PID, never an external process.
            proc.kill()
            proc.wait(timeout=8)
        try:
            record['termination_requested']=True
            if not k.TerminateJobObject(job.handle,0xE0000059):
                raise ctypes.WinError(ctypes.get_last_error())
            deadline=time.monotonic()+8
            while account()!=0 and time.monotonic()<deadline:
                time.sleep(0.05)
            record['whole_owned_job_terminal']=account()==0
        except BaseException:
            record['errors'].append(traceback.format_exc())
    finally:
        # KILL_ON_JOB_CLOSE is the final containment backstop, not terminal proof.
        job.close()
        record['duration_seconds']=round(time.monotonic()-start,6)
        record['finished_utc']=datetime.now(timezone.utc).isoformat()
        record['stdout_sha256']=digest(outdir/(label+'.stdout.log'))
        record['stderr_sha256']=digest(outdir/(label+'.stderr.log'))
        record['ownership_ok']=not record['errors'] and record.get('whole_owned_job_terminal') is True
        save(outdir/(label+'.command.json'),record)
    return record


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    args=parser.parse_args()
    assert re.fullmatch(r'attempt-[0-9]{2}',args.attempt)
    assert Path(__file__).resolve().parent == SOURCE.resolve()
    attempt=EVIDENCE/args.attempt
    attempt.mkdir(parents=True,exist_ok=False)
    result={'schema':1,'status':'failed','attempt':str(attempt),'commands':[],
            'scope':'pure combinational mapper simulation only; no G05 or product acceptance'}
    try:
        helper=REPO/'fpga_mesh/windows_job.py'
        assert digest(helper)==HELPER_SHA
        inputs=attempt/'inputs'; inputs.mkdir()
        for name,path in (('enums.json',ENUMS),('assignment.md',ASSIGNMENT),
                          ('immutable_scope.json',LOCK),('windows_job.py',helper)):
            shutil.copyfile(path,inputs/name)
        helper_spec=importlib.util.spec_from_file_location('mapper_owned_job',inputs/'windows_job.py')
        helper_module=importlib.util.module_from_spec(helper_spec)
        helper_spec.loader.exec_module(helper_module)
        env=os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE']='1'
        ini=attempt/'modelsim.ini'
        ini.write_text('[Library]\nwork = work\nothers = D:/modelsim1/modelsim.ini\n',encoding='ascii')
        env['MODELSIM']=str(ini)
        def run(label,argv,expected_exit=0):
            record=run_owned(helper_module.WindowsJob,argv,attempt,attempt,label,env)
            result['commands'].append({'label':label,'exit_code':record.get('exit_code'),
                'ownership_ok':record['ownership_ok'],'pid':record.get('pid')})
            assert record['ownership_ok'], f'{label}: process ownership failure'
            if expected_exit is not None:
                assert record.get('exit_code')==expected_exit, f'{label}: unexpected exit {record.get("exit_code")}'
            return record
        generator=[sys.executable,'-B','-X','utf8',str(SOURCE/'generate_curvature_rom.py'),
                   '--enums',str(ENUMS),'--assignment',str(ASSIGNMENT),'--lock',str(LOCK)]
        if (SOURCE/'curvature_limits.json').exists() or (SOURCE/'deepeye_g05_curvature_rom.svh').exists():
            generator.append('--check')
        run('01-generate',generator)
        snapshot=attempt/'source'; snapshot.mkdir()
        for path in sorted(SOURCE.iterdir()):
            assert path.is_file(),f'unexpected source directory: {path}'
            shutil.copyfile(path,snapshot/path.name)
        result['source_hashes']={path.name:digest(path) for path in sorted(snapshot.iterdir())}
        save(attempt/'source_manifest.json',result['source_hashes'])
        run('02-oracle',[sys.executable,'-B','-X','utf8',snapshot/'oracle_vectors.py','--output',attempt/'oracle'])
        oracle=json.loads((attempt/'oracle/vectors.json').read_text(encoding='utf-8'))
        rom=json.loads((snapshot/'curvature_limits.json').read_text(encoding='utf-8'))
        assert {(r['profile_id'],r['speed_code']):r['curvature_limit'] for r in rom['rows']} == {
            (r['profile'],r['code']):r['limit'] for r in oracle['independent_limits']}
        result['known_vectors']=oracle['row_count']; result['unknown_vectors']=18
        result['oracle_categories']=oracle['categories']
        run('03-vlog-version',[TOOLS/'vlog.exe','-version'])
        run('04-vsim-version',[TOOLS/'vsim.exe','-version'])
        run('05-vlib',[TOOLS/'vlib.exe','work'])
        run('06-compile',[TOOLS/'vlog.exe','-sv','-work','work','+incdir+'+str(snapshot),
                          snapshot/'deepeye_g05_command_map.sv',snapshot/'tb_deepeye_g05_command_map.sv'])
        do=attempt/'simulate.do'
        do.write_text('onerror {quit -code 1}\n'
            'onbreak {\n'
            '  if {[catch {examine -radix decimal sim:/tb_deepeye_g05_command_map/completion_status} done]} {quit -code 3}\n'
            '  if {$done == 1} {quit -code 0}\n'
            '  quit -code 2\n}\n'
            'onfinish stop\nrun -all\nquit -code 4\n',encoding='ascii')
        common=[TOOLS/'vsim.exe','-c','-voptargs=+acc','-lib','work','tb_deepeye_g05_command_map',
                '+VECTORS='+str(attempt/'oracle/vectors.hex'),'+COUNT='+str(oracle['row_count']),'-do',str(do)]
        run('07-positive',[*common,'-l',str(attempt/'positive.transcript')])
        positive=(attempt/'positive.transcript').read_text(encoding='utf-8',errors='replace')
        expected=f"G05_MAPPER_PASS known={oracle['row_count']} unknown=18"
        assert len(re.findall(r'^#?\s*'+re.escape(expected)+r'\s*$',positive,re.MULTILINE))==1
        assert not re.search(r'\*\*\s+(?:Error|Fatal):',positive)
        negative=run('08-negative-checker',[*common,'+CORRUPT_EXPECTED=1',
                     '-l',str(attempt/'negative.transcript')],expected_exit=None)
        neg=(attempt/'negative.transcript').read_text(encoding='utf-8',errors='replace')
        assert negative['exit_code']!=0 and 'G05_MAPPER_CHECK_FAILED' in neg
        assert 'G05_MAPPER_MISMATCH index=0 ' in neg and 'G05_MAPPER_PASS' not in neg
        compile_text=(attempt/'06-compile.stdout.log').read_text(encoding='utf-8',errors='replace')
        assert re.search(r'Errors:\s*0\b',compile_text) and not re.search(r'\*\*\s+(?:Error|Fatal):',compile_text)
        assert result['source_hashes']=={p.name:digest(p) for p in sorted(SOURCE.iterdir())}
        result['negative_control']='expected TTL bit32 mismatch detected at vector0 with nonzero simulator exit'
        result['status']='passed'
    except BaseException:
        result['failure']=traceback.format_exc()
    finally:
        save(attempt/'result.json',result)
        print(json.dumps(result,indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':
    sys.exit(main())
