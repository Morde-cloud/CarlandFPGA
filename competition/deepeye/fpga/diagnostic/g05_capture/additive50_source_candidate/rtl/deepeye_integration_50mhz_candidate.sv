// Minimum same-PS/FCLK50 integration topology. SOURCE_ONLY / UNEXECUTED.
// Task DEEPEYE-IMPLEMENTATION-20261014/v1; work
// B-DEEPEYE-G05-ADDITIVE50-INTEGRATION-SOURCE-20261029-63.
//
// This source is disabled and is not a build, pinout, address map, HWH, clock
// approval, ABI activation, H12 result or product acceptance. FCLK50 is a
// proposal. The 50G05 external connector, physical pins, PS aperture and Root
// provenance/admission/pose/action records are not produced here. A alone
// reviews, releases, builds and operates the board.
`default_nettype none
module deepeye_integration_50mhz_candidate #(
    parameter integer CLOCK_HZ = 50000000,
    parameter integer BAUD = 0,
    parameter bit SOURCE_REVIEW_HOLD = 1'b1
) (
    // One common proposed PS fabric clock. All synchronous logic below uses
    // this clock. No PL-generated clock or clock-domain crossing is added here.
    input logic fclk50_candidate,
    input logic peripheral_aresetn_candidate,

    // Existing raw acquisition source interface. sample_tick is the original
    // uint64 source QPC_ns supplied by Root; sample_quality is opaque uint8.
    input logic sample_strobe,
    input logic [1:0] sample_channel,
    input logic [15:0] sample_data,
    input logic [63:0] sample_tick,
    input logic [7:0] sample_quality,
    // Root-owned synchronous DATA-PATH cancellation only. This disarms raw
    // capture and flushes queued/lane/sample/codec/serializer/UART state.
    // It is not G05/PC motion STOP, a host ACK, or a retired world action.
    input logic source_cancel,
    input logic capture_stop,
    input logic capture_rearm,
    input logic [31:0] capture_rearm_tag,
    input logic queue_cancel,
    input logic lane_cancel,

    // Root-owned association sideband for one lane/sample block. Full host
    // session strings and source hashes stay in the Root receipt, not here.
    input logic assoc_valid, output logic assoc_ready,
    input logic [31:0] assoc_tag,
    input logic [31:0] assoc_first_seq, assoc_last_seq,
    input logic [1:0] assoc_channel,
    input logic [31:0] assoc_session, assoc_first_index,
    input logic [7:0] assoc_count,
    input logic [3:0] assoc_e,
    input logic [15:0] assoc_index_stride, assoc_tick_stride_us,
    input logic [63:0] assoc_first_qpc_ns, assoc_first_tick_us,
    input logic [9:0] assoc_first_remainder_ns,
    input logic [63:0] assoc_tick_stride_ns,
    input logic [62:0] assoc_origin_qpc_ns,
    input logic [63:0] assoc_origin_tick_us,
    input logic [9:0] assoc_origin_remainder_ns,
    input logic assoc_semantics_valid,
    input logic assoc_valid_sample, assoc_saturated, assoc_held, assoc_source_fault,
    input logic [63:0] assoc_source_qpc_ns, assoc_source_tick_us,
    input logic [9:0] assoc_source_remainder_ns,
    input logic [7:0] assoc_epoch, input logic [15:0] assoc_seq,

    // Existing lane stream. Top consumes one lane only when a matching Root
    // association is present; no first/last capture sequence is relabelled as
    // a per-channel acquisition index.
    output logic trace_lane_ready,

    // Unproduced Root-owned blocking UART boundary. Physical pin/profile unset.
    output logic trace_uart_tx,
    output logic trace_transaction_aborted,
    output logic trace_result_valid, output logic [2:0] trace_result_error,
    output logic [5:0] trace_result_bytes,
    output logic [3:0] trace_refusal_code,
    output logic trace_wire_faulted, trace_transport_profile_unset,
    // Empty/disarmed internal data path; not source health or movement STOP.
    // Root must record the cancellation and invalidate any partial wire frame.
    output logic data_path_quiescent,
    output logic capture_fault_event, capture_sequence_exhausted,
    output logic [31:0] capture_discarded_samples,

    // G05 private AXI4-Lite candidate. PS assigns the actual aperture externally.
    input logic [11:0] s_axi_awaddr, input logic [2:0] s_axi_awprot,
    input logic s_axi_awvalid, output logic s_axi_awready,
    input logic [31:0] s_axi_wdata, input logic [3:0] s_axi_wstrb,
    input logic s_axi_wvalid, output logic s_axi_wready,
    output logic [1:0] s_axi_bresp, output logic s_axi_bvalid,
    input logic s_axi_bready,
    input logic [11:0] s_axi_araddr, input logic [2:0] s_axi_arprot,
    input logic s_axi_arvalid, output logic s_axi_arready,
    output logic [31:0] s_axi_rdata, output logic [1:0] s_axi_rresp,
    output logic s_axi_rvalid, input logic s_axi_rready,

    // Logical 50G05 candidate connector. These are not approved PYNQ pins.
    output logic g05_50_candidate_yaw_pwm_o,
    output logic g05_50_candidate_pitch_pwm_o,
    output logic g05_50_candidate_speed_pwm_o,
    input logic g05_50_candidate_yaw_capture_i,
    input logic g05_50_candidate_pitch_capture_i,
    input logic g05_50_candidate_speed_capture_i
);
    // Common reset: asynchronous assertion, two-cycle synchronous release.
    (* ASYNC_REG = "TRUE" *) logic [1:0] trace_reset_release_q;
    always_ff @(posedge fclk50_candidate or negedge peripheral_aresetn_candidate) begin
        if (!peripheral_aresetn_candidate) trace_reset_release_q <= 2'b00;
        else trace_reset_release_q <= {trace_reset_release_q[0],1'b1};
    end
    wire trace_rst = !trace_reset_release_q[1] || SOURCE_REVIEW_HOLD;

    logic cap_out_valid, cap_out_ready;
    logic [63:0] cap_out_data;
    logic [255:0] cap_out_ticks;
    logic [31:0] cap_out_quality, cap_out_first_seq, cap_out_last_seq, cap_out_tag;
    logic cap_armed;
    logic [2:0] cap_partial_len;
    logic [31:0] cap_next_seq;
    logic cap_seq_exhausted, cap_order_error_event, cap_overrun_event, cap_seq_exhaust_event;
    logic [31:0] cap_stat_events, cap_stat_scans, cap_stat_retired;
    logic [31:0] cap_stat_discarded_samples, cap_stat_order_errors, cap_stat_overruns;
    logic [2:0] cap_queue_level;
    logic [31:0] cap_queue_accepted, cap_queue_retired, cap_queue_aborted;

    deepeye_buffered_scan_capture capture_i (
        .clk(fclk50_candidate), .rst(trace_rst), .stop(capture_stop || source_cancel),
        .rearm(capture_rearm), .queue_cancel(queue_cancel || source_cancel),
        .sample_strobe(sample_strobe), .rearm_tag(capture_rearm_tag),
        .sample_channel(sample_channel), .sample_data(sample_data),
        .sample_tick(sample_tick), .sample_quality(sample_quality),
        .out_ready(cap_out_ready), .out_valid(cap_out_valid), .out_data(cap_out_data),
        .out_ticks(cap_out_ticks), .out_quality(cap_out_quality),
        .out_first_seq(cap_out_first_seq), .out_last_seq(cap_out_last_seq),
        .out_tag(cap_out_tag), .capture_armed(cap_armed),
        .capture_partial_len(cap_partial_len), .capture_next_seq(cap_next_seq),
        .capture_seq_exhausted(cap_seq_exhausted),
        .capture_order_error_event(cap_order_error_event),
        .capture_overrun_event(cap_overrun_event),
        .capture_seq_exhaust_event(cap_seq_exhaust_event),
        .capture_stat_events(cap_stat_events), .capture_stat_scans(cap_stat_scans),
        .capture_stat_retired(cap_stat_retired),
        .capture_stat_discarded_samples(cap_stat_discarded_samples),
        .capture_stat_order_errors(cap_stat_order_errors),
        .capture_stat_overruns(cap_stat_overruns),
        .queue_level(cap_queue_level), .queue_stat_accepted(cap_queue_accepted),
        .queue_stat_retired(cap_queue_retired), .queue_stat_aborted(cap_queue_aborted));

    assign capture_fault_event = cap_order_error_event || cap_overrun_event || cap_seq_exhaust_event;
    assign capture_sequence_exhausted = cap_seq_exhausted;
    assign capture_discarded_samples = cap_stat_discarded_samples;

    logic lane_valid, lane_ready, lane_last;
    logic [1:0] lane_channel;
    logic [15:0] lane_data;
    logic [63:0] lane_tick;
    logic [7:0] lane_quality;
    logic [31:0] lane_first_seq, lane_last_seq, lane_tag;

    deepeye_scan_lane_stream lane_i (
        .clk(fclk50_candidate), .rst(trace_rst), .cancel(lane_cancel || source_cancel),
        .in_valid(cap_out_valid), .in_ready(cap_out_ready), .in_data(cap_out_data),
        .in_ticks(cap_out_ticks), .in_quality(cap_out_quality),
        .in_first_seq(cap_out_first_seq), .in_last_seq(cap_out_last_seq),
        .in_tag(cap_out_tag), .out_valid(lane_valid), .out_ready(lane_ready),
        .out_channel(lane_channel), .out_data(lane_data), .out_tick(lane_tick),
        .out_quality(lane_quality), .out_first_seq(lane_first_seq),
        .out_last_seq(lane_last_seq), .out_tag(lane_tag), .out_last(lane_last));

    logic trace_blk_valid, trace_blk_ready;
    logic trace_s_valid, trace_s_ready;
    logic trace_result_ready, trace_busy, trace_cancel_active;
    logic sample_pending_q, source_cancelled_q;
    wire assoc_match = !trace_rst && !source_cancel && !trace_cancel_active && !sample_pending_q && lane_valid && assoc_valid &&
        (assoc_tag == lane_tag) &&
        (assoc_first_seq == lane_first_seq) &&
        (assoc_last_seq == lane_last_seq) &&
        (assoc_channel == lane_channel) &&
        (assoc_count == 8'd1) &&
        (assoc_first_qpc_ns == lane_tick);
    assign lane_ready = trace_blk_ready && assoc_match;
    assign trace_lane_ready = lane_ready;
    assign assoc_ready = trace_blk_ready && assoc_match;
    // Producer valid is independent of downstream ready. Root must hold
    // assoc_valid and every assoc_* field until assoc_valid && assoc_ready,
    // or explicitly cancel the joined transaction. The lane stream holds its
    // pending raw lane while stalled. No mismatch timeout is invented here.
    assign trace_blk_valid = assoc_match;

    logic [15:0] sample_data_q;
    always_ff @(posedge fclk50_candidate) begin
        if (trace_rst) source_cancelled_q <= 1'b0;
        else if (source_cancel) source_cancelled_q <= 1'b1;
        else if (capture_rearm) source_cancelled_q <= 1'b0;
    end
    always_ff @(posedge fclk50_candidate) begin
        if (trace_rst || source_cancel || trace_cancel_active) begin
            sample_pending_q <= 1'b0;
            sample_data_q <= 16'd0;
        end else begin
            if (trace_blk_valid && trace_blk_ready) begin
                sample_pending_q <= 1'b1;
                sample_data_q <= lane_data;
            end else if (trace_s_valid && trace_s_ready) begin
                sample_pending_q <= 1'b0;
            end else if (trace_result_valid) begin
                // Refused descriptor produced no payload; drop its held sample.
                sample_pending_q <= 1'b0;
            end
        end
    end
    assign trace_s_valid = sample_pending_q;

    deepeye_trace_block_uart_50mhz_candidate #(
        .CLOCK_HZ(CLOCK_HZ), .BAUD(BAUD), .STAT_W(32)
    ) trace_i (
        .clk(fclk50_candidate), .rst(trace_rst), .cancel(source_cancel),
        // No public v2 semantic or transport profile is activated by this top.
        .profile_v2_authorized(1'b0), .transport_allowed(1'b0),
        .blk_valid(trace_blk_valid), .blk_ready(trace_blk_ready),
        .blk_count(assoc_count), .blk_e(assoc_e), .blk_session(assoc_session),
        .blk_channel(assoc_channel), .blk_first_index(assoc_first_index),
        .blk_index_stride(assoc_index_stride),
        .blk_first_qpc_ns(assoc_first_qpc_ns), .blk_first_tick_us(assoc_first_tick_us),
        .blk_first_remainder_ns(assoc_first_remainder_ns),
        .blk_tick_stride_ns(assoc_tick_stride_ns),
        .blk_tick_stride_us(assoc_tick_stride_us),
        .blk_origin_qpc_ns(assoc_origin_qpc_ns),
        .blk_origin_tick_us(assoc_origin_tick_us),
        .blk_origin_remainder_ns(assoc_origin_remainder_ns),
        .blk_raw_quality(lane_quality), .blk_semantics_valid(assoc_semantics_valid),
        .blk_valid_sample(assoc_valid_sample), .blk_saturated(assoc_saturated),
        .blk_held(assoc_held), .blk_source_fault(assoc_source_fault),
        .blk_source_qpc_ns(assoc_source_qpc_ns),
        .blk_source_tick_us(assoc_source_tick_us),
        .blk_source_remainder_ns(assoc_source_remainder_ns),
        .cfg_epoch(assoc_epoch), .cfg_seq(assoc_seq),
        .s_valid(trace_s_valid), .s_ready(trace_s_ready),
        .s_data(sample_data_q), .s_last(1'b1),
        .tx(trace_uart_tx), .result_valid(trace_result_valid),
        .result_ready(trace_result_ready), .result_error(trace_result_error),
        .result_bytes(trace_result_bytes), .last_refusal_code(trace_refusal_code),
        .cancel_active(trace_cancel_active),
        .transaction_aborted(trace_transaction_aborted),
        .busy(trace_busy), .wire_faulted(trace_wire_faulted),
        .transport_profile_unset(trace_transport_profile_unset));
    assign trace_result_ready = 1'b1;
    // Qualify this indication only after an actual source_cancel edge. A
    // merely disarmed capture can still hold a completed internal scan slot.
    assign data_path_quiescent = source_cancelled_q && !trace_rst && !capture_rearm && !cap_armed
        && (cap_partial_len == 0) && (cap_queue_level == 0) && !cap_out_valid
        && !lane_valid && !sample_pending_q && !trace_busy;
    // source_cancel beats capture_rearm at the capture primitive. Releasing
    // cancel does not rearm it. Root must issue a fresh explicit rearm/tag and
    // private transport binding; never replay an old descriptor automatically.
    // Already emitted bytes cannot be recalled. Quiescence is a local digital
    // observation only and says nothing about g05_i or a PC/world executor.

    deepeye_g05_axi_50mhz_candidate g05_i (
        .s_axi_aclk(fclk50_candidate),
        .s_axi_aresetn(peripheral_aresetn_candidate && !SOURCE_REVIEW_HOLD),
        .s_axi_awaddr(s_axi_awaddr), .s_axi_awprot(s_axi_awprot),
        .s_axi_awvalid(s_axi_awvalid), .s_axi_awready(s_axi_awready),
        .s_axi_wdata(s_axi_wdata), .s_axi_wstrb(s_axi_wstrb),
        .s_axi_wvalid(s_axi_wvalid), .s_axi_wready(s_axi_wready),
        .s_axi_bresp(s_axi_bresp), .s_axi_bvalid(s_axi_bvalid),
        .s_axi_bready(s_axi_bready), .s_axi_araddr(s_axi_araddr),
        .s_axi_arprot(s_axi_arprot), .s_axi_arvalid(s_axi_arvalid),
        .s_axi_arready(s_axi_arready), .s_axi_rdata(s_axi_rdata),
        .s_axi_rresp(s_axi_rresp), .s_axi_rvalid(s_axi_rvalid),
        .s_axi_rready(s_axi_rready),
        .g05_50_candidate_yaw_pwm_o(g05_50_candidate_yaw_pwm_o),
        .g05_50_candidate_pitch_pwm_o(g05_50_candidate_pitch_pwm_o),
        .g05_50_candidate_speed_pwm_o(g05_50_candidate_speed_pwm_o),
        .g05_50_candidate_yaw_capture_i(g05_50_candidate_yaw_capture_i),
        .g05_50_candidate_pitch_capture_i(g05_50_candidate_pitch_capture_i),
        .g05_50_candidate_speed_capture_i(g05_50_candidate_speed_capture_i));

    // This source intentionally exposes no BOOT, session admission, source
    // authenticity, pose/action registry or motion-enable register. Those gates
    // are external Root/A responsibilities and remain unproduced.
endmodule
`default_nettype wire
