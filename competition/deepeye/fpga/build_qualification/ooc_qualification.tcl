# B06 out-of-context synthesis qualification.
#
# Task DEEPEYE-IMPLEMENTATION-20261014/v1; operation
# B-DEEPEYE-OOC-SYNTHESIS-20261024-33. This script prepares evidence only.
# It does not place, route, generate a bitstream, program hardware, or waive
# synthesis/DRC warnings.

proc emit {line} {
    puts $line
    flush stdout
}

proc require_new_file {path} {
    if {[file exists $path]} {
        error "refusing to overwrite existing output: $path"
    }
}

proc require_nonempty_file {path} {
    if {![file exists $path]} {
        error "required output was not created: $path"
    }
    if {[file size $path] <= 0} {
        error "required output is empty: $path"
    }
}

if {[llength $argv] != 4} {
    puts stderr "B06_OOC_ARGUMENT_ERROR|expected=4|actual=[llength $argv]"
    flush stderr
    exit 2
}

lassign $argv run_dir top_name source_list clock_mode
set run_dir [file normalize $run_dir]
set source_list [file normalize $source_list]
set run_id [file tail $run_dir]
set requested_part "xc7z020clg400-1"

emit "B06_OOC_BEGIN|run_id=$run_id|top=$top_name|clock_mode=$clock_mode"

if {[catch {
    set expected_work [file normalize [file join $run_dir work]]
    set expected_tmp  [file normalize [file join $run_dir tmp]]
    set expected_cache [file normalize [file join $run_dir cache]]
    if {![string equal -nocase [file normalize [pwd]] $expected_work]} {
        error "unexpected process cwd: [pwd]"
    }
    foreach env_name {TEMP TMP TMPDIR} {
        if {![info exists ::env($env_name)]} {
            error "$env_name is not set"
        }
        if {![string equal -nocase [file normalize $::env($env_name)] $expected_tmp]} {
            error "$env_name is not the owned attempt temp directory: $::env($env_name)"
        }
    }
    if {![info exists ::env(XILINX_LOCAL_USER_DATA)]} {
        error "XILINX_LOCAL_USER_DATA is not set"
    }
    if {![file isdirectory $expected_cache]} {
        error "owned XILINX_LOCAL_USER_DATA directory is missing: $expected_cache"
    }
    set observed_cache [file normalize $::env(XILINX_LOCAL_USER_DATA)]
    if {![string equal -nocase $observed_cache $expected_cache]} {
        error "XILINX_LOCAL_USER_DATA is not the exact owned cache directory: $observed_cache"
    }
    emit "B06_OOC_USER_DATA|mode=owned_cache|path=$observed_cache"

    set tool_version [version -short]
    emit "B06_OOC_VERSION|value=$tool_version"
    set matching_parts [get_parts $requested_part]
    if {[llength $matching_parts] != 1} {
        error "expected exactly one part $requested_part, found [llength $matching_parts]"
    }
    emit "B06_OOC_PART|requested=$requested_part|matched=1"

    create_project -in_memory -part $requested_part
    set_param general.maxThreads 2
    set actual_threads [get_param general.maxThreads]
    if {![string equal $actual_threads "2"]} {
        error "general.maxThreads requested 2, actual $actual_threads"
    }
    emit "B06_OOC_THREADS|requested=2|actual=$actual_threads"

    set source_handle [open $source_list r]
    set source_text [read $source_handle]
    close $source_handle
    set sources [list]
    foreach source_line [split [string map [list "\r" ""] $source_text] "\n"] {
        set source_line [string trim $source_line]
        if {$source_line ne ""} {
            lappend sources $source_line
        }
    }
    if {[llength $sources] == 0} {
        error "source list is empty"
    }
    set source_index 0
    foreach source_file $sources {
        if {![file exists $source_file]} {
            error "snapshot source is missing: $source_file"
        }
        read_verilog -sv $source_file
        incr source_index
        emit "B06_OOC_SOURCE_READ|index=$source_index|path=$source_file"
    }
    emit "B06_OOC_SOURCE_COUNT|count=$source_index"

    emit "B06_OOC_SYNTH_BEGIN|top=$top_name|mode=out_of_context|part=$requested_part"
    synth_design -mode out_of_context -part $requested_part -top $top_name
    emit "B06_OOC_SYNTH_DONE|top=$top_name|status=complete"

    set design_part [get_property PART [current_design]]
    if {![string equal -nocase $design_part $requested_part]} {
        error "synthesized part mismatch: $design_part"
    }
    emit "B06_OOC_DESIGN|part=$design_part|port_count=[llength [get_ports]]"

    switch -- $clock_mode {
        "clock:clk" {
            set clock_ports [list clk]
        }
        "dual_clock" {
            set clock_ports [list src_clk dst_clk]
        }
        "none" {
            set clock_ports [list]
        }
        default {
            error "unsupported clock policy: $clock_mode"
        }
    }

    foreach clock_port $clock_ports {
        set matching_ports [get_ports $clock_port]
        if {[llength $matching_ports] != 1} {
            error "clock port $clock_port not found exactly once"
        }
        create_clock -name $clock_port -period 10.000 $matching_ports
        emit "B06_OOC_CLOCK|name=$clock_port|port=$clock_port|period_ns=10.000|status=created"
    }
    if {[llength $clock_ports] == 0} {
        emit "B06_OOC_CLOCK_POLICY|mode=none|reason=combinational_no_clock|constrained=0"
    }

    set reports_dir [file join $run_dir reports]
    file mkdir $reports_dir
    set utilization_report [file join $reports_dir utilization.rpt]
    set timing_report      [file join $reports_dir timing_summary.rpt]
    set check_report       [file join $reports_dir check_timing.rpt]
    set drc_report         [file join $reports_dir drc.rpt]
    set checkpoint         [file join $run_dir ooc.dcp]
    foreach output_path [list $utilization_report $timing_report $check_report $drc_report $checkpoint] {
        require_new_file $output_path
    }

    report_utilization -file $utilization_report
    require_nonempty_file $utilization_report
    emit "B06_OOC_REPORT|kind=utilization|status=written|path=$utilization_report"

    report_timing_summary -file $timing_report
    require_nonempty_file $timing_report
    emit "B06_OOC_REPORT|kind=timing_summary|status=written|diagnostic_only=1|path=$timing_report"

    check_timing -verbose -file $check_report
    require_nonempty_file $check_report
    emit "B06_OOC_REPORT|kind=check_timing|status=written|diagnostic_only=1|path=$check_report"

    report_drc -verbose -no_waivers -file $drc_report
    require_nonempty_file $drc_report
    set drc_violations [get_drc_violations]
    emit "B06_OOC_REPORT|kind=drc|status=written|violation_count=[llength $drc_violations]|path=$drc_report"

    write_checkpoint $checkpoint
    require_nonempty_file $checkpoint
    emit "B06_OOC_CHECKPOINT|status=written|path=$checkpoint"
    emit "B06_OOC_END|run_id=$run_id|top=$top_name|status=artifact_complete"
} error_message error_options]} {
    set safe_message [string map [list "\r" " " "\n" " " "|" "/"] $error_message]
    puts stderr "B06_OOC_TCL_ERROR|run_id=$run_id|top=$top_name|message=$safe_message"
    emit "B06_OOC_END|run_id=$run_id|top=$top_name|status=failed"
    flush stderr
    exit 1
}

exit 0
