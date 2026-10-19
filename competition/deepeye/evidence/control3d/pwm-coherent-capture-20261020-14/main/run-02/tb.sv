`timescale 1ns/1ps
// Independent public-port replay; every RLE repetition is checked individually.
module main_tb_pwm_coherent_capture;
parameter COUNT_W=32,WITNESS_W=64,TAG_W=32;
reg clk=0,rst=0,stop=0,rearm=0,out_ready=0;
reg [2:0] sample_levels=0;
reg [TAG_W-1:0] window_tag=0;
wire armed,out_valid;
wire [COUNT_W-1:0] out_period,out_high0,out_high1,out_high2,fault_count;
wire [WITNESS_W-1:0] out_start,out_end;
wire [TAG_W-1:0] out_tag;
wire incoherent_event,period_overflow_event,witness_overflow_event,overrun_event;
wire incoherent_seen,period_overflow_seen,witness_overflow_seen,overrun_seen;
deepeye_pwm_coherent_capture #(.COUNT_W(COUNT_W),.WITNESS_W(WITNESS_W),.TAG_W(TAG_W)) dut(.*);
reg [63:0] x[0:25],v[0:18];reg preval;
integer fd,logfd,rows,i,j,k,got,edges=0;
string vectors,trace;
task snapshot;
begin
 v[0]=preval;v[1]=armed;v[2]=out_valid;v[3]=out_period;
 v[4]=out_high0;v[5]=out_high1;v[6]=out_high2;v[7]=out_start;v[8]=out_end;v[9]=out_tag;
 v[10]=incoherent_event;v[11]=period_overflow_event;v[12]=witness_overflow_event;v[13]=overrun_event;
 v[14]=incoherent_seen;v[15]=period_overflow_seen;v[16]=witness_overflow_seen;v[17]=overrun_seen;v[18]=fault_count;
end
endtask
initial begin
 if(!$value$plusargs("VECTORS=%s",vectors)||!$value$plusargs("TRACE=%s",trace))$fatal(1,"missing filenames");
 fd=$fopen(vectors,"r");logfd=$fopen(trace,"w");if(!fd||!logfd)$fatal(1,"file open failed");
 got=$fscanf(fd,"%d\n",rows);if(got!=1||rows<=0)$fatal(1,"invalid row count");
 for(i=0;i<rows;i=i+1)begin
  got=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",x[0],x[1],x[2],x[3],x[4],x[5],x[6],x[7],x[8],x[9],x[10],x[11],x[12],x[13],x[14],x[15],x[16],x[17],x[18],x[19],x[20],x[21],x[22],x[23],x[24],x[25]);
  if(got!=26||x[0]==0||x[0]>10000000)$fatal(1,"invalid vector row %0d",i);
  for(j=0;j<x[0];j=j+1)begin
   clk=0;rst=x[1];stop=x[2];rearm=x[3];sample_levels=x[4];window_tag=x[5];out_ready=x[6];#2;
   preval=out_valid;
   if(out_valid!==x[7][0])$fatal(1,"PUBLIC_PORT_MISMATCH pre row=%0d repeat=%0d edge=%0d got=%h expected=%h",i,j,edges,out_valid,x[7]);
   clk=1;#2;edges=edges+1;snapshot();
   for(k=0;k<19;k=k+1)if(v[k]!==x[k+7])$fatal(1,"PUBLIC_PORT_MISMATCH post row=%0d repeat=%0d edge=%0d field=%0d got=%h expected=%h",i,j,edges,k,v[k],x[k+7]);
   clk=0;#1;
  end
  $fwrite(logfd,"%0d %0d %0d",i,edges,x[0]);
  for(k=0;k<19;k=k+1)$fwrite(logfd," %h",v[k]);
  $fwrite(logfd,"\n");
 end
 $fclose(fd);$fclose(logfd);$display("MAIN_COHERENT_CAPTURE_PASS edges=%0d rows=%0d",edges,rows);$finish;
end
endmodule
