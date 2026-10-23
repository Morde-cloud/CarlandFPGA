`timescale 1ns/1ps
// Main absolute-time reference frozen before inspection of author RX source.
module main_tb_uart_rx;
parameter longint CLOCK_HZ=97, BAUD=5;
parameter integer STAT_W=32, BRIEF=0;
// Invalid-parameter guard port clamp; legal configurations are unchanged.
localparam integer SW=(STAT_W<2)?2:((STAT_W>32)?32:STAT_W);
localparam longint LIMIT=(64'd1<<SW)-1;
reg clk=0,rst=1,cancel=0,rx_async=1,out_ready=0;
always #5 clk=~clk;
wire out_valid,busy,framing_error_event,overrun_event,false_start_event;
wire [7:0] out_data;
wire [SW-1:0] stat_frames,stat_retired,stat_overruns,stat_framing,stat_false_starts,stat_aborted;
deepeye_uart_rx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD),.STAT_W(STAT_W)) dut(.*);
longint cycles=0,checks=0,good_total=0,retire_total=0,over_total=0,err_total=0,false_total=0,abort_total=0;
longint frames=0,retired=0,overruns=0,framing=0,falses=0,aborted=0,start_at=0;
bit meta=1,syncv=1,prev=1,armed=0,active=0,full=0,fe=0,oe=0,se=0;
integer warm=0,half=1;
reg [7:0] acc=0,slot=0;
function automatic longint sat(input longint n); sat=(n>LIMIT)?LIMIT:n; endfunction
function automatic longint boundary(input longint h); boundary=(h*CLOCK_HZ+2*BAUD-1)/(2*BAUD); endfunction
task automatic eq(input string field,input longint got,input longint expected);
begin checks++; if(got!==expected) begin
 $display("MAIN_MISMATCH cycle=%0d field=%s got=%0d expected=%0d elapsed=%0d",cycles,field,got,expected,cycles-start_at);
 $fatal(1,"main numeric mismatch"); end end endtask
task automatic model;
bit oldsync,oldmeta,oldprev,oldfull,oldactive,ret;
begin
 cycles++; oldsync=syncv;oldmeta=meta;oldprev=prev;oldfull=full;oldactive=active;
 fe=0;oe=0;se=0;
 if(rst) begin
  meta=1;syncv=1;prev=1;warm=0;armed=0;active=0;full=0;half=1;acc=0;slot=0;
  frames=0;retired=0;overruns=0;framing=0;falses=0;aborted=0;
 end else if(cancel) begin
  aborted=sat(aborted+longint'(oldactive)+longint'(oldfull)); abort_total+=longint'(oldactive)+longint'(oldfull);
  meta=1;syncv=1;prev=1;warm=0;armed=0;active=0;full=0;half=1;acc=0;
 end else begin
  ret=oldfull && out_ready;
  if(ret) begin full=0;retired=sat(retired+1);retire_total++;end
  meta=rx_async;syncv=oldmeta;prev=oldsync;
  if(warm<2) warm++;
  else if(!oldactive) begin
   if(oldsync) armed=1;
   else if(armed && oldprev) begin active=1;armed=0;start_at=cycles;half=1;acc=0;end
  end else if(cycles-start_at==boundary(half)) begin
   if(half==1 && oldsync) begin active=0;armed=1;se=1;falses=sat(falses+1);false_total++;end
   else if(half==19) begin
    active=0;armed=oldsync;
    if(!oldsync) begin fe=1;framing=sat(framing+1);err_total++;end
    else begin
     frames=sat(frames+1);good_total++;
     if(oldfull && !ret) begin oe=1;overruns=sat(overruns+1);over_total++;end
     else begin full=1;slot=acc;end
    end
   end else begin if(half>=3) acc[(half-3)/2]=oldsync;half+=2;end
  end
 end
end endtask
task automatic tick(input bit reset_i,input bit cancel_i,input bit line_i,input bit ready_i);
bit oldbusy;
begin
 @(negedge clk);oldbusy=busy;rst=reset_i;cancel=cancel_i;rx_async=line_i;out_ready=ready_i;
 #1;eq("between_busy",busy,oldbusy);eq("between_valid",out_valid,full && !rst && !cancel);
 @(posedge clk);model();#1;
 eq("busy",busy,active);eq("valid",out_valid,full && !rst && !cancel);
 eq("data",out_valid?out_data:0,(full && !rst && !cancel)?slot:0);
 eq("framing_event",framing_error_event,fe);eq("overrun_event",overrun_event,oe);eq("false_event",false_start_event,se);
 eq("frames",stat_frames,frames);eq("retired",stat_retired,retired);eq("overruns",stat_overruns,overruns);
 eq("framing",stat_framing,framing);eq("falses",stat_false_starts,falses);eq("aborted",stat_aborted,aborted);
end endtask
task automatic idle(input integer n,input bit ready_i); begin repeat(n)tick(0,0,1,ready_i);end endtask
task automatic serial(input integer value,input bit stop_i,input integer ready_mode,input integer abort_kind,input integer abort_bit);
longint k,n,phase;bit line_i,rr,cc,rd;
begin
 n=(10*CLOCK_HZ+BAUD-1)/BAUD;
 for(k=0;k<n;k++)begin
  phase=k*BAUD/CLOCK_HZ;
  if(phase==0)line_i=0;else if(phase<9)line_i=(value>>(phase-1))&1;else line_i=stop_i;
  rr=(abort_kind==1 && phase==abort_bit);cc=(abort_kind==2 && phase==abort_bit);
  if(ready_mode==4 && active && cycles+1-start_at==boundary(19))cc=1;
  if(ready_mode==5 && active && cycles+1-start_at==boundary(19))rr=1;
  rd=(ready_mode==1)||(ready_mode==2 && k%7==0);
  // Independent sampling formula schedules a simultaneous old-slot retirement.
  if(ready_mode==3)rd=(active && cycles+1-start_at==boundary(19));
  tick(rr,cc,line_i,rd);
 end
end endtask
integer b,j,v;
initial begin
 $display("MAIN_BEGIN clock=%0d baud=%0d stat=%0d brief=%0d",CLOCK_HZ,BAUD,STAT_W,BRIEF);
 // Guard mode reaches the DUT's time-zero fatal before any tick/division.
 tick(1,0,0,0);repeat(12)tick(0,0,0,0);idle(8,0);
 if(BRIEF)begin
  serial(0,1,1,0,0);serial(255,1,1,0,0);serial(165,1,1,0,0);serial(90,1,1,0,0);idle(8,1);
 end else begin
  for(v=0;v<256;v++)serial(v,1,1,0,0);idle(8,1);
  // A short pulse must be rejected as a false start; low cannot retrigger.
  tick(0,0,0,1);idle(integer'(boundary(1))+10,1);
  serial(8'h63,0,0,0,0);repeat(integer'(CLOCK_HZ/BAUD)+12)tick(0,0,0,0);idle(8,0);
  serial(8'h81,1,0,0,0);serial(8'h29,1,0,0,0);serial(8'h76,1,3,0,0);idle(8,1);
  serial(8'h44,1,0,0,0);serial(8'h92,1,4,0,0);idle(8,0);
  serial(8'h44,1,0,0,0);serial(8'h92,1,5,0,0);idle(8,1);
  // Pending output plus active reception: abort may remove two items.
  for(j=1;j<=2;j++)for(b=0;b<10;b++)begin
   tick(1,0,1,0);idle(8,0);serial(8'ha5,1,0,0,0);serial(8'h3c,1,0,j,b);idle(12,1);
  end
  tick(1,0,1,0);idle(8,0);
  for(v=0;v<12;v++)serial(v,1,0,0,0);idle(8,1);
  for(v=0;v<8;v++)begin serial(v,0,1,0,0);idle(8,1);end
  for(v=0;v<8;v++)begin tick(0,0,0,1);idle(integer'(boundary(1))+10,1);end
  for(v=0;v<8;v++)begin serial(v,1,0,0,0);tick(0,1,0,1);repeat(3)tick(0,1,0,1);idle(8,0);end
  tick(1,1,1,1);idle(8,1);
 end
 $display("MAIN_STATS cycles=%0d checks=%0d frames=%0d retired=%0d overruns=%0d framing=%0d falses=%0d aborted=%0d",cycles,checks,good_total,retire_total,over_total,err_total,false_total,abort_total);
 $display("MAIN_PASS");$finish;
end
initial begin #2000000000; $fatal(1,"main watchdog");end
endmodule
