`timescale 1ns/1ps

module tb_raw_scan_queue #(
    parameter int DEPTH  = 4,
    parameter int SEQ_W  = 32,
    parameter int TICK_W = 64,
    parameter int TAG_W  = 32,
    parameter int STAT_W = 32
);
    localparam int DEPTH_R = (DEPTH >= 1 && DEPTH <= 8) ? DEPTH : 1;
    localparam int SEQ_R   = (SEQ_W >= 2 && SEQ_W <= 32) ? SEQ_W : 2;
    localparam int TICK_R  = (TICK_W >= 1 && TICK_W <= 64) ? TICK_W : 1;
    localparam int TAG_R   = (TAG_W >= 1 && TAG_W <= 64) ? TAG_W : 1;
    localparam int STAT_R  = (STAT_W >= 2 && STAT_W <= 32) ? STAT_W : 2;
    localparam int LEVEL_R = (DEPTH_R <= 1) ? 1 : $clog2(DEPTH_R + 1);
    localparam longint STAT_MAX = (64'd1 << STAT_R) - 64'd1;

    typedef struct packed {
        logic [63:0]  data;
        logic [255:0] ticks;
        logic [31:0]  quality;
        logic [31:0]  first_seq;
        logic [31:0]  last_seq;
        logic [63:0]  tag;
    } rec_t;

    logic clk;
    logic rst;
    logic cancel;
    logic in_valid;
    logic in_ready;
    logic [63:0] in_data;
    logic [4*TICK_R-1:0] in_ticks;
    logic [31:0] in_quality;
    logic [SEQ_R-1:0] in_first_seq;
    logic [SEQ_R-1:0] in_last_seq;
    logic [TAG_R-1:0] in_tag;
    logic out_valid;
    logic out_ready;
    logic [63:0] out_data;
    logic [4*TICK_R-1:0] out_ticks;
    logic [31:0] out_quality;
    logic [SEQ_R-1:0] out_first_seq;
    logic [SEQ_R-1:0] out_last_seq;
    logic [TAG_R-1:0] out_tag;
    logic [LEVEL_R-1:0] level;
    logic [STAT_R-1:0] stat_accepted;
    logic [STAT_R-1:0] stat_retired;
    logic [STAT_R-1:0] stat_aborted;

    deepeye_raw_scan_queue #(
        .DEPTH(DEPTH),
        .SEQ_W(SEQ_W),
        .TICK_W(TICK_W),
        .TAG_W(TAG_W),
        .STAT_W(STAT_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_data(in_data),
        .in_ticks(in_ticks),
        .in_quality(in_quality),
        .in_first_seq(in_first_seq),
        .in_last_seq(in_last_seq),
        .in_tag(in_tag),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_data(out_data),
        .out_ticks(out_ticks),
        .out_quality(out_quality),
        .out_first_seq(out_first_seq),
        .out_last_seq(out_last_seq),
        .out_tag(out_tag),
        .level(level),
        .stat_accepted(stat_accepted),
        .stat_retired(stat_retired),
        .stat_aborted(stat_aborted)
    );

    rec_t ref_mem [0:DEPTH_R-1];
    int ref_head;
    int ref_tail;
    int ref_level;
    longint ref_accepted;
    longint ref_retired;
    longint ref_aborted;
    int checks;
    int errors;
    int cycles;
    int resets;
    int cancels;
    int stalls;
    int wrap_writes;
    int wrap_reads;
    string test_case;

    function automatic logic [255:0] pack_ticks4(
        input logic [63:0] lane0,
        input logic [63:0] lane1,
        input logic [63:0] lane2,
        input logic [63:0] lane3
    );
        logic [255:0] value;
        value = '0;
        value[0*TICK_R +: TICK_R] = lane0[TICK_R-1:0];
        value[1*TICK_R +: TICK_R] = lane1[TICK_R-1:0];
        value[2*TICK_R +: TICK_R] = lane2[TICK_R-1:0];
        value[3*TICK_R +: TICK_R] = lane3[TICK_R-1:0];
        pack_ticks4 = value;
    endfunction

    function automatic rec_t make_rec(
        input logic [63:0] data_i,
        input logic [255:0] ticks_i,
        input logic [31:0] quality_i,
        input logic [31:0] first_i,
        input logic [31:0] last_i,
        input logic [63:0] tag_i
    );
        rec_t value;
        value.data = data_i;
        value.ticks = ticks_i;
        value.quality = quality_i;
        value.first_seq = first_i;
        value.last_seq = last_i;
        value.tag = tag_i;
        make_rec = value;
    endfunction

    function automatic rec_t empty_rec();
        rec_t value;
        value = '0;
        empty_rec = value;
    endfunction

    function automatic rec_t default_rec(input logic [63:0] seed);
        rec_t value;
        value = make_rec(
            seed,
            pack_ticks4(seed, seed + 64'd1, seed + 64'd2, seed + 64'd3),
            seed[31:0],
            seed[31:0],
            ~seed[31:0],
            seed
        );
        default_rec = value;
    endfunction

    function automatic longint sat_value(input longint value);
        if (value > STAT_MAX) begin
            sat_value = STAT_MAX;
        end else begin
            sat_value = value;
        end
    endfunction

    task automatic check_wide(
        input string field,
        input logic [255:0] expected,
        input logic [255:0] actual
    );
        begin
            checks = checks + 1;
            if (expected !== actual) begin
                errors = errors + 1;
                $display("RAW_SCAN_MISMATCH field=%s expected=%0d actual=%0d",
                         field, expected, actual);
            end
        end
    endtask

    task automatic check_int(
        input string field,
        input longint expected,
        input longint actual
    );
        begin
            checks = checks + 1;
            if (expected !== actual) begin
                errors = errors + 1;
                $display("RAW_SCAN_MISMATCH field=%s expected=%0d actual=%0d",
                         field, expected, actual);
            end
        end
    endtask

    task automatic check_rec(input rec_t expected);
        logic [255:0] actual_ticks;
        begin
            actual_ticks = '0;
            actual_ticks[4*TICK_R-1:0] = out_ticks;
            check_wide("data", {192'b0, expected.data}, {192'b0, out_data});
            check_wide("ticks", expected.ticks, actual_ticks);
            check_wide("quality", {224'b0, expected.quality}, {224'b0, out_quality});
            check_wide("first_seq", {224'b0, expected.first_seq[SEQ_R-1:0]},
                       {224'b0, out_first_seq});
            check_wide("last_seq", {224'b0, expected.last_seq[SEQ_R-1:0]},
                       {224'b0, out_last_seq});
            check_wide("tag", {192'b0, expected.tag[TAG_R-1:0]},
                       {192'b0, out_tag});
        end
    endtask

    task automatic check_state(input bit check_payload);
        begin
            check_int("level", ref_level, level);
            check_int("stat_accepted", sat_value(ref_accepted), stat_accepted);
            check_int("stat_retired", sat_value(ref_retired), stat_retired);
            check_int("stat_aborted", sat_value(ref_aborted), stat_aborted);
            if (check_payload && (out_valid === 1'b1)) begin
                check_rec(ref_mem[ref_head]);
            end
        end
    endtask

    task automatic check_comb(input bit rst_i, input bit cancel_i);
        bit expect_ready;
        bit expect_valid;
        begin
            expect_ready = !rst_i && !cancel_i && (ref_level < DEPTH_R);
            expect_valid = !rst_i && !cancel_i && (ref_level > 0);
            check_int("in_ready", expect_ready, in_ready);
            check_int("out_valid", expect_valid, out_valid);
            check_state(expect_valid);
        end
    endtask

    task automatic trace_queue(input string phase);
        begin
            if ($test$plusargs("TRACE")) begin
                $display("RAW_SCAN_TRACE side=%s case=%s cycle=%0d rst=%b cancel=%b in_valid=%b in_ready=%b in_data=%016h in_ticks=%0h in_quality=%08h in_first_seq=%0h in_last_seq=%0h in_tag=%0h out_valid=%b out_ready=%b out_data=%016h out_ticks=%0h out_quality=%08h out_first_seq=%0h out_last_seq=%0h out_tag=%0h level=%0d stat_accepted=%0d stat_retired=%0d stat_aborted=%0d ref_level=%0d ref_accepted=%0d ref_retired=%0d ref_aborted=%0d",
                         phase, test_case, cycles, rst, cancel, in_valid, in_ready,
                         in_data, in_ticks, in_quality, in_first_seq, in_last_seq,
                         in_tag, out_valid, out_ready, out_data, out_ticks,
                         out_quality, out_first_seq, out_last_seq, out_tag, level,
                         stat_accepted, stat_retired, stat_aborted, ref_level,
                         ref_accepted, ref_retired, ref_aborted);
            end
        end
    endtask

    task automatic model_update(
        input bit rst_i,
        input bit cancel_i,
        input bit push_i,
        input bit pop_i,
        input rec_t input_rec
    );
        begin
            if (rst_i) begin
                ref_level = 0;
                ref_head = 0;
                ref_tail = 0;
                ref_accepted = 0;
                ref_retired = 0;
                ref_aborted = 0;
            end else if (cancel_i) begin
                ref_aborted = ref_aborted + ref_level;
                ref_level = 0;
                ref_head = 0;
                ref_tail = 0;
            end else begin
                if (pop_i) begin
                    ref_retired = ref_retired + 1;
                    if (ref_head == DEPTH_R - 1) begin
                        ref_head = 0;
                    end else begin
                        ref_head = ref_head + 1;
                    end
                    ref_level = ref_level - 1;
                end
                if (push_i) begin
                    ref_mem[ref_tail] = input_rec;
                    if (ref_tail == DEPTH_R - 1) begin
                        ref_tail = 0;
                    end else begin
                        ref_tail = ref_tail + 1;
                    end
                    ref_level = ref_level + 1;
                    ref_accepted = ref_accepted + 1;
                end
            end
        end
    endtask

    task automatic qedge(
        input bit rst_i,
        input bit cancel_i,
        input bit in_valid_i,
        input bit out_ready_i,
        input rec_t input_rec
    );
        bit push_i;
        bit pop_i;
        begin
            @(negedge clk);
            rst = rst_i;
            cancel = cancel_i;
            in_valid = in_valid_i;
            out_ready = out_ready_i;
            in_data = input_rec.data;
            in_ticks = input_rec.ticks[4*TICK_R-1:0];
            in_quality = input_rec.quality;
            in_first_seq = input_rec.first_seq[SEQ_R-1:0];
            in_last_seq = input_rec.last_seq[SEQ_R-1:0];
            in_tag = input_rec.tag[TAG_R-1:0];
            #1;
            check_comb(rst_i, cancel_i);
            trace_queue("pre");
            push_i = in_valid_i && !rst_i && !cancel_i && (ref_level < DEPTH_R);
            pop_i = !rst_i && !cancel_i && (ref_level > 0) && out_ready_i;
            @(posedge clk);
            #1;
            model_update(rst_i, cancel_i, push_i, pop_i, input_rec);
            cycles = cycles + 1;
            if (rst_i) resets = resets + 1;
            if (cancel_i) cancels = cancels + 1;
            check_comb(rst_i, cancel_i);
            trace_queue("post");
        end
    endtask

    task automatic apply_reset();
        begin
            qedge(1'b1, 1'b0, 1'b0, 1'b0, empty_rec());
            qedge(1'b1, 1'b0, 1'b0, 1'b0, empty_rec());
            qedge(1'b0, 1'b0, 1'b0, 1'b0, empty_rec());
        end
    endtask

    task automatic fill_n(input int count, input logic [63:0] base);
        int index;
        begin
            for (index = 0; index < count; index = index + 1) begin
                qedge(1'b0, 1'b0, 1'b1, 1'b0, default_rec(base + index));
            end
        end
    endtask

    task automatic drain_all();
        int guard;
        begin
            guard = 0;
            while ((ref_level > 0) && (guard < 64)) begin
                qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
                guard = guard + 1;
            end
            if (ref_level != 0) begin
                errors = errors + 1;
                $display("RAW_SCAN_MISMATCH field=drain_stuck expected=0 actual=%0d", ref_level);
            end
        end
    endtask

    task automatic run_guard_healthy();
        rec_t record_value;
        begin
            apply_reset();
            record_value = default_rec(64'h1234_5678_9abc_def0);
            qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
            qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
            check_int("guard_healthy_level", 0, ref_level);
        end
    endtask

    task automatic run_queue_directed();
        rec_t record_value;
        int index;
        int level_index;
        int combo;
        longint segment_acc;
        longint segment_ret;
        begin
            apply_reset();

            fill_n(DEPTH_R, 64'h0000_0000_0000_1000);
            check_int("capacity_level", DEPTH_R, ref_level);
            check_int("capacity_ready", 0, in_ready);
            check_int("capacity_valid", 1, out_valid);

            record_value = make_rec(
                64'hffff_ffff_ffff_ffff,
                {256{1'b1}},
                32'hffff_ffff,
                32'hffff_ffff,
                32'h0000_0000,
                64'hffff_ffff_ffff_ffff
            );
            qedge(1'b0, 1'b0, 1'b1, 1'b1, record_value);
            check_int("full_bubble_level", DEPTH_R - 1, ref_level);
            qedge(1'b0, 1'b0, 1'b1, 1'b0, default_rec(64'h0000_0000_0000_2000));
            check_int("refill_level", DEPTH_R, ref_level);
            drain_all();
            check_int("drain_level", 0, ref_level);
            check_int("drain_valid", 0, out_valid);

            qedge(1'b0, 1'b0, 1'b1, 1'b1, default_rec(64'h0000_0000_0000_2100));
            check_int("empty_offer_level", 1, ref_level);
            drain_all();

            fill_n(1, 64'h0000_0000_0000_3000);
            qedge(1'b0, 1'b0, 1'b1, 1'b1, default_rec(64'h0000_0000_0000_3100));
            if (DEPTH_R > 1) begin
                check_int("simultaneous_level", 1, ref_level);
            end else begin
                check_int("simultaneous_level", 0, ref_level);
            end
            drain_all();

            for (level_index = 0; level_index <= DEPTH_R; level_index = level_index + 1) begin
                for (combo = 0; combo < 16; combo = combo + 1) begin
                    apply_reset();
                    fill_n(level_index, 64'h0000_0000_0000_4000
                                        + level_index * 16 + combo);
                    record_value = default_rec(64'h0000_0000_0000_5000
                                               + level_index * 16 + combo);
                    qedge((combo & 1) != 0,
                         (combo & 2) != 0,
                         (combo & 4) != 0,
                         (combo & 8) != 0,
                         record_value);
                    drain_all();
                    check_int("combo_final_level", 0, ref_level);
                end
            end

            apply_reset();
            fill_n(DEPTH_R, 64'h0000_0000_0000_6000);
            for (index = 0; index < 3; index = index + 1) begin
                qedge(1'b0, 1'b1, 1'b0, 1'b0, empty_rec());
            end
            check_int("held_cancel_level", 0, ref_level);
            check_int("held_cancel_valid", 0, out_valid);
            fill_n(1, 64'h0000_0000_0000_6100);
            drain_all();

            fill_n(2, 64'h0000_0000_0000_6200);
            for (index = 0; index < 3; index = index + 1) begin
                qedge(1'b1, 1'b0, 1'b0, 1'b0, empty_rec());
            end
            check_int("held_reset_level", 0, ref_level);
            check_int("held_reset_accepted", 0, stat_accepted);
            check_int("held_reset_retired", 0, stat_retired);
            check_int("held_reset_aborted", 0, stat_aborted);

            apply_reset();
            for (index = 0; index < DEPTH_R; index = index + 1) begin
                record_value = default_rec(64'h0000_0000_0000_6800 + index);
                record_value.tag = 64'hcafe_face_dead_beef;
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
            end
            qedge(1'b0, 1'b1, 1'b0, 1'b0, empty_rec());
            check_int("stale_cancel_level", 0, ref_level);
            check_int("stale_cancel_valid", 0, out_valid);
            for (index = 0; index < DEPTH_R; index = index + 1) begin
                record_value = default_rec(64'h0000_0000_0000_6900 + index);
                record_value.tag = 64'hcafe_face_dead_beef;
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
            end
            drain_all();

            if ((DEPTH_R == 8) && (STAT_R == 2)) begin
                apply_reset();
                fill_n(8, 64'h0000_0000_0000_6a00);
                check_int("oldlevel8_accepted_before_cancel", 3, stat_accepted);
                qedge(1'b0, 1'b1, 1'b0, 1'b0, empty_rec());
                check_int("oldlevel8_cancel_aborted", 3, stat_aborted);
                check_int("oldlevel8_cancel_level", 0, level);
                check_int("oldlevel8_cancel_accepted_preserved", 3, stat_accepted);
                check_int("oldlevel8_cancel_retired_preserved", 0, stat_retired);
            end

            if (STAT_R <= 4) begin
                apply_reset();
                for (index = 0; index < 6; index = index + 1) begin
                    fill_n(DEPTH_R, 64'h0000_0000_0000_7000 + index * DEPTH_R);
                    qedge(1'b0, 1'b1, 1'b0, 1'b0, empty_rec());
                end
                check_int("abort_saturated", STAT_MAX, stat_aborted);
            end

            apply_reset();
            record_value = default_rec(64'h0000_0000_0000_8000);
            for (index = 0; index < 64; index = index + 1) begin
                record_value = default_rec(64'h0000_0000_0000_8100);
                record_value.data = (64'd1 << index);
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
                qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
                record_value.data = ~(64'd1 << index);
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
                qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
            end
            for (index = 0; index < 32; index = index + 1) begin
                record_value = default_rec(64'h0000_0000_0000_8200);
                record_value.quality = (32'd1 << index);
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
                qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
                record_value.quality = ~(32'd1 << index);
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
                qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
            end
            for (index = 0; index < SEQ_R; index = index + 1) begin
                record_value = default_rec(64'h0000_0000_0000_8300);
                record_value.first_seq = (32'd1 << index);
                record_value.last_seq = ~(32'd1 << index);
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
                qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
                record_value.first_seq = ~(32'd1 << index);
                record_value.last_seq = (32'd1 << index);
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
                qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
            end
            for (index = 0; index < TAG_R; index = index + 1) begin
                record_value = default_rec(64'h0000_0000_0000_8400);
                record_value.tag = (64'd1 << index);
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
                qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
                record_value.tag = ~(64'd1 << index);
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
                qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
            end
            for (index = 0; index < 4*TICK_R; index = index + 1) begin
                record_value = default_rec(64'h0000_0000_0000_8500);
                record_value.ticks = '0;
                record_value.ticks[index] = 1'b1;
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
                qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
                record_value.ticks[4*TICK_R-1:0] =
                    ~record_value.ticks[4*TICK_R-1:0];
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
                qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
            end

            record_value = default_rec(64'h0000_0000_0000_8600);
            for (index = 0; index < DEPTH_R; index = index + 1) begin
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
            end
            drain_all();
            for (index = 0; index < 3; index = index + 1) begin
                qedge(1'b0, 1'b0, 1'b1, 1'b0, record_value);
                qedge(1'b0, 1'b0, 1'b0, 1'b1, empty_rec());
            end

            apply_reset();
            qedge(1'b0, 1'b0, 1'b1, 1'b0, default_rec(64'h0000_0000_0000_8700));
            for (index = 0; index < 4096; index = index + 1) begin
                qedge(1'b0, 1'b0, 1'b0, 1'b0, empty_rec());
                stalls = stalls + 1;
            end
            drain_all();

            apply_reset();
            fill_n(DEPTH_R, 64'h0000_0000_0000_9000);
            segment_acc = ref_accepted;
            segment_ret = ref_retired;
            for (index = 0; index < (2*1000*DEPTH_R + 8); index = index + 1) begin
                qedge(1'b0, 1'b0, 1'b1, 1'b1,
                     default_rec(64'h0000_0000_0000_a000 + index));
            end
            wrap_writes = (ref_accepted - segment_acc) / DEPTH_R;
            wrap_reads = (ref_retired - segment_ret) / DEPTH_R;
            check_int("wrap_writes_min", 1, (wrap_writes >= 1000) ? 1 : 0);
            check_int("wrap_reads_min", 1, (wrap_reads >= 1000) ? 1 : 0);
            drain_all();

            if (STAT_R <= 4) begin
                for (index = 0; index < 6; index = index + 1) begin
                    fill_n(DEPTH_R, 64'h0000_0000_0000_b000 + index * DEPTH_R);
                    qedge(1'b0, 1'b1, 1'b0, 1'b0, empty_rec());
                end
                check_int("abort_saturated_final", STAT_MAX, stat_aborted);
            end
            drain_all();

            check_int("final_level", 0, ref_level);
            check_int("final_valid", 0, out_valid);
            check_int("true_balance", ref_accepted,
                      ref_retired + ref_aborted + ref_level);
            if (STAT_R <= 3) begin
                check_int("accepted_saturated", STAT_MAX, stat_accepted);
                check_int("retired_saturated", STAT_MAX, stat_retired);
            end
        end
    endtask

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        rst = 1'b0;
        cancel = 1'b0;
        in_valid = 1'b0;
        in_data = '0;
        in_ticks = '0;
        in_quality = '0;
        in_first_seq = '0;
        in_last_seq = '0;
        in_tag = '0;
        out_ready = 1'b0;
        ref_head = 0;
        ref_tail = 0;
        ref_level = 0;
        ref_accepted = 0;
        ref_retired = 0;
        ref_aborted = 0;
        checks = 0;
        errors = 0;
        cycles = 0;
        resets = 0;
        cancels = 0;
        stalls = 0;
        wrap_writes = 0;
        wrap_reads = 0;
        test_case = "queue_directed";
        if (!$value$plusargs("CASE=%s", test_case)) begin
            test_case = "queue_directed";
        end
        if ((DEPTH < 1) || (DEPTH > 8) || (SEQ_W < 2) || (SEQ_W > 32)
            || (TICK_W < 1) || (TICK_W > 64) || (TAG_W < 1) || (TAG_W > 64)
            || (STAT_W < 2) || (STAT_W > 32)) begin
            $display("RAW_SCAN_GUARD_SHELL");
            #100;
            $display("RAW_SCAN_GUARD_MISSING");
            $finish;
        end
        if (test_case == "guard_healthy") begin
            run_guard_healthy();
            $display("RAW_SCAN_GUARD_ALIVE");
        end else begin
            run_queue_directed();
        end
        $display("RAW_SCAN_STATS case=%s depth=%0d seq_w=%0d tick_w=%0d tag_w=%0d stat_w=%0d checks=%0d errors=%0d level=%0d accepted=%0d retired=%0d aborted=%0d true_accepted=%0d true_retired=%0d true_aborted=%0d cycles=%0d resets=%0d cancels=%0d stalls=%0d wrap_writes=%0d wrap_reads=%0d",
                 test_case, DEPTH, SEQ_W, TICK_W, TAG_W, STAT_W,
                 checks, errors, level, stat_accepted, stat_retired,
                 stat_aborted, ref_accepted, ref_retired,
                 ref_aborted, cycles, resets, cancels, stalls,
                 wrap_writes, wrap_reads);
        if (errors == 0) begin
            $display("RAW_SCAN_PASS");
        end else begin
            $display("RAW_SCAN_FAIL");
        end
        $finish;
    end

endmodule

module tb_raw_scan_queue_composition #(
    parameter int DEPTH  = 4,
    parameter int SEQ_W  = 32,
    parameter int TICK_W = 64,
    parameter int TAG_W  = 32,
    parameter int STAT_W = 32
);
    localparam int DEPTH_R = (DEPTH >= 1 && DEPTH <= 8) ? DEPTH : 1;
    localparam int SEQ_R   = (SEQ_W >= 2 && SEQ_W <= 32) ? SEQ_W : 2;
    localparam int TICK_R  = (TICK_W >= 1 && TICK_W <= 64) ? TICK_W : 1;
    localparam int TAG_R   = (TAG_W >= 1 && TAG_W <= 64) ? TAG_W : 1;
    localparam int STAT_R  = (STAT_W >= 2 && STAT_W <= 32) ? STAT_W : 2;
    localparam int LEVEL_R = (DEPTH_R <= 1) ? 1 : $clog2(DEPTH_R + 1);
    localparam longint STAT_MAX = (64'd1 << STAT_R) - 64'd1;
    localparam logic [SEQ_R-1:0] SEQ_LAST = {SEQ_R{1'b1}};

    typedef struct packed {
        logic [63:0]  data;
        logic [255:0] ticks;
        logic [31:0]  quality;
        logic [31:0]  first_seq;
        logic [31:0]  last_seq;
        logic [63:0]  tag;
    } rec_t;

    logic clk;
    logic rst;
    logic stop;
    logic rearm;
    logic [TAG_R-1:0] rearm_tag;
    logic sample_strobe;
    logic [1:0] sample_channel;
    logic [15:0] sample_data;
    logic [TICK_R-1:0] sample_tick;
    logic [7:0] sample_quality;
    logic consumer_ready;

    logic collector_out_valid;
    logic [63:0] collector_out_data;
    logic [4*TICK_R-1:0] collector_out_ticks;
    logic [31:0] collector_out_quality;
    logic [SEQ_R-1:0] collector_out_first_seq;
    logic [SEQ_R-1:0] collector_out_last_seq;
    logic [TAG_R-1:0] collector_out_tag;
    logic collector_armed;
    logic [2:0] collector_partial_len;
    logic [SEQ_R-1:0] collector_next_seq;
    logic collector_seq_exhausted;
    logic collector_order_error_event;
    logic collector_overrun_event;
    logic collector_seq_exhaust_event;
    logic [STAT_R-1:0] collector_stat_events;
    logic [STAT_R-1:0] collector_stat_scans;
    logic [STAT_R-1:0] collector_stat_retired;
    logic [STAT_R-1:0] collector_stat_discarded_samples;
    logic [STAT_R-1:0] collector_stat_order_errors;
    logic [STAT_R-1:0] collector_stat_overruns;

    logic queue_in_ready;
    logic queue_cancel;
    logic queue_out_valid;
    logic [63:0] queue_out_data;
    logic [4*TICK_R-1:0] queue_out_ticks;
    logic [31:0] queue_out_quality;
    logic [SEQ_R-1:0] queue_out_first_seq;
    logic [SEQ_R-1:0] queue_out_last_seq;
    logic [TAG_R-1:0] queue_out_tag;
    logic [LEVEL_R-1:0] queue_level;
    logic [STAT_R-1:0] queue_stat_accepted;
    logic [STAT_R-1:0] queue_stat_retired;
    logic [STAT_R-1:0] queue_stat_aborted;

    assign queue_cancel = stop | rearm;

    deepeye_sample_scan_capture #(
        .SEQ_W(SEQ_W),
        .TICK_W(TICK_W),
        .TAG_W(TAG_W),
        .STAT_W(STAT_W)
    ) collector (
        .clk(clk),
        .rst(rst),
        .stop(stop),
        .rearm(rearm),
        .rearm_tag(rearm_tag),
        .sample_strobe(sample_strobe),
        .sample_channel(sample_channel),
        .sample_data(sample_data),
        .sample_tick(sample_tick),
        .sample_quality(sample_quality),
        .out_ready(queue_in_ready),
        .out_valid(collector_out_valid),
        .out_data(collector_out_data),
        .out_ticks(collector_out_ticks),
        .out_quality(collector_out_quality),
        .out_first_seq(collector_out_first_seq),
        .out_last_seq(collector_out_last_seq),
        .out_tag(collector_out_tag),
        .armed(collector_armed),
        .partial_len(collector_partial_len),
        .next_seq(collector_next_seq),
        .seq_exhausted(collector_seq_exhausted),
        .order_error_event(collector_order_error_event),
        .overrun_event(collector_overrun_event),
        .seq_exhaust_event(collector_seq_exhaust_event),
        .stat_events(collector_stat_events),
        .stat_scans(collector_stat_scans),
        .stat_retired(collector_stat_retired),
        .stat_discarded_samples(collector_stat_discarded_samples),
        .stat_order_errors(collector_stat_order_errors),
        .stat_overruns(collector_stat_overruns)
    );

    deepeye_raw_scan_queue #(
        .DEPTH(DEPTH),
        .SEQ_W(SEQ_W),
        .TICK_W(TICK_W),
        .TAG_W(TAG_W),
        .STAT_W(STAT_W)
    ) dut_queue (
        .clk(clk),
        .rst(rst),
        .cancel(queue_cancel),
        .in_valid(collector_out_valid),
        .in_ready(queue_in_ready),
        .in_data(collector_out_data),
        .in_ticks(collector_out_ticks),
        .in_quality(collector_out_quality),
        .in_first_seq(collector_out_first_seq),
        .in_last_seq(collector_out_last_seq),
        .in_tag(collector_out_tag),
        .out_valid(queue_out_valid),
        .out_ready(consumer_ready),
        .out_data(queue_out_data),
        .out_ticks(queue_out_ticks),
        .out_quality(queue_out_quality),
        .out_first_seq(queue_out_first_seq),
        .out_last_seq(queue_out_last_seq),
        .out_tag(queue_out_tag),
        .level(queue_level),
        .stat_accepted(queue_stat_accepted),
        .stat_retired(queue_stat_retired),
        .stat_aborted(queue_stat_aborted)
    );

    rec_t m_slot;
    bit m_slot_valid;
    bit m_armed;
    logic [2:0] m_partial_len;
    logic [15:0] m_partial_data [0:3];
    logic [63:0] m_partial_tick [0:3];
    logic [7:0] m_partial_quality [0:3];
    logic [SEQ_R-1:0] m_partial_first;
    logic [SEQ_R-1:0] m_next_seq;
    bit m_exhausted;
    logic [TAG_R-1:0] m_tag;
    longint m_events;
    longint m_scans;
    longint m_retired;
    longint m_discarded;
    longint m_order_errors;
    longint m_overruns;
    bit m_order_event;
    bit m_overrun_event;
    bit m_exhaust_event;

    rec_t q_mem [0:DEPTH_R-1];
    int q_head;
    int q_tail;
    int q_level;
    longint q_acc;
    longint q_ret;
    longint q_abort;

    int comp_checks;
    int comp_errors;
    int comp_cycles;
    string comp_case;

    function automatic logic [255:0] pack_ticks4(
        input logic [63:0] lane0,
        input logic [63:0] lane1,
        input logic [63:0] lane2,
        input logic [63:0] lane3
    );
        logic [255:0] value;
        value = '0;
        value[0*TICK_R +: TICK_R] = lane0[TICK_R-1:0];
        value[1*TICK_R +: TICK_R] = lane1[TICK_R-1:0];
        value[2*TICK_R +: TICK_R] = lane2[TICK_R-1:0];
        value[3*TICK_R +: TICK_R] = lane3[TICK_R-1:0];
        pack_ticks4 = value;
    endfunction

    function automatic rec_t make_rec(
        input logic [63:0] data_i,
        input logic [255:0] ticks_i,
        input logic [31:0] quality_i,
        input logic [31:0] first_i,
        input logic [31:0] last_i,
        input logic [63:0] tag_i
    );
        rec_t value;
        value.data = data_i;
        value.ticks = ticks_i;
        value.quality = quality_i;
        value.first_seq = first_i;
        value.last_seq = last_i;
        value.tag = tag_i;
        make_rec = value;
    endfunction

    function automatic rec_t empty_rec();
        rec_t value;
        value = '0;
        empty_rec = value;
    endfunction

    function automatic longint sat_value(input longint value);
        if (value > STAT_MAX) begin
            sat_value = STAT_MAX;
        end else begin
            sat_value = value;
        end
    endfunction

    task automatic check_wide(
        input string field,
        input logic [255:0] expected,
        input logic [255:0] actual
    );
        begin
            comp_checks = comp_checks + 1;
            if (expected !== actual) begin
                comp_errors = comp_errors + 1;
                $display("RAW_SCAN_COMP_MISMATCH field=%s expected=%0d actual=%0d",
                         field, expected, actual);
            end
        end
    endtask

    task automatic check_int(
        input string field,
        input longint expected,
        input longint actual
    );
        begin
            comp_checks = comp_checks + 1;
            if (expected !== actual) begin
                comp_errors = comp_errors + 1;
                $display("RAW_SCAN_COMP_MISMATCH field=%s expected=%0d actual=%0d",
                         field, expected, actual);
            end
        end
    endtask

    task automatic check_collector_rec(input rec_t expected);
        logic [255:0] actual_ticks;
        begin
            actual_ticks = '0;
            actual_ticks[4*TICK_R-1:0] = collector_out_ticks;
            check_wide("c_data", {192'b0, expected.data}, {192'b0, collector_out_data});
            check_wide("c_ticks", expected.ticks, actual_ticks);
            check_wide("c_quality", {224'b0, expected.quality},
                       {224'b0, collector_out_quality});
            check_wide("c_first_seq", {224'b0, expected.first_seq[SEQ_R-1:0]},
                       {224'b0, collector_out_first_seq});
            check_wide("c_last_seq", {224'b0, expected.last_seq[SEQ_R-1:0]},
                       {224'b0, collector_out_last_seq});
            check_wide("c_tag", {192'b0, expected.tag[TAG_R-1:0]},
                       {192'b0, collector_out_tag});
        end
    endtask

    task automatic check_queue_rec(input rec_t expected);
        logic [255:0] actual_ticks;
        begin
            actual_ticks = '0;
            actual_ticks[4*TICK_R-1:0] = queue_out_ticks;
            check_wide("q_data", {192'b0, expected.data}, {192'b0, queue_out_data});
            check_wide("q_ticks", expected.ticks, actual_ticks);
            check_wide("q_quality", {224'b0, expected.quality},
                       {224'b0, queue_out_quality});
            check_wide("q_first_seq", {224'b0, expected.first_seq[SEQ_R-1:0]},
                       {224'b0, queue_out_first_seq});
            check_wide("q_last_seq", {224'b0, expected.last_seq[SEQ_R-1:0]},
                       {224'b0, queue_out_last_seq});
            check_wide("q_tag", {192'b0, expected.tag[TAG_R-1:0]},
                       {192'b0, queue_out_tag});
        end
    endtask

    task automatic check_comp_state(input bit check_payload);
        bit expect_collector_valid;
        bit expect_queue_ready;
        bit expect_queue_valid;
        begin
            expect_collector_valid = m_slot_valid && !rst && !stop && !rearm;
            expect_queue_ready = !rst && !queue_cancel && (q_level < DEPTH_R);
            expect_queue_valid = !rst && !queue_cancel && (q_level > 0);
            check_int("c_out_valid", expect_collector_valid, collector_out_valid);
            check_int("q_in_ready", expect_queue_ready, queue_in_ready);
            check_int("q_out_valid", expect_queue_valid, queue_out_valid);
            check_int("q_cancel", (stop || rearm) ? 1 : 0, queue_cancel);
            check_int("c_armed", m_armed, collector_armed);
            check_int("c_partial_len", m_partial_len, collector_partial_len);
            check_int("c_next_seq", m_next_seq, collector_next_seq);
            check_int("c_exhausted", m_exhausted, collector_seq_exhausted);
            check_int("c_order_event", m_order_event, collector_order_error_event);
            check_int("c_overrun_event", m_overrun_event, collector_overrun_event);
            check_int("c_exhaust_event", m_exhaust_event, collector_seq_exhaust_event);
            check_int("c_events", sat_value(m_events), collector_stat_events);
            check_int("c_scans", sat_value(m_scans), collector_stat_scans);
            check_int("c_retired", sat_value(m_retired), collector_stat_retired);
            check_int("c_discarded", sat_value(m_discarded),
                      collector_stat_discarded_samples);
            check_int("c_order_errors", sat_value(m_order_errors),
                      collector_stat_order_errors);
            check_int("c_overruns", sat_value(m_overruns),
                      collector_stat_overruns);
            check_int("q_level", q_level, queue_level);
            check_int("q_accepted", sat_value(q_acc), queue_stat_accepted);
            check_int("q_retired", sat_value(q_ret), queue_stat_retired);
            check_int("q_aborted", sat_value(q_abort), queue_stat_aborted);
            if (check_payload && expect_collector_valid) begin
                check_collector_rec(m_slot);
            end
            if (check_payload && expect_queue_valid) begin
                check_queue_rec(q_mem[q_head]);
            end
        end
    endtask

    task automatic comp_clear();
        int lane;
        begin
            m_slot = empty_rec();
            m_slot_valid = 1'b0;
            m_armed = 1'b0;
            m_partial_len = 3'd0;
            m_partial_first = '0;
            m_next_seq = '0;
            m_exhausted = 1'b0;
            m_tag = '0;
            for (lane = 0; lane < 4; lane = lane + 1) begin
                m_partial_data[lane] = 16'd0;
                m_partial_tick[lane] = 64'd0;
                m_partial_quality[lane] = 8'd0;
            end
            m_events = 0;
            m_scans = 0;
            m_retired = 0;
            m_discarded = 0;
            m_order_errors = 0;
            m_overruns = 0;
            m_order_event = 1'b0;
            m_overrun_event = 1'b0;
            m_exhaust_event = 1'b0;
            q_head = 0;
            q_tail = 0;
            q_level = 0;
            q_acc = 0;
            q_ret = 0;
            q_abort = 0;
        end
    endtask

    task automatic trace_comp(input string phase);
        begin
            if ($test$plusargs("TRACE")) begin
                $display("RAW_SCAN_COMP_TRACE side=%s case=%s cycle=%0d rst=%b stop=%b rearm=%b rearm_tag=%0h sample_strobe=%b sample_channel=%0d sample_data=%04h sample_tick=%0h sample_quality=%02h consumer_ready=%b c_out_valid=%b c_out_data=%016h c_out_ticks=%0h c_out_quality=%08h c_out_first_seq=%0h c_out_last_seq=%0h c_out_tag=%0h c_armed=%b c_partial_len=%0d c_next_seq=%0d c_exhausted=%b c_order_event=%b c_overrun_event=%b c_exhaust_event=%b c_events=%0d c_scans=%0d c_retired=%0d c_discarded=%0d c_order_errors=%0d c_overruns=%0d q_in_ready=%b q_out_valid=%b q_out_ready=%b q_out_data=%016h q_out_ticks=%0h q_out_quality=%08h q_out_first_seq=%0h q_out_last_seq=%0h q_out_tag=%0h q_level=%0d q_accepted=%0d q_retired=%0d q_aborted=%0d ref_partial=%0d ref_slot=%b ref_q_level=%0d ref_q_accepted=%0d ref_q_retired=%0d ref_q_aborted=%0d",
                         phase, comp_case, comp_cycles, rst, stop, rearm, rearm_tag,
                         sample_strobe, sample_channel, sample_data, sample_tick,
                         sample_quality, consumer_ready, collector_out_valid,
                         collector_out_data, collector_out_ticks,
                         collector_out_quality, collector_out_first_seq,
                         collector_out_last_seq, collector_out_tag, collector_armed,
                         collector_partial_len, collector_next_seq,
                         collector_seq_exhausted, collector_order_error_event,
                         collector_overrun_event, collector_seq_exhaust_event,
                         collector_stat_events, collector_stat_scans,
                         collector_stat_retired, collector_stat_discarded_samples,
                         collector_stat_order_errors, collector_stat_overruns,
                         queue_in_ready, queue_out_valid, consumer_ready,
                         queue_out_data, queue_out_ticks, queue_out_quality,
                         queue_out_first_seq, queue_out_last_seq, queue_out_tag,
                         queue_level, queue_stat_accepted, queue_stat_retired,
                         queue_stat_aborted, m_partial_len, m_slot_valid,
                         q_level, q_acc, q_ret, q_abort);
            end
        end
    endtask

    task automatic comp_edge(
        input bit rst_i,
        input bit stop_i,
        input bit rearm_i,
        input bit strobe_i,
        input logic [1:0] channel_i,
        input logic [15:0] data_i,
        input logic [63:0] tick_i,
        input logic [7:0] quality_i,
        input bit ready_i,
        input logic [TAG_R-1:0] tag_i
    );
        bit event_fire;
        bit retire;
        bit qpop;
        bit complete;
        bit terminal;
        bit order_err;
        bit overrun;
        bit start0;
        bit extend;
        logic [2:0] partial_after;
        logic [3:0] discard_order;
        logic [3:0] discard_terminal;
        logic [SEQ_R-1:0] seq_val;
        rec_t new_slot;
        int lane;
        begin
            @(negedge clk);
            rst = rst_i;
            stop = stop_i;
            rearm = rearm_i;
            rearm_tag = tag_i;
            sample_strobe = strobe_i;
            sample_channel = channel_i;
            sample_data = data_i;
            sample_tick = tick_i[TICK_R-1:0];
            sample_quality = quality_i;
            consumer_ready = ready_i;
            #1;
            check_comp_state(1'b1);
            trace_comp("pre");
            if ($test$plusargs("DEBUG")) begin
                $display("RAW_SCAN_COMP_DEBUG pre cycle=%0d rst=%b stop=%b rearm=%b strobe=%b ch=%0d m_partial=%0d dut_partial=%0d q_level=%0d q_acc=%0d q_ret=%0d q_abort=%0d slot=%b c_valid=%b",
                         comp_cycles, rst_i, stop_i, rearm_i, strobe_i, channel_i,
                         m_partial_len, collector_partial_len, q_level, q_acc,
                         q_ret, q_abort, m_slot_valid, collector_out_valid);
            end

            event_fire = !rst_i && !stop_i && !rearm_i && m_armed && strobe_i;
            retire = m_slot_valid && !rst_i && !stop_i && !rearm_i
                     && (q_level < DEPTH_R);
            qpop = !rst_i && !(stop_i || rearm_i) && (q_level > 0) && ready_i;

            @(posedge clk);
            #1;
            if (rst_i) begin
                comp_clear();
            end else if (stop_i) begin
                m_slot = empty_rec();
                m_slot_valid = 1'b0;
                m_armed = 1'b0;
                m_partial_len = 3'd0;
                m_partial_first = '0;
                m_next_seq = '0;
                m_exhausted = 1'b0;
                m_tag = '0;
                for (lane = 0; lane < 4; lane = lane + 1) begin
                    m_partial_data[lane] = 16'd0;
                    m_partial_tick[lane] = 64'd0;
                    m_partial_quality[lane] = 8'd0;
                end
                m_events = 0;
                m_scans = 0;
                m_retired = 0;
                m_discarded = 0;
                m_order_errors = 0;
                m_overruns = 0;
                m_order_event = 1'b0;
                m_overrun_event = 1'b0;
                m_exhaust_event = 1'b0;
                q_abort = q_abort + q_level;
                q_level = 0;
                q_head = 0;
                q_tail = 0;
            end else if (rearm_i) begin
                m_slot = empty_rec();
                m_slot_valid = 1'b0;
                m_armed = 1'b1;
                m_partial_len = 3'd0;
                m_partial_first = '0;
                m_next_seq = '0;
                m_exhausted = 1'b0;
                m_tag = tag_i;
                for (lane = 0; lane < 4; lane = lane + 1) begin
                    m_partial_data[lane] = 16'd0;
                    m_partial_tick[lane] = 64'd0;
                    m_partial_quality[lane] = 8'd0;
                end
                m_events = 0;
                m_scans = 0;
                m_retired = 0;
                m_discarded = 0;
                m_order_errors = 0;
                m_overruns = 0;
                m_order_event = 1'b0;
                m_overrun_event = 1'b0;
                m_exhaust_event = 1'b0;
                q_abort = q_abort + q_level;
                q_level = 0;
                q_head = 0;
                q_tail = 0;
            end else begin
                order_err = 1'b0;
                complete = 1'b0;
                start0 = 1'b0;
                extend = 1'b0;
                terminal = 1'b0;
                partial_after = m_partial_len;
                discard_order = 4'd0;
                seq_val = m_next_seq;
                if (event_fire) begin
                    if (m_partial_len == 3'd0) begin
                        if (channel_i == 2'd0) begin
                            start0 = 1'b1;
                            partial_after = 3'd1;
                        end else begin
                            order_err = 1'b1;
                            discard_order = 4'd1;
                        end
                    end else if (channel_i == m_partial_len[1:0]) begin
                        if (m_partial_len == 3'd3) begin
                            complete = 1'b1;
                            partial_after = 3'd0;
                        end else begin
                            extend = 1'b1;
                            partial_after = m_partial_len + 3'd1;
                        end
                    end else begin
                        order_err = 1'b1;
                        if (channel_i == 2'd0) begin
                            start0 = 1'b1;
                            partial_after = 3'd1;
                            discard_order = {1'b0, m_partial_len};
                        end else begin
                            partial_after = 3'd0;
                            discard_order = {1'b0, m_partial_len} + 4'd1;
                        end
                    end
                    terminal = (seq_val == SEQ_LAST);
                end

                discard_terminal = 4'd0;
                if (terminal && (partial_after != 3'd0)) begin
                    discard_terminal = {1'b0, partial_after};
                    partial_after = 3'd0;
                end
                overrun = complete && m_slot_valid && !retire;

                if (qpop) begin
                    q_ret = q_ret + 1;
                    if (q_head == DEPTH_R - 1) begin
                        q_head = 0;
                    end else begin
                        q_head = q_head + 1;
                    end
                    q_level = q_level - 1;
                end
                if (retire) begin
                    q_mem[q_tail] = m_slot;
                    if (q_tail == DEPTH_R - 1) begin
                        q_tail = 0;
                    end else begin
                        q_tail = q_tail + 1;
                    end
                    q_acc = q_acc + 1;
                    q_level = q_level + 1;
                end

                if (event_fire) m_events = m_events + 1;
                if (complete) m_scans = m_scans + 1;
                if (retire) m_retired = m_retired + 1;
                if (order_err) m_order_errors = m_order_errors + 1;
                if (overrun) m_overruns = m_overruns + 1;
                m_discarded = m_discarded + discard_order + discard_terminal
                              + (overrun ? 4 : 0);

                if (complete) begin
                    if (!m_slot_valid || retire) begin
                        new_slot = make_rec(
                            {data_i, m_partial_data[2], m_partial_data[1],
                             m_partial_data[0]},
                            pack_ticks4(m_partial_tick[0], m_partial_tick[1],
                                        m_partial_tick[2], tick_i),
                            {quality_i, m_partial_quality[2],
                             m_partial_quality[1], m_partial_quality[0]},
                            m_partial_first,
                            m_partial_first + 3,
                            m_tag
                        );
                        m_slot = new_slot;
                        m_slot_valid = 1'b1;
                    end
                end else if (retire) begin
                    m_slot_valid = 1'b0;
                end

                if (event_fire) begin
                    if (start0) begin
                        m_partial_data[0] = data_i;
                        m_partial_tick[0] = tick_i;
                        m_partial_quality[0] = quality_i;
                        m_partial_first = seq_val;
                        m_partial_len = 3'd1;
                        for (lane = 1; lane < 4; lane = lane + 1) begin
                            m_partial_data[lane] = 16'd0;
                            m_partial_tick[lane] = 64'd0;
                            m_partial_quality[lane] = 8'd0;
                        end
                    end else if (extend) begin
                        m_partial_data[m_partial_len] = data_i;
                        m_partial_tick[m_partial_len] = tick_i;
                        m_partial_quality[m_partial_len] = quality_i;
                        m_partial_len = m_partial_len + 3'd1;
                    end else begin
                        m_partial_len = 3'd0;
                        m_partial_first = '0;
                        for (lane = 0; lane < 4; lane = lane + 1) begin
                            m_partial_data[lane] = 16'd0;
                            m_partial_tick[lane] = 64'd0;
                            m_partial_quality[lane] = 8'd0;
                        end
                    end
                    if (complete) begin
                        m_partial_len = 3'd0;
                        m_partial_first = '0;
                        for (lane = 0; lane < 4; lane = lane + 1) begin
                            m_partial_data[lane] = 16'd0;
                            m_partial_tick[lane] = 64'd0;
                            m_partial_quality[lane] = 8'd0;
                        end
                    end
                    if (terminal) begin
                        m_armed = 1'b0;
                        m_exhausted = 1'b1;
                        m_next_seq = SEQ_LAST;
                        m_partial_len = 3'd0;
                        m_partial_first = '0;
                        for (lane = 0; lane < 4; lane = lane + 1) begin
                            m_partial_data[lane] = 16'd0;
                            m_partial_tick[lane] = 64'd0;
                            m_partial_quality[lane] = 8'd0;
                        end
                    end else begin
                        m_next_seq = m_next_seq + 1'b1;
                    end
                end
                m_order_event = order_err;
                m_overrun_event = overrun;
                m_exhaust_event = terminal;
            end
            comp_cycles = comp_cycles + 1;
            check_comp_state(1'b1);
            trace_comp("post");
            if ($test$plusargs("DEBUG")) begin
                $display("RAW_SCAN_COMP_DEBUG post cycle=%0d m_partial=%0d dut_partial=%0d q_level=%0d q_acc=%0d q_ret=%0d q_abort=%0d slot=%b c_valid=%b",
                         comp_cycles, m_partial_len, collector_partial_len, q_level,
                         q_acc, q_ret, q_abort, m_slot_valid, collector_out_valid);
            end
        end
    endtask

    task automatic comp_reset();
        begin
            comp_edge(1'b1, 1'b0, 1'b0, 1'b0, 2'd0, 16'd0, 64'd0, 8'd0, 1'b0, '0);
            comp_edge(1'b1, 1'b0, 1'b0, 1'b0, 2'd0, 16'd0, 64'd0, 8'd0, 1'b0, '0);
            comp_edge(1'b0, 1'b0, 1'b0, 1'b0, 2'd0, 16'd0, 64'd0, 8'd0, 1'b0, '0);
        end
    endtask

    task automatic comp_rearm(input logic [TAG_R-1:0] tag_i);
        begin
            comp_edge(1'b0, 1'b0, 1'b1, 1'b1, 2'd0, 16'h1111,
                      64'h2222_3333_4444_5555, 8'h66, 1'b0, tag_i);
        end
    endtask

    task automatic comp_stop();
        begin
            comp_edge(1'b0, 1'b1, 1'b0, 1'b1, 2'd3, 16'hdead,
                      64'hfeed_face_dead_beef, 8'hff, 1'b1, '0);
        end
    endtask

    task automatic comp_sample(
        input logic [1:0] channel_i,
        input logic [15:0] data_i,
        input logic [63:0] tick_i,
        input logic [7:0] quality_i,
        input bit ready_i
    );
        begin
            comp_edge(1'b0, 1'b0, 1'b0, 1'b1, channel_i, data_i,
                      tick_i, quality_i, ready_i, '0);
        end
    endtask

    task automatic comp_idle(input bit ready_i);
        begin
            comp_edge(1'b0, 1'b0, 1'b0, 1'b0, 2'd0, 16'd0,
                      64'd0, 8'd0, ready_i, '0);
        end
    endtask

    task automatic comp_good_scan(input logic [63:0] base, input bit ready_i);
        begin
            comp_sample(2'd0, base[15:0], base, base[7:0], ready_i);
            comp_sample(2'd1, base[15:0] + 16'd1, base + 1,
                        base[7:0] + 8'd1, ready_i);
            comp_sample(2'd2, base[15:0] + 16'd2, base + 2,
                        base[7:0] + 8'd2, ready_i);
            comp_sample(2'd3, base[15:0] + 16'd3, base + 3,
                        base[7:0] + 8'd3, ready_i);
        end
    endtask

    task automatic comp_wrong_scan(input bit ready_i);
        begin
            comp_sample(2'd2, 16'h0202, 64'h0000_0000_0000_2000, 8'h02, ready_i);
            comp_good_scan(64'h0000_0000_0000_2100, ready_i);
        end
    endtask

    task automatic comp_fill_queue(input int target, input logic [63:0] base);
        int index;
        begin
            for (index = 0; index < target; index = index + 1) begin
                comp_good_scan(base + index * 64'h10, 1'b0);
                comp_idle(1'b0);
            end
        end
    endtask

    task automatic comp_drain_all();
        int guard;
        begin
            for (guard = 0; guard < DEPTH_R + 32; guard = guard + 1) begin
                if ((q_level == 0) && (!m_slot_valid)) begin
                    guard = DEPTH_R + 32;
                end else begin
                    comp_idle(1'b1);
                end
            end
            check_int("drain_q_level", 0, q_level);
            check_int("drain_slot_valid", 0, m_slot_valid);
        end
    endtask

    task automatic comp_basic_schedule();
        begin
            comp_reset();
            comp_rearm(64'h0000_0000_0000_00a1);

            comp_fill_queue(DEPTH_R, 64'h0000_0000_0000_1000);
            comp_good_scan(64'h0000_0000_0000_3000, 1'b0);
            comp_good_scan(64'h0000_0000_0000_3100, 1'b0);
            check_int("basic_overrun_present", 1, (m_overruns > 0) ? 1 : 0);
            comp_idle(1'b0);
            comp_drain_all();

            comp_rearm(64'h0000_0000_0000_00a1);
            comp_wrong_scan(1'b0);
            comp_idle(1'b0);
            comp_idle(1'b1);

            comp_fill_queue(DEPTH_R, 64'h0000_0000_0000_4000);
            comp_good_scan(64'h0000_0000_0000_5000, 1'b0);
            comp_sample(2'd0, 16'h6000, 64'h0000_0000_0000_6000, 8'h60, 1'b0);
            comp_stop();
            check_int("basic_stop_q_level", 0, q_level);
            check_int("basic_stop_abort_present", 1, (q_abort > 0) ? 1 : 0);

            comp_rearm(64'h0000_0000_0000_00a1);
            comp_good_scan(64'h0000_0000_0000_7000, 1'b0);
            comp_idle(1'b0);
            comp_idle(1'b1);

            comp_rearm(64'h0000_0000_0000_00a1);
            comp_sample(2'd0, 16'h7100, 64'h0000_0000_0000_7100, 8'h71, 1'b0);
            comp_sample(2'd1, 16'h7101, 64'h0000_0000_0000_7101, 8'h72, 1'b0);
            comp_rearm(64'h0000_0000_0000_00a1);
            comp_good_scan(64'h0000_0000_0000_7200, 1'b0);
            comp_idle(1'b0);
            comp_idle(1'b1);

            comp_rearm(64'h0000_0000_0000_00b2);
            comp_sample(2'd0, 16'h7300, 64'h0000_0000_0000_7300, 8'h73, 1'b0);
            comp_rearm(64'h0000_0000_0000_00b2);
            comp_good_scan(64'h0000_0000_0000_7400, 1'b0);
            comp_idle(1'b0);
            comp_idle(1'b1);
            comp_drain_all();
        end
    endtask

    task automatic comp_exhaust_schedule();
        begin
            comp_reset();
            comp_rearm(64'h0000_0000_0000_00c3);

            comp_good_scan(64'h0000_0000_0000_1000, 1'b0);
            comp_idle(1'b0);
            check_int("exhaust_armed", 0, m_armed);
            check_int("exhaust_flag", 1, m_exhausted);
            check_int("exhaust_q_level", 1, q_level);
            check_int("exhaust_scans", 1, m_scans);
            comp_sample(2'd0, 16'h1100, 64'h0000_0000_0000_1100, 8'h11, 1'b0);
            check_int("exhaust_ignored_events", 4, m_events);
            comp_idle(1'b1);
            comp_idle(1'b1);

            comp_rearm(64'h0000_0000_0000_00c3);
            comp_sample(2'd0, 16'h2100, 64'h0000_0000_0000_2100, 8'h21, 1'b0);
            comp_sample(2'd1, 16'h2101, 64'h0000_0000_0000_2101, 8'h22, 1'b0);
            comp_sample(2'd0, 16'h2102, 64'h0000_0000_0000_2102, 8'h23, 1'b0);
            comp_sample(2'd2, 16'h2103, 64'h0000_0000_0000_2103, 8'h24, 1'b0);
            check_int("exhaust_partial_armed", 0, m_armed);
            check_int("exhaust_partial_flag", 1, m_exhausted);
            check_int("exhaust_partial_scans", 0, m_scans);
            check_int("exhaust_partial_events", 4, m_events);
            check_int("exhaust_partial_discarded", 4, m_discarded);
            check_int("exhaust_partial_order_errors", 2, m_order_errors);
            comp_idle(1'b1);

            comp_rearm(64'h0000_0000_0000_00d4);
            comp_fill_queue(1, 64'h0000_0000_0000_3000);
            comp_stop();
            check_int("exhaust_stop_q_level", 0, q_level);
            check_int("exhaust_stop_abort_present", 1, (q_abort > 0) ? 1 : 0);
            comp_rearm(64'h0000_0000_0000_00d4);
            comp_good_scan(64'h0000_0000_0000_4000, 1'b0);
            comp_idle(1'b0);
            comp_idle(1'b1);
            comp_drain_all();
        end
    endtask

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        rst = 1'b0;
        stop = 1'b0;
        rearm = 1'b0;
        rearm_tag = '0;
        sample_strobe = 1'b0;
        sample_channel = 2'd0;
        sample_data = 16'd0;
        sample_tick = '0;
        sample_quality = 8'd0;
        consumer_ready = 1'b0;
        comp_checks = 0;
        comp_errors = 0;
        comp_cycles = 0;
        comp_case = "comp_basic";
        if (!$value$plusargs("CASE=%s", comp_case)) begin
            comp_case = "comp_basic";
        end
        comp_clear();
        if ((DEPTH < 1) || (DEPTH > 8) || (SEQ_W < 2) || (SEQ_W > 32)
            || (TICK_W < 1) || (TICK_W > 64) || (TAG_W < 1) || (TAG_W > 64)
            || (STAT_W < 2) || (STAT_W > 32)) begin
            $display("RAW_SCAN_COMP_GUARD_SHELL");
            #100;
            $display("RAW_SCAN_COMP_GUARD_MISSING");
            $finish;
        end
        if (comp_case == "comp_exhaust") begin
            comp_exhaust_schedule();
        end else begin
            comp_basic_schedule();
        end
        check_int("final_q_level", 0, q_level);
        check_int("final_slot_valid", 0, m_slot_valid);
        check_int("q_balance", q_acc, q_ret + q_abort + q_level);
        check_int("c_event_identity", m_events,
                  4 * (m_retired + ((m_slot_valid) ? 1 : 0))
                  + m_partial_len + m_discarded);
        check_int("c_scan_identity", m_scans,
                  m_retired + ((m_slot_valid) ? 1 : 0) + m_overruns);
        $display("RAW_SCAN_COMP_STATS case=%s depth=%0d seq_w=%0d tick_w=%0d tag_w=%0d stat_w=%0d checks=%0d errors=%0d q_level=%0d q_accepted=%0d q_retired=%0d q_aborted=%0d q_true_accepted=%0d q_true_retired=%0d q_true_aborted=%0d c_events=%0d c_scans=%0d c_retired=%0d c_discarded=%0d c_order_errors=%0d c_overruns=%0d c_true_events=%0d c_true_scans=%0d c_true_retired=%0d c_true_discarded=%0d c_true_order_errors=%0d c_true_overruns=%0d c_armed=%0d c_partial_len=%0d c_exhausted=%0d c_occupied=%0d cycles=%0d",
                 comp_case, DEPTH, SEQ_W, TICK_W, TAG_W, STAT_W,
                 comp_checks, comp_errors, q_level, sat_value(q_acc),
                 sat_value(q_ret), sat_value(q_abort), q_acc, q_ret, q_abort,
                 sat_value(m_events), sat_value(m_scans),
                 sat_value(m_retired), sat_value(m_discarded),
                 sat_value(m_order_errors), sat_value(m_overruns),
                 m_events, m_scans, m_retired, m_discarded,
                 m_order_errors, m_overruns, m_armed, m_partial_len,
                 m_exhausted, m_slot_valid, comp_cycles);
        if (comp_errors == 0) begin
            $display("RAW_SCAN_COMP_PASS");
        end else begin
            $display("RAW_SCAN_COMP_FAIL");
        end
        $finish;
    end

endmodule

