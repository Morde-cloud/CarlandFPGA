`default_nettype none
`timescale 1ns/1ps

module deepeye_nominal_uplink_slot_gate_candidate (
    input  wire         clk,
    input  wire         rst,
    input  wire         enable,
    input  wire         arm,
    input  wire         cancel,
    input  wire         clear_fault,
    input  wire [63:0]  now_ns,
    input  wire         downstream_quiescent,

    input  wire         token_valid,
    output logic         token_ready,
    input  wire [63:0]  token_id,
    input  wire [63:0]  token_desc,
    input  wire [1:0]   token_class,
    input  wire [15:0]  token_cost,
    input  wire [1:0]   token_profile_id,
    input  wire [3:0]   token_role,
    input  wire [63:0]  window_origin_ns,
    input  wire [63:0]  deadline_ns,
    input  wire [255:0] profile_sha256,
    input  wire [15:0]  grant_mask,
    input  wire         first_ack_ok,

    input  wire         in_valid,
    output logic         in_ready,
    input  wire [63:0]  in_desc,
    input  wire [1:0]   in_class,
    input  wire [15:0]  in_cost,

    output logic         out_valid,
    input  wire         out_ready,
    output logic [63:0]  out_desc,
    output logic [1:0]   out_class,
    output logic [15:0]  out_cost,

    output logic         armed,
    output logic         fault_valid,
    output logic [3:0]   fault_code,
    output logic [63:0]  fault_token_id,
    output logic         forward_pulse,
    output logic [63:0]  forwarded_token_id,
    output logic [7:0]   used_roles,
    output logic [15:0]  credits_remaining,
    output logic [2:0]   count_q0,
    output logic [2:0]   count_q1,
    output logic [2:0]   count_q2,
    output logic [31:0]  accepted_count,
    output logic [31:0]  sent_count,
    output logic [31:0]  flushed_count
);

    localparam logic [3:0] FAULT_NONE = 4'd0;
    localparam logic [3:0] FAULT_TOKEN_INVALID = 4'd1;
    localparam logic [3:0] FAULT_IDENTITY = 4'd2;
    localparam logic [3:0] FAULT_MISSED_SLOT = 4'd3;
    localparam logic [3:0] FAULT_TIME_REGRESSION = 4'd4;
    localparam logic [3:0] FAULT_CANCELLED_OR_DISABLED = 4'd5;
    localparam logic [3:0] FAULT_BUSY_ARM = 4'd6;
    localparam logic [3:0] FAULT_REPLAY_OR_WINDOW = 4'd7;

    localparam logic [3:0] ROLE_EVENT = 4'd1;
    localparam logic [3:0] ROLE_TELEM = 4'd2;
    localparam logic [3:0] ROLE_ACK_PRIMARY = 4'd3;
    localparam logic [3:0] ROLE_STATE3D = 4'd4;
    localparam logic [3:0] ROLE_ACK_RETRY = 4'd5;
    localparam logic [3:0] ROLE_CONFIG_ACK = 4'd6;
    localparam logic [3:0] ROLE_EVENT_RETRY = 4'd7;

    localparam logic [1:0] PROFILE_FAST = 2'd1;
    localparam logic [1:0] PROFILE_STRESS = 2'd2;
    localparam logic [63:0] MAX_U63 = 64'h7fff_ffff_ffff_ffff;
    localparam logic [63:0] FAST_WINDOW_NS = 64'd500_000_000;
    localparam logic [63:0] FAST_GUARD_NS = 64'd40_000_000;
    localparam logic [63:0] STRESS_WINDOW_NS = 64'd8_000_000_000;
    localparam logic [63:0] STRESS_GUARD_NS = 64'd200_000_000;
    localparam logic [255:0] EXPECTED_PROFILE_SHA256 =
        256'hb7abdd50d04337c4526ae43de6912c9b7f05e9803e79a519dd4fd7528edc3b46;

    function automatic logic [7:0] role_mask(input logic [3:0] role_id);
        begin
            role_mask = 8'h00;
            case (role_id)
                ROLE_EVENT:       role_mask = 8'h01;
                ROLE_TELEM:       role_mask = 8'h02;
                ROLE_ACK_PRIMARY: role_mask = 8'h04;
                ROLE_STATE3D:     role_mask = 8'h08;
                ROLE_ACK_RETRY:   role_mask = 8'h10;
                ROLE_CONFIG_ACK:  role_mask = 8'h20;
                ROLE_EVENT_RETRY: role_mask = 8'h40;
                default:          role_mask = 8'h00;
            endcase
        end
    endfunction

    function automatic logic [1:0] role_class(input logic [3:0] role_id);
        begin
            role_class = 2'd0;
            case (role_id)
                ROLE_TELEM:   role_class = 2'd1;
                ROLE_STATE3D: role_class = 2'd1;
                default:      role_class = 2'd0;
            endcase
        end
    endfunction

    function automatic logic [15:0] role_cost(input logic [3:0] role_id);
        begin
            role_cost = 16'd0;
            case (role_id)
                ROLE_EVENT:       role_cost = 16'd20;
                ROLE_TELEM:       role_cost = 16'd32;
                ROLE_ACK_PRIMARY: role_cost = 16'd34;
                ROLE_STATE3D:     role_cost = 16'd34;
                ROLE_ACK_RETRY:   role_cost = 16'd34;
                ROLE_CONFIG_ACK:  role_cost = 16'd32;
                ROLE_EVENT_RETRY: role_cost = 16'd20;
                default:          role_cost = 16'd0;
            endcase
        end
    endfunction

    function automatic logic [63:0] role_offset_ns(
        input logic [1:0] profile_id,
        input logic [3:0] role_id
    );
        begin
            role_offset_ns = 64'd0;
            case (profile_id)
                PROFILE_FAST: begin
                    case (role_id)
                        ROLE_EVENT:       role_offset_ns = 64'd0;
                        ROLE_TELEM:       role_offset_ns = 64'd35_000_000;
                        ROLE_ACK_PRIMARY: role_offset_ns = 64'd255_000_000;
                        ROLE_STATE3D:     role_offset_ns = 64'd305_000_000;
                        ROLE_ACK_RETRY:   role_offset_ns = 64'd410_000_000;
                        ROLE_CONFIG_ACK:  role_offset_ns = 64'd405_000_000;
                        ROLE_EVENT_RETRY: role_offset_ns = 64'd365_000_000;
                        default:          role_offset_ns = 64'd0;
                    endcase
                end
                PROFILE_STRESS: begin
                    case (role_id)
                        ROLE_EVENT:       role_offset_ns = 64'd0;
                        ROLE_TELEM:       role_offset_ns = 64'd700_000_000;
                        ROLE_ACK_PRIMARY: role_offset_ns = 64'd3_100_000_000;
                        ROLE_STATE3D:     role_offset_ns = 64'd4_300_000_000;
                        ROLE_ACK_RETRY:   role_offset_ns = 64'd6_550_000_000;
                        ROLE_CONFIG_ACK:  role_offset_ns = 64'd6_550_000_000;
                        ROLE_EVENT_RETRY: role_offset_ns = 64'd5_500_000_000;
                        default:          role_offset_ns = 64'd0;
                    endcase
                end
                default: role_offset_ns = 64'd0;
            endcase
        end
    endfunction

    function automatic logic [63:0] role_wire_ns(
        input logic [1:0] profile_id,
        input logic [3:0] role_id
    );
        begin
            role_wire_ns = 64'd0;
            case (profile_id)
                PROFILE_FAST: begin
                    case (role_id)
                        ROLE_EVENT:       role_wire_ns = 64'd20_833_334;
                        ROLE_TELEM:       role_wire_ns = 64'd33_333_334;
                        ROLE_ACK_PRIMARY: role_wire_ns = 64'd35_416_667;
                        ROLE_STATE3D:     role_wire_ns = 64'd35_416_667;
                        ROLE_ACK_RETRY:   role_wire_ns = 64'd35_416_667;
                        ROLE_CONFIG_ACK:  role_wire_ns = 64'd33_333_334;
                        ROLE_EVENT_RETRY: role_wire_ns = 64'd20_833_334;
                        default:          role_wire_ns = 64'd0;
                    endcase
                end
                PROFILE_STRESS: begin
                    case (role_id)
                        ROLE_EVENT:       role_wire_ns = 64'd666_666_667;
                        ROLE_TELEM:       role_wire_ns = 64'd1_066_666_667;
                        ROLE_ACK_PRIMARY: role_wire_ns = 64'd1_133_333_334;
                        ROLE_STATE3D:     role_wire_ns = 64'd1_133_333_334;
                        ROLE_ACK_RETRY:   role_wire_ns = 64'd1_133_333_334;
                        ROLE_CONFIG_ACK:  role_wire_ns = 64'd1_066_666_667;
                        ROLE_EVENT_RETRY: role_wire_ns = 64'd666_666_667;
                        default:          role_wire_ns = 64'd0;
                    endcase
                end
                default: role_wire_ns = 64'd0;
            endcase
        end
    endfunction

    function automatic logic [63:0] profile_window_ns(input logic [1:0] profile_id);
        begin
            case (profile_id)
                PROFILE_FAST:   profile_window_ns = FAST_WINDOW_NS;
                PROFILE_STRESS: profile_window_ns = STRESS_WINDOW_NS;
                default:        profile_window_ns = FAST_WINDOW_NS;
            endcase
        end
    endfunction

    function automatic logic [63:0] profile_guard_ns(input logic [1:0] profile_id);
        begin
            case (profile_id)
                PROFILE_FAST:   profile_guard_ns = FAST_GUARD_NS;
                PROFILE_STRESS: profile_guard_ns = STRESS_GUARD_NS;
                default:        profile_guard_ns = FAST_GUARD_NS;
            endcase
        end
    endfunction

    function automatic logic grant_role_ok(
        input logic [3:0] role_id,
        input logic [15:0] grants,
        input logic first_ack
    );
        begin
            grant_role_ok = 1'b1;
            case (role_id)
                ROLE_ACK_PRIMARY: grant_role_ok = grants[15];
                ROLE_ACK_RETRY:   grant_role_ok = grants[15] && grants[13] && !grants[14] && !first_ack;
                ROLE_CONFIG_ACK:  grant_role_ok = grants[14] && !grants[13];
                ROLE_EVENT_RETRY: grant_role_ok = !grants[13] && !grants[14];
                default:          grant_role_ok = 1'b1;
            endcase
        end
    endfunction

    localparam logic [64:0] MAX_U63_65 = {1'b0, MAX_U63};
    localparam logic [15:0] GRANT_LOW_BITS = 16'h1fff;
    logic armed_q;
    logic arm_q;
    logic enable_q;
    logic fault_q;
    logic [3:0] fault_code_q;
    logic [63:0] fault_token_id_q;
    logic [63:0] last_forwarded_token_id_q;

    logic token_active_q;
    logic credits_loaded_q;
    logic descriptor_present_q;
    logic token_clear_seen_q;

    logic [63:0] bound_token_id_q;
    logic [63:0] bound_desc_q;
    logic [1:0] bound_class_q;
    logic [15:0] bound_cost_q;
    logic [63:0] bound_start_q;

    logic last_id_valid_q;
    logic [63:0] last_id_q;
    logic profile_lock_q;
    logic [1:0] profile_context_q;
    logic window_seen_q;
    logic window_closed_q;
    logic [7:0] used_roles_q;
    logic [63:0] current_origin_q;
    logic [63:0] current_window_end_q;
    logic time_seen_q;
    logic [63:0] last_now_q;

    logic q_flush;
    logic q_enable;
    logic q_in_valid;
    logic q_in_ready;
    logic q_in_invalid;
    logic q_credit_load_valid;
    logic q_credit_load_ready;
    logic [2:0] q_eligible_mask;
    logic q_out_valid;
    logic q_out_ready;
    logic [63:0] q_out_desc;
    logic [1:0] q_out_class;
    logic [15:0] q_out_cost;
    logic [15:0] q_credits_remaining;
    logic [2:0] q_count_q0;
    logic [2:0] q_count_q1;
    logic [2:0] q_count_q2;
    logic [31:0] q_accepted_count;
    logic [31:0] q_sent_count;
    logic [31:0] q_flushed_count;

    logic [7:0] requested_role_mask;
    logic [7:0] effective_used_roles;
    logic new_window_candidate;
    logic profile_id_ok;
    logic profile_hash_ok;
    logic profile_lock_ok;
    logic grant_bits_ok;
    logic grant_state_ok;
    logic grant_specific_ok;
    logic role_known;
    logic role_class_cost_ok;
    logic role_reused;
    logic role_pair_ok;
    logic token_id_nonzero_u63;
    logic token_id_monotonic;
    logic window_relation_ok;

    logic [63:0] expected_window_value;
    logic [63:0] expected_guard_value;
    logic [63:0] role_offset_value;
    logic [63:0] role_wire_value;
    logic [64:0] origin_ext;
    logic [64:0] window_ext;
    logic [64:0] window_end_ext;
    logic [64:0] current_window_end_ext;
    logic [64:0] now_ext;
    logic [64:0] deadline_ext;
    logic [64:0] start_ext;
    logic [64:0] frame_end_ext;
    logic [64:0] guard_end_ext;
    logic [64:0] origin_delta_ext;
    logic [64:0] origin_remainder_ext;
    logic time_sums_u63_ok;
    logic time_shape_ok;
    logic start_in_future;
    logic [3:0] token_bind_fault;
    logic token_checks_ok;

    logic core_empty;
    logic context_busy;
    logic time_now_bad;
    logic bind_candidate;
    logic arm_attempt;
    logic arm_conditions_ok;
    logic arm_success;
    logic ingress_exact;
    logic ingress_mismatch;
    logic ingress_allow;
    logic in_accept;
    logic load_allow;
    logic load_accept;
    logic held_exact;
    logic held_mismatch;
    logic slot_view_ok;
    logic slot_ready_at_deadline;
    logic slot_expired;
    logic fire;

    logic fault_event;
    logic [3:0] fault_event_code;
    logic [63:0] fault_event_token_id;
    logic clear_allowed;

    assign requested_role_mask = role_mask(token_role);
    assign new_window_candidate = !window_seen_q
                                || (window_origin_ns != current_origin_q);
    assign effective_used_roles = new_window_candidate ? 8'h00 : used_roles_q;

    assign profile_id_ok = (token_profile_id == PROFILE_FAST)
                        || (token_profile_id == PROFILE_STRESS);
    assign profile_hash_ok = (profile_sha256 == EXPECTED_PROFILE_SHA256);
    assign profile_lock_ok = !profile_lock_q
                          || (token_profile_id == profile_context_q);
    assign grant_bits_ok = (grant_mask & GRANT_LOW_BITS) == 16'h0000;
    assign grant_state_ok = !grant_mask[13]
                         || (grant_mask[15] && !grant_mask[14]);
    assign grant_specific_ok = grant_role_ok(token_role, grant_mask, first_ack_ok);
    assign role_known = (requested_role_mask != 8'h00);
    assign role_class_cost_ok = (token_class == role_class(token_role))
                             && (token_cost == role_cost(token_role));
    assign role_reused = ((effective_used_roles & requested_role_mask) != 8'h00);
    assign token_id_nonzero_u63 = (token_id != 64'd0) && !token_id[63];
    assign token_id_monotonic = !last_id_valid_q || (token_id > last_id_q);

    always_comb begin
        role_pair_ok = 1'b1;
        case (token_role)
            ROLE_ACK_RETRY: begin
                role_pair_ok = !effective_used_roles[5]
                            && !effective_used_roles[6];
            end
            ROLE_CONFIG_ACK: begin
                role_pair_ok = !effective_used_roles[4]
                            && !effective_used_roles[6];
            end
            ROLE_EVENT_RETRY: begin
                role_pair_ok = !effective_used_roles[4]
                            && !effective_used_roles[5];
            end
            default: role_pair_ok = 1'b1;
        endcase
    end

    assign expected_window_value = profile_window_ns(token_profile_id);
    assign expected_guard_value = profile_guard_ns(token_profile_id);
    assign role_offset_value = role_offset_ns(token_profile_id, token_role);
    assign role_wire_value = role_wire_ns(token_profile_id, token_role);

    assign origin_ext = {1'b0, window_origin_ns};
    assign window_ext = {1'b0, expected_window_value};
    assign window_end_ext = origin_ext + window_ext;
    assign current_window_end_ext = {1'b0, current_window_end_q};
    assign now_ext = {1'b0, now_ns};
    assign deadline_ext = {1'b0, deadline_ns};
    assign start_ext = origin_ext + {1'b0, role_offset_value};
    assign frame_end_ext = start_ext + {1'b0, role_wire_value};
    assign guard_end_ext = frame_end_ext + {1'b0, expected_guard_value};
    assign origin_delta_ext = origin_ext - {1'b0, current_origin_q};
    assign origin_remainder_ext = origin_delta_ext % window_ext;

    assign time_sums_u63_ok = (window_end_ext <= MAX_U63_65)
                           && (start_ext <= MAX_U63_65)
                           && (frame_end_ext <= MAX_U63_65)
                           && (guard_end_ext <= MAX_U63_65);
    assign time_shape_ok = !now_ns[63]
                        && !window_origin_ns[63]
                        && !deadline_ns[63]
                        && time_sums_u63_ok
                        && (frame_end_ext < deadline_ext)
                        && (guard_end_ext <= window_end_ext);
    assign start_in_future = start_ext > now_ext;

    always_comb begin
        window_relation_ok = 1'b0;
        if (!window_seen_q) begin
            window_relation_ok = 1'b1;
        end else if (window_origin_ns == current_origin_q) begin
            window_relation_ok = !window_closed_q;
        end else begin
            window_relation_ok = !window_origin_ns[63]
                              && (origin_ext >= current_window_end_ext)
                              && (origin_remainder_ext == 65'd0);
        end
    end

    always_comb begin
        token_bind_fault = FAULT_NONE;
        if (!profile_id_ok || !profile_hash_ok || !grant_bits_ok
                || !grant_state_ok || !grant_specific_ok || !role_known
                || !role_class_cost_ok) begin
            token_bind_fault = FAULT_TOKEN_INVALID;
        end else if (!token_id_nonzero_u63) begin
            token_bind_fault = FAULT_TOKEN_INVALID;
        end else if (!profile_lock_ok || !token_id_monotonic || role_reused
                || !role_pair_ok || !window_relation_ok) begin
            token_bind_fault = FAULT_REPLAY_OR_WINDOW;
        end else if (!time_shape_ok) begin
            token_bind_fault = FAULT_TOKEN_INVALID;
        end else if (!start_in_future) begin
            token_bind_fault = FAULT_MISSED_SLOT;
        end
    end

    assign token_checks_ok = (token_bind_fault == FAULT_NONE);

    assign core_empty = (q_count_q0 == 3'd0)
                     && (q_count_q1 == 3'd0)
                     && (q_count_q2 == 3'd0)
                     && !q_out_valid;
    assign context_busy = armed_q || token_active_q || !core_empty;
    assign time_now_bad = now_ns[63]
                       || (time_seen_q && (now_ns < last_now_q));

    assign bind_candidate = !rst
                         && token_valid
                         && token_clear_seen_q
                         && armed_q
                         && enable
                         && !fault_q
                         && !cancel
                         && !token_active_q
                         && core_empty
                         && downstream_quiescent
                         && !time_now_bad;

    assign arm_attempt = arm && !arm_q && enable && !fault_q && !cancel;
    assign arm_conditions_ok = !token_active_q
                            && core_empty
                            && downstream_quiescent
                            && !token_valid;
    assign arm_success = arm_attempt && arm_conditions_ok && !armed_q;

    assign ingress_exact = (in_desc == bound_desc_q)
                        && (in_class == bound_class_q)
                        && (in_cost == bound_cost_q);
    assign ingress_mismatch = token_active_q && in_valid && !ingress_exact;
    assign ingress_allow = token_active_q
                        && credits_loaded_q
                        && !descriptor_present_q
                        && armed_q
                        && enable
                        && !fault_q
                        && !cancel
                        && !time_now_bad
                        && !arm_attempt
                        && (now_ns < bound_start_q)
                        && ingress_exact;
    assign q_in_valid = in_valid && ingress_allow;
    assign in_ready = ingress_allow && q_in_ready;
    assign in_accept = q_in_valid && q_in_ready;

    assign load_allow = token_active_q
                     && !credits_loaded_q
                     && !descriptor_present_q
                     && armed_q
                     && enable
                     && !fault_q
                     && !cancel
                     && !time_now_bad
                     && !arm_attempt
                     && (now_ns < bound_start_q)
                     && core_empty
                     && downstream_quiescent;
    assign q_credit_load_valid = load_allow;
    assign load_accept = q_credit_load_valid && q_credit_load_ready;

    assign held_exact = q_out_valid
                     && (q_out_desc == bound_desc_q)
                     && (q_out_class == bound_class_q)
                     && (q_out_cost == bound_cost_q);
    assign held_mismatch = token_active_q && q_out_valid && !held_exact;

    assign slot_ready_at_deadline = descriptor_present_q && held_exact;
    assign slot_expired = token_active_q
                       && ((now_ns > bound_start_q)
                           || ((now_ns == bound_start_q)
                               && !slot_ready_at_deadline));
    assign slot_view_ok = token_active_q
                       && descriptor_present_q
                       && armed_q
                       && enable
                       && !fault_q
                       && !cancel
                       && downstream_quiescent
                       && (now_ns == bound_start_q)
                       && held_exact;
    assign out_valid = slot_view_ok && !fault_event;
    assign q_out_ready = out_ready && out_valid;
    assign fire = out_valid && out_ready;

    always_comb begin
        fault_event = 1'b0;
        fault_event_code = FAULT_NONE;
        fault_event_token_id = 64'd0;
        if (!rst && !fault_q) begin
            if (time_now_bad) begin
                fault_event = 1'b1;
                fault_event_code = FAULT_TIME_REGRESSION;
            end else if (cancel && context_busy) begin
                fault_event = 1'b1;
                fault_event_code = FAULT_CANCELLED_OR_DISABLED;
            end else if (enable_q && !enable && context_busy) begin
                fault_event = 1'b1;
                fault_event_code = FAULT_CANCELLED_OR_DISABLED;
            end else if (arm_attempt && !arm_conditions_ok) begin
                fault_event = 1'b1;
                fault_event_code = FAULT_BUSY_ARM;
            end else if (token_active_q
                    && (held_mismatch || ingress_mismatch || q_in_invalid)) begin
                fault_event = 1'b1;
                fault_event_code = FAULT_IDENTITY;
            end else if (slot_expired) begin
                fault_event = 1'b1;
                fault_event_code = FAULT_MISSED_SLOT;
            end else if (bind_candidate && !token_checks_ok) begin
                fault_event = 1'b1;
                fault_event_code = token_bind_fault;
            end

            if (fault_event) begin
                if (token_active_q) begin
                    fault_event_token_id = bound_token_id_q;
                end else if (bind_candidate) begin
                    fault_event_token_id = token_id;
                end
            end
        end
    end

    assign token_ready = bind_candidate && token_checks_ok && !fault_event;
    assign clear_allowed = clear_fault
                        && fault_q
                        && !token_valid
                        && !token_active_q
                        && core_empty
                        && downstream_quiescent;

    assign q_flush = fault_q;
    assign q_enable = token_active_q
                   && credits_loaded_q
                   && armed_q
                   && enable
                   && !fault_q
                   && !cancel
                   && !time_now_bad;
    assign q_eligible_mask = (bound_class_q == 2'd0) ? 3'b001
                           : (bound_class_q == 2'd1) ? 3'b010
                           : 3'b000;

    deepeye_q012_scheduler #(
        .DESC_W(64),
        .CREDIT_W(16),
        .DEPTH(4),
        .MAX_Q0_BURST(4),
        .MAX_NON_Q2_BURST(8),
        .STAT_W(32)
    ) u_q012_scheduler (
        .clk(clk),
        .rst(rst),
        .flush(q_flush),
        .enable(q_enable),
        .in_valid(q_in_valid),
        .in_class(in_class),
        .in_desc(in_desc),
        .in_cost(in_cost),
        .in_ready(q_in_ready),
        .in_invalid(q_in_invalid),
        .credit_load_valid(q_credit_load_valid),
        .credit_load_value(bound_cost_q),
        .credit_load_ready(q_credit_load_ready),
        .eligible_mask(q_eligible_mask),
        .out_valid(q_out_valid),
        .out_ready(q_out_ready),
        .out_class(q_out_class),
        .out_desc(q_out_desc),
        .out_cost(q_out_cost),
        .credits_remaining(q_credits_remaining),
        .count_q0(q_count_q0),
        .count_q1(q_count_q1),
        .count_q2(q_count_q2),
        .accepted_count(q_accepted_count),
        .sent_count(q_sent_count),
        .flushed_count(q_flushed_count)
    );

    always_ff @(posedge clk) begin
        if (rst) begin
            armed_q <= 1'b0;
            arm_q <= arm;
            enable_q <= enable;
            fault_q <= 1'b0;
            fault_code_q <= FAULT_NONE;
            fault_token_id_q <= 64'd0;
            last_forwarded_token_id_q <= 64'd0;

            token_active_q <= 1'b0;
            credits_loaded_q <= 1'b0;
            descriptor_present_q <= 1'b0;
            token_clear_seen_q <= 1'b0;

            bound_token_id_q <= 64'd0;
            bound_desc_q <= 64'd0;
            bound_class_q <= 2'd0;
            bound_cost_q <= 16'd0;
            bound_start_q <= 64'd0;

            last_id_valid_q <= 1'b0;
            last_id_q <= 64'd0;
            profile_lock_q <= 1'b0;
            profile_context_q <= 2'd0;
            window_seen_q <= 1'b0;
            window_closed_q <= 1'b0;
            used_roles_q <= 8'h00;
            current_origin_q <= 64'd0;
            current_window_end_q <= 64'd0;
            time_seen_q <= 1'b0;
            last_now_q <= 64'd0;
        end else begin
            arm_q <= arm;
            enable_q <= enable;

            if (fault_q) begin
                if (clear_allowed) begin
                    fault_q <= 1'b0;
                    fault_code_q <= FAULT_NONE;
                    fault_token_id_q <= 64'd0;
                    armed_q <= 1'b0;
                    token_active_q <= 1'b0;
                    credits_loaded_q <= 1'b0;
                    descriptor_present_q <= 1'b0;
                    token_clear_seen_q <= 1'b1;
                end
            end else if (fault_event) begin
                fault_q <= 1'b1;
                fault_code_q <= fault_event_code;
                fault_token_id_q <= fault_event_token_id;
                armed_q <= 1'b0;
                token_active_q <= 1'b0;
                credits_loaded_q <= 1'b0;
                descriptor_present_q <= 1'b0;
                token_clear_seen_q <= 1'b0;
                if (window_seen_q)
                    window_closed_q <= 1'b1;
            end else begin
                if (arm_success) begin
                    armed_q <= 1'b1;
                end

                if (token_valid && token_ready) begin
                    token_active_q <= 1'b1;
                    credits_loaded_q <= 1'b0;
                    descriptor_present_q <= 1'b0;
                    token_clear_seen_q <= 1'b0;
                    bound_token_id_q <= token_id;
                    bound_desc_q <= token_desc;
                    bound_class_q <= token_class;
                    bound_cost_q <= token_cost;
                    bound_start_q <= start_ext[63:0];

                    last_id_valid_q <= 1'b1;
                    last_id_q <= token_id;
                    profile_lock_q <= 1'b1;
                    profile_context_q <= token_profile_id;
                    window_seen_q <= 1'b1;
                    window_closed_q <= 1'b0;
                    used_roles_q <= effective_used_roles | requested_role_mask;
                    current_origin_q <= window_origin_ns;
                    current_window_end_q <= window_end_ext[63:0];
                end

                if (load_accept)
                    credits_loaded_q <= 1'b1;
                if (in_accept)
                    descriptor_present_q <= 1'b1;
                if (fire) begin
                    token_active_q <= 1'b0;
                    credits_loaded_q <= 1'b0;
                    descriptor_present_q <= 1'b0;
                    last_forwarded_token_id_q <= bound_token_id_q;
                end

                if (!token_valid)
                    token_clear_seen_q <= 1'b1;

            end

            if (!now_ns[63]
                    && (!time_seen_q || (now_ns >= last_now_q))) begin
                last_now_q <= now_ns;
                time_seen_q <= 1'b1;
            end
        end
    end

    assign armed = armed_q;
    assign fault_valid = fault_q;
    assign fault_code = fault_code_q;
    assign fault_token_id = fault_token_id_q;
    assign forward_pulse = fire;
    assign forwarded_token_id = fire ? bound_token_id_q
                                     : last_forwarded_token_id_q;
    assign out_desc = q_out_desc;
    assign out_class = q_out_class;
    assign out_cost = q_out_cost;
    assign used_roles = used_roles_q;
    assign credits_remaining = q_credits_remaining;
    assign count_q0 = q_count_q0;
    assign count_q1 = q_count_q1;
    assign count_q2 = q_count_q2;
    assign accepted_count = q_accepted_count;
    assign sent_count = q_sent_count;
    assign flushed_count = q_flushed_count;

endmodule

`default_nettype wire
