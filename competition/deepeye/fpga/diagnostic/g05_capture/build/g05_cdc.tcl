# Main supplies exact three-stage D-pin names after source acceptance.
# No guessed hierarchy or wildcard exception. This executes after open_run synth_1.
proc apply_g05_cdc {bindings report_path} {
    if {[lsort [dict keys $bindings]] ne {pitch_capture_i speed_capture_i yaw_capture_i}} {
        error {exact three capture bindings required; unresolved CDC blocks build}
    }
    set used {}
    set report {}
    dict for {port_name stage_names} $bindings {
        if {[llength $stage_names] != 3} {error "three synchronizer stages required: $port_name"}
        set pins {}
        foreach name $stage_names {
            # Exact hierarchical name comparison, including literal vector brackets.
            set found {}
            foreach p [get_pins -hierarchical -quiet] {
                if {[get_property NAME $p] eq $name} {lappend found $p}
            }
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
        if {[llength $roots] != 1 || [lindex $roots 0] ne $port} {error "first CDC stage is not driven solely by $port_name"}
        # The external input may feed only its own first FF; stages two/three stay timed.
        set endpoints [all_fanout -flat -endpoints_only -from $port]
        if {[llength $endpoints] != 1 || [lindex $endpoints 0] ne $first} {error "unexpected asynchronous fanout: $port_name"}
        for {set index 1} {$index < 3} {incr index} {
            set previous [get_cells -of_objects [lindex $pins [expr {$index-1}]]]
            set expected [get_pins -of_objects $previous -filter {REF_PIN_NAME == Q}]
            set actual [all_fanin -flat -startpoints_only -to [lindex $pins $index]]
            if {[llength $expected] != 1 || $actual ne $expected} {error "broken three-stage CDC chain: $port_name"}
        }
        set_false_path -from $port -to $first
        lappend report "$port_name -> $stage_names; only external-to-first-D excluded"
    }
    set f [open $report_path {WRONLY CREAT EXCL}]
    puts $f [join $report \n]
    close $f
}
