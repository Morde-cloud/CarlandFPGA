// deepeye_encoded_frame_queue - two-slot encoded-frame queue candidate.
//
// Work: B-ENCODED-FRAME-QUEUE-RTL-20261022-20-v1
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Operation: B-DEEPEYE-ENCODED-FRAME-QUEUE-20261022-20
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// CANDIDATE-ONLY.  This module stores at most two complete encoded frames.  It
// has exactly two 256 x 8 payload banks and two descriptor records.  The ports
// below are internal candidate RTL ports, not a public ABI, register map, TRACE
// layout, BOOT/tick source, motion authority or board/system acceptance claim.
//
// All ready/valid decisions use pre-edge state.  rst and cancel are synchronous
// active-high; rst has priority over cancel.  Either input gates every ready and
// valid low on that edge and suppresses every transfer.  There is no same-edge
// input-to-output bypass, no descriptor-to-first-payload acceptance and no
// output-metadata-to-first-output-byte delivery.  A frame becomes visible only
// after its final accepted payload byte seals it.
//
// A descriptor is admitted when not faulted, no payload is open and the old
// level is below two.  A simultaneous retire never creates admission credit at
// old level two; the one-cycle bubble is intentional.  An accepted descriptor
// reserves the tail slot immediately.  Duplicate tags are legal and are not
// slot identities.
//
// Framing validation is local and limited to this queue's transport contract:
//   * error == 0: 1 <= bytes <= 256 and 8*(bytes-1) < valid_bits <= 8*bytes.
//   * error != 0: bytes == 0 and valid_bits == 0; the original metadata is
//     sealed immediately and forwarded with no payload.  Error code 3 is an
//     opaque injected code with no producer or public meaning here.
//   * anything else reserves the slot, latches fault_code 1 and never exposes
//     that slot.  A payload last/length mismatch latches fault_code 2.  A
//     faulted queue blocks new input but lets older sealed frames drain.
//
// The counters saturate at 2**STAT_W-1 and never affect data flow.  STAT_W is
// diagnostic width only.  Before saturation and between resets,
// stat_meta == stat_retired + stat_aborted + level.

