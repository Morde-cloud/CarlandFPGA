"""NEW isolated syntax/parser/authorization controls only; never invokes Vivado."""
import argparse
import ast
import copy
import json
from pathlib import Path
import sys
import tkinter
import traceback
import xml.etree.ElementTree as E
import build_g05 as b
from hwh_guard import verify_hwh, PORTS, INSTANCE, VLNV


def hwh_fixture():
    r=E.Element('EDKSYSTEM',VIVADOVERSION='2026.1',TEST_FIXTURE='synthetic-not-hardware')
    ex=E.SubElement(r,'EXTERNALPORTS'); interfaces=E.SubElement(r,'EXTERNALINTERFACES'); modules=E.SubElement(r,'MODULES')
    def module(name,vlnv):
        m=E.SubElement(modules,'MODULE',INSTANCE=name,FULLNAME='/'+name,VLNV=vlnv)
        for tag in ('PORTS','PARAMETERS','BUSINTERFACES'):E.SubElement(m,tag)
        return m
    def param(parent,name,value):E.SubElement(parent,'PARAMETER',NAME=name,VALUE=str(value))
    def port(parent,name,direction,net,links=(),**attrs):
        p=E.SubElement(parent,'PORT',NAME=name,DIR=direction,SIGNAME=net,**attrs)
        c=E.SubElement(p,'CONNECTIONS')
        for i,n in links:E.SubElement(c,'CONNECTION',INSTANCE=i,PORT=n)
        return p
    ip=module(INSTANCE,VLNV); ps=module('ps7_0','xilinx.com:ip:processing_system7:5.5'); rst=module('rst_fclk0','xilinx.com:ip:proc_sys_reset:5.0')
    bus=E.SubElement(ip.find('BUSINTERFACES'),'BUSINTERFACE',NAME='S_AXI',TYPE='SLAVE',VLNV='xilinx.com:interface:aximm:1.0',DATAWIDTH='32')
    for k,v in {'DATA_WIDTH':32,'ADDR_WIDTH':12,'PROTOCOL':'AXI4LITE','FREQ_HZ':100000000}.items():param(bus,k,v)
    stale=E.SubElement(ps.find('BUSINTERFACES'),'BUSINTERFACE',NAME='M_AXI_GP0')
    param(stale,'FREQ_HZ',10000000)  # Deliberately stale descriptive metadata.
    for name,bits in (('s_axi_wdata',32),('s_axi_rdata',32),('s_axi_awaddr',12),('s_axi_araddr',12)):
        port(ip.find('PORTS'),name,'I','fixture_'+name,LEFT=str(bits-1),RIGHT='0')
    mm=E.SubElement(ps,'MEMORYMAP')
    E.SubElement(mm,'MEMRANGE',INSTANCE=INSTANCE,SLAVEBUSINTERFACE='S_AXI',MASTERBUSINTERFACE='M_AXI_GP0',BASEVALUE='0x41000000',HIGHVALUE='0x41000fff')
    for k,v in {'PCW_FPGA0_PERIPHERAL_FREQMHZ':'100','PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ':'100.000000'}.items():param(ps.find('PARAMETERS'),k,v)
    param(rst.find('PARAMETERS'),'C_EXT_RESET_HIGH',0)
    clock={'SIGIS':'clk','CLKFREQUENCY':'100000000'}
    port(ip.find('PORTS'),'s_axi_aclk','I','fclk',[('ps7_0','FCLK_CLK0')],**clock)
    port(ps.find('PORTS'),'FCLK_CLK0','O','fclk',[(INSTANCE,'s_axi_aclk'),('ps7_0','M_AXI_GP0_ACLK'),('rst_fclk0','slowest_sync_clk')],**clock)
    port(ps.find('PORTS'),'M_AXI_GP0_ACLK','I','fclk',[('ps7_0','FCLK_CLK0')],**clock)
    port(rst.find('PORTS'),'slowest_sync_clk','I','fclk',[('ps7_0','FCLK_CLK0')],**clock)
    reset={'SIGIS':'rst','POLARITY':'ACTIVE_LOW'}
    port(ip.find('PORTS'),'s_axi_aresetn','I','peripheral_reset',[('rst_fclk0','peripheral_aresetn')],**reset)
    port(rst.find('PORTS'),'peripheral_aresetn','O','peripheral_reset',[(INSTANCE,'s_axi_aresetn')],**reset)
    port(rst.find('PORTS'),'ext_reset_in','I','ps_reset',[('ps7_0','FCLK_RESET0_N')],**reset)
    port(ps.find('PORTS'),'FCLK_RESET0_N','O','ps_reset',[('rst_fclk0','ext_reset_in')],**reset)
    for prefix,names in (('DDR',('addr','ba','cas_n','ck_n','ck_p','cke','cs_n','dm','dq','dqs_n','dqs_p','odt','ras_n','reset_n','we_n')),
                         ('FIXED_IO',('ddr_vrn','ddr_vrp','mio','ps_clk','ps_porb','ps_srstb'))):
        maps=E.SubElement(E.SubElement(interfaces,'BUSINTERFACE',NAME=prefix),'PORTMAPS')
        for n in names:
            name=prefix+'_'+n
            E.SubElement(maps,'PORTMAP',LOGICAL=n,PHYSICAL=name)
            port(ex,name,'IO','fixture_'+name,[('ps7_0',name)])
    for name,(direction,pin) in PORTS.items():
        port(ex,name,direction,'fixture_'+name,[(INSTANCE,name)])
        port(ip.find('PORTS'),name,direction,'fixture_'+name,[('g05_diag_imp',name)])
    return r


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[4]
    cases=[]
    def check(name,fn,reject=False):
        try:
            value=fn()
        except (ValueError,RuntimeError,KeyError,tkinter.TclError) as error:
            if not reject:raise
            cases.append({'name':name,'status':'expected_rejection','reason':str(error)})
        else:
            if reject:raise AssertionError('unexpected acceptance: '+name)
            cases.append({'name':name,'status':'pass'})
    mapping={'instance':INSTANCE,'vlnv':VLNV,'bd':'g05_diag','top':'g05_diag_wrapper','base':'0x41000000','range':'0x1000'}
    def xml_path(label,xml):
        p=out/(label+'.synthetic.hwh');E.ElementTree(xml).write(p,encoding='utf-8',xml_declaration=True);return p
    good=hwh_fixture();good_path=xml_path('good',good)
    try:
        for path in sorted(Path(__file__).parent.glob('*.py')):
            check('python-syntax-'+path.name,lambda p=path:ast.parse(p.read_bytes(),filename=str(p)))
        for name in ('build_g05.tcl','g05_cdc.tcl','g05_ports.xdc'):
            source=(root/(b.FPGA+name)).read_text(encoding='utf-8')
            check('tcl-complete-'+name,lambda s=source:b.require(tkinter.Tcl().call('info','complete',s)==1,'incomplete Tcl'))
        tcl=tkinter.Tcl();tcl.call('set','g05_library_only',1)
        check('tcl-load-library-no-Vivado',lambda:tcl.call('source',(root/(b.FPGA+'build_g05.tcl')).as_posix()))
        check('HWH-positive-with-stale-GP0-description',lambda:verify_hwh(good_path,mapping,fixture=True))
        check('synthetic-HWH-refused-as-real',lambda:verify_hwh(good_path,mapping),True)
        def mutate(label,path,attr,value):
            xml=copy.deepcopy(good);node=xml.find(path);assert node is not None;node.set(attr,value)
            p=xml_path(label,xml);check(label,lambda:verify_hwh(p,mapping,fixture=True),True)
        ip="./MODULES/MODULE[@INSTANCE='g05_diag_0']"
        ps="./MODULES/MODULE[@INSTANCE='ps7_0']"
        reset="./MODULES/MODULE[@INSTANCE='rst_fclk0']"
        mutations=[('wrong-vlnv',ip,'VLNV','old:ip:diag:1.0'),('wrong-instance',ip,'INSTANCE','old_diag'),
            ('wrong-aperture',ps+'/MEMORYMAP/MEMRANGE','HIGHVALUE','0x4100ffff'),
            ('wrong-base',ps+'/MEMORYMAP/MEMRANGE','BASEVALUE','0x41001000'),
            ('wrong-AXI-width',ip+"/BUSINTERFACES/BUSINTERFACE[@NAME='S_AXI']",'DATAWIDTH','64'),
            ('wrong-physical-width',ip+"/PORTS/PORT[@NAME='s_axi_wdata']",'LEFT','15'),
            ('wrong-clock-freq',ip+"/PORTS/PORT[@NAME='s_axi_aclk']",'CLKFREQUENCY','10000000'),
            ('wrong-clock-net',ip+"/PORTS/PORT[@NAME='s_axi_aclk']",'SIGNAME','stale_gp0'),
            ('wrong-clock-source',ip+"/PORTS/PORT[@NAME='s_axi_aclk']/CONNECTIONS/CONNECTION",'PORT','FCLK_CLK1'),
            ('wrong-configured-FCLK',ps+"/PARAMETERS/PARAMETER[@NAME='PCW_FPGA0_PERIPHERAL_FREQMHZ']",'VALUE','10'),
            ('wrong-reset-derived',reset+"/PARAMETERS/PARAMETER[@NAME='C_EXT_RESET_HIGH']",'VALUE','1'),
            ('wrong-reset-polarity',ip+"/PORTS/PORT[@NAME='s_axi_aresetn']",'POLARITY','ACTIVE_HIGH'),
            ('wrong-reset-source',ip+"/PORTS/PORT[@NAME='s_axi_aresetn']/CONNECTIONS/CONNECTION",'INSTANCE','ps7_0'),
            ('wrong-external-direction',"./EXTERNALPORTS/PORT[@NAME='yaw_capture_i']",'DIR','O'),
            ('wrong-external-width',"./EXTERNALPORTS/PORT[@NAME='yaw_capture_i']",'LEFT','2'),
            ('wrong-external-wire',"./EXTERNALPORTS/PORT[@NAME='yaw_capture_i']/CONNECTIONS/CONNECTION",'PORT','pitch_capture_i'),
            ('internal-PWM-loopback',ip+"/PORTS/PORT[@NAME='yaw_capture_i']/CONNECTIONS/CONNECTION",'INSTANCE',INSTANCE)]
        for item in mutations:mutate(*item)
        xml=copy.deepcopy(good);xml.find('EXTERNALPORTS').append(copy.deepcopy(xml.find('./EXTERNALPORTS/PORT')))
        p=xml_path('duplicate-external',xml);check('duplicate-external',lambda:verify_hwh(p,mapping,fixture=True),True)
        xml=copy.deepcopy(good);E.SubElement(xml.find('EXTERNALPORTS'),'PORT',NAME='rs485_tx_o')
        p=xml_path('extra-external',xml);check('extra-external',lambda:verify_hwh(p,mapping,fixture=True),True)
        xml=copy.deepcopy(good);xml.find('MODULES').append(copy.deepcopy(xml.find(ip)))
        p=xml_path('duplicate-IP',xml);check('duplicate-IP',lambda:verify_hwh(p,mapping,fixture=True),True)

        review=out/'SYNTHETIC_CDC_REVIEW_NOT_AUTHORITY.txt';review.write_text('Isolated parser test only; no real source or main authorization.',encoding='utf-8')
        acc={'schema':1,'TEST_FIXTURE':'synthetic-not-authority','task_id':b.TASK,'task_version':1,
            'director_thread_id':b.MAIN,'accepted':True,'source_commit':'1'*40,'requirements_sha256':b.CONTRACT,
            'frozen_design':b.DESIGN,'sources':{p:b.DEPENDENCIES.get(p,'0'*64) for p in b.SOURCES},
            'build_files':{p:'0'*64 for p in b.BUILD_FILES},'cdc_bindings':{p:[f'g05_diag_i/fixture/{p}/stage{s}/D' for s in range(3)] for p in PORTS if p.endswith('_i')},
            'cdc_source_review':{'path':str(review),'sha256':b.digest(review),'reviewed_by':b.MAIN}}
        def save(label,value):
            path=out/(label+'.synthetic.json');b.write_json(path,value);return path
        apath=save('source-acceptance',acc)
        check('acceptance-complete-fixture',lambda:b.acceptance(apath,fixture=True))
        check('synthetic-acceptance-refused',lambda:b.acceptance(apath),True)
        for name,mutator in [('missing-header',lambda a:a['sources'].pop(b.SOURCES[3])),
            ('extra-source',lambda a:a['sources'].update({'fpga/old.sv':'0'*64})),
            ('modified-primitive',lambda a:a['sources'].update({b.SOURCES[0]:'0'*64})),
            ('unaccepted-source',lambda a:a.update(accepted=False)),('wrong-commit',lambda a:a.update(source_commit='main')),
            ('missing-tool-pin',lambda a:a['build_files'].pop(b.BUILD_FILES[0])),
            ('unresolved-CDC',lambda a:a.update(cdc_bindings={})),
            ('wildcard-CDC',lambda a:a['cdc_bindings']['yaw_capture_i'].__setitem__(0,'g05_diag_i/*/D')),
            ('reused-CDC',lambda a:a['cdc_bindings'].__setitem__('pitch_capture_i',a['cdc_bindings']['yaw_capture_i'])),
            ('wrong-contract',lambda a:a.update(requirements_sha256='0'*64))]:
            a=copy.deepcopy(acc);mutator(a);p=save(name,a);check(name,lambda p=p:b.acceptance(p,fixture=True),True)
        auth={'TEST_FIXTURE':'synthetic-not-authority','task_id':b.TASK,'task_version':1,'director_thread_id':b.MAIN,
            'authorized':True,'action':'full_g05_diagnostic_build','source_commit':acc['source_commit'],
            'source_acceptance_sha256':b.digest(apath),'requirements_sha256':b.CONTRACT,
            'physical_unknowns_acknowledged':b.PHYSICAL_UNKNOWNS,'work_id':'SYNTHETIC-ONLY',
            'operation_id':'SYNTHETIC-ONLY','output_directory':str(out/'never-launch')}
        authpath=save('authorization',auth)
        check('authorization-fixture',lambda:b.authorization(authpath,apath,acc,out/'never-launch',fixture=True))
        check('synthetic-authorization-refused',lambda:b.authorization(authpath,apath,acc,out/'never-launch'),True)
        for key,value in [('authorized',False),('work_id',b.WORK),('source_acceptance_sha256','0'*64),
                          ('source_commit','2'*40),('output_directory',str(out/'wrong')),('physical_unknowns_acknowledged',[])]:
            a=copy.deepcopy(auth);a[key]=value;p=save('bad-auth-'+key,a)
            check('bad-auth-'+key,lambda p=p:b.authorization(p,apath,acc,out/'never-launch',fixture=True),True)
        check('CLI-build-without-authorization',lambda:b.main(['--mode','build','--out',str(out/'denied'),
              '--contract-json',str(out/'not-read')]),True)
        check('CLI-existing-output',lambda:b.main(['--out',str(out),'--contract-json',str(out/'not-read')]),True)
        done={'run_id':'fixture','top':'g05_diag_wrapper','bd':'g05_diag','part':b.PART,'version':'2026.1',
              'status':'bitstream_complete_pending_hwh_check_and_main_review'}
        check('marker-positive',lambda:b.completion('G05_DIAG_COMPLETE|fixture\n','', 'fixture',done))
        for label,stdout in [('missing-marker',''),('duplicate-marker','G05_DIAG_COMPLETE|fixture\nG05_DIAG_COMPLETE|fixture\n'),('error-after-marker','G05_DIAG_COMPLETE|fixture\nERROR: injected')]:
            check(label,lambda s=stdout:b.completion(s,'','fixture',done),True)
        for label,process in [('parent-only',{'exit_code':0}),('timeout',{'exit_code':0,'timed_out':True}),
            ('unknown-job',{'exit_code':0,'launcher_exit_confirmed':True,'termination_confirmed':True,'job_terminal_confirmed':False})]:
            check('owned-success-refuses-'+label,lambda p=process:b.require_owned_success(p),True)
        cdc=tkinter.Tcl();cdc.call('source',(root/(b.FPGA+'g05_cdc.tcl')).as_posix())
        check('CDC-unresolved-bindings-stop',lambda:cdc.call('apply_g05_cdc','',str(out/'never-report')),True)
        def cdc_fixture(label,period=10,async_reg='TRUE',fanout_extra=0,broken=0,missing=0):
            interp=tkinter.Tcl()
            bindings=acc['cdc_bindings']
            pins=[p for stages in bindings.values() for p in stages]
            roots={}
            for port,stages in bindings.items():
                for i,pin in enumerate(stages):roots[pin]=port if i==0 else stages[i-1][:-1]+'Q'
            if broken:roots[pins[1]]=pins[2][:-1]+'Q'
            interp.call('set','fixture_pins',tuple(pins[:-1] if missing else pins))
            interp.call('set','fixture_roots',interp.call('dict','create',*[v for pair in roots.items() for v in pair]))
            interp.call('set','fixture_first',interp.call('dict','create',*[v for p,s in bindings.items() for v in (p,s[0])]))
            interp.call('set','fixture_period',period);interp.call('set','fixture_async',async_reg)
            interp.call('set','fixture_extra',fanout_extra)
            interp.eval('''
set fixture_exceptions {}
proc get_pins {args} {
 if {[lindex $args 0] eq "-hierarchical"} {return $::fixture_pins}
 set cell [lindex $args 1]
 if {[lindex $args end] eq "REF_PIN_NAME == C"} {return $cell/C}
 return $cell/Q
}
proc get_property {name object} {
 switch -- $name {
  NAME {return $object}
  REF_PIN_NAME {return [file tail $object]}
  IS_SEQUENTIAL {return 1}
  ASYNC_REG {return $::fixture_async}
  PERIOD {return $::fixture_period}
  default {error "unexpected fixture property $name"}
 }
}
proc get_cells {args} {return [file dirname [lindex $args end]]}
proc get_ports {args} {return [lindex $args end]}
proc get_clocks {args} {return fixture_clock}
proc all_fanin {args} {return [list [dict get $::fixture_roots [lindex $args end]]]}
proc all_fanout {args} {
 set result [list [dict get $::fixture_first [lindex $args end]]]
 if {$::fixture_extra} {lappend result unrelated/D}
 return $result
}
proc set_false_path {args} {lappend ::fixture_exceptions $args}
''')
            interp.call('source',(root/(b.FPGA+'g05_cdc.tcl')).as_posix())
            bind=interp.call('dict','create',*[v for p,s in bindings.items() for v in (p,tuple(s))])
            interp.call('apply_g05_cdc',bind,(out/(label+'.synthetic-cdc.txt')).as_posix())
            b.require(int(interp.call('llength',interp.getvar('fixture_exceptions')))==3,'three narrow CDC exceptions only')
        check('CDC-synthetic-three-narrow-first-FF-paths',lambda:cdc_fixture('cdc-good'))
        for label,kwargs in [('wrong-clock',{'period':20}),('missing-ASYNC_REG',{'async_reg':'FALSE'}),
            ('broad-input-fanout',{'fanout_extra':1}),('broken-chain',{'broken':1}),('missing-exact-pin',{'missing':1})]:
            check('CDC-'+label,lambda label=label,kwargs=kwargs:cdc_fixture(label,**kwargs),True)
        xdc=tkinter.Tcl()
        xdc.eval('''
set assignments {}
proc get_ports {args} {return [lindex $args end]}
proc get_property {name port} {
 if {[string match *_capture_i $port]} {return IN}
 return OUT
}
proc set_property {name value port} {lappend ::assignments [list $name $value $port]}
''')
        xdc.call('source',(root/(b.FPGA+'g05_ports.xdc')).as_posix())
        check('XDC-only-six-package-and-six-standard-properties',lambda:b.require(int(xdc.call('llength',xdc.getvar('assignments')))==12,'unexpected XDC properties'))
        # Loading library and malformed bindings never creates any Vivado command.
        check('offline-no-create-project-command',lambda:b.require(tcl.call('info','commands','create_project')=='','unexpected Vivado command'))
        status='passed'
    except BaseException:
        status='failed';cases.append({'failure':traceback.format_exc()})
    b.write_json(out/'RESULT.json',{'status':status,'controls':cases,'control_count':len(cases),
        'scope':'synthetic syntax/parser/gate controls only; no real HWH, Vivado or hardware execution',
        'python':sys.version,'tcl':tkinter.Tcl().call('info','patchlevel'),
        'source_hashes':{p:b.digest(root/p) for p in b.BUILD_FILES}})
    print(json.dumps({'status':status,'control_count':len(cases),'out':str(out),'last':cases[-1]},indent=2))
    return int(status!='passed')


if __name__=='__main__':raise SystemExit(main())
