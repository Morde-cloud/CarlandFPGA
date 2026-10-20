# deepeye_first_capture_deadline candidate

Status: author-side candidate implementation and self-test only. This document
does not claim product acceptance, synthesis, implementation, timing closure,
CDC/RDC qualification, all29/G05/B06/R03, board execution, or system acceptance.

## Contract and scope

- Task: `DEEPEYE-IMPLEMENTATION-20261014/v1`
- Work: `B-FIRST-CAPTURE-DEADLINE-RTL-20261021-18-v1`
- Operation: `B-DEEPEYE-FIRST-CAPTURE-DEADLINE-20261021-18`
- Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01-H15
- Contract pin: `f5989cd5defce561f9ba98e6b18fc2682945f0a2`
- Requirements SHA256: `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`
- Frozen design: `1011259415a0916054eb580687612580bc1e5f09`
- Baseline worktree commit: `ccf3698cce065e20dbfa24bb6d07a97be7e38de6`

The module is a same-clock integer first-capture deadline monitor. It does not
define or connect physical TTL, STOP, PWM, ENABLE, clock frequency, source
identity, BOOT, register/TRACE/HWH, ABI, motion authority, or CDC/RDC behavior.
Only the existing B15 public ports are composed in the new test fixture. Only
machine A may operate a physical board.

## Interface

```systemverilog
module deepeye_first_capture_deadline #(
    parameter integer BUDGET_W = 32
) (
    input  logic                    clk,
    input  logic                    rst,
    input  logic                    cancel,
    input  logic                    start,
    input  logic                    observed,
    input  logic [BUDGET_AW-1:0]    budget_cycles,
    output logic                    waiting,
    output logic                    completed,
    output logic                    expired,
    output logic                    invalid_request,
    output logic                    started_event,
    output logic                    completed_event,
    output logic                    expired_event,
    output logic                    invalid_request_event
);
```

`BUDGET_AW` is a local clamp of `BUDGET_W` to 1..32 so unsupported parameters
can reach a simulation guard without an unrelated range error. Supported
`BUDGET_W` values are exactly 1..32, with default 32.

## Edge semantics

All decisions use pre-edge inputs and registered state. `rst` and `cancel` are
synchronous and have highest priority. State levels are registered and are
one-hot-or-zero; each entry event is a registered one-edge pulse and is cleared
by `rst`/`cancel` or by the next sampled edge.

1. `rst` or `cancel`: IDLE, all state and events zero.
2. WAIT with `start`: INVALID, `invalid_request_event=1`, no deadline renewal.
3. Non-WAIT with `start` and positive `budget_cycles`: WAIT,
   `started_event=1`, latched budget. `observed` on this same edge is ignored.
4. Non-WAIT with `start` and zero budget: INVALID,
   `invalid_request_event=1`, replacing any previous terminal result.
5. WAIT without `start`: a pre-edge `observed` gives COMPLETED and
   `completed_event=1`; otherwise the final allowed edge gives EXPIRED and
   `expired_event=1`; otherwise WAIT remains.
6. Non-WAIT without `start`: retain IDLE or the terminal result. Late
   `observed` has no effect. Changing `budget_cycles` cannot change a latched
   deadline.

For start edge E0 with positive N, the internal countdown is initialized to
N-1. Pre-edge `observed` is eligible at E0+1 through E0+N inclusive; the
E0+N event wins over expiry. A record first visible after E0+N NBA is late
and cannot revive a terminal state. `start` is sampled every edge, not
rising-edge detected. A held start therefore produces a new sampled request on
every edge: in WAIT it is rejected; a following non-WAIT positive or zero
budget is a new distinct request. Held zero-budget starts produce one rejection
event on every sampled edge.

## Guard behavior

`BUDGET_W=0` and `BUDGET_W=33` (and other unsupported integers) produce, at
simulation time zero, the exact parameter diagnostic

```
DEEPEYE_FIRST_CAPTURE_INVALID_PARAM BUDGET_W=<original> SAFE_BUDGET_W=<clamped>
```

followed by the module's own fatal text

```
DEEPEYE_FIRST_CAPTURE_INVALID_PARAM unsupported width
```

The clamp is simulation-only and is not hardware initialization. ModelSim
10.7 SE-64 records the expected guard with exit code 0 even for `$fatal`; the
runner therefore qualifies the exact diagnostic and fatal line and requires
exit 0, rather than inventing a nonzero exit code.

## Independent author testbench

`competition/deepeye/tests/control/tb_first_capture_deadline.sv` contains:

- A separately written behavioral reference model using an enum/case style.
  It is not the DUT and the testbench never reads DUT hierarchy or uses DUT
  outputs to form expectations.
- Directed exhaustive small-width tests for `BUDGET_W=1..5`: every nonzero
  representable budget, every observation position through deadline+1 plus no
  observation, every cancel/reset position from the start edge through
  deadline+1, every WAIT repeated-start position, priority combinations,
  held starts, terminal zero-budget requests, latched-budget changes, and
  deterministic random sequences.
- A bounded `BUDGET_W=32` prefix over selected budgets and observation
  positions. This is not a full 2^32 traversal.
