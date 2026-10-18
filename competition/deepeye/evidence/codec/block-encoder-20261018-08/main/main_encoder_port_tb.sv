`timescale 1ns/1ps
module main_encoder_port_tb;
  logic clk=0;
  always #5 clk=~clk;
  logic rst=1,cancel=0,cfg_valid=0,s_valid=0,s_last=0,meta_ready=0,m_ready=0;
  logic [7:0] cfg_count=0;
  logic [3:0] cfg_e=0;
  logic [15:0] s_data=0;
  wire cfg_ready,s_ready,meta_valid,meta_raw,m_valid,m_last;
  wire [1:0] meta_error;
  wire [7:0] meta_count,m_data;
  wire [3:0] meta_e,meta_k;
  wire [11:0] meta_valid_bits;
  wire [8:0] meta_bytes;
  deepeye_block_encoder dut(.*);
  integer fi,fo,rc,id=-1,requested_n,requested_e,actual_n,last_mode,abort_stage,abort_reset,seed;
  integer samples[0:127];
  integer idx,guard,j,val,cycles=0,cfg_events=0,s_events=0,h_events=0,o_events=0,x_events=0,stall_checks=0;
  integer phase=0,live=0,got_header=0,si=0,oi=0;
  logic old_meta_stall=0,old_data_stall=0;
  logic [39:0] old_meta;
  logic [8:0] old_data;
  wire [39:0] meta_pack={meta_error,meta_count,meta_e,meta_raw,meta_k,meta_valid_bits,meta_bytes};
  string input_path,output_path;
  task fail(input string why);
    begin $display("MAIN_PORT_FAIL id=%0d cycle=%0d %s",id,cycles,why); $fatal(1,"main protocol assertion"); end
  endtask
  // Sole observation point: public ports sampled before sequential updates.
  always @(posedge clk) begin
    cycles=cycles+1;
    if(cycles>50000000) fail("global watchdog");
    if(rst||cancel) begin
      if(cfg_ready!==0||s_ready!==0||meta_valid!==0||m_valid!==0) fail("reset/cancel ports not gated");
      old_meta_stall=0;old_data_stall=0;live=0;got_header=0;si=0;oi=0;
    end else begin
      if(old_meta_stall) begin
        stall_checks=stall_checks+1;
        if(meta_valid!==1 || meta_pack!==old_meta) fail("metadata changed while stalled");
      end
      if(old_data_stall) begin
        stall_checks=stall_checks+1;
        if(m_valid!==1 || {m_last,m_data}!==old_data) fail("payload changed while stalled");
      end
      if($isunknown({cfg_ready,s_ready,meta_valid,m_valid})) fail("unknown handshake");
      if(live && cfg_ready) fail("config ready before current transaction completes");
      if(cfg_valid&&cfg_ready) begin
        if(live || (s_valid&&s_ready)) fail("overlap config or same-cycle first sample");
        live=1;got_header=0;si=0;oi=0;cfg_events=cfg_events+1;
        $fdisplay(fo,"C %0d %0d %0d %0d",id,cycles,cfg_count,cfg_e);
      end
      if(s_valid&&s_ready) begin
        if(!live||got_header) fail("sample outside live input block");
        $fdisplay(fo,"S %0d %0d %0d %0d %0d",id,cycles,si,s_data,s_last);
        si=si+1;s_events=s_events+1;
      end
      if(meta_valid) begin
        if(!live||got_header||$isunknown(meta_pack)) fail("invalid metadata validity");
        if(meta_ready) begin
          got_header=1;h_events=h_events+1;
          $fdisplay(fo,"H %0d %0d %0d %0d %0d %0d %0d %0d %0d",id,cycles,meta_error,meta_count,meta_e,meta_raw,meta_k,meta_valid_bits,meta_bytes);
          if(meta_error!=0) live=0;
        end
      end
      if(m_valid) begin
        if(!live||!got_header||$isunknown({m_data,m_last})) fail("payload without successful earlier header");
        if(m_ready) begin
          $fdisplay(fo,"O %0d %0d %0d %0d %0d",id,cycles,oi,m_data,m_last);
          oi=oi+1;o_events=o_events+1;
          if(m_last) live=0;
        end
      end
      old_meta_stall=meta_valid&&!meta_ready;old_meta=meta_pack;
      old_data_stall=m_valid&&!m_ready;old_data={m_last,m_data};
    end
  end
  // Inputs are driven at falling edges; step returns at the next falling edge.
  task step;
    begin @(posedge clk); #1; @(negedge clk); end
  endtask
  task idle_steps(input integer n);
    integer t;
    begin for(t=0;t<n;t=t+1) step(); end
  endtask
  task abort_block;
    begin
      cfg_valid=0;s_valid=0;meta_ready=0;m_ready=0;
      if(abort_reset) rst=1; else cancel=1;
      x_events=x_events+1;$fdisplay(fo,"X %0d %0d %0d %0d",id,cycles,abort_stage,abort_reset);
      idle_steps(2);rst=0;cancel=0;idle_steps(4);
      if(meta_valid||m_valid||!cfg_ready) fail("not fresh idle after abort");
    end
  endtask
  task one_case;
    logic ready_seen,last_seen;
    integer err_seen;
    begin : body
      cfg_count=requested_n;cfg_e=requested_e;cfg_valid=1;
      s_valid=0;meta_ready=0;m_ready=0;guard=0;
      do begin ready_seen=cfg_ready;step();guard=guard+1;if(guard>40)fail("config timeout");end while(!ready_seen);
      cfg_valid=0;
      for(idx=0;idx<actual_n;idx=idx+1) begin
        s_valid=0;idle_steps((idx+seed)%3);
        s_data=samples[idx];s_last=(idx==requested_n-1);
        if(last_mode==1) s_last=(idx==actual_n-1);
        if(last_mode==2) s_last=0;
        s_valid=1;guard=0;
        do begin ready_seen=s_ready;step();guard=guard+1;if(guard>20000)fail("sample timeout");end while(!ready_seen);
        s_valid=0;
        if(abort_stage==1 && idx==1) begin abort_block();disable body;end
      end
      // Deliberate busy-phase input noise must never become extra samples.
      s_valid=1;s_data=16'hdead;s_last=1;
      if(abort_stage==2) begin idle_steps(1+(seed%5));abort_block();disable body;end
      guard=0;
      while(!meta_valid) begin step();guard=guard+1;if(guard>20000)fail("processing latency exceeded");end
      idle_steps(7+(seed%5));
      if(abort_stage==3) begin abort_block();disable body;end
      err_seen=meta_error;meta_ready=1;step();meta_ready=0;
      if(err_seen!=0) begin idle_steps(4);disable body;end
      guard=0;last_seen=0;j=0;
      while(!last_seen) begin
        m_ready=((j+seed)%7>=3);ready_seen=m_valid&&m_ready;last_seen=ready_seen&&m_last;
        step();j=j+1;guard=guard+1;if(guard>20000)fail("payload timeout");
        if(abort_stage==4&&ready_seen) begin m_ready=0;idle_steps(5);abort_block();disable body;end
      end
      m_ready=0;idle_steps(4);
    end
  endtask
  initial begin
    if(!$value$plusargs("INPUT=%s",input_path)||!$value$plusargs("OUTPUT=%s",output_path))$fatal(1,"missing IO");
    fi=$fopen(input_path,"r");fo=$fopen(output_path,"w");if(!fi||!fo)$fatal(1,"open failed");
    @(negedge clk);idle_steps(4);rst=0;idle_steps(4);
    while(!$feof(fi)) begin
      rc=$fscanf(fi,"%d %d %d %d %d %d %d %d",id,requested_n,requested_e,actual_n,last_mode,abort_stage,abort_reset,seed);
      if(rc==-1)begin end
      else begin
        if(rc!=8)$fatal(1,"bad case header");
        for(j=0;j<actual_n;j=j+1)begin rc=$fscanf(fi,"%d",val);if(rc!=1)$fatal(1,"bad sample");samples[j]=val;end
        one_case();
        $fdisplay(fo,"D %0d %0d",id,cycles);
      end
    end
    idle_steps(5);
    if(live||meta_valid||m_valid)$fatal(1,"unfinished final transaction");
    $fdisplay(fo,"END %0d %0d %0d %0d %0d %0d %0d",cycles,cfg_events,s_events,h_events,o_events,x_events,stall_checks);
    $fclose(fi);$fclose(fo);$display("MAIN_PORT_COMPLETE cycles=%0d",cycles);$finish;
  end
endmodule
