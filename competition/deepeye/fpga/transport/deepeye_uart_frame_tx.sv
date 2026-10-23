// deepeye_uart_frame_tx - complete-frame buffer and UART direction timing.
//
// Work: B-UART-FRAME-TX-20261023-26-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-UART-FRAME-TX-20261023-26
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// CANDIDATE-ONLY.  This block buffers one internal frame of 1..64 bytes and
// sequences the unchanged byte UART core plus the registered direction-enable
// output.  It does not define the public wire packet format, RS485 electrical
// approval, arbitration, receive path, CDC/RDC, board wiring or a system result.

`define DEEPEYE_UART_FRAME_TX_STAT_W ((STAT_W < 2) ? 2 : ((STAT_W > 32) ? 32 : STAT_W))

module deepeye_uart_frame_tx #(
    parameter integer CLOCK_HZ = 100000000,
    parameter integer BAUD = 9600,
    parameter integer PRE_CYCLES = 0,
    parameter integer POST_CYCLES = 0,
    parameter integer STAT_W = 32
) (
    input  logic clk,
    input  logic rst,
    input  logic cancel,
    input  logic cfg_valid,
    output logic cfg_ready,
    input  logic [6:0] cfg_count,
    input  logic s_valid,
    output logic s_ready,
    input  logic [7:0] s_data,
    input  logic s_last,
    output logic tx,
    output logic de,
    output logic busy,
    output logic receiving,
    output logic faulted,
    output logic fault_event,
    output logic [1:0] fault_code,
    output logic [`DEEPEYE_UART_FRAME_TX_STAT_W-1:0] stat_admitted,
    output logic [`DEEPEYE_UART_FRAME_TX_STAT_W-1:0] stat_sent,
    output logic [`DEEPEYE_UART_FRAME_TX_STAT_W-1:0] stat_aborted,
    output logic [`DEEPEYE_UART_FRAME_TX_STAT_W-1:0] stat_faults
);

    localparam bit CLOCK_VALID = (CLOCK_HZ >= 2) && (CLOCK_HZ <= 2147483647);
    localparam bit BAUD_VALID = CLOCK_VALID && (BAUD >= 1) &&
                                (BAUD <= (CLOCK_HZ / 2));
    localparam bit PRE_VALID = (PRE_CYCLES >= 0) && (PRE_CYCLES <= 65535);
    localparam bit POST_VALID = (POST_CYCLES >= 0) && (POST_CYCLES <= 65535);
    localparam bit STAT_VALID = (STAT_W >= 2) && (STAT_W <= 32);

    // Keep ports and declarations legal for illegal overrides so the exact
    // time-zero guard, rather than a dependent compile error, is observed.
    localparam integer CLOCK_SAFE = CLOCK_VALID ? CLOCK_HZ : 100000000;
    localparam integer BAUD_LIMIT = CLOCK_SAFE / 2;
    localparam integer BAUD_FALLBACK = (BAUD_LIMIT >= 9600) ? 9600 : BAUD_LIMIT;
    localparam integer BAUD_SAFE = BAUD_VALID ? BAUD : BAUD_FALLBACK;
    localparam integer STAT_SAFE = STAT_VALID ? STAT_W : 2;

    localparam logic [STAT_SAFE-1:0] STAT_MAX = {STAT_SAFE{1'b1}};

    typedef enum logic [2:0] {
        ST_IDLE,
        ST_RECEIVE,
        ST_SEALED,
        ST_PRE,
        ST_NEXT_BYTE,
        ST_WAIT_BYTE,
        ST_POST,
        ST_FAULT
    } state_t;

    state_t state_q;
    logic [6:0] frame_count_q;
    logic [5:0] sample_index_q;
    logic [5:0] send_index_q;
    logic [15:0] pre_count_q;
    logic [15:0] post_count_q;

    logic receiving_q;
    logic faulted_q;
    logic fault_event_q;
    logic [1:0] fault_code_q;
    logic de_q;
    logic busy_q;

    logic [STAT_SAFE-1:0] stat_admitted_q;
    logic [STAT_SAFE-1:0] stat_sent_q;
    logic [STAT_SAFE-1:0] stat_aborted_q;
    logic [STAT_SAFE-1:0] stat_faults_q;

    // Exactly one frame storage array.  sample_index_q is six bits, so all
    // write addresses are structurally confined to 0..63.
    logic [7:0] frame_mem [0:63];

    logic core_in_valid;
    logic core_in_ready;
    logic core_tx;
    logic core_busy;
    logic [STAT_SAFE-1:0] core_stat_accepted;
    logic [STAT_SAFE-1:0] core_stat_completed;
    logic [STAT_SAFE-1:0] core_stat_aborted;

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

    function automatic logic sample_is_last(input logic [5:0] index);
        begin
            sample_is_last = ({1'b0, index} == (frame_count_q - 7'd1));
        end
    endfunction

    function automatic logic send_is_last(input logic [5:0] index);
        begin
            send_is_last = ({1'b0, index} == (frame_count_q - 7'd1));
        end
    endfunction

    always_comb begin
        core_in_valid = 1'b0;
        if (!rst && !cancel && !faulted_q) begin
            if (state_q == ST_PRE) begin
                core_in_valid = (pre_count_q >= PRE_CYCLES) && core_in_ready;
            end else if (state_q == ST_NEXT_BYTE) begin
                core_in_valid = core_in_ready;
            end
        end
    end

    assign cfg_ready = !rst && !cancel && !faulted_q && (state_q == ST_IDLE);
    assign s_ready   = !rst && !cancel && !faulted_q && (state_q == ST_RECEIVE);

    assign tx         = core_tx;
    assign de         = de_q;
    assign busy       = busy_q;
    assign receiving  = receiving_q;
    assign faulted    = faulted_q;
    assign fault_event = fault_event_q;
    assign fault_code = fault_code_q;
    assign stat_admitted = stat_admitted_q;
    assign stat_sent     = stat_sent_q;
    assign stat_aborted  = stat_aborted_q;
    assign stat_faults   = stat_faults_q;

    // The accepted byte transmitter is instantiated exactly once and is not
    // modified by this operation.
    deepeye_uart_tx #(
        .CLOCK_HZ(CLOCK_SAFE),
        .BAUD(BAUD_SAFE),
        .STAT_W(STAT_SAFE)
    ) tx_core (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .in_valid(core_in_valid),
        .in_ready(core_in_ready),
        .in_data(frame_mem[send_index_q]),
        .tx(core_tx),
        .busy(core_busy),
        .stat_accepted(core_stat_accepted),
        .stat_completed(core_stat_completed),
        .stat_aborted(core_stat_aborted)
    );

    always_ff @(posedge clk) begin
        if (rst) begin
            state_q          <= ST_IDLE;
            frame_count_q    <= 7'd0;
            sample_index_q   <= 6'd0;
            send_index_q     <= 6'd0;
            pre_count_q      <= 16'd0;
            post_count_q     <= 16'd0;
            receiving_q      <= 1'b0;
            faulted_q        <= 1'b0;
            fault_event_q    <= 1'b0;
            fault_code_q     <= 2'd0;
            de_q             <= 1'b0;
            busy_q           <= 1'b0;
            stat_admitted_q  <= '0;
            stat_sent_q      <= '0;
            stat_aborted_q   <= '0;
            stat_faults_q    <= '0;
        end else if (cancel) begin
            if (busy_q) begin
                stat_aborted_q <= sat_inc(stat_aborted_q);
            end
            state_q        <= ST_IDLE;
            frame_count_q  <= 7'd0;
            sample_index_q <= 6'd0;
            send_index_q   <= 6'd0;
            pre_count_q    <= 16'd0;
            post_count_q   <= 16'd0;
            receiving_q    <= 1'b0;
            faulted_q      <= 1'b0;
            fault_event_q  <= 1'b0;
            fault_code_q   <= 2'd0;
            de_q           <= 1'b0;
            busy_q         <= 1'b0;
        end else begin
            // A fault event is a one-clock pulse.  Every ordinary cycle first
            // withdraws it; a newly detected fault below re-asserts it.
            fault_event_q <= 1'b0;

            case (state_q)
                ST_IDLE: begin
                    if (cfg_valid) begin
                        busy_q          <= 1'b1;
                        stat_admitted_q <= sat_inc(stat_admitted_q);
                        frame_count_q   <= cfg_count;
                        sample_index_q  <= 6'd0;
                        send_index_q    <= 6'd0;
                        pre_count_q     <= 16'd0;
                        post_count_q    <= 16'd0;
                        if ((cfg_count == 7'd0) || (cfg_count > 7'd64)) begin
                            faulted_q     <= 1'b1;
                            fault_code_q  <= 2'd1;
                            fault_event_q <= 1'b1;
                            stat_faults_q <= sat_inc(stat_faults_q);
                            receiving_q   <= 1'b0;
                            state_q       <= ST_FAULT;
                        end else begin
                            receiving_q <= 1'b1;
                            state_q     <= ST_RECEIVE;
                        end
                    end
                end

                ST_RECEIVE: begin
                    if (s_valid) begin
                        if (s_last == sample_is_last(sample_index_q)) begin
                            frame_mem[sample_index_q] <= s_data;
                            if (sample_is_last(sample_index_q)) begin
                                receiving_q <= 1'b0;
                                state_q     <= ST_SEALED;
                            end else begin
                                sample_index_q <= sample_index_q + 6'd1;
                            end
                        end else begin
                            // Retain the reservation, accept no further input,
                            // and never expose a partial frame to the core.
                            faulted_q     <= 1'b1;
                            fault_code_q  <= 2'd2;
                            fault_event_q <= 1'b1;
                            stat_faults_q <= sat_inc(stat_faults_q);
                            receiving_q   <= 1'b0;
                            state_q       <= ST_FAULT;
                        end
                    end
                end

                ST_SEALED: begin
                    // The scan edge after the final accepted sample raises DE.
                    // It cannot also admit the first byte.
                    de_q        <= 1'b1;
                    pre_count_q <= 16'd0;
                    state_q     <= ST_PRE;
                end

                ST_PRE: begin
                    if (pre_count_q >= PRE_CYCLES) begin
                        if (core_in_ready) begin
                            send_index_q <= 6'd0;
                            state_q      <= ST_WAIT_BYTE;
                        end
                    end else begin
                        pre_count_q <= pre_count_q + 16'd1;
                    end
                end

                ST_NEXT_BYTE: begin
                    if (core_in_ready) begin
                        state_q <= ST_WAIT_BYTE;
                    end
                end

                ST_WAIT_BYTE: begin
                    if (!core_busy) begin
                        if (send_is_last(send_index_q)) begin
                            // core_busy fell on the preceding edge c.  This
                            // edge is c+1, when that fall is observable here.
                            if (POST_CYCLES == 0) begin
                                de_q       <= 1'b0;
                                busy_q     <= 1'b0;
                                stat_sent_q <= sat_inc(stat_sent_q);
                                state_q    <= ST_IDLE;
                            end else begin
                                post_count_q <= 16'd1;
                                state_q       <= ST_POST;
                            end
                        end else begin
                            send_index_q <= send_index_q + 6'd1;
                            state_q      <= ST_NEXT_BYTE;
                        end
                    end
                end

                ST_POST: begin
                    if (post_count_q >= POST_CYCLES) begin
                        de_q        <= 1'b0;
                        busy_q      <= 1'b0;
                        stat_sent_q <= sat_inc(stat_sent_q);
                        state_q     <= ST_IDLE;
                    end else begin
                        post_count_q <= post_count_q + 16'd1;
                    end
                end

                ST_FAULT: begin
                    // Reservation and sticky fault remain until cancel/reset.
                end

                default: begin
                    state_q  <= ST_IDLE;
                    de_q     <= 1'b0;
                    busy_q   <= 1'b0;
                    faulted_q <= 1'b1;
                    fault_code_q <= 2'd2;
                    fault_event_q <= 1'b1;
                end
            endcase
        end
    end

    // Exact own diagnostics take priority over the dependency's duplicate
    // checks.  Parameters passed to the core are clamped above.
    `ifndef SYNTHESIS
    // synthesis translate_off
    generate
        if (!CLOCK_VALID) begin : g_guard_clock_hz
            initial begin
                $fatal(1, "deepeye_uart_frame_tx: CLOCK_HZ out of range");
            end
        end else if (!BAUD_VALID) begin : g_guard_baud
            initial begin
                $fatal(1, "deepeye_uart_frame_tx: BAUD out of range");
            end
        end else if (!PRE_VALID) begin : g_guard_pre_cycles
            initial begin
                $fatal(1, "deepeye_uart_frame_tx: PRE_CYCLES out of range");
            end
        end else if (!POST_VALID) begin : g_guard_post_cycles
            initial begin
                $fatal(1, "deepeye_uart_frame_tx: POST_CYCLES out of range");
            end
        end else if (!STAT_VALID) begin : g_guard_stat_w
            initial begin
                $fatal(1, "deepeye_uart_frame_tx: STAT_W out of range");
            end
        end
    endgenerate
    // synthesis translate_on
    `endif

endmodule

`undef DEEPEYE_UART_FRAME_TX_STAT_W
