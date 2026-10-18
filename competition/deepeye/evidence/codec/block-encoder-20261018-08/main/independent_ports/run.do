onerror {quit -code 8}
onbreak {quit -code 7}
vsim -voptargs=+acc work.main_encoder_port_tb {+INPUT=D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/independent-completion-audit-20261018-v1/main-final-review/cases.txt} {+OUTPUT=D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/independent-completion-audit-20261018-v1/main-final-review/ports.txt}
run -all
quit -code 0
