onerror {quit -force -code 8}
onbreak {quit -force -code 7}
run 1500000 ns
puts "RUNNER_REACHED_BOUND wneg"
quit -force -code 0
