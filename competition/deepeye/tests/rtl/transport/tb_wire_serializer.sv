// Public-port tests for deepeye_wire_serializer.
//
// Work: B-WIRE-SERIALIZER-20261024-28-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-WIRE-SERIALIZER-20261024-28
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// The local CRC reference uses the same CCITT-FALSE recurrence as the accepted
// CRC primitive.  It is an author cross-check, not an independent oracle.
// Fixed packet CRC constants below come from Python binascii.crc_hqx and are
// used only as external spot checks.

`timescale 1ns/1ps

module tb_wire_serializer;

    logic clk;
    initial clk = 1'b0;
    always #5 clk = ~clk;

    logic rst;
    logic cancel;
    logic cfg_valid;
    logic cfg_ready;
    logic [7:0] cfg_type;
    logic [7:0] cfg_epoch;
    logic [15:0] cfg_seq;
    logic [31:0] cfg_tick;
    logic [5:0] cfg_len;
    logic p_valid;
    logic p_ready;
    logic [7:0] p_data;
    logic p_last;
    logic out_valid;
    logic out_ready;
    logic [7:0] out_data;
    logic out_last;
    logic [5:0] out_count;
    logic busy;
    logic receiving;
    logic faulted;
    logic fault_event;
    logic [1:0] fault_code;
    logic [31:0] stat_admitted;
    logic [31:0] stat_sent;
    logic [31:0] stat_aborted;
    logic [31:0] stat_faults;

    logic s_rst;
    logic s_cancel;
    logic s_cfg_valid;
    logic s_cfg_ready;
    logic [7:0] s_cfg_type;
    logic [7:0] s_cfg_epoch;
    logic [15:0] s_cfg_seq;
    logic [31:0] s_cfg_tick;
    logic [5:0] s_cfg_len;
    logic s_p_valid;
    logic s_p_ready;
    logic [7:0] s_p_data;
    logic s_p_last;
    logic s_out_valid;
    logic s_out_ready;
    logic [7:0] s_out_data;
    logic s_out_last;
    logic [5:0] s_out_count;
    logic s_busy;
    logic s_receiving;
    logic s_faulted;
    logic s_fault_event;
    logic [1:0] s_fault_code;
    logic [1:0] s_stat_admitted;
    logic [1:0] s_stat_sent;
    logic [1:0] s_stat_aborted;
    logic [1:0] s_stat_faults;

    integer checks = 0;
    integer failures = 0;
    integer cases = 0;
    integer pass_cases = 0;
    integer fail_cases = 0;
    integer case_checks = 0;
    string current_case = "";
    bit case_failed = 1'b0;

    integer expected_admitted = 0;
    integer expected_sent = 0;
    integer expected_aborted = 0;
    integer expected_faults = 0;

    integer valid_frames = 0;
    integer lengths_covered = 0;
    integer byte_values_covered = 0;
    integer external_crc_vectors = 0;
    integer fault_cases = 0;
    integer fault_event_boundary_vectors = 0;
    integer cancel_phases = 0;
    integer reset_phases = 0;
    integer stall_cycles = 0;
    integer saturation_checks = 0;
    integer no_credit_checks = 0;
    integer max_field_vectors = 0;
    integer held_cancel_sequences = 0;
    integer reset_priority_checks = 0;

    bit length_seen [0:32];
    bit byte_seen [0:255];
    logic [7:0] frame_payload [0:31];
    logic [7:0] exp_packet [0:45];
    logic [15:0] exp_crc;
    integer exp_total;
    integer pseudo_state = 32'h1234_5678;

    integer s_expected_admitted = 0;
    integer s_expected_sent = 0;
    integer s_expected_aborted = 0;
    integer s_expected_faults = 0;

    deepeye_wire_serializer #(.STAT_W(32)) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .cfg_valid(cfg_valid),
        .cfg_ready(cfg_ready),
        .cfg_type(cfg_type),
        .cfg_epoch(cfg_epoch),
        .cfg_seq(cfg_seq),
        .cfg_tick(cfg_tick),
        .cfg_len(cfg_len),
        .p_valid(p_valid),
        .p_ready(p_ready),
        .p_data(p_data),
        .p_last(p_last),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_data(out_data),
        .out_last(out_last),
        .out_count(out_count),
        .busy(busy),
        .receiving(receiving),
        .faulted(faulted),
        .fault_event(fault_event),
        .fault_code(fault_code),
        .stat_admitted(stat_admitted),
        .stat_sent(stat_sent),
        .stat_aborted(stat_aborted),
        .stat_faults(stat_faults)
    );

    deepeye_wire_serializer #(.STAT_W(2)) dut_small (
        .clk(clk),
        .rst(s_rst),
        .cancel(s_cancel),
        .cfg_valid(s_cfg_valid),
        .cfg_ready(s_cfg_ready),
        .cfg_type(s_cfg_type),
        .cfg_epoch(s_cfg_epoch),
        .cfg_seq(s_cfg_seq),
        .cfg_tick(s_cfg_tick),
        .cfg_len(s_cfg_len),
        .p_valid(s_p_valid),
        .p_ready(s_p_ready),
        .p_data(s_p_data),
        .p_last(s_p_last),
        .out_valid(s_out_valid),
        .out_ready(s_out_ready),
        .out_data(s_out_data),
        .out_last(s_out_last),
        .out_count(s_out_count),
        .busy(s_busy),
        .receiving(s_receiving),
        .faulted(s_faulted),
        .fault_event(s_fault_event),
        .fault_code(s_fault_code),
        .stat_admitted(s_stat_admitted),
        .stat_sent(s_stat_sent),
        .stat_aborted(s_stat_aborted),
        .stat_faults(s_stat_faults)
    );

    function automatic bit pseudo_bit();
        begin
            pseudo_state = {pseudo_state[30:0],
                            pseudo_state[31] ^ pseudo_state[21] ^
                            pseudo_state[1] ^ pseudo_state[0]};
            pseudo_bit = pseudo_state[0];
        end
    endfunction

    function automatic logic [15:0] crc_byte_reference(
        input logic [15:0] state,
        input logic [7:0] value
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

    task automatic tick();
        begin
            @(posedge clk);
            #1;
        end
    endtask

    task automatic check(input bit condition, input string label);
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
            if (case_checks == 0) begin
                failures = failures + 1;
                case_failed = 1'b1;
                $display("CHECK_FAIL case=%s name=no_checks", current_case);
            end
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

    task automatic build_expected(
        input logic [7:0] typ,
        input logic [7:0] epoch,
        input logic [15:0] seq,
        input logic [31:0] tick_value,
        input logic [5:0] len
    );
        integer index;
        logic [15:0] crc;
        begin
            for (index = 0; index < 46; index = index + 1) begin
                exp_packet[index] = 8'h00;
            end
            exp_packet[0] = 8'hA5;
            exp_packet[1] = 8'h5A;
            exp_packet[2] = 8'h03;
            exp_packet[3] = typ;
            exp_packet[4] = {2'b00, len};
            exp_packet[5] = epoch;
            exp_packet[6] = seq[7:0];
            exp_packet[7] = seq[15:8];
            exp_packet[8] = tick_value[7:0];
            exp_packet[9] = tick_value[15:8];
            exp_packet[10] = tick_value[23:16];
            exp_packet[11] = tick_value[31:24];
            for (index = 0; index < len; index = index + 1) begin
                exp_packet[12 + index] = frame_payload[index];
            end
            crc = 16'hFFFF;
            for (index = 2; index < (12 + len); index = index + 1) begin
                crc = crc_byte_reference(crc, exp_packet[index]);
            end
            exp_crc = crc;
            exp_packet[12 + len] = crc[7:0];
            exp_packet[13 + len] = crc[15:8];
            exp_total = len + 14;
        end
    endtask

    task automatic mark_coverage(input logic [5:0] len);
        integer index;
        begin
            if (!length_seen[len[5:0]]) begin
                length_seen[len[5:0]] = 1'b1;
                lengths_covered = lengths_covered + 1;
            end
            for (index = 0; index < len; index = index + 1) begin
                if (!byte_seen[frame_payload[index]]) begin
                    byte_seen[frame_payload[index]] = 1'b1;
                    byte_values_covered = byte_values_covered + 1;
                end
            end
        end
    endtask

    task automatic wait_idle();
        integer guard;
        begin
            guard = 0;
            while (!cfg_ready && (guard < 100)) begin
                tick();
                guard = guard + 1;
            end
            check(guard < 100, "idle_timeout");
            check(cfg_ready == 1'b1, "cfg_ready_idle");
            check(busy == 1'b0, "busy_idle");
            check(out_valid == 1'b0, "out_valid_idle");
            check(stat_admitted == expected_admitted, "stat_admitted_idle");
            check(stat_sent == expected_sent, "stat_sent_idle");
            check(stat_aborted == expected_aborted, "stat_aborted_idle");
            check(stat_faults == expected_faults, "stat_faults_idle");
        end
    endtask

    task automatic drive_config(
        input logic [7:0] typ,
        input logic [7:0] epoch,
        input logic [15:0] seq,
        input logic [31:0] tick_value,
        input logic [5:0] len
    );
        begin
            cfg_valid = 1'b1;
            cfg_type = typ;
            cfg_epoch = epoch;
            cfg_seq = seq;
            cfg_tick = tick_value;
            cfg_len = len;
            check(cfg_ready == 1'b1, "cfg_ready_accept");
            check(out_valid == 1'b0, "no_same_edge_config_output");
            tick();
            cfg_valid = 1'b0;
        end
    endtask

    task automatic run_valid_frame(
        input logic [7:0] typ,
        input logic [7:0] epoch,
        input logic [15:0] seq,
        input logic [31:0] tick_value,
        input logic [5:0] len,
        input bit use_bubbles,
        input bit use_output_stalls,
        input bit use_metadata_noise,
        input bit use_no_credit
    );
        integer index;
        integer hold;
        integer total;
        begin
            build_expected(typ, epoch, seq, tick_value, len);
            wait_idle();
            check(out_count == 6'd0, "out_count_before_config");
            drive_config(typ, epoch, seq, tick_value, len);
            expected_admitted = expected_admitted + 1;

            check(busy == 1'b1, "busy_after_config");
            check(receiving == (len != 0), "receiving_after_config");
            check(faulted == 1'b0, "faulted_after_config");
            check(out_count == (6'd14 + len), "out_count_after_config");
            check(stat_admitted == expected_admitted, "stat_admitted_after_config");
            check(cfg_ready == 1'b0, "cfg_ready_busy");
            mark_coverage(len);

            if (len == 6'd0) begin
                check(p_ready == 1'b0, "p_ready_zero_length");
                check(out_valid == 1'b1, "out_valid_zero_length");
                check(out_data == 8'hA5, "out_data_zero_length");
            end else begin
                check(p_ready == 1'b1, "p_ready_receive");
                check(out_valid == 1'b0, "out_valid_receive");
            end

            if (use_metadata_noise) begin
                cfg_valid = 1'b1;
                cfg_type = 8'hEE;
                cfg_epoch = 8'hDD;
                cfg_seq = 16'hCBCB;
                cfg_tick = 32'h12345678;
                cfg_len = 6'd1;
                check(cfg_ready == 1'b0, "metadata_noise_ready_low");
                tick();
                cfg_valid = 1'b0;
                check(busy == 1'b1, "metadata_noise_busy");
                stall_cycles = stall_cycles + 1;
            end

            if (len != 6'd0) begin
                for (index = 0; index < len; index = index + 1) begin
                    if (use_bubbles && pseudo_bit()) begin
                        p_valid = 1'b0;
                        hold = 1 + pseudo_bit();
                        repeat (hold) begin
                            tick();
                            check(p_ready == 1'b1, "p_ready_bubble");
                            check(out_valid == 1'b0, "out_valid_bubble");
                            stall_cycles = stall_cycles + 1;
                        end
                    end
                    check(p_ready == 1'b1, "p_ready_pre");
                    p_valid = 1'b1;
                    p_data = frame_payload[index];
                    p_last = (index == (len - 1));
                    check(p_ready == 1'b1, "p_ready_accept");
                    check(out_valid == 1'b0, "no_same_edge_payload_output");
                    tick();
                    p_valid = 1'b0;
                    p_last = 1'b0;

                    if (index == (len - 1)) begin
                        check(busy == 1'b1, "busy_after_last_payload");
                        check(receiving == 1'b0, "receiving_after_last_payload");
                        check(out_valid == 1'b1, "out_valid_after_last_payload");
                        check(out_count == (6'd14 + len), "out_count_after_last_payload");
                        check(out_data == 8'hA5, "out_data_after_last_payload");
                    end else begin
                        check(receiving == 1'b1, "receiving_mid_payload");
                        check(out_valid == 1'b0, "out_valid_mid_payload");
                    end
                end
            end

            total = len + 14;
            out_ready = 1'b0;
            for (index = 0; index < total; index = index + 1) begin
                check(out_valid == 1'b1, "out_valid_output");
                check(out_count == (len + 14), "out_count_output");
                check(out_data == exp_packet[index], "out_data_output");
                check(out_last == (index == (total - 1)), "out_last_output");
                check(busy == 1'b1, "busy_output");

                if (use_output_stalls && ((index == 0) || pseudo_bit())) begin
                    hold = 1 + pseudo_bit();
                    repeat (hold) begin
                        tick();
                        check(out_valid == 1'b1, "out_valid_stall");
                        check(out_data == exp_packet[index], "out_data_stall");
                        check(out_last == (index == (total - 1)), "out_last_stall");
                        check(out_count == (len + 14), "out_count_stall");
                        stall_cycles = stall_cycles + 1;
                    end
                end

                check(cfg_ready == 1'b0, "cfg_ready_output");
                check(p_ready == 1'b0, "p_ready_output");
                out_ready = 1'b1;
                if (use_no_credit && (index == (total - 1))) begin
                    cfg_valid = 1'b1;
                    cfg_type = 8'hEE;
                    cfg_epoch = 8'hDD;
                    cfg_seq = 16'hCBCB;
                    cfg_tick = 32'h12345678;
                    cfg_len = 6'd1;
                    check(cfg_ready == 1'b0, "no_credit_ready_low");
                end
                tick();
                out_ready = 1'b0;

                if (use_no_credit && (index == (total - 1))) begin
                    cfg_valid = 1'b0;
                    check(busy == 1'b0, "no_credit_busy_low");
                    check(out_valid == 1'b0, "no_credit_out_low");
                    check(cfg_ready == 1'b1, "no_credit_ready_next");
                    check(stat_admitted == expected_admitted, "no_credit_admitted");
                    no_credit_checks = no_credit_checks + 1;
                end

                if (index == (total - 1)) begin
                    expected_sent = expected_sent + 1;
                    check(busy == 1'b0, "busy_after_final_output");
                    check(out_valid == 1'b0, "out_valid_after_final_output");
                    check(out_count == 6'd0, "out_count_after_final_output");
                    check(stat_sent == expected_sent, "stat_sent_after_final_output");
                end else begin
                    check(out_valid == 1'b1, "out_valid_after_handshake");
                    check(out_count == (len + 14), "out_count_after_handshake");
                end
            end

            check(stat_admitted == expected_admitted, "stat_admitted_final");
            check(stat_sent == expected_sent, "stat_sent_final");
            check(stat_aborted == expected_aborted, "stat_aborted_final");
            check(stat_faults == expected_faults, "stat_faults_final");
            valid_frames = valid_frames + 1;
        end
    endtask

    task automatic clear_fault_with_held_cancel();
        begin
            cancel = 1'b1;
            check(out_valid == 1'b0, "fault_cancel_out_gate");
            check(cfg_ready == 1'b0, "fault_cancel_cfg_gate");
            check(p_ready == 1'b0, "fault_cancel_p_gate");
            tick();
            expected_aborted = expected_aborted + 1;
            held_cancel_sequences = held_cancel_sequences + 1;
            check(busy == 1'b0, "fault_cancel_busy_low");
            check(faulted == 1'b0, "fault_cancel_faulted_low");
            check(fault_code == 2'd0, "fault_cancel_code_zero");
            check(out_count == 6'd0, "fault_cancel_count_zero");
            check(stat_aborted == expected_aborted, "fault_cancel_aborted");
            check(stat_admitted == expected_admitted, "fault_cancel_admitted");
            check(stat_sent == expected_sent, "fault_cancel_sent");
            repeat (2) begin
                tick();
                check(stat_aborted == expected_aborted, "held_cancel_counts_once");
            end
            cancel = 1'b0;
            tick();
            check(cfg_ready == 1'b1, "fault_cancel_released");
        end
    endtask

    task automatic run_illegal_length_fault(input logic [5:0] len);
        begin
            wait_idle();
            drive_config(8'h11, 8'h22, 16'h3344, 32'h55667788, len);
            expected_admitted = expected_admitted + 1;
            expected_faults = expected_faults + 1;
            fault_cases = fault_cases + 1;
            check(busy == 1'b1, "illegal_busy");
            check(receiving == 1'b0, "illegal_receiving_low");
            check(faulted == 1'b1, "illegal_faulted");
            check(fault_event == 1'b1, "illegal_event_pulse");
            check(fault_code == 2'd1, "illegal_code");
            check(out_valid == 1'b0, "illegal_out_valid_low");
            check(out_count == 6'd0, "illegal_out_count_zero");
            check(cfg_ready == 1'b0, "illegal_cfg_ready_low");
            check(p_ready == 1'b0, "illegal_p_ready_low");
            check(stat_admitted == expected_admitted, "illegal_admitted");
            check(stat_faults == expected_faults, "illegal_faults");
            tick();
            check(faulted == 1'b1, "illegal_faulted_sticky");
            check(fault_event == 1'b0, "illegal_event_one_cycle");
            check(fault_code == 2'd1, "illegal_code_sticky");
            check(busy == 1'b1, "illegal_busy_hold");
            check(out_count == 6'd0, "illegal_count_hold");
            clear_fault_with_held_cancel();
        end
    endtask

    task automatic run_payload_fault(
        input logic [5:0] len,
        input integer fault_index,
        input bit bad_last_value
    );
        integer index;
        begin
            build_expected(8'h31, 8'h32, 16'h3344, 32'h55667788, len);
            wait_idle();
            drive_config(8'h31, 8'h32, 16'h3344, 32'h55667788, len);
            expected_admitted = expected_admitted + 1;
            check(busy == 1'b1, "payload_fault_busy");
            check(receiving == 1'b1, "payload_fault_receiving");
            check(out_count == (6'd14 + len), "payload_fault_count_init");

            for (index = 0; index <= fault_index; index = index + 1) begin
                check(p_ready == 1'b1, "payload_fault_p_ready");
                p_valid = 1'b1;
                p_data = frame_payload[index];
                if (index == fault_index) begin
                    p_last = bad_last_value;
                end else begin
                    p_last = (index == (len - 1));
                end
                tick();
                p_valid = 1'b0;
                p_last = 1'b0;
                if (index < fault_index) begin
                    check(receiving == 1'b1, "payload_fault_prior_receiving");
                end
            end

            expected_faults = expected_faults + 1;
            fault_cases = fault_cases + 1;
            check(busy == 1'b1, "payload_fault_busy_after");
            check(receiving == 1'b0, "payload_fault_receiving_after");
            check(faulted == 1'b1, "payload_fault_faulted");
            check(fault_event == 1'b1, "payload_fault_event");
            check(fault_code == 2'd2, "payload_fault_code");
            check(out_valid == 1'b0, "payload_fault_out_valid_low");
            check(out_count == (6'd14 + len), "payload_fault_count_hold");
            check(stat_admitted == expected_admitted, "payload_fault_admitted");
            check(stat_faults == expected_faults, "payload_fault_faults");
            tick();
            check(faulted == 1'b1, "payload_fault_sticky");
            check(fault_event == 1'b0, "payload_fault_event_one_cycle");
            check(fault_code == 2'd2, "payload_fault_code_sticky");
            check(busy == 1'b1, "payload_fault_busy_sticky");
            check(out_count == (6'd14 + len), "payload_fault_count_stable");
            clear_fault_with_held_cancel();
        end
    endtask

    task automatic run_fault_event_ordinary();
        begin
            wait_idle();
            drive_config(8'h61, 8'h62, 16'h6364, 32'h65666768, 6'd33);
            expected_admitted = expected_admitted + 1;
            expected_faults = expected_faults + 1;
            fault_cases = fault_cases + 1;
            fault_event_boundary_vectors = fault_event_boundary_vectors + 1;
            check(busy == 1'b1, "ordinary_event_busy");
            check(faulted == 1'b1, "ordinary_event_faulted");
            check(fault_event == 1'b1, "ordinary_event_registered");
            check(fault_code == 2'd1, "ordinary_event_code");
            check(stat_admitted == expected_admitted, "ordinary_event_admitted");
            check(stat_faults == expected_faults, "ordinary_event_faults");

            @(negedge clk);
            #1;
            check(fault_event == 1'b1, "ordinary_pre_rise_event");
            check(faulted == 1'b1, "ordinary_pre_rise_faulted");
            check(stat_admitted == expected_admitted, "ordinary_pre_rise_admitted");
            check(stat_aborted == expected_aborted, "ordinary_pre_rise_aborted");
            check(stat_faults == expected_faults, "ordinary_pre_rise_faults");
            tick();
            check(fault_event == 1'b0, "ordinary_post_rise_event_clear");
            check(faulted == 1'b1, "ordinary_post_rise_faulted_sticky");
            check(fault_code == 2'd1, "ordinary_post_rise_code_sticky");
            check(busy == 1'b1, "ordinary_post_rise_busy_sticky");
            check(stat_faults == expected_faults, "ordinary_post_rise_faults");
            clear_fault_with_held_cancel();
        end
    endtask

    task automatic run_fault_event_cancel_boundary();
        begin
            wait_idle();
            drive_config(8'h71, 8'h72, 16'h7374, 32'h75767778, 6'd33);
            expected_admitted = expected_admitted + 1;
            expected_faults = expected_faults + 1;
            fault_cases = fault_cases + 1;
            fault_event_boundary_vectors = fault_event_boundary_vectors + 1;
            check(busy == 1'b1, "cancel_event_busy");
            check(faulted == 1'b1, "cancel_event_faulted");
            check(fault_event == 1'b1, "cancel_event_registered");
            check(fault_code == 2'd1, "cancel_event_code");
            check(stat_admitted == expected_admitted, "cancel_event_admitted");
            check(stat_faults == expected_faults, "cancel_event_faults");

            @(negedge clk);
            cancel = 1'b1;
            #1;
            check(fault_event == 1'b1, "cancel_pre_rise_event");
            check(stat_admitted == expected_admitted, "cancel_pre_rise_admitted");
            check(stat_sent == expected_sent, "cancel_pre_rise_sent");
            check(stat_aborted == expected_aborted, "cancel_pre_rise_aborted");
            check(stat_faults == expected_faults, "cancel_pre_rise_faults");
            check(cfg_ready == 1'b0, "cancel_pre_rise_cfg_gate");
            check(p_ready == 1'b0, "cancel_pre_rise_p_gate");
            check(out_valid == 1'b0, "cancel_pre_rise_out_gate");
            tick();
            expected_aborted = expected_aborted + 1;
            held_cancel_sequences = held_cancel_sequences + 1;
            check(fault_event == 1'b0, "cancel_post_rise_event_clear");
            check(faulted == 1'b0, "cancel_post_rise_faulted_clear");
            check(fault_code == 2'd0, "cancel_post_rise_code_clear");
            check(busy == 1'b0, "cancel_post_rise_busy_clear");
            check(out_count == 6'd0, "cancel_post_rise_count_clear");
            check(stat_aborted == expected_aborted, "cancel_post_rise_aborted");
            check(stat_sent == expected_sent, "cancel_post_rise_sent");
            check(stat_admitted == expected_admitted, "cancel_post_rise_admitted");
            check(stat_faults == expected_faults, "cancel_post_rise_faults");
            check(cfg_ready == 1'b0, "cancel_held_cfg_gate");
            check(p_ready == 1'b0, "cancel_held_p_gate");
            check(out_valid == 1'b0, "cancel_held_out_gate");
            tick();
            check(stat_aborted == expected_aborted, "cancel_held_counts_once");
            cancel = 1'b0;
            tick();
            check(cfg_ready == 1'b1, "cancel_event_released");
        end
    endtask

    task automatic run_fault_event_reset_boundary();
        begin
            wait_idle();
            drive_config(8'h81, 8'h82, 16'h8384, 32'h85868788, 6'd33);
            expected_admitted = expected_admitted + 1;
            expected_faults = expected_faults + 1;
            fault_cases = fault_cases + 1;
            fault_event_boundary_vectors = fault_event_boundary_vectors + 1;
            check(busy == 1'b1, "reset_event_busy");
            check(faulted == 1'b1, "reset_event_faulted");
            check(fault_event == 1'b1, "reset_event_registered");
            check(fault_code == 2'd1, "reset_event_code");
            check(stat_admitted == expected_admitted, "reset_event_admitted");
            check(stat_faults == expected_faults, "reset_event_faults");

            @(negedge clk);
            rst = 1'b1;
            #1;
            check(fault_event == 1'b1, "reset_pre_rise_event");
            check(stat_admitted == expected_admitted, "reset_pre_rise_admitted");
            check(stat_sent == expected_sent, "reset_pre_rise_sent");
            check(stat_aborted == expected_aborted, "reset_pre_rise_aborted");
            check(stat_faults == expected_faults, "reset_pre_rise_faults");
            check(cfg_ready == 1'b0, "reset_pre_rise_cfg_gate");
            check(p_ready == 1'b0, "reset_pre_rise_p_gate");
            check(out_valid == 1'b0, "reset_pre_rise_out_gate");
            tick();
            expected_admitted = 0;
            expected_sent = 0;
            expected_aborted = 0;
            expected_faults = 0;
            check(fault_event == 1'b0, "reset_post_rise_event_clear");
            check(faulted == 1'b0, "reset_post_rise_faulted_clear");
            check(fault_code == 2'd0, "reset_post_rise_code_clear");
            check(busy == 1'b0, "reset_post_rise_busy_clear");
            check(out_count == 6'd0, "reset_post_rise_count_clear");
            check(stat_admitted == 0, "reset_post_rise_admitted_zero");
            check(stat_sent == 0, "reset_post_rise_sent_zero");
            check(stat_aborted == 0, "reset_post_rise_aborted_zero");
            check(stat_faults == 0, "reset_post_rise_faults_zero");
            check(cfg_ready == 1'b0, "reset_held_cfg_gate");
            check(p_ready == 1'b0, "reset_held_p_gate");
            check(out_valid == 1'b0, "reset_held_out_gate");
            rst = 1'b0;
            tick();
            check(cfg_ready == 1'b1, "reset_event_released");
        end
    endtask

    task automatic consume_expected_byte(input integer index);
        begin
            check(out_valid == 1'b1, "consume_out_valid");
            check(out_data == exp_packet[index], "consume_out_data");
            check(out_last == (index == (exp_total - 1)), "consume_out_last");
            check(out_count == exp_total[5:0], "consume_out_count");
            out_ready = 1'b1;
            tick();
            out_ready = 1'b0;
        end
    endtask

    task automatic start_frame_and_payload(input logic [5:0] len);
        integer index;
        begin
            build_expected(8'h41, 8'h42, 16'h4344, 32'h45464748, len);
            wait_idle();
            drive_config(8'h41, 8'h42, 16'h4344, 32'h45464748, len);
            expected_admitted = expected_admitted + 1;
            check(busy == 1'b1, "phase_busy");
            for (index = 0; index < len; index = index + 1) begin
                check(p_ready == 1'b1, "phase_p_ready");
                p_valid = 1'b1;
                p_data = frame_payload[index];
                p_last = (index == (len - 1));
                tick();
                p_valid = 1'b0;
                p_last = 1'b0;
            end
            check(out_valid == 1'b1, "phase_out_valid");
            check(out_count == exp_total[5:0], "phase_out_count");
        end
    endtask

    task automatic start_config_only(input logic [5:0] len);
        begin
            build_expected(8'h41, 8'h42, 16'h4344, 32'h45464748, len);
            wait_idle();
            drive_config(8'h41, 8'h42, 16'h4344, 32'h45464748, len);
            expected_admitted = expected_admitted + 1;
            check(busy == 1'b1, "config_only_busy");
            check(receiving == 1'b1, "config_only_receiving");
            check(out_valid == 1'b0, "config_only_out_low");
            check(out_count == exp_total[5:0], "config_only_out_count");
        end
    endtask

    task automatic run_cancel_phase(input logic [5:0] len, input integer consume_count);
        integer index;
        begin
            if (consume_count == 0) begin
                start_config_only(len);
            end else begin
                start_frame_and_payload(len);
            end
            cancel_phases = cancel_phases + 1;
            if (consume_count == 0) begin
                check(receiving == 1'b1, "cancel_receive_phase");
                check(out_valid == 1'b0, "cancel_receive_no_output");
            end else begin
                for (index = 0; index < consume_count; index = index + 1) begin
                    consume_expected_byte(index);
                end
                check(out_valid == 1'b1, "cancel_phase_output_pending");
                check(out_data == exp_packet[consume_count], "cancel_phase_next_byte");
            end
            cancel = 1'b1;
            #1;
            check(out_valid == 1'b0, "cancel_out_gate");
            check(cfg_ready == 1'b0, "cancel_cfg_gate");
            check(p_ready == 1'b0, "cancel_p_gate");
            tick();
            expected_aborted = expected_aborted + 1;
            held_cancel_sequences = held_cancel_sequences + 1;
            check(busy == 1'b0, "cancel_busy_low");
            check(out_count == 6'd0, "cancel_count_zero");
            check(stat_aborted == expected_aborted, "cancel_aborted");
            check(stat_sent == expected_sent, "cancel_sent_preserved");
            check(stat_admitted == expected_admitted, "cancel_admitted_preserved");
            check(stat_faults == expected_faults, "cancel_faults_preserved");
            repeat (2) begin
                tick();
                check(stat_aborted == expected_aborted, "cancel_held_once");
            end
            cancel = 1'b0;
            tick();
            check(cfg_ready == 1'b1, "cancel_released");
        end
    endtask

    task automatic run_reset_phase(
        input logic [5:0] len,
        input integer consume_count,
        input bit simultaneous_cancel
    );
        integer index;
        begin
            if (consume_count == 0) begin
                start_config_only(len);
            end else begin
                start_frame_and_payload(len);
            end
            reset_phases = reset_phases + 1;
            if (consume_count == 0) begin
                check(receiving == 1'b1, "reset_receive_phase");
                check(out_valid == 1'b0, "reset_receive_no_output");
            end else begin
                for (index = 0; index < consume_count; index = index + 1) begin
                    consume_expected_byte(index);
                end
                check(out_valid == 1'b1, "reset_phase_output_pending");
                check(out_data == exp_packet[consume_count], "reset_phase_next_byte");
            end
            rst = 1'b1;
            if (simultaneous_cancel) begin
                cancel = 1'b1;
                reset_priority_checks = reset_priority_checks + 1;
            end
            #1;
            check(out_valid == 1'b0, "reset_out_gate");
            check(cfg_ready == 1'b0, "reset_cfg_gate");
            check(p_ready == 1'b0, "reset_p_gate");
            tick();
            expected_admitted = 0;
            expected_sent = 0;
            expected_aborted = 0;
            expected_faults = 0;
            check(busy == 1'b0, "reset_busy_low");
            check(receiving == 1'b0, "reset_receiving_low");
            check(faulted == 1'b0, "reset_faulted_low");
            check(fault_event == 1'b0, "reset_event_low");
            check(fault_code == 2'd0, "reset_code_zero");
            check(out_count == 6'd0, "reset_count_zero");
            check(out_valid == 1'b0, "reset_out_valid_low");
            check(stat_admitted == 0, "reset_admitted_zero");
            check(stat_sent == 0, "reset_sent_zero");
            check(stat_aborted == 0, "reset_aborted_zero");
            check(stat_faults == 0, "reset_faults_zero");
            tick();
            check(stat_aborted == 0, "reset_held_no_aborted");
            rst = 1'b0;
            cancel = 1'b0;
            tick();
            check(cfg_ready == 1'b1, "reset_released");
        end
    endtask

    task automatic small_wait_idle();
        integer guard;
        begin
            guard = 0;
            while (!s_cfg_ready && (guard < 100)) begin
                tick();
                guard = guard + 1;
            end
            check(guard < 100, "small_idle_timeout");
            check(s_cfg_ready == 1'b1, "small_cfg_ready");
            check(s_busy == 1'b0, "small_busy_low");
            check(s_out_valid == 1'b0, "small_out_valid_low");
        end
    endtask

    task automatic small_run_zero_frame(
        input logic [7:0] typ,
        input logic [7:0] epoch,
        input logic [15:0] seq,
        input logic [31:0] tick_value
    );
        integer index;
        begin
            build_expected(typ, epoch, seq, tick_value, 6'd0);
            small_wait_idle();
            s_cfg_valid = 1'b1;
            s_cfg_type = typ;
            s_cfg_epoch = epoch;
            s_cfg_seq = seq;
            s_cfg_tick = tick_value;
            s_cfg_len = 6'd0;
            check(s_cfg_ready == 1'b1, "small_cfg_accept");
            tick();
            s_cfg_valid = 1'b0;
            if (s_expected_admitted < 3) s_expected_admitted = s_expected_admitted + 1;
            check(s_busy == 1'b1, "small_busy_after_config");
            check(s_out_valid == 1'b1, "small_out_valid_zero");
            check(s_out_count == 6'd14, "small_out_count_zero");
            check(s_stat_admitted == s_expected_admitted, "small_admitted");
            for (index = 0; index < 14; index = index + 1) begin
                check(s_out_valid == 1'b1, "small_out_valid");
                check(s_out_data == exp_packet[index], "small_out_data");
                check(s_out_last == (index == 13), "small_out_last");
                check(s_out_count == 6'd14, "small_out_count");
                s_out_ready = 1'b1;
                tick();
                s_out_ready = 1'b0;
            end
            if (s_expected_sent < 3) s_expected_sent = s_expected_sent + 1;
            check(s_busy == 1'b0, "small_busy_after_frame");
            check(s_out_valid == 1'b0, "small_out_valid_after_frame");
            check(s_out_count == 6'd0, "small_out_count_after_frame");
            check(s_stat_sent == s_expected_sent, "small_sent");
            if (s_expected_admitted < 3) begin
                check(s_stat_admitted == (s_stat_sent + s_stat_aborted + s_busy),
                      "small_invariant_before_saturation");
            end
            if (s_stat_admitted == 2'd3) saturation_checks = saturation_checks + 1;
            if (s_stat_sent == 2'd3) saturation_checks = saturation_checks + 1;
        end
    endtask

    task automatic small_fault_cancel(input integer iteration);
        begin
            small_wait_idle();
            s_cfg_valid = 1'b1;
            s_cfg_type = 8'h71;
            s_cfg_epoch = 8'h72;
            s_cfg_seq = 16'h7374;
            s_cfg_tick = 32'h75767778;
            s_cfg_len = 6'd33;
            check(s_cfg_ready == 1'b1, "small_fault_cfg_accept");
            tick();
            s_cfg_valid = 1'b0;
            if (s_expected_admitted < 3) s_expected_admitted = s_expected_admitted + 1;
            if (s_expected_faults < 3) s_expected_faults = s_expected_faults + 1;
            check(s_busy == 1'b1, "small_fault_busy");
            check(s_faulted == 1'b1, "small_fault_faulted");
            check(s_fault_event == 1'b1, "small_fault_event");
            check(s_fault_code == 2'd1, "small_fault_code");
            check(s_out_valid == 1'b0, "small_fault_out_low");
            check(s_out_count == 6'd0, "small_fault_count_zero");
            check(s_stat_admitted == s_expected_admitted, "small_fault_admitted");
            check(s_stat_faults == s_expected_faults, "small_fault_faults");
            check(s_stat_sent == s_expected_sent, "small_fault_sent_preserved");
            if (s_stat_admitted == 2'd3) saturation_checks = saturation_checks + 1;
            if (s_stat_sent == 2'd3) saturation_checks = saturation_checks + 1;
            if (s_stat_faults == 2'd3) saturation_checks = saturation_checks + 1;
            s_cancel = 1'b1;
            tick();
            if (s_expected_aborted < 3) s_expected_aborted = s_expected_aborted + 1;
            s_cancel = 1'b0;
            check(s_busy == 1'b0, "small_cancel_busy");
            check(s_faulted == 1'b0, "small_cancel_faulted_low");
            check(s_stat_aborted == s_expected_aborted, "small_cancel_aborted");
            check(s_stat_admitted == s_expected_admitted, "small_cancel_admitted");
            check(s_stat_sent == s_expected_sent, "small_cancel_sent");
            check(s_stat_faults == s_expected_faults, "small_cancel_faults");
            if (s_stat_aborted == 2'd3) saturation_checks = saturation_checks + 1;
            if (s_stat_faults == 2'd3) saturation_checks = saturation_checks + 1;
            tick();
            check(s_cfg_ready == 1'b1, "small_cancel_released");
        end
    endtask

    initial begin
        rst = 1'b0;
        cancel = 1'b0;
        cfg_valid = 1'b0;
        cfg_type = 8'h00;
        cfg_epoch = 8'h00;
        cfg_seq = 16'h0000;
        cfg_tick = 32'h00000000;
        cfg_len = 6'd0;
        p_valid = 1'b0;
        p_data = 8'h00;
        p_last = 1'b0;
        out_ready = 1'b0;

        s_rst = 1'b0;
        s_cancel = 1'b0;
        s_cfg_valid = 1'b0;
        s_cfg_type = 8'h00;
        s_cfg_epoch = 8'h00;
        s_cfg_seq = 16'h0000;
        s_cfg_tick = 32'h00000000;
        s_cfg_len = 6'd0;
        s_p_valid = 1'b0;
        s_p_data = 8'h00;
        s_p_last = 1'b0;
        s_out_ready = 1'b0;

        #1;
        $display("TB_BEGIN tb=tb_wire_serializer");

        begin_case("initial_reset");
        rst = 1'b1;
        s_rst = 1'b1;
        repeat (2) tick();
        check(busy == 1'b0, "init_busy");
        check(receiving == 1'b0, "init_receiving");
        check(faulted == 1'b0, "init_faulted");
        check(out_valid == 1'b0, "init_out_valid");
        check(out_count == 6'd0, "init_out_count");
        check(stat_admitted == 0, "init_admitted");
        check(stat_sent == 0, "init_sent");
        check(stat_aborted == 0, "init_aborted");
        check(stat_faults == 0, "init_faults");
        check(s_busy == 1'b0, "init_small_busy");
        check(s_stat_admitted == 0, "init_small_admitted");
        rst = 1'b0;
        s_rst = 1'b0;
        tick();
        check(cfg_ready == 1'b1, "init_cfg_ready");
        check(s_cfg_ready == 1'b1, "init_small_cfg_ready");
        end_case();

        begin_case("length_and_byte_sweep");
        for (integer frame_len = 0; frame_len <= 32; frame_len = frame_len + 1) begin
            for (integer b = 0; b < 32; b = b + 1) begin
                frame_payload[b] = (frame_len * 11 + b * 7 + 3) & 8'hFF;
            end
            run_valid_frame(
                8'h20 + frame_len[7:0],
                8'h40 + frame_len[7:0],
                16'h1000 + frame_len[15:0],
                32'h01020304 + frame_len[31:0],
                frame_len[5:0],
                1'b0, 1'b0, 1'b0, (frame_len == 0)
            );
        end
        for (integer base = 0; base < 8; base = base + 1) begin
            for (integer b = 0; b < 32; b = b + 1) begin
                frame_payload[b] = (base * 32 + b) & 8'hFF;
            end
            if (base == 0) begin
                max_field_vectors = max_field_vectors + 1;
                run_valid_frame(8'hFF, 8'hAA, 16'hFFFF, 32'hFFFFFFFF, 6'd32,
                                1'b1, 1'b1, 1'b0, 1'b0);
            end else begin
                run_valid_frame(8'h80 + base[7:0], 8'h90 + base[7:0],
                                16'h2000 + base[15:0], 32'h02030405 + base[31:0],
                                6'd32, (base == 1), (base == 2), (base == 3), 1'b0);
            end
        end
        end_case();

        begin_case("external_crc_spots");
        build_expected(8'h00, 8'h00, 16'h0000, 32'h00000000, 6'd0);
        check(exp_crc == 16'h50F6, "external_zero_crc");
        external_crc_vectors = external_crc_vectors + 1;
        run_valid_frame(8'h00, 8'h00, 16'h0000, 32'h00000000, 6'd0,
                        1'b0, 1'b0, 1'b0, 1'b0);

        build_expected(8'hFF, 8'hAA, 16'hFFFF, 32'hFFFFFFFF, 6'd0);
        check(exp_crc == 16'h7D55, "external_max_crc");
        external_crc_vectors = external_crc_vectors + 1;
        max_field_vectors = max_field_vectors + 1;
        run_valid_frame(8'hFF, 8'hAA, 16'hFFFF, 32'hFFFFFFFF, 6'd0,
                        1'b0, 1'b0, 1'b0, 1'b0);

        frame_payload[0] = 8'h00;
        build_expected(8'h01, 8'h02, 16'h1234, 32'h89ABCDEF, 6'd1);
        check(exp_crc == 16'h9600, "external_one_crc");
        external_crc_vectors = external_crc_vectors + 1;
        run_valid_frame(8'h01, 8'h02, 16'h1234, 32'h89ABCDEF, 6'd1,
                        1'b0, 1'b0, 1'b0, 1'b0);

        frame_payload[0] = 8'h31;
        frame_payload[1] = 8'h32;
        frame_payload[2] = 8'h33;
        build_expected(8'h05, 8'h06, 16'hABCD, 32'h01020304, 6'd3);
        check(exp_crc == 16'hA610, "external_three_crc");
        external_crc_vectors = external_crc_vectors + 1;
        run_valid_frame(8'h05, 8'h06, 16'hABCD, 32'h01020304, 6'd3,
                        1'b0, 1'b0, 1'b0, 1'b0);
        end_case();

        begin_case("stall_and_bubbles");
        for (integer b = 0; b < 8; b = b + 1) begin
            frame_payload[b] = 8'hA0 + b[7:0];
        end
        run_valid_frame(8'h57, 8'h58, 16'h5960, 32'h61626364, 6'd8,
                        1'b1, 1'b1, 1'b1, 1'b0);
        end_case();

        begin_case("payload_faults");
        frame_payload[0] = 8'h01;
        frame_payload[1] = 8'h02;
        frame_payload[2] = 8'h03;
        frame_payload[3] = 8'h04;
        run_payload_fault(6'd4, 0, 1'b1);
        run_payload_fault(6'd2, 1, 1'b0);
        end_case();

        begin_case("illegal_length_faults");
        run_illegal_length_fault(6'd33);
        run_illegal_length_fault(6'd63);
        end_case();

        begin_case("cancel_phases");
        run_cancel_phase(6'd4, 0);
        run_cancel_phase(6'd4, 1);
        run_cancel_phase(6'd4, 12);
        run_cancel_phase(6'd4, 16);
        run_cancel_phase(6'd4, 17);
        end_case();

        begin_case("reset_phases");
        run_reset_phase(6'd4, 0, 1'b1);
        run_reset_phase(6'd4, 1, 1'b0);
        run_reset_phase(6'd4, 12, 1'b0);
        run_reset_phase(6'd4, 16, 1'b0);
        run_reset_phase(6'd4, 17, 1'b0);
        end_case();

        begin_case("small_counter_saturation");
        small_run_zero_frame(8'h01, 8'h02, 16'h0304, 32'h05060708);
        small_run_zero_frame(8'h11, 8'h12, 16'h1314, 32'h15161718);
        small_run_zero_frame(8'h21, 8'h22, 16'h2324, 32'h25262728);
        small_run_zero_frame(8'h31, 8'h32, 16'h3334, 32'h35363738);
        for (integer iteration = 0; iteration < 4; iteration = iteration + 1) begin
            small_fault_cancel(iteration);
        end
        s_rst = 1'b1;
        tick();
        s_rst = 1'b0;
        tick();
        check(s_busy == 1'b0, "small_reset_busy");
        check(s_out_valid == 1'b0, "small_reset_out");
        check(s_stat_admitted == 0, "small_reset_admitted");
        check(s_stat_sent == 0, "small_reset_sent");
        check(s_stat_aborted == 0, "small_reset_aborted");
        check(s_stat_faults == 0, "small_reset_faults");
        check(s_cfg_ready == 1'b1, "small_reset_ready");
        end_case();

        begin_case("fault_event_boundary");
        run_fault_event_ordinary();
        run_fault_event_cancel_boundary();
        run_fault_event_reset_boundary();
        end_case();

        begin_case("final_state");
        check(busy == 1'b0, "final_busy");
        check(receiving == 1'b0, "final_receiving");
        check(faulted == 1'b0, "final_faulted");
        check(fault_event == 1'b0, "final_fault_event");
        check(fault_code == 2'd0, "final_fault_code");
        check(out_valid == 1'b0, "final_out_valid");
        check(out_count == 6'd0, "final_out_count");
        check(cfg_ready == 1'b1, "final_cfg_ready");
        check(stat_admitted == 0, "final_admitted");
        check(stat_sent == 0, "final_sent");
        check(stat_aborted == 0, "final_aborted");
        check(stat_faults == 0, "final_faults");
        check(lengths_covered == 33, "coverage_lengths");
        check(byte_values_covered == 256, "coverage_bytes");
        check(valid_frames == 46, "coverage_valid_frames");
        check(external_crc_vectors == 4, "coverage_external");
        check(fault_cases == 7, "coverage_faults");
        check(fault_event_boundary_vectors == 3, "coverage_fault_event_boundary");
        check(cancel_phases == 5, "coverage_cancels");
        check(reset_phases == 5, "coverage_resets");
        check(no_credit_checks == 1, "coverage_no_credit");
        check(max_field_vectors == 2, "coverage_max_fields");
        check(held_cancel_sequences == 11, "coverage_held_cancel");
        check(reset_priority_checks == 1, "coverage_reset_priority");
        check(stall_cycles > 0, "coverage_stalls");
        check(saturation_checks > 0, "coverage_saturation");
        end_case();

        if (current_case != "") begin
            failures = failures + 1;
            $display("CHECK_FAIL case=%s name=no_open_case_at_finish", current_case);
        end
        $display("TB_STAT valid_frames=%0d", valid_frames);
        $display("TB_STAT lengths_covered=%0d", lengths_covered);
        $display("TB_STAT byte_values_covered=%0d", byte_values_covered);
        $display("TB_STAT external_crc_vectors=%0d", external_crc_vectors);
        $display("TB_STAT fault_cases=%0d", fault_cases);
        $display("TB_STAT fault_event_boundary_vectors=%0d", fault_event_boundary_vectors);
        $display("TB_STAT cancel_phases=%0d", cancel_phases);
        $display("TB_STAT reset_phases=%0d", reset_phases);
        $display("TB_STAT stall_cycles=%0d", stall_cycles);
        $display("TB_STAT saturation_checks=%0d", saturation_checks);
        $display("TB_STAT no_credit_checks=%0d", no_credit_checks);
        $display("TB_STAT max_field_vectors=%0d", max_field_vectors);
        $display("TB_STAT held_cancel_sequences=%0d", held_cancel_sequences);
        $display("TB_STAT reset_priority_checks=%0d", reset_priority_checks);
        $display("TB_SUMMARY cases=%0d pass=%0d fail=%0d checks=%0d",
                 cases, pass_cases, fail_cases, checks);
        if (failures == 0) begin
            $display("TB_END pass");
        end else begin
            $display("TB_END fail");
        end
        $finish;
    end

endmodule

module tb_wire_serializer_bad_stat;
    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic rst = 1'b0;
    logic cancel = 1'b0;
    logic cfg_valid = 1'b0;
    logic cfg_ready;
    logic [7:0] cfg_type = 8'h00;
    logic [7:0] cfg_epoch = 8'h00;
    logic [15:0] cfg_seq = 16'h0000;
    logic [31:0] cfg_tick = 32'h00000000;
    logic [5:0] cfg_len = 6'd0;
    logic p_valid = 1'b0;
    logic p_ready;
    logic [7:0] p_data = 8'h00;
    logic p_last = 1'b0;
    logic out_valid;
    logic out_ready = 1'b0;
    logic [7:0] out_data;
    logic out_last;
    logic [5:0] out_count;
    logic busy;
    logic receiving;
    logic faulted;
    logic fault_event;
    logic [1:0] fault_code;
    logic [1:0] stat_admitted;
    logic [1:0] stat_sent;
    logic [1:0] stat_aborted;
    logic [1:0] stat_faults;

    deepeye_wire_serializer #(.STAT_W(1)) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .cfg_valid(cfg_valid),
        .cfg_ready(cfg_ready),
        .cfg_type(cfg_type),
        .cfg_epoch(cfg_epoch),
        .cfg_seq(cfg_seq),
        .cfg_tick(cfg_tick),
        .cfg_len(cfg_len),
        .p_valid(p_valid),
        .p_ready(p_ready),
        .p_data(p_data),
        .p_last(p_last),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_data(out_data),
        .out_last(out_last),
        .out_count(out_count),
        .busy(busy),
        .receiving(receiving),
        .faulted(faulted),
        .fault_event(fault_event),
        .fault_code(fault_code),
        .stat_admitted(stat_admitted),
        .stat_sent(stat_sent),
        .stat_aborted(stat_aborted),
        .stat_faults(stat_faults)
    );

    initial begin
        #100;
        $display("BAD_STAT_SENTINEL_REACHED");
        $finish;
    end
endmodule
