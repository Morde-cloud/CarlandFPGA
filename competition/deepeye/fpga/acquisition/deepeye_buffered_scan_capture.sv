// Fixed, same-clock composition. Control ownership stays with each stage.
module deepeye_buffered_scan_capture (
    input  logic         clk,
    input  logic         rst,
    input  logic         stop,
    input  logic         rearm,
    input  logic         queue_cancel,
    input  logic         sample_strobe,
    input  logic [31:0]  rearm_tag,
    input  logic [1:0]   sample_channel,
    input  logic [15:0]  sample_data,
    input  logic [63:0]  sample_tick,
    input  logic [7:0]   sample_quality,
    input  logic         out_ready,
    output logic         out_valid,
    output logic [63:0]  out_data,
    output logic [255:0] out_ticks,
    output logic [31:0]  out_quality,
    output logic [31:0]  out_first_seq,
    output logic [31:0]  out_last_seq,
    output logic [31:0]  out_tag,
    output logic         capture_armed,
    output logic [2:0]   capture_partial_len,
    output logic [31:0]  capture_next_seq,
    output logic         capture_seq_exhausted,
    output logic         capture_order_error_event,
    output logic         capture_overrun_event,
    output logic         capture_seq_exhaust_event,
    output logic [31:0]  capture_stat_events,
    output logic [31:0]  capture_stat_scans,
    output logic [31:0]  capture_stat_retired,
    output logic [31:0]  capture_stat_discarded_samples,
    output logic [31:0]  capture_stat_order_errors,
    output logic [31:0]  capture_stat_overruns,
    output logic [2:0]   queue_level,
    output logic [31:0]  queue_stat_accepted,
    output logic [31:0]  queue_stat_retired,
    output logic [31:0]  queue_stat_aborted
);
    logic         capture_valid;
    logic         capture_ready;
    logic [63:0]  capture_data;
    logic [255:0] capture_ticks;
    logic [31:0]  capture_quality;
    logic [31:0]  capture_first_seq;
    logic [31:0]  capture_last_seq;
    logic [31:0]  capture_tag;

    deepeye_sample_scan_capture #(
        .SEQ_W(32), .TICK_W(64), .TAG_W(32), .STAT_W(32)
    ) capture (
        .clk(clk), .rst(rst), .stop(stop), .rearm(rearm),
        .rearm_tag(rearm_tag), .sample_strobe(sample_strobe),
        .sample_channel(sample_channel), .sample_data(sample_data),
        .sample_tick(sample_tick), .sample_quality(sample_quality),
        .out_ready(capture_ready), .out_valid(capture_valid),
        .out_data(capture_data), .out_ticks(capture_ticks),
        .out_quality(capture_quality), .out_first_seq(capture_first_seq),
        .out_last_seq(capture_last_seq), .out_tag(capture_tag),
        .armed(capture_armed), .partial_len(capture_partial_len),
        .next_seq(capture_next_seq), .seq_exhausted(capture_seq_exhausted),
        .order_error_event(capture_order_error_event),
        .overrun_event(capture_overrun_event),
        .seq_exhaust_event(capture_seq_exhaust_event),
        .stat_events(capture_stat_events), .stat_scans(capture_stat_scans),
        .stat_retired(capture_stat_retired),
        .stat_discarded_samples(capture_stat_discarded_samples),
        .stat_order_errors(capture_stat_order_errors),
        .stat_overruns(capture_stat_overruns)
    );

    deepeye_raw_scan_queue #(
        .DEPTH(4), .SEQ_W(32), .TICK_W(64), .TAG_W(32), .STAT_W(32)
    ) queue (
        .clk(clk), .rst(rst), .cancel(queue_cancel),
        .in_valid(capture_valid), .in_ready(capture_ready),
        .in_data(capture_data), .in_ticks(capture_ticks),
        .in_quality(capture_quality), .in_first_seq(capture_first_seq),
        .in_last_seq(capture_last_seq), .in_tag(capture_tag),
        .out_ready(out_ready), .out_valid(out_valid),
        .out_data(out_data), .out_ticks(out_ticks), .out_quality(out_quality),
        .out_first_seq(out_first_seq), .out_last_seq(out_last_seq), .out_tag(out_tag),
        .level(queue_level), .stat_accepted(queue_stat_accepted),
        .stat_retired(queue_stat_retired), .stat_aborted(queue_stat_aborted)
    );
endmodule
