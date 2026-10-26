`timescale 1ns/1ps
module tb_deepeye_g05_command_map;
    logic [7:0] profile_id, speed_code;
    logic signed [15:0] yaw_q, pitch_q;
    logic [15:0] ttl_ms;
    wire legal;
    wire [3:0] reject_bits;
    wire [31:0] period_ticks, high_yaw, high_pitch, high_speed;
    wire [63:0] ttl_ticks, curvature_sum, curvature_limit;
    deepeye_g05_command_map dut(.*);

    logic e_legal;
    logic [3:0] e_reject;
    logic [31:0] e_period, e_yaw, e_pitch, e_speed;
    logic [63:0] e_ttl, e_sum, e_limit;
    integer file_handle, fields, count, unknown_count, expected_count, corrupt_expected;
    integer completion_status;
    string vector_path;

    task automatic check_known;
        if ({legal,reject_bits,period_ticks,high_yaw,high_pitch,high_speed,
             ttl_ticks,curvature_sum,curvature_limit} !==
            {e_legal,e_reject,e_period,e_yaw,e_pitch,e_speed,e_ttl,e_sum,e_limit}) begin
            $display("G05_MAPPER_MISMATCH index=%0d profile=%h yaw=%h pitch=%h speed=%h ttl=%h",
                count,profile_id,yaw_q,pitch_q,speed_code,ttl_ms);
            $display("actual   legal=%h reject=%h period=%h yaw=%h pitch=%h speed=%h ttl=%h sum=%h limit=%h",
                legal,reject_bits,period_ticks,high_yaw,high_pitch,high_speed,ttl_ticks,curvature_sum,curvature_limit);
            $display("expected legal=%h reject=%h period=%h yaw=%h pitch=%h speed=%h ttl=%h sum=%h limit=%h",
                e_legal,e_reject,e_period,e_yaw,e_pitch,e_speed,e_ttl,e_sum,e_limit);
            $fatal(1,"G05_MAPPER_CHECK_FAILED");
        end
        if (legal && !(high_yaw>0 && high_yaw<period_ticks && high_pitch>0 &&
                      high_pitch<period_ticks && high_speed>0 && high_speed<period_ticks))
            $fatal(1,"G05_MAPPER_HIGH_BOUND_FAILED");
    endtask

    task automatic defaults;
        profile_id=1; yaw_q=0; pitch_q=0; speed_code=1; ttl_ms=1;
    endtask

    task automatic check_unknown(input string label_text);
        #1;
        if (legal === 1'b1)
            $fatal(1,"G05_MAPPER_UNKNOWN_ACCEPTED %s",label_text);
        if ({period_ticks,high_yaw,high_pitch,high_speed,ttl_ticks} !== 192'd0)
            $fatal(1,"G05_MAPPER_UNKNOWN_MAPPING_NONZERO %s",label_text);
        unknown_count=unknown_count+1;
    endtask

    initial begin
        count=0; unknown_count=0; corrupt_expected=0; completion_status=0;
        if (!$value$plusargs("VECTORS=%s",vector_path)) $fatal(1,"missing VECTORS");
        if (!$value$plusargs("COUNT=%d",expected_count)) $fatal(1,"missing COUNT");
        if ($value$plusargs("CORRUPT_EXPECTED=%d",corrupt_expected)) begin end
        file_handle=$fopen(vector_path,"r");
        if (!file_handle) $fatal(1,"cannot open vector file");
        while (!$feof(file_handle)) begin
            fields=$fscanf(file_handle,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",
                profile_id,yaw_q,pitch_q,speed_code,ttl_ms,e_legal,e_reject,
                e_period,e_yaw,e_pitch,e_speed,e_ttl,e_sum,e_limit);
            if (fields != 14) $fatal(1,"malformed vector index=%0d fields=%0d",count,fields);
            #1;
            // Deliberate oracle mismatch validates the actual simulator failure path.
            if (corrupt_expected && count==0) e_ttl=e_ttl ^ 64'h0000000100000000;
            check_known();
            count=count+1;
        end
        $fclose(file_handle);
        if (count!=expected_count || count<42) $fatal(1,"unexpected vector count %0d",count);
        defaults(); profile_id=8'hxx; check_unknown("profile X");
        defaults(); profile_id=8'hzz; check_unknown("profile Z");
        defaults(); profile_id=8'b000000x1; check_unknown("profile partial X");
        defaults(); profile_id=8'b000000z1; check_unknown("profile partial Z");
        defaults(); speed_code=8'hxx; check_unknown("speed X");
        defaults(); speed_code=8'hzz; check_unknown("speed Z");
        defaults(); speed_code=8'b000000x1; check_unknown("speed partial X");
        defaults(); speed_code=8'b000000z1; check_unknown("speed partial Z");
        defaults(); yaw_q=16'hxxxx; check_unknown("yaw X");
        defaults(); yaw_q=16'hzzzz; check_unknown("yaw Z");
        defaults(); pitch_q=16'hxxxx; check_unknown("pitch X");
        defaults(); pitch_q=16'hzzzz; check_unknown("pitch Z");
        defaults(); ttl_ms=16'hxxxx; check_unknown("ttl X");
        defaults(); ttl_ms=16'hzzzz; check_unknown("ttl Z");
        defaults(); ttl_ms=16'b00000000000000x1; check_unknown("ttl partial X");
        defaults(); ttl_ms=16'b00000000000000z1; check_unknown("ttl partial Z");
        defaults(); profile_id=8'd3; speed_code=8'hxx; check_unknown("invalid profile and X speed");
        defaults(); profile_id=2; speed_code=8'hzz; check_unknown("STRESS Z speed");
        completion_status=1;
        $display("G05_MAPPER_PASS known=%0d unknown=%0d",count,unknown_count);
        $finish;
    end
endmodule
