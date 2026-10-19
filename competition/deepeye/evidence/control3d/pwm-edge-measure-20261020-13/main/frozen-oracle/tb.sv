`timescale 1ns/1ps
// Main replay harness. RLE compresses only identical inputs AND expected ports.
// Every repeated sampled edge is checked; no internal state access or force.
module main_tb_pwm_edge_measure;
parameter COUNT_W=32, TAG_W=32;
reg clk=0,rst=0,stop=0,rearm=0,sample_level=0,out_ready=0;
reg [TAG_W-1:0] window_tag=0;
wire armed,out_valid,overflow_event,overrun_event,overflow_seen,overrun_seen;
wire [COUNT_W-1:0] out_period,out_high,loss_count;
wire [TAG_W-1:0] out_tag;
deepeye_pwm_edge_measure #(.COUNT_W(COUNT_W),.TAG_W(TAG_W)) dut(.*);
reg [63:0] x[0:17];
integer fd,logfd,rows,i,j,k,got,edges=0;reg preval;
string vectors,trace;
initial begin
 if(!$value$plusargs("VECTORS=%s",vectors)||!$value$plusargs("TRACE=%s",trace)) $fatal(1,"missing filenames");
 fd=$fopen(vectors,"r");logfd=$fopen(trace,"w");if(!fd||!logfd)$fatal(1,"file open failed");
 got=$fscanf(fd,"%d\n",rows);if(got!=1||rows<=0)$fatal(1,"invalid row count");
 for(i=0;i<rows;i=i+1)begin
  got=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",x[0],x[1],x[2],x[3],x[4],x[5],x[6],x[7],x[8],x[9],x[10],x[11],x[12],x[13],x[14],x[15],x[16],x[17]);
  if(got!=18||x[0]==0||x[0]>10000000)$fatal(1,"invalid vector row %0d",i);
  for(j=0;j<x[0];j=j+1)begin
   clk=0;rst=x[1];stop=x[2];rearm=x[3];sample_level=x[4];window_tag=x[5];out_ready=x[6];#2;
   preval=out_valid;
   if(out_valid!==x[7][0])$fatal(1,"PUBLIC_PORT_MISMATCH pre row=%0d repeat=%0d edge=%0d got=%h expected=%h",i,j,edges,out_valid,x[7]);
   clk=1;#2;edges=edges+1;
   if(armed!==x[8][0]||out_valid!==x[9][0]||out_period!==x[10][COUNT_W-1:0]||out_high!==x[11][COUNT_W-1:0]||out_tag!==x[12][TAG_W-1:0]||overflow_event!==x[13][0]||overrun_event!==x[14][0]||overflow_seen!==x[15][0]||overrun_seen!==x[16][0]||loss_count!==x[17][COUNT_W-1:0])begin
    $display("got a/v/p/h/tag/ov/rr/os/rs/loss=%h %h %h %h %h %h %h %h %h %h",armed,out_valid,out_period,out_high,out_tag,overflow_event,overrun_event,overflow_seen,overrun_seen,loss_count);
    $display("expected=%h %h %h %h %h %h %h %h %h %h",x[8],x[9],x[10],x[11],x[12],x[13],x[14],x[15],x[16],x[17]);
    $fatal(1,"PUBLIC_PORT_MISMATCH post row=%0d repeat=%0d edge=%0d",i,j,edges);
   end
   clk=0;#1;
  end
  $fdisplay(logfd,"%0d %0d %0d %h %h %h %h %h %h %h %h %h %h %h",i,edges,x[0],preval,armed,out_valid,out_period,out_high,out_tag,overflow_event,overrun_event,overflow_seen,overrun_seen,loss_count);
 end
 $fclose(fd);$fclose(logfd);$display("MAIN_EDGE_MEASURE_PASS edges=%0d rows=%0d",edges,rows);$finish;
end
endmodule
