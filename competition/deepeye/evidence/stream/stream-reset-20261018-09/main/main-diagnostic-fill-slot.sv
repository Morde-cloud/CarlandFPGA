// deepeye_block_stream - two-slot ordered block-stream integration candidate.
//
// Work: B-STREAM-RESET-INTEGRATION-20261018-09-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// CANDIDATE-ONLY.  This is a digital integration candidate around the pinned
// deepeye_block_encoder.  It is not TRACE, a public ABI/register map, a BOOT or
// tick source, motion authority, B01/B03/system acceptance, or a board result.
//
// The wrapper owns exactly two 128 x 16 raw-block slots.  One slot may be in
// input-fill state while the older sealed slot is encoded/emitted by the
// unchanged core.  Slot allocation is bounded by level < 2, and a slot is not
// released until its success payload or error metadata reaches its terminal
// handshake.  The core and these two slots bound all candidate storage.

module deepeye_block_stream (
    input  logic        clk,
    input  logic        rst,
    input  logic        cancel,
    input  logic        cfg_valid,
    output logic        cfg_ready,
    input  logic [7:0]  cfg_count,
    input  logic [3:0]  cfg_e,
    input  logic [15:0] cfg_tag,
    input  logic        s_valid,
    output logic        s_ready,
    input  logic [15:0] s_data,
    input  logic        s_last,
    output logic        meta_valid,
    input  logic        meta_ready,
    output logic [15:0] meta_tag,
    output logic [1:0]  meta_error,
    output logic [7:0]  meta_count,
    output logic [3:0]  meta_e,
    output logic        meta_raw,
    output logic [3:0]  meta_k,
    output logic [11:0] meta_valid_bits,
    output logic [8:0]  meta_bytes,
    output logic        m_valid,
    input  logic        m_ready,
    output logic [7:0]  m_data,
    output logic        m_last,
    output logic [1:0]  level,
    output logic        filling,
    output logic [31:0] stat_cfg,
    output logic [31:0] stat_samples,
    output logic [31:0] stat_ok,
    output logic [31:0] stat_error,
    output logic [31:0] stat_aborted
);

    localparam logic [1:0] SLOT_FREE   = 2'd0;
    localparam logic [1:0] SLOT_FILL   = 2'd1;
    localparam logic [1:0] SLOT_SEALED = 2'd2;

    localparam logic [2:0] PHASE_IDLE = 3'd0;
    localparam logic [2:0] PHASE_FEED = 3'd1;
    localparam logic [2:0] PHASE_META = 3'd2;
    localparam logic [2:0] PHASE_OUT  = 3'd3;

    logic [15:0] slot_mem [0:1][0:127];
    logic [1:0]  slot_status [0:1];
    logic [1:0]  slot_error [0:1];
    logic [7:0]  slot_count [0:1];
    logic [3:0]  slot_e [0:1];
    logic [15:0] slot_tag [0:1];

    logic [1:0]  level_q;
    logic        filling_q;
    logic        head_q;
    logic        tail_q;
    logic [7:0]  fill_index_q;
    logic [7:0]  feed_index_q;
    logic [2:0]  phase_q;

    logic [31:0] stat_cfg_q;
    logic [31:0] stat_samples_q;
    logic [31:0] stat_ok_q;
    logic [31:0] stat_error_q;
    logic [31:0] stat_aborted_q;

    logic        core_cfg_valid;
    logic        core_cfg_ready;
    logic [7:0]  core_cfg_count;
    logic [3:0]  core_cfg_e;
    logic        core_s_valid;
    logic        core_s_ready;
    logic [15:0] core_s_data;
    logic        core_s_last;
    logic        core_meta_valid;
    logic        core_meta_ready;
    logic [1:0]  core_meta_error;
    logic [7:0]  core_meta_count;
    logic [3:0]  core_meta_e;
    logic        core_meta_raw;
    logic [3:0]  core_meta_k;
    logic [11:0] core_meta_valid_bits;
    logic [8:0]  core_meta_bytes;
    logic        core_m_valid;
    logic        core_m_ready;
    logic [7:0]  core_m_data;
    logic        core_m_last;

    logic        alloc_fire;
    logic        sample_fire;
    logic        core_cfg_fire;
    logic        core_sample_fire;
    logic        core_meta_fire;
    logic        core_error_retire_fire;
    logic        error_retire_fire;
    logic        ok_retire_fire;
    logic        retire_fire;

    integer slot_index;

    function automatic logic cfg_e_legal(input logic [3:0] value);
        cfg_e_legal = (value == 4'd0) || (value == 4'd1) ||
                      (value == 4'd2) || (value == 4'd4) ||
                      (value == 4'd8);
    endfunction

    function automatic logic [31:0] sat_inc(input logic [31:0] value);
        sat_inc = (value == 32'hFFFF_FFFF) ? value : value + 32'd1;
    endfunction

    function automatic logic [31:0] sat_add(input logic [31:0] value,
                                             input logic [31:0] amount);
        if (amount > (32'hFFFF_FFFF - value)) begin
            sat_add = 32'hFFFF_FFFF;
        end else begin
            sat_add = value + amount;
        end
    endfunction

    assign cfg_ready = !rst && !cancel && !filling_q && (level_q < 2'd2);
    assign s_ready   = !rst && !cancel && filling_q;

    assign level   = level_q;
    assign filling = filling_q;
    assign stat_cfg     = stat_cfg_q;
    assign stat_samples = stat_samples_q;
    assign stat_ok      = stat_ok_q;
    assign stat_error   = stat_error_q;
    assign stat_aborted = stat_aborted_q;

    assign core_cfg_valid = !rst && !cancel && (phase_q == PHASE_IDLE) &&
                            (level_q != 2'd0) &&
                            (slot_status[head_q] == SLOT_SEALED) &&
                            (slot_error[head_q] == 2'd0);
    assign core_cfg_count = slot_count[head_q];
    assign core_cfg_e     = slot_e[head_q];
    assign core_s_valid   = !rst && !cancel && (phase_q == PHASE_FEED);
    assign core_s_data    = slot_mem[head_q][feed_index_q[6:0]];
    assign core_s_last    = (feed_index_q == (slot_count[head_q] - 8'd1));
    assign core_meta_ready = !rst && !cancel && (phase_q == PHASE_META) &&
                             meta_ready;
    assign core_m_ready    = !rst && !cancel && (phase_q == PHASE_OUT) &&
                             m_ready;

    assign alloc_fire = cfg_valid && cfg_ready;
    assign sample_fire = s_valid && s_ready;
    assign core_cfg_fire = core_cfg_valid && core_cfg_ready;
    assign core_sample_fire = core_s_valid && core_s_ready;
    assign core_meta_fire = core_meta_valid && meta_ready &&
                            (phase_q == PHASE_META);
    assign core_error_retire_fire = core_meta_fire &&
                                    (core_meta_error != 2'd0);
    assign error_retire_fire = meta_ready && (phase_q == PHASE_IDLE) &&
                               (level_q != 2'd0) &&
                               (slot_status[head_q] == SLOT_SEALED) &&
                               (slot_error[head_q] != 2'd0);
    assign ok_retire_fire = core_m_valid && m_ready && core_m_last &&
                            (phase_q == PHASE_OUT);
    assign retire_fire = error_retire_fire || core_error_retire_fire ||
                         ok_retire_fire;

    always @* begin
        meta_valid      = 1'b0;
        meta_tag        = 16'd0;
        meta_error      = 2'd0;
        meta_count      = 8'd0;
        meta_e          = 4'd0;
        meta_raw        = 1'b0;
        meta_k          = 4'd0;
        meta_valid_bits = 12'd0;
        meta_bytes      = 9'd0;
        m_valid         = 1'b0;
        m_data          = 8'd0;
        m_last          = 1'b0;

        if (!rst && !cancel) begin
            if ((phase_q == PHASE_IDLE) && (level_q != 2'd0) &&
                (slot_status[head_q] == SLOT_SEALED) &&
                (slot_error[head_q] != 2'd0)) begin
                meta_valid      = 1'b1;
                meta_tag        = slot_tag[head_q];
                meta_error      = slot_error[head_q];
                meta_count      = 8'd0;
                meta_e          = 4'd0;
                meta_raw        = 1'b1;
                meta_k          = 4'd0;
                meta_valid_bits = 12'd0;
                meta_bytes      = 9'd0;
            end else if ((phase_q == PHASE_META) && core_meta_valid) begin
                meta_valid = 1'b1;
                meta_tag   = slot_tag[head_q];
                if (core_meta_error != 2'd0) begin
                    meta_error      = core_meta_error;
                    meta_count      = 8'd0;
                    meta_e          = 4'd0;
                    meta_raw        = 1'b1;
                    meta_k          = 4'd0;
                    meta_valid_bits = 12'd0;
                    meta_bytes      = 9'd0;
                end else begin
                    meta_error      = 2'd0;
                    meta_count      = core_meta_count;
                    meta_e          = core_meta_e;
                    meta_raw        = core_meta_raw;
                    meta_k          = core_meta_k;
                    meta_valid_bits = core_meta_valid_bits;
                    meta_bytes      = core_meta_bytes;
                end
            end else if ((phase_q == PHASE_OUT) && core_m_valid) begin
                m_valid = 1'b1;
                m_data  = core_m_data;
                m_last  = core_m_last;
            end
        end
    end

    deepeye_block_encoder core (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .cfg_valid(core_cfg_valid),
        .cfg_ready(core_cfg_ready),
        .cfg_count(core_cfg_count),
        .cfg_e(core_cfg_e),
        .s_valid(core_s_valid),
        .s_ready(core_s_ready),
        .s_data(core_s_data),
        .s_last(core_s_last),
        .meta_valid(core_meta_valid),
        .meta_ready(core_meta_ready),
        .meta_error(core_meta_error),
        .meta_count(core_meta_count),
        .meta_e(core_meta_e),
        .meta_raw(core_meta_raw),
        .meta_k(core_meta_k),
        .meta_valid_bits(core_meta_valid_bits),
        .meta_bytes(core_meta_bytes),
        .m_valid(core_m_valid),
        .m_ready(core_m_ready),
        .m_data(core_m_data),
        .m_last(core_m_last)
    );

    always @(posedge clk) begin
        if (rst) begin
            level_q      <= 2'd0;
            filling_q    <= 1'b0;
            head_q       <= 1'b0;
            tail_q       <= 1'b0;
            fill_index_q <= 8'd0;
            feed_index_q <= 8'd0;
            phase_q      <= PHASE_IDLE;
            stat_cfg_q     <= 32'd0;
            stat_samples_q <= 32'd0;
            stat_ok_q      <= 32'd0;
            stat_error_q   <= 32'd0;
            stat_aborted_q <= 32'd0;
            for (slot_index = 0; slot_index < 2; slot_index = slot_index + 1) begin
                slot_status[slot_index] <= SLOT_FREE;
                slot_error[slot_index]  <= 2'd0;
                slot_count[slot_index]  <= 8'd0;
                slot_e[slot_index]      <= 4'd0;
                slot_tag[slot_index]    <= 16'd0;
            end
        end else if (cancel) begin
            level_q      <= 2'd0;
            filling_q    <= 1'b0;
            head_q       <= 1'b0;
            tail_q       <= 1'b0;
            fill_index_q <= 8'd0;
            feed_index_q <= 8'd0;
            phase_q      <= PHASE_IDLE;
            stat_aborted_q <= sat_add(stat_aborted_q, {30'd0, level_q});
            for (slot_index = 0; slot_index < 2; slot_index = slot_index + 1) begin
                slot_status[slot_index] <= SLOT_FREE;
                slot_error[slot_index]  <= 2'd0;
            end
        end else begin
            if (alloc_fire) begin
                slot_count[tail_q] <= cfg_count;
                slot_e[tail_q]     <= cfg_e;
                slot_tag[tail_q]   <= cfg_tag;
                if ((cfg_count == 8'd0) || (cfg_count > 8'd128) ||
                    !cfg_e_legal(cfg_e)) begin
                    slot_status[tail_q] <= SLOT_SEALED;
                    slot_error[tail_q]  <= 2'd1;
                    filling_q           <= 1'b0;
                end else begin
                    slot_status[tail_q] <= SLOT_FILL;
                    slot_error[tail_q]  <= 2'd0;
                    filling_q           <= 1'b1;
                end
            end else if (sample_fire) begin
                slot_mem[~tail_q][fill_index_q[6:0]] <= s_data;
                if (s_last != (fill_index_q == (slot_count[~tail_q] - 8'd1))) begin
                    slot_status[~tail_q] <= SLOT_SEALED;
                    slot_error[~tail_q]  <= 2'd2;
                    filling_q           <= 1'b0;
                end else if (s_last) begin
                    slot_status[~tail_q] <= SLOT_SEALED;
                    slot_error[~tail_q]  <= 2'd0;
                    filling_q           <= 1'b0;
                end else begin
                    fill_index_q <= fill_index_q + 8'd1;
                end
            end

            if (alloc_fire) begin
                fill_index_q <= 8'd0;
            end

            if (core_cfg_fire) begin
                feed_index_q <= 8'd0;
                phase_q      <= PHASE_FEED;
            end else if (core_sample_fire) begin
                if (core_s_last) begin
                    phase_q <= PHASE_META;
                end else begin
                    feed_index_q <= feed_index_q + 8'd1;
                end
            end else if (core_meta_fire) begin
                if (core_meta_error != 2'd0) begin
                    phase_q <= PHASE_IDLE;
                end else begin
                    phase_q <= PHASE_OUT;
                end
            end else if (ok_retire_fire) begin
                phase_q <= PHASE_IDLE;
            end

            if (alloc_fire && retire_fire) begin
                level_q <= level_q;
            end else if (alloc_fire) begin
                level_q <= level_q + 2'd1;
            end else if (retire_fire) begin
                level_q <= level_q - 2'd1;
            end else begin
                level_q <= level_q;
            end

            if (retire_fire) begin
                head_q <= ~head_q;
            end

            if (alloc_fire) begin
                tail_q <= ~tail_q;
                stat_cfg_q <= sat_inc(stat_cfg_q);
            end

            if (sample_fire) begin
                stat_samples_q <= sat_inc(stat_samples_q);
            end

            if (ok_retire_fire) begin
                stat_ok_q <= sat_inc(stat_ok_q);
            end

            if (core_error_retire_fire || error_retire_fire) begin
                stat_error_q <= sat_inc(stat_error_q);
            end
        end
    end

endmodule
