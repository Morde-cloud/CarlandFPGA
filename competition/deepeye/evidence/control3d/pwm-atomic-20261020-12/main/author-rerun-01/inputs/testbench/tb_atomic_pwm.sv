// Self-checking author testbench for the internal atomic PWM candidate.
//
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Work: B-ATOMIC-PWM-RTL-20261020-12-v1
// Product operation: B-DEEPEYE-PWM-ATOMIC-20261020-12
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Contract pin: f5989cd5defce561f9ba98e6b18fc2682945f0a2.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// CANDIDATE-ONLY public-port verification. This testbench does not establish
// synthesis, timing closure, CDC/RDC, public ABI, board or formal-card results.
// The frame-boundary atomic scheduling is a B internal design choice for this
// increment, not a quoted frozen public ABI.

`timescale 1ns / 1ps

module atomic_pwm_probe #(
    parameter integer COUNT_W = 32,
    parameter integer TAG_W = 32,
    parameter string LABEL = "p"
) (
    input logic clk,
    input logic rst,
    input logic stop,
    input logic cfg_valid,
    input logic [31:0] cfg_period,
    input logic [31:0] cfg_high_yaw,
    input logic [31:0] cfg_high_pitch,
    input logic [31:0] cfg_high_speed,
    input logic [63:0] cfg_tag
);
    logic [COUNT_W-1:0] eff_period;
    logic [COUNT_W-1:0] eff_high_yaw;
    logic [COUNT_W-1:0] eff_high_pitch;
    logic [COUNT_W-1:0] eff_high_speed;
    logic [TAG_W-1:0] eff_tag;

    logic cfg_ready;
    logic accepted;
    logic rejected;
    logic applied;
    logic frame_start;
    logic running;
    logic pending;
    logic [2:0] pwm;
    logic [COUNT_W-1:0] active_period;
    logic [COUNT_W-1:0] active_high_yaw;
    logic [COUNT_W-1:0] active_high_pitch;
    logic [COUNT_W-1:0] active_high_speed;
    logic [TAG_W-1:0] active_tag;

    assign eff_period = cfg_period[COUNT_W-1:0];
    assign eff_high_yaw = cfg_high_yaw[COUNT_W-1:0];
    assign eff_high_pitch = cfg_high_pitch[COUNT_W-1:0];
    assign eff_high_speed = cfg_high_speed[COUNT_W-1:0];
    assign eff_tag = cfg_tag[TAG_W-1:0];

    deepeye_atomic_pwm #(
        .COUNT_W(COUNT_W),
        .TAG_W(TAG_W)
    ) dut (
        .clk(clk), .rst(rst), .stop(stop),
        .cfg_valid(cfg_valid), .cfg_ready(cfg_ready),
        .cfg_period(eff_period), .cfg_high_yaw(eff_high_yaw),
        .cfg_high_pitch(eff_high_pitch), .cfg_high_speed(eff_high_speed),
        .cfg_tag(eff_tag), .accepted(accepted), .rejected(rejected),
        .applied(applied), .frame_start(frame_start), .running(running),
        .pending(pending), .pwm(pwm), .active_period(active_period),
        .active_high_yaw(active_high_yaw), .active_high_pitch(active_high_pitch),
        .active_high_speed(active_high_speed), .active_tag(active_tag)
    );

    integer edge_count = 0;
    integer error_count = 0;
    integer check_count = 0;
    integer completed_frames = 0;
    integer aborted_frames = 0;
    integer accepted_count = 0;
    integer rejected_count = 0;
    integer applied_count = 0;
    integer frame_start_count = 0;
    integer busy_valid_count = 0;
    integer high_yaw_count = 0;
    integer high_pitch_count = 0;
    integer high_speed_count = 0;
    integer last_frame_ticks = 0;
    integer last_frame_yaw = 0;
    integer last_frame_pitch = 0;
    integer last_frame_speed = 0;

    logic model_running = 1'b0;
    logic model_pending = 1'b0;
    logic [COUNT_W-1:0] model_phase = {COUNT_W{1'b0}};
    logic [COUNT_W-1:0] model_ap = {COUNT_W{1'b0}};
    logic [COUNT_W-1:0] model_ahy = {COUNT_W{1'b0}};
    logic [COUNT_W-1:0] model_ahp = {COUNT_W{1'b0}};
    logic [COUNT_W-1:0] model_ahs = {COUNT_W{1'b0}};
    logic [TAG_W-1:0] model_atag = {TAG_W{1'b0}};
    logic [COUNT_W-1:0] model_pp = {COUNT_W{1'b0}};
    logic [COUNT_W-1:0] model_phy = {COUNT_W{1'b0}};
    logic [COUNT_W-1:0] model_php = {COUNT_W{1'b0}};
    logic [COUNT_W-1:0] model_phs = {COUNT_W{1'b0}};
    logic [TAG_W-1:0] model_ptag = {TAG_W{1'b0}};

    logic exp_accepted;
    logic exp_rejected;
    logic exp_applied;
    logic exp_frame_start;
    logic exp_running;
    logic exp_pending;
    logic [2:0] exp_pwm;
    logic [COUNT_W-1:0] exp_ap;
    logic [COUNT_W-1:0] exp_ahy;
    logic [COUNT_W-1:0] exp_ahp;
    logic [COUNT_W-1:0] exp_ahs;
    logic [TAG_W-1:0] exp_atag;
    logic [COUNT_W-1:0] next_phase;
    logic next_running;
    logic next_pending;
    logic [COUNT_W-1:0] next_ap;
    logic [COUNT_W-1:0] next_ahy;
    logic [COUNT_W-1:0] next_ahp;
    logic [COUNT_W-1:0] next_ahs;
    logic [TAG_W-1:0] next_atag;
    logic [COUNT_W-1:0] next_pp;
    logic [COUNT_W-1:0] next_phy;
    logic [COUNT_W-1:0] next_php;
    logic [COUNT_W-1:0] next_phs;
    logic [TAG_W-1:0] next_ptag;
    logic [2:0] next_pwm;
    logic apply_edge;
    logic boundary_edge;
    logic legal_payload;
    logic abort_edge;

    integer frame_active = 0;
    integer frame_ticks = 0;
    integer frame_yaw = 0;
    integer frame_pitch = 0;
    integer frame_speed = 0;
    integer mon_period = 0;
    integer mon_yaw = 0;
    integer mon_pitch = 0;
    integer mon_speed = 0;

    task automatic check(input logic condition, input string what);
        begin
            check_count = check_count + 1;
            if (condition !== 1'b1) begin
                error_count = error_count + 1;
                $display("APWM_CHECK_FAIL probe=%s check=%s edge=%0d time=%0t",
                         LABEL, what, edge_count, $time);
            end
        end
    endtask

    always @(posedge clk) begin
        edge_count = edge_count + 1;
        abort_edge = rst || stop;
        check(cfg_ready === (!rst && !stop && !model_pending),
              "cfg_ready pre-edge");
        if (cfg_valid && !cfg_ready) busy_valid_count = busy_valid_count + 1;
        #1;

        exp_accepted = 1'b0;
        exp_rejected = 1'b0;
        exp_applied = 1'b0;
        exp_frame_start = 1'b0;
        exp_pwm = 3'b000;

        next_running = model_running;
        next_pending = model_pending;
        next_phase = model_phase;
        next_ap = model_ap;
        next_ahy = model_ahy;
        next_ahp = model_ahp;
        next_ahs = model_ahs;
        next_atag = model_atag;
        next_pp = model_pp;
        next_phy = model_phy;
        next_php = model_php;
        next_phs = model_phs;
        next_ptag = model_ptag;

        boundary_edge = model_running &&
                        ((model_phase + 1'b1) == model_ap);
        apply_edge = model_pending && (!model_running || boundary_edge);
        legal_payload = (eff_period != {COUNT_W{1'b0}}) &&
                        (eff_high_yaw <= eff_period) &&
                        (eff_high_pitch <= eff_period) &&
                        (eff_high_speed <= eff_period);

        if (abort_edge) begin
            next_running = 1'b0;
            next_pending = 1'b0;
            next_phase = {COUNT_W{1'b0}};
            next_ap = {COUNT_W{1'b0}};
            next_ahy = {COUNT_W{1'b0}};
            next_ahp = {COUNT_W{1'b0}};
            next_ahs = {COUNT_W{1'b0}};
            next_atag = {TAG_W{1'b0}};
            next_pp = {COUNT_W{1'b0}};
            next_phy = {COUNT_W{1'b0}};
            next_php = {COUNT_W{1'b0}};
            next_phs = {COUNT_W{1'b0}};
            next_ptag = {TAG_W{1'b0}};
            next_pwm = 3'b000;
        end else if (apply_edge) begin
            next_running = 1'b1;
            next_pending = 1'b0;
            next_phase = {COUNT_W{1'b0}};
            next_ap = model_pp;
            next_ahy = model_phy;
            next_ahp = model_php;
            next_ahs = model_phs;
            next_atag = model_ptag;
            next_pp = {COUNT_W{1'b0}};
            next_phy = {COUNT_W{1'b0}};
            next_php = {COUNT_W{1'b0}};
            next_phs = {COUNT_W{1'b0}};
            next_ptag = {TAG_W{1'b0}};
            next_pwm = {(model_phs != {COUNT_W{1'b0}}),
                        (model_php != {COUNT_W{1'b0}}),
                        (model_phy != {COUNT_W{1'b0}})};
            exp_applied = 1'b1;
            exp_frame_start = 1'b1;
        end else if (boundary_edge) begin
            next_phase = {COUNT_W{1'b0}};
            next_pwm = {(model_ahs != {COUNT_W{1'b0}}),
                        (model_ahp != {COUNT_W{1'b0}}),
                        (model_ahy != {COUNT_W{1'b0}})};
            exp_frame_start = 1'b1;
        end else if (model_running) begin
            next_phase = model_phase + 1'b1;
            next_pwm = {((next_phase) < model_ahs),
                        ((next_phase) < model_ahp),
                        ((next_phase) < model_ahy)};
        end else begin
            next_running = 1'b0;
            next_phase = {COUNT_W{1'b0}};
            next_pwm = 3'b000;
        end

        if (!abort_edge && !model_pending && cfg_valid) begin
            if (legal_payload) begin
                exp_accepted = 1'b1;
                next_pending = 1'b1;
                next_pp = eff_period;
                next_phy = eff_high_yaw;
                next_php = eff_high_pitch;
                next_phs = eff_high_speed;
                next_ptag = eff_tag;
            end else begin
                exp_rejected = 1'b1;
            end
        end

        check(accepted === exp_accepted, "accepted pulse");
        check(rejected === exp_rejected, "rejected pulse");
        check(applied === exp_applied, "applied pulse");
        check(frame_start === exp_frame_start, "frame_start pulse");
        check(running === next_running, "running state");
        check(pending === next_pending, "pending state");
        check(pwm === next_pwm, "pwm vector");
        check(active_period === next_ap, "active_period");
        check(active_high_yaw === next_ahy, "active_high_yaw");
        check(active_high_pitch === next_ahp, "active_high_pitch");
        check(active_high_speed === next_ahs, "active_high_speed");
        check(active_tag === next_atag, "active_tag");
        check(cfg_ready === (!rst && !stop && !next_pending),
              "cfg_ready post-edge");

        if (accepted) accepted_count = accepted_count + 1;
        if (rejected) rejected_count = rejected_count + 1;
        if (applied) applied_count = applied_count + 1;
        if (frame_start) frame_start_count = frame_start_count + 1;

        if (abort_edge) begin
            if (frame_active) begin
                frame_active = 0;
                aborted_frames = aborted_frames + 1;
            end
        end else if (frame_start) begin
            if (frame_active) begin
                check(frame_ticks == mon_period, "complete frame period count");
                check(frame_yaw == mon_yaw, "complete frame yaw high count");
                check(frame_pitch == mon_pitch, "complete frame pitch high count");
                check(frame_speed == mon_speed, "complete frame speed high count");
                last_frame_ticks = frame_ticks;
                last_frame_yaw = frame_yaw;
                last_frame_pitch = frame_pitch;
                last_frame_speed = frame_speed;
                completed_frames = completed_frames + 1;
            end
            frame_active = 1;
            frame_ticks = 1;
            frame_yaw = pwm[0];
            frame_pitch = pwm[1];
            frame_speed = pwm[2];
            mon_period = active_period;
            mon_yaw = active_high_yaw;
            mon_pitch = active_high_pitch;
            mon_speed = active_high_speed;
            high_yaw_count = high_yaw_count + pwm[0];
            high_pitch_count = high_pitch_count + pwm[1];
            high_speed_count = high_speed_count + pwm[2];
            check(active_period != {COUNT_W{1'b0}}, "nonzero active period at frame start");
        end else if (running) begin
            check(frame_active != 0, "running edge has active frame");
            frame_ticks = frame_ticks + 1;
            frame_yaw = frame_yaw + pwm[0];
            frame_pitch = frame_pitch + pwm[1];
            frame_speed = frame_speed + pwm[2];
            high_yaw_count = high_yaw_count + pwm[0];
            high_pitch_count = high_pitch_count + pwm[1];
            high_speed_count = high_speed_count + pwm[2];
        end else begin
            check(frame_active == 0, "idle edge has no active frame");
        end

        model_running = next_running;
        model_pending = next_pending;
        model_phase = next_phase;
        model_ap = next_ap;
        model_ahy = next_ahy;
        model_ahp = next_ahp;
        model_ahs = next_ahs;
        model_atag = next_atag;
        model_pp = next_pp;
        model_phy = next_phy;
        model_php = next_php;
        model_phs = next_phs;
        model_ptag = next_ptag;
    end
endmodule

module tb_atomic_pwm;
    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic rst = 1'b1;
    logic stop = 1'b0;
    logic cfg_valid = 1'b0;
    logic [31:0] cfg_period = 32'd0;
    logic [31:0] cfg_high_yaw = 32'd0;
    logic [31:0] cfg_high_pitch = 32'd0;
    logic [31:0] cfg_high_speed = 32'd0;
    logic [63:0] cfg_tag = 64'd0;

    atomic_pwm_probe #(.COUNT_W(32), .TAG_W(32), .LABEL("p32t32")) u_default (
        .clk(clk), .rst(rst), .stop(stop), .cfg_valid(cfg_valid),
        .cfg_period(cfg_period), .cfg_high_yaw(cfg_high_yaw),
        .cfg_high_pitch(cfg_high_pitch), .cfg_high_speed(cfg_high_speed),
        .cfg_tag(cfg_tag)
    );
    atomic_pwm_probe #(.COUNT_W(2), .TAG_W(1), .LABEL("p2t1")) u_w2 (
        .clk(clk), .rst(rst), .stop(stop), .cfg_valid(cfg_valid),
        .cfg_period(cfg_period), .cfg_high_yaw(cfg_high_yaw),
        .cfg_high_pitch(cfg_high_pitch), .cfg_high_speed(cfg_high_speed),
        .cfg_tag(cfg_tag)
    );
    atomic_pwm_probe #(.COUNT_W(32), .TAG_W(64), .LABEL("p32t64")) u_tag64 (
        .clk(clk), .rst(rst), .stop(stop), .cfg_valid(cfg_valid),
        .cfg_period(cfg_period), .cfg_high_yaw(cfg_high_yaw),
        .cfg_high_pitch(cfg_high_pitch), .cfg_high_speed(cfg_high_speed),
        .cfg_tag(cfg_tag)
    );

    integer tb_errors = 0;
    integer tb_checks = 0;
    integer total_cases = 0;
    integer pass_cases = 0;
    integer fail_cases = 0;
    integer case_start_error = 0;
    string case_name = "init";
    integer replay_fd = 0;
    integer replay_enabled = 0;
    logic last_pre_ready = 1'b0;
    logic [63:0] rng_seed = 64'h30A7_1C3D_5E6F_1021;

    integer cov_boundary_positions = 0;
    integer cov_invalid_requests = 0;
    integer cov_held_valid_tests = 0;
    integer cov_reset_stop_overlaps = 0;
    integer cov_period_changes = 0;
    integer cov_tag_atomic_checks = 0;
    integer cov_same_edge_bypass = 0;
    integer cov_w2_tuples = 0;
    integer cov_tag64_values = 0;
    integer cov_highbit32_partial = 0;
    integer cov_long_frame_ticks = 0;
    integer cov_random_steps = 0;

    function automatic integer error_sum();
        error_sum = tb_errors + u_default.error_count + u_w2.error_count +
                    u_tag64.error_count;
    endfunction

    function automatic integer check_sum();
        check_sum = tb_checks + u_default.check_count + u_w2.check_count +
                    u_tag64.check_count;
    endfunction

    function automatic [63:0] xorshift64(input [63:0] value);
        logic [63:0] work;
        work = value;
        work = work ^ (work << 13);
        work = work ^ (work >> 7);
        work = work ^ (work << 17);
        xorshift64 = work;
    endfunction

    task automatic check_top(input logic condition, input string what);
        begin
            tb_checks = tb_checks + 1;
            if (condition !== 1'b1) begin
                tb_errors = tb_errors + 1;
                $display("APWM_CHECK_FAIL top=%s time=%0t", what, $time);
            end
        end
    endtask

    task automatic begin_case(input string name);
        begin
            case_name = name;
            case_start_error = error_sum();
        end
    endtask

    task automatic end_case();
        begin
            total_cases = total_cases + 1;
            if (error_sum() == case_start_error) begin
                pass_cases = pass_cases + 1;
            end else begin
                fail_cases = fail_cases + 1;
                $display("APWM_CASE_FAIL name=%s time=%0t", case_name, $time);
            end
        end
    endtask

    task automatic step(
        input logic rst_i,
        input logic stop_i,
        input logic valid_i,
        input logic [31:0] period_i,
        input logic [31:0] high_yaw_i,
        input logic [31:0] high_pitch_i,
        input logic [31:0] high_speed_i,
        input logic [63:0] tag_i
    );
        begin
            @(negedge clk);
            rst = rst_i;
            stop = stop_i;
            cfg_valid = valid_i;
            cfg_period = period_i;
            cfg_high_yaw = high_yaw_i;
            cfg_high_pitch = high_pitch_i;
            cfg_high_speed = high_speed_i;
            cfg_tag = tag_i;
            #1;
            last_pre_ready = u_default.cfg_ready;
            if (replay_enabled) begin
                $fdisplay(replay_fd,
                    "STEP %0d %0d %0d %0d %0d %0d %0d %0d %0d",
                    rst, stop, cfg_valid, cfg_period, cfg_high_yaw,
                    cfg_high_pitch, cfg_high_speed, cfg_tag, last_pre_ready);
            end
            @(posedge clk);
            #2;
        end
    endtask

    task automatic run_edges(input integer count);
        integer index;
        begin
            for (index = 0; index < count; index = index + 1) begin
                step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            end
        end
    endtask

    task automatic check_default_idle(input string what);
        begin
            check_top(u_default.running === 1'b0, what);
            check_top(u_default.pending === 1'b0, what);
            check_top(u_default.pwm === 3'b000, what);
            check_top(u_default.active_period === 32'd0, what);
            check_top(u_default.active_high_yaw === 32'd0, what);
            check_top(u_default.active_high_pitch === 32'd0, what);
            check_top(u_default.active_high_speed === 32'd0, what);
            check_top(u_default.active_tag === 32'd0, what);
        end
    endtask

    task automatic check_default_active(
        input logic [31:0] period_i,
        input logic [31:0] high_yaw_i,
        input logic [31:0] high_pitch_i,
        input logic [31:0] high_speed_i,
        input logic [63:0] tag_i,
        input string what
    );
        begin
            check_top(u_default.active_period === period_i, what);
            check_top(u_default.active_high_yaw === high_yaw_i, what);
            check_top(u_default.active_high_pitch === high_pitch_i, what);
            check_top(u_default.active_high_speed === high_speed_i, what);
            check_top(u_default.active_tag === tag_i[31:0], what);
        end
    endtask

    task automatic reset_dut();
        begin
            step(1'b1, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            step(1'b1, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_default_idle("post-reset idle");
        end
    endtask

    task automatic queue_and_apply(
        input logic [31:0] period_i,
        input logic [31:0] high_yaw_i,
        input logic [31:0] high_pitch_i,
        input logic [31:0] high_speed_i,
        input logic [63:0] tag_i
    );
        begin
            step(1'b0, 1'b0, 1'b1, period_i, high_yaw_i, high_pitch_i,
                 high_speed_i, tag_i);
            check_top(u_default.accepted === 1'b1, "accepted queued tuple");
            check_top(u_default.rejected === 1'b0, "legal tuple not rejected");
            check_top(u_default.pending === 1'b1, "tuple enters pending");
            check_top(u_default.running === 1'b0, "idle queue does not run");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b1, "pending applies next edge");
            check_top(u_default.frame_start === 1'b1, "apply starts frame");
            check_top(u_default.running === 1'b1, "apply starts running");
            check_top(u_default.pending === 1'b0, "apply empties pending");
            check_default_active(period_i, high_yaw_i, high_pitch_i,
                                 high_speed_i, tag_i, "apply active tuple");
        end
    endtask

    task automatic test_reset_stop_priority();
        begin
            begin_case("reset_stop_priority");
            reset_dut();
            step(1'b1, 1'b0, 1'b1, 32'd9, 32'd9, 32'd9, 32'd9, 64'h11);
            check_top(u_default.cfg_ready === 1'b0, "reset gates ready");
            check_top(u_default.accepted === 1'b0, "reset suppresses accept");
            check_top(u_default.rejected === 1'b0, "reset suppresses reject");
            check_top(u_default.applied === 1'b0, "reset suppresses apply");
            check_default_idle("reset held idle");
            cov_reset_stop_overlaps = cov_reset_stop_overlaps + 1;

            step(1'b0, 1'b1, 1'b1, 32'd9, 32'd9, 32'd9, 32'd9, 64'h12);
            check_top(u_default.cfg_ready === 1'b0, "stop gates ready");
            check_top(u_default.accepted === 1'b0, "stop suppresses accept");
            check_top(u_default.rejected === 1'b0, "stop suppresses reject");
            check_top(u_default.applied === 1'b0, "stop suppresses apply");
            check_default_idle("stop held idle");
            cov_reset_stop_overlaps = cov_reset_stop_overlaps + 1;

            step(1'b1, 1'b1, 1'b1, 32'd5, 32'd1, 32'd1, 32'd1, 64'h13);
            check_default_idle("reset and stop priority");
            check_top(u_default.cfg_ready === 1'b0, "both gate ready");
            cov_reset_stop_overlaps = cov_reset_stop_overlaps + 1;

            step(1'b0, 1'b0, 1'b1, 32'd4, 32'd1, 32'd2, 32'd3, 64'h14);
            check_top(u_default.accepted === 1'b1, "fresh tuple accepted after abort");
            check_top(u_default.running === 1'b0, "accepted tuple still idle");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b1, "fresh tuple applies");

            step(1'b0, 1'b0, 1'b1, 32'd4, 32'd4, 32'd4, 32'd4, 64'h15);
            check_top(u_default.accepted === 1'b1, "second tuple queues");
            check_top(u_default.pending === 1'b1, "second tuple pending");
            step(1'b0, 1'b1, 1'b1, 32'd5, 32'd5, 32'd5, 32'd5, 64'h16);
            check_top(u_default.applied === 1'b0, "stop overrides pending apply");
            check_top(u_default.accepted === 1'b0, "stop overrides incoming accept");
            check_top(u_default.frame_start === 1'b0, "stop suppresses boundary");
            check_default_idle("stop flushes pending and active");
            cov_reset_stop_overlaps = cov_reset_stop_overlaps + 1;

            step(1'b0, 1'b1, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_default_idle("held stop remains quiescent");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_default_idle("stop deassert does not resume output");

            queue_and_apply(32'd6, 32'd6, 32'd6, 32'd6, 64'h17);
            check_top(u_default.pwm === 3'b111, "full-high starts high");
            step(1'b1, 1'b0, 1'b1, 32'd2, 32'd1, 32'd1, 32'd1, 64'h18);
            check_top(u_default.pwm === 3'b000, "reset truncates high pulse");
            check_default_idle("reset flushes active tuple");
            cov_reset_stop_overlaps = cov_reset_stop_overlaps + 1;
            step(1'b1, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_default_idle("final priority idle");
            end_case();
        end
    endtask

    task automatic test_invalid_and_held();
        begin
            begin_case("invalid_and_held");
            reset_dut();
            step(1'b0, 1'b0, 1'b1, 32'd0, 32'd0, 32'd0, 32'd0, 64'h21);
            check_top(u_default.rejected === 1'b1, "zero period rejected");
            check_top(u_default.accepted === 1'b0, "zero period not accepted");
            check_default_idle("zero period leaves idle");
            cov_invalid_requests = cov_invalid_requests + 1;

            step(1'b0, 1'b0, 1'b1, 32'd5, 32'd6, 32'd0, 32'd0, 64'h22);
            check_top(u_default.rejected === 1'b1, "yaw high above period rejected");
            check_default_idle("bad yaw leaves idle");
            cov_invalid_requests = cov_invalid_requests + 1;

            step(1'b0, 1'b0, 1'b1, 32'd5, 32'd0, 32'd6, 32'd0, 64'h23);
            check_top(u_default.rejected === 1'b1, "pitch high above period rejected");
            check_default_idle("bad pitch leaves idle");
            cov_invalid_requests = cov_invalid_requests + 1;

            step(1'b0, 1'b0, 1'b1, 32'd5, 32'd0, 32'd0, 32'd6, 64'h24);
            check_top(u_default.rejected === 1'b1, "speed high above period rejected");
            check_default_idle("bad speed leaves idle");
            cov_invalid_requests = cov_invalid_requests + 1;

            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            queue_and_apply(32'd6, 32'd1, 32'd3, 32'd5, 64'h25);
            run_edges(2);
            step(1'b0, 1'b0, 1'b1, 32'd6, 32'd7, 32'd3, 32'd5, 64'h26);
            check_top(u_default.rejected === 1'b1, "running bad yaw rejected");
            check_top(u_default.running === 1'b1, "running bad yaw keeps running");
            check_top(u_default.pending === 1'b0, "running bad yaw no pending");
            check_default_active(32'd6, 32'd1, 32'd3, 32'd5, 64'h25,
                                 "bad yaw no active mutation");
            cov_invalid_requests = cov_invalid_requests + 1;

            step(1'b0, 1'b0, 1'b1, 32'd6, 32'd1, 32'd7, 32'd5, 64'h27);
            check_top(u_default.rejected === 1'b1, "running bad pitch rejected");
            check_default_active(32'd6, 32'd1, 32'd3, 32'd5, 64'h25,
                                 "bad pitch no active mutation");
            cov_invalid_requests = cov_invalid_requests + 1;

            step(1'b0, 1'b0, 1'b1, 32'd6, 32'd1, 32'd3, 32'd7, 64'h28);
            check_top(u_default.rejected === 1'b1, "running bad speed rejected");
            check_default_active(32'd6, 32'd1, 32'd3, 32'd5, 64'h25,
                                 "bad speed no active mutation");
            cov_invalid_requests = cov_invalid_requests + 1;

            reset_dut();
            step(1'b0, 1'b0, 1'b1, 32'd5, 32'd5, 32'd5, 32'd5, 64'h29);
            check_top(u_default.accepted === 1'b1, "held test tuple queued");
            step(1'b0, 1'b0, 1'b1, 32'd4, 32'd1, 32'd2, 32'd3, 64'h2A);
            check_top(u_default.applied === 1'b1, "held valid does not bypass apply");
            check_top(u_default.accepted === 1'b0, "apply edge cannot accept");
            check_top(u_default.rejected === 1'b0, "apply edge does not reject held valid");
            check_default_active(32'd5, 32'd5, 32'd5, 32'd5, 64'h29,
                                 "held valid apply keeps old active tuple");
            step(1'b0, 1'b0, 1'b1, 32'd4, 32'd1, 32'd2, 32'd3, 64'h2A);
            check_top(u_default.accepted === 1'b1, "held valid accepted one edge later");
            check_top(u_default.pending === 1'b1, "held valid enters pending");
            check_default_active(32'd5, 32'd5, 32'd5, 32'd5, 64'h29,
                                 "accepted held valid does not mutate active");
            step(1'b0, 1'b0, 1'b1, 32'd4, 32'd1, 32'd2, 32'd3, 64'h2A);
            check_top(u_default.accepted === 1'b0, "pending blocks repeated accept");
            check_top(u_default.rejected === 1'b0, "pending suppresses reject");
            check_top(u_default.cfg_ready === 1'b0, "pending busy deasserts ready");
            run_edges(2);
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b1, "held tuple applies at boundary");
            check_default_active(32'd4, 32'd1, 32'd2, 32'd3, 64'h2A,
                                 "held tuple fully atomic at apply");
            cov_held_valid_tests = cov_held_valid_tests + 1;

            reset_dut();
            step(1'b0, 1'b0, 1'b1, 32'd3, 32'd3, 32'd3, 32'd3, 64'h2B);
            step(1'b0, 1'b0, 1'b1, 32'd3, 32'd4, 32'd0, 32'd0, 64'h2C);
            check_top(u_default.applied === 1'b1, "invalid held apply edge");
            check_top(u_default.rejected === 1'b0, "invalid held when busy no reject");
            step(1'b0, 1'b0, 1'b1, 32'd3, 32'd4, 32'd0, 32'd0, 64'h2C);
            check_top(u_default.rejected === 1'b1, "invalid held rejects when ready");
            check_default_active(32'd3, 32'd3, 32'd3, 32'd3, 64'h2B,
                                 "invalid held no active mutation");
            cov_held_valid_tests = cov_held_valid_tests + 1;

            reset_dut();
            step(1'b1, 1'b0, 1'b1, 32'd4, 32'd1, 32'd2, 32'd3, 64'h2D);
            check_top(u_default.accepted === 1'b0, "reset held ignores valid");
            step(1'b0, 1'b0, 1'b1, 32'd4, 32'd1, 32'd2, 32'd3, 64'h2D);
            check_top(u_default.accepted === 1'b1, "held valid accepted after reset");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b1, "post-reset held tuple applies");
            step(1'b0, 1'b1, 1'b1, 32'd4, 32'd4, 32'd3, 32'd2, 64'h2E);
            check_top(u_default.accepted === 1'b0, "stop held ignores valid");
            check_default_idle("stop held flushes active");
            step(1'b0, 1'b0, 1'b1, 32'd4, 32'd4, 32'd3, 32'd2, 64'h2E);
            check_top(u_default.accepted === 1'b1, "held valid accepted after stop");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b1, "post-stop held tuple applies");
            cov_reset_stop_overlaps = cov_reset_stop_overlaps + 2;
            cov_held_valid_tests = cov_held_valid_tests + 1;
            end_case();
        end
    endtask

    task automatic exercise_frame(
        input integer period_i,
        input integer high_yaw_i,
        input integer high_pitch_i,
        input integer high_speed_i,
        input logic [63:0] tag_i
    );
        integer before_frames;
        begin
            reset_dut();
            before_frames = u_default.completed_frames;
            queue_and_apply(period_i[31:0], high_yaw_i[31:0],
                            high_pitch_i[31:0], high_speed_i[31:0], tag_i);
            check_top(u_default.pwm === {(high_speed_i != 0),
                                         (high_pitch_i != 0),
                                         (high_yaw_i != 0)},
                      "apply pwm matches high masks");
            if (period_i > 1) begin
                run_edges(period_i - 1);
                check_default_active(period_i[31:0], high_yaw_i[31:0],
                                     high_pitch_i[31:0], high_speed_i[31:0],
                                     tag_i, "active stable before boundary");
            end
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.frame_start === 1'b1, "expected frame boundary");
            check_top(u_default.completed_frames == before_frames + 1,
                      "one complete frame observed");
            check_top(u_default.last_frame_ticks == period_i,
                      "exact measured frame length");
            check_top(u_default.last_frame_yaw == high_yaw_i,
                      "exact yaw high intervals");
            check_top(u_default.last_frame_pitch == high_pitch_i,
                      "exact pitch high intervals");
            check_top(u_default.last_frame_speed == high_speed_i,
                      "exact speed high intervals");
            check_default_active(period_i[31:0], high_yaw_i[31:0],
                                 high_pitch_i[31:0], high_speed_i[31:0],
                                 tag_i, "repeat keeps active tuple");
            step(1'b0, 1'b1, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_default_idle("frame test stop flush");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
        end
    endtask

    task automatic test_exact_frames();
        begin
            begin_case("exact_frames");
            exercise_frame(1, 0, 1, 1, 64'h31);
            exercise_frame(3, 0, 3, 1, 64'h32);
            exercise_frame(7, 7, 7, 7, 64'h33);
            exercise_frame(5, 0, 0, 0, 64'h34);
            exercise_frame(8, 1, 4, 8, 64'h35);
            exercise_frame(11, 5, 11, 2, 64'h36);
            exercise_frame(2, 2, 1, 0, 64'h37);
            end_case();
        end
    endtask

    task automatic test_boundary_positions();
        integer target;
        integer index;
        integer observed_delay;
        integer expected_delay;
        logic applied_seen;
        begin
            begin_case("boundary_positions");
            for (target = 1; target <= 8; target = target + 1) begin
                reset_dut();
                step(1'b0, 1'b0, 1'b1, 32'd8, 32'd2, 32'd5, 32'd7,
                     64'h400 + target);
                step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
                check_top(u_default.applied === 1'b1, "boundary base apply");
                check_default_active(32'd8, 32'd2, 32'd5, 32'd7,
                                     64'h400 + target, "boundary base active");
                for (index = 1; index < target; index = index + 1) begin
                    step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
                end
                step(1'b0, 1'b0, 1'b1, 32'd8, 32'd1, 32'd4, 32'd8,
                     64'h500 + target);
                check_top(u_default.accepted === 1'b1, "boundary update accepted");
                check_top(u_default.applied === 1'b0, "boundary update does not bypass");
                check_default_active(32'd8, 32'd2, 32'd5, 32'd7,
                                     64'h400 + target,
                                     "old active tuple held at queue edge");
                check_top(u_default.frame_start === (target == 8),
                          "only exact boundary queue repeats frame");
                observed_delay = 0;
                applied_seen = 1'b0;
                for (index = 0; index < 12 && !applied_seen; index = index + 1) begin
                    step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
                    observed_delay = observed_delay + 1;
                    if (u_default.applied) applied_seen = 1'b1;
                end
                expected_delay = (target == 8) ? 8 : (8 - target);
                check_top(applied_seen === 1'b1, "boundary update eventually applies");
                check_top(observed_delay == expected_delay,
                          "boundary update applies at next full boundary");
                check_default_active(32'd8, 32'd1, 32'd4, 32'd8,
                                     64'h500 + target,
                                     "boundary update atomic at apply");
                cov_boundary_positions = cov_boundary_positions + 1;
            end

            reset_dut();
            step(1'b0, 1'b0, 1'b1, 32'd8, 32'd8, 32'd0, 32'd4, 64'h5F0);
            step(1'b0, 1'b0, 1'b1, 32'd6, 32'd1, 32'd2, 32'd3, 64'h5F1);
            check_top(last_pre_ready === 1'b0, "apply edge ready pre-state low");
            check_top(u_default.applied === 1'b1, "apply edge still applies");
            check_top(u_default.accepted === 1'b0, "apply edge cannot bypass pending stage");
            check_top(u_default.rejected === 1'b0, "apply edge ignores held legal request");
            check_default_active(32'd8, 32'd8, 32'd0, 32'd4, 64'h5F0,
                                 "same-edge request cannot mutate active");
            step(1'b0, 1'b0, 1'b1, 32'd6, 32'd1, 32'd2, 32'd3, 64'h5F1);
            check_top(u_default.accepted === 1'b1, "held request accepted after apply");
            check_top(u_default.pending === 1'b1, "held request waits in pending");
            check_default_active(32'd8, 32'd8, 32'd0, 32'd4, 64'h5F0,
                                 "queued request not active yet");
            cov_same_edge_bypass = cov_same_edge_bypass + 1;
            step(1'b0, 1'b1, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_default_idle("boundary test final idle");
            end_case();
        end
    endtask

    task automatic test_period_changes_and_tag();
        begin
            begin_case("period_changes_tag");
            reset_dut();
            queue_and_apply(32'd5, 32'd1, 32'd2, 32'd3, 64'h610);
            run_edges(2);
            step(1'b0, 1'b0, 1'b1, 32'd9, 32'd9, 32'd0, 32'd4, 64'h611);
            check_top(u_default.accepted === 1'b1, "upward period update queues");
            check_top(u_default.applied === 1'b0, "upward period waits for boundary");
            check_default_active(32'd5, 32'd1, 32'd2, 32'd3, 64'h610,
                                 "upward update keeps old active tuple");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b0, "upward update still waits");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b1, "upward update applies at boundary");
            check_default_active(32'd9, 32'd9, 32'd0, 32'd4, 64'h611,
                                 "upward update all-field atomic");
            cov_period_changes = cov_period_changes + 1;
            cov_tag_atomic_checks = cov_tag_atomic_checks + 1;

            run_edges(4);
            step(1'b0, 1'b0, 1'b1, 32'd3, 32'd0, 32'd3, 32'd1, 64'h612);
            check_top(u_default.accepted === 1'b1, "downward period update queues");
            check_default_active(32'd9, 32'd9, 32'd0, 32'd4, 64'h611,
                                 "downward update keeps old active tuple");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b0, "downward update waits edge one");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b0, "downward update waits edge two");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b0, "downward update waits edge three");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b1, "downward update applies at boundary");
            check_default_active(32'd3, 32'd0, 32'd3, 32'd1, 64'h612,
                                 "downward update all-field atomic");
            cov_period_changes = cov_period_changes + 1;
            cov_tag_atomic_checks = cov_tag_atomic_checks + 1;

            step(1'b0, 1'b0, 1'b1, 32'd3, 32'd0, 32'd3, 32'd1, 64'h613);
            check_top(u_default.accepted === 1'b1, "tag-only update queues");
            check_default_active(32'd3, 32'd0, 32'd3, 32'd1, 64'h612,
                                 "tag-only update preserves old tag while pending");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b0, "tag-only waits first edge");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b1, "tag-only applies at boundary");
            check_default_active(32'd3, 32'd0, 32'd3, 32'd1, 64'h613,
                                 "tag-only update atomic");
            cov_tag_atomic_checks = cov_tag_atomic_checks + 1;
            step(1'b0, 1'b1, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_default_idle("period tag final idle");
            end_case();
        end
    endtask

    task automatic test_width_tag_boundaries();
        logic [63:0] tags [0:3];
        integer index;
        begin
            begin_case("width_tag_boundaries");
            tags[0] = 64'd0;
            tags[1] = 64'd1;
            tags[2] = 64'h8000_0000_0000_0000;
            tags[3] = 64'hFFFF_FFFF_FFFF_FFFF;
            for (index = 0; index < 4; index = index + 1) begin
                reset_dut();
                queue_and_apply(32'd2, 32'd1, 32'd0, 32'd2, tags[index]);
                check_top(u_tag64.active_tag === tags[index],
                          "TAG_W 64 preserves full tag");
                check_top(u_default.active_tag === tags[index][31:0],
                          "TAG_W 32 truncates tag boundary");
                check_top(u_w2.active_tag === tags[index][0],
                          "TAG_W 1 preserves low tag bit");
                run_edges(2);
                step(1'b0, 1'b1, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
                step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
                cov_tag64_values = cov_tag64_values + 1;
            end

            reset_dut();
            step(1'b0, 1'b0, 1'b1, 32'hFFFF_FFFF, 32'h8000_0000,
                 32'hFFFF_FFFF, 32'd0, 64'h620);
            check_top(u_default.accepted === 1'b1,
                      "unsigned high-bit tuple accepted");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b1, "high-bit tuple applies");
            check_top(u_default.pwm === 3'b011, "unsigned high-bit pwm observations");
            run_edges(256);
            check_top(u_default.pwm === 3'b011, "high-bit pwm remains high in bounded run");
            check_default_active(32'hFFFF_FFFF, 32'h8000_0000,
                                 32'hFFFF_FFFF, 32'd0, 64'h620,
                                 "high-bit active tuple stable");
            step(1'b0, 1'b1, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            cov_highbit32_partial = cov_highbit32_partial + 1;

            reset_dut();
            step(1'b0, 1'b0, 1'b1, 32'h8000_0001, 32'h8000_0000,
                 32'h8000_0001, 32'd0, 64'h621);
            check_top(u_default.accepted === 1'b1,
                      "unsigned high-bit period comparison accepted");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.pwm === 3'b011, "high-bit period partial pwm");
            run_edges(64);
            check_top(u_default.pwm === 3'b011, "high-bit period bounded observation");
            step(1'b0, 1'b1, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            cov_highbit32_partial = cov_highbit32_partial + 1;

            reset_dut();
            step(1'b0, 1'b0, 1'b1, 32'h7FFF_FFFF, 32'h8000_0000,
                 32'd0, 32'd0, 64'h622);
            check_top(u_default.rejected === 1'b1,
                      "unsigned comparison rejects high bit above period");
            check_default_idle("unsigned invalid leaves idle");
            cov_invalid_requests = cov_invalid_requests + 1;
            end_case();
        end
    endtask

    task automatic test_width2_exhaustive();
        integer period_i;
        integer yaw_i;
        integer pitch_i;
        integer speed_i;
        integer before_frames;
        begin
            begin_case("width2_exhaustive");
            for (period_i = 1; period_i <= 3; period_i = period_i + 1) begin
                for (yaw_i = 0; yaw_i <= period_i; yaw_i = yaw_i + 1) begin
                    for (pitch_i = 0; pitch_i <= period_i; pitch_i = pitch_i + 1) begin
                        for (speed_i = 0; speed_i <= period_i; speed_i = speed_i + 1) begin
                            reset_dut();
                            before_frames = u_w2.completed_frames;
                            step(1'b0, 1'b0, 1'b1, period_i[31:0],
                                 yaw_i[31:0], pitch_i[31:0], speed_i[31:0],
                                 64'hA500_0000_0000_0000 + cov_w2_tuples);
                            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0,
                                 32'd0, 64'd0);
                            check_top(u_w2.active_period === period_i[1:0],
                                      "COUNT_W 2 active period boundary");
                            check_top(u_w2.active_high_yaw === yaw_i[1:0],
                                      "COUNT_W 2 yaw boundary");
                            check_top(u_w2.active_high_pitch === pitch_i[1:0],
                                      "COUNT_W 2 pitch boundary");
                            check_top(u_w2.active_high_speed === speed_i[1:0],
                                      "COUNT_W 2 speed boundary");
                            check_top(u_w2.active_tag === cov_w2_tuples[0],
                                      "TAG_W 1 exhaustive tuple boundary");
                            run_edges(2 * period_i);
                            check_top(u_w2.completed_frames == before_frames + 2,
                                      "COUNT_W 2 two complete frames no rollover");
                            cov_w2_tuples = cov_w2_tuples + 1;
                        end
                    end
                end
            end
            reset_dut();
            check_top(u_w2.running === 1'b0, "COUNT_W 2 final idle");
            end_case();
        end
    endtask

    task automatic test_long_candidate_frame();
        integer index;
        integer before_frames;
        begin
            begin_case("candidate_2m_frame");
            reset_dut();
            step(1'b0, 1'b0, 1'b1, 32'd2000000, 32'd1, 32'd1000000,
                 32'd1999999, 64'h700);
            check_top(u_default.accepted === 1'b1, "2m tuple accepted");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.applied === 1'b1, "2m tuple applies");
            check_default_active(32'd2000000, 32'd1, 32'd1000000,
                                 32'd1999999, 64'h700, "2m active tuple");
            before_frames = u_default.completed_frames;
            for (index = 0; index < 2000000; index = index + 1) begin
                @(negedge clk);
                rst = 1'b0;
                stop = 1'b0;
                cfg_valid = 1'b0;
                cfg_period = 32'd0;
                cfg_high_yaw = 32'd0;
                cfg_high_pitch = 32'd0;
                cfg_high_speed = 32'd0;
                cfg_tag = 64'd0;
                @(posedge clk);
                #2;
            end
            check_top(u_default.frame_start === 1'b1, "2m frame boundary");
            check_top(u_default.completed_frames == before_frames + 1,
                      "2m complete frame counted");
            check_top(u_default.last_frame_ticks == 2000000,
                      "2m exact frame ticks");
            check_top(u_default.last_frame_yaw == 1,
                      "2m exact yaw high ticks");
            check_top(u_default.last_frame_pitch == 1000000,
                      "2m exact pitch high ticks");
            check_top(u_default.last_frame_speed == 1999999,
                      "2m exact speed high ticks");
            check_top(u_default.pwm === 3'b111, "2m next frame starts high");
            cov_long_frame_ticks = 2000000;
            step(1'b0, 1'b1, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            check_top(u_default.pwm === 3'b000, "2m stop flushes pwm");
            check_default_idle("2m stop flush idle");
            step(1'b0, 1'b0, 1'b0, 32'd0, 32'd0, 32'd0, 32'd0, 64'd0);
            end_case();
        end
    endtask

    task automatic test_random_schedule();
        logic [63:0] r;
        logic [63:0] r2;
        logic [63:0] base;
        logic [63:0] tag_value;
        logic [31:0] period_value;
        logic [31:0] yaw_value;
        logic [31:0] pitch_value;
        logic [31:0] speed_value;
        logic valid_value;
        logic rst_value;
        logic stop_value;
        logic stalled;
        integer index;
        integer before_busy;
        integer before_accept;
        integer before_reject;
        begin
            begin_case("deterministic_random");
            replay_enabled = 1;
            $fdisplay(replay_fd, "# ATOMIC_PWM_SEED %0d", rng_seed);
            reset_dut();
            $fdisplay(replay_fd, "# ATOMIC_PWM_RANDOM_BEGIN");
            r = rng_seed;
            stalled = 1'b0;
            rst_value = 1'b0;
            stop_value = 1'b0;
            valid_value = 1'b0;
            period_value = 32'd0;
            yaw_value = 32'd0;
            pitch_value = 32'd0;
            speed_value = 32'd0;
            tag_value = 64'd0;
            before_busy = u_default.busy_valid_count;
            before_accept = u_default.accepted_count;
            before_reject = u_default.rejected_count;
            for (index = 0; index < 12000; index = index + 1) begin
                if (!stalled) begin
                    r = xorshift64(r);
                    rst_value = (r[7:0] < 3);
                    stop_value = !rst_value && (r[15:8] < 5);
                    valid_value = (r[23:16] < 200);
                    period_value = 32'd1 + (r[30:24] % 32'd16);
                    if (r[34:31] == 0) begin
                        period_value = 32'd1 + (r[47:32] % 32'd1000);
                    end
                    r2 = xorshift64(r);
                    r = xorshift64(r2);
                    base = {32'b0, period_value} + 64'd1;
                    yaw_value = r2[31:0] % base[31:0];
                    pitch_value = r2[47:16] % base[31:0];
                    speed_value = r2[63:32] % base[31:0];
                    if (period_value == 32'd0) begin
                        period_value = 32'd0;
                    end else if ((r2[55:52] == 0) || (r2[59:56] == 0)) begin
                        yaw_value = period_value + 32'd1;
                    end else if (r2[63:60] == 0) begin
                        period_value = 32'd0;
                    end
                    tag_value = xorshift64(r);
                end else begin
                    rst_value = 1'b0;
                    stop_value = 1'b0;
                    valid_value = 1'b1;
                end
                step(rst_value, stop_value, valid_value, period_value,
                     yaw_value, pitch_value, speed_value, tag_value);
                if (valid_value && !last_pre_ready) begin
                    stalled = 1'b1;
                end else begin
                    stalled = 1'b0;
                end
                cov_random_steps = cov_random_steps + 1;
            end
            $fdisplay(replay_fd, "# ATOMIC_PWM_RANDOM_END");
            reset_dut();
            replay_enabled = 0;
            check_top(u_default.busy_valid_count > before_busy + 100,
                      "random observed busy held-valid");
            check_top(u_default.accepted_count > before_accept + 100,
                      "random accepted legal requests");
            check_top(u_default.rejected_count > before_reject + 20,
                      "random rejected invalid requests");
            check_default_idle("random final idle");
            end_case();
        end
    endtask

    task automatic coverage_marker(input logic condition, input string name);
        begin
            if (condition) begin
                $display("APWM_COVER %s", name);
            end else begin
                check_top(1'b0, name);
            end
        end
    endtask

    initial begin : main
        logic [63:0] seed_arg;
        begin
            seed_arg = rng_seed;
            if ($value$plusargs("ATOMIC_PWM_SEED=%d", seed_arg)) begin
                rng_seed = seed_arg;
            end
            replay_fd = $fopen("replay_events.log", "w");
            if (replay_fd == 0) begin
                $fatal(1, "APWM_FAIL cannot open replay_events.log");
            end
            $display("APWM_SEED %0d", rng_seed);

            test_reset_stop_priority();
            test_invalid_and_held();
            test_exact_frames();
            test_boundary_positions();
            test_period_changes_and_tag();
            test_width_tag_boundaries();
            test_width2_exhaustive();
            test_long_candidate_frame();
            test_random_schedule();

            reset_dut();
            check_top(u_default.running === 1'b0, "final default idle");
            check_top(u_w2.running === 1'b0, "final width2 idle");
            check_top(u_tag64.running === 1'b0, "final tag64 idle");
            check_top(u_default.error_count == 0, "default probe clean");
            check_top(u_w2.error_count == 0, "width2 probe clean");
            check_top(u_tag64.error_count == 0, "tag64 probe clean");
            check_top(total_cases == 9, "all nine directed/random case groups ran");
            check_top(pass_cases == total_cases, "all case groups passed");
            check_top(fail_cases == 0, "no failed case groups");

            coverage_marker(cov_boundary_positions == 8,
                            "boundary_positions_8");
            coverage_marker(cov_same_edge_bypass == 1,
                            "same_edge_bypass_checked");
            coverage_marker(cov_invalid_requests >= 8,
                            "invalid_inputs_each_field");
            coverage_marker(cov_held_valid_tests >= 3,
                            "held_valid_busy_checked");
            coverage_marker(cov_reset_stop_overlaps >= 7,
                            "reset_stop_overlap_checked");
            coverage_marker(cov_period_changes == 2,
                            "period_up_and_down");
            coverage_marker(cov_tag_atomic_checks == 3,
                            "tag_atomicity_checked");
            coverage_marker(cov_w2_tuples == 99,
                            "width2_legal_tuples_exhaustive");
            coverage_marker(u_w2.completed_frames >= 198,
                            "width2_frame_counts");
            coverage_marker(cov_tag64_values == 4,
                            "tag64_boundary_values");
            coverage_marker(cov_highbit32_partial == 2,
                            "unsigned_highbit32_partial");
            coverage_marker(cov_long_frame_ticks == 2000000,
                            "candidate_2m_complete_frame");
            coverage_marker(cov_random_steps == 12000,
                            "deterministic_random_12000");
            coverage_marker(u_default.completed_frames >= 200,
                            "default_complete_frames");
            coverage_marker(u_default.busy_valid_count > 100,
                            "busy_held_valid_observed");
            coverage_marker(u_default.accepted_count > 300,
                            "accepted_atomicity_traffic");
            coverage_marker(u_default.rejected_count > 50,
                            "rejected_invalid_traffic");
            coverage_marker(u_default.applied_count > 100,
                            "atomic_apply_traffic");
            coverage_marker(u_default.aborted_frames > 50,
                            "reset_stop_flush_traffic");
            coverage_marker(check_sum() > 1000000,
                            "public_port_checks_above_one_million");

            $display("APWM_COVER_COUNTS boundary=%0d invalid=%0d held=%0d overlaps=%0d period=%0d tag=%0d bypass=%0d w2=%0d tag64=%0d highbit=%0d long=%0d random=%0d busy=%0d",
                     cov_boundary_positions, cov_invalid_requests,
                     cov_held_valid_tests, cov_reset_stop_overlaps,
                     cov_period_changes, cov_tag_atomic_checks,
                     cov_same_edge_bypass, cov_w2_tuples, cov_tag64_values,
                     cov_highbit32_partial, cov_long_frame_ticks,
                     cov_random_steps, u_default.busy_valid_count);
            $display("APWM_SUMMARY cases=%0d pass=%0d fail=%0d checks=%0d default_frames=%0d w2_frames=%0d tag64_frames=%0d accepted=%0d rejected=%0d applied=%0d aborted=%0d",
                     total_cases, pass_cases, fail_cases, check_sum(),
                     u_default.completed_frames, u_w2.completed_frames,
                     u_tag64.completed_frames, u_default.accepted_count,
                     u_default.rejected_count, u_default.applied_count,
                     u_default.aborted_frames);
            if (replay_fd != 0) begin
                $fclose(replay_fd);
                replay_fd = 0;
            end
            if (error_sum() != 0) begin
                $display("APWM_END fail");
                $fatal(1, "APWM_FAILURES %0d", error_sum());
            end
            $display("APWM_END pass");
            $display("APWM_DONE");
            $finish(0);
        end
    end

    initial begin : watchdog
        #100000000;
        $display("APWM_WATCHDOG_TIMEOUT");
        $fatal(1);
    end
endmodule
