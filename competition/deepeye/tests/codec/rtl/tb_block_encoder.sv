// Directed + fixed-seed vector testbench for deepeye_block_encoder.
//
// Work: B-BLOCK-ENCODER-RTL-20261018-08-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
//
// External-port oracle only.  The vector file is generated from the pinned
// golden reference by tools/codec/run_block_encoder.py.  Every legal case is
// compared field-by-field and byte-by-byte; every protocol error, reset and
// cancel case is directed here.  A watchdog and bounded wait loops make a
// hang or a missing marker fatal.  Stimulus changes on the clock negedge;
// handshakes are sampled at the following posedge.
//
// Machine-readable transcript lines (no leading '# '):
//   TB_CASE_BEGIN <name>
//   TB_CASE <name> pass=<0|1> cfg=<n> sample=<n> meta=<n> data=<n>
//   TB_META case=<name> error=<e> count=<n> e=<E> raw=<r> k=<k> bits=<b> bytes=<n> cycles=<n>
//   TB_PAYLOAD case=<name> n=<n> <byte0> ... <byte n-1>
//   TB_CHK case=<name> token=<t> ok=<0|1>
//   TB_SUMMARY cases=<n> pass=<n> fail=<n> cfg_hs=<n> sample_hs=<n> meta_hs=<n> data_hs=<n> error_meta=<n> resets=<n> cancels=<n>
//   TB_END pass|fail
//   TB_DONE

