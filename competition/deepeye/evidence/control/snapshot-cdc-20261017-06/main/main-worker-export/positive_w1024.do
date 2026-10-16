onerror {quit -force -code 8}
onbreak {quit -force -code 7}
run 600000 ns
puts "RUNNER_REACHED_BOUND w1024"
quit -force -code 0
