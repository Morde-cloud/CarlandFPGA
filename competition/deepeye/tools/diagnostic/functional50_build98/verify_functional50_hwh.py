"""Strict structural verifier for the NEW98 functional50 HWH and timing gate.

Read-only: parses HWH XML, BD_MAPPING.json and same-run timing reports. It does
not launch Vivado or a simulator, run Tcl, touch a board, use network/service
credentials, mutate Git or write a build directory. A passing result is
structural evidence only, never physical-board or H01-H15 acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import functional50_contract as c


def require(test, message):
    if not test:
        raise ValueError(message)


def one(items, description):
    values = list(items)
    require(len(values) == 1, "expected exactly one " + description)
    return values[0]


def named(parent, path, name):
    return one([item for item in parent.findall(path) if item.get("NAME") == name], name)


def parameters(parent):
    require(parent is not None, "missing parameter container")
    values = {}
    for item in parent.findall("./PARAMETERS/PARAMETER") + parent.findall("./PARAMETER"):
        key = item.get("NAME")
        require(key is not None and key not in values, "duplicate/malformed parameter")
        values[key] = item.get("VALUE")
    return values


def connections(port):
    pairs = [(item.get("INSTANCE"), item.get("PORT")) for item in port.findall("./CONNECTIONS/CONNECTION")]
    require(len(pairs) == len(set(pairs)), "duplicate port connection")
    return set(pairs)


def width(port):
    left, right = port.get("LEFT"), port.get("RIGHT")
    require((left is None) == (right is None), "partial port width metadata")
    if left is None:
        return 1
    return abs(int(left) - int(right)) + 1


def port(module, name):
    return named(module, "./PORTS/PORT", name)


def int_value(value, description):
    text = str(value).strip()
    require(re.fullmatch(r"(0[xX][0-9a-fA-F]+|[0-9]+)", text) is not None, "invalid integer: " + description)
    return int(text, 16 if text.lower().startswith("0x") else 10)


def parse_build_id(value):
    text = str(value).strip().lower().replace("_", "")
    if text.startswith("128'h"):
        text = text[5:]
    elif text.startswith("0x"):
        text = text[2:]
    require(re.fullmatch(r"[0-9a-f]{1,32}", text) is not None, "BUILD_ID must be at most 32 hex digits")
    parsed = int(text, 16)
    require(0 < parsed < (1 << 128), "BUILD_ID must be nonzero and fit 128 bits")
    return parsed


def finite_number(value, description):
    require(type(value) in (int, float, str) and re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", str(value)) is not None,
            "invalid numeric metric: " + description)
    number = float(value)
    require(math.isfinite(number), "nonfinite metric: " + description)
    return number


def record(path):
    data = Path(path).read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def verify_hwh(path, mapping, expected_build_id):
    """Read actual same-run HWH topology; no MMIO or synthetic build claims."""
    raw = Path(path).read_bytes()
    require(0 < len(raw) <= 8*1024*1024 and b'<!DOCTYPE' not in raw and b'<!ENTITY' not in raw, "bounded plain HWH XML required")
    root = ET.fromstring(raw)
    require(root.tag == "EDKSYSTEM" and root.get("VIVADOVERSION") == c.VIVADO_VERSION, "HWH format/version")
    require("TEST_FIXTURE" not in root.attrib, "synthetic HWH cannot establish a same-run build")
    require(isinstance(expected_build_id, str) and re.fullmatch(r"[0-9a-f]{32}", expected_build_id) and int(expected_build_id,16)>0,
            "exact nonzero expected BUILD_ID required")
    require(mapping.get("bd") == c.BD_NAME and mapping.get("top") == c.TOP_NAME and mapping.get("master") == "ps7_0/Data", "BD mapping identity")
    require(mapping.get("build_id") == expected_build_id, "mapping/expected BUILD_ID mismatch")
    windows = mapping.get("windows")
    require(isinstance(windows,list) and len(windows)==2 and
            [(w.get("instance"),w.get("vlnv")) for w in windows] == [(c.G05_INSTANCE,c.G05_VLNV),(c.TRACE_INSTANCE,c.TRACE_VLNV)], "exact two selected windows")
    modules = root.findall("./MODULES/MODULE")
    def module(name,vlnv):
        obj = one([m for m in modules if m.get("INSTANCE")==name or m.get("FULLNAME","").strip("/")==name],name)
        require(obj.get("INSTANCE")==name and obj.get("FULLNAME")=="/"+name and obj.get("VLNV")==vlnv,"module identity: "+name)
        return obj
    ps = module("ps7_0","xilinx.com:ip:processing_system7:5.5")
    reset = module("rst_fclk0","xilinx.com:ip:proc_sys_reset:5.0")
    interconnect = module("axi_gp0","xilinx.com:ip:axi_interconnect:2.1")
    g05 = module(c.G05_INSTANCE,c.G05_VLNV);trace = module(c.TRACE_INSTANCE,c.TRACE_VLNV)
    private = [m for m in modules if m.get("VLNV","").startswith("carlandfpga.local:diagnostic:")]
    require(len(private)==2 and {m.get("VLNV") for m in private}=={c.G05_VLNV,c.TRACE_VLNV}, "old/duplicate/unselected private IP")
    pp = parameters(ps);rp = parameters(reset);ip = parameters(interconnect)
    for key in ("PCW_USE_M_AXI_GP0","PCW_EN_CLK0_PORT","PCW_EN_RST0_PORT"):
        require(int_value(pp.get(key),key)==1,"required PS interface: "+key)
    for key in ("PCW_USE_M_AXI_GP1","PCW_USE_S_AXI_GP0","PCW_USE_S_AXI_GP1","PCW_USE_S_AXI_ACP",
                "PCW_USE_S_AXI_HP0","PCW_USE_S_AXI_HP1","PCW_USE_S_AXI_HP2","PCW_USE_S_AXI_HP3",
                "PCW_EN_CLK1_PORT","PCW_EN_CLK2_PORT","PCW_EN_CLK3_PORT","PCW_EN_RST1_PORT","PCW_EN_RST2_PORT","PCW_EN_RST3_PORT"):
        require(int_value(pp.get(key),key)==0,"unused PS interface must be disabled: "+key)
    for key in ("PCW_FPGA0_PERIPHERAL_FREQMHZ","PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ"):
        require(finite_number(pp.get(key),key)==50.0,"PS configured/actual FCLK0 must be 50MHz")
    require(int_value(ip.get("NUM_SI"),"NUM_SI")==1 and int_value(ip.get("NUM_MI"),"NUM_MI")==2,"one GP0/two interconnect master interfaces")
    require(rp.get("C_EXT_RESET_HIGH")=="0","actual propagated reset polarity must be active low")
    require(parse_build_id(parameters(trace).get("BUILD_ID"))==int(expected_build_id,16),"TRACE HWH/mapping/closure BUILD_ID mismatch")
    # G05 is unchanged and has NO BUILD_ID parameter/register. Its exact source,
    # selected VLNV and same-run BIT/HWH linkage are verified by the builder.
    require("BUILD_ID" not in parameters(g05),"unexpected G05 source/interface identity change")
    ranges = list(root.iter("MEMRANGE"))
    gp0 = [r for r in ranges if r.get("MASTERBUSINTERFACE")=="M_AXI_GP0"]
    require(len(gp0)==2 and {r.get("INSTANCE") for r in gp0}=={c.G05_INSTANCE,c.TRACE_INSTANCE},"unexpected/missing GP0 peripheral mapping")
    spans=[]
    for window,obj in zip(windows,(g05,trace)):
        name=window["instance"];bus=named(obj,"./BUSINTERFACES/BUSINTERFACE","S_AXI");bp=parameters(bus)
        require(bus.get("TYPE")=="SLAVE" and bus.get("VLNV")=="xilinx.com:interface:aximm:1.0","AXI-Lite slave metadata")
        require(bus.get("DATAWIDTH")=="32" and bp.get("DATA_WIDTH")=="32" and bp.get("ADDR_WIDTH")=="12" and bp.get("PROTOCOL")=="AXI4LITE","exact AXI dimensions/protocol")
        require(bp.get("FREQ_HZ")==str(c.CLOCK_HZ),"AXI clock metadata must be 50MHz")
        for physical,bits in (("s_axi_wdata",32),("s_axi_rdata",32),("s_axi_awaddr",12),("s_axi_araddr",12),("s_axi_wstrb",4)):
            require(width(port(obj,physical))==bits,"physical AXI width: "+name+"/"+physical)
        address=one([r for r in ranges if r.get("INSTANCE")==name],name+" MEMRANGE")
        require(address in gp0 and address.get("SLAVEBUSINTERFACE")=="S_AXI","selected address interfaces")
        base=int_value(address.get("BASEVALUE"),"HWH base");high=int_value(address.get("HIGHVALUE"),"HWH high")
        require(base>=0 and base%4096==0 and high<=0xffffffff and high-base+1==4096,"exact aligned uint32 4KiB HWH span")
        require(base==int_value(window.get("base"),"mapping base") and int_value(window.get("range"),"mapping range")==4096,"actual HWH/BD_MAPPING aperture mismatch")
        spans.append((base,high))
        require(not any(p.get("SIGIS","").lower() in {"interrupt","int","irq"} for p in obj.findall("./PORTS/PORT")),"selected endpoint must not introduce an interrupt")
    require(spans[0][1]<spans[1][0] or spans[1][1]<spans[0][0],"two peripheral windows overlap")
    psclock=port(ps,"FCLK_CLK0");clock_net=psclock.get("SIGNAME")
    require(clock_net and psclock.get("SIGIS")=="clk" and psclock.get("CLKFREQUENCY")==str(c.CLOCK_HZ),"actual PS clock output metadata")
    clock_targets=[("ps7_0",ps,"M_AXI_GP0_ACLK"),("rst_fclk0",reset,"slowest_sync_clk"),
        (c.G05_INSTANCE,g05,"s_axi_aclk"),(c.TRACE_INSTANCE,trace,"s_axi_aclk")]
    clock_targets += [("axi_gp0",interconnect,n) for n in ("ACLK","S00_ACLK","M00_ACLK","M01_ACLK")]
    for name,obj,pname in clock_targets:
        pin=port(obj,pname)
        require(pin.get("SIGIS")=="clk" and pin.get("SIGNAME")==clock_net and connections(pin)=={("ps7_0","FCLK_CLK0")},"common direct FCLK0 domain: "+name+"/"+pname)
        if pin.get("CLKFREQUENCY") is not None:
            require(pin.get("CLKFREQUENCY")==str(c.CLOCK_HZ),"inconsistent connected clock frequency")
    require(connections(psclock)=={(name,pname) for name,_,pname in clock_targets},"unexpected/missing actual PS clock endpoints")
    def reset_net(source,source_name,targets):
        origin=port(source,source_name);net=origin.get("SIGNAME")
        require(net and origin.get("SIGIS")=="rst" and origin.get("POLARITY")=="ACTIVE_LOW","active-low reset source metadata")
        expected=set()
        for name,obj,pname in targets:
            pin=port(obj,pname);expected.add((name,pname))
            require(pin.get("SIGNAME")==net and pin.get("SIGIS")=="rst", "common reset sink net/type metadata")
            # Existing generated HWH omits POLARITY on AXI-interconnect ARESETN
            # ports. Their exact direct source above is explicitly active-low.
            # Preserve strict explicit polarity on PS/controller/private ports.
            require(pin.get("POLARITY") in ((None,"ACTIVE_LOW") if name=="axi_gp0" else ("ACTIVE_LOW",)),
                    "active-low common reset sink metadata")
            origin_name="ps7_0" if source is ps else "rst_fclk0"
            require(connections(pin)=={(origin_name,source_name)},"reset sink source")
        require(connections(origin)==expected,"reset source exact endpoints")
    reset_net(ps,"FCLK_RESET0_N",[("rst_fclk0",reset,"ext_reset_in")])
    reset_net(reset,"interconnect_aresetn",[("axi_gp0",interconnect,"ARESETN")])
    reset_net(reset,"peripheral_aresetn",[(c.G05_INSTANCE,g05,"s_axi_aresetn"),(c.TRACE_INSTANCE,trace,"s_axi_aresetn")]+
              [("axi_gp0",interconnect,n) for n in ("S00_ARESETN","M00_ARESETN","M01_ARESETN")])
    for name,value,sinks in (("const_one",1,("dcm_locked",)),("const_zero",0,("aux_reset_in","mb_debug_sys_rst"))):
        constant=module(name,"xilinx.com:ip:xlconstant:1.1");cp=parameters(constant)
        require(int_value(cp.get("CONST_WIDTH"),"constant width")==1 and int_value(cp.get("CONST_VAL"),"constant value")==value,"reset controller constant")
        output=port(constant,"dout");require(connections(output)=={("rst_fclk0",n) for n in sinks},"constant endpoints")
        for n in sinks:
            pin=port(reset,n);require(connections(pin)=={(name,"dout")} and pin.get("SIGNAME")==output.get("SIGNAME") and pin.get("SIGNAME"),"reset constant sink")
    interfaces=root.findall("./EXTERNALINTERFACES/BUSINTERFACE")
    require(sorted(x.get("NAME","") for x in interfaces)==["DDR","FIXED_IO"],"only DDR/FIXED_IO external interfaces")
    ps_members={p.get("PHYSICAL") for b in interfaces for p in b.findall("./PORTMAPS/PORTMAP")}
    expected_ps={"DDR_"+n for n in ("addr","ba","cas_n","ck_n","ck_p","cke","cs_n","dm","dq","dqs_n","dqs_p","odt","ras_n","reset_n","we_n")}
    expected_ps|={"FIXED_IO_"+n for n in ("ddr_vrn","ddr_vrp","mio","ps_clk","ps_porb","ps_srstb")}
    require(ps_members==expected_ps,"exact complete PS external membership")
    external=root.findall("./EXTERNALPORTS/PORT")
    require(len(external)==len({p.get("NAME") for p in external}) and {p.get("NAME") for p in external}==ps_members|set(c.PINS),"extra/missing top port; external UART forbidden")
    for pin in external:
        if pin.get("NAME") not in c.PINS:
            require(connections(pin) and all(i=="ps7_0" for i,_ in connections(pin)),"PS external member must connect only to PS")
    nets=[]
    for name,selected in c.PINS.items():
        ext=named(root,"./EXTERNALPORTS/PORT",name);pin=port(g05,selected["g05_port"])
        require(width(ext)==width(pin)==1 and ext.get("DIR")==pin.get("DIR")==selected["direction"],"exact six scalar PL directions/widths")
        require(connections(ext)=={(c.G05_INSTANCE,selected["g05_port"])} and connections(pin)=={(c.TOP_IMP,name)},"exact external G05 pin connection")
        require(pin.get("SIGNAME") and pin.get("SIGNAME")==ext.get("SIGNAME"),"external G05 net identity")
        nets.append(pin.get("SIGNAME"))
    require(len(set(nets))==6,"aliased/shorted G05 PWM/capture nets")
    return {"status":"same_run_hwh_structure_verified", "hwh":record(path),"windows":windows,"connected_clock_hz":c.CLOCK_HZ,
            "trace_build_id":expected_build_id,"g05_build_id":"not present in unchanged source; same-run manifest/VLNV linkage only",
            "metadata_labels":{"g05_magic":hex(c.G05_MAGIC),"g05_layout":c.G05_LAYOUT,"trace_magic":hex(c.TRACE_MAGIC),"trace_layout":c.TRACE_LAYOUT},
            "labels_are_mmio_observations":False,"intrinsic_memory_entries":[dict(r.attrib) for r in ranges if r not in gp0],
            "cpu_memory_certification":False,"ps_interrupt_configuration_certified":False,
            "physical_validation":"not_run; A-only; HWH topology is not physical evidence"}


SUMMARY_HEADER = 'WNS(ns) TNS(ns) TNS Failing Endpoints TNS Total Endpoints WHS(ns) THS(ns) THS Failing Endpoints THS Total Endpoints WPWS(ns) TPWS(ns) TPWS Failing Endpoints TPWS Total Endpoints'


def parse_design_timing_summary(path):
    text=Path(path).read_text('utf-8',errors='strict');lines=text.splitlines()
    require(len(re.findall(r'^\s*\|?\s*Design Timing Summary\s*$',text,re.M))==1,"one Design Timing Summary section required")
    headers=[];in_design=False
    for i,line in enumerate(lines):
        value=line.strip();title=value.lstrip('|').strip()
        if title=='Design Timing Summary':in_design=True
        elif re.match(r'^\|\s*[A-Za-z]',value):in_design=False
        if re.match(r'^WNS\(ns\)(?:\s|$)',value):
            require(in_design and ' '.join(value.split())==SUMMARY_HEADER,"out-of-section/unsupported design summary header")
            headers.append(i)
    index=one(headers,'design summary header')
    require(index+2<len(lines) and re.fullmatch(r'-+(?:\s+-+)+',lines[index+1].strip()),"missing summary separator/row")
    row=lines[index+2].split();require(len(row)==12,"one twelve-field design summary row required")
    require(index+3>=len(lines) or re.match(r'^\s*[+-]?(?:[0-9]|\.[0-9])',lines[index+3]) is None,"duplicate summary row")
    data={}
    for name,i in (("wns_ns",0),("tns_ns",1),("whs_ns",4),("ths_ns",5),("wpws_ns",8),("tpws_ns",9)):
        data[name]=finite_number(row[i],name)
    for name,i in (("setup_failing_endpoints",2),("setup_total_endpoints",3),("hold_failing_endpoints",6),("hold_total_endpoints",7),("pulse_failing_endpoints",10),("pulse_total_endpoints",11)):
        require(re.fullmatch('[0-9]+',row[i]) is not None,"invalid summary endpoint count")
        data[name]=int(row[i])
    require(data['setup_total_endpoints']>0 and data['hold_total_endpoints']>0,"empty setup/hold inventory")
    return data


def verify_check_timing(path):
    text=Path(path).read_text('utf-8',errors='strict');counts=re.findall(r'^\s*[0-9]+\.\s+checking unconstrained_internal_endpoints\s+\(([0-9]+)\)\s*$',text,re.M)
    require(len(counts)==2 and counts[0]==counts[1] and int(counts[0])==0,"missing/ambiguous/nonzero same-run unconstrained endpoint inventory")
    return {"unconstrained_internal_endpoints":0,"report":record(path)}


def verify_timing_gate(path, check_timing):
    path=Path(path);check_timing=Path(check_timing)
    require(path.parent.resolve()==check_timing.parent.resolve(),"timing reports must belong to the same run directory")
    summary_path=path.parent/'route_timing_summary.txt'
    summary=parse_design_timing_summary(summary_path)
    gate=json.loads(path.read_text('utf-8'))
    require(isinstance(gate,dict),"timing gate object required")
    for key in ('wns_ns','tns_ns','whs_ns','ths_ns'):
        require(key in gate and finite_number(gate[key],key)==summary[key] and summary[key]>=0,"negative/inconsistent same-run summary metric: "+key)
    for key in ('setup_failing_endpoints','hold_failing_endpoints'):
        require(type(gate.get(key)) is int and gate[key]==summary[key]==0,"nonzero/inconsistent failing endpoint inventory")
    require(summary['wpws_ns']>=0 and summary['tpws_ns']>=0 and summary['pulse_failing_endpoints']==0,
            "negative/violating design pulse-width summary")
    for key in ('drc_errors','drc_critical_warnings','lutlp1'):
        require(type(gate.get(key)) is int and gate[key]==0,"missing/nonzero DRC inventory: "+key)
    clocks=gate.get('clocks');require(isinstance(clocks,list) and clocks,"actual clocks required")
    names=set();periods=[]
    for clock in clocks:
        require(isinstance(clock,dict) and set(clock)=={'name','period_ns'} and isinstance(clock['name'],str) and clock['name'] and clock['name'] not in names,"exact distinct clock records")
        names.add(clock['name']);period=finite_number(clock['period_ns'],'clock period');require(period>0,"positive actual clock period")
        periods.append(period)
    has20=any(abs(x-20.0)<=.00001 for x in periods);has10=any(abs(x-10.0)<=.00001 for x in periods)
    require(type(gate.get('has_20ns_clock')) is int and gate['has_20ns_clock']==int(has20)==1,"actual 20ns clock missing")
    require(type(gate.get('has_10ns_clock')) is int and gate['has_10ns_clock']==int(has10)==0,"unexpected actual 10ns clock")
    require(gate.get('authoritative_source')=='same-run route_timing_summary.txt Design Timing Summary; get_drc_violations/get_clocks',"timing source identity")
    return {"status":"same_run_timing_consistency_verified","summary":summary,"summary_report":record(summary_path),
            "gate_report":record(path),"check_timing":verify_check_timing(check_timing),"clocks":clocks,
            "board_result":False,"independent_physical_or_formal_acceptance":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hwh',type=Path);parser.add_argument('--mapping',type=Path);parser.add_argument('--expected-build-id')
    parser.add_argument('--timing-gate',type=Path);parser.add_argument('--check-timing',type=Path)
    args=parser.parse_args(argv)
    try:
        result={}
        if args.hwh is not None:
            require(args.mapping is not None and args.expected_build_id is not None,'HWH requires mapping and expected-build-id')
            result['hwh']=verify_hwh(args.hwh,json.loads(args.mapping.read_text('utf-8')),args.expected_build_id)
        if args.timing_gate is not None:
            require(args.check_timing is not None,'timing gate requires same-run check-timing')
            result['timing']=verify_timing_gate(args.timing_gate,args.check_timing)
        require(result,'select HWH and/or timing verification')
        print(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2));return 0
    except Exception as error:
        print(type(error).__name__+': '+str(error),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
