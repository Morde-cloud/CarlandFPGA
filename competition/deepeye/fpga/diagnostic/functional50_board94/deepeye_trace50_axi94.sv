// SOURCE_ONLY / UNEXECUTED private diagnostic endpoint for work94.
// Task DEEPEYE-IMPLEMENTATION-20261014/v1; work
// B-DEEPEYE-TRACE50-AXI-SOURCE-20261030-94.
// Contract DEEPEYE-HUMAN-LOCK-20261014/revision1, H01-H15 canonical SHA256
// c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
// pin f5989cd5defce561f9ba98e6b18fc2682945f0a2;
// freeze 1011259415a0916054eb580687612580bc1e5f09.
//
// This is a SOFTWARE_FIXTURE raw-source endpoint. It is not a production
// BOOT/enable, Root authority, admission decision, calibrated sensor, physical
// UART/electrical result, board test, H12 action path or product acceptance.
// It uses one 50 MHz PS fabric clock, one AXI-Lite 4 KiB aperture, the unchanged
// deepeye_SYNTHETIC_codec74_fixture, and the unchanged deepeye_uart_rx.
// No compile, test, simulation, build or hardware evidence is attached.
`default_nettype none
module deepeye_trace50_axi94 #(
    parameter logic [127:0] BUILD_ID = 128'd0
) (
    input  logic s_axi_aclk,
    input  logic s_axi_aresetn,
    input  logic [11:0] s_axi_awaddr,
    input  logic [2:0] s_axi_awprot,
    input  logic s_axi_awvalid,
    output logic s_axi_awready,
    input  logic [31:0] s_axi_wdata,
    input  logic [3:0] s_axi_wstrb,
    input  logic s_axi_wvalid,
    output logic s_axi_wready,
    output logic [1:0] s_axi_bresp,
    output logic s_axi_bvalid,
    input  logic s_axi_bready,
    input  logic [11:0] s_axi_araddr,
    input  logic [2:0] s_axi_arprot,
    input  logic s_axi_arvalid,
    output logic s_axi_arready,
    output logic [31:0] s_axi_rdata,
    output logic [1:0] s_axi_rresp,
    output logic s_axi_rvalid,
    input  logic s_axi_rready
);
    localparam logic [31:0] MAGIC = 32'h54353046;
    localparam logic [31:0] LAYOUT = 32'd1;
    localparam logic [31:0] SOURCE_KIND = 32'd4;
    localparam logic [31:0] CLOCK_HZ = 32'd50000000;
    localparam logic [31:0] BAUD = 32'd1000000;
    localparam logic [31:0] FIFO_CAPACITY = 32'd4096;
    localparam logic [1:0] RESP_OKAY = 2'b00;
    localparam logic [1:0] RESP_SLVERR = 2'b10;
    localparam logic [3:0] ST_CANCEL = 4'd0;
    localparam logic [3:0] ST_ARM_WAIT = 4'd1;
    localparam logic [3:0] ST_ARM_SETTLE = 4'd2;
    localparam logic [3:0] ST_ARMED = 4'd3;
    localparam logic [3:0] ST_CAPTURED = 4'd4;
    localparam logic [3:0] ST_BINDING = 4'd5;
    localparam logic [3:0] ST_WAIT_RESULT = 4'd6;
    localparam logic [3:0] ST_RESULT_READY = 4'd7;
    localparam logic [3:0] ST_WAIT_CORE_IDLE = 4'd8;
    localparam logic [3:0] ST_COMPLETE = 4'd9;
    localparam logic [7:0] CMD_ARM = 8'd1;
    localparam logic [7:0] CMD_PUSH = 8'd2;
    localparam logic [7:0] CMD_BIND = 8'd3;
    localparam logic [7:0] CMD_ACK = 8'd4;
    localparam logic [7:0] CMD_CANCEL = 8'd5;
    localparam logic [7:0] CMD_CLEAR_FAULT = 8'd6;
    localparam logic [7:0] CMD_CLEAR_FIFO = 8'd7;
    localparam logic [7:0] CMD_POP = 8'd8;

    // Asynchronous assertion and two-cycle synchronous release.
    (* ASYNC_REG = "TRUE" *) logic [1:0] reset_release_q;
    always_ff @(posedge s_axi_aclk or negedge s_axi_aresetn) begin
        if (!s_axi_aresetn) reset_release_q <= 2'b00;
        else reset_release_q <= {reset_release_q[0], 1'b1};
    end
    wire rst_n_sync = reset_release_q[1];
    wire rst = !rst_n_sync;

    // Independent one-slot AW/W capture and held B/R response.
    logic aw_full_q, w_full_q;
    logic [11:0] aw_addr_q;
    logic [31:0] w_data_q;
    logic [3:0] w_strb_q;
    logic bvalid_q;
    logic [1:0] bresp_q;
    logic rvalid_q;
    logic [31:0] rdata_q;
    logic [1:0] rresp_q;
    logic [31:0] read_word_c;
    logic read_ok_c;
    logic write_accept;

    assign s_axi_awready = !rst && !aw_full_q && !bvalid_q;
    assign s_axi_wready  = !rst && !w_full_q && !bvalid_q;
    assign s_axi_arready = !rst && !rvalid_q;
    assign s_axi_bvalid  = bvalid_q;
    assign s_axi_bresp   = bresp_q;
    assign s_axi_rvalid  = rvalid_q;
    assign s_axi_rdata   = rdata_q;
    assign s_axi_rresp   = rresp_q;
    assign write_accept  = aw_full_q && w_full_q && !bvalid_q && !rst;

    // All writable/protocol state lives in this one 50 MHz domain.
    logic [31:0] arm_tag_q, origin_low_q, origin_high_q;
    logic [31:0] sample_channel_q, sample_data_q, sample_tick_low_q;
    logic [31:0] sample_tick_high_q, sample_quality_q;
    logic [31:0] assoc_session_q, assoc_first_index_q, assoc_acq_tick_q;
    logic [31:0] assoc_acq_rem_q, assoc_source_ns_low_q, assoc_source_ns_high_q;
    logic [31:0] assoc_source_tick_q, assoc_source_rem_q, assoc_epoch_q;
    logic [31:0] assoc_frame_seq_q, expected_result_id_q, expected_pop_id_q;
    logic [2:0] arm_fresh_q;
    logic [4:0] sample_fresh_q;
    logic [9:0] assoc_fresh_q;
    logic ack_id_fresh_q, pop_id_fresh_q;

    // Local fixture identity, saturating/refused counters, and held result.
    logic [3:0] state_q;
    logic [31:0] last_arm_tag_q, scan_tag_q, scan_origin_low_q, scan_origin_high_q;
    logic [2:0] push_count_q, assoc_next_q;
    logic [63:0] scan_tick_q;
    logic [15:0] scan_quality_q;
    logic [31:0] last_frame_seq_q;
    logic frame_seen_q;
    logic [31:0] last_cmd_q, refusal_q;
    logic [31:0] result_id_q, result_rx_start_q, result_rx_end_q;
    logic [2:0] result_error_q;
    logic [5:0] result_bytes_q;
    logic result_visible_q, result_canceled_q;
    logic [31:0] sticky_fault_q;

    // Association descriptor retained across the actual core handshake.
    logic [31:0] bind_session_q, bind_first_index_q, bind_acq_tick_q;
    logic [31:0] bind_source_tick_q, bind_source_ns_low_q, bind_source_ns_high_q;
    logic [9:0] bind_acq_rem_q, bind_source_rem_q;
    logic [7:0] bind_epoch_q;
    logic [15:0] bind_seq_q;
    logic bind_valid_q, bind_saturated_q, bind_held_q, bind_source_fault_q;

    // UART byte ingress and the non-overwriting 4096-byte raw ring.
    logic [11:0] fifo_wr_q, fifo_rd_q;
    logic [12:0] fifo_count_q;
    logic [7:0] fifo_mem [0:4095];
    logic [31:0] rx_total_q, pop_id_q, discard_count_q;
    logic fifo_pop_fire, fifo_clear_fire, rx_fire, fifo_overflow_event;
    logic counter_fault_event;

    // Core-visible source/cancellation/rearm signals and observations.
    logic sample_strobe_c, capture_rearm_c;
    logic [1:0] sample_channel_c;
    logic [15:0] sample_data_c;
    logic [63:0] sample_tick_c;
    logic [7:0] sample_quality_c;
    logic core_assoc_valid, core_assoc_ready;
    logic core_trace_lane_ready, core_uart_tx, core_result_valid;
    logic core_result_ready, core_wire_faulted, core_transport_unset;
    logic core_data_path_quiescent, core_capture_fault_event;
    logic core_capture_sequence_exhausted, core_transaction_aborted;
    logic [31:0] core_capture_discarded;
    logic [2:0] core_result_error;
    logic [5:0] core_result_bytes;
    logic [3:0] core_refusal_code;

    logic rx_out_valid, rx_busy;
    logic [7:0] rx_out_data;
    logic rx_framing_error_event, rx_overrun_event, rx_false_start_event;
    logic [31:0] rx_stat_frames, rx_stat_retired, rx_stat_overruns;
    logic [31:0] rx_stat_framing, rx_stat_false_starts, rx_stat_aborted;

    // Local command/resolution signals; no AXI response depends on valid.
    logic write_aligned_c, write_strobe_ok_c, write_is_stage_c, write_is_cmd_c;
    logic write_route_ok_c, write_bresp_error_c;
    logic [7:0] command_code_c;
    logic command_known_c, command_ok_c;
    logic cmd_arm_c, cmd_push_c, cmd_bind_c, cmd_ack_c;
    logic cmd_cancel_c, cmd_clear_fault_c, cmd_clear_fifo_c, cmd_pop_c;
    logic arm_ok_c, push_ok_c, bind_ok_c, ack_ok_c, clear_fault_ok_c;
    logic clear_fifo_ok_c, pop_ok_c;
    logic faults_now_c;
    logic [31:0] fault_events_c;
    logic rx_idle_c;
    logic push_pulse_c, ack_pulse_c, fixture_gates_c;
    logic bind_quality_valid_c, bind_quality_saturated_c;
    logic bind_quality_held_c, bind_quality_source_fault_c;
    logic [63:0] push_tick_c, bind_acq_tick64_c;
    logic [64:0] bind_acq_sum_c;
    logic [63:0] bind_source_tick64_c;
    logic [64:0] bind_source_sum_c;
    logic [63:0] bind_source_ns_c;
    logic bind_time_ok_c, bind_flags_ok_c, bind_source_le_acq_c;
    logic bind_acq_matches_scan_c, bind_source_matches_ns_c;
    logic bind_held_expected_c;
    logic [32:0] result_expected_end_ext_c;
    logic [31:0] result_expected_end_c;
    logic result_success_ready_c, result_refused_ready_c;
    logic result_excess_c, result_missing_c;
    logic [3:0] bind_quality_sel_c;
    logic [31:0] other_faults_c;
    logic pop_intent_c, clear_intent_c, pop_candidate_c;
    logic [32:0] discard_sum_ext_c;
    // Exact register offsets. Unknown, misaligned, read-only writes and partial
    // strobes are rejected without changing endpoint state.
    assign write_aligned_c = (aw_addr_q[1:0] == 2'b00);
    assign write_strobe_ok_c = (w_strb_q == 4'hf);
    assign write_is_cmd_c = (aw_addr_q == 12'h080);
    assign write_is_stage_c =
        (aw_addr_q == 12'h100) || (aw_addr_q == 12'h104) ||
        (aw_addr_q == 12'h108) || (aw_addr_q == 12'h110) ||
        (aw_addr_q == 12'h114) || (aw_addr_q == 12'h118) ||
        (aw_addr_q == 12'h11c) || (aw_addr_q == 12'h120) ||
        (aw_addr_q == 12'h130) || (aw_addr_q == 12'h134) ||
        (aw_addr_q == 12'h138) || (aw_addr_q == 12'h13c) ||
        (aw_addr_q == 12'h140) || (aw_addr_q == 12'h144) ||
        (aw_addr_q == 12'h148) || (aw_addr_q == 12'h14c) ||
        (aw_addr_q == 12'h150) || (aw_addr_q == 12'h154) ||
        (aw_addr_q == 12'h160) || (aw_addr_q == 12'h164);
    assign write_route_ok_c = write_aligned_c && write_strobe_ok_c &&
        (write_is_stage_c || write_is_cmd_c);
    assign command_code_c = w_data_q[7:0];
    // Staging data must never decode as a command or pulse the core/FIFO.
    assign command_known_c = write_is_cmd_c && (w_data_q[31:8] == 24'd0) &&
        (command_code_c >= CMD_ARM) && (command_code_c <= CMD_POP);
    assign cmd_arm_c = command_known_c && (command_code_c == CMD_ARM);
    assign cmd_push_c = command_known_c && (command_code_c == CMD_PUSH);
    assign cmd_bind_c = command_known_c && (command_code_c == CMD_BIND);
    assign cmd_ack_c = command_known_c && (command_code_c == CMD_ACK);
    assign cmd_cancel_c = command_known_c && (command_code_c == CMD_CANCEL);
    assign cmd_clear_fault_c = command_known_c && (command_code_c == CMD_CLEAR_FAULT);
    assign cmd_clear_fifo_c = command_known_c && (command_code_c == CMD_CLEAR_FIFO);
    assign cmd_pop_c = command_known_c && (command_code_c == CMD_POP);

    // Exact source/tick reconstruction, with reserved high-bit checks kept
    // outside the truncating arithmetic itself.
    assign push_tick_c = {1'b0, sample_tick_high_q[30:0], sample_tick_low_q};
    assign bind_acq_tick64_c = {32'b0, assoc_acq_tick_q};
    assign bind_acq_sum_c = {2'b0, scan_origin_high_q[30:0], scan_origin_low_q} +
        {1'b0, (bind_acq_tick64_c * 64'd1000)} +
        {54'b0, assoc_acq_rem_q};
    assign bind_source_tick64_c = {32'b0, assoc_source_tick_q};
    assign bind_source_ns_c = {assoc_source_ns_high_q[30:0], assoc_source_ns_low_q};
    assign bind_source_sum_c = {2'b0, scan_origin_high_q[30:0], scan_origin_low_q} +
        {1'b0, (bind_source_tick64_c * 64'd1000)} +
        {54'b0, assoc_source_rem_q};
    assign bind_acq_matches_scan_c = (bind_acq_sum_c[63:0] == scan_tick_q);
    assign bind_source_matches_ns_c =
        (bind_source_sum_c[63:0] == bind_source_ns_c);
    assign bind_source_le_acq_c = (bind_source_ns_c <= bind_acq_sum_c[62:0]);
    assign bind_held_expected_c = (bind_source_ns_c < bind_acq_sum_c[62:0]);

    always_comb begin
        case (assoc_next_q)
            3'd0: bind_quality_sel_c = scan_quality_q[3:0];
            3'd1: bind_quality_sel_c = scan_quality_q[7:4];
            3'd2: bind_quality_sel_c = scan_quality_q[11:8];
            3'd3: bind_quality_sel_c = scan_quality_q[15:12];
            default: bind_quality_sel_c = 4'd0;
        endcase
    end
    assign bind_quality_valid_c = bind_quality_sel_c[0];
    assign bind_quality_saturated_c = bind_quality_sel_c[1];
    assign bind_quality_held_c = bind_quality_sel_c[2];
    assign bind_quality_source_fault_c = bind_quality_sel_c[3];

    assign arm_ok_c = (state_q == ST_CANCEL) && (arm_fresh_q == 3'b111) &&
        (BUILD_ID != 128'd0) && (origin_high_q[31] == 1'b0) &&
        (arm_tag_q != 32'd0) && (arm_tag_q > last_arm_tag_q) &&
        core_data_path_quiescent && rx_idle_c && (fifo_count_q == 13'd0) &&
        !core_result_valid && !result_visible_q && (sticky_fault_q == 32'd0);

    assign push_ok_c = (state_q == ST_ARMED) && (push_count_q < 3'd4) &&
        (sample_fresh_q == 5'b11111) &&
        (sample_channel_q[31:2] == 30'd0) &&
        (sample_data_q[31:16] == 16'd0) &&
        (sample_tick_high_q[31] == 1'b0) &&
        (sample_quality_q[31:4] == 28'd0) &&
        (sample_channel_q[1:0] == push_count_q[1:0]) &&
        ((push_count_q == 3'd0) || (push_tick_c == scan_tick_q)) &&
        (sample_quality_q[0] || (!sample_quality_q[1] && !sample_quality_q[2])) &&
        (sample_quality_q[0] || (sample_data_q[15:0] == 16'd0));

    assign bind_time_ok_c = (assoc_acq_rem_q < 32'd1000) &&
        (assoc_source_ns_high_q[31] == 1'b0) &&
        (assoc_source_rem_q < 32'd1000) &&
        (assoc_epoch_q[31:8] == 24'd0) &&
        (assoc_frame_seq_q[31:16] == 16'd0) &&
        (bind_acq_sum_c[64] == 1'b0) &&
        (bind_acq_sum_c[63] == 1'b0) &&
        bind_acq_matches_scan_c &&
        (!bind_quality_valid_c ||
            ((bind_source_sum_c[64] == 1'b0) &&
             (bind_source_sum_c[63] == 1'b0) &&
             bind_source_matches_ns_c &&
             bind_source_le_acq_c &&
             (bind_quality_held_c == bind_held_expected_c)));
    assign bind_flags_ok_c = bind_quality_valid_c ||
        (!bind_quality_saturated_c && !bind_quality_held_c);
    assign bind_ok_c = (state_q == ST_CAPTURED) && (push_count_q == 3'd4) &&
        (assoc_next_q < 3'd4) && (assoc_fresh_q == 10'h3ff) &&
        !core_result_valid && rx_idle_c && !result_visible_q &&
        (result_id_q != 32'hffffffff) && bind_time_ok_c && bind_flags_ok_c &&
        (!frame_seen_q ||
            ({16'b0, assoc_frame_seq_q[15:0]} > {16'b0, last_frame_seq_q[15:0]}));
    assign ack_ok_c = (state_q == ST_RESULT_READY) && result_visible_q &&
        core_result_valid &&
        ack_id_fresh_q && (expected_result_id_q == result_id_q) &&
        (result_id_q != 32'd0);
    assign clear_fault_ok_c = (state_q == ST_CANCEL) &&
        core_data_path_quiescent && rx_idle_c && !result_visible_q &&
        !core_result_valid;
    assign discard_sum_ext_c = {1'b0, discard_count_q} +
        {20'b0, fifo_count_q};
    assign clear_fifo_ok_c = (state_q == ST_CANCEL) &&
        core_data_path_quiescent && rx_idle_c && !core_result_valid &&
        !result_visible_q && (discard_sum_ext_c[32] == 1'b0);
    assign pop_ok_c = ((state_q == ST_CANCEL) || (state_q == ST_COMPLETE)) &&
        pop_id_fresh_q && (fifo_count_q != 13'd0) &&
        (pop_id_q != 32'hffffffff) && (expected_pop_id_q == (pop_id_q + 32'd1));

    always_comb begin
        command_ok_c = 1'b0;
        case (command_code_c)
            CMD_ARM: command_ok_c = arm_ok_c;
            CMD_PUSH: command_ok_c = push_ok_c;
            CMD_BIND: command_ok_c = bind_ok_c;
            CMD_ACK: command_ok_c = ack_ok_c;
            CMD_CANCEL: command_ok_c = 1'b1;
            CMD_CLEAR_FAULT: command_ok_c = clear_fault_ok_c;
            CMD_CLEAR_FIFO: command_ok_c = clear_fifo_ok_c;
            CMD_POP: command_ok_c = pop_ok_c;
            default: command_ok_c = 1'b0;
        endcase
    end

    // FIFO and command effects share only the ring/counter registers. Pop is
    // evaluated before capacity overflow, avoiding combinational dependence on
    // its own effect while still permitting one full-and-pop replacement.
    assign pop_intent_c = write_accept && write_route_ok_c &&
        cmd_pop_c && pop_ok_c;
    assign clear_intent_c = write_accept && write_route_ok_c &&
        cmd_clear_fifo_c && clear_fifo_ok_c;
    assign pop_candidate_c = pop_intent_c && (other_faults_c == 32'd0);
    assign fifo_overflow_event = rx_out_valid &&
        (fifo_count_q == 13'd4096) && !pop_candidate_c;
    assign counter_fault_event =
        (rx_out_valid && (rx_total_q == 32'hffffffff) &&
         ((fifo_count_q != 13'd4096) || pop_candidate_c)) ||
        (clear_intent_c && discard_sum_ext_c[32]);
    assign fifo_pop_fire = pop_candidate_c && !counter_fault_event;
    assign fifo_clear_fire = clear_intent_c && !faults_now_c;
    assign rx_fire = rx_out_valid && (other_faults_c == 32'd0) &&
        !fifo_overflow_event && !counter_fault_event &&
        (rx_total_q != 32'hffffffff) &&
        ((fifo_count_q != 13'd4096) || pop_candidate_c);

    assign result_expected_end_ext_c = {1'b0, result_rx_start_q} +
        {27'b0, core_result_bytes};
    assign result_expected_end_c = result_expected_end_ext_c[31:0];
    assign result_refused_ready_c = (state_q == ST_WAIT_RESULT) &&
        core_result_valid && (core_result_error != 3'd0) && rx_idle_c;
    assign result_success_ready_c = (state_q == ST_WAIT_RESULT) &&
        core_result_valid && (core_result_error == 3'd0) && rx_idle_c &&
        !result_expected_end_ext_c[32] &&
        (rx_total_q == result_expected_end_c);
    assign result_excess_c = (state_q == ST_WAIT_RESULT) &&
        core_result_valid && (core_result_error == 3'd0) &&
        (result_expected_end_ext_c[32] ||
         (rx_total_q > result_expected_end_c));
    assign result_missing_c = (state_q == ST_WAIT_RESULT) &&
        core_result_valid && (core_result_error == 3'd0) && rx_idle_c &&
        !result_expected_end_ext_c[32] &&
        (rx_total_q < result_expected_end_c);

    assign other_faults_c =
        ({31'b0, core_capture_fault_event || core_capture_sequence_exhausted}) |
        (rx_framing_error_event ? 32'h0000_0004 : 32'd0) |
        (rx_overrun_event ? 32'h0000_0008 : 32'd0) |
        (rx_false_start_event ? 32'h0000_0010 : 32'd0) |
        (result_excess_c ? 32'h0000_0020 : 32'd0) |
        (result_missing_c ? 32'h0000_0040 : 32'd0) |
        32'd0;
    assign fault_events_c = other_faults_c |
        (fifo_overflow_event ? 32'h0000_0002 : 32'd0) |
        (counter_fault_event ? 32'h0000_0080 : 32'd0);
    assign faults_now_c = (fault_events_c != 32'd0);
    assign write_bresp_error_c = !write_route_ok_c ||
        (write_accept && faults_now_c) ||
        (write_accept && write_is_cmd_c &&
         (!command_known_c || !command_ok_c));
    assign ack_pulse_c = write_accept && write_route_ok_c && !faults_now_c &&
        cmd_ack_c && ack_ok_c;
    assign push_pulse_c = write_accept && write_route_ok_c && !faults_now_c &&
        cmd_push_c && push_ok_c;
    assign fixture_gates_c = (state_q == ST_ARMED) ||
        (state_q == ST_CAPTURED) || (state_q == ST_BINDING) ||
        (state_q == ST_WAIT_RESULT) || (state_q == ST_RESULT_READY) ||
        (state_q == ST_WAIT_CORE_IDLE) || (state_q == ST_COMPLETE);

    // The core uses the unchanged 74 fixture and exact existing single codec.
    deepeye_SYNTHETIC_codec74_fixture #(
        .CLOCK_HZ(50000000), .BAUD(1000000), .SOURCE_REVIEW_HOLD(1'b0)
    ) core_i (
        .fclk50_candidate(s_axi_aclk),
        .peripheral_aresetn_candidate(s_axi_aresetn),
        .sample_strobe(sample_strobe_c),
        .sample_channel(sample_channel_c),
        .sample_data(sample_data_c),
        .sample_tick(sample_tick_c),
        .sample_quality(sample_quality_c),
        .source_cancel(state_q == ST_CANCEL),
        .capture_stop(1'b0),
        .capture_rearm(capture_rearm_c),
        .capture_rearm_tag(scan_tag_q),
        .queue_cancel(1'b0),
        .lane_cancel(1'b0),
        .assoc_valid(core_assoc_valid),
        .assoc_ready(core_assoc_ready),
        .assoc_tag(scan_tag_q),
        .assoc_first_seq(32'd0),
        .assoc_last_seq(32'd3),
        .assoc_channel(assoc_next_q[1:0]),
        .assoc_session(bind_session_q),
        .assoc_first_index(bind_first_index_q),
        .assoc_count(8'd1),
        .assoc_e(4'd0),
        .assoc_index_stride(16'd0),
        .assoc_tick_stride_us(16'd0),
        .assoc_first_qpc_ns(scan_tick_q),
        .assoc_first_tick_us({32'b0, bind_acq_tick_q}),
        .assoc_first_remainder_ns(bind_acq_rem_q),
        .assoc_tick_stride_ns(64'd0),
        .assoc_origin_qpc_ns({scan_origin_high_q[30:0], scan_origin_low_q}),
        .assoc_origin_tick_us(64'd0),
        .assoc_origin_remainder_ns(10'd0),
        .assoc_semantics_valid(1'b1),
        .assoc_valid_sample(bind_valid_q),
        .assoc_saturated(bind_saturated_q),
        .assoc_held(bind_held_q),
        .assoc_source_fault(bind_source_fault_q),
        .assoc_source_qpc_ns(bind_valid_q ?
            {1'b0, bind_source_ns_high_q[30:0], bind_source_ns_low_q} : 64'd0),
        .assoc_source_tick_us(bind_valid_q ?
            {32'b0, bind_source_tick_q} : 64'd0),
        .assoc_source_remainder_ns(bind_valid_q ?
            bind_source_rem_q : 10'd0),
        .assoc_epoch(bind_epoch_q),
        .assoc_seq(bind_seq_q),
        .trace_lane_ready(core_trace_lane_ready),
        .trace_uart_tx(core_uart_tx),
        .trace_transaction_aborted(core_transaction_aborted),
        .trace_result_valid(core_result_valid),
        .trace_result_error(core_result_error),
        .trace_result_bytes(core_result_bytes),
        .trace_refusal_code(core_refusal_code),
        .trace_wire_faulted(core_wire_faulted),
        .trace_transport_profile_unset(core_transport_unset),
        .data_path_quiescent(core_data_path_quiescent),
        .capture_fault_event(core_capture_fault_event),
        .capture_sequence_exhausted(core_capture_sequence_exhausted),
        .capture_discarded_samples(core_capture_discarded),
        .fixture_profile_enabled(fixture_gates_c),
        .fixture_transport_enabled(fixture_gates_c),
        .fixture_result_ready(core_result_ready)
    );

    // Actual source bytes are received unchanged; the 1 MHz rate is below the
    // unchanged receiver's 50 MHz / 16 eligibility limit.
    deepeye_uart_rx #(
        .CLOCK_HZ(50000000), .BAUD(1000000), .STAT_W(32)
    ) raw_rx_i (
        .clk(s_axi_aclk), .rst(rst), .cancel(state_q == ST_CANCEL),
        .rx_async(core_uart_tx),
        .out_ready((other_faults_c == 32'd0) && !fifo_overflow_event &&
            !counter_fault_event && (rx_total_q != 32'hffffffff)),
        .out_valid(rx_out_valid), .out_data(rx_out_data), .busy(rx_busy),
        .framing_error_event(rx_framing_error_event),
        .overrun_event(rx_overrun_event),
        .false_start_event(rx_false_start_event),
        .stat_frames(rx_stat_frames), .stat_retired(rx_stat_retired),
        .stat_overruns(rx_stat_overruns), .stat_framing(rx_stat_framing),
        .stat_false_starts(rx_stat_false_starts),
        .stat_aborted(rx_stat_aborted)
    );
    assign sample_strobe_c = push_pulse_c;
    assign capture_rearm_c = (state_q == ST_ARM_WAIT);
    assign sample_channel_c = sample_channel_q[1:0];
    assign sample_data_c = sample_data_q[15:0];
    assign sample_tick_c = push_tick_c;
    assign sample_quality_c = {4'b0, sample_quality_q[3:0]};
    assign rx_idle_c = !rx_busy && !rx_out_valid;
    assign core_assoc_valid = (state_q == ST_BINDING);
    assign core_result_ready = ack_pulse_c;
    // FIFO write/pop are specified together so a full FIFO may replace exactly
    // one simultaneously popped item but can never overwrite without that pop.
    always_ff @(posedge s_axi_aclk or negedge rst_n_sync) begin
        if (rst) begin
            fifo_wr_q <= 12'd0;
            fifo_rd_q <= 12'd0;
            fifo_count_q <= 13'd0;
            rx_total_q <= 32'd0;
            pop_id_q <= 32'd0;
            discard_count_q <= 32'd0;
        end else if (fifo_clear_fire) begin
            fifo_wr_q <= 12'd0;
            fifo_rd_q <= 12'd0;
            fifo_count_q <= 13'd0;
            discard_count_q <= discard_sum_ext_c[31:0];
        end else begin
            if (rx_fire) begin
                fifo_mem[fifo_wr_q] <= rx_out_data;
                fifo_wr_q <= fifo_wr_q + 12'd1;
                if (rx_total_q != 32'hffffffff)
                    rx_total_q <= rx_total_q + 32'd1;
            end
            if (fifo_pop_fire) begin
                fifo_rd_q <= fifo_rd_q + 12'd1;
                pop_id_q <= pop_id_q + 32'd1;
            end
            case ({rx_fire, fifo_pop_fire})
                2'b10: fifo_count_q <= fifo_count_q + 13'd1;
                2'b01: fifo_count_q <= fifo_count_q - 13'd1;
                default: fifo_count_q <= fifo_count_q;
            endcase
        end
    end

    // State, retained fixture identity, command consumption, result and fault.
    always_ff @(posedge s_axi_aclk or negedge rst_n_sync) begin
        if (rst) begin
            aw_full_q <= 1'b0;
            w_full_q <= 1'b0;
            aw_addr_q <= 12'd0;
            w_data_q <= 32'd0;
            w_strb_q <= 4'd0;
            bvalid_q <= 1'b0;
            bresp_q <= RESP_OKAY;
            rvalid_q <= 1'b0;
            rdata_q <= 32'd0;
            rresp_q <= RESP_OKAY;
            arm_tag_q <= 32'd0;
            origin_low_q <= 32'd0;
            origin_high_q <= 32'd0;
            sample_channel_q <= 32'd0;
            sample_data_q <= 32'd0;
            sample_tick_low_q <= 32'd0;
            sample_tick_high_q <= 32'd0;
            sample_quality_q <= 32'd0;
            assoc_session_q <= 32'd0;
            assoc_first_index_q <= 32'd0;
            assoc_acq_tick_q <= 32'd0;
            assoc_acq_rem_q <= 32'd0;
            assoc_source_ns_low_q <= 32'd0;
            assoc_source_ns_high_q <= 32'd0;
            assoc_source_tick_q <= 32'd0;
            assoc_source_rem_q <= 32'd0;
            assoc_epoch_q <= 32'd0;
            assoc_frame_seq_q <= 32'd0;
            expected_result_id_q <= 32'd0;
            expected_pop_id_q <= 32'd0;
            arm_fresh_q <= 3'd0;
            sample_fresh_q <= 5'd0;
            assoc_fresh_q <= 10'd0;
            ack_id_fresh_q <= 1'b0;
            pop_id_fresh_q <= 1'b0;
            state_q <= ST_CANCEL;
            last_arm_tag_q <= 32'd0;
            scan_tag_q <= 32'd0;
            scan_origin_low_q <= 32'd0;
            scan_origin_high_q <= 32'd0;
            push_count_q <= 3'd0;
            assoc_next_q <= 3'd0;
            scan_tick_q <= 64'd0;
            scan_quality_q <= 16'd0;
            last_frame_seq_q <= 32'd0;
            frame_seen_q <= 1'b0;
            last_cmd_q <= 32'd0;
            refusal_q <= 32'd0;
            result_id_q <= 32'd0;
            result_rx_start_q <= 32'd0;
            result_rx_end_q <= 32'd0;
            result_error_q <= 3'd0;
            result_bytes_q <= 6'd0;
            result_visible_q <= 1'b0;
            result_canceled_q <= 1'b0;
            sticky_fault_q <= 32'd0;
            bind_session_q <= 32'd0;
            bind_first_index_q <= 32'd0;
            bind_acq_tick_q <= 32'd0;
            bind_source_tick_q <= 32'd0;
            bind_source_ns_low_q <= 32'd0;
            bind_source_ns_high_q <= 32'd0;
            bind_acq_rem_q <= 10'd0;
            bind_source_rem_q <= 10'd0;
            bind_epoch_q <= 8'd0;
            bind_seq_q <= 16'd0;
            bind_valid_q <= 1'b0;
            bind_saturated_q <= 1'b0;
            bind_held_q <= 1'b0;
            bind_source_fault_q <= 1'b0;
        end else begin
            // B/R response registers are independent of persistence. A stalled
            // response is held unchanged and a captured AW/W pair is consumed once.
            if (write_accept) begin
                bvalid_q <= 1'b1;
                bresp_q <= write_bresp_error_c ? RESP_SLVERR : RESP_OKAY;
            end else if (bvalid_q && s_axi_bready) begin
                bvalid_q <= 1'b0;
            end
            if (s_axi_arvalid && s_axi_arready) begin
                rvalid_q <= 1'b1;
                rdata_q <= read_word_c;
                rresp_q <= read_ok_c ? RESP_OKAY : RESP_SLVERR;
            end else if (rvalid_q && s_axi_rready) begin
                rvalid_q <= 1'b0;
            end
            if (s_axi_awvalid && s_axi_awready) begin
                aw_addr_q <= s_axi_awaddr;
                aw_full_q <= 1'b1;
            end
            if (s_axi_wvalid && s_axi_wready) begin
                w_data_q <= s_axi_wdata;
                w_strb_q <= s_axi_wstrb;
                w_full_q <= 1'b1;
            end
            if (write_accept) begin
                aw_full_q <= 1'b0;
                w_full_q <= 1'b0;
            end

            if (faults_now_c) begin
                sticky_fault_q <= sticky_fault_q | fault_events_c;
                if (result_visible_q || (state_q != ST_CANCEL))
                    result_canceled_q <= 1'b1;
                state_q <= ST_CANCEL;
                result_visible_q <= 1'b0;
                arm_fresh_q <= 3'd0;
                sample_fresh_q <= 5'd0;
                assoc_fresh_q <= 10'd0;
                ack_id_fresh_q <= 1'b0;
                pop_id_fresh_q <= 1'b0;
            end else begin                // Actual core handshake and result progress precedes explicit
                // commands below, so CANCEL wins if both occur on one edge.
                case (state_q)
                    ST_ARM_WAIT: state_q <= ST_ARM_SETTLE;
                    ST_ARM_SETTLE: state_q <= ST_ARMED;
                    ST_BINDING: if (core_assoc_ready) begin
                        assoc_next_q <= assoc_next_q + 3'd1;
                        state_q <= ST_WAIT_RESULT;
                    end
                    ST_WAIT_RESULT: if (result_success_ready_c ||
                                         result_refused_ready_c) begin
                        result_error_q <= core_result_error;
                        result_bytes_q <= core_result_bytes;
                        result_rx_end_q <= rx_total_q;
                        refusal_q <= {28'd0, core_refusal_code};
                        result_id_q <= result_id_q + 32'd1;
                        result_visible_q <= 1'b1;
                        result_canceled_q <= 1'b0;
                        state_q <= ST_RESULT_READY;
                    end
                    ST_WAIT_CORE_IDLE: if (!core_result_valid)
                        state_q <= (assoc_next_q == 3'd4) ?
                            ST_COMPLETE : ST_CAPTURED;
                    default: begin end
                endcase

                if (write_accept && write_route_ok_c) begin
                    if (write_is_stage_c) begin
                        case (aw_addr_q)
                            12'h100: begin
                                arm_tag_q <= w_data_q;
                                arm_fresh_q[0] <= 1'b1;
                            end
                            12'h104: begin
                                origin_low_q <= w_data_q;
                                arm_fresh_q[1] <= 1'b1;
                            end
                            12'h108: begin
                                origin_high_q <= w_data_q;
                                arm_fresh_q[2] <= 1'b1;
                            end
                            12'h110: begin
                                sample_channel_q <= w_data_q;
                                sample_fresh_q[0] <= 1'b1;
                            end
                            12'h114: begin
                                sample_data_q <= w_data_q;
                                sample_fresh_q[1] <= 1'b1;
                            end
                            12'h118: begin
                                sample_tick_low_q <= w_data_q;
                                sample_fresh_q[2] <= 1'b1;
                            end
                            12'h11c: begin
                                sample_tick_high_q <= w_data_q;
                                sample_fresh_q[3] <= 1'b1;
                            end
                            12'h120: begin
                                sample_quality_q <= w_data_q;
                                sample_fresh_q[4] <= 1'b1;
                            end
                            12'h130: begin
                                assoc_session_q <= w_data_q;
                                assoc_fresh_q[0] <= 1'b1;
                            end
                            12'h134: begin
                                assoc_first_index_q <= w_data_q;
                                assoc_fresh_q[1] <= 1'b1;
                            end
                            12'h138: begin
                                assoc_acq_tick_q <= w_data_q;
                                assoc_fresh_q[2] <= 1'b1;
                            end
                            12'h13c: begin
                                assoc_acq_rem_q <= w_data_q;
                                assoc_fresh_q[3] <= 1'b1;
                            end
                            12'h140: begin
                                assoc_source_ns_low_q <= w_data_q;
                                assoc_fresh_q[4] <= 1'b1;
                            end
                            12'h144: begin
                                assoc_source_ns_high_q <= w_data_q;
                                assoc_fresh_q[5] <= 1'b1;
                            end
                            12'h148: begin
                                assoc_source_tick_q <= w_data_q;
                                assoc_fresh_q[6] <= 1'b1;
                            end
                            12'h14c: begin
                                assoc_source_rem_q <= w_data_q;
                                assoc_fresh_q[7] <= 1'b1;
                            end
                            12'h150: begin
                                assoc_epoch_q <= w_data_q;
                                assoc_fresh_q[8] <= 1'b1;
                            end
                            12'h154: begin
                                assoc_frame_seq_q <= w_data_q;
                                assoc_fresh_q[9] <= 1'b1;
                            end
                            12'h160: begin
                                expected_result_id_q <= w_data_q;
                                ack_id_fresh_q <= 1'b1;
                            end
                            12'h164: begin
                                expected_pop_id_q <= w_data_q;
                                pop_id_fresh_q <= 1'b1;
                            end
                            default: begin end
                        endcase
                    end else if (write_is_cmd_c && command_known_c) begin
                        last_cmd_q <= {24'd0, command_code_c};
                        case (command_code_c)
                            CMD_ARM: if (arm_ok_c) begin
                                refusal_q <= 32'd0;
                                last_arm_tag_q <= arm_tag_q;
                                scan_tag_q <= arm_tag_q;
                                scan_origin_low_q <= origin_low_q;
                                scan_origin_high_q <= origin_high_q;
                                push_count_q <= 3'd0;
                                assoc_next_q <= 3'd0;
                                scan_tick_q <= 64'd0;
                                scan_quality_q <= 16'd0;
                                last_frame_seq_q <= 32'd0;
                                frame_seen_q <= 1'b0;
                                result_error_q <= 3'd0;
                                result_bytes_q <= 6'd0;
                                result_visible_q <= 1'b0;
                                result_canceled_q <= 1'b0;
                                arm_fresh_q <= 3'd0;
                                sample_fresh_q <= 5'd0;
                                assoc_fresh_q <= 10'd0;
                                ack_id_fresh_q <= 1'b0;
                                pop_id_fresh_q <= 1'b0;
                                state_q <= ST_ARM_WAIT;
                            end
                            CMD_PUSH: if (push_ok_c) begin
                                sample_fresh_q <= 5'd0;
                                if (push_count_q == 3'd0)
                                    scan_tick_q <= push_tick_c;
                                case (push_count_q)
                                    3'd0: scan_quality_q[3:0] <=
                                        sample_quality_q[3:0];
                                    3'd1: scan_quality_q[7:4] <=
                                        sample_quality_q[3:0];
                                    3'd2: scan_quality_q[11:8] <=
                                        sample_quality_q[3:0];
                                    3'd3: scan_quality_q[15:12] <=
                                        sample_quality_q[3:0];
                                    default: begin end
                                endcase
                                push_count_q <= push_count_q + 3'd1;
                                if (push_count_q == 3'd3)
                                    state_q <= ST_CAPTURED;
                            end
                            CMD_BIND: if (bind_ok_c) begin
                                refusal_q <= 32'd0;
                                bind_session_q <= assoc_session_q;
                                bind_first_index_q <= assoc_first_index_q;
                                bind_acq_tick_q <= assoc_acq_tick_q;
                                bind_acq_rem_q <= assoc_acq_rem_q[9:0];
                                bind_source_tick_q <= assoc_source_tick_q;
                                bind_source_ns_low_q <= assoc_source_ns_low_q;
                                bind_source_ns_high_q <= assoc_source_ns_high_q;
                                bind_source_rem_q <= assoc_source_rem_q[9:0];
                                bind_epoch_q <= assoc_epoch_q[7:0];
                                bind_seq_q <= assoc_frame_seq_q[15:0];
                                bind_valid_q <= bind_quality_valid_c;
                                bind_saturated_q <= bind_quality_saturated_c;
                                bind_held_q <= bind_quality_held_c;
                                bind_source_fault_q <=
                                    bind_quality_source_fault_c;
                                assoc_fresh_q <= 10'd0;
                                last_frame_seq_q <= assoc_frame_seq_q;
                                frame_seen_q <= 1'b1;
                                result_rx_start_q <= rx_total_q;
                                result_error_q <= 3'd0;
                                result_bytes_q <= 6'd0;
                                result_visible_q <= 1'b0;
                                result_canceled_q <= 1'b0;
                                state_q <= ST_BINDING;
                            end
                            CMD_ACK: if (ack_ok_c) begin
                                ack_id_fresh_q <= 1'b0;
                                result_visible_q <= 1'b0;
                                state_q <= ST_WAIT_CORE_IDLE;
                            end
                            CMD_CANCEL: begin
                                if (result_visible_q || (state_q != ST_CANCEL))
                                    result_canceled_q <= 1'b1;
                                state_q <= ST_CANCEL;
                                result_visible_q <= 1'b0;
                                arm_fresh_q <= 3'd0;
                                sample_fresh_q <= 5'd0;
                                assoc_fresh_q <= 10'd0;
                                ack_id_fresh_q <= 1'b0;
                                pop_id_fresh_q <= 1'b0;
                            end
                            CMD_CLEAR_FAULT: if (clear_fault_ok_c) begin
                                sticky_fault_q <= 32'd0;
                            end
                            CMD_CLEAR_FIFO: if (clear_fifo_ok_c) begin
                            end
                            CMD_POP: if (pop_ok_c) begin
                                pop_id_fresh_q <= 1'b0;
                            end
                            default: begin end
                        endcase
                    end
                end
            end
        end
    end    // Read-only observation and staging readback. Reads never alter model state,
    // counters, the FIFO, the UART or the core.
    always_comb begin
        read_word_c = 32'd0;
        read_ok_c = 1'b0;
        if (s_axi_araddr[1:0] == 2'b00) begin
            read_ok_c = 1'b1;
            case (s_axi_araddr)
                12'h000: read_word_c = MAGIC;
                12'h004: read_word_c = LAYOUT;
                12'h008: read_word_c = SOURCE_KIND;
                12'h00c: read_word_c = CLOCK_HZ;
                12'h010: read_word_c = BAUD;
                12'h014: read_word_c = FIFO_CAPACITY;
                12'h018: read_word_c = {28'd0, state_q};
                12'h01c: read_word_c = sticky_fault_q;
                12'h020: read_word_c = {24'd0,
                    (state_q == ST_COMPLETE),
                    (fifo_count_q == 13'd4096),
                    (fifo_count_q == 13'd0),
                    result_visible_q,
                    (state_q == ST_BINDING),
                    !rx_idle_c,
                    core_data_path_quiescent,
                    ((state_q >= ST_ARM_WAIT) &&
                     (state_q <= ST_WAIT_CORE_IDLE))};
                12'h024: read_word_c = {29'd0, push_count_q};
                12'h028: read_word_c = {29'd0, assoc_next_q};
                12'h02c: read_word_c = last_arm_tag_q;
                12'h030: read_word_c = {19'd0, fifo_count_q};
                12'h034: read_word_c = rx_total_q;
                12'h038: read_word_c = pop_id_q;
                12'h03c: read_word_c = discard_count_q;
                12'h040: read_word_c = result_id_q;
                12'h044: read_word_c = {29'd0, result_error_q};
                12'h048: read_word_c = {26'd0, result_bytes_q};
                12'h04c: read_word_c = refusal_q;
                12'h050: read_word_c = result_rx_start_q;
                12'h054: read_word_c = rx_stat_aborted;
                12'h058: read_word_c = core_capture_discarded;
                12'h05c: read_word_c = {30'd0,
                    core_capture_sequence_exhausted,
                    core_capture_fault_event};
                12'h060: read_word_c = BUILD_ID[31:0];
                12'h064: read_word_c = BUILD_ID[63:32];
                12'h068: read_word_c = BUILD_ID[95:64];
                12'h06c: read_word_c = BUILD_ID[127:96];
                12'h070: read_word_c = {23'd0,
                    (fifo_count_q != 13'd0),
                    (fifo_count_q != 13'd0) ? fifo_mem[fifo_rd_q] : 8'd0};
                12'h074: read_word_c = last_cmd_q;
                12'h078: read_word_c = {31'd0, result_canceled_q};
                12'h07c: read_word_c = result_rx_end_q;
                12'h100: read_word_c = arm_tag_q;
                12'h104: read_word_c = origin_low_q;
                12'h108: read_word_c = origin_high_q;
                12'h110: read_word_c = sample_channel_q;
                12'h114: read_word_c = sample_data_q;
                12'h118: read_word_c = sample_tick_low_q;
                12'h11c: read_word_c = sample_tick_high_q;
                12'h120: read_word_c = sample_quality_q;
                12'h130: read_word_c = assoc_session_q;
                12'h134: read_word_c = assoc_first_index_q;
                12'h138: read_word_c = assoc_acq_tick_q;
                12'h13c: read_word_c = assoc_acq_rem_q;
                12'h140: read_word_c = assoc_source_ns_low_q;
                12'h144: read_word_c = assoc_source_ns_high_q;
                12'h148: read_word_c = assoc_source_tick_q;
                12'h14c: read_word_c = assoc_source_rem_q;
                12'h150: read_word_c = assoc_epoch_q;
                12'h154: read_word_c = assoc_frame_seq_q;
                12'h160: read_word_c = expected_result_id_q;
                12'h164: read_word_c = expected_pop_id_q;
                default: begin
                    read_word_c = 32'd0;
                    read_ok_c = 1'b0;
                end
            endcase
        end
    end
endmodule
`default_nettype wire
