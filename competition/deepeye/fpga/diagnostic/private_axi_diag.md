# Private AXI diagnostic, slice 53

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-MINIMAL-PL-AXI-20261025-53-v1`. This is the main-selected private source4
digital diagnostic. It adds no public overlay ABI, external IO, UART, TRACE,
PWM, sensor-validity rule or control policy. The quality main owns design
decisions and acceptance. A alone operates the physical board.

H01–H15 remain mandatory under `DEEPEYE-HUMAN-LOCK-20261014/revision1`, pinned
at `f5989cd5defce561f9ba98e6b18fc2682945f0a2`; canonical requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
The full 3D/UI, volume collisions, free camera/editing/random layouts,
free/equal blue/red entry/exit gates and complete passage, hidden truth,
device-bounded causal observations, online 3D decisions, substantive PC AI,
and PC_DIRECT plus FPGA-output paths remain required. This module and its
author regression do not accept those product requirements. All 29 formal
items, R03, full product, synthesis, implementation, bitstream and board work
are `not_run` in this slice. Slice54 prepares separate build files; this slice
does not authorize or run a full build.

## Interface and lifecycle

`deepeye_private_axi_diag` has one clock `s_axi_aclk` and synchronous active-low
`s_axi_aresetn`. Address is 12-bit byte-addressed, data 32 bits, WSTRB four
bits, AWPROT/ARPROT three bits (accepted without privilege semantics), and
BRESP/RRESP two bits. There is one independent outstanding write and read.
AW and W are latched separately, in either order. A later edge commits the
pair exactly once when no B response is pending. READY does not depend on
VALID. B and R payloads remain stable until their respective handshakes.

The downstream reset is explicitly registered on this same clock. Bus
admission waits for it to clear after reset release. Reset drops pending
AW/W/B/AR/R, clears all application state, tag history and counters. This is
a synchronous-reset design and provides no asynchronous CDC/RDC proof.

START requires a stopped session and a nonzero staged tag different from
the immediately previous successful tag. START increments generation without
wrapping, clears all 13 freshness bits, and produces a rearm pulse after the
stopped pipeline is released. Running is reported only when capture is armed.
Tag history retains only the last successful tag until full reset; it makes
no infinite-history claim. STOP preserves generation and cumulative counters.

TRIGGER requires running/armed, idle/no result, all 13 words freshly written
with full WSTRB since START or the previous successful TRIGGER, a remaining
trigger ID and four nonwrapping capture sequence numbers. It freezes the
entire scan and emits channel 0,1,2,3 on four subsequent clocks into the
unchanged capture39 → queue → lane44 chain. No stage write is allowed while
busy. Each actual lane VALID/READY handshake copies one result into separate
stable registers. Explicit ACK releases that result; the next lane can latch
on a later edge. Busy ends only at the fourth ACK. The original opaque host
QPC `tick64` and quality bytes are transported exactly, without converting
PL cycles or readback time into acquisition provenance.

STOP is valid only at aligned CONTROL with WSTRB[0] enabled and WDATA[0] set.
It dominates every other command bit and ignores the other strobes. It
cancels capture, queue, lane, feeder and result on that write-commit edge,
clears active/staged tag, stage values/freshness, busy and session, and clears
the diagnostic fault/error. It retains last successful tag, generation and
cumulative counters. An already accepted AXI R response remains a stale but
stable snapshot through STOP. Software must discard it and recheck current
session/status. Reset is the sole response-dropping exception.

Unexpected capture order/overrun/exhaustion stops and cancels the pipeline,
with a sticky fault and diagnostic error. The expected sequence-terminal
event of a complete scan starting at `0xfffffffc` is allowed; no later trigger
can wrap. Lane channel/tag/sequence/last identity is checked before publishing;
its alarm is registered to avoid a combinational VALID/cancel loop. A bad lane
never becomes a valid result. STOP (or full reset) is required to clear a
fatal fault before a new START. Invalid accesses otherwise return SLVERR and
preserve application state; rejected writes update only `LAST_ERROR`.

## Registers

All offsets are relative to this private slave. Unknown/unaligned accesses
return SLVERR, reads with zero data. CONTROL is write-only; reading it returns
SLVERR. All non-STOP writes require WSTRB `1111`. Staging writes cannot be
partial. Reading a staging word does not make it fresh.

| Offset | Access | Value |
| --- | --- | --- |
| 00 | RO | MAGIC `0x44505953` |
| 04 | RO | VERSION `0x00010000` |
| 08 | RO | STATUS: bit0 running, bit1 busy, bit2 result_valid, bit3 sticky fault |
| 0c | WO | CONTROL: STOP=1, START=2, TRIGGER=4, ACK=8; non-STOP is exactly one command |
| 10 | RW | staged_tag (START requires nonzero; tag writes require stopped) |
| 14 | RO | active_tag |
| 18 | RO | generation, successful START count, no wrap |
| 1c | RO | trigger_id for current session, first successful trigger=1, no wrap |
| 20 | RO | PL diagnostic cycle counter, modulo 2^32, **not QPC** |
| 24 | RO | cumulative actual capture events, saturating |
| 28 | RO | cumulative queue accepted scans, saturating |
| 2c | — | reserved/unknown: SLVERR |
| 30 | RO | cumulative actual lane handshakes into result stage, saturating |
| 34 | RO | LAST_ERROR, last rejected write/fatal cause; STOP/reset/successful START clear |
| 40/44/48/4c | RW | data16 for channel0..3; upper16 must be zero |
| 50/54,58/5c,60/64,68/6c | RW | tick0..3, low32/high32, original opaque QPC values |
| 70 | RW | quality8x4, channel0 in low byte |
| 80 | RO | result_data16, upper16 zero |
| 84 | RO | result_channel[1:0], quality[15:8]; other bits zero |
| 88/8c | RO | original result_tick64 low32/high32 |
| 90/94 | RO | result first_seq/last_seq, repeated on all four lanes |
| 98/9c/a0 | RO | result tag/trigger_id/generation |
| a4 | RO | **PL_RESULT_LATCH_CYCLE**: PL counter sampled on the actual lane handshake into the result register |

`0xA4` implements the main's clarification: it is result-latch time, never
original acquisition/capture time. Every lane has its own latch cycle; it
remains stable until ACK/STOP/reset. The four pinned dependencies carry the
original opaque tick64 and provide no separately propagated PL acquisition
cycle. ACK and STOP zero invalid result fields.

Capture39's per-arm event statistic resets at STOP/rearm. The wrapper sums
nonnegative deltas of that actual statistic into a saturating lifetime count;
it can lag capture by one clock. Queue accepted is the queue's actual
cumulative statistic, retained through cancel. Lane count increments only on
an actual lane handshake; ACK does not increment it. Full reset clears all.

## LAST_ERROR codes

Read failures do not update LAST_ERROR. Invalid write checks follow alignment,
address/access, strobe, then state/value preconditions; first failing guard wins.
STOP dominance applies before other CONTROL checks.

| Code | Cause |
| --- | --- |
| 0 | cleared/no error |
| 1 | unaligned write |
| 2 | unknown write address |
| 3 | write to RO register |
| 4 | missing full WSTRB, including STOP without byte0 enabled |
| 5 | zero, multiple or unknown non-STOP command bits |
| 6 | START while a session is active/pending arm |
| 7 | START tag zero |
| 8 | START tag equals last successful tag |
| 9 | generation exhausted; START cannot wrap |
| 10 | TRIGGER while not running/armed (includes terminal exhausted capture) |
| 11 | TRIGGER while busy/result pending |
| 12 | missing any fresh data/tick/quality word |
| 13 | trigger ID exhausted |
| 14 | insufficient remaining sequence capacity |
| 15 | ACK without result |
| 16 | stage write while busy |
| 17 | tag write while session active/pending arm |
| 18 | data16 write with nonzero upper16 |
| 19 | START with fatal fault requiring STOP |
| 32 | unexpected capture order error |
| 33 | capture overrun |
| 34 | unexpected sequence exhaustion |
| 35 | lane identity inconsistency; invalid lane not published |

Generation/trigger/sequence capacity checks are fixed 32-bit guards; the bounded
public-interface author regression does not exhaust 2^32 values or inject
internal faults. Those guards and fatal recovery need the main's independent
review. No hierarchical shortcuts are used to claim coverage.

## Exact inputs and bounded reproduction

The only RTL dependencies are unchanged, as selected in main `SOURCE_PINS.json`:

| File under fpga/acquisition | SHA256 |
| --- | --- |
| deepeye_buffered_scan_capture.sv | c8a540db8122b8f5520582a0f1fa9be0c43cb54a62f03c7c4edc893906f28411 |
| deepeye_sample_scan_capture.sv | fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d |
| deepeye_raw_scan_queue.sv | 630e14803d82b3379517d91626de4ad7e7d3c509ad14363b3164031a5f633ee4 |
| deepeye_scan_lane_stream.sv | b3c9d2024d9325191538cf08fec9a652ff8ff0ae316ec9af96078f85cf5be3cc |

From the product root, using the existing repository virtual environment:

```powershell
& 'D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe' -X utf8 tools/diagnostic/run_private_axi_diag.py --modelsim-home D:/modelsim1/win64 --seed 53025
```

The runner verifies the fixed human hash and four source pins, snapshots raw
source bytes before compilation, runs hidden actual ModelSim10.7, and records
commands, PID, tool version, stdout/stderr, exit codes, transcripts and hashes
under `evidence/diagnostic/private-axi-20261025-53/author/attemptNN/`.
It allows an initial attempt plus at most two author corrections. It does not
automatically retry or alter dependencies. Existing evidence is never replaced.

The seeded public-AXI bench covers 14 directed cases, 16 exact raw records,
freshness and invalid writes, two sessions, AW-before-W/W-before-AW, B/R
backpressure and no duplicate effects, delayed ACK, repeated trigger rejection,
STOP during feeder, pending result and result-ready race, reset during pending
AW/W/B/R, and recovery. A separate real `$fatal` negative run must be refused.
Nine synthetic parser controls reject false PASS envelopes, including a real
`Errors: 1` summary or Error/Fatal line even after PASS with exit zero.
Unique exact run/seed BEGIN/STATS/PASS, case/record counts, unchanged sources,
actual zero exit and no simulator errors are all required for author PASS.
Failed attempt bytes and expected negative failures remain preserved.

The first actual ModelSim10.7 negative control produced `$fatal`, `Errors: 1`
and exit **0** with `onfinish exit`. The positive run completed all 14 cases
with 16 records and zero errors. The original runner rejected the negative
log correctly but its extra nonzero-negative-exit expectation made the
aggregate fail. Author correction01 removes that invalid expectation; it
does not relax positive PASS, error detection or input identity. The existing
raw simulation bytes are re-adjudicated without rerunning the simulations;
the original failed summary, command exits, source snapshots and logs remain
unchanged. This result interpretation is recorded separately in author
`correction01/rejudgment.json`. RTL and bench are unchanged by this correction.
