onerror {quit -force -code 8}
onbreak {quit -force -code 7}
run 20 ns
if {[examine -radix decimal sim:/smoke/done] != 1} {quit -force -code 9}
puts "RUNNER_CHECK_PASSED"
quit -force -code 0
