// Raw-block to TRACE payload source candidate. SOURCE_ONLY / UNEXECUTED.
// One encoder only: this module instantiates the existing raw-uint16
// deepeye_trace_payload_candidate. It never consumes encoded block-stream bytes.
//
// Proposed private semantic profile: TRACE-PAYLOAD-1US-PRIVATE-v2.
// Tick fields retain revision-1 layout but mean integer microseconds. The
// adapter changes only payload revision byte 0 from 1 to 2 on the output byte
// stream, so an unmodified revision-1 decoder rejects the block. A future
// decoder may interpret revision 2 only with an explicit Root receipt carrying
// the uint63 origin QPC, full acquisition QPC values, remainders and hashes.
// Profile authorization is an external gate and is not granted by this file.
module deepeye_trace_block_payload_1us_candidate (
    input logic clk, rst, cancel,
    input logic profile_v2_authorized,

    // One already associated, uniform raw block. blk_* is the selected raw
    // capture block; semantic flags are a Root-side classification, not a
    // reinterpretation of the opaque raw uint8 quality byte.
    input logic blk_valid, output logic blk_ready,
    input logic [7:0] blk_count,
    input logic [3:0] blk_e,
    input logic [31:0] blk_session,
    input logic [1:0] blk_channel,
    input logic [31:0] blk_first_index,
    input logic [15:0] blk_index_stride,
    input logic [63:0] blk_first_qpc_ns,
    input logic [63:0] blk_first_tick_us,
    input logic [9:0] blk_first_remainder_ns,
    input logic [63:0] blk_tick_stride_ns,
    input logic [15:0] blk_tick_stride_us,
    input logic [62:0] blk_origin_qpc_ns,
    input logic [63:0] blk_origin_tick_us,
    input logic [9:0] blk_origin_remainder_ns,
    input logic [7:0] blk_raw_quality,
    input logic blk_semantics_valid,
    input logic blk_valid_sample, blk_saturated, blk_held, blk_source_fault,
    input logic [63:0] blk_source_qpc_ns, blk_source_tick_us,
    input logic [9:0] blk_source_remainder_ns,

    output logic refusal_valid,
    output logic [3:0] refusal_code,

    input logic s_valid, output logic s_ready,
    input logic [15:0] s_data, input logic s_last,
    output logic meta_valid, input logic meta_ready,
    output logic [1:0] meta_error, output logic [5:0] meta_bytes,
    output logic [31:0] meta_tick,
    output logic p_valid, input logic p_ready,
    output logic [7:0] p_data, output logic p_last
);
    logic payload_cfg_valid, payload_cfg_ready;
    logic payload_s_ready;
    logic payload_meta_valid;
    logic [1:0] payload_meta_error;
    logic [5:0] payload_meta_bytes;
    logic [31:0] payload_meta_tick;
    logic payload_m_valid, payload_m_ready, payload_m_last;
    logic [7:0] payload_m_data;
    logic first_payload_byte_q, inflight_q, refusal_q;
    logic [3:0] refusal_code_q;

    logic cfg_time_ok, cfg_size_ok, cfg_block_ok;
    logic [64:0] origin_reconstructed, first_reconstructed, source_reconstructed;
    logic [64:0] qpc_end, tick_end, source_age_ticks;
    logic [63:0] first_tick_reconstructed;
    logic [6:0] metadata_bytes_calc;
    logic [7:0] raw_bytes_calc;
    logic held_requires_age;

    always_comb begin
        // Proposed PRIVATE Root-origin-relative unit. Original QPC and the
        // Root source clock origin are preserved; this is transport representation.
        origin_reconstructed = {2'd0,blk_origin_qpc_ns};
        first_reconstructed = {2'd0,blk_origin_qpc_ns}
                            + {1'b0,blk_first_tick_us} * 65'd1000
                            + {55'd0,blk_first_remainder_ns};
        source_reconstructed = {2'd0,blk_origin_qpc_ns}
                             + {1'b0,blk_source_tick_us} * 65'd1000
                             + {55'd0,blk_source_remainder_ns};
        qpc_end = {1'b0,blk_first_qpc_ns} + {1'b0,blk_tick_stride_ns}
                * ({57'd0,blk_count} - 65'd1);
        tick_end = {1'b0,blk_first_tick_us} + {49'd0,blk_tick_stride_us}
                 * ({57'd0,blk_count} - 65'd1);
        held_requires_age = blk_valid_sample && blk_held;
        source_age_ticks = {1'b0,blk_first_tick_us} - {1'b0,blk_source_tick_us};
        metadata_bytes_calc = 7'd21 + ((blk_count > 1) ? 7'd4 : 7'd0)
                            + (held_requires_age ? ((source_age_ticks > 65535) ? 7'd8 : 7'd2) : 7'd0);
        raw_bytes_calc = blk_count << 1;
        // This proposed short diagnostic view admits relative uint32 ticks.
        // It NEVER emits a truncated original QPC in the wire's 32-bit tick field.
        cfg_time_ok = (blk_origin_tick_us == 0) && (blk_origin_remainder_ns == 0)
                    && (blk_first_tick_us[63:32] == 0)
                    && (blk_first_remainder_ns <= 999)
                    && (blk_first_qpc_ns[63] == 0)
                    && (first_reconstructed[64:63] == 0)
                    && (first_reconstructed == {1'b0,blk_first_qpc_ns});
        if (blk_count == 1)
            cfg_time_ok = cfg_time_ok && (blk_index_stride == 0)
                        && (blk_tick_stride_us == 0) && (blk_tick_stride_ns == 0);
        else
            cfg_time_ok = cfg_time_ok && (blk_count >= 2) && (blk_count <= 3)
                        && (blk_index_stride != 0) && (blk_tick_stride_us != 0)
                        && (blk_tick_stride_ns == {48'd0,blk_tick_stride_us} * 64'd1000)
                        && (qpc_end[64:63] == 0) && (tick_end[64:32] == 0);
        if (!blk_valid_sample)
            cfg_time_ok = cfg_time_ok && !blk_saturated && !blk_held
                        && (blk_source_qpc_ns == 0) && (blk_source_tick_us == 0)
                        && (blk_source_remainder_ns == 0);
        else begin
            cfg_time_ok = cfg_time_ok && (blk_source_tick_us[63:32] == 0)
                        && (blk_source_remainder_ns <= 999)
                        && (source_reconstructed[64:63] == 0)
                        && (source_reconstructed == {1'b0,blk_source_qpc_ns});
            if (!blk_held)
                cfg_time_ok = cfg_time_ok && (blk_source_qpc_ns == blk_first_qpc_ns)
                            && (blk_source_tick_us == blk_first_tick_us)
                            && (blk_source_remainder_ns == blk_first_remainder_ns);
            else
                // Sub-us held gaps cannot be represented as a strict tick gap.
                cfg_time_ok = cfg_time_ok && (blk_source_qpc_ns < blk_first_qpc_ns)
                            && (blk_source_tick_us < blk_first_tick_us);
        end
        cfg_size_ok = (blk_count >= 1) && (blk_count <= 3)
                    && (metadata_bytes_calc <= 32)
                    && (raw_bytes_calc <= (8'd32 - metadata_bytes_calc));
        cfg_block_ok = profile_v2_authorized && blk_semantics_valid && !refusal_q
                     && ((blk_e==0)||(blk_e==1)||(blk_e==2)||(blk_e==4)||(blk_e==8))
                     && cfg_time_ok && cfg_size_ok && !rst && !cancel;

        payload_cfg_valid = blk_valid && blk_ready && cfg_block_ok;
        blk_ready = !rst && !cancel && !inflight_q &&
                    (payload_cfg_ready || !cfg_block_ok);
        s_ready = payload_s_ready;
        meta_valid = payload_meta_valid;
        meta_error = payload_meta_error;
        meta_bytes = payload_meta_bytes;
        meta_tick = payload_meta_tick;
        p_valid = payload_m_valid && !rst && !cancel;
        p_data = (first_payload_byte_q ? 8'h02 : payload_m_data);
        p_last = payload_m_last;
        payload_m_ready = p_ready && !rst && !cancel;
        refusal_valid = refusal_q;
        refusal_code = refusal_code_q;
    end

    deepeye_trace_payload_candidate payload_unit (
        .clk(clk), .rst(rst), .cancel(cancel),
        .cfg_valid(payload_cfg_valid), .cfg_ready(payload_cfg_ready),
        .cfg_count(blk_count), .cfg_e(blk_e), .cfg_session(blk_session),
        .cfg_channel(blk_channel), .cfg_first_index(blk_first_index),
        .cfg_first_tick(blk_first_tick_us),
        .cfg_index_stride(blk_index_stride), .cfg_tick_stride(blk_tick_stride_us),
        .cfg_valid_sample(blk_valid_sample), .cfg_saturated(blk_saturated),
        .cfg_held(blk_held), .cfg_source_fault(blk_source_fault),
        .cfg_source_tick(blk_valid_sample ? (blk_held ? blk_source_tick_us : blk_first_tick_us) : 64'd0),
        .s_valid(s_valid && !rst && !cancel), .s_ready(payload_s_ready),
        .s_data(s_data), .s_last(s_last),
        .meta_valid(payload_meta_valid), .meta_ready(meta_ready),
        .meta_error(payload_meta_error), .meta_bytes(payload_meta_bytes),
        .meta_tick(payload_meta_tick),
        .m_valid(payload_m_valid), .m_ready(payload_m_ready),
        .m_data(payload_m_data), .m_last(payload_m_last)
    );

    always_ff @(posedge clk) begin
        if (rst || cancel) begin
            first_payload_byte_q <= 1'b0;
            inflight_q <= 1'b0;
            refusal_q <= 1'b0;
            refusal_code_q <= 4'd0;
        end else begin
            refusal_q <= 1'b0;
            if (blk_valid && blk_ready) begin
                refusal_code_q <= 4'd0;
                if (!cfg_block_ok) begin
                    refusal_q <= 1'b1;
                    if (!profile_v2_authorized) refusal_code_q <= 4'd1;
                    else if (!blk_semantics_valid) refusal_code_q <= 4'd2;
                    else if (!cfg_size_ok) refusal_code_q <= 4'd3;
                    else if (!cfg_time_ok) refusal_code_q <= 4'd4;
                    else refusal_code_q <= 4'd5;
                end else begin
                    inflight_q <= 1'b1;
                end
            end
            if (payload_meta_valid && meta_ready) begin
                if (payload_meta_error == 0) begin
                    first_payload_byte_q <= 1'b1;
                end else begin
                    // A rejected block emits no bytes; release the block slot.
                    inflight_q <= 1'b0;
                    first_payload_byte_q <= 1'b0;
                end
            end
            if (p_valid && p_ready) begin
                if (p_last) begin
                    inflight_q <= 1'b0;
                    first_payload_byte_q <= 1'b0;
                end else if (first_payload_byte_q) begin
                    first_payload_byte_q <= 1'b0;
                end
            end
        end
    end
endmodule
