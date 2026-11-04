"""Offline verification of original1392 records and documentary1423 handoff."""
from pathlib import Path
import ast,binascii,hashlib,io,json,tarfile
D=Path(__file__).resolve().parent;R=D/'evidence/raw';idx=json.loads((R/'BUNDLE_INDEX.json').read_bytes());sha=lambda b:hashlib.sha256(b).hexdigest();parts=[]
for row in idx['parts']:
 b=(R/row['path']).read_bytes();assert len(b)==row['size'] and sha(b)==row['sha256'];parts.append(b)
b=b''.join(parts);assert sha(b)==idx['archive_sha256'];raw={}
with tarfile.open(fileobj=io.BytesIO(b),mode='r:gz')as tar:
 members=tar.getmembers();assert len(members)==idx['member_count']==len(idx['members'])
 for m,row in zip(members,idx['members']):
  assert m.isfile() and m.name==row['path'] and not m.name.startswith('/') and '..'not in Path(m.name).parts
  data=tar.extractfile(m).read();assert len(data)==row['size'] and sha(data)==row['sha256'];raw[m.name]=data
load=lambda name:json.loads(raw[name]);rows=[json.loads(x)for x in raw['A174/uart-events.jsonl'].splitlines()];tx=[];rx=[]
for row in rows:
 assert row['operation_id']=='A-GEN4-UART-ACTUATOR-20261104-1392-R01' and row['simulation'] is False
 for key in ('frame_hex','reply_hex','request_hex'):
  if key in row:
   f=bytes.fromhex(row[key]);assert len(f)==32 and binascii.crc_hqx(f[:30],65535)==int.from_bytes(f[30:],'little')
 if row['event']=='uart_write_intent':tx.append(row)
 if row['event']=='uart_reply_bytes':rx.append(row)
assert len(tx)==len(rx)==213
assert [r['frame_hex']for r in tx]==[r['request_hex']for r in rx]
assert [int.from_bytes(bytes.fromhex(r['frame_hex'])[4:8],'little')for r in tx]==list(range(302,515))
by={}
for row in rx:
 a=bytes.fromhex(row['request_hex']);b=bytes.fromhex(row['reply_hex']);assert a[4:8]==b[4:8] and b[9]==0;by[int.from_bytes(a[4:8],'little')]=(a,b,row)
a,b,_=by[304];assert a[3]==8 and int.from_bytes(a[14:16],'little')==880 and b[8]==0 and b[10:16]==bytes(6)
a,b,_=by[307];assert a[3]==6 and int.from_bytes(a[14:16],'little',signed=True)==850 and int.from_bytes(b[14:16],'little')==675
a,b,r513=by[513];assert a[3]==6 and int.from_bytes(a[20:24],'little')==49 and b[8]==1 and int.from_bytes(b[14:16],'little')==625
a,b,_=by[514];assert a[3]==3 and b[8]==0 and b[14:16]==bytes(2) and b[18]&3==3 and b[19]==0 and b[28:30]==bytes(2)
r49=next(r for r in rows if r['event']=='existing_stream_command_intent' and r['request'].get('command_seq')==49)
assert r49['request']['source_valid_for_ms']==11369 and r49['request']['expires_ms']==110958
assert (r513['monotonic_ns']-r49['monotonic_ns'])/1e6==505.323458
host=load('A174/HOST_RESULT.json');worker=host['physical_follow']['worker'];audit=host['physical_follow']['transport_audit']
assert worker['startup_ready'] and int(worker['startup_ready_qpc_ns'])-int(worker['startup_ack_qpc_ns'])==1000000000
assert worker['last_common_seq']==48 and worker['last_attempted_common_seq']==49 and 'NO_REPLAY'in worker['stop_error']
assert load('A174/HOST_RETURNED.json')['exit_code']==2 and audit['returncode']==1 and audit['wait_completed'] and audit['reader_joined'] and all(audit[k]for k in ('stdin_closed','stdout_closed','stderr_closed'))
ps=load('A174/PS_READBACK_ACTUAL.json');assert not ps['UART'] and not ps['PL'] and ps['actors']==[] and ps['lock']['release_returned'] and ps['lock']['device']==45826 and ps['lock']['inode']==800403
g=load('A174/G05_CLOSED.json');assert g['exit_code']==0 and g['wait_confirmed'] and g['stop_response']['response']['request_seq']==121 and not g['physical_zero_capture_proven']
desc=load('A174/G05_CAPTURE_DESCRIPTOR.json');assert not desc['full_stream_hashed'] and sha(raw['A174/G05_STREAM_TAIL.original.bin'])==desc['tail_sha256']
last=json.loads(raw['A174/G05_STREAM_TAIL.original.bin'].splitlines()[-1]);assert last==desc['last_complete_record'] and last['closed'] and not last['stop_unknown']
child=load('A175/child-manifest.json');assert sha(raw['A175/child-request-body.json'])==child['request_sha256'] and len(raw['A175/child-request-body.json'])==1189
prev=child['predecessor'];assert prev['events_sha256']==sha(raw['A174/uart-events.jsonl']) and prev['closed_record_sha256']==sha(raw['A175/closed-record.json']) and prev['binding_sha256']==sha(raw['A174/binding.json']) and prev['sequence_sha256']==sha(raw['A174/sequence.json'])
assert load('A174/sequence.json')['next_seq']==515
ob=load('MCU_OBSERVATION529.json');transfer=load('transfer530/B_TRANSFER.json');assert transfer['evidence_sha256']==sha(raw['MCU_OBSERVATION529.json']) and transfer['last_seq']==514 and transfer['operation_id']==child['operation_id']
assert ob['not_a_new_SWD_or_live_CPU_observation'] and ob['current_CPU_RUNNING_not_newly_measured'] and ob['no_B_hardware_since_delivered509']
assert load('A174/binding.json')['transfer']==load('historical/B_TRANSFER509.json')
review=load('rpc528/REVIEW528.json');assert review['narrow_findings']==[] and review['AST_parse_both']
for row in review['source_files']:
 rel='A176/baseline_mtr4/fpga_link/ssh_client.py'if row['name']=='ssh_client.py'else 'A176/drill_live_link/compound_session.py'
 assert sha(raw[rel])==row['A176_sha256'];ast.parse(raw[rel])
result=load('rpc528/RESULT528.json');assert result['narrow_review_complete'] and result['all_owned_file_writes_released']
print(json.dumps(dict(raw_members=len(raw),CRC_frames_checked=426,last_ACK514_OFF=True,next_seq=515,actual513_executed_no_replay=True,Host_exit=2,MCU_service_exit=1,documentary_only_observation=True,new_MCU_live_measurement=False,A176_sources_readonly_reviewed=True,A_RED_GREEN_fixture_not_independently_reproduced=True,hardware_actions_by_this_verifier=0,formal_full_route_dualH12_all29=False)))
