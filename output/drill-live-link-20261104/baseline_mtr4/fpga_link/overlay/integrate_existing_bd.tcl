# LIBRARY ONLY: sourcing defines a function but performs no design mutation.
# Explicit integration recipe for a product owner with an UNUSED PS M_AXI_GP1.
# Do not call unchanged if GP1, Y18/Y19 or address0x43C00000/64K are in use.
# It does NOT authorize loading/replacing a physical-board overlay.
proc add_mcu_uart_on_unused_gp1 {ps_cell} {
    if {[llength [get_bd_cells -quiet mcu_uart]] || [llength [get_bd_cells -quiet mcu_uart_xbar]]} {
        error {mcu_uart or mcu_uart_xbar already exists; do not overwrite}
    }
    set ps [get_bd_cells $ps_cell]
    if {[llength $ps] != 1} {error {expected exactly one existing PS7 cell}}
    set gp [get_bd_intf_pins -quiet $ps_cell/M_AXI_GP1]
    if {[llength $gp] && [llength [get_bd_intf_nets -of_objects $gp]]} {
        error {M_AXI_GP1 already connected; integrate through existing fabric instead}
    }
    # The caller checks package-pin conflicts before this first mutation.
    set_property CONFIG.PCW_USE_M_AXI_GP1 1 $ps
    set uart [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_uartlite:2.0 mcu_uart]
    set_property -dict [list CONFIG.C_BAUDRATE 115200 CONFIG.C_DATA_BITS 8 CONFIG.C_USE_PARITY 0 CONFIG.C_ODD_PARITY 0] $uart
    # Use reviewed automation for existing fabric expansion if GP1 cannot be
    # dedicated. For this dedicated GP1 recipe use a single-SI/single-MI xbar.
    set xbar [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 mcu_uart_xbar]
    set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 1] $xbar
    set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 mcu_uart_rst]
    set hi [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 mcu_uart_one]
    set lo [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 mcu_uart_zero]
    set_property CONFIG.CONST_VAL 1 $hi
    set_property CONFIG.CONST_VAL 0 $lo
    connect_bd_intf_net [get_bd_intf_pins $ps_cell/M_AXI_GP1] [get_bd_intf_pins mcu_uart_xbar/S00_AXI]
    connect_bd_intf_net [get_bd_intf_pins mcu_uart_xbar/M00_AXI] [get_bd_intf_pins mcu_uart/S_AXI]
    connect_bd_net [get_bd_pins $ps_cell/FCLK_CLK0] [get_bd_pins $ps_cell/M_AXI_GP1_ACLK] \
        [get_bd_pins mcu_uart_xbar/ACLK] [get_bd_pins mcu_uart_xbar/S00_ACLK] [get_bd_pins mcu_uart_xbar/M00_ACLK] \
        [get_bd_pins mcu_uart/s_axi_aclk] [get_bd_pins mcu_uart_rst/slowest_sync_clk]
    connect_bd_net [get_bd_pins $ps_cell/FCLK_RESET0_N] [get_bd_pins mcu_uart_rst/ext_reset_in]
    connect_bd_net [get_bd_pins mcu_uart_one/dout] [get_bd_pins mcu_uart_rst/dcm_locked]
    connect_bd_net [get_bd_pins mcu_uart_zero/dout] [get_bd_pins mcu_uart_rst/aux_reset_in] [get_bd_pins mcu_uart_rst/mb_debug_sys_rst]
    connect_bd_net [get_bd_pins mcu_uart_rst/interconnect_aresetn] [get_bd_pins mcu_uart_xbar/ARESETN]
    connect_bd_net [get_bd_pins mcu_uart_rst/peripheral_aresetn] [get_bd_pins mcu_uart_xbar/S00_ARESETN] \
        [get_bd_pins mcu_uart_xbar/M00_ARESETN] [get_bd_pins mcu_uart/s_axi_aresetn]
    foreach {name direction pin} {uart_txd O tx uart_rxd I rx} {
        connect_bd_net [create_bd_port -dir $direction $name] [get_bd_pins mcu_uart/$pin]
    }
    assign_bd_address -target_address_space [get_bd_addr_spaces $ps_cell/Data] \
        -offset 0x43C00000 -range 64K [get_bd_addr_segs mcu_uart/S_AXI/Reg]
    validate_bd_design
    # Add pmod_uart.xdc to constrs_1 explicitly in the owning product project,
    # verify routed exact pins/clock/reset/DRC/CDC, then regenerate bit+HWH.
    # This library helper is a recipe, not an independently built product image.
}