`timescale 1ns / 1ps

module tb_block_encoder;

    localparam integer MAX_SAMPLES = 128;
    localparam integer MAX_BYTES   = 256;
    localparam integer WATCHDOG_NS = 200000000;

    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic        rst        = 1'b1;
    logic        cancel     = 1'b0;
    logic        cfg_valid  = 1'b0;
    logic        cfg_ready;
    logic [7:0]  cfg_count  = 8'd0;
    logic [3:0]  cfg_e      = 4'd0;
    logic        s_valid    = 1'b0;
    logic        s_ready;
    logic [15:0] s_data     = 16'd0;
    logic        s_last     = 1'b0;
    logic        meta_valid;
    logic        meta_ready = 1'b0;
    logic [1:0]  meta_error;
    logic [7:0]  meta_count;
    logic [3:0]  meta_e;
    logic        meta_raw;
    logic [3:0]  meta_k;
    logic [11:0] meta_valid_bits;
    logic [8:0]  meta_bytes;
    logic        m_valid;
    logic        m_ready    = 1'b0;
    logic [7:0]  m_data;
    logic        m_last;

    deepeye_block_encoder dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .cfg_valid(cfg_valid),
        .cfg_ready(cfg_ready),
        .cfg_count(cfg_count),
        .cfg_e(cfg_e),
        .s_valid(s_valid),
        .s_ready(s_ready),
        .s_data(s_data),
        .s_last(s_last),
        .meta_valid(meta_valid),
        .meta_ready(meta_ready),
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
        .m_last(m_last)
    );

    integer cyc = 0;
    always @(negedge clk) cyc = cyc + 1;

    integer tb_errors       = 0;
    integer case_errors     = 0;
    integer cfg_hs          = 0;
    integer sample_hs       = 0;
    integer meta_hs         = 0;
    integer data_hs         = 0;
    integer error_meta_cases= 0;
    integer reset_pulses    = 0;
    integer cancel_pulses   = 0;
    integer case_cfg        = 0;
    integer case_sample     = 0;
    integer case_meta       = 0;
    integer case_data       = 0;
    integer total_cases     = 0;
    integer pass_cases      = 0;
    integer fail_cases      = 0;
    integer last_sample_cycle = 0;
    integer last_to_meta    = 0;

    string  case_name = "init";

    integer v_ncases = 0;
    integer v_idx;
    integer v_e;
    integer v_n;
    integer v_raw;
    integer v_k;
    integer v_bits;
    integer v_bytes;
    integer v_stall;
    integer v_sample [0:MAX_SAMPLES-1];
    integer v_byte   [0:MAX_BYTES-1];

    integer d_sample [0:MAX_SAMPLES-1];
    integer d_byte   [0:MAX_BYTES-1];
    bit     d_last   [0:MAX_SAMPLES-1];
    integer cur_exp_byte [0:MAX_BYTES-1];
    integer obs_byte     [0:MAX_BYTES-1];
    integer port_fd;

    function automatic integer gap_for(input integer idx, input integer profile);
        begin
            case (profile)
                0: gap_for = 0;
                1: gap_for = 2;
                2: gap_for = (idx % 3);
                3: gap_for = ((idx * 7 + 1) % 5);
                default: gap_for = 0;
            endcase
        end
    endfunction

    function automatic integer meta_stall_for(input integer profile);
        begin
            case (profile)
                0: meta_stall_for = 0;
                1: meta_stall_for = 5;
                2: meta_stall_for = 17;
                3: meta_stall_for = 1;
                default: meta_stall_for = 0;
            endcase
        end
    endfunction

    function automatic integer data_stall_for(input integer idx, input integer nbytes,
                                              input integer profile);
        begin
            case (profile)
                0: data_stall_for = 0;
                1: data_stall_for = (idx == 0) ? 5 : 0;
                2: data_stall_for = (idx % 2);
                3: data_stall_for = ((idx == 0) || (idx == nbytes - 1)) ? 7 : 1;
                default: data_stall_for = 0;
            endcase
        end
    endfunction

    task automatic tb_check(input string token, input bit ok);
        begin
            $display("TB_CHK case=%s token=%s ok=%0d", case_name, token, ok ? 1 : 0);
            if (!ok) begin
                case_errors = case_errors + 1;
                tb_errors   = tb_errors + 1;
                $display("TB_CHECK_FAIL case=%s token=%s", case_name, token);
            end
        end
    endtask

    task automatic case_begin(input string name);
        begin
            case_name   = name;
            case_errors = 0;
            case_cfg    = 0;
            case_sample = 0;
            case_meta   = 0;
            case_data   = 0;
            total_cases = total_cases + 1;
            $display("TB_CASE_BEGIN %s", name);
        end
    endtask

    task automatic case_end();
        begin
            if (case_errors == 0) begin
                pass_cases = pass_cases + 1;
                $display("TB_CASE %s pass=1 cfg=%0d sample=%0d meta=%0d data=%0d",
                         case_name, case_cfg, case_sample, case_meta, case_data);
            end else begin
                fail_cases = fail_cases + 1;
                $display("TB_CASE %s pass=0 cfg=%0d sample=%0d meta=%0d data=%0d",
                         case_name, case_cfg, case_sample, case_meta, case_data);
            end
        end
    endtask

    task automatic send_config(input [3:0] e_in, input [7:0] n_in);
        integer guard;
        bit     done;
        begin
            @(negedge clk);
            cfg_e     = e_in;
            cfg_count = n_in;
            cfg_valid = 1'b1;
            done      = 1'b0;
            guard     = 0;
            while (!done) begin
                #1;
                if (cfg_ready) begin
                    @(posedge clk);
                    case_cfg = case_cfg + 1;
                    cfg_hs   = cfg_hs + 1;
                    $fwrite(port_fd, "cfg %0d e=%0d count=%0d\n", cyc, e_in, n_in);
                    @(negedge clk);
                    cfg_valid = 1'b0;
                    done = 1'b1;
                end else begin
                    @(negedge clk);
                    guard = guard + 1;
                    if (guard > 2000)
                        $fatal(1, "TB_FAIL cfg_ready timeout case=%s", case_name);
                end
            end
        end
    endtask

    task automatic send_sample(input [15:0] data_in, input bit last_in, input integer gap);
        integer guard;
        bit     done;
        begin
            repeat (gap) @(negedge clk);
            @(negedge clk);
            s_valid = 1'b1;
            s_data  = data_in;
            s_last  = last_in;
            done    = 1'b0;
            guard   = 0;
            while (!done) begin
                #1;
                if (s_ready) begin
                    @(posedge clk);
                    case_sample = case_sample + 1;
                    sample_hs   = sample_hs + 1;
                    $fwrite(port_fd, "sample %0d data=%0d last=%0d\n",
                            cyc, data_in, last_in);
                    if (last_in) last_sample_cycle = cyc;
                    @(negedge clk);
                    s_valid = 1'b0;
                    done = 1'b1;
                end else begin
                    @(negedge clk);
                    guard = guard + 1;
                    if (guard > 60000)
                        $fatal(1, "TB_FAIL s_ready timeout case=%s", case_name);
                end
            end
        end
    endtask

    task automatic do_reset(input integer ncycles);
        integer i;
        begin
            @(negedge clk);
            rst = 1'b1;
            for (i = 0; i < ncycles; i = i + 1) begin
                @(negedge clk);
                tb_check("outputs_low_during_reset",
                         (cfg_ready === 1'b0) && (s_ready === 1'b0) &&
                         (meta_valid === 1'b0) && (m_valid === 1'b0));
            end
            @(negedge clk);
            rst = 1'b0;
            reset_pulses = reset_pulses + 1;
            $fwrite(port_fd, "reset %0d cycles=%0d\n", cyc, ncycles);
        end
    endtask

    task automatic do_cancel(input integer ncycles);
        integer i;
        begin
            @(negedge clk);
            cancel = 1'b1;
            for (i = 0; i < ncycles; i = i + 1) begin
                @(negedge clk);
                tb_check("outputs_low_during_cancel",
                         (cfg_ready === 1'b0) && (s_ready === 1'b0) &&
                         (meta_valid === 1'b0) && (m_valid === 1'b0));
            end
            @(negedge clk);
            cancel = 1'b0;
            cancel_pulses = cancel_pulses + 1;
            $fwrite(port_fd, "cancel %0d cycles=%0d\n", cyc, ncycles);
        end
    endtask

    task automatic wait_meta(input [1:0] exp_err, input [7:0] exp_count,
                             input [3:0] exp_e, input bit exp_raw,
                             input [3:0] exp_k, input [11:0] exp_bits,
                             input [8:0] exp_bytes, input integer stall);
        integer    guard;
        logic [1:0]  cap_err;
        logic [7:0]  cap_count;
        logic [3:0]  cap_e;
        logic        cap_raw;
        logic [3:0]  cap_k;
        logic [11:0] cap_bits;
        logic [8:0]  cap_bytes;
        begin
            guard = 0;
            while (meta_valid !== 1'b1) begin
                @(negedge clk);
                guard = guard + 1;
                if (guard > 30000)
                    $fatal(1, "TB_FAIL meta_valid timeout case=%s", case_name);
            end
            cap_err   = meta_error;
            cap_count = meta_count;
            cap_e     = meta_e;
            cap_raw   = meta_raw;
            cap_k     = meta_k;
            cap_bits  = meta_valid_bits;
            cap_bytes = meta_bytes;
            last_to_meta = cyc - last_sample_cycle;
            tb_check("meta_known",
                     ((^{meta_error, meta_count, meta_e, meta_raw, meta_k,
                         meta_valid_bits, meta_bytes}) !== 1'bx));
            if (exp_err == 2'd0) begin
                tb_check("meta_within_20000", (last_to_meta <= 20000));
            end
            $display("TB_META case=%s error=%0d count=%0d e=%0d raw=%0d k=%0d bits=%0d bytes=%0d cycles=%0d",
                     case_name, cap_err, cap_count, cap_e, cap_raw, cap_k,
                     cap_bits, cap_bytes, last_to_meta);
            repeat (stall) begin
                @(negedge clk);
                tb_check("meta_valid_holds_under_stall", (meta_valid === 1'b1));
                tb_check("meta_stable_under_stall",
                         (meta_error === cap_err) && (meta_count === cap_count) &&
                         (meta_e === cap_e) && (meta_raw === cap_raw) &&
                         (meta_k === cap_k) && (meta_valid_bits === cap_bits) &&
                         (meta_bytes === cap_bytes));
            end
            @(negedge clk);
            meta_ready = 1'b1;
            #1;
            tb_check("meta_valid_at_ready", (meta_valid === 1'b1));
            @(posedge clk);
            case_meta = case_meta + 1;
            meta_hs   = meta_hs + 1;
            $fwrite(port_fd, "meta %0d error=%0d count=%0d e=%0d raw=%0d k=%0d bits=%0d bytes=%0d cycles=%0d\n",
                    cyc, cap_err, cap_count, cap_e, cap_raw, cap_k,
                    cap_bits, cap_bytes, last_to_meta);
            @(negedge clk);
            meta_ready = 1'b0;
            tb_check("meta_error_match", (cap_err === exp_err));
            tb_check("meta_count_match", (cap_count === exp_count));
            tb_check("meta_e_match",     (cap_e === exp_e));
            tb_check("meta_raw_match",   (cap_raw === exp_raw));
            tb_check("meta_k_match",     (cap_k === exp_k));
            tb_check("meta_bits_match",  (cap_bits === exp_bits));
            tb_check("meta_bytes_match", (cap_bytes === exp_bytes));
            if (exp_err != 2'd0) error_meta_cases = error_meta_cases + 1;
        end
    endtask

    task automatic collect_payload(input integer nbytes, input integer stall_mode);
        integer i;
        integer guard;
        integer st;
        logic [7:0] cap_data;
        bit         cap_last;
        begin
            for (i = 0; i < nbytes; i = i + 1) begin
                guard = 0;
                while (m_valid !== 1'b1) begin
                    @(negedge clk);
                    guard = guard + 1;
                    if (guard > 30000)
                        $fatal(1, "TB_FAIL m_valid timeout case=%s byte=%0d",
                               case_name, i);
                end
                cap_data = m_data;
                cap_last = m_last;
                obs_byte[i] = m_data;
                tb_check("payload_known", ((^{m_data, m_last}) !== 1'bx));
                tb_check("payload_last_flag", (m_last === (i == (nbytes - 1))));
                tb_check("payload_data_match", (m_data === cur_exp_byte[i][7:0]));
                st = data_stall_for(i, nbytes, stall_mode);
                repeat (st) begin
                    @(negedge clk);
                    tb_check("payload_valid_holds_under_stall", (m_valid === 1'b1));
                    tb_check("payload_stable_under_stall",
                             (m_data === cap_data) && (m_last === cap_last));
                end
                @(negedge clk);
                m_ready = 1'b1;
                #1;
                tb_check("payload_valid_at_ready", (m_valid === 1'b1));
                @(posedge clk);
                case_data = case_data + 1;
                data_hs   = data_hs + 1;
                $fwrite(port_fd, "data %0d byte=%0d last=%0d\n",
                        cyc, cap_data, cap_last);
                @(negedge clk);
                m_ready = 1'b0;
            end
            $write("TB_PAYLOAD case=%s n=%0d", case_name, nbytes);
            for (i = 0; i < nbytes; i = i + 1)
                $write(" %0d", obs_byte[i]);
            $write("\n");
            repeat (2) @(negedge clk);
            tb_check("no_extra_payload", (m_valid === 1'b0));
            guard = 0;
            while (cfg_ready !== 1'b1) begin
                @(negedge clk);
                guard = guard + 1;
                if (guard > 100)
                    $fatal(1, "TB_FAIL idle timeout case=%s", case_name);
            end
            tb_check("returned_idle",
                     (cfg_ready === 1'b1) && (meta_valid === 1'b0) &&
                     (m_valid === 1'b0) && (s_ready === 1'b0));
        end
    endtask

    task automatic check_no_payload();
        integer i;
        begin
            for (i = 0; i < 10; i = i + 1) begin
                @(negedge clk);
                tb_check("error_no_payload", (m_valid === 1'b0));
                tb_check("error_no_meta_restart", (meta_valid === 1'b0));
            end
            tb_check("error_returns_idle",
                     (cfg_ready === 1'b1) && (s_ready === 1'b0) &&
                     (meta_valid === 1'b0) && (m_valid === 1'b0));
        end
    endtask

    task automatic legal_body(input [3:0] e_in, input [7:0] n_in,
                              input bit raw_in, input [3:0] k_in,
                              input [11:0] bits_in, input [8:0] bytes_in,
                              input integer gap, input integer meta_stall,
                              input integer data_mode);
        integer i;
        begin
            send_config(e_in, n_in);
            for (i = 0; i < n_in; i = i + 1)
                send_sample(d_sample[i][15:0], (i == (n_in - 1)), gap);
            wait_meta(2'd0, n_in, e_in, raw_in, k_in, bits_in, bytes_in, meta_stall);
            for (i = 0; i < bytes_in; i = i + 1)
                cur_exp_byte[i] = d_byte[i];
            collect_payload(bytes_in, data_mode);
        end
    endtask

    task automatic set_v_a();
        begin
            d_sample[0] = 0;
            d_sample[1] = 1;
            d_sample[2] = 2;
            d_last[0]   = 1'b0;
            d_last[1]   = 1'b0;
            d_last[2]   = 1'b1;
            d_byte[0]   = 8'h00;
            d_byte[1]   = 8'h00;
            d_byte[2]   = 8'h24;
        end
    endtask

    task automatic set_v_b();
        begin
            d_sample[0] = 65535;
            d_sample[1] = 65534;
            d_sample[2] = 0;
            d_sample[3] = 65535;
            d_last[0]   = 1'b0;
            d_last[1]   = 1'b0;
            d_last[2]   = 1'b0;
            d_last[3]   = 1'b1;
            d_byte[0]   = 8'hFF;
            d_byte[1]   = 8'hFF;
            d_byte[2]   = 8'hFF;
            d_byte[3]   = 8'hFE;
            d_byte[4]   = 8'h00;
            d_byte[5]   = 8'h00;
            d_byte[6]   = 8'hFF;
            d_byte[7]   = 8'hFF;
        end
    endtask

    task automatic directed_errors();
        begin
            case_begin("D_startup_idle");
            repeat (3) @(negedge clk);
            tb_check("startup_cfg_ready", (cfg_ready === 1'b1));
            tb_check("startup_no_other_outputs",
                     (s_ready === 1'b0) && (meta_valid === 1'b0) &&
                     (m_valid === 1'b0));
            case_end();

            case_begin("D_invalid_count0");
            send_config(4'd0, 8'd0);
            last_sample_cycle = cyc;
            wait_meta(2'd1, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, 3);
            check_no_payload();
            case_end();

            case_begin("R_after_invalid_count0");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_invalid_count129");
            send_config(4'd0, 8'd129);
            last_sample_cycle = cyc;
            wait_meta(2'd1, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, 0);
            check_no_payload();
            case_end();

            case_begin("R_after_invalid_count129");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_invalid_count255");
            send_config(4'd0, 8'd255);
            last_sample_cycle = cyc;
            wait_meta(2'd1, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, 0);
            check_no_payload();
            case_end();

            case_begin("R_after_invalid_count255");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_invalid_e3");
            send_config(4'd3, 8'd4);
            last_sample_cycle = cyc;
            wait_meta(2'd1, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, 0);
            check_no_payload();
            case_end();

            case_begin("R_after_invalid_e3");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_invalid_e15");
            send_config(4'd15, 8'd1);
            last_sample_cycle = cyc;
            wait_meta(2'd1, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, 0);
            check_no_payload();
            case_end();

            case_begin("R_after_invalid_e15");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_length_missing_last");
            send_config(4'd0, 8'd3);
            send_sample(16'd0, 1'b0, 0);
            send_sample(16'd1, 1'b0, 0);
            send_sample(16'd2, 1'b0, 0);
            last_sample_cycle = cyc;
            wait_meta(2'd2, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, 2);
            check_no_payload();
            case_end();

            case_begin("R_after_length_missing_last");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_length_early_last");
            send_config(4'd0, 8'd3);
            send_sample(16'd0, 1'b1, 0);
            last_sample_cycle = cyc;
            wait_meta(2'd2, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, 0);
            check_no_payload();
            case_end();

            case_begin("R_after_length_early_last");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();
        end
    endtask

    task automatic directed_legal();
        integer i;
        begin
            case_begin("D_n1_raw_tie");
            d_sample[0] = 5;
            d_last[0]   = 1'b1;
            d_byte[0]   = 8'h00;
            d_byte[1]   = 8'h05;
            legal_body(4'd8, 8'd1, 1'b1, 4'd0, 12'd16, 9'd2, 0, 0, 0);
            case_end();

            case_begin("D_consecutive_A");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_consecutive_B");
            set_v_b();
            legal_body(4'd1, 8'd4, 1'b1, 4'd0, 12'd64, 9'd8, 0, 0, 0);
            case_end();

            case_begin("D_input_gaps_meta_stall");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 50, 10, 1);
            case_end();

            case_begin("D_extra_sample_ignored");
            set_v_a();
            send_config(4'd0, 8'd3);
            send_sample(16'd0, 1'b0, 0);
            send_sample(16'd1, 1'b0, 0);
            send_sample(16'd2, 1'b1, 0);
            @(negedge clk);
            s_valid = 1'b1;
            s_data  = 16'hDEAD;
            s_last  = 1'b1;
            for (i = 0; i < 5; i = i + 1) begin
                @(negedge clk);
                tb_check("extra_sample_not_accepted", (s_ready === 1'b0));
            end
            s_valid = 1'b0;
            wait_meta(2'd0, 8'd3, 4'd0, 1'b0, 4'd0, 12'd22, 9'd3, 0);
            for (i = 0; i < 3; i = i + 1) cur_exp_byte[i] = d_byte[i];
            collect_payload(3, 0);
            case_end();

            case_begin("D_long_backpressure");
            set_v_b();
            legal_body(4'd1, 8'd4, 1'b1, 4'd0, 12'd64, 9'd8, 0, 100, 3);
            case_end();
        end
    endtask

    task automatic abort_pulse(input bit use_cancel, input integer ncycles);
        begin
            if (use_cancel) do_cancel(ncycles);
            else             do_reset(ncycles);
        end
    endtask

    task automatic directed_aborts_early();
        integer i;
        begin
            case_begin("D_reset_load");
            send_config(4'd2, 8'd5);
            send_sample(16'd0, 1'b0, 0);
            send_sample(16'd1000, 1'b0, 0);
            repeat (30) @(negedge clk);
            tb_check("load_phase_s_ready", (s_ready === 1'b1));
            abort_pulse(1'b0, 3);
            repeat (2) @(negedge clk);
            tb_check("abort_idle", (cfg_ready === 1'b1) && (meta_valid === 1'b0) &&
                                   (m_valid === 1'b0));
            case_end();

            case_begin("R_after_reset_load");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_cancel_load");
            send_config(4'd2, 8'd5);
            send_sample(16'd0, 1'b0, 0);
            send_sample(16'd1000, 1'b0, 0);
            repeat (30) @(negedge clk);
            tb_check("load_phase_s_ready", (s_ready === 1'b1));
            abort_pulse(1'b1, 3);
            repeat (2) @(negedge clk);
            tb_check("abort_idle", (cfg_ready === 1'b1) && (meta_valid === 1'b0) &&
                                   (m_valid === 1'b0));
            case_end();

            case_begin("R_after_cancel_load");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_reset_div");
            send_config(4'd0, 8'd8);
            for (i = 0; i < 8; i = i + 1) d_sample[i] = i * 1000;
            for (i = 0; i < 8; i = i + 1)
                send_sample(d_sample[i][15:0], (i == 7), 0);
            repeat (3) @(negedge clk);
            tb_check("div_phase_no_meta", (meta_valid === 1'b0));
            abort_pulse(1'b0, 3);
            repeat (2) @(negedge clk);
            tb_check("abort_idle", (cfg_ready === 1'b1) && (meta_valid === 1'b0) &&
                                   (m_valid === 1'b0));
            case_end();

            case_begin("R_after_reset_div");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_cancel_div");
            send_config(4'd0, 8'd8);
            for (i = 0; i < 8; i = i + 1) d_sample[i] = i * 1000;
            for (i = 0; i < 8; i = i + 1)
                send_sample(d_sample[i][15:0], (i == 7), 0);
            repeat (3) @(negedge clk);
            tb_check("div_phase_no_meta", (meta_valid === 1'b0));
            abort_pulse(1'b1, 3);
            repeat (2) @(negedge clk);
            tb_check("abort_idle", (cfg_ready === 1'b1) && (meta_valid === 1'b0) &&
                                   (m_valid === 1'b0));
            case_end();

            case_begin("R_after_cancel_div");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_reset_sel");
            send_config(4'd0, 8'd8);
            for (i = 0; i < 8; i = i + 1) d_sample[i] = i * 1000;
            for (i = 0; i < 8; i = i + 1)
                send_sample(d_sample[i][15:0], (i == 7), 0);
            repeat (40) @(negedge clk);
            tb_check("sel_phase_internal", (s_ready === 1'b0) &&
                                           (meta_valid === 1'b0) &&
                                           (m_valid === 1'b0));
            abort_pulse(1'b0, 3);
            repeat (2) @(negedge clk);
            tb_check("abort_idle", (cfg_ready === 1'b1) && (meta_valid === 1'b0) &&
                                   (m_valid === 1'b0));
            case_end();

            case_begin("R_after_reset_sel");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_cancel_sel");
            send_config(4'd0, 8'd8);
            for (i = 0; i < 8; i = i + 1) d_sample[i] = i * 1000;
            for (i = 0; i < 8; i = i + 1)
                send_sample(d_sample[i][15:0], (i == 7), 0);
            repeat (40) @(negedge clk);
            tb_check("sel_phase_internal", (s_ready === 1'b0) &&
                                           (meta_valid === 1'b0) &&
                                           (m_valid === 1'b0));
            abort_pulse(1'b1, 3);
            repeat (2) @(negedge clk);
            tb_check("abort_idle", (cfg_ready === 1'b1) && (meta_valid === 1'b0) &&
                                   (m_valid === 1'b0));
            case_end();

            case_begin("R_after_cancel_sel");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();
        end
    endtask

    task automatic directed_aborts_late();
        begin
            case_begin("D_reset_meta");
            send_config(4'd0, 8'd3);
            send_sample(16'd0, 1'b0, 0);
            send_sample(16'd1, 1'b0, 0);
            send_sample(16'd2, 1'b1, 0);
            while (meta_valid !== 1'b1) @(negedge clk);
            repeat (3) @(negedge clk);
            abort_pulse(1'b0, 3);
            repeat (2) @(negedge clk);
            tb_check("abort_idle", (cfg_ready === 1'b1) && (meta_valid === 1'b0) &&
                                   (m_valid === 1'b0));
            case_end();

            case_begin("R_after_reset_meta");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_cancel_meta");
            send_config(4'd0, 8'd3);
            send_sample(16'd0, 1'b0, 0);
            send_sample(16'd1, 1'b0, 0);
            send_sample(16'd2, 1'b1, 0);
            while (meta_valid !== 1'b1) @(negedge clk);
            repeat (3) @(negedge clk);
            abort_pulse(1'b1, 3);
            repeat (2) @(negedge clk);
            tb_check("abort_idle", (cfg_ready === 1'b1) && (meta_valid === 1'b0) &&
                                   (m_valid === 1'b0));
            case_end();

            case_begin("R_after_cancel_meta");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_reset_data");
            send_config(4'd0, 8'd3);
            send_sample(16'd0, 1'b0, 0);
            send_sample(16'd1, 1'b0, 0);
            send_sample(16'd2, 1'b1, 0);
            wait_meta(2'd0, 8'd3, 4'd0, 1'b0, 4'd0, 12'd22, 9'd3, 0);
            while (m_valid !== 1'b1) @(negedge clk);
            repeat (2) @(negedge clk);
            abort_pulse(1'b0, 3);
            repeat (2) @(negedge clk);
            tb_check("abort_idle", (cfg_ready === 1'b1) && (meta_valid === 1'b0) &&
                                   (m_valid === 1'b0));
            case_end();

            case_begin("R_after_reset_data");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();

            case_begin("D_cancel_data");
            send_config(4'd0, 8'd3);
            send_sample(16'd0, 1'b0, 0);
            send_sample(16'd1, 1'b0, 0);
            send_sample(16'd2, 1'b1, 0);
            wait_meta(2'd0, 8'd3, 4'd0, 1'b0, 4'd0, 12'd22, 9'd3, 0);
            while (m_valid !== 1'b1) @(negedge clk);
            repeat (2) @(negedge clk);
            abort_pulse(1'b1, 3);
            repeat (2) @(negedge clk);
            tb_check("abort_idle", (cfg_ready === 1'b1) && (meta_valid === 1'b0) &&
                                   (m_valid === 1'b0));
            case_end();

            case_begin("R_after_cancel_data");
            set_v_a();
            legal_body(4'd0, 8'd3, 1'b0, 4'd0, 12'd22, 9'd3, 0, 0, 0);
            case_end();
        end
    endtask

    task automatic run_directed_tests();
        begin
            directed_errors();
            directed_legal();
            directed_aborts_early();
            directed_aborts_late();
        end
    endtask

    initial begin : watchdog
        #(WATCHDOG_NS);
        $display("TB_WATCHDOG_TIMEOUT");
        $fatal(1, "TB_WATCHDOG_TIMEOUT");
    end

    initial begin : main
        integer fd;
        integer sc;
        integer i;
        integer vi;

        rst        = 1'b1;
        cancel     = 1'b0;
        cfg_valid  = 1'b0;
        s_valid    = 1'b0;
        meta_ready = 1'b0;
        m_ready    = 1'b0;
        repeat (6) @(negedge clk);
        rst = 1'b0;
        repeat (2) @(negedge clk);
        port_fd = $fopen("ports_raw.log", "w");
        if (port_fd == 0) $fatal(1, "TB_FAIL cannot open ports_raw.log");

        fd = $fopen("stimulus.vec", "r");
        if (fd == 0) $fatal(1, "TB_FAIL cannot open stimulus.vec");
        sc = $fscanf(fd, "%d", v_ncases);
        if (sc != 1) $fatal(1, "TB_FAIL cannot read case count");
        if (v_ncases < 1) $fatal(1, "TB_FAIL empty stimulus");
        $display("TB_STIMULUS cases=%0d", v_ncases);

        for (vi = 0; vi < v_ncases; vi = vi + 1) begin
            sc = $fscanf(fd, "%d %d %d %d %d %d %d %d",
                         v_idx, v_e, v_n, v_raw, v_k, v_bits, v_bytes, v_stall);
            if (sc != 8) $fatal(1, "TB_FAIL bad header case=%0d", vi);
            if (v_n < 1 || v_n > MAX_SAMPLES)
                $fatal(1, "TB_FAIL bad sample count case=%0d n=%0d", vi, v_n);
            if (v_bytes < 0 || v_bytes > MAX_BYTES)
                $fatal(1, "TB_FAIL bad byte count case=%0d bytes=%0d", vi, v_bytes);
            for (i = 0; i < v_n; i = i + 1) begin
                sc = $fscanf(fd, "%d", v_sample[i]);
                if (sc != 1) $fatal(1, "TB_FAIL bad sample case=%0d i=%0d", vi, i);
            end
            for (i = 0; i < v_bytes; i = i + 1) begin
                sc = $fscanf(fd, "%d", v_byte[i]);
                if (sc != 1) $fatal(1, "TB_FAIL bad byte case=%0d i=%0d", vi, i);
            end

            case_begin($sformatf("V%0d", v_idx));
            send_config(v_e[3:0], v_n[7:0]);
            for (i = 0; i < v_n; i = i + 1)
                send_sample(v_sample[i][15:0], (i == (v_n - 1)),
                            gap_for(i, v_stall));
            wait_meta(2'd0, v_n[7:0], v_e[3:0], (v_raw != 0), v_k[3:0],
                      v_bits[11:0], v_bytes[8:0], meta_stall_for(v_stall));
            for (i = 0; i < v_bytes; i = i + 1)
                cur_exp_byte[i] = v_byte[i];
            collect_payload(v_bytes, v_stall);
            case_end();
        end
        $fclose(fd);

        run_directed_tests();
        $fclose(port_fd);

        $display("TB_SUMMARY cases=%0d pass=%0d fail=%0d cfg_hs=%0d sample_hs=%0d meta_hs=%0d data_hs=%0d error_meta=%0d resets=%0d cancels=%0d",
                 total_cases, pass_cases, fail_cases, cfg_hs, sample_hs, meta_hs,
                 data_hs, error_meta_cases, reset_pulses, cancel_pulses);
        if (tb_errors != 0) begin
            $display("TB_END fail");
            $fatal(1, "TB_FAILURES %0d", tb_errors);
        end
        $display("TB_END pass");
        $display("TB_DONE");
    end

endmodule
