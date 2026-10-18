onerror {quit -force -code 8}
onbreak {quit -force -code 7}
run 30000000 ns
puts "RUNNER_REACHED_END"
quit -force -code 0
