"""Offline exact evidence verification. Opens no device, port or connection."""
from pathlib import Path
import binascii,hashlib,io,json,struct,tarfile
D=Path(__file__).resolve().parent;W=D.parents[2];R=D/'evidence/raw'
sha=lambda b:hashlib.sha256(b).hexdigest()
idx=json.loads((R/'BUNDLE_INDEX.json').read_bytes());parts=[]
for row in idx['parts']:
 b=(R/row['path']).read_bytes();assert len(b)==row['size'] and sha(b)==row['sha256'];parts.append(b)
b=b''.join(parts);assert sha(b)==idx['archive_sha256'];raw={}
with tarfile.open(fileobj=io.BytesIO(b),mode='r:gz')as tar:
 members=tar.getmembers();assert len(members)==idx['member_count']==len(idx['members'])
 for m,row in zip(members,idx['members']):
  assert m.isfile() and m.name==row['path'] and not m.name.startswith('/') and '..' not in Path(m.name).parts
  q=tar.extractfile(m).read();assert len(q)==row['size'] and sha(q)==row['sha256'];raw[m.name]=q
load=lambda n:json.loads(raw[n]);source=load('SOURCE505.json')
for path,digest in source['source_hashes'].items():assert sha((W/path).read_bytes())==digest,path
calls=load('mcu-build5-evidence/COMMANDS.json');assert len(calls)==16 and all(c['exit_code']==0 for c in calls)
for i,c in enumerate(calls):
 for ext in ('stdout','stderr'):assert sha(raw[f'mcu-build5-evidence/{i:02}.{ext}'])==c[ext+'_sha256']
assert b'STARTUP_PREPARE_PASS checks=24' in raw['mcu-build5-evidence/05.stdout']
assert load('CROSS505_PROCESS.json')['exit_code']==0 and b'PYTHON_STARTUP_FRAME_ACCEPTED' in raw['CROSS505.stdout']
assert all(c['exit_code']==0 for c in load('BOOT506b_COMMANDS.json'))
assert b'STARTUP_BOOT_PASS' in raw['BOOT506b_boot.stdout']
host=load('host503/RESULT503.json');assert host['tests']['tests']==12 and host['tests']['exit_code']==0 and host['release_all_host_writes']
assert load('host503/TEST503_PROCESS.json')['exit_code']==0 and b'Ran 12 tests' in raw['host503/TEST503.stderr.txt']
events=[json.loads(x)for x in raw['A171/uart-events.jsonl'].splitlines()];tx=[];rx=[]
for row in events:
 for field in ('frame_hex','request_hex','reply_hex'):
  if field in row:
   q=bytes.fromhex(row[field]);assert len(q)==32 and binascii.crc_hqx(q[:30],65535)==int.from_bytes(q[30:],'little')
 if row['event']=='uart_write_intent':tx.append(bytes.fromhex(row['frame_hex']))
 if row['event']=='uart_reply_bytes':rx.append((bytes.fromhex(row['request_hex']),bytes.fromhex(row['reply_hex'])))
assert len(tx)==len(rx)==257 and [a for a,b in rx]==tx
assert [int.from_bytes(q[4:8],'little')for q in tx]==list(range(45,302))
for a,b in rx:assert a[4:8]==b[4:8] and b[9]==0
a,b=rx[-1];assert a[3]==3 and b[8]==0 and b[14:16]==b'\0\0' and b[18]&3==3 and b[19]==0 and b[28:30]==b'\0\0'
ps=load('A171/PS_READBACK_ACTUAL.json');assert ps['actors']==[] and not ps['UART'] and not ps['PL'] and ps['lock']['release_returned']
audit=load('A171/HOST_RESULT.json')['physical_follow']['transport_audit'];assert audit['returncode']==0 and audit['reader_joined'] and audit['wait_completed'] and not audit['close_errors']
assert all(audit[k]for k in ('stdin_closed','stdout_closed','stderr_closed')) and audit['stop_error_type'] is None
desc=load('A171/G05_CAPTURE_DESCRIPTOR.json');assert not desc['full_stream_hashed'] and sha(raw['A171/G05_STREAM_TAIL.original.bin'])==desc['tail_sha256']
terminal=json.loads(raw['A171/G05_STREAM_TAIL.original.bin'].splitlines()[-1]);assert terminal==desc['last_complete_record'] and terminal['closed'] and not terminal['stop_unknown']
assert load('A171/G05_CLOSED.json')['stop_response'] is None
child=load('A172/child-manifest.json');assert sha(raw['A172/child-request-body.json'])==child['request_sha256']
prev=child['predecessor'];assert prev['closed_record_sha256']==sha(raw['A172/closed-record.json']) and prev['events_sha256']==sha(raw['A171/uart-events.jsonl']) and prev['binding_sha256']==sha(raw['A171/binding.json'])
deploy=load('deploy507/actual/DEPLOY.json');assert deploy['load_program_intents']==deploy['load_program_returns']==1 and deploy['shutdown_returned'] and not deploy['cpu_halted_before_shutdown'] and deploy['MCU_READY']
assert load('deploy507/RUN507_PROCESS.json')['exit_code']==0 and deploy['code_commit']==source['source_commit']
for seg in deploy['flash_readback']:
 q=raw[f"deploy507/actual/flash-{seg['address']}.bin"];assert len(q)==seg['bytes'] and sha(q)==seg['actual_sha256']==seg['expected_sha256']
last=deploy['samples'][-1];assert last['armed']==last['motor_duty']==last['PWM_applied']==last['tx_moves']==last['prepared_valid']==last['startup_pose_pending']==0 and last['state']==3 and last['preflight']==8
assert last['feedback_seen']==[1,1] and all(0<=last['ticks']-v<=1000 for v in last['feedback_ms'])
g=raw['deploy507/actual/free-2.bin'];m=raw['deploy507/actual/motor-2.bin'];assert len(g)==172 and len(m)==40
assert g[34]==0 and g[171]==0 and int.from_bytes(m[12:14],'little')==0 and m[14]==m[39]==0
assert deploy['saved_reference']==[0x47524331,1,2088,1961] and deploy['UART_TX_writes']==deploy['UART_RXDATA_reads']==0
obs=load('MCU_OBSERVATION508.json');t=load('transfer509/B_TRANSFER.json');assert t['evidence_sha256']==sha(raw['MCU_OBSERVATION508.json']) and t['last_seq']==301 and obs['persistent_next_seq']==302 and obs['old44_wire_ACK_remains_unknown']
assert t['operation_id']==child['operation_id']=='A-GEN4-UART-ACTUATOR-20261104-1392-R01'
print(json.dumps(dict(raw_members=len(raw),CRC_frames_checked=len(tx)+len(rx),last_ACK301_OFF=True,next_seq=302,source_commit=source['source_commit'],MCU_once_deployed_OFF_SDK0=True,host_tests=12,hardware_actions_by_this_verifier=0,physical_opcode8_acceptance=False,formal_all29=False)))
