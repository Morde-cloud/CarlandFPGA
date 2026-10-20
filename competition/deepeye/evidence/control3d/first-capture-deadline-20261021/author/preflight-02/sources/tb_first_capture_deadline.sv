`timescale 1ns/1ps

// Independent behavioral reference for the author testbench. It is deliberately
// written with a state enum and a case statement, and it never inspects the DUT
// hierarchy or any DUT output. The testbench compares only public outputs.
module fc_deadline_reference #(
    parameter integer BUDGET_W = 32,
    localparam integer BUDGET_AW = (BUDGET_W < 1) ? 1 :
                                   ((BUDGET_W > 32) ? 32 : BUDGET_W)
) (
    input  logic                 clk,
    input  logic                 rst,
    input  logic                 cancel,
    input  logic                 start,
    input  logic                 observed,
    input  logic [BUDGET_AW-1:0] budget_cycles,
    output logic                 waiting,
    output logic                 completed,
    output logic                 expired,
    output logic                 invalid_request,
    output logic                 started_event,
    output logic                 completed_event,
    output logic                 expired_event,
    output logic                 invalid_request_event
);
    typedef enum logic [2:0] {
        REF_IDLE      = 3'd0,
        REF_WAIT      = 3'd1,
        REF_COMPLETED = 3'd2,
        REF_EXPIRED   = 3'd3,
        REF_INVALID   = 3'd4
    } ref_state_t;

    ref_state_t state_q;
    integer     remaining_q;
    logic       started_q;
    logic       completed_ev_q;
    logic       expired_ev_q;
    logic       invalid_ev_q;

    assign waiting               = (state_q == REF_WAIT);
    assign completed             = (state_q == REF_COMPLETED);
    assign expired               = (state_q == REF_EXPIRED);
    assign invalid_request       = (state_q == REF_INVALID);
    assign started_event         = started_q;
    assign completed_event       = completed_ev_q;
    assign expired_event         = expired_ev_q;
    assign invalid_request_event = invalid_ev_q;

    always_ff @(posedge clk) begin
        started_q     <= 1'b0;
        completed_ev_q <= 1'b0;
        expired_ev_q  <= 1'b0;
        invalid_ev_q  <= 1'b0;

        if (rst || cancel) begin
            state_q     <= REF_IDLE;
            remaining_q <= 0;
        end else begin
            case (state_q)
                REF_WAIT: begin
                    if (start) begin
                        state_q     <= REF_INVALID;
                        remaining_q <= 0;
                        invalid_ev_q <= 1'b1;
                    end else if (observed) begin
                        state_q      <= REF_COMPLETED;
                        remaining_q  <= 0;
                        completed_ev_q <= 1'b1;
                    end else if (remaining_q == 0) begin
                        state_q     <= REF_EXPIRED;
                        remaining_q <= 0;
                        expired_ev_q <= 1'b1;
                    end else begin
                        remaining_q <= remaining_q - 1;
                    end
                end
                default: begin
                    if (start) begin
                        if (budget_cycles == '0) begin
                            state_q      <= REF_INVALID;
                            remaining_q  <= 0;
                            invalid_ev_q <= 1'b1;
                        end else begin
                            state_q      <= REF_WAIT;
                            remaining_q  <= budget_cycles - 1'b1;
                            started_q    <= 1'b1;
                        end
                    end
                end
            endcase
        end
    end
endmodule


module tb_first_capture_deadline_composition #(
    parameter integer DUT_BUDGET_W = 4
);
    localparam integer BUDGET_AW = (DUT_BUDGET_W < 1) ? 1 :
                                   ((DUT_BUDGET_W > 32) ? 32 : DUT_BUDGET_W);

    logic clk;
    logic rst;
    logic stop;
    logic cfg_valid;
    wire  cfg_ready;
    logic [3:0] cfg_period;
    logic [3:0] cfg_high_yaw;
    logic [3:0] cfg_high_pitch;
    logic [3:0] cfg_high_speed;
    logic [3:0] cfg_tag;
    logic [2:0] sample_levels;
    logic       out_ready;

    wire accepted;
    wire rejected;
    wire applied;
    wire frame_start;
    wire running;
    wire pending;
    wire [2:0] pwm;
    wire [3:0] active_period;
    wire [3:0] active_high_yaw;
    wire [3:0] active_high_pitch;
    wire [3:0] active_high_speed;
    wire [3:0] active_tag;
    wire window_active;
    wire window_started;
    wire capture_armed;
    wire out_valid;
    wire [3:0] out_period;
    wire [3:0] out_high0;
    wire [3:0] out_high1;
    wire [3:0] out_high2;
    wire [7:0] out_start;
    wire [7:0] out_end;
    wire [3:0] out_tag;
    wire [3:0] expected_period;
    wire [3:0] expected_high0;
    wire [3:0] expected_high1;
    wire [3:0] expected_high2;
    wire [3:0] expected_tag;
    wire [3:0] raw_fault_events;
    wire failure_event;
    wire [2:0] failure_code;

    logic [BUDGET_AW-1:0] dut_budget;
    wire dut_cancel;
    wire dut_waiting;
    wire dut_completed;
    wire dut_expired;
    wire dut_invalid_request;
    wire dut_started_event;
    wire dut_completed_event;
    wire dut_expired_event;
    wire dut_invalid_request_event;
    wire ref_waiting;
    wire ref_completed;
    wire ref_expired;
    wire ref_invalid_request;
    wire ref_started_event;
    wire ref_completed_event;
    wire ref_expired_event;
    wire ref_invalid_request_event;

    integer check_count;
    integer failure_count;
    integer scenario_count;
    integer scenario_check_start;
    integer scenario_failure_start;
    integer scenario_checks;
    integer grp_trace;
    string current_id;
    string scenario_status;

    logic pre_window_started;
    logic pre_out_valid;
    logic pre_cancel;
    logic pre_waiting;
    logic pre_completed;
    logic pre_expired;
    logic pre_invalid_request;
    logic post_out_valid;
    logic [3:0] post_raw_fault_events;
    logic post_failure_event;
    logic post_window_active;
    logic [2:0] post_failure_code;

    initial clk = 1'b0;
    always #5 clk = ~clk;

    // EXACT frozen composition wiring. out_ready is deliberately absent from
    // cancel and from observed.
    assign dut_cancel = stop || (cfg_valid && cfg_ready) || pending ||
                        !running || !window_active || failure_event ||
                        (|raw_fault_events);

    deepeye_pwm_applied_capture #(
        .COUNT_W(4),
        .WITNESS_W(8),
        .TAG_W(4)
    ) b15 (
        .clk(clk),
        .rst(rst),
        .stop(stop),
        .cfg_valid(cfg_valid),
        .cfg_ready(cfg_ready),
        .cfg_period(cfg_period),
        .cfg_high_yaw(cfg_high_yaw),
        .cfg_high_pitch(cfg_high_pitch),
        .cfg_high_speed(cfg_high_speed),
        .cfg_tag(cfg_tag),
        .sample_levels(sample_levels),
        .out_ready(out_ready),
        .accepted(accepted),
        .rejected(rejected),
        .applied(applied),
        .frame_start(frame_start),
        .running(running),
        .pending(pending),
        .pwm(pwm),
        .active_period(active_period),
        .active_high_yaw(active_high_yaw),
        .active_high_pitch(active_high_pitch),
        .active_high_speed(active_high_speed),
        .active_tag(active_tag),
        .window_active(window_active),
        .window_started(window_started),
        .capture_armed(capture_armed),
        .out_valid(out_valid),
        .out_period(out_period),
        .out_high0(out_high0),
        .out_high1(out_high1),
        .out_high2(out_high2),
        .out_start(out_start),
        .out_end(out_end),
        .out_tag(out_tag),
        .expected_period(expected_period),
        .expected_high0(expected_high0),
        .expected_high1(expected_high1),
        .expected_high2(expected_high2),
        .expected_tag(expected_tag),
        .raw_fault_events(raw_fault_events),
        .failure_event(failure_event),
        .failure_code(failure_code)
    );

    deepeye_first_capture_deadline #(
        .BUDGET_W(DUT_BUDGET_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(dut_cancel),
        .start(window_started),
        .observed(out_valid),
        .budget_cycles(dut_budget),
        .waiting(dut_waiting),
        .completed(dut_completed),
        .expired(dut_expired),
        .invalid_request(dut_invalid_request),
        .started_event(dut_started_event),
        .completed_event(dut_completed_event),
        .expired_event(dut_expired_event),
        .invalid_request_event(dut_invalid_request_event)
    );

    fc_deadline_reference #(
        .BUDGET_W(DUT_BUDGET_W)
    ) ref (
        .clk(clk),
        .rst(rst),
        .cancel(dut_cancel),
        .start(window_started),
        .observed(out_valid),
        .budget_cycles(dut_budget),
        .waiting(ref_waiting),
        .completed(ref_completed),
        .expired(ref_expired),
        .invalid_request(ref_invalid_request),
        .started_event(ref_started_event),
        .completed_event(ref_completed_event),
        .expired_event(ref_expired_event),
        .invalid_request_event(ref_invalid_request_event)
    );

    task automatic fail_check(input string phase, input string detail);
        begin
            failure_count = failure_count + 1;
            $display("DEEPEYE_FC_CHECK_FAIL width=4 scenario=%s phase=%s %s",
                     current_id, phase, detail);
        end
    endtask

    task automatic compare_outputs(input string phase);
        integer onehot;
        begin
            onehot = 0;
            if (dut_waiting === 1'b1) onehot = onehot + 1;
            if (dut_completed === 1'b1) onehot = onehot + 1;
            if (dut_expired === 1'b1) onehot = onehot + 1;
            if (dut_invalid_request === 1'b1) onehot = onehot + 1;

            check_count = check_count + 9;
            if (dut_waiting !== ref_waiting)
                fail_check(phase, $sformatf("waiting dut=%b ref=%b", dut_waiting, ref_waiting));
            if (dut_completed !== ref_completed)
                fail_check(phase, $sformatf("completed dut=%b ref=%b", dut_completed, ref_completed));
            if (dut_expired !== ref_expired)
                fail_check(phase, $sformatf("expired dut=%b ref=%b", dut_expired, ref_expired));
            if (dut_invalid_request !== ref_invalid_request)
                fail_check(phase, $sformatf("invalid dut=%b ref=%b", dut_invalid_request, ref_invalid_request));
            if (onehot > 1)
                fail_check(phase, $sformatf("state-not-onehot-or-zero count=%0d", onehot));
            if (dut_started_event !== ref_started_event)
                fail_check(phase, $sformatf("started_event dut=%b ref=%b", dut_started_event, ref_started_event));
            if (dut_completed_event !== ref_completed_event)
                fail_check(phase, $sformatf("completed_event dut=%b ref=%b", dut_completed_event, ref_completed_event));
            if (dut_expired_event !== ref_expired_event)
                fail_check(phase, $sformatf("expired_event dut=%b ref=%b", dut_expired_event, ref_expired_event));
            if (dut_invalid_request_event !== ref_invalid_request_event)
                fail_check(phase, $sformatf("invalid_event dut=%b ref=%b", dut_invalid_request_event, ref_invalid_request_event));
        end
    endtask

    task automatic expect_bit(input string label, input logic actual, input logic expected);
        begin
            check_count = check_count + 1;
            if (actual !== expected)
                fail_check("expect", $sformatf("%s actual=%b expected=%b", label, actual, expected));
        end
    endtask

    task automatic expect_nonzero4(input string label, input logic [3:0] actual);
        begin
            check_count = check_count + 1;
            if (actual == 4'b0000)
                fail_check("expect", $sformatf("%s expected nonzero actual=%b", label, actual));
        end
    endtask

    task automatic row(
        input logic rst_i,
        input logic stop_i,
        input logic cfg_valid_i,
        input logic [3:0] cfg_period_i,
        input logic [3:0] cfg_yaw_i,
        input logic [3:0] cfg_pitch_i,
        input logic [3:0] cfg_speed_i,
        input logic [3:0] cfg_tag_i,
        input logic [2:0] sample_i,
        input logic ready_i,
        input logic [BUDGET_AW-1:0] budget_i
    );
        begin
            @(negedge clk);
            rst          = rst_i;
            stop         = stop_i;
            cfg_valid    = cfg_valid_i;
            cfg_period   = cfg_period_i;
            cfg_high_yaw = cfg_yaw_i;
            cfg_high_pitch = cfg_pitch_i;
            cfg_high_speed = cfg_speed_i;
            cfg_tag      = cfg_tag_i;
            sample_levels = sample_i;
            out_ready    = ready_i;
            dut_budget   = budget_i;
            #1;
            pre_window_started = window_started;
            pre_out_valid      = out_valid;
            pre_cancel         = dut_cancel;
            pre_waiting        = dut_waiting;
            pre_completed      = dut_completed;
            pre_expired        = dut_expired;
            pre_invalid_request = dut_invalid_request;
            @(posedge clk);
            #1;
            compare_outputs("post");
            post_out_valid      = out_valid;
            post_raw_fault_events = raw_fault_events;
            post_failure_event  = failure_event;
            post_window_active  = window_active;
            post_failure_code   = failure_code;
        end
    endtask

    task automatic begin_trace(input string id, input integer budget_v);
        begin
            current_id = id;
            scenario_check_start = check_count;
            scenario_failure_start = failure_count;
            grp_trace = grp_trace + 1;
        end
    endtask

    task automatic end_trace(input integer budget_v);
        begin
            scenario_checks = check_count - scenario_check_start;
            if (failure_count == scenario_failure_start)
                scenario_status = "pass";
            else
                scenario_status = "fail";
            $display("DEEPEYE_FC_SCENARIO id=%s width=4 group=trace budget=%0d obs=0 checks=%0d status=%s",
                     current_id, budget_v, scenario_checks, scenario_status);
            scenario_count = scenario_count + 1;
        end
    endtask

    task automatic trace_good(input integer budget_v);
        begin
            begin_trace($sformatf("good-N%0d", budget_v), budget_v);
            row(1'b1, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, '0);
            row(1'b1, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, '0);
            expect_bit("row0-window_started", window_started, 1'b0);
            row(1'b0, 1'b0, 1'b1, 4'd2, 4'd1, 4'd1, 4'd1, 4'd3, 3'b000, 1'b1, budget_v);
            expect_bit("row1-accepted", accepted, 1'b1);
            row(1'b0, 1'b0, 1'b0, 4'd2, 4'd1, 4'd1, 4'd1, 4'd3, 3'b000, 1'b1, budget_v);
            expect_bit("row2-applied", applied, 1'b1);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, budget_v);
            expect_bit("row3-window_started", window_started, 1'b1);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b111, 1'b1, budget_v);
            expect_bit("row4-start-pre", pre_window_started, 1'b1);
            expect_bit("row4-started", dut_started_event, 1'b1);
            expect_bit("row4-waiting", dut_waiting, 1'b1);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, budget_v);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b111, 1'b1, budget_v);
            if (budget_v == 2) begin
                expect_bit("N2-row6-expired", dut_expired, 1'b1);
                expect_bit("N2-row6-expired-event", dut_expired_event, 1'b1);
                expect_bit("N2-row6-not-completed", dut_completed, 1'b0);
            end else if (budget_v == 3) begin
                expect_bit("N3-row6-waiting", dut_waiting, 1'b1);
                expect_bit("N3-row6-not-expired", dut_expired, 1'b0);
            end
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b111, 1'b1, budget_v);
            expect_bit("row7-pre-out_valid", pre_out_valid, 1'b1);
            if (budget_v == 2) begin
                expect_bit("N2-row7-late-no-complete", dut_completed, 1'b0);
                expect_bit("N2-row7-still-expired", dut_expired, 1'b1);
            end else if (budget_v == 3) begin
                expect_bit("N3-row7-completed", dut_completed, 1'b1);
                expect_bit("N3-row7-completed-event", dut_completed_event, 1'b1);
            end
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b111, 1'b1, budget_v);
            expect_bit("good-no-raw-fault", (|raw_fault_events), 1'b0);
            expect_bit("good-no-failure", failure_event, 1'b0);
            end_trace(budget_v);
        end
    endtask

    task automatic trace_backpressure_fault();
        begin
            begin_trace("backpressure-fault", 4);
            row(1'b1, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, '0);
            row(1'b1, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, '0);
            row(1'b0, 1'b0, 1'b1, 4'd2, 4'd1, 4'd1, 4'd1, 4'd3, 3'b000, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd2, 4'd1, 4'd1, 4'd1, 4'd3, 3'b000, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b111, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b111, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b110, 1'b0, 4);
            expect_bit("bp-row7-pre-out_valid", pre_out_valid, 1'b1);
            expect_bit("bp-row7-retained-valid", post_out_valid, 1'b1);
            expect_bit("bp-row7-still-waiting", dut_waiting, 1'b1);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b111, 1'b1, 4);
            expect_bit("bp-row8-pre-out_valid", pre_out_valid, 1'b1);
            expect_bit("bp-row8-completed", dut_completed, 1'b1);
            expect_bit("bp-row8-completed-event", dut_completed_event, 1'b1);
            expect_bit("bp-row8-post-out_valid-zero", post_out_valid, 1'b0);
            expect_nonzero4("bp-row8-post-raw-fault", post_raw_fault_events);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b111, 1'b0, 4);
            expect_bit("bp-row9-pre-completed", pre_completed, 1'b1);
            expect_bit("bp-row9-pre-cancel", pre_cancel, 1'b1);
            expect_bit("bp-row9-post-idle-waiting", dut_waiting, 1'b0);
            expect_bit("bp-row9-post-idle-completed", dut_completed, 1'b0);
            expect_bit("bp-row9-failure-event", post_failure_event, 1'b1);
            expect_bit("bp-row9-window-inactive", post_window_active, 1'b0);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b111, 1'b0, 4);
            expect_bit("bp-row10-idle", dut_waiting | dut_completed | dut_expired | dut_invalid_request, 1'b0);
            end_trace(4);
        end
    endtask

    task automatic trace_stop();
        begin
            begin_trace("stop", 4);
            row(1'b1, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, '0);
            row(1'b1, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, '0);
            row(1'b0, 1'b0, 1'b1, 4'd2, 4'd1, 4'd1, 4'd1, 4'd3, 3'b000, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd2, 4'd1, 4'd1, 4'd1, 4'd3, 3'b000, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b111, 1'b1, 4);
            row(1'b0, 1'b1, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, 4);
            expect_bit("stop-pre-cancel", pre_cancel, 1'b1);
            expect_bit("stop-post-idle", dut_waiting | dut_completed | dut_expired | dut_invalid_request, 1'b0);
            expect_bit("stop-running-zero", running, 1'b0);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, 4);
            expect_bit("stop-released-idle", dut_waiting | dut_completed | dut_expired | dut_invalid_request, 1'b0);
            end_trace(4);
        end
    endtask

    task automatic trace_new_cfg();
        begin
            begin_trace("newcfg", 4);
            row(1'b1, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, '0);
            row(1'b1, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, '0);
            row(1'b0, 1'b0, 1'b1, 4'd2, 4'd1, 4'd1, 4'd1, 4'd3, 3'b000, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd2, 4'd1, 4'd1, 4'd1, 4'd3, 3'b000, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b111, 1'b1, 4);
            row(1'b0, 1'b0, 1'b1, 4'd4, 4'd1, 4'd2, 4'd3, 4'd5, 3'b111, 1'b1, 4);
            expect_bit("newcfg-pre-cancel", pre_cancel, 1'b1);
            expect_bit("newcfg-accepted", accepted, 1'b1);
            expect_bit("newcfg-pending", pending, 1'b1);
            expect_bit("newcfg-post-idle", dut_waiting | dut_completed | dut_expired | dut_invalid_request, 1'b0);
            row(1'b0, 1'b0, 1'b0, 4'd4, 4'd1, 4'd2, 4'd3, 4'd5, 3'b111, 1'b1, 4);
            expect_bit("newcfg-no-start", dut_started_event, 1'b0);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b111, 1'b1, 4);
            expect_bit("newcfg-still-idle", dut_waiting | dut_completed | dut_expired | dut_invalid_request, 1'b0);
            end_trace(4);
        end
    endtask

    task automatic trace_failure();
        begin
            begin_trace("failure-event", 4);
            row(1'b1, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, '0);
            row(1'b1, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, '0);
            row(1'b0, 1'b0, 1'b1, 4'd2, 4'd0, 4'd1, 4'd1, 4'd3, 3'b000, 1'b1, 4);
            row(1'b0, 1'b0, 1'b0, 4'd2, 4'd0, 4'd1, 4'd1, 4'd3, 3'b000, 1'b1, 4);
            expect_bit("failure-row2-event", failure_event, 1'b1);
            expect_bit("failure-row2-window-started", window_started, 1'b0);
            expect_bit("failure-row2-dut-idle", dut_waiting | dut_completed | dut_expired | dut_invalid_request, 1'b0);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, 4);
            expect_bit("failure-row3-pre-cancel", pre_cancel, 1'b1);
            expect_bit("failure-row3-still-latched", failure_event, 1'b1);
            row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b1, 4);
            expect_bit("failure-row4-cleared", failure_event, 1'b0);
            expect_bit("failure-final-idle", dut_waiting | dut_completed | dut_expired | dut_invalid_request, 1'b0);
            end_trace(4);
        end
    endtask

    task automatic trace_quiet();
        begin
            begin_trace("quiet", 4);
            row(1'b1, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b0, '0);
            for (integer q = 0; q < 8; q = q + 1) begin
                row(1'b0, 1'b0, 1'b0, 4'd0, 4'd0, 4'd0, 4'd0, 4'd0, 3'b000, 1'b0, 4);
                expect_bit("quiet-idle", dut_waiting | dut_completed | dut_expired | dut_invalid_request, 1'b0);
                expect_bit("quiet-out_valid", out_valid, 1'b0);
                expect_bit("quiet-no-raw-fault", (|raw_fault_events), 1'b0);
            end
            end_trace(4);
        end
    endtask

    initial begin
        rst = 1'b0;
        stop = 1'b0;
        cfg_valid = 1'b0;
        cfg_period = 4'd0;
        cfg_high_yaw = 4'd0;
        cfg_high_pitch = 4'd0;
        cfg_high_speed = 4'd0;
        cfg_tag = 4'd0;
        sample_levels = 3'b000;
        out_ready = 1'b1;
        dut_budget = '0;
        check_count = 0;
        failure_count = 0;
        scenario_count = 0;
        grp_trace = 0;
        current_id = "init";

        $display("DEEPEYE_FC_RUN width=4 kind=composition");
        trace_quiet();
        trace_good(3);
        trace_good(2);
        trace_backpressure_fault();
        trace_stop();
        trace_new_cfg();
        trace_failure();

        $display("DEEPEYE_FC_SUMMARY width=4 kind=composition scenarios=%0d checks=%0d failures=%0d groups=trace:%0d",
                 scenario_count, check_count, failure_count, grp_trace);
        if (failure_count == 0)
            $display("DEEPEYE_FC_FINISH width=4 status=PASS");
        else
            $display("DEEPEYE_FC_FINISH width=4 status=FAIL");
        if (failure_count != 0)
            $fatal(1, "DEEPEYE_FC_BEHAVIOR_FAIL width=4 failures=%0d", failure_count);
        $finish;
    end

endmodule


module tb_first_capture_deadline_guard #(
    parameter integer BUDGET_W = 0
);
    localparam integer BUDGET_AW = (BUDGET_W < 1) ? 1 :
                                   ((BUDGET_W > 32) ? 32 : BUDGET_W);
    logic clk;
    logic rst;
    logic cancel;
    logic start;
    logic observed;
    logic [BUDGET_AW-1:0] budget;
    wire waiting;
    wire completed;
    wire expired;
    wire invalid_request;
    wire started_event;
    wire completed_event;
    wire expired_event;
    wire invalid_request_event;

    initial clk = 1'b0;
    always #5 clk = ~clk;

    deepeye_first_capture_deadline #(
        .BUDGET_W(BUDGET_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .start(start),
        .observed(observed),
        .budget_cycles(budget),
        .waiting(waiting),
        .completed(completed),
        .expired(expired),
        .invalid_request(invalid_request),
        .started_event(started_event),
        .completed_event(completed_event),
        .expired_event(expired_event),
        .invalid_request_event(invalid_request_event)
    );

    initial begin
        rst = 1'b1;
        cancel = 1'b0;
        start = 1'b0;
        observed = 1'b0;
        budget = '0;
        $display("DEEPEYE_FC_RUN width=%0d kind=guard", BUDGET_W);
        #20;
        $display("DEEPEYE_FC_GUARD_UNEXPECTED_ALIVE width=%0d", BUDGET_W);
        $finish;
    end

endmodule


module tb_first_capture_deadline #(
    parameter integer BUDGET_W = 3
);
    localparam integer BUDGET_AW = (BUDGET_W < 1) ? 1 :
                                   ((BUDGET_W > 32) ? 32 : BUDGET_W);

    logic clk;
    logic rst;
    logic cancel;
    logic start;
    logic observed;
    logic [BUDGET_AW-1:0] budget;

    wire waiting;
    wire completed;
    wire expired;
    wire invalid_request;
    wire started_event;
    wire completed_event;
    wire expired_event;
    wire invalid_request_event;

    integer check_count;
    integer failure_count;
    integer scenario_count;
    integer scenario_check_start;
    integer scenario_failure_start;
    integer scenario_checks;

    integer grp_obs;
    integer grp_cancel;
    integer grp_reset;
    integer grp_restart;
    integer grp_priority;
    integer grp_held;
    integer grp_terminal;
    integer grp_latch;
    integer grp_random;
    integer grp_prefix;

    integer max_small;
    integer budget_loop;
    integer position_loop;
    integer kind_loop;
    integer seed_loop;
    integer prefix_loop;
    integer prefix_pos;
    integer prefix_budget;
    integer rng;
    integer k;

    string current_id;
    string current_group;
    string scenario_status;
    string summary_groups;

    initial clk = 1'b0;
    always #5 clk = ~clk;

    deepeye_first_capture_deadline #(
        .BUDGET_W(BUDGET_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .start(start),
        .observed(observed),
        .budget_cycles(budget),
        .waiting(waiting),
        .completed(completed),
        .expired(expired),
        .invalid_request(invalid_request),
        .started_event(started_event),
        .completed_event(completed_event),
        .expired_event(expired_event),
        .invalid_request_event(invalid_request_event)
    );

    wire ref_waiting;
    wire ref_completed;
    wire ref_expired;
    wire ref_invalid_request;
    wire ref_started_event;
    wire ref_completed_event;
    wire ref_expired_event;
    wire ref_invalid_request_event;

    fc_deadline_reference #(
        .BUDGET_W(BUDGET_W)
    ) ref (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .start(start),
        .observed(observed),
        .budget_cycles(budget),
        .waiting(ref_waiting),
        .completed(ref_completed),
        .expired(ref_expired),
        .invalid_request(ref_invalid_request),
        .started_event(ref_started_event),
        .completed_event(ref_completed_event),
        .expired_event(ref_expired_event),
        .invalid_request_event(ref_invalid_request_event)
    );

    task automatic fail_check(input string phase, input string detail);
        begin
            failure_count = failure_count + 1;
            $display("DEEPEYE_FC_CHECK_FAIL width=%0d scenario=%s phase=%s %s",
                     BUDGET_W, current_id, phase, detail);
        end
    endtask

    task automatic compare_outputs(input string phase);
        integer onehot;
        begin
            onehot = 0;
            if (waiting === 1'b1) onehot = onehot + 1;
            if (completed === 1'b1) onehot = onehot + 1;
            if (expired === 1'b1) onehot = onehot + 1;
            if (invalid_request === 1'b1) onehot = onehot + 1;

            check_count = check_count + 9;
            if (waiting !== ref_waiting)
                fail_check(phase, $sformatf("waiting dut=%b ref=%b", waiting, ref_waiting));
            if (completed !== ref_completed)
                fail_check(phase, $sformatf("completed dut=%b ref=%b", completed, ref_completed));
            if (expired !== ref_expired)
                fail_check(phase, $sformatf("expired dut=%b ref=%b", expired, ref_expired));
            if (invalid_request !== ref_invalid_request)
                fail_check(phase, $sformatf("invalid_request dut=%b ref=%b", invalid_request, ref_invalid_request));
            if (onehot > 1)
                fail_check(phase, $sformatf("state-not-onehot-or-zero count=%0d", onehot));
            if (started_event !== ref_started_event)
                fail_check(phase, $sformatf("started_event dut=%b ref=%b", started_event, ref_started_event));
            if (completed_event !== ref_completed_event)
                fail_check(phase, $sformatf("completed_event dut=%b ref=%b", completed_event, ref_completed_event));
            if (expired_event !== ref_expired_event)
                fail_check(phase, $sformatf("expired_event dut=%b ref=%b", expired_event, ref_expired_event));
            if (invalid_request_event !== ref_invalid_request_event)
                fail_check(phase, $sformatf("invalid_request_event dut=%b ref=%b", invalid_request_event, ref_invalid_request_event));
        end
    endtask

    task automatic apply_step(
        input logic rst_i,
        input logic cancel_i,
        input logic start_i,
        input logic observed_i,
        input logic [BUDGET_AW-1:0] budget_i
    );
        begin
            @(negedge clk);
            rst      = rst_i;
            cancel   = cancel_i;
            start    = start_i;
            observed = observed_i;
            budget   = budget_i;
            @(posedge clk);
            #1;
            compare_outputs("post");
        end
    endtask

    task automatic count_group(input string group_name);
        begin
            case (group_name)
                "obs":      grp_obs      = grp_obs + 1;
                "cancel":   grp_cancel   = grp_cancel + 1;
                "reset":    grp_reset    = grp_reset + 1;
                "restart":  grp_restart  = grp_restart + 1;
                "priority": grp_priority = grp_priority + 1;
                "held":     grp_held     = grp_held + 1;
                "terminal": grp_terminal = grp_terminal + 1;
                "latch":    grp_latch    = grp_latch + 1;
                "random":   grp_random   = grp_random + 1;
                "prefix":   grp_prefix   = grp_prefix + 1;
                default: fail_check("group", $sformatf("unknown group %s", group_name));
            endcase
        end
    endtask

    task automatic begin_scenario(input string id, input string group_name);
        begin
            current_id            = id;
            current_group         = group_name;
            scenario_check_start  = check_count;
            scenario_failure_start = failure_count;
            count_group(group_name);
        end
    endtask

    task automatic end_scenario(input integer budget_v, input integer obs_v);
        begin
            scenario_checks = check_count - scenario_check_start;
            if (failure_count == scenario_failure_start)
                scenario_status = "pass";
            else
                scenario_status = "fail";
            $display("DEEPEYE_FC_SCENARIO id=%s width=%0d group=%s budget=%0d obs=%0d checks=%0d status=%s",
                     current_id, BUDGET_W, current_group, budget_v, obs_v,
                     scenario_checks, scenario_status);
            scenario_count = scenario_count + 1;
        end
    endtask

    task automatic scenario_observation(
        input integer budget_v,
        input integer obs_pos,
        input string group_name
    );
        begin
            begin_scenario($sformatf("w%0db%0do%0d", BUDGET_W, budget_v, obs_pos), group_name);
            apply_step(1'b1, 1'b0, 1'b0, 1'b0, budget_v);
            apply_step(1'b0, 1'b0, 1'b1, 1'b0, budget_v);
            for (k = 1; k <= budget_v + 1; k = k + 1) begin
                apply_step(1'b0, 1'b0, 1'b0, (k == obs_pos), budget_v);
            end
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, '0);
            end_scenario(budget_v, obs_pos);
        end
    endtask

    task automatic scenario_cancel_or_reset(
        input integer budget_v,
        input integer position_v,
        input logic use_rst
    );
        begin
            begin_scenario($sformatf("w%0db%0d%s%0d", BUDGET_W, budget_v,
                                    use_rst ? "r" : "c", position_v),
                           use_rst ? "reset" : "cancel");
            if (position_v == 0) begin
                apply_step(use_rst, !use_rst, 1'b1, 1'b1, budget_v);
            end else begin
                apply_step(1'b0, 1'b0, 1'b1, 1'b0, budget_v);
                for (k = 1; k <= budget_v + 1; k = k + 1) begin
                    apply_step(use_rst && (k == position_v),
                               (!use_rst) && (k == position_v),
                               1'b0, 1'b0, budget_v);
                end
            end
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, '0);
            apply_step(1'b0, 1'b0, 1'b1, 1'b0, budget_v);
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, '0);
            end_scenario(budget_v, position_v);
        end
    endtask

    task automatic scenario_restart(input integer budget_v, input integer position_v);
        begin
            begin_scenario($sformatf("w%0db%0dst%0d", BUDGET_W, budget_v, position_v),
                           "restart");
            apply_step(1'b1, 1'b0, 1'b0, 1'b0, budget_v);
            apply_step(1'b0, 1'b0, 1'b1, 1'b0, budget_v);
            for (k = 1; k <= budget_v + 1; k = k + 1) begin
                apply_step(1'b0, 1'b0, (k == position_v), (k == position_v), budget_v);
            end
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, '0);
            apply_step(1'b0, 1'b0, 1'b1, 1'b0, budget_v);
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, '0);
            end_scenario(budget_v, position_v);
        end
    endtask

    task automatic scenario_priority(input integer kind_v);
        begin
            begin_scenario($sformatf("w%0dprio%0d", BUDGET_W, kind_v), "priority");
            apply_step(1'b1, 1'b0, 1'b0, 1'b0, 2);
            case (kind_v)
                0: begin
                    apply_step(1'b0, 1'b1, 1'b1, 1'b1, 2);
                    apply_step(1'b0, 1'b0, 1'b0, 1'b1, 2);
                end
                1: begin
                    apply_step(1'b1, 1'b0, 1'b1, 1'b1, 2);
                    apply_step(1'b0, 1'b0, 1'b0, 1'b1, 2);
                end
                2: begin
                    apply_step(1'b0, 1'b0, 1'b1, 1'b1, 2);
                    apply_step(1'b0, 1'b0, 1'b0, 1'b1, 2);
                end
                3: begin
                    apply_step(1'b0, 1'b0, 1'b1, 1'b0, 3);
                    apply_step(1'b0, 1'b0, 1'b1, 1'b1, 3);
                    apply_step(1'b0, 1'b0, 1'b0, 1'b0, 3);
                end
                4: begin
                    apply_step(1'b0, 1'b0, 1'b1, 1'b0, 3);
                    apply_step(1'b0, 1'b1, 1'b0, 1'b1, 3);
                end
                5: begin
                    apply_step(1'b0, 1'b0, 1'b1, 1'b0, 3);
                    apply_step(1'b0, 1'b1, 1'b1, 1'b0, 3);
                end
                6: begin
                    apply_step(1'b0, 1'b0, 1'b1, 1'b0, 1);
                    apply_step(1'b0, 1'b1, 1'b0, 1'b1, 1);
                end
                default: begin
                    apply_step(1'b1, 1'b1, 1'b1, 1'b1, 2);
                end
            endcase
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, '0);
            end_scenario(2, kind_v);
        end
    endtask

    task automatic scenario_held(input integer budget_v, input integer zero_case);
        begin
            begin_scenario($sformatf("w%0dheld%0d", BUDGET_W, zero_case), "held");
            apply_step(1'b1, 1'b0, 1'b0, 1'b0, budget_v);
            for (k = 0; k < 6; k = k + 1) begin
                apply_step(1'b0, 1'b0, 1'b1, (k == 5), budget_v);
            end
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, budget_v);
            end_scenario(budget_v, 0);
        end
    endtask

    task automatic scenario_terminal_zero();
        begin
            begin_scenario($sformatf("w%0dtermzero", BUDGET_W), "terminal");
            apply_step(1'b1, 1'b0, 1'b0, 1'b0, 3);
            apply_step(1'b0, 1'b0, 1'b1, 1'b0, 3);
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, 3);
            apply_step(1'b0, 1'b0, 1'b1, 1'b0, '0);
            apply_step(1'b0, 1'b0, 1'b1, 1'b0, '0);
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, '0);
            apply_step(1'b0, 1'b0, 1'b1, 1'b0, 2);
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, 2);
            end_scenario(0, 0);
        end
    endtask

    task automatic scenario_terminal_restart();
        begin
            begin_scenario($sformatf("w%0dtermrestart", BUDGET_W), "terminal");
            apply_step(1'b1, 1'b0, 1'b0, 1'b0, 2);
            apply_step(1'b0, 1'b0, 1'b1, 1'b0, 2);
            apply_step(1'b0, 1'b0, 1'b0, 1'b0, 2);
            apply_step(1'b0, 1'b0, 1'b0, 1'b0, 2);
            apply_step(1'b0, 1'b0, 1'b1, 1'b0, 2);
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, 2);
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, 2);
            end_scenario(2, 0);
        end
    endtask

    task automatic scenario_latch(input integer budget_v, input integer complete_case);
        begin
            begin_scenario($sformatf("w%0db%0dlatch%0d", BUDGET_W, budget_v, complete_case),
                           "latch");
            apply_step(1'b1, 1'b0, 1'b0, 1'b0, budget_v);
            apply_step(1'b0, 1'b0, 1'b1, 1'b0, budget_v);
            for (k = 1; k <= budget_v; k = k + 1) begin
                if (k == budget_v)
                    apply_step(1'b0, 1'b0, 1'b0, complete_case, '0);
                else if ((k % 2) == 1)
                    apply_step(1'b0, 1'b0, 1'b0, 1'b0, '0);
                else
                    apply_step(1'b0, 1'b0, 1'b0, 1'b0, '1);
            end
            apply_step(1'b0, 1'b0, 1'b0, 1'b1, '0);
            end_scenario(budget_v, complete_case);
        end
    endtask

    task automatic scenario_random(input integer seed_v);
        begin
            begin_scenario($sformatf("w%0drnd%0d", BUDGET_W, seed_v), "random");
            rng = seed_v;
            apply_step(1'b1, 1'b0, 1'b0, 1'b0, '0);
            for (k = 0; k < 64; k = k + 1) begin
                apply_step((rng[0] & rng[1] & rng[2] & rng[3]),
                           (rng[4] & rng[5] & rng[6] & rng[7]),
                           (rng[8] & rng[9]),
                           (rng[10] & rng[11]),
                           rng);
                rng = {rng[30:0], rng[31] ^ rng[21] ^ rng[1] ^ rng[0]};
            end
            end_scenario(0, 0);
        end
    endtask

    initial begin
        rst      = 1'b0;
        cancel   = 1'b0;
        start    = 1'b0;
        observed = 1'b0;
        budget   = '0;
        check_count    = 0;
        failure_count  = 0;
        scenario_count = 0;
        grp_obs = 0; grp_cancel = 0; grp_reset = 0; grp_restart = 0;
        grp_priority = 0; grp_held = 0; grp_terminal = 0; grp_latch = 0;
        grp_random = 0; grp_prefix = 0;
        current_id = "init";
        current_group = "init";

        $display("DEEPEYE_FC_RUN width=%0d kind=standalone", BUDGET_W);

        if (BUDGET_W <= 5) begin
            max_small = (1 << BUDGET_W) - 1;
            for (budget_loop = 1; budget_loop <= max_small; budget_loop = budget_loop + 1) begin
                for (position_loop = 0; position_loop <= budget_loop + 1; position_loop = position_loop + 1) begin
                    scenario_observation(budget_loop, position_loop, "obs");
                end
            end
            for (budget_loop = 1; budget_loop <= max_small; budget_loop = budget_loop + 1) begin
                for (position_loop = 0; position_loop <= budget_loop + 1; position_loop = position_loop + 1) begin
                    scenario_cancel_or_reset(budget_loop, position_loop, 1'b0);
                    scenario_cancel_or_reset(budget_loop, position_loop, 1'b1);
                end
            end
            for (budget_loop = 1; budget_loop <= max_small; budget_loop = budget_loop + 1) begin
                for (position_loop = 1; position_loop <= budget_loop + 1; position_loop = position_loop + 1) begin
                    scenario_restart(budget_loop, position_loop);
                end
            end
            for (kind_loop = 0; kind_loop <= 7; kind_loop = kind_loop + 1) begin
                scenario_priority(kind_loop);
            end
            scenario_held(3, 0);
            scenario_held(0, 1);
            scenario_terminal_zero();
            scenario_terminal_restart();
            for (budget_loop = 1; budget_loop <= max_small; budget_loop = budget_loop + 1) begin
                scenario_latch(budget_loop, 1);
                scenario_latch(budget_loop, 0);
            end
            for (seed_loop = 0; seed_loop < 100; seed_loop = seed_loop + 1) begin
                scenario_random(32'hC0DE0000 + (BUDGET_W * 32'h1000) + seed_loop);
            end
            summary_groups = $sformatf("obs:%0d,cancel:%0d,reset:%0d,restart:%0d,priority:%0d,held:%0d,terminal:%0d,latch:%0d,random:%0d",
                                       grp_obs, grp_cancel, grp_reset, grp_restart,
                                       grp_priority, grp_held, grp_terminal, grp_latch,
                                       grp_random);
        end else begin
            for (prefix_loop = 0; prefix_loop < 8; prefix_loop = prefix_loop + 1) begin
                case (prefix_loop)
                    0: prefix_budget = 1;
                    1: prefix_budget = 2;
                    2: prefix_budget = 3;
                    3: prefix_budget = 31;
                    4: prefix_budget = 32;
                    5: prefix_budget = 33;
                    6: prefix_budget = 100;
                    default: prefix_budget = 255;
                endcase
                scenario_observation(prefix_budget, 0, "prefix");
                scenario_observation(prefix_budget, 1, "prefix");
                scenario_observation(prefix_budget, prefix_budget, "prefix");
                scenario_observation(prefix_budget, prefix_budget + 1, "prefix");
            end
            summary_groups = $sformatf("prefix:%0d", grp_prefix);
        end

        $display("DEEPEYE_FC_SUMMARY width=%0d kind=standalone scenarios=%0d checks=%0d failures=%0d groups=%s",
                 BUDGET_W, scenario_count, check_count, failure_count, summary_groups);
        if (failure_count == 0)
            $display("DEEPEYE_FC_FINISH width=%0d status=PASS", BUDGET_W);
        else
            $display("DEEPEYE_FC_FINISH width=%0d status=FAIL", BUDGET_W);
        if (failure_count != 0)
            $fatal(1, "DEEPEYE_FC_BEHAVIOR_FAIL width=%0d failures=%0d", BUDGET_W, failure_count);
        $finish;
    end

endmodule
