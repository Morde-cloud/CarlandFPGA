`timescale 1ns/1ps
module smoke;
reg done=0;
initial begin #5; done=1; $display("SMOKE_EXECUTED"); end
endmodule
module negative;
reg done=0;
initial begin #5; $fatal(1,"EXPECTED_NEGATIVE_CONTROL"); end
endmodule
