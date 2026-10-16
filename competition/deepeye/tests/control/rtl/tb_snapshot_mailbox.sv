// Directed + fixed-seed randomized testbench for deepeye_snapshot_mailbox.
//
// Work: B-SNAPSHOT-CDC-CANDIDATE-20261017-06-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
//
// External-port oracle only: src_valid/src_ready/src_data and
// dst_valid/dst_ready/dst_data. Internal req/ack are never an acceptance
// oracle. A watchdog timeout and every checker error are fatal, so a hang or
// a mismatch can never pass. Clock edges land on integer ns; every testbench
// stimulus or reset change lands on a half-integer ns or on a quiet clock
// negedge, so stimulus never races a sampling edge.
//
// Machine-readable transcript lines (Tcl puts without '# ', $display with):
//   TB_CASE_BEGIN case=<name> width=<W>
//   TB_CASE case=<name> width=<W> accepted=<n> delivered=<n> discarded=<n> errors=<n>
//   TB_EVT case=<name> width=<W> kind=accept data=<hex>
//   TB_EVT case=<name> width=<W> kind=deliver data=<hex>
//   TB_EVT case=<name> width=<W> kind=flush reason=<both|src_reset|dst_reset> discarded=<n>
//   TB_SUMMARY width=<W> accepted=<n> delivered=<n> discarded=<n> ...
//   TB_DONE width=<W>

