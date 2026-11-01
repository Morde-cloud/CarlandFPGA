# B157 source-only ModelSim 10.7 STD run driver.
# Parent executes this later from calendar_test157:
#   vsim -c -do run_tb.do

set script_dir [pwd]
set tb_file [file join $script_dir tb_deepeye_b04_slot89_first_controls157.sv]
set q012_file [file normalize [file join $script_dir .. .. transport deepeye_q012_scheduler.sv]]
set candidate_file [file normalize [file join $script_dir .. calendar_gate89 deepeye_nominal_uplink_slot_gate_candidate.sv]]
set status_file [file join $script_dir b04_slot89_first_controls157.status]
set work_lib [file join $script_dir work157]

if {![file exists $tb_file] || ![file exists $q012_file] || ![file exists $candidate_file]} {
    puts stderr "RUN_TB_FAIL missing source file"
    exit 1
}

file delete -force $status_file
file delete -force $work_lib

if {[catch {vlib $work_lib} msg]} {
    puts stderr "RUN_TB_FAIL vlib: $msg"
    exit 1
}
if {[catch {vmap work157 $work_lib} msg]} {
    puts stderr "RUN_TB_FAIL vmap: $msg"
    exit 1
}
if {[catch {vlog -sv -work work157 $q012_file} msg]} {
    puts stderr "RUN_TB_FAIL vlog_q012: $msg"
    exit 1
}
if {[catch {vlog -sv -work work157 $candidate_file} msg]} {
    puts stderr "RUN_TB_FAIL vlog_candidate: $msg"
    exit 1
}
if {[catch {vlog -sv -work work157 $tb_file} msg]} {
    puts stderr "RUN_TB_FAIL vlog_tb: $msg"
    exit 1
}
if {[catch {vsim -c -onfinish stop -t 1ps -voptargs=+acc work157.tb_deepeye_b04_slot89_first_controls157} msg]} {
    puts stderr "RUN_TB_FAIL vsim: $msg"
    exit 1
}
if {[catch {run -all} msg]} {
    puts stderr "RUN_TB_FAIL run_all: $msg"
    exit 1
}

if {![file exists $status_file]} {
    puts stderr "RUN_TB_FAIL missing_status_file"
    exit 1
}
set fd [open $status_file r]
set status_text [read $fd]
close $fd
set pass_marker "TEST_PASS completed=1 checked_cases=46 manual_cases=47 review_only_skipped=1"
if {[string first $pass_marker $status_text] < 0} {
    puts stderr "RUN_TB_FAIL missing_exact_pass_marker"
    puts stderr $status_text
    exit 1
}
if {[string first "TEST_FAIL" $status_text] >= 0} {
    puts stderr "RUN_TB_FAIL test_fail_marker"
    puts stderr $status_text
    exit 1
}
puts "RUN_TB_PASS completed=1 checked_cases=46 status=$status_file"
quit -f
