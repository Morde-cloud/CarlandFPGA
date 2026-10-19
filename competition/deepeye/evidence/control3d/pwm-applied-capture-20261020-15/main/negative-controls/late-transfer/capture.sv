// deepeye_pwm_coherent_capture - internal synchronous three-channel raw
// coherent-capture candidate.
//
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Work: B-PWM-COHERENT-CAPTURE-RTL-20261020-14-v1
// Product operation: B-DEEPEYE-PWM-COHERENT-CAPTURE-20261020-14
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Contract pin: f5989cd5defce561f9ba98e6b18fc2682945f0a2.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
// Normative scope SHA256:
// f2d8ed287848e536b140629f3f30f7105d2171a6cc0c00be2186d09c9115331d.
//
// CANDIDATE-ONLY internal synchronous sampled-level capture. This file
// defines no public ABI, register address, pin, clock frequency, analog/PWM
// profile, source liveness, execution proof, motion authority, CDC/RDC
// contract, synthesis result, implementation result or board result.
//
// One shared capture state machine observes sample_levels[2:0] after an
// explicit rearm. It accepts a record only when a common observed rising
// starts the interval, every lane has a first fall strictly inside that
// interval, and the same three lanes rise together at the closing witness.
// The module stores one raw result slot. out_valid means only that a record is
// queued for transport; it grants no freshness, waveform validity or motion
// eligibility.

