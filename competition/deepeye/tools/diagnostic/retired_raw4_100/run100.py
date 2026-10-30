"""One attempt, snapshot-only, suspended-before-attach Windows Job runtime."""
from __future__ import annotations
import argparse, datetime, hashlib, importlib.util, json, os, subprocess, sys, time, traceback
from pathlib import Path
sys.dont_write_bytecode=True
W=Path(__file__).resolve().parents[5]
ROOT=Path('D:/pynq/CarlandFPGA')
P=ROOT/'.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-74'
TOOLS=Path('D:/modelsim1/win64')
REL='competition/deepeye/tools/diagnostic/retired_raw4_100/'
BENCH='competition/deepeye/fpga/diagnostic/retired_raw4_100/tb_RETIRED_RAW4_100.sv'
ADAPTER='competition/deepeye/tools/diagnostic/causal_raw4_92/raw4_adapter92.py'
HELPER='competition/deepeye/tools/diagnostic/g05_capture/build/owned_process.py'
JOBHELPER='fpga_mesh/windows_job.py'
REQUIREMENTS='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
JOB='child-19bf374e4aef42ae9525052750f26b67'
AGENT='/root/retired_raw4_100'
WORK='B-DEEPEYE-RETIRED70-RAW4-RECOVERY-20261031-100'
LIMIT=8*1024*1024
# SOURCE_TABLES inserted by source preparation, never imported from the old runner.
COMPILE_RELS = ['competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv', 'competition/deepeye/fpga/acquisition/deepeye_raw_scan_queue.sv', 'competition/deepeye/fpga/acquisition/deepeye_buffered_scan_capture.sv', 'competition/deepeye/fpga/acquisition/deepeye_scan_lane_stream.sv', 'competition/deepeye/fpga/codec/deepeye_block_encoder.sv', 'competition/deepeye/fpga/codec/deepeye_trace_payload_candidate.sv', 'competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_payload_1us_candidate.sv', 'competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_uart_50mhz_candidate.sv', 'competition/deepeye/fpga/transport/deepeye_crc16_byte.sv', 'competition/deepeye/fpga/transport/deepeye_wire_serializer.sv', 'competition/deepeye/fpga/transport/deepeye_uart_tx.sv', 'competition/deepeye/fpga/diagnostic/offboard_codec74/deepeye_SYNTHETIC_codec74_fixture.sv', 'competition/deepeye/fpga/diagnostic/retired_raw4_100/tb_RETIRED_RAW4_100.sv']
READONLY_EXPECTED = {'competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv': 'fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d', 'competition/deepeye/fpga/acquisition/deepeye_raw_scan_queue.sv': '630e14803d82b3379517d91626de4ad7e7d3c509ad14363b3164031a5f633ee4', 'competition/deepeye/fpga/acquisition/deepeye_buffered_scan_capture.sv': 'c8a540db8122b8f5520582a0f1fa9be0c43cb54a62f03c7c4edc893906f28411', 'competition/deepeye/fpga/acquisition/deepeye_scan_lane_stream.sv': 'b3c9d2024d9325191538cf08fec9a652ff8ff0ae316ec9af96078f85cf5be3cc', 'competition/deepeye/fpga/codec/deepeye_block_encoder.sv': '4cb79428ef89096742e293516c4696caf985048d8185f531fe92eaa485c8d532', 'competition/deepeye/fpga/codec/deepeye_trace_payload_candidate.sv': 'fb64ace453c451838110c81bf6cb4a815a96fb2668e28a306ff699beca5acef6', 'competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_payload_1us_candidate.sv': '5ebe65dfe0844aab62365e8664507f153cb75ff47b3c8d4e10f45356e94147a8', 'competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_uart_50mhz_candidate.sv': '41ea63819c892ec67fe92d6e9338a771d5f93f60d0976e895f18bc97966283d2', 'competition/deepeye/fpga/transport/deepeye_crc16_byte.sv': '8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f', 'competition/deepeye/fpga/transport/deepeye_wire_serializer.sv': 'efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885', 'competition/deepeye/fpga/transport/deepeye_uart_tx.sv': '5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47', 'competition/deepeye/fpga/diagnostic/offboard_codec74/deepeye_SYNTHETIC_codec74_fixture.sv': '409ee484113fa4006eb27e12554a4db57708df5e7dadf269548f546d03931a6a', 'competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_integration_50mhz_candidate.sv': '957f696429c39fed5c41dc83df88fa78ab2a294a57c1a834ef0f0ef81b7ae2dd', 'competition/deepeye/golden/codec/trace_candidate.py': 'a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642', 'competition/deepeye/tools/diagnostic/g05_capture/additive50_source_candidate/deepeye_transport50_source_candidate.py': '1f4da870d9c885a3cc6156c30d2170e21001187392a59a19172c059c9ab0c768', 'competition/deepeye/tools/diagnostic/g05_capture/build/owned_process.py': '1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692', 'fpga_mesh/windows_job.py': '3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3'}
SELECTED=[REL+'run100.py',REL+'input100.py',REL+'check100.py',BENCH,ADAPTER,
          'competition/deepeye/golden/diagnostic/retired_raw4_100/README.md']
