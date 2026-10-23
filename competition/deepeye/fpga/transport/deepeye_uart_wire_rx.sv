// deepeye_uart_wire_rx - opaque UART-to-parser receive composition.
//
// Work: B-UART-WIRE-RX-20261024-31-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-UART-WIRE-RX-20261024-31
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// This is an opaque same-clock digital receive candidate. It is not a public
// ABI, semantic packet/profile/source/BOOT decision, authentication, replay or
// liveness policy, physical CDC/oscillator/electrical proof, or board result.

`default_nettype none

`define DEEPEYE_UART_WIRE_RX_STAT_W \
    ((STAT_W < 2) ? 2 : ((STAT_W > 32) ? 32 : STAT_W))

module deepeye_uart_wire_rx #(
    parameter integer CLOCK_HZ = 100000000,
    parameter integer BAUD = 9600,
    parameter integer STAT_W = 32
) (
    input  wire logic clk,
    input  wire logic rst,
    input  wire logic cancel,
    input  wire logic rx_async,
    input  wire logic out_ready,

    output logic out_valid,
    output logic [7:0] out_type,
    output logic [7:0] out_epoch,
    output logic [15:0] out_seq,
    output logic [31:0] out_tick,
    output logic [5:0] out_len,
    output logic [255:0] out_payload,

    output logic uart_busy,
    output logic receiving,
    output logic line_error_event,
    output logic [2:0] line_error_bits,
    output logic error_event,
    output logic [1:0] error_code,

    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_uart_frames,
    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_uart_retired,
    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_uart_overruns,
    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_uart_framing,
    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_uart_false_starts,
    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_uart_aborted,
    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_bytes,
    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_frames,
    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_retired,
    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_version,
    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_length,
    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_crc,
    output logic [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_aborted
);

    localparam bit CLOCK_VALID = (CLOCK_HZ >= 16) && (CLOCK_HZ <= 2147483647);
    localparam bit BAUD_VALID = CLOCK_VALID && (BAUD >= 1) &&
                                (BAUD <= (CLOCK_HZ / 16));
    localparam bit STAT_VALID = (STAT_W >= 2) && (STAT_W <= 32);

    // Invalid overrides are made elaboration-safe before dependency
    // elaboration, so this module owns the first and only time-zero guard.
    localparam integer CLOCK_SAFE = CLOCK_VALID ? CLOCK_HZ : 100000000;
    localparam integer BAUD_LIMIT = CLOCK_SAFE / 16;
    localparam integer BAUD_FALLBACK = (BAUD_LIMIT >= 9600) ? 9600 : BAUD_LIMIT;
    localparam integer BAUD_SAFE = BAUD_VALID ? BAUD : BAUD_FALLBACK;
    localparam integer STAT_SAFE = (STAT_W < 2) ? 2 : ((STAT_W > 32) ? 32 : STAT_W);

    logic uart_out_valid;
    logic [7:0] uart_out_data;
    logic uart_busy_i;
    logic uart_framing_error;
    logic uart_overrun;
    logic uart_false_start;
    logic parser_in_ready;
    logic parser_receiving;
    logic parser_error_event;
    logic [1:0] parser_error_code;
    logic parser_out_valid;
    logic [7:0] parser_out_type;
    logic [7:0] parser_out_epoch;
    logic [15:0] parser_out_seq;
    logic [31:0] parser_out_tick;
    logic [5:0] parser_out_len;
    logic [255:0] parser_out_payload;

    logic internal_cancel;

    assign internal_cancel = cancel || line_error_event;

    deepeye_uart_rx #(
        .CLOCK_HZ(CLOCK_SAFE),
        .BAUD(BAUD_SAFE),
        .STAT_W(STAT_SAFE)
    ) uart_rx_unit (
        .clk(clk),
        .rst(rst),
        .cancel(internal_cancel),
        .rx_async(rx_async),
        .out_ready(parser_in_ready),
        .out_valid(uart_out_valid),
        .out_data(uart_out_data),
        .busy(uart_busy_i),
        .framing_error_event(uart_framing_error),
        .overrun_event(uart_overrun),
        .false_start_event(uart_false_start),
        .stat_frames(stat_uart_frames),
        .stat_retired(stat_uart_retired),
        .stat_overruns(stat_uart_overruns),
        .stat_framing(stat_uart_framing),
        .stat_false_starts(stat_uart_false_starts),
        .stat_aborted(stat_uart_aborted)
    );

    deepeye_wire_parser #(
        .STAT_W(STAT_SAFE)
    ) wire_parser (
        .clk(clk),
        .rst(rst),
        .cancel(internal_cancel),
        .in_valid(uart_out_valid),
        .in_ready(parser_in_ready),
        .in_data(uart_out_data),
        .out_valid(parser_out_valid),
        .out_ready(out_ready),
        .out_type(parser_out_type),
        .out_epoch(parser_out_epoch),
        .out_seq(parser_out_seq),
        .out_tick(parser_out_tick),
        .out_len(parser_out_len),
        .out_payload(parser_out_payload),
        .receiving(parser_receiving),
        .error_event(parser_error_event),
        .error_code(parser_error_code),
        .stat_bytes(stat_bytes),
        .stat_frames(stat_frames),
        .stat_retired(stat_retired),
        .stat_version(stat_version),
        .stat_length(stat_length),
        .stat_crc(stat_crc),
        .stat_aborted(stat_aborted)
    );

    assign line_error_bits = {uart_overrun, uart_framing_error, uart_false_start};
    assign line_error_event = uart_overrun || uart_framing_error || uart_false_start;

    assign out_valid = parser_out_valid;
    assign out_type = parser_out_type;
    assign out_epoch = parser_out_epoch;
    assign out_seq = parser_out_seq;
    assign out_tick = parser_out_tick;
    assign out_len = parser_out_len;
    assign out_payload = parser_out_payload;
    assign uart_busy = uart_busy_i;
    assign receiving = parser_receiving;
    assign error_event = parser_error_event;
    assign error_code = parser_error_code;

    `ifndef SYNTHESIS
    // synthesis translate_off
    generate
        if (!CLOCK_VALID) begin : g_guard_clock_hz
            initial begin
                $fatal(1, "deepeye_uart_wire_rx: CLOCK_HZ out of range");
            end
        end else if (!BAUD_VALID) begin : g_guard_baud
            initial begin
                $fatal(1, "deepeye_uart_wire_rx: BAUD out of range");
            end
        end else if (!STAT_VALID) begin : g_guard_stat_w
            initial begin
                $fatal(1, "deepeye_uart_wire_rx: STAT_W out of range");
            end
        end
    endgenerate
    // synthesis translate_on
    `endif

endmodule

`undef DEEPEYE_UART_WIRE_RX_STAT_W
`default_nettype wire
