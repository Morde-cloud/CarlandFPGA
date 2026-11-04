// One explicit post-A1195 closure RAM observation. No UART data reads or writes.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
if(process.argv[3]!=='--post-a1195-snapshot-once')throw Error('Explicit main approval required');
const p=JSON.parse(fs.readFileSync(process.argv[4],'utf8'));
if(p.operation_id!=='B-POST-A1195-MCU-SNAPSHOT-20261104-409'||p.source_sha256!==sha(fs.readFileSync(__filename))||Date.now()>=Date.parse(p.expires_utc))throw Error('Proof/source/deadline mismatch');
const ac=JSON.parse(fs.readFileSync(p.A_closed_path,'utf8')),ap=JSON.parse(fs.readFileSync(p.A_process_path,'utf8')),ar=JSON.parse(fs.readFileSync(p.A_recovery_path,'utf8'));
if(ac.boot_id!=='1abc1dff-1195-4833-9eb9-0291c349c79d'||ac.PL||ac.UART||ac.actors.length||!ac.lock.acquire_returned||!ac.lock.release_returned||ap.returncode!==2||!ap.wait_confirmed||!ap.reader_thread_stopped||ar.UART_TX||ar.reset||ar.flush||ar.final_status!==4||!ar.lock_unlock_returned||!ar.lock_fd_closed)throw Error('A actual terminal close required');
const O=path.join(__dirname,'snapshot409');fs.mkdirSync(O,{recursive:false});const f=path.join(O,'READ.json');
const r={operation_id:p.operation_id,main_thread:p.main_thread,actual_turn:p.actual_turn,script_pid:process.pid,source_sha256:p.source_sha256,requirements_sha256:'2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d',samples:[],UART_RXDATA_reads:0,UART_TX_writes:0,memory_writes:0,reset_requested:false,flash_programmed:false,resume_intents:0,resume_returns:0,status:'intent_no_replay'};
fs.writeFileSync(f,JSON.stringify(r,null,2),{flag:'wx'});const save=()=>fs.writeFileSync(f,JSON.stringify(r,null,2));
const ds=initScripting();ds.setScriptingTimeout(10000);let s;
function bytes(a,n){const base=Math.floor(a/4)*4,off=a-base,count=Math.ceil((off+n)/4),v=s.memory.read(BigInt(base),count,32);if(v.length!==count)throw Error('Shortread');const b=Buffer.alloc(count*4);v.forEach((x,i)=>b.writeUInt32LE(Number(x)>>>0,4*i));return b.subarray(off,off+n);}
const word=a=>bytes(a,4).readUInt32LE(0);
function snap(label){const b=bytes(0x20200000,172),m=bytes(0x202001b0,16),bus=bytes(0x202000ac,130),pc=bytes(0x2020012e,130),i=r.samples.length;for(const[n,v]of Object.entries({free:b,motor:m,bus_tx:bus,pc_tx:pc}))fs.writeFileSync(path.join(O,n+'-'+i+'.bin'),v,{flag:'wx'});const d={label,cpu_halted:s.target.isHalted(),signature:b.readUInt32LE(52),state:b.readUInt32LE(56),last_seq:b.readUInt32LE(0),have_seq:b[37],armed:b[34],motor_duty:m.readUInt16LE(12),motor_active:m[14],PWM_applied:word(0x202001d4),ticks:word(0x202001c0),pc_head:pc[128],pc_tail:pc[129],bus_head:bus[128],bus_tail:bus[129],UART1_STAT:word(0x40101108)};r.samples.push(d);save();return d;}
function off(d){if(d.signature!==0x4d545234||d.armed||d.motor_duty||d.motor_active||d.PWM_applied)throw Error('Expected original MTR4 disarmed/off observation changed');}
try{
 ds.configure('D:/pynq/CarlandFPGA/.local/drill-demo-code-20261025/vendor-example/empty_LP_MSPM0G3507_nortos_ticlang/targetConfigs/MSPM0G3507.ccxml');s=ds.openSession(/CORTEX_M0P$/i);
 r.EnableWaitForDebug=s.settings.get('EnableWaitForDebug');save();if(r.EnableWaitForDebug!==false&&r.EnableWaitForDebug!==0)throw Error('Conditionalresetsettingmustremainoff');
 r.connect_intent=true;save();s.target.connect();r.connect_returned=true;save();const pre=snap('post_A1195_before_resume');off(pre);if(!pre.cpu_halted)throw Error('Connect did not return held');
 if(Date.now()>=Date.parse(p.expires_utc))throw Error('Fresh proof expired');r.resume_intents=1;save();s.target.run(false);r.resume_returns=1;save();sleep(120);const post=snap('post_A1195_running');off(post);if(post.cpu_halted||post.ticks===pre.ticks)throw Error('RUN progress not confirmed');
 r.status='POST_A1195_CURRENT_RAM_OBSERVED_CPU_RUN';r.MCU_READY=post.state===3;
}catch(e){r.status='failed_unknown_no_replay';r.error=String(e);}
finally{try{if(s)r.cpu_halted_before_shutdown=s.target.isHalted();}catch(e){r.cpu_state_error=String(e);}try{ds.shutdown();r.shutdown_returned=true;}catch(e){r.shutdown_error=String(e);r.status='failed_unknown_no_replay';}r.closed_utc=new Date().toISOString();save();}
console.log(JSON.stringify(r));if(r.status==='failed_unknown_no_replay')process.exit(1);
