`timescale 1ns/1ns
// File-driven public-port history only; no internal probes, force, or oracle.
module tb_trace_frame_candidate;
    logic clk=0;
    always #5 clk=~clk;
    logic rst=1, cancel=0, cfg_valid=0, s_valid=0, s_last=0;
    logic out_ready=0, result_ready=0;
    logic [15:0] s_data=0;
    logic [265:0] cfg_word=0, original_cfg;
    wire cfg_ready, s_ready, out_valid, out_last, result_valid, busy;
    wire [7:0] out_data;
    wire [5:0] out_count, result_bytes;
    wire [2:0] result_error;
    wire wire_faulted, wire_fault_event;
    wire [1:0] wire_fault_code;
    wire [7:0] cfg_count, cfg_epoch;
    wire [3:0] cfg_e;
    wire [31:0] cfg_session, cfg_first_index;
    wire [1:0] cfg_channel;
    wire [63:0] cfg_first_tick, cfg_source_tick;
    wire [15:0] cfg_index_stride, cfg_tick_stride, cfg_seq;
    wire cfg_valid_sample, cfg_saturated, cfg_held, cfg_source_fault;
    assign {cfg_count,cfg_e,cfg_session,cfg_channel,cfg_first_index,cfg_first_tick,
        cfg_index_stride,cfg_tick_stride,cfg_valid_sample,cfg_saturated,cfg_held,
        cfg_source_fault,cfg_source_tick,cfg_epoch,cfg_seq}=cfg_word;
    deepeye_trace_frame_candidate dut (
        .clk(clk),.rst(rst),.cancel(cancel),.cfg_valid(cfg_valid),.cfg_ready(cfg_ready),
        .cfg_count(cfg_count),.cfg_e(cfg_e),.cfg_session(cfg_session),.cfg_channel(cfg_channel),
        .cfg_first_index(cfg_first_index),.cfg_first_tick(cfg_first_tick),
        .cfg_index_stride(cfg_index_stride),.cfg_tick_stride(cfg_tick_stride),
        .cfg_valid_sample(cfg_valid_sample),.cfg_saturated(cfg_saturated),.cfg_held(cfg_held),
        .cfg_source_fault(cfg_source_fault),.cfg_source_tick(cfg_source_tick),
        .cfg_epoch(cfg_epoch),.cfg_seq(cfg_seq),.s_valid(s_valid),.s_ready(s_ready),
        .s_data(s_data),.s_last(s_last),.out_valid(out_valid),.out_ready(out_ready),
        .out_data(out_data),.out_last(out_last),.out_count(out_count),
        .result_valid(result_valid),.result_ready(result_ready),
        .result_error(result_error),.result_bytes(result_bytes),.busy(busy),
        .wire_faulted(wire_faulted),.wire_fault_event(wire_fault_event),.wire_fault_code(wire_fault_code)
    );
    wire [288:0] inputs={rst,cancel,cfg_valid,cfg_word,s_valid,s_data,s_last,out_ready,result_ready};
    wire [32:0] outputs={cfg_ready,s_ready,out_valid,out_data,out_last,out_count,
        result_valid,result_error,result_bytes,busy,wire_faulted,wire_fault_event,wire_fault_code};
    integer cycle=0, local_cycle=0, case_id=0, gap=0;
    integer cfg_hs=0, sample_hs=0, byte_hs=0, result_hs=0, controls=0;
    bit cfg_fire, sample_fire, byte_fire, result_fire, pre_out_valid, pre_result_valid;
    task automatic step;
        #1;
        $display("F45_TRACE cycle=%0d case=%0d local=%0d gap=%0d phase=pre time=%0d inputs=%073h outputs=%09h",
            cycle,case_id,local_cycle,gap,$time,inputs,outputs);
        cfg_fire=cfg_valid&&cfg_ready;
        sample_fire=s_valid&&s_ready;
        byte_fire=out_valid&&out_ready;
        result_fire=result_valid&&result_ready;
        pre_out_valid=out_valid; pre_result_valid=result_valid;
        cfg_hs=cfg_hs+cfg_fire; sample_hs=sample_hs+sample_fire;
        byte_hs=byte_hs+byte_fire; result_hs=result_hs+result_fire;
        controls=controls+(rst||cancel);
        @(posedge clk); #1;
        $display("F45_TRACE cycle=%0d case=%0d local=%0d gap=%0d phase=post time=%0d inputs=%073h outputs=%09h",
            cycle,case_id,local_cycle,gap,$time,inputs,outputs);
        cycle=cycle+1;
    endtask
    integer fd, cases, ordinal, n, sample_count, last_mode, abort_at, abort_kind;
    integer accepted_cycle, sample_index, byte_hold, report_hold, j, scanned;
    bit accepted, complete, aborted, pulse;
    logic [15:0] samples[0:127];
    string input_path;
    initial begin
        if (!$value$plusargs("INPUT=%s",input_path) || !$value$plusargs("CASES=%d",cases) || cases<=0)
            $fatal(1,"F45_BAD_ARGUMENTS");
        fd=$fopen(input_path,"r");
        if (fd==0) $fatal(1,"F45_BAD_INPUT");
        @(posedge clk); #1;
        $display("F45_BEGIN cases=%0d",cases);
        for (ordinal=0;ordinal<cases;ordinal=ordinal+1) begin
            scanned=$fscanf(fd,"%d %h %d %d %d %d\n",case_id,original_cfg,sample_count,last_mode,abort_at,abort_kind);
            if (scanned!=6 || case_id!=ordinal || sample_count<0 || sample_count>128)
                $fatal(1,"F45_BAD_CASE");
            for(n=0;n<sample_count;n=n+1) begin
                scanned=$fscanf(fd,"%h\n",samples[n]);
                if(scanned!=1) $fatal(1,"F45_SHORT_SAMPLES");
            end
            $display("F45_CASE_BEGIN id=%0d",case_id);
            accepted=0; complete=0; aborted=0; accepted_cycle=-1;
            sample_index=0; byte_hold=0; report_hold=0; gap=0;
            for(local_cycle=0;local_cycle<20000;local_cycle=local_cycle+1) begin
                @(negedge clk);
                pulse=(abort_kind!=0)&&((abort_at==-2 && local_cycle==0)||
                    (accepted && (local_cycle-accepted_cycle==abort_at)));
                rst=pulse&&(abort_kind==1); cancel=pulse&&(abort_kind==2);
                cfg_valid=!accepted || busy;
                cfg_word=accepted ? (~original_cfg ^ (266'd3405691582+local_cycle)) : original_cfg;
                s_valid=(sample_index<sample_count)&&(local_cycle%3!=0);
                s_data=(sample_index<sample_count) ? samples[sample_index] : 16'hdead;
                s_last=(last_mode==1) ? (sample_index==0) :
                    ((last_mode==2) ? 1'b0 : (sample_index==sample_count-1));
                out_ready=(byte_hold>=2); result_ready=(report_hold>=3);
                step();
                if(cfg_fire) begin accepted=1; accepted_cycle=local_cycle; end
                if(sample_fire) sample_index=sample_index+1;
                if(pre_out_valid) byte_hold=byte_fire ? 0 : byte_hold+1;
                else byte_hold=0;
                if(pre_result_valid) report_hold=result_fire ? 0 : report_hold+1;
                else report_hold=0;
                if(pulse) begin aborted=1; break; end
                if(result_fire) begin complete=1; break; end
            end
            if(!aborted&&!complete) $fatal(1,"F45_CASE_TIMEOUT id=%0d",case_id);
            gap=1;
            for(j=0;j<5;j=j+1) begin
                local_cycle=local_cycle+1;
                @(negedge clk);
                rst=0; cancel=0; cfg_valid=0; s_valid=0; s_last=0; s_data=0;
                out_ready=1; result_ready=1;
                step();
            end
            if(aborted) $display("F45_CASE_END id=%0d reason=control",case_id);
            else $display("F45_CASE_END id=%0d reason=result",case_id);
        end
        scanned=$fscanf(fd,"%d",n);
        if(scanned!=-1) $fatal(1,"F45_EXTRA_INPUT");
        $fclose(fd);
        $display("F45_DONE cases=%0d cycles=%0d records=%0d cfg=%0d samples=%0d bytes=%0d results=%0d controls=%0d",
            cases,cycle,2*cycle,cfg_hs,sample_hs,byte_hs,result_hs,controls);
        $display("F45_FINAL result=PASS");
        $finish;
    end
endmodule