module deepeye_pwm_coherent_capture #(
    parameter integer COUNT_W    = 32,
    parameter integer WITNESS_W  = 64,
    parameter integer TAG_W      = 32,
    localparam integer COUNT_AW  = (COUNT_W < 2) ? 2 :
                                   ((COUNT_W > 32) ? 32 : COUNT_W),
    localparam integer WITNESS_AW= (WITNESS_W < 2) ? 2 :
                                   ((WITNESS_W > 64) ? 64 : WITNESS_W),
    localparam integer TAG_AW    = (TAG_W < 1) ? 1 :
                                   ((TAG_W > 64) ? 64 : TAG_W)
) (
    input  logic                     clk,
    input  logic                     rst,
    input  logic                     stop,
    input  logic                     rearm,
    input  logic [2:0]               sample_levels,
    input  logic [TAG_AW-1:0]        window_tag,
    input  logic                     out_ready,
    output logic                     armed,
    output logic                     out_valid,
    output logic [COUNT_AW-1:0]      out_period,
    output logic [COUNT_AW-1:0]      out_high0,
    output logic [COUNT_AW-1:0]      out_high1,
    output logic [COUNT_AW-1:0]      out_high2,
    output logic [WITNESS_AW-1:0]    out_start,
    output logic [WITNESS_AW-1:0]    out_end,
    output logic [TAG_AW-1:0]        out_tag,
    output logic                     incoherent_event,
    output logic                     period_overflow_event,
    output logic                     witness_overflow_event,
    output logic                     overrun_event,
    output logic                     incoherent_seen,
    output logic                     period_overflow_seen,
    output logic                     witness_overflow_seen,
    output logic                     overrun_seen,
    output logic [COUNT_AW-1:0]      fault_count
);

    localparam logic [COUNT_AW-1:0]   COUNT_ZERO = '0;
    localparam logic [COUNT_AW-1:0]   COUNT_MAX  = '1;
    localparam logic [WITNESS_AW-1:0] WIT_ZERO   = '0;
    localparam logic [WITNESS_AW-1:0] WIT_MAX    = '1;
    localparam logic [TAG_AW-1:0]     TAG_ZERO   = '0;
    localparam logic [2:0]            RISE_NONE  = 3'b000;
    localparam logic [2:0]            RISE_ALL   = 3'b111;
    localparam logic [2:0]            FALL_NONE  = 3'b000;
    localparam logic [2:0]            FALL_ALL   = 3'b111;

    logic                     armed_q;
    logic [2:0]               previous_q;
    logic [WITNESS_AW-1:0]    tick_q;

    logic                     partial_valid_q;
    logic [WITNESS_AW-1:0]    partial_start_q;
    logic [COUNT_AW-1:0]      partial_age_q;
    logic [2:0]               fall_seen_q;
    logic [COUNT_AW-1:0]      high0_q;
    logic [COUNT_AW-1:0]      high1_q;
    logic [COUNT_AW-1:0]      high2_q;
    logic [TAG_AW-1:0]        window_tag_q;

    logic                     slot_valid_q;
    logic [COUNT_AW-1:0]      slot_period_q;
    logic [COUNT_AW-1:0]      slot_high0_q;
    logic [COUNT_AW-1:0]      slot_high1_q;
    logic [COUNT_AW-1:0]      slot_high2_q;
    logic [WITNESS_AW-1:0]    slot_start_q;
    logic [WITNESS_AW-1:0]    slot_end_q;
    logic [TAG_AW-1:0]        slot_tag_q;

    logic                     incoherent_event_q;
    logic                     period_overflow_event_q;
    logic                     witness_overflow_event_q;
    logic                     overrun_event_q;
    logic                     incoherent_seen_q;
    logic                     period_overflow_seen_q;
    logic                     witness_overflow_seen_q;
    logic                     overrun_seen_q;
    logic [COUNT_AW-1:0]      fault_count_q;

    assign armed                 = armed_q;
    assign out_valid             = slot_valid_q && !rst && !stop && !rearm;
    assign out_period            = slot_period_q;
    assign out_high0             = slot_high0_q;
    assign out_high1             = slot_high1_q;
    assign out_high2             = slot_high2_q;
    assign out_start             = slot_start_q;
    assign out_end               = slot_end_q;
    assign out_tag               = slot_tag_q;
    assign incoherent_event      = incoherent_event_q;
    assign period_overflow_event = period_overflow_event_q;
    assign witness_overflow_event= witness_overflow_event_q;
    assign overrun_event         = overrun_event_q;
    assign incoherent_seen       = incoherent_seen_q;
    assign period_overflow_seen  = period_overflow_seen_q;
    assign witness_overflow_seen = witness_overflow_seen_q;
    assign overrun_seen          = overrun_seen_q;
    assign fault_count           = fault_count_q;

    // Unsupported widths are simulation-only guard cases. Port and internal
    // widths above are clamped so a zero, negative or oversized parameter
    // reaches this diagnostic instead of causing an unrelated range error.
    // synthesis translate_off
    initial begin
        if ((COUNT_W < 2) || (COUNT_W > 32) ||
            (WITNESS_W < 2) || (WITNESS_W > 64) ||
            (TAG_W < 1) || (TAG_W > 64)) begin
            $display("DEEPEYE_COHERENT_INVALID_PARAM COUNT_W=%0d WITNESS_W=%0d TAG_W=%0d",
                     COUNT_W, WITNESS_W, TAG_W);
            $fatal(1, "DEEPEYE_COHERENT_INVALID_PARAM unsupported widths");
        end
    end
    // synthesis translate_on

    always_ff @(posedge clk) begin
        logic [2:0]            rise_mask;
        logic [2:0]            fall_mask;
        logic [WITNESS_AW-1:0] witness_now;
        logic [COUNT_AW-1:0]   elapsed;
        logic                  coherent_candidate;

        incoherent_event_q       <= 1'b0;
        period_overflow_event_q  <= 1'b0;
        witness_overflow_event_q <= 1'b0;
        overrun_event_q          <= 1'b0;

        if (rst || stop) begin
            armed_q             <= 1'b0;
            previous_q          <= 3'b000;
            tick_q              <= WIT_ZERO;
            partial_valid_q     <= 1'b0;
            partial_start_q     <= WIT_ZERO;
            partial_age_q       <= COUNT_ZERO;
            fall_seen_q         <= FALL_NONE;
            high0_q             <= COUNT_ZERO;
            high1_q             <= COUNT_ZERO;
            high2_q             <= COUNT_ZERO;
            window_tag_q        <= TAG_ZERO;
            slot_valid_q        <= 1'b0;
            slot_period_q       <= COUNT_ZERO;
            slot_high0_q        <= COUNT_ZERO;
            slot_high1_q        <= COUNT_ZERO;
            slot_high2_q        <= COUNT_ZERO;
            slot_start_q        <= WIT_ZERO;
            slot_end_q          <= WIT_ZERO;
            slot_tag_q          <= TAG_ZERO;
            incoherent_seen_q   <= 1'b0;
            period_overflow_seen_q <= 1'b0;
            witness_overflow_seen_q <= 1'b0;
            overrun_seen_q      <= 1'b0;
            fault_count_q       <= COUNT_ZERO;
        end else if (rearm) begin
            armed_q             <= 1'b1;
            previous_q          <= sample_levels;
            tick_q              <= WIT_ZERO;
            partial_valid_q     <= 1'b0;
            partial_start_q     <= WIT_ZERO;
            partial_age_q       <= COUNT_ZERO;
            fall_seen_q         <= FALL_NONE;
            high0_q             <= COUNT_ZERO;
            high1_q             <= COUNT_ZERO;
            high2_q             <= COUNT_ZERO;
            window_tag_q        <= window_tag;
            slot_valid_q        <= 1'b0;
            slot_period_q       <= COUNT_ZERO;
            slot_high0_q        <= COUNT_ZERO;
            slot_high1_q        <= COUNT_ZERO;
            slot_high2_q        <= COUNT_ZERO;
            slot_start_q        <= WIT_ZERO;
            slot_end_q          <= WIT_ZERO;
            slot_tag_q          <= TAG_ZERO;
            incoherent_seen_q   <= 1'b0;
            period_overflow_seen_q <= 1'b0;
            witness_overflow_seen_q <= 1'b0;
            overrun_seen_q      <= 1'b0;
            fault_count_q       <= COUNT_ZERO;
        end else begin
            // A queued record is transport-only and retires independently of
            // capture state. A fresh candidate is not visible for consumption
            // until a later edge because this decision uses old slot state.
            if (slot_valid_q && out_ready) begin
                slot_valid_q  <= 1'b0;
                slot_period_q <= COUNT_ZERO;
                slot_high0_q  <= COUNT_ZERO;
                slot_high1_q  <= COUNT_ZERO;
                slot_high2_q  <= COUNT_ZERO;
                slot_start_q  <= WIT_ZERO;
                slot_end_q    <= WIT_ZERO;
                slot_tag_q    <= TAG_ZERO;
            end

            if (armed_q) begin
                if (tick_q == WIT_MAX) begin
                    // Witness namespace exhaustion outranks every candidate
                    // fault. No TMAX+1 witness is manufactured or wrapped.
                    witness_overflow_event_q <= 1'b1;
                    witness_overflow_seen_q  <= 1'b1;
                    armed_q                  <= 1'b0;
                    partial_valid_q          <= 1'b0;
                    if (fault_count_q != COUNT_MAX) begin
                        fault_count_q <= fault_count_q + 1'b1;
                    end
                end else begin
                    witness_now = tick_q + 1'b1;
                    tick_q      <= witness_now;
                    previous_q  <= sample_levels;
                    rise_mask   = ((~previous_q) & sample_levels) & 3'b111;
                    fall_mask   = (previous_q & (~sample_levels)) & 3'b111;

                    if (!partial_valid_q) begin
                        if (rise_mask == RISE_ALL) begin // MUTATION_IDLE_RELAXED_COMMON
                            partial_valid_q <= 1'b1;
                            partial_start_q <= witness_now;
                            partial_age_q   <= COUNT_ZERO;
                            fall_seen_q     <= FALL_NONE;
                            high0_q         <= COUNT_ZERO;
                            high1_q         <= COUNT_ZERO;
                            high2_q         <= COUNT_ZERO;
                        end else if (rise_mask != RISE_NONE) begin
                            // A proper-subset rise is an observed unequal start.
                            incoherent_event_q <= 1'b1;
                            incoherent_seen_q  <= 1'b1;
                            if (fault_count_q != COUNT_MAX) begin
                                fault_count_q <= fault_count_q + 1'b1;
                            end
                        end
                    end else if (partial_age_q == COUNT_MAX) begin
                        // The would-be interval is CMAX+1. The overflowing
                        // edge may restart only from a genuine common rise.
                        period_overflow_event_q <= 1'b1;
                        period_overflow_seen_q  <= 1'b1;
                        partial_valid_q         <= 1'b0;
                        if (fault_count_q != COUNT_MAX) begin
                            fault_count_q <= fault_count_q + 1'b1;
                        end
                        if (rise_mask == RISE_ALL) begin
                            partial_valid_q <= 1'b1;
                            partial_start_q <= witness_now;
                            partial_age_q   <= COUNT_ZERO;
                            fall_seen_q     <= FALL_NONE;
                            high0_q         <= COUNT_ZERO;
                            high1_q         <= COUNT_ZERO;
                            high2_q         <= COUNT_ZERO;
                        end
                    end else begin
                        elapsed = partial_age_q + 1'b1;

                        if (rise_mask == RISE_NONE) begin
                            // Record each lane's first fall only at its actual
                            // elapsed count. Later falls do not rewrite it.
                            if (!fall_seen_q[0] && fall_mask[0]) begin
                                fall_seen_q[0] <= 1'b1;
                                high0_q        <= elapsed;
                            end
                            if (!fall_seen_q[1] && fall_mask[1]) begin
                                fall_seen_q[1] <= 1'b1;
                                high1_q        <= elapsed;
                            end
                            if (!fall_seen_q[2] && fall_mask[2]) begin
                                fall_seen_q[2] <= 1'b1;
                                high2_q        <= elapsed;
                            end
                            partial_age_q <= elapsed;
                        end else if (rise_mask != RISE_ALL) begin
                            // Abandon every old partial field. No earlier lane
                            // interval may be spliced into a later frame.
                            incoherent_event_q <= 1'b1;
                            incoherent_seen_q  <= 1'b1;
                            partial_valid_q    <= 1'b0; // MUTATION_ABORT_PARTIAL
                            if (fault_count_q != COUNT_MAX) begin
                                fault_count_q <= fault_count_q + 1'b1;
                            end
                        end else begin
                            coherent_candidate = (fall_seen_q == FALL_ALL) &&
                                                 (high0_q != COUNT_ZERO) &&
                                                 (high0_q < elapsed) &&
                                                 (high1_q != COUNT_ZERO) &&
                                                 (high1_q < elapsed) &&
                                                 (high2_q != COUNT_ZERO) &&
                                                 (high2_q < elapsed);

                            if (coherent_candidate) begin
                                if (!slot_valid_q || out_ready) begin
                                    slot_valid_q  <= 1'b1;
                                    slot_period_q <= elapsed;
                                    slot_high0_q  <= high0_q;
                                    slot_high1_q  <= high1_q;
                                    slot_high2_q  <= high2_q;
                                    slot_start_q  <= partial_start_q;
                                    slot_end_q    <= witness_now;
                                    slot_tag_q    <= window_tag_q;
                                end else begin
                                    overrun_event_q <= 1'b1;
                                    overrun_seen_q  <= 1'b1;
                                    if (fault_count_q != COUNT_MAX) begin
                                        fault_count_q <= fault_count_q + 1'b1;
                                    end
                                end
                            end else begin
                                incoherent_event_q <= 1'b1;
                                incoherent_seen_q  <= 1'b1;
                                if (fault_count_q != COUNT_MAX) begin
                                    fault_count_q <= fault_count_q + 1'b1;
                                end
                            end

                            // The closing common rise always starts the next
                            // candidate-only partial, including a rejected one.
                            partial_valid_q <= 1'b1;
                            partial_start_q <= witness_now;
                            partial_age_q   <= COUNT_ZERO;
                            fall_seen_q     <= FALL_NONE;
                            high0_q         <= COUNT_ZERO;
                            high1_q         <= COUNT_ZERO;
                            high2_q         <= COUNT_ZERO;
                        end
                    end
                end
            end
        end
    end

endmodule
