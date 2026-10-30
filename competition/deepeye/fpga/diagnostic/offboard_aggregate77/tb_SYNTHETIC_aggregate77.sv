`timescale 1ns/1ps
module tb_SYNTHETIC_aggregate77;
 logic clk=0,rst=1,cancel=0,capture_rearm=0,collect_rearm=0,seal=0,enabled=1;
 logic [31:0] rearm_tag=17;
 logic sample_strobe=0;logic [1:0] sample_channel=0;logic [15:0] sample_data=0;
 logic [63:0] sample_qpc=0;logic [7:0] sample_quality=0;
 logic semantics_valid=1,valid_sample=1,held=0,offer_allowed=0,result_ready=0;
 wire tx,result_valid,refused,quiescent,aborted;wire [2:0] result_error;
 wire [5:0] result_bytes;wire [3:0] refusal_code,count;
 deepeye_SYNTHETIC_aggregate77 dut(.*);
 always #10 clk=~clk;
 integer completed=0,cycles=0,mode=0,uart_n=0,serial_n=0,aborts=0,stalls=0,retired=0;
 integer fd_uart,fd_serial,fd_events,fd_blocks,fd_lanes;string outdir;
 logic [7:0] rx,previous;logic was_stalled=0;
 logic uart_symbol_aborted=0;
 logic [15:0] raw[0:11];logic [7:0] quality[0:3];
 localparam logic [63:0] ORIGIN=64'd9007199254740993;
 always @(posedge clk)begin
  cycles=cycles+1;if(cycles>100000)$fatal(1,"B77 cycle deadline state=%0d count=%0d adapter=%0d",dut.collector_i.state,count,dut.adapter_i.state);
  if(dut.adapter_i.uart_i.serializer_out_valid && dut.adapter_i.uart_i.serializer_out_ready)begin
   $fdisplay(fd_serial,"%02x",dut.adapter_i.uart_i.serializer_out_data);serial_n=serial_n+1;
  end
  if(dut.adapter_cancel)uart_symbol_aborted=1;
  if(!rst && !dut.adapter_cancel)begin
   if(was_stalled && dut.adapter_i.uart_i.serializer_out_valid && dut.adapter_i.uart_i.serializer_out_data!==previous)$fatal(1,"B77 UART backpressure unstable");
   was_stalled=dut.adapter_i.uart_i.serializer_out_valid && !dut.adapter_i.uart_i.serializer_out_ready;
   previous=dut.adapter_i.uart_i.serializer_out_data;if(was_stalled)stalls=stalls+1;
  end else was_stalled=0;
  if(aborted)aborts=aborts+1;
  if(dut.retire)retired=retired+1;
  if(dut.lane_valid && dut.lane_ready)$fdisplay(fd_lanes,"%0d %0d %0d %0d %0d %0d %0d",dut.lane_channel,dut.lane_data,dut.lane_qpc,dut.lane_quality,dut.lane_tag,dut.lane_first,dut.lane_last);
  if(dut.block_valid && dut.block_ready)$fdisplay(fd_blocks,"%0d %012x %048x %06x %024x %024x %0d %0d %0d %0d",dut.channel,dut.data,dut.qpcs,dut.qualities,dut.firsts,dut.lasts,dut.tag,dut.first_index,dut.stride_ns,dut.stride_us);
 end
 initial forever begin
  @(negedge tx);uart_symbol_aborted=0;repeat(15)@(posedge clk);#1;
  for(integer b=0;b<8;b=b+1)begin rx[b]=tx;repeat(10)@(posedge clk);#1;end
  if(!uart_symbol_aborted && !dut.adapter_cancel)begin if(tx!==1)$fatal(1,"UART stop");$fdisplay(fd_uart,"%02x",rx);uart_n=uart_n+1;end
 end
 task automatic step(input integer n);repeat(n)@(negedge clk);endtask
 task automatic scan(input integer sn);
  for(integer c=0;c<4;c=c+1)begin
   sample_channel=c;sample_data=raw[sn*4+c];sample_qpc=ORIGIN+64'd10000123+sn*64'd10000000+c*64'd1007;
   sample_quality=quality[c];
   if(mode==1 && sn==1 && c==2)sample_quality=sample_quality^8'h01;
   if(mode==2 && sn==2 && c==0)sample_qpc=sample_qpc+1;
   if(mode==6 && sn==0 && c==0)sample_qpc=64'h8000000000000000;
   sample_strobe=1;step(1);sample_strobe=0;step(1);
  end
  step(6);
 endtask
 task automatic expect_refusal(input integer code);
  while(!refused)step(1);
  if(refusal_code!=code || uart_n!=0 || serial_n!=0)$fatal(1,"B77 refusal expected%0d actual%0d bytes%0d",code,refusal_code,uart_n);
  $fdisplay(fd_events,"REFUSED %0d COUNT %0d",refusal_code,count);
 endtask
 task automatic flush;
  cancel=1;step(120);if(!quiescent)$fatal(1,"B77 cancel not quiescent");
  cancel=0;step(20);if(count!=0 || dut.lane_ready || result_valid)$fatal(1,"B77 cancel replay");
 endtask
 task automatic output_four;
  logic [47:0] saved_data;logic [191:0] saved_qpcs;logic [95:0] saved_firsts;
  seal=1;step(1);seal=0;
  while(!dut.block_valid)step(1);
  saved_data=dut.data;saved_qpcs=dut.qpcs;saved_firsts=dut.firsts;
  step(12);
  if(dut.data!==saved_data || dut.qpcs!==saved_qpcs || dut.firsts!==saved_firsts || count!=12 || dut.lane_ready)$fatal(1,"B77 output offer unstable");
  $fdisplay(fd_events,"COLLECTOR_BACKPRESSURE_STABLE");offer_allowed=1;
  for(integer c=0;c<4;c=c+1)begin
   while(!result_valid)step(1);
   if(result_error!=0)$fatal(1,"B77 wrapper result%0d",result_error);
   step(10);if(!result_valid || dut.lane_ready)$fatal(1,"B77 result backpressure");
   $fdisplay(fd_events,"RESULT %0d %0d",c,result_bytes);
   result_ready=1;step(1);result_ready=0;step(2);
  end
  if(retired!=4 || count!=0 || dut.lane_ready || uart_n!=serial_n || stalls==0)$fatal(1,"B77 retirement/cost");
 endtask
 initial begin
  if(!$value$plusargs("OUT=%s",outdir))$fatal(1,"OUT required");if(!$value$plusargs("MODE=%d",mode))mode=0;
  fd_uart=$fopen({outdir,"/uart.hex"},"w");fd_serial=$fopen({outdir,"/serializer.hex"},"w");fd_events=$fopen({outdir,"/events.txt"},"w");
  fd_blocks=$fopen({outdir,"/blocks.txt"},"w");fd_lanes=$fopen({outdir,"/lanes.txt"},"w");
  if(!fd_uart||!fd_serial||!fd_events||!fd_blocks||!fd_lanes)$fatal(1,"file open");
  raw[0]=32769;raw[1]=65280;raw[2]=4096;raw[3]=65535;
  raw[4]=32770;raw[5]=65279;raw[6]=5000;raw[7]=0;
  raw[8]=32771;raw[9]=65278;raw[10]=6000;raw[11]=65535;
  quality[0]=128;quality[1]=254;quality[2]=85;quality[3]=163;
  step(5);rst=0;capture_rearm=1;collect_rearm=1;step(1);capture_rearm=0;collect_rearm=0;step(2);
  if(mode==12)$fatal(1,"B77_INTENTIONAL_RUNNER_NEGATIVE");
  if(mode>=14 && mode<=16)begin
   scan(0);scan(1);scan(2);while(count!=12)step(1);
   seal=1;step(1);seal=0;offer_allowed=1;
   while(dut.collector_i.state!=4 || !dut.adapter_i.uart_i.transaction_active_q)step(1);
   if(mode==16)begin
    while(uart_n<3)step(1);step(20);
    result_ready=1;collect_rearm=1;step(1);collect_rearm=0;
    if(!refused || refusal_code!=9)$fatal(1,"busy rearm not refused9");
    step(6000);
    if(retired!=0 || result_valid || dut.adapter_i.busy || aborts!=1 || uart_n!=3 || serial_n!=4 || !refused || refusal_code!=9)
     $fatal(1,"busy rearm old effect retired or resumed uart%0d serial%0d abort%0d retire%0d",uart_n,serial_n,aborts,retired);
    $fdisplay(fd_events,"BUSY_REARM_REFUSED9 UART %0d SERIAL %0d ABORT %0d RETIRED %0d STABLE_CLOCKS 6000",uart_n,serial_n,aborts,retired);
    flush();
   end else begin
    enabled=0;result_ready=1;step(120);
    if(!quiescent || count!=0 || result_valid || retired!=0 || dut.armed || aborts!=1)$fatal(1,"gate withdrawal did not flush accepted WAIT_RETIRE");
    $fdisplay(fd_events,"GATE_WITHDRAW_WAIT_RETIRE QUIESCENT ABORT %0d RETIRED %0d",aborts,retired);
    if(mode==15)begin
     enabled=1;step(6000);
     if(!quiescent || count!=0 || dut.armed || result_valid || retired!=0 || uart_n!=0 || serial_n!=0 || dut.lane_ready)
      $fatal(1,"gate restore replayed old epoch");
     $fdisplay(fd_events,"GATE_RESTORE_NO_REPLAY CLOCKS 6000 UART %0d SERIAL %0d RETIRED %0d",uart_n,serial_n,retired);
     rearm_tag=18;capture_rearm=1;collect_rearm=1;step(1);capture_rearm=0;collect_rearm=0;step(3);
     if(!dut.armed || count!=0 || !dut.lane_ready || result_valid || uart_n!=0)$fatal(1,"fresh explicit rearm invalid");
     $fdisplay(fd_events,"FRESH_REARM TAG 18 COUNT 0 NO_OLD_PAYLOAD");flush();
    end
   end
  end else if(mode==13)begin $fdisplay(fd_events,"RUNNER_SUCCESS");end
  else if(mode==3)begin held=1;scan(0);expect_refusal(1);end
  else if(mode==4 || mode==5)begin
   scan(0);while(count<4)step(1);
   if(mode==4)rearm_tag=18;capture_rearm=1;step(1);capture_rearm=0;step(2);scan(1);
   expect_refusal(mode==4?2:3);
  end else if(mode==7)begin scan(0);scan(1);while(count<8)step(1);seal=1;step(1);seal=0;expect_refusal(7);end
  else begin
   scan(0);if(!refused)scan(1);if(!refused)begin
    if(mode==8)begin
     // Third scan creates four queued lanes. Seal is mutually exclusive with
     // every lane handshake; simultaneous last lane is explicitly refused.
     fork
      scan(2);
      begin while(count!=11)step(1);seal=1;step(1);seal=0;end
     join
    end else scan(2);
   end
   case(mode)
    0:begin while(count!=12)step(1);output_four();end
    1:expect_refusal(5);
    2:expect_refusal(6);
    6:expect_refusal(4);
    8:expect_refusal(7);
    9:begin
     while(count!=12)step(1);scan(0);step(10);
     if(!dut.lane_valid || dut.lane_ready || count!=12)$fatal(1,"B77 thirteenth lane not held");
     $fdisplay(fd_events,"THIRTEENTH_BACKPRESSURED");output_four();
     if(!dut.lane_valid || dut.lane_ready)$fatal(1,"B77 pending input replay");flush();
    end
    10:begin while(count!=12)step(1);flush();if(uart_n!=0)$fatal(1,"B77 preseal emitted");end
    11:begin
     while(count!=12)step(1);seal=1;step(1);seal=0;offer_allowed=1;
     while(uart_n<3)step(1);step(20);flush();
     if(aborts!=1 || retired!=0)$fatal(1,"B77 abort/retirement");
     $fdisplay(fd_events,"PARTIAL_CANCEL %0d %0d ABORT %0d",uart_n,serial_n,aborts);
    end
    default:$fatal(1,"unknown mode");
   endcase
  end
  $fdisplay(fd_events,"DONE %0d UART %0d SERIAL %0d RETIRED %0d STALLS %0d",cycles,uart_n,serial_n,retired,stalls);
  $fclose(fd_uart);$fclose(fd_serial);$fclose(fd_events);
  $fclose(fd_blocks);$fclose(fd_lanes);
  completed=1;$display("B77_DONE mode=%0d cycles=%0d uart=%0d serial=%0d",mode,cycles,uart_n,serial_n);$finish;
 end
endmodule
