`timescale 1ns/1ps

// NEW82 focused digital test. External SPI pins and public result ports only.
// A RED run is expected to fail the old 80 source at explicit arm recovery.

module tb_r04_gain82;
    logic clk = 0;
    always #5 clk = ~clk;

    logic        rst = 1;
    logic        enable = 0;
    logic        arm = 0;
    logic        cancel = 0;
    logic        overrange = 0;
    logic [31:0] reserved_safety_tag = 32'h00000099;
    logic        host_valid = 0;
    logic [2:0]  host_gain_code = 0;
    logic [31:0] host_tag = 0;
    logic        host_result_ready = 0;
    logic        safety_result_ready = 0;

    wire         host_ready;
    wire         host_result_valid;
    wire         host_result_error;
    wire [31:0]  host_result_tag;
    wire         safety_result_valid;
    wire         safety_result_error;
    wire [31:0]  safety_result_tag;
    wire         armed;
    wire         inhibit;
    wire         sticky_fault;
    wire         spi_cs_n;
    wire         spi_sck;
    wire         spi_si;

    deepeye_mcp6s21_safety_arbiter_candidate dut (.*);

    localparam [31:0] TAG_H11 = 32'h00000011;
    localparam [31:0] TAG_H12 = 32'h00000012;
    localparam [31:0] TAG_H21 = 32'h00000021;
    localparam [31:0] TAG_H22 = 32'h00000022;
    localparam [31:0] TAG_H31 = 32'h00000031;
    localparam [31:0] TAG_H44 = 32'h00000044;
    localparam [31:0] TAG_H55 = 32'h00000055;
    localparam [31:0] TAG_H66 = 32'h00000066;
    localparam [31:0] TAG_H77 = 32'h00000077;
    localparam [31:0] TAG_SAFE = 32'h00000099;
    localparam [31:0] TAG_ALT  = 32'h0000009A;
    localparam [15:0] W_4000 = 16'h4000;
    localparam [15:0] W_4001 = 16'h4001;
    localparam [15:0] W_4002 = 16'h4002;
    localparam [15:0] W_4004 = 16'h4004;

    integer fd;
    integer cycle = 0;
    integer starts = 0;
    integer frames = 0;
    integer checks = 0;
    integer failures = 0;
    integer red_mode = 0;
    integer case_id = 0;
    integer edges = 0;
    integer last_edges = 0;
    logic [15:0] observed = 0;
    logic [15:0] last_word = 0;
    bit prev_cs = 1;
    bit prev_sck = 0;
    integer completion_status = 0;

    task automatic ck(input bit okay, input string why);
        checks++;
        if (!okay) begin
            failures++;
            $fdisplay(fd, "FAIL,%0d,%s", cycle, why);
            $fflush(fd);
            $fatal(1, "R04_NEW82 %s", why);
        end
    endtask

    task automatic clocks(input integer count);
        repeat (count) @(negedge clk);
    endtask

    task automatic wait_starts(input integer target, input string why);
        integer n;
        n = 0;
        while (starts < target && n < 20000) begin
            clocks(1);
            n++;
        end
        ck(starts >= target, why);
    endtask

    task automatic wait_frames(input integer target, input string why);
        integer n;
        n = 0;
        while (frames < target && n < 20000) begin
            clocks(1);
            n++;
        end
        ck(frames >= target, why);
    endtask

    task automatic wait_host_ready(input string why);
        integer n;
        n = 0;
        while (!host_ready && n < 3000) begin
            clocks(1);
            n++;
        end
        ck(host_ready, why);
    endtask

    task automatic send_host(input [31:0] tag, input [2:0] gain, input string why);
        host_tag = tag;
        host_gain_code = gain;
        wait_host_ready(why);
        host_valid = 1;
        $fdisplay(fd, "HOST_DRIVE,%0d,%0d,%0d", case_id, cycle, tag);
        clocks(1);
        host_valid = 0;
        clocks(1);
    endtask

    task automatic wait_host_result(input bit want_error, input [31:0] want_tag, input string why);
        integer n;
        n = 0;
        while (!host_result_valid && n < 7000) begin
            clocks(1);
            n++;
        end
        ck(host_result_valid, why);
        ck(host_result_error == want_error && host_result_tag == want_tag, why);
        $fdisplay(fd, "HOST_RESULT,%0d,%0d,%0d,%0d", case_id, cycle, host_result_error, host_result_tag);
    endtask

    task automatic wait_safety_result(input bit want_error, input [31:0] want_tag, input string why);
        integer n;
        n = 0;
        while (!safety_result_valid && n < 7000) begin
            clocks(1);
            n++;
        end
        ck(safety_result_valid, why);
        ck(safety_result_error == want_error && safety_result_tag == want_tag, why);
        $fdisplay(fd, "SAFETY_RESULT,%0d,%0d,%0d,%0d", case_id, cycle, safety_result_error, safety_result_tag);
    endtask

    task automatic drain_host;
        host_result_ready = 1;
        clocks(1);
        host_result_ready = 0;
        clocks(1);
        ck(!host_result_valid, "host result drained");
    endtask

    task automatic drain_safety;
        safety_result_ready = 1;
        clocks(1);
        safety_result_ready = 0;
        clocks(1);
        ck(!safety_result_valid, "safety result drained");
    endtask

    task automatic check_complete_frame(
        input integer start_base,
        input integer frame_base,
        input [15:0] expected_word,
        input string why
    );
        wait_starts(start_base + 1, why);
        wait_frames(frame_base + 1, why);
        ck(starts == start_base + 1, why);
        ck(frames == frame_base + 1, why);
        ck(last_edges == 16, why);
        ck(last_word == expected_word, why);
        $fdisplay(fd, "WORD,%0d,%0d,%04x", case_id, cycle, last_word);
    endtask

    task automatic check_partial_frame(
        input integer start_base,
        input integer frame_base,
        input integer min_edges,
        input string why
    );
        wait_starts(start_base + 1, why);
        wait_frames(frame_base + 1, why);
        ck(starts == start_base + 1, why);
        ck(frames == frame_base + 1, why);
        ck(last_edges >= min_edges && last_edges < 16, why);
        $fdisplay(fd, "PARTIAL,%0d,%0d,%0d", case_id, cycle, last_edges);
    endtask

    task automatic reset_all;
        rst = 1;
        enable = 0;
        arm = 0;
        cancel = 0;
        overrange = 0;
        reserved_safety_tag = TAG_SAFE;
        host_valid = 0;
        host_gain_code = 0;
        host_tag = 0;
        host_result_ready = 0;
        safety_result_ready = 0;
        clocks(5);
        rst = 0;
        enable = 1;
        clocks(250);
        ck(!armed && !inhibit && !sticky_fault, "reset context clear");
        ck(!host_result_valid && !safety_result_valid, "reset result slots clear");
        ck(spi_cs_n && !spi_sck && !spi_si, "reset SPI pins safe");
    endtask

    task automatic arm_safe;
        arm = 0;
        clocks(2);
        ck(!host_valid, "safe arm requires host_valid low");
        arm = 1;
        clocks(1);
        arm = 0;
        clocks(4);
        ck(armed && !inhibit && !sticky_fault, "safe initial arm");
        ck(!host_result_valid && !safety_result_valid, "arm result slots drained");
    endtask

    task automatic arm_pulse;
        arm = 0;
        clocks(2);
        arm = 1;
        clocks(1);
        arm = 0;
        clocks(2);
    endtask

    always @(posedge clk) begin
        #1;
        cycle++;
        if (fd) begin
            if (prev_cs && !spi_cs_n) begin
                starts++;
                ck(!spi_sck, "SCK high at CS fall");
                edges = 0;
                observed = 0;
                $fdisplay(fd, "CS_LOW,%0d,%0d", case_id, cycle);
            end
            if (!prev_sck && spi_sck) begin
                ck(!spi_cs_n, "SCK rise outside CS");
                observed = {observed[14:0], spi_si};
                edges++;
                $fdisplay(fd, "RISE,%0d,%0d,%0d,%0d", case_id, cycle, edges, spi_si);
            end
            if (!prev_cs && spi_cs_n) begin
                frames++;
                last_edges = edges;
                last_word = observed;
                $fdisplay(fd, "FRAME,%0d,%0d,%0d,%04x", case_id, cycle, last_edges, last_word);
            end
            prev_cs = spi_cs_n;
            prev_sck = spi_sck;
            if (cycle > 180000)
                $fatal(1, "R04_NEW82 cycle deadline");
        end
    end

    task automatic case_recovery(input integer expect_red);
        integer s0, f0;
        case_id = 1;
        $fdisplay(fd, "CASE_BEGIN,%0d,recovery,expect_red=%0d", case_id, expect_red);
        reset_all();
        arm_safe();

        s0 = starts;
        f0 = frames;
        send_host(TAG_H11, 3'd4, "recovery host ready");
        check_complete_frame(s0, f0, W_4004, "host word 4004");
        wait_host_result(0, TAG_H11, "normal host result tag 11");

        repeat (20) clocks(1);
        ck(host_result_valid && !host_result_error && host_result_tag == TAG_H11,
           "host result held stable");
        ck(!host_ready, "held host result blocks host ready");
        host_valid = 1;
        host_tag = TAG_H12;
        host_gain_code = 3'd1;
        clocks(1);
        ck(!host_ready, "held host result blocks new handshake");
        host_valid = 0;
        clocks(1);

        s0 = starts;
        f0 = frames;
        overrange = 1;
        wait_safety_result(0, TAG_SAFE, "fallback result tag 99");
        check_complete_frame(s0, f0, W_4000, "fallback word 4000 despite host backpressure");
        ck(host_result_valid && !host_result_error && host_result_tag == TAG_H11,
           "host held slot preserved through fallback");
        repeat (400) clocks(1);
        ck(starts == s0 + 1 && frames == f0 + 1, "one fallback under sustained overrange");

        drain_host();
        drain_safety();
        overrange = 0;
        repeat (260) clocks(1);
        arm_pulse();

        if (expect_red) begin
            if (armed && inhibit && !sticky_fault && starts == s0 + 1 && frames == f0 + 1) begin
                $fdisplay(fd, "RED_CONFIRMED,%0d,%0d,%0d", cycle, starts, frames);
                completion_status = 2;
                $display("R04_NEW82_RED_CONFIRMED cycles=%0d", cycle);
                $fclose(fd);
                fd = 0;
                $finish;
            end else begin
                ck(1'b0, "RED did not reproduce expected old-source recovery failure");
            end
        end else begin
            ck(armed && !inhibit && !sticky_fault, "explicit arm recovers inhibit");
            ck(starts == s0 + 1 && frames == f0 + 1, "recovery arm issued no SPI");
        end
        $fdisplay(fd, "CASE_END,%0d,recovery", case_id);
    endtask

    task automatic case_master_guard;
        integer s0, f0;
        case_id = 2;
        $fdisplay(fd, "CASE_BEGIN,%0d,master_guard", case_id);
        reset_all();
        arm_safe();

        s0 = starts;
        f0 = frames;
        overrange = 1;
        wait_safety_result(0, TAG_SAFE, "guard fallback tag 99");
        check_complete_frame(s0, f0, W_4000, "guard fallback word 4000");
        overrange = 0;
        drain_safety();
        ck(!host_result_valid && !safety_result_valid, "guard both slots drained");

        arm_pulse();
        clocks(3);
        ck(inhibit && armed && starts == s0 + 1 && frames == f0 + 1,
           "arm blocked until master idle");

        repeat (200) clocks(1);
        ck(inhibit && armed && !host_ready && starts == s0 + 1 && frames == f0 + 1,
           "master idle does not auto arm");

        arm_pulse();
        ck(armed && !inhibit && !sticky_fault, "explicit arm after master idle");
        ck(starts == s0 + 1 && frames == f0 + 1, "master guard arm issued no SPI");
        $fdisplay(fd, "CASE_END,%0d,master_guard", case_id);
    endtask

    task automatic case_release_boundaries;
        integer s0, f0;
        case_id = 3;
        $fdisplay(fd, "CASE_BEGIN,%0d,release_boundaries", case_id);
        reset_all();
        arm_safe();

        s0 = starts;
        f0 = frames;
        send_host(TAG_H21, 3'd2, "release host ready");
        check_complete_frame(s0, f0, W_4002, "host word 4002");
        wait_host_result(0, TAG_H21, "release host result tag 21");

        s0 = starts;
        f0 = frames;
        overrange = 1;
        wait_safety_result(0, TAG_SAFE, "release fallback tag 99");
        check_complete_frame(s0, f0, W_4000, "release fallback word 4000");
        repeat (500) clocks(1);
        ck(starts == s0 + 1 && frames == f0 + 1, "sustained overrange one fallback");

        overrange = 0;
        repeat (200) clocks(1);
        ck(inhibit && armed && starts == s0 + 1 && frames == f0 + 1 && !host_ready,
           "release does not auto recover");

        arm_pulse();
        clocks(3);
        ck(inhibit && armed && starts == s0 + 1, "arm blocked by full slots");
        drain_host();
        arm_pulse();
        clocks(3);
        ck(inhibit && armed && starts == s0 + 1, "arm blocked by safety slot");
        drain_safety();
        overrange = 1;

        arm_pulse();
        clocks(3);
        ck(inhibit && armed && starts == s0 + 1, "arm blocked by asserted overrange");
        ck(!host_ready, "host remains blocked while inhibit");

        overrange = 0;
        repeat (200) clocks(1);
        ck(inhibit && armed && starts == s0 + 1 && !host_ready,
           "release after drains does not auto arm");

        host_valid = 1;
        host_tag = TAG_H55;
        host_gain_code = 3'd1;
        clocks(2);
        ck(!host_ready, "host blocked before safe recovery");
        arm_pulse();
        ck(armed && !inhibit && !sticky_fault, "held host valid does not block explicit recovery");
        repeat (20) clocks(1);
        ck(!host_ready && starts == s0 + 1 && frames == f0 + 1,
           "old held host valid not replayed after arm");

        host_valid = 0;
        clocks(3);
        s0 = starts;
        f0 = frames;
        send_host(TAG_H31, 3'd1, "fresh host after recovery");
        check_complete_frame(s0, f0, W_4001, "fresh host word 4001");
        wait_host_result(0, TAG_H31, "fresh host result tag 31");
        $fdisplay(fd, "CASE_END,%0d,release_boundaries", case_id);
    endtask

    task automatic case_host_cancel_7edges;
        integer s0, f0, s1, f1, n;
        case_id = 4;
        $fdisplay(fd, "CASE_BEGIN,%0d,host_cancel_7edges", case_id);
        reset_all();
        arm_safe();
        s0 = starts;
        f0 = frames;
        send_host(TAG_H22, 3'd2, "cancel host ready");
        n = 0;
        while (edges < 7 && n < 6000) begin
            clocks(1);
            n++;
        end
        ck(edges >= 7 && !spi_cs_n && starts == s0 + 1, "host reaches seven native edges");
        overrange = 1;
        clocks(1);
        wait_host_result(1, TAG_H22, "host cancel keeps original tag/error");
        check_partial_frame(s0, f0, 7, "host frame aborted before sixteen edges");
        ck(host_result_valid && host_result_error && host_result_tag == TAG_H22,
           "host cancel terminal retained");

        s1 = starts;
        f1 = frames;
        wait_safety_result(0, TAG_SAFE, "post-cancel fallback tag 99");
        check_complete_frame(s1, f1, W_4000, "post-cancel fallback word 4000");
        ck(host_result_valid && host_result_error && host_result_tag == TAG_H22,
           "host abort slot preserved through fallback");
        repeat (400) clocks(1);
        ck(starts == s1 + 1 && frames == f1 + 1, "post-cancel one fallback only");
        $fdisplay(fd, "CASE_END,%0d,host_cancel_7edges", case_id);
    endtask

    task automatic case_fallback_cancel_disable;
        integer s0, f0, n;
        case_id = 5;
        $fdisplay(fd, "CASE_BEGIN,%0d,fallback_cancel_disable", case_id);
        reset_all();
        arm_safe();
        s0 = starts;
        f0 = frames;
        overrange = 1;
        n = 0;
        while ((spi_cs_n || edges < 3) && n < 6000) begin
            clocks(1);
            n++;
        end
        ck(!spi_cs_n && edges >= 3 && starts == s0 + 1, "fallback active before cancel");
        cancel = 1;
        clocks(1);
        wait_safety_result(1, TAG_SAFE, "canceled fallback error tag 99");
        check_partial_frame(s0, f0, 3, "fallback canceled before sixteen edges");
        cancel = 0;
        repeat (500) clocks(1);
        ck(starts == s0 + 1 && frames == f0 + 1 && spi_cs_n,
           "canceled fallback not retried");
        ck(inhibit && !armed, "cancel closes arm and keeps inhibit");

        reset_all();
        arm_safe();
        s0 = starts;
        f0 = frames;
        overrange = 1;
        n = 0;
        while ((spi_cs_n || edges < 3) && n < 6000) begin
            clocks(1);
            n++;
        end
        ck(!spi_cs_n && edges >= 3 && starts == s0 + 1, "fallback active before disable");
        enable = 0;
        clocks(1);
        wait_safety_result(1, TAG_SAFE, "disabled fallback error tag 99");
        check_partial_frame(s0, f0, 3, "fallback disabled before sixteen edges");
        enable = 1;
        repeat (500) clocks(1);
        ck(starts == s0 + 1 && frames == f0 + 1 && spi_cs_n,
           "disabled fallback not retried");
        ck(inhibit && !armed, "disable closes arm and keeps inhibit");
        $fdisplay(fd, "CASE_END,%0d,fallback_cancel_disable", case_id);
    endtask

    task automatic case_same_cycle_overrange;
        integer s0, f0;
        case_id = 6;
        $fdisplay(fd, "CASE_BEGIN,%0d,same_cycle_overrange", case_id);
        reset_all();
        arm_safe();
        host_valid = 0;
        clocks(3);
        s0 = starts;
        f0 = frames;
        host_valid = 1;
        host_tag = TAG_H44;
        host_gain_code = 3'd1;
        overrange = 1;
        ck(!host_ready, "same-cycle overrange blocks host handshake");
        clocks(1);
        host_valid = 0;
        clocks(1);
        ck(!host_result_valid, "blocked same-cycle host has no result");
        wait_safety_result(0, TAG_SAFE, "same-cycle fallback tag 99");
        check_complete_frame(s0, f0, W_4000, "same-cycle fallback word 4000");
        ck(starts == s0 + 1 && frames == f0 + 1, "same-cycle host emitted no frame");
        $fdisplay(fd, "CASE_END,%0d,same_cycle_overrange", case_id);
    endtask

    task automatic case_tag_faults;
        integer s0;
        case_id = 7;
        $fdisplay(fd, "CASE_BEGIN,%0d,tag_faults", case_id);

        reset_all();
        reserved_safety_tag = 32'd0;
        clocks(2);
        s0 = starts;
        arm = 1;
        clocks(1);
        arm = 0;
        clocks(3);
        ck(sticky_fault && inhibit && !armed, "zero safety tag faults");
        host_valid = 1;
        host_tag = TAG_H44;
        host_gain_code = 3'd1;
        clocks(3);
        ck(!host_ready, "zero safety tag blocks host");
        host_valid = 0;
        repeat (200) clocks(1);
        ck(starts == s0 && spi_cs_n, "zero safety tag emits no SPI");

        reset_all();
        arm_safe();
        s0 = starts;
        host_valid = 1;
        host_tag = 32'd0;
        host_gain_code = 3'd1;
        clocks(1);
        ck(!host_ready, "zero host tag immediately refused");
        clocks(2);
        ck(sticky_fault && inhibit && !armed, "zero host tag faults");
        host_valid = 0;
        repeat (200) clocks(1);
        ck(starts == s0 && spi_cs_n, "zero host tag emits no SPI");

        reset_all();
        arm_safe();
        s0 = starts;
        host_valid = 1;
        host_tag = TAG_SAFE;
        host_gain_code = 3'd1;
        clocks(1);
        ck(!host_ready, "colliding host tag immediately refused");
        clocks(2);
        ck(sticky_fault && inhibit && !armed, "colliding host tag faults");
        host_valid = 0;
        repeat (200) clocks(1);
        ck(starts == s0 && spi_cs_n, "colliding host tag emits no SPI");

        reset_all();
        arm_safe();
        s0 = starts;
        reserved_safety_tag = TAG_ALT;
        clocks(2);
        ck(sticky_fault && inhibit && !armed, "changed safety tag faults");
        host_valid = 1;
        host_tag = TAG_H55;
        host_gain_code = 3'd1;
        clocks(2);
        ck(!host_ready, "changed safety tag blocks host");
        host_valid = 0;
        repeat (200) clocks(1);
        ck(starts == s0 && spi_cs_n, "changed safety tag emits no SPI");
        $fdisplay(fd, "CASE_END,%0d,tag_faults", case_id);
    endtask

    task automatic case_reset_destructive;
        integer s0, f0, s1, f1, n;
        case_id = 8;
        $fdisplay(fd, "CASE_BEGIN,%0d,reset_destructive", case_id);
        reset_all();
        arm_safe();
        s0 = starts;
        f0 = frames;
        send_host(TAG_H66, 3'd4, "reset host ready");
        n = 0;
        while (edges < 5 && n < 6000) begin
            clocks(1);
            n++;
        end
        ck(edges >= 5 && !spi_cs_n && starts == s0 + 1, "reset host frame active");
        rst = 1;
        clocks(3);
        ck(spi_cs_n && !spi_sck && !spi_si, "reset forces safe SPI pins");
        ck(!host_result_valid && !safety_result_valid, "reset destroys both result slots");
        ck(!armed && !inhibit && !sticky_fault && !host_ready, "reset returns unarmed");
        rst = 0;
        enable = 1;
        host_valid = 1;
        host_tag = TAG_H77;
        host_gain_code = 3'd1;
        clocks(2);
        s1 = starts;
        f1 = frames;
        repeat (300) clocks(1);
        ck(starts == s1 && frames == f1, "reset does not replay host");
        ck(!host_result_valid && !safety_result_valid && !armed && !host_ready,
           "post-reset context remains unavailable");
        host_valid = 0;

        reset_all();
        arm_safe();
        s0 = starts;
        f0 = frames;
        send_host(TAG_H66, 3'd4, "held-slot reset host ready");
        check_complete_frame(s0, f0, W_4004, "held-slot reset host word 4004");
        wait_host_result(0, TAG_H66, "held-slot reset host result tag 66");
        s0 = starts;
        f0 = frames;
        overrange = 1;
        wait_safety_result(0, TAG_SAFE, "held-slot reset fallback tag 99");
        check_complete_frame(s0, f0, W_4000, "held-slot reset fallback word 4000");
        ck(host_result_valid && safety_result_valid, "both result slots held before reset");

        rst = 1;
        clocks(3);
        ck(spi_cs_n && !spi_sck && !spi_si, "held-slot reset safe SPI pins");
        ck(!host_result_valid && !safety_result_valid, "reset destroys both held slots");
        ck(!armed && !inhibit && !sticky_fault && !host_ready, "held-slot reset unarmed");
        overrange = 0;
        rst = 0;
        enable = 1;
        clocks(250);
        ck(!armed && !inhibit && !sticky_fault && !host_ready,
           "held-slot reset has no automatic recovery");
        ck(!host_result_valid && !safety_result_valid, "held-slot reset leaves no ACK");
        $fdisplay(fd, "CASE_END,%0d,reset_destructive", case_id);
    endtask

    string out;
    integer found;
    initial begin
        if (!$value$plusargs("OUT=%s", out))
            $fatal(1, "OUT required");
        red_mode = 0;
        found = $value$plusargs("RED=%d", red_mode);
        fd = $fopen(out, "w");
        if (!fd)
            $fatal(1, "cannot open OUT");
        $fdisplay(fd, "HEADER,task=DEEPEYE-IMPLEMENTATION-20261014/v1,work=B-R04-OVERRANGE-FUNCTIONAL-20261030-82,red=%0d", red_mode);
        $fdisplay(fd, "CONTRACT,H01-H15,c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804");
        $fdisplay(fd, "EXTERNAL_ONLY,SPI_CS_SCK_SI_AND_PUBLIC_RESULTS");

        case_recovery(red_mode);
        if (red_mode)
            $fatal(1, "RED mode returned without terminal classification");

        case_master_guard();
        case_release_boundaries();
        case_host_cancel_7edges();
        case_fallback_cancel_disable();
        case_same_cycle_overrange();
        case_tag_faults();
        case_reset_destructive();

        completion_status = 1;
        $fdisplay(fd, "GREEN_DONE,%0d,%0d,%0d,%0d", cycle, starts, frames, checks);
        $display("R04_NEW82_GREEN_PASS cycles=%0d checks=%0d", cycle, checks);
        $fclose(fd);
        fd = 0;
        $finish;
    end

    initial begin
        #2000000;
        $fatal(1, "R04_NEW82 wall simulation bound");
    end
endmodule
