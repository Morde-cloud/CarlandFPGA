from pathlib import Path
import json,hashlib
W=Path("D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
E=W/"competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20/main"
P=W/"competition/deepeye/tests/rtl/stream/main_tb_encoded_frame_queue.sv"
plan=json.loads((E/"composition_frozen.json").read_bytes())
decl=r"""
logic clk=0,rst=0,cancel=0;
logic in_meta_valid=0,in_meta_ready;
logic [15:0] in_meta_tag=0,out_meta_tag;
logic [1:0] in_meta_error=0,out_meta_error;
logic [7:0] in_meta_count=0,out_meta_count;
logic [3:0] in_meta_e=0,out_meta_e,in_meta_k=0,out_meta_k;
logic in_meta_raw=0,out_meta_raw;
logic [11:0] in_meta_valid_bits=0,out_meta_valid_bits;
logic [8:0] in_meta_bytes=0,out_meta_bytes;
logic in_valid=0,in_ready,in_last=0,out_valid,out_ready=0,out_last;
logic [7:0] in_data=0,out_data;
logic out_meta_valid,out_meta_ready=0;
logic [1:0] level,fault_code;
logic receiving,faulted,fault_event;
logic [STAT_W-1:0] stat_meta,stat_in_bytes,stat_retired,stat_aborted,stat_fault;
wire [31:0] sm=stat_meta,si=stat_in_bytes,sr=stat_retired,sa=stat_aborted,sf=stat_fault;
wire [70:0] stimulus={rst,cancel,in_meta_valid,in_meta_tag,in_meta_error,in_meta_count,in_meta_e,in_meta_raw,in_meta_k,in_meta_valid_bits,in_meta_bytes,in_valid,in_data,in_last,out_meta_ready,out_ready};
wire [235:0] observed={in_meta_ready,in_ready,out_meta_valid,
 out_meta_valid?out_meta_tag:16'd0,out_meta_valid?out_meta_error:2'd0,
 out_meta_valid?out_meta_count:8'd0,out_meta_valid?out_meta_e:4'd0,
 out_meta_valid?out_meta_raw:1'b0,out_meta_valid?out_meta_k:4'd0,
 out_meta_valid?out_meta_valid_bits:12'd0,out_meta_valid?out_meta_bytes:9'd0,
 out_valid,out_valid?out_data:8'd0,out_valid?out_last:1'b0,
 level,receiving,faulted,fault_event,fault_code,sm,si,sr,sa,sf};
deepeye_encoded_frame_queue #(.STAT_W(STAT_W)) dut(.*);
"""
standalone=r"""
module main_queue_tb #(parameter STAT_W=32);
DECL
string input_path,trace_path;
integer inf,tf,rc,edges=0;
reg [70:0] row;
initial begin
 if (!$value$plusargs("INPUT=%s",input_path) || !$value$plusargs("TRACE=%s",trace_path))
  $fatal(1,"MAIN_QUEUE_MISSING_PATH");
 inf=$fopen(input_path,"r");tf=$fopen(trace_path,"w");
 if (!inf || !tf) $fatal(1,"MAIN_QUEUE_FILE_OPEN");
 while (!$feof(inf)) begin
  rc=$fscanf(inf,"%h\n",row);
  if (rc!=1) $fatal(1,"MAIN_QUEUE_BAD_VECTOR edge=%0d rc=%0d",edges,rc);
  {rst,cancel,in_meta_valid,in_meta_tag,in_meta_error,in_meta_count,in_meta_e,in_meta_raw,in_meta_k,in_meta_valid_bits,in_meta_bytes,in_valid,in_data,in_last,out_meta_ready,out_ready}=row;
  #4;
  $fdisplay(tf,"Q %0d %h %h",edges,stimulus,observed);
  #1;clk=1;#5;clk=0;edges=edges+1;
 end
 $fclose(inf);$fclose(tf);
 $display("MAIN_QUEUE_DONE edges=%0d STAT_W=%0d",edges,STAT_W);
 $finish;
end
endmodule
""".replace("DECL",decl)
# Actual composition drives only source/public control ports. Queue input wires
# are the original op09 stream outputs, not a duplicated encoder instance.
compdecl=decl
for text in ("in_meta_valid=0","in_meta_tag=0","in_meta_error=0","in_meta_count=0",
             "in_meta_e=0","in_meta_k=0","in_meta_raw=0","in_meta_valid_bits=0",
             "in_meta_bytes=0","in_valid=0","in_last=0","in_data=0"):
    compdecl=compdecl.replace(text,text.replace("=0",""))
cases=[]
for i,c in enumerate(plan["cases"]):
    lines=[f"{i}: begin",f"send_cfg({c.get('count',len(c['samples']))},{c['e']},{c['tag']});"]
    for j,value in enumerate(c["samples"]):
        lines.append(f"send_sample(16'd{value},1'b{int(j==len(c['samples'])-1)});")
        if j%17==3:lines.append("repeat(2) @(negedge clk);")
    lines.append("end");cases.append("\n".join(lines))
composition=r"""
module main_queue_composition;
parameter STAT_W=32;
DECL
logic cfg_valid=0,cfg_ready,s_valid=0,s_ready,s_last=0;
logic [7:0] cfg_count=0;
logic [3:0] cfg_e=0;
logic [15:0] cfg_tag=0,s_data=0;
logic [1:0] stream_level;
logic stream_filling;
logic [31:0] stream_cfg,stream_samples,stream_ok,stream_error,stream_aborted;
logic hold_outputs=1;
integer cycles=0,tf;
string trace_path;
wire [151:0] source_observed={cfg_valid,cfg_ready,cfg_count,cfg_e,cfg_tag,s_valid,s_ready,s_data,s_last,stream_level,stream_ok,stream_error,stream_aborted};
deepeye_block_stream source(
 .clk(clk),.rst(rst),.cancel(cancel),.cfg_valid(cfg_valid),.cfg_ready(cfg_ready),
 .cfg_count(cfg_count),.cfg_e(cfg_e),.cfg_tag(cfg_tag),.s_valid(s_valid),.s_ready(s_ready),.s_data(s_data),.s_last(s_last),
 .meta_valid(in_meta_valid),.meta_ready(in_meta_ready),.meta_tag(in_meta_tag),.meta_error(in_meta_error),
 .meta_count(in_meta_count),.meta_e(in_meta_e),.meta_raw(in_meta_raw),.meta_k(in_meta_k),
 .meta_valid_bits(in_meta_valid_bits),.meta_bytes(in_meta_bytes),
 .m_valid(in_valid),.m_ready(in_ready),.m_data(in_data),.m_last(in_last),
 .level(stream_level),.filling(stream_filling),.stat_cfg(stream_cfg),.stat_samples(stream_samples),
 .stat_ok(stream_ok),.stat_error(stream_error),.stat_aborted(stream_aborted));
always #5 clk=~clk;
always @(negedge clk) begin
 out_meta_ready<=!hold_outputs && cycles%7!=2;
 out_ready<=!hold_outputs && cycles%11!=3 && cycles%11!=4;
end
always @(posedge clk) begin
 $fdisplay(tf,"C %0d %h %h %h",cycles,stimulus,observed,source_observed);
 cycles=cycles+1;
 if(cycles>700000) $fatal(1,"MAIN_COMPOSITION_TIMEOUT");
end
task automatic send_cfg(input integer n,e,t);
 integer bound;logic accepted;
 begin
 @(negedge clk);cfg_valid=1;cfg_count=n;cfg_e=e;cfg_tag=t;accepted=0;bound=0;
 while(!accepted && bound<250000) begin @(posedge clk);accepted=cfg_ready;bound=bound+1;end
 if(!accepted) $fatal(1,"MAIN_CFG_TIMEOUT");
 @(negedge clk);cfg_valid=0;
 end
endtask
task automatic send_sample(input logic[15:0] value,input logic last);
 integer bound;logic accepted;
 begin
 @(negedge clk);s_valid=1;s_data=value;s_last=last;accepted=0;bound=0;
 while(!accepted && bound<250000) begin @(posedge clk);accepted=s_ready;bound=bound+1;end
 if(!accepted) $fatal(1,"MAIN_SAMPLE_TIMEOUT");
 @(negedge clk);s_valid=0;
 end
endtask
task automatic send_case(input integer which);
 begin case(which)
 CASES
 default:$fatal(1,"MAIN_BAD_CASE");
 endcase end
endtask
task automatic drained(input integer target);
 integer bound;
 begin
 bound=0;
 while((sr<target || level!=0 || stream_level!=0) && bound<250000) begin @(negedge clk);bound=bound+1;end
 if(bound==250000) $fatal(1,"MAIN_DRAIN_TIMEOUT");
 repeat(3) @(negedge clk);
 end
endtask
task automatic abort_shared;
 begin
 @(negedge clk);cancel=1;
 repeat(3) @(negedge clk);
 cancel=0;repeat(2) @(negedge clk);
 end
endtask
integer checkpoint,bound;
initial begin
 if(!$value$plusargs("TRACE=%s",trace_path)) $fatal(1,"MAIN_TRACE_PATH");
 tf=$fopen(trace_path,"w");if(!tf) $fatal(1,"MAIN_TRACE_OPEN");
 rst=1;repeat(3) @(negedge clk);rst=0;
 fork
  begin repeat(100000) @(negedge clk);hold_outputs=0;end
  begin for(integer i=0;i<8;i=i+1) send_case(i);end
 join
 drained(8);
 // Abort a partly received encoded payload while the consumer is stalled.
 hold_outputs=1;checkpoint=si;send_case(1);bound=0;
 while(!(receiving && si>=checkpoint+3) && bound<50000) begin @(negedge clk);bound=bound+1;end
 if(bound==50000) $fatal(1,"MAIN_RECEIVE_PHASE_MISSING");
 abort_shared();hold_outputs=0;send_case(5);drained(9);
 // Abort a sealed metadata offer.
 hold_outputs=1;send_case(0);bound=0;
 while(!out_meta_valid && bound<50000) begin @(negedge clk);bound=bound+1;end
 if(bound==50000) $fatal(1,"MAIN_META_PHASE_MISSING");
 abort_shared();hold_outputs=0;send_case(4);drained(10);
 // Abort after a real output payload handshake, before its terminal byte.
 send_case(1);bound=0;
 while(!(out_valid && out_ready && !out_last) && bound<50000) begin @(posedge clk);bound=bound+1;end
 if(bound==50000) $fatal(1,"MAIN_PAYLOAD_PHASE_MISSING");
 abort_shared();send_case(7);drained(11);
 repeat(5) @(negedge clk);
 $fclose(tf);$display("MAIN_COMPOSITION_DONE cycles=%0d retired=%0d",cycles,sr);$finish;
end
endmodule
""".replace("DECL",compdecl).replace("CASES","\n".join(cases))
# 1+1+8+4+16+1+1+16+1+2+32+32+32 =147, not an implicit extra field.
composition=composition.replace("[151:0] source_observed","[146:0] source_observed")
guard=r"""
module main_queue_guard #(parameter STAT_W=0);
reg clk=0,rst=1,cancel=0;
always #5 clk=~clk;
deepeye_encoded_frame_queue #(.STAT_W(STAT_W)) dut(.clk(clk),.rst(rst),.cancel(cancel));
initial begin #100;$display("MAIN_GUARD_MISSING");$finish;end
endmodule
"""
with P.open("x",encoding="utf-8",newline="\n") as out:out.write(standalone+composition+guard)
with (E/"TB_FREEZE.json").open("x",encoding="utf-8") as out:
    json.dump({"path":str(P),"sha256":hashlib.sha256(P.read_bytes()).hexdigest(),
               "author_RTL_read":False,"scope":"public-port driver/trace only; no expected values or hierarchy probes"},out,indent=2)
print(json.dumps({"path":str(P),"bytes":P.stat().st_size,"sha256":hashlib.sha256(P.read_bytes()).hexdigest()}))
