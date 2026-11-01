Final source 746e296ccfd39d1ba7db1e477879fcc33fabeea9

Actual commands from the bounded ModelSim/PC join, exit 0 each:

```text
D:\pynq\CarlandFPGA\.local\venv\Scripts\python.exe -B -X utf8 D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\tools\diagnostic\demo_multiscan147\verify_upload147.py --wire D:\pynq\CarlandFPGA\.local\vmulti152\four_actual_frames.bin --out D:\pynq\CarlandFPGA\.local\vmulti152\pc-result
D:\modelsim1\win64\vlib.exe work
D:\modelsim1\win64\vlog.exe -version
D:\modelsim1\win64\vlog.exe -sv -work work D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\fpga\codec\deepeye_block_encoder.sv D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\fpga\codec\deepeye_trace_payload_candidate.sv D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\fpga\transport\deepeye_crc16_byte.sv D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\fpga\transport\deepeye_wire_serializer.sv D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\fpga\transport\deepeye_uart_tx.sv D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\fpga\transport\deepeye_uart_rx.sv D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\fpga\diagnostic\g05_capture\additive50_source_candidate\rtl\deepeye_trace_block_payload_1us_candidate.sv D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\fpga\diagnostic\g05_capture\additive50_source_candidate\rtl\deepeye_trace_block_uart_50mhz_candidate.sv D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\fpga\diagnostic\offboard_aggregate77\deepeye_aggregate12_candidate.sv D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\fpga\diagnostic\demo_multiscan147\deepeye_demo_multiscan147.sv D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\fpga\diagnostic\demo_multiscan147\tb_deepeye_demo_multiscan147.sv
D:\modelsim1\win64\vmap.exe -c
D:\modelsim1\win64\vsim.exe -version
D:\modelsim1\win64\vsim.exe -c -voptargs=+acc -onfinish stop -l modelsim.log -wlf wave.wlf work.tb_deepeye_demo_multiscan147 +bytefile=actual_bytes.txt +logfile=tb.log -do do D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/fpga/diagnostic/demo_multiscan147/run_tb.do
```

The raw archive includes stdout/stderr, Job records and before-run freezes for failed 150/151 and passed 152. All source bundles are synthetic. Physical and formal stages remain open.
