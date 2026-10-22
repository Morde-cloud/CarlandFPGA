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
            end else begin
                $fatal(1, "tb_sample_scan_capture: case failed");
            end
        end
    endtask

    task automatic run_directed();
        logic [63:0] expected_data;
        logic [4*TICK_W-1:0] expected_ticks;
        logic [31:0] expected_quality;
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

            idle_cycle(1'b0);
            idle_cycle(1'b0);
            idle_cycle(1'b0);
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
        end else begin
            $fatal(1, "tb_sample_scan_capture: unknown CASE");
        end
    end

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
                    .out_ready(1'b0));
            end
            1: begin
                deepeye_sample_scan_capture #(.SEQ_W(33)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0));
            end
            2: begin
                deepeye_sample_scan_capture #(.TICK_W(0)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0));
            end
            3: begin
                deepeye_sample_scan_capture #(.TICK_W(65)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0));
            end
            4: begin
                deepeye_sample_scan_capture #(.TAG_W(0)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0));
            end
            5: begin
                deepeye_sample_scan_capture #(.TAG_W(65)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0));
            end
            6: begin
                deepeye_sample_scan_capture #(.STAT_W(1)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0));
            end
            7: begin
                deepeye_sample_scan_capture #(.STAT_W(33)) dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0));
            end
            default: begin
                deepeye_sample_scan_capture dut (
                    .clk(clk), .rst(1'b0), .stop(1'b0), .rearm(1'b0),
                    .rearm_tag('0), .sample_strobe(1'b0), .sample_channel(2'd0),
                    .sample_data(16'd0), .sample_tick('0), .sample_quality(8'd0),
                    .out_ready(1'b0));
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