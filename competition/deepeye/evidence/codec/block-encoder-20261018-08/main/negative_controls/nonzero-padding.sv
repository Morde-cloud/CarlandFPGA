// deepeye_block_encoder - bounded one-block uint16 inner-codec encoder candidate.
//
// Work: B-BLOCK-ENCODER-RTL-20261018-08-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design 1011259415a0916054eb580687612580bc1e5f09.
//
// CANDIDATE-ONLY.  This module encodes exactly one block of 1..128 uint16
// samples with the pinned integer inner-codec candidate rules.  It is NOT the
// TRACE layout, defines no public ABI/payload offset/tick/mask/block id and
// carries no synthesis, implementation, board or acceptance claim.
//
// Algorithm (matches golden/codec/codec_reference.py):
//   * D = 2E+1 for E in {0,1,2,4,8}; q = floor((x-p+E)/D) with true
//     mathematical floor for negative nonmultiples; y = clamp(p+q*D);
//     p = y; first sample is the exact absolute anchor.
//   * z = 2q if q >= 0 else -2q-1.
//   * Every k in 0..15 is considered; k is legal only if every z>>k <= 31.
//     Rice body bits = sum(z>>k) + (n-1)*(k+1).  Smallest body wins, lowest k
//     wins ties.  RAW (original uint16 words) wins when no k is legal or when
//     the best Rice body is >= 16*(n-1); RAW also wins the n=1 tie.
//   * Payload is MSB-first: 16-bit anchor, then either Rice (unary quotient
//     zeros + one terminator + k remainder bits) or 16-bit original words.
//     Unused low bits of the final byte are zero.  No escape code exists.
//
// Storage and arithmetic widths (all finite, no unbounded unary):
//   x_mem   128 x 16  original samples (2048 bits)
//   z_mem   127 x 17  ZigZag residuals, index i-1 for sample i (2159 bits)
//   byte_mem 256 x 8  packed payload bytes (2048 bits)
//   divider  magnitude 17 bits, remainder 6 bits, quotient 17 bits,
//            bit counter 5 bits; fixed 17 shift/subtract steps.
//   selection accumulator 13 bits, overhead 12 bits, total 13 bits.
//   bit writer value 17 bits, field length 6 bits, fill 3 bits, total 12 bits.
//   byte index/count 9 bits (0..256).  Maximum payload is 256 bytes because a
//   chosen Rice body is strictly below 16*(n-1) <= 2032 bits.
//
// Processing bound from the last accepted sample to meta_valid (no reset or
// cancel): one 18-cycle divider finalization, 16*(n-1)+16 selection cycles
// (<=2048 for n=128), plus a few fixed cycles; < 2100 clocks at n=128, well
// below the 20000-clock requirement.  Payload generation is a separate
// post-metadata phase and is not part of that bound.
//
// Reset/cancel are synchronous active-high, sampled at posedge, take priority
// over every handshake and flush all control state.  Ready/valid outputs are
// gated low while either is asserted.  RAM contents are not cleared; every
// location read by a transaction is first written by that same transaction.
//
// This file uses only synthesizable RTL: no initial blocks, no delays, no
// file/DPI I/O, no force and no simulation-only constructs.

