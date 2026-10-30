"""ONE NEW102 short-snapshot functional attempt. Any failure stops; no retry.

Only trusted pinned Windows Job bootstrap is imported outside the owned Job.
Candidate/checker imports, guards, vendor tools and strict decoding all run
inside that Job from repository-local snapshot copies. No network/Git/board.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,datetime,hashlib,importlib.util,json,os,shutil,subprocess,time,traceback
from pathlib import Path

REL='competition/deepeye/tools/diagnostic/functional50_axi95'
BENCH='competition/deepeye/fpga/diagnostic/functional50_axi95/tb_deepeye_trace50_axi95.sv'
OWNED='competition/deepeye/tools/diagnostic/g05_capture/build/owned_process.py'
JOB='fpga_mesh/windows_job.py'
OWNED_SHA='1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692'
JOB_SHA='3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3'
REQUIREMENTS='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
WORK='B-DEEPEYE-TRACE50-AXI-RECOVERY-20261031-102'
W=Path(__file__).resolve().parents[5]
R=Path('D:/pynq/CarlandFPGA')
P=R/'.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-74'
PRIVATE_OUT=P/'board50-worker102'
SHORT=R/'.local/v102/attempt-01'
MODEL=Path('D:/modelsim1/win64')
MANUAL=Path('D:/modelsim1/docs/htmldocs/modelsim_se_ref/topics/Command_Vlog_id6ce6948b.html')
MANUAL_SHA='216b3f0556ab5ad64c53fbb049ead73e0d18152049c60ae4f41b1ab1ece14793'

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def record(p):p=Path(p);return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
def need(ok,why):
    if not ok:raise RuntimeError(why)
def save(p,value):Path(p).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def total_bytes(out):
    n=0
    for p in out.rglob('*'):
        try:
            if p.is_file():n+=p.stat().st_size
        except FileNotFoundError:pass # Vendor atomically replaces its own file.
    return n
def command(out,name,args,cwd):
    d=out/'commands';d.mkdir(exist_ok=True)
    r=dict(argv=list(map(str,args)),cwd=str(cwd),started_utc=utc(),timeout_seconds=25,expected_exit=0)
    with(d/(name+'.stdout.bin')).open('xb')as so,(d/(name+'.stderr.bin')).open('xb')as se:
        proc=subprocess.Popen(r['argv'],cwd=cwd,stdin=subprocess.DEVNULL,stdout=so,stderr=se,shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
        r['pid']=proc.pid;save(d/(name+'.STARTED.json'),r)
        deadline=time.monotonic()+25
        try:
            while proc.poll()is None:
                need(time.monotonic()<deadline,'25s command deadline '+name)
                size=total_bytes(out);r['max_polled_output_bytes']=max(size,r.get('max_polled_output_bytes',0))
                need(size<=8*1024*1024,'8MiB output cap '+name)
                time.sleep(.04)
            r['exit_code']=proc.returncode
        except BaseException:
            r['error']=traceback.format_exc();proc.kill();r['exit_code']=proc.wait(timeout=5);raise
        finally:
            r.update(ended_utc=utc(),stdout=record(d/(name+'.stdout.bin')),stderr=record(d/(name+'.stderr.bin')))
            save(d/(name+'.json'),r)
    need(r['exit_code']==0,'command failed '+name+' exit='+str(r['exit_code']))
    need(total_bytes(out)<=8*1024*1024,'8MiB output cap after '+name)
    return r

def inner(out):
    # The entire function, including the candidate checker import, is a child
    # of the suspended-create/attach-before-resume Windows Job.
    try:
        spec=importlib.util.spec_from_file_location('_new102_checker',W/REL/'check95.py')
        c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
        for rel,pin in c.SOURCE_PINS.items():need(sha(W/rel)==pin,'readonly snapshot pin '+rel)
        scope=load(out/'inputs/immutable_scope_pinned.json')
        need(hashlib.sha256(c.canonical(scope['requirements'])).hexdigest()==REQUIREMENTS,'fixed H01-H15 requirements hash')
        need([r['id']for r in scope['requirements']]==[f'H{i:02d}'for i in range(1,16)],'all15requirements')
        # Guard original bytes BEFORE JSON decode; this is not a live source.
        a18=out/'inputs/retired-source70.json'
        need(a18.stat().st_size==82496 and sha(a18)==c.EXPECTED_A18_SHA,'exact original A18 bytes')
        need(sha(out/'inputs/BOARD50_102_MAIN_QUALITY_CORRECTION.json')==c.EXPECTED_CORRECTION_SHA,'main quality correction pin')
        need(sha(out/'inputs/ModelSim_vlog_manual.html')==MANUAL_SHA,'local compiler manual pin')
        save(out/'GUARDS.json',dict(status='actual_owned_job_guards_passed',requirements_sha256=REQUIREMENTS,readonly_source_pins=c.SOURCE_PINS,
             main102_quality=[5,5,5,1],old95_observation='FALSE_FAILURE_PROVENANCE_ONLY',manual_sha256=MANUAL_SHA))
        sim=out/'sim';sim.mkdir()
        commands=[]
        commands.append(command(out,'00-vlog-version',[MODEL/'vlog.exe','-version'],sim))
        commands.append(command(out,'01-vsim-version',[MODEL/'vsim.exe','-version'],sim))
        commands.append(command(out,'02-vmap-local',[MODEL/'vmap.exe','-c'],sim))
        commands.append(command(out,'03-vlib',[MODEL/'vlib.exe','work'],sim))
        sources=[W/rel for rel in c.SOURCE_PINS if rel.endswith('.sv')]
        commands.append(command(out,'04-vlog',[MODEL/'vlog.exe','-sv','-svinputport=var','-work','work',*sources,W/BENCH],sim))
        log=(out/'commands/04-vlog.stdout.bin').read_text(encoding='utf-8',errors='replace')
        need('Errors: 0'in log and '** Error:'not in log and '** Fatal:'not in log,'actual compile result')
        do=sim/'run.do'
        do.write_text('onerror {quit -code 3 -force}\nonbreak {\nif {[examine -radix decimal /tb_deepeye_trace50_axi95/completed] == 1} {quit -code 0 -force}\nquit -code 4 -force\n}\nrun -all\nif {[examine -radix decimal /tb_deepeye_trace50_axi95/completed] == 1} {quit -code 0 -force}\nquit -code 4 -force\n',encoding='ascii')
        commands.append(command(out,'05-vsim',[MODEL/'vsim.exe','-c','-voptargs=+acc','-onfinish','stop','-wlf',sim/'wave.wlf','-l',sim/'modelsim.log',
          'work.tb_deepeye_trace50_axi95','+OUT='+sim.as_posix(),'-do','do '+do.as_posix()],sim))
        log=(sim/'modelsim.log').read_text(encoding='utf-8',errors='replace')
        need('B95_DONE'in log and '** Fatal:'not in log and '** Error:'not in log and 'Errors: 0'in log,'actual simulator completion')
        commands.append(command(out,'06-check102',[sys.executable,'-B',W/REL/'check95.py','--out',out],sim))
        save(out/'INNER_RESULT.json',dict(status='FOCUSED102_COMPLETED_PENDING_MAIN',commands=commands,completed_utc=utc()))
        return 0
    except BaseException:
        error=traceback.format_exc();save(out/'INNER_FAILURE.json',dict(status='FAILED_STOP_NO_RETRY',error=error,utc=utc()))
        print(error,file=sys.stderr);return 1

def outer():
    # This is the one authorized attempt's trusted snapshot/Job bootstrap,
    # not a candidate preflight. Failure is final; it never retries anything.
    out=SHORT;out.mkdir(parents=True,exist_ok=False)
    result=dict(schema='B102_FIRST_FUNCTIONAL_RESULT_V1',status='FAILED_STOP_NO_RETRY',task_id='DEEPEYE-IMPLEMENTATION-20261014',task_version=1,
      work_id=WORK,job_id='child-cb57e71fabbc41dba36acb32d796b9a6',canonical_agent_id='/root/offboard_codec74',actual_thread_id=os.environ.get('CODEX_THREAD_ID'),
      requirements_sha256=REQUIREMENTS,requirements_ids=[f'H{i:02d}'for i in range(1,16)],attempts_allowed=1,attempts_started=1,
      source94_commit='6ca1f039740fbef977c143d079bfb15beba14472',source94_sha256='9697494e1694ba84708b40542fd8b4ee2544bd85bd763b1104e695441d57c6e7',
      started_utc=utc(),bounds=dict(command_seconds=25,whole_job_seconds=120,polled_attempt_output_bytes=8*1024*1024,HDL_cycles=600000),
      source_scope='exact pre-commit source snapshots; no later commit claimed tested',current_source_eligible=False,status_all='STOP',command=None,core_ran=False,
      acceptance='NONE; parent quality main/A only',board='not_run; A only',Vivado='not_run',network_Git_services_SQL_credentials='not_used')
    save(out/'RESULT.json',result)
    before={};inputs={};owned_process=None
    try:
        review=load(P/'BOARD50_95_MAIN_REVIEW.json')
        selected=[W/r['path']for r in review['source94_files']+review['dependency_closure_verified']]
        selected += [W/rel for rel in [BENCH,REL+'/check95.py',REL+'/run102.py',OWNED,JOB,
          'competition/deepeye/tools/diagnostic/g05_capture/additive50_source_candidate/deepeye_transport50_source_candidate.py',
          'competition/deepeye/golden/codec/trace_candidate.py','competition/deepeye/tools/diagnostic/offboard_codec74/semantic_controls.py',
          'competition/deepeye/fpga/diagnostic/functional50_axi95/README.md',
          'competition/deepeye/golden/diagnostic/functional50_axi95/RECOVERY102_PLAN.json']]
        selected=list(dict.fromkeys(selected))
        snapshot=out/'source';snapshot.mkdir()
        for path in selected:
            rel=path.relative_to(W).as_posix();dest=snapshot/rel
            need(len(str(dest))<240,'snapshot path exceeds short path limit '+rel)
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())
            before[rel]=dict(original=record(path),snapshot=record(dest))
        save(out/'SOURCE_BEFORE.json',before)
        need(sha(snapshot/OWNED)==OWNED_SHA and sha(snapshot/JOB)==JOB_SHA,'pinned owned Job helpers')
        inp=out/'inputs';inp.mkdir()
        mapping={
          'retired-source70.json':P/'source-inputs/A18-retired-source70-r2/competition/deepeye/evidence/system/a-gen4-source70-retired-example-20261030/retired-source70.json',
          'PINS.json':P/'source-inputs/A18-retired-source70-r2/PINS.json',
          'A18_INDEPENDENT_DATA.json':P/'main-verification96/A18_INDEPENDENT_DATA.json',
          'immutable_scope_pinned.json':P/'immutable_scope_pinned.json',
          'SPEC_OBSERVATION_QUALITY.json':P/'board50-worker95/SPEC_OBSERVATION_QUALITY.json',
          'MAIN_STOP_AND_INVENTORY.json':P/'board95-stopped-original/MAIN_STOP_AND_INVENTORY.json',
          'ModelSim_vlog_manual.html':MANUAL,
        }
        for name in ['BOARD50_95_MAIN_FINAL_DESIGN.md','BOARD50_95_MAIN_REVIEW.json','BOARD50_95R1_DISPATCH_DECISION.json',
          'BOARD50_95R1_DISPATCH_RECEIPT.json','BOARD50_102_MAIN_RECOVERY.md','BOARD50_102_MAIN_QUALITY_CORRECTION.json','BOARD50_102_MAIN_TOOL_CHOICE.json']:
            mapping[name]=P/name
        for name,path in mapping.items():
            dest=inp/name;dest.write_bytes(path.read_bytes());inputs[name]=dict(original=record(path),snapshot=record(dest))
        save(out/'INPUT_PINS.json',inputs)
        spec=importlib.util.spec_from_file_location('_pinned102_owned',snapshot/OWNED)
        trusted=importlib.util.module_from_spec(spec);spec.loader.exec_module(trusted)
        jobout=out/'owned_job';jobout.mkdir()
        owned_process=trusted.run_owned([sys.executable,'-B',str(snapshot/REL/'run102.py'),'--inner','--out',str(out)],jobout,120,snapshot/JOB)
        result['process']=owned_process
        trusted.require_owned_success(owned_process);need(owned_process.get('job_closed')is True,'Job close proof')
        need((out/'INNER_RESULT.json').is_file()and(out/'SEMANTIC_RESULT.json').is_file(),'complete first attempt result')
        result['semantic']=load(out/'SEMANTIC_RESULT.json');result['status']='FOCUSED102_COMPLETED_PENDING_MAIN'
    except BaseException:
        result['error']=traceback.format_exc()
    finally:
        after={rel:dict(original=record(W/rel),snapshot=record(Path(info['snapshot']['path'])))for rel,info in before.items()}
        save(out/'SOURCE_AFTER.json',after)
        result['sources_unchanged']=all(before[r]['original']['sha256']==v['original']['sha256']==v['snapshot']['sha256']==before[r]['snapshot']['sha256']for r,v in after.items())
        if not result['sources_unchanged']:result['status']='FAILED_STOP_NO_RETRY';result['source_error']='selected source changed during one attempt'
        result['finished_utc']=utc();result['actual_attempt_bytes']=total_bytes(out)
        result['source_before']=record(out/'SOURCE_BEFORE.json')if(out/'SOURCE_BEFORE.json').exists()else None
        result['source_after']=record(out/'SOURCE_AFTER.json')
        result['tool_binaries']={n:record(MODEL/(n+'.exe'))for n in ['vmap','vlib','vlog','vsim']}
        result['python']=dict(executable=sys.executable,version=sys.version,sha256=sha(sys.executable))
        result['native_commands']=[load(f)for f in sorted((out/'commands').glob('*.json'))if not f.name.endswith('.STARTED.json')]if(out/'commands').exists()else []
        result['artifacts']=[record(f)for f in sorted(out.rglob('*'))if f.is_file()and f.name!='RESULT.json'and 'source'not in f.relative_to(out).parts and 'work'not in f.relative_to(out).parts and f.suffix!='.wlf']
        # Preserve any actual prefix even if a later runtime assertion fails.
        result['raw_bytes']={}
        for name in ['uart','pop']:
            f=out/'sim'/(name+'.hex')
            if f.exists():
                raw=bytes.fromhex(f.read_text(encoding='ascii'));binary=out/(name+'.bin');binary.write_bytes(raw)
                result['raw_bytes'][name]=dict(hex_file=record(f),binary=record(binary),byte_count=len(raw),hex=raw.hex())
        save(out/'RESULT.json',result)
        PRIVATE_OUT.mkdir(exist_ok=True)
        # Native result pointer contains actual finite-Job proof and exact data;
        # source/evidence remain at the short path, not at the sealed95 path.
        public=dict(result,short_result=record(out/'RESULT.json'))
        save(PRIVATE_OUT/'RESULT.json',public)
        print(json.dumps(dict(status=result['status'],result=str(PRIVATE_OUT/'RESULT.json'),result_sha256=sha(PRIVATE_OUT/'RESULT.json'),short_result=str(out/'RESULT.json'))))
    return 0 if result['status']=='FOCUSED102_COMPLETED_PENDING_MAIN'else 1

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--inner',action='store_true');a.add_argument('--out',type=Path);n=a.parse_args()
    raise SystemExit(inner(n.out.resolve())if n.inner else outer())
