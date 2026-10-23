`timescale 1ns/1ps
`default_nettype none

module uart_probe #(
    parameter integer CLOCK_HZ = 64,
    parameter integer BAUD = 8
) (
    input  wire logic clk,
    input  wire logic rst,
    input  wire logic de,
    input  wire logic serial,
    output logic byte_valid,
    output logic [7:0] byte_data,
    output logic stop_error
);
    typedef enum logic [1:0] {
        P_IDLE,
        P_SAMPLE,
        P_WAIT_HIGH
    } probe_state_t;

    probe_state_t state_q;
    integer elapsed_q;
    logic [3:0] phase_q;
    logic [7:0] shift_q;

    function automatic integer boundary(input integer bit_index);
        integer numerator;
        begin
            numerator = bit_index * CLOCK_HZ;
            boundary = (numerator + BAUD - 1) / BAUD;
        end
    endfunction

    function automatic integer sample_target(input integer phase);
        integer value;
        begin
            value = ((boundary(phase + 1) + boundary(phase + 2)) / 2) - 1;
            if (value < 0) begin
                sample_target = 0;
            end else begin
                sample_target = value;
            end
        end
    endfunction

    always_ff @(posedge clk) begin
        if (rst) begin
            state_q    <= P_IDLE;
            elapsed_q  <= 0;
            phase_q    <= 4'd0;
            shift_q    <= 8'd0;
            byte_valid <= 1'b0;
            byte_data  <= 8'd0;
            stop_error <= 1'b0;
        end else if (!de) begin
            state_q    <= P_IDLE;
            elapsed_q  <= 0;
            phase_q    <= 4'd0;
            byte_valid <= 1'b0;
        end else begin
            byte_valid <= 1'b0;
            case (state_q)
                P_IDLE: begin
                    if (serial === 1'b0) begin
                        elapsed_q <= 0;
                        phase_q   <= 4'd0;
                        state_q   <= P_SAMPLE;
                    end
                end

                P_SAMPLE: begin
                    if (elapsed_q >= sample_target(phase_q)) begin
                        if (phase_q < 4'd8) begin
                            shift_q[phase_q] <= serial;
                            phase_q          <= phase_q + 1'b1;
                        end else begin
                            byte_data  <= shift_q;
                            stop_error <= (serial !== 1'b1);
                            byte_valid <= 1'b1;
                            state_q    <= P_WAIT_HIGH;
                        end
                    end
                    elapsed_q <= elapsed_q + 1;
                end

                P_WAIT_HIGH: begin
                    if (serial === 1'b1) begin
                        state_q <= P_IDLE;
                    end
                end

                default: state_q <= P_IDLE;
            endcase
        end
    end
endmodule


module tb_wire_uart_tx;
    localparam integer VECTOR_MAX = 64;
    localparam integer EXPECTED_MAX = 4096;
    localparam integer CAPTURE_TIMEOUT = 2500000;

    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic main_rst, main_cancel;
    logic main_cfg_valid, main_cfg_ready;
    logic [7:0] main_cfg_type, main_cfg_epoch;
    logic [15:0] main_cfg_seq;
    logic [31:0] main_cfg_tick;
    logic [5:0] main_cfg_len;
    logic main_p_valid, main_p_ready, main_p_last;
    logic [7:0] main_p_data;
    logic main_tx, main_de, main_busy, main_receiving;
    logic main_faulted, main_fault_event;
    logic [1:0] main_fault_code;
    logic [31:0] main_stat_admitted, main_stat_sent, main_stat_aborted;
    logic main_probe_valid, main_probe_stop_error;
    logic [7:0] main_probe_data;

    logic frac_rst, frac_cancel;
    logic frac_cfg_valid, frac_cfg_ready;
    logic [7:0] frac_cfg_type, frac_cfg_epoch;
    logic [15:0] frac_cfg_seq;
    logic [31:0] frac_cfg_tick;
    logic [5:0] frac_cfg_len;
    logic frac_p_valid, frac_p_ready, frac_p_last;
    logic [7:0] frac_p_data;
    logic frac_tx, frac_de, frac_busy, frac_receiving;
    logic frac_faulted, frac_fault_event;
    logic [1:0] frac_fault_code;
    logic [31:0] frac_stat_admitted, frac_stat_sent, frac_stat_aborted;
    logic frac_probe_valid, frac_probe_stop_error;
    logic [7:0] frac_probe_data;

    logic dflt_rst, dflt_cancel;
    logic dflt_cfg_valid, dflt_cfg_ready;
    logic [7:0] dflt_cfg_type, dflt_cfg_epoch;
    logic [15:0] dflt_cfg_seq;
    logic [31:0] dflt_cfg_tick;
    logic [5:0] dflt_cfg_len;
    logic dflt_p_valid, dflt_p_ready, dflt_p_last;
    logic [7:0] dflt_p_data;
    logic dflt_tx, dflt_de, dflt_busy, dflt_receiving;
    logic dflt_faulted, dflt_fault_event;
    logic [1:0] dflt_fault_code;
    logic [31:0] dflt_stat_admitted, dflt_stat_sent, dflt_stat_aborted;
    logic dflt_probe_valid, dflt_probe_stop_error;
    logic [7:0] dflt_probe_data;

    logic small_rst, small_cancel;
    logic small_cfg_valid, small_cfg_ready;
    logic [7:0] small_cfg_type, small_cfg_epoch;
    logic [15:0] small_cfg_seq;
    logic [31:0] small_cfg_tick;
    logic [5:0] small_cfg_len;
    logic small_p_valid, small_p_ready, small_p_last;
    logic [7:0] small_p_data;
    logic small_tx, small_de, small_busy, small_receiving;
    logic small_faulted, small_fault_event;
    logic [1:0] small_fault_code;
    logic [1:0] small_stat_admitted, small_stat_sent, small_stat_aborted;
    logic small_probe_valid, small_probe_stop_error;
    logic [7:0] small_probe_data;

    integer v_len [0:VECTOR_MAX-1];
    integer v_type [0:VECTOR_MAX-1];
    integer v_epoch [0:VECTOR_MAX-1];
    integer v_seq [0:VECTOR_MAX-1];
    longint unsigned v_tick [0:VECTOR_MAX-1];
    integer v_count [0:VECTOR_MAX-1];
    integer v_offset [0:VECTOR_MAX-1];
    logic [7:0] expected_mem [0:EXPECTED_MAX-1];

    integer vector_count;
    bit lengths_seen [0:32];
    bit payload_seen [0:255];
    integer max_metadata_vectors;
    integer expected_total_bytes;

    integer total_checks;
    integer total_failures;
    integer total_cases;
    integer total_pass_cases;
    integer total_fail_cases;
    integer case_checks;
    integer case_failure_start;
    string current_case;

    integer main_exp_admitted;
    integer main_exp_sent;
    integer main_exp_aborted;
    integer main_payload_bytes_seen;
    integer main_bubble_cycles;
    integer vectors_processed;
    integer bubble_vectors;
    integer packet_bytes_compared;
    integer same_edge_config_payload_cases;
    integer cfg_held_busy_frames;
    integer illegal_length_cases;
    integer illegal_last_cases;
    integer fault_events_checked;
    integer cancel_phase_cases;
    integer reset_phase_cases;
    integer held_cancel_sequences;
    integer preamble_cycles;
    integer postamble_cycles;
    integer fractional_baud_frames;
    integer default_baud_frames;
    integer saturation_success_frames;
    integer saturation_abort_frames;

    deepeye_wire_uart_tx #(
        .CLOCK_HZ(64),
        .BAUD(8),
        .PRE_CYCLES(2),
        .POST_CYCLES(3),
        .STAT_W(32)
    ) dut_main (
        .clk(clk), .rst(main_rst), .cancel(main_cancel),
        .cfg_valid(main_cfg_valid), .cfg_ready(main_cfg_ready),
        .cfg_type(main_cfg_type), .cfg_epoch(main_cfg_epoch),
        .cfg_seq(main_cfg_seq), .cfg_tick(main_cfg_tick), .cfg_len(main_cfg_len),
        .p_valid(main_p_valid), .p_ready(main_p_ready), .p_data(main_p_data),
        .p_last(main_p_last), .tx(main_tx), .de(main_de), .busy(main_busy),
        .receiving(main_receiving), .faulted(main_faulted),
        .fault_event(main_fault_event), .fault_code(main_fault_code),
        .stat_admitted(main_stat_admitted), .stat_sent(main_stat_sent),
        .stat_aborted(main_stat_aborted)
    );

    uart_probe #(.CLOCK_HZ(64), .BAUD(8)) probe_main (
        .clk(clk), .rst(main_rst), .de(main_de), .serial(main_tx),
        .byte_valid(main_probe_valid), .byte_data(main_probe_data),
        .stop_error(main_probe_stop_error)
    );

    deepeye_wire_uart_tx #(
        .CLOCK_HZ(100),
        .BAUD(7),
        .PRE_CYCLES(3),
        .POST_CYCLES(2),
        .STAT_W(32)
    ) dut_fractional (
        .clk(clk), .rst(frac_rst), .cancel(frac_cancel),
        .cfg_valid(frac_cfg_valid), .cfg_ready(frac_cfg_ready),
        .cfg_type(frac_cfg_type), .cfg_epoch(frac_cfg_epoch),
        .cfg_seq(frac_cfg_seq), .cfg_tick(frac_cfg_tick), .cfg_len(frac_cfg_len),
        .p_valid(frac_p_valid), .p_ready(frac_p_ready), .p_data(frac_p_data),
        .p_last(frac_p_last), .tx(frac_tx), .de(frac_de), .busy(frac_busy),
        .receiving(frac_receiving), .faulted(frac_faulted),
        .fault_event(frac_fault_event), .fault_code(frac_fault_code),
        .stat_admitted(frac_stat_admitted), .stat_sent(frac_stat_sent),
        .stat_aborted(frac_stat_aborted)
    );

    uart_probe #(.CLOCK_HZ(100), .BAUD(7)) probe_fractional (
        .clk(clk), .rst(frac_rst), .de(frac_de), .serial(frac_tx),
        .byte_valid(frac_probe_valid), .byte_data(frac_probe_data),
        .stop_error(frac_probe_stop_error)
    );

    deepeye_wire_uart_tx dut_default (
        .clk(clk), .rst(dflt_rst), .cancel(dflt_cancel),
        .cfg_valid(dflt_cfg_valid), .cfg_ready(dflt_cfg_ready),
        .cfg_type(dflt_cfg_type), .cfg_epoch(dflt_cfg_epoch),
        .cfg_seq(dflt_cfg_seq), .cfg_tick(dflt_cfg_tick), .cfg_len(dflt_cfg_len),
        .p_valid(dflt_p_valid), .p_ready(dflt_p_ready), .p_data(dflt_p_data),
        .p_last(dflt_p_last), .tx(dflt_tx), .de(dflt_de), .busy(dflt_busy),
        .receiving(dflt_receiving), .faulted(dflt_faulted),
        .fault_event(dflt_fault_event), .fault_code(dflt_fault_code),
        .stat_admitted(dflt_stat_admitted), .stat_sent(dflt_stat_sent),
        .stat_aborted(dflt_stat_aborted)
    );

    uart_probe #(.CLOCK_HZ(100000000), .BAUD(9600)) probe_default (
        .clk(clk), .rst(dflt_rst), .de(dflt_de), .serial(dflt_tx),
        .byte_valid(dflt_probe_valid), .byte_data(dflt_probe_data),
        .stop_error(dflt_probe_stop_error)
    );

    deepeye_wire_uart_tx #(
        .CLOCK_HZ(32),
        .BAUD(8),
        .PRE_CYCLES(0),
        .POST_CYCLES(0),
        .STAT_W(2)
    ) dut_small (
        .clk(clk), .rst(small_rst), .cancel(small_cancel),
        .cfg_valid(small_cfg_valid), .cfg_ready(small_cfg_ready),
        .cfg_type(small_cfg_type), .cfg_epoch(small_cfg_epoch),
        .cfg_seq(small_cfg_seq), .cfg_tick(small_cfg_tick), .cfg_len(small_cfg_len),
        .p_valid(small_p_valid), .p_ready(small_p_ready), .p_data(small_p_data),
        .p_last(small_p_last), .tx(small_tx), .de(small_de), .busy(small_busy),
        .receiving(small_receiving), .faulted(small_faulted),
        .fault_event(small_fault_event), .fault_code(small_fault_code),
        .stat_admitted(small_stat_admitted), .stat_sent(small_stat_sent),
        .stat_aborted(small_stat_aborted)
    );

    uart_probe #(.CLOCK_HZ(32), .BAUD(8)) probe_small (
        .clk(clk), .rst(small_rst), .de(small_de), .serial(small_tx),
        .byte_valid(small_probe_valid), .byte_data(small_probe_data),
        .stop_error(small_probe_stop_error)
    );

    task automatic check_condition(input logic condition, input string label);
        begin
            total_checks = total_checks + 1;
            case_checks = case_checks + 1;
            if (condition !== 1'b1) begin
                total_failures = total_failures + 1;
                $display("# CHECK_FAIL case=%s id=%s", current_case, label);
            end
        end
    endtask

    task automatic begin_case(input string name);
        begin
            current_case = name;
            case_checks = 0;
            case_failure_start = total_failures;
            total_cases = total_cases + 1;
            $display("# CASE_BEGIN name=%s", name);
        end
    endtask

    task automatic end_case();
        string status;
        begin
            if (total_failures == case_failure_start) begin
                status = "pass";
                total_pass_cases = total_pass_cases + 1;
            end else begin
                status = "fail";
                total_fail_cases = total_fail_cases + 1;
            end
            $display("# CASE_END name=%s status=%s checks=%0d", current_case, status, case_checks);
        end
    endtask

    task automatic load_vectors();
        string meta_path;
        string hex_path;
        integer fd;
        integer scan_count;
        integer file_count;
        integer mi, ml, mt, me, ms, mc, mo;
        longint unsigned mti;
        integer i, j, total;
        begin
            if (!$value$plusargs("VECTOR_META=%s", meta_path)) begin
                $fatal(1, "tb_wire_uart_tx: missing VECTOR_META");
            end
            if (!$value$plusargs("VECTOR_HEX=%s", hex_path)) begin
                $fatal(1, "tb_wire_uart_tx: missing VECTOR_HEX");
            end
            for (i = 0; i < VECTOR_MAX; i = i + 1) begin
                v_len[i] = 0; v_type[i] = 0; v_epoch[i] = 0; v_seq[i] = 0;
                v_tick[i] = 0; v_count[i] = 0; v_offset[i] = 0;
            end
            for (i = 0; i < EXPECTED_MAX; i = i + 1) begin
                expected_mem[i] = 8'h00;
            end
            for (i = 0; i < 33; i = i + 1) begin
                lengths_seen[i] = 1'b0;
            end
            for (i = 0; i < 256; i = i + 1) begin
                payload_seen[i] = 1'b0;
            end
            fd = $fopen(meta_path, "r");
            if (fd == 0) begin
                $fatal(1, "tb_wire_uart_tx: cannot open vector metadata");
            end
            file_count = 0;
            total = 0;
            while (!$feof(fd)) begin
                scan_count = $fscanf(fd, "%d %d %d %d %d %d %d %d\n",
                                      mi, ml, mt, me, ms, mti, mc, mo);
                if (scan_count == 8) begin
                    if ((mi != file_count) || (mi < 0) || (mi >= VECTOR_MAX)) begin
                        $fatal(1, "tb_wire_uart_tx: vector index/order invalid");
                    end
                    if ((ml < 0) || (ml > 32) || (mc != (14 + ml)) || (mo != total) ||
                        (mo < 0) || ((mo + mc) > EXPECTED_MAX)) begin
                        $fatal(1, "tb_wire_uart_tx: vector bounds invalid");
                    end
                    v_len[mi] = ml;
                    v_type[mi] = mt;
                    v_epoch[mi] = me;
                    v_seq[mi] = ms;
                    v_tick[mi] = mti;
                    v_count[mi] = mc;
                    v_offset[mi] = mo;
                    lengths_seen[ml] = 1'b1;
                    total = total + mc;
                    file_count = file_count + 1;
                end
            end
            $fclose(fd);
            if (file_count != 40) begin
                $fatal(1, "tb_wire_uart_tx: expected 40 vectors");
            end
            vector_count = file_count;
            expected_total_bytes = total;
            $readmemh(hex_path, expected_mem);
            for (i = 0; i < vector_count; i = i + 1) begin
                for (j = 0; j < v_len[i]; j = j + 1) begin
                    payload_seen[expected_mem[v_offset[i] + 12 + j]] = 1'b1;
                end
            end
            max_metadata_vectors = 0;
            for (i = 0; i < vector_count; i = i + 1) begin
                if ((v_type[i] == 255) && (v_epoch[i] == 255) &&
                    (v_seq[i] == 65535) && (v_tick[i] == 64'hFFFFFFFF)) begin
                    max_metadata_vectors = max_metadata_vectors + 1;
                end
            end
            for (i = 0; i < 33; i = i + 1) begin
                if (!lengths_seen[i]) $fatal(1, "tb_wire_uart_tx: missing length");
            end
            for (i = 0; i < 256; i = i + 1) begin
                if (!payload_seen[i]) $fatal(1, "tb_wire_uart_tx: missing payload byte");
            end
        end
    endtask

    task automatic main_quiet_reset();
        begin
            @(negedge clk); #1;
            main_rst = 1'b1;
            @(posedge clk); #1;
            main_exp_admitted = 0;
            main_exp_sent = 0;
            main_exp_aborted = 0;
            check_condition(main_stat_admitted == 0, "quiet_reset_admitted");
            check_condition(main_stat_sent == 0, "quiet_reset_sent");
            check_condition(main_stat_aborted == 0, "quiet_reset_aborted");
            @(negedge clk); #1;
            main_rst = 1'b0;
            @(posedge clk); #1;
            check_condition(main_cfg_ready === 1'b1, "quiet_reset_cfg_ready");
        end
    endtask

    task automatic main_config_from_vector(input integer index, input bit same_edge_payload);
        begin
            @(negedge clk); #1;
            check_condition(main_cfg_ready === 1'b1, "cfg_ready_before");
            check_condition(main_busy === 1'b0, "busy_before_cfg");
            main_cfg_valid = 1'b1;
            main_cfg_type = v_type[index][7:0];
            main_cfg_epoch = v_epoch[index][7:0];
            main_cfg_seq = v_seq[index][15:0];
            main_cfg_tick = v_tick[index][31:0];
            main_cfg_len = v_len[index][5:0];
            main_p_valid = 1'b0;
            main_p_last = 1'b0;
            if (same_edge_payload && (v_len[index] > 0)) begin
                main_p_valid = 1'b1;
                main_p_data = expected_mem[v_offset[index] + 12];
                main_p_last = (v_len[index] == 1);
                check_condition(main_p_ready === 1'b0, "same_edge_p_ready_low");
            end
            @(posedge clk); #1;
            main_cfg_valid = 1'b0;
            main_exp_admitted = main_exp_admitted + 1;
            check_condition(main_busy === 1'b1, "busy_after_cfg");
            check_condition(main_cfg_ready === 1'b0, "cfg_ready_busy");
            check_condition(main_stat_admitted == main_exp_admitted, "admitted_after_cfg");
            if (same_edge_payload) begin
                check_condition(main_p_ready === 1'b1, "p_ready_after_cfg");
            end
            if (v_len[index] == 0) begin
                check_condition(main_receiving === 1'b0, "receiving_zero_len");
            end else begin
                check_condition(main_receiving === 1'b1, "receiving_nonzero_len");
            end
        end
    endtask

    task automatic main_config_raw(
        input logic [5:0] len_value,
        input logic [7:0] type_value,
        input logic [7:0] epoch_value,
        input logic [15:0] seq_value,
        input logic [31:0] tick_value
    );
        begin
            @(negedge clk); #1;
            check_condition(main_cfg_ready === 1'b1, "raw_cfg_ready_before");
            main_cfg_valid = 1'b1;
            main_cfg_type = type_value;
            main_cfg_epoch = epoch_value;
            main_cfg_seq = seq_value;
            main_cfg_tick = tick_value;
            main_cfg_len = len_value;
            main_p_valid = 1'b0;
            main_p_last = 1'b0;
            @(posedge clk); #1;
            main_cfg_valid = 1'b0;
            main_exp_admitted = main_exp_admitted + 1;
            check_condition(main_busy === 1'b1, "raw_busy_after_cfg");
            check_condition(main_cfg_ready === 1'b0, "raw_cfg_ready_busy");
            check_condition(main_stat_admitted == main_exp_admitted, "raw_admitted");
        end
    endtask

    task automatic main_send_byte(input logic [7:0] data, input logic last);
        begin
            @(negedge clk); #1;
            main_p_valid = 1'b1;
            main_p_data = data;
            main_p_last = last;
            check_condition(main_p_ready === 1'b1, "payload_ready");
            @(posedge clk); #1;
            main_p_valid = 1'b0;
            main_p_last = 1'b0;
            main_payload_bytes_seen = main_payload_bytes_seen + 1;
        end
    endtask

    task automatic main_send_payload(input integer index, input integer start_index,
                                     input bit add_bubbles);
        integer i;
        begin
            for (i = start_index; i < v_len[index]; i = i + 1) begin
                main_send_byte(expected_mem[v_offset[index] + 12 + i],
                               (i == (v_len[index] - 1)));
                if (add_bubbles && ((i + 1) < v_len[index]) && ((i % 3) == 2)) begin
                    repeat (2) @(posedge clk);
                    #1;
                    main_bubble_cycles = main_bubble_cycles + 2;
                end
            end
        end
    endtask

    task automatic main_capture_count(input integer index, input integer count);
        integer i;
        integer timeout;
        begin
            i = 0;
            while (i < count) begin
                timeout = 0;
                @(posedge clk); #1;
                while ((main_probe_valid !== 1'b1) && (timeout < CAPTURE_TIMEOUT)) begin
                    @(posedge clk); #1;
                    timeout = timeout + 1;
                end
                check_condition(timeout < CAPTURE_TIMEOUT,
                                $sformatf("vec%0d_byte%0d_timeout", index, i));
                if (timeout >= CAPTURE_TIMEOUT) begin
                    i = count;
                end else begin
                    check_condition(main_probe_data === expected_mem[v_offset[index] + i],
                                    $sformatf("vec%0d_byte%0d_data", index, i));
                    check_condition(main_probe_stop_error === 1'b0,
                                    $sformatf("vec%0d_byte%0d_stop", index, i));
                    packet_bytes_compared = packet_bytes_compared + 1;
                    i = i + 1;
                end
            end
        end
    endtask

    task automatic main_wait_retire();
        integer timeout;
        begin
            timeout = 0;
            @(posedge clk); #1;
            while ((main_busy === 1'b1) && (timeout < 100000)) begin
                @(posedge clk); #1;
                timeout = timeout + 1;
            end
            check_condition(timeout < 100000, "retire_timeout");
            check_condition(main_busy === 1'b0, "retire_busy_low");
            main_exp_sent = main_exp_sent + 1;
            check_condition(main_stat_sent == main_exp_sent, "retire_sent_count");
            check_condition(main_tx === 1'b1, "retire_tx_idle");
            check_condition(main_de === 1'b0, "retire_de_low");
            check_condition(main_cfg_ready === 1'b1, "retire_cfg_ready");
        end
    endtask

    task automatic main_wait_de_rise();
        integer timeout;
        begin
            timeout = 0;
            @(posedge clk); #1;
            while ((main_de !== 1'b1) && (timeout < 100000)) begin
                @(posedge clk); #1;
                timeout = timeout + 1;
            end
            check_condition(timeout < 100000, "de_rise_timeout");
            check_condition(main_de === 1'b1, "de_rise_seen");
            check_condition(main_busy === 1'b1, "de_rise_busy");
        end
    endtask

    task automatic main_wait_tx_fall();
        integer timeout;
        begin
            timeout = 0;
            while ((main_tx !== 1'b0) && (timeout < 100000)) begin
                @(posedge clk); #1;
                timeout = timeout + 1;
            end
            check_condition(timeout < 100000, "tx_fall_timeout");
            check_condition(main_tx === 1'b0, "tx_fall_seen");
        end
    endtask

    task automatic main_abort_cancel(input string label, input bit hold_cancel);
        begin
            @(negedge clk); #1;
            check_condition(main_busy === 1'b1, $sformatf("%s_busy_before", label));
            main_cancel = 1'b1;
            @(posedge clk); #1;
            main_exp_aborted = main_exp_aborted + 1;
            if (hold_cancel) held_cancel_sequences = held_cancel_sequences + 1;
            check_condition(main_busy === 1'b0, $sformatf("%s_busy_after", label));
            check_condition(main_de === 1'b0, $sformatf("%s_de_after", label));
            check_condition(main_tx === 1'b1, $sformatf("%s_tx_after", label));
            check_condition(main_stat_aborted == main_exp_aborted,
                            $sformatf("%s_aborted", label));
            check_condition(main_stat_admitted == main_exp_admitted,
                            $sformatf("%s_admitted_hold", label));
            check_condition(main_stat_sent == main_exp_sent,
                            $sformatf("%s_sent_hold", label));
            check_condition(main_cfg_ready === 1'b0,
                            $sformatf("%s_cfg_blocked", label));
            if (hold_cancel) begin
                repeat (2) @(posedge clk); #1;
                check_condition(main_stat_aborted == main_exp_aborted,
                                $sformatf("%s_aborted_once", label));
            end
            @(negedge clk); #1;
            main_cancel = 1'b0;
            @(posedge clk); #1;
            check_condition(main_cfg_ready === 1'b1,
                            $sformatf("%s_cfg_released", label));
        end
    endtask

    task automatic main_abort_reset(input string label);
        begin
            @(negedge clk); #1;
            main_rst = 1'b1;
            @(posedge clk); #1;
            main_exp_admitted = 0;
            main_exp_sent = 0;
            main_exp_aborted = 0;
            check_condition(main_busy === 1'b0, $sformatf("%s_busy_reset", label));
            check_condition(main_de === 1'b0, $sformatf("%s_de_reset", label));
            check_condition(main_tx === 1'b1, $sformatf("%s_tx_reset", label));
            check_condition(main_faulted === 1'b0, $sformatf("%s_fault_reset", label));
            check_condition(main_stat_admitted == 0, $sformatf("%s_adm_reset", label));
            check_condition(main_stat_sent == 0, $sformatf("%s_sent_reset", label));
            check_condition(main_stat_aborted == 0, $sformatf("%s_abort_reset", label));
            check_condition(main_cfg_ready === 1'b0, $sformatf("%s_cfg_reset", label));
            repeat (1) @(posedge clk); #1;
            check_condition(main_stat_admitted == 0, $sformatf("%s_adm_held", label));
            @(negedge clk); #1;
            main_rst = 1'b0;
            @(posedge clk); #1;
            check_condition(main_cfg_ready === 1'b1, $sformatf("%s_ready_release", label));
        end
    endtask

    task automatic main_check_idle(input string tag);
        begin
            check_condition(main_cfg_ready === 1'b1, $sformatf("%s_cfg_ready", tag));
            check_condition(main_busy === 1'b0, $sformatf("%s_busy", tag));
            check_condition(main_receiving === 1'b0, $sformatf("%s_receiving", tag));
            check_condition(main_tx === 1'b1, $sformatf("%s_tx", tag));
            check_condition(main_de === 1'b0, $sformatf("%s_de", tag));
            check_condition(main_faulted === 1'b0, $sformatf("%s_faulted", tag));
            check_condition(main_fault_event === 1'b0, $sformatf("%s_fault_event", tag));
            check_condition(main_fault_code == 0, $sformatf("%s_fault_code", tag));
            check_condition(main_stat_admitted == 0, $sformatf("%s_admitted", tag));
            check_condition(main_stat_sent == 0, $sformatf("%s_sent", tag));
            check_condition(main_stat_aborted == 0, $sformatf("%s_aborted", tag));
        end
    endtask

    initial begin
        total_checks = 0;
        total_failures = 0;
        total_cases = 0;
        total_pass_cases = 0;
        total_fail_cases = 0;
        case_checks = 0;
        case_failure_start = 0;
        current_case = "none";
        main_exp_admitted = 0;
        main_exp_sent = 0;
        main_exp_aborted = 0;
        main_payload_bytes_seen = 0;
        main_bubble_cycles = 0;
        vectors_processed = 0;
        bubble_vectors = 0;
        packet_bytes_compared = 0;
        same_edge_config_payload_cases = 0;
        cfg_held_busy_frames = 0;
        illegal_length_cases = 0;
        illegal_last_cases = 0;
        fault_events_checked = 0;
        cancel_phase_cases = 0;
        reset_phase_cases = 0;
        held_cancel_sequences = 0;
        preamble_cycles = 0;
        postamble_cycles = 0;
        fractional_baud_frames = 0;
        default_baud_frames = 0;
        saturation_success_frames = 0;
        saturation_abort_frames = 0;

        main_rst = 1'b1; main_cancel = 1'b0; main_cfg_valid = 1'b0;
        main_cfg_type = 0; main_cfg_epoch = 0; main_cfg_seq = 0; main_cfg_tick = 0;
        main_cfg_len = 0; main_p_valid = 1'b0; main_p_data = 0; main_p_last = 1'b0;
        frac_rst = 1'b1; frac_cancel = 1'b0; frac_cfg_valid = 1'b0;
        frac_cfg_type = 0; frac_cfg_epoch = 0; frac_cfg_seq = 0; frac_cfg_tick = 0;
        frac_cfg_len = 0; frac_p_valid = 1'b0; frac_p_data = 0; frac_p_last = 1'b0;
        dflt_rst = 1'b1; dflt_cancel = 1'b0; dflt_cfg_valid = 1'b0;
        dflt_cfg_type = 0; dflt_cfg_epoch = 0; dflt_cfg_seq = 0; dflt_cfg_tick = 0;
        dflt_cfg_len = 0; dflt_p_valid = 1'b0; dflt_p_data = 0; dflt_p_last = 1'b0;
        small_rst = 1'b1; small_cancel = 1'b0; small_cfg_valid = 1'b0;
        small_cfg_type = 0; small_cfg_epoch = 0; small_cfg_seq = 0; small_cfg_tick = 0;
        small_cfg_len = 0; small_p_valid = 1'b0; small_p_data = 0; small_p_last = 1'b0;

        load_vectors();
        repeat (4) @(posedge clk); #1;
        begin_case("initial_reset");
        check_condition(main_busy === 1'b0, "reset_main_busy");
        check_condition(main_tx === 1'b1, "reset_main_tx");
        check_condition(main_de === 1'b0, "reset_main_de");
        check_condition(main_stat_admitted == 0, "reset_main_admitted");
        @(negedge clk); #1;
        main_rst = 1'b0; frac_rst = 1'b0; dflt_rst = 1'b0; small_rst = 1'b0;
        repeat (2) @(posedge clk); #1;
        main_check_idle("initial_main");
        check_condition(frac_cfg_ready === 1'b1, "initial_frac_cfg_ready");
        check_condition(frac_busy === 1'b0, "initial_frac_busy");
        check_condition(frac_tx === 1'b1, "initial_frac_tx");
        check_condition(frac_de === 1'b0, "initial_frac_de");
        check_condition(dflt_cfg_ready === 1'b1, "initial_dflt_cfg_ready");
        check_condition(dflt_busy === 1'b0, "initial_dflt_busy");
        check_condition(dflt_tx === 1'b1, "initial_dflt_tx");
        check_condition(dflt_de === 1'b0, "initial_dflt_de");
        check_condition(small_cfg_ready === 1'b1, "initial_small_cfg_ready");
        check_condition(small_busy === 1'b0, "initial_small_busy");
        check_condition(small_tx === 1'b1, "initial_small_tx");
        check_condition(small_de === 1'b0, "initial_small_de");
        main_check_idle("released_main");
        check_condition(frac_cfg_ready === 1'b1, "released_frac_cfg_ready");
        check_condition(dflt_cfg_ready === 1'b1, "released_dflt_cfg_ready");
        check_condition(small_cfg_ready === 1'b1, "released_small_cfg_ready");
        end_case();

        begin_case("packet_vectors");
        main_quiet_reset();
        for (integer vi = 0; vi < vector_count; vi = vi + 1) begin
            if (v_len[vi] > 1) bubble_vectors = bubble_vectors + 1;
            main_config_from_vector(vi, 1'b0);
            main_send_payload(vi, 0, 1'b1);
            main_capture_count(vi, v_count[vi]);
            main_wait_retire();
            vectors_processed = vectors_processed + 1;
        end
        check_condition(vectors_processed == 40, "vector_count_processed");
        check_condition(main_stat_admitted == 40, "vector_admitted_total");
        check_condition(main_stat_sent == 40, "vector_sent_total");
        end_case();

        begin_case("prepost_timing");
        main_quiet_reset();
        main_config_from_vector(0, 1'b0);
        main_wait_de_rise();
        preamble_cycles = 0;
        while (main_tx === 1'b1) begin
            @(posedge clk); #1;
            preamble_cycles = preamble_cycles + 1;
        end
        check_condition(preamble_cycles == 3, "pre_cycles_exact");
        main_capture_count(0, v_count[0]);
        postamble_cycles = 0;
        while (main_de === 1'b1) begin
            @(posedge clk); #1;
            postamble_cycles = postamble_cycles + 1;
        end
        // The probe reports the STOP sample four clocks before the UART core
        // releases busy.  The remaining high span is those four clocks plus
        // the three configured POST_CYCLES.
        check_condition(postamble_cycles == 7, "post_cycles_exact");
        main_wait_retire();
        end_case();

        begin_case("config_payload_cadence");
        main_quiet_reset();
        main_config_from_vector(1, 1'b1);
        same_edge_config_payload_cases = same_edge_config_payload_cases + 1;
        @(posedge clk); #1;
        check_condition(main_p_ready === 1'b0, "cadence_payload_accepted_no_credit");
        main_p_valid = 1'b0;
        main_p_last = 1'b0;
        main_payload_bytes_seen = main_payload_bytes_seen + 1;
        main_capture_count(1, v_count[1]);
        main_wait_retire();
        end_case();

        begin_case("cfg_held_busy");
        main_quiet_reset();
        main_config_from_vector(2, 1'b0);
        @(negedge clk); #1;
        main_cfg_valid = 1'b1;
        main_cfg_type = v_type[0][7:0];
        main_cfg_epoch = v_epoch[0][7:0];
        main_cfg_seq = v_seq[0][15:0];
        main_cfg_tick = v_tick[0][31:0];
        main_cfg_len = v_len[0][5:0];
        check_condition(main_cfg_ready === 1'b0, "held_cfg_blocked");
        main_send_payload(2, 0, 1'b1);
        main_capture_count(2, v_count[2]);
        check_condition(main_cfg_ready === 1'b0, "held_cfg_still_blocked");
        main_wait_retire();
        check_condition(main_stat_admitted == 1, "held_cfg_no_retire_edge_admit");
        check_condition(main_cfg_ready === 1'b1, "held_cfg_ready_following");
        main_cfg_valid = 1'b0;
        @(posedge clk); #1;
        check_condition(main_stat_admitted == 1, "held_cfg_deassert_no_admit");
        cfg_held_busy_frames = cfg_held_busy_frames + 1;
        end_case();

        begin_case("illegal_inputs");
        main_quiet_reset();
        for (integer li = 0; li < 2; li = li + 1) begin
            if (li == 0) main_config_raw(6'd33, 8'hA1, 8'hB2, 16'hC3D4, 32'hE5F60718);
            else        main_config_raw(6'd63, 8'hA5, 8'hB6, 16'hC7D8, 32'hE9FA0B1C);
            illegal_length_cases = illegal_length_cases + 1;
            fault_events_checked = fault_events_checked + 1;
            check_condition(main_faulted === 1'b1, "illegal_len_faulted");
            check_condition(main_fault_event === 1'b1, "illegal_len_event");
            check_condition(main_fault_code == 1, "illegal_len_code");
            check_condition(main_cfg_ready === 1'b0, "illegal_len_cfg_blocked");
            check_condition(main_p_ready === 1'b0, "illegal_len_p_blocked");
            @(posedge clk); #1;
            check_condition(main_faulted === 1'b1, "illegal_len_sticky");
            check_condition(main_fault_event === 1'b0, "illegal_len_event_pulse");
            repeat (40) @(posedge clk); #1;
            check_condition(main_tx === 1'b1, "illegal_len_no_tx");
            check_condition(main_de === 1'b0, "illegal_len_no_de");
            check_condition(main_probe_valid === 1'b0, "illegal_len_no_byte");
            main_abort_cancel("illegal_len_cancel", 1'b1);
            main_abort_reset("illegal_len_reset");
        end
        main_config_raw(6'd2, 8'h31, 8'h42, 16'h5364, 32'h65768798);
        @(negedge clk); #1;
        main_p_valid = 1'b1;
        main_p_data = 8'h5A;
        main_p_last = 1'b1;
        check_condition(main_p_ready === 1'b1, "illegal_last_p_ready");
        @(posedge clk); #1;
        main_p_valid = 1'b0;
        main_p_last = 1'b0;
        illegal_last_cases = illegal_last_cases + 1;
        fault_events_checked = fault_events_checked + 1;
        check_condition(main_faulted === 1'b1, "illegal_last_faulted");
        check_condition(main_fault_event === 1'b1, "illegal_last_event");
        check_condition(main_fault_code == 2, "illegal_last_code");
        check_condition(main_p_ready === 1'b0, "illegal_last_p_blocked");
        repeat (40) @(posedge clk); #1;
        check_condition(main_fault_event === 1'b0, "illegal_last_event_pulse");
        check_condition(main_tx === 1'b1, "illegal_last_no_tx");
        check_condition(main_de === 1'b0, "illegal_last_no_de");
        check_condition(main_probe_valid === 1'b0, "illegal_last_no_byte");
        main_abort_cancel("illegal_last_cancel", 1'b0);
        main_abort_reset("illegal_last_reset");
        end_case();

        begin_case("abort_collect");
        main_quiet_reset();
        main_config_from_vector(4, 1'b0);
        main_send_byte(expected_mem[v_offset[4] + 12], 1'b0);
        main_send_byte(expected_mem[v_offset[4] + 13], 1'b0);
        check_condition(main_receiving === 1'b1, "collect_cancel_receiving");
        check_condition(main_de === 1'b0, "collect_cancel_de");
        main_abort_cancel("collect_cancel", 1'b0);
        cancel_phase_cases = cancel_phase_cases + 1;
        main_config_from_vector(4, 1'b0);
        main_send_byte(expected_mem[v_offset[4] + 12], 1'b0);
        main_send_byte(expected_mem[v_offset[4] + 13], 1'b0);
        check_condition(main_receiving === 1'b1, "collect_reset_receiving");
        main_abort_reset("collect_reset");
        reset_phase_cases = reset_phase_cases + 1;
        end_case();

        begin_case("abort_transfer");
        main_quiet_reset();
        main_config_from_vector(0, 1'b0);
        repeat (4) @(posedge clk); #1;
        check_condition(main_busy === 1'b1, "transfer_cancel_busy");
        check_condition(main_de === 1'b0, "transfer_cancel_de");
        check_condition(main_tx === 1'b1, "transfer_cancel_tx");
        main_abort_cancel("transfer_cancel", 1'b0);
        cancel_phase_cases = cancel_phase_cases + 1;
        main_config_from_vector(0, 1'b0);
        repeat (4) @(posedge clk); #1;
        check_condition(main_busy === 1'b1, "transfer_reset_busy");
        check_condition(main_de === 1'b0, "transfer_reset_de");
        main_abort_reset("transfer_reset");
        reset_phase_cases = reset_phase_cases + 1;
        end_case();

        begin_case("abort_pre");
        main_quiet_reset();
        main_config_from_vector(0, 1'b0);
        main_wait_de_rise();
        check_condition(main_tx === 1'b1, "pre_cancel_tx_high");
        main_abort_cancel("pre_cancel", 1'b0);
        cancel_phase_cases = cancel_phase_cases + 1;
        main_config_from_vector(0, 1'b0);
        main_wait_de_rise();
        check_condition(main_tx === 1'b1, "pre_reset_tx_high");
        main_abort_reset("pre_reset");
        reset_phase_cases = reset_phase_cases + 1;
        end_case();

        begin_case("abort_start");
        main_quiet_reset();
        main_config_from_vector(0, 1'b0);
        main_wait_de_rise();
        main_wait_tx_fall();
        main_abort_cancel("start_cancel", 1'b0);
        cancel_phase_cases = cancel_phase_cases + 1;
        main_config_from_vector(0, 1'b0);
        main_wait_de_rise();
        main_wait_tx_fall();
        main_abort_reset("start_reset");
        reset_phase_cases = reset_phase_cases + 1;
        end_case();

        begin_case("abort_data");
        main_quiet_reset();
        main_config_from_vector(0, 1'b0);
        main_wait_de_rise();
        main_wait_tx_fall();
        repeat (9) @(posedge clk); #1;
        main_abort_cancel("data_cancel", 1'b0);
        cancel_phase_cases = cancel_phase_cases + 1;
        main_config_from_vector(0, 1'b0);
        main_wait_de_rise();
        main_wait_tx_fall();
        repeat (9) @(posedge clk); #1;
        main_abort_reset("data_reset");
        reset_phase_cases = reset_phase_cases + 1;
        end_case();

        begin_case("abort_stop");
        main_quiet_reset();
        main_config_from_vector(0, 1'b0);
        main_wait_de_rise();
        main_capture_count(0, 13);
        main_wait_tx_fall();
        repeat (74) @(posedge clk); #1;
        check_condition(main_de === 1'b1, "stop_cancel_de_hold");
        main_abort_cancel("stop_cancel", 1'b0);
        cancel_phase_cases = cancel_phase_cases + 1;
        main_config_from_vector(0, 1'b0);
        main_wait_de_rise();
        main_capture_count(0, 13);
        main_wait_tx_fall();
        repeat (74) @(posedge clk); #1;
        check_condition(main_de === 1'b1, "stop_reset_de_hold");
        main_abort_reset("stop_reset");
        reset_phase_cases = reset_phase_cases + 1;
        end_case();

        begin_case("abort_post");
        main_quiet_reset();
        main_config_from_vector(0, 1'b0);
        main_wait_de_rise();
        main_capture_count(0, 14);
        check_condition(main_de === 1'b1, "post_cancel_de_hold");
        check_condition(main_busy === 1'b1, "post_cancel_busy");
        main_abort_cancel("post_cancel", 1'b0);
        cancel_phase_cases = cancel_phase_cases + 1;
        main_config_from_vector(0, 1'b0);
        main_wait_de_rise();
        main_capture_count(0, 14);
        check_condition(main_de === 1'b1, "post_reset_de_hold");
        main_abort_reset("post_reset");
        reset_phase_cases = reset_phase_cases + 1;
        end_case();

        begin_case("fractional_baud");
        @(negedge clk); #1;
        check_condition(frac_cfg_ready === 1'b1, "frac_cfg_ready");
        frac_cfg_valid = 1'b1;
        frac_cfg_type = v_type[1][7:0];
        frac_cfg_epoch = v_epoch[1][7:0];
        frac_cfg_seq = v_seq[1][15:0];
        frac_cfg_tick = v_tick[1][31:0];
        frac_cfg_len = v_len[1][5:0];
        @(posedge clk); #1;
        frac_cfg_valid = 1'b0;
        check_condition(frac_busy === 1'b1, "frac_busy");
        check_condition(frac_stat_admitted == 1, "frac_admitted");
        for (integer fi = 0; fi < v_len[1]; fi = fi + 1) begin
            @(negedge clk); #1;
            frac_p_valid = 1'b1;
            frac_p_data = expected_mem[v_offset[1] + 12 + fi];
            frac_p_last = (fi == (v_len[1] - 1));
            check_condition(frac_p_ready === 1'b1, "frac_p_ready");
            @(posedge clk); #1;
            frac_p_valid = 1'b0;
            frac_p_last = 1'b0;
        end
        for (integer fb = 0; fb < v_count[1]; fb = fb + 1) begin
            integer ftimeout;
            ftimeout = 0;
            @(posedge clk); #1;
            while ((frac_probe_valid !== 1'b1) && (ftimeout < 10000)) begin
                @(posedge clk); #1;
                ftimeout = ftimeout + 1;
            end
            check_condition(ftimeout < 10000, "frac_byte_timeout");
            check_condition(frac_probe_data === expected_mem[v_offset[1] + fb], "frac_byte");
            check_condition(frac_probe_stop_error === 1'b0, "frac_stop");
        end
        begin : frac_retire_wait
            integer ftimeout;
            ftimeout = 0;
            @(posedge clk); #1;
            while ((frac_busy === 1'b1) && (ftimeout < 10000)) begin
                @(posedge clk); #1;
                ftimeout = ftimeout + 1;
            end
            check_condition(ftimeout < 10000, "frac_retire_timeout");
        end
        check_condition(frac_busy === 1'b0, "frac_retired");
        check_condition(frac_stat_sent == 1, "frac_sent");
        check_condition(frac_tx === 1'b1, "frac_tx_idle");
        check_condition(frac_de === 1'b0, "frac_de_idle");
        fractional_baud_frames = fractional_baud_frames + 1;
        end_case();

        begin_case("default_100mhz_9600");
        @(negedge clk); #1;
        check_condition(dflt_cfg_ready === 1'b1, "default_cfg_ready");
        dflt_cfg_valid = 1'b1;
        dflt_cfg_type = v_type[0][7:0];
        dflt_cfg_epoch = v_epoch[0][7:0];
        dflt_cfg_seq = v_seq[0][15:0];
        dflt_cfg_tick = v_tick[0][31:0];
        dflt_cfg_len = v_len[0][5:0];
        @(posedge clk); #1;
        dflt_cfg_valid = 1'b0;
        check_condition(dflt_busy === 1'b1, "default_busy");
        check_condition(dflt_stat_admitted == 1, "default_admitted");
        for (integer di = 0; di < v_count[0]; di = di + 1) begin
            integer dtimeout;
            dtimeout = 0;
            @(posedge clk); #1;
            while ((dflt_probe_valid !== 1'b1) && (dtimeout < 3000000)) begin
                @(posedge clk); #1;
                dtimeout = dtimeout + 1;
            end
            check_condition(dtimeout < 3000000, "default_byte_timeout");
            check_condition(dflt_probe_data === expected_mem[v_offset[0] + di], "default_byte");
            check_condition(dflt_probe_stop_error === 1'b0, "default_stop");
        end
        begin : dflt_retire_wait
            integer dtimeout;
            dtimeout = 0;
            @(posedge clk); #1;
            while ((dflt_busy === 1'b1) && (dtimeout < 3000000)) begin
                @(posedge clk); #1;
                dtimeout = dtimeout + 1;
            end
            check_condition(dtimeout < 3000000, "default_retire_timeout");
        end
        check_condition(dflt_busy === 1'b0, "default_retired");
        check_condition(dflt_stat_sent == 1, "default_sent");
        check_condition(dflt_tx === 1'b1, "default_tx_idle");
        check_condition(dflt_de === 1'b0, "default_de_idle");
        default_baud_frames = default_baud_frames + 1;
        end_case();

        begin_case("counter_saturation");
        @(negedge clk); #1;
        small_rst = 1'b1;
        @(posedge clk); #1;
        @(negedge clk); #1;
        small_rst = 1'b0;
        @(posedge clk); #1;
        for (integer si = 0; si < 4; si = si + 1) begin
            @(negedge clk); #1;
            check_condition(small_cfg_ready === 1'b1, "small_cfg_ready");
            small_cfg_valid = 1'b1;
            small_cfg_type = v_type[0][7:0];
            small_cfg_epoch = v_epoch[0][7:0];
            small_cfg_seq = v_seq[0][15:0];
            small_cfg_tick = v_tick[0][31:0];
            small_cfg_len = v_len[0][5:0];
            @(posedge clk); #1;
            small_cfg_valid = 1'b0;
            for (integer sb = 0; sb < v_count[0]; sb = sb + 1) begin
                integer stimeout;
                stimeout = 0;
                @(posedge clk); #1;
                while ((small_probe_valid !== 1'b1) && (stimeout < 10000)) begin
                    @(posedge clk); #1;
                    stimeout = stimeout + 1;
                end
                check_condition(stimeout < 10000, "small_byte_timeout");
                check_condition(small_probe_data === expected_mem[v_offset[0] + sb], "small_byte");
                check_condition(small_probe_stop_error === 1'b0, "small_stop");
            end
            begin : small_retire_wait
                integer stimeout;
                stimeout = 0;
                @(posedge clk); #1;
                while ((small_busy === 1'b1) && (stimeout < 10000)) begin
                    @(posedge clk); #1;
                    stimeout = stimeout + 1;
                end
                check_condition(stimeout < 10000, "small_retire_timeout");
            end
            saturation_success_frames = saturation_success_frames + 1;
        end
        check_condition(small_stat_admitted == 2'd3, "small_admitted_sat");
        check_condition(small_stat_sent == 2'd3, "small_sent_sat");
        for (integer sa = 0; sa < 4; sa = sa + 1) begin
            @(negedge clk); #1;
            check_condition(small_cfg_ready === 1'b1, "small_abort_cfg_ready");
            small_cfg_valid = 1'b1;
            small_cfg_type = v_type[1][7:0];
            small_cfg_epoch = v_epoch[1][7:0];
            small_cfg_seq = v_seq[1][15:0];
            small_cfg_tick = v_tick[1][31:0];
            small_cfg_len = v_len[1][5:0];
            @(posedge clk); #1;
            small_cfg_valid = 1'b0;
            @(negedge clk); #1;
            small_cancel = 1'b1;
            @(posedge clk); #1;
            check_condition(small_busy === 1'b0, "small_cancel_busy");
            @(negedge clk); #1;
            small_cancel = 1'b0;
            @(posedge clk); #1;
            saturation_abort_frames = saturation_abort_frames + 1;
        end
        check_condition(small_stat_aborted == 2'd3, "small_aborted_sat");
        @(negedge clk); #1;
        small_rst = 1'b1;
        @(posedge clk); #1;
        check_condition(small_stat_admitted == 0, "small_reset_admitted");
        check_condition(small_stat_sent == 0, "small_reset_sent");
        check_condition(small_stat_aborted == 0, "small_reset_aborted");
        @(negedge clk); #1;
        small_rst = 1'b0;
        @(posedge clk); #1;
        end_case();

        $display("# TB_STAT vector_frames=%0d", vectors_processed);
        $display("# TB_STAT lengths_covered=33");
        $display("# TB_STAT payload_byte_values_covered=256");
        $display("# TB_STAT max_metadata_vectors=%0d", max_metadata_vectors);
        $display("# TB_STAT bubble_vectors=%0d", bubble_vectors);
        $display("# TB_STAT bubble_cycles=%0d", main_bubble_cycles);
        $display("# TB_STAT packet_bytes_compared=%0d", packet_bytes_compared);
        $display("# TB_STAT same_edge_config_payload_cases=%0d", same_edge_config_payload_cases);
        $display("# TB_STAT cfg_held_busy_frames=%0d", cfg_held_busy_frames);
        $display("# TB_STAT illegal_length_cases=%0d", illegal_length_cases);
        $display("# TB_STAT illegal_last_cases=%0d", illegal_last_cases);
        $display("# TB_STAT fault_events_checked=%0d", fault_events_checked);
        $display("# TB_STAT cancel_phase_cases=%0d", cancel_phase_cases);
        $display("# TB_STAT reset_phase_cases=%0d", reset_phase_cases);
        $display("# TB_STAT held_cancel_sequences=%0d", held_cancel_sequences);
        $display("# TB_STAT preamble_cycles=%0d", preamble_cycles);
        $display("# TB_STAT postamble_cycles=%0d", postamble_cycles);
        $display("# TB_STAT fractional_baud_frames=%0d", fractional_baud_frames);
        $display("# TB_STAT default_baud_frames=%0d", default_baud_frames);
        $display("# TB_STAT saturation_success_frames=%0d", saturation_success_frames);
        $display("# TB_STAT saturation_abort_frames=%0d", saturation_abort_frames);
        $display("# TB_STAT expected_total_bytes=%0d", expected_total_bytes);
        $display("# TB_SUMMARY cases=%0d pass=%0d fail=%0d checks=%0d",
                 total_cases, total_pass_cases, total_fail_cases, total_checks);
        if (total_fail_cases == 0) $display("# TB_END pass");
        else $display("# TB_END fail");
        $finish;
    end
endmodule


module tb_wire_uart_tx_guard_clock_hz;
    logic clk = 1'b0;
    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic cfg_valid = 1'b0;
    logic [7:0] cfg_type = 8'd0;
    logic [7:0] cfg_epoch = 8'd0;
    logic [15:0] cfg_seq = 16'd0;
    logic [31:0] cfg_tick = 32'd0;
    logic [5:0] cfg_len = 6'd0;
    logic p_valid = 1'b0;
    logic [7:0] p_data = 8'd0;
    logic p_last = 1'b0;
    logic cfg_ready, p_ready, tx, de, busy, receiving, faulted, fault_event;
    logic [1:0] fault_code;
    logic [1:0] stat_admitted, stat_sent, stat_aborted;
    deepeye_wire_uart_tx #(.CLOCK_HZ(1), .BAUD(0), .PRE_CYCLES(-1),
                           .POST_CYCLES(65536), .STAT_W(1)) dut (
        .clk(clk), .rst(rst), .cancel(cancel), .cfg_valid(cfg_valid),
        .cfg_type(cfg_type), .cfg_epoch(cfg_epoch), .cfg_seq(cfg_seq),
        .cfg_tick(cfg_tick), .cfg_len(cfg_len), .p_valid(p_valid),
        .p_data(p_data), .p_last(p_last), .cfg_ready(cfg_ready),
        .p_ready(p_ready), .tx(tx), .de(de), .busy(busy),
        .receiving(receiving), .faulted(faulted), .fault_event(fault_event),
        .fault_code(fault_code), .stat_admitted(stat_admitted),
        .stat_sent(stat_sent), .stat_aborted(stat_aborted)
    );
    initial begin
        #1000;
        $display("GUARD_NOT_FIRED clock_hz");
        $finish;
    end
endmodule

module tb_wire_uart_tx_guard_baud;
    logic clk = 1'b0;
    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic cfg_valid = 1'b0;
    logic [7:0] cfg_type = 8'd0;
    logic [7:0] cfg_epoch = 8'd0;
    logic [15:0] cfg_seq = 16'd0;
    logic [31:0] cfg_tick = 32'd0;
    logic [5:0] cfg_len = 6'd0;
    logic p_valid = 1'b0;
    logic [7:0] p_data = 8'd0;
    logic p_last = 1'b0;
    logic cfg_ready, p_ready, tx, de, busy, receiving, faulted, fault_event;
    logic [1:0] fault_code;
    logic [1:0] stat_admitted, stat_sent, stat_aborted;
    deepeye_wire_uart_tx #(.CLOCK_HZ(100), .BAUD(51), .PRE_CYCLES(-1),
                           .POST_CYCLES(65536), .STAT_W(1)) dut (
        .clk(clk), .rst(rst), .cancel(cancel), .cfg_valid(cfg_valid),
        .cfg_type(cfg_type), .cfg_epoch(cfg_epoch), .cfg_seq(cfg_seq),
        .cfg_tick(cfg_tick), .cfg_len(cfg_len), .p_valid(p_valid),
        .p_data(p_data), .p_last(p_last), .cfg_ready(cfg_ready),
        .p_ready(p_ready), .tx(tx), .de(de), .busy(busy),
        .receiving(receiving), .faulted(faulted), .fault_event(fault_event),
        .fault_code(fault_code), .stat_admitted(stat_admitted),
        .stat_sent(stat_sent), .stat_aborted(stat_aborted)
    );
    initial begin
        #1000;
        $display("GUARD_NOT_FIRED baud");
        $finish;
    end
endmodule

module tb_wire_uart_tx_guard_pre_cycles;
    logic clk = 1'b0;
    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic cfg_valid = 1'b0;
    logic [7:0] cfg_type = 8'd0;
    logic [7:0] cfg_epoch = 8'd0;
    logic [15:0] cfg_seq = 16'd0;
    logic [31:0] cfg_tick = 32'd0;
    logic [5:0] cfg_len = 6'd0;
    logic p_valid = 1'b0;
    logic [7:0] p_data = 8'd0;
    logic p_last = 1'b0;
    logic cfg_ready, p_ready, tx, de, busy, receiving, faulted, fault_event;
    logic [1:0] fault_code;
    logic [1:0] stat_admitted, stat_sent, stat_aborted;
    deepeye_wire_uart_tx #(.CLOCK_HZ(100), .BAUD(10), .PRE_CYCLES(-1),
                           .POST_CYCLES(65536), .STAT_W(1)) dut (
        .clk(clk), .rst(rst), .cancel(cancel), .cfg_valid(cfg_valid),
        .cfg_type(cfg_type), .cfg_epoch(cfg_epoch), .cfg_seq(cfg_seq),
        .cfg_tick(cfg_tick), .cfg_len(cfg_len), .p_valid(p_valid),
        .p_data(p_data), .p_last(p_last), .cfg_ready(cfg_ready),
        .p_ready(p_ready), .tx(tx), .de(de), .busy(busy),
        .receiving(receiving), .faulted(faulted), .fault_event(fault_event),
        .fault_code(fault_code), .stat_admitted(stat_admitted),
        .stat_sent(stat_sent), .stat_aborted(stat_aborted)
    );
    initial begin
        #1000;
        $display("GUARD_NOT_FIRED pre_cycles");
        $finish;
    end
endmodule

module tb_wire_uart_tx_guard_post_cycles;
    logic clk = 1'b0;
    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic cfg_valid = 1'b0;
    logic [7:0] cfg_type = 8'd0;
    logic [7:0] cfg_epoch = 8'd0;
    logic [15:0] cfg_seq = 16'd0;
    logic [31:0] cfg_tick = 32'd0;
    logic [5:0] cfg_len = 6'd0;
    logic p_valid = 1'b0;
    logic [7:0] p_data = 8'd0;
    logic p_last = 1'b0;
    logic cfg_ready, p_ready, tx, de, busy, receiving, faulted, fault_event;
    logic [1:0] fault_code;
    logic [1:0] stat_admitted, stat_sent, stat_aborted;
    deepeye_wire_uart_tx #(.CLOCK_HZ(100), .BAUD(10), .PRE_CYCLES(0),
                           .POST_CYCLES(65536), .STAT_W(1)) dut (
        .clk(clk), .rst(rst), .cancel(cancel), .cfg_valid(cfg_valid),
        .cfg_type(cfg_type), .cfg_epoch(cfg_epoch), .cfg_seq(cfg_seq),
        .cfg_tick(cfg_tick), .cfg_len(cfg_len), .p_valid(p_valid),
        .p_data(p_data), .p_last(p_last), .cfg_ready(cfg_ready),
        .p_ready(p_ready), .tx(tx), .de(de), .busy(busy),
        .receiving(receiving), .faulted(faulted), .fault_event(fault_event),
        .fault_code(fault_code), .stat_admitted(stat_admitted),
        .stat_sent(stat_sent), .stat_aborted(stat_aborted)
    );
    initial begin
        #1000;
        $display("GUARD_NOT_FIRED post_cycles");
        $finish;
    end
endmodule

module tb_wire_uart_tx_guard_stat_w;
    logic clk = 1'b0;
    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic cfg_valid = 1'b0;
    logic [7:0] cfg_type = 8'd0;
    logic [7:0] cfg_epoch = 8'd0;
    logic [15:0] cfg_seq = 16'd0;
    logic [31:0] cfg_tick = 32'd0;
    logic [5:0] cfg_len = 6'd0;
    logic p_valid = 1'b0;
    logic [7:0] p_data = 8'd0;
    logic p_last = 1'b0;
    logic cfg_ready, p_ready, tx, de, busy, receiving, faulted, fault_event;
    logic [1:0] fault_code;
    logic [1:0] stat_admitted, stat_sent, stat_aborted;
    deepeye_wire_uart_tx #(.CLOCK_HZ(100), .BAUD(10), .PRE_CYCLES(0),
                           .POST_CYCLES(0), .STAT_W(1)) dut (
        .clk(clk), .rst(rst), .cancel(cancel), .cfg_valid(cfg_valid),
        .cfg_type(cfg_type), .cfg_epoch(cfg_epoch), .cfg_seq(cfg_seq),
        .cfg_tick(cfg_tick), .cfg_len(cfg_len), .p_valid(p_valid),
        .p_data(p_data), .p_last(p_last), .cfg_ready(cfg_ready),
        .p_ready(p_ready), .tx(tx), .de(de), .busy(busy),
        .receiving(receiving), .faulted(faulted), .fault_event(fault_event),
        .fault_code(fault_code), .stat_admitted(stat_admitted),
        .stat_sent(stat_sent), .stat_aborted(stat_aborted)
    );
    initial begin
        #1000;
        $display("GUARD_NOT_FIRED stat_w");
        $finish;
    end
endmodule

`default_nettype wire
