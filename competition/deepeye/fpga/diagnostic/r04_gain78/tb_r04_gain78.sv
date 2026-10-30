`timescale 1ns/1ps
// NEW78 SYNTHETIC digital pin observations only. No analog device model/SO.
module tb_r04_gain78;
    logic clk=0; always #5 clk=~clk;
    logic rst=1,enable=0,cancel=0,cmd_valid=0,result_ready=0;
    logic [2:0] gain_code=0; logic [31:0] tag=0;
    wire cmd_ready,accepted,aborted,result_valid,result_error,spi_cs_n,spi_sck,spi_si;
    wire [31:0] result_tag;
    deepeye_mcp6s21_write_candidate dut(.*);
    integer completion_status=0,fd,cycle=0,edges=0,frames=0,accepts=0,aborts=0,checks=0;
    integer negative=0,case_id=0,cs_fall=0,cs_rise=0,sck_edge=0,si_edge=0;
    bit previous_cs=1,previous_sck=0,previous_si=0,normal_expected=0;
    logic [15:0] observed=0,expected_word=0;
    string out;
    task automatic ck(input bit okay,input string why);
        checks++; if(!okay)begin $fdisplay(fd,"FAIL,%0d,%s",cycle,why);$fflush(fd);$fatal(1,"R04_NEW78 %s",why);end
    endtask
    always @(posedge clk)begin
        #1; cycle++;
        if(fd)begin
            ck(!(rst&&cmd_ready),"ready during reset");
            ck(!((cancel||!enable)&&cmd_ready),"ready during cancelled/disabled gate");
            if(accepted)begin accepts++;$fdisplay(fd,"ACCEPTED,%0d,%0d,%0d",case_id,cycle,tag);end
            if(aborted)begin aborts++;$fdisplay(fd,"ABORT,%0d,%0d",case_id,cycle);end
            if(previous_cs&&!spi_cs_n)begin
                ck(!spi_sck,"clock high at CS fall");ck(cycle-cs_rise>=100,"CS high guard");
                cs_fall=cycle;edges=0;observed=0;$fdisplay(fd,"CS_LOW,%0d,%0d",case_id,cycle);
            end
            if(!previous_sck&&spi_sck)begin
                ck(!spi_cs_n,"SCK rise outside CS");ck(cycle-(edges==0?cs_fall:sck_edge)>=100,"SCK low/setup");
                ck(cycle-si_edge>=4,"SI setup below40ns");
                observed={observed[14:0],spi_si};edges++;
                $fdisplay(fd,"RISE,%0d,%0d,%0d,%0d",case_id,cycle,edges,spi_si);
            end
            if(previous_sck&&!spi_sck&&!rst&&!cancel&&enable)ck(cycle-sck_edge>=100,"SCK high below1us");
            if(previous_sck!=spi_sck)sck_edge=cycle;
            if(previous_si!=spi_si)begin ck(!spi_sck,"SI changed with SCK high");si_edge=cycle;end
            if(!previous_cs&&spi_cs_n)begin
                frames++;cs_rise=cycle;
                $fdisplay(fd,"FRAME,%0d,%0d,%0d,%0d,%0d",case_id,cycle,edges,observed,normal_expected);
                if(normal_expected)begin
                    ck(edges==16,"normal frame clock count");ck(cycle-sck_edge>=100,"last SCK to CS hold");
                    ck(observed==(negative?expected_word^16'd1:expected_word),"independent pin byte oracle");
                end
            end
            previous_cs=spi_cs_n;previous_sck=spi_sck;previous_si=spi_si;
            if(cycle>180000)$fatal(1,"R04_NEW78 cycle deadline");
        end
    end
    task automatic clocks(input integer n);repeat(n)@(negedge clk);endtask
    task automatic ready;
        integer n;n=0;while(!cmd_ready&&n<5000)begin clocks(1);n++;end
        ck(cmd_ready,"bounded command ready");
    endtask
    task automatic issue(input integer code,input integer identity,input bit normal);
        ready();case_id=identity;gain_code=code;tag=identity;expected_word=16'h4000|code;
        normal_expected=normal;cmd_valid=1;clocks(1);cmd_valid=0;
    endtask
    task automatic result_check(input bit error,input integer identity);
        integer n;logic [31:0] held_tag;bit held_error;
        n=0;while(!result_valid&&n<5000)begin clocks(1);n++;end
        ck(result_valid&&result_error==error&&result_tag==identity,"result identity/error");
        held_tag=result_tag;held_error=result_error;
        repeat(9)begin clocks(1);ck(result_valid&&result_tag==held_tag&&result_error==held_error&&!cmd_ready,"held result stability");end
        $fdisplay(fd,"RESULT,%0d,%0d,%0d,%0d",case_id,cycle,result_error,result_tag);
        result_ready=1;clocks(1);result_ready=0;clocks(1);
        ck(!result_valid,"result handshake retirement");normal_expected=0;
    endtask
    integer code,old_frames,old_accepts;
    initial begin
        if(!$value$plusargs("OUT=%s",out))$fatal(1,"OUT required");
        code=$value$plusargs("NEGATIVE=%d",negative);fd=$fopen(out,"w");if(!fd)$fatal(1,"open");
        clocks(4);enable=1;cmd_valid=1;clocks(3);ck(!accepted&&!cmd_ready,"reset request not accepted");cmd_valid=0;rst=0;ready();
        issue(0,100,1);result_check(0,100);
        issue(1,101,1);result_check(0,101);
        issue(2,102,1);result_check(0,102);
        issue(4,104,1);result_check(0,104);
        for(code=3;code<=7;code++)if(code!=4)begin
            old_frames=frames;old_accepts=accepts;issue(code,200+code,0);result_check(1,200+code);
            ck(frames==old_frames&&accepts==old_accepts&&spi_cs_n&&!spi_sck,"illegal code emitted frame");
        end
        // New explicit requests, cancellation at three distinct native phases.
        issue(2,301,0);clocks(10);cancel=1;clocks(1);result_check(1,301);cancel=0;ready();
        issue(4,302,0);while(edges<7)clocks(1);cancel=1;clocks(1);result_check(1,302);cancel=0;ready();
        issue(1,303,0);while(edges<16||spi_sck)clocks(1);cancel=1;clocks(1);result_check(1,303);cancel=0;ready();
        issue(2,304,0);while(edges<4)clocks(1);enable=0;clocks(1);result_check(1,304);enable=1;ready();
        issue(4,305,0);while(edges<3)clocks(1);old_accepts=accepts;rst=1;clocks(2);
        ck(spi_cs_n&&!spi_sck&&!spi_si&&!result_valid&&result_tag==0,"destructive reset safe/unavailable tag");
        rst=0;ready();clocks(500);ck(accepts==old_accepts,"reset automatically replayed");
        ck(aborts==5,"cancel/disable/reset abort count");
        $fdisplay(fd,"DONE,%0d,%0d,%0d,%0d",cycle,frames,accepts,checks);$fclose(fd);fd=0;
        completion_status=1;$display("R04_NEW78_PASS cycles=%0d",cycle);$finish;
    end
    initial begin #2000000;$fatal(1,"R04_NEW78 wall simulation bound");end
endmodule
