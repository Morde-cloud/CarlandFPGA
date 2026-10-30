`timescale 1ns/1ps
module tb_RETIRED_RAW4_100;
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

always #10 fclk50_candidate=~fclk50_candidate;
localparam logic [62:0] ORIGIN = 63'd27001348289300;
localparam logic [63:0] ORIGIN64 = {1'b0, ORIGIN};
localparam [31:0] TAG = 32'h00000097;
localparam [31:0] SESSION = 32'h97345678;
localparam integer MAX_CYCLES = 600000;

integer cycles=0, uart_n=0, serial_n=0, frame_n=0, aborts=0, mode=0;
integer r, ch;
integer uart_base, serial_base, uart_at_cancel, serial_at_cancel;
integer serializer_stalls=0;
logic serializer_held=0;
logic [7:0] serializer_held_data;
integer uart_fd, serial_fd, events_fd;
string outdir, memfile;
logic [15:0] input_words [0:139];
logic [7:0] observed;
integer completed=0;

function automatic integer em_tick(input integer r);
    em_tick = input_words[r*7+4];
endfunction
function automatic logic held(input integer r);
    held = em_tick(r) < r * 10;
endfunction
function automatic logic c3_valid(input integer r);
    c3_valid = input_words[r*7+5][3];
endfunction
function automatic logic [15:0] em_count(input integer ch, input integer r);
    em_count = input_words[r*7+ch];
endfunction
function automatic logic [7:0] lane_quality(input integer ch, input integer r);
    if (ch < 3) lane_quality = held(r) ? 8'h05 : 8'h01;
    else lane_quality = c3_valid(r) ? 8'h01 : 8'h00;
endfunction
function automatic logic [12:0] global_quality(input integer r);
    global_quality = input_words[r*7+5];
endfunction

always @(posedge fclk50_candidate) begin
    cycles = cycles + 1;
    if (cycles > MAX_CYCLES) $fatal(1, "B100 bounded cycle deadline mode=%0d state=%0d pending=%0d", mode, dut.trace_i.state_q, dut.sample_pending_q);
    if (dut.trace_i.serializer_out_valid && dut.trace_i.serializer_out_ready) begin
        $fdisplay(serial_fd, "%02x", dut.trace_i.serializer_out_data);
        serial_n = serial_n + 1;
        if (dut.trace_i.serializer_out_last) begin
            frame_n = frame_n + 1;
            $fdisplay(events_fd, "FRAME %0d %0d", frame_n, serial_n);
        end
    end
    if (trace_transaction_aborted) aborts = aborts + 1;
    if (!source_cancel && !dut.trace_rst) begin
        if (serializer_held && dut.trace_i.serializer_out_valid &&
            dut.trace_i.serializer_out_data !== serializer_held_data)
            $fatal(1, "B100 serializer changed byte under backpressure");
        serializer_held = dut.trace_i.serializer_out_valid && !dut.trace_i.serializer_out_ready;
        serializer_held_data = dut.trace_i.serializer_out_data;
        if (serializer_held) serializer_stalls = serializer_stalls + 1;
    end else begin
        serializer_held = 0;
    end
end

initial forever begin
    @(negedge trace_uart_tx);
    repeat (15) @(posedge fclk50_candidate);
    #1;
    for (integer bitno = 0; bitno < 8; bitno = bitno + 1) begin
        observed[bitno] = trace_uart_tx;
        repeat (10) @(posedge fclk50_candidate);
        #1;
    end
    if (!source_cancel) begin
        if (trace_uart_tx !== 1'b1) $fatal(1, "B100 UART missing stop bit");
        $fdisplay(uart_fd, "%02x", observed);
        uart_n = uart_n + 1;
    end
end

task automatic clocks(input integer n);
    repeat (n) @(negedge fclk50_candidate);
endtask
task automatic rearm;
    capture_rearm = 1; clocks(1); capture_rearm = 0; clocks(2);
endtask
task automatic scan_record(input integer r);
    integer ch;
    for (ch = 0; ch < 4; ch = ch + 1) begin
        sample_channel = ch;
        sample_data = (ch < 3) ? em_count(ch, r) : 16'd0;
        sample_tick = ORIGIN64 + r * 64'd10000000;
        sample_quality = lane_quality(ch, r);
        sample_strobe = 1; clocks(1); sample_strobe = 0; clocks(1);
    end
    clocks(10);
endtask
task automatic association(input integer r, input integer ch);
    assoc_tag = TAG;
    assoc_first_seq = r * 4;
    assoc_last_seq = r * 4 + 3;
    assoc_channel = ch;
    assoc_session = SESSION;
    assoc_first_index = r;
    assoc_count = 1;
    assoc_e = 0;
    assoc_index_stride = 0;
    assoc_tick_stride_us = 0;
    assoc_tick_stride_ns = 0;
    assoc_first_qpc_ns = ORIGIN64 + r * 64'd10000000;
    assoc_first_tick_us = r * 64'd10000;
    assoc_first_remainder_ns = 0;
    assoc_origin_qpc_ns = ORIGIN;
    assoc_origin_tick_us = 0;
    assoc_origin_remainder_ns = 0;
    assoc_semantics_valid = 1;
    assoc_valid_sample = (ch < 3) || c3_valid(r);
    assoc_saturated = 0;
    assoc_held = (ch < 3) ? held(r) : 1'b0;
    assoc_source_fault = 1'b0;
    if (assoc_valid_sample) begin
        if (ch < 3 && held(r)) begin
            assoc_source_qpc_ns = ORIGIN64 + em_tick(r) * 64'd1000000;
            assoc_source_tick_us = em_tick(r) * 64'd1000;
        end else begin
            assoc_source_qpc_ns = assoc_first_qpc_ns;
            assoc_source_tick_us = assoc_first_tick_us;
        end
        assoc_source_remainder_ns = 0;
    end else begin
        assoc_source_qpc_ns = 0;
        assoc_source_tick_us = 0;
        assoc_source_remainder_ns = 0;
    end
    assoc_epoch = 9;
    assoc_seq = r * 4 + ch;
    assoc_valid = 1;
endtask
task automatic accept_assoc;
    do @(posedge fclk50_candidate); while (!assoc_ready);
    @(negedge fclk50_candidate);
    assoc_valid = 0;
endtask
task automatic wait_result;
    while (!trace_result_valid) clocks(1);
endtask
task automatic result_ok(input integer expected_error);
    wait_result;
    if (trace_result_error !== expected_error)
        $fatal(1, "B100 unexpected result error %0d", trace_result_error);
    $fdisplay(events_fd, "RESULT %0d %0d %0d", assoc_channel, trace_result_error, trace_result_bytes);
    clocks(1);
endtask
task automatic normal_frame(input integer r, input integer ch);
    integer held_bytes;
    association(r, ch);
    if (r == 1 && ch == 0) begin
        uart_base = uart_n;
        assoc_tag = 18; clocks(10);
        if (assoc_ready || trace_lane_ready || uart_n != uart_base)
            $fatal(1, "B100 wrong identity consumed lane");
        if (dut.lane_data !== em_count(ch,r) || dut.lane_quality !== 8'h05)
            $fatal(1, "B100 wrong identity changed lane");
        $fdisplay(events_fd, "WRONG_IDENTITY_REFUSED %0d %0d", r, ch);
        assoc_tag = TAG;
    end
    fixture_result_ready = 0;
    accept_assoc();
    wait_result();
    if (trace_result_error !== 0) $fatal(1, "B100 normal frame refused");
    if (r == 0 && ch == 3) begin
        held_bytes = trace_result_bytes;
        clocks(10);
        if (!trace_result_valid || trace_result_bytes != held_bytes || assoc_ready)
            $fatal(1, "B100 result backpressure lost");
        $fdisplay(events_fd, "RESULT_BACKPRESSURE %0d %0d %0d", r, ch, held_bytes);
    end
    fixture_result_ready = 1;
    result_ok(0);
    clocks(5);
endtask

initial begin
    fclk50_candidate = 0;
    peripheral_aresetn_candidate = 0;
    sample_strobe = 0; sample_channel = 0; sample_data = 0; sample_tick = 0; sample_quality = 0;
    source_cancel = 0; capture_stop = 0; capture_rearm = 0; capture_rearm_tag = 0;
    queue_cancel = 0; lane_cancel = 0;
    assoc_valid = 0; assoc_tag = 0; assoc_first_seq = 0; assoc_last_seq = 0;
    assoc_channel = 0; assoc_session = 0; assoc_first_index = 0; assoc_count = 0;
    assoc_e = 0; assoc_index_stride = 0; assoc_tick_stride_us = 0;
    assoc_first_qpc_ns = 0; assoc_first_tick_us = 0; assoc_first_remainder_ns = 0;
    assoc_tick_stride_ns = 0; assoc_origin_qpc_ns = 0; assoc_origin_tick_us = 0;
    assoc_origin_remainder_ns = 0; assoc_semantics_valid = 0;
    assoc_valid_sample = 0; assoc_saturated = 0; assoc_held = 0; assoc_source_fault = 0;
    assoc_source_qpc_ns = 0; assoc_source_tick_us = 0; assoc_source_remainder_ns = 0;
    assoc_epoch = 0; assoc_seq = 0;
    fixture_profile_enabled = 0; fixture_transport_enabled = 0; fixture_result_ready = 0;
    if (!$value$plusargs("OUT=%s", outdir)) $fatal(1, "OUT required");
    if (!$value$plusargs("MEM=%s", memfile)) $fatal(1, "MEM required");
    $readmemh(memfile, input_words);
    uart_fd = $fopen({outdir, "/uart.hex"}, "w");
    serial_fd = $fopen({outdir, "/serializer.hex"}, "w");
    events_fd = $fopen({outdir, "/events.txt"}, "w");
    if (!uart_fd || !serial_fd || !events_fd) $fatal(1, "B100 file open");
    fixture_profile_enabled = 1; fixture_transport_enabled = 1; fixture_result_ready = 1;
    capture_rearm_tag = TAG;
    clocks(5); peripheral_aresetn_candidate = 1; clocks(5); rearm();

    if (mode == 0) begin
        for (r = 0; r < 20; r = r + 1) begin
            scan_record(r);
            for (ch = 0; ch < 4; ch = ch + 1) begin
                normal_frame(r, ch);
                if (ch == 3 && !c3_valid(r))
                    $fdisplay(events_fd, "NULL_FRAME %0d %0d", r, ch);
                else if (ch == 3 && c3_valid(r))
                    $fdisplay(events_fd, "ZERO_FRAME %0d %0d", r, ch);
                else if (held(r))
                    $fdisplay(events_fd, "HELD_FRAME %0d %0d", r, ch);
            end
        end
        clocks(100);
        if (frame_n != 80) $fatal(1, "B100 mode0 frame count %0d", frame_n);
        if (uart_n != serial_n) $fatal(1, "B100 UART/serializer mismatch %0d %0d", uart_n, serial_n);
    end

    $fdisplay(events_fd, "DONE %0d %0d %0d %0d", cycles, uart_n, serial_n, frame_n);
    $fclose(uart_fd); $fclose(serial_fd); $fclose(events_fd);
    $display("B100_SYNTHETIC_DONE mode=%0d cycles=%0d uart=%0d serial=%0d frames=%0d", mode, cycles, uart_n, serial_n, frame_n);
    completed = 1;
    $finish;
end
endmodule
