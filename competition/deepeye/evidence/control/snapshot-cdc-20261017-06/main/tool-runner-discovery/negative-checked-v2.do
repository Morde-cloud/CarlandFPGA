onerror {quit -force -code 8}
onbreak {quit -force -code 7}
run 20 ns
puts "RUNNER_REACHED_BOUND"
quit -force -code 0
