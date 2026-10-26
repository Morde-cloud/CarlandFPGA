# G05 external capture engine — author candidate

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-G05-EXTERNAL-ENGINE-20261026-59-v1`, native job
`child-c554397b43b441ceb36afe75abf99445`, canonical child
`01a16ecb-340d-7e22-8a53-184264edb47d`. Main
`01a13b55-095b-7461-8dd5-5476a130bd82` owns the architecture, integration and
independent acceptance. This directory owns only the count-level engine,
its new author benches, runner and this description. Mapper/AXI work belongs
to separate writers. No old RTL is edited.

H01–H15 of `DEEPEYE-HUMAN-LOCK-20261014/revision1` remain mandatory, verified
at `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, canonical requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen design: `1011259415a0916054eb580687612580bc1e5f09`. Input source head:
`42feaa80c4f7756226500bf891e05625772120cf`. Physical board operation is A-only.
Author simulation does not close G05, all29, R03, fullH12, CDC, synthesis,
implementation, physical timing, or product acceptance.

## Interface and composition

`deepeye_g05_capture_engine` has exactly the parent's requested ports and no
tunable production parameters. Three packed 32-bit slices are yaw, pitch,
speed, low to high. Packed 64-bit witnesses use the same order. The 64-bit
tag is `{command_id[31:0], opaque_tag[31:0]}`. The engine checks count legality;
the production top must use the main's fixed mapper and wrapper identity rules.
It does not validate a public motion grant, session, profile or duplicate ID.
The wrapper owns exact-current duplicate status and first-profile locking.

The read-only instances are:

| Primitive | Fixed instantiation | Required source SHA256 |
| --- | --- | --- |
| `deepeye_atomic_pwm` | COUNT_W32, TAG_W64 | `9dc8ecf96e59a2ae8467bda64572f62eb602d52db535733f236f64ff97c43428` |
| `deepeye_pwm_coherent_capture` | Three instances, COUNT_W32, WITNESS_W64, TAG_W64 | `4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456` |

Every external pin has its own three-register ASYNC_REG chain. Only its third
register is replicated into its own capture primitive's three sample-level
inputs. There is no internal PWM-to-capture connection. Each capture output
has `out_ready=1`; the engine holds one result per channel while joining.

A ready handshake requires a live, nonpending engine without an already due
terminal condition. Legal counts are period>=32, all highs strictly between
zero and period, and positive TTL. Count violations pulse `rejected`, retire
the engine and prevent output. Arithmetic overflow is classified separately
as fault5. While `cfg_ready=0`, `cfg_valid` is ignored without accepted/rejected
pulses. Only one command can be pending. The engine keeps pending asserted
through observation of the primitive's registered application event, giving
one observation-edge bubble before accepting another command.

## Exact edge and timestamp semantics

On synchronous reset, cycle_tick=0. Each nonreset rising edge advances it by
one; at maximum it saturates. The would-wrap edge terminally fails with fault5.
Cycle accounting can continue after an earlier terminal failure, but that
first fault is retained. Reset alone clears terminal state and allows restart.

Call the actual atomic PWM application edge **A**. The primitive changes all
three outputs and raises its registered applied indication on A. The engine
observes that indication on A+1 and pulses its own `applied`. It records
`applied_tick=A`, using the pre-edge cycle_tick, not A+1. The new deadline is
`A+ttl_ticks`, evaluated with a 65-bit carry check. The actual new tag is exposed
with the primitive event, then held for terminal evidence.

The old command's deadline gates the actual prospective application edge.
Expiry on that edge stops the primitive and cancels the pending command.
After a genuine new application has already occurred, the delayed observation
does not let the old deadline kill the newly applied command. TTL=1 therefore
allows the A-to-A+1 interval and drives PWM low on A+1, while preserving its
actual application event, tag and exact deadline. No accepted-but-unapplied
command, capture result, host read, ACK or duplicate input renews TTL.

Main design revision1 explicitly allows rearm at A+5 **or later with a precise
documented edge**. This implementation uses **A+7**. The observed application
on A+1 sets a countdown of six. Three synchronizer stages, the primitive's
sampling edge and the allowed two-tick external pin skew have then reached a
common baseline. All three capture primitives rearm on the same A+7 edge and
set witness zero there. An already-high pin is a baseline, not a new rise.

The first attempt used A+5. The new public-port delay0/1/2 control showed that
the initial two-tick-delayed pin could rise after that baseline and produce a
record one frame ahead of its peers. The failure is preserved in run-01. Moving
to the explicitly permitted later A+7 edge corrected that observed case; no
capture tolerance, watchdog, source or policy was relaxed.

