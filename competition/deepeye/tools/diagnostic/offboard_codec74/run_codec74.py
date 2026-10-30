"""Finite new B74 offboard compilation/simulation and semantic controls only.

All native commands are descendants of one suspended-launch Windows Job.
The pinned existing whole-Job helper proves terminal/empty/closed state.
Each command has a30s timeout; the full Job has180s and16MiB output bound.
Never installs, calls Vivado/board, changes services, or writes a Git index.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,datetime,hashlib,importlib.util,json,os,shutil,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parents[3]
ROOT=P.parents[1]
HDL=P/'fpga/diagnostic/offboard_codec74'
TOOLS=P/'tools/diagnostic/offboard_codec74'
MODEL=Path('D:/modelsim1/win64')
G05=P/'fpga/diagnostic/g05_capture/additive50_source_candidate/rtl'
SOURCES=[P/f'fpga/acquisition/{n}.sv' for n in ['deepeye_sample_scan_capture','deepeye_raw_scan_queue','deepeye_buffered_scan_capture','deepeye_scan_lane_stream']]
SOURCES += [P/'fpga/codec/deepeye_block_encoder.sv',P/'fpga/codec/deepeye_trace_payload_candidate.sv',
  G05/'deepeye_trace_block_payload_1us_candidate.sv',G05/'deepeye_trace_block_uart_50mhz_candidate.sv']
SOURCES += [P/f'fpga/transport/{n}.sv' for n in ['deepeye_crc16_byte','deepeye_wire_serializer','deepeye_uart_tx']]
SOURCES += [HDL/'deepeye_SYNTHETIC_codec74_fixture.sv',HDL/'tb_SYNTHETIC_codec74.sv']
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def command(out,name,args,cwd,expected=0):
    r=dict(argv=list(map(str,args)),cwd=str(cwd),started_utc=utc(),timeout_seconds=30,expected_exit=expected)
    with (out/(name+'.stdout.bin')).open('xb') as so,(out/(name+'.stderr.bin')).open('xb') as se:
        proc=subprocess.Popen(r['argv'],cwd=cwd,stdout=so,stderr=se,stdin=subprocess.DEVNULL,shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
        r['pid']=proc.pid;save(out/(name+'.STARTED.json'),r)
        try:
            deadline=time.monotonic()+30
            while proc.poll() is None:
                if time.monotonic()>deadline:raise TimeoutError('finite native command deadline')
                if sum(f.stat().st_size for f in out.rglob('*') if f.is_file())>16*1024*1024:raise RuntimeError('16MiB whole output bound')
                time.sleep(.05)
            r['exit_code']=proc.returncode
        except BaseException as e:
            r['error']=repr(e);proc.kill();r['exit_code']=proc.wait(timeout=5)
            raise
        finally:
            r.update(ended_utc=utc(),stdout_sha256=sha(out/(name+'.stdout.bin')),stderr_sha256=sha(out/(name+'.stderr.bin')))
            save(out/(name+'.json'),r)
    assert r['exit_code']==expected,(name,r)
    return r
def inner(out,phase='full',saved=None):
    commands=out/'commands';commands.mkdir();sim=out/'sim';sim.mkdir();reports=[]
    if phase=='positive':
        reports.append(command(commands,'semantic-positive',[sys.executable,'-B',TOOLS/'semantic_controls.py','--simdir',saved,'--out',out/'semantic'],sim))
        save(out/'INNER_RESULT.json',dict(status='bounded_synthetic_semantic_positive_passed',commands=reports,completed_utc=utc()))
        return
    for tool in ['vlog','vsim']:
        reports.append(command(commands,tool+'-version',[MODEL/(tool+'.exe'),'-version'],sim))
    reports.append(command(commands,'vmap-local',[MODEL/'vmap.exe','-c'],sim))
    reports.append(command(commands,'vlib',[MODEL/'vlib.exe','work'],sim))
    reports.append(command(commands,'vlog',[MODEL/'vlog.exe','-sv','-work','work',*SOURCES],sim))
    if phase=='remaining':
        (out/'mode0').mkdir()
        for name in ['uart.hex','serializer.hex','events.txt','modelsim.log']:
            shutil.copyfile(saved/'mode0'/name,out/'mode0'/name)
        save(out/'mode0/REUSED_SAVED_INPUT_NOT_RERUN.json',dict(source=str(saved/'mode0'),files={n:sha(saved/'mode0'/n) for n in ['uart.hex','serializer.hex','events.txt','modelsim.log']}))
    for mode in ([1,2,3,4,5] if phase=='remaining' else range(6)):
        dest=out/f'mode{mode}';dest.mkdir()
        # Tcl quit code propagates actual assertion/fatal; no ModelSim
        # -onfinish exit0 qualification loophole for negative/error cases.
        dofile=dest/'run.do'
        dofile.write_text('onerror {quit -code 3 -force}\nonbreak {\nif {[examine -radix decimal /tb_SYNTHETIC_codec74/completed] == 1} {quit -code 0 -force}\nquit -code 4 -force\n}\nrun -all\nif {[examine -radix decimal /tb_SYNTHETIC_codec74/completed] == 1} {quit -code 0 -force}\nquit -code 4 -force\n',encoding='ascii')
        reports.append(command(commands,f'vsim-mode{mode}',[MODEL/'vsim.exe','-c','-voptargs=+acc','-onfinish','stop','-wlf',str(dest/'wave.wlf'),'-l',str(dest/'modelsim.log'),
            'work.tb_SYNTHETIC_codec74','+OUT='+dest.as_posix(),'+MODE='+str(mode),'-do','do '+dofile.as_posix()],sim,expected=4 if mode==4 else 0))
        log=(dest/'modelsim.log').read_text(encoding='utf-8')
        if mode==4:
            assert '** Fatal: B74_INTENTIONAL_RUNNER_NEGATIVE' in log and 'B74_SYNTHETIC_DONE' not in log
        else:
            assert 'B74_SYNTHETIC_DONE mode='+str(mode) in log and '** Fatal:' not in log and '** Error:' not in log and 'Errors: 0' in log
    if phase!='remaining':
        reports.append(command(commands,'semantic-positive',[sys.executable,'-B',TOOLS/'semantic_controls.py','--simdir',out,'--out',out/'semantic'],sim))
    for case in ['crc','partial','identity','quality','quality_flags','time','u63_overflow','nonwrap','wrong_index','relative_overflow']:
        reports.append(command(commands,'negative-'+case,[sys.executable,'-B',TOOLS/'semantic_controls.py','--simdir',out,'--negative',case],sim,expected=2))
        text=(commands/('negative-'+case+'.stdout.bin')).read_text()
        assert 'expected_rejection' in text and 'FALSE_ACCEPT' not in text
    save(out/'INNER_RESULT.json',dict(status='bounded_synthetic_controls_passed',commands=reports,completed_utc=utc()))
def outer(out,phase='full',saved=None):
    out.mkdir(parents=True,exist_ok=False)
    extra=[G05/'deepeye_integration_50mhz_candidate.sv',P/'golden/codec/trace_candidate.py',
      P/'tools/diagnostic/g05_capture/additive50_source_candidate/deepeye_transport50_source_candidate.py',
      P/'tools/diagnostic/g05_capture/build/owned_process.py',ROOT/'fpga_mesh/windows_job.py',
      P/'golden/diagnostic/offboard_codec74/SYNTHETIC_raw4.json',HDL/'tb_body.sv.inc']+list(TOOLS.glob('*.py'))
    files=list(dict.fromkeys(SOURCES+extra));snap=out/'source';snap.mkdir()
    pins={}
    for f in files:
        rel=f.relative_to(ROOT);target=snap/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
        pins[str(rel)]={'sha256':sha(f),'bytes':f.stat().st_size,'snapshot':str(target)}
    save(out/'SOURCE_BEFORE.json',pins)
    helper=snap/'fpga_mesh/windows_job.py'
    spec=importlib.util.spec_from_file_location('b74_owned_process',P/'tools/diagnostic/g05_capture/build/owned_process.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    jobout=out/'owned_job';jobout.mkdir()
    argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--inner','--out',str(out),'--phase',phase]
    if saved is not None:
        argv+=['--saved-mode0',str(saved)]
        save(out/'SAVED_MODE0_INPUTS.json',{str(f):sha(f) for f in (saved/'mode0').iterdir() if f.is_file()})
    process=m.run_owned(argv,jobout,180,helper)
    after={str(f.relative_to(ROOT)):sha(f) for f in files};save(out/'SOURCE_AFTER.json',after)
    result=dict(status='failed_preserved',evidence_kind='SYNTHETIC_FIXTURE',process=process,
      task_id='DEEPEYE-IMPLEMENTATION-20261014',task_version=1,work_id='B-DEEPEYE-OFFBOARD-CODEC-EXECUTABLE-20261030-74',
      requirements_sha256='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804',
      requirements_ids=[f'H{i:02d}' for i in range(1,16)],
      source_snapshot_kind='uncommitted exact file hashes; no later commit claimed tested',phase=phase,
      tool_binaries={str(MODEL/(n+'.exe')):sha(MODEL/(n+'.exe')) for n in ['vmap','vlib','vlog','vsim']},
      python=dict(executable=sys.executable,version=sys.version,sha256=sha(sys.executable)),
      sources_unchanged=all(pins[r]['sha256']==h for r,h in after.items()),
      board='not_run; A only',vivado='not_run',production_defaults='unchanged, hold/profile0/transport0/BAUD0',
      aggregation='not_run; later operation',acceptance='not granted; quality main/A review required')
    try:
        m.require_owned_success(process)
        assert process['job_closed'] and result['sources_unchanged']
        assert (out/'INNER_RESULT.json').exists()
        result['status']='bounded_synthetic_controls_passed'
        if (out/'semantic/RESULT.json').exists():
            result['semantic']=json.loads((out/'semantic/RESULT.json').read_text())
    finally:save(out/'RESULT.json',result)
    print(json.dumps({'status':result['status'],'result':str(out/'RESULT.json')}))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);a.add_argument('--inner',action='store_true');a.add_argument('--phase',choices=['full','positive','remaining'],default='full');a.add_argument('--saved-mode0',type=Path);n=a.parse_args()
    (inner if n.inner else outer)(n.out.resolve(),n.phase,n.saved_mode0)
