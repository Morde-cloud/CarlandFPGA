# Three-channel synchronous raw capture with common sampled-edge witnesses

Task DEEPEYE-IMPLEMENTATION-20261014/v1; sole B product director
01a13b55-095b-7461-8dd5-5476a130bd82, actual App turn
01a154e7-12a1-7e12-ad4a-c4e2577b93b9. Parent work
B-LOCAL-COHERENT-CAPTURE-CONTINUE-20261020-v1; instruction operation
B-LOCAL-COHERENT-CAPTURE-CONTINUE-20261020-v1-DIRECTOR-SCOPE. Proposed product
operation B-DEEPEYE-PWM-COHERENT-CAPTURE-20261020-14 and ONE Flash/max work
B-PWM-COHERENT-CAPTURE-RTL-20261020-14-v1. Current authorization is this scope
freeze and substantive coordinator review; no worker before actual CONTINUE.

H01-H15, DEEPEYE-HUMAN-LOCK-20261014/revision1, requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804,
contract pin f5989cd5defce561f9ba98e6b18fc2682945f0a2 and frozen design
1011259415a0916054eb580687612580bc1e5f09 remain fixed. Preserve full game-grade
3D/UI, hollow edge cube, solid-volume collisions, free camera/editable/random
layouts/free faces, equal gates and full passage, hidden truth, device-bounded
causal observation, substantive online3D PC AI and both control paths. This
primitive cannot waive any of those requirements. All29 formal cards, full
G05/B06/R03, board/system and CDC/RDC remain not_run/unaccepted. Physical board
is A-only; actual Vivado reports are needed for synthesis/implementation.

## Exact inputs and independent ownership

Use existing worktree D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014.
Baseline local/PR30 head732a58ba60c7cce0027d683e912d986453755843; op13 tested
source923e19dedf53b0b38134e4a7da3cc121d8c0e505; request
1a3bf5940f10ae3d0076ecb192490dfcd8e672efc9ab507194e8031b3ae5fd33;
manifest47382b6eeb6a9fd24b60f6c0d209328c141a4e3f513a55c472e7313b50121230.
Its completed coordinator ACCEPT decision SHA256 is
5112037dbeb712b5bff4eca01d88bea12ae2eb99a4b83d8aa38644a1cb1a6acf;
next-scope instruction SHA256 is
d923c0bb113bfac95180a298f966d4110b223cefa67d7131e6c9e96ecb674c69.
Current ledger: zero active jobs, zero pool instances, no duplicate work14.
All proposed product paths are absent. Fresh PR30 has six comments/zero reviews,
no comment after6273192999. That A feedback accepts only software10/reference
and11/candidate at testedcd48ae7; it grants no12/13 acceptance or new register,
HWH/extension/TRACEtype7 authority. A's public ABI remains untouched.

Choose a NEW shared capture state machine in its new RTL file. It directly
observes all three sample bits and stores common start/end witnesses. It does
not compose three transport queues whose identical numeric periods might come
from different frames. Existing op12/op13 modules/interfaces/tests/evidence are
immutable inputs and are neither modified nor rerun. No generator, requested
command, internal signal or hierarchical force supplies a measured width.

## Interface and widths

Module deepeye_pwm_coherent_capture. Parameters:

- COUNT_W=32, supported2..32; CMAX=2**COUNT_W-1, unsigned.
- WITNESS_W=64, supported2..64; TMAX=2**WITNESS_W-1, unsigned.
- TAG_W=32, supported1..64.

Inputs: clk, rst, stop, rearm, sample_levels[2:0], window_tag[TAG_W-1:0],
out_ready. All are binary synchronous values sampled on rising clk. Channel
indices0/1/2 are raw lanes, not newly assigned public motion axes. Transitions
between samples, analog behavior, synchronizers, pins and physical frequency
are outside this contract. Explicit sampled reset is required before use.

Outputs: armed, out_valid; out_period and out_high0/out_high1/out_high2, each
COUNT_W bits; out_start/out_end, each WITNESS_W bits; out_tag TAG_W bits;
incoherent_event, period_overflow_event, witness_overflow_event, overrun_event;
corresponding incoherent_seen, period_overflow_seen, witness_overflow_seen,
overrun_seen; and fault_count COUNT_W bits. All payload, armed and diagnostic
outputs are registered. Only out_valid is the occupied register qualified by
!rst && !stop && !rearm. No other combinational input changes payload.

