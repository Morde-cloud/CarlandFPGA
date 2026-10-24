// Internal structural49 candidate. No ABI, baud/clock authority or remote rollback.
module deepeye_trace_uart_candidate #(
    parameter integer CLOCK_HZ=100000000,
    parameter integer BAUD=9600
) (
    input logic clk,rst,cancel,
    input logic cfg_valid,output logic cfg_ready,
    input logic [7:0] cfg_count,input logic [3:0] cfg_e,
    input logic [31:0] cfg_session,input logic [1:0] cfg_channel,
    input logic [31:0] cfg_first_index,input logic [63:0] cfg_first_tick,
    input logic [15:0] cfg_index_stride,cfg_tick_stride,
    input logic cfg_valid_sample,cfg_saturated,cfg_held,cfg_source_fault,
    input logic [63:0] cfg_source_tick,
    input logic [7:0] cfg_epoch,input logic [15:0] cfg_seq,
    input logic s_valid,output logic s_ready,
    input logic [15:0] s_data,input logic s_last,
    output logic tx,uart_busy,
    output logic result_valid,input logic result_ready,
    output logic [2:0] result_error,output logic [5:0] result_bytes,
    output logic busy,wire_faulted,wire_fault_event,
    output logic [1:0] wire_fault_code
);
    wire frame_cfg_ready,frame_result_valid,frame_busy;
    wire byte_valid,byte_ready;
    wire [7:0] byte_data;
    wire report_enable=!uart_busy&&!rst&&!cancel;
    assign cfg_ready=frame_cfg_ready&&report_enable;
    assign result_valid=frame_result_valid&&report_enable;
    assign busy=frame_busy||uart_busy;
    deepeye_trace_frame_candidate frame_stage (
        .clk(clk),.rst(rst),.cancel(cancel),
        .cfg_valid(cfg_valid&&report_enable),.cfg_ready(frame_cfg_ready),
        .cfg_count(cfg_count),.cfg_e(cfg_e),.cfg_session(cfg_session),.cfg_channel(cfg_channel),
        .cfg_first_index(cfg_first_index),.cfg_first_tick(cfg_first_tick),
        .cfg_index_stride(cfg_index_stride),.cfg_tick_stride(cfg_tick_stride),
        .cfg_valid_sample(cfg_valid_sample),.cfg_saturated(cfg_saturated),
        .cfg_held(cfg_held),.cfg_source_fault(cfg_source_fault),.cfg_source_tick(cfg_source_tick),
        .cfg_epoch(cfg_epoch),.cfg_seq(cfg_seq),
        .s_valid(s_valid),.s_ready(s_ready),.s_data(s_data),.s_last(s_last),
        .out_valid(byte_valid),.out_ready(byte_ready),.out_data(byte_data),.out_last(),.out_count(),
        .result_valid(frame_result_valid),.result_ready(result_ready&&report_enable),
        .result_error(result_error),.result_bytes(result_bytes),.busy(frame_busy),
        .wire_faulted(wire_faulted),.wire_fault_event(wire_fault_event),.wire_fault_code(wire_fault_code)
    );
    deepeye_uart_tx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD),.STAT_W(32)) uart_stage (
        .clk(clk),.rst(rst),.cancel(cancel),.in_valid(byte_valid),.in_ready(byte_ready),.in_data(byte_data),
        .tx(tx),.busy(uart_busy),.stat_accepted(),.stat_completed(),.stat_aborted()
    );
endmodule
