"""Generate the explicitly synthetic B74 data-only harness from B73 wiring.

This does not edit, instantiate, force, or release the production integration top.
The generated fixture exposes gates solely for bounded simulation.
"""
from pathlib import Path
import hashlib,json,re

P=Path(__file__).resolve().parents[3]
D=P/'fpga/diagnostic/offboard_codec74'
BASE=P/'fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_integration_50mhz_candidate.sv'

def main():
    raw=BASE.read_bytes(); s=raw.decode()
    # Preserve the exact data composition and association predicates. G05 is
    # outside this work's simulation and is omitted, never replaced or enabled.
    s=s[s.index('`default_nettype none'):]
    s=s.replace('deepeye_integration_50mhz_candidate','deepeye_SYNTHETIC_codec74_fixture',1)
    s=s.replace('parameter integer BAUD = 0','parameter integer BAUD = 5000000')
    s=s.replace("parameter bit SOURCE_REVIEW_HOLD = 1'b1","parameter bit SOURCE_REVIEW_HOLD = 1'b0")
    a=s.index('    // G05 private AXI4-Lite candidate.')
    z=s.index(');',a)
    s=s[:a]+'''    input logic fixture_profile_enabled, fixture_transport_enabled,
    input wire logic fixture_result_ready
'''+s[z:]
    a=s.index('    deepeye_g05_axi_50mhz_candidate g05_i (')
    s=s[:a]+'endmodule\n`default_nettype wire\n'
    s=s.replace(".profile_v2_authorized(1'b0), .transport_allowed(1'b0)",
                '.profile_v2_authorized(fixture_profile_enabled), .transport_allowed(fixture_transport_enabled)')
    s=s.replace("assign trace_result_ready = 1'b1;",'assign trace_result_ready = fixture_result_ready;')
    s='// SYNTHETIC_FIXTURE ONLY: copied B73 data wiring; no production enable.\n'+s
    (D/'deepeye_SYNTHETIC_codec74_fixture.sv').write_text(s,encoding='utf-8',newline='\n')
    s=s.replace('input logic','input wire logic')
    (D/'deepeye_SYNTHETIC_codec74_fixture.sv').write_text(s,encoding='utf-8',newline='\n')
    ports=s[s.index('    input wire logic fclk50_candidate'):s.index(');')]
    ports=re.sub(r'//[^\n]*','',ports)
    rows=[];direction=width=None
    for part in ports.split(','):
        part=part.strip()
        m=re.fullmatch(r'(input|output)\s+(?:wire\s+)?logic\s*(\[[^]]+\])?\s*(\w+)',part)
        if m: direction,width,name=m.groups()
        else: name=part
        rows.append((direction,width or '',name))
    declarations='\n'.join('logic '+w+' '+n+';' for _,w,n in rows)
    connections=',\n'.join('.'+n+'('+n+')' for _,_,n in rows)
    init='\n'.join(n+"=0;" for d,_,n in rows if d=='input')
    (D/'ports.json').write_text(json.dumps(rows,indent=2)+'\n')
    template=(D/'tb_body.sv.inc').read_text()
    tb='`timescale 1ns/1ps\nmodule tb_SYNTHETIC_codec74;\n'+declarations+'\n'
    tb+='deepeye_SYNTHETIC_codec74_fixture dut(\n'+connections+'\n);\n'
    tb+=template.replace('@@INIT@@',init)+'\nendmodule\n'
    (D/'tb_SYNTHETIC_codec74.sv').write_text(tb,encoding='utf-8',newline='\n')
    print(json.dumps({'synthetic_fixture_generated':True,'copied_source_sha256':hashlib.sha256(raw).hexdigest()}))

if __name__=='__main__':main()
