// deepeye_wire_serializer - opaque version-3 frame serializer candidate.
//
// Work: B-WIRE-SERIALIZER-20261024-28-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-WIRE-SERIALIZER-20261024-28
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// This module serializes one already-admitted opaque frame.  Type, epoch, seq
// and tick are copied without interpretation.  out_valid is not a policy,
// freshness or motion authorization; the caller must discard any partial frame
// after cancel.

`define DEEPEYE_WIRE_SERIALIZER_STAT_W \
    ((STAT_W < 2) ? 2 : ((STAT_W > 32) ? 32 : STAT_W))

module deepeye_wire_serializer #(
    parameter integer STAT_W = 32
) (
    input  logic clk,
    input  logic rst,
    input  logic cancel,
    input  logic cfg_valid,
    output logic cfg_ready,
    input  logic [7:0]  cfg_type,
    input  logic [7:0]  cfg_epoch,
    input  logic [15:0] cfg_seq,
    input  logic [31:0] cfg_tick,
    input  logic [5:0]  cfg_len,
    input  logic p_valid,
    output logic p_ready,
    input  logic [7:0]  p_data,
    input  logic p_last,
    output logic out_valid,
    input  logic out_ready,
    output logic [7:0]  out_data,
    output logic out_last,
    output logic [5:0]  out_count,
    output logic busy,
    output logic receiving,
    output logic faulted,
    output logic fault_event,
    output logic [1:0]  fault_code,
    output logic [`DEEPEYE_WIRE_SERIALIZER_STAT_W-1:0] stat_admitted,
    output logic [`DEEPEYE_WIRE_SERIALIZER_STAT_W-1:0] stat_sent,
    output logic [`DEEPEYE_WIRE_SERIALIZER_STAT_W-1:0] stat_aborted,
    output logic [`DEEPEYE_WIRE_SERIALIZER_STAT_W-1:0] stat_faults
);

    localparam integer STAT_SAFE = (STAT_W < 2) ? 2 : ((STAT_W > 32) ? 32 : STAT_W);
    localparam logic [STAT_SAFE-1:0] STAT_MAX = {STAT_SAFE{1'b1}};

    localparam logic [1:0] ST_IDLE    = 2'd0;
    localparam logic [1:0] ST_RECEIVE = 2'd1;
    localparam logic [1:0] ST_OUTPUT  = 2'd2;
    localparam logic [1:0] ST_FAULT   = 2'd3;

    logic [1:0] state_q;

    logic [7:0]  type_q;
    logic [7:0]  epoch_q;
    logic [15:0] seq_q;
    logic [31:0] tick_q;
    logic [5:0]  len_q;

    logic [7:0] payload_mem [0:31];
    logic [5:0] payload_index_q;
    logic [5:0] out_index_q;
    logic [5:0] out_count_q;
    logic [15:0] crc_state_q;

    logic fault_event_q;
    logic [1:0] fault_code_q;

    logic [STAT_SAFE-1:0] stat_admitted_q;
    logic [STAT_SAFE-1:0] stat_sent_q;
    logic [STAT_SAFE-1:0] stat_aborted_q;
    logic [STAT_SAFE-1:0] stat_faults_q;

    logic [15:0] crc_next;
    logic [4:0]  payload_sel;
    logic [5:0]  covered_end;

    function automatic logic [STAT_SAFE-1:0] sat_inc(
        input logic [STAT_SAFE-1:0] value
    );
        begin
            if (value == STAT_MAX) begin
                sat_inc = value;
            end else begin
                sat_inc = value + 1'b1;
            end
        end
    endfunction

    initial begin
        if (STAT_W < 2 || STAT_W > 32) begin
            $fatal(1, "deepeye_wire_serializer: STAT_W out of range");
        end
    end

    deepeye_crc16_byte crc_unit (
        .crc_in(crc_state_q),
        .data_in(out_data),
        .crc_out(crc_next)
    );

    assign covered_end = 6'd12 + len_q;
    assign cfg_ready = (state_q == ST_IDLE) && !rst && !cancel;
    assign p_ready   = (state_q == ST_RECEIVE) && !rst && !cancel;
    assign out_valid = (state_q == ST_OUTPUT) && !rst && !cancel;
    assign busy      = (state_q != ST_IDLE);
    assign receiving = (state_q == ST_RECEIVE);
    assign faulted   = (state_q == ST_FAULT);
    assign fault_event = fault_event_q;
    assign fault_code  = fault_code_q;
    assign out_count   = out_count_q;
    assign out_last    = out_valid && (out_index_q == (out_count_q - 6'd1));

    assign stat_admitted = stat_admitted_q;
    assign stat_sent     = stat_sent_q;
    assign stat_aborted  = stat_aborted_q;
    assign stat_faults   = stat_faults_q;

    always_comb begin
        payload_sel = 5'd0;
        if ((out_index_q >= 6'd12) && (out_index_q < covered_end)) begin
            payload_sel = out_index_q - 6'd12;
        end

        out_data = 8'h00;
        if (out_index_q == 6'd0) begin
            out_data = 8'hA5;
        end else if (out_index_q == 6'd1) begin
            out_data = 8'h5A;
        end else if (out_index_q == 6'd2) begin
            out_data = 8'h03;
        end else if (out_index_q == 6'd3) begin
            out_data = type_q;
        end else if (out_index_q == 6'd4) begin
            out_data = len_q;
        end else if (out_index_q == 6'd5) begin
            out_data = epoch_q;
        end else if (out_index_q == 6'd6) begin
            out_data = seq_q[7:0];
        end else if (out_index_q == 6'd7) begin
            out_data = seq_q[15:8];
        end else if (out_index_q == 6'd8) begin
            out_data = tick_q[7:0];
        end else if (out_index_q == 6'd9) begin
            out_data = tick_q[15:8];
        end else if (out_index_q == 6'd10) begin
            out_data = tick_q[23:16];
        end else if (out_index_q == 6'd11) begin
            out_data = tick_q[31:24];
        end else if (out_index_q < covered_end) begin
            out_data = payload_mem[payload_sel];
        end else if (out_index_q == covered_end) begin
            out_data = crc_state_q[7:0];
        end else if (out_index_q == (covered_end + 6'd1)) begin
            out_data = crc_state_q[15:8];
        end
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            state_q          <= ST_IDLE;
            type_q           <= 8'h00;
            epoch_q          <= 8'h00;
            seq_q            <= 16'h0000;
            tick_q           <= 32'h00000000;
            len_q            <= 6'd0;
            payload_index_q  <= 6'd0;
            out_index_q      <= 6'd0;
            out_count_q      <= 6'd0;
            crc_state_q      <= 16'hFFFF;
            fault_event_q    <= 1'b0;
            fault_code_q     <= 2'd0;
            stat_admitted_q  <= '0;
            stat_sent_q      <= '0;
            stat_aborted_q   <= '0;
            stat_faults_q    <= '0;
        end else if (cancel) begin
            if (state_q != ST_IDLE) begin
                stat_aborted_q <= sat_inc(stat_aborted_q);
            end
            state_q         <= ST_IDLE;
            payload_index_q <= 6'd0;
            out_index_q     <= 6'd0;
            out_count_q     <= 6'd0;
            crc_state_q     <= 16'hFFFF;
            fault_event_q   <= 1'b0;
            fault_code_q    <= 2'd0;
        end else begin
            fault_event_q <= 1'b0;

            if (state_q == ST_IDLE) begin
                if (cfg_valid) begin
                    stat_admitted_q <= sat_inc(stat_admitted_q);
                    type_q          <= cfg_type;
                    epoch_q         <= cfg_epoch;
                    seq_q           <= cfg_seq;
                    tick_q          <= cfg_tick;
                    len_q           <= cfg_len;
                    payload_index_q <= 6'd0;
                    out_index_q     <= 6'd0;
                    crc_state_q     <= 16'hFFFF;
                    fault_code_q    <= 2'd0;

                    if (cfg_len <= 6'd32) begin
                        out_count_q <= 6'd14 + cfg_len;
                        if (cfg_len == 6'd0) begin
                            state_q <= ST_OUTPUT;
                        end else begin
                            state_q <= ST_RECEIVE;
                        end
                    end else begin
                        out_count_q    <= 6'd0;
                        state_q        <= ST_FAULT;
                        fault_event_q  <= 1'b1;
                        fault_code_q   <= 2'd1;
                        stat_faults_q  <= sat_inc(stat_faults_q);
                    end
                end
            end else if (state_q == ST_RECEIVE) begin
                if (p_valid) begin
                    if (p_last != (payload_index_q == (len_q - 6'd1))) begin
                        state_q       <= ST_FAULT;
                        fault_event_q <= 1'b1;
                        fault_code_q  <= 2'd2;
                        stat_faults_q <= sat_inc(stat_faults_q);
                    end else begin
                        payload_mem[payload_index_q[4:0]] <= p_data;
                        if (payload_index_q == (len_q - 6'd1)) begin
                            payload_index_q <= 6'd0;
                            out_index_q     <= 6'd0;
                            state_q         <= ST_OUTPUT;
                        end else begin
                            payload_index_q <= payload_index_q + 1'b1;
                        end
                    end
                end
            end else if (state_q == ST_OUTPUT) begin
                if (out_ready) begin
                    if ((out_index_q >= 6'd2) && (out_index_q < covered_end)) begin
                        crc_state_q <= crc_next;
                    end

                    if (out_index_q == (out_count_q - 6'd1)) begin
                        stat_sent_q     <= sat_inc(stat_sent_q);
                        state_q         <= ST_IDLE;
                        out_index_q     <= 6'd0;
                        out_count_q     <= 6'd0;
                        payload_index_q <= 6'd0;
                    end else begin
                        out_index_q <= out_index_q + 1'b1;
                    end
                end
            end
        end
    end

endmodule

`undef DEEPEYE_WIRE_SERIALIZER_STAT_W
