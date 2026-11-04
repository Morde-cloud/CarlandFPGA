'use strict';
// SOURCE ONLY: ZERO_TX_ONLY. Explicit new main proof is required for active debug recovery.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const sha = b => crypto.createHash('sha256').update(b).digest('hex');
const HASH = '2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d';
const FLAG = '--execute-new-approved-zero-tx-recovery';
const ix = process.argv.indexOf(FLAG);
if (ix < 0) {
  console.log('SOURCE_ONLY_NOT_EXECUTED: no SDK initialization, connection, memory read or resume.');
} else {
  execute(process.argv[ix + 1]);
}
function execute(proofPath) {
  if (!proofPath) throw Error('Fresh trusted-main proof required');
  const proofBytes = fs.readFileSync(proofPath), p = JSON.parse(proofBytes);
  const sourceSHA = sha(fs.readFileSync(__filename));
  const bindings = {
    boot_id: '1abc1dff-1195-4833-9eb9-0291c349c79d', build_id: '76bea92ec0d97e37250733bad1eb3a38',
    parent_operation: 'A-GEN4-JOINT-UART-BOARD-20261104-1130-R01',
    parent_request_hash: '81b30937615981e7079e72b463d62643d92b8355d365b95b3fae46f09a0a8bb0'
  };
  const expected = {
    schema: 'B_ZERO_TX_CPU_RECOVERY_APPROVAL_V1', requirements_sha256: HASH,
    source_sha256: sourceSHA, main_thread: '01a18824-4172-74e2-a13f-f3e3d1e3ed99',
    trusted_main_reviewed_A149: true, CPU_resume_once_allowed: true,
    new_operation_not_retry: true, B_other_MCU_actors_closed: true, old377_processes_absent: true,
    A_actual_TX_count: 0, old377_RXDATA_requested: 0, old377_RXDATA_returned: 0,
    A_operation_id: 'A-GEN4-UART-TX1-20261104-1134-R01',
    authenticated_A_event_id: 'B:A-GEN4-A149B-EXPIRED-ZERO-TX-CLOSED-20261104-1151', ...bindings
  };
  // This checks a main attestation, not event authenticity. External trust is mandatory.
  for (const [k,v] of Object.entries(expected)) if (p[k] !== v) throw Error('Approval differs: ' + k);
  if (!/^B-MCU-RECOVERY-[A-Za-z0-9_-]+$/.test(p.B_operation_id) || !p.actual_turn) throw Error('New recovery identity required');
  const created = Date.parse(p.created_utc), expires = Date.parse(p.expires_utc);
  function fresh() {
    const now = Date.now();
    if (!Number.isFinite(created) || !Number.isFinite(expires) || created > now || expires <= now || expires - created <= 0 || expires - created > 120000) throw Error('Fresh proof max120s required');
  }
  fresh();
  function retained(name, fixedSHA) {
    if (p[name + '_sha256'] !== fixedSHA) throw Error('Proof raw hash differs: ' + name);
    const b = fs.readFileSync(p[name + '_path']);
    if (sha(b) !== fixedSHA) throw Error('Retained bytes differ: ' + name);
    return b;
  }
  retained('old377_source', '6039df82a3420f1d6993071adff0852b6e002bbad7016114cc1017b3c90c4881');
  const oldProcess = JSON.parse(retained('old377_process', '1131de2c2751173a58dc9bb2ccd2f5dfaae769a8d47e97159de17da7f569772e'));
  const oldCapture = JSON.parse(retained('old377_capture', '372c92a4abcd4147ba436cbc249e4df757b8e5a4c39eb3b2530f16fa17192dbf'));
  retained('A149_event', '164d7c57212e1c55a885fd73eca0c696fe6e98f3ef919e275d9a52a0b2681437');
  const a = JSON.parse(retained('A149_process', '5d916e07b06ced06cd37238f5fbb146293b9ecd869d3f6e1d3c3f4202253e212'));
  const c = JSON.parse(retained('A149_closed', '2b88f548378877d2521c8ed80452aaca40f92fb444b0cb5451250b4683219b58'));
  if (oldProcess.exit_code !== 1 || oldCapture.shutdown_returned !== true || oldCapture.RXDATA_reads_requested !== 0 || oldCapture.RXDATA_reads_returned !== 0) throw Error('Old377 terminal differs');
  if (a.TX_request_dispatched !== false || a.automatic_retry !== false || !Array.isArray(a.known_octets_write_returned) || a.known_octets_write_returned.length || a.reader_thread_stopped !== true || a.returncode !== 0 || a.wait_confirmed !== true) throw Error('A zero TX closure differs');
  if (c.event !== 'tx1-owner-closed' || c.lock_fd_closed !== true || c.lock_unlock_returned !== true || c.FIFO_flush !== false || c.UART_cleanup !== false || c.automatic_STOP !== false) throw Error('A owner closure differs');
  const REPO = 'D:/pynq/CarlandFPGA';
  const image = path.join(REPO, 'output/drill-demo-code-20261025/motor_runtime/build/motor_probe.out');
  if (sha(fs.readFileSync(image)) !== '69c5c57e6f896b879bb41a73d4f114180e11a9f16a8894eae6b035893848841f') throw Error('Frozen ELF differs');
  const config = path.join(REPO, '.local/drill-demo-code-20261025/vendor-example/empty_LP_MSPM0G3507_nortos_ticlang/targetConfigs/MSPM0G3507.ccxml');
  const dependencies = {
    [config]: '50d3cd02de2e579d75b6b86bce0504e2e92e7f7af71e876cf13b280072eed8b7',
    'C:/ti/ccs2100/ccs/ccs_base/common/targetdb/devices/MSPM0G3507.xml': '926091cef94c3bd48102d237b18f2aa6a08a6f8f0b1db2a074198344b0cd62db',
    'C:/ti/ccs2100/ccs/ccs_base/emulation/gel/mspm0g3507.gel': 'c40e17581d95678ece5d4702ec03d5eb41b02130224a6ef640c99366739b3023',
    'C:/ti/ccs2100/ccs/ccs_base/DebugServer/propertyDB/MSPM0_FlashProperties.xml': '22cd07ad1ce2bab8bf3ba6081ac77846a6e75fd7f55bba0a42f7469eb613a4f1'
  };
  for (const [file,h] of Object.entries(dependencies)) if (sha(fs.readFileSync(file)) !== h) throw Error('CCS dependency differs: ' + file);
  fresh();
  const O = path.join(__dirname, p.B_operation_id);
  fs.mkdirSync(O, {recursive:false}); // Existing operation directory is never reused.
  function durable(file, bytes, flag='w') {
    const fd = fs.openSync(file, flag);
    try { fs.writeFileSync(fd, bytes); fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
  }
  const out = path.join(O, 'RECOVERY.json');
  const rec = {task_id:'DEEPEYE-IMPLEMENTATION-20261014', task_version:1,
    work_id:p.B_operation_id, main_thread:p.main_thread, actual_turn:p.actual_turn,
    actual_script_pid:process.pid, source_sha256:sourceSHA, proof_sha256:sha(proofBytes),
    requirements_sha256:HASH, requirements_ids:Array.from({length:15},(_,i)=>'H'+String(i+1).padStart(2,'0')),
    contract_pin:'817b355887c14cfa9c5d830c8589684f994af082',
    started_utc:new Date().toISOString(), status:'intent_no_replay',
    preconnect_CPU:'unknown; connect is active and may halt', final_CPU:'unknown',
    RXDATA_reads_requested:0, RXDATA_reads_returned:0, resume_requested:0, resume_returned:0,
    memory_writes:0, UART_TX_writes:0, reset_requested:false, flash_programmed:false,
    hard_CPU_hold_ceiling_guaranteed:false, samples:[], CCS_dependency_sha256:dependencies,
    memory_writes_scope:'No explicit script memory writes; no claim that debugger transport has no internal writes.'};
  durable(out, JSON.stringify(rec,null,2), 'wx');
  const save = () => durable(out, JSON.stringify(rec,null,2));
  durable(path.join(O,'APPROVAL_RAW.json'),proofBytes,'wx');
  let ds, s;
  const start = process.hrtime.bigint();
  function guard(stage) {
    fresh();
    const left = 60000 - Number((process.hrtime.bigint()-start)/1000000n);
    if (left <= 0) throw Error('Diagnostic budget expired: ' + stage);
    if (ds) ds.setScriptingTimeout(Math.max(1, Math.min(10000,left,expires-Date.now())));
  }
  function call(stage, fn) { guard(stage); return fn(); }
  function bytes(addr,n) {
    const base = Math.floor(addr/4)*4, offset=addr-base, count=Math.ceil((offset+n)/4);
    const w=call('memory.read',()=>s.memory.read(BigInt(base),count,32));
    if (w.length !== count) throw Error('Short read');
    const b=Buffer.alloc(count*4); w.forEach((v,i)=>b.writeUInt32LE(Number(v)>>>0,4*i));
    return b.subarray(offset,offset+n);
  }
  const word = a => bytes(a,4).readUInt32LE(0);
  function debugOff() {
    const v=call('EnableWaitForDebug read',()=>s.settings.get('EnableWaitForDebug'));
    rec.EnableWaitForDebug_actual=v; save();
    if(v!==false && v!==0) throw Error('EnableWaitForDebug must already be false/0');
  }
  function sample(label) {
    const i=rec.samples.length, files={};
    function raw(name,addr,n) {
      const b=bytes(addr,n), file=name+'-'+i+'.bin'; durable(path.join(O,file),b,'wx');
      files[name]={file,bytes:b.length,sha256:sha(b)}; return b;
    }
    const b=raw('original_ram',0x20200000,172),m=raw('motor',0x202001b0,16),pc=raw('pc_tx',0x2020012e,130);
    const regs={PDBGCTL:0x40101018,CTL0:0x40101100,LCRH:0x40101104,STAT:0x40101108,IBRD:0x40101110,FBRD:0x40101114,PB6_mux:0x4042805c,PB7_mux:0x40428060,PWM_applied:0x202001d4,ticks:0x202001c0};
    const r={}; for(const [k,a] of Object.entries(regs))r[k]=raw(k,a,4).readUInt32LE(0);
    const d={label,at_utc:new Date().toISOString(),cpu_halted:call('CPU state',()=>s.target.isHalted()),
      signature:b.readUInt32LE(52),state:b.readUInt32LE(56),last_seq:b.readUInt32LE(0),armed:b[34],have_seq:b[37],motor_duty:m.readUInt16LE(12),motor_active:m[14],pc_head:pc[128],pc_tail:pc[129],...r,raw_files:files};
    rec.samples.push(d); rec.final_CPU=d.cpu_halted?'held':'running'; save(); return d;
  }
  function invariant(d) {
    if(d.signature!==0x4d545234 || d.state!==4 || d.last_seq!==0 || d.have_seq!==0 || d.armed!==0 || d.motor_duty!==0 || d.motor_active!==0 || d.PWM_applied!==0 || d.pc_head!==d.pc_tail) throw Error('Changed fault/off/sequence/PC TX state; stop without automatic action');
    if(d.CTL0!==0x20039 || d.LCRH!==0x30 || d.IBRD!==17 || d.FBRD!==23 || d.PB6_mux!==0x82 || d.PB7_mux!==0x40082 || (d.PDBGCTL&1)!==1 || (d.STAT&0x44)!==0x44 || (d.STAT&1)!==0) throw Error('UART mux/idle/RXFE/PDBG differs; no resume');
  }
  try {
    guard('SDK init'); ds=initScripting(); ds.setScriptingTimeout(10000);
    call('configure',()=>ds.configure(config)); s=call('openSession',()=>ds.openSession(/CORTEX_M0P$/i));
    debugOff(); guard('connect'); rec.connect_intent_utc=new Date().toISOString(); save();
    call('connect',()=>s.target.connect()); rec.connect_returned=true; save();
    // Connect may itself halt; the prior physical state cannot be inferred.
    if(call('post-connect held check',()=>s.target.isHalted())!==true) throw Error('CPU not already held after connect; no halt or recovery action');
    debugOff(); call('symbols only',()=>s.symbols.load(image));
    const pre=sample('held_snapshot_1'); invariant(pre);
    const held=sample('held_snapshot_2'); invariant(held);
    if(!pre.cpu_halted || !held.cpu_halted || pre.ticks!==held.ticks || pre.PDBGCTL!==held.PDBGCTL) throw Error('CPU/ticks not held; no resume');
    guard('single explicit resume'); rec.resume_requested=1;rec.resume_intent_utc=new Date().toISOString();save();
    call('single explicit resume',()=>s.target.run(false)); rec.resume_returned=1;rec.final_CPU='unknown after resume';save();
    call('brief tick observation',()=>sleep(50));
    const after=sample('after_explicit_resume');invariant(after);
    if(after.cpu_halted || after.ticks===held.ticks)throw Error('Run/tick advance unconfirmed; no retry');
    rec.status='zero_tx_CPU_running_ticks_advance_fault_outputs_off';
  } catch(e) { rec.status='failed_or_unknown_no_replay_no_automatic_action'; rec.error=String(e); }
  finally {
    if(ds) {
      // Cleanup has a separate bounded timeout even if diagnostic budget/proof expired.
      try { ds.setScriptingTimeout(5000); if(s) { const h=s.target.isHalted(); rec.cpu_halted_before_shutdown=h;rec.final_CPU=h?'held':'running'; if(h && rec.status==='zero_tx_CPU_running_ticks_advance_fault_outputs_off')rec.status='failed_or_unknown_no_replay_no_automatic_action'; } } catch(e){rec.final_CPU='unknown';rec.cpu_query_error=String(e);rec.status='failed_or_unknown_no_replay_no_automatic_action';}
      rec.SDK_closing_intent_utc=new Date().toISOString();save();
      try { ds.setScriptingTimeout(5000);ds.shutdown();rec.shutdown_returned=true; }
      catch(e){rec.shutdown_error=String(e);rec.status='failed_or_unknown_no_replay_no_automatic_action';}
    }
    rec.closed_utc=new Date().toISOString();
    rec.intended_exit_code=rec.status==='zero_tx_CPU_running_ticks_advance_fault_outputs_off' && rec.shutdown_returned===true ? 0 : 1;
    save(); process.exitCode=rec.intended_exit_code;
  }
  console.log(JSON.stringify({status:rec.status,evidence:out,final_CPU:rec.final_CPU,shutdown_returned:rec.shutdown_returned,error:rec.error}));
  // CCS launcher otherwise finishes with process.exit(0), overriding exitCode.
  if(rec.intended_exit_code!==0)process.exit(rec.intended_exit_code);
}
