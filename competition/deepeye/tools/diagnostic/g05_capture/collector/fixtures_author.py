"""NEW software fixtures only. No actual manifest, build, authorization or MMIO."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as E

import pins

# Captured outputs of the pinned DDR resolver, not a completed build package.
# These fixture-only pins must never become production manifest authority.
CAPTURED_DDR = {
    'ddr_literal.json':'50987d08b668e921024f1fe357dd6725cf7b474afbb96bac659b310d89109031',
    'ddr_resolved.json':'8c5ebc3b8f64eb9393fd9f4775e52e1bdb6008aeba9c88b82e0691dbab3734e7',
    'ddr_resolution.json':'c0fc74946ba9070e1fca5c1b9dd686276ede2147d2d3c506ba48475464819685',
    'ddr_expected.tcl':'926e57df13a2aebfa0374cb78bdd6c2b9e9934732923de731bf7f3219ea9acc6',
    'ps7_preset_parameters.json':'f92c4e2c1f2b33da6cd919b77b43e1b79fae64f9a47f86099d54fdad58f2a463',
}


def encoded(obj):
    return (json.dumps(obj,sort_keys=True,indent=2)+'\n').encode()


def synthetic_hwh(guard):
    root=E.Element('EDKSYSTEM',VIVADOVERSION='2026.1',TEST_FIXTURE='synthetic-not-hardware')
    modules=E.SubElement(root,'MODULES');external=E.SubElement(root,'EXTERNALPORTS');interfaces=E.SubElement(root,'EXTERNALINTERFACES')
    def mod(name,vlnv):
        m=E.SubElement(modules,'MODULE',INSTANCE=name,FULLNAME='/'+name,VLNV=vlnv)
        for part in ('PORTS','PARAMETERS','BUSINTERFACES'):E.SubElement(m,part)
        return m
    def param(parent,name,value):E.SubElement(parent,'PARAMETER',NAME=name,VALUE=str(value))
    def port(parent,name,direction,net,links=(),**attrs):
        p=E.SubElement(parent,'PORT',NAME=name,DIR=direction,SIGNAME=net,**attrs)
        c=E.SubElement(p,'CONNECTIONS')
        for instance,signal in links:E.SubElement(c,'CONNECTION',INSTANCE=instance,PORT=signal)
        return p
    ip=mod(guard.INSTANCE,guard.VLNV);ps=mod('ps7_0','xilinx.com:ip:processing_system7:5.5');rst=mod('rst_fclk0','xilinx.com:ip:proc_sys_reset:5.0')
    bus=E.SubElement(ip.find('BUSINTERFACES'),'BUSINTERFACE',NAME='S_AXI',TYPE='SLAVE',VLNV='xilinx.com:interface:aximm:1.0',DATAWIDTH='32')
    for name,value in {'DATA_WIDTH':32,'ADDR_WIDTH':12,'PROTOCOL':'AXI4LITE','FREQ_HZ':100000000}.items():param(bus,name,value)
    for name,n in (('s_axi_wdata',32),('s_axi_rdata',32),('s_axi_awaddr',12),('s_axi_araddr',12)):
        port(ip.find('PORTS'),name,'I',name,LEFT=str(n-1),RIGHT='0')
    E.SubElement(E.SubElement(ps,'MEMORYMAP'),'MEMRANGE',INSTANCE=guard.INSTANCE,SLAVEBUSINTERFACE='S_AXI',MASTERBUSINTERFACE='M_AXI_GP0',BASEVALUE='0x42000000',HIGHVALUE='0x42000fff')
    for name in ('PCW_FPGA0_PERIPHERAL_FREQMHZ','PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ'):param(ps.find('PARAMETERS'),name,'100.000000')
    param(rst.find('PARAMETERS'),'C_EXT_RESET_HIGH',0)
    attrs={'SIGIS':'clk','CLKFREQUENCY':'100000000'}
    for m,name,links in ((ip,'s_axi_aclk',[('ps7_0','FCLK_CLK0')]),(ps,'FCLK_CLK0',[(guard.INSTANCE,'s_axi_aclk'),('ps7_0','M_AXI_GP0_ACLK'),('rst_fclk0','slowest_sync_clk')]),(ps,'M_AXI_GP0_ACLK',[('ps7_0','FCLK_CLK0')]),(rst,'slowest_sync_clk',[('ps7_0','FCLK_CLK0')])):
        port(m.find('PORTS'),name,'O' if name=='FCLK_CLK0' else 'I','clock',links,**attrs)
    attrs={'SIGIS':'rst','POLARITY':'ACTIVE_LOW'}
    for m,name,net,links in ((ip,'s_axi_aresetn','periph',[('rst_fclk0','peripheral_aresetn')]),(rst,'peripheral_aresetn','periph',[(guard.INSTANCE,'s_axi_aresetn')]),(rst,'ext_reset_in','psreset',[('ps7_0','FCLK_RESET0_N')]),(ps,'FCLK_RESET0_N','psreset',[('rst_fclk0','ext_reset_in')])):
        port(m.find('PORTS'),name,'I',net,links,**attrs)
    for prefix,signals in (('DDR','addr ba cas_n ck_n ck_p cke cs_n dm dq dqs_n dqs_p odt ras_n reset_n we_n'),('FIXED_IO','ddr_vrn ddr_vrp mio ps_clk ps_porb ps_srstb')):
        maps=E.SubElement(E.SubElement(interfaces,'BUSINTERFACE',NAME=prefix),'PORTMAPS')
        for signal in signals.split():
            name=prefix+'_'+signal;E.SubElement(maps,'PORTMAP',PHYSICAL=name,LOGICAL=signal)
            port(external,name,'IO',name,[('ps7_0',name)])
    for name,(direction,_) in guard.PORTS.items():
        port(external,name,direction,name,[(guard.INSTANCE,name)])
        port(ip.find('PORTS'),name,direction,name,[('g05_diag_imp',name)])
    return E.tostring(root,encoding='utf-8',xml_declaration=True)


def package_bytes(repo,product,guard,*,ddr_inputs=None):
    """Create marked synthetic metadata around unchanged real source inputs."""
    blobs={}
    for name,digest in pins.SOURCES.items():
        raw=(product/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
        blobs['inputs/rtl_flat/'+Path(name).name]=raw
        if name in list(pins.SOURCES)[:2]:blobs['inputs/readonly_primitives/'+name]=raw
    for name,digest in pins.BUILD_FILES.items():
        raw=(product/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
        blobs['inputs/tooling/'+name]=raw
    for name in ('build_g05.tcl','g05_ports.xdc','g05_cdc.tcl'):
        blobs['inputs/'+name]=(product/'fpga/diagnostic/g05_capture/build'/name).read_bytes()
    for name,digest in pins.LAUNCH_PINS.items():
        if name=='inputs/vendor_ddr_preset.xml':
            source=Path('D:/pynq/AMD2026/2026.1/Vivado/data/PS/7series/data/zynqconfig/ddr/ddr_preset.xml')
        elif '/board_repo/' in name:
            source=Path('D:/pynq/AMD2026/2026.1/Vivado/data/boards/board_files/pynq-z2/A.0')/Path(name).name
        elif '/io_reference/' in name:
            source=repo/'.local/deployment/node-b/evidence/task-resume-20261026/a-g05-inputs/files/competition/deepeye/evidence/system/a-r02-io-map-20261021'/Path(name).name
        else:source=repo/'fpga_mesh/windows_job.py'
        raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==digest;blobs[name]=raw
    blobs['inputs/immutable_scope.json']=subprocess.check_output(['git','show','f5989cd5defce561f9ba98e6b18fc2682945f0a2:docs/competition/deepeye-2026/immutable_scope.json'],cwd=repo,timeout=10)
    blobs['inputs/main_cdc_review']=b'SYNTHETIC AUTHOR PARSER FIXTURE ONLY. No source acceptance or authority.\n'
    if ddr_inputs is None:
        ddr_inputs=repo/'.local/deployment/node-b/evidence/g05-capture-20261026-59/ddr-check-repair/run002/controls/25_snapshots_and_Tcl_tables/inputs'
    for name,digest in CAPTURED_DDR.items():
        raw=(Path(ddr_inputs)/name).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==digest,'captured DDR fixture changed: '+name
        blobs['inputs/'+name]=raw
    blobs['inputs/rtl_sources.txt']=b'SYNTHETIC TEST ONLY\n'
    blobs['inputs/build_config.tcl']=b'# SYNTHETIC TEST ONLY; never executed\n'
    blobs['artifacts/g05_diag.bit']=(b'SYNTHETIC-NOT-A-BITSTREAM\n'*64)
    blobs['artifacts/g05_diag.hwh']=synthetic_hwh(guard)
    blobs['BD_MAPPING.json']=encoded({'instance':guard.INSTANCE,'vlnv':guard.VLNV,'base':'0x42000000','range':'0x1000','bd':'g05_diag','top':'g05_diag_wrapper','master':'ps7_0/Data','slave':'g05_diag_0/S_AXI/Reg','segment':'SYNTHETIC'})
    blobs['VIVADO_COMPLETE.json']=encoded({'run_id':'1'*32,'top':'g05_diag_wrapper','bd':'g05_diag','part':'xc7z020clg400-1','version':'2026.1','status':'bitstream_complete_pending_hwh_check_and_main_review'})
    blobs['PROCESS.json']=encoded({'TEST_FIXTURE':'synthetic-not-authority','elapsed_seconds':0.125,'exit_code':0})
    blobs['process.stdout.bin']=('SYNTHETIC TEST ONLY\nG05_DIAG_COMPLETE|'+'1'*32+'\n').encode()
    blobs['process.stderr.bin']=b''
    return blobs


class SimulatedMMIO:
    """Register-level software model; no RTL, PYNQ or hardware claims."""
    def __init__(self,mode='good'):
        self.mode=mode;self.status=0;self.identity=[0]*13;self.command=[0]*7
        self.writes=[];self.reads=[];self.seq=0;self.applied=0;self.polls=0
        self.record=[];self.held=False;self.saved=False;self.identity_reads=0;self.stop_count=0

    def write(self,offset,value):
        self.writes.append((offset,value))
        if offset==12 and value==3:
            self.stop_count+=1
            if self.mode=='stop_write_fail':raise OSError('injected STOP write failure')
            self.status=3;self.held=False;return
        if offset==0x200 and self.mode=='write_fail':raise OSError('injected command write failure')
        if 0x100<=offset<=0x130:self.identity[(offset-0x100)//4]=value;return
        if 0x200<=offset<=0x218:self.command[(offset-0x200)//4]=value;return
        if offset==12:
            if value==1:
                assert self.status==0;self.status=1
            elif value==2:
                self.seq+=1;self.status=0x4d;self.polls=0;self.applied+=5000000
                if self.mode=='commit_unknown':raise OSError('COMMIT may have happened; never replay')
            elif value==4:
                self.status=0x35;self.held=True;self.saved=False
                yaw,pitch,profile,speed,ttl,cid,tag=self.command
                self.record=[self.seq,cid,tag,profile+(speed<<8),yaw+(pitch<<16),ttl]
                def u64(n):return [n&0xffffffff,n>>32]
                self.record+=u64(self.applied)+u64(self.applied+ttl*100000)+u64(self.applied+4000005)
                self.record += [2000000]*3+[250000,250000,50000]
                self.record += u64(1999997)*3+u64(3999997)*3+[self.identity[12],0x47303544]
                if self.mode=='old_seq' and self.seq==2:self.record[0]=1
                if self.mode=='bad_ttl':self.record[8]+=1
                if self.mode=='bad_causal':self.record[10]-=1
                if self.mode=='skew':self.record[28]+=3
            elif value==5:
                assert self.saved,'ACK before durable validated record'
                self.held=False;self.status=0x15

    def read(self,offset):
        self.reads.append(offset)
        if self.stop_count and self.mode=='stop_read_fail':raise OSError('injected STOP read failure')
        if offset==0x304 and self.held:
            if self.mode=='read_fail':raise OSError('injected record read failure')
            if self.mode=='cancel':raise KeyboardInterrupt('injected cancellation')
        if offset==0:return 0x47303544
        if offset==4:return 1
        if offset==8:
            if self.seq and not self.stop_count and not self.held:
                self.polls+=1
                if self.mode=='pending':return 0x4d
                self.status=0x4d if self.polls<=2 else 5 if self.polls==3 else 0x15
            return self.status
        if offset==0x10:
            if self.stop_count:return 6
            if self.seq and self.mode in ('fault','expiry'):return 3 if self.mode=='fault' else 2
            return 0
        if offset==0x28:return 0
        if 0x100<=offset<=0x130:
            if offset==0x100:self.identity_reads+=1
            v=self.identity[(offset-0x100)//4]
            return v^1 if self.mode=='changed_session' and self.held and self.identity_reads>=3 else v
        if offset==0x14:return self.command[5]
        if offset==0x18:return self.command[6]
        if offset==0x40:return self.applied&0xffffffff
        if offset==0x44:return self.applied>>32
        if 0x300<=offset<=0x37c:return self.record[(offset-0x300)//4]
        raise AssertionError('unmapped read '+hex(offset))
