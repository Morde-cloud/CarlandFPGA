# Internal actual-application capture-window composition

DEEPEYE-IMPLEMENTATION-20261014/v1, sole B product director
01a13b55-095b-7461-8dd5-5476a130bd82, App turn
01a154e7-12a1-7e12-ad4a-c4e2577b93b9. Parent work
B-LOCAL-APPLIED-CAPTURE-CONTINUE-20261020-v1; instruction operation
B-LOCAL-APPLIED-CAPTURE-CONTINUE-20261020-v1-DIRECTOR-SCOPE. Proposed product
operation B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15; one proposed Flash/max work
B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1. This is a scope for substantive review,
not execution authorization. No product files or worker before actual CONTINUE.

H01-H15, DEEPEYE-HUMAN-LOCK-20261014/revision1, contract source
f5989cd5defce561f9ba98e6b18fc2682945f0a2, requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 and design
1011259415a0916054eb580687612580bc1e5f09 remain fixed. Preserve full3D/UI,
hollow edge cube, solid-volume collisions, free camera/layouts/faces, equal
gates and complete passage, hidden truth, device-bounded causal observation,
substantive online3D PC AI and both PC_DIRECT/FPGA-output paths. This local
composition grants none of the missing public identity/clock/motion authority.
All29 formal cards, G05/B06/R03, CDC/RDC, board/system remain unaccepted/not_run;
physical board A-only. No service/config/SQL/queue/credential changes.

## Exact inputs, authorization and ownership

Existing worktree D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014,
branch codex/b/deepeye-implementation-20261014. Baseline local/PR30 head
7dd2c4108ee49cc6e0feb7c715d786f8b11a99c2; op14 source
21ae4c6bc9d03aea8a79bf784d9873ebdaf1c903, request
1d23fc80980b0269bece376230d3722892355b725e217f7644e5b519b8230970, manifest
f93e490bb0da5fb7e676538ec29e73aa56aacd388b574351de008b1d61ea8602.
Op14 actual completed ACCEPT decision
28de1e1ed43aaf0fe0e25f1448742927d429fce998b481ff6fdbb0c70cf9ebfa;
next-scope instruction625babe3ed6789cc9fdc993274d8b276544d95686bf2187bb6af863a78657483.
The original review event actually completed, rather than only being queued.

Instantiate these immutable modules through their public ports only:

- competition/deepeye/fpga/control3d/deepeye_atomic_pwm.sv,
  SHA2569dc8ecf96e59a2ae8467bda64572f62eb602d52db535733f236f64ff97c43428.
- competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv,
  SHA2564baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456.

Do not edit their source/interfaces/tests/evidence or rerun historical08-14
suites. New integration simulation necessarily instantiates the two exact
modules; it is new scope15 evidence, not an inherited historical PASS.

Fresh local ledger: no active jobs/pool or duplicate work15; registered product
thread remains the one above. All nine proposed product paths were absent.
PR30 has six comments/zero reviews, no new feedback after6273192999. Latest
read-only foreign metadata heads are A PR24b45bee841768c9d2c248fd164cf3fd21238c285d
and C PR25942fa309ffc8f1d32c816cfa643b009b031d7d0a. Reading these heads is not
review or acceptance and does not grant new public ABI authority. Original
peer publication14 messages to A/C remain queued at recorded send; no replay.

After actual CONTINUE, one worker owns only these five new worktree paths:

- competition/deepeye/fpga/control3d/deepeye_pwm_applied_capture.sv
- competition/deepeye/fpga/control3d/pwm_applied_capture_candidate.md
- competition/deepeye/tests/rtl/control3d/tb_pwm_applied_capture.sv
- competition/deepeye/tools/control3d/run_pwm_applied_capture.py
- competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author/

