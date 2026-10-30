// ADDITIVE-50 timing/profile source candidate (source-only, unexecuted).
// Task DEEPEYE-IMPLEMENTATION-20261014/v1; work
// B-DEEPEYE-G05-ADDITIVE50-INTEGRATION-SOURCE-20261029-63.
// Contract pin f5989cd5defce561f9ba98e6b18fc2682945f0a2; requirements SHA256
// c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Proposal only: not final clock approval, not a product profile, no clock setter.
package deepeye_g05_profile_50mhz;
    localparam logic [31:0] CLOCK_HZ             = 32'd50000000;
    localparam logic [31:0] TICK_NS              = 32'd20;
    localparam logic [31:0] FRAME_TICKS          = 32'd1000000;
    localparam logic [31:0] FRAME_NS             = 32'd20000000;
    localparam logic signed [31:0] YAW_PITCH_BASE = 32'sd125000;
    localparam logic signed [31:0] YAW_PITCH_STEP = 32'sd8;
    localparam logic [31:0] SPEED_BASE           = 32'd25000;
    localparam logic [31:0] SPEED_STEP           = 32'd500;
    localparam logic [63:0] TTL_TICKS_PER_MS     = 64'd50000;
    localparam logic [31:0] WATCHDOG_FIRST_MULT  = 32'd3;
    localparam logic [31:0] WATCHDOG_NEXT_MULT   = 32'd2;
    localparam logic [31:0] WATCHDOG_GUARD_TICKS = 32'd8;
    localparam logic [31:0] NEAR_TOLERANCE_TICKS = 32'd1;
    localparam logic [31:0] NEAR_TOLERANCE_NS    = 32'd20;
    localparam logic [2:0]  REARM_CYCLES         = 3'd5;
    localparam logic [2:0]  REARM_FALLBACK_CYCLES= 3'd6;
    localparam logic signed [15:0] Q_MIN         = -16'sd15000;
    localparam logic signed [15:0] Q_MAX         = 16'sd15000;
    localparam logic [7:0]  SPEED_MAX            = 8'd20;
    localparam logic [15:0] TTL_MAX_PROFILE1_MS  = 16'd3000;
    localparam logic [15:0] TTL_MAX_PROFILE2_MS  = 16'd12000;
    localparam logic [31:0] MIN_PERIOD_TICKS     = 32'd32;
endpackage
