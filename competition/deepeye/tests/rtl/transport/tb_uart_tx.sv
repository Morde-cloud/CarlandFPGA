// Public-port testbenches for deepeye_uart_tx.
//
// Work: B-UART-TX-20261023-24-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-UART-TX-20261023-24
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// Every check observes only the DUT's declared ports.  The expected tx level
// comes from absolute elapsed rising edges and ceil(k*CLOCK_HZ/BAUD), not from
// the DUT phase state.  Ordinary rows are intentionally unique and anchored so
// the strict runner can reject missing, duplicate or malformed evidence.

`timescale 1ns/1ps

module tb_uart_tx_harness #(
    parameter integer CLOCK_HZ = 97,
    parameter integer BAUD = 11,
    parameter integer STAT_W = 32,
    parameter integer PROFILE = 0,
    parameter string NAME = "tb_uart_tx_harness"
) ();

    localparam integer P_ALL_BYTES = 0;
    localparam integer P_CANCEL_RESET = 1;
    localparam integer P_SUSTAINED = 2;
    localparam integer P_DEFAULT = 3;
    localparam integer P_BAUD_300 = 4;
    localparam integer P_BAUD_1200 = 5;
    localparam integer P_STAT_W2 = 6;

    localparam integer B1  = (CLOCK_HZ + BAUD - 1) / BAUD;
    localparam integer B2  = (2 * CLOCK_HZ + BAUD - 1) / BAUD;
    localparam integer B3  = (3 * CLOCK_HZ + BAUD - 1) / BAUD;
    localparam integer B4  = (4 * CLOCK_HZ + BAUD - 1) / BAUD;
    localparam integer B5  = (5 * CLOCK_HZ + BAUD - 1) / BAUD;
    localparam integer B6  = (6 * CLOCK_HZ + BAUD - 1) / BAUD;
    localparam integer B7  = (7 * CLOCK_HZ + BAUD - 1) / BAUD;
    localparam integer B8  = (8 * CLOCK_HZ + BAUD - 1) / BAUD;
    localparam integer B9  = (9 * CLOCK_HZ + BAUD - 1) / BAUD;
    localparam integer B10 = (10 * CLOCK_HZ + BAUD - 1) / BAUD;

    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic in_valid = 1'b0;
    logic in_ready;
    logic [7:0] in_data = 8'd0;
    logic tx;
    logic busy;
    logic [STAT_W-1:0] stat_accepted;
    logic [STAT_W-1:0] stat_completed;
    logic [STAT_W-1:0] stat_aborted;

    deepeye_uart_tx #(
        .CLOCK_HZ(CLOCK_HZ),
        .BAUD(BAUD),
        .STAT_W(STAT_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_data(in_data),
        .tx(tx),
        .busy(busy),
        .stat_accepted(stat_accepted),
        .stat_completed(stat_completed),
        .stat_aborted(stat_aborted)
    );

    int checks = 0;
    int failures = 0;
    int cases = 0;
    int pass_cases = 0;
    int fail_cases = 0;
    int case_checks = 0;
    string current_case = "";
    bit case_failed = 1'b0;

    longint expected_accepted = 0;
    longint expected_completed = 0;
    longint expected_aborted = 0;
    logic [7:0] waveform_byte = 8'd0;

    function automatic longint golden_inc(input longint value);
        longint maximum;
        begin
            maximum = (64'd1 << STAT_W) - 64'd1;
            if (value >= maximum) begin
                golden_inc = maximum;
            end else begin
                golden_inc = value + 64'd1;
            end
        end
    endfunction

    function automatic logic tx_for_elapsed(input integer elapsed);
        begin
            if (elapsed >= B9) begin
                tx_for_elapsed = 1'b1;
            end else if (elapsed >= B8) begin
                tx_for_elapsed = waveform_byte[7];
            end else if (elapsed >= B7) begin
                tx_for_elapsed = waveform_byte[6];
            end else if (elapsed >= B6) begin
                tx_for_elapsed = waveform_byte[5];
            end else if (elapsed >= B5) begin
                tx_for_elapsed = waveform_byte[4];
            end else if (elapsed >= B4) begin
                tx_for_elapsed = waveform_byte[3];
            end else if (elapsed >= B3) begin
                tx_for_elapsed = waveform_byte[2];
            end else if (elapsed >= B2) begin
                tx_for_elapsed = waveform_byte[1];
            end else if (elapsed >= B1) begin
                tx_for_elapsed = waveform_byte[0];
            end else begin
                tx_for_elapsed = 1'b0;
            end
        end
    endfunction

    function automatic integer boundary_for_k(input integer k);
        begin
            case (k)
                1: boundary_for_k = B1;
                2: boundary_for_k = B2;
                3: boundary_for_k = B3;
                4: boundary_for_k = B4;
                5: boundary_for_k = B5;
                6: boundary_for_k = B6;
                7: boundary_for_k = B7;
                8: boundary_for_k = B8;
                9: boundary_for_k = B9;
                10: boundary_for_k = B10;
                default: boundary_for_k = -1;
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
                $display("CHECK_FAIL name=%s", label);
            end
        end
    endtask

    task automatic begin_case(input string name);
        begin
            if (current_case != "") begin
                $display("CHECK_FAIL name=nested_case previous=%s", current_case);
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

    task automatic observe_cycle(input integer elapsed, input bit expect_busy);
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if ((tx !== tx_for_elapsed(elapsed)) ||
                (busy !== expect_busy) ||
                (in_ready !== (expect_busy ? 1'b0 : 1'b1)) ||
                (stat_accepted !== expected_accepted[STAT_W-1:0]) ||
                (stat_completed !== expected_completed[STAT_W-1:0]) ||
                (stat_aborted !== expected_aborted[STAT_W-1:0])) begin
                failures = failures + 1;
                case_failed = 1'b1;
                $display("CHECK_FAIL name=edge_observation elapsed=%0d tx=%0b expected_tx=%0b busy=%0b expected_busy=%0b ready=%0b accepted=%0d/%0d completed=%0d/%0d aborted=%0d/%0d",
                         elapsed, tx, tx_for_elapsed(elapsed), busy, expect_busy,
                         in_ready, stat_accepted, expected_accepted,
                         stat_completed, expected_completed,
                         stat_aborted, expected_aborted);
            end
        end
    endtask

    task automatic reset_dut();
        integer index;
        begin
            @(negedge clk);
            rst = 1'b1;
            cancel = 1'b0;
            in_valid = 1'b0;
            in_data = 8'd0;
            expected_accepted = 0;
            expected_completed = 0;
            expected_aborted = 0;
            for (index = 0; index < 3; index = index + 1) begin
                @(posedge clk);
                #1;
                simple_check((tx === 1'b1), "reset_tx_high");
                simple_check((busy === 1'b0), "reset_busy_low");
                simple_check((in_ready === 1'b0), "reset_ready_low");
                simple_check((stat_accepted === {STAT_W{1'b0}}), "reset_accepted_zero");
                simple_check((stat_completed === {STAT_W{1'b0}}), "reset_completed_zero");
                simple_check((stat_aborted === {STAT_W{1'b0}}), "reset_aborted_zero");
            end
            @(negedge clk);
            rst = 1'b0;
            #1;
            simple_check((tx === 1'b1), "reset_release_tx_high");
            simple_check((busy === 1'b0), "reset_release_busy_low");
            simple_check((in_ready === 1'b1), "reset_release_ready_high");
        end
    endtask

    task automatic admit_only(input logic [7:0] value);
        begin
            @(negedge clk);
            in_valid = 1'b1;
            in_data = value;
            waveform_byte = value;
            #1;
            simple_check((in_ready === 1'b1), "admission_ready_high");
            @(posedge clk);
            #1;
            expected_accepted = golden_inc(expected_accepted);
            observe_cycle(0, 1'b1);
            @(negedge clk);
            in_valid = 1'b0;
            in_data = 8'd0;
            #1;
            simple_check((in_ready === 1'b0), "admission_ready_low");
        end
    endtask

    task automatic send_byte(input logic [7:0] value);
        integer elapsed;
        begin
            @(negedge clk);
            in_valid = 1'b1;
            in_data = value;
            waveform_byte = value;
            #1;
            simple_check((in_ready === 1'b1), "send_ready_high");
            @(posedge clk);
            #1;
            expected_accepted = golden_inc(expected_accepted);
            observe_cycle(0, 1'b1);
            @(negedge clk);
            in_valid = 1'b0;
            in_data = 8'd0;
            #1;
            simple_check((in_ready === 1'b0), "send_ready_low_while_busy");
            for (elapsed = 1; elapsed <= B10; elapsed = elapsed + 1) begin
                @(posedge clk);
                #1;
                if (elapsed == B10) begin
                    expected_completed = golden_inc(expected_completed);
                end
                observe_cycle(elapsed, (elapsed < B10));
            end
            @(negedge clk);
            #1;
            simple_check((in_ready === 1'b1), "send_ready_after_completion");
        end
    endtask

    task automatic send_byte_compact(input logic [7:0] value);
        integer phase;
        integer target;
        integer elapsed;
        integer advance_count;
        begin
            @(negedge clk);
            in_valid = 1'b1;
            in_data = value;
            waveform_byte = value;
            #1;
            simple_check((in_ready === 1'b1), "compact_send_ready_high");
            @(posedge clk);
            #1;
            expected_accepted = golden_inc(expected_accepted);
            observe_cycle(0, 1'b1);
            @(negedge clk);
            in_valid = 1'b0;
            in_data = 8'd0;
            #1;
            simple_check((in_ready === 1'b0), "compact_send_ready_low_while_busy");
            elapsed = 0;
            for (phase = 1; phase <= 10; phase = phase + 1) begin
                target = boundary_for_k(phase);
                advance_count = target - 1 - elapsed;
                repeat (advance_count) begin
                    @(posedge clk);
                    #1;
                end
                elapsed = target - 1;
                observe_cycle(elapsed, 1'b1);
                @(posedge clk);
                #1;
                elapsed = elapsed + 1;
                if (phase == 10) begin
                    expected_completed = golden_inc(expected_completed);
                end
                observe_cycle(elapsed, (phase < 10));
            end
            @(negedge clk);
            #1;
            simple_check((in_ready === 1'b1), "compact_send_ready_after_completion");
        end
    endtask

    task automatic advance_to_pre_boundary(input integer target);
        integer elapsed;
        begin
            for (elapsed = 1; elapsed < target; elapsed = elapsed + 1) begin
                @(posedge clk);
                #1;
                observe_cycle(elapsed, 1'b1);
                @(negedge clk);
                #1;
            end
        end
    endtask

    task automatic observe_abort_held();
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if ((tx !== 1'b1) || (busy !== 1'b0) || (in_ready !== 1'b0) ||
                (stat_accepted !== expected_accepted[STAT_W-1:0]) ||
                (stat_completed !== expected_completed[STAT_W-1:0]) ||
                (stat_aborted !== expected_aborted[STAT_W-1:0])) begin
                failures = failures + 1;
                case_failed = 1'b1;
                $display("CHECK_FAIL name=abort_held tx=%0b busy=%0b ready=%0b accepted=%0d/%0d completed=%0d/%0d aborted=%0d/%0d",
                         tx, busy, in_ready, stat_accepted, expected_accepted,
                         stat_completed, expected_completed,
                         stat_aborted, expected_aborted);
            end
        end
    endtask

    task automatic cancel_asserted();
        integer hold_index;
        begin
            // The caller is just after the admission edge's following negedge,
            // so cancel reaches the next selected boundary edge synchronously.
            cancel = 1'b1;
            #1;
            simple_check((in_ready === 1'b0), "cancel_preedge_ready_low");
            @(posedge clk);
            #1;
            expected_aborted = golden_inc(expected_aborted);
            observe_abort_held();
            for (hold_index = 0; hold_index < 3; hold_index = hold_index + 1) begin
                @(posedge clk);
                #1;
                observe_abort_held();
            end
            @(negedge clk);
            cancel = 1'b0;
            #1;
            simple_check((in_ready === 1'b1), "cancel_release_ready_high");
            simple_check((tx === 1'b1), "cancel_release_tx_high");
        end
    endtask

    task automatic cancel_at_phase(input integer phase);
        integer target;
        begin
            admit_only(8'hA5);
            target = boundary_for_k(phase);
            advance_to_pre_boundary(target);
            cancel_asserted();
            send_byte(8'h3C);
        end
    endtask

    task automatic observe_reset_held();
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if ((tx !== 1'b1) || (busy !== 1'b0) || (in_ready !== 1'b0) ||
                (stat_accepted !== {STAT_W{1'b0}}) ||
                (stat_completed !== {STAT_W{1'b0}}) ||
                (stat_aborted !== {STAT_W{1'b0}})) begin
                failures = failures + 1;
                case_failed = 1'b1;
                $display("CHECK_FAIL name=reset_held tx=%0b busy=%0b ready=%0b accepted=%0d completed=%0d aborted=%0d",
                         tx, busy, in_ready, stat_accepted, stat_completed, stat_aborted);
            end
        end
    endtask

    task automatic reset_asserted();
        integer hold_index;
        begin
            rst = 1'b1;
            cancel = 1'b1;
            expected_accepted = 0;
            expected_completed = 0;
            expected_aborted = 0;
            #1;
            simple_check((in_ready === 1'b0), "reset_priority_preedge_ready_low");
            @(posedge clk);
            #1;
            observe_reset_held();
            for (hold_index = 0; hold_index < 3; hold_index = hold_index + 1) begin
                @(posedge clk);
                #1;
                observe_reset_held();
            end
            @(negedge clk);
            rst = 1'b0;
            cancel = 1'b0;
            #1;
            simple_check((in_ready === 1'b1), "reset_priority_release_ready_high");
        end
    endtask

    task automatic reset_at_phase(input integer phase);
        integer target;
        begin
            admit_only(8'h5A);
            target = boundary_for_k(phase);
            advance_to_pre_boundary(target);
            reset_asserted();
            send_byte(8'hC3);
        end
    endtask

    task automatic case_reset_idle();
        begin
            begin_case("reset_idle");
            reset_dut();
            end_case();
        end
    endtask

    task automatic case_long_idle();
        integer index;
        begin
            begin_case("long_idle");
            for (index = 0; index < 1000; index = index + 1) begin
                @(posedge clk);
                #1;
                if ((index % 50) == 0) begin
                    simple_check((tx === 1'b1), "idle_tx_high");
                    simple_check((busy === 1'b0), "idle_busy_low");
                    simple_check((in_ready === 1'b1), "idle_ready_high");
                end
            end
            simple_check((expected_accepted == 0), "idle_no_accept");
            simple_check((expected_completed == 0), "idle_no_completion");
            simple_check((stat_aborted === expected_aborted[STAT_W-1:0]), "idle_no_abort");
            end_case();
        end
    endtask

    task automatic case_all_bytes();
        integer value;
        begin
            begin_case("all_byte_values");
            for (value = 0; value < 256; value = value + 1) begin
                send_byte(value[7:0]);
            end
            simple_check((expected_accepted == 256), "all_bytes_accepted_model");
            simple_check((expected_completed == 256), "all_bytes_completed_model");
            simple_check((stat_accepted === expected_accepted[STAT_W-1:0]), "all_bytes_accepted_observed");
            simple_check((stat_completed === expected_completed[STAT_W-1:0]), "all_bytes_completed_observed");
            end_case();
        end
    endtask

    task automatic case_busy_perturbation();
        integer elapsed;
        begin
            begin_case("busy_perturbation");
            @(negedge clk);
            in_valid = 1'b1;
            in_data = 8'h3C;
            waveform_byte = 8'h3C;
            #1;
            simple_check((in_ready === 1'b1), "perturb_admission_ready");
            @(posedge clk);
            #1;
            expected_accepted = golden_inc(expected_accepted);
            observe_cycle(0, 1'b1);
            @(negedge clk);
            in_valid = 1'b0;
            in_data = 8'd0;
            #1;
            simple_check((in_ready === 1'b0), "perturb_ready_low");
            for (elapsed = 1; elapsed < B10; elapsed = elapsed + 1) begin
                @(posedge clk);
                #1;
                observe_cycle(elapsed, 1'b1);
                @(negedge clk);
                if (elapsed == 1) begin
                    in_valid = 1'b1;
                    in_data = 8'hFF;
                end else if (elapsed == 2) begin
                    in_valid = 1'b0;
                    in_data = 8'h00;
                end else if (elapsed == 3) begin
                    in_valid = 1'b1;
                    in_data = 8'hA5;
                end else if (elapsed == 4) begin
                    in_valid = 1'b0;
                    in_data = 8'h00;
                end else if (elapsed == (B10 - 2)) begin
                    in_valid = 1'b1;
                    in_data = 8'hE7;
                end
                #1;
                if (in_valid) begin
                    simple_check((in_ready === 1'b0), "perturb_busy_ready_low");
                end
            end
            @(posedge clk);
            #1;
            expected_completed = golden_inc(expected_completed);
            observe_cycle(B10, 1'b0);
            simple_check((expected_accepted == 257), "perturb_no_same_edge_credit");
            @(negedge clk);
            in_valid = 1'b0;
            in_data = 8'd0;
            #1;
            simple_check((in_ready === 1'b1), "perturb_post_completion_ready");
            end_case();
        end
    endtask

    task automatic case_cancel_each_phase();
        integer phase;
        begin
            begin_case("cancel_each_phase");
            for (phase = 1; phase <= 10; phase = phase + 1) begin
                cancel_at_phase(phase);
            end
            simple_check((expected_accepted == 20), "cancel_phases_accepted_model");
            simple_check((expected_completed == 10), "cancel_phases_completed_model");
            simple_check((expected_aborted == 10), "cancel_phases_aborted_model");
            end_case();
        end
    endtask

    task automatic case_reset_each_phase();
        integer phase;
        begin
            begin_case("reset_each_phase");
            for (phase = 1; phase <= 10; phase = phase + 1) begin
                reset_at_phase(phase);
            end
            simple_check((expected_accepted == 1), "reset_phases_accepted_model");
            simple_check((expected_completed == 1), "reset_phases_completed_model");
            simple_check((stat_aborted === {STAT_W{1'b0}}), "reset_phases_no_abort");
            end_case();
        end
    endtask

    task automatic case_cancel_idle();
        integer hold_index;
        begin
            begin_case("cancel_idle");
            @(negedge clk);
            cancel = 1'b1;
            #1;
            simple_check((in_ready === 1'b0), "cancel_idle_ready_low");
            for (hold_index = 0; hold_index < 3; hold_index = hold_index + 1) begin
                @(posedge clk);
                #1;
                simple_check((tx === 1'b1), "cancel_idle_tx_high");
                simple_check((busy === 1'b0), "cancel_idle_busy_low");
                simple_check((stat_accepted === expected_accepted[STAT_W-1:0]), "cancel_idle_accepted_hold");
                simple_check((stat_completed === expected_completed[STAT_W-1:0]), "cancel_idle_completed_hold");
                simple_check((stat_aborted === expected_aborted[STAT_W-1:0]), "cancel_idle_aborted_hold");
            end
            @(negedge clk);
            cancel = 1'b0;
            #1;
            simple_check((in_ready === 1'b1), "cancel_idle_release_ready");
            end_case();
        end
    endtask

    task automatic case_reset_over_cancel();
        begin
            begin_case("reset_over_cancel");
            admit_only(8'h6D);
            advance_to_pre_boundary(B5);
            reset_asserted();
            send_byte(8'h96);
            end_case();
        end
    endtask

    task automatic case_two_aborts();
        begin
            begin_case("two_aborts");
            admit_only(8'h01);
            cancel_asserted();
            admit_only(8'h80);
            cancel_asserted();
            simple_check((expected_accepted == 3), "two_aborts_accepted_model");
            simple_check((expected_completed == 1), "two_aborts_completed_model");
            simple_check((expected_aborted == 2), "two_aborts_aborted_model");
            simple_check((stat_accepted === expected_accepted[STAT_W-1:0]), "two_aborts_accepted_observed");
            simple_check((stat_completed === expected_completed[STAT_W-1:0]), "two_aborts_completed_observed");
            simple_check((stat_aborted === expected_aborted[STAT_W-1:0]), "two_aborts_aborted_observed");
            end_case();
        end
    endtask

    task automatic case_sustained_offer();
        integer index;
        integer elapsed;
        logic [7:0] next_value;
        begin
            begin_case("sustained_offer");
            @(negedge clk);
            in_valid = 1'b1;
            in_data = 8'd11;
            #1;
            simple_check((in_ready === 1'b1), "sustained_initial_ready");
            for (index = 0; index < 64; index = index + 1) begin
                @(posedge clk);
                #1;
                waveform_byte = in_data;
                expected_accepted = golden_inc(expected_accepted);
                observe_cycle(0, 1'b1);
                next_value = ((index * 37) + 11) & 8'hFF;
                @(negedge clk);
                in_data = next_value;
                #1;
                simple_check((in_ready === 1'b0), "sustained_ready_low_busy");
                for (elapsed = 1; elapsed <= B10; elapsed = elapsed + 1) begin
                    @(posedge clk);
                    #1;
                    if (elapsed == B10) begin
                        expected_completed = golden_inc(expected_completed);
                    end
                    observe_cycle(elapsed, (elapsed < B10));
                    if (elapsed == B10) begin
                        simple_check((expected_accepted == (index + 1)), "sustained_no_completion_credit");
                    end
                end
                if (index < 63) begin
                    @(negedge clk);
                    #1;
                    simple_check((in_ready === 1'b1), "sustained_ready_only_after_completion");
                end
            end
            @(negedge clk);
            in_valid = 1'b0;
            in_data = 8'd0;
            #1;
            simple_check((in_ready === 1'b1), "sustained_final_ready");
            simple_check((expected_accepted == 64), "sustained_accepted_model");
            simple_check((expected_completed == 64), "sustained_completed_model");
            end_case();
        end
    endtask

    task automatic case_default_frame();
        begin
            begin_case("default_frame");
            send_byte_compact(8'h00);
            send_byte_compact(8'h55);
            send_byte_compact(8'hAA);
            simple_check((expected_accepted == 3), "default_accepted_model");
            simple_check((expected_completed == 3), "default_completed_model");
            end_case();
        end
    endtask

    task automatic case_baud300_frame();
        begin
            begin_case("baud300_frame");
            send_byte_compact(8'h5A);
            send_byte_compact(8'hC3);
            simple_check((expected_accepted == 2), "baud300_accepted_model");
            simple_check((expected_completed == 2), "baud300_completed_model");
            end_case();
        end
    endtask

    task automatic case_baud1200_frame();
        begin
            begin_case("baud1200_frame");
            send_byte_compact(8'h00);
            send_byte_compact(8'hA5);
            send_byte_compact(8'hFF);
            simple_check((expected_accepted == 3), "baud1200_accepted_model");
            simple_check((expected_completed == 3), "baud1200_completed_model");
            end_case();
        end
    endtask

    task automatic case_stat_saturation();
        integer index;
        begin
            begin_case("stat_saturation");
            for (index = 0; index < 4; index = index + 1) begin
                send_byte(8'h10 + index[7:0]);
            end
            simple_check((stat_accepted === 2'd3), "stat2_accepted_completion_saturation");
            simple_check((stat_completed === 2'd3), "stat2_completed_saturation");
            for (index = 0; index < 4; index = index + 1) begin
                admit_only(8'h80 + index[7:0]);
                cancel_asserted();
            end
            simple_check((stat_accepted === 2'd3), "stat2_accepted_abort_saturation");
            simple_check((stat_completed === 2'd3), "stat2_completed_abort_saturation");
            simple_check((stat_aborted === 2'd3), "stat2_aborted_saturation");
            send_byte(8'hEE);
            simple_check((stat_accepted === 2'd3), "stat2_accepted_transfer_held");
            simple_check((stat_completed === 2'd3), "stat2_completed_transfer_held");
            simple_check((stat_aborted === 2'd3), "stat2_aborted_transfer_held");
            end_case();
        end
    endtask

    task automatic finish_tb();
        begin
            if (current_case != "") begin
                failures = failures + 1;
                $display("CHECK_FAIL name=no_open_case_at_finish");
            end
            $display("TB_STAT accepted=%0d", stat_accepted);
            $display("TB_STAT completed=%0d", stat_completed);
            $display("TB_STAT aborted=%0d", stat_aborted);
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
        $display("TB_BEGIN tb=%s", NAME);
        case_reset_idle();
        case (PROFILE)
            P_ALL_BYTES: begin
                case_long_idle();
                case_all_bytes();
                case_busy_perturbation();
            end
            P_CANCEL_RESET: begin
                case_cancel_each_phase();
                case_reset_each_phase();
                case_cancel_idle();
                case_reset_over_cancel();
                case_two_aborts();
            end
            P_SUSTAINED: begin
                case_sustained_offer();
            end
            P_DEFAULT: begin
                case_default_frame();
            end
            P_BAUD_300: begin
                case_baud300_frame();
            end
            P_BAUD_1200: begin
                case_baud1200_frame();
            end
            P_STAT_W2: begin
                case_stat_saturation();
            end
            default: begin
                begin_case("invalid_profile");
                simple_check(1'b0, "unknown_profile");
                end_case();
            end
        endcase
        finish_tb();
    end

endmodule

module tb_uart_tx_ratio_97_11;
    tb_uart_tx_harness #(
        .CLOCK_HZ(97),
        .BAUD(11),
        .STAT_W(32),
        .PROFILE(0),
        .NAME("tb_uart_tx_ratio_97_11")
    ) env ();
endmodule

module tb_uart_tx_ratio_31_3;
    tb_uart_tx_harness #(
        .CLOCK_HZ(31),
        .BAUD(3),
        .STAT_W(32),
        .PROFILE(0),
        .NAME("tb_uart_tx_ratio_31_3")
    ) env ();
endmodule

module tb_uart_tx_min_ratio;
    tb_uart_tx_harness #(
        .CLOCK_HZ(2),
        .BAUD(1),
        .STAT_W(32),
        .PROFILE(0),
        .NAME("tb_uart_tx_min_ratio")
    ) env ();
endmodule

module tb_uart_tx_cancel_reset;
    tb_uart_tx_harness #(
        .CLOCK_HZ(97),
        .BAUD(11),
        .STAT_W(32),
        .PROFILE(1),
        .NAME("tb_uart_tx_cancel_reset")
    ) env ();
endmodule

module tb_uart_tx_sustained;
    tb_uart_tx_harness #(
        .CLOCK_HZ(97),
        .BAUD(11),
        .STAT_W(32),
        .PROFILE(2),
        .NAME("tb_uart_tx_sustained")
    ) env ();
endmodule

module tb_uart_tx_default_9600;
    tb_uart_tx_harness #(
        .CLOCK_HZ(100000000),
        .BAUD(9600),
        .STAT_W(32),
        .PROFILE(3),
        .NAME("tb_uart_tx_default_9600")
    ) env ();
endmodule

module tb_uart_tx_baud_300;
    tb_uart_tx_harness #(
        .CLOCK_HZ(100000000),
        .BAUD(300),
        .STAT_W(32),
        .PROFILE(4),
        .NAME("tb_uart_tx_baud_300")
    ) env ();
endmodule

module tb_uart_tx_baud_1200;
    tb_uart_tx_harness #(
        .CLOCK_HZ(100000000),
        .BAUD(1200),
        .STAT_W(32),
        .PROFILE(5),
        .NAME("tb_uart_tx_baud_1200")
    ) env ();
endmodule

module tb_uart_tx_stat_w2;
    tb_uart_tx_harness #(
        .CLOCK_HZ(97),
        .BAUD(11),
        .STAT_W(2),
        .PROFILE(6),
        .NAME("tb_uart_tx_stat_w2")
    ) env ();
endmodule

`ifndef G_CLOCK
`define G_CLOCK 97
`endif
`ifndef G_BAUD
`define G_BAUD 11
`endif
`ifndef G_STAT_W
`define G_STAT_W 32
`endif

module tb_uart_tx_guard;
    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic in_valid = 1'b0;
    logic in_ready;
    logic tx;
    logic busy;

    deepeye_uart_tx #(
        .CLOCK_HZ(`G_CLOCK),
        .BAUD(`G_BAUD),
        .STAT_W(`G_STAT_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_data(8'd0),
        .tx(tx),
        .busy(busy),
        .stat_accepted(),
        .stat_completed(),
        .stat_aborted()
    );

    initial begin
        #100;
        $display("GUARD_TB_UNEXPECTED_NO_FATAL");
        $finish;
    end
endmodule
