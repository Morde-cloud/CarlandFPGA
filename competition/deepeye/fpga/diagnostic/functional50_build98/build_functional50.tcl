# NEW98 functional50 build Tcl. Source-only; reading this file executes nothing.
# One explicitly authorized run only. Default driver mode is prepare/inspect.
# No old 100 MHz Tcl is sourced; old builder/R20/R21/collector remain untouched.
proc require {condition message} {
    if {![uplevel 1 [list expr $condition]]} {error $message}
}
proc putfile {path data} {
    set f [open $path {WRONLY CREAT EXCL}]
    puts $f $data
    close $f
}
proc one {objects description} {
    require {[llength $objects] == 1} "expected exactly one $description: $objects"
    return [lindex $objects 0]
}
proc busparam {interface name value} {
    set p [ipx::add_bus_parameter $name $interface]
    set_property value $value $p
}
proc expose_core_parameter {core name width} {
    # package_project already infers both objects and the XGUI user->HDL map.
    # Require that actual structure; never fabricate a replacement parameter.
    require {$name eq "BUILD_ID" && $width == 128} {only the selected 128-bit BUILD_ID may be exposed}
    set parameter [one [ipx::get_user_parameters $name -of_objects $core] "user parameter $name"]
    set hdl_parameter [one [ipx::get_hdl_parameters $name -of_objects $core] "HDL parameter $name"]
    foreach object [list $parameter $hdl_parameter] {
        require {[get_property value_format $object] eq "bitString"} {BUILD_ID parameter must remain bitString}
        require {[get_property value_bit_string_length $object] == $width} {BUILD_ID parameter width mismatch}
        require {[regexp {^(0[xX])?0+$} [get_property value $object]]} {BUILD_ID inferred default must remain zero}
    }
    return $parameter
}
proc check_functional50_ports {report_path} {
    set rows [list "port\tdirection\tpackage_pin\tiostandard\tbank\tbonded"]
    set errors {}
    foreach {name pin direction} {yaw_pwm_o W14 OUT pitch_pwm_o Y14 OUT speed_pwm_o T11 OUT yaw_capture_i V16 IN pitch_capture_i W16 IN speed_capture_i V12 IN} {
        set port [get_ports -quiet $name]
        if {[llength $port] != 1} {lappend errors "missing/duplicate port $name"; continue}
        set actual_pin [get_property PACKAGE_PIN $port]
        set actual_direction [get_property DIRECTION $port]
        set standard [get_property IOSTANDARD $port]
        set bank missing; set bonded missing
        if {$actual_pin ne ""} {
            set package [get_package_pins -quiet $actual_pin]
            if {[llength $package] == 1} {
                set bank [get_property BANK $package]
                set bonded [get_property IS_BONDED $package]
            }
        }
        lappend rows "$name\t$actual_direction\t$actual_pin\t$standard\t$bank\t$bonded"
        if {$actual_direction ne $direction || $actual_pin ne $pin || $standard ne "LVCMOS33" || $bank ne "34" || $bonded ne "1"} {
            lappend errors "wrong exact G05 package allocation: $name"
        }
    }
    putfile $report_path [join $rows \n]
    require {[llength $errors] == 0} [join $errors {; }]
}
proc ddr_tsv {value} {
    return [string map [list \\ \\\\ \t \\t \r \\r \n \\n] $value]
}
proc check_ddr72 {ps literal_ddr expected_ddr report_dir stage} {
    require {$stage in {after_board_fclk after_validate}} {unknown DDR check stage}
    set errors {}
    set expected_keys [lsort [dict keys $expected_ddr]]
    set literal_keys [lsort [dict keys $literal_ddr]]
    if {[llength $expected_keys] != 72 || $literal_keys ne $expected_keys} {
        lappend errors {expected/literal DDR tables must have the same exact72 keys}
    }
    set actual_keys {}
    if {[catch {list_property $ps} properties]} {
        lappend errors "DDR property inventory failed: $properties"
    } else {
        foreach key $properties {
            if {[string match CONFIG.PCW_UIPARAM_DDR_* $key]} {lappend actual_keys $key}
        }
        set actual_keys [lsort $actual_keys]
        if {$actual_keys ne $expected_keys} {lappend errors {actual DDR key set differs from expected72}}
    }
    set actual [dict create]
    set differences [dict create]
    set rows [list "key\tboard_literal\tresolved_expected\tactual\tresult"]
    set diff_rows $rows
    foreach key [lsort -unique [concat $expected_keys $actual_keys]] {
        set board_value <missing>; set expected <missing>; set value <missing>; set result exact
        if {[dict exists $literal_ddr $key]} {set board_value [dict get $literal_ddr $key]}
        if {[dict exists $expected_ddr $key]} {set expected [dict get $expected_ddr $key]} else {set result unexpected_key}
        if {$key ni $actual_keys} {
            set result missing_key
        } elseif {[catch {get_property $key $ps} value]} {
            set result read_error
        } elseif {$value ne $expected} {
            set result mismatch
        }
        dict set actual $key $value
        if {$result ne "exact"} {lappend errors "$key: $result"}
        set row "[ddr_tsv $key]\t[ddr_tsv $board_value]\t[ddr_tsv $expected]\t[ddr_tsv $value]\t$result"
        lappend rows $row
        if {$result ne "exact" || $value ne $board_value} {
            dict set differences $key [dict create board_literal $board_value resolved_expected $expected actual $value result $result]
            lappend diff_rows $row
        }
    }
    # Export every value/difference before raising, not just the first mismatch.
    set evidence [dict create stage $stage comparison exact_string_no_numeric_tolerance \
        literal_ddr $literal_ddr expected_ddr $expected_ddr actual_ddr $actual \
        actual_keys $actual_keys differences $differences errors $errors]
    putfile [file join $report_dir ${stage}_ddr72.tcl] [list set ddr_stage_evidence $evidence]
    putfile [file join $report_dir ${stage}_ddr72.tsv] [join $rows \n]
    putfile [file join $report_dir ${stage}_ddr_differences.tsv] [join $diff_rows \n]
    require {[llength $errors] == 0} "DDR72 mismatch at $stage: [join $errors {; }]"
    return $evidence
}
proc f50_timing_number {text description} {
    require {[regexp {^[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?$} $text]} \
        "missing/non-numeric timing metric: $description"
    set value [expr {double($text)}]
    require {$value >= -1.7976931348623157e308 && $value <= 1.7976931348623157e308} \
        "nonfinite timing metric: $description"
    return $value
}
proc f50_design_timing_summary {report_path} {
    set f [open $report_path r]; set text [read $f]; close $f
    set titles [regexp -all -inline -line {^[ \t]*\|?[ \t]*Design Timing Summary[ \t]*$} $text]
    require {[llength $titles] == 1} {exactly one Design Timing Summary section required}
    set expected {WNS(ns) TNS(ns) TNS Failing Endpoints TNS Total Endpoints WHS(ns) THS(ns) THS Failing Endpoints THS Total Endpoints WPWS(ns) TPWS(ns) TPWS Failing Endpoints TPWS Total Endpoints}
    set lines [split $text \n]
    set header_index -1
    set in_design 0
    for {set i 0} {$i < [llength $lines]} {incr i} {
        set line [string trim [lindex $lines $i]]
        set title [string trim [string trimleft $line |]]
        if {$title eq "Design Timing Summary"} {
            set in_design 1
        } elseif {[regexp {^\|[ \t]*[A-Za-z]} $line]} {
            set in_design 0
        }
        if {[regexp {^WNS\(ns\)([ \t]|$)} $line]} {
            require {$in_design && $header_index == -1} {duplicate/out-of-section design summary header}
            set normalized [join [regexp -all -inline {\S+} $line] { }]
            require {$normalized eq $expected} {unsupported/ambiguous Design Timing Summary columns}
            set header_index $i
        }
    }
    require {$header_index >= 0 && $header_index+2 < [llength $lines]} {Design Timing Summary data row missing}
    set separator [string trim [lindex $lines [expr {$header_index+1}]]]
    require {[regexp {^-+([ \t]+-+)+$} $separator]} {design summary column separator missing}
    set row [regexp -all -inline {\S+} [lindex $lines [expr {$header_index+2}]]]
    require {[llength $row] == 12} {exactly one complete twelve-field design summary row required}
    set next [string trim [lindex $lines [expr {$header_index+3}]]]
    require {![regexp {^[+-]?([0-9]|\.[0-9])} $next]} {duplicate design summary data row}
    set result [dict create]
    foreach {key index} {wns_ns 0 tns_ns 1 whs_ns 4 ths_ns 5 wpws_ns 8 tpws_ns 9} {
        dict set result $key [f50_timing_number [lindex $row $index] $key]
    }
    foreach {key index} {setup_failing_endpoints 2 setup_total_endpoints 3 hold_failing_endpoints 6 hold_total_endpoints 7 pulse_failing_endpoints 10 pulse_total_endpoints 11} {
        set value [lindex $row $index]
        require {[regexp {^[0-9]+$} $value]} "invalid endpoint count: $key"
        dict set result $key [expr {wide($value)}]
    }
    require {[dict get $result setup_total_endpoints] > 0 && [dict get $result hold_total_endpoints] > 0} \
        {empty setup/hold endpoint inventory; timing not proven}
    return $result
}
proc f50_check_unconstrained {report_path} {
    set f [open $report_path r]; set text [read $f]; close $f
    set counts {}
    foreach line [split $text \n] {
        if {[regexp {^[ \t]*[0-9]+\.[ \t]+checking unconstrained_internal_endpoints[ \t]+\(([0-9]+)\)[ \t]*$} $line -> count]} {
            lappend counts $count
        }
    }
    # Vivado verbose check_timing emits this in its TOC and detailed section.
    require {[llength $counts] == 2 && [lindex $counts 0] eq [lindex $counts 1]} \
        {missing/ambiguous same-run unconstrained endpoint inventory}
    require {[expr {wide([lindex $counts 0])}] == 0} {unconstrained internal endpoints remain; reports preserved}
}
proc package_ip {sources root core_name top_name display description header_name parameter_name parameter_width} {
    create_project "pack_$core_name" [file join $root "packaging_$core_name"] -part xc7z020clg400-1
    add_files -norecurse $sources
    set_property file_type SystemVerilog [get_files *.sv]
    if {$header_name ne ""} {
        set header [one [get_files */$header_name] "packaged header $header_name"]
        set_property file_type {Verilog Header} $header
        set_property include_dirs [list [file dirname $header]] [current_fileset]
    }
    set_property top $top_name [current_fileset]
    update_compile_order -fileset sources_1
    ipx::package_project -root_dir [file join $root packaged_ip $core_name] -vendor carlandfpga.local -library diagnostic -taxonomy /UserIP -import_files -set_current true
    set core [ipx::current_core]
    set_property name $core_name $core
    set_property version 1.0 $core
    set_property display_name $display $core
    set_property description $description $core
    foreach interface [ipx::get_bus_interfaces -of_objects $core] {
        ipx::remove_bus_interface [get_property NAME $interface] $core
    }
    foreach memory [ipx::get_memory_maps -of_objects $core] {
        ipx::remove_memory_map [get_property NAME $memory] $core
    }
    set axi [ipx::add_bus_interface S_AXI $core]
    set_property interface_mode slave $axi
    set_property bus_type_vlnv xilinx.com:interface:aximm:1.0 $axi
    set_property abstraction_type_vlnv xilinx.com:interface:aximm_rtl:1.0 $axi
    foreach logical {AWADDR AWPROT AWVALID AWREADY WDATA WSTRB WVALID WREADY BRESP BVALID BREADY ARADDR ARPROT ARVALID ARREADY RDATA RRESP RVALID RREADY} {
        set physical s_axi_[string tolower $logical]
        one [ipx::get_ports $physical -of_objects $core] "RTL port $physical"
        set map [ipx::add_port_map $logical $axi]
        set_property physical_name $physical $map
    }
    foreach {name value} {PROTOCOL AXI4LITE DATA_WIDTH 32 ADDR_WIDTH 12 READ_WRITE_MODE READ_WRITE} {
        busparam $axi $name $value
    }
    set memory [ipx::add_memory_map S_AXI $core]
    set block [ipx::add_address_block Reg $memory]
    set_property base_address 0 $block
    set_property range 4096 $block
    set_property width 32 $block
    set_property usage register $block
    set_property access read-write $block
    set_property slave_memory_map_ref S_AXI $axi
    foreach {name physical type} {s_axi_aclk s_axi_aclk clock s_axi_aresetn s_axi_aresetn reset} {
        set interface [ipx::add_bus_interface $name $core]
        set_property interface_mode slave $interface
        set_property bus_type_vlnv xilinx.com:signal:${type}:1.0 $interface
        set_property abstraction_type_vlnv xilinx.com:signal:${type}_rtl:1.0 $interface
        set logical [expr {$type eq "clock" ? "CLK" : "RST"}]
        set map [ipx::add_port_map $logical $interface]
        set_property physical_name $physical $map
        if {$type eq "clock"} {
            busparam $interface ASSOCIATED_BUSIF S_AXI
            busparam $interface ASSOCIATED_RESET s_axi_aresetn
            busparam $interface FREQ_HZ 50000000
        } else {
            busparam $interface POLARITY ACTIVE_LOW
        }
    }
    if {$parameter_name ne ""} {
        expose_core_parameter $core $parameter_name $parameter_width
    }
    ipx::create_xgui_files $core
    ipx::update_checksums $core
    ipx::check_integrity $core
    ipx::save_core $core
    set expected [dict create]
    foreach source $sources {dict set expected [file tail $source] $source}
    set found [dict create]
    set packaged_root [file normalize [file join $root packaged_ip $core_name]]
    foreach group [ipx::get_file_groups -of_objects $core] {
        foreach entry [ipx::get_files -of_objects $group] {
            set name [get_property NAME $entry]
            if {[file extension $name] ni {.sv .svh}} {continue}
            set base [file tail $name]
            require {[dict exists $expected $base]} "unexpected packaged RTL/header: $name"
            set actual [file normalize [file join $packaged_root $name]]
            require {[string first "$packaged_root/" $actual] == 0} {packaged source escaped snapshot}
            set a [open $actual rb]; set actual_bytes [read $a]; close $a
            set b [open [dict get $expected $base] rb]; set original_bytes [read $b]; close $b
            require {$actual_bytes eq $original_bytes} "packaged bytes changed: $base"
            dict set found $base $actual
        }
    }
    require {[lsort [dict keys $found]] eq [lsort [dict keys $expected]]} {incomplete packaged source/header list}
    putfile [file join $root reports "packaged_${core_name}_sources.txt"] $found
    close_project
}
proc full_build {config} {
    global run_root
    source $config
    require {[info exists build_authorized_for_run] && $build_authorized_for_run eq $run_id} {main-verified generated run config required}
    require {[info exists build_id] && [regexp {^[0-9a-f]{32}$} $build_id] && $build_id ne "00000000000000000000000000000000"} {nonzero 128-bit BUILD_ID required}
    require {[info exists cdc_policy] && $cdc_policy eq "ACTUAL_NETLIST_THREE_FF_V1"} {main-selected actual-netlist CDC policy required}
    require {[info exists max_threads] && $max_threads == 2} {exactly two Vivado threads/jobs required}
    set_param general.maxThreads 2
    require {[version -short] eq "2026.1"} {Vivado 2026.1 required}
    putfile [file join $run_root tool_version.txt] [version]
    require {[llength [get_parts -quiet xc7z020clg400-1]] == 1} {target part missing}
    set g05_sources [split [string trim [read [open $g05_source_list r]]] \n]
    set trace_sources [split [string trim [read [open $trace_source_list r]]] \n]
    require {[llength $g05_sources] == 6} {exactly six G05 source/header files required}
    require {[llength $trace_sources] == 14} {exactly fourteen TRACE source/header files required}
    foreach p [concat $g05_sources $trace_sources] {require {[file isfile $p]} "missing source $p"}
    foreach directory {reports artifacts constraints} {file mkdir [file join $run_root $directory]}
    package_ip $g05_sources $run_root deepeye_g05_axi_50 deepeye_g05_axi_50mhz_candidate \
        {DeepEye private G05 50 MHz AXI diagnostic} \
        {Private six-pin G05 50 MHz diagnostic; magic 0x47303550 layout2; no public motion authority} \
        deepeye_g05_curvature_rom_50mhz.svh "" 0
    package_ip $trace_sources $run_root deepeye_trace50_axi deepeye_trace50_axi94 \
        {DeepEye private TRACE50 AXI diagnostic} \
        {Private raw4 fixture AXI endpoint; magic 0x54353046 layout1; internal 1Mbaud TX/RX and 4096-byte FIFO; no external UART} \
        "" BUILD_ID 128
    set_param board.repoPaths [list $board_repo]
    set board_part [one [get_board_parts -quiet tul.com.tw:pynq-z2:part0:1.0] {pinned PYNQ-Z2 board part}]
    set project_dir [file join $run_root functional50_diag project]
    create_project functional50_diag $project_dir -part xc7z020clg400-1
    set_property board_part $board_part [current_project]
    set_property ip_repo_paths [list [file join $run_root packaged_ip]] [current_project]
    update_ip_catalog
    create_bd_design functional50_diag
    set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7_0]
    apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {make_external "FIXED_IO, DDR" apply_board_preset "1"} $ps
    set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 1 CONFIG.PCW_USE_M_AXI_GP1 0 \
        CONFIG.PCW_USE_S_AXI_GP0 0 CONFIG.PCW_USE_S_AXI_GP1 0 CONFIG.PCW_USE_S_AXI_ACP 0 \
        CONFIG.PCW_USE_S_AXI_HP0 0 CONFIG.PCW_USE_S_AXI_HP1 0 CONFIG.PCW_USE_S_AXI_HP2 0 CONFIG.PCW_USE_S_AXI_HP3 0 \
        CONFIG.PCW_EN_CLK0_PORT 1 CONFIG.PCW_EN_RST0_PORT 1 CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ 50 \
        CONFIG.PCW_EN_CLK1_PORT 0 CONFIG.PCW_EN_CLK2_PORT 0 CONFIG.PCW_EN_CLK3_PORT 0 \
        CONFIG.PCW_EN_RST1_PORT 0 CONFIG.PCW_EN_RST2_PORT 0 CONFIG.PCW_EN_RST3_PORT 0] $ps
    foreach property {PCW_USE_M_AXI_GP0 PCW_EN_CLK0_PORT PCW_EN_RST0_PORT} {require {[get_property "CONFIG.$property" $ps] == 1} "required PS7 interface missing: $property"}
    foreach property {PCW_USE_M_AXI_GP1 PCW_USE_S_AXI_GP0 PCW_USE_S_AXI_GP1 PCW_USE_S_AXI_ACP PCW_USE_S_AXI_HP0 PCW_USE_S_AXI_HP1 PCW_USE_S_AXI_HP2 PCW_USE_S_AXI_HP3 PCW_EN_CLK1_PORT PCW_EN_CLK2_PORT PCW_EN_CLK3_PORT PCW_EN_RST1_PORT PCW_EN_RST2_PORT PCW_EN_RST3_PORT} {require {[get_property "CONFIG.$property" $ps] == 0} "unused PS7 interface must be disabled: $property"}
    require {[get_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $ps] == 50} {FCLK0 must be configured at 50MHz}
    source [file join $run_root inputs ddr_expected.tcl]
    check_ddr72 $ps $literal_ddr $expected_ddr [file join $run_root reports] after_board_fclk
    report_property $ps -file [file join $run_root reports ps7_properties.txt]
    set interconnect [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_gp0]
    set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 2] $interconnect
    require {[get_property CONFIG.NUM_SI $interconnect] == 1 && [get_property CONFIG.NUM_MI $interconnect] == 2} {exactly one GP0 slave and two AXI masters required}
    set g05 [create_bd_cell -type ip -vlnv carlandfpga.local:diagnostic:deepeye_g05_axi_50:1.0 g05_50_0]
    set trace [create_bd_cell -type ip -vlnv carlandfpga.local:diagnostic:deepeye_trace50_axi:1.0 trace50_0]
    set private_cells {}
    foreach cell [get_bd_cells -quiet] {
        if {[string match {carlandfpga.local:diagnostic:*} [get_property VLNV $cell]]} {lappend private_cells $cell}
    }
    require {[llength $private_cells] == 2} {exactly two private diagnostic endpoints required; no old G05 or third IP}
    set_property CONFIG.BUILD_ID "0x$build_id" $trace
    require {[string equal -nocase [get_property CONFIG.BUILD_ID $trace] "0x$build_id"]} {TRACE50 BUILD_ID parameter was not accepted by the packaged IP}
    set reset [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_fclk0]
    set_property CONFIG.C_AUX_RESET_HIGH 1 $reset
    set onebit [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 const_one]
    set zerobit [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 const_zero]
    set_property -dict [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 1] $onebit
    set_property -dict [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 0] $zerobit
    connect_bd_intf_net [get_bd_intf_pins ps7_0/M_AXI_GP0] [get_bd_intf_pins axi_gp0/S00_AXI]
    connect_bd_intf_net [get_bd_intf_pins axi_gp0/M00_AXI] [get_bd_intf_pins g05_50_0/S_AXI]
    connect_bd_intf_net [get_bd_intf_pins axi_gp0/M01_AXI] [get_bd_intf_pins trace50_0/S_AXI]
    connect_bd_net [get_bd_pins ps7_0/FCLK_CLK0] [get_bd_pins ps7_0/M_AXI_GP0_ACLK] \
        [get_bd_pins axi_gp0/ACLK] [get_bd_pins axi_gp0/S00_ACLK] [get_bd_pins axi_gp0/M00_ACLK] [get_bd_pins axi_gp0/M01_ACLK] \
        [get_bd_pins g05_50_0/s_axi_aclk] [get_bd_pins trace50_0/s_axi_aclk] [get_bd_pins rst_fclk0/slowest_sync_clk]
    connect_bd_net [get_bd_pins ps7_0/FCLK_RESET0_N] [get_bd_pins rst_fclk0/ext_reset_in]
    connect_bd_net [get_bd_pins const_one/dout] [get_bd_pins rst_fclk0/dcm_locked]
    connect_bd_net [get_bd_pins const_zero/dout] [get_bd_pins rst_fclk0/aux_reset_in] [get_bd_pins rst_fclk0/mb_debug_sys_rst]
    connect_bd_net [get_bd_pins rst_fclk0/interconnect_aresetn] [get_bd_pins axi_gp0/ARESETN]
    connect_bd_net [get_bd_pins rst_fclk0/peripheral_aresetn] [get_bd_pins axi_gp0/S00_ARESETN] \
        [get_bd_pins axi_gp0/M00_ARESETN] [get_bd_pins axi_gp0/M01_ARESETN] \
        [get_bd_pins g05_50_0/s_axi_aresetn] [get_bd_pins trace50_0/s_axi_aresetn]
    set address_space [one [get_bd_addr_spaces ps7_0/Data] {PS GP0 address space}]
    foreach instance {g05_50_0 trace50_0} {
        set target [one [get_bd_addr_segs $instance/S_AXI/Reg] "private 4KiB slave segment $instance"]
        assign_bd_address -target_address_space $address_space -range 4K $target
    }
    set mapped [get_bd_addr_segs -of_objects $address_space]
    require {[llength $mapped] == 2} {exactly two mapped private windows required}
    set windows {}
    foreach segment $mapped {
        set_property range 4096 $segment
        set base [get_property OFFSET $segment]
        set range [get_property RANGE $segment]
        set name [get_property NAME $segment]
        require {[expr {$range}] == 4096} "private aperture must be exactly 4KiB: $name"
        require {[expr {$base}] % 4096 == 0} "private aperture must be 4KiB aligned: $name"
        dict lappend windows $name [dict create base $base range $range segment $segment]
    }
    set g05_mapped [one [get_bd_addr_segs -of_objects $address_space -filter {NAME =~ *g05_50_0*}] {G05 mapped segment}]
    set trace_mapped [one [get_bd_addr_segs -of_objects $address_space -filter {NAME =~ *trace50_0*}] {TRACE mapped segment}]
    set g05_base [expr {[get_property OFFSET $g05_mapped]}]
    set trace_base [expr {[get_property OFFSET $trace_mapped]}]
    set g05_high [expr {$g05_base + 4095}]
    set trace_high [expr {$trace_base + 4095}]
    require {($g05_high < $trace_base) || ($trace_high < $g05_base)} {two 4KiB windows overlap}
    putfile [file join $run_root BD_MAPPING.json] [format {{"bd":"functional50_diag","top":"functional50_diag_wrapper","master":"ps7_0/Data","build_id":"%s","windows":[{"instance":"g05_50_0","vlnv":"carlandfpga.local:diagnostic:deepeye_g05_axi_50:1.0","base":"0x%08X","range":"0x%X","segment":"%s"},{"instance":"trace50_0","vlnv":"carlandfpga.local:diagnostic:deepeye_trace50_axi:1.0","base":"0x%08X","range":"0x%X","segment":"%s"}],"address_assignment":"Vivado auto; host discovers HWH bases","no_guessed_bases":true}} $build_id $g05_base 4096 $g05_mapped $trace_base 4096 $trace_mapped]
    foreach {name port direction} {yaw_pwm_o g05_50_candidate_yaw_pwm_o O pitch_pwm_o g05_50_candidate_pitch_pwm_o O speed_pwm_o g05_50_candidate_speed_pwm_o O yaw_capture_i g05_50_candidate_yaw_capture_i I pitch_capture_i g05_50_candidate_pitch_capture_i I speed_capture_i g05_50_candidate_speed_capture_i I} {
        set external [create_bd_port -dir $direction $name]
        connect_bd_net $external [get_bd_pins g05_50_0/$port]
        set net [one [get_bd_nets -of_objects $external] "external net $name"]
        require {[get_bd_ports -of_objects $net] eq $external} "aliased external connection: $name"
    }
    set interface_names {}
    foreach port [get_bd_intf_ports -quiet] {lappend interface_names [get_property NAME $port]}
    require {[lsort $interface_names] eq {DDR FIXED_IO}} {only DDR/FIXED_IO external interfaces allowed}
    set interface_scalar_names {}
    foreach interface [get_bd_intf_ports -quiet] {
        foreach port [get_bd_ports -quiet -of_objects $interface] {lappend interface_scalar_names [get_property NAME $port]}
    }
    set pl_names {}
    foreach port [get_bd_ports -quiet] {
        set name [get_property NAME $port]
        if {[lsearch -exact $interface_scalar_names $name] < 0} {lappend pl_names $name}
    }
    set expected_pl {yaw_pwm_o pitch_pwm_o speed_pwm_o yaw_capture_i pitch_capture_i speed_capture_i}
    require {[llength $pl_names] == 6} {exactly six external PL ports required; no UART/control pin}
    require {[lsort $pl_names] eq [lsort $expected_pl]} {unexpected top PL port}
    putfile [file join $run_root reports external_ports.txt] [list "interfaces" [lsort $interface_names] "pl_ports" [lsort $pl_names] "all_bd_ports" [lsort [get_bd_ports]]]
    set validation_code [catch {validate_bd_design} validation_message validation_options]
    set ddr_code [catch {check_ddr72 $ps $literal_ddr $expected_ddr [file join $run_root reports] after_validate} ddr_message ddr_options]
    putfile [file join $run_root reports bd_validation_status.tcl] [list set bd_validation_status \
        [dict create return_code $validation_code message $validation_message options $validation_options]]
    if {$validation_code != 0} {return -options $validation_options $validation_message}
    if {$ddr_code != 0} {return -options $ddr_options $ddr_message}
    require {[get_property CONFIG.C_EXT_RESET_HIGH $reset] == 0} {PS reset did not propagate as active low}
    require {[get_property CONFIG.POLARITY [get_bd_pins rst_fclk0/ext_reset_in]] eq "ACTIVE_LOW"} {reset pin polarity mismatch}
    report_property $reset -file [file join $run_root reports reset_properties.txt]
    save_bd_design
    write_bd_tcl [file join $run_root artifacts functional50_diag_bd.tcl]
    set bd_file [one [get_files */functional50_diag.bd] {named private functional50 BD}]
    generate_target all $bd_file
    set wrappers [make_wrapper -files $bd_file -top]
    require {[llength $wrappers] == 1} {exactly one generated wrapper required}
    add_files -norecurse $wrappers
    set_property top functional50_diag_wrapper [current_fileset]
    set xdc [file join $run_root inputs functional50_ports.xdc]
    add_files -fileset constrs_1 -norecurse $xdc
    update_compile_order -fileset sources_1
    launch_runs synth_1 -jobs 2
    wait_on_run synth_1
    require {[get_property STATUS [get_runs synth_1]] eq "synth_design Complete!"} {synthesis did not complete}
    set synthesis_inventory {}
    foreach run [get_runs -filter {IS_SYNTHESIS == 1}] {
        lappend synthesis_inventory "[get_property NAME $run]\t[file normalize [get_property DIRECTORY $run]]\t[get_property STATUS $run]"
    }
    putfile [file join $run_root SYNTHESIS_RUNS.tsv] [join $synthesis_inventory \n]
    open_run synth_1
    check_functional50_ports [file join $run_root reports exact_functional50_package_pins.tsv]
    source [file join $run_root inputs functional50_cdc.tcl]
    set cdc_bindings [discover_functional50_cdc]
    apply_functional50_cdc $cdc_bindings [file join $run_root reports cdc_exact_bindings.txt] 1
    write_functional50_cdc_json [file join $run_root CDC_BINDINGS_ACTUAL.json] $cdc_bindings $run_id $build_id synth
    write_checkpoint [file join $run_root artifacts functional50_diag_synth.dcp]
    opt_design
    place_design
    phys_opt_design -directive AggressiveExplore
    route_design
    write_checkpoint [file join $run_root artifacts functional50_diag_routed.dcp]
    report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file [file join $run_root reports route_timing_summary.txt]
    check_timing -verbose -file [file join $run_root reports route_check_timing.txt]
    report_utilization -file [file join $run_root reports route_utilization.txt]
    report_drc -file [file join $run_root reports route_drc.txt]
    report_clocks -file [file join $run_root reports route_clocks.txt]
    report_route_status -file [file join $run_root reports route_status.txt]
    report_cdc -details -file [file join $run_root reports route_cdc.txt]
    report_rdc -file [file join $run_root reports route_rdc.txt]
    report_exceptions -file [file join $run_root reports route_exceptions.txt]
    report_methodology -file [file join $run_root reports route_methodology.txt]
    write_xdc [file join $run_root constraints implemented.xdc]
    putfile [file join $run_root reports physical_unknowns.txt] {External output propagation, input flight time and cross-channel physical skew unmeasured. No invented IO delay constraints. A alone confirms physical/electrical behavior. Internal UART loopback is not a physical link result.}
    # Retain the routed checkpoint/reports before a CDC revalidation failure.
    set routed_bindings [discover_functional50_cdc]
    foreach port_name {yaw_capture_i pitch_capture_i speed_capture_i} {
        require {[dict get $routed_bindings $port_name] eq [dict get $cdc_bindings $port_name]} {CDC names changed after route; no automatic retarget/retry}
    }
    apply_functional50_cdc $routed_bindings [file join $run_root reports cdc_route_exact_bindings.txt] 0
    write_functional50_cdc_json [file join $run_root CDC_BINDINGS_ROUTED.json] $routed_bindings $run_id $build_id routed
    # Aggregate metrics come only from the ONE same-run routed summary row.
    # TNS/THS are not assumed to be TIMING_PATH properties. No default zeros.
    set summary [f50_design_timing_summary [file join $run_root reports route_timing_summary.txt]]
    foreach name {wns_ns tns_ns whs_ns ths_ns} {set $name [dict get $summary $name]}
    set setup_fail [dict get $summary setup_failing_endpoints]
    set hold_fail [dict get $summary hold_failing_endpoints]
    set drc_errors 0
    set drc_critical 0
    set lutlp1 0
    foreach violation [get_drc_violations] {
        set severity [get_property SEVERITY $violation]
        set vname [get_property NAME $violation]
        if {$severity eq "Error"} {incr drc_errors}
        if {$severity eq "Critical Warning"} {incr drc_critical}
        if {[string match {LUTLP-1*} $vname]} {incr lutlp1}
    }
    set clock_items {}
    set has_20ns 0
    set has_10ns 0
    foreach clock [get_clocks] {
        set period [f50_timing_number [get_property PERIOD $clock] {clock period}]
        require {$period > 0.0} {clock period must be positive}
        set cname [get_property NAME $clock]
        if {abs($period-20.0) <= 0.00001} {set has_20ns 1}
        if {abs($period-10.0) <= 0.00001} {set has_10ns 1}
        set safe_name [string map {\" \\\"} $cname]
        lappend clock_items [format {{"name":"%s","period_ns":%.6f}} $safe_name $period]
    }
    set clocks_json [join $clock_items ,]
    set gate_json [format {{"wns_ns":%.17g,"whs_ns":%.17g,"tns_ns":%.17g,"ths_ns":%.17g,"setup_failing_endpoints":%d,"hold_failing_endpoints":%d,"drc_errors":%d,"drc_critical_warnings":%d,"lutlp1":%d,"has_20ns_clock":%d,"has_10ns_clock":%d,"clocks":[%s],"authoritative_source":"same-run route_timing_summary.txt Design Timing Summary; get_drc_violations/get_clocks"}} \
        $wns_ns $whs_ns $tns_ns $ths_ns $setup_fail $hold_fail $drc_errors $drc_critical $lutlp1 $has_20ns $has_10ns $clocks_json]
    putfile [file join $run_root reports timing_gate.json] $gate_json
    foreach metric {wns_ns tns_ns whs_ns ths_ns wpws_ns tpws_ns} {
        require {[dict get $summary $metric] >= 0.0} "negative design timing metric $metric; reports preserved"
    }
    require {[dict get $summary pulse_failing_endpoints] == 0} {pulse-width failing endpoints remain; reports preserved}
    require {$setup_fail == 0} "setup-failing endpoints remain; reports preserved"
    require {$hold_fail == 0} "hold-failing endpoints remain; reports preserved"
    require {$drc_errors == 0} "DRC errors remain; reports preserved"
    require {$drc_critical == 0} "DRC critical warnings remain; reports preserved"
    require {$lutlp1 == 0} "combinational loop LUTLP-1 present; reports preserved"
    require {$has_20ns == 1} "20ns/50MHz clock constraint missing"
    require {$has_10ns == 0} "unexpected 10ns/100MHz clock in selected50 design"
    f50_check_unconstrained [file join $run_root reports route_check_timing.txt]
    write_bitstream [file join $run_root artifacts functional50_diag.bit]
    set handoffs [concat \
        [glob -nocomplain [file join $project_dir functional50_diag.gen sources_1 bd functional50_diag hw_handoff functional50_diag.hwh]] \
        [glob -nocomplain [file join $project_dir functional50_diag.srcs sources_1 bd functional50_diag hw_handoff functional50_diag.hwh]]]
    set hwh [one $handoffs {same run generated HWH}]
    file copy $hwh [file join $run_root artifacts functional50_diag.hwh]
    putfile [file join $run_root VIVADO_COMPLETE.json] [format {{"run_id":"%s","build_id":"%s","top":"functional50_diag_wrapper","bd":"functional50_diag","part":"xc7z020clg400-1","board_part":"tul.com.tw:pynq-z2:part0:1.0","version":"2026.1","status":"bitstream_complete_pending_hwh_timing_review"}} $run_id $build_id]
    close_project
    puts "FUNCTIONAL50_COMPLETE|$run_id|$build_id"
}
if {[info exists ::functional50_library_only] && $::functional50_library_only} {return}
if {[catch {
    require {$argc == 1} {one generated build_config.tcl argument is required}
    full_build [file normalize [lindex $argv 0]]
} message options]} {
    puts stderr "FUNCTIONAL50_FAILED: $message"
    if {[info exists run_root]} {
        catch {putfile [file join $run_root TCL_ERROR.txt] [dict get $options -errorinfo]}
    }
    catch {close_project}
    exit 1
}
exit 0
