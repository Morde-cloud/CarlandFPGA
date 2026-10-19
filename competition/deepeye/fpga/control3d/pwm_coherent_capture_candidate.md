# Three-channel synchronous raw coherent-capture candidate

Operation `B-DEEPEYE-PWM-COHERENT-CAPTURE-20261020-14`  
Work `B-PWM-COHERENT-CAPTURE-RTL-20261020-14-v1`  
Task `DEEPEYE-IMPLEMENTATION-20261014/v1`  
Sole technical director `01a13b55-095b-7461-8dd5-5476a130bd82`

Status: **author-side candidate only**. This note, the RTL and the local
ModelSim run are not main acceptance, product acceptance, synthesis,
implementation, CDC/RDC, physical-capture, board or system evidence.

## Immutable scope carried into this candidate

- Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01-H15.
- Requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
  recomputed from JSON `requirements` with `ensure_ascii=False`,
  `sort_keys=True`, `separators=(',',':')`, then UTF-8.
- Contract pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`.
- Frozen design `1011259415a0916054eb580687612580bc1e5f09`.
- Normative scope `SCOPE.md` SHA256
  `f2d8ed287848e536b140629f3f30f7105d2171a6cc0c00be2186d09c9115331d`.
- Frozen receipt `SCOPE_FROZEN.json` SHA256
  `0a8992e32b30e1b084f7392c2941b42e1b3814048d6cd0139f669189353f4eea`.
- Actual `CONTINUE` decision SHA256
  `2290a3e5f69d55f02036d318ac6953e8b0081694c253ff02d65e26461c6b6c99`.
  The consumed receipt is
  `D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/independent-coherent-capture-20261020-14/SCOPE_CONTINUE_CONSUMED.json`
  SHA256 `021672d5204c8d034ea879921f6d0c3b34180ad538b2b49719c5ab4750d8a4a6`.

The full game-grade 3D/UI, hollow edge-only cube, solid-volume collisions,
free camera, editable/random layouts, free entry/exit faces, equal blue/red
gates with complete passage, hidden obstacle truth, device-bounded causal
observations, substantive online 3D PC AI and both PC_DIRECT/FPGA-output
control paths remain requirements. This primitive cannot waive or weaken any
of them.

## Files

- RTL: `competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv`
- Self-checking TB: `competition/deepeye/tests/rtl/control3d/tb_pwm_coherent_capture.sv`
- Runner: `competition/deepeye/tools/control3d/run_pwm_coherent_capture.py`
- Official author run:
  `competition/deepeye/evidence/control3d/pwm-coherent-capture-20261020-14/author/run-author-20261020-14-a/`

Source hashes for the official run:

| Source | SHA256 |
|---|---|
| RTL | `4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456` |
| TB | `6efa84f8b6fa1d56356615a85a702f0372d0957a71eadb870121963b6d42976e` |
| Runner | `bb52d8b2693ff34851b53eefa80d7442ade95bf37dd05c11809c74cf2b86f911` |

## Interface and widths

```systemverilog
module deepeye_pwm_coherent_capture #(
    parameter integer COUNT_W    = 32, // supported 2..32
    parameter integer WITNESS_W  = 64, // supported 2..64
    parameter integer TAG_W      = 32  // supported 1..64
) (
    input  logic clk,
    input  logic rst,
    input  logic stop,
    input  logic rearm,
    input  logic [2:0] sample_levels,
    input  logic [TAG_W-1:0] window_tag,
    input  logic out_ready,
    output logic armed,
    output logic out_valid,
    output logic [COUNT_W-1:0] out_period,
    output logic [COUNT_W-1:0] out_high0,
    output logic [COUNT_W-1:0] out_high1,
    output logic [COUNT_W-1:0] out_high2,
    output logic [WITNESS_W-1:0] out_start,
    output logic [WITNESS_W-1:0] out_end,
    output logic [TAG_W-1:0] out_tag,
    output logic incoherent_event,
    output logic period_overflow_event,
    output logic witness_overflow_event,
    output logic overrun_event,
    output logic incoherent_seen,
    output logic period_overflow_seen,
    output logic witness_overflow_seen,
    output logic overrun_seen,
    output logic [COUNT_W-1:0] fault_count
);
```

`COUNT_W=2..32`, `WITNESS_W=2..64`, `TAG_W=1..64` are the supported ranges.
`CMAX=2**COUNT_W-1` and `TMAX=2**WITNESS_W-1` are all-ones vectors. Widths in
the declaration are exact for supported parameters. For an invalid parameter,
the implementation clamps vector widths only so the time-zero simulation guard
can be reached without an unrelated replication or part-select failure; no
invalid-width hardware behavior is claimed.

Unsupported parameters produce, in simulation only:

```text
DEEPEYE_COHERENT_INVALID_PARAM COUNT_W=<n> WITNESS_W=<n> TAG_W=<n>
```

followed by `$fatal`. The diagnostic is inside
`synthesis translate_off/on`, and there is no hardware initial state.

All payload, `armed` and diagnostic outputs are registered. `out_valid` is the
one exception explicitly allowed by the scope: it is the occupied register
qualified by `!rst && !stop && !rearm`. No other combinational input changes
payload.

## Capture semantics

One shared capture machine observes `sample_levels[2:0]`; it is not three
numeric queues. On each ordinary armed edge it computes, from the previous
sampled vector and the current vector:

```text
rise_mask = ~previous & sample_levels
fall_mask =  previous & ~sample_levels
```

Then it updates `previous` to the actual current vector.

### Reset, STOP and rearm

- `rst` or `stop`, highest priority, clears armed state, previous samples,
  local tick, partial start/age/falls/high counts, latched tag, result slot,
  all diagnostics and `fault_count`. `out_valid` is suppressed on that edge.
- `rearm`, next priority, sets `armed=1`, `tick=0`, latches `window_tag` and
  the current samples as baseline, and clears every partial, queued result,
  diagnostic and `fault_count`. The rearm edge is never a captured rise/fall.
- Held rearm creates a fresh empty baseline on every edge. Tag changes without
  rearm are ignored. Zero/repeated/full-width tags are opaque values, not
  globally unique identities or proof of an applied command.

### Local witnesses and common edges

Each subsequent ordinary armed edge advances the nonwrapping local tick by
one if the old tick is below `TMAX`. The new value `t` is the witness for the
sampled transition. A permitted start therefore has `start>=1` and is strictly
after rearm. A record has:

```text
start < end <= TMAX
period = end - start              (nonmodular)
high_i = first_fall_i - start
1 <= high_i < period <= CMAX
```

While idle:

- `rise_mask==111` starts a shared partial at `t`, `age=0`, with no falls.
- A nonzero proper-subset rise pulses `incoherent_event`, sets its sticky flag,
  increments `fault_count` and remains idle. It reports an observed unequal
  start, not a missing-edge timer.
- No rising bits keeps waiting. Falls from a high rearm baseline are ignored;
  a future common fresh rising is necessary.

While a partial exists, `elapsed=old_age+1` unless the old age is `CMAX`:

- `old age==CMAX`: the new interval would be `CMAX+1`. Pulse
  `period_overflow_event`, set its sticky flag, increment `fault_count`, and
  abandon the partial before candidate completion. If `rise_mask==111`, that
  genuine common rising starts a new partial at `t`; otherwise capture becomes
  idle while remaining armed. A close at elapsed `CMAX` is legal.
- No rise: record each lane's first fall at its actual elapsed count; later
  falls do not rewrite it. Advance age.
- Nonzero proper-subset rise, including an early rise coincident with another
  lane's fall: pulse `incoherent_event`, set its sticky flag, increment
  `fault_count`, and abandon all old lane counts/masks/start. No old lane may
  be spliced into a later frame.
- `rise_mask==111`: a record requires all three `fall_seen` bits and every
  high count strictly inside the interval. A valid close stores one record and
  starts the next partial at this same common rising. An invalid close pulses
  one `incoherent_event` and still starts the next partial. The common rising
  is never rejected merely because the earlier candidate was invalid.

Transitions between samples, analog behavior, synchronizers, pins and physical
frequency are outside this contract. A lane that is constant cannot produce a
rise/fall/rise sequence.

### Witness namespace exhaustion

Processing at `t==TMAX` itself remains legal: a record may close there, or a
partial may start there. On the next ordinary armed edge, with old
`tick==TMAX`, the implementation:

- pulses exactly one `witness_overflow_event`;
- sets `witness_overflow_seen`;
- increments `fault_count` with saturation;
- sets `armed=0`;
- clears the partial; and
- freezes the local tick at `TMAX` without wrapping or manufacturing
  `TMAX+1`.

This happens exactly once even when idle. It is finite representation
namespace exhaustion, not evidence of a missing signal, a physical timeout,
source liveness or a watchdog. Further acquisition requires a new explicit
rearm.

### One transport slot

There is exactly one result slot. On an ordinary edge, an old
`occupied && out_ready` record retires independently of input processing and
even when unarmed. A newly completed candidate may fill an empty slot or
replace an old retiring record. There is no combinational bypass: a candidate
created in an old empty slot is not consumable until a later edge.

Consumption without replacement clears occupancy and all payload fields to
zero. While stalled, every payload field and `out_valid` stay unchanged.
`out_valid` means only transport availability; it grants no freshness,
waveform validity, liveness, motion eligibility or applied-command proof.

If a complete candidate arrives with a full slot and `out_ready=0`, the old
record is preserved whole, only the new candidate is dropped, and one
`overrun_event` is pulsed with `overrun_seen` and a saturating `fault_count`
increment. Other partial faults never replace, relabel or promote the older
queued record. Input sampling does not stall with result transport.

### Fault priority and counting

At most one fault event is emitted per ordinary edge:

```text
witness_overflow > period_overflow > incoherent > overrun
```

All pulse outputs default to zero each edge. `seen` flags stay set until
reset/STOP/rearm. `fault_count` increments once per emitted event and
saturates at `CMAX`; saturation does not suppress later pulses. It counts
fault/drop notifications, not a known number of lost physical PWM frames.
Intentional reset/STOP/rearm clears diagnostics and adds no fault.

## Verification performed

Runner invocation:

```text
python competition/deepeye/tools/control3d/run_pwm_coherent_capture.py \
  --out competition/deepeye/evidence/control3d/pwm-coherent-capture-20261020-14/author/run-author-20261020-14-a
