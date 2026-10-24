# B52 digital TRACE/UART receiver fixture

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-TRACE-UART-LOOPBACK-20261024-52-v1`, operation
`B-DEEPEYE-TRACE-UART-LOOPBACK-20261024-52`.
This fixture implements the quality main's bounded specification. The main
retains design, critical evaluation and acceptance. Only the testbench, runner,
this document and the B52 `author/` evidence directory are owned here.

The contract is `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01–H15, pinned at
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`; its requirements-array SHA256 is
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
The runner checks this fixed value using UTF-8 canonical JSON with
`ensure_ascii=False`, sorted keys and compact comma/colon separators. Frozen
design: `1011259415a0916054eb580687612580bc1e5f09`.
All full 3D/UI, edge-only hollow cube, solid volume collisions, free camera,
editable/random obstacles, free faces, equal blue/red gates and full passage,
hidden truth, device-bounded causal observation, online 3D decisions,
substantive PC AI, PC_DIRECT and FPGA-output paths remain mandatory.

The ten immutable RTL dependencies and the 53 main49 vectors are SHA256-pinned
in the runner and copied into each fresh attempt. The vectors reuse main49's
payload and CRC goldens; they are not a new codec oracle. A separately labelled
quality-invalid, single-observation vector produces the shortest 35-byte frame
at the real numeric defaults, 100 MHz and 9600 baud. The simulation clock is
10 ns; reduced numeric clock/baud pairs exercise digital ratio arithmetic.

Run from the product root with the existing Python environment:

```powershell
& D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -X utf8 tools/transport/run_trace_uart_loopback.py --attempt attempt-01
```

Fresh attempt names prevent overwrite/replay. The runner launches hidden
ModelSim 10.7 command-line processes and records argv, cwd, PID, exit, duration,
stdout/stderr, actual versions and tool/file hashes. Original failures remain
in their attempt directory. Author repair is limited to two bounded cycles;
immutable dependency defects must be returned to the main.

The recorded author execution used both permitted repair cycles. Attempt 01
compiled cleanly but failed library loading. Attempt 02 passed all four actual
simulation profiles and 18 saved-log negatives; only its separate diagnostic
had the wrong OS exit. `--finish-attempt attempt-02` verifies the unchanged
saved profiles and creates `author/repair-02/` with the corrected diagnostic.
It does not rerun the passed simulations or rewrite historical failures.

The new bench connects public TRACE TX directly to the opaque receiver's
`rx_async` through a test-only line corruption mux. The baseline admits no
second frame while RX is blocked. For each successful frame, RX output is held
for another complete frame interval; TX result backpressure is independent.
Unaccepted configuration is mutated and sample input has deterministic bubbles.
At 16/1, shared reset/cancel covers first/last byte start, eight data bits and
stop, sample feeding, a pending candidate, and a previously retired candidate.
Each abort is followed by high-line/warmup and a fresh complete frame.

The corruption flips byte index 12, data bit 3, over the whole interval from
`start + ceil(4*CLOCK_HZ/BAUD)` to `start + ceil(5*CLOCK_HZ/BAUD)`.
Byte indices come only from public TX busy transitions. Start and stop remain
intact. Public RX CRC rejection and the next clean frame are required.

`events.log` retains all public TX/busy/line transition cycles, configuration
and sample handshakes, result offers/retirements, RX fields, errors, readiness
changes, abort prefixes and status snapshots. The separately executed Python
check decodes those transitions and recomputes CRC independently of the SV
monitor. It checks exact RX type 7/epoch/sequence/tick/length/payload, unused
payload zeroes and public counter changes. Retired candidates remain recorded
across abort; reset-cleared device counters are reported separately.

Transcript checks require unique anchored markers, consistent numeric totals,
the exact bound finish source file/line, matching simulator time and a complete
zero-error footer. Saved-log negative recipes retain base/mutated hashes without
duplicating large logs. A fresh actual OS-zero/ModelSim-error-positive process
must also be rejected. Existing parameter guard campaigns are not repeated.

RX `out_valid` establishes syntax only and may precede completion of TX's stop
interval. TX result establishes local transmission only. Neither grants motion,
TTL, BOOT or source authority. This is same-clock digital simulation, with no
physical noise, oscillator tolerance, CDC, synthesis, implementation, OOC50 or
board claim. A alone operates the board. All 29 formal cards, B01/B03/B06/R03
and full product acceptance remain `not_run`.
