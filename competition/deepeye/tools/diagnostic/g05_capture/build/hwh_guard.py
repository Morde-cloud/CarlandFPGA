"""Strict structural G05 HWH checks. Synthetic parser fixtures are never build proof."""
import xml.etree.ElementTree as ET

VLNV = 'carlandfpga.local:diagnostic:deepeye_g05_axi:1.0'
INSTANCE = 'g05_diag_0'
PORTS = {'yaw_pwm_o': ('O','W14'), 'pitch_pwm_o': ('O','Y14'),
         'speed_pwm_o': ('O','T11'), 'yaw_capture_i': ('I','V16'),
         'pitch_capture_i': ('I','W16'), 'speed_capture_i': ('I','V12')}


def require(test, text):
    if not test:
        raise ValueError(text)


def one(items, text):
    require(len(items)==1, 'expected exactly one '+text)
    return items[0]


def named(parent, path, name):
    return one([p for p in parent.findall(path) if p.get('NAME')==name],name)


def parameters(parent):
    return {p.get('NAME'):p.get('VALUE') for p in parent.findall('./PARAMETER')}


def connections(port):
    pairs=[(p.get('INSTANCE'),p.get('PORT')) for p in port.findall('./CONNECTIONS/CONNECTION')]
    require(len(pairs)==len(set(pairs)), 'duplicate port connection')
    return set(pairs)


def width(port):
    require(('LEFT' in port.attrib)==('RIGHT' in port.attrib),'partial width metadata')
    return abs(int(port.get('LEFT','0'))-int(port.get('RIGHT','0')))+1


