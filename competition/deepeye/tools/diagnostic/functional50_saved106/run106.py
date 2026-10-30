"""One NEW106 software-checker Job on sealed104 evidence; no vendor/Git calls."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import argparse,datetime,hashlib,importlib.util,json,os,subprocess,time,traceback
from pathlib import Path
R=Path('D:/pynq/CarlandFPGA');W=Path(__file__).resolve().parents[5]
P=R/'.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-74'
OUT=R/'.local/v106/attempt-01';SAVED=R/'.local/v104/attempt-01'
REL='competition/deepeye/tools/diagnostic/functional50_saved106'
OWNED='competition/deepeye/tools/diagnostic/g05_capture/build/owned_process.py'
JOB='fpga_mesh/windows_job.py'
OWNED_SHA='1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692'
JOB_SHA='3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3'
RESULT104=P/'board50-worker104/RESULT.json'
RESULT104_SHA='3e2630ba3ca0a28c23b7e50cee98db7e9f780ec8263af0158930312c81e8b3f1'
AUDIT=P/'main-verification104/INDEPENDENT_SAVED_BYTES.json'
AUDIT_SHA='c1a21c77000932ce9d2195f4564e2f3a3e6cecb0a9b24be65a32fa9785d554d9'
REQUIREMENTS='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
WORK='B-DEEPEYE-TRACE50-SAVED104-SEMANTICS-20261031-106'
COMMIT104='7ab2614a3996e51983b81856cfc5bb9fcb026ba0'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rec(p):p=Path(p);return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def need(ok,why):
    if not ok:raise RuntimeError(why)
def size(out):
    n=0
    for f in out.rglob('*'):
        try:
            if f.is_file():n+=f.stat().st_size
        except FileNotFoundError:pass
    return n
def inner(out):
    # Only this corrected checker process executes inside the owned Job.
    d=out/'commands';d.mkdir(exist_ok=True)
    info=dict(argv=[sys.executable,'-B',str(W/REL/'check106.py'),'--out',str(out)],cwd=str(out),started_utc=utc(),timeout_seconds=25)
    try:
        with(d/'00-check106.stdout.bin').open('xb')as so,(d/'00-check106.stderr.bin').open('xb')as se:
            proc=subprocess.Popen(info['argv'],cwd=out,stdin=subprocess.DEVNULL,stdout=so,stderr=se,shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
            info['pid']=proc.pid;save(d/'00-check106.STARTED.json',info)
            deadline=time.monotonic()+25
            try:
                while proc.poll()is None:
                    need(time.monotonic()<deadline,'25s corrected-checker deadline')
                    n=size(out);info['max_polled_output_bytes']=max(n,info.get('max_polled_output_bytes',0))
                    need(n<=8*1024*1024,'8MiB output cap');time.sleep(.04)
                info['exit_code']=proc.returncode
            except BaseException:
                proc.kill();info['exit_code']=proc.wait(timeout=5);raise
        need(info['exit_code']==0,'corrected saved104 checker failed; STOP/no retry')
        need(size(out)<=8*1024*1024,'8MiB final output cap')
        save(out/'INNER_RESULT106.json',dict(status='SAVED104_CHECKER106_COMPLETED_PENDING_MAIN',utc=utc()))
        return 0
    except BaseException:
        info['error']=traceback.format_exc();save(out/'INNER_FAILURE106.json',dict(status='FAILED_STOP_NO_RETRY',error=info['error']));print(info['error'],file=sys.stderr);return 1
    finally:
        info.update(ended_utc=utc(),stdout=rec(d/'00-check106.stdout.bin'),stderr=rec(d/'00-check106.stderr.bin'))
        save(d/'00-check106.json',info)

def outer(freeze_file,start_file):
    need(freeze_file is not None and start_file is not None,'main106 freeze and explicit START required')
    freeze=load(freeze_file);start=load(start_file)
    for x in [freeze,start]:need(x['task_id']=='DEEPEYE-IMPLEMENTATION-20261014'and x['task_version']==1 and x['work_id']==WORK,'main106 authorization identity')
    need(start['runtime_start']is True and start['freeze_sha256']==sha(freeze_file),'explicit START binds main106 freeze')
    need(type(freeze['source_commit'])is str and len(freeze['source_commit'])==40,'new106 checker source commit')
    required={REL+'/check106.py',REL+'/run106.py',REL+'/recovery106_plan.json',REL+'/README.md'}
    need(required.issubset(freeze['files']),'all new106 source files frozen')
    for rel,pin in freeze['files'].items():need(sha(W/rel)==pin,'main-frozen106 source '+rel)
    out=OUT;out.mkdir(parents=True,exist_ok=False)
    result=dict(schema='B106_SAVED104_CHECKER_RESULT_V1',status='FAILED_STOP_NO_RETRY',task_id='DEEPEYE-IMPLEMENTATION-20261014',task_version=1,work_id=WORK,
      job_id='child-5c7371e8000948a8a849493f9342f290',canonical_agent_id='/root/offboard_codec74',actual_thread_id=os.environ.get('CODEX_THREAD_ID'),actual_main_thread='01a18824-4172-74e2-a13f-f3e3d1e3ed99',
      original104_source_commit=COMMIT104,original104_status='FAILED_OVERALL_PRESERVED',checker106_source_commit=freeze['source_commit'],
      requirements_sha256=REQUIREMENTS,requirements_ids=[f'H{i:02d}'for i in range(1,16)],started_utc=utc(),attempts_started=1,attempts_allowed=1,
      execution_scope='ONLY new106 corrected software checker; no RTL/vendor/Git/version commands',bounds=dict(command_seconds=25,Job_seconds=120,polled_output_bytes=8*1024*1024),
      current_source_eligible=False,command=None,core_ran=False,board='not_run; A only',Vivado='not_run',acceptance='NONE; main/A only')
    save(out/'RESULT.json',result)
    references={};copy_map={};new_before={}
    def copy(path,dest):
        path=Path(path);dest=Path(dest);dest.parent.mkdir(parents=True,exist_ok=True)
        old=rec(path);references[str(path)]=old;dest.write_bytes(path.read_bytes())
        need(sha(dest)==old['sha256'],'exact byte copy');copy_map[str(dest.relative_to(out))]=dict(original=old,copy=rec(dest))
    try:
        need(sha(RESULT104)==RESULT104_SHA,'immutable original104 result pin');need(sha(AUDIT)==AUDIT_SHA,'main independent audit pin')
        old_result=load(RESULT104);need(old_result['source_commit']==COMMIT104 and old_result['status']=='FAILED_STOP_NO_RETRY','old104 failure remains')
        before104=load(SAVED/'SOURCE_BEFORE.json');audit=load(AUDIT)
        # Reuse only required modules/bench/helpers. Never read/import/copy an
        # old102/104 whole runner. Original26-source manifest stays byte-exact.
        review=load(SAVED/'inputs/BOARD50_95_MAIN_REVIEW.json')
        required_old=[r['path']for r in review['source94_files']+review['dependency_closure_verified']]
        required_old += [OWNED,JOB,'competition/deepeye/fpga/diagnostic/functional50_axi95/tb_deepeye_trace50_axi95.sv',
          'competition/deepeye/tools/diagnostic/g05_capture/additive50_source_candidate/deepeye_transport50_source_candidate.py',
          'competition/deepeye/golden/codec/trace_candidate.py','competition/deepeye/tools/diagnostic/offboard_codec74/semantic_controls.py']
        snapshot=out/'source';snapshot.mkdir()
        for rel in dict.fromkeys(required_old):
            src=Path(before104[rel]['snapshot']['path']);need(sha(src)==before104[rel]['snapshot']['sha256'],'audited104 source dependency '+rel)
            copy(src,snapshot/rel)
        for rel in sorted(required):
            src=W/rel;dest=snapshot/rel;need(len(str(dest))<240,'new106 short source path')
            copy(src,dest);new_before[rel]=dict(original=rec(src),snapshot=rec(dest))
        save(out/'CHECKER106_SOURCE_BEFORE.json',new_before)
        copy(SAVED/'SOURCE_BEFORE.json',out/'SOURCE_BEFORE.json')
        copy(SAVED/'SOURCE_AFTER.json',out/'SAVED104_SOURCE_AFTER.json')
        copy(RESULT104,out/'reused104/RESULT.json')
        copy(SAVED/'owned_job/PROCESS.json',out/'reused104/PROCESS.json')
        copy(AUDIT,out/'inputs/INDEPENDENT_SAVED_BYTES.json')
        for name in ['retired-source70.json','PINS.json','A18_INDEPENDENT_DATA.json','immutable_scope_pinned.json','BOARD50_95_MAIN_FINAL_DESIGN.md',
            'BOARD50_95_MAIN_REVIEW.json','BOARD50_95R1_DISPATCH_DECISION.json','BOARD50_95R1_DISPATCH_RECEIPT.json',
            'BOARD50_102_MAIN_QUALITY_CORRECTION.json','SPEC_OBSERVATION_QUALITY.json','MAIN_FREEZE.json']:
            copy(SAVED/'inputs'/name,out/'inputs'/name)
        for name in ['uart.hex','pop.hex','events.txt','modelsim.log']:copy(SAVED/'sim'/name,out/'sim'/name)
        copy(SAVED/'commands/04-vlog.stdout.bin',out/'commands/04-vlog.stdout.bin')
        for f in sorted((SAVED/'commands').iterdir()):
            if f.is_file():copy(f,out/'reused104/commands'/f.name)
        # Reference original decoded artifacts by hash only; NEVER copy them to
        # fresh decoded/ output. The new checker reconstructs every artifact.
        for index,row in enumerate(audit['rows']):
            for name,pin in [(f'companion{index:03d}.json',row['companion_sha256']),(f'frame{index:03d}.bin',row['wire_sha256'])]:
                p=SAVED/'decoded'/name;need(sha(p)==pin,'sealed104 original comparison artifact');references[str(p)]=rec(p)
        copy(P/'MAIN_IDENTITY_TRANSCRIPTION_CORRECTION_20261031.json',out/'inputs/MAIN_IDENTITY_ERRATUM.json')
        copy(P/'BOARD50_106_MAIN_ASSIGNMENT.md',out/'inputs/BOARD50_106_MAIN_ASSIGNMENT.md')
        copy(freeze_file,out/'inputs/CHECKER106_MAIN_FREEZE.json');copy(start_file,out/'inputs/CHECKER106_RUNTIME_START.json')
        save(out/'COPY_MAP106.json',copy_map);save(out/'SAVED104_REFERENCE_BEFORE.json',references)
        need(sha(snapshot/OWNED)==OWNED_SHA and sha(snapshot/JOB)==JOB_SHA,'pinned Windows Job helpers')
        spec=importlib.util.spec_from_file_location('_trusted106_owned',snapshot/OWNED);trusted=importlib.util.module_from_spec(spec);spec.loader.exec_module(trusted)
        d=out/'owned_job';d.mkdir()
        process=trusted.run_owned([sys.executable,'-B',str(snapshot/REL/'run106.py'),'--inner','--out',str(out)],d,120,snapshot/JOB)
        result['process']=process;trusted.require_owned_success(process);need(process['job_closed'],'Job closure')
        semantic=load(out/'SEMANTIC_RESULT.json');need(semantic['status']=='SAVED104_CHECKER106_COMPLETED_PENDING_MAIN','new106 checker result')
        need((out/'INNER_RESULT106.json').is_file(),'owned checker complete')
        result.update(status='SAVED104_CHECKER106_COMPLETED_PENDING_MAIN',semantic=semantic)
    except BaseException:result['error']=traceback.format_exc()
    finally:
        after={rel:dict(original=rec(W/rel),snapshot=rec(Path(r['snapshot']['path'])))for rel,r in new_before.items()}
        save(out/'CHECKER106_SOURCE_AFTER.json',after)
        reference_after={path:rec(Path(path))for path in references};save(out/'SAVED104_REFERENCE_AFTER.json',reference_after)
        result['new_sources_unchanged']=all(r['original']['sha256']==after[rel]['original']['sha256']==r['snapshot']['sha256']==after[rel]['snapshot']['sha256']for rel,r in new_before.items())
        result['immutable_references_unchanged']=all(r['sha256']==reference_after[path]['sha256']for path,r in references.items())
        if not result['new_sources_unchanged']or not result['immutable_references_unchanged']:result['status']='FAILED_STOP_NO_RETRY';result['integrity_error']='source/reference changed'
        result['original104_result']=dict(path=str(RESULT104),sha256=RESULT104_SHA,status='FAILED_STOP_NO_RETRY')
        result['actual_new_command']=load(out/'commands/00-check106.json')if(out/'commands/00-check106.json').exists()else None
        result['reused104_native_commands']=old_result['native_commands']if'old_result'in locals()else []
        result['python']=dict(executable=sys.executable,version=sys.version,sha256=sha(sys.executable));result['finished_utc']=utc();result['actual_output_bytes']=size(out)
        result['artifacts']=[rec(f)for f in sorted(out.rglob('*'))if f.is_file()and f.name!='RESULT.json'and 'source'not in f.relative_to(out).parts and 'work'not in f.relative_to(out).parts]
        save(out/'RESULT.json',result)
        target=P/'board50-worker106/RESULT.json';save(target,dict(result,short_result=rec(out/'RESULT.json')))
        print(json.dumps(dict(status=result['status'],result=str(target),sha256=sha(target))))
    return 0 if result['status']=='SAVED104_CHECKER106_COMPLETED_PENDING_MAIN'else 1
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--inner',action='store_true');a.add_argument('--out',type=Path);a.add_argument('--freeze',type=Path);a.add_argument('--runtime-start',type=Path);n=a.parse_args()
    raise SystemExit(inner(n.out.resolve())if n.inner else outer(n.freeze,n.runtime_start))
