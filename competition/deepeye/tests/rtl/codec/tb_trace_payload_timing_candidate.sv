`timescale 1ns/1ps
// Public-port fixture test only; no hierarchical acceptance assertions.
module tb_trace_payload_timing_candidate;
    reg clk=0; always #5 clk=~clk;
    reg rst=1,cancel=0,cfg_valid=0,s_valid=0,s_last=0,meta_ready=0,m_ready=0;
    reg [7:0] cfg_count=0;
    reg [3:0] cfg_e=0;
    reg [31:0] cfg_session=0,cfg_first_index=0;
    reg [1:0] cfg_channel=0;
    reg [63:0] cfg_first_tick=0,cfg_source_tick=0;
    reg [15:0] cfg_index_stride=0,cfg_tick_stride=0,s_data=0;
    reg cfg_valid_sample=0,cfg_saturated=0,cfg_held=0,cfg_source_fault=0;
    wire cfg_ready,s_ready,meta_valid,m_valid,m_last;
    wire [1:0] meta_error;
    wire [5:0] meta_bytes;
    wire [31:0] meta_tick;
    wire [7:0] m_data;
    deepeye_trace_payload_timing_candidate dut (
        .clk(clk),.rst(rst),.cancel(cancel),.cfg_valid(cfg_valid),.cfg_ready(cfg_ready),
        .cfg_count(cfg_count),.cfg_e(cfg_e),.cfg_session(cfg_session),.cfg_channel(cfg_channel),
        .cfg_first_index(cfg_first_index),.cfg_first_tick(cfg_first_tick),
        .cfg_index_stride(cfg_index_stride),.cfg_tick_stride(cfg_tick_stride),
        .cfg_valid_sample(cfg_valid_sample),.cfg_saturated(cfg_saturated),.cfg_held(cfg_held),
        .cfg_source_fault(cfg_source_fault),.cfg_source_tick(cfg_source_tick),
        .s_valid(s_valid),.s_ready(s_ready),.s_data(s_data),.s_last(s_last),
        .meta_valid(meta_valid),.meta_ready(meta_ready),.meta_error(meta_error),
        .meta_bytes(meta_bytes),.meta_tick(meta_tick),.m_valid(m_valid),.m_ready(m_ready),
        .m_data(m_data),.m_last(m_last)
    );
    integer accepted_cfg_cycle=-1000;
    integer cycle=0,trace_fd,input_fd,rc,total,case_id=0,kind,which,delay_count,send_count;
    integer ex_error,ex_bytes;
    reg [31:0] ex_tick;
    reg [3:0] flags;
    reg [15:0] words[0:127];
    reg lasts[0:127];
    reg [7:0] expected[0:31];
    integer lc_cfg=0,lc_sample=0,lc_meta=0,lc_data=0;
    integer gc_cfg=0,gc_sample=0,gc_meta=0,gc_data=0;
    integer st_cfg=0,st_sample=0,st_meta=0,st_data=0,resets=0,cancels=0;
    integer complete_count=0,error_count=0,abort_count=0,recovery_count=0;
    reg enabled=0,expected_on=0,cfg_accepted,sample_accepted;
    reg previous_meta_stall=0,previous_data_stall=0;
    reg [39:0] previous_metadata;
    reg [8:0] previous_data;
    string input_path,trace_path;
    task automatic fail(input string why);
        $display("TP_FAIL cycle=%0d id=%0d %s",cycle,case_id,why);
        $fatal(1,"TP_FAIL");
    endtask
    always @(posedge clk) begin
        cycle=cycle+1;
        cfg_accepted=cfg_valid&&cfg_ready;
        sample_accepted=s_valid&&s_ready;
        if(enabled) begin
            if ((^{cfg_ready,s_ready,meta_valid,m_valid,m_last})===1'bx) fail("unknown handshake");
            if ((rst||cancel)&&{cfg_ready,s_ready,meta_valid,m_valid,m_last}!==5'd0) fail("abort gating");
            if (!m_valid&&m_last) fail("last outside valid");
            if (!expected_on&&(meta_valid||m_valid)) fail("phantom output");
            if(!rst&&!cancel)begin
                if(previous_meta_stall&&(!meta_valid||{meta_error,meta_bytes,meta_tick}!==previous_metadata))fail("metadata stall stability");
                if(previous_data_stall&&(!m_valid||{m_data,m_last}!==previous_data))fail("data stall stability");
            end
            previous_meta_stall=meta_valid&&!meta_ready&&!rst&&!cancel;
            previous_data_stall=m_valid&&!m_ready&&!rst&&!cancel;
            if(previous_meta_stall)previous_metadata={meta_error,meta_bytes,meta_tick};
            if(previous_data_stall)previous_data={m_data,m_last};
            $fdisplay(trace_fd,"%0d %0d %b%b %b%b %02h %01h %08h %01h %08h %016h %04h %04h %01h %016h %b%b %04h %b %b%b %01h %02h %08h %b%b %02h %b",
                cycle,case_id,rst,cancel,cfg_valid,cfg_ready,cfg_count,cfg_e,cfg_session,cfg_channel,
                cfg_first_index,cfg_first_tick,cfg_index_stride,cfg_tick_stride,
                {cfg_valid_sample,cfg_saturated,cfg_held,cfg_source_fault},cfg_source_tick,
                s_valid,s_ready,s_data,s_last,meta_valid,meta_ready,
                meta_valid?meta_error:2'd0,meta_valid?meta_bytes:6'd0,meta_valid?meta_tick:32'd0,
                m_valid,m_ready,m_valid?m_data:8'd0,m_last);
            if(rst||cancel)accepted_cfg_cycle=-1000;
            if(cfg_accepted)accepted_cfg_cycle=cycle;
            if(!rst&&!cancel&&cycle>accepted_cfg_cycle&&cycle<=accepted_cfg_cycle+3)
                if({cfg_ready,s_ready,meta_valid,m_valid}!==4'd0)fail("preflight public gating");
            if(cfg_accepted) begin lc_cfg=lc_cfg+1;gc_cfg=gc_cfg+1;end
            if(sample_accepted) begin
                if(lc_sample>=send_count||s_data!==words[lc_sample]||s_last!==lasts[lc_sample]) fail("sample accept");
                lc_sample=lc_sample+1;gc_sample=gc_sample+1;
            end
            if(meta_valid) begin
                if(lc_cfg!=1||lc_sample!=send_count)fail("metadata before input completion");
                if((^{meta_error,meta_bytes,meta_tick})===1'bx) fail("unknown metadata");
                if(meta_error!==ex_error[1:0]||meta_bytes!==ex_bytes[5:0]||meta_tick!==ex_tick) fail("golden metadata");
                if(meta_ready) begin lc_meta=lc_meta+1;gc_meta=gc_meta+1;end
            end
            if(m_valid) begin
                if(lc_meta!=1||ex_error!=0||lc_data>=ex_bytes) fail("unexpected data");
                if(m_data!==expected[lc_data]||m_last!==(lc_data==ex_bytes-1)) fail("golden byte/last");
                if(m_ready) begin lc_data=lc_data+1;gc_data=gc_data+1;end
            end
            if(cfg_valid&&!cfg_ready) st_cfg=st_cfg+1;
            if(s_valid&&!s_ready) st_sample=st_sample+1;
            if(meta_valid&&!meta_ready) st_meta=st_meta+1;
            if(m_valid&&!m_ready) st_data=st_data+1;
            if(rst) resets=resets+1;
            if(cancel) cancels=cancels+1;
        end
    end
    task automatic step;
        @(posedge clk);#1;
    endtask
    task automatic idle_clocks(input integer amount);
        repeat(amount) begin
            @(negedge clk);if(!s_valid)s_data=s_data^16'ha53c;
            step();
        end
    endtask
    task automatic send_cfg;
        integer timeout_cfg;
        @(negedge clk);cfg_valid=1;timeout_cfg=0;
        begin:cfg_wait
            forever begin
                step();if(cfg_accepted)disable cfg_wait;
                timeout_cfg=timeout_cfg+1;if(timeout_cfg>20)fail("config timeout");
            end
        end
        @(negedge clk);cfg_valid=0;
        // Changes to unaccepted live configuration must not affect this block.
        cfg_session=~cfg_session;cfg_first_tick=~cfg_first_tick;
        cfg_e=15;cfg_count=255;cfg_index_stride=0;cfg_tick_stride=0;
        cfg_channel=~cfg_channel;cfg_first_index=~cfg_first_index;cfg_source_tick=~cfg_source_tick;
        {cfg_valid_sample,cfg_saturated,cfg_held,cfg_source_fault}=~{cfg_valid_sample,cfg_saturated,cfg_held,cfg_source_fault};
    endtask
    task automatic send_word(input integer index);
        integer timeout_sample;
        s_valid=0;idle_clocks((index+case_id)%3);
        @(negedge clk);s_valid=1;s_data=words[index];s_last=lasts[index];timeout_sample=0;
        begin:sample_wait
            forever begin
                step();if(sample_accepted)disable sample_wait;
                timeout_sample=timeout_sample+1;if(timeout_sample>50)fail("sample timeout");
            end
        end
        @(negedge clk);s_valid=0;s_last=0;s_data=~words[index];
    endtask
    task automatic wait_meta;
        integer timeout_meta;
        timeout_meta=0;
        while(!meta_valid) begin
            idle_clocks(1);timeout_meta=timeout_meta+1;
            if(timeout_meta>15000)fail("metadata timeout");
        end
    endtask
    task automatic take_meta;
        wait_meta();
        @(negedge clk);cfg_valid=1;
        idle_clocks(3+case_id%3);
        @(negedge clk);cfg_valid=0;meta_ready=1;
        step();@(negedge clk);meta_ready=0;s_valid=0;s_last=0;
    endtask
    task automatic abort_now;
        integer timeout_idle;
        if(kind!=8)@(negedge clk);expected_on=0;
        rst=(which==0);cancel=(which==1);
        cfg_valid=1;s_valid=1;s_last=1;meta_ready=1;m_ready=1;
        step();
        @(negedge clk);rst=0;cancel=0;cfg_valid=0;s_valid=0;s_last=0;meta_ready=0;m_ready=0;
        timeout_idle=0;
        while(!cfg_ready)begin step();timeout_idle=timeout_idle+1;if(timeout_idle>10)fail("abort idle timeout");end
        idle_clocks(3);
    endtask
    integer i,j,timeout_data;
    initial begin
        if(!$value$plusargs("INPUT=%s",input_path)||!$value$plusargs("TRACE=%s",trace_path))$fatal(1,"paths");
        input_fd=$fopen(input_path,"r");trace_fd=$fopen(trace_path,"w");
        if(!input_fd||!trace_fd)$fatal(1,"file open");
        rc=$fscanf(input_fd,"%d",total);if(rc!=1||total<1)$fatal(1,"case count");
        repeat(3)step();@(negedge clk);rst=0;enabled=1;
        for(i=0;i<total;i=i+1)begin
            rc=$fscanf(input_fd,"%d %d %d %d %d %d %d %h %h %h %h %h %h %h %h %d %d %h",
                case_id,kind,which,delay_count,send_count,cfg_count,cfg_e,cfg_session,cfg_channel,
                cfg_first_index,cfg_first_tick,cfg_index_stride,cfg_tick_stride,flags,cfg_source_tick,
                ex_error,ex_bytes,ex_tick);
            if(rc!=18||send_count>128||ex_bytes>32)fail("fixture header");
            {cfg_valid_sample,cfg_saturated,cfg_held,cfg_source_fault}=flags;
            for(j=0;j<send_count;j=j+1)begin
                rc=$fscanf(input_fd,"%h %b",words[j],lasts[j]);if(rc!=2)fail("fixture sample");
            end
            for(j=0;j<ex_bytes;j=j+1)begin rc=$fscanf(input_fd,"%h",expected[j]);if(rc!=1)fail("fixture bytes");end
            lc_cfg=0;lc_sample=0;lc_meta=0;lc_data=0;
            expected_on=1;cfg_valid=0;s_valid=0;s_last=0;meta_ready=0;m_ready=0;
            if(kind!=7)send_cfg();
            for(j=0;j<send_count;j=j+1)send_word(j);
            if(kind==0||kind==6)begin
                // Quality-only/invalid-config transactions must accept no sample.
                if(send_count==0)begin s_valid=1;s_data=16'hcafe;s_last=1;end
                take_meta();timeout_data=0;
                while(lc_data<ex_bytes)begin
                    @(negedge clk);m_ready=(timeout_data%7>=3);s_data=s_data^16'h96e1;
                    step();timeout_data=timeout_data+1;if(timeout_data>5000)fail("data timeout");
                end
                @(negedge clk);m_ready=0;
                if(lc_cfg!=1||lc_sample!=send_count||lc_meta!=1||lc_data!=ex_bytes)fail("transaction counts");
                expected_on=0;idle_clocks(3);
                complete_count=complete_count+1;if(ex_error!=0)error_count=error_count+1;
                if(kind==6)recovery_count=recovery_count+1;
            end else begin
                if(kind==4||kind==5)begin
                    take_meta();
                    timeout_data=0;
                    while(!m_valid)begin idle_clocks(1);timeout_data=timeout_data+1;if(timeout_data>5000)fail("abort data timeout");end
                    if(kind==5)begin @(negedge clk);m_ready=1;step();@(negedge clk);m_ready=0;end
                end else idle_clocks(delay_count);
                abort_now();abort_count=abort_count+1;
            end
            $display("TP_CASE id=%0d kind=%0d error=%0d bytes=%0d tick=%08h cfg=%0d samples=%0d meta=%0d data=%0d PASS",
                case_id,kind,ex_error,ex_bytes,ex_tick,lc_cfg,lc_sample,lc_meta,lc_data);
        end
        $fclose(input_fd);@(negedge clk);
        if(st_cfg==0||st_sample==0||st_meta==0||st_data==0||resets==0||cancels==0)fail("coverage counters");
        $display("TP_SUMMARY cases=%0d complete=%0d errors=%0d aborts=%0d recovery=%0d cycles=%0d cfg=%0d samples=%0d meta=%0d data=%0d cfgstall=%0d samplestall=%0d metastall=%0d datastall=%0d reset=%0d cancel=%0d",
            total,complete_count,error_count,abort_count,recovery_count,cycle,gc_cfg,gc_sample,gc_meta,gc_data,
            st_cfg,st_sample,st_meta,st_data,resets,cancels);
        $fclose(trace_fd);$display("TP_DONE trace_payload_timing_candidate PASS");$finish;
    end
    initial begin #2000000000;$fatal(1,"TP_FAIL global timeout");end
endmodule
