module deepeye_sample_scan_capture #(
    parameter int SEQ_W  = 32,
    parameter int TICK_W = 64,
    parameter int TAG_W  = 32,
    parameter int STAT_W = 32
) (
    input  logic                       clk,
    input  logic                       rst,
    input  logic                       stop,
    input  logic                       rearm,
    input  logic [((TAG_W < 1) ? 1 : (TAG_W > 64) ? 64 : TAG_W)-1:0] rearm_tag,
    input  logic                       sample_strobe,
    input  logic [1:0]                 sample_channel,
    input  logic [15:0]                sample_data,
    input  logic [((TICK_W < 1) ? 1 : (TICK_W > 64) ? 64 : TICK_W)-1:0] sample_tick,
    input  logic [7:0]                 sample_quality,
    input  logic                       out_ready,
    output logic                       out_valid,
    output logic [63:0]                out_data,
    output logic [4*((TICK_W < 1) ? 1 : (TICK_W > 64) ? 64 : TICK_W)-1:0] out_ticks,
    output logic [31:0]                out_quality,
    output logic [((SEQ_W < 2) ? 2 : (SEQ_W > 32) ? 32 : SEQ_W)-1:0] out_first_seq,
    output logic [((SEQ_W < 2) ? 2 : (SEQ_W > 32) ? 32 : SEQ_W)-1:0] out_last_seq,
    output logic [((TAG_W < 1) ? 1 : (TAG_W > 64) ? 64 : TAG_W)-1:0] out_tag,
    output logic                       armed,
    output logic [2:0]                 partial_len,
    output logic [((SEQ_W < 2) ? 2 : (SEQ_W > 32) ? 32 : SEQ_W)-1:0] next_seq,
    output logic                       seq_exhausted,
    output logic                       order_error_event,
    output logic                       overrun_event,
    output logic                       seq_exhaust_event,
    output logic [((STAT_W < 2) ? 2 : (STAT_W > 32) ? 32 : STAT_W)-1:0] stat_events,
    output logic [((STAT_W < 2) ? 2 : (STAT_W > 32) ? 32 : STAT_W)-1:0] stat_scans,
    output logic [((STAT_W < 2) ? 2 : (STAT_W > 32) ? 32 : STAT_W)-1:0] stat_retired,
    output logic [((STAT_W < 2) ? 2 : (STAT_W > 32) ? 32 : STAT_W)-1:0] stat_discarded_samples,
    output logic [((STAT_W < 2) ? 2 : (STAT_W > 32) ? 32 : STAT_W)-1:0] stat_order_errors,
    output logic [((STAT_W < 2) ? 2 : (STAT_W > 32) ? 32 : STAT_W)-1:0] stat_overruns
);

    localparam int SEQ_EFF_W  = (SEQ_W  < 2 ) ? 2  : (SEQ_W  > 32) ? 32 : SEQ_W;
    localparam int TICK_EFF_W = (TICK_W < 1 ) ? 1  : (TICK_W > 64) ? 64 : TICK_W;
    localparam int TAG_EFF_W  = (TAG_W  < 1 ) ? 1  : (TAG_W  > 64) ? 64 : TAG_W;
    localparam int STAT_EFF_W = (STAT_W < 2 ) ? 2  : (STAT_W > 32) ? 32 : STAT_W;
    localparam logic [SEQ_EFF_W-1:0] SEQ_LAST = {SEQ_EFF_W{1'b1}};

`ifndef SYNTHESIS
    initial begin
        if (SEQ_W < 2 || SEQ_W > 32) begin
            $fatal(1, "deepeye_sample_scan_capture: SEQ_W out of range");
        end
        if (TICK_W < 1 || TICK_W > 64) begin
            $fatal(1, "deepeye_sample_scan_capture: TICK_W out of range");
        end
        if (TAG_W < 1 || TAG_W > 64) begin
            $fatal(1, "deepeye_sample_scan_capture: TAG_W out of range");
        end
        if (STAT_W < 2 || STAT_W > 32) begin
            $fatal(1, "deepeye_sample_scan_capture: STAT_W out of range");
        end
    end
`endif

    logic [15:0]                partial_data_q [0:3];
    logic [TICK_EFF_W-1:0]      partial_tick_q [0:3];
    logic [7:0]                 partial_quality_q [0:3];

    logic                       slot_valid_q;
    logic [63:0]                slot_data_q;
    logic [4*TICK_EFF_W-1:0]    slot_ticks_q;
    logic [31:0]                slot_quality_q;
    logic [SEQ_EFF_W-1:0]       slot_first_seq_q;
    logic [SEQ_EFF_W-1:0]       slot_last_seq_q;
    logic [TAG_EFF_W-1:0]       slot_tag_q;

    logic                       armed_q;
    logic [2:0]                 partial_len_q;
    logic [SEQ_EFF_W-1:0]       partial_first_seq_q;
    logic [SEQ_EFF_W-1:0]       next_seq_q;
    logic                       seq_exhausted_q;
    logic [TAG_EFF_W-1:0]       tag_q;

    logic                       order_error_event_q;
    logic                       overrun_event_q;
    logic                       seq_exhaust_event_q;

    logic [STAT_EFF_W-1:0]      stat_events_q;
    logic [STAT_EFF_W-1:0]      stat_scans_q;
    logic [STAT_EFF_W-1:0]      stat_retired_q;
    logic [STAT_EFF_W-1:0]      stat_discarded_samples_q;
    logic [STAT_EFF_W-1:0]      stat_order_errors_q;
    logic [STAT_EFF_W-1:0]      stat_overruns_q;

    logic                       event_fire_c;
    logic                       event_terminal_c;
    logic                       retire_now_c;
    logic                       complete_now_c;
    logic                       start_ch0_c;
    logic                       extend_c;
    logic                       order_error_c;
    logic                       overrun_c;
    logic [2:0]                 partial_after_order_c;
    logic [3:0]                 discard_order_c;
    logic [3:0]                 discard_terminal_c;
    logic [7:0]                 discard_inc_c;
    logic [7:0]                 events_inc_c;
    logic [7:0]                 scans_inc_c;
    logic [7:0]                 retired_inc_c;
    logic [7:0]                 order_errors_inc_c;
    logic [7:0]                 overruns_inc_c;
    logic [SEQ_EFF_W+1:0]       first_plus3_c;

    function automatic logic [STAT_EFF_W-1:0] sat_add(
        input logic [STAT_EFF_W-1:0] value,
        input logic [7:0]            increment
    );
        logic [STAT_EFF_W+7:0] sum_ext;
        sum_ext = {{8{1'b0}}, value} + {{STAT_EFF_W{1'b0}}, increment};
        if (|sum_ext[STAT_EFF_W+7:STAT_EFF_W]) begin
            sat_add = {STAT_EFF_W{1'b1}};
        end else begin
            sat_add = sum_ext[STAT_EFF_W-1:0];
        end
    endfunction

    function automatic logic [SEQ_EFF_W+1:0] plus3_wide(
        input logic [SEQ_EFF_W-1:0] value
    );
        plus3_wide = {2'b00, value} + {{SEQ_EFF_W{1'b0}}, 2'd3};
    endfunction

    always_comb begin
        event_fire_c     = !rst && !stop && !rearm && armed_q && sample_strobe;
        event_terminal_c = event_fire_c && (next_seq_q == SEQ_LAST);
        retire_now_c     = !rst && !stop && !rearm && slot_valid_q && out_ready;

        complete_now_c      = 1'b0;
        start_ch0_c         = 1'b0;
        extend_c            = 1'b0;
        order_error_c       = 1'b0;
        partial_after_order_c = partial_len_q;
        discard_order_c     = 4'd0;

        if (event_fire_c) begin
            if (partial_len_q == 3'd0) begin
                if (sample_channel == 2'd0) begin
                    start_ch0_c           = 1'b1;
                    partial_after_order_c = 3'd1;
                end else begin
                    order_error_c   = 1'b1;
                    discard_order_c = 4'd1;
                end
            end else if (sample_channel == partial_len_q[1:0]) begin
                if (partial_len_q == 3'd3) begin
                    complete_now_c        = 1'b1;
                    partial_after_order_c = 3'd0;
                end else begin
                    extend_c              = 1'b1;
                    partial_after_order_c = partial_len_q + 3'd1;
                end
            end else begin
                order_error_c = 1'b1;
                if (sample_channel == 2'd0) begin
                    start_ch0_c           = 1'b1;
                    partial_after_order_c = 3'd1;
                    discard_order_c       = {1'b0, partial_len_q};
                end else begin
                    partial_after_order_c = 3'd0;
                    discard_order_c       = {1'b0, partial_len_q};
                end
            end
        end

        overrun_c = complete_now_c && slot_valid_q && !retire_now_c;

        discard_terminal_c = 4'd0;
        if (event_terminal_c && (partial_after_order_c != 3'd0)) begin
            discard_terminal_c = {1'b0, partial_after_order_c};
        end

        discard_inc_c        = {4'b0000, discard_order_c}
                             + {4'b0000, discard_terminal_c}
                             + (overrun_c ? 8'd4 : 8'd0);
        events_inc_c         = event_fire_c ? 8'd1 : 8'd0;
        scans_inc_c          = complete_now_c ? 8'd1 : 8'd0;
        retired_inc_c        = retire_now_c ? 8'd1 : 8'd0;
        order_errors_inc_c   = order_error_c ? 8'd1 : 8'd0;
        overruns_inc_c       = overrun_c ? 8'd1 : 8'd0;

        first_plus3_c = plus3_wide(partial_first_seq_q);
    end

    always @(posedge clk) begin
        integer lane;
        if (rst) begin
            partial_len_q            <= 3'd0;
            partial_first_seq_q      <= '0;
            next_seq_q               <= '0;
            seq_exhausted_q          <= 1'b0;
            tag_q                    <= '0;
            armed_q                  <= 1'b0;
            slot_valid_q             <= 1'b0;
            slot_data_q              <= '0;
            slot_ticks_q             <= '0;
            slot_quality_q           <= '0;
            slot_first_seq_q         <= '0;
            slot_last_seq_q          <= '0;
            slot_tag_q               <= '0;
            order_error_event_q      <= 1'b0;
            overrun_event_q          <= 1'b0;
            seq_exhaust_event_q      <= 1'b0;
            stat_events_q            <= '0;
            stat_scans_q             <= '0;
            stat_retired_q           <= '0;
            stat_discarded_samples_q <= '0;
            stat_order_errors_q      <= '0;
            stat_overruns_q          <= '0;
            for (lane = 0; lane < 4; lane = lane + 1) begin
                partial_data_q[lane]    <= '0;
                partial_tick_q[lane]    <= '0;
                partial_quality_q[lane] <= '0;
            end
        end else if (stop) begin
            partial_len_q            <= 3'd0;
            partial_first_seq_q      <= '0;
            next_seq_q               <= '0;
            seq_exhausted_q          <= 1'b0;
            tag_q                    <= '0;
            armed_q                  <= 1'b0;
            slot_valid_q             <= 1'b0;
            slot_data_q              <= '0;
            slot_ticks_q             <= '0;
            slot_quality_q           <= '0;
            slot_first_seq_q         <= '0;
            slot_last_seq_q          <= '0;
            slot_tag_q               <= '0;
            order_error_event_q      <= 1'b0;
            overrun_event_q          <= 1'b0;
            seq_exhaust_event_q      <= 1'b0;
            stat_events_q            <= '0;
            stat_scans_q             <= '0;
            stat_retired_q           <= '0;
            stat_discarded_samples_q <= '0;
            stat_order_errors_q      <= '0;
            stat_overruns_q          <= '0;
            for (lane = 0; lane < 4; lane = lane + 1) begin
                partial_data_q[lane]    <= '0;
                partial_tick_q[lane]    <= '0;
                partial_quality_q[lane] <= '0;
            end
        end else if (rearm) begin
            partial_len_q            <= 3'd0;
            partial_first_seq_q      <= '0;
            next_seq_q               <= '0;
            seq_exhausted_q          <= 1'b0;
            tag_q                    <= rearm_tag;
            armed_q                  <= 1'b1;
            slot_valid_q             <= 1'b0;
            slot_data_q              <= '0;
            slot_ticks_q             <= '0;
            slot_quality_q           <= '0;
            slot_first_seq_q         <= '0;
            slot_last_seq_q          <= '0;
            slot_tag_q               <= '0;
            order_error_event_q      <= 1'b0;
            overrun_event_q          <= 1'b0;
            seq_exhaust_event_q      <= 1'b0;
            stat_events_q            <= '0;
            stat_scans_q             <= '0;
            stat_retired_q           <= '0;
            stat_discarded_samples_q <= '0;
            stat_order_errors_q      <= '0;
            stat_overruns_q          <= '0;
            for (lane = 0; lane < 4; lane = lane + 1) begin
                partial_data_q[lane]    <= '0;
                partial_tick_q[lane]    <= '0;
                partial_quality_q[lane] <= '0;
            end
        end else begin
            order_error_event_q <= order_error_c;
            overrun_event_q     <= overrun_c;
            seq_exhaust_event_q <= event_terminal_c;

            stat_events_q            <= sat_add(stat_events_q, events_inc_c);
            stat_scans_q             <= sat_add(stat_scans_q, scans_inc_c);
            stat_retired_q           <= sat_add(stat_retired_q, retired_inc_c);
            stat_discarded_samples_q <= sat_add(stat_discarded_samples_q, discard_inc_c);
            stat_order_errors_q      <= sat_add(stat_order_errors_q, order_errors_inc_c);
            stat_overruns_q          <= sat_add(stat_overruns_q, overruns_inc_c);

            if (retire_now_c) begin
                slot_valid_q <= 1'b0;
            end

            if (event_fire_c) begin
                if (start_ch0_c) begin
                    partial_data_q[0]    <= sample_data;
                    partial_tick_q[0]    <= sample_tick;
                    partial_quality_q[0] <= sample_quality;
                    partial_first_seq_q  <= next_seq_q;
                    partial_len_q        <= 3'd1;
                    for (lane = 1; lane < 4; lane = lane + 1) begin
                        partial_data_q[lane]    <= '0;
                        partial_tick_q[lane]    <= '0;
                        partial_quality_q[lane] <= '0;
                    end
                end else if (extend_c) begin
                    partial_data_q[partial_len_q]    <= sample_data;
                    partial_tick_q[partial_len_q]    <= sample_tick;
                    partial_quality_q[partial_len_q] <= sample_quality;
                    partial_len_q <= partial_len_q + 3'd1;
                end else begin
                    partial_len_q       <= 3'd0;
                    partial_first_seq_q <= '0;
                    for (lane = 0; lane < 4; lane = lane + 1) begin
                        partial_data_q[lane]    <= '0;
                        partial_tick_q[lane]    <= '0;
                        partial_quality_q[lane] <= '0;
                    end
                end

                if (complete_now_c) begin
                    if (!slot_valid_q || retire_now_c) begin
                        slot_valid_q     <= 1'b1;
                        slot_data_q      <= {sample_data,
                                             partial_data_q[2],
                                             partial_data_q[1],
                                             partial_data_q[0]};
                        slot_ticks_q     <= {sample_tick,
                                             partial_tick_q[2],
                                             partial_tick_q[1],
                                             partial_tick_q[0]};
                        slot_quality_q   <= {sample_quality,
                                             partial_quality_q[2],
                                             partial_quality_q[1],
                                             partial_quality_q[0]};
                        slot_first_seq_q <= partial_first_seq_q;
                        slot_last_seq_q  <= first_plus3_c[SEQ_EFF_W-1:0];
                        slot_tag_q       <= tag_q;
                    end
                end

                if (event_terminal_c) begin
                    armed_q         <= 1'b0;
                    seq_exhausted_q <= 1'b1;
                    next_seq_q      <= SEQ_LAST;
                    if (partial_after_order_c != 3'd0) begin
                        partial_len_q       <= 3'd0;
                        partial_first_seq_q <= '0;
                        for (lane = 0; lane < 4; lane = lane + 1) begin
                            partial_data_q[lane]    <= '0;
                            partial_tick_q[lane]    <= '0;
                            partial_quality_q[lane] <= '0;
                        end
                    end
                end else begin
                    next_seq_q <= next_seq_q + 1'b1;
                end
            end
        end
    end

    assign out_valid     = slot_valid_q && !rst && !stop && !rearm;
    assign out_data      = slot_data_q;
    assign out_ticks     = slot_ticks_q;
    assign out_quality   = slot_quality_q;
    assign out_first_seq = slot_first_seq_q;
    assign out_last_seq  = slot_last_seq_q;
    assign out_tag       = slot_tag_q;

    assign armed              = armed_q;
    assign partial_len        = partial_len_q;
    assign next_seq           = next_seq_q;
    assign seq_exhausted      = seq_exhausted_q;
    assign order_error_event  = order_error_event_q;
    assign overrun_event      = overrun_event_q;
    assign seq_exhaust_event  = seq_exhaust_event_q;

    assign stat_events            = stat_events_q;
    assign stat_scans             = stat_scans_q;
    assign stat_retired           = stat_retired_q;
    assign stat_discarded_samples = stat_discarded_samples_q;
    assign stat_order_errors      = stat_order_errors_q;
    assign stat_overruns          = stat_overruns_q;

endmodule
