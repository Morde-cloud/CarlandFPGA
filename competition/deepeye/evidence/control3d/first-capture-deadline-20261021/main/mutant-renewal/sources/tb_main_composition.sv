
module tb_main_composition;
logic clk=0,rst=1,stop=0,cfg_valid=0,out_ready=0;
logic [3:0] cfg_period=2,cfg_high_yaw=1,cfg_high_pitch=1,cfg_high_speed=1,cfg_tag=3;
logic [2:0] sample_levels=0;
wire cfg_ready,accepted,rejected,applied,frame_start,running,pending;
wire [2:0] pwm;
wire [3:0] active_period,active_high_yaw,active_high_pitch,active_high_speed,active_tag;
wire window_active,window_started,capture_armed,out_valid;
wire [3:0] out_period,out_high0,out_high1,out_high2,out_tag;
wire [7:0] out_start,out_end;
wire [3:0] expected_period,expected_high0,expected_high1,expected_high2,expected_tag;
wire [3:0] raw_fault_events;
wire failure_event;wire[2:0] failure_code;
deepeye_pwm_applied_capture #(.COUNT_W(4),.WITNESS_W(8),.TAG_W(4)) source_dut(.*);
wire start=window_started;
wire observed=out_valid;
wire cancel=stop || (cfg_valid && cfg_ready) || pending || !running ||
            !window_active || failure_event || (|raw_fault_events);
logic [5:0] budget_cycles=0;
wire waiting,completed,expired,invalid_request;
wire started_event,completed_event,expired_event,invalid_request_event;
wire[7:0] flags={invalid_request_event,expired_event,completed_event,started_event,
                invalid_request,expired,completed,waiting};
deepeye_first_capture_deadline #(.BUDGET_W(6)) monitor(.*);
always #5 clk=~clk;
integer fd,scan,idx,mask,budget,levels,ready,count=0;
integer pre_start,pre_obs,pre_cancel,pre_fault,pre_valid,pre_wa,pre_pending,pre_running;
reg[4095:0] filename;
initial begin
 if(!$value$plusargs("VECTORS=%s",filename))$fatal(1,"MAIN_NO_INPUT");
 fd=$fopen(filename,"r");if(!fd)$fatal(1,"MAIN_OPEN_FAILED");
 while(!$feof(fd))begin
  scan=$fscanf(fd,"%d %h %h %h %h\n",idx,mask,budget,levels,ready);
  if(scan!=5)$fatal(1,"MAIN_BAD_INPUT");
  @(negedge clk);rst=mask[0];stop=mask[1];cfg_valid=mask[2];
  budget_cycles=budget;sample_levels=levels;out_ready=ready;
  #1;pre_start=start;pre_obs=observed;pre_cancel=cancel;
  pre_fault=raw_fault_events;pre_valid=out_valid;pre_wa=window_active;
  pre_pending=pending;pre_running=running;
  @(posedge clk);#1;
  $display("COMP_ROW %0d %0h %0h %0h %0h %0d %0d %0d %0h %0d %0d %0d %0d %02h %0d %0d %0h %0d %0d %0h %0h %0h %0h",
   idx,mask,budget,levels,ready,pre_start,pre_obs,pre_cancel,pre_fault,pre_valid,
   pre_wa,pre_pending,pre_running,flags,out_valid,window_active,raw_fault_events,
   failure_event,window_started,out_period,out_high0,out_high1,out_high2);
  count=count+1;
 end
 $fclose(fd);$display("COMP_DONE rows=%0d",count);$finish;
end
endmodule