def verify_hwh(path, mapping, *, fixture=False):
    root=ET.parse(path).getroot()
    is_fixture=root.get('TEST_FIXTURE')=='synthetic-not-hardware'
    require(is_fixture==fixture,'fixture provenance mismatch; synthetic HWH cannot prove a build')
    require(root.tag=='EDKSYSTEM' and root.get('VIVADOVERSION')=='2026.1','HWH format/version mismatch')
    require(mapping.get('instance')==INSTANCE and mapping.get('vlnv')==VLNV,'BD identity mismatch')
    require(mapping.get('bd')=='g05_diag' and mapping.get('top')=='g05_diag_wrapper','BD/top mismatch')
    modules=root.findall('./MODULES/MODULE')
    def module(name,vlnv):
        m=one([m for m in modules if m.get('INSTANCE')==name or m.get('FULLNAME','').strip('/')==name],name)
        require(m.get('INSTANCE')==name and m.get('FULLNAME')=='/'+name and m.get('VLNV')==vlnv,'module identity mismatch: '+name)
        return m
    ip=module(INSTANCE,VLNV)
    ps=module('ps7_0','xilinx.com:ip:processing_system7:5.5')
    reset=module('rst_fclk0','xilinx.com:ip:proc_sys_reset:5.0')
    require(len([m for m in modules if m.get('VLNV')==VLNV])==1,'duplicate G05 IP')
    bus=named(ip,'./BUSINTERFACES/BUSINTERFACE','S_AXI')
    bp=parameters(bus)
    require(bus.get('TYPE')=='SLAVE' and bus.get('VLNV')=='xilinx.com:interface:aximm:1.0','AXI slave metadata')
    require(bus.get('DATAWIDTH')=='32' and bp.get('DATA_WIDTH')=='32' and bp.get('ADDR_WIDTH')=='12','AXI width')
    require(bp.get('PROTOCOL')=='AXI4LITE','AXI protocol')
    for physical,bits in (('s_axi_wdata',32),('s_axi_rdata',32),('s_axi_awaddr',12),('s_axi_araddr',12)):
        require(width(named(ip,'./PORTS/PORT',physical))==bits,'physical AXI width: '+physical)
    ranges=[p for p in root.iter('MEMRANGE') if p.get('INSTANCE')==INSTANCE]
    address=one(ranges,'G05 MEMRANGE')
    require(address.get('SLAVEBUSINTERFACE')=='S_AXI' and address.get('MASTERBUSINTERFACE')=='M_AXI_GP0','AXI address interface')
    base,high=int(address.attrib['BASEVALUE'],0),int(address.attrib['HIGHVALUE'],0)
    require(base>=0 and base%4096==0 and high<=0xffffffff and high-base+1==4096,'4KiB aligned address span')
    require(base==int(mapping['base'],0) and int(mapping['range'],0)==4096,'actual BD/HWH address mismatch')

    clock=named(ip,'./PORTS/PORT','s_axi_aclk')
    psclock=named(ps,'./PORTS/PORT','FCLK_CLK0')
    for port in (clock,psclock,named(ps,'./PORTS/PORT','M_AXI_GP0_ACLK'),named(reset,'./PORTS/PORT','slowest_sync_clk')):
        require(port.get('CLKFREQUENCY')=='100000000' and port.get('SIGIS')=='clk','connected clock is not 100MHz')
        require(port.get('SIGNAME')==psclock.get('SIGNAME') and bool(port.get('SIGNAME')),'clock net mismatch')
    require(connections(clock)=={('ps7_0','FCLK_CLK0')},'G05 clock source')
    for instance,port in ((INSTANCE,'s_axi_aclk'),('ps7_0','M_AXI_GP0_ACLK'),('rst_fclk0','slowest_sync_clk')):
        require((instance,port) in connections(psclock),'PS FCLK endpoint missing')
    pp=parameters(ps.find('PARAMETERS'))
    require(float(pp['PCW_FPGA0_PERIPHERAL_FREQMHZ'])==100.0 and float(pp['PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ'])==100.0,'PS configured/actual FCLK0')
    # GP0 descriptive FREQ_HZ can be stale. Actual connected PORT net/frequency above is authoritative.
    require(bp.get('FREQ_HZ')=='100000000','G05 AXI clock metadata mismatch')
    rp=parameters(reset.find('PARAMETERS'))
    require(rp.get('C_EXT_RESET_HIGH')=='0','derived reset polarity')
    ipreset=named(ip,'./PORTS/PORT','s_axi_aresetn')
    peripheral=named(reset,'./PORTS/PORT','peripheral_aresetn')
    extreset=named(reset,'./PORTS/PORT','ext_reset_in')
    psreset=named(ps,'./PORTS/PORT','FCLK_RESET0_N')
    for port in (ipreset,peripheral,extreset,psreset):
        require(port.get('POLARITY')=='ACTIVE_LOW' and port.get('SIGIS')=='rst','active-low reset metadata')
    require(connections(ipreset)=={('rst_fclk0','peripheral_aresetn')} and (INSTANCE,'s_axi_aresetn') in connections(peripheral),'G05 peripheral reset connection')
    require(ipreset.get('SIGNAME')==peripheral.get('SIGNAME') and bool(ipreset.get('SIGNAME')),'peripheral reset net')
    require(connections(extreset)=={('ps7_0','FCLK_RESET0_N')} and ('rst_fclk0','ext_reset_in') in connections(psreset),'PS reset controller connection')
    require(extreset.get('SIGNAME')==psreset.get('SIGNAME') and bool(extreset.get('SIGNAME')),'PS reset net')

    interfaces=root.findall('./EXTERNALINTERFACES/BUSINTERFACE')
    require(sorted(x.get('NAME') for x in interfaces)==['DDR','FIXED_IO'],'unexpected external interface')
    ps_members={p.get('PHYSICAL') for b in interfaces for p in b.findall('./PORTMAPS/PORTMAP')}
    expected_ps={'DDR_'+n for n in ('addr','ba','cas_n','ck_n','ck_p','cke','cs_n','dm','dq','dqs_n','dqs_p','odt','ras_n','reset_n','we_n')}
    expected_ps|={'FIXED_IO_'+n for n in ('ddr_vrn','ddr_vrp','mio','ps_clk','ps_porb','ps_srstb')}
    require(ps_members==expected_ps,'complete exact PS interface membership')
    external=root.findall('./EXTERNALPORTS/PORT')
    require(len(external)==len({p.get('NAME') for p in external}),'duplicate external port')
    require({p.get('NAME') for p in external}==ps_members|set(PORTS),'extra/missing PL external port')
    for p in external:
        name=p.get('NAME')
        if name not in PORTS:
            require(connections(p) and all(i=='ps7_0' for i,_ in connections(p)),'PS member must connect only to PS')
    nets=[]
    for name,(direction,pin) in PORTS.items():
        ext=named(root,'./EXTERNALPORTS/PORT',name)
        port=named(ip,'./PORTS/PORT',name)
        require(width(ext)==1 and width(port)==1 and ext.get('DIR')==port.get('DIR')==direction,'scalar port width/direction: '+name)
        require(connections(ext)=={(INSTANCE,name)},'external port miswired: '+name)
        require(connections(port)=={('g05_diag_imp',name)},'G05 port must connect only to its external pin: '+name)
        require(bool(port.get('SIGNAME')) and port.get('SIGNAME')==ext.get('SIGNAME'),'external net mismatch: '+name)
        nets.append(port.get('SIGNAME'))
    require(len(set(nets))==6,'internal PWM/capture short or aliased external nets')
    return {'status':'synthetic_parser_fixture_pass' if fixture else 'same_run_hwh_structure_verified',
            'instance':INSTANCE,'vlnv':VLNV,'base':hex(base),'span':4096,'data_width':32,
            'connected_clock_hz':100000000,'reset':'PS active-low through proc_sys_reset',
            'external_ports':list(PORTS),'physical_validation':'not_run; HWH alone is not physical proof'}
