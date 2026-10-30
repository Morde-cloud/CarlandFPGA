`timescale 1ns/1ps
module tb_SYNTHETIC_codec74;
logic  fclk50_candidate;
logic  peripheral_aresetn_candidate;
logic  sample_strobe;
logic [1:0] sample_channel;
logic [15:0] sample_data;
logic [63:0] sample_tick;
logic [7:0] sample_quality;
logic  source_cancel;
logic  capture_stop;
logic  capture_rearm;
logic [31:0] capture_rearm_tag;
logic  queue_cancel;
logic  lane_cancel;
logic  assoc_valid;
logic  assoc_ready;
logic [31:0] assoc_tag;
logic [31:0] assoc_first_seq;
logic [31:0] assoc_last_seq;
logic [1:0] assoc_channel;
logic [31:0] assoc_session;
logic [31:0] assoc_first_index;
logic [7:0] assoc_count;
logic [3:0] assoc_e;
logic [15:0] assoc_index_stride;
logic [15:0] assoc_tick_stride_us;
logic [63:0] assoc_first_qpc_ns;
logic [63:0] assoc_first_tick_us;
logic [9:0] assoc_first_remainder_ns;
logic [63:0] assoc_tick_stride_ns;
logic [62:0] assoc_origin_qpc_ns;
logic [63:0] assoc_origin_tick_us;
logic [9:0] assoc_origin_remainder_ns;
logic  assoc_semantics_valid;
logic  assoc_valid_sample;
logic  assoc_saturated;
logic  assoc_held;
logic  assoc_source_fault;
logic [63:0] assoc_source_qpc_ns;
logic [63:0] assoc_source_tick_us;
logic [9:0] assoc_source_remainder_ns;
logic [7:0] assoc_epoch;
logic [15:0] assoc_seq;
logic  trace_lane_ready;
logic  trace_uart_tx;
logic  trace_transaction_aborted;
logic  trace_result_valid;
logic [2:0] trace_result_error;
logic [5:0] trace_result_bytes;
logic [3:0] trace_refusal_code;
logic  trace_wire_faulted;
logic  trace_transport_profile_unset;
logic  data_path_quiescent;
logic  capture_fault_event;
logic  capture_sequence_exhausted;
logic [31:0] capture_discarded_samples;
logic  fixture_profile_enabled;
logic  fixture_transport_enabled;
logic  fixture_result_ready;
deepeye_SYNTHETIC_codec74_fixture dut(
.fclk50_candidate(fclk50_candidate),
.peripheral_aresetn_candidate(peripheral_aresetn_candidate),
.sample_strobe(sample_strobe),
.sample_channel(sample_channel),
.sample_data(sample_data),
.sample_tick(sample_tick),
.sample_quality(sample_quality),
.source_cancel(source_cancel),
.capture_stop(capture_stop),
.capture_rearm(capture_rearm),
.capture_rearm_tag(capture_rearm_tag),
.queue_cancel(queue_cancel),
.lane_cancel(lane_cancel),
.assoc_valid(assoc_valid),
.assoc_ready(assoc_ready),
.assoc_tag(assoc_tag),
.assoc_first_seq(assoc_first_seq),
.assoc_last_seq(assoc_last_seq),
.assoc_channel(assoc_channel),
.assoc_session(assoc_session),
.assoc_first_index(assoc_first_index),
.assoc_count(assoc_count),
.assoc_e(assoc_e),
.assoc_index_stride(assoc_index_stride),
.assoc_tick_stride_us(assoc_tick_stride_us),
.assoc_first_qpc_ns(assoc_first_qpc_ns),
.assoc_first_tick_us(assoc_first_tick_us),
.assoc_first_remainder_ns(assoc_first_remainder_ns),
.assoc_tick_stride_ns(assoc_tick_stride_ns),
.assoc_origin_qpc_ns(assoc_origin_qpc_ns),
.assoc_origin_tick_us(assoc_origin_tick_us),
.assoc_origin_remainder_ns(assoc_origin_remainder_ns),
.assoc_semantics_valid(assoc_semantics_valid),
.assoc_valid_sample(assoc_valid_sample),
.assoc_saturated(assoc_saturated),
.assoc_held(assoc_held),
.assoc_source_fault(assoc_source_fault),
.assoc_source_qpc_ns(assoc_source_qpc_ns),
.assoc_source_tick_us(assoc_source_tick_us),
.assoc_source_remainder_ns(assoc_source_remainder_ns),
.assoc_epoch(assoc_epoch),
.assoc_seq(assoc_seq),
.trace_lane_ready(trace_lane_ready),
.trace_uart_tx(trace_uart_tx),
.trace_transaction_aborted(trace_transaction_aborted),
.trace_result_valid(trace_result_valid),
.trace_result_error(trace_result_error),
.trace_result_bytes(trace_result_bytes),
.trace_refusal_code(trace_refusal_code),
.trace_wire_faulted(trace_wire_faulted),
.trace_transport_profile_unset(trace_transport_profile_unset),
.data_path_quiescent(data_path_quiescent),
.capture_fault_event(capture_fault_event),
.capture_sequence_exhausted(capture_sequence_exhausted),
.capture_discarded_samples(capture_discarded_samples),
.fixture_profile_enabled(fixture_profile_enabled),
.fixture_transport_enabled(fixture_transport_enabled),
.fixture_result_ready(fixture_result_ready)
);
// SYNTHETIC fixture clock50MHz / baud5M, no physical UART assertion.
always #10 fclk50_candidate=~fclk50_candidate;
localparam logic [62:0] ORIGIN=63'd9007199254740993;
integer cycles=0, uart_n=0, serial_n=0, aborts=0, mode=0, k, i;
integer completed=0;
integer serializer_stalls=0;
logic serializer_held=0;
logic [7:0] serializer_held_data;
integer uart_fd, serial_fd, events_fd;
string outdir;
logic [7:0] observed;
logic [15:0] raw[0:3];
logic [7:0] qual[0:3];
logic [63:0] qpc[0:3];
always @(posedge fclk50_candidate) begin
    cycles=cycles+1;
    if(cycles>100000) $fatal(1,"B74 bounded cycle deadline lane=%0d wrapper=%0d payload=%0d encoder=%0d pending=%0d meta=%0d",dut.lane_channel,dut.trace_i.state_q,dut.trace_i.payload_stage.payload_unit.state,dut.trace_i.payload_stage.payload_unit.inner_encoder.state,dut.sample_pending_q,dut.trace_i.payload_meta_valid);
    if(dut.trace_i.serializer_out_valid && dut.trace_i.serializer_out_ready) begin
        $fdisplay(serial_fd,"%02x",dut.trace_i.serializer_out_data); serial_n=serial_n+1;
    end
    if(trace_transaction_aborted) aborts=aborts+1;
    if(!source_cancel && !dut.trace_rst) begin
        if(serializer_held && dut.trace_i.serializer_out_valid &&
           dut.trace_i.serializer_out_data!==serializer_held_data) $fatal(1,"serializer changed byte under backpressure");
        serializer_held=dut.trace_i.serializer_out_valid && !dut.trace_i.serializer_out_ready;
        serializer_held_data=dut.trace_i.serializer_out_data;
        if(serializer_held) serializer_stalls=serializer_stalls+1;
    end else serializer_held=0;
end
// Observe the external UART line independently of serializer data. Integer
// ratio10 permits midpoint sampling at 1.5bit then every10clocks (8N1).
initial forever begin
    @(negedge trace_uart_tx);
    repeat(15) @(posedge fclk50_candidate);
    #1;
    for(integer bitno=0;bitno<8;bitno=bitno+1) begin
        observed[bitno]=trace_uart_tx;
        repeat(10) @(posedge fclk50_candidate);
        #1;
    end
    if(!source_cancel) begin
        if(trace_uart_tx !== 1'b1) $fatal(1,"UART missing stop bit");
        $fdisplay(uart_fd,"%02x",observed); uart_n=uart_n+1;
    end
end
task automatic clocks(input integer n);
    repeat(n) @(negedge fclk50_candidate);
endtask
task automatic rearm;
    capture_rearm=1; clocks(1); capture_rearm=0; clocks(2);
endtask
task automatic scan;
    for(integer ch=0;ch<4;ch=ch+1) begin
        sample_channel=ch; sample_data=raw[ch]; sample_tick=qpc[ch]; sample_quality=qual[ch];
        sample_strobe=1; clocks(1); sample_strobe=0; clocks(1);
    end
    clocks(5);
endtask
task automatic association(input integer ch);
    assoc_tag=17; assoc_first_seq=0; assoc_last_seq=3; assoc_channel=ch;
    assoc_session=32'h12345678; assoc_first_index=1000+ch;
    assoc_count=1; assoc_e=0; assoc_index_stride=0; assoc_tick_stride_us=0;
    assoc_tick_stride_ns=0; assoc_first_qpc_ns=qpc[ch];
    assoc_first_tick_us=(qpc[ch]-ORIGIN)/1000;
    assoc_first_remainder_ns=(qpc[ch]-ORIGIN)%1000;
    assoc_origin_qpc_ns=ORIGIN; assoc_origin_tick_us=0; assoc_origin_remainder_ns=0;
    assoc_semantics_valid=1; assoc_valid_sample=1;
    assoc_saturated=(ch==1); assoc_held=(ch==2); assoc_source_fault=(ch==3);
    assoc_source_qpc_ns=qpc[ch]-((ch==2)?64'd2000456:0);
    assoc_source_tick_us=(assoc_source_qpc_ns-ORIGIN)/1000;
    assoc_source_remainder_ns=(assoc_source_qpc_ns-ORIGIN)%1000;
    assoc_epoch=7; assoc_seq=200+ch; assoc_valid=1;
endtask
task automatic accept_assoc;
    // Sample ready on the SAME active edge that consumes valid. A negedge
    // polling loop can miss the ready pulse after lane/wrapper advance.
    do @(posedge fclk50_candidate); while(!assoc_ready);
    @(negedge fclk50_candidate); assoc_valid=0;
endtask
task automatic result_ok(input integer expected_error);
    while(!trace_result_valid) clocks(1);
    if(trace_result_error!==expected_error) $fatal(1,"B74 unexpected result error %0d",trace_result_error);
    $fdisplay(events_fd,"RESULT %0d %0d %0d",assoc_channel,trace_result_error,trace_result_bytes);
    clocks(1);
endtask
initial begin
    fclk50_candidate=0;
peripheral_aresetn_candidate=0;
sample_strobe=0;
sample_channel=0;
sample_data=0;
sample_tick=0;
sample_quality=0;
source_cancel=0;
capture_stop=0;
capture_rearm=0;
capture_rearm_tag=0;
queue_cancel=0;
lane_cancel=0;
assoc_valid=0;
assoc_tag=0;
assoc_first_seq=0;
assoc_last_seq=0;
assoc_channel=0;
assoc_session=0;
assoc_first_index=0;
assoc_count=0;
assoc_e=0;
assoc_index_stride=0;
assoc_tick_stride_us=0;
assoc_first_qpc_ns=0;
assoc_first_tick_us=0;
assoc_first_remainder_ns=0;
assoc_tick_stride_ns=0;
assoc_origin_qpc_ns=0;
assoc_origin_tick_us=0;
assoc_origin_remainder_ns=0;
assoc_semantics_valid=0;
assoc_valid_sample=0;
assoc_saturated=0;
assoc_held=0;
assoc_source_fault=0;
assoc_source_qpc_ns=0;
assoc_source_tick_us=0;
assoc_source_remainder_ns=0;
assoc_epoch=0;
assoc_seq=0;
fixture_profile_enabled=0;
fixture_transport_enabled=0;
fixture_result_ready=0;
    if(!$value$plusargs("OUT=%s",outdir)) $fatal(1,"OUT required");
    if(!$value$plusargs("MODE=%d",mode)) mode=0;
    uart_fd=$fopen({outdir,"/uart.hex"},"w");
    serial_fd=$fopen({outdir,"/serializer.hex"},"w");
    events_fd=$fopen({outdir,"/events.txt"},"w");
    if(!uart_fd || !serial_fd || !events_fd) $fatal(1,"file open");
    raw[0]=16'd32769; raw[1]=16'd65280; raw[2]=16'd4096; raw[3]=16'd65535;
    qual[0]=8'h80; qual[1]=8'hfe; qual[2]=8'h55; qual[3]=8'ha3;
    for(i=0;i<4;i=i+1) qpc[i]=ORIGIN+64'd10000123+i*64'd10000007;
    fixture_profile_enabled=1; fixture_transport_enabled=1; fixture_result_ready=1;
    capture_rearm_tag=17;
    clocks(5); peripheral_aresetn_candidate=1; clocks(5); rearm(); scan();
    if(mode==0) begin
        for(k=0;k<4;k=k+1) begin
            association(k);
            if(k==0) begin
                // Wrong raw association cannot consume the held lane.
                assoc_tag=18; clocks(10);
                if(assoc_ready || trace_lane_ready || uart_n!=0) $fatal(1,"wrong source identity consumed");
                if(dut.lane_data!==raw[0] || dut.lane_quality!==qual[0]) $fatal(1,"backpressure changed lane");
                $fdisplay(events_fd,"SOURCE_IDENTITY_REFUSED"); assoc_tag=17;
            end
            accept_assoc(); fixture_result_ready=0;
            while(!trace_result_valid) clocks(1);
            if(trace_result_error!=0) $fatal(1,"normal frame refused");
            i=trace_result_bytes; clocks(10);
            if(!trace_result_valid || trace_result_bytes!=i || assoc_ready) $fatal(1,"result backpressure lost");
            $fdisplay(events_fd,"RESULT_BACKPRESSURE %0d",k);
            fixture_result_ready=1; result_ok(0); clocks(3);
        end
        if(uart_n!=serial_n || uart_n!=150) $fatal(1,"wire count %0d %0d",uart_n,serial_n);
    end else if(mode==1) begin
        association(0); accept_assoc();
        while(uart_n<5) clocks(1);
        clocks(20); // Sixth symbol is now in flight; cancel cannot recall it.
        source_cancel=1; clocks(120);
        if(!data_path_quiescent || aborts!=1 || dut.cap_armed) $fatal(1,"cancel not quiescent/once");
        if(serializer_stalls==0) $fatal(1,"no actual UART backpressure exercised");
        $fdisplay(events_fd,"CANCEL_PARTIAL %0d %0d %0d STALLS %0d",uart_n,serial_n,aborts,serializer_stalls);
        source_cancel=0; clocks(120);
        if(trace_result_valid || assoc_ready || dut.cap_armed) $fatal(1,"cancel automatically resumed");
    end else if(mode==2) begin
        association(0); assoc_first_tick_us=64'h100000000;
        accept_assoc(); result_ok(4); clocks(10);
        if(trace_refusal_code!=4 || uart_n!=0 || serial_n!=0) $fatal(1,"relative uint32 overflow accepted");
        $fdisplay(events_fd,"OVERFLOW_REFUSED");
    end else if(mode==3) begin
        association(0); assoc_source_qpc_ns=64'h8000000000000000;
        accept_assoc(); result_ok(4); clocks(10);
        if(trace_refusal_code!=4 || uart_n!=0) $fatal(1,"uint63 source overflow accepted");
        $fdisplay(events_fd,"QPC_OVERFLOW_REFUSED");
    end else if(mode==4) $fatal(1,"B74_INTENTIONAL_RUNNER_NEGATIVE");
    else if(mode==5) begin
        if(uart_n!=0 || serial_n!=0) $fatal(1,"dedicated runner success emitted unexpected data");
        $fdisplay(events_fd,"RUNNER_SUCCESS_NO_CODEC_REPLAY");
    end
    else $fatal(1,"unknown fixture mode");
    $fdisplay(events_fd,"DONE %0d %0d %0d",cycles,uart_n,serial_n);
    $fclose(uart_fd); $fclose(serial_fd); $fclose(events_fd);
    $display("B74_SYNTHETIC_DONE mode=%0d cycles=%0d uart=%0d serial=%0d",mode,cycles,uart_n,serial_n);
    completed=1;
    $finish;
end

endmodule
