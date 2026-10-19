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

    // PATCH_INSERT_TASKS

    // PATCH_INSERT_DISPATCH
endmodule
