// tb_pwm_applied_capture - authored public-port self-checking stimulus.
//
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Work: B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1
// Operation: B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Contract pin: f5989cd5defce561f9ba98e6b18fc2682945f0a2.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// The default sample source is an independently driven observed-level
// schedule. LOOPBACK=1 names the supplemental internal digital-loopback case.
// The checker reads public ports and absolute sampled indices only. It does not
// use hierarchy, forces, internal counters, or expected tuples as measurements.

`timescale 1ns/1ps

module tb_pwm_applied_capture #(
    parameter integer COUNT_W   = 32,
    parameter integer WITNESS_W = 64,
    parameter integer TAG_W     = 32,
    parameter integer TEST_GROUP = 0,
    parameter integer LOOPBACK   = 0
);

    localparam logic [COUNT_W-1:0]   COUNT_ZERO = '0;
    localparam logic [TAG_W-1:0]     TAG_ZERO   = '0;
    localparam logic [TAG_W-1:0]     TAG_ONES   = '1;

    logic                 clk;
    logic                 rst;
    logic                 stop;
    logic                 cfg_valid;
    logic                 cfg_ready;
    logic [COUNT_W-1:0]   cfg_period;
    logic [COUNT_W-1:0]   cfg_high_yaw;
    logic [COUNT_W-1:0]   cfg_high_pitch;
    logic [COUNT_W-1:0]   cfg_high_speed;
    logic [TAG_W-1:0]     cfg_tag;
    logic [2:0]           stimulus_levels;
    logic [2:0]           sample_levels;
    logic                 out_ready;

    logic                 accepted;
    logic                 rejected;
    logic                 applied;
    logic                 frame_start;
    logic                 running;
    logic                 pending;
    logic [2:0]           pwm;
    logic [COUNT_W-1:0]   active_period;
    logic [COUNT_W-1:0]   active_high_yaw;
    logic [COUNT_W-1:0]   active_high_pitch;
    logic [COUNT_W-1:0]   active_high_speed;
    logic [TAG_W-1:0]     active_tag;
    logic                 window_active;
    logic                 window_started;
    logic                 capture_armed;
    logic                 out_valid;
    logic [COUNT_W-1:0]   out_period;
    logic [COUNT_W-1:0]   out_high0;
    logic [COUNT_W-1:0]   out_high1;
    logic [COUNT_W-1:0]   out_high2;
    logic [WITNESS_W-1:0] out_start;
    logic [WITNESS_W-1:0] out_end;
    logic [TAG_W-1:0]     out_tag;
    logic [COUNT_W-1:0]   expected_period;
    logic [COUNT_W-1:0]   expected_high0;
    logic [COUNT_W-1:0]   expected_high1;
    logic [COUNT_W-1:0]   expected_high2;
    logic [TAG_W-1:0]     expected_tag;
    logic [3:0]           raw_fault_events;
    logic                 failure_event;
    logic [2:0]           failure_code;

    logic pre_cfg_ready;
    logic pre_applied;
    logic pre_out_valid;
    logic pre_out_ready;

    integer groups;
    integer cases;
    integer samples;
    integer assertions;
    integer mismatches;
    integer records;
    integer raw_faults;
    integer failure_events;
    integer window_starts;
    integer handshakes;
    integer group_cases_start;
    integer group_samples_start;
    integer group_assertions_start;
    integer group_mismatches_start;
    integer group_records_start;
    integer group_raw_faults_start;
    integer group_failure_events_start;
    integer group_window_starts_start;
    integer group_handshakes_start;

    assign sample_levels = LOOPBACK ? pwm : stimulus_levels;

    deepeye_pwm_applied_capture #(
        .COUNT_W(COUNT_W),
        .WITNESS_W(WITNESS_W),
        .TAG_W(TAG_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .stop(stop),
        .cfg_valid(cfg_valid),
        .cfg_ready(cfg_ready),
        .cfg_period(cfg_period),
        .cfg_high_yaw(cfg_high_yaw),
        .cfg_high_pitch(cfg_high_pitch),
        .cfg_high_speed(cfg_high_speed),
        .cfg_tag(cfg_tag),
        .sample_levels(sample_levels),
        .out_ready(out_ready),
        .accepted(accepted),
        .rejected(rejected),
        .applied(applied),
        .frame_start(frame_start),
        .running(running),
        .pending(pending),
        .pwm(pwm),
        .active_period(active_period),
        .active_high_yaw(active_high_yaw),
        .active_high_pitch(active_high_pitch),
        .active_high_speed(active_high_speed),
        .active_tag(active_tag),
        .window_active(window_active),
        .window_started(window_started),
        .capture_armed(capture_armed),
        .out_valid(out_valid),
        .out_period(out_period),
        .out_high0(out_high0),
        .out_high1(out_high1),
        .out_high2(out_high2),
        .out_start(out_start),
        .out_end(out_end),
        .out_tag(out_tag),
        .expected_period(expected_period),
        .expected_high0(expected_high0),
        .expected_high1(expected_high1),
        .expected_high2(expected_high2),
        .expected_tag(expected_tag),
        .raw_fault_events(raw_fault_events),
        .failure_event(failure_event),
        .failure_code(failure_code)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        rst = 1'b1;
        stop = 1'b0;
        cfg_valid = 1'b0;
        cfg_period = COUNT_ZERO;
        cfg_high_yaw = COUNT_ZERO;
        cfg_high_pitch = COUNT_ZERO;
        cfg_high_speed = COUNT_ZERO;
        cfg_tag = TAG_ZERO;
        stimulus_levels = 3'b000;
        out_ready = 1'b0;
        pre_cfg_ready = 1'b0;
        pre_applied = 1'b0;
        pre_out_valid = 1'b0;
        pre_out_ready = 1'b0;
        groups = 0;
        cases = 0;
        samples = 0;
        assertions = 0;
        mismatches = 0;
        records = 0;
        raw_faults = 0;
        failure_events = 0;
        window_starts = 0;
        handshakes = 0;
        group_cases_start = 0;
        group_samples_start = 0;
        group_assertions_start = 0;
        group_mismatches_start = 0;
        group_records_start = 0;
        group_raw_faults_start = 0;
        group_failure_events_start = 0;
        group_window_starts_start = 0;
        group_handshakes_start = 0;
    end

    string current_group;

    task automatic mismatch(input string label,
                            input logic [63:0] expected,
                            input logic [63:0] actual);
        begin
            mismatches = mismatches + 1;
            $display("MISMATCH sample=%0d label=%s expected=%0h actual=%0h",
                     samples, label, expected, actual);
        end
    endtask

    task automatic check64(input logic [63:0] actual,
                           input logic [63:0] expected,
                           input string label);
        begin
            assertions = assertions + 1;
            if (actual !== expected) mismatch(label, expected, actual);
        end
    endtask

    task automatic check_expected_context(input logic [COUNT_W-1:0] period,
                                          input logic [COUNT_W-1:0] high0,
                                          input logic [COUNT_W-1:0] high1,
                                          input logic [COUNT_W-1:0] high2,
                                          input logic [TAG_W-1:0] tag,
                                          input string label);
        begin
            check64(expected_period, period, label);
            check64(expected_high0, high0, label);
            check64(expected_high1, high1, label);
            check64(expected_high2, high2, label);
            check64(expected_tag, tag, label);
        end
    endtask

    task automatic check_zero_context(input string label);
        begin
            check_expected_context(COUNT_ZERO, COUNT_ZERO, COUNT_ZERO,
                                   COUNT_ZERO, TAG_ZERO, label);
        end
    endtask

    task automatic check_unbound(input string label);
        begin
            check64(window_active, 1'b0, label);
            check_zero_context(label);
            check64(out_valid, 1'b0, label);
            check64(capture_armed, 1'b0, label);
        end
    endtask

    task automatic group_begin(input string name);
        begin
            groups = groups + 1;
            current_group = name;
            group_cases_start = cases;
            group_samples_start = samples;
            group_assertions_start = assertions;
            group_mismatches_start = mismatches;
            group_records_start = records;
            group_raw_faults_start = raw_faults;
            group_failure_events_start = failure_events;
            group_window_starts_start = window_starts;
            group_handshakes_start = handshakes;
            $display("GROUP_BEGIN %s", name);
        end
    endtask

    task automatic group_end(input string name);
        begin
            $display("GROUP_END %s cases=%0d samples=%0d assertions=%0d mismatches=%0d records=%0d raw_faults=%0d failure_events=%0d window_starts=%0d handshakes=%0d",
                     name,
                     cases - group_cases_start,
                     samples - group_samples_start,
                     assertions - group_assertions_start,
                     mismatches - group_mismatches_start,
                     records - group_records_start,
                     raw_faults - group_raw_faults_start,
                     failure_events - group_failure_events_start,
                     window_starts - group_window_starts_start,
                     handshakes - group_handshakes_start);
        end
    endtask

    task automatic cycle(input logic rst_i,
                         input logic stop_i,
                         input logic cfg_valid_i,
                         input logic out_ready_i,
                         input logic [2:0] levels_i);
        integer index;
        begin
            @(negedge clk);
            rst = rst_i;
            stop = stop_i;
            cfg_valid = cfg_valid_i;
            out_ready = out_ready_i;
            stimulus_levels = levels_i;
            #1;
            pre_cfg_ready = cfg_ready;
            pre_applied = applied;
            pre_out_valid = out_valid;
            pre_out_ready = out_ready;
            samples = samples + 1;
            if (pre_out_valid && pre_out_ready) begin
                handshakes = handshakes + 1;
                assertions = assertions + 1;
                $display("HANDSHAKE sample=%0d period=%0d h0=%0d h1=%0d h2=%0d start=%0d end=%0d tag=%0h",
                         samples, out_period, out_high0, out_high1, out_high2,
                         out_start, out_end, out_tag);
                if ((out_period !== expected_period) ||
                    (out_high0 !== expected_high0) ||
                    (out_high1 !== expected_high1) ||
                    (out_high2 !== expected_high2) ||
                    (out_tag !== expected_tag)) begin
                    mismatch("handshake_raw_matches_expected",
                             {64'b0, expected_tag}, {64'b0, out_tag});
                end
            end
            @(posedge clk);
            #1;
            if (window_started) window_starts = window_starts + 1;
            if (failure_event) failure_events = failure_events + 1;
            if (raw_fault_events !== 4'b0000) raw_faults = raw_faults + 1;
            if (out_valid) begin
                assertions = assertions + 1;
                if (!window_active) mismatch("out_valid_requires_window", 1, window_active);
                if (!capture_armed) mismatch("out_valid_requires_armed", 1, capture_armed);
                if (raw_fault_events !== 4'b0000) mismatch("out_valid_requires_no_raw_fault", 0, raw_fault_events);
                if ((out_period !== expected_period) ||
                    (out_high0 !== expected_high0) ||
                    (out_high1 !== expected_high1) ||
                    (out_high2 !== expected_high2) ||
                    (out_tag !== expected_tag)) begin
                    mismatch("out_valid_raw_matches_expected",
                             {64'b0, expected_tag}, {64'b0, out_tag});
                end
            end
            for (index = 0; index < 1; index = index + 1) begin
                if (rst_i && (window_active || window_started || failure_event ||
                              (failure_code != 3'd0))) begin
                    mismatch("reset_outputs_clean", 0,
                             {failure_code, failure_event, window_started, window_active});
                end
            end
        end
    endtask

    task automatic reset_dut;
        begin
            cfg_valid = 1'b0;
            out_ready = 1'b0;
            stimulus_levels = 3'b000;
            cycle(1'b1, 1'b0, 1'b0, 1'b0, 3'b000);
            check_unbound("reset_edge_unbound");
            check64(window_started, 1'b0, "reset_edge_no_start");
            check64(failure_event, 1'b0, "reset_edge_no_failure");
            check64(failure_code, 3'd0, "reset_edge_code0");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            check_unbound("reset_release_unbound");
            check64(failure_code, 3'd0, "reset_release_code0");
        end
    endtask

    task automatic submit_command(input logic [COUNT_W-1:0] period,
                                  input logic [COUNT_W-1:0] high0,
                                  input logic [COUNT_W-1:0] high1,
                                  input logic [COUNT_W-1:0] high2,
                                  input logic [TAG_W-1:0] tag,
                                  input logic ready_i,
                                  input logic [2:0] levels_i,
                                  input string label);
        begin
            cfg_period = period;
            cfg_high_yaw = high0;
            cfg_high_pitch = high1;
            cfg_high_speed = high2;
            cfg_tag = tag;
            cycle(1'b0, 1'b0, 1'b1, ready_i, levels_i);
            check64(pre_cfg_ready, 1'b1, label);
            check64(accepted, 1'b1, label);
            check64(rejected, 1'b0, label);
            check64(applied, 1'b0, label);
            check64(pending, 1'b1, label);
            check_unbound(label);
            check64(window_started, 1'b0, label);
            check64(failure_event, 1'b0, label);
        end
    endtask

    task automatic wait_application_and_observe(input logic [COUNT_W-1:0] period,
                                                input logic [COUNT_W-1:0] high0,
                                                input logic [COUNT_W-1:0] high1,
                                                input logic [COUNT_W-1:0] high2,
                                                input logic [TAG_W-1:0] tag,
                                                input logic [2:0] baseline,
                                                input logic eligible,
                                                input string label);
        integer waited;
        begin
            waited = 0;
            cycle(1'b0, 1'b0, 1'b0, 1'b0, baseline);
            waited = 1;
            while ((applied !== 1'b1) && (waited < 70000)) begin
                cycle(1'b0, 1'b0, 1'b0, 1'b0, baseline);
                waited = waited + 1;
            end
            check64(applied, 1'b1, label);
            check64(pending, 1'b0, label);
            check64(running, 1'b1, label);
            check64(active_period, period, label);
            check64(active_high_yaw, high0, label);
            check64(active_high_pitch, high1, label);
            check64(active_high_speed, high2, label);
            check64(active_tag, tag, label);
            check_unbound(label);
            cycle(1'b0, 1'b0, 1'b0, 1'b0, baseline);
            if (eligible) begin
                check64(window_active, 1'b1, label);
                check64(window_started, 1'b1, label);
                check64(capture_armed, 1'b1, label);
                check64(failure_event, 1'b0, label);
                check64(failure_code, 3'd0, label);
                check_expected_context(period, high0, high1, high2, tag, label);
            end else begin
                check_unbound(label);
                check64(window_started, 1'b0, label);
                check64(failure_event, 1'b1, label);
                check64(failure_code, 3'd6, label);
                cycle(1'b0, 1'b0, 1'b0, 1'b0, baseline);
                check_unbound(label);
                check64(failure_event, 1'b0, label);
                check64(failure_code, 3'd6, label);
            end
        end
    endtask

    task automatic start_application(input logic [COUNT_W-1:0] period,
                                     input logic [COUNT_W-1:0] high0,
                                     input logic [COUNT_W-1:0] high1,
                                     input logic [COUNT_W-1:0] high2,
                                     input logic [TAG_W-1:0] tag,
                                     input logic [2:0] baseline,
                                     input logic eligible,
                                     input string label);
        begin
            submit_command(period, high0, high1, high2, tag, 1'b0,
                           baseline, label);
            wait_application_and_observe(period, high0, high1, high2, tag,
                                         baseline, eligible, label);
        end
    endtask

    task automatic emit_frame(input logic [COUNT_W-1:0] period,
                              input logic [COUNT_W-1:0] high0,
                              input logic [COUNT_W-1:0] high1,
                              input logic [COUNT_W-1:0] high2);
        integer offset;
        logic [2:0] levels;
        begin
            for (offset = 1; offset <= period + 1; offset = offset + 1) begin
                if ((offset == 1) || (offset == period + 1)) begin
                    levels = 3'b111;
                end else begin
                    levels[0] = (offset < high0);
                    levels[1] = (offset < high1);
                    levels[2] = (offset < high2);
                end
                cycle(1'b0, 1'b0, 1'b0, 1'b0, levels);
            end
        end
    endtask

    task automatic emit_continuation(input logic [COUNT_W-1:0] period,
                                     input logic [COUNT_W-1:0] high0,
                                     input logic [COUNT_W-1:0] high1,
                                     input logic [COUNT_W-1:0] high2);
        integer offset;
        logic [2:0] levels;
        begin
            for (offset = 1; offset <= period; offset = offset + 1) begin
                if (offset == period) begin
                    levels = 3'b111;
                end else begin
                    levels[0] = (offset < high0);
                    levels[1] = (offset < high1);
                    levels[2] = (offset < high2);
                end
                cycle(1'b0, 1'b0, 1'b0, 1'b0, levels);
            end
        end
    endtask

    task automatic expect_record(input logic [COUNT_W-1:0] period,
                                 input logic [COUNT_W-1:0] high0,
                                 input logic [COUNT_W-1:0] high1,
                                 input logic [COUNT_W-1:0] high2,
                                 input logic [TAG_W-1:0] tag,
                                 input logic [WITNESS_W-1:0] start_i,
                                 input logic [WITNESS_W-1:0] end_i,
                                 input string label);
        begin
            check64(out_valid, 1'b1, label);
            check64(out_period, period, label);
            check64(out_high0, high0, label);
            check64(out_high1, high1, label);
            check64(out_high2, high2, label);
            check64(out_start, start_i, label);
            check64(out_end, end_i, label);
            check64(out_tag, tag, label);
            check64(window_active, 1'b1, label);
            check64(capture_armed, 1'b1, label);
            check_expected_context(period, high0, high1, high2, tag, label);
            records = records + 1;
        end
    endtask

    task automatic expect_no_record(input string label);
        begin
            check64(out_valid, 1'b0, label);
        end
    endtask

    task automatic group_controls;
        integer hb;
        integer waited;
        logic [COUNT_W-1:0] p2;
        logic [COUNT_W-1:0] p3;
        begin
            group_begin("startup_actual_application_and_registered_observation");
            reset_dut();
            cases = cases + 1;
            cfg_period = 3;
            cfg_high_yaw = 1;
            cfg_high_pitch = 2;
            cfg_high_speed = 1;
            cfg_tag = 8'hA5;
            cycle(1'b0, 1'b0, 1'b1, 1'b0, 3'b000);
            check64(pre_cfg_ready, 1'b1, "startup_T_ready");
            check64(accepted, 1'b1, "startup_accepted");
            check64(rejected, 1'b0, "startup_not_rejected");
            check64(applied, 1'b0, "startup_accepted_not_applied");
            check64(pending, 1'b1, "startup_pending");
            check_unbound("startup_not_bound");
            cycle(1'b0, 1'b0, 1'b1, 1'b0, 3'b000);
            check64(pre_cfg_ready, 1'b0, "held_valid_while_pending_no_T");
            check64(accepted, 1'b0, "held_valid_no_second_accept");
            check64(rejected, 1'b0, "held_valid_not_rejected");
            check64(applied, 1'b1, "startup_actual_application");
            check64(pending, 1'b0, "startup_pending_cleared");
            check64(running, 1'b1, "startup_running");
            check64(active_period, 3, "startup_active_period");
            check64(active_high_yaw, 1, "startup_active_yaw");
            check64(active_high_pitch, 2, "startup_active_pitch");
            check64(active_high_speed, 1, "startup_active_speed");
            check64(active_tag, 8'hA5, "startup_active_tag");
            check_unbound("application_not_observation");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b111);
            check64(window_active, 1'b1, "observation_opens_window");
            check64(window_started, 1'b1, "observation_started_pulse");
            check64(capture_armed, 1'b1, "observation_arms_capture");
            check64(failure_event, 1'b0, "observation_no_failure");
            check_expected_context(3, 1, 2, 1, 8'hA5, "observation_context");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b111);
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b010);
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b111);
            expect_record(3, 1, 2, 1, 8'hA5, 2, 5, "literal_independent_record");
            hb = handshakes;
            cycle(1'b0, 1'b0, 1'b0, 1'b1, 3'b111);
            check64(handshakes, hb + 1, "literal_record_handshakes_once");
            check64(out_valid, 1'b0, "retired_record_not_valid");

            submit_command(2, 1, 1, 1, 8'h5A, 1'b1, 3'b000,
                           "pre_observation_command");
            waited = 0;
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            waited = 1;
            while ((applied !== 1'b1) && (waited < 70000)) begin
                cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
                waited = waited + 1;
            end
            check64(applied, 1'b1, "first_application_before_O");
            check64(active_period, 2, "first_application_active");
            p2 = 2;
            p3 = 4;
            hb = handshakes;
            cfg_period = p3;
            cfg_high_yaw = 1;
            cfg_high_pitch = 2;
            cfg_high_speed = 3;
            cfg_tag = 8'hC3;
            cycle(1'b0, 1'b0, 1'b1, 1'b1, 3'b000);
            check64(pre_applied, 1'b1, "new_T_on_observation_edge");
            check64(pre_cfg_ready, 1'b1, "new_T_on_O_ready");
            check64(accepted, 1'b1, "new_T_on_O_accepted");
            check64(pending, 1'b1, "new_T_on_O_pending");
            check64(handshakes, hb, "new_T_on_O_suppresses_old_handshake");
            check_unbound("new_T_on_O_discards_prior_application");
            check64(window_started, 1'b0, "new_T_on_O_no_prior_start");
            wait_application_and_observe(4, 1, 2, 3, 8'hC3, 3'b000, 1'b1,
                                         "new_T_later_application");

            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b111);
            hb = handshakes;
            cfg_period = 3;
            cfg_high_yaw = 4;
            cfg_high_pitch = 2;
            cfg_high_speed = 1;
            cfg_tag = 8'h33;
            cycle(1'b0, 1'b0, 1'b1, 1'b1, 3'b001);
            check64(pre_cfg_ready, 1'b1, "illegal_T_ready");
            check64(rejected, 1'b1, "illegal_T_rejected");
            check64(accepted, 1'b0, "illegal_T_not_accepted");
            check64(pending, 1'b0, "illegal_T_not_pending");
            check64(handshakes, hb, "illegal_T_no_old_handshake");
            check_unbound("illegal_T_discards_old_binding");
            check64(failure_event, 1'b0, "illegal_T_not_fault");
            check64(failure_code, 3'd0, "illegal_T_clears_code");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            check_unbound("illegal_T_no_automatic_recovery");
            start_application(4, 1, 2, 3, 8'hC3, 3'b000, 1'b1,
                              "legal_application_recovery");
            emit_frame(4, 1, 2, 3);
            expect_record(4, 1, 2, 3, 8'hC3, 1, 5,
                          "recovery_independent_record");
            cases = cases + 1;
            group_end("startup_actual_application_and_registered_observation");
        end
    endtask

    task automatic exhaustive_group(input integer max_period,
                                    input string name);
        integer p;
        integer h0;
        integer h1;
        integer h2;
        logic eligible;
        logic [TAG_W-1:0] tuple_tag;
        begin
            group_begin(name);
            for (p = 1; p <= max_period; p = p + 1) begin
                for (h0 = 0; h0 <= p; h0 = h0 + 1) begin
                    for (h1 = 0; h1 <= p; h1 = h1 + 1) begin
                        for (h2 = 0; h2 <= p; h2 = h2 + 1) begin
                            cases = cases + 1;
                            eligible = (p >= 2) && (h0 > 0) && (h0 < p) &&
                                       (h1 > 0) && (h1 < p) &&
                                       (h2 > 0) && (h2 < p);
                            tuple_tag = p ^ (h0 << 1) ^ (h1 << 2) ^ (h2 << 3);
                            reset_dut();
                            start_application(p, h0, h1, h2, tuple_tag,
                                              3'b000, eligible,
                                              "exhaustive_classification");
                            if (eligible) begin
                                emit_frame(p, h0, h1, h2);
                                expect_record(p, h0, h1, h2, tuple_tag,
                                              1, p + 1,
                                              "exhaustive_sampled_record");
                                cycle(1'b0, 1'b0, 1'b0, 1'b1, 3'b000);
                                check64(out_valid, 1'b0,
                                        "exhaustive_record_handshake");
                            end else begin
                                expect_no_record("ineligible_no_record");
                            end
                        end
                    end
                end
            end
            group_end(name);
        end
    endtask

    task automatic group_faults_and_recovery;
        integer hb;
        integer i;
        begin
            group_begin("faults_backpressure_raw_expected_separation_recovery");
            cases = cases + 1;
            reset_dut();
            start_application(3, 1, 2, 1, 8'h11, 3'b000, 1'b1,
                              "mismatch_window_start");
            emit_frame(4, 1, 1, 1);
            expect_no_record("wrong_period_not_external_valid");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            check_unbound("wrong_period_closes");
            check64(failure_event, 1'b1, "wrong_period_failure_pulse");
            check64(failure_code, 3'd1, "wrong_period_code1");

            start_application(3, 1, 2, 1, 8'h11, 3'b000, 1'b1,
                              "same_tuple_tag_recovery_1");
            emit_frame(3, 1, 2, 1);
            expect_record(3, 1, 2, 1, 8'h11, 1, 4,
                          "same_tuple_tag_recovered_record_1");
            for (i = 0; i < 3; i = i + 1) begin
                cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
                check64(out_valid, 1'b1, "backpressure_holds_valid");
                check64(out_period, 3, "backpressure_period_stable");
                check64(out_high0, 1, "backpressure_h0_stable");
                check64(out_high1, 2, "backpressure_h1_stable");
                check64(out_high2, 1, "backpressure_h2_stable");
            end
            hb = handshakes;
            cycle(1'b0, 1'b0, 1'b0, 1'b1, 3'b000);
            check64(handshakes, hb + 1, "backpressured_record_handshake");
            check64(out_valid, 1'b0, "backpressured_record_retired");

            start_application(3, 1, 2, 1, 8'h11, 3'b000, 1'b1,
                              "phase_shape_window_start");
            emit_frame(3, 1, 1, 1);
            expect_no_record("equal_period_wrong_high_not_valid");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            check_unbound("equal_period_wrong_high_closes");
            check64(failure_event, 1'b1, "equal_period_failure_pulse");
            check64(failure_code, 3'd1, "equal_period_code1");

            start_application(3, 1, 2, 1, 8'h11, 3'b000, 1'b1,
                              "same_tuple_tag_recovery_2");
            emit_frame(3, 1, 2, 1);
            expect_record(3, 1, 2, 1, 8'h11, 1, 4,
                          "same_tuple_tag_recovered_record_2");

            start_application(3, 1, 2, 1, 8'h11, 3'b000, 1'b1,
                              "incoherent_window_start");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b111);
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b001);
            check64(raw_fault_events, 4'b0001, "incoherent_raw_event_immediate");
            check64(out_valid, 1'b0, "incoherent_masks_immediately");
            check64(window_active, 1'b1, "incoherent_registered_latency_window");
            check64(failure_event, 1'b0, "incoherent_not_yet_wrapper_fault");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            check_unbound("incoherent_closes_next_edge");
            check64(failure_event, 1'b1, "incoherent_failure_pulse");
            check64(failure_code, 3'd2, "incoherent_code2");

            start_application(3, 1, 2, 1, 8'h11, 3'b000, 1'b1,
                              "overrun_window_start");
            emit_frame(3, 1, 2, 1);
            expect_record(3, 1, 2, 1, 8'h11, 1, 4,
                          "pre_overrun_record");
            emit_continuation(3, 1, 2, 1);
            check64(raw_fault_events, 4'b1000, "overrun_raw_event");
            check64(out_valid, 1'b0, "overrun_masks_full_slot");
            check64(window_active, 1'b1, "overrun_registered_latency_window");
            check64(failure_event, 1'b0, "overrun_not_yet_wrapper_fault");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            check_unbound("overrun_closes_next_edge");
            check64(failure_event, 1'b1, "overrun_failure_pulse");
            check64(failure_code, 3'd5, "overrun_code5");

            start_application(3, 1, 2, 1, 8'h11, 3'b000, 1'b1,
                              "same_tuple_tag_recovery_3");
            emit_frame(3, 1, 2, 1);
            expect_record(3, 1, 2, 1, 8'h11, 1, 4,
                          "same_tuple_tag_recovered_record_3");
            group_end("faults_backpressure_raw_expected_separation_recovery");
        end
    endtask

    task automatic group_min_width_exhaustion;
        begin
            group_begin("count_w2_witness_w2_exhaustion_and_recovery");
            cases = cases + 1;
            reset_dut();
            start_application(2, 1, 1, 1, 1'b1, 3'b000, 1'b1,
                              "witness_w2_window_start");
            emit_frame(2, 1, 1, 1);
            expect_record(2, 1, 1, 1, 1'b1, 1, 3,
                          "witness_w2_first_record");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            check64(raw_fault_events, 4'b0100,
                    "witness_w2_exhaustion_event");
            check64(out_valid, 1'b0, "witness_exhaustion_masks_record");
            check64(window_active, 1'b1, "witness_exhaustion_latency");
            check64(failure_event, 1'b0, "witness_exhaustion_not_yet_fault");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            check_unbound("witness_exhaustion_closes");
            check64(failure_event, 1'b1, "witness_failure_pulse");
            check64(failure_code, 3'd4, "witness_code4");
            start_application(2, 1, 1, 1, 1'b1, 3'b000, 1'b1,
                              "witness_same_tag_recovery");
            emit_frame(2, 1, 1, 1);
            expect_record(2, 1, 1, 1, 1'b1, 1, 3,
                          "witness_recovered_record");
            group_end("count_w2_witness_w2_exhaustion_and_recovery");
        end
    endtask

    task automatic group_count16_boundaries;
        integer n;
        begin
            group_begin("count_w16_full_period_and_raw_overflow");
            cases = cases + 1;
            reset_dut();
            start_application(65535, 1, 2, 3, 16'hA55A, 3'b000, 1'b1,
                              "period65535_window_start");
            emit_frame(65535, 1, 2, 3);
            expect_record(65535, 1, 2, 3, 16'hA55A, 1, 65536,
                          "period65535_fully_observed");
            cycle(1'b0, 1'b0, 1'b0, 1'b1, 3'b000);
            check64(out_valid, 1'b0, "period65535_handshake");

            cases = cases + 1;
            start_application(65535, 1, 2, 3, 16'hA55A, 3'b000, 1'b1,
                              "period_overflow_window_start");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b111);
            for (n = 2; n <= 65537; n = n + 1) begin
                cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            end
            check64(raw_fault_events, 4'b0010,
                    "raw_period_overflow_65536");
            check64(out_valid, 1'b0, "period_overflow_masks_output");
            check64(window_active, 1'b1, "period_overflow_latency");
            check64(failure_event, 1'b0, "period_overflow_not_yet_fault");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            check_unbound("period_overflow_closes");
            check64(failure_event, 1'b1, "period_overflow_failure_pulse");
            check64(failure_code, 3'd3, "period_overflow_code3");
            group_end("count_w16_full_period_and_raw_overflow");
        end
    endtask

    task automatic group_max_widths;
        begin
            group_begin("count_w32_witness_w64_tag_w64_bounded");
            cases = cases + 1;
            reset_dut();
            start_application(7, 1, 3, 6, TAG_ONES, 3'b000, 1'b1,
                              "max_width_window_start");
            emit_frame(7, 1, 3, 6);
            expect_record(7, 1, 3, 6, TAG_ONES, 1, 8,
                          "max_width_bounded_record");
            cycle(1'b0, 1'b0, 1'b0, 1'b1, 3'b000);
            check64(out_valid, 1'b0, "max_width_handshake");
            cases = cases + 1;
            start_application(3, 1, 2, 1, TAG_ZERO, 3'b000, 1'b1,
                              "zero_tag_window_start");
            emit_frame(3, 1, 2, 1);
            expect_record(3, 1, 2, 1, TAG_ZERO, 1, 4,
                          "zero_tag_record");
            group_end("count_w32_witness_w64_tag_w64_bounded");
        end
    endtask

    task automatic group_default_smoke;
        begin
            group_begin("default_width_smoke");
            cases = cases + 1;
            reset_dut();
            start_application(7, 1, 3, 5, 32'h1234_5678, 3'b000, 1'b1,
                              "default_window_start");
            emit_frame(7, 1, 3, 5);
            expect_record(7, 1, 3, 5, 32'h1234_5678, 1, 8,
                          "default_record");
            group_end("default_width_smoke");
        end
    endtask

    task automatic group_loopback_record;
        integer n;
        begin
            group_begin("actual_digital_loopback_complete_interval");
            cases = cases + 1;
            reset_dut();
            start_application(3, 1, 2, 1, 8'h7E, 3'b000, 1'b1,
                              "loopback_window_start");
            for (n = 1; n <= 6; n = n + 1) begin
                cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            end
            expect_record(3, 1, 2, 1, 8'h7E, 3, 6,
                          "actual_digital_loopback_record");
            cycle(1'b0, 1'b0, 1'b0, 1'b1, 3'b000);
            check64(out_valid, 1'b0, "loopback_handshake");
            group_end("actual_digital_loopback_complete_interval");
        end
    endtask

    task automatic group_loopback_exhaustion;
        begin
            group_begin("actual_digital_loopback_witness_exhaustion");
            cases = cases + 1;
            reset_dut();
            start_application(2, 1, 1, 1, 1'b1, 3'b000, 1'b1,
                              "loopback_w2_window_start");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            check64(raw_fault_events, 4'b0100,
                    "loopback_w2_witness_event");
            check64(out_valid, 1'b0, "loopback_w2_no_invented_record");
            cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
            check_unbound("loopback_w2_closes");
            check64(failure_event, 1'b1, "loopback_w2_failure_pulse");
            check64(failure_code, 3'd4, "loopback_w2_code4");
            group_end("actual_digital_loopback_witness_exhaustion");
        end
    endtask

    task automatic drive_partial(input integer sample_count);
        integer n;
        logic [2:0] levels;
        begin
            for (n = 1; n <= sample_count; n = n + 1) begin
                if (n == 1) levels = 3'b111;
                else levels = 3'b000;
                cycle(1'b0, 1'b0, 1'b0, 1'b0, levels);
            end
        end
    endtask

    task automatic group_phase_controls;
        integer phase;
        integer hb;
        begin
            group_begin("reset_stop_and_T_at_every_bounded_phase");
            for (phase = 0; phase <= 4; phase = phase + 1) begin
                reset_dut();
                start_application(3, 1, 2, 1, 8'h21, 3'b000, 1'b1,
                                  "phase_T_initial_window");
                drive_partial(phase);
                hb = handshakes;
                submit_command(4, 1, 2, 3, 8'h22, 1'b1, 3'b000,
                               "phase_T_at_boundary");
                check64(handshakes, hb, "phase_T_old_slot_never_handshakes");
                wait_application_and_observe(4, 1, 2, 3, 8'h22, 3'b000, 1'b1,
                                             "phase_T_new_application");
                cases = cases + 1;

                drive_partial(phase);
                cycle(1'b0, 1'b1, 1'b0, 1'b0, 3'b000);
                check_unbound("phase_stop_unbound");
                check64(failure_event, 1'b0, "phase_stop_not_fault");
                check64(failure_code, 3'd0, "phase_stop_code0");
                cycle(1'b0, 1'b1, 1'b0, 1'b0, 3'b000);
                check_unbound("phase_stop_held_unbound");
                check64(failure_event, 1'b0, "phase_stop_held_not_fault");
                cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
                check_unbound("phase_stop_release_no_auto_recovery");
                cases = cases + 1;

                start_application(3, 1, 2, 1, 8'h23, 3'b000, 1'b1,
                                  "phase_reset_prepare_window");
                drive_partial(phase);
                cycle(1'b1, 1'b0, 1'b0, 1'b0, 3'b000);
                check_unbound("phase_reset_unbound");
                check64(failure_event, 1'b0, "phase_reset_not_fault");
                check64(failure_code, 3'd0, "phase_reset_code0");
                cycle(1'b1, 1'b0, 1'b0, 1'b0, 3'b000);
                check_unbound("phase_reset_held_unbound");
                cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
                check_unbound("phase_reset_release_no_auto_recovery");
                cases = cases + 1;

                start_application(3, 1, 2, 1, 8'h23, 3'b000, 1'b1,
                                  "phase_next_iteration_prepare");
            end
            group_end("reset_stop_and_T_at_every_bounded_phase");
        end
    endtask

    task automatic group_t_boundary(input logic same_tag,
                                    input string name);
        integer hb;
        logic [TAG_W-1:0] next_tag;
        begin
            group_begin(name);
            cases = cases + 1;
            reset_dut();
            start_application(3, 1, 2, 1, 8'h31, 3'b000, 1'b1,
                              "old_window_start");
            emit_frame(3, 1, 2, 1);
            expect_record(3, 1, 2, 1, 8'h31, 1, 4,
                          "old_matched_slot_present");
            if (same_tag) begin
                cfg_period = 3;
                cfg_high_yaw = 1;
                cfg_high_pitch = 2;
                cfg_high_speed = 1;
                next_tag = 8'h31;
            end else begin
                cfg_period = 2;
                cfg_high_yaw = 1;
                cfg_high_pitch = 1;
                cfg_high_speed = 1;
                next_tag = 8'h32;
            end
            cfg_tag = next_tag;
            hb = handshakes;
            cycle(1'b0, 1'b0, 1'b1, 1'b1, 3'b000);
            check64(pre_out_valid, 1'b0, "T_suppresses_preexisting_out_valid");
            check64(handshakes, hb, "T_suppresses_old_handshake");
            check64(accepted, 1'b1, "T_boundary_accepted");
            check64(pending, 1'b1, "T_boundary_pending");
            check_unbound("T_boundary_clears_binding");
            check64(window_started, 1'b0, "T_boundary_no_start");
            cycle(1'b0, 1'b0, 1'b0, 1'b1, 3'b000);
            check_unbound("T_boundary_pending_cycle_unbound");
            wait_application_and_observe(cfg_period, cfg_high_yaw,
                                         cfg_high_pitch, cfg_high_speed,
                                         next_tag, 3'b000, 1'b1,
                                         "T_boundary_new_application");
            expect_no_record("T_boundary_no_same_edge_creation");
            group_end(name);
        end
    endtask

    task automatic group_mismatch_admission_control;
        integer hb;
        begin
            group_begin("mismatch_never_admitted_public_control");
            cases = cases + 1;
            reset_dut();
            start_application(3, 1, 2, 1, 8'h41, 3'b000, 1'b1,
                              "mismatch_control_window_start");
            emit_frame(4, 1, 1, 1);
            expect_no_record("mismatch_control_not_external_valid");
            hb = handshakes;
            cycle(1'b0, 1'b0, 1'b0, 1'b1, 3'b000);
            check64(handshakes, hb, "mismatch_control_no_handshake");
            check_unbound("mismatch_control_closes");
            check64(failure_event, 1'b1, "mismatch_control_failure_pulse");
            check64(failure_code, 3'd1, "mismatch_control_code1");
            group_end("mismatch_never_admitted_public_control");
        end
    endtask

    // PATCH_INSERT_TASKS

    initial begin
        repeat (2) @(negedge clk);
        case (TEST_GROUP)
            0: group_controls();
            1: exhaustive_group(3, "exhaustive_count_w2_all_legal_tuples");
            2: exhaustive_group(7, "exhaustive_count_w3_all_legal_tuples");
            3: group_faults_and_recovery();
            4: group_min_width_exhaustion();
            5: group_count16_boundaries();
            6: group_max_widths();
            7: group_default_smoke();
            8: group_loopback_record();
            9: group_loopback_exhaustion();
            10: group_phase_controls();
            20: group_t_boundary(1'b0, "T_boundary_public_control");
            21: group_t_boundary(1'b1, "same_tag_boundary_public_control");
            22: group_mismatch_admission_control();
            30: begin
                group_begin("code7_deliberate_faulty_copy");
                reset_dut();
                start_application(3, 1, 2, 1, 8'h71, 3'b000, 1'b1,
                                  "code7_probe_window_start");
                cycle(1'b0, 1'b0, 1'b0, 1'b0, 3'b000);
                check_unbound("code7_probe_closes");
                check64(failure_event, 1'b1, "code7_probe_failure_pulse");
                check64(failure_code, 3'd7, "code7_probe_code7");
                group_end("code7_deliberate_faulty_copy");
            end
            default: begin
                group_begin("invalid_test_group");
                cases = cases + 1;
                mismatch("unknown_test_group", 0, TEST_GROUP);
                group_end("invalid_test_group");
            end
        endcase
        $display("TB_STATS groups=%0d cases=%0d samples=%0d assertions=%0d records=%0d raw_faults=%0d failure_events=%0d window_starts=%0d handshakes=%0d mismatches=%0d",
                 groups, cases, samples, assertions, records, raw_faults,
                 failure_events, window_starts, handshakes, mismatches);
        if (mismatches == 0) begin
            $display("TB_PASS group=%0d loopback=%0d", TEST_GROUP, LOOPBACK);
            $finish;
        end else begin
            $display("TB_FAIL group=%0d mismatches=%0d", TEST_GROUP, mismatches);
            $fatal(1, "TB_FAIL public-port self-check");
        end
    end
endmodule

module tb_invalid_applied_capture #(
    parameter integer COUNT_W   = 32,
    parameter integer WITNESS_W = 64,
    parameter integer TAG_W     = 32
);
    logic          clk;
    logic [31:0]   cfg_period;
    logic [31:0]   cfg_high_yaw;
    logic [31:0]   cfg_high_pitch;
    logic [31:0]   cfg_high_speed;
    logic [63:0]   cfg_tag;

    deepeye_pwm_applied_capture #(
        .COUNT_W(COUNT_W),
        .WITNESS_W(WITNESS_W),
        .TAG_W(TAG_W)
    ) dut (
        .clk(clk),
        .rst(1'b1),
        .stop(1'b0),
        .cfg_valid(1'b0),
        .cfg_ready(),
        .cfg_period(cfg_period),
        .cfg_high_yaw(cfg_high_yaw),
        .cfg_high_pitch(cfg_high_pitch),
        .cfg_high_speed(cfg_high_speed),
        .cfg_tag(cfg_tag),
        .sample_levels(3'b000),
        .out_ready(1'b0),
        .accepted(),
        .rejected(),
        .applied(),
        .frame_start(),
        .running(),
        .pending(),
        .pwm(),
        .active_period(),
        .active_high_yaw(),
        .active_high_pitch(),
        .active_high_speed(),
        .active_tag(),
        .window_active(),
        .window_started(),
        .capture_armed(),
        .out_valid(),
        .out_period(),
        .out_high0(),
        .out_high1(),
        .out_high2(),
        .out_start(),
        .out_end(),
        .out_tag(),
        .expected_period(),
        .expected_high0(),
        .expected_high1(),
        .expected_high2(),
        .expected_tag(),
        .raw_fault_events(),
        .failure_event(),
        .failure_code()
    );

    initial begin
        clk = 1'b0;
        cfg_period = 32'd0;
        cfg_high_yaw = 32'd0;
        cfg_high_pitch = 32'd0;
        cfg_high_speed = 32'd0;
        cfg_tag = 64'd0;
    end

    initial begin
        forever #5 clk = ~clk;
    end

    initial begin
        #20;
        $display("APPLIED_CAPTURE_INVALID_GUARD_MISSING COUNT_W=%0d WITNESS_W=%0d TAG_W=%0d",
                 COUNT_W, WITNESS_W, TAG_W);
        $fatal(1, "APPLIED_CAPTURE_INVALID_GUARD_MISSING");
    end
endmodule
