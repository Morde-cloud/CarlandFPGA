# deepeye_uart_frame_tx candidate

Work: `B-UART-FRAME-TX-20261023-26-v1`  
Task: `DEEPEYE-IMPLEMENTATION-20261014/v1`  
Operation: `B-DEEPEYE-UART-FRAME-TX-20261023-26`  
Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1` (H01-H15), canonical
requirements SHA-256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`  
Frozen design: `1011259415a0916054eb580687612580bc1e5f09`  
Accepted dependency: `deepeye_uart_tx.sv`, unchanged SHA-256
`5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47`

This is the candidate internal complete-frame buffer and digital direction-enable
sequencer. It is not a public wire packet format, connector pinout, RS485
electrical approval, arbitration policy, receive path, scheduler, CDC/RDC proof,
timing-closure result or board measurement.

## Interface

Module `deepeye_uart_frame_tx`:

| Direction | Signal | Width | Meaning |
| --- | --- | --- | --- |
| input | `clk` | 1 | Single clock domain |
| input | `rst` | 1 | Synchronous active-high reset, highest priority |
| input | `cancel` | 1 | Synchronous active-high abort, below reset |
| input | `cfg_valid` | 1 | Whole-frame configuration offer |
| output | `cfg_ready` | 1 | Configuration accepted only while idle |
| input | `cfg_count` | 7 | Requested stored length, 1..64 legal |
| input | `s_valid` | 1 | Stored-byte offer |
| output | `s_ready` | 1 | Sample accepted only while receiving |
| input | `s_data` | 8 | Byte written at the current sample index |
| input | `s_last` | 1 | Must be high exactly at index `cfg_count-1` |
| output | `tx` | 1 | Registered 8N1 output from the accepted TX core |
| output | `de` | 1 | Registered direction enable |
| output | `busy` | 1 | A whole-frame reservation is allocated |
| output | `receiving` | 1 | A valid, non-faulted partial frame is being stored |
| output | `faulted` | 1 | Sticky fault status until reset/cancel |
| output | `fault_event` | 1 | One-clock pulse for each newly detected fault |
| output | `fault_code` | 2 | Sticky fault reason, zero when clear |
| output | `stat_admitted` | `STAT_W` | Saturating admitted-frame count |
| output | `stat_sent` | `STAT_W` | Saturating completely retired-frame count |
| output | `stat_aborted` | `STAT_W` | Saturating cancelled-reservation count |
| output | `stat_faults` | `STAT_W` | Saturating new-fault count |

Parameters and legal ranges:

- `CLOCK_HZ`: `2..2147483647`, default `100000000`.
- `BAUD`: `1..floor(CLOCK_HZ/2)`, default `9600`.
- `PRE_CYCLES`: `0..65535`, default `0`.
- `POST_CYCLES`: `0..65535`, default `0`.
- `STAT_W`: `2..32`, default `32`.

Illegal declarations retain legal implementation widths and then issue one
time-zero fatal. Priority is `CLOCK_HZ`, `BAUD`, `PRE_CYCLES`, `POST_CYCLES`,
`STAT_W`, with these exact diagnostics:

```text
deepeye_uart_frame_tx: CLOCK_HZ out of range
deepeye_uart_frame_tx: BAUD out of range
deepeye_uart_frame_tx: PRE_CYCLES out of range
deepeye_uart_frame_tx: POST_CYCLES out of range
deepeye_uart_frame_tx: STAT_W out of range
```

The checks are disabled by `SYNTHESIS` and by synthesis translate-off. Values
passed to the TX core are clamped so a duplicate dependency guard cannot obscure
the frame module's own ordered diagnostic.

## Storage and handshakes

There is exactly one 64-byte `frame_mem` array and one set of finite control
metadata. There is no second payload queue. The sample index is six bits, so
storage addresses are structurally confined to 0..63.

An idle `cfg_valid` handshake reserves the whole frame and increments
`stat_admitted`. Counts 1..64 enter `receiving`; counts 0 or 65..127 instead
reserve a poisoned frame, latch code 1, pulse `fault_event`, increment
`stat_faults`, and enter the sticky fault state. They never assert `de` or feed
the TX core. An explicit `cancel` releases that poisoned reservation.

While receiving, each accepted sample must satisfy:

```text
s_last == (sample_index == cfg_count-1)
```

An early high `s_last`, or a low `s_last` at the final index, latches code 2,
pulses the event, increments the fault counter, stops further acceptance and
keeps the reservation allocated. No byte of the poisoned or partial frame is
transmitted. There is no timeout or guessed resynchronisation. Reset or cancel
is required to leave the fault state.

Configuration and samples are never accepted on the same edge: `s_ready` is low
while the configuration handshake is accepted, and `cfg_ready` is low while the
sample handshake is active. Both ready signals are gated by reset, cancel and
fault. A complete good frame seals on the rising edge that accepts the final
correctly marked sample.

## Direction and transmission timing

Let edge `E` be the rising edge that accepts the final good sample and seals the
frame. The registered DE output rises at edge `E+1`. Let that DE edge be `d`.
The first TX-core admission edge is exactly `d+PRE_CYCLES+1` under ordinary
unstalled-core conditions. With `PRE_CYCLES=0`, a full clock still separates DE
assertion from the first core admission.

