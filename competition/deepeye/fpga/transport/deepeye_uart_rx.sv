// deepeye_uart_rx - internal asynchronous-serial receiver candidate.
//
// Work: B-UART-RX-20261023-25-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-UART-RX-20261023-25
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// CANDIDATE-ONLY.  This is a single digital asynchronous-serial input core.  It
// does not claim metastability resolution, physical CDC proof, oscillator or
// baud tolerance, pin voltage, line qualification, a public ABI or a board
// result.  rx_async is sampled through two registers and decisions use only
// the older synchronizer state.

`define DEEPEYE_UART_RX_STAT_W ((STAT_W < 2) ? 2 : ((STAT_W > 32) ? 32 : STAT_W))

module deepeye_uart_rx #(
    parameter integer CLOCK_HZ = 100000000,
    parameter integer BAUD = 9600,
    parameter integer STAT_W = 32
) (
    input  logic clk,
    input  logic rst,
    input  logic cancel,
    input  logic rx_async,
    input  logic out_ready,
    output logic out_valid,
    output logic [7:0] out_data,
    output logic busy,
    output logic framing_error_event,
    output logic overrun_event,
    output logic false_start_event,
    output logic [`DEEPEYE_UART_RX_STAT_W-1:0] stat_frames,
    output logic [`DEEPEYE_UART_RX_STAT_W-1:0] stat_retired,
    output logic [`DEEPEYE_UART_RX_STAT_W-1:0] stat_overruns,
    output logic [`DEEPEYE_UART_RX_STAT_W-1:0] stat_framing,
    output logic [`DEEPEYE_UART_RX_STAT_W-1:0] stat_false_starts,
    output logic [`DEEPEYE_UART_RX_STAT_W-1:0] stat_aborted
);

    localparam bit CLOCK_VALID = (CLOCK_HZ >= 16) && (CLOCK_HZ <= 2147483647);
    localparam bit BAUD_VALID = CLOCK_VALID && (BAUD >= 1) &&
                                (BAUD <= (CLOCK_HZ / 16));
    localparam bit STAT_VALID = (STAT_W >= 2) && (STAT_W <= 32);

    // Clamp every illegal override to legal widths and arithmetic before the
    // simulation-only time-zero guard reports the first invalid parameter.
    localparam integer CLOCK_SAFE = CLOCK_VALID ? CLOCK_HZ : 100000000;
    localparam integer BAUD_LIMIT = CLOCK_SAFE / 16;
    localparam integer BAUD_FALLBACK = (BAUD_LIMIT >= 9600) ? 9600 : BAUD_LIMIT;
    localparam integer BAUD_SAFE = BAUD_VALID ? BAUD : BAUD_FALLBACK;
    localparam integer STAT_SAFE = STAT_VALID ? STAT_W : 2;

    localparam logic [STAT_SAFE-1:0] STAT_MAX = {STAT_SAFE{1'b1}};

    (* ASYNC_REG = "TRUE" *) logic meta_q;
    (* ASYNC_REG = "TRUE" *) logic sync_q;
    logic prev_sync_q;
    logic [1:0] warm_q;
    logic high_seen_q;

    logic busy_q;
    logic [31:0] phase_q;
    logic [4:0] half_count_q;
    logic [7:0] shift_q;

    logic slot_full_q;
    logic [7:0] slot_data_q;

    logic framing_error_q;
    logic overrun_q;
    logic false_start_q;

    logic [STAT_SAFE-1:0] stat_frames_q;
    logic [STAT_SAFE-1:0] stat_retired_q;
    logic [STAT_SAFE-1:0] stat_overruns_q;
    logic [STAT_SAFE-1:0] stat_framing_q;
    logic [STAT_SAFE-1:0] stat_false_starts_q;
    logic [STAT_SAFE-1:0] stat_aborted_q;

    logic [31:0] clock_u;
    logic [31:0] half_step_u;
    logic [32:0] phase_sum;
    logic [32:0] clock_ext;
    logic [31:0] phase_remainder;
    logic boundary_hit;
    logic [4:0] half_next;

    logic false_start_hit;
    logic data_sample_hit;
    logic good_stop_hit;
    logic bad_stop_hit;
    logic qualified_start;
    logic retire_fire;
    logic offer_store;
    logic overrun_fire;
    logic [1:0] abort_amount;

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

    function automatic logic [STAT_SAFE-1:0] sat_add_small(
        input logic [STAT_SAFE-1:0] value,
        input logic [1:0] amount
    );
        logic [STAT_SAFE+1:0] sum_ext;
        begin
            sum_ext = {2'b0, value} + {{STAT_SAFE{1'b0}}, amount};
            if (sum_ext > {2'b0, STAT_MAX}) begin
                sat_add_small = STAT_MAX;
            end else begin
                sat_add_small = sum_ext[STAT_SAFE-1:0];
            end
        end
    endfunction

    assign clock_u = CLOCK_SAFE;
    assign half_step_u = BAUD_SAFE << 1;
    assign clock_ext = {1'b0, clock_u};

    assign phase_sum = {1'b0, phase_q} + {1'b0, half_step_u};
    assign phase_remainder = phase_sum[31:0] - clock_u;
    assign boundary_hit = busy_q && (phase_sum >= clock_ext);
    assign half_next = half_count_q + 5'd1;

    assign false_start_hit = boundary_hit && (half_count_q == 5'd0) && sync_q;
    assign data_sample_hit = boundary_hit &&
                             (half_count_q >= 5'd2) &&
                             (half_count_q <= 5'd16) &&
                             !half_count_q[0];
    assign good_stop_hit = boundary_hit && (half_count_q == 5'd18) && sync_q;
    assign bad_stop_hit  = boundary_hit && (half_count_q == 5'd18) && !sync_q;

    assign qualified_start = !busy_q && (warm_q == 2'd2) && high_seen_q &&
                             prev_sync_q && !sync_q;
    assign retire_fire = !rst && !cancel && slot_full_q && out_ready;
    assign offer_store = good_stop_hit && (!slot_full_q || retire_fire);
    assign overrun_fire = good_stop_hit && slot_full_q && !retire_fire;
    assign abort_amount = {1'b0, busy_q} + {1'b0, slot_full_q};

    assign out_valid = !rst && !cancel && slot_full_q;
    assign out_data = slot_data_q;
    assign busy = busy_q;
    assign framing_error_event = framing_error_q;
    assign overrun_event = overrun_q;
    assign false_start_event = false_start_q;
    assign stat_frames = stat_frames_q;
    assign stat_retired = stat_retired_q;
    assign stat_overruns = stat_overruns_q;
    assign stat_framing = stat_framing_q;
    assign stat_false_starts = stat_false_starts_q;
    assign stat_aborted = stat_aborted_q;

    always_ff @(posedge clk) begin
        if (rst) begin
            meta_q              <= 1'b1;
            sync_q              <= 1'b1;
            prev_sync_q         <= 1'b1;
            warm_q              <= 2'd0;
            high_seen_q         <= 1'b0;
            busy_q              <= 1'b0;
            phase_q             <= 32'd0;
            half_count_q        <= 5'd0;
            shift_q             <= 8'd0;
            slot_full_q         <= 1'b0;
            slot_data_q         <= 8'd0;
            framing_error_q     <= 1'b0;
            overrun_q           <= 1'b0;
            false_start_q       <= 1'b0;
            stat_frames_q       <= '0;
            stat_retired_q      <= '0;
            stat_overruns_q     <= '0;
            stat_framing_q      <= '0;
            stat_false_starts_q <= '0;
            stat_aborted_q      <= '0;
        end else if (cancel) begin
            // Reset the receiver view of the line so a line held low after the
            // abort must first be observed high before a new falling edge.
            meta_q              <= 1'b1;
            sync_q              <= 1'b1;
            prev_sync_q         <= 1'b1;
            warm_q              <= 2'd0;
            high_seen_q         <= 1'b0;
            busy_q              <= 1'b0;
            phase_q             <= 32'd0;
            half_count_q        <= 5'd0;
            shift_q             <= 8'd0;
            slot_full_q         <= 1'b0;
            slot_data_q         <= 8'd0;
            framing_error_q     <= 1'b0;
            overrun_q           <= 1'b0;
            false_start_q       <= 1'b0;
            stat_aborted_q      <= sat_add_small(stat_aborted_q, abort_amount);
        end else begin
            meta_q      <= rx_async;
            sync_q      <= meta_q;
            prev_sync_q <= sync_q;
            framing_error_q <= 1'b0;
            overrun_q       <= 1'b0;
            false_start_q   <= 1'b0;

            if (warm_q < 2'd2) begin
                warm_q <= warm_q + 1'b1;
            end

            if (retire_fire) begin
                stat_retired_q <= sat_inc(stat_retired_q);
                slot_full_q    <= 1'b0;
                slot_data_q    <= 8'd0;
            end

            if (qualified_start) begin
                busy_q          <= 1'b1;
                phase_q         <= 32'd0;
                half_count_q    <= 5'd0;
                shift_q         <= 8'd0;
                high_seen_q     <= 1'b0;
            end else if (false_start_hit) begin
                busy_q              <= 1'b0;
                phase_q             <= 32'd0;
                half_count_q        <= 5'd0;
                high_seen_q         <= 1'b1;
                false_start_q       <= 1'b1;
                stat_false_starts_q <= sat_inc(stat_false_starts_q);
            end else if (good_stop_hit) begin
                busy_q          <= 1'b0;
                phase_q         <= 32'd0;
                half_count_q    <= 5'd0;
                high_seen_q     <= 1'b1;
                stat_frames_q   <= sat_inc(stat_frames_q);
                if (offer_store) begin
                    slot_full_q <= 1'b1;
                    slot_data_q <= shift_q;
                end else if (overrun_fire) begin
                    overrun_q        <= 1'b1;
                    stat_overruns_q  <= sat_inc(stat_overruns_q);
                end
            end else if (bad_stop_hit) begin
                busy_q            <= 1'b0;
                phase_q           <= 32'd0;
                half_count_q      <= 5'd0;
                high_seen_q       <= 1'b0;
                framing_error_q   <= 1'b1;
                stat_framing_q    <= sat_inc(stat_framing_q);
            end else if (busy_q) begin
                if (boundary_hit) begin
                    phase_q      <= phase_remainder;
                    half_count_q <= half_next;
                    if (data_sample_hit) begin
                        shift_q <= {sync_q, shift_q[7:1]};
                    end
                end else begin
                    phase_q <= phase_sum[31:0];
                end
            end else if (warm_q == 2'd2) begin
                if (sync_q) begin
                    high_seen_q <= 1'b1;
                end
            end
        end
    end

    // Keep declarations legal for invalid overrides, then report exactly one
    // time-zero fatal in the fixed CLOCK_HZ > BAUD > STAT_W priority.
    `ifndef SYNTHESIS
    // synthesis translate_off
    generate
        if (!CLOCK_VALID) begin : g_guard_clock_hz
            initial begin
                $fatal(1, "deepeye_uart_rx: CLOCK_HZ out of range");
            end
        end else if (!BAUD_VALID) begin : g_guard_baud
            initial begin
                $fatal(1, "deepeye_uart_rx: BAUD out of range");
            end
        end else if (!STAT_VALID) begin : g_guard_stat_w
            initial begin
                $fatal(1, "deepeye_uart_rx: STAT_W out of range");
            end
        end
    endgenerate
    // synthesis translate_on
    `endif

endmodule

`undef DEEPEYE_UART_RX_STAT_W
