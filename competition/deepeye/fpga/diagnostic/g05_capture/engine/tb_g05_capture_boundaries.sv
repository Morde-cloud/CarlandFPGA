`timescale 1ns/1ps
// Additional NEW public-port controls for wide arithmetic and a missing frame.
// No private hierarchy access, force, shortened DUT widths or old tests.
module tb_g05_capture_boundaries;
    logic clk=0,rst=1,stop=0,cfg_valid=0,cfg_ready;
    logic[31:0] cfg_period=32;
    logic[95:0] cfg_highs={32'd16,32'd12,32'd8};
    logic[63:0] cfg_ttl_ticks=1000,cfg_tag=64'h2200000033;
    logic[2:0] capture_async_i=0,pwm_o;
    logic accepted,rejected,applied,running,pending,halted;
    logic[7:0] fault_code;
    logic[63:0] cycle_tick,applied_tick,deadline_tick,active_tag;
    logic result_valid;
    logic[31:0] result_seq;
    logic[63:0] result_tag,result_tick;
    logic[95:0] result_periods,result_highs;
    logic[191:0] result_starts,result_ends;
    logic[2:0] mask=7;
    integer checks=0,cases=0;
    deepeye_g05_capture_engine dut(.*);
    always #5 clk=~clk;
    always @(negedge clk)capture_async_i=rst?3'b0:(pwm_o&mask);
    task automatic tick;@(posedge clk);#2;endtask
    task automatic check(input logic ok,input string msg);
        checks++;
        if(ok!==1'b1)begin $display("G05_ENGINE_AUTHOR_FAIL boundary=%0d tick=%0d %s",cases,cycle_tick,msg);$fatal(1,"boundary assertion");end
    endtask
    task automatic reset_case;
        cases++;@(negedge clk);rst=1;stop=0;cfg_valid=0;mask=7;repeat(2)tick();
        @(negedge clk);rst=0;tick();
    endtask
    task automatic launch(input logic[31:0] p,input logic[95:0] h,input logic[63:0] ttl,output logic[63:0] a);
        @(negedge clk);cfg_period=p;cfg_highs=h;cfg_ttl_ticks=ttl;cfg_valid=1;tick();cfg_valid=0;
        check(accepted&&!rejected,"count command accepted");tick();a=cycle_tick;
        check(pwm_o==7&&running,"actual application edge");
    endtask
    initial begin
        logic[63:0] a;
        integer budget;
        reset_case();mask=0;
        // 3*0x55555551+16 = 0x100000003. A 32-bit watchdog wraps to3;
        // the correct wide first deadline remains beyond this TTL20 window.
        launch(32'h55555551,{32'd16,32'd12,32'd8},20,a);
        while(cycle_tick<a+20)begin check(!halted,"wide first watchdog must not wrap to3");tick();end
        check(halted&&fault_code==2&&pwm_o==0&&deadline_tick==a+20,"TTL20 wins, no wrapped watchdog");

        reset_case();launch(32,{32'd31,32'd16,32'd1},1000,a);budget=0;
        while(result_seq<2&&!halted&&budget<200)begin tick();budget++;end
        check(!halted&&result_valid&&result_seq==2,"minimum/maximum nonconstant highs capture");
        check(result_periods=={32'd32,32'd32,32'd32}&&result_highs=={32'd31,32'd16,32'd1},"actual boundary widths retained");

        reset_case();launch(40,{32'd16,32'd12,32'd8},1000,a);budget=0;
        while(result_seq<1&&!halted&&budget<200)begin tick();budget++;end
        check(result_valid&&!halted&&result_seq==1,"first coherent frame before missing-frame control");
        while(cycle_tick<a+100)tick();mask=3'b110;
        // Suppress only yaw's next rising edge; restore before the following
        // frame. Other channels continue, so a join must never splice frames.
        while(cycle_tick<a+150&&!halted)tick();mask=3'b111;
        budget=0;
        while(!halted&&budget<80)begin tick();budget++;end
        check(halted&&fault_code==3&&!result_valid&&result_seq==1,"missing whole frame rejects rather than joining adjacent frames");
        tick();check(pwm_o==0,"wrong-frame terminal output stop");
        $display("G05_ENGINE_AUTHOR_DONE mode=boundary cases=%0d checks=%0d failures=0",cases,checks);$finish;
    end
    initial begin #100000;$fatal(1,"boundary controls timeout");end
endmodule
