// TRACE raw-block-to-UART source composition. SOURCE_ONLY / UNEXECUTED.
// Exact selected chain: raw uint16 block -> existing trace payload encoder ->
// existing wire serializer -> existing byte UART. No already-encoded block
// stream is accepted, and there is no second encoder.
//
// This is not a public type/ABI enable, baud profile, pin assignment or board
// result. BAUD has no approved value here. A legal override must be supplied by
// Root/A; the zero default deliberately leaves the transport unavailable.
`default_nettype none
module deepeye_trace_block_uart_50mhz_candidate #(
    parameter integer CLOCK_HZ = 50000000,
    parameter integer BAUD = 0,
    parameter integer STAT_W = 32
) (
    input wire logic clk, rst, cancel,
    input wire logic profile_v2_authorized, transport_allowed,

    input wire logic blk_valid, output logic blk_ready,
    input wire logic [7:0] blk_count, input wire logic [3:0] blk_e,
    input wire logic [31:0] blk_session, input wire logic [1:0] blk_channel,
    input wire logic [31:0] blk_first_index, input wire logic [15:0] blk_index_stride,
    input wire logic [63:0] blk_first_qpc_ns, blk_first_tick_us,
    input wire logic [9:0] blk_first_remainder_ns,
    input wire logic [63:0] blk_tick_stride_ns,
    input wire logic [15:0] blk_tick_stride_us,
    input wire logic [62:0] blk_origin_qpc_ns,
    input wire logic [63:0] blk_origin_tick_us,
    input wire logic [9:0] blk_origin_remainder_ns,
    input wire logic [7:0] blk_raw_quality,
    input wire logic blk_semantics_valid,
    input wire logic blk_valid_sample, blk_saturated, blk_held, blk_source_fault,
    input wire logic [63:0] blk_source_qpc_ns, blk_source_tick_us,
    input wire logic [9:0] blk_source_remainder_ns,
    input wire logic [7:0] cfg_epoch, input wire logic [15:0] cfg_seq,
    input wire logic s_valid, output logic s_ready,
    input wire logic [15:0] s_data, input wire logic s_last,

    output logic tx,
    output logic result_valid, input wire logic result_ready,
    output logic [2:0] result_error, output logic [5:0] result_bytes,
    output logic [3:0] last_refusal_code,
    // Shared cancellation level, not completion/health/authorization.
    output logic cancel_active,
    // One registered pulse for a non-reset cancel of an accepted outstanding
    // descriptor. Root retains its full accepted identity; no wire ACK implied.
    output logic transaction_aborted,
    output logic busy, wire_faulted, transport_profile_unset
);
    localparam bit CLOCK_VALID = (CLOCK_HZ == 50000000);
    localparam bit BAUD_VALID = CLOCK_VALID && (BAUD >= 1) && (BAUD <= (CLOCK_HZ/2));
    localparam integer CLOCK_SAFE = CLOCK_VALID ? CLOCK_HZ : 50000000;
    localparam integer BAUD_SAFE = BAUD_VALID ? BAUD : 1;
    localparam logic [2:0] IDLE=0, WAIT_ACCEPT=1, WAIT_META=2, FEED=3,
        WAIT_FRAME=4, WAIT_DRAIN=5, REPORT=6, FAULT=7;

    logic [2:0] state_q;
    logic [7:0] epoch_q;
    logic [15:0] seq_q;
    logic [5:0] expected_total_q;
    logic fault_report_pending_q, transaction_active_q;

    logic adapter_blk_ready, adapter_refusal_valid, adapter_s_ready;
    logic [3:0] adapter_refusal_code;
    logic payload_meta_valid;
    logic [1:0] payload_meta_error;
    logic [5:0] payload_meta_bytes;
    logic [31:0] payload_meta_tick;
    logic payload_valid, payload_ready, payload_last;
    logic [7:0] payload_data;
    logic serializer_cfg_ready, serializer_p_ready;
    logic serializer_out_valid, serializer_out_ready, serializer_out_last;
    logic [7:0] serializer_out_data;
    logic [5:0] serializer_out_count;
    logic serializer_busy, serializer_faulted;
    logic [1:0] serializer_fault_code;
    logic uart_in_ready, uart_busy;

    wire candidate_cancel = cancel || !profile_v2_authorized || !transport_allowed || !CLOCK_VALID || !BAUD_VALID;
    wire enabled = !rst && !candidate_cancel;
    assign cancel_active = candidate_cancel;
    wire serializer_cfg_valid = (state_q==WAIT_META) && payload_meta_valid &&
        (payload_meta_error==0) && serializer_cfg_ready && enabled;
    wire adapter_blk_valid = blk_valid && (state_q==IDLE) &&
        serializer_cfg_ready && enabled;

    assign blk_ready = adapter_blk_ready && (state_q==IDLE) &&
        serializer_cfg_ready && enabled;
    assign s_ready = adapter_s_ready && (state_q==WAIT_ACCEPT) && enabled;
    assign payload_ready = serializer_p_ready && (state_q==FEED) && enabled;
    assign serializer_out_ready = uart_in_ready && (state_q==WAIT_FRAME) && enabled;
    assign result_valid = !rst && !cancel && enabled &&
        (((state_q==REPORT) && !serializer_faulted) ||
         ((state_q==FAULT) && fault_report_pending_q));
    assign busy = (state_q!=IDLE) || adapter_refusal_valid || serializer_busy || uart_busy;
    assign wire_faulted = serializer_faulted;
    assign transport_profile_unset = !BAUD_VALID;

    deepeye_trace_block_payload_1us_candidate payload_stage (
        .clk(clk), .rst(rst), .cancel(candidate_cancel),
        .profile_v2_authorized(profile_v2_authorized),
        .blk_valid(adapter_blk_valid), .blk_ready(adapter_blk_ready),
        .blk_count(blk_count), .blk_e(blk_e), .blk_session(blk_session),
        .blk_channel(blk_channel), .blk_first_index(blk_first_index),
        .blk_index_stride(blk_index_stride),
        .blk_first_qpc_ns(blk_first_qpc_ns), .blk_first_tick_us(blk_first_tick_us),
        .blk_first_remainder_ns(blk_first_remainder_ns),
        .blk_tick_stride_ns(blk_tick_stride_ns), .blk_tick_stride_us(blk_tick_stride_us),
        .blk_origin_qpc_ns(blk_origin_qpc_ns),
        .blk_origin_tick_us(blk_origin_tick_us),
        .blk_origin_remainder_ns(blk_origin_remainder_ns),
        .blk_raw_quality(blk_raw_quality), .blk_semantics_valid(blk_semantics_valid),
        .blk_valid_sample(blk_valid_sample), .blk_saturated(blk_saturated),
        .blk_held(blk_held), .blk_source_fault(blk_source_fault),
        .blk_source_qpc_ns(blk_source_qpc_ns), .blk_source_tick_us(blk_source_tick_us),
        .blk_source_remainder_ns(blk_source_remainder_ns),
        .refusal_valid(adapter_refusal_valid), .refusal_code(adapter_refusal_code),
        .s_valid(s_valid && (state_q==WAIT_ACCEPT) && enabled), .s_ready(adapter_s_ready),
        .s_data(s_data), .s_last(s_last),
        .meta_valid(payload_meta_valid),
        .meta_ready((state_q==WAIT_META) && serializer_cfg_ready && enabled),
        .meta_error(payload_meta_error), .meta_bytes(payload_meta_bytes),
        .meta_tick(payload_meta_tick),
        .p_valid(payload_valid), .p_ready(payload_ready),
        .p_data(payload_data), .p_last(payload_last));

    deepeye_wire_serializer #(.STAT_W(STAT_W)) serializer (
        .clk(clk), .rst(rst), .cancel(candidate_cancel),
        .cfg_valid(serializer_cfg_valid), .cfg_ready(serializer_cfg_ready),
        .cfg_type(8'hE4), .cfg_epoch(epoch_q), .cfg_seq(seq_q),
        .cfg_tick(payload_meta_tick), .cfg_len(payload_meta_bytes),
        .p_valid(payload_valid && (state_q==FEED) && enabled),
        .p_ready(serializer_p_ready), .p_data(payload_data), .p_last(payload_last),
        .out_valid(serializer_out_valid),
        .out_ready(serializer_out_ready), .out_data(serializer_out_data),
        .out_last(serializer_out_last), .out_count(serializer_out_count),
        .busy(serializer_busy), .receiving(), .faulted(serializer_faulted),
        .fault_event(), .fault_code(serializer_fault_code),
        .stat_admitted(), .stat_sent(), .stat_aborted(), .stat_faults());

    deepeye_uart_tx #(.CLOCK_HZ(CLOCK_SAFE), .BAUD(BAUD_SAFE), .STAT_W(STAT_W)) uart (
        .clk(clk), .rst(rst), .cancel(candidate_cancel),
        .in_valid(serializer_out_valid && (state_q==WAIT_FRAME) && enabled),
        .in_ready(uart_in_ready), .in_data(serializer_out_data), .tx(tx),
        .busy(uart_busy), .stat_accepted(), .stat_completed(), .stat_aborted());

    always_ff @(posedge clk) begin
        if (rst) begin
            transaction_active_q <= 1'b0;
            transaction_aborted <= 1'b0;
        end else begin
            transaction_aborted <= 1'b0;
            if (candidate_cancel) begin
                transaction_aborted <= transaction_active_q;
                transaction_active_q <= 1'b0;
            end else if (adapter_blk_valid && adapter_blk_ready) begin
                transaction_active_q <= 1'b1;
            end else if (result_valid && result_ready) begin
                transaction_active_q <= 1'b0;
            end
        end
    end

    always_ff @(posedge clk) begin
        if (rst || candidate_cancel) begin
            state_q <= IDLE;
            epoch_q <= 0;
            seq_q <= 0;
            expected_total_q <= 0;
            result_error <= 0;
            result_bytes <= 0;
            last_refusal_code <= 0;
            fault_report_pending_q <= 0;
        end else if ((state_q!=IDLE) && (state_q!=FAULT) && serializer_faulted) begin
            state_q <= FAULT;
            result_error <= 3'd6;
            result_bytes <= 0;
            fault_report_pending_q <= 1;
        end else begin
            case (state_q)
                IDLE: if (adapter_blk_valid && adapter_blk_ready) begin
                    epoch_q <= cfg_epoch;
                    seq_q <= cfg_seq;
                    state_q <= WAIT_ACCEPT;
                end
                WAIT_ACCEPT: begin
                    if (adapter_refusal_valid) begin
                        last_refusal_code <= adapter_refusal_code;
                        result_error <= 3'd4;
                        result_bytes <= 0;
                        state_q <= REPORT;
                    end else if (payload_meta_valid) begin
                        state_q <= WAIT_META;
                    end
                end
                WAIT_META: begin
                    if (payload_meta_valid && serializer_cfg_ready) begin
                        if (payload_meta_error!=0) begin
                            result_error <= 3'd5;
                            result_bytes <= 0;
                            state_q <= REPORT;
                        end else begin
                            expected_total_q <= 6'd14 + payload_meta_bytes;
                            state_q <= FEED;
                        end
                    end
                end
                FEED: if (payload_valid && payload_ready && payload_last)
                    state_q <= WAIT_FRAME;
                WAIT_FRAME: if (serializer_out_valid && serializer_out_ready && serializer_out_last)
                    state_q <= WAIT_DRAIN;
                WAIT_DRAIN: if (!uart_busy) begin
                    result_error <= 3'd0;
                    result_bytes <= expected_total_q;
                    state_q <= REPORT;
                end
                REPORT: if (result_valid && result_ready) state_q <= IDLE;
                FAULT: if (result_valid && result_ready) fault_report_pending_q <= 0;
                default: begin
                    state_q <= FAULT;
                    result_error <= 3'd6;
                    result_bytes <= 0;
                    fault_report_pending_q <= 1;
                end
            endcase
        end
    end

    // Candidate gates default closed; A owns any enabling profile.
    // synthesis translate_off
    generate
        if (!CLOCK_VALID) begin : g_clock_guard
            initial begin
                $fatal(1, "deepeye_trace_block_uart_50mhz_candidate: CLOCK_HZ must equal the50MHz source contract");
            end
        end else if (!BAUD_VALID) begin : g_baud_unset_guard
            initial begin
                $fatal(1, "deepeye_trace_block_uart_50mhz_candidate: BAUD not Root-approved");
            end
        end
    endgenerate
    // synthesis translate_on
endmodule
`default_nettype wire
