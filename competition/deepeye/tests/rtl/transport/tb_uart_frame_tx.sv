// Public-port directed tests for deepeye_uart_frame_tx.
//
// Work: B-UART-FRAME-TX-20261023-26-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-UART-FRAME-TX-20261023-26
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// The independent waveform oracle is derived from the public contract and the
// unchanged TX core's documented ceil(k*CLOCK_HZ/BAUD) boundary rule.  It does
// not look at hierarchy, force signals or feed the DUT output back as expected
// data.  No main-owned test, verifier or evidence file is used here.

`timescale 1ns/1ps

`ifndef G_CLOCK_HZ
`define G_CLOCK_HZ 100000000
`endif
`ifndef G_BAUD
`define G_BAUD 9600
`endif
`ifndef G_PRE_CYCLES
`define G_PRE_CYCLES 0
`endif
`ifndef G_POST_CYCLES
`define G_POST_CYCLES 0
`endif
`ifndef G_STAT_W
`define G_STAT_W 32
`endif

module tb_uart_frame_tx_harness #(
    parameter integer CLOCK_HZ = 31,
    parameter integer BAUD = 7,
    parameter integer PRE_CYCLES = 0,
    parameter integer POST_CYCLES = 0,
    parameter integer STAT_W = 16,
    parameter integer PROFILE = 0,
    parameter string NAME = "tb_uart_frame_tx_harness"
) ();

    localparam integer P_LENGTHS = 0;
    localparam integer P_ALL_BYTES = 1;
    localparam integer P_GUARDS = 2;
    localparam integer P_MAX_GUARDS = 3;
    localparam integer P_FAULTS = 4;
    localparam integer P_CANCEL_RESET = 5;
    localparam integer P_STAT2 = 6;
    localparam integer P_DEFAULT = 7;
    localparam integer P_BAUD300 = 8;
    localparam integer P_BAUD1200 = 9;

    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic cfg_valid = 1'b0;
    logic cfg_ready;
    logic [6:0] cfg_count = 7'd0;
    logic s_valid = 1'b0;
    logic s_ready;
    logic [7:0] s_data = 8'd0;
    logic s_last = 1'b0;
    logic tx;
    logic de;
    logic busy;
    logic receiving;
    logic faulted;
    logic fault_event;
    logic [1:0] fault_code;
    logic [STAT_W-1:0] stat_admitted;
    logic [STAT_W-1:0] stat_sent;
    logic [STAT_W-1:0] stat_aborted;
    logic [STAT_W-1:0] stat_faults;

    deepeye_uart_frame_tx #(
        .CLOCK_HZ(CLOCK_HZ),
        .BAUD(BAUD),
        .PRE_CYCLES(PRE_CYCLES),
        .POST_CYCLES(POST_CYCLES),
        .STAT_W(STAT_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .cfg_valid(cfg_valid),
        .cfg_ready(cfg_ready),
        .cfg_count(cfg_count),
        .s_valid(s_valid),
        .s_ready(s_ready),
        .s_data(s_data),
        .s_last(s_last),
        .tx(tx),
        .de(de),
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

    longint cycle = 0;
    always @(posedge clk) cycle <= cycle + 1;

    int checks = 0;
    int failures = 0;
    int cases = 0;
    int pass_cases = 0;
    int fail_cases = 0;
    int case_checks = 0;
    string current_case = "";
    bit case_failed = 1'b0;

    longint exp_admitted = 0;
    longint exp_sent = 0;
    longint exp_aborted = 0;
    longint exp_faults = 0;

    int frame_n = 0;
    logic [7:0] frame_bytes [0:63];
    longint adm [0:63];
    longint config_edge = 0;
    longint seal_edge = 0;
    longint retire_edge = 0;

    function automatic longint sat_ref(input longint value);
        longint maximum;
        begin
            maximum = (64'sd1 << STAT_W) - 64'sd1;
            if (value >= maximum) begin
                sat_ref = maximum;
            end else begin
                sat_ref = value + 64'sd1;
            end
        end
    endfunction

    function automatic longint bit_edge(input integer k);
        begin
            bit_edge = (longint'(k) * CLOCK_HZ + BAUD - 1) / BAUD;
        end
    endfunction

    function automatic logic tx_reference(input longint at_cycle);
        integer i;
        integer bit_number;
        longint elapsed;
        logic value;
        begin
            value = 1'b1;
            for (i = 0; i < frame_n; i = i + 1) begin
                if ((at_cycle >= adm[i]) &&
                    (at_cycle < (adm[i] + bit_edge(10)))) begin
                    elapsed = at_cycle - adm[i];
                    if (elapsed < bit_edge(1)) begin
                        value = 1'b0;
                    end else begin
                        value = 1'b1;
                        for (bit_number = 0; bit_number < 8; bit_number = bit_number + 1) begin
                            if ((elapsed >= bit_edge(bit_number + 1)) &&
                                (elapsed < bit_edge(bit_number + 2))) begin
                                value = frame_bytes[i][bit_number];
                            end
                        end
                    end
                end
            end
            tx_reference = value;
        end
    endfunction

    task automatic begin_case(input string name);
        begin
            if (current_case != "") begin
                $display("CHECK_FAIL name=nested_case previous=%s cycle=%0d", current_case, cycle);
                failures = failures + 1;
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

    task automatic check(input bit condition, input string label);
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if (condition !== 1'b1) begin
                failures = failures + 1;
                case_failed = 1'b1;
                $display("CHECK_FAIL name=%s cycle=%0d", label, cycle);
            end
        end
    endtask

    task automatic check_eq(input longint actual, input longint expected, input string label);
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if (actual !== expected) begin
                failures = failures + 1;
                case_failed = 1'b1;
                $display("CHECK_FAIL name=%s cycle=%0d actual=%0d expected=%0d",
                         label, cycle, actual, expected);
            end
        end
    endtask

    task automatic check_idle(input string label);
        begin
            check((tx === 1'b1), {label, "_tx_high"});
            check((de === 1'b0), {label, "_de_low"});
            check((busy === 1'b0), {label, "_busy_low"});
            check((receiving === 1'b0), {label, "_receiving_low"});
            check((faulted === 1'b0), {label, "_faulted_low"});
            check((fault_event === 1'b0), {label, "_event_low"});
            check((fault_code === 2'd0), {label, "_code_zero"});
            check((cfg_ready === 1'b1), {label, "_cfg_ready"});
            check((s_ready === 1'b0), {label, "_s_ready_low"});
            check_eq(stat_admitted, exp_admitted, {label, "_admitted"});
            check_eq(stat_sent, exp_sent, {label, "_sent"});
            check_eq(stat_aborted, exp_aborted, {label, "_aborted"});
            check_eq(stat_faults, exp_faults, {label, "_faults"});
        end
    endtask

    task automatic wait_idle_cycles(input integer count);
        integer index;
        begin
            for (index = 0; index < count; index = index + 1) begin
                @(posedge clk);
                #1;
                check_idle("idle_wait");
            end
        end
    endtask

    task automatic reset_dut();
        begin
            @(negedge clk);
            rst = 1'b1;
            cancel = 1'b0;
            cfg_valid = 1'b0;
            s_valid = 1'b0;
            cfg_count = 7'd0;
            s_data = 8'd0;
            s_last = 1'b0;
            @(posedge clk);
            #1;
            check((tx === 1'b1), "reset_tx_high");
            check((de === 1'b0), "reset_de_low");
            check((busy === 1'b0), "reset_busy_low");
            check((receiving === 1'b0), "reset_receiving_low");
            check((faulted === 1'b0), "reset_faulted_low");
            check((fault_event === 1'b0), "reset_event_low");
            check((fault_code === 2'd0), "reset_code_zero");
            check((stat_admitted === {STAT_W{1'b0}}), "reset_admitted_zero");
            check((stat_sent === {STAT_W{1'b0}}), "reset_sent_zero");
            check((stat_aborted === {STAT_W{1'b0}}), "reset_aborted_zero");
            check((stat_faults === {STAT_W{1'b0}}), "reset_faults_zero");
            @(posedge clk);
            #1;
            @(negedge clk);
            rst = 1'b0;
            #1;
            exp_admitted = 0;
            exp_sent = 0;
            exp_aborted = 0;
            exp_faults = 0;
            check_idle("reset_release");
        end
    endtask

    task automatic accept_config(input logic [6:0] count, input integer gap,
                                 output longint edge_out);
        begin
            repeat (gap) begin
                @(posedge clk);
                #1;
                check_idle("cfg_gap");
            end
            @(negedge clk);
            cfg_valid = 1'b1;
            cfg_count = count;
            #1;
            check((cfg_ready === 1'b1), "config_ready_before");
            check((s_ready === 1'b0), "config_no_sample_ready");
            @(posedge clk);
            #1;
            edge_out = cycle;
            exp_admitted = sat_ref(exp_admitted);
            check((cfg_ready === 1'b0), "config_ready_after");
            check((busy === 1'b1), "config_busy");
            check((receiving === 1'b1), "config_receiving");
            check((de === 1'b0), "config_de_low");
            check((tx === 1'b1), "config_tx_high");
            check((faulted === 1'b0), "config_faulted_low");
            check_eq(stat_admitted, exp_admitted, "config_admitted_count");
            @(negedge clk);
            cfg_valid = 1'b0;
            cfg_count = 7'd0;
        end
    endtask

    task automatic accept_sample_good(input logic [7:0] value, input bit last,
                                      input integer gap, output longint edge_out);
        begin
            repeat (gap) begin
                @(posedge clk);
                #1;
                check((busy === 1'b1), "sample_gap_busy");
                check((receiving === 1'b1), "sample_gap_receiving");
                check((de === 1'b0), "sample_gap_de_low");
                check((tx === 1'b1), "sample_gap_tx_high");
            end
            @(negedge clk);
            s_valid = 1'b1;
            s_data = value;
            s_last = last;
            #1;
            check((s_ready === 1'b1), "sample_ready_before");
            check((cfg_ready === 1'b0), "sample_no_config_ready");
            @(posedge clk);
            #1;
            edge_out = cycle;
            if (last) begin
                check((receiving === 1'b0), "last_sample_receiving_low");
            end else begin
                check((receiving === 1'b1), "sample_receiving_high");
            end
            check((busy === 1'b1), "sample_busy_high");
            check((de === 1'b0), "sample_no_same_edge_de");
            check((tx === 1'b1), "sample_tx_high");
            check((s_ready === (last ? 1'b0 : 1'b1)), "sample_ready_after");
            check_eq(stat_sent, exp_sent, "sample_sent_unchanged");
            check_eq(stat_aborted, exp_aborted, "sample_aborted_unchanged");
            check_eq(stat_faults, exp_faults, "sample_faults_unchanged");
            @(negedge clk);
            s_valid = 1'b0;
            s_data = 8'd0;
            s_last = 1'b0;
        end
    endtask

    task automatic compute_schedule(input integer count, input longint seal);
        integer index;
        begin
            frame_n = count;
            adm[0] = seal + PRE_CYCLES + 2;
            for (index = 1; index < count; index = index + 1) begin
                adm[index] = adm[index - 1] + bit_edge(10) + 2;
            end
            retire_edge = adm[count - 1] + bit_edge(10) + POST_CYCLES + 1;
        end
    endtask

    task automatic check_success_cycle(input longint at_cycle);
        longint expected_sent_now;
        begin
            expected_sent_now = (at_cycle >= retire_edge) ? sat_ref(exp_sent) : exp_sent;
            check((tx === tx_reference(at_cycle)), "frame_tx_reference");
            check((de === ((at_cycle >= (seal_edge + 1)) &&
                           (at_cycle < retire_edge))), "frame_de_window");
            check((busy === ((at_cycle >= config_edge) &&
                             (at_cycle < retire_edge))), "frame_busy_window");
            check((receiving === 1'b0), "frame_receiving_low");
            check((faulted === 1'b0), "frame_faulted_low");
            check((fault_event === 1'b0), "frame_event_low");
            check((fault_code === 2'd0), "frame_code_zero");
            check((cfg_ready === (at_cycle >= retire_edge)), "frame_cfg_ready");
            check((s_ready === 1'b0), "frame_s_ready_low");
            check_eq(stat_admitted, exp_admitted, "frame_admitted");
            check_eq(stat_sent, expected_sent_now, "frame_sent");
            check_eq(stat_aborted, exp_aborted, "frame_aborted");
            check_eq(stat_faults, exp_faults, "frame_faults");
        end
    endtask

    task automatic advance_and_check(input longint target);
        begin
            if (target >= cycle) begin
                while (cycle < target) begin
                    @(posedge clk);
                    #1;
                end
                check_success_cycle(target);
            end
        end
    endtask

    task automatic verify_success(input bit dense);
        integer index;
        integer boundary;
        longint at_cycle;
        begin
            check_eq(adm[0] - (seal_edge + 1), PRE_CYCLES + 1,
                     "de_to_first_admission");
            check_success_cycle(seal_edge);
            if (dense) begin
                at_cycle = seal_edge + 1;
                while (at_cycle <= (retire_edge + 1)) begin
                    @(posedge clk);
                    #1;
                    check_success_cycle(at_cycle);
                    at_cycle = at_cycle + 1;
                end
            end else begin
                advance_and_check(seal_edge + 1);
                for (index = 0; index < frame_n; index = index + 1) begin
                    advance_and_check(adm[index] - 1);
                    advance_and_check(adm[index]);
                    for (boundary = 1; boundary <= 10; boundary = boundary + 1) begin
                        advance_and_check(adm[index] + bit_edge(boundary) - 1);
                        advance_and_check(adm[index] + bit_edge(boundary));
                    end
                end
                advance_and_check(retire_edge - 1);
                advance_and_check(retire_edge);
                advance_and_check(retire_edge + 1);
            end
            exp_sent = sat_ref(exp_sent);
        end
    endtask

    task automatic run_good_frame(input integer count, input bit dense,
                                  input integer cfg_gap, input integer sample_gap);
        integer index;
        longint unused_edge;
        begin
            frame_n = count;
            accept_config(count[6:0], cfg_gap, config_edge);
            for (index = 0; index < count; index = index + 1) begin
                accept_sample_good(frame_bytes[index], (index == (count - 1)),
                                   sample_gap, unused_edge);
                if (index == (count - 1)) begin
                    seal_edge = unused_edge;
                end
            end
            compute_schedule(count, seal_edge);
            verify_success(dense);
            check_eq(stat_sent, exp_sent, "frame_sent_after_retire");
            wait_idle_cycles(2);
        end
    endtask

    task automatic advance_to_edge(input longint target);
        begin
            while (cycle < target) begin
                @(posedge clk);
                #1;
            end
        end
    endtask

    task automatic do_cancel(input bit expect_busy, input integer hold_edges);
        integer index;
        begin
            @(negedge clk);
            cancel = 1'b1;
            #1;
            check((busy === expect_busy), "cancel_synchronous_before");
            check_eq(stat_aborted, exp_aborted, "cancel_before_aborted");
            @(posedge clk);
            #1;
            if (expect_busy) begin
                exp_aborted = sat_ref(exp_aborted);
            end
            check((busy === 1'b0), "cancel_busy_low");
            check((receiving === 1'b0), "cancel_receiving_low");
            check((de === 1'b0), "cancel_de_low");
            check((faulted === 1'b0), "cancel_faulted_low");
            check((fault_event === 1'b0), "cancel_event_low");
            check((fault_code === 2'd0), "cancel_code_zero");
            check((tx === 1'b1), "cancel_tx_high");
            check_eq(stat_admitted, exp_admitted, "cancel_admitted_preserved");
            check_eq(stat_sent, exp_sent, "cancel_sent_preserved");
            check_eq(stat_aborted, exp_aborted, "cancel_aborted_count");
            check_eq(stat_faults, exp_faults, "cancel_faults_preserved");
            for (index = 0; index < hold_edges; index = index + 1) begin
                @(posedge clk);
                #1;
                check_eq(stat_aborted, exp_aborted, "cancel_held_no_recount");
                check((busy === 1'b0), "cancel_held_busy_low");
                check((de === 1'b0), "cancel_held_de_low");
                check((tx === 1'b1), "cancel_held_tx_high");
            end
            @(negedge clk);
            cancel = 1'b0;
            #1;
            check((cfg_ready === 1'b1), "cancel_release_cfg_ready");
            check((s_ready === 1'b0), "cancel_release_s_ready");
        end
    endtask

    task automatic do_reset_edge(input bit expect_busy);
        integer index;
        begin
            @(negedge clk);
            rst = 1'b1;
            #1;
            check((busy === expect_busy), "reset_synchronous_before");
            @(posedge clk);
            #1;
            exp_admitted = 0;
            exp_sent = 0;
            exp_aborted = 0;
            exp_faults = 0;
            check((tx === 1'b1), "reset_edge_tx_high");
            check((de === 1'b0), "reset_edge_de_low");
            check((busy === 1'b0), "reset_edge_busy_low");
            check((receiving === 1'b0), "reset_edge_receiving_low");
            check((faulted === 1'b0), "reset_edge_faulted_low");
            check((fault_event === 1'b0), "reset_edge_event_low");
            check((fault_code === 2'd0), "reset_edge_code_zero");
            check((stat_admitted === {STAT_W{1'b0}}), "reset_edge_admitted_zero");
            check((stat_sent === {STAT_W{1'b0}}), "reset_edge_sent_zero");
            check((stat_aborted === {STAT_W{1'b0}}), "reset_edge_aborted_zero");
            check((stat_faults === {STAT_W{1'b0}}), "reset_edge_faults_zero");
            for (index = 0; index < 2; index = index + 1) begin
                @(posedge clk);
                #1;
                check((busy === 1'b0), "reset_held_busy_low");
                check((de === 1'b0), "reset_held_de_low");
            end
            @(negedge clk);
            rst = 1'b0;
            #1;
            check_idle("reset_edge_release");
        end
    endtask

    task automatic prepare_sealed_frame(input integer count, input integer sample_gap,
                                        output longint cfg_edge, output longint sealed);
        integer index;
        longint sample_edge;
        begin
            frame_n = count;
            accept_config(count[6:0], 0, cfg_edge);
            sealed = cfg_edge;
            for (index = 0; index < count; index = index + 1) begin
                accept_sample_good(frame_bytes[index], (index == (count - 1)),
                                   sample_gap, sample_edge);
                if (index == (count - 1)) begin
                    sealed = sample_edge;
                end
            end
            compute_schedule(count, sealed);
        end
    endtask

    task automatic run_bad_config(input logic [6:0] count);
        integer index;
        longint edge_out;
        begin
            @(negedge clk);
            cfg_valid = 1'b1;
            cfg_count = count;
            #1;
            check((cfg_ready === 1'b1), "bad_cfg_ready_before");
            @(posedge clk);
            #1;
            edge_out = cycle;
            exp_admitted = sat_ref(exp_admitted);
            exp_faults = sat_ref(exp_faults);
            check((cfg_ready === 1'b0), "bad_cfg_ready_after");
            check((s_ready === 1'b0), "bad_cfg_no_sample_ready");
            check((busy === 1'b1), "bad_cfg_busy");
            check((receiving === 1'b0), "bad_cfg_not_receiving");
            check((faulted === 1'b1), "bad_cfg_faulted");
            check((fault_event === 1'b1), "bad_cfg_event_pulse");
            check((fault_code === 2'd1), "bad_cfg_code_one");
            check((tx === 1'b1), "bad_cfg_tx_high");
            check((de === 1'b0), "bad_cfg_de_low");
            check_eq(stat_admitted, exp_admitted, "bad_cfg_admitted");
            check_eq(stat_sent, exp_sent, "bad_cfg_sent_unchanged");
            check_eq(stat_aborted, exp_aborted, "bad_cfg_aborted_unchanged");
            check_eq(stat_faults, exp_faults, "bad_cfg_faults");
            @(posedge clk);
            #1;
            check((fault_event === 1'b0), "bad_cfg_event_one_cycle");
            check((faulted === 1'b1), "bad_cfg_fault_sticky");
            check((fault_code === 2'd1), "bad_cfg_code_sticky");
            @(negedge clk);
            s_valid = 1'b1;
            s_data = 8'h5a;
            s_last = 1'b1;
            for (index = 0; index < 8; index = index + 1) begin
                @(posedge clk);
                #1;
                check((s_ready === 1'b0), "bad_cfg_sample_blocked");
                check((cfg_ready === 1'b0), "bad_cfg_config_blocked");
                check((busy === 1'b1), "bad_cfg_reservation_held");
                check((tx === 1'b1), "bad_cfg_no_tx");
                check((de === 1'b0), "bad_cfg_no_de");
            end
            @(negedge clk);
            s_valid = 1'b0;
            s_last = 1'b0;
            cfg_valid = 1'b0;
            do_cancel(1'b1, 3);
        end
    endtask

    task automatic run_protocol_fault(input integer count, input integer good_samples,
                                       input bit fault_early);
        integer index;
        longint edge_out;
        integer hold_index;
        logic [7:0] fault_data;
        logic fault_last;
        begin
            frame_n = count;
            accept_config(count[6:0], 0, edge_out);
            for (index = 0; index < good_samples; index = index + 1) begin
                accept_sample_good(frame_bytes[index], 1'b0, 0, edge_out);
            end
            fault_data = frame_bytes[good_samples];
            fault_last = fault_early ? 1'b1 : 1'b0;
            @(negedge clk);
            s_valid = 1'b1;
            s_data = fault_data;
            s_last = fault_last;
            #1;
            check((s_ready === 1'b1), "protocol_fault_ready_before");
            @(posedge clk);
            #1;
            exp_faults = sat_ref(exp_faults);
            check((busy === 1'b1), "protocol_fault_busy");
            check((receiving === 1'b0), "protocol_fault_not_receiving");
            check((faulted === 1'b1), "protocol_fault_sticky_set");
            check((fault_event === 1'b1), "protocol_fault_event_pulse");
            check((fault_code === 2'd2), "protocol_fault_code_two");
            check((s_ready === 1'b0), "protocol_fault_s_ready_low");
            check((cfg_ready === 1'b0), "protocol_fault_cfg_ready_low");
            check((de === 1'b0), "protocol_fault_no_de");
            check((tx === 1'b1), "protocol_fault_no_tx");
            check_eq(stat_sent, exp_sent, "protocol_fault_sent_unchanged");
            check_eq(stat_aborted, exp_aborted, "protocol_fault_aborted_unchanged");
            check_eq(stat_faults, exp_faults, "protocol_fault_count");
            @(negedge clk);
            s_valid = 1'b0;
            s_last = 1'b0;
            for (hold_index = 0; hold_index < 18; hold_index = hold_index + 1) begin
                @(posedge clk);
                #1;
                check((faulted === 1'b1), "protocol_fault_sticky_hold");
                check((fault_event === 1'b0), "protocol_fault_event_only_once");
                check((fault_code === 2'd2), "protocol_fault_code_hold");
                check((busy === 1'b1), "protocol_fault_reservation_hold");
                check((tx === 1'b1), "protocol_fault_tx_never_started");
                check((de === 1'b0), "protocol_fault_de_never_started");
            end
            @(negedge clk);
            cfg_valid = 1'b1;
            cfg_count = 7'd2;
            s_valid = 1'b1;
            s_data = 8'hc3;
            s_last = 1'b1;
            for (hold_index = 0; hold_index < 4; hold_index = hold_index + 1) begin
                @(posedge clk);
                #1;
                check((cfg_ready === 1'b0), "protocol_fault_cfg_blocked");
                check((s_ready === 1'b0), "protocol_fault_sample_blocked");
                check_eq(stat_admitted, exp_admitted, "protocol_fault_no_new_config");
                check_eq(stat_sent, exp_sent, "protocol_fault_no_new_send");
            end
            @(negedge clk);
            cfg_valid = 1'b0;
            s_valid = 1'b0;
            s_last = 1'b0;
            do_cancel(1'b1, 3);
        end
    endtask

    task automatic finish_tb();
        bit final_ok;
        begin
            final_ok = (current_case == "") &&
                       (longint'(stat_admitted) == exp_admitted) &&
                       (longint'(stat_sent) == exp_sent) &&
                       (longint'(stat_aborted) == exp_aborted) &&
                       (longint'(stat_faults) == exp_faults);
            checks = checks + 1;
            if (!final_ok) begin
                failures = failures + 1;
                $display("CHECK_FAIL name=final_stats_or_case cycle=%0d admitted=%0d/%0d sent=%0d/%0d aborted=%0d/%0d faults=%0d/%0d",
                         cycle, stat_admitted, exp_admitted, stat_sent, exp_sent,
                         stat_aborted, exp_aborted, stat_faults, exp_faults);
            end
            $display("TB_SUMMARY cases=%0d pass=%0d fail=%0d checks=%0d",
                     cases, pass_cases, fail_cases, checks);
            $display("TB_STAT admitted=%0d sent=%0d aborted=%0d faults=%0d",
                     stat_admitted, stat_sent, stat_aborted, stat_faults);
            if ((failures == 0) && (fail_cases == 0)) begin
                $display("TB_END pass");
            end else begin
                $display("TB_END fail");
            end
            $finish;
        end
    endtask

    initial begin : main_sequence
        integer length_index;
        integer byte_index;
        integer offset;
        integer fault_index;
        longint edge_out;
        longint sealed;
        longint cfg_edge;
        longint first_done;
        bit seen [0:255];

        $display("TB_BEGIN tb=%s", NAME);
        for (byte_index = 0; byte_index < 256; byte_index = byte_index + 1) begin
            seen[byte_index] = 1'b0;
        end

        if (PROFILE == P_LENGTHS) begin
            begin_case("reset_idle");
            reset_dut();
            wait_idle_cycles(20);
            end_case();

            begin_case("all_lengths_1_64");
            for (length_index = 1; length_index <= 64; length_index = length_index + 1) begin
                for (byte_index = 0; byte_index < length_index; byte_index = byte_index + 1) begin
                    frame_bytes[byte_index] = ((length_index * 37) + (byte_index * 11) + 5) & 255;
                end
                run_good_frame(length_index, 1'b1, (length_index % 3), (length_index % 2));
            end
            check_eq(stat_admitted, 64, "lengths_admitted_total");
            check_eq(stat_sent, 64, "lengths_sent_total");
            check_eq(stat_aborted, 0, "lengths_aborted_total");
            check_eq(stat_faults, 0, "lengths_faults_total");
            end_case();

            begin_case("source_silence");
            wait_idle_cycles(1200);
            frame_bytes[0] = 8'h3c;
            run_good_frame(1, 1'b1, 17, 700);
            wait_idle_cycles(1200);
            check_eq(stat_admitted, 65, "silence_admitted_total");
            check_eq(stat_sent, 65, "silence_sent_total");
            end_case();
        end else if (PROFILE == P_ALL_BYTES) begin
            begin_case("reset_idle");
            reset_dut();
            wait_idle_cycles(10);
            end_case();

            begin_case("all_byte_values");
            for (offset = 0; offset < 256; offset = offset + 64) begin
                for (byte_index = 0; byte_index < 64; byte_index = byte_index + 1) begin
                    frame_bytes[byte_index] = offset + byte_index;
                    seen[offset + byte_index] = 1'b1;
                end
                run_good_frame(64, 1'b1, 0, (offset / 64));
            end
            for (byte_index = 0; byte_index < 256; byte_index = byte_index + 1) begin
                check(seen[byte_index], "all_byte_value_covered");
            end
            check_eq(stat_admitted, 4, "all_bytes_admitted_total");
            check_eq(stat_sent, 4, "all_bytes_sent_total");
            end_case();
        end else if (PROFILE == P_GUARDS) begin
            begin_case("reset_idle");
            reset_dut();
            wait_idle_cycles(10);
            end_case();

            begin_case("unequal_guards");
            for (byte_index = 0; byte_index < 4; byte_index = byte_index + 1) begin
                frame_bytes[byte_index] = 8'h80 + byte_index;
            end
            run_good_frame(4, 1'b1, 0, 2);
            end_case();

            begin_case("raw_gaps");
            for (byte_index = 0; byte_index < 2; byte_index = byte_index + 1) begin
                frame_bytes[byte_index] = 8'h5a - byte_index;
            end
            run_good_frame(2, 1'b0, 29, 7);
            end_case();

            begin_case("no_same_edge_cfg_sample");
            @(negedge clk);
            cfg_valid = 1'b1;
            cfg_count = 7'd1;
            s_valid = 1'b1;
            s_data = 8'ha5;
            s_last = 1'b1;
            #1;
            check((cfg_ready === 1'b1), "dual_offer_cfg_ready");
            check((s_ready === 1'b0), "dual_offer_sample_not_ready");
            @(posedge clk);
            #1;
            cfg_edge = cycle;
            config_edge = cfg_edge;
            exp_admitted = sat_ref(exp_admitted);
            check((cfg_ready === 1'b0), "dual_offer_cfg_not_same_edge_sample");
            check((s_ready === 1'b1), "dual_offer_sample_ready_next");
            check((receiving === 1'b1), "dual_offer_receiving");
            check((de === 1'b0), "dual_offer_de_low");
            @(posedge clk);
            #1;
            seal_edge = cycle;
            check((receiving === 1'b0), "dual_offer_seal_receiving_low");
            check((de === 1'b0), "dual_offer_seal_no_same_edge_de");
            @(negedge clk);
            cfg_valid = 1'b0;
            s_valid = 1'b0;
            s_last = 1'b0;
            frame_n = 1;
            frame_bytes[0] = 8'ha5;
            compute_schedule(1, seal_edge);
            verify_success(1'b1);
            end_case();

            begin_case("completion_no_credit");
            frame_bytes[0] = 8'h6a;
            frame_bytes[1] = 8'h95;
            accept_config(7'd1, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b1, 0, sealed);
            compute_schedule(1, sealed);
            advance_to_edge(retire_edge - 1);
            check((de === 1'b1), "credit_cfg_de_high_before");
            check((busy === 1'b1), "credit_cfg_busy_before");
            check((cfg_ready === 1'b0), "credit_cfg_not_ready_before");
            @(negedge clk);
            cfg_valid = 1'b1;
            cfg_count = 7'd1;
            #1;
            check((cfg_ready === 1'b0), "credit_cfg_offer_blocked_at_retire");
            @(posedge clk);
            #1;
            check((busy === 1'b0), "credit_cfg_retire_busy_low");
            check((de === 1'b0), "credit_cfg_retire_de_low");
            check((cfg_ready === 1'b1), "credit_cfg_ready_after_retire");
            check_eq(stat_admitted, exp_admitted, "credit_cfg_no_same_edge_admit");
            exp_sent = sat_ref(exp_sent);
            check_eq(stat_sent, exp_sent, "credit_cfg_first_sent");
            @(posedge clk);
            #1;
            cfg_edge = cycle;
            config_edge = cfg_edge;
            exp_admitted = sat_ref(exp_admitted);
            check((busy === 1'b1), "credit_cfg_next_edge_busy");
            check((receiving === 1'b1), "credit_cfg_next_edge_receiving");
            check((cfg_ready === 1'b0), "credit_cfg_next_edge_ready_low");
            check_eq(stat_admitted, exp_admitted, "credit_cfg_next_edge_admitted");
            @(negedge clk);
            cfg_valid = 1'b0;
            cfg_count = 7'd0;
            accept_sample_good(frame_bytes[1], 1'b1, 0, sealed);
            frame_n = 1;
            frame_bytes[0] = 8'h95;
            seal_edge = sealed;
            compute_schedule(1, sealed);
            verify_success(1'b1);
            wait_idle_cycles(2);
            end_case();
        end else if (PROFILE == P_MAX_GUARDS) begin
            begin_case("reset_idle");
            reset_dut();
            wait_idle_cycles(10);
            end_case();

            begin_case("max_guards");
            frame_bytes[0] = 8'h96;
            run_good_frame(1, 1'b0, 0, 0);
            check_eq(adm[0] - (seal_edge + 1), 65536, "max_pre_edge_delta");
            check_eq(retire_edge - (adm[0] + bit_edge(10)), 65536, "max_post_edge_delta");
            end_case();
        end else if (PROFILE == P_FAULTS) begin
            begin_case("reset_idle");
            reset_dut();
            wait_idle_cycles(10);
            end_case();

            begin_case("invalid_counts");
            run_bad_config(7'd0);
            run_bad_config(7'd65);
            run_bad_config(7'd127);
            end_case();

            begin_case("missing_final_last");
            for (byte_index = 0; byte_index < 3; byte_index = byte_index + 1) begin
                frame_bytes[byte_index] = 8'h10 + byte_index;
            end
            run_protocol_fault(3, 2, 1'b0);
            end_case();

            begin_case("early_last");
            for (byte_index = 0; byte_index < 4; byte_index = byte_index + 1) begin
                frame_bytes[byte_index] = 8'h20 + byte_index;
            end
            run_protocol_fault(4, 2, 1'b1);
            end_case();

            begin_case("sticky_recovery");
            frame_bytes[0] = 8'hde;
            frame_bytes[1] = 8'had;
            run_good_frame(2, 1'b1, 3, 1);
            end_case();

            begin_case("repeat_fault_event");
            run_bad_config(7'd0);
            end_case();
        end else if (PROFILE == P_CANCEL_RESET) begin
            begin_case("reset_idle");
            reset_dut();
            wait_idle_cycles(10);
            end_case();

            begin_case("cancel_receive");
            reset_dut();
            for (byte_index = 0; byte_index < 4; byte_index = byte_index + 1) begin
                frame_bytes[byte_index] = 8'h30 + byte_index;
            end
            accept_config(7'd4, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b0, 0, edge_out);
            accept_sample_good(frame_bytes[1], 1'b0, 2, edge_out);
            advance_to_edge(edge_out + 2);
            do_cancel(1'b1, 3);
            end_case();

            begin_case("cancel_seal_pre");
            reset_dut();
            frame_bytes[0] = 8'h41;
            accept_config(7'd1, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b1, 0, sealed);
            compute_schedule(1, sealed);
            advance_to_edge(sealed);
            do_cancel(1'b1, 2);
            check((de === 1'b0), "seal_cancel_never_de");

            reset_dut();
            accept_config(7'd1, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b1, 0, sealed);
            compute_schedule(1, sealed);
            advance_to_edge(sealed + 1);
            check((de === 1'b1), "pre_cancel_de_high");
            do_cancel(1'b1, 2);
            end_case();

            begin_case("cancel_byte_between");
            reset_dut();
            accept_config(7'd1, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b1, 0, sealed);
            compute_schedule(1, sealed);
            advance_to_edge(adm[0] + bit_edge(2) - 1);
            check((de === 1'b1), "byte_cancel_de_high");
            do_cancel(1'b1, 2);

            reset_dut();
            frame_bytes[0] = 8'h52;
            frame_bytes[1] = 8'h53;
            prepare_sealed_frame(2, 0, cfg_edge, sealed);
            first_done = adm[0] + bit_edge(10);
            advance_to_edge(first_done);
            check((busy === 1'b1), "between_cancel_guard_busy");
            do_cancel(1'b1, 2);
            end_case();

            begin_case("cancel_final_post");
            reset_dut();
            frame_bytes[0] = 8'h64;
            accept_config(7'd1, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b1, 0, sealed);
            compute_schedule(1, sealed);
            advance_to_edge(retire_edge - 2);
            check((de === 1'b1), "post_cancel_de_high");
            check((busy === 1'b1), "post_cancel_busy_high");
            do_cancel(1'b1, 2);
            end_case();

            begin_case("reset_stages");
            reset_dut();
            frame_bytes[0] = 8'h70;
            frame_bytes[1] = 8'h71;
            accept_config(7'd3, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b0, 0, edge_out);
            do_reset_edge(1'b1);

            accept_config(7'd1, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b1, 0, sealed);
            compute_schedule(1, sealed);
            advance_to_edge(sealed);
            check((de === 1'b0), "reset_seal_de_still_low");
            do_reset_edge(1'b1);

            accept_config(7'd1, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b1, 0, sealed);
            compute_schedule(1, sealed);
            advance_to_edge(sealed + 1);
            check((de === 1'b1), "reset_pre_de_high");
            do_reset_edge(1'b1);

            accept_config(7'd1, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b1, 0, sealed);
            compute_schedule(1, sealed);
            advance_to_edge(adm[0] + bit_edge(2));
            do_reset_edge(1'b1);

            accept_config(7'd1, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b1, 0, sealed);
            compute_schedule(1, sealed);
            advance_to_edge(retire_edge - 2);
            check((de === 1'b1), "reset_post_de_high");
            do_reset_edge(1'b1);

            accept_config(7'd1, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b1, 0, sealed);
            compute_schedule(1, sealed);
            advance_to_edge(retire_edge - 1);
            do_reset_edge(1'b1);
            end_case();

            begin_case("held_cancel_reset_priority");
            reset_dut();
            do_cancel(1'b0, 3);
            check_idle("idle_cancel_done");
            accept_config(7'd1, 0, cfg_edge);
            @(negedge clk);
            rst = 1'b1;
            cancel = 1'b1;
            #1;
            check((busy === 1'b1), "reset_over_cancel_before");
            @(posedge clk);
            #1;
            exp_admitted = 0;
            exp_sent = 0;
            exp_aborted = 0;
            exp_faults = 0;
            check((busy === 1'b0), "reset_over_cancel_busy");
            check((de === 1'b0), "reset_over_cancel_de");
            check((stat_admitted === {STAT_W{1'b0}}), "reset_over_cancel_admitted");
            check((stat_aborted === {STAT_W{1'b0}}), "reset_over_cancel_aborted");
            @(negedge clk);
            rst = 1'b0;
            cancel = 1'b0;
            #1;
            check_idle("reset_over_cancel_release");
            end_case();

            begin_case("cancel_retire_edge");
            reset_dut();
            frame_bytes[0] = 8'h88;
            accept_config(7'd1, 0, cfg_edge);
            accept_sample_good(frame_bytes[0], 1'b1, 0, sealed);
            compute_schedule(1, sealed);
            advance_to_edge(retire_edge - 1);
            check((de === 1'b1), "retire_cancel_de_before");
            do_cancel(1'b1, 2);
            end_case();
        end else if (PROFILE == P_STAT2) begin
            begin_case("reset_idle");
            reset_dut();
            wait_idle_cycles(10);
            end_case();

            begin_case("stat_saturation");
            for (fault_index = 0; fault_index < 5; fault_index = fault_index + 1) begin
                run_bad_config(7'd0);
            end
            for (byte_index = 0; byte_index < 5; byte_index = byte_index + 1) begin
                frame_bytes[0] = 8'h90 + byte_index;
                run_good_frame(1, 1'b1, 0, 1);
            end
            check_eq(stat_admitted, 3, "stat2_admitted_saturated");
            check_eq(stat_sent, 3, "stat2_sent_saturated");
            check_eq(stat_aborted, 3, "stat2_aborted_saturated");
            check_eq(stat_faults, 3, "stat2_faults_saturated");
            end_case();
        end else if (PROFILE == P_DEFAULT) begin
            begin_case("reset_idle");
            reset_dut();
            wait_idle_cycles(10);
            end_case();

            begin_case("default_9600_example");
            frame_bytes[0] = 8'h55;
            frame_bytes[1] = 8'haa;
            run_good_frame(2, 1'b0, 0, 0);
            end_case();
        end else if (PROFILE == P_BAUD300) begin
            begin_case("reset_idle");
            reset_dut();
            wait_idle_cycles(10);
            end_case();

            begin_case("baud300_example");
            frame_bytes[0] = 8'h96;
            run_good_frame(1, 1'b0, 0, 0);
            end_case();
        end else if (PROFILE == P_BAUD1200) begin
            begin_case("reset_idle");
            reset_dut();
            wait_idle_cycles(10);
            end_case();

            begin_case("baud1200_example");
            frame_bytes[0] = 8'h3c;
            frame_bytes[1] = 8'hc3;
            run_good_frame(2, 1'b0, 0, 1);
            end_case();
        end else begin
            begin_case("unknown_profile");
            check(1'b0, "unknown_profile_selected");
            end_case();
        end

        finish_tb();
    end

endmodule

module tb_uart_frame_tx_lengths;
    tb_uart_frame_tx_harness #(
        .CLOCK_HZ(31), .BAUD(7), .PRE_CYCLES(0), .POST_CYCLES(0),
        .STAT_W(16), .PROFILE(0), .NAME("tb_uart_frame_tx_lengths")
    ) harness ();
endmodule

module tb_uart_frame_tx_all_bytes;
    tb_uart_frame_tx_harness #(
        .CLOCK_HZ(17), .BAUD(3), .PRE_CYCLES(0), .POST_CYCLES(0),
        .STAT_W(16), .PROFILE(1), .NAME("tb_uart_frame_tx_all_bytes")
    ) harness ();
endmodule

module tb_uart_frame_tx_guards;
    tb_uart_frame_tx_harness #(
        .CLOCK_HZ(97), .BAUD(11), .PRE_CYCLES(1), .POST_CYCLES(5),
        .STAT_W(12), .PROFILE(2), .NAME("tb_uart_frame_tx_guards")
    ) harness ();
endmodule

module tb_uart_frame_tx_max_guards;
    tb_uart_frame_tx_harness #(
        .CLOCK_HZ(9), .BAUD(4), .PRE_CYCLES(65535), .POST_CYCLES(65535),
        .STAT_W(8), .PROFILE(3), .NAME("tb_uart_frame_tx_max_guards")
    ) harness ();
endmodule

module tb_uart_frame_tx_faults;
    tb_uart_frame_tx_harness #(
        .CLOCK_HZ(23), .BAUD(5), .PRE_CYCLES(1), .POST_CYCLES(2),
        .STAT_W(8), .PROFILE(4), .NAME("tb_uart_frame_tx_faults")
    ) harness ();
endmodule

module tb_uart_frame_tx_cancel_reset;
    tb_uart_frame_tx_harness #(
        .CLOCK_HZ(31), .BAUD(7), .PRE_CYCLES(2), .POST_CYCLES(3),
        .STAT_W(8), .PROFILE(5), .NAME("tb_uart_frame_tx_cancel_reset")
    ) harness ();
endmodule

module tb_uart_frame_tx_stat_w2;
    tb_uart_frame_tx_harness #(
        .CLOCK_HZ(13), .BAUD(3), .PRE_CYCLES(0), .POST_CYCLES(1),
        .STAT_W(2), .PROFILE(6), .NAME("tb_uart_frame_tx_stat_w2")
    ) harness ();
endmodule

module tb_uart_frame_tx_default_9600;
    tb_uart_frame_tx_harness #(
        .CLOCK_HZ(100000000), .BAUD(9600), .PRE_CYCLES(0), .POST_CYCLES(0),
        .STAT_W(16), .PROFILE(7), .NAME("tb_uart_frame_tx_default_9600")
    ) harness ();
endmodule

module tb_uart_frame_tx_baud300;
    tb_uart_frame_tx_harness #(
        .CLOCK_HZ(100000000), .BAUD(300), .PRE_CYCLES(0), .POST_CYCLES(1),
        .STAT_W(16), .PROFILE(8), .NAME("tb_uart_frame_tx_baud300")
    ) harness ();
endmodule

module tb_uart_frame_tx_baud1200;
    tb_uart_frame_tx_harness #(
        .CLOCK_HZ(100000000), .BAUD(1200), .PRE_CYCLES(1), .POST_CYCLES(0),
        .STAT_W(16), .PROFILE(9), .NAME("tb_uart_frame_tx_baud1200")
    ) harness ();
endmodule

module tb_uart_frame_tx_guard_top;
    logic clk = 1'b0;
    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic cfg_valid = 1'b0;
    logic cfg_ready;
    logic s_valid = 1'b0;
    logic s_ready;
    logic [7:0] s_data = 8'd0;
    logic s_last = 1'b0;
    logic tx;
    logic de;
    logic busy;
    logic receiving;
    logic faulted;
    logic fault_event;
    logic [1:0] fault_code;
    localparam integer GUARD_STAT_W = (`G_STAT_W < 2) ? 2 :
                                       ((`G_STAT_W > 32) ? 32 : `G_STAT_W);
    logic [GUARD_STAT_W-1:0] stat_admitted;
    logic [GUARD_STAT_W-1:0] stat_sent;
    logic [GUARD_STAT_W-1:0] stat_aborted;
    logic [GUARD_STAT_W-1:0] stat_faults;

    always #5 clk = ~clk;

    deepeye_uart_frame_tx #(
        .CLOCK_HZ(`G_CLOCK_HZ),
        .BAUD(`G_BAUD),
        .PRE_CYCLES(`G_PRE_CYCLES),
        .POST_CYCLES(`G_POST_CYCLES),
        .STAT_W(`G_STAT_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .cfg_valid(cfg_valid),
        .cfg_ready(cfg_ready),
        .cfg_count(7'd0),
        .s_valid(s_valid),
        .s_ready(s_ready),
        .s_data(s_data),
        .s_last(s_last),
        .tx(tx),
        .de(de),
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
        #2;
        $display("GUARD_UNEXPECTED_NO_FATAL");
        $finish;
    end
endmodule
