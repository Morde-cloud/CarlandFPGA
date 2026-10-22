module deepeye_raw_scan_queue #(
    parameter int DEPTH  = 4,
    parameter int SEQ_W  = 32,
    parameter int TICK_W = 64,
    parameter int TAG_W  = 32,
    parameter int STAT_W = 32,
    localparam int DEPTH_E = (DEPTH >= 1 && DEPTH <= 8) ? DEPTH : 1,
    localparam int SEQ_E   = (SEQ_W >= 2 && SEQ_W <= 32) ? SEQ_W : 2,
    localparam int TICK_E  = (TICK_W >= 1 && TICK_W <= 64) ? TICK_W : 1,
    localparam int TAG_E   = (TAG_W >= 1 && TAG_W <= 64) ? TAG_W : 1,
    localparam int STAT_E  = (STAT_W >= 2 && STAT_W <= 32) ? STAT_W : 2,
    localparam int LEVEL_W = (DEPTH_E <= 1) ? 1 : $clog2(DEPTH_E + 1),
    localparam int PTR_W   = (DEPTH_E <= 1) ? 1 : $clog2(DEPTH_E),
    localparam int ABORT_W = ((STAT_E > LEVEL_W) ? STAT_E : LEVEL_W) + 1
) (
    input  logic                       clk,
    input  logic                       rst,
    input  logic                       cancel,
    input  logic                       in_valid,
    output logic                       in_ready,
    input  logic [63:0]                in_data,
    input  logic [4*TICK_E-1:0]        in_ticks,
    input  logic [31:0]                in_quality,
    input  logic [SEQ_E-1:0]           in_first_seq,
    input  logic [SEQ_E-1:0]           in_last_seq,
    input  logic [TAG_E-1:0]           in_tag,
    output logic                       out_valid,
    input  logic                       out_ready,
    output logic [63:0]                out_data,
    output logic [4*TICK_E-1:0]        out_ticks,
    output logic [31:0]                out_quality,
    output logic [SEQ_E-1:0]           out_first_seq,
    output logic [SEQ_E-1:0]           out_last_seq,
    output logic [TAG_E-1:0]           out_tag,
    output logic [LEVEL_W-1:0]         level,
    output logic [STAT_E-1:0]          stat_accepted,
    output logic [STAT_E-1:0]          stat_retired,
    output logic [STAT_E-1:0]          stat_aborted
);

    localparam logic [PTR_W-1:0] PTR_LAST = DEPTH_E - 1;

