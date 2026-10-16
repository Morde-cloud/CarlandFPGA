onerror {quit -force -code 8}
onbreak {quit -force -code 7}
run 10000 ns
puts "RUNNER_REACHED_BOUND wprobebounds"
quit -force -code 0
