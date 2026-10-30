"""First focused pure software controls. Runtime needs separate main release.

All generated approvals/reviews/netlists/HWH are SYNTHETIC_FUNCTION_CONTROL_ONLY
and can enter ONLY pure validator functions. No prepare/build_run/vendor call.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import xml.etree.ElementTree as E
import fixtures99t as f


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):f.write_json(p,v)


class Cases:
    def __init__(self,root):self.root=root;self.assertions=0;self.count=0;self.negatives=0
    def check(self,ok,why):
        self.assertions+=1
        if not ok:raise AssertionError(why)
    def write(self,name,status,detail=None):
        self.count+=1
        row=dict(case=name,status=status,detail=detail,evidence_kind=f.EVIDENCE_KIND,assertions_so_far=self.assertions)
        with (self.root/'cases.jsonl').open('a',encoding='utf-8') as out:out.write(json.dumps(row,sort_keys=True)+'\n');out.flush();os.fsync(out.fileno())
        print(json.dumps(row,sort_keys=True),flush=True)
    def positive(self,name,fn):
        value=fn();self.check(True,name);self.write(name,'OBSERVED_RETURN',repr(value)[:512]);return value
    def negative(self,name,fn,contains=None):
        try:fn()
        except ValueError as error:
            self.check(contains is None or contains in str(error),'wrong refusal: '+name+': '+str(error))
            self.negatives+=1;self.write(name,'OBSERVED_VALUEERROR',str(error)[:512])
        else:raise AssertionError('negative was accepted: '+name)
    def finish(self):
        value=dict(status='SOFTWARE_CASES_COMPLETED',cases=self.count,observed_expected_refusals=self.negatives,assertions=self.assertions,evidence_kind=f.EVIDENCE_KIND,
                   actual95=False,actual_authority=False,actual_netlist=False,actual_build=False,board=False)
        save(self.root/'SUMMARY.json',value);print(json.dumps(value),flush=True)


def candidate(product):
    here=product/'tools/diagnostic/functional50_build98';sys.path.insert(0,str(here))
    def load(name):
        spec=importlib.util.spec_from_file_location(name,here/(name+'.py'));m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
    return load('functional50_contract'),load('build_functional50'),load('verify_functional50_closure'),load('verify_functional50_hwh')


def synthetic_resolved(c,product,template):
    """Fake review receipts exist ONLY to test pure byte/schema refusal logic."""
    value=copy.deepcopy(template)
    for e in value['sources']+value['tooling']:
        p=product/e['path'];e['bytes']=p.stat().st_size;e['sha256']=digest(p)
    endpoint=next(e for e in value['sources'] if e['role']=='trace_endpoint94')
    value['review_95'].update(completed=True,actual_95_result_sha256='5'*64,main_review_sha256='6'*64,
        source94={k:endpoint[k] for k in ('path','bytes','sha256')})
    value['source_commit']='1'*40;value['status']='FROZEN_MAIN_REVIEWED';value['frozen']=True
    value['cdc_source_review']=dict(reviewed_by='main',sha256='7'*64)
    computed=c.compute_build_id(value);value['build_id']=computed['build_id'];value['build_id_full_sha256']=computed['full_sha256']
    return value


def cli_contract(args,s,c,b,v,h):
    product=args.product;template_path=product/'fpga/diagnostic/functional50_build98/closure_template.json'
    template=json.loads(template_path.read_text('utf-8'));script=product/'tools/diagnostic/functional50_build98/build_functional50.py'
    def cli(name,extra,expected):
        argv=[sys.executable,'-B','-X','utf8',str(script),'--product-root',str(product),'--contract-json',str(args.contract),'--closure-template',str(template_path),*extra]
        run=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,timeout=8,shell=False,creationflags=subprocess.CREATE_NO_WINDOW)
        (args.out/(name+'.stdout.bin')).write_bytes(run.stdout);(args.out/(name+'.stderr.bin')).write_bytes(run.stderr)
        save(args.out/(name+'.command.json'),dict(argv=argv,exit_code=run.returncode,expected_exit=expected))
        s.check(run.returncode==expected,'CLI actual exit: '+name)
        return run
    run=cli('default-inspect',[],0);doc=json.loads(run.stdout)
    s.check(doc['build_ready'] is False and doc['status']=='inspect_only_no_build','default remains closed')
    s.positive('default_inspect_closed',lambda:doc['build_ready'])
    view=s.positive('actual_unfrozen_template_verifier',lambda:v.verify(template_path,product,args.contract,'template'))
    s.check(view['frozen'] is False and view['build_ready'] is False,'template cannot authorize build')
    full=['--mode','build','--closure',str(template_path),'--approval',str(args.out/'MISSING-APPROVAL-NOT-A-FIXTURE'),
          '--run-id','SYNTHETIC99T-unused','--operation-id','SYNTHETIC99T-unused-op','--work-id','SYNTHETIC99T-unused-work','--out',str(args.out/'NEVER-CREATED')]
    for flag in ('--closure','--approval','--run-id','--operation-id','--work-id'):
        items=list(full);i=items.index(flag);del items[i:i+2]
        run=cli('missing-'+flag[2:],items,1)
        s.check(b'build requires closure, approval, run_id, operation_id and work_id' in run.stderr,'missing field refusal cause')
        s.write('missing_'+flag[2:],'OBSERVED_NONZERO_CLI')
    existing=args.out/'PREEXISTING';existing.mkdir();(existing/'sentinel.bin').write_bytes(b'preexisting\x00sentinel\xff')
    before={p.relative_to(existing).as_posix():digest(p) for p in existing.rglob('*') if p.is_file()}
    run=cli('existing-output',['--mode','prepare','--out',str(existing)],1)
    s.check(b'existing attempt cannot be reused' in run.stderr,'existing output refusal cause')
    after={p.relative_to(existing).as_posix():digest(p) for p in existing.rglob('*') if p.is_file()}
    s.check(before==after and not (existing/'FAILURE.json').exists(),'preexisting inventory unchanged')
    s.write('preexisting_sentinel_unchanged','OBSERVED_BYTE_EQUAL',before)
    s.positive('twenty_source_roles',lambda:s.check(len(template['sources'])==20 and sum(e['sha256'] is None for e in template['sources'])==1,'exact20/one null'))
    s.positive('template_source_bytes',lambda:c.validate_source_bytes(template,product,False))
    resolved=synthetic_resolved(c,product,template)
    s.positive('pure_synthetic_resolved94_byte_proof',lambda:c.validate_source_bytes(resolved,product,True))
    for name,mutate in [('missing95',lambda x:x['review_95'].update(completed=False)),('wrong94proof',lambda x:x['review_95']['source94'].update(sha256='0'*64)),
                        ('empty94bytes',lambda x:next(e for e in x['sources'] if e['role']=='trace_endpoint94').update(bytes=0))]:
        x=copy.deepcopy(resolved);mutate(x);s.negative('resolved94_'+name,lambda x=x:c.validate_source_bytes(x,product,True))
    for e in template['sources']:
        if e['role']=='trace_endpoint94':continue
        x=copy.deepcopy(template);next(a for a in x['sources'] if a['role']==e['role'])['sha256']='0'*64
        s.negative('fixed_pin_refuses_'+e['role'],lambda x=x:c.validate_source_bytes(x,product,False))
    base=c.compute_build_id(resolved)
    changed=copy.deepcopy(resolved);changed['build_id']='f'*32;changed['build_id_full_sha256']='e'*64
    s.check(c.compute_build_id(changed)==base,'build ID excludes its own declared fields')
    expected=hashlib.sha256(json.dumps(base['canonical_payload'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    s.check(base['full_sha256']==expected and base['build_id']==expected[:32],'independent canonical SHA calculation')
    s.check(resolved['cdc_bindings'] is None and 'bindings' not in base['canonical_payload']['cdc'],'no prelaunch graph/circular hash')
    s.write('canonical_build_id_deterministic','OBSERVED_DIGEST_EQUAL',base['build_id'])
    s.positive('pure_synthetic_frozen_schema',lambda:c.validate_closure(resolved,product,True))
    for name,edit in [('mode',lambda p:p.update(mode='MANUAL_GUESSED')),('ports',lambda p:p.update(ports=['yaw_capture_i'])),('stages',lambda p:p.update(stages=2)),('period',lambda p:p.update(period_ns=10.0))]:
        x=copy.deepcopy(resolved);edit(x['cdc_policy']);s.negative('policy_'+name,lambda x=x:c.validate_closure(x,product,True))
    x=copy.deepcopy(resolved);x['cdc_bindings']=f.bindings();s.negative('guessed_prelaunch_graph',lambda:c.validate_closure(x,product,True))


def identity_cdc(args,s,c,b,v,h):
    template=json.loads((args.product/'fpga/diagnostic/functional50_build98/closure_template.json').read_text('utf-8'))
    closure=synthetic_resolved(c,args.product,template);a26=c.A_SELECTION_OPERATION_ID
    selection=dict(provided=True,selected_by='A',operation_id=a26,a_message_id='SYNTHETIC-NOT-AN-A-MESSAGE',a_message_sha256='8'*64)
    closure['a_selection']=selection
    cp=args.out/'SYNTHETIC-closure.json';save(cp,closure)
    expected_output=args.out/'NEVER-RUN-BUILD';run='SYNTHETIC99T';op='SYNTHETIC99T-OP';work='SYNTHETIC99T-WORK'
    approval=dict(schema='FUNCTIONAL50_A_SELECTION_V1',task_id=c.TASK_ID,task_version=1,work_id=work,operation_id=op,run_id=run,
        selected_by='A',board_operator='A',b_board_access=False,source_commit=closure['source_commit'],source_closure_sha256=digest(cp),build_id=closure['build_id'],
        requirements_sha256=c.REQUIREMENTS_SHA256,frozen_design=c.FROZEN_DESIGN,part=c.PART,board_part=c.BOARD_PART,vivado_version=c.VIVADO_VERSION,
        clock_plan=dict(fclk0_hz=50000000,period_ns=20.0,fclk1_3_disabled=True,no_pl_clock=True,cdc_rule='exact external-to-first-D only; stages 2/3 and internal TX-RX timed'),
        max_threads=2,timeout_seconds=60,job_drain_seconds=5.0,job_terminate_seconds=5.0,output_directory=str(expected_output),
        a_selection=dict(selected=True,operation_id=a26,a_message_id=selection['a_message_id'],a_message_sha256=selection['a_message_sha256']),
        main_attestation=dict(main_thread_id=c.MAIN_THREAD_ID,verified_actual_a_message=True,main_review_sha256='9'*64,
          a_operation_id=a26,a_message_id=selection['a_message_id'],a_message_sha256=selection['a_message_sha256'],verified_at_utc='2026-10-31T00:00:00Z'),approved_at_utc='2026-10-31T00:00:01Z')
    ap=args.out/'SYNTHETIC-UNTRUSTED-validator-input-only.json'
    def verify(payload):save(ap,payload);return b.verify_approval(ap,cp,closure,expected_output,run,op,work,60,5.0,5.0)
    s.positive('pure_untrusted_approval_schema_only',lambda:verify(approval))
    for field,value in [('run_id','other'),('operation_id','other'),('work_id',c.WORK_ID),('task_id','other'),('task_version',2),
                        ('source_commit','0'*40),('source_closure_sha256','0'*64),('build_id','0'*32),('output_directory',str(args.out/'other')),
                        ('timeout_seconds',61),('max_threads',3),('job_drain_seconds',4),('approved_at_utc','invalid-time')]:
        x=copy.deepcopy(approval);x[field]=value;s.negative('approval_wrong_'+field,lambda x=x:verify(x))
    for name,mutate in [('A26_equals_wrong_Bop',lambda x:x['a_selection'].update(operation_id=op)),('A_message',lambda x:x['a_selection'].update(a_message_id='other')),
                        ('attestation',lambda x:x['main_attestation'].update(a_message_sha256='0'*64)),('payload_fixture_marker',lambda x:x.update(synthetic=True))]:
        x=copy.deepcopy(approval);mutate(x);s.negative('approval_'+name,lambda x=x:verify(x))
    state=dict(run_id=run,build_id=f.BUILD);path=args.out/'SYNTHETIC-cdc.json';base=f.cdc_record()
    def verify_cdc(value):save(path,value);return b.verify_actual_cdc(path,state,'synth')
    s.positive('synthetic_exact_cdc_schema_only',lambda:verify_cdc(base))
    mutations=[('wrong_run',lambda x:x.update(run_id='other')),('wrong_build',lambda x:x.update(build_id='0'*32)),('wrong_stage',lambda x:x.update(stage='routed')),
       ('missing_port',lambda x:x['bindings'].pop('yaw_capture_i')),('duplicate_pin',lambda x:x['bindings']['yaw_capture_i'].__setitem__(1,x['bindings']['yaw_capture_i'][0])),
       ('unsafe_pin',lambda x:x['bindings']['yaw_capture_i'].__setitem__(0,'unsafe*[0]/D')),('shared_chain',lambda x:x['bindings'].__setitem__('pitch_capture_i',x['bindings']['yaw_capture_i']))]
    for name,edit in mutations:
        x=copy.deepcopy(base);edit(x);s.negative('cdc_'+name,lambda x=x:verify_cdc(x))
    xp=args.out/'SYNTHETIC-implemented.xdc';good=f.xdc()
    def verify_xdc(text):xp.write_text(text,encoding='utf-8');return b.verify_false_paths(xp,f.bindings())
    s.positive('xdc_three_exact_literal_vector_names',lambda:verify_xdc(good))
    for name,text in [('duplicate',good+good.splitlines()[0]+'\n'),('through',good.replace(' -to ',' -through [get_pins {logic/D}] -to ',1)),
        ('extra_endpoint',good.replace('get_ports {yaw_capture_i}','get_ports {yaw_capture_i pitch_capture_i}',1)),('glob',good.replace('meta_reg[0]','meta_reg*',1)),
        ('global',good+'set_clock_groups -asynchronous -group [get_clocks *]\n'),('substring',good.replace('yaw_capture_i','fake_yaw_capture_i',1)),
        ('option',good.replace('set_false_path','set_false_path -setup',1)),('extra_command',good.replace('\n','; puts injected\n',1)),
        ('other_firstD',good.replace('meta_reg[0]','level_reg[0]',1))]:s.negative('xdc_'+name,lambda text=text:verify_xdc(text))


def timing_hwh(args,s,c,b,v,h):
    pins=json.loads(args.pins.read_text('utf-8'))
    for item in pins['actual_reports']:
        path=Path(item['path']);s.check(digest(path)==item['sha256'],'immutable report pin before parse')
        data=s.positive('actual_report_'+item['name'],lambda path=path:h.parse_design_timing_summary(path))
        for key,value in item['independent_expected'].items():s.check(data[key]==value,'actual report independent '+key)
    valid=args.out/'SYNTHETIC-valid-summary.txt';valid.write_text(f.timing_text(),encoding='utf-8')
    s.positive('synthetic_summary_syntax',lambda:h.parse_design_timing_summary(valid))
    for name,text in [('missing',f.timing_text().replace('Design Timing Summary','Missing Summary')),('duplicate',f.timing_text()+f.timing_text()),
        ('malformed',f.timing_text().replace('0.5 0.0','junk 0.0')),('nonfinite',f.timing_text().replace('0.5 0.0','NaN 0.0')),('empty_total',f.timing_text().replace('0 99','0 0'))]:
        path=args.out/('SYNTHETIC-'+name+'.txt');path.write_text(text,encoding='utf-8');s.negative('summary_'+name,lambda path=path:h.parse_design_timing_summary(path))
    reports=args.out/'SYNTHETIC-timing-gate';reports.mkdir();summary=reports/'route_timing_summary.txt';check=reports/'check.txt';gate=reports/'gate.json'
    check.write_text('4. checking unconstrained_internal_endpoints (0)\n4. checking unconstrained_internal_endpoints (0)\n',encoding='utf-8')
    good_gate=dict(wns_ns=.5,tns_ns=0.,whs_ns=.25,ths_ns=0.,setup_failing_endpoints=0,hold_failing_endpoints=0,
        drc_errors=0,drc_critical_warnings=0,lutlp1=0,has_20ns_clock=1,has_10ns_clock=0,clocks=[dict(name='SYNTHETIC_FCLK0',period_ns=20.)],
        authoritative_source='same-run route_timing_summary.txt Design Timing Summary; get_drc_violations/get_clocks')
    summary.write_text(f.timing_text(),encoding='utf-8');save(gate,good_gate)
    s.positive('synthetic_timing_consistency_only',lambda:h.verify_timing_gate(gate,check))
    for name,row in [('negative_setup','-0.5 -1 1 99 0.25 0 0 99 1 0 0 12'),('negative_hold','0.5 0 0 99 -0.25 -1 1 99 1 0 0 12')]:
        summary.write_text(f.timing_text(row),encoding='utf-8')
        bad_gate=copy.deepcopy(good_gate)
        if name=='negative_setup':bad_gate.update(wns_ns=-.5,tns_ns=-1.,setup_failing_endpoints=1)
        else:bad_gate.update(whs_ns=-.25,ths_ns=-1.,hold_failing_endpoints=1)
        save(gate,bad_gate);s.negative(name,lambda:h.verify_timing_gate(gate,check))
    summary.write_text(f.timing_text(),encoding='utf-8')
    x=copy.deepcopy(good_gate);x['wns_ns']=.6;save(gate,x);s.negative('gate_summary_mismatch',lambda:h.verify_timing_gate(gate,check))
    s.negative('old_actual100MHz_G05only_HWH',lambda:h.verify_hwh(Path(pins['old_actual_hwh']['path']),f.mapping(),f.BUILD))
    xml=args.out/'SYNTHETIC-pure-structural.hwh';mapping=f.mapping()
    def verify_xml(root,map_value=None):E.ElementTree(root).write(xml,encoding='utf-8',xml_declaration=True);return h.verify_hwh(xml,map_value or mapping,f.BUILD)
    result=s.positive('synthetic_twoendpoint_HWH_structure_only',lambda:verify_xml(f.hwh()))
    s.check(result['labels_are_mmio_observations'] is False and result['cpu_memory_certification'] is False,'structural labels not MMIO/cpu certification')
    mutations=[('fixture_marker',lambda r:r.set('TEST_FIXTURE','synthetic-not-hardware')),
        ('old_clock',lambda r:r.find("./MODULES/MODULE[@INSTANCE='ps7_0']/PARAMETERS/PARAMETER[@NAME='PCW_FPGA0_PERIPHERAL_FREQMHZ']").set('VALUE','100')),
        ('build_id',lambda r:r.find("./MODULES/MODULE[@INSTANCE='trace50_0']/PARAMETERS/PARAMETER[@NAME='BUILD_ID']").set('VALUE','0')),
        ('reset',lambda r:r.find("./MODULES/MODULE[@INSTANCE='rst_fclk0']/PARAMETERS/PARAMETER[@NAME='C_EXT_RESET_HIGH']").set('VALUE','1')),
        ('window',lambda r:r.find(".//MEMRANGE[@INSTANCE='trace50_0']").set('BASEVALUE','0x41000000')),
        ('pin_width',lambda r:r.find("./EXTERNALPORTS/PORT[@NAME='yaw_pwm_o']").set('LEFT','1')),
        ('extra_uart',lambda r:E.SubElement(r.find('EXTERNALPORTS'),'PORT',NAME='uart_tx_o',DIR='O')),
        ('vlnv',lambda r:r.find("./MODULES/MODULE[@INSTANCE='g05_50_0']").set('VLNV','old:old:old:1.0'))]
    for name,edit in mutations:
        root=f.hwh();edit(root);s.negative('HWH_'+name,lambda root=root:verify_xml(root))


def tcl_helpers(args,s,c,b,v,h):
    # Selected by the main: native Tcl only, no Tk window and no Vivado exe.
    import tkinter
    interp=tkinter.Tcl(useTk=False)
    s.write('plain_Tcl_version','OBSERVED_VERSION',interp.call('info','patchlevel'))
    source=args.product/'fpga/diagnostic/functional50_build98/build_functional50.tcl'
    interp.setvar('::functional50_library_only',1);interp.call('source',str(source))
    vector='literal\\backslash\tTAB\rCR\nLF'
    expected=vector.replace('\\','\\\\').replace('\t','\\t').replace('\r','\\r').replace('\n','\\n')
    s.check(interp.call('ddr_tsv',vector)==expected,'DDR backslash/tab/CR/LF exact escape')
    s.write('ddr_tsv_byte_escape','OBSERVED_EXACT_STRING')
    s.check(float(interp.call('f50_timing_number','20.0','synthetic clock'))==20.0,'finite clock numeric helper')
    for bad in ('NaN','Inf','-Inf','garbage','1e9999'):
        try:interp.call('f50_timing_number',bad,'synthetic bad clock')
        except tkinter.TclError as error:s.negatives+=1;s.check(True,'Tcl finite refusal');s.write('Tcl_nonfinite_'+bad,'OBSERVED_TCLERROR',str(error))
        else:raise AssertionError('Tcl accepted nonfinite: '+bad)
    pins=json.loads(args.pins.read_text('utf-8'))
    for item in pins['actual_reports']:
        path=Path(item['path']);s.check(digest(path)==item['sha256'],'Tcl immutable source pin')
        data=interp.call('f50_design_timing_summary',str(path))
        for key,value in item['independent_expected'].items():s.check(float(interp.call('dict','get',data,key))==value,'Tcl actual aggregate '+key)
        s.write('Tcl_actual_report_'+item['name'],'OBSERVED_AGGREGATES')
    malformed=args.out/'SYNTHETIC-Tcl-summary.txt'
    for name,text in [('missing',f.timing_text().replace('Design Timing Summary','missing')),('duplicate',f.timing_text()+f.timing_text()),
                      ('nonfinite',f.timing_text().replace('0.5 0.0','NaN 0.0')),('emptytotal',f.timing_text().replace('0 99','0 0'))]:
        malformed.write_text(text,encoding='utf-8')
        try:interp.call('f50_design_timing_summary',str(malformed))
        except tkinter.TclError as error:s.negatives+=1;s.check(True,'Tcl summary refusal');s.write('Tcl_summary_'+name,'OBSERVED_TCLERROR',str(error))
        else:raise AssertionError('Tcl accepted malformed summary: '+name)
    check=args.out/'SYNTHETIC-check_timing.txt';check.write_text('4. checking unconstrained_internal_endpoints (0)\n4. checking unconstrained_internal_endpoints (0)\n',encoding='utf-8')
    interp.call('f50_check_unconstrained',str(check));s.write('Tcl_zero_unconstrained','OBSERVED_RETURN')
    for name,text in [('nonzero','4. checking unconstrained_internal_endpoints (1)\n'*2),('missing','unconstrained missing\n')]:
        check.write_text(text,encoding='utf-8')
        try:interp.call('f50_check_unconstrained',str(check))
        except tkinter.TclError as error:s.negatives+=1;s.check(True,'Tcl unconstrained refusal');s.write('Tcl_unconstrained_'+name,'OBSERVED_TCLERROR',str(error))
        else:raise AssertionError('Tcl accepted invalid unconstrained inventory')


def main():
    p=argparse.ArgumentParser();p.add_argument('--category',choices=['cli_contract','identity_cdc','timing_hwh','tcl_helpers'],required=True)
    p.add_argument('--product',type=Path,required=True);p.add_argument('--contract',type=Path,required=True);p.add_argument('--pins',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=False);f.manifest(args.out);s=Cases(args.out)
    try:
        c,b,v,h=candidate(args.product)
        globals()[args.category](args,s,c,b,v,h);s.finish();return 0
    except BaseException:
        (args.out/'UNEXPECTED_FAILURE.txt').write_text(traceback.format_exc(),encoding='utf-8');traceback.print_exc();return 1


if __name__=='__main__':raise SystemExit(main())
