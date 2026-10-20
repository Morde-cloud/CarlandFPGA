
module tb_main_deadline;
parameter integer BUDGET_W=5;
logic clk=0,rst=1,cancel=0,start=0,observed=0;
logic [BUDGET_W-1:0] budget_cycles=0;
wire waiting,completed,expired,invalid_request;
wire started_event,completed_event,expired_event,invalid_request_event;
wire [7:0] flags={invalid_request_event,expired_event,completed_event,started_event,
                 invalid_request,expired,completed,waiting};
deepeye_first_capture_deadline #(.BUDGET_W(BUDGET_W)) dut(.*);
always #5 clk=~clk;
integer fd,scan,idx,mask,budget,count=0;reg[4095:0] filename;
initial begin
 if(!$value$plusargs("VECTORS=%s",filename)) $fatal(1,"MAIN_NO_INPUT");
 fd=$fopen(filename,"r");if(!fd)$fatal(1,"MAIN_OPEN_FAILED");
 while(!$feof(fd))begin
  scan=$fscanf(fd,"%d %h %h\n",idx,mask,budget);
  if(scan!=3)$fatal(1,"MAIN_BAD_INPUT");
  @(negedge clk);{observed,start,cancel,rst}=mask[3:0];budget_cycles=budget;
  @(posedge clk);#1;
  $display("MAIN_ROW %0d %0h %0h %02h",idx,mask,budget,flags);count=count+1;
 end
 $fclose(fd);$display("MAIN_DONE rows=%0d",count);$finish;
end
endmodule
