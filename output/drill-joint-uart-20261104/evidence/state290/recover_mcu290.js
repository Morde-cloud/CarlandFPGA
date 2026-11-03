// Main-only one new recovery, authorized by human289. No flash/memory/UART write.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const P=__dirname,R=path.resolve(P,'../../../../../../../..');
// Resolve by explicit repo path to avoid implicit workspace traversal.
const REPO='D:/pynq/CarlandFPGA',D=path.join(REPO,'output/drill-demo-code-20261025/motor_runtime');
const op=process.argv[3];if(op!=='B-JOINT-MCU-CONTROLLED-RECOVERY-20261104-290')throw Error('Unique290operationrequired');
const proof=JSON.parse(fs.readFileSync(path.join(P,'HUMAN_WIRED_USB289.json'),'utf8'));
if(!proof.wiring_human_confirmed||!proof.onsite_observer||proof.battery_connected!==false)throw Error('Currenthuman289factsrequired');
const O=path.join(P,'recovery290');fs.mkdirSync(O,{recursive:false});const out=path.join(O,'RECOVERY.json');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex'),image=path.join(D,'build/motor_probe.out');
if(sha(fs.readFileSync(image))!=='69c5c57e6f896b879bb41a73d4f114180e11a9f16a8894eae6b035893848841f')throw Error('MTR4imagechanged');
const config=path.join(REPO,'.local/drill-demo-code-20261025/vendor-example/empty_LP_MSPM0G3507_nortos_ticlang/targetConfigs/MSPM0G3507.ccxml');
const rec={task_id:'DEEPEYE-IMPLEMENTATION-20261014',task_version:1,work_id:op,operation_id:op,started_utc:new Date().toISOString(),
 source:'actualG3507 oneSystemReset/run + originalRAMdiagnostics; not FPGA/physicalRPMmeasurement',script_sha256:sha(fs.readFileSync(__filename)),
 authorized_by:'Directhuman289: wired/USB-only/noBattery/startjointdebug; onsiteobserver',status:'intent_recorded_no_replay',
 flash_programmed:false,target_memory_written:false,UART_written:false,ARM_or_MOTOR_requested:false,samples:[],
 requirements_sha256:'2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d'};
fs.writeFileSync(out,JSON.stringify(rec,null,2),{flag:'wx'});const save=()=>fs.writeFileSync(out,JSON.stringify(rec,null,2));
const ds=initScripting();ds.setScriptingTimeout(15000);let s;
function bytes(a,n){const w=s.memory.read(BigInt(a),n/4,32);if(w.length!==n/4)throw Error('ShortRAMread');const b=Buffer.alloc(n);w.forEach((v,i)=>b.writeUInt32LE(Number(v)>>>0,i*4));return b;}
function sample(label){const b=bytes(0x20200000,172),m=bytes(0x202001b0,16),t=bytes(0x202001c0,4);const index=rec.samples.length;
 fs.writeFileSync(path.join(O,'free-'+index+'.bin'),b,{flag:'wx'});fs.writeFileSync(path.join(O,'motor-'+index+'.bin'),m,{flag:'wx'});
 const d={label,at_utc:new Date().toISOString(),cpu_halted:s.target.isHalted(),signature:'0x'+b.readUInt32LE(52).toString(16),state:b.readUInt32LE(56),
  ticks:t.readUInt32LE(0),last_seq:b.readUInt32LE(0),have_seq:b[37],armed:b[34],bus_status:b[41],result:b[42],yaw_raw:b.readUInt16LE(22),pitch_raw:b.readUInt16LE(24),
  yaw_feedback_seen:b[38],pitch_feedback_seen:b[39],bus_errors:b.readUInt16LE(26),tx_moves:b.readUInt32LE(84),sync_frames:b.readUInt32LE(156),
  configured_min:[b.readUInt16LE(160),b.readUInt16LE(162)],configured_max:[b.readUInt16LE(164),b.readUInt16LE(166)],
  motor:{duty:m.readUInt16LE(12),active:m[14],commands:m.readUInt32LE(4)},motor_pwm_applied:bytes(0x202001d4,4).readUInt32LE(0),raw_free_sha256:sha(b),raw_motor_sha256:sha(m)};
 rec.samples.push(d);save();if(d.signature!=='0x4d545234')throw Error('Targetsignaturechanged');return d;}
try{
 ds.configure(config);s=ds.openSession(/CORTEX_M0P$/i);s.target.connect();s.symbols.load(image);
 const pre=sample('before_reset');
 if(pre.state!==4||pre.last_seq!==0||pre.armed||pre.motor.duty||pre.motor.active||pre.motor_pwm_applied)throw Error('Knownprestatechanged; do notreset');
 const resets=s.target.getResets();rec.available_resets=resets;save();
 const selected=Object.keys(resets).find(k=>k==='System Reset'&&resets[k]===true);
 if(!selected)throw Error('ExplicitSystemResetunsupported; nofallback');
 rec.reset_intent={type:selected,at_utc:new Date().toISOString()};save();s.target.reset(selected);rec.reset_returned=true;save();
 rec.run_intent_utc=new Date().toISOString();save();s.target.run(false);rec.run_returned=true;save();
 const deadline=Date.now()+12000;let d;
 while(Date.now()<deadline){sleep(200);d=sample('after_run');
  if(d.cpu_halted)throw Error('Unexpectedhalt; noautoresume');
  if(d.armed||d.motor.duty||d.motor.active||d.motor_pwm_applied)throw Error('Unexpectedmotor_or_ARM; noUARTcommandsauthorized');
  if(d.state===3&&d.yaw_feedback_seen&&d.pitch_feedback_seen){rec.MCU_READY=true;break;}
  if(d.state===4){rec.MCU_READY=false;rec.reason='Actualstartupfault/nohealthyservofeedback; do notretryreset orclaimactuatorpower';break;}
 }
 rec.final=d;rec.MCU_READY=rec.MCU_READY===true;rec.status=rec.MCU_READY?'initialized_READY_motor_OFF':'recovery_returned_actuators_not_READY';
 rec.current_last_seq=d.last_seq;rec.UART_writer_granted=false;rec.requires_new_B_handoff=true;
}catch(e){rec.status='failed_no_automatic_replay';rec.error=String(e);}
finally{try{if(s&&s.target.isConnected())rec.cpu_halted_before_shutdown=s.target.isHalted();}catch(e){rec.cpu_query_error=String(e);}
 try{ds.shutdown();rec.shutdown_returned=true;}catch(e){rec.shutdown_error=String(e);rec.status='failed_no_automatic_replay';}
 rec.closed_utc=new Date().toISOString();save();}
console.log(JSON.stringify({status:rec.status,MCU_READY:rec.MCU_READY,final:rec.final,error:rec.error,evidence:out},null,2));
if(rec.status==='failed_no_automatic_replay')process.exit(1);
