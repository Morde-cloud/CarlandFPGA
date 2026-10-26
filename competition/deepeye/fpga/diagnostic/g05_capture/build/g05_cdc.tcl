# Main supplies exact three-stage D-pin names after source acceptance.
# No guessed hierarchy or wildcard exception. This executes after open_run synth_1.
proc g05_same_one {actual expected} {
    return [expr {[llength $actual] == 1 && [llength $expected] == 1 &&
        [get_property NAME [lindex $actual 0]] eq [get_property NAME [lindex $expected 0]]}]
}
proc apply_g05_cdc {bindings report_path} {
    if {[lsort [dict keys $bindings]] ne {pitch_capture_i speed_capture_i yaw_capture_i}} {
        error {exact three capture bindings required; unresolved CDC blocks build}
    }
    set used {}
    set report {}
    set exact_pins [dict create]
    foreach pin [get_pins -hierarchical -quiet] {
        dict lappend exact_pins [get_property NAME $pin] $pin
    }
    dict for {port_name stage_names} $bindings {
        if {[llength $stage_names] != 3} {error "three synchronizer stages required: $port_name"}
        set pins {}
        foreach name $stage_names {
            # Exact hierarchical name comparison, including literal vector brackets.
            set found {}
            if {[dict exists $exact_pins $name]} {set found [dict get $exact_pins $name]}
            if {[llength $found] != 1} {error "unresolved/duplicate CDC pin: $name"}
            set pin [lindex $found 0]
            if {[get_property REF_PIN_NAME $pin] ne "D"} {error "CDC target must be FF D: $name"}
            set cell [get_cells -of_objects $pin]
            if {[llength $cell] != 1 || [get_property IS_SEQUENTIAL $cell] != 1 || [get_property ASYNC_REG $cell] ni {TRUE true 1}} {
                error "CDC target is not an ASYNC_REG sequential cell: $name"
            }
            set clock_pin [get_pins -of_objects $cell -filter {REF_PIN_NAME == C}]
            set clock [get_clocks -of_objects $clock_pin]
            if {[llength $clock_pin] != 1 || [llength $clock] != 1 || abs(double([get_property PERIOD $clock])-10.0) > 0.00001} {
                error "CDC stage is not timed by the actual 100MHz clock: $name"
            }
            if {$name in $used} {error "shared CDC target: $name"}
            lappend used $name
            lappend pins $pin
        }
        set port [get_ports -quiet $port_name]
        if {[llength $port] != 1} {error "CDC external input missing: $port_name"}
        set first [lindex $pins 0]
        set roots [all_fanin -flat -startpoints_only -to $first]
        if {![g05_same_one $roots $port]} {error "first CDC stage is not driven solely by $port_name"}
        # The external input may feed only its own first FF; stages two/three stay timed.
        set endpoints [all_fanout -flat -endpoints_only -from $port]
        if {![g05_same_one $endpoints [list $first]]} {error "unexpected asynchronous fanout: $port_name"}
        for {set index 1} {$index < 3} {incr index} {
            set previous [get_cells -of_objects [lindex $pins [expr {$index-1}]]]
            set target [lindex $pins $index]
            set expected_q [get_pins -of_objects $previous -filter {REF_PIN_NAME == Q}]
            set drivers [get_pins -quiet -leaf -of_objects [get_nets -quiet -of_objects $target] -filter {DIRECTION == OUT}]
            if {![g05_same_one $drivers $expected_q]} {error "broken direct Q-to-D CDC chain: $port_name"}
            # Vivado's timing startpoint is the launching FF clock pin, not Q.
            # Check this separately; direct-driver equality rejects intervening logic.
            set expected_c [get_pins -of_objects $previous -filter {REF_PIN_NAME == C}]
            set starts [all_fanin -flat -startpoints_only -to $target]
            if {![g05_same_one $starts $expected_c]} {error "unexpected CDC timing startpoint: $port_name"}
            lappend report "$port_name stage$index: direct [get_property NAME [lindex $drivers 0]] -> [get_property NAME $target]; start [get_property NAME [lindex $starts 0]]"
        }
        set_false_path -from $port -to $first
        lappend report "$port_name -> $stage_names; only external-to-first-D excluded"
    }
    set f [open $report_path {WRONLY CREAT EXCL}]
    puts $f [join $report \n]
    close $f
}
