# Fixed capture and queue composition — author candidate

Operation B-DEEPEYE-BUFFERED-SCAN-CAPTURE-20261024-39, work
B-BUFFERED-SCAN-CAPTURE-20261024-39-v1, under main
01a13b55-095b-7461-8dd5-5476a130bd82. Main retains evaluation and acceptance.

`deepeye_buffered_scan_capture` instantiates the unchanged sample capture and
raw scan queue with explicit SEQ_W=32, TICK_W=64, TAG_W=32, STAT_W=32 and queue
DEPTH=4. It adds no state, arithmetic, clock domain, policy, or new record format.
Six record fields cross the existing ready/valid boundary without rewriting.
All 24 public output ports expose the original stage outputs directly.

Shared `rst` resets both stages. `stop`, `rearm` and `rearm_tag` reach capture
only. `queue_cancel` reaches the queue only. Stopping or rearming capture does
not flush queued records; old queued tags survive rearm. Queue cancellation
does not clear a pending capture record or stop a partially collected scan.
The caller owns any future coordinated discard. Capture counters reset on
stop/rearm, while queue counters preserve their original separate semantics.
Do not sum stage retirement counters as distinct source scans.

The queue's unchanged RAM is not cleared by reset or cancel. `out_valid=0`
invalidates its payload; stale or unknown payload pins while invalid are
permitted. No stale record may become a valid transfer after shared reset.

The testbench reuses a separate direct chain of the exact dependency modules
and compares every public output before and after every sampled edge. This
checks wrapper wiring, not an independent proof of the modules. Its field
mapping was informed by base 0885ed48b9edc48be7fd20135e8c141a485218d4,
`tests/rtl/acquisition/tb_raw_scan_queue.sv` lines 727–795, SHA256
e38944f5340cd4f17c9f6a2481ed4150cf82d3902031dec3ac7f6db3790f0ad0.
The old testbench's `stop | rearm` queue cancellation convention is not used.

The author runner also applies a separate public transaction model: channel
tuples form complete records, one pending record feeds a FIFO list, and
disposition/counter checks account for reset, cancellation, retirement, order
errors and overrun. The original published model informed lane packing and
pre-edge handshakes; no private main oracle is read or imported. Full 128-bit
input and 780-bit output traces preserve every public signal, including
invalid RAM pins. Strict anchored completion parsing derives cycle/check
counts from the raw trace and rejects mutations of that saved trace.

Directed cases exercise all four channels and distinct data/ticks/quality/tags,
partial scans and order errors, full queue backpressure and capture overruns,
simultaneous push/pop, separate stop/rearm/cancel, and all 64 combinations of
reset/stop/rearm/cancel/strobe/ready with queued, pending and partial work.
A seeded finite mix and a final reset/rearm/new scan exercise fresh recovery.
Fixed 32-bit sequence exhaustion and counter saturation are not economically
reached and no internal state is forced. Earlier narrow-parameter dependency
tests are prior evidence only; this operation makes no new exhaustion proof.

Run with the existing Python and hidden ModelSim 10.7 processes:

```powershell
& 'D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe' -B -X utf8 tools/acquisition/run_buffered_scan_capture.py
```

The default evidence directory is
`evidence/acquisition/buffered-scan-20261024-39/author/attempt-01/`.
An existing output or input alias is rejected. Source snapshots, protected
before/after pins, command argv/cwd/PID, executable hashes, versions, exits and
raw stdout/stderr are retained. See author `RESULT.json` for actual results and
any preserved failed attempts; this document does not assert a test result.

H01–H15 remain pinned to f5989cd5defce561f9ba98e6b18fc2682945f0a2;
requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
Frozen design 1011259415a0916054eb580687612580bc1e5f09 remains unchanged.
Full game-grade 3D/UI, solid-volume collisions, free camera/editable layouts,
equal blue/red gates and complete passage, hidden truth, bounded causal
observations, online 3D PC AI and both control paths remain mandatory.
This candidate adds no sensor authenticity, sample-rate, TRACE, AXI/HWH, DMA,
CDC, board, physical timing, formal-card or system acceptance claim. All 29
formal cards remain not_run. Only A operates the physical board.
