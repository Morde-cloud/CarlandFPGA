// Public-port testbenches for deepeye_uart_rx.
//
// Work: B-UART-RX-20261023-25-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-UART-RX-20261023-25
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// Only declared DUT ports are observed.  The BFM drives rx_async at negedges
// and accounts for the two-register synchronizer delay when establishing a
// qualified falling edge.  Frame samples are checked just before and at every
// half-bit boundary derived from ceil(h*CLOCK_HZ/(2*BAUD)).  The golden slot
// and counters are evaluated from the frozen contract, not internal RTL state.

`timescale 1ns/1ps

module tb_uart_rx_harness #(
    parameter integer CLOCK_HZ = 160,
    parameter integer BAUD = 10,
    parameter integer STAT_W = 32,
    parameter integer PROFILE = 0,
    parameter string NAME = "tb_uart_rx_harness"
) ();

    localparam integer P_ALL_BYTES = 0;
    localparam integer P_PROTOCOL = 1;
    localparam integer P_ABORT = 2;
    localparam integer P_STAT_W2 = 3;
    localparam integer P_DEFAULT = 4;
    localparam integer P_BAUD_300 = 5;
    localparam integer P_BAUD_1200 = 6;

    localparam integer H1  = (CLOCK_HZ + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H2  = ((2 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H3  = ((3 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H4  = ((4 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H5  = ((5 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H6  = ((6 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H7  = ((7 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H8  = ((8 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H9  = ((9 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H10 = ((10 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H11 = ((11 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H12 = ((12 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H13 = ((13 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H14 = ((14 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H15 = ((15 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H16 = ((16 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H17 = ((17 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H18 = ((18 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);
    localparam integer H19 = ((19 * CLOCK_HZ) + (2 * BAUD) - 1) / (2 * BAUD);

    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic rx_async = 1'b1;
    logic out_ready = 1'b0;

    logic out_valid;
    logic [7:0] out_data;
    logic busy;
    logic framing_error_event;
    logic overrun_event;
    logic false_start_event;
    logic [STAT_W-1:0] stat_frames;
    logic [STAT_W-1:0] stat_retired;
    logic [STAT_W-1:0] stat_overruns;
    logic [STAT_W-1:0] stat_framing;
    logic [STAT_W-1:0] stat_false_starts;
    logic [STAT_W-1:0] stat_aborted;

    deepeye_uart_rx #(
        .CLOCK_HZ(CLOCK_HZ),
        .BAUD(BAUD),
        .STAT_W(STAT_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .rx_async(rx_async),
        .out_ready(out_ready),
        .out_valid(out_valid),
        .out_data(out_data),
        .busy(busy),
        .framing_error_event(framing_error_event),
        .overrun_event(overrun_event),
        .false_start_event(false_start_event),
        .stat_frames(stat_frames),
        .stat_retired(stat_retired),
        .stat_overruns(stat_overruns),
        .stat_framing(stat_framing),
        .stat_false_starts(stat_false_starts),
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

    longint expected_frames = 0;
    longint expected_retired = 0;
    longint expected_overruns = 0;
    longint expected_framing = 0;
    longint expected_false_starts = 0;
    longint expected_aborted = 0;
    bit expected_slot_full = 1'b0;
    logic [7:0] expected_slot_data = 8'd0;

    integer frame_elapsed = 0;
    logic [7:0] frame_data = 8'd0;
    bit frame_stop_good = 1'b1;

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

    function automatic longint golden_add(input longint value, input integer amount);
        longint maximum;
        longint candidate;
        begin
            maximum = (64'd1 << STAT_W) - 64'd1;
            candidate = value + amount;
            if (candidate > maximum) begin
                golden_add = maximum;
            end else begin
                golden_add = candidate;
            end
        end
    endfunction

    function automatic integer half_boundary(input integer index);
        begin
            case (index)
                1: half_boundary = H1;
                2: half_boundary = H2;
                3: half_boundary = H3;
                4: half_boundary = H4;
                5: half_boundary = H5;
                6: half_boundary = H6;
                7: half_boundary = H7;
                8: half_boundary = H8;
                9: half_boundary = H9;
                10: half_boundary = H10;
                11: half_boundary = H11;
                12: half_boundary = H12;
                13: half_boundary = H13;
                14: half_boundary = H14;
                15: half_boundary = H15;
                16: half_boundary = H16;
                17: half_boundary = H17;
                18: half_boundary = H18;
                19: half_boundary = H19;
                default: half_boundary = -1;
            endcase
        end
    endfunction

    function automatic logic line_at_even(input integer index,
                                          input logic [7:0] value,
                                          input bit stop_good);
        begin
            case (index)
                2: line_at_even = value[0];
                4: line_at_even = value[1];
                6: line_at_even = value[2];
                8: line_at_even = value[3];
                10: line_at_even = value[4];
                12: line_at_even = value[5];
                14: line_at_even = value[6];
                16: line_at_even = value[7];
                18: line_at_even = stop_good;
                default: line_at_even = 1'b1;
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
                failures = failures + 1;
                $display("CHECK_FAIL name=nested_case previous=%s", current_case);
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

    task automatic check_stats();
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if ((stat_frames !== expected_frames[STAT_W-1:0]) ||
                (stat_retired !== expected_retired[STAT_W-1:0]) ||
                (stat_overruns !== expected_overruns[STAT_W-1:0]) ||
                (stat_framing !== expected_framing[STAT_W-1:0]) ||
                (stat_false_starts !== expected_false_starts[STAT_W-1:0]) ||
                (stat_aborted !== expected_aborted[STAT_W-1:0])) begin
                failures = failures + 1;
                case_failed = 1'b1;
                $display("CHECK_FAIL name=stats actual_frames=%0d expected_frames=%0d actual_retired=%0d expected_retired=%0d actual_overruns=%0d expected_overruns=%0d actual_framing=%0d expected_framing=%0d actual_false=%0d expected_false=%0d actual_aborted=%0d expected_aborted=%0d",
                         stat_frames, expected_frames, stat_retired, expected_retired,
                         stat_overruns, expected_overruns, stat_framing, expected_framing,
                         stat_false_starts, expected_false_starts,
                         stat_aborted, expected_aborted);
            end
        end
    endtask

    task automatic check_slot();
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if ((out_valid !== expected_slot_full) ||
                (expected_slot_full && (out_data !== expected_slot_data))) begin
                failures = failures + 1;
                case_failed = 1'b1;
                $display("CHECK_FAIL name=slot actual_valid=%0b expected_valid=%0b actual_data=%02x expected_data=%02x",
                         out_valid, expected_slot_full, out_data, expected_slot_data);
            end
        end
    endtask

    task automatic check_no_pulses();
        begin
            checks = checks + 1;
            case_checks = case_checks + 1;
            if ((framing_error_event !== 1'b0) ||
                (overrun_event !== 1'b0) ||
                (false_start_event !== 1'b0)) begin
                failures = failures + 1;
                case_failed = 1'b1;
                $display("CHECK_FAIL name=pulses framing=%0b overrun=%0b false_start=%0b",
                         framing_error_event, overrun_event, false_start_event);
            end
        end
    endtask

    task automatic reset_dut();
        integer index;
        begin
            @(negedge clk);
            rst = 1'b1;
            cancel = 1'b0;
            rx_async = 1'b0;
            out_ready = 1'b0;
            expected_frames = 0;
            expected_retired = 0;
            expected_overruns = 0;
            expected_framing = 0;
            expected_false_starts = 0;
            expected_aborted = 0;
            expected_slot_full = 1'b0;
            expected_slot_data = 8'd0;
            for (index = 0; index < 3; index = index + 1) begin
                @(posedge clk);
                #1;
                simple_check((busy === 1'b0), "reset_busy_low");
                simple_check((out_valid === 1'b0), "reset_out_invalid");
                check_no_pulses();
                check_stats();
            end
            @(negedge clk);
            rst = 1'b0;
            rx_async = 1'b0;
            #1;
            simple_check((out_valid === 1'b0), "reset_release_out_invalid");
            for (index = 0; index < 8; index = index + 1) begin
                @(posedge clk);
                #1;
                simple_check((busy === 1'b0), "low_after_reset_no_start");
                check_no_pulses();
            end
            check_stats();
            check_slot();
        end
    endtask

    task automatic qualify_high();
        integer index;
        begin
            simple_check((busy === 1'b0), "qualify_entry_not_busy");
            @(negedge clk);
            rx_async = 1'b1;
            #1;
            for (index = 0; index < 5; index = index + 1) begin
                @(posedge clk);
                #1;
                simple_check((busy === 1'b0), "qualify_high_no_start");
                check_no_pulses();
            end
            check_stats();
            check_slot();
        end
    endtask

    task automatic arm_frame(input logic [7:0] value);
        begin
            qualify_high();
            @(negedge clk);
            rx_async = 1'b0;
            #1;
            @(posedge clk);
            #1;
            simple_check((busy === 1'b0), "fall_pre_sync1_idle");
            @(posedge clk);
            #1;
            simple_check((busy === 1'b0), "fall_pre_sync2_idle");
            @(posedge clk);
            #1;
            simple_check((busy === 1'b1), "qualified_start_busy");
            check_no_pulses();
            check_stats();
            check_slot();
            frame_elapsed = 0;
            frame_data = value;
            frame_stop_good = 1'b1;
        end
    endtask

    task automatic advance_to_pre(input integer phase);
        integer target;
        integer advance_count;
        begin
            target = half_boundary(phase);
            advance_count = target - 1 - frame_elapsed;
            repeat (advance_count) begin
                @(posedge clk);
                #1;
            end
            frame_elapsed = target - 1;
            simple_check((busy === 1'b1), "pre_boundary_busy");
            check_no_pulses();
            check_stats();
            check_slot();
        end
    endtask

    task automatic step_boundary(input integer phase,
                                 input logic [7:0] value,
                                 input bit stop_good);
        integer target;
        begin
            advance_to_pre(phase);
            @(posedge clk);
            #1;
            target = half_boundary(phase);
            frame_elapsed = target;
            if ((phase % 2) == 0) begin
                rx_async = line_at_even(phase, value, stop_good);
            end
            simple_check((busy === 1'b1), "mid_frame_busy_at_boundary");
            check_no_pulses();
            check_stats();
            check_slot();
        end
    endtask

    task automatic run_frame_core(input logic [7:0] value,
                                  input bit stop_good,
                                  input integer mode);
        integer phase;
        bit old_slot_full;
        bit retired_now;
        bit expect_overrun;
        bit expect_framing;
        begin
            if (mode == 1) begin
                simple_check((expected_slot_full === 1'b0), "drain_mode_slot_empty");
                @(negedge clk);
                out_ready = 1'b1;
                #1;
            end else begin
                @(negedge clk);
                out_ready = 1'b0;
                #1;
                if (mode == 2) begin
                    simple_check((expected_slot_full === 1'b1), "terminal_mode_old_slot_full");
                end
            end

            arm_frame(value);
            frame_stop_good = stop_good;
            for (phase = 1; phase <= 18; phase = phase + 1) begin
                step_boundary(phase, value, stop_good);
            end
            advance_to_pre(19);
            if (mode == 2) begin
                @(negedge clk);
                out_ready = 1'b1;
                #1;
            end

            old_slot_full = expected_slot_full;
            retired_now = old_slot_full && out_ready;
            if (retired_now) begin
                expected_retired = golden_inc(expected_retired);
                expected_slot_full = 1'b0;
            end
            expect_overrun = 1'b0;
            expect_framing = 1'b0;

            @(posedge clk);
            #1;
            frame_elapsed = H19;
            if (stop_good) begin
                expected_frames = golden_inc(expected_frames);
                if (!old_slot_full || retired_now) begin
                    expected_slot_full = 1'b1;
                    expected_slot_data = value;
                end else begin
                    expected_overruns = golden_inc(expected_overruns);
                    expect_overrun = 1'b1;
                end
            end else begin
                expected_framing = golden_inc(expected_framing);
                expect_framing = 1'b1;
            end

            simple_check((busy === 1'b0), "final_boundary_busy_low");
            simple_check((framing_error_event === expect_framing), "final_framing_pulse");
            simple_check((overrun_event === expect_overrun), "final_overrun_pulse");
            simple_check((false_start_event === 1'b0), "final_false_start_zero");
            check_stats();
            check_slot();

            @(posedge clk);
            #1;
            if (((mode == 1) || (mode == 2)) && expected_slot_full) begin
                expected_retired = golden_inc(expected_retired);
                expected_slot_full = 1'b0;
            end
            simple_check((busy === 1'b0), "post_frame_busy_low");
            check_no_pulses();
            check_stats();
            check_slot();

            if ((mode == 1) || (mode == 2)) begin
                @(negedge clk);
                out_ready = 1'b0;
                #1;
            end
        end
    endtask

    task automatic drain_slot();
        begin
            simple_check((expected_slot_full === 1'b1), "drain_pre_slot_full");
            simple_check((out_ready === 1'b0), "drain_pre_ready_low");
            @(negedge clk);
            out_ready = 1'b1;
            #1;
            check_slot();
            @(posedge clk);
            #1;
            expected_retired = golden_inc(expected_retired);
            expected_slot_full = 1'b0;
            simple_check((out_valid === 1'b0), "drain_out_invalid");
            check_no_pulses();
            check_stats();
            @(negedge clk);
            out_ready = 1'b0;
            #1;
        end
    endtask

    task automatic hold_slot_stable(input integer cycles);
        integer index;
        begin
            simple_check((expected_slot_full === 1'b1), "hold_slot_full");
            for (index = 0; index < cycles; index = index + 1) begin
                @(posedge clk);
                #1;
                check_slot();
                check_no_pulses();
            end
            check_stats();
        end
    endtask

    task automatic run_false_start();
        begin
            @(negedge clk);
            out_ready = 1'b0;
            arm_frame(8'h00);
            @(negedge clk);
            rx_async = 1'b1;
            #1;
            advance_to_pre(1);
            @(posedge clk);
            #1;
            frame_elapsed = H1;
            expected_false_starts = golden_inc(expected_false_starts);
            simple_check((busy === 1'b0), "false_start_busy_low");
            simple_check((false_start_event === 1'b1), "false_start_pulse");
            simple_check((framing_error_event === 1'b0), "false_start_no_framing");
            simple_check((overrun_event === 1'b0), "false_start_no_overrun");
            check_stats();
            check_slot();
            @(posedge clk);
            #1;
            simple_check((false_start_event === 1'b0), "false_start_one_cycle");
            simple_check((busy === 1'b0), "false_start_recovery_not_busy");
            check_stats();
        end
    endtask

    task automatic arm_partial_to_pre(input logic [7:0] value, input integer phase);
        integer index;
        begin
            @(negedge clk);
            out_ready = 1'b0;
            arm_frame(value);
            for (index = 1; index < phase; index = index + 1) begin
                step_boundary(index, value, 1'b1);
            end
            advance_to_pre(phase);
        end
    endtask

    task automatic cancel_pending_at_phase(input integer phase,
                                           input integer hold_cycles,
                                           input bit ready_at_abort);
        integer index;
        begin
            simple_check((expected_slot_full === 1'b1), "cancel_pending_slot_full");
            arm_partial_to_pre(8'hA5, phase);
            @(negedge clk);
            out_ready = ready_at_abort;
            cancel = 1'b1;
            #1;
            expected_aborted = golden_add(expected_aborted, 2);
            expected_slot_full = 1'b0;
            @(posedge clk);
            #1;
            simple_check((busy === 1'b0), "cancel_busy_low");
            simple_check((out_valid === 1'b0), "cancel_out_invalid");
            check_no_pulses();
            check_stats();
            check_slot();
            for (index = 0; index < hold_cycles; index = index + 1) begin
                @(posedge clk);
                #1;
                simple_check((busy === 1'b0), "held_cancel_busy_low");
                simple_check((out_valid === 1'b0), "held_cancel_out_invalid");
                check_no_pulses();
                check_stats();
            end
            @(negedge clk);
            cancel = 1'b0;
            rx_async = 1'b0;
            out_ready = 1'b0;
            #1;
            for (index = 0; index < 8; index = index + 1) begin
                @(posedge clk);
                #1;
                simple_check((busy === 1'b0), "post_cancel_low_no_start");
                check_stats();
            end
        end
    endtask

    task automatic reset_pending_at_phase(input integer phase, input bit also_cancel);
        integer index;
        begin
            simple_check((expected_slot_full === 1'b1), "reset_pending_slot_full");
            arm_partial_to_pre(8'h5A, phase);
            @(negedge clk);
            rst = 1'b1;
            cancel = also_cancel;
            #1;
            expected_frames = 0;
            expected_retired = 0;
            expected_overruns = 0;
            expected_framing = 0;
            expected_false_starts = 0;
            expected_aborted = 0;
            expected_slot_full = 1'b0;
            expected_slot_data = 8'd0;
            @(posedge clk);
            #1;
            simple_check((busy === 1'b0), "phase_reset_busy_low");
            simple_check((out_valid === 1'b0), "phase_reset_out_invalid");
            check_no_pulses();
            check_stats();
            for (index = 0; index < 3; index = index + 1) begin
                @(posedge clk);
                #1;
                simple_check((busy === 1'b0), "held_reset_busy_low");
                check_stats();
            end
            @(negedge clk);
            rst = 1'b0;
            cancel = 1'b0;
            rx_async = 1'b0;
            out_ready = 1'b0;
            #1;
            for (index = 0; index < 8; index = index + 1) begin
                @(posedge clk);
                #1;
                simple_check((busy === 1'b0), "post_reset_low_no_start");
                check_no_pulses();
                check_stats();
            end
        end
    endtask

    task automatic cancel_idle_slot();
        integer index;
        begin
            simple_check((expected_slot_full === 1'b1), "idle_cancel_slot_full");
            simple_check((busy === 1'b0), "idle_cancel_not_busy");
            @(negedge clk);
            out_ready = 1'b0;
            cancel = 1'b1;
            #1;
            expected_aborted = golden_add(expected_aborted, 1);
            expected_slot_full = 1'b0;
            @(posedge clk);
            #1;
            simple_check((out_valid === 1'b0), "idle_cancel_out_invalid");
            check_no_pulses();
            check_stats();
            for (index = 0; index < 4; index = index + 1) begin
                @(posedge clk);
                #1;
                check_stats();
            end
            @(negedge clk);
            cancel = 1'b0;
            rx_async = 1'b0;
            #1;
            for (index = 0; index < 8; index = index + 1) begin
                @(posedge clk);
                #1;
                simple_check((busy === 1'b0), "idle_cancel_low_no_start");
            end
        end
    endtask

    task automatic fill_slot(input logic [7:0] value);
        begin
            simple_check((expected_slot_full === 1'b0), "fill_slot_pre_empty");
            run_frame_core(value, 1'b1, 0);
            simple_check((expected_slot_full === 1'b1), "fill_slot_post_full");
            check_slot();
        end
    endtask

    task automatic case_reset_idle();
        begin
            begin_case("reset_idle");
            reset_dut();
            end_case();
        end
    endtask

    task automatic case_all_bytes();
        integer value;
        begin
            begin_case("all_byte_values");
            for (value = 0; value < 256; value = value + 1) begin
                run_frame_core(value[7:0], 1'b1, 1);
            end
            simple_check((expected_frames == 256), "all_bytes_frame_model");
            simple_check((expected_retired == 256), "all_bytes_retired_model");
            simple_check((expected_slot_full === 1'b0), "all_bytes_slot_empty");
            check_stats();
            end_case();
        end
    endtask

    task automatic case_bad_stop_recovery();
        begin
            begin_case("bad_stop_recovery");
            run_frame_core(8'h00, 1'b0, 0);
            simple_check((expected_framing == 1), "bad_stop_framing_model");
            simple_check((out_valid === 1'b0), "bad_stop_no_output");
            run_frame_core(8'hA5, 1'b1, 1);
            simple_check((expected_frames == 257), "bad_recovery_frames_model");
            simple_check((expected_retired == 257), "bad_recovery_retired_model");
            check_stats();
            check_slot();
            end_case();
        end
    endtask

    task automatic case_qualified_idle();
        integer index;
        begin
            begin_case("qualified_idle");
            reset_dut();
            for (index = 0; index < 50; index = index + 1) begin
                @(posedge clk);
                #1;
                simple_check((busy === 1'b0), "held_low_never_starts");
            end
            check_stats();
            run_frame_core(8'h5A, 1'b1, 1);
            simple_check((expected_frames == 1), "qualified_idle_frame");
            simple_check((expected_retired == 1), "qualified_idle_retired");
            check_stats();
            end_case();
        end
    endtask

    task automatic case_false_start();
        begin
            begin_case("false_start");
            reset_dut();
            run_false_start();
            run_frame_core(8'h3C, 1'b1, 1);
            simple_check((expected_false_starts == 1), "false_start_model");
            simple_check((expected_frames == 1), "false_start_recovery_frame");
            check_stats();
            check_slot();
            end_case();
        end
    endtask

    task automatic case_bad_stop_long_low();
        integer index;
        begin
            begin_case("bad_stop_long_low");
            reset_dut();
            run_frame_core(8'h00, 1'b0, 0);
            for (index = 0; index < 200; index = index + 1) begin
                @(posedge clk);
                #1;
                simple_check((busy === 1'b0), "long_low_no_restart");
                check_no_pulses();
            end
            simple_check((expected_framing == 1), "long_low_framing_model");
            simple_check((out_valid === 1'b0), "long_low_no_output");
            run_frame_core(8'h69, 1'b1, 1);
            check_stats();
            end_case();
        end
    endtask

    task automatic case_back_to_back();
        begin
            begin_case("back_to_back");
            reset_dut();
            run_frame_core(8'h11, 1'b1, 1);
            run_frame_core(8'h22, 1'b1, 1);
            simple_check((expected_frames == 2), "back_to_back_frames");
            simple_check((expected_retired == 2), "back_to_back_retired");
            check_stats();
            check_slot();
            end_case();
        end
    endtask

    task automatic case_bad_stop_retire_collision();
        begin
            begin_case("bad_stop_retire_collision");
            reset_dut();
            fill_slot(8'h6D);
            run_frame_core(8'hFF, 1'b0, 2);
            simple_check((expected_frames == 1), "collision_frames_model");
            simple_check((expected_retired == 1), "collision_retired_model");
            simple_check((expected_framing == 1), "collision_framing_model");
            simple_check((out_valid === 1'b0), "collision_no_new_byte");
            run_frame_core(8'h4B, 1'b1, 1);
            simple_check((expected_frames == 2), "collision_recovery_frames");
            simple_check((expected_retired == 2), "collision_recovery_retired");
            check_stats();
            check_slot();
            end_case();
        end
    endtask

    task automatic case_back_to_back_immediate();
        integer phase;
        begin
            begin_case("back_to_back_immediate_stop");
            reset_dut();
            @(negedge clk);
            out_ready = 1'b1;
            #1;

            arm_frame(8'hC3);
            for (phase = 1; phase <= 18; phase = phase + 1) begin
                step_boundary(phase, 8'hC3, 1'b1);
            end
            advance_to_pre(19);

            @(posedge clk);
            #1;
            frame_elapsed = H19;
            expected_frames = golden_inc(expected_frames);
            expected_slot_full = 1'b1;
            expected_slot_data = 8'hC3;
            simple_check((busy === 1'b0), "immediate_first_stop_busy_low");
            check_no_pulses();
            check_stats();
            check_slot();

            // Drive the next start before another rising edge can perform an
            // explicit idle-high qualification.
            @(negedge clk);
            rx_async = 1'b0;
            #1;

            @(posedge clk);
            #1;
            expected_retired = golden_inc(expected_retired);
            expected_slot_full = 1'b0;
            simple_check((busy === 1'b0), "immediate_fall_sync1_idle");
            check_no_pulses();
            check_stats();
            check_slot();

            @(posedge clk);
            #1;
            simple_check((busy === 1'b0), "immediate_fall_sync2_idle");
            check_no_pulses();
            check_stats();
            check_slot();

            @(posedge clk);
            #1;
            simple_check((busy === 1'b1), "immediate_second_start_busy");
            check_no_pulses();
            check_stats();
            check_slot();
            frame_elapsed = 0;
            frame_data = 8'h96;
            frame_stop_good = 1'b1;

            for (phase = 1; phase <= 18; phase = phase + 1) begin
                step_boundary(phase, 8'h96, 1'b1);
            end
            advance_to_pre(19);

            @(posedge clk);
            #1;
            frame_elapsed = H19;
            expected_frames = golden_inc(expected_frames);
            expected_slot_full = 1'b1;
            expected_slot_data = 8'h96;
            simple_check((busy === 1'b0), "immediate_second_stop_busy_low");
            check_no_pulses();
            check_stats();
            check_slot();

            @(posedge clk);
            #1;
            expected_retired = golden_inc(expected_retired);
            expected_slot_full = 1'b0;
            simple_check((out_valid === 1'b0), "immediate_second_drained");
            check_stats();
            check_slot();

            @(negedge clk);
            out_ready = 1'b0;
            #1;
            simple_check((expected_frames == 2), "immediate_frames_model");
            simple_check((expected_retired == 2), "immediate_retired_model");
            end_case();
        end
    endtask

    task automatic case_output_stall();
        begin
            begin_case("output_stall_overrun_refill");
            reset_dut();
            run_frame_core(8'h11, 1'b1, 0);
            simple_check((out_valid === 1'b1), "stall_first_valid");
            simple_check((out_data === 8'h11), "stall_first_data");
            hold_slot_stable(20);
            run_frame_core(8'h22, 1'b1, 0);
            simple_check((expected_overruns == 1), "overrun_model");
            simple_check((out_data === 8'h11), "overrun_preserves_data");
            hold_slot_stable(5);
            drain_slot();
            run_frame_core(8'h33, 1'b1, 0);
            simple_check((out_data === 8'h33), "refill_data");
            run_frame_core(8'h44, 1'b1, 2);
            simple_check((expected_frames == 4), "terminal_frame_model");
            simple_check((expected_retired == 3), "terminal_retire_two_bytes");
            simple_check((expected_slot_full === 1'b0), "terminal_drained");
            run_frame_core(8'h55, 1'b1, 0);
            simple_check((out_data === 8'h55), "second_refill_data");
            drain_slot();
            simple_check((expected_retired == 4), "final_refill_retired");
            check_stats();
            check_slot();
            end_case();
        end
    endtask

    task automatic case_error_preserves_pending();
        begin
            begin_case("error_preserves_pending");
            reset_dut();
            run_frame_core(8'h5A, 1'b1, 0);
            run_frame_core(8'h00, 1'b0, 0);
            simple_check((expected_framing == 1), "pending_framing_model");
            simple_check((out_valid === 1'b1), "pending_survives_error");
            simple_check((out_data === 8'h5A), "pending_data_survives_error");
            hold_slot_stable(3);
            drain_slot();
            check_stats();
            check_slot();
            end_case();
        end
    endtask

    task automatic case_cancel_each_phase();
        integer phase;
        begin
            begin_case("cancel_each_phase_pending");
            for (phase = 1; phase <= 19; phase = phase + 1) begin
                reset_dut();
                fill_slot(8'h21);
                cancel_pending_at_phase(phase, 2, 1'b0);
            end
            simple_check((expected_frames == 1), "cancel_phase_frames_preserved");
            simple_check((expected_retired == 0), "cancel_phase_no_retire");
            simple_check((expected_aborted == 2), "cancel_phase_abort_count");
            check_stats();
            end_case();
        end
    endtask

    task automatic case_reset_each_phase();
        integer phase;
        begin
            begin_case("reset_each_phase_pending");
            for (phase = 1; phase <= 19; phase = phase + 1) begin
                reset_dut();
                fill_slot(8'h31);
                reset_pending_at_phase(phase, 1'b0);
            end
            simple_check((expected_frames == 0), "reset_phase_frames_zero");
            simple_check((expected_aborted == 0), "reset_phase_aborted_zero");
            check_stats();
            check_slot();
            end_case();
        end
    endtask

    task automatic case_idle_cancel_slot();
        begin
            begin_case("idle_cancel_slot");
            reset_dut();
            fill_slot(8'h71);
            cancel_idle_slot();
            simple_check((expected_frames == 1), "idle_cancel_frames_preserved");
            simple_check((expected_aborted == 1), "idle_cancel_one_pending");
            check_stats();
            end_case();
        end
    endtask

    task automatic case_terminal_cancel_ready();
        begin
            begin_case("terminal_cancel_with_ready");
            reset_dut();
            fill_slot(8'h72);
            cancel_pending_at_phase(19, 2, 1'b1);
            simple_check((expected_frames == 1), "terminal_cancel_no_completion");
            simple_check((expected_retired == 0), "terminal_cancel_no_retire");
            simple_check((expected_aborted == 2), "terminal_cancel_abort_count");
            check_stats();
            end_case();
        end
    endtask

    task automatic case_reset_over_cancel();
        begin
            begin_case("reset_over_cancel_pending");
            reset_dut();
            fill_slot(8'h73);
            reset_pending_at_phase(5, 1'b1);
            simple_check((expected_aborted == 0), "reset_priority_no_abort");
            check_stats();
            end_case();
        end
    endtask

    task automatic case_held_abort_pending();
        begin
            begin_case("held_abort_pending");
            reset_dut();
            fill_slot(8'h74);
            cancel_pending_at_phase(7, 5, 1'b0);
            simple_check((expected_frames == 1), "held_abort_frames_preserved");
            simple_check((expected_aborted == 2), "held_abort_counted_once");
            check_stats();
            end_case();
        end
    endtask

    task automatic case_stat_saturation();
        integer index;
        begin
            begin_case("saturation");
            reset_dut();
            for (index = 0; index < 4; index = index + 1) begin
                run_frame_core(8'h10 + index[7:0], 1'b1, 1);
            end
            simple_check((stat_frames === 2'd3), "stat2_frames_saturate_after_completion");
            simple_check((stat_retired === 2'd3), "stat2_retired_saturate_after_completion");
            run_frame_core(8'h40, 1'b1, 0);
            for (index = 0; index < 4; index = index + 1) begin
                run_frame_core(8'h41 + index[7:0], 1'b1, 0);
            end
            simple_check((stat_overruns === 2'd3), "stat2_overruns_saturate");
            for (index = 0; index < 4; index = index + 1) begin
                run_frame_core(8'h00, 1'b0, 0);
            end
            simple_check((stat_framing === 2'd3), "stat2_framing_saturate");
            for (index = 0; index < 4; index = index + 1) begin
                run_false_start();
            end
            simple_check((stat_false_starts === 2'd3), "stat2_false_starts_saturate");
            cancel_pending_at_phase(5, 1, 1'b0);
            run_frame_core(8'h50, 1'b1, 0);
            cancel_pending_at_phase(9, 1, 1'b0);
            simple_check((stat_aborted === 2'd3), "stat2_aborted_saturate");
            check_stats();
            check_slot();
            end_case();
        end
    endtask

    task automatic case_default_frames();
        begin
            begin_case("default_frames");
            run_frame_core(8'h55, 1'b1, 1);
            run_frame_core(8'hAA, 1'b1, 1);
            simple_check((expected_frames == 2), "default_frames_model");
            simple_check((expected_retired == 2), "default_retired_model");
            check_stats();
            end_case();
        end
    endtask

    task automatic case_baud300_frame();
        begin
            begin_case("baud300_frame");
            run_frame_core(8'h5A, 1'b1, 1);
            simple_check((expected_frames == 1), "baud300_frame_model");
            simple_check((expected_retired == 1), "baud300_retired_model");
            check_stats();
            end_case();
        end
    endtask

    task automatic case_baud1200_frames();
        begin
            begin_case("baud1200_frames");
            run_frame_core(8'h00, 1'b1, 1);
            run_frame_core(8'hFF, 1'b1, 1);
            simple_check((expected_frames == 2), "baud1200_frame_model");
            simple_check((expected_retired == 2), "baud1200_retired_model");
            check_stats();
            end_case();
        end
    endtask

    task automatic finish_tb();
        begin
            if (current_case != "") begin
                failures = failures + 1;
                $display("CHECK_FAIL name=no_open_case_at_finish");
            end
            $display("TB_STAT frames=%0d", stat_frames);
            $display("TB_STAT retired=%0d", stat_retired);
            $display("TB_STAT overruns=%0d", stat_overruns);
            $display("TB_STAT framing=%0d", stat_framing);
            $display("TB_STAT false_starts=%0d", stat_false_starts);
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
                case_all_bytes();
                case_bad_stop_recovery();
            end
            P_PROTOCOL: begin
                case_qualified_idle();
                case_false_start();
                case_bad_stop_long_low();
                case_bad_stop_retire_collision();
                case_back_to_back();
                case_back_to_back_immediate();
                case_output_stall();
                case_error_preserves_pending();
            end
            P_ABORT: begin
                case_cancel_each_phase();
                case_reset_each_phase();
                case_idle_cancel_slot();
                case_terminal_cancel_ready();
                case_reset_over_cancel();
                case_held_abort_pending();
            end
            P_STAT_W2: begin
                case_stat_saturation();
            end
            P_DEFAULT: begin
                case_default_frames();
            end
            P_BAUD_300: begin
                case_baud300_frame();
            end
            P_BAUD_1200: begin
                case_baud1200_frames();
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

module tb_uart_rx_all_160_10;
    tb_uart_rx_harness #(
        .CLOCK_HZ(160),
        .BAUD(10),
        .STAT_W(32),
        .PROFILE(0),
        .NAME("tb_uart_rx_all_160_10")
    ) env ();
endmodule

module tb_uart_rx_all_1000_53;
    tb_uart_rx_harness #(
        .CLOCK_HZ(1000),
        .BAUD(53),
        .STAT_W(32),
        .PROFILE(0),
        .NAME("tb_uart_rx_all_1000_53")
    ) env ();
endmodule

module tb_uart_rx_all_97_5;
    tb_uart_rx_harness #(
        .CLOCK_HZ(97),
        .BAUD(5),
        .STAT_W(32),
        .PROFILE(0),
        .NAME("tb_uart_rx_all_97_5")
    ) env ();
endmodule

module tb_uart_rx_protocol;
    tb_uart_rx_harness #(
        .CLOCK_HZ(160),
        .BAUD(10),
        .STAT_W(32),
        .PROFILE(1),
        .NAME("tb_uart_rx_protocol")
    ) env ();
endmodule

module tb_uart_rx_abort;
    tb_uart_rx_harness #(
        .CLOCK_HZ(160),
        .BAUD(10),
        .STAT_W(32),
        .PROFILE(2),
        .NAME("tb_uart_rx_abort")
    ) env ();
endmodule

module tb_uart_rx_stat_w2_min;
    tb_uart_rx_harness #(
        .CLOCK_HZ(16),
        .BAUD(1),
        .STAT_W(2),
        .PROFILE(3),
        .NAME("tb_uart_rx_stat_w2_min")
    ) env ();
endmodule

module tb_uart_rx_default_9600;
    tb_uart_rx_harness #(
        .CLOCK_HZ(100000000),
        .BAUD(9600),
        .STAT_W(32),
        .PROFILE(4),
        .NAME("tb_uart_rx_default_9600")
    ) env ();
endmodule

module tb_uart_rx_baud_300;
    tb_uart_rx_harness #(
        .CLOCK_HZ(100000000),
        .BAUD(300),
        .STAT_W(32),
        .PROFILE(5),
        .NAME("tb_uart_rx_baud_300")
    ) env ();
endmodule

module tb_uart_rx_baud_1200;
    tb_uart_rx_harness #(
        .CLOCK_HZ(100000000),
        .BAUD(1200),
        .STAT_W(32),
        .PROFILE(6),
        .NAME("tb_uart_rx_baud_1200")
    ) env ();
endmodule

`ifndef G_CLOCK
`define G_CLOCK 160
`endif
`ifndef G_BAUD
`define G_BAUD 10
`endif
`ifndef G_STAT_W
`define G_STAT_W 32
`endif

module tb_uart_rx_guard;
    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic rx_async = 1'b1;
    logic out_ready = 1'b0;
    logic out_valid;
    logic [7:0] out_data;
    logic busy;
    logic framing_error_event;
    logic overrun_event;
    logic false_start_event;

    deepeye_uart_rx #(
        .CLOCK_HZ(`G_CLOCK),
        .BAUD(`G_BAUD),
        .STAT_W(`G_STAT_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .rx_async(rx_async),
        .out_ready(out_ready),
        .out_valid(out_valid),
        .out_data(out_data),
        .busy(busy),
        .framing_error_event(framing_error_event),
        .overrun_event(overrun_event),
        .false_start_event(false_start_event),
        .stat_frames(),
        .stat_retired(),
        .stat_overruns(),
        .stat_framing(),
        .stat_false_starts(),
        .stat_aborted()
    );

    initial begin
        #100;
        $display("GUARD_TB_UNEXPECTED_NO_FATAL");
        $finish;
    end
endmodule
