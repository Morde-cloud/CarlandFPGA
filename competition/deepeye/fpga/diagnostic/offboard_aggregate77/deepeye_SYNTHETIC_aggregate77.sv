// Explicitly SYNTHETIC fixture enable and clock50MHz/baud5M only.
`default_nettype none
module deepeye_SYNTHETIC_aggregate77(
 input wire logic clk,rst,cancel,capture_rearm,collect_rearm,seal,enabled,
 input wire logic [31:0] rearm_tag,
 input wire logic sample_strobe,input wire logic [1:0] sample_channel,
 input wire logic [15:0] sample_data,input wire logic [63:0] sample_qpc,
 input wire logic [7:0] sample_quality,
 input wire logic semantics_valid,valid_sample,held,
 input wire logic offer_allowed,result_ready,
 output logic tx,result_valid,output logic [2:0] result_error,
 output logic [5:0] result_bytes,
 output logic refused,output logic [3:0] refusal_code,count,
 output logic quiescent,aborted
);
 logic cap_valid,cap_ready,lane_valid,lane_ready;
 logic [63:0] cap_data;logic [255:0] cap_ticks;
 logic [31:0] cap_quality,cap_first,cap_last,cap_tag;
 logic armed;logic [2:0] partial_len,queue_level;
 logic [1:0] lane_channel;logic [15:0] lane_data;logic [63:0] lane_qpc;
 logic [7:0] lane_quality;logic [31:0] lane_first,lane_last,lane_tag;
 logic block_valid,block_ready,adapter_ready,retire,busy,collector_quiet;
 logic [1:0] channel;logic [47:0] data;
 logic [191:0] qpcs;logic [23:0] qualities;
 logic [95:0] firsts,lasts;logic [31:0] tag,first_index;
 logic [62:0] origin;logic [63:0] stride_ns;logic [15:0] stride_us;
 wire path_cancel=cancel || !enabled;
 logic invalid_rearm;
 wire adapter_cancel=path_cancel || invalid_rearm;
 deepeye_buffered_scan_capture capture_i(
  .clk(clk),.rst(rst),.stop(path_cancel),.rearm(capture_rearm),.queue_cancel(path_cancel||capture_rearm),
  .sample_strobe(sample_strobe),.rearm_tag(rearm_tag),.sample_channel(sample_channel),
  .sample_data(sample_data),.sample_tick(sample_qpc),.sample_quality(sample_quality),
  .out_ready(cap_ready),.out_valid(cap_valid),.out_data(cap_data),.out_ticks(cap_ticks),
  .out_quality(cap_quality),.out_first_seq(cap_first),.out_last_seq(cap_last),.out_tag(cap_tag),
  .capture_armed(armed),.capture_partial_len(partial_len),.capture_next_seq(),.capture_seq_exhausted(),
  .capture_order_error_event(),.capture_overrun_event(),.capture_seq_exhaust_event(),
  .capture_stat_events(),.capture_stat_scans(),.capture_stat_retired(),.capture_stat_discarded_samples(),
  .capture_stat_order_errors(),.capture_stat_overruns(),.queue_level(queue_level),
  .queue_stat_accepted(),.queue_stat_retired(),.queue_stat_aborted());
 deepeye_scan_lane_stream lane_i(
  .clk(clk),.rst(rst),.cancel(path_cancel||capture_rearm),.in_valid(cap_valid),.in_ready(cap_ready),
  .in_data(cap_data),.in_ticks(cap_ticks),.in_quality(cap_quality),.in_first_seq(cap_first),
  .in_last_seq(cap_last),.in_tag(cap_tag),.out_valid(lane_valid),.out_ready(lane_ready),
  .out_channel(lane_channel),.out_data(lane_data),.out_tick(lane_qpc),.out_quality(lane_quality),
  .out_first_seq(lane_first),.out_last_seq(lane_last),.out_tag(lane_tag),.out_last());
 deepeye_aggregate12_candidate collector_i(
  .clk(clk),.rst(rst),.cancel(path_cancel),.rearm(collect_rearm),.seal(seal),.origin_qpc_ns(63'd9007199254740993),
  .s_valid(lane_valid),.s_ready(lane_ready),.s_channel(lane_channel),.s_data(lane_data),
  .s_qpc_ns(lane_qpc),.s_quality(lane_quality),.s_tag(lane_tag),.s_first_seq(lane_first),.s_last_seq(lane_last),
  .semantics_valid(semantics_valid),.valid_sample(valid_sample),.held(held),
  .out_valid(block_valid),.out_ready(block_ready),.retire(retire),.out_channel(channel),.out_data(data),
  .out_qpcs(qpcs),.out_qualities(qualities),.out_first_seqs(firsts),.out_last_seqs(lasts),
  .out_tag(tag),.out_first_index(first_index),.out_origin_qpc_ns(origin),
  .out_stride_ns(stride_ns),.out_stride_us(stride_us),.refused(refused),.refusal_code(refusal_code),.quiescent(collector_quiet),.invalid_rearm(invalid_rearm),.count(count));
 assign block_ready=adapter_ready && offer_allowed;
 deepeye_aggregate_uart_candidate adapter_i(
  .clk(clk),.rst(rst),.cancel(adapter_cancel),.enabled(enabled),.block_valid(block_valid&&offer_allowed),.block_ready(adapter_ready),
  .block_channel(channel),.block_data(data),.block_qpcs(qpcs),.block_qualities(qualities),
  .block_tag(tag),.block_first_index(first_index),.block_origin(origin),.block_stride_ns(stride_ns),.block_stride_us(stride_us),
  .tx(tx),.result_valid(result_valid),.result_ready(result_ready),.result_error(result_error),.result_bytes(result_bytes),
  .retire(retire),.aborted(aborted),.busy(busy));
 assign quiescent=collector_quiet && !armed && partial_len==0 && queue_level==0 && !cap_valid && !lane_valid && !busy;
endmodule
`default_nettype wire