Unsupported widths receive an explicit time-zero simulation diagnostic,
excluded from synthesis. Use width-safe constants and harness comparisons so
zero/negative representative widths can reach that diagnostic instead of
failing an unrelated replication or part-select. No hardware initial state.

## Window, witnesses and priority

On rst or stop, highest priority: armed=0; clear previous samples, local tick,
partial state/counts/masks/start, window tag, occupied/payload, all diagnostics
and fault_count. out_valid is suppressed on that edge, so there is no old
handshake or new record. Deassertion alone does not arm capture.

Next priority is rearm: armed=1; local tick=0; latch window_tag and current
sample_levels as the baseline; clear every partial, queued result, diagnostic
and fault_count. The edge itself is never a captured rise/fall. Held rearm
creates a fresh empty baseline each edge, producing no record/fault. Tag
changes without rearm are ignored. Zero/repeated tags are legal opaque values;
they are NOT globally unique identities or evidence of applied commands.

Each subsequent ordinary armed edge advances the local tick by one if the old
tick is below TMAX. The new value t is the witness for events sampled on that
edge. Therefore a permitted start is strictly after rearm, with start>=1.
A record has start<end<=TMAX, period=end-start, high_i=first_fall_i-start,
and 1<=high_i<period<=CMAX for all three lanes. Arithmetic is nonmodular; no
wrapped timestamp or tick subtraction may justify a record. The witnesses are
local sampled-clock indices within this rearm window, not host/global time,
BOOT identity, capture_seq, source liveness or an A public clock ABI.

On an ordinary armed edge with old tick==TMAX, the would-be next witness cannot
be represented. Before any input/candidate processing, pulse witness_overflow,
set its sticky flag, increment fault_count with saturation, set armed=0, and
clear the partial. Freeze local tick at TMAX. No event at a fictitious TMAX+1
is captured and no automatic wrap/re-arm occurs. A new explicit rearm is
required. This single representation-exhaustion event occurs even if no partial
exists; it is not evidence of missing signal or a physical timeout/watchdog.

At t==TMAX itself, ordinary event processing remains legal. A record may close
there, or a partial may begin there and be abandoned on the following edge.
If WITNESS_W is small, its finite window can end before CMAX periods are
possible. The interface promises no otherwise-unrepresentable capture.

Result transport is independent of armed. A correctly completed old result may
remain queued after witness exhaustion; an old ready/valid handshake still
retires it on the exhaustion edge or a later unarmed ordinary edge. Its counts,
witnesses and tag remain unchanged while stalled. Its out_valid conveys ONLY
transport availability, not current waveform validity or fresh capture.

## Shared observed start, falls and end

On each ordinary armed edge where witness exhaustion did not occur, calculate
rise_mask=(~previous)&sample_levels and fall_mask=previous&(~sample_levels),
restricted to three bits, then update previous to the actual sample_levels.

While idle:

- rise_mask==111 starts a new shared measurement: start=t, age=0,
  fall_seen=000, high counts=0. It cannot produce a record.
- A nonzero proper subset rise_mask pulses incoherent_event, sets its sticky
  flag and increments fault_count; remain idle. This reports an actually
  observed unequal start, not a missing-edge timer.
- No rising bits means keep waiting without an acquisition fault. Falling
  bits from a high rearm baseline are ignored; a future common fresh rising
  is necessary. Constant initial levels produce no measured period.

While a partial exists, age denotes elapsed intervals since its common R0.
If old age==CMAX, the new interval would be CMAX+1: pulse period_overflow,
set its sticky flag, increment fault_count, and abandon the partial before
candidate completion. If rise_mask==111 on this overflowing edge, use this
genuine common rising as a NEW start=t/age0 with empty falls; otherwise become
idle. This makes an R1 at elapsed CMAX legal and elapsed CMAX+1 invalid.

Otherwise, elapsed=old age+1 is representable:

