`timescale 1ns/1ps
// Public AXI only: no hierarchy, force, bind, or dependency modification.
module tb_private_axi_diag;
    logic s_axi_aclk=0;
    always #5 s_axi_aclk=~s_axi_aclk;
    logic s_axi_aresetn=0;
    logic [11:0] s_axi_awaddr=0, s_axi_araddr=0;
    logic [2:0] s_axi_awprot=0, s_axi_arprot=0;
    logic s_axi_awvalid=0, s_axi_awready, s_axi_wvalid=0, s_axi_wready;
    logic [31:0] s_axi_wdata=0;
    logic [3:0] s_axi_wstrb=0;
    logic [1:0] s_axi_bresp, s_axi_rresp;
    logic s_axi_bvalid, s_axi_bready=0, s_axi_arvalid=0, s_axi_arready;
    logic [31:0] s_axi_rdata;
    logic s_axi_rvalid, s_axi_rready=0;
    deepeye_private_axi_diag dut (.*);

    string run_id;
    integer seed, negative=0;
    logic [31:0] rng;
    integer checks=0, writes=0, reads=0, records=0, cases=0;
    integer aw_pending=0, w_pending=0, ar_pending=0;
    bit b_stalled=0, r_stalled=0;
    logic [1:0] saved_bresp, saved_rresp;
    logic [31:0] saved_rdata;
    logic [31:0] words [0:12];
    logic [15:0] expected_data [0:3];
    logic [63:0] expected_ticks [0:3];
    logic [7:0] expected_quality [0:3];

    function automatic logic [31:0] draw();
        rng=rng^(rng<<13); rng=rng^(rng>>17); rng=rng^(rng<<5);
        draw=rng;
    endfunction
    task automatic check(input bit condition, input string message);
        if (!condition) begin
            $display("DIAG53_FAIL run=%s check=%0d message=%s",run_id,checks,message);
            $fatal(1,"private AXI diagnostic check failed");
        end
        checks=checks+1;
    endtask
    task automatic begin_case(input string label_text);
        cases=cases+1;
        $display("DIAG53_CASE run=%s index=%0d name=%s",run_id,cases,label_text);
    endtask

    // Passive checks sample interface handshakes at the clock edge.
    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            aw_pending=0; w_pending=0; ar_pending=0; b_stalled=0; r_stalled=0;
        end else begin
            if (b_stalled) check(s_axi_bvalid && s_axi_bresp===saved_bresp,"B stable under backpressure");
            if (r_stalled) check(s_axi_rvalid && s_axi_rdata===saved_rdata && s_axi_rresp===saved_rresp,"R stable under backpressure");
            b_stalled=s_axi_bvalid && !s_axi_bready;
            r_stalled=s_axi_rvalid && !s_axi_rready;
            saved_bresp=s_axi_bresp; saved_rdata=s_axi_rdata; saved_rresp=s_axi_rresp;
            if (s_axi_awvalid && s_axi_awready) aw_pending=aw_pending+1;
            if (s_axi_wvalid && s_axi_wready) w_pending=w_pending+1;
            if (s_axi_arvalid && s_axi_arready) ar_pending=ar_pending+1;
            if (s_axi_bvalid && s_axi_bready) begin
                check(aw_pending==1 && w_pending==1,"one B per complete AW/W pair");
                aw_pending=aw_pending-1; w_pending=w_pending-1; writes=writes+1;
            end
            if (s_axi_rvalid && s_axi_rready) begin
                check(ar_pending==1,"one R per AR"); ar_pending=ar_pending-1; reads=reads+1;
            end
            check(aw_pending<=1 && w_pending<=1 && ar_pending<=1,"single outstanding limits");
        end
    end

    task automatic reset_bus();
        @(negedge s_axi_aclk);
        s_axi_aresetn=0; s_axi_awvalid=0; s_axi_wvalid=0; s_axi_arvalid=0;
        s_axi_bready=0; s_axi_rready=0;
        repeat(3) @(negedge s_axi_aclk);
        check(!s_axi_bvalid && !s_axi_rvalid,"reset drops pending responses");
        s_axi_aresetn=1;
        repeat(3) @(negedge s_axi_aclk);
        check(s_axi_awready && s_axi_wready && s_axi_arready,"READY independent of VALID after synchronous reset");
    endtask

    task automatic send_aw(input logic [11:0] address, input integer gap);
        integer timeout_count;
        repeat(gap) @(negedge s_axi_aclk);
        @(negedge s_axi_aclk);
        s_axi_awaddr=address; s_axi_awprot=draw(); s_axi_awvalid=1;
        timeout_count=0;
        do begin
            @(posedge s_axi_aclk);
            timeout_count=timeout_count+1;
            check(timeout_count<80,"AW timeout");
        end while(!s_axi_awready);
        @(negedge s_axi_aclk); s_axi_awvalid=0;
    endtask
    task automatic send_w(input logic [31:0] value, input logic [3:0] strobes, input integer gap);
        integer timeout_count;
        repeat(gap) @(negedge s_axi_aclk);
        @(negedge s_axi_aclk);
        s_axi_wdata=value; s_axi_wstrb=strobes; s_axi_wvalid=1;
        timeout_count=0;
        do begin
            @(posedge s_axi_aclk);
            timeout_count=timeout_count+1;
            check(timeout_count<80,"W timeout");
        end while(!s_axi_wready);
        @(negedge s_axi_aclk); s_axi_wvalid=0;
    endtask
    task automatic collect_b(input logic [1:0] response, input integer hold_cycles);
        integer timeout_count;
        logic [1:0] snapshot;
        timeout_count=0;
        while(!s_axi_bvalid) begin
            @(posedge s_axi_aclk); #1;
            timeout_count=timeout_count+1; check(timeout_count<80,"B timeout");
        end
        snapshot=s_axi_bresp;
        check(snapshot===response,$sformatf("BRESP got %h wanted %h",snapshot,response));
        repeat(hold_cycles) begin
            @(posedge s_axi_aclk); #1;
            check(s_axi_bvalid && s_axi_bresp===snapshot,"held B unchanged");
            check(!s_axi_awready && !s_axi_wready,"no second write while B pending");
        end
        @(negedge s_axi_aclk); s_axi_bready=1;
        @(posedge s_axi_aclk);
        @(negedge s_axi_aclk); s_axi_bready=0;
    endtask
    task automatic axi_write(input logic [11:0] address, input logic [31:0] value,
                             input logic [3:0] strobes, input integer order_kind,
                             input integer gap, input integer hold_cycles,
                             input logic [1:0] response);
        fork
            send_aw(address,(order_kind==2)?gap:0);
            send_w(value,strobes,(order_kind==1)?gap:0);
        join
        collect_b(response,hold_cycles);
    endtask
    task automatic send_ar(input logic [11:0] address);
        integer timeout_count;
        @(negedge s_axi_aclk);
        s_axi_araddr=address; s_axi_arprot=draw(); s_axi_arvalid=1;
        timeout_count=0;
        do begin
            @(posedge s_axi_aclk);
            timeout_count=timeout_count+1; check(timeout_count<80,"AR timeout");
        end while(!s_axi_arready);
        @(negedge s_axi_aclk); s_axi_arvalid=0;
    endtask
    task automatic collect_r(output logic [31:0] value, input logic [1:0] response, input integer hold_cycles);
        integer timeout_count;
        logic [1:0] snapshot_response;
        timeout_count=0;
        while(!s_axi_rvalid) begin
            @(posedge s_axi_aclk); #1;
            timeout_count=timeout_count+1; check(timeout_count<80,"R timeout");
        end
        value=s_axi_rdata; snapshot_response=s_axi_rresp;
        check(snapshot_response===response,"RRESP exact");
        repeat(hold_cycles) begin
            @(posedge s_axi_aclk); #1;
            check(s_axi_rvalid && s_axi_rdata===value && s_axi_rresp===snapshot_response,"held R unchanged");
            check(!s_axi_arready,"no second read while R pending");
        end
        @(negedge s_axi_aclk); s_axi_rready=1;
        @(posedge s_axi_aclk);
        @(negedge s_axi_aclk); s_axi_rready=0;
    endtask
    task automatic axi_read(input logic [11:0] address, output logic [31:0] value,
                            input logic [1:0] response, input integer hold_cycles);
        send_ar(address); collect_r(value,response,hold_cycles);
    endtask
    task automatic read_equal(input logic [11:0] address, input logic [31:0] expected_value);
        logic [31:0] value;
        axi_read(address,value,0,draw()%3);
        check(value===expected_value,$sformatf("read %03h got %08h wanted %08h",address,value,expected_value));
    endtask
    task automatic reject_write(input logic [11:0] address, input logic [31:0] value,
                                input logic [3:0] strobes, input logic [31:0] error_code);
        axi_write(address,value,strobes,draw()%3,1+draw()%4,draw()%4,2);
        read_equal(12'h034,error_code);
    endtask
    task automatic make_words();
        integer i;
        logic [31:0] a,b;
        for(i=0;i<4;i=i+1) begin
            a=draw(); b=draw();
            expected_data[i]=a[15:0]; expected_ticks[i]={b,a};
            expected_quality[i]=b[7:0];
            words[i]={16'b0,expected_data[i]};
            words[4+2*i]=a; words[5+2*i]=b;
        end
        // Values are deliberately opaque, including clear/high quality bits.
        expected_data[0]=16'h0000; expected_data[3]=16'hffff;
        words[0]=0; words[3]=32'hffff;
        expected_quality[0]=8'h00; expected_quality[3]=8'hff;
        words[12]={expected_quality[3],expected_quality[2],expected_quality[1],expected_quality[0]};
    endtask
    task automatic fill_words(input integer skip_index);
        integer i;
        for(i=0;i<13;i=i+1)
            if(i!=skip_index) axi_write(12'h040+4*i,words[i],15,draw()%3,1+draw()%4,draw()%3,0);
    endtask
    task automatic start_session(input logic [31:0] tag_value, input logic [31:0] generation_value);
        axi_write(12'h010,tag_value,15,1,3,2,0);
        axi_write(12'h00c,2,15,2,4,5,0);
        read_equal(12'h014,tag_value); read_equal(12'h018,generation_value);
        read_equal(12'h01c,0); read_equal(12'h008,1);
    endtask
    task automatic wait_result();
        logic [31:0] status_value;
        integer i;
        status_value=0; i=0;
        while((status_value&4)==0 && i<80) begin
            axi_read(12'h008,status_value,0,0); i=i+1;
        end
        check((status_value&15)==7,"running busy result-valid, no fault");
    endtask
    task automatic drain_scan(input logic [31:0] tag_value, input logic [31:0] generation_value,
                              input logic [31:0] trigger_value, input logic [31:0] first_value);
        integer i;
        logic [31:0] cycle_value, now_value;
        for(i=0;i<4;i=i+1) begin
            wait_result();
            read_equal(12'h080,{16'b0,expected_data[i]});
            read_equal(12'h084,{16'b0,expected_quality[i],6'b0,2'(i)});
            read_equal(12'h088,expected_ticks[i][31:0]);
            read_equal(12'h08c,expected_ticks[i][63:32]);
            read_equal(12'h090,first_value); read_equal(12'h094,first_value+3);
            read_equal(12'h098,tag_value); read_equal(12'h09c,trigger_value);
            read_equal(12'h0a0,generation_value);
            axi_read(12'h0a4,cycle_value,0,3);
            axi_read(12'h020,now_value,0,0);
            check(cycle_value<=now_value,"PL_RESULT_LATCH_CYCLE is a prior PL counter snapshot");
            repeat(7+i) @(negedge s_axi_aclk);
            read_equal(12'h080,{16'b0,expected_data[i]});
            read_equal(12'h088,expected_ticks[i][31:0]);
            read_equal(12'h0a4,cycle_value);
            records=records+1;
            $display("DIAG53_RECORD run=%s tag=%08h generation=%0d trigger=%0d channel=%0d data=%04h tick=%016h quality=%02h first=%0d last=%0d",
                run_id,tag_value,generation_value,trigger_value,i,expected_data[i],expected_ticks[i],expected_quality[i],first_value,first_value+3);
            axi_write(12'h00c,8,15,draw()%3,2,draw()%3,0);
        end
        read_equal(12'h008,1);
    endtask
    task automatic counts(input logic [31:0] capture_value, queue_value, lane_value);
        read_equal(12'h024,capture_value); read_equal(12'h028,queue_value); read_equal(12'h030,lane_value);
    endtask
    task automatic stopped();
        integer i;
        read_equal(12'h008,0); read_equal(12'h014,0); read_equal(12'h010,0);
        for(i=0;i<10;i=i+1) read_equal(12'h080+4*i,0);
        repeat(15) @(negedge s_axi_aclk);
        read_equal(12'h008,0);
    endtask

    // Queue STOP while the trigger B is being accepted. There is no second
    // outstanding write: AW/W wait for READY. STOP commits after two strobes.
    task automatic trigger_stop_in_feeder();
        integer t;
        fork send_aw(12'h00c,0); send_w(4,15,0); join
        t=0;
        while(!s_axi_bvalid) begin @(posedge s_axi_aclk); #1; t=t+1; check(t<80,"fast trigger B timeout"); end
        check(s_axi_bresp==0,"fast trigger accepted");
        @(negedge s_axi_aclk);
        s_axi_bready=1; s_axi_awvalid=1; s_axi_awaddr=12'h00c;
        s_axi_wvalid=1; s_axi_wdata=1; s_axi_wstrb=1;
        @(posedge s_axi_aclk); check(s_axi_bvalid,"trigger B still pending");
        @(negedge s_axi_aclk); s_axi_bready=0;
        fork
            begin
                @(posedge s_axi_aclk); check(s_axi_awready,"queued STOP AW ready");
                @(negedge s_axi_aclk); s_axi_awvalid=0;
            end
            begin
                @(posedge s_axi_aclk); check(s_axi_wready,"queued STOP W ready");
                @(negedge s_axi_aclk); s_axi_wvalid=0;
            end
        join
        collect_b(0,2);
    endtask

    initial begin : stimulus
        logic [31:0] value, held_value;
        logic [11:0] ro_addresses [0:20];
        integer i;
        if(!$value$plusargs("RUN_ID=%s",run_id)) $fatal(1,"missing RUN_ID");
        if(!$value$plusargs("SEED=%d",seed)) $fatal(1,"missing SEED");
        i=$value$plusargs("NEGATIVE=%d",negative);
        rng=32'(seed);
        $display("DIAG53_BEGIN run=%s seed=%0d",run_id,seed);
        reset_bus();
        read_equal(0,32'h44505953);
        if(negative!=0) begin
            $display("DIAG53_EXPECTED_FAILURE run=%s purpose=runner_must_reject_real_simulator_fatal",run_id);
            $fatal(1,"DIAG53 deliberate negative control");
        end

        begin_case("fresh_boot_bad_accesses_and_STOP_byte0_dominance");
        read_equal(4,32'h00010000); read_equal(8,0); counts(0,0,0);
        axi_read(12'h02c,value,2,6); check(value==0,"unknown read data zero");
        axi_read(12'h001,value,2,4); axi_read(12'h00c,value,2,2);
        reject_write(12'h041,32'h1234,15,1);
        reject_write(12'h02c,1,15,2);
        ro_addresses='{12'h000,12'h004,12'h008,12'h014,12'h018,12'h01c,12'h020,
            12'h024,12'h028,12'h030,12'h034,12'h080,12'h084,12'h088,12'h08c,
            12'h090,12'h094,12'h098,12'h09c,12'h0a0,12'h0a4};
        for(i=0;i<21;i=i+1) reject_write(ro_addresses[i],draw(),15,3);
        read_equal(0,32'h44505953);
        reject_write(12'h010,32'h1234,7,4); read_equal(12'h010,0);
        reject_write(12'h00c,2,15,7);
        reject_write(12'h00c,0,15,5); reject_write(12'h00c,6,15,5);
        reject_write(12'h00c,32'h80,15,5);
        reject_write(12'h00c,4,1,4);
        reject_write(12'h00d,1,1,1);
        axi_write(12'h00c,32'hffffffff,1,1,3,6,0);
        read_equal(12'h034,0); stopped();

        begin_case("session1_START_split_channels_and_freshness");
        make_words(); fill_words(-1);
        start_session(32'ha5310021,1);
        reject_write(12'h00c,2,15,6);
        reject_write(12'h010,32'hffff,15,17); read_equal(12'h014,32'ha5310021);
        reject_write(12'h00c,4,15,12);
        fill_words(12); reject_write(12'h00c,4,15,12);
        reject_write(12'h070,words[12],1,4); reject_write(12'h00c,4,15,12);
        axi_write(12'h070,words[12],15,2,4,2,0);

        begin_case("four_exact_records_B_R_backpressure_delayed_ACK");
        axi_write(12'h00c,4,15,2,4,10,0);
        read_equal(12'h01c,1); read_equal(12'h018,1);
        reject_write(12'h040,32'h1234,15,16); reject_write(12'h00c,4,15,11);
        wait_result(); read_equal(12'h030,1);
        drain_scan(32'ha5310021,1,1,0); counts(4,1,4);
        reject_write(12'h00c,8,15,15); reject_write(12'h00c,4,15,12);

        begin_case("second_scan_requires_every_fresh_word_and_data16_range");
        make_words(); fill_words(2);
        reject_write(12'h048,32'h00010001,15,18);
        reject_write(12'h00c,4,15,12);
        axi_write(12'h048,words[2],15,1,3,1,0);
        axi_write(12'h00c,4,15,1,5,7,0);
        drain_scan(32'ha5310021,1,2,4); counts(8,2,8);

        begin_case("STOP_preserves_counters_and_rejects_immediate_old_tag");
        axi_write(12'h00c,32'hffff000f,1,0,0,4,0);
        stopped(); read_equal(12'h018,1); counts(8,2,8);
        axi_write(12'h010,32'ha5310021,15,2,4,2,0);
        reject_write(12'h00c,2,15,8);
        read_equal(12'h018,1); read_equal(12'h008,0);

        begin_case("second_session_new_generation_original_tick64");
        start_session(32'hb6420032,2);
        reject_write(12'h00c,4,15,12);
        make_words(); fill_words(-1); axi_write(12'h00c,4,15,0,0,3,0);
        drain_scan(32'hb6420032,2,1,0); counts(12,3,12);

        begin_case("STOP_with_result_and_stalled_R_snapshot");
        make_words(); fill_words(-1); axi_write(12'h00c,4,15,0,0,0,0);
        wait_result(); send_ar(12'h080);
        check(s_axi_rvalid,"held result R exists"); held_value=s_axi_rdata;
        axi_write(12'h00c,1,1,2,3,4,0);
        check(s_axi_rvalid && s_axi_rdata===held_value,"STOP preserves preexisting R snapshot");
        collect_r(value,0,5); check(value===held_value,"stale snapshot accepted unchanged");
        stopped(); counts(16,4,13); reject_write(12'h00c,8,15,15);

        begin_case("STOP_during_feeder_cancels_partial_scan");
        start_session(32'hc7530043,3);
        make_words(); fill_words(-1); trigger_stop_in_feeder();
        stopped(); counts(18,4,13);

        begin_case("STOP_same_edge_as_first_result_ready");
        start_session(32'hd8640054,4);
        make_words(); fill_words(-1); axi_write(12'h00c,4,15,0,0,0,0);
        // Public-edge schedule: trigger commit T2; samples T3..T6; queue
        // accepts T7; lane accepts scan T8. STOP commit T9 suppresses lane0.
        repeat(3) @(negedge s_axi_aclk);
        axi_write(12'h00c,1,1,0,0,0,0);
        stopped(); counts(22,5,13);

        begin_case("reset_pending_AW_and_new_unpaired_W");
        send_aw(12'h040,0); repeat(4) @(negedge s_axi_aclk);
        check(!s_axi_bvalid,"AW alone has no response"); reset_bus();
        send_w(32'h1234,15,0); repeat(4) @(negedge s_axi_aclk);
        check(!s_axi_bvalid,"old AW not paired after reset"); reset_bus(); read_equal(12'h040,0);

        begin_case("reset_pending_W_and_new_unpaired_AW");
        send_w(32'habcd,15,0); repeat(4) @(negedge s_axi_aclk);
        check(!s_axi_bvalid,"W alone has no response"); reset_bus();
        send_aw(12'h040,0); repeat(4) @(negedge s_axi_aclk);
        check(!s_axi_bvalid,"old W not paired after reset"); reset_bus();

        begin_case("reset_pending_B");
        fork send_aw(12'h040,0); send_w(32'h1234,15,0); join
        while(!s_axi_bvalid) begin @(posedge s_axi_aclk); #1; end
        repeat(5) @(negedge s_axi_aclk); reset_bus();
        read_equal(12'h040,0); counts(0,0,0); read_equal(12'h018,0);

        begin_case("reset_pending_R");
        send_ar(0); check(s_axi_rvalid,"R pending before reset");
        reset_bus(); read_equal(4,32'h00010000);

        begin_case("reset_clears_last_tag_history_and_clean_recovery");
        start_session(32'ha5310021,1);
        make_words(); fill_words(-1); axi_write(12'h00c,4,15,2,6,8,0);
        drain_scan(32'ha5310021,1,1,0); counts(4,1,4);
        axi_write(12'h00c,1,1,0,0,0,0); stopped();

        check(records==16,"sixteen verified raw lane records");
        check(cases==14,"all directed cases completed");
        $display("DIAG53_STATS run=%s checks=%0d writes=%0d reads=%0d records=%0d cases=%0d",run_id,checks,writes,reads,records,cases);
        $display("DIAG53_PASS run=%s seed=%0d",run_id,seed);
        $finish;
    end
    initial begin
        #2000000;
        $fatal(1,"DIAG53 global timeout");
    end
endmodule
