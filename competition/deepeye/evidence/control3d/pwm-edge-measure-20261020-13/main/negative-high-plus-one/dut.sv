// deepeye_pwm_edge_measure - internal synchronous single-channel raw PWM
// edge-measurement candidate.
//
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Work: B-PWM-EDGE-MEASURE-RTL-20261020-13-v1
// Product operation: B-DEEPEYE-PWM-EDGE-MEASURE-20261020-13
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Contract pin: f5989cd5defce561f9ba98e6b18fc2682945f0a2.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
// Normative scope SHA256:
// cc7960d77300fcd46a2b8e6e5e0aca1adafc99842d172934ab77ca8d593b3a90.
//
// CANDIDATE-ONLY internal synchronous integer edge counter. This file defines
// no public ABI, register address, pin, clock frequency, analog/PWM profile,
// capture authority, freshness/liveness grant, motion mapping, CDC/RDC
// contract, synthesis result or board result.
//
// out_valid is the registered result-slot occupancy qualified by the
// synchronous abort controls. It means only that one raw record is queued for
// transport. It does not mean the source is live, fresh, eligible or safe for
// motion. A completed record may wait while later input is lost; the loss
// diagnostics report that fact. Only reset/STOP/rearm flush the record.

module deepeye_pwm_edge_measure #(
    parameter integer COUNT_W = 32,
    parameter integer TAG_W   = 32
) (
    input  logic                 clk,
    input  logic                 rst,
    input  logic                 stop,
    input  logic                 rearm,
    input  logic                 sample_level,
    input  logic [TAG_W-1:0]     window_tag,
    input  logic                 out_ready,
    output logic                 armed,
    output logic                 out_valid,
    output logic [COUNT_W-1:0]   out_period,
    output logic [COUNT_W-1:0]   out_high,
    output logic [TAG_W-1:0]     out_tag,
    output logic                 overflow_event,
    output logic                 overrun_event,
    output logic                 overflow_seen,
    output logic                 overrun_seen,
    output logic [COUNT_W-1:0]   loss_count
);

    localparam logic [COUNT_W-1:0] COUNT_MAX = '1;
    localparam logic [TAG_W-1:0]   TAG_ZERO  = '0;

    localparam logic [1:0] ST_IDLE = 2'd0;
    localparam logic [1:0] ST_HIGH = 2'd1;
    localparam logic [1:0] ST_LOW  = 2'd2;

    logic [1:0]         state_q;
    logic               armed_q;
    logic               prev_q;
    logic [COUNT_W-1:0] age_q;
    logic [COUNT_W-1:0] high_q;
    logic               slot_valid_q;
    logic [COUNT_W-1:0] slot_period_q;
    logic [COUNT_W-1:0] slot_high_q;
    logic [TAG_W-1:0]   slot_tag_q;
    logic [TAG_W-1:0]   win_tag_q;
    logic               overflow_event_q;
    logic               overrun_event_q;
    logic               overflow_seen_q;
    logic               overrun_seen_q;
    logic [COUNT_W-1:0] loss_q;

    assign armed          = armed_q;
    assign out_valid      = slot_valid_q && !rst && !stop && !rearm;
    assign out_period     = slot_period_q;
    assign out_high       = slot_high_q;
    assign out_tag        = slot_tag_q;
    assign overflow_event = overflow_event_q;
    assign overrun_event  = overrun_event_q;
    assign overflow_seen  = overflow_seen_q;
    assign overrun_seen   = overrun_seen_q;
    assign loss_count     = loss_q;

    always_ff @(posedge clk) begin
        overflow_event_q <= 1'b0;
        overrun_event_q  <= 1'b0;

        if (rst || stop) begin
            armed_q         <= 1'b0;
            state_q         <= ST_IDLE;
            prev_q          <= 1'b0;
            age_q           <= '0;
            high_q          <= '0;
            slot_valid_q    <= 1'b0;
            slot_period_q   <= '0;
            slot_high_q     <= '0;
            slot_tag_q      <= TAG_ZERO;
            win_tag_q       <= TAG_ZERO;
            overflow_seen_q <= 1'b0;
            overrun_seen_q  <= 1'b0;
            loss_q          <= '0;
        end else if (rearm) begin
            armed_q         <= 1'b1;
            state_q         <= ST_IDLE;
            prev_q          <= sample_level;
            age_q           <= '0;
            high_q          <= '0;
            slot_valid_q    <= 1'b0;
            slot_period_q   <= '0;
            slot_high_q     <= '0;
            slot_tag_q      <= TAG_ZERO;
            win_tag_q       <= window_tag;
            overflow_seen_q <= 1'b0;
            overrun_seen_q  <= 1'b0;
            loss_q          <= '0;
        end else if (armed_q) begin
            prev_q <= sample_level;

            if ((state_q != ST_IDLE) && (age_q == COUNT_MAX)) begin
                // The interval that would close this partial is MAX+1.
                // Abandon only this partial; never wrap or relabel it.
                overflow_event_q <= 1'b1;
                overflow_seen_q  <= 1'b1;
                if (loss_q != COUNT_MAX) begin
                    loss_q <= loss_q + 1'b1;
                end
                high_q <= '0;
                age_q  <= '0;
                if (!prev_q && sample_level) begin
                    // A genuinely fresh rising on the overflowing edge is the
                    // next window's R0 baseline.
                    state_q <= ST_HIGH;
                end else begin
                    state_q <= ST_IDLE;
                end
                if (slot_valid_q && out_ready) begin
                    slot_valid_q  <= 1'b0;
                    slot_period_q <= '0;
                    slot_high_q   <= '0;
                    slot_tag_q    <= TAG_ZERO;
                end
            end else if (state_q == ST_IDLE) begin
                if (!prev_q && sample_level) begin
                    state_q <= ST_HIGH;
                    age_q   <= '0;
                end
                if (slot_valid_q && out_ready) begin
                    slot_valid_q  <= 1'b0;
                    slot_period_q <= '0;
                    slot_high_q   <= '0;
                    slot_tag_q    <= TAG_ZERO;
                end
            end else if (state_q == ST_HIGH) begin
                if (prev_q && !sample_level) begin
                    high_q  <= age_q + 1'b1;
                    age_q   <= age_q + 1'b1;
                    state_q <= ST_LOW;
                end else begin
                    age_q <= age_q + 1'b1;
                end
                if (slot_valid_q && out_ready) begin
                    slot_valid_q  <= 1'b0;
                    slot_period_q <= '0;
                    slot_high_q   <= '0;
                    slot_tag_q    <= TAG_ZERO;
                end
            end else begin
                if (!prev_q && sample_level) begin
                    if (slot_valid_q && !out_ready) begin
                        overrun_event_q <= 1'b1;
                        overrun_seen_q  <= 1'b1;
                        if (loss_q != COUNT_MAX) begin
                            loss_q <= loss_q + 1'b1;
                        end
                    end else begin
                        slot_valid_q  <= 1'b1;
                        slot_period_q <= age_q + 1'b1;
                        slot_high_q   <= high_q + 1'b1;
                        slot_tag_q    <= win_tag_q;
                    end
                    state_q <= ST_HIGH;
                    age_q   <= '0;
                    high_q  <= '0;
                end else begin
                    age_q <= age_q + 1'b1;
                    if (slot_valid_q && out_ready) begin
                        slot_valid_q  <= 1'b0;
                        slot_period_q <= '0;
                        slot_high_q   <= '0;
                        slot_tag_q    <= TAG_ZERO;
                    end
                end
            end
        end
    end

    // Unsupported parameter combinations are a time-zero simulator diagnostic
    // only. The generate/initial block is explicitly excluded from synthesis
    // and creates no hardware initial state, latch or multiple driver.
    // synthesis translate_off
    generate
        if ((COUNT_W < 2) || (COUNT_W > 32) || (TAG_W < 1) || (TAG_W > 64)) begin : g_param_guard
            initial begin
                $fatal(1,
                       "PWM_EDGE_UNSUPPORTED_PARAMETERS COUNT_W=%0d TAG_W=%0d",
                       COUNT_W, TAG_W);
            end
        end
    endgenerate
    // synthesis translate_on

endmodule