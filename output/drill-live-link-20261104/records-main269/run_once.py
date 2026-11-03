from pathlib import Path
import datetime,hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent;R=HERE.parents[2];P=R/'.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-88'
freeze=json.loads((P/'SOURCE270.json').read_bytes());out=HERE/'evidence270';out.mkdir()
def pins():return {n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in freeze['files']}
before=pins();assert before==freeze['files'];argv=[sys.executable,'-B','-X','utf8',str(HERE/'test_archive_records.py')]
r=dict(task_id=freeze['task_id'],task_version=1,work_id='B-A127-ARCHIVAL-MAIN-CONTROLS-20261104-270',main_thread='01a18824-4172-74e2-a13f-f3e3d1e3ed99',source=freeze['source'],argv=argv,source_before=before,started_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),test_sha256=hashlib.sha256((HERE/'test_archive_records.py').read_bytes()).hexdigest())
(out/'RUN.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
with (out/'stdout.txt').open('xb') as stdout,(out/'stderr.txt').open('xb') as stderr:
 process=subprocess.Popen(argv,stdout=stdout,stderr=stderr);r['pid']=process.pid;code=process.wait()
r.update(exit_code=code,source_after=pins(),finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),stdout_sha256=hashlib.sha256((out/'stdout.txt').read_bytes()).hexdigest(),stderr_sha256=hashlib.sha256((out/'stderr.txt').read_bytes()).hexdigest());(out/'RUN.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');assert r['source_after']==before
result=dict(status='PASS_NEW_ARCHIVAL_BOUNDARIES' if code==0 else 'FAILED_NEW_ARCHIVAL_BOUNDARIES',count=10,actual_exit=code,source=freeze['source'],source_unchanged=True,hardware_actions=0,requirements_ids=freeze['requirements_ids'],requirements_sha256=freeze['requirements_sha256']);(out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result));raise SystemExit(code)
