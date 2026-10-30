"""New B77 finite offboard controls, never the sealed B74 suite.

Native commands descend from the pinned suspended Windows Job helper.
30s per command /180s whole Job /32MiB total attempt files polled per command.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,datetime,hashlib,importlib.util,json,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parents[3];ROOT=P.parents[1]
HDL=P/'fpga/diagnostic/offboard_aggregate77';TOOLS=P/'tools/diagnostic/offboard_aggregate77'
MODEL=Path('D:/modelsim1/win64')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def command(out,name,args,cwd,expected=0):
    folder=out/'commands';folder.mkdir(exist_ok=True)
    r=dict(argv=list(map(str,args)),cwd=str(cwd),started_utc=utc(),timeout_seconds=30,expected_exit=expected)
    with (folder/(name+'.stdout.bin')).open('xb')as so,(folder/(name+'.stderr.bin')).open('xb')as se:
        proc=subprocess.Popen(r['argv'],cwd=cwd,stdout=so,stderr=se,stdin=subprocess.DEVNULL,shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
        r['pid']=proc.pid;save(folder/(name+'.STARTED.json'),r)
        try:
            deadline=time.monotonic()+30
            while proc.poll()is None:
                if time.monotonic()>deadline:raise TimeoutError('B77 command deadline')
                if sum(f.stat().st_size for f in out.rglob('*')if f.is_file())>32*1024*1024:raise RuntimeError('B77 whole attempt32MiB output cap')
                time.sleep(.05)
            r['exit_code']=proc.returncode
        except BaseException as e:
            r['error']=repr(e);proc.kill();r['exit_code']=proc.wait(timeout=5);raise
        finally:
            r.update(ended_utc=utc(),stdout_sha256=sha(folder/(name+'.stdout.bin')),stderr_sha256=sha(folder/(name+'.stderr.bin')))
            save(folder/(name+'.json'),r)
    assert r['exit_code']==expected,(name,r)
    return r
def pin_data():return json.loads((HDL/'dependency_pins.json').read_text())['files']
def sources():
    fixed=[ROOT/r for r in pin_data()if r.endswith('.sv')]
    return fixed+[HDL/n for n in ['deepeye_aggregate12_candidate.sv','deepeye_aggregate_uart_candidate.sv','deepeye_SYNTHETIC_aggregate77.sv','tb_SYNTHETIC_aggregate77.sv']]
def inner(out,saved=None,lifecycle=False):
    sim=out/'sim';sim.mkdir();reports=[]
    if saved is not None:
        reports.append(command(out,'semantic-positive',[sys.executable,'-B',TOOLS/'semantic77_controls.py','--source',saved,'--out',out/'semantic'],sim))
        for name in ['boolean_e','boolean_channel']:
            reports.append(command(out,'negative-'+name,[sys.executable,'-B',TOOLS/'semantic77_controls.py','--source',saved,'--negative',name],sim,2))
            assert 'expected_rejection'in(out/'commands'/('negative-'+name+'.stdout.bin')).read_text()
        save(out/'INNER_RESULT.json',dict(status='B77_saved_bytes_strict_type_controls_passed',commands=reports,completed_utc=utc()))
        return
    for name in ['vlog','vsim']:reports.append(command(out,name+'-version',[MODEL/(name+'.exe'),'-version'],sim))
    reports.append(command(out,'vmap-local',[MODEL/'vmap.exe','-c'],sim));reports.append(command(out,'vlib',[MODEL/'vlib.exe','work'],sim))
    reports.append(command(out,'vlog',[MODEL/'vlog.exe','-sv','-work','work',*sources()],sim))
    for mode in ([14,15,16]if lifecycle else range(14)):
        d=out/f'mode{mode}';d.mkdir();do=d/'run.do'
        do.write_text('onerror {quit -code 3 -force}\nonbreak {\nif {[examine -radix decimal /tb_SYNTHETIC_aggregate77/completed] == 1} {quit -code 0 -force}\nquit -code 4 -force\n}\nrun -all\nif {[examine -radix decimal /tb_SYNTHETIC_aggregate77/completed] == 1} {quit -code 0 -force}\nquit -code 4 -force\n',encoding='ascii')
        reports.append(command(out,f'vsim-mode{mode}',[MODEL/'vsim.exe','-c','-voptargs=+acc','-onfinish','stop','-wlf',d/'wave.wlf','-l',d/'modelsim.log',
          'work.tb_SYNTHETIC_aggregate77','+OUT='+d.as_posix(),'+MODE='+str(mode),'-do','do '+do.as_posix()],sim,4 if mode==12 else 0))
        log=(d/'modelsim.log').read_text(encoding='utf-8')
        if mode==12:assert '** Fatal: B77_INTENTIONAL_RUNNER_NEGATIVE'in log and 'B77_DONE'not in log
        else:assert 'B77_DONE mode='+str(mode)in log and '** Fatal:'not in log and '** Error:'not in log and 'Errors: 0, Warnings: 0'in log
    if lifecycle:
        save(out/'INNER_RESULT.json',dict(status='B77_lifecycle_controls_passed',commands=reports,completed_utc=utc()))
        return
    reports.append(command(out,'semantic-positive',[sys.executable,'-B',TOOLS/'semantic77_controls.py','--source',out,'--out',out/'semantic'],sim))
    for name in ['crc','partial','count','metadata','identity','quality','time','overflow','nonwrap','held','value','missing']:
        reports.append(command(out,'negative-'+name,[sys.executable,'-B',TOOLS/'semantic77_controls.py','--source',out,'--negative',name],sim,2))
        text=(out/'commands'/('negative-'+name+'.stdout.bin')).read_text();assert 'expected_rejection'in text and 'FALSE_ACCEPT'not in text
    save(out/'INNER_RESULT.json',dict(status='B77_bounded_synthetic_controls_passed',commands=reports,completed_utc=utc()))
def outer(out,saved=None,lifecycle=False):
    out.mkdir(parents=True,exist_ok=False)
    for r,v in pin_data().items():assert sha(ROOT/r)==v['sha256'],('fixed dependency pin',r)
    files=list(dict.fromkeys(sources()+[ROOT/r for r in pin_data()]+list(HDL.glob('*.json'))+list(TOOLS.glob('*.py'))+list((P/'golden/diagnostic/offboard_aggregate77').glob('*.json'))))
    snapshot=out/'source';snapshot.mkdir();before={}
    for f in files:
        rel=f.relative_to(ROOT);target=snapshot/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(f.read_bytes())
        before[str(rel)]=dict(sha256=sha(f),bytes=f.stat().st_size,snapshot=str(target))
    save(out/'SOURCE_BEFORE.json',before)
    spec=importlib.util.spec_from_file_location('_b77_owned_process',P/'tools/diagnostic/g05_capture/build/owned_process.py');owned=importlib.util.module_from_spec(spec);spec.loader.exec_module(owned)
    jobout=out/'owned_job';jobout.mkdir()
    argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--inner','--out',str(out)]
    if saved is not None:
        argv+=['--saved-source',str(saved)]
        save(out/'SAVED_INPUT_HASHES.json',{str(f):sha(f)for f in(saved/'mode0').iterdir()if f.is_file()and f.suffix!='.wlf'})
    if lifecycle:argv+=['--lifecycle-only']
    process=owned.run_owned(argv,jobout,180,snapshot/'fpga_mesh/windows_job.py')
    after={str(f.relative_to(ROOT)):sha(f)for f in files};save(out/'SOURCE_AFTER.json',after)
    result=dict(schema='B77_EXECUTION_RESULT_V1',status='failed_preserved',evidence_kind='SYNTHETIC_FIXTURE',
      task_id='DEEPEYE-IMPLEMENTATION-20261014',task_version=1,work_id='B-DEEPEYE-OFFBOARD-BOUNDED-AGGREGATION-20261030-77',
      requirements_sha256='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804',requirements_ids=[f'H{i:02d}'for i in range(1,16)],
      source_label='actual uncommitted source snapshots, no later commit claimed tested',process=process,software_saved_source=str(saved)if saved else None,lifecycle_only=lifecycle,
      sources_unchanged=all(before[r]['sha256']==h for r,h in after.items()),
      tool_binaries={str(MODEL/(n+'.exe')):sha(MODEL/(n+'.exe'))for n in ['vmap','vlib','vlog','vsim']},
      python=dict(executable=sys.executable,version=sys.version,sha256=sha(sys.executable)),
      board='not_run; A only',Vivado='not_run',production='unchanged closed',acceptance='parent quality main/A only')
    try:
        owned.require_owned_success(process);assert process['job_closed']and result['sources_unchanged']
        if not lifecycle:result['semantic']=json.loads((out/'semantic/RESULT.json').read_text())
        assert(out/'INNER_RESULT.json').exists()
        result['status']='B77_bounded_synthetic_controls_passed'
    finally:save(out/'RESULT.json',result)
    print(json.dumps(dict(status=result['status'],result=str(out/'RESULT.json'))))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);a.add_argument('--inner',action='store_true');a.add_argument('--saved-source',type=Path);a.add_argument('--lifecycle-only',action='store_true');n=a.parse_args()
    (inner if n.inner else outer)(n.out.resolve(),n.saved_source,n.lifecycle_only)
