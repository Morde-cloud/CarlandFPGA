# Six scalar PL package allocations only, selected from A commit5c192f34.
# Input/output flight time and physical cross-channel skew remain unmeasured.
# No invented IO delays, external clocks, or unrelated J3/analog/RS485 pins.
foreach {name pin direction} {
    yaw_pwm_o W14 OUT pitch_pwm_o Y14 OUT speed_pwm_o T11 OUT
    yaw_capture_i V16 IN pitch_capture_i W16 IN speed_capture_i V12 IN
} {
    set port [get_ports -quiet $name]
    if {[llength $port] != 1 || [get_property DIRECTION $port] ne $direction} {
        error "missing/wrong-direction exact G05 scalar port: $name"
    }
    set_property PACKAGE_PIN $pin $port
    set_property IOSTANDARD LVCMOS33 $port
}
