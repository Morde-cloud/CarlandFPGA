"""Explicit SYNTHETIC_FUNCTION_CONTROL_ONLY data; no authority or fake bitstream.

Main selected unmarked API payloads only inside an externally labelled isolated
fixture directory. Nothing here is passed to prepare/build_run/vendor code.
"""
import json
import xml.etree.ElementTree as E

EVIDENCE_KIND='SYNTHETIC_FUNCTION_CONTROL_ONLY'
BUILD='1234567890abcdef1234567890abcdef'
G05='g05_50_0';TRACE='trace50_0'
GV='carlandfpga.local:diagnostic:deepeye_g05_axi_50:1.0'
TV='carlandfpga.local:diagnostic:deepeye_trace50_axi:1.0'
PINS={'yaw_pwm_o':('O','g05_50_candidate_yaw_pwm_o'),'pitch_pwm_o':('O','g05_50_candidate_pitch_pwm_o'),
 'speed_pwm_o':('O','g05_50_candidate_speed_pwm_o'),'yaw_capture_i':('I','g05_50_candidate_yaw_capture_i'),
 'pitch_capture_i':('I','g05_50_candidate_pitch_capture_i'),'speed_capture_i':('I','g05_50_candidate_speed_capture_i')}
PORTS=('yaw_capture_i','pitch_capture_i','speed_capture_i')


def write_json(path,value):path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n',encoding='utf-8')


def manifest(directory):
    write_json(directory/'SYNTHETIC_FUNCTION_CONTROL_ONLY.json',dict(evidence_kind=EVIDENCE_KIND,
        authority=False,actual95_executed=False,actual_netlist=False,actual_build=False,actual_board=False,
        policy='Unmarked XML/JSON payloads exercise pure validators only; fixture approvals NEVER enter prepare/build_run; no fakebit.'))


def bindings():
    return {port:[f'SYNTHETIC_ONLY/g05_50_0/meta_reg[{i}]/D',f'SYNTHETIC_ONLY/g05_50_0/sync_reg[{i}]/D',
                  f'SYNTHETIC_ONLY/g05_50_0/level_reg[{i}]/D'] for i,port in enumerate(PORTS)}


def cdc_record(run='SYNTHETIC99T',stage='synth'):
    return dict(schema='FUNCTIONAL50_CDC_BINDINGS_V1',mode='ACTUAL_NETLIST_THREE_FF_V1',run_id=run,build_id=BUILD,stage=stage,bindings=bindings())


def xdc():return ''.join('set_false_path -from [get_ports {'+p+'}] -to [get_pins {'+bindings()[p][0]+'}]\n' for p in PORTS)


def mapping():
    return dict(bd='functional50_diag',top='functional50_diag_wrapper',master='ps7_0/Data',build_id=BUILD,
        windows=[dict(instance=G05,vlnv=GV,base='0x41000000',range='0x1000'),dict(instance=TRACE,vlnv=TV,base='0x41003000',range='0x1000')])


