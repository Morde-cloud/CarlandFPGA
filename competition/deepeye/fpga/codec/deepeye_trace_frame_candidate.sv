// Isolated candidate composition45. No public type7 enable or transport grant.
module deepeye_trace_frame_candidate (
    input logic clk, rst, cancel,
    input logic cfg_valid, output logic cfg_ready,
    input logic [7:0] cfg_count, input logic [3:0] cfg_e,
    input logic [31:0] cfg_session, input logic [1:0] cfg_channel,
    input logic [31:0] cfg_first_index, input logic [63:0] cfg_first_tick,
    input logic [15:0] cfg_index_stride, cfg_tick_stride,
    input logic cfg_valid_sample, cfg_saturated, cfg_held, cfg_source_fault,
    input logic [63:0] cfg_source_tick,
    input logic [7:0] cfg_epoch, input logic [15:0] cfg_seq,
    input logic s_valid, output logic s_ready,
    input logic [15:0] s_data, input logic s_last,
    output logic out_valid, input logic out_ready,
    output logic [7:0] out_data, output logic out_last,
    output logic [5:0] out_count,
    output logic result_valid, input logic result_ready,
    output logic [2:0] result_error, output logic [5:0] result_bytes,
    output logic busy,
    output logic wire_faulted, wire_fault_event,
    output logic [1:0] wire_fault_code
);
    localparam logic [2:0] IDLE=0, WAIT_META=1, FEED=2,
        WAIT_FRAME=3, REPORT=4, FAULT=5;
    logic [2:0] state;
    logic [7:0] epoch_q;
    logic [15:0] seq_q;
    logic [5:0] expected_total;
    logic fault_report_pending;
    wire enabled = !rst && !cancel && !wire_faulted;
    logic payload_cfg_ready, payload_s_ready;
    logic meta_valid, meta_ready;
    logic [1:0] meta_error;
    logic [5:0] meta_bytes;
    logic [31:0] meta_tick;
    logic payload_valid, payload_ready, payload_last;
    logic [7:0] payload_data;
    logic serializer_cfg_ready, serializer_p_ready;
    logic serializer_valid, serializer_last;
    logic [7:0] serializer_data;
    logic [5:0] serializer_count;
    wire serializer_cfg_valid = (state==WAIT_META) && meta_valid &&
        (meta_error==0) && enabled;

    assign cfg_ready = (state==IDLE) && payload_cfg_ready && serializer_cfg_ready && enabled;
    assign s_ready = (state==WAIT_META) && payload_s_ready && enabled;
    assign meta_ready = (state==WAIT_META) && ((meta_error!=0) || serializer_cfg_ready) && enabled;
    assign payload_ready = (state==FEED) && serializer_p_ready && enabled;
    assign out_valid = (state==WAIT_FRAME) && serializer_valid && enabled;
    assign out_data = serializer_data;
    assign out_last = out_valid && serializer_last;
    assign out_count = out_valid ? serializer_count : 6'd0;
    assign result_valid = !rst && !cancel &&
        (((state==REPORT) && !wire_faulted) || ((state==FAULT) && fault_report_pending));
    assign busy = (state!=IDLE);

    deepeye_trace_payload_timing_candidate payload_stage (
        .clk(clk), .rst(rst), .cancel(cancel),
        .cfg_valid(cfg_valid && (state==IDLE) && serializer_cfg_ready && enabled),
        .cfg_ready(payload_cfg_ready),
        .cfg_count(cfg_count), .cfg_e(cfg_e), .cfg_session(cfg_session),
        .cfg_channel(cfg_channel), .cfg_first_index(cfg_first_index),
        .cfg_first_tick(cfg_first_tick), .cfg_index_stride(cfg_index_stride),
        .cfg_tick_stride(cfg_tick_stride), .cfg_valid_sample(cfg_valid_sample),
        .cfg_saturated(cfg_saturated), .cfg_held(cfg_held),
        .cfg_source_fault(cfg_source_fault), .cfg_source_tick(cfg_source_tick),
        .s_valid(s_valid && (state==WAIT_META) && enabled), .s_ready(payload_s_ready),
        .s_data(s_data), .s_last(s_last),
        .meta_valid(meta_valid), .meta_ready(meta_ready),
        .meta_error(meta_error), .meta_bytes(meta_bytes), .meta_tick(meta_tick),
        .m_valid(payload_valid), .m_ready(payload_ready),
        .m_data(payload_data), .m_last(payload_last)
    );
    deepeye_wire_serializer #(.STAT_W(32)) serializer (
        .clk(clk), .rst(rst), .cancel(cancel),
        .cfg_valid(serializer_cfg_valid), .cfg_ready(serializer_cfg_ready),
        .cfg_type(8'h07), .cfg_epoch(epoch_q), .cfg_seq(seq_q),
        .cfg_tick(meta_tick), .cfg_len(meta_bytes),
        .p_valid(payload_valid && (state==FEED) && enabled), .p_ready(serializer_p_ready),
        .p_data(payload_data), .p_last(payload_last),
        .out_valid(serializer_valid),
        .out_ready(out_ready && (state==WAIT_FRAME) && enabled),
        .out_data(serializer_data), .out_last(serializer_last), .out_count(serializer_count),
        .busy(), .receiving(), .faulted(wire_faulted),
        .fault_event(wire_fault_event), .fault_code(wire_fault_code),
        .stat_admitted(), .stat_sent(), .stat_aborted(), .stat_faults()
    );
    always @(posedge clk) begin
        if (rst || cancel) begin
            state<=IDLE; epoch_q<=0; seq_q<=0; expected_total<=0;
            result_error<=0; result_bytes<=0; fault_report_pending<=0;
        end else if ((state!=IDLE) && (state!=FAULT) && wire_faulted) begin
            state<=FAULT; result_error<=3'd4; result_bytes<=0; fault_report_pending<=1;
        end else begin
            case (state)
                IDLE: if (cfg_valid && cfg_ready) begin
                    epoch_q<=cfg_epoch; seq_q<=cfg_seq; state<=WAIT_META;
                end
                WAIT_META: if (meta_valid && meta_ready) begin
                    if (meta_error!=0) begin
                        result_error<={1'b0,meta_error}; result_bytes<=0; state<=REPORT;
                    end else begin
                        expected_total<=6'd14+meta_bytes; state<=FEED;
                    end
                end
                FEED: if (payload_valid && payload_ready && payload_last) state<=WAIT_FRAME;
                WAIT_FRAME: if (out_valid && out_ready && out_last) begin
                    result_error<=0; result_bytes<=expected_total; state<=REPORT;
                end
                REPORT: if (result_valid && result_ready) state<=IDLE;
                FAULT: if (result_valid && result_ready) fault_report_pending<=0;
                default: begin state<=FAULT; result_error<=3'd4; result_bytes<=0; fault_report_pending<=1; end
            endcase
        end
    end
endmodule
