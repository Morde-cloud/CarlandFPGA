`timescale 1ns/1ps
module main_stream_ports;
  reg clk=0; always #5 clk=~clk;
  reg rst=1,cancel=0,cfg_valid=0,s_valid=0,meta_ready=0,m_ready=0;
  reg [7:0] cfg_count=0; reg [3:0] cfg_e=0; reg [15:0] cfg_tag=0,s_data=0; reg s_last=0;
  wire cfg_ready,s_ready,meta_valid,m_valid,m_last,meta_raw,filling;
  wire [15:0] meta_tag; wire [1:0] meta_error,level;
  wire [7:0] meta_count,m_data; wire [3:0] meta_e,meta_k;
  wire [11:0] meta_valid_bits; wire [8:0] meta_bytes;
  wire [31:0] stat_cfg,stat_samples,stat_ok,stat_error,stat_aborted;
  deepeye_block_stream dut(.*);
  integer cycle=0,events=0,stability=0,full_cycles=0;
  integer fd,logfd,scan,op,a,b,c,d,loops,mode=0,byte_limit=0,bytes_since_mode=0;
  reg [31:0] rng=32'h527ad0e9;
  reg cf,sf,hf,bf; reg [55:0] mh; reg [8:0] by;
  reg prev_hstall=0,prev_bstall=0;reg [55:0] prev_h;reg [8:0] prev_b;
  integer expected_level=0,remaining=0;reg expected_fill=0;
  reg [31:0] ec=0,es=0,eo=0,ee=0,ea=0;
  string commands_path,ports_path;
  function automatic [31:0] sat(input [31:0] x,input integer n);
    reg [32:0] wide;begin wide={1'b0,x}+n;sat=wide[32]?32'hffffffff:wide[31:0];end
  endfunction
  function automatic valid_cfg(input [7:0] n,input [3:0] e);
    valid_cfg=(n>=1&&n<=128)&&(e==0||e==1||e==2||e==4||e==8);
  endfunction
  task automatic fail(input string why);
    begin $display("MAIN_STREAM_FAIL cycle=%0d %s",cycle,why);$fdisplay(logfd,"FAIL %0d %s",cycle,why);$fatal(1,"main stream failure");end
  endtask
  always @(posedge clk) begin
    cycle=cycle+1;if(cycle>20000000)fail("watchdog");
    cf=cfg_valid&&cfg_ready;sf=s_valid&&s_ready;hf=meta_valid&&meta_ready;bf=m_valid&&m_ready;
    mh=meta_valid?{meta_tag,meta_error,meta_count,meta_e,meta_raw,meta_k,meta_valid_bits,meta_bytes}:56'd0;
    by=m_valid?{m_data,m_last}:9'd0;
    if(rst||cancel)begin
      if(cfg_ready!==0||s_ready!==0||meta_valid!==0||m_valid!==0)fail("flush handshake gating");
      prev_hstall=0;prev_bstall=0;
      if(rst)begin ec=0;es=0;eo=0;ee=0;ea=0;end
      else ea=sat(ea,expected_level);
      expected_level=0;expected_fill=0;remaining=0;
    end else begin
      if($isunknown({cfg_ready,s_ready,meta_valid,m_valid,level,filling,stat_cfg,stat_samples,stat_ok,stat_error,stat_aborted}))fail("unknown control");
      if(cfg_ready!==(!expected_fill&&expected_level<2))fail("cfg admission contract");
      if(s_ready!==expected_fill)fail("sample admission contract");
      if(level!==expected_level||filling!==expected_fill)fail("preedge occupancy/filling");
      if(meta_valid&&$isunknown(mh))fail("unknown valid metadata");
      if(m_valid&&$isunknown(by))fail("unknown valid byte");
      if(prev_hstall)begin stability=stability+1;if(!meta_valid||mh!==prev_h)fail("metadata stall instability");end
      if(prev_bstall)begin stability=stability+1;if(!m_valid||by!==prev_b)fail("byte stall instability");end
      prev_hstall=meta_valid&&!meta_ready;prev_bstall=m_valid&&!m_ready;prev_h=mh;prev_b=by;
      if(expected_level==2)full_cycles=full_cycles+1;
      if(cf)begin expected_level=expected_level+1;ec=sat(ec,1);expected_fill=valid_cfg(cfg_count,cfg_e);remaining=cfg_count;end
      if(sf)begin
        es=sat(es,1);
        if((s_last!=(remaining==1))||(remaining==1))begin expected_fill=0;remaining=0;end
        else remaining=remaining-1;
      end
      if(hf&&mh[39:38]!=0)begin expected_level=expected_level-1;ee=sat(ee,1);end
      if(bf&&by[0])begin expected_level=expected_level-1;eo=sat(eo,1);end
    end
    #1;
    if(level!==expected_level||filling!==expected_fill)fail("postedge occupancy/filling");
    if(stat_cfg!==ec||stat_samples!==es||stat_ok!==eo||stat_error!==ee||stat_aborted!==ea)fail("counter mismatch");
    if(expected_level<0||expected_level>2)fail("occupancy out of range");
    if(cf||sf||hf||bf||rst||cancel)begin
      events=events+1;
      $fdisplay(logfd,"E %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
       cycle,rst,cancel,cf,cfg_count,cfg_e,cfg_tag,sf,s_data,s_last,hf,mh[55:40],mh[39:38],mh[37:30],mh[29:26],mh[25],mh[24:21],mh[20:9],mh[8:0],bf,by[8:1],by[0],level,filling,stat_cfg,stat_samples,stat_ok,stat_error,stat_aborted);
    end
  end
  task automatic step;
    begin
      @(negedge clk);
      rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);
      case(mode)
      0:begin meta_ready=0;m_ready=0;end
      1:begin meta_ready=1;m_ready=1;end
      2:begin meta_ready=rng[0]||rng[5];m_ready=rng[2]||rng[7];end
      3:begin meta_ready=0;m_ready=1;end
      4:begin meta_ready=1;m_ready=0;end
      5:begin meta_ready=1;m_ready=rng[3];end
      6:begin meta_ready=1;m_ready=(bytes_since_mode<byte_limit);end
      default:fail("invalid consumer mode");
      endcase
      @(posedge clk);#2;if(bf)bytes_since_mode=bytes_since_mode+1;
    end
  endtask
  function automatic condition(input integer code);
    case(code)
      0:condition=(level==0);
      1:condition=meta_valid;
      2:condition=m_valid;
      3:condition=filling;
      4:condition=(level==2);
      5:condition=m_valid&&m_last;
      default:condition=0;
    endcase
  endfunction
  initial begin
    if(!$value$plusargs("COMMANDS=%s",commands_path)||!$value$plusargs("PORTS=%s",ports_path))$fatal(1,"paths missing");
    fd=$fopen(commands_path,"r");logfd=$fopen(ports_path,"w");if(!fd||!logfd)$fatal(1,"file open");
    step();rst=0;
    while(!$feof(fd))begin
      scan=$fscanf(fd,"%d %d %d %d %d\n",op,a,b,c,d);
      if(scan!=5)fail("command parse");
      cfg_valid=0;s_valid=0;
      case(op)
      0:begin rst=a;cancel=b;cfg_valid=d;s_valid=d;cfg_count=1;cfg_e=0;cfg_tag=61166;s_data=4444;s_last=1;repeat(c)step();rst=0;cancel=0;cfg_valid=0;s_valid=0;end
      1:begin cfg_count=a;cfg_e=b;cfg_tag=c;cfg_valid=1;loops=0;do begin step();loops=loops+1;if(loops>200000)fail("cfg timeout");end while(!cf);cfg_valid=0;end
      2:begin s_data=a;s_last=b;s_valid=1;loops=0;do begin step();loops=loops+1;if(loops>200000)fail("sample timeout");end while(!sf);s_valid=0;end
      3:repeat(a)step();
      4:begin mode=a;byte_limit=b;bytes_since_mode=0;end
      5:begin loops=0;while(!condition(a))begin step();loops=loops+1;if(loops>b)fail("condition timeout");end end
      6:begin cfg_count=a;cfg_e=b;cfg_tag=c;cfg_valid=1;repeat(d)step();cfg_valid=0;end
      7:begin s_data=a;s_last=b;s_valid=1;repeat(c)step();s_valid=0;end
      9:begin
        case(a)
        0:begin $deposit(dut.stat_cfg_q,b);ec=b;end
        1:begin $deposit(dut.stat_samples_q,b);es=b;end
        2:begin $deposit(dut.stat_ok_q,b);eo=b;end
        3:begin $deposit(dut.stat_error_q,b);ee=b;end
        4:begin $deposit(dut.stat_aborted_q,b);ea=b;end
        default:fail("bad seed port");
        endcase
        $fdisplay(logfd,"S %0d %0d",a,$unsigned(b));
      end
      10:begin
        if(level!=0)fail("unfinished final queue");
        $fdisplay(logfd,"PASS %0d %0d %0d %0d",cycle,events,stability,full_cycles);
        $display("MAIN_STREAM_PASS cycles=%0d events=%0d stability=%0d full=%0d",cycle,events,stability,full_cycles);
        $fclose(fd);$fclose(logfd);$finish;
      end
      default:fail("bad opcode");
      endcase
    end
    fail("missing finish command");
  end
endmodule
