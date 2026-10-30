// ADDITIVE50 SOURCE/DESIGN ONLY; uncompiled/unexecuted, no clock or ABI activation.
// Original100 comparator51f2ef... at974583f... remains byte-identical.
// Preserve original64-bit square math/legality/ROM; change dimensional constants only.
// Pure SET_TARGET reference mapping. Session/ENABLE/STOP remain external.
module deepeye_g05_command_map_50mhz (
    input  logic [7:0] profile_id,
    input  logic signed [15:0] yaw_q, pitch_q,
    input  logic [7:0] speed_code,
    input  logic [15:0] ttl_ms,
    output logic legal,
    output logic [3:0] reject_bits,
    output logic [31:0] period_ticks, high_yaw, high_pitch, high_speed,
    output logic [63:0] ttl_ticks, curvature_sum, curvature_limit
);
    logic signed [63:0] yaw_wide, pitch_wide;
    logic [63:0] yaw_squared, pitch_squared;

    always_comb begin
        // Widen BEFORE multiplication, including the -32768 input.
        yaw_wide = {{48{yaw_q[15]}}, yaw_q};
        pitch_wide = {{48{pitch_q[15]}}, pitch_q};
        yaw_squared = $unsigned(yaw_wide * yaw_wide);
        pitch_squared = $unsigned(pitch_wide * pitch_wide);
        curvature_sum = yaw_squared + pitch_squared;
        `include "deepeye_g05_curvature_rom_50mhz.svh"

        reject_bits[0] = !((profile_id == 8'd1) || (profile_id == 8'd2));
        reject_bits[1] = (yaw_wide < -64'sd15000) || (yaw_wide > 64'sd15000)
                      || (pitch_wide < -64'sd15000) || (pitch_wide > 64'sd15000)
                      || (speed_code > 8'd20)
                      || ((speed_code == 8'd0) &&
                          ((yaw_wide != 64'sd0) || (pitch_wide != 64'sd0)));
        reject_bits[2] = (ttl_ms == 16'd0)
                      || ((profile_id == 8'd1) && (ttl_ms > 16'd3000))
                      || ((profile_id == 8'd2) && (ttl_ms > 16'd12000));
        reject_bits[3] = (curvature_sum > curvature_limit);
        legal = ~(|reject_bits);

        period_ticks = 32'd0;
        high_yaw = 32'd0;
        high_pitch = 32'd0;
        high_speed = 32'd0;
        ttl_ticks = 64'd0;
        if (legal) begin
            period_ticks = 32'd1000000;
            high_yaw = 32'(64'sd125000 + 64'sd8 * yaw_wide);
            high_pitch = 32'(64'sd125000 + 64'sd8 * pitch_wide);
            high_speed = 32'd25000 + 32'd500 * {24'd0, speed_code};
            ttl_ticks = {48'd0, ttl_ms} * 64'd50000;
        end
    end
endmodule
