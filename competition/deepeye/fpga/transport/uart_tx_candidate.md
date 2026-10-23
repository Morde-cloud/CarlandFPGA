# deepeye_uart_tx candidate

Work: `B-UART-TX-20261023-24-v1`  
Task: `DEEPEYE-IMPLEMENTATION-20261014/v1`  
Operation: `B-DEEPEYE-UART-TX-20261023-24`  
Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1` (H01-H15), requirements
SHA-256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`  
Frozen design: `1011259415a0916054eb580687612580bc1e5f09`

This is a candidate internal RTL block. It is not a public ABI, connector pin
assignment, clock calibration result, direction-enable policy, message framing
definition, receive path, scheduler or board measurement.

## Interface

Module `deepeye_uart_tx`:

| Direction | Signal | Width | Meaning |
| --- | --- | --- | --- |
| input | `clk` | 1 | Single clock domain |
| input | `rst` | 1 | Synchronous active-high reset, highest priority |
| input | `cancel` | 1 | Synchronous active-high abort, below reset |
| input | `in_valid` | 1 | Offered byte |
| output | `in_ready` | 1 | `!rst && !cancel && !busy` |
| input | `in_data` | 8 | Byte latched on admission |
| output | `tx` | 1 | Registered serial output, high when idle |
| output | `busy` | 1 | Registered transmitter occupancy |
| output | `stat_accepted` | `STAT_W` | Saturating accepted-byte count |
| output | `stat_completed` | `STAT_W` | Saturating completed-byte count |
| output | `stat_aborted` | `STAT_W` | Saturating cancelled-byte count |

Parameters and legal ranges:

- `CLOCK_HZ`: `2..2147483647`, default `100000000`.
- `BAUD`: `1..floor(CLOCK_HZ/2)`, default `9600`.
- `STAT_W`: `2..32`, default `32`.

Illegal declarations retain legal implementation widths and then execute one
time-zero fatal. The priority is `CLOCK_HZ`, `BAUD`, `STAT_W`, with exact
messages:

```text
deepeye_uart_tx: CLOCK_HZ out of range
deepeye_uart_tx: BAUD out of range
deepeye_uart_tx: STAT_W out of range
```

The checks are disabled by `SYNTHESIS` and by synthesis translate-off.

## Transfer semantics

An admission at rising edge `t=0` immediately drives start `0`, latches all
eight data bits and sets registered `busy`. The phase accumulator starts at
zero for that byte. On each subsequent edge it adds `BAUD`; the first edge on
which the sum reaches `CLOCK_HZ` is boundary `k`, exactly:

```text
ceil(k * CLOCK_HZ / BAUD)
```

The programmed minimum legal ratio makes the shortest bit two clock periods.
Boundaries 1 through 8 select `data[0]` through `data[7]`; boundary 9 selects
stop `1`; boundary 10 clears `busy` and increments `stat_completed`. The phase
remainder is retained only within the byte and reset to zero at each new
admission, so idle time has no accumulated credit.

`rst` clears every counter and returns `busy=0`, `tx=1`. `cancel` discards the
one active byte, clears phase/busy, forces `tx=1`, and increments
`stat_aborted` once with saturation. Holding `cancel` does not count again.
Reset overrides cancel. A cancel on the final completion edge records an abort,
not a completion. Accepted and completed counts survive cancel. All three
counters saturate independently at `2**STAT_W-1`.

The output is registered and is not combinationally gated by cancel. A new
byte cannot be accepted on the completion edge; after that edge `in_ready`
rises and admission is possible on the next rising edge.

## Directed verification

`competition/deepeye/tests/rtl/transport/tb_uart_tx.sv` observes public ports
only. Its golden tx level is a function of absolute elapsed edges and the
ceiling formula, not internal phase state. Profiles cover:

- all 256 byte values at `97/11`, `31/3`, and the minimum legal `2/1` ratio;
- default `100 MHz / 9600`, plus representative `100 MHz / 300` and
  `100 MHz / 1200` frames;
- long idle, held `in_valid`, changing data while busy, and no same-edge
  completion credit;
- cancel and reset at every one of the ten bit boundaries, held cancel, two
  aborting bytes, idle cancel, reset-over-cancel, and immediate recovery;
- `STAT_W=2` saturation through real transfers, completion and cancellation;
- exact invalid-parameter fatals and priority through guard tops.

The three smaller-ratio profiles compare every baud-interval edge. Because
300-baud frames span more than three million clocks each, the three long frame
profiles sample the clock just before each of the ten boundaries and at that
boundary, while still deriving both samples from absolute elapsed edges.

The strict runner is
`competition/deepeye/tools/transport/run_uart_tx.py`. It creates a fresh
attempt below `competition/deepeye/evidence/transport/uart-tx-20261023-24/author/`,
copies immutable source snapshots into each suite, and runs the actual ModelSim
`vlib`, `vlog`, and `vsim` executables with the suite directory as cwd. Raw
stdout and stderr are separate byte files. The runner rejects nonzero exits,
timeouts, missing or duplicate anchored rows, malformed case order, check-count
disagreement, nonzero ordinary tallies and wrong final counters. Guard suites
accept only the module's own exact fatal and its expected one-error tally.

Reproduction from the product worktree, with `TEMP` and `TMP` under the author
evidence tree and bytecode disabled:

```powershell
$env:TEMP='D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014\competition\deepeye\evidence\transport\uart-tx-20261023-24\author'
$env:TMP=$env:TEMP
$env:PYTHONDONTWRITEBYTECODE='1'
D:\pynq\CarlandFPGA\.local\venv\Scripts\python.exe -B competition/deepeye/tools/transport/run_uart_tx.py --attempt-id <fresh-id>
```

The persisted attempt's `result.json`, per-step `command.json` and
`process.json`, separate `stdout.bin`/`stderr.bin`, `vsim.log`, and suite source
snapshots are the evidence to inspect. `author/RESULT.json` is the concise
author handoff.

## Limits

This work establishes candidate RTL behavior only through ModelSim simulation.
It does not establish synthesis, implementation, timing closure, CDC/RDC,
metastability, pin or clock calibration, RS485 direction control, UART receive,
message framing, buffering, scheduling, shared budgets, a public ABI, or a
PYNQ-Z2 board result. Only the independent quality main can decide acceptance.
