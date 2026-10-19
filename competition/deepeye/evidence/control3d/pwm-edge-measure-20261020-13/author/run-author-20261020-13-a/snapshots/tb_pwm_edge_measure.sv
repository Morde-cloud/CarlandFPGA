// tb_pwm_edge_measure - self-checking signal-stimulus testbench for
// deepeye_pwm_edge_measure.
//
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Work: B-PWM-EDGE-MEASURE-RTL-20261020-13-v1
// Product operation: B-DEEPEYE-PWM-EDGE-MEASURE-20261020-13
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Normative scope SHA256:
// cc7960d77300fcd46a2b8e6e5e0aca1adafc99842d172934ab77ca8d593b3a90.
//
// This testbench drives only the public synchronous ports with sampled signal
// levels, controls, tags and consumer readiness. It does not force internal
// signals and does not use generator settings as an oracle. A separately coded
// event-index/queue reference model updates from the sampled input stream and
// is compared on every sampled clock edge. Directed hard-coded expectations
// additionally check exact records and event counts. The plusarg RUNLOG writes
// replayable run-length stimulus and observed event lines.
//
// A positive run prints TB_PASS. A mismatch prints MISMATCH lines and TB_FAIL.

`timescale 1ns/1ps

module tb_pwm_edge_measure #(
    parameter integer COUNT_W = 32,
    parameter integer TAG_W   = 32
);

    localparam logic [COUNT_W-1:0] TB_MAX      = {COUNT_W{1'b1}};
    localparam logic [TAG_W-1:0]   TB_TAG_ZERO = {TAG_W{1'b0}};
    localparam logic [TAG_W-1:0]   TB_TAG_ONES = {TAG_W{1'b1}};

    logic                 clk;
    logic                 rst;
    logic                 stop;
    logic                 rearm;
    logic                 sample_level;
    logic [TAG_W-1:0]     window_tag;
    logic                 out_ready;

    logic                 armed;
    logic                 out_valid;
    logic [COUNT_W-1:0]   out_period;
    logic [COUNT_W-1:0]   out_high;
    logic [TAG_W-1:0]     out_tag;
    logic                 overflow_event;
    logic                 overrun_event;
    logic                 overflow_seen;
    logic                 overrun_seen;
    logic [COUNT_W-1:0]   loss_count;

    deepeye_pwm_edge_measure #(
        .COUNT_W(COUNT_W),
        .TAG_W(TAG_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .stop(stop),
        .rearm(rearm),
        .sample_level(sample_level),
        .window_tag(window_tag),
        .out_ready(out_ready),
        .armed(armed),
        .out_valid(out_valid),
        .out_period(out_period),
        .out_high(out_high),
        .out_tag(out_tag),
        .overflow_event(overflow_event),
        .overrun_event(overrun_event),
        .overflow_seen(overflow_seen),
        .overrun_seen(overrun_seen),
        .loss_count(loss_count)
    );
    // ------------------------------------------------------------------
    // Independent reference model state. This is a software-style model of
    // the frozen rules, using explicit sampled event indices and a one-slot
    // queue. It is not instantiated from the RTL.
    // ------------------------------------------------------------------
    logic               ref_armed;
    logic               ref_prev;
    logic               ref_have_r0;
    logic               ref_have_f0;
    logic [COUNT_W-1:0] ref_index;
    logic [COUNT_W-1:0] ref_high;
    logic               ref_slot_valid;
    logic [COUNT_W-1:0] ref_out_period;
    logic [COUNT_W-1:0] ref_out_high;
    logic [TAG_W-1:0]   ref_out_tag;
    logic [TAG_W-1:0]   ref_tag_latched;
    logic               ref_ov_pulse;
    logic               ref_or_pulse;
    logic               ref_ov_seen;
    logic               ref_or_seen;
    logic [COUNT_W-1:0] ref_loss;
    logic               ref_out_valid;

    logic               ref_handshake;
    logic [COUNT_W-1:0] ref_handshake_period;
    logic [COUNT_W-1:0] ref_handshake_high;
    logic [TAG_W-1:0]   ref_handshake_tag;
    logic               ref_record_new;
    logic [COUNT_W-1:0] ref_record_period;
    logic [COUNT_W-1:0] ref_record_high;
    logic [TAG_W-1:0]   ref_record_tag;

    // ------------------------------------------------------------------
    // Statistics and replay state.
    // ------------------------------------------------------------------
    integer cycles;
    integer cycle_assertions;
    integer directed_checks;
    integer records_checked;
    integer records_generated;
    integer handshakes;
    integer overflow_events;
    integer overrun_events;
    integer mismatches;
    integer groups;
    integer cases;
    integer random_cycles;

    logic prev_out_valid;
    logic [COUNT_W-1:0] prev_period;
    logic [COUNT_W-1:0] prev_high;
    logic [TAG_W-1:0]   prev_tag;
    logic prev_ready;
    logic prev_abort;
    logic prev_checked;

    integer runlog_fd;
    logic runlog_en;
    reg [1023:0] runlog_path;
    integer seed;
    integer smoke;

    logic        last_logged;
    logic        last_rst;
    logic        last_stop;
    logic        last_rearm;
    logic        last_level;
    logic        last_ready;
    logic [TAG_W-1:0] last_tag;

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    function automatic integer max_int();
        if (COUNT_W >= 32) begin
            max_int = 32'h7FFFFFFF;
        end else begin
            max_int = TB_MAX;
        end
    endfunction

    function automatic integer common_p();
        common_p = (COUNT_W >= 3) ? 5 : 3;
    endfunction

    function automatic integer common_h();
        common_h = (COUNT_W >= 3) ? 2 : 1;
    endfunction

    function automatic logic [31:0] lfsr_next(input logic [31:0] v);
        lfsr_next = {v[30:0], v[31] ^ v[21] ^ v[1] ^ v[0]};
    endfunction

    task automatic mismatch(input string field,
                            input logic [63:0] exp,
                            input logic [63:0] act);
        begin
            mismatches = mismatches + 1;
            if (mismatches <= 50) begin
                $display("MISMATCH cycle=%0d field=%s exp=%0h act=%0h",
                         cycles, field, exp, act);
            end
        end
    endtask
    task automatic ref_step(input logic rst_i,
                            input logic stop_i,
                            input logic rearm_i,
                            input logic level_i,
                            input logic ready_i,
                            input logic [TAG_W-1:0] tag_i);
        logic handshake;
        logic [COUNT_W-1:0] next_index;
        begin
            ref_ov_pulse     = 1'b0;
            ref_or_pulse     = 1'b0;
            ref_handshake    = 1'b0;
            ref_record_new   = 1'b0;
            ref_handshake_period = '0;
            ref_handshake_high   = '0;
            ref_handshake_tag    = TB_TAG_ZERO;
            ref_record_period    = '0;
            ref_record_high      = '0;
            ref_record_tag       = TB_TAG_ZERO;

            if (rst_i || stop_i) begin
                ref_armed       = 1'b0;
                ref_prev        = 1'b0;
                ref_have_r0     = 1'b0;
                ref_have_f0     = 1'b0;
                ref_index       = '0;
                ref_high        = '0;
                ref_slot_valid  = 1'b0;
                ref_out_period  = '0;
                ref_out_high    = '0;
                ref_out_tag     = TB_TAG_ZERO;
                ref_tag_latched = TB_TAG_ZERO;
                ref_ov_seen     = 1'b0;
                ref_or_seen     = 1'b0;
                ref_loss        = '0;
            end else if (rearm_i) begin
                ref_armed       = 1'b1;
                ref_prev        = level_i;
                ref_have_r0     = 1'b0;
                ref_have_f0     = 1'b0;
                ref_index       = '0;
                ref_high        = '0;
                ref_slot_valid  = 1'b0;
                ref_out_period  = '0;
                ref_out_high    = '0;
                ref_out_tag     = TB_TAG_ZERO;
                ref_tag_latched = tag_i;
                ref_ov_seen     = 1'b0;
                ref_or_seen     = 1'b0;
                ref_loss        = '0;
            end else if (ref_armed) begin
                handshake = ref_slot_valid && ready_i;
                if (handshake) begin
                    ref_handshake        = 1'b1;
                    ref_handshake_period = ref_out_period;
                    ref_handshake_high   = ref_out_high;
                    ref_handshake_tag    = ref_out_tag;
                end

                if (ref_have_r0 && (ref_index == TB_MAX)) begin
                    ref_ov_pulse = 1'b1;
                    ref_ov_seen  = 1'b1;
                    if (ref_loss != TB_MAX) begin
                        ref_loss = ref_loss + 1'b1;
                    end
                    ref_high    = '0;
                    ref_index   = '0;
                    ref_have_f0 = 1'b0;
                    if (!ref_prev && level_i) begin
                        ref_have_r0 = 1'b1;
                    end else begin
                        ref_have_r0 = 1'b0;
                    end
                    if (handshake) begin
                        ref_slot_valid = 1'b0;
                        ref_out_period = '0;
                        ref_out_high   = '0;
                        ref_out_tag    = TB_TAG_ZERO;
                    end
                end else if (!ref_have_r0) begin
                    if (!ref_prev && level_i) begin
                        ref_have_r0 = 1'b1;
                        ref_index   = '0;
                    end
                    if (handshake) begin
                        ref_slot_valid = 1'b0;
                        ref_out_period = '0;
                        ref_out_high   = '0;
                        ref_out_tag    = TB_TAG_ZERO;
                    end
                end else if (!ref_have_f0) begin
                    next_index = ref_index + 1'b1;
                    ref_index  = next_index;
                    if (ref_prev && !level_i) begin
                        ref_have_f0 = 1'b1;
                        ref_high    = next_index;
                    end
                    if (handshake) begin
                        ref_slot_valid = 1'b0;
                        ref_out_period = '0;
                        ref_out_high   = '0;
                        ref_out_tag    = TB_TAG_ZERO;
                    end
                end else begin
                    if (!ref_prev && level_i) begin
                        if (ref_slot_valid && !ready_i) begin
                            ref_or_pulse = 1'b1;
                            ref_or_seen  = 1'b1;
                            if (ref_loss != TB_MAX) begin
                                ref_loss = ref_loss + 1'b1;
                            end
                        end else begin
                            ref_slot_valid = 1'b1;
                            ref_out_period = ref_index + 1'b1;
                            ref_out_high   = ref_high;
                            ref_out_tag    = ref_tag_latched;
                            ref_record_new    = 1'b1;
                            ref_record_period = ref_index + 1'b1;
                            ref_record_high   = ref_high;
                            ref_record_tag    = ref_tag_latched;
                        end
                        ref_have_r0 = 1'b1;
                        ref_have_f0 = 1'b0;
                        ref_index   = '0;
                        ref_high    = '0;
                    end else begin
                        ref_index = ref_index + 1'b1;
                        if (handshake) begin
                            ref_slot_valid = 1'b0;
                            ref_out_period = '0;
                            ref_out_high   = '0;
                            ref_out_tag    = TB_TAG_ZERO;
                        end
                    end
                end

                ref_prev = level_i;
            end

            ref_out_valid = ref_slot_valid && !rst_i && !stop_i && !rearm_i;
        end
    endtask
    task automatic check_outputs();
        logic [63:0] act64;
        logic [63:0] exp64;
        begin
            cycle_assertions = cycle_assertions + 10;
            if (armed !== ref_armed) mismatch("armed", ref_armed, armed);
            if (out_valid !== ref_out_valid) mismatch("out_valid", ref_out_valid, out_valid);
            act64 = out_period;
            exp64 = ref_out_period;
            if (act64 !== exp64) mismatch("out_period", exp64, act64);
            act64 = out_high;
            exp64 = ref_out_high;
            if (act64 !== exp64) mismatch("out_high", exp64, act64);
            act64 = out_tag;
            exp64 = ref_out_tag;
            if (act64 !== exp64) mismatch("out_tag", exp64, act64);
            if (overflow_event !== ref_ov_pulse) mismatch("overflow_event", ref_ov_pulse, overflow_event);
            if (overrun_event !== ref_or_pulse) mismatch("overrun_event", ref_or_pulse, overrun_event);
            if (overflow_seen !== ref_ov_seen) mismatch("overflow_seen", ref_ov_seen, overflow_seen);
            if (overrun_seen !== ref_or_seen) mismatch("overrun_seen", ref_or_seen, overrun_seen);
            act64 = loss_count;
            exp64 = ref_loss;
            if (act64 !== exp64) mismatch("loss_count", exp64, act64);

            cycle_assertions = cycle_assertions + 1;
            if (overflow_event && overrun_event) begin
                mismatch("pulse_exclusion", 0, 1);
            end

            if (rst || stop || rearm) begin
                cycle_assertions = cycle_assertions + 1;
                if (out_valid !== 1'b0) begin
                    mismatch("abort_out_valid", 0, out_valid);
                end
            end

            if (prev_checked && prev_out_valid && !prev_ready && !prev_abort &&
                !rst && !stop && !rearm && !out_ready) begin
                cycle_assertions = cycle_assertions + 4;
                if (out_valid !== 1'b1) mismatch("stable_valid", 1, out_valid);
                act64 = out_period;
                exp64 = prev_period;
                if (act64 !== exp64) mismatch("stable_period", exp64, act64);
                act64 = out_high;
                exp64 = prev_high;
                if (act64 !== exp64) mismatch("stable_high", exp64, act64);
                act64 = out_tag;
                exp64 = prev_tag;
                if (act64 !== exp64) mismatch("stable_tag", exp64, act64);
            end

            prev_out_valid = out_valid;
            prev_period    = out_period;
            prev_high      = out_high;
            prev_tag       = out_tag;
            prev_ready     = out_ready;
            prev_abort     = rst || stop || rearm;
            prev_checked   = 1'b1;

            if (overflow_event) begin
                overflow_events = overflow_events + 1;
                if (runlog_en) begin
                    $fdisplay(runlog_fd, "O %0d loss=%0d seen=%0d",
                              cycles, loss_count, overflow_seen);
                end
            end
            if (overrun_event) begin
                overrun_events = overrun_events + 1;
                if (runlog_en) begin
                    $fdisplay(runlog_fd, "V %0d loss=%0d seen=%0d",
                              cycles, loss_count, overrun_seen);
                end
            end
            if (ref_handshake) begin
                handshakes = handshakes + 1;
                if (runlog_en) begin
                    $fdisplay(runlog_fd, "H %0d period=%0d high=%0d tag=%0h",
                              cycles, ref_handshake_period, ref_handshake_high,
                              ref_handshake_tag);
                end
            end
            if (ref_record_new) begin
                records_generated = records_generated + 1;
                if (runlog_en) begin
                    $fdisplay(runlog_fd, "R %0d period=%0d high=%0d tag=%0h",
                              cycles, ref_record_period, ref_record_high,
                              ref_record_tag);
                end
            end
        end
    endtask
    task automatic tick(input logic rst_i,
                        input logic stop_i,
                        input logic rearm_i,
                        input logic level_i,
                        input logic ready_i,
                        input logic [TAG_W-1:0] tag_i);
        begin
            @(negedge clk);
            rst          = rst_i;
            stop         = stop_i;
            rearm        = rearm_i;
            sample_level = level_i;
            out_ready    = ready_i;
            window_tag   = tag_i;
            @(posedge clk);
            #1;
            ref_step(rst_i, stop_i, rearm_i, level_i, ready_i, tag_i);
            cycles = cycles + 1;
            if (runlog_en) begin
                if (!last_logged ||
                    (rst !== last_rst) || (stop !== last_stop) ||
                    (rearm !== last_rearm) || (sample_level !== last_level) ||
                    (out_ready !== last_ready) || (window_tag !== last_tag)) begin
                    $fdisplay(runlog_fd, "S %0d %0d %0d %0d %0d %0h %0d",
                              cycles, rst, stop, rearm, sample_level,
                              window_tag, out_ready);
                    last_rst    = rst;
                    last_stop   = stop;
                    last_rearm  = rearm;
                    last_level  = sample_level;
                    last_ready  = out_ready;
                    last_tag    = window_tag;
                    last_logged = 1'b1;
                end
            end
            check_outputs();
        end
    endtask

    task automatic tick_n(input integer n,
                          input logic level_i,
                          input logic ready_i,
                          input logic [TAG_W-1:0] tag_i);
        integer i;
        begin
            for (i = 0; i < n; i = i + 1) begin
                tick(1'b0, 1'b0, 1'b0, level_i, ready_i, tag_i);
            end
        end
    endtask

    task automatic expect_slot(input integer p,
                               input integer h,
                               input logic [TAG_W-1:0] tg,
                               input string label);
        logic [COUNT_W-1:0] ep;
        logic [COUNT_W-1:0] eh;
        begin
            directed_checks = directed_checks + 1;
            records_checked = records_checked + 1;
            ep = p;
            eh = h;
            if (out_valid !== 1'b1) begin
                mismatch(label, 1, out_valid);
            end else begin
                if (out_period !== ep) mismatch(label, ep, out_period);
                if (out_high !== eh) mismatch(label, eh, out_high);
                if (out_tag !== tg) mismatch(label, tg, out_tag);
            end
            if (runlog_en) begin
                $fdisplay(runlog_fd, "C %0d %s period=%0d high=%0d tag=%0h",
                          cycles, label, p, h, tg);
            end
        end
    endtask

    task automatic expect_no_slot(input string label);
        begin
            directed_checks = directed_checks + 1;
            if (out_valid !== 1'b0) mismatch(label, 0, out_valid);
            if (out_period !== '0) mismatch(label, 0, out_period);
            if (out_high !== '0) mismatch(label, 0, out_high);
            if (out_tag !== '0) mismatch(label, 0, out_tag);
        end
    endtask

    task automatic expect_clean(input string label);
        begin
            directed_checks = directed_checks + 1;
            if (armed !== 1'b0) mismatch(label, 0, armed);
            if (out_valid !== 1'b0) mismatch(label, 0, out_valid);
            if (out_period !== '0) mismatch(label, 0, out_period);
            if (out_high !== '0) mismatch(label, 0, out_high);
            if (out_tag !== '0) mismatch(label, 0, out_tag);
            if (overflow_event !== 1'b0) mismatch(label, 0, overflow_event);
            if (overrun_event !== 1'b0) mismatch(label, 0, overrun_event);
            if (overflow_seen !== 1'b0) mismatch(label, 0, overflow_seen);
            if (overrun_seen !== 1'b0) mismatch(label, 0, overrun_seen);
            if (loss_count !== '0) mismatch(label, 0, loss_count);
        end
    endtask

    task automatic expect_armed_clean(input string label);
        begin
            directed_checks = directed_checks + 1;
            if (armed !== 1'b1) mismatch(label, 1, armed);
            if (out_valid !== 1'b0) mismatch(label, 0, out_valid);
            if (out_period !== '0) mismatch(label, 0, out_period);
            if (out_high !== '0) mismatch(label, 0, out_high);
            if (out_tag !== '0) mismatch(label, 0, out_tag);
            if (overflow_event !== 1'b0) mismatch(label, 0, overflow_event);
            if (overrun_event !== 1'b0) mismatch(label, 0, overrun_event);
            if (overflow_seen !== 1'b0) mismatch(label, 0, overflow_seen);
            if (overrun_seen !== 1'b0) mismatch(label, 0, overrun_seen);
            if (loss_count !== '0) mismatch(label, 0, loss_count);
        end
    endtask
    task automatic check_abort_state(input integer kind,
                                     input logic [TAG_W-1:0] tg);
        begin
            directed_checks = directed_checks + 1;
            if (kind == 2) begin
                if (armed !== 1'b1) mismatch("abort.rearm.armed", 1, armed);
            end else begin
                if (armed !== 1'b0) mismatch("abort.armed", 0, armed);
            end
            if (out_valid !== 1'b0) mismatch("abort.valid", 0, out_valid);
            if (out_period !== '0) mismatch("abort.period", 0, out_period);
            if (out_high !== '0) mismatch("abort.high", 0, out_high);
            if (out_tag !== '0) mismatch("abort.tag", 0, out_tag);
            if (overflow_event !== 1'b0) mismatch("abort.ov", 0, overflow_event);
            if (overrun_event !== 1'b0) mismatch("abort.or", 0, overrun_event);
            if (overflow_seen !== 1'b0) mismatch("abort.ovseen", 0, overflow_seen);
            if (overrun_seen !== 1'b0) mismatch("abort.orseen", 0, overrun_seen);
            if (loss_count !== '0) mismatch("abort.loss", 0, loss_count);
            if (runlog_en) begin
                $fdisplay(runlog_fd, "A %0d kind=%0d tag=%0h", cycles, kind, tg);
            end
        end
    endtask

    task automatic reset_dut();
        begin
            tick(1'b1, 1'b0, 1'b0, 1'b0, 1'b0, TB_TAG_ZERO);
            tick(1'b1, 1'b0, 1'b0, 1'b1, 1'b1, TB_TAG_ONES);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, TB_TAG_ZERO);
            expect_clean("after_reset");
        end
    endtask

    task automatic rearm_dut(input logic baseline,
                             input logic [TAG_W-1:0] tg);
        begin
            tick(1'b0, 1'b0, 1'b1, baseline, 1'b0, tg);
            expect_armed_clean("after_rearm");
        end
    endtask

    task automatic run_frames(input integer p,
                              input integer h,
                              input integer reps,
                              input logic [TAG_W-1:0] tg,
                              input logic ready_const);
        integer r;
        integer i;
        begin
            tick(1'b0, 1'b0, 1'b0, 1'b1, ready_const, tg);
            for (r = 0; r < reps; r = r + 1) begin
                for (i = 1; i < h; i = i + 1) begin
                    tick(1'b0, 1'b0, 1'b0, 1'b1, ready_const, tg);
                end
                tick(1'b0, 1'b0, 1'b0, 1'b0, ready_const, tg);
                for (i = h + 1; i < p; i = i + 1) begin
                    tick(1'b0, 1'b0, 1'b0, 1'b0, ready_const, tg);
                end
                tick(1'b0, 1'b0, 1'b0, 1'b1, ready_const, tg);
                expect_slot(p, h, tg, "run_frames");
            end
        end
    endtask

    task automatic group_begin(input string name);
        begin
            groups = groups + 1;
            $display("GROUP_BEGIN %s", name);
            if (runlog_en) $fdisplay(runlog_fd, "G_BEGIN %s", name);
        end
    endtask

    task automatic group_end(input string name);
        begin
            $display("GROUP_END %s cycles=%0d checks=%0d mismatches=%0d",
                     name, cycles, cycle_assertions, mismatches);
            if (runlog_en) begin
                $fdisplay(runlog_fd, "G_END %s cycles=%0d checks=%0d mismatches=%0d",
                          name, cycles, cycle_assertions, mismatches);
            end
        end
    endtask

    // ------------------------------------------------------------------
    // Directed groups.
    // ------------------------------------------------------------------

    task automatic test_reset_unarmed();
        integer i;
        begin
            group_begin("reset_unarmed");
            reset_dut();
            for (i = 0; i < 8; i = i + 1) begin
                tick(1'b0, 1'b0, 1'b0, (i % 2), ((i / 2) % 2), TB_TAG_ZERO);
                expect_clean("unarmed");
            end
            group_end("reset_unarmed");
        end
    endtask
    task automatic test_rearm_phases();
        integer p;
        integer h;
        begin
            group_begin("rearm_phases");
            p = common_p();
            h = common_h();

            reset_dut();
            rearm_dut(1'b0, 3);
            run_frames(p, h, 1, 3, 1'b1);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, 3);
            expect_no_slot("rearm_low.consume");

            reset_dut();
            rearm_dut(1'b1, 4);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 4);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 4);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 4);
            tick_n(h - 1, 1'b1, 1'b0, 4);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 4);
            tick_n(p - h - 1, 1'b0, 1'b0, 4);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 4);
            expect_slot(p, h, 4, "rearm_high");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, 4);
            expect_no_slot("rearm_high.consume");

            reset_dut();
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 5);
            rearm_dut(1'b1, 5);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 5);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 5);
            tick_n(h - 1, 1'b1, 1'b0, 5);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 5);
            tick_n(p - h - 1, 1'b0, 1'b0, 5);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 5);
            expect_slot(p, h, 5, "rearm_rise");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, 5);
            expect_no_slot("rearm_rise.consume");

            reset_dut();
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 6);
            rearm_dut(1'b0, 6);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 6);
            tick_n(h - 1, 1'b1, 1'b0, 6);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 6);
            tick_n(p - h - 1, 1'b0, 1'b0, 6);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 6);
            expect_slot(p, h, 6, "rearm_fall");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, 6);
            expect_no_slot("rearm_fall.consume");

            group_end("rearm_phases");
        end
    endtask

    task automatic test_held_rearm();
        integer i;
        integer p;
        integer h;
        logic [TAG_W-1:0] last_tag;
        begin
            group_begin("held_rearm");
            p = common_p();
            h = common_h();
            reset_dut();
            last_tag = 9;
            for (i = 0; i < 6; i = i + 1) begin
                last_tag = 9 + i;
                tick(1'b0, 1'b0, 1'b1, (i % 2), 1'b0, last_tag);
                directed_checks = directed_checks + 1;
                if (armed !== 1'b1) mismatch("held_rearm.armed", 1, armed);
                if (out_valid !== 1'b0) mismatch("held_rearm.valid", 0, out_valid);
                if (overflow_seen !== 1'b0) mismatch("held_rearm.ovseen", 0, overflow_seen);
                if (overrun_seen !== 1'b0) mismatch("held_rearm.orseen", 0, overrun_seen);
                if (loss_count !== '0) mismatch("held_rearm.loss", 0, loss_count);
            end
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, last_tag);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, last_tag);
            tick_n(h - 1, 1'b1, 1'b0, last_tag);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, last_tag);
            tick_n(p - h - 1, 1'b0, 1'b0, last_tag);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, last_tag);
            expect_slot(p, h, last_tag, "held_rearm.record");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, last_tag);
            expect_no_slot("held_rearm.consume");
            group_end("held_rearm");
        end
    endtask
    task automatic test_tag_behavior();
        logic [TAG_W-1:0] tag_a;
        logic [TAG_W-1:0] tag_b;
        integer p;
        integer h;
        begin
            group_begin("tag_behavior");
            p = common_p();
            h = common_h();
            if (TAG_W == 1) begin
                tag_a = 1'b0;
                tag_b = 1'b1;
            end else begin
                tag_a = 3;
                tag_b = 5;
            end

            reset_dut();
            rearm_dut(1'b0, TB_TAG_ZERO);
            run_frames(p, h, 1, TB_TAG_ZERO, 1'b1);
            expect_slot(p, h, TB_TAG_ZERO, "tag_zero");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, TB_TAG_ZERO);
            expect_no_slot("tag_zero.consume");

            reset_dut();
            rearm_dut(1'b0, TB_TAG_ONES);
            run_frames(p, h, 1, TB_TAG_ONES, 1'b1);
            expect_slot(p, h, TB_TAG_ONES, "tag_ones");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, TB_TAG_ONES);
            expect_no_slot("tag_ones.consume");

            reset_dut();
            rearm_dut(1'b0, tag_a);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_a);
            tick_n(h - 1, 1'b1, 1'b0, tag_a);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, tag_b);
            tick_n(p - h - 1, 1'b0, 1'b0, tag_b);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_b);
            expect_slot(p, h, tag_a, "tag_latch_a");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_b);
            expect_slot(p, h, tag_a, "tag_latch_a_stable");
            tick(1'b0, 1'b0, 1'b1, 1'b0, 1'b0, tag_b);
            expect_no_slot("tag_rearm_flush");
            directed_checks = directed_checks + 1;
            if (out_tag !== '0) mismatch("tag_rearm_zero", 0, out_tag);
            if (loss_count !== '0) mismatch("tag_rearm_loss", 0, loss_count);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_b);
            tick_n(h - 1, 1'b1, 1'b0, tag_b);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, tag_b);
            tick_n(p - h - 1, 1'b0, 1'b0, tag_b);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_b);
            expect_slot(p, h, tag_b, "tag_b");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, tag_b);
            expect_no_slot("tag_b.consume");
            group_end("tag_behavior");
        end
    endtask
    task automatic test_abort_stages();
        integer k;
        integer p;
        integer h;
        logic r_ctl;
        logic s_ctl;
        logic a_ctl;
        begin
            group_begin("abort_stages");
            p = common_p();
            h = common_h();
            for (k = 0; k < 3; k = k + 1) begin
                r_ctl = (k == 0);
                s_ctl = (k == 1);
                a_ctl = (k == 2);

                reset_dut();
                tick(r_ctl, s_ctl, a_ctl, 1'b0, 1'b0, 11);
                check_abort_state(k, 11);

                reset_dut();
                rearm_dut(1'b0, 11);
                tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 11);
                tick(r_ctl, s_ctl, a_ctl, 1'b0, 1'b0, 11);
                check_abort_state(k, 11);

                reset_dut();
                rearm_dut(1'b0, 11);
                tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 11);
                tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 11);
                tick(r_ctl, s_ctl, a_ctl, 1'b0, 1'b0, 11);
                check_abort_state(k, 11);

                reset_dut();
                rearm_dut(1'b0, 11);
                tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 11);
                tick_n(h - 1, 1'b1, 1'b0, 11);
                tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 11);
                tick_n(p - h - 1, 1'b0, 1'b0, 11);
                tick(r_ctl, s_ctl, a_ctl, 1'b1, 1'b0, 11);
                check_abort_state(k, 11);

                reset_dut();
                rearm_dut(1'b0, 11);
                tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 11);
                tick_n(h - 1, 1'b1, 1'b0, 11);
                tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 11);
                tick_n(p - h - 1, 1'b0, 1'b0, 11);
                tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 11);
                expect_slot(p, h, 11, "abort.fill");
                tick(r_ctl, s_ctl, a_ctl, 1'b1, 1'b1, 11);
                check_abort_state(k, 11);

                tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 11);
                if (k == 2) begin
                    directed_checks = directed_checks + 1;
                    if (armed !== 1'b1) mismatch("abort.rearm.after", 1, armed);
                end else begin
                    expect_clean("abort_deassert");
                end
            end
            group_end("abort_stages");
        end
    endtask
    task automatic test_queue_backpressure();
        integer p;
        integer h;
        integer i;
        integer maxv;
        integer stall_ticks;
        logic [TAG_W-1:0] tag_a;
        logic [TAG_W-1:0] tag_b;
        begin
            group_begin("queue_backpressure");
            p = common_p();
            h = common_h();
            maxv = max_int();
            tag_a = 21;
            tag_b = 22;

            reset_dut();
            rearm_dut(1'b0, tag_a);
            run_frames(p, h, 1, tag_a, 1'b0);
            expect_slot(p, h, tag_a, "queue.fill_a");

            for (i = 0; i < 8; i = i + 1) begin
                tick_n(h - 1, 1'b1, 1'b0, tag_a);
                tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, tag_a);
                tick_n(p - h - 1, 1'b0, 1'b0, tag_a);
                tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_a);
                expect_slot(p, h, tag_a, "queue.overrun_keep");
                directed_checks = directed_checks + 1;
                if (overrun_event !== 1'b1) mismatch("queue.or_pulse", 1, overrun_event);
                if (overflow_event !== 1'b0) mismatch("queue.no_ov", 0, overflow_event);
            end
            directed_checks = directed_checks + 1;
            if (loss_count !== ((8 > maxv) ? maxv : 8)) begin
                mismatch("queue.loss", ((8 > maxv) ? maxv : 8), loss_count);
            end
            if (overrun_seen !== 1'b1) mismatch("queue.orseen", 1, overrun_seen);

            if (maxv > 32) stall_ticks = 30;
            else stall_ticks = maxv - 2;
            tick_n(stall_ticks, 1'b1, 1'b0, tag_a);
            expect_slot(p, h, tag_a, "queue.stall_stable");

            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b1, tag_a);
            expect_no_slot("queue.consume_a");
            directed_checks = directed_checks + 1;
            if (overrun_event !== 1'b0) mismatch("queue.consume_or", 0, overrun_event);
            if (overflow_event !== 1'b0) mismatch("queue.consume_ov", 0, overflow_event);

            reset_dut();
            rearm_dut(1'b0, tag_b);
            run_frames(p, h, 1, tag_b, 1'b1);
            expect_slot(p, h, tag_b, "queue.after_consume");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, tag_b);
            expect_no_slot("queue.consume_b");
            group_end("queue_backpressure");
        end
    endtask

    task automatic test_same_edge_swap();
        integer p;
        integer h;
        logic [TAG_W-1:0] tag_a;
        logic [TAG_W-1:0] tag_b;
        begin
            group_begin("same_edge_swap");
            p = common_p();
            h = common_h();
            tag_a = 31;
            tag_b = 32;

            reset_dut();
            rearm_dut(1'b0, tag_a);
            run_frames(p, h, 1, tag_a, 1'b0);
            expect_slot(p, h, tag_a, "swap.fill_a");

            tick_n(h - 1, 1'b1, 1'b0, tag_b);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, tag_b);
            tick_n(p - h - 1, 1'b0, 1'b0, tag_b);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, tag_b);
            directed_checks = directed_checks + 1;
            if (ref_handshake !== 1'b1) mismatch("swap.handshake", 1, ref_handshake);
            expect_slot(p, h, tag_a, "swap.fill_b");
            directed_checks = directed_checks + 1;
            if (overrun_event !== 1'b0) mismatch("swap.no_or", 0, overrun_event);

            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, tag_b);
            expect_no_slot("swap.consume_b");
            group_end("same_edge_swap");
        end
    endtask

    task automatic test_consume_no_candidate();
        integer p;
        integer h;
        logic [TAG_W-1:0] tag_a;
        begin
            group_begin("consume_no_candidate");
            p = common_p();
            h = common_h();
            tag_a = 41;
            reset_dut();
            rearm_dut(1'b0, tag_a);
            run_frames(p, h, 1, tag_a, 1'b0);
            expect_slot(p, h, tag_a, "consume.fill");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, tag_a);
            expect_no_slot("consume.empty");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b0) mismatch("consume.no_ov", 0, overflow_event);
            if (overrun_event !== 1'b0) mismatch("consume.no_or", 0, overrun_event);
            group_end("consume_no_candidate");
        end
    endtask
    task automatic test_overflow_queue();
        integer p;
        integer h;
        integer maxv;
        logic [TAG_W-1:0] tag_a;
        begin
            group_begin("overflow_queue");
            p = common_p();
            h = common_h();
            maxv = max_int();
            tag_a = 51;

            // Old valid&&ready record is consumed on the overflow edge.
            reset_dut();
            rearm_dut(1'b0, tag_a);
            run_frames(p, h, 1, tag_a, 1'b0);
            expect_slot(p, h, tag_a, "ovq.fill_a");
            tick_n(maxv + 1, 1'b1, 1'b1, tag_a);
            expect_no_slot("ovq.consumed");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b1) mismatch("ovq.ov_pulse", 1, overflow_event);
            if (loss_count !== 1) mismatch("ovq.loss", 1, loss_count);
            if (overrun_event !== 1'b0) mismatch("ovq.no_or", 0, overrun_event);

            // Full stalled slot survives the same overflow unchanged.
            reset_dut();
            rearm_dut(1'b0, tag_a);
            run_frames(p, h, 1, tag_a, 1'b0);
            expect_slot(p, h, tag_a, "ovq.fill_b");
            tick_n(maxv + 1, 1'b1, 1'b0, tag_a);
            expect_slot(p, h, tag_a, "ovq.kept");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b1) mismatch("ovq.ov_pulse2", 1, overflow_event);
            if (loss_count !== 1) mismatch("ovq.loss2", 1, loss_count);
            if (overrun_event !== 1'b0) mismatch("ovq.no_or2", 0, overrun_event);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, tag_a);
            expect_no_slot("ovq.consume");
            group_end("overflow_queue");
        end
    endtask

    task automatic test_flush_discard();
        integer p;
        integer h;
        logic [TAG_W-1:0] tag_a;
        logic [TAG_W-1:0] tag_b;
        begin
            group_begin("flush_discard");
            p = common_p();
            h = common_h();
            tag_a = 61;
            tag_b = 62;
            reset_dut();
            rearm_dut(1'b0, tag_a);
            run_frames(p, h, 1, tag_a, 1'b0);
            expect_slot(p, h, tag_a, "flush.fill");
            tick(1'b0, 1'b0, 1'b1, 1'b0, 1'b0, tag_b);
            expect_no_slot("flush.empty");
            directed_checks = directed_checks + 1;
            if (loss_count !== '0) mismatch("flush.loss", 0, loss_count);
            if (overflow_seen !== 1'b0) mismatch("flush.ovseen", 0, overflow_seen);
            if (overrun_seen !== 1'b0) mismatch("flush.orseen", 0, overrun_seen);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_b);
            tick_n(h - 1, 1'b1, 1'b0, tag_b);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, tag_b);
            tick_n(p - h - 1, 1'b0, 1'b0, tag_b);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_b);
            expect_slot(p, h, tag_b, "flush.new_tag");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, tag_b);
            expect_no_slot("flush.consume");
            group_end("flush_discard");
        end
    endtask
    task automatic test_constant_levels();
        integer i;
        integer maxv;
        logic [TAG_W-1:0] tag_a;
        begin
            group_begin("constant_levels");
            maxv = max_int();
            tag_a = 71;

            reset_dut();
            rearm_dut(1'b0, tag_a);
            for (i = 0; i < 10; i = i + 1) begin
                tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, tag_a);
            end
            expect_no_slot("const_low");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b0) mismatch("const_low.ov", 0, overflow_event);
            if (loss_count !== '0) mismatch("const_low.loss", 0, loss_count);

            reset_dut();
            rearm_dut(1'b1, tag_a);
            for (i = 0; i < 10; i = i + 1) begin
                tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_a);
            end
            expect_no_slot("const_high");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b0) mismatch("const_high.ov", 0, overflow_event);
            if (loss_count !== '0) mismatch("const_high.loss", 0, loss_count);

            if ((COUNT_W <= 4) || (COUNT_W == 16)) begin
                reset_dut();
                rearm_dut(1'b0, tag_a);
                tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_a);
                for (i = 0; i < maxv + 1; i = i + 1) begin
                    tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_a);
                end
                expect_no_slot("const_high_started");
                directed_checks = directed_checks + 1;
                if (overflow_event !== 1'b1) mismatch("const_high_started.ov", 1, overflow_event);
                if (loss_count !== 1) mismatch("const_high_started.loss", 1, loss_count);
                tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_a);
                directed_checks = directed_checks + 1;
                if (overflow_event !== 1'b0) mismatch("const_high_no_repeat", 0, overflow_event);
                if (loss_count !== 1) mismatch("const_high_no_repeat.loss", 1, loss_count);

                reset_dut();
                rearm_dut(1'b0, tag_a);
                tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_a);
                tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, tag_a);
                for (i = 0; i < maxv; i = i + 1) begin
                    tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, tag_a);
                end
                expect_no_slot("const_low_started");
                directed_checks = directed_checks + 1;
                if (overflow_event !== 1'b1) mismatch("const_low_started.ov", 1, overflow_event);
                if (loss_count !== 1) mismatch("const_low_started.loss", 1, loss_count);
                tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, tag_a);
                directed_checks = directed_checks + 1;
                if (overflow_event !== 1'b0) mismatch("const_low_no_repeat", 0, overflow_event);
                if (loss_count !== 1) mismatch("const_low_no_repeat.loss", 1, loss_count);
            end
            group_end("constant_levels");
        end
    endtask
    task automatic test_exhaustive();
        integer p;
        integer h;
        logic [TAG_W-1:0] tg;
        integer maxv;
        begin
            group_begin("exhaustive_pairs");
            maxv = max_int();
            tg = 1;
            for (p = 2; p <= maxv; p = p + 1) begin
                for (h = 1; h < p; h = h + 1) begin
                    cases = cases + 1;
                    reset_dut();
                    if (tg == 0) tg = 1;
                    rearm_dut(1'b0, tg);
                    run_frames(p, h, 4, tg, 1'b1);
                    tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, tg);
                    expect_no_slot("exh.consume");
                    directed_checks = directed_checks + 1;
                    if (loss_count !== '0) mismatch("exh.loss", 0, loss_count);
                    if (overflow_seen !== 1'b0) mismatch("exh.ovseen", 0, overflow_seen);
                    if (overrun_seen !== 1'b0) mismatch("exh.orseen", 0, overrun_seen);
                    tg = tg + 1;
                end
            end
            group_end("exhaustive_pairs");
        end
    endtask
    task automatic test_bounds_small();
        integer maxv;
        begin
            group_begin("bounds_small");
            maxv = max_int();

            // Exact MAX period, minimum high.
            reset_dut();
            rearm_dut(1'b0, 3);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 3);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 3);
            tick_n(maxv - 2, 1'b0, 1'b0, 3);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 3);
            expect_slot(maxv, 1, 3, "bound.max_h1");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b0) mismatch("bound.max_h1.ov", 0, overflow_event);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, 3);
            expect_no_slot("bound.max_h1.consume");

            // R1 at MAX+1 is invalid; the same rising starts the next R0.
            reset_dut();
            rearm_dut(1'b0, 4);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 4);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 4);
            tick_n(maxv - 1, 1'b0, 1'b0, 4);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 4);
            expect_no_slot("bound.maxp1.no_slot");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b1) mismatch("bound.maxp1.ov", 1, overflow_event);
            if (loss_count !== 1) mismatch("bound.maxp1.loss", 1, loss_count);
            if (overflow_seen !== 1'b1) mismatch("bound.maxp1.seen", 1, overflow_seen);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 4);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 4);
            expect_slot(2, 1, 4, "bound.maxp1.recovery");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, 4);
            expect_no_slot("bound.maxp1.consume");

            // High partial over-bound with a falling at MAX+1.
            reset_dut();
            rearm_dut(1'b0, 5);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 5);
            tick_n(maxv, 1'b1, 1'b0, 5);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 5);
            expect_no_slot("bound.highfall.no_slot");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b1) mismatch("bound.highfall.ov", 1, overflow_event);
            if (loss_count !== 1) mismatch("bound.highfall.loss", 1, loss_count);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 5);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 5);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 5);
            expect_slot(2, 1, 5, "bound.highfall.recovery");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, 5);
            expect_no_slot("bound.highfall.consume");
            // Constant high after a started R0 overflows exactly once.
            reset_dut();
            rearm_dut(1'b0, 6);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 6);
            tick_n(maxv + 1, 1'b1, 1'b0, 6);
            expect_no_slot("bound.consthigh.no_slot");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b1) mismatch("bound.consthigh.ov", 1, overflow_event);
            if (loss_count !== 1) mismatch("bound.consthigh.loss", 1, loss_count);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 6);
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b0) mismatch("bound.consthigh.repeat", 0, overflow_event);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 6);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 6);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 6);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 6);
            expect_slot(2, 1, 6, "bound.consthigh.recovery");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, 6);
            expect_no_slot("bound.consthigh.consume");

            // Constant low after F0 overflows exactly once.
            reset_dut();
            rearm_dut(1'b0, 7);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 7);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 7);
            tick_n(maxv, 1'b0, 1'b0, 7);
            expect_no_slot("bound.constlow.no_slot");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b1) mismatch("bound.constlow.ov", 1, overflow_event);
            if (loss_count !== 1) mismatch("bound.constlow.loss", 1, loss_count);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 7);
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b0) mismatch("bound.constlow.repeat", 0, overflow_event);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 7);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 7);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 7);
            expect_slot(2, 1, 7, "bound.constlow.recovery");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, 7);
            expect_no_slot("bound.constlow.consume");

            // Maximum high for an exact MAX period.
            reset_dut();
            rearm_dut(1'b0, 8);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 8);
            tick_n(maxv - 2, 1'b1, 1'b0, 8);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, 8);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, 8);
            expect_slot(maxv, maxv - 1, 8, "bound.max_hmax");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b0) mismatch("bound.max_hmax.ov", 0, overflow_event);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, 8);
            expect_no_slot("bound.max_hmax.consume");

            group_end("bounds_small");
        end
    endtask
    task automatic test_loss_saturation();
        integer p;
        integer h;
        integer i;
        integer maxv;
        logic [TAG_W-1:0] tag_a;
        begin
            group_begin("loss_saturation");
            p = common_p();
            h = common_h();
            maxv = max_int();
            tag_a = 91;

            reset_dut();
            rearm_dut(1'b0, tag_a);
            run_frames(p, h, 1, tag_a, 1'b0);
            expect_slot(p, h, tag_a, "sat.fill");
            for (i = 0; i < (2 * maxv); i = i + 1) begin
                tick_n(h - 1, 1'b1, 1'b0, tag_a);
                tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, tag_a);
                tick_n(p - h - 1, 1'b0, 1'b0, tag_a);
                tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_a);
                directed_checks = directed_checks + 1;
                if (overrun_event !== 1'b1) mismatch("sat.or_pulse", 1, overrun_event);
                if (loss_count !== ((i + 1 > maxv) ? maxv : (i + 1))) begin
                    mismatch("sat.or_loss", ((i + 1 > maxv) ? maxv : (i + 1)), loss_count);
                end
            end
            expect_slot(p, h, tag_a, "sat.keep");
            directed_checks = directed_checks + 1;
            if (overrun_seen !== 1'b1) mismatch("sat.orseen", 1, overrun_seen);
            if (loss_count !== maxv) mismatch("sat.max", maxv, loss_count);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, tag_a);
            expect_no_slot("sat.consume");

            reset_dut();
            rearm_dut(1'b0, tag_a);
            for (i = 0; i < (maxv + 2); i = i + 1) begin
                if (i > 0) tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, tag_a);
                tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, tag_a);
                tick_n(maxv + 1, 1'b1, 1'b0, tag_a);
                directed_checks = directed_checks + 1;
                if (overflow_event !== 1'b1) mismatch("sat.ov_pulse", 1, overflow_event);
                if (loss_count !== ((i + 1 > maxv) ? maxv : (i + 1))) begin
                    mismatch("sat.ov_loss", ((i + 1 > maxv) ? maxv : (i + 1)), loss_count);
                end
            end
            directed_checks = directed_checks + 1;
            if (overflow_seen !== 1'b1) mismatch("sat.ovseen", 1, overflow_seen);
            if (loss_count !== maxv) mismatch("sat.ovmax", maxv, loss_count);
            group_end("loss_saturation");
        end
    endtask
    task automatic test_wide16();
        integer maxv;
        logic [TAG_W-1:0] t1;
        logic [TAG_W-1:0] t2;
        logic [TAG_W-1:0] t3;
        begin
            group_begin("wide16");
            maxv = max_int();
            t1 = 16'h8001;
            t2 = 16'h8002;
            t3 = 16'h8003;

            reset_dut();
            rearm_dut(1'b0, t1);
            run_frames(32768, 16384, 1, t1, 1'b1);
            expect_slot(32768, 16384, t1, "w16.p32768");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, t1);
            expect_no_slot("w16.p32768.consume");

            reset_dut();
            rearm_dut(1'b0, t2);
            run_frames(40000, 20000, 1, t2, 1'b1);
            expect_slot(40000, 20000, t2, "w16.p40000");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, t2);
            expect_no_slot("w16.p40000.consume");

            reset_dut();
            rearm_dut(1'b0, t3);
            run_frames(maxv, 1, 1, t3, 1'b1);
            expect_slot(maxv, 1, t3, "w16.max_h1");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, t3);
            expect_no_slot("w16.max_h1.consume");

            reset_dut();
            rearm_dut(1'b0, t1);
            run_frames(maxv, maxv - 1, 1, t1, 1'b1);
            expect_slot(maxv, maxv - 1, t1, "w16.max_hmax");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, t1);
            expect_no_slot("w16.max_hmax.consume");

            // Rising at MAX+1: overflow, then the new R0 completes period 2.
            reset_dut();
            rearm_dut(1'b0, t2);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, t2);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, t2);
            tick_n(maxv - 1, 1'b0, 1'b0, t2);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, t2);
            expect_no_slot("w16.maxp1.no_slot");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b1) mismatch("w16.maxp1.ov", 1, overflow_event);
            if (loss_count !== 1) mismatch("w16.maxp1.loss", 1, loss_count);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, t2);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, t2);
            expect_slot(2, 1, t2, "w16.maxp1.recovery");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, t2);
            expect_no_slot("w16.maxp1.consume");
            // Constant high after R0: one overflow at MAX+1, no repeat.
            reset_dut();
            rearm_dut(1'b0, t3);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, t3);
            tick_n(maxv + 1, 1'b1, 1'b0, t3);
            expect_no_slot("w16.consthigh.no_slot");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b1) mismatch("w16.consthigh.ov", 1, overflow_event);
            if (loss_count !== 1) mismatch("w16.consthigh.loss", 1, loss_count);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, t3);
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b0) mismatch("w16.consthigh.repeat", 0, overflow_event);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, t3);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, t3);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, t3);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, t3);
            expect_slot(2, 1, t3, "w16.consthigh.recovery");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, t3);
            expect_no_slot("w16.consthigh.consume");

            // Constant low after F0: one overflow at MAX+1, no repeat.
            reset_dut();
            rearm_dut(1'b0, t1);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, t1);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, t1);
            tick_n(maxv - 1, 1'b0, 1'b0, t1);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, t1);
            expect_no_slot("w16.constlow.no_slot");
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b1) mismatch("w16.constlow.ov", 1, overflow_event);
            if (loss_count !== 1) mismatch("w16.constlow.loss", 1, loss_count);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, t1);
            directed_checks = directed_checks + 1;
            if (overflow_event !== 1'b0) mismatch("w16.constlow.repeat", 0, overflow_event);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, t1);
            tick(1'b0, 1'b0, 1'b0, 1'b0, 1'b0, t1);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b0, t1);
            expect_slot(2, 1, t1, "w16.constlow.recovery");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, t1);
            expect_no_slot("w16.constlow.consume");

            group_end("wide16");
        end
    endtask
    task automatic test_wide32();
        logic [TAG_W-1:0] t1;
        logic [TAG_W-1:0] t2;
        logic [TAG_W-1:0] t3;
        logic [TAG_W-1:0] t4;
        begin
            group_begin("wide32_bounded");
            if (TAG_W >= 64) begin
                t1 = 64'h0123456789ABCDEF;
                t2 = 64'hFEDCBA9876543210;
                t4 = 64'h0F0F0F0F0F0F0F0F;
            end else begin
                t1 = 32'h89ABCDEF;
                t2 = 32'h76543210;
                t4 = 32'h0F0F0F0F;
            end
            t3 = TB_TAG_ONES;

            reset_dut();
            rearm_dut(1'b0, t1);
            run_frames(32768, 16384, 1, t1, 1'b1);
            expect_slot(32768, 16384, t1, "w32.p32768");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, t1);
            expect_no_slot("w32.p32768.consume");

            reset_dut();
            rearm_dut(1'b0, t2);
            run_frames(65536, 32768, 1, t2, 1'b1);
            expect_slot(65536, 32768, t2, "w32.p65536");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, t2);
            expect_no_slot("w32.p65536.consume");

            reset_dut();
            rearm_dut(1'b0, t3);
            run_frames(100000, 99999, 1, t3, 1'b1);
            expect_slot(100000, 99999, t3, "w32.p100000");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, t3);
            expect_no_slot("w32.p100000.consume");

            reset_dut();
            rearm_dut(1'b0, t4);
            run_frames(200000, 1, 1, t4, 1'b1);
            expect_slot(200000, 1, t4, "w32.p200000");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, t4);
            expect_no_slot("w32.p200000.consume");

            // Deliberately no 2^32-1 period and no 2^32 overflow observation.
            group_end("wide32_bounded");
        end
    endtask

    task automatic test_smoke_wide();
        logic [TAG_W-1:0] t1;
        begin
            group_begin("smoke_wide");
            t1 = 17;
            reset_dut();
            rearm_dut(1'b0, t1);
            run_frames(17, 9, 2, t1, 1'b1);
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, t1);
            expect_no_slot("smoke.p17.consume");

            reset_dut();
            rearm_dut(1'b0, TB_TAG_ZERO);
            run_frames(1000, 999, 1, TB_TAG_ZERO, 1'b1);
            expect_slot(1000, 999, TB_TAG_ZERO, "smoke.p1000");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, TB_TAG_ZERO);
            expect_no_slot("smoke.p1000.consume");

            reset_dut();
            rearm_dut(1'b0, TB_TAG_ONES);
            run_frames(17, 1, 1, TB_TAG_ONES, 1'b1);
            expect_slot(17, 1, TB_TAG_ONES, "smoke.tag_ones");
            tick(1'b0, 1'b0, 1'b0, 1'b1, 1'b1, TB_TAG_ONES);
            expect_no_slot("smoke.tag_ones.consume");
            group_end("smoke_wide");
        end
    endtask
    task automatic test_random(input integer n);
        integer i;
        logic [31:0] rng;
        logic lvl;
        logic rdy;
        logic ra;
        logic st;
        logic rs;
        logic [TAG_W-1:0] tg;
        begin
            group_begin("random_schedule");
            rng = seed;
            if (rng == 0) rng = 32'h1;
            reset_dut();
            rearm_dut(1'b0, TB_TAG_ZERO);
            for (i = 0; i < n; i = i + 1) begin
                rng = lfsr_next(rng);
                lvl = rng[0];
                rdy = rng[1];
                ra = (rng[7:0] == 8'h01);
                st = (rng[9:0] == 10'h002);
                rs = (rng[11:0] == 12'h004);
                if (TAG_W >= 64) begin
                    tg = {rng, lfsr_next(rng)};
                end else begin
                    tg = rng[TAG_W-1:0];
                end
                tick(rs, st, ra, lvl, rdy, tg);
                random_cycles = random_cycles + 1;
            end
            $display("RANDOM_DONE cycles=%0d seed=%0d", n, seed);
            group_end("random_schedule");
        end
    endtask

    task automatic run_all();
        begin
            $display("TB_BEGIN COUNT_W=%0d TAG_W=%0d SEED=%0d SMOKE=%0d MAX=%0h",
                     COUNT_W, TAG_W, seed, smoke, TB_MAX);
            test_reset_unarmed();
            test_rearm_phases();
            test_held_rearm();
            test_tag_behavior();
            test_abort_stages();
            test_queue_backpressure();
            test_same_edge_swap();
            test_consume_no_candidate();
            test_flush_discard();
            test_constant_levels();

            if (smoke != 0) begin
                if (COUNT_W <= 4) begin
                    test_exhaustive();
                    test_bounds_small();
                end else begin
                    test_smoke_wide();
                end
            end else begin
                if (COUNT_W <= 4) begin
                    test_exhaustive();
                    test_bounds_small();
                    test_loss_saturation();
                end else if (COUNT_W == 16) begin
                    test_wide16();
                end else if (COUNT_W == 32) begin
                    test_wide32();
                end else begin
                    test_smoke_wide();
                end
            end

            if (COUNT_W <= 4) begin
                test_overflow_queue();
            end

            test_random((smoke != 0) ? 5000 : 20000);
        end
    endtask

    task automatic finish_report();
        begin
            if (runlog_en) begin
                $fdisplay(runlog_fd,
                    "E cycles=%0d groups=%0d cases=%0d cycle_assertions=%0d directed_checks=%0d records_checked=%0d records_generated=%0d handshakes=%0d overflow_events=%0d overrun_events=%0d mismatches=%0d random_cycles=%0d",
                    cycles, groups, cases, cycle_assertions, directed_checks,
                    records_checked, records_generated, handshakes,
                    overflow_events, overrun_events, mismatches, random_cycles);
                $fclose(runlog_fd);
            end
            $display("TB_STATS COUNT_W=%0d TAG_W=%0d groups=%0d cases=%0d cycles=%0d cycle_assertions=%0d directed_checks=%0d records_checked=%0d records_generated=%0d handshakes=%0d overflow_events=%0d overrun_events=%0d mismatches=%0d random_cycles=%0d",
                     COUNT_W, TAG_W, groups, cases, cycles, cycle_assertions,
                     directed_checks, records_checked, records_generated,
                     handshakes, overflow_events, overrun_events, mismatches,
                     random_cycles);
            if (mismatches == 0) begin
                $display("TB_PASS");
            end else begin
                $display("TB_FAIL mismatches=%0d", mismatches);
            end
            $finish;
        end
    endtask
    initial begin
        rst          = 1'b0;
        stop         = 1'b0;
        rearm        = 1'b0;
        sample_level = 1'b0;
        window_tag   = TB_TAG_ZERO;
        out_ready    = 1'b0;

        cycles           = 0;
        cycle_assertions = 0;
        directed_checks  = 0;
        records_checked  = 0;
        records_generated = 0;
        handshakes       = 0;
        overflow_events  = 0;
        overrun_events   = 0;
        mismatches       = 0;
        groups           = 0;
        cases            = 0;
        random_cycles    = 0;

        prev_out_valid = 1'b0;
        prev_period    = '0;
        prev_high      = '0;
        prev_tag       = TB_TAG_ZERO;
        prev_ready     = 1'b0;
        prev_abort     = 1'b0;
        prev_checked   = 1'b0;

        last_logged = 1'b0;
        last_rst    = 1'b0;
        last_stop   = 1'b0;
        last_rearm  = 1'b0;
        last_level  = 1'b0;
        last_ready  = 1'b0;
        last_tag    = TB_TAG_ZERO;

        runlog_en = 1'b0;
        runlog_fd = 0;
        if (!$value$plusargs("SEED=%d", seed)) seed = 20261020;
        if (!$value$plusargs("SMOKE=%d", smoke)) smoke = 0;
        if ($value$plusargs("RUNLOG=%s", runlog_path)) begin
            runlog_fd = $fopen(runlog_path, "w");
            if (runlog_fd == 0) begin
                $display("TB_FAIL cannot_open_runlog %s", runlog_path);
                $finish;
            end
            runlog_en = 1'b1;
            $fdisplay(runlog_fd,
                      "TB_BEGIN COUNT_W=%0d TAG_W=%0d SEED=%0d SMOKE=%0d MAX=%0h",
                      COUNT_W, TAG_W, seed, smoke, TB_MAX);
        end

        run_all();
        finish_report();
    end

endmodule