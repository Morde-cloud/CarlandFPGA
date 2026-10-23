# B operation24: bounded UART 8N1 transmitter

The byte-to-serial TX gap now has synthesizable-style bounded RTL and actual
ModelSim10.7 evidence. One accepted byte emits start, eight LSB-first bits and
stop; exact boundaries are ceil(k*CLOCK_HZ/BAUD). Reset and cancel are synchronous.
No extra input buffering or same-edge completion credit is implied.

Main accepted only the internal RTL simulation scope recorded in ACCEPTANCE.json.
The pre-author absolute-time oracle independently checked every clock of seven
configurations, including100MHz at300/1200/9600baud and integer parameter limits.
Nine exact own-fatal guards and three compiled numeric counterexamples are
included. No old operation was rerun. All29/B04/R03/board/system remain not_run.

RAW_INDEX.json binds each selected original byte in raw-evidence.tar.gz; compiler
scratch/work libraries and waveform scratch are explicitly omitted. Extract only
into a fresh owned folder. Historical failed attempts remain historical. Author
RESULT refers to original runner bytes; SOURCE_BINDING is the final source binding.
The main corrected only the runner's obsolete Git-HEAD gate; actual source hashes
and contract remain checked. Main's first mutant classification was wrong about
the required fatal tally; its failed result is preserved beside raw logs and the
later byte-only reclassification. This did not rerun or change the RTL tests.

Reproduce independently with Python3.12 and ModelSim vlib/vlog/vsim on PATH or
--tools. Run from a fresh owned directory and supply absolute source paths:

```
python -B main_verify_uart_tx.py --rtl deepeye_uart_tx.sv --tb main_tb_uart_tx.sv --out <fresh-run> --tools <modelsim-bin> --clock 97 --baud 11 --stat 32
```

Repeat only desired new verification, with a new output path; use --brief1
(written as --brief 1) for100MHz and baud300/1200/9600. guard_tb.sv and isolated
mutants are in the raw archive. Source paths in historical receipts reflect the
original B worktree; relocate explicit inputs rather than rewriting those receipts.
The author runner also requires the repository contract and TEMP/TMP beneath its
new author attempt directory. Its Git context is now descriptive, not a gate.

This is no A-approved TRACE layout, BOOT/source clock, RX/CDC, RS485 physical
endpoint, shared-budget scheduler, completed B04, synthesis/timing or hardware
test. Physical board remains A-only. H01-H15 and fixed requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 remain unchanged.
