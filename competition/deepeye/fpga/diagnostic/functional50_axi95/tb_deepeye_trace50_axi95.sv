// NEW102 recovery: focused public AXI -> unchanged74 codec/TX -> actual RX/FIFO.
// SOURCE/TEST FIXTURE ONLY. No board, BOOT, ADC, H12, publication or acceptance.
`timescale 1ns/1ps
`default_nettype none
module tb_deepeye_trace50_axi95;
    localparam logic [31:0] MAGIC = 32'h54353046;
    localparam logic [63:0] ORIGIN = 64'd27001348289300;
    localparam logic [63:0] ACQ9 = ORIGIN + 64'd90000000;
    localparam logic [63:0] SRC9_H = ORIGIN + 64'd50000000;
    localparam logic [63:0] SRC9_F = ORIGIN + 64'd90000000;
    localparam logic [63:0] MISMATCH_TICK = ORIGIN + 64'd1;
    localparam logic [127:0] FIXTURE_BUILD = {4{32'h95959595}};

    logic s_axi_aclk;
    logic s_axi_aresetn;
    logic [11:0] s_axi_awaddr;
    logic [2:0] s_axi_awprot;
    logic s_axi_awvalid;
    logic s_axi_awready;
    logic [31:0] s_axi_wdata;
    logic [3:0] s_axi_wstrb;
    logic s_axi_wvalid;
    logic s_axi_wready;
    logic [1:0] s_axi_bresp;
    logic s_axi_bvalid;
    logic s_axi_bready;
    logic [11:0] s_axi_araddr;
    logic [2:0] s_axi_arprot;
    logic s_axi_arvalid;
    logic s_axi_arready;
    logic [31:0] s_axi_rdata;
    logic [1:0] s_axi_rresp;
    logic s_axi_rvalid;
    logic s_axi_rready;

    logic zero_s_axi_aresetn;
    logic [11:0] zero_awaddr;
    logic [2:0] zero_awprot;
    logic zero_awvalid;
    logic zero_awready;
    logic [31:0] zero_wdata;
    logic [3:0] zero_wstrb;
    logic zero_wvalid;
    logic zero_wready;
    logic [1:0] zero_bresp;
    logic zero_bvalid;
    logic zero_bready;
    logic [11:0] zero_araddr;
    logic [2:0] zero_arprot;
    logic zero_arvalid;
    logic zero_arready;
    logic [31:0] zero_rdata;
    logic [1:0] zero_rresp;
    logic zero_rvalid;
    logic zero_rready;

    deepeye_trace50_axi94 #(.BUILD_ID(FIXTURE_BUILD)) dut (
        .s_axi_aclk(s_axi_aclk), .s_axi_aresetn(s_axi_aresetn),
        .s_axi_awaddr(s_axi_awaddr), .s_axi_awprot(s_axi_awprot),
        .s_axi_awvalid(s_axi_awvalid), .s_axi_awready(s_axi_awready),
        .s_axi_wdata(s_axi_wdata), .s_axi_wstrb(s_axi_wstrb),
        .s_axi_wvalid(s_axi_wvalid), .s_axi_wready(s_axi_wready),
        .s_axi_bresp(s_axi_bresp), .s_axi_bvalid(s_axi_bvalid),
        .s_axi_bready(s_axi_bready), .s_axi_araddr(s_axi_araddr),
        .s_axi_arprot(s_axi_arprot), .s_axi_arvalid(s_axi_arvalid),
        .s_axi_arready(s_axi_arready), .s_axi_rdata(s_axi_rdata),
        .s_axi_rresp(s_axi_rresp), .s_axi_rvalid(s_axi_rvalid),
        .s_axi_rready(s_axi_rready)
    );

    deepeye_trace50_axi94 #(.BUILD_ID(128'd0)) dut_zero (
        .s_axi_aclk(s_axi_aclk), .s_axi_aresetn(zero_s_axi_aresetn),
        .s_axi_awaddr(zero_awaddr), .s_axi_awprot(zero_awprot),
        .s_axi_awvalid(zero_awvalid), .s_axi_awready(zero_awready),
        .s_axi_wdata(zero_wdata), .s_axi_wstrb(zero_wstrb),
        .s_axi_wvalid(zero_wvalid), .s_axi_wready(zero_wready),
        .s_axi_bresp(zero_bresp), .s_axi_bvalid(zero_bvalid),
        .s_axi_bready(zero_bready), .s_axi_araddr(zero_araddr),
        .s_axi_arprot(zero_arprot), .s_axi_arvalid(zero_arvalid),
        .s_axi_arready(zero_arready), .s_axi_rdata(zero_rdata),
        .s_axi_rresp(zero_rresp), .s_axi_rvalid(zero_rvalid),
        .s_axi_rready(zero_rready)
    );

    always #10 s_axi_aclk = ~s_axi_aclk;

    integer cycles = 0;
    integer completed = 0;
    integer aw_first_count = 0;
    integer w_first_count = 0;
    always @(posedge s_axi_aclk) begin
        cycles = cycles + 1;
        if (cycles > 600000) $fatal(1, "B95 finite cycle deadline");
    end

    integer uart_n = 0;
    integer uart_partial = 0;
    integer cancel_seq = 0;
    logic [7:0] uart_bytes [0:1023];
    integer zero_low_events = 0;
    always @(negedge dut_zero.core_uart_tx) begin
        if (zero_s_axi_aresetn) zero_low_events = zero_low_events + 1;
    end

    // Independent actual-TX sampler: 50 clocks/bit, first midpoint at 1.5 bit.
    initial begin : uart_sampler
        integer bitno;
        integer start_cancel;
        logic [7:0] sampled;
        forever begin
            @(negedge dut.core_uart_tx);
            if (s_axi_aresetn) begin
                start_cancel = cancel_seq;
                repeat (75) @(posedge s_axi_aclk);
                #1;
                sampled = 8'd0;
                for (bitno = 0; bitno < 8; bitno = bitno + 1) begin
                    sampled[bitno] = dut.core_uart_tx;
                    repeat (50) @(posedge s_axi_aclk);
                    #1;
                end
                if (start_cancel != cancel_seq) begin
                    uart_partial = uart_partial + 1;
                    $fdisplay(events_fd, "UART_PARTIAL_DISCARDED");
                end else begin
                    if (dut.core_uart_tx !== 1'b1)
                        $fatal(1, "B95 UART stop bit was not high");
                    uart_bytes[uart_n] = sampled;
                    $fdisplay(uart_fd, "%02x", sampled);
                    $fflush(uart_fd);
                    uart_n = uart_n + 1;
                end
            end
        end
    end

    string outdir;
    integer uart_fd;
    integer pop_fd;
    integer events_fd;
    integer bus_phase = 0;
    logic [31:0] last_rdata;
    logic [1:0] last_rresp;
    logic [1:0] last_bresp;
    logic [31:0] tmp32;
    integer tmpi;
    integer popped_total = 0;
    integer push_count;
    integer assoc_next;
    logic [31:0] rx_before;
    logic [31:0] rx_after;
    logic [31:0] result_id;
    logic [31:0] result_bytes;
    logic [31:0] result_error;
    logic [31:0] result_end;
    logic [31:0] result_start;
    logic [31:0] status_word;
    logic [31:0] fifo_count;
    logic [31:0] pop_id_word;
    logic [31:0] discard_word;
    logic [31:0] stat_aborted_word;
    logic [31:0] canceled_word;
    integer i;
    integer rec;
    integer ch;
    integer slot;
    integer frame_sequence;
    integer expected_result;
    integer counts [0:7];
    integer qualities [0:7];
    logic [63:0] source_ticks [0:7];
    logic [63:0] source_ns [0:7];

    task automatic clocks(input integer n);
        begin
            repeat (n) @(negedge s_axi_aclk);
        end
    endtask

    function automatic integer bus_order;
        begin
            bus_phase = bus_phase + 1;
            bus_order = bus_phase % 2;
        end
    endfunction

    function automatic integer bus_hold;
        begin
            bus_hold = (bus_phase % 3) + 1;
        end
    endfunction

    task automatic axi_write(input logic [11:0] addr, input logic [31:0] data,
                             input logic [3:0] strb, input integer order,
                             input integer hold);
        logic [1:0] held_resp;
        integer guard;
        begin
            if (s_axi_bvalid) $fatal(1, "B95 BVALID before new write");
            @(negedge s_axi_aclk);
            s_axi_bready = 1'b0;
            s_axi_awaddr = addr;
            s_axi_awprot = 3'd0;
            s_axi_wdata = data;
            s_axi_wstrb = strb;
            if (order == 0) aw_first_count = aw_first_count + 1;
            else w_first_count = w_first_count + 1;
            if (order == 0) begin
                s_axi_awvalid = 1'b1;
                s_axi_wvalid = 1'b0;
                guard = 0;
                @(posedge s_axi_aclk);
                while (!s_axi_awready) begin
                    guard = guard + 1;
                    if (guard > 100) $fatal(1, "B95 AW timeout");
                    @(posedge s_axi_aclk);
                end
                @(negedge s_axi_aclk);
                s_axi_awvalid = 1'b0;
                s_axi_wvalid = 1'b1;
                guard = 0;
                @(posedge s_axi_aclk);
                while (!s_axi_wready) begin
                    guard = guard + 1;
                    if (guard > 100) $fatal(1, "B95 W timeout");
                    @(posedge s_axi_aclk);
                end
            end else begin
                s_axi_wvalid = 1'b1;
                s_axi_awvalid = 1'b0;
                guard = 0;
                @(posedge s_axi_aclk);
                while (!s_axi_wready) begin
                    guard = guard + 1;
                    if (guard > 100) $fatal(1, "B95 W timeout");
                    @(posedge s_axi_aclk);
                end
                @(negedge s_axi_aclk);
                s_axi_wvalid = 1'b0;
                s_axi_awvalid = 1'b1;
                guard = 0;
                @(posedge s_axi_aclk);
                while (!s_axi_awready) begin
                    guard = guard + 1;
                    if (guard > 100) $fatal(1, "B95 AW timeout");
                    @(posedge s_axi_aclk);
                end
            end
            @(negedge s_axi_aclk);
            s_axi_awvalid = 1'b0;
            s_axi_wvalid = 1'b0;
            s_axi_bready = 1'b0;
            guard = 0;
            while (!s_axi_bvalid) begin
                guard = guard + 1;
                if (guard > 100) $fatal(1, "B95 B timeout");
                @(posedge s_axi_aclk);
            end
            #1;
            held_resp = s_axi_bresp;
            last_bresp = s_axi_bresp;
            repeat (hold) begin
                @(posedge s_axi_aclk);
                #1;
                if (!s_axi_bvalid || s_axi_bresp !== held_resp)
                    $fatal(1, "B95 B response changed under stall");
            end
            @(negedge s_axi_aclk);
            s_axi_bready = 1'b1;
            @(posedge s_axi_aclk);
            #1;
            if (s_axi_bvalid) $fatal(1, "B95 B response did not retire");
            @(negedge s_axi_aclk);
            s_axi_bready = 1'b0;
        end
    endtask

    // Hold one status read while a real UART byte changes FIFO state.
    task automatic axi_read_hold_until_uart(input logic [11:0] addr,
                                             input integer target_uart);
        logic [31:0] held_data;
        logic [1:0] held_resp;
        integer guard;
        begin
            if (s_axi_rvalid) $fatal(1, "B95 held-status RVALID preexisting");
            @(negedge s_axi_aclk);
            s_axi_araddr = addr;
            s_axi_arprot = 3'd0;
            s_axi_arvalid = 1'b1;
            s_axi_rready = 1'b0;
            guard = 0;
            @(posedge s_axi_aclk);
            while (!s_axi_arready) begin
                guard = guard + 1;
                if (guard > 100) $fatal(1, "B95 held-status AR timeout");
                @(posedge s_axi_aclk);
            end
            @(negedge s_axi_aclk);
            s_axi_arvalid = 1'b0;
            guard = 0;
            while (!s_axi_rvalid) begin
                guard = guard + 1;
                if (guard > 100) $fatal(1, "B95 held-status R timeout");
                @(posedge s_axi_aclk);
            end
            #1;
            held_data = s_axi_rdata;
            held_resp = s_axi_rresp;
            // BIND has just been accepted; no UART byte has completed yet.
            // Hold this empty-FIFO response while the first actual byte arrives.
            if (held_resp !== 2'b00 || held_data !== 32'd0)
                $fatal(1, "B95 held-status initial word=%h resp=%b",
                       held_data, held_resp);
            while (uart_n < target_uart) begin
                @(posedge s_axi_aclk);
                #1;
                if (!s_axi_rvalid || s_axi_rdata !== held_data ||
                    s_axi_rresp !== held_resp)
                    $fatal(1, "B95 RDATA changed while FIFO status moved");
            end
            repeat (3) begin
                @(posedge s_axi_aclk);
                #1;
                if (!s_axi_rvalid || s_axi_rdata !== held_data ||
                    s_axi_rresp !== held_resp)
                    $fatal(1, "B95 RDATA changed after FIFO movement");
            end
            @(negedge s_axi_aclk);
            s_axi_rready = 1'b1;
            @(posedge s_axi_aclk);
            #1;
            if (s_axi_rvalid) $fatal(1, "B95 held-status R did not retire");
            @(negedge s_axi_aclk);
            s_axi_rready = 1'b0;
            last_rdata = held_data;
            last_rresp = held_resp;
            $fdisplay(events_fd, "NEGATIVE held_rdata_under_fifo_change");
        end
    endtask

    task automatic axi_read(input logic [11:0] addr, input integer hold);
        logic [31:0] held_data;
        logic [1:0] held_resp;
        integer guard;
        begin
            if (s_axi_rvalid) $fatal(1, "B95 RVALID before new read");
            @(negedge s_axi_aclk);
            s_axi_araddr = addr;
            s_axi_arprot = 3'd0;
            s_axi_arvalid = 1'b1;
            s_axi_rready = 1'b0;
            guard = 0;
            @(posedge s_axi_aclk);
            while (!s_axi_arready) begin
                guard = guard + 1;
                if (guard > 100) $fatal(1, "B95 AR timeout");
                @(posedge s_axi_aclk);
            end
            @(negedge s_axi_aclk);
            s_axi_arvalid = 1'b0;
            guard = 0;
            while (!s_axi_rvalid) begin
                guard = guard + 1;
                if (guard > 100) $fatal(1, "B95 R timeout");
                @(posedge s_axi_aclk);
            end
            #1;
            held_data = s_axi_rdata;
            held_resp = s_axi_rresp;
            last_rdata = held_data;
            last_rresp = held_resp;
            repeat (hold) begin
                @(posedge s_axi_aclk);
                #1;
                if (!s_axi_rvalid || s_axi_rdata !== held_data ||
                    s_axi_rresp !== held_resp)
                    $fatal(1, "B95 R response changed under stall");
            end
            @(negedge s_axi_aclk);
            s_axi_rready = 1'b1;
            @(posedge s_axi_aclk);
            #1;
            if (s_axi_rvalid) $fatal(1, "B95 R response did not retire");
            @(negedge s_axi_aclk);
            s_axi_rready = 1'b0;
        end
    endtask

    task automatic wr_ok(input logic [11:0] addr, input logic [31:0] data);
        begin
            axi_write(addr, data, 4'hf, bus_order(), bus_hold());
            if (last_bresp !== 2'b00)
                $fatal(1, "B95 expected OKAY write addr=%h data=%h got=%b",
                       addr, data, last_bresp);
        end
    endtask

    task automatic wr_err(input logic [11:0] addr, input logic [31:0] data,
                          input logic [3:0] strb);
        begin
            axi_write(addr, data, strb, bus_order(), 3);
            if (last_bresp !== 2'b10)
                $fatal(1, "B95 expected SLVERR write addr=%h data=%h got=%b",
                       addr, data, last_bresp);
        end
    endtask

    task automatic rd_ok(input logic [11:0] addr, input logic [31:0] expected);
        begin
            axi_read(addr, 2);
            if (last_rresp !== 2'b00 || last_rdata !== expected)
                $fatal(1, "B95 read mismatch addr=%h exp=%h got=%h resp=%b",
                       addr, expected, last_rdata, last_rresp);
        end
    endtask

    task automatic rd_err(input logic [11:0] addr);
        begin
            axi_read(addr, 3);
            if (last_rresp !== 2'b10 || last_rdata !== 32'd0)
                $fatal(1, "B95 invalid read accepted addr=%h data=%h resp=%b",
                       addr, last_rdata, last_rresp);
        end
    endtask

    task automatic command(input logic [7:0] code, input logic [1:0] expected);
        begin
            axi_write(12'h080, {24'd0, code}, 4'hf, bus_order(), 3);
            if (last_bresp !== expected)
                $fatal(1, "B95 command %0d response exp=%b got=%b",
                       code, expected, last_bresp);
            if (code == 8'd5 && expected == 2'b00)
                cancel_seq = cancel_seq + 1;
            $fdisplay(events_fd, "CMD %0d %0d", code, last_bresp);
            $fflush(events_fd);
        end
    endtask

    task automatic wait_state(input logic [3:0] wanted);
        begin
            axi_read(12'h018, 1);
            while (last_rdata[3:0] != wanted) begin
                clocks(2);
                axi_read(12'h018, 1);
                if (last_rresp !== 2'b00) $fatal(1, "B95 state read error");
            end
        end
    endtask

    task automatic wait_quiescent;
        begin
            axi_read(12'h020, 2);
            while (last_rdata[1] !== 1'b1) begin
                clocks(2);
                axi_read(12'h020, 1);
            end
            if (last_rdata[0] !== 1'b0) $fatal(1, "B95 quiescent state not CANCEL");
        end
    endtask

    task automatic stage_sample(input integer lane, input logic [63:0] tick,
                                input integer data_value, input integer quality_value,
                                input integer channel_value);
        begin
            wr_ok(12'h110, channel_value);
            wr_ok(12'h114, data_value);
            wr_ok(12'h118, tick[31:0]);
            wr_ok(12'h11c, tick[63:32]);
            wr_ok(12'h120, quality_value);
            command(8'd2, 2'b00);
        end
    endtask

    task automatic stage_bind(input integer first_index, input integer acq_tick,
                              input logic [63:0] source_value, input integer source_tick,
                              input integer sequence_value);
        begin
            wr_ok(12'h130, 32'h95345678);
            wr_ok(12'h134, first_index);
            wr_ok(12'h138, acq_tick);
            wr_ok(12'h13c, 32'd0);
            wr_ok(12'h140, source_value[31:0]);
            wr_ok(12'h144, source_value[63:32]);
            wr_ok(12'h148, source_tick);
            wr_ok(12'h14c, 32'd0);
            wr_ok(12'h150, 32'h00000095);
            wr_ok(12'h154, sequence_value);
        end
    endtask

    task automatic complete_result(input integer expected_index,
                                   input logic [3:0] final_state,
                                   input logic [31:0] before_value);
        begin
            wait_state(4'd7);
            axi_read(12'h040, 4);
            if (last_rresp !== 2'b00 || last_rdata !== expected_index)
                $fatal(1, "B95 result id exp=%0d got=%0d", expected_index, last_rdata);
            result_id = last_rdata;
            axi_read(12'h044, 4);
            if (last_rresp !== 2'b00 || last_rdata !== 32'd0)
                $fatal(1, "B95 result error nonzero %h", last_rdata);
            result_error = last_rdata;
            axi_read(12'h048, 4);
            if (last_rresp !== 2'b00 || last_rdata == 32'd0 || last_rdata > 32'd63)
                $fatal(1, "B95 result bytes invalid %h", last_rdata);
            result_bytes = last_rdata;
            axi_read(12'h050, 4);
            if (last_rresp !== 2'b00 || last_rdata !== before_value)
                $fatal(1, "B95 result start exp=%0d got=%0d", before_value, last_rdata);
            result_start = last_rdata;
            axi_read(12'h07c, 4);
            if (last_rresp !== 2'b00 ||
                last_rdata !== (result_start + result_bytes))
                $fatal(1, "B95 result end mismatch start=%0d bytes=%0d end=%h",
                       result_start, result_bytes, last_rdata);
            result_end = last_rdata;
            repeat (100) @(posedge s_axi_aclk);
            if (uart_n != result_end)
                $fatal(1, "B95 independent UART count=%0d RX total=%0d",
                       uart_n, result_end);

            // Repeated, stalled reads must return the same held result.
            axi_read(12'h040, 4);
            if (last_rdata !== result_id) $fatal(1, "B95 result id changed");
            axi_read(12'h048, 4);
            if (last_rdata !== result_bytes) $fatal(1, "B95 result bytes changed");
            axi_read(12'h044, 4);
            if (last_rdata !== result_error) $fatal(1, "B95 result error changed");

            wr_ok(12'h160, 32'd0);
            command(8'd4, 2'b10);
            rd_ok(12'h018, 32'd7);
            wr_ok(12'h160, result_id + 32'd1);
            command(8'd4, 2'b10);
            rd_ok(12'h018, 32'd7);

            wr_ok(12'h160, result_id);
            command(8'd4, 2'b00);
            wr_ok(12'h160, result_id);
            command(8'd4, 2'b10);
            wait_state(final_state);
            $fdisplay(events_fd, "NEGATIVE wrong_and_duplicate_ack id=%0d",
                      result_id);
            $fdisplay(events_fd, "RESULT id=%0d err=%0d bytes=%0d start=%0d end=%0d uart=%0d",
                      result_id, result_error, result_bytes, result_start,
                      result_end, uart_n);
            $fflush(events_fd);
        end
    endtask

    task automatic drain_fifo(input integer expected_count);
        integer drained;
        logic [31:0] peek_word;
        begin
            drained = 0;
            axi_read(12'h030, 1);
            if (last_rdata !== expected_count)
                $fatal(1, "B95 drain expected %0d got %h", expected_count, last_rdata);
            axi_read(12'h038, 1);
            if (last_rresp !== 2'b00) $fatal(1, "B95 pop id read error");
            pop_id_word = last_rdata;
            while (drained < expected_count) begin
                axi_read(12'h070, 3);
                if (last_rresp !== 2'b00 || last_rdata[8] !== 1'b1)
                    $fatal(1, "B95 peek valid failure at %0d", drained);
                if (last_rdata[31:9] !== 23'd0)
                    $fatal(1, "B95 peek reserved bits nonzero");
                peek_word = last_rdata;
                axi_read(12'h070, 3);
                if (last_rdata !== peek_word)
                    $fatal(1, "B95 peek was destructive at %0d", drained);
                if (peek_word[7:0] !== uart_bytes[popped_total])
                    $fatal(1, "B95 FIFO byte %0d exp=%02x got=%02x",
                           popped_total, uart_bytes[popped_total], peek_word[7:0]);
                if (drained == 0) begin
                    wr_ok(12'h164, pop_id_word);
                    command(8'd8, 2'b10);
                    rd_ok(12'h038, pop_id_word);
                    rd_ok(12'h030, expected_count);
                    $fdisplay(events_fd, "NEGATIVE stale_pop_id");
                end
                wr_ok(12'h164, pop_id_word + 32'd1);
                command(8'd8, 2'b00);
                pop_id_word = pop_id_word + 32'd1;
                rd_ok(12'h038, pop_id_word);
                $fdisplay(pop_fd, "%02x", peek_word[7:0]);
                $fflush(pop_fd);
                popped_total = popped_total + 1;
                drained = drained + 1;
                if (drained == 1) begin
                    wr_ok(12'h164, pop_id_word);
                    command(8'd8, 2'b10);
                    rd_ok(12'h038, pop_id_word);
                    rd_ok(12'h030, expected_count - 1);
                    $fdisplay(events_fd, "NEGATIVE duplicate_pop_id");
                end
            end
            axi_read(12'h030, 1);
            if (last_rdata !== 32'd0) $fatal(1, "B95 FIFO not empty after drain");
        end
    endtask

    // Small duplicated BUILD_ID=0 AXI drivers. This instance never emits.
    task automatic zaxi_write(input logic [11:0] addr, input logic [31:0] data);
        integer guard;
        begin
            @(negedge s_axi_aclk);
            zero_bready = 1'b0;
            zero_awaddr = addr; zero_awvalid = 1'b1;
            zero_wdata = data; zero_wstrb = 4'hf; zero_wvalid = 1'b0;
            guard = 0;
            @(posedge s_axi_aclk);
            while (!zero_awready) begin
                guard = guard + 1;
                if (guard > 100) $fatal(1, "B95 zero AW timeout");
                @(posedge s_axi_aclk);
            end
            @(negedge s_axi_aclk);
            zero_awvalid = 1'b0; zero_wvalid = 1'b1;
            guard = 0;
            @(posedge s_axi_aclk);
            while (!zero_wready) begin
                guard = guard + 1;
                if (guard > 100) $fatal(1, "B95 zero W timeout");
                @(posedge s_axi_aclk);
            end
            @(negedge s_axi_aclk);
            zero_awvalid = 1'b0; zero_wvalid = 1'b0;
            guard = 0;
            while (!zero_bvalid) begin
                guard = guard + 1;
                if (guard > 100) $fatal(1, "B95 zero B timeout");
                @(posedge s_axi_aclk);
            end
            @(negedge s_axi_aclk);
            zero_bready = 1'b1;
            @(posedge s_axi_aclk);
            #1;
            last_bresp = zero_bresp;
            @(negedge s_axi_aclk);
            zero_bready = 1'b0;
        end
    endtask

    task automatic zaxi_read(input logic [11:0] addr);
        integer guard;
        begin
            @(negedge s_axi_aclk);
            zero_araddr = addr; zero_arvalid = 1'b1; zero_rready = 1'b0;
            guard = 0;
            @(posedge s_axi_aclk);
            while (!zero_arready) begin
                guard = guard + 1;
                if (guard > 100) $fatal(1, "B95 zero AR timeout");
                @(posedge s_axi_aclk);
            end
            @(negedge s_axi_aclk);
            zero_arvalid = 1'b0;
            guard = 0;
            while (!zero_rvalid) begin
                guard = guard + 1;
                if (guard > 100) $fatal(1, "B95 zero R timeout");
                @(posedge s_axi_aclk);
            end
            #1;
            last_rdata = zero_rdata;
            last_rresp = zero_rresp;
            @(negedge s_axi_aclk);
            zero_rready = 1'b1;
            @(posedge s_axi_aclk);
            #1;
            @(negedge s_axi_aclk);
            zero_rready = 1'b0;
        end
    endtask

    initial begin
        s_axi_aclk = 1'b0;
        s_axi_aresetn = 1'b0;
        zero_s_axi_aresetn = 1'b0;
        s_axi_awaddr = 12'd0; s_axi_awprot = 3'd0; s_axi_awvalid = 1'b0;
        s_axi_wdata = 32'd0; s_axi_wstrb = 4'd0; s_axi_wvalid = 1'b0;
        s_axi_bready = 1'b0;
        s_axi_araddr = 12'd0; s_axi_arprot = 3'd0; s_axi_arvalid = 1'b0;
        s_axi_rready = 1'b0;
        zero_awaddr = 12'd0; zero_awprot = 3'd0; zero_awvalid = 1'b0;
        zero_wdata = 32'd0; zero_wstrb = 4'd0; zero_wvalid = 1'b0;
        zero_bready = 1'b0;
        zero_araddr = 12'd0; zero_arprot = 3'd0; zero_arvalid = 1'b0;
        zero_rready = 1'b0;

        if (!$value$plusargs("OUT=%s", outdir)) $fatal(1, "B95 OUT required");
        uart_fd = $fopen({outdir, "/uart.hex"}, "w");
        pop_fd = $fopen({outdir, "/pop.hex"}, "w");
        events_fd = $fopen({outdir, "/events.txt"}, "w");
        if (!uart_fd || !pop_fd || !events_fd) $fatal(1, "B95 file open failure");

        counts[0] = 3011; counts[1] = 1924; counts[2] = 2002; counts[3] = 0;
        counts[4] = 2982; counts[5] = 2021; counts[6] = 1966; counts[7] = 0;
        qualities[0] = 1; qualities[1] = 1; qualities[2] = 1; qualities[3] = 0;
        // Main102 correction:1807=0x070f has no saturation; valid+held=5.
        qualities[4] = 5; qualities[5] = 5; qualities[6] = 5; qualities[7] = 1;
        for (i = 0; i < 4; i = i + 1) begin
            source_ticks[i] = 64'd0;
            source_ns[i] = ORIGIN;
        end
        source_ns[3] = 64'd0;
        for (i = 4; i < 8; i = i + 1) begin
            source_ticks[i] = (i == 7) ? 64'd90000 : 64'd50000;
            source_ns[i] = (i == 7) ? SRC9_F : SRC9_H;
        end

        repeat (10) @(posedge s_axi_aclk);
        @(negedge s_axi_aclk);
        s_axi_aresetn = 1'b1;
        zero_s_axi_aresetn = 1'b1;
        repeat (10) @(posedge s_axi_aclk);

        rd_ok(12'h000, MAGIC);
        rd_ok(12'h004, 32'd1);
        rd_ok(12'h008, 32'd4);
        rd_ok(12'h00c, 32'd50000000);
        rd_ok(12'h010, 32'd1000000);
        rd_ok(12'h014, 32'd4096);
        rd_ok(12'h018, 32'd0);
        rd_ok(12'h01c, 32'd0);
        rd_ok(12'h060, 32'h95959595);
        rd_ok(12'h064, 32'h95959595);
        rd_ok(12'h068, 32'h95959595);
        rd_ok(12'h06c, 32'h95959595);

        // The separate zero-BUILD_ID instance cannot ARM or emit.
        zaxi_read(12'h060); if (last_rdata !== 32'd0 || last_rresp !== 2'b00)
            $fatal(1, "B95 zero build word 0 mismatch");
        zaxi_read(12'h06c); if (last_rdata !== 32'd0 || last_rresp !== 2'b00)
            $fatal(1, "B95 zero build word 3 mismatch");
        zaxi_write(12'h100, 32'h9501);
        if (last_bresp !== 2'b00) $fatal(1, "B95 zero tag stage failed");
        zaxi_write(12'h104, ORIGIN[31:0]);
        if (last_bresp !== 2'b00) $fatal(1, "B95 zero origin low stage failed");
        zaxi_write(12'h108, ORIGIN[63:32]);
        if (last_bresp !== 2'b00) $fatal(1, "B95 zero origin high stage failed");
        zaxi_write(12'h080, 32'd1);
        if (last_bresp !== 2'b10) $fatal(1, "B95 zero BUILD_ID ARM not refused");
        zaxi_read(12'h018); if (last_rdata !== 32'd0) $fatal(1, "B95 zero state moved");
        zaxi_read(12'h01c); if (last_rdata !== 32'd0) $fatal(1, "B95 zero fault");
        zaxi_read(12'h030); if (last_rdata !== 32'd0) $fatal(1, "B95 zero FIFO nonempty");
        if (dut_zero.core_uart_tx !== 1'b1) $fatal(1, "B95 zero UART not idle high");
        $fdisplay(events_fd, "NEGATIVE zero_build_arm");

        // Unknown/misaligned/WO reads, invalid writes, and held R data.
        rd_err(12'h0fe);
        rd_err(12'h001);
        rd_err(12'h080);
        wr_err(12'h0fc, 32'h12345678, 4'hf);
        wr_err(12'h101, 32'h12345678, 4'hf);
        wr_err(12'h000, 32'h12345678, 4'hf);
        rd_ok(12'h000, MAGIC);
        wr_err(12'h100, 32'h12345678, 4'h1);
        rd_ok(12'h100, 32'd0);
        wr_err(12'h080, 32'h01000001, 4'hf);
        rd_ok(12'h018, 32'd0);
        $fdisplay(events_fd, "NEGATIVE bus_invalid_routes");

        // Incomplete and uint63-invalid ARM staging do not move state.
        wr_ok(12'h100, 32'hdead);
        command(8'd1, 2'b10);
        rd_ok(12'h018, 32'd0);
        rd_ok(12'h02c, 32'd0);
        wr_ok(12'h104, ORIGIN[31:0]);
        wr_ok(12'h108, 32'h80000000);
        command(8'd1, 2'b10);
        rd_ok(12'h018, 32'd0);
        rd_ok(12'h02c, 32'd0);
        $fdisplay(events_fd, "NEGATIVE incomplete_and_uint63_arm");

        // Reset with a captured AW, no W, and a held R response.
        @(negedge s_axi_aclk);
        s_axi_awaddr = 12'h100; s_axi_awvalid = 1'b1; s_axi_wvalid = 1'b0;
        @(posedge s_axi_aclk);
        while (!s_axi_awready) @(posedge s_axi_aclk);
        @(negedge s_axi_aclk); s_axi_awvalid = 1'b0;
        @(negedge s_axi_aclk);
        s_axi_araddr = 12'h000; s_axi_arvalid = 1'b1; s_axi_rready = 1'b0;
        @(posedge s_axi_aclk);
        while (!s_axi_arready) @(posedge s_axi_aclk);
        @(negedge s_axi_aclk); s_axi_arvalid = 1'b0;
        while (!s_axi_rvalid) @(posedge s_axi_aclk);
        @(negedge s_axi_aclk);
        s_axi_aresetn = 1'b0; s_axi_bready = 1'b0; s_axi_rready = 1'b0;
        s_axi_awvalid = 1'b0; s_axi_wvalid = 1'b0; s_axi_arvalid = 1'b0;
        repeat (4) @(posedge s_axi_aclk);
        @(negedge s_axi_aclk); s_axi_aresetn = 1'b1;
        repeat (10) @(posedge s_axi_aclk);
        if (s_axi_bvalid || s_axi_rvalid) $fatal(1, "B95 reset held stale response");
        rd_ok(12'h100, 32'd0);
        rd_ok(12'h018, 32'd0);
        rd_ok(12'h030, 32'd0);
        $fdisplay(events_fd, "NEGATIVE reset_pending_aw_r");

        // A lone captured W must also be discarded; no AW is supplied.
        @(negedge s_axi_aclk);
        s_axi_awvalid = 1'b0;
        s_axi_wdata = 32'hface; s_axi_wstrb = 4'hf; s_axi_wvalid = 1'b1;
        @(posedge s_axi_aclk);
        while (!s_axi_wready) @(posedge s_axi_aclk);
        @(negedge s_axi_aclk); s_axi_wvalid = 1'b0;
        s_axi_aresetn = 1'b0;
        repeat (4) @(posedge s_axi_aclk);
        @(negedge s_axi_aclk); s_axi_aresetn = 1'b1;
        repeat (10) @(posedge s_axi_aclk);
        if (s_axi_bvalid || s_axi_rvalid) $fatal(1, "B95 reset retained lone W");
        rd_ok(12'h100, 32'd0);
        rd_ok(12'h018, 32'd0);
        rd_ok(12'h030, 32'd0);
        $fdisplay(events_fd, "NEGATIVE reset_pending_w");

        // Reset with a pending B and R response; neither replays.
        @(negedge s_axi_aclk);
        s_axi_awaddr = 12'h100; s_axi_awvalid = 1'b1;
        s_axi_wdata = 32'hbeef; s_axi_wstrb = 4'hf; s_axi_wvalid = 1'b1;
        s_axi_bready = 1'b0;
        @(posedge s_axi_aclk);
        if (!s_axi_awready || !s_axi_wready) $fatal(1, "B95 reset-pending slots not ready");
        @(negedge s_axi_aclk); s_axi_awvalid = 1'b0; s_axi_wvalid = 1'b0;
        // Independent slots are decoded on the next rising edge; wait for
        // actual BVALID rather than assuming zero-cycle response latency.
        tmpi = 0;
        while (!s_axi_bvalid) begin
            @(posedge s_axi_aclk); #1;
            tmpi = tmpi + 1;
            if (tmpi > 100) $fatal(1, "B95 pending B never became visible");
        end
        @(negedge s_axi_aclk);
        s_axi_araddr = 12'h004; s_axi_arvalid = 1'b1; s_axi_rready = 1'b0;
        @(posedge s_axi_aclk);
        while (!s_axi_arready) @(posedge s_axi_aclk);
        @(negedge s_axi_aclk); s_axi_arvalid = 1'b0;
        while (!s_axi_rvalid) @(posedge s_axi_aclk);
        @(negedge s_axi_aclk);
        s_axi_aresetn = 1'b0; s_axi_bready = 1'b0; s_axi_rready = 1'b0;
        repeat (4) @(posedge s_axi_aclk);
        @(negedge s_axi_aclk); s_axi_aresetn = 1'b1;
        repeat (10) @(posedge s_axi_aclk);
        if (s_axi_bvalid || s_axi_rvalid) $fatal(1, "B95 reset retained B/R");
        rd_ok(12'h100, 32'd0);
        rd_ok(12'h018, 32'd0);
        rd_ok(12'h030, 32'd0);
        $fdisplay(events_fd, "NEGATIVE reset_pending_b_r");

        // First scan: exact retired A70 record 0.
        wr_ok(12'h100, 32'h9501);
        wr_ok(12'h104, ORIGIN[31:0]);
        wr_ok(12'h108, ORIGIN[63:32]);
        command(8'd1, 2'b00);
        wait_state(4'd3);
        rd_ok(12'h02c, 32'h9501);

        // ARM while active refuses and leaves the accepted tag unchanged.
        wr_ok(12'h100, 32'h9502);
        wr_ok(12'h104, ORIGIN[31:0]);
        wr_ok(12'h108, ORIGIN[63:32]);
        command(8'd1, 2'b10);
        rd_ok(12'h02c, 32'h9501);
        rd_ok(12'h018, 32'd3);
        $fdisplay(events_fd, "NEGATIVE arm_while_active");

        // Freshness, pad, reserved quality, wrong channel and common-tick refusals.
        wr_ok(12'h110, 32'd0);
        command(8'd2, 2'b10);
        rd_ok(12'h024, 32'd0);
        wr_ok(12'h114, counts[0]);
        command(8'd2, 2'b10);
        wr_ok(12'h118, ORIGIN[31:0]);
        wr_ok(12'h11c, ORIGIN[63:32]);
        command(8'd2, 2'b10);
        wr_ok(12'h120, 32'd1);
        wr_ok(12'h114, 32'd1);
        wr_ok(12'h120, 32'd0);
        command(8'd2, 2'b10);
        rd_ok(12'h024, 32'd0);
        wr_ok(12'h114, 32'd0);
        wr_ok(12'h120, 32'h00010001);
        command(8'd2, 2'b10);
        wr_ok(12'h120, 32'd1);
        wr_ok(12'h110, 32'd1);
        wr_ok(12'h114, counts[1]);
        command(8'd2, 2'b10);
        rd_ok(12'h024, 32'd0);
        $fdisplay(events_fd, "NEGATIVE push_freshness_pad_quality_channel");

        // Explicit uint63 sample high-bit refusal leaves the push count unchanged.
        wr_ok(12'h110, 32'd0);
        wr_ok(12'h114, counts[0]);
        wr_ok(12'h118, ORIGIN[31:0]);
        wr_ok(12'h11c, 32'h80000000);
        wr_ok(12'h120, 32'd1);
        command(8'd2, 2'b10);
        rd_ok(12'h024, 32'd0);
        $fdisplay(events_fd, "NEGATIVE sample_uint63_highbit");

        wr_ok(12'h110, 32'd0);
        wr_ok(12'h114, counts[0]);
        wr_ok(12'h118, ORIGIN[31:0]);
        wr_ok(12'h11c, ORIGIN[63:32]);
        wr_ok(12'h120, 32'd1);
        command(8'd2, 2'b00);
        rd_ok(12'h024, 32'd1);
        wr_ok(12'h110, 32'd1);
        wr_ok(12'h114, counts[1]);
        wr_ok(12'h118, MISMATCH_TICK[31:0]);
        wr_ok(12'h11c, MISMATCH_TICK[63:32]);
        wr_ok(12'h120, 32'd1);
        command(8'd2, 2'b10);
        rd_ok(12'h024, 32'd1);
        wr_ok(12'h118, ORIGIN[31:0]);
        wr_ok(12'h11c, ORIGIN[63:32]);
        command(8'd2, 2'b00);
        rd_ok(12'h024, 32'd2);
        wr_ok(12'h110, 32'd2);
        wr_ok(12'h114, counts[2]);
        wr_ok(12'h118, ORIGIN[31:0]);
        wr_ok(12'h11c, ORIGIN[63:32]);
        wr_ok(12'h120, 32'd1);
        command(8'd2, 2'b00);
        rd_ok(12'h024, 32'd3);
        wr_ok(12'h110, 32'd3);
        wr_ok(12'h114, 32'd0);
        wr_ok(12'h118, ORIGIN[31:0]);
        wr_ok(12'h11c, ORIGIN[63:32]);
        wr_ok(12'h120, 32'd0);
        command(8'd2, 2'b00);
        rd_ok(12'h024, 32'd4);
        rd_ok(12'h018, 32'd4);
        $fdisplay(events_fd, "NEGATIVE common_tick_and_invalid_lane");

        // Fifth lane is refused without changing the four captured lanes.
        wr_ok(12'h110, 32'd0);
        wr_ok(12'h114, counts[0]);
        wr_ok(12'h118, ORIGIN[31:0]);
        wr_ok(12'h11c, ORIGIN[63:32]);
        wr_ok(12'h120, 32'd1);
        command(8'd2, 2'b10);
        rd_ok(12'h024, 32'd4);
        rd_ok(12'h028, 32'd0);
        $fdisplay(events_fd, "NEGATIVE fifth_push");

        // Incomplete association staging is refused before any BIND effect.
        wr_ok(12'h130, 32'h95345678);
        command(8'd3, 2'b10);
        rd_ok(12'h028, 32'd0);
        $fdisplay(events_fd, "NEGATIVE incomplete_bind_staging");

        stage_bind(0, 0, ORIGIN, 0, 950);
        wr_ok(12'h13c, 32'd1000);
        command(8'd3, 2'b10);
        rd_ok(12'h028, 32'd0);
        stage_bind(0, 0, ORIGIN, 0, 950);
        wr_ok(12'h144, 32'h80000000);
        command(8'd3, 2'b10);
        rd_ok(12'h028, 32'd0);
        stage_bind(0, 0, ORIGIN + 64'd1000, 1, 950);
        command(8'd3, 2'b10);
        rd_ok(12'h028, 32'd0);
        stage_bind(0, 1, ORIGIN, 0, 950);
        command(8'd3, 2'b10);
        rd_ok(12'h028, 32'd0);
        $fdisplay(events_fd, "NEGATIVE bind_rem_uint63_source_acq_decomp");

        axi_read(12'h034, 1); rx_before = last_rdata;
        stage_bind(0, 0, ORIGIN, 0, 950);
        command(8'd3, 2'b00);
        complete_result(1, 4'd4, rx_before);

        // Reused sequence on lane 1 refuses, then fresh 951 succeeds.
        axi_read(12'h034, 1); rx_before = last_rdata;
        stage_bind(1, 0, ORIGIN, 0, 950);
        command(8'd3, 2'b10);
        rd_ok(12'h028, 32'd1);
        stage_bind(1, 0, ORIGIN, 0, 951);
        command(8'd3, 2'b00);
        complete_result(2, 4'd4, rx_before);
        $fdisplay(events_fd, "NEGATIVE reused_frame_sequence");

        axi_read(12'h034, 1); rx_before = last_rdata;
        stage_bind(2, 0, ORIGIN, 0, 952);
        command(8'd3, 2'b00);
        complete_result(3, 4'd4, rx_before);
        axi_read(12'h034, 1); rx_before = last_rdata;
        stage_bind(3, 0, 64'd0, 0, 953);
        command(8'd3, 2'b00);
        complete_result(4, 4'd9, rx_before);

        repeat (100) @(posedge s_axi_aclk);
        axi_read(12'h034, 2);
        if (last_rdata !== 32'd146)
            $fatal(1, "B95 record0 measured wire bytes=%h expected 146", last_rdata);
        if (uart_n != 146) $fatal(1, "B95 record0 independent UART count=%0d", uart_n);
        $fdisplay(events_fd, "SCAN record=0 wire_bytes=%0d", last_rdata);

        // A second ARM cannot begin with the first scan's FIFO retained.
        wr_ok(12'h100, 32'h9502);
        wr_ok(12'h104, ORIGIN[31:0]);
        wr_ok(12'h108, ORIGIN[63:32]);
        command(8'd1, 2'b10);
        rd_ok(12'h02c, 32'h9501);
        rd_ok(12'h018, 32'd9);
        command(8'd5, 2'b00);
        wait_quiescent;
        axi_read(12'h030, 1);
        if (last_rdata !== 32'd146) $fatal(1, "B95 cancel did not retain FIFO");
        command(8'd1, 2'b10);
        rd_ok(12'h02c, 32'h9501);
        $fdisplay(events_fd, "NEGATIVE arm_nonempty_after_cancel");

        drain_fifo(146);
        if (popped_total != 146) $fatal(1, "B95 popped record0 total %0d", popped_total);
        $fdisplay(events_fd, "DRAIN count=146 pop_id_end=%0d", pop_id_word);

        // Stale tag is refused only after the drained/quiescent precondition.
        wr_ok(12'h100, 32'h9501);
        wr_ok(12'h104, ORIGIN[31:0]);
        wr_ok(12'h108, ORIGIN[63:32]);
        command(8'd1, 2'b10);
        rd_ok(12'h02c, 32'h9501);
        $fdisplay(events_fd, "NEGATIVE stale_arm_tag");

        wr_ok(12'h100, 32'h9502);
        wr_ok(12'h104, ORIGIN[31:0]);
        wr_ok(12'h108, ORIGIN[63:32]);
        command(8'd1, 2'b00);
        wait_state(4'd3);
        rd_ok(12'h02c, 32'h9502);

        // Second scan: exact retired A70 record 9.
        for (slot = 4; slot < 8; slot = slot + 1) begin
            wr_ok(12'h110, slot - 4);
            wr_ok(12'h114, counts[slot]);
            wr_ok(12'h118, ACQ9[31:0]);
            wr_ok(12'h11c, ACQ9[63:32]);
            wr_ok(12'h120, qualities[slot]);
            command(8'd2, 2'b00);
        end
        rd_ok(12'h024, 32'd4);
        rd_ok(12'h018, 32'd4);

        // Held/source mismatch controls precede record9 lane0 BIND.
        axi_read(12'h034, 1); rx_before = last_rdata;
        stage_bind(36, 90000, ACQ9, 90000, 954);
        command(8'd3, 2'b10);
        rd_ok(12'h028, 32'd0);
        stage_bind(36, 90000, SRC9_H, 50000, 954);
        command(8'd3, 2'b00);
        complete_result(5, 4'd4, rx_before);
        $fdisplay(events_fd, "NEGATIVE held_mismatch");

        axi_read(12'h034, 1); rx_before = last_rdata;
        stage_bind(37, 90000, SRC9_H, 50000, 955);
        command(8'd3, 2'b00);
        complete_result(6, 4'd4, rx_before);
        axi_read(12'h034, 1); rx_before = last_rdata;
        stage_bind(38, 90000, SRC9_H, 50000, 956);
        command(8'd3, 2'b00);
        complete_result(7, 4'd4, rx_before);

        // Fresh C3 valid-zero rejects a held/source-age substitution.
        axi_read(12'h034, 1); rx_before = last_rdata;
        stage_bind(39, 90000, SRC9_H, 50000, 957);
        command(8'd3, 2'b10);
        rd_ok(12'h028, 32'd3);
        stage_bind(39, 90000, SRC9_F, 90000, 957);
        command(8'd3, 2'b00);
        complete_result(8, 4'd9, rx_before);
        $fdisplay(events_fd, "NEGATIVE fresh_held_mismatch");

        repeat (100) @(posedge s_axi_aclk);
        axi_read(12'h034, 2);
        if (last_rdata !== 32'd300)
            $fatal(1, "B95 record9 measured cumulative wire bytes=%h expected 300", last_rdata);
        if (uart_n != 300) $fatal(1, "B95 record9 independent UART count=%0d", uart_n);
        $fdisplay(events_fd, "SCAN record=9 cumulative_wire_bytes=%0d", last_rdata);
        drain_fifo(154);
        if (popped_total != 300) $fatal(1, "B95 popped total %0d", popped_total);
        $fdisplay(events_fd, "DRAIN count=154 pop_id_end=%0d", pop_id_word);

        // New public cancel inside a real second UART frame after one complete byte.
        command(8'd5, 2'b00);
        wait_quiescent;
        rd_ok(12'h030, 32'd0);
        wr_ok(12'h100, 32'h9503);
        wr_ok(12'h104, ORIGIN[31:0]);
        wr_ok(12'h108, ORIGIN[63:32]);
        command(8'd1, 2'b00);
        wait_state(4'd3);
        for (slot = 4; slot < 8; slot = slot + 1) begin
            wr_ok(12'h110, slot - 4);
            wr_ok(12'h114, counts[slot]);
            wr_ok(12'h118, ACQ9[31:0]);
            wr_ok(12'h11c, ACQ9[63:32]);
            wr_ok(12'h120, qualities[slot]);
            command(8'd2, 2'b00);
        end
        rd_ok(12'h018, 32'd4);
        stage_bind(36, 90000, SRC9_H, 50000, 958);
        command(8'd3, 2'b00);
        axi_read_hold_until_uart(12'h030, 301);
        if (uart_n != 301) $fatal(1, "B95 FIFO movement did not complete");
        @(negedge dut.core_uart_tx);
        rd_ok(12'h030, 32'd1);
        repeat (150) @(posedge s_axi_aclk);
        command(8'd5, 2'b00);
        rd_ok(12'h018, 32'd0);
        wait_quiescent;
        repeat (600) @(posedge s_axi_aclk);
        if (uart_partial < 1) $fatal(1, "B95 cancel did not abort an actual UART frame");
        if (uart_n != 301) $fatal(1, "B95 cancel retained unexpected UART completions %0d", uart_n);
        axi_read(12'h034, 2); if (last_rdata !== 32'd301)
            $fatal(1, "B95 cancel rx_total=%0d", last_rdata);
        axi_read(12'h078, 2); canceled_word = last_rdata;
        if (canceled_word !== 32'd1) $fatal(1, "B95 cancel flag not visible");
        axi_read(12'h040, 2); if (last_rdata !== 32'd8)
            $fatal(1, "B95 cancel changed result id");
        axi_read(12'h020, 2); if (last_rdata[4] !== 1'b0)
            $fatal(1, "B95 canceled partial produced a result");
        axi_read(12'h030, 2); fifo_count = last_rdata;
        if (fifo_count != 1) $fatal(1, "B95 cancel prefix FIFO count=%0d", fifo_count);
        axi_read(12'h054, 2); stat_aborted_word = last_rdata;
        if (stat_aborted_word == 32'd0) $fatal(1, "B95 RX did not report aborted partial frame");
        axi_read(12'h070, 3);
        if (last_rdata[8] !== 1'b1 || last_rdata[7:0] !== uart_bytes[300])
            $fatal(1, "B95 canceled prefix peek mismatch %h", last_rdata);
        $fdisplay(events_fd, "CANCEL_PARTIAL uart=%0d partial=%0d fifo=%0d aborted=%0d",
                  uart_n, uart_partial, fifo_count, stat_aborted_word);

        // Quiet wait proves no hidden replay; then explicit CLEAR_FIFO preserves counters.
        repeat (5000) @(posedge s_axi_aclk);
        rd_ok(12'h018, 32'd0);
        if (uart_n != 301) $fatal(1, "B95 automatic UART replay after cancel");
        axi_read(12'h040, 2); if (last_rdata !== 32'd8)
            $fatal(1, "B95 automatic result after cancel");
        axi_read(12'h03c, 2); discard_word = last_rdata;
        axi_read(12'h034, 2); rx_after = last_rdata;
        axi_read(12'h038, 2); pop_id_word = last_rdata;
        command(8'd7, 2'b00);
        rd_ok(12'h030, 32'd0);
        axi_read(12'h03c, 2);
        if (last_rdata !== discard_word + fifo_count)
            $fatal(1, "B95 CLEAR_FIFO discard count mismatch");
        axi_read(12'h034, 2); if (last_rdata !== rx_after)
            $fatal(1, "B95 CLEAR_FIFO changed rx_total");
        axi_read(12'h038, 2); if (last_rdata !== pop_id_word)
            $fatal(1, "B95 CLEAR_FIFO changed pop_id");
        axi_read(12'h040, 2); if (last_rdata !== 32'd8)
            $fatal(1, "B95 CLEAR_FIFO changed result_id");
        $fdisplay(events_fd, "CLEAR_FIFO discard=%0d rx=%0d pop=%0d result=%0d",
                  fifo_count, rx_after, pop_id_word, 8);

        // Fresh greater ARM demonstrates recovery without a redundant full scan.
        wr_ok(12'h100, 32'h9504);
        wr_ok(12'h104, ORIGIN[31:0]);
        wr_ok(12'h108, ORIGIN[63:32]);
        command(8'd1, 2'b00);
        wait_state(4'd3);
        rd_ok(12'h02c, 32'h9504);
        command(8'd5, 2'b00);
        wait_quiescent;
        repeat (100) @(posedge s_axi_aclk);
        if (uart_n != 301) $fatal(1, "B95 recovery ARM emitted data");
        rd_ok(12'h040, 32'd8);
        rd_ok(12'h01c, 32'd0);
        if (dut.core_uart_tx !== 1'b1) $fatal(1, "B95 main UART not idle high");
        if (dut_zero.core_uart_tx !== 1'b1 || zero_low_events != 0)
            $fatal(1, "B95 zero instance emitted UART activity");
        if (aw_first_count == 0 || w_first_count == 0)
            $fatal(1, "B95 both AXI write orders were not exercised");
        $fdisplay(events_fd, "BUS_ORDERS aw_first=%0d w_first=%0d",
                  aw_first_count, w_first_count);

        $fdisplay(events_fd, "DONE cycles=%0d uart=%0d popped=%0d partial=%0d",
                  cycles, uart_n, popped_total, uart_partial);
        $fflush(events_fd);
        $fclose(uart_fd);
        $fclose(pop_fd);
        $fclose(events_fd);
        $display("B95_DONE cycles=%0d uart=%0d popped=%0d partial=%0d",
                 cycles, uart_n, popped_total, uart_partial);
        completed = 1;
        $finish;
    end
endmodule
`default_nettype wire
