// deepeye_atomic_pwm - internal one-frame-boundary three-channel PWM candidate.
//
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Work: B-ATOMIC-PWM-RTL-20261020-12-v1
// Product operation: B-DEEPEYE-PWM-ATOMIC-20261020-12
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Contract pin: f5989cd5defce561f9ba98e6b18fc2682945f0a2.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// CANDIDATE-ONLY internal synchronous count generator. This file defines no
// public ABI, register address, pin, clock frequency, capture authority, stop
// authority, motion mapping, CDC/RDC contract, synthesis result or board result.
// The frame-boundary atomic scheduling is a B internal design choice for this
// increment, not a quoted frozen public ABI.

module deepeye_atomic_pwm #(
    parameter integer COUNT_W = 32,
    parameter integer TAG_W   = 32
) (
    input  logic                   clk,
    input  logic                   rst,
    input  logic                   stop,
    input  logic                   cfg_valid,
    output logic                   cfg_ready,
    input  logic [COUNT_W-1:0]     cfg_period,
    input  logic [COUNT_W-1:0]     cfg_high_yaw,
    input  logic [COUNT_W-1:0]     cfg_high_pitch,
    input  logic [COUNT_W-1:0]     cfg_high_speed,
    input  logic [TAG_W-1:0]       cfg_tag,
    output logic                   accepted,
    output logic                   rejected,
    output logic                   applied,
    output logic                   frame_start,
    output logic                   running,
    output logic                   pending,
    output logic [2:0]             pwm,
    output logic [COUNT_W-1:0]     active_period,
    output logic [COUNT_W-1:0]     active_high_yaw,
    output logic [COUNT_W-1:0]     active_high_pitch,
    output logic [COUNT_W-1:0]     active_high_speed,
    output logic [TAG_W-1:0]       active_tag
);

    localparam logic [COUNT_W-1:0] COUNT_ZERO = '0;
    localparam logic [TAG_W-1:0]   TAG_ZERO   = '0;

    logic                         running_q;
    logic                         pending_q;
    logic [COUNT_W-1:0]           phase_q;
    logic [COUNT_W-1:0]           active_period_q;
    logic [COUNT_W-1:0]           active_high_yaw_q;
    logic [COUNT_W-1:0]           active_high_pitch_q;
    logic [COUNT_W-1:0]           active_high_speed_q;
    logic [TAG_W-1:0]             active_tag_q;
    logic [COUNT_W-1:0]           pending_period_q;
    logic [COUNT_W-1:0]           pending_high_yaw_q;
    logic [COUNT_W-1:0]           pending_high_pitch_q;
    logic [COUNT_W-1:0]           pending_high_speed_q;
    logic [TAG_W-1:0]             pending_tag_q;
    logic [2:0]                   pwm_q;
    logic                         accepted_q;
    logic                         rejected_q;
    logic                         applied_q;
    logic                         frame_start_q;

    logic                         boundary_now;
    logic                         apply_now;
    logic                         transfer_now;
    logic                         payload_legal;

    assign cfg_ready = !rst && !stop && !pending_q;
    assign running     = running_q;
    assign pending     = pending_q;
    assign pwm         = pwm_q;
    assign accepted    = accepted_q;
    assign rejected    = rejected_q;
    assign applied     = applied_q;
    assign frame_start = frame_start_q;
    assign active_period     = active_period_q;
    assign active_high_yaw   = active_high_yaw_q;
    assign active_high_pitch = active_high_pitch_q;
    assign active_high_speed = active_high_speed_q;
    assign active_tag        = active_tag_q;

    assign boundary_now = running_q &&
                          ((phase_q + 1'b1) == active_period_q);
    assign apply_now    = !rst && !stop && pending_q &&
                          (!running_q || boundary_now);
    assign transfer_now = cfg_valid && cfg_ready;
    assign payload_legal = (cfg_period != COUNT_ZERO) &&
                           (cfg_high_yaw <= cfg_period) &&
                           (cfg_high_pitch <= cfg_period) &&
                           (cfg_high_speed <= cfg_period);

    always_ff @(posedge clk) begin
        accepted_q    <= 1'b0;
        rejected_q    <= 1'b0;
        applied_q     <= 1'b0;
        frame_start_q <= 1'b0;

        if (rst || stop) begin
            running_q            <= 1'b0;
            pending_q            <= 1'b0;
            phase_q              <= COUNT_ZERO;
            active_period_q      <= COUNT_ZERO;
            active_high_yaw_q    <= COUNT_ZERO;
            active_high_pitch_q  <= COUNT_ZERO;
            active_high_speed_q  <= COUNT_ZERO;
            active_tag_q         <= TAG_ZERO;
            pending_period_q     <= COUNT_ZERO;
            pending_high_yaw_q   <= COUNT_ZERO;
            pending_high_pitch_q <= COUNT_ZERO;
            pending_high_speed_q <= COUNT_ZERO;
            pending_tag_q        <= TAG_ZERO;
            pwm_q                <= 3'b000;
        end else if (apply_now) begin
            running_q            <= 1'b1;
            pending_q            <= 1'b0;
            phase_q              <= COUNT_ZERO;
            active_period_q      <= pending_period_q;
            active_high_yaw_q    <= pending_high_yaw_q;
            active_high_pitch_q  <= pending_high_pitch_q;
            active_high_speed_q  <= pending_high_speed_q;
            active_tag_q         <= pending_tag_q;
            pending_period_q     <= COUNT_ZERO;
            pending_high_yaw_q   <= COUNT_ZERO;
            pending_high_pitch_q <= COUNT_ZERO;
            pending_high_speed_q <= COUNT_ZERO;
            pending_tag_q        <= TAG_ZERO;
            pwm_q                <= {pending_high_speed_q != COUNT_ZERO,
                                     pending_high_pitch_q != COUNT_ZERO,
                                     pending_high_yaw_q   != COUNT_ZERO};
            applied_q            <= 1'b1;
            frame_start_q        <= 1'b1;
        end else begin
            if (running_q) begin
                if (boundary_now) begin
                    phase_q       <= COUNT_ZERO;
                    pwm_q         <= {active_high_speed_q != COUNT_ZERO,
                                      active_high_pitch_q != COUNT_ZERO,
                                      active_high_yaw_q   != COUNT_ZERO};
                    frame_start_q <= 1'b1;
                end else begin
                    phase_q <= phase_q + 1'b1;
                    pwm_q   <= {((phase_q + 1'b1) < active_high_speed_q),
                                ((phase_q + 1'b1) < active_high_pitch_q),
                                ((phase_q + 1'b1) < active_high_yaw_q)};
                end
            end else begin
                phase_q <= COUNT_ZERO;
                pwm_q   <= 3'b000;
            end

            if (transfer_now) begin
                if (payload_legal) begin
                    accepted_q           <= 1'b1;
                    pending_q            <= 1'b1;
                    pending_period_q     <= cfg_period;
                    pending_high_yaw_q   <= cfg_high_yaw;
                    pending_high_pitch_q <= cfg_high_pitch;
                    pending_high_speed_q <= cfg_high_speed;
                    pending_tag_q        <= cfg_tag;
                end else begin
                    rejected_q <= 1'b1;
                end
            end
        end
    end

    // Parameter rejection is a simulator diagnostic, not synthesized hardware.
    // synthesis translate_off
    generate
        if ((COUNT_W < 2) || (COUNT_W > 32) || (TAG_W < 1) || (TAG_W > 64)) begin : g_param_guard
            initial begin
                $fatal(1,
                       "ATOMIC_PWM_UNSUPPORTED_PARAMETERS COUNT_W=%0d TAG_W=%0d",
                       COUNT_W, TAG_W);
            end
        end
    endgenerate
    // synthesis translate_on

endmodule
