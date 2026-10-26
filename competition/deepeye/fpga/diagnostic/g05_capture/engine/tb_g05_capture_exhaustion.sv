`timescale 1ns/1ps
// SEPARATE FAULT-INJECTION BENCH. Forced exhaustion states are not claimed as
// naturally reached through public ports. All ensuing observations are public.
module tb_g05_capture_exhaustion;
    logic clk=0,rst=1,stop=0,cfg_valid=0,cfg_ready;
    logic[31:0] cfg_period=32;
    logic[95:0] cfg_highs={32'd16,32'd12,32'd8};
    logic[63:0] cfg_ttl_ticks=1000,cfg_tag=64'h1100000022;
    logic[2:0] capture_async_i=0,pwm_o;
    logic accepted,rejected,applied,running,pending,halted;
    logic[7:0] fault_code;
    logic[63:0] cycle_tick,applied_tick,deadline_tick,active_tag;
    logic result_valid;
    logic[31:0] result_seq;
    logic[63:0] result_tag,result_tick;
    logic[95:0] result_periods,result_highs;
    logic[191:0] result_starts,result_ends;
    integer checks=0,cases=0;
    deepeye_g05_capture_engine dut(.*);
    always #5 clk=~clk;
    always @(negedge clk) capture_async_i=rst?3'b0:pwm_o;
    task automatic tick;@(posedge clk);#2;endtask
    task automatic check(input logic ok,input string msg);
        checks++;
        if(ok!==1'b1)begin $display("G05_EXHAUSTION_FAIL %s",msg);$fatal(1,"injection check");end
    endtask
    task automatic reset_case;
        cases++;@(negedge clk);rst=1;cfg_valid=0;stop=0;repeat(2)tick();
        @(negedge clk);rst=0;tick();
    endtask
    initial begin
        $display("G05_EXHAUSTION_DISCLOSURE forced cycle_tick/result_seq, not public reachability proof");
        reset_case();
        @(negedge clk);force dut.cycle_tick=64'hffffffffffffffff;#1;release dut.cycle_tick;
        tick();check(halted&&fault_code==5&&cycle_tick==64'hffffffffffffffff&&pwm_o==0,"cycle exhaustion saturates and stops");
        repeat(3)tick();check(cycle_tick==64'hffffffffffffffff&&fault_code==5,"no cycle wrap");

        reset_case();
        @(negedge clk);force dut.cycle_tick=64'hffffffffffffff9b;#1;release dut.cycle_tick;
        cfg_ttl_ticks=1;cfg_valid=1;tick();cfg_valid=0;
        check(rejected&&halted&&fault_code==5&&pwm_o==0,"checked first watchdog addition near TMAX");

        reset_case();cfg_ttl_ticks=1000;
        @(negedge clk);cfg_valid=1;tick();cfg_valid=0;
        while(result_seq!=1&&!halted)tick();check(result_valid&&!halted,"ordinary first record before injection");
        @(negedge clk);force dut.result_seq=32'hfffffffe;#1;release dut.result_seq;
        while(result_seq!=32'hffffffff&&!halted)tick();
        check(result_seq==32'hffffffff&&result_valid&&!halted,"last representable sequence remains legal");
        while(!halted)tick();check(fault_code==5&&!result_valid&&result_seq==32'hffffffff,"next record retires without sequence wrap");
        tick();check(pwm_o==0,"exhaustion stops PWM");
        $display("G05_ENGINE_AUTHOR_DONE mode=fault_injection cases=%0d checks=%0d failures=0",cases,checks);$finish;
    end
    initial begin #100000;$fatal(1,"G05_EXHAUSTION_TIMEOUT");end
endmodule
