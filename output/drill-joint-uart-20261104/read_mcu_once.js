// Parent-owned diagnostic read. NEVER run/reset/program/halt/write the target.
// Debugger connect/disconnect may have vendor side effects: record real state.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const R=path.resolve(__dirname,'../..');
const P=path.join(R,'.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-89');
const operation=process.argv[3];
if(!operation||!/^[A-Za-z0-9_-]+$/.test(operation))throw Error('Unique operation required');
const power=JSON.parse(fs.readFileSync(path.join(P,'HUMAN_POWER_STATE.json'),'utf8'));
if(power.actuators_power_isolated!==true||power.MCU_USB_powered!==true||power.onsite_observer!==true||power.actual_turn_id!=='01a1a343-44a0-76f3-8e05-97dd71803e5d')throw Error('Current direct human power isolation required');
const D=path.join(R,'output/drill-demo-code-20261025/motor_runtime');
const image=path.join(D,'build/motor_probe.out'),mapfile=path.join(D,'build/motor_probe.map');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
if(sha(fs.readFileSync(image))!=='69c5c57e6f896b879bb41a73d4f114180e11a9f16a8894eae6b035893848841f'||sha(fs.readFileSync(mapfile))!=='afdca14b71450a037ac9ffcc8477868f16b4996c8ad4361bb9d1a5af3e494011')throw Error('Pinned MTR4 image/map changed');
const config=path.join(R,'.local/drill-demo-code-20261025/vendor-example/empty_LP_MSPM0G3507_nortos_ticlang/targetConfigs/MSPM0G3507.ccxml');
const O=path.join(P,'readiness278',operation);fs.mkdirSync(O,{recursive:false});
const outfile=path.join(O,'READ.json');
const rec={task_id:'DEEPEYE-IMPLEMENTATION-20261014',task_version:1,work_id:'B-JOINT-MCU-READINESS-20261104-278',operation_id:operation,
 main_thread:'01a18824-4172-74e2-a13f-f3e3d1e3ed99',actual_turn:'01a1a343-44a0-76f3-8e05-97dd71803e5d',started_utc:new Date().toISOString(),
 source:'actual MSPM0 SWD memory read; not PWM/RPM/angle physical measurement',status:'intent_recorded_no_replay',
 target_reset_requested:false,target_program_requested:false,target_run_requested:false,target_halt_requested:false,target_memory_write_requested:false,
 connect_vendor_effects_not_proven_absent:true,actuators_power_isolated:true,MCU_USB_powered:true,onsite_observer:true,
 script_sha256:sha(fs.readFileSync(__filename)),local_image_sha256:sha(fs.readFileSync(image)),map_sha256:sha(fs.readFileSync(mapfile)),config_sha256:sha(fs.readFileSync(config)),
 requirements_ids:Array.from({length:15},(_,i)=>'H'+String(i+1).padStart(2,'0')),requirements_sha256:'2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d',samples:[]};