- A B15 composition fixture with literal public wiring:

```systemverilog
start    = window_started;
observed = out_valid;
cancel   = stop || (cfg_valid && cfg_ready) || pending || !running ||
           !window_active || failure_event || (|raw_fault_events);
```

`rst` is shared and synchronous. `out_ready` is not added to `cancel` or
`observed`. `sample_levels` is driven by a separate literal waveform, not by
expected counters or old hierarchy.

The P2/H1 composition traces exercise reset, configuration handshake,
application, rearm, the common 111/000/111 waveform, the registered
`window_started` edge, N3 completion on E0+3, N2 expiry on E0+2, and the
second trace where the row6 record is retained at row7 with `out_ready=0`,
then transported at row8 while a post-edge subset-rise fault appears. The
row8 post-NBA completed status is not retroactively revoked; the next sampled
public fault cancellation clears it at row9. Quiet B15, STOP, new
configuration, ineligible-application `failure_event`, and raw fault cases are
also covered.

## Author test results

Final author run (normal): `run-normal-final-01`.

| case | width | scenarios | checks | failures |
|---|---:|---:|---:|---:|
| standalone | 1 | 125 | 59688 | 0 |
| standalone | 2 | 163 | 62055 | 0 |
| standalone | 3 | 287 | 73305 | 0 |
| standalone | 4 | 727 | 137997 | 0 |
| standalone | 5 | 2375 | 565173 | 0 |
| bounded prefix | 32 | 31 | 17559 | 0 |
| composition | 4 | 7 | 661 | 0 |
| guard | 0 | expected fatal | n/a | 0 |
| guard | 33 | expected fatal | n/a | 0 |

Small-width directed scenarios total 3677 across widths 1..5. Observation
positions total 765, cancel positions 765, reset positions 765, repeated-start
positions 708, priority 40, held 10, terminal 10, latch 114, and deterministic
random 500. The 3677 count is not the sum of repeated assertions; each scenario
has a unique id and an independent stimulus/expectation window.

## Real RTL mutants

Four separately generated and compiled copies of the new module were tested
through the public ports. Each mutant compiled successfully and produced at
least one `DEEPEYE_FC_CHECK_FAIL` at widths 1, 2, and 3; no compile failure,
X-only initialization, or parser injection is counted as a hit.

| mutant | behavioral change | widths rejected |
|---|---|---|
| deadline-off-by-one | deadline extended by one edge | 1, 2, 3 |
| repeat-start-renewal | WAIT duplicate start reloads deadline | 1, 2, 3 |
| cancel-ignored | synchronous cancel removed | 1, 2, 3 |
| late-observed-resurrection | late observed revives COMPLETED | 1, 2, 3 |

Final mutant run: `run-mutants-final-01`.

## Runner qualification

`competition/deepeye/tools/control3d/run_first_capture_deadline.py` snapshots
the exact source bytes, records argv/versions/timestamps, creates a fresh
working directory and unique logs for every case, and launches ModelSim and
Python tools with hidden windows (`CREATE_NO_WINDOW`) and explicit timeouts.
It never launches a GUI.

The parser requires exactly one `RUN`, one `SUMMARY`, and one `FINISH`; unique
scenario ids; complete and consistent group counts; scenario/check totals
matching the summary; PASS status; expected exit and no timeout; no unrelated
`Fatal`/`Error`; and no pseudo or malformed `DEEPEYE_FC_` prefix. Guard cases
require exactly the zero/33 parameter diagnostic, the exact fatal text, no
unexpected live marker, and the simulator's actual exit code 0. A valid-width
fake guard is rejected.

`competition/deepeye/tests/control/test_first_capture_deadline_runner.py`
contains 24 standard-library `unittest` cases, including a genuine normal
ModelSim width1 transcript acceptance control, genuine guard0/guard33
transcripts, duplicate/conflicting statistics, missing/duplicate finish,
unrelated fatal/error, pseudo prefix, group/count mismatch, guard fake,
non-expected exit, and a real subprocess timeout. It has no dependency on old
private evidence or controller layout.

## Limitations and non-claims

- No Vivado is installed on this machine. New synthesis and implementation are
  `blocked`/`not_run`; no timing, utilization, DRC, placement, routing, or
  bitstream result is claimed. The old A OOC result is not inherited.
- `all29`, `G05`, `B06`, `R03`, board, and complete-system acceptance are
  `not_run`.
- Width32 is a bounded prefix, not a complete maximum-count traversal.
- No physical TTL, clock frequency, source authentication, register bank,
  `0x2c`, HWH, TRACE type7, BOOT, profile, curvature, final authority, CDC/RDC,
  STOP/PWM/ENABLE connection, or motion authority is introduced.
- H01-H15 remain unchanged in full. The 3D game, UI, solid collisions, free
  camera/layout, equal blue/red gates and full passage, hidden truth, causal
  sensing, substantive PC AI, and both H12 control paths are not weakened by
  this monitor.
- Only machine A may operate the physical board. This author work is not a
  product acceptance or a board result.
