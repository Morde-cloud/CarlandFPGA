// tb_pwm_coherent_capture - authored self-checking public-port stimulus.
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
// All stimulus is an independently specified sampled-level schedule. The
// checker uses absolute local-window indices and records, never DUT internal
// signals, hierarchical forces, generator settings or a sampled seed argument.
// No public ABI, pin, clock, physical-frequency, freshness or motion claim is
// made by this simulation.

`timescale 1ns/1ps

module tb_pwm_coherent_capture #(
    parameter integer COUNT_W   = 32,
    parameter integer WITNESS_W = 64,
    parameter integer TAG_W     = 32,
    parameter integer TEST_GROUP= 0
);

    localparam logic [COUNT_W-1:0]   CMAX     = '1;
    localparam logic [WITNESS_W-1:0] TMAX     = '1;
    localparam logic [TAG_W-1:0]     TAG_ZERO = '0;
    localparam logic [TAG_W-1:0]     TAG_ONES = '1;

    logic                 clk;
    logic                 rst;
    logic                 stop;
    logic                 rearm;
    logic [2:0]           sample_levels;
    logic [TAG_W-1:0]     window_tag;
    logic                 out_ready;

    logic                 armed;
    logic                 out_valid;
    logic [COUNT_W-1:0]   out_period;
    logic [COUNT_W-1:0]   out_high0;
    logic [COUNT_W-1:0]   out_high1;
    logic [COUNT_W-1:0]   out_high2;
    logic [WITNESS_W-1:0] out_start;
    logic [WITNESS_W-1:0] out_end;
    logic [TAG_W-1:0]     out_tag;
    logic                 incoherent_event;
    logic                 period_overflow_event;
    logic                 witness_overflow_event;
    logic                 overrun_event;
    logic                 incoherent_seen;
    logic                 period_overflow_seen;
    logic                 witness_overflow_seen;
    logic                 overrun_seen;
    logic [COUNT_W-1:0]   fault_count;

    integer groups;
    integer cases;
    integer samples;
    integer assertions;
    integer mismatches;
    integer records;
    integer fault_events;
    integer random_state;
    integer group_cases_start;
    integer group_samples_start;
    integer group_assertions_start;
    integer group_mismatches_start;
    integer group_records_start;
    integer group_fault_events_start;

    deepeye_pwm_coherent_capture #(
        .COUNT_W(COUNT_W),
        .WITNESS_W(WITNESS_W),
        .TAG_W(TAG_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .stop(stop),
        .rearm(rearm),
        .sample_levels(sample_levels),
        .window_tag(window_tag),
        .out_ready(out_ready),
        .armed(armed),
        .out_valid(out_valid),
        .out_period(out_period),
        .out_high0(out_high0),
        .out_high1(out_high1),
        .out_high2(out_high2),
        .out_start(out_start),
        .out_end(out_end),
        .out_tag(out_tag),
        .incoherent_event(incoherent_event),
        .period_overflow_event(period_overflow_event),
        .witness_overflow_event(witness_overflow_event),
        .overrun_event(overrun_event),
        .incoherent_seen(incoherent_seen),
        .period_overflow_seen(period_overflow_seen),
        .witness_overflow_seen(witness_overflow_seen),
        .overrun_seen(overrun_seen),
        .fault_count(fault_count)
    );

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        rst           = 1'b1;
        stop          = 1'b0;
        rearm         = 1'b0;
        sample_levels = 3'b000;
        window_tag    = TAG_ZERO;
        out_ready     = 1'b0;
        groups        = 0;
        cases         = 0;
        samples       = 0;
        assertions    = 0;
        mismatches    = 0;
        records       = 0;
        fault_events  = 0;
        random_state  = 32'h1ACE_B00C;
        group_cases_start       = 0;
        group_samples_start     = 0;
        group_assertions_start  = 0;
        group_mismatches_start  = 0;
        group_records_start     = 0;
        group_fault_events_start= 0;
    end

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

    task automatic check_events(input logic [3:0] expected,
                                input string label);
        logic [3:0] observed;
        begin
            observed = {overrun_event, witness_overflow_event,
                        period_overflow_event, incoherent_event};
            check64({60'b0, observed}, {60'b0, expected}, label);
        end
    endtask

    task automatic check_seen(input logic [3:0] expected,
                              input string label);
        logic [3:0] observed;
        begin
            observed = {overrun_seen, witness_overflow_seen,
                        period_overflow_seen, incoherent_seen};
            check64({60'b0, observed}, {60'b0, expected}, label);
        end
    endtask

    task automatic check_zero_payload(input string label);
        begin
            check64(out_valid, 1'b0, label);
            check64(out_period, 64'b0, label);
            check64(out_high0, 64'b0, label);
            check64(out_high1, 64'b0, label);
            check64(out_high2, 64'b0, label);
            check64(out_start, 64'b0, label);
            check64(out_end, 64'b0, label);
            check64(out_tag, 64'b0, label);
        end
    endtask

    task automatic check_clean(input string label);
        begin
            check64(armed, 1'b0, label);
            check_zero_payload(label);
            check_events(4'b0000, label);
            check_seen(4'b0000, label);
            check64(fault_count, 64'b0, label);
        end
    endtask

    task automatic check_armed_clean(input string label);
        begin
            check64(armed, 1'b1, label);
            check_zero_payload(label);
            check_events(4'b0000, label);
            check_seen(4'b0000, label);
            check64(fault_count, 64'b0, label);
        end
    endtask

    task automatic check_payload_values(input integer period,
                                        input integer h0,
                                        input integer h1,
                                        input integer h2,
                                        input integer start_index,
                                        input integer end_index,
                                        input logic [TAG_W-1:0] expected_tag,
                                        input string label);
        begin
            check64(out_valid, 1'b1, label);
            check64(out_period, period, label);
            check64(out_high0, h0, label);
            check64(out_high1, h1, label);
            check64(out_high2, h2, label);
            check64(out_start, start_index, label);
            check64(out_end, end_index, label);
            check64(out_tag, expected_tag, label);
        end
    endtask

    task automatic check_record_fields(input integer period,
                                       input integer h0,
                                       input integer h1,
                                       input integer h2,
                                       input integer start_index,
                                       input integer end_index,
                                       input logic [TAG_W-1:0] expected_tag,
                                       input string label);
        begin
            check64(armed, 1'b1, label);
            check_payload_values(period, h0, h1, h2, start_index, end_index,
                                 expected_tag, label);
            check_events(4'b0000, label);
        end
    endtask

    task automatic check_record(input integer period,
                                input integer h0,
                                input integer h1,
                                input integer h2,
                                input integer start_index,
                                input integer end_index,
                                input logic [TAG_W-1:0] expected_tag,
                                input string label);
        begin
            records = records + 1;
            check_record_fields(period, h0, h1, h2, start_index, end_index,
                                expected_tag, label);
        end
    endtask

    task automatic tick(input logic rst_i,
                        input logic stop_i,
                        input logic rearm_i,
                        input logic [2:0] levels_i,
                        input logic [TAG_W-1:0] tag_i,
                        input logic ready_i);
        begin
            @(negedge clk);
            rst           = rst_i;
            stop          = stop_i;
            rearm         = rearm_i;
            sample_levels = levels_i;
            window_tag    = tag_i;
            out_ready     = ready_i;
            @(posedge clk);
            #1;
            samples = samples + 1;
            if (incoherent_event)       fault_events = fault_events + 1;
            if (period_overflow_event)  fault_events = fault_events + 1;
            if (witness_overflow_event) fault_events = fault_events + 1;
            if (overrun_event)          fault_events = fault_events + 1;
        end
    endtask

    function automatic integer rand_mod(input integer limit);
        integer temp;
        begin
            random_state = ((random_state * 1103515245) + 12345) & 32'h7FFFFFFF;
            temp = (random_state >> 8) & 32'h7FFF;
            if (limit <= 0) rand_mod = 0;
            else rand_mod = temp % limit;
        end
    endfunction

    task automatic group_begin(input string name);
        begin
            groups = groups + 1;
            group_cases_start        = cases;
            group_samples_start      = samples;
            group_assertions_start   = assertions;
            group_mismatches_start   = mismatches;
            group_records_start      = records;
            group_fault_events_start = fault_events;
            $display("GROUP_BEGIN %s", name);
        end
    endtask

    task automatic group_end(input string name);
        begin
            $display("GROUP_END %s cases=%0d samples=%0d assertions=%0d mismatches=%0d records=%0d fault_events=%0d",
                     name,
                     cases - group_cases_start,
                     samples - group_samples_start,
                     assertions - group_assertions_start,
                     mismatches - group_mismatches_start,
                     records - group_records_start,
                     fault_events - group_fault_events_start);
        end
    endtask

    task automatic reset_dut;
        begin
            tick(1'b1, 1'b0, 1'b0, 3'b000, TAG_ZERO, 1'b0);
            tick(1'b1, 1'b0, 1'b0, 3'b111, TAG_ONES, 1'b1);
            tick(1'b0, 1'b0, 1'b0, 3'b000, TAG_ZERO, 1'b0);
            check_clean("after_reset");
        end
    endtask

    task automatic rearm_dut(input logic [2:0] baseline,
                             input logic [TAG_W-1:0] tag_i);
        begin
            tick(1'b0, 1'b0, 1'b1, baseline, tag_i, 1'b0);
            check_armed_clean("after_rearm");
        end
    endtask

    task automatic drive_clean_finish(input integer period,
                                      input integer h0,
                                      input integer h1,
                                      input integer h2,
                                      input logic [TAG_W-1:0] tag_i,
                                      input integer start_index,
                                      input logic ready_end,
                                      input string label);
        integer e;
        logic [2:0] levels_now;
        begin
            for (e = 1; e < period; e = e + 1) begin
                levels_now[0] = (e >= h0) ? 1'b0 : 1'b1;
                levels_now[1] = (e >= h1) ? 1'b0 : 1'b1;
                levels_now[2] = (e >= h2) ? 1'b0 : 1'b1;
                tick(1'b0, 1'b0, 1'b0, levels_now, tag_i, 1'b0);
                check64(armed, 1'b1, label);
                check64(out_valid, 1'b0, label);
                check_events(4'b0000, label);
                check64(fault_count, 64'b0, label);
            end
            tick(1'b0, 1'b0, 1'b0, 3'b111, tag_i, ready_end);
            check_record(period, h0, h1, h2, start_index,
                         start_index + period, tag_i, label);
        end
    endtask

    task automatic run_tuple(input integer period,
                             input integer h0,
                             input integer h1,
                             input integer h2,
                             input logic [TAG_W-1:0] tag_i,
                             input string label);
        begin
            cases = cases + 1;
            rearm_dut(3'b000, tag_i);
            tick(1'b0, 1'b0, 1'b0, 3'b111, tag_i, 1'b0);
            check64(armed, 1'b1, label);
            check64(out_valid, 1'b0, label);
            check_events(4'b0000, label);
            drive_clean_finish(period, h0, h1, h2, tag_i, 1, 1'b0, label);
            tick(1'b0, 1'b0, 1'b0, 3'b000, tag_i, 1'b1);
            check_zero_payload(label);
            check_events(4'b0000, label);
            check_seen(4'b0000, label);
            check64(fault_count, 64'b0, label);
        end
    endtask

    task automatic group_small_boundaries;
        begin
            group_begin("small_literal_period_and_witness");
            reset_dut;

            cases = cases + 1;
            rearm_dut(3'b000, 3'b001);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 3'b001, 1'b0);
            drive_clean_finish(3, 1, 2, 1, 3'b001, 1, 1'b0,
                               "literal_period3");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b001, 1'b1);
            check_zero_payload("literal_retire");
            check_events(4'b0000, "literal_retire.events");

            // COUNT_W2 CMAX=3: a genuine common rise on the CMAX+1 edge
            // pulses period_overflow and restarts the partial at that edge.
            cases = cases + 1;
            rearm_dut(3'b000, 3'b010);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 3'b010, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b010, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b010, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b010, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 3'b010, 1'b0);
            check_events(4'b0010, "period_overflow_restart.events");
            check_seen(4'b0010, "period_overflow_restart.seen");
            check64(armed, 1'b1, "period_overflow_restart.armed");
            check64(out_valid, 1'b0, "period_overflow_restart.valid");
            check64(fault_count, 64'd1, "period_overflow_restart.count");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b010, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 3'b010, 1'b0);
            check_record(2, 1, 1, 1, 5, 7, 3'b010,
                         "period_overflow_restart.record");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b010, 1'b1);
            check_zero_payload("period_overflow_restart.retire");

            // Without a common rise on the overflowing edge, the old partial
            // is abandoned and capture becomes idle but remains armed.
            cases = cases + 1;
            rearm_dut(3'b000, 3'b011);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 3'b011, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b011, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b011, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b011, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b011, 1'b0);
            check_events(4'b0010, "period_overflow_idle.events");
            check64(armed, 1'b1, "period_overflow_idle.armed");
            check64(out_valid, 1'b0, "period_overflow_idle.valid");
            check64(fault_count, 64'd1, "period_overflow_idle.count");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b011, 1'b0);
            check_events(4'b0000, "period_overflow_idle.next");

            // Witness exhaustion and count overflow coincide at the next
            // ordinary edge after start4/fall5/no closure through TMAX=7.
            cases = cases + 1;
            rearm_dut(3'b000, 3'b100);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b100, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b100, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b100, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 3'b100, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b100, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b100, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b100, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b100, 1'b0);
            check_events(4'b0100, "witness_count_priority.events");
            check_seen(4'b0100, "witness_count_priority.seen");
            check64(armed, 1'b0, "witness_count_priority.armed");
            check64(fault_count, 64'd1, "witness_count_priority.count");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 3'b100, 1'b0);
            check64(armed, 1'b0, "witness_count_priority.later_armed");
            check_events(4'b0000, "witness_count_priority.later_events");

            // Processing at t==TMAX is legal: a period-3 record closes there.
            cases = cases + 1;
            rearm_dut(3'b000, 3'b101);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b101, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b101, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b101, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 3'b101, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b101, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b101, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 3'b101, 1'b0);
            check_record(3, 1, 1, 1, 4, 7, 3'b101, "tmax_legal_record");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b101, 1'b1);
            check_events(4'b0100, "tmax_next_exhaustion.events");
            check64(armed, 1'b0, "tmax_next_exhaustion.armed");
            check_zero_payload("tmax_next_exhaustion.retire");
            group_end("small_literal_period_and_witness");
        end
    endtask

    task automatic group_exhaustive_width2;
        integer p;
        integer h0;
        integer h1;
        integer h2;
        logic [TAG_W-1:0] tag_i;
        begin
            group_begin("exhaustive_count_w2_legal_high_triples");
            reset_dut;
            for (p = 2; p <= CMAX; p = p + 1) begin
                for (h0 = 1; h0 < p; h0 = h0 + 1) begin
                    for (h1 = 1; h1 < p; h1 = h1 + 1) begin
                        for (h2 = 1; h2 < p; h2 = h2 + 1) begin
                            tag_i = ((p + h0 + h1 + h2) % 2 == 0) ? TAG_ZERO : TAG_ONES;
                            run_tuple(p, h0, h1, h2, tag_i, "exhaustive_w2");
                        end
                    end
                end
            end
            group_end("exhaustive_count_w2_legal_high_triples");
        end
    endtask

    task automatic group_fault_saturation;
        integer i;
        integer expected_count;
        begin
            group_begin("fault_count_saturation");
            reset_dut;
            rearm_dut(3'b000, 3'b001);
            for (i = 0; i < 5; i = i + 1) begin
                cases = cases + 1;
                tick(1'b0, 1'b0, 1'b0, 3'b001, 3'b001, 1'b0);
                expected_count = (i + 1 < 3) ? (i + 1) : 3;
                check_events(4'b0001, "saturation.events");
                check_seen(4'b0001, "saturation.seen");
                check64(fault_count, expected_count, "saturation.count");
                tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b001, 1'b0);
                check_events(4'b0000, "saturation.fall");
            end
            // With fault_count already saturated, a genuine period fault must
            // still pulse and set its sticky flag.
            cases = cases + 1;
            tick(1'b0, 1'b0, 1'b0, 3'b111, 3'b001, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b001, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b001, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b001, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 3'b001, 1'b0);
            check_events(4'b0010, "saturation_period.events");
            check_seen(4'b0011, "saturation_period.seen");
            check64(fault_count, 64'd3, "saturation_period.count");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 3'b001, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b001, 3'b001, 1'b0);
            check_events(4'b0001, "saturation_after_period.events");
            check_seen(4'b0011, "saturation_after_period.seen");
            check64(fault_count, 64'd3, "saturation_after_period.count");
            group_end("fault_count_saturation");
        end
    endtask

    task automatic group_count16_boundaries;
        integer e;
        logic [2:0] levels_now;
        begin
            group_begin("count_w16_full_period_boundaries");
            reset_dut;
            run_tuple(32768, 1, 16384, 32767, 16'h8000,
                      "period_bit15_cross");
            run_tuple(65535, 1, 32768, 65534, 16'hFFFF,
                      "period_cmax_65535");

            cases = cases + 1;
            reset_dut;
            rearm_dut(3'b000, 16'hA55A);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 16'hA55A, 1'b0);
            for (e = 1; e <= 65535; e = e + 1) begin
                levels_now[0] = (e >= 1) ? 1'b0 : 1'b1;
                levels_now[1] = (e >= 32768) ? 1'b0 : 1'b1;
                levels_now[2] = (e >= 65535) ? 1'b0 : 1'b1;
                tick(1'b0, 1'b0, 1'b0, levels_now, 16'hA55A, 1'b0);
                check64(armed, 1'b1, "period_overflow_65536");
                check64(out_valid, 1'b0, "period_overflow_65536");
                check_events(4'b0000, "period_overflow_65536");
                check64(fault_count, 64'd0, "period_overflow_65536");
            end
            tick(1'b0, 1'b0, 1'b0, 3'b111, 16'hA55A, 1'b0);
            check_events(4'b0010, "period_overflow_65536.events");
            check_seen(4'b0010, "period_overflow_65536.seen");
            check64(fault_count, 64'd1, "period_overflow_65536.count");
            check64(armed, 1'b1, "period_overflow_65536.armed");
            check64(out_valid, 1'b0, "period_overflow_65536.valid");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 16'hA55A, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 16'hA55A, 1'b0);
            check_record(2, 1, 1, 1, 65537, 65539, 16'hA55A,
                         "period_overflow_restart_65536");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 16'hA55A, 1'b1);
            check_zero_payload("period_overflow_65536.retire");
            group_end("count_w16_full_period_boundaries");
        end
    endtask

    task automatic group_width3_overflow;
        integer e;
        begin
            group_begin("count_w3_period_overflow");
            reset_dut;

            // CMAX=7 is legal when the common close occurs at elapsed 7.
            cases = cases + 1;
            rearm_dut(3'b000, 4'h1);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 4'h1, 1'b0);
            drive_clean_finish(7, 1, 1, 1, 4'h1, 1, 1'b0, "w3_cmax_legal");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 4'h1, 1'b1);
            check_zero_payload("w3_cmax_retire");
            check_events(4'b0000, "w3_cmax_retire.events");
            check_seen(4'b0000, "w3_cmax_retire.seen");
            check64(fault_count, 64'd0, "w3_cmax_retire.count");

            // CMAX+1 with a genuine common rising: overflow and restart at
            // the representable witness of that edge.
            cases = cases + 1;
            rearm_dut(3'b000, 4'h2);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 4'h2, 1'b0);
            for (e = 0; e < 7; e = e + 1) begin
                tick(1'b0, 1'b0, 1'b0, 3'b000, 4'h2, 1'b0);
            end
            tick(1'b0, 1'b0, 1'b0, 3'b111, 4'h2, 1'b0);
            check_events(4'b0010, "w3_period_overflow_restart.events");
            check_seen(4'b0010, "w3_period_overflow_restart.seen");
            check64(fault_count, 64'd1, "w3_period_overflow_restart.count");
            check64(armed, 1'b1, "w3_period_overflow_restart.armed");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 4'h2, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 4'h2, 1'b0);
            check_record(2, 1, 1, 1, 9, 11, 4'h2,
                         "w3_period_overflow_restart.record");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 4'h2, 1'b1);
            check_zero_payload("w3_period_overflow_restart.retire");

            // CMAX+1 without a common rising: abandon the partial but remain
            // armed and idle, with no stale lane splice.
            cases = cases + 1;
            rearm_dut(3'b000, 4'h3);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 4'h3, 1'b0);
            for (e = 0; e < 7; e = e + 1) begin
                tick(1'b0, 1'b0, 1'b0, 3'b000, 4'h3, 1'b0);
            end
            tick(1'b0, 1'b0, 1'b0, 3'b000, 4'h3, 1'b0);
            check_events(4'b0010, "w3_period_overflow_idle.events");
            check_seen(4'b0010, "w3_period_overflow_idle.seen");
            check64(fault_count, 64'd1, "w3_period_overflow_idle.count");
            check64(armed, 1'b1, "w3_period_overflow_idle.armed");
            check64(out_valid, 1'b0, "w3_period_overflow_idle.valid");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 4'h3, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 4'h3, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 4'h3, 1'b0);
            check_record(2, 1, 1, 1, 10, 12, 4'h3,
                         "w3_period_overflow_idle.record");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 4'h3, 1'b1);
            check_zero_payload("w3_period_overflow_idle.retire");
            group_end("count_w3_period_overflow");
        end
    endtask

    task automatic group_witness_w3_exhaustion;
        integer i;
        begin
            group_begin("witness_w3_namespace_exhaustion");
            reset_dut;

            // Processing at TMAX=7 is legal; the following armed edge emits
            // exactly one exhaustion, disarms, and leaves the queued record
            // transport-valid.
            cases = cases + 1;
            rearm_dut(3'b000, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b0, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b0, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b0, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b0, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b0, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b0, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b0, 1'b0);
            check_record(2, 1, 1, 1, 5, 7, 1'b0, "w3_tmax_record");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b0, 1'b0);
            check_events(4'b0100, "w3_exhaustion.events");
            check_seen(4'b0100, "w3_exhaustion.seen");
            check64(fault_count, 64'd1, "w3_exhaustion.count");
            check64(armed, 1'b0, "w3_exhaustion.armed");
            check_payload_values(2, 1, 1, 1, 5, 7, 1'b0,
                                 "w3_pending_transport");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b0, 1'b1);
            check_zero_payload("w3_unarmed_retire");
            check64(armed, 1'b0, "w3_unarmed_retire.armed");
            check_events(4'b0000, "w3_unarmed_retire.events");
            check_seen(4'b0100, "w3_unarmed_retire.seen");

            // A ready retirement may occur on the exhaustion edge itself.
            cases = cases + 1;
            reset_dut;
            rearm_dut(3'b000, 1'b1);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b1, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b1, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b1, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b1, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b1, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b1, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b1, 1'b0);
            check_record(2, 1, 1, 1, 5, 7, 1'b1, "w3_tmax_record_ready");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b1, 1'b1);
            check_events(4'b0100, "w3_exhaustion_retire.events");
            check_seen(4'b0100, "w3_exhaustion_retire.seen");
            check64(fault_count, 64'd1, "w3_exhaustion_retire.count");
            check64(armed, 1'b0, "w3_exhaustion_retire.armed");
            check_zero_payload("w3_exhaustion_retire.payload");

            // Idle namespace exhaustion also occurs once and requires a new
            // explicit rearm.
            cases = cases + 1;
            reset_dut;
            rearm_dut(3'b000, 1'b0);
            for (i = 0; i < 7; i = i + 1) begin
                tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b0, 1'b0);
            end
            check_events(4'b0000, "w3_idle_tmax.events");
            check64(armed, 1'b1, "w3_idle_tmax.armed");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b0, 1'b0);
            check_events(4'b0100, "w3_idle_exhaustion.events");
            check64(armed, 1'b0, "w3_idle_exhaustion.armed");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b0, 1'b0);
            check_events(4'b0000, "w3_idle_exhaustion_once.events");
            check64(armed, 1'b0, "w3_idle_exhaustion_once.armed");
            group_end("witness_w3_namespace_exhaustion");
        end
    endtask

    task automatic group_min_width;
        begin
            group_begin("count_w2_witness_w2_exhaustion");
            reset_dut;

            // The record closes legally at t=3=TMAX; the next ordinary armed
            // edge emits one exhaustion event and leaves an old stalled record
            // transport-valid while unarmed.
            cases = cases + 1;
            rearm_dut(3'b000, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b0, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b0, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b0, 1'b0);
            check_record(2, 1, 1, 1, 1, 3, 1'b0, "witness_w2_record");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b0, 1'b0);
            check_events(4'b0100, "witness_w2_exhaustion.events");
            check_seen(4'b0100, "witness_w2_exhaustion.seen");
            check64(fault_count, 64'd1, "witness_w2_exhaustion.count");
            check64(armed, 1'b0, "witness_w2_exhaustion.armed");
            check_payload_values(2, 1, 1, 1, 1, 3, 1'b0,
                                 "witness_w2_pending_transport");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b0, 1'b1);
            check_zero_payload("witness_w2_unarmed_retire");
            check64(armed, 1'b0, "witness_w2_unarmed_armed");
            check_events(4'b0000, "witness_w2_unarmed.events");
            check_seen(4'b0100, "witness_w2_unarmed.seen");

            // Exhaustion also occurs from idle and occurs only once without
            // an explicit rearm.
            cases = cases + 1;
            reset_dut;
            rearm_dut(3'b000, 1'b1);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b1, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b1, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b1, 1'b0);
            check_events(4'b0000, "idle_tmax_legal.events");
            check64(armed, 1'b1, "idle_tmax_legal.armed");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 1'b1, 1'b0);
            check_events(4'b0100, "idle_exhaustion.events");
            check64(armed, 1'b0, "idle_exhaustion.armed");
            check64(out_valid, 1'b0, "idle_exhaustion.valid");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 1'b1, 1'b0);
            check_events(4'b0000, "idle_exhaustion_once.events");
            check64(armed, 1'b0, "idle_exhaustion_once.armed");
            group_end("count_w2_witness_w2_exhaustion");
        end
    endtask

    task automatic group_max_width;
        begin
            group_begin("count_w32_witness_w64_tag_w64");
            reset_dut;
            run_tuple(3, 1, 2, 1, TAG_ZERO, "max_width_zero_tag");
            run_tuple(3, 2, 1, 2, TAG_ONES, "max_width_full_tag");
            run_tuple(3, 1, 1, 2, 64'hA5A5_5A5A_0123_4567,
                      "max_width_pattern_tag");
            group_end("count_w32_witness_w64_tag_w64");
        end
    endtask

    task automatic group_default_smoke;
        begin
            group_begin("default_parameter_smoke");
            reset_dut;
            run_tuple(2, 1, 1, 1, TAG_ZERO, "default_smoke");
            group_end("default_parameter_smoke");
        end
    endtask

    task automatic group_random;
        integer c;
        integer i;
        integer e;
        integer idle_edges;
        integer period;
        integer h0;
        integer h1;
        integer h2;
        integer start_index;
        logic [2:0] levels_now;
        logic [TAG_W-1:0] tag_i;
        logic [TAG_W-1:0] tag_now;
        logic ready_now;
        begin
            group_begin("deterministic_random_three_lane_schedule");
            reset_dut;
            for (c = 0; c < 128; c = c + 1) begin
                cases = cases + 1;
                if (rand_mod(2) == 0) begin
                    reset_dut;
                end else begin
                    tick(1'b0, 1'b1, 1'b0, 3'b000, TAG_ZERO, 1'b0);
                    check_clean("random_stop_control");
                end
                tag_i = random_state[15:0] ^ (c * 16'h1234);
                rearm_dut(3'b000, tag_i);
                idle_edges = 1 + rand_mod(5);
                for (i = 0; i < idle_edges; i = i + 1) begin
                    tag_now = tag_i ^ (i * 16'h0101);
                    tick(1'b0, 1'b0, 1'b0, 3'b000, tag_now,
                         rand_mod(2));
                    check64(armed, 1'b1, "random_idle.armed");
                    check64(out_valid, 1'b0, "random_idle.valid");
                    check_events(4'b0000, "random_idle.events");
                    check64(fault_count, 64'd0, "random_idle.count");
                end
                start_index = idle_edges + 1;
                tag_now = tag_i ^ 16'h5555;
                tick(1'b0, 1'b0, 1'b0, 3'b111, tag_now, rand_mod(2));
                check64(armed, 1'b1, "random_start.armed");
                check64(out_valid, 1'b0, "random_start.valid");
                check_events(4'b0000, "random_start.events");
                period = 2 + rand_mod(18);
                h0 = 1 + rand_mod(period - 1);
                h1 = 1 + rand_mod(period - 1);
                h2 = 1 + rand_mod(period - 1);
                for (e = 1; e < period; e = e + 1) begin
                    levels_now[0] = (e >= h0) ? 1'b0 : 1'b1;
                    levels_now[1] = (e >= h1) ? 1'b0 : 1'b1;
                    levels_now[2] = (e >= h2) ? 1'b0 : 1'b1;
                    tag_now = tag_i ^ (e * 16'h1F1F);
                    ready_now = rand_mod(2);
                    tick(1'b0, 1'b0, 1'b0, levels_now, tag_now, ready_now);
                    check64(armed, 1'b1, "random_interval.armed");
                    check64(out_valid, 1'b0, "random_interval.valid");
                    check_events(4'b0000, "random_interval.events");
                    check64(fault_count, 64'd0, "random_interval.count");
                end
                tag_now = tag_i ^ 16'hAAAA;
                tick(1'b0, 1'b0, 1'b0, 3'b111, tag_now, rand_mod(2));
                check_record(period, h0, h1, h2, start_index,
                             start_index + period, tag_i, "random_record");
                tick(1'b0, 1'b0, 1'b0, 3'b000, tag_i, 1'b1);
                check_zero_payload("random_retire");
                check_seen(4'b0000, "random_retire.seen");
                check64(fault_count, 64'd0, "random_retire.count");
            end
            group_end("deterministic_random_three_lane_schedule");
        end
    endtask

    task automatic group_mutant_relaxed;
        begin
            group_begin("mutant_relaxed_common_start_public_ports");
            reset_dut;
            cases = cases + 1;
            rearm_dut(3'b000, 8'hB1);
            tick(1'b0, 1'b0, 1'b0, 3'b001, 8'hB1, 1'b0);
            check_events(4'b0001, "mutant_relaxed_subset_start.events");
            check64(out_valid, 1'b0, "mutant_relaxed_subset_start.valid");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'hB1, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'hB1, 1'b0);
            check64(out_valid, 1'b0, "mutant_relaxed_no_record.valid");
            check64(out_period, 64'b0, "mutant_relaxed_no_record.period");
            group_end("mutant_relaxed_common_start_public_ports");
        end
    endtask

    task automatic group_mutant_mixed;
        begin
            group_begin("mutant_mixed_frame_public_ports");
            reset_dut;
            cases = cases + 1;
            rearm_dut(3'b000, 8'hB2);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'hB2, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'hB2, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b001, 8'hB2, 1'b0);
            check_events(4'b0001, "mutant_mixed_abort.events");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'hB2, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'hB2, 1'b0);
            check64(out_valid, 1'b0, "mutant_mixed_no_record.valid");
            check64(out_period, 64'b0, "mutant_mixed_no_record.period");
            group_end("mutant_mixed_frame_public_ports");
        end
    endtask

    task automatic group_exhaustive_width3;
        integer p;
        integer h0;
        integer h1;
        integer h2;
        logic [TAG_W-1:0] tag_i;
        begin
            group_begin("exhaustive_count_w3_legal_high_triples");
            reset_dut;
            for (p = 2; p <= CMAX; p = p + 1) begin
                for (h0 = 1; h0 < p; h0 = h0 + 1) begin
                    for (h1 = 1; h1 < p; h1 = h1 + 1) begin
                        for (h2 = 1; h2 < p; h2 = h2 + 1) begin
                            tag_i = (p + h0 + h1 + h2);
                            run_tuple(p, h0, h1, h2, tag_i, "exhaustive_w3");
                        end
                    end
                end
            end
            group_end("exhaustive_count_w3_legal_high_triples");
        end
    endtask

    task automatic group_main_controls;
        integer i;
        begin
            group_begin("controls_tags_and_abort_phases");
            reset_dut;

            cases = cases + 1;
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h11, 1'b1);
            check_clean("unarmed_common_rise");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h22, 1'b0);
            check_clean("unarmed_fall");

            // High baseline is ignored until a fresh common rising; the first
            // representable start is after rearm, not on the rearm edge.
            cases = cases + 1;
            rearm_dut(3'b111, 8'h31);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h32, 1'b0);
            check64(armed, 1'b1, "high_baseline_falls");
            check_events(4'b0000, "high_baseline_falls.events");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h33, 1'b0);
            check64(armed, 1'b1, "high_baseline_start");
            check_events(4'b0000, "high_baseline_start.events");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h34, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h35, 1'b0);
            check_record(2, 1, 1, 1, 2, 4, 8'h31, "high_baseline_record");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h31, 1'b1);
            check_zero_payload("high_baseline_retire");

            // Tag changes without rearm are opaque and must not relabel the
            // latched window.
            cases = cases + 1;
            rearm_dut(3'b000, 8'h5A);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'hA5, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h00, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'hFF, 1'b0);
            check_record(2, 1, 1, 1, 1, 3, 8'h5A, "tag_change_ignored");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h5A, 1'b1);
            check_zero_payload("tag_change_retire");

            // Held rearm creates a fresh empty baseline on every edge.
            cases = cases + 1;
            for (i = 0; i < 3; i = i + 1) begin
                tick(1'b0, 1'b0, 1'b1, 3'b000, 8'h70 + i, 1'b0);
                check_armed_clean("held_rearm");
            end
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h77, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h77, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h77, 1'b0);
            check_record(2, 1, 1, 1, 1, 3, 8'h72, "held_rearm_record");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h77, 1'b1);
            check_zero_payload("held_rearm_retire");

            // Reset after R0 and STOP after a first fall clear every partial
            // field, queue, diagnostic and handshake.
            cases = cases + 1;
            rearm_dut(3'b000, 8'h81);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h81, 1'b0);
            check64(armed, 1'b1, "reset_after_r0.armed");
            tick(1'b1, 1'b0, 1'b0, 3'b000, 8'h81, 1'b1);
            check_clean("reset_after_r0");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h81, 1'b0);
            check_clean("reset_deassert_no_arm");

            cases = cases + 1;
            rearm_dut(3'b000, 8'h82);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h82, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h82, 1'b0);
            check64(armed, 1'b1, "stop_after_fall.armed");
            tick(1'b0, 1'b1, 1'b0, 3'b111, 8'h82, 1'b1);
            check_clean("stop_after_fall");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h82, 1'b0);
            check_clean("stop_deassert_no_arm");

            // RST/STOP outrank rearm even when all three are asserted.
            cases = cases + 1;
            tick(1'b1, 1'b1, 1'b1, 3'b111, 8'h83, 1'b1);
            check_clean("reset_stop_rearm_priority");
            tick(1'b0, 1'b1, 1'b1, 3'b111, 8'h83, 1'b1);
            check_clean("stop_rearm_priority");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h83, 1'b0);
            check_clean("priority_deassert");

            // Held STOP repeatedly clears a newly armed partial.
            cases = cases + 1;
            rearm_dut(3'b000, 8'h84);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h84, 1'b0);
            for (i = 0; i < 3; i = i + 1) begin
                tick(1'b0, 1'b1, 1'b0, 3'b000, 8'h84, 1'b1);
                check_clean("held_stop");
            end
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h84, 1'b0);
            check_clean("held_stop_deassert");

            // A rearm clears sticky diagnostics and any queued record.
            cases = cases + 1;
            rearm_dut(3'b000, 8'h91);
            tick(1'b0, 1'b0, 1'b0, 3'b001, 8'h91, 1'b0);
            check_events(4'b0001, "diag_clear_seed.events");
            check_seen(4'b0001, "diag_clear_seed.seen");
            check64(fault_count, 64'd1, "diag_clear_seed.count");
            rearm_dut(3'b000, 8'h92);
            check_armed_clean("diag_cleared_by_rearm");

            // Rearm in the middle of a partial after first falls clears the
            // old start/counts; the new interval starts strictly after rearm.
            cases = cases + 1;
            rearm_dut(3'b000, 8'h86);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h86, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h86, 1'b0);
            check64(armed, 1'b1, "rearm_mid_partial.armed");
            rearm_dut(3'b000, 8'h87);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h87, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h87, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h87, 1'b0);
            check_record(2, 1, 1, 1, 1, 3, 8'h87,
                         "rearm_mid_partial_record");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h87, 1'b1);
            check_zero_payload("rearm_mid_partial_retire");
            group_end("controls_tags_and_abort_phases");
        end
    endtask

    task automatic group_main_negatives;
        integer i;
        begin
            group_begin("negative_coherence_and_recovery");
            reset_dut;

            cases = cases + 1;
            rearm_dut(3'b000, 8'h21);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h21, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b010, 8'h21, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b001, 8'h21, 1'b0);
            check_events(4'b0001, "early_rise_coincident_fall.events");
            check_seen(4'b0001, "early_rise_coincident_fall.seen");
            check64(fault_count, 64'd1, "early_rise_coincident_fall.count");
            check64(out_valid, 1'b0, "early_rise_coincident_fall.valid");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h21, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h21, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h21, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h21, 1'b0);
            check_record(2, 1, 1, 1, 5, 7, 8'h21, "frame_recovery");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h21, 1'b1);
            check_zero_payload("frame_recovery_retire");

            // Unequal end edges make both subset rises incoherent. No stale
            // lane/start state is reused for the eventual common future start.
            cases = cases + 1;
            rearm_dut(3'b000, 8'h22);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h22, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h22, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b011, 8'h22, 1'b0);
            check_events(4'b0001, "unequal_end_first.events");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h22, 1'b0);
            check_events(4'b0001, "unequal_end_second.events");
            check64(fault_count, 64'd2, "unequal_end.count");
            check64(out_valid, 1'b0, "unequal_end.valid");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h22, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h22, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h22, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h22, 1'b0);
            check_record(2, 1, 1, 1, 6, 8, 8'h22, "unequal_end_recovery");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h22, 1'b1);
            check_zero_payload("unequal_end_retire");

            // No common start: proper-subset starts report incoherent events,
            // while a constant subset level adds no clocked event.
            cases = cases + 1;
            rearm_dut(3'b000, 8'h23);
            tick(1'b0, 1'b0, 1'b0, 3'b001, 8'h23, 1'b0);
            check_events(4'b0001, "no_common_start.first");
            for (i = 0; i < 3; i = i + 1) begin
                tick(1'b0, 1'b0, 1'b0, 3'b001, 8'h23, 1'b0);
                check_events(4'b0000, "no_common_start.constant");
            end
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h23, 1'b0);
            check_events(4'b0000, "no_common_start.fall");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h23, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h23, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h23, 1'b0);
            check_record(2, 1, 1, 1, 6, 8, 8'h23, "no_common_start_recovery");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h23, 1'b1);
            check_zero_payload("no_common_start_retire");

            // Equal per-lane periods with fixed phase offsets never present a
            // common sampled rising. Numeric period equality alone must not
            // produce a record.
            cases = cases + 1;
            rearm_dut(3'b000, 8'h24);
            tick(1'b0, 1'b0, 1'b0, 3'b001, 8'h24, 1'b0);
            check_events(4'b0001, "phase_shift_lane0_start.events");
            tick(1'b0, 1'b0, 1'b0, 3'b011, 8'h24, 1'b0);
            check_events(4'b0001, "phase_shift_lane1_start.events");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h24, 1'b0);
            check_events(4'b0001, "phase_shift_lane2_start.events");
            tick(1'b0, 1'b0, 1'b0, 3'b011, 8'h24, 1'b0);
            check_events(4'b0000, "phase_shift_lane0_fall.events");
            tick(1'b0, 1'b0, 1'b0, 3'b001, 8'h24, 1'b0);
            check_events(4'b0000, "phase_shift_lane1_fall.events");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h24, 1'b0);
            check_events(4'b0000, "phase_shift_lane2_fall.events");
            tick(1'b0, 1'b0, 1'b0, 3'b001, 8'h24, 1'b0);
            check_events(4'b0001, "phase_shift_lane0_next.events");
            tick(1'b0, 1'b0, 1'b0, 3'b011, 8'h24, 1'b0);
            check_events(4'b0001, "phase_shift_lane1_next.events");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h24, 1'b0);
            check_events(4'b0001, "phase_shift_lane2_next.events");
            check_seen(4'b0001, "phase_shift.seen");
            check64(out_valid, 1'b0, "phase_shift.valid");
            check64(fault_count, 64'd6, "phase_shift.count");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h24, 1'b0);
            check_events(4'b0000, "phase_shift_all_fall.events");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h24, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h24, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h24, 1'b0);
            check_record(2, 1, 1, 1, 11, 13, 8'h24,
                         "phase_shift_recovery");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h24, 1'b1);
            check_zero_payload("phase_shift_retire");

            // A common sampled close requires all three first falls strictly
            // inside. One lane held high after R0 is an incomplete/missing
            // first fall; the subset rising tails are incoherent and no record
            // may splice the two lanes that did fall.
            cases = cases + 1;
            rearm_dut(3'b000, 8'h25);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h25, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b001, 8'h25, 1'b0);
            check_events(4'b0000, "incomplete_fall.partial.events");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h25, 1'b0);
            check_events(4'b0001, "incomplete_fall.tail.events");
            check_seen(4'b0001, "incomplete_fall.seen");
            check64(out_valid, 1'b0, "incomplete_fall.valid");
            check64(fault_count, 64'd1, "incomplete_fall.count");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h25, 1'b0);
            check_events(4'b0000, "incomplete_fall.all_low.events");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h25, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h25, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h25, 1'b0);
            check_record(2, 1, 1, 1, 5, 7, 8'h25,
                         "incomplete_fall_recovery");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h25, 1'b1);
            check_zero_payload("incomplete_fall_retire");

            // A lane that rises again after its first fall, while the other
            // lanes stay low, must abort rather than contribute to a later
            // common close.
            cases = cases + 1;
            rearm_dut(3'b000, 8'h26);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h26, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h26, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b001, 8'h26, 1'b0);
            check_events(4'b0001, "extra_rise.events");
            check_seen(4'b0001, "extra_rise.seen");
            check64(fault_count, 64'd1, "extra_rise.count");
            check64(out_valid, 1'b0, "extra_rise.valid");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h26, 1'b0);
            check_events(4'b0000, "extra_rise.all_low.events");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h26, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h26, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h26, 1'b0);
            check_record(2, 1, 1, 1, 5, 7, 8'h26, "extra_rise_recovery");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h26, 1'b1);
            check_zero_payload("extra_rise_retire");
            group_end("negative_coherence_and_recovery");
        end
    endtask

    task automatic group_main_queue;
        integer i;
        begin
            group_begin("one_slot_transport_and_fault_priority");
            reset_dut;

            // Long stall: the entire old record and out_valid remain stable
            // while input sampling continues independently.
            cases = cases + 1;
            rearm_dut(3'b000, 8'h41);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h41, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h41, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h41, 1'b0);
            check_record(2, 1, 1, 1, 1, 3, 8'h41, "stall_a");
            for (i = 0; i < 6; i = i + 1) begin
                tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h41, 1'b0);
                check_record_fields(2, 1, 1, 1, 1, 3, 8'h41, "stall_hold");
                check_events(4'b0000, "stall_hold.events");
                check64(fault_count, 64'd0, "stall_hold.count");
            end
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h41, 1'b1);
            check_zero_payload("stall_retire");
            check64(armed, 1'b1, "stall_retire.armed");

            // A ready retirement and a new candidate may fill the same slot
            // on one edge, but a candidate created from an empty slot is not
            // consumable until a later edge.
            cases = cases + 1;
            reset_dut;
            rearm_dut(3'b000, 8'h42);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h42, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h42, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h42, 1'b0);
            check_record(2, 1, 1, 1, 1, 3, 8'h42, "refill_a");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h42, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h42, 1'b1);
            check_record(2, 1, 1, 1, 3, 5, 8'h42, "refill_b");
            check_events(4'b0000, "refill_b.events");
            check64(fault_count, 64'd0, "refill_b.count");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h42, 1'b1);
            check_zero_payload("refill_retire");

            // A valid candidate against a full, non-ready slot is dropped and
            // reports overrun without changing the old record.
            cases = cases + 1;
            reset_dut;
            rearm_dut(3'b000, 8'h43);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h43, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h43, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h43, 1'b0);
            check_record(2, 1, 1, 1, 1, 3, 8'h43, "overrun_a");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h43, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h43, 1'b0);
            check_events(4'b1000, "overrun.events");
            check_seen(4'b1000, "overrun.seen");
            check64(fault_count, 64'd1, "overrun.count");
            check64(out_valid, 1'b1, "overrun.old_valid");
            check64(out_period, 64'd2, "overrun.old_period");
            check64(out_high0, 64'd1, "overrun.old_high0");
            check64(out_high1, 64'd1, "overrun.old_high1");
            check64(out_high2, 64'd1, "overrun.old_high2");
            check64(out_start, 64'd1, "overrun.old_start");
            check64(out_end, 64'd3, "overrun.old_end");
            check64(out_tag, 8'h43, "overrun.old_tag");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h43, 1'b1);
            check_zero_payload("overrun_retire");

            // Incoherent input faults do not mutate an older queued record;
            // retirement still follows out_ready independently on that edge.
            cases = cases + 1;
            reset_dut;
            rearm_dut(3'b000, 8'h44);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h44, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h44, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h44, 1'b0);
            check_record(2, 1, 1, 1, 1, 3, 8'h44, "fault_retire_a");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h44, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b001, 8'h44, 1'b1);
            check_events(4'b0001, "fault_retire.events");
            check_seen(4'b0001, "fault_retire.seen");
            check64(fault_count, 64'd1, "fault_retire.count");
            check_zero_payload("fault_retire.retired");
            check64(armed, 1'b1, "fault_retire.armed");

            // STOP on a would-be completion edge suppresses the candidate and
            // the old ready/valid handshake, then clears all state.
            cases = cases + 1;
            reset_dut;
            rearm_dut(3'b000, 8'h45);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h45, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h45, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h45, 1'b0);
            check_record(2, 1, 1, 1, 1, 3, 8'h45, "stop_completion_a");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h45, 1'b0);
            tick(1'b0, 1'b1, 1'b0, 3'b111, 8'h45, 1'b1);
            check_clean("stop_completion_edge");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h45, 1'b1);
            check_clean("stop_completion_deassert");

            // Rearm outranks an old ready handshake and clears the slot.
            cases = cases + 1;
            reset_dut;
            rearm_dut(3'b000, 8'h46);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h46, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h46, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h46, 1'b0);
            check_record(2, 1, 1, 1, 1, 3, 8'h46, "rearm_retire_a");
            tick(1'b0, 1'b0, 1'b1, 3'b000, 8'h47, 1'b1);
            check_armed_clean("rearm_retire");

            // Reset with a queued record clears occupancy and payload and
            // suppresses a coincident ready handshake.
            cases = cases + 1;
            reset_dut;
            rearm_dut(3'b000, 8'h49);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h49, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h49, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h49, 1'b0);
            check_record(2, 1, 1, 1, 1, 3, 8'h49, "reset_queue_a");
            tick(1'b1, 1'b0, 1'b0, 3'b000, 8'h00, 1'b1);
            check_clean("reset_with_queued_record");
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h00, 1'b1);
            check_clean("reset_with_queued_deassert");
            group_end("one_slot_transport_and_fault_priority");
        end
    endtask

    task automatic group_main_priority;
        integer i;
        begin
            group_begin("period_before_incoherent_with_stalled_record");
            reset_dut;
            cases = cases + 1;
            rearm_dut(3'b000, 8'h48);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h48, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h48, 1'b0);
            tick(1'b0, 1'b0, 1'b0, 3'b111, 8'h48, 1'b0);
            check_record(2, 1, 1, 1, 1, 3, 8'h48, "priority_a");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h48, 1'b0);
            for (i = 0; i < 14; i = i + 1) begin
                tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h48, 1'b0);
            end
            tick(1'b0, 1'b0, 1'b0, 3'b001, 8'h48, 1'b0);
            check_events(4'b0010, "priority_period.events");
            check_seen(4'b0010, "priority_period.seen");
            check64(fault_count, 64'd1, "priority_period.count");
            check64(out_valid, 1'b1, "priority_period.old_valid");
            check64(out_period, 64'd2, "priority_period.old_period");
            check64(out_start, 64'd1, "priority_period.old_start");
            check64(out_end, 64'd3, "priority_period.old_end");
            check64(out_tag, 8'h48, "priority_period.old_tag");
            check64(armed, 1'b1, "priority_period.armed");
            tick(1'b0, 1'b0, 1'b0, 3'b000, 8'h48, 1'b1);
            check_zero_payload("priority_period.retire");
            group_end("period_before_incoherent_with_stalled_record");
        end
    endtask
    initial begin
        $display("TB_BEGIN COUNT_W=%0d WITNESS_W=%0d TAG_W=%0d TEST_GROUP=%0d",
                 COUNT_W, WITNESS_W, TAG_W, TEST_GROUP);
        case (TEST_GROUP)
            0: begin
                group_main_controls;
                group_main_negatives;
                group_main_queue;
                group_main_priority;
            end
            1: begin
                group_exhaustive_width2;
                group_fault_saturation;
            end
            2: group_exhaustive_width3;
            3: group_count16_boundaries;
            4: group_min_width;
            5: group_max_width;
            6: group_random;
            7: group_mutant_mixed;
            8: group_mutant_relaxed;
            9: group_small_boundaries;
            10: group_default_smoke;
            11: group_width3_overflow;
            12: group_witness_w3_exhaustion;
            default: begin
                $display("MISMATCH unknown TEST_GROUP=%0d", TEST_GROUP);
                mismatches = mismatches + 1;
            end
        endcase
        $display("TB_STATS groups=%0d cases=%0d samples=%0d assertions=%0d records=%0d fault_events=%0d mismatches=%0d",
                 groups, cases, samples, assertions, records, fault_events, mismatches);
        if (mismatches == 0) begin
            $display("TB_PASS");
            $finish;
        end else begin
            $display("TB_FAIL");
            $fatal(1, "TB_FAIL");
        end
    end

endmodule

module tb_invalid_pwm_coherent #(
    parameter integer COUNT_W = 2,
    parameter integer WITNESS_W = 8,
    parameter integer TAG_W = 8
);
    localparam integer TAG_SAFE = (TAG_W < 1) ? 1 :
                                  ((TAG_W > 64) ? 64 : TAG_W);
    localparam integer COUNT_SAFE = (COUNT_W < 2) ? 2 :
                                    ((COUNT_W > 32) ? 32 : COUNT_W);
    localparam integer WITNESS_SAFE = (WITNESS_W < 2) ? 2 :
                                      ((WITNESS_W > 64) ? 64 : WITNESS_W);
    logic clk;
    logic rst;
    logic stop;
    logic rearm;
    logic [2:0] sample_levels;
    logic [TAG_SAFE-1:0] window_tag;
    logic out_ready;
    logic armed;
    logic out_valid;
    logic [COUNT_SAFE-1:0] out_period;
    logic [COUNT_SAFE-1:0] out_high0;
    logic [COUNT_SAFE-1:0] out_high1;
    logic [COUNT_SAFE-1:0] out_high2;
    logic [WITNESS_SAFE-1:0] out_start;
    logic [WITNESS_SAFE-1:0] out_end;
    logic [TAG_SAFE-1:0] out_tag;
    logic incoherent_event;
    logic period_overflow_event;
    logic witness_overflow_event;
    logic overrun_event;
    logic incoherent_seen;
    logic period_overflow_seen;
    logic witness_overflow_seen;
    logic overrun_seen;
    logic [COUNT_SAFE-1:0] fault_count;

    initial begin
        clk = 1'b0;
        rst = 1'b0;
        stop = 1'b0;
        rearm = 1'b0;
        sample_levels = 3'b000;
        window_tag = '0;
        out_ready = 1'b0;
    end

    deepeye_pwm_coherent_capture #(
        .COUNT_W(COUNT_W),
        .WITNESS_W(WITNESS_W),
        .TAG_W(TAG_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .stop(stop),
        .rearm(rearm),
        .sample_levels(sample_levels),
        .window_tag(window_tag),
        .out_ready(out_ready),
        .armed(armed),
        .out_valid(out_valid),
        .out_period(out_period),
        .out_high0(out_high0),
        .out_high1(out_high1),
        .out_high2(out_high2),
        .out_start(out_start),
        .out_end(out_end),
        .out_tag(out_tag),
        .incoherent_event(incoherent_event),
        .period_overflow_event(period_overflow_event),
        .witness_overflow_event(witness_overflow_event),
        .overrun_event(overrun_event),
        .incoherent_seen(incoherent_seen),
        .period_overflow_seen(period_overflow_seen),
        .witness_overflow_seen(witness_overflow_seen),
        .overrun_seen(overrun_seen),
        .fault_count(fault_count)
    );

    initial begin
        #20;
        $display("INVALID_CONFIG_GUARD_MISSING COUNT_W=%0d WITNESS_W=%0d TAG_W=%0d",
                 COUNT_W, WITNESS_W, TAG_W);
        $fatal(1, "INVALID_CONFIG_GUARD_MISSING");
    end
endmodule

module tb_invalid_count_zero;
    tb_invalid_pwm_coherent #(.COUNT_W(0), .WITNESS_W(8), .TAG_W(8)) u();
endmodule
module tb_invalid_count_negative;
    tb_invalid_pwm_coherent #(.COUNT_W(-1), .WITNESS_W(8), .TAG_W(8)) u();
endmodule
module tb_invalid_count_high;
    tb_invalid_pwm_coherent #(.COUNT_W(33), .WITNESS_W(8), .TAG_W(8)) u();
endmodule
module tb_invalid_witness_zero;
    tb_invalid_pwm_coherent #(.COUNT_W(8), .WITNESS_W(0), .TAG_W(8)) u();
endmodule
module tb_invalid_witness_negative;
    tb_invalid_pwm_coherent #(.COUNT_W(8), .WITNESS_W(-1), .TAG_W(8)) u();
endmodule
module tb_invalid_witness_high;
    tb_invalid_pwm_coherent #(.COUNT_W(8), .WITNESS_W(65), .TAG_W(8)) u();
endmodule
module tb_invalid_tag_zero;
    tb_invalid_pwm_coherent #(.COUNT_W(8), .WITNESS_W(8), .TAG_W(0)) u();
endmodule
module tb_invalid_tag_negative;
    tb_invalid_pwm_coherent #(.COUNT_W(8), .WITNESS_W(8), .TAG_W(-1)) u();
endmodule
module tb_invalid_tag_high;
    tb_invalid_pwm_coherent #(.COUNT_W(8), .WITNESS_W(8), .TAG_W(65)) u();
endmodule