For the bench's falling-edge scheduled loopback fixture with delay d, a raw pin
rise sampled at edge R is observed by capture at R+3. Its witness is R+3-(A+7).
A zero-delay first complete capture has start=P-3, end=2P-3 and result_tick=A+2P+5.
The latest channel's digital delay adds to that result edge. These are the
specified digital bench timings, not physical delay or metastability bounds.

## Capture, joining and retirement

New acceptance immediately invalidates the latest result and all join
eligibility, and abandons old partial eligibility. The primitive capture state
is held stopped while pending and while waiting for the new baseline. Old PWM
and its TTL continue until actual application or retirement. No old partial
is eligible for a new-command result.

Every incoming channel record must have the current tag, a positive high less
than period, period/high absolute deviation<=2 from the actual applied counts,
identical replicated high fields, strictly ordered nonzero start/end, and
end-start equal to period. After a previous joined record, that channel's next
start must exactly equal its previous end. A duplicate channel before the join,
any primitive error, malformed tag/field, or cross-channel start/end spread>2
is terminal. This prevents adjacent or missing frames from being silently
spliced. The three raw measured periods, highs and witnesses are recorded.

First watchdog deadline is `A+3*period+16`. Each good joined result sets the
ongoing deadline to `result_tick+2*period+16`; all calculations are at least
65 bits before checking carry. A valid good join on the watchdog deadline wins
over timeout. Reset, STOP, TTL and existing fatal conditions outrank it.
Monitoring is continuous and independent of host activity. The latest result
can be replaced; result_seq starts at1 and advances across commands without
wrapping. A good record after sequence maximum retires with fault5.

| Fault | Meaning |
| --- | --- |
| 0 | No terminal fault |
| 1 | Invalid period/high/TTL counts |
| 2 | TTL expiry |
| 3 | Capture field/skew/tag/duplicate/primitive event, or unexpected primitive application metadata |
| 4 | Capture watchdog timeout |
| 5 | Cycle/sequence exhaustion or checked deadline/watchdog arithmetic overflow |
| 6 | Explicit STOP before any previous terminal failure |

Reset dominates STOP and clears all state. STOP is terminal even while idle.
External STOP/reset drive the atomic primitive's stop/reset on their edge;
TTL is computed before the deadline edge and also stops on that exact edge.
Detected capture faults invalidate the result on discovery and feed the
primitive stop directly; the requirement is no later than the next edge.
The benches check the public PWM timeline. Invalid payloads never drive output.

Once halted, the engine retains the **first** fault_code, deadline and last
applied command evidence. Continuously asserted wrapper STOP cannot overwrite
TTL/capture/overflow faults with6. Only hardware reset clears them. Result data
bits may remain as invalid historical evidence, but result_valid is zero.

## New author execution and evidence

Use the runner only with a fresh output under its declared private engine root:

```powershell
& D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 `
  D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/fpga/diagnostic/g05_capture/engine/run_engine_author.py `
  --repo D:/pynq/CarlandFPGA `
  --output D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/g05-capture-20261026-59/engine/<new-run> `
  --modes small production fault_injection boundary
```

These are new ModelSim10.7 benches, not a replay of old suites. The runner
verifies both read-only source pins, snapshots all executed sources and itself,
records exact tools/versions/commands/PIDs/exits, and launches hidden suspended
processes into its own Windows job using the pinned existing helper. It requires
exit0, no Error/Fatal/nonzero error summary, one exact completion marker and
unchanged inputs. ModelSim exit0 after `$fatal` is insufficient. Every output
directory is exclusive, and failed attempts are never overwritten or retried
automatically. Raw transcripts, process logs, public edge CSV and selected
public-signal VCD waveforms remain available. The clock and free-running counter
are omitted from VCD to keep the production-period waveform bounded; VCD time
and recorded result/application ticks retain the edge timing.

`tb_g05_capture_engine.sv` has no private hierarchical reads/forces. Its short
mode covers synchronous lifecycle phases, atomic update and busy handling,
TTL1/2/31/32/33/65, old-expiry/application coincidences, independent pin delay and
skew0/1/2/3, count tolerance boundaries, wrong distinct channel wiring, missing
rises/falls, continuously replacing results, exact first watchdog good-at-deadline
and ongoing timeout, and persistent wrapper STOP after earlier faults.

Production mode uses the full2,000,000-tick period with frozen mapping qyaw=0,
qpitch=0, speed_code=0: highs250000/250000/50000. TTL10,000,000 ticks is100ms at the
candidate100MHz rate. It waits for two complete postbaseline external captures
over multiple full periods, verifies the measured counts/witnesses and then
explicitly stops. No mapper implementation or physical frequency is claimed.

