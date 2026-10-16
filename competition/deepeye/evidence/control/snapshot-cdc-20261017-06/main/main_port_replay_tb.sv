`timescale 1ns/1ps
module main_port_replay_tb;
  parameter integer WIDTH=256;
  reg src_clk=0, dst_clk=0, src_reset_n=0, dst_reset_n=0;
  reg src_valid=0, dst_ready=0;
  reg [WIDTH-1:0] src_data=0;
  wire src_ready, src_online, dst_valid, dst_online;
  wire [WIDTH-1:0] dst_data;
  deepeye_snapshot_mailbox #(.WIDTH(WIDTH)) dut(
    .src_clk(src_clk),.src_reset_n(src_reset_n),.src_valid(src_valid),
    .src_ready(src_ready),.src_data(src_data),.src_online(src_online),
    .dst_clk(dst_clk),.dst_reset_n(dst_reset_n),.dst_valid(dst_valid),
    .dst_ready(dst_ready),.dst_data(dst_data),.dst_online(dst_online));
  integer fi,fo,n,sc,dc,sr,dr,sv,dy,i=0;
  reg [WIDTH-1:0] sd;
  string input_name,output_name;
  initial begin
    if (!$value$plusargs("INPUT=%s",input_name)) $fatal(1,"MISSING_INPUT");
    if (!$value$plusargs("OUTPUT=%s",output_name)) $fatal(1,"MISSING_OUTPUT");
    fi=$fopen(input_name,"r"); fo=$fopen(output_name,"w");
    if (!fi || !fo) $fatal(1,"OPEN_FAILED");
    // Initialize explicit common reset event before the first clock edge.
    #1; src_reset_n=1; dst_reset_n=1; #1; src_reset_n=0; dst_reset_n=0;
    while (!$feof(fi)) begin
      n=$fscanf(fi,"%d %d %d %d %d %d %h\n",sc,dc,sr,dr,sv,dy,sd);
      if (n!=7) $fatal(1,"BAD_VECTOR_LINE");
      #1;
      src_reset_n=sr; dst_reset_n=dr; src_valid=sv; dst_ready=dy; src_data=sd;
      #1;
      // Preedge outputs are observed BEFORE the clock changes and NBA updates.
      $fwrite(fo,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%h,%b,%b,%b,%b,%h,",
        i,sc,dc,sr,dr,sv,dy,sd,src_ready,src_online,dst_valid,dst_online,dst_data);
      src_clk=sc; dst_clk=dc;
      #1;
      $fwrite(fo,"%b,%b,%b,%b,%h\n",src_ready,src_online,dst_valid,dst_online,dst_data);
      i=i+1;
    end
    $fclose(fi); $fclose(fo);
    $display("MAIN_PORT_REPLAY_DONE %0d",i);
    // Remain idle; macro checks completion sentinel and exits at a fixed bound.
  end
endmodule