- With no rising bits, latch the first falling edge of each lane at its actual
  elapsed count; set that lane's fall_seen bit. Keep the shared partial and
  advance age. Each lane must fall strictly after the common start.
- With a nonzero proper subset of rising bits, pulse incoherent_event,
  set its sticky flag, increment fault_count and abandon ALL partial lane
  counts/masks/start. No old lane survives to splice with a later frame.
  This includes an early rise coincident with another lane's first fall.
- With rise_mask==111, a record requires all three fall_seen bits and all
  high_i in1..elapsed-1. Its shared start is the stored R0 and end=t. Otherwise
  report one incoherent_event and produce no record. Either way, this genuine
  common rise is the next shared R0 at age0, with all new falls cleared.

Extra rising edges, phase-shifted equal periods and unequal completion edges
therefore cannot be accepted by numerical equality or transport coincidence.
Loss of an individual edge can only be judged from the sampled stream; the
module cannot detect transitions hidden between sample edges.

## One result slot and diagnostics

There is exactly one result slot. On an ordinary edge, an OLD occupied&&ready
record retires independently of input processing and even if armed=0. A newly
completed coherent candidate may fill an empty slot or replace an old retiring
record. There is no combinational bypass: a candidate in an old empty slot
cannot be consumed on its creation edge. Consumption without replacement
clears occupied and all payload fields to zero.

If a complete candidate arrives when the old slot is full and out_ready=0,
preserve the entire old record, drop only that new candidate, pulse overrun,
set overrun_seen, and increment fault_count. The common closing rise still
starts the next partial. Input sampling never stalls with result transport.
Other partial faults never replace, relabel or promote the older queued record.

At most one fault event is emitted per ordinary edge, with this priority:
witness_overflow > period_overflow > incoherent > overrun. Output retirement
is independent of that priority. Pulses default0 each edge; seen flags stay
set until reset/STOP/rearm. fault_count increments once per emitted event,
saturates at CMAX, and does not suppress later pulses after saturation.
It counts fault/drop notifications, NOT a known number of lost physical PWM
frames: idle unequal-start edges and one witness-exhaustion notification also
count. Intentional reset/STOP/rearm discard clears diagnostics and adds no
fault. Waiting with no observed start emits none except the explicit finite
witness-namespace exhaustion event described above.

## Independent acceptance, frozen before author code is read

Main independently constructs observed event traces and absolute-index
expectations, including each channel's first fall and shared R0/R1. It imports
no worker model and no generator, and stores deterministic input/control/tag/
ready schedules before inspecting author implementation. Preserve the original
freeze and any later harness-only repair with exact differences; never guess
read chronology in an automatically generated field.

Required coverage:

1. Literal examples, including COUNT_W2/adequate witness width: common R0 at1,
   falls at2/3/2, common R1 at4 -> period3, highs1/2/1, witnesses1/4. All legal
   high triples for every period at COUNT_W2 and3:9+441=450 tuples, repeated
   coherent intervals, high1/low1 and exact CMAX boundaries.
2. Phase-shifted equal-period negatives, different end edges, extra/early rises,
   incomplete falls, a constant/missing lane after start, no common start,
   recovery only on a genuinely common future rising. No mixed-frame splicing.
3. Reset/STOP/rearm at every phase, completion and retirement; their priority
   combinations/held controls; high baseline; changing and reused/zero/full64
   tags. A new complete interval begins strictly after its rearm edge.
4. Empty/full queue, long stalls, simultaneous retire/refill, early input faults
   with an older stalled or retiring record, overrun and saturating fault count.
   Witness exhaustion with pending data must test transport while unarmed.
5. COUNT_W2/3 period overflow, including fresh common rise on overflow. Small
   WITNESS_W2/3 actually exhaust the clock namespace and halt without wrapping.
   Example WITNESS_W2: start1/fall2/end3 record is legal, next edge emits exactly
   one exhaustion and disarms; old record may still retire. Co-incident count
   and witness overflow exercises the specified diagnostic priority.
6. Fully observed representative COUNT_W16 periods crossing bit15 and65535,
   overflow65536 with sufficient witness width. COUNT_W32 and WITNESS_W64
   observations remain bounded; no full32/64 traversal claim or internal
   forcing/seeding. Distinguish structural unsigned-width reasoning from runs.
