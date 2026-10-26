`timescale 1ns/1ps
// New author public-port bench. External pins are separately scheduled digital
// fixtures, never hardware evidence. No DUT hierarchy is read or forced here.
module tb_g05_capture_engine;
    logic clk=0, rst=1, stop=0, cfg_valid=0, cfg_ready;
    logic [31:0] cfg_period=0;
    logic [95:0] cfg_highs=0;
    logic [63:0] cfg_ttl_ticks=0, cfg_tag=0;
    logic [2:0] capture_async_i=0, pwm_o;
    logic accepted,rejected,applied,running,pending,halted;
    logic [7:0] fault_code;
    logic [63:0] cycle_tick,applied_tick,deadline_tick,active_tag;
    logic result_valid;
    logic [31:0] result_seq;
    logic [63:0] result_tag,result_tick;
    logic [95:0] result_periods,result_highs;
    logic [191:0] result_starts,result_ends;
    deepeye_g05_capture_engine dut(.*);
    always #5 clk=~clk;

    integer fixture_mode=0, delay0=0,delay1=0,delay2=0;
    logic swap_axes=0;
    logic [2:0] stuck_low=0,stuck_high=0;
    logic [7:0] history [0:2];
    logic [31:0] external_period=40;
    logic [95:0] external_highs={32'd16,32'd12,32'd8};
    logic [63:0] external_first_rise=64'h7fffffffffffffff;
    logic external_enable=1;
    integer checks=0,cases=0,event_log;
    string mode;
    logic [2:0] prior_pwm=0,prior_pin=0;
    logic prior_halted=0;
    logic [31:0] prior_seq=0;
    // A pin scheduled at a falling edge is sampled at the NEXT rising edge.
    always @(negedge clk) begin : fixture
        logic [2:0] candidate;
        logic [63:0] phase;
        if(rst) begin
            for(integer i=0;i<3;i=i+1) history[i]=0;
            capture_async_i=0;
        end else begin
            for(integer i=0;i<3;i=i+1) history[i]={history[i][6:0],pwm_o[i]};
            candidate=0;
            if(fixture_mode==1) begin
                candidate={history[2][delay2],history[1][delay1],history[0][delay0]};
                if(swap_axes) candidate={candidate[2],candidate[0],candidate[1]};
            end else if(fixture_mode==2 && external_enable && cycle_tick+1>=external_first_rise) begin
                phase=(cycle_tick+1-external_first_rise)%external_period;
                for(integer i=0;i<3;i=i+1) candidate[i]=(phase<external_highs[32*i+:32]);
            end
            capture_async_i=(candidate & ~stuck_low)|stuck_high;
        end
    end
    always @(posedge clk) begin
        #1;
        if(accepted||rejected||applied||pwm_o!=prior_pwm||capture_async_i!=prior_pin||
           halted!=prior_halted||result_seq!=prior_seq) begin
            $fdisplay(event_log,"%0t,%0d,%0b,%0b,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0h",
                $time,cycle_tick,pwm_o,capture_async_i,accepted,rejected,applied,pending,
                halted,fault_code,applied_tick,deadline_tick,result_seq,active_tag);
        end
        prior_pwm=pwm_o;prior_pin=capture_async_i;prior_halted=halted;prior_seq=result_seq;
    end

    task automatic check(input logic ok,input string text);
        checks=checks+1;
        if(ok!==1'b1) begin
            $display("G05_ENGINE_AUTHOR_FAIL case=%0d tick=%0d %s fault=%0d pwm=%b",cases,cycle_tick,text,fault_code,pwm_o);
            $fatal(1,"author public-port assertion");
        end
    endtask
    task automatic tick;
        @(posedge clk);#2;
    endtask
    task automatic start_case(input string label);
        cases=cases+1;$display("G05_ENGINE_CASE %0d %s",cases,label);
        @(negedge clk);rst=1;stop=0;cfg_valid=0;fixture_mode=0;
        stuck_low=0;stuck_high=0;swap_axes=0;delay0=0;delay1=0;delay2=0;
        external_enable=1;external_first_rise=64'h7fffffffffffffff;
        repeat(2) tick();
        check(pwm_o==0&&!halted&&fault_code==0&&!result_valid&&result_seq==0,"reset clears everything");
        @(negedge clk);rst=0;tick();
        check(cfg_ready&&!running&&!pending,"reset release idle");
    endtask
    task automatic send(input logic[31:0] p,input logic[95:0] h,input logic[63:0] ttl,input logic[63:0] tag);
        @(negedge clk);cfg_period=p;cfg_highs=h;cfg_ttl_ticks=ttl;cfg_tag=tag;cfg_valid=1;
        check(cfg_ready,"send sees ready");tick();cfg_valid=0;
    endtask
    task automatic launch(input logic[31:0] p,input logic[95:0] h,input logic[63:0] ttl,
                          input logic[63:0] tag,output logic[63:0] actual_a);
        send(p,h,ttl,tag);
        check(accepted&&!rejected&&pending&&pwm_o==0,"legal command accepted while idle");
        tick();actual_a=cycle_tick;
        check(pwm_o==3'b111&&running&&!applied&&pending,"actual PWM applies one edge after acceptance");
        check(active_tag==tag,"actual application exposes command tag");
    endtask
    task automatic wait_until(input logic[63:0] target);
        while(cycle_tick<target) tick();
    endtask
    task automatic wait_record(input logic[31:0] wanted,input integer budget);
        integer spent;
        spent=0;
        while(result_seq<wanted&&!halted&&spent<budget) begin tick();spent=spent+1;end
        check(!halted&&result_valid&&result_seq>=wanted,"coherent record within bounded wait");
    endtask
    task automatic wait_fault(input logic[7:0] expected,input integer budget);
        integer spent;
        spent=0;
        while(!halted&&spent<budget)begin tick();spent=spent+1;end
        check(halted&&fault_code==expected&&!result_valid&&!pending&&!cfg_ready,"expected terminal fault");
        tick();check(pwm_o==0,"fault stops PWM no later than next edge");
    endtask
    task automatic sticky_stop(input logic[7:0] expected);
        logic[63:0] saved_deadline,saved_tag,saved_applied;
        saved_deadline=deadline_tick;saved_tag=active_tag;saved_applied=applied_tick;
        @(negedge clk);stop=1;cfg_valid=1;
        repeat(5) begin
            tick();
            check(halted&&fault_code==expected&&deadline_tick==saved_deadline&&
                  applied_tick==saved_applied&&active_tag==saved_tag&&pwm_o==0&&
                  !accepted&&!rejected&&!applied&&!result_valid,"continuous wrapper STOP preserves FIRST terminal evidence");
        end
        cfg_valid=0;
    endtask
    task automatic check_wave(input logic[63:0] origin,input logic[31:0] p,input logic[95:0] h);
        logic[63:0] phase;logic[2:0] want;
        phase=(cycle_tick-origin)%p;
        for(integer i=0;i<3;i=i+1)want[i]=phase<h[32*i+:32];
        check(pwm_o==want,"public PWM waveform phase/high counts");
    endtask
    task automatic ttl_case(input integer ttl);
        logic[63:0] a;
        start_case($sformatf("exact TTL %0d",ttl));
        launch(32,{32'd16,32'd12,32'd8},ttl,64'h1100000022,a);
        while(cycle_tick<a+ttl) begin
            if(cycle_tick>a)check(!halted&&deadline_tick==a+ttl,"no early TTL/no deadline renewal");
            check_wave(a,32,{32'd16,32'd12,32'd8});tick();
            if(cycle_tick==a+1)check(applied&&applied_tick==a&&deadline_tick==a+ttl,"applied event records prior actual edge");
        end
        check(cycle_tick==a+ttl&&halted&&fault_code==2&&pwm_o==0,"TTL stops on exact edge, no one-tick extension");
        sticky_stop(2);
    endtask
    task automatic delay_case(input integer d0,input integer d1,input integer d2,input logic good);
        logic[63:0] a;
        start_case($sformatf("independent pin delays %0d/%0d/%0d",d0,d1,d2));
        delay0=d0;delay1=d1;delay2=d2;fixture_mode=1;
        launch(40,{32'd16,32'd12,32'd8},1000,64'h2000000033,a);
        if(good)begin
            wait_record(1,160);
            check(result_periods=={32'd40,32'd40,32'd40}&&result_highs=={32'd16,32'd12,32'd8},"measured distinct channel counts");
            check(result_starts=={64'(37+d2),64'(37+d1),64'(37+d0)},"common rearm A+7 and three-FF actual start witnesses");
            check(result_ends=={64'(77+d2),64'(77+d1),64'(77+d0)},"actual end witnesses");
            check(result_tick==a+85+((d0>d1)?((d0>d2)?d0:d2):((d1>d2)?d1:d2)),"join edge follows latest synchronized closing rise");
        end else begin wait_fault(3,180);sticky_stop(3);end
    endtask
    task automatic generator_case(input integer dp,input integer dh,input logic good);
        logic[63:0] a;
        start_case($sformatf("independent count offsets period=%0d high=%0d",dp,dh));
        fixture_mode=2;external_period=40+dp;external_highs={32'(16+dh),32'(12+dh),32'(8+dh)};
        launch(40,{32'd16,32'd12,32'd8},1000,64'h3000000044,a);
        external_first_rise=a+10;
        if(good)begin
            wait_record(2,180);
            check(result_periods=={32'(40+dp),32'(40+dp),32'(40+dp)}&&result_highs==external_highs,"retain actual counts within tolerance, not requested echo");
        end else wait_fault(3,180);
    endtask

    initial begin : tests
        logic[63:0] a,b,accept_edge,expected_b,saved_deadline,first_tick;
        logic[31:0] oldseq;
        logic[191:0] oldends;
        integer n;
        mode="small";n=$value$plusargs("MODE=%s",mode);
        event_log=$fopen("public_edges.csv","w");
        $fdisplay(event_log,"time,cycle,pwm,external,accepted,rejected,applied,pending,halted,fault,applied_tick,deadline,seq,active_tag");
        if(mode=="production")begin
            start_case("production 2,000,000 period; qyaw=qpitch=0 speed_code=0 TTL=100ms candidate mapping");
            fixture_mode=1;
            launch(2000000,{32'd50000,32'd250000,32'd250000},10000000,64'h100000001,a);
            wait_record(2,6500000);
            check(result_periods=={32'd2000000,32'd2000000,32'd2000000},"production measured periods");
            check(result_highs=={32'd50000,32'd250000,32'd250000},"production frozen mapping measured widths");
            check(result_starts=={64'd3999997,64'd3999997,64'd3999997}&&
                  result_ends=={64'd5999997,64'd5999997,64'd5999997},"production second complete external frame witnesses");
            check(result_tick==a+6000005,"production actual capture edge");
            @(negedge clk);stop=1;tick();check(pwm_o==0&&halted&&fault_code==6&&!result_valid,"production explicit STOP");
        end else begin
            start_case("STOP idle terminal; reset alone clears");
            @(negedge clk);stop=1;cfg_valid=1;tick();check(halted&&fault_code==6&&pwm_o==0&&!accepted,"STOP wins simultaneous idle config");sticky_stop(6);
            for(integer k=0;k<5;k=k+1)begin
                start_case($sformatf("invalid payload %0d",k));
                case(k)
                    0:send(31,{32'd16,32'd12,32'd8},1000,1);
                    1:send(32,{32'd16,32'd12,32'd0},1000,1);
                    2:send(32,{32'd32,32'd12,32'd8},1000,1);
                    3:send(32,{32'd16,32'd12,32'd8},0,1);
                    4:send(32,{32'd16,32'd12,32'd8},64'hffffffffffffffff,1);
                endcase
                check(rejected&&!accepted&&halted&&fault_code==((k==4)?5:1)&&pwm_o==0,"invalid payload terminally rejected before output");
            end
            ttl_case(1);ttl_case(2);ttl_case(31);ttl_case(32);ttl_case(33);ttl_case(65);
            delay_case(0,0,0,1);delay_case(0,1,2,1);delay_case(2,2,2,1);delay_case(0,1,3,0);
            generator_case(2,2,1);generator_case(-2,-2,1);generator_case(3,0,0);generator_case(0,3,0);

            start_case("continuous latest result despite host inactivity");fixture_mode=1;
            launch(40,{32'd16,32'd12,32'd8},1000,64'h4000000055,a);
            wait_record(1,160);saved_deadline=deadline_tick;oldends=result_ends;oldseq=result_seq;first_tick=result_tick;
            while(result_seq<8&&!halted)begin
                tick();check(deadline_tick==saved_deadline,"capture activity never renews TTL");
                if(result_seq!=oldseq)begin
                    check(result_seq==oldseq+1&&result_starts==oldends&&result_tick==first_tick+40,"continuous frame/sequence continuity");
                    oldends=result_ends;oldseq=result_seq;first_tick=result_tick;
                end
            end
            check(result_seq==8&&!halted,"eight captures without any host handshake");

            start_case("atomic update; held busy cfg ignored; sequence across commands");fixture_mode=1;
            launch(40,{32'd16,32'd12,32'd8},1000,64'h5000000066,a);wait_record(1,160);oldseq=result_seq;
            send(48,{32'd23,32'd17,32'd11},1000,64'h6000000077);accept_edge=cycle_tick;
            expected_b=a+(((accept_edge-a)/40)+1)*40;
            check(accepted&&!result_valid&&pending,"new acceptance retires latest immediately");
            cfg_valid=1;cfg_period=99;cfg_highs=0;cfg_ttl_ticks=0;cfg_tag=0;
            while(cycle_tick<expected_b)begin check_wave(a,40,{32'd16,32'd12,32'd8});tick();check(!accepted&&!rejected,"busy config ignored");end
            cfg_valid=0;b=cycle_tick;
            check(b==expected_b&&pwm_o==7&&active_tag==64'h6000000077,"new three-channel atomic boundary");
            tick();check(applied&&applied_tick==b&&deadline_tick==b+1000,"new actual application deadline");
            repeat(55)begin check_wave(b,48,{32'd23,32'd17,32'd11});tick();end
            wait_record(oldseq+1,160);check(result_tag==64'h6000000077&&result_highs=={32'd23,32'd17,32'd11},"no old/new splice; nonwrapping seq continues");

            for(integer extra=0;extra<2;extra=extra+1)begin
                start_case($sformatf("old TTL boundary priority extra=%0d",extra));
                launch(64,{32'd24,32'd16,32'd8},64+extra,64'h7000000088,a);
                wait_until(a+18);send(64,{32'd25,32'd17,32'd9},10,64'h8000000099);
                wait_until(a+64);
                if(extra==0)begin
                    check(halted&&fault_code==2&&pwm_o==0&&active_tag==64'h7000000088,"old expiry wins same actual apply edge");
                    tick();check(!applied&&deadline_tick==a+64,"pending command never applied");
                end else begin
                    check(!halted&&pwm_o==7&&active_tag==64'h8000000099,"new application before old expiry");
                    tick();check(applied&&!halted&&applied_tick==a+64&&deadline_tick==a+74,"old deadline cannot retire already applied new command");
                    wait_until(a+74);check(halted&&fault_code==2&&pwm_o==0,"new TTL exact edge");
                end
            end

            start_case("first good capture wins exact watchdog deadline");fixture_mode=2;
            external_period=40;external_highs={32'd16,32'd12,32'd8};
            launch(40,{32'd16,32'd12,32'd8},1000,64'h90000000aa,a);
            external_first_rise=a+92;wait_until(a+136);
            check(!halted&&result_valid&&result_seq==1&&result_tick==a+136,"inclusive first deadline good capture wins");
            external_enable=0;saved_deadline=result_tick+96;
            wait_until(saved_deadline-1);check(!halted,"ongoing watchdog not early");
            tick();check(halted&&fault_code==4&&pwm_o==0&&cycle_tick==saved_deadline,"ongoing missing waveform exact watchdog edge");
            sticky_stop(4);

            for(integer stuck=0;stuck<3;stuck=stuck+1)begin
                start_case($sformatf("missing rise/fall stuck scenario %0d",stuck));fixture_mode=1;
                if(stuck==0)stuck_low=3'b001;
                if(stuck==1)stuck_high=3'b010;
                if(stuck==2)begin stuck_low=7;stuck_high=0;end
                launch(40,{32'd16,32'd12,32'd8},1000,64'ha0000000bb,a);
                // One absent channel may expose duplicate other-channel records
                // first (fault3); all-absent must reach first watchdog (fault4).
                if(stuck<2)wait_fault(3,180);else begin wait_until(a+136);check(halted&&fault_code==4,"all missing exact first watchdog");end
            end
            start_case("wrong channel wiring with distinct codes");fixture_mode=1;swap_axes=1;
            launch(40,{32'd16,32'd12,32'd8},1000,64'hb0000000cc,a);wait_fault(3,180);sticky_stop(3);

            for(integer phase=0;phase<5;phase=phase+1)begin
                start_case($sformatf("STOP phase %0d",phase));fixture_mode=1;
                if(phase==0)begin send(40,{32'd16,32'd12,32'd8},1000,64'hc0000000dd);end
                else begin
                    launch(40,{32'd16,32'd12,32'd8},1000,64'hc0000000dd,a);
                    if(phase==2)wait_until(a+20);
                    if(phase==3)wait_record(1,160);
                    if(phase==4)begin wait_until(a+12);send(48,{32'd23,32'd17,32'd11},1000,64'hd0000000ee);end
                end
                @(negedge clk);stop=1;tick();
                check(halted&&fault_code==6&&pwm_o==0&&!result_valid&&!pending,"STOP retires current phase on its edge");
                sticky_stop(6);
            end
            for(integer phase=0;phase<4;phase=phase+1)begin
                start_case($sformatf("reset phase %0d",phase));fixture_mode=1;
                if(phase==0)send(40,{32'd16,32'd12,32'd8},1000,1);
                else begin launch(40,{32'd16,32'd12,32'd8},1000,1,a);
                    if(phase==2)wait_until(a+20);if(phase==3)wait_record(1,160);end
                @(negedge clk);rst=1;stop=1;tick();
                check(!halted&&fault_code==0&&pwm_o==0&&result_seq==0&&!result_valid&&deadline_tick==0&&active_tag==0,"reset dominates STOP and clears phase");
            end
        end
        $display("G05_ENGINE_AUTHOR_DONE mode=%s cases=%0d checks=%0d failures=0",mode,cases,checks);
        $fclose(event_log);$finish;
    end
    initial begin #150000000;$fatal(1,"G05_ENGINE_AUTHOR_TIMEOUT");end
endmodule
