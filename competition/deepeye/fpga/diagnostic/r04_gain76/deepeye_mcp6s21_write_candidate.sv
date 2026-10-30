`default_nettype none

// CANDIDATE-ONLY write-only MCP6S21 gain master seam.
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1; work B-R04-GAIN-PROTOCOL-SOURCE-20261030-76.
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements SHA256
// c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804; pin f5989cd5defce561f9ba98e6b18fc2682945f0a2.
// No SO/readback, ADC access, pin/top/clock integration, analog result or physical-compliance claim.

module deepeye_mcp6s21_write_candidate (
    input wire logic        clk,
    input wire logic        rst,
    input wire logic        enable,
    input wire logic        cancel,
    input wire logic        cmd_valid,
    output logic        cmd_ready,
    input wire logic [2:0]  gain_code,
    input wire logic [31:0] tag,
    output logic        accepted,
    output logic        aborted,
    output logic        result_valid,
    input wire logic        result_ready,
    output logic        result_error,
    output logic [31:0] result_tag,
    output logic        spi_cs_n,
    output logic        spi_sck,
    output logic        spi_si
);

    localparam integer HALF_PERIOD_TICKS = 100;
    localparam integer CS_GUARD_TICKS    = 100;

    typedef enum logic [2:0] {
        S_IDLE,
        S_CS_SETUP,
        S_SCK_HIGH,
        S_SCK_LOW,
        S_CS_HOLD,
        S_CS_GAP
    } state_t;

    state_t      state;
    logic [15:0] phase_count;
    logic [3:0]  bit_index;
    logic [15:0] shift_reg;
    logic [31:0] active_tag;
    logic        legal_gain;
    logic        active;

    assign legal_gain = (gain_code == 3'd0) || (gain_code == 3'd1) ||
                        (gain_code == 3'd2) || (gain_code == 3'd4);
    assign active = (state == S_CS_SETUP) || (state == S_SCK_HIGH) ||
                    (state == S_SCK_LOW)  || (state == S_CS_HOLD);
    assign cmd_ready = !rst && enable && !cancel && (state == S_IDLE) && !result_valid;

    always_ff @(posedge clk) begin
        accepted <= 1'b0;
        aborted  <= 1'b0;

        if (result_valid && result_ready)
            result_valid <= 1'b0;

        if (rst) begin
            if (active)
                aborted <= 1'b1;
            state        <= S_CS_GAP;
            phase_count  <= '0;
            bit_index    <= '0;
            shift_reg    <= '0;
            active_tag   <= '0;
            result_valid <= 1'b0;
            result_error <= 1'b0;
            result_tag   <= '0;
            spi_cs_n     <= 1'b1;
            spi_sck      <= 1'b0;
            spi_si       <= 1'b0;
        end else if (active && (!enable || cancel)) begin
            state        <= S_CS_GAP;
            phase_count  <= '0;
            bit_index    <= '0;
            spi_cs_n     <= 1'b1;
            spi_sck      <= 1'b0;
            spi_si       <= 1'b0;
            aborted      <= 1'b1;
            result_valid <= 1'b1;
            result_error <= 1'b1;
            result_tag   <= active_tag;
        end else begin
            case (state)
                S_IDLE: begin
                    spi_cs_n <= 1'b1;
                    spi_sck  <= 1'b0;
                    spi_si   <= 1'b0;
                    if (cmd_valid && cmd_ready) begin
                        if (legal_gain) begin
                            shift_reg   <= {8'h40, 5'b00000, gain_code};
                            active_tag  <= tag;
                            phase_count <= '0;
                            bit_index   <= '0;
                            spi_cs_n    <= 1'b0;
                            accepted    <= 1'b1;
                            state       <= S_CS_SETUP;
                        end else begin
                            result_valid <= 1'b1;
                            result_error <= 1'b1;
                            result_tag   <= tag;
                        end
                    end
                end

                S_CS_SETUP: begin
                    if (phase_count == CS_GUARD_TICKS-1) begin
                        phase_count <= '0;
                        spi_sck     <= 1'b1;
                        state       <= S_SCK_HIGH;
                    end else begin
                        phase_count <= phase_count + 1'b1;
                    end
                end

                S_SCK_HIGH: begin
                    if (phase_count == HALF_PERIOD_TICKS-1) begin
                        phase_count <= '0;
                        spi_sck     <= 1'b0;
                        if (bit_index == 4'd15) begin
                            spi_si <= 1'b0;
                            state  <= S_CS_HOLD;
                        end else begin
                            spi_si    <= shift_reg[14];
                            shift_reg <= {shift_reg[14:0], 1'b0};
                            bit_index <= bit_index + 1'b1;
                            state     <= S_SCK_LOW;
                        end
                    end else begin
                        phase_count <= phase_count + 1'b1;
                    end
                end

                S_SCK_LOW: begin
                    if (phase_count == HALF_PERIOD_TICKS-1) begin
                        phase_count <= '0;
                        spi_sck     <= 1'b1;
                        state       <= S_SCK_HIGH;
                    end else begin
                        phase_count <= phase_count + 1'b1;
                    end
                end

                S_CS_HOLD: begin
                    if (phase_count == CS_GUARD_TICKS-1) begin
                        phase_count  <= '0;
                        spi_cs_n     <= 1'b1;
                        result_valid <= 1'b1;
                        result_error <= 1'b0;
                        result_tag   <= active_tag;
                        state        <= S_CS_GAP;
                    end else begin
                        phase_count <= phase_count + 1'b1;
                    end
                end

                S_CS_GAP: begin
                    if (phase_count == CS_GUARD_TICKS-1) begin
                        phase_count <= '0;
                        state       <= S_IDLE;
                    end else begin
                        phase_count <= phase_count + 1'b1;
                    end
                end

                default: begin
                    spi_cs_n <= 1'b1;
                    spi_sck  <= 1'b0;
                    spi_si   <= 1'b0;
                    state    <= S_IDLE;
                end
            endcase
        end
    end
endmodule

`default_nettype wire