The one accepted TX instance receives stored bytes in increasing index order.
After a byte is admitted, the frame controller waits for that byte's completion
before offering the next byte. For byte UART boundary rule
`B(k)=ceil(k*CLOCK_HZ/BAUD)`, the core busy output falls at `A+B(10)` for an
admission edge `A`. The controller observes that fall at the following edge and
admits the next stored byte at `A+B(10)+2`. This two-edge inter-byte turnaround is
the public handshake/state latency; it is not a configured bitrate or throughput
claim.

For the final byte, let `c` be the actual edge where core busy falls. The frame
controller observes that old-high value at `c+1`. It releases registered `de`,
clears `busy`, and increments `stat_sent` exactly at `c+POST_CYCLES+1`. Zero
post guard therefore holds DE for one additional complete clock after core stop
completion. Final retirement is not inferred from the last byte admission. A new
configuration cannot be accepted on the retirement edge; `cfg_ready` rises after
that edge and a handshake can occur on a later edge.

## Reset, cancel and counters

Priority is `reset > cancel > ordinary`. Both are synchronous active-high.

- Reset clears every control register and all four counters, returns `de=0`,
  `busy=0`, `receiving=0`, `faulted=0`, `fault_event=0` and `fault_code=0`, and
  returns the TX core to idle-high `tx`.
- Cancel with a reservation allocated increments `stat_aborted` once, releases
  `busy`, clears DE/fault/control, and truncates any on-wire byte by passing the
  same cancel to the accepted core. Holding cancel does not recount.
- Cancel on the exact final retirement edge wins, recording an abort rather than
  a send.
- Reset overrides cancel and clears even a same-edge abort accounting.
- Admitted, sent and fault counts are preserved across cancel unless the widened
  saturating counter has reached its maximum.

Before saturation, `stat_admitted = stat_sent + stat_aborted + busy` for a
single-reservation implementation. All counters increment through widened math
and saturate independently at `2**STAT_W-1`.

## Verification

`competition/deepeye/tests/rtl/transport/tb_uart_frame_tx.sv` observes only
public ports. Its expected TX waveform is computed from absolute elapsed edges,
the stored byte list and `B(k)=ceil(k*CLOCK_HZ/BAUD)`; it does not read hierarchy,
force state or reuse a DUT output as the oracle. Directed profiles cover:

- every frame length 1..64, all 256 byte values, raw configuration/sample gaps,
  long source silence and the same-edge configuration/sample exclusion;
- zero, one, unequal and maximum `PRE_CYCLES`/`POST_CYCLES`, including exact
  DE-to-admission, final-completion-to-retirement and no-same-edge-completion-
  credit checks;
- invalid counts 0, 65 and 127, early `s_last`, absent final `s_last`, sticky
  fault/event behaviour, no partial transmission and recovery through cancel;
- reset and cancel during receive, seal, pre-guard, byte transmission, between
  bytes, post-guard and the exact retirement edge, plus held cancel, idle cancel,
  reset-over-cancel and synchronous-priority checks;
- saturation at `STAT_W=2` through real invalid-frame aborts and good frames;
- real `100 MHz` examples at 9600, 1200 and 300 baud;
- exact own time-zero fatals and ordered parameter priority for all five
  parameters, including low/high BAUD and STAT_W bounds.

`competition/deepeye/tools/transport/run_uart_frame_tx.py` creates a fresh
`attempt-*` directory below the author evidence root on every invocation. Each
suite gets immutable source snapshots, its own `work` library and its own
TEMP/TMP/TMPDIR/cache directories. `command.json`, separate raw
`stdout.bin`/`stderr.bin`, `process.json`, `vsim.log`, source manifests,
per-suite results and the attempt-level `result.json` retain exact commands,
exits, durations, byte counts and SHA-256 hashes. Failed attempts are never
reused or deleted.

The runner verifies the canonical contract from pinned commit
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, verifies the unchanged accepted TX
dependency hash, requires exact ordered TB markers and complete case-check
totals, and rejects missing/duplicate rows, nonzero ordinary ModelSim tallies,
wrong final counters, timeouts and nonzero process exits. Guard runs accept only
one exact module fatal and its one-error tally. Current Git HEAD is recorded as
provenance only; it is not a success gate.

Reproduction from any checkout of the product worktree:

```powershell
D:\pynq\CarlandFPGA\.local\venv\Scripts\python.exe -B competition/deepeye/tools/transport/run_uart_frame_tx.py --attempt-id <fresh-id>
```

The runner discovers ModelSim from `PATH` by default; use
`--tool-dir <dir>` when the executables are not on `PATH`.

## Limits

This work establishes candidate RTL behaviour only through actual ModelSim
10.7 simulation. It does not establish synthesis, implementation, timing
closure, CDC/RDC, metastability, RS485 electrical compliance, pin direction or
transceiver turnaround, a public packet ABI, arbitration, UART receive, the
concurrent RX author's work, a system integration result or any PYNQ-Z2 board
result. Only machine A operates the physical board, and only the independent
quality main can decide acceptance.
