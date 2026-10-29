// Private count-level G05 candidate. Main decision revision1, work59 engine.
// H01-H15/revision1 SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Production composition MUST use the main's fixed mapper. No motion authority.
module deepeye_g05_capture_engine (
    input logic clk, rst, stop,
    input logic cfg_valid,
    output logic cfg_ready,
    input logic [31:0] cfg_period,
    input logic [95:0] cfg_highs,
    input logic [63:0] cfg_ttl_ticks, cfg_tag,
    input logic [2:0] capture_async_i,
    output logic [2:0] pwm_o,
    output logic accepted, rejected, applied, running, pending, halted,
    output logic [7:0] fault_code,
    output logic [63:0] cycle_tick, applied_tick, deadline_tick, active_tag,
    output logic result_valid,
    output logic [31:0] result_seq,
    output logic [63:0] result_tag, result_tick,
    output logic [95:0] result_periods, result_highs,
    output logic [191:0] result_starts, result_ends
);
    localparam logic [63:0] TMAX = 64'hffffffffffffffff;
    logic pending_q, lifetime_q, monitor_q, capture_enabled_q;
    logic rearm_wait_q;
    logic [2:0] rearm_left_q;
    logic [31:0] pending_period_q, active_period_q;
    // Exact period-derived constants, updated beside their source period.
    // 3*(2^32-1)+16 < 2^34; reset period0 requires span16.
    logic [33:0] pending_first_span_q, active_next_span_q;
    logic [95:0] pending_highs_q, active_highs_q;
    logic [63:0] pending_ttl_q, pending_tag_q, active_tag_q, watchdog_q;
    logic [2:0] join_valid_q;
    logic [95:0] join_periods_q, join_highs_q;
    logic [191:0] join_starts_q, join_ends_q, previous_ends_q;
    logic previous_join_q;

    // Three distinct external input chains; no connection from pwm_o.
    (* ASYNC_REG = "TRUE" *) logic [2:0] capture_meta_q;
    (* ASYNC_REG = "TRUE" *) logic [2:0] capture_sync_q;
    (* ASYNC_REG = "TRUE" *) logic [2:0] capture_level_q;
    always_ff @(posedge clk) begin
        if (rst) begin
            capture_meta_q <= 0;
            capture_sync_q <= 0;
            capture_level_q <= 0;
        end else begin
            capture_meta_q <= capture_async_i;
            capture_sync_q <= capture_meta_q;
            capture_level_q <= capture_sync_q;
        end
    end

    logic atom_accepted, atom_rejected, atom_applied, atom_frame;
    logic atom_running, atom_pending, atom_ready, atom_stop, atom_cfg_valid;
    logic [31:0] atom_period, atom_high0, atom_high1, atom_high2;
    logic [63:0] atom_tag;
    deepeye_g05_stop_factored_pwm #(.COUNT_W(32), .TAG_W(64)) u_pwm (
        .clk(clk), .rst(rst), .stop(atom_stop), .cfg_valid(atom_cfg_valid),
        .cfg_ready(atom_ready), .cfg_period(cfg_period),
        .cfg_high_yaw(cfg_highs[31:0]), .cfg_high_pitch(cfg_highs[63:32]),
        .cfg_high_speed(cfg_highs[95:64]), .cfg_tag(cfg_tag),
        .accepted(atom_accepted), .rejected(atom_rejected), .applied(atom_applied),
        .frame_start(atom_frame), .running(atom_running), .pending(atom_pending),
        .pwm(pwm_o), .active_period(atom_period), .active_high_yaw(atom_high0),
        .active_high_pitch(atom_high1), .active_high_speed(atom_high2), .active_tag(atom_tag)
    );

    logic cap_stop, cap_rearm;
    logic [2:0] cap_valid, cap_armed, cap_incoherent, cap_period_overflow;
    logic [2:0] cap_witness_overflow, cap_overrun;
    logic [31:0] cap_period [0:2], cap_high0 [0:2], cap_high1 [0:2], cap_high2 [0:2];
    logic [63:0] cap_start [0:2], cap_end [0:2], cap_tag [0:2];
    logic [31:0] cap_start_raw [0:2], cap_end_raw [0:2];
    genvar channel;
    generate for (channel=0; channel<3; channel=channel+1) begin : g_external
        // Production mapper bounds every active window to <=1200000000 ticks.
        // Rearm resets the local witness; STOP/expiry clears it. A 32-bit
        // witness is therefore sufficient, with conservative overflow fault
        // for unsupported much-longer count-level diagnostic windows.
        assign cap_start[channel] = {32'd0,cap_start_raw[channel]};
        assign cap_end[channel] = {32'd0,cap_end_raw[channel]};
        deepeye_pwm_coherent_capture #(.COUNT_W(32), .WITNESS_W(32), .TAG_W(64)) u_capture (
            .clk(clk), .rst(rst), .stop(cap_stop), .rearm(cap_rearm),
            .sample_levels({3{capture_level_q[channel]}}), .window_tag(active_tag_q),
            .out_ready(1'b1), .armed(cap_armed[channel]), .out_valid(cap_valid[channel]),
            .out_period(cap_period[channel]), .out_high0(cap_high0[channel]),
            .out_high1(cap_high1[channel]), .out_high2(cap_high2[channel]),
            .out_start(cap_start_raw[channel]), .out_end(cap_end_raw[channel]), .out_tag(cap_tag[channel]),
            .incoherent_event(cap_incoherent[channel]), .period_overflow_event(cap_period_overflow[channel]),
            .witness_overflow_event(cap_witness_overflow[channel]), .overrun_event(cap_overrun[channel]),
            .incoherent_seen(), .period_overflow_seen(), .witness_overflow_seen(), .overrun_seen(), .fault_count()
        );
    end endgenerate

    function automatic logic near_two(input logic [31:0] a, input logic [31:0] b);
        near_two = near_two64({32'd0,a}, {32'd0,b});
    endfunction

    logic [2:0] joined_valid;
    logic [95:0] joined_periods, joined_highs;
    logic [191:0] joined_starts, joined_ends;
    logic capture_bad, joined_good;
    // R15B exact nonwrapping successor in sixteen independent four-bit groups.
    // Below the incremented group a must be F and b zero; above it groups
    // must match. Local Boolean prefixes reject wrap past the last group.
    // This avoids serial carry inside either the group or the whole witness.
    function automatic logic successor64(input logic [63:0] a, input logic [63:0] b);
        logic [15:0] equal_groups, a_full, b_zero, local_step, cases;
        logic [3:0] av, bv;
        begin
            for (integer j=0; j<16; j=j+1) begin
                av = a[4*j +: 4];
                bv = b[4*j +: 4];
                equal_groups[j] = av == bv;
                a_full[j] = &av;
                b_zero[j] = ~|bv;
                // Four-bit nonwrapping successor, direct Boolean prefixes.
                // No data-dependent + or - carry chain is used.
                local_step[j] = (bv[0] == !av[0]) &&
                                (bv[1] == (av[1] ^ av[0])) &&
                                (bv[2] == (av[2] ^ (av[1] & av[0]))) &&
                                (bv[3] == (av[3] ^ (&av[2:0]))) && !(&av);
            end
            for (integer j=0; j<16; j=j+1)
                cases[j] = local_step[j] &&
                    (&(equal_groups | (16'hffff >> (15-j)))) &&
                    (&(a_full | (16'hffff << j))) &&
                    (&(b_zero | (16'hffff << j)));
            successor64 = |cases;
        end
    endfunction
    // For equal high groups only low-bit 0/3 pairs differ by three. Adjacent
    // high groups require low(a)>=low(b)+2; successor64 never wraps.
    function automatic logic near_two64(input logic [63:0] a, input logic [63:0] b);
        logic [64:0] difference;
        begin
            // Zero extension makes the signed range exactly -(2^64-1)..2^64-1.
            // Positive residues 0,1,2 or negative residues -1,-2 are the only
            // accepted values. No unsigned endpoint can wrap into this set.
            difference = {1'b0,a} - {1'b0,b};
            near_two64 = ((~|difference[64:2]) && difference[1:0] != 2'd3) ||
                         (&difference[64:1]);
        end
    endfunction
    // Compare all data alternatives before choosing by the three slot flags.
    // These kept one-bit predicates keep a late slot/control flag out of the
    // wide witness arithmetic, without adding a clock or changing tolerance.
    (* keep = "TRUE" *) logic [3:0] start_near_choices [0:2], end_near_choices [0:2];
    logic [2:0] selected_start_near, selected_end_near;
    genvar pair_index;
    generate for (pair_index=0; pair_index<3; pair_index=pair_index+1) begin : g_pair_check
        localparam integer A = (pair_index==2) ? 1 : 0;
        localparam integer B = (pair_index==0) ? 1 : 2;
        assign start_near_choices[pair_index][0] = near_two64(cap_start[A], cap_start[B]);
        assign start_near_choices[pair_index][1] = near_two64(cap_start[A], join_starts_q[64*B +: 64]);
        assign start_near_choices[pair_index][2] = near_two64(join_starts_q[64*A +: 64], cap_start[B]);
        assign start_near_choices[pair_index][3] = near_two64(join_starts_q[64*A +: 64], join_starts_q[64*B +: 64]);
        assign end_near_choices[pair_index][0] = near_two64(cap_end[A], cap_end[B]);
        assign end_near_choices[pair_index][1] = near_two64(cap_end[A], join_ends_q[64*B +: 64]);
        assign end_near_choices[pair_index][2] = near_two64(join_ends_q[64*A +: 64], cap_end[B]);
        assign end_near_choices[pair_index][3] = near_two64(join_ends_q[64*A +: 64], join_ends_q[64*B +: 64]);
        assign selected_start_near[pair_index] = start_near_choices[pair_index][{join_valid_q[A],join_valid_q[B]}];
        assign selected_end_near[pair_index] = end_near_choices[pair_index][{join_valid_q[A],join_valid_q[B]}];
    end endgenerate
    always_comb begin
        joined_valid = join_valid_q;
        // A filled slot keeps its immutable payload. An empty slot may look
        // ahead at raw capture data, but joined_valid alone grants eligibility.
        // This keeps reset/STOP/rearm masks out of the wide data comparator.
        // A second capture for a filled slot is still an immediate fault below.
        for (integer i=0; i<3; i=i+1) begin
            joined_periods[32*i +: 32] = join_valid_q[i] ? join_periods_q[32*i +: 32] : cap_period[i];
            joined_highs[32*i +: 32] = join_valid_q[i] ? join_highs_q[32*i +: 32] : cap_high0[i];
            joined_starts[64*i +: 64] = join_valid_q[i] ? join_starts_q[64*i +: 64] : cap_start[i];
            joined_ends[64*i +: 64] = join_valid_q[i] ? join_ends_q[64*i +: 64] : cap_end[i];
        end
        capture_bad = 1'b0;
        if (capture_enabled_q) begin
            if (|(cap_incoherent | cap_period_overflow | cap_witness_overflow | cap_overrun))
                capture_bad = 1'b1;
            for (integer i=0; i<3; i=i+1) begin
                if (cap_valid[i]) begin
                    if (join_valid_q[i] || cap_tag[i] != active_tag_q ||
                        !near_two(cap_period[i], active_period_q) ||
                        !near_two(cap_high0[i], active_highs_q[32*i +: 32]) ||
                        cap_high0[i] != cap_high1[i] || cap_high0[i] != cap_high2[i] ||
                        // The hash-pinned coherent primitive qualifies every
                        // valid record: 0<high<period and 0<start<end with
                        // end-start==period. Its nonwrapping witness/age
                        // construction supplies these invariants. Do not
                        // duplicate wide serial subtraction on the STOP path.
                        (previous_join_q && cap_start[i] != previous_ends_q[64*i +: 64]))
                        capture_bad = 1'b1;
                    joined_valid[i] = 1'b1;
                end
            end
        end
        // For three unsigned values, max-min<=2 iff every unordered pair is near.
        if (capture_enabled_q && (&joined_valid) &&
            (!(&selected_start_near) || !(&selected_end_near))) capture_bad = 1'b1;
        joined_good = capture_enabled_q && (&joined_valid) && !capture_bad;
    end

    logic [63:0] edge_tick;
    logic [64:0] accept_base, accept_deadline, accept_watchdog;
    logic [64:0] pending_deadline, pending_watchdog, observed_deadline, observed_watchdog;
    logic [64:0] next_watchdog;
    logic counts_legal, accept_arith_bad, pending_arith_bad, observed_arith_bad;
    logic old_ttl_due, observed_ttl_due, handshake;
    logic [7:0] failure_now;
    assign edge_tick = (cycle_tick == TMAX) ? TMAX : cycle_tick + 64'd1;
    // Earliest application is the edge after the accepting edge.
    assign accept_base = {1'b0,cycle_tick} + 65'd2;
    assign accept_deadline = accept_base + {1'b0,cfg_ttl_ticks};
    assign accept_watchdog = accept_base + ({33'd0,cfg_period} * 65'd3) + 65'd16;
    assign pending_deadline = {1'b0,edge_tick} + {1'b0,pending_ttl_q};
    assign pending_watchdog = {1'b0,edge_tick} + {31'd0,pending_first_span_q};
    // atom_applied is registered: its observed pre-edge cycle_tick IS the
    // previous edge on which PWM actually changed; do not use edge_tick here.
    assign observed_deadline = {1'b0,cycle_tick} + {1'b0,pending_ttl_q};
    assign observed_watchdog = {1'b0,cycle_tick} + {31'd0,pending_first_span_q};
    assign next_watchdog = {1'b0,edge_tick} + {31'd0,active_next_span_q};
    assign counts_legal = cfg_period >= 32'd32 && cfg_ttl_ticks != 0 &&
        cfg_highs[31:0] != 0 && cfg_highs[31:0] < cfg_period &&
        cfg_highs[63:32] != 0 && cfg_highs[63:32] < cfg_period &&
        cfg_highs[95:64] != 0 && cfg_highs[95:64] < cfg_period;
    assign accept_arith_bad = accept_deadline[64] || accept_watchdog[64];
    assign pending_arith_bad = pending_q && !atom_applied && (pending_deadline[64] || pending_watchdog[64]);
    assign observed_arith_bad = atom_applied && (observed_deadline[64] || observed_watchdog[64]);
    // The old deadline still gates the ACTUAL applying edge. Once an actual
    // application has occurred, its delayed notification retires the old TTL.
    assign old_ttl_due = lifetime_q && !atom_applied && edge_tick >= deadline_tick;
    assign observed_ttl_due = atom_applied && !observed_arith_bad && edge_tick >= observed_deadline[63:0];
    always_comb begin
        failure_now = 0;
        if (cycle_tick == TMAX) failure_now = 8'd5;
        else if (old_ttl_due || observed_ttl_due) failure_now = 8'd2;
        else if (pending_arith_bad || observed_arith_bad) failure_now = 8'd5;
        else if (atom_applied && (!pending_q || atom_period != pending_period_q ||
                 {atom_high2,atom_high1,atom_high0} != pending_highs_q || atom_tag != pending_tag_q))
            failure_now = 8'd3;
        else if (atom_rejected || capture_bad) failure_now = 8'd3;
        else if (joined_good && (result_seq == 32'hffffffff || next_watchdog[64])) failure_now = 8'd5;
        else if (monitor_q && !pending_q && !atom_applied && edge_tick >= watchdog_q && !joined_good)
            failure_now = 8'd4;
    end
    // Fault presence is a parallel reduction, not a decode of priority reason.
    // The reason encoder above is retained verbatim for the fault evidence FF.
    logic failure_any, command_offer;
    assign failure_any = cycle_tick == TMAX || old_ttl_due || observed_ttl_due ||
        pending_arith_bad || observed_arith_bad ||
        (atom_applied && (!pending_q || atom_period != pending_period_q ||
         {atom_high2,atom_high1,atom_high0} != pending_highs_q || atom_tag != pending_tag_q)) ||
        atom_rejected || capture_bad ||
        (joined_good && (result_seq == 32'hffffffff || next_watchdog[64])) ||
        (monitor_q && !pending_q && !atom_applied && edge_tick >= watchdog_q && !joined_good);
    assign command_offer = cfg_valid && !rst && !stop && !halted && !pending_q;
    // R17 public payload enable. With joined_good true, capture_bad and
    // the missing-join watchdog term are false. With command_offer false,
    // handshake and its invalid-count branch cannot preempt publication.
    // Keep every other fault guard, reset/STOP, halt and application priority.
    // This is exactly the old payload-write predicate, not speculative data.
    (* keep = "TRUE" *) logic result_payload_ce;
    assign result_payload_ce = !rst && !stop && !halted &&
        !command_offer && !atom_applied && joined_good &&
        !(cycle_tick == TMAX || old_ttl_due || observed_ttl_due ||
          pending_arith_bad || observed_arith_bad || atom_rejected ||
          result_seq == 32'hffffffff || next_watchdog[64]);
    assign cfg_ready = !rst && !stop && !halted && !pending_q && !failure_any;
    assign handshake = cfg_valid && cfg_ready;
    // When failure_any is high atom_stop is high. The immutable PWM primitive
    // gates cfg_ready/apply_now by stop and its sequential STOP branch wins.
    // Therefore passing the offer here does not permit an acceptance, while
    // avoiding a second failure-dependent path through PWM payload admission.
    assign atom_cfg_valid = command_offer && counts_legal && !accept_arith_bad;
    assign atom_stop = stop || halted || failure_any || (command_offer && (!counts_legal || accept_arith_bad));
    assign running = atom_running && !halted;
    assign pending = pending_q;
    // Expose actual new identity immediately with the primitive's event, then
    // retain it for terminal evidence after the primitive is stopped/cleared.
    assign active_tag = atom_applied ? atom_tag : active_tag_q;
    // Main revision1 permits A+5 or later. Use A+7: the event observed at
    // A+1 sets six, flushing three FFs plus up to two ticks of pin skew and
    // the primitive's sampling edge before taking a shared baseline.
    // Rearm is scheduled solely by registered state and external reset/STOP.
    // failure_now consumes capture out_valid, which is masked by rearm/stop;
    // feeding it back here formed a combinational loop. Terminal failure still
    // wins the engine's same-edge sequential branch and immediately stops PWM.
    // If due on this internal rearm edge, halted suppresses capture next cycle;
    // no record or command is made eligible by this internal baseline action.
    assign cap_rearm = rearm_wait_q && rearm_left_q == 3'd1 && !rst && !stop && !halted;
    assign cap_stop = stop || halted || pending_q || (!capture_enabled_q && !cap_rearm);

    // R14 private payload banks. These registers are speculative unless the
    // unchanged control path qualifies and uses them. No failure, capture_bad,
    // or joined_good term gates their update; reset still clears every bit.
    // A legal handshake and a qualifying atom application retain the original
    // priorities, while a fault/STOP retires the bank before any later use.
    always_ff @(posedge clk) begin
        if (rst) begin
            pending_period_q <= 0; pending_highs_q <= 0;
            pending_first_span_q <= 34'd16;
            pending_ttl_q <= 0; pending_tag_q <= 0;
            active_period_q <= 0; active_highs_q <= 0;
            active_next_span_q <= 34'd16;
            watchdog_q <= 0; previous_ends_q <= 0;
        end else begin
            if (!halted && command_offer) begin
                pending_period_q <= cfg_period; pending_highs_q <= cfg_highs;
                pending_first_span_q <= ({2'b0,cfg_period} * 34'd3) + 34'd16;
                pending_ttl_q <= cfg_ttl_ticks; pending_tag_q <= cfg_tag;
            end
            if (!halted && !command_offer) begin
                if (atom_applied) begin
                    active_period_q <= atom_period;
                    active_next_span_q <= {1'b0,atom_period,1'b0} + 34'd16;
                    active_highs_q <= {atom_high2,atom_high1,atom_high0};
                    watchdog_q <= observed_watchdog[63:0];
                end else if (capture_enabled_q && (&joined_valid)) begin
                    watchdog_q <= next_watchdog[63:0];
                    previous_ends_q <= joined_ends;
                end
            end
        end
    end

    // Only validity/control state retires on STOP/fault/command transitions.
    // Empty-slot data is unobservable and can track the raw input continuously;
    // filled-slot data selects itself. Thus the wide payload bank needs no
    // capture-fault-derived shared enable, while reset still clears every bit.
    always_ff @(posedge clk) begin
        if (rst) begin
            join_periods_q <= 0; join_highs_q <= 0;
            join_starts_q <= 0; join_ends_q <= 0;
        end else begin
            join_periods_q <= joined_periods; join_highs_q <= joined_highs;
            join_starts_q <= joined_starts; join_ends_q <= joined_ends;
        end
    end

    // Public result payload retains exactly its old write/reset/hold behavior.
    // A dedicated direct enable avoids the shared priority/handshake cone.
    always_ff @(posedge clk) begin
        if (rst) begin
            result_seq <= 0; result_tag <= 0; result_tick <= 0;
            result_periods <= 0; result_highs <= 0; result_starts <= 0; result_ends <= 0;
        end else if (result_payload_ce) begin
            result_seq <= result_seq + 1'b1;
            result_tag <= active_tag_q; result_tick <= edge_tick;
            result_periods <= joined_periods; result_highs <= joined_highs;
            result_starts <= joined_starts; result_ends <= joined_ends;
        end
    end

    always_ff @(posedge clk) begin
        accepted <= 0; rejected <= 0; applied <= 0;
        if (rst) begin
            halted <= 0; fault_code <= 0; cycle_tick <= 0;
            applied_tick <= 0; deadline_tick <= 0; active_tag_q <= 0;
            pending_q <= 0; lifetime_q <= 0; monitor_q <= 0; capture_enabled_q <= 0;
            rearm_wait_q <= 0; rearm_left_q <= 0;
            join_valid_q <= 0; previous_join_q <= 0;
            result_valid <= 0;
        end else begin
            cycle_tick <= edge_tick;
            if (!halted) begin
                // Even a TTL=1 expiry or STOP at A+1 preserves the actual A
                // application event and timestamp; reset alone clears evidence.
                if (atom_applied) begin
                    applied <= 1;
                    applied_tick <= cycle_tick;
                    deadline_tick <= observed_deadline[63:0];
                    active_tag_q <= atom_tag;
                end
                if (stop || failure_any || (handshake && (!counts_legal || accept_arith_bad))) begin
                    halted <= 1;
                    if (stop) fault_code <= 8'd6;
                    else if (failure_any) fault_code <= failure_now;
                    else if (!counts_legal) fault_code <= 8'd1;
                    else fault_code <= 8'd5;
                    rejected <= handshake && (!counts_legal || accept_arith_bad);
                    pending_q <= 0; lifetime_q <= 0; monitor_q <= 0;
                    capture_enabled_q <= 0; rearm_wait_q <= 0; rearm_left_q <= 0;
                    result_valid <= 0; join_valid_q <= 0; previous_join_q <= 0;
                end else if (handshake) begin
                    accepted <= 1;
                    pending_q <= 1;
                    // Old output/deadline remain active until actual apply.
                    result_valid <= 0; join_valid_q <= 0; previous_join_q <= 0;
                    capture_enabled_q <= 0; monitor_q <= 0;
                    rearm_wait_q <= 0; rearm_left_q <= 0;
                end else if (atom_applied) begin
                    pending_q <= 0; lifetime_q <= 1; monitor_q <= 1;
                    rearm_wait_q <= 1; rearm_left_q <= 6;
                    capture_enabled_q <= 0; join_valid_q <= 0; previous_join_q <= 0;
                    result_valid <= 0;
                end else begin
                    if (rearm_wait_q) begin
                        if (rearm_left_q == 1) begin
                            rearm_wait_q <= 0; rearm_left_q <= 0;
                            capture_enabled_q <= 1;
                            join_valid_q <= 0; previous_join_q <= 0;
                        end else rearm_left_q <= rearm_left_q - 1'b1;
                    end
                    if (capture_enabled_q) begin
                        if (joined_good) begin
                            result_valid <= 1;
                            previous_join_q <= 1;
                            join_valid_q <= 0;
                        end else begin
                            join_valid_q <= joined_valid;
                        end
                    end
                end
            end
        end
    end
endmodule

// G05 private STOP-factored copy of immutable atomic PWM SHA256
// 9dc8ecf96e59a2ae8467bda64572f62eb602d52db535733f236f64ff97c43428.
// Only the two inner branch predicates omit rst/stop already excluded by the
// outer synchronous reset/STOP branch. Registers/public timing are unchanged.
// This is a new G05 implementation, not reused operation12 acceptance.
module deepeye_g05_stop_factored_pwm #(
    parameter integer COUNT_W = 32,
    parameter integer TAG_W   = 32
) (
    input  logic                   clk,
    input  logic                   rst,
    input  logic                   stop,
    input  logic                   cfg_valid,
    output logic                   cfg_ready,
    input  logic [COUNT_W-1:0]     cfg_period,
    input  logic [COUNT_W-1:0]     cfg_high_yaw,
    input  logic [COUNT_W-1:0]     cfg_high_pitch,
    input  logic [COUNT_W-1:0]     cfg_high_speed,
    input  logic [TAG_W-1:0]       cfg_tag,
    output logic                   accepted,
    output logic                   rejected,
    output logic                   applied,
    output logic                   frame_start,
    output logic                   running,
    output logic                   pending,
    output logic [2:0]             pwm,
    output logic [COUNT_W-1:0]     active_period,
    output logic [COUNT_W-1:0]     active_high_yaw,
    output logic [COUNT_W-1:0]     active_high_pitch,
    output logic [COUNT_W-1:0]     active_high_speed,
    output logic [TAG_W-1:0]       active_tag
);

    localparam logic [COUNT_W-1:0] COUNT_ZERO = '0;
    localparam logic [TAG_W-1:0]   TAG_ZERO   = '0;

    logic                         running_q;
    logic                         pending_q;
    logic [COUNT_W-1:0]           phase_q;
    logic [COUNT_W-1:0]           active_period_q;
    logic [COUNT_W-1:0]           active_high_yaw_q;
    logic [COUNT_W-1:0]           active_high_pitch_q;
    logic [COUNT_W-1:0]           active_high_speed_q;
    logic [TAG_W-1:0]             active_tag_q;
    logic [COUNT_W-1:0]           pending_period_q;
    logic [COUNT_W-1:0]           pending_high_yaw_q;
    logic [COUNT_W-1:0]           pending_high_pitch_q;
    logic [COUNT_W-1:0]           pending_high_speed_q;
    logic [TAG_W-1:0]             pending_tag_q;
    logic [2:0]                   pwm_q;
    logic                         accepted_q;
    logic                         rejected_q;
    logic                         applied_q;
    logic                         frame_start_q;

    logic                         boundary_now;
    logic                         apply_now;
    logic                         transfer_now;
    logic                         payload_legal;

    assign cfg_ready = !rst && !stop && !pending_q;
    assign running     = running_q;
    assign pending     = pending_q;
    assign pwm         = pwm_q;
    assign accepted    = accepted_q;
    assign rejected    = rejected_q;
    assign applied     = applied_q;
    assign frame_start = frame_start_q;
    assign active_period     = active_period_q;
    assign active_high_yaw   = active_high_yaw_q;
    assign active_high_pitch = active_high_pitch_q;
    assign active_high_speed = active_high_speed_q;
    assign active_tag        = active_tag_q;

    assign boundary_now = running_q &&
                          ((phase_q + 1'b1) == active_period_q);
    assign apply_now    = !rst && !stop && pending_q &&
                          (!running_q || boundary_now);
    assign transfer_now = cfg_valid && cfg_ready;
    assign payload_legal = (cfg_period != COUNT_ZERO) &&
                           (cfg_high_yaw <= cfg_period) &&
                           (cfg_high_pitch <= cfg_period) &&
                           (cfg_high_speed <= cfg_period);

    always_ff @(posedge clk) begin
        accepted_q    <= 1'b0;
        rejected_q    <= 1'b0;
        applied_q     <= 1'b0;
        frame_start_q <= 1'b0;

        if (rst || stop) begin
            running_q            <= 1'b0;
            pending_q            <= 1'b0;
            phase_q              <= COUNT_ZERO;
            active_period_q      <= COUNT_ZERO;
            active_high_yaw_q    <= COUNT_ZERO;
            active_high_pitch_q  <= COUNT_ZERO;
            active_high_speed_q  <= COUNT_ZERO;
            active_tag_q         <= TAG_ZERO;
            pending_period_q     <= COUNT_ZERO;
            pending_high_yaw_q   <= COUNT_ZERO;
            pending_high_pitch_q <= COUNT_ZERO;
            pending_high_speed_q <= COUNT_ZERO;
            pending_tag_q        <= TAG_ZERO;
            pwm_q                <= 3'b000;
        end else if (pending_q && (!running_q || boundary_now)) begin
            running_q            <= 1'b1;
            pending_q            <= 1'b0;
            phase_q              <= COUNT_ZERO;
            active_period_q      <= pending_period_q;
            active_high_yaw_q    <= pending_high_yaw_q;
            active_high_pitch_q  <= pending_high_pitch_q;
            active_high_speed_q  <= pending_high_speed_q;
            active_tag_q         <= pending_tag_q;
            pending_period_q     <= COUNT_ZERO;
            pending_high_yaw_q   <= COUNT_ZERO;
            pending_high_pitch_q <= COUNT_ZERO;
            pending_high_speed_q <= COUNT_ZERO;
            pending_tag_q        <= TAG_ZERO;
            pwm_q                <= {pending_high_speed_q != COUNT_ZERO,
                                     pending_high_pitch_q != COUNT_ZERO,
                                     pending_high_yaw_q   != COUNT_ZERO};
            applied_q            <= 1'b1;
            frame_start_q        <= 1'b1;
        end else begin
            if (running_q) begin
                if (boundary_now) begin
                    phase_q       <= COUNT_ZERO;
                    pwm_q         <= {active_high_speed_q != COUNT_ZERO,
                                      active_high_pitch_q != COUNT_ZERO,
                                      active_high_yaw_q   != COUNT_ZERO};
                    frame_start_q <= 1'b1;
                end else begin
                    phase_q <= phase_q + 1'b1;
                    pwm_q   <= {((phase_q + 1'b1) < active_high_speed_q),
                                ((phase_q + 1'b1) < active_high_pitch_q),
                                ((phase_q + 1'b1) < active_high_yaw_q)};
                end
            end else begin
                phase_q <= COUNT_ZERO;
                pwm_q   <= 3'b000;
            end

            if (cfg_valid && !pending_q) begin
                if (payload_legal) begin
                    accepted_q           <= 1'b1;
                    pending_q            <= 1'b1;
                    pending_period_q     <= cfg_period;
                    pending_high_yaw_q   <= cfg_high_yaw;
                    pending_high_pitch_q <= cfg_high_pitch;
                    pending_high_speed_q <= cfg_high_speed;
                    pending_tag_q        <= cfg_tag;
                end else begin
                    rejected_q <= 1'b1;
                end
            end
        end
    end

    // Parameter rejection is a simulator diagnostic, not synthesized hardware.
    // synthesis translate_off
    generate
        if ((COUNT_W < 2) || (COUNT_W > 32) || (TAG_W < 1) || (TAG_W > 64)) begin : g_param_guard
            initial begin
                $fatal(1,
                       "ATOMIC_PWM_UNSUPPORTED_PARAMETERS COUNT_W=%0d TAG_W=%0d",
                       COUNT_W, TAG_W);
            end
        end
    endgenerate
    // synthesis translate_on

endmodule
