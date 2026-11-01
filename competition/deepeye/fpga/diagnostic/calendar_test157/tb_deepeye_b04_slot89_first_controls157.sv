`timescale 1ns/1ps
`default_nettype none

module tb_deepeye_b04_slot89_first_controls157;
    localparam logic [255:0] PROFILE_SHA256 =
        256'hb7abdd50d04337c4526ae43de6912c9b7f05e9803e79a519dd4fd7528edc3b46;
    localparam logic [255:0] PROFILE_SHA256_BAD =
        256'hb7abdd50d04337c4526ae43de6912c9b7f05e9803e79a519dd4fd7528edc3b47;

    localparam logic [63:0] FAST_ORIGIN_NS   = 64'd10_000_000_000;
    localparam logic [63:0] FAST_NOW_NS      = 64'd9_990_000_000;
    localparam logic [63:0] FAST_DEADLINE_NS = 64'd10_500_000_000;
    localparam logic [63:0] FAST_WINDOW_NS   = 64'd500_000_000;
    localparam logic [63:0] FAST_GUARD_NS    = 64'd40_000_000;

    localparam logic [63:0] STRESS_ORIGIN_NS   = 64'd20_000_000_000;
    localparam logic [63:0] STRESS_NOW_NS      = 64'd19_990_000_000;
    localparam logic [63:0] STRESS_DEADLINE_NS = 64'd28_000_000_000;
    localparam logic [63:0] STRESS_WINDOW_NS   = 64'd8_000_000_000;
    localparam logic [63:0] STRESS_GUARD_NS    = 64'd200_000_000;

    localparam logic [63:0] MAX_U63_NS = 64'h7fff_ffff_ffff_ffff;
    localparam integer MAX_GLOBAL_CYCLES = 20000;
    localparam integer EXECUTABLE_CASES = 46;
    localparam integer MANUAL_CASES = 47;
    localparam integer REVIEW_ONLY_CASES = 1;

    logic clk;
    logic rst;
    logic enable;
    logic arm;
    logic cancel;
    logic clear_fault;
    logic [63:0] now_ns;
    logic downstream_quiescent;

    logic token_valid;
    logic token_ready;
    logic [63:0] token_id;
    logic [63:0] token_desc;
    logic [1:0] token_class;
    logic [15:0] token_cost;
    logic [1:0] token_profile_id;
    logic [3:0] token_role;
    logic [63:0] window_origin_ns;
    logic [63:0] deadline_ns;
    logic [255:0] token_profile_sha256;
    logic [15:0] token_grant_mask;
    logic token_first_ack_ok;

    logic in_valid;
    logic in_ready;
    logic [63:0] in_desc;
    logic [1:0] in_class;
    logic [15:0] in_cost;

    logic out_valid;
    logic out_ready;
    logic [63:0] out_desc;
    logic [1:0] out_class;
    logic [15:0] out_cost;

    logic armed;
    logic fault_valid;
    logic [3:0] fault_code;
    logic [63:0] fault_token_id;
    logic forward_pulse;
    logic [63:0] forwarded_token_id;
    logic [7:0] used_roles;
    logic [15:0] credits_remaining;
    logic [2:0] count_q0;
    logic [2:0] count_q1;
    logic [2:0] count_q2;
    logic [31:0] accepted_count;
    logic [31:0] sent_count;
    logic [31:0] flushed_count;

    integer status_fd;
    string status_path;
    string active_case;
    string active_manual;
    integer checked_cases;
    integer cycle_count;
    integer saved_flush_count;
    integer saved_sent_count;
    integer saved_accept_count;

    deepeye_nominal_uplink_slot_gate_candidate dut (
        .clk(clk),
        .rst(rst),
        .enable(enable),
        .arm(arm),
        .cancel(cancel),
        .clear_fault(clear_fault),
        .now_ns(now_ns),
        .downstream_quiescent(downstream_quiescent),
        .token_valid(token_valid),
        .token_ready(token_ready),
        .token_id(token_id),
        .token_desc(token_desc),
        .token_class(token_class),
        .token_cost(token_cost),
        .token_profile_id(token_profile_id),
        .token_role(token_role),
        .window_origin_ns(window_origin_ns),
        .deadline_ns(deadline_ns),
        .profile_sha256(token_profile_sha256),
        .grant_mask(token_grant_mask),
        .first_ack_ok(token_first_ack_ok),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_desc(in_desc),
        .in_class(in_class),
        .in_cost(in_cost),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_desc(out_desc),
        .out_class(out_class),
        .out_cost(out_cost),
        .armed(armed),
        .fault_valid(fault_valid),
        .fault_code(fault_code),
        .fault_token_id(fault_token_id),
        .forward_pulse(forward_pulse),
        .forwarded_token_id(forwarded_token_id),
        .used_roles(used_roles),
        .credits_remaining(credits_remaining),
        .count_q0(count_q0),
        .count_q1(count_q1),
        .count_q2(count_q2),
        .accepted_count(accepted_count),
        .sent_count(sent_count),
        .flushed_count(flushed_count)
    );

    task automatic tb_fail(input string reason);
        begin
            $display("CASE_END case=%s manual_id=%s status=FAIL reason=%s cycle=%0d",
                     active_case, active_manual, reason, cycle_count);
            if (status_fd != 0) begin
                $fwrite(status_fd, "TEST_FAIL case=%s manual_id=%s reason=%s cycle=%0d\n",
                        active_case, active_manual, reason, cycle_count);
                $fclose(status_fd);
                status_fd = 0;
            end
            $fatal(1, "B04_SLOT89_FAIL case=%s manual_id=%s reason=%s",
                   active_case, active_manual, reason);
        end
    endtask

    task automatic case_begin(input string case_name,
                              input string manual_id,
                              input string category);
        begin
            active_case = case_name;
            active_manual = manual_id;
            $display("CASE_BEGIN case=%s manual_id=%s category=%s cycle=%0d",
                     active_case, active_manual, category, cycle_count);
        end
    endtask

    task automatic case_pass(input string detail);
        begin
            checked_cases = checked_cases + 1;
            $display("CASE_END case=%s manual_id=%s status=PASS detail=%s accepted=%0d sent=%0d flushed=%0d cycle=%0d",
                     active_case, active_manual, detail, accepted_count, sent_count,
                     flushed_count, cycle_count);
        end
    endtask

    task automatic inputs_idle();
        begin
            rst = 1'b0;
            enable = 1'b0;
            arm = 1'b0;
            cancel = 1'b0;
            clear_fault = 1'b0;
            now_ns = 64'd0;
            downstream_quiescent = 1'b1;
            token_valid = 1'b0;
            token_id = 64'd0;
            token_desc = 64'd0;
            token_class = 2'd0;
            token_cost = 16'd0;
            token_profile_id = 2'd1;
            token_role = 4'd1;
            window_origin_ns = 64'd0;
            deadline_ns = 64'd0;
            token_profile_sha256 = PROFILE_SHA256;
            token_grant_mask = 16'd0;
            token_first_ack_ok = 1'b0;
            in_valid = 1'b0;
            in_desc = 64'd0;
            in_class = 2'd0;
            in_cost = 16'd0;
            out_ready = 1'b0;
        end
    endtask

    task automatic reset_dut();
        begin
            @(negedge clk);
            inputs_idle();
            rst = 1'b1;
            repeat (3) @(posedge clk);
            @(negedge clk);
            rst = 1'b0;
            repeat (2) @(posedge clk);
            #1;
            if (armed !== 1'b0) tb_fail("reset_armed_not_clear");
            if (fault_valid !== 1'b0) tb_fail("reset_fault_not_clear");
            if (out_valid !== 1'b0) tb_fail("reset_out_valid_not_clear");
            if (forward_pulse !== 1'b0) tb_fail("reset_forward_pulse_not_clear");
            if (credits_remaining !== 16'd0) tb_fail("reset_credits_not_clear");
            if ((count_q0 !== 3'd0) || (count_q1 !== 3'd0) || (count_q2 !== 3'd0))
                tb_fail("reset_queue_count_not_clear");
            if ((accepted_count !== 32'd0) || (sent_count !== 32'd0) ||
                (flushed_count !== 32'd0))
                tb_fail("reset_q012_statistics_not_clear");
        end
    endtask

    task automatic arm_dut(input [63:0] now_value);
        begin
            @(negedge clk);
            enable = 1'b1;
            arm = 1'b0;
            cancel = 1'b0;
            clear_fault = 1'b0;
            now_ns = now_value;
            token_valid = 1'b0;
            in_valid = 1'b0;
            out_ready = 1'b0;
            downstream_quiescent = 1'b1;
            repeat (2) @(posedge clk);
            #1;
            if (armed !== 1'b0) tb_fail("arm_start_not_disarmed");
            if (token_ready !== 1'b0) tb_fail("arm_start_token_ready");
            @(negedge clk);
            arm = 1'b1;
            @(posedge clk);
            #1;
            if (armed !== 1'b1) tb_fail("arm_rising_edge_not_accepted");
            if (fault_valid !== 1'b0) tb_fail("arm_unexpected_fault");
            @(negedge clk);
            arm = 1'b0;
            token_valid = 1'b0;
            @(posedge clk);
            #1;
            if (armed !== 1'b1) tb_fail("arm_not_held_after_collect");
            if (token_ready !== 1'b0) tb_fail("arm_valid_low_not_sampled");
        end
    endtask

    task automatic wait_credits(input [15:0] expected_credits);
        integer wait_index;
        begin : wait_credits_block
            for (wait_index = 0; wait_index < 32; wait_index = wait_index + 1) begin
                @(posedge clk);
                #1;
                if (credits_remaining === expected_credits)
                    disable wait_credits_block;
            end
            tb_fail("credit_load_timeout");
        end
    endtask

    task automatic bind_accept(
        input [63:0] next_token_id,
        input [63:0] next_token_desc,
        input [1:0] next_token_class,
        input [15:0] next_token_cost,
        input [1:0] next_profile_id,
        input [3:0] next_role,
        input [63:0] next_origin_ns,
        input [63:0] next_deadline_ns,
        input [15:0] next_grant_mask,
        input logic next_first_ack_ok,
        input [255:0] next_profile_sha256,
        input [63:0] bind_now_ns
    );
        integer accepted_before;
        integer sent_before;
        begin
            accepted_before = accepted_count;
            sent_before = sent_count;
            @(negedge clk);
            now_ns = bind_now_ns;
            enable = 1'b1;
            cancel = 1'b0;
            clear_fault = 1'b0;
            in_valid = 1'b0;
            out_ready = 1'b0;
            downstream_quiescent = 1'b1;
            token_valid = 1'b1;
            token_id = next_token_id;
            token_desc = next_token_desc;
            token_class = next_token_class;
            token_cost = next_token_cost;
            token_profile_id = next_profile_id;
            token_role = next_role;
            window_origin_ns = next_origin_ns;
            deadline_ns = next_deadline_ns;
            token_profile_sha256 = next_profile_sha256;
            token_grant_mask = next_grant_mask;
            token_first_ack_ok = next_first_ack_ok;
            @(posedge clk);
            if (token_ready !== 1'b1) tb_fail("bind_accept_ready_low");
            #1;
            if (fault_valid !== 1'b0) tb_fail("bind_accept_faulted");
            if (out_valid !== 1'b0) tb_fail("bind_accept_visible_too_early");
            if (accepted_count !== accepted_before) tb_fail("bind_accept_q012_enqueue");
            if (sent_count !== sent_before) tb_fail("bind_accept_forwarded");
            @(negedge clk);
            token_valid = 1'b0;
            @(posedge clk);
            #1;
            if (fault_valid !== 1'b0) tb_fail("bind_accept_post_fault");
            wait_credits(next_token_cost);
        end
    endtask

    task automatic bind_reject(
        input [63:0] next_token_id,
        input [63:0] next_token_desc,
        input [1:0] next_token_class,
        input [15:0] next_token_cost,
        input [1:0] next_profile_id,
        input [3:0] next_role,
        input [63:0] next_origin_ns,
        input [63:0] next_deadline_ns,
        input [15:0] next_grant_mask,
        input logic next_first_ack_ok,
        input [255:0] next_profile_sha256,
        input [63:0] bind_now_ns,
        input [3:0] expected_fault_code,
        input [63:0] expected_fault_token_id
    );
        integer accepted_before;
        integer sent_before;
        begin
            accepted_before = accepted_count;
            sent_before = sent_count;
            @(negedge clk);
            now_ns = bind_now_ns;
            enable = 1'b1;
            cancel = 1'b0;
            clear_fault = 1'b0;
            in_valid = 1'b0;
            out_ready = 1'b0;
            downstream_quiescent = 1'b1;
            token_valid = 1'b1;
            token_id = next_token_id;
            token_desc = next_token_desc;
            token_class = next_token_class;
            token_cost = next_token_cost;
            token_profile_id = next_profile_id;
            token_role = next_role;
            window_origin_ns = next_origin_ns;
            deadline_ns = next_deadline_ns;
            token_profile_sha256 = next_profile_sha256;
            token_grant_mask = next_grant_mask;
            token_first_ack_ok = next_first_ack_ok;
            @(posedge clk);
            if (token_ready !== 1'b0) tb_fail("bind_reject_unexpected_ready");
            #1;
            if (fault_valid !== 1'b1) tb_fail("bind_reject_fault_missing");
            if (fault_code !== expected_fault_code) tb_fail("bind_reject_wrong_fault_code");
            if (fault_token_id !== expected_fault_token_id) tb_fail("bind_reject_wrong_fault_token_id");
            if (out_valid !== 1'b0) tb_fail("bind_reject_visible");
            if (accepted_count !== accepted_before) tb_fail("bind_reject_q012_enqueue");
            if (sent_count !== sent_before) tb_fail("bind_reject_forwarded");
            @(negedge clk);
            token_valid = 1'b0;
            repeat (2) @(posedge clk);
            #1;
            if (fault_valid !== 1'b1) tb_fail("bind_reject_fault_not_sticky");
            if (forward_pulse !== 1'b0) tb_fail("bind_reject_forward_pulse");
        end
    endtask

    task automatic ingress_exact(
        input [63:0] exact_desc,
        input [1:0] exact_class,
        input [15:0] exact_cost
    );
        integer accepted_before;
        integer sent_before;
        begin
            accepted_before = accepted_count;
            sent_before = sent_count;
            @(negedge clk);
            in_valid = 1'b1;
            in_desc = exact_desc;
            in_class = exact_class;
            in_cost = exact_cost;
            @(posedge clk);
            if (in_valid !== 1'b1) tb_fail("ingress_valid_not_stable");
            if (in_ready !== 1'b1) tb_fail("ingress_ready_low");
            #1;
            if (accepted_count !== accepted_before + 1) tb_fail("ingress_accept_count");
            if (sent_count !== sent_before) tb_fail("ingress_forwarded_early");
            if (out_valid !== 1'b0) tb_fail("ingress_visible_before_slot");
            if (fault_valid !== 1'b0) tb_fail("ingress_unexpected_fault");
            @(negedge clk);
            in_valid = 1'b0;
            @(posedge clk);
            #1;
            if (accepted_count !== accepted_before + 1) tb_fail("ingress_multiple_accept");
        end
    endtask

    task automatic ingress_identity_bad(
        input [63:0] bad_desc,
        input [1:0] bad_class,
        input [15:0] bad_cost,
        input [63:0] expected_bound_token_id
    );
        integer accepted_before;
        integer sent_before;
        begin
            accepted_before = accepted_count;
            sent_before = sent_count;
            @(negedge clk);
            in_valid = 1'b1;
            in_desc = bad_desc;
            in_class = bad_class;
            in_cost = bad_cost;
            @(posedge clk);
            if (in_ready !== 1'b0) tb_fail("identity_bad_ready_high");
            #1;
            if (fault_valid !== 1'b1) tb_fail("identity_fault_missing");
            if (fault_code !== 4'd2) tb_fail("identity_wrong_fault_code");
            if (fault_token_id !== expected_bound_token_id)
                tb_fail("identity_wrong_bound_token_id");
            if (accepted_count !== accepted_before) tb_fail("identity_bad_q012_enqueue");
            if (sent_count !== sent_before) tb_fail("identity_bad_forwarded");
            if (out_valid !== 1'b0) tb_fail("identity_bad_out_valid");
            @(negedge clk);
            in_valid = 1'b0;
            repeat (2) @(posedge clk);
            #1;
            if (forward_pulse !== 1'b0) tb_fail("identity_bad_forward_pulse");
        end
    endtask

    task automatic expect_no_outer_valid(input integer cycles);
        integer index;
        begin
            for (index = 0; index < cycles; index = index + 1) begin
                @(posedge clk);
                if (out_valid !== 1'b0) tb_fail("outer_valid_before_slot");
                #1;
                if (out_valid !== 1'b0) tb_fail("outer_valid_after_edge_before_slot");
            end
        end
    endtask

    task automatic fire_exact(
        input [63:0] expected_desc,
        input [1:0] expected_class,
        input [15:0] expected_cost,
        input [63:0] expected_token_id,
        input [63:0] start_ns
    );
        integer sent_before;
        begin
            sent_before = sent_count;
            @(negedge clk);
            now_ns = start_ns;
            out_ready = 1'b1;
            in_valid = 1'b0;
            #1;
            if (out_valid !== 1'b1) tb_fail("fire_out_valid_missing");
            if (out_desc !== expected_desc) tb_fail("fire_desc_mismatch");
            if (out_class !== expected_class) tb_fail("fire_class_mismatch");
            if (out_cost !== expected_cost) tb_fail("fire_cost_mismatch");
            if (fault_valid !== 1'b0) tb_fail("fire_pre_fault");
            @(posedge clk);
            if (out_valid !== 1'b1) tb_fail("fire_edge_out_valid_missing");
            if (out_ready !== 1'b1) tb_fail("fire_edge_ready_missing");
            if (forward_pulse !== 1'b1) tb_fail("fire_forward_pulse_missing");
            #1;
            if (sent_count !== sent_before + 1) tb_fail("fire_sent_count");
            if (credits_remaining !== 16'd0) tb_fail("fire_credits_not_consumed");
            if (forwarded_token_id !== expected_token_id) tb_fail("fire_forwarded_token_id");
            if (fault_valid !== 1'b0) tb_fail("fire_post_fault");
            if (out_valid !== 1'b0) tb_fail("fire_output_not_retired");
            @(negedge clk);
            out_ready = 1'b0;
            repeat (2) @(posedge clk);
            #1;
            if (out_valid !== 1'b0) tb_fail("fire_replay_out_valid");
            if (forward_pulse !== 1'b0) tb_fail("fire_replay_forward_pulse");
            if (sent_count !== sent_before + 1) tb_fail("fire_auto_retry");
        end
    endtask

    task automatic execute_transaction(
        input [63:0] next_token_id,
        input [63:0] next_token_desc,
        input [1:0] next_token_class,
        input [15:0] next_token_cost,
        input [1:0] next_profile_id,
        input [3:0] next_role,
        input [63:0] next_origin_ns,
        input [63:0] bind_now_ns,
        input [63:0] next_deadline_ns,
        input [63:0] start_ns,
        input [15:0] next_grant_mask,
        input logic next_first_ack_ok,
        input [7:0] expected_used_roles
    );
        begin
            arm_dut(bind_now_ns);
            bind_accept(next_token_id, next_token_desc, next_token_class,
                        next_token_cost, next_profile_id, next_role,
                        next_origin_ns, next_deadline_ns, next_grant_mask,
                        next_first_ack_ok, PROFILE_SHA256, bind_now_ns);
            if (used_roles !== expected_used_roles) tb_fail("bind_used_roles");
            @(negedge clk);
            now_ns = start_ns - 64'd1;
            @(posedge clk);
            #1;
            ingress_exact(next_token_desc, next_token_class, next_token_cost);
            expect_no_outer_valid(4);
            @(negedge clk);
            in_desc = ~next_token_desc;
            in_class = 2'd3;
            in_cost = 16'd1;
            expect_no_outer_valid(2);
            fire_exact(next_token_desc, next_token_class, next_token_cost,
                       next_token_id, start_ns);
            if (fault_valid !== 1'b0) tb_fail("transaction_post_fault");
            if (out_valid !== 1'b0) tb_fail("transaction_post_visible");
        end
    endtask

    task automatic prepare_held_transaction(
        input [63:0] next_token_id,
        input [63:0] next_token_desc,
        input [1:0] next_token_class,
        input [15:0] next_token_cost,
        input [1:0] next_profile_id,
        input [3:0] next_role,
        input [63:0] next_origin_ns,
        input [63:0] bind_now_ns,
        input [63:0] next_deadline_ns,
        input [63:0] start_ns,
        input [15:0] next_grant_mask,
        input logic next_first_ack_ok,
        input [7:0] expected_used_roles
    );
        begin
            arm_dut(bind_now_ns);
            bind_accept(next_token_id, next_token_desc, next_token_class,
                        next_token_cost, next_profile_id, next_role,
                        next_origin_ns, next_deadline_ns, next_grant_mask,
                        next_first_ack_ok, PROFILE_SHA256, bind_now_ns);
            if (used_roles !== expected_used_roles) tb_fail("held_used_roles");
            @(negedge clk);
            now_ns = start_ns - 64'd1;
            @(posedge clk);
            #1;
            ingress_exact(next_token_desc, next_token_class, next_token_cost);
            repeat (4) @(posedge clk);
            #1;
            if (out_valid !== 1'b0) tb_fail("held_outer_valid_before_slot");
            if (fault_valid !== 1'b0) tb_fail("held_unexpected_fault");
            if (next_token_class === 2'd0) begin
                if (count_q0 !== 3'd1) tb_fail("held_q0_count_not_one");
            end else if (next_token_class === 2'd1) begin
                if (count_q1 !== 3'd1) tb_fail("held_q1_count_not_one");
            end else begin
                tb_fail("held_unsupported_class");
            end
        end
    endtask

    task automatic wait_flush_delta(input integer flush_before,
                                    input integer expected_delta);
        integer wait_index;
        integer expected_flush;
        begin : wait_flush_block
            expected_flush = flush_before + expected_delta;
            for (wait_index = 0; wait_index < 8; wait_index = wait_index + 1) begin
                @(posedge clk);
                #1;
                if (flushed_count === expected_flush)
                    disable wait_flush_block;
            end
            tb_fail("flush_delta_timeout");
        end
    endtask

    task automatic clear_fault_checked(input [63:0] clear_now_ns);
        begin
            @(negedge clk);
            token_valid = 1'b0;
            cancel = 1'b0;
            in_valid = 1'b0;
            out_ready = 1'b0;
            now_ns = clear_now_ns;
            clear_fault = 1'b1;
            @(posedge clk);
            #1;
            if (fault_valid !== 1'b0) tb_fail("clear_fault_not_accepted");
            if (armed !== 1'b0) tb_fail("clear_auto_armed");
            if (out_valid !== 1'b0) tb_fail("clear_out_valid");
            @(negedge clk);
            clear_fault = 1'b0;
            repeat (2) @(posedge clk);
            #1;
            if (fault_valid !== 1'b0) tb_fail("clear_fault_returned");
            if (armed !== 1'b0) tb_fail("clear_auto_armed_late");
        end
    endtask

    task automatic run_nominal_case(
        input string case_name,
        input string manual_id,
        input [1:0] profile_id,
        input [3:0] role_id,
        input [63:0] next_token_id,
        input [63:0] next_token_desc,
        input [1:0] next_token_class,
        input [15:0] next_token_cost,
        input [15:0] next_grant_mask,
        input logic next_first_ack_ok,
        input [63:0] next_origin_ns,
        input [63:0] bind_now_ns,
        input [63:0] next_deadline_ns,
        input [63:0] start_ns,
        input [7:0] expected_used_roles
    );
        begin
            case_begin(case_name, manual_id, "nominal");
            reset_dut();
            execute_transaction(next_token_id, next_token_desc, next_token_class,
                                next_token_cost, profile_id, role_id,
                                next_origin_ns, bind_now_ns, next_deadline_ns,
                                start_ns, next_grant_mask, next_first_ack_ok,
                                expected_used_roles);
            if (used_roles !== expected_used_roles) tb_fail("nominal_used_roles_late");
            if (fault_valid !== 1'b0) tb_fail("nominal_fault_late");
            case_pass("exact_slot_outer_gated_no_fault");
        end
    endtask

    initial begin
        clk = 1'b0;
        forever begin
            #5 clk = 1'b1;
            #5 clk = 1'b0;
        end
    end

    always @(posedge clk) begin
        cycle_count = cycle_count + 1;
        if (cycle_count > MAX_GLOBAL_CYCLES)
            tb_fail("global_clock_cycle_cap");
    end

    initial begin
        status_fd = 0;
        status_path = "b04_slot89_first_controls157.status";
        checked_cases = 0;
        cycle_count = 0;
        active_case = "INIT";
        active_manual = "NONE";
        inputs_idle();
        $display("TB_START profile_sha256=%h requirements_sha256=%s manual_cases=%0d executable_cases=%0d review_only=%0d",
                 PROFILE_SHA256,
                 "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804",
                 MANUAL_CASES, EXECUTABLE_CASES, REVIEW_ONLY_CASES);
        status_fd = $fopen(status_path, "w");
        if (status_fd == 0) begin
            $fatal(1, "B04_SLOT89_FAIL cannot_open_status_file");
        end
        $fwrite(status_fd, "TEST_INCOMPLETE\n");

        run_nominal_case("F1_NOM_EVENT", "F1-NOM-EVENT", 2'd1, 4'd1,
                         64'd101, 64'h8900000000000001, 2'd0, 16'd20,
                         16'h0000, 1'b0, FAST_ORIGIN_NS, FAST_NOW_NS,
                         FAST_DEADLINE_NS, FAST_ORIGIN_NS + 64'd0, 8'h01);
        run_nominal_case("F1_NOM_TELEM", "F1-NOM-TELEM", 2'd1, 4'd2,
                         64'd102, 64'h8900000000000002, 2'd1, 16'd32,
                         16'h0000, 1'b0, FAST_ORIGIN_NS, FAST_NOW_NS,
                         FAST_DEADLINE_NS, FAST_ORIGIN_NS + 64'd35_000_000, 8'h02);
        run_nominal_case("F1_NOM_ACK_PRIMARY", "F1-NOM-ACK-PRIMARY", 2'd1, 4'd3,
                         64'd103, 64'h8900000000000003, 2'd0, 16'd34,
                         16'h8000, 1'b1, FAST_ORIGIN_NS, FAST_NOW_NS,
                         FAST_DEADLINE_NS, FAST_ORIGIN_NS + 64'd255_000_000, 8'h04);
        run_nominal_case("F1_NOM_STATE3D", "F1-NOM-STATE3D", 2'd1, 4'd4,
                         64'd104, 64'h8900000000000004, 2'd1, 16'd34,
                         16'h0000, 1'b0, FAST_ORIGIN_NS, FAST_NOW_NS,
                         FAST_DEADLINE_NS, FAST_ORIGIN_NS + 64'd305_000_000, 8'h08);
        run_nominal_case("F1_NOM_ACK_RETRY", "F1-NOM-ACK-RETRY", 2'd1, 4'd5,
                         64'd105, 64'h8900000000000005, 2'd0, 16'd34,
                         16'ha000, 1'b0, FAST_ORIGIN_NS, FAST_NOW_NS,
                         FAST_DEADLINE_NS, FAST_ORIGIN_NS + 64'd410_000_000, 8'h10);
        run_nominal_case("F1_NOM_CONFIG_ACK", "F1-NOM-CONFIG-ACK", 2'd1, 4'd6,
                         64'd106, 64'h8900000000000006, 2'd0, 16'd32,
                         16'h4000, 1'b0, FAST_ORIGIN_NS, FAST_NOW_NS,
                         FAST_DEADLINE_NS, FAST_ORIGIN_NS + 64'd405_000_000, 8'h20);
        run_nominal_case("F1_NOM_EVENT_RETRY", "F1-NOM-EVENT-RETRY", 2'd1, 4'd7,
                         64'd107, 64'h8900000000000007, 2'd0, 16'd20,
                         16'h0000, 1'b0, FAST_ORIGIN_NS, FAST_NOW_NS,
                         FAST_DEADLINE_NS, FAST_ORIGIN_NS + 64'd365_000_000, 8'h40);

        run_nominal_case("F2_NOM_EVENT", "F2-NOM-EVENT", 2'd2, 4'd1,
                         64'd201, 64'h8900000000000101, 2'd0, 16'd20,
                         16'h0000, 1'b0, STRESS_ORIGIN_NS, STRESS_NOW_NS,
                         STRESS_DEADLINE_NS, STRESS_ORIGIN_NS + 64'd0, 8'h01);
        run_nominal_case("F2_NOM_TELEM", "F2-NOM-TELEM", 2'd2, 4'd2,
                         64'd202, 64'h8900000000000102, 2'd1, 16'd32,
                         16'h0000, 1'b0, STRESS_ORIGIN_NS, STRESS_NOW_NS,
                         STRESS_DEADLINE_NS, STRESS_ORIGIN_NS + 64'd700_000_000, 8'h02);
        run_nominal_case("F2_NOM_ACK_PRIMARY", "F2-NOM-ACK-PRIMARY", 2'd2, 4'd3,
                         64'd203, 64'h8900000000000103, 2'd0, 16'd34,
                         16'h8000, 1'b1, STRESS_ORIGIN_NS, STRESS_NOW_NS,
                         STRESS_DEADLINE_NS, STRESS_ORIGIN_NS + 64'd3_100_000_000, 8'h04);
        run_nominal_case("F2_NOM_STATE3D", "F2-NOM-STATE3D", 2'd2, 4'd4,
                         64'd204, 64'h8900000000000104, 2'd1, 16'd34,
                         16'h0000, 1'b0, STRESS_ORIGIN_NS, STRESS_NOW_NS,
                         STRESS_DEADLINE_NS, STRESS_ORIGIN_NS + 64'd4_300_000_000, 8'h08);
        run_nominal_case("F2_NOM_ACK_RETRY", "F2-NOM-ACK-RETRY", 2'd2, 4'd5,
                         64'd205, 64'h8900000000000105, 2'd0, 16'd34,
                         16'ha000, 1'b0, STRESS_ORIGIN_NS, STRESS_NOW_NS,
                         STRESS_DEADLINE_NS, STRESS_ORIGIN_NS + 64'd6_550_000_000, 8'h10);
        run_nominal_case("F2_NOM_CONFIG_ACK", "F2-NOM-CONFIG-ACK", 2'd2, 4'd6,
                         64'd206, 64'h8900000000000106, 2'd0, 16'd32,
                         16'h4000, 1'b0, STRESS_ORIGIN_NS, STRESS_NOW_NS,
                         STRESS_DEADLINE_NS, STRESS_ORIGIN_NS + 64'd6_550_000_000, 8'h20);
        run_nominal_case("F2_NOM_EVENT_RETRY", "F2-NOM-EVENT-RETRY", 2'd2, 4'd7,
                         64'd207, 64'h8900000000000107, 2'd0, 16'd20,
                         16'h0000, 1'b0, STRESS_ORIGIN_NS, STRESS_NOW_NS,
                         STRESS_DEADLINE_NS, STRESS_ORIGIN_NS + 64'd5_500_000_000, 8'h40);

        case_begin("FIRST_ACK_RETRY_SUPPRESS", "FIRST-ACK-RETRY-SUPPRESS", "negative_grant");
        reset_dut();
        arm_dut(FAST_NOW_NS);
        bind_reject(64'd301, 64'h8900000000000301, 2'd0, 16'd34,
                    2'd1, 4'd5, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'ha000, 1'b1, PROFILE_SHA256, FAST_NOW_NS,
                    4'd1, 64'd301);
        if (used_roles !== 8'h00) tb_fail("first_ack_retry_used_roles");
        case_pass("first_ack_retry_suppressed_fault1");

        case_begin("CONFIG_RETRY_MUTEX", "CONFIG-RETRY-MUTEX", "mutual_exclusion");
        reset_dut();
        execute_transaction(64'd302, 64'h8900000000000302, 2'd0, 16'd32,
                            2'd1, 4'd6, FAST_ORIGIN_NS, FAST_NOW_NS,
                            FAST_DEADLINE_NS, FAST_ORIGIN_NS + 64'd405_000_000,
                            16'h4000, 1'b0, 8'h20);
        bind_reject(64'd303, 64'h8900000000000303, 2'd0, 16'd34,
                    2'd1, 4'd5, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'ha000, 1'b0, PROFILE_SHA256,
                    FAST_ORIGIN_NS + 64'd406_000_000, 4'd7, 64'd303);
        case_pass("config_then_retry_mutex_fault7");

        case_begin("ROLE_CLASS_MISMATCH", "ROLE-CLASS-MISMATCH", "negative_identity");
        reset_dut();
        arm_dut(FAST_NOW_NS);
        bind_reject(64'd304, 64'h8900000000000304, 2'd0, 16'd32,
                    2'd1, 4'd2, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h0000, 1'b0, PROFILE_SHA256, FAST_NOW_NS,
                    4'd1, 64'd304);
        case_pass("telem_class_mismatch_fault1");

        case_begin("ROLE_COST_MISMATCH", "ROLE-COST-MISMATCH", "negative_identity");
        reset_dut();
        arm_dut(FAST_NOW_NS);
        bind_reject(64'd305, 64'h8900000000000305, 2'd1, 16'd31,
                    2'd1, 4'd2, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h0000, 1'b0, PROFILE_SHA256, FAST_NOW_NS,
                    4'd1, 64'd305);
        case_pass("telem_cost_mismatch_fault1");

        case_begin("PROFILE_HASH_MISMATCH", "PROFILE-HASH-MISMATCH", "negative_hash");
        reset_dut();
        arm_dut(FAST_NOW_NS);
        bind_reject(64'd306, 64'h8900000000000306, 2'd0, 16'd20,
                    2'd1, 4'd1, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h0000, 1'b0, PROFILE_SHA256_BAD, FAST_NOW_NS,
                    4'd1, 64'd306);
        case_pass("profile_hash_mismatch_fault1");

        case_begin("PROFILE_SWITCH_WITHOUT_RESET", "PROFILE-SWITCH-WITHOUT-RESET", "profile_lock");
        reset_dut();
        execute_transaction(64'd307, 64'h8900000000000307, 2'd0, 16'd20,
                            2'd1, 4'd1, FAST_ORIGIN_NS, FAST_NOW_NS,
                            FAST_DEADLINE_NS, FAST_ORIGIN_NS,
                            16'h0000, 1'b0, 8'h01);
        bind_reject(64'd308, 64'h8900000000000308, 2'd0, 16'd20,
                    2'd2, 4'd1, 64'd18_000_000_000, 64'd26_000_000_000,
                    16'h0000, 1'b0, PROFILE_SHA256,
                    64'd17_990_000_000, 4'd7, 64'd308);
        case_pass("profile_lock_fault7");

        case_begin("TOKEN_ID_ZERO", "TOKEN-ID-ZERO", "uint63_identity");
        reset_dut();
        arm_dut(FAST_NOW_NS);
        bind_reject(64'd0, 64'd0, 2'd0, 16'd20,
                    2'd1, 4'd1, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h0000, 1'b0, PROFILE_SHA256, FAST_NOW_NS,
                    4'd1, 64'd0);
        case_pass("token_id_zero_fault1");

        case_begin("TOKEN_ID_REPLAY", "TOKEN-ID-REPLAY", "stale_identity");
        reset_dut();
        execute_transaction(64'd309, 64'h8900000000000309, 2'd0, 16'd20,
                            2'd1, 4'd1, FAST_ORIGIN_NS, FAST_NOW_NS,
                            FAST_DEADLINE_NS, FAST_ORIGIN_NS,
                            16'h0000, 1'b0, 8'h01);
        bind_reject(64'd309, 64'h8900000000000309, 2'd1, 16'd32,
                    2'd1, 4'd2, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h0000, 1'b0, PROFILE_SHA256,
                    FAST_ORIGIN_NS + 64'd1, 4'd7, 64'd309);
        case_pass("stale_token_id_fault7");

        case_begin("TOKEN_ID_MSB_SET", "TOKEN-ID-MSB-SET", "uint63_identity");
        reset_dut();
        arm_dut(FAST_NOW_NS);
        bind_reject(64'h8000_0000_0000_0000, 64'h8900000000000322,
                    2'd0, 16'd20, 2'd1, 4'd1, FAST_ORIGIN_NS,
                    FAST_DEADLINE_NS, 16'h0000, 1'b0,
                    PROFILE_SHA256, FAST_NOW_NS, 4'd1,
                    64'h8000_0000_0000_0000);
        case_pass("token_id_msb_fault1");

        case_begin("INGRESS_DESCRIPTOR_MISMATCH", "INGRESS-DESCRIPTOR-MISMATCH", "negative_ingress");
        reset_dut();
        arm_dut(FAST_NOW_NS);
        bind_accept(64'd310, 64'h8900000000000310, 2'd1, 16'd32,
                    2'd1, 4'd2, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h0000, 1'b0, PROFILE_SHA256, FAST_NOW_NS);
        if (used_roles !== 8'h02) tb_fail("ingress_mismatch_used_roles");
        @(negedge clk);
        now_ns = FAST_ORIGIN_NS + 64'd35_000_000 - 64'd1;
        @(posedge clk);
        #1;
        saved_flush_count = flushed_count;
        ingress_identity_bad(64'h8900000000000311, 2'd1, 16'd32, 64'd310);
        if (flushed_count !== saved_flush_count) tb_fail("ingress_identity_flush_delta");
        if (out_valid !== 1'b0) tb_fail("ingress_identity_visible");
        case_pass("descriptor_mismatch_fault2_no_enqueue");

        run_nominal_case("HELD_OFFER_GATED_BEFORE_SLOT", "HELD-OFFER-GATED-BEFORE-SLOT",
                         2'd1, 4'd4, 64'd311, 64'h8900000000000311,
                         2'd1, 16'd34, 16'h0000, 1'b0,
                         FAST_ORIGIN_NS, FAST_NOW_NS, FAST_DEADLINE_NS,
                         FAST_ORIGIN_NS + 64'd305_000_000, 8'h08);

        case_begin("CANCEL_WITH_HELD_OFFER", "CANCEL-WITH-HELD-OFFER", "cancel_flush");
        reset_dut();
        prepare_held_transaction(64'd312, 64'h8900000000000312, 2'd1, 16'd32,
                                 2'd1, 4'd2, FAST_ORIGIN_NS, FAST_NOW_NS,
                                 FAST_DEADLINE_NS,
                                 FAST_ORIGIN_NS + 64'd35_000_000,
                                 16'h0000, 1'b0, 8'h02);
        saved_sent_count = sent_count;
        saved_flush_count = flushed_count;
        @(negedge clk);
        cancel = 1'b1;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b1) tb_fail("cancel_fault_missing");
        if (fault_code !== 4'd5) tb_fail("cancel_wrong_fault_code");
        if (fault_token_id !== 64'd312) tb_fail("cancel_wrong_token_id");
        if (armed !== 1'b0) tb_fail("cancel_not_disarmed");
        if (out_valid !== 1'b0) tb_fail("cancel_out_valid");
        @(negedge clk);
        cancel = 1'b0;
        wait_flush_delta(saved_flush_count, 1);
        if (sent_count !== saved_sent_count) tb_fail("cancel_forwarded");
        if (forward_pulse !== 1'b0) tb_fail("cancel_forward_pulse");
        if (out_valid !== 1'b0) tb_fail("cancel_post_out_valid");
        case_pass("held_offer_cancel_fault5_flush1");

        case_begin("DISABLE_WHILE_ACTIVE", "DISABLE-WHILE-ACTIVE", "disable_flush");
        reset_dut();
        prepare_held_transaction(64'd313, 64'h8900000000000313, 2'd1, 16'd34,
                                 2'd1, 4'd4, FAST_ORIGIN_NS, FAST_NOW_NS,
                                 FAST_DEADLINE_NS,
                                 FAST_ORIGIN_NS + 64'd305_000_000,
                                 16'h0000, 1'b0, 8'h08);
        saved_sent_count = sent_count;
        saved_flush_count = flushed_count;
        @(negedge clk);
        enable = 1'b0;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b1) tb_fail("disable_fault_missing");
        if (fault_code !== 4'd5) tb_fail("disable_wrong_fault_code");
        if (fault_token_id !== 64'd313) tb_fail("disable_wrong_token_id");
        if (armed !== 1'b0) tb_fail("disable_not_disarmed");
        if (out_valid !== 1'b0) tb_fail("disable_out_valid");
        wait_flush_delta(saved_flush_count, 1);
        if (sent_count !== saved_sent_count) tb_fail("disable_forwarded");
        if (forward_pulse !== 1'b0) tb_fail("disable_forward_pulse");
        case_pass("active_disable_fault5_flush1");

        case_begin("BUSY_ARM_WHILE_TOKEN_LIVE", "BUSY-ARM-WHILE-TOKEN-LIVE", "arm_fault");
        reset_dut();
        prepare_held_transaction(64'd314, 64'h8900000000000314, 2'd1, 16'd32,
                                 2'd1, 4'd2, FAST_ORIGIN_NS, FAST_NOW_NS,
                                 FAST_DEADLINE_NS,
                                 FAST_ORIGIN_NS + 64'd35_000_000,
                                 16'h0000, 1'b0, 8'h02);
        saved_sent_count = sent_count;
        saved_flush_count = flushed_count;
        @(negedge clk);
        arm = 1'b0;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b0) tb_fail("busy_arm_pre_fault");
        @(negedge clk);
        arm = 1'b1;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b1) tb_fail("busy_arm_fault_missing");
        if (fault_code !== 4'd6) tb_fail("busy_arm_wrong_fault_code");
        if (fault_token_id !== 64'd314) tb_fail("busy_arm_wrong_token_id");
        if (armed !== 1'b0) tb_fail("busy_arm_not_disarmed");
        @(negedge clk);
        arm = 1'b0;
        wait_flush_delta(saved_flush_count, 1);
        if (sent_count !== saved_sent_count) tb_fail("busy_arm_forwarded");
        if (forward_pulse !== 1'b0) tb_fail("busy_arm_forward_pulse");
        case_pass("busy_rearm_fault6_flush1");

        case_begin("CLEAR_PRESERVES_CLOSED_WINDOW", "CLEAR-PRESERVES-CLOSED-WINDOW", "clear_window");
        reset_dut();
        execute_transaction(64'd314, 64'h8900000000000314, 2'd0, 16'd20,
                            2'd1, 4'd1, FAST_ORIGIN_NS, FAST_NOW_NS,
                            FAST_DEADLINE_NS, FAST_ORIGIN_NS,
                            16'h0000, 1'b0, 8'h01);
        saved_flush_count = flushed_count;
        @(negedge clk);
        cancel = 1'b1;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b1) tb_fail("clear_case_fault_missing");
        if (fault_code !== 4'd5) tb_fail("clear_case_fault_code");
        if (fault_token_id !== 64'd0) tb_fail("clear_case_fault_token_id");
        @(negedge clk);
        cancel = 1'b0;
        wait_flush_delta(saved_flush_count, 0);
        clear_fault_checked(FAST_ORIGIN_NS + 64'd1);
        arm_dut(FAST_ORIGIN_NS + 64'd2);
        bind_reject(64'd315, 64'h8900000000000315, 2'd1, 16'd32,
                    2'd1, 4'd2, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h0000, 1'b0, PROFILE_SHA256,
                    FAST_ORIGIN_NS + 64'd3, 4'd7, 64'd315);
        case_pass("clear_then_same_window_fault7");

        case_begin("NEW_WINDOW_AFTER_FAULT_ALLOWED", "NEW-WINDOW-AFTER-FAULT-ALLOWED", "future_window");
        reset_dut();
        execute_transaction(64'd330, 64'h8900000000000330, 2'd0, 16'd20,
                            2'd1, 4'd1, FAST_ORIGIN_NS, FAST_NOW_NS,
                            FAST_DEADLINE_NS, FAST_ORIGIN_NS,
                            16'h0000, 1'b0, 8'h01);
        saved_flush_count = flushed_count;
        @(negedge clk);
        cancel = 1'b1;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b1) tb_fail("new_window_fault_missing");
        if (fault_code !== 4'd5) tb_fail("new_window_fault_code");
        if (fault_token_id !== 64'd0) tb_fail("new_window_fault_token_id");
        @(negedge clk);
        cancel = 1'b0;
        wait_flush_delta(saved_flush_count, 0);
        clear_fault_checked(FAST_ORIGIN_NS + 64'd1);
        arm_dut(FAST_ORIGIN_NS + FAST_WINDOW_NS - 64'd10_000_000);
        bind_accept(64'd331, 64'h8900000000000331, 2'd0, 16'd20,
                    2'd1, 4'd1, FAST_ORIGIN_NS + FAST_WINDOW_NS,
                    FAST_ORIGIN_NS + FAST_WINDOW_NS + FAST_WINDOW_NS,
                    16'h0000, 1'b0, PROFILE_SHA256,
                    FAST_ORIGIN_NS + FAST_WINDOW_NS - 64'd10_000_000);
        if (used_roles !== 8'h01) tb_fail("new_window_used_roles");
        if (fault_valid !== 1'b0) tb_fail("new_window_unexpected_fault");
        case_pass("future_aligned_window_bind");

        case_begin("NEW_WINDOW_UNALIGNED", "NEW-WINDOW-UNALIGNED", "future_window");
        reset_dut();
        execute_transaction(64'd315, 64'h8900000000000315, 2'd0, 16'd20,
                            2'd1, 4'd1, FAST_ORIGIN_NS, FAST_NOW_NS,
                            FAST_DEADLINE_NS, FAST_ORIGIN_NS,
                            16'h0000, 1'b0, 8'h01);
        bind_reject(64'd316, 64'h8900000000000316, 2'd0, 16'd20,
                    2'd1, 4'd1, 64'd10_500_000_001, 64'd11_000_000_001,
                    16'h0000, 1'b0, PROFILE_SHA256,
                    64'd10_490_000_001, 4'd7, 64'd316);
        case_pass("unaligned_window_fault7");

        case_begin("NEW_WINDOW_BEFORE_PRIOR_END", "NEW-WINDOW-BEFORE-PRIOR-END", "future_window");
        reset_dut();
        execute_transaction(64'd315, 64'h8900000000000315, 2'd0, 16'd20,
                            2'd1, 4'd1, FAST_ORIGIN_NS, FAST_NOW_NS,
                            FAST_DEADLINE_NS, FAST_ORIGIN_NS,
                            16'h0000, 1'b0, 8'h01);
        bind_reject(64'd317, 64'h8900000000000317, 2'd1, 16'd32,
                    2'd1, 4'd2, 64'd10_250_000_000, 64'd10_750_000_000,
                    16'h0000, 1'b0, PROFILE_SHA256,
                    64'd10_240_000_000, 4'd7, 64'd317);
        case_pass("window_before_prior_end_fault7");

        case_begin("DEADLINE_EQUAL_FRAME_END", "DEADLINE-EQUAL-FRAME-END", "negative_time");
        reset_dut();
        arm_dut(FAST_NOW_NS);
        bind_reject(64'd318, 64'h8900000000000318, 2'd0, 16'd20,
                    2'd1, 4'd1, FAST_ORIGIN_NS, 64'd10_020_833_334,
                    16'h0000, 1'b0, PROFILE_SHA256, FAST_NOW_NS,
                    4'd1, 64'd318);
        case_pass("deadline_strict_fault1");

        case_begin("WINDOW_END_OVERFLOW_U63", "WINDOW-END-OVERFLOW-U63", "negative_time");
        reset_dut();
        arm_dut(64'd9_223_372_036_854_775_706);
        bind_reject(64'd319, 64'h8900000000000319, 2'd0, 16'd20,
                    2'd1, 4'd1, 64'd9_223_372_036_854_775_707,
                    MAX_U63_NS, 16'h0000, 1'b0, PROFILE_SHA256,
                    64'd9_223_372_036_854_775_706, 4'd1, 64'd319);
        case_pass("window_sum_overflow_fault1");

        case_begin("LATE_BIND_AT_EXACT_START", "LATE-BIND-AT-EXACT-START", "missed_slot");
        reset_dut();
        arm_dut(FAST_NOW_NS);
        bind_reject(64'd320, 64'h8900000000000320, 2'd1, 16'd32,
                    2'd1, 4'd2, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h0000, 1'b0, PROFILE_SHA256,
                    FAST_ORIGIN_NS + 64'd35_000_000, 4'd3, 64'd320);
        case_pass("late_bind_fault3");

        case_begin("MISS_AFTER_SLOT_BACKPRESSURE", "MISS-AFTER-SLOT-BACKPRESSURE", "backpressure");
        reset_dut();
        prepare_held_transaction(64'd321, 64'h8900000000000321, 2'd1, 16'd32,
                                 2'd1, 4'd2, FAST_ORIGIN_NS, FAST_NOW_NS,
                                 FAST_DEADLINE_NS,
                                 FAST_ORIGIN_NS + 64'd35_000_000,
                                 16'h0000, 1'b0, 8'h02);
        saved_sent_count = sent_count;
        saved_flush_count = flushed_count;
        @(negedge clk);
        now_ns = FAST_ORIGIN_NS + 64'd35_000_000;
        out_ready = 1'b0;
        #1;
        if (out_valid !== 1'b1) tb_fail("backpressure_start_not_visible");
        if (fault_valid !== 1'b0) tb_fail("backpressure_start_fault");
        @(posedge clk);
        if (forward_pulse !== 1'b0) tb_fail("backpressure_unexpected_fire");
        #1;
        if (sent_count !== saved_sent_count) tb_fail("backpressure_forwarded");
        if (fault_valid !== 1'b0) tb_fail("backpressure_early_fault");
        @(negedge clk);
        now_ns = FAST_ORIGIN_NS + 64'd35_000_000 + 64'd1;
        out_ready = 1'b1;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b1) tb_fail("backpressure_miss_fault_missing");
        if (fault_code !== 4'd3) tb_fail("backpressure_wrong_fault_code");
        if (fault_token_id !== 64'd321) tb_fail("backpressure_wrong_token_id");
        if (out_valid !== 1'b0) tb_fail("backpressure_post_out_valid");
        @(negedge clk);
        out_ready = 1'b0;
        wait_flush_delta(saved_flush_count, 1);
        if (sent_count !== saved_sent_count) tb_fail("backpressure_catchup_send");
        if (forward_pulse !== 1'b0) tb_fail("backpressure_forward_pulse");
        case_pass("missed_slot_fault3_no_catchup_flush1");

        case_begin("TIME_REGRESSION_STICKY", "TIME-REGRESSION-STICKY", "time_regression");
        reset_dut();
        arm_dut(FAST_NOW_NS);
        saved_accept_count = accepted_count;
        saved_sent_count = sent_count;
        saved_flush_count = flushed_count;
        @(negedge clk);
        now_ns = FAST_NOW_NS - 64'd1;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b1) tb_fail("time_regression_fault_missing");
        if (fault_code !== 4'd4) tb_fail("time_regression_wrong_code");
        if (fault_token_id !== 64'd0) tb_fail("time_regression_token_id");
        if (armed !== 1'b0) tb_fail("time_regression_still_armed");
        if (out_valid !== 1'b0) tb_fail("time_regression_out_valid");
        if (accepted_count !== saved_accept_count) tb_fail("time_regression_enqueue");
        if (sent_count !== saved_sent_count) tb_fail("time_regression_forwarded");
        repeat (2) begin
            @(posedge clk);
            #1;
            if (fault_valid !== 1'b1) tb_fail("time_regression_not_sticky");
            if (armed !== 1'b0) tb_fail("time_regression_auto_rearm");
        end
        @(negedge clk);
        now_ns = FAST_NOW_NS;
        repeat (2) begin
            @(posedge clk);
            #1;
            if (fault_valid !== 1'b1) tb_fail("time_regression_cleared_without_request");
            if (armed !== 1'b0) tb_fail("time_regression_rearmed_without_request");
        end
        clear_fault_checked(FAST_NOW_NS);
        arm_dut(FAST_NOW_NS + 64'd1);
        if (armed !== 1'b1) tb_fail("time_regression_new_arm_failed");
        case_pass("fault4_sticky_requires_clear_and_new_arm_rise");

        case_begin("TOKEN_VALID_HELD_NO_REPLAY", "TOKEN-VALID-HELD-NO-REPLAY", "valid_lifecycle");
        reset_dut();
        arm_dut(FAST_NOW_NS);
        saved_accept_count = accepted_count;
        saved_sent_count = sent_count;
        @(negedge clk);
        token_valid = 1'b1;
        token_id = 64'd340;
        token_desc = 64'h8900000000000340;
        token_class = 2'd0;
        token_cost = 16'd20;
        token_profile_id = 2'd1;
        token_role = 4'd1;
        window_origin_ns = FAST_ORIGIN_NS;
        deadline_ns = FAST_DEADLINE_NS;
        token_profile_sha256 = PROFILE_SHA256;
        token_grant_mask = 16'h0000;
        token_first_ack_ok = 1'b0;
        @(posedge clk);
        if (token_ready !== 1'b1) tb_fail("held_valid_first_bind_ready");
        #1;
        if (fault_valid !== 1'b0) tb_fail("held_valid_first_bind_fault");
        if (used_roles !== 8'h01) tb_fail("held_valid_first_role_mask");
        @(negedge clk);
        token_id = 64'd341;
        token_desc = 64'h8900000000000341;
        token_class = 2'd1;
        token_cost = 16'd32;
        token_role = 4'd2;
        if (token_ready !== 1'b0) tb_fail("held_valid_second_token_ready");
        wait_credits(16'd20);
        @(negedge clk);
        now_ns = FAST_ORIGIN_NS - 64'd1;
        ingress_exact(64'h8900000000000340, 2'd0, 16'd20);
        expect_no_outer_valid(4);
        fire_exact(64'h8900000000000340, 2'd0, 16'd20, 64'd340, FAST_ORIGIN_NS);
        if (sent_count !== saved_sent_count + 1) tb_fail("held_valid_sent_count");
        if (token_ready !== 1'b0) tb_fail("held_valid_high_token_ready");
        if (fault_valid !== 1'b0) tb_fail("held_valid_high_fault");
        @(negedge clk);
        token_valid = 1'b0;
        @(posedge clk);
        #1;
        if (token_ready !== 1'b0) tb_fail("held_valid_low_ready");
        if (fault_valid !== 1'b0) tb_fail("held_valid_low_fault");
        bind_accept(64'd342, 64'h8900000000000342, 2'd1, 16'd32,
                    2'd1, 4'd2, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h0000, 1'b0, PROFILE_SHA256, FAST_ORIGIN_NS + 64'd1);
        if (used_roles !== 8'h03) tb_fail("held_valid_second_role_mask");
        case_pass("held_valid_no_replay_then_low_rebinds");

        case_begin("RESET_DESTRUCTIVE_UNKNOWN", "RESET-DESTRUCTIVE-UNKNOWN", "reset");
        reset_dut();
        prepare_held_transaction(64'd350, 64'h8900000000000350, 2'd0, 16'd20,
                                 2'd1, 4'd1, FAST_ORIGIN_NS, FAST_NOW_NS,
                                 FAST_DEADLINE_NS, FAST_ORIGIN_NS,
                                 16'h0000, 1'b0, 8'h01);
        if (accepted_count !== 32'd1) tb_fail("reset_live_accept_count");
        if (count_q0 !== 3'd1) tb_fail("reset_live_q0_count");
        saved_accept_count = accepted_count;
        saved_sent_count = sent_count;
        saved_flush_count = flushed_count;
        @(negedge clk);
        rst = 1'b1;
        repeat (3) @(posedge clk);
        @(negedge clk);
        rst = 1'b0;
        repeat (2) @(posedge clk);
        #1;
        if (fault_valid !== 1'b0) tb_fail("reset_fault_clear");
        if (fault_code !== 4'd0) tb_fail("reset_fault_code_clear");
        if (armed !== 1'b0) tb_fail("reset_armed_clear");
        if (out_valid !== 1'b0) tb_fail("reset_output_clear");
        if (token_ready !== 1'b0) tb_fail("reset_ready_clear");
        if (credits_remaining !== 16'd0) tb_fail("reset_credit_clear");
        if ((count_q0 !== 3'd0) || (count_q1 !== 3'd0) || (count_q2 !== 3'd0))
            tb_fail("reset_queue_clear");
        if (accepted_count !== 32'd0) tb_fail("reset_accept_stat_clear");
        if (sent_count !== 32'd0) tb_fail("reset_sent_stat_clear");
        if (flushed_count !== 32'd0) tb_fail("reset_flush_stat_clear");
        if (forward_pulse !== 1'b0) tb_fail("reset_ack_or_auto_action");
        if (forwarded_token_id !== 64'd0) tb_fail("reset_forwarded_id_clear");
        if ((saved_accept_count !== 1) || (saved_sent_count !== 0) ||
            (saved_flush_count !== 0))
            tb_fail("reset_live_preconditions");
        arm_dut(FAST_ORIGIN_NS - 64'd1);
        bind_accept(64'd350, 64'h8900000000000350, 2'd0, 16'd20,
                    2'd1, 4'd1, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h0000, 1'b0, PROFILE_SHA256, FAST_ORIGIN_NS - 64'd1);
        if (used_roles !== 8'h01) tb_fail("reset_identity_context_not_cleared");
        case_pass("destructive_reset_clears_context_no_ack_rebind");

        case_begin("CLEAR_REFUSED_WHILE_CORE_NONEMPTY", "CLEAR-REFUSED-WHILE-CORE-NONEMPTY", "clear_flush");
        reset_dut();
        prepare_held_transaction(64'd351, 64'h8900000000000351, 2'd0, 16'd20,
                                 2'd1, 4'd1, FAST_ORIGIN_NS, FAST_NOW_NS,
                                 FAST_DEADLINE_NS, FAST_ORIGIN_NS,
                                 16'h0000, 1'b0, 8'h01);
        saved_flush_count = flushed_count;
        saved_sent_count = sent_count;
        @(negedge clk);
        cancel = 1'b1;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b1) tb_fail("clear_core_fault_missing");
        if (fault_code !== 4'd5) tb_fail("clear_core_wrong_fault");
        if (fault_token_id !== 64'd351) tb_fail("clear_core_wrong_token");
        if (count_q0 !== 3'd1) tb_fail("clear_core_not_held");
        @(negedge clk);
        cancel = 1'b0;
        clear_fault = 1'b1;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b1) tb_fail("clear_core_first_clear_accepted");
        if (fault_code !== 4'd5) tb_fail("clear_core_first_clear_code");
        if (flushed_count !== saved_flush_count + 1) tb_fail("clear_core_flush_delta");
        if ((count_q0 !== 3'd0) || (count_q1 !== 3'd0) || (count_q2 !== 3'd0))
            tb_fail("clear_core_not_empty");
        if (out_valid !== 1'b0) tb_fail("clear_core_offer_visible");
        if (sent_count !== saved_sent_count) tb_fail("clear_core_forwarded");
        @(negedge clk);
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b0) tb_fail("clear_core_later_clear_refused");
        if (armed !== 1'b0) tb_fail("clear_core_auto_armed");
        @(negedge clk);
        clear_fault = 1'b0;
        repeat (2) @(posedge clk);
        #1;
        if (fault_valid !== 1'b0) tb_fail("clear_core_clear_returned");
        if (armed !== 1'b0) tb_fail("clear_core_late_auto_arm");
        case_pass("first_clear_refused_then_clear_after_flush");

        case_begin("IDLE_CANCEL_DISABLE_NO_FAULT", "IDLE-CANCEL-DISABLE-NO-FAULT", "idle_control");
        reset_dut();
        saved_accept_count = accepted_count;
        saved_sent_count = sent_count;
        saved_flush_count = flushed_count;
        @(negedge clk);
        enable = 1'b1;
        arm = 1'b0;
        cancel = 1'b0;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b0) tb_fail("idle_enable_fault");
        if (armed !== 1'b0) tb_fail("idle_enable_armed");
        @(negedge clk);
        cancel = 1'b1;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b0) tb_fail("idle_cancel_fault");
        if (fault_code !== 4'd0) tb_fail("idle_cancel_code");
        if (flushed_count !== saved_flush_count) tb_fail("idle_cancel_flush");
        if (armed !== 1'b0) tb_fail("idle_cancel_armed");
        @(negedge clk);
        cancel = 1'b0;
        enable = 1'b0;
        @(posedge clk);
        #1;
        if (fault_valid !== 1'b0) tb_fail("idle_disable_fault");
        if (flushed_count !== saved_flush_count) tb_fail("idle_disable_flush");
        if (accepted_count !== saved_accept_count) tb_fail("idle_accept_delta");
        if (sent_count !== saved_sent_count) tb_fail("idle_sent_delta");
        if (out_valid !== 1'b0) tb_fail("idle_output");
        case_pass("idle_cancel_disable_no_fault_no_flush");

        case_begin("SAME_ORIGIN_SAME_ROLE_REPLAY", "SAME-ORIGIN-SAME-ROLE-REPLAY", "replay");
        reset_dut();
        execute_transaction(64'd360, 64'h8900000000000360, 2'd0, 16'd20,
                            2'd1, 4'd1, FAST_ORIGIN_NS, FAST_NOW_NS,
                            FAST_DEADLINE_NS, FAST_ORIGIN_NS,
                            16'h0000, 1'b0, 8'h01);
        bind_reject(64'd361, 64'h8900000000000361, 2'd0, 16'd20,
                    2'd1, 4'd1, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h0000, 1'b0, PROFILE_SHA256,
                    FAST_ORIGIN_NS + 64'd1, 4'd7, 64'd361);
        if (used_roles !== 8'h01) tb_fail("same_role_mask_changed");
        case_pass("same_origin_same_role_fault7");

        case_begin("SAME_ORIGIN_DIFFERENT_ROLE_ALLOWED", "SAME-ORIGIN-DIFFERENT-ROLE-ALLOWED", "role_reuse");
        reset_dut();
        execute_transaction(64'd362, 64'h8900000000000362, 2'd0, 16'd20,
                            2'd1, 4'd1, FAST_ORIGIN_NS, FAST_NOW_NS,
                            FAST_DEADLINE_NS, FAST_ORIGIN_NS,
                            16'h0000, 1'b0, 8'h01);
        bind_accept(64'd363, 64'h8900000000000363, 2'd1, 16'd32,
                    2'd1, 4'd2, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h0000, 1'b0, PROFILE_SHA256, FAST_ORIGIN_NS + 64'd1);
        if (used_roles !== 8'h03) tb_fail("different_role_mask");
        if (fault_valid !== 1'b0) tb_fail("different_role_fault");
        case_pass("same_origin_telem_bind_used_roles_03");

        case_begin("NEW_WINDOW_CLEARS_ROLE_MASK", "NEW-WINDOW-CLEARS-ROLE-MASK", "future_window");
        reset_dut();
        execute_transaction(64'd364, 64'h8900000000000364, 2'd0, 16'd20,
                            2'd1, 4'd1, FAST_ORIGIN_NS, FAST_NOW_NS,
                            FAST_DEADLINE_NS, FAST_ORIGIN_NS,
                            16'h0000, 1'b0, 8'h01);
        bind_accept(64'd365, 64'h8900000000000365, 2'd0, 16'd20,
                    2'd1, 4'd1, FAST_ORIGIN_NS + FAST_WINDOW_NS,
                    FAST_ORIGIN_NS + FAST_WINDOW_NS + FAST_WINDOW_NS,
                    16'h0000, 1'b0, PROFILE_SHA256,
                    FAST_ORIGIN_NS + FAST_WINDOW_NS - 64'd10_000_000);
        if (used_roles !== 8'h01) tb_fail("new_window_role_mask_not_cleared");
        if (fault_valid !== 1'b0) tb_fail("new_window_role_fault");
        case_pass("aligned_new_window_reuses_role_slot");

        case_begin("RETRY_GRANT_STATE_INVALID", "RETRY-GRANT-STATE-INVALID", "grant_state");
        reset_dut();
        arm_dut(FAST_NOW_NS);
        bind_reject(64'd370, 64'h8900000000000370, 2'd0, 16'd20,
                    2'd1, 4'd1, FAST_ORIGIN_NS, FAST_DEADLINE_NS,
                    16'h2000, 1'b0, PROFILE_SHA256, FAST_NOW_NS,
                    4'd1, 64'd370);
        if (used_roles !== 8'h00) tb_fail("retry_grant_state_used_roles");
        case_pass("bit13_without_bit15_fault1");

        case_begin("UNARMED_TOKEN_BACKPRESSURE", "UNARMED-TOKEN-BACKPRESSURE", "unarmed_boundary");
        reset_dut();
        saved_accept_count = accepted_count;
        saved_sent_count = sent_count;
        @(negedge clk);
        enable = 1'b1;
        arm = 1'b0;
        token_valid = 1'b1;
        token_id = 64'd371;
        token_desc = 64'h8900000000000371;
        token_class = 2'd0;
        token_cost = 16'd20;
        token_profile_id = 2'd1;
        token_role = 4'd1;
        window_origin_ns = FAST_ORIGIN_NS;
        deadline_ns = FAST_DEADLINE_NS;
        token_profile_sha256 = PROFILE_SHA256;
        token_grant_mask = 16'h0000;
        token_first_ack_ok = 1'b0;
        in_valid = 1'b0;
        out_ready = 1'b0;
        downstream_quiescent = 1'b1;
        repeat (4) begin
            @(posedge clk);
            #1;
            if (token_ready !== 1'b0) tb_fail("unarmed_token_ready");
            if (fault_valid !== 1'b0) tb_fail("unarmed_token_fault");
            if (accepted_count !== saved_accept_count) tb_fail("unarmed_token_enqueue");
            if (out_valid !== 1'b0) tb_fail("unarmed_token_output");
            if (armed !== 1'b0) tb_fail("unarmed_token_armed");
        end
        if (sent_count !== saved_sent_count) tb_fail("unarmed_token_forwarded");
        @(negedge clk);
        token_valid = 1'b0;
        enable = 1'b0;
        case_pass("valid_token_without_arm_is_held_off");

        if (checked_cases !== EXECUTABLE_CASES)
            tb_fail("executable_case_count_mismatch");
        if ((EXECUTABLE_CASES + REVIEW_ONLY_CASES) !== MANUAL_CASES)
            tb_fail("manual_case_count_mismatch");
        $display("REVIEW_ONLY_SKIP manual_id=HELD-OFFER-MISMATCH-NOT-NATURAL");
        if (status_fd == 0)
            $fatal(1, "B04_SLOT89_FAIL status_file_closed_before_pass");
        $fwrite(status_fd, "REVIEW_ONLY_SKIP manual_id=HELD-OFFER-MISMATCH-NOT-NATURAL\n");
        $fwrite(status_fd,
                "TEST_PASS completed=1 checked_cases=%0d manual_cases=%0d review_only_skipped=%0d\n",
                checked_cases, MANUAL_CASES, REVIEW_ONLY_CASES);
        $display("TEST_PASS completed=1 checked_cases=%0d manual_cases=%0d review_only_skipped=%0d",
                 checked_cases, MANUAL_CASES, REVIEW_ONLY_CASES);
        $fclose(status_fd);
        status_fd = 0;
        $finish;
    end

endmodule

`default_nettype wire
