`timescale 1ns/1ps

module tb_wire_parser;
    logic clk;
    logic rst;
    logic cancel;

    logic       in_valid;
    logic [7:0] in_data;
    logic       out_ready;

    wire        in_ready;
    wire        out_valid;
    wire [7:0]  out_type;
    wire [7:0]  out_epoch;
    wire [15:0] out_seq;
    wire [31:0] out_tick;
    wire [5:0]  out_len;
    wire [255:0] out_payload;
    wire        receiving;
    wire        error_event;
    wire [1:0]  error_code;
    wire [31:0] stat_bytes;
    wire [31:0] stat_frames;
    wire [31:0] stat_retired;
    wire [31:0] stat_version;
    wire [31:0] stat_length;
    wire [31:0] stat_crc;
    wire [31:0] stat_aborted;

    logic       small_rst;
    logic       small_cancel;
    logic       small_in_valid;
    logic [7:0] small_in_data;
    logic       small_out_ready;
    wire        small_in_ready;
    wire        small_out_valid;
    wire [7:0]  small_out_type;
    wire [7:0]  small_out_epoch;
    wire [15:0] small_out_seq;
    wire [31:0] small_out_tick;
    wire [5:0]  small_out_len;
    wire [255:0] small_out_payload;
    wire        small_receiving;
    wire        small_error_event;
    wire [1:0]  small_error_code;
    wire [1:0]  small_stat_bytes;
    wire [1:0]  small_stat_frames;
    wire [1:0]  small_stat_retired;
    wire [1:0]  small_stat_version;
    wire [1:0]  small_stat_length;
    wire [1:0]  small_stat_crc;
    wire [1:0]  small_stat_aborted;

    deepeye_wire_parser #(.STAT_W(32)) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_data(in_data),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_type(out_type),
        .out_epoch(out_epoch),
        .out_seq(out_seq),
        .out_tick(out_tick),
        .out_len(out_len),
        .out_payload(out_payload),
        .receiving(receiving),
        .error_event(error_event),
        .error_code(error_code),
        .stat_bytes(stat_bytes),
        .stat_frames(stat_frames),
        .stat_retired(stat_retired),
        .stat_version(stat_version),
        .stat_length(stat_length),
        .stat_crc(stat_crc),
        .stat_aborted(stat_aborted)
    );

    deepeye_wire_parser #(.STAT_W(2)) dut_small (
        .clk(clk),
        .rst(small_rst),
        .cancel(small_cancel),
        .in_valid(small_in_valid),
        .in_ready(small_in_ready),
        .in_data(small_in_data),
        .out_valid(small_out_valid),
        .out_ready(small_out_ready),
        .out_type(small_out_type),
        .out_epoch(small_out_epoch),
        .out_seq(small_out_seq),
        .out_tick(small_out_tick),
        .out_len(small_out_len),
        .out_payload(small_out_payload),
        .receiving(small_receiving),
        .error_event(small_error_event),
        .error_code(small_error_code),
        .stat_bytes(small_stat_bytes),
        .stat_frames(small_stat_frames),
        .stat_retired(small_stat_retired),
        .stat_version(small_stat_version),
        .stat_length(small_stat_length),
        .stat_crc(small_stat_crc),
        .stat_aborted(small_stat_aborted)
    );

    always #5 clk = ~clk;

    integer checks;
    integer errors;
    integer case_checks;
    integer case_errors_before;
    integer case_number;
    string  current_case;

    logic [7:0] phase_frame [0:21];
    integer     fixture_fd;
    integer     fixture_count;
    integer     fixture_rc;
    string      fixture_path;

    function automatic logic [15:0] crc_ref_byte(
        input logic [15:0] crc_in,
        input logic [7:0]  data_in
    );
        integer bit_index;
        logic [15:0] value;
        begin
            value = crc_in;
            for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1) begin
                if (value[15] ^ data_in[7-bit_index]) begin
                    value = (value << 1) ^ 16'h1021;
                end else begin
                    value = value << 1;
                end
            end
            crc_ref_byte = value;
        end
    endfunction

    function automatic logic [15:0] crc_ref_frame(
        input logic [7:0]   frame_type,
        input logic [7:0]   epoch,
        input logic [15:0]  seq,
        input logic [31:0]  tick,
        input logic [5:0]   length,
        input logic [255:0] payload
    );
        logic [15:0] value;
        integer index;
        begin
            value = 16'hFFFF;
            value = crc_ref_byte(value, 8'h03);
            value = crc_ref_byte(value, frame_type);
            value = crc_ref_byte(value, {2'b00, length});
            value = crc_ref_byte(value, epoch);
            value = crc_ref_byte(value, seq[7:0]);
            value = crc_ref_byte(value, seq[15:8]);
            value = crc_ref_byte(value, tick[7:0]);
            value = crc_ref_byte(value, tick[15:8]);
            value = crc_ref_byte(value, tick[23:16]);
            value = crc_ref_byte(value, tick[31:24]);
            for (index = 0; index < length; index = index + 1) begin
                value = crc_ref_byte(value, payload[8*index +: 8]);
            end
            crc_ref_frame = value;
        end
    endfunction

    task automatic check1(input logic condition, input string label);
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if (condition !== 1'b1) begin
                errors = errors + 1;
                $display("WIRE_PARSER_CHECK_FAIL|%0s|%0s|actual=%b", current_case, label, condition);
            end
        end
    endtask

    task automatic check8(input logic [7:0] actual, input logic [7:0] expected, input string label);
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if (actual !== expected) begin
                errors = errors + 1;
                $display("WIRE_PARSER_CHECK_FAIL|%0s|%0s|actual=%02h|expected=%02h", current_case, label, actual, expected);
            end
        end
    endtask

    task automatic check16(input logic [15:0] actual, input logic [15:0] expected, input string label);
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if (actual !== expected) begin
                errors = errors + 1;
                $display("WIRE_PARSER_CHECK_FAIL|%0s|%0s|actual=%04h|expected=%04h", current_case, label, actual, expected);
            end
        end
    endtask

    task automatic check32(input logic [31:0] actual, input logic [31:0] expected, input string label);
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if (actual !== expected) begin
                errors = errors + 1;
                $display("WIRE_PARSER_CHECK_FAIL|%0s|%0s|actual=%08h|expected=%08h", current_case, label, actual, expected);
            end
        end
    endtask

    task automatic check256(input logic [255:0] actual, input logic [255:0] expected, input string label);
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if (actual !== expected) begin
                errors = errors + 1;
                $display("WIRE_PARSER_CHECK_FAIL|%0s|%0s|actual=%064h|expected=%064h", current_case, label, actual, expected);
            end
        end
    endtask

    task automatic begin_case(input string name);
        begin
            case_number = case_number + 1;
            current_case = name;
            case_checks = 0;
            case_errors_before = errors;
            $display("WIRE_PARSER_CASE_BEGIN|%0d|%0s", case_number, name);
        end
    endtask

    task automatic end_case;
        begin
            $display("WIRE_PARSER_CASE_CHECKS|%0d|%0s|%0d", case_number, current_case, case_checks);
            if (errors == case_errors_before) begin
                $display("WIRE_PARSER_CASE_END|%0d|%0s|PASS", case_number, current_case);
            end else begin
                $display("WIRE_PARSER_CASE_END|%0d|%0s|FAIL", case_number, current_case);
            end
        end
    endtask

    task automatic do_reset;
        begin
            @(negedge clk);
            rst = 1'b1;
            cancel = 1'b0;
            in_valid = 1'b0;
            in_data = 8'h00;
            out_ready = 1'b0;
            @(posedge clk); #1;
            @(negedge clk);
            rst = 1'b0;
            #1;
        end
    endtask

    task automatic idle_cycles(input integer count);
        integer index;
        begin
            for (index = 0; index < count; index = index + 1) begin
                @(posedge clk); #1;
            end
        end
    endtask

    task automatic send_byte(input logic [7:0] value);
        integer wait_cycles;
        begin
            wait_cycles = 0;
            @(negedge clk);
            in_data = value;
            in_valid = 1'b1;
            while (in_ready !== 1'b1) begin
                @(negedge clk);
                wait_cycles = wait_cycles + 1;
                if (wait_cycles > 100) begin
                    check1(1'b0, "send_byte.in_ready_timeout");
                    disable send_byte;
                end
            end
            @(posedge clk); #1;
            in_valid = 1'b0;
            in_data = 8'h00;
        end
    endtask

    task automatic cancel_pulse;
        begin
            @(negedge clk);
            cancel = 1'b1; #1;
            @(posedge clk); #1;
            @(negedge clk);
            cancel = 1'b0;
            #1;
        end
    endtask

    task automatic pop_output;
        begin
            @(negedge clk);
            out_ready = 1'b1;
            @(posedge clk); #1;
            @(negedge clk);
            out_ready = 1'b0;
            #1;
        end
    endtask

    task automatic send_frame_body(
        input logic [7:0]   frame_type,
        input logic [7:0]   epoch,
        input logic [15:0]  seq,
        input logic [31:0]  tick,
        input logic [5:0]   length,
        input logic [255:0] payload,
        input logic [15:0]  forced_crc,
        input logic         use_forced_crc
    );
        logic [15:0] computed_crc;
        logic [15:0] wire_crc;
        integer index;
        begin
            computed_crc = crc_ref_frame(frame_type, epoch, seq, tick, length, payload);
            send_byte(8'h03);
            send_byte(frame_type);
            send_byte({2'b00, length});
            send_byte(epoch);
            send_byte(seq[7:0]);
            send_byte(seq[15:8]);
            send_byte(tick[7:0]);
            send_byte(tick[15:8]);
            send_byte(tick[23:16]);
            send_byte(tick[31:24]);
            for (index = 0; index < length; index = index + 1) begin
                send_byte(payload[8*index +: 8]);
            end
            if (use_forced_crc) begin
                wire_crc = forced_crc;
            end else begin
                wire_crc = computed_crc;
            end
            send_byte(wire_crc[7:0]);
            check1(!out_valid, "frame.no_premature_output");
            check1(receiving, "frame.receiving_before_crc_high");
            check1(in_ready, "frame.ready_before_crc_high");
            send_byte(wire_crc[15:8]);
        end
    endtask

    task automatic send_frame(
        input logic [7:0]   frame_type,
        input logic [7:0]   epoch,
        input logic [15:0]  seq,
        input logic [31:0]  tick,
        input logic [5:0]   length,
        input logic [255:0] payload
    );
        begin
            send_byte(8'hA5);
            send_byte(8'h5A);
            send_frame_body(frame_type, epoch, seq, tick, length, payload, 16'h0000, 1'b0);
        end
    endtask

    task automatic send_frame_forced_crc(
        input logic [7:0]   frame_type,
        input logic [7:0]   epoch,
        input logic [15:0]  seq,
        input logic [31:0]  tick,
        input logic [5:0]   length,
        input logic [255:0] payload,
        input logic [15:0]  forced_crc
    );
        begin
            send_byte(8'hA5);
            send_byte(8'h5A);
            send_frame_body(frame_type, epoch, seq, tick, length, payload, forced_crc, 1'b1);
        end
    endtask

    task automatic expect_complete(
        input logic [7:0]   frame_type,
        input logic [7:0]   epoch,
        input logic [15:0]  seq,
        input logic [31:0]  tick,
        input logic [5:0]   length,
        input logic [255:0] payload
    );
        begin
            check1(out_valid, "complete.out_valid");
            check8(out_type, frame_type, "complete.type");
            check8(out_epoch, epoch, "complete.epoch");
            check16(out_seq, seq, "complete.seq");
            check32(out_tick, tick, "complete.tick");
            check8({2'b00, out_len}, {2'b00, length}, "complete.len");
            check256(out_payload, payload, "complete.payload");
            check1(!receiving, "complete.receiving_low");
            check1(!in_ready, "complete.in_ready_low");
        end
    endtask

    task automatic check_main_stats(
        input integer expected_bytes,
        input integer expected_frames,
        input integer expected_retired,
        input integer expected_version,
        input integer expected_length,
        input integer expected_crc,
        input integer expected_aborted
    );
        begin
            check32(stat_bytes, expected_bytes, "stats.bytes");
            check32(stat_frames, expected_frames, "stats.frames");
            check32(stat_retired, expected_retired, "stats.retired");
            check32(stat_version, expected_version, "stats.version");
            check32(stat_length, expected_length, "stats.length");
            check32(stat_crc, expected_crc, "stats.crc");
            check32(stat_aborted, expected_aborted, "stats.aborted");
        end
    endtask

    task automatic check_status_snapshot(
        input string  label,
        input logic   expected_receiving,
        input logic   expected_error_event,
        input logic [1:0] expected_error_code,
        input integer expected_bytes,
        input integer expected_frames,
        input integer expected_retired,
        input integer expected_version,
        input integer expected_length,
        input integer expected_crc,
        input integer expected_aborted,
        input logic   expected_in_ready,
        input logic   expected_out_valid
    );
        begin
            check1(receiving === expected_receiving, $sformatf("%s.receiving", label));
            check1(error_event === expected_error_event, $sformatf("%s.error_event", label));
            check8({6'b000000, error_code}, {6'b000000, expected_error_code}, $sformatf("%s.error_code", label));
            check32(stat_bytes, expected_bytes, $sformatf("%s.stat_bytes", label));
            check32(stat_frames, expected_frames, $sformatf("%s.stat_frames", label));
            check32(stat_retired, expected_retired, $sformatf("%s.stat_retired", label));
            check32(stat_version, expected_version, $sformatf("%s.stat_version", label));
            check32(stat_length, expected_length, $sformatf("%s.stat_length", label));
            check32(stat_crc, expected_crc, $sformatf("%s.stat_crc", label));
            check32(stat_aborted, expected_aborted, $sformatf("%s.stat_aborted", label));
            check1(in_ready === expected_in_ready, $sformatf("%s.in_ready", label));
            check1(out_valid === expected_out_valid, $sformatf("%s.out_valid", label));
        end
    endtask

    task automatic small_do_reset;
        begin
            @(negedge clk);
            small_rst = 1'b1;
            small_cancel = 1'b0;
            small_in_valid = 1'b0;
            small_in_data = 8'h00;
            small_out_ready = 1'b0;
            @(posedge clk); #1;
            @(negedge clk);
            small_rst = 1'b0;
            #1;
        end
    endtask

    task automatic small_send_byte(input logic [7:0] value);
        integer wait_cycles;
        begin
            wait_cycles = 0;
            @(negedge clk);
            small_in_data = value;
            small_in_valid = 1'b1;
            while (small_in_ready !== 1'b1) begin
                @(negedge clk);
                wait_cycles = wait_cycles + 1;
                if (wait_cycles > 100) begin
                    check1(1'b0, "small.send.in_ready_timeout");
                    disable small_send_byte;
                end
            end
            @(posedge clk); #1;
            small_in_valid = 1'b0;
            small_in_data = 8'h00;
        end
    endtask

    task automatic small_send_len0_frame(
        input logic [7:0]  frame_type,
        input logic [7:0]  epoch,
        input logic [15:0] seq,
        input logic [31:0] tick,
        input logic        corrupt_crc
    );
        logic [15:0] good_crc;
        logic [15:0] sent_crc;
        begin
            good_crc = crc_ref_frame(frame_type, epoch, seq, tick, 6'd0, 256'h0);
            if (corrupt_crc) begin
                sent_crc = good_crc ^ 16'h0001;
            end else begin
                sent_crc = good_crc;
            end
            small_send_byte(8'hA5);
            small_send_byte(8'h5A);
            small_send_byte(8'h03);
            small_send_byte(frame_type);
            small_send_byte(8'h00);
            small_send_byte(epoch);
            small_send_byte(seq[7:0]);
            small_send_byte(seq[15:8]);
            small_send_byte(tick[7:0]);
            small_send_byte(tick[15:8]);
            small_send_byte(tick[23:16]);
            small_send_byte(tick[31:24]);
            small_send_byte(sent_crc[7:0]);
            small_send_byte(sent_crc[15:8]);
        end
    endtask

    task automatic small_pop;
        begin
            @(negedge clk);
            small_out_ready = 1'b1;
            @(posedge clk); #1;
            @(negedge clk);
            small_out_ready = 1'b0;
            #1;
        end
    endtask

    task automatic small_cancel_partial;
        begin
            small_send_byte(8'hA5);
            @(negedge clk);
            small_cancel = 1'b1;
            @(posedge clk); #1;
            @(negedge clk);
            small_cancel = 1'b0;
            #1;
        end
    endtask

    integer i;
    integer j;
    integer cut;
    integer byte_index;
    integer expected_bytes;
    integer expected_frames;
    integer remaining_chunks;
    logic [255:0] payload_work;
    logic [15:0]  crc_work;
    logic [15:0]  crc_forced;
    logic [15:0]  crc_forced_two;
    integer fixture_len_i;
    logic [7:0] fixture_type;
    logic [7:0] fixture_epoch;
    logic [15:0] fixture_seq;
    logic [31:0] fixture_tick;
    logic [255:0] fixture_payload;
    logic [15:0] fixture_crc;

    initial begin
        clk = 1'b0;
        rst = 1'b1;
        cancel = 1'b0;
        in_valid = 1'b0;
        in_data = 8'h00;
        out_ready = 1'b0;
        small_rst = 1'b0;
        small_cancel = 1'b0;
        small_in_valid = 1'b0;
        small_in_data = 8'h00;
        small_out_ready = 1'b0;

        checks = 0;
        errors = 0;
        case_checks = 0;
        case_errors_before = 0;
        case_number = 0;
        current_case = "startup";

        repeat (2) @(posedge clk);
        #1;

        // ------------------------------------------------------------------
        begin_case("reset_and_receiving");
        do_reset();
        check1(in_ready, "reset.in_ready");
        check1(!out_valid, "reset.out_valid_low");
        check1(!receiving, "reset.receiving_low");
        check1(!error_event, "reset.error_event_low");
        check8({6'b000000, error_code}, 8'h00, "reset.error_code_zero");
        check256(out_payload, 256'h0, "reset.payload_zero");
        check_main_stats(0, 0, 0, 0, 0, 0, 0);
        cancel_pulse();
        check1(in_ready, "reset.empty_cancel_ready");
        check32(stat_aborted, 0, "reset.empty_cancel_not_counted");

        send_byte(8'h00);
        check1(!receiving, "noise.no_partial");
        check32(stat_bytes, 1, "noise.byte_count");
        send_byte(8'hA5);
        check1(receiving, "prefix.a5_receiving");
        send_byte(8'hA5);
        check1(receiving, "prefix.a5_retained");
        send_byte(8'h00);
        check1(!receiving, "prefix.non5a_returns_search");
        check1(!out_valid, "prefix.no_output");
        send_byte(8'hA5);
        send_byte(8'hA5);
        send_byte(8'hA5);
        send_byte(8'h5A);
        check1(receiving, "prefix.multi_a5_then_5a");
        check_main_stats(8, 0, 0, 0, 0, 0, 0);
        cancel_pulse();
        check1(!receiving, "cancel.prefix_cleared");
        check_main_stats(8, 0, 0, 0, 0, 0, 1);
        end_case();

        // ------------------------------------------------------------------
        begin_case("lengths_0_32");
        do_reset();
        for (i = 0; i <= 32; i = i + 1) begin
            payload_work = 256'h0;
            for (j = 0; j < i; j = j + 1) begin
                payload_work[8*j +: 8] = 8'h80 ^ ((j * 7 + i) & 8'hFF);
            end
            send_frame(8'h10 + i[7:0], i[7:0], 16'h1200 + i[15:0], 32'h89AB_CD00 + i[31:0], i[5:0], payload_work);
            expect_complete(8'h10 + i[7:0], i[7:0], 16'h1200 + i[15:0], 32'h89AB_CD00 + i[31:0], i[5:0], payload_work);
            check32(stat_frames, i + 1, "length.frames_progress");
            pop_output();
            check1(!out_valid, "length.pop_clears_valid");
            check1(in_ready, "length.pop_restores_ready");
            check32(stat_retired, i + 1, "length.retired_progress");
        end
        check_main_stats(990, 33, 33, 0, 0, 0, 0);
        end_case();

        // ------------------------------------------------------------------
        begin_case("all_256_byte_values");
        do_reset();
        for (i = 0; i < 8; i = i + 1) begin
            payload_work = 256'h0;
            for (j = 0; j < 32; j = j + 1) begin
                payload_work[8*j +: 8] = 8'((i * 32) + j);
            end
            send_frame(8'h30 + i[7:0], 8'h70 + i[7:0], 16'hA500 + i[15:0], 32'h0102_0300 + i[31:0], 6'd32, payload_work);
            expect_complete(8'h30 + i[7:0], 8'h70 + i[7:0], 16'hA500 + i[15:0], 32'h0102_0300 + i[31:0], 6'd32, payload_work);
            pop_output();
            check1(!out_valid, "allbytes.pop_low");
            check1(in_ready, "allbytes.ready_after_pop");
        end
        check_main_stats(368, 8, 8, 0, 0, 0, 0);
        end_case();

        // ------------------------------------------------------------------
        begin_case("metadata_endian_and_maxima");
        do_reset();
        payload_work = 256'h0;
        for (j = 0; j < 32; j = j + 1) begin
            payload_work[8*j +: 8] = 8'hF0 + j[7:0];
        end
        send_frame(8'hFF, 8'hFF, 16'hFFFF, 32'hFFFF_FFFF, 6'd32, payload_work);
        expect_complete(8'hFF, 8'hFF, 16'hFFFF, 32'hFFFF_FFFF, 6'd32, payload_work);
        pop_output();
        send_frame(8'h00, 8'h00, 16'h0000, 32'h0000_0000, 6'd0, 256'h0);
        expect_complete(8'h00, 8'h00, 16'h0000, 32'h0000_0000, 6'd0, 256'h0);
        pop_output();
        check_main_stats(60, 2, 2, 0, 0, 0, 0);
        end_case();

        // ------------------------------------------------------------------
        begin_case("stdlib_crc_vectors");
        do_reset();
        fixture_count = 0;
        fixture_path = "UNSET";
        if (!$value$plusargs("FIXTURES=%s", fixture_path)) begin
            check1(1'b0, "fixtures.plusarg_present");
        end else begin
            check1(1'b1, "fixtures.plusarg_present");
            fixture_fd = $fopen(fixture_path, "r");
            check1(fixture_fd != 0, "fixtures.open");
            if (fixture_fd != 0) begin
                fixture_rc = $fscanf(fixture_fd, "%d\n", fixture_count);
                check1(fixture_rc == 1, "fixtures.count_read");
                check1(fixture_count >= 33, "fixtures.count_at_least_33");
                expected_bytes = 0;
                for (i = 0; i < fixture_count; i = i + 1) begin
                    payload_work = 256'h0;
                    fixture_len_i = 0;
                    fixture_type = 8'h00;
                    fixture_epoch = 8'h00;
                    fixture_seq = 16'h0000;
                    fixture_tick = 32'h0000_0000;
                    fixture_crc = 16'h0000;
                    fixture_rc = $fscanf(
                        fixture_fd,
                        "%d %h %h %h %h %h %h\n",
                        fixture_len_i,
                        fixture_type,
                        fixture_epoch,
                        fixture_seq,
                        fixture_tick,
                        payload_work,
                        fixture_crc
                    );
                    check1(fixture_rc == 7, "fixtures.record_read");
                    check1((fixture_len_i >= 0) && (fixture_len_i <= 32), "fixtures.length_range");
                    send_frame_forced_crc(
                        fixture_type,
                        fixture_epoch,
                        fixture_seq,
                        fixture_tick,
                        fixture_len_i[5:0],
                        payload_work,
                        fixture_crc
                    );
                    expect_complete(
                        fixture_type,
                        fixture_epoch,
                        fixture_seq,
                        fixture_tick,
                        fixture_len_i[5:0],
                        payload_work
                    );
                    pop_output();
                    expected_bytes = expected_bytes + 14 + fixture_len_i;
                end
                $fclose(fixture_fd);
                check32(stat_bytes, expected_bytes, "fixtures.bytes");
                check32(stat_frames, fixture_count, "fixtures.frames");
                check32(stat_retired, fixture_count, "fixtures.retired");
                check32(stat_version, 0, "fixtures.version_zero");
                check32(stat_length, 0, "fixtures.length_zero");
                check32(stat_crc, 0, "fixtures.crc_zero");
                check32(stat_aborted, 0, "fixtures.aborted_zero");
            end
        end
        end_case();

        // ------------------------------------------------------------------
        begin_case("noise_prefix_resync");
        do_reset();
        send_byte(8'h00);
        send_byte(8'h5A);
        send_byte(8'h11);
        send_byte(8'hA5);
        check1(receiving, "noise.a5_partial");
        send_byte(8'hA5);
        check1(receiving, "noise.a5_retained");
        send_byte(8'h00);
        check1(!receiving, "noise.other_clears_prefix");
        send_byte(8'hA5);
        send_byte(8'hA5);
        send_byte(8'hA5);
        send_byte(8'h5A);
        check1(receiving, "noise.multi_prefix_entered_version");
        cancel_pulse();
        check32(stat_aborted, 1, "noise.cancel_prefix");
        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h04);
        check1(error_event, "noise.version_error_event");
        check8({6'b000000, error_code}, 8'h01, "noise.version_error_code");
        check1(!receiving, "noise.version_error_no_partial");
        idle_cycles(1);
        check1(!error_event, "noise.version_error_one_cycle");
        check8({6'b000000, error_code}, 8'h00, "noise.error_code_cleared");
        payload_work = 256'h0011_2233_4455_6677;
        send_frame(8'h42, 8'h43, 16'hA55A, 32'h89AB_CDEF, 6'd8, payload_work);
        expect_complete(8'h42, 8'h43, 16'hA55A, 32'h89AB_CDEF, 6'd8, payload_work);
        pop_output();
        check_main_stats(35, 1, 1, 1, 0, 0, 1);
        end_case();

        // ------------------------------------------------------------------
        begin_case("truncation_no_timeout");
        do_reset();
        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h03);
        send_byte(8'h20);
        send_byte(8'h08);
        send_byte(8'h01);
        send_byte(8'h02);
        send_byte(8'h03);
        check1(receiving, "trunc.partial");
        check1(!out_valid, "trunc.no_partial_output");
        idle_cycles(20);
        check1(receiving, "trunc.remains_partial_without_timeout");
        check32(stat_bytes, 8, "trunc.no_phantom_bytes");
        check32(stat_frames, 0, "trunc.no_phantom_frame");
        cancel_pulse();
        check1(!receiving, "trunc.cancel_clears");
        check32(stat_aborted, 1, "trunc.cancel_count");
        payload_work = 256'hA5A5_5A5A_0303_0404;
        send_frame(8'h44, 8'h45, 16'h1234, 32'h5566_7788, 6'd8, payload_work);
        expect_complete(8'h44, 8'h45, 16'h1234, 32'h5566_7788, 6'd8, payload_work);
        pop_output();
        check_main_stats(30, 1, 1, 0, 0, 0, 1);
        end_case();

        // ------------------------------------------------------------------
        begin_case("corrupt_version");
        do_reset();
        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h02);
        check1(error_event, "version.error_pulse");
        check8({6'b000000, error_code}, 8'h01, "version.error_code");
        check1(!receiving, "version.non_a5_search");
        check32(stat_version, 1, "version.count_one");
        idle_cycles(1);
        check1(!error_event, "version.pulse_clears");
        check8({6'b000000, error_code}, 8'h00, "version.code_clears");

        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'hA5);
        check1(error_event, "version.a5.error_pulse");
        check1(receiving, "version.a5.restarts_prefix");
        send_byte(8'h5A);
        check1(receiving, "version.a5.version_wait");
        payload_work = 256'h0011_2233;
        send_frame_body(8'h51, 8'h52, 16'hA55A, 32'h0102_0304, 6'd4, payload_work, 16'h0000, 1'b0);
        expect_complete(8'h51, 8'h52, 16'hA55A, 32'h0102_0304, 6'd4, payload_work);
        pop_output();
        check_main_stats(23, 1, 1, 2, 0, 0, 0);
        end_case();

        // ------------------------------------------------------------------
        begin_case("corrupt_length");
        do_reset();
        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h03);
        send_byte(8'hAA);
        send_byte(8'h21);
        check1(error_event, "length.error_pulse");
        check8({6'b000000, error_code}, 8'h02, "length.error_code");
        check1(!receiving, "length.non_a5_search");
        check32(stat_length, 1, "length.count_one");
        idle_cycles(1);
        check1(!error_event, "length.pulse_clears");

        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h03);
        send_byte(8'hAA);
        send_byte(8'hA5);
        check1(error_event, "length.a5.error_pulse");
        check1(receiving, "length.a5.restarts_prefix");
        send_byte(8'h5A);
        payload_work = 256'h1234_5678;
        send_frame_body(8'h61, 8'h62, 16'h3456, 32'h789A_BCDE, 6'd4, payload_work, 16'h0000, 1'b0);
        expect_complete(8'h61, 8'h62, 16'h3456, 32'h789A_BCDE, 6'd4, payload_work);
        pop_output();
        check_main_stats(27, 1, 1, 0, 2, 0, 0);
        end_case();

        // ------------------------------------------------------------------
        begin_case("corrupt_crc_no_rescan");
        do_reset();
        payload_work = 256'h0;
        payload_work[7:0] = 8'hA5;
        payload_work[15:8] = 8'h5A;
        payload_work[23:16] = 8'h03;
        payload_work[31:24] = 8'hFF;
        crc_work = crc_ref_frame(8'h71, 8'h72, 16'h0102, 32'h0304_0506, 6'd4, payload_work);
        crc_forced = {8'h00, crc_work[7:0]};
        if (crc_forced == crc_work) begin
            crc_forced = {8'h01, crc_work[7:0]};
        end
        send_frame_forced_crc(8'h71, 8'h72, 16'h0102, 32'h0304_0506, 6'd4, payload_work, crc_forced);
        check1(error_event, "crc.error_pulse");
        check8({6'b000000, error_code}, 8'h03, "crc.error_code");
        check1(!receiving, "crc.non_a5_search");
        check1(!out_valid, "crc.no_output_on_mismatch");
        check32(stat_crc, 1, "crc.count_one");
        send_byte(8'h5A);
        check1(!out_valid, "crc.no_buffered_rescan");
        check32(stat_frames, 0, "crc.no_buffered_frame");
        check32(stat_bytes, 19, "crc.no_phantom_bytes");

        payload_work = 256'h0;
        payload_work[7:0] = 8'h10;
        payload_work[15:8] = 8'h20;
        crc_work = crc_ref_frame(8'h73, 8'h74, 16'h1111, 32'h2222_3333, 6'd4, payload_work);
        crc_forced = {8'hA5, crc_work[7:0] ^ 8'h01};
        send_frame_forced_crc(8'h73, 8'h74, 16'h1111, 32'h2222_3333, 6'd4, payload_work, crc_forced);
        check1(error_event, "crc.a5.error_pulse");
        check1(receiving, "crc.a5.restarts_prefix");
        send_byte(8'h5A);
        payload_work = 256'h4433_2211;
        send_frame_body(8'h75, 8'h76, 16'h5544, 32'h7766_5588, 6'd4, payload_work, 16'h0000, 1'b0);
        expect_complete(8'h75, 8'h76, 16'h5544, 32'h7766_5588, 6'd4, payload_work);
        pop_output();

        payload_work = 256'h9988_7766_5544;
        send_frame(8'h77, 8'h78, 16'hA0A1, 32'hB0B1_B2B3, 6'd8, payload_work);
        expect_complete(8'h77, 8'h78, 16'hA0A1, 32'hB0B1_B2B3, 6'd8, payload_work);
        pop_output();
        check_main_stats(76, 2, 2, 0, 0, 2, 0);
        end_case();

        // ------------------------------------------------------------------
        begin_case("output_stall_input_hold");
        do_reset();
        payload_work = 256'hDEAD_BEEF_0123_4567_89AB_CDEF_1020_3040_5060_7080_90A0_B0C0_D0E0_F001_0203_0405;
        send_frame(8'h80, 8'h81, 16'hA1B2, 32'hC3D4_E5F6, 6'd32, payload_work);
        expect_complete(8'h80, 8'h81, 16'hA1B2, 32'hC3D4_E5F6, 6'd32, payload_work);
        check32(stat_frames, 1, "stall.frames_one");
        check32(stat_retired, 0, "stall.not_retired");
        check32(stat_bytes, 46, "stall.bytes_before");

        @(negedge clk);
        in_valid = 1'b1;
        in_data = 8'hA5;
        for (i = 0; i < 5; i = i + 1) begin
            @(posedge clk); #1;
            check1(out_valid, "stall.valid_stable");
            check8(out_type, 8'h80, "stall.type_stable");
            check8(out_epoch, 8'h81, "stall.epoch_stable");
            check16(out_seq, 16'hA1B2, "stall.seq_stable");
            check32(out_tick, 32'hC3D4_E5F6, "stall.tick_stable");
            check8({2'b00, out_len}, 8'h20, "stall.len_stable");
            check256(out_payload, payload_work, "stall.payload_stable");
            check1(!in_ready, "stall.in_ready_low");
            check1(!receiving, "stall.receiving_low");
            check32(stat_bytes, 46, "stall.no_input_sampled");
            check32(stat_frames, 1, "stall.frames_stable");
            check32(stat_retired, 0, "stall.retired_stable");
        end
        in_valid = 1'b0;
        in_data = 8'h00;
        pop_output();
        check1(!out_valid, "stall.pop_low");
        check1(in_ready, "stall.pop_ready");
        check32(stat_retired, 1, "stall.retired_one");
        check_main_stats(46, 1, 1, 0, 0, 0, 0);
        end_case();

        // ------------------------------------------------------------------
        begin_case("retire_edge_no_credit");
        do_reset();
        payload_work = 256'h0;
        for (j = 0; j < 8; j = j + 1) begin
            payload_work[8*j +: 8] = 8'h90 + j[7:0];
        end
        send_frame(8'h82, 8'h83, 16'hB2C3, 32'hD4E5_F607, 6'd8, payload_work);
        expect_complete(8'h82, 8'h83, 16'hB2C3, 32'hD4E5_F607, 6'd8, payload_work);
        check32(stat_bytes, 22, "retire.bytes_before");

        @(negedge clk);
        in_valid = 1'b1;
        in_data = 8'hA5;
        out_ready = 1'b1;
        check1(!in_ready, "retire.pre_edge_no_credit");
        @(posedge clk); #1;
        check1(!out_valid, "retire.slot_cleared");
        check32(stat_retired, 1, "retire.retired_once");
        check32(stat_bytes, 22, "retire.no_same_edge_accept");
        check1(!receiving, "retire.no_same_edge_partial");
        check1(in_ready, "retire.ready_after_edge");
        @(posedge clk); #1;
        check32(stat_bytes, 23, "retire.next_edge_accept");
        check1(receiving, "retire.next_edge_prefix");
        in_valid = 1'b0;
        in_data = 8'h00;
        out_ready = 1'b0;
        cancel_pulse();
        check_main_stats(23, 1, 1, 0, 0, 0, 1);
        end_case();

        // ------------------------------------------------------------------
        begin_case("zero_tail_reuse");
        do_reset();
        payload_work = {256{1'b1}};
        send_frame(8'h84, 8'h85, 16'hC3D4, 32'hE5F6_0718, 6'd32, payload_work);
        expect_complete(8'h84, 8'h85, 16'hC3D4, 32'hE5F6_0718, 6'd32, payload_work);
        pop_output();
        send_frame(8'h86, 8'h87, 16'hD4E5, 32'hF607_1829, 6'd0, 256'h0);
        expect_complete(8'h86, 8'h87, 16'hD4E5, 32'hF607_1829, 6'd0, 256'h0);
        pop_output();
        payload_work = 256'h0;
        for (j = 0; j < 5; j = j + 1) begin
            payload_work[8*j +: 8] = 8'h11 + j[7:0];
        end
        send_frame(8'h88, 8'h89, 16'hE5F6, 32'h0718_293A, 6'd5, payload_work);
        expect_complete(8'h88, 8'h89, 16'hE5F6, 32'h0718_293A, 6'd5, payload_work);
        pop_output();
        check_main_stats(79, 3, 3, 0, 0, 0, 0);
        end_case();

        // ------------------------------------------------------------------
        begin_case("cancel_each_phase");
        phase_frame[0] = 8'hA5;
        phase_frame[1] = 8'h5A;
        phase_frame[2] = 8'h03;
        phase_frame[3] = 8'h95;
        phase_frame[4] = 8'h08;
        phase_frame[5] = 8'h96;
        phase_frame[6] = 8'h34;
        phase_frame[7] = 8'h12;
        phase_frame[8] = 8'h78;
        phase_frame[9] = 8'h56;
        phase_frame[10] = 8'h34;
        phase_frame[11] = 8'h12;
        payload_work = 256'h0;
        for (j = 0; j < 8; j = j + 1) begin
            phase_frame[12+j] = 8'hA0 + j[7:0];
            payload_work[8*j +: 8] = 8'hA0 + j[7:0];
        end
        crc_work = crc_ref_frame(8'h95, 8'h96, 16'h1234, 32'h1234_5678, 6'd8, payload_work);
        phase_frame[20] = crc_work[7:0];
        phase_frame[21] = crc_work[15:8];
        for (cut = 1; cut <= 22; cut = cut + 1) begin
            do_reset();
            for (byte_index = 0; byte_index < cut; byte_index = byte_index + 1) begin
                send_byte(phase_frame[byte_index]);
            end
            if (cut == 22) begin
                check1(out_valid, "cancel22.slot_pending");
                check1(!receiving, "cancel22.receiving_low");
                check1(!in_ready, "cancel22.ready_low");
            end else begin
                check1(receiving, "cancel.partial_receiving");
                check1(!out_valid, "cancel.partial_no_output");
                check1(in_ready, "cancel.partial_ready");
            end
            @(negedge clk);
            cancel = 1'b1;
            in_valid = 1'b1;
            in_data = 8'hAA;
            out_ready = 1'b1;
            #1;
            check1(!out_valid, "cancel.aborts_valid");
            check1((cut == 22) ? !receiving : receiving, "cancel.preserves_receiving_until_edge");
            check1(!in_ready, "cancel.aborts_ready");
            check1(!error_event, "cancel.no_error");
            @(posedge clk); #1;
            check32(stat_bytes, cut, "cancel.no_abort_sample");
            check32(stat_frames, (cut == 22) ? 1 : 0, "cancel.frames_preserved");
            check32(stat_retired, 0, "cancel.no_retire");
            check32(stat_aborted, 1, "cancel.abort_once");
            check8({2'b00, out_len}, 8'h00, "cancel.len_cleared");
            check256(out_payload, 256'h0, "cancel.payload_cleared");
            repeat (2) begin
                @(posedge clk); #1;
                check32(stat_aborted, 1, "cancel.held_no_recount");
                check32(stat_retired, 0, "cancel.held_no_retire");
                check32(stat_bytes, cut, "cancel.held_no_sample");
            end
            @(negedge clk);
            cancel = 1'b0;
            in_valid = 1'b0;
            in_data = 8'h00;
            out_ready = 1'b0;
            #1;
            check1(in_ready, "cancel.release_ready");
        end
        end_case();

        // ------------------------------------------------------------------
        begin_case("reset_each_phase");
        for (cut = 1; cut <= 22; cut = cut + 1) begin
            do_reset();
            for (byte_index = 0; byte_index < cut; byte_index = byte_index + 1) begin
                send_byte(phase_frame[byte_index]);
            end
            if (cut == 22) begin
                check1(out_valid, "reset22.slot_pending");
            end else begin
                check1(receiving, "reset.partial_receiving_before_reset");
            end
            @(negedge clk);
            rst = 1'b1;
            cancel = 1'b1;
            in_valid = 1'b1;
            in_data = 8'hBB;
            out_ready = 1'b1;
            #1;
            check1(!out_valid, "reset.valid_cleared_immediate");
            check1((cut == 22) ? !receiving : receiving, "reset.preserves_receiving_until_edge");
            check1(!in_ready, "reset.ready_low");
            @(posedge clk); #1;
            check_main_stats(0, 0, 0, 0, 0, 0, 0);
            check8({2'b00, out_len}, 8'h00, "reset.len_zero");
            check256(out_payload, 256'h0, "reset.payload_zero");
            repeat (2) begin
                @(posedge clk); #1;
                check_main_stats(0, 0, 0, 0, 0, 0, 0);
            end
            @(negedge clk);
            rst = 1'b0;
            cancel = 1'b0;
            in_valid = 1'b0;
            in_data = 8'h00;
            out_ready = 1'b0;
            #1;
            check1(in_ready, "reset.release_ready");
        end
        end_case();

        // ------------------------------------------------------------------
        begin_case("small_stat_saturation");
        small_do_reset();
        check8({6'b000000, small_stat_bytes}, 8'h00, "small.reset.bytes");
        check8({6'b000000, small_stat_frames}, 8'h00, "small.reset.frames");
        for (i = 0; i < 8; i = i + 1) begin
            small_send_byte(i[7:0]);
        end
        check8({6'b000000, small_stat_bytes}, 8'h03, "small.bytes_saturate");
        for (i = 0; i < 4; i = i + 1) begin
            small_send_byte(8'hA5);
            small_send_byte(8'h5A);
            small_send_byte(8'h04);
        end
        check8({6'b000000, small_stat_version}, 8'h03, "small.version_saturate");
        for (i = 0; i < 4; i = i + 1) begin
            small_send_byte(8'hA5);
            small_send_byte(8'h5A);
            small_send_byte(8'h03);
            small_send_byte(8'h20);
            small_send_byte(8'h21);
        end
        check8({6'b000000, small_stat_length}, 8'h03, "small.length_saturate");
        for (i = 0; i < 4; i = i + 1) begin
            small_send_len0_frame(8'h30 + i[7:0], 8'h40 + i[7:0], 16'h1000 + i[15:0], 32'h2000_0000 + i[31:0], 1'b1);
            check8({6'b000000, small_error_code}, 8'h03, "small.crc_error_code");
            check1(!small_out_valid, "small.crc_no_output");
        end
        check8({6'b000000, small_stat_crc}, 8'h03, "small.crc_saturate");
        for (i = 0; i < 4; i = i + 1) begin
            small_send_len0_frame(8'h50 + i[7:0], 8'h60 + i[7:0], 16'h3000 + i[15:0], 32'h4000_0000 + i[31:0], 1'b0);
            check1(small_out_valid, "small.frame_valid");
            check8({2'b00, small_out_type}, 8'h50 + i[7:0], "small.frame_type");
            small_pop();
            check1(!small_out_valid, "small.frame_popped");
        end
        check8({6'b000000, small_stat_frames}, 8'h03, "small.frames_saturate");
        check8({6'b000000, small_stat_retired}, 8'h03, "small.retired_saturate");
        for (i = 0; i < 4; i = i + 1) begin
            small_cancel_partial();
        end
        check8({6'b000000, small_stat_aborted}, 8'h03, "small.aborted_saturate");
        check8({6'b000000, small_stat_bytes}, 8'h03, "small.bytes_remain_saturated");
        check8({6'b000000, small_stat_version}, 8'h03, "small.version_remain_saturated");
        check8({6'b000000, small_stat_length}, 8'h03, "small.length_remain_saturated");
        check8({6'b000000, small_stat_crc}, 8'h03, "small.crc_remain_saturated");
        check8({6'b000000, small_stat_frames}, 8'h03, "small.frames_remain_saturated");
        check8({6'b000000, small_stat_retired}, 8'h03, "small.retired_remain_saturated");
        end_case();

        // ------------------------------------------------------------------
        begin_case("error_pulse_and_recovery");
        do_reset();
        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h7F);
        check1(error_event, "pulse.high_after_error_byte");
        check8({6'b000000, error_code}, 8'h01, "pulse.version_code");
        idle_cycles(1);
        check1(!error_event, "pulse.cleared_next_cycle");
        check8({6'b000000, error_code}, 8'h00, "pulse.code_zero_next_cycle");
        idle_cycles(3);
        check1(!error_event, "pulse.no_sticky_event");
        check8({6'b000000, error_code}, 8'h00, "pulse.no_sticky_code");
        payload_work = 256'h0102_0304_0506_0708;
        send_frame(8'h90, 8'h91, 16'hF1F2, 32'hF3F4_F5F6, 6'd8, payload_work);
        expect_complete(8'h90, 8'h91, 16'hF1F2, 32'hF3F4_F5F6, 6'd8, payload_work);
        pop_output();
        check_main_stats(25, 1, 1, 1, 0, 0, 0);
        end_case();

        // ------------------------------------------------------------------
        begin_case("reset_cancel_priority");
        do_reset();
        payload_work = 256'h0;
        for (j = 0; j < 8; j = j + 1) begin
            payload_work[8*j +: 8] = 8'hC0 + j[7:0];
        end
        send_frame(8'h92, 8'h93, 16'hA1A2, 32'hA3A4_A5A6, 6'd8, payload_work);
        expect_complete(8'h92, 8'h93, 16'hA1A2, 32'hA3A4_A5A6, 6'd8, payload_work);
        pop_output();
        send_byte(8'hA5);
        @(negedge clk);
        rst = 1'b1;
        cancel = 1'b1;
        in_valid = 1'b1;
        in_data = 8'hCC;
        out_ready = 1'b1;
        #1;
        check_main_stats(23, 1, 1, 0, 0, 0, 0);
        @(posedge clk); #1;
        check_main_stats(0, 0, 0, 0, 0, 0, 0);
        check1(!out_valid, "priority.reset_clears_output");
        check1(!receiving, "priority.reset_clears_partial");
        @(negedge clk);
        rst = 1'b0;
        cancel = 1'b0;
        in_valid = 1'b0;
        in_data = 8'h00;
        out_ready = 1'b0;
        #1;
        check1(in_ready, "priority.ready_after_reset");
        idle_cycles(1);
        check_main_stats(0, 0, 0, 0, 0, 0, 0);
        end_case();

        // ------------------------------------------------------------------
        begin_case("sync_partial_abort_gates");
        do_reset();
        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h03);
        @(negedge clk);
        cancel = 1'b1;
        #1;
        check_status_snapshot("partial.cancel.before", 1'b1, 1'b0, 2'b00, 3, 0, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(posedge clk); #1;
        check_status_snapshot("partial.cancel.after", 1'b0, 1'b0, 2'b00, 3, 0, 0, 0, 0, 0, 1, 1'b0, 1'b0);
        @(negedge clk);
        cancel = 1'b0;
        #1;
        check_status_snapshot("partial.cancel.recovered", 1'b0, 1'b0, 2'b00, 3, 0, 0, 0, 0, 0, 1, 1'b1, 1'b0);

        do_reset();
        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h03);
        @(negedge clk);
        rst = 1'b1;
        #1;
        check_status_snapshot("partial.reset.before", 1'b1, 1'b0, 2'b00, 3, 0, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(posedge clk); #1;
        check_status_snapshot("partial.reset.after", 1'b0, 1'b0, 2'b00, 0, 0, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(negedge clk);
        rst = 1'b0;
        #1;
        check_status_snapshot("partial.reset.recovered", 1'b0, 1'b0, 2'b00, 0, 0, 0, 0, 0, 0, 0, 1'b1, 1'b0);

        do_reset();
        send_byte(8'hA5);
        @(negedge clk);
        rst = 1'b1;
        cancel = 1'b1;
        in_valid = 1'b1;
        in_data = 8'hCC;
        out_ready = 1'b1;
        #1;
        check_status_snapshot("partial.reset_cancel.before", 1'b1, 1'b0, 2'b00, 1, 0, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(posedge clk); #1;
        check_status_snapshot("partial.reset_cancel.after", 1'b0, 1'b0, 2'b00, 0, 0, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(negedge clk);
        rst = 1'b0;
        cancel = 1'b0;
        in_valid = 1'b0;
        in_data = 8'h00;
        out_ready = 1'b0;
        #1;
        check_status_snapshot("partial.reset_cancel.recovered", 1'b0, 1'b0, 2'b00, 0, 0, 0, 0, 0, 0, 0, 1'b1, 1'b0);
        end_case();

        // ------------------------------------------------------------------
        begin_case("sync_error_abort_gates");
        do_reset();
        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h7F);
        check1(error_event, "pulse_targeted.high_after_error_byte");
        check8({6'b000000, error_code}, 8'h01, "pulse_targeted.version_code");
        idle_cycles(1);
        check1(!error_event, "pulse_targeted.cleared_next_cycle");
        check8({6'b000000, error_code}, 8'h00, "pulse_targeted.code_zero_next_cycle");
        check32(stat_version, 1, "pulse_targeted.version_count_stable");
        check32(stat_bytes, 3, "pulse_targeted.byte_count_stable");

        do_reset();
        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h7F);
        @(negedge clk);
        cancel = 1'b1;
        #1;
        check_status_snapshot("version.cancel.before", 1'b0, 1'b1, 2'b01, 3, 0, 0, 1, 0, 0, 0, 1'b0, 1'b0);
        @(posedge clk); #1;
        check_status_snapshot("version.cancel.after", 1'b0, 1'b0, 2'b00, 3, 0, 0, 1, 0, 0, 0, 1'b0, 1'b0);
        @(negedge clk);
        cancel = 1'b0;
        #1;
        check1(in_ready, "version.cancel.ready_after_abort");
        check1(!receiving, "version.cancel.receiving_after_abort");
        check1(!error_event, "version.cancel.event_after_abort");
        check8({6'b000000, error_code}, 8'h00, "version.cancel.code_after_abort");

        do_reset();
        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h7F);
        @(negedge clk);
        rst = 1'b1;
        #1;
        check_status_snapshot("version.reset.before", 1'b0, 1'b1, 2'b01, 3, 0, 0, 1, 0, 0, 0, 1'b0, 1'b0);
        @(posedge clk); #1;
        check_status_snapshot("version.reset.after", 1'b0, 1'b0, 2'b00, 0, 0, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(negedge clk);
        rst = 1'b0;
        #1;
        check1(in_ready, "version.reset.ready_after_abort");
        check1(!receiving, "version.reset.receiving_after_abort");
        check1(!error_event, "version.reset.event_after_abort");
        check8({6'b000000, error_code}, 8'h00, "version.reset.code_after_abort");

        do_reset();
        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h03);
        send_byte(8'h31);
        send_byte(8'h21);
        @(negedge clk);
        cancel = 1'b1;
        #1;
        check_status_snapshot("length.cancel.before", 1'b0, 1'b1, 2'b10, 5, 0, 0, 0, 1, 0, 0, 1'b0, 1'b0);
        @(posedge clk); #1;
        check_status_snapshot("length.cancel.after", 1'b0, 1'b0, 2'b00, 5, 0, 0, 0, 1, 0, 0, 1'b0, 1'b0);
        @(negedge clk);
        cancel = 1'b0;
        #1;
        check1(in_ready, "length.cancel.ready_after_abort");
        check1(!receiving, "length.cancel.receiving_after_abort");
        check1(!error_event, "length.cancel.event_after_abort");
        check8({6'b000000, error_code}, 8'h00, "length.cancel.code_after_abort");

        do_reset();
        send_byte(8'hA5);
        send_byte(8'h5A);
        send_byte(8'h03);
        send_byte(8'h31);
        send_byte(8'h21);
        @(negedge clk);
        rst = 1'b1;
        #1;
        check_status_snapshot("length.reset.before", 1'b0, 1'b1, 2'b10, 5, 0, 0, 0, 1, 0, 0, 1'b0, 1'b0);
        @(posedge clk); #1;
        check_status_snapshot("length.reset.after", 1'b0, 1'b0, 2'b00, 0, 0, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(negedge clk);
        rst = 1'b0;
        #1;
        check1(in_ready, "length.reset.ready_after_abort");
        check1(!receiving, "length.reset.receiving_after_abort");
        check1(!error_event, "length.reset.event_after_abort");
        check8({6'b000000, error_code}, 8'h00, "length.reset.code_after_abort");

        do_reset();
        payload_work = 256'hA1B2_C3D4;
        crc_work = crc_ref_frame(8'h72, 8'h73, 16'h4455, 32'h6677_8899, 6'd4, payload_work);
        send_frame_forced_crc(8'h72, 8'h73, 16'h4455, 32'h6677_8899, 6'd4, payload_work, crc_work ^ 16'h0001);
        @(negedge clk);
        cancel = 1'b1;
        #1;
        check_status_snapshot("crc.cancel.before", 1'b0, 1'b1, 2'b11, 18, 0, 0, 0, 0, 1, 0, 1'b0, 1'b0);
        @(posedge clk); #1;
        check_status_snapshot("crc.cancel.after", 1'b0, 1'b0, 2'b00, 18, 0, 0, 0, 0, 1, 0, 1'b0, 1'b0);
        @(negedge clk);
        cancel = 1'b0;
        #1;
        check1(in_ready, "crc.cancel.ready_after_abort");
        check1(!receiving, "crc.cancel.receiving_after_abort");
        check1(!error_event, "crc.cancel.event_after_abort");
        check8({6'b000000, error_code}, 8'h00, "crc.cancel.code_after_abort");

        do_reset();
        payload_work = 256'hA1B2_C3D4;
        crc_work = crc_ref_frame(8'h72, 8'h73, 16'h4455, 32'h6677_8899, 6'd4, payload_work);
        send_frame_forced_crc(8'h72, 8'h73, 16'h4455, 32'h6677_8899, 6'd4, payload_work, crc_work ^ 16'h0001);
        @(negedge clk);
        rst = 1'b1;
        #1;
        check_status_snapshot("crc.reset.before", 1'b0, 1'b1, 2'b11, 18, 0, 0, 0, 0, 1, 0, 1'b0, 1'b0);
        @(posedge clk); #1;
        check_status_snapshot("crc.reset.after", 1'b0, 1'b0, 2'b00, 0, 0, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(negedge clk);
        rst = 1'b0;
        #1;
        check1(in_ready, "crc.reset.ready_after_abort");
        check1(!receiving, "crc.reset.receiving_after_abort");
        check1(!error_event, "crc.reset.event_after_abort");
        check8({6'b000000, error_code}, 8'h00, "crc.reset.code_after_abort");
        end_case();

        // ------------------------------------------------------------------
        begin_case("sync_output_abort_gates");
        do_reset();
        payload_work = 256'h0;
        send_frame(8'hA0, 8'hA1, 16'hA2A3, 32'hA4A5_A6A7, 6'd0, payload_work);
        @(negedge clk);
        cancel = 1'b1;
        out_ready = 1'b1;
        #1;
        check_status_snapshot("output.cancel.before", 1'b0, 1'b0, 2'b00, 14, 1, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(posedge clk); #1;
        check_status_snapshot("output.cancel.after", 1'b0, 1'b0, 2'b00, 14, 1, 0, 0, 0, 0, 1, 1'b0, 1'b0);
        @(negedge clk);
        cancel = 1'b0;
        out_ready = 1'b0;
        #1;
        check1(in_ready, "output.cancel.ready_after_abort");
        check1(!out_valid, "output.cancel.valid_after_abort");

        do_reset();
        payload_work = 256'h0;
        send_frame(8'hB0, 8'hB1, 16'hB2B3, 32'hB4B5_B6B7, 6'd0, payload_work);
        @(negedge clk);
        rst = 1'b1;
        out_ready = 1'b1;
        #1;
        check_status_snapshot("output.reset.before", 1'b0, 1'b0, 2'b00, 14, 1, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(posedge clk); #1;
        check_status_snapshot("output.reset.after", 1'b0, 1'b0, 2'b00, 0, 0, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(negedge clk);
        rst = 1'b0;
        out_ready = 1'b0;
        #1;
        check1(in_ready, "output.reset.ready_after_abort");
        check1(!out_valid, "output.reset.valid_after_abort");

        do_reset();
        payload_work = 256'h0;
        send_frame(8'hC0, 8'hC1, 16'hC2C3, 32'hC4C5_C6C7, 6'd0, payload_work);
        @(negedge clk);
        rst = 1'b1;
        cancel = 1'b1;
        out_ready = 1'b1;
        #1;
        check_status_snapshot("output.reset_cancel.before", 1'b0, 1'b0, 2'b00, 14, 1, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(posedge clk); #1;
        check_status_snapshot("output.reset_cancel.after", 1'b0, 1'b0, 2'b00, 0, 0, 0, 0, 0, 0, 0, 1'b0, 1'b0);
        @(negedge clk);
        rst = 1'b0;
        cancel = 1'b0;
        out_ready = 1'b0;
        #1;
        check1(in_ready, "output.reset_cancel.ready_after_abort");
        check1(!out_valid, "output.reset_cancel.valid_after_abort");
        end_case();

        repeat (2) @(posedge clk);
        $display("WIRE_PARSER_SUMMARY|%0d|%0d|%0d|%0s", case_number, checks, errors, (errors == 0) ? "PASS" : "FAIL");
        if (errors == 0) begin
            $display("WIRE_PARSER_ALL_PASS");
            $finish;
        end else begin
            $fatal(1, "WIRE_PARSER_FAILED");
        end
    end
endmodule

module tb_wire_parser_guard1;
    logic clk = 1'b0;
    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic in_valid = 1'b0;
    logic [7:0] in_data = 8'h00;
    wire in_ready;
    wire out_valid;
    wire [7:0] out_type;
    wire [7:0] out_epoch;
    wire [15:0] out_seq;
    wire [31:0] out_tick;
    wire [5:0] out_len;
    wire [255:0] out_payload;
    wire receiving;
    wire error_event;
    wire [1:0] error_code;
    wire [1:0] stat_bytes;
    wire [1:0] stat_frames;
    wire [1:0] stat_retired;
    wire [1:0] stat_version;
    wire [1:0] stat_length;
    wire [1:0] stat_crc;
    wire [1:0] stat_aborted;

    deepeye_wire_parser #(.STAT_W(1)) dut (
        .clk(clk), .rst(rst), .cancel(cancel),
        .in_valid(in_valid), .in_ready(in_ready), .in_data(in_data),
        .out_valid(out_valid), .out_ready(1'b0), .out_type(out_type),
        .out_epoch(out_epoch), .out_seq(out_seq), .out_tick(out_tick),
        .out_len(out_len), .out_payload(out_payload), .receiving(receiving),
        .error_event(error_event), .error_code(error_code),
        .stat_bytes(stat_bytes), .stat_frames(stat_frames),
        .stat_retired(stat_retired), .stat_version(stat_version),
        .stat_length(stat_length), .stat_crc(stat_crc),
        .stat_aborted(stat_aborted)
    );

    initial begin
        #100;
        $display("WIRE_PARSER_GUARD_NOT_TRIGGERED|1");
        $fatal(1, "STAT_W=1 guard did not trigger");
    end
endmodule

module tb_wire_parser_guard33;
    logic clk = 1'b0;
    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic in_valid = 1'b0;
    logic [7:0] in_data = 8'h00;
    wire in_ready;
    wire out_valid;
    wire [7:0] out_type;
    wire [7:0] out_epoch;
    wire [15:0] out_seq;
    wire [31:0] out_tick;
    wire [5:0] out_len;
    wire [255:0] out_payload;
    wire receiving;
    wire error_event;
    wire [1:0] error_code;
    wire [31:0] stat_bytes;
    wire [31:0] stat_frames;
    wire [31:0] stat_retired;
    wire [31:0] stat_version;
    wire [31:0] stat_length;
    wire [31:0] stat_crc;
    wire [31:0] stat_aborted;

    deepeye_wire_parser #(.STAT_W(33)) dut (
        .clk(clk), .rst(rst), .cancel(cancel),
        .in_valid(in_valid), .in_ready(in_ready), .in_data(in_data),
        .out_valid(out_valid), .out_ready(1'b0), .out_type(out_type),
        .out_epoch(out_epoch), .out_seq(out_seq), .out_tick(out_tick),
        .out_len(out_len), .out_payload(out_payload), .receiving(receiving),
        .error_event(error_event), .error_code(error_code),
        .stat_bytes(stat_bytes), .stat_frames(stat_frames),
        .stat_retired(stat_retired), .stat_version(stat_version),
        .stat_length(stat_length), .stat_crc(stat_crc),
        .stat_aborted(stat_aborted)
    );

    initial begin
        #100;
        $display("WIRE_PARSER_GUARD_NOT_TRIGGERED|33");
        $fatal(1, "STAT_W=33 guard did not trigger");
    end
endmodule
