# PYNQ-Z2 TUL board package: PMODA pin1=Y18, pin2=Y19, bank34 3.3V.
# PMODA pins are shared with the Raspberry Pi connector; do not double-drive.
set_property -dict {PACKAGE_PIN Y18 IOSTANDARD LVCMOS33} [get_ports uart_txd]
set_property -dict {PACKAGE_PIN Y19 IOSTANDARD LVCMOS33 PULLUP TRUE} [get_ports uart_rxd]
# Asynchronous UART external timing is not a synchronous source-synchronous bus.
# Board/cable flight time and electrical behavior remain physically unmeasured.
