`timescale 1ns/1ps
module main_buffered_scan_capture;
logic clk=0; always #5 clk=~clk;
logic rst;
logic stop;
logic rearm;
logic queue_cancel;
logic sample_strobe;
logic [31:0] rearm_tag;
logic [1:0] sample_channel;
logic [15:0] sample_data;
logic [63:0] sample_tick;
logic [7:0] sample_quality;
logic out_ready;
logic out_valid;
logic [63:0] out_data;
logic [255:0] out_ticks;
logic [31:0] out_quality;
logic [31:0] out_first_seq;
logic [31:0] out_last_seq;
logic [31:0] out_tag;
logic capture_armed;
logic [2:0] capture_partial_len;
logic [31:0] capture_next_seq;
logic capture_seq_exhausted;
logic capture_order_error_event;
logic capture_overrun_event;
logic capture_seq_exhaust_event;
logic [31:0] capture_stat_events;
logic [31:0] capture_stat_scans;
logic [31:0] capture_stat_retired;
logic [31:0] capture_stat_discarded_samples;
logic [31:0] capture_stat_order_errors;
logic [31:0] capture_stat_overruns;
logic [2:0] queue_level;
logic [31:0] queue_stat_accepted;
logic [31:0] queue_stat_retired;
logic [31:0] queue_stat_aborted;
deepeye_buffered_scan_capture dut(.*);
integer vf,tf,rc,cycle;string vp,tp;
task dump(input string phase);begin
$fwrite(tf,"%s %0d %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",phase,cycle,out_valid,out_data,out_ticks,out_quality,out_first_seq,out_last_seq,out_tag,capture_armed,capture_partial_len,capture_next_seq,capture_seq_exhausted,capture_order_error_event,capture_overrun_event,capture_seq_exhaust_event,capture_stat_events,capture_stat_scans,capture_stat_retired,capture_stat_discarded_samples,capture_stat_order_errors,capture_stat_overruns,queue_level,queue_stat_accepted,queue_stat_retired,queue_stat_aborted);
end endtask
initial begin
rst=0;
stop=0;
rearm=0;
queue_cancel=0;
sample_strobe=0;
rearm_tag=0;
sample_channel=0;
sample_data=0;
sample_tick=0;
sample_quality=0;
out_ready=0;
rst=1;cycle=0;
if(!$value$plusargs("VECTORS=%s",vp)||!$value$plusargs("TRACE=%s",tp))$fatal(1,"ARGS");
vf=$fopen(vp,"r");tf=$fopen(tp,"w");if(!vf||!tf)$fatal(1,"FILES");
while(!$feof(vf))begin
@(negedge clk);rc=$fscanf(vf,"%h %h %h %h %h %h %h %h %h %h %h\n",rst,stop,rearm,queue_cancel,sample_strobe,rearm_tag,sample_channel,sample_data,sample_tick,sample_quality,out_ready);
if(rc!=11)$fatal(1,"VECTOR");
#1;dump("P");@(posedge clk);#1;dump("Q");cycle=cycle+1;
end
$fclose(vf);$fclose(tf);$display("MAIN39_DONE cycles=%0d",cycle);$finish;
end
endmodule
