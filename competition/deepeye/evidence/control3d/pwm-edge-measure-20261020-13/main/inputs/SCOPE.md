# One synchronous single-channel PWM edge measurement primitive

Task DEEPEYE-IMPLEMENTATION-20261014/v1, sole B product director
01a13b55-095b-7461-8dd5-5476a130bd82, actual App turn
01a154e7-12a1-7e12-ad4a-c4e2577b93b9. Parent work
B-LOCAL-CAPTURE-CONTINUE-20261020-v1; instruction operation
B-LOCAL-CAPTURE-CONTINUE-20261020-v1-DIRECTOR-SCOPE. New product operation
B-DEEPEYE-PWM-EDGE-MEASURE-20261020-13; single proposed Flash work
B-PWM-EDGE-MEASURE-RTL-20261020-13-v1. Current authority is scope freeze and
coordinator review only; no worker before actual CONTINUE.

Contract DEEPEYE-HUMAN-LOCK-20261014/revision1, H01-H15, requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
source f5989cd5defce561f9ba98e6b18fc2682945f0a2, design
1011259415a0916054eb580687612580bc1e5f09. Preserve complete3D/UI, hollow edge-only
cube, solid-volume collision, free camera/editing/random layouts/free faces,
equal blue/red gates and whole-body passage, hidden truth, device-bounded causal
observations, online3D decisions, substantive PC AI and both control chains.
All29 formal cards remain not_run/unaccepted; physical board A-only.

## Inputs and real gap

Existing worktree D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014,
baseline f7e95af8f8abae6d4a5312c08d99e095a7e5dec1; op12 source
61141302a68c3085951721074abbfeec31bfcb3a. Op12 generation has independently
reviewed digital evidence and 355 exact delivered files. The coordinator's
completed decision SHA256 is 5f435827f0610f202e24dd75a0f6cc9af16c4de25930961167fd67da7a267c48.
Its new explicit scope instruction SHA256 is
3820f18b868a8bffa6a4c4555b3bc876f1f31f0875ffae5e623eb22b8daf0608.
There is no actual independent edge-counting RTL in this worktree. This work
does not modify or rerun op12 or any old operation suite.

Fresh PR30 head remains f7e95af8f8abae6d4a5312c08d99e095a7e5dec1; five comments,
zero formal reviews, no new comment after6261676586 at this scope read.
A peer transport for op12 delivered; C remains queued in its existing outbox.
Neither is a new A/C acceptance. Current ledger has zero active jobs/pool
instances and no prior operation13/work13 duplicate. New named paths are absent.

## Interface and domain

Module deepeye_pwm_edge_measure. Parameters COUNT_W=32, supported2..32;
TAG_W=32, supported1..64. MAX=(2**COUNT_W)-1, an unsigned count bound, not a
physical timeout. Invalid parameters have an explicit time-zero simulation
diagnostic excluded from synthesis. No hardware initial state is used.

Inputs: clk, rst, stop, rearm, sample_level, window_tag[TAG_W-1:0], out_ready.
All are binary synchronous inputs sampled on rising clk. No synchronizer or
asynchronous pin/analog claim is supplied. Every active clock edge is a sample;
unobserved transitions between samples are outside this primitive's evidence.

Outputs: armed; out_valid; out_period[COUNT_W-1:0]; out_high[COUNT_W-1:0];
out_tag[TAG_W-1:0]; overflow_event; overrun_event; overflow_seen; overrun_seen;
loss_count[COUNT_W-1:0]. Count/tag payload and diagnostic/armed outputs are
registers. out_valid is the registered occupied bit qualified by
!rst && !stop && !rearm, so an explicitly aborted record cannot handshake on
that same sampled edge. No other combinational input affects result payload.

out_valid denotes a queued raw record, **not** capture eligibility, waveform
liveness or movement authority. A completed record may wait while later input
is lost; loss diagnostics report this, but the record's correct old counts are
preserved until consumed or explicit flush. There is no freshness grant or
physical timeout. Future integration must supply source/session/request/epoch,
start/end time, three-channel same-period coherence, live-edge/freshness rules,
profile decoding and authority before using any raw record for motion.

## Window, priority and sampled edges

