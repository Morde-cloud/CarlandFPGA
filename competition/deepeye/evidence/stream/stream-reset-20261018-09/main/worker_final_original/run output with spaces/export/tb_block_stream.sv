// Public-port and directed checker for deepeye_block_stream.
//
// Work: B-STREAM-RESET-INTEGRATION-20261018-09-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
//
// Success bytes and metadata come from the pinned golden reference through
// the runner-generated stimulus.vec.  Directed errors, stalls, occupancy,
// reset/cancel and counter saturation are checked here at the external ports,
// except for the explicitly separated whitebox counter boundary tests.

`timescale 1ns / 1ps

module tb_block_stream;

    localparam integer MAX_VEC = 64;
    localparam integer MAX_SAMPLES = 128;
    localparam integer MAX_BYTES = 256;
    localparam integer MAX_EXP = 64;
    localparam integer MAX_VEC_SAMPLES = MAX_VEC * MAX_SAMPLES;
    localparam integer MAX_EXP_BYTES = MAX_EXP * MAX_BYTES;
    localparam integer WATCHDOG_NS = 500000000;
    localparam integer DRAIN_LIMIT = 2000000;

    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic        rst = 1'b1;
    logic        cancel = 1'b0;
    logic        cfg_valid = 1'b0;
    logic        cfg_ready;
    logic [7:0]  cfg_count = 8'd0;
    logic [3:0]  cfg_e = 4'd0;
    logic [15:0] cfg_tag = 16'd0;
    logic        s_valid = 1'b0;
    logic        s_ready;
    logic [15:0] s_data = 16'd0;
    logic        s_last = 1'b0;
    logic        meta_valid;
    logic        meta_ready = 1'b0;
    logic [15:0] meta_tag;
    logic [1:0]  meta_error;
    logic [7:0]  meta_count;
    logic [3:0]  meta_e;
    logic        meta_raw;
    logic [3:0]  meta_k;
    logic [11:0] meta_valid_bits;
    logic [8:0]  meta_bytes;
    logic        m_valid;
    logic        m_ready = 1'b0;
    logic [7:0]  m_data;
    logic        m_last;
    logic [1:0]  level;
    logic        filling;
    logic [31:0] stat_cfg;
    logic [31:0] stat_samples;
    logic [31:0] stat_ok;
    logic [31:0] stat_error;
    logic [31:0] stat_aborted;

    deepeye_block_stream dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .cfg_valid(cfg_valid),
        .cfg_ready(cfg_ready),
        .cfg_count(cfg_count),
        .cfg_e(cfg_e),
        .cfg_tag(cfg_tag),
        .s_valid(s_valid),
        .s_ready(s_ready),
        .s_data(s_data),
        .s_last(s_last),
        .meta_valid(meta_valid),
        .meta_ready(meta_ready),
        .meta_tag(meta_tag),
        .meta_error(meta_error),
        .meta_count(meta_count),
        .meta_e(meta_e),
        .meta_raw(meta_raw),
        .meta_k(meta_k),
        .meta_valid_bits(meta_valid_bits),
        .meta_bytes(meta_bytes),
        .m_valid(m_valid),
        .m_ready(m_ready),
        .m_data(m_data),
        .m_last(m_last),
        .level(level),
        .filling(filling),
        .stat_cfg(stat_cfg),
        .stat_samples(stat_samples),
        .stat_ok(stat_ok),
        .stat_error(stat_error),
        .stat_aborted(stat_aborted)
    );

    integer cyc = 0;
    always @(posedge clk) cyc = cyc + 1;

    integer tb_errors = 0;
    integer tb_checks = 0;
    integer case_errors = 0;
    integer total_cases = 0;
    integer pass_cases = 0;
    integer fail_cases = 0;
    integer whitebox_checks = 0;
    integer obs_meta = 0;
    integer obs_data = 0;
    integer obs_ok = 0;
    integer obs_error = 0;
    integer event_cfg_hs = 0;
    integer event_sample_hs = 0;
    integer event_fd = 0;
    string case_name = "init";

    integer vec_count = 0;
    integer vec_n [0:MAX_VEC-1];
    integer vec_e [0:MAX_VEC-1];
    integer vec_raw [0:MAX_VEC-1];
    integer vec_k [0:MAX_VEC-1];
    integer vec_bits [0:MAX_VEC-1];
    integer vec_bytes [0:MAX_VEC-1];
    integer vec_tag [0:MAX_VEC-1];
    integer vec_sample [0:MAX_VEC_SAMPLES-1];
    integer vec_payload [0:MAX_EXP_BYTES-1];

    integer exp_head = 0;
    integer exp_tail = 0;
    integer exp_tag [0:MAX_EXP-1];
    integer exp_error [0:MAX_EXP-1];
    integer exp_count [0:MAX_EXP-1];
    integer exp_e [0:MAX_EXP-1];
    integer exp_raw [0:MAX_EXP-1];
    integer exp_k [0:MAX_EXP-1];
    integer exp_bits [0:MAX_EXP-1];
    integer exp_bytes [0:MAX_EXP-1];
    integer exp_payload [0:MAX_EXP_BYTES-1];
    logic   exp_meta_active = 1'b0;
    integer exp_byte_index = 0;

    logic [31:0] model_cfg = 32'd0;
    logic [31:0] model_samples = 32'd0;
    logic [31:0] model_ok = 32'd0;
    logic [31:0] model_error = 32'd0;
    logic [31:0] model_aborted = 32'd0;
    integer      model_level = 0;
    logic        whitebox_mode = 1'b0;
    logic        producer_done = 1'b0;

    integer cover_all_e = 0;
    integer cover_raw = 0;
    integer cover_rice = 0;
    integer cover_n1 = 0;
    integer cover_n128 = 0;
    integer cover_concurrent_fill = 0;
    integer cover_fill_during_emit = 0;
    integer cover_queuefull_cycles = 0;
    integer cover_meta_stall_cycles = 0;
    integer cover_byte_stall_cycles = 0;
    integer cover_backtoback_blocks = 0;
    integer cover_cfg_notready = 0;
    integer cover_sample_notready = 0;
    integer cover_invalid_cfg = 0;
    integer cover_early_last = 0;
    integer cover_missing_last = 0;
    integer cover_partial_reset = 0;
    integer cover_partial_cancel = 0;
    integer cover_corefeed_cancel = 0;
    integer cover_meta_reset = 0;
    integer cover_meta_cancel = 0;
    integer cover_firstbyte_cancel = 0;
    integer cover_midbyte_cancel = 0;
    integer cover_finalbyte_cancel = 0;
    integer cover_heldcancel = 0;
    integer cover_alloc_retire = 0;
    integer cover_reset_recovery = 0;
    integer cover_cancel_recovery = 0;
    integer cover_pointer_wrap = 0;
    integer cover_saturation = 0;
    integer cover_random_schedule_cycles = 0;
    integer cover_random_ready_stalls = 0;
    integer cover_random_valid_gaps = 0;
    logic random_producer_done = 1'b0;

    function automatic logic [31:0] lfsr_next(input logic [31:0] value);
        lfsr_next = {value[30:0], value[31] ^ value[21] ^ value[1] ^ value[0]};
    endfunction

    function automatic integer next_exp(input integer index);
        next_exp = (index == (MAX_EXP - 1)) ? 0 : index + 1;
    endfunction

    function automatic logic queue_empty();
        queue_empty = (exp_head == exp_tail);
    endfunction

    function automatic logic [31:0] sat_inc_tb(input logic [31:0] value);
        sat_inc_tb = (value == 32'hFFFF_FFFF) ? value : value + 32'd1;
    endfunction

    function automatic logic [31:0] sat_add_tb(input logic [31:0] value,
                                               input integer amount);
        logic [63:0] wide;
        wide = {32'd0, value} + amount;
        sat_add_tb = (wide > 64'h0000_0000_FFFF_FFFF) ? 32'hFFFF_FFFF : wide[31:0];
    endfunction

    task automatic tb_check(input string name, input logic condition);
        tb_checks = tb_checks + 1;
        if (condition !== 1'b1) begin
            tb_errors = tb_errors + 1;
            case_errors = case_errors + 1;
            $display("TB_CHECK_FAIL case=%s check=%s cycle=%0d", case_name, name, cyc);
        end
    endtask

    task automatic silent_check(input string name, input logic condition);
        tb_checks = tb_checks + 1;
        if (condition !== 1'b1) begin
            tb_errors = tb_errors + 1;
            case_errors = case_errors + 1;
            $display("TB_CHECK_FAIL case=%s check=%s cycle=%0d", case_name, name, cyc);
        end
    endtask

    task automatic case_begin(input string name);
        case_name = name;
        case_errors = 0;
        $display("TB_CASE_BEGIN %s", name);
    endtask

    task automatic case_end();
        total_cases = total_cases + 1;
        if (case_errors == 0) begin
            pass_cases = pass_cases + 1;
            $display("TB_CASE %s pass=1", case_name);
        end else begin
            fail_cases = fail_cases + 1;
            $display("TB_CASE %s pass=0", case_name);
        end
    endtask

    task automatic clear_expectations();
        exp_head = 0;
        exp_tail = 0;
        exp_meta_active = 1'b0;
        exp_byte_index = 0;
    endtask

    task automatic push_error(input integer tag_value, input integer error_code);
        integer p;
        exp_tag[exp_tail] = tag_value;
        exp_error[exp_tail] = error_code;
        exp_count[exp_tail] = 0;
        exp_e[exp_tail] = 0;
        exp_raw[exp_tail] = 1;
        exp_k[exp_tail] = 0;
        exp_bits[exp_tail] = 0;
        exp_bytes[exp_tail] = 0;
        for (p = 0; p < MAX_BYTES; p = p + 1)
            exp_payload[exp_tail * MAX_BYTES + p] = 0;
        exp_tail = next_exp(exp_tail);
        if (exp_tail == exp_head)
            tb_check("expectation_queue_not_full", 1'b0);
    endtask

    task automatic push_success(input integer vec_index, input integer tag_value);
        integer p;
        exp_tag[exp_tail] = tag_value;
        exp_error[exp_tail] = 0;
        exp_count[exp_tail] = vec_n[vec_index];
        exp_e[exp_tail] = vec_e[vec_index];
        exp_raw[exp_tail] = vec_raw[vec_index];
        exp_k[exp_tail] = vec_k[vec_index];
        exp_bits[exp_tail] = vec_bits[vec_index];
        exp_bytes[exp_tail] = vec_bytes[vec_index];
        for (p = 0; p < vec_bytes[vec_index]; p = p + 1)
            exp_payload[exp_tail * MAX_BYTES + p] =
                vec_payload[vec_index * MAX_BYTES + p];
        exp_tail = next_exp(exp_tail);
        if (exp_tail == exp_head)
            tb_check("expectation_queue_not_full", 1'b0);
    endtask

    task automatic pop_expectation();
        exp_head = next_exp(exp_head);
        exp_meta_active = 1'b0;
        exp_byte_index = 0;
    endtask

    task automatic load_vectors();
        integer fd;
        integer vi;
        integer i;
        integer index_value;
        integer sc;
        fd = $fopen("stimulus.vec", "r");
        if (fd == 0) $fatal(1, "TB_FAIL cannot open stimulus.vec");
        sc = $fscanf(fd, "%d", vec_count);
        if (sc != 1 || vec_count < 1 || vec_count > MAX_VEC)
            $fatal(1, "TB_FAIL bad vector count");
        for (vi = 0; vi < vec_count; vi = vi + 1) begin
            sc = $fscanf(fd, "%d %d %d %d %d %d %d %d",
                         index_value, vec_n[vi], vec_e[vi], vec_raw[vi],
                         vec_k[vi], vec_bits[vi], vec_bytes[vi], vec_tag[vi]);
            if (sc != 8 || index_value != vi)
                $fatal(1, "TB_FAIL bad vector header %0d", vi);
            for (i = 0; i < vec_n[vi]; i = i + 1) begin
                sc = $fscanf(fd, "%d", vec_sample[vi * MAX_SAMPLES + i]);
                if (sc != 1) $fatal(1, "TB_FAIL bad vector sample");
            end
            for (i = 0; i < vec_bytes[vi]; i = i + 1) begin
                sc = $fscanf(fd, "%d", vec_payload[vi * MAX_BYTES + i]);
                if (sc != 1) $fatal(1, "TB_FAIL bad vector byte");
            end
        end
        $fclose(fd);
        $display("TB_STIMULUS vectors=%0d", vec_count);
    endtask

    task automatic clear_drive_inputs();
        cfg_valid = 1'b0;
        cfg_count = 8'd0;
        cfg_e = 4'd0;
        cfg_tag = 16'd0;
        s_valid = 1'b0;
        s_data = 16'd0;
        s_last = 1'b0;
    endtask

    task automatic clear_output_ready();
        meta_ready = 1'b0;
        m_ready = 1'b0;
    endtask

    task automatic accept_config(input integer count_value,
                                 input integer e_value,
                                 input integer tag_value);
        @(negedge clk);
        cfg_valid = 1'b1;
        cfg_count = count_value[7:0];
        cfg_e = e_value[3:0];
        cfg_tag = tag_value[15:0];
        while (cfg_ready !== 1'b1) begin
            cover_cfg_notready = cover_cfg_notready + 1;
            @(negedge clk);
        end
        @(posedge clk);
        #1;
        @(negedge clk);
        cfg_valid = 1'b0;
        cfg_count = 8'd0;
        cfg_e = 4'd0;
        cfg_tag = 16'd0;
    endtask

    task automatic send_sample_value(input integer value_value,
                                     input logic last_value,
                                     input integer gap_value);
        if (gap_value > 0) repeat (gap_value) @(negedge clk);
        @(negedge clk);
        s_valid = 1'b1;
        s_data = value_value[15:0];
        s_last = last_value;
        while (s_ready !== 1'b1) begin
            cover_sample_notready = cover_sample_notready + 1;
            @(negedge clk);
        end
        @(posedge clk);
        #1;
        @(negedge clk);
        s_valid = 1'b0;
        s_data = 16'd0;
        s_last = 1'b0;
    endtask

    task automatic send_vector_samples(input integer vec_index,
                                       input integer gap_value);
        integer i;
        for (i = 0; i < vec_n[vec_index]; i = i + 1)
            send_sample_value(vec_sample[vec_index * MAX_SAMPLES + i],
                              (i == (vec_n[vec_index] - 1)), gap_value);
    endtask

    task automatic drive_success(input integer vec_index,
                                 input integer tag_value,
                                 input integer gap_value);
        push_success(vec_index, tag_value);
        accept_config(vec_n[vec_index], vec_e[vec_index], tag_value);
        send_vector_samples(vec_index, gap_value);
    endtask

    task automatic drive_error1(input integer tag_value,
                                input integer count_value,
                                input integer e_value);
        push_error(tag_value, 1);
        accept_config(count_value, e_value, tag_value);
        tb_check("error1_no_samples", s_ready === 1'b0);
        cover_invalid_cfg = cover_invalid_cfg + 1;
    endtask

    task automatic drive_early_last(input integer vec_index,
                                    input integer tag_value,
                                    input integer error_index);
        integer i;
        push_error(tag_value, 2);
        accept_config(vec_n[vec_index], vec_e[vec_index], tag_value);
        for (i = 0; i <= error_index; i = i + 1)
            send_sample_value(vec_sample[vec_index * MAX_SAMPLES + i],
                              (i == error_index), 0);
        tb_check("early_last_filling_clear", filling === 1'b0);
        tb_check("early_last_ready_clear", s_ready === 1'b0);
        cover_early_last = cover_early_last + 1;
    endtask

    task automatic drive_missing_last(input integer vec_index,
                                      input integer tag_value);
        integer i;
        push_error(tag_value, 2);
        accept_config(vec_n[vec_index], vec_e[vec_index], tag_value);
        for (i = 0; i < vec_n[vec_index]; i = i + 1)
            send_sample_value(vec_sample[vec_index * MAX_SAMPLES + i],
                              1'b0, 0);
        tb_check("missing_last_filling_clear", filling === 1'b0);
        tb_check("missing_last_ready_clear", s_ready === 1'b0);
        cover_missing_last = cover_missing_last + 1;
    endtask

    task automatic drive_partial(input integer vec_index,
                                 input integer tag_value,
                                 input integer accepted_samples);
        integer i;
        accept_config(vec_n[vec_index], vec_e[vec_index], tag_value);
        for (i = 0; i < accepted_samples; i = i + 1)
            send_sample_value(vec_sample[vec_index * MAX_SAMPLES + i],
                              1'b0, 0);
    endtask

    task automatic drive_ready(input integer pattern_value,
                               input integer step_value);
        case (pattern_value)
            0: begin
                meta_ready = 1'b1;
                m_ready = 1'b1;
            end
            1: begin
                meta_ready = ((step_value % 11) != 0);
                m_ready = ((step_value % 5) != 0);
            end
            2: begin
                meta_ready = ((step_value % 2) == 0) || (step_value > 40);
                m_ready = ((step_value % 7) != 0) || (step_value > 90);
            end
            default: begin
                meta_ready = ((step_value % 3) != 0) || (step_value > 30);
                m_ready = ((step_value % 4) != 0) || (step_value > 80);
            end
        endcase
    endtask

    task automatic drain_outputs(input integer pattern_value);
        integer guard;
        logic done;
        guard = 0;
        done = 1'b0;
        while ((!done) && (guard < DRAIN_LIMIT)) begin
            if (queue_empty() && (!exp_meta_active)) begin
                done = 1'b1;
            end else begin
                drive_ready(pattern_value, guard);
                @(negedge clk);
                guard = guard + 1;
            end
        end
        clear_output_ready();
        tb_check("drain_finished", done);
    endtask

    task automatic drain_until_producer_done(input integer pattern_value);
        integer guard;
        logic done;
        guard = 0;
        done = 1'b0;
        while ((!done) && (guard < DRAIN_LIMIT)) begin
            if (producer_done && queue_empty() && (!exp_meta_active)) begin
                done = 1'b1;
            end else begin
                drive_ready(pattern_value, guard);
                @(negedge clk);
                guard = guard + 1;
            end
        end
        clear_output_ready();
        tb_check("producer_drain_finished", done);
    endtask

    task automatic expect_idle(input string prefix);
        tb_check({prefix, "_level_zero"}, level === 2'd0);
        tb_check({prefix, "_filling_zero"}, filling === 1'b0);
        tb_check({prefix, "_meta_low"}, meta_valid === 1'b0);
        tb_check({prefix, "_data_low"}, m_valid === 1'b0);
        tb_check({prefix, "_expect_queue_empty"}, queue_empty());
    endtask

    always @(posedge clk) begin
        if (!(rst || cancel)) begin
            if ((cfg_valid === 1'b1) && (cfg_ready === 1'b1)) begin
                if (event_fd != 0)
                    $fdisplay(event_fd, "EV cycle=%0d cfg tag=%0d count=%0d e=%0d",
                              cyc, cfg_tag, cfg_count, cfg_e);
                silent_check("cfg_transfer_known",
                    !$isunknown({cfg_count, cfg_e, cfg_tag}));
                event_cfg_hs = event_cfg_hs + 1;
            end
            if ((s_valid === 1'b1) && (s_ready === 1'b1)) begin
                if (event_fd != 0)
                    $fdisplay(event_fd, "EV cycle=%0d sample data=%0d last=%0d",
                              cyc, s_data, s_last);
                silent_check("sample_transfer_known", !$isunknown({s_data, s_last}));
                event_sample_hs = event_sample_hs + 1;
            end
            if ((meta_valid === 1'b1) && (meta_ready === 1'b1)) begin
                if (event_fd != 0)
                    $fdisplay(event_fd, "EV cycle=%0d meta tag=%0d error=%0d count=%0d e=%0d raw=%0d k=%0d bits=%0d bytes=%0d",
                              cyc, meta_tag, meta_error, meta_count, meta_e,
                              meta_raw, meta_k, meta_valid_bits, meta_bytes);
                if (queue_empty()) begin
                    silent_check("unexpected_meta", 1'b0);
                end else if (exp_meta_active) begin
                    silent_check("meta_interleave", 1'b0);
                end else begin
                    obs_meta = obs_meta + 1;
                    silent_check("meta_tag", meta_tag === exp_tag[exp_head][15:0]);
                    silent_check("meta_error", meta_error === exp_error[exp_head][1:0]);
                    if (exp_error[exp_head] == 0) begin
                        silent_check("meta_count", meta_count === exp_count[exp_head][7:0]);
                        silent_check("meta_e", meta_e === exp_e[exp_head][3:0]);
                        silent_check("meta_raw", meta_raw === exp_raw[exp_head][0]);
                        silent_check("meta_k", meta_k === exp_k[exp_head][3:0]);
                        silent_check("meta_bits", meta_valid_bits === exp_bits[exp_head][11:0]);
                        silent_check("meta_bytes", meta_bytes === exp_bytes[exp_head][8:0]);
                        silent_check("meta_bytes_range",
                                     (meta_bytes >= 9'd1) && (meta_bytes <= 9'd256));
                        exp_meta_active = 1'b1;
                        exp_byte_index = 0;
                        $display("TB_OBS_META case=%s tag=%0d error=0 count=%0d e=%0d raw=%0d k=%0d bits=%0d bytes=%0d",
                                 case_name, meta_tag, meta_count, meta_e, meta_raw,
                                 meta_k, meta_valid_bits, meta_bytes);
                    end else begin
                        silent_check("error001_count_zero", meta_count === 8'd0);
                        silent_check("error001_e_zero", meta_e === 4'd0);
                        silent_check("error001_raw_one", meta_raw === 1'b1);
                        silent_check("error001_k_zero", meta_k === 4'd0);
                        silent_check("error001_bits_zero", meta_valid_bits === 12'd0);
                        silent_check("error001_bytes_zero", meta_bytes === 9'd0);
                        obs_error = obs_error + 1;
                        $display("TB_OBS_ERROR case=%s tag=%0d error=%0d",
                                 case_name, meta_tag, meta_error);
                        pop_expectation();
                    end
                end
            end
            if ((m_valid === 1'b1) && (m_ready === 1'b1)) begin
                if (event_fd != 0)
                    $fdisplay(event_fd, "EV cycle=%0d byte=%0d last=%0d",
                              cyc, m_data, m_last);
                obs_data = obs_data + 1;
                if (!exp_meta_active) begin
                    silent_check("unexpected_byte", 1'b0);
                end else begin
                    silent_check("byte_data",
                        m_data === exp_payload[exp_head * MAX_BYTES + exp_byte_index][7:0]);
                    if (exp_byte_index == (exp_bytes[exp_head] - 1)) begin
                        silent_check("final_byte_last", m_last === 1'b1);
                        silent_check("payload_length",
                                     exp_byte_index < exp_bytes[exp_head]);
                        obs_ok = obs_ok + 1;
                        $display("TB_OBS_PAYLOAD case=%s tag=%0d bytes=%0d",
                                 case_name, exp_tag[exp_head], exp_bytes[exp_head]);
                        pop_expectation();
                    end else begin
                        silent_check("nonfinal_byte_last", m_last === 1'b0);
                        exp_byte_index = exp_byte_index + 1;
                    end
                end
            end
        end
    end

    logic prev_meta_stall = 1'b0;
    logic [15:0] prev_meta_tag = 16'd0;
    logic [1:0]  prev_meta_error = 2'd0;
    logic [7:0]  prev_meta_count = 8'd0;
    logic [3:0]  prev_meta_e = 4'd0;
    logic        prev_meta_raw = 1'b0;
    logic [3:0]  prev_meta_k = 4'd0;
    logic [11:0] prev_meta_bits = 12'd0;
    logic [8:0]  prev_meta_bytes = 9'd0;
    logic prev_data_stall = 1'b0;
    logic [7:0] prev_data = 8'd0;
    logic prev_last = 1'b0;

    always @(posedge clk) begin
        if (!(rst || cancel)) begin
            if (meta_valid === 1'b1) begin
                silent_check("meta_fields_known",
                    !$isunknown({meta_tag, meta_error, meta_count, meta_e,
                                 meta_raw, meta_k, meta_valid_bits, meta_bytes}));
            end
            if (m_valid === 1'b1) begin
                silent_check("data_fields_known", !$isunknown({m_data, m_last}));
            end
            if (prev_meta_stall) begin
                silent_check("meta_stalled_valid", meta_valid === 1'b1);
                silent_check("meta_stalled_tag", meta_tag === prev_meta_tag);
                silent_check("meta_stalled_error", meta_error === prev_meta_error);
                silent_check("meta_stalled_count", meta_count === prev_meta_count);
                silent_check("meta_stalled_e", meta_e === prev_meta_e);
                silent_check("meta_stalled_raw", meta_raw === prev_meta_raw);
                silent_check("meta_stalled_k", meta_k === prev_meta_k);
                silent_check("meta_stalled_bits", meta_valid_bits === prev_meta_bits);
                silent_check("meta_stalled_bytes", meta_bytes === prev_meta_bytes);
            end
            if (prev_data_stall) begin
                silent_check("data_stalled_valid", m_valid === 1'b1);
                silent_check("data_stalled_data", m_data === prev_data);
                silent_check("data_stalled_last", m_last === prev_last);
            end
            prev_meta_stall <= (meta_valid === 1'b1) && (meta_ready !== 1'b1);
            prev_meta_tag <= meta_tag;
            prev_meta_error <= meta_error;
            prev_meta_count <= meta_count;
            prev_meta_e <= meta_e;
            prev_meta_raw <= meta_raw;
            prev_meta_k <= meta_k;
            prev_meta_bits <= meta_valid_bits;
            prev_meta_bytes <= meta_bytes;
            prev_data_stall <= (m_valid === 1'b1) && (m_ready !== 1'b1);
            prev_data <= m_data;
            prev_last <= m_last;
        end else begin
            prev_meta_stall <= 1'b0;
            prev_data_stall <= 1'b0;
        end
    end

    always @(posedge clk) begin
        logic alloc_value;
        logic sample_value;
        logic meta_terminal_value;
        logic data_terminal_value;
        integer delta_value;
        if (rst) begin
            model_cfg = 32'd0;
            model_samples = 32'd0;
            model_ok = 32'd0;
            model_error = 32'd0;
            model_aborted = 32'd0;
            model_level = 0;
        end else if (cancel) begin
            model_aborted = sat_add_tb(model_aborted, model_level);
            model_level = 0;
        end else begin
            alloc_value = (cfg_valid === 1'b1) && (cfg_ready === 1'b1);
            sample_value = (s_valid === 1'b1) && (s_ready === 1'b1);
            meta_terminal_value = (meta_valid === 1'b1) && (meta_ready === 1'b1) &&
                                  ((meta_error != 2'd0) === 1'b1);
            data_terminal_value = (m_valid === 1'b1) && (m_ready === 1'b1) &&
                                  (m_last === 1'b1);
            if (alloc_value) model_cfg = sat_inc_tb(model_cfg);
            if (sample_value) model_samples = sat_inc_tb(model_samples);
            if (meta_terminal_value) model_error = sat_inc_tb(model_error);
            if (data_terminal_value) model_ok = sat_inc_tb(model_ok);
            delta_value = (alloc_value ? 1 : 0) - (meta_terminal_value ? 1 : 0)
                          - (data_terminal_value ? 1 : 0);
            model_level = model_level + delta_value;
        end
    end

    always @(posedge clk) begin
        logic [63:0] conservation_sum;
        #1;
        if (!whitebox_mode) begin
            silent_check("stat_cfg_model", stat_cfg === model_cfg);
            silent_check("stat_samples_model", stat_samples === model_samples);
            silent_check("stat_ok_model", stat_ok === model_ok);
            silent_check("stat_error_model", stat_error === model_error);
            silent_check("stat_aborted_model", stat_aborted === model_aborted);
            silent_check("level_model", level === model_level[1:0]);
            silent_check("level_range", level <= 2'd2);
            silent_check("filling_implies_level", (!filling) || (level != 2'd0));
            silent_check("cfg_ready_rule",
                cfg_ready === (!rst && !cancel && !filling && (level < 2'd2)));
            silent_check("s_ready_rule",
                s_ready === (!rst && !cancel && filling));
            if (rst || cancel) begin
                silent_check("flush_meta_gate", meta_valid === 1'b0);
                silent_check("flush_data_gate", m_valid === 1'b0);
            end
            conservation_sum = {32'd0, stat_ok} + {32'd0, stat_error} +
                               {32'd0, stat_aborted} + {62'd0, level};
            if ((stat_cfg != 32'hFFFF_FFFF) && (stat_ok != 32'hFFFF_FFFF) &&
                (stat_error != 32'hFFFF_FFFF) &&
                (stat_aborted != 32'hFFFF_FFFF)) begin
                silent_check("counter_conservation",
                             {32'd0, stat_cfg} === conservation_sum);
            end
        end
    end

    function automatic integer find_vector(input integer n_value,
                                              input integer e_value,
                                              input integer want_raw);
        integer i;
        integer found;
        found = -1;
        for (i = 0; i < vec_count; i = i + 1) begin
            if ((found < 0) && (vec_n[i] == n_value) && (vec_e[i] == e_value) &&
                ((want_raw < 0) || (vec_raw[i] == want_raw)))
                found = i;
        end
        find_vector = found;
    endfunction

    task automatic apply_reset(input integer cycles_value);
        @(negedge clk);
        rst = 1'b1;
        cancel = 1'b0;
        clear_drive_inputs();
        clear_output_ready();
        clear_expectations();
        repeat (cycles_value) @(negedge clk);
        @(negedge clk);
        rst = 1'b0;
    endtask

    task automatic apply_cancel(input integer cycles_value);
        @(negedge clk);
        rst = 1'b0;
        cancel = 1'b1;
        clear_drive_inputs();
        clear_output_ready();
        clear_expectations();
        repeat (cycles_value) @(negedge clk);
        @(negedge clk);
        cancel = 1'b0;
    endtask

    task automatic wait_meta_valid(input integer label_value);
        integer guard;
        guard = 0;
        meta_ready = 1'b0;
        m_ready = 1'b0;
        while ((meta_valid !== 1'b1) && (guard < DRAIN_LIMIT)) begin
            @(negedge clk);
            guard = guard + 1;
        end
        tb_check("wait_meta_valid", meta_valid === 1'b1);
    endtask

    task automatic wait_data_valid();
        integer guard;
        guard = 0;
        while ((m_valid !== 1'b1) && (guard < DRAIN_LIMIT)) begin
            @(negedge clk);
            guard = guard + 1;
        end
        tb_check("wait_data_valid", m_valid === 1'b1);
    endtask

    task automatic consume_metadata();
        @(negedge clk);
        meta_ready = 1'b1;
        @(posedge clk);
        #1;
        @(negedge clk);
        meta_ready = 1'b0;
        m_ready = 1'b0;
    endtask

    task automatic test_vector_sweep();
        integer vi;
        string name_value;
        for (vi = 0; vi < vec_count; vi = vi + 1) begin
            name_value = $sformatf("VECTOR_%0d", vi);
            case_begin(name_value);
            drive_success(vi, 16'h4000 + vi, (vi % 4));
            tb_check("vector_reserved_level", level === 2'd1);
            drain_outputs(vi % 4);
            expect_idle("vector");
            if (vec_n[vi] == 1) cover_n1 = cover_n1 + 1;
            if (vec_n[vi] == 128) cover_n128 = cover_n128 + 1;
            if (vec_raw[vi] != 0) cover_raw = cover_raw + 1;
            else cover_rice = cover_rice + 1;
            case_end();
        end
    endtask

    task automatic test_two_block_concurrency();
        integer a_vec;
        integer b_vec;
        a_vec = find_vector(128, 0, -1);
        b_vec = find_vector(128, 8, -1);
        tb_check("find_two_block_vectors", (a_vec >= 0) && (b_vec >= 0));
        apply_reset(2);
        case_begin("TWO_BLOCK_FILL_AND_ENCODE");
        drive_success(a_vec, 16'h5101, 0);
        drive_success(b_vec, 16'h5102, 1);
        tb_check("concurrent_level_two", level === 2'd2);
        tb_check("concurrent_not_filling", filling === 1'b0);
        cover_concurrent_fill = cover_concurrent_fill + 1;
        drain_outputs(2);
        expect_idle("two_block");
        case_end();

        apply_reset(2);
        case_begin("FILL_WHILE_FIRST_BYTE_STALLED");
        a_vec = find_vector(4, 0, -1);
        b_vec = find_vector(128, 2, -1);
        tb_check("find_emit_fill_vectors", (a_vec >= 0) && (b_vec >= 0));
        drive_success(a_vec, 16'h5201, 0);
        wait_meta_valid(0);
        consume_metadata();
        wait_data_valid();
        tb_check("first_byte_stalled", m_last === 1'b0);
        drive_success(b_vec, 16'h5202, 2);
        tb_check("fill_while_emit_level_two", level === 2'd2);
        tb_check("first_byte_still_valid", m_valid === 1'b1);
        cover_fill_during_emit = cover_fill_during_emit + 1;
        drain_outputs(1);
        expect_idle("fill_emit");
        case_end();
    endtask

    task automatic test_queue_full_and_backpressure();
        integer a_vec;
        integer b_vec;
        integer c_vec;
        integer hold_cycles;
        integer cfg_before;
        a_vec = find_vector(128, 4, -1);
        b_vec = find_vector(128, 1, -1);
        c_vec = find_vector(3, 0, -1);
        tb_check("find_queuefull_vectors",
                 (a_vec >= 0) && (b_vec >= 0) && (c_vec >= 0));
        apply_reset(2);
        case_begin("QUEUE_FULL_BACKPRESSURE");
        drive_success(a_vec, 16'h5301, 0);
        drive_success(b_vec, 16'h5302, 0);
        tb_check("queuefull_level_two", level === 2'd2);
        push_success(c_vec, 16'h5303);
        @(negedge clk);
        cfg_valid = 1'b1;
        cfg_count = vec_n[c_vec][7:0];
        cfg_e = vec_e[c_vec][3:0];
        cfg_tag = 16'h5303;
        cfg_before = stat_cfg;
        hold_cycles = 0;
        while (hold_cycles < 4096) begin
            if (cfg_ready !== 1'b0)
                silent_check("cfg_ready_must_stall", 1'b0);
            cover_cfg_notready = cover_cfg_notready + 1;
            @(negedge clk);
            hold_cycles = hold_cycles + 1;
        end
        cover_queuefull_cycles = cover_queuefull_cycles + hold_cycles;
        silent_check("cfg_not_counted_while_full", stat_cfg === cfg_before);
        producer_done = 1'b0;
        fork
            begin
                integer guard_value;
                guard_value = 0;
                while ((cfg_ready !== 1'b1) && (guard_value < DRAIN_LIMIT)) begin
                    @(negedge clk);
                    guard_value = guard_value + 1;
                end
                tb_check("held_cfg_eventually_ready", cfg_ready === 1'b1);
                @(posedge clk);
                #1;
                @(negedge clk);
                cfg_valid = 1'b0;
                cfg_count = 8'd0;
                cfg_e = 4'd0;
                cfg_tag = 16'd0;
                send_vector_samples(c_vec, 1);
                producer_done = 1'b1;
            end
            drain_until_producer_done(1);
        join
        expect_idle("queuefull");
        case_end();
    endtask

    task automatic test_back_to_back();
        integer small_idx [0:4];
        integer k;
        integer vi;
        small_idx[0] = find_vector(3, 0, -1);
        small_idx[1] = find_vector(3, 1, -1);
        small_idx[2] = find_vector(3, 2, -1);
        small_idx[3] = find_vector(3, 4, -1);
        small_idx[4] = find_vector(3, 8, -1);
        tb_check("find_backtoback_vectors",
                 (small_idx[0] >= 0) && (small_idx[1] >= 0) &&
                 (small_idx[2] >= 0) && (small_idx[3] >= 0) &&
                 (small_idx[4] >= 0));
        apply_reset(2);
        case_begin("BACK_TO_BACK_POINTER_WRAP");
        producer_done = 1'b0;
        fork
            begin
                for (k = 0; k < 12; k = k + 1) begin
                    vi = small_idx[k % 5];
                    drive_success(vi, 16'h6000 + (k % 3), (k % 6));
                end
                producer_done = 1'b1;
            end
            drain_until_producer_done(3);
        join
        cover_backtoback_blocks = cover_backtoback_blocks + 12;
        cover_pointer_wrap = cover_pointer_wrap + 1;
        expect_idle("backtoback");
        case_end();
    endtask

    task automatic test_error_ordering();
        integer v3e0;
        integer v1e0;
        integer v3e1;
        integer v3e2;
        integer v1e8;
        integer v4e4;
        v3e0 = find_vector(3, 0, -1);
        v1e0 = find_vector(1, 0, -1);
        v3e1 = find_vector(3, 1, -1);
        v3e2 = find_vector(3, 2, -1);
        v1e8 = find_vector(1, 8, -1);
        v4e4 = find_vector(4, 4, -1);
        tb_check("find_error_order_vectors",
                 (v3e0 >= 0) && (v1e0 >= 0) && (v3e1 >= 0) && (v3e2 >= 0) &&
                 (v1e8 >= 0) && (v4e4 >= 0));
        apply_reset(2);
        case_begin("ERROR_SUCCESS_ORDER");
        producer_done = 1'b0;
        fork
            begin
                drive_error1(16'h7001, 0, 0);
                drive_success(v3e0, 16'h7001, 0);
                drive_early_last(v3e0, 16'h7002, 0);
                drive_error1(16'h7003, 3, 3);
                drive_missing_last(v3e1, 16'h7004);
                drive_error1(16'h7005, 129, 0);
                drive_early_last(v3e2, 16'h7006, 1);
                drive_success(v1e8, 16'h7007, 2);
                drive_error1(16'h7008, 8, 15);
                drive_success(v4e4, 16'h7009, 1);
                drive_success(v1e0, 16'h7001, 0);
                producer_done = 1'b1;
            end
            drain_until_producer_done(2);
        join
        expect_idle("error_order");
        case_end();
    endtask

    task automatic test_no_consumption_without_ready();
        integer vi;
        vi = find_vector(2, 0, -1);
        tb_check("find_no_ready_vector", vi >= 0);
        apply_reset(2);
        case_begin("NO_HANDSHAKE_WITHOUT_READY");
        push_success(vi, 16'h7101);
        @(negedge clk);
        s_valid = 1'b1;
        s_data = vec_sample[vi * MAX_SAMPLES];
        s_last = 1'b0;
        repeat (40) @(negedge clk);
        silent_check("sample_not_counted_without_fill", stat_samples === 32'd0);
        cover_sample_notready = cover_sample_notready + 40;
        cfg_valid = 1'b1;
        cfg_count = vec_n[vi][7:0];
        cfg_e = vec_e[vi][3:0];
        cfg_tag = 16'h7101;
        @(posedge clk);
        #1;
        silent_check("cfg_only_on_empty_edge", stat_cfg === 32'd1);
        silent_check("sample_not_same_empty_edge", stat_samples === 32'd0);
        silent_check("cfg_opened_fill", filling === 1'b1 && level === 2'd1);
        @(negedge clk);
        cfg_valid = 1'b0;
        cfg_count = 8'd0;
        cfg_e = 4'd0;
        cfg_tag = 16'd0;
        @(posedge clk);
        #1;
        silent_check("held_sample_accepts_next_edge", stat_samples === 32'd1);
        @(negedge clk);
        s_valid = 1'b0;
        s_data = 16'd0;
        s_last = 1'b0;
        send_sample_value(vec_sample[vi * MAX_SAMPLES + 1], 1'b1, 0);
        drain_outputs(0);
        expect_idle("no_ready");
        case_end();
    endtask

    task automatic test_simultaneous_allocate_retire();
        integer va;
        integer vb;
        va = find_vector(1, 0, -1);
        vb = find_vector(2, 8, -1);
        tb_check("find_alloc_retire_vectors", (va >= 0) && (vb >= 0));
        apply_reset(2);
        case_begin("SIMULTANEOUS_ALLOCATE_RETIRE");
        push_success(va, 16'h7201);
        accept_config(vec_n[va], vec_e[va], 16'h7201);
        send_vector_samples(va, 0);
        wait_meta_valid(0);
        consume_metadata();
        m_ready = 1'b1;
        while (!((m_valid === 1'b1) && (m_last === 1'b1))) @(negedge clk);
        m_ready = 1'b0;
        @(negedge clk);
        tb_check("final_byte_waiting", (m_valid === 1'b1) && (m_last === 1'b1));
        push_success(vb, 16'h7202);
        cfg_valid = 1'b1;
        cfg_count = vec_n[vb][7:0];
        cfg_e = vec_e[vb][3:0];
        cfg_tag = 16'h7202;
        m_ready = 1'b1;
        tb_check("alloc_retire_cfg_ready", cfg_ready === 1'b1);
        @(posedge clk);
        #1;
        tb_check("alloc_retire_level_stays_one", level === 2'd1);
        tb_check("alloc_retire_new_filling", filling === 1'b1);
        tb_check("alloc_retire_old_ok", stat_ok === 32'd1);
        tb_check("alloc_retire_cfg_counted", stat_cfg === 32'd2);
        @(negedge clk);
        cfg_valid = 1'b0;
        cfg_count = 8'd0;
        cfg_e = 4'd0;
        cfg_tag = 16'd0;
        send_vector_samples(vb, 1);
        cover_alloc_retire = cover_alloc_retire + 1;
        drain_outputs(1);
        expect_idle("alloc_retire");
        case_end();
    endtask

    task automatic test_metadata_and_byte_stalls();
        integer vi;
        integer target_mid;
        integer target_last;
        vi = find_vector(16, 0, -1);
        tb_check("find_stall_vector", vi >= 0);
        apply_reset(2);
        case_begin("META_FIRST_MIDDLE_FINAL_BYTE_STALLS");
        push_success(vi, 16'h7301);
        accept_config(vec_n[vi], vec_e[vi], 16'h7301);
        send_vector_samples(vi, 0);
        wait_meta_valid(0);
        repeat (1000) @(negedge clk);
        tb_check("meta_still_valid_after_1000", meta_valid === 1'b1);
        cover_meta_stall_cycles = cover_meta_stall_cycles + 1000;
        consume_metadata();
        wait_data_valid();
        repeat (700) @(negedge clk);
        tb_check("first_byte_still_valid", m_valid === 1'b1);
        cover_byte_stall_cycles = cover_byte_stall_cycles + 700;
        target_mid = exp_bytes[exp_head] / 2;
        m_ready = 1'b1;
        while (exp_byte_index < target_mid) @(negedge clk);
        m_ready = 1'b0;
        repeat (500) @(negedge clk);
        tb_check("middle_byte_still_valid", m_valid === 1'b1);
        cover_byte_stall_cycles = cover_byte_stall_cycles + 500;
        target_last = exp_bytes[exp_head] - 1;
        m_ready = 1'b1;
        while (exp_byte_index < target_last) @(negedge clk);
        m_ready = 1'b0;
        repeat (300) @(negedge clk);
        tb_check("final_byte_stall_valid", (m_valid === 1'b1) && (m_last === 1'b1));
        cover_byte_stall_cycles = cover_byte_stall_cycles + 300;
        drain_outputs(0);
        expect_idle("stalls");
        case_end();
    endtask

    task automatic test_partial_input_flush();
        integer large_vec;
        integer fresh_vec;
        integer sample_before;
        large_vec = find_vector(128, 0, -1);
        fresh_vec = find_vector(3, 0, -1);
        tb_check("find_partial_flush_vectors", (large_vec >= 0) && (fresh_vec >= 0));

        apply_reset(2);
        case_begin("RESET_PARTIAL_INPUT_RECOVERY");
        drive_partial(large_vec, 16'h8101, 20);
        tb_check("partial_reset_level", level === 2'd1);
        tb_check("partial_reset_filling", filling === 1'b1);
        tb_check("partial_reset_samples", stat_samples === 32'd20);
        apply_reset(2);
        tb_check("reset_clears_cfg", stat_cfg === 32'd0);
        tb_check("reset_clears_samples", stat_samples === 32'd0);
        tb_check("reset_clears_ok", stat_ok === 32'd0);
        tb_check("reset_clears_error", stat_error === 32'd0);
        tb_check("reset_clears_aborted", stat_aborted === 32'd0);
        expect_idle("reset_partial");
        cover_partial_reset = cover_partial_reset + 1;
        drive_success(fresh_vec, 16'h8102, 0);
        drain_outputs(0);
        expect_idle("reset_recovery");
        cover_reset_recovery = cover_reset_recovery + 1;
        case_end();

        apply_reset(2);
        case_begin("CANCEL_PARTIAL_INPUT_RECOVERY");
        drive_partial(large_vec, 16'h8201, 12);
        sample_before = stat_samples;
        tb_check("partial_cancel_sample_count", sample_before == 12);
        apply_cancel(1);
        tb_check("cancel_preserves_cfg", stat_cfg === 32'd1);
        tb_check("cancel_preserves_samples", stat_samples === sample_before);
        tb_check("cancel_increments_aborted", stat_aborted === 32'd1);
        tb_check("cancel_no_ok", stat_ok === 32'd0);
        tb_check("cancel_no_error", stat_error === 32'd0);
        expect_idle("cancel_partial");
        cover_partial_cancel = cover_partial_cancel + 1;
        drive_success(fresh_vec, 16'h8202, 1);
        drain_outputs(1);
        expect_idle("cancel_recovery");
        cover_cancel_recovery = cover_cancel_recovery + 1;
        case_end();
    endtask

    task automatic test_held_cancel_and_corefeed();
        integer large_vec;
        integer fresh_vec;
        large_vec = find_vector(128, 0, -1);
        fresh_vec = find_vector(4, 4, -1);
        tb_check("find_held_vectors", (large_vec >= 0) && (fresh_vec >= 0));

        apply_reset(2);
        case_begin("HELD_CANCEL_COUNTS_ONCE");
        drive_error1(16'h8301, 0, 0);
        drive_partial(large_vec, 16'h8302, 10);
        tb_check("held_cancel_pre_level_two", level === 2'd2);
        apply_cancel(4);
        tb_check("held_cancel_aborted_two", stat_aborted === 32'd2);
        tb_check("held_cancel_cfg_two", stat_cfg === 32'd2);
        tb_check("held_cancel_samples_ten", stat_samples === 32'd10);
        tb_check("held_cancel_ok_zero", stat_ok === 32'd0);
        tb_check("held_cancel_error_zero", stat_error === 32'd0);
        expect_idle("held_cancel");
        cover_heldcancel = cover_heldcancel + 1;
        drive_success(fresh_vec, 16'h8303, 0);
        drain_outputs(0);
        expect_idle("held_cancel_recovery");
        case_end();

        apply_reset(2);
        case_begin("CANCEL_DURING_CORE_FEED");
        drive_success(large_vec, 16'h8401, 0);
        repeat (30) @(negedge clk);
        tb_check("corefeed_no_meta_yet", meta_valid === 1'b0);
        tb_check("corefeed_no_data_yet", m_valid === 1'b0);
        apply_cancel(1);
        tb_check("corefeed_aborted_one", stat_aborted === 32'd1);
        tb_check("corefeed_cfg_preserved", stat_cfg === 32'd1);
        tb_check("corefeed_samples_preserved", stat_samples === 32'd128);
        tb_check("corefeed_ok_zero", stat_ok === 32'd0);
        expect_idle("corefeed_cancel");
        cover_corefeed_cancel = cover_corefeed_cancel + 1;
        case_end();
    endtask

    task automatic test_metadata_flush();
        integer vi;
        vi = find_vector(4, 0, -1);
        tb_check("find_meta_flush_vector", vi >= 0);

        apply_reset(2);
        case_begin("RESET_DURING_METADATA_STALL");
        drive_success(vi, 16'h8501, 0);
        wait_meta_valid(0);
        repeat (50) @(negedge clk);
        tb_check("meta_reset_still_valid", meta_valid === 1'b1);
        apply_reset(2);
        tb_check("meta_reset_clears_all", (stat_cfg == 0) && (stat_ok == 0) &&
                                          (stat_error == 0) && (stat_aborted == 0));
        expect_idle("meta_reset");
        cover_meta_reset = cover_meta_reset + 1;
        case_end();

        apply_reset(2);
        case_begin("CANCEL_DURING_METADATA_STALL");
        drive_success(vi, 16'h8502, 0);
        wait_meta_valid(0);
        repeat (50) @(negedge clk);
        tb_check("meta_cancel_still_valid", meta_valid === 1'b1);
        apply_cancel(1);
        tb_check("meta_cancel_aborted_one", stat_aborted === 32'd1);
        tb_check("meta_cancel_ok_zero", stat_ok === 32'd0);
        tb_check("meta_cancel_error_zero", stat_error === 32'd0);
        tb_check("meta_cancel_cfg_preserved", stat_cfg === 32'd1);
        expect_idle("meta_cancel");
        cover_meta_cancel = cover_meta_cancel + 1;
        case_end();
    endtask

    task automatic test_output_flush_phases();
        integer vi;
        integer target_mid;
        integer target_last;
        vi = find_vector(16, 0, -1);
        tb_check("find_output_flush_vector", vi >= 0);

        apply_reset(2);
        case_begin("CANCEL_FIRST_BYTE_STALL");
        drive_success(vi, 16'h8601, 0);
        wait_meta_valid(0);
        consume_metadata();
        wait_data_valid();
        repeat (25) @(negedge clk);
        tb_check("first_cancel_byte_valid", m_valid === 1'b1);
        apply_cancel(1);
        tb_check("first_cancel_aborted_one", stat_aborted === 32'd1);
        tb_check("first_cancel_no_ok", stat_ok === 32'd0);
        expect_idle("first_cancel");
        cover_firstbyte_cancel = cover_firstbyte_cancel + 1;
        case_end();

        apply_reset(2);
        case_begin("CANCEL_MIDDLE_BYTE_STALL");
        drive_success(vi, 16'h8602, 0);
        wait_meta_valid(0);
        consume_metadata();
        target_mid = exp_bytes[exp_head] / 2;
        m_ready = 1'b1;
        while (exp_byte_index < target_mid) @(negedge clk);
        m_ready = 1'b0;
        repeat (25) @(negedge clk);
        tb_check("middle_cancel_byte_valid", m_valid === 1'b1);
        apply_cancel(1);
        tb_check("middle_cancel_aborted_one", stat_aborted === 32'd1);
        tb_check("middle_cancel_no_ok", stat_ok === 32'd0);
        expect_idle("middle_cancel");
        cover_midbyte_cancel = cover_midbyte_cancel + 1;
        case_end();

        apply_reset(2);
        case_begin("CANCEL_FINAL_BYTE_COMPETITION");
        drive_success(vi, 16'h8603, 0);
        wait_meta_valid(0);
        consume_metadata();
        target_last = exp_bytes[exp_head] - 1;
        m_ready = 1'b1;
        while (exp_byte_index < target_last) @(negedge clk);
        tb_check("final_competition_waiting", (m_valid === 1'b1) && (m_last === 1'b1));
        cancel = 1'b1;
        m_ready = 1'b1;
        clear_expectations();
        @(posedge clk);
        #1;
        tb_check("final_competition_no_ok", stat_ok === 32'd0);
        tb_check("final_competition_aborted_one", stat_aborted === 32'd1);
        tb_check("final_competition_level_zero", level === 2'd0);
        tb_check("final_competition_data_gated", m_valid === 1'b0);
        @(negedge clk);
        cancel = 1'b0;
        cover_finalbyte_cancel = cover_finalbyte_cancel + 1;
        drive_success(vi, 16'h8604, 0);
        drain_outputs(0);
        expect_idle("final_cancel_recovery");
        case_end();
    endtask

    task automatic test_counter_saturation_whitebox();
        integer va;
        integer vb;
        va = find_vector(1, 0, -1);
        vb = find_vector(2, 8, -1);
        tb_check("find_saturation_vectors", (va >= 0) && (vb >= 0));
        apply_reset(2);
        whitebox_mode = 1'b1;
        case_begin("WHITEBOX_COUNTER_SATURATION");
        $display("TB_WHITEBOX_BEGIN counter_boundaries");

        dut.stat_cfg_q = 32'hFFFF_FFFE;
        drive_error1(16'h9001, 0, 0);
        drain_outputs(0);
        tb_check("sat_cfg_reaches_max", stat_cfg === 32'hFFFF_FFFF);
        whitebox_checks = whitebox_checks + 1;
        drive_error1(16'h9002, 129, 0);
        drain_outputs(0);
        tb_check("sat_cfg_stays_max", stat_cfg === 32'hFFFF_FFFF);
        whitebox_checks = whitebox_checks + 1;

        apply_reset(2);
        dut.stat_error_q = 32'hFFFF_FFFE;
        drive_error1(16'h9003, 0, 0);
        drain_outputs(0);
        tb_check("sat_error_reaches_max", stat_error === 32'hFFFF_FFFF);
        whitebox_checks = whitebox_checks + 1;
        drive_error1(16'h9004, 0, 0);
        drain_outputs(0);
        tb_check("sat_error_stays_max", stat_error === 32'hFFFF_FFFF);
        whitebox_checks = whitebox_checks + 1;

        apply_reset(2);
        dut.stat_ok_q = 32'hFFFF_FFFE;
        drive_success(va, 16'h9005, 0);
        drain_outputs(0);
        tb_check("sat_ok_reaches_max", stat_ok === 32'hFFFF_FFFF);
        tb_check("sat_ok_data_flow", obs_ok > 0);
        whitebox_checks = whitebox_checks + 2;

        apply_reset(2);
        dut.stat_samples_q = 32'hFFFF_FFFE;
        drive_success(vb, 16'h9006, 0);
        drain_outputs(0);
        tb_check("sat_samples_reaches_max", stat_samples === 32'hFFFF_FFFF);
        whitebox_checks = whitebox_checks + 1;

        apply_reset(2);
        dut.stat_aborted_q = 32'hFFFF_FFFE;
        drive_partial(vb, 16'h9007, 1);
        apply_cancel(1);
        tb_check("sat_aborted_reaches_max", stat_aborted === 32'hFFFF_FFFF);
        whitebox_checks = whitebox_checks + 1;
        drive_partial(vb, 16'h9008, 1);
        apply_cancel(1);
        tb_check("sat_aborted_stays_max", stat_aborted === 32'hFFFF_FFFF);
        whitebox_checks = whitebox_checks + 1;

        $display("TB_WHITEBOX_END counter_boundaries");
        apply_reset(2);
        whitebox_mode = 1'b0;
        cover_saturation = cover_saturation + 5;
        expect_idle("saturation");
        case_end();
    endtask

    task automatic randomized_producer();
        integer block_index;
        integer sample_index;
        integer gap_value;
        integer vi;
        integer is_error;
        logic [31:0] state;
        integer v128_raw;
        integer v128_rice;
        integer v128_e8;
        integer v1_e8;
        integer v16_e2;
        integer v4_e0;
        integer v2_e8;
        integer v64_rice;
        integer v1_e1;

        v128_raw  = find_vector(128, 0, 1);
        v128_rice = find_vector(128, 4, 0);
        v128_e8   = find_vector(128, 8, -1);
        v1_e8     = find_vector(1, 8, -1);
        v16_e2    = find_vector(16, 2, -1);
        v4_e0     = find_vector(4, 0, -1);
        v2_e8     = find_vector(2, 8, -1);
        v64_rice  = find_vector(64, 1, 0);
        v1_e1     = find_vector(1, 1, -1);
        tb_check("random_find_vectors",
                 (v128_raw >= 0) && (v128_rice >= 0) && (v128_e8 >= 0) &&
                 (v1_e8 >= 0) && (v16_e2 >= 0) && (v4_e0 >= 0) &&
                 (v2_e8 >= 0) && (v64_rice >= 0) && (v1_e1 >= 0));

        state = 32'h6D2B_79F5;
        for (block_index = 0; block_index < 10; block_index = block_index + 1) begin
            state = lfsr_next(state);
            gap_value = 1 + (state % 5);
            cover_random_valid_gaps = cover_random_valid_gaps + gap_value;
            repeat (gap_value) @(negedge clk);

            is_error = 1'b0;
            case (block_index)
                0: vi = v128_raw;
                1: vi = v1_e8;
                2: vi = v16_e2;
                3: begin
                    vi = v4_e0;
                    is_error = 1'b1;
                end
                4: vi = v128_rice;
                5: vi = v4_e0;
                6: vi = v2_e8;
                7: vi = v64_rice;
                8: vi = v1_e1;
                default: vi = v128_e8;
            endcase

            if (is_error) begin
                push_error(16'h6001, 1);
                @(negedge clk);
                cfg_valid = 1'b1;
                cfg_count = 8'd0;
                cfg_e = 4'd0;
                cfg_tag = 16'h6001;
            end else begin
                push_success(vi, 16'h6000 + (block_index % 4));
                @(negedge clk);
                cfg_valid = 1'b1;
                cfg_count = vec_n[vi][7:0];
                cfg_e = vec_e[vi][3:0];
                cfg_tag = 16'h6000 + (block_index % 4);
            end
            while (cfg_ready !== 1'b1) begin
                cover_cfg_notready = cover_cfg_notready + 1;
                @(negedge clk);
            end
            @(posedge clk);
            #1;
            @(negedge clk);
            cfg_valid = 1'b0;
            cfg_count = 8'd0;
            cfg_e = 4'd0;
            cfg_tag = 16'd0;

            if (!is_error) begin
                for (sample_index = 0; sample_index < vec_n[vi];
                     sample_index = sample_index + 1) begin
                    state = lfsr_next(state);
                    gap_value = state % 4;
                    cover_random_valid_gaps = cover_random_valid_gaps + gap_value;
                    repeat (gap_value) @(negedge clk);
                    @(negedge clk);
                    s_valid = 1'b1;
                    s_data = vec_sample[vi * MAX_SAMPLES + sample_index];
                    s_last = (sample_index == (vec_n[vi] - 1));
                    while (s_ready !== 1'b1) begin
                        cover_sample_notready = cover_sample_notready + 1;
                        @(negedge clk);
                    end
                    @(posedge clk);
                    #1;
                    @(negedge clk);
                    s_valid = 1'b0;
                    s_data = 16'd0;
                    s_last = 1'b0;
                end
            end
        end
        clear_drive_inputs();
        random_producer_done = 1'b1;
    endtask

    task automatic randomized_consumer();
        integer guard;
        logic [31:0] state;

        guard = 0;
        state = 32'h1357_9BDF;
        meta_ready = 1'b0;
        m_ready = 1'b0;
        while (!(random_producer_done && queue_empty() && (!exp_meta_active)) &&
               (guard < DRAIN_LIMIT)) begin
            @(negedge clk);
            state = lfsr_next(state);
            meta_ready = state[3] ^ state[9] ^ state[17];
            state = lfsr_next(state);
            m_ready = state[2] ^ state[13] ^ state[19] ^ state[25];
            if ((meta_valid === 1'b1) && (meta_ready !== 1'b1))
                cover_random_ready_stalls = cover_random_ready_stalls + 1;
            if ((m_valid === 1'b1) && (m_ready !== 1'b1))
                cover_random_ready_stalls = cover_random_ready_stalls + 1;
            cover_random_schedule_cycles = cover_random_schedule_cycles + 1;
            guard = guard + 1;
        end
        clear_output_ready();
        tb_check("random_consumer_finished", guard < DRAIN_LIMIT);
    endtask

    task automatic test_randomized_schedule();
        apply_reset(2);
        case_begin("RANDOMIZED_VALID_READY");
        random_producer_done = 1'b0;
        fork
            randomized_producer();
            randomized_consumer();
        join
        tb_check("random_schedule_sustained", cover_random_schedule_cycles >= 1024);
        tb_check("random_ready_stalls", cover_random_ready_stalls >= 16);
        tb_check("random_valid_gaps", cover_random_valid_gaps >= 100);
        expect_idle("random_schedule");
        apply_reset(2);
        expect_idle("random_schedule_clean");
        case_end();
    endtask

    task automatic check_vector_coverage();
        integer all_e_count;
        all_e_count = 0;
        if (find_vector(1, 0, -1) >= 0) all_e_count = all_e_count + 1;
        if (find_vector(1, 1, -1) >= 0) all_e_count = all_e_count + 1;
        if (find_vector(1, 2, -1) >= 0) all_e_count = all_e_count + 1;
        if (find_vector(1, 4, -1) >= 0) all_e_count = all_e_count + 1;
        if (find_vector(1, 8, -1) >= 0) all_e_count = all_e_count + 1;
        cover_all_e = all_e_count;
        tb_check("stimulus_all_e", all_e_count == 5);
        tb_check("stimulus_n1", find_vector(1, 0, -1) >= 0);
        tb_check("stimulus_n128", find_vector(128, 0, -1) >= 0);
        tb_check("stimulus_n16", find_vector(16, 0, -1) >= 0);
    endtask

    initial begin : watchdog
        #(WATCHDOG_NS);
        $display("TB_WATCHDOG_TIMEOUT");
        $fatal(1, "TB_WATCHDOG_TIMEOUT");
    end

    initial begin : main
        integer e_index;
        rst = 1'b1;
        cancel = 1'b0;
        clear_drive_inputs();
        clear_output_ready();
        repeat (6) @(negedge clk);
        rst = 1'b0;
        repeat (2) @(negedge clk);
        load_vectors();
        check_vector_coverage();
        event_fd = $fopen("public_events.log", "w");
        if (event_fd == 0) $fatal(1, "TB_FAIL cannot open public_events.log");

        test_vector_sweep();
        test_two_block_concurrency();
        test_queue_full_and_backpressure();
        test_back_to_back();
        test_error_ordering();
        test_no_consumption_without_ready();
        test_simultaneous_allocate_retire();
        test_metadata_and_byte_stalls();
        test_partial_input_flush();
        test_held_cancel_and_corefeed();
        test_metadata_flush();
        test_output_flush_phases();
        test_counter_saturation_whitebox();
        test_randomized_schedule();

        clear_drive_inputs();
        clear_output_ready();
        expect_idle("final");
        tb_check("final_stats_zero", (stat_cfg == 0) && (stat_samples == 0) &&
                                     (stat_ok == 0) && (stat_error == 0) &&
                                     (stat_aborted == 0));
        tb_check("coverage_raw", cover_raw > 0);
        tb_check("coverage_rice", cover_rice > 0);
        tb_check("coverage_all_e", cover_all_e == 5);
        tb_check("coverage_n1", cover_n1 > 0);
        tb_check("coverage_n128", cover_n128 > 0);
        tb_check("coverage_queuefull", cover_queuefull_cycles >= 4096);
        tb_check("coverage_meta_stall", cover_meta_stall_cycles >= 1000);
        tb_check("coverage_byte_stall", cover_byte_stall_cycles >= 1500);
        tb_check("coverage_backtoback", cover_backtoback_blocks >= 12);
        $fclose(event_fd);
        event_fd = 0;

        $display("TB_COVER all_e=%0d", cover_all_e);
        $display("TB_COVER raw=%0d", cover_raw);
        $display("TB_COVER rice=%0d", cover_rice);
        $display("TB_COVER n1=%0d", cover_n1);
        $display("TB_COVER n128=%0d", cover_n128);
        $display("TB_COVER concurrent_fill=%0d", cover_concurrent_fill);
        $display("TB_COVER fill_during_emit=%0d", cover_fill_during_emit);
        $display("TB_COVER queuefull_cycles=%0d", cover_queuefull_cycles);
        $display("TB_COVER meta_stall_cycles=%0d", cover_meta_stall_cycles);
        $display("TB_COVER byte_stall_cycles=%0d", cover_byte_stall_cycles);
        $display("TB_COVER backtoback_blocks=%0d", cover_backtoback_blocks);
        $display("TB_COVER cfg_notready=%0d", cover_cfg_notready);
        $display("TB_COVER sample_notready=%0d", cover_sample_notready);
        $display("TB_COVER invalid_cfg=%0d", cover_invalid_cfg);
        $display("TB_COVER early_last=%0d", cover_early_last);
        $display("TB_COVER missing_last=%0d", cover_missing_last);
        $display("TB_COVER partial_reset=%0d", cover_partial_reset);
        $display("TB_COVER partial_cancel=%0d", cover_partial_cancel);
        $display("TB_COVER corefeed_cancel=%0d", cover_corefeed_cancel);
        $display("TB_COVER meta_reset=%0d", cover_meta_reset);
        $display("TB_COVER meta_cancel=%0d", cover_meta_cancel);
        $display("TB_COVER firstbyte_cancel=%0d", cover_firstbyte_cancel);
        $display("TB_COVER midbyte_cancel=%0d", cover_midbyte_cancel);
        $display("TB_COVER finalbyte_cancel=%0d", cover_finalbyte_cancel);
        $display("TB_COVER heldcancel=%0d", cover_heldcancel);
        $display("TB_COVER alloc_retire=%0d", cover_alloc_retire);
        $display("TB_COVER reset_recovery=%0d", cover_reset_recovery);
        $display("TB_COVER cancel_recovery=%0d", cover_cancel_recovery);
        $display("TB_COVER pointer_wrap=%0d", cover_pointer_wrap);
        $display("TB_COVER saturation=%0d", cover_saturation);
        $display("TB_COVER random_schedule_cycles=%0d", cover_random_schedule_cycles);
        $display("TB_COVER random_ready_stalls=%0d", cover_random_ready_stalls);
        $display("TB_COVER random_valid_gaps=%0d", cover_random_valid_gaps);
        $display("TB_SUMMARY cases=%0d pass=%0d fail=%0d checks=%0d cfg_hs=%0d sample_hs=%0d meta_hs=%0d data_hs=%0d ok=%0d error=%0d whitebox=%0d",
                 total_cases, pass_cases, fail_cases, tb_checks,
                 event_cfg_hs, event_sample_hs, obs_meta, obs_data,
                 obs_ok, obs_error, whitebox_checks);
        if (tb_errors != 0) begin
            $display("TB_END fail");
            $fatal(1, "TB_FAILURES %0d", tb_errors);
        end
        $display("TB_END pass");
        $display("TB_DONE");
        $finish(0);
    end

endmodule
