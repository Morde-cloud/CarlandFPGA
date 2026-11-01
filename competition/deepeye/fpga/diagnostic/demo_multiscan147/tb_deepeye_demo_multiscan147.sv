`timescale 1ns/1ps
// Focused new-source TB for B-DEEPEYE-DEMO-MULTISCAN-INGRESS-20261101-147.
// SOURCE_ONLY: this file is provided for the parent's later selected run.
// It is not an execution result, board result, ADC/BOOT proof or acceptance.
//
// One new batch:
//   * three scans x four lanes, values selected by the main;
//   * dynamic session/epoch/base frame sequence/origin/tag;
//   * UART TX is looped back only inside this TB to the DUT's existing pinned
//     RX, and bytes are captured through up_valid/up_ready;
//   * four frames, exact original values and native indices, measured RAW or
//     Rice mode from the actual prefix byte;
//   * a base_frame_seq+3 wrap refusal, a held-status refusal, a mid-frame
//     cancel, and a mid-frame disable, each with no successful result and no
//     automatic replay. Abort cause is checked separately.
module tb_deepeye_demo_multiscan147;
    logic clk = 1'b0;
    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic enable = 1'b1;
    logic arm = 1'b0;

    logic [31:0] cfg_session = 32'd0;
    logic [7:0] cfg_epoch = 8'd0;
    logic [15:0] cfg_base_frame_seq = 16'd0;
    logic [62:0] cfg_origin_qpc_ns = 63'd0;
    logic [31:0] cfg_tag = 32'd0;

    logic s_valid = 1'b0;
    wire s_ready;
    logic [1:0] s_channel = 2'd0;
    logic [15:0] s_data = 16'd0;
    logic [63:0] s_acq_qpc_ns = 64'd0;
    logic [7:0] s_quality = 8'd0;
    logic [31:0] s_tag = 32'd0;
    logic [31:0] s_native_first_seq = 32'd0;
    logic [31:0] s_native_last_seq = 32'd0;
    logic s_semantics_valid = 1'b1;
    logic s_fresh = 1'b1;
    logic s_sample_valid = 1'b1;
    logic s_held = 1'b0;
    logic s_saturated = 1'b0;
    logic s_source_fault = 1'b0;

    wire tx;
    wire result_valid;
    logic result_ready = 1'b0;
    wire [2:0] result_error;
    wire [5:0] result_bytes;

    wire rx_async;
    assign rx_async = tx;
    wire up_valid;
    logic up_ready = 1'b1;
    wire [7:0] up_data;
    wire up_busy;
    wire up_framing_error;
    wire up_overrun;
    wire up_false_start;

    wire refused;
    wire [3:0] refusal_code;
    wire busy;
    wire quiescent;
    wire armed;
    wire arm_ready;
    wire batch_done;
    wire aborted;
    wire [1:0] abort_code;
    wire [2:0] frames_retired;
    wire [3:0] accepted_lanes;

    deepeye_demo_multiscan147 dut (
        .clk(clk), .rst(rst), .cancel(cancel), .enable(enable), .arm(arm),
        .cfg_session(cfg_session), .cfg_epoch(cfg_epoch),
        .cfg_base_frame_seq(cfg_base_frame_seq),
        .cfg_origin_qpc_ns(cfg_origin_qpc_ns), .cfg_tag(cfg_tag),
        .s_valid(s_valid), .s_ready(s_ready), .s_channel(s_channel),
        .s_data(s_data), .s_acq_qpc_ns(s_acq_qpc_ns), .s_quality(s_quality),
        .s_tag(s_tag), .s_native_first_seq(s_native_first_seq),
        .s_native_last_seq(s_native_last_seq),
        .s_semantics_valid(s_semantics_valid), .s_fresh(s_fresh),
        .s_sample_valid(s_sample_valid), .s_held(s_held),
        .s_saturated(s_saturated), .s_source_fault(s_source_fault),
        .tx(tx), .result_valid(result_valid), .result_ready(result_ready),
        .result_error(result_error), .result_bytes(result_bytes),
        .rx_async(rx_async), .up_valid(up_valid), .up_ready(up_ready),
        .up_data(up_data), .up_busy(up_busy), .up_framing_error(up_framing_error),
        .up_overrun(up_overrun), .up_false_start(up_false_start),
        .refused(refused), .refusal_code(refusal_code), .busy(busy),
        .quiescent(quiescent), .armed(armed), .arm_ready(arm_ready),
        .batch_done(batch_done), .aborted(aborted), .abort_code(abort_code),
        .frames_retired(frames_retired), .accepted_lanes(accepted_lanes)
    );

    localparam logic [31:0] SESSION = 32'h42a50031;
    localparam logic [7:0] EPOCH = 8'h2d;
    localparam logic [15:0] BASE_SEQ = 16'h1200;
    localparam logic [62:0] ORIGIN63 = 63'd9007199254740993;
    localparam logic [63:0] ORIGIN64 = 64'd9007199254740993;
    localparam logic [31:0] TAG = 32'h00000051;

    logic [15:0] raw [0:11];
    logic [15:0] expected [0:11];
    logic [63:0] scan_qpc [0:2];
    logic [7:0] rx_bytes [0:511];
    integer rx_count = 0;
    integer good_rx_count = 0;
    integer cancel_rx_count = 0;
    integer disable_rx_count = 0;
    integer cycles = 0;
    integer completed = 0;
    integer up_framing_count = 0;
    integer up_overrun_count = 0;
    integer up_false_count = 0;
    integer result_bytes_cap [0:3];
    integer result_error_cap [0:3];

    string bytefile;
    string logfile;
    integer fd_bytes = 0;
    integer fd_log = 0;

    always #10 clk = ~clk;

    always @(posedge clk) begin
        cycles = cycles + 1;
        if (cycles > 500000)
            $fatal(1, "TB_TIMEOUT cycles=%0d rx=%0d busy=%0d", cycles, rx_count, busy);
        if (!rst && up_valid && up_ready) begin
            if (rx_count >= 512)
                $fatal(1, "TB_RX_OVERFLOW");
            rx_bytes[rx_count] = up_data;
            $fdisplay(fd_bytes, "CAPTURE %0d %02x", rx_count, up_data);
            rx_count = rx_count + 1;
        end
        if (up_framing_error) up_framing_count = up_framing_count + 1;
        if (up_overrun) up_overrun_count = up_overrun_count + 1;
        if (up_false_start) up_false_count = up_false_count + 1;
    end

    function automatic logic [15:0] crc_byte(
        input logic [15:0] crc_in,
        input logic [7:0] data_in
    );
        integer j;
        logic [15:0] c;
        begin
            c = crc_in;
            for (j = 0; j < 8; j = j + 1) begin
                if (c[15] ^ data_in[7-j])
                    c = (c << 1) ^ 16'h1021;
                else
                    c = c << 1;
            end
            crc_byte = c;
        end
    endfunction

    task automatic step(input integer n);
        begin
            repeat (n) @(negedge clk);
        end
    endtask

    task automatic fail(input string msg);
        begin
            $display("TEST_FAIL %s cycles=%0d rx=%0d", msg, cycles, rx_count);
            if (fd_log != 0)
                $fdisplay(fd_log, "TEST_FAIL %s cycles=%0d rx=%0d", msg, cycles, rx_count);
            if (fd_bytes != 0) $fclose(fd_bytes);
            if (fd_log != 0) $fclose(fd_log);
            $fatal(1, "TEST_FAIL %s", msg);
        end
    endtask

    task automatic check(input logic cond, input string msg);
        begin
            if (cond !== 1'b1) fail(msg);
        end
    endtask

    // Sample a real positive-edge transfer with the offered payload held stable.
    task automatic await_lane_handshake(input integer limit);
        integer t;
        begin
            t = 0;
            do begin
                @(posedge clk);
                t = t + 1;
                if (t > limit) fail("offered lane handshake timeout");
            end while (s_ready !== 1'b1);
            @(negedge clk);
        end
    endtask

    task automatic wait_armed(input integer limit);
        integer t;
        begin
            t = 0;
            while (!armed) begin
                step(1);
                t = t + 1;
                if (t > limit) fail("armed timeout");
            end
        end
    endtask

    task automatic wait_result(input integer limit);
        integer t;
        begin
            t = 0;
            while (result_valid !== 1'b1) begin
                step(1);
                t = t + 1;
                if (t > limit) fail("result timeout");
            end
        end
    endtask

    task automatic wait_refused(input integer limit);
        integer t;
        begin
            t = 0;
            while (!refused) begin
                step(1);
                t = t + 1;
                if (t > limit) fail("refused timeout");
            end
        end
    endtask

    task automatic wait_frames(input integer n, input integer limit);
        integer t;
        begin
            t = 0;
            while (frames_retired < n) begin
                step(1);
                t = t + 1;
                if (t > limit) fail("frames_retired timeout");
            end
        end
    endtask

    task automatic wait_quiescent(input integer limit);
        integer t;
        begin
            t = 0;
            while (!quiescent) begin
                step(1);
                t = t + 1;
                if (t > limit) fail("quiescent timeout");
            end
        end
    endtask

    task automatic do_reset;
        begin
            rst = 1'b1;
            cancel = 1'b0;
            enable = 1'b1;
            arm = 1'b0;
            s_valid = 1'b0;
            result_ready = 1'b0;
            up_ready = 1'b1;
            s_channel = 2'd0;
            s_data = 16'd0;
            s_acq_qpc_ns = 64'd0;
            s_quality = 8'd0;
            s_tag = 32'd0;
            s_native_first_seq = 32'd0;
            s_native_last_seq = 32'd0;
            s_semantics_valid = 1'b1;
            s_fresh = 1'b1;
            s_sample_valid = 1'b1;
            s_held = 1'b0;
            s_saturated = 1'b0;
            s_source_fault = 1'b0;
            rx_count = 0;
            up_framing_count = 0;
            up_overrun_count = 0;
            up_false_count = 0;
            repeat (10) step(1);
            rst = 1'b0;
            repeat (10) step(1);
        end
    endtask

    task automatic do_arm(
        input logic [31:0] session_i,
        input logic [7:0] epoch_i,
        input logic [15:0] base_i,
        input logic [62:0] origin_i,
        input logic [31:0] tag_i
    );
        begin
            cfg_session = session_i;
            cfg_epoch = epoch_i;
            cfg_base_frame_seq = base_i;
            cfg_origin_qpc_ns = origin_i;
            cfg_tag = tag_i;
            arm = 1'b0;
            step(2);
            arm = 1'b1;
            step(1);
            arm = 1'b0;
            step(2);
        end
    endtask

    task automatic cancel_pulse;
        begin
            cancel = 1'b1;
            repeat (20) step(1);
            cancel = 1'b0;
            repeat (5) step(1);
        end
    endtask

    task automatic send_good_lane(input integer scan, input integer lane);
        begin
            s_channel = lane[1:0];
            s_data = raw[scan*4+lane];
            s_acq_qpc_ns = scan_qpc[scan];
            s_quality = 8'd0;
            s_tag = TAG;
            s_native_first_seq = 32'd40 + (scan * 4);
            s_native_last_seq = s_native_first_seq + 32'd3;
            s_semantics_valid = 1'b1;
            s_fresh = 1'b1;
            s_sample_valid = 1'b1;
            s_held = 1'b0;
            s_saturated = 1'b0;
            s_source_fault = 1'b0;
            s_valid = 1'b1;
            await_lane_handshake(2000);
            s_valid = 1'b0;
            step(1);
        end
    endtask

    task automatic parse_good_frames;
        integer pos;
        integer f;
        integer len;
        integer total;
        integer i;
        integer code_len;
        integer bits;
        integer raw_mode;
        integer k;
        integer ecode;
        integer channel;
        integer valid;
        integer sat;
        integer held;
        integer fault;
        integer longf;
        integer count;
        integer idx_stride;
        integer tick_stride;
        integer bitpos;
        integer q;
        integer z;
        integer s;
        integer b;
        integer p;
        integer unary_q;
        integer padbit;
        logic [15:0] crc;
        logic [15:0] crc_wire;
        logic [15:0] vals0;
        logic [15:0] vals1;
        logic [15:0] vals2;
        logic [63:0] tick64;
        logic [31:0] session32;
        logic [31:0] index32;
        begin
            pos = 0;
            for (f = 0; f < 4; f = f + 1) begin
                if (rx_count < (pos + 14)) fail("short captured frame");
                if (rx_bytes[pos+0] !== 8'hA5) fail("frame magic 0");
                if (rx_bytes[pos+1] !== 8'h5A) fail("frame magic 1");
                if (rx_bytes[pos+2] !== 8'h03) fail("frame version");
                if (rx_bytes[pos+3] !== 8'hE4) fail("frame type");
                len = rx_bytes[pos+4];
                if (len < 25 || len > 32) fail("payload length bound");
                total = 14 + len;
                if ((pos + total) > rx_count) fail("short captured payload");

                crc = 16'hFFFF;
                for (i = 2; i < (12 + len); i = i + 1)
                    crc = crc_byte(crc, rx_bytes[pos+i]);
                crc_wire = {rx_bytes[pos+13+len], rx_bytes[pos+12+len]};
                if (crc !== crc_wire) fail("CRC mismatch");

                if (rx_bytes[pos+5] !== 8'h2D) fail("wire epoch");
                if ({rx_bytes[pos+7], rx_bytes[pos+6]} !== (16'h1200 + f))
                    fail("wire frame sequence");
                tick64 = {32'd0, rx_bytes[pos+11], rx_bytes[pos+10],
                          rx_bytes[pos+9], rx_bytes[pos+8]};
                if (tick64 !== 64'd100) fail("wire first tick");

                if (rx_bytes[pos+12] !== 8'h02) fail("payload revision");
                raw_mode = (rx_bytes[pos+13] >> 3) & 1;
                k = (rx_bytes[pos+13] >> 4) & 8'h0F;
                ecode = rx_bytes[pos+13] & 8'h07;
                if (ecode !== 0) fail("payload E code");
                channel = rx_bytes[pos+14] & 8'h03;
                valid = (rx_bytes[pos+14] >> 2) & 1;
                sat = (rx_bytes[pos+14] >> 3) & 1;
                held = (rx_bytes[pos+14] >> 4) & 1;
                fault = (rx_bytes[pos+14] >> 5) & 1;
                longf = (rx_bytes[pos+14] >> 6) & 1;
                if (channel !== f) fail("payload channel");
                if (valid !== 1 || sat !== 0 || held !== 0 || fault !== 0 || longf !== 0)
                    fail("payload status flags");
                count = rx_bytes[pos+15];
                if (count !== 3) fail("payload count");
                bits = rx_bytes[pos+16];
                session32 = {rx_bytes[pos+20], rx_bytes[pos+19],
                             rx_bytes[pos+18], rx_bytes[pos+17]};
                if (session32 !== 32'h42a50031) fail("payload session");
                index32 = {rx_bytes[pos+24], rx_bytes[pos+23],
                           rx_bytes[pos+22], rx_bytes[pos+21]};
                if (index32 !== (32'd40 + f)) fail("payload native first index");
                tick64 = {rx_bytes[pos+32], rx_bytes[pos+31],
                          rx_bytes[pos+30], rx_bytes[pos+29], rx_bytes[pos+28],
                          rx_bytes[pos+27], rx_bytes[pos+26], rx_bytes[pos+25]};
                if (tick64 !== 64'd100) fail("payload first tick");
                idx_stride = {rx_bytes[pos+34], rx_bytes[pos+33]};
                if (idx_stride !== 4) fail("payload index stride");
                tick_stride = {rx_bytes[pos+36], rx_bytes[pos+35]};
                if (tick_stride !== 200) fail("payload tick stride");

                code_len = len - 25;
                if (code_len < 2 || code_len > 7) fail("code byte bound");
                if (code_len !== ((bits + 7) / 8)) fail("code length versus bits");
                if (raw_mode == 1) begin
                    if (k !== 0 || bits !== 48 || code_len !== 6)
                        fail("RAW shape");
                    vals0 = {rx_bytes[pos+38], rx_bytes[pos+37]};
                    vals1 = {rx_bytes[pos+40], rx_bytes[pos+39]};
                    vals2 = {rx_bytes[pos+42], rx_bytes[pos+41]};
                end else begin
                    vals0 = {rx_bytes[pos+38], rx_bytes[pos+37]};
                    bitpos = 0;
                    p = vals0;
                    for (s = 0; s < 2; s = s + 1) begin
                        unary_q = 0;
                        b = 0;
                        while (b == 0) begin
                            if (bitpos >= ((code_len * 8) - 16))
                                fail("Rice unary overrun");
                            b = (rx_bytes[pos+39+(bitpos/8)] >> (7-(bitpos%8))) & 1;
                            bitpos = bitpos + 1;
                            if (b == 0) unary_q = unary_q + 1;
                        end
                        z = 0;
                        for (i = 0; i < k; i = i + 1) begin
                            if (bitpos >= ((code_len * 8) - 16))
                                fail("Rice remainder overrun");
                            b = (rx_bytes[pos+39+(bitpos/8)] >> (7-(bitpos%8))) & 1;
                            bitpos = bitpos + 1;
                            z = (z << 1) | b;
                        end
                        z = (unary_q << k) | z;
                        if ((z & 1) != 0) q = -((z + 1) / 2);
                        else q = z / 2;
                        p = p + q;
                        if (p < 0 || p > 65535) fail("Rice decoded range");
                        if (s == 0) vals1 = p[15:0];
                        else vals2 = p[15:0];
                    end
                    if (bits !== (16 + bitpos)) fail("Rice declared bit count");
                    for (padbit = 16 + bitpos; padbit < (code_len * 8); padbit = padbit + 1) begin
                        if ((rx_bytes[pos+37+(padbit/8)] >> (7-(padbit%8))) & 1)
                            fail("Rice nonzero padding");
                    end
                end

                if (vals0 !== expected[f*3+0]) fail("sample 0 mismatch");
                if (vals1 !== expected[f*3+1]) fail("sample 1 mismatch");
                if (vals2 !== expected[f*3+2]) fail("sample 2 mismatch");
                if (result_error_cap[f] !== 0) fail("result error captured");
                if (result_bytes_cap[f] !== total) fail("result bytes mismatch");

                $fwrite(fd_log, "FRAME_BYTES %0d", f);
                for (i = 0; i < total; i = i + 1)
                    $fwrite(fd_log, " %02x", rx_bytes[pos+i]);
                $fwrite(fd_log, "\n");
                if (raw_mode == 1) begin
                    $fdisplay(fd_log,
                        "FRAME %0d MODE RAW LEN %0d TOTAL %0d SESSION %08x INDEX %0d TICK %0d VALUES %0d %0d %0d",
                        f, len, total, session32, index32, tick64[31:0],
                        vals0, vals1, vals2);
                    $display("FRAME %0d MODE RAW TOTAL %0d VALUES %0d %0d %0d",
                             f, total, vals0, vals1, vals2);
                end else begin
                    $fdisplay(fd_log,
                        "FRAME %0d MODE RICE K %0d LEN %0d TOTAL %0d SESSION %08x INDEX %0d TICK %0d VALUES %0d %0d %0d",
                        f, k, len, total, session32, index32, tick64[31:0],
                        vals0, vals1, vals2);
                    $display("FRAME %0d MODE RICE K %0d TOTAL %0d VALUES %0d %0d %0d",
                             f, k, total, vals0, vals1, vals2);
                end
                pos = pos + total;
            end
            if (pos !== rx_count) fail("extra captured bytes");
            $fdisplay(fd_log,
                "ORIGINAL_MATCH 12 values; native index 40..43; session 42a50031; tick 100; stride 200; quality input-only 0");
        end
    endtask

    integer scan;
    integer lane;
    integer f;
    integer cap_err;
    integer cap_bytes;
    integer i;
    integer t;

    initial begin
        if (!$value$plusargs("bytefile=%s", bytefile))
            bytefile = "demo_multiscan147_uart_bytes.txt";
        if (!$value$plusargs("logfile=%s", logfile))
            logfile = "demo_multiscan147_tb.log";
        fd_bytes = $fopen(bytefile, "w");
        fd_log = $fopen(logfile, "w");
        if (fd_bytes == 0 || fd_log == 0)
            $fatal(1, "cannot open byte/log files");

        raw[0] = 16'd1234;  raw[1] = 16'd40000; raw[2] = 16'd65535; raw[3] = 16'd0;
        raw[4] = 16'd1234;  raw[5] = 16'd40001; raw[6] = 16'd65534; raw[7] = 16'd65535;
        raw[8] = 16'd1234;  raw[9] = 16'd40002; raw[10] = 16'd65533; raw[11] = 16'd1;
        for (i = 0; i < 4; i = i + 1) begin
            expected[i*3+0] = raw[0*4+i];
            expected[i*3+1] = raw[1*4+i];
            expected[i*3+2] = raw[2*4+i];
        end
        scan_qpc[0] = ORIGIN64 + 64'd100007;
        scan_qpc[1] = scan_qpc[0] + 64'd200000;
        scan_qpc[2] = scan_qpc[1] + 64'd200000;
        check(scan_qpc[0] == ORIGIN64 + 64'd100007, "scan0 QPC vector");
        check(scan_qpc[1] == ORIGIN64 + 64'd300007, "scan1 QPC vector");
        check(scan_qpc[2] == ORIGIN64 + 64'd500007, "scan2 QPC vector");
        check((scan_qpc[0] - ORIGIN64) % 64'd1000 == 64'd7, "scan0 QPC remainder");
        check((scan_qpc[1] - ORIGIN64) % 64'd1000 == 64'd7, "scan1 QPC remainder");
        check((scan_qpc[2] - ORIGIN64) % 64'd1000 == 64'd7, "scan2 QPC remainder");

        $fdisplay(fd_log, "START task=DEEPEYE-IMPLEMENTATION-20261014/v1 work=B-DEEPEYE-DEMO-MULTISCAN-INGRESS-20261101-147");
        $fdisplay(fd_log, "SOURCE_ONLY semantics_supplied=1 authentication=absent fresh=1 quality=0 input_only=1");
        $fdisplay(fd_log, "VECTORS session=%08x epoch=%02x base_seq=%04x origin=%0d tag=%02x",
                  SESSION, EPOCH, BASE_SEQ, ORIGIN64, TAG);
        $fdisplay(fd_log, "ORIGINAL_QPC %0d %0d %0d origin=%0d remainder_ns=7",
                  scan_qpc[0], scan_qpc[1], scan_qpc[2], ORIGIN64);

        // GOOD batch
        do_reset();
        do_arm(SESSION, EPOCH, BASE_SEQ, ORIGIN63, TAG);
        wait_armed(2000);
        // Configuration is captured by ARM. Move every live configuration
        // input after the edge; the four wire frames must still use the latched
        // owner values and the input tag association above.
        cfg_session = 32'hDEADBEEF;
        cfg_epoch = 8'hFF;
        cfg_base_frame_seq = 16'h0000;
        cfg_origin_qpc_ns = 63'd1;
        cfg_tag = 32'hBAD0BAD0;
        for (scan = 0; scan < 3; scan = scan + 1)
            for (lane = 0; lane < 4; lane = lane + 1)
                send_good_lane(scan, lane);

        check(accepted_lanes == 4'd12, "good batch accepted lane count");
        for (f = 0; f < 4; f = f + 1) begin
            wait_result(200000);
            if (result_error !== 3'd0) fail("unexpected result error");
            cap_err = result_error;
            cap_bytes = result_bytes;
            repeat (20) step(1);
            if (!result_valid || result_error !== cap_err || result_bytes !== cap_bytes)
                fail("result backpressure unstable");
            result_bytes_cap[f] = cap_bytes;
            result_error_cap[f] = cap_err;
            result_ready = 1'b1;
            step(1);
            result_ready = 1'b0;
            step(2);
        end
        wait_frames(4, 20000);
        check(frames_retired == 3'd4, "four frames retired");
        check(batch_done, "batch_done");
        repeat (20) step(1);
        check(!busy, "good batch busy low");
        check(quiescent, "good batch quiescent");
        check(!armed, "good batch armed cleared");

        repeat (6000) step(1);
        check(up_framing_count == 0, "good batch framing error");
        check(up_overrun_count == 0, "good batch RX overrun");
        check(up_false_count == 0, "good batch false start");
        check(!up_busy, "good batch RX idle");
        parse_good_frames();
        good_rx_count = rx_count;
        $fdisplay(fd_log, "GOOD_BATCH_DONE bytes=%0d frames=4 results=4", good_rx_count);

        // BAD metadata: base_frame_seq+3 wraps. No ARM success, no bytes.
        do_reset();
        do_arm(SESSION, EPOCH, 16'hFFFF, ORIGIN63, TAG);
        wait_refused(2000);
        check(refusal_code == 4'd10, "bad metadata refusal code");
        check(!armed, "bad metadata not armed");
        check(!s_ready, "bad metadata not ready");
        repeat (1000) step(1);
        check(rx_count == 0, "bad metadata zero bytes");
        check(!result_valid, "bad metadata no result");
        $fdisplay(fd_log, "BAD_METADATA_REFUSED code=%0d bytes=%0d", refusal_code, rx_count);
        cancel_pulse();

        // BAD status: a held lane is backpressured and refused, never passed
        // with an invented held=0 flag.
        do_reset();
        do_arm(SESSION, EPOCH, BASE_SEQ, ORIGIN63, TAG);
        wait_armed(2000);
        s_channel = 2'd0;
        s_data = raw[0];
        s_acq_qpc_ns = scan_qpc[0];
        s_quality = 8'd0;
        s_tag = TAG;
        s_native_first_seq = 32'd40;
        s_native_last_seq = 32'd43;
        s_semantics_valid = 1'b1;
        s_fresh = 1'b1;
        s_sample_valid = 1'b1;
        s_held = 1'b1;
        s_saturated = 1'b0;
        s_source_fault = 1'b0;
        s_valid = 1'b1;
        repeat (5) step(1);
        check(!s_ready, "held input backpressure");
        wait_refused(2000);
        check(refusal_code == 4'd13, "held input refusal code");
        check(!armed, "held input not armed");
        s_valid = 1'b0;
        step(2);
        check(rx_count == 0, "held input zero bytes");
        check(!result_valid, "held input no result");
        $fdisplay(fd_log, "BAD_STATUS_REFUSED code=%0d bytes=%0d", refusal_code, rx_count);
        cancel_pulse();

        // CANCEL: start a real frame, cancel mid-symbol, then verify no
        // successful result, no retirement and no automatic replay.
        do_reset();
        do_arm(SESSION, EPOCH, BASE_SEQ, ORIGIN63, TAG);
        wait_armed(2000);
        for (scan = 0; scan < 3; scan = scan + 1)
            for (lane = 0; lane < 4; lane = lane + 1)
                send_good_lane(scan, lane);
        check(accepted_lanes == 4'd12, "cancel batch accepted lane count");
        t = 0;
        while (tx !== 1'b0 && t < 100000) begin
            step(1);
            t = t + 1;
        end
        check(tx == 1'b0, "cancel output did not start");
        repeat (5) step(1);
        cancel = 1'b1;
        repeat (20) step(1);
        cancel = 1'b0;
        repeat (5) step(1);
        check(aborted, "cancel aborted status");
        check(abort_code == 2'd1, "cancel abort cause");
        check(frames_retired == 3'd0, "cancel no retirement");
        check(!armed, "cancel disarmed");
        check(!result_valid, "cancel no result");
        cancel_rx_count = rx_count;
        $fdisplay(fd_log, "CANCEL_PARTIAL_BYTES %0d", cancel_rx_count);
        repeat (5000) step(1);
        check(frames_retired == 3'd0, "cancel replay frames");
        check(!armed, "cancel replay armed");
        check(accepted_lanes == 4'd0, "cancel replay lanes");
        check(rx_count == cancel_rx_count, "cancel replay bytes");
        check(tx == 1'b1, "cancel replay tx idle");
        check(!result_valid, "cancel replay result");
        check(!busy, "cancel replay busy");
        wait_quiescent(10000);
        check(quiescent, "cancel replay quiescent");
        check(abort_code == 2'd1, "cancel abort cause stable");
        $fdisplay(fd_log, "CANCEL_NO_REPLAY bytes=%0d retired=%0d abort_code=1",
                  cancel_rx_count, frames_retired);

        // DISABLE: withdrawing enable must abort an accepted frame exactly like
        // cancel, but report the distinct owner action. Restoration alone does
        // not rearm or replay.
        do_reset();
        do_arm(SESSION, EPOCH, BASE_SEQ, ORIGIN63, TAG);
        wait_armed(2000);
        for (scan = 0; scan < 3; scan = scan + 1)
            for (lane = 0; lane < 4; lane = lane + 1)
                send_good_lane(scan, lane);
        check(accepted_lanes == 4'd12, "disable batch accepted lane count");
        t = 0;
        while (tx !== 1'b0 && t < 100000) begin
            step(1);
            t = t + 1;
        end
        check(tx == 1'b0, "disable output did not start");
        repeat (5) step(1);
        enable = 1'b0;
        repeat (20) step(1);
        check(aborted, "disable aborted status");
        check(abort_code == 2'd2, "disable abort cause");
        check(frames_retired == 3'd0, "disable no retirement");
        check(!armed, "disable disarmed");
        check(!result_valid, "disable no result");
        disable_rx_count = rx_count;
        enable = 1'b1;
        repeat (20) step(1);
        check(aborted, "disable abort status persists");
        check(frames_retired == 3'd0, "disable restore no retirement");
        check(!armed, "disable restore not armed");
        check(!result_valid, "disable restore no result");
        repeat (5000) step(1);
        check(frames_retired == 3'd0, "disable replay frames");
        check(!armed, "disable replay armed");
        check(accepted_lanes == 4'd0, "disable replay lanes");
        check(rx_count == disable_rx_count, "disable replay bytes");
        check(tx == 1'b1, "disable replay tx idle");
        check(!result_valid, "disable replay result");
        check(!busy, "disable replay busy");
        wait_quiescent(10000);
        check(quiescent, "disable replay quiescent");
        check(abort_code == 2'd2, "disable abort cause stable");
        $fdisplay(fd_log, "DISABLE_NO_REPLAY bytes=%0d retired=%0d abort_code=2",
                  disable_rx_count, frames_retired);

        completed = 1;
        $fdisplay(fd_log,
            "TEST_PASS good_bytes=%0d bad_meta_code=10 bad_status_code=13 cancel_bytes=%0d disable_bytes=%0d cancel_abort=1 disable_abort=2 no_replay",
            good_rx_count, cancel_rx_count, disable_rx_count);
        $display("DEMO_MULTISCAN147_TEST_PASS good_bytes=%0d cancel_bytes=%0d disable_bytes=%0d bad_meta=10 bad_status=13 abort=1/2",
                 good_rx_count, cancel_rx_count, disable_rx_count);
        $fclose(fd_bytes);
        $fclose(fd_log);
        $finish;
    end
endmodule
