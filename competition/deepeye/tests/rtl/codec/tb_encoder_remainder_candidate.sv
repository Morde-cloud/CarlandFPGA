`timescale 1ns/1ps
// Author-only public-port miter, task DEEPEYE-IMPLEMENTATION-20261014/v1.
// Work B-ENCODER-REMAINDER-CANDIDATE-20261024-36-v1. H01-H15 preserved;
// contract SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// No DUT hierarchy, force, internal-state probes or board/acceptance claims.
module tb_encoder_remainder_candidate;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst = 1, cancel = 0;
    reg cfg_valid = 0, s_valid = 0, s_last = 0;
    reg [7:0] cfg_count = 0;
    reg [3:0] cfg_e = 0;
    reg [15:0] s_data = 0;
    reg meta_ready = 0, m_ready = 0;
    wire cfg_r0, cfg_r1, s_r0, s_r1, mv0, mv1, dv0, dv1;
    wire [1:0] err0, err1;
    wire [7:0] count0, count1, data0, data1;
    wire [3:0] e0, e1, k0, k1;
    wire raw0, raw1, last0, last1;
    wire [11:0] bits0, bits1;
    wire [8:0] bytes0, bytes1;

    deepeye_block_encoder reference_dut (
        .clk(clk), .rst(rst), .cancel(cancel),
        .cfg_valid(cfg_valid), .cfg_ready(cfg_r0), .cfg_count(cfg_count), .cfg_e(cfg_e),
        .s_valid(s_valid), .s_ready(s_r0), .s_data(s_data), .s_last(s_last),
        .meta_valid(mv0), .meta_ready(meta_ready), .meta_error(err0),
        .meta_count(count0), .meta_e(e0), .meta_raw(raw0), .meta_k(k0),
        .meta_valid_bits(bits0), .meta_bytes(bytes0),
        .m_valid(dv0), .m_ready(m_ready), .m_data(data0), .m_last(last0)
    );
    deepeye_block_encoder_remainder_candidate candidate_dut (
        .clk(clk), .rst(rst), .cancel(cancel),
        .cfg_valid(cfg_valid), .cfg_ready(cfg_r1), .cfg_count(cfg_count), .cfg_e(cfg_e),
        .s_valid(s_valid), .s_ready(s_r1), .s_data(s_data), .s_last(s_last),
        .meta_valid(mv1), .meta_ready(meta_ready), .meta_error(err1),
        .meta_count(count1), .meta_e(e1), .meta_raw(raw1), .meta_k(k1),
        .meta_valid_bits(bits1), .meta_bytes(bytes1),
        .m_valid(dv1), .m_ready(m_ready), .m_data(data1), .m_last(last1)
    );

    integer cycle = 0, trace_fd, input_fd, scan_rc;
    integer cfg_hs = 0, sample_hs = 0, meta_hs = 0, data_hs = 0;
    integer meta_seen = 0, byte_seen = 0;
    integer stall_cfg = 0, stall_sample = 0, stall_meta = 0, stall_data = 0;
    integer reset_seen = 0, cancel_seen = 0, valid_cases = 0, invalid_cases = 0;
    integer abort_cases = 0, recovery_cases = 0, completed = 0;
    integer case_id = -1, n, ev, ex_raw, ex_k, ex_bits, ex_bytes;
    integer ex_error = 0, ex_count = 0, ex_e = 0;
    reg monitor_enable = 0, expected_on = 0;
    reg cfg_accepted, sample_accepted;
    reg [15:0] samples [0:127];
    reg [7:0] expected_data [0:255];
    string input_path, trace_path;

    task automatic fail(input string message);
        $display("TB_FAIL cycle=%0d case=%0d %s", cycle, case_id, message);
        $fatal(1, "TB_FAIL");
    endtask

    // Compare every cycle after initialization, including all stall/abort cycles.
    // Metadata/data are masked precisely when their corresponding valid is low.
    always @(posedge clk) begin
        cycle = cycle + 1;
        cfg_accepted = cfg_valid && cfg_r0;
        sample_accepted = s_valid && s_r0;
        if (monitor_enable) begin
            if ((^{cfg_r0, s_r0, mv0, dv0, cfg_r1, s_r1, mv1, dv1}) === 1'bx)
                fail("unknown ready/valid");
            if ({cfg_r0,s_r0,mv0,dv0} !== {cfg_r1,s_r1,mv1,dv1})
                fail("miter ready/valid");
            if (mv0 && ({err0,count0,e0,raw0,k0,bits0,bytes0} !==
                        {err1,count1,e1,raw1,k1,bits1,bytes1}))
                fail("miter metadata");
            if (dv0 && ({data0,last0} !== {data1,last1}))
                fail("miter byte/last");
            if ((rst || cancel) && {cfg_r0,s_r0,mv0,dv0} !== 4'b0000)
                fail("reset/cancel gating");
            if (mv0 && (^{err0,count0,e0,raw0,k0,bits0,bytes0}) === 1'bx)
                fail("unknown valid metadata");
            if (dv0 && (^{data0,last0}) === 1'bx) fail("unknown valid data");
            $fdisplay(trace_fd, "%0d %0d %b%b %b%b %b%b %b%b %b%b %b%b %h %h %h %h",
                cycle, case_id, rst,cancel, cfg_valid,cfg_r0, s_valid,s_r0,
                mv0,meta_ready, dv0,m_ready, cfg_r1,s_r1,
                mv0 ? {err0,count0,e0,raw0,k0,bits0,bytes0} : 40'd0,
                dv0 ? {data0,last0} : 9'd0, s_data, {mv1,dv1});
            if (cfg_valid && !cfg_r0) stall_cfg = stall_cfg + 1;
            if (s_valid && !s_r0) stall_sample = stall_sample + 1;
            if (mv0 && !meta_ready) stall_meta = stall_meta + 1;
            if (dv0 && !m_ready) stall_data = stall_data + 1;
            if (rst) reset_seen = reset_seen + 1;
            if (cancel) cancel_seen = cancel_seen + 1;
            if (cfg_accepted) cfg_hs = cfg_hs + 1;
            if (sample_accepted) sample_hs = sample_hs + 1;
            if (mv0 && meta_ready) meta_hs = meta_hs + 1;
            if (dv0 && m_ready) data_hs = data_hs + 1;
            if (expected_on && mv0) begin
                if (err0 !== ex_error[1:0] || count0 !== ex_count[7:0] ||
                    e0 !== ex_e[3:0] || raw0 !== ex_raw[0] ||
                    k0 !== ex_k[3:0] || bits0 !== ex_bits[11:0] ||
                    bytes0 !== ex_bytes[8:0]) fail("golden metadata");
                if (meta_ready) meta_seen = meta_seen + 1;
            end
            if (expected_on && dv0) begin
                if (ex_error != 0 || byte_seen >= ex_bytes) fail("unexpected output byte");
                if (data0 !== expected_data[byte_seen] ||
                    last0 !== (byte_seen == ex_bytes-1)) fail("golden byte/last");
                if (m_ready) byte_seen = byte_seen + 1;
            end
        end
    end

    task automatic step;
        @(posedge clk); #1;
    endtask
    task automatic idle_clocks(input integer amount);
        repeat (amount) begin
            @(negedge clk);
            s_data = s_data ^ 16'ha53c; // deliberately change unaccepted live input
            step();
        end
    endtask
    task automatic reset_or_cancel(input integer which);
        @(negedge clk);
        expected_on = 0;
        if (which == 0) rst = 1; else cancel = 1;
        // Contending inputs exercise synchronous abort priority over handshakes.
        cfg_valid = 1; s_valid = 1; s_last = 1;
        meta_ready = 1; m_ready = 1;
        step();
        @(negedge clk);
        rst = 0; cancel = 0; cfg_valid = 0; s_valid = 0; s_last = 0;
        meta_ready = 0; m_ready = 0;
        step();
        if (cfg_r0 !== 1'b1 || s_r0 !== 1'b0 || mv0 !== 1'b0 || dv0 !== 1'b0)
            fail("abort did not return idle");
        idle_clocks(3);
    endtask
    task automatic send_config(input integer count_arg, input integer e_arg);
        integer timeout_cfg;
        @(negedge clk);
        cfg_count = count_arg[7:0]; cfg_e = e_arg[3:0]; cfg_valid = 1;
        timeout_cfg = 0;
        begin : wait_config
            forever begin
                step();
                if (cfg_accepted) disable wait_config;
                timeout_cfg = timeout_cfg + 1;
                if (timeout_cfg > 100) fail("config timeout");
            end
        end
        @(negedge clk); cfg_valid = 0;
    endtask
    task automatic send_sample(input integer value, input integer last_arg, input integer gap);
        integer timeout_sample;
        s_valid = 0;
        idle_clocks(gap);
        @(negedge clk); s_valid = 1; s_data = value[15:0]; s_last = last_arg[0];
        timeout_sample = 0;
        begin : wait_sample
            forever begin
                step();
                if (sample_accepted) disable wait_sample;
                timeout_sample = timeout_sample + 1;
                if (timeout_sample > 100) fail("sample timeout");
            end
        end
        @(negedge clk); s_valid = 0; s_last = 0; s_data = ~value[15:0];
    endtask
    task automatic wait_meta;
        integer timeout_meta;
        timeout_meta = 0;
        while (mv0 !== 1'b1) begin
            idle_clocks(1);
            timeout_meta = timeout_meta + 1;
            if (timeout_meta > 5000) fail("metadata timeout");
        end
    endtask
    task automatic finish_expected;
        integer timeout_data, j;
        wait_meta();
        // Offer another configuration while busy, then withdraw before idle.
        @(negedge clk); cfg_valid = 1;
        idle_clocks(4 + (case_id % 3));
        @(negedge clk); cfg_valid = 0; meta_ready = 1;
        step();
        @(negedge clk); meta_ready = 0;
        if (ex_error == 0) begin
            timeout_data = 0;
            while (byte_seen < ex_bytes) begin
                @(negedge clk);
                m_ready = ((timeout_data % 7) >= 3);
                s_data = s_data ^ 16'h96e1;
                step();
                timeout_data = timeout_data + 1;
                if (timeout_data > 20000) fail("data timeout");
            end
        end
        @(negedge clk); m_ready = 0;
        if (meta_seen != 1 || byte_seen != ex_bytes) fail("golden transaction counts");
        expected_on = 0;
        for (j = 0; j < 3; j = j + 1) begin
            step();
            if (mv0 || dv0 || !cfg_r0) fail("duplicate/stale completion");
            @(negedge clk);
        end
        completed = completed + 1;
    endtask
    task automatic prepare_expected(input integer error_arg, input integer count_arg,
                                    input integer e_arg, input integer raw_arg,
                                    input integer k_arg, input integer bits_arg,
                                    input integer bytes_arg);
        ex_error = error_arg; ex_count = count_arg; ex_e = e_arg;
        ex_raw = raw_arg; ex_k = k_arg; ex_bits = bits_arg; ex_bytes = bytes_arg;
        meta_seen = 0; byte_seen = 0; expected_on = 1;
    endtask
    task automatic recovery;
        case_id = 100000 + recovery_cases;
        expected_data[0] = 8'h12; expected_data[1] = 8'h34;
        prepare_expected(0,1,8,1,0,16,2);
        send_config(1,8); send_sample(16'h1234,1,1);
        finish_expected();
        recovery_cases = recovery_cases + 1;
    endtask

    integer i, j, total, which, stage, stage_case, vtmp;
    integer invalid_n [0:3];
    initial begin
        if (!$value$plusargs("INPUT=%s", input_path)) $fatal(1,"missing INPUT");
        if (!$value$plusargs("TRACE=%s", trace_path)) $fatal(1,"missing TRACE");
        input_fd = $fopen(input_path, "r"); trace_fd = $fopen(trace_path, "w");
        if (!input_fd || !trace_fd) $fatal(1,"cannot open fixture/trace");
        repeat (3) step();
        @(negedge clk); rst = 0; monitor_enable = 1;
        scan_rc = $fscanf(input_fd, "%d", total);
        if (scan_rc != 1 || total < 1) fail("fixture count");
        for (i = 0; i < total; i = i + 1) begin
            scan_rc = $fscanf(input_fd, "%d %d %d %d %d %d %d", case_id,n,ev,ex_raw,ex_k,ex_bits,ex_bytes);
            if (scan_rc != 7 || n < 1 || n > 128 || ex_bytes < 2 || ex_bytes > 256)
                fail("fixture header");
            for (j = 0; j < n; j = j + 1) begin
                scan_rc = $fscanf(input_fd, "%h", samples[j]);
                if (scan_rc != 1) fail("fixture sample");
            end
            for (j = 0; j < ex_bytes; j = j + 1) begin
                scan_rc = $fscanf(input_fd, "%h", expected_data[j]);
                if (scan_rc != 1) fail("fixture byte");
            end
            prepare_expected(0,n,ev,ex_raw,ex_k,ex_bits,ex_bytes);
            idle_clocks(case_id % 4);
            send_config(n,ev);
            for (j = 0; j < n; j = j + 1) send_sample(samples[j],j == n-1,(j+case_id)%3);
            finish_expected(); valid_cases = valid_cases + 1;
            $display("TB_CASE id=%0d n=%0d e=%0d raw=%0d k=%0d bits=%0d bytes=%0d PASS",
                     case_id,n,ev,ex_raw,ex_k,ex_bits,ex_bytes);
        end
        $fclose(input_fd);

        // All invalid count/E headers, including stalled error metadata.
        invalid_n[0]=0; invalid_n[1]=129; invalid_n[2]=255; invalid_n[3]=2;
        for (i = 0; i < 4; i = i + 1) begin
            case_id = 200000 + i;
            prepare_expected(1,0,0,1,0,0,0);
            send_config(invalid_n[i],i == 3 ? 3 : 0);
            finish_expected(); invalid_cases = invalid_cases + 1;
            $display("TB_INVALID id=%0d PASS", case_id);
        end
        // Early and missing s_last are separately required protocol errors.
        for (i = 0; i < 2; i = i + 1) begin
            case_id = 200004 + i;
            prepare_expected(2,0,0,1,0,0,0);
            send_config(2,2);
            send_sample(65535,i == 0,0);
            if (i == 1) send_sample(0,0,0);
            finish_expected(); invalid_cases = invalid_cases + 1;
            $display("TB_INVALID id=%0d PASS", case_id);
        end

        // Abort at cycle offsets deduced from accepted public handshakes only.
        // 0 idle; 1 load; 2 first sample; 3 early divide; 4 last divide step;
        // 5 divide finalization; 6 selection; 7 metadata; 8 generation; 9 output;
        // 10 after one output byte; 11 invalid metadata. Both reset and cancel.
        for (which = 0; which < 2; which = which + 1) begin
            for (stage = 0; stage < 12; stage = stage + 1) begin
                stage_case = 300000 + which*100 + stage; case_id = stage_case;
                expected_on = 0; meta_ready = 0; m_ready = 0;
                if (stage == 11) send_config(0,3);
                else if (stage > 0) begin
                    send_config(2,8);
                    if (stage >= 2) send_sample(65535,0,0);
                    if (stage >= 3) send_sample(0,1,0);
                    if (stage == 3) idle_clocks(3);
                    if (stage == 4) idle_clocks(16);
                    if (stage == 5) idle_clocks(17);
                    if (stage == 6) idle_clocks(22);
                    if (stage >= 7) wait_meta();
                    if (stage >= 8) begin
                        @(negedge clk); meta_ready = 1;
                        step(); @(negedge clk); meta_ready = 0;
                        if (stage == 8) idle_clocks(7);
                        if (stage >= 9) begin
                            j = 0;
                            while (!dv0) begin
                                idle_clocks(1); j=j+1;
                                if (j > 5000) fail("abort output timeout");
                            end
                        end
                        if (stage == 10) begin
                            @(negedge clk); m_ready = 1;
                            step(); @(negedge clk); m_ready = 0;
                        end
                    end
                end
                reset_or_cancel(which);
                abort_cases = abort_cases + 1;
                $display("TB_ABORT id=%0d which=%0d stage=%0d PASS",stage_case,which,stage);
                recovery();
            end
        end
        if (stall_cfg == 0 || stall_sample == 0 || stall_meta == 0 || stall_data == 0)
            fail("missing stall coverage");
        if (reset_seen != 12 || cancel_seen != 12 || abort_cases != 24 || recovery_cases != 24)
            fail("missing abort/recovery coverage");
        $display("TB_SUMMARY valid=%0d invalid=%0d abort=%0d recovery=%0d completed=%0d cycles=%0d cfg=%0d samples=%0d meta=%0d data=%0d cfgstall=%0d samplestall=%0d metastall=%0d datastall=%0d reset=%0d cancel=%0d",
            valid_cases,invalid_cases,abort_cases,recovery_cases,completed,cycle,
            cfg_hs,sample_hs,meta_hs,data_hs,stall_cfg,stall_sample,stall_meta,stall_data,reset_seen,cancel_seen);
        $fclose(trace_fd);
        $display("TB_DONE encoder_remainder_candidate PASS");
        $finish;
    end
    initial begin
        #200000000;
        $fatal(1,"TB_FAIL global timeout");
    end
endmodule