Before use, an explicit reset edge is required. Highest priority is rst or stop:
on that edge armed=0; previous-sample/partial age/high/window tag/result slot,
all output payloads, diagnostics and pulses become zero. out_valid is suppressed
while either control is asserted. Stop/reset cannot consume or create a result.
Deassertion alone leaves the primitive unarmed.

Next priority is rearm: armed=1; latch window_tag; flush every partial/result,
counter and diagnostic; snapshot sample_level as the new previous sample. This
edge is only a baseline, never a rising/falling event for the new window. A high
signal at rearm must first become low and then rise freshly before measurement
can begin. Held rearm starts a new empty baseline each edge and produces no
result or loss event. Changing window_tag without rearm has no effect. A zero
tag is legal and opaque.

On an ordinary armed edge, derive rising = !previous_sample && sample_level,
falling = previous_sample && !sample_level, then update previous_sample. The
state waits for a fresh rising edge R0, then the first falling F0, then the next
rising R1. At R1 the candidate counts are:

- high = index(F0) - index(R0)
- period = index(R1) - index(R0)

Indices count sampled clock-edge intervals; R0 establishes age0, a falling on
the next edge yields high1, and the earliest next rising yields period2. A
candidate needs 1<=high<period<=MAX. No width0/full-period result can be inferred
from constant levels. Binary sampling inherently makes F0 strictly between
R0 and R1. The successful R1 also starts the next measurement at age0, regardless
of whether its previous result could be buffered. No generator settings,
metadata or internal signals may be used as a measurement source or oracle.

## Bound and missing-edge behavior

Age measures intervals since the current R0. At an ordinary edge, if the old
age equals MAX, the new elapsed interval would be MAX+1: abandon that partial,
emit exactly one overflow_event, set overflow_seen, and increment loss_count
with saturation. Do not increment/wrap age. This check has priority over
closing the old period, so R1 at MAX is valid, R1 at MAX+1 is invalid.

If the overflowing edge is itself a freshly observed rising edge, it starts a
new measurement at age0 after invalidating the old one. Otherwise return to
waiting for a fresh rising, keeping the actual sampled level as previous.
A constant high after a started R0 thus overflows once, then waits for a later
low/rise. A constant low after F0 similarly overflows once. Constant low or high
from rearm with no fresh R0 produces neither result nor overflow; this is not an
absence-of-signal watchdog. A physical timeout must not be invented here.

Overflow never fabricates a completed result or re-labels an old partial. It
does not revoke a correctly completed older record already in the result slot;
out_valid remains a transport signal only. Flush commands discard such a
pending record explicitly and prevent its old tag from reappearing afterward.

## Result slot and visible loss

There is exactly one result slot. A handshake consumes the old record when
out_valid && out_ready at an ordinary edge. A newly completed candidate may
replace it on that same edge, or fill an empty old slot. The new record cannot
be consumed on its creation edge when no old out_valid existed: there is no
combinational bypass. If a record is consumed with no new candidate, occupied
and its payload registers become zero.

If the old slot is occupied and out_ready=0 when a candidate completes, preserve
the entire old payload/valid, drop only the new candidate, pulse overrun_event,
set overrun_seen and increment loss_count with saturation. Input measurement
continues independently of output readiness. No partial-channel or field update
is allowed. Stable valid/payload under backpressure is required except explicit
reset/STOP/rearm abort. Same-edge consumption and new result incurs no overrun.

overflow_event and overrun_event are one-edge pulses, default0 each ordinary
edge; they are mutually exclusive because an out-of-bound period is not a
complete candidate. The seen flags remain set until reset/STOP/rearm.
loss_count counts overflow episodes plus dropped complete candidates in the
current window, saturating at MAX; pulses and sticky flags remain visible even
after saturation. Intentional partial/pending discard at flush is not counted
as loss and does not preserve old-window diagnostics. Consumers issuing flush
are explicitly abandoning that record. There is no hidden overwrite or silent
counter wrap.

## Ownership and implementation routing

Exactly one Flash/max execution after actual coordination CONTINUE. Its only
paths, relative to the existing product worktree:

