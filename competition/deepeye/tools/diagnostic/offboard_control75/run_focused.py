"""One NEW finite B75 operation. Fresh directory mandatory; no retry loop.

Runs source-hashed software and actual unchanged 50MHz RTL, not the old suites.
Every subprocess owns a separate Windows Job, stdout/stderr and terminal proof.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import traceback

PRODUCT=Path(__file__).resolve().parents[3]
RTL='fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/'
PINS={
 RTL+'deepeye_g05_profile_50mhz.sv':'8ec9bf0415e2ce5e87d2a793260bf635664f16584e2cb842df1fefba75e64307',
 RTL+'deepeye_g05_command_map_50mhz.sv':'8df580388e85a59a43a0eaaae697534123a6e128fdb4675098e7173bda60a6a1',
 RTL+'deepeye_g05_curvature_rom_50mhz.svh':'d462859e6893cd90fb33ad9ddd481aaa7ee46937ba3d197431f81b602357a83c',
 RTL+'deepeye_g05_capture_engine_50mhz.sv':'fcdb04d1e307506328c205154730e1cf8c5bff2efe72727a46a2f3f4b856ed8a',
 RTL+'deepeye_g05_axi_50mhz_candidate.sv':'99cdb09399466966458343351d0d941191f34cc9af6f9808c5fb3cc58086ea5a',
 'fpga/control3d/deepeye_pwm_coherent_capture.sv':'4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456'}
CONTRACT='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'


def need(ok, message):
    if not ok: raise RuntimeError(message)


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,value):
    with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def make_stimulus(module,out,case):
    """Host adapter emits the very register writes consumed by actual RTL."""
    context=dict(operation_id='SYNTHETIC-B75-actual-RTL-'+out.parent.name+'-'+case,kernel_boot_id='SYNTHETIC-BOOT-NOT-AUTHENTICATED',
        session_id='full-original-fixture-session-not-truncated',clock_domain_id='original-synthetic-QPC',
        action_id='synthetic-original-action-unavailable-in-real-Root',request_hash='a'*64,
        build_manifest_sha256='b'*64,source_record_sha256='c'*64,capture_sha256='d'*64,tested_commit='e'*40,
        tag=(1<<60)+15,generation=(1<<62)+123,epoch=(1<<61)+3,trigger_id=(1<<60)+5,
        request_seq=17,capture_seq=19,source_admission_index=23)
    now=(1<<62)+54321
    adapter=module.ControlAdapter.synthetic_fixture(context)
    decision=dict(yaw_q=100,pitch_q=-200,profile=1,speed=20,ttl_ms=100 if case=='normal' else 1)
    key=adapter.queue(original_source_qpc_ns=now-99,now_qpc_ns=now,decision=decision)
    adapter.hold(key)
    rows=[]
    def wr(address,value,response=0):rows.append((0,address,value,response))
    def rd(address,response=0):rows.append((1,address,0,response))
    def wait(n):rows.append((2,n,0,0))
    rd(0);rd(4)
    for address,value in adapter.begin_registers():wr(address,value)
    for i in range(13):rd(0x100+4*i)
    sent=[]
    def transport(regs):
        need(adapter.records[key]['state']=='SEND_UNKNOWN','intent state before transport')
        sent.extend(regs)
        for address,value in regs:wr(address,value)
    adapter.send_once(key,now_qpc_ns=now,intent_path=out/'SEND_UNKNOWN_INTENT.json',send=transport)
    wait(20)
    for address in (0x008,0x014,0x018,0x040,0x044,0x048,0x04c):rd(address)
    if case=='normal':
        wait(2_000_100)
        wr(0x00c,4)
        for i in range(32):rd(0x300+4*i)
        # Deliberate fixture-only duplicate tests RTL idempotence. This is NOT
        # an automatic adapter resend; send_once itself refuses a retry.
        for address,value in sent:wr(address,value)
        for address in (0x040,0x044,0x048,0x04c):rd(address)
        for i in range(32):rd(0x300+4*i)
        # Wrong identity attempt cannot mutate a bound bank.
        wr(0x100,0x77777777,2);rd(0x100)
        wr(0x00c,3);wait(10)
    else:wait(50_100)
    for address in (0x008,0x010,0x014,0x018,0x040,0x044,0x048,0x04c):rd(address)
    rows.append((3,0,0,0))
    (out/'stimulus.txt').write_text(''.join('%d %d %d %d\n'%row for row in rows),encoding='ascii')
    save(out/'HOST_REQUEST.json',dict(evidence_kind=module.SYNTHETIC,context=context,original_source_qpc_ns=now-99,
        original_now_qpc_ns=now,source_age_ns=99,identity_words=list(adapter.identity_words),
        request_registers=sent,decision=decision,adapter_send_calls=1,
        fixture_only_duplicate=(case=='normal'),action_retirement_available=False))
    return adapter,key


def ingest_trace(adapter,key,path):
    """Only actual trace facts are admitted. No expected capture is substituted."""
    text=path.read_text('ascii');need(len(text)<2*1024*1024,'trace budget')
    rows=[line.split(',') for line in text.splitlines()]
    need(len([r for r in rows if r[0]=='END'])==1 and not any(r[0]=='FAIL' for r in rows),'exact completed trace required')
    r=adapter.records[key];assoc=dict(context=r['context'],identity_words=r['identity_words'],command_id=r['command_id'],transport_tag=r['transport_tag'])
    regs={};captures=[];bank=None;events=[];applied=[];deadlines=[];pins=[]
    for row in rows:
        if row[0]=='READ':
            address,value,resp=map(int,row[1:]);need(resp==0,'all selected public readbacks must succeed')
            regs[address]=value
            if address==0x300:bank=[];captures.append(bank)
            if 0x300 <= address <= 0x37c:
                need(bank is not None and address==0x300+4*len(bank),'complete ordered capture bank')
                bank.append(value)
            if address==0x044:applied.append(regs[0x040]|value<<32)
            if address==0x04c:deadlines.append(regs[0x048]|value<<32)
        elif row[0]=='ACCEPTED':
            tick,cmd,tag=map(int,row[1:]);need((cmd,tag)==(r['command_id'],r['transport_tag']),'accepted issued command identity')
            adapter.digital_fact(key,**assoc,fact='ACCEPTED');events.append(dict(fact='ACCEPTED',engine_tick=tick))
        elif row[0]=='APPLIED':
            a,d,cmd,tag=map(int,row[1:]);need((cmd,tag)==(r['command_id'],r['transport_tag']),'applied issued command identity')
            adapter.digital_fact(key,**assoc,fact='APPLIED',applied_tick=a,deadline_tick=d)
            events.append(dict(fact='APPLIED',actual_applying_edge=a,actual_deadline=d))
        elif row[0]=='PINS':pins.append(tuple(map(int,row[1:])))
    need(regs[0]==0x47303550 and regs[4]==2,'actual G05P/layout2 readback')
    need([regs[0x100+4*i] for i in range(13)]==r['identity_words'],'exact public identity bank echo')
    need(regs[0x014]==r['command_id'] and regs[0x018]==r['transport_tag'],'public active command/tag echo')
    need(len(events)==2 and events[0]['fact']=='ACCEPTED' and events[1]['fact']=='APPLIED','exact single engine acceptance/application')
    need(applied and all(x==r['applied_tick'] for x in applied) and deadlines and all(x==r['deadline_tick'] for x in deadlines),
         'public readbacks preserve actual applying-edge TTL; no duplicate renewal')
    for words in captures:adapter.digital_fact(key,**assoc,fact='CAPTURED',words=words)
    need(len(pins)==1,'one final pin observation')
    tick,pwm=pins[0]
    adapter.digital_fact(key,**assoc,fact='STOP',terminal_status=regs[8],pwm=pwm,fault=regs[0x10]&255,tick=tick)
    need(r['host_receipt_ack'] is None and r['original_action_retirement'] is None and r['stop_required'],
         'digital STOP must not fabricate original receipt/action retirement')
    return dict(engine_events=events,public_applied_readbacks=applied,public_deadline_readbacks=deadlines,
        actual_latched_capture_banks=captures,terminal_status=regs[8],terminal_fault=regs[0x10],
        final_pin_tick=tick,final_pwm=pwm,adapter=adapter.snapshot())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--job-helper',required=True)
    ap.add_argument('--model-home',default='D:/modelsim1/win64')
    args=ap.parse_args();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    result=dict(status='failed_preserved',evidence_kind='SYNTHETIC_FIXTURE',task_id='DEEPEYE-IMPLEMENTATION-20261014',
        task_version=1,work_id='B-DEEPEYE-OFFBOARD-CONTROL-ACK-RETIREMENT-20261030-75',
        requirements_sha256=CONTRACT,requirements_ids=['H%02d'%i for i in range(1,16)],
        contract_pin='f5989cd5defce561f9ba98e6b18fc2682945f0a2',freeze='1011259415a0916054eb580687612580bc1e5f09',
        declared_base_head='d201499c513cf7172bd121c0e874fce3991bb175',source_base='0a35e06248073564baab65706c6c30d89069db54',
        tested_commit=None,tested_source='exact precommit snapshot hashes; no later commit tested',commands=[],cases=[],
        actual_Root_BOOT_calibration_action_receipt='unavailable',board='not_run',synthesis='not_run',implementation='not_run',
        original_100MHz_gate='retained',final_1pct_100ms_gate='retained; not accepted',R20_R21_failures='unchanged',
        complete_H12_and_all_formal_gates='not accepted',motion_authorized=False)
    try:
        snap=out/'snapshot';snap.mkdir()
        selected=list(PINS)
        for folder in ('tools/diagnostic/offboard_control75','fpga/diagnostic/offboard_control75','golden/diagnostic/offboard_control75'):
            selected += [p.relative_to(PRODUCT).as_posix() for p in (PRODUCT/folder).glob('*') if p.is_file()]
        for name in selected:
            source=PRODUCT/name;dest=snap/name;dest.parent.mkdir(parents=True,exist_ok=True)
            if name in PINS:need(sha(source)==PINS[name],'frozen dependency changed: '+name)
            shutil.copyfile(source,dest)
        result['snapshot_files']={n:dict(bytes=(snap/n).stat().st_size,sha256=sha(snap/n)) for n in sorted(selected)}
        shutil.copyfile(args.job_helper,out/'windows_job.snapshot.py')
        helper=load_module('b75_owned',snap/'tools/diagnostic/offboard_control75/bounded_owned.py')
        module=load_module('b75_adapter',snap/'tools/diagnostic/offboard_control75/control_adapter.py')
        model=Path(args.model_home).resolve()
        def run(label,argv,timeout=60,expect=0):
            directory=out/label;directory.mkdir()
            r=helper.run_owned([str(x) for x in argv],directory,timeout,out/'windows_job.snapshot.py')
            result['commands'].append(dict(label=label,exit_code=r['exit_code'],pid=r.get('original_pid'),
                timeout=r['timed_out'],job_terminal_confirmed=r['job_terminal_confirmed'],job_closed=r.get('job_closed'),
                evidence=str(directory/'PROCESS.json')))
            print(json.dumps(result['commands'][-1]),flush=True)
            need(r['termination_confirmed'] and r['job_terminal_confirmed'] and r.get('job_closed') and not r['timed_out'],label+' process closure failed')
            need(r['exit_code']==expect if expect is not None else r['exit_code']!=0,label+' unexpected exit')
            return directory,r
        software,_=run('01-software-controls',[sys.executable,'-B','-X','utf8',snap/'golden/diagnostic/offboard_control75/test_controls.py'])
        output=(software/'process.stderr.bin').read_text('utf-8')
        need(re.search(r'Ran 14 tests\b',output) is not None and '\nOK\n' in output,'exact software control completion')
        negative_code="import importlib.util; s=importlib.util.spec_from_file_location('a',"+repr(str(snap/'tools/diagnostic/offboard_control75/control_adapter.py'))+"); a=importlib.util.module_from_spec(s);s.loader.exec_module(a); a.ControlAdapter().queue(original_source_qpc_ns=1,now_qpc_ns=1,decision={})"
        neg,_=run('02-software-negative-refusal',[sys.executable,'-B','-c',negative_code],expect=1)
        need('production INPUT_UNAVAILABLE' in (neg/'process.stderr.bin').read_text('utf-8'),'negative control must fail for actual refusal')
        run('03-vlog-version',[model/'vlog.exe','-version'])
        run('04-vsim-version',[model/'vsim.exe','-version'])
        library=out/'library';ini=out/'modelsim.ini'
        ini.write_text('[Library]\nwork = '+library.as_posix()+'\nothers = '+model.parent.as_posix()+'/modelsim.ini\n',encoding='ascii')
        os.environ['MODELSIM']=str(ini);os.environ['PYTHONDONTWRITEBYTECODE']='1'
        run('05-vlib',[model/'vlib.exe',library])
        sources=[snap/name for name in PINS if name.endswith('.sv')]
        bench=snap/'fpga/diagnostic/offboard_control75/tb_offboard_control75.sv'
        run('06-compile',[model/'vlog.exe','-sv','-work','work','+incdir+'+str(snap/RTL),*sources,bench])
        do=out/'run.do';do.write_text('onerror {quit -code 1}\nonbreak {\n if {[catch {examine -radix decimal sim:/tb_offboard_control75/completion_status} done]} {quit -code 3}\n if {$done == 1} {quit -code 0}\n quit -code 2\n}\nonfinish stop\nrun -all\nquit -code 4\n',encoding='ascii')
        for case in ('normal','expiry'):
            fixture=out/('input-'+case);fixture.mkdir()
            adapter,key=make_stimulus(module,fixture,case)
            label='07-sim-'+case;directory=out/label
            argv=[model/'vsim.exe','-c','-voptargs=+acc','-lib','work','tb_offboard_control75',
                '+STIM='+(fixture/'stimulus.txt').as_posix(),'+TRACE='+(directory/'ports.csv').as_posix(),'-do',do,'-l',directory/'transcript.log']
            directory,_=run(label,argv,timeout=180)
            transcript=(directory/'transcript.log').read_text('utf-8',errors='replace')
            markers=re.findall(r'^# B75_PASS lines=(\d+) assertions=(\d+)\s*$',transcript,re.M)
            need(len(markers)==1 and not re.search(r'\*\* (?:Error|Fatal):|B75_FAIL',transcript),'unique exact completion without simulation error')
            view=ingest_trace(adapter,key,directory/'ports.csv')
            need((len(view['actual_latched_capture_banks'])==2 if case=='normal' else not view['actual_latched_capture_banks']), 'case capture count')
            need(view['terminal_fault']==(6 if case=='normal' else 2),'actual STOP/TTL expiry cause')
            save(directory/'ADAPTER_READBACK.json',view)
            result['cases'].append(dict(case=case,status='passed',actual_capture_banks=len(view['actual_latched_capture_banks']),
                digital_stop=True,host_receipt_ack=False,original_action_retirement=False,readback=str(directory/'ADAPTER_READBACK.json')))
        label='08-rtl-negative-oracle';directory=out/label
        run(label,[model/'vsim.exe','-c','-voptargs=+acc','-lib','work','tb_offboard_control75',
            '+STIM='+(out/'input-normal/stimulus.txt').as_posix(),'+TRACE='+(directory/'ports.csv').as_posix(),
            '+NEGATIVE=1','-do',do,'-l',directory/'transcript.log'],expect=2)
        need('B75_FAIL actual G05P magic oracle' in (directory/'transcript.log').read_text('utf-8',errors='replace'),'actual negative oracle not reached')
        need(all(sha(PRODUCT/n)==row['sha256'] for n,row in result['snapshot_files'].items()),'source changed during test')
        result['status']='focused_passed_main_review_pending'
    except BaseException:
        result['failure']=traceback.format_exc()
    finally:
        save(out/'RESULT.json',result)
        save(out/'FILE_MANIFEST.json',{p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(out.rglob('*')) if p.is_file()})
        print(json.dumps(dict(status=result['status'],out=str(out),failure=result.get('failure'))),flush=True)
    return 0 if result['status']=='focused_passed_main_review_pending' else 1


if __name__=='__main__':raise SystemExit(main())
