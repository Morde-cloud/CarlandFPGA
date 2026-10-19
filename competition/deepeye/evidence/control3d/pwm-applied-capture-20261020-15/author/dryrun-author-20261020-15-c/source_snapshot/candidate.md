# Internal actual-application PWM capture candidate

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1`, operation
`B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15`.

Status: candidate-only internal synchronous composition with author-side local
ModelSim simulation evidence. This note does not self-accept, publish, claim a
public ABI, or claim synthesis, implementation, CDC/RDC, board, system, or
physical measurement results.

## Contract and immutable inputs

- Contract `DEEPEYE-HUMAN-LOCK-20261014` revision 1, H01-H15, pinned at
  `f5989cd5defce561f9ba98e6b18fc2682945f0a2`; canonical `requirements`
  SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
- Frozen design `1011259415a0916054eb580687612580bc1e5f09`; baseline
  `7dd2c4108ee49cc6e0feb7c715d786f8b11a99c2`.
- `deepeye_atomic_pwm.sv` SHA256
  `9dc8ecf96e59a2ae8467bda64572f62eb602d52db535733f236f64ff97c43428`.
- `deepeye_pwm_coherent_capture.sv` SHA256
  `4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456`.

Both immutable modules are instantiated through their public ports only. Their
source, interfaces, tests, evidence, and historical suites are untouched. The
wrapper does not duplicate their counters, infer private phase, use hierarchy,
force internal state, or seed counters.

## Scope preservation

This local composition preserves H01-H15 by leaving the generator and capture
contracts intact: full 3D/UI, hollow edge-only cube, solid-volume collisions,
free camera/layout/entry/exit, equal blue/red gates and complete passage, hidden
obstacle truth, device-bounded causal observation, substantive online 3D PC AI,
and both `PC_DIRECT` and FPGA-output control paths remain project requirements.
The wrapper only associates an observed sample stream with an actually applied
generator tuple. It provides no physical board, clock, source, register, BOOT,
TRACE type-7, HWH, TTL, profile, curvature, motion, or public control authority.
Machine A alone may operate the physical board.

## Parameters and interface

Parameters: `COUNT_W=32` (2..32), `WITNESS_W=64` (2..64), `TAG_W=32` (1..64).
Unsupported values are rejected at simulation time zero with one explicit
diagnostic printing all three original values and safe clamped widths. The
clamped widths exist only so invalid representatives can reach that diagnostic;
supported widths are exact. There is no hardware initial state; sampled reset is
mandatory.

Inputs: `clk`, `rst`, `stop`, `cfg_valid`, `out_ready`,
`sample_levels[2:0]`, `cfg_period`, `cfg_high_yaw`, `cfg_high_pitch`,
`cfg_high_speed`, and `cfg_tag`.

Generator outputs are forwarded unchanged: `cfg_ready`, `accepted`, `rejected`,
`applied`, `frame_start`, `running`, `pending`, `pwm[2:0]`, `active_period`,
`active_high_yaw`, `active_high_pitch`, `active_high_speed`, and `active_tag`.
The inherited bit mapping is `pwm[0]=yaw`, `pwm[1]=pitch`, `pwm[2]=speed`; this
does not freeze a new public axis or control ABI.

Additional outputs:

- `window_active`: registered binding state.
- `window_started`: registered one-edge pulse only on a permitted observation of
  actual applied, never on accepted or requested configuration.
- `capture_armed`: the capture module's public armed output.
- `out_valid`: qualified transport availability.
- `out_period`, `out_high0`, `out_high1`, `out_high2`, `out_start`, `out_end`,
  `out_tag`: directly forwarded registered raw slot fields.
- `expected_period`, `expected_high0`, `expected_high1`, `expected_high2`,
  `expected_tag`: registered context latched only at a permitted actual
  application observation; never used to populate raw measurements.
- `raw_fault_events[3:0]`: forwarded registered capture pulses in the order
  `{overrun,witness_overflow,period_overflow,incoherent}`.
- `failure_event`, `failure_code[2:0]`: registered one-edge pulse and last cause:
  0 none, 1 mismatch, 2 incoherent, 3 period overflow, 4 witness overflow,
  5 overrun, 6 unmeasurable application, 7 unexpected capture disarm.

No extra result queue or slot is introduced. Raw payload may remain visible while
`out_valid=0` until the next sampled capture flush; such fields are unqualified.
Expected fields clear whenever the registered binding closes. A consumer must use
`out_valid`; even a handshaken record proves only this local digital association.

## Frozen control and comparison rules

All inputs are binary and synchronous. At a rising edge E, modules read pre-edge
states and inputs. The external handshake at E is pre-edge `out_valid &&
out_ready`; new registered values are visible after E. The wrapper uses:

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

`W` is `window_active_q`; `P/H0/H1/H2/tag` are the registered expected context.
`T` includes an illegal rejected transfer and immediately masks/flushes the old
binding. `H` outranks `A`, pending, STOP, and reset. `capture_stop`/`capture_rearm`
never depend on `c_out_valid` or mismatch, avoiding the capture module's
combinational abort qualifier loop.

Registered wrapper state updates in this priority:

1. `rst||stop`: `W=0`, zero expected fields, `window_started`, `failure_event`,
   `failure_code`.
2. Default `window_started=0`, `failure_event=0`.
3. `T||g_pending||!g_running`: `W=0`, zero expected fields and `failure_code`;
   intentional discard is not a measurement fault.
4. Else if `A`: clear `failure_code`; if eligible set `W=1`, copy the actual
   active tuple/tag, pulse `window_started`, and rearm only the current sampled
   baseline; if ineligible set `W=0`, zero expected fields, pulse
   `failure_event`, and set code 6.
5. Else if `W`: close on the old registered raw fault with priority witness 4 >
   period 3 > incoherent 2 > overrun 5; else `!c_armed` gives code 7; else
   `c_out_valid && !equal` gives code 1; otherwise retain.
6. Else keep `W=0`, zero context, and the last `failure_code`; no repeated pulse.

Every actual application is a distinct boundary even when tag and tuple repeat.
The wrapper uses the applied event and a full flush, not tag uniqueness; it has no
application counter, session/request ID, `capture_seq`, or timestamp. A new raw
fault masks `out_valid` immediately; the wrapper records closure on E+1 unless a
higher-priority intentional boundary supersedes the old window. A pre-edge
handshake of an already completed record at E is permitted when the fault first
arises after E, because that record belonged to the earlier same-application
interval. Configuration/STOP/reset boundaries are known before E and suppress
that handshake. A mismatching raw slot is never external-valid.

The measurable subset is the generator's original legal domain restricted to
`period>=2` and `1<=each high<period`. Other legal generator tuples continue
normal PWM operation but cannot open a measurement window (code 6, no record).
After any measurement failure, the wrapper stays closed until a new legal
configuration is actually applied and observed; same tuple/tag is allowed. There
is no standalone rearm port. STOP/reset alone does not resume.

## Test coverage

The self-checking testbench uses an independently driven `sample_levels` schedule
as the primary measurement source. `LOOPBACK=1` is an explicitly named
supplemental actual digital-loopback case that wires actual `pwm` to the sample
input; it is not the primary source and grants no source-selection ABI.

Positive ModelSim groups cover:

- startup, accepted-not-applied, registered application/observation delay,
  illegal and stalled transfers, and a new `T` on the observation edge;
- every legal small generator tuple for `COUNT_W=2` and `COUNT_W=3`, classified
  consistently, with complete sampled records for the eligible subset;
- same tag/same tuple reapplications, different tuple/same tag, zero and full-64
  tags, rapid replacement, old partial/slot ready conflicts, mismatch and
  wrong-period/wrong-high controls, constant high input, and a missing closing
  edge;
- reset and STOP at every bounded phase and at a handshake edge, continuous held
  controls, no automatic recovery, and no same-edge creation bypass;
- raw/expected separation, immediate raw-fault masking, the same-edge
  old-record retirement boundary, overrun, witness/period exhaustion, code 1..6
  behavior, backpressure, and explicit recovery with repeated tags;
- a new tuple's matching waveform present before actual application, proving it
  is flushed rather than used as the new baseline;
- a fully observed representative 16-bit period 65,535 and raw overflow at
  65,536; bounded maximum 32/64-width observations;
- supplemental actual digital loopback and loopback witness exhaustion.

Code 7 is a defensive interface-invariant failure, not a normal acquisition
event. The correct composition does not reach it in the tested normal domain.
Code 7 is demonstrated only on a deliberately faulty isolated wrapper copy that
suppresses rearm.

The runner creates isolated public-port mutants and requires behavioral
rejection, not a compile error:

1. delayed `T` invalidation until registered notification, which incorrectly
   handshakes an old result;
2. same-tag state retention/splicing, which exports an interval without a
   complete post-boundary cycle;
3. mismatch admission, which makes a mismatching raw slot externally valid;
4. suppressed rearm, which exposes code 7 and is also rejected on a normal
   same-tag record group.

Invalid-parameter runs cover zero, negative, and too-large representatives for
all three parameters. The runner is fail-closed on `TB_PASS`, `TB_FAIL`,
`Fatal:`, exact diagnostic rows, immutable input hashes before/after, and the
expected mutant/code7 markers. ModelSim may exit 0 after `$fatal`; the runner
does not trust the process exit alone.

## Evidence and reproduction

Every run snapshots exact source/input bytes before compilation and preserves
unique stdout, stderr, ModelSim transcript, WLF, command, exit, and hash records.
Failed or preparatory runs under the author evidence directory are retained.

Portable reproduction from the worktree:

```text
D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 \
  competition/deepeye/tools/control3d/run_pwm_applied_capture.py \
  --modelsim-root D:/modelsim1/win64 \
  --out competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author/run-author-20261020-15-a