module deepeye_block_encoder (
    input  logic        clk,
    input  logic        rst,
    input  logic        cancel,
    input  logic        cfg_valid,
    output logic        cfg_ready,
    input  logic [7:0]  cfg_count,
    input  logic [3:0]  cfg_e,
    input  logic        s_valid,
    output logic        s_ready,
    input  logic [15:0] s_data,
    input  logic        s_last,
    output logic        meta_valid,
    input  logic        meta_ready,
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
    output logic        m_last
);

    localparam [3:0] ST_IDLE    = 4'd0;
    localparam [3:0] ST_LOAD    = 4'd1;
    localparam [3:0] ST_DIV     = 4'd2;
    localparam [3:0] ST_DIV_FIN = 4'd3;
    localparam [3:0] ST_SEL_INIT= 4'd4;
    localparam [3:0] ST_SEL_SCAN= 4'd5;
    localparam [3:0] ST_SEL_NEXT= 4'd6;
    localparam [3:0] ST_META    = 4'd7;
    localparam [3:0] ST_GEN     = 4'd8;
    localparam [3:0] ST_GEN_DONE= 4'd9;
    localparam [3:0] ST_OUT     = 4'd10;

    logic [3:0] state;

    logic [15:0] x_mem [0:127];
    logic [16:0] z_mem [0:126];
    logic [7:0]  byte_mem [0:255];

    logic [7:0]  cfg_count_q;
    logic [3:0]  cfg_e_q;
    logic [7:0]  count_m1;
    logic [15:0] p_q;

    logic [7:0]  load_idx;
    logic [7:0]  cur_idx;
    logic        cur_last;

    logic        div_neg;
    logic [16:0] div_mag;
    logic [5:0]  div_rem;
    logic [16:0] div_quot;
    logic [4:0]  div_bit;

    logic [3:0]  sel_k;
    logic [7:0]  sel_i;
    logic [12:0] sel_acc;
    logic        sel_ok;
    logic [11:0] sel_overhead;
    logic        best_valid;
    logic [3:0]  best_k;
    logic [12:0] best_bits;

    logic        final_raw;
    logic [3:0]  final_k;
    logic [16:0] final_mask;
    logic [12:0] final_body_bits;

    logic [7:0]  gen_si;
    logic [1:0]  gen_sub;
    logic [31:0] wr_val;
    logic [5:0]  wr_left;
    logic [2:0]  fill;
    logic [7:0]  cur_byte;
    logic [8:0]  byte_wr;
    logic [11:0] bits_total;

    logic [8:0]  out_idx;

    // Combinational datapath helpers.
    logic [4:0]  d_calc;
    logic signed [17:0] n_signed;
    logic [17:0] q_bits;
    logic [17:0] q_abs;
    logic [17:0] z_calc;
    logic signed [23:0] prod;
    logic signed [24:0] y_ext;
    logic [15:0] y_clamped;
    logic [12:0] raw_bits_calc;
    logic [12:0] sel_total_calc;
    logic        sel_take_raw;
    logic [12:0] sel_body_bits;
    logic [3:0]  sel_k_out;
    logic [11:0] sel_valid_bits;
    logic [8:0]  sel_meta_bytes;
    logic [16:0] qz_sel;
    logic [16:0] qz_gen;
    logic [5:0]  shift_calc;
    logic        bit_calc;

    assign cfg_ready  = (state == ST_IDLE) && !rst && !cancel;
    assign s_ready    = (state == ST_LOAD) && !rst && !cancel;
    assign meta_valid = (state == ST_META) && !rst && !cancel;
    assign m_valid    = (state == ST_OUT)  && !rst && !cancel;

    assign m_data = byte_mem[out_idx[7:0]];
    assign m_last = (out_idx == (meta_bytes - 9'd1));

    always @* begin
        d_calc = {cfg_e_q, 1'b0} + 5'd1;
        n_signed = $signed({2'b00, s_data}) - $signed({2'b00, p_q})
                   + $signed({14'b0, cfg_e_q});

        if (!div_neg) begin
            q_bits = {1'b0, div_quot};
        end else if (div_rem == 6'd0) begin
            q_bits = 18'd0 - {1'b0, div_quot};
        end else begin
            q_bits = 18'd0 - ({1'b0, div_quot} + 18'd1);
        end
        q_abs = 18'd0 - q_bits;
        if (!q_bits[17]) begin
            z_calc = {q_bits[16:0], 1'b0};
        end else begin
            z_calc = (q_abs << 1) - 18'd1;
        end
        prod = $signed(q_bits) * $signed({1'b0, d_calc});
        y_ext = $signed({9'b0, p_q}) + prod;
        if (y_ext < 0) begin
            y_clamped = 16'd0;
        end else if (y_ext > 25'sd65535) begin
            y_clamped = 16'hFFFF;
        end else begin
            y_clamped = y_ext[15:0];
        end

        raw_bits_calc = ({5'b0, cfg_count_q} - 13'd1) << 4;
        sel_total_calc = sel_acc + {1'b0, sel_overhead};
        sel_take_raw = (!best_valid) || (best_bits >= raw_bits_calc);
        sel_body_bits = sel_take_raw ? raw_bits_calc : best_bits;
        sel_k_out = sel_take_raw ? 4'd0 : best_k;
        sel_valid_bits = 12'd16 + sel_body_bits;
        sel_meta_bytes = (sel_valid_bits + 12'd7) >> 3;

        qz_sel = z_mem[sel_i[6:0]] >> sel_k;
        if (gen_si != 8'd0) begin
            qz_gen = z_mem[gen_si[6:0] - 1'b1] >> final_k;
        end else begin
            qz_gen = 17'd0;
        end
    end

    always @(posedge clk) begin
        if (rst || cancel) begin
            state           <= ST_IDLE;
            cfg_count_q     <= 8'd0;
            cfg_e_q         <= 4'd0;
            count_m1        <= 8'd0;
            p_q             <= 16'd0;
            load_idx        <= 8'd0;
            cur_idx         <= 8'd0;
            cur_last        <= 1'b0;
            div_neg         <= 1'b0;
            div_mag         <= 17'd0;
            div_rem         <= 6'd0;
            div_quot        <= 17'd0;
            div_bit         <= 5'd0;
            sel_k           <= 4'd0;
            sel_i           <= 8'd0;
            sel_acc         <= 13'd0;
            sel_ok          <= 1'b0;
            sel_overhead    <= 12'd0;
            best_valid      <= 1'b0;
            best_k          <= 4'd0;
            best_bits       <= 13'd0;
            final_raw       <= 1'b0;
            final_k         <= 4'd0;
            final_mask      <= 17'd0;
            final_body_bits <= 13'd0;
            meta_error      <= 2'd0;
            meta_count      <= 8'd0;
            meta_e          <= 4'd0;
            meta_raw        <= 1'b0;
            meta_k          <= 4'd0;
            meta_valid_bits <= 12'd0;
            meta_bytes      <= 9'd0;
            gen_si          <= 8'd0;
            gen_sub         <= 2'd0;
            wr_val          <= 17'd0;
            wr_left         <= 6'd0;
            fill            <= 3'd0;
            cur_byte        <= 8'd0;
            byte_wr         <= 9'd0;
            bits_total      <= 12'd0;
            out_idx         <= 9'd0;
        end else begin
            case (state)
                ST_IDLE: begin
                    if (cfg_valid) begin
                        if ((cfg_count == 8'd0) || (cfg_count > 8'd128) ||
                            !((cfg_e == 4'd0) || (cfg_e == 4'd1) ||
                              (cfg_e == 4'd2) || (cfg_e == 4'd4) ||
                              (cfg_e == 4'd8))) begin
                            meta_error      <= 2'd1;
                            meta_count      <= 8'd0;
                            meta_e          <= 4'd0;
                            meta_raw        <= 1'b1;
                            meta_k          <= 4'd0;
                            meta_valid_bits <= 12'd0;
                            meta_bytes      <= 9'd0;
                            state           <= ST_META;
                        end else begin
                            cfg_count_q <= cfg_count;
                            cfg_e_q     <= cfg_e;
                            count_m1    <= cfg_count - 8'd1;
                            load_idx    <= 8'd0;
                            p_q         <= 16'd0;
                            state       <= ST_LOAD;
                        end
                    end
                end

                ST_LOAD: begin
                    if (s_valid) begin
                        if (s_last != (load_idx == count_m1)) begin
                            meta_error      <= 2'd2;
                            meta_count      <= 8'd0;
                            meta_e          <= 4'd0;
                            meta_raw        <= 1'b1;
                            meta_k          <= 4'd0;
                            meta_valid_bits <= 12'd0;
                            meta_bytes      <= 9'd0;
                            state           <= ST_META;
                        end else if (load_idx == 8'd0) begin
                            x_mem[7'd0] <= s_data;
                            p_q         <= s_data;
                            if (count_m1 == 8'd0) begin
                                final_raw       <= 1'b1;
                                final_k         <= 4'd0;
                                final_mask      <= 17'd0;
                                final_body_bits <= 13'd0;
                                meta_error      <= 2'd0;
                                meta_count      <= 8'd1;
                                meta_e          <= cfg_e_q;
                                meta_raw        <= 1'b1;
                                meta_k          <= 4'd0;
                                meta_valid_bits <= 12'd16;
                                meta_bytes      <= 9'd2;
                                state           <= ST_META;
                            end else begin
                                load_idx <= 8'd1;
                            end
                        end else begin
                            x_mem[load_idx[6:0]] <= s_data;
                            cur_idx  <= load_idx;
                            cur_last <= s_last;
                            div_neg  <= n_signed[17];
                            div_mag  <= n_signed[17] ? (17'd0 - n_signed[16:0])
                                                     : n_signed[16:0];
                            div_rem  <= 6'd0;
                            div_quot <= 17'd0;
                            div_bit  <= 5'd16;
                            state    <= ST_DIV;
                        end
                    end
                end

                ST_DIV: begin
                    shift_calc = {div_rem[4:0], div_mag[div_bit]};
                    if (shift_calc >= {1'b0, d_calc}) begin
                        div_rem  <= shift_calc - {1'b0, d_calc};
                        div_quot <= {div_quot[15:0], 1'b1};
                    end else begin
                        div_rem  <= shift_calc;
                        div_quot <= {div_quot[15:0], 1'b0};
                    end
                    if (div_bit == 5'd0) begin
                        state <= ST_DIV_FIN;
                    end else begin
                        div_bit <= div_bit - 5'd1;
                    end
                end

                ST_DIV_FIN: begin
                    z_mem[cur_idx[6:0] - 1'b1] <= z_calc[16:0];
                    p_q <= y_clamped;
                    if (cur_last) begin
                        state <= ST_SEL_INIT;
                    end else begin
                        load_idx <= cur_idx + 8'd1;
                        state    <= ST_LOAD;
                    end
                end

                ST_SEL_INIT: begin
                    sel_k        <= 4'd0;
                    sel_i        <= 8'd0;
                    sel_acc      <= 13'd0;
                    sel_ok       <= 1'b1;
                    sel_overhead <= {4'b0, count_m1};
                    best_valid   <= 1'b0;
                    best_k       <= 4'd0;
                    best_bits    <= 13'd0;
                    state        <= ST_SEL_SCAN;
                end

                ST_SEL_SCAN: begin
                    if (sel_i < count_m1) begin
                        if (qz_sel > 17'd31) begin
                            sel_ok <= 1'b0;
                            state  <= ST_SEL_NEXT;
                        end else begin
                            sel_acc <= sel_acc + {8'b0, qz_sel[4:0]};
                            sel_i   <= sel_i + 8'd1;
                        end
                    end else begin
                        if (sel_ok && ((!best_valid) || (sel_total_calc < best_bits))) begin
                            best_valid <= 1'b1;
                            best_k     <= sel_k;
                            best_bits  <= sel_total_calc;
                        end
                        state <= ST_SEL_NEXT;
                    end
                end

                ST_SEL_NEXT: begin
                    if (sel_k == 4'd15) begin
                        meta_error      <= 2'd0;
                        meta_count      <= cfg_count_q;
                        meta_e          <= cfg_e_q;
                        meta_raw        <= sel_take_raw;
                        meta_k          <= sel_k_out;
                        meta_valid_bits <= sel_valid_bits;
                        meta_bytes      <= sel_meta_bytes;
                        final_raw       <= sel_take_raw;
                        final_k         <= sel_k_out;
                        final_mask      <= (17'd1 << sel_k_out) - 17'd1;
                        final_body_bits <= sel_body_bits;
                        state           <= ST_META;
                    end else begin
                        sel_k        <= sel_k + 4'd1;
                        sel_i        <= 8'd0;
                        sel_acc      <= 13'd0;
                        sel_ok       <= 1'b1;
                        sel_overhead <= sel_overhead + {4'b0, count_m1};
                        state        <= ST_SEL_SCAN;
                    end
                end

                ST_META: begin
                    if (meta_ready) begin
                        if (meta_error != 2'd0) begin
                            state <= ST_IDLE;
                        end else begin
                            gen_si     <= 8'd0;
                            gen_sub    <= 2'd0;
                            wr_val     <= 17'd0;
                            wr_left    <= 6'd0;
                            fill       <= 3'd0;
                            cur_byte   <= 8'd0;
                            byte_wr    <= 9'd0;
                            bits_total <= 12'd0;
                            state      <= ST_GEN;
                        end
                    end
                end

                ST_GEN: begin
                    if (wr_left != 6'd0) begin
                        bit_calc = wr_val[wr_left - 1'b1];
                        wr_left  <= wr_left - 6'd1;
                        bits_total <= bits_total + 12'd1;
                        if (fill == 3'd7) begin
                            byte_mem[byte_wr[7:0]] <= {cur_byte[6:0], bit_calc};
                            byte_wr  <= byte_wr + 9'd1;
                            fill     <= 3'd0;
                            cur_byte <= 8'd0;
                        end else begin
                            cur_byte <= {cur_byte[6:0], bit_calc};
                            fill     <= fill + 3'd1;
                        end
                    end else if (gen_si == 8'd0) begin
                        wr_val  <= {1'b0, x_mem[7'd0]};
                        wr_left <= 6'd16;
                        gen_si  <= 8'd1;
                        gen_sub <= 2'd0;
                    end else if (gen_si >= cfg_count_q) begin
                        state <= ST_GEN_DONE;
                    end else if (final_raw) begin
                        wr_val  <= {1'b0, x_mem[gen_si[6:0]]};
                        wr_left <= 6'd16;
                        gen_si  <= gen_si + 8'd1;
                    end else begin
                        case (gen_sub)
                            2'd0: begin
                                if (qz_gen == 17'd0) begin
                                    wr_val  <= 17'd1;
                                    wr_left <= 6'd1;
                                    gen_sub <= 2'd2;
                                end else begin
                                    wr_val  <= 17'd0;
                                    wr_left <= {1'b0, qz_gen[4:0]};
                                    gen_sub <= 2'd1;
                                end
                            end
                            2'd1: begin
                                wr_val  <= 17'd1;
                                wr_left <= 6'd1;
                                gen_sub <= 2'd2;
                            end
                            default: begin
                                if (final_k == 4'd0) begin
                                    gen_si  <= gen_si + 8'd1;
                                    gen_sub <= 2'd0;
                                end else begin
                                    wr_val  <= z_mem[gen_si[6:0] - 1'b1] & final_mask;
                                    wr_left <= {2'b0, final_k};
                                    gen_si  <= gen_si + 8'd1;
                                    gen_sub <= 2'd0;
                                end
                            end
                        endcase
                    end
                end

                ST_GEN_DONE: begin
                    if (fill != 3'd0) begin
                        byte_mem[byte_wr[7:0]] <= (cur_byte << (8 - fill)) | 8'd1;
                        byte_wr <= byte_wr + 9'd1;
                        fill    <= 3'd0;
                    end
                    out_idx <= 9'd0;
                    state   <= ST_OUT;
                end

                ST_OUT: begin
                    if (m_ready) begin
                        if (out_idx == (meta_bytes - 9'd1)) begin
                            state <= ST_IDLE;
                        end else begin
                            out_idx <= out_idx + 9'd1;
                        end
                    end
                end

                default: begin
                    state <= ST_IDLE;
                end
            endcase
        end
    end

endmodule
