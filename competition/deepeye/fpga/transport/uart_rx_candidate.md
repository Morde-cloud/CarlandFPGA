# `deepeye_uart_rx` author candidate

Work `B-UART-RX-20261023-25-v1`, operation
`B-DEEPEYE-UART-RX-20261023-25`, under task
`DEEPEYE-IMPLEMENTATION-20261014/v1`.

This document describes the author implementation only. Main owns independent
oracle construction, acceptance, mutation testing, integration, and publication.
The fixed human contract is `DEEPEYE-HUMAN-LOCK-20261014/revision1` (H01-H15),
requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`;
the frozen design input is
`1011259415a0916054eb580687612580bc1e5f09`.

## Interface

`deepeye_uart_rx` is a single-clock, public-port synchronous receiver:

- Inputs: `clk`, `rst`, `cancel`, `rx_async`, `out_ready`.
- Outputs: `out_valid`, `out_data[7:0]`, `busy`, `framing_error_event`,
  `overrun_event`, `false_start_event`, and six saturating counters:
  `stat_frames`, `stat_retired`, `stat_overruns`, `stat_framing`,
  `stat_false_starts`, `stat_aborted`.
- Parameters: `CLOCK_HZ=100000000`, `BAUD=9600`, `STAT_W=32`.

Legal parameter ranges are `CLOCK_HZ=16..2147483647`,
`BAUD=1..floor(CLOCK_HZ/16)`, and `STAT_W=2..32`. Illegal declarations are
clamped to legal arithmetic widths or values before a simulation-only time-zero
`$fatal`. The priority is `CLOCK_HZ`, then `BAUD`, then `STAT_W`, with the exact
message `deepeye_uart_rx: <PARAM> out of range`. The guard is excluded from
synthesis by preprocessor and synthesis-translate directives.

## Receive behavior

`rx_async` drives two `ASYNC_REG`-annotated registers. All decisions use the
older synchronized value. Reset and cancel initialize both stages and the
previous value high, clear the warm-up count, and require two ordinary edges of
warm-up. A new frame requires a qualified observed high followed by an old
`prev_sync=1`, old `sync=0` falling edge. Reset's initialized high cannot itself
qualify a start, so a line held low through reset or cancel cannot create a
frame.

The start edge is time zero. Half boundaries are implemented with a bounded
32-bit phase accumulator adding `2*BAUD`; the first accumulated boundary that
reaches `CLOCK_HZ` implements
`ceil(h*CLOCK_HZ/(2*BAUD))`. The start bit is checked at h1, data bits are
sampled LSB first at h3, h5, ..., h17, and stop is checked at h19. Even half
boundaries do not sample data. The implementation uses no real arithmetic,
delays, file I/O, or dynamic storage.

A high start check, high stop, low stop, and start failure respectively perform
an ordinary receive, a completed frame, a framing event, and a false-start
event. A bad stop emits no byte and a subsequent frame requires a newly
qualified high. Each event is a one-cycle pulse.

## Output and accounting

One completed-byte slot is separate from active reception. A stalled valid
byte remains stable until `out_valid && out_ready`. An old byte retires on that
edge and increments `stat_retired`; a byte completed on the same edge cannot
retire until a later edge. A newly completed byte stores when the slot is empty
or retires concurrently. If a full slot does not retire, the new byte is
dropped, `overrun_event` pulses, and `stat_overruns` increments; the good-stop
frame is still counted. Reception continues under backpressure. Errors and
framing failures do not discard an older pending byte.

Synchronous priority is reset, then cancel, then ordinary operation. Reset
clears all controls, synchronizer state, slot, events, and counters. Cancel
clears controls, slot, synchronizer state, and cycles, preserves non-abort
counters, and adds old `busy + slot_full` to `stat_aborted` with widened
saturation. Held cancel therefore counts a pending partial frame and pending
completed byte only once. Reset overrides cancel. No retirement or sampling
occurs on an abort edge. All counters saturate at `2**STAT_W-1`.

## Author verification

`tests/rtl/transport/tb_uart_rx.sv` observes public ports only and models the
contract independently in the testbench. It covers all 256 byte values at
160/10, 1000/53, and 97/5; qualified idle; false starts; bad-stop recovery and
long low; bad-stop/retirement coincidence; normal and immediate back-to-back
frames; output stalling, overrun, retirement and refill; every cancel and reset
phase; terminal abort coincidence; held cancel; `STAT_W=2` saturation; default
100 MHz 300, 1200, and 9600 baud cases; and exact parameter guards.

`tools/transport/run_uart_rx.py` is the strict portable author runner. It
creates a new author-owned attempt rather than overwriting evidence, snapshots
the exact RTL and testbench, isolates temporary files and simulator working
directories, records actual process arguments, exits, timeouts, versions, and
raw binary stdout/stderr, then checks unique anchored transcript rows and exact
expected counters. ModelSim 10.7 is the executed simulator; no synthesis,
implementation, CDC sign-off, or board result is claimed here.

## Limits

Only binary digital serial stimuli are modeled. This candidate does not prove
metastability resolution, oscillator or baud tolerance, pin voltage or line
qualification, physical CDC timing, ASIC/FPGA synthesis timing closure, a
system integration, or an actual board result. Those are separate integration
and acceptance activities. Main's independent oracle and mutants remain the
acceptance authority.
