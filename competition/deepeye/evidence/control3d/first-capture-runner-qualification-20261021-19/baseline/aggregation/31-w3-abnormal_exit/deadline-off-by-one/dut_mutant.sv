// deepeye_first_capture_deadline - bounded first-capture deadline monitor.
//
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Work: B-FIRST-CAPTURE-DEADLINE-RTL-20261021-18-v1
// Product operation: B-DEEPEYE-FIRST-CAPTURE-DEADLINE-20261021-18
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15),
// requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Contract pin: f5989cd5defce561f9ba98e6b18fc2682945f0a2.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// CANDIDATE-ONLY synchronous sampled-level monitor. It records whether the
// first externally observed record arrives within a caller-supplied number of
// clock edges after a start. It defines no physical TTL, source freshness,
// ENABLE, motion authority, STOP/PWM wiring, clock rate, CDC/RDC contract,
// synthesis result, implementation result or board result.
//
// At start edge E0 with latched positive budget N, pre-edge observed is
// eligible only at E0+1 through E0+N inclusive. The event at E0+N wins over
// expiry. A record first visible after E0+N is late and cannot revive a
// terminal result. start is sampled every edge, without rising-edge detection.

module deepeye_first_capture_deadline #(
    parameter integer BUDGET_W = 32,
    localparam integer BUDGET_AW = (BUDGET_W < 1) ? 1 :
                                   ((BUDGET_W > 32) ? 32 : BUDGET_W)
) (
    input  logic                    clk,
    input  logic                    rst,
    input  logic                    cancel,
    input  logic                    start,
    input  logic                    observed,
    input  logic [BUDGET_AW-1:0]    budget_cycles,
    output logic                    waiting,
    output logic                    completed,
    output logic                    expired,
    output logic                    invalid_request,
    output logic                    started_event,
    output logic                    completed_event,
    output logic                    expired_event,
    output logic                    invalid_request_event
);

    logic                    waiting_q;
    logic                    completed_q;
    logic                    expired_q;
    logic                    invalid_request_q;
    logic [BUDGET_AW-1:0]    remaining_q;
    logic                    started_event_q;
    logic                    completed_event_q;
    logic                    expired_event_q;
    logic                    invalid_request_event_q;

    assign waiting                = waiting_q;
    assign completed              = completed_q;
    assign expired                = expired_q;
    assign invalid_request        = invalid_request_q;
    assign started_event          = started_event_q;
    assign completed_event        = completed_event_q;
    assign expired_event          = expired_event_q;
    assign invalid_request_event  = invalid_request_event_q;

    always_ff @(posedge clk) begin
        started_event_q         <= 1'b0;
        completed_event_q       <= 1'b0;
        expired_event_q         <= 1'b0;
        invalid_request_event_q <= 1'b0;

        if (rst || cancel) begin
            waiting_q         <= 1'b0;
            completed_q       <= 1'b0;
            expired_q         <= 1'b0;
            invalid_request_q <= 1'b0;
            remaining_q       <= '0;
        end else if (waiting_q) begin
            if (start) begin
                // WAIT_DUPLICATE_START_REJECT
                // A second sampled start is a refused request. The original
                // latched deadline is discarded, never extended.
                waiting_q                <= 1'b0;
                completed_q              <= 1'b0;
                expired_q                <= 1'b0;
                invalid_request_q        <= 1'b1;
                invalid_request_event_q  <= 1'b1;
                remaining_q              <= '0;
            end else if (observed) begin
                // Observed wins over expiry at the final allowed edge.
                waiting_q         <= 1'b0;
                completed_q       <= 1'b1;
                expired_q         <= 1'b0;
                invalid_request_q <= 1'b0;
                completed_event_q <= 1'b1;
                remaining_q       <= '0;
            end else if (remaining_q == '0) begin
                waiting_q         <= 1'b0;
                completed_q       <= 1'b0;
                expired_q         <= 1'b1;
                invalid_request_q <= 1'b0;
                expired_event_q   <= 1'b1;
                remaining_q       <= '0;
            end else begin
                remaining_q <= remaining_q - 1'b1;
            end
        end else begin
            if (start) begin
                if (budget_cycles == '0) begin
                    waiting_q                <= 1'b0;
                    completed_q              <= 1'b0;
                    expired_q                <= 1'b0;
                    invalid_request_q        <= 1'b1;
                    invalid_request_event_q  <= 1'b1;
                    remaining_q              <= '0;
                end else begin
                    waiting_q         <= 1'b1;
                    completed_q       <= 1'b0;
                    expired_q         <= 1'b0;
                    invalid_request_q <= 1'b0;
                    started_event_q   <= 1'b1;
                    remaining_q       <= budget_cycles;
                end
            end else begin
                // RETAIN_TERMINAL_STATE
                // Non-WAIT without start retains IDLE or the terminal result.
                // A late observed has no effect, and budget_cycles is ignored.
            end
        end
    end

    // Unsupported widths are simulation-only diagnostic guards. Port and
    // internal widths are clamped so the guard is reached without a range
    // error. This is not hardware initialization or synthesis approval.
    // synthesis translate_off
    initial begin
        #0;
        if ((BUDGET_W < 1) || (BUDGET_W > 32)) begin
            $display("DEEPEYE_FIRST_CAPTURE_INVALID_PARAM BUDGET_W=%0d SAFE_BUDGET_W=%0d",
                     BUDGET_W, BUDGET_AW);
            $fatal(1, "DEEPEYE_FIRST_CAPTURE_INVALID_PARAM unsupported width");
        end
    end
    // synthesis translate_on

endmodule