`ifndef SYNTHESIS
    initial begin
        if (DEPTH < 1 || DEPTH > 8) begin
            $fatal(1, "deepeye_raw_scan_queue: DEPTH out of range");
        end else if (SEQ_W < 2 || SEQ_W > 32) begin
            $fatal(1, "deepeye_raw_scan_queue: SEQ_W out of range");
        end else if (TICK_W < 1 || TICK_W > 64) begin
            $fatal(1, "deepeye_raw_scan_queue: TICK_W out of range");
        end else if (TAG_W < 1 || TAG_W > 64) begin
            $fatal(1, "deepeye_raw_scan_queue: TAG_W out of range");
        end else if (STAT_W < 2 || STAT_W > 32) begin
            $fatal(1, "deepeye_raw_scan_queue: STAT_W out of range");
        end
    end
`endif

    logic [63:0]             mem_data [0:DEPTH_E-1];
    logic [4*TICK_E-1:0]     mem_ticks [0:DEPTH_E-1];
    logic [31:0]             mem_quality [0:DEPTH_E-1];
    logic [SEQ_E-1:0]        mem_first_seq [0:DEPTH_E-1];
    logic [SEQ_E-1:0]        mem_last_seq [0:DEPTH_E-1];
    logic [TAG_E-1:0]        mem_tag [0:DEPTH_E-1];

    logic [PTR_W-1:0]        wr_ptr_q;
    logic [PTR_W-1:0]        rd_ptr_q;
    logic [LEVEL_W-1:0]      level_q;
    logic [STAT_E-1:0]       stat_accepted_q;
    logic [STAT_E-1:0]       stat_retired_q;
    logic [STAT_E-1:0]       stat_aborted_q;

    logic                    push;
    logic                    pop;

    function automatic logic [PTR_W-1:0] next_wr_ptr(input logic [PTR_W-1:0] p);
        if (p == PTR_LAST) begin
            next_wr_ptr = '0;
        end else begin
            next_wr_ptr = p + 1'b1;
        end
    endfunction

    function automatic logic [PTR_W-1:0] next_rd_ptr(input logic [PTR_W-1:0] p);
        if (p == PTR_LAST) begin
            next_rd_ptr = '0;
        end else begin
            next_rd_ptr = p + 1'b1;
        end
    endfunction

    function automatic logic [STAT_E-1:0] sat_inc(input logic [STAT_E-1:0] value);
        logic [STAT_E:0] sum;
        sum = {1'b0, value} + 1'b1;
        if (sum[STAT_E]) begin
            sat_inc = {STAT_E{1'b1}};
        end else begin
            sat_inc = sum[STAT_E-1:0];
        end
    endfunction

    function automatic logic [STAT_E-1:0] sat_abort(
        input logic [STAT_E-1:0] value,
        input logic [LEVEL_W-1:0] inc
    );
        logic [ABORT_W-1:0] sum;
        logic [ABORT_W-1:0] maximum;
        sum = {{(ABORT_W-STAT_E){1'b0}}, value}
            + {{(ABORT_W-LEVEL_W){1'b0}}, inc};
        maximum = {{(ABORT_W-STAT_E){1'b0}}, {STAT_E{1'b1}}};
        if (sum > maximum) begin
            sat_abort = {STAT_E{1'b1}};
        end else begin
            sat_abort = sum[STAT_E-1:0];
        end
    endfunction

    assign push = in_valid && in_ready;
    assign pop  = out_valid && out_ready;

    assign in_ready  = !rst && !cancel && (level_q < DEPTH_E);
    assign out_valid = !rst && !cancel && (level_q != 0);

    assign out_data      = mem_data[rd_ptr_q];
    assign out_ticks     = mem_ticks[rd_ptr_q];
    assign out_quality   = mem_quality[rd_ptr_q];
    assign out_first_seq = mem_first_seq[rd_ptr_q];
    assign out_last_seq  = mem_last_seq[rd_ptr_q];
    assign out_tag       = mem_tag[rd_ptr_q];

    always_ff @(posedge clk) begin
        if (rst) begin
            level_q         <= '0;
            wr_ptr_q        <= '0;
            rd_ptr_q        <= '0;
            stat_accepted_q <= '0;
            stat_retired_q  <= '0;
            stat_aborted_q  <= '0;
        end else if (cancel) begin
            stat_aborted_q <= sat_abort(stat_aborted_q, level_q);
            level_q         <= {LEVEL_W{1'b0}};
            wr_ptr_q        <= '0;
            rd_ptr_q        <= '0;
        end else begin
            if (push) begin
                mem_data[wr_ptr_q]      <= in_data;
                mem_ticks[wr_ptr_q]     <= in_ticks;
                mem_quality[wr_ptr_q]   <= in_quality;
                mem_first_seq[wr_ptr_q] <= in_first_seq;
                mem_last_seq[wr_ptr_q]  <= in_last_seq;
                mem_tag[wr_ptr_q]       <= in_tag;
                wr_ptr_q                <= next_wr_ptr(wr_ptr_q);
                stat_accepted_q         <= sat_inc(stat_accepted_q);
            end
            if (pop) begin
                rd_ptr_q        <= next_rd_ptr(rd_ptr_q);
                stat_retired_q  <= sat_inc(stat_retired_q);
            end
            if (push && !pop) begin
                level_q <= level_q + 1'b1;
            end else if (!push && pop) begin
                level_q <= level_q - 1'b1;
            end
        end
    end

    assign level         = level_q;
    assign stat_accepted = stat_accepted_q;
    assign stat_retired  = stat_retired_q;
    assign stat_aborted  = stat_aborted_q;

endmodule