Main owns corresponding main/ evidence, main_tb_pwm_applied_capture.sv,
main_verify_pwm_applied_capture.py, handoffs/b/B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15/
and this new private independent-applied-capture-20261020-15 directory. Main
repairs worker paths only after terminal release. Protect existing dirty
handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json SHA256
6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8.
No second root/native/App context, speculative helper or autonomous child
commit/push/peer/group/service/board action. Report genuine [需桌面回合] or
[需本人操作] blockers with IDs/evidence. Preserve failed runs and preparation
logs; do not repeat author14's unavailable early temporary-directory history.

## Chosen architecture and exact interface

One new module deepeye_pwm_applied_capture composes the unchanged generator and
capture modules, plus a small registered binding state. It does not duplicate
their counters, infer private phase, or access hierarchy. No source-select mux.
The independent synchronous input sample_levels[2:0] is always the capture
source. A testbench may wire actual pwm to that input for an explicitly named
internal digital loopback case, or drive independent observed-level schedules.
That wiring is testbench-only and grants no public source-selection ABI.

Parameters COUNT_W=32 (2..32), WITNESS_W=64 (2..64), TAG_W=32 (1..64).
Simulation rejects unsupported values at time zero, explicitly printing all
three original values. Width-safe clamped declaration/instantiation widths may
be used only so invalid representatives reach this diagnostic; supported widths
are exact. No hardware initial state; a sampled reset is mandatory. Existing
modules receive supported safe widths in invalid diagnostic cases, so only the
new wrapper owns that invalid-parameter diagnostic. No waveform is claimed for
unsupported configurations.

Inputs:

- clk,rst,stop,cfg_valid,out_ready,sample_levels[2:0].
- cfg_period,cfg_high_yaw,cfg_high_pitch,cfg_high_speed, each COUNT_W bits;
  cfg_tag TAG_W bits.

Unmodified generator public outputs are forwarded with the same names and
semantics: cfg_ready,accepted,rejected,applied,frame_start,running,pending,pwm[2:0],
active_period,active_high_yaw,active_high_pitch,active_high_speed,active_tag.
The inherited internal bit mapping is pwm[0]=yaw,[1]=pitch,[2]=speed. It does not
freeze a new public control ABI or physical axis/profile assignment.

Additional outputs:

- window_active: the registered binding-state bit described below.
- window_started: registered one-edge pulse on a permitted observation of
  actual applied, not on accepted or requested configuration.
- capture_armed: unchanged capture module's armed output.
- out_valid: qualified transport availability defined below.
- out_period,out_high0,out_high1,out_high2 (COUNT_W), out_start,out_end
  (WITNESS_W), out_tag (TAG_W): directly forwarded registered raw slot fields.
- expected_period,expected_high0,expected_high1,expected_high2 (COUNT_W),
  expected_tag (TAG_W): registered context latched only at permitted applied
  observation. Used for comparison; never used to populate raw measurement.
- raw_fault_events[3:0], directly forwarded registered capture pulses in order
  {overrun,witness_overflow,period_overflow,incoherent}.
- failure_event (registered one-edge pulse), failure_code[2:0] (registered
  last cause):0 none,1 mismatch,2 incoherent,3 period overflow,4 witness
  overflow,5 overrun,6 unmeasurable application,7 unexpected capture disarm.
  These are private candidate diagnostics, not public enum assignments.

No extra result queue is introduced. Raw payload can remain visible while
out_valid=0 until the capture receives its next sampled flush; such fields are
unqualified and cannot be handshaken. expected fields clear whenever the
registered binding closes. Public consumers must use out_valid, and even a
handshaken record proves only this local digital association.

## Edge convention and actual-applied observation

Every input is binary and synchronous. At a rising edge E, all three modules
read their pre-edge states/inputs and then update registers. The external
handshake at E is pre-edge out_valid && out_ready. New registered output values
are visible after E; no same-creation-edge bypass is possible.

Let T=cfg_valid&&cfg_ready evaluated before the edge. T can be a legal accepted
command or an illegal rejected attempt; either deliberately invalidates the old
binding immediately. A value held while cfg_ready=0 is not T; pending itself
already keeps capture closed. This conservative policy may discard a usable
old window for a rejected transfer. Recovery then requires another legal
command to be actually applied; rejection never silently reopens old binding.

