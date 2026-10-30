// Additive private G05 50 MHz AXI source candidate. SOURCE_ONLY / UNEXECUTED.
// Task DEEPEYE-IMPLEMENTATION-20261014/v1; work
// B-DEEPEYE-G05-ADDITIVE50-INTEGRATION-SOURCE-20261029-63.
// Base AXI object: 0026cb5573620fa9d28db07b437370a7211e1c0b.
// New magic/layout deliberately distinguishes this candidate from the existing
// 100 MHz G05D/layout-1 image. This is not a public BOOT/ENABLE/motion ABI and
// not acceptance of 50 MHz as the final target. The externally named 50G05
// connector is a logical source boundary only; pins/clock profile/address/HWH
// remain A-owned and unproduced. Only A may build or operate the board.
module deepeye_g05_axi_50mhz_candidate (
    input logic s_axi_aclk, input logic s_axi_aresetn,
    input logic [11:0] s_axi_awaddr, input logic [2:0] s_axi_awprot,
    input logic s_axi_awvalid, output logic s_axi_awready,
    input logic [31:0] s_axi_wdata, input logic [3:0] s_axi_wstrb,
    input logic s_axi_wvalid, output logic s_axi_wready,
    output logic [1:0] s_axi_bresp, output logic s_axi_bvalid,
    input logic s_axi_bready,
    input logic [11:0] s_axi_araddr, input logic [2:0] s_axi_arprot,
    input logic s_axi_arvalid, output logic s_axi_arready,
    output logic [31:0] s_axi_rdata, output logic [1:0] s_axi_rresp,
    output logic s_axi_rvalid, input logic s_axi_rready,
    output logic g05_50_candidate_yaw_pwm_o,
    output logic g05_50_candidate_pitch_pwm_o,
    output logic g05_50_candidate_speed_pwm_o,
    input logic g05_50_candidate_yaw_capture_i,
    input logic g05_50_candidate_pitch_capture_i,
    input logic g05_50_candidate_speed_capture_i
);
    localparam logic [31:0] G05_50_MAGIC = 32'h47303550; // "G05P"
    localparam logic [31:0] G05_50_LAYOUT = 32'd2;
    wire clk=s_axi_aclk;
    // Asynchronous assertion, two-stage synchronous release in FCLK50.
    (* ASYNC_REG = "TRUE" *) logic [1:0] areset_release_q;
    always_ff @(posedge clk or negedge s_axi_aresetn) begin
        if (!s_axi_aresetn) areset_release_q <= 2'b00;
        else areset_release_q <= {areset_release_q[0],1'b1};
    end
    wire rst=!areset_release_q[1];
    logic aw_full,w_full;
    logic [11:0] aw_addr;
    logic [31:0] w_data;
    logic [3:0] w_strb;
    logic [31:0] identity[0:12];
    logic [12:0] identity_fresh;
    logic [31:0] staged[0:6];
    logic [6:0] command_fresh;
    logic bound,retired,profile_locked,latch_valid,inflight;
    logic [7:0] wrapper_fault;
    logic [31:0] last_cmd,last_tag;
    logic [7:0] submitted_profile,submitted_speed;
    logic signed [15:0] submitted_yaw,submitted_pitch;
    logic [15:0] submitted_ttl;
    logic [31:0] latched[0:31];
    logic stop_pulse,cfg_valid;
    logic [31:0] cfg_period;
    logic [95:0] cfg_highs;
    logic [63:0] cfg_ttl,cfg_tag;
    wire cfg_ready,eng_accepted,eng_rejected,eng_applied,eng_running,eng_pending,eng_halted;
    wire [7:0] eng_fault;
    wire [63:0] cycle_tick,applied_tick,deadline_tick,active_tag;
    wire result_valid;
    wire [31:0] result_seq;
    wire [63:0] result_tag,result_tick;
    wire [95:0] result_periods,result_highs;
    wire [191:0] result_starts,result_ends;
    wire [2:0] pwm;
    wire map_legal;
    wire [3:0] map_reject;
    wire [31:0] map_period,map_yaw,map_pitch,map_speed;
    wire [63:0] map_ttl,map_sum,map_limit;
    wire stage_encoding_ok=(staged[0][31:16]==0)&&(staged[1][31:16]==0)&&
        (staged[2][31:8]==0)&&(staged[3][31:8]==0)&&(staged[4][31:16]==0);
    wire exact_duplicate=(staged[5]==last_cmd)&&(staged[6]==last_tag)&&
        (staged[0][15:0]==submitted_yaw)&&(staged[1][15:0]==submitted_pitch)&&
        (staged[2][7:0]==submitted_profile)&&(staged[3][7:0]==submitted_speed)&&
        (staged[4][15:0]==submitted_ttl);
    wire live=bound&&!retired&&!eng_halted;
    wire latest_eligible=live&&result_valid&&!inflight&&!eng_pending&&
        (result_tag=={last_cmd,last_tag});
    wire [31:0] status_word={25'b0,inflight,(latch_valid&&live),latest_eligible,
        eng_pending,eng_running,(retired||eng_halted),bound};
    assign {g05_50_candidate_speed_pwm_o,
            g05_50_candidate_pitch_pwm_o,
            g05_50_candidate_yaw_pwm_o}=pwm;
    assign s_axi_awready=!rst&&!aw_full&&!s_axi_bvalid;
    assign s_axi_wready=!rst&&!w_full&&!s_axi_bvalid;
    assign s_axi_arready=!rst&&!s_axi_rvalid;

    deepeye_g05_command_map_50mhz map_i(
        .profile_id(staged[2][7:0]),.yaw_q(staged[0][15:0]),.pitch_q(staged[1][15:0]),
        .speed_code(staged[3][7:0]),.ttl_ms(staged[4][15:0]),.legal(map_legal),
        .reject_bits(map_reject),.period_ticks(map_period),.high_yaw(map_yaw),
        .high_pitch(map_pitch),.high_speed(map_speed),.ttl_ticks(map_ttl),
        .curvature_sum(map_sum),.curvature_limit(map_limit));
    deepeye_g05_capture_engine_50mhz engine_i(
        .clk(clk),.rst(rst),.stop(stop_pulse||retired),.cfg_valid(cfg_valid),
        .cfg_ready(cfg_ready),.cfg_period(cfg_period),.cfg_highs(cfg_highs),
        .cfg_ttl_ticks(cfg_ttl),.cfg_tag(cfg_tag),
        .capture_async_i({g05_50_candidate_speed_capture_i,
                          g05_50_candidate_pitch_capture_i,
                          g05_50_candidate_yaw_capture_i}),.pwm_o(pwm),
        .accepted(eng_accepted),.rejected(eng_rejected),.applied(eng_applied),
        .running(eng_running),.pending(eng_pending),.halted(eng_halted),.fault_code(eng_fault),
        .cycle_tick(cycle_tick),.applied_tick(applied_tick),.deadline_tick(deadline_tick),
        .active_tag(active_tag),.result_valid(result_valid),.result_seq(result_seq),
        .result_tag(result_tag),.result_tick(result_tick),.result_periods(result_periods),
        .result_highs(result_highs),.result_starts(result_starts),.result_ends(result_ends));

    // The payload bank is independent of acceptance; admission remains cfg_valid.
    always_ff @(posedge clk) begin : payload_bank
        if(rst) begin
            cfg_period<=0;cfg_highs<=0;cfg_ttl<=0;cfg_tag<=0;
        end else begin
            cfg_period<=map_period;cfg_highs<={map_speed,map_pitch,map_yaw};
            cfg_ttl<=map_ttl;cfg_tag<={staged[5],staged[6]};
        end
    end

    wire write_issue = aw_full && w_full && !s_axi_bvalid;
    wire write_wellformed = (aw_addr[1:0]==0) && (w_strb==4'hf);
    wire write_control = write_issue && write_wellformed && (aw_addr==12'h00c);
    wire write_stage = write_issue && write_wellformed &&
        (aw_addr>=12'h200) && (aw_addr<=12'h218) && live;
    wire write_identity = write_issue && write_wellformed &&
        (aw_addr>=12'h100) && (aw_addr<=12'h130) && !bound && !retired && !eng_halted;
    wire commit_context = write_control && (w_data==32'd2) && live && (&command_fresh);
    wire commit_duplicate = stage_encoding_ok && map_legal && (last_cmd!=0) && exact_duplicate;
    wire commit_bad = !stage_encoding_ok || !map_legal || (staged[5]==0) ||
        (staged[5]<=last_cmd) || (profile_locked && (staged[2][7:0]!=submitted_profile));
    wire commit_slot = !inflight && !eng_pending && !latch_valid;
    (* keep = "TRUE" *) wire command_admit = commit_context && !commit_duplicate &&
        !commit_bad && commit_slot && cfg_ready;
    wire write_stop = write_control && (w_data==32'd3);
    (* keep = "TRUE" *) wire fresh_clear = write_stop ||
        (commit_context && (commit_duplicate || commit_bad || (commit_slot && cfg_ready)));
    wire any_run_direct = |{identity[0],identity[1],identity[2],identity[3],
        identity[4],identity[5],identity[6],identity[7]};
    wire any_nonce_direct = |{identity[8],identity[9],identity[10],identity[11]};
    wire begin_ok = !bound && !retired && !eng_halted && (&identity_fresh) &&
        any_run_direct && any_nonce_direct && (identity[12]!=0);
    wire write_success = write_identity || write_stage ||
        (write_control && (((w_data==32'd1) && begin_ok) ||
         ((w_data==32'd2) && commit_context && (commit_duplicate || command_admit)) ||
         (w_data==32'd3) || ((w_data==32'd4) && latest_eligible && !latch_valid) ||
         ((w_data==32'd5) && live && latch_valid)));

    always_ff @(posedge clk) begin : exact_command_banks
        if(rst) begin
            command_fresh<=0;cfg_valid<=0;inflight<=0;s_axi_bresp<=0;
            profile_locked<=0;last_cmd<=0;last_tag<=0;
            submitted_profile<=0;submitted_speed<=0;
            submitted_yaw<=0;submitted_pitch<=0;submitted_ttl<=0;
        end else begin
            cfg_valid<=command_admit;
            if(fresh_clear)command_fresh<=0;
            else if(write_stage)command_fresh[(aw_addr-12'h200)>>2]<=1;
            if(write_issue)s_axi_bresp<=write_success?2'b00:2'b10;
            if(command_admit)begin
                inflight<=1;last_cmd<=staged[5];last_tag<=staged[6];
                submitted_yaw<=staged[0][15:0];submitted_pitch<=staged[1][15:0];
                submitted_profile<=staged[2][7:0];submitted_speed<=staged[3][7:0];
                submitted_ttl<=staged[4][15:0];profile_locked<=1;
            end else if(eng_accepted||eng_rejected||eng_halted||write_stop)inflight<=0;
        end
    end

    always_ff @(posedge clk) begin : control
        integer i,idx;
        logic read_ok;
        logic [31:0] read_value;
        logic any_run,any_nonce;
        stop_pulse<=0;
        if(rst) begin
            aw_full<=0;w_full<=0;aw_addr<=0;w_data<=0;w_strb<=0;
            s_axi_bvalid<=0;s_axi_rvalid<=0;s_axi_rdata<=0;s_axi_rresp<=0;
            identity_fresh<=0;bound<=0;retired<=0;
            latch_valid<=0;wrapper_fault<=0;
            for(i=0;i<13;i=i+1)identity[i]<=0;
            for(i=0;i<7;i=i+1)staged[i]<=0;
            for(i=0;i<32;i=i+1)latched[i]<=0;
        end else begin
            if(s_axi_bvalid&&s_axi_bready)s_axi_bvalid<=0;
            if(s_axi_rvalid&&s_axi_rready)s_axi_rvalid<=0;
            if(s_axi_awvalid&&s_axi_awready)begin aw_full<=1;aw_addr<=s_axi_awaddr;end
            if(s_axi_wvalid&&s_axi_wready)begin w_full<=1;w_data<=s_axi_wdata;w_strb<=s_axi_wstrb;end
            if(eng_halted||eng_rejected)begin retired<=1;latch_valid<=0;end

            if(aw_full&&w_full&&!s_axi_bvalid)begin
                aw_full<=0;w_full<=0;s_axi_bvalid<=1;
                if((aw_addr[1:0]==0)&&(w_strb==4'hf))begin
                    if(aw_addr==12'h00c)begin
                        case(w_data)
                            32'd1:begin
                                any_run=0;any_nonce=0;
                                for(i=0;i<8;i=i+1)any_run=any_run|(|identity[i]);
                                for(i=8;i<12;i=i+1)any_nonce=any_nonce|(|identity[i]);
                                if(!bound&&!retired&&!eng_halted&&(&identity_fresh)&&
                                   any_run&&any_nonce&&(identity[12]!=0))begin
                                    bound<=1;identity_fresh<=0;
                                end
                            end
                            32'd2:begin
                                if(live&&(&command_fresh))begin
                                    if(stage_encoding_ok&&map_legal&&(last_cmd!=0)&&exact_duplicate)begin
                                    end else if(!stage_encoding_ok||!map_legal||(staged[5]==0)||
                                        (staged[5]<=last_cmd)||
                                        (profile_locked&&(staged[2][7:0]!=submitted_profile)))begin
                                        retired<=1;stop_pulse<=1;latch_valid<=0;
                                        wrapper_fault<=8'd1;
                                    end else if(!inflight&&!eng_pending&&cfg_ready&&!latch_valid)begin
                                        latch_valid<=0;
                                    end
                                end
                            end
                            32'd3:begin
                                stop_pulse<=1;retired<=1;latch_valid<=0;
                            end
                            32'd4:begin
                                if(latest_eligible&&!latch_valid)begin
                                    latched[0]<=result_seq;latched[1]<=result_tag[63:32];
                                    latched[2]<=result_tag[31:0];
                                    latched[3]<={16'b0,submitted_speed,submitted_profile};
                                    latched[4]<={submitted_pitch,submitted_yaw};latched[5]<={16'b0,submitted_ttl};
                                    latched[6]<=applied_tick[31:0];latched[7]<=applied_tick[63:32];
                                    latched[8]<=deadline_tick[31:0];latched[9]<=deadline_tick[63:32];
                                    latched[10]<=result_tick[31:0];latched[11]<=result_tick[63:32];
                                    for(i=0;i<3;i=i+1)begin
                                        latched[12+i]<=result_periods[i*32+:32];
                                        latched[15+i]<=result_highs[i*32+:32];
                                        latched[18+2*i]<=result_starts[i*64+:32];
                                        latched[19+2*i]<=result_starts[i*64+32+:32];
                                        latched[24+2*i]<=result_ends[i*64+:32];
                                        latched[25+2*i]<=result_ends[i*64+32+:32];
                                    end
                                    latched[30]<=identity[12];latched[31]<=G05_50_MAGIC;
                                    latch_valid<=1;
                                end
                            end
                            32'd5:begin
                                if(live&&latch_valid)begin latch_valid<=0;end
                            end
                            default:begin retired<=1;stop_pulse<=1;latch_valid<=0;wrapper_fault<=8'd2;end
                        endcase
                    end else if((aw_addr>=12'h100)&&(aw_addr<=12'h130)&&!bound&&!retired&&!eng_halted)begin
                        idx=(aw_addr-12'h100)>>2;identity[idx]<=w_data;identity_fresh[idx]<=1;
                    end else if((aw_addr>=12'h200)&&(aw_addr<=12'h218)&&live)begin
                        idx=(aw_addr-12'h200)>>2;staged[idx]<=w_data;
                    end
                end
            end
            if(s_axi_arvalid&&s_axi_arready)begin
                read_value=0;read_ok=1;
                if(s_axi_araddr[1:0]!=0)read_ok=0;
                else begin
                    case(s_axi_araddr)
                        12'h000:read_value=G05_50_MAGIC;
                        12'h004:read_value=G05_50_LAYOUT;
                        12'h008:read_value=status_word;
                        12'h010:read_value={16'b0,wrapper_fault,eng_fault};
                        12'h014:read_value=last_cmd;
                        12'h018:read_value=active_tag[31:0];
                        12'h01c:read_value=result_seq;
                        12'h020:read_value=cycle_tick[31:0];
                        12'h024:read_value=cycle_tick[63:32];
                        12'h028:read_value={12'b0,command_fresh,identity_fresh};
                        12'h040:read_value=applied_tick[31:0];
                        12'h044:read_value=applied_tick[63:32];
                        12'h048:read_value=deadline_tick[31:0];
                        12'h04c:read_value=deadline_tick[63:32];
                        default:begin
                            if((s_axi_araddr>=12'h100)&&(s_axi_araddr<=12'h130))begin
                                idx=(s_axi_araddr-12'h100)>>2;read_value=identity[idx];
                            end else if((s_axi_araddr>=12'h200)&&(s_axi_araddr<=12'h218))begin
                                idx=(s_axi_araddr-12'h200)>>2;read_value=staged[idx];
                            end else if((s_axi_araddr>=12'h300)&&(s_axi_araddr<=12'h37c)&&latch_valid&&live)begin
                                idx=(s_axi_araddr-12'h300)>>2;read_value=latched[idx];
                            end else read_ok=0;
                        end
                    endcase
                end
                s_axi_rvalid<=1;s_axi_rdata<=read_value;s_axi_rresp<=read_ok?2'b00:2'b10;
            end
        end
    end
endmodule
