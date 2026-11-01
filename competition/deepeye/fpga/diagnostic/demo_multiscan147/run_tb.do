# Later-parent ModelSim completion guard for the one focused B147 TB run.
# The TB uses $fatal on any failure/timeout and sets completed=1 only at the
# final pass marker. A fatal is exit 3; completed=0 after run is exit 4.
onerror {quit -code 3 -force}
onbreak {
    if {[catch {examine -radix decimal /tb_deepeye_demo_multiscan147/completed} done]} {
        quit -code 3 -force
    }
    if {$done == 1} {quit -code 0 -force}
    quit -code 4 -force
}
run -all
if {[catch {examine -radix decimal /tb_deepeye_demo_multiscan147/completed} done]} {
    quit -code 3 -force
}
if {$done == 1} {quit -code 0 -force}
quit -code 4 -force
