// Candidate only. Work B-TRACE-PAYLOAD-RTL-20261024-38-v1.
// DEEPEYE-IMPLEMENTATION-20261014/v1; H01-H15, contract revision1,
// SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
// Main spec 0545a23843e92f1c7f4bdeec0e268a2cbfb2a246c77c0ee7641db0162a48bc48.
// One already selected block; no public TRACE enable or control authority.
module deepeye_trace_payload_candidate (
    input logic clk, rst, cancel,
    input logic cfg_valid, output logic cfg_ready,
    input logic [7:0] cfg_count, input logic [3:0] cfg_e,
    input logic [31:0] cfg_session, input logic [1:0] cfg_channel,
    input logic [31:0] cfg_first_index, input logic [63:0] cfg_first_tick,
    input logic [15:0] cfg_index_stride, cfg_tick_stride,
    input logic cfg_valid_sample, cfg_saturated, cfg_held, cfg_source_fault,
    input logic [63:0] cfg_source_tick,
    input logic s_valid, output logic s_ready,
    input logic [15:0] s_data, input logic s_last,
    output logic meta_valid, input logic meta_ready,
    output logic [1:0] meta_error, output logic [5:0] meta_bytes,
    output logic [31:0] meta_tick,
    output logic m_valid, input logic m_ready,
    output logic [7:0] m_data, output logic m_last
);
    localparam [3:0] IDLE=0, CHECK=1, CORE_CFG=2, LOAD=3, WAIT_META=4,
        DRAIN=5, RAW_COPY=6, PREFIX=7, META=8, OUT=9, CLEAR=10;
    logic [3:0] state;
    logic [7:0] count_q;
    logic [3:0] e_q;
    logic [31:0] session_q, index_q;
    logic [1:0] channel_q;
    logic [63:0] tick_q, source_q;
    logic [15:0] index_stride_q, tick_stride_q;
    logic valid_q, saturated_q, held_q, fault_q;
    logic [15:0] samples [0:127];
    logic [7:0] payload [0:31];
    logic [7:0] loaded;
    logic [8:0] drain_index, copy_index;
    logic [5:0] prefix_index, output_index, metadata_length, total_length;
    logic long_q, raw_q, error_pending;
    logic [15:0] short_age;
    logic [3:0] k_q;
    logic [11:0] bits_q, core_bits_q;
    logic [8:0] core_bytes_q, code_bytes_q;

    logic c_cfg_ready, c_s_ready, c_meta_valid, c_m_valid, c_m_last;
    logic [1:0] c_error;
    logic [7:0] c_count, c_data;
    logic [3:0] c_e, c_k;
    logic c_raw;
    logic [11:0] c_bits;
    logic [8:0] c_bytes;
    wire core_cancel = cancel || (state == CLEAR);
    deepeye_block_encoder inner_encoder (
        .clk(clk), .rst(rst), .cancel(core_cancel),
        .cfg_valid((state == CORE_CFG) && !rst && !cancel), .cfg_ready(c_cfg_ready),
        .cfg_count(count_q), .cfg_e(e_q),
        .s_valid((state == LOAD) && s_valid && !rst && !cancel), .s_ready(c_s_ready),
        .s_data(s_data), .s_last(s_last),
        .meta_valid(c_meta_valid), .meta_ready((state == WAIT_META) && !rst && !cancel),
        .meta_error(c_error), .meta_count(c_count), .meta_e(c_e),
        .meta_raw(c_raw), .meta_k(c_k), .meta_valid_bits(c_bits), .meta_bytes(c_bytes),
        .m_valid(c_m_valid), .m_ready((state == DRAIN) && !rst && !cancel),
        .m_data(c_data), .m_last(c_m_last)
    );
    assign cfg_ready = (state == IDLE) && c_cfg_ready && !rst && !cancel;
    assign s_ready = (state == LOAD) && c_s_ready && !rst && !cancel;
    assign meta_valid = (state == META) && !rst && !cancel;
    assign m_valid = (state == OUT) && !rst && !cancel;
    assign m_data = payload[output_index[4:0]];
    assign m_last = m_valid && (output_index == total_length-6'd1);

    logic [7:0] count_minus_one;
    logic [23:0] index_span, tick_span;
    logic [32:0] index_end;
    logic [64:0] tick_end, age;
    logic config_bad, choose_raw;
    logic [5:0] metadata_calc;
    logic [8:0] raw_bytes, selected_bytes;
    logic [11:0] raw_bits, selected_bits;
    logic [9:0] selected_total;
    logic [2:0] e_code;
    logic [7:0] prefix_byte;
    logic [8:0] pad_mask;
    logic [9:0] store_address;
    always @* begin
        count_minus_one = count_q-8'd1;
        // At most 127*65535 < 2^23; explicit extension before endpoint addition.
        index_span = {16'd0,count_minus_one} * {8'd0,index_stride_q};
        tick_span = {16'd0,count_minus_one} * {8'd0,tick_stride_q};
        index_end = {1'b0,index_q}+{9'd0,index_span};
        tick_end = {1'b0,tick_q}+{41'd0,tick_span};
        age = {1'b0,tick_q}-{1'b0,source_q};
        config_bad = (count_q == 0) || (count_q > 128) ||
            !((e_q==0)||(e_q==1)||(e_q==2)||(e_q==4)||(e_q==8));
        if (count_q == 1) begin
            if ((index_stride_q != 0)||(tick_stride_q != 0)) config_bad=1;
        end else begin
            if ((index_stride_q == 0)||(tick_stride_q == 0)||index_end[32]||tick_end[64]) config_bad=1;
        end
        if (!valid_q) begin
            if (saturated_q || held_q || (source_q != 0)) config_bad=1;
        end else if (held_q) begin
            if (source_q >= tick_q) config_bad=1;
        end else if (source_q != tick_q) config_bad=1;
        metadata_calc = 6'd21 + ((count_q>1) ? 6'd4 : 6'd0)
                        + (held_q ? ((age>65'd65535) ? 6'd8 : 6'd2) : 6'd0);
        raw_bytes = {count_q,1'b0};
        raw_bits = {count_q,4'b0};
        choose_raw = c_raw || (c_bytes >= raw_bytes);
        selected_bytes = choose_raw ? raw_bytes : c_bytes;
        selected_bits = choose_raw ? raw_bits : c_bits;
        selected_total = {4'd0,metadata_length}+{1'b0,selected_bytes};
        case (e_q)
            0:e_code=0; 1:e_code=1; 2:e_code=2; 4:e_code=3; default:e_code=4;
        endcase
        prefix_byte=8'd0;
        case (prefix_index)
            0:prefix_byte=8'd1;
            1:prefix_byte={k_q,raw_q,e_code};
            2:prefix_byte={1'b0,long_q,fault_q,held_q,saturated_q,valid_q,channel_q};
            3:prefix_byte=count_q;
            4:prefix_byte=bits_q[7:0];
            5,6,7,8:prefix_byte=session_q >> ((prefix_index-5)*8);
            9,10,11,12:prefix_byte=index_q >> ((prefix_index-9)*8);
            13,14,15,16,17,18,19,20:prefix_byte=tick_q >> ((prefix_index-13)*8);
            default: begin
                if ((count_q>1) && (prefix_index<25)) begin
                    case (prefix_index)
                        21:prefix_byte=index_stride_q[7:0];
                        22:prefix_byte=index_stride_q[15:8];
                        23:prefix_byte=tick_stride_q[7:0];
                        default:prefix_byte=tick_stride_q[15:8];
                    endcase
                end else if (long_q) begin
                    prefix_byte=source_q >> ((prefix_index-((count_q>1)?25:21))*8);
                end else begin
                    prefix_byte=short_age >> ((prefix_index-((count_q>1)?25:21))*8);
                end
            end
        endcase
        pad_mask = (core_bits_q[2:0]==0) ? 9'd0 :
                   ((9'd1 << (4'd8-{1'b0,core_bits_q[2:0]}))-9'd1);
        // Rice anchor is the sole endian change; the remainder is MSB-first.
        if (drain_index==0) store_address={4'd0,metadata_length}+10'd1;
        else if (drain_index==1) store_address={4'd0,metadata_length};
        else store_address={4'd0,metadata_length}+{1'b0,drain_index};
    end

    task automatic reject_block(input logic [1:0] error_code);
        begin
            meta_error<=error_code; meta_bytes<=0; meta_tick<=0;
            error_pending<=1; state<=CLEAR;
        end
    endtask
    always @(posedge clk) begin
        if (rst || cancel) begin
            state<=CLEAR; error_pending<=0;
            count_q<=0; e_q<=0; session_q<=0; channel_q<=0; index_q<=0;
            tick_q<=0; source_q<=0; index_stride_q<=0; tick_stride_q<=0;
            valid_q<=0; saturated_q<=0; held_q<=0; fault_q<=0;
            loaded<=0; drain_index<=0; copy_index<=0; prefix_index<=0; output_index<=0;
            metadata_length<=0; total_length<=0; long_q<=0; raw_q<=1; short_age<=0;
            k_q<=0; bits_q<=0; core_bits_q<=0; core_bytes_q<=0; code_bytes_q<=0;
            meta_error<=0; meta_bytes<=0; meta_tick<=0;
        end else begin
            case (state)
                CLEAR: begin
                    state<=error_pending ? META : IDLE;
                    error_pending<=0;
                end
                IDLE: if (cfg_valid && cfg_ready) begin
                    count_q<=cfg_count; e_q<=cfg_e; session_q<=cfg_session; channel_q<=cfg_channel;
                    index_q<=cfg_first_index; tick_q<=cfg_first_tick;
                    index_stride_q<=cfg_index_stride; tick_stride_q<=cfg_tick_stride;
                    valid_q<=cfg_valid_sample; saturated_q<=cfg_saturated;
                    held_q<=cfg_held; fault_q<=cfg_source_fault; source_q<=cfg_source_tick;
                    loaded<=0; prefix_index<=0; output_index<=0;
                    meta_error<=0; meta_bytes<=0; meta_tick<=0; state<=CHECK;
                end
                CHECK: begin
                    if (config_bad) reject_block(2'd1);
                    else begin
                        metadata_length<=metadata_calc;
                        long_q<=held_q && (age>65'd65535); short_age<=age[15:0];
                        if (!valid_q) begin
                            raw_q<=1; k_q<=0; bits_q<=0; code_bytes_q<=0;
                            total_length<=metadata_calc; state<=PREFIX;
                        end else state<=CORE_CFG;
                    end
                end
                CORE_CFG: if (c_cfg_ready) state<=LOAD;
                LOAD: begin
                    if (c_meta_valid) state<=WAIT_META;
                    else if (s_valid && s_ready) begin
                        samples[loaded[6:0]]<=s_data;
                        loaded<=loaded+8'd1;
                        if (s_last || (loaded==count_minus_one)) state<=WAIT_META;
                    end
                end
                WAIT_META: if (c_meta_valid) begin
                    if ((c_error!=0)||(loaded!=count_q)||(c_count!=count_q)||(c_e!=e_q)||
                        (c_bits<16)||(c_bits>raw_bits)||
                        (c_bytes!=((c_bits+12'd7)>>3))||(c_bytes<2)||(c_bytes>256)||
                        (c_raw && ((c_k!=0)||(c_bits!=raw_bits)))) reject_block(2'd2);
                    else if ((selected_total>32)||(selected_bits>255)) reject_block(2'd3);
                    else begin
                        raw_q<=choose_raw; k_q<=choose_raw ? 4'd0 : c_k;
                        bits_q<=selected_bits; code_bytes_q<=selected_bytes;
                        core_bits_q<=c_bits; core_bytes_q<=c_bytes;
                        total_length<=selected_total[5:0]; drain_index<=0; state<=DRAIN;
                    end
                end
                DRAIN: if (c_m_valid) begin
                    if ((c_m_last!=(drain_index==core_bytes_q-9'd1))||
                        ((drain_index==core_bytes_q-9'd1)&&((c_data & pad_mask[7:0])!=0)))
                        reject_block(2'd2);
                    else begin
                        if (!raw_q) payload[store_address[4:0]]<=c_data;
                        if (drain_index==core_bytes_q-9'd1) begin
                            copy_index<=0; state<=raw_q ? RAW_COPY : PREFIX;
                        end else drain_index<=drain_index+9'd1;
                    end
                end
                RAW_COPY: begin
                    if (copy_index[0]) payload[metadata_length+copy_index]<=samples[copy_index[7:1]][15:8];
                    else payload[metadata_length+copy_index]<=samples[copy_index[7:1]][7:0];
                    if (copy_index==code_bytes_q-9'd1) state<=PREFIX;
                    else copy_index<=copy_index+9'd1;
                end
                PREFIX: begin
                    payload[prefix_index[4:0]]<=prefix_byte;
                    if (prefix_index==metadata_length-6'd1) begin
                        meta_error<=0; meta_bytes<=total_length; meta_tick<=tick_q[31:0]; state<=META;
                    end else prefix_index<=prefix_index+6'd1;
                end
                META: if (meta_ready) begin
                    output_index<=0; state<=(meta_error!=0) ? IDLE : OUT;
                end
                OUT: if (m_ready) begin
                    if (output_index==total_length-6'd1) state<=IDLE;
                    else output_index<=output_index+6'd1;
                end
                default: begin error_pending<=0; state<=CLEAR; end
            endcase
        end
    end
endmodule
