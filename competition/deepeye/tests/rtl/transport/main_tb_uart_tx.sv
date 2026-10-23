`timescale 1ns/1ps
// Main oracle frozen before reading author RTL. Absolute-time division is
// deliberately independent of a phase-accumulator implementation.
module main_tb_uart_tx;
  parameter integer CLOCK_HZ=97, BAUD=11, STAT_W=32, BRIEF=0;
  reg clk=0, rst=1, cancel=0, in_valid=0;
  reg [7:0] in_data=0;
  wire in_ready, tx, busy;
  localparam integer SW=(STAT_W>=2 && STAT_W<=32) ? STAT_W : 2;
  wire [SW-1:0] stat_accepted,stat_completed,stat_aborted;
  deepeye_uart_tx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD),.STAT_W(STAT_W)) dut(.*);
  always #5 clk=~clk;
  reg active=0, known=0, expected_tx=1;
  reg [7:0] saved=0;
  longint unsigned elapsed=0, cycle=0, checks=0, admitted=0, completed=0, aborted=0;
  longint unsigned ca=0, cc=0, cx=0, limit_value;
  integer phase;
  reg event_flag;
  reg [31:0] rng=32'h85ebca6b;
  function automatic [31:0] next_rng(input [31:0] v);
    reg [31:0] t;
    begin t=v^(v<<13); t=t^(t>>17); next_rng=t^(t<<5); end
  endfunction
  task automatic contradiction(input string name,input longint unsigned got,input longint unsigned wanted);
    begin $display("MAIN_MISMATCH cycle=%0d field=%s got=%0d expected=%0d elapsed=%0d",cycle,name,got,wanted,elapsed); $fatal(1,"main numeric mismatch"); end
  endtask
  always @(posedge clk) begin
    cycle=cycle+1; event_flag=0;
    if(known) begin
      checks=checks+1;
      if(in_ready !== (!rst && !cancel && !active)) contradiction("in_ready",in_ready,(!rst&&!cancel&&!active));
    end
    if(rst) begin
      active=0; expected_tx=1; elapsed=0; ca=0; cc=0; cx=0; known=1;
    end else if(cancel) begin
      if(active) begin if(cx<limit_value) cx=cx+1; aborted=aborted+1; event_flag=1; end
      active=0; expected_tx=1; elapsed=0;
    end else if(active) begin
      elapsed=elapsed+1;
      phase=(elapsed*BAUD)/CLOCK_HZ;
      if(phase>=10) begin
        active=0; expected_tx=1; if(cc<limit_value) cc=cc+1;
        completed=completed+1; event_flag=1;
      end else if(phase==0) expected_tx=0;
      else if(phase==9) expected_tx=1;
      else expected_tx=saved[phase-1];
    end else if(in_valid) begin
      active=1; elapsed=0; saved=in_data; expected_tx=0;
      if(ca<limit_value) ca=ca+1; admitted=admitted+1; event_flag=1;
    end
    #1;
    if(known) begin
      checks=checks+5;
      if(tx !== expected_tx) contradiction("tx",tx,expected_tx);
      if(busy !== active) contradiction("busy",busy,active);
      if(stat_accepted !== ca[SW-1:0]) contradiction("accepted",stat_accepted,ca);
      if(stat_completed !== cc[SW-1:0]) contradiction("completed",stat_completed,cc);
      if(stat_aborted !== cx[SW-1:0]) contradiction("aborted",stat_aborted,cx);
      if(event_flag) $display("MAIN_EVENT cycle=%0d busy=%0d tx=%0d accepted=%0d completed=%0d aborted=%0d",cycle,busy,tx,stat_accepted,stat_completed,stat_aborted);
    end
  end
  task automatic step(input bit r,input bit c,input bit v,input [7:0] data);
    begin
      @(negedge clk); rst=r; cancel=c; in_valid=v; in_data=data;
      #1;
      // Abort and data changes must not asynchronously change registered pins.
      if(known && tx !== expected_tx) contradiction("tx_between_edges",tx,expected_tx);
      if(known && busy !== active) contradiction("busy_between_edges",busy,active);
      @(posedge clk); #2;
    end
  endtask
  task automatic drain;
    begin while(active) begin rng=next_rng(rng); step(0,0,1,rng[7:0]); end step(0,0,0,0); end
  endtask
  integer i,j,k;
  longint unsigned deadline;
  initial begin
    limit_value=(64'd1<<STAT_W)-1;
    $display("MAIN_BEGIN clock=%0d baud=%0d stat=%0d brief=%0d",CLOCK_HZ,BAUD,STAT_W,BRIEF);
    step(1,0,0,0); step(1,1,1,255); step(0,0,0,0);
    if(BRIEF) begin
      for(i=0;i<4;i=i+1) begin
        case(i) 0:step(0,0,1,8'h55); 1:step(0,0,1,8'haa); 2:step(0,0,1,8'h00); 3:step(0,0,1,8'hff); endcase
        drain();
      end
    end else begin
      for(i=0;i<256;i=i+1) begin step(0,0,1,i[7:0]); drain(); end
      for(i=0;i<2048;i=i+1) step(0,0,0,i[7:0]);
      for(i=0;i<5000;i=i+1) begin rng=next_rng(rng); step(0,0,rng[1:0]!=0,rng[7:0]); end
      drain();
      // Each bit phase, cancel then reset; original input is perturbed while busy.
      for(j=0;j<2;j=j+1) for(k=0;k<10;k=k+1) begin
        step(0,0,1,8'ha5);
        while(active && (elapsed*BAUD)/CLOCK_HZ < k) step(0,0,1,8'h5a);
        step(j==1,j==0,1,8'hff); step(j==1,j==0,1,8'h00); step(0,0,0,0);
        step(0,0,1,8'h3c); drain();
      end
      deadline=(64'd10*CLOCK_HZ+BAUD-1)/BAUD;
      // Precisely the would-be final completion edge, abort wins.
      for(j=0;j<3;j=j+1) begin
        step(0,0,1,8'hc3);
        while(elapsed<deadline-1) step(0,0,1,8'h5a);
        step(j!=0,j!=1,1,8'hff); step(0,0,0,0);
      end
      // Counter saturation by ordinary accepted frames and aborts.
      for(i=0;i<20;i=i+1) begin step(0,0,1,8'h55); step(0,1,1,8'haa); step(0,1,0,0); step(0,0,0,0); end
      for(i=0;i<20;i=i+1) begin step(0,0,1,i[7:0]); drain(); end
    end
    step(0,0,0,0);
    $display("MAIN_STATS cycles=%0d checks=%0d admitted=%0d completed=%0d aborted=%0d",cycle,checks,admitted,completed,aborted);
    $display("MAIN_PASS"); $finish;
  end
  initial begin #2000000000; $fatal(1,"main watchdog"); end
endmodule
