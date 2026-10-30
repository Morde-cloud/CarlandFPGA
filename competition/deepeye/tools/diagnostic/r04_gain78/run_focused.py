"""NEW78 finite standalone digital SPI controls; no board, analog model or SO."""
import argparse,datetime,hashlib,importlib.util,json,subprocess,sys,time
from pathlib import Path
R=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
TOOLS=Path('D:/modelsim1/win64')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(p,o):p.write_bytes((json.dumps(o,indent=2)+'\n').encode())
def command(out,name,args,cwd,expected=0):
    row={'argv':list(map(str,args)),'cwd':str(cwd),'expected_exit':expected,'timeout_seconds':25}
    started=time.monotonic()
    with (out/(name+'.stdout.bin')).open('xb') as so,(out/(name+'.stderr.bin')).open('xb') as se:
        p=subprocess.Popen(row['argv'],cwd=cwd,stdout=so,stderr=se,stdin=subprocess.DEVNULL,shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
        row['pid']=p.pid;save(out/(name+'.STARTED.json'),row)
        try:
            while p.poll() is None:
                assert time.monotonic()-started<25,'native command deadline'
                assert sum(f.stat().st_size for f in out.parent.rglob('*') if f.is_file())<8*1024*1024,'8MiB output limit'
                time.sleep(.025)
        finally:
            row.update(exit_code=p.poll(),elapsed_seconds=time.monotonic()-started)
            save(out/(name+'.json'),row)
    assert row['exit_code']==expected,(name,row)
    return row
def inner(out):
    sim=out/'sim';sim.mkdir();cmd=out/'commands';cmd.mkdir();rows=[]
    for tool in ['vlog','vsim']:rows.append(command(cmd,tool+'-version',[TOOLS/(tool+'.exe'),'-version'],sim))
    rows.append(command(cmd,'vmap',[TOOLS/'vmap.exe','-c'],sim))
    rows.append(command(cmd,'vlib',[TOOLS/'vlib.exe','work'],sim))
    rows.append(command(cmd,'compile',[TOOLS/'vlog.exe','-sv','-work','work',out/'source/dut.sv',out/'source/tb.sv'],sim))
    compile_text=(cmd/'compile.stdout.bin').read_text(errors='replace')
    assert 'Errors: 0, Warnings: 0' in compile_text
    for name,negative,expected in [('positive',0,0),('negative',1,4)]:
        dest=out/name;dest.mkdir();dofile=dest/'run.do'
        dofile.write_text('onerror {quit -code 3 -force}\nonbreak {\nif {[examine -radix decimal /tb_r04_gain78/completion_status] == 1} {quit -code 0 -force}\nquit -code 4 -force\n}\nrun -all\nquit -code 4 -force\n')
        rows.append(command(cmd,name,[TOOLS/'vsim.exe','-c','-voptargs=+acc','-onfinish','stop','-wlf',dest/'wave.wlf','-l',dest/'modelsim.log',
          'work.tb_r04_gain78','+OUT='+(dest/'pins.csv').as_posix(),'+NEGATIVE='+str(negative),'-do','do '+dofile.as_posix()],sim,expected))
        text=(dest/'modelsim.log').read_text(errors='replace')
        assert ('R04_NEW78_PASS' in text and '** Fatal:' not in text) if not negative else '** Fatal: R04_NEW78 independent pin byte oracle' in text
    save(out/'INNER_RESULT.json',{'status':'new_focused_digital_controls_passed','commands':rows})
def outer(out):
    out.mkdir(parents=True,exist_ok=False);snap=out/'source';snap.mkdir()
    paths={'dut.sv':R/'competition/deepeye/fpga/diagnostic/r04_gain76/deepeye_mcp6s21_write_candidate.sv',
      'tb.sv':R/'competition/deepeye/fpga/diagnostic/r04_gain78/tb_r04_gain78.sv',
      'run78.py':Path(__file__).resolve(),
      'owned_process.py':R/'competition/deepeye/tools/diagnostic/g05_capture/build/owned_process.py',
      'windows_job.py':R/'fpga_mesh/windows_job.py'}
    pins={}
    for name,path in paths.items():
        b=path.read_bytes();(snap/name).write_bytes(b);pins[name]={'original':str(path),'sha256':sha(b),'bytes':len(b)}
    assert pins['windows_job.py']['sha256']=='3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3'
    save(out/'SOURCE_BEFORE.json',pins)
    spec=importlib.util.spec_from_file_location('r04_owned',snap/'owned_process.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    job=out/'job';job.mkdir()
    argv=list(map(str,[sys.executable,'-B',snap/'run78.py','--inner','--out',out]))
    pr=m.run_owned(argv,job,90,snap/'windows_job.py')
    result={'status':'failed_preserved','task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'work_id':'B-R04-GAIN-DIGITAL-VERIFICATION-20261030-78',
      'evidence_kind':'SYNTHETIC_DIGITAL_FIXTURE','requirements_sha256':'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804',
      'process':pr,'source_snapshots':pins,'tested_commit':None,'source_description':'Exact frozen precommit source snapshots, no later commit execution claimed',
      'board':'not_run; A only','analog_gain_actual':None,'R04':'NOT_PASSED','ADC_readback_actual':'unavailable',
      'tool_binary_sha256':{n:sha((TOOLS/(n+'.exe')).read_bytes()) for n in ['vmap','vlib','vlog','vsim']}}
    after={name:sha(path.read_bytes()) for name,path in paths.items()};save(out/'SOURCE_AFTER.json',after)
    try:
        m.require_owned_success(pr);assert pr['job_closed']
        assert all(pins[name]['sha256']==h for name,h in after.items())
        assert (out/'INNER_RESULT.json').exists();result['status']='new_focused_digital_controls_passed'
    finally:save(out/'RESULT.json',result)
    print(json.dumps({'status':result['status'],'result':str(out/'RESULT.json')}))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True);a.add_argument('--inner',action='store_true');n=a.parse_args()
    (inner if n.inner else outer)(n.out.resolve())
