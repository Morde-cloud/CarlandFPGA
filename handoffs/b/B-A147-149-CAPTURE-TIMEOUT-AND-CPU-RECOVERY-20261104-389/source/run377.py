from pathlib import Path
import base64,datetime,hashlib,json,subprocess,sys,time
P=Path(__file__).resolve().parent;O=P/'rx377';op='B-MCU-RX-NEW-A1134-20261104-377';script=O/'rx_single_byte377.js';approval=P/'APPROVAL377.json'
load=lambda p:json.loads(p.read_bytes());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
decision=load(P/'MAIN_APPROVE377.json');assert decision['execution_allowed'] is True and decision['B_operation_id']==op and decision['source_sha256']==sha(script)=='6039df82a3420f1d6993071adff0852b6e002bbad7016114cc1017b3c90c4881'
assert decision['fresh_A_coordination_event_id'] and decision['A_actor_currently_live_confirmed'] and decision['A_enforces_B_META_deadline_confirmed'] and decision['native375_actual_terminal_verified']
assert sha(Path(decision['fresh_A_coordination_raw_path']))==decision['fresh_A_coordination_raw_sha256']
now=datetime.datetime.now(datetime.timezone.utc);proof=load(P/'APPROVAL377_TEMPLATE.json');proof.update(created_utc=now.isoformat(),expires_utc=(now+datetime.timedelta(seconds=120)).isoformat())
assert proof['source_sha256']==sha(script) and proof['B_operation_id']==op
with approval.open('x',encoding='utf-8') as f:json.dump(proof,f,ensure_ascii=False,indent=2)
argv=['cmd.exe','/d','/c','C:/ti/ccs2100/ccs/scripting/run.bat',str(script),'--execute-new-approved-operation',str(approval)]
r={'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'work_id':op,'operation_id':op,'main_thread':'01a18824-4172-74e2-a13f-f3e3d1e3ed99','actual_turn':'01a1a3e0-1f9c-79a0-9109-e2e96f1790c0','argv':argv,'script_sha256':sha(script),'approval_sha256':sha(approval),'main_decision_sha256':sha(P/'MAIN_APPROVE377.json'),'started_at_utc':now.isoformat(),'status':'intent_no_replay'}
record=P/'RX377_PROCESS.json'
with record.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
readydir=O/op;ready=readydir/'B_READY.json';meta=readydir/'B_READY_META.json';notified=False
with (P/'RX377.stdout.txt').open('xb') as stdout,(P/'RX377.stderr.txt').open('xb') as stderr:
 q=subprocess.Popen(argv,stdout=stdout,stderr=stderr);r.update(actual_wrapper_pid=q.pid,status='running');record.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
 while True:
  if ready.is_file() and meta.is_file() and not notified:
   readybytes=ready.read_bytes();metabytes=meta.read_bytes();notice={'phase':'ACTUAL_B_CAPTURE_READY','B_operation_id':op,'actual_wrapper_pid':q.pid,'actual_script_pid':json.loads(metabytes)['actual_script_pid'],'ready':{'bytes':len(readybytes),'sha256':hashlib.sha256(readybytes).hexdigest(),'data_b64':base64.b64encode(readybytes).decode()},'meta':{'bytes':len(metabytes),'sha256':hashlib.sha256(metabytes).hexdigest(),'data_b64':base64.b64encode(metabytes).decode()}}
   notice.update(ready_record=json.loads(readybytes),meta_record=json.loads(metabytes),remaining_seconds_at_notice=(datetime.datetime.fromisoformat(json.loads(metabytes)['ready_valid_until_utc'].replace('Z','+00:00'))-datetime.datetime.now(datetime.timezone.utc)).total_seconds())
   with (P/'RX377_READY_NOTIFICATION.json').open('x',encoding='utf-8') as f:json.dump(notice,f,indent=2)
   print(json.dumps(notice),flush=True);notified=True
  code=q.poll()
  if code is not None:break
  time.sleep(.05)
r.update(exit_code=code,status='returned',finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),stdout_sha256=sha(P/'RX377.stdout.txt'),stderr_sha256=sha(P/'RX377.stderr.txt'))
record.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print(json.dumps(r),flush=True);sys.exit(code)