```

The runner refuses an existing output directory and does not require private
controller, scope, oracle, old-suite, or main evidence files. The terminal
manifest records the exact five owned paths and their hashes, the evidence-tree
hash, the command/log map, scenario/sample/assertion counts, failures,
corrections, warnings, and limitations.

## Preserved failures and corrections

- A preflight used a relative virtual-environment path; the corrected absolute
  path and both preflight directories are preserved.
- Early ModelSim compile/run attempts exposed PowerShell and `-work` invocation
  errors; those failed directories remain.
- Two startup-group attempts used an offset rather than `offset-1` in the
  testbench frame generator; the corrected runs are preserved.
- A fault-group attempt demanded immediate `capture_armed=0` and produced false
  mismatches; it was corrected to respect the documented one-edge registered
  STOP latency.
- A misleading TB mismatch print showed the tag instead of the differing period;
  it was corrected to print the period.
- The old author14 early temporary preparation metadata was unavailable; this
  work preserves every preflight, compile, debug, source snapshot, and official
  run directory instead.
- A long-stall attempt with `COUNT_W=4` legitimately produced a raw period
  overflow after 15 idle samples. The group was widened to `COUNT_W=8` instead of
  weakening or masking the stall.

## Limitations and gates

This is author-side local digital simulation only. Synthesis, implementation,
place-and-route, static timing, CDC/RDC, physical board operation, system
integration, G05 applied-command/full-cycle/system binding, public
register/TRACE-type7/HWH/BOOT ABI, physical frequency/clock/source/TTL/profile/
curvature/motion authority, and all 29 formal acceptance cards are `not_run`.
Maximum-width coverage is bounded observation, not maximum traversal. Mutant
rejection is public-port behavioral evidence, not a proof against every possible
fault. Main independently decides and accepts final exact bytes; this note and
its evidence do not constitute acceptance or publication.