`timescale 1ns / 1ps

module tb_snapshot_mailbox #(
    parameter integer WIDTH = 256
) ();

    localparam integer SRC_HALF        = 5;
    localparam integer DST_HALF        = 7;
    localparam integer DST_PHASE       = 3;
    localparam integer QDEPTH          = 8;
    localparam integer TB_WATCHDOG_NS  = 1200000;
    localparam integer SOAK_STEPS      = 400;

    reg src_clk    = 1'b0;
    reg dst_clk    = 1'b0;
    reg src_clk_en = 1'b1;
    reg dst_clk_en = 1'b1;

    initial begin : src_clock_gen
        src_clk = 1'b0;
        forever begin
            #(SRC_HALF);
            if (src_clk_en) src_clk = ~src_clk;
        end
    end

    initial begin : dst_clock_gen
        dst_clk = 1'b0;
        #(DST_PHASE);
        forever begin
            #(DST_HALF);
            if (dst_clk_en) dst_clk = ~dst_clk;
        end
    end

    reg              src_reset_n = 1'b0;
    reg              dst_reset_n = 1'b0;
    reg              src_valid   = 1'b0;
    reg  [WIDTH-1:0] src_data    = {WIDTH{1'b0}};
    reg              dst_ready   = 1'b0;

    wire             src_ready;
    wire             src_online;
    wire             dst_valid;
    wire [WIDTH-1:0] dst_data;
    wire             dst_online;

    deepeye_snapshot_mailbox #(.WIDTH(WIDTH)) u_dut (
        .src_clk(src_clk),
        .src_reset_n(src_reset_n),
        .src_valid(src_valid),
        .src_ready(src_ready),
        .src_data(src_data),
        .src_online(src_online),
        .dst_clk(dst_clk),
        .dst_reset_n(dst_reset_n),
        .dst_valid(dst_valid),
        .dst_ready(dst_ready),
        .dst_data(dst_data),
        .dst_online(dst_online)
    );

    wire common_reset_n = src_reset_n & dst_reset_n;

    reg [WIDTH-1:0] expect_q [0:QDEPTH-1];
    integer q_head = 0;
    integer q_tail = 0;
    integer q_count = 0;
    integer accepted_total  = 0;
    integer delivered_total = 0;
    integer discarded_total = 0;
    integer flush_events    = 0;
    integer src_reset_drops = 0;
    integer dst_reset_drops = 0;
    integer tb_errors       = 0;
    integer last_flush_discarded = 0;
    reg     flush_seen = 1'b1;

    string  current_case  = "initial";
    integer case_acc_base = 0;
    integer case_del_base = 0;
    integer case_disc_base = 0;
    integer case_err_base  = 0;

    integer directed_acc_total  = 0;
    integer directed_del_total  = 0;
    integer directed_disc_total = 0;

    reg [63:0] rng_state = 64'h20261017DEE90001;
    reg [63:0] r;
    integer i;
    integer soak_step;
    integer soak_accepts_at_offer = 0;
    integer drain_guard;

    function automatic [63:0] rng_next();
        reg [63:0] x;
        begin
            x = rng_state;
            x = x ^ (x << 13);
            x = x ^ (x >> 7);
            x = x ^ (x << 17);
            rng_state = x;
            rng_next = x;
        end
    endfunction

    function automatic real rnd01(input [63:0] v);
        rnd01 = (v % 41) + 0.5;
    endfunction

    function automatic [WIDTH-1:0] pattern(input integer unsigned seq);
        reg [63:0] mixed;
        reg [1023:0] wide;
        integer k;
        begin
            mixed = ({32'b0, seq} * 64'h9E3779B97F4A7C15) ^ 64'hA5A55A5AC3C33C3C;
            wide = 1024'b0;
            for (k = 0; k < 1024; k = k + 64) wide[k +: 64] = mixed;
            pattern = wide[WIDTH-1:0];
        end
    endfunction

    task automatic tb_fail(input string message);
        begin
            tb_errors = tb_errors + 1;
            $display("TB_ERROR %0d %s", tb_errors, message);
            $fatal(1, "TB_FAILURE");
        end
    endtask

    task automatic tb_event_data(input string kind, input [WIDTH-1:0] data);
        begin
            $display("TB_EVT case=%s width=%0d kind=%s data=%h", current_case, WIDTH, kind, data);
        end
    endtask

    task automatic tb_event_flush(input string reason, input integer discarded_now);
        begin
            $display("TB_EVT case=%s width=%0d kind=flush reason=%s discarded=%0d accepted=%0d delivered=%0d",
                     current_case, WIDTH, reason, discarded_now, accepted_total, delivered_total);
        end
    endtask

    always @(posedge src_clk) begin
        if (src_valid === 1'b1 && src_ready === 1'b1) begin
            if ((accepted_total - delivered_total - discarded_total) !== 0) begin
                tb_fail("accepted while a snapshot is outstanding");
            end
            expect_q[q_tail % QDEPTH] = src_data;
            q_tail = q_tail + 1;
            q_count = q_count + 1;
            accepted_total = accepted_total + 1;
            tb_event_data("accept", src_data);
        end
    end

    always @(posedge dst_clk) begin
        if (dst_valid === 1'b1 && dst_ready === 1'b1) begin
            if (q_count <= 0) begin
                tb_fail("delivered with no outstanding snapshot (phantom)");
            end else if (expect_q[q_head % QDEPTH] !== dst_data) begin
                tb_fail("delivered data mismatch (stale or torn)");
            end else begin
                q_head = q_head + 1;
                q_count = q_count - 1;
                delivered_total = delivered_total + 1;
                tb_event_data("deliver", dst_data);
            end
        end
    end

    reg             stall_seen = 1'b0;
    reg [WIDTH-1:0] stall_data = {WIDTH{1'b0}};

    always @(posedge dst_clk or negedge common_reset_n) begin
        if (!common_reset_n) begin
            stall_seen <= 1'b0;
        end else begin
            if (stall_seen === 1'b1) begin
                if (dst_valid !== 1'b1) begin
                    tb_fail("dst_valid dropped while stalled without consumption");
                end else if (dst_ready !== 1'b1) begin
                    if (dst_data !== stall_data) begin
                        tb_fail("dst_data changed while dst_valid && !dst_ready");
                    end
                end
            end
            if (dst_valid === 1'b1 && dst_ready !== 1'b1) begin
                stall_seen <= 1'b1;
                stall_data <= dst_data;
            end else begin
                stall_seen <= 1'b0;
            end
        end
    end

    always @(negedge src_reset_n) src_reset_drops = src_reset_drops + 1;
    always @(negedge dst_reset_n) dst_reset_drops = dst_reset_drops + 1;

    always @(common_reset_n) begin
        if (common_reset_n === 1'b0 && flush_seen === 1'b0) begin
            flush_seen = 1'b1;
            flush_events = flush_events + 1;
            last_flush_discarded = 0;
            while (q_count > 0) begin
                q_head = q_head + 1;
                q_count = q_count - 1;
                last_flush_discarded = last_flush_discarded + 1;
            end
            discarded_total = discarded_total + last_flush_discarded;
            if (src_reset_n === 1'b0 && dst_reset_n === 1'b0) tb_event_flush("both", last_flush_discarded);
            else if (src_reset_n === 1'b0) tb_event_flush("src_reset", last_flush_discarded);
            else tb_event_flush("dst_reset", last_flush_discarded);
        end else if (common_reset_n === 1'b1) begin
            flush_seen = 1'b0;
        end
    end

    initial begin : tb_watchdog
        #(TB_WATCHDOG_NS);
        $display("TB_ERROR watchdog timeout at %0t", $time);
        $fatal(1, "TB_WATCHDOG_TIMEOUT");
    end

    task automatic stop_src_clock();
        @(negedge src_clk);
        src_clk_en = 1'b0;
    endtask

    task automatic resume_src_clock();
        src_clk_en = 1'b1;
    endtask

    task automatic stop_dst_clock();
        @(negedge dst_clk);
        dst_clk_en = 1'b0;
    endtask

    task automatic resume_dst_clock();
        dst_clk_en = 1'b1;
    endtask

    task automatic wait_online_both();
        integer guard;
        guard = 0;
        while (!(src_online === 1'b1 && dst_online === 1'b1) && guard < 4000) begin
            @(posedge src_clk);
            guard = guard + 1;
        end
        if (!(src_online === 1'b1 && dst_online === 1'b1)) tb_fail("timeout waiting for both online signals");
    endtask

    task automatic check_ready_low_until_online();
        integer guard;
        guard = 0;
        while (src_online !== 1'b1 && guard < 2000) begin
            @(posedge src_clk);
            if (src_online !== 1'b1 && src_ready !== 1'b0) tb_fail("src_ready high before src_online");
            guard = guard + 1;
        end
        if (src_online !== 1'b1) tb_fail("timeout waiting for src_online");
    endtask

    task automatic wait_ready_high();
        integer guard;
        guard = 0;
        while (src_ready !== 1'b1 && guard < 2000) begin
            @(posedge src_clk);
            guard = guard + 1;
        end
        if (src_ready !== 1'b1) tb_fail("timeout waiting for src_ready");
    endtask

    task automatic wait_accept_count(input integer target);
        integer guard;
        guard = 0;
        while (accepted_total < target && guard < 4000) begin
            @(posedge src_clk);
            guard = guard + 1;
        end
        if (accepted_total < target) tb_fail("timeout waiting for accept count");
    endtask

    task automatic wait_deliver_count(input integer target);
        integer guard;
        guard = 0;
        while (delivered_total < target && guard < 4000) begin
            @(posedge dst_clk);
            guard = guard + 1;
        end
        if (delivered_total < target) tb_fail("timeout waiting for deliver count");
    endtask

    task automatic wait_dst_valid_high();
        integer guard;
        guard = 0;
        while (dst_valid !== 1'b1 && guard < 4000) begin
            @(posedge dst_clk);
            guard = guard + 1;
        end
        if (dst_valid !== 1'b1) tb_fail("timeout waiting for dst_valid");
    endtask

    task automatic repeat_dst_stall_edges(input integer cycles);
        integer k;
        for (k = 0; k < cycles; k = k + 1) begin
            @(posedge dst_clk);
            if (dst_valid !== 1'b1) tb_fail("dst_valid dropped during stall window");
        end
    endtask

    task automatic repeat_src_edges_check_ready_low(input integer cycles);
        integer k;
        for (k = 0; k < cycles; k = k + 1) begin
            @(posedge src_clk);
            if (src_ready !== 1'b0) tb_fail("src_ready high while valid held through reset was not rearmed");
        end
    endtask

    task automatic expect_idle_dst(input integer cycles);
        integer k;
        for (k = 0; k < cycles; k = k + 1) begin
            @(posedge dst_clk);
            if (dst_valid !== 1'b0) tb_fail("dst_valid high during expected-idle window");
        end
        #0.5;
        if (dst_valid !== 1'b0) tb_fail("dst_valid high at end of expected-idle window");
    endtask

    task automatic begin_case(input string name);
        current_case = name;
        case_acc_base = accepted_total;
        case_del_base = delivered_total;
        case_disc_base = discarded_total;
        case_err_base = tb_errors;
        $display("TB_CASE_BEGIN case=%s width=%0d", name, WIDTH);
    endtask

    task automatic end_case(input string name, input integer exp_acc, input integer exp_del, input integer exp_disc);
        $display("TB_CASE case=%s width=%0d accepted=%0d delivered=%0d discarded=%0d errors=%0d",
                 name, WIDTH, accepted_total - case_acc_base, delivered_total - case_del_base,
                 discarded_total - case_disc_base, tb_errors - case_err_base);
        if ((accepted_total - case_acc_base) !== exp_acc ||
            (delivered_total - case_del_base) !== exp_del ||
            (discarded_total - case_disc_base) !== exp_disc) begin
            tb_fail("case count mismatch");
        end
    endtask

    task automatic drive_offer();
        @(negedge src_clk);
        src_data  = pattern(accepted_total);
        src_valid = 1'b1;
    endtask

    task automatic lower_offer();
        @(negedge src_clk);
        src_valid = 1'b0;
    endtask

    task automatic transfer_directed();
        wait_ready_high();
        drive_offer();
        wait_accept_count(accepted_total + 1);
        lower_offer();
        wait_deliver_count(delivered_total + 1);
        expect_idle_dst(6);
    endtask

    initial begin : tb_main
        $timeformat(-9, 3, "ns", 20);
        if ($test$plusargs("tb_neg_hang")) begin
            $display("TB_NEG_HANG_ARMED width=%0d", WIDTH);
            #(TB_WATCHDOG_NS + 1000000);
            $display("TB_NEG_HANG_NOT_CAUGHT width=%0d", WIDTH);
            $finish;
        end else begin

            begin_case("startup");
            #33.5;
            src_reset_n = 1'b1;
            #14.0;
            dst_reset_n = 1'b1;
            check_ready_low_until_online();
            wait_online_both();
            wait_ready_high();
            #0.5;
            dst_ready = 1'b1;
            transfer_directed();
            end_case("startup", 1, 1, 0);

            begin_case("payload_stall");
            #0.5;
            dst_ready = 1'b0;
            wait_ready_high();
            drive_offer();
            wait_accept_count(accepted_total + 1);
            lower_offer();
            wait_dst_valid_high();
            repeat_dst_stall_edges(40);
            if ((delivered_total - case_del_base) !== 0) tb_fail("premature delivery during stall");
            #0.5;
            dst_ready = 1'b1;
            wait_deliver_count(delivered_total + 1);
            expect_idle_dst(6);
            end_case("payload_stall", 1, 1, 0);

            begin_case("consecutive");
            #0.5;
            dst_ready = 1'b1;
            for (i = 0; i < 8; i = i + 1) begin
                drive_offer();
                wait_accept_count(accepted_total + 1);
            end
            lower_offer();
            wait_deliver_count(case_del_base + 8);
            expect_idle_dst(8);
            end_case("consecutive", 8, 8, 0);

            begin_case("dst_clock_stop");
            stop_dst_clock();
            #0.5;
            dst_ready = 1'b1;
            wait_ready_high();
            drive_offer();
            wait_accept_count(accepted_total + 1);
            lower_offer();
            #0.5;
            src_data  = pattern(accepted_total);
            src_valid = 1'b1;
            #100.5;
            if ((accepted_total - case_acc_base) !== 1) tb_fail("accept while destination clock stopped and transfer pending");
            if ((delivered_total - case_del_base) !== 0) tb_fail("delivery while destination clock stopped");
            #0.5;
            src_valid = 1'b0;
            resume_dst_clock();
            wait_deliver_count(delivered_total + 1);
            wait_ready_high();
            transfer_directed();
            end_case("dst_clock_stop", 2, 2, 0);

            begin_case("src_clock_stop");
            stop_src_clock();
            #50.5;
            if (src_ready !== 1'b1) tb_fail("src_ready dropped while source clock stopped and idle");
            resume_src_clock();
            transfer_directed();
            #0.5;
            dst_ready = 1'b0;
            wait_ready_high();
            drive_offer();
            wait_accept_count(accepted_total + 1);
            lower_offer();
            wait_dst_valid_high();
            stop_src_clock();
            #0.5;
            dst_ready = 1'b1;
            wait_deliver_count(delivered_total + 1);
            #30.5;
            if ((accepted_total - case_acc_base) !== 2) tb_fail("unexpected accept with source clock stopped");
            resume_src_clock();
            wait_ready_high();
            transfer_directed();
            #0.5;
            dst_ready = 1'b1;
            end_case("src_clock_stop", 3, 3, 0);

            begin_case("held_high_valid_across_reset");
            #0.5;
            src_data    = pattern(accepted_total);
            src_reset_n = 1'b0;
            src_valid   = 1'b1;
            #40.5;
            src_reset_n = 1'b1;
            wait_online_both();
            repeat_src_edges_check_ready_low(10);
            if ((accepted_total - case_acc_base) !== 0) tb_fail("held-high valid accepted after reset");
            #0.5;
            src_valid = 1'b0;
            wait_ready_high();
            #0.5;
            src_data  = ~pattern(accepted_total);
            src_valid = 1'b1;
            wait_accept_count(accepted_total + 1);
            lower_offer();
            wait_deliver_count(delivered_total + 1);
            expect_idle_dst(6);
            end_case("held_high_valid_across_reset", 1, 1, 0);

            begin_case("reset_idle");
            transfer_directed();
            #0.5;
            src_reset_n = 1'b0;
            #30.5;
            src_reset_n = 1'b1;
            wait_online_both();
            wait_ready_high();
            expect_idle_dst(4);
            transfer_directed();
            #0.5;
            dst_reset_n = 1'b0;
            #25.5;
            dst_reset_n = 1'b1;
            wait_online_both();
            wait_ready_high();
            expect_idle_dst(4);
            transfer_directed();
            end_case("reset_idle", 3, 3, 0);

            begin_case("reset_inflight_request");
            stop_dst_clock();
            #0.5;
            dst_ready = 1'b1;
            wait_ready_high();
            drive_offer();
            wait_accept_count(accepted_total + 1);
            lower_offer();
            #20.5;
            if ((delivered_total - case_del_base) !== 0) tb_fail("delivery while destination clock stopped");
            src_reset_n = 1'b0;
            #30.5;
            src_reset_n = 1'b1;
            resume_dst_clock();
            #0.5;
            expect_idle_dst(20);
            if ((delivered_total - case_del_base) !== 0) tb_fail("phantom delivery after in-flight reset");
            if ((discarded_total - case_disc_base) !== 1) tb_fail("in-flight reset did not discard exactly one snapshot");
            wait_online_both();
            wait_ready_high();
            transfer_directed();
            end_case("reset_inflight_request", 2, 1, 1);

            begin_case("reset_valid_pending_stall");
            #0.5;
            dst_ready = 1'b0;
            wait_ready_high();
            drive_offer();
            wait_accept_count(accepted_total + 1);
            lower_offer();
            wait_dst_valid_high();
            repeat_dst_stall_edges(30);
            #0.5;
            src_reset_n = 1'b0;
            #2.5;
            if (dst_valid !== 1'b0) tb_fail("shared flush did not clear dst_valid asynchronously");
            #28.5;
            src_reset_n = 1'b1;
            wait_online_both();
            wait_ready_high();
            if ((delivered_total - case_del_base) !== 0) tb_fail("stalled snapshot delivered after reset");
            if ((discarded_total - case_disc_base) !== 1) tb_fail("stalled snapshot not discarded");
            #0.5;
            dst_ready = 1'b1;
            expect_idle_dst(16);
            transfer_directed();
            end_case("reset_valid_pending_stall", 2, 1, 1);

            begin_case("reset_dst_clock_stopped");
            stop_dst_clock();
            #0.5;
            dst_ready = 1'b1;
            wait_ready_high();
            drive_offer();
            wait_accept_count(accepted_total + 1);
            lower_offer();
            #15.5;
            src_reset_n = 1'b0;
            dst_reset_n = 1'b0;
            #40.5;
            src_reset_n = 1'b1;
            #30.5;
            if (src_ready !== 1'b0) tb_fail("src_ready high while peer reset held low");
            #30.5;
            drive_offer();
            #100.5;
            if ((accepted_total - case_acc_base) !== 1) tb_fail("accept while peer reset held and destination clock stopped");
            if (src_ready !== 1'b0) tb_fail("src_ready high while destination clock stopped");
            lower_offer();
            #0.5;
            dst_reset_n = 1'b1;
            #50.5;
            if (src_ready !== 1'b0) tb_fail("src_ready high while destination clock stopped after release");
            if ((discarded_total - case_disc_base) !== 1) tb_fail("in-flight snapshot not discarded");
            resume_dst_clock();
            wait_online_both();
            wait_ready_high();
            expect_idle_dst(8);
            transfer_directed();
            end_case("reset_dst_clock_stopped", 2, 1, 1);

            begin_case("reset_src_clock_stopped");
            #0.5;
            dst_ready = 1'b0;
            wait_ready_high();
            drive_offer();
            wait_accept_count(accepted_total + 1);
            lower_offer();
            wait_dst_valid_high();
            repeat_dst_stall_edges(20);
            stop_src_clock();
            #0.5;
            src_reset_n = 1'b0;
            #2.5;
            if (dst_valid !== 1'b0) tb_fail("shared flush from source reset did not clear dst_valid with source clock stopped");
            #30.5;
            src_reset_n = 1'b1;
            #50.5;
            if (src_ready !== 1'b0) tb_fail("src_ready high while source clock stopped after reset");
            if ((discarded_total - case_disc_base) !== 1) tb_fail("pending snapshot not discarded by source-clock-stopped reset");
            #0.5;
            dst_ready = 1'b1;
            expect_idle_dst(12);
            resume_src_clock();
            wait_online_both();
            wait_ready_high();
            transfer_directed();
            end_case("reset_src_clock_stopped", 2, 1, 1);

            begin_case("reset_dst_only_stalled");
            #0.5;
            dst_ready = 1'b0;
            wait_ready_high();
            drive_offer();
            wait_accept_count(accepted_total + 1);
            lower_offer();
            wait_dst_valid_high();
            repeat_dst_stall_edges(24);
            #0.5;
            dst_reset_n = 1'b0;
            #2.5;
            if (dst_valid !== 1'b0) tb_fail("destination-only reset did not clear stalled dst_valid");
            #28.5;
            dst_reset_n = 1'b1;
            wait_online_both();
            wait_ready_high();
            if ((delivered_total - case_del_base) !== 0) tb_fail("stalled snapshot delivered after destination-only reset");
            if ((discarded_total - case_disc_base) !== 1) tb_fail("stalled snapshot not discarded");
            #0.5;
            dst_ready = 1'b1;
            expect_idle_dst(16);
            transfer_directed();
            end_case("reset_dst_only_stalled", 2, 1, 1);

            begin_case("reset_dst_only_inflight_request");
            stop_dst_clock();
            #0.5;
            dst_ready = 1'b1;
            wait_ready_high();
            drive_offer();
            wait_accept_count(accepted_total + 1);
            lower_offer();
            #20.5;
            if ((delivered_total - case_del_base) !== 0) tb_fail("delivery while destination clock stopped and request in flight");
            dst_reset_n = 1'b0;
            #2.5;
            if (src_ready !== 1'b0) tb_fail("src_ready high while destination-only reset held low");
            if ((discarded_total - case_disc_base) !== 1) tb_fail("in-flight destination-only reset did not discard exactly one snapshot");
            #28.5;
            dst_reset_n = 1'b1;
            resume_dst_clock();
            wait_online_both();
            wait_ready_high();
            if ((delivered_total - case_del_base) !== 0) tb_fail("phantom delivery after destination-only in-flight reset");
            if ((accepted_total - case_acc_base) !== 1) tb_fail("unexpected accept after destination-only in-flight reset");
            #0.5;
            dst_ready = 1'b1;
            expect_idle_dst(20);
            transfer_directed();
            end_case("reset_dst_only_inflight_request", 2, 1, 1);

            directed_acc_total  = accepted_total;
            directed_del_total  = delivered_total;
            directed_disc_total = discarded_total;

            begin_case("random_soak");
            #0.5;
            dst_ready = 1'b1;
            wait_ready_high();
            soak_accepts_at_offer = accepted_total;
            for (soak_step = 0; soak_step < SOAK_STEPS; soak_step = soak_step + 1) begin
                r = rng_next();
                #(rnd01(r));
                case (r % 24)
                    0: begin
                        src_reset_n = 1'b0;
                        #(rnd01(r >> 8));
                        src_reset_n = 1'b1;
                    end
                    6: begin
                        dst_reset_n = 1'b0;
                        #(rnd01(r >> 12));
                        dst_reset_n = 1'b1;
                    end
                    12: begin
                        src_reset_n = 1'b0;
                        dst_reset_n = 1'b0;
                        #(rnd01(r >> 16));
                        src_reset_n = 1'b1;
                        dst_reset_n = 1'b1;
                    end
                    default: begin end
                endcase
                if ((r % 32) === 4 && src_clk_en === 1'b1) begin
                    stop_src_clock();
                    #(rnd01(r >> 20));
                    resume_src_clock();
                end
                if ((r % 32) === 11 && dst_clk_en === 1'b1) begin
                    stop_dst_clock();
                    #(rnd01(r >> 24));
                    resume_dst_clock();
                end
                if ((r % 3) === 0) begin
                    dst_ready = ~dst_ready;
                end
                if (src_valid === 1'b1) begin
                    if (accepted_total > soak_accepts_at_offer) begin
                        soak_accepts_at_offer = accepted_total;
                        if ((r % 2) === 0) begin
                            src_valid = 1'b0;
                        end else begin
                            src_data = pattern(accepted_total);
                        end
                    end else if ((r % 4) === 0) begin
                        src_valid = 1'b0;
                    end
                end else begin
                    if ((r % 4) !== 3) begin
                        src_data = pattern(accepted_total);
                        src_valid = 1'b1;
                        soak_accepts_at_offer = accepted_total;
                    end
                end
            end
            if (src_clk_en !== 1'b1) resume_src_clock();
            if (dst_clk_en !== 1'b1) resume_dst_clock();
            #0.5;
            src_valid = 1'b0;
            #0.5;
            dst_ready = 1'b1;
            drain_guard = 0;
            while ((q_count > 0 || dst_valid === 1'b1 || src_ready !== 1'b1) && drain_guard < 20000) begin
                @(posedge src_clk);
                drain_guard = drain_guard + 1;
            end
            if (q_count > 0 || dst_valid === 1'b1) tb_fail("soak drain did not complete");
            if (src_ready !== 1'b1) tb_fail("soak drain ready did not return");
            expect_idle_dst(8);
            if ((accepted_total - case_acc_base) !== (delivered_total - case_del_base) + (discarded_total - case_disc_base)) tb_fail("soak ledger mismatch");
            if ((accepted_total - case_acc_base) < 16) tb_fail("soak completed too few transfers to be meaningful");
            $display("TB_CASE case=random_soak width=%0d accepted=%0d delivered=%0d discarded=%0d errors=%0d",
                     WIDTH, accepted_total - case_acc_base, delivered_total - case_del_base,
                     discarded_total - case_disc_base, tb_errors - case_err_base);

            if (accepted_total !== delivered_total + discarded_total) tb_fail("final ledger mismatch");
            $display("TB_SUMMARY width=%0d accepted=%0d delivered=%0d discarded=%0d directed_accepted=%0d directed_delivered=%0d directed_discarded=%0d soak_accepted=%0d soak_delivered=%0d soak_discarded=%0d flush_events=%0d src_reset_drops=%0d dst_reset_drops=%0d tb_errors=%0d",
                     WIDTH, accepted_total, delivered_total, discarded_total,
                     directed_acc_total, directed_del_total, directed_disc_total,
                     accepted_total - directed_acc_total, delivered_total - directed_del_total, discarded_total - directed_disc_total,
                     flush_events, src_reset_drops, dst_reset_drops, tb_errors);
            $display("TB_END width=%0d sim_ns=%0t", WIDTH, $time);
            $display("TB_DONE width=%0d", WIDTH);
        end
    end

endmodule

module snapshot_mailbox_width_bounds_negative #(
    parameter integer BOUNDS_WIDTH = 1025
) ();
    reg clk0 = 1'b0;
    reg rst0 = 1'b0;

    deepeye_snapshot_mailbox #(.WIDTH(BOUNDS_WIDTH)) u_dut (
        .src_clk(clk0),
        .src_reset_n(rst0),
        .src_valid(),
        .src_ready(),
        .src_data(),
        .src_online(),
        .dst_clk(clk0),
        .dst_reset_n(rst0),
        .dst_valid(),
        .dst_ready(),
        .dst_data(),
        .dst_online()
    );

    initial begin : bounds_negative_watchdog
        #1000;
        $display("BOUNDS_NEGATIVE_DID_NOT_FIRE");
        $fatal(1, "BOUNDS_NEGATIVE_DID_NOT_FIRE");
    end
endmodule
