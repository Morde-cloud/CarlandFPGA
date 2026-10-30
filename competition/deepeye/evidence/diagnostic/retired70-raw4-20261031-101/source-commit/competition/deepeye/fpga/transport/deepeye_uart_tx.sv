// deepeye_uart_tx - internal byte-to-UART transmitter candidate.
//
// Work: B-UART-TX-20261023-24-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-UART-TX-20261023-24
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// CANDIDATE-ONLY.  This is one internal eight-bit UART transmitter.  It does
// not claim a public ABI, wire pinout, baud calibration, direction enable,
// message framing, RX/CDC, scheduler, shared transport budget or board result.
//
// A byte is admitted on one edge when in_ready is high.  The start bit is
// driven immediately after that edge and all eight data bits are latched.
// Boundary k is the first rising edge on which the phase accumulator reaches
// CLOCK_HZ, which is exactly ceil(k*CLOCK_HZ/BAUD) edges after admission.
// The phase is restarted for every accepted byte; idle time earns no credit.

`define DEEPEYE_UART_TX_STAT_W ((STAT_W < 2) ? 2 : ((STAT_W > 32) ? 32 : STAT_W))

module deepeye_uart_tx #(
    parameter integer CLOCK_HZ = 100000000,
    parameter integer BAUD = 9600,
    parameter integer STAT_W = 32
) (
    input  logic clk,
    input  logic rst,
    input  logic cancel,
    input  logic in_valid,
    output logic in_ready,
    input  logic [7:0] in_data,
    output logic tx,
    output logic busy,
    output logic [`DEEPEYE_UART_TX_STAT_W-1:0] stat_accepted,
    output logic [`DEEPEYE_UART_TX_STAT_W-1:0] stat_completed,
    output logic [`DEEPEYE_UART_TX_STAT_W-1:0] stat_aborted
);

    localparam bit CLOCK_VALID = (CLOCK_HZ >= 2) && (CLOCK_HZ <= 2147483647);
    localparam bit BAUD_VALID = CLOCK_VALID && (BAUD >= 1) &&
                                (BAUD <= (CLOCK_HZ / 2));
    localparam bit STAT_VALID = (STAT_W >= 2) && (STAT_W <= 32);

    // Keep every declaration legal for invalid overrides so the exact runtime
    // guard, rather than a compile error, reports the first invalid parameter.
    localparam integer CLOCK_SAFE = CLOCK_VALID ? CLOCK_HZ : 100000000;
    localparam integer BAUD_LIMIT = CLOCK_SAFE / 2;
    localparam integer BAUD_FALLBACK = (BAUD_LIMIT >= 9600) ? 9600 : BAUD_LIMIT;
    localparam integer BAUD_SAFE = BAUD_VALID ? BAUD : BAUD_FALLBACK;
    localparam integer STAT_SAFE = STAT_VALID ? STAT_W : 2;

    localparam logic [STAT_SAFE-1:0] STAT_MAX = {STAT_SAFE{1'b1}};

    logic [7:0]  data_q;
    logic [31:0] phase_q;
    logic [3:0]  boundary_q;
    logic        busy_q;
    logic        tx_q;

    logic [STAT_SAFE-1:0] stat_accepted_q;
    logic [STAT_SAFE-1:0] stat_completed_q;
    logic [STAT_SAFE-1:0] stat_aborted_q;

    logic [31:0] clock_u;
    logic [31:0] baud_u;
    logic [32:0] phase_sum;
    logic [31:0] phase_remainder;
    logic        boundary_hit;

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

    assign clock_u = CLOCK_SAFE;
    assign baud_u  = BAUD_SAFE;

    assign phase_sum = {1'b0, phase_q} + {1'b0, baud_u};
    assign phase_remainder = phase_sum[31:0] - clock_u;
    assign boundary_hit = busy_q && (phase_sum >= {1'b0, clock_u});

    assign in_ready = !rst && !cancel && !busy_q;
    assign tx       = tx_q;
    assign busy     = busy_q;
    assign stat_accepted  = stat_accepted_q;
    assign stat_completed = stat_completed_q;
    assign stat_aborted   = stat_aborted_q;

    always_ff @(posedge clk) begin
        if (rst) begin
            data_q           <= 8'd0;
            phase_q          <= 32'd0;
            boundary_q       <= 4'd0;
            busy_q           <= 1'b0;
            tx_q             <= 1'b1;
            stat_accepted_q  <= '0;
            stat_completed_q <= '0;
            stat_aborted_q   <= '0;
        end else if (cancel) begin
            if (busy_q) begin
                stat_aborted_q <= sat_inc(stat_aborted_q);
            end
            // A cancelled byte is discarded, not drained.  Held cancel remains
            // counted once because busy is already clear on later edges.
            data_q     <= 8'd0;
            phase_q    <= 32'd0;
            boundary_q <= 4'd0;
            busy_q     <= 1'b0;
            tx_q       <= 1'b1;
        end else if (busy_q) begin
            if (boundary_hit) begin
                phase_q <= phase_remainder;
                if (boundary_q == 4'd9) begin
                    boundary_q       <= 4'd0;
                    busy_q           <= 1'b0;
                    tx_q             <= 1'b1;
                    stat_completed_q <= sat_inc(stat_completed_q);
                end else begin
                    boundary_q <= boundary_q + 1'b1;
                    case (boundary_q + 1'b1)
                        4'd1: tx_q <= data_q[0];
                        4'd2: tx_q <= data_q[1];
                        4'd3: tx_q <= data_q[2];
                        4'd4: tx_q <= data_q[3];
                        4'd5: tx_q <= data_q[4];
                        4'd6: tx_q <= data_q[5];
                        4'd7: tx_q <= data_q[6];
                        4'd8: tx_q <= data_q[7];
                        4'd9: tx_q <= 1'b1;
                        default: tx_q <= 1'b1;
                    endcase
                end
            end else begin
                phase_q <= phase_sum[31:0];
            end
        end else begin
            tx_q <= 1'b1;
            if (in_valid && in_ready) begin
                data_q          <= in_data;
                phase_q         <= 32'd0;
                boundary_q      <= 4'd0;
                busy_q          <= 1'b1;
                tx_q            <= 1'b0;
                stat_accepted_q <= sat_inc(stat_accepted_q);
            end
        end
    end

    // Parameter checks are elaboration-legal, then fire once at time zero.
    // The if/else chain fixes the required CLOCK_HZ > BAUD > STAT_W priority.
    `ifndef SYNTHESIS
    // synthesis translate_off
    generate
        if (!CLOCK_VALID) begin : g_guard_clock_hz
            initial begin
                $fatal(1, "deepeye_uart_tx: CLOCK_HZ out of range");
            end
        end else if (!BAUD_VALID) begin : g_guard_baud
            initial begin
                $fatal(1, "deepeye_uart_tx: BAUD out of range");
            end
        end else if (!STAT_VALID) begin : g_guard_stat_w
            initial begin
                $fatal(1, "deepeye_uart_tx: STAT_W out of range");
            end
        end
    endgenerate
    // synthesis translate_on
    `endif

endmodule

`undef DEEPEYE_UART_TX_STAT_W
