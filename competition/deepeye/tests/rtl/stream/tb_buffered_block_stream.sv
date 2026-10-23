// Public-port author fixture for the bounded buffered block-stream candidate.

`timescale 1ns/1ps

module tb_buffered_block_stream;
    `include "bbs_vectors.svh"

    localparam int MAX_CYCLES = 3_000_000;
    localparam logic [15:0] TAG_BASE = 16'h3500;

    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic cfg_valid = 1'b0;
    logic [7:0] cfg_count = 8'd0;
    logic [3:0] cfg_e = 4'd0;
    logic [15:0] cfg_tag = 16'd0;
    logic s_valid = 1'b0;
    logic [15:0] s_data = 16'd0;
    logic s_last = 1'b0;
    logic out_meta_ready = 1'b0;
    logic out_ready = 1'b0;

    logic cfg_ready;
    logic s_ready;
    logic out_meta_valid;
    logic [15:0] out_meta_tag;
    logic [1:0] out_meta_error;
    logic [7:0] out_meta_count;
    logic [3:0] out_meta_e;
    logic out_meta_raw;
    logic [3:0] out_meta_k;
    logic [11:0] out_meta_valid_bits;
    logic [8:0] out_meta_bytes;
    logic out_valid;
    logic [7:0] out_data;
    logic out_last;
    logic [1:0] stream_level;
    logic stream_filling;
    logic [1:0] queue_level;
    logic queue_receiving;
    logic queue_faulted;
    logic queue_fault_event;
    logic [1:0] queue_fault_code;
    logic [31:0] stream_stat_cfg;
    logic [31:0] stream_stat_samples;
    logic [31:0] stream_stat_ok;
    logic [31:0] stream_stat_error;
    logic [31:0] stream_stat_aborted;
    logic [31:0] queue_stat_meta;
    logic [31:0] queue_stat_in_bytes;
    logic [31:0] queue_stat_retired;
    logic [31:0] queue_stat_aborted;
    logic [31:0] queue_stat_fault;

    string active_case = "startup";
    int suite_cases = 0;
    int suite_checks = 0;
    int suite_failures = 0;
    int case_checks = 0;
    int case_failures = 0;
    int cycle_count = 0;
    bit watchdog_fired = 1'b0;

    deepeye_buffered_block_stream dut (
        .clk(clk), .rst(rst), .cancel(cancel),
        .cfg_valid(cfg_valid), .cfg_ready(cfg_ready),
        .cfg_count(cfg_count), .cfg_e(cfg_e), .cfg_tag(cfg_tag),
        .s_valid(s_valid), .s_ready(s_ready), .s_data(s_data), .s_last(s_last),
        .out_meta_valid(out_meta_valid), .out_meta_ready(out_meta_ready),
        .out_meta_tag(out_meta_tag), .out_meta_error(out_meta_error),
        .out_meta_count(out_meta_count), .out_meta_e(out_meta_e),
        .out_meta_raw(out_meta_raw), .out_meta_k(out_meta_k),
        .out_meta_valid_bits(out_meta_valid_bits),
        .out_meta_bytes(out_meta_bytes),
        .out_valid(out_valid), .out_ready(out_ready),
        .out_data(out_data), .out_last(out_last),
        .stream_level(stream_level), .stream_filling(stream_filling),
        .queue_level(queue_level), .queue_receiving(queue_receiving),
        .queue_faulted(queue_faulted), .queue_fault_event(queue_fault_event),
        .queue_fault_code(queue_fault_code),
        .stream_stat_cfg(stream_stat_cfg),
        .stream_stat_samples(stream_stat_samples),
        .stream_stat_ok(stream_stat_ok),
        .stream_stat_error(stream_stat_error),
        .stream_stat_aborted(stream_stat_aborted),
        .queue_stat_meta(queue_stat_meta),
        .queue_stat_in_bytes(queue_stat_in_bytes),
        .queue_stat_retired(queue_stat_retired),
        .queue_stat_aborted(queue_stat_aborted),
        .queue_stat_fault(queue_stat_fault)
    );

    always @(posedge clk) begin
        cycle_count <= cycle_count + 1;
        if (cycle_count > MAX_CYCLES && !watchdog_fired) begin
            watchdog_fired <= 1'b1;
            $fatal(1, "BBS_WATCHDOG");
        end
    end

    // All observations use public ports. Tags are deliberately not identities.
    int case_id = -1;
    int check_seq = 0;
    int observed_cycles = 0;
    int drive_vector = 0;
    bit did_cfg = 0;
    bit did_sample = 0;
    int ledger_vec [0:4095];
    int ledger_tag [0:4095];
    int ledger_head = 0;
    int ledger_tail = 0;
    int live = 0;
    int terminals = 0;
    int meta_count_seen = 0;
    int payload_bytes_seen = 0;
    bit head_meta = 0;
    int head_offset = 0;
    int epoch_cfg = 0;
    int epoch_samples = 0;
    int epoch_retired = 0;
    int expected_stream_aborted = 0;
    int expected_queue_aborted = 0;
    bit held_meta = 0;
    bit held_byte = 0;
    logic [62:0] held_meta_value;
    logic [8:0] held_byte_value;

    task automatic check_value(input bit condition, input string label,
                               input int observed, input int expected);
        begin
            check_seq = check_seq + 1;
            suite_checks = suite_checks + 1;
            case_checks = case_checks + 1;
            $display("BBS_CHECK seq=%0d case=%0d label=%s observed=%0d expected=%0d result=%s",
                     check_seq, case_id, label, observed, expected,
                     condition ? "PASS" : "FAIL");
            if (!condition) begin
                suite_failures = suite_failures + 1;
                case_failures = case_failures + 1;
                $fatal(1, "BBS_CHECK_FAILED");
            end
        end
    endtask

    task automatic guard(input bit condition, input string label);
        begin
            if (!condition)
                check_value(0, label, cycle_count, -1);
        end
    endtask

    task automatic terminal_one(input string outcome);
        begin
            guard(ledger_head < ledger_tail, "terminal_without_admission");
            $display("BBS_TERMINAL id=%0d case=%0d outcome=%s",
                     ledger_head, case_id, outcome);
            ledger_head = ledger_head + 1;
            live = live - 1;
            terminals = terminals + 1;
            head_meta = 0;
            head_offset = 0;
        end
    endtask

    // Return at a falling edge, leaving every driver stable for the next rise.
    task automatic step;
        int vid;
        int old_stream_level;
        int old_queue_level;
        logic [62:0] metadata;
        begin
            @(posedge clk);
            old_stream_level = rst ? 0 : int'(stream_level);
            old_queue_level = rst ? 0 : int'(queue_level);
            did_cfg = 0;
            did_sample = 0;
            metadata = {out_meta_tag, out_meta_error, out_meta_count,
                        out_meta_e, out_meta_raw, out_meta_k,
                        out_meta_valid_bits, out_meta_bytes};
            if (rst || cancel) begin
                guard(!cfg_ready && !s_ready && !out_meta_valid && !out_valid,
                      "clear_gates_transfers");
                while (live != 0)
                    terminal_one(rst ? "reset" : "cancel");
                if (rst) begin
                    epoch_cfg = 0;
                    epoch_samples = 0;
                    epoch_retired = 0;
                    expected_stream_aborted = 0;
                    expected_queue_aborted = 0;
                end else begin
                    expected_stream_aborted = expected_stream_aborted + old_stream_level;
                    expected_queue_aborted = expected_queue_aborted + old_queue_level;
                end
                held_meta = 0;
                held_byte = 0;
            end else begin
                if (held_meta)
                    guard(out_meta_valid && (metadata === held_meta_value),
                          "metadata_stable_when_stalled");
                if (held_byte)
                    guard(out_valid && ({out_data, out_last} === held_byte_value),
                          "byte_stable_when_stalled");
                held_meta = out_meta_valid && !out_meta_ready;
                held_meta_value = metadata;
                held_byte = out_valid && !out_ready;
                held_byte_value = {out_data, out_last};
                guard(!(out_valid && out_meta_valid), "no_metadata_byte_bypass");
                if (cfg_valid && cfg_ready) begin
                    guard(ledger_tail < 4096, "ledger_capacity");
                    ledger_vec[ledger_tail] = drive_vector;
                    ledger_tag[ledger_tail] = int'(cfg_tag);
                    $display("BBS_ADMIT id=%0d case=%0d vector=%0d tag=%0d",
                             ledger_tail, case_id, drive_vector, cfg_tag);
                    ledger_tail = ledger_tail + 1;
                    live = live + 1;
                    epoch_cfg = epoch_cfg + 1;
                    did_cfg = 1;
                end
                if (s_valid && s_ready) begin
                    epoch_samples = epoch_samples + 1;
                    did_sample = 1;
                end
                if (out_meta_valid && out_meta_ready) begin
                    guard((live != 0) && !head_meta, "one_ordered_metadata");
                    vid = ledger_vec[ledger_head];
                    guard(out_meta_tag === 16'(ledger_tag[ledger_head]), "metadata_tag");
                    guard(out_meta_error === 2'(v_error[vid]), "metadata_error");
                    guard(out_meta_count === 8'(v_meta_count[vid]), "metadata_count");
                    guard(out_meta_e === 4'(v_meta_e[vid]), "metadata_e");
                    guard(out_meta_raw === 1'(v_raw[vid]), "metadata_raw");
                    guard(out_meta_k === 4'(v_k[vid]), "metadata_k");
                    guard(out_meta_valid_bits === 12'(v_bits[vid]), "metadata_valid_bits");
                    guard(out_meta_bytes === 9'(v_bytes[vid]), "metadata_bytes");
                    meta_count_seen = meta_count_seen + 1;
                    if (v_error[vid] != 0) begin
                        terminal_one("error");
                        epoch_retired = epoch_retired + 1;
                    end else begin
                        head_meta = 1;
                    end
                end
                if (out_valid && out_ready) begin
                    guard((live != 0) && head_meta, "payload_after_metadata");
                    vid = ledger_vec[ledger_head];
                    guard(head_offset < v_bytes[vid], "no_excess_payload");
                    guard(out_data === v_payload[vid][head_offset], "exact_payload_byte");
                    guard(out_last === (head_offset == v_bytes[vid] - 1), "exact_payload_last");
                    head_offset = head_offset + 1;
                    payload_bytes_seen = payload_bytes_seen + 1;
                    if (out_last) begin
                        terminal_one("ok");
                        epoch_retired = epoch_retired + 1;
                    end
                end
            end
            #1;
            observed_cycles = observed_cycles + 1;
            guard(stream_level <= 2 && queue_level <= 2, "bounded_stage_levels");
            guard(live == int'(stream_level) + int'(queue_level) -
                          (queue_receiving ? 1 : 0), "unique_residency_no_double_credit");
            guard(stream_stat_cfg === 32'(epoch_cfg), "exact_cfg_counter");
            guard(stream_stat_samples === 32'(epoch_samples), "exact_sample_counter");
            guard(stream_stat_aborted === 32'(expected_stream_aborted), "raw_abort_counter");
            guard(queue_stat_aborted === 32'(expected_queue_aborted), "encoded_abort_counter");
            guard(queue_stat_retired === 32'(epoch_retired), "exact_retirement_counter");
            guard(stream_stat_cfg == stream_stat_ok + stream_stat_error +
                  stream_stat_aborted + stream_level, "raw_stage_conservation");
            guard(queue_stat_meta == queue_stat_retired + queue_stat_aborted +
                  queue_level, "encoded_stage_conservation");
            guard(!queue_faulted && !queue_fault_event && queue_fault_code == 0 &&
                  queue_stat_fault == 0, "legal_producer_no_queue_fault");
            @(negedge clk);
        end
    endtask

    task automatic ticks(input int count);
        repeat (count) step();
    endtask

    task automatic begin_case(input string name);
        begin
            guard(live == 0, "case_starts_empty");
            case_id = case_id + 1;
            suite_cases = suite_cases + 1;
            active_case = name;
            case_checks = 0;
            case_failures = 0;
            $display("BBS_CASE_BEGIN case=%0d name=%s", case_id, active_case);
            cfg_valid = 0;
            s_valid = 0;
            cancel = 0;
            rst = 1;
            step();
            rst = 0;
            out_meta_ready = 1;
            out_ready = 1;
        end
    endtask

    task automatic end_case;
        begin
            ticks(3);
            check_value(live == 0 && stream_level == 0 && queue_level == 0 &&
                        !out_meta_valid && !out_valid, "all_admissions_terminal", live, 0);
            $display("BBS_CASE_END case=%0d name=%s checks=%0d failures=%0d",
                     case_id, active_case, case_checks, case_failures);
        end
    endtask

    task automatic admit(input int vid, input int tag);
        int k;
        begin : bounded_admission
            drive_vector = vid;
            cfg_count = 8'(v_count[vid]);
            cfg_e = 4'(v_e[vid]);
            cfg_tag = 16'(tag);
            cfg_valid = 1;
            for (k = 0; k < 100000; k = k + 1) begin
                step();
                if (did_cfg) begin
                    cfg_valid = 0;
                    disable bounded_admission;
                end
            end
            check_value(0, "configuration_watchdog", k, -1);
        end
    endtask

    task automatic send_sample(input int value, input bit last_value);
        int k;
        begin : bounded_sample
            s_data = 16'(value);
            s_last = last_value;
            s_valid = 1;
            for (k = 0; k < 100000; k = k + 1) begin
                step();
                if (did_sample) begin
                    s_valid = 0;
                    disable bounded_sample;
                end
            end
            check_value(0, "sample_watchdog", k, -1);
        end
    endtask

    task automatic send_vector(input int vid, input int tag);
        int i;
        begin
            admit(vid, tag);
            for (i = 0; i < v_send[vid]; i = i + 1) begin
                if ((i % 7) == 3) ticks(2);
                send_sample(int'(v_samples[vid][i]), v_last[vid][i]);
            end
        end
    endtask

    task automatic drain;
        int k;
        begin : bounded_drain
            out_meta_ready = 1;
            out_ready = 1;
            for (k = 0; k < 100000; k = k + 1) begin
                if (live == 0) disable bounded_drain;
                // Deterministic independent metadata/byte stalls.
                out_meta_ready = ((k % 11) != 2) && ((k % 11) != 3);
                out_ready = ((k % 7) != 0) && ((k % 7) != 1);
                step();
            end
            check_value(0, "drain_watchdog", k, -1);
        end
    endtask

    task automatic wait_queue(input int wanted_level, input bit wanted_receiving);
        int k;
        begin : bounded_queue_wait
            for (k = 0; k < 100000; k = k + 1) begin
                if ((int'(queue_level) == wanted_level) &&
                    (queue_receiving == wanted_receiving)) disable bounded_queue_wait;
                step();
            end
            check_value(0, "queue_state_watchdog", k, -1);
        end
    endtask

    task automatic wait_final;
        int k;
        begin : bounded_final_wait
            out_meta_ready = 1;
            out_ready = 0;
            for (k = 0; k < 100000; k = k + 1) begin
                if (out_valid && out_last) disable bounded_final_wait;
                if (out_valid && !out_last) out_ready = 1;
                step();
                out_ready = 0;
            end
            check_value(0, "final_state_watchdog", k, -1);
        end
    endtask

    // Caller-initiated shared clear. Inputs are deliberately valid on the edge.
    task automatic clear_once(input bit use_reset, input bit both);
        int raw_before;
        int encoded_before;
        int cfg_before;
        int bytes_before;
        int meta_before;
        begin
            raw_before = int'(stream_level);
            encoded_before = int'(queue_level);
            cfg_before = int'(stream_stat_cfg);
            bytes_before = int'(queue_stat_in_bytes);
            meta_before = int'(queue_stat_meta);
            check_value(live > 0, "clear_has_actual_residency", live > 0 ? 1 : 0, 1);
            cfg_valid = 1;
            s_valid = 1;
            out_meta_ready = 1;
            out_ready = 1;
            rst = use_reset;
            cancel = !use_reset || both;
            step();
            check_value(stream_level == 0 && queue_level == 0 && !queue_receiving &&
                        !stream_filling, "clear_empties_both_stages", live, 0);
            if (use_reset) begin
                check_value(stream_stat_cfg == 0 && queue_stat_meta == 0 &&
                            stream_stat_aborted == 0 && queue_stat_aborted == 0 &&
                            queue_stat_in_bytes == 0, "reset_priority_counters", 0, 0);
            end else begin
                check_value(stream_stat_aborted == raw_before &&
                            queue_stat_aborted == encoded_before,
                            "cancel_separate_overlap_accounting",
                            int'(stream_stat_aborted) + int'(queue_stat_aborted),
                            raw_before + encoded_before);
                check_value(stream_stat_cfg == cfg_before &&
                            queue_stat_meta == meta_before &&
                            queue_stat_in_bytes == bytes_before,
                            "cancel_preserves_stage_counters", int'(stream_stat_cfg), cfg_before);
            end
            cfg_valid = 0;
            s_valid = 0;
            rst = 0;
            cancel = 0;
            ticks(4);
            send_vector(V_SINGLE, 16'hface);
            drain();
        end
    endtask

    // Every interruption boundary is set using public levels/counters/channels.
    task automatic interruption_case(input int phase, input bit use_reset);
        int i;
        int k;
        string phase_name;
        begin
            case (phase)
                0: phase_name = "raw_fill";
                1: phase_name = "encoding";
                2: phase_name = "metadata_boundary";
                3: phase_name = "encoded_fill";
                4: phase_name = "output_stall";
                5: phase_name = "final_data";
                default: phase_name = "final_error_metadata";
            endcase
            begin_case({use_reset ? "reset_" : "cancel_", phase_name});
            out_meta_ready = 0;
            out_ready = 0;
            case (phase)
                0: begin
                    admit(V_LONG, 16'h8800);
                    for (i = 0; i < 8; i = i + 1)
                        send_sample(int'(v_samples[V_LONG][i]), 0);
                    check_value(stream_filling && stream_level == 1 &&
                                queue_level == 0, "raw_fill_boundary", int'(stream_level), 1);
                end
                1: begin
                    send_vector(V_LONG, 16'h8801);
                    ticks(12);
                    check_value(stream_level == 1 && !stream_filling &&
                                queue_stat_meta == 0, "encoding_public_boundary",
                                int'(queue_stat_meta), 0);
                end
                2: begin
                    admit(V_ERR, 16'h8802);
                    check_value(stream_level == 1 && queue_stat_meta == 0,
                                "pre_metadata_transfer_boundary", int'(stream_level), 1);
                end
                3: begin : filling_wait
                    send_vector(V_LONG, 16'h8803);
                    for (k = 0; k < 100000; k = k + 1) begin
                        if (queue_receiving && queue_stat_in_bytes > 0)
                            disable filling_wait;
                        step();
                    end
                    check_value(0, "encoded_fill_watchdog", k, -1);
                end
                4: begin
                    send_vector(V_SINGLE, 16'h8804);
                    wait_queue(1, 0);
                    out_meta_ready = 1;
                    step();
                    out_meta_ready = 0;
                    ticks(6);
                    admit(V_LONG, 16'h9904);
                    send_sample(16'h1234, 0);
                    check_value(out_valid && stream_filling && queue_level == 1,
                                "stalled_output_and_raw_fill", live, 2);
                end
                5: begin
                    send_vector(V_SINGLE, 16'h8805);
                    wait_queue(1, 0);
                    wait_final();
                    check_value(out_valid && out_last, "final_data_boundary", 1, 1);
                end
                default: begin
                    send_vector(V_ERR, 16'h8806);
                    wait_queue(1, 0);
                    check_value(out_meta_valid && out_meta_error != 0,
                                "final_error_metadata_boundary", 1, 1);
                end
            endcase
            if (phase == 3)
                check_value(queue_receiving && stream_level == 1 &&
                            queue_level == 1, "overlapping_same_block_reservations", live, 1);
            clear_once(use_reset, 0);
            end_case();
        end
    endtask

    initial begin : author_suite
        int i;
        int p;
        int qmeta_before;
        int retired_before;
        int raw_before;
        int sample_before;
        int bytes_expected;
        int success_expected;
        int error_expected;
        load_vectors();
        @(negedge clk);
        $display("BBS_SUITE_BEGIN version=1");

        begin_case("valid_vectors");
        bytes_expected = 0;
        success_expected = 0;
        for (i = 0; i < V_TOTAL; i = i + 1) begin
            if (v_error[i] == 0) begin
                send_vector(i, 16'h3500 + i);
                bytes_expected = bytes_expected + v_bytes[i];
                success_expected = success_expected + 1;
            end
        end
        drain();
        check_value(queue_stat_in_bytes == bytes_expected,
                    "all_expected_encoded_bytes", int'(queue_stat_in_bytes), bytes_expected);
        check_value(stream_stat_ok == success_expected && stream_stat_error == 0,
                    "raw_success_error_split", int'(stream_stat_ok), success_expected);
        end_case();

        begin_case("error_order_duplicate_tags");
        error_expected = 0;
        send_vector(V_SINGLE, 16'hbbbb);
        for (i = 0; i < V_TOTAL; i = i + 1) begin
            if (v_error[i] != 0) begin
                send_vector(i, 16'hbbbb);
                send_vector(V_SINGLE, 16'hbbbb);
                error_expected = error_expected + 1;
            end
        end
        drain();
        check_value(stream_stat_error == error_expected,
                    "all_config_last_errors", int'(stream_stat_error), error_expected);
        check_value(queue_stat_fault == 0, "upstream_errors_are_frames", int'(queue_stat_fault), 0);
        end_case();

        begin_case("full_queue_frontend_backpressure");
        out_meta_ready = 0;
        out_ready = 0;
        send_vector(V_SINGLE, 16'h7777);
        wait_queue(1, 0);
        send_vector(V_SINGLE, 16'h7777);
        wait_queue(2, 0);
        send_vector(V_SINGLE, 16'h7777);
        send_vector(V_SINGLE, 16'h7777);
        ticks(100);
        check_value(queue_level == 2 && stream_level == 2 && live == 4,
                    "four_unique_bounded_residents", live, 4);
        cfg_valid = 1;
        drive_vector = V_SINGLE;
        cfg_count = 1;
        cfg_e = 0;
        cfg_tag = 16'h7777;
        raw_before = int'(stream_stat_cfg);
        ticks(8);
        check_value(!cfg_ready && stream_stat_cfg == raw_before,
                    "full_cfg_backpressure", int'(stream_stat_cfg), raw_before);
        cfg_valid = 0;
        wait_final();
        qmeta_before = int'(queue_stat_meta);
        retired_before = int'(queue_stat_retired);
        out_ready = 1;
        step();
        check_value(queue_stat_meta == qmeta_before &&
                    queue_stat_retired == retired_before + 1 && queue_level == 1,
                    "old_full_final_data_no_same_edge_credit", int'(queue_stat_meta), qmeta_before);
        drain();
        send_vector(V_SINGLE, 16'h7777);
        drain();
        check_value(stream_stat_cfg == 5 && queue_stat_retired == 5,
                    "fifth_admission_after_credit", int'(queue_stat_retired), 5);
        end_case();

        begin_case("final_data_metadata_same_edge_credit");
        out_meta_ready = 0;
        out_ready = 0;
        send_vector(V_SINGLE, 16'h6100);
        wait_queue(1, 0);
        wait_final();
        admit(V_ERR, 16'h6101);
        qmeta_before = int'(queue_stat_meta);
        retired_before = int'(queue_stat_retired);
        out_ready = 1;
        step();
        check_value(queue_stat_meta == qmeta_before + 1 &&
                    queue_stat_retired == retired_before + 1 && queue_level == 1,
                    "old_one_simultaneous_final_data_metadata", int'(queue_level), 1);
        drain();
        end_case();

        begin_case("error_metadata_same_edge_credit");
        out_meta_ready = 0;
        out_ready = 0;
        send_vector(V_ERR, 16'h6200);
        wait_queue(1, 0);
        admit(V_ERR, 16'h6201);
        qmeta_before = int'(queue_stat_meta);
        retired_before = int'(queue_stat_retired);
        out_meta_ready = 1;
        step();
        check_value(queue_stat_meta == qmeta_before + 1 &&
                    queue_stat_retired == retired_before + 1 && queue_level == 1,
                    "old_one_simultaneous_error_metadata", int'(queue_level), 1);
        drain();
        end_case();

        begin_case("full_error_metadata_retirement_bubble");
        out_meta_ready = 0;
        out_ready = 0;
        send_vector(V_ERR, 16'h6300);
        send_vector(V_ERR, 16'h6301);
        wait_queue(2, 0);
        send_vector(V_ERR, 16'h6302);
        ticks(2);
        qmeta_before = int'(queue_stat_meta);
        out_meta_ready = 1;
        step();
        check_value(queue_stat_meta == qmeta_before && queue_level == 1,
                    "old_full_error_no_same_edge_credit", int'(queue_stat_meta), qmeta_before);
        step();
        check_value(queue_stat_meta == qmeta_before + 1 && queue_level == 1,
                    "next_edge_descriptor_credit", int'(queue_stat_meta), qmeta_before + 1);
        drain();
        end_case();

        for (p = 0; p < 7; p = p + 1) begin
            interruption_case(p, 0);
            interruption_case(p, 1);
        end

        begin_case("reset_over_cancel_priority");
        out_meta_ready = 0;
        out_ready = 0;
        send_vector(V_SINGLE, 16'hff00);
        wait_queue(1, 0);
        admit(V_LONG, 16'hff01);
        send_sample(16'h5678, 0);
        clear_once(1, 1);
        check_value(ledger_tail == terminals && live == 0,
                    "every_admission_exactly_one_outcome", terminals, ledger_tail);
        end_case();
        $display("BBS_SUITE_TALLY cases=%0d checks=%0d admissions=%0d terminals=%0d metadata=%0d payload_bytes=%0d invariant_cycles=%0d",
                 suite_cases, suite_checks, ledger_tail, terminals,
                 meta_count_seen, payload_bytes_seen, observed_cycles);
        $display("BBS_DIAG failures=%0d watchdog=%0d live=%0d",
                 suite_failures, watchdog_fired, live);
        $display("BBS_FINAL result=PASS");
        $finish;
    end
endmodule
