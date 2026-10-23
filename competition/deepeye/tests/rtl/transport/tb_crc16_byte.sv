// Public-port tests for deepeye_crc16_byte.
//
// Work: B-CRC16-BYTE-20261024-27-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-CRC16-BYTE-20261024-27
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// The main sweep uses an author recurrence with the same polynomial algorithm.
// It is explicitly not an independent oracle. The published standard vector
// and the sampled binascii.crc_hqx constants provide external cross-checks.

`timescale 1ns/1ps
`default_nettype none

module tb_crc16_byte;

    logic [15:0] crc_in;
    logic [7:0]  data_in;
    logic [15:0] crc_out;

    deepeye_crc16_byte dut (
        .crc_in(crc_in),
        .data_in(data_in),
        .crc_out(crc_out)
    );

    integer checks = 0;
    integer failures = 0;
    integer cases = 0;
    integer pass_cases = 0;
    integer fail_cases = 0;
    integer case_checks = 0;
    string current_case = "";
    bit case_failed = 1'b0;

    longint stat_standard_bytes = 0;
    longint stat_empty_seed_calls = 0;
    longint stat_seed_matrix_vectors = 0;
    longint stat_state_byte_vectors = 0;
    longint stat_stream_bytes = 0;
    longint stat_contrast_vectors = 0;
    longint stat_external_vectors = 0;

    function automatic logic [15:0] crc_byte_reference(
        input logic [15:0] state,
        input logic [7:0]  value
    );
        integer bit_index;
        logic [15:0] working;
        begin
            working = state;
            for (bit_index = 7; bit_index >= 0; bit_index = bit_index - 1) begin
                if (working[15] ^ value[bit_index]) begin
                    working = (working << 1) ^ 16'h1021;
                end else begin
                    working = working << 1;
                end
            end
            crc_byte_reference = working;
        end
    endfunction

    function automatic logic [15:0] seed_at(input integer index);
        begin
            case (index)
                0: seed_at = 16'h0000;
                1: seed_at = 16'hFFFF;
                2: seed_at = 16'h1021;
                3: seed_at = 16'hA5C3;
                4: seed_at = 16'h1234;
                default: seed_at = 16'h8000;
            endcase
        end
    endfunction

    function automatic logic [7:0] selected_byte(input integer index);
        begin
            case (index)
                0: selected_byte = 8'h00;
                1: selected_byte = 8'hA5;
                default: selected_byte = 8'hFF;
            endcase
        end
    endfunction

    task automatic simple_check(input bit condition, input string label);
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if (condition !== 1'b1) begin
                failures = failures + 1;
                case_failed = 1'b1;
                $display("CHECK_FAIL case=%s name=%s", current_case, label);
            end
        end
    endtask

    task automatic begin_case(input string name);
        begin
            if (current_case != "") begin
                failures = failures + 1;
                $display("CHECK_FAIL case=%s name=nested_case", current_case);
            end
            current_case = name;
            case_failed = 1'b0;
            case_checks = 0;
            cases = cases + 1;
            $display("CASE_BEGIN name=%s", name);
        end
    endtask

    task automatic end_case();
        begin
            if (case_failed) begin
                fail_cases = fail_cases + 1;
                $display("CASE_END name=%s status=fail checks=%0d", current_case, case_checks);
            end else begin
                pass_cases = pass_cases + 1;
                $display("CASE_END name=%s status=pass checks=%0d", current_case, case_checks);
            end
            current_case = "";
        end
    endtask

    task automatic check_expected(
        input logic [15:0] seed,
        input logic [7:0]  value,
        input logic [15:0] expected
    );
        begin
            crc_in = seed;
            data_in = value;
            #1;
            checks = checks + 1;
            case_checks = case_checks + 1;
            if (crc_out !== expected) begin
                failures = failures + 1;
                case_failed = 1'b1;
                $display("CHECK_FAIL case=%s seed=%04x data=%02x actual=%04x expected=%04x",
                         current_case, seed, value, crc_out, expected);
            end
        end
    endtask

    task automatic check_reference(input logic [15:0] seed, input logic [7:0] value);
        begin
            check_expected(seed, value, crc_byte_reference(seed, value));
        end
    endtask

    task automatic case_standard_vector();
        integer index;
        logic [15:0] stream_state;
        begin
            begin_case("standard_vector");
            stream_state = 16'hFFFF;
            for (index = 0; index < 9; index = index + 1) begin
                check_reference(stream_state, 8'h31 + index[7:0]);
                stream_state = crc_out;
                stat_standard_bytes = stat_standard_bytes + 1;
            end
            simple_check((stream_state === 16'h29B1), "standard_check_value");
            end_case();
        end
    endtask

    task automatic case_zero_length_caller_seed();
        logic [15:0] caller_crc;
        integer caller_byte_calls;
        begin
            begin_case("zero_length_caller_seed");
            caller_crc = 16'hFFFF;
            caller_byte_calls = 0;
            simple_check((caller_crc === 16'hFFFF), "empty_message_seed_unchanged");
            simple_check((caller_byte_calls == 0), "empty_message_no_byte_update");
            stat_empty_seed_calls = caller_byte_calls;
            end_case();
        end
    endtask

    task automatic case_all_values_seed_matrix();
        integer seed_index;
        integer value_index;
        begin
            begin_case("all_values_seed_matrix");
            for (seed_index = 0; seed_index < 6; seed_index = seed_index + 1) begin
                for (value_index = 0; value_index < 256; value_index = value_index + 1) begin
                    check_reference(seed_at(seed_index), value_index[7:0]);
                    stat_seed_matrix_vectors = stat_seed_matrix_vectors + 1;
                end
            end
            end_case();
        end
    endtask

    task automatic case_all_states_selected_bytes();
        integer state_index;
        integer byte_index;
        begin
            begin_case("all_states_selected_bytes");
            for (state_index = 0; state_index < 65536; state_index = state_index + 1) begin
                for (byte_index = 0; byte_index < 3; byte_index = byte_index + 1) begin
                    check_reference(state_index[15:0], selected_byte(byte_index));
                    stat_state_byte_vectors = stat_state_byte_vectors + 1;
                end
            end
            end_case();
        end
    endtask

    task automatic case_stream_concatenation();
        integer value_index;
        logic [15:0] stream_state;
        begin
            begin_case("stream_concatenation");
            stream_state = 16'hFFFF;
            for (value_index = 0; value_index < 256; value_index = value_index + 1) begin
                check_reference(stream_state, value_index[7:0]);
                stream_state = crc_out;
                stat_stream_bytes = stat_stream_bytes + 1;
            end
            simple_check((stream_state === 16'h3FBD), "stream_library_final_state");
            end_case();
        end
    endtask

    task automatic case_bit_order_contrast();
        integer index;
        logic [15:0] seed;
        logic [15:0] msb_expected;
        logic [15:0] bit_reversed_expected;
        begin
            begin_case("bit_order_contrast");
            for (index = 0; index < 4; index = index + 1) begin
                seed = seed_at(index);
                msb_expected = crc_byte_reference(seed, 8'h01);
                bit_reversed_expected = crc_byte_reference(seed, 8'h80);
                check_expected(seed, 8'h01, msb_expected);
                simple_check((crc_out !== bit_reversed_expected), "msb_first_differs_from_reversed");
                stat_contrast_vectors = stat_contrast_vectors + 1;
            end
            end_case();
        end
    endtask

    task automatic case_external_library_spots();
        begin
            begin_case("external_library_spots");
            check_expected(16'h0000, 8'h00, 16'h0000); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'h0000, 8'h01, 16'h1021); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'h0000, 8'h80, 16'h9188); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'h0000, 8'hA5, 16'hE54F); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'h0000, 8'hFF, 16'h1EF0); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'hFFFF, 8'h00, 16'hE1F0); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'hFFFF, 8'h01, 16'hF1D1); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'hFFFF, 8'h80, 16'h7078); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'hFFFF, 8'hA5, 16'h04BF); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'hFFFF, 8'hFF, 16'hFF00); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'h1021, 8'h00, 16'h3331); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'h1021, 8'h01, 16'h2310); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'h1021, 8'h80, 16'hA2B9); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'h1021, 8'hA5, 16'hD67E); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'h1021, 8'hFF, 16'h2DC1); stat_external_vectors = stat_external_vectors + 1;
            check_expected(16'hA5C3, 8'h00, 16'h264F); stat_external_vectors = stat_external_vectors + 1;
            end_case();
        end
    endtask

    task automatic finish_tb();
        begin
            if (current_case != "") begin
                failures = failures + 1;
                $display("CHECK_FAIL case=%s name=no_open_case_at_finish", current_case);
            end
            $display("TB_STAT standard_bytes=%0d", stat_standard_bytes);
            $display("TB_STAT empty_seed_calls=%0d", stat_empty_seed_calls);
            $display("TB_STAT seed_matrix_vectors=%0d", stat_seed_matrix_vectors);
            $display("TB_STAT state_byte_vectors=%0d", stat_state_byte_vectors);
            $display("TB_STAT stream_bytes=%0d", stat_stream_bytes);
            $display("TB_STAT contrast_vectors=%0d", stat_contrast_vectors);
            $display("TB_STAT external_vectors=%0d", stat_external_vectors);
            $display("TB_SUMMARY cases=%0d pass=%0d fail=%0d checks=%0d",
                     cases, pass_cases, fail_cases, checks);
            if (failures == 0) begin
                $display("TB_END pass");
            end else begin
                $display("TB_END fail");
            end
            $finish;
        end
    endtask

    initial begin
        crc_in = 16'h0000;
        data_in = 8'h00;
        #1;
        $display("TB_BEGIN tb=tb_crc16_byte");
        case_standard_vector();
        case_zero_length_caller_seed();
        case_all_values_seed_matrix();
        case_all_states_selected_bytes();
        case_stream_concatenation();
        case_bit_order_contrast();
        case_external_library_spots();
        finish_tb();
    end

endmodule

`default_nettype wire
