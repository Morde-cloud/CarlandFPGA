# NEW98 functional50 external package constraints.
# Source-only candidate; every check remains unexecuted. A alone confirms physical availability and electrical
# loopback before any board action. No UART, analog, RS485 or debug pin exists.
# Exact old G05 locations and LVCMOS33 bank34 are reused under new top names.
# Exact six-port closure; no other top-level PL port is defined here.
set_property PACKAGE_PIN W14 [get_ports {yaw_pwm_o}]
set_property IOSTANDARD LVCMOS33 [get_ports {yaw_pwm_o}]
set_property PACKAGE_PIN Y14 [get_ports {pitch_pwm_o}]
set_property IOSTANDARD LVCMOS33 [get_ports {pitch_pwm_o}]
set_property PACKAGE_PIN T11 [get_ports {speed_pwm_o}]
set_property IOSTANDARD LVCMOS33 [get_ports {speed_pwm_o}]
set_property PACKAGE_PIN V16 [get_ports {yaw_capture_i}]
set_property IOSTANDARD LVCMOS33 [get_ports {yaw_capture_i}]
set_property PACKAGE_PIN W16 [get_ports {pitch_capture_i}]
set_property IOSTANDARD LVCMOS33 [get_ports {pitch_capture_i}]
set_property PACKAGE_PIN V12 [get_ports {speed_capture_i}]
set_property IOSTANDARD LVCMOS33 [get_ports {speed_capture_i}]
