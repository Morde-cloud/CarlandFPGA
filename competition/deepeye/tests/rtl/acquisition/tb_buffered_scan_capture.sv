`timescale 1ns/1ns
// The second chain reuses the pinned dependency RTL to check wrapper wiring.
// The runner separately checks this public trace with a transaction model.
module tb_buffered_scan_capture;
    logic clk = 0;
    always #5 clk = ~clk;
    logic rst = 1, stop = 0, rearm = 0, queue_cancel = 0;
    logic sample_strobe = 0, out_ready = 0;
    logic [31:0] rearm_tag = 0;
    logic [1:0] sample_channel = 0;
    logic [15:0] sample_data = 0;
    logic [63:0] sample_tick = 0;
    logic [7:0] sample_quality = 0;

    wire out_valid, capture_armed, capture_seq_exhausted;
    wire capture_order_error_event, capture_overrun_event, capture_seq_exhaust_event;
    wire [2:0] capture_partial_len, queue_level;
    wire [63:0] out_data;
    wire [255:0] out_ticks;
    wire [31:0] out_quality, out_first_seq, out_last_seq, out_tag;
    wire [31:0] capture_next_seq;
    wire [31:0] capture_stat_events, capture_stat_scans, capture_stat_retired;
    wire [31:0] capture_stat_discarded_samples, capture_stat_order_errors;
    wire [31:0] capture_stat_overruns;
    wire [31:0] queue_stat_accepted, queue_stat_retired, queue_stat_aborted;

    deepeye_buffered_scan_capture dut (
        .clk(clk), .rst(rst), .stop(stop), .rearm(rearm),
        .queue_cancel(queue_cancel), .sample_strobe(sample_strobe),
        .rearm_tag(rearm_tag), .sample_channel(sample_channel),
        .sample_data(sample_data), .sample_tick(sample_tick),
        .sample_quality(sample_quality), .out_ready(out_ready),
        .out_valid(out_valid), .out_data(out_data), .out_ticks(out_ticks),
        .out_quality(out_quality), .out_first_seq(out_first_seq),
        .out_last_seq(out_last_seq), .out_tag(out_tag),
        .capture_armed(capture_armed), .capture_partial_len(capture_partial_len),
        .capture_next_seq(capture_next_seq), .capture_seq_exhausted(capture_seq_exhausted),
        .capture_order_error_event(capture_order_error_event),
        .capture_overrun_event(capture_overrun_event),
        .capture_seq_exhaust_event(capture_seq_exhaust_event),
        .capture_stat_events(capture_stat_events), .capture_stat_scans(capture_stat_scans),
        .capture_stat_retired(capture_stat_retired),
        .capture_stat_discarded_samples(capture_stat_discarded_samples),
        .capture_stat_order_errors(capture_stat_order_errors),
        .capture_stat_overruns(capture_stat_overruns), .queue_level(queue_level),
        .queue_stat_accepted(queue_stat_accepted), .queue_stat_retired(queue_stat_retired),
        .queue_stat_aborted(queue_stat_aborted)
    );

    wire ref_capture_valid, ref_capture_ready;
    wire [63:0] ref_capture_data;
    wire [255:0] ref_capture_ticks;
    wire [31:0] ref_capture_quality, ref_capture_first_seq, ref_capture_last_seq, ref_capture_tag;
    wire ref_valid, ref_armed, ref_seq_exhausted;
    wire ref_order_error_event, ref_overrun_event, ref_seq_exhaust_event;
    wire [2:0] ref_partial_len, ref_level;
    wire [63:0] ref_data;
    wire [255:0] ref_ticks;
    wire [31:0] ref_quality, ref_first_seq, ref_last_seq, ref_tag;
    wire [31:0] ref_next_seq, ref_events, ref_scans, ref_capture_retired;
    wire [31:0] ref_discarded, ref_order_errors, ref_overruns;
    wire [31:0] ref_accepted, ref_retired, ref_aborted;

    deepeye_sample_scan_capture #(
        .SEQ_W(32), .TICK_W(64), .TAG_W(32), .STAT_W(32)
    ) reference_capture (
        .clk(clk), .rst(rst), .stop(stop), .rearm(rearm), .rearm_tag(rearm_tag),
        .sample_strobe(sample_strobe), .sample_channel(sample_channel),
        .sample_data(sample_data), .sample_tick(sample_tick), .sample_quality(sample_quality),
        .out_ready(ref_capture_ready), .out_valid(ref_capture_valid),
        .out_data(ref_capture_data), .out_ticks(ref_capture_ticks),
        .out_quality(ref_capture_quality), .out_first_seq(ref_capture_first_seq),
        .out_last_seq(ref_capture_last_seq), .out_tag(ref_capture_tag),
        .armed(ref_armed), .partial_len(ref_partial_len), .next_seq(ref_next_seq),
        .seq_exhausted(ref_seq_exhausted), .order_error_event(ref_order_error_event),
        .overrun_event(ref_overrun_event), .seq_exhaust_event(ref_seq_exhaust_event),
        .stat_events(ref_events), .stat_scans(ref_scans), .stat_retired(ref_capture_retired),
        .stat_discarded_samples(ref_discarded), .stat_order_errors(ref_order_errors),
        .stat_overruns(ref_overruns)
    );
    deepeye_raw_scan_queue #(
        .DEPTH(4), .SEQ_W(32), .TICK_W(64), .TAG_W(32), .STAT_W(32)
    ) reference_queue (
        .clk(clk), .rst(rst), .cancel(queue_cancel),
        .in_valid(ref_capture_valid), .in_ready(ref_capture_ready),
        .in_data(ref_capture_data), .in_ticks(ref_capture_ticks),
        .in_quality(ref_capture_quality), .in_first_seq(ref_capture_first_seq),
        .in_last_seq(ref_capture_last_seq), .in_tag(ref_capture_tag),
        .out_ready(out_ready), .out_valid(ref_valid), .out_data(ref_data),
        .out_ticks(ref_ticks), .out_quality(ref_quality), .out_first_seq(ref_first_seq),
        .out_last_seq(ref_last_seq), .out_tag(ref_tag), .level(ref_level),
        .stat_accepted(ref_accepted), .stat_retired(ref_retired), .stat_aborted(ref_aborted)
    );

    // 332 diagnostic/control bits followed by 448 record bits. Unknown invalid
    // queue memory is preserved in the trace, including across reset/cancel.
    wire [779:0] observed = {
        out_valid, capture_armed, capture_partial_len, capture_next_seq,
        capture_seq_exhausted, capture_order_error_event, capture_overrun_event,
        capture_seq_exhaust_event, capture_stat_events, capture_stat_scans,
        capture_stat_retired, capture_stat_discarded_samples, capture_stat_order_errors,
        capture_stat_overruns, queue_level, queue_stat_accepted, queue_stat_retired,
        queue_stat_aborted, out_data, out_ticks, out_quality, out_first_seq,
        out_last_seq, out_tag
    };
    wire [779:0] reference_observed = {
        ref_valid, ref_armed, ref_partial_len, ref_next_seq, ref_seq_exhausted,
        ref_order_error_event, ref_overrun_event, ref_seq_exhaust_event,
        ref_events, ref_scans, ref_capture_retired, ref_discarded, ref_order_errors,
        ref_overruns, ref_level, ref_accepted, ref_retired, ref_aborted,
        ref_data, ref_ticks, ref_quality, ref_first_seq, ref_last_seq, ref_tag
    };
    wire [127:0] input_observed = {
        rst, stop, rearm, queue_cancel, sample_strobe, rearm_tag, sample_channel,
        sample_data, sample_tick, sample_quality, out_ready
    };
    integer cycles, cycle, checks = 0, fd, count;
    reg [127:0] stimulus;
    string stimulus_path;

    task automatic trace_check(input string phase_name);
        $display("SCAN_TRACE cycle=%0d phase=%s time=%0d inputs=%032h dut=%0195h ref=%0195h",
                 cycle, phase_name, $time, input_observed, observed, reference_observed);
        checks = checks + 1;
        if (observed !== reference_observed) begin
            $fatal(1, "SCAN_MISMATCH cycle=%0d phase=%s", cycle, phase_name);
        end
    endtask

    initial begin
        if (!$value$plusargs("STIMULUS=%s", stimulus_path) ||
            !$value$plusargs("CYCLES=%d", cycles) || cycles <= 0)
            $fatal(1, "SCAN_BAD_ARGUMENTS");
        fd = $fopen(stimulus_path, "r");
        if (fd == 0) $fatal(1, "SCAN_BAD_STIMULUS");
        // Establish common-reset control state before cycle 0; RAM is not reset.
        @(posedge clk); #1;
        $display("SCAN_BEGIN cycles=%0d ports=24 bits=780", cycles);
        for (cycle = 0; cycle < cycles; cycle = cycle + 1) begin
            @(negedge clk);
            count = $fscanf(fd, "%h\n", stimulus);
            if (count != 1) $fatal(1, "SCAN_SHORT_STIMULUS cycle=%0d", cycle);
            {rst, stop, rearm, queue_cancel, sample_strobe, rearm_tag, sample_channel,
             sample_data, sample_tick, sample_quality, out_ready} = stimulus;
            #1; trace_check("pre");
            @(posedge clk); #1; trace_check("post");
        end
        count = $fscanf(fd, "%h\n", stimulus);
        if (count != -1) $fatal(1, "SCAN_EXTRA_STIMULUS");
        $fclose(fd);
        $display("SCAN_DONE cycles=%0d checks=%0d mismatch=0", cycles, checks);
        $display("SCAN_FINAL result=PASS");
        $finish;
    end
endmodule