The generator's accepted/rejected outputs are registered notifications after T.
accepted does not mean applied. The generator applies old pending only on its
actual application edge A0 (startup or its frame boundary), updates its active
tuple/pwm and asserts registered applied after A0. Another always_ff observes
that applied value on edge O=A0+1, together with the active tuple produced at
A0. Use this real module output. Never substitute accepted, cfg_valid,
frame_start, guessed phase, intended command or expected tuple for it.

If a new transfer T occurs at O, it outranks opening the prior application:
close capture and wait for that new command's later actual application. Because
old pending holds cfg_ready=0 at A0, the generator cannot apply and accept a
different transfer on the same edge. It may accept on the next edge O.

Every actual application is a distinct boundary even when tag AND tuple repeat.
The module uses the event and flush, not tag uniqueness. It intentionally has no
global application counter, session ID, request ID, capture_seq or timestamp.
An external observer cannot identify repeated applications from tag alone.

## Measurable subset and readiness

Keep the generator's original legal domain: period>=1 and each high<=period.
Its accepted/rejected/pending/running/PWM behavior is unchanged. The wrapper's
R/F/R-eligible subset is period>=2 and 1<=each high<period. An actual application
outside that subset continues normal generator operation but cannot open a
measurement window: failure_event=1/code6 on observed applied, window_active=0,
expected fields zero, capture flushed. Do not fabricate zero/full-duty widths.

R/F/R eligibility does not guarantee a record fits a small witness namespace.
Raw14 still requires genuine R0>=1 and R1<=TMAX with representable differences;
otherwise actual exhaustion closes the window. For internal loopback with a
high application baseline, the first possible record spans local P..2P, so a
namespace shorter than2P can exhaust with no record. Independent samples can
have other phases. No frequency, physical timeout or absence watchdog is added.

## Precise control, comparison and failure rules

Use the following pre-edge definitions. g_* denotes the corresponding public
generator outputs; c_* denotes public capture outputs; W is window_active_q.
P/H0/H1/H2/tag are the registered expected context.

```text
T = cfg_valid && g_cfg_ready
A = g_applied
eligible = g_active_period>=2 &&
           0<g_active_high_yaw<g_active_period &&
           0<g_active_high_pitch<g_active_period &&
           0<g_active_high_speed<g_active_period
H = rst || stop || T || g_pending || !g_running
arm = !H && A && eligible
capture_stop = H || (A && !eligible) || (!W && !arm)
capture_rearm = arm
G = W && !H && !A
F = OR(c_incoherent_event,c_period_overflow_event,
       c_witness_overflow_event,c_overrun_event)
equal = c_out_period==P && c_out_high0==H0 && c_out_high1==H1 &&
        c_out_high2==H2 && c_out_tag==tag
out_valid = G && c_armed && !F && c_out_valid && equal
c_out_ready = G && c_armed && !F && equal && out_ready
```

Wire c_rst=rst and c_stop/c_rearm as above; wire c_window_tag from the
generator active_tag at the arm edge (the same value copied into expected_tag).
No capture_stop/rearm expression depends on c_out_valid or mismatch: that would
create a combinational loop through c_out_valid's existing abort qualifier.
c_out_ready does not cause a combinational bypass and does not control sampling.

The wrapper state/diagnostics update at each edge, in this exact priority:

1. rst||stop: W=0; zero expected fields,window_started,failure_event,failure_code.
2. Otherwise default window_started=0 and failure_event=0.
3. If T||g_pending||!g_running: W=0, zero expected fields and failure_code.
   This is intentional discard, not a measurement fault. No old handshake on T,
   pending, STOP/reset or observed applied because the combinational guard above
   suppresses it before the edge.
4. Else if A: clear failure_code. If eligible, set W=1, copy the actual active
   tuple/tag into expected context, pulse window_started, and let capture_rearm
   latch only the current sampled baseline. If not eligible, W=0/expected zero,
   pulse failure_event and set code6. No actual rising is inferred at this edge.
