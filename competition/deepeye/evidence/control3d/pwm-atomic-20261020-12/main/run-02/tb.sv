`timescale 1ns/1ps
// Independent public-port replay. No DUT hierarchy references or author oracle.
// DEEPEYE-IMPLEMENTATION-20261014/v1, B-DEEPEYE-PWM-ATOMIC-20261020-12.
module main_tb_atomic_pwm;
  parameter COUNT_W=3, TAG_W=64;
  reg clk=0; always #5 clk=~clk;
  reg rst=1,stop=0,cfg_valid=0;
  reg [COUNT_W-1:0] cfg_period=0,cfg_high_yaw=0,cfg_high_pitch=0,cfg_high_speed=0;
  reg [TAG_W-1:0] cfg_tag=0;
  wire cfg_ready,accepted,rejected,applied,frame_start,running,pending;
  wire [2:0] pwm;
  wire [COUNT_W-1:0] active_period,active_high_yaw,active_high_pitch,active_high_speed;
  wire [TAG_W-1:0] active_tag;
  deepeye_atomic_pwm #(.COUNT_W(COUNT_W),.TAG_W(TAG_W)) dut(.*);
  reg [63:0] v[0:21]; reg [63:0] got[0:21];
  string vectors,tracepath; integer fd,logfd,n,i,j,k,count;
  initial begin
    if (!$value$plusargs("VECTORS=%s",vectors) || !$value$plusargs("TRACE=%s",tracepath)) $fatal(1,"missing paths");
    fd=$fopen(vectors,"r"); logfd=$fopen(tracepath,"w");
    if(!fd || !logfd) $fatal(1,"open failed");
    count=$fscanf(fd,"%d\n",n); if(count!=1 || n<1) $fatal(1,"bad count");
    // Bootstrap synchronous reset independently of vector content.
    @(posedge clk); #1;
    for(i=0;i<n;i=i+1) begin
      for(j=0;j<22;j=j+1) begin
        count=$fscanf(fd,"%h",v[j]); if(count!=1) $fatal(1,"short vector %0d %0d",i,j);
      end
      @(negedge clk);
      rst=v[0];stop=v[1];cfg_valid=v[2];cfg_period=v[3];
      cfg_high_yaw=v[4];cfg_high_pitch=v[5];cfg_high_speed=v[6];cfg_tag=v[7];
      #1;got[8]=cfg_ready;
      if(got[8]!==v[8]) $fatal(1,"ready pre row=%0d got=%h expected=%h",i,got[8],v[8]);
      @(posedge clk);#1;
      got[9]=cfg_ready;got[10]=accepted;got[11]=rejected;got[12]=applied;got[13]=frame_start;
      got[14]=running;got[15]=pending;got[16]=pwm;got[17]=active_period;got[18]=active_high_yaw;
      got[19]=active_high_pitch;got[20]=active_high_speed;got[21]=active_tag;
      $fwrite(logfd,"%0d",i);
      for(j=8;j<22;j=j+1) begin
        $fwrite(logfd," %h",got[j]);
        if(got[j]!==v[j]) begin
          $fwrite(logfd," FAIL expected=%h field=%0d\n",v[j],j);$fflush(logfd);
          $fatal(1,"row=%0d field=%0d got=%h expected=%h",i,j,got[j],v[j]);
        end
      end
      $fwrite(logfd,"\n");
    end
    $fclose(fd);$fclose(logfd);
    $display("MAIN_PWM_PASS rows=%0d COUNT_W=%0d TAG_W=%0d",n,COUNT_W,TAG_W);$finish;
  end
endmodule

module main_tb_atomic_pwm_long;
  reg clk=0;always #5 clk=~clk;
  reg rst=1,stop=0,cfg_valid=0;
  reg [31:0] cfg_period=0,cfg_high_yaw=0,cfg_high_pitch=0,cfg_high_speed=0,cfg_tag=0;
  wire cfg_ready,accepted,rejected,applied,frame_start,running,pending;
  wire [2:0] pwm;
  wire [31:0] active_period,active_high_yaw,active_high_pitch,active_high_speed,active_tag;
  deepeye_atomic_pwm dut(.*);
  integer i,y,p,s;
  task edge_step;
    begin @(posedge clk);#1;end
  endtask
  initial begin
    edge_step();@(negedge clk);rst=0;cfg_valid=1;
    cfg_period=2000000;cfg_high_yaw=10000;cfg_high_pitch=490000;cfg_high_speed=70000;cfg_tag=32'hfedcba98;
    edge_step();if(!accepted || running || !pending) $fatal(1,"long admission");
    @(negedge clk);cfg_valid=0;edge_step();
    if(!applied || !frame_start || !running) $fatal(1,"long apply");
    y=0;p=0;s=0;
    for(i=0;i<2000000;i=i+1) begin
      if(i>0) begin
        @(negedge clk);
        cfg_valid=(i==1000000);
        if(cfg_valid) begin cfg_period=37;cfg_high_yaw=37;cfg_high_pitch=0;cfg_high_speed=17;cfg_tag=32'h87654321;end
        edge_step();
      end
      if(pwm[0] !== (i<10000) || pwm[1] !== (i<490000) || pwm[2] !== (i<70000)) $fatal(1,"long waveform row=%0d",i);
      if(active_period!==32'd2000000 || active_high_yaw!==32'd10000 || active_high_pitch!==32'd490000 || active_high_speed!==32'd70000 || active_tag!==32'hfedcba98) $fatal(1,"partial active update row=%0d",i);
      if(frame_start !== (i==0) || applied !== (i==0)) $fatal(1,"early wrap row=%0d",i);
      if(accepted !== (i==1000000) || rejected) $fatal(1,"accept row=%0d",i);
      y=y+pwm[0];p=p+pwm[1];s=s+pwm[2];
    end
    if(y!=10000 || p!=490000 || s!=70000) $fatal(1,"long totals");
    @(negedge clk);cfg_valid=0;edge_step();
    if(!applied || !frame_start || active_period!==32'd37 || active_high_yaw!==32'd37 || active_high_pitch!==32'd0 || active_high_speed!==32'd17 || active_tag!==32'h87654321) $fatal(1,"boundary tuple");
    for(i=0;i<74;i=i+1) begin
      if(i>0) edge_step();
      if(pwm[0]!==1'b1 || pwm[1]!==1'b0 || pwm[2] !== ((i%37)<17) || frame_start !== ((i%37)==0)) $fatal(1,"new frame row=%0d",i);
    end
    @(negedge clk);stop=1;cfg_valid=1;edge_step();
    if(running || pending || pwm || applied || accepted || rejected || frame_start || active_period || active_tag) $fatal(1,"stop priority");
    @(negedge clk);stop=0;cfg_valid=0;edge_step();if(running || pwm) $fatal(1,"stale resume");
    $display("MAIN_PWM_LONG_PASS full_period=2000000 high_counts=%0d,%0d,%0d new_period=37 new_frames=2",y,p,s);$finish;
  end
endmodule
