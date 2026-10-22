`timescale 1ns/1ps

module tb_sample_scan_capture #(
    parameter int SEQ_W  = 32,
    parameter int TICK_W = 64,
    parameter int TAG_W  = 32,
    parameter int STAT_W = 32
);
    logic clk;
    logic rst;
    logic stop;
    logic rearm;
    logic [TAG_W-1:0] rearm_tag;
    logic sample_strobe;
    logic [1:0] sample_channel;
    logic [15:0] sample_data;
    logic [TICK_W-1:0] sample_tick;
    logic [7:0] sample_quality;
    logic out_ready;

    logic out_valid;
    logic [63:0] out_data;
    logic [4*TICK_W-1:0] out_ticks;
    logic [31:0] out_quality;
    logic [SEQ_W-1:0] out_first_seq;
    logic [SEQ_W-1:0] out_last_seq;
    logic [TAG_W-1:0] out_tag;
    logic armed;
    logic [2:0] partial_len;
    logic [SEQ_W-1:0] next_seq;
    logic seq_exhausted;
    logic order_error_event;
    logic overrun_event;
    logic seq_exhaust_event;
    logic [STAT_W-1:0] stat_events;
    logic [STAT_W-1:0] stat_scans;
    logic [STAT_W-1:0] stat_retired;
    logic [STAT_W-1:0] stat_discarded_samples;
    logic [STAT_W-1:0] stat_order_errors;
    logic [STAT_W-1:0] stat_overruns;

    deepeye_sample_scan_capture #(
        .SEQ_W(SEQ_W),
        .TICK_W(TICK_W),
        .TAG_W(TAG_W),
        .STAT_W(STAT_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .stop(stop),
        .rearm(rearm),
        .rearm_tag(rearm_tag),
        .sample_strobe(sample_strobe),
        .sample_channel(sample_channel),
        .sample_data(sample_data),
        .sample_tick(sample_tick),
        .sample_quality(sample_quality),
        .out_ready(out_ready),
        .out_valid(out_valid),
        .out_data(out_data),
        .out_ticks(out_ticks),
        .out_quality(out_quality),
        .out_first_seq(out_first_seq),
        .out_last_seq(out_last_seq),
        .out_tag(out_tag),
        .armed(armed),
        .partial_len(partial_len),
        .next_seq(next_seq),
        .seq_exhausted(seq_exhausted),
        .order_error_event(order_error_event),
        .overrun_event(overrun_event),
        .seq_exhaust_event(seq_exhaust_event),
        .stat_events(stat_events),
        .stat_scans(stat_scans),
        .stat_retired(stat_retired),
        .stat_discarded_samples(stat_discarded_samples),
        .stat_order_errors(stat_order_errors),
        .stat_overruns(stat_overruns)
    );

    always #5 clk = ~clk;

    string test_case;
    int errors;
    int checks;
    int windows;

    int m_armed;
    int m_exhausted;
    int m_partial_len;
    int m_slot_valid;
    int m_events;
    int m_scans;
    int m_retired;
    int m_discarded;
    int m_order_errors;
    int m_overruns;
    int m_order_error_event;
    int m_overrun_event;
    int m_seq_exhaust_event;
    logic [SEQ_W-1:0] m_next_seq;
    logic [SEQ_W-1:0] m_partial_first_seq;
    logic [SEQ_W-1:0] m_slot_first_seq;
    logic [SEQ_W-1:0] m_slot_last_seq;
    logic [TAG_W-1:0] m_tag;
    logic [TAG_W-1:0] m_slot_tag;
    logic [15:0] m_partial_data [0:3];
    logic [TICK_W-1:0] m_partial_tick [0:3];
    logic [7:0] m_partial_quality [0:3];
    logic [63:0] m_slot_data;
    logic [4*TICK_W-1:0] m_slot_ticks;
    logic [31:0] m_slot_quality;

    logic [63:0] agg_scans;
    logic [63:0] agg_discarded;
    logic [63:0] agg_order_errors;
    logic [63:0] agg_partial_end;
    logic [63:0] agg_windows;

    function automatic logic [63:0] sat_stat(input longint value);
        logic [63:0] maximum;
        begin
            maximum = (64'd1 << STAT_W) - 64'd1;
            if (value > maximum) begin
                sat_stat = maximum;
            end else begin
                sat_stat = value;
            end
        end
    endfunction

    task automatic check64(
        input string field,
        input logic [63:0] expected,
        input logic [63:0] actual
    );
        begin
            checks = checks + 1;
            if (expected !== actual) begin
                errors = errors + 1;
                $display("SAMPLE_SCAN_MISMATCH field=%s expected=%0d actual=%0d", field, expected, actual);
            end
        end
    endtask

    task automatic check_payload();
        begin
            checks = checks + 1;
            if (dut.out_data !== m_slot_data) begin
                errors = errors + 1;
                $display("SAMPLE_SCAN_MISMATCH field=data expected=%016h actual=%016h", m_slot_data, dut.out_data);
            end
            checks = checks + 1;
            if (dut.out_ticks !== m_slot_ticks) begin
                errors = errors + 1;
                $display("SAMPLE_SCAN_MISMATCH field=ticks expected=%0h actual=%0h", m_slot_ticks, dut.out_ticks);
            end
            checks = checks + 1;
            if (dut.out_quality !== m_slot_quality) begin
                errors = errors + 1;
                $display("SAMPLE_SCAN_MISMATCH field=quality expected=%08h actual=%08h", m_slot_quality, dut.out_quality);
            end
            check64("first_seq", m_slot_first_seq, dut.out_first_seq);
            check64("last_seq", m_slot_last_seq, dut.out_last_seq);
            check64("tag", m_slot_tag, dut.out_tag);
        end
    endtask

    task automatic compare_model();
        begin
            check64("out_valid", m_slot_valid, dut.out_valid);
            check64("armed", m_armed, dut.armed);
            check64("partial_len", m_partial_len, dut.partial_len);
            check64("next_seq", m_next_seq, dut.next_seq);
            check64("seq_exhausted", m_exhausted, dut.seq_exhausted);
            check64("order_error_event", m_order_error_event, dut.order_error_event);
            check64("overrun_event", m_overrun_event, dut.overrun_event);
            check64("seq_exhaust_event", m_seq_exhaust_event, dut.seq_exhaust_event);
            check64("stat_events", sat_stat(m_events), dut.stat_events);
            check64("stat_scans", sat_stat(m_scans), dut.stat_scans);
            check64("stat_retired", sat_stat(m_retired), dut.stat_retired);
            check64("stat_discarded", sat_stat(m_discarded), dut.stat_discarded_samples);
            check64("stat_order_errors", sat_stat(m_order_errors), dut.stat_order_errors);
            check64("stat_overruns", sat_stat(m_overruns), dut.stat_overruns);
            if (m_slot_valid) begin
                check_payload();
            end
        end
    endtask

    task automatic model_clear(input bit arm_it, input logic [TAG_W-1:0] tag_in);
        int lane;
        begin
            m_armed = arm_it ? 1 : 0;
            m_exhausted = 0;
            m_partial_len = 0;
            m_slot_valid = 0;
            m_events = 0;
            m_scans = 0;
            m_retired = 0;
            m_discarded = 0;
            m_order_errors = 0;
            m_overruns = 0;
            m_order_error_event = 0;
            m_overrun_event = 0;
            m_seq_exhaust_event = 0;
            m_next_seq = '0;
            m_partial_first_seq = '0;
            m_slot_first_seq = '0;
            m_slot_last_seq = '0;
            m_tag = arm_it ? tag_in : '0;
            m_slot_tag = '0;
            m_slot_data = '0;
            m_slot_ticks = '0;
            m_slot_quality = '0;
            for (lane = 0; lane < 4; lane = lane + 1) begin
                m_partial_data[lane] = '0;
                m_partial_tick[lane] = '0;
                m_partial_quality[lane] = '0;
            end
        end
    endtask

    task automatic model_step(
        input bit event_i,
        input logic [1:0] channel_i,
        input logic [15:0] data_i,
        input logic [TICK_W-1:0] tick_i,
        input logic [7:0] quality_i,
        input bit ready_i
    );
        logic [SEQ_W-1:0] seq_value;
        begin
            m_order_error_event = 0;
            m_overrun_event = 0;
            m_seq_exhaust_event = 0;

            if (m_slot_valid && ready_i) begin
                m_retired = m_retired + 1;
                m_slot_valid = 0;
            end

            if (event_i && m_armed) begin
                seq_value = m_next_seq;
                m_events = m_events + 1;

                if (m_partial_len == 0) begin
                    if (channel_i == 2'd0) begin
                        m_partial_data[0] = data_i;
                        m_partial_tick[0] = tick_i;
                        m_partial_quality[0] = quality_i;
                        m_partial_first_seq = seq_value;
                        m_partial_len = 1;
                    end else begin
                        m_order_errors = m_order_errors + 1;
                        m_discarded = m_discarded + 1;
                        m_order_error_event = 1;
                    end
                end else if (channel_i == m_partial_len[1:0]) begin
                    if (m_partial_len == 3) begin
                        m_scans = m_scans + 1;
                        if (m_slot_valid) begin
                            m_overruns = m_overruns + 1;
                            m_discarded = m_discarded + 4;
                            m_overrun_event = 1;
                        end else begin
                            m_slot_valid = 1;
                            m_slot_data = {data_i,
                                           m_partial_data[2],
                                           m_partial_data[1],
                                           m_partial_data[0]};
                            m_slot_ticks = {tick_i,
                                            m_partial_tick[2],
                                            m_partial_tick[1],
                                            m_partial_tick[0]};
                            m_slot_quality = {quality_i,
                                              m_partial_quality[2],
                                              m_partial_quality[1],
                                              m_partial_quality[0]};
                            m_slot_first_seq = m_partial_first_seq;
                            m_slot_last_seq = m_partial_first_seq + 3;
                            m_slot_tag = m_tag;
                        end
                        m_partial_len = 0;
                    end else begin
                        m_partial_data[m_partial_len] = data_i;
                        m_partial_tick[m_partial_len] = tick_i;
                        m_partial_quality[m_partial_len] = quality_i;
                        m_partial_len = m_partial_len + 1;
                    end
                end else begin
                    m_order_errors = m_order_errors + 1;
                    m_order_error_event = 1;
                    if (channel_i == 2'd0) begin
                        m_discarded = m_discarded + m_partial_len;
                        m_partial_data[0] = data_i;
                        m_partial_tick[0] = tick_i;
                        m_partial_quality[0] = quality_i;
                        m_partial_first_seq = seq_value;
                        m_partial_len = 1;
                    end else begin
                        m_discarded = m_discarded + m_partial_len + 1;
                        m_partial_len = 0;
                    end
                end

                if (seq_value == {SEQ_W{1'b1}}) begin
                    m_armed = 0;
                    m_exhausted = 1;
                    m_seq_exhaust_event = 1;
                    m_next_seq = {SEQ_W{1'b1}};
                    if (m_partial_len != 0) begin
                        m_discarded = m_discarded + m_partial_len;
                        m_partial_len = 0;
                    end
                end else begin
                    m_next_seq = m_next_seq + 1'b1;
                end
            end
        end
    endtask

    task automatic initial_reset();
        begin
            @(negedge clk);
            rst = 1'b1;
            stop = 1'b0;
            rearm = 1'b0;
            rearm_tag = '0;
            sample_strobe = 1'b0;
            sample_channel = 2'd0;
            sample_data = 16'd0;
            sample_tick = '0;
            sample_quality = 8'd0;
            out_ready = 1'b0;
            #1;
            checks = checks + 1;
            if (dut.out_valid !== 1'b0) begin
                errors = errors + 1;
                $display("SAMPLE_SCAN_MISMATCH field=reset_out_valid expected=0 actual=1");
            end
            @(posedge clk);
            #1;
            model_clear(1'b0, '0);
            compare_model();
            @(negedge clk);
            rst = 1'b0;
        end
    endtask

    task automatic send_ordinary(
        input bit strobe_i,
        input logic [1:0] channel_i,
        input logic [15:0] data_i,
        input logic [TICK_W-1:0] tick_i,
        input logic [7:0] quality_i,
        input bit ready_i
    );
        begin
            @(negedge clk);
            rst = 1'b0;
            stop = 1'b0;
            rearm = 1'b0;
            sample_strobe = strobe_i;
            sample_channel = channel_i;
            sample_data = data_i;
            sample_tick = tick_i;
            sample_quality = quality_i;
            out_ready = ready_i;
            @(posedge clk);
            #1;
            model_step(strobe_i, channel_i, data_i, tick_i, quality_i, ready_i);
            compare_model();
        end
    endtask

    task automatic idle_cycle(input bit ready_i);
        begin
            send_ordinary(1'b0, 2'd0, 16'd0, '0, 8'd0, ready_i);
        end
    endtask

    task automatic abort_window(
        input bit rst_i,
        input bit stop_i,
        input bit rearm_i,
        input logic [TAG_W-1:0] tag_i
    );
        begin
            @(negedge clk);
            rst = rst_i;
            stop = stop_i;
            rearm = rearm_i;
            rearm_tag = tag_i;
            sample_strobe = 1'b1;
            sample_channel = 2'd3;
            sample_data = 16'hdead;
            sample_tick = '1;
            sample_quality = 8'hff;
            out_ready = 1'b1;
            #1;
            checks = checks + 1;
            if (dut.out_valid !== 1'b0) begin
                errors = errors + 1;
                $display("SAMPLE_SCAN_MISMATCH field=abort_out_valid expected=0 actual=1");
            end
            @(posedge clk);
            #1;
            if (rst_i || stop_i) begin
                model_clear(1'b0, '0);
            end else if (rearm_i) begin
                model_clear(1'b1, tag_i);
            end
            compare_model();
            @(negedge clk);
            rst = 1'b0;
            stop = 1'b0;
            rearm = 1'b0;
            sample_strobe = 1'b0;
            out_ready = 1'b0;
        end
    endtask

    task automatic begin_window(input logic [TAG_W-1:0] tag_i);
        begin
            abort_window(1'b0, 1'b0, 1'b1, tag_i);
            windows = windows + 1;
        end
    endtask

    task automatic emit_and_finish();
        begin
            $display("SAMPLE_SCAN_STATS case=%s checks=%0d errors=%0d windows=%0d events=%0d scans=%0d retired=%0d discarded=%0d order_errors=%0d overruns=%0d partial_len=%0d occupied=%0d armed=%0d exhausted=%0d",
                     test_case, checks, errors, windows,
                     dut.stat_events, dut.stat_scans, dut.stat_retired,
                     dut.stat_discarded_samples, dut.stat_order_errors,
                     dut.stat_overruns, dut.partial_len,
                     dut.out_valid ? 1 : 0, dut.armed, dut.seq_exhausted);
            if (errors == 0) begin
                $display("SAMPLE_SCAN_PASS");
                $finish;
            end else begin
                $fatal(1, "tb_sample_scan_capture: case failed");
            end
        end
    endtask

    task automatic run_directed();
        logic [63:0] expected_data;
        logic [4*TICK_W-1:0] expected_ticks;
        logic [31:0] expected_quality;
        int stall_cycle;
        begin
            initial_reset();
            begin_window({TAG_W{1'b0}} | 32'h11223344);

            send_ordinary(1'b1, 2'd0, 16'h1111, 64'h0000000000000001, 8'h10, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h2222, 64'h0000000000000002, 8'h20, 1'b0);
            check64("wrong_first_order_event", 1, dut.order_error_event);
            check64("wrong_first_discarded", 2, dut.stat_discarded_samples);
            check64("wrong_first_partial", 0, dut.partial_len);

            send_ordinary(1'b1, 2'd0, 16'h0000, 64'h0000000000000000, 8'h00, 1'b0);
            check64("error_event_cleared", 0, dut.order_error_event);
            send_ordinary(1'b1, 2'd1, 16'h0001, 64'h1111111111111111, 8'h7f, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h7fff, 64'h8000000000000000, 8'h80, 1'b0);
            send_ordinary(1'b1, 2'd3, 16'hffff, 64'hfffffffffffffffe, 8'hff, 1'b0);

            expected_data = {16'hffff, 16'h7fff, 16'h0001, 16'h0000};
            expected_ticks = {64'hfffffffffffffffe,
                              64'h8000000000000000,
                              64'h1111111111111111,
                              64'h0000000000000000};
            expected_quality = {8'hff, 8'h80, 8'h7f, 8'h00};
            check64("scan1_valid", 1, dut.out_valid);
            check64("scan1_first", 2, dut.out_first_seq);
            check64("scan1_last", 5, dut.out_last_seq);
            check64("scan1_tag", 32'h11223344, dut.out_tag);
            check64("scan1_data", expected_data, dut.out_data);
            check64("scan1_quality", expected_quality, dut.out_quality);
            checks = checks + 1;
            if (dut.out_ticks !== expected_ticks) begin
                errors = errors + 1;
                $display("SAMPLE_SCAN_MISMATCH field=scan1_ticks expected=%0h actual=%0h", expected_ticks, dut.out_ticks);
            end

            for (stall_cycle = 0; stall_cycle < 8; stall_cycle = stall_cycle + 1) begin
                idle_cycle(1'b0);
            end
            check64("stalled_data_stable", expected_data, dut.out_data);
            check64("stalled_valid_stable", 1, dut.out_valid);

            send_ordinary(1'b1, 2'd0, 16'h3000, 64'h3000000000000000, 8'h30, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h3001, 64'h3000000000000001, 8'h31, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h3002, 64'h3000000000000002, 8'h32, 1'b0);
            send_ordinary(1'b1, 2'd3, 16'h3003, 64'h3000000000000003, 8'h33, 1'b0);
            check64("drop_overrun_event", 1, dut.overrun_event);
            check64("drop_overruns", 1, dut.stat_overruns);
            check64("drop_discarded", 6, dut.stat_discarded_samples);
            check64("drop_scans", 2, dut.stat_scans);
            check64("drop_old_data_stable", expected_data, dut.out_data);
            check64("drop_old_first_stable", 2, dut.out_first_seq);

            idle_cycle(1'b0);
            check64("overrun_pulse_cleared", 0, dut.overrun_event);

            send_ordinary(1'b1, 2'd0, 16'h4000, 64'h4000000000000000, 8'h40, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h4001, 64'h4000000000000001, 8'h41, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h4002, 64'h4000000000000002, 8'h42, 1'b0);
            send_ordinary(1'b1, 2'd3, 16'h4003, 64'h4000000000000003, 8'h43, 1'b1);
            check64("refill_retired", 1, dut.stat_retired);
            check64("refill_overrun_clear", 0, dut.overrun_event);
            check64("refill_new_first", 10, dut.out_first_seq);
            check64("refill_new_last", 13, dut.out_last_seq);
            check64("refill_new_data", {16'h4003, 16'h4002, 16'h4001, 16'h4000}, dut.out_data);
            check64("refill_new_valid", 1, dut.out_valid);

            idle_cycle(1'b1);
            check64("drained_valid", 0, dut.out_valid);
            check64("drained_retired", 2, dut.stat_retired);
            check64("drained_events", 14, dut.stat_events);
            check64("drained_scans", 3, dut.stat_scans);
            check64("drained_discarded", 6, dut.stat_discarded_samples);
            check64("drained_identity_events", 14, 4 * (dut.stat_retired + (dut.out_valid ? 1 : 0)) + dut.partial_len + dut.stat_discarded_samples);
            check64("drained_identity_scans", 3, dut.stat_retired + (dut.out_valid ? 1 : 0) + dut.stat_overruns);
            emit_and_finish();
        end
    endtask

    initial begin
        clk = 1'b0;
        rst = 1'b0;
        stop = 1'b0;
        rearm = 1'b0;
        rearm_tag = '0;
        sample_strobe = 1'b0;
        sample_channel = 2'd0;
        sample_data = 16'd0;
        sample_tick = '0;
        sample_quality = 8'd0;
        out_ready = 1'b0;
        errors = 0;
        checks = 0;
        windows = 0;
        agg_scans = 0;
        agg_discarded = 0;
        agg_order_errors = 0;
        agg_partial_end = 0;
        agg_windows = 0;
        model_clear(1'b0, '0);

        if (!$value$plusargs("CASE=%s", test_case)) begin
            test_case = "directed";
        end

        if (test_case == "directed") begin
            run_directed();
        end else if (test_case == "exhaustive6") begin
            run_exhaustive6();
        end else if (test_case == "quality_lanes") begin
            run_quality_lanes();
        end else if (test_case == "tag64_flush") begin
            run_tag64_flush();
        end else if (test_case == "abort_matrix") begin
            run_abort_matrix();
        end else if (test_case == "seq2_conditions") begin
            run_seq2_conditions();
        end else if (test_case == "seq3_conditions") begin
            run_seq3_conditions();
        end else if (test_case == "seq4_conditions") begin
            run_seq4_conditions();
        end else if (test_case == "stat2_saturation") begin
            run_stat2_saturation();
        end else if (test_case == "stat3_saturation") begin
            run_stat3_saturation();
        end else if (test_case == "tick16_pack") begin
            run_tick16_pack();
        end else if (test_case == "tick1_pack") begin
            run_tick1_pack();
        end else if (test_case == "mutant_mix") begin
            run_mutant_mix();
        end else if (test_case == "mutant_loss") begin
            run_mutant_loss();
        end else if (test_case == "seq16_window") begin
            run_seq16_window();
        end else if (test_case == "random20k") begin
            run_random20k();
        end else begin
            $fatal(1, "tb_sample_scan_capture: unknown CASE");
        end
    end

    task automatic drive_scan(
        input bit ready_i,
        input logic [15:0] base_data,
        input logic [TICK_W-1:0] base_tick,
        input logic [7:0] base_quality
    );
        int channel;
        begin
            for (channel = 0; channel < 4; channel = channel + 1) begin
                send_ordinary(1'b1,
                              channel[1:0],
                              base_data + channel[15:0],
                              base_tick + channel,
                              base_quality + channel[7:0],
                              ready_i);
            end
        end
    endtask

    task automatic drive_partial(
        input int length_i,
        input logic [15:0] base_data,
        input logic [TICK_W-1:0] base_tick,
        input logic [7:0] base_quality
    );
        int channel;
        begin
            for (channel = 0; channel < length_i; channel = channel + 1) begin
                send_ordinary(1'b1,
                              channel[1:0],
                              base_data + channel[15:0],
                              base_tick + channel,
                              base_quality + channel[7:0],
                              1'b0);
            end
        end
    endtask

    task automatic record_window_totals();
        begin
            agg_scans = agg_scans + m_scans;
            agg_discarded = agg_discarded + m_discarded;
            agg_order_errors = agg_order_errors + m_order_errors;
            agg_partial_end = agg_partial_end + m_partial_len;
            agg_windows = agg_windows + 1;
        end
    endtask

    task automatic run_exhaustive6();
        int code;
        int position;
        logic [1:0] channel;
        logic [15:0] data_value;
        logic [TICK_W-1:0] tick_value;
        logic [7:0] quality_value;
        begin
            initial_reset();
            agg_scans = 0;
            agg_discarded = 0;
            agg_order_errors = 0;
            agg_partial_end = 0;
            agg_windows = 0;

            for (code = 0; code < 4096; code = code + 1) begin
                begin_window(code[TAG_W-1:0]);
                for (position = 0; position < 6; position = position + 1) begin
                    channel = (code >> (2 * (5 - position))) & 3;
                    data_value = 16'h8000 ^ code[15:0] ^ position[15:0];
                    tick_value = '0;
                    tick_value[15:0] = code[15:0] ^ position[15:0];
                    quality_value = code[7:0] ^ position[7:0];
                    send_ordinary(1'b1, channel, data_value, tick_value, quality_value, 1'b1);
                end
                idle_cycle(1'b1);
                check64("exhaustive_slot_empty", 0, m_slot_valid);
                record_window_totals();
            end

            check64("exhaustive_windows", 4096, agg_windows);
            check64("exhaustive_scans", 48, agg_scans);
            check64("exhaustive_discarded", 22656, agg_discarded);
            check64("exhaustive_order_errors", 18432, agg_order_errors);
            check64("exhaustive_partial_end", 1728, agg_partial_end);

            begin_window({TAG_W{1'b1}});
            drive_scan(1'b0, 16'hA000, '0, 8'hA0);
            idle_cycle(1'b1);
            check64("exhaustive_final_events", 4, dut.stat_events);
            check64("exhaustive_final_scans", 1, dut.stat_scans);
            check64("exhaustive_final_retired", 1, dut.stat_retired);
            check64("exhaustive_final_discarded", 0, dut.stat_discarded_samples);
            emit_and_finish();
        end
    endtask

    task automatic run_quality_lanes();
        int quality_index;
        int lane;
        int channel;
        int pattern_index;
        logic [15:0] data_value;
        logic [TICK_W-1:0] tick_value;
        logic [TICK_W-1:0] expected_ticks [0:3];
        logic [7:0] quality_value;
        begin
            initial_reset();
            begin_window({TAG_W{1'b1}});

            for (quality_index = 0; quality_index < 256; quality_index = quality_index + 1) begin
                for (lane = 0; lane < 4; lane = lane + 1) begin
                    for (channel = 0; channel < 4; channel = channel + 1) begin
                        pattern_index = (quality_index + channel) % 6;
                        case (pattern_index)
                            0: data_value = 16'h0000;
                            1: data_value = 16'h0001;
                            2: data_value = 16'h7fff;
                            3: data_value = 16'h8000;
                            4: data_value = 16'hffff;
                            default: data_value = 16'ha55a;
                        endcase

                        tick_value = '0;
                        if (channel == 1) begin
                            tick_value[15:0] = quality_index[15:0];
                        end else if (channel == 2) begin
                            tick_value[31] = 1'b1;
                            tick_value[7:0] = quality_index[7:0];
                        end else if (channel == 3) begin
                            tick_value = '1;
                            tick_value[7:0] = quality_index[7:0];
                        end

                        quality_value = quality_index[7:0] ^ (channel * 8'h11);
                        if (channel == lane) begin
                            quality_value = quality_index[7:0];
                        end
                        expected_ticks[channel] = tick_value;
                        send_ordinary(1'b1, channel[1:0], data_value, tick_value, quality_value, 1'b1);
                    end

                    checks = checks + 1;
                    if (dut.out_quality[lane*8 +: 8] !== quality_index[7:0]) begin
                        errors = errors + 1;
                        $display("SAMPLE_SCAN_MISMATCH field=quality_lane lane=%0d expected=%0d actual=%0d",
                                 lane, quality_index[7:0], dut.out_quality[lane*8 +: 8]);
                    end
                    check64("quality_lane_tick", expected_ticks[lane], dut.out_ticks[lane*TICK_W +: TICK_W]);
                end
            end

            idle_cycle(1'b1);
            check64("quality_events", 4096, dut.stat_events);
            check64("quality_scans", 1024, dut.stat_scans);
            check64("quality_retired", 1024, dut.stat_retired);
            check64("quality_discarded", 0, dut.stat_discarded_samples);
            emit_and_finish();
        end
    endtask

    task automatic run_tag64_flush();
        begin
            initial_reset();
            begin_window({TAG_W{1'b1}});
            drive_scan(1'b0, 16'h1000, 64'h1000000000000000, 8'h10);
            check64("tag64_first_valid", 1, dut.out_valid);
            check64("tag64_all_ones", 64'hffffffffffffffff, dut.out_tag);
            send_ordinary(1'b1, 2'd0, 16'h1100, 64'h1100000000000000, 8'h11, 1'b0);
            check64("tag64_partial_before_flush", 1, dut.partial_len);

            abort_window(1'b0, 1'b0, 1'b1, 64'hffffffffffffffff);
            check64("tag64_same_rearm_valid", 0, dut.out_valid);
            check64("tag64_same_rearm_partial", 0, dut.partial_len);
            check64("tag64_same_rearm_events", 0, dut.stat_events);
            check64("tag64_same_rearm_armed", 1, dut.armed);
            check64("tag64_same_rearm_next", 0, dut.next_seq);

            begin_window(64'ha5a55a5aa5a55a5a);
            drive_scan(1'b0, 16'h2000, 64'h2000000000000000, 8'h20);
            check64("tag64_mixed_tag", 64'ha5a55a5aa5a55a5a, dut.out_tag);
            check64("tag64_mixed_payload", {16'h2003, 16'h2002, 16'h2001, 16'h2000}, dut.out_data);
            abort_window(1'b0, 1'b0, 1'b1, 64'h8000000000000001);

            begin_window(64'h8000000000000001);
            drive_scan(1'b0, 16'h3000, 64'h3000000000000000, 8'h30);
            check64("tag64_bit63_tag", 64'h8000000000000001, dut.out_tag);
            check64("tag64_bit63_valid", 1, dut.out_valid);
            idle_cycle(1'b1);
            check64("tag64_retired", 1, dut.stat_retired);
            check64("tag64_final_discarded", 0, dut.stat_discarded_samples);
            emit_and_finish();
        end
    endtask
    task automatic send_ordinary_nocheck(
        input bit strobe_i,
        input logic [1:0] channel_i,
        input logic [15:0] data_i,
        input logic [TICK_W-1:0] tick_i,
        input logic [7:0] quality_i,
        input bit ready_i
    );
        begin
            @(negedge clk);
            rst = 1'b0;
            stop = 1'b0;
            rearm = 1'b0;
            sample_strobe = strobe_i;
            sample_channel = channel_i;
            sample_data = data_i;
            sample_tick = tick_i;
            sample_quality = quality_i;
            out_ready = ready_i;
            @(posedge clk);
            #1;
            model_step(strobe_i, channel_i, data_i, tick_i, quality_i, ready_i);
        end
    endtask

    task automatic abort_hold(
        input bit rst_i,
        input bit stop_i,
        input bit rearm_i,
        input logic [TAG_W-1:0] tag_i,
        input int cycles_i
    );
        int cycle_index;
        begin
            @(negedge clk);
            rst = rst_i;
            stop = stop_i;
            rearm = rearm_i;
            rearm_tag = tag_i;
            sample_strobe = 1'b1;
            sample_channel = 2'd1;
            sample_data = 16'hcafe;
            sample_tick = '1;
            sample_quality = 8'hc3;
            out_ready = 1'b1;
            for (cycle_index = 0; cycle_index < cycles_i; cycle_index = cycle_index + 1) begin
                #1;
                checks = checks + 1;
                if (dut.out_valid !== 1'b0) begin
                    errors = errors + 1;
                    $display("SAMPLE_SCAN_MISMATCH field=held_abort_valid expected=0 actual=1");
                end
                @(posedge clk);
                #1;
                if (rst_i || stop_i) begin
                    model_clear(1'b0, '0);
                end else if (rearm_i) begin
                    model_clear(1'b1, tag_i);
                end
                compare_model();
                @(negedge clk);
            end
            rst = 1'b0;
            stop = 1'b0;
            rearm = 1'b0;
            sample_strobe = 1'b0;
            out_ready = 1'b0;
        end
    endtask

    task automatic run_abort_matrix();
        int stage;
        int kind;
        int combination;
        logic [TAG_W-1:0] tag_value;
        begin
            initial_reset();

            for (stage = 0; stage < 4; stage = stage + 1) begin
                for (kind = 0; kind < 3; kind = kind + 1) begin
                    tag_value = '0;
                    tag_value[15:0] = stage * 8 + kind;
                    begin_window(tag_value);
                    drive_partial(stage, 16'h5000 + stage * 16, 64'h5000000000000000 + stage, 8'h50 + stage);
                    if (kind == 0) begin
                        abort_window(1'b1, 1'b0, 1'b0, tag_value);
                    end else if (kind == 1) begin
                        abort_window(1'b0, 1'b1, 1'b0, tag_value);
                    end else begin
                        abort_window(1'b0, 1'b0, 1'b1, tag_value);
                    end
                    check64("abort_matrix_events_zero", 0, dut.stat_events);
                    check64("abort_matrix_scans_zero", 0, dut.stat_scans);
                    check64("abort_matrix_retired_zero", 0, dut.stat_retired);
                    check64("abort_matrix_discarded_zero", 0, dut.stat_discarded_samples);
                    check64("abort_matrix_partial_zero", 0, dut.partial_len);
                    check64("abort_matrix_next_zero", 0, dut.next_seq);
                    check64("abort_matrix_exhausted_zero", 0, dut.seq_exhausted);
                    if (kind < 2) begin
                        send_ordinary(1'b1, 2'd0, 16'h6000, 64'h6000000000000000, 8'h60, 1'b1);
                        check64("unarmed_event_ignored", 0, dut.stat_events);
                    end else begin
                        idle_cycle(1'b0);
                        check64("rearm_not_consumed", 0, dut.stat_events);
                    end
                end
            end

            for (kind = 0; kind < 3; kind = kind + 1) begin
                begin_window(32'h7000 + kind);
                drive_scan(1'b0, 16'h7000 + kind * 16, 64'h7000000000000000, 8'h70 + kind);
                check64("abort_old_record_present", 1, dut.out_valid);
                if (kind == 0) begin
                    abort_window(1'b1, 1'b0, 1'b0, '0);
                end else if (kind == 1) begin
                    abort_window(1'b0, 1'b1, 1'b0, '0);
                end else begin
                    abort_window(1'b0, 1'b0, 1'b1, 32'h7002);
                end
                check64("abort_old_record_not_retired", 0, dut.stat_retired);
                check64("abort_old_record_flushed", 0, dut.out_valid);
                check64("abort_old_record_slot_cleared", 0, dut.stat_scans);
            end

            for (combination = 1; combination < 8; combination = combination + 1) begin
                begin_window(32'h7800 + combination);
                drive_scan(1'b0, 16'h7800 + combination * 16, 64'h7800000000000000 + combination, 8'h78);
                abort_hold(combination[0], combination[1], combination[2], 32'h7900 + combination, 2);
                check64("held_abort_counters_zero", 0, dut.stat_events);
                check64("held_abort_slot_zero", 0, dut.out_valid);
            end

            begin_window(32'h7f00);
            drive_scan(1'b0, 16'h7f00, 64'h7f00000000000000, 8'h7f);
            idle_cycle(1'b1);
            check64("abort_matrix_final_events", 4, dut.stat_events);
            check64("abort_matrix_final_retired", 1, dut.stat_retired);
            emit_and_finish();
        end
    endtask

    task automatic run_seq2_conditions();
        begin
            initial_reset();

            begin_window(32'h00000021);
            send_ordinary(1'b1, 2'd0, 16'h2100, 64'h2100000000000000, 8'h21, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h2101, 64'h2100000000000001, 8'h22, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h2102, 64'h2100000000000002, 8'h23, 1'b0);
            send_ordinary(1'b1, 2'd3, 16'h2103, 64'h2100000000000003, 8'h24, 1'b0);
            check64("seq2_terminal_valid", 1, dut.out_valid);
            check64("seq2_terminal_exhaust_event", 1, dut.seq_exhaust_event);
            check64("seq2_terminal_armed", 0, dut.armed);
            check64("seq2_terminal_next", 3, dut.next_seq);
            check64("seq2_terminal_exhausted", 1, dut.seq_exhausted);
            check64("seq2_terminal_events", 4, dut.stat_events);
            check64("seq2_terminal_scans", 1, dut.stat_scans);
            idle_cycle(1'b0);
            check64("seq2_exhaust_pulse_cleared", 0, dut.seq_exhaust_event);
            send_ordinary(1'b1, 2'd0, 16'h2199, 64'h2199000000000000, 8'h99, 1'b1);
            check64("seq2_unarmed_event_ignored", 4, dut.stat_events);
            check64("seq2_old_record_retired_after_terminal", 1, dut.stat_retired);
            check64("seq2_next_held", 3, dut.next_seq);
            check64("seq2_armed_held_low", 0, dut.armed);

            begin_window(32'h00000022);
            check64("seq2_rearm_armed", 1, dut.armed);
            check64("seq2_rearm_next_zero", 0, dut.next_seq);
            check64("seq2_rearm_exhaust_clear", 0, dut.seq_exhausted);
            send_ordinary(1'b1, 2'd0, 16'h2200, 64'h2200000000000000, 8'h31, 1'b0);
            send_ordinary(1'b1, 2'd0, 16'h2201, 64'h2200000000000001, 8'h32, 1'b0);
            send_ordinary(1'b1, 2'd0, 16'h2202, 64'h2200000000000002, 8'h33, 1'b0);
            send_ordinary(1'b1, 2'd0, 16'h2203, 64'h2200000000000003, 8'h34, 1'b0);
            check64("seq2_terminal_new_zero_scans", 0, dut.stat_scans);
            check64("seq2_terminal_new_zero_discard", 4, dut.stat_discarded_samples);
            check64("seq2_terminal_new_zero_errors", 3, dut.stat_order_errors);
            check64("seq2_terminal_new_zero_partial", 0, dut.partial_len);
            check64("seq2_terminal_new_zero_order_event", 1, dut.order_error_event);
            check64("seq2_terminal_new_zero_exhaust_event", 1, dut.seq_exhaust_event);

            begin_window(32'h00000023);
            send_ordinary(1'b1, 2'd0, 16'h2300, 64'h2300000000000000, 8'h41, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h2301, 64'h2300000000000001, 8'h42, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h2302, 64'h2300000000000002, 8'h43, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h2303, 64'h2300000000000003, 8'h44, 1'b0);
            check64("seq2_terminal_mismatch_scans", 0, dut.stat_scans);
            check64("seq2_terminal_mismatch_discard", 4, dut.stat_discarded_samples);
            check64("seq2_terminal_mismatch_errors", 1, dut.stat_order_errors);
            check64("seq2_terminal_mismatch_partial", 0, dut.partial_len);

            begin_window(32'h00000024);
            send_ordinary(1'b1, 2'd1, 16'h2400, 64'h2400000000000000, 8'h51, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h2401, 64'h2400000000000001, 8'h52, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h2402, 64'h2400000000000002, 8'h53, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h2403, 64'h2400000000000003, 8'h54, 1'b0);
            check64("seq2_terminal_orphan_scans", 0, dut.stat_scans);
            check64("seq2_terminal_orphan_discard", 4, dut.stat_discarded_samples);
            check64("seq2_terminal_orphan_errors", 4, dut.stat_order_errors);

            begin_window(32'h00000025);
            drive_scan(1'b0, 16'h2500, 64'h2500000000000000, 8'h61);
            idle_cycle(1'b1);
            check64("seq2_final_events", 4, dut.stat_events);
            check64("seq2_final_scans", 1, dut.stat_scans);
            check64("seq2_final_retired", 1, dut.stat_retired);
            check64("seq2_final_armed", 0, dut.armed);
            check64("seq2_final_next", 3, dut.next_seq);
            emit_and_finish();
        end
    endtask

    task automatic run_seq3_conditions();
        begin
            initial_reset();

            begin_window(32'h00000031);
            drive_scan(1'b0, 16'h3100, 64'h3100000000000000, 8'h31);
            check64("seq3_first_fill_scans", 1, dut.stat_scans);
            check64("seq3_first_fill_valid", 1, dut.out_valid);
            check64("seq3_first_fill_first", 0, dut.out_first_seq);
            check64("seq3_first_fill_last", 3, dut.out_last_seq);
            drive_scan(1'b0, 16'h3200, 64'h3200000000000000, 8'h32);
            check64("seq3_terminal_drop_overrun", 1, dut.stat_overruns);
            check64("seq3_terminal_drop_discard", 4, dut.stat_discarded_samples);
            check64("seq3_terminal_drop_scans", 2, dut.stat_scans);
            check64("seq3_terminal_drop_exhaust", 1, dut.seq_exhaust_event);
            check64("seq3_terminal_drop_overrun_event", 1, dut.overrun_event);
            check64("seq3_terminal_drop_armed", 0, dut.armed);
            check64("seq3_terminal_drop_next", 7, dut.next_seq);
            check64("seq3_old_record_still_valid", 1, dut.out_valid);
            check64("seq3_old_record_still_first", 0, dut.out_first_seq);
            idle_cycle(1'b1);
            check64("seq3_old_record_retired", 1, dut.stat_retired);
            check64("seq3_old_record_retired_valid", 0, dut.out_valid);

            begin_window(32'h00000032);
            send_ordinary(1'b1, 2'd0, 16'h3300, 64'h3300000000000000, 8'h41, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h3301, 64'h3300000000000001, 8'h42, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h3302, 64'h3300000000000002, 8'h43, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h3303, 64'h3300000000000003, 8'h44, 1'b0);
            send_ordinary(1'b1, 2'd0, 16'h3304, 64'h3300000000000004, 8'h45, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h3305, 64'h3300000000000005, 8'h46, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h3306, 64'h3300000000000006, 8'h47, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h3307, 64'h3300000000000007, 8'h48, 1'b0);
            check64("seq3_partial_terminal_discard", 8, dut.stat_discarded_samples);
            check64("seq3_partial_terminal_errors", 2, dut.stat_order_errors);
            check64("seq3_partial_terminal_scans", 0, dut.stat_scans);
            check64("seq3_partial_terminal_partial", 0, dut.partial_len);
            check64("seq3_partial_terminal_exhaust", 1, dut.seq_exhaust_event);
            check64("seq3_partial_terminal_order_event", 1, dut.order_error_event);

            begin_window(32'h00000033);
            drive_scan(1'b1, 16'h3400, 64'h3400000000000000, 8'h51);
            check64("seq3_final_events", 4, dut.stat_events);
            check64("seq3_final_scans", 1, dut.stat_scans);
            check64("seq3_final_completion_not_bypassed", 0, dut.stat_retired);
            check64("seq3_final_occupied", 1, dut.out_valid);
            check64("seq3_final_armed", 1, dut.armed);
            check64("seq3_final_next", 4, dut.next_seq);
            idle_cycle(1'b1);
            check64("seq3_final_retired", 1, dut.stat_retired);
            check64("seq3_final_retired_valid", 0, dut.out_valid);
            emit_and_finish();
        end
    endtask

    task automatic run_seq4_conditions();
        int index;
        begin
            initial_reset();
            begin_window(32'h00000041);
            drive_scan(1'b0, 16'h4100, 64'h4100000000000000, 8'h41);
            for (index = 0; index < 11; index = index + 1) begin
                send_ordinary(1'b1, 2'd1, 16'h4200 + index[15:0], 64'h4200000000000000 + index,
                              8'h42 + index[7:0], 1'b0);
            end
            send_ordinary(1'b1, 2'd0, 16'h4300, 64'h4300000000000000, 8'h53, 1'b0);
            check64("seq4_terminal_new_zero_events", 16, dut.stat_events);
            check64("seq4_terminal_new_zero_scans", 1, dut.stat_scans);
            check64("seq4_terminal_new_zero_discard", 12, dut.stat_discarded_samples);
            check64("seq4_terminal_new_zero_errors", 11, dut.stat_order_errors);
            check64("seq4_terminal_new_zero_partial", 0, dut.partial_len);
            check64("seq4_terminal_new_zero_exhaust_event", 1, dut.seq_exhaust_event);
            check64("seq4_terminal_next", 15, dut.next_seq);
            check64("seq4_terminal_armed", 0, dut.armed);
            check64("seq4_terminal_valid_old", 1, dut.out_valid);
            idle_cycle(1'b1);
            begin_window(32'h00000042);
            drive_scan(1'b1, 16'h4400, 64'h4400000000000000, 8'h61);
            check64("seq4_final_events", 4, dut.stat_events);
            check64("seq4_final_scans", 1, dut.stat_scans);
            check64("seq4_final_completion_not_bypassed", 0, dut.stat_retired);
            check64("seq4_final_occupied", 1, dut.out_valid);
            idle_cycle(1'b1);
            check64("seq4_final_retired", 1, dut.stat_retired);
            check64("seq4_final_retired_valid", 0, dut.out_valid);
            emit_and_finish();
        end
    endtask
    task automatic run_stat2_saturation();
        begin
            initial_reset();

            begin_window(32'h00000051);
            drive_partial(3, 16'h5000, 64'h5000000000000000, 8'h50);
            check64("stat2_pre_sat_events", 3, dut.stat_events);
            check64("stat2_pre_sat_partial", 3, dut.partial_len);
            check64("stat2_pre_sat_identity", 3, 4 * (dut.stat_retired + (dut.out_valid ? 1 : 0)) + dut.partial_len + dut.stat_discarded_samples);
            send_ordinary(1'b1, 2'd3, 16'h5003, 64'h5000000000000003, 8'h53, 1'b1);
            drive_scan(1'b1, 16'h5100, 64'h5100000000000000, 8'h51);
            drive_scan(1'b1, 16'h5200, 64'h5200000000000000, 8'h52);
            check64("stat2_pre_overrun_scans", 3, dut.stat_scans);
            check64("stat2_pre_overrun_retired", 2, dut.stat_retired);
            check64("stat2_pre_overrun_identity_scans", 3, dut.stat_retired + (dut.out_valid ? 1 : 0) + dut.stat_overruns);
            check64("stat2_pre_overrun_identity_events", 12, 4 * (dut.stat_retired + (dut.out_valid ? 1 : 0)) + dut.partial_len + dut.stat_discarded_samples);
            drive_scan(1'b1, 16'h5300, 64'h5300000000000000, 8'h53);
            check64("stat2_retired_saturated", 3, dut.stat_retired);
            check64("stat2_scans_saturated", 3, dut.stat_scans);
            check64("stat2_events_saturated", 3, dut.stat_events);
            check64("stat2_retired_exhausted", 1, dut.seq_exhausted);
            check64("stat2_retired_next", 15, dut.next_seq);
            idle_cycle(1'b1);
            check64("stat2_retired_final", 3, dut.stat_retired);

            begin_window(32'h00000052);
            send_ordinary(1'b1, 2'd1, 16'h5400, 64'h5400000000000000, 8'h54, 1'b1);
            send_ordinary(1'b1, 2'd1, 16'h5401, 64'h5400000000000001, 8'h55, 1'b1);
            send_ordinary(1'b1, 2'd1, 16'h5402, 64'h5400000000000002, 8'h56, 1'b1);
            check64("stat2_order_saturated", 3, dut.stat_order_errors);
            check64("stat2_order_discarded_saturated", 3, dut.stat_discarded_samples);
            check64("stat2_order_events_saturated", 3, dut.stat_events);
            drive_scan(1'b1, 16'h5500, 64'h5500000000000000, 8'h57);
            idle_cycle(1'b1);
            send_ordinary(1'b1, 2'd1, 16'h5600, 64'h5600000000000000, 8'h58, 1'b1);
            check64("stat2_order_flow_after_sat", 3, dut.stat_events);
            check64("stat2_order_scans", 1, dut.stat_scans);
            check64("stat2_order_retired", 1, dut.stat_retired);
            check64("stat2_order_errors_final", 3, dut.stat_order_errors);

            begin_window(32'h00000053);
            drive_scan(1'b0, 16'h5700, 64'h5700000000000000, 8'h61);
            drive_scan(1'b0, 16'h5800, 64'h5800000000000000, 8'h62);
            drive_scan(1'b0, 16'h5900, 64'h5900000000000000, 8'h63);
            check64("stat2_pre_overrun2_events_saturated", 3, dut.stat_events);
            check64("stat2_pre_overrun2_scans", 3, dut.stat_scans);
            check64("stat2_pre_overrun2_overruns", 2, dut.stat_overruns);
            check64("stat2_pre_overrun2_discarded_saturated", 3, dut.stat_discarded_samples);
            check64("stat2_pre_overrun2_model_events", 12, m_events);
            check64("stat2_pre_overrun2_model_discarded", 8, m_discarded);
            check64("stat2_pre_overrun2_model_identity_scans", m_scans, m_retired + m_slot_valid + m_overruns);
            check64("stat2_pre_overrun2_model_identity_events", m_events, 4 * (m_retired + m_slot_valid) + m_partial_len + m_discarded);
            drive_scan(1'b0, 16'ha700, 64'ha700000000000000, 8'h71);
            check64("stat2_overrun_saturated", 3, dut.stat_overruns);
            check64("stat2_discard_saturated", 3, dut.stat_discarded_samples);
            check64("stat2_terminal_drop_exhaust", 1, dut.seq_exhaust_event);
            check64("stat2_terminal_drop_occupied", 1, dut.out_valid);
            idle_cycle(1'b1);
            check64("stat2_terminal_old_retired", 1, dut.stat_retired);
            check64("stat2_terminal_final_events", 3, dut.stat_events);
            check64("stat2_terminal_final_scans", 3, dut.stat_scans);
            check64("stat2_terminal_final_exhausted", 1, dut.seq_exhausted);
            emit_and_finish();
        end
    endtask

    task automatic run_stat3_saturation();
        int scan_index;
        begin
            initial_reset();

            begin_window(32'h00000061);
            drive_partial(3, 16'h6100, 64'h6100000000000000, 8'h61);
            check64("stat3_pre_sat_events", 3, dut.stat_events);
            check64("stat3_pre_sat_partial", 3, dut.partial_len);
            send_ordinary(1'b1, 2'd3, 16'h6103, 64'h6100000000000003, 8'h64, 1'b1);
            for (scan_index = 0; scan_index < 7; scan_index = scan_index + 1) begin
                drive_scan(1'b1, 16'h6200 + scan_index * 16, 64'h6200000000000000 + scan_index, 8'h62);
            end
            check64("stat3_retired_saturated", 7, dut.stat_retired);
            check64("stat3_scans_saturated", 7, dut.stat_scans);
            check64("stat3_events_saturated", 7, dut.stat_events);
            check64("stat3_retired_exhausted", 1, dut.seq_exhausted);
            check64("stat3_retired_next", 31, dut.next_seq);
            idle_cycle(1'b1);
            check64("stat3_retired_final", 7, dut.stat_retired);

            begin_window(32'h00000062);
            for (scan_index = 0; scan_index < 7; scan_index = scan_index + 1) begin
                send_ordinary(1'b1, 2'd1, 16'h6300 + scan_index[15:0],
                              64'h6300000000000000 + scan_index, 8'h63 + scan_index[7:0], 1'b1);
            end
            check64("stat3_order_saturated", 7, dut.stat_order_errors);
            check64("stat3_order_discard_saturated", 7, dut.stat_discarded_samples);
            check64("stat3_order_events_saturated", 7, dut.stat_events);
            drive_scan(1'b1, 16'h6400, 64'h6400000000000000, 8'h70);
            idle_cycle(1'b1);
            send_ordinary(1'b1, 2'd1, 16'h6500, 64'h6500000000000000, 8'h71, 1'b1);
            check64("stat3_order_flow_after_sat", 7, dut.stat_events);
            check64("stat3_order_scans", 1, dut.stat_scans);
            check64("stat3_order_retired", 1, dut.stat_retired);
            check64("stat3_order_errors_final", 7, dut.stat_order_errors);

            begin_window(32'h00000063);
            for (scan_index = 0; scan_index < 8; scan_index = scan_index + 1) begin
                drive_scan(1'b0, 16'h6600 + scan_index * 16, 64'h6600000000000000 + scan_index, 8'h72);
            end
            check64("stat3_overrun_saturated", 7, dut.stat_overruns);
            check64("stat3_discard_saturated", 7, dut.stat_discarded_samples);
            check64("stat3_terminal_drop_exhaust", 1, dut.seq_exhaust_event);
            check64("stat3_terminal_drop_occupied", 1, dut.out_valid);
            idle_cycle(1'b1);
            check64("stat3_terminal_old_retired", 1, dut.stat_retired);
            check64("stat3_terminal_final_events", 7, dut.stat_events);
            check64("stat3_terminal_final_scans", 7, dut.stat_scans);
            check64("stat3_terminal_final_exhausted", 1, dut.seq_exhausted);
            emit_and_finish();
        end
    endtask

    task automatic run_tick16_pack();
        begin
            initial_reset();
            begin_window(32'h00000071);
            send_ordinary(1'b1, 2'd0, 16'h0000, 16'h0000, 8'h00, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h0001, 16'h0000, 8'h11, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h7fff, 16'h8000, 8'h22, 1'b0);
            send_ordinary(1'b1, 2'd3, 16'hffff, 16'hffff, 8'h33, 1'b0);
            check64("tick16_valid", 1, dut.out_valid);
            check64("tick16_data", 64'hffff7fff00010000, dut.out_data);
            check64("tick16_ticks", 64'hffff800000000000, dut.out_ticks);
            check64("tick16_quality", 32'h33221100, dut.out_quality);
            idle_cycle(1'b0);
            check64("tick16_stable", 64'hffff800000000000, dut.out_ticks);
            idle_cycle(1'b1);
            check64("tick16_retired", 1, dut.stat_retired);
            emit_and_finish();
        end
    endtask

    task automatic run_tick1_pack();
        begin
            initial_reset();
            begin_window(32'h00000072);
            send_ordinary(1'b1, 2'd0, 16'h0000, 1'b0, 8'h00, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h0001, 1'b1, 8'h11, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h8000, 1'b1, 8'h22, 1'b0);
            send_ordinary(1'b1, 2'd3, 16'hffff, 1'b0, 8'h33, 1'b0);
            check64("tick1_valid", 1, dut.out_valid);
            check64("tick1_data", 64'hffff800000010000, dut.out_data);
            check64("tick1_ticks", 4'b0110, dut.out_ticks);
            check64("tick1_quality", 32'h33221100, dut.out_quality);
            idle_cycle(1'b1);
            check64("tick1_retired", 1, dut.stat_retired);
            emit_and_finish();
        end
    endtask

    task automatic run_mutant_mix();
        begin
            initial_reset();
            begin_window(32'h00000081);
            send_ordinary(1'b1, 2'd0, 16'h8100, 64'h8100000000000000, 8'h10, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h8102, 64'h8100000000000002, 8'h12, 1'b0);
            send_ordinary(1'b1, 2'd1, 16'h8101, 64'h8100000000000001, 8'h11, 1'b0);
            send_ordinary(1'b1, 2'd3, 16'h8103, 64'h8100000000000003, 8'h13, 1'b0);
            check64("mutant_mix_events", 4, dut.stat_events);
            check64("mutant_mix_scans", 0, dut.stat_scans);
            check64("mutant_mix_discarded", 4, dut.stat_discarded_samples);
            check64("mutant_mix_order_errors", 3, dut.stat_order_errors);
            check64("mutant_mix_partial", 0, dut.partial_len);
            check64("mutant_mix_valid", 0, dut.out_valid);
            check64("mutant_mix_next", 4, dut.next_seq);
            emit_and_finish();
        end
    endtask

    task automatic run_mutant_loss();
        begin
            initial_reset();
            begin_window(32'h00000082);
            send_ordinary(1'b1, 2'd0, 16'h8200, 64'h8200000000000000, 8'h20, 1'b0);
            send_ordinary(1'b1, 2'd2, 16'h8202, 64'h8200000000000002, 8'h22, 1'b0);
            check64("mutant_loss_events", 2, dut.stat_events);
            check64("mutant_loss_scans", 0, dut.stat_scans);
            check64("mutant_loss_discarded", 2, dut.stat_discarded_samples);
            check64("mutant_loss_order_errors", 1, dut.stat_order_errors);
            check64("mutant_loss_partial", 0, dut.partial_len);
            check64("mutant_loss_valid", 0, dut.out_valid);
            check64("mutant_loss_next", 2, dut.next_seq);
            emit_and_finish();
        end
    endtask

    task automatic run_seq16_window();
        int event_index;
        logic [1:0] channel;
        begin
            initial_reset();
            begin_window(16'h1600);
            for (event_index = 0; event_index < 65536; event_index = event_index + 1) begin
                channel = event_index[1:0];
                send_ordinary_nocheck(1'b1,
                                      channel,
                                      16'h6000 ^ event_index[15:0],
                                      event_index[15:0],
                                      event_index[7:0],
                                      1'b1);
                if ((event_index == 32766) || (event_index == 32767) ||
                    (event_index == 32768) || (event_index == 65534) ||
                    (event_index == 65535) || ((event_index % 4096) == 4095)) begin
                    compare_model();
                end
            end
            check64("seq16_terminal_armed", 0, dut.armed);
            check64("seq16_terminal_exhausted", 1, dut.seq_exhausted);
            check64("seq16_terminal_next", 65535, dut.next_seq);
            check64("seq16_terminal_exhaust_event", 1, dut.seq_exhaust_event);
            check64("seq16_terminal_valid", 1, dut.out_valid);
            idle_cycle(1'b0);
            check64("seq16_exhaust_pulse_cleared", 0, dut.seq_exhaust_event);
            idle_cycle(1'b1);
            check64("seq16_events", 65536, dut.stat_events);
            check64("seq16_scans", 16384, dut.stat_scans);
            check64("seq16_retired", 16384, dut.stat_retired);
            check64("seq16_discarded", 0, dut.stat_discarded_samples);
            check64("seq16_order_errors", 0, dut.stat_order_errors);
            check64("seq16_overruns", 0, dut.stat_overruns);
            check64("seq16_next_held", 65535, dut.next_seq);
            send_ordinary(1'b1, 2'd0, 16'h6550, 16'h6550, 8'h55, 1'b1);
            check64("seq16_unarmed_after_exhaust", 65536, dut.stat_events);
            emit_and_finish();
        end
    endtask

    task automatic run_random20k();
        int edge_index;
        int rearm_count;
        int abort_count;
        int error_count;
        int stall_count;
        int completion_count;
        int overrun_count;
        int scan_before;
        logic [31:0] random_state;
        logic [31:0] random_value;
        logic [31:0] random_value2;
        logic [TAG_W-1:0] tag_value;
        logic [15:0] data_value;
        logic [TICK_W-1:0] tick_value;
        begin
            initial_reset();
            random_state = 32'h1a2b3c4d;
            rearm_count = 0;
            abort_count = 0;
            error_count = 0;
            stall_count = 0;
            completion_count = 0;
            overrun_count = 0;
            tag_value = '0;
            tag_value[31:0] = 32'h00c0ffee;
            begin_window(tag_value);

            for (edge_index = 0; edge_index < 20000; edge_index = edge_index + 1) begin
                random_value = random_state;
                random_state = {random_state[30:0],
                                random_state[31] ^ random_state[21] ^
                                random_state[1] ^ random_state[0]};
                tag_value = '0;
                tag_value[31:0] = random_value;
                if (random_value[15:6] == 10'd0) begin
                    rearm_count = rearm_count + 1;
                    begin_window(tag_value);
                end else if (random_value[21:12] == 10'd0) begin
                    abort_count = abort_count + 1;
                    if (random_value[0]) begin
                        abort_window(1'b1, 1'b0, 1'b0, tag_value);
                    end else begin
                        abort_window(1'b0, 1'b1, 1'b0, tag_value);
                    end
                end else begin
                    random_value2 = random_state;
                    random_state = {random_state[30:0],
                                    random_state[31] ^ random_state[21] ^
                                    random_state[1] ^ random_state[0]};
                    data_value = random_value[31:16] ^ random_value2[15:0];
                    tick_value = '0;
                    tick_value[31:0] = random_value;
                    if (TICK_W > 32) begin
                        tick_value[63:32] = random_value2;
                    end
                    scan_before = m_scans;
                    if (m_slot_valid && !random_value[4]) begin
                        stall_count = stall_count + 1;
                    end
                    send_ordinary(random_value[3],
                                  random_value[6:5],
                                  data_value,
                                  tick_value,
                                  random_value[23:16] ^ random_value2[7:0],
                                  random_value[4]);
                    if (m_order_error_event) begin
                        error_count = error_count + 1;
                    end
                    if (m_overrun_event) begin
                        overrun_count = overrun_count + 1;
                    end
                    if (m_scans > scan_before) begin
                        completion_count = completion_count + 1;
                    end
                end
            end

            check64("random_edges", 20000, edge_index);
            check64("random_rearm_present", 1, (rearm_count > 0) ? 1 : 0);
            check64("random_abort_present", 1, (abort_count > 0) ? 1 : 0);
            check64("random_order_error_present", 1, (error_count > 0) ? 1 : 0);
            check64("random_stall_present", 1, (stall_count > 0) ? 1 : 0);
            check64("random_completion_present", 1, (completion_count > 0) ? 1 : 0);
            $display("SAMPLE_SCAN_RANDOM edges=20000 seed=00000001a2b3c4d final_state=%08h windows=%0d",
                     random_state, windows);

            begin_window(32'h0000cafe);
            drive_scan(1'b0, 16'hcafe, 64'hcafe000000000000, 8'hca);
            idle_cycle(1'b1);
            check64("random_final_events", 4, dut.stat_events);
            check64("random_final_scans", 1, dut.stat_scans);
            check64("random_final_retired", 1, dut.stat_retired);
            check64("random_final_discarded", 0, dut.stat_discarded_samples);
            check64("random_final_order_errors", 0, dut.stat_order_errors);
            check64("random_final_overruns", 0, dut.stat_overruns);
            check64("random_final_next", 4, dut.next_seq);
            check64("random_final_armed", 1, dut.armed);
            emit_and_finish();
        end
    endtask
endmodule

module tb_sample_scan_capture_guard #(
    parameter int GUARD_SELECT = 0
);
    logic clk;

    always #5 clk = ~clk;

    generate
        case (GUARD_SELECT)
            0: begin
                deepeye_sample_scan_capture #(.SEQ_W(1)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0),
                    .out_valid(), .out_data(), .out_ticks(), .out_quality(),
                    .out_first_seq(), .out_last_seq(), .out_tag(),
                    .armed(), .partial_len(), .next_seq(), .seq_exhausted(),
                    .order_error_event(), .overrun_event(), .seq_exhaust_event(),
                    .stat_events(), .stat_scans(), .stat_retired(),
                    .stat_discarded_samples(), .stat_order_errors(), .stat_overruns());
            end
            1: begin
                deepeye_sample_scan_capture #(.SEQ_W(33)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0),
                    .out_valid(), .out_data(), .out_ticks(), .out_quality(),
                    .out_first_seq(), .out_last_seq(), .out_tag(),
                    .armed(), .partial_len(), .next_seq(), .seq_exhausted(),
                    .order_error_event(), .overrun_event(), .seq_exhaust_event(),
                    .stat_events(), .stat_scans(), .stat_retired(),
                    .stat_discarded_samples(), .stat_order_errors(), .stat_overruns());
            end
            2: begin
                deepeye_sample_scan_capture #(.TICK_W(0)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0),
                    .out_valid(), .out_data(), .out_ticks(), .out_quality(),
                    .out_first_seq(), .out_last_seq(), .out_tag(),
                    .armed(), .partial_len(), .next_seq(), .seq_exhausted(),
                    .order_error_event(), .overrun_event(), .seq_exhaust_event(),
                    .stat_events(), .stat_scans(), .stat_retired(),
                    .stat_discarded_samples(), .stat_order_errors(), .stat_overruns());
            end
            3: begin
                deepeye_sample_scan_capture #(.TICK_W(65)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0),
                    .out_valid(), .out_data(), .out_ticks(), .out_quality(),
                    .out_first_seq(), .out_last_seq(), .out_tag(),
                    .armed(), .partial_len(), .next_seq(), .seq_exhausted(),
                    .order_error_event(), .overrun_event(), .seq_exhaust_event(),
                    .stat_events(), .stat_scans(), .stat_retired(),
                    .stat_discarded_samples(), .stat_order_errors(), .stat_overruns());
            end
            4: begin
                deepeye_sample_scan_capture #(.TAG_W(0)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0),
                    .out_valid(), .out_data(), .out_ticks(), .out_quality(),
                    .out_first_seq(), .out_last_seq(), .out_tag(),
                    .armed(), .partial_len(), .next_seq(), .seq_exhausted(),
                    .order_error_event(), .overrun_event(), .seq_exhaust_event(),
                    .stat_events(), .stat_scans(), .stat_retired(),
                    .stat_discarded_samples(), .stat_order_errors(), .stat_overruns());
            end
            5: begin
                deepeye_sample_scan_capture #(.TAG_W(65)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0),
                    .out_valid(), .out_data(), .out_ticks(), .out_quality(),
                    .out_first_seq(), .out_last_seq(), .out_tag(),
                    .armed(), .partial_len(), .next_seq(), .seq_exhausted(),
                    .order_error_event(), .overrun_event(), .seq_exhaust_event(),
                    .stat_events(), .stat_scans(), .stat_retired(),
                    .stat_discarded_samples(), .stat_order_errors(), .stat_overruns());
            end
            6: begin
                deepeye_sample_scan_capture #(.STAT_W(1)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0),
                    .out_valid(), .out_data(), .out_ticks(), .out_quality(),
                    .out_first_seq(), .out_last_seq(), .out_tag(),
                    .armed(), .partial_len(), .next_seq(), .seq_exhausted(),
                    .order_error_event(), .overrun_event(), .seq_exhaust_event(),
                    .stat_events(), .stat_scans(), .stat_retired(),
                    .stat_discarded_samples(), .stat_order_errors(), .stat_overruns());
            end
            7: begin
                deepeye_sample_scan_capture #(.STAT_W(33)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0),
                    .out_valid(), .out_data(), .out_ticks(), .out_quality(),
                    .out_first_seq(), .out_last_seq(), .out_tag(),
                    .armed(), .partial_len(), .next_seq(), .seq_exhausted(),
                    .order_error_event(), .overrun_event(), .seq_exhaust_event(),
                    .stat_events(), .stat_scans(), .stat_retired(),
                    .stat_discarded_samples(), .stat_order_errors(), .stat_overruns());
            end
            default: begin
                deepeye_sample_scan_capture dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0),
                    .out_valid(), .out_data(), .out_ticks(), .out_quality(),
                    .out_first_seq(), .out_last_seq(), .out_tag(),
                    .armed(), .partial_len(), .next_seq(), .seq_exhausted(),
                    .order_error_event(), .overrun_event(), .seq_exhaust_event(),
                    .stat_events(), .stat_scans(), .stat_retired(),
                    .stat_discarded_samples(), .stat_order_errors(), .stat_overruns());
            end
        endcase
    endgenerate

    initial begin
        clk = 1'b0;
        #30;
        $display("GUARD_CONTROL_ALIVE");
        $finish;
    end

endmodule
