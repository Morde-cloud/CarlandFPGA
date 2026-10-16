// deepeye_snapshot_mailbox - bounded two-clock opaque snapshot transport candidate.
//
// Work: B-SNAPSHOT-CDC-CANDIDATE-20261017-06-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
//
// Candidate-only generic transport for one outstanding opaque WIDTH-bit
// snapshot. It defines no public register address/bit field, no motion
// authorization, no clock-liveness promise, no timeout and no physical
// acceptance. BOTH reset inputs feed ONE shared flush network
// (common_reset_n = src_reset_n & dst_reset_n): either low asynchronously
// clears both halves even when one clock is stopped. Reset deassertion is
// synchronized inside each clock domain. After every reset the source stays
// not-ready until src_valid==0 is seen on a source edge while online, so a
// valid held high through reset is not replayed. The held bus is a
// bundled-data path (stable data plus synchronized handshake); it is NOT
// per-bit synchronized and carries no ASYNC_REG. Physical correctness still
// requires integrated CDC/RDC review, delay/skew and reset-pulse analysis;
// see SNAPSHOT_CDC_CANDIDATE.md.

module deepeye_snapshot_mailbox #(
    parameter integer WIDTH = 256
) (
    input  wire             src_clk,
    input  wire             src_reset_n,
    input  wire             src_valid,
    output wire             src_ready,
    input  wire [WIDTH-1:0] src_data,
    output wire             src_online,
    input  wire             dst_clk,
    input  wire             dst_reset_n,
    output wire             dst_valid,
    input  wire             dst_ready,
    output wire [WIDTH-1:0] dst_data,
    output wire             dst_online
);

    generate
        if ((WIDTH < 1) || (WIDTH > 1024)) begin : g_width_bounds_violation
            initial begin
                $error("deepeye_snapshot_mailbox: WIDTH=%0d is outside the legal range 1..1024", WIDTH);
                $fatal(1, "deepeye_snapshot_mailbox: WIDTH bounds violation");
            end
        end
    endgenerate

    wire common_reset_n = src_reset_n & dst_reset_n;

    (* ASYNC_REG = "TRUE" *) reg [1:0] src_rst_sync;
    (* ASYNC_REG = "TRUE" *) reg [1:0] dst_up_sync;
    (* ASYNC_REG = "TRUE" *) reg [1:0] ack_sync;
    reg             src_up;
    reg             req;
    reg [WIDTH-1:0] data_hold;
    reg             armed;
    wire            src_released;

    (* ASYNC_REG = "TRUE" *) reg [1:0] dst_rst_sync;
    (* ASYNC_REG = "TRUE" *) reg [1:0] src_up_sync;
    (* ASYNC_REG = "TRUE" *) reg [1:0] req_sync;
    reg             dst_up;
    reg             ack;
    reg             dst_valid_r;
    reg [WIDTH-1:0] dst_data_r;
    wire            dst_released;

    assign src_released = src_rst_sync[1];
    assign src_online   = src_up & dst_up_sync[1];
    assign src_ready    = armed & (req == ack_sync[1]);
    assign dst_released = dst_rst_sync[1];
    assign dst_online   = dst_up & src_up_sync[1];

    always @(posedge src_clk or negedge common_reset_n) begin
        if (!common_reset_n)    src_rst_sync <= 2'b00;
        else                    src_rst_sync <= {src_rst_sync[0], 1'b1};
    end

    always @(posedge src_clk or negedge common_reset_n) begin
        if (!common_reset_n)    src_up <= 1'b0;
        else if (!src_released) src_up <= 1'b0;
        else                    src_up <= 1'b1;
    end

    always @(posedge src_clk or negedge common_reset_n) begin
        if (!common_reset_n)    dst_up_sync <= 2'b00;
        else if (!src_released) dst_up_sync <= 2'b00;
        else                    dst_up_sync <= {dst_up_sync[0], dst_up};
    end

    always @(posedge src_clk or negedge common_reset_n) begin
        if (!common_reset_n)    ack_sync <= 2'b00;
        else if (!src_released) ack_sync <= 2'b00;
        else                    ack_sync <= {ack_sync[0], ack};
    end

    always @(posedge src_clk or negedge common_reset_n) begin
        if (!common_reset_n)    armed <= 1'b0;
        else if (!src_released) armed <= 1'b0;
        else if (!armed && src_online && !src_valid) armed <= 1'b1;
    end

    always @(posedge src_clk or negedge common_reset_n) begin
        if (!common_reset_n) begin
            req       <= 1'b0;
            data_hold <= {WIDTH{1'b0}};
        end else if (!src_released) begin
            req       <= 1'b0;
            data_hold <= {WIDTH{1'b0}};
        end else if (src_valid && src_ready) begin
            data_hold <= src_data;
            req       <= ~req;
        end
    end

    always @(posedge dst_clk or negedge common_reset_n) begin
        if (!common_reset_n)    dst_rst_sync <= 2'b00;
        else                    dst_rst_sync <= {dst_rst_sync[0], 1'b1};
    end

    always @(posedge dst_clk or negedge common_reset_n) begin
        if (!common_reset_n)    dst_up <= 1'b0;
        else if (!dst_released) dst_up <= 1'b0;
        else                    dst_up <= 1'b1;
    end

    always @(posedge dst_clk or negedge common_reset_n) begin
        if (!common_reset_n)    src_up_sync <= 2'b00;
        else if (!dst_released) src_up_sync <= 2'b00;
        else                    src_up_sync <= {src_up_sync[0], src_up};
    end

    always @(posedge dst_clk or negedge common_reset_n) begin
        if (!common_reset_n)    req_sync <= 2'b00;
        else if (!dst_released) req_sync <= 2'b00;
        else                    req_sync <= {req_sync[0], req};
    end

    always @(posedge dst_clk or negedge common_reset_n) begin
        if (!common_reset_n) begin
            dst_valid_r <= 1'b0;
            dst_data_r  <= {WIDTH{1'b0}};
            ack         <= 1'b0;
        end else if (!dst_released) begin
            dst_valid_r <= 1'b0;
            dst_data_r  <= {WIDTH{1'b0}};
            ack         <= 1'b0;
        end else if (!dst_valid_r) begin
            if (req_sync[1] != ack) begin
                dst_data_r  <= data_hold;
                dst_valid_r <= 1'b1;
            end
        end else if (dst_ready) begin
            ack         <= req_sync[1];
            dst_valid_r <= 1'b0;
        end
    end

    assign dst_valid = dst_valid_r;
    assign dst_data  = dst_data_r;

endmodule
