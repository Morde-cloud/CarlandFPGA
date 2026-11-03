// B main: one inert MCU-TX -> FPGA-RX fixture after actual A142 RX-ready proof.
// No reset, flash, RXDATA read, PDBGCTL write, GPIO, servo or motor command.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const P=__dirname,REPO='D:/pynq/CarlandFPGA',op=process.argv[3],PATTERN=Buffer.from('55a533cc0ff06996','hex');
if(op!=='B-MCU-TX-FIXTURE-20261104-345')throw Error('Exact345operationrequired');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),proofPath=path.join(P,'A_RX_READY345.json'),proof=JSON.parse(fs.readFileSync(proofPath,'utf8'));
if(proof.phase!=='A142_RX_ONLY_READY_ACTUALLY_VERIFIED'||proof.pattern_hex!==PATTERN.toString('hex')||proof.boot_id!=='e764fa92-e676-4b0a-95f4-778f20918d2f'||proof.build_id!=='76bea92ec0d97e37250733bad1eb3a38'||proof.uart_base!==0x42c00000||!proof.authenticated_A_event_id||!proof.A_RX_FIFO_EMPTY||proof.A_TX_allowed!==false)throw Error('ActualauthenticatedA_RXreadyrequired');
if(!proof.raw_ready_path||sha(fs.readFileSync(proof.raw_ready_path))!==proof.raw_ready_sha256)throw Error('ExactretainedAreadybytesrequired');
const O=path.join(P,'tx345');fs.mkdirSync(O,{recursive:false});const out=path.join(O,'TX_FIXTURE.json');
const rec={task_id:'DEEPEYE-IMPLEMENTATION-20261014',task_version:1,work_id:op,operation_id:op,main_thread:'01a18824-4172-74e2-a13f-f3e3d1e3ed99',actual_turn:'01a1a3a7-d75a-7181-a610-7c00ffef0d5a',started_utc:new Date().toISOString(),script_sha256:sha(fs.readFileSync(__filename)),A_ready_proof_sha256:sha(fs.readFileSync(proofPath)),pattern_hex:PATTERN.toString('hex'),byte_spacing_ms:200,status:'intent_recorded_no_replay',reset_requested:false,flash_programmed:false,RXDATA_read:false,PDBGCTL_written:false,actuator_command_written:false,TXDATA_writes_requested:0,TXDATA_writes_returned:0,pre_connect_cpu_state:'unknown; connect may halt',samples:[],writes:[],requirements_sha256:'2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d'};
fs.writeFileSync(out,JSON.stringify(rec,null,2),{flag:'wx'});const save=()=>fs.writeFileSync(out,JSON.stringify(rec,null,2));
const image=path.join(REPO,'output/drill-demo-code-20261025/motor_runtime/build/motor_probe.out');
if(sha(fs.readFileSync(image))!=='69c5c57e6f896b879bb41a73d4f114180e11a9f16a8894eae6b035893848841f')throw Error('MTR4ELFchanged');
const config=path.join(REPO,'.local/drill-demo-code-20261025/vendor-example/empty_LP_MSPM0G3507_nortos_ticlang/targetConfigs/MSPM0G3507.ccxml');
const ds=initScripting();ds.setScriptingTimeout(15000);let s;
function bytes(a,n){const aligned=Math.floor(a/4)*4,offset=a-aligned,count=Math.ceil((offset+n)/4),values=s.memory.read(BigInt(aligned),count,32);if(values.length!==count)throw Error('Shortmemoryread');const b=Buffer.alloc(count*4);values.forEach((v,i)=>b.writeUInt32LE(Number(v)>>>0,i*4));return b.subarray(offset,offset+n);}
function word(a){return bytes(a,4).readUInt32LE(0);}
function sample(label){const b=bytes(0x20200000,172),m=bytes(0x202001b0,16),pc=bytes(0x2020012e,130),i=rec.samples.length;
 for(const[n,raw]of Object.entries({free:b,motor:m,pc_tx:pc}))fs.writeFileSync(path.join(O,n+'-'+i+'.bin'),raw,{flag:'wx'});
 const d={label,at_utc:new Date().toISOString(),cpu_halted:s.target.isHalted(),signature:'0x'+b.readUInt32LE(52).toString(16),state:b.readUInt32LE(56),last_seq:b.readUInt32LE(0),have_seq:b[37],armed:b[34],motor:{duty:m.readUInt16LE(12),active:m[14],commands:m.readUInt32LE(4)},motor_pwm_applied:word(0x202001d4),pc_tx:{head:pc[128],tail:pc[129]},ticks:word(0x202001c0),PDBGCTL:word(0x40101018),CTL0:word(0x40101100),LCRH:word(0x40101104),STAT:word(0x40101108),IBRD:word(0x40101110),FBRD:word(0x40101114),raw_free_sha256:sha(b),raw_motor_sha256:sha(m)};rec.samples.push(d);save();return d;}
