`timescale 1ns/1ps
`default_nettype none

module tb_uart_wire_rx #(
    parameter integer CLOCK_HZ = 100000000,
    parameter integer BAUD = 9600,
    parameter integer STAT_W = 32,
    parameter integer SUITE = 1
);
    localparam integer SUITE_DEFAULT = 0;
    localparam integer SUITE_FULL = 1;
    localparam integer SUITE_MIN_BAUD = 2;
    localparam integer SUITE_FRACTIONAL = 3;
    localparam integer SUITE_STAT2 = 4;
    localparam integer SUITE_GUARD = 5;
    localparam integer CLOCK_TB = ((CLOCK_HZ >= 16) &&
                                   (CLOCK_HZ <= 2147483647))
                                      ? CLOCK_HZ : 100000000;
    localparam integer BAUD_TB = ((BAUD >= 1) &&
                                  (BAUD <= (CLOCK_TB / 16)))
                                     ? BAUD : 9600;
    localparam real HALF_NS = 500000000.0 / CLOCK_TB;
    localparam real BIT_NS = 1000000000.0 / BAUD_TB;

    `define DEEPEYE_UART_WIRE_RX_STAT_W \
        ((STAT_W < 2) ? 2 : ((STAT_W > 32) ? 32 : STAT_W))

    logic clk;
    logic rst;
    logic cancel;
    logic rx_async;
    logic out_ready;
    logic out_valid;
    logic [7:0] out_type;
    logic [7:0] out_epoch;
    logic [15:0] out_seq;
    logic [31:0] out_tick;
    logic [5:0] out_len;
    logic [255:0] out_payload;
    logic uart_busy;
    logic receiving;
    logic line_error_event;
    logic [2:0] line_error_bits;
    logic error_event;
    logic [1:0] error_code;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_uart_frames;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_uart_retired;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_uart_overruns;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_uart_framing;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_uart_false_starts;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_uart_aborted;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_bytes;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_frames;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_retired;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_version;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_length;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_crc;
    wire [`DEEPEYE_UART_WIRE_RX_STAT_W-1:0] stat_aborted;

    deepeye_uart_wire_rx #(
        .CLOCK_HZ(CLOCK_HZ), .BAUD(BAUD), .STAT_W(STAT_W)
    ) dut (
        .clk(clk), .rst(rst), .cancel(cancel), .rx_async(rx_async),
        .out_ready(out_ready), .out_valid(out_valid), .out_type(out_type),
        .out_epoch(out_epoch), .out_seq(out_seq), .out_tick(out_tick),
        .out_len(out_len), .out_payload(out_payload), .uart_busy(uart_busy),
        .receiving(receiving), .line_error_event(line_error_event),
        .line_error_bits(line_error_bits), .error_event(error_event),
        .error_code(error_code), .stat_uart_frames(stat_uart_frames),
        .stat_uart_retired(stat_uart_retired),
        .stat_uart_overruns(stat_uart_overruns),
        .stat_uart_framing(stat_uart_framing),
        .stat_uart_false_starts(stat_uart_false_starts),
        .stat_uart_aborted(stat_uart_aborted), .stat_bytes(stat_bytes),
        .stat_frames(stat_frames), .stat_retired(stat_retired),
        .stat_version(stat_version), .stat_length(stat_length),
        .stat_crc(stat_crc), .stat_aborted(stat_aborted)
    );

    integer checks;
    integer failures;
    integer cases;
    integer case_checks_start;
    integer case_fail_start;
    string suite_name;
    string current_case;
    integer payload_seen [0:255];
    logic [7:0] wire_bytes [0:63];
    integer wire_len;
    integer mon_line_count;
    integer mon_line_post_count;
    logic mon_line_prev;
    logic [2:0] mon_line_bits_after;
    logic mon_line_out_valid_after;
    logic mon_line_busy_after;
    logic mon_line_receiving_after;
    integer mon_line_uart_aborted_after;
    integer mon_line_parser_aborted_after;
    integer mon_line_uart_aborted_post;
    integer mon_line_parser_aborted_post;
    integer mon_parser_count;
    integer mon_parser_post_count;
    logic mon_parser_prev;
    logic [1:0] mon_parser_code_after;
    logic [1:0] mon_parser_code_post;
    logic mon_parser_out_valid_after;
    logic mon_parser_busy_after;
    logic mon_parser_receiving_after;

    initial begin
        clk = 1'b0;
        forever #(HALF_NS) clk = ~clk;
    end

    initial begin
        integer init_index;
        rst = 1'b1;
        cancel = 1'b0;
        rx_async = 1'b1;
        out_ready = 1'b0;
        checks = 0;
        failures = 0;
        cases = 0;
        case_checks_start = 0;
        case_fail_start = 0;
        suite_name = "unset";
        current_case = "unset";
        mon_line_count = 0;
        mon_line_post_count = 0;
        mon_line_prev = 1'b0;
        mon_line_bits_after = 3'b000;
        mon_line_out_valid_after = 1'b0;
        mon_line_busy_after = 1'b0;
        mon_line_receiving_after = 1'b0;
        mon_line_uart_aborted_after = 0;
        mon_line_parser_aborted_after = 0;
        mon_line_uart_aborted_post = 0;
        mon_line_parser_aborted_post = 0;
        mon_parser_count = 0;
        mon_parser_post_count = 0;
        mon_parser_prev = 1'b0;
        mon_parser_code_after = 2'b00;
        mon_parser_code_post = 2'b00;
        mon_parser_out_valid_after = 1'b0;
        mon_parser_busy_after = 1'b0;
        mon_parser_receiving_after = 1'b0;
        for (init_index = 0; init_index < 256; init_index = init_index + 1) begin
            payload_seen[init_index] = 0;
        end
    end

    always @(posedge clk) begin
        #1ps;
        if (line_error_event) begin
            mon_line_count = mon_line_count + 1;
            mon_line_bits_after = line_error_bits;
            mon_line_out_valid_after = out_valid;
            mon_line_busy_after = uart_busy;
            mon_line_receiving_after = receiving;
            mon_line_uart_aborted_after = to_int(stat_uart_aborted);
            mon_line_parser_aborted_after = to_int(stat_aborted);
        end else if (mon_line_prev) begin
            mon_line_post_count = mon_line_post_count + 1;
            mon_line_uart_aborted_post = to_int(stat_uart_aborted);
            mon_line_parser_aborted_post = to_int(stat_aborted);
        end
        mon_line_prev = line_error_event;

        if (error_event) begin
            mon_parser_count = mon_parser_count + 1;
            mon_parser_code_after = error_code;
            mon_parser_out_valid_after = out_valid;
            mon_parser_busy_after = uart_busy;
            mon_parser_receiving_after = receiving;
        end else if (mon_parser_prev) begin
            mon_parser_post_count = mon_parser_post_count + 1;
            mon_parser_code_post = error_code;
        end
        mon_parser_prev = error_event;
    end

    function automatic integer to_int(input logic [31:0] value);
        begin
            to_int = value;
        end
    endfunction

    function automatic integer sat_max;
        begin
            if (STAT_W >= 31) begin
                sat_max = 2147483647;
            end else begin
                sat_max = (1 << STAT_W) - 1;
            end
        end
    endfunction

    function automatic integer sat_add(input integer base, input integer delta);
        integer sum;
        begin
            sum = base + delta;
            if (sum > sat_max()) begin
                sat_add = sat_max();
            end else begin
                sat_add = sum;
            end
        end
    endfunction

    function automatic integer sat_inc(input integer value);
        begin
            if (value >= sat_max()) begin
                sat_inc = sat_max();
            end else begin
                sat_inc = value + 1;
            end
        end
    endfunction

    function automatic logic [7:0] payload_value(
        input integer seed,
        input integer index
    );
        begin
            payload_value = 8'((seed + index) & 255);
        end
    endfunction

    function automatic logic [15:0] crc16_step(
        input logic [15:0] state,
        input logic [7:0] data
    );
        integer bit_index;
        logic [15:0] value;
        begin
            value = state;
            for (bit_index = 7; bit_index >= 0; bit_index = bit_index - 1) begin
                if (value[15] ^ data[bit_index]) begin
                    value = (value << 1) ^ 16'h1021;
                end else begin
                    value = value << 1;
                end
            end
            crc16_step = value;
        end
    endfunction

    function automatic integer packet_timeout;
        integer byte_cycles;
        begin
            byte_cycles = (CLOCK_TB + BAUD_TB - 1) / BAUD_TB;
            packet_timeout = ((wire_len + 4) * 10 * byte_cycles) + 10000;
        end
    endfunction

    task automatic check(input logic condition, input string message);
        begin
            checks = checks + 1;
            if (!condition) begin
                failures = failures + 1;
                $display("WIRE_RX_ERROR suite=%s case=%s check=%s",
                         suite_name, current_case, message);
            end
        end
    endtask

    task automatic check_int(
        input integer actual,
        input integer expected,
        input string message
    );
        begin
            check(actual == expected,
                  $sformatf("%s_actual_%0d_expected_%0d",
                            message, actual, expected));
        end
    endtask

    task automatic begin_case(input string name);
        begin
            cases = cases + 1;
            current_case = name;
            case_checks_start = checks;
            case_fail_start = failures;
        end
    endtask

    task automatic end_case;
        begin
            if (failures == case_fail_start) begin
                $display("WIRE_RX_CASE suite=%s case=%s checks=%0d status=PASS",
                         suite_name, current_case, checks - case_checks_start);
            end else begin
                $display("WIRE_RX_CASE suite=%s case=%s checks=%0d status=FAIL",
                         suite_name, current_case, checks - case_checks_start);
            end
        end
    endtask

    task automatic build_packet(
        input logic [7:0] version_i,
        input logic [7:0] type_i,
        input logic [7:0] pkt_len,
        input logic [7:0] epoch_i,
        input logic [15:0] seq_i,
        input logic [31:0] tick_i,
        input integer seed_i,
        input logic corrupt_crc
    );
        integer index;
        integer crc_end;
        logic [15:0] crc;
        begin
            wire_bytes[0] = 8'hA5;
            wire_bytes[1] = 8'h5A;
            wire_bytes[2] = version_i;
            wire_bytes[3] = type_i;
            wire_bytes[4] = pkt_len;
            wire_bytes[5] = epoch_i;
            wire_bytes[6] = seq_i[7:0];
            wire_bytes[7] = seq_i[15:8];
            wire_bytes[8] = tick_i[7:0];
            wire_bytes[9] = tick_i[15:8];
            wire_bytes[10] = tick_i[23:16];
            wire_bytes[11] = tick_i[31:24];
            for (index = 0; index < 32; index = index + 1) begin
                if (index < pkt_len) begin
                    wire_bytes[12 + index] = payload_value(seed_i, index);
                end
            end
            crc = 16'hFFFF;
            crc_end = 12 + pkt_len;
            for (index = 2; index < crc_end; index = index + 1) begin
                crc = crc16_step(crc, wire_bytes[index]);
            end
            wire_bytes[12 + pkt_len] = crc[7:0];
            wire_bytes[13 + pkt_len] = crc[15:8];
            if (corrupt_crc) begin
                wire_bytes[13 + pkt_len] = wire_bytes[13 + pkt_len] ^ 8'h20;
            end
            wire_len = 14 + pkt_len;
        end
    endtask

    task automatic send_byte(
        input logic [7:0] data_i,
        input logic bad_stop
    );
        integer bit_index;
        begin
            @(negedge clk);
            rx_async = 1'b0;
            #(BIT_NS);
            for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1) begin
                rx_async = data_i[bit_index];
                #(BIT_NS);
            end
            rx_async = bad_stop ? 1'b0 : 1'b1;
            #(BIT_NS);
            rx_async = 1'b1;
        end
    endtask

    task automatic inject_false_start;
        begin
            @(negedge clk);
            rx_async = 1'b0;
            #(BIT_NS * 0.35);
            rx_async = 1'b1;
            #(BIT_NS * 0.85);
        end
    endtask

    task automatic send_packet_count(input integer count);
        integer index;
        begin
            for (index = 0; index < count; index = index + 1) begin
                send_byte(wire_bytes[index], 1'b0);
            end
        end
    endtask

    task automatic wait_out_valid(input integer max_cycles);
        integer waited;
        begin
            waited = 0;
            while (!out_valid && (waited < max_cycles)) begin
                @(posedge clk);
                #1ps;
                waited = waited + 1;
            end
            check(out_valid, $sformatf("out_valid_timeout_%0d", waited));
        end
    endtask

    task automatic wait_parser_bytes(input integer target, input integer max_cycles);
        integer waited;
        begin
            waited = 0;
            while ((to_int(stat_bytes) < target) && (waited < max_cycles)) begin
                @(posedge clk);
                #1ps;
                waited = waited + 1;
            end
            check_int(to_int(stat_bytes), target,
                      $sformatf("parser_bytes_wait_%0d", waited));
        end
    endtask

    task automatic wait_line_events(input integer target);
        integer waited;
        begin
            waited = 0;
            while ((mon_line_count < target) && (waited < packet_timeout())) begin
                @(posedge clk);
                #1ps;
                waited = waited + 1;
            end
            check_int(mon_line_count, target,
                      $sformatf("line_event_wait_%0d", waited));
        end
    endtask

    task automatic wait_parser_events(input integer target);
        integer waited;
        begin
            waited = 0;
            while ((mon_parser_count < target) && (waited < packet_timeout())) begin
                @(posedge clk);
                #1ps;
                waited = waited + 1;
            end
            check_int(mon_parser_count, target,
                      $sformatf("parser_event_wait_%0d", waited));
        end
    endtask

    task automatic advance_cycles(input integer count);
        integer index;
        begin
            for (index = 0; index < count; index = index + 1) begin
                @(posedge clk);
                #1ps;
            end
        end
    endtask

    task automatic retire_candidate;
        integer retired_before;
        begin
            retired_before = to_int(stat_retired);
            @(negedge clk);
            out_ready = 1'b1;
            @(posedge clk);
            #1ps;
            check(!out_valid, "candidate_not_retired");
            check_int(to_int(stat_retired), sat_inc(retired_before),
                      "parser_retired_after_accept");
            @(negedge clk);
            out_ready = 1'b0;
        end
    endtask

    task automatic check_payload(
        input integer pkt_len,
        input integer seed_i
    );
        integer lane;
        logic [7:0] expected;
        begin
            for (lane = 0; lane < 32; lane = lane + 1) begin
                if (lane < pkt_len) begin
                    expected = payload_value(seed_i, lane);
                    payload_seen[expected] = 1;
                end else begin
                    expected = 8'h00;
                end
                check(out_payload[8*lane +: 8] == expected,
                      $sformatf("payload_lane_%0d", lane));
            end
        end
    endtask

    // Packet-run and suite tasks follow.

    task automatic run_valid_packet(
        input logic [7:0] type_i,
        input logic [7:0] pkt_len,
        input logic [7:0] epoch_i,
        input logic [15:0] seq_i,
        input logic [31:0] tick_i,
        input integer seed_i
    );
        integer pre_uart_frames;
        integer pre_uart_retired;
        integer pre_bytes;
        integer pre_frames;
        integer pre_retired;
        integer line_base;
        integer parser_base;
        begin
            build_packet(8'h03, type_i, pkt_len, epoch_i, seq_i, tick_i,
                         seed_i, 1'b0);
            pre_uart_frames = to_int(stat_uart_frames);
            pre_uart_retired = to_int(stat_uart_retired);
            pre_bytes = to_int(stat_bytes);
            pre_frames = to_int(stat_frames);
            pre_retired = to_int(stat_retired);
            line_base = mon_line_count;
            parser_base = mon_parser_count;
            send_packet_count(wire_len);
            wait_out_valid(packet_timeout());
            check_int(to_int(stat_uart_frames),
                      sat_add(pre_uart_frames, wire_len), "uart_frames_valid");
            check_int(to_int(stat_uart_retired),
                      sat_add(pre_uart_retired, wire_len), "uart_retired_valid");
            check_int(to_int(stat_bytes), sat_add(pre_bytes, wire_len),
                      "parser_bytes_valid");
            check_int(to_int(stat_frames), sat_inc(pre_frames),
                      "parser_frames_valid");
            check_int(to_int(stat_retired), pre_retired, "retired_before_ready");
            check_int(mon_line_count, line_base, "unexpected_line_event");
            check_int(mon_parser_count, parser_base, "unexpected_parser_error");
            check(out_valid, "valid_candidate_visible");
            check(!out_ready, "out_ready_held_during_check");
            check(!uart_busy, "uart_idle_at_valid"); 
            check(!receiving, "parser_not_receiving_at_valid");
            check(out_type == type_i, "type_mismatch");
            check(out_epoch == epoch_i, "epoch_mismatch");
            check(out_seq == seq_i, "seq_little_endian_mismatch");
            check(out_tick == tick_i, "tick_little_endian_mismatch");
            check(out_len == pkt_len[5:0], "length_mismatch");
            check_payload(pkt_len, seed_i);
            retire_candidate();
            check_int(to_int(stat_retired), sat_inc(pre_retired),
                      "parser_retired_valid");
        end
    endtask

    task automatic issue_version_error;
        integer pre_uart_frames;
        integer pre_uart_retired;
        integer pre_bytes;
        integer pre_frames;
        integer pre_version;
        integer line_base;
        integer parser_base;
        begin
            build_packet(8'h02, 8'h21, 8'd0, 8'h32, 16'h3412,
                         32'h78563412, 7, 1'b0);
            pre_uart_frames = to_int(stat_uart_frames);
            pre_uart_retired = to_int(stat_uart_retired);
            pre_bytes = to_int(stat_bytes);
            pre_frames = to_int(stat_frames);
            pre_version = to_int(stat_version);
            line_base = mon_line_count;
            parser_base = mon_parser_count;
            send_packet_count(wire_len);
            wait_parser_events(parser_base + 1);
            check_int(to_int(stat_uart_frames),
                      sat_add(pre_uart_frames, wire_len), "uart_frames_version");
            check_int(to_int(stat_uart_retired),
                      sat_add(pre_uart_retired, wire_len),
                      "uart_retired_version");
            check_int(to_int(stat_bytes), sat_add(pre_bytes, wire_len),
                      "parser_bytes_version");
            check_int(to_int(stat_frames), pre_frames, "frames_version");
            check_int(to_int(stat_version), sat_inc(pre_version),
                      "version_count");
            check_int(mon_line_count, line_base, "line_event_version");
            check_int(mon_parser_post_count, parser_base + 1,
                      "parser_error_next_edge_version");
            check(mon_parser_code_after == 2'b01, "version_error_code");
            check(mon_parser_code_post == 2'b00, "version_error_cleared");
            check(!mon_parser_out_valid_after, "version_no_candidate");
            check(!out_valid, "version_output_absent");
            advance_cycles(4);
        end
    endtask

    task automatic issue_length_error;
        integer pre_uart_frames;
        integer pre_uart_retired;
        integer pre_bytes;
        integer pre_frames;
        integer pre_length;
        integer line_base;
        integer parser_base;
        begin
            build_packet(8'h03, 8'h42, 8'd33, 8'h53, 16'h6543,
                         32'hABCDEF01, 9, 1'b0);
            pre_uart_frames = to_int(stat_uart_frames);
            pre_uart_retired = to_int(stat_uart_retired);
            pre_bytes = to_int(stat_bytes);
            pre_frames = to_int(stat_frames);
            pre_length = to_int(stat_length);
            line_base = mon_line_count;
            parser_base = mon_parser_count;
            send_packet_count(5);
            wait_parser_events(parser_base + 1);
            check_int(to_int(stat_uart_frames),
                      sat_add(pre_uart_frames, 5), "uart_frames_length");
            check_int(to_int(stat_uart_retired),
                      sat_add(pre_uart_retired, 5), "uart_retired_length");
            check_int(to_int(stat_bytes), sat_add(pre_bytes, 5),
                      "parser_bytes_length");
            check_int(to_int(stat_frames), pre_frames, "frames_length");
            check_int(to_int(stat_length), sat_inc(pre_length),
                      "length_count");
            check_int(mon_line_count, line_base, "line_event_length");
            check_int(mon_parser_post_count, parser_base + 1,
                      "parser_error_next_edge_length");
            check(mon_parser_code_after == 2'b10, "length_error_code");
            check(mon_parser_code_post == 2'b00, "length_error_cleared");
            check(!mon_parser_out_valid_after, "length_no_candidate");
            check(!out_valid, "length_output_absent");
            advance_cycles(4);
        end
    endtask

    task automatic issue_crc_error;
        integer pre_uart_frames;
        integer pre_uart_retired;
        integer pre_bytes;
        integer pre_frames;
        integer pre_crc;
        integer line_base;
        integer parser_base;
        begin
            build_packet(8'h03, 8'h63, 8'd0, 8'h74, 16'h8765,
                         32'h10325476, 11, 1'b1);
            pre_uart_frames = to_int(stat_uart_frames);
            pre_uart_retired = to_int(stat_uart_retired);
            pre_bytes = to_int(stat_bytes);
            pre_frames = to_int(stat_frames);
            pre_crc = to_int(stat_crc);
            line_base = mon_line_count;
            parser_base = mon_parser_count;
            send_packet_count(wire_len);
            wait_parser_events(parser_base + 1);
            check_int(to_int(stat_uart_frames),
                      sat_add(pre_uart_frames, wire_len), "uart_frames_crc");
            check_int(to_int(stat_uart_retired),
                      sat_add(pre_uart_retired, wire_len), "uart_retired_crc");
            check_int(to_int(stat_bytes), sat_add(pre_bytes, wire_len),
                      "parser_bytes_crc");
            check_int(to_int(stat_frames), pre_frames, "frames_crc");
            check_int(to_int(stat_crc), sat_inc(pre_crc), "crc_count");
            check_int(mon_line_count, line_base, "line_event_crc");
            check_int(mon_parser_post_count, parser_base + 1,
                      "parser_error_next_edge_crc");
            check(mon_parser_code_after == 2'b11, "crc_error_code");
            check(mon_parser_code_post == 2'b00, "crc_error_cleared");
            check(!mon_parser_out_valid_after, "crc_no_candidate");
            check(!out_valid, "crc_output_absent");
            advance_cycles(4);
        end
    endtask

    task automatic issue_bad_stop(input integer byte_index, input integer pkt_len);
        integer pre_uart_frames;
        integer pre_uart_retired;
        integer pre_uart_framing;
        integer pre_uart_aborted;
        integer pre_bytes;
        integer pre_frames;
        integer pre_aborted;
        integer line_base;
        integer expected_aborted;
        begin
            build_packet(8'h03, 8'h75, pkt_len, 8'h86, 16'hA987,
                         32'h54761032, 13, 1'b0);
            pre_uart_frames = to_int(stat_uart_frames);
            pre_uart_retired = to_int(stat_uart_retired);
            pre_uart_framing = to_int(stat_uart_framing);
            pre_uart_aborted = to_int(stat_uart_aborted);
            pre_bytes = to_int(stat_bytes);
            pre_frames = to_int(stat_frames);
            pre_aborted = to_int(stat_aborted);
            line_base = mon_line_count;
            send_packet_count(byte_index);
            send_byte(wire_bytes[byte_index], 1'b1);
            wait_line_events(line_base + 1);
            check_int(to_int(stat_uart_framing), sat_inc(pre_uart_framing),
                      "framing_count");
            check_int(to_int(stat_uart_frames),
                      sat_add(pre_uart_frames, byte_index), "uart_frames_bad_stop");
            check_int(to_int(stat_uart_retired),
                      sat_add(pre_uart_retired, byte_index),
                      "uart_retired_bad_stop");
            check_int(to_int(stat_bytes), sat_add(pre_bytes, byte_index),
                      "parser_bytes_bad_stop");
            check_int(to_int(stat_frames), pre_frames, "frames_bad_stop");
            check(mon_line_bits_after == 3'b010, "bad_stop_line_bits");
            check(!mon_line_out_valid_after, "bad_stop_masks_candidate");
            check_int(mon_line_uart_aborted_after, pre_uart_aborted,
                      "uart_abort_pre_flush_bad_stop");
            check_int(mon_line_parser_aborted_after, pre_aborted,
                      "parser_abort_pre_flush_bad_stop");
            expected_aborted = (byte_index > 0)
                               ? sat_inc(pre_aborted) : pre_aborted;
            check_int(mon_line_parser_aborted_post, expected_aborted,
                      "parser_abort_post_flush_bad_stop");
            check_int(mon_line_uart_aborted_post, pre_uart_aborted,
                      "uart_abort_post_flush_bad_stop");
            check_int(mon_line_post_count, line_base + 1,
                      "bad_stop_flushes_next_edge");
            check(!out_valid, "bad_stop_output_absent");
            advance_cycles(4);
        end
    endtask

    task automatic issue_false_start(
        input integer prefix_bytes,
        input integer pkt_len
    );
        integer pre_uart_frames;
        integer pre_uart_retired;
        integer pre_uart_false_starts;
        integer pre_uart_aborted;
        integer pre_bytes;
        integer pre_aborted;
        integer line_base;
        integer expected_aborted;
        begin
            build_packet(8'h03, 8'h76, pkt_len, 8'h97, 16'hBA98,
                         32'h76543210, 15, 1'b0);
            pre_uart_frames = to_int(stat_uart_frames);
            pre_uart_retired = to_int(stat_uart_retired);
            pre_uart_false_starts = to_int(stat_uart_false_starts);
            pre_uart_aborted = to_int(stat_uart_aborted);
            pre_bytes = to_int(stat_bytes);
            pre_aborted = to_int(stat_aborted);
            line_base = mon_line_count;
            send_packet_count(prefix_bytes);
            if (prefix_bytes > 0) begin
                wait_parser_bytes(pre_bytes + prefix_bytes, packet_timeout());
            end
            inject_false_start();
            wait_line_events(line_base + 1);
            check_int(to_int(stat_uart_false_starts),
                      sat_inc(pre_uart_false_starts), "false_start_count");
            check_int(to_int(stat_uart_frames),
                      sat_add(pre_uart_frames, prefix_bytes),
                      "uart_frames_false_start");
            check_int(to_int(stat_uart_retired),
                      sat_add(pre_uart_retired, prefix_bytes),
                      "uart_retired_false_start");
            check_int(to_int(stat_bytes), sat_add(pre_bytes, prefix_bytes),
                      "parser_bytes_false_start");
            check(mon_line_bits_after == 3'b001, "false_start_line_bits");
            check(!mon_line_out_valid_after, "false_start_masks_candidate");
            check_int(mon_line_uart_aborted_after, pre_uart_aborted,
                      "uart_abort_pre_flush_false_start");
            check_int(mon_line_parser_aborted_after, pre_aborted,
                      "parser_abort_pre_flush_false_start");
            expected_aborted = (prefix_bytes > 0)
                               ? sat_inc(pre_aborted) : pre_aborted;
            check_int(mon_line_parser_aborted_post, expected_aborted,
                      "parser_abort_post_flush_false_start");
            check_int(mon_line_uart_aborted_post, pre_uart_aborted,
                      "uart_abort_post_flush_false_start");
            check_int(mon_line_post_count, line_base + 1,
                      "false_start_flushes_next_edge");
            check(!out_valid, "false_start_output_absent");
            advance_cycles(4);
        end
    endtask

    task automatic issue_overrun;
        integer pre_uart_frames;
        integer pre_uart_retired;
        integer pre_uart_overruns;
        integer pre_uart_aborted;
        integer pre_bytes;
        integer pre_frames;
        integer pre_retired;
        integer pre_aborted;
        integer line_base;
        integer parser_base;
        begin
            build_packet(8'h03, 8'h87, 8'd0, 8'h98, 16'hCBB9,
                         32'h87654321, 17, 1'b0);
            send_packet_count(wire_len);
            wait_out_valid(packet_timeout());
            check(out_valid, "overrun_setup_candidate");
            check(out_type == 8'h87, "overrun_setup_type");
            pre_uart_frames = to_int(stat_uart_frames);
            pre_uart_retired = to_int(stat_uart_retired);
            pre_uart_overruns = to_int(stat_uart_overruns);
            pre_uart_aborted = to_int(stat_uart_aborted);
            pre_bytes = to_int(stat_bytes);
            pre_frames = to_int(stat_frames);
            pre_retired = to_int(stat_retired);
            pre_aborted = to_int(stat_aborted);
            line_base = mon_line_count;
            parser_base = mon_parser_count;
            send_byte(wire_bytes[0], 1'b0);
            send_byte(wire_bytes[1], 1'b0);
            wait_line_events(line_base + 1);
            check(mon_line_bits_after == 3'b100, "overrun_line_bits");
            check(!mon_line_out_valid_after, "overrun_masks_prior_candidate");
            check_int(to_int(stat_uart_overruns),
                      sat_inc(pre_uart_overruns), "overrun_count");
            check_int(to_int(stat_uart_frames), sat_add(pre_uart_frames, 2),
                      "uart_frames_overrun");
            check_int(to_int(stat_uart_retired), pre_uart_retired,
                      "uart_retired_overrun");
            check_int(to_int(stat_bytes), pre_bytes, "parser_bytes_overrun");
            check_int(to_int(stat_frames), pre_frames, "frames_overrun");
            check_int(to_int(stat_retired), pre_retired,
                      "retired_overrun_candidate_discarded");
            check_int(mon_parser_count, parser_base, "line_error_not_parser_fault");
            check_int(mon_line_uart_aborted_after, pre_uart_aborted,
                      "uart_abort_pre_flush_overrun");
            check_int(mon_line_parser_aborted_after, pre_aborted,
                      "parser_abort_pre_flush_overrun");
            check_int(mon_line_uart_aborted_post, sat_inc(pre_uart_aborted),
                      "uart_abort_post_flush_overrun");
            check_int(mon_line_parser_aborted_post, sat_inc(pre_aborted),
                      "parser_abort_post_flush_overrun");
            check_int(mon_line_post_count, line_base + 1,
                      "overrun_flushes_next_edge");
            check(!out_valid, "prior_candidate_discarded_on_line_error");
            advance_cycles(4);
        end
    endtask

    task automatic issue_cancel_region(
        input integer prefix_bytes,
        input integer pkt_len,
        input logic completed_mode
    );
        integer pre_uart_aborted;
        integer pre_aborted;
        integer pre_bytes;
        integer expected_aborted;
        integer held_aborted;
        integer held_uart_aborted;
        begin
            build_packet(8'h03, 8'h99, pkt_len, 8'hA9, 16'hDCBA,
                         32'h98765432, 19, 1'b0);
            pre_bytes = to_int(stat_bytes);
            if (completed_mode) begin
                send_packet_count(wire_len);
                wait_out_valid(packet_timeout());
                check(out_valid, "cancel_completed_setup");
            end else if (prefix_bytes > 0) begin
                send_packet_count(prefix_bytes);
                wait_parser_bytes(pre_bytes + prefix_bytes, packet_timeout());
            end
            pre_uart_aborted = to_int(stat_uart_aborted);
            pre_aborted = to_int(stat_aborted);
            @(negedge clk);
            cancel = 1'b1;
            @(posedge clk);
            #1ps;
            expected_aborted = (completed_mode || (prefix_bytes > 0))
                               ? sat_inc(pre_aborted) : pre_aborted;
            check_int(to_int(stat_aborted), expected_aborted,
                      "cancel_first_flush");
            check_int(to_int(stat_uart_aborted), pre_uart_aborted,
                      "cancel_uart_abort_no_pending");
            check(!out_valid, "cancel_masks_candidate");
            held_aborted = to_int(stat_aborted);
            held_uart_aborted = to_int(stat_uart_aborted);
            advance_cycles(2);
            check_int(to_int(stat_aborted), held_aborted,
                      "cancel_held_flushes_once");
            check_int(to_int(stat_uart_aborted), held_uart_aborted,
                      "cancel_held_uart_flushes_once");
            @(negedge clk);
            cancel = 1'b0;
            advance_cycles(6);
        end
    endtask

    task automatic issue_reset_region(
        input integer prefix_bytes,
        input integer pkt_len,
        input logic completed_mode
    );
        integer pre_bytes;
        begin
            build_packet(8'h03, 8'h9A, pkt_len, 8'hBA, 16'hEDCB,
                         32'hA9876543, 21, 1'b0);
            pre_bytes = to_int(stat_bytes);
            if (completed_mode) begin
                send_packet_count(wire_len);
                wait_out_valid(packet_timeout());
                check(out_valid, "reset_completed_setup");
            end else if (prefix_bytes > 0) begin
                send_packet_count(prefix_bytes);
                wait_parser_bytes(pre_bytes + prefix_bytes, packet_timeout());
            end
            @(negedge clk);
            rst = 1'b1;
            @(posedge clk);
            #1ps;
            check_all_cleared("reset_first_edge");
            @(posedge clk);
            #1ps;
            check_all_cleared("reset_second_edge");
            @(negedge clk);
            rst = 1'b0;
            advance_cycles(6);
        end
    endtask

    task automatic check_all_cleared(input string label);
        begin
            check(!out_valid, {label, "_out_valid"});
            check(!uart_busy, {label, "_uart_busy"});
            check(!receiving, {label, "_receiving"});
            check(!line_error_event, {label, "_line_error"});
            check(!error_event, {label, "_parser_error"});
            check_int(to_int(stat_uart_frames), 0, {label, "_uart_frames"});
            check_int(to_int(stat_uart_retired), 0, {label, "_uart_retired"});
            check_int(to_int(stat_uart_overruns), 0, {label, "_uart_overruns"});
            check_int(to_int(stat_uart_framing), 0, {label, "_uart_framing"});
            check_int(to_int(stat_uart_false_starts), 0,
                      {label, "_uart_false_starts"});
            check_int(to_int(stat_uart_aborted), 0, {label, "_uart_aborted"});
            check_int(to_int(stat_bytes), 0, {label, "_bytes"});
            check_int(to_int(stat_frames), 0, {label, "_frames"});
            check_int(to_int(stat_retired), 0, {label, "_retired"});
            check_int(to_int(stat_version), 0, {label, "_version"});
            check_int(to_int(stat_length), 0, {label, "_length"});
            check_int(to_int(stat_crc), 0, {label, "_crc"});
            check_int(to_int(stat_aborted), 0, {label, "_aborted"});
        end
    endtask

    task automatic run_noise_recovery;
        integer pre_uart_frames;
        integer pre_uart_retired;
        integer pre_bytes;
        integer pre_frames;
        integer pre_retired;
        integer line_base;
        integer parser_base;
        begin
            build_packet(8'h03, 8'hA1, 8'd2, 8'hB2, 16'h3456,
                         32'h76543210, 23, 1'b0);
            pre_uart_frames = to_int(stat_uart_frames);
            pre_uart_retired = to_int(stat_uart_retired);
            pre_bytes = to_int(stat_bytes);
            pre_frames = to_int(stat_frames);
            pre_retired = to_int(stat_retired);
            line_base = mon_line_count;
            parser_base = mon_parser_count;
            send_byte(8'h00, 1'b0);
            send_byte(8'hFF, 1'b0);
            send_byte(8'h55, 1'b0);
            send_byte(8'hA5, 1'b0);
            send_byte(8'h00, 1'b0);
            send_byte(8'h7E, 1'b0);
            send_packet_count(wire_len);
            wait_out_valid(packet_timeout());
            check_int(to_int(stat_uart_frames),
                      sat_add(pre_uart_frames, wire_len + 6),
                      "uart_frames_noise");
            check_int(to_int(stat_uart_retired),
                      sat_add(pre_uart_retired, wire_len + 6),
                      "uart_retired_noise");
            check_int(to_int(stat_bytes), sat_add(pre_bytes, wire_len + 6),
                      "parser_bytes_noise");
            check_int(to_int(stat_frames), sat_inc(pre_frames),
                      "parser_frames_noise");
            check_int(mon_line_count, line_base, "line_event_noise");
            check_int(mon_parser_count, parser_base, "parser_error_noise");
            check(out_valid, "noise_candidate_visible");
            check(out_type == 8'hA1, "noise_type");
            check(out_len == 6'd2, "noise_len");
            check_payload(2, 23);
            retire_candidate();
            check_int(to_int(stat_retired), sat_inc(pre_retired),
                      "parser_retired_noise");
        end
    endtask

    task automatic run_retired_before_later_error;
        integer pre_uart_frames;
        integer pre_uart_retired;
        integer pre_bytes;
        integer pre_frames;
        integer pre_retired;
        integer pre_uart_framing;
        integer pre_parser_aborted;
        integer line_base;
        begin
            build_packet(8'h03, 8'hB3, 8'd0, 8'hC4, 16'h5678,
                         32'h89ABCDEF, 25, 1'b0);
            send_packet_count(wire_len);
            wait_out_valid(packet_timeout());
            check(out_valid, "retired_boundary_setup");
            retire_candidate();
            pre_uart_frames = to_int(stat_uart_frames);
            pre_uart_retired = to_int(stat_uart_retired);
            pre_bytes = to_int(stat_bytes);
            pre_frames = to_int(stat_frames);
            pre_retired = to_int(stat_retired);
            pre_uart_framing = to_int(stat_uart_framing);
            pre_parser_aborted = to_int(stat_aborted);
            line_base = mon_line_count;
            send_byte(8'h55, 1'b1);
            wait_line_events(line_base + 1);
            check(mon_line_bits_after == 3'b010, "later_error_framing_bits");
            check_int(to_int(stat_uart_framing), sat_inc(pre_uart_framing),
                      "later_error_framing_count");
            check_int(to_int(stat_uart_frames), pre_uart_frames,
                      "later_error_not_retroactive_uart_frames");
            check_int(to_int(stat_uart_retired), pre_uart_retired,
                      "later_error_not_retroactive_uart_retired");
            check_int(to_int(stat_bytes), pre_bytes,
                      "later_error_not_retroactive_bytes");
            check_int(to_int(stat_frames), pre_frames,
                      "later_error_not_retroactive_frames");
            check_int(to_int(stat_retired), pre_retired,
                      "later_error_not_retroactive_parser_retired");
            check_int(to_int(stat_aborted), pre_parser_aborted,
                      "later_error_idle_parser_not_aborted");
            check(!out_valid, "later_error_no_candidate");
            advance_cycles(4);
        end
    endtask

    task automatic run_held_cancel_post_low;
        integer pre_bytes;
        integer pre_aborted;
        integer pre_uart_aborted;
        integer line_base;
        begin
            build_packet(8'h03, 8'hC5, 8'd4, 8'hD6, 16'h789A,
                         32'hFEDCBA98, 27, 1'b0);
            pre_bytes = to_int(stat_bytes);
            send_packet_count(3);
            wait_parser_bytes(pre_bytes + 3, packet_timeout());
            pre_aborted = to_int(stat_aborted);
            pre_uart_aborted = to_int(stat_uart_aborted);
            line_base = mon_line_count;
            @(negedge clk);
            rx_async = 1'b0;
            cancel = 1'b1;
            @(posedge clk);
            #1ps;
            check_int(to_int(stat_aborted), sat_inc(pre_aborted),
                      "held_cancel_first_flush");
            check_int(to_int(stat_uart_aborted), pre_uart_aborted,
                      "held_cancel_uart_no_pending");
            check(!out_valid, "held_cancel_no_candidate");
            advance_cycles(2);
            check_int(to_int(stat_aborted), sat_inc(pre_aborted),
                      "held_cancel_flushes_once");
            @(negedge clk);
            cancel = 1'b0;
            #(BIT_NS * 2.0);
            check(!uart_busy, "post_abort_low_not_busy");
            check(!receiving, "post_abort_low_not_receiving");
            check(!out_valid, "post_abort_low_no_output");
            check_int(mon_line_count, line_base, "post_abort_low_no_line_error");
            @(negedge clk);
            rx_async = 1'b1;
            advance_cycles(6);
            run_valid_packet(8'hD7, 8'd2, 8'hE8, 16'h9ABC,
                             32'h12345678, 29);
        end
    endtask

    task automatic run_length_sweep;
        integer length_index;
        begin
            for (length_index = 0; length_index <= 32;
                 length_index = length_index + 1) begin
                begin_case($sformatf("len_%0d", length_index));
                run_valid_packet(
                    8'((length_index * 9 + 1) & 255),
                    length_index[7:0],
                    8'((length_index * 13 + 5) & 255),
                    16'((length_index * 257 + 3) & 65535),
                    32'(32'h10000000 + length_index * 32'h00010001),
                    length_index * 8
                );
                end_case;
            end
        end
    endtask

    task automatic run_payload_and_adjacency;
        integer group;
        begin
            begin_case("payload_all_bytes");
            for (group = 0; group < 8; group = group + 1) begin
                run_valid_packet(8'(8'h40 + group), 8'd32,
                                 8'(8'h80 + group), 16'(16'h2000 + group),
                                 32'(32'h60000000 + group), group * 32);
            end
            for (group = 0; group < 256; group = group + 1) begin
                check(payload_seen[group] == 1,
                      $sformatf("payload_byte_unseen_%0d", group));
            end
            end_case;

            begin_case("maxima_endianness");
            run_valid_packet(8'hFF, 8'd32, 8'hFF, 16'hFFFF,
                             32'hFFFFFFFF, 8'hA5);
            end_case;

            begin_case("adjacent_valid");
            run_valid_packet(8'h55, 8'd1, 8'h66, 16'h1234,
                             32'h89ABCDEF, 31);
            run_valid_packet(8'hAA, 8'd2, 8'h77, 16'hFFFE,
                             32'h76543210, 33);
            end_case;
        end
    endtask

    task automatic run_parser_fault_recovery;
        begin
            begin_case("noise_prefix_recovery");
            run_noise_recovery();
            end_case;

            begin_case("version_error_recovery");
            issue_version_error();
            run_valid_packet(8'hA2, 8'd1, 8'hB3, 16'h3457,
                             32'h76543211, 35);
            end_case;

            begin_case("length_error_recovery");
            issue_length_error();
            run_valid_packet(8'hA3, 8'd2, 8'hB4, 16'h3458,
                             32'h76543212, 37);
            end_case;

            begin_case("crc_error_recovery");
            issue_crc_error();
            run_valid_packet(8'hA4, 8'd3, 8'hB5, 16'h3459,
                             32'h76543213, 39);
            end_case;
        end
    endtask

    task automatic run_line_faults;
        begin
            begin_case("overrun_discard");
            issue_overrun();
            run_valid_packet(8'hC6, 8'd2, 8'hD7, 16'h4567,
                             32'h89ABCDE0, 41);
            end_case;

            begin_case("bad_stop_header");
            issue_bad_stop(0, 8);
            run_valid_packet(8'hC7, 8'd1, 8'hD8, 16'h4568,
                             32'h89ABCDE1, 43);
            end_case;

            begin_case("bad_stop_payload");
            issue_bad_stop(12, 8);
            run_valid_packet(8'hC8, 8'd2, 8'hD9, 16'h4569,
                             32'h89ABCDE2, 45);
            end_case;

            begin_case("bad_stop_crc");
            issue_bad_stop(20, 8);
            run_valid_packet(8'hC9, 8'd3, 8'hDA, 16'h456A,
                             32'h89ABCDE3, 47);
            end_case;

            begin_case("false_start_header");
            issue_false_start(0, 8);
            run_valid_packet(8'hCA, 8'd1, 8'hDB, 16'h456B,
                             32'h89ABCDE4, 49);
            end_case;

            begin_case("false_start_payload");
            issue_false_start(14, 8);
            run_valid_packet(8'hCB, 8'd2, 8'hDC, 16'h456C,
                             32'h89ABCDE5, 51);
            end_case;

            begin_case("false_start_crc");
            issue_false_start(20, 8);
            run_valid_packet(8'hCC, 8'd3, 8'hDD, 16'h456D,
                             32'h89ABCDE6, 53);
            end_case;

            begin_case("held_cancel_post_low");
            run_held_cancel_post_low();
            end_case;

            begin_case("retired_before_later_error");
            run_retired_before_later_error();
            end_case;
        end
    endtask

    task automatic run_partition_matrix;
        begin
            begin_case("cancel_idle");
            issue_cancel_region(0, 8, 1'b0);
            run_valid_packet(8'hE1, 8'd0, 8'hF2, 16'h5679,
                             32'h13579BDF, 55);
            end_case;

            begin_case("cancel_header");
            issue_cancel_region(3, 8, 1'b0);
            run_valid_packet(8'hE2, 8'd1, 8'hF3, 16'h567A,
                             32'h13579BE0, 57);
            end_case;

            begin_case("cancel_metadata");
            issue_cancel_region(8, 8, 1'b0);
            run_valid_packet(8'hE3, 8'd2, 8'hF4, 16'h567B,
                             32'h13579BE1, 59);
            end_case;

            begin_case("cancel_payload");
            issue_cancel_region(14, 8, 1'b0);
            run_valid_packet(8'hE4, 8'd3, 8'hF5, 16'h567C,
                             32'h13579BE2, 61);
            end_case;

            begin_case("cancel_crc");
            issue_cancel_region(20, 8, 1'b0);
            run_valid_packet(8'hE5, 8'd4, 8'hF6, 16'h567D,
                             32'h13579BE3, 63);
            end_case;

            begin_case("cancel_completed");
            issue_cancel_region(0, 8, 1'b1);
            run_valid_packet(8'hE6, 8'd5, 8'hF7, 16'h567E,
                             32'h13579BE4, 65);
            end_case;

            begin_case("reset_idle");
            issue_reset_region(0, 8, 1'b0);
            run_valid_packet(8'hE7, 8'd0, 8'hF8, 16'h567F,
                             32'h13579BE5, 67);
            end_case;

            begin_case("reset_header");
            issue_reset_region(3, 8, 1'b0);
            run_valid_packet(8'hE8, 8'd1, 8'hF9, 16'h5680,
                             32'h13579BE6, 69);
            end_case;

            begin_case("reset_metadata");
            issue_reset_region(8, 8, 1'b0);
            run_valid_packet(8'hE9, 8'd2, 8'hFA, 16'h5681,
                             32'h13579BE7, 71);
            end_case;

            begin_case("reset_payload");
            issue_reset_region(14, 8, 1'b0);
            run_valid_packet(8'hEA, 8'd3, 8'hFB, 16'h5682,
                             32'h13579BE8, 73);
            end_case;

            begin_case("reset_crc");
            issue_reset_region(20, 8, 1'b0);
            run_valid_packet(8'hEB, 8'd4, 8'hFC, 16'h5683,
                             32'h13579BE9, 75);
            end_case;

            begin_case("reset_completed");
            issue_reset_region(0, 8, 1'b1);
            run_valid_packet(8'hEC, 8'd5, 8'hFD, 16'h5684,
                             32'h13579BEA, 77);
            end_case;
        end
    endtask

    task automatic run_stat2_suite;
        integer repeat_index;
        begin
            begin_case("stat2_base_saturation");
            for (repeat_index = 0; repeat_index < 3;
                 repeat_index = repeat_index + 1) begin
                run_valid_packet(8'(8'h10 + repeat_index), 8'd0,
                                 8'(8'h20 + repeat_index),
                                 16'(16'h3000 + repeat_index),
                                 32'(32'h40000000 + repeat_index),
                                 79 + repeat_index);
            end
            check_int(to_int(stat_uart_frames), 3, "stat2_uart_frames_base");
            check_int(to_int(stat_uart_retired), 3, "stat2_uart_retired_base");
            check_int(to_int(stat_bytes), 3, "stat2_bytes_base");
            check_int(to_int(stat_frames), 3, "stat2_frames_base");
            check_int(to_int(stat_retired), 3, "stat2_retired_base");
            end_case;

            begin_case("stat2_version_saturation");
            for (repeat_index = 0; repeat_index < 3;
                 repeat_index = repeat_index + 1) begin
                issue_version_error();
            end
            check_int(to_int(stat_version), 3, "stat2_version");
            end_case;

            begin_case("stat2_length_saturation");
            for (repeat_index = 0; repeat_index < 3;
                 repeat_index = repeat_index + 1) begin
                issue_length_error();
            end
            check_int(to_int(stat_length), 3, "stat2_length");
            end_case;

            begin_case("stat2_crc_saturation");
            for (repeat_index = 0; repeat_index < 3;
                 repeat_index = repeat_index + 1) begin
                issue_crc_error();
            end
            check_int(to_int(stat_crc), 3, "stat2_crc");
            end_case;

            begin_case("stat2_false_start_saturation");
            for (repeat_index = 0; repeat_index < 3;
                 repeat_index = repeat_index + 1) begin
                issue_false_start(0, 0);
            end
            check_int(to_int(stat_uart_false_starts), 3,
                      "stat2_false_starts");
            end_case;

            begin_case("stat2_framing_saturation");
            for (repeat_index = 0; repeat_index < 3;
                 repeat_index = repeat_index + 1) begin
                issue_bad_stop(0, 0);
            end
            check_int(to_int(stat_uart_framing), 3, "stat2_framing");
            end_case;

            begin_case("stat2_overrun_saturation");
            for (repeat_index = 0; repeat_index < 3;
                 repeat_index = repeat_index + 1) begin
                issue_overrun();
            end
            check_int(to_int(stat_uart_overruns), 3, "stat2_overruns");
            end_case;

            begin_case("stat2_all_saturated");
            check_int(to_int(stat_uart_frames), 3, "stat2_all_uart_frames");
            check_int(to_int(stat_uart_retired), 3, "stat2_all_uart_retired");
            check_int(to_int(stat_uart_overruns), 3, "stat2_all_uart_overruns");
            check_int(to_int(stat_uart_framing), 3, "stat2_all_uart_framing");
            check_int(to_int(stat_uart_false_starts), 3,
                      "stat2_all_uart_false_starts");
            check_int(to_int(stat_uart_aborted), 3, "stat2_all_uart_aborted");
            check_int(to_int(stat_bytes), 3, "stat2_all_bytes");
            check_int(to_int(stat_frames), 3, "stat2_all_frames");
            check_int(to_int(stat_retired), 3, "stat2_all_retired");
            check_int(to_int(stat_version), 3, "stat2_all_version");
            check_int(to_int(stat_length), 3, "stat2_all_length");
            check_int(to_int(stat_crc), 3, "stat2_all_crc");
            check_int(to_int(stat_aborted), 3, "stat2_all_aborted");
            end_case;
        end
    endtask

    task automatic run_full_suite;
        begin
            run_length_sweep();
            run_payload_and_adjacency();
            run_parser_fault_recovery();
            run_line_faults();
            run_partition_matrix();
        end
    endtask

    initial begin
        if (SUITE == SUITE_GUARD) begin
            repeat (8) @(posedge clk);
            $display("WIRE_RX_GUARD_MISSING");
            $fatal(1, "tb_uart_wire_rx: expected DUT parameter guard");
        end else begin
            case (SUITE)
                SUITE_DEFAULT: suite_name = "default";
                SUITE_FULL: suite_name = "full";
                SUITE_MIN_BAUD: suite_name = "min_baud";
                SUITE_FRACTIONAL: suite_name = "fractional";
                SUITE_STAT2: suite_name = "stat2";
                default: suite_name = "invalid_suite";
            endcase
            if (suite_name == "invalid_suite") begin
                $display("WIRE_RX_BAD_SUITE value=%0d", SUITE);
                $fatal(1, "tb_uart_wire_rx: invalid suite");
            end

            repeat (8) @(posedge clk);
            @(negedge clk);
            rst = 1'b0;
            repeat (6) @(posedge clk);
            out_ready = 1'b0;

            $display("WIRE_RX_BEGIN suite=%s clock_hz=%0d baud=%0d stat_w=%0d",
                     suite_name, CLOCK_HZ, BAUD, STAT_W);

            case (SUITE)
                SUITE_DEFAULT: begin
                    begin_case("default_bounded");
                    run_valid_packet(8'hD1, 8'd4, 8'hE2, 16'hA55A,
                                     32'h13572468, 81);
                    end_case;
                end
                SUITE_FULL: begin
                    run_full_suite();
                end
                SUITE_MIN_BAUD: begin
                    begin_case("min_baud_frame");
                    run_valid_packet(8'hD3, 8'd0, 8'hE4, 16'hC3D5,
                                     32'h24681357, 83);
                    end_case;
                end
                SUITE_FRACTIONAL: begin
                    begin_case("fractional_baud_frame");
                    run_valid_packet(8'hD5, 8'd32, 8'hE6, 16'hE7F8,
                                     32'hFFFFFFFF, 8'hA5);
                    end_case;
                end
                SUITE_STAT2: begin
                    run_stat2_suite();
                end
                default: begin
                    $fatal(1, "tb_uart_wire_rx: unreachable suite");
                end
            endcase

            $display("WIRE_RX_TALLY suite=%s cases=%0d checks=%0d failures=%0d",
                     suite_name, cases, checks, failures);
            if (failures == 0) begin
                $display("WIRE_RX_STATUS suite=%s result=PASS", suite_name);
                $finish;
            end else begin
                $display("WIRE_RX_STATUS suite=%s result=FAIL", suite_name);
                $fatal(1, "tb_uart_wire_rx: author checks failed");
            end
        end
    end

endmodule

`undef DEEPEYE_UART_WIRE_RX_STAT_W
`default_nettype wire
