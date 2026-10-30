// B77 main-selected 12 raw slots -> four genuine fresh channel triplets.
// SYNTHETIC/offboard candidate, no authentication or production enable.
`default_nettype none
module deepeye_aggregate12_candidate(
 input wire logic clk,rst,cancel,rearm,seal,
 input wire logic [62:0] origin_qpc_ns,
 input wire logic s_valid, output logic s_ready,
 input wire logic [1:0] s_channel,
 input wire logic [15:0] s_data,
 input wire logic [63:0] s_qpc_ns,
 input wire logic [7:0] s_quality,
 input wire logic [31:0] s_tag,s_first_seq,s_last_seq,
 input wire logic semantics_valid,valid_sample,held,
 output logic out_valid,input wire logic out_ready,retire,
 output logic [1:0] out_channel,
 output logic [47:0] out_data,
 output logic [191:0] out_qpcs,
 output logic [23:0] out_qualities,
 output logic [95:0] out_first_seqs,out_last_seqs,
 output logic [31:0] out_tag,out_first_index,
 output logic [62:0] out_origin_qpc_ns,
 output logic [63:0] out_stride_ns,
 output logic [15:0] out_stride_us,
 output logic refused,output logic [3:0] refusal_code,
 output logic quiescent,invalid_rearm,output logic [3:0] count
);
 localparam logic [2:0] DISARMED=0,COLLECT=1,FULL=2,OFFER=3,WAIT_RETIRE=4,REFUSED=5;
 logic [2:0] state;
 logic [15:0] values[0:11];
 logic [63:0] qpcs[0:11];
 logic [7:0] qualities[0:11];
 logic [31:0] firsts[0:2],lasts[0:2],tag_q,base_seq;
 logic [62:0] origin_q;
 logic [1:0] channel_q;
 logic bad; logic [3:0] code;
 logic [64:0] expected_first,rel,delta,expected_qpc;
 integer scan_no,ch;
 always_comb begin
  scan_no=count>>2; ch=count&3;
  expected_first={33'd0,base_seq}+((count>>2)*65'd4);
  rel={1'b0,s_qpc_ns}-{2'd0,origin_q};
  delta=(count>=4)?{1'b0,s_qpc_ns}-{1'b0,qpcs[ch]}:65'd0;
  expected_qpc=(count>=8)?{1'b0,qpcs[ch]}+(({1'b0,qpcs[ch+4]}-{1'b0,qpcs[ch]})*65'd2):65'd0;
  bad=0;code=0;
  if(!semantics_valid || !valid_sample || held)begin bad=1;code=1;end
  else if(s_channel!=ch || s_tag==0 || (count!=0 && s_tag!=tag_q))begin bad=1;code=2;end
  else if(({1'b0,s_first_seq}+33'd3)!={1'b0,s_last_seq} ||
          (count==0 && ({1'b0,s_first_seq}+33'd11)>33'h0ffffffff) ||
          (count!=0 && (expected_first[64:32]!=0 || s_first_seq!=expected_first[31:0])))begin bad=1;code=3;end
  else if(s_qpc_ns[63] || s_qpc_ns<{1'b0,origin_q} || rel/65'd1000>65'h0ffffffff)begin bad=1;code=4;end
  else if(count>=4 && s_quality!=qualities[ch])begin bad=1;code=5;end
  else if(count>=4 && (s_qpc_ns<=qpcs[ch] || delta%65'd1000!=0 || delta==0 ||
            (count<8 && delta>65'd65535000) ||
            (count>=8 && (expected_qpc[64:63]!=0 || {1'b0,s_qpc_ns}!=expected_qpc))))begin bad=1;code=6;end
  s_ready=(state==COLLECT) && !rst && !cancel;
  out_valid=(state==OFFER) && !rst && !cancel;
  out_channel=channel_q;out_tag=tag_q;out_origin_qpc_ns=origin_q;
  out_first_index=base_seq+channel_q;
  out_stride_ns=qpcs[channel_q+4]-qpcs[channel_q];out_stride_us=out_stride_ns/1000;
  out_data={values[channel_q+8],values[channel_q+4],values[channel_q]};
  out_qpcs={qpcs[channel_q+8],qpcs[channel_q+4],qpcs[channel_q]};
  out_qualities={qualities[channel_q+8],qualities[channel_q+4],qualities[channel_q]};
  out_first_seqs={firsts[2],firsts[1],firsts[0]};out_last_seqs={lasts[2],lasts[1],lasts[0]};
  refused=(state==REFUSED);quiescent=(state==DISARMED)&&count==0;
  // Refuse busy rearm locally AND let the owner cancel accepted downstream
  // work on this same edge. Refusal alone cannot recall an adapter's offer.
  invalid_rearm=rearm && state!=DISARMED && state!=REFUSED && !rst && !cancel;
 end
 always_ff @(posedge clk)begin
  if(rst || cancel)begin state<=DISARMED;count<=0;channel_q<=0;refusal_code<=0;tag_q<=0;base_seq<=0;origin_q<=0;end
  else if(rearm)begin
   if(state==DISARMED || state==REFUSED)begin state<=COLLECT;count<=0;channel_q<=0;refusal_code<=0;origin_q<=origin_qpc_ns;end
   else begin state<=REFUSED;refusal_code<=9;end
  end else if(seal && state==COLLECT)begin state<=REFUSED;refusal_code<=7;end
  else begin
   case(state)
    COLLECT:if(s_valid && s_ready)begin
     if(bad)begin state<=REFUSED;refusal_code<=code;end
     else begin
      values[count]<=s_data;qpcs[count]<=s_qpc_ns;qualities[count]<=s_quality;
      if(ch==0)begin firsts[scan_no]<=s_first_seq;lasts[scan_no]<=s_last_seq;end
      if(count==0)begin tag_q<=s_tag;base_seq<=s_first_seq;end
      count<=count+1;
      if(count==11)state<=FULL;
     end
    end
    FULL:if(seal)begin state<=OFFER;channel_q<=0;end
    OFFER:if(out_valid && out_ready)state<=WAIT_RETIRE;
    WAIT_RETIRE:if(retire)begin
     if(channel_q==3)begin state<=DISARMED;count<=0;end
     else begin channel_q<=channel_q+1;state<=OFFER;end
    end
    default:;
   endcase
  end
 end
endmodule
`default_nettype wire