def hwh():
    root=E.Element('EDKSYSTEM',VIVADOVERSION='2026.1');mods=E.SubElement(root,'MODULES')
    def module(name,vlnv,params=None):
        m=E.SubElement(mods,'MODULE',INSTANCE=name,FULLNAME='/'+name,VLNV=vlnv)
        ps=E.SubElement(m,'PARAMETERS')
        for k,v in (params or {}).items():E.SubElement(ps,'PARAMETER',NAME=k,VALUE=str(v))
        E.SubElement(m,'PORTS');return m
    def port(m,name,direction='I',net=None,kind=None,polarity=None,freq=None,bits=1,links=()):
        a=dict(NAME=name,DIR=direction)
        if net is not None:a['SIGNAME']=net
        if kind:a['SIGIS']=kind
        if polarity:a['POLARITY']=polarity
        if freq:a['CLKFREQUENCY']=str(freq)
        if bits!=1:a.update(LEFT=str(bits-1),RIGHT='0')
        p=E.SubElement(m.find('PORTS'), 'PORT',a);connections=E.SubElement(p,'CONNECTIONS')
        for i,n in links:E.SubElement(connections,'CONNECTION',INSTANCE=i,PORT=n)
        return p
    enabled={'PCW_USE_M_AXI_GP0','PCW_EN_CLK0_PORT','PCW_EN_RST0_PORT'}
    disabled={'PCW_USE_M_AXI_GP1','PCW_USE_S_AXI_GP0','PCW_USE_S_AXI_GP1','PCW_USE_S_AXI_ACP',
        'PCW_USE_S_AXI_HP0','PCW_USE_S_AXI_HP1','PCW_USE_S_AXI_HP2','PCW_USE_S_AXI_HP3',
        'PCW_EN_CLK1_PORT','PCW_EN_CLK2_PORT','PCW_EN_CLK3_PORT','PCW_EN_RST1_PORT','PCW_EN_RST2_PORT','PCW_EN_RST3_PORT'}
    pp={k:'1' for k in enabled};pp.update({k:'0' for k in disabled});pp.update(PCW_FPGA0_PERIPHERAL_FREQMHZ='50',PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ='50')
    ps=module('ps7_0','xilinx.com:ip:processing_system7:5.5',pp)
    reset=module('rst_fclk0','xilinx.com:ip:proc_sys_reset:5.0',{'C_EXT_RESET_HIGH':'0'})
    axi=module('axi_gp0','xilinx.com:ip:axi_interconnect:2.1',{'NUM_SI':'1','NUM_MI':'2'})
    g=module(G05,GV);t=module(TRACE,TV,{'BUILD_ID':"128'h"+BUILD})
    targets=[('ps7_0',ps,'M_AXI_GP0_ACLK'),('rst_fclk0',reset,'slowest_sync_clk'),(G05,g,'s_axi_aclk'),(TRACE,t,'s_axi_aclk')]
    targets += [('axi_gp0',axi,n) for n in ('ACLK','S00_ACLK','M00_ACLK','M01_ACLK')]
    port(ps,'FCLK_CLK0','O','SYNTHETIC_FCLK50','clk',freq=50000000,links=[(n,p) for n,_,p in targets])
    for n,m,p in targets:port(m,p,net='SYNTHETIC_FCLK50',kind='clk',freq=None if n=='axi_gp0' else 50000000,links=[('ps7_0','FCLK_CLK0')])
    def reset_net(source,source_instance,name,sinks):
        net='SYNTHETIC_'+name;port(source,name,'O',net,'rst','ACTIVE_LOW',links=[(n,p) for n,_,p in sinks])
        for n,m,p in sinks:port(m,p,net=net,kind='rst',polarity=None if n=='axi_gp0' else 'ACTIVE_LOW',links=[(source_instance,name)])
    reset_net(ps,'ps7_0','FCLK_RESET0_N',[('rst_fclk0',reset,'ext_reset_in')])
    reset_net(reset,'rst_fclk0','interconnect_aresetn',[('axi_gp0',axi,'ARESETN')])
    reset_net(reset,'rst_fclk0','peripheral_aresetn',[(G05,g,'s_axi_aresetn'),(TRACE,t,'s_axi_aresetn')]+[('axi_gp0',axi,n) for n in ('S00_ARESETN','M00_ARESETN','M01_ARESETN')])
    for name,value,sinks in [('const_one',1,['dcm_locked']),('const_zero',0,['aux_reset_in','mb_debug_sys_rst'])]:
        m=module(name,'xilinx.com:ip:xlconstant:1.1',dict(CONST_WIDTH=1,CONST_VAL=value));net='SYNTHETIC_'+name
        port(m,'dout','O',net,links=[('rst_fclk0',n) for n in sinks])
        for n in sinks:port(reset,n,net=net,links=[(name,'dout')])
    mm=E.SubElement(ps,'MEMORYMAP')
    for m,name,base in [(g,G05,0x41000000),(t,TRACE,0x41003000)]:
        bus=E.SubElement(E.SubElement(m,'BUSINTERFACES'),'BUSINTERFACE',NAME='S_AXI',TYPE='SLAVE',VLNV='xilinx.com:interface:aximm:1.0',DATAWIDTH='32')
        for k,v in dict(DATA_WIDTH=32,ADDR_WIDTH=12,PROTOCOL='AXI4LITE',FREQ_HZ=50000000).items():E.SubElement(bus,'PARAMETER',NAME=k,VALUE=str(v))
        for n,bits in [('s_axi_wdata',32),('s_axi_rdata',32),('s_axi_awaddr',12),('s_axi_araddr',12),('s_axi_wstrb',4)]:port(m,n,bits=bits)
        E.SubElement(mm,'MEMRANGE',INSTANCE=name,SLAVEBUSINTERFACE='S_AXI',MASTERBUSINTERFACE='M_AXI_GP0',BASEVALUE=hex(base),HIGHVALUE=hex(base+4095))
    interface=E.SubElement(root,'EXTERNALINTERFACES');external=E.SubElement(root,'EXTERNALPORTS')
    for bus,names in [('DDR','addr ba cas_n ck_n ck_p cke cs_n dm dq dqs_n dqs_p odt ras_n reset_n we_n'.split()),('FIXED_IO','ddr_vrn ddr_vrp mio ps_clk ps_porb ps_srstb'.split())]:
        maps=E.SubElement(E.SubElement(interface,'BUSINTERFACE',NAME=bus),'PORTMAPS')
        for n in names:
            full=bus+'_'+n;E.SubElement(maps,'PORTMAP',PHYSICAL=full)
            p=E.SubElement(external,'PORT',NAME=full);cs=E.SubElement(p,'CONNECTIONS');E.SubElement(cs,'CONNECTION',INSTANCE='ps7_0',PORT=full)
    for name,(direction,internal) in PINS.items():
        net='SYNTHETIC_NET_'+name;p=E.SubElement(external,'PORT',NAME=name,DIR=direction,SIGNAME=net)
        cs=E.SubElement(p,'CONNECTIONS');E.SubElement(cs,'CONNECTION',INSTANCE=G05,PORT=internal)
        port(g,internal,direction,net,links=[('functional50_diag_imp',name)])
    return root


def timing_text(row=None):
    header='WNS(ns) TNS(ns) TNS Failing Endpoints TNS Total Endpoints WHS(ns) THS(ns) THS Failing Endpoints THS Total Endpoints WPWS(ns) TPWS(ns) TPWS Failing Endpoints TPWS Total Endpoints'
    return '| Design Timing Summary\n'+header+'\n'+' '.join(['-------']*12)+'\n'+(row or '0.5 0.0 0 99 0.25 0.0 0 99 1.0 0.0 0 12')+'\n\n| Clock Summary\n'
