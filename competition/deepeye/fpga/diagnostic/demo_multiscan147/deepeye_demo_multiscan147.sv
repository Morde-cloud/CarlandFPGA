// DEEPEYE-IMPLEMENTATION-20261014/v1
// Work B-DEEPEYE-DEMO-MULTISCAN-INGRESS-20261101-147
// SOURCE_ONLY / UNEXECUTED. This is not a board, BOOT, ADC, motion or
// acceptance result. A alone owns physical operation and build selection.
//
// Contract DEEPEYE-HUMAN-LOCK-20261014/revision1 H01-H15, requirements SHA256
// c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804,
// fixed at f5989cd5defce561f9ba98e6b18fc2682945f0a2. Frozen design
// 1011259415a0916054eb580687612580bc1e5f09. Original29, both H12 paths,
// full 3D/UI and the final 100 MHz / 1% / 100 ms gates remain unchanged and
// are not claimed by this diagnostic source.
//
// This wrapper is deliberately narrow:
//   * unchanged deepeye_aggregate12_candidate turns three native four-lane
//     scans into four same-lane E=0 count=3 blocks;
//   * unchanged deepeye_trace_block_uart_50mhz_candidate supplies the single
//     existing payload/block-encoder/wire-serializer/UART chain;
//   * the small egress adapter below only supplies dynamic owner metadata and
//     the original native first-index association. It is not a compressor;
//   * the existing pinned deepeye_uart_rx is exposed as a bounded ready/valid
//     upload byte boundary with framing/overrun/false-start failure events.
//
// The accepted TRACE payload has no raw-quality field. Quality is an opaque
// input-side association byte checked by aggregate12 for per-channel
// constancy; it is not transported or adjusted here. No quality bit is
// fabricated. The full origin/remainder and companion/source-association
// bytes remain a host-side responsibility.
`default_nettype none

module deepeye_demo_multiscan147 #(
    parameter integer CLOCK_HZ = 50000000,
    parameter integer BAUD = 1000000,
    parameter integer STAT_W = 32
) (
    input wire clk,
    input wire rst,
    input wire cancel,
    input wire enable,
    input wire arm,

    input wire [31:0] cfg_session,
    input wire [7:0] cfg_epoch,
    input wire [15:0] cfg_base_frame_seq,
    input wire [62:0] cfg_origin_qpc_ns,
    input wire [31:0] cfg_tag,

    input wire s_valid,
    output logic s_ready,
    input wire [1:0] s_channel,
    input wire [15:0] s_data,
    input wire [63:0] s_acq_qpc_ns,
    input wire [7:0] s_quality,
    input wire [31:0] s_tag,
    input wire [31:0] s_native_first_seq,
    input wire [31:0] s_native_last_seq,

    // Caller-supplied classification. semantics_valid is not authentication.
    input wire s_semantics_valid,
    input wire s_fresh,
    input wire s_sample_valid,
    input wire s_held,
    input wire s_saturated,
    input wire s_source_fault,

    output logic tx,
    output logic result_valid,
    input wire result_ready,
    output logic [2:0] result_error,
    output logic [5:0] result_bytes,

    // Pinned existing UART RX boundary. tx and rx_async are separate logical
    // directions; this source does not wire them together and assigns no pin.
    input wire rx_async,
    output logic up_valid,
    input wire up_ready,
    output logic [7:0] up_data,
    output logic up_busy,
    output logic up_framing_error,
    output logic up_overrun,
    output logic up_false_start,

    output logic refused,
    output logic [3:0] refusal_code,
    output logic busy,
    output logic quiescent,
    output logic armed,
    output logic arm_ready,
    output logic batch_done,
    output logic aborted,
    output logic [1:0] abort_code,
    output logic [2:0] frames_retired,
    output logic [3:0] accepted_lanes
);
    localparam logic [3:0] CODE_CFG_WRAP = 4'd10;
    localparam logic [3:0] CODE_CFG_TAG  = 4'd11;
    localparam logic [3:0] CODE_IN_TAG   = 4'd12;
    localparam logic [3:0] CODE_IN_STATUS= 4'd13;
    localparam logic [3:0] CODE_IN_QPC   = 4'd14;
    localparam logic [3:0] CODE_EGRESS   = 4'd15;
    localparam bit PARAM_OK = (CLOCK_HZ == 50000000) && (BAUD == 1000000);

    logic [31:0] cfg_session_q;
    logic [7:0] cfg_epoch_q;
    logic [15:0] cfg_base_frame_seq_q;
    logic [62:0] cfg_origin_qpc_q;
    logic [31:0] cfg_tag_q;

    logic arm_d;
    logic cfg_armed_q;
    logic run_active_q;
    logic start_pending_q;
    logic run_stopped_q;
    logic cfg_refused_q;
    logic [3:0] local_refusal_code_q;
    logic [63:0] scan_qpc_q;
    logic [2:0] frames_retired_q;
    logic batch_done_q;
    logic aborted_q;
    logic [1:0] abort_code_q;

    logic collector_ready;
    logic collector_valid;
    logic collector_refused;
    logic collector_quiescent;
    logic [3:0] collector_count;
    logic [3:0] collector_refusal_code;
    logic [1:0] collector_channel;
    logic [47:0] collector_data;
    logic [191:0] collector_qpcs;
    logic [23:0] collector_qualities;
    logic [31:0] collector_tag;
    logic [31:0] collector_first_index;
    logic [62:0] collector_origin;
    logic [63:0] collector_stride_ns;
    logic [15:0] collector_stride_us;

    logic egress_block_ready;
    logic egress_result_valid;
    logic [2:0] egress_result_error;
    logic [5:0] egress_result_bytes;
    logic egress_retire;
    logic egress_aborted;
    logic egress_busy;
    logic egress_local_refused;

    wire batch_full = (collector_count == 4'd12);
    wire arm_pulse = arm && !arm_d;
    wire path_cancel = rst || cancel || !enable || run_stopped_q || !PARAM_OK;
    wire profile_allowed = cfg_armed_q && !run_stopped_q && !cfg_refused_q &&
                           enable && !rst && !cancel && PARAM_OK;

    wire cfg_wrap_bad = (cfg_base_frame_seq > 16'hFFFC);
    wire cfg_tag_bad = (cfg_tag == 32'd0);
    wire cfg_bad = cfg_wrap_bad || cfg_tag_bad;
    wire [3:0] cfg_bad_code = cfg_wrap_bad ? CODE_CFG_WRAP : CODE_CFG_TAG;

    // The collector is the sole acceptance authority. Its count, not an
    // optimistic top-level handshake count, drives lane order and the public
    // accepted-lane view.
    wire [1:0] lane_in_scan = collector_count[1:0];
    wire s_status_ok = s_semantics_valid && s_fresh && s_sample_valid &&
                       !s_held && !s_saturated && !s_source_fault;
    wire s_tag_ok = (s_tag == cfg_tag_q);
    wire s_scan_qpc_ok = (lane_in_scan == 2'd0) ||
                         (s_acq_qpc_ns == scan_qpc_q);
    wire s_accept_ok = cfg_armed_q && !run_stopped_q && !cfg_refused_q &&
                       !path_cancel && !batch_full &&
                       s_status_ok && s_tag_ok && s_scan_qpc_ok;
    wire s_handshake = s_valid && s_ready;
    wire input_bad = s_valid && cfg_armed_q && !run_stopped_q &&
                     !cfg_refused_q && !path_cancel && !batch_full &&
                     !(s_status_ok && s_tag_ok && s_scan_qpc_ok);
    wire [3:0] input_code = !s_tag_ok ? CODE_IN_TAG :
                            (!s_status_ok ? CODE_IN_STATUS : CODE_IN_QPC);
    wire trace_error = egress_result_valid && result_ready &&
                       (egress_result_error != 3'd0);

    wire can_arm = !run_active_q && !run_stopped_q && !egress_busy &&
                   collector_quiescent && !path_cancel;

    assign s_ready = collector_ready && s_accept_ok;
    assign result_valid = egress_result_valid;
    assign result_error = egress_result_error;
    assign result_bytes = egress_result_bytes;
    assign armed = cfg_armed_q;
    assign arm_ready = can_arm;
    assign batch_done = batch_done_q;
    assign aborted = aborted_q;
    assign abort_code = abort_code_q;
    assign frames_retired = frames_retired_q;
    assign accepted_lanes = collector_count;
    assign busy = run_active_q || egress_busy || collector_valid ||
                  collector_refused || (collector_count != 4'd0);
    assign quiescent = !run_active_q && !cfg_armed_q && !egress_busy &&
                       collector_quiescent &&
                       !collector_valid && !collector_refused;
    assign refused = cfg_refused_q || run_stopped_q ||
                     collector_refused || egress_local_refused;
    assign refusal_code = (local_refusal_code_q != 4'd0) ? local_refusal_code_q :
                          (egress_local_refused ? CODE_EGRESS :
                          (collector_refused ? collector_refusal_code : 4'd0));

    // One arm captures all owner metadata. The collector is rearmed on the
    // following cycle so it samples the newly latched origin, not the previous
    // value. Configuration registers are never rewritten during a batch.
    deepeye_aggregate12_candidate collector_i (
        .clk(clk), .rst(rst), .cancel(path_cancel),
        .rearm(start_pending_q), .seal(collector_count == 4'd12),
        .origin_qpc_ns(cfg_origin_qpc_q),
        .s_valid(s_valid && s_accept_ok), .s_ready(collector_ready),
        .s_channel(s_channel), .s_data(s_data), .s_qpc_ns(s_acq_qpc_ns),
        .s_quality(s_quality), .s_tag(s_tag),
        .s_first_seq(s_native_first_seq), .s_last_seq(s_native_last_seq),
        .semantics_valid(s_semantics_valid), .valid_sample(s_sample_valid),
        .held(s_held),
        .out_valid(collector_valid), .out_ready(egress_block_ready),
        .retire(egress_retire),
        .out_channel(collector_channel), .out_data(collector_data),
        .out_qpcs(collector_qpcs), .out_qualities(collector_qualities),
        .out_first_seqs(), .out_last_seqs(), .out_tag(collector_tag),
        .out_first_index(collector_first_index),
        .out_origin_qpc_ns(collector_origin),
        .out_stride_ns(collector_stride_ns),
        .out_stride_us(collector_stride_us),
        .refused(collector_refused), .refusal_code(collector_refusal_code),
        .quiescent(collector_quiescent), .invalid_rearm(), .count(collector_count)
    );

    deepeye_demo_multiscan147_egress #(
        .CLOCK_HZ(CLOCK_HZ), .BAUD(BAUD), .STAT_W(STAT_W)
    ) egress_i (
        .clk(clk), .rst(rst), .cancel(path_cancel), .enable(enable),
        .profile_allowed(profile_allowed),
        .cfg_session(cfg_session_q), .cfg_epoch(cfg_epoch_q),
        .cfg_base_frame_seq(cfg_base_frame_seq_q),
        .cfg_origin_qpc_ns(cfg_origin_qpc_q), .cfg_tag(cfg_tag_q),
        .block_valid(collector_valid), .block_ready(egress_block_ready),
        .block_channel(collector_channel), .block_data(collector_data),
        .block_qpcs(collector_qpcs), .block_qualities(collector_qualities),
        .block_tag(collector_tag), .block_first_index(collector_first_index),
        .block_origin(collector_origin),
        .block_stride_ns(collector_stride_ns),
        .block_stride_us(collector_stride_us),
        .tx(tx), .result_valid(egress_result_valid),
        .result_ready(result_ready), .result_error(egress_result_error),
        .result_bytes(egress_result_bytes), .retire(egress_retire),
        .aborted(egress_aborted), .busy(egress_busy),
        .local_refused(egress_local_refused),
        .local_refusal_code()
    );

    // Existing pinned receiver used as the actual upload byte source boundary.
    // The external integrator supplies rx_async and consumes the ready/valid
    // bytes or a FIFO layer. This file creates no physical wiring or pin map.
    deepeye_uart_rx #(
        .CLOCK_HZ(CLOCK_HZ), .BAUD(BAUD), .STAT_W(STAT_W)
    ) uplink_i (
        .clk(clk), .rst(rst), .cancel(cancel || !enable || !PARAM_OK),
        .rx_async(rx_async),
        .out_ready(up_ready), .out_valid(up_valid), .out_data(up_data),
        .busy(up_busy), .framing_error_event(up_framing_error),
        .overrun_event(up_overrun), .false_start_event(up_false_start),
        .stat_frames(), .stat_retired(), .stat_overruns(), .stat_framing(),
        .stat_false_starts(), .stat_aborted()
    );

    always_ff @(posedge clk) begin
        if (rst) begin
            arm_d <= 1'b0;
            cfg_session_q <= 32'd0;
            cfg_epoch_q <= 8'd0;
            cfg_base_frame_seq_q <= 16'd0;
            cfg_origin_qpc_q <= 63'd0;
            cfg_tag_q <= 32'd0;
            cfg_armed_q <= 1'b0;
            run_active_q <= 1'b0;
            start_pending_q <= 1'b0;
            run_stopped_q <= 1'b0;
            cfg_refused_q <= 1'b0;
            local_refusal_code_q <= 4'd0;
            scan_qpc_q <= 64'd0;
            frames_retired_q <= 3'd0;
            batch_done_q <= 1'b0;
            aborted_q <= 1'b0;
            abort_code_q <= 2'd0;
        end else begin
            arm_d <= arm;

            if (arm_pulse && can_arm) begin
                cfg_refused_q <= 1'b0;
                run_stopped_q <= 1'b0;
                local_refusal_code_q <= 4'd0;
                scan_qpc_q <= 64'd0;
                frames_retired_q <= 3'd0;
                batch_done_q <= 1'b0;
                aborted_q <= 1'b0;
                abort_code_q <= 2'd0;
                if (cfg_bad) begin
                    cfg_refused_q <= 1'b1;
                    local_refusal_code_q <= cfg_bad_code;
                    cfg_armed_q <= 1'b0;
                    run_active_q <= 1'b0;
                    start_pending_q <= 1'b0;
                end else begin
                    cfg_session_q <= cfg_session;
                    cfg_epoch_q <= cfg_epoch;
                    cfg_base_frame_seq_q <= cfg_base_frame_seq;
                    cfg_origin_qpc_q <= cfg_origin_qpc_ns;
                    cfg_tag_q <= cfg_tag;
                    cfg_armed_q <= 1'b1;
                    run_active_q <= 1'b1;
                    start_pending_q <= 1'b1;
                end
            end else if (cancel || !enable) begin
                cfg_armed_q <= 1'b0;
                run_active_q <= 1'b0;
                start_pending_q <= 1'b0;
                run_stopped_q <= 1'b0;
                cfg_refused_q <= 1'b0;
                local_refusal_code_q <= 4'd0;
                scan_qpc_q <= 64'd0;
                frames_retired_q <= 3'd0;
                batch_done_q <= 1'b0;
                if (run_active_q || (collector_count != 4'd0) ||
                    collector_valid || collector_refused || egress_busy) begin
                    aborted_q <= 1'b1;
                    abort_code_q <= cancel ? 2'd1 : 2'd2;
                end
            end else if (run_stopped_q) begin
                cfg_armed_q <= 1'b0;
                run_active_q <= 1'b0;
                start_pending_q <= 1'b0;
                scan_qpc_q <= 64'd0;
                if (egress_aborted && !aborted_q) begin
                    aborted_q <= 1'b1;
                    abort_code_q <= 2'd3;
                end
            end else if (cfg_refused_q) begin
                cfg_armed_q <= 1'b0;
                run_active_q <= 1'b0;
                start_pending_q <= 1'b0;
                scan_qpc_q <= 64'd0;
            end else begin
                if (start_pending_q) start_pending_q <= 1'b0;

                if (s_handshake && lane_in_scan == 2'd0)
                    scan_qpc_q <= s_acq_qpc_ns;

                if (input_bad) begin
                    run_stopped_q <= 1'b1;
                    local_refusal_code_q <= input_code;
                end else if (collector_refused && !run_stopped_q) begin
                    run_stopped_q <= 1'b1;
                    local_refusal_code_q <= collector_refusal_code;
                end else if (egress_local_refused && !run_stopped_q) begin
                    run_stopped_q <= 1'b1;
                    local_refusal_code_q <= CODE_EGRESS;
                end else if (trace_error && !run_stopped_q) begin
                    run_stopped_q <= 1'b1;
                    local_refusal_code_q <= CODE_EGRESS;
                end

                if (egress_retire) begin
                    if (frames_retired_q == 3'd3) begin
                        frames_retired_q <= 3'd4;
                        run_active_q <= 1'b0;
                        cfg_armed_q <= 1'b0;
                        start_pending_q <= 1'b0;
                        scan_qpc_q <= 64'd0;
                        batch_done_q <= 1'b1;
                    end else begin
                        frames_retired_q <= frames_retired_q + 3'd1;
                    end
                end

                if (egress_aborted && !aborted_q) begin
                    aborted_q <= 1'b1;
                    abort_code_q <= 2'd3;
                end
            end
        end
    end

    // This composition is defined only at the selected 50 MHz / 1 Mbaud
    // diagnostic point. It is not the final 100 MHz timing qualification.
    // synthesis translate_off
    generate
        if (!PARAM_OK) begin : g_parameter_guard
            initial begin
                $fatal(1, "deepeye_demo_multiscan147: exact 50 MHz / 1 Mbaud required");
            end
        end
    endgenerate
    // synthesis translate_on
endmodule

// Small descriptor adapter only. It changes no codec rule and contains no
// compressor. All block values, QPCs, qualities and native indices come from
// the unchanged aggregate; this module supplies dynamic session/epoch/frame
// sequence/origin metadata and the existing TRACE block encoder's handshake.
module deepeye_demo_multiscan147_egress #(
    parameter integer CLOCK_HZ = 50000000,
    parameter integer BAUD = 1000000,
    parameter integer STAT_W = 32
) (
    input wire clk,
    input wire rst,
    input wire cancel,
    input wire enable,
    input wire profile_allowed,
    input wire [31:0] cfg_session,
    input wire [7:0] cfg_epoch,
    input wire [15:0] cfg_base_frame_seq,
    input wire [62:0] cfg_origin_qpc_ns,
    input wire [31:0] cfg_tag,

    input wire block_valid,
    output logic block_ready,
    input wire [1:0] block_channel,
    input wire [47:0] block_data,
    input wire [191:0] block_qpcs,
    input wire [23:0] block_qualities,
    input wire [31:0] block_tag,
    input wire [31:0] block_first_index,
    input wire [62:0] block_origin,
    input wire [63:0] block_stride_ns,
    input wire [15:0] block_stride_us,

    output logic tx,
    output logic result_valid,
    input wire result_ready,
    output logic [2:0] result_error,
    output logic [5:0] result_bytes,
    output logic retire,
    output logic aborted,
    output logic busy,
    output logic local_refused,
    output logic [3:0] local_refusal_code
);
    localparam logic [2:0] IDLE = 3'd0;
    localparam logic [2:0] DESCRIBE = 3'd1;
    localparam logic [2:0] SAMPLES = 3'd2;
    localparam logic [2:0] RESULT = 3'd3;

    logic [2:0] state_q;
    logic [2:0] sample_no_q;
    logic [47:0] data_q;
    logic [63:0] first_qpc_q;
    logic [62:0] origin_q;
    logic [63:0] stride_ns_q;
    logic [15:0] stride_us_q;
    logic [7:0] quality_q;
    logic [1:0] channel_q;
    logic [31:0] index_q;

    logic tb_blk_ready;
    logic tb_s_ready;
    logic tb_tx;
    logic tb_result_valid;
    logic [2:0] tb_result_error;
    logic [5:0] tb_result_bytes;
    logic tb_transaction_aborted;
    logic tb_busy;

    wire [64:0] mid_delta = {1'b0, block_qpcs[127:64]} - {1'b0, block_qpcs[63:0]};
    wire [64:0] high_delta = {1'b0, block_qpcs[191:128]} - {1'b0, block_qpcs[127:64]};
    wire [64:0] first_delta = {1'b0, block_qpcs[63:0]} - {2'd0, block_origin};
    wire [64:0] first_tick_ext = first_delta / 65'd1000;
    wire stride_exact = (block_stride_us != 16'd0) &&
                        (block_stride_ns == {48'd0, block_stride_us} * 64'd1000);
    wire qpc_regular = (mid_delta == {1'b0, block_stride_ns}) &&
                       (high_delta == {1'b0, block_stride_ns}) && stride_exact;
    wire qpc_u63 = !block_qpcs[63] && !block_qpcs[127] && !block_qpcs[191];
    wire first_time_ok = !block_qpcs[63] &&
                         ({1'b0, block_qpcs[63:0]} >= {2'd0, block_origin}) &&
                         (first_tick_ext[64:32] == 33'd0);
    wire index_end_ok = (({1'b0, block_first_index} + 33'd8) <=
                         33'h0FFFFFFFF);
    wire frame_seq_ok = (cfg_base_frame_seq <= 16'hFFFC);
    wire quality_uniform = (block_qualities[7:0] == block_qualities[15:8]) &&
                           (block_qualities[7:0] == block_qualities[23:16]);
    wire block_bad = (block_origin != cfg_origin_qpc_ns) ||
                     (block_tag != cfg_tag) || (block_tag == 32'd0) ||
                     !frame_seq_ok || !qpc_regular || !qpc_u63 ||
                     !first_time_ok || !index_end_ok || !quality_uniform;

    wire [63:0] first_tick_w = (first_qpc_q - {1'b0, origin_q}) / 64'd1000;
    wire [9:0] first_remainder_w = (first_qpc_q - {1'b0, origin_q}) % 64'd1000;
    wire tb_blk_valid = (state_q == DESCRIBE) && !rst && !cancel && enable && profile_allowed;
    wire tb_s_valid = (state_q == SAMPLES) && !rst && !cancel && enable && profile_allowed;
    wire tb_s_last = (sample_no_q == 2'd2);
    wire tb_result_ready = result_ready && (state_q == RESULT);

    assign block_ready = (state_q == IDLE) && !rst && !cancel && enable && profile_allowed;
    assign tx = tb_tx;
    assign result_valid = (state_q == RESULT) && tb_result_valid;
    assign result_error = tb_result_error;
    assign result_bytes = tb_result_bytes;
    assign retire = (state_q == RESULT) && tb_result_valid && result_ready &&
                    (tb_result_error == 3'd0);
    assign aborted = tb_transaction_aborted;
    assign busy = (state_q != IDLE) || tb_busy;

    // These downstream status levels are the consequence of the top-level
    // acceptance gate: only fresh, semantics-valid, non-held, non-saturated,
    // non-fault records reach the collector. They add no new provenance or
    // fresh flag. quality_q is supplied only as the aggregate's opaque
    // association value; the pinned payload adapter does not encode it.
    deepeye_trace_block_uart_50mhz_candidate #(
        .CLOCK_HZ(CLOCK_HZ), .BAUD(BAUD), .STAT_W(STAT_W)
    ) tb_i (
        .clk(clk), .rst(rst), .cancel(cancel),
        .profile_v2_authorized(profile_allowed),
        .transport_allowed(profile_allowed),
        .blk_valid(tb_blk_valid), .blk_ready(tb_blk_ready),
        .blk_count(8'd3), .blk_e(4'd0),
        .blk_session(cfg_session), .blk_channel(channel_q),
        .blk_first_index(index_q), .blk_index_stride(16'd4),
        .blk_first_qpc_ns(first_qpc_q),
        .blk_first_tick_us(first_tick_w),
        .blk_first_remainder_ns(first_remainder_w),
        .blk_tick_stride_ns(stride_ns_q),
        .blk_tick_stride_us(stride_us_q),
        .blk_origin_qpc_ns(origin_q),
        .blk_origin_tick_us(64'd0), .blk_origin_remainder_ns(10'd0),
        .blk_raw_quality(quality_q),
        .blk_semantics_valid(1'b1), .blk_valid_sample(1'b1),
        .blk_saturated(1'b0), .blk_held(1'b0), .blk_source_fault(1'b0),
        .blk_source_qpc_ns(first_qpc_q),
        .blk_source_tick_us(first_tick_w),
        .blk_source_remainder_ns(first_remainder_w),
        .cfg_epoch(cfg_epoch),
        .cfg_seq(cfg_base_frame_seq + {14'd0, channel_q}),
        .s_valid(tb_s_valid), .s_ready(tb_s_ready),
        .s_data(data_q[16*sample_no_q +: 16]), .s_last(tb_s_last),
        .tx(tb_tx), .result_valid(tb_result_valid),
        .result_ready(tb_result_ready), .result_error(tb_result_error),
        .result_bytes(tb_result_bytes), .last_refusal_code(),
        .cancel_active(), .transaction_aborted(tb_transaction_aborted),
        .busy(tb_busy), .wire_faulted(), .transport_profile_unset()
    );

    always_ff @(posedge clk) begin
        if (rst || cancel) begin
            state_q <= IDLE;
            sample_no_q <= 2'd0;
            data_q <= 48'd0;
            first_qpc_q <= 64'd0;
            origin_q <= 63'd0;
            stride_ns_q <= 64'd0;
            stride_us_q <= 16'd0;
            quality_q <= 8'd0;
            channel_q <= 2'd0;
            index_q <= 32'd0;
            local_refused <= 1'b0;
            local_refusal_code <= 4'd0;
        end else begin
            case (state_q)
                IDLE: if (block_valid && block_ready) begin
                    if (block_bad) begin
                        local_refused <= 1'b1;
                        local_refusal_code <= 4'd1;
                        state_q <= IDLE;
                    end else begin
                        data_q <= block_data;
                        first_qpc_q <= block_qpcs[63:0];
                        origin_q <= block_origin;
                        stride_ns_q <= block_stride_ns;
                        stride_us_q <= block_stride_us;
                        quality_q <= block_qualities[7:0];
                        channel_q <= block_channel;
                        index_q <= block_first_index;
                        sample_no_q <= 2'd0;
                        local_refused <= 1'b0;
                        local_refusal_code <= 4'd0;
                        state_q <= DESCRIBE;
                    end
                end
                DESCRIBE: begin
                    if (tb_result_valid) state_q <= RESULT;
                    else if (tb_blk_ready) state_q <= SAMPLES;
                end
                SAMPLES: begin
                    if (tb_result_valid) state_q <= RESULT;
                    else if (tb_s_ready) begin
                        if (sample_no_q == 2'd2) state_q <= RESULT;
                        else sample_no_q <= sample_no_q + 2'd1;
                    end
                end
                RESULT: if (tb_result_valid && result_ready) state_q <= IDLE;
                default: state_q <= IDLE;
            endcase
        end
    end
endmodule

`default_nettype wire
