// deepeye_pwm_applied_capture - internal actual-application capture window.
//
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Work: B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1
// Operation: B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Contract pin: f5989cd5defce561f9ba98e6b18fc2682945f0a2.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// CANDIDATE-ONLY internal synchronous composition. It defines no public ABI,
// register, pin, clock rate, physical source, motion authority, CDC/RDC or
// board contract. sample_levels is the only raw measurement source.

module deepeye_pwm_applied_capture #(
    parameter integer COUNT_W   = 32,
    parameter integer WITNESS_W = 64,
    parameter integer TAG_W     = 32,
    localparam integer COUNT_AW = (COUNT_W < 2) ? 2 :
                                  ((COUNT_W > 32) ? 32 : COUNT_W),
    localparam integer WITNESS_AW = (WITNESS_W < 2) ? 2 :
                                    ((WITNESS_W > 64) ? 64 : WITNESS_W),
    localparam integer TAG_AW = (TAG_W < 1) ? 1 :
                                ((TAG_W > 64) ? 64 : TAG_W)
) (
    input  logic                    clk,
    input  logic                    rst,
    input  logic                    stop,
    input  logic                    cfg_valid,
    output logic                    cfg_ready,
    input  logic [COUNT_AW-1:0]     cfg_period,
    input  logic [COUNT_AW-1:0]     cfg_high_yaw,
    input  logic [COUNT_AW-1:0]     cfg_high_pitch,
    input  logic [COUNT_AW-1:0]     cfg_high_speed,
    input  logic [TAG_AW-1:0]       cfg_tag,
    input  logic [2:0]              sample_levels,
    input  logic                    out_ready,
    output logic                    accepted,
    output logic                    rejected,
    output logic                    applied,
    output logic                    frame_start,
    output logic                    running,
    output logic                    pending,
    output logic [2:0]              pwm,
    output logic [COUNT_AW-1:0]     active_period,
    output logic [COUNT_AW-1:0]     active_high_yaw,
    output logic [COUNT_AW-1:0]     active_high_pitch,
    output logic [COUNT_AW-1:0]     active_high_speed,
    output logic [TAG_AW-1:0]       active_tag,
    output logic                    window_active,
    output logic                    window_started,
    output logic                    capture_armed,
    output logic                    out_valid,
    output logic [COUNT_AW-1:0]     out_period,
    output logic [COUNT_AW-1:0]     out_high0,
    output logic [COUNT_AW-1:0]     out_high1,
    output logic [COUNT_AW-1:0]     out_high2,
    output logic [WITNESS_AW-1:0]   out_start,
    output logic [WITNESS_AW-1:0]   out_end,
    output logic [TAG_AW-1:0]       out_tag,
    output logic [COUNT_AW-1:0]     expected_period,
    output logic [COUNT_AW-1:0]     expected_high0,
    output logic [COUNT_AW-1:0]     expected_high1,
    output logic [COUNT_AW-1:0]     expected_high2,
    output logic [TAG_AW-1:0]       expected_tag,
    output logic [3:0]              raw_fault_events,
    output logic                    failure_event,
    output logic [2:0]              failure_code
);

    localparam logic [COUNT_AW-1:0]   COUNT_ZERO = '0;
    localparam logic [TAG_AW-1:0]     TAG_ZERO   = '0;

    logic                    g_cfg_ready;
    logic                    g_applied;
    logic                    g_frame_start;
    logic                    g_running;
    logic                    g_pending;
    logic [2:0]              g_pwm;
    logic [COUNT_AW-1:0]     g_active_period;
    logic [COUNT_AW-1:0]     g_active_high_yaw;
    logic [COUNT_AW-1:0]     g_active_high_pitch;
    logic [COUNT_AW-1:0]     g_active_high_speed;
    logic [TAG_AW-1:0]       g_active_tag;

    logic                    c_armed;
    logic                    c_out_valid;
    logic [COUNT_AW-1:0]     c_out_period;
    logic [COUNT_AW-1:0]     c_out_high0;
    logic [COUNT_AW-1:0]     c_out_high1;
    logic [COUNT_AW-1:0]     c_out_high2;
    logic [WITNESS_AW-1:0]   c_out_start;
    logic [WITNESS_AW-1:0]   c_out_end;
    logic [TAG_AW-1:0]       c_out_tag;
    logic                    c_incoherent_event;
    logic                    c_period_overflow_event;
    logic                    c_witness_overflow_event;
    logic                    c_overrun_event;
    logic                    c_incoherent_seen;
    logic                    c_period_overflow_seen;
    logic                    c_witness_overflow_seen;
    logic                    c_overrun_seen;
    logic [COUNT_AW-1:0]     c_fault_count;

    logic                    window_active_q;
    logic                    window_started_q;
    logic                    failure_event_q;
    logic [2:0]              failure_code_q;
    logic [COUNT_AW-1:0]     expected_period_q;
    logic [COUNT_AW-1:0]     expected_high0_q;
    logic [COUNT_AW-1:0]     expected_high1_q;
    logic [COUNT_AW-1:0]     expected_high2_q;
    logic [TAG_AW-1:0]       expected_tag_q;

    logic                    transfer_now;
    logic                    eligible_application;
    logic                    intentional_boundary;
    logic                    capture_arm;
    logic                    capture_stop;
    logic                    capture_rearm;
    logic                    transport_window;
    logic                    raw_fault;
    logic                    raw_equal;
    logic                    capture_out_ready;

    deepeye_atomic_pwm #(
        .COUNT_W(COUNT_AW),
        .TAG_W(TAG_AW)
    ) u_generator (
        .clk(clk),
        .rst(rst),
        .stop(stop),
        .cfg_valid(cfg_valid),
        .cfg_ready(g_cfg_ready),
        .cfg_period(cfg_period),
        .cfg_high_yaw(cfg_high_yaw),
        .cfg_high_pitch(cfg_high_pitch),
        .cfg_high_speed(cfg_high_speed),
        .cfg_tag(cfg_tag),
        .accepted(accepted),
        .rejected(rejected),
        .applied(g_applied),
        .frame_start(g_frame_start),
        .running(g_running),
        .pending(g_pending),
        .pwm(g_pwm),
        .active_period(g_active_period),
        .active_high_yaw(g_active_high_yaw),
        .active_high_pitch(g_active_high_pitch),
        .active_high_speed(g_active_high_speed),
        .active_tag(g_active_tag)
    );

    deepeye_pwm_coherent_capture #(
        .COUNT_W(COUNT_AW),
        .WITNESS_W(WITNESS_AW),
        .TAG_W(TAG_AW)
    ) u_capture (
        .clk(clk),
        .rst(rst),
        .stop(capture_stop),
        .rearm(capture_rearm),
        .sample_levels(sample_levels),
        .window_tag(g_active_tag),
        .out_ready(capture_out_ready),
        .armed(c_armed),
        .out_valid(c_out_valid),
        .out_period(c_out_period),
        .out_high0(c_out_high0),
        .out_high1(c_out_high1),
        .out_high2(c_out_high2),
        .out_start(c_out_start),
        .out_end(c_out_end),
        .out_tag(c_out_tag),
        .incoherent_event(c_incoherent_event),
        .period_overflow_event(c_period_overflow_event),
        .witness_overflow_event(c_witness_overflow_event),
        .overrun_event(c_overrun_event),
        .incoherent_seen(c_incoherent_seen),
        .period_overflow_seen(c_period_overflow_seen),
        .witness_overflow_seen(c_witness_overflow_seen),
        .overrun_seen(c_overrun_seen),
        .fault_count(c_fault_count)
    );

    assign cfg_ready      = g_cfg_ready;
    assign applied        = g_applied;
    assign frame_start    = g_frame_start;
    assign running        = g_running;
    assign pending        = g_pending;
    assign pwm            = g_pwm;
    assign active_period  = g_active_period;
    assign active_high_yaw    = g_active_high_yaw;
    assign active_high_pitch  = g_active_high_pitch;
    assign active_high_speed  = g_active_high_speed;
    assign active_tag         = g_active_tag;

    assign window_active  = window_active_q;
    assign window_started = window_started_q;
    assign capture_armed  = c_armed;
    assign out_period     = c_out_period;
    assign out_high0      = c_out_high0;
    assign out_high1      = c_out_high1;
    assign out_high2      = c_out_high2;
    assign out_start      = c_out_start;
    assign out_end        = c_out_end;
    assign out_tag        = c_out_tag;
    assign expected_period     = expected_period_q;
    assign expected_high0      = expected_high0_q;
    assign expected_high1      = expected_high1_q;
    assign expected_high2      = expected_high2_q;
    assign expected_tag        = expected_tag_q;
    assign failure_event       = failure_event_q;
    assign failure_code        = failure_code_q;
    assign raw_fault_events    = {c_overrun_event,
                                  c_witness_overflow_event,
                                  c_period_overflow_event,
                                  c_incoherent_event};

    assign transfer_now = cfg_valid && g_cfg_ready;
    assign eligible_application =
        (g_active_period >= 2) &&
        (g_active_high_yaw != COUNT_ZERO) &&
        (g_active_high_yaw < g_active_period) &&
        (g_active_high_pitch != COUNT_ZERO) &&
        (g_active_high_pitch < g_active_period) &&
        (g_active_high_speed != COUNT_ZERO) &&
        (g_active_high_speed < g_active_period);
    assign intentional_boundary =
        rst || stop || g_pending || !g_running;
    assign capture_arm = !intentional_boundary && g_applied &&
                         eligible_application;
    assign capture_stop = intentional_boundary ||
                          (g_applied && !eligible_application) ||
                          (!window_active_q && !capture_arm);
    assign capture_rearm = capture_arm;
    assign transport_window = window_active_q && !intentional_boundary &&
                              !g_applied;
    assign raw_fault = c_incoherent_event || c_period_overflow_event ||
                       c_witness_overflow_event || c_overrun_event;
    assign raw_equal = (c_out_period == expected_period_q) &&
                       (c_out_high0 == expected_high0_q) &&
                       (c_out_high1 == expected_high1_q) &&
                       (c_out_high2 == expected_high2_q) &&
                       (c_out_tag == expected_tag_q);
    assign out_valid = transport_window && c_armed && !raw_fault &&
                       c_out_valid && raw_equal;
    assign capture_out_ready = transport_window && c_armed && !raw_fault &&
                               raw_equal && out_ready;

    always_ff @(posedge clk) begin
        window_started_q <= 1'b0;
        failure_event_q  <= 1'b0;

        if (rst || stop) begin
            window_active_q     <= 1'b0;
            expected_period_q   <= COUNT_ZERO;
            expected_high0_q    <= COUNT_ZERO;
            expected_high1_q    <= COUNT_ZERO;
            expected_high2_q    <= COUNT_ZERO;
            expected_tag_q      <= TAG_ZERO;
            failure_code_q      <= 3'd0;
        end else if (transfer_now || g_pending || !g_running) begin
            window_active_q     <= 1'b0;
            expected_period_q   <= COUNT_ZERO;
            expected_high0_q    <= COUNT_ZERO;
            expected_high1_q    <= COUNT_ZERO;
            expected_high2_q    <= COUNT_ZERO;
            expected_tag_q      <= TAG_ZERO;
            failure_code_q      <= 3'd0;
        end else if (g_applied) begin
            failure_code_q <= 3'd0;
            if (eligible_application) begin
                window_active_q   <= 1'b1;
                expected_period_q <= g_active_period;
                expected_high0_q  <= g_active_high_yaw;
                expected_high1_q  <= g_active_high_pitch;
                expected_high2_q  <= g_active_high_speed;
                expected_tag_q    <= g_active_tag;
                window_started_q  <= 1'b1;
            end else begin
                window_active_q   <= 1'b0;
                expected_period_q <= COUNT_ZERO;
                expected_high0_q  <= COUNT_ZERO;
                expected_high1_q  <= COUNT_ZERO;
                expected_high2_q  <= COUNT_ZERO;
                expected_tag_q    <= TAG_ZERO;
                failure_event_q   <= 1'b1;
                failure_code_q    <= 3'd6;
            end

        end else if (window_active_q) begin
            if (c_witness_overflow_event) begin
                window_active_q   <= 1'b0;
                expected_period_q <= COUNT_ZERO;
                expected_high0_q  <= COUNT_ZERO;
                expected_high1_q  <= COUNT_ZERO;
                expected_high2_q  <= COUNT_ZERO;
                expected_tag_q    <= TAG_ZERO;
                failure_event_q   <= 1'b1;
                failure_code_q    <= 3'd4;
            end else if (c_period_overflow_event) begin
                window_active_q   <= 1'b0;
                expected_period_q <= COUNT_ZERO;
                expected_high0_q  <= COUNT_ZERO;
                expected_high1_q  <= COUNT_ZERO;
                expected_high2_q  <= COUNT_ZERO;
                expected_tag_q    <= TAG_ZERO;
                failure_event_q   <= 1'b1;
                failure_code_q    <= 3'd3;
            end else if (c_incoherent_event) begin
                window_active_q   <= 1'b0;
                expected_period_q <= COUNT_ZERO;
                expected_high0_q  <= COUNT_ZERO;
                expected_high1_q  <= COUNT_ZERO;
                expected_high2_q  <= COUNT_ZERO;
                expected_tag_q    <= TAG_ZERO;
                failure_event_q   <= 1'b1;
                failure_code_q    <= 3'd2;
            end else if (c_overrun_event) begin
                window_active_q   <= 1'b0;
                expected_period_q <= COUNT_ZERO;
                expected_high0_q  <= COUNT_ZERO;
                expected_high1_q  <= COUNT_ZERO;
                expected_high2_q  <= COUNT_ZERO;
                expected_tag_q    <= TAG_ZERO;
                failure_event_q   <= 1'b1;
                failure_code_q    <= 3'd5;
            end else if (!c_armed) begin
                window_active_q   <= 1'b0;
                expected_period_q <= COUNT_ZERO;
                expected_high0_q  <= COUNT_ZERO;
                expected_high1_q  <= COUNT_ZERO;
                expected_high2_q  <= COUNT_ZERO;
                expected_tag_q    <= TAG_ZERO;
                failure_event_q   <= 1'b1;
                failure_code_q    <= 3'd7;
            end else if (c_out_valid && !raw_equal) begin
                window_active_q   <= 1'b0;
                expected_period_q <= COUNT_ZERO;
                expected_high0_q  <= COUNT_ZERO;
                expected_high1_q  <= COUNT_ZERO;
                expected_high2_q  <= COUNT_ZERO;
                expected_tag_q    <= TAG_ZERO;
                failure_event_q   <= 1'b1;
                failure_code_q    <= 3'd1;
            end
        end else begin
            window_active_q   <= 1'b0;
            expected_period_q <= COUNT_ZERO;
            expected_high0_q  <= COUNT_ZERO;
            expected_high1_q  <= COUNT_ZERO;
            expected_high2_q  <= COUNT_ZERO;
            expected_tag_q    <= TAG_ZERO;
        end
    end
    // synthesis translate_off
    initial begin
        if ((COUNT_W < 2) || (COUNT_W > 32) ||
            (WITNESS_W < 2) || (WITNESS_W > 64) ||
            (TAG_W < 1) || (TAG_W > 64)) begin
            $display("DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM COUNT_W=%0d WITNESS_W=%0d TAG_W=%0d SAFE_COUNT_W=%0d SAFE_WITNESS_W=%0d SAFE_TAG_W=%0d",
                     COUNT_W, WITNESS_W, TAG_W,
                     COUNT_AW, WITNESS_AW, TAG_AW);
            $fatal(1, "DEEPEYE_APPLIED_CAPTURE_INVALID_PARAM unsupported widths");
        end
    end
    // synthesis translate_on

endmodule
