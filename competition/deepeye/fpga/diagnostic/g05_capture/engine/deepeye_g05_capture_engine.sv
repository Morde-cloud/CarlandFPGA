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
    deepeye_atomic_pwm #(.COUNT_W(32), .TAG_W(64)) u_pwm (
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
    // Exact nonwrapping successor, expressed as eight independent byte cases.
    // Below the incremented byte a must be FF and b zero; above it bytes
    // must match. The local nine-bit addition rejects carry past the last byte.
    // This avoids a serial 62-bit carry chain in the joined-witness comparator.
    function automatic logic successor64(input logic [63:0] a, input logic [63:0] b);
        logic [7:0] equal_bytes, a_full, b_zero, local_step, cases;
        begin
            for (integer j=0; j<8; j=j+1) begin
                equal_bytes[j] = a[8*j +: 8] == b[8*j +: 8];
                a_full[j] = &a[8*j +: 8];
                b_zero[j] = ~|b[8*j +: 8];
                local_step[j] = ({1'b0,a[8*j +: 8]} + 9'd1) == {1'b0,b[8*j +: 8]};
            end
            for (integer j=0; j<8; j=j+1)
                cases[j] = local_step[j] &&
                    (&(equal_bytes | (8'hff >> (7-j)))) &&
                    (&(a_full | (8'hff << j))) && (&(b_zero | (8'hff << j)));
            successor64 = |cases;
        end
    endfunction
    // For equal high groups only low-bit 0/3 pairs differ by three. Adjacent
    // high groups require low(a)>=low(b)+2; successor64 never wraps.
    function automatic logic near_two64(input logic [63:0] a, input logic [63:0] b);
        begin
            near_two64 = ((a[63:2] == b[63:2]) &&
                          !((a[1:0] == 2'd0 && b[1:0] == 2'd3) ||
                            (a[1:0] == 2'd3 && b[1:0] == 2'd0))) ||
                         (successor64({2'b0,a[63:2]}, {2'b0,b[63:2]}) &&
                          ({1'b0,a[1:0]} >= ({1'b0,b[1:0]} + 3'd2))) ||
                         (successor64({2'b0,b[63:2]}, {2'b0,a[63:2]}) &&
                          ({1'b0,b[1:0]} >= ({1'b0,a[1:0]} + 3'd2)));
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
                        cap_high0[i] == 0 || cap_high0[i] >= cap_period[i] ||
                        cap_start[i] == 0 || cap_end[i] <= cap_start[i] ||
                        (cap_end[i]-cap_start[i]) != {32'd0,cap_period[i]} ||
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
    assign pending_watchdog = {1'b0,edge_tick} + ({33'd0,pending_period_q} * 65'd3) + 65'd16;
    // atom_applied is registered: its observed pre-edge cycle_tick IS the
    // previous edge on which PWM actually changed; do not use edge_tick here.
    assign observed_deadline = {1'b0,cycle_tick} + {1'b0,pending_ttl_q};
    assign observed_watchdog = {1'b0,cycle_tick} + ({33'd0,pending_period_q} * 65'd3) + 65'd16;
    assign next_watchdog = {1'b0,edge_tick} + ({33'd0,active_period_q} * 65'd2) + 65'd16;
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
    assign cfg_ready = !rst && !stop && !halted && !pending_q && failure_now == 0;
    assign handshake = cfg_valid && cfg_ready;
    assign atom_cfg_valid = handshake && counts_legal && !accept_arith_bad;
    assign atom_stop = stop || halted || failure_now != 0 || (handshake && (!counts_legal || accept_arith_bad));
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

    always_ff @(posedge clk) begin
        accepted <= 0; rejected <= 0; applied <= 0;
        if (rst) begin
            halted <= 0; fault_code <= 0; cycle_tick <= 0;
            applied_tick <= 0; deadline_tick <= 0; active_tag_q <= 0;
            pending_q <= 0; lifetime_q <= 0; monitor_q <= 0; capture_enabled_q <= 0;
            rearm_wait_q <= 0; rearm_left_q <= 0;
            pending_period_q <= 0; active_period_q <= 0;
            pending_highs_q <= 0; active_highs_q <= 0;
            pending_ttl_q <= 0; pending_tag_q <= 0; watchdog_q <= 0;
            join_valid_q <= 0; previous_ends_q <= 0; previous_join_q <= 0;
            result_valid <= 0; result_seq <= 0; result_tag <= 0; result_tick <= 0;
            result_periods <= 0; result_highs <= 0; result_starts <= 0; result_ends <= 0;
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
                if (stop || failure_now != 0 || (handshake && (!counts_legal || accept_arith_bad))) begin
                    halted <= 1;
                    if (stop) fault_code <= 8'd6;
                    else if (failure_now != 0) fault_code <= failure_now;
                    else if (!counts_legal) fault_code <= 8'd1;
                    else fault_code <= 8'd5;
                    rejected <= handshake && (!counts_legal || accept_arith_bad);
                    pending_q <= 0; lifetime_q <= 0; monitor_q <= 0;
                    capture_enabled_q <= 0; rearm_wait_q <= 0; rearm_left_q <= 0;
                    result_valid <= 0; join_valid_q <= 0; previous_join_q <= 0;
                end else if (handshake) begin
                    accepted <= 1;
                    pending_q <= 1;
                    pending_period_q <= cfg_period; pending_highs_q <= cfg_highs;
                    pending_ttl_q <= cfg_ttl_ticks; pending_tag_q <= cfg_tag;
                    // Old output/deadline remain active until actual apply.
                    result_valid <= 0; join_valid_q <= 0; previous_join_q <= 0;
                    capture_enabled_q <= 0; monitor_q <= 0;
                    rearm_wait_q <= 0; rearm_left_q <= 0;
                end else if (atom_applied) begin
                    pending_q <= 0; lifetime_q <= 1; monitor_q <= 1;
                    active_period_q <= atom_period;
                    active_highs_q <= {atom_high2,atom_high1,atom_high0};
                    watchdog_q <= observed_watchdog[63:0];
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
                            result_valid <= 1; result_seq <= result_seq + 1'b1;
                            result_tag <= active_tag_q; result_tick <= edge_tick;
                            result_periods <= joined_periods; result_highs <= joined_highs;
                            result_starts <= joined_starts; result_ends <= joined_ends;
                            previous_ends_q <= joined_ends; previous_join_q <= 1;
                            join_valid_q <= 0;
                            watchdog_q <= next_watchdog[63:0];
                        end else begin
                            join_valid_q <= joined_valid;
                        end
                    end
                end
            end
        end
    end
endmodule
