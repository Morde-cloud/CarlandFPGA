// deepeye_crc16_byte - one-byte CRC16/CCITT-FALSE mathematical update.
//
// Work: B-CRC16-BYTE-20261024-27-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-CRC16-BYTE-20261024-27
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// This is only the unreflected mathematical byte update. Seeding, packet
// framing, field acceptance, reset, and storage belong to callers.

`default_nettype none

module deepeye_crc16_byte (
    input  wire logic [15:0] crc_in,
    input  wire logic [7:0]  data_in,
    output logic [15:0] crc_out
);

    function automatic logic [15:0] crc_bit_step(
        input logic [15:0] state,
        input logic        data_bit
    );
        begin
            if (state[15] ^ data_bit) begin
                crc_bit_step = (state << 1) ^ 16'h1021;
            end else begin
                crc_bit_step = state << 1;
            end
        end
    endfunction

    logic [15:0] bit_step_1;
    logic [15:0] bit_step_2;
    logic [15:0] bit_step_3;
    logic [15:0] bit_step_4;
    logic [15:0] bit_step_5;
    logic [15:0] bit_step_6;
    logic [15:0] bit_step_7;
    logic [15:0] bit_step_8;

    assign bit_step_1 = crc_bit_step(crc_in,     data_in[7]);
    assign bit_step_2 = crc_bit_step(bit_step_1, data_in[6]);
    assign bit_step_3 = crc_bit_step(bit_step_2, data_in[5]);
    assign bit_step_4 = crc_bit_step(bit_step_3, data_in[4]);
    assign bit_step_5 = crc_bit_step(bit_step_4, data_in[3]);
    assign bit_step_6 = crc_bit_step(bit_step_5, data_in[2]);
    assign bit_step_7 = crc_bit_step(bit_step_6, data_in[1]);
    assign bit_step_8 = crc_bit_step(bit_step_7, data_in[0]);

    assign crc_out = bit_step_8;

endmodule

`default_nettype wire