5. Else if W: inspect the old registered capture signals. An existing raw fault
   closes W, zeros expected fields and emits failure_event/last code, with
   witness4 > period3 > incoherent2 > overrun5 priority. Otherwise, if !c_armed,
   close with code7. Otherwise, if c_out_valid && !equal, close with code1.
   Otherwise retain W/context and previous failure_code.
6. Else keep W=0, context zero and last failure_code; no repeated failure pulse.

After any measurement failure, automatic capture recovery is disabled even
though raw14 itself can recover from some partial faults. The new wrapper stays
closed until a NEW legal configuration is actually applied and observed (same
tuple/tag allowed). There is no standalone rearm input. STOP/reset alone does
not resume; generator startup still needs a legal configuration/application.

A new raw fault produced after edge E masks external out_valid immediately via F.
The wrapper observes it and records closure on E+1 unless a higher-priority
intentional boundary supersedes that old window. Its registered W may remain1
between E and E+1, but cannot expose a valid record while F or !c_armed holds.
Once W closes, capture_stop is asserted; raw payload may clear on the following
edge. This documented registered latency does not allow a post-fault handshake.
A pre-edge handshake of an already completed record at E is permitted when the
fault first arises after E: the record belonged to the earlier, same-application
interval. It does not claim liveness/freshness at E. Configuration/STOP/reset
boundaries differ: T/H is already known before E and suppresses that handshake.

A mismatching raw slot is never external-valid. Its old registered values cause
code1 on the next edge; capture is then flushed through W=0. No expected count
is substituted into raw fields. A valid matched record has the real raw period,
three high counts,local witnesses and tag; equality is only local consistency.
An old matched slot may wait while armed, but raw overrun/exhaustion/error closes
the window as above. Backpressure cannot stall sample acquisition. No claim is
made about lost physical frames or source authenticity.

## Literal timing examples to pin the implementation

Example1, startup P=3,H=(1,2,1), legal opaque tag K, no new transfers:

- Edge0 sampled reset. Edge1=T accepts; pending=1 after1; no binding.
- Edge2 actual generator application: applied=1, active tuple and first PWM
  state after2. Capture is still stopped by old pending at2.
- Edge3 observes old applied=1 and opens the R/F/R window. Current sample7 is
  baseline, not R0; expected context now equals the active tuple.
- Independent samples at4=0,5=7,6=2,7=0,8=7 produce genuine local witnesses
  start2/end5, period3, highs1/2/1. First external valid appears after8;
  earliest handshake is edge9 if ready. Counts come from those samples.
- In a separate actual digital loopback, edge3 baseline sees PWM7; local R0
  occurs at3+P=6 and R1=3+2P=9. These are a different input schedule, not a
  contradiction or a fabricated sample from desired counts.

Example2, ready old matched slot plus a new T: pre-edge out_valid is suppressed,
even if tag/tuple repeat and out_ready=1. Capture flushes atT, remains stopped
while pending, and waits through the real application notification. Neither
accepted nor repeated numeric equality preserves the old slot or partial.

Example3, P=2/H=1 and WITNESS_W2: an independent schedule R0 at local1,falls2,
R1=3 can produce one matched raw record. At the next edge namespace exhaustion
arises; output is masked and wrapper failure4 appears on the following edge.
Actual loopback from high baseline instead needs local2..4 and cannot complete
before exhaustion. No loopback record may be invented from the active tuple.

## Independent main acceptance, before reading author15 implementation

Main freezes a separate command/application-event model and absolute sampled
edge model/inputs before reading author15 code. Expected generation scheduling
is derived from the already accepted12 port contract; measured counts are
derived from independent sample schedules and absolute first-fall indices.
Import no author model and never fill measurements from desired/active tuples.
Author15 must not read main's oracle/tests. Internal loopback is supplemental;
the main suite must also use independently controlled correct,wrong,phase-shifted
and missing-edge sample inputs, including a new tuple's matching waveform
present BEFORE that tuple is actually applied.