- competition/deepeye/fpga/control3d/deepeye_pwm_edge_measure.sv
- competition/deepeye/fpga/control3d/pwm_edge_measure_candidate.md
- competition/deepeye/tests/rtl/control3d/tb_pwm_edge_measure.sv
- competition/deepeye/tools/control3d/run_pwm_edge_measure.py
- competition/deepeye/evidence/control3d/pwm-edge-measure-20261020-13/author/

Main alone owns the corresponding main/ evidence subtree, tests/rtl/control3d/
main_tb_pwm_edge_measure.sv, tools/control3d/main_verify_pwm_edge_measure.py,
handoffs/b/B-DEEPEYE-PWM-EDGE-MEASURE-20261020-13/, and this private
independent-capture-20261020-13 directory. Main may repair new worker files only
after terminal ownership release. Runtime helper/source fixtures stay within
these declared directories. No existing op12 files or old directories are
modified. Preserve the sole protected dirty input at
handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json SHA256
6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8.

No other agent, native lease or main is created. Child cannot commit/publish,
message peers/groups, read credentials or alter services/config/SQL/queues/
public schemas/board state. It reports to this director. Carry standing-order
markers [需桌面回合] / [需本人操作] with exact action, IDs and evidence only when
actually needed; no presence broadcasts. Duplicate job results are reused.

## Independent acceptance design

Main freezes a reference based on sampled event indices and a one-record
consumer queue before reading author implementation. It must not import the
generator or author model. Record deterministic independent waveforms and
ready/control/tag schedules, actual public-port observations and exact inputs.
ModelSim SE-64 10.7 was actually exercised in op12; op13 must run its own compile
and simulation, preserve commands/version/raw stdout/stderr/exits/source hashes,
and reject compiler errors, unexpected fatal content or missing success markers.
No source hierarchy forcing or seeded counters supports a public-port claim.

Required authored and main coverage:

1. Every representable legal period/high pair at small widths, repeated cycles,
   minimum high1/low1/period2, exact MAX period, MAX+1 invalid period, high/low
   over-bound partials and recovery that reuses an overflow-edge fresh rising.
2. Independent waveform phases and rearm at low/high/rise/fall, STOP/reset/rearm
   at every partial stage and at result completion/retirement, held commands,
   tag changes without rearm, full-width/zero tags and no prior-window relabel.
3. Empty/full result slot, long backpressure, same-edge consume/refill, loss
   pulses/stickies/saturation with small widths, pending-record preservation
   through a later overflow and explicit flush discard. Keep expected validity
   defined as raw transport, not source liveness.
4. Constant low/high with and without a started cycle, count bounds without
   wrapping, recovery after overflow/overrun, deterministic randomized edge and
   consumer schedules, parameter minima/maxima and invalid parameter guards.
5. Fully observed representative COUNT_W16 periods crossing bit15, including
   max65535 and overflow at65536; bounded COUNT_W32 functional observations and
   full-width tags. Do not claim 32-bit count overflow or a full max32 period
   was executed. Mathematical/structural width reasoning is labeled separately.
6. An isolated off-by-one or stale-window mutant must be rejected by actual
   public-port evidence; preserve the faulty copy and original unchanged bytes.
7. Preserve failures and original logs; fix/retest only actual defects. The
   positive suite and exact committed bytes must agree. Count test groups,
   sampled cycles and per-cycle assertions separately.

The independent oracle may use run-length stimuli for longer intervals, while
checking output stability and event timing on all sampled edges and recording
replayable run lengths and observed events. It cannot infer success merely from
a generator/capture roundtrip or echoing requested counts.

Only bounded digital behavior can be accepted. Synthesis/implementation remain
blocked without actual Vivado; no physical timing/capture/CDC/RDC/BOOT/source/
HWH/profile/curvature/TTL or motion eligibility is supplied. Three-channel
same-period complete capture, including original application/command binding,
remains a later explicit integration gate. G05/B06/R03, both control chains and
all29 formal cards remain not_run/unaccepted.

After approved implementation and independent main acceptance, create a new
source/evidence commit and standard operation13 manifest, publish existing PR30
with force=false and exact remote-byte verification, and return a terminal
receipt to the existing coordinating task. Unknown writes are reconciled before
replay. No old operation test rerun, Goal, automation, periodic model polling,
or service changes. Scope review and final result use original returned
message_id/main_wait through the already proven distinct App/resident entries.
