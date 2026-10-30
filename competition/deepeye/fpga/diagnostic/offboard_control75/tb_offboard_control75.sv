`timescale 1ns/1ps
// SYNTHETIC_FIXTURE only. Actual unchanged mapper/AXI/engine/capture, 50MHz.
// External fixture mirrors public output pins on the falling edge. No force,
// internal drive, stubs, clock/period override, or production wrapper activation.
module tb_offboard_control75;
    logic s_axi_aclk=0; always #10 s_axi_aclk=~s_axi_aclk;
    logic s_axi_aresetn=0;
    logic [11:0] s_axi_awaddr=0,s_axi_araddr=0;
    logic [2:0] s_axi_awprot=0,s_axi_arprot=0;
    logic s_axi_awvalid=0,s_axi_wvalid=0,s_axi_bready=0,s_axi_arvalid=0,s_axi_rready=0;
    logic [31:0] s_axi_wdata=0; logic [3:0] s_axi_wstrb=15;
    wire s_axi_awready,s_axi_wready,s_axi_bvalid,s_axi_arready,s_axi_rvalid;
    wire [1:0] s_axi_bresp,s_axi_rresp; wire [31:0] s_axi_rdata;
    wire g05_50_candidate_yaw_pwm_o,g05_50_candidate_pitch_pwm_o,g05_50_candidate_speed_pwm_o;
    logic g05_50_candidate_yaw_capture_i=0,g05_50_candidate_pitch_capture_i=0,g05_50_candidate_speed_capture_i=0;
    wire [2:0] pwm={g05_50_candidate_speed_pwm_o,g05_50_candidate_pitch_pwm_o,g05_50_candidate_yaw_pwm_o};
    deepeye_g05_axi_50mhz_candidate dut(.*);
    integer completion_status=0,raw,stim,code,op,a,b,c,lines=0,assertions=0;
    integer negative=0; longint unsigned total=0;
    string stim_path,trace_path;
    task automatic ck(input bit ok,input string why);
        assertions++;
        if(!ok)begin $fdisplay(raw,"FAIL,%s",why);$fflush(raw);$fatal(1,"B75_FAIL %s",why);end
    endtask
    always @(negedge s_axi_aclk)begin
        {g05_50_candidate_speed_capture_i,g05_50_candidate_pitch_capture_i,g05_50_candidate_yaw_capture_i}=s_axi_aresetn?pwm:3'b0;
    end
    // These are observation-only internal event taps, accompanied by actual
    // public readback. No internal signal is driven by the fixture.
    always @(posedge s_axi_aclk)begin
        total<=total+1;
        #1;
        if(raw && s_axi_aresetn)begin
            if(dut.eng_accepted)$fdisplay(raw,"ACCEPTED,%0d,%0d,%0d",dut.cycle_tick,dut.cfg_tag[63:32],dut.cfg_tag[31:0]);
            if(dut.eng_applied)$fdisplay(raw,"APPLIED,%0d,%0d,%0d,%0d",dut.applied_tick,dut.deadline_tick,dut.active_tag[63:32],dut.active_tag[31:0]);
        end
        if(total>6000000)$fatal(1,"B75 cycle bound");
    end
    always @(pwm)if(raw)$fdisplay(raw,"PWM,%0d,%0d",$time,pwm);
    task automatic wr(input logic[11:0] address,input logic[31:0] value,input integer resp);
        integer n;
        @(negedge s_axi_aclk);s_axi_awaddr=address;s_axi_wdata=value;s_axi_awvalid=1;s_axi_wvalid=1;
        @(posedge s_axi_aclk);ck(s_axi_awready&&s_axi_wready,"AXI write ready");
        @(negedge s_axi_aclk);s_axi_awvalid=0;s_axi_wvalid=0;
        n=0;while(!s_axi_bvalid&&n<20)begin @(negedge s_axi_aclk);n++;end
        ck(s_axi_bvalid&&s_axi_bresp==resp,"AXI write response");
        $fdisplay(raw,"WRITE,%0d,%0d,%0d",address,value,s_axi_bresp);
        s_axi_bready=1;@(negedge s_axi_aclk);s_axi_bready=0;
    endtask
    task automatic rd(input logic[11:0] address,input integer resp);
        integer n;
        @(negedge s_axi_aclk);s_axi_araddr=address;s_axi_arvalid=1;
        @(posedge s_axi_aclk);ck(s_axi_arready,"AXI read ready");
        @(negedge s_axi_aclk);s_axi_arvalid=0;
        n=0;while(!s_axi_rvalid&&n<20)begin @(negedge s_axi_aclk);n++;end
        ck(s_axi_rvalid&&s_axi_rresp==resp,"AXI read response");
        if(address==0)ck(s_axi_rdata==(negative?32'h0:32'h47303550),"actual G05P magic oracle");
        $fdisplay(raw,"READ,%0d,%0d,%0d",address,s_axi_rdata,s_axi_rresp);
        s_axi_rready=1;@(negedge s_axi_aclk);s_axi_rready=0;
    endtask
    initial begin
        if(!$value$plusargs("STIM=%s",stim_path))$fatal(1,"missing STIM");
        if(!$value$plusargs("TRACE=%s",trace_path))$fatal(1,"missing TRACE");
        code=$value$plusargs("NEGATIVE=%d",negative);
        raw=$fopen(trace_path,"w");stim=$fopen(stim_path,"r");
        if(!raw||!stim)$fatal(1,"fixture open failure");
        repeat(5)@(negedge s_axi_aclk);s_axi_aresetn=1;repeat(4)@(negedge s_axi_aclk);
        while(!$feof(stim))begin
            code=$fscanf(stim,"%d %d %d %d\n",op,a,b,c);
            ck(code==4,"stimulus parse");lines++;ck(lines<=512,"bounded stimulus");
            case(op)
                0:wr(a,b,c);
                1:rd(a,c);
                2:begin ck(a>=0&&a<=5000000,"finite wait");repeat(a)@(negedge s_axi_aclk);end
                3:$fdisplay(raw,"PINS,%0d,%0d",dut.cycle_tick,pwm);
                default:ck(0,"unknown stimulus opcode");
            endcase
        end
        ck(lines>0,"nonempty test");
        $fdisplay(raw,"END,%0d,%0d",lines,assertions);$fclose(stim);$fclose(raw);raw=0;
        completion_status=1;$display("B75_PASS lines=%0d assertions=%0d",lines,assertions);$finish;
    end
    initial begin #120000200; $fatal(1,"B75 simulation deadline");end
endmodule
