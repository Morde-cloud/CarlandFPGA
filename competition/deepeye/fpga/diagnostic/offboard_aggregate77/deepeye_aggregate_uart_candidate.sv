// One latched triplet, three original raw samples, unchanged B73 wrapper.
`default_nettype none
module deepeye_aggregate_uart_candidate(
 input wire logic clk,rst,cancel,enabled,
 input wire logic block_valid,output logic block_ready,
 input wire logic [1:0] block_channel,
 input wire logic [47:0] block_data,
 input wire logic [191:0] block_qpcs,
 input wire logic [23:0] block_qualities,
 input wire logic [31:0] block_tag,block_first_index,
 input wire logic [62:0] block_origin,
 input wire logic [63:0] block_stride_ns,
 input wire logic [15:0] block_stride_us,
 output logic tx,result_valid,input wire logic result_ready,
 output logic [2:0] result_error,output logic [5:0] result_bytes,
 output logic retire,aborted,busy
);
 localparam logic [2:0] IDLE=0,DESCRIBE=1,SAMPLES=2,RESULT=3;
 logic [2:0] state;
 logic [47:0] data_q;logic [63:0] first_q,stride_q;
 logic [62:0] origin_q;logic [7:0] quality_q;logic [1:0] channel_q,sample_no;
 logic [31:0] index_q;logic [15:0] stride_us_q;
 logic blk_ready,s_ready,res_valid;logic [3:0] refusal;
 wire [63:0] relative_ns=first_q-{1'b0,origin_q};
 // Explicit destination width; mathematical modulo1000 is always0..999.
 wire [9:0] remainder_ns=relative_ns%64'd1000;
 assign block_ready=state==IDLE && enabled && !rst && !cancel;
 assign result_valid=res_valid && state==RESULT && !rst && !cancel;
 assign retire=result_valid && result_ready;
 assign busy=state!=IDLE;
 deepeye_trace_block_uart_50mhz_candidate #(.CLOCK_HZ(50000000),.BAUD(5000000)) uart_i(
  .clk(clk),.rst(rst),.cancel(cancel),.profile_v2_authorized(enabled),.transport_allowed(enabled),
  .blk_valid(state==DESCRIBE),.blk_ready(blk_ready),.blk_count(8'd3),.blk_e(4'd0),
  .blk_session(32'h12345678),.blk_channel(channel_q),.blk_first_index(index_q),.blk_index_stride(16'd4),
  .blk_first_qpc_ns(first_q),.blk_first_tick_us(relative_ns/64'd1000),.blk_first_remainder_ns(remainder_ns),
  .blk_tick_stride_ns(stride_q),.blk_tick_stride_us(stride_us_q),.blk_origin_qpc_ns(origin_q),
  .blk_origin_tick_us(64'd0),.blk_origin_remainder_ns(10'd0),.blk_raw_quality(quality_q),
  .blk_semantics_valid(1'b1),.blk_valid_sample(1'b1),.blk_saturated(1'b0),.blk_held(1'b0),.blk_source_fault(1'b0),
  .blk_source_qpc_ns(first_q),.blk_source_tick_us(relative_ns/64'd1000),.blk_source_remainder_ns(remainder_ns),
  .cfg_epoch(8'd9),.cfg_seq(16'd300+{14'd0,channel_q}),
  .s_valid(state==SAMPLES),.s_ready(s_ready),.s_data(data_q[16*sample_no+:16]),.s_last(sample_no==2),
  .tx(tx),.result_valid(res_valid),.result_ready(result_ready && state==RESULT),
  .result_error(result_error),.result_bytes(result_bytes),.last_refusal_code(refusal),
  .cancel_active(),.transaction_aborted(aborted),.busy(),.wire_faulted(),.transport_profile_unset());
 always_ff @(posedge clk)begin
  if(rst || cancel || !enabled)begin state<=IDLE;sample_no<=0;data_q<=0;first_q<=0;origin_q<=0;stride_q<=0;stride_us_q<=0;quality_q<=0;channel_q<=0;index_q<=0;end
  else case(state)
   IDLE:if(block_valid && block_ready)begin
    data_q<=block_data;first_q<=block_qpcs[63:0];quality_q<=block_qualities[7:0];
    origin_q<=block_origin;stride_q<=block_stride_ns;stride_us_q<=block_stride_us;
    channel_q<=block_channel;index_q<=block_first_index;state<=DESCRIBE;sample_no<=0;
   end
   DESCRIBE:if(blk_ready)state<=SAMPLES;
   SAMPLES:if(res_valid)state<=RESULT;else if(s_ready)begin
    if(sample_no==2)state<=RESULT;else sample_no<=sample_no+1;
   end
   RESULT:if(retire)state<=IDLE;
   default:state<=IDLE;
  endcase
 end
endmodule
`default_nettype wire
