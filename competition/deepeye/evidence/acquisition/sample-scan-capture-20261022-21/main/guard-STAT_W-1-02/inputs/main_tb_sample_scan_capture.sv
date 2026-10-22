`timescale 1ns/1ps
module main_tb_sample_scan_capture;
parameter integer SEQ_W=32,TICK_W=64,TAG_W=64,STAT_W=32;
reg clk=0,rst=1,stop=0,rearm=0,sample_strobe=0,out_ready=0;
reg [TAG_W-1:0] rearm_tag=0;
reg [1:0] sample_channel=0;
reg [15:0] sample_data=0;
reg [TICK_W-1:0] sample_tick=0;
reg [7:0] sample_quality=0;
wire out_valid,armed,seq_exhausted,order_error_event,overrun_event,seq_exhaust_event;
wire [63:0] out_data;
wire [4*TICK_W-1:0] out_ticks;
wire [31:0] out_quality;
wire [SEQ_W-1:0] out_first_seq,out_last_seq,next_seq;
wire [TAG_W-1:0] out_tag;
wire [2:0] partial_len;
wire [STAT_W-1:0] stat_events,stat_scans,stat_retired,stat_discarded_samples,stat_order_errors,stat_overruns;
deepeye_sample_scan_capture #(.SEQ_W(SEQ_W),.TICK_W(TICK_W),.TAG_W(TAG_W),.STAT_W(STAT_W)) dut(
.clk(clk),.rst(rst),.stop(stop),.rearm(rearm),.rearm_tag(rearm_tag),
.sample_strobe(sample_strobe),.sample_channel(sample_channel),.sample_data(sample_data),.sample_tick(sample_tick),.sample_quality(sample_quality),.out_ready(out_ready),
.out_valid(out_valid),.out_data(out_data),.out_ticks(out_ticks),.out_quality(out_quality),.out_first_seq(out_first_seq),.out_last_seq(out_last_seq),.out_tag(out_tag),
.armed(armed),.partial_len(partial_len),.next_seq(next_seq),.seq_exhausted(seq_exhausted),.order_error_event(order_error_event),.overrun_event(overrun_event),.seq_exhaust_event(seq_exhaust_event),
.stat_events(stat_events),.stat_scans(stat_scans),.stat_retired(stat_retired),.stat_discarded_samples(stat_discarded_samples),.stat_order_errors(stat_order_errors),.stat_overruns(stat_overruns));
integer src,trace,n,edge_index=0;
reg [4095:0] input_path,trace_path;
task dump;
begin
$fwrite(trace," %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h",out_valid,out_data,out_ticks,out_quality,out_first_seq,out_last_seq,out_tag,armed,partial_len,next_seq,seq_exhausted,order_error_event,overrun_event,seq_exhaust_event,stat_events,stat_scans,stat_retired,stat_discarded_samples,stat_order_errors,stat_overruns);
end
endtask
initial begin
if (!$value$plusargs("INPUT=%s",input_path) || !$value$plusargs("TRACE=%s",trace_path)) $fatal(1,"MAIN_INPUT_ARGUMENT_MISSING");
src=$fopen(input_path,"r");trace=$fopen(trace_path,"w");
if (!src || !trace) $fatal(1,"MAIN_FILE_OPEN_FAILED");
while (!$feof(src)) begin
clk=0;
n=$fscanf(src,"%h %h %h %h %h %h %h %h %h %h\n",rst,stop,rearm,rearm_tag,sample_strobe,sample_channel,sample_data,sample_tick,sample_quality,out_ready);
if (n!=10) $fatal(1,"MAIN_VECTOR_PARSE_FAILED");
#5;
$fwrite(trace,"S %0d %h %h %h %h %h %h %h %h %h %h",edge_index,rst,stop,rearm,rearm_tag,sample_strobe,sample_channel,sample_data,sample_tick,sample_quality,out_ready);
dump();clk=1;#1;dump();$fwrite(trace,"\n");#4;
edge_index=edge_index+1;
end
$fclose(src);$fclose(trace);
$display("MAIN_SAMPLE_SCAN_DONE edges=%0d SEQ_W=%0d TICK_W=%0d TAG_W=%0d STAT_W=%0d",edge_index,SEQ_W,TICK_W,TAG_W,STAT_W);
$finish;
end
endmodule

// All named ports are connected, with context-sized zero inputs and open
// outputs: illegal-parameter checks cannot pass through width warnings.
module main_guard_sample_scan_capture;
parameter integer SEQ_W=32,TICK_W=64,TAG_W=64,STAT_W=32;
deepeye_sample_scan_capture #(.SEQ_W(SEQ_W),.TICK_W(TICK_W),.TAG_W(TAG_W),.STAT_W(STAT_W)) dut(
.clk(1'b0),.rst(1'b1),.stop(1'b0),.rearm(1'b0),.rearm_tag('0),
.sample_strobe(1'b0),.sample_channel('0),.sample_data('0),.sample_tick('0),.sample_quality('0),.out_ready(1'b0),
.out_valid(),.out_data(),.out_ticks(),.out_quality(),.out_first_seq(),.out_last_seq(),.out_tag(),
.armed(),.partial_len(),.next_seq(),.seq_exhausted(),.order_error_event(),.overrun_event(),.seq_exhaust_event(),
.stat_events(),.stat_scans(),.stat_retired(),.stat_discarded_samples(),.stat_order_errors(),.stat_overruns());
initial begin #10;$display("MAIN_GUARD_MISSING");$finish;end
endmodule
