`timescale 1ns/1ps
// Independent public-port bench. No DUT hierarchy, forced internals or stubs.
module tb_g05_real_composition;
    logic s_axi_aclk=0;
    always #5 s_axi_aclk=~s_axi_aclk;
    logic s_axi_aresetn=0;
    logic [11:0] s_axi_awaddr=0,s_axi_araddr=0;
    logic [2:0] s_axi_awprot=0,s_axi_arprot=0;
    logic s_axi_awvalid=0,s_axi_wvalid=0,s_axi_bready=0,s_axi_arvalid=0,s_axi_rready=0;
    logic [31:0] s_axi_wdata=0;
    logic [3:0] s_axi_wstrb=15;
    wire s_axi_awready,s_axi_wready,s_axi_bvalid,s_axi_arready,s_axi_rvalid;
    wire [1:0] s_axi_bresp,s_axi_rresp;
    wire [31:0] s_axi_rdata;
    wire yaw_pwm_o,pitch_pwm_o,speed_pwm_o;
    logic yaw_capture_i=0,pitch_capture_i=0,speed_capture_i=0;
    deepeye_g05_axi dut(.*);
    wire [2:0] outputs={speed_pwm_o,pitch_pwm_o,yaw_pwm_o};
    wire [2:0] inputs={speed_capture_i,pitch_capture_i,yaw_capture_i};
    localparam longint unsigned PERIOD=2000000;
    integer case_id,completion_status=0,raw,reset_generation=0;
    longint unsigned tick=0,total_cycles=0,assertions=0,stall_cycles=0;
    longint unsigned first_rise=0,rise_tick[0:2],last_high[0:2],last_period[0:2];
    longint unsigned pwm_edges=0,pin_edges=0,wr_tick=0;
    logic [2:0] previous_outputs=0;
    integer fixture_mode=0,fixture_delay[0:2],expected_high[0:2];
    bit check_width=0,check_period=0,held_read=0;
    logic [31:0] held_data;
    logic [1:0] held_resp;
    logic [31:0] words[0:31],saved[0:31];
    string trace_path;

    task automatic ck(input bit condition,input string message);
        assertions=assertions+1;
        if(!condition)begin
            $display("G05_COMPOSITION_FAIL case=%0d tick=%0d assertion=%0d reason=%s",case_id,tick,assertions,message);
            if(raw)begin $fdisplay(raw,"FAIL,%0d,%0d,%s",$time,tick,message);$fflush(raw);end
            $fatal(1,"G05_COMPOSITION_ASSERTION_FAILED");
        end
    endtask

    always @(posedge s_axi_aclk)begin
        total_cycles<=total_cycles+1;
        if(!s_axi_aresetn)tick<=0;else tick<=tick+1;
        #1;
        if(!s_axi_aresetn)begin
            previous_outputs=0;first_rise=0;
            for(integer k=0;k<3;k=k+1)begin rise_tick[k]=0;last_high[k]=0;last_period[k]=0;end
        end else begin
            if(first_rise==0 && outputs!=0)first_rise=tick;
            for(integer k=0;k<3;k=k+1)begin
                if(outputs[k]&&!previous_outputs[k])begin
                    if(rise_tick[k]!=0)begin
                        last_period[k]=tick-rise_tick[k];
                        if(check_period)ck(last_period[k]==PERIOD,$sformatf("output period channel%0d actual%0d",k,last_period[k]));
                    end
                    rise_tick[k]=tick;pwm_edges=pwm_edges+1;
                end
                if(!outputs[k]&&previous_outputs[k])begin
                    last_high[k]=tick-rise_tick[k];pwm_edges=pwm_edges+1;
                    if(check_width)ck(last_high[k]==expected_high[k],$sformatf("output high channel%0d expected%0d actual%0d",k,expected_high[k],last_high[k]));
                end
            end
            previous_outputs=outputs;
            if(held_read)begin
                stall_cycles=stall_cycles+1;
                if(s_axi_rvalid!==1'b1 || s_axi_rdata!==held_data || s_axi_rresp!==held_resp)
                    ck(0,"R response changed while RREADY stalled");
            end
        end
    end

    // Three explicitly scheduled external fixture pins. A pin value changes on
    // a falling clock edge and is sampled later by the real synchronizers.
    // Normal path mirrors only the PUBLIC output through independently scheduled pins.
    always @(negedge s_axi_aclk)begin : fixture
        logic [2:0] levels;
        longint signed relative,phase;
        levels=0;
        if(s_axi_aresetn && first_rise!=0)begin
            for(integer k=0;k<3;k=k+1)begin
                relative=longint'(tick)-longint'(first_rise)-fixture_delay[k];
                phase=relative%longint'(PERIOD);
                if(fixture_mode==0)levels[k]=outputs[k];
                else if(relative>=0)levels[k]=(phase<expected_high[k]);
            end
            case(fixture_mode)
                1:levels=0; // missing all inputs: actual watchdog, no fake sample
                2:levels[2]=1; // independent stuck-high speed pin
                3:begin // wrong pitch high by three counts
                    relative=longint'(tick)-longint'(first_rise);
                    levels[1]=(relative%longint'(PERIOD))<(expected_high[1]+3);
                end
                4:begin // wrong yaw period by three counts
                    relative=longint'(tick)-longint'(first_rise);
                    levels[0]=(relative%longint'(PERIOD+3))<expected_high[0];
                end
                5:if(tick<first_rise+2*PERIOD)levels[2]=0; // whole-frame witness mismatch
                7:begin // permitted two-tick skew AND two-tick pitch high variation
                    relative=longint'(tick)-longint'(first_rise)-fixture_delay[1];
                    levels[1]=(relative>=0)&&((relative%longint'(PERIOD))<(expected_high[1]+2));
                end
                8:begin levels[0]=outputs[2];levels[2]=outputs[0];end // distinct-code wrong wiring
                default:begin end
            endcase
        end
        {speed_capture_i,pitch_capture_i,yaw_capture_i}=levels;
    end
    always @(yaw_pwm_o or pitch_pwm_o or speed_pwm_o)if(raw)$fdisplay(raw,"PWM,%0d,%0d,%b",$time,tick,outputs);
    always @(yaw_capture_i or pitch_capture_i or speed_capture_i)if(raw)begin
        pin_edges=pin_edges+1;$fdisplay(raw,"PIN,%0d,%0d,%b",$time,tick,inputs);
    end

    task automatic wait_tick(input longint unsigned target);
        while(tick<target)@(negedge s_axi_aclk);
        ck(tick==target,$sformatf("missed requested public tick %0d actual%0d",target,tick));
    endtask
    task automatic write_reg(input logic[11:0] address,input logic[31:0] value,
                             input logic[1:0] response=0,input logic[3:0] strobes=15);
        integer bound;
        @(negedge s_axi_aclk);
        s_axi_awaddr=address;s_axi_wdata=value;s_axi_wstrb=strobes;
        s_axi_awvalid=1;s_axi_wvalid=1;s_axi_bready=0;
        @(posedge s_axi_aclk);
        ck(s_axi_awready===1'b1&&s_axi_wready===1'b1,"bounded sequential write ready");
        @(negedge s_axi_aclk);s_axi_awvalid=0;s_axi_wvalid=0;
        bound=0;
        while(!s_axi_bvalid&&bound<20)begin @(negedge s_axi_aclk);bound=bound+1;end
        ck(s_axi_bvalid===1'b1&&s_axi_bresp===response,$sformatf("write %h data%h response expected%h actual%h",address,value,response,s_axi_bresp));
        wr_tick=tick;$fdisplay(raw,"WRITE,%0d,%0d,%h,%h,%h",$time,tick,address,value,s_axi_bresp);
        s_axi_bready=1;@(negedge s_axi_aclk);s_axi_bready=0;
    endtask
    task automatic start_read(input logic[11:0] address,input logic[1:0] response=0);
        integer bound;
        @(negedge s_axi_aclk);s_axi_araddr=address;s_axi_arvalid=1;s_axi_rready=0;
        @(posedge s_axi_aclk);ck(s_axi_arready===1'b1,"read address ready");
        @(negedge s_axi_aclk);s_axi_arvalid=0;
        bound=0;while(!s_axi_rvalid&&bound<20)begin @(negedge s_axi_aclk);bound=bound+1;end
        ck(s_axi_rvalid===1'b1&&s_axi_rresp===response,$sformatf("read %h response expected%h actual%h",address,response,s_axi_rresp));
        held_data=s_axi_rdata;held_resp=s_axi_rresp;held_read=1;
        $fdisplay(raw,"READ_START,%0d,%0d,%h,%h,%h",$time,tick,address,s_axi_rdata,s_axi_rresp);
    endtask
    task automatic release_read;
        held_read=0;s_axi_rready=1;@(negedge s_axi_aclk);s_axi_rready=0;
    endtask
    task automatic read_reg(input logic[11:0] address,output logic[31:0] value,input logic[1:0] response=0);
        start_read(address,response);value=held_data;release_read();
    endtask
    task automatic read64(input logic[11:0] address,output longint unsigned value);
        logic[31:0] lo,hi;read_reg(address,lo);read_reg(address+4,hi);value={hi,lo};
    endtask
    task automatic reset_design;
        check_width=0;check_period=0;held_read=0;
        @(negedge s_axi_aclk);s_axi_aresetn=0;
        s_axi_awvalid=0;s_axi_wvalid=0;s_axi_bready=0;s_axi_arvalid=0;s_axi_rready=0;
        fixture_mode=0;for(integer i=0;i<3;i=i+1)fixture_delay[i]=0;
        repeat(5)@(negedge s_axi_aclk);
        s_axi_aresetn=1;reset_generation=reset_generation+1;
        repeat(3)@(negedge s_axi_aclk);ck(outputs===3'b000,"reset output zero");
    endtask
    task automatic begin_identity;
        logic[31:0] value,expected;
        for(integer i=0;i<13;i=i+1)begin
            expected=(i==12)?(32'h51000000+reset_generation):(32'ha0000000+reset_generation*256+i);
            write_reg(12'h100+i*4,expected);
        end
        write_reg(12'h00c,1);
        for(integer i=0;i<13;i=i+1)begin
            expected=(i==12)?(32'h51000000+reset_generation):(32'ha0000000+reset_generation*256+i);
            read_reg(12'h100+i*4,value);ck(value===expected,"PL identity echo");
        end
        read_reg(12'h008,value);ck(value[0]&&!value[1],"session live");
    endtask
    task automatic stage(input integer yaw,pitch,profile,speed,ttl,input logic[31:0] command_id,tag);
        write_reg(12'h200,32'(yaw&65535));write_reg(12'h204,32'(pitch&65535));
        write_reg(12'h208,profile);write_reg(12'h20c,speed);write_reg(12'h210,ttl);
        write_reg(12'h214,command_id);write_reg(12'h218,tag);
    endtask
    task automatic start_legal(input integer yaw=100,pitch=-200,speed=20,ttl=300);
        integer timeout;
        expected_high[0]=10000+16*(yaw+15000);expected_high[1]=10000+16*(pitch+15000);expected_high[2]=50000+1000*speed;
        check_width=1;check_period=1;
        stage(yaw,pitch,1,speed,ttl,1,32'habc00001);write_reg(12'h00c,2);
        timeout=0;while(first_rise==0&&timeout<20)begin @(negedge s_axi_aclk);timeout=timeout+1;end
        ck(first_rise!=0&&outputs===3'b111,"first triple applies together");
    endtask
    task automatic latch_record;
        logic[31:0] value;
        read_reg(12'h008,value);ck(value[4]&&!value[1],"latest eligible before latch");
        write_reg(12'h00c,4);
        for(integer i=0;i<32;i=i+1)read_reg(12'h300+4*i,words[i]);
        read_reg(12'h008,value);ck(value[5]&&!value[1],"latched record stays eligible");
    endtask
    task automatic check_record(input logic[31:0] command_id,tag,input integer yaw,pitch,speed,ttl,input longint unsigned applied);
        longint unsigned start_w,end_w,event_tick;
        ck(words[0]>0,"nonzero capture sequence");ck(words[1]==command_id&&words[2]==tag,"actual PL command identity");
        ck(words[3]==((speed<<8)|1)&&words[4]=={16'(pitch),16'(yaw)}&&words[5]==ttl,"record command snapshot");
        ck({words[7],words[6]}==applied,"actual application timestamp");
        ck({words[9],words[8]}==applied+64'(ttl)*100000,"original nonrenewed deadline");
        event_tick={words[11],words[10]};
        ck(event_tick>=applied+2*PERIOD&&event_tick<=tick,"complete postapplication capture only");
        for(integer i=0;i<3;i=i+1)begin
            ck(words[12+i]==PERIOD,"actual measured period");
            ck(words[15+i]==expected_high[i]+((fixture_mode==7&&i==1)?2:0),"actual independently measured high");
            start_w={words[19+2*i],words[18+2*i]};end_w={words[25+2*i],words[24+2*i]};
            ck(start_w>0&&end_w>start_w&&end_w-start_w==PERIOD,"full-cycle causal witnesses");
            if(i>0)ck(start_w-{words[19],words[18]}==fixture_delay[i],"measured channel start skew");
        end
        ck(words[30]==32'h51000000+reset_generation&&words[31]==32'h47303544,"record session/magic");
        $display("G05_OBSERVATION case=%0d apply=%0d result_tick=%0d seq=%0d start=%0d,%0d,%0d high=%0d,%0d,%0d",case_id,applied,event_tick,words[0],{words[19],words[18]},{words[21],words[20]},{words[23],words[22]},words[15],words[16],words[17]);
    endtask
    task automatic terminal_state(input integer expected_fault=-1,input integer wrapper=-1);
        logic[31:0] state,fault;
        repeat(3)@(negedge s_axi_aclk);
        read_reg(12'h008,state);read_reg(12'h010,fault);
        ck(state[1]&&!state[2]&&!state[3]&&!state[4]&&!state[5]&&!state[6],"terminal eligibility and activity cleared");
        ck(outputs===3'b000,"terminal PWM zero");
        if(expected_fault>=0)ck(fault[7:0]==expected_fault,"engine terminal cause");
        if(wrapper>=0)ck(fault[15:8]==wrapper,"wrapper terminal cause");
        $display("G05_TERMINAL case=%0d tick=%0d status=%h fault=%h",case_id,tick,state,fault);
    endtask

    initial begin : test
        logic[31:0] value,old_seq,new_seq;
        longint unsigned a,d,seen,boundary;
        if(!$value$plusargs("CASE=%d",case_id))$fatal(1,"missing CASE");
        if(!$value$plusargs("TRACE=%s",trace_path))$fatal(1,"missing TRACE");
        raw=$fopen(trace_path,"w");if(!raw)$fatal(1,"trace open failed");
        $fdisplay(raw,"kind,time_ns,public_tick,data...");
        reset_design();
        read_reg(0,value);ck(value==32'h47303544,"real AXI magic");
        read_reg(12'h02c,value,2); // explicitly unmapped old offset
        case(case_id)
            0:begin
                begin_identity();start_legal();a=first_rise;
                read64(12'h040,seen);ck(seen==a,"first actual application readback");
                read64(12'h048,d);ck(d==a+30000000,"first TTL readback");
                wait_tick(a+2*PERIOD+64);latch_record();check_record(1,32'habc00001,100,-200,20,300,a);
                old_seq=words[0];for(integer i=0;i<32;i=i+1)saved[i]=words[i];
                stage(100,-200,1,20,300,1,32'habc00001);write_reg(12'h00c,2); // exact duplicate while held
                start_read(12'h300);ck(held_data==old_seq,"held R sequence");
                wait_tick(a+3*PERIOD+128);ck(s_axi_rdata==old_seq,"R stable across newer capture");release_read();
                read_reg(12'h01c,new_seq);ck(new_seq>old_seq,"continuous capture progresses while read/latch held");
                for(integer i=0;i<32;i=i+1)begin read_reg(12'h300+4*i,value);ck(value===saved[i],"entire latch immutable");end
                read64(12'h040,seen);ck(seen==a,"duplicate no reapplication");read64(12'h048,seen);ck(seen==d,"duplicate no TTL renewal");
                write_reg(12'h00c,5);write_reg(12'h00c,4);read_reg(12'h300,value);ck(value>old_seq&&value==new_seq,"ACK then newer nonwrapping sequence");
                start_read(12'h304);ck(held_data==1,"held command response before STOP");
                check_width=0;check_period=0;write_reg(12'h00c,3);
                ck(outputs==0&&s_axi_rdata==1,"STOP while read/latch held stops outputs but preserves issued R");
                release_read();terminal_state(6,0);read_reg(12'h300,value,2);
                reset_design();begin_identity();start_legal(0,0,20,1);a=first_rise;
                check_width=0;wait_tick(a+100000);ck(outputs==0,"one-ms TTL exact edge");terminal_state(2,0);
            end
            1:begin
                write_reg(12'h100,1);write_reg(12'h00c,1,2);read_reg(12'h008,value);ck(!value[0]&&outputs==0,"incomplete identity failclosed");
                for(integer i=0;i<13;i=i+1)write_reg(12'h100+4*i,0);
                write_reg(12'h00c,1,2);ck(outputs==0,"zero identity failclosed");begin_identity();
                for(integer i=0;i<6;i=i+1)write_reg(12'h200+4*i,(i==2)?1:0);
                write_reg(12'h00c,2,2);ck(outputs==0,"incomplete command failclosed");
                start_legal();a=first_rise;check_width=0;
                stage(100,-199,1,20,300,1,32'habc00001);write_reg(12'h00c,2,2);terminal_state(6,1);
                reset_design();begin_identity();read_reg(12'h130,value);ck(value==32'h51000000+reset_generation,"fresh identity after reset");
            end
            2,3,4:begin
                begin_identity();start_legal(0,0,20,(case_id==2)?300:20);a=first_rise;d=a+2000000;
                wait_tick(a+600000);stage(100,-200,1,19,300,2,32'habc00002);write_reg(12'h00c,2);
                read_reg(12'h008,value);ck(value[3]&&!value[4],"new triple pending and old capture ineligible");
                read_reg(12'h018,value);ck(value==32'habc00001,"old active tag retained while pending");
                read64(12'h048,seen);ck(seen==a+((case_id==2)?30000000:2000000),"old deadline retained while pending");
                if(case_id==4)begin
                    check_width=0;check_period=0;wait_tick(d-4);write_reg(12'h00c,3);
                    ck(wr_tick+1==d,"STOP processed one edge before exact expiry");ck(outputs==0,"STOP/expiry edge wins over pending apply");terminal_state(6,0);
                end else if(case_id==3)begin
                    check_width=0;check_period=0;wait_tick(d);ck(outputs==0,"old expiry wins at pending frame boundary");
                    read64(12'h040,seen);ck(seen==a,"expired pending never applied");terminal_state(2,0);
                end else begin
                    boundary=a+PERIOD;wait_tick(boundary-1);ck(outputs==0,"no early pending application");
                    expected_high[0]=251600;expected_high[1]=246800;expected_high[2]=69000;
                    wait_tick(boundary);ck(outputs===3'b111,"pending triple atomically starts on frame boundary");
                    repeat(3)@(negedge s_axi_aclk);read64(12'h040,seen);ck(seen==boundary,"new actual application timestamp");
                    wait_tick(boundary+2*PERIOD+64);latch_record();check_record(2,32'habc00002,100,-200,19,300,boundary);
                end
            end
            5:begin
                begin_identity();start_legal(0,0,20,300);check_width=0;
                stage(0,0,2,20,300,2,32'habc00002);write_reg(12'h00c,2,2);terminal_state(6,1);
                reset_design();begin_identity();stage(6000,6000,1,20,300,1,1);write_reg(12'h00c,2,2);
                ck(first_rise==0,"combined diagonal curvature rejects before output");terminal_state(6,1);
                reset_design();begin_identity();stage(-32768,-32768,1,20,300,1,1);write_reg(12'h00c,2,2);
                ck(first_rise==0,"signed minimum pair fails closed through real mapper");terminal_state(6,1);
            end
            6,7,8,9,10,11,12,13:begin
                begin_identity();start_legal();a=first_rise;
                case(case_id)
                    6:fixture_mode=1;
                    7:fixture_mode=2;
                    8:fixture_mode=3;
                    9:fixture_mode=4;
                    10:fixture_mode=5;
                    11:begin fixture_mode=6;fixture_delay[2]=3;end
                    12:begin fixture_mode=7;fixture_delay[1]=1;fixture_delay[2]=2;end
                    13:fixture_mode=8;
                endcase
                if(case_id==12)begin
                    wait_tick(a+2*PERIOD+64);latch_record();check_record(1,32'habc00001,100,-200,20,300,a);
                end else begin
                    // Stop may truncate a high pulse on a malformed input; widths before that remain in the raw trace.
                    check_width=0;check_period=0;
                    wait_tick(a+((case_id==6||case_id==7||case_id==10)?3*PERIOD+32:2*PERIOD+64));
                    terminal_state((case_id==6)?4:3,0);
                    read_reg(12'h300,value,2);
                end
            end
            99:begin
                begin_identity();start_legal();a=first_rise;
                wait_tick(a+300000);ck(last_high[2]==70000,"mutation control real speed width");
            end
            default:$fatal(1,"unknown CASE");
        endcase
        $fdisplay(raw,"END,%0d,%0d,assertions=%0d",$time,tick,assertions);$fclose(raw);raw=0;
        completion_status=1;
        $display("G05_COMPOSITION_STATS case=%0d assertions=%0d stall_cycles=%0d pwm_edges=%0d pin_edges=%0d cycles=%0d",case_id,assertions,stall_cycles,pwm_edges,pin_edges,total_cycles);
        $display("G05_COMPOSITION_PASS case=%0d assertions=%0d",case_id,assertions);
        $finish;
    end
    initial begin #200000000; $fatal(1,"G05_COMPOSITION_SIMULATION_TIMEOUT"); end
endmodule
