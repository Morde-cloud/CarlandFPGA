# One explicitly authorized full run. No project, device, service or hardware
# interaction happens when merely reading/syntax checking this source.
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
proc check_g05_ports {report_path} {
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
    # Tcl list encoding preserves raw values/errors losslessly; TSV is a view.
    set evidence [dict create stage $stage comparison exact_string_no_numeric_tolerance \
        literal_ddr $literal_ddr expected_ddr $expected_ddr actual_ddr $actual \
        actual_keys $actual_keys differences $differences errors $errors]
    putfile [file join $report_dir ${stage}_ddr72.tcl] [list set ddr_stage_evidence $evidence]
    putfile [file join $report_dir ${stage}_ddr72.tsv] [join $rows \n]
    putfile [file join $report_dir ${stage}_ddr_differences.tsv] [join $diff_rows \n]
    require {[llength $errors] == 0} "DDR72 mismatch at $stage: [join $errors {; }]"
    return $evidence
}
proc package_private {sources root} {
    create_project diag_pack [file join $root packaging_project] -part xc7z020clg400-1
    add_files -norecurse $sources
    set_property file_type SystemVerilog [get_files *.sv]
    set header [one [get_files */deepeye_g05_curvature_rom.svh] {snapshot curvature header}]
    set_property file_type {Verilog Header} $header
    set_property include_dirs [list [file dirname $header]] [current_fileset]
    set_property top deepeye_g05_axi [current_fileset]
    update_compile_order -fileset sources_1
    ipx::package_project -root_dir [file join $root packaged_ip] -vendor carlandfpga.local -library diagnostic -taxonomy /UserIP -import_files -set_current true
    set core [ipx::current_core]
    set_property name deepeye_g05_axi $core
    set_property version 1.0 $core
    set_property display_name {DeepEye private AXI digital diagnostic} $core
    set_property description {Private six-pin G05 capture diagnostic; no public motion authority} $core
    # Replace inferred metadata, leaving all six source/header files unchanged.
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
            busparam $interface FREQ_HZ 100000000
        } else {
            busparam $interface POLARITY ACTIVE_LOW
        }
    }
    ipx::create_xgui_files $core
    ipx::update_checksums $core
    ipx::check_integrity $core
    ipx::save_core $core
    # Imported synthesis/simulation files must be actual byte-exact packaged inputs.
    set expected [dict create]
    foreach source $sources {dict set expected [file tail $source] $source}
    set found [dict create]
    foreach group [ipx::get_file_groups -of_objects $core] {
        foreach entry [ipx::get_files -of_objects $group] {
            set name [get_property NAME $entry]
            if {[file extension $name] ni {.sv .svh}} {continue}
            set base [file tail $name]
            require {[dict exists $expected $base]} "unexpected packaged RTL/header: $name"
            set actual [file normalize [file join $root packaged_ip $name]]
            require {[string first "[file normalize [file join $root packaged_ip]]/" $actual] == 0} {packaged source escaped snapshot}
            set a [open $actual rb]; set actual_bytes [read $a]; close $a
            set b [open [dict get $expected $base] rb]; set original_bytes [read $b]; close $b
            require {$actual_bytes eq $original_bytes} "packaged bytes changed: $base"
            dict set found $base $actual
        }
    }
    require {[lsort [dict keys $found]] eq [lsort [dict keys $expected]]} {incomplete packaged source/header list}
    require {[file dirname [dict get $found deepeye_g05_command_map.sv]] eq [file dirname [dict get $found deepeye_g05_curvature_rom.svh]]} {mapper header not colocated inside packaged input}
    putfile [file join $root reports packaged_sources.txt] $found
    close_project
}
proc full_build {config} {
    global run_root
    source $config
    require {[info exists build_authorized_for_run] && $build_authorized_for_run eq $run_id} {main-authorized generated run config required}
    require {[info exists cdc_bindings] && [dict size $cdc_bindings] == 3} {accepted exact CDC pin bindings required}
    set_param general.maxThreads 2
    require {[version -short] eq "2026.1"} {Vivado 2026.1 required}
    putfile [file join $run_root tool_version.txt] [version]
    require {[llength [get_parts -quiet xc7z020clg400-1]] == 1} {target part missing}
    set f [open $source_list r]
    set sources [split [string trim [read $f]] \n]
    close $f
    require {[llength $sources] == 6} {six main-accepted source/header files required}
    foreach p $sources {require {[file isfile $p]} "missing source $p"}
    foreach directory {reports artifacts constraints} {file mkdir [file join $run_root $directory]}
    package_private $sources $run_root
    set_param board.repoPaths [list $board_repo]
    set board_part [one [get_board_parts -quiet tul.com.tw:pynq-z2:part0:1.0] {pinned PYNQ-Z2 board part}]
    set project_dir [file join $run_root g05_diag project]
    create_project g05_diag $project_dir -part xc7z020clg400-1
    set_property board_part $board_part [current_project]
    set_property ip_repo_paths [list [file join $run_root packaged_ip]] [current_project]
    update_ip_catalog
    create_bd_design g05_diag
    set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7_0]
    # Use the actual hashed board preset for all PS7 DDR/MIO electrical settings.
    apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {make_external "FIXED_IO, DDR" apply_board_preset "1"} $ps
    set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 1 CONFIG.PCW_USE_M_AXI_GP1 0 \
        CONFIG.PCW_USE_S_AXI_GP0 0 CONFIG.PCW_USE_S_AXI_GP1 0 CONFIG.PCW_USE_S_AXI_ACP 0 \
        CONFIG.PCW_USE_S_AXI_HP0 0 CONFIG.PCW_USE_S_AXI_HP1 0 CONFIG.PCW_USE_S_AXI_HP2 0 CONFIG.PCW_USE_S_AXI_HP3 0 \
        CONFIG.PCW_EN_CLK0_PORT 1 CONFIG.PCW_EN_RST0_PORT 1 CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ 100 \
        CONFIG.PCW_EN_CLK1_PORT 0 CONFIG.PCW_EN_CLK2_PORT 0 CONFIG.PCW_EN_CLK3_PORT 0 \
        CONFIG.PCW_EN_RST1_PORT 0 CONFIG.PCW_EN_RST2_PORT 0 CONFIG.PCW_EN_RST3_PORT 0] $ps
    source [file join $run_root inputs ddr_expected.tcl]
    check_ddr72 $ps $literal_ddr $expected_ddr [file join $run_root reports] after_board_fclk
    report_property $ps -file [file join $run_root reports ps7_properties.txt]
    set interconnect [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 axi_gp0]
    set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 1] $interconnect
    set slave [create_bd_cell -type ip -vlnv carlandfpga.local:diagnostic:deepeye_g05_axi:1.0 g05_diag_0]
    set reset [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_fclk0]
    # PS FCLK_RESET0_N is active low; no fabric MMCM/PLL needs a lock input.
    # dcm_locked=1 is intentional for a direct PS FCLK, not a fabricated lock.
    # C_EXT_RESET_HIGH is propagate-only in this installed IP. The connected
    # PS FCLK_RESET0_N supplies ACTIVE_LOW; verify the derived value after BD
    # validation instead of trying to write a read-only parameter.
    set_property CONFIG.C_AUX_RESET_HIGH 1 $reset
    set onebit [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 const_one]
    set zerobit [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 const_zero]
    set_property -dict [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 1] $onebit
    set_property -dict [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 0] $zerobit
    connect_bd_intf_net [get_bd_intf_pins ps7_0/M_AXI_GP0] [get_bd_intf_pins axi_gp0/S00_AXI]
    connect_bd_intf_net [get_bd_intf_pins axi_gp0/M00_AXI] [get_bd_intf_pins g05_diag_0/S_AXI]
    connect_bd_net [get_bd_pins ps7_0/FCLK_CLK0] [get_bd_pins ps7_0/M_AXI_GP0_ACLK] \
        [get_bd_pins axi_gp0/ACLK] [get_bd_pins axi_gp0/S00_ACLK] [get_bd_pins axi_gp0/M00_ACLK] \
        [get_bd_pins g05_diag_0/s_axi_aclk] [get_bd_pins rst_fclk0/slowest_sync_clk]
    connect_bd_net [get_bd_pins ps7_0/FCLK_RESET0_N] [get_bd_pins rst_fclk0/ext_reset_in]
    connect_bd_net [get_bd_pins const_one/dout] [get_bd_pins rst_fclk0/dcm_locked]
    connect_bd_net [get_bd_pins const_zero/dout] [get_bd_pins rst_fclk0/aux_reset_in] [get_bd_pins rst_fclk0/mb_debug_sys_rst]
    connect_bd_net [get_bd_pins rst_fclk0/interconnect_aresetn] [get_bd_pins axi_gp0/ARESETN]
    connect_bd_net [get_bd_pins rst_fclk0/peripheral_aresetn] [get_bd_pins axi_gp0/S00_ARESETN] \
        [get_bd_pins axi_gp0/M00_ARESETN] [get_bd_pins g05_diag_0/s_axi_aresetn]
    set address_space [one [get_bd_addr_spaces ps7_0/Data] {PS GP0 address space}]
    set target [one [get_bd_addr_segs g05_diag_0/S_AXI/Reg] {private 4KiB slave segment}]
    # Let Vivado allocate the absolute base; the host must discover this mapping.
    assign_bd_address -target_address_space $address_space -range 4K $target
    set mapped [one [get_bd_addr_segs -of_objects $address_space] {mapped private slave}]
    # Automatic placement selected a 64KiB default in the first actual run.
    # Keep its discovered base, then explicitly size the mapped master segment.
    set_property range 4096 $mapped
    set base [get_property OFFSET $mapped]
    set range [get_property RANGE $mapped]
    require {[expr {$range}] == 4096} {private aperture must be exactly 4KiB}
    putfile [file join $run_root BD_MAPPING.json] [format {{"instance":"g05_diag_0","vlnv":"carlandfpga.local:diagnostic:deepeye_g05_axi:1.0","base":"0x%08X","range":"0x%X","bd":"g05_diag","top":"g05_diag_wrapper","master":"ps7_0/Data","slave":"g05_diag_0/S_AXI/Reg","segment":"%s"}} [expr {$base}] [expr {$range}] $mapped]
    foreach {name direction} {yaw_pwm_o O pitch_pwm_o O speed_pwm_o O yaw_capture_i I pitch_capture_i I speed_capture_i I} {
        set external [create_bd_port -dir $direction $name]
        connect_bd_net $external [get_bd_pins g05_diag_0/$name]
        set net [one [get_bd_nets -of_objects $external] "external net $name"]
        require {[get_bd_pins -of_objects $net] eq [get_bd_pins g05_diag_0/$name]} "unexpected internal connection: $name"
        require {[get_bd_ports -of_objects $net] eq $external} "aliased external connection: $name"
    }
    set interface_names {}
    foreach port [get_bd_intf_ports -quiet] {lappend interface_names [get_property NAME $port]}
    require {[lsort $interface_names] eq {DDR FIXED_IO}} {only DDR/FIXED_IO external interfaces allowed}
    set allowed [get_bd_ports -of_objects [get_bd_intf_ports]]
    foreach name {yaw_pwm_o pitch_pwm_o speed_pwm_o yaw_capture_i pitch_capture_i speed_capture_i} {lappend allowed [get_bd_ports $name]}
    require {[lsort [get_bd_ports]] eq [lsort $allowed]} {unexpected top PL port}
    putfile [file join $run_root reports external_ports.txt] [lsort $allowed]
    set validation_code [catch {validate_bd_design} validation_message validation_options]
    # Retain a post-validation table even when validate_bd_design itself fails.
    set ddr_code [catch {check_ddr72 $ps $literal_ddr $expected_ddr [file join $run_root reports] after_validate} ddr_message ddr_options]
    putfile [file join $run_root reports bd_validation_status.tcl] [list set bd_validation_status \
        [dict create return_code $validation_code message $validation_message options $validation_options]]
    if {$validation_code != 0} {return -options $validation_options $validation_message}
    if {$ddr_code != 0} {return -options $ddr_options $ddr_message}
    require {[get_property CONFIG.C_EXT_RESET_HIGH $reset] == 0} {PS reset did not propagate as active low}
    require {[get_property CONFIG.POLARITY [get_bd_pins rst_fclk0/ext_reset_in]] eq "ACTIVE_LOW"} {reset pin polarity mismatch}
    report_property $reset -file [file join $run_root reports reset_properties.txt]
    save_bd_design
    write_bd_tcl [file join $run_root artifacts g05_diag_bd.tcl]
    set bd_file [one [get_files */g05_diag.bd] {named private diagnostic BD}]
    generate_target all $bd_file
    set wrappers [make_wrapper -files $bd_file -top]
    require {[llength $wrappers] == 1} {exactly one generated wrapper required}
    add_files -norecurse $wrappers
    set_property top g05_diag_wrapper [current_fileset]
    set xdc [file join $run_root inputs g05_ports.xdc]
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
    check_g05_ports [file join $run_root reports exact_g05_package_pins.tsv]
    source [file join $run_root inputs g05_cdc.tcl]
    apply_g05_cdc $cdc_bindings [file join $run_root reports cdc_exact_bindings.txt]
    write_checkpoint [file join $run_root artifacts g05_diag_synth.dcp]
    opt_design
    place_design
    route_design
    write_checkpoint [file join $run_root artifacts g05_diag_routed.dcp]
    report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file [file join $run_root reports route_timing_summary.txt]
    check_timing -verbose -file [file join $run_root reports route_check_timing.txt]
    report_utilization -file [file join $run_root reports route_utilization.txt]
    report_drc -file [file join $run_root reports route_drc.txt]
    report_clocks -file [file join $run_root reports route_clocks.txt]
    report_route_status -file [file join $run_root reports route_status.txt]
    report_cdc -details -file [file join $run_root reports route_cdc.txt]
    report_exceptions -file [file join $run_root reports route_exceptions.txt]
    putfile [file join $run_root reports physical_unknowns.txt] {External output propagation, input flight time and cross-channel physical skew unmeasured. No invented IO delay constraints. This run cannot establish G05/B06 full external timing.}
    report_methodology -file [file join $run_root reports route_methodology.txt]
    write_xdc [file join $run_root constraints implemented.xdc]
    foreach delay {max min} {
        set paths [get_timing_paths -delay_type $delay -max_paths 1]
        require {[llength $paths] == 1} "no $delay timing paths; timing not proven"
        require {[get_property SLACK $paths] >= 0} "$delay timing failed; reports preserved"
    }
    set has_100mhz 0
    foreach clock [get_clocks] {
        if {abs(double([get_property PERIOD $clock])-10.0) < 0.00001} {set has_100mhz 1}
    }
    require {$has_100mhz} {100MHz FCLK constraint missing}
    foreach violation [get_drc_violations] {
        require {[get_property SEVERITY $violation] ne "Error"} "DRC error: $violation"
    }
    write_bitstream [file join $run_root artifacts g05_diag.bit]
    set handoffs [concat \
        [glob -nocomplain [file join $project_dir g05_diag.gen sources_1 bd g05_diag hw_handoff g05_diag.hwh]] \
        [glob -nocomplain [file join $project_dir g05_diag.srcs sources_1 bd g05_diag hw_handoff g05_diag.hwh]]]
    set hwh [one $handoffs {same run generated HWH}]
    file copy $hwh [file join $run_root artifacts g05_diag.hwh]
    putfile [file join $run_root VIVADO_COMPLETE.json] [format {{"run_id":"%s","top":"g05_diag_wrapper","bd":"g05_diag","part":"xc7z020clg400-1","version":"2026.1","status":"bitstream_complete_pending_hwh_check_and_main_review"}} $run_id]
    close_project
    puts "G05_DIAG_COMPLETE|$run_id"
}
if {[info exists ::g05_library_only] && $::g05_library_only} {return}
if {[catch {
    require {$argc == 1} {one generated build_config.tcl argument is required}
    full_build [file normalize [lindex $argv 0]]
} message options]} {
    puts stderr "G05_DIAG_FAILED: $message"
    if {[info exists run_root]} {
        catch {putfile [file join $run_root TCL_ERROR.txt] [dict get $options -errorinfo]}
    }
    catch {close_project}
    exit 1
}
exit 0