Required independent actual ModelSim coverage:

1. Literal startup/registered-applied delay above; accepted while pending is not
   applied; commands at every phase of bounded frames; back-to-back submissions
   including a new T on the observation edge; illegal attempts and stalled valid.
2. Every legal small generator tuple for COUNT_W2/3 classified consistently:
   1394 legal command triples total (including constant/full/period1),450 R/F/R
   eligible triples. Complete sampled records for the eligible subset with
   adequate witness space; no width invention for the other944 tuples.
3. Same tag/same tuple reapplications, different tuple/same tag,zero/full64 tags,
   quick applications with insufficient complete cycles, old partial/queued
   data and ready conflicts at transfer, actual application and observation.
4. Reset/STOP at every bounded phase and handshakes; known control priorities;
   continuous held controls; no output until a future genuine common R0/R1.
5. Correct external measurements, wrong period or any high, equal-period phase
   shifts, extra/early/missing edges, constant input, mismatching old raw slot;
   prove raw/expected separation and failure1..7 semantics (code7 may require a
   deliberately faulty copy; do not force internal state in the correct design).
6. Empty/full result slot, long stall, no same-edge creation bypass, raw fault
   versus old retirement, overrun closure, small count and witness exhaustion,
   explicit new actual application recovery, repeated tags on every recovery.
7. Fully observed representative16-bit period65535 and raw overflow65536 with
   adequate witnesses; maximum32/64 widths only bounded observations; no seeding,
   hierarchy/force, claimed maximum traversal, physical frequency or time claim.
8. At least two real isolated faulty-wrapper copies rejected at public ports:
   one defers T invalidation until a registered notification and incorrectly
   handshakes an old result; another retains same-tag application state and
   splices/exports an interval without the required complete post-boundary
   cycle. A mismatch-admission mutant is useful additional discrimination.
   A compile error is not a successful negative-control rejection.
9. Explicit wrapper invalid-parameter diagnostics including zero/negative and
   too-large representatives; exact immutable12/14 hashes before/after. Real
   commands,versions,stdout/stderr,exits,input rows and raw public-port traces.
   RLE may compress storage but every repeated edge is checked; count samples,
   assertions,triples and scenarios separately. Preserve all failures/corrections.

Code7 is a defensive interface-invariant failure, not a new normal acquisition
event. The normal accepted composition should never reach it without an earlier
raw witness event or an intentional boundary, both of which have higher priority.
Do not claim a normal-domain test for an unreachable condition.

## Delivery and remaining gates

After actual scope CONTINUE, exactly one Flash/max executor; main independently
accepts final exact bytes and publishes a new source/request/manifest on existing
PR30. Use a fresh private publication directory/helper, bind op15/work15 BEFORE
the first API request, and preserve every actual response under unique names.
The op14 wrapper class/hash9f54798abd76f67014141d845495fad2364d5c2aed21dac19749b82062dd33a3
and its53-response audit are read-only references. The legacy client remains
df1c53fc95a423beb65915604d2525739c4338ecc416c3e8909472c2db8d1b6f and unchanged.
Use blob OIDs for long-path raw comparisons. Unknown writes or stale readbacks
require exact reconciliation; never replay ref/object/commit operations.

Historical op13 missing15 raw404 responses and op14 author preparation gaps stay
disclosed; neither history can be repaired by new evidence. No old source/test/
publication replay. This scope introduces no public register/TRACEtype7/HWH/BOOT,
pins,clock rate,CDC/RDC,physical capture,trusted source/session/request/control_epoch/
capture_seq,host timestamp,TTL/profile/curvature or dual-chain motion permission.
The actual G05 applied-command/full-cycle/system binding remains unaccepted.
Missing Vivado keeps synthesis/implementation blocked; all29 formal cards stay
not_run/unaccepted. Main submits this scope once to the existing coordinator and
consumes the original message_id's actual result; no model polling,Goal,
automation,self-queued READY or second director.
