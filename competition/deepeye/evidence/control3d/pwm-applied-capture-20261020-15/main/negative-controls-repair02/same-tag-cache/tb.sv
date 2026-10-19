`timescale 1ns/1ps
// Independent public-port replay; every RLE repeated edge is checked.
module main_tb_pwm_applied_capture;
parameter COUNT_W=32,WITNESS_W=64,TAG_W=32;
localparam CW=(COUNT_W<2)?2:((COUNT_W>32)?32:COUNT_W);
localparam WW=(WITNESS_W<2)?2:((WITNESS_W>64)?64:WITNESS_W);
localparam TW=(TAG_W<1)?1:((TAG_W>64)?64:TAG_W);
reg clk=0,rst=0,stop=0,cfg_valid=0,out_ready=0,loopback=0;
reg [CW-1:0] cfg_period=0,cfg_high_yaw=0,cfg_high_pitch=0,cfg_high_speed=0;
reg [TW-1:0] cfg_tag=0;
reg [2:0] drive_levels=0;
wire [2:0] sample_levels,pwm;
assign sample_levels=loopback?pwm:drive_levels;
wire cfg_ready,accepted,rejected,applied,frame_start,running,pending;
wire [CW-1:0] active_period,active_high_yaw,active_high_pitch,active_high_speed;
wire [TW-1:0] active_tag;
wire window_active,window_started,capture_armed,out_valid;
wire [CW-1:0] out_period,out_high0,out_high1,out_high2;
wire [WW-1:0] out_start,out_end;
wire [TW-1:0] out_tag;
wire [CW-1:0] expected_period,expected_high0,expected_high1,expected_high2;
wire [TW-1:0] expected_tag;
wire [3:0] raw_fault_events;
wire failure_event;wire [2:0] failure_code;
deepeye_pwm_applied_capture #(.COUNT_W(COUNT_W),.WITNESS_W(WITNESS_W),.TAG_W(TAG_W)) dut(.*);
reg [63:0] x[0:45],v[0:33];reg pre_valid,pre_ready;
integer fd,logfd,rows,i,j,k,got,edges=0;
string vectors,trace;
task snapshot;
begin
 v[0]=pre_valid;
 v[1]=pre_ready;
 v[2]=cfg_ready;
 v[3]=accepted;
 v[4]=rejected;
 v[5]=applied;
 v[6]=frame_start;
 v[7]=running;
 v[8]=pending;
 v[9]=pwm;
 v[10]=active_period;
 v[11]=active_high_yaw;
 v[12]=active_high_pitch;
 v[13]=active_high_speed;
 v[14]=active_tag;
 v[15]=window_active;
 v[16]=window_started;
 v[17]=capture_armed;
 v[18]=out_valid;
 v[19]=out_period;
 v[20]=out_high0;
 v[21]=out_high1;
 v[22]=out_high2;
 v[23]=out_start;
 v[24]=out_end;
 v[25]=out_tag;
 v[26]=expected_period;
 v[27]=expected_high0;
 v[28]=expected_high1;
 v[29]=expected_high2;
 v[30]=expected_tag;
 v[31]=raw_fault_events;
 v[32]=failure_event;
 v[33]=failure_code;
end
endtask
initial begin
 if(!$value$plusargs("VECTORS=%s",vectors)||!$value$plusargs("TRACE=%s",trace))$fatal(1,"missing filenames");
 fd=$fopen(vectors,"r");logfd=$fopen(trace,"w");if(!fd||!logfd)$fatal(1,"file open failed");
 got=$fscanf(fd,"%d\n",rows);if(got!=1||rows<=0)$fatal(1,"invalid row count");
 for(i=0;i<rows;i=i+1)begin
  got=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",x[0],x[1],x[2],x[3],x[4],x[5],x[6],x[7],x[8],x[9],x[10],x[11],x[12],x[13],x[14],x[15],x[16],x[17],x[18],x[19],x[20],x[21],x[22],x[23],x[24],x[25],x[26],x[27],x[28],x[29],x[30],x[31],x[32],x[33],x[34],x[35],x[36],x[37],x[38],x[39],x[40],x[41],x[42],x[43],x[44],x[45]);
  if(got!=46||x[0]==0||x[0]>10000000)$fatal(1,"invalid vector row %0d",i);
  for(j=0;j<x[0];j=j+1)begin
   clk=0;rst=x[1];stop=x[2];cfg_valid=x[3];cfg_period=x[4];cfg_high_yaw=x[5];cfg_high_pitch=x[6];cfg_high_speed=x[7];cfg_tag=x[8];drive_levels=x[9];loopback=x[10];out_ready=x[11];#2;
   pre_valid=out_valid;pre_ready=cfg_ready;
   if(out_valid!==x[12][0]||cfg_ready!==x[13][0])$fatal(1,"PUBLIC_PORT_MISMATCH pre row=%0d repeat=%0d edge=%0d valid=%h/%h ready=%h/%h",i,j,edges,out_valid,x[12],cfg_ready,x[13]);
   clk=1;#2;edges=edges+1;snapshot();
   for(k=0;k<34;k=k+1)if(v[k]!==x[k+12])$fatal(1,"PUBLIC_PORT_MISMATCH post row=%0d repeat=%0d edge=%0d field=%0d got=%h expected=%h",i,j,edges,k,v[k],x[k+12]);
   clk=0;#1;
  end
  $fwrite(logfd,"%0d %0d %0d",i,edges,x[0]);
  for(k=0;k<34;k=k+1)$fwrite(logfd," %h",v[k]);
  $fwrite(logfd,"\n");
 end
 $fclose(fd);$fclose(logfd);$display("MAIN_APPLIED_CAPTURE_PASS edges=%0d rows=%0d",edges,rows);$finish;
end
endmodule
