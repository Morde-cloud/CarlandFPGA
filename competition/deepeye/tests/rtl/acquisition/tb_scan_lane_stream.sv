`timescale 1ns/1ps
// Fixture transaction-list scoreboard; no force or hierarchical state access.
module tb_scan_lane_stream;
    reg clk=0;always #5 clk=~clk;
    reg rst=1,cancel=0,standalone_valid=0,out_ready=0;
    reg [447:0] standalone_record=0;
    reg upstream_rst=1,stop=0,rearm=0,queue_cancel=0,sample_strobe=0;
    reg [31:0] rearm_tag=0;
    reg [1:0] sample_channel=0;
    reg [15:0] sample_data=0;
    reg [63:0] sample_tick=0;
    reg [7:0] sample_quality=0;
    wire capture_valid,capture_armed,order_error,overrun;
    wire [63:0] capture_data;
    wire [255:0] capture_ticks;
    wire [31:0] capture_quality,capture_first,capture_last,capture_tag;
    wire [447:0] capture_record={capture_tag,capture_last,capture_first,capture_quality,capture_ticks,capture_data};
    integer mode=0;
    wire in_valid=(mode==0)?standalone_valid:capture_valid;
    wire [447:0] record_in=(mode==0)?standalone_record:capture_record;
    wire in_ready,out_valid,out_last;
    wire [1:0] out_channel;
    wire [15:0] out_data;
    wire [63:0] out_tick;
    wire [7:0] out_quality;
    wire [31:0] out_first_seq,out_last_seq,out_tag;
    wire [186:0] output_word={out_channel,out_data,out_tick,out_quality,out_first_seq,out_last_seq,out_tag,out_last};
    wire [126:0] producer={upstream_rst,stop,rearm,queue_cancel,sample_strobe,rearm_tag,sample_channel,sample_data,sample_tick,sample_quality};
    deepeye_buffered_scan_capture capture39 (
        .clk(clk),.rst(upstream_rst),.stop(stop),.rearm(rearm),.queue_cancel(queue_cancel),
        .sample_strobe(sample_strobe),.rearm_tag(rearm_tag),.sample_channel(sample_channel),
        .sample_data(sample_data),.sample_tick(sample_tick),.sample_quality(sample_quality),
        .out_ready((mode==1)&&in_ready),.out_valid(capture_valid),.out_data(capture_data),
        .out_ticks(capture_ticks),.out_quality(capture_quality),.out_first_seq(capture_first),
        .out_last_seq(capture_last),.out_tag(capture_tag),.capture_armed(capture_armed),
        .capture_order_error_event(order_error),.capture_overrun_event(overrun),
        .capture_partial_len(),.capture_next_seq(),.capture_seq_exhausted(),
        .capture_seq_exhaust_event(),.capture_stat_events(),.capture_stat_scans(),
        .capture_stat_retired(),.capture_stat_discarded_samples(),.capture_stat_order_errors(),
        .capture_stat_overruns(),.queue_level(),.queue_stat_accepted(),.queue_stat_retired(),.queue_stat_aborted()
    );
    deepeye_scan_lane_stream dut (
        .clk(clk),.rst(rst),.cancel(cancel),.in_valid(in_valid),.in_ready(in_ready),
        .in_data(record_in[63:0]),.in_ticks(record_in[319:64]),.in_quality(record_in[351:320]),
        .in_first_seq(record_in[383:352]),.in_last_seq(record_in[415:384]),.in_tag(record_in[447:416]),
        .out_valid(out_valid),.out_ready(out_ready),.out_channel(out_channel),.out_data(out_data),
        .out_tick(out_tick),.out_quality(out_quality),.out_first_seq(out_first_seq),
        .out_last_seq(out_last_seq),.out_tag(out_tag),.out_last(out_last)
    );
    reg [447:0] records[0:2047];
    reg [186:0] lanes[0:8191];
    integer expected_stream[0:2047];
    integer pending[0:131071];
    integer head=0,tail=0,stream_index=0,record_count,stream_count,cycles;
    integer fd,trace_fd,rc,i,j,record_id,scenario,cycle=0;
    reg [3:0] controls;
    reg [126:0] producer_bits;
    integer record_hs=0,lane_hs=0,reloads=0,input_stalls=0,output_stalls=0;
    integer resets=0,cancels=0,discarded=0,lane_count[0:3];
    string input_path,trace_path;
    task automatic fail(input string why);
        $display("SL_FAIL mode=%0d cycle=%0d %s",mode,cycle,why);$fatal(1,"SL_FAIL");
    endtask
    task automatic check_ports;
        reg wanted_ready;
        begin
            if((^{in_ready,out_valid,out_last})===1'bx)fail("unknown handshake");
            if(rst||cancel)begin
                if({in_ready,out_valid,out_last}!==3'b000)fail("abort gating");
            end else begin
                if(out_valid!==(tail>head))fail("output validity/record slot");
                wanted_ready=(tail==head)||(out_valid&&out_ready&&lanes[pending[head]][0]);
                if(in_ready!==wanted_ready)fail("ready/final-lane replacement rule");
                if(out_valid&&output_word!==lanes[pending[head]])fail("lane tuple/opaque metadata");
                if(!out_valid&&out_last)fail("last outside valid");
            end
            if(mode==1&&!upstream_rst)begin
                if(order_error!==1'b0||overrun!==1'b0)fail("unexpected upstream event in bounded well-formed suite");
            end
        end
    endtask
    task automatic trace(input string phase);
        $fdisplay(trace_fd,"%0d %s %0d %b%b%b%b %b %b %0112h %0112h %047h %047h %032h %0d %b",
            cycle,phase,scenario,rst,cancel,in_valid,out_ready,in_ready,out_valid,
            in_valid?record_in:448'd0,record_in,out_valid?output_word:187'd0,output_word,producer,record_id,out_last);
    endtask
    integer rid;
    initial begin
        for(i=0;i<4;i=i+1)lane_count[i]=0;
        if(!$value$plusargs("MODE=%d",mode)||!$value$plusargs("INPUT=%s",input_path)||!$value$plusargs("TRACE=%s",trace_path))$fatal(1,"arguments");
        fd=$fopen(input_path,"r");trace_fd=$fopen(trace_path,"w");if(!fd||!trace_fd)$fatal(1,"files");
        rc=$fscanf(fd,"%d %d %d",record_count,stream_count,cycles);
        if(rc!=3||record_count>2048||stream_count>2048||cycles<1)fail("fixture limits");
        for(i=0;i<record_count;i=i+1)begin
            rc=$fscanf(fd,"%h %h %h %h %h",records[i],lanes[4*i],lanes[4*i+1],lanes[4*i+2],lanes[4*i+3]);
            if(rc!=5)fail("record/independent lane list fixture");
        end
        for(i=0;i<stream_count;i=i+1)begin rc=$fscanf(fd,"%d",expected_stream[i]);if(rc!=1)fail("integration stream fixture");end
        for(i=0;i<cycles;i=i+1)begin
            rc=$fscanf(fd,"%d %h %d %h",scenario,controls,record_id,producer_bits);if(rc!=4||record_id<0||record_id>=record_count)fail("cycle fixture");
            if(i>0)@(negedge clk);
            {rst,cancel,standalone_valid,out_ready}=controls;standalone_record=records[record_id];
            {upstream_rst,stop,rearm,queue_cancel,sample_strobe,rearm_tag,sample_channel,sample_data,sample_tick,sample_quality}=producer_bits;
            @(posedge clk);cycle=i+1;
            check_ports();trace("PRE");
            if(rst)resets=resets+1;if(cancel)cancels=cancels+1;
            if(in_valid&&!in_ready)input_stalls=input_stalls+1;
            if(out_valid&&!out_ready)output_stalls=output_stalls+1;
            if(rst||cancel)begin discarded=discarded+tail-head;head=tail;end
            else begin
                if(out_valid&&out_ready)begin lane_hs=lane_hs+1;lane_count[out_channel]=lane_count[out_channel]+1;head=head+1;end
                if(in_valid&&in_ready)begin
                    if(mode==0)rid=record_id;
                    else begin
                        if(stream_index>=stream_count)fail("extra upstream record");
                        rid=expected_stream[stream_index];stream_index=stream_index+1;
                    end
                    if(record_in!==records[rid])fail("accepted record differs from independent transaction list");
                    if(out_valid&&out_ready&&out_last)reloads=reloads+1;
                    for(j=0;j<4;j=j+1)begin pending[tail]=4*rid+j;tail=tail+1;end
                    record_hs=record_hs+1;
                end
            end
            #1;check_ports();trace("POST");
        end
        if(tail!=head||4*record_hs!=lane_hs+discarded)fail("terminal conservation/drain");
        if(mode==1&&stream_index!=stream_count)fail("missing integration records");
        for(i=0;i<4;i=i+1)if(lane_count[i]==0)fail("lane coverage");
        if(input_stalls==0||output_stalls==0||reloads==0||resets==0)fail("boundary coverage");
        if(mode==0&&cancels==0)fail("cancel coverage");
        $fclose(fd);@(negedge clk);
        $display("SL_SUMMARY mode=%0d cycles=%0d checks=%0d records=%0d lanes=%0d reloads=%0d in_stalls=%0d out_stalls=%0d reset=%0d cancel=%0d discarded=%0d lane0=%0d lane1=%0d lane2=%0d lane3=%0d",
            mode,cycle,cycle*2,record_hs,lane_hs,reloads,input_stalls,output_stalls,resets,cancels,discarded,
            lane_count[0],lane_count[1],lane_count[2],lane_count[3]);
        $fclose(trace_fd);$display("SL_DONE mode=%0d PASS",mode);$finish;
    end
    initial begin #100000000;$fatal(1,"SL_FAIL timeout");end
endmodule
