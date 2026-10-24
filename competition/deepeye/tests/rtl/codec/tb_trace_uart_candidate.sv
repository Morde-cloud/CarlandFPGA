`timescale 1ns/1ps
// Public ports only. UART bit deadlines use ceil(k*CLOCK_HZ/BAUD).
module tb_trace_uart_candidate #(
    parameter integer CLOCK_HZ=5,BAUD=2
);
    reg clk=0;always #5 clk=~clk;
    reg rst=1,cancel=0,cfg_valid=0,s_valid=0,s_last=0,result_ready=1;
    reg [265:0] cfg_bus=0;
    wire [7:0] cfg_count=cfg_bus[265:258];
    wire [3:0] cfg_e=cfg_bus[257:254];
    wire [31:0] cfg_session=cfg_bus[253:222];
    wire [1:0] cfg_channel=cfg_bus[221:220];
    wire [31:0] cfg_first_index=cfg_bus[219:188];
    wire [63:0] cfg_first_tick=cfg_bus[187:124];
    wire [15:0] cfg_index_stride=cfg_bus[123:108],cfg_tick_stride=cfg_bus[107:92];
    wire cfg_valid_sample=cfg_bus[91],cfg_saturated=cfg_bus[90],cfg_held=cfg_bus[89],cfg_source_fault=cfg_bus[88];
    wire [63:0] cfg_source_tick=cfg_bus[87:24];
    wire [7:0] cfg_epoch=cfg_bus[23:16];
    wire [15:0] cfg_seq=cfg_bus[15:0];
    reg [15:0] s_data=0;
    wire cfg_ready,s_ready,tx,uart_busy,result_valid,busy,wire_faulted,wire_fault_event;
    wire [2:0] result_error;
    wire [5:0] result_bytes;
    wire [1:0] wire_fault_code;
    wire [24:0] ports={result_bytes,result_error,wire_fault_code,wire_fault_event,wire_faulted,
        s_last,s_valid,cfg_valid,cancel,rst,result_ready,result_valid,s_ready,cfg_ready,busy,uart_busy,tx};
    deepeye_trace_uart_candidate #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) dut (
        .clk(clk),.rst(rst),.cancel(cancel),.cfg_valid(cfg_valid),.cfg_ready(cfg_ready),
        .cfg_count(cfg_count),.cfg_e(cfg_e),.cfg_session(cfg_session),.cfg_channel(cfg_channel),
        .cfg_first_index(cfg_first_index),.cfg_first_tick(cfg_first_tick),
        .cfg_index_stride(cfg_index_stride),.cfg_tick_stride(cfg_tick_stride),
        .cfg_valid_sample(cfg_valid_sample),.cfg_saturated(cfg_saturated),.cfg_held(cfg_held),
        .cfg_source_fault(cfg_source_fault),.cfg_source_tick(cfg_source_tick),.cfg_epoch(cfg_epoch),.cfg_seq(cfg_seq),
        .s_valid(s_valid),.s_ready(s_ready),.s_data(s_data),.s_last(s_last),
        .tx(tx),.uart_busy(uart_busy),.result_valid(result_valid),.result_ready(result_ready),
        .result_error(result_error),.result_bytes(result_bytes),.busy(busy),
        .wire_faulted(wire_faulted),.wire_fault_event(wire_fault_event),.wire_fault_code(wire_fault_code)
    );
    reg [265:0] configs[0:63];
    reg [15:0] sample_table[0:8191];
    reg [7:0] frames[0:2943];
    integer nsamples[0:63],errors[0:63],lengths[0:63],last_modes[0:63];
    integer vectors,plans,pvector[0:511],paction[0:511],pkind[0:511],pwhich[0:511],pphase[0:511],phold[0:511];
    integer fd,tf,rc,i,j,case_id=0,vector_id=0,action=0,kind=0,which_byte=0,target_phase=0;
    integer cycle=0,expect_error=0,expect_length=0;
    integer total_cfg=0,total_samples=0,total_starts=0,total_bytes=0,total_results=0,total_aborts=0;
    integer local_cfg=0,local_samples=0,local_starts=0,local_bytes=0,local_results=0;
    integer admitted_cycle=0,age,phase,byte_number,local_abort=0;
    integer cfg_hs,sample_hs,result_hs,pre_uart,prev_tx=1;
    reg [24:0] pre_ports;
    reg [8:0] held_report;
    reg [7:0] decoded=0;
    reg expected_tx;
    string fixture_path,trace_path;
    task automatic fail(input string why);
        $display("TU49_FAIL case=%0d cycle=%0d %s",case_id,cycle,why);$fatal(1,"TU49_FAIL");
    endtask
    task automatic check_report;
        begin
            if(result_valid)begin
                if(uart_busy||cfg_ready)fail("result/config visible before UART idle or report retirement");
                if(result_error!==expect_error||result_bytes!==(expect_error==0?expect_length:0))fail("result tuple");
                if(expect_error==0&&(local_bytes!=expect_length||uart_busy))fail("early success before last physical stop");
                if(expect_error!=0&&(local_starts!=0||local_bytes!=0))fail("error emitted UART bytes");
            end
            if(uart_busy&&(!busy||cfg_ready||result_valid))fail("UART busy gating");
            if(wire_faulted||wire_fault_event||wire_fault_code!=0)fail("unexpected structurally unreachable wire fault");
        end
    endtask
    task automatic tick;
        begin
            @(posedge clk);cycle=cycle+1;
            pre_ports=ports;pre_uart=uart_busy;
            cfg_hs=cfg_valid&&cfg_ready;sample_hs=s_valid&&s_ready;result_hs=result_valid&&result_ready;
            if((rst||cancel)&&(cfg_ready||s_ready||result_valid))fail("immediate handshake mask");
            if(cycle>1&&tx!==prev_tx)fail("TX changed between active edges/combinational reset mux");
            if(cycle>1)check_report();
            if(result_valid&&!result_ready)held_report={result_error,result_bytes};
            total_cfg=total_cfg+cfg_hs;local_cfg=local_cfg+cfg_hs;
            total_samples=total_samples+sample_hs;local_samples=local_samples+sample_hs;
            total_results=total_results+result_hs;local_results=local_results+result_hs;
            #1;
            if((^{tx,uart_busy,result_valid,cfg_ready,s_ready,busy})===1'bx)fail("unknown public endpoint");
            if(rst||cancel)begin
                if(tx!==1'b1||uart_busy||cfg_ready||s_ready||result_valid)fail("synchronous abort idle/masks");
            end else if(!pre_uart&&uart_busy)begin
                if(expect_error!=0||local_starts>=expect_length)fail("extra UART byte admission");
                admitted_cycle=cycle;byte_number=local_starts;local_starts=local_starts+1;total_starts=total_starts+1;
                decoded=0;if(tx!==1'b0)fail("start bit");
            end else if(pre_uart)begin
                age=cycle-admitted_cycle;
                if(age>=((10*CLOCK_HZ+BAUD-1)/BAUD))begin
                    if(age!=((10*CLOCK_HZ+BAUD-1)/BAUD)||uart_busy||tx!==1'b1)fail("stop completion boundary");
                    if(decoded!==frames[46*vector_id+byte_number])fail("actual UART decoded byte");
                    local_bytes=local_bytes+1;total_bytes=total_bytes+1;
                end else begin
                    if(!uart_busy)fail("UART busy ended before full stop");
                    phase=(age*BAUD)/CLOCK_HZ;
                    expected_tx=(phase==0)?1'b0:(phase==9)?1'b1:frames[46*vector_id+byte_number][phase-1];
                    if(tx!==expected_tx)fail("UART analytical bit deadline/value");
                    if(phase>=1&&phase<=8&&age==((phase*CLOCK_HZ+BAUD-1)/BAUD))decoded[phase-1]=tx;
                end
            end else if(tx!==1'b1)fail("idle TX low");
            check_report();
            if(pre_ports[5]&&!pre_ports[6]&&!rst&&!cancel&&
                (!result_valid||{result_error,result_bytes}!==held_report))fail("stalled report unstable");
            prev_tx=tx;
            // One record per active edge, cycle = one-based record number.
            $fdisplay(tf,"%0d %07h %07h",case_id,pre_ports,ports);
            @(negedge clk);
        end
    endtask
    task automatic abort_once;
        begin
            if(kind==1)rst=1;else cancel=1;
            s_valid=1;cfg_valid=1;result_ready=1;
            tick();total_aborts=total_aborts+1;local_abort=1;
            rst=0;cancel=0;cfg_valid=0;s_valid=0;s_last=0;
            #1;if(cfg_ready)fail("missing42 CLEAR recovery barrier");
            repeat(12)begin tick();if(result_valid)fail("stale result after abort");end
        end
    endtask
    integer sample_index,hold_count,begin_cycle,attempt,kill_now,finished,after_samples;
    initial begin
        if(CLOCK_HZ<2||BAUD<1||BAUD>CLOCK_HZ/2)begin
            #100;$fatal(1,"TU49 missing actual DUT parameter guard");
        end else begin
            if(!$value$plusargs("INPUT=%s",fixture_path)||!$value$plusargs("TRACE=%s",trace_path))$fatal(1,"arguments");
            fd=$fopen(fixture_path,"r");tf=$fopen(trace_path,"w");if(!fd||!tf)$fatal(1,"files");
            rc=$fscanf(fd,"%d %d",vectors,plans);if(rc!=2||vectors>64||plans>512)fail("fixture bounds");
            for(i=0;i<vectors;i=i+1)begin
                rc=$fscanf(fd,"%h %d %d %d %d",configs[i],nsamples[i],errors[i],lengths[i],last_modes[i]);
                if(rc!=5||nsamples[i]>128||lengths[i]>46)fail("vector");
                for(j=0;j<nsamples[i];j=j+1)begin rc=$fscanf(fd,"%h",sample_table[128*i+j]);if(rc!=1)fail("samples");end
                for(j=0;j<lengths[i];j=j+1)begin rc=$fscanf(fd,"%h",frames[46*i+j]);if(rc!=1)fail("frame");end
            end
            for(i=0;i<plans;i=i+1)begin
                rc=$fscanf(fd,"%d %d %d %d %d %d",pvector[i],paction[i],pkind[i],pwhich[i],pphase[i],phold[i]);
                if(rc!=6)fail("plan");
            end
            $fclose(fd);
            $display("TU49_BEGIN clock=%0d baud=%0d vectors=%0d plans=%0d",CLOCK_HZ,BAUD,vectors,plans);
            repeat(2)tick();rst=0;repeat(3)tick();
            for(i=0;i<plans;i=i+1)begin
                case_id=i+1;vector_id=pvector[i];action=paction[i];kind=pkind[i];which_byte=pwhich[i];target_phase=pphase[i];
                expect_error=errors[vector_id];expect_length=lengths[vector_id];
                local_cfg=0;local_samples=0;local_starts=0;local_bytes=0;local_results=0;local_abort=0;
                begin_cycle=cycle+1;cfg_bus=configs[vector_id];cfg_valid=1;s_valid=0;s_last=0;result_ready=(action!=1&&action!=6);
                if(action==3)begin
                    while(!cfg_ready)tick();
                    abort_once();
                end else begin
                    do tick();while(!cfg_hs);
                    sample_index=0;hold_count=0;attempt=0;finished=0;after_samples=0;
                    while(!finished)begin
                        cfg_valid=1;cfg_bus=~configs[vector_id]^cycle;
                        s_valid=(sample_index<nsamples[vector_id])&&((cycle%3)!=0);
                        s_data=sample_table[128*vector_id+sample_index];
                        s_last=(last_modes[vector_id]==1)?(sample_index==0):
                               (last_modes[vector_id]==2)?0:(sample_index==nsamples[vector_id]-1);
                        if(sample_index>=nsamples[vector_id])after_samples=after_samples+1;
                        if(result_valid)hold_count=hold_count+1;
                        result_ready=(action==6)?0:(action==1)?(hold_count>=phold[i]):1;
                        kill_now=0;
                        if(action==2&&uart_busy&&(local_starts-1==(which_byte==0?0:expect_length-1))&&
                           (((cycle-admitted_cycle)*BAUD)/CLOCK_HZ)==target_phase)kill_now=1;
                        if(action==4&&sample_index>=1)kill_now=1;
                        if(action==5&&after_samples>=2)kill_now=1;
                        if(action==6&&hold_count>=3)kill_now=1;
                        if(kill_now)begin abort_once();finished=1;end
                        else begin
                            tick();if(sample_hs)sample_index=sample_index+1;
                            if(result_hs)finished=1;
                        end
                        attempt=attempt+1;if(attempt>6000000)fail("bounded case timeout");
                    end
                end
                cfg_valid=0;s_valid=0;s_last=0;result_ready=1;
                repeat(2)tick();
                if(local_abort)begin if(local_results!=0)fail("result consumed after cancelled operation");end
                else if(local_results!=1||local_cfg!=1||local_bytes!=expect_length)fail("normal terminal totals");
                $display("TU49_TRACE id=%0d vector=%0d action=%0d kind=%0d started=%0d ended=%0d cfg=%0d samples=%0d starts=%0d bytes=%0d results=%0d aborted=%0d error=%0d nframe=%0d",
                    case_id,vector_id,action,kind,begin_cycle,cycle,local_cfg,local_samples,local_starts,local_bytes,local_results,local_abort,expect_error,expect_length);
            end
            $display("TU49_STATS cycles=%0d checks=%0d cases=%0d cfg=%0d samples=%0d starts=%0d bytes=%0d results=%0d aborts=%0d",
                cycle,cycle*2,plans,total_cfg,total_samples,total_starts,total_bytes,total_results,total_aborts);
            $fclose(tf);$display("TU49_DONE PASS");$finish;
        end
    end
    initial begin #1000000000;$fatal(1,"TU49_FAIL global timeout");end
endmodule