7. Independent randomized three-lane phases, controls, tags and ready; actual
   isolated mixed-frame/relaxed-common-edge or stale-window mutant rejection
   at PUBLIC ports, not merely an elaboration failure. Original RTL unchanged.
8. Supported minimum/maximum parameter elaboration and explicit invalid guards
   with representative zero/negative/out-of-range values. Record actual ModelSim
   compile/run versions, commands, exits, stdout/stderr, public-port replay,
   exact sources and hashes. RLE is allowed only if every repeated edge is
   actually checked; count samples/assertions/cases separately.

No physical-frequency value, absence watchdog or zero/full-duty width is
invented. A constant channel cannot produce R/F/R; this does not capture every
valid op12 generator setting. Later profile interpretation of constant levels
is a separate gate. Opaque tag/rearm is not proof of applying a real command.
G05 still requires the original after-application/full-cycle integration,
session/request/control_epoch/source/capture_seq binding, actual clock/freshness,
TTL/profile/curvature and final motion authority. Both full control chains,
public TRACE/register/HWH/BOOT ABI and formal acceptance remain outside op14.

## Exclusive paths and future publication prerequisite

After actual scope CONTINUE, ONE Flash/max executor owns only these new paths,
relative to the existing worktree:

- competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv
- competition/deepeye/fpga/control3d/pwm_coherent_capture_candidate.md
- competition/deepeye/tests/rtl/control3d/tb_pwm_coherent_capture.sv
- competition/deepeye/tools/control3d/run_pwm_coherent_capture.py
- competition/deepeye/evidence/control3d/pwm-coherent-capture-20261020-14/author/

Main alone owns the corresponding main/ evidence subtree,
tests/rtl/control3d/main_tb_pwm_coherent_capture.sv,
tools/control3d/main_verify_pwm_coherent_capture.py,
handoffs/b/B-DEEPEYE-PWM-COHERENT-CAPTURE-20261020-14/, and private
.local/deployment/node-b/evidence/independent-coherent-capture-20261020-14/.
Main may repair worker paths only after terminal release. No other writer,
main, native lease, App context or worker is created. Duplicate jobs are reused.
Protected dirty codec input SHA256 remains
6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8.
Children cannot commit/publish, read credentials, send peers/groups, operate
boards or alter services/config/SQL/queues/public schemas. Report actual
[需桌面回合]/[需本人操作] blockers with exact IDs/evidence; no presence broadcasts.

PUB13-READLOG01 is retained:15 initial404 lookup raw responses were overwritten
by later same-name200 files. Old timestamps/status/hashes remain, but missing
bytes cannot be verified or recreated. Final365 Git/archive files and mutating
ref/metadata readbacks were verified, so limited op13 acceptance stands.

The NEW private unique_observations.py wrapper assigns a monotonic per-call
prefix to every logical request, including repeated reads. Its fresh phase
directory cannot exist beforehand. It saves the observation index before
calling the existing unchanged client and refuses existing raw paths. Later
reads resolve through that index. Serial calls only; unknown mutation outcomes
remain unknown and are reconciled before any new attempt. The helper and its
local fake-transport proof are pinned in SCOPE_FROZEN.json. The proof retains
distinct404/200 bytes for a repeated logical name and a third separate local
request, with zero network/credential calls. Fresh actual scope reads also use
unique000001.. names. This is a publication prerequisite, not a second worker
or an RTL acceptance. Before a future publication verify this wrapper hash and
the read-only legacy client hash
df1c53fc95a423beb65915604d2525739c4338ecc416c3e8909472c2db8d1b6f.
No modification rights to the older client or any service/config/credential.

After main acceptance, a NEW source/request/manifest may be published through
existing PR30 with force=false and exact remote-byte checks. No old publication
or old simulation replay. Scope and completed review use the existing
B-MAIN-CONTINUATION-20261019/v1 and original returned message_id/main_wait in
the proven distinct App/resident entries. No polling model, timer, READY turn,
Goal or automation. Concrete blocked dependencies remain explicit.
