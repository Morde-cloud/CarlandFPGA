# Operation18 pre-author interface and acceptance freeze

Task DEEPEYE-IMPLEMENTATION-20261014/v1; operation
B-DEEPEYE-FIRST-CAPTURE-DEADLINE-20261021-18. Parent work
B-LOCAL-FIRST-CAPTURE-DEADLINE-CONTINUE-20261021-v1. One execution work
B-FIRST-CAPTURE-DEADLINE-RTL-20261021-18-v1; main owns technical acceptance.
Baseline ccf3698cce065e20dbfa24bb6d07a97be7e38de6. Contract
DEEPEYE-HUMAN-LOCK-20261014/revision1 H01-H15 canonical requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
design1011259415a0916054eb580687612580bc1e5f09.

Module `deepeye_first_capture_deadline`, parameter integer `BUDGET_W=32`,
supported1..32. Input ports: `clk,rst,cancel,start,observed` (one bit),
`budget_cycles[BUDGET_AW-1:0]`. Localparam BUDGET_AW clamps unsupported values
to1..32 only to reach an unambiguous simulation guard. Supported widths are exact.
Unsupported widths0/33 must fail at time0, with a complete unique diagnostic
`DEEPEYE_FIRST_CAPTURE_INVALID_PARAM BUDGET_W=<original> SAFE_BUDGET_W=<clamped>`
and own fatal text `DEEPEYE_FIRST_CAPTURE_INVALID_PARAM unsupported width`.
Guards are simulation-only, not hardware initialization or synthesis approval.

Registered one-hot-or-zero state levels:
`waiting,completed,expired,invalid_request`.
Registered entry events:
`started_event,completed_event,expired_event,invalid_request_event`.
Every event defaults to0 each sampled edge; rst/cancel clears all state/events.
Back-to-back distinct requests may legitimately assert invalid_request_event
on consecutive edges; each assertion belongs to that edge's sampled request,
not a single pulse carried by implicit edge detection. Reset is required.

Priority and definition, all based on pre-edge inputs/state:

1. rst or cancel -> IDLE/all zero; dominates every other input.
2. WAIT with start -> INVALID, invalid_request_event=1, no renewed deadline.
3. Non-WAIT with start -> positive budget enters WAIT/started_event=1;
   zero enters INVALID/invalid_request_event=1, replacing any old terminal result.
   observed is ignored on this start edge.
4. WAIT without start -> observed enters COMPLETE/completed_event=1.
   Otherwise the final allowed edge enters EXPIRED/expired_event=1;
   otherwise keep WAIT. At start edge E0 and latched budget N>0,
   allowed observed edges are E0+1..E0+N inclusive; final-edge observed wins.
5. Non-WAIT with no start retains terminal or IDLE state, clears entry events;
   late observed does not alter it. Later budget_cycles changes have no effect
   on the latched active request. No count wrap or implicit renewal.

No clock Hz, physical TTL, source authentication, BOOT, register/TRACE/HWH,
source freshness, ENABLE or motion authority. No output connection to product
STOP/PWM. Shared synchronous binary stimulus only; CDC/RDC/board not covered.

New composition test uses only original B15 public ports, with EXACT wiring:

```
start = window_started;
observed = out_valid;
cancel = stop || (cfg_valid && cfg_ready) || pending || !running ||
         !window_active || failure_event || (|raw_fault_events);
```

rst is shared synchronous reset. Do not add out_ready into cancel or observed.
Do not peek/force hierarchy, phase/counters, or manufacture a raw capture from
expected values. Input sample_levels is a separate externally driven waveform.

Frozen literal P2/H1 trace (all three high counts1, period2):
reset at row0, cfg handshake row1, actual application A0=row2,
rearm row3 with raw000, monitor start E0=row4 with common R0=111,
row5 F0=000, row6 R1=111 produces the slot after the edge,
row7 first pre-edge out_valid eligible for monitor. N3 completes row7;
N2 expires row6. Tag fixed to3. COUNT_W4/WITNESS_W8/TAG_W4 suffice.
One extra initial reset edge in the driver is not a measured timeline row.

A second literal trace retains the row6 record with out_ready0 at row7,
sample110 at row7, then sample111/out_ready1 at row8. At row8 the old record
may be transported pre-edge while the new subset-rise fault appears post-edge.
At row9 the public fault cancellation clears terminal status; no retrospective
revocation of the row8 handshake. Main verification must inspect both pre/post
public values, not just a post-NBA snapshot. Historical COMPLETE never grants action.

Small-width budgets1..MAX for widths1..5: every observation position through
deadline+1 plus none; every cancel/reset/repeated-start position; priority
combinations; held-start, terminal zero-budget, latched-budget changes.
Width32 is bounded prefix only. Cover quiet B15, good external waveform,
backpressure, STOP/new config/raw fault. Preserve native command/exit/logs.
Four actual compiled RTL mutant classes: deadline off-by-one, repeated-start
renewal, cancel ignored, late-observation resurrection. Reject by public-port
behavior, not parser injection/compile failure/X-only output.

Author must build separate TB expectations and runner qualification tests.
Do not read/import main oracle/vector/TB files beyond this interface document.
Main freezes an absolute-edge reference and concrete inputs before author work.
Old08–17 suites are not rerun. Old threeRTL, tests/oracles/evidence unchanged.
all29/G05/B06/R03/board/system not_run; new synth/implementation blocked without
Vivado; board A-only.
