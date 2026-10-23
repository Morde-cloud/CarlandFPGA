// deepeye_buffered_block_stream - bounded sample-to-buffered-byte composition.
//
// Operation: B-DEEPEYE-BUFFERED-BLOCK-STREAM-20261024-35
// Task: DEEPEYE-IMPLEMENTATION-20261014/v1
// Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15), requirements
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Frozen design: 1011259415a0916054eb580687612580bc1e5f09.
//
// CANDIDATE-ONLY.  This is a stateless, same-clock composition of the frozen
// deepeye_block_stream and deepeye_encoded_frame_queue.  It adds no storage,
// state machine, retry, fault waiver, counter or protocol policy.  The wrapper
// is not TRACE, a public ABI, QoS, BOOT/tick logic, source-clock CDC, motion
// authority, B01/B03/full-product acceptance, or a board result.

module deepeye_buffered_block_stream (
    input  logic        clk,
    input  logic        rst,
    input  logic        cancel,

    input  logic        cfg_valid,
    output logic        cfg_ready,
    input  logic [7:0]  cfg_count,
    input  logic [3:0]  cfg_e,
    input  logic [15:0] cfg_tag,

    input  logic        s_valid,
    output logic        s_ready,
    input  logic [15:0] s_data,
    input  logic        s_last,

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

    output logic        out_valid,
    input  logic        out_ready,
    output logic [7:0]  out_data,
    output logic        out_last,

    output logic [1:0]  stream_level,
    output logic        stream_filling,
    output logic [1:0]  queue_level,
    output logic        queue_receiving,
    output logic        queue_faulted,
    output logic        queue_fault_event,
    output logic [1:0]  queue_fault_code,

    output logic [31:0] stream_stat_cfg,
    output logic [31:0] stream_stat_samples,
    output logic [31:0] stream_stat_ok,
    output logic [31:0] stream_stat_error,
    output logic [31:0] stream_stat_aborted,

    output logic [31:0] queue_stat_meta,
    output logic [31:0] queue_stat_in_bytes,
    output logic [31:0] queue_stat_retired,
    output logic [31:0] queue_stat_aborted,
    output logic [31:0] queue_stat_fault
);

    logic        stream_meta_valid;
    logic        stream_meta_ready;
    logic [15:0] stream_meta_tag;
    logic [1:0]  stream_meta_error;
    logic [7:0]  stream_meta_count;
    logic [3:0]  stream_meta_e;
    logic        stream_meta_raw;
    logic [3:0]  stream_meta_k;
    logic [11:0] stream_meta_valid_bits;
    logic [8:0]  stream_meta_bytes;

    logic        stream_m_valid;
    logic        stream_m_ready;
    logic [7:0]  stream_m_data;
    logic        stream_m_last;

    deepeye_block_stream u_block_stream (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .cfg_valid(cfg_valid),
        .cfg_ready(cfg_ready),
        .cfg_count(cfg_count),
        .cfg_e(cfg_e),
        .cfg_tag(cfg_tag),
        .s_valid(s_valid),
        .s_ready(s_ready),
        .s_data(s_data),
        .s_last(s_last),
        .meta_valid(stream_meta_valid),
        .meta_ready(stream_meta_ready),
        .meta_tag(stream_meta_tag),
        .meta_error(stream_meta_error),
        .meta_count(stream_meta_count),
        .meta_e(stream_meta_e),
        .meta_raw(stream_meta_raw),
        .meta_k(stream_meta_k),
        .meta_valid_bits(stream_meta_valid_bits),
        .meta_bytes(stream_meta_bytes),
        .m_valid(stream_m_valid),
        .m_ready(stream_m_ready),
        .m_data(stream_m_data),
        .m_last(stream_m_last),
        .level(stream_level),
        .filling(stream_filling),
        .stat_cfg(stream_stat_cfg),
        .stat_samples(stream_stat_samples),
        .stat_ok(stream_stat_ok),
        .stat_error(stream_stat_error),
        .stat_aborted(stream_stat_aborted)
    );

    deepeye_encoded_frame_queue u_encoded_frame_queue (
        .clk(clk),
        .rst(rst),
        .cancel(cancel),
        .in_meta_valid(stream_meta_valid),
        .in_meta_ready(stream_meta_ready),
        .in_meta_tag(stream_meta_tag),
        .in_meta_error(stream_meta_error),
        .in_meta_count(stream_meta_count),
        .in_meta_e(stream_meta_e),
        .in_meta_raw(stream_meta_raw),
        .in_meta_k(stream_meta_k),
        .in_meta_valid_bits(stream_meta_valid_bits),
        .in_meta_bytes(stream_meta_bytes),
        .in_valid(stream_m_valid),
        .in_ready(stream_m_ready),
        .in_data(stream_m_data),
        .in_last(stream_m_last),
        .out_meta_valid(out_meta_valid),
        .out_meta_ready(out_meta_ready),
        .out_meta_tag(out_meta_tag),
        .out_meta_error(out_meta_error),
        .out_meta_count(out_meta_count),
        .out_meta_e(out_meta_e),
        .out_meta_raw(out_meta_raw),
        .out_meta_k(out_meta_k),
        .out_meta_valid_bits(out_meta_valid_bits),
        .out_meta_bytes(out_meta_bytes),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_data(out_data),
        .out_last(out_last),
        .level(queue_level),
        .receiving(queue_receiving),
        .faulted(queue_faulted),
        .fault_event(queue_fault_event),
        .fault_code(queue_fault_code),
        .stat_meta(queue_stat_meta),
        .stat_in_bytes(queue_stat_in_bytes),
        .stat_retired(queue_stat_retired),
        .stat_aborted(queue_stat_aborted),
        .stat_fault(queue_stat_fault)
    );

endmodule
