`timescale 1ns/1ps
// Main reference: accepted-frame storage and absolute 8N1 timing.
// Interbyte start edges are observable anchors; every bit after each anchor is
// calculated from CLOCK/BAUD, never from author state or an imported TX model.
module main_tb_uart_frame_tx;
parameter longint CLOCK_HZ=97,BAUD=11;
parameter integer STAT_W=32,PRE_CYCLES=0,POST_CYCLES=0,BRIEF=0;
// Safe port sizing for invalid parameter guards; legal configurations unchanged.
localparam integer SW=(STAT_W<2)?2:((STAT_W>32)?32:STAT_W);
localparam longint LIMIT=(64'd1<<SW)-1;
reg clk=0,rst=1,cancel=0,cfg_valid=0,s_valid=0,s_last=0;
reg [6:0] cfg_count=0;reg [7:0] s_data=0;
always #5 clk=~clk;
wire cfg_ready,s_ready,tx,de,busy,receiving,faulted,fault_event;
wire [1:0] fault_code;
wire [SW-1:0] stat_admitted,stat_sent,stat_aborted,stat_faults;
deepeye_uart_frame_tx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD),.STAT_W(STAT_W),.PRE_CYCLES(PRE_CYCLES),.POST_CYCLES(POST_CYCLES)) dut(.*);
longint cycles=0,checks=0,admitted=0,sent=0,aborted=0,faults=0;
longint all_admitted=0,all_sent=0,all_aborted=0,all_faults=0,all_bytes=0,first_at=0,byte_at=0,release_at=0,seal_at=0;
longint gap_min=1000000,gap_max=0,completed_at=0;
integer state=0,count=0,loaded=0,index=0,code=0;
reg [7:0] frame[0:63];
bit eventv=0,expected_tx=1,expected_de=0;
function automatic longint sat(input longint n);sat=(n>LIMIT)?LIMIT:n;endfunction
function automatic longint byte_cycles();byte_cycles=(10*CLOCK_HZ+BAUD-1)/BAUD;endfunction
task automatic eq(input string field,input longint got,input longint expected);
begin checks++;if(got!==expected)begin
 $display("MAIN_MISMATCH cycle=%0d field=%s got=%0d expected=%0d elapsed=%0d",cycles,field,got,expected,cycles-byte_at);
 $fatal(1,"main numeric mismatch");end end endtask
task automatic model;
longint phase,gap;integer oldstate;
begin
 cycles++;oldstate=state;eventv=0;
 if(rst)begin state=0;code=0;expected_tx=1;expected_de=0;admitted=0;sent=0;aborted=0;faults=0;end
 else if(cancel)begin
  if(state!=0)begin aborted=sat(aborted+1);all_aborted++;end
  state=0;code=0;expected_tx=1;expected_de=0;
 end else begin
  case(oldstate)
  0:begin
   if(cfg_valid)begin
    admitted=sat(admitted+1);all_admitted++;count=cfg_count;loaded=0;index=0;
    if(count<1||count>64)begin state=7;code=1;eventv=1;faults=sat(faults+1);all_faults++;end
    else state=1;
   end
  end
  1:if(s_valid)begin
   if(s_last!=(loaded==count-1))begin state=7;code=2;eventv=1;faults=sat(faults+1);all_faults++;end
   else begin frame[loaded]=s_data;loaded++;if(loaded==count)begin state=2;seal_at=cycles;end end
  end
  2:begin expected_de=1;state=3;first_at=cycles+longint'(PRE_CYCLES)+1;end
  3:if(cycles==first_at)begin state=4;byte_at=cycles;expected_tx=0;all_bytes++;end
  4:begin
   phase=(cycles-byte_at)*BAUD/CLOCK_HZ;
   if(phase>=10)begin
    expected_tx=1;completed_at=cycles;
    if(index==count-1)begin state=6;release_at=cycles+longint'(POST_CYCLES)+1;end
    else begin state=5;index++;end
   end else if(phase==0)expected_tx=0;
   else if(phase<9)expected_tx=frame[index][phase-1];else expected_tx=1;
  end
  5:begin
   expected_tx=1;
   if(tx===1'b0)begin
    gap=cycles-completed_at;if(gap<gap_min)gap_min=gap;if(gap>gap_max)gap_max=gap;
    state=4;byte_at=cycles;expected_tx=0;all_bytes++;
   end
  end
  6:if(cycles==release_at)begin expected_de=0;state=0;sent=sat(sent+1);all_sent++;end
  7:begin end
  default:$fatal(1,"invalid main state");
  endcase
 end
end endtask
task automatic tick(input bit rr,input bit cc,input bit cv,input integer cn,input bit sv,input integer sd,input bit sl);
bit oldtx,oldde,oldbusy;
begin
 @(negedge clk);oldtx=tx;oldde=de;oldbusy=busy;
 rst=rr;cancel=cc;cfg_valid=cv;cfg_count=cn;s_valid=sv;s_data=sd;s_last=sl;
 #1;eq("between_tx",tx,oldtx);eq("between_de",de,oldde);eq("between_busy",busy,oldbusy);
 eq("pre_cfg_ready",cfg_ready,state==0&&!rr&&!cc);eq("pre_s_ready",s_ready,state==1&&!rr&&!cc);
 @(posedge clk);#1;model();
 eq("tx",tx,expected_tx);eq("de",de,expected_de);eq("busy",busy,state!=0);eq("receiving",receiving,state==1);
 eq("faulted",faulted,state==7);eq("fault_event",fault_event,eventv);eq("fault_code",fault_code,code);
 eq("admitted",stat_admitted,admitted);eq("sent",stat_sent,sent);eq("aborted",stat_aborted,aborted);eq("faults",stat_faults,faults);
 eq("cfg_ready",cfg_ready,state==0&&!rr&&!cc);eq("s_ready",s_ready,state==1&&!rr&&!cc);
end endtask
task automatic idle(input integer n);begin repeat(n)tick(0,0,0,0,0,0,0);end endtask
task automatic load_frame(input integer n,input integer seed,input integer bubbles);
integer j;begin
 tick(0,0,1,n,1,255,1);
 for(j=0;j<n;j++)begin if(bubbles)idle((j*3+seed)%4);tick(0,0,0,0,1,(seed+j*37)&255,j==n-1);end
end endtask
task automatic drain;
longint watch,limit;begin
 watch=0;limit=PRE_CYCLES+POST_CYCLES+count*(byte_cycles()+32)+64;
 while(state!=0)begin tick(0,0,1,64,1,231,0);watch++;if(watch>limit)$fatal(1,"main drain watchdog");end
end endtask
integer n,j,k,stage;
initial begin
 $display("MAIN_BEGIN clock=%0d baud=%0d stat=%0d pre=%0d post=%0d brief=%0d",CLOCK_HZ,BAUD,STAT_W,PRE_CYCLES,POST_CYCLES,BRIEF);
 tick(1,0,0,0,0,0,0);idle(2);
 if(BRIEF)begin load_frame(4,0,0);drain();end
 else begin
  for(n=1;n<=64;n++)begin load_frame(n,n,1);drain();end
  for(n=0;n<256;n++)begin load_frame(1,n,0);drain();end
  // Both invalid cardinalities poison, cannot start or consume payload.
  for(n=0;n<128;n++)if(n==0||n>64)begin tick(0,0,1,n,0,0,0);idle(3);tick(0,1,1,1,1,55,1);end
  load_frame(1,9,0);drain();
  tick(0,0,1,4,0,0,0);tick(0,0,0,0,1,14,1);idle(12);tick(0,1,0,0,0,0,0);
  tick(0,0,1,1,0,0,0);tick(0,0,0,0,1,14,0);idle(12);tick(0,1,0,0,0,0,0);
  tick(0,0,1,64,0,0,0);idle(1000);tick(0,1,0,0,0,0,0);
  // Each bit of first and final bytes, synchronous reset/cancel, pending stop.
  for(stage=0;stage<2;stage++)for(j=1;j<=2;j++)for(n=0;n<10;n++)begin
   load_frame(2,165,0);while(state!=4 || index!=stage)idle(1);
   for(k=0;k<(n*CLOCK_HZ+BAUD-1)/BAUD;k++)idle(1);
   tick(j==1,j==2,1,4,1,77,1);repeat(3)tick(j==1,j==2,1,4,1,77,1);idle(2);
  end
  // Abort sealed before DE, pre-guard/first admission, partial and fault.
  load_frame(2,41,0);tick(0,1,0,0,0,0,0);idle(2);
  load_frame(2,41,0);idle(1);tick(0,1,0,0,0,0,0);idle(2);
  tick(0,0,1,3,0,0,0);tick(0,0,0,0,1,99,0);tick(1,0,0,0,0,0,0);idle(2);
  tick(0,0,1,0,0,0,0);tick(1,0,0,0,0,0,0);idle(2);
  // Abort exactly when final completion would release DE; abort wins.
  load_frame(1,255,0);while(state!=6)idle(1);
  while(cycles+1<release_at)idle(1);tick(0,1,1,1,1,22,1);idle(2);
  for(n=0;n<8;n++)begin tick(0,0,1,1,0,0,0);tick(0,1,0,0,0,0,0);end
  for(n=0;n<8;n++)begin load_frame(1,n,0);drain();end
  tick(1,1,1,1,1,1,1);idle(2);
 end
 $display("MAIN_STATS cycles=%0d checks=%0d admitted=%0d sent=%0d aborted=%0d faults=%0d bytes=%0d gap_min=%0d gap_max=%0d",cycles,checks,all_admitted,all_sent,all_aborted,all_faults,all_bytes,gap_min,gap_max);
 $display("MAIN_PASS");$finish;
end
initial begin #2000000000;$fatal(1,"main watchdog");end
endmodule