```

The runner refused a pre-existing output directory, snapshotted the RTL, TB,
runner, scope/frozen/decision/consumed inputs and contract documents, and
compiled from the snapshots. It recorded each command, working directory,
actual exit, duration, raw stdout, raw stderr, transcript, and SHA256.

Actual local toolchain:

- `D:/modelsim1/win64/vlib.exe` SHA256
  `128a99858b689f4d535ffdff4a35342ea166a681c201887bb980179680b9b57e`
- `D:/modelsim1/win64/vlog.exe` SHA256
  `6342a4ffe784fadafc15f0e9c25738b421624cf89668f84b114b07b43fc686f6`
- `D:/modelsim1/win64/vsim.exe` SHA256
  `a5fb4747c8c06b1f3ad5b5f9ae6240ab6e28598cdf6058aa6f5139d0732303cf`
- `vlog -version`: `ModelSim SE-64 vlog 10.7 Compiler 2017.12 Dec 7 2017`
- `vsim -version`: `ModelSim SE-64 vsim 10.7 Simulator 2017.12 Dec 7 2017`
- `vlib -version` is unsupported by this installation; it returned exit 1 and
  printed usage. The vlib executable hash is recorded.

Official run manifest SHA256:
`b580d67142750f73396f0e55855fdd8da4a5eb02d1dabe70ded233d01b8f3457`.
Summary SHA256:
`0bb646b44b10dec8d9d29b4c3c5496769f5968b618914167875a9f11fb90cc6e`.
Commands SHA256:
`08e91d13f2727b2550719d3e0a4cbeefcf69aa734c3f1fd88a9e2d88fab01dba`.
Source manifest SHA256:
`2ad8ef29937872d6fba7fcaa4093ef28559fea351aad083003b8731e4f264ceb`.

Aggregate positive results:

- 11 positive runs, 15 distinct groups.
- 628 cases, 170,762 sampled edges, 695,329 assertions, 613 records,
  36 fault events.
- 0 TB mismatches, `TB_PASS` on every positive run.
- 9/9 invalid-parameter tops reached the explicit time-zero fatal diagnostic
  and did not reach `INVALID_CONFIG_GUARD_MISSING`.
- 2/2 isolated mutants failed at public ports.

| Run | Parameters | Groups / cases | Samples | Assertions | Records | Fault events | Mismatches |
|---|---|---:|---:|---:|---:|---:|---:|
| g00 main controls/negatives/queue/priority | C4/W8/T8 | 4 / 24 | 211 | 1,116 | 19 | 16 | 0 |
| g01 exhaustive W2 + saturation | C2/W8/T4 | 2 / 15 | 77 | 454 | 9 | 7 | 0 |
| g02 exhaustive W3 | C3/W8/T5 | 1 / 441 | 4,042 | 24,988 | 441 | 0 | 0 |
| g03 COUNT_W16 boundaries | C16/W32/T16 | 1 / 3 | 163,856 | 655,475 | 3 | 1 | 0 |
| g04 minimum widths / W2 exhaustion | C2/W2/T1 | 1 / 2 | 18 | 88 | 1 | 2 | 0 |
| g05 maximum widths, bounded | C32/W64/T64 | 1 / 3 | 21 | 144 | 3 | 0 | 0 |
| g06 deterministic random schedule | C8/W16/T16 | 1 / 128 | 2,407 | 12,588 | 128 | 0 | 0 |
| g09 small boundaries | C2/W3/T3 | 1 / 5 | 44 | 153 | 3 | 5 | 0 |
| g10 default smoke | defaults | 1 / 1 | 8 | 52 | 1 | 0 | 0 |
| g11 COUNT_W3 period overflow | C3/W8/T4 | 1 / 3 | 40 | 138 | 3 | 2 | 0 |
| g12 WITNESS_W3 exhaustion | C3/W3/T1 | 1 / 3 | 38 | 133 | 2 | 3 | 0 |

The two exhaustive groups cover all legal high triples:
`9 + 441 = 450`, with adequate witness space (`WITNESS_W=8`).

### Required coverage mapping

1. Literal COUNT_W2 example, all 450 legal COUNT_W2/3 high triples, repeated
   coherent intervals, high/low boundaries and exact `CMAX` boundaries:
   g01, g02, g09 and g11. The literal `start1/falls2,3,2/end4 -> period3,
   highs1,2,1` is in g09.
2. Phase-shifted equal periods, unequal end edges, early/extra rises,
   incomplete falls, a constant/missing lane after start, no common start,
   and recovery only on a genuinely common future rising: g00 negatives.
3. Reset/STOP/rearm at start, partial, completion and retirement phases,
   priority combinations, held controls, high baseline, changing/reused/zero/
   full tags and a new interval strictly after rearm: g00 controls and queue
   cases, plus the W3 exhaustion cases.
4. Empty/full slot, long stalls, simultaneous retire/refill, early faults
   with older stalled/retiring data, overrun and saturating fault count,
   witness exhaustion with pending transport: g00 queue/priority, g01 and
   g04/g12.
5. COUNT_W2/3 period overflow, including fresh common rise on overflow;
   WITNESS_W2/3 real namespace exhaustion without wrapping: g09, g11, g04 and
   g12. Coincident count/witness priority is in g09.
6. Fully observed COUNT_W16 periods crossing bit 15 and 65535, overflow at
   65536 with sufficient witness width: g03. COUNT_W32/WITNESS_W64 observations
   are bounded smoke tests only; no full 32/64 traversal is claimed.
7. Independent deterministic three-lane phases, controls, tags and ready:
   g06. Isolated mutants are compiled and run separately; both are rejected at
   public ports, not merely at elaboration.
8. Minimum/maximum supported parameters and explicit invalid guards for zero,
   negative and out-of-range widths: g04, g05, g10 and the nine invalid tops.

### Isolated mutants

Both mutants were generated from the snapshot RTL and compiled in separate
work libraries. The original RTL hash was verified unchanged before and after.

- `relaxed-common-start`: idle common-start acceptance relaxed to any nonzero
  subset. The TB failed at public port with
  `MISMATCH ... label=mutant_relaxed_subset_start.events expected=1 actual=0`.
- `retain-partial-on-subset`: the partial-abort assignment retained the old
  partial. The TB failed at public ports with
  `MISMATCH ... label=mutant_mixed_no_record.valid expected=0 actual=1`
  and `label=mutant_mixed_no_record.period expected=0 actual=3`.

Each mutant run ended `TB_FAIL`; the log is preserved. Under the recorded
ModelSim `-do` script, `vsim` returns process exit 0 after a `$fatal`/`TB_FAIL`
break. Fail-closed status is therefore established by the explicit fatal/
`TB_FAIL` public-port log and the absence of `TB_PASS`, not by the process exit
code. The invalid guards similarly stop at time zero with
`DEEPEYE_COHERENT_INVALID_PARAM` and never reach the TB's guard-missing fatal.

## Limitations and non-claims

- No Vivado is available on this node. Synthesis and implementation are
  **blocked / not run**. The RTL is synthesizable-style candidate code, not a
  synthesis result.
- No physical board operation. The board is A-only; no physical capture,
  TTL, profile, clock, source, pin, HWH, BOOT or motion-authority result is
  claimed.
- No CDC/RDC analysis or result.
- All 29 formal cards are `not_run`.
- Full G05/B06/R03, the system integration, both complete control chains and
  the public ABI/register/HWH/BOOT/TRACE type 7 surface remain outside this
  operation and unaccepted.
- `out_valid` is transport-only. This primitive proves no sampled transition
  correctness beyond the observed schedule, no source liveness, no command
  application, no causal/physical interpretation and no motion eligibility.
- COUNT_W32 and WITNESS_W64 observations are bounded. No full maximum-width
  traversal, internal forcing or seeding is claimed.
- A constant channel cannot produce R/F/R; later profile interpretation is a
  separate gate.
- Local ModelSim evidence is author evidence only. Main's independent oracle,
  review and product acceptance are still required.
