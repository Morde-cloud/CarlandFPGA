// SOURCE ONLY. Active SWD hold and ONE RXDATA consume require a new main-approved operation.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const HERE=__dirname,REPO='D:/pynq/CarlandFPGA',HASH='2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d';
if(process.argv[3]!=='--execute-new-approved-operation'){
 console.log('SOURCE_ONLY_NOT_EXECUTED: no connection, CPU hold or RXDATA read.');
}else{
 const proofPath=process.argv[4];if(!proofPath)throw Error('Fresh main approval proof required');
 const proof=JSON.parse(fs.readFileSync(proofPath,'utf8'));
 const bindings={boot_id:'e764fa92-e676-4b0a-95f4-778f20918d2f',build_id:'76bea92ec0d97e37250733bad1eb3a38',parent_operation:'A-GEN4-JOINT-UART-BOARD-20261104-1018-R01',parent_request_hash:'c5d09eb3c9ef754fc5996d27f1e89dd1345faf37bd81de6bb470aa2cc57ddd19'};
 for(const[k,v]of Object.entries(bindings))if(proof[k]!==v)throw Error('Actual physical identity proof differs: '+k);
 if(proof.schema!=='B_NEW_SINGLE_BYTE_RX_APPROVAL_V1'||proof.requirements_sha256!==HASH||proof.source_sha256!==sha(fs.readFileSync(__filename))||proof.expected_byte!==0x55||proof.bytes_permitted!==1||proof.CPU_hold_allowed!==true||proof.single_RXDATA_consume_allowed!==true||proof.new_operation_not_retry!==true||proof.XDS_isolated_confirmed!==true||proof.three_wires_common_ground_seated_confirmed!==true||proof.A_bytes_already_sent!==0||proof.A_holds_new_TX_only_owner!==true||proof.B_other_MCU_actors_closed!==true||!proof.authenticated_A_ready_event_id||!proof.authenticated_wire_receipt_event_id||!proof.A_operation_id||!/^B-MCU-RX-NEW-[A-Za-z0-9_-]+$/.test(proof.B_operation_id))throw Error('New explicitly approved single-byte operation required');
 const now=Date.now(),created=Date.parse(proof.created_utc),expires=Date.parse(proof.expires_utc);
 if(!Number.isFinite(created)||!Number.isFinite(expires)||created>now||expires<now||expires-created>120000)throw Error('Fresh approval max120s required');
 if(sha(fs.readFileSync(proof.A_ready_raw_path))!==proof.A_ready_raw_sha256)throw Error('Retained actual A ready bytes differ');
 const image=path.join(REPO,'output/drill-demo-code-20261025/motor_runtime/build/motor_probe.out');
 if(sha(fs.readFileSync(image))!=='69c5c57e6f896b879bb41a73d4f114180e11a9f16a8894eae6b035893848841f')throw Error('Frozen MTR4 ELF changed');
 const config=path.join(REPO,'.local/drill-demo-code-20261025/vendor-example/empty_LP_MSPM0G3507_nortos_ticlang/targetConfigs/MSPM0G3507.ccxml');
 const dependencies={
  [config]:'50d3cd02de2e579d75b6b86bce0504e2e92e7f7af71e876cf13b280072eed8b7',
  'C:/ti/ccs2100/ccs/ccs_base/common/targetdb/devices/MSPM0G3507.xml':'926091cef94c3bd48102d237b18f2aa6a08a6f8f0b1db2a074198344b0cd62db',
  'C:/ti/ccs2100/ccs/ccs_base/emulation/gel/mspm0g3507.gel':'c40e17581d95678ece5d4702ec03d5eb41b02130224a6ef640c99366739b3023',
  'C:/ti/ccs2100/ccs/ccs_base/DebugServer/propertyDB/MSPM0_FlashProperties.xml':'22cd07ad1ce2bab8bf3ba6081ac77846a6e75fd7f55bba0a42f7469eb613a4f1'
 };
 for(const[p,h]of Object.entries(dependencies))if(sha(fs.readFileSync(p))!==h)throw Error('Reviewed CCS dependency changed: '+p);
 const O=path.join(HERE,proof.B_operation_id);fs.mkdirSync(O,{recursive:false});
 const out=path.join(O,'RX_CAPTURE.json'),rec={task_id:'DEEPEYE-IMPLEMENTATION-20261014',task_version:1,work_id:proof.B_operation_id,main_thread:'01a18824-4172-74e2-a13f-f3e3d1e3ed99',requirements_sha256:HASH,source_sha256:sha(fs.readFileSync(__filename)),proof_sha256:sha(fs.readFileSync(proofPath)),status:'intent_no_replay',started_utc:new Date().toISOString(),reset_requested:false,flash_programmed:false,memory_writes:0,UART_TX_writes:0,RXDATA_reads_requested:0,RXDATA_reads_returned:0,samples:[]};
 fs.writeFileSync(out,JSON.stringify(rec,null,2),{flag:'wx'});const save=()=>fs.writeFileSync(out,JSON.stringify(rec,null,2));
 rec.CCS_dependency_sha256=dependencies;rec.memory_writes_scope='No explicit script memory writes. Debug transport/CPU halt is active; no bus trace asserting absence of internal debugger writes.';save();
 const ds=initScripting();ds.setScriptingTimeout(15000);let s;
 const startNs=process.hrtime.bigint(),budgetNs=60000000000n;
 function guard(stage){const remaining=Number((budgetNs-(process.hrtime.bigint()-startNs))/1000000n);if(remaining<=0||Date.now()>=expires)throw Error('Diagnostic active budget/approval expired at '+stage+'; no further diagnostic action');ds.setScriptingTimeout(Math.min(15000,remaining));return remaining;}
 function waitForDebugOff(){guard('debug setting read');const actual=s.settings.get('EnableWaitForDebug');rec.EnableWaitForDebug_actual=actual;save();if(actual!==false&&actual!==0)throw Error('Conditional GEL reset path not excluded; no connect/fileload');}
 function bytes(a,n){guard('memory.read');const start=Math.floor(a/4)*4,offset=a-start,count=Math.ceil((offset+n)/4),words=s.memory.read(BigInt(start),count,32);if(words.length!==count)throw Error('Short read');const b=Buffer.alloc(count*4);words.forEach((v,i)=>b.writeUInt32LE(Number(v)>>>0,4*i));return b.subarray(offset,offset+n);}
 function word(a){return bytes(a,4).readUInt32LE(0);}
 function sample(label){const b=bytes(0x20200000,172),m=bytes(0x202001b0,16),pc=bytes(0x2020012e,130),i=rec.samples.length;
  for(const[n,raw]of Object.entries({free:b,motor:m,pc_tx:pc}))fs.writeFileSync(path.join(O,n+'-'+i+'.bin'),raw,{flag:'wx'});
  guard('CPU-state query');const d={label,at_utc:new Date().toISOString(),cpu_halted:s.target.isHalted(),signature:b.readUInt32LE(52),state:b.readUInt32LE(56),last_seq:b.readUInt32LE(0),armed:b[34],have_seq:b[37],motor_duty:m.readUInt16LE(12),motor_active:m[14],PWM_applied:word(0x202001d4),pc_head:pc[128],pc_tail:pc[129],ticks:word(0x202001c0),PDBGCTL:word(0x40101018),CTL0:word(0x40101100),LCRH:word(0x40101104),STAT:word(0x40101108),IBRD:word(0x40101110),FBRD:word(0x40101114),PB6_mux:word(0x4042805c),PB7_mux:word(0x40428060)};rec.samples.push(d);save();return d;
 }
 function faultOff(d){if(d.signature!==0x4d545234||d.state!==4||d.last_seq!==0||d.have_seq||d.armed||d.motor_duty||d.motor_active||d.PWM_applied||d.pc_head!==d.pc_tail)throw Error('Changed MCU state; no receive consume');}
 try{
  guard('configure');ds.configure(config);guard('openSession');s=ds.openSession(/CORTEX_M0P$/i);
  waitForDebugOff();guard('connect');rec.connect_intent_utc=new Date().toISOString();save();s.target.connect();rec.connect_returned=true;save();
  waitForDebugOff();guard('symbols.load');s.symbols.load(image);
  const pre=sample('after_connect');faultOff(pre);
  if(pre.CTL0!==0x20039||pre.LCRH!==0x30||pre.IBRD!==17||pre.FBRD!==23||pre.PB6_mux!==0x82||pre.PB7_mux!==0x40082||(pre.PDBGCTL&1)!==1||(pre.STAT&0x44)!==0x44||(pre.STAT&1))throw Error('Known idle UART/PDBG FREE/mux required; no configuration change');
  if(!pre.cpu_halted){guard('halt');rec.halt_intent_utc=new Date().toISOString();save();s.target.halt();rec.halt_returned=true;save();}
  const held=sample('held_before_A_TX');faultOff(held);
  if(!held.cpu_halted||(held.STAT&4)!==4||held.PDBGCTL!==pre.PDBGCTL)throw Error('Hold/empty FIFO changed');
  const remaining=guard('B ready');const ready={schema:'B_SINGLE_BYTE_RX_HELD_READY_V1',B_operation_id:proof.B_operation_id,A_operation_id:proof.A_operation_id,expected_byte:85,CPU_held:true,PDBG_FREE:true,RX_empty:true,source_sha256:rec.source_sha256,proof_sha256:rec.proof_sha256,ready_utc:new Date().toISOString(),ready_valid_until_utc:new Date(Math.min(expires,Date.now()+remaining)).toISOString(),active_budget_ms:60000,hard_CPU_hold_ceiling_guaranteed:false,...bindings};
  fs.writeFileSync(path.join(O,'B_READY.json'),JSON.stringify(ready,null,2),{flag:'wx'});rec.ready_written=true;save();
  const resultPath=path.join(O,'A_TX_RESULT.json');
  while(!fs.existsSync(resultPath)){guard('A terminal receipt wait');sleep(100);}
  guard('A terminal receipt validation');const aBytes=fs.readFileSync(resultPath),a=JSON.parse(aBytes);rec.A_result_sha256=sha(aBytes);save();
  for(const[k,v]of Object.entries(bindings))if(a[k]!==v)throw Error('A terminal identity differs');
  if(a.schema!=='A_SINGLE_BYTE_TX_CLOSED_V1'||a.A_operation_id!==proof.A_operation_id||a.B_operation_id!==proof.B_operation_id||a.B_ready_sha256!==sha(fs.readFileSync(path.join(O,'B_READY.json')))||a.byte!==85||a.TX_writes_requested!==1||a.TX_writes_returned!==1||a.A_actors_closed!==true||a.same_owner_lock_released!==true||a.reset_requested!==false||a.FIFO_flush!==false||a.MTR4_frames!==0||a.automatic_retry!==false||!a.authenticated_A_event_id||!a.raw_result_path||sha(fs.readFileSync(a.raw_result_path))!==a.raw_result_sha256)throw Error('Main-authenticated exact once-only A terminal proof required');
  while((word(0x40101108)&4)!==0){guard('incoming byte wait');sleep(10);}
  const before=sample('before_single_RXDATA');faultOff(before);if(!before.cpu_halted||before.PDBGCTL!==pre.PDBGCTL)throw Error('CPU hold/PDBG changed');
  guard('single RXDATA intent');rec.RXDATA_reads_requested=1;rec.RXDATA_read_intent_utc=new Date().toISOString();save();
  const raw=word(0x40101124);rec.RXDATA_reads_returned=1;rec.raw_RXDATA=raw;rec.byte=raw&255;rec.error_bits=raw&0x1f00;save();
  const after=sample('after_single_RXDATA');faultOff(after);
  if(rec.byte!==85||rec.error_bits!==0||(after.STAT&4)!==4||!after.cpu_halted||after.PDBGCTL!==pre.PDBGCTL)throw Error('Byte/error/remaining FIFO/CPU unexpected; no automatic consume or resume');
  guard('explicit successful resume');rec.resume_intent_utc=new Date().toISOString();save();s.target.run(false);rec.resume_returned=true;save();sleep(50);
  const final=sample('final_after_explicit_resume');faultOff(final);if(final.cpu_halted)throw Error('Final CPU not running');
  rec.status='single_raw55_received_MCU_READY_still_false';rec.MCU_READY=false;
 }catch(e){rec.status='failed_or_unknown_no_replay_no_automatic_resume';rec.error=String(e);}
 finally{try{if(s&&s.target.isConnected())rec.cpu_halted_before_shutdown=s.target.isHalted();}catch(e){rec.cpu_query_error=String(e);}try{ds.shutdown();rec.shutdown_returned=true;}catch(e){rec.shutdown_error=String(e);rec.status='failed_or_unknown_no_replay_no_automatic_resume';}rec.closed_utc=new Date().toISOString();save();}
 console.log(JSON.stringify({status:rec.status,evidence:out,reads_requested:rec.RXDATA_reads_requested,reads_returned:rec.RXDATA_reads_returned,cpu_halted_before_shutdown:rec.cpu_halted_before_shutdown,error:rec.error}));
 if(rec.status!=='single_raw55_received_MCU_READY_still_false')process.exit(1);
}
