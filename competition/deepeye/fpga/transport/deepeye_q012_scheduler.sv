`timescale 1ns/1ps

module deepeye_q012_scheduler #(
    parameter integer DESC_W = 64,
    parameter integer CREDIT_W = 16,
    parameter integer DEPTH = 4,
    parameter integer MAX_Q0_BURST = 4,
    parameter integer MAX_NON_Q2_BURST = 8,
    parameter integer STAT_W = 32
) (
    input  logic clk,
    input  logic rst,
    input  logic flush,
    input  logic enable,

    input  logic                    in_valid,
    input  logic [1:0]              in_class,
    input  logic [DESC_W-1:0]       in_desc,
    input  logic [CREDIT_W-1:0]     in_cost,
    output logic                    in_ready,
    output logic                    in_invalid,

    input  logic                    credit_load_valid,
    input  logic [CREDIT_W-1:0]     credit_load_value,
    output logic                    credit_load_ready,

    input  logic [2:0]              eligible_mask,

    output logic                    out_valid,
    input  logic                    out_ready,
    output logic [1:0]              out_class,
    output logic [DESC_W-1:0]       out_desc,
    output logic [CREDIT_W-1:0]     out_cost,

    output logic [CREDIT_W-1:0]     credits_remaining,
    output logic [$clog2(DEPTH+1)-1:0] count_q0,
    output logic [$clog2(DEPTH+1)-1:0] count_q1,
    output logic [$clog2(DEPTH+1)-1:0] count_q2,

    output logic [STAT_W-1:0]       accepted_count,
    output logic [STAT_W-1:0]       sent_count,
    output logic [STAT_W-1:0]       flushed_count
);

    localparam integer PTR_W = (DEPTH > 1) ? $clog2(DEPTH) : 1;
    localparam integer CNT_W = (DEPTH > 1) ? $clog2(DEPTH + 1) : 1;
    localparam integer Q0_RUN_W = (MAX_Q0_BURST > 1) ? $clog2(MAX_Q0_BURST + 1) : 1;
    localparam integer NON_Q2_RUN_W = (MAX_NON_Q2_BURST > 1) ? $clog2(MAX_NON_Q2_BURST + 1) : 1;
    localparam logic [STAT_W-1:0] STAT_MAX = {STAT_W{1'b1}};

    logic [DESC_W-1:0] desc_mem0 [0:DEPTH-1];
    logic [DESC_W-1:0] desc_mem1 [0:DEPTH-1];
    logic [DESC_W-1:0] desc_mem2 [0:DEPTH-1];
    logic [CREDIT_W-1:0] cost_mem0 [0:DEPTH-1];
    logic [CREDIT_W-1:0] cost_mem1 [0:DEPTH-1];
    logic [CREDIT_W-1:0] cost_mem2 [0:DEPTH-1];

    logic [PTR_W-1:0] head_q0;
    logic [PTR_W-1:0] tail_q0;
    logic [PTR_W-1:0] head_q1;
    logic [PTR_W-1:0] tail_q1;
    logic [PTR_W-1:0] head_q2;
    logic [PTR_W-1:0] tail_q2;

    logic [CNT_W-1:0] q0_count;
    logic [CNT_W-1:0] q1_count;
    logic [CNT_W-1:0] q2_count;

    logic [CREDIT_W-1:0] credits_i;
    logic [Q0_RUN_W-1:0] q0_run;
    logic [NON_Q2_RUN_W-1:0] non_q2_run;

    logic                    offer_valid;
    logic [1:0]              offer_class;
    logic [DESC_W-1:0]       offer_desc;
    logic [CREDIT_W-1:0]     offer_cost;

    logic                    chosen_full;
    logic                    sel_valid;
    logic [1:0]              sel_class;
    logic [DESC_W-1:0]       sel_desc;
    logic [CREDIT_W-1:0]     sel_cost;

    wire [CREDIT_W-1:0] q0_head_cost = cost_mem0[head_q0];
    wire [CREDIT_W-1:0] q1_head_cost = cost_mem1[head_q1];
    wire [CREDIT_W-1:0] q2_head_cost = cost_mem2[head_q2];

    wire eligible_q0 = (q0_count != 0) && eligible_mask[0] && (q0_head_cost <= credits_i);
    wire eligible_q1 = (q1_count != 0) && eligible_mask[1] && (q1_head_cost <= credits_i);
    wire eligible_q2 = (q2_count != 0) && eligible_mask[2] && (q2_head_cost <= credits_i);

    wire in_accept = in_valid && in_ready;
    wire load_accept = credit_load_valid && credit_load_ready;
    wire fire = out_valid && out_ready;

    wire enq_q0 = in_accept && (in_class == 2'd0);
    wire enq_q1 = in_accept && (in_class == 2'd1);
    wire enq_q2 = in_accept && (in_class == 2'd2);

    wire fire_q0 = fire && (offer_class == 2'd0);
    wire fire_q1 = fire && (offer_class == 2'd1);
    wire fire_q2 = fire && (offer_class == 2'd2);

    wire [CNT_W+1:0] queued_total = {{2{1'b0}}, q0_count}
                                  + {{2{1'b0}}, q1_count}
                                  + {{2{1'b0}}, q2_count};

    function automatic [PTR_W-1:0] next_ptr(input [PTR_W-1:0] ptr);
        begin
            if (ptr == DEPTH - 1)
                next_ptr = '0;
            else
                next_ptr = ptr + 1'b1;
        end
    endfunction

    function automatic [STAT_W-1:0] stat_inc(input [STAT_W-1:0] current);
        begin
            if (current == STAT_MAX)
                stat_inc = STAT_MAX;
            else
                stat_inc = current + 1'b1;
        end
    endfunction

    function automatic [STAT_W-1:0] sat_add_queued(
        input [STAT_W-1:0] current,
        input [CNT_W+1:0] addend
    );
        logic [STAT_W+3:0] total;
        begin
            total = {{4{1'b0}}, current}
                  + {{(STAT_W + 2 - CNT_W){1'b0}}, addend};
            if (total > {{4{1'b0}}, STAT_MAX})
                sat_add_queued = STAT_MAX;
            else
                sat_add_queued = total[STAT_W-1:0];
        end
    endfunction

    assign in_invalid = in_valid
                     && ((in_class == 2'd3) || (in_cost == {CREDIT_W{1'b0}}));

    always_comb begin
        chosen_full = 1'b0;
        case (in_class)
            2'd0: chosen_full = (q0_count == DEPTH);
            2'd1: chosen_full = (q1_count == DEPTH);
            2'd2: chosen_full = (q2_count == DEPTH);
            default: chosen_full = 1'b1;
        endcase
    end

    assign in_ready = !rst && !flush && (in_class != 2'd3)
                    && (in_cost != {CREDIT_W{1'b0}}) && !chosen_full;
    assign credit_load_ready = !rst && !flush && !offer_valid;

    always_comb begin
        sel_valid = 1'b0;
        sel_class = 2'd0;
        sel_desc = '0;
        sel_cost = '0;
        if (enable && !rst && !flush && !offer_valid && !load_accept) begin
            if (eligible_q2 && (non_q2_run >= MAX_NON_Q2_BURST)) begin
                sel_valid = 1'b1;
                sel_class = 2'd2;
                sel_desc = desc_mem2[head_q2];
                sel_cost = cost_mem2[head_q2];
            end else if (eligible_q1 && (q0_run >= MAX_Q0_BURST)) begin
                sel_valid = 1'b1;
                sel_class = 2'd1;
                sel_desc = desc_mem1[head_q1];
                sel_cost = cost_mem1[head_q1];
            end else if (eligible_q0) begin
                sel_valid = 1'b1;
                sel_class = 2'd0;
                sel_desc = desc_mem0[head_q0];
                sel_cost = cost_mem0[head_q0];
            end else if (eligible_q1) begin
                sel_valid = 1'b1;
                sel_class = 2'd1;
                sel_desc = desc_mem1[head_q1];
                sel_cost = cost_mem1[head_q1];
            end else if (eligible_q2) begin
                sel_valid = 1'b1;
                sel_class = 2'd2;
                sel_desc = desc_mem2[head_q2];
                sel_cost = cost_mem2[head_q2];
            end
        end
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            offer_valid <= 1'b0;
            offer_class <= 2'd0;
            offer_desc <= '0;
            offer_cost <= '0;
            credits_i <= '0;
            q0_count <= '0;
            q1_count <= '0;
            q2_count <= '0;
            head_q0 <= '0;
            tail_q0 <= '0;
            head_q1 <= '0;
            tail_q1 <= '0;
            head_q2 <= '0;
            tail_q2 <= '0;
            q0_run <= '0;
            non_q2_run <= '0;
            accepted_count <= '0;
            sent_count <= '0;
            flushed_count <= '0;
        end else if (flush) begin
            flushed_count <= sat_add_queued(flushed_count, queued_total);
            offer_valid <= 1'b0;
            offer_class <= 2'd0;
            offer_desc <= '0;
            offer_cost <= '0;
            credits_i <= '0;
            q0_count <= '0;
            q1_count <= '0;
            q2_count <= '0;
            head_q0 <= '0;
            tail_q0 <= '0;
            head_q1 <= '0;
            tail_q1 <= '0;
            head_q2 <= '0;
            tail_q2 <= '0;
            q0_run <= '0;
            non_q2_run <= '0;
        end else begin
            if (load_accept)
                credits_i <= credit_load_value;
            else if (fire)
                credits_i <= credits_i - offer_cost;

            if (enq_q0) begin
                desc_mem0[tail_q0] <= in_desc;
                cost_mem0[tail_q0] <= in_cost;
            end
            if (enq_q1) begin
                desc_mem1[tail_q1] <= in_desc;
                cost_mem1[tail_q1] <= in_cost;
            end
            if (enq_q2) begin
                desc_mem2[tail_q2] <= in_desc;
                cost_mem2[tail_q2] <= in_cost;
            end

            if (enq_q0 && fire_q0) begin
                q0_count <= q0_count;
                head_q0 <= next_ptr(head_q0);
                tail_q0 <= next_ptr(tail_q0);
            end else if (enq_q0) begin
                q0_count <= q0_count + 1'b1;
                tail_q0 <= next_ptr(tail_q0);
            end else if (fire_q0) begin
                q0_count <= q0_count - 1'b1;
                head_q0 <= next_ptr(head_q0);
            end

            if (enq_q1 && fire_q1) begin
                q1_count <= q1_count;
                head_q1 <= next_ptr(head_q1);
                tail_q1 <= next_ptr(tail_q1);
            end else if (enq_q1) begin
                q1_count <= q1_count + 1'b1;
                tail_q1 <= next_ptr(tail_q1);
            end else if (fire_q1) begin
                q1_count <= q1_count - 1'b1;
                head_q1 <= next_ptr(head_q1);
            end

            if (enq_q2 && fire_q2) begin
                q2_count <= q2_count;
                head_q2 <= next_ptr(head_q2);
                tail_q2 <= next_ptr(tail_q2);
            end else if (enq_q2) begin
                q2_count <= q2_count + 1'b1;
                tail_q2 <= next_ptr(tail_q2);
            end else if (fire_q2) begin
                q2_count <= q2_count - 1'b1;
                head_q2 <= next_ptr(head_q2);
            end

            if (in_accept)
                accepted_count <= stat_inc(accepted_count);
            if (fire)
                sent_count <= stat_inc(sent_count);

            if (fire) begin
                if (offer_class == 2'd0) begin
                    if (q0_run < MAX_Q0_BURST)
                        q0_run <= q0_run + 1'b1;
                end else begin
                    q0_run <= '0;
                end

                if ((offer_class == 2'd0) || (offer_class == 2'd1)) begin
                    if (non_q2_run < MAX_NON_Q2_BURST)
                        non_q2_run <= non_q2_run + 1'b1;
                end else begin
                    non_q2_run <= '0;
                end
            end

            if (fire) begin
                offer_valid <= 1'b0;
                offer_class <= 2'd0;
                offer_desc <= '0;
                offer_cost <= '0;
            end else if (sel_valid) begin
                offer_valid <= 1'b1;
                offer_class <= sel_class;
                offer_desc <= sel_desc;
                offer_cost <= sel_cost;
            end
        end
    end

    assign out_valid = offer_valid && !rst && !flush;
    assign out_class = offer_class;
    assign out_desc = offer_desc;
    assign out_cost = offer_cost;

    assign credits_remaining = credits_i;
    assign count_q0 = q0_count;
    assign count_q1 = q1_count;
    assign count_q2 = q2_count;

endmodule