`tb_g05_capture_exhaustion.sv` is separately labeled fault injection. It forces
cycle_tick/result_seq near exhaustion, then checks saturation, checked watchdog
addition and terminal nonwrapping behavior. Those states were not reached by
waiting2^64/2^32 public events. Normal port tests remain separate. No analog
metastability, board wiring, identical-waveform swap detection, hardware clock,
full65-bit state-space proof or independent main acceptance is claimed.

`tb_g05_capture_boundaries.sv` adds three public-port controls: a period whose
`3*period+16` exceeds32bits must retain its later TTL deadline without a false
early watchdog; legal high counts1 and period-1 must capture correctly; and a
channel missing a whole frame must terminate rather than join adjacent frames.
There are no hierarchical reads or forces in this bench.

The original run-01 waveform visibility errors and the A+5 skew failure remain
intact. The completed author executions are:

| Attempt / mode | Cases | Checks | Result |
| --- | ---: | ---: | --- |
| run-02 / small | 38 | 1091 | exit0, zero errors |
| run-03 / production | 1 | 12 | exit0, zero errors |
| run-03 / explicit fault injection | 3 | 7 | exit0, zero errors |
| run-04 / boundary | 3 | 32 | exit0, zero errors |

Thus42 public-port cases/1135 checks and3 separate injection cases/7 checks
completed. All completed runs used identical final engine RTL bytes. The
runner gained the boundary-mode dispatch after run-03; its exact executed
version is preserved per run. No RTL or existing bench changed for run-04.
The private author RESULT and evidence manifest provide exact source hashes,
commands, raw logs and limitations. Main owns independent acceptance of these
bytes before synthesis or hardware use; these are author simulation results.


## Main R4 structural repair after actual R3 failure

The original R3 routed candidate failed 100MHz setup (WNS -12.767ns,
TNS -33053.863ns, 5958 endpoints) and had one LUTLP-1 combinational loop.
Its original source, reports and terminal process remain preserved; no R3
bitstream was generated. Prior passing digital tests were not timing proof.

Main removed capture-derived `failure_now` from the internal rearm schedule:
rearm still depends on registered countdown and reset/STOP/halted. The original
feedback travelled through capture out_valid (masked by rearm/stop), join and
fault logic back into rearm. A simultaneous terminal failure still wins the
unchanged engine sequential branch and immediately stops PWM. An internal
baseline pulse on that edge cannot produce a public record; halted suppresses
capture next cycle. All registers, event edge definitions, fault priority,
command/TTL rules and fixed read-only primitives are retained.

The 64-bit start/end skew test now checks all three unordered pair distances.
For a=4A+u and b=4B+v, equal high groups reject only low pairs0/3; adjacent high
groups require preceding-low>=following-low+2. A widened63-bit high increment
retains carry, preventing max-to-zero alias. Larger high-group separation is
at least five counts. Thus pairwise distance<=2 is exactly equivalent to the
previous max-min<=2 for known unsigned values; no tolerance is widened.

The full-composition runner pins this revised engine. The private arithmetic
oracle and new rearm-boundary comparison have their own evidence and do not
replace full composition or actual synthesis/route. The build now explicitly
rejects LUTLP-1 even though Vivado classifies it as Critical Warning. No clock
period, IO delay, false-path scope, board ownership or formal gate is relaxed.
Only the exact subsequent build receipt can establish new physical-tool results.


## Main R5 arithmetic after actual R4 timing failure

R4 removed the loop (actual routed check: zero loops), but failed 100MHz
setup with WNS -6.687ns, TNS -18588.086ns and6256 endpoints; hold +.044ns.
The full original failure and closed96-process job are retained, with no bit.
The worst path was rearm_wait through selected joined witnesses and the
62-bit successor carry chain into PWM reset, 30logic levels/17CARRY4 cells.

R5 expresses nonwrapping successor as eight byte cases: exactly one byte
increments using nine bits, all lower bytes go FF->00, all higher bytes match.
Each possible carry stopping byte is a separate, disjoint case. MAX->0 cannot
match any case. The high-group near-two argument above remains exact; the
32-bit distance test uses the same helper after zero extension. All engine
sequential statements, CDC chains, deadline/STOP priorities, ports, rearm and
tolerances are byte-for-byte unchanged fromR4. Four-state exhaustive semantic
equivalence is not claimed; digital operation remains gated by reset/identity.

The build adds a placement physical-optimization pass, then the same routing,
DRC, no-loop and min/max timing gates. No clock, IO, CDC exception or gate is
weakened. Arithmetic/simulation qualification does not prove route timing;
only the new exact-source execution can establish that result.
