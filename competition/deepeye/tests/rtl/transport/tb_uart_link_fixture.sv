`timescale 1ps/1ps
`default_nettype none

// Test-only digital pin-to-pin UART link fixture.
//
// Work: B-UART-LINK-FIXTURE-20261024-34-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-UART-LINK-FIXTURE-20261024-34
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), canonical
// requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Exact source snapshot: bbfb11439b35e0866a6d2486f3857b92ed6cf529.
// Frozen design input: 1011259415a0916054eb580687612580bc1e5f09.
//
// This harness joins the two frozen compositions only at their public pins.
// It adds no RTL state, semantic packet, transport policy, motion grant, CDC,
// electrical, oscillator-tolerance or physical-board claim. The fault mux is a
// testbench-only digital impairment. Expected bytes come from a separately
// generated vector file, never from the TX output as the receive oracle.

module tb_uart_link_fixture #(
    parameter integer SUITE = 0,
    parameter integer TX_PERIOD_PS = 10000,
    parameter integer RX_PERIOD_PS = 10000,
    parameter integer RX_PHASE_PS = 2500,
    parameter integer TX_CLOCK_HZ = 64,
    parameter integer TX_BAUD = 4,
    parameter integer TX_PRE_CYCLES = 2,
    parameter integer TX_POST_CYCLES = 3,
    parameter integer RX_CLOCK_HZ = 64,
    parameter integer RX_BAUD = 4,
    parameter longint WATCHDOG_PS = 64'd100000000000,
    parameter integer EVENT_ROW_CAP = 200000
);

    localparam integer MAX_RECORDS = 128;
    localparam integer MAX_PAYLOAD = 32;
    localparam integer MAX_WIRE = 46;

    localparam integer MODE_NORMAL = 0;
    localparam integer MODE_BIT_ERROR = 1;
    localparam integer MODE_BAD_STOP = 2;
    localparam integer MODE_TX_CANCEL = 3;
    localparam integer MODE_RX_CANCEL_HEADER = 4;
    localparam integer MODE_RX_CANCEL_PAYLOAD = 5;
    localparam integer MODE_RX_CANCEL_PENDING = 6;
    localparam integer MODE_OVERRUN = 7;
    localparam integer MODE_RETIRED_THEN_ERROR = 8;
    localparam integer MODE_IMMEDIATE_PAIR = 20;

    localparam integer TX_HALF_PS = TX_PERIOD_PS / 2;
    localparam integer RX_HALF_PS = RX_PERIOD_PS / 2;
    localparam integer TX_BIT_CYCLES =
        (TX_CLOCK_HZ + TX_BAUD - 1) / TX_BAUD;
    localparam longint TX_BIT_PS = 64'(TX_BIT_CYCLES) * 64'(TX_PERIOD_PS);
    localparam longint TX_BYTE_PS = 64'(10) * TX_BIT_PS;
    localparam integer PENDING_CYCLES = 4;

    logic tx_clk;
    logic rx_clk;
    logic rst;
    logic tx_cancel;
    logic rx_cancel;

    logic cfg_valid;
    logic tx_cfg_ready;
    logic [7:0] cfg_type;
    logic [7:0] cfg_epoch;
    logic [15:0] cfg_seq;
    logic [31:0] cfg_tick;
    logic [5:0] cfg_len;

    logic p_valid;
    logic tx_p_ready;
    logic [7:0] p_data;
    logic p_last;

    logic tx_line;
    logic tx_de;
    logic tx_busy;
    logic tx_receiving;
    logic tx_faulted;
    logic tx_fault_event;
    logic [1:0] tx_fault_code;
    logic [31:0] tx_stat_admitted;
    logic [31:0] tx_stat_sent;
    logic [31:0] tx_stat_aborted;

    logic rx_out_ready;
    logic rx_out_valid;
    logic [7:0] rx_out_type;
    logic [7:0] rx_out_epoch;
    logic [15:0] rx_out_seq;
    logic [31:0] rx_out_tick;
    logic [5:0] rx_out_len;
    logic [255:0] rx_out_payload;
    logic rx_uart_busy;
    logic rx_receiving;
    logic rx_line_error_event;
    logic [2:0] rx_line_error_bits;
    logic rx_error_event;
    logic [1:0] rx_error_code;
    logic [31:0] rx_stat_uart_frames;
    logic [31:0] rx_stat_uart_retired;
    logic [31:0] rx_stat_uart_overruns;
    logic [31:0] rx_stat_uart_framing;
    logic [31:0] rx_stat_uart_false_starts;
    logic [31:0] rx_stat_uart_aborted;
    logic [31:0] rx_stat_bytes;
    logic [31:0] rx_stat_frames;
    logic [31:0] rx_stat_retired;
    logic [31:0] rx_stat_version;
    logic [31:0] rx_stat_length;
    logic [31:0] rx_stat_crc;
    logic [31:0] rx_stat_aborted;

    logic fault_enable;
    logic fault_value;
    logic rx_line;

    assign rx_line = fault_enable ? fault_value : tx_line;

    deepeye_wire_uart_tx #(
        .CLOCK_HZ(TX_CLOCK_HZ),
        .BAUD(TX_BAUD),
        .PRE_CYCLES(TX_PRE_CYCLES),
        .POST_CYCLES(TX_POST_CYCLES),
        .STAT_W(32)
    ) tx_dut (
        .clk(tx_clk),
        .rst(rst),
        .cancel(tx_cancel),
        .cfg_valid(cfg_valid),
        .cfg_ready(tx_cfg_ready),
        .cfg_type(cfg_type),
        .cfg_epoch(cfg_epoch),
        .cfg_seq(cfg_seq),
        .cfg_tick(cfg_tick),
        .cfg_len(cfg_len),
        .p_valid(p_valid),
        .p_ready(tx_p_ready),
        .p_data(p_data),
        .p_last(p_last),
        .tx(tx_line),
        .de(tx_de),
        .busy(tx_busy),
        .receiving(tx_receiving),
        .faulted(tx_faulted),
        .fault_event(tx_fault_event),
        .fault_code(tx_fault_code),
        .stat_admitted(tx_stat_admitted),
        .stat_sent(tx_stat_sent),
        .stat_aborted(tx_stat_aborted)
    );

    deepeye_uart_wire_rx #(
        .CLOCK_HZ(RX_CLOCK_HZ),
        .BAUD(RX_BAUD),
        .STAT_W(32)
    ) rx_dut (
        .clk(rx_clk),
        .rst(rst),
        .cancel(rx_cancel),
        .rx_async(rx_line),
        .out_ready(rx_out_ready),
        .out_valid(rx_out_valid),
        .out_type(rx_out_type),
        .out_epoch(rx_out_epoch),
        .out_seq(rx_out_seq),
        .out_tick(rx_out_tick),
        .out_len(rx_out_len),
        .out_payload(rx_out_payload),
        .uart_busy(rx_uart_busy),
        .receiving(rx_receiving),
        .line_error_event(rx_line_error_event),
        .line_error_bits(rx_line_error_bits),
        .error_event(rx_error_event),
        .error_code(rx_error_code),
        .stat_uart_frames(rx_stat_uart_frames),
        .stat_uart_retired(rx_stat_uart_retired),
        .stat_uart_overruns(rx_stat_uart_overruns),
        .stat_uart_framing(rx_stat_uart_framing),
        .stat_uart_false_starts(rx_stat_uart_false_starts),
        .stat_uart_aborted(rx_stat_uart_aborted),
        .stat_bytes(rx_stat_bytes),
        .stat_frames(rx_stat_frames),
        .stat_retired(rx_stat_retired),
        .stat_version(rx_stat_version),
        .stat_length(rx_stat_length),
        .stat_crc(rx_stat_crc),
        .stat_aborted(rx_stat_aborted)
    );

    integer n_records;
    integer n_cases;
    integer file_suite;
    integer vector_fd;
    integer event_fd;
    string vector_path;
    string event_path;
    logic logging_active;
    integer event_rows;

    integer r_case [0:MAX_RECORDS-1];
    integer r_index [0:MAX_RECORDS-1];
    integer r_last [0:MAX_RECORDS-1];
    integer r_mode [0:MAX_RECORDS-1];
    integer r_len [0:MAX_RECORDS-1];
    integer r_type [0:MAX_RECORDS-1];
    integer r_epoch [0:MAX_RECORDS-1];
    integer r_seq [0:MAX_RECORDS-1];
    integer r_tick [0:MAX_RECORDS-1];
    integer r_wire_len [0:MAX_RECORDS-1];
    integer r_target_byte [0:MAX_RECORDS-1];
    integer r_target_bit [0:MAX_RECORDS-1];
    integer r_expect_output [0:MAX_RECORDS-1];
    integer r_expect_sent [0:MAX_RECORDS-1];
    integer r_expect_aborted [0:MAX_RECORDS-1];
    integer r_expect_frames [0:MAX_RECORDS-1];
    logic [255:0] r_payload [0:MAX_RECORDS-1];
    logic [367:0] r_wire [0:MAX_RECORDS-1];

    integer checks;
    integer failures;
    integer cases_run;
    integer suite_checks_start;
    integer suite_fail_start;
    integer current_case_id;
    string current_case_name;

    integer obs_cfg_accepts;
    integer obs_payload_accepts;
    integer obs_out_handshakes;
    integer obs_parser_errors;
    integer obs_line_errors;
    integer obs_rx_cancel_asserts;
    integer obs_tx_cancel_asserts;
    logic [1:0] obs_last_parser_code;
    logic [2:0] obs_line_mask_seen;
    integer obs_last_parser_time;
    integer obs_last_line_time;
    logic obs_overrun_seen;
    logic obs_framing_seen;
    logic obs_pending_invalidated;
    logic last_cfg_while_busy;
    integer tx_edges;
    integer rx_edges;

    logic [31:0] prev_tx_admitted;
    logic [31:0] prev_tx_sent;
    logic [31:0] prev_tx_aborted;
    logic [31:0] prev_rx_stat_uart_frames;
    logic [31:0] prev_rx_stat_uart_retired;
    logic [31:0] prev_rx_stat_uart_overruns;
    logic [31:0] prev_rx_stat_uart_framing;
    logic [31:0] prev_rx_stat_uart_false_starts;
    logic [31:0] prev_rx_stat_uart_aborted;
    logic [31:0] prev_rx_stat_bytes;
    logic [31:0] prev_rx_stat_frames;
    logic [31:0] prev_rx_stat_retired;
    logic [31:0] prev_rx_stat_version;
    logic [31:0] prev_rx_stat_length;
    logic [31:0] prev_rx_stat_crc;
    logic [31:0] prev_rx_stat_aborted;
    logic prev_out_valid;
    logic prev_uart_busy;
    logic prev_receiving;

    initial begin
        tx_clk = 1'b0;
        #(TX_HALF_PS);
        forever begin
            tx_clk = 1'b1;
            #(TX_HALF_PS);
            tx_clk = 1'b0;
            #(TX_HALF_PS);
        end
    end

    initial begin
        rx_clk = 1'b0;
        #(RX_PHASE_PS);
        forever begin
            rx_clk = 1'b1;
            #(RX_HALF_PS);
            rx_clk = 1'b0;
            #(RX_HALF_PS);
        end
    end

    initial begin
        #(WATCHDOG_PS);
        $display("LINK_WATCHDOG_TIMEOUT suite=%0d t_ps=%0d", SUITE, $time);
        $fatal(1, "tb_uart_link_fixture: bounded watchdog expired");
    end

    task automatic log_event(input string message);
        begin
            if (logging_active) begin
                if (event_rows >= EVENT_ROW_CAP) begin
                    $fdisplay(event_fd,
                              "LINK_EVENT_LOG_TRUNCATED suite=%0d row_cap=%0d",
                              SUITE, EVENT_ROW_CAP);
                    $fatal(1, "tb_uart_link_fixture: event row cap reached");
                end
                event_rows = event_rows + 1;
                $fdisplay(event_fd, "t_ps=%0d %s", $time, message);
            end
        end
    endtask

    task automatic check_int(input integer actual, input integer expected,
                             input string label);
        begin
            checks = checks + 1;
            if (actual !== expected) begin
                failures = failures + 1;
                $display("CHECK_FAIL case=%s label=%s actual=%0d expected=%0d",
                         current_case_name, label, actual, expected);
                log_event($sformatf(
                    "CHECK_FAIL case=%s label=%s actual=%0d expected=%0d",
                    current_case_name, label, actual, expected));
            end
        end
    endtask

    task automatic check_true(input logic actual, input string label);
        begin
            checks = checks + 1;
            if (actual !== 1'b1) begin
                failures = failures + 1;
                $display("CHECK_FAIL case=%s label=%s actual_false",
                         current_case_name, label);
                log_event($sformatf(
                    "CHECK_FAIL case=%s label=%s actual_false",
                    current_case_name, label));
            end
        end
    endtask

    task automatic get_case_name(input integer suite_id, input integer case_id,
                                 output string name);
        begin
            name = $sformatf("s%0dc%0d", suite_id, case_id);
            case (suite_id)
                0: begin
                    case (case_id)
                        0: name = "default_zero_maxmeta";
                        1: name = "default_one_minmeta";
                    endcase
                end
                1: begin
                    if (case_id < 33) begin
                        name = $sformatf("len_%0d", case_id);
                    end else if (case_id == 33) begin
                        name = "immediate_pair";
                    end
                end
                2: begin
                    case (case_id)
                        0: name = "early_zero_extrema";
                        1: name = "early_one_minmeta";
                        2: name = "early_max_ramp";
                        3: name = "early_bubbles";
                    endcase
                end
                3: begin
                    case (case_id)
                        0: name = "late_zero_extrema";
                        1: name = "late_one_minmeta";
                        2: name = "late_max_ramp";
                        3: name = "late_bubbles";
                    endcase
                end
                4: begin
                    case (case_id)
                        0: name = "bit_error_crc";
                        1: name = "bad_stop_discard";
                        2: name = "tx_cancel_rx_recover";
                        3: name = "rx_cancel_header";
                        4: name = "rx_cancel_payload";
                        5: name = "rx_cancel_pending";
                        6: name = "uart_overrun_discard";
                        7: name = "retired_then_error";
                    endcase
                end
            endcase
        end
    endtask

    always @(posedge tx_clk) begin
        tx_edges = tx_edges + 1;
        if (logging_active) begin
            if ((tx_stat_admitted !== prev_tx_admitted) ||
                (tx_stat_sent !== prev_tx_sent) ||
                (tx_stat_aborted !== prev_tx_aborted)) begin
                log_event($sformatf(
                    "TX_STATS admitted=%0d sent=%0d aborted=%0d",
                    tx_stat_admitted, tx_stat_sent, tx_stat_aborted));
            end
        end
        prev_tx_admitted = tx_stat_admitted;
        prev_tx_sent = tx_stat_sent;
        prev_tx_aborted = tx_stat_aborted;
    end

    always @(posedge rx_clk) begin
        rx_edges = rx_edges + 1;
        if (logging_active) begin
            if ((rx_stat_uart_frames !== prev_rx_stat_uart_frames) ||
                (rx_stat_uart_retired !== prev_rx_stat_uart_retired) ||
                (rx_stat_uart_overruns !== prev_rx_stat_uart_overruns) ||
                (rx_stat_uart_framing !== prev_rx_stat_uart_framing) ||
                (rx_stat_uart_false_starts !== prev_rx_stat_uart_false_starts) ||
                (rx_stat_uart_aborted !== prev_rx_stat_uart_aborted) ||
                (rx_stat_bytes !== prev_rx_stat_bytes) ||
                (rx_stat_frames !== prev_rx_stat_frames) ||
                (rx_stat_retired !== prev_rx_stat_retired) ||
                (rx_stat_version !== prev_rx_stat_version) ||
                (rx_stat_length !== prev_rx_stat_length) ||
                (rx_stat_crc !== prev_rx_stat_crc) ||
                (rx_stat_aborted !== prev_rx_stat_aborted)) begin
                log_event($sformatf(
                    "RX_STATS uart_frames=%0d uart_retired=%0d uart_overruns=%0d uart_framing=%0d uart_false_starts=%0d uart_aborted=%0d bytes=%0d frames=%0d retired=%0d version=%0d length=%0d crc=%0d aborted=%0d",
                    rx_stat_uart_frames, rx_stat_uart_retired,
                    rx_stat_uart_overruns, rx_stat_uart_framing,
                    rx_stat_uart_false_starts, rx_stat_uart_aborted,
                    rx_stat_bytes, rx_stat_frames, rx_stat_retired,
                    rx_stat_version, rx_stat_length, rx_stat_crc,
                    rx_stat_aborted));
            end

            if (rx_uart_busy !== prev_uart_busy) begin
                log_event($sformatf("RX_UART_BUSY value=%0b", rx_uart_busy));
            end
            if (rx_receiving !== prev_receiving) begin
                log_event($sformatf("RX_PARSER_RECEIVING value=%0b",
                                     rx_receiving));
            end
            if (rx_line_error_event) begin
                obs_line_errors = obs_line_errors + 1;
                obs_line_mask_seen = obs_line_mask_seen | rx_line_error_bits;
                obs_last_line_time = $time;
                if (rx_line_error_bits[1]) obs_framing_seen = 1'b1;
                if (rx_line_error_bits[2]) obs_overrun_seen = 1'b1;
                log_event($sformatf(
                    "RX_LINE_ERROR bits=%03b overrun=%0b framing=%0b false_start=%0b",
                    rx_line_error_bits, rx_line_error_bits[2],
                    rx_line_error_bits[1], rx_line_error_bits[0]));
            end
            if (rx_error_event) begin
                obs_parser_errors = obs_parser_errors + 1;
                obs_last_parser_code = rx_error_code;
                obs_last_parser_time = $time;
                log_event($sformatf("RX_PARSER_ERROR code=%0d", rx_error_code));
            end
            if (prev_out_valid && !rx_out_valid && !rx_out_ready) begin
                obs_pending_invalidated = 1'b1;
                log_event("RX_OUT_PENDING_INVALIDATED");
            end
            if (rx_out_valid && rx_out_ready) begin
                obs_out_handshakes = obs_out_handshakes + 1;
                log_event($sformatf(
                    "RX_OUT_HANDSHAKE type=%02h epoch=%02h seq=%04h tick=%08h len=%0d payload=%064h",
                    rx_out_type, rx_out_epoch, rx_out_seq, rx_out_tick,
                    rx_out_len, rx_out_payload));
            end
        end
        prev_rx_stat_uart_frames = rx_stat_uart_frames;
        prev_rx_stat_uart_retired = rx_stat_uart_retired;
        prev_rx_stat_uart_overruns = rx_stat_uart_overruns;
        prev_rx_stat_uart_framing = rx_stat_uart_framing;
        prev_rx_stat_uart_false_starts = rx_stat_uart_false_starts;
        prev_rx_stat_uart_aborted = rx_stat_uart_aborted;
        prev_rx_stat_bytes = rx_stat_bytes;
        prev_rx_stat_frames = rx_stat_frames;
        prev_rx_stat_retired = rx_stat_retired;
        prev_rx_stat_version = rx_stat_version;
        prev_rx_stat_length = rx_stat_length;
        prev_rx_stat_crc = rx_stat_crc;
        prev_rx_stat_aborted = rx_stat_aborted;
        prev_out_valid = rx_out_valid;
        prev_uart_busy = rx_uart_busy;
        prev_receiving = rx_receiving;
    end

    always @(tx_line) begin
        if (logging_active) begin
            log_event($sformatf(
                "TX_PIN tx=%0b de=%0b busy=%0b", tx_line, tx_de, tx_busy));
        end
    end

    always @(tx_de) begin
        if (logging_active) begin
            log_event($sformatf("TX_DE value=%0b tx=%0b busy=%0b",
                                tx_de, tx_line, tx_busy));
        end
    end

    always @(tx_busy or tx_cfg_ready or tx_p_ready) begin
        if (logging_active) begin
            log_event($sformatf(
                "TX_HANDSHAKE_STATE busy=%0b cfg_ready=%0b p_ready=%0b",
                tx_busy, tx_cfg_ready, tx_p_ready));
        end
    end

    always @(rst) begin
        if (logging_active) begin
            log_event($sformatf("RESET value=%0b", rst));
        end
    end

    always @(tx_cancel) begin
        if (logging_active) begin
            if (tx_cancel) obs_tx_cancel_asserts = obs_tx_cancel_asserts + 1;
            log_event($sformatf("TX_CANCEL value=%0b", tx_cancel));
        end
    end

    always @(rx_cancel) begin
        if (logging_active) begin
            if (rx_cancel) obs_rx_cancel_asserts = obs_rx_cancel_asserts + 1;
            log_event($sformatf("RX_CANCEL value=%0b", rx_cancel));
        end
    end

    always @(fault_enable) begin
        if (logging_active) begin
            log_event($sformatf("RX_MUX_CONTROL enable=%0b value=%0b source=%0b",
                                fault_enable, fault_value, rx_line));
        end
    end

    always @(fault_value) begin
        if (logging_active) begin
            log_event($sformatf("RX_MUX_VALUE enable=%0b value=%0b source=%0b",
                                fault_enable, fault_value, rx_line));
        end
    end

    always @(rx_line) begin
        if (logging_active) begin
            log_event($sformatf("RX_INPUT_EDGE value=%0b mux=%0b tx=%0b",
                                rx_line, fault_enable, tx_line));
        end
    end

    always @(rx_out_valid) begin
        if (logging_active) begin
            log_event($sformatf(
                "RX_OUT_VALID value=%0b ready=%0b type=%02h len=%0d payload=%064h",
                rx_out_valid, rx_out_ready, rx_out_type, rx_out_len,
                rx_out_payload));
        end
    end

    always @(rx_out_ready) begin
        if (logging_active) begin
            log_event($sformatf("RX_OUT_READY value=%0b valid=%0b",
                                rx_out_ready, rx_out_valid));
        end
    end

    task automatic load_vectors;
        integer code;
        integer rec;
        integer byte_index;
        integer value;
        integer last_case;
        integer expected_index;
        begin
            if (!$value$plusargs("VECTOR_FILE=%s", vector_path)) begin
                $fatal(1, "tb_uart_link_fixture: missing +VECTOR_FILE");
            end
            vector_fd = $fopen(vector_path, "r");
            if (vector_fd == 0) begin
                $fatal(1, "tb_uart_link_fixture: cannot open vector file");
            end
            code = $fscanf(vector_fd, "%d %d", file_suite, n_records);
            if (code != 2) begin
                $fatal(1, "tb_uart_link_fixture: malformed vector header");
            end
            check_int(file_suite, SUITE, "vector_suite");
            check_true((n_records > 0) && (n_records <= MAX_RECORDS),
                       "vector_record_bound");
            n_cases = 0;
            last_case = -1;
            expected_index = 0;
            for (rec = 0; rec < n_records; rec = rec + 1) begin
                code = $fscanf(vector_fd,
                    "%d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d",
                    r_case[rec], r_index[rec], r_last[rec], r_mode[rec],
                    r_len[rec], r_type[rec], r_epoch[rec], r_seq[rec],
                    r_tick[rec], r_wire_len[rec], r_target_byte[rec],
                    r_target_bit[rec], r_expect_output[rec],
                    r_expect_sent[rec], r_expect_aborted[rec],
                    r_expect_frames[rec]);
                if (code != 16) begin
                    $fatal(1, "tb_uart_link_fixture: malformed record header");
                end
                if (r_case[rec] != last_case) begin
                    if (r_case[rec] != last_case + 1) begin
                        $fatal(1, "tb_uart_link_fixture: noncontiguous case ids");
                    end
                    last_case = r_case[rec];
                    expected_index = 0;
                    n_cases = n_cases + 1;
                end
                check_int(r_index[rec], expected_index, "record_index");
                expected_index = expected_index + 1;
                check_true((r_len[rec] >= 0) && (r_len[rec] <= 32),
                           "record_length_bound");
                check_int(r_wire_len[rec], r_len[rec] + 14,
                          "record_wire_length");
                r_payload[rec] = '0;
                for (byte_index = 0; byte_index < MAX_PAYLOAD;
                     byte_index = byte_index + 1) begin
                    code = $fscanf(vector_fd, "%d", value);
                    if (code != 1 || value < 0 || value > 255) begin
                        $fatal(1, "tb_uart_link_fixture: malformed payload byte");
                    end
                    r_payload[rec][byte_index*8 +: 8] = value[7:0];
                end
                r_wire[rec] = '0;
                for (byte_index = 0; byte_index < MAX_WIRE;
                     byte_index = byte_index + 1) begin
                    code = $fscanf(vector_fd, "%d", value);
                    if (code != 1 || value < 0 || value > 255) begin
                        $fatal(1, "tb_uart_link_fixture: malformed wire byte");
                    end
                    r_wire[rec][byte_index*8 +: 8] = value[7:0];
                end
            end
            $fclose(vector_fd);
            if (r_last[n_records-1] != 1) begin
                $fatal(1, "tb_uart_link_fixture: missing final case terminator");
            end
        end
    endtask

    task automatic start_config(input integer rec);
        begin
            @(negedge tx_clk);
            cfg_type = r_type[rec][7:0];
            cfg_epoch = r_epoch[rec][7:0];
            cfg_seq = r_seq[rec][15:0];
            cfg_tick = r_tick[rec][31:0];
            cfg_len = r_len[rec][5:0];
            cfg_valid = 1'b1;
            last_cfg_while_busy = tx_busy;
            log_event($sformatf(
                "TX_CFG_DRIVE type=%02h epoch=%02h seq=%04h tick=%08h len=%0d busy=%0b",
                cfg_type, cfg_epoch, cfg_seq, cfg_tick, cfg_len, tx_busy));
            @(posedge tx_clk);
            while (!(cfg_valid && tx_cfg_ready)) begin
                @(posedge tx_clk);
            end
            obs_cfg_accepts = obs_cfg_accepts + 1;
            log_event($sformatf(
                "TX_CFG_ACCEPT type=%02h epoch=%02h seq=%04h tick=%08h len=%0d",
                cfg_type, cfg_epoch, cfg_seq, cfg_tick, cfg_len));
            @(negedge tx_clk);
            cfg_valid = 1'b0;
        end
    endtask

    task automatic feed_payload(input integer rec);
        integer index;
        integer bubble;
        begin
            for (index = 0; index < r_len[rec]; index = index + 1) begin
                bubble = 1 + ((index + rec) % 3);
                repeat (bubble) @(negedge tx_clk);
                p_data = r_payload[rec][index*8 +: 8];
                p_last = (index == (r_len[rec] - 1));
                p_valid = 1'b1;
                log_event($sformatf(
                    "TX_PAYLOAD_DRIVE index=%0d data=%02h last=%0b",
                    index, p_data, p_last));
                @(posedge tx_clk);
                while (!(p_valid && tx_p_ready)) begin
                    @(posedge tx_clk);
                end
                obs_payload_accepts = obs_payload_accepts + 1;
                log_event($sformatf(
                    "TX_PAYLOAD_ACCEPT index=%0d data=%02h last=%0b",
                    index, p_data, p_last));
                @(negedge tx_clk);
                p_valid = 1'b0;
            end
        end
    endtask

    task automatic wait_frame_done(input integer rec);
        begin
            @(posedge tx_clk);
            while (tx_busy) begin
                @(posedge tx_clk);
            end
            #1;
            log_event($sformatf(
                "TX_FRAME_DONE sent=%0d aborted=%0d tx=%0b de=%0b",
                tx_stat_sent, tx_stat_aborted, tx_line, tx_de));
        end
    endtask

    task automatic send_full(input integer rec);
        begin
            start_config(rec);
            feed_payload(rec);
            wait_frame_done(rec);
        end
    endtask

    task automatic accept_output(input integer rec);
        integer mismatch_count;
        integer before_handshakes;
        integer index;
        integer hold_cycles;
        logic [7:0] out_type_sample;
        logic [7:0] out_epoch_sample;
        logic [15:0] out_seq_sample;
        logic [31:0] out_tick_sample;
        logic [5:0] out_len_sample;
        logic [255:0] out_payload_sample;
        begin
            rx_out_ready = 1'b0;
            while (!rx_out_valid) @(posedge rx_clk);
            hold_cycles = PENDING_CYCLES + (r_index[rec] % 3);
            repeat (hold_cycles) @(posedge rx_clk);
            log_event($sformatf(
                "RX_OUT_PENDING_HELD type=%02h seq=%04h len=%0d",
                rx_out_valid ? rx_out_type : 8'h00,
                rx_out_valid ? rx_out_seq : 16'h0000,
                rx_out_valid ? rx_out_len : 6'd0));
            before_handshakes = obs_out_handshakes;
            @(negedge rx_clk);
            rx_out_ready = 1'b1;
            @(posedge rx_clk);
            out_type_sample = rx_out_type;
            out_epoch_sample = rx_out_epoch;
            out_seq_sample = rx_out_seq;
            out_tick_sample = rx_out_tick;
            out_len_sample = rx_out_len;
            out_payload_sample = rx_out_payload;
            #1;
            mismatch_count = 0;
            if (out_type_sample !== r_type[rec][7:0]) mismatch_count = mismatch_count + 1;
            if (out_epoch_sample !== r_epoch[rec][7:0]) mismatch_count = mismatch_count + 1;
            if (out_seq_sample !== r_seq[rec][15:0]) mismatch_count = mismatch_count + 1;
            if (out_tick_sample !== r_tick[rec][31:0]) mismatch_count = mismatch_count + 1;
            if (out_len_sample !== r_len[rec][5:0]) mismatch_count = mismatch_count + 1;
            for (index = 0; index < MAX_PAYLOAD; index = index + 1) begin
                if (out_payload_sample[index*8 +: 8] !==
                    r_payload[rec][index*8 +: 8]) begin
                    mismatch_count = mismatch_count + 1;
                end
            end
            if (obs_out_handshakes != (before_handshakes + 1)) begin
                mismatch_count = mismatch_count + 1;
            end
            log_event($sformatf(
                "RX_OUT_ACCEPT type=%02h epoch=%02h seq=%04h tick=%08h len=%0d payload=%064h",
                out_type_sample, out_epoch_sample, out_seq_sample,
                out_tick_sample, out_len_sample, out_payload_sample));
            check_int(mismatch_count, 0,
                      $sformatf("descriptor_record_%0d", rec));
            @(negedge rx_clk);
            rx_out_ready = 1'b0;
        end
    endtask

    task automatic wait_pending_output(input string label);
        begin
            while (!rx_out_valid) @(posedge rx_clk);
            log_event($sformatf("RX_OUT_PENDING %s type=%02h seq=%04h len=%0d",
                                label, rx_out_type, rx_out_seq, rx_out_len));
        end
    endtask

    task automatic inject_bit_error(input integer byte_index,
                                    input integer bit_index);
        integer current_byte;
        begin
            wait (tx_de === 1'b1);
            wait (tx_line === 1'b0);
            for (current_byte = 0; current_byte < byte_index;
                 current_byte = current_byte + 1) begin
                #(TX_BYTE_PS - (4 * TX_PERIOD_PS));
                wait (tx_line === 1'b0);
            end
            #(TX_BIT_PS * (bit_index + 1) + 1);
            fault_value = ~tx_line;
            fault_enable = 1'b1;
            log_event($sformatf(
                "FAULT_BIT_ERROR byte=%0d bit=%0d forced=%0b",
                byte_index, bit_index, fault_value));
            #(TX_BIT_PS - 2);
            fault_enable = 1'b0;
            fault_value = 1'b1;
            log_event("FAULT_BIT_ERROR_RELEASE");
        end
    endtask

    task automatic inject_bad_stop(input integer byte_index);
        integer current_byte;
        begin
            wait (tx_de === 1'b1);
            wait (tx_line === 1'b0);
            for (current_byte = 0; current_byte < byte_index;
                 current_byte = current_byte + 1) begin
                #(TX_BYTE_PS - (4 * TX_PERIOD_PS));
                wait (tx_line === 1'b0);
            end
            #(TX_BIT_PS * 9 + 1);
            fault_value = 1'b0;
            fault_enable = 1'b1;
            log_event($sformatf("FAULT_BAD_STOP byte=%0d forced_low=1",
                                byte_index));
            #(TX_BIT_PS - 2);
            fault_enable = 1'b0;
            fault_value = 1'b1;
            log_event("FAULT_BAD_STOP_RELEASE");
        end
    endtask

    task automatic release_rx_cancel_after_tx(input string label);
        begin
            while (tx_busy) @(posedge tx_clk);
            wait (tx_line === 1'b1);
            repeat (4) @(posedge rx_clk);
            @(negedge rx_clk);
            rx_cancel = 1'b0;
            log_event($sformatf("RX_CANCEL_RELEASE reason=%s", label));
            repeat (4) @(posedge rx_clk);
        end
    endtask

    task automatic run_normal_case(input integer case_start,
                                   input integer case_end);
        integer rec;
        begin
            for (rec = case_start; rec <= case_end; rec = rec + 1) begin
                send_full(rec);
                accept_output(rec);
            end
        end
    endtask

    task automatic run_immediate_pair(input integer case_start,
                                      input integer case_end);
        begin
            if ((case_end - case_start) != 1) begin
                $fatal(1, "tb_uart_link_fixture: immediate pair record count");
            end
            start_config(case_start);
            feed_payload(case_start);
            start_config(case_end);
            check_true(last_cfg_while_busy,
                       "immediate_cfg_driven_while_busy");
            accept_output(case_start);
            feed_payload(case_end);
            wait_frame_done(case_end);
            accept_output(case_end);
        end
    endtask

    task automatic run_bit_error_case(input integer case_start,
                                      input integer case_end);
        integer parser_before;
        integer crc_before;
        begin
            if ((case_end - case_start) != 1) begin
                $fatal(1, "tb_uart_link_fixture: bit-error record count");
            end
            parser_before = obs_parser_errors;
            crc_before = rx_stat_crc;
            fork
                send_full(case_start);
                inject_bit_error(r_target_byte[case_start],
                                 r_target_bit[case_start]);
            join
            #1;
            check_true((obs_parser_errors - parser_before) >= 1,
                       "bit_error_parser_event");
            check_int(obs_last_parser_code, 3, "bit_error_crc_code");
            check_true((rx_stat_crc - crc_before) >= 1,
                       "bit_error_crc_counter");
            check_true(rx_out_valid === 1'b0, "bit_error_no_output");
            repeat (4) @(posedge rx_clk);
            send_full(case_end);
            accept_output(case_end);
        end
    endtask

    task automatic run_bad_stop_case(input integer case_start,
                                     input integer case_end);
        integer line_before;
        integer framing_before;
        integer aborted_before;
        begin
            if ((case_end - case_start) != 1) begin
                $fatal(1, "tb_uart_link_fixture: bad-stop record count");
            end
            line_before = obs_line_errors;
            framing_before = rx_stat_uart_framing;
            aborted_before = rx_stat_aborted;
            fork
                send_full(case_start);
                inject_bad_stop(r_target_byte[case_start]);
            join
            #1;
            check_true((obs_line_errors - line_before) >= 1,
                       "bad_stop_line_event");
            check_true((obs_line_mask_seen & 3'b010) == 3'b010,
                       "bad_stop_framing_bit");
            check_true((rx_stat_uart_framing - framing_before) >= 1,
                       "bad_stop_framing_counter");
            check_true((rx_stat_aborted - aborted_before) >= 1,
                       "bad_stop_parser_abort");
            check_true(rx_out_valid === 1'b0, "bad_stop_no_output");
            @(negedge rx_clk);
            rx_cancel = 1'b1;
            log_event("RX_CANCEL_ASSERT reason=bad_stop_recovery");
            release_rx_cancel_after_tx("bad_stop_recovery");
            send_full(case_end);
            accept_output(case_end);
        end
    endtask

    task automatic run_tx_cancel_case(input integer case_start,
                                      input integer case_end);
        integer uart_aborted_before;
        integer parser_aborted_before;
        integer cancel_before;
        begin
            if ((case_end - case_start) != 1) begin
                $fatal(1, "tb_uart_link_fixture: tx-cancel record count");
            end
            uart_aborted_before = rx_stat_uart_aborted;
            parser_aborted_before = rx_stat_aborted;
            cancel_before = obs_rx_cancel_asserts;
            fork
                send_full(case_start);
                begin
                    wait (tx_de === 1'b1);
                    #(3 * TX_BYTE_PS);
                    @(negedge tx_clk);
                    tx_cancel = 1'b1;
                    log_event("TX_CANCEL_ASSERT reason=mid_frame");
                    @(negedge rx_clk);
                    rx_cancel = 1'b1;
                    log_event("RX_CANCEL_ASSERT reason=tx_cancel_recovery");
                end
            join
            repeat (3) @(posedge tx_clk);
            @(negedge tx_clk);
            tx_cancel = 1'b0;
            log_event("TX_CANCEL_RELEASE reason=mid_frame");
            release_rx_cancel_after_tx("tx_cancel_recovery");
            check_true((rx_stat_uart_aborted - uart_aborted_before) >= 1,
                       "tx_cancel_uart_abort");
            check_true((rx_stat_aborted - parser_aborted_before) >= 1,
                       "tx_cancel_parser_abort");
            check_int(obs_rx_cancel_asserts - cancel_before, 1,
                      "tx_cancel_explicit_rx_cancel");
            check_true(rx_out_valid === 1'b0, "tx_cancel_no_output");
            send_full(case_end);
            accept_output(case_end);
        end
    endtask

    task automatic run_rx_cancel_case(input integer case_start,
                                      input integer case_end,
                                      input logic in_payload);
        integer uart_aborted_before;
        integer parser_aborted_before;
        integer cancel_before;
        begin
            if ((case_end - case_start) != 1) begin
                $fatal(1, "tb_uart_link_fixture: rx-cancel record count");
            end
            uart_aborted_before = rx_stat_uart_aborted;
            parser_aborted_before = rx_stat_aborted;
            cancel_before = obs_rx_cancel_asserts;
            fork
                send_full(case_start);
                begin
                    wait (rx_receiving === 1'b1);
                    if (in_payload) begin
                        #(12 * TX_BYTE_PS);
                        check_true(rx_receiving === 1'b1,
                                   "rx_cancel_payload_still_receiving");
                    end
                    @(negedge rx_clk);
                    rx_cancel = 1'b1;
                    log_event(in_payload
                        ? "RX_CANCEL_ASSERT reason=payload"
                        : "RX_CANCEL_ASSERT reason=header");
                end
            join
            release_rx_cancel_after_tx(in_payload
                ? "payload" : "header");
            if (in_payload) begin
                check_true((rx_stat_uart_aborted - uart_aborted_before) >= 1,
                           "rx_cancel_uart_abort");
            end else begin
                check_int(rx_stat_uart_aborted - uart_aborted_before, 0,
                          "rx_cancel_no_active_uart");
            end
            check_true((rx_stat_aborted - parser_aborted_before) >= 1,
                       "rx_cancel_parser_abort");
            check_int(obs_rx_cancel_asserts - cancel_before, 1,
                      "rx_cancel_assert_once");
            check_true(rx_out_valid === 1'b0, "rx_cancel_no_output");
            send_full(case_end);
            accept_output(case_end);
        end
    endtask

    task automatic run_pending_cancel_case(input integer case_start,
                                           input integer case_end);
        integer uart_aborted_before;
        integer parser_aborted_before;
        integer cancel_before;
        integer handshakes_before;
        begin
            if ((case_end - case_start) != 1) begin
                $fatal(1, "tb_uart_link_fixture: pending-cancel record count");
            end
            uart_aborted_before = rx_stat_uart_aborted;
            parser_aborted_before = rx_stat_aborted;
            cancel_before = obs_rx_cancel_asserts;
            handshakes_before = obs_out_handshakes;
            rx_out_ready = 1'b0;
            send_full(case_start);
            wait_pending_output("pending_cancel");
            repeat (5) @(posedge rx_clk);
            @(negedge rx_clk);
            rx_cancel = 1'b1;
            log_event("RX_CANCEL_ASSERT reason=pending_output");
            #1;
            check_true(rx_out_valid === 1'b0,
                       "pending_cancel_valid_cleared");
            repeat (3) @(posedge rx_clk);
            @(negedge rx_clk);
            rx_cancel = 1'b0;
            log_event("RX_CANCEL_RELEASE reason=pending_output");
            repeat (4) @(posedge rx_clk);
            check_int(obs_out_handshakes - handshakes_before, 0,
                      "pending_cancel_no_handshake");
            check_int(rx_stat_uart_aborted - uart_aborted_before, 0,
                      "pending_cancel_no_active_uart");
            check_true((rx_stat_aborted - parser_aborted_before) >= 1,
                       "pending_cancel_parser_abort");
            check_int(obs_rx_cancel_asserts - cancel_before, 1,
                      "pending_cancel_assert_once");
            send_full(case_end);
            accept_output(case_end);
        end
    endtask

    task automatic run_overrun_case(input integer case_start,
                                    input integer case_end);
        integer overrun_before;
        integer uart_aborted_before;
        integer parser_aborted_before;
        integer cancel_before;
        integer handshakes_before;
        begin
            if ((case_end - case_start) != 2) begin
                $fatal(1, "tb_uart_link_fixture: overrun record count");
            end
            overrun_before = rx_stat_uart_overruns;
            uart_aborted_before = rx_stat_uart_aborted;
            parser_aborted_before = rx_stat_aborted;
            cancel_before = obs_rx_cancel_asserts;
            handshakes_before = obs_out_handshakes;
            rx_out_ready = 1'b0;
            send_full(case_start);
            wait_pending_output("overrun_first_candidate");
            fork
                send_full(case_start + 1);
                begin
                    wait ((rx_line_error_event === 1'b1) &&
                          (rx_line_error_bits[2] === 1'b1));
                    log_event("RX_OVERRUN_OBSERVED");
                end
            join
            #1;
            check_true(obs_overrun_seen, "overrun_line_bit");
            check_true((rx_stat_uart_overruns - overrun_before) >= 1,
                       "overrun_uart_counter");
            check_true(rx_out_valid === 1'b0,
                       "overrun_pending_candidate_discarded");
            check_true(obs_pending_invalidated,
                       "overrun_pending_invalidated_edge");
            @(negedge rx_clk);
            rx_cancel = 1'b1;
            log_event("RX_CANCEL_ASSERT reason=overrun_recovery");
            repeat (3) @(posedge rx_clk);
            @(negedge rx_clk);
            rx_cancel = 1'b0;
            log_event("RX_CANCEL_RELEASE reason=overrun_recovery");
            repeat (4) @(posedge rx_clk);
            check_int(obs_out_handshakes - handshakes_before, 0,
                      "overrun_no_handshake");
            check_true((rx_stat_uart_aborted - uart_aborted_before) >= 1,
                       "overrun_uart_abort");
            check_true((rx_stat_aborted - parser_aborted_before) >= 1,
                       "overrun_parser_abort");
            check_int(obs_rx_cancel_asserts - cancel_before, 1,
                      "overrun_explicit_cancel_once");
            send_full(case_end);
            accept_output(case_end);
        end
    endtask

    task automatic run_retired_then_error_case(input integer case_start,
                                               input integer case_end);
        integer parser_before;
        integer retired_time;
        begin
            if ((case_end - case_start) != 2) begin
                $fatal(1, "tb_uart_link_fixture: retired-error record count");
            end
            send_full(case_start);
            accept_output(case_start);
            retired_time = $time;
            log_event($sformatf("RETIRED_BEFORE_LATER_ERROR t_ps=%0d",
                                retired_time));
            parser_before = obs_parser_errors;
            fork
                send_full(case_start + 1);
                inject_bit_error(r_target_byte[case_start + 1],
                                 r_target_bit[case_start + 1]);
            join
            #1;
            check_true((obs_parser_errors - parser_before) >= 1,
                       "retired_error_parser_event");
            check_int(obs_last_parser_code, 3, "retired_error_crc_code");
            check_true(obs_last_parser_time > retired_time,
                       "retired_candidate_precedes_error");
            send_full(case_end);
            accept_output(case_end);
        end
    endtask

    task automatic finish_case(input integer case_start,
                               input integer case_end,
                               input integer out_before,
                               input integer sent_before,
                               input integer aborted_before,
                               input integer frames_before,
                               input integer retired_before,
                               input integer admitted_before,
                               input integer case_checks_start,
                               input integer case_fail_start);
        integer rec;
        integer expect_outputs;
        integer expect_sent;
        integer expect_aborted;
        integer expect_frames;
        integer mismatch_count;
        begin
            expect_outputs = 0;
            expect_sent = 0;
            expect_aborted = 0;
            expect_frames = 0;
            for (rec = case_start; rec <= case_end; rec = rec + 1) begin
                expect_outputs = expect_outputs + r_expect_output[rec];
                expect_sent = expect_sent + r_expect_sent[rec];
                expect_aborted = expect_aborted + r_expect_aborted[rec];
                expect_frames = expect_frames + r_expect_frames[rec];
            end
            mismatch_count = 0;
            if ((obs_out_handshakes - out_before) != expect_outputs) begin
                mismatch_count = mismatch_count + 1;
                $display("CASE_TOTAL_MISMATCH %s outputs actual=%0d expected=%0d",
                         current_case_name, obs_out_handshakes - out_before,
                         expect_outputs);
            end
            if ((tx_stat_sent - sent_before) != expect_sent) begin
                mismatch_count = mismatch_count + 1;
                $display("CASE_TOTAL_MISMATCH %s sent actual=%0d expected=%0d",
                         current_case_name, tx_stat_sent - sent_before,
                         expect_sent);
            end
            if ((tx_stat_aborted - aborted_before) != expect_aborted) begin
                mismatch_count = mismatch_count + 1;
                $display("CASE_TOTAL_MISMATCH %s aborted actual=%0d expected=%0d",
                         current_case_name, tx_stat_aborted - aborted_before,
                         expect_aborted);
            end
            if ((rx_stat_frames - frames_before) != expect_frames) begin
                mismatch_count = mismatch_count + 1;
                $display("CASE_TOTAL_MISMATCH %s parser_frames actual=%0d expected=%0d",
                         current_case_name, rx_stat_frames - frames_before,
                         expect_frames);
            end
            if ((rx_stat_retired - retired_before) != expect_outputs) begin
                mismatch_count = mismatch_count + 1;
                $display("CASE_TOTAL_MISMATCH %s parser_retired actual=%0d expected=%0d",
                         current_case_name, rx_stat_retired - retired_before,
                         expect_outputs);
            end
            if ((tx_stat_admitted - admitted_before) !=
                ((case_end - case_start) + 1)) begin
                mismatch_count = mismatch_count + 1;
                $display("CASE_TOTAL_MISMATCH %s admitted actual=%0d expected=%0d",
                         current_case_name, tx_stat_admitted - admitted_before,
                         (case_end - case_start) + 1);
            end
            check_int(mismatch_count, 0, "case_counter_totals");
            cases_run = cases_run + 1;
            $display("CASE_END suite=%0d case=%0d name=%s checks=%0d failures=%0d result=%s",
                     SUITE, current_case_id, current_case_name,
                     checks - case_checks_start,
                     failures - case_fail_start,
                     (failures == case_fail_start) ? "PASS" : "FAIL");
        end
    endtask

    initial begin
        integer rec;
        integer case_start;
        integer case_end;
        integer dispatch_mode;
        integer out_before;
        integer sent_before;
        integer aborted_before;
        integer frames_before;
        integer retired_before;
        integer admitted_before;
        integer case_checks_start;
        integer case_fail_start;
        integer total_payload;
        integer total_wire;
        integer total_outputs;
        integer total_frames;
        integer total_sent;
        integer total_aborted;

        rst = 1'b1;
        tx_cancel = 1'b0;
        rx_cancel = 1'b0;
        cfg_valid = 1'b0;
        cfg_type = 8'h00;
        cfg_epoch = 8'h00;
        cfg_seq = 16'h0000;
        cfg_tick = 32'h00000000;
        cfg_len = 6'd0;
        p_valid = 1'b0;
        p_data = 8'h00;
        p_last = 1'b0;
        rx_out_ready = 1'b0;
        fault_enable = 1'b0;
        fault_value = 1'b1;
        logging_active = 1'b0;
        event_rows = 0;
        checks = 0;
        failures = 0;
        cases_run = 0;
        current_case_id = -1;
        current_case_name = "unset";
        obs_cfg_accepts = 0;
        obs_payload_accepts = 0;
        obs_out_handshakes = 0;
        obs_parser_errors = 0;
        obs_line_errors = 0;
        obs_rx_cancel_asserts = 0;
        obs_tx_cancel_asserts = 0;
        obs_last_parser_code = 2'b00;
        obs_line_mask_seen = 3'b000;
        obs_last_parser_time = -1;
        obs_last_line_time = -1;
        obs_overrun_seen = 1'b0;
        obs_framing_seen = 1'b0;
        obs_pending_invalidated = 1'b0;
        last_cfg_while_busy = 1'b0;
        tx_edges = 0;
        rx_edges = 0;
        prev_tx_admitted = 32'd0;
        prev_tx_sent = 32'd0;
        prev_tx_aborted = 32'd0;
        prev_out_valid = 1'b0;
        prev_uart_busy = 1'b0;
        prev_receiving = 1'b0;

        if ((TX_PERIOD_PS < 2) || ((TX_PERIOD_PS % 2) != 0) ||
            (RX_PERIOD_PS < 2) || ((RX_PERIOD_PS % 2) != 0) ||
            (RX_PHASE_PS < 0) || (TX_CLOCK_HZ < 2) ||
            (RX_CLOCK_HZ < 2) || (TX_BAUD < 1) || (RX_BAUD < 1) ||
            (EVENT_ROW_CAP < 1)) begin
            $fatal(1, "tb_uart_link_fixture: invalid top parameters");
        end

        if (!$value$plusargs("EVENT_LOG=%s", event_path)) begin
            $fatal(1, "tb_uart_link_fixture: missing +EVENT_LOG");
        end
        event_fd = $fopen(event_path, "w");
        if (event_fd == 0) begin
            $fatal(1, "tb_uart_link_fixture: cannot open event log");
        end
        logging_active = 1'b1;
        log_event($sformatf(
            "LINK_CLOCK_PROFILE suite=%0d tx_period_ps=%0d tx_half_ps=%0d tx_first_rise_ps=%0d rx_period_ps=%0d rx_half_ps=%0d rx_first_rise_ps=%0d rx_phase_ps=%0d tx_clock_hz=%0d tx_baud=%0d tx_pre=%0d tx_post=%0d rx_clock_hz=%0d rx_baud=%0d",
            SUITE, TX_PERIOD_PS, TX_HALF_PS, TX_HALF_PS, RX_PERIOD_PS,
            RX_HALF_PS, RX_PHASE_PS, RX_PHASE_PS, TX_CLOCK_HZ, TX_BAUD,
            TX_PRE_CYCLES, TX_POST_CYCLES, RX_CLOCK_HZ, RX_BAUD));

        suite_checks_start = checks;
        suite_fail_start = failures;
        load_vectors;
        $display("LINK_SUITE_BEGIN suite=%0d cases=%0d records=%0d tx_clock_hz=%0d tx_baud=%0d tx_pre=%0d tx_post=%0d rx_clock_hz=%0d rx_baud=%0d tx_period_ps=%0d rx_period_ps=%0d rx_phase_ps=%0d",
                 SUITE, n_cases, n_records, TX_CLOCK_HZ, TX_BAUD,
                 TX_PRE_CYCLES, TX_POST_CYCLES, RX_CLOCK_HZ, RX_BAUD,
                 TX_PERIOD_PS, RX_PERIOD_PS, RX_PHASE_PS);

        repeat (12) @(posedge tx_clk);
        repeat (12) @(posedge rx_clk);
        @(negedge tx_clk);
        rst = 1'b0;
        log_event("RESET_DEASSERT");
        repeat (6) @(posedge rx_clk);
        repeat (3) @(posedge tx_clk);

        total_payload = 0;
        total_wire = 0;
        total_outputs = 0;
        total_frames = 0;
        total_sent = 0;
        total_aborted = 0;
        for (rec = 0; rec < n_records; rec = rec + 1) begin
            total_payload = total_payload + r_len[rec];
            total_wire = total_wire + r_wire_len[rec];
            total_outputs = total_outputs + r_expect_output[rec];
            total_frames = total_frames + r_expect_frames[rec];
            total_sent = total_sent + r_expect_sent[rec];
            total_aborted = total_aborted + r_expect_aborted[rec];
        end

        rec = 0;
        while (rec < n_records) begin
            case_start = rec;
            current_case_id = r_case[rec];
            get_case_name(SUITE, current_case_id, current_case_name);
            while (((rec + 1) < n_records) &&
                   (r_case[rec + 1] == current_case_id)) begin
                rec = rec + 1;
            end
            case_end = rec;
            if (r_last[case_end] != 1) begin
                $fatal(1, "tb_uart_link_fixture: case missing terminator");
            end
            $display("CASE_BEGIN suite=%0d case=%0d name=%s mode=%0d records=%0d",
                     SUITE, current_case_id, current_case_name,
                     r_mode[case_start], (case_end - case_start) + 1);
            out_before = obs_out_handshakes;
            sent_before = tx_stat_sent;
            aborted_before = tx_stat_aborted;
            frames_before = rx_stat_frames;
            retired_before = rx_stat_retired;
            admitted_before = tx_stat_admitted;
            case_checks_start = checks;
            case_fail_start = failures;
            rx_out_ready = 1'b0;
            dispatch_mode = r_mode[case_start];
            case (dispatch_mode)
                MODE_NORMAL: begin
                    run_normal_case(case_start, case_end);
                end
                MODE_IMMEDIATE_PAIR: begin
                    run_immediate_pair(case_start, case_end);
                end
                MODE_BIT_ERROR: begin
                    run_bit_error_case(case_start, case_end);
                end
                MODE_BAD_STOP: begin
                    run_bad_stop_case(case_start, case_end);
                end
                MODE_TX_CANCEL: begin
                    run_tx_cancel_case(case_start, case_end);
                end
                MODE_RX_CANCEL_HEADER: begin
                    run_rx_cancel_case(case_start, case_end, 1'b0);
                end
                MODE_RX_CANCEL_PAYLOAD: begin
                    run_rx_cancel_case(case_start, case_end, 1'b1);
                end
                MODE_RX_CANCEL_PENDING: begin
                    run_pending_cancel_case(case_start, case_end);
                end
                MODE_OVERRUN: begin
                    run_overrun_case(case_start, case_end);
                end
                MODE_RETIRED_THEN_ERROR: begin
                    run_retired_then_error_case(case_start, case_end);
                end
                default: begin
                    $fatal(1, "tb_uart_link_fixture: unknown case mode");
                end
            endcase
            finish_case(case_start, case_end, out_before, sent_before,
                        aborted_before, frames_before, retired_before,
                        admitted_before, case_checks_start, case_fail_start);
            rec = rec + 1;
        end

        check_int(cases_run, n_cases, "suite_case_count");
        check_int(obs_cfg_accepts, n_records, "suite_cfg_accept_count");
        check_int(obs_payload_accepts, total_payload, "suite_payload_accept_count");
        check_int(obs_out_handshakes, total_outputs, "suite_output_count");
        check_int(tx_stat_admitted, n_records, "suite_tx_admitted");
        check_int(tx_stat_sent, total_sent, "suite_tx_sent");
        check_int(tx_stat_aborted, total_aborted, "suite_tx_aborted");
        check_int(rx_stat_frames, total_frames, "suite_parser_frames");
        check_int(rx_stat_retired, total_outputs, "suite_parser_retired");

        if ((SUITE >= 0) && (SUITE <= 3)) begin
            check_int(rx_stat_uart_frames, total_wire, "suite_uart_frames");
            check_int(rx_stat_uart_retired, total_wire,
                      "suite_uart_retired");
            check_int(rx_stat_bytes, total_wire, "suite_parser_bytes");
            check_int(rx_stat_uart_overruns, 0, "suite_no_overrun");
            check_int(rx_stat_uart_framing, 0, "suite_no_framing");
            check_int(rx_stat_uart_false_starts, 0, "suite_no_false_start");
            check_int(rx_stat_uart_aborted, 0, "suite_no_uart_abort");
            check_int(rx_stat_version, 0, "suite_no_version_error");
            check_int(rx_stat_length, 0, "suite_no_length_error");
            check_int(rx_stat_crc, 0, "suite_no_crc_error");
            check_int(rx_stat_aborted, 0, "suite_no_parser_abort");
            check_int(obs_parser_errors, 0, "suite_no_parser_error_event");
            check_int(obs_line_errors, 0, "suite_no_line_error_event");
        end

        log_event($sformatf(
            "LINK_COUNTERS tx_admitted=%0d tx_sent=%0d tx_aborted=%0d uart_frames=%0d uart_retired=%0d uart_overruns=%0d uart_framing=%0d uart_false_starts=%0d uart_aborted=%0d parser_bytes=%0d parser_frames=%0d parser_retired=%0d parser_version=%0d parser_length=%0d parser_crc=%0d parser_aborted=%0d tx_edges=%0d rx_edges=%0d",
            tx_stat_admitted, tx_stat_sent, tx_stat_aborted,
            rx_stat_uart_frames, rx_stat_uart_retired,
            rx_stat_uart_overruns, rx_stat_uart_framing,
            rx_stat_uart_false_starts, rx_stat_uart_aborted,
            rx_stat_bytes, rx_stat_frames, rx_stat_retired,
            rx_stat_version, rx_stat_length, rx_stat_crc,
            rx_stat_aborted, tx_edges, rx_edges));

        $display("LINK_SUITE_TALLY suite=%0d cases=%0d checks=%0d failures=%0d",
                 SUITE, cases_run, checks - suite_checks_start,
                 failures - suite_fail_start);
        if (failures == suite_fail_start) begin
            log_event($sformatf("LINK_EVENT_LOG_END suite=%0d rows=%0d status=OK",
                                SUITE, event_rows));
            $fclose(event_fd);
            logging_active = 1'b0;
            $display("LINK_SUITE_STATUS suite=%0d result=PASS", SUITE);
            $finish;
        end else begin
            log_event($sformatf("LINK_EVENT_LOG_END suite=%0d rows=%0d status=FAIL",
                                SUITE, event_rows));
            $fclose(event_fd);
            logging_active = 1'b0;
            $display("LINK_SUITE_STATUS suite=%0d result=FAIL", SUITE);
            $fatal(1, "tb_uart_link_fixture: fixture checks failed");
        end
    end

endmodule

`default_nettype wire