function faultOff(d){if(d.signature!=='0x4d545234'||d.state!==4||d.last_seq!==0||d.have_seq!==0||d.armed||d.motor.duty||d.motor.active||d.motor_pwm_applied||d.pc_tx.head!==d.pc_tx.tail)throw Error('ChangedMCUprestate_noFixture');}
function txIdle(){const value=word(0x40101108);return(value&0x40)!==0&&(value&1)===0;}
function waitTxIdle(){const limit=Date.now()+500;while(!txIdle()){if(Date.now()>=limit)throw Error('ActualTX_notdrained_unknown_no_retry');sleep(10);}return word(0x40101108);}
try{
 ds.configure(config);s=ds.openSession(/CORTEX_M0P$/i);rec.connect_intent_utc=new Date().toISOString();save();s.target.connect();rec.connect_returned=true;save();s.symbols.load(image);
 const pre=sample('after_connect_before_any_TX');faultOff(pre);
 if(pre.CTL0!==0x20039||pre.LCRH!==0x30||pre.IBRD!==17||pre.FBRD!==23||(pre.STAT&0x44)!==0x44||(pre.STAT&1)!==0)throw Error('ActualUARTnotknownidle_noFixture');
 rec.PDBGCTL_original=pre.PDBGCTL;rec.PDBG_FREE_actual=(pre.PDBGCTL&1)!==0;rec.PDBG_behavior='Recorded only; CPU will run original quiescentFAULT during TX, so no debugFREE change needed';save();
 if(pre.cpu_halted){rec.resume_intent={at_utc:new Date().toISOString(),reason:'Explicit one continuation of actualFAULT/unarmed/motor0/emptyUART, no reset/startup/home'};save();s.target.run(false);rec.resume_returned=true;save();sleep(100);}
 const ready=sample('running_before_fixture');faultOff(ready);if(ready.cpu_halted)throw Error('CPU_notrunning_noFixture');
 for(let i=0;i<PATTERN.length;i++){
  if(s.target.isHalted())throw Error('UnexpectedCPUhalt_no_more_TX');
  const st=waitTxIdle();if(st&0x80)throw Error('UnexpectedTXfull_no_more_TX');
  const motor=bytes(0x202001bc,4),queue=bytes(0x202001ae,2);
  if(word(0x20200000)!==0||word(0x20200038)!==4||bytes(0x20200022,1)[0]!==0||bytes(0x20200025,1)[0]!==0||motor.readUInt16LE(0)!==0||motor[2]!==0||word(0x202001d4)!==0||queue[0]!==pre.pc_tx.head||queue[1]!==pre.pc_tx.tail)throw Error('ChangedMCUcontrolstate_no_more_TX');
  const entry={index:i,value:PATTERN[i],address:'0x40101120',STAT_before:st,write_intent_utc:new Date().toISOString()};rec.writes.push(entry);rec.TXDATA_writes_requested++;save();
  s.memory.write(0x40101120n,[PATTERN[i]],32);entry.write_returned_utc=new Date().toISOString();rec.TXDATA_writes_returned++;save();
  if(s.target.isHalted())throw Error('CPUhalt_after_write_outcome_unknown');entry.STAT_drained=waitTxIdle();entry.drained_utc=new Date().toISOString();save();if(i+1<PATTERN.length)sleep(200);
 }
 const final=sample('after_eight_fixture_writes');faultOff(final);if(final.cpu_halted||!txIdle()||final.PDBGCTL!==rec.PDBGCTL_original)throw Error('Unexpectedfinalstate_no_retry');
 rec.final=final;rec.status='eight_TXDATA_writes_returned_hardware_TX_drained_A_RX_unproven';rec.MCU_READY=false;
}catch(e){rec.status='failed_unknown_partial_no_automatic_replay';rec.error=String(e);}
finally{try{if(s&&s.target.isConnected())rec.cpu_halted_before_shutdown=s.target.isHalted();}catch(e){rec.cpu_query_error=String(e);}try{ds.shutdown();rec.shutdown_returned=true;}catch(e){rec.shutdown_error=String(e);rec.status='failed_unknown_partial_no_automatic_replay';}rec.closed_utc=new Date().toISOString();save();}
console.log(JSON.stringify({status:rec.status,TXDATA_writes_requested:rec.TXDATA_writes_requested,TXDATA_writes_returned:rec.TXDATA_writes_returned,final:rec.final,error:rec.error,evidence:out},null,2));if(rec.status==='failed_unknown_partial_no_automatic_replay')process.exit(1);
