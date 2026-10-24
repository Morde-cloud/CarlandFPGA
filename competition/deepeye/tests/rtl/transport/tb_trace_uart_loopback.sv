`timescale 1ns/1ps
// B52 fixture only: public ports, common clock/reset/cancel; no product changes.
module tb_trace_uart_loopback;
    parameter integer CLOCK_HZ=16, BAUD=1, EXTENDED=0, DEFAULT_ONLY=0;
    reg clk=0; always #5 clk=~clk;
    reg rst=1,cancel=0,cv=0,sv=0,sl=0,tr=0,rr=0;
    reg [7:0] count=0,epoch=0;
    reg [3:0] exponent=0;
    reg [31:0] session=0,first_index=0;
    reg [1:0] channel=0;
    reg [63:0] first_tick=0,source_tick=0;
    reg [15:0] index_stride=0,tick_stride=0,seq=0,sd=0;
    reg valid_sample=0,saturated=0,held=0,source_fault=0;
    wire cr,sr,tv,tx,tu_busy,tbusy,wfault,wevent;
    wire [2:0] terror;
    wire [5:0] tbytes;
    wire [1:0] wcode;
    wire rv,ru_busy,receiving,line_event,parse_event;
    wire [2:0] line_bits;
    wire [1:0] parse_code;
    wire [7:0] rtype,repoch;
    wire [15:0] rseq;
    wire [31:0] rtick;
    wire [5:0] rlen;
    wire [255:0] payload;
    wire [31:0] uf,ur,uo,ue,us,ua,pb,pf,pr,pv,pl,pc,pa;
    reg flip=0;
    wire rx_line=tx^flip;
    deepeye_trace_uart_candidate #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) transmitter (
        .clk(clk),.rst(rst),.cancel(cancel),.cfg_valid(cv),.cfg_ready(cr),
        .cfg_count(count),.cfg_e(exponent),.cfg_session(session),.cfg_channel(channel),
        .cfg_first_index(first_index),.cfg_first_tick(first_tick),
        .cfg_index_stride(index_stride),.cfg_tick_stride(tick_stride),
        .cfg_valid_sample(valid_sample),.cfg_saturated(saturated),.cfg_held(held),
        .cfg_source_fault(source_fault),.cfg_source_tick(source_tick),.cfg_epoch(epoch),.cfg_seq(seq),
        .s_valid(sv),.s_ready(sr),.s_data(sd),.s_last(sl),.tx(tx),.uart_busy(tu_busy),
        .result_valid(tv),.result_ready(tr),.result_error(terror),.result_bytes(tbytes),
        .busy(tbusy),.wire_faulted(wfault),.wire_fault_event(wevent),.wire_fault_code(wcode));
    deepeye_uart_wire_rx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD),.STAT_W(32)) receiver (
        .clk(clk),.rst(rst),.cancel(cancel),.rx_async(rx_line),.out_ready(rr),.out_valid(rv),
        .out_type(rtype),.out_epoch(repoch),.out_seq(rseq),.out_tick(rtick),.out_len(rlen),.out_payload(payload),
        .uart_busy(ru_busy),.receiving(receiving),.line_error_event(line_event),.line_error_bits(line_bits),
        .error_event(parse_event),.error_code(parse_code),.stat_uart_frames(uf),.stat_uart_retired(ur),
        .stat_uart_overruns(uo),.stat_uart_framing(ue),.stat_uart_false_starts(us),.stat_uart_aborted(ua),
        .stat_bytes(pb),.stat_frames(pf),.stat_retired(pr),.stat_version(pv),.stat_length(pl),
        .stat_crc(pc),.stat_aborted(pa));

    integer logfd,fd,rc,i,j,sel,case_id,cycle=0,run_id=-1,mode,kind,stage,phase;
    integer words,bad_last,expected_error,frame_len,feed_count,feed_valid;
    reg [15:0] samples[0:255]; reg [7:0] frame[0:45];
    integer started,completed,sent,candidates,retired,reports,crc_events,line_events;
    integer total_started=0,total_completed=0,total_sent=0,total_candidates=0,total_retired=0,total_reports=0;
    integer total_crc=0,total_line=0,normal_runs=0,error_runs=0,abort_runs=0,recovery_runs=0,corrupt_runs=0;
    integer byte_start=0,byte_index=-1,elapsed,bit_no,guard,tseen_cycle,vseen_cycle,rx_retire_cycle;
    integer last_wire=-1,wire_value,control_kind,control_phase;
    reg tracking=0,active_byte=0,pending_sample=0,seen_tx=0,seen_rx=0;
    reg prev_ub=0,rx_hold=0,tx_hold=0,inject=0,flip_reported=0;
    reg [325:0] held_packet;
    reg [8:0] held_report;
    string vector_path,event_path,binding;
    localparam integer BYTE_CYCLES=(10*64'(CLOCK_HZ)+BAUD-1)/BAUD;
    localparam integer QUARTER=(CLOCK_HZ/BAUD)/4;

    task automatic fail(input string reason);
        begin $display("TRACE52_FAIL cycle=%0d run=%0d reason=%s",cycle,run_id,reason); $fatal(1,"TRACE52_PUBLIC_FAILURE"); end
    endtask
    task automatic stats(input integer tag);
        begin $fdisplay(logfd,"K %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",cycle,run_id,tag,uf,ur,uo,ue,us,ua,pb,pf,pr,pv,pl,pc,pa); end
    endtask
    task automatic packet_event(input string tag);
        begin $fdisplay(logfd,"%s %0d %0d %02x %02x %04x %08x %0d %064x",tag,cycle,run_id,rtype,repoch,rseq,rtick,rlen,payload); end
    endtask

    always @(posedge clk) begin
        cycle=cycle+1;
        if(rst||cancel) begin
            if(cr!==0||sr!==0||tv!==0||rv!==0) fail("control_mask");
            rx_hold=0;tx_hold=0;pending_sample=0;
        end else if(tracking) begin
            if(wfault||wevent||line_event) fail("wire_or_line_fault");
            if(rx_hold&&(!rv||{rtype,repoch,rseq,rtick,rlen,payload}!==held_packet[325:0])) fail("rx_hold_changed");
            if(tx_hold&&(!tv||{terror,tbytes}!==held_report)) fail("tx_hold_changed");
            if(cv&&cr) $fdisplay(logfd,"C %0d %0d %02x %01x %08x %01x %08x %016x %04x %04x %b %b %b %b %016x %02x %04x",cycle,run_id,count,exponent,session,channel,first_index,first_tick,index_stride,tick_stride,valid_sample,saturated,held,source_fault,source_tick,epoch,seq);
            pending_sample=sv&&!sr;
            if(sv&&sr) begin $fdisplay(logfd,"S %0d %0d %0d %04x %b",cycle,run_id,sent,sd,sl);sent=sent+1;total_sent=total_sent+1; end
            if(tv&&!seen_tx) begin
                if(tu_busy||terror!==expected_error[2:0]||tbytes!==frame_len[5:0]) fail("tx_report_fields_or_early");
                seen_tx=1;tseen_cycle=cycle;$fdisplay(logfd,"U %0d %0d %0d %0d",cycle,run_id,terror,tbytes);
            end
            if(rv&&!seen_rx) begin seen_rx=1;vseen_cycle=cycle;candidates=candidates+1;total_candidates=total_candidates+1;packet_event("V"); end
            if(rv&&rr) begin retired=retired+1;total_retired=total_retired+1;rx_retire_cycle=cycle;packet_event("R"); end
            if(tv&&tr) begin reports=reports+1;total_reports=total_reports+1;$fdisplay(logfd,"T %0d %0d %0d %0d",cycle,run_id,terror,tbytes);end
            if(parse_event) begin $fdisplay(logfd,"E %0d %0d %0d",cycle,run_id,parse_code);if(parse_code==3) begin crc_events=crc_events+1;total_crc=total_crc+1;end end
            if(line_event) begin $fdisplay(logfd,"L %0d %0d %0d",cycle,run_id,line_bits);line_events=line_events+1;total_line=total_line+1;end
            rx_hold=rv&&!rr;held_packet={rtype,repoch,rseq,rtick,rlen,payload};
            tx_hold=tv&&!tr;held_report={terror,tbytes};
        end
        #1;
        if(rst||cancel) begin
            if(tx!==1||tu_busy!==0) fail("control_edge_idle");
            active_byte=0;flip=0;
        end else if(tracking) begin
            if(tu_busy&&!prev_ub) begin
                byte_index=started;started=started+1;total_started=total_started+1;
                byte_start=cycle;active_byte=1;$fdisplay(logfd,"B %0d %0d %0d",cycle,run_id,byte_index);
            end
            if(!tu_busy&&prev_ub) begin
                completed=completed+1;total_completed=total_completed+1;active_byte=0;
                $fdisplay(logfd,"D %0d %0d %0d",cycle,run_id,byte_index);
            end
            elapsed=cycle-byte_start;
            flip=inject&&active_byte&&(byte_index==12)&&(elapsed>=((4*64'(CLOCK_HZ)+BAUD-1)/BAUD))&&(elapsed<((5*64'(CLOCK_HZ)+BAUD-1)/BAUD));
            if(flip&&!flip_reported) begin
                $fdisplay(logfd,"F %0d %0d 12 3 %0d %0d",cycle,run_id,byte_start+(4*64'(CLOCK_HZ)+BAUD-1)/BAUD,byte_start+(5*64'(CLOCK_HZ)+BAUD-1)/BAUD);
                flip_reported=1;
            end
        end else flip=0;
        prev_ub=tu_busy;
        #1;
        wire_value={tx,tu_busy,rx_line,flip};
        if(wire_value!=last_wire) begin $fdisplay(logfd,"W %0d %0d %b %b %b %b",cycle,run_id,tx,tu_busy,rx_line,flip);last_wire=wire_value;end
    end

    task automatic load_case(input integer selection);
        integer n,k;
        begin
            fd=$fopen(vector_path,"r");if(!fd)fail("vector_open");
            for(n=0;n<=selection;n=n+1) begin
                rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h",case_id,count,exponent,session,channel,first_index,first_tick,index_stride,tick_stride,valid_sample,saturated,held,source_fault,source_tick,epoch,seq,bad_last,expected_error,frame_len,words);
                if(rc!=20)fail("vector_fields");
                for(k=0;k<words;k=k+1)begin rc=$fscanf(fd,"%h",samples[k]);if(rc!=1)fail("sample_input");end
                for(k=0;k<frame_len;k=k+1)begin rc=$fscanf(fd,"%h",frame[k]);if(rc!=1)fail("frame_input");end
            end
            $fclose(fd);feed_count=count;feed_valid=valid_sample;
        end
    endtask
    task automatic ready(input reg nr,input reg nt);
        begin if(rr!==nr||tr!==nt)begin rr=nr;tr=nt;$fdisplay(logfd,"G %0d %0d %b %b",cycle,run_id,rr,tr);end end
    endtask
    task automatic begin_run(input integer selection,input integer run_mode,input integer which,input integer target_stage,input integer target_phase);
        begin
            cv=0;sv=0;ready(0,0);guard=0;
            while(cr!==1)begin @(negedge clk);guard=guard+1;if(guard>100)fail("idle_timeout");end
            if(tbusy||tu_busy||rv||tx!==1)fail("orphan_at_start");
            load_case(selection);run_id=run_id+1;mode=run_mode;kind=which;stage=target_stage;phase=target_phase;
            started=0;completed=0;sent=0;candidates=0;retired=0;reports=0;crc_events=0;line_events=0;
            seen_tx=0;seen_rx=0;rx_hold=0;tx_hold=0;pending_sample=0;flip_reported=0;
            tseen_cycle=-1;vseen_cycle=-1;rx_retire_cycle=-1;inject=(mode==1);tracking=1;
            $fdisplay(logfd,"N %0d %0d %0d %0d %0d %0d %0d %0d",cycle,run_id,selection,case_id,mode,kind,stage,phase);stats(0);
            cv=1;@(posedge clk);if(!cr)fail("config_not_admitted");@(negedge clk);cv=0;
            count=~count;exponent=~exponent;session=~session;channel=~channel;first_index=~first_index;first_tick=~first_tick;
            index_stride=~index_stride;tick_stride=~tick_stride;valid_sample=~valid_sample;saturated=~saturated;held=~held;source_fault=~source_fault;source_tick=~source_tick;epoch=~epoch;seq=~seq;
            $fdisplay(logfd,"M %0d %0d",cycle,run_id);guard=0;
        end
    endtask
    task automatic drive_samples;
        begin
            cv=(reports==0)&&(cycle%5==0);
            if(!pending_sample)begin
                sv=(sent<words)&&feed_valid&&(cycle%7!=2);
                if(sent<words)begin sd=samples[sent];sl=(sent==feed_count-1);if(sent==bad_last)sl=!sl;end
            end
        end
    endtask
    task automatic end_run;
        begin
            cv=0;sv=0;ready(0,0);stats(3);
            $fdisplay(logfd,"Z %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",cycle,run_id,started,completed,sent,candidates,retired,reports,crc_events,line_events);
            tracking=0;inject=0;repeat(24)@(negedge clk);
        end
    endtask
    task automatic clean_run(input integer selection,input integer run_mode);
        reg nr,nt,done;
        begin
            begin_run(selection,run_mode,-1,-1,-1);done=0;
            while(!done)begin
                drive_samples();nr=0;nt=0;
                if(expected_error!=0||mode==1) begin nr=1;nt=seen_tx&&(cycle>=tseen_cycle+5);end
                else begin
                    nr=seen_rx&&(cycle>=vseen_cycle+frame_len*BYTE_CYCLES+16);
                    if(run_id%2==0)nt=seen_tx&&(cycle>=tseen_cycle+5);
                    else nt=(retired==1)&&(cycle>=rx_retire_cycle+9);
                end
                ready(nr,nt);@(posedge clk);@(negedge clk);guard=guard+1;
                if(guard>3*frame_len*BYTE_CYCLES+100000)fail("transaction_timeout");
                done=(reports==1)&&((expected_error!=0)?(cycle>=tseen_cycle+20):((mode==1)?(crc_events==1):(retired==1)));
            end
            if(started!=frame_len||completed!=frame_len||reports!=1)fail("tx_counts");
            if(expected_error!=0)begin if(candidates||retired||started)fail("error_output");error_runs=error_runs+1;end
            else if(mode==1)begin if(candidates||retired||crc_events!=1)fail("corrupt_candidate");corrupt_runs=corrupt_runs+1;end
            else begin if(candidates!=1||retired!=1||crc_events)fail("rx_counts");if(mode==3)recovery_runs=recovery_runs+1;else normal_runs=normal_runs+1;end
            end_run();
        end
    endtask
    task automatic abort_run(input integer which,input integer target_stage,input integer target_phase);
        reg reached;
        integer target_byte,target_elapsed;
        begin
            begin_run(3,2,which,target_stage,target_phase);reached=0;
            target_byte=(stage==1)?0:frame_len-1;
            target_elapsed=(target_phase*64'(CLOCK_HZ)+BAUD-1)/BAUD+QUARTER;
            while(!reached)begin
                drive_samples();ready(stage==4,0);@(posedge clk);@(negedge clk);guard=guard+1;
                if(stage==0)reached=(sent>=1);
                else if(stage==1||stage==2)reached=active_byte&&(byte_index==target_byte)&&(cycle-byte_start>=target_elapsed);
                else if(stage==3)reached=seen_rx;
                else if(stage==4)reached=(retired==1);
                if(guard>frame_len*BYTE_CYCLES+100000)fail("abort_phase_timeout");
            end
            stats(1);$fdisplay(logfd,"A %0d %0d %0d %0d %0d %b %b %b",cycle,run_id,kind,stage,phase,ru_busy,receiving,rv);
            cv=1;sv=1;ready(1,1);if(which==0)rst=1;else cancel=1;
            #1;if(cr!==0||sr!==0||tv!==0||rv!==0)fail("immediate_mask");
            $fdisplay(logfd,"I %0d %0d %b %b %b %b",cycle,run_id,cr,sr,tv,rv);
            repeat(2)@(negedge clk);stats(2);
            rst=0;cancel=0;cv=0;sv=0;ready(0,0);repeat(24)@(negedge clk);
            if(tbusy||tu_busy||rv||receiving||ru_busy||tx!==1)fail("abort_rearm");
            if(reports)fail("aborted_tx_report");abort_runs=abort_runs+1;end_run();
            clean_run(3,3);
        end
    endtask
    initial begin
        if(!$value$plusargs("VECTORS=%s",vector_path)||!$value$plusargs("EVENTS=%s",event_path)||!$value$plusargs("BIND=%s",binding))$fatal(1,"TRACE52_PATHS");
        logfd=$fopen(event_path,"w");if(!logfd)$fatal(1,"TRACE52_OPEN");
        $fdisplay(logfd,"H %0d %0d %s",CLOCK_HZ,BAUD,binding);
        $display("TRACE52_BEGIN clock=%0d baud=%0d bind=%s",CLOCK_HZ,BAUD,binding);
        repeat(3)@(negedge clk);rst=0;repeat(24)@(negedge clk);
        if(DEFAULT_ONLY)clean_run(53,0);
        else begin
            for(sel=0;sel<53;sel=sel+1)clean_run(sel,0);
            if(EXTENDED)begin
                for(control_kind=0;control_kind<2;control_kind=control_kind+1)begin
                    abort_run(control_kind,0,-1);
                    for(control_phase=0;control_phase<10;control_phase=control_phase+1)begin abort_run(control_kind,1,control_phase);abort_run(control_kind,2,control_phase);end
                    abort_run(control_kind,3,-1);abort_run(control_kind,4,-1);
                end
                clean_run(3,1);clean_run(3,3);
            end
        end
        $fdisplay(logfd,"Q %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",run_id+1,normal_runs,error_runs,abort_runs,recovery_runs,corrupt_runs,total_started,total_completed,total_sent,total_candidates,total_retired,total_reports,total_crc,total_line,cycle);
        $fdisplay(logfd,"END %0d %s",cycle,binding);$fclose(logfd);
        $display("TRACE52_DONE clock=%0d baud=%0d runs=%0d cycles=%0d time_ns=%0d bind=%s",CLOCK_HZ,BAUD,run_id+1,cycle,$time,binding);
        $finish;
    end
endmodule
