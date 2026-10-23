// deepeye_wire_parser - bounded version-3 byte-frame syntax candidate parser.
//
// Work: B-WIRE-PARSER-20261024-29-v1
// Repair: B-WIRE-PARSER-STATUS-REPAIR-20261024-29-r1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-WIRE-PARSER-20261024-29
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// out_valid denotes only a syntactically well-formed byte candidate. It does
// not establish semantic acceptance, profile/source/BOOT/TTL validity,
// authentication, replay protection, liveness, or motion authority.

`default_nettype none

module deepeye_wire_parser #(
    parameter integer STAT_W = 32,
    localparam integer STAT_W_SAFE = (STAT_W < 2) ? 2 : (STAT_W > 32) ? 32 : STAT_W
) (
    input  wire  logic        clk,
    input  wire  logic        rst,
    input  wire  logic        cancel,

    input  wire  logic        in_valid,
    output wire  logic        in_ready,
    input  wire  logic [7:0]  in_data,

    output wire  logic        out_valid,
    input  wire  logic        out_ready,
    output logic [7:0]        out_type,
    output logic [7:0]        out_epoch,
    output logic [15:0]       out_seq,
    output logic [31:0]       out_tick,
    output logic [5:0]        out_len,
    output wire  logic [255:0] out_payload,

    output wire  logic        receiving,
    output wire  logic        error_event,
    output wire  logic [1:0]  error_code,

    output logic [STAT_W_SAFE-1:0] stat_bytes,
    output logic [STAT_W_SAFE-1:0] stat_frames,
    output logic [STAT_W_SAFE-1:0] stat_retired,
    output logic [STAT_W_SAFE-1:0] stat_version,
    output logic [STAT_W_SAFE-1:0] stat_length,
    output logic [STAT_W_SAFE-1:0] stat_crc,
    output logic [STAT_W_SAFE-1:0] stat_aborted
);

    initial begin
        if (STAT_W < 2 || STAT_W > 32) begin
            $fatal(1, "deepeye_wire_parser: STAT_W out of range");
        end
    end

    localparam logic [7:0] MAGIC_A5 = 8'hA5;
    localparam logic [7:0] MAGIC_5A = 8'h5A;
    localparam logic [7:0] WIRE_VERSION = 8'h03;

    typedef enum logic [3:0] {
        S_SEARCH  = 4'd0,
        S_WAIT_5A = 4'd1,
        S_VERSION = 4'd2,
        S_TYPE    = 4'd3,
        S_LENGTH  = 4'd4,
        S_EPOCH   = 4'd5,
        S_SEQ_LO  = 4'd6,
        S_SEQ_HI  = 4'd7,
        S_TICK0   = 4'd8,
        S_TICK1   = 4'd9,
        S_TICK2   = 4'd10,
        S_TICK3   = 4'd11,
        S_PAYLOAD = 4'd12,
        S_CRC_LO  = 4'd13,
        S_CRC_HI  = 4'd14
    } parser_state_t;

    parser_state_t state_q;
    logic          completed_slot_q;

    logic [7:0]    payload_mem [0:31];
    logic [5:0]    payload_index_q;

    logic [15:0]   crc_q;
    logic [7:0]    crc_lo_q;
    logic [15:0]   crc_next;

    logic          error_event_q;
    logic [1:0]    error_code_q;

    function automatic logic [STAT_W_SAFE-1:0] saturating_inc(
        input logic [STAT_W_SAFE-1:0] value
    );
        begin
            if (&value) begin
                saturating_inc = value;
            end else begin
                saturating_inc = value + {{(STAT_W_SAFE-1){1'b0}}, 1'b1};
            end
        end
    endfunction

    task automatic clear_payload;
        integer clear_index;
        begin
            for (clear_index = 0; clear_index < 32; clear_index = clear_index + 1) begin
                payload_mem[clear_index] <= 8'h00;
            end
        end
    endtask

    task automatic clear_candidate_controls;
        begin
            payload_index_q <= 6'd0;
            crc_q          <= 16'hFFFF;
            crc_lo_q       <= 8'h00;
            out_type       <= 8'h00;
            out_epoch      <= 8'h00;
            out_seq        <= 16'h0000;
            out_tick       <= 32'h0000_0000;
            out_len        <= 6'd0;
            clear_payload();
        end
    endtask

    deepeye_crc16_byte u_crc16_byte (
        .crc_in(crc_q),
        .data_in(in_data),
        .crc_out(crc_next)
    );

    genvar payload_byte;
    generate
        for (payload_byte = 0; payload_byte < 32; payload_byte = payload_byte + 1) begin : g_out_payload
            assign out_payload[8*payload_byte +: 8] = payload_mem[payload_byte];
        end
    endgenerate

    assign in_ready = !rst && !cancel && !completed_slot_q;
    assign out_valid = completed_slot_q && !rst && !cancel;
    assign receiving = !completed_slot_q && (state_q != S_SEARCH);
    assign error_event = error_event_q;
    assign error_code = error_event_q ? error_code_q : 2'b00;

    logic accept;
    assign accept = in_valid && in_ready;

    always_ff @(posedge clk) begin
        if (rst) begin
            state_q          <= S_SEARCH;
            completed_slot_q <= 1'b0;
            payload_index_q  <= 6'd0;
            crc_q            <= 16'hFFFF;
            crc_lo_q         <= 8'h00;
            error_event_q    <= 1'b0;
            error_code_q     <= 2'b00;
            out_type         <= 8'h00;
            out_epoch        <= 8'h00;
            out_seq          <= 16'h0000;
            out_tick         <= 32'h0000_0000;
            out_len          <= 6'd0;
            stat_bytes       <= '0;
            stat_frames      <= '0;
            stat_retired     <= '0;
            stat_version     <= '0;
            stat_length      <= '0;
            stat_crc         <= '0;
            stat_aborted     <= '0;
            clear_payload();
        end else if (cancel) begin
            state_q          <= S_SEARCH;
            completed_slot_q <= 1'b0;
            payload_index_q  <= 6'd0;
            crc_q            <= 16'hFFFF;
            crc_lo_q         <= 8'h00;
            error_event_q    <= 1'b0;
            error_code_q     <= 2'b00;
            out_type         <= 8'h00;
            out_epoch        <= 8'h00;
            out_seq          <= 16'h0000;
            out_tick         <= 32'h0000_0000;
            out_len          <= 6'd0;
            clear_payload();
            if (state_q != S_SEARCH || completed_slot_q) begin
                stat_aborted <= saturating_inc(stat_aborted);
            end
        end else begin
            error_event_q <= 1'b0;
            error_code_q  <= 2'b00;

            if (accept) begin
                stat_bytes <= saturating_inc(stat_bytes);

                case (state_q)
                    S_SEARCH: begin
                        if (in_data == MAGIC_A5) begin
                            state_q <= S_WAIT_5A;
                            clear_candidate_controls();
                        end
                    end

                    S_WAIT_5A: begin
                        if (in_data == MAGIC_5A) begin
                            state_q <= S_VERSION;
                        end else if (in_data != MAGIC_A5) begin
                            state_q <= S_SEARCH;
                        end
                    end

                    S_VERSION: begin
                        if (in_data == WIRE_VERSION) begin
                            crc_q   <= crc_next;
                            state_q <= S_TYPE;
                        end else begin
                            stat_version  <= saturating_inc(stat_version);
                            error_event_q <= 1'b1;
                            error_code_q  <= 2'b01;
                            if (in_data == MAGIC_A5) begin
                                state_q <= S_WAIT_5A;
                                clear_candidate_controls();
                            end else begin
                                state_q <= S_SEARCH;
                            end
                        end
                    end

                    S_TYPE: begin
                        out_type <= in_data;
                        crc_q    <= crc_next;
                        state_q  <= S_LENGTH;
                    end

                    S_LENGTH: begin
                        if (in_data > 8'd32) begin
                            stat_length   <= saturating_inc(stat_length);
                            error_event_q <= 1'b1;
                            error_code_q  <= 2'b10;
                            if (in_data == MAGIC_A5) begin
                                state_q <= S_WAIT_5A;
                                clear_candidate_controls();
                            end else begin
                                state_q <= S_SEARCH;
                            end
                        end else begin
                            out_len         <= in_data[5:0];
                            payload_index_q <= 6'd0;
                            crc_q           <= crc_next;
                            state_q <= S_EPOCH;
                        end
                    end

                    S_EPOCH: begin
                        out_epoch <= in_data;
                        crc_q     <= crc_next;
                        state_q   <= S_SEQ_LO;
                    end

                    S_SEQ_LO: begin
                        out_seq[7:0] <= in_data;
                        crc_q        <= crc_next;
                        state_q      <= S_SEQ_HI;
                    end

                    S_SEQ_HI: begin
                        out_seq[15:8] <= in_data;
                        crc_q         <= crc_next;
                        state_q       <= S_TICK0;
                    end

                    S_TICK0: begin
                        out_tick[7:0] <= in_data;
                        crc_q         <= crc_next;
                        state_q       <= S_TICK1;
                    end

                    S_TICK1: begin
                        out_tick[15:8] <= in_data;
                        crc_q          <= crc_next;
                        state_q        <= S_TICK2;
                    end

                    S_TICK2: begin
                        out_tick[23:16] <= in_data;
                        crc_q           <= crc_next;
                        state_q         <= S_TICK3;
                    end

                    S_TICK3: begin
                        out_tick[31:24] <= in_data;
                        crc_q           <= crc_next;
                        if (out_len == 6'd0) begin
                            state_q <= S_CRC_LO;
                        end else begin
                            state_q <= S_PAYLOAD;
                        end
                    end

                    S_PAYLOAD: begin
                        payload_mem[payload_index_q[4:0]] <= in_data;
                        payload_index_q                    <= payload_index_q + 6'd1;
                        crc_q                              <= crc_next;
                        if ((payload_index_q + 6'd1) == {out_len}) begin
                            state_q <= S_CRC_LO;
                        end
                    end

                    S_CRC_LO: begin
                        crc_lo_q <= in_data;
                        state_q  <= S_CRC_HI;
                    end

                    S_CRC_HI: begin
                        if (crc_q == {in_data, crc_lo_q}) begin
                            completed_slot_q <= 1'b1;
                            state_q          <= S_SEARCH;
                            stat_frames      <= saturating_inc(stat_frames);
                        end else begin
                            stat_crc      <= saturating_inc(stat_crc);
                            error_event_q <= 1'b1;
                            error_code_q  <= 2'b11;
                            if (in_data == MAGIC_A5) begin
                                state_q <= S_WAIT_5A;
                                clear_candidate_controls();
                            end else begin
                                state_q <= S_SEARCH;
                            end
                        end
                    end

                    default: begin
                        state_q <= S_SEARCH;
                    end
                endcase
            end else if (completed_slot_q && out_ready) begin
                completed_slot_q <= 1'b0;
                stat_retired     <= saturating_inc(stat_retired);
            end
        end
    end

endmodule

`default_nettype wire
