// Private source4 diagnostic. B-MINIMAL-PL-AXI-20261025-53-v1.
// H01-H15: c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// One clock only; reset is synchronous. No physical validity or CDC claim.
module deepeye_private_axi_diag (
    input  logic        s_axi_aclk,
    input  logic        s_axi_aresetn,
    input  logic [11:0] s_axi_awaddr,
    input  logic [2:0]  s_axi_awprot,
    input  logic        s_axi_awvalid,
    output logic        s_axi_awready,
    input  logic [31:0] s_axi_wdata,
    input  logic [3:0]  s_axi_wstrb,
    input  logic        s_axi_wvalid,
    output logic        s_axi_wready,
    output logic [1:0]  s_axi_bresp,
    output logic        s_axi_bvalid,
    input  logic        s_axi_bready,
    input  logic [11:0] s_axi_araddr,
    input  logic [2:0]  s_axi_arprot,
    input  logic        s_axi_arvalid,
    output logic        s_axi_arready,
    output logic [31:0] s_axi_rdata,
    output logic [1:0]  s_axi_rresp,
    output logic        s_axi_rvalid,
    input  logic        s_axi_rready
);
    localparam logic [31:0]
        E_NONE=0, E_ALIGN=1, E_ADDRESS=2, E_READ_ONLY=3, E_STROBE=4,
        E_COMMAND=5, E_START_STATE=6, E_TAG_ZERO=7, E_TAG_REUSE=8,
        E_GENERATION=9, E_NOT_ARMED=10, E_BUSY=11, E_NOT_FRESH=12,
        E_TRIGGER_ID=13, E_SEQUENCE=14, E_NO_RESULT=15, E_STAGE_BUSY=16,
        E_TAG_RUNNING=17, E_DATA_RANGE=18, E_FAULT_LATCHED=19,
        E_CAPTURE_ORDER=32, E_CAPTURE_OVERRUN=33, E_CAPTURE_SEQUENCE=34,
        E_LANE_IDENTITY=35;

    logic pipe_reset_q;
    // The downstream synchronous reset is explicitly sampled on this clock.
    // Bus admission waits an extra edge after reset release.
    always_ff @(posedge s_axi_aclk) pipe_reset_q <= !s_axi_aresetn;

    logic aw_full_q, w_full_q;
    logic [11:0] awaddr_q;
    logic [31:0] wdata_q;
    logic [3:0] wstrb_q;
    logic commit_write;
    assign s_axi_awready = s_axi_aresetn && !pipe_reset_q && !aw_full_q && !s_axi_bvalid;
    assign s_axi_wready  = s_axi_aresetn && !pipe_reset_q && !w_full_q && !s_axi_bvalid;
    assign s_axi_arready = s_axi_aresetn && !pipe_reset_q && !s_axi_rvalid;
    assign commit_write = s_axi_aresetn && !pipe_reset_q && aw_full_q && w_full_q && !s_axi_bvalid;

    logic session_q, busy_q, fault_q, rearm_q;
    logic [31:0] staged_tag_q, active_tag_q, last_tag_q, generation_q, trigger_q;
    logic [31:0] cycle_q, error_q;
    logic [31:0] stage_q [0:12];
    logic [12:0] fresh_q;
    logic feeder_q;
    logic [1:0] feed_channel_q, next_lane_q;
    logic [63:0] frozen_data_q;
    logic [255:0] frozen_ticks_q;
    logic [31:0] frozen_quality_q, scan_first_q;

    logic result_valid_q;
    logic [15:0] result_data_q;
    logic [1:0] result_channel_q;
    logic [7:0] result_quality_q;
    logic [63:0] result_tick_q;
    logic [31:0] result_first_q, result_last_q, result_tag_q;
    logic [31:0] result_trigger_q, result_generation_q, result_cycle_q;

    logic cap_armed, cap_exhausted, cap_order_event, cap_overrun_event, cap_exhaust_event;
    logic [31:0] cap_next_seq, cap_events, cap_previous_q, cap_total_q;
    logic [31:0] queue_accepted, lane_total_q;
    logic scan_valid, scan_ready;
    logic [63:0] scan_data;
    logic [255:0] scan_ticks;
    logic [31:0] scan_quality, scan_first, scan_last, scan_tag;
    logic lane_valid, lane_ready, lane_last;
    logic [1:0] lane_channel;
    logic [15:0] lane_data;
    logic [63:0] lane_tick;
    logic [7:0] lane_quality;
    logic [31:0] lane_first, lane_end, lane_tag;
    logic running, sample_fire, lane_fire, cancel_pipeline, lane_identity_bad, lane_fault_q;
    logic stop_now, start_now, trigger_now, ack_now;
    logic [31:0] write_error, fatal_error;
    integer write_stage_index;
    logic write_stage, write_tag;

    assign running = session_q && cap_armed && !rearm_q && !pipe_reset_q;
    assign sample_fire = feeder_q && running && !cancel_pipeline;
    assign lane_ready = session_q && busy_q && !result_valid_q && !cancel_pipeline && !pipe_reset_q;
    assign lane_fire = lane_valid && lane_ready;
    assign lane_identity_bad = lane_valid && !result_valid_q &&
        (!busy_q || lane_channel!=next_lane_q || lane_tag!=active_tag_q ||
         lane_first!=scan_first_q || lane_end!=scan_first_q+32'd3 ||
         lane_last!=(lane_channel==2'd3));

    // Decode only latched AW/W, never live VALID. STOP dominates command bits.
    always_comb begin
        write_error = E_NONE;
        stop_now=0; start_now=0; trigger_now=0; ack_now=0;
        write_stage=0; write_tag=0; write_stage_index=0;
        if (awaddr_q[1:0] != 0) write_error=E_ALIGN;
        else if (awaddr_q == 12'h00c) begin
            if (wstrb_q[0] && wdata_q[0]) stop_now=commit_write;
            else if (wstrb_q != 4'hf) write_error=E_STROBE;
            else case (wdata_q)
                32'd2: begin
                    if (session_q) write_error=E_START_STATE;
                    else if (fault_q) write_error=E_FAULT_LATCHED;
                    else if (staged_tag_q == 0) write_error=E_TAG_ZERO;
                    else if (staged_tag_q == last_tag_q) write_error=E_TAG_REUSE;
                    else if (generation_q == 32'hffffffff) write_error=E_GENERATION;
                    else start_now=commit_write;
                end
                32'd4: begin
                    if (!running) write_error=E_NOT_ARMED;
                    else if (busy_q || result_valid_q) write_error=E_BUSY;
                    else if (fresh_q != 13'h1fff) write_error=E_NOT_FRESH;
                    else if (trigger_q == 32'hffffffff) write_error=E_TRIGGER_ID;
                    else if (cap_exhausted || cap_next_seq > 32'hfffffffc) write_error=E_SEQUENCE;
                    else trigger_now=commit_write;
                end
                32'd8: begin
                    if (!result_valid_q) write_error=E_NO_RESULT;
                    else ack_now=commit_write;
                end
                default: write_error=E_COMMAND;
            endcase
        end else if (awaddr_q == 12'h010) begin
            if (wstrb_q != 4'hf) write_error=E_STROBE;
            else if (session_q) write_error=E_TAG_RUNNING;
            else write_tag=commit_write;
        end else if (awaddr_q >= 12'h040 && awaddr_q <= 12'h070) begin
            write_stage_index=(awaddr_q-12'h040)>>2;
            if (wstrb_q != 4'hf) write_error=E_STROBE;
            else if (busy_q) write_error=E_STAGE_BUSY;
            else if (write_stage_index < 4 && wdata_q[31:16] != 0) write_error=E_DATA_RANGE;
            else write_stage=commit_write;
        end else begin
            case (awaddr_q)
                12'h000,12'h004,12'h008,12'h014,12'h018,12'h01c,
                12'h020,12'h024,12'h028,12'h030,12'h034,
                12'h080,12'h084,12'h088,12'h08c,12'h090,12'h094,
                12'h098,12'h09c,12'h0a0,12'h0a4: write_error=E_READ_ONLY;
                default: write_error=E_ADDRESS;
            endcase
        end
    end

    // Fatal paths only inspect real stage outputs. Expected terminal sequence
    // exhaustion at the fourth sample of the last nonwrapping scan is allowed.
    always_comb begin
        fatal_error=E_NONE;
        if (session_q && !rearm_q && !pipe_reset_q) begin
            if (cap_order_event) fatal_error=E_CAPTURE_ORDER;
            else if (cap_overrun_event) fatal_error=E_CAPTURE_OVERRUN;
            else if (cap_exhaust_event && !(busy_q && scan_first_q==32'hfffffffc))
                fatal_error=E_CAPTURE_SEQUENCE;
            else if (lane_fault_q) fatal_error=E_LANE_IDENTITY;
        end
    end
    assign cancel_pipeline = !session_q || stop_now || (fatal_error != E_NONE);

    deepeye_buffered_scan_capture capture_queue (
        .clk(s_axi_aclk), .rst(pipe_reset_q), .stop(cancel_pipeline),
        .rearm(rearm_q), .queue_cancel(cancel_pipeline), .sample_strobe(sample_fire),
        .rearm_tag(active_tag_q), .sample_channel(feed_channel_q),
        .sample_data(frozen_data_q[16*feed_channel_q+:16]),
        .sample_tick(frozen_ticks_q[64*feed_channel_q+:64]),
        .sample_quality(frozen_quality_q[8*feed_channel_q+:8]),
        .out_ready(scan_ready), .out_valid(scan_valid), .out_data(scan_data),
        .out_ticks(scan_ticks), .out_quality(scan_quality), .out_first_seq(scan_first),
        .out_last_seq(scan_last), .out_tag(scan_tag), .capture_armed(cap_armed),
        .capture_partial_len(), .capture_next_seq(cap_next_seq),
        .capture_seq_exhausted(cap_exhausted), .capture_order_error_event(cap_order_event),
        .capture_overrun_event(cap_overrun_event), .capture_seq_exhaust_event(cap_exhaust_event),
        .capture_stat_events(cap_events), .capture_stat_scans(), .capture_stat_retired(),
        .capture_stat_discarded_samples(), .capture_stat_order_errors(),
        .capture_stat_overruns(), .queue_level(), .queue_stat_accepted(queue_accepted),
        .queue_stat_retired(), .queue_stat_aborted()
    );
    deepeye_scan_lane_stream lane_stream (
        .clk(s_axi_aclk), .rst(pipe_reset_q), .cancel(cancel_pipeline),
        .in_valid(scan_valid), .in_ready(scan_ready), .in_data(scan_data),
        .in_ticks(scan_ticks), .in_quality(scan_quality), .in_first_seq(scan_first),
        .in_last_seq(scan_last), .in_tag(scan_tag), .out_valid(lane_valid),
        .out_ready(lane_ready), .out_channel(lane_channel), .out_data(lane_data),
        .out_tick(lane_tick), .out_quality(lane_quality), .out_first_seq(lane_first),
        .out_last_seq(lane_end), .out_tag(lane_tag), .out_last(lane_last)
    );

    function automatic logic [31:0] sat_add32(input logic [31:0] a, b);
        logic [32:0] sum;
        sum={1'b0,a}+{1'b0,b};
        sat_add32=sum[32] ? 32'hffffffff : sum[31:0];
    endfunction

    // Bus responses retain their complete snapshot through backpressure,
    // including a STOP of the application pipeline. Reset alone drops them.
    always_ff @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            aw_full_q<=0; w_full_q<=0; awaddr_q<=0; wdata_q<=0; wstrb_q<=0;
            s_axi_bvalid<=0; s_axi_bresp<=0;
            s_axi_rvalid<=0; s_axi_rresp<=0; s_axi_rdata<=0;
        end else begin
            if (s_axi_awvalid && s_axi_awready) begin aw_full_q<=1; awaddr_q<=s_axi_awaddr; end
            if (s_axi_wvalid && s_axi_wready) begin w_full_q<=1; wdata_q<=s_axi_wdata; wstrb_q<=s_axi_wstrb; end
            if (s_axi_bvalid && s_axi_bready) s_axi_bvalid<=0;
            if (commit_write) begin
                aw_full_q<=0; w_full_q<=0; s_axi_bvalid<=1;
                s_axi_bresp<=(write_error==E_NONE && (fatal_error==E_NONE || stop_now)) ? 2'b00 : 2'b10;
            end
            if (s_axi_rvalid && s_axi_rready) s_axi_rvalid<=0;
            if (s_axi_arvalid && s_axi_arready) begin
                s_axi_rvalid<=1; s_axi_rresp<=0; s_axi_rdata<=0;
                if (s_axi_araddr[1:0]!=0) s_axi_rresp<=2'b10;
                else if (s_axi_araddr>=12'h040 && s_axi_araddr<=12'h070)
                    s_axi_rdata<=stage_q[(s_axi_araddr-12'h040)>>2];
                else case (s_axi_araddr)
                    12'h000: s_axi_rdata<=32'h44505953;
                    12'h004: s_axi_rdata<=32'h00010000;
                    12'h008: s_axi_rdata<={28'b0,fault_q,result_valid_q,busy_q,running};
                    12'h010: s_axi_rdata<=staged_tag_q;
                    12'h014: s_axi_rdata<=active_tag_q;
                    12'h018: s_axi_rdata<=generation_q;
                    12'h01c: s_axi_rdata<=trigger_q;
                    12'h020: s_axi_rdata<=cycle_q;
                    12'h024: s_axi_rdata<=cap_total_q;
                    12'h028: s_axi_rdata<=queue_accepted;
                    12'h030: s_axi_rdata<=lane_total_q;
                    12'h034: s_axi_rdata<=error_q;
                    12'h080: s_axi_rdata<={16'b0,result_data_q};
                    12'h084: s_axi_rdata<={16'b0,result_quality_q,6'b0,result_channel_q};
                    12'h088: s_axi_rdata<=result_tick_q[31:0];
                    12'h08c: s_axi_rdata<=result_tick_q[63:32];
                    12'h090: s_axi_rdata<=result_first_q;
                    12'h094: s_axi_rdata<=result_last_q;
                    12'h098: s_axi_rdata<=result_tag_q;
                    12'h09c: s_axi_rdata<=result_trigger_q;
                    12'h0a0: s_axi_rdata<=result_generation_q;
                    12'h0a4: s_axi_rdata<=result_cycle_q;
                    default: s_axi_rresp<=2'b10;
                endcase
            end
        end
    end

    always_ff @(posedge s_axi_aclk) begin : application
        integer i;
        if (!s_axi_aresetn) begin
            session_q<=0; busy_q<=0; fault_q<=0; rearm_q<=0; lane_fault_q<=0;
            staged_tag_q<=0; active_tag_q<=0; last_tag_q<=0; generation_q<=0; trigger_q<=0;
            cycle_q<=0; error_q<=E_NONE; fresh_q<=0; feeder_q<=0;
            feed_channel_q<=0; next_lane_q<=0; frozen_data_q<=0; frozen_ticks_q<=0;
            frozen_quality_q<=0; scan_first_q<=0;
            result_valid_q<=0; result_data_q<=0; result_channel_q<=0; result_quality_q<=0;
            result_tick_q<=0; result_first_q<=0; result_last_q<=0; result_tag_q<=0;
            result_trigger_q<=0; result_generation_q<=0; result_cycle_q<=0;
            cap_previous_q<=0; cap_total_q<=0; lane_total_q<=0;
            for (i=0;i<13;i=i+1) stage_q[i]<=0;
        end else begin
            cycle_q<=cycle_q+32'd1;
            rearm_q<=0;
            // Register the integrity alarm to avoid feeding cancel back through
            // lane_stream's combinational VALID mask. Bad lanes never publish.
            lane_fault_q<=lane_identity_bad;
            // Capture's per-arm counter resets on STOP/rearm. Accumulate only
            // nonnegative deltas of its actual public statistic, not PS writes.
            cap_previous_q<=cap_events;
            if (!pipe_reset_q && cap_events>=cap_previous_q)
                cap_total_q<=sat_add32(cap_total_q,cap_events-cap_previous_q);
            if (lane_fire) lane_total_q<=sat_add32(lane_total_q,32'd1);

            if (stop_now || fatal_error!=E_NONE) begin
                session_q<=0; busy_q<=0; rearm_q<=0; lane_fault_q<=0; active_tag_q<=0; staged_tag_q<=0;
                trigger_q<=0; fresh_q<=0; feeder_q<=0; feed_channel_q<=0; next_lane_q<=0;
                frozen_data_q<=0; frozen_ticks_q<=0; frozen_quality_q<=0;
                scan_first_q<=0;
                result_valid_q<=0; result_data_q<=0; result_channel_q<=0; result_quality_q<=0;
                result_tick_q<=0; result_first_q<=0; result_last_q<=0; result_tag_q<=0;
                result_trigger_q<=0; result_generation_q<=0; result_cycle_q<=0;
                for (i=0;i<13;i=i+1) stage_q[i]<=0;
                fault_q<=!stop_now;
                error_q<=stop_now ? E_NONE : fatal_error;
            end else begin
                if (commit_write && write_error!=E_NONE) error_q<=write_error;
                if (write_tag) staged_tag_q<=wdata_q;
                if (write_stage) begin
                    stage_q[write_stage_index]<=wdata_q;
                    fresh_q[write_stage_index]<=1;
                end
                if (start_now) begin
                    session_q<=1; busy_q<=0; active_tag_q<=staged_tag_q;
                    last_tag_q<=staged_tag_q; generation_q<=generation_q+32'd1;
                    trigger_q<=0; fresh_q<=0; rearm_q<=1; error_q<=E_NONE;
                end
                if (trigger_now) begin
                    busy_q<=1; feeder_q<=1; feed_channel_q<=0; next_lane_q<=0;
                    trigger_q<=trigger_q+32'd1; scan_first_q<=cap_next_seq;
                    fresh_q<=0;
                    for (i=0;i<4;i=i+1) begin
                        frozen_data_q[16*i+:16]<=stage_q[i][15:0];
                        frozen_ticks_q[64*i+:64]<={stage_q[5+2*i],stage_q[4+2*i]};
                    end
                    frozen_quality_q<=stage_q[12];
                end
                if (sample_fire) begin
                    if (feed_channel_q==2'd3) feeder_q<=0;
                    else feed_channel_q<=feed_channel_q+2'd1;
                end
                if (lane_fire && !lane_identity_bad) begin
                    result_valid_q<=1; result_data_q<=lane_data; result_channel_q<=lane_channel;
                    result_tick_q<=lane_tick; result_quality_q<=lane_quality;
                    result_first_q<=lane_first; result_last_q<=lane_end; result_tag_q<=lane_tag;
                    result_trigger_q<=trigger_q; result_generation_q<=generation_q;
                    // Private 0xA4 = PL_RESULT_LATCH_CYCLE, not acquisition time.
                    result_cycle_q<=cycle_q; next_lane_q<=next_lane_q+2'd1;
                end
                if (ack_now) begin
                    result_valid_q<=0; result_data_q<=0; result_channel_q<=0; result_quality_q<=0;
                    result_tick_q<=0; result_first_q<=0; result_last_q<=0; result_tag_q<=0;
                    result_trigger_q<=0; result_generation_q<=0; result_cycle_q<=0;
                    if (result_channel_q==2'd3) busy_q<=0;
                end
            end
        end
    end
    // AWPROT/ARPROT are accepted and deliberately have no private privilege ABI.
endmodule