`define DEEPEYE_EFQ_STAT_W ((STAT_W < 2) ? 2 : ((STAT_W > 32) ? 32 : STAT_W))

module deepeye_encoded_frame_queue #(
    parameter integer STAT_W = 32
) (
    input  logic clk,
    input  logic rst,
    input  logic cancel,

    input  logic        in_meta_valid,
    output logic        in_meta_ready,
    input  logic [15:0] in_meta_tag,
    input  logic [1:0]  in_meta_error,
    input  logic [7:0]  in_meta_count,
    input  logic [3:0]  in_meta_e,
    input  logic        in_meta_raw,
    input  logic [3:0]  in_meta_k,
    input  logic [11:0] in_meta_valid_bits,
    input  logic [8:0]  in_meta_bytes,

    input  logic       in_valid,
    output logic       in_ready,
    input  logic [7:0] in_data,
    input  logic       in_last,

    output logic        out_meta_valid,
    input  logic        out_meta_ready,
    output logic [15:0] out_meta_tag,
    output logic [1:0]  out_meta_error,
    output logic [7:0]  out_meta_count,
    output logic [3:0]  out_meta_e,
    output logic        out_meta_raw,
    output logic [3:0]  out_meta_k,
    output logic [11:0] out_meta_valid_bits,
    output logic [8:0]  out_meta_bytes,

    output logic       out_valid,
    input  logic       out_ready,
    output logic [7:0] out_data,
    output logic       out_last,

    output logic [1:0] level,
    output logic       receiving,
    output logic       faulted,
    output logic       fault_event,
    output logic [1:0] fault_code,

    output logic [`DEEPEYE_EFQ_STAT_W-1:0] stat_meta,
    output logic [`DEEPEYE_EFQ_STAT_W-1:0] stat_in_bytes,
    output logic [`DEEPEYE_EFQ_STAT_W-1:0] stat_retired,
    output logic [`DEEPEYE_EFQ_STAT_W-1:0] stat_aborted,
    output logic [`DEEPEYE_EFQ_STAT_W-1:0] stat_fault
);

    localparam integer STAT_W_INT = (STAT_W < 2) ? 2 : ((STAT_W > 32) ? 32 : STAT_W);
    localparam logic [STAT_W_INT-1:0] STAT_MAX = {STAT_W_INT{1'b1}};

    localparam logic [1:0] SLOT_FREE = 2'd0;
    localparam logic [1:0] SLOT_RECV = 2'd1;
    localparam logic [1:0] SLOT_SEAL = 2'd2;
    localparam logic [1:0] SLOT_POISON = 2'd3;

    logic [7:0] bank_mem [0:1][0:255];

    logic [1:0]  slot_status [0:1];
    logic [1:0]  slot_fault [0:1];
    logic        slot_meta_done [0:1];
    logic [15:0] slot_tag [0:1];
    logic [1:0]  slot_error [0:1];
    logic [7:0]  slot_count [0:1];
    logic [3:0]  slot_e [0:1];
    logic        slot_raw [0:1];
    logic [3:0]  slot_k [0:1];
    logic [11:0] slot_valid_bits [0:1];
    logic [8:0]  slot_bytes [0:1];

    logic [1:0] level_q;
    logic       head_q;
    logic       tail_q;
    logic       receiving_q;
    logic       fill_slot_q;
    logic [7:0] fill_index_q;
    logic [7:0] out_index_q;
    logic       faulted_q;
    logic       fault_event_q;
    logic [1:0] fault_code_q;

    logic [STAT_W_INT-1:0] stat_meta_q;
    logic [STAT_W_INT-1:0] stat_in_bytes_q;
    logic [STAT_W_INT-1:0] stat_retired_q;
    logic [STAT_W_INT-1:0] stat_aborted_q;
    logic [STAT_W_INT-1:0] stat_fault_q;

    logic [12:0] in_bytes_ext;
    logic [12:0] in_bytes_m1_x8;
    logic [12:0] in_bytes_x8;
    logic [12:0] in_valid_bits_ext;
    logic        descriptor_success;
    logic        descriptor_upstream_error;
    logic        descriptor_invalid;

    logic meta_fire;
    logic payload_fire;
    logic out_meta_fire;
    logic out_fire;
    logic retire_error_meta;
    logic retire_success_payload;
    logic retire_fire;
    logic expected_last;
    logic payload_mismatch;
    logic payload_seal;
    logic head_has_payload;

    integer slot_index;

    function automatic logic [STAT_W_INT-1:0] sat_inc(
        input logic [STAT_W_INT-1:0] value
    );
        sat_inc = (value == STAT_MAX) ? value : (value + 1'b1);
    endfunction

    function automatic logic [STAT_W_INT-1:0] sat_add_level(
        input logic [STAT_W_INT-1:0] value,
        input logic [1:0] amount
    );
        logic [STAT_W_INT-1:0] amount_ext;
        begin
            amount_ext = '0;
            amount_ext[1:0] = amount;
            if (value > (STAT_MAX - amount_ext)) begin
                sat_add_level = STAT_MAX;
            end else begin
                sat_add_level = value + amount_ext;
            end
        end
    endfunction

    assign in_bytes_ext       = {4'b0, in_meta_bytes};
    assign in_bytes_m1_x8     = (in_bytes_ext - 13'd1) << 3;
    assign in_bytes_x8        = in_bytes_ext << 3;
    assign in_valid_bits_ext  = {1'b0, in_meta_valid_bits};

    always_comb begin
        descriptor_success        = 1'b0;
        descriptor_upstream_error = 1'b0;
        descriptor_invalid        = 1'b1;

        if (in_meta_error == 2'd0) begin
            if ((in_meta_bytes != 9'd0) && (in_meta_bytes <= 9'd256) &&
                (in_valid_bits_ext > in_bytes_m1_x8) &&
                (in_valid_bits_ext <= in_bytes_x8)) begin
                descriptor_success = 1'b1;
                descriptor_invalid = 1'b0;
            end
        end else begin
            if ((in_meta_bytes == 9'd0) && (in_meta_valid_bits == 12'd0)) begin
                descriptor_upstream_error = 1'b1;
                descriptor_invalid        = 1'b0;
            end
        end
    end

    assign in_meta_ready = !rst && !cancel && !faulted_q &&
                           !receiving_q && (level_q < 2'd2);
    assign in_ready      = !rst && !cancel && !faulted_q && receiving_q;

    assign meta_fire    = in_meta_valid && in_meta_ready;
    assign payload_fire = in_valid && in_ready;

    assign head_has_payload = (slot_status[head_q] == SLOT_SEAL) &&
                              (slot_error[head_q] == 2'd0) &&
                              (slot_bytes[head_q] != 9'd0);

    assign out_meta_valid = !rst && !cancel && (level_q != 2'd0) &&
                            (slot_status[head_q] == SLOT_SEAL) &&
                            !slot_meta_done[head_q];
    assign out_valid      = !rst && !cancel && (level_q != 2'd0) &&
                            (slot_status[head_q] == SLOT_SEAL) &&
                            slot_meta_done[head_q] && head_has_payload;

    assign out_meta_tag        = slot_tag[head_q];
    assign out_meta_error      = slot_error[head_q];
    assign out_meta_count      = slot_count[head_q];
    assign out_meta_e          = slot_e[head_q];
    assign out_meta_raw        = slot_raw[head_q];
    assign out_meta_k          = slot_k[head_q];
    assign out_meta_valid_bits = slot_valid_bits[head_q];
    assign out_meta_bytes      = slot_bytes[head_q];

    assign out_data = bank_mem[head_q][out_index_q];
    assign out_last = (out_index_q == (slot_bytes[head_q] - 9'd1));

    assign out_meta_fire = out_meta_valid && out_meta_ready;
    assign out_fire      = out_valid && out_ready;

    assign retire_error_meta      = out_meta_fire && !head_has_payload;
    assign retire_success_payload = out_fire && out_last;
    assign retire_fire            = retire_error_meta || retire_success_payload;

    assign expected_last   = (fill_index_q == (slot_bytes[fill_slot_q] - 9'd1));
    assign payload_mismatch = payload_fire && (in_last != expected_last);
    assign payload_seal     = payload_fire && (in_last == expected_last) && in_last;

    assign level     = level_q;
    assign receiving = receiving_q;
    assign faulted   = faulted_q;
    assign fault_event = fault_event_q;
    assign fault_code  = fault_code_q;

    assign stat_meta      = stat_meta_q;
    assign stat_in_bytes  = stat_in_bytes_q;
    assign stat_retired   = stat_retired_q;
    assign stat_aborted   = stat_aborted_q;
    assign stat_fault     = stat_fault_q;

    // Parameter guard: keep the declaration widths legal for 0/1/33 so the
    // exact simulation-time fatal is reached instead of a compile failure.
    generate
        if ((STAT_W < 2) || (STAT_W > 32)) begin : g_invalid_stat_w
            // synthesis translate_off
            initial begin
                $fatal(1, "DEEPEYE_ENCODED_FRAME_QUEUE_INVALID_PARAM STAT_W=%0d", STAT_W);
            end
            // synthesis translate_on
        end
    endgenerate

    always_ff @(posedge clk) begin
        if (rst) begin
            level_q        <= 2'd0;
            head_q         <= 1'b0;
            tail_q         <= 1'b0;
            receiving_q    <= 1'b0;
            fill_slot_q    <= 1'b0;
            fill_index_q   <= 8'd0;
            out_index_q    <= 8'd0;
            faulted_q      <= 1'b0;
            fault_event_q  <= 1'b0;
            fault_code_q   <= 2'd0;
            stat_meta_q    <= '0;
            stat_in_bytes_q<= '0;
            stat_retired_q <= '0;
            stat_aborted_q <= '0;
            stat_fault_q   <= '0;
            for (slot_index = 0; slot_index < 2; slot_index = slot_index + 1) begin
                slot_status[slot_index]    <= SLOT_FREE;
                slot_fault[slot_index]     <= 2'd0;
                slot_meta_done[slot_index] <= 1'b0;
                slot_tag[slot_index]       <= 16'd0;
                slot_error[slot_index]     <= 2'd0;
                slot_count[slot_index]     <= 8'd0;
                slot_e[slot_index]         <= 4'd0;
                slot_raw[slot_index]       <= 1'b0;
                slot_k[slot_index]         <= 4'd0;
                slot_valid_bits[slot_index]<= 12'd0;
                slot_bytes[slot_index]     <= 9'd0;
            end
        end else if (1'b0 && cancel) begin
            stat_aborted_q <= sat_add_level(stat_aborted_q, level_q);
            level_q        <= 2'd0;
            head_q         <= 1'b0;
            tail_q         <= 1'b0;
            receiving_q    <= 1'b0;
            fill_slot_q    <= 1'b0;
            fill_index_q   <= 8'd0;
            out_index_q    <= 8'd0;
            faulted_q      <= 1'b0;
            fault_event_q  <= 1'b0;
            fault_code_q   <= 2'd0;
            for (slot_index = 0; slot_index < 2; slot_index = slot_index + 1) begin
                slot_status[slot_index]    <= SLOT_FREE;
                slot_fault[slot_index]     <= 2'd0;
                slot_meta_done[slot_index] <= 1'b0;
                slot_tag[slot_index]       <= 16'd0;
                slot_error[slot_index]     <= 2'd0;
                slot_count[slot_index]     <= 8'd0;
                slot_e[slot_index]         <= 4'd0;
                slot_raw[slot_index]       <= 1'b0;
                slot_k[slot_index]         <= 4'd0;
                slot_valid_bits[slot_index]<= 12'd0;
                slot_bytes[slot_index]     <= 9'd0;
            end
        end else begin
            fault_event_q <= 1'b0;

            if (meta_fire) begin
                slot_tag[tail_q]        <= in_meta_tag;
                slot_error[tail_q]      <= in_meta_error;
                slot_count[tail_q]      <= in_meta_count;
                slot_e[tail_q]          <= in_meta_e;
                slot_raw[tail_q]        <= in_meta_raw;
                slot_k[tail_q]          <= in_meta_k;
                slot_valid_bits[tail_q] <= in_meta_valid_bits;
                slot_bytes[tail_q]      <= in_meta_bytes;
                slot_meta_done[tail_q]  <= 1'b0;
                slot_fault[tail_q]      <= descriptor_invalid ? 2'd1 : 2'd0;
                tail_q                  <= ~tail_q;
                stat_meta_q             <= sat_inc(stat_meta_q);

                if (descriptor_success) begin
                    slot_status[tail_q] <= SLOT_RECV;
                    fill_slot_q         <= tail_q;
                    fill_index_q        <= 8'd0;
                    receiving_q         <= 1'b1;
                end else if (descriptor_upstream_error) begin
                    slot_status[tail_q] <= SLOT_SEAL;
                end else begin
                    slot_status[tail_q] <= SLOT_POISON;
                    faulted_q           <= 1'b1;
                    fault_event_q       <= 1'b1;
                    fault_code_q        <= 2'd1;
                    stat_fault_q        <= sat_inc(stat_fault_q);
                end
            end

            if (payload_fire) begin
                bank_mem[fill_slot_q][fill_index_q] <= in_data;
                stat_in_bytes_q <= sat_inc(stat_in_bytes_q);

                if (payload_mismatch) begin
                    slot_status[fill_slot_q] <= SLOT_POISON;
                    slot_fault[fill_slot_q]  <= 2'd2;
                    receiving_q              <= 1'b0;
                    faulted_q                <= 1'b1;
                    fault_event_q            <= 1'b1;
                    fault_code_q             <= 2'd2;
                    stat_fault_q             <= sat_inc(stat_fault_q);
                end else if (in_last) begin
                    slot_status[fill_slot_q] <= SLOT_SEAL;
                    receiving_q              <= 1'b0;
                end else begin
                    fill_index_q <= fill_index_q + 8'd1;
                end
            end

            if (out_meta_fire) begin
                if (head_has_payload) begin
                    slot_meta_done[head_q] <= 1'b1;
                    out_index_q            <= 8'd0;
                end
            end

            if (out_fire) begin
                if (!out_last) begin
                    out_index_q <= out_index_q + 8'd1;
                end
            end

            if (retire_fire) begin
                slot_status[head_q]    <= SLOT_FREE;
                slot_fault[head_q]     <= 2'd0;
                slot_meta_done[head_q] <= 1'b0;
                slot_tag[head_q]       <= 16'd0;
                slot_error[head_q]     <= 2'd0;
                slot_count[head_q]     <= 8'd0;
                slot_e[head_q]         <= 4'd0;
                slot_raw[head_q]       <= 1'b0;
                slot_k[head_q]         <= 4'd0;
                slot_valid_bits[head_q]<= 12'd0;
                slot_bytes[head_q]     <= 9'd0;
                head_q                 <= ~head_q;
                out_index_q            <= 8'd0;
                stat_retired_q         <= sat_inc(stat_retired_q);
            end

            if (meta_fire && retire_fire) begin
                level_q <= level_q;
            end else if (meta_fire) begin
                level_q <= level_q + 2'd1;
            end else if (retire_fire) begin
                level_q <= level_q - 2'd1;
            end
        end
    end

endmodule

`undef DEEPEYE_EFQ_STAT_W
