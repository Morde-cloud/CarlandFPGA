# NEW99S source-only implementation of main amendment1. NOT EXECUTED.
# Actual connectivity discovery happens inside the ONE future authorized build.
# No guessed hierarchy, manual fallback or second discovery synthesis exists.
proc f50_require {condition message} {
    if {![uplevel 1 [list expr $condition]]} {error $message}
}
proc f50_same_one {actual expected} {
    return [expr {[llength $actual] == 1 && [llength $expected] == 1 &&
        [get_property NAME [lindex $actual 0]] eq [get_property NAME [lindex $expected 0]]}]
}
proc f50_ff {pin} {
    f50_require {[get_property REF_PIN_NAME $pin] eq "D"} {CDC endpoint must be one FF D pin}
    set cell [get_cells -of_objects $pin]
    f50_require {[llength $cell] == 1 && [get_property IS_SEQUENTIAL $cell] == 1 &&
        [get_property ASYNC_REG $cell] in {TRUE true 1}} {CDC endpoint must be an ASYNC_REG sequential cell}
    set clock_pin [get_pins -of_objects $cell -filter {REF_PIN_NAME == C}]
    set clock [get_clocks -of_objects $clock_pin]
    f50_require {[llength $clock_pin] == 1 && [llength $clock] == 1 &&
        abs(double([get_property PERIOD $clock])-20.0) <= 0.00001} {CDC stage must have one actual 20ns clock}
    set q [get_pins -of_objects $cell -filter {REF_PIN_NAME == Q}]
    f50_require {[llength $q] == 1} {CDC FF must expose exactly one Q pin}
    return [dict create cell $cell clock $clock clock_pin $clock_pin q $q]
}
proc discover_functional50_cdc {} {
    set bindings [dict create]
    foreach port_name {yaw_capture_i pitch_capture_i speed_capture_i} {
        set port [get_ports -quiet $port_name]
        f50_require {[llength $port] == 1 && [get_property DIRECTION $port] eq "IN" &&
            [get_property IS_BUS $port] == 0} "one exact scalar input required: $port_name"
        set endpoints [all_fanout -flat -endpoints_only -from $port]
        f50_require {[llength $endpoints] == 1} "external input must drive one first FF D: $port_name"
        set pin [lindex $endpoints 0]
        set names {}
        for {set stage 0} {$stage < 3} {incr stage} {
            set info [f50_ff $pin]
            set name [get_property NAME $pin]
            f50_require {[regexp {^([A-Za-z0-9_./-]|\[[0-9]+\])+$} $name]} "unsafe actual CDC name: $name"
            lappend names $name
            if {$stage < 2} {
                set endpoints [all_fanout -flat -endpoints_only -from [dict get $info q]]
                f50_require {[llength $endpoints] == 1} "ambiguous next CDC stage: $port_name stage$stage"
                set pin [lindex $endpoints 0]
            }
        }
        dict set bindings $port_name $names
    }
    return $bindings
}
proc apply_functional50_cdc {bindings report_path {apply_exceptions 1}} {
    f50_require {$apply_exceptions in {0 1}} {explicit CDC apply/revalidate mode required}
    f50_require {[lsort [dict keys $bindings]] eq {pitch_capture_i speed_capture_i yaw_capture_i}} \
        {exact three G05 capture bindings required; unresolved CDC blocks build}
    set used {}
    set used_cells {}
    set common_clock {}
    set report {}
    set false_paths_applied 0
    set exclusions {}
    set exact_pins [dict create]
    foreach pin [get_pins -hierarchical -quiet] {
        dict lappend exact_pins [get_property NAME $pin] $pin
    }
    dict for {port_name stage_names} $bindings {
        f50_require {[llength $stage_names] == 3} "three synchronizer stages required: $port_name"
        set pins {}
        foreach name $stage_names {
            # Exact hierarchical name comparison, including literal vector brackets.
            f50_require {[regexp {^([A-Za-z0-9_./-]|\[[0-9]+\])+$} $name]} {unsafe literal actual CDC pin name}
            set found {}
            if {[dict exists $exact_pins $name]} {set found [dict get $exact_pins $name]}
            f50_require {[llength $found] == 1} "unresolved/duplicate CDC pin: $name"
            set pin [lindex $found 0]
            set info [f50_ff $pin]
            set cell_name [get_property NAME [dict get $info cell]]
            set clock [dict get $info clock]
            if {[llength $common_clock] == 0} {set common_clock $clock}
            f50_require {[f50_same_one $clock $common_clock]} {all nine CDC FFs must share the same actual clock}
            f50_require {$name ni $used} "shared CDC target: $name"
            f50_require {$cell_name ni $used_cells} "shared CDC FF cell: $cell_name"
            lappend used $name
            lappend used_cells $cell_name
            lappend pins $pin
        }
        set port [get_ports -quiet $port_name]
        f50_require {[llength $port] == 1 && [get_property DIRECTION $port] eq "IN" &&
            [get_property IS_BUS $port] == 0} "CDC exact scalar external input missing: $port_name"
        set first [lindex $pins 0]
        set roots [all_fanin -flat -startpoints_only -to $first]
        f50_require {[f50_same_one $roots $port]} "first CDC stage is not driven solely by $port_name"
        # The external input may feed only its own first FF; stages two/three stay timed.
        set endpoints [all_fanout -flat -endpoints_only -from $port]
        f50_require {[f50_same_one $endpoints [list $first]]} "unexpected asynchronous fanout: $port_name"
        for {set index 1} {$index < 3} {incr index} {
            set previous [get_cells -of_objects [lindex $pins [expr {$index-1}]]]
            set target [lindex $pins $index]
            set expected_q [get_pins -of_objects $previous -filter {REF_PIN_NAME == Q}]
            set drivers [get_pins -quiet -leaf -of_objects [get_nets -quiet -of_objects $target] -filter {DIRECTION == OUT}]
            f50_require {[f50_same_one $drivers $expected_q]} "broken direct Q-to-D CDC chain: $port_name"
            set endpoints [all_fanout -flat -endpoints_only -from $expected_q]
            f50_require {[f50_same_one $endpoints [list $target]]} "unexpected CDC Q fanout: $port_name"
            # Vivado's timing startpoint is the launching FF clock pin, not Q.
            # Check this separately; direct-driver equality rejects intervening logic.
            set expected_c [get_pins -of_objects $previous -filter {REF_PIN_NAME == C}]
            set starts [all_fanin -flat -startpoints_only -to $target]
            f50_require {[f50_same_one $starts $expected_c]} "unexpected CDC timing startpoint: $port_name"
            lappend report "$port_name stage$index: direct [get_property NAME [lindex $drivers 0]] -> [get_property NAME $target]; start [get_property NAME [lindex $starts 0]]"
        }
        # Only the external pin to the first D pin is asynchronous. Stages 2/3,
        # the internal TX->RX path and every AXI path remain timed.
        lappend exclusions [list $port $first]
        lappend report "$port_name -> $stage_names; only external-to-first-D excluded"
    }
    f50_require {[llength $used] == 9 && [llength $used_cells] == 9} {nine distinct CDC D pins/cells required}
    # Complete graph validation precedes any side effect. Route revalidation
    # uses apply_exceptions=0 and never repeats a set_false_path call.
    if {$apply_exceptions} {
        foreach pair $exclusions {
            set_false_path -from [lindex $pair 0] -to [lindex $pair 1]
            incr false_paths_applied
        }
        f50_require {$false_paths_applied == 3} {exactly three external-to-first-D false paths required}
    }
    set f [open $report_path {WRONLY CREAT EXCL}]
    puts $f [join $report \n]
    close $f
}
proc write_functional50_cdc_json {path bindings run_id build_id stage} {
    f50_require {[regexp {^[A-Za-z0-9._-]{1,96}$} $run_id] && [regexp {^[0-9a-f]{32}$} $build_id]} {safe exact CDC run/build identity required}
    f50_require {$stage in {synth routed}} {known actual CDC stage required}
    set rows {}
    foreach port_name {yaw_capture_i pitch_capture_i speed_capture_i} {
        set names {}
        foreach name [dict get $bindings $port_name] {
            f50_require {[regexp {^([A-Za-z0-9_./-]|\[[0-9]+\])+$} $name]} {safe literal actual pin required}
            lappend names [format {"%s"} $name]
        }
        lappend rows [format {"%s":[%s]} $port_name [join $names ,]]
    }
    set data [format {{"schema":"FUNCTIONAL50_CDC_BINDINGS_V1","mode":"ACTUAL_NETLIST_THREE_FF_V1","run_id":"%s","build_id":"%s","stage":"%s","bindings":{%s}}} $run_id $build_id $stage [join $rows ,]]
    set f [open $path {WRONLY CREAT EXCL}]; puts $f $data; close $f
}
