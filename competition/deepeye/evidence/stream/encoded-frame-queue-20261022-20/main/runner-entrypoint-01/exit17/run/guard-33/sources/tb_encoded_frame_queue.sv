// Directed public-port testbenches for deepeye_encoded_frame_queue.
//
// Work: B-ENCODED-FRAME-QUEUE-RTL-20261022-20-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-ENCODED-FRAME-QUEUE-20261022-20
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// The guard bench below is compiled with +define+GUARD_W=<0|1|33>.  It exists
// only to reach the module's own simulation-time parameter fatal; it is not a
// product test and prints no PASS claim.

module tb_encoded_frame_queue;
    localparam integer STAT_W = 32;
    localparam integer MAX_FRAMES = 64;
    localparam integer WAIT_LIMIT = 200000;

    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic rst = 1'b1;
    logic cancel = 1'b0;

    logic        in_meta_valid = 1'b0;
    logic        in_meta_ready;
    logic [15:0] in_meta_tag = 16'd0;
    logic [1:0]  in_meta_error = 2'd0;
    logic [7:0]  in_meta_count = 8'd0;
    logic [3:0]  in_meta_e = 4'd0;
    logic        in_meta_raw = 1'b0;
    logic [3:0]  in_meta_k = 4'd0;
    logic [11:0] in_meta_valid_bits = 12'd0;
    logic [8:0]  in_meta_bytes = 9'd0;

    logic       in_valid = 1'b0;
    logic       in_ready;
    logic [7:0] in_data = 8'd0;
    logic       in_last = 1'b0;

    logic        out_meta_valid;
    logic        out_meta_ready = 1'b0;
    logic [15:0] out_meta_tag;
    logic [1:0]  out_meta_error;
    logic [7:0]  out_meta_count;
    logic [3:0]  out_meta_e;
    logic        out_meta_raw;
    logic [3:0]  out_meta_k;
    logic [11:0] out_meta_valid_bits;
    logic [8:0]  out_meta_bytes;

    logic       out_valid;
    logic       out_ready = 1'b0;
    logic [7:0] out_data;
    logic       out_last;

    logic [1:0] level;
    logic       receiving;
    logic       faulted;
    logic       fault_event;
    logic [1:0] fault_code;
    logic [31:0] stat_meta;
    logic [31:0] stat_in_bytes;
    logic [31:0] stat_retired;
    logic [31:0] stat_aborted;
    logic [31:0] stat_fault;

    deepeye_encoded_frame_queue #(
        .STAT_W(STAT_W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .in_meta_valid(in_meta_valid),
        .in_meta_ready(in_meta_ready),
        .in_meta_tag(in_meta_tag),
        .in_meta_error(in_meta_error),
        .in_meta_count(in_meta_count),
        .in_meta_e(in_meta_e),
        .in_meta_raw(in_meta_raw),
        .in_meta_k(in_meta_k),
        .in_meta_valid_bits(in_meta_valid_bits),
        .in_meta_bytes(in_meta_bytes),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_data(in_data),
        .in_last(in_last),
        .out_meta_valid(out_meta_valid),
        .out_meta_ready(out_meta_ready),
        .out_meta_tag(out_meta_tag),
        .out_meta_error(out_meta_error),
        .out_meta_count(out_meta_count),
        .out_meta_e(out_meta_e),
        .out_meta_raw(out_meta_raw),
        .out_meta_k(out_meta_k),
        .out_meta_valid_bits(out_meta_valid_bits),
        .out_meta_bytes(out_meta_bytes),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_data(out_data),
        .out_last(out_last),
        .level(level),
        .receiving(receiving),
        .faulted(faulted),
        .fault_event(fault_event),
        .fault_code(fault_code),
        .stat_meta(stat_meta),
        .stat_in_bytes(stat_in_bytes),
        .stat_retired(stat_retired),
        .stat_aborted(stat_aborted),
        .stat_fault(stat_fault)
    );

    int checks = 0;
    int failures = 0;
    int cases = 0;
    int pass_cases = 0;
    string current_case = "";
    bit case_failed = 1'b0;
    int case_checks = 0;

    logic [15:0] exp_tag [0:MAX_FRAMES-1];
    logic [1:0]  exp_error [0:MAX_FRAMES-1];
    logic [7:0]  exp_count [0:MAX_FRAMES-1];
    logic [3:0]  exp_e [0:MAX_FRAMES-1];
    logic        exp_raw [0:MAX_FRAMES-1];
    logic [3:0]  exp_k [0:MAX_FRAMES-1];
    logic [11:0] exp_valid_bits [0:MAX_FRAMES-1];
    logic [8:0]  exp_bytes [0:MAX_FRAMES-1];
    logic [7:0]  exp_data [0:MAX_FRAMES-1][0:255];
    int exp_head = 0;
    int exp_tail = 0;
    int wrap_expected_bytes = 0;

    bit accepted = 1'b0;
    bit byte_ok = 1'b0;
    bit pre_in_ready = 1'b0;
    bit pre_meta = 1'b0;
    bit pre_out = 1'b0;

    logic [15:0] pend_tag = 16'd0;
    logic [1:0]  pend_error = 2'd0;
    logic [7:0]  pend_count = 8'd0;
    logic [3:0]  pend_e = 4'd0;
    logic        pend_raw = 1'b0;
    logic [3:0]  pend_k = 4'd0;
    logic [11:0] pend_valid_bits = 12'd0;
    logic [8:0]  pend_bytes = 9'd0;
    logic [7:0]  pend_data [0:255];
    int pend_index = 0;
    bit pend_active = 1'b0;

    task automatic check(input bit condition, input string message);
        checks = checks + 1;
        case_checks = case_checks + 1;
        if (!condition) begin
            failures = failures + 1;
            case_failed = 1'b1;
            $display("TB_CHECK_FAIL case=%s msg=%s time=%0t", current_case, message, $time);
        end
    endtask

    task automatic check_val(input logic [63:0] actual,
                             input logic [63:0] expected,
                             input string message);
        checks = checks + 1;
        case_checks = case_checks + 1;
        if (actual !== expected) begin
            failures = failures + 1;
            case_failed = 1'b1;
            $display("TB_CHECK_FAIL case=%s msg=%s actual=%0d expected=%0d time=%0t",
                     current_case, message, actual, expected, $time);
        end
    endtask

    task automatic case_begin(input string name);
        current_case = name;
        case_failed = 1'b0;
        case_checks = 0;
        cases = cases + 1;
        $display("CASE_BEGIN name=%s", name);
    endtask

    task automatic case_end();
        if (!case_failed && (case_checks > 0)) begin
            pass_cases = pass_cases + 1;
            $display("CASE_END name=%s status=pass checks=%0d", current_case, case_checks);
        end else begin
            $display("CASE_END name=%s status=fail checks=%0d", current_case, case_checks);
        end
    endtask

    task automatic do_reset(input integer cycles);
        @(negedge clk);
        rst = 1'b1;
        cancel = 1'b0;
        in_meta_valid = 1'b0;
        in_valid = 1'b0;
        out_meta_ready = 1'b0;
        out_ready = 1'b0;
        #1;
        check_val(in_meta_ready, 0, "rst gates in_meta_ready");
        check_val(in_ready, 0, "rst gates in_ready");
        check_val(out_meta_valid, 0, "rst gates out_meta_valid");
        check_val(out_valid, 0, "rst gates out_valid");
        repeat (cycles) @(posedge clk);
        #1;
        exp_head = 0;
        exp_tail = 0;
        pend_active = 1'b0;
        check_val(level, 0, "reset level");
        check_val(receiving, 0, "reset receiving");
        check_val(faulted, 0, "reset faulted");
        check_val(fault_event, 0, "reset fault_event");
        check_val(fault_code, 0, "reset fault_code");
        check_val(stat_meta, 0, "reset stat_meta");
        check_val(stat_in_bytes, 0, "reset stat_in_bytes");
        check_val(stat_retired, 0, "reset stat_retired");
        check_val(stat_aborted, 0, "reset stat_aborted");
        check_val(stat_fault, 0, "reset stat_fault");
        check_val(out_meta_valid, 0, "reset out_meta_valid");
        check_val(out_valid, 0, "reset out_valid");
        @(negedge clk);
        rst = 1'b0;
        #1;
        check_val(in_meta_ready, 1, "in_meta_ready after reset");
        check_val(in_ready, 0, "in_ready after reset");
    endtask

    task automatic drive_meta(input logic [15:0] tag,
                              input logic [1:0] error,
                              input logic [7:0] count,
                              input logic [3:0] e,
                              input logic raw,
                              input logic [3:0] k,
                              input logic [11:0] valid_bits,
                              input logic [8:0] bytes,
                              output bit accepted);
        @(negedge clk);
        in_meta_valid = 1'b1;
        in_meta_tag = tag;
        in_meta_error = error;
        in_meta_count = count;
        in_meta_e = e;
        in_meta_raw = raw;
        in_meta_k = k;
        in_meta_valid_bits = valid_bits;
        in_meta_bytes = bytes;
        #1;
        accepted = (in_meta_ready === 1'b1);
        @(posedge clk);
        #1;
        in_meta_valid = 1'b0;
        in_meta_tag = 16'd0;
        in_meta_error = 2'd0;
        in_meta_count = 8'd0;
        in_meta_e = 4'd0;
        in_meta_raw = 1'b0;
        in_meta_k = 4'd0;
        in_meta_valid_bits = 12'd0;
        in_meta_bytes = 9'd0;
    endtask

    task automatic drive_byte(input logic [7:0] data,
                              input logic last,
                              output bit accepted);
        @(negedge clk);
        in_valid = 1'b1;
        in_data = data;
        in_last = last;
        #1;
        accepted = (in_ready === 1'b1);
        @(posedge clk);
        #1;
        in_valid = 1'b0;
        in_data = 8'd0;
        in_last = 1'b0;
    endtask

    task automatic drive_meta_observe(input logic [15:0] tag,
                                      input logic [1:0] error,
                                      input logic [7:0] count,
                                      input logic [3:0] e,
                                      input logic raw,
                                      input logic [3:0] k,
                                      input logic [11:0] valid_bits,
                                      input logic [8:0] bytes,
                                      output bit accepted,
                                      output bit pre_in_ready,
                                      output bit pre_out_meta_valid,
                                      output bit pre_out_valid);
        @(negedge clk);
        in_meta_valid = 1'b1;
        in_meta_tag = tag;
        in_meta_error = error;
        in_meta_count = count;
        in_meta_e = e;
        in_meta_raw = raw;
        in_meta_k = k;
        in_meta_valid_bits = valid_bits;
        in_meta_bytes = bytes;
        #1;
        accepted = (in_meta_ready === 1'b1);
        pre_in_ready = (in_ready === 1'b1);
        pre_out_meta_valid = (out_meta_valid === 1'b1);
        pre_out_valid = (out_valid === 1'b1);
        @(posedge clk);
        #1;
        in_meta_valid = 1'b0;
        in_meta_tag = 16'd0;
        in_meta_error = 2'd0;
        in_meta_count = 8'd0;
        in_meta_e = 4'd0;
        in_meta_raw = 1'b0;
        in_meta_k = 4'd0;
        in_meta_valid_bits = 12'd0;
        in_meta_bytes = 9'd0;
    endtask

    task automatic drive_byte_observe(input logic [7:0] data,
                                      input logic last,
                                      output bit accepted,
                                      output bit pre_out_meta_valid,
                                      output bit pre_out_valid);
        @(negedge clk);
        in_valid = 1'b1;
        in_data = data;
        in_last = last;
        #1;
        accepted = (in_ready === 1'b1);
        pre_out_meta_valid = (out_meta_valid === 1'b1);
        pre_out_valid = (out_valid === 1'b1);
        @(posedge clk);
        #1;
        in_valid = 1'b0;
        in_data = 8'd0;
        in_last = 1'b0;
    endtask

    task automatic push_error(input logic [15:0] tag,
                              input logic [1:0] error,
                              input logic [7:0] count,
                              input logic [3:0] e,
                              input logic raw,
                              input logic [3:0] k,
                              input logic [11:0] valid_bits,
                              input logic [8:0] bytes);
        check(exp_tail < MAX_FRAMES, "expected queue capacity");
        exp_tag[exp_tail] = tag;
        exp_error[exp_tail] = error;
        exp_count[exp_tail] = count;
        exp_e[exp_tail] = e;
        exp_raw[exp_tail] = raw;
        exp_k[exp_tail] = k;
        exp_valid_bits[exp_tail] = valid_bits;
        exp_bytes[exp_tail] = bytes;
        exp_tail = exp_tail + 1;
    endtask

    task automatic begin_pending(input logic [15:0] tag,
                                 input logic [7:0] count,
                                 input logic [3:0] e,
                                 input logic raw,
                                 input logic [3:0] k,
                                 input logic [11:0] valid_bits,
                                 input logic [8:0] bytes);
        pend_tag = tag;
        pend_error = 2'd0;
        pend_count = count;
        pend_e = e;
        pend_raw = raw;
        pend_k = k;
        pend_valid_bits = valid_bits;
        pend_bytes = bytes;
        pend_index = 0;
        pend_active = 1'b1;
    endtask

    task automatic pending_byte(input logic [7:0] data);
        check(pend_active && (pend_index < 256), "pending byte capacity");
        pend_data[pend_index] = data;
        pend_index = pend_index + 1;
    endtask

    task automatic commit_pending();
        integer i;
        check(exp_tail < MAX_FRAMES, "expected queue capacity");
        exp_tag[exp_tail] = pend_tag;
        exp_error[exp_tail] = 2'd0;
        exp_count[exp_tail] = pend_count;
        exp_e[exp_tail] = pend_e;
        exp_raw[exp_tail] = pend_raw;
        exp_k[exp_tail] = pend_k;
        exp_valid_bits[exp_tail] = pend_valid_bits;
        exp_bytes[exp_tail] = pend_bytes;
        for (i = 0; i < 256; i = i + 1) begin
            exp_data[exp_tail][i] = pend_data[i];
        end
        exp_tail = exp_tail + 1;
        pend_active = 1'b0;
    endtask

    task automatic wait_meta();
        integer guard;
        guard = 0;
        @(negedge clk);
        #1;
        while ((out_meta_valid !== 1'b1) && (guard < WAIT_LIMIT)) begin
            @(negedge clk);
            #1;
            guard = guard + 1;
        end
        check_val(out_meta_valid, 1, "out_meta_valid wait");
    endtask

    task automatic check_meta_expected();
        if (exp_head >= exp_tail) begin
            check(1'b0, "unexpected out_meta transaction");
        end else begin
            check_val(out_meta_tag, exp_tag[exp_head], "out_meta_tag");
            check_val(out_meta_error, exp_error[exp_head], "out_meta_error");
            check_val(out_meta_count, exp_count[exp_head], "out_meta_count");
            check_val(out_meta_e, exp_e[exp_head], "out_meta_e");
            check_val(out_meta_raw, exp_raw[exp_head], "out_meta_raw");
            check_val(out_meta_k, exp_k[exp_head], "out_meta_k");
            check_val(out_meta_valid_bits, exp_valid_bits[exp_head], "out_meta_valid_bits");
            check_val(out_meta_bytes, exp_bytes[exp_head], "out_meta_bytes");
        end
    endtask

    task automatic handshake_meta(input integer stall_cycles);
        integer i;
        check_val(out_meta_valid, 1, "meta valid at handshake point");
        check_meta_expected();
        for (i = 0; i < stall_cycles; i = i + 1) begin
            @(negedge clk);
            #1;
            check_val(out_meta_valid, 1, "meta valid stable during stall");
            check_meta_expected();
        end
        out_meta_ready = 1'b1;
        @(posedge clk);
        #1;
        out_meta_ready = 1'b0;
    endtask

    task automatic wait_payload();
        integer guard;
        guard = 0;
        @(negedge clk);
        #1;
        while ((out_valid !== 1'b1) && (guard < WAIT_LIMIT)) begin
            @(negedge clk);
            #1;
            guard = guard + 1;
        end
        check_val(out_valid, 1, "out_valid wait");
        check_val(out_meta_valid, 0, "out_meta_valid low during payload");
    endtask

    task automatic drain_payload(input integer stall_cycles);
        integer i;
        integer j;
        for (i = 0; i < exp_bytes[exp_head]; i = i + 1) begin
            wait_payload();
            check_val(out_data, exp_data[exp_head][i], "out_data");
            check_val(out_last, (i == (exp_bytes[exp_head] - 1)), "out_last");
            for (j = 0; j < stall_cycles; j = j + 1) begin
                @(negedge clk);
                #1;
                check_val(out_valid, 1, "payload valid stable during stall");
                check_val(out_data, exp_data[exp_head][i], "payload stable data");
                check_val(out_last, (i == (exp_bytes[exp_head] - 1)), "payload stable last");
            end
            out_ready = 1'b1;
            @(posedge clk);
            #1;
            out_ready = 1'b0;
        end
    endtask

    task automatic drain_one(input integer meta_stall, input integer payload_stall);
        wait_meta();
        check_meta_expected();
        if (exp_head < exp_tail) begin
            if (exp_error[exp_head] != 2'd0) begin
                handshake_meta(meta_stall);
                @(negedge clk);
                #1;
                check_val(out_valid, 0, "error frame emits no payload");
                exp_head = exp_head + 1;
            end else begin
                handshake_meta(meta_stall);
                drain_payload(payload_stall);
                exp_head = exp_head + 1;
            end
        end
    endtask

    task automatic drain_all();
        while (exp_head < exp_tail) begin
            drain_one(0, 0);
        end
        @(negedge clk);
        #1;
        check_val(out_meta_valid, 0, "no extra out_meta after drain");
        check_val(out_valid, 0, "no extra out_valid after drain");
    endtask

    task automatic check_invariant(input string message);
        logic [63:0] rhs;
        rhs = {32'd0, stat_retired} + {32'd0, stat_aborted} + {62'd0, level};
        check_val({32'd0, stat_meta}, rhs, message);
    endtask

    task automatic clear_expected();
        exp_head = 0;
        exp_tail = 0;
        pend_active = 1'b0;
    endtask

    task automatic do_cancel(input integer cycles, input logic [63:0] expected_abort);
        logic [31:0] pre_meta;
        logic [31:0] pre_bytes;
        logic [31:0] pre_retired;
        logic [31:0] pre_abort;
        logic [31:0] pre_fault;
        logic [1:0] pre_level;
        @(negedge clk);
        pre_meta = stat_meta;
        pre_bytes = stat_in_bytes;
        pre_retired = stat_retired;
        pre_abort = stat_aborted;
        pre_fault = stat_fault;
        pre_level = level;
        cancel = 1'b1;
        rst = 1'b0;
        #1;
        check_val(in_meta_ready, 0, "cancel gates in_meta_ready");
        check_val(in_ready, 0, "cancel gates in_ready");
        check_val(out_meta_valid, 0, "cancel gates out_meta_valid");
        check_val(out_valid, 0, "cancel gates out_valid");
        repeat (cycles) @(posedge clk);
        #1;
        check_val(level, 0, "cancel clears level");
        check_val(receiving, 0, "cancel clears receiving");
        check_val(faulted, 0, "cancel clears faulted");
        check_val(fault_event, 0, "cancel clears fault_event");
        check_val(fault_code, 0, "cancel clears fault_code");
        check_val(stat_meta, pre_meta, "cancel preserves stat_meta");
        check_val(stat_in_bytes, pre_bytes, "cancel preserves stat_in_bytes");
        check_val(stat_retired, pre_retired, "cancel preserves stat_retired");
        check_val(stat_fault, pre_fault, "cancel preserves stat_fault");
        check_val({32'd0, stat_aborted}, {32'd0, pre_abort} + {62'd0, pre_level},
                  "cancel adds pre-edge level once");
        check_val(stat_aborted, expected_abort, "cancel abort total");
        check_val(out_meta_valid, 0, "cancel leaves no metadata");
        check_val(out_valid, 0, "cancel leaves no payload");
        @(negedge clk);
        cancel = 1'b0;
        #1;
        check_val(in_meta_ready, 1, "in_meta_ready after cancel");
        check_val(in_ready, 0, "in_ready after cancel");
        clear_expected();
    endtask

    task automatic reset_with_cancel();
        @(negedge clk);
        rst = 1'b1;
        cancel = 1'b1;
        #1;
        check_val(in_meta_ready, 0, "rst+cancel gates in_meta_ready");
        check_val(in_ready, 0, "rst+cancel gates in_ready");
        check_val(out_meta_valid, 0, "rst+cancel gates out_meta_valid");
        check_val(out_valid, 0, "rst+cancel gates out_valid");
        repeat (2) @(posedge clk);
        #1;
        check_val(level, 0, "rst+cancel level");
        check_val(receiving, 0, "rst+cancel receiving");
        check_val(faulted, 0, "rst+cancel faulted");
        check_val(fault_event, 0, "rst+cancel fault_event");
        check_val(fault_code, 0, "rst+cancel fault_code");
        check_val(stat_meta, 0, "rst+cancel stat_meta");
        check_val(stat_in_bytes, 0, "rst+cancel stat_in_bytes");
        check_val(stat_retired, 0, "rst+cancel stat_retired");
        check_val(stat_aborted, 0, "rst priority keeps aborted zero");
        check_val(stat_fault, 0, "rst+cancel stat_fault");
        @(negedge clk);
        rst = 1'b0;
        cancel = 1'b0;
        #1;
        clear_expected();
    endtask

    task automatic fault1_case(input logic [1:0] error,
                               input logic [8:0] bytes,
                               input logic [11:0] valid_bits,
                               input logic [15:0] tag);
        do_reset(2);
        drive_meta(tag, error, 8'h5A, 4'hA, 1'b1, 4'hF, valid_bits, bytes, accepted);
        check_val(accepted, 1, "invalid descriptor accepted into reservation");
        check_val(level, 1, "invalid descriptor reserves one slot");
        check_val(receiving, 0, "invalid descriptor opens no payload");
        check_val(faulted, 1, "invalid descriptor latches faulted");
        check_val(fault_code, 1, "invalid descriptor fault_code one");
        check_val(fault_event, 1, "invalid descriptor fault_event pulse");
        check_val(stat_meta, 1, "invalid descriptor stat_meta");
        check_val(stat_fault, 1, "invalid descriptor stat_fault");
        check_val(stat_in_bytes, 0, "invalid descriptor no input bytes");
        check_val(out_meta_valid, 0, "invalid descriptor not visible");
        check_val(out_valid, 0, "invalid descriptor no payload output");
        check_val(in_meta_ready, 0, "faulted blocks new metadata");
        check_val(in_ready, 0, "faulted blocks payload");
        @(posedge clk);
        #1;
        check_val(fault_event, 0, "fault_event clears after one cycle");
        check_val(faulted, 1, "faulted remains sticky");
        drive_meta(16'h7F01, 2'd0, 8'd1, 4'd0, 1'b1, 4'd0, 12'd8, 9'd1, accepted);
        check_val(accepted, 0, "faulted rejects later descriptor");
        check_val(stat_meta, 1, "rejected descriptor does not increment stat_meta");
        check_val(stat_fault, 1, "rejected descriptor does not increment stat_fault");
        do_cancel(1, 64'd1);
    endtask

    task automatic error_forward_case(input logic [1:0] error,
                                      input logic [15:0] tag);
        do_reset(2);
        push_error(tag, error, 8'hA5, 4'h9, 1'b1, 4'hF, 12'd0, 9'd0);
        drive_meta(tag, error, 8'hA5, 4'h9, 1'b1, 4'hF, 12'd0, 9'd0, accepted);
        check_val(accepted, 1, "upstream error descriptor accepted");
        check_val(level, 1, "upstream error reserves one slot");
        check_val(receiving, 0, "upstream error opens no payload");
        check_val(stat_meta, 1, "upstream error stat_meta");
        check_val(stat_fault, 0, "upstream error is not a local fault");
        check_val(faulted, 0, "upstream error leaves faulted clear");
        drain_one(3, 0);
        check_val(level, 0, "upstream error retires on metadata");
        check_val(stat_retired, 1, "upstream error retired count");
        check_val(in_ready, 0, "upstream error never opens payload input");
        check_val(out_valid, 0, "upstream error emits no payload");
        check_invariant("upstream error invariant");
    endtask

    task automatic accept_success_frame(input logic [15:0] tag,
                                        input integer length,
                                        input logic [7:0] seed,
                                        output bit accepted);
        integer i;
        bit byte_ok;
        drive_meta(tag, 2'd0, length[7:0], 4'd0, 1'b1, 4'd0,
                   12'(length * 8), 9'(length), accepted);
        check_val(accepted, 1, "success descriptor accepted");
        if (accepted) begin
            begin_pending(tag, length[7:0], 4'd0, 1'b1, 4'd0,
                          12'(length * 8), 9'(length));
            for (i = 0; i < length; i = i + 1) begin
                pending_byte(seed + i[7:0]);
                drive_byte(seed + i[7:0], (i == (length - 1)), byte_ok);
                check_val(byte_ok, 1, "success payload byte accepted");
            end
            commit_pending();
        end
    endtask

    task automatic accept_error_frame(input logic [15:0] tag,
                                      input logic [1:0] error);
        push_error(tag, error, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0);
        drive_meta(tag, error, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, accepted);
        check_val(accepted, 1, "error frame descriptor accepted");
    endtask

    initial begin
        $display("TB_BEGIN tb=encoded_frame_queue");

        case_begin("reset_idle");
        do_reset(3);
        check_val(stat_meta, 0, "idle stat_meta");
        check_val(stat_in_bytes, 0, "idle stat_in_bytes");
        check_val(stat_retired, 0, "idle stat_retired");
        check_val(stat_aborted, 0, "idle stat_aborted");
        check_val(stat_fault, 0, "idle stat_fault");
        check_val(in_meta_ready, 1, "idle in_meta_ready");
        check_val(in_ready, 0, "idle in_ready");
        check_invariant("idle counter invariant");
        case_end();

        case_begin("single_success");
        do_reset(2);
        begin_pending(16'h1001, 8'd3, 4'd0, 1'b1, 4'd0, 12'd24, 9'd3);
        drive_meta_observe(16'h1001, 2'd0, 8'd3, 4'd0, 1'b1, 4'd0, 12'd24, 9'd3,
                           accepted, pre_in_ready, pre_meta, pre_out);
        check_val(accepted, 1, "descriptor accepted");
        check_val(pre_in_ready, 0, "no payload on descriptor admission edge");
        check_val(in_meta_ready, 0, "no second descriptor while receiving");
        check_val(level, 1, "level after descriptor");
        check_val(receiving, 1, "receiving after descriptor");
        check_val(stat_meta, 1, "stat_meta after descriptor");
        pending_byte(8'h10);
        drive_byte(8'h10, 1'b0, byte_ok);
        check_val(byte_ok, 1, "first payload byte accepted");
        check_val(stat_in_bytes, 1, "stat_in_bytes first byte");
        pending_byte(8'h20);
        drive_byte(8'h20, 1'b0, byte_ok);
        check_val(byte_ok, 1, "second payload byte accepted");
        check_val(stat_in_bytes, 2, "stat_in_bytes second byte");
        check_val(out_meta_valid, 0, "incomplete frame not visible");
        pending_byte(8'h30);
        drive_byte(8'h30, 1'b1, byte_ok);
        check_val(byte_ok, 1, "final payload byte accepted");
        check_val(stat_in_bytes, 3, "stat_in_bytes final byte");
        check_val(receiving, 0, "receiving cleared on seal");
        commit_pending();
        @(negedge clk);
        #1;
        check_val(out_meta_valid, 1, "sealed frame visible");
        check_invariant("single success sealed invariant");
        drain_one(2, 2);
        check_val(level, 0, "level after retire");
        check_val(stat_retired, 1, "stat_retired after retire");
        check_val(out_meta_valid, 0, "no metadata after retire");
        check_val(out_valid, 0, "no payload after retire");
        check_invariant("single success retired invariant");
        case_end();

        case_begin("two_deep_stall");
        do_reset(2);
        accept_success_frame(16'h2001, 2, 8'hA0, accepted);
        check_val(level, 1, "first frame level");
        accept_success_frame(16'h2002, 4, 8'hB0, accepted);
        check_val(level, 2, "second frame level");
        check_val(in_meta_ready, 0, "queue full blocks new metadata");
        @(negedge clk);
        #1;
        check_val(out_meta_valid, 1, "head metadata visible while stalled");
        check_val(out_meta_tag, 16'h2001, "head metadata tag stable");
        repeat (8) begin
            @(negedge clk);
            #1;
            check_val(out_meta_valid, 1, "head metadata remains valid");
            check_val(out_meta_tag, 16'h2001, "head metadata stable");
        end
        check_invariant("two deep invariant");
        drain_all();
        check_val(level, 0, "two deep level after drain");
        check_val(stat_retired, 2, "two deep retired count");
        case_end();

        case_begin("no_same_edge_bypass");
        do_reset(2);
        begin_pending(16'h3001, 8'd1, 4'd0, 1'b1, 4'd0, 12'd8, 9'd1);
        drive_meta_observe(16'h3001, 2'd0, 8'd1, 4'd0, 1'b1, 4'd0, 12'd8, 9'd1,
                           accepted, pre_in_ready, pre_meta, pre_out);
        check_val(accepted, 1, "one byte descriptor accepted");
        check_val(pre_in_ready, 0, "metadata-to-payload same-edge blocked");
        pending_byte(8'h5A);
        drive_byte_observe(8'h5A, 1'b1, byte_ok, pre_meta, pre_out);
        check_val(byte_ok, 1, "one byte payload accepted");
        check_val(pre_meta, 0, "seal edge does not publish metadata");
        commit_pending();
        @(negedge clk);
        #1;
        check_val(out_meta_valid, 1, "metadata visible after seal edge");
        check_meta_expected();
        check_val(out_valid, 0, "metadata-to-first-byte same-edge blocked");
        out_meta_ready = 1'b1;
        out_ready = 1'b1;
        #1;
        @(posedge clk);
        #1;
        out_meta_ready = 1'b0;
        out_ready = 1'b0;
        @(negedge clk);
        #1;
        check_val(out_meta_valid, 0, "metadata deasserted after handshake");
        check_val(out_valid, 1, "first payload visible after metadata edge");
        check_val(out_data, 8'h5A, "first payload data");
        check_val(out_last, 1, "first payload last");
        out_ready = 1'b1;
        @(posedge clk);
        #1;
        out_ready = 1'b0;
        exp_head = exp_head + 1;
        check_val(level, 0, "no bypass level after retire");
        check_val(stat_retired, 1, "no bypass retired");
        case_end();

        case_begin("full_old_level_no_credit");
        do_reset(2);
        push_error(16'h4001, 2'd1, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0);
        drive_meta(16'h4001, 2'd1, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, accepted);
        check_val(accepted, 1, "error frame accepted");
        check_val(level, 1, "error frame level");
        accept_success_frame(16'h4002, 1, 8'hC0, accepted);
        check_val(level, 2, "full queue level");
        @(negedge clk);
        #1;
        check_val(out_meta_valid, 1, "error head visible");
        check_val(out_meta_tag, 16'h4001, "error head tag");
        check_val(in_meta_ready, 0, "full queue blocks admission at old level two");
        out_meta_ready = 1'b1;
        in_meta_valid = 1'b1;
        in_meta_tag = 16'h4003;
        in_meta_error = 2'd0;
        in_meta_count = 8'd1;
        in_meta_e = 4'd0;
        in_meta_raw = 1'b1;
        in_meta_k = 4'd0;
        in_meta_valid_bits = 12'd8;
        in_meta_bytes = 9'd1;
        #1;
        check_val(in_meta_ready, 0, "simultaneous retire gives no old-level credit");
        @(posedge clk);
        #1;
        out_meta_ready = 1'b0;
        in_meta_valid = 1'b0;
        check_val(level, 1, "retire reduced level while admission was blocked");
        check_val(stat_retired, 1, "error metadata retired");
        exp_head = exp_head + 1;
        @(negedge clk);
        #1;
        check_val(in_meta_ready, 1, "one-cycle bubble then admission credit");
        begin_pending(16'h4003, 8'd1, 4'd0, 1'b1, 4'd0, 12'd8, 9'd1);
        drive_meta(16'h4003, 2'd0, 8'd1, 4'd0, 1'b1, 4'd0, 12'd8, 9'd1, accepted);
        check_val(accepted, 1, "post-bubble descriptor accepted");
        pending_byte(8'hC3);
        drive_byte(8'hC3, 1'b1, byte_ok);
        check_val(byte_ok, 1, "post-bubble payload accepted");
        commit_pending();
        check_val(level, 2, "post-bubble level");
        drain_all();
        check_val(level, 0, "full rule final level");
        check_val(stat_retired, 3, "full rule retired count");
        case_end();

        case_begin("framing_boundaries");
        for (integer bi = 0; bi < 4; bi = bi + 1) begin
            logic [8:0] nbytes;
            logic [11:0] lower_bits;
            logic [11:0] upper_bits;
            if (bi == 0) nbytes = 9'd1;
            else if (bi == 1) nbytes = 9'd2;
            else if (bi == 2) nbytes = 9'd255;
            else nbytes = 9'd256;
            lower_bits = 12'((8 * (nbytes - 1)) + 1);
            upper_bits = 12'(8 * nbytes);
            for (integer bed = 0; bed < 2; bed = bed + 1) begin
                logic [11:0] vbits;
                logic [15:0] ftag;
                vbits = (bed == 0) ? lower_bits : upper_bits;
                ftag = 16'h5000 + 16'(bi * 2 + bed);
                do_reset(2);
                begin_pending(ftag, nbytes[7:0], 4'd0, 1'b1, 4'd0, vbits, nbytes);
                drive_meta(ftag, 2'd0, nbytes[7:0], 4'd0, 1'b1, 4'd0,
                           vbits, nbytes, accepted);
                check_val(accepted, 1, "boundary framing descriptor accepted");
                for (integer j = 0; j < nbytes; j = j + 1) begin
                    logic [7:0] bdata;
                    bdata = 8'((j * 13 + bi * 7 + bed) & 255);
                    pending_byte(bdata);
                    drive_byte(bdata, (j == (nbytes - 1)), byte_ok);
                    check_val(byte_ok, 1, "boundary payload byte accepted");
                end
                commit_pending();
                check_val(level, 1, "boundary frame level");
                drain_one(0, 0);
                check_val(level, 0, "boundary frame retired");
                check_val(stat_retired, 1, "boundary retired count");
                check_invariant("boundary counter invariant");
            end
        end
        case_end();

        case_begin("early_last_fault2");
        for (integer li = 0; li < 5; li = li + 1) begin
            integer len;
            if (li == 0) len = 2;
            else if (li == 1) len = 3;
            else if (li == 2) len = 4;
            else if (li == 3) len = 8;
            else len = 16;
            for (integer pi = 0; pi < 3; pi = pi + 1) begin
                integer pos;
                integer j;
                if (pi == 0) pos = 0;
                else if (pi == 1) pos = ((len / 2) < (len - 1)) ? (len / 2) : 0;
                else pos = len - 2;
                do_reset(2);
                drive_meta(16'h8000 + 16'(li * 3 + pi), 2'd0, len[7:0], 4'd0,
                           1'b1, 4'd0, 12'(8 * len), 9'(len), accepted);
                check_val(accepted, 1, "early-last descriptor accepted");
                check_val(level, 1, "early-last reservation level");
                check_val(receiving, 1, "early-last payload open");
                for (j = 0; j <= pos; j = j + 1) begin
                    drive_byte(8'((j * 5 + li * 11 + pi * 3) & 255),
                               (j == pos), byte_ok);
                    check_val(byte_ok, 1, "early-last byte accepted");
                end
                check_val(faulted, 1, "early last latches faulted");
                check_val(fault_code, 2, "early last fault_code two");
                check_val(fault_event, 1, "early last fault_event");
                check_val(receiving, 0, "early last closes payload");
                check_val(level, 1, "early last keeps reservation");
                check_val(stat_meta, 1, "early last stat_meta");
                check_val(stat_in_bytes, pos + 1, "early last byte count");
                check_val(stat_fault, 1, "early last stat_fault");
                check_val(out_meta_valid, 0, "early last never visible");
                check_val(out_valid, 0, "early last no payload output");
                @(posedge clk);
                #1;
                check_val(fault_event, 0, "early last event clears");
                check_val(faulted, 1, "early last faulted sticky");
                drive_meta(16'h8F00, 2'd0, 8'd1, 4'd0, 1'b1, 4'd0, 12'd8, 9'd1, accepted);
                check_val(accepted, 0, "faulted rejects after early last");
                do_cancel(1, 64'd1);
                check_val(stat_meta, 1, "early last cancel preserves meta");
                check_val(stat_in_bytes, pos + 1, "early last cancel preserves bytes");
                check_val(stat_fault, 1, "early last cancel preserves fault");
                check_val(stat_aborted, 1, "early last abort count");
            end
        end
        case_end();

        case_begin("missing_last_fault2");
        for (integer mi = 0; mi < 4; mi = mi + 1) begin
            integer mlen;
            integer mj;
            if (mi == 0) mlen = 1;
            else if (mi == 1) mlen = 2;
            else if (mi == 2) mlen = 255;
            else mlen = 256;
            do_reset(2);
            drive_meta(16'h9000 + 16'(mi), 2'd0, mlen[7:0], 4'd0, 1'b1, 4'd0,
                       12'(8 * mlen), 9'(mlen), accepted);
            check_val(accepted, 1, "missing-last descriptor accepted");
            for (mj = 0; mj < mlen; mj = mj + 1) begin
                drive_byte(8'((mj * 7 + mi * 17) & 255), 1'b0, byte_ok);
                check_val(byte_ok, 1, "missing-last byte accepted");
            end
            check_val(faulted, 1, "missing last latches faulted");
            check_val(fault_code, 2, "missing last fault_code two");
            check_val(fault_event, 1, "missing last fault_event");
            check_val(receiving, 0, "missing last closes payload");
            check_val(level, 1, "missing last keeps reservation");
            check_val(stat_meta, 1, "missing last stat_meta");
            check_val(stat_in_bytes, mlen, "missing last byte count");
            check_val(stat_fault, 1, "missing last stat_fault");
            check_val(out_meta_valid, 0, "missing last never visible");
            check_val(out_valid, 0, "missing last no payload output");
            @(posedge clk);
            #1;
            check_val(fault_event, 0, "missing last event clears");
            do_cancel(1, 64'd1);
            check_val(stat_in_bytes, mlen, "missing last cancel preserves bytes");
        end
        case_end();

        case_begin("invalid_framing_fault1");
        fault1_case(2'd0, 9'd0, 12'd0, 16'hA001);
        fault1_case(2'd0, 9'd257, 12'd2048, 16'hA002);
        fault1_case(2'd0, 9'd511, 12'd4088, 16'hA003);
        fault1_case(2'd0, 9'd4, 12'd0, 16'hA004);
        fault1_case(2'd0, 9'd4, 12'd24, 16'hA005);
        fault1_case(2'd0, 9'd4, 12'd33, 16'hA006);
        fault1_case(2'd0, 9'd256, 12'd2040, 16'hA007);
        fault1_case(2'd0, 9'd256, 12'd2049, 16'hA008);
        fault1_case(2'd1, 9'd1, 12'd0, 16'hA009);
        fault1_case(2'd1, 9'd0, 12'd8, 16'hA00A);
        fault1_case(2'd2, 9'd1, 12'd0, 16'hA00B);
        fault1_case(2'd3, 9'd1, 12'd0, 16'hA00C);
        case_end();

        case_begin("upstream_error_forward");
        error_forward_case(2'd1, 16'hB001);
        error_forward_case(2'd2, 16'hB002);
        error_forward_case(2'd3, 16'hB003);
        do_reset(2);
        push_error(16'hB010, 2'd1, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0);
        drive_meta(16'hB010, 2'd1, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, accepted);
        check_val(accepted, 1, "consecutive error one accepted");
        drain_one(0, 0);
        push_error(16'hB011, 2'd2, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0);
        drive_meta(16'hB011, 2'd2, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, accepted);
        check_val(accepted, 1, "consecutive error two accepted");
        drain_one(0, 0);
        check_val(stat_retired, 2, "consecutive errors retired");
        check_val(stat_meta, 2, "consecutive errors stat_meta");
        do_reset(2);
        push_error(16'hB020, 2'd1, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0);
        drive_meta(16'hB020, 2'd1, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, accepted);
        check_val(accepted, 1, "error before success accepted");
        accept_success_frame(16'hB021, 2, 8'hD0, accepted);
        check_val(level, 2, "error before success fills queue");
        drain_one(2, 2);
        check_val(level, 1, "error before success retires first");
        push_error(16'hB022, 2'd2, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0);
        drive_meta(16'hB022, 2'd2, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, accepted);
        check_val(accepted, 1, "error after success accepted");
        check_val(level, 2, "error after success fills queue");
        drain_all();
        check_val(stat_retired, 3, "error success error retired");
        check_val(stat_meta, 3, "error success error stat_meta");
        check_val(stat_fault, 0, "upstream errors are not local faults");
        case_end();

        case_begin("fault_drains_older");
        do_reset(2);
        accept_success_frame(16'hC001, 2, 8'hE0, accepted);
        check_val(level, 1, "older frame sealed level");
        @(negedge clk);
        #1;
        check_val(out_meta_valid, 1, "older frame visible before fault");
        check_val(out_meta_tag, 16'hC001, "older frame tag before fault");
        drive_meta(16'hC002, 2'd0, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, accepted);
        check_val(accepted, 1, "fault descriptor accepted alongside older frame");
        check_val(faulted, 1, "fault latched beside older frame");
        check_val(fault_code, 1, "fault code one beside older frame");
        check_val(level, 2, "fault reserved tail slot");
        check_val(stat_meta, 2, "fault stat_meta");
        check_val(stat_fault, 1, "fault stat_fault");
        @(negedge clk);
        #1;
        check_val(out_meta_valid, 1, "older frame still drains after fault");
        check_val(out_meta_tag, 16'hC001, "older frame tag still stable");
        check_meta_expected();
        drain_one(3, 3);
        check_val(level, 1, "poisoned reservation remains after older drain");
        check_val(stat_retired, 1, "older frame retired");
        check_val(out_meta_valid, 0, "poisoned reservation not visible");
        check_val(out_valid, 0, "poisoned reservation no payload");
        check_val(in_meta_ready, 0, "faulted queue rejects new input");
        do_cancel(1, 64'd1);
        check_val(stat_meta, 2, "fault drain cancel preserves meta");
        check_val(stat_retired, 1, "fault drain cancel preserves retired");
        check_val(stat_fault, 1, "fault drain cancel preserves fault");
        check_val(stat_aborted, 1, "fault drain abort counts poisoned slot");
        case_end();

        case_begin("fault_event_single_pulse");
        do_reset(2);
        drive_meta(16'hC101, 2'd0, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, accepted);
        check_val(accepted, 1, "pulse fault descriptor accepted");
        check_val(fault_event, 1, "pulse fault event first cycle");
        for (integer pe = 0; pe < 4; pe = pe + 1) begin
            @(posedge clk);
            #1;
            check_val(fault_event, 0, "pulse fault event clears");
            drive_meta(16'hC110 + 16'(pe), 2'd0, 8'd1, 4'd0, 1'b1, 4'd0,
                       12'd8, 9'd1, accepted);
            check_val(accepted, 0, "pulse fault rejects input");
            check_val(stat_fault, 1, "pulse fault tallied once");
        end
        do_cancel(1, 64'd1);
        case_end();

        case_begin("duplicate_aba_tags");
        do_reset(2);
        accept_success_frame(16'h6001, 2, 8'h11, accepted);
        accept_success_frame(16'h6001, 3, 8'h21, accepted);
        check_val(level, 2, "duplicate tags fill two slots");
        drain_one(0, 0);
        drain_one(0, 0);
        check_val(stat_retired, 2, "duplicate tags retired two frames");
        accept_success_frame(16'h6001, 1, 8'h31, accepted);
        drain_one(0, 0);
        accept_success_frame(16'h6002, 2, 8'h41, accepted);
        drain_one(0, 0);
        accept_success_frame(16'h6001, 4, 8'h51, accepted);
        drain_one(0, 0);
        check_val(stat_retired, 5, "ABA tags retired five frames");
        check_val(level, 0, "ABA tags final level");
        case_end();

        case_begin("cancel_empty");
        do_reset(2);
        do_cancel(1, 64'd0);
        check_val(stat_aborted, 0, "empty cancel abort count");
        check_val(stat_meta, 0, "empty cancel meta count");
        accept_success_frame(16'hD100, 1, 8'h71, accepted);
        check_val(level, 1, "recovery frame level");
        drain_one(0, 0);
        check_val(stat_retired, 1, "recovery frame retired");
        check_val(level, 0, "recovery frame drained");
        case_end();

        case_begin("cancel_after_meta");
        do_reset(2);
        drive_meta(16'hD201, 2'd0, 8'd4, 4'd0, 1'b1, 4'd0, 12'd32, 9'd4, accepted);
        check_val(accepted, 1, "cancel-after-meta descriptor accepted");
        check_val(level, 1, "cancel-after-meta level");
        check_val(receiving, 1, "cancel-after-meta receiving");
        check_val(stat_meta, 1, "cancel-after-meta stat_meta");
        do_cancel(1, 64'd1);
        check_val(stat_meta, 1, "cancel-after-meta preserves meta");
        check_val(stat_in_bytes, 0, "cancel-after-meta preserves zero bytes");
        check_val(stat_retired, 0, "cancel-after-meta preserves retired");
        check_val(stat_aborted, 1, "cancel-after-meta abort count");
        accept_success_frame(16'hD202, 2, 8'h72, accepted);
        drain_one(0, 0);
        check_val(stat_retired, 1, "cancel-after-meta recovery retired");
        check_val(stat_meta, 2, "cancel-after-meta recovery meta");
        case_end();

        case_begin("cancel_partial_payload");
        do_reset(2);
        drive_meta(16'hD301, 2'd0, 8'd4, 4'd0, 1'b1, 4'd0, 12'd32, 9'd4, accepted);
        check_val(accepted, 1, "partial-payload descriptor accepted");
        drive_byte(8'h81, 1'b0, byte_ok);
        check_val(byte_ok, 1, "partial-payload byte one");
        drive_byte(8'h82, 1'b0, byte_ok);
        check_val(byte_ok, 1, "partial-payload byte two");
        check_val(stat_in_bytes, 2, "partial-payload input bytes");
        check_val(level, 1, "partial-payload level");
        check_val(receiving, 1, "partial-payload receiving");
        do_cancel(1, 64'd1);
        check_val(stat_in_bytes, 2, "partial-payload cancel preserves bytes");
        check_val(stat_retired, 0, "partial-payload cancel preserves retired");
        check_val(stat_aborted, 1, "partial-payload abort count");
        accept_success_frame(16'hD302, 3, 8'h83, accepted);
        drain_one(0, 0);
        check_val(stat_retired, 1, "partial-payload recovery retired");
        check_val(stat_meta, 2, "partial-payload recovery meta");
        check_val(stat_in_bytes, 5, "partial-payload recovery bytes");
        case_end();

        case_begin("cancel_sealed_output");
        do_reset(2);
        accept_success_frame(16'hD401, 2, 8'h91, accepted);
        accept_success_frame(16'hD402, 3, 8'hA1, accepted);
        check_val(level, 2, "sealed-cancel queue full");
        @(negedge clk);
        #1;
        check_val(out_meta_valid, 1, "sealed-cancel head visible");
        do_cancel(1, 64'd2);
        check_val(stat_meta, 2, "sealed-cancel preserves meta");
        check_val(stat_in_bytes, 5, "sealed-cancel preserves bytes");
        check_val(stat_retired, 0, "sealed-cancel preserves retired");
        check_val(stat_aborted, 2, "sealed-cancel abort count");
        accept_success_frame(16'hD403, 1, 8'hB1, accepted);
        drain_one(0, 0);
        check_val(stat_retired, 1, "sealed-cancel recovery retired");
        check_val(stat_meta, 3, "sealed-cancel recovery meta");
        check_val(stat_in_bytes, 6, "sealed-cancel recovery bytes");
        case_end();

        case_begin("cancel_partial_output");
        do_reset(2);
        accept_success_frame(16'hD501, 3, 8'h80, accepted);
        wait_meta();
        check_meta_expected();
        handshake_meta(0);
        wait_payload();
        check_val(out_data, 8'h80, "partial-output first data");
        check_val(out_last, 0, "partial-output first last");
        out_ready = 1'b1;
        @(posedge clk);
        #1;
        out_ready = 1'b0;
        check_val(level, 1, "partial-output level after one byte");
        check_val(stat_retired, 0, "partial-output not retired");
        do_cancel(1, 64'd1);
        check_val(stat_retired, 0, "partial-output cancel preserves retired");
        check_val(stat_aborted, 1, "partial-output abort count");
        accept_success_frame(16'hD502, 2, 8'hC1, accepted);
        drain_one(0, 0);
        check_val(stat_retired, 1, "partial-output recovery retired");
        check_val(stat_meta, 2, "partial-output recovery meta");
        case_end();

        case_begin("cancel_held_once");
        do_reset(2);
        accept_success_frame(16'hD601, 2, 8'hD1, accepted);
        do_cancel(3, 64'd1);
        check_val(stat_aborted, 1, "held cancel counted once");
        check_val(stat_meta, 1, "held cancel preserves meta");
        accept_success_frame(16'hD602, 1, 8'hD2, accepted);
        drain_one(0, 0);
        check_val(stat_retired, 1, "held cancel recovery retired");
        check_val(stat_aborted, 1, "held cancel recovery abort unchanged");
        case_end();

        case_begin("reset_priority_over_cancel");
        do_reset(2);
        accept_success_frame(16'hD701, 2, 8'hE1, accepted);
        accept_error_frame(16'hD702, 2'd1);
        check_val(level, 2, "reset-priority full queue");
        reset_with_cancel();
        check_val(stat_meta, 0, "reset priority clears stat_meta");
        check_val(stat_in_bytes, 0, "reset priority clears stat_in_bytes");
        check_val(stat_retired, 0, "reset priority clears stat_retired");
        check_val(stat_aborted, 0, "reset priority clears stat_aborted");
        check_val(stat_fault, 0, "reset priority clears stat_fault");
        accept_success_frame(16'hD703, 1, 8'hE2, accepted);
        drain_one(0, 0);
        check_val(stat_retired, 1, "reset priority recovery retired");
        do_reset(2);
        drive_meta(16'hD704, 2'd0, 8'd0, 4'd0, 1'b1, 4'd0, 12'd0, 9'd0, accepted);
        check_val(faulted, 1, "reset-after-fault setup faulted");
        do_reset(2);
        check_val(faulted, 0, "reset clears faulted");
        check_val(stat_fault, 0, "reset clears stat_fault");
        check_val(stat_meta, 0, "reset after fault clears meta");
        case_end();

        case_begin("simultaneous_alloc_retire");
        do_reset(2);
        accept_error_frame(16'hD801, 2'd1);
        check_val(level, 1, "alloc/retire initial level");
        @(negedge clk);
        #1;
        check_val(out_meta_valid, 1, "alloc/retire error head visible");
        check_val(in_meta_ready, 1, "alloc/retire admission available");
        out_meta_ready = 1'b1;
        in_meta_valid = 1'b1;
        in_meta_tag = 16'hD802;
        in_meta_error = 2'd0;
        in_meta_count = 8'd2;
        in_meta_e = 4'd0;
        in_meta_raw = 1'b1;
        in_meta_k = 4'd0;
        in_meta_valid_bits = 12'd16;
        in_meta_bytes = 9'd2;
        #1;
        check_val(in_meta_ready, 1, "alloc/retire simultaneous admission ready");
        @(posedge clk);
        #1;
        out_meta_ready = 1'b0;
        in_meta_valid = 1'b0;
        check_val(level, 1, "alloc/retire level stays one");
        check_val(stat_meta, 2, "alloc/retire stat_meta");
        check_val(stat_retired, 1, "alloc/retire stat_retired");
        check_val(receiving, 1, "alloc/retire new frame receiving");
        exp_head = exp_head + 1;
        begin_pending(16'hD802, 8'd2, 4'd0, 1'b1, 4'd0, 12'd16, 9'd2);
        pending_byte(8'hF1);
        drive_byte(8'hF1, 1'b0, byte_ok);
        check_val(byte_ok, 1, "alloc/retire byte one");
        pending_byte(8'hF2);
        drive_byte(8'hF2, 1'b1, byte_ok);
        check_val(byte_ok, 1, "alloc/retire byte two");
        commit_pending();
        drain_all();
        check_val(stat_retired, 2, "alloc/retire final retired");
        check_val(level, 0, "alloc/retire final level");
        case_end();

        case_begin("simultaneous_seal_retire");
        do_reset(2);
        accept_success_frame(16'hD901, 1, 8'hAA, accepted);
        drive_meta(16'hD902, 2'd0, 8'd1, 4'd0, 1'b1, 4'd0, 12'd8, 9'd1, accepted);
        check_val(accepted, 1, "seal/retire second descriptor accepted");
        begin_pending(16'hD902, 8'd1, 4'd0, 1'b1, 4'd0, 12'd8, 9'd1);
        pending_byte(8'hBB);
        check_val(level, 2, "seal/retire queue full");
        check_val(receiving, 1, "seal/retire second receiving");
        wait_meta();
        check_meta_expected();
        handshake_meta(0);
        wait_payload();
        check_val(out_data, 8'hAA, "seal/retire first data");
        check_val(out_last, 1, "seal/retire first last");
        in_valid = 1'b1;
        in_data = 8'hBB;
        in_last = 1'b1;
        out_ready = 1'b1;
        #1;
        check_val(in_ready, 1, "seal/retire second input ready");
        check_val(out_valid, 1, "seal/retire first output valid");
        @(posedge clk);
        #1;
        in_valid = 1'b0;
        in_data = 8'd0;
        in_last = 1'b0;
        out_ready = 1'b0;
        check_val(level, 1, "seal/retire level after simultaneous edge");
        check_val(stat_retired, 1, "seal/retire first retired");
        check_val(receiving, 0, "seal/retire second sealed");
        exp_head = exp_head + 1;
        commit_pending();
        drain_all();
        check_val(stat_retired, 2, "seal/retire final retired");
        check_val(level, 0, "seal/retire final level");
        check_val(stat_in_bytes, 2, "seal/retire input bytes");
        case_end();

        case_begin("pointer_wrap_many");
        do_reset(2);
        wrap_expected_bytes = 0;
        accept_success_frame(16'hE000, 2, 8'h10, accepted);
        wrap_expected_bytes = wrap_expected_bytes + 2;
        accept_error_frame(16'hE001, 2'd1);
        for (integer wi = 0; wi < 6; wi = wi + 1) begin
            drain_one(0, 0);
            if ((wi % 2) == 0) begin
                integer wlen;
                wlen = 1 + (wi % 4);
                accept_success_frame(16'hE100 + 16'(wi), wlen,
                                     8'(8'h20 + wi * 8'h10), accepted);
                wrap_expected_bytes = wrap_expected_bytes + wlen;
            end else begin
                accept_error_frame(16'hE100 + 16'(wi), 2'd2);
            end
        end
        drain_all();
        check_val(stat_meta, 8, "wrap total stat_meta");
        check_val(stat_retired, 8, "wrap total stat_retired");
        check_val(stat_in_bytes, wrap_expected_bytes, "wrap total input bytes");
        check_val(stat_fault, 0, "wrap no faults");
        check_val(stat_aborted, 0, "wrap no aborts");
        check_val(level, 0, "wrap final level");
        case_end();

        $display("TB_SUMMARY cases=%0d pass=%0d fail=%0d checks=%0d",
                 cases, pass_cases, (cases - pass_cases), checks);
        $display("TB_STAT cases=%0d", cases);
        $display("TB_STAT checks=%0d", checks);
        $display("TB_STAT failures=%0d", failures);
        $display("TB_STAT final_level=%0d", level);
        $display("TB_STAT final_stat_meta=%0d", stat_meta);
        $display("TB_STAT final_stat_in_bytes=%0d", stat_in_bytes);
        $display("TB_STAT final_stat_retired=%0d", stat_retired);
        $display("TB_STAT final_stat_aborted=%0d", stat_aborted);
        $display("TB_STAT final_stat_fault=%0d", stat_fault);
        if ((failures == 0) && (pass_cases == cases)) begin
            $display("TB_END pass");
        end else begin
            $display("TB_END fail");
        end
        $finish;
    end

endmodule

module tb_encoded_frame_queue_small;
    localparam integer SW = 2;
    localparam integer WAIT_LIMIT = 20000;

    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic in_meta_valid = 1'b0;
    logic in_meta_ready;
    logic [15:0] in_meta_tag = 16'd0;
    logic [1:0] in_meta_error = 2'd0;
    logic [7:0] in_meta_count = 8'd0;
    logic [3:0] in_meta_e = 4'd0;
    logic in_meta_raw = 1'b0;
    logic [3:0] in_meta_k = 4'd0;
    logic [11:0] in_meta_valid_bits = 12'd0;
    logic [8:0] in_meta_bytes = 9'd0;
    logic in_valid = 1'b0;
    logic in_ready;
    logic [7:0] in_data = 8'd0;
    logic in_last = 1'b0;
    logic out_meta_valid;
    logic out_meta_ready = 1'b0;
    logic [15:0] out_meta_tag;
    logic [1:0] out_meta_error;
    logic [7:0] out_meta_count;
    logic [3:0] out_meta_e;
    logic out_meta_raw;
    logic [3:0] out_meta_k;
    logic [11:0] out_meta_valid_bits;
    logic [8:0] out_meta_bytes;
    logic out_valid;
    logic out_ready = 1'b0;
    logic [7:0] out_data;
    logic out_last;
    logic [1:0] level;
    logic receiving;
    logic faulted;
    logic fault_event;
    logic [1:0] fault_code;
    logic [1:0] stat_meta;
    logic [1:0] stat_in_bytes;
    logic [1:0] stat_retired;
    logic [1:0] stat_aborted;
    logic [1:0] stat_fault;

    deepeye_encoded_frame_queue #(
        .STAT_W(SW)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .in_meta_valid(in_meta_valid),
        .in_meta_ready(in_meta_ready),
        .in_meta_tag(in_meta_tag),
        .in_meta_error(in_meta_error),
        .in_meta_count(in_meta_count),
        .in_meta_e(in_meta_e),
        .in_meta_raw(in_meta_raw),
        .in_meta_k(in_meta_k),
        .in_meta_valid_bits(in_meta_valid_bits),
        .in_meta_bytes(in_meta_bytes),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_data(in_data),
        .in_last(in_last),
        .out_meta_valid(out_meta_valid),
        .out_meta_ready(out_meta_ready),
        .out_meta_tag(out_meta_tag),
        .out_meta_error(out_meta_error),
        .out_meta_count(out_meta_count),
        .out_meta_e(out_meta_e),
        .out_meta_raw(out_meta_raw),
        .out_meta_k(out_meta_k),
        .out_meta_valid_bits(out_meta_valid_bits),
        .out_meta_bytes(out_meta_bytes),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_data(out_data),
        .out_last(out_last),
        .level(level),
        .receiving(receiving),
        .faulted(faulted),
        .fault_event(fault_event),
        .fault_code(fault_code),
        .stat_meta(stat_meta),
        .stat_in_bytes(stat_in_bytes),
        .stat_retired(stat_retired),
        .stat_aborted(stat_aborted),
        .stat_fault(stat_fault)
    );

    int checks = 0;
    int failures = 0;
    bit accepted = 1'b0;
    bit byte_ok = 1'b0;

    task automatic check(input bit condition, input string message);
        checks = checks + 1;
        if (!condition) begin
            failures = failures + 1;
            $display("TB_CHECK_FAIL tb=small msg=%s time=%0t", message, $time);
        end
    endtask

    task automatic check_val(input logic [63:0] actual,
                             input logic [63:0] expected,
                             input string message);
        checks = checks + 1;
        if (actual !== expected) begin
            failures = failures + 1;
            $display("TB_CHECK_FAIL tb=small msg=%s actual=%0d expected=%0d time=%0t",
                     message, actual, expected, $time);
        end
    endtask

    task automatic reset_small(input integer cycles);
        @(negedge clk);
        rst = 1'b1;
        cancel = 1'b0;
        in_meta_valid = 1'b0;
        in_valid = 1'b0;
        out_meta_ready = 1'b0;
        out_ready = 1'b0;
        #1;
        check_val(in_meta_ready, 0, "small reset gates in_meta_ready");
        check_val(in_ready, 0, "small reset gates in_ready");
        repeat (cycles) @(posedge clk);
        #1;
        check_val(level, 0, "small reset level");
        check_val(receiving, 0, "small reset receiving");
        check_val(faulted, 0, "small reset faulted");
        check_val(stat_meta, 0, "small reset stat_meta");
        check_val(stat_in_bytes, 0, "small reset stat_in_bytes");
        check_val(stat_retired, 0, "small reset stat_retired");
        check_val(stat_aborted, 0, "small reset stat_aborted");
        check_val(stat_fault, 0, "small reset stat_fault");
        @(negedge clk);
        rst = 1'b0;
    endtask

    task automatic drive_meta_small(input logic [15:0] tag,
                                    input logic [1:0] error,
                                    input logic [7:0] count,
                                    input logic [11:0] valid_bits,
                                    input logic [8:0] bytes,
                                    output bit got);
        @(negedge clk);
        in_meta_valid = 1'b1;
        in_meta_tag = tag;
        in_meta_error = error;
        in_meta_count = count;
        in_meta_e = 4'd0;
        in_meta_raw = 1'b1;
        in_meta_k = 4'd0;
        in_meta_valid_bits = valid_bits;
        in_meta_bytes = bytes;
        #1;
        got = (in_meta_ready === 1'b1);
        @(posedge clk);
        #1;
        in_meta_valid = 1'b0;
        in_meta_tag = 16'd0;
        in_meta_error = 2'd0;
        in_meta_count = 8'd0;
        in_meta_valid_bits = 12'd0;
        in_meta_bytes = 9'd0;
    endtask

    task automatic drive_byte_small(input logic [7:0] data,
                                    input logic last,
                                    output bit got);
        @(negedge clk);
        in_valid = 1'b1;
        in_data = data;
        in_last = last;
        #1;
        got = (in_ready === 1'b1);
        @(posedge clk);
        #1;
        in_valid = 1'b0;
        in_data = 8'd0;
        in_last = 1'b0;
    endtask

    task automatic cancel_small();
        @(negedge clk);
        cancel = 1'b1;
        #1;
        check_val(in_meta_ready, 0, "small cancel gates in_meta_ready");
        check_val(in_ready, 0, "small cancel gates in_ready");
        check_val(out_meta_valid, 0, "small cancel gates out_meta_valid");
        check_val(out_valid, 0, "small cancel gates out_valid");
        @(posedge clk);
        #1;
        check_val(level, 0, "small cancel level");
        check_val(receiving, 0, "small cancel receiving");
        check_val(faulted, 0, "small cancel faulted");
        @(negedge clk);
        cancel = 1'b0;
    endtask

    task automatic drain_small(input logic [15:0] tag,
                               input integer length,
                               input logic [7:0] seed);
        integer i;
        integer guard;
        guard = 0;
        @(negedge clk);
        #1;
        while ((out_meta_valid !== 1'b1) && (guard < WAIT_LIMIT)) begin
            @(negedge clk);
            #1;
            guard = guard + 1;
        end
        check_val(out_meta_valid, 1, "small drain metadata wait");
        check_val(out_meta_tag, tag, "small drain tag");
        check_val(out_meta_error, 0, "small drain error");
        check_val(out_meta_bytes, length, "small drain bytes");
        out_meta_ready = 1'b1;
        @(posedge clk);
        #1;
        out_meta_ready = 1'b0;
        for (i = 0; i < length; i = i + 1) begin
            guard = 0;
            @(negedge clk);
            #1;
            while ((out_valid !== 1'b1) && (guard < WAIT_LIMIT)) begin
                @(negedge clk);
                #1;
                guard = guard + 1;
            end
            check_val(out_valid, 1, "small drain payload wait");
            check_val(out_data, seed + i[7:0], "small drain data");
            check_val(out_last, (i == (length - 1)), "small drain last");
            out_ready = 1'b1;
            @(posedge clk);
            #1;
            out_ready = 1'b0;
        end
        check_val(level, 0, "small drain level");
    endtask

    initial begin
        $display("TB_BEGIN tb=encoded_frame_queue_small");
        $display("CASE_BEGIN name=saturation_statw2");

        reset_small(2);
        for (integer si = 0; si < 4; si = si + 1) begin
            drive_meta_small(16'hA000 + 16'(si), 2'd0, 8'd1, 12'd8, 9'd1, accepted);
            check_val(accepted, 1, "small saturation descriptor accepted");
            drive_byte_small(8'h40 + si[7:0], 1'b1, byte_ok);
            check_val(byte_ok, 1, "small saturation byte accepted");
            drain_small(16'hA000 + 16'(si), 1, 8'h40 + si[7:0]);
            check_val(stat_meta, (si < 3) ? (si + 1) : 3, "small stat_meta saturates");
            check_val(stat_retired, (si < 3) ? (si + 1) : 3, "small stat_retired saturates");
            check_val(stat_in_bytes, (si < 3) ? (si + 1) : 3, "small stat_in_bytes saturates");
        end
        check_val(stat_meta, 3, "small stat_meta final saturated");
        check_val(stat_retired, 3, "small stat_retired final saturated");
        check_val(stat_in_bytes, 3, "small stat_in_bytes final saturated");

        drive_meta_small(16'hA100, 2'd0, 8'd2, 12'd16, 9'd2, accepted);
        check_val(accepted, 1, "small post-saturation descriptor accepted");
        drive_byte_small(8'h5A, 1'b0, byte_ok);
        check_val(byte_ok, 1, "small post-saturation first byte");
        drive_byte_small(8'h5B, 1'b1, byte_ok);
        check_val(byte_ok, 1, "small post-saturation final byte");
        drain_small(16'hA100, 2, 8'h5A);
        check_val(stat_meta, 3, "small post-saturation stat_meta stays saturated");
        check_val(stat_retired, 3, "small post-saturation stat_retired stays saturated");
        check_val(stat_in_bytes, 3, "small post-saturation stat_in_bytes stays saturated");

        reset_small(2);
        for (integer ai = 0; ai < 4; ai = ai + 1) begin
            drive_meta_small(16'hB000 + 16'(ai), 2'd0, 8'd1, 12'd8, 9'd1, accepted);
            check_val(accepted, 1, "small abort descriptor accepted");
            cancel_small();
        end
        check_val(stat_aborted, 3, "small stat_aborted saturates");
        check_val(stat_meta, 3, "small abort stat_meta saturates");
        check_val(stat_retired, 0, "small abort retired remains zero");

        reset_small(2);
        for (integer fi = 0; fi < 4; fi = fi + 1) begin
            drive_meta_small(16'hC000 + 16'(fi), 2'd0, 8'd0, 12'd0, 9'd0, accepted);
            check_val(accepted, 1, "small fault descriptor accepted");
            check_val(faulted, 1, "small fault latched");
            check_val(fault_event, 1, "small fault event");
            cancel_small();
        end
        check_val(stat_fault, 3, "small stat_fault saturates");
        check_val(stat_meta, 3, "small fault stat_meta saturates");
        check_val(stat_aborted, 3, "small fault stat_aborted saturates");
        drive_meta_small(16'hC100, 2'd0, 8'd1, 12'd8, 9'd1, accepted);
        check_val(accepted, 1, "small post-fault descriptor accepted");
        drive_byte_small(8'hC5, 1'b1, byte_ok);
        check_val(byte_ok, 1, "small post-fault byte accepted");
        drain_small(16'hC100, 1, 8'hC5);
        check_val(stat_fault, 3, "small post-fault stat_fault stays saturated");
        check_val(stat_meta, 3, "small post-fault stat_meta stays saturated");
        check_val(stat_aborted, 3, "small post-fault stat_aborted stays saturated");
        check_val(stat_retired, 1, "small post-fault data flow retired");
        check_val(stat_in_bytes, 1, "small post-fault data flow bytes");

        $display("CASE_END name=saturation_statw2 status=%s checks=%0d",
                 (failures == 0) ? "pass" : "fail", checks);
        $display("TB_SUMMARY cases=1 pass=%0d fail=%0d checks=%0d",
                 (failures == 0) ? 1 : 0, (failures == 0) ? 0 : 1, checks);
        $display("TB_STAT cases=1");
        $display("TB_STAT checks=%0d", checks);
        $display("TB_STAT failures=%0d", failures);
        $display("TB_STAT final_stat_meta=%0d", stat_meta);
        $display("TB_STAT final_stat_in_bytes=%0d", stat_in_bytes);
        $display("TB_STAT final_stat_retired=%0d", stat_retired);
        $display("TB_STAT final_stat_aborted=%0d", stat_aborted);
        $display("TB_STAT final_stat_fault=%0d", stat_fault);
        if (failures == 0) $display("TB_END pass");
        else $display("TB_END fail");
        $finish;
    end

endmodule

module tb_encoded_frame_queue_compose;
    localparam integer WAIT_LIMIT = 300000;

    logic clk = 1'b0;
    always #5 clk = ~clk;

    logic rst = 1'b1;
    logic cancel = 1'b0;

    logic cfg_valid = 1'b0;
    logic cfg_ready;
    logic [7:0] cfg_count = 8'd0;
    logic [3:0] cfg_e = 4'd0;
    logic [15:0] cfg_tag = 16'd0;
    logic s_valid = 1'b0;
    logic s_ready;
    logic [15:0] s_data = 16'd0;
    logic s_last = 1'b0;

    logic stream_meta_valid;
    logic [15:0] stream_meta_tag;
    logic [1:0] stream_meta_error;
    logic [7:0] stream_meta_count;
    logic [3:0] stream_meta_e;
    logic stream_meta_raw;
    logic [3:0] stream_meta_k;
    logic [11:0] stream_meta_valid_bits;
    logic [8:0] stream_meta_bytes;
    logic stream_m_valid;
    logic [7:0] stream_m_data;
    logic stream_m_last;
    logic [1:0] stream_level;
    logic stream_filling;
    logic [31:0] stream_stat_cfg;
    logic [31:0] stream_stat_samples;
    logic [31:0] stream_stat_ok;
    logic [31:0] stream_stat_error;
    logic [31:0] stream_stat_aborted;

    logic queue_meta_ready;
    logic queue_in_ready;
    logic queue_out_meta_valid;
    logic queue_out_meta_ready = 1'b0;
    logic [15:0] queue_out_meta_tag;
    logic [1:0] queue_out_meta_error;
    logic [7:0] queue_out_meta_count;
    logic [3:0] queue_out_meta_e;
    logic queue_out_meta_raw;
    logic [3:0] queue_out_meta_k;
    logic [11:0] queue_out_meta_valid_bits;
    logic [8:0] queue_out_meta_bytes;
    logic queue_out_valid;
    logic queue_out_ready = 1'b0;
    logic [7:0] queue_out_data;
    logic queue_out_last;
    logic [1:0] queue_level;
    logic queue_receiving;
    logic queue_faulted;
    logic queue_fault_event;
    logic [1:0] queue_fault_code;
    logic [31:0] queue_stat_meta;
    logic [31:0] queue_stat_in_bytes;
    logic [31:0] queue_stat_retired;
    logic [31:0] queue_stat_aborted;
    logic [31:0] queue_stat_fault;

    logic [15:0] samples [0:127];
    logic [7:0] exp_payload [0:255];
    int exp_length = 0;

    int checks = 0;
    int failures = 0;
    int cases = 0;
    int pass_cases = 0;
    string current_case = "";
    bit case_failed = 1'b0;
    int case_checks = 0;

    deepeye_block_stream stream (
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
        .meta_valid(stream_meta_valid),
        .meta_ready(queue_meta_ready),
        .meta_tag(stream_meta_tag),
        .meta_error(stream_meta_error),
        .meta_count(stream_meta_count),
        .meta_e(stream_meta_e),
        .meta_raw(stream_meta_raw),
        .meta_k(stream_meta_k),
        .meta_valid_bits(stream_meta_valid_bits),
        .meta_bytes(stream_meta_bytes),
        .m_valid(stream_m_valid),
        .m_ready(queue_in_ready),
        .m_data(stream_m_data),
        .m_last(stream_m_last),
        .level(stream_level),
        .filling(stream_filling),
        .stat_cfg(stream_stat_cfg),
        .stat_samples(stream_stat_samples),
        .stat_ok(stream_stat_ok),
        .stat_error(stream_stat_error),
        .stat_aborted(stream_stat_aborted)
    );

    deepeye_encoded_frame_queue #(
        .STAT_W(32)
    ) queue (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .in_meta_valid(stream_meta_valid),
        .in_meta_ready(queue_meta_ready),
        .in_meta_tag(stream_meta_tag),
        .in_meta_error(stream_meta_error),
        .in_meta_count(stream_meta_count),
        .in_meta_e(stream_meta_e),
        .in_meta_raw(stream_meta_raw),
        .in_meta_k(stream_meta_k),
        .in_meta_valid_bits(stream_meta_valid_bits),
        .in_meta_bytes(stream_meta_bytes),
        .in_valid(stream_m_valid),
        .in_ready(queue_in_ready),
        .in_data(stream_m_data),
        .in_last(stream_m_last),
        .out_meta_valid(queue_out_meta_valid),
        .out_meta_ready(queue_out_meta_ready),
        .out_meta_tag(queue_out_meta_tag),
        .out_meta_error(queue_out_meta_error),
        .out_meta_count(queue_out_meta_count),
        .out_meta_e(queue_out_meta_e),
        .out_meta_raw(queue_out_meta_raw),
        .out_meta_k(queue_out_meta_k),
        .out_meta_valid_bits(queue_out_meta_valid_bits),
        .out_meta_bytes(queue_out_meta_bytes),
        .out_valid(queue_out_valid),
        .out_ready(queue_out_ready),
        .out_data(queue_out_data),
        .out_last(queue_out_last),
        .level(queue_level),
        .receiving(queue_receiving),
        .faulted(queue_faulted),
        .fault_event(queue_fault_event),
        .fault_code(queue_fault_code),
        .stat_meta(queue_stat_meta),
        .stat_in_bytes(queue_stat_in_bytes),
        .stat_retired(queue_stat_retired),
        .stat_aborted(queue_stat_aborted),
        .stat_fault(queue_stat_fault)
    );

    task automatic check(input bit condition, input string message);
        checks = checks + 1;
        case_checks = case_checks + 1;
        if (!condition) begin
            failures = failures + 1;
            case_failed = 1'b1;
            $display("TB_CHECK_FAIL case=%s msg=%s time=%0t", current_case, message, $time);
        end
    endtask

    task automatic check_val(input logic [63:0] actual,
                             input logic [63:0] expected,
                             input string message);
        checks = checks + 1;
        case_checks = case_checks + 1;
        if (actual !== expected) begin
            failures = failures + 1;
            case_failed = 1'b1;
            $display("TB_CHECK_FAIL case=%s msg=%s actual=%0d expected=%0d time=%0t",
                     current_case, message, actual, expected, $time);
        end
    endtask

    task automatic case_begin(input string name);
        current_case = name;
        case_failed = 1'b0;
        case_checks = 0;
        cases = cases + 1;
        $display("CASE_BEGIN name=%s", name);
    endtask

    task automatic case_end();
        if (!case_failed && (case_checks > 0)) begin
            pass_cases = pass_cases + 1;
            $display("CASE_END name=%s status=pass checks=%0d", current_case, case_checks);
        end else begin
            $display("CASE_END name=%s status=fail checks=%0d", current_case, case_checks);
        end
    endtask

    task automatic compose_reset(input integer cycles);
        @(negedge clk);
        rst = 1'b1;
        cancel = 1'b0;
        cfg_valid = 1'b0;
        s_valid = 1'b0;
        queue_out_meta_ready = 1'b0;
        queue_out_ready = 1'b0;
        #1;
        check_val(queue_meta_ready, 0, "compose reset queue meta ready");
        check_val(queue_in_ready, 0, "compose reset queue payload ready");
        repeat (cycles) @(posedge clk);
        #1;
        check_val(queue_level, 0, "compose reset queue level");
        check_val(queue_stat_meta, 0, "compose reset queue stat_meta");
        check_val(queue_stat_in_bytes, 0, "compose reset queue stat_in_bytes");
        check_val(queue_stat_retired, 0, "compose reset queue stat_retired");
        check_val(queue_stat_aborted, 0, "compose reset queue stat_aborted");
        check_val(queue_stat_fault, 0, "compose reset queue stat_fault");
        check_val(stream_level, 0, "compose reset stream level");
        check_val(stream_stat_cfg, 0, "compose reset stream stat_cfg");
        @(negedge clk);
        rst = 1'b0;
    endtask

    task automatic send_block(input integer count,
                              input logic [3:0] e,
                              input logic [15:0] tag);
        integer i;
        integer guard;
        guard = 0;
        @(negedge clk);
        #1;
        while ((cfg_ready !== 1'b1) && (guard < WAIT_LIMIT)) begin
            @(negedge clk);
            #1;
            guard = guard + 1;
        end
        check_val(cfg_ready, 1, "stream cfg_ready");
        cfg_valid = 1'b1;
        cfg_count = count[7:0];
        cfg_e = e;
        cfg_tag = tag;
        @(posedge clk);
        #1;
        cfg_valid = 1'b0;
        for (i = 0; i < count; i = i + 1) begin
            guard = 0;
            @(negedge clk);
            #1;
            while ((s_ready !== 1'b1) && (guard < WAIT_LIMIT)) begin
                @(negedge clk);
                #1;
                guard = guard + 1;
            end
            check_val(s_ready, 1, "stream s_ready");
            s_valid = 1'b1;
            s_data = samples[i];
            s_last = (i == (count - 1));
            @(posedge clk);
            #1;
            s_valid = 1'b0;
            s_data = 16'd0;
            s_last = 1'b0;
        end
    endtask

    task automatic send_invalid_cfg(input logic [15:0] tag);
        integer guard;
        guard = 0;
        @(negedge clk);
        #1;
        while ((cfg_ready !== 1'b1) && (guard < WAIT_LIMIT)) begin
            @(negedge clk);
            #1;
            guard = guard + 1;
        end
        check_val(cfg_ready, 1, "invalid cfg ready");
        cfg_valid = 1'b1;
        cfg_count = 8'd0;
        cfg_e = 4'd0;
        cfg_tag = tag;
        @(posedge clk);
        #1;
        cfg_valid = 1'b0;
    endtask

    task automatic send_early_last(input logic [15:0] tag);
        integer guard;
        guard = 0;
        @(negedge clk);
        #1;
        while ((cfg_ready !== 1'b1) && (guard < WAIT_LIMIT)) begin
            @(negedge clk);
            #1;
            guard = guard + 1;
        end
        check_val(cfg_ready, 1, "early last cfg ready");
        cfg_valid = 1'b1;
        cfg_count = 8'd2;
        cfg_e = 4'd0;
        cfg_tag = tag;
        @(posedge clk);
        #1;
        cfg_valid = 1'b0;
        guard = 0;
        @(negedge clk);
        #1;
        while ((s_ready !== 1'b1) && (guard < WAIT_LIMIT)) begin
            @(negedge clk);
            #1;
            guard = guard + 1;
        end
        check_val(s_ready, 1, "early last sample ready");
        s_valid = 1'b1;
        s_data = 16'h1111;
        s_last = 1'b1;
        @(posedge clk);
        #1;
        s_valid = 1'b0;
        s_data = 16'd0;
        s_last = 1'b0;
    endtask

    task automatic wait_queue_meta();
        integer guard;
        guard = 0;
        @(negedge clk);
        #1;
        while ((queue_out_meta_valid !== 1'b1) && (guard < WAIT_LIMIT)) begin
            @(negedge clk);
            #1;
            guard = guard + 1;
        end
        check_val(queue_out_meta_valid, 1, "queue metadata wait");
    endtask

    task automatic wait_queue_two_sealed();
        integer guard;
        guard = 0;
        @(negedge clk);
        #1;
        while (((queue_level !== 2'd2) || (queue_receiving !== 1'b0)) &&
               (guard < WAIT_LIMIT)) begin
            @(negedge clk);
            #1;
            guard = guard + 1;
        end
        check_val(queue_level, 2, "two-slot queue level");
        check_val(queue_receiving, 0, "second encoded frame sealed");
    endtask

    task automatic wait_stream_meta_stalled();
        integer guard;
        guard = 0;
        @(negedge clk);
        #1;
        while ((stream_meta_valid !== 1'b1) && (guard < WAIT_LIMIT)) begin
            @(negedge clk);
            #1;
            guard = guard + 1;
        end
        check_val(stream_meta_valid, 1, "third frame reaches stream metadata");
        check_val(queue_meta_ready, 0, "queue full backpressures metadata");
    endtask

    task automatic handshake_queue_meta();
        check_val(queue_out_meta_valid, 1, "queue metadata at handshake");
        queue_out_meta_ready = 1'b1;
        @(posedge clk);
        #1;
        queue_out_meta_ready = 1'b0;
    endtask

    task automatic drain_success_meta(input logic [15:0] tag,
                                      input integer count,
                                      input logic [3:0] e,
                                      input logic raw,
                                      input logic [3:0] k,
                                      input logic [11:0] valid_bits,
                                      input integer bytes);
        wait_queue_meta();
        check_val(queue_out_meta_tag, tag, "compose success tag");
        check_val(queue_out_meta_error, 0, "compose success error");
        check_val(queue_out_meta_count, count, "compose success count");
        check_val(queue_out_meta_e, e, "compose success e");
        check_val(queue_out_meta_raw, raw, "compose success raw");
        check_val(queue_out_meta_k, k, "compose success k");
        check_val(queue_out_meta_valid_bits, valid_bits, "compose success valid_bits");
        check_val(queue_out_meta_bytes, bytes, "compose success bytes");
        handshake_queue_meta();
        for (integer i = 0; i < bytes; i = i + 1) begin
            integer guard;
            guard = 0;
            @(negedge clk);
            #1;
            while ((queue_out_valid !== 1'b1) && (guard < WAIT_LIMIT)) begin
                @(negedge clk);
                #1;
                guard = guard + 1;
            end
            check_val(queue_out_valid, 1, "compose payload valid");
            check_val(queue_out_data, exp_payload[i], "compose payload data");
            check_val(queue_out_last, (i == (bytes - 1)), "compose payload last");
            queue_out_ready = 1'b1;
            @(posedge clk);
            #1;
            queue_out_ready = 1'b0;
        end
    endtask

    task automatic drain_error_meta(input logic [15:0] tag,
                                    input logic [1:0] error);
        wait_queue_meta();
        check_val(queue_out_meta_tag, tag, "compose error tag");
        check_val(queue_out_meta_error, error, "compose error code");
        check_val(queue_out_meta_count, 0, "compose error count");
        check_val(queue_out_meta_valid_bits, 0, "compose error valid_bits");
        check_val(queue_out_meta_bytes, 0, "compose error bytes");
        handshake_queue_meta();
        @(negedge clk);
        #1;
        check_val(queue_out_valid, 0, "compose error no payload");
    endtask

    initial begin
        $display("TB_BEGIN tb=encoded_frame_queue_compose");

        case_begin("compose_two_raw_rice_stall");
        compose_reset(2);
        samples[0] = 16'h1234;
        send_block(1, 4'd0, 16'hC001);
        check_val(cfg_ready, 1, "stream accepts work while first encodes");
        samples[0] = 16'd1000;
        samples[1] = 16'd1001;
        samples[2] = 16'd1002;
        samples[3] = 16'd1001;
        send_block(4, 4'd0, 16'hC001);
        wait_queue_two_sealed();
        check_val(queue_level, 2, "two encoded frames retained while stalled");
        check_val(queue_out_meta_valid, 1, "stalled head metadata visible");
        check_val(queue_out_meta_tag, 16'hC001, "stalled head tag");
        check_val(queue_meta_ready, 0, "full queue backpressures metadata");
        samples[0] = 16'hABCD;
        send_block(1, 4'd0, 16'hC003);
        wait_stream_meta_stalled();
        repeat (6) begin
            @(negedge clk);
            #1;
            check_val(stream_meta_valid, 1, "third frame stalls at stream metadata");
            check_val(queue_meta_ready, 0, "queue remains full while third stalls");
        end
        exp_length = 2;
        exp_payload[0] = 8'h12;
        exp_payload[1] = 8'h34;
        drain_success_meta(16'hC001, 1, 4'd0, 1'b1, 4'd0, 12'd16, 2);
        check_val(queue_level, 1, "queue level after first encoded frame");
        exp_length = 3;
        exp_payload[0] = 8'h03;
        exp_payload[1] = 8'hE8;
        exp_payload[2] = 8'h25;
        drain_success_meta(16'hC001, 4, 4'd0, 1'b0, 4'd0, 12'd24, 3);
        check_val(queue_level, 1, "queue level after second encoded frame");
        exp_length = 2;
        exp_payload[0] = 8'hAB;
        exp_payload[1] = 8'hCD;
        drain_success_meta(16'hC003, 1, 4'd0, 1'b1, 4'd0, 12'd16, 2);
        check_val(queue_level, 0, "queue level after third encoded frame");
        check_val(queue_stat_meta, 3, "compose stat_meta");
        check_val(queue_stat_retired, 3, "compose stat_retired");
        check_val(queue_stat_in_bytes, 7, "compose stat_in_bytes");
        check_val(queue_stat_fault, 0, "compose no queue faults");
        check_val(stream_stat_cfg, 3, "compose stream cfg count");
        check_val(stream_stat_samples, 6, "compose stream sample count");
        check_val(stream_stat_ok, 3, "compose stream ok count");
        check_val(stream_stat_error, 0, "compose stream error count");
        check_val(stream_level, 0, "compose stream level zero");
        case_end();

        case_begin("compose_error_and_cancel");
        compose_reset(2);
        send_invalid_cfg(16'hC101);
        drain_error_meta(16'hC101, 2'd1);
        check_val(queue_level, 0, "compose error1 queue level");
        check_val(stream_stat_error, 1, "compose stream error1");
        send_early_last(16'hC102);
        drain_error_meta(16'hC102, 2'd2);
        check_val(queue_level, 0, "compose error2 queue level");
        check_val(stream_stat_error, 2, "compose stream error2");
        samples[0] = 16'h2222;
        send_block(1, 4'd0, 16'hC103);
        samples[0] = 16'h3333;
        send_block(1, 4'd0, 16'hC104);
        wait_queue_two_sealed();
        check_val(queue_level, 2, "compose cancel pre-level");
        @(negedge clk);
        cancel = 1'b1;
        #1;
        check_val(queue_out_meta_valid, 0, "compose cancel gates queue meta");
        check_val(queue_out_valid, 0, "compose cancel gates queue payload");
        repeat (2) @(posedge clk);
        #1;
        check_val(queue_level, 0, "compose cancel clears queue level");
        check_val(queue_stat_aborted, 2, "compose cancel aborts two frames");
        check_val(queue_stat_retired, 2, "compose cancel preserves retired");
        check_val(stream_level, 0, "compose cancel clears stream level");
        @(negedge clk);
        cancel = 1'b0;
        samples[0] = 16'h4444;
        send_block(1, 4'd0, 16'hC105);
        exp_length = 2;
        exp_payload[0] = 8'h44;
        exp_payload[1] = 8'h44;
        drain_success_meta(16'hC105, 1, 4'd0, 1'b1, 4'd0, 12'd16, 2);
        check_val(queue_level, 0, "compose recovery level");
        check_val(queue_stat_meta, 5, "compose error/cancel stat_meta");
        check_val(queue_stat_retired, 3, "compose error/cancel stat_retired");
        check_val(queue_stat_aborted, 2, "compose error/cancel stat_aborted");
        check_val(queue_stat_in_bytes, 6, "compose error/cancel stat_in_bytes");
        check_val(queue_stat_fault, 0, "compose error/cancel no local faults");
        check_val(stream_stat_cfg, 5, "compose error/cancel stream cfg");
        check_val(stream_stat_ok, 3, "compose error/cancel stream ok");
        check_val(stream_stat_error, 2, "compose error/cancel stream error");
        check_val(stream_level, 0, "compose error/cancel stream level");
        case_end();

        case_begin("compose_full_256");
        compose_reset(2);
        for (integer fi = 0; fi < 128; fi = fi + 1) begin
            samples[fi] = ((fi % 2) == 0) ? 16'h0000 : 16'hFFFF;
        end
        send_block(128, 4'd0, 16'hC201);
        wait_queue_meta();
        check_val(queue_out_meta_tag, 16'hC201, "full256 tag");
        check_val(queue_out_meta_error, 0, "full256 error");
        check_val(queue_out_meta_count, 128, "full256 count");
        check_val(queue_out_meta_e, 0, "full256 e");
        check_val(queue_out_meta_raw, 1, "full256 raw");
        check_val(queue_out_meta_k, 0, "full256 k");
        check_val(queue_out_meta_valid_bits, 2048, "full256 valid_bits");
        check_val(queue_out_meta_bytes, 256, "full256 bytes");
        handshake_queue_meta();
        for (integer bi = 0; bi < 256; bi = bi + 1) begin
            integer guard;
            logic [7:0] expected_byte;
            guard = 0;
            @(negedge clk);
            #1;
            while ((queue_out_valid !== 1'b1) && (guard < WAIT_LIMIT)) begin
                @(negedge clk);
                #1;
                guard = guard + 1;
            end
            check_val(queue_out_valid, 1, "full256 payload valid");
            expected_byte = (((bi / 2) % 2) == 0) ? 8'h00 : 8'hFF;
            check_val(queue_out_data, expected_byte, "full256 payload data");
            check_val(queue_out_last, (bi == 255), "full256 payload last");
            queue_out_ready = 1'b1;
            @(posedge clk);
            #1;
            queue_out_ready = 1'b0;
        end
        check_val(queue_level, 0, "full256 level");
        check_val(queue_stat_meta, 1, "full256 stat_meta");
        check_val(queue_stat_retired, 1, "full256 stat_retired");
        check_val(queue_stat_in_bytes, 256, "full256 stat_in_bytes");
        check_val(stream_stat_cfg, 1, "full256 stream cfg");
        check_val(stream_stat_samples, 128, "full256 stream samples");
        check_val(stream_stat_ok, 1, "full256 stream ok");
        check_val(stream_level, 0, "full256 stream level");
        case_end();

        $display("TB_SUMMARY cases=%0d pass=%0d fail=%0d checks=%0d",
                 cases, pass_cases, (cases - pass_cases), checks);
        $display("TB_STAT cases=%0d", cases);
        $display("TB_STAT checks=%0d", checks);
        $display("TB_STAT failures=%0d", failures);
        $display("TB_STAT final_queue_level=%0d", queue_level);
        $display("TB_STAT final_queue_stat_meta=%0d", queue_stat_meta);
        $display("TB_STAT final_queue_stat_in_bytes=%0d", queue_stat_in_bytes);
        $display("TB_STAT final_queue_stat_retired=%0d", queue_stat_retired);
        $display("TB_STAT final_queue_stat_aborted=%0d", queue_stat_aborted);
        $display("TB_STAT final_queue_stat_fault=%0d", queue_stat_fault);
        if ((failures == 0) && (pass_cases == cases)) begin
            $display("TB_END pass");
        end else begin
            $display("TB_END fail");
        end
        $finish;
    end

endmodule

`ifndef GUARD_W
`define GUARD_W 0
`endif

module tb_encoded_frame_queue_guard;
    localparam integer W = `GUARD_W;

    logic clk = 1'b0;
    logic rst = 1'b1;
    logic cancel = 1'b0;
    logic in_meta_valid = 1'b0;
    logic in_valid = 1'b0;
    logic out_meta_ready = 1'b0;
    logic out_ready = 1'b0;

    logic in_meta_ready;
    logic in_ready;
    logic out_meta_valid;
    logic out_valid;
    logic [7:0] out_data;
    logic out_last;
    logic [1:0] level;
    logic receiving;
    logic faulted;
    logic fault_event;
    logic [1:0] fault_code;

    deepeye_encoded_frame_queue #(
        .STAT_W(W)
    ) dut (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .in_meta_valid(in_meta_valid),
        .in_meta_ready(in_meta_ready),
        .in_meta_tag(16'h0000),
        .in_meta_error(2'd0),
        .in_meta_count(8'd0),
        .in_meta_e(4'd0),
        .in_meta_raw(1'b0),
        .in_meta_k(4'd0),
        .in_meta_valid_bits(12'd0),
        .in_meta_bytes(9'd0),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_data(8'h00),
        .in_last(1'b0),
        .out_meta_valid(out_meta_valid),
        .out_meta_ready(out_meta_ready),
        .out_meta_tag(),
        .out_meta_error(),
        .out_meta_count(),
        .out_meta_e(),
        .out_meta_raw(),
        .out_meta_k(),
        .out_meta_valid_bits(),
        .out_meta_bytes(),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_data(out_data),
        .out_last(out_last),
        .level(level),
        .receiving(receiving),
        .faulted(faulted),
        .fault_event(fault_event),
        .fault_code(fault_code),
        .stat_meta(),
        .stat_in_bytes(),
        .stat_retired(),
        .stat_aborted(),
        .stat_fault()
    );

    initial begin
        $display("GUARD_TB_BEGIN W=%0d", W);
        #200;
        $display("GUARD_TB_UNEXPECTED_NO_FATAL W=%0d", W);
        $finish;
    end

endmodule
