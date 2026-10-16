onerror {quit -force -code 8}
onbreak {quit -force -code 7}
run 40 us
puts "MAIN_RUN_BOUND"
quit -force -code 0
