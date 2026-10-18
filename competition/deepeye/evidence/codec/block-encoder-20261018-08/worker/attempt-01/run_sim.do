onerror {quit -force -code 8}
onbreak {quit -force -code 7}
run -all
puts "RUNNER_REACHED_END"
quit -force -code 0
