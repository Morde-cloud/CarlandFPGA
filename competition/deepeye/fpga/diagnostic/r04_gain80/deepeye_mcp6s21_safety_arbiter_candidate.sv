`default_nettype none

// CANDIDATE-ONLY finite safety wrapper around the adopted r04_gain76 master.
// Task DEEPEYE-IMPLEMENTATION-20261014/v1; work B-R04-LOCAL-OVERRANGE-SOURCE-20261030-80.
// H01-H15 requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// SOURCE_ONLY: no compile, simulation, ADC, pinout, clock constraint, board or analog proof.

module deepeye_mcp6s21_safety_arbiter_candidate (
    input wire logic        clk,
    input wire logic        rst,
    input wire logic        enable,
    input wire logic        arm,
    input wire logic        cancel,
    input wire logic        overrange,
    input wire logic [31:0] reserved_safety_tag,
    input wire logic        host_valid,
    output logic        host_ready,
    input wire logic [2:0]  host_gain_code,
    input wire logic [31:0] host_tag,
    output logic        host_result_valid,
    input wire logic        host_result_ready,
    output logic        host_result_error,
    output logic [31:0] host_result_tag,
    output logic        safety_result_valid,
    input wire logic        safety_result_ready,
    output logic        safety_result_error,
    output logic [31:0] safety_result_tag,
    output logic        armed,
    output logic        inhibit,
    output logic        sticky_fault,
    output logic        spi_cs_n,
    output logic        spi_sck,
    output logic        spi_si
);

    logic        m_cancel, m_cmd_valid, m_cmd_ready;
    logic        m_result_valid, m_result_ready, m_result_error;
    logic [2:0]  m_cmd_gain;
    logic [31:0] m_cmd_tag, m_result_tag;

    logic        armed_q, inhibit_q, sticky_fault_q, host_gate_q, arm_q;
    logic        host_inflight_q, safety_inflight_q, fallback_pending_q;
    logic [31:0] host_inflight_tag_q, safety_inflight_tag_q, safety_tag_q;
    logic        host_result_valid_q, host_result_error_q;
    logic [31:0] host_result_tag_q;
    logic        safety_result_valid_q, safety_result_error_q;
    logic [31:0] safety_result_tag_q;

    logic arm_rise, arm_space_ok, arm_fire, host_tag_ok, host_eligible;
    logic host_fire, fallback_choose, master_fire, host_match, safety_match;
    logic tag_changed, bad_host_tag, arm_zero_tag, master_tag_bad, identity_fault;

    assign armed         = armed_q;
    assign inhibit       = inhibit_q;
    assign sticky_fault  = sticky_fault_q;
    assign host_result_valid = host_result_valid_q;
    assign host_result_error = host_result_error_q;
    assign host_result_tag   = host_result_tag_q;
    assign safety_result_valid = safety_result_valid_q;
    assign safety_result_error = safety_result_error_q;
    assign safety_result_tag   = safety_result_tag_q;

    assign arm_rise = arm && !arm_q;
    assign arm_space_ok = enable && !cancel && !overrange && !sticky_fault_q &&
                          !host_inflight_q && !safety_inflight_q &&
                          !host_result_valid_q && !safety_result_valid_q &&
                          !fallback_pending_q && m_cmd_ready;
    assign arm_fire = arm_rise && (!armed_q || inhibit_q) && arm_space_ok;
    assign host_tag_ok = (host_tag != 32'd0) && (host_tag != safety_tag_q);
    assign host_eligible = enable && !rst && !cancel && !overrange && armed_q && host_gate_q &&
                           !inhibit_q && !sticky_fault_q && !host_inflight_q &&
                           !safety_inflight_q && !host_result_valid_q &&
                           !safety_result_valid_q && !fallback_pending_q && m_cmd_ready;
    assign host_ready = host_eligible && host_tag_ok && !tag_changed && !master_tag_bad;
    assign host_fire = host_valid && host_ready;

    assign fallback_choose = fallback_pending_q && armed_q && !host_inflight_q &&
                             !safety_inflight_q && !safety_result_valid_q;
    assign m_cmd_valid = enable && !rst && !cancel && !sticky_fault_q && !identity_fault &&
                         (fallback_choose || host_fire);
    assign m_cmd_gain = fallback_choose ? 3'd0 : host_gain_code;
    assign m_cmd_tag = fallback_choose ? safety_tag_q : host_tag;
    assign master_fire = m_cmd_valid && m_cmd_ready;
    assign m_cancel = rst || !enable || cancel || sticky_fault_q ||
                      (host_inflight_q && (overrange || inhibit_q));

    assign host_match = host_inflight_q && !safety_inflight_q &&
                        (m_result_tag == host_inflight_tag_q) && !host_result_valid_q;
    assign safety_match = safety_inflight_q && !host_inflight_q &&
                          (m_result_tag == safety_inflight_tag_q) &&
                          !safety_result_valid_q;
    assign m_result_ready = m_result_valid && !sticky_fault_q && !identity_fault &&
                            (host_match || safety_match);

    assign tag_changed = armed_q && (reserved_safety_tag != safety_tag_q);
    assign bad_host_tag = host_valid && host_eligible && !host_tag_ok;
    assign arm_zero_tag = arm_fire && (reserved_safety_tag == 32'd0);
    assign master_tag_bad = m_result_valid && !sticky_fault_q &&
                            !host_match && !safety_match;
    assign identity_fault = tag_changed || bad_host_tag || arm_zero_tag || master_tag_bad;

    always_ff @(posedge clk) begin
        arm_q <= arm;

        if (host_result_valid_q && host_result_ready)
            host_result_valid_q <= 1'b0;
        if (safety_result_valid_q && safety_result_ready)
            safety_result_valid_q <= 1'b0;

        if (rst) begin
            armed_q              <= 1'b0;
            inhibit_q            <= 1'b0;
            sticky_fault_q       <= 1'b0;
            host_gate_q          <= 1'b0;
            host_inflight_q      <= 1'b0;
            safety_inflight_q    <= 1'b0;
            fallback_pending_q   <= 1'b0;
            host_inflight_tag_q  <= 32'd0;
            safety_inflight_tag_q<= 32'd0;
            safety_tag_q         <= 32'd0;
            host_result_valid_q  <= 1'b0;
            host_result_error_q  <= 1'b0;
            host_result_tag_q    <= 32'd0;
            safety_result_valid_q<= 1'b0;
            safety_result_error_q<= 1'b0;
            safety_result_tag_q  <= 32'd0;
        end else if (identity_fault || sticky_fault_q) begin
            sticky_fault_q       <= 1'b1;
            inhibit_q            <= 1'b1;
            armed_q              <= 1'b0;
            host_gate_q          <= 1'b0;
            fallback_pending_q   <= 1'b0;
        end else begin
            if (m_result_valid) begin
                if (host_match) begin
                    host_result_valid_q <= 1'b1;
                    host_result_error_q <= m_result_error;
                    host_result_tag_q   <= m_result_tag;
                    host_inflight_q     <= 1'b0;
                end else if (safety_match) begin
                    safety_result_valid_q <= 1'b1;
                    safety_result_error_q <= m_result_error;
                    safety_result_tag_q   <= m_result_tag;
                    safety_inflight_q     <= 1'b0;
                end
            end

            if (master_fire) begin
                if (fallback_choose) begin
                    safety_inflight_q    <= 1'b1;
                    safety_inflight_tag_q<= safety_tag_q;
                    fallback_pending_q   <= 1'b0;
                end else begin
                    host_inflight_q     <= 1'b1;
                    host_inflight_tag_q <= host_tag;
                end
            end

            if (arm_fire) begin
                armed_q        <= 1'b1;
                inhibit_q      <= 1'b0;
                host_gate_q    <= 1'b0;
                fallback_pending_q <= 1'b0;
                safety_tag_q   <= reserved_safety_tag;
            end

            if (!armed_q || !enable || cancel || inhibit_q || sticky_fault_q)
                host_gate_q <= 1'b0;
            else if (!host_valid)
                host_gate_q <= 1'b1;

            if (overrange && !inhibit_q) begin
                inhibit_q <= 1'b1;
                if (reserved_safety_tag == 32'd0) begin
                    sticky_fault_q     <= 1'b1;
                    armed_q            <= 1'b0;
                    host_gate_q        <= 1'b0;
                    fallback_pending_q <= 1'b0;
                end else if (armed_q) begin
                    if (host_inflight_q && (host_inflight_tag_q == safety_tag_q)) begin
                        sticky_fault_q     <= 1'b1;
                        armed_q            <= 1'b0;
                        host_gate_q        <= 1'b0;
                        fallback_pending_q <= 1'b0;
                    end else if (!safety_inflight_q && !safety_result_valid_q) begin
                        fallback_pending_q <= 1'b1;
                    end
                end
            end

            if (!enable || cancel) begin
                armed_q            <= 1'b0;
                host_gate_q        <= 1'b0;
                fallback_pending_q <= 1'b0;
            end
        end
    end

    deepeye_mcp6s21_write_candidate master (
        .clk(clk),
        .rst(rst),
        .enable(enable),
        .cancel(m_cancel),
        .cmd_valid(m_cmd_valid),
        .cmd_ready(m_cmd_ready),
        .gain_code(m_cmd_gain),
        .tag(m_cmd_tag),
        .accepted(),
        .aborted(),
        .result_valid(m_result_valid),
        .result_ready(m_result_ready),
        .result_error(m_result_error),
        .result_tag(m_result_tag),
        .spi_cs_n(spi_cs_n),
        .spi_sck(spi_sck),
        .spi_si(spi_si)
    );
endmodule

`default_nettype wire