fs.writeFileSync(outfile,JSON.stringify(rec,null,2),{flag:'wx'});const save=()=>fs.writeFileSync(outfile,JSON.stringify(rec,null,2));
const ds=initScripting();ds.setScriptingTimeout(15000);let session;
function bytes(addr,size){const words=session.memory.read(BigInt(addr),size/4,32);if(words.length!==size/4)throw Error('Short SWDread');const b=Buffer.alloc(size);words.forEach((w,i)=>b.writeUInt32LE(Number(w)>>>0,i*4));return b;}
function readSample(i){
 const b=bytes(0x20200000,172),m=bytes(0x202001b0,16),t=bytes(0x202001c0,4);
 fs.writeFileSync(path.join(O,'free-'+i+'.bin'),b,{flag:'wx'});fs.writeFileSync(path.join(O,'motor-'+i+'.bin'),m,{flag:'wx'});
 const d={host_utc:new Date().toISOString(),cpu_halted:session.target.isHalted(),signature:'0x'+b.readUInt32LE(52).toString(16),
  state:b.readUInt32LE(56),last_seq:b.readUInt32LE(0),armed:b[34],bus_status:b[41],result:b[42],ticks:t.readUInt32LE(0),
  yaw_raw:b.readUInt16LE(22),pitch_raw:b.readUInt16LE(24),bus_errors:b.readUInt16LE(26),yaw_feedback_seen:b[38],pitch_feedback_seen:b[39],
  configured_min:[b.readUInt16LE(160),b.readUInt16LE(162)],configured_max:[b.readUInt16LE(164),b.readUInt16LE(166)],
  motor:{deadline_ms:m.readUInt32LE(0),commands:m.readUInt32LE(4),stops:m.readUInt32LE(8),duty:m.readUInt16LE(12),active:m[14]},
  free_bytes_sha256:sha(b),motor_bytes_sha256:sha(m)};
 rec.samples.push(d);save();if(d.signature!=='0x4d545234')throw Error('Target MTR4 signature mismatch');return d;
}
try{
 ds.configure(config);session=ds.openSession(/CORTEX_M0P$/i);rec.connect_intent_utc=new Date().toISOString();save();
 session.target.connect();rec.connected=true;rec.cpu_halted_after_connect=session.target.isHalted();save();
 // Symbols only, no image/program loading.
 session.symbols.load(image);
 const addrs={};for(const name of ['free_diagnostics','motor_diagnostics','free_saved_reference'])addrs[name]='0x'+BigInt(session.expressions.evaluate('&'+name)).toString(16);
 rec.symbol_addresses=addrs;
 if(addrs.free_diagnostics!=='0x20200000'||addrs.motor_diagnostics!=='0x202001b0')throw Error('Diagnostic map mismatch');
 const ref=BigInt(addrs.free_saved_reference);if(ref<0n||ref+16n>0x20000n)throw Error('Reference outside MAIN');
 rec.saved_reference_words=Array.from({length:4},(_,i)=>bytes(ref+BigInt(i*4),4).readUInt32LE(0));
 if(rec.saved_reference_words.join(',')!=='1196573489,1,2088,1961')throw Error('Saved reference mismatch');
 readSample(0);sleep(100);readSample(1);
 // Read full MAIN without erase/write, in existing proven 4KiB access chunks.
 const flash=Buffer.alloc(0x20000);
 for(let addr=0;addr<flash.length;addr+=0x1000)bytes(addr,0x1000).copy(flash,addr);
 fs.writeFileSync(path.join(O,'mainflash.bin'),flash,{flag:'wx'});rec.mainflash_sha256=sha(flash);
 const lines=fs.readFileSync(path.join(D,'build/motor_probe.hex'),'utf8').trim().split(/\r?\n/);let base=0,seen=0;
 for(const line of lines){if(!/^:[0-9a-f]+$/i.test(line))throw Error('IntelHEX syntax');const b=Buffer.from(line.slice(1),'hex');if(b.length!==b[0]+5||b.reduce((a,v)=>(a+v)&255,0)!==0)throw Error('IntelHEX checksum');const kind=b[3],addr=b.readUInt16BE(1);
  if(kind===4){if(b[0]!==2)throw Error('IntelHEX ELA');base=b.readUInt16BE(4)*65536;}
  else if(kind===0){const at=base+addr;if(at<0||at+b[0]>flash.length)throw Error('Image outside MAIN');if(!flash.subarray(at,at+b[0]).equals(b.subarray(4,4+b[0])))throw Error('Actual MAIN differs from pinned build hex');seen+=b[0];}
  else if(kind!==1&&kind!==5)throw Error('Unsupported IntelHEX record');
 }
 rec.actual_programmed_bytes_match_pinned_hex=true;rec.compared_programmed_bytes=seen;
 const d=rec.samples.at(-1);rec.highwater_read=d.last_seq;rec.cpu_halted_at_last_read=d.cpu_halted;
 rec.runtime_READY_claimed=false;rec.reason='Actuator supply isolated; no resume requested. Diagnostics may show LINK_WAIT/fault or halted state; restore/serial follow requires a separate current-state decision.';
 rec.status='actual_MTR4_flash_and_diagnostics_read';
}catch(e){rec.status='failed_no_automatic_replay';rec.error=String(e);}
finally{
 try{if(session&&session.target.isConnected())rec.cpu_halted_before_shutdown=session.target.isHalted();}catch(e){rec.shutdown_state_query_error=String(e);}
 try{ds.shutdown();rec.debugger_shutdown_returned=true;}catch(e){rec.shutdown_error=String(e);rec.status='failed_no_automatic_replay';}
 rec.cpu_state_after_shutdown_not_observed=true;rec.closed_utc=new Date().toISOString();save();
}
console.log(JSON.stringify({operation:operation,status:rec.status,highwater_read:rec.highwater_read,samples:rec.samples,actual_programmed_bytes_match_pinned_hex:rec.actual_programmed_bytes_match_pinned_hex,error:rec.error,evidence:outfile},null,2));
if(rec.status==='failed_no_automatic_replay')process.exit(1);