def need(ok,why):
    if not ok: raise RuntimeError(why)
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(raw): return hashlib.sha256(raw).hexdigest()
def record(p):
    p=Path(p);r=p.read_bytes();return {'path':str(p),'bytes':len(r),'sha256':sha(r)}
def write(p,v):
    with Path(p).open('x',encoding='utf8',newline='\n') as f: json.dump(v,f,ensure_ascii=False,sort_keys=True,indent=2);f.write('\n')
def size(out): return sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
def command(out,name,argv,cwd):
    commands=out/'commands';started=time.monotonic();row={'argv':[str(x) for x in argv],'cwd':str(cwd),'started':utc(),'timeout_seconds':25,'expected_exit':0}
    with (commands/(name+'.stdout.bin')).open('xb') as stdout,(commands/(name+'.stderr.bin')).open('xb') as stderr:
        p=subprocess.Popen(row['argv'],cwd=cwd,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
        row['pid']=p.pid;write(commands/(name+'.STARTED.json'),row)
        row['timed_out']=False;row['output_limit_exceeded']=False
        while p.poll() is None:
            if time.monotonic()-started>=25: row['timed_out']=True;p.kill()
            if size(out)>LIMIT-131072: row['output_limit_exceeded']=True;p.kill()
            time.sleep(.02)
        row['exit_code']=p.returncode
    row.update(elapsed_seconds=time.monotonic()-started,ended=utc(),stdout=record(commands/(name+'.stdout.bin')),stderr=record(commands/(name+'.stderr.bin')))
    write(commands/(name+'.json'),row)
    need(not row['timed_out'] and not row['output_limit_exceeded'] and row['exit_code']==0,'failed command '+name)
    return row
def inner(out):
    write(out/'ATTEMPT_STARTED.json',{'job_id':JOB,'agent_id':AGENT,'work_id':WORK,'utc':utc(),'single_actual_attempt':True})
    (out/'commands').mkdir();sim=out/'sim';sim.mkdir()
    for rel,expected in READONLY_EXPECTED.items(): need(sha((W/rel).read_bytes())==expected,'snapshot dependency '+rel)
    c=json.loads((out/'inputs/immutable_scope_pinned.json').read_bytes())
    need(sha(json.dumps(c['requirements'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())==REQUIREMENTS,'fixed H01-H15 hash')
    command(out,'00-python-version',[sys.executable,'--version'],sim)
    command(out,'01-build-input',[sys.executable,'-B',W/(REL+'input100.py'),'--fixture-mode','RETIRED_A70_TRANSPORT_FIXTURE','--input',out/'inputs/retired-source70.json','--out',out/'fixture'],sim)
    command(out,'02-default-input',[sys.executable,'-B',W/(REL+'input100.py')],sim)
    default=json.loads((out/'commands/02-default-input.stdout.bin').read_bytes())
    need(default['input_status']=='INPUT_UNAVAILABLE' and default['command'] is None and default['core_ran'] is False,'default CLI closed')
    for tool in ('vlog','vsim','vmap'): command(out,'03-'+tool+'-version',[TOOLS/(tool+'.exe'),'-version'],sim)
    command(out,'04-vmap',[TOOLS/'vmap.exe','-c'],sim)
    command(out,'05-vlib',[TOOLS/'vlib.exe','work'],sim)
    command(out,'06-vlog',[TOOLS/'vlog.exe','-sv','-work','work',*[W/r for r in COMPILE_RELS]],sim)
    log=(out/'commands/06-vlog.stdout.bin').read_text(errors='replace')
    need('Errors: 0' in log and '** Error:' not in log,'compile log errors')
    dest=out/'mode0';dest.mkdir()
    do=out/'run.do'
    do.write_text('onerror {quit -code 3 -force}\nonbreak {\nif {[examine -radix decimal /tb_RETIRED_RAW4_100/completed] == 1} {quit -code 0 -force}\nquit -code 4 -force\n}\nrun -all\nif {[examine -radix decimal /tb_RETIRED_RAW4_100/completed] == 1} {quit -code 0 -force}\nquit -code 4 -force\n',encoding='ascii')
    command(out,'07-vsim',[TOOLS/'vsim.exe','-c','-voptargs=+acc','-onfinish','stop','-wlf',dest/'wave.wlf','-l',dest/'modelsim.log','work.tb_RETIRED_RAW4_100','+OUT='+dest.as_posix(),'+MEM='+(out/'fixture/records.hex').as_posix(),'-do','do '+do.as_posix()],sim)
    log=(dest/'modelsim.log').read_text(errors='replace')
    need('B100_SYNTHETIC_DONE mode=0' in log and 'Errors: 0' in log and '** Fatal:' not in log and '** Error:' not in log,'exact simulation completion')
    command(out,'08-check',[sys.executable,'-B',W/(REL+'check100.py'),'--out',out],sim)
    write(out/'INNER_RESULT.json',{'status':'COMPLETED_CHECKS_MAIN_REVIEW_PENDING','utc':utc(),'semantic':json.loads((out/'SEMANTIC_RESULT.json').read_bytes())})
    return 0
def terminal(j):
    return all(j.get(k) is True for k in ('job_attached_before_resume','launcher_exit_confirmed','job_empty_observed_before_close','job_terminal_confirmed','job_closed')) and not any(j.get(k) for k in ('timed_out','process_error','job_query_failed','job_termination_failed','job_close_error'))
def outer(out):
    out.mkdir(parents=True,exist_ok=False)
    selected={r:W/r for r in set(SELECTED+COMPILE_RELS+list(READONLY_EXPECTED))}
    before={}
    for r,p in selected.items():
        dst=out/'source'/r;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(p.read_bytes());before[r]={'live':record(p),'snapshot':record(dst)}
    write(out/'SOURCE_BEFORE.json',before)
    inputs=out/'inputs';inputs.mkdir()
    pins=json.loads((P/'source-inputs/A18-retired-source70-r2/PINS.json').read_bytes())
    files={'immutable_scope_pinned.json':P/'immutable_scope_pinned.json','retired-source70.json':Path(pins[0]['local']),'source-readme.md':Path(pins[1]['local']),'PINS.json':P/'source-inputs/A18-retired-source70-r2/PINS.json','RETIRED97_MAIN_DESIGN.md':P/'RETIRED97_MAIN_DESIGN.md','RETIRED100_MAIN_RECOVERY_DECISION.json':P/'RETIRED100_MAIN_RECOVERY_DECISION.json','A18_INDEPENDENT_DATA.json':P/'main-verification96/A18_INDEPENDENT_DATA.json','INDEPENDENT_SAVED_BYTES_R1.json':P/'main-verification92/INDEPENDENT_SAVED_BYTES_R1.json'}
    for name,p in files.items(): (inputs/name).write_bytes(p.read_bytes())
    write(out/'INPUT_BEFORE.json',{name:record(inputs/name) for name in files})
    write(out/'TOOL_BINARIES.json',{n:record(TOOLS/(n+'.exe')) for n in ('vmap','vlib','vlog','vsim')})
    for rel,expected in READONLY_EXPECTED.items(): need(before[rel]['snapshot']['sha256']==expected,'pinned dependency '+rel)
    snap=out/'source'
    spec=importlib.util.spec_from_file_location('b100_owned',snap/HELPER);owned=importlib.util.module_from_spec(spec);spec.loader.exec_module(owned)
    jd=out/'owned_job';jd.mkdir()
    job=owned.run_owned([sys.executable,'-B',str(snap/(REL+'run100.py')),'--inner','--out',str(out)],jd,120,snap/JOBHELPER,job_drain_seconds=5,job_terminate_seconds=5)
    write(out/'JOB_RESULT.json',job)
    after={r:{'live':record(p),'snapshot':record(snap/r)} for r,p in selected.items()};write(out/'SOURCE_AFTER.json',after)
    write(out/'INPUT_AFTER.json',{name:record(inputs/name) for name in files})
    stable=before==after
    ir=out/'INNER_RESULT.json';sem=out/'SEMANTIC_RESULT.json';inner_result=json.loads(ir.read_bytes()) if ir.exists() else None
    ok=job.get('exit_code')==0 and terminal(job) and stable and inner_result is not None
    commands=[json.loads(p.read_bytes()) for p in sorted((out/'commands').glob('*.json')) if not p.name.endswith('.STARTED.json')]
    result={'status':'COMPLETED_RUNTIME_MAIN_REVIEW_PENDING' if ok else 'FAILED_PRESERVED_NO_RETRY','job_id':JOB,'agent_id':AGENT,'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'work_id':WORK,'requirements_ids':['H%02d'%i for i in range(1,16)],'requirements_sha256':REQUIREMENTS,'freeze':'1011259415a0916054eb580687612580bc1e5f09','source_runtime_commit':'4dc91fd24531b3df53fc916e8b7f509ad524592c','current_B_source_kind':'exact snapshot bytes; no later commit claimed tested','selected_sources':{r:before[r] for r in SELECTED},'sources_unchanged':stable,'job':job,'job_terminal_empty_closed':terminal(job),'commands':commands,'semantic':json.loads(sem.read_bytes()) if sem.exists() else None,'scope':'actual historical numerical input and RTL simulation only','unmet_gates':{'actual_Root':'UNAVAILABLE','original_EM_receipt':'UNAVAILABLE','BOOT':'UNAVAILABLE','admission':'UNAVAILABLE','physical_ADC':'NOT_RUN','board':'NOT_RUN A_ONLY','synthesis':'NOT_RUN','implementation':'NOT_RUN','current_source_eligible':False,'command':None,'core_ran':False,'status':'STOP','full_H12':'NOT_ACCEPTED','final_1percent_100ms':'NOT_ACCEPTED','original_100MHz':'NOT_ACCEPTED','all29':'NOT_ACCEPTED','H01_H15_product_acceptance':'NOT_ACCEPTED'},'utc':utc()}
    result['evidence']={p.relative_to(out).as_posix():record(p) for p in sorted(out.rglob('*')) if p.is_file()}
    result['output_bytes_before_result']=size(out);write(out/'RESULT.json',result)
    need(size(out)<=LIMIT,'total output exceeds 8MiB')
    print(json.dumps({'status':result['status'],'result':str(out/'RESULT.json'),'result_sha256':sha((out/'RESULT.json').read_bytes()),'job_terminal_empty_closed':terminal(job),'output_bytes':size(out)}))
    return 0 if ok else 1
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--inner',action='store_true');o=p.parse_args();out=o.out.resolve()
    try: return inner(out) if o.inner else outer(out)
    except Exception:
        error=traceback.format_exc();print(error,file=sys.stderr)
        if out.exists():
            name='INNER_FAILURE.json' if o.inner else 'OUTER_FAILURE.json'
            if not (out/name).exists(): write(out/name,{'error':error,'utc':utc(),'no_retry':True})
        return 1
if __name__=='__main__': raise SystemExit(main())
