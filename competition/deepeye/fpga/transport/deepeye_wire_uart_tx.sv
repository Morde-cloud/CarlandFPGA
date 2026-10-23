// deepeye_wire_uart_tx - opaque packet-to-UART direction compositor.
//
// Work: B-WIRE-UART-TX-20261024-30-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-WIRE-UART-TX-20261024-30
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// Internal candidate composition only. This is not a public ABI, packet format,
// BOOT/source selection, clock/TTL/RS485 approval, control policy or board
// result. It composes the unchanged serializer, CRC byte primitive, complete
// frame buffer and byte UART transmitter under one admitted reservation.

`default_nettype none

`define DEEPEYE_WIRE_UART_TX_STAT_W \
    ((STAT_W < 2) ? 2 : ((STAT_W > 32) ? 32 : STAT_W))

module deepeye_wire_uart_tx #(
    parameter integer CLOCK_HZ = 100000000,
    parameter integer BAUD = 9600,
    parameter integer PRE_CYCLES = 0,
    parameter integer POST_CYCLES = 0,
    parameter integer STAT_W = 32
) (
    input  wire logic clk,
    input  wire logic rst,
    input  wire logic cancel,
    input  wire logic cfg_valid,
    output logic cfg_ready,
    input  wire logic [7:0]  cfg_type,
    input  wire logic [7:0]  cfg_epoch,
    input  wire logic [15:0] cfg_seq,
    input  wire logic [31:0] cfg_tick,
    input  wire logic [5:0]  cfg_len,
    input  wire logic p_valid,
    output logic p_ready,
    input  wire logic [7:0] p_data,
    input  wire logic p_last,
    output logic tx,
    output logic de,
    output logic busy,
    output logic receiving,
    output logic faulted,
    output logic fault_event,
    output logic [1:0] fault_code,
    output logic [`DEEPEYE_WIRE_UART_TX_STAT_W-1:0] stat_admitted,
    output logic [`DEEPEYE_WIRE_UART_TX_STAT_W-1:0] stat_sent,
    output logic [`DEEPEYE_WIRE_UART_TX_STAT_W-1:0] stat_aborted
);

    localparam bit CLOCK_VALID = (CLOCK_HZ >= 2) && (CLOCK_HZ <= 2147483647);
    localparam bit BAUD_VALID = CLOCK_VALID && (BAUD >= 1) &&
                                (BAUD <= (CLOCK_HZ / 2));
    localparam bit PRE_VALID = (PRE_CYCLES >= 0) && (PRE_CYCLES <= 65535);
    localparam bit POST_VALID = (POST_CYCLES >= 0) && (POST_CYCLES <= 65535);
    localparam bit STAT_VALID = (STAT_W >= 2) && (STAT_W <= 32);

    // Invalid top overrides are replaced before dependency elaboration so this
    // module owns the first and only time-zero diagnostic.
    localparam integer CLOCK_SAFE = CLOCK_VALID ? CLOCK_HZ : 100000000;
    localparam integer BAUD_LIMIT = CLOCK_SAFE / 2;
    localparam integer BAUD_FALLBACK = (BAUD_LIMIT >= 9600) ? 9600 : BAUD_LIMIT;
    localparam integer BAUD_SAFE = BAUD_VALID ? BAUD : BAUD_FALLBACK;
    localparam integer PRE_SAFE = PRE_VALID ? PRE_CYCLES : 0;
    localparam integer POST_SAFE = POST_VALID ? POST_CYCLES : 0;
    localparam integer STAT_SAFE = STAT_VALID ? STAT_W : 2;

    localparam logic [STAT_SAFE-1:0] STAT_MAX = {STAT_SAFE{1'b1}};

    typedef enum logic [2:0] {
        ST_IDLE,
        ST_COLLECT,
        ST_TRANSFER,
        ST_WAIT_DRAIN,
        ST_FAULT
    } state_t;

    state_t state_q;
    logic transfer_perm_q;

    logic [STAT_SAFE-1:0] stat_admitted_q;
    logic [STAT_SAFE-1:0] stat_sent_q;
    logic [STAT_SAFE-1:0] stat_aborted_q;

    logic ser_cfg_ready;
    logic ser_p_ready;
    logic ser_out_valid;
    logic [7:0] ser_out_data;
    logic ser_out_last;
    logic [5:0] ser_out_count;
    logic ser_busy;
    logic ser_receiving;
    logic ser_faulted;
    logic ser_fault_event;
    logic [1:0] ser_fault_code;
    logic [STAT_SAFE-1:0] ser_stat_admitted;
    logic [STAT_SAFE-1:0] ser_stat_sent;
    logic [STAT_SAFE-1:0] ser_stat_aborted;
    logic [STAT_SAFE-1:0] ser_stat_faults;

    logic frame_cfg_ready;
    logic frame_s_ready;
    logic frame_tx;
    logic frame_de;
    logic frame_busy;
    logic frame_receiving;
    logic frame_faulted;
    logic frame_fault_event;
    logic [1:0] frame_fault_code;
    logic [STAT_SAFE-1:0] frame_stat_admitted;
    logic [STAT_SAFE-1:0] frame_stat_sent;
    logic [STAT_SAFE-1:0] frame_stat_aborted;
    logic [STAT_SAFE-1:0] frame_stat_faults;

    logic ser_cfg_valid;
    logic ser_p_valid;
    logic ser_out_ready;
    logic frame_cfg_valid;
    logic frame_s_valid;

    function automatic logic [STAT_SAFE-1:0] sat_inc(
        input logic [STAT_SAFE-1:0] value
    );
        logic [STAT_SAFE:0] widened;
        begin
            widened = {1'b0, value} + 1'b1;
            if (widened > {1'b0, STAT_MAX}) begin
                sat_inc = STAT_MAX;
            end else begin
                sat_inc = widened[STAT_SAFE-1:0];
            end
        end
    endfunction

    assign cfg_ready = (state_q == ST_IDLE) && !rst && !cancel &&
                       ser_cfg_ready && frame_cfg_ready;
    assign p_ready = (state_q == ST_COLLECT) && ser_p_ready;

    assign ser_cfg_valid = cfg_valid && cfg_ready;
    assign ser_p_valid = p_valid;
    assign ser_out_ready = transfer_perm_q && frame_s_ready;

    assign frame_cfg_valid = (state_q == ST_COLLECT) && ser_out_valid &&
                             frame_cfg_ready && !ser_faulted && !frame_faulted;
    assign frame_s_valid = transfer_perm_q && ser_out_valid;

    assign tx = frame_tx;
    assign de = frame_de;
    assign busy = (state_q != ST_IDLE);
    assign receiving = ser_receiving;
    assign faulted = ser_faulted || frame_faulted;
    assign fault_event = ser_faulted ? ser_fault_event : frame_fault_event;
    assign fault_code = ser_faulted ? ser_fault_code : frame_fault_code;

    assign stat_admitted = stat_admitted_q;
    assign stat_sent = stat_sent_q;
    assign stat_aborted = stat_aborted_q;

    deepeye_wire_serializer #(
        .STAT_W(STAT_SAFE)
    ) serializer (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .cfg_valid(ser_cfg_valid),
        .cfg_ready(ser_cfg_ready),
        .cfg_type(cfg_type),
        .cfg_epoch(cfg_epoch),
        .cfg_seq(cfg_seq),
        .cfg_tick(cfg_tick),
        .cfg_len(cfg_len),
        .p_valid(ser_p_valid),
        .p_ready(ser_p_ready),
        .p_data(p_data),
        .p_last(p_last),
        .out_valid(ser_out_valid),
        .out_ready(ser_out_ready),
        .out_data(ser_out_data),
        .out_last(ser_out_last),
        .out_count(ser_out_count),
        .busy(ser_busy),
        .receiving(ser_receiving),
        .faulted(ser_faulted),
        .fault_event(ser_fault_event),
        .fault_code(ser_fault_code),
        .stat_admitted(ser_stat_admitted),
        .stat_sent(ser_stat_sent),
        .stat_aborted(ser_stat_aborted),
        .stat_faults(ser_stat_faults)
    );

    deepeye_uart_frame_tx #(
        .CLOCK_HZ(CLOCK_SAFE),
        .BAUD(BAUD_SAFE),
        .PRE_CYCLES(PRE_SAFE),
        .POST_CYCLES(POST_SAFE),
        .STAT_W(STAT_SAFE)
    ) frame_tx_unit (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .cfg_valid(frame_cfg_valid),
        .cfg_ready(frame_cfg_ready),
        .cfg_count({1'b0, ser_out_count}),
        .s_valid(frame_s_valid),
        .s_ready(frame_s_ready),
        .s_data(ser_out_data),
        .s_last(ser_out_last),
        .tx(frame_tx),
        .de(frame_de),
        .busy(frame_busy),
        .receiving(frame_receiving),
        .faulted(frame_faulted),
        .fault_event(frame_fault_event),
        .fault_code(frame_fault_code),
        .stat_admitted(frame_stat_admitted),
        .stat_sent(frame_stat_sent),
        .stat_aborted(frame_stat_aborted),
        .stat_faults(frame_stat_faults)
    );

    always_ff @(posedge clk) begin
        if (rst) begin
            state_q          <= ST_IDLE;
            transfer_perm_q  <= 1'b0;
            stat_admitted_q  <= '0;
            stat_sent_q      <= '0;
            stat_aborted_q   <= '0;
        end else if (cancel) begin
            if (state_q != ST_IDLE) begin
                stat_aborted_q <= sat_inc(stat_aborted_q);
            end
            state_q         <= ST_IDLE;
            transfer_perm_q <= 1'b0;
        end else if (ser_faulted || frame_faulted) begin
            state_q         <= ST_FAULT;
            transfer_perm_q <= 1'b0;
        end else begin
            case (state_q)
                ST_IDLE: begin
                    if (cfg_valid && cfg_ready) begin
                        stat_admitted_q <= sat_inc(stat_admitted_q);
                        state_q         <= ST_COLLECT;
                    end
                end

                ST_COLLECT: begin
                    if (frame_cfg_valid) begin
                        transfer_perm_q <= 1'b1;
                        state_q         <= ST_TRANSFER;
                    end
                end

                ST_TRANSFER: begin
                    if (transfer_perm_q && ser_out_valid && ser_out_last &&
                        frame_s_ready) begin
                        transfer_perm_q <= 1'b0;
                        state_q         <= ST_WAIT_DRAIN;
                    end
                end

                ST_WAIT_DRAIN: begin
                    if (!frame_busy) begin
                        stat_sent_q <= sat_inc(stat_sent_q);
                        state_q     <= ST_IDLE;
                    end
                end

                ST_FAULT: begin
                    // The reservation remains until cancel/reset.
                end

                default: begin
                    state_q         <= ST_FAULT;
                    transfer_perm_q <= 1'b0;
                end
            endcase
        end
    end

    // Exact top-level parameter diagnostics. Dependencies receive only safe
    // values, so their duplicate guards cannot pre-empt these messages.
    `ifndef SYNTHESIS
    // synthesis translate_off
    generate
        if (!CLOCK_VALID) begin : g_guard_clock_hz
            initial begin
                $fatal(1, "deepeye_wire_uart_tx: CLOCK_HZ out of range");
            end
        end else if (!BAUD_VALID) begin : g_guard_baud
            initial begin
                $fatal(1, "deepeye_wire_uart_tx: BAUD out of range");
            end
        end else if (!PRE_VALID) begin : g_guard_pre_cycles
            initial begin
                $fatal(1, "deepeye_wire_uart_tx: PRE_CYCLES out of range");
            end
        end else if (!POST_VALID) begin : g_guard_post_cycles
            initial begin
                $fatal(1, "deepeye_wire_uart_tx: POST_CYCLES out of range");
            end
        end else if (!STAT_VALID) begin : g_guard_stat_w
            initial begin
                $fatal(1, "deepeye_wire_uart_tx: STAT_W out of range");
            end
        end
    endgenerate
    // synthesis translate_on
    `endif

endmodule

`undef DEEPEYE_WIRE_UART_TX_STAT_W
`default_nettype wire
