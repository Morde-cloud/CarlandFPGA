# Declarative package constraints; procedural validation belongs in build_g05.tcl.
# A candidate5c192f34: bank34 LVCMOS33; external delays/skew remain unmeasured.
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
