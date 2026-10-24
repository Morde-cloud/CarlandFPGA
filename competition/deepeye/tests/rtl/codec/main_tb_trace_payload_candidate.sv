`timescale 1ns/1ps
// Main38 independent preinspection public-port driver; fixed bitstring vectors.
module main_trace_payload;
  reg clk=0; always #5 clk=~clk;
  reg rst=1,cancel=0,cv=0,sv=0,sl=0,mr=0,orr=0;
  reg [7:0] cn=0; reg [3:0] ce=0; reg [31:0] session=0,idx=0;
  reg [1:0] ch=0; reg [63:0] tick=0,source_tick=0;
  reg [15:0] istride=0,tstride=0,sd=0;
  reg valid_sample=0,sat=0,held=0,sfault=0;
  wire cr,sr,mv,ov,ol; wire [1:0] me; wire [5:0] ml;
  wire [31:0] mt; wire [7:0] od;
  deepeye_trace_payload_candidate dut(
    .clk(clk),.rst(rst),.cancel(cancel),.cfg_valid(cv),.cfg_ready(cr),
    .cfg_count(cn),.cfg_e(ce),.cfg_session(session),.cfg_channel(ch),
    .cfg_first_index(idx),.cfg_first_tick(tick),.cfg_index_stride(istride),
    .cfg_tick_stride(tstride),.cfg_valid_sample(valid_sample),.cfg_saturated(sat),
    .cfg_held(held),.cfg_source_fault(sfault),.cfg_source_tick(source_tick),
    .s_valid(sv),.s_ready(sr),.s_data(sd),.s_last(sl),
    .meta_valid(mv),.meta_ready(mr),.meta_error(me),.meta_bytes(ml),.meta_tick(mt),
    .m_valid(ov),.m_ready(orr),.m_data(od),.m_last(ol));
  integer f,logfile,rc,cid=-1,cycle=0,cases=0,comparisons=0;
  integer expected_error,expected_len,words,bad_last,i,j,guard,seen,got,stalls,delay_input;
  reg hold_input=0;
  reg [31:0] expected_tick;
  reg [15:0] samples[0:255]; reg [7:0] bytes_expected[0:31];
  reg meta_stalled=0,byte_stalled=0;
  reg [39:0] prev_meta; reg [8:0] prev_byte;
  string vectors_path,trace_path;
  task automatic fail(input string why);
    begin $display("MAIN38_FAIL cycle=%0d case=%0d reason=%s",cycle,cid,why);$fatal(1,"MAIN38_NUMERIC_FAILURE");end
  endtask
  always @(posedge clk) begin
    cycle=cycle+1;
    if(logfile) $fdisplay(logfile,"T %0d %0d %b %b %b %b %b %b %b %04x %b %b %01x %02x %08x %b %b %b %02x",cycle,cid,rst,cancel,cv,cr,sv,sr,sl,sd,mv,mr,me,ml,mt,ov,orr,ol,od);
    if(rst||cancel) begin
      if(cr!==0||sr!==0||mv!==0||ov!==0)fail("abort_handshake_gate");
      meta_stalled=0;byte_stalled=0;
    end else begin
      if(meta_stalled && (mv!==1 || {me,ml,mt}!==prev_meta))fail("metadata_not_stable");
      if(byte_stalled && (ov!==1 || {ol,od}!==prev_byte))fail("byte_not_stable");
      meta_stalled=(mv===1&&mr===0);byte_stalled=(ov===1&&orr===0);
      prev_meta={me,ml,mt};prev_byte={ol,od};
      if(cv&&cr) $fdisplay(logfile,"C %0d %0d %02x %01x %08x %01x %08x %016x %04x %04x %b %b %b %b %016x",cycle,cid,cn,ce,session,ch,idx,tick,istride,tstride,valid_sample,sat,held,sfault,source_tick);
    end
  end
  initial begin
    if(!$value$plusargs("VECTORS=%s",vectors_path)||!$value$plusargs("TRACE=%s",trace_path))$fatal(1,"missing paths");
    f=$fopen(vectors_path,"r");logfile=$fopen(trace_path,"w");if(!f||!logfile)$fatal(1,"open failed");
    repeat(3)@(negedge clk);rst=0;
    while(!$feof(f)) begin
      rc=$fscanf(f,"%h",cid);if(rc!=1)break;
      rc=$fscanf(f,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h",cn,ce,session,ch,idx,tick,istride,tstride,valid_sample,sat,held,sfault,source_tick,bad_last,expected_error,expected_len,expected_tick,words);
      if(rc!=18 || words<0 || words>256 || expected_len>32)fail("vector_fields");
      for(i=0;i<words;i=i+1)begin rc=$fscanf(f,"%h",samples[i]);if(rc!=1)fail("sample_vector");end
      for(i=0;i<expected_len;i=i+1)begin rc=$fscanf(f,"%h",bytes_expected[i]);if(rc!=1)fail("byte_vector");end
      guard=0;
      while(cr!==1)begin @(negedge clk);guard=guard+1;if(guard>100)fail("idle_timeout");if(mv||ov)fail("orphan_output");end
      cv=1;@(posedge clk);if(cr!==1)fail("cfg_notaccepted");@(negedge clk);cv=0;
      j=0;seen=0;guard=0;sv=0;mr=0;orr=0;delay_input=0;hold_input=0;
      while(!seen)begin
        sv=hold_input || (j<words && valid_sample && (guard%7!=2));
        if(j<words)begin sd=samples[j];sl=(j==cn-1);if(j==bad_last)sl=!sl;end
        @(posedge clk);
        if(ov)fail("bytes_before_metadata");
        hold_input=sv&&!sr;
        if(sv&&sr)begin j=j+1;if(expected_error==1)fail("badcfg_accepted_sample");end
        if(mv)seen=1;
        @(negedge clk);guard=guard+1;if(guard>20000)fail("metadata_timeout");
      end
      sv=0;
      if(me!==expected_error[1:0] || ml!==expected_len[5:0] || mt!==expected_tick)fail("metadata_value");
      comparisons=comparisons+3;
      repeat(3)begin @(posedge clk);if(mv!==1||ov!==0)fail("metadata_hold");@(negedge clk);end
      mr=1;@(posedge clk);if(mv!==1)fail("metadata_drop");@(negedge clk);mr=0;
      got=0;guard=0;
      while(got<expected_len)begin
        orr=(guard%5==0||guard%5==4);
        @(posedge clk);
        if(ov&&orr)begin
          if(od!==bytes_expected[got] || ol!==(got==expected_len-1))fail("payload_value");
          comparisons=comparisons+2;got=got+1;
        end
        @(negedge clk);guard=guard+1;if(guard>1000)fail("payload_timeout");
      end
      orr=0;
      repeat(3)begin @(posedge clk);if(mv||ov)fail("extra_output");@(negedge clk);end
      $fdisplay(logfile,"E %0d %0d %0d %0d %0d",cycle,cid,expected_error,got,j);
      cases=cases+1;
    end
    $display("MAIN38_DONE cases=%0d comparisons=%0d cycles=%0d",cases,comparisons,cycle);
    $fclose(f);$fclose(logfile);$finish;
  end
endmodule
