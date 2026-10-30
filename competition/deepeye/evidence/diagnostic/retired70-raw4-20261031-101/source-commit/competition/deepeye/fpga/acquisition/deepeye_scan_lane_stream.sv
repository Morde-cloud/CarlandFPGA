// B-SCAN-LANE-STREAM-20261024-44-v1; candidate only, no source/policy inference.
// H01-H15 contract requirements c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
module deepeye_scan_lane_stream (
    input logic clk, rst, cancel, in_valid,
    output logic in_ready,
    input logic [63:0] in_data,
    input logic [255:0] in_ticks,
    input logic [31:0] in_quality, in_first_seq, in_last_seq, in_tag,
    output logic out_valid,
    input logic out_ready,
    output logic [1:0] out_channel,
    output logic [15:0] out_data,
    output logic [63:0] out_tick,
    output logic [7:0] out_quality,
    output logic [31:0] out_first_seq, out_last_seq, out_tag,
    output logic out_last
);
    logic full;
    logic [1:0] lane;
    logic [63:0] data_q;
    logic [255:0] ticks_q;
    logic [31:0] quality_q, first_q, last_q, tag_q;
    assign out_valid=full&&!rst&&!cancel;
    assign in_ready=(!full||(out_valid&&out_ready&&(lane==2'd3)))&&!rst&&!cancel;
    assign out_channel=lane;
    assign out_data=data_q[16*lane+:16];
    assign out_tick=ticks_q[64*lane+:64];
    assign out_quality=quality_q[8*lane+:8];
    assign out_first_seq=first_q;
    assign out_last_seq=last_q;
    assign out_tag=tag_q;
    assign out_last=out_valid&&(lane==2'd3);
    always @(posedge clk) begin
        if(rst||cancel)begin full<=0;lane<=0;end
        else if(in_valid&&in_ready)begin
            data_q<=in_data;ticks_q<=in_ticks;quality_q<=in_quality;
            first_q<=in_first_seq;last_q<=in_last_seq;tag_q<=in_tag;
            full<=1;lane<=0;
        end else if(out_valid&&out_ready)begin
            if(lane==2'd3)begin full<=0;lane<=0;end
            else lane<=lane+2'd1;
        end
    end
endmodule
