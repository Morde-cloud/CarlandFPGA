# Synchronous single-channel raw PWM edge-measure candidate

Status: author-local candidate implementation and bounded ModelSim digital
evidence. This is not main acceptance, product acceptance, synthesis evidence,
CDC/RDC evidence, a public interface, or a board result. The sole product main
must review it independently.

## Identity and frozen authority

- Product operation: `B-DEEPEYE-PWM-EDGE-MEASURE-20261020-13`
- Execution work: `B-PWM-EDGE-MEASURE-RTL-20261020-13-v1`
- Task: `DEEPEYE-IMPLEMENTATION-20261014/v1`
- Sole product director: `01a13b55-095b-7461-8dd5-5476a130bd82`
- Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01-H15
- Contract pin: `f5989cd5defce561f9ba98e6b18fc2682945f0a2`
- Canonical requirements SHA256:
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`
- Frozen design: `1011259415a0916054eb580687612580bc1e5f09`
- Normative scope SHA256:
  `cc7960d77300fcd46a2b8e6e5e0aca1adafc99842d172934ab77ca8d593b3a90`
- Frozen-scope receipt SHA256:
  `7cef6c82254b97c776ff3e6646f4cc19cecef2c1ed4c660395204cd7a8e8ade5`
- Coordinator CONTINUE decision SHA256:
  `1d527d7069a4f5a3041296f709ad58ba913d9066f8b64032acf57b9b58afd283`
- Main consumed-readback receipt SHA256:
  `21f10e999c585d54441517be2d4f9dcccdbde6f3304493c096abcb511dc0175e`
- Baseline product worktree:
  `f7e95af8f8abae6d4a5312c08d99e095a7e5dec1`

The canonical requirements hash above was recomputed from the pinned commit's
JSON `requirements` array with `ensure_ascii=False`, `sort_keys=True`,
`separators=(',', ':')`, then UTF-8 encoding. It matched the fixed expected
value and all 15 IDs H01-H15 were read.

This primitive does not weaken H01-H15. The full 3D/UI application, hollow
edge-only cube, solid-volume collisions, free camera and editable/random
layouts, free entry/exit faces, equal blue/red gates and complete passage,
hidden obstacle truth, device-bounded causal observations, online 3D decisions,
substantive PC AI, and both PC_DIRECT and FPGA-output control chains remain
required at the product level. This module supplies only an input-ready raw
single-channel integer measurement primitive.

## Interface

```systemverilog
module deepeye_pwm_edge_measure #(
    parameter integer COUNT_W = 32,  // supported 2..32
    parameter integer TAG_W   = 32   // supported 1..64
) (
    input  logic               clk,
    input  logic               rst,
    input  logic               stop,
    input  logic               rearm,
    input  logic               sample_level,
    input  logic [TAG_W-1:0]   window_tag,
    input  logic               out_ready,
    output logic               armed,
    output logic               out_valid,
    output logic [COUNT_W-1:0] out_period,
    output logic [COUNT_W-1:0] out_high,
    output logic [TAG_W-1:0]   out_tag,
    output logic               overflow_event,
    output logic               overrun_event,
    output logic               overflow_seen,
    output logic               overrun_seen,
    output logic [COUNT_W-1:0] loss_count
);
```

Every input is a binary synchronous input sampled on a rising `clk` edge. No
synchronizer, asynchronous pin, analog waveform, CDC transfer, clock-frequency
decision, or physical timeout is supplied. Signal transitions between sampled
edges are outside this primitive's evidence.

`MAX` is the unsigned value `(2**COUNT_W)-1`. `out_valid` is the registered
result-slot occupancy qualified by `!rst && !stop && !rearm`. It means only
that one old raw record is queued for transport. It does not assert source
liveness, freshness, capture eligibility, sensor validity, or motion authority.

## Sampled behavior

### Reset, STOP, rearm priority

`rst || stop` has highest priority on a sampled edge. It deasserts `armed`,
flushes every partial and the result slot, zeros payloads, tags, diagnostics,
loss count and pulses, and prevents `out_valid` from presenting a record on that
edge. Deassertion alone does not arm the primitive.

`rearm` has next priority. It asserts `armed`, latches `window_tag`, snapshots
`sample_level` as the new previous level, and flushes all old partials, the old
result record, diagnostics and counters. The rearm edge is only a baseline; it
cannot be a rising or falling event for the new window. A high level at rearm
must first become low and then be followed by a fresh rising sample. Held rearm
rebases every edge and produces no result or loss event. Tag changes without
rearm have no effect; zero is a legal opaque tag.

### R0/F0/R1 count convention

On an ordinary armed sampled edge:

```text
rising  = !previous_sample && sample_level
falling =  previous_sample && !sample_level
```

The primitive waits for fresh rising `R0`, then first falling `F0`, then next
rising `R1`. It emits:

```text
high   = index(F0) - index(R0)
period = index(R1) - index(R0)
valid candidate condition: 1 <= high < period <= MAX
```

`R0` establishes age0. A falling on the immediately following edge yields high1.
An immediately following next rising yields period2 therefore. The successful
`R1` starts the next measurement at age0 even if backpressure dropped its
completed candidate.

### MAX and overflow

At an ordinary edge where the pre-update age equals `MAX`, the next elapsed
interval would be `MAX+1`. This check precedes candidate completion:

- `R1` at age `MAX` is valid with period `MAX`.
- `R1` at age `MAX+1` is invalid and never wraps into a record.
- The out-of-bound partial is abandoned, one `overflow_event` pulses,
  `overflow_seen` becomes sticky, and saturating `loss_count` increments once.
- If that overflowing edge is itself a fresh rising, it becomes the next R0.
- Otherwise the state waits for a later fresh rising while preserving the
  actual sampled previous level.

Constant high after a started R0 overflows once and then waits for low/fresh-rise.
Constant low after F0 overflows once and then waits for fresh-rise. Constant low
or high from rearm with no fresh R0 produces neither record nor overflow. This
is not an absence-of-signal watchdog.

### One-record result slot

There is exactly one result slot.

- A handshake occurs when `out_valid && out_ready` on an ordinary edge.
- A candidate completed on that same edge may replace a consumed old record.
- A new record is never visible for consumption on its creation edge.
- Consuming with no candidate clears valid and all payload registers.
- If the old slot is occupied and `out_ready=0` when a candidate completes, the
  entire old period/high/tag record remains stable; only the new candidate is
  dropped. `overrun_event` pulses, `overrun_seen` becomes sticky, and saturating
  `loss_count` increments once.
- Measurement input continues independently of output readiness.
- Overflow neither fabricates nor relabels a result and does not revoke a
  correctly completed older record already in the slot.
- Reset, STOP or rearm explicitly flush a pending record without counting that
  intentional discard as loss and without restoring old-window diagnostics.

`overflow_event` and `overrun_event` are one-edge pulses, default zero on each
ordinary edge, and are mutually exclusive. Sticky flags and pulses remain
visible after saturation; no hidden overwrite or counter wrap exists.

## Invalid parameters

Supported ranges are `COUNT_W=2..32` and `TAG_W=1..64`. Unsupported combinations
produce a time-zero simulation fatal with this exact marker:

```text
PWM_EDGE_UNSUPPORTED_PARAMETERS COUNT_W=<value> TAG_W=<value>
```

The generate/initial guard is enclosed by `synthesis translate_off/on`. It
creates no synthesized hardware initial state, latch, or multiple driver.

## Verification environment

Observed tool:

- `vlog`: `D:\modelsim1\win64\vlog.exe`, Model Technology ModelSim SE-64 vlog
  10.7 Compiler 2017.12 Dec 7 2017
- `vsim`: `D:\modelsim1\win64\vsim.exe`, Model Technology ModelSim SE-64 vsim
  10.7 Simulator 2017.12 Dec 7 2017
- Binary SHA256: vlog
  `6342a4ffe784fadafc15f0e9c25738b421624cf89668f84b114b07b43fc686f6`;
  vsim `a5fb4747c8c06b1f3ad5b5f9ae6240ab6e28598cdf6058aa6f5139d0732303cf`;
  vlib `128a99858b689f4d535ffdff4a35342ea166a681c201887bb980179680b9b57e`.
- `vlib -version` exits 1 with usage in this installation. The runner records
  that raw result and does not mistake it for a compile failure.

The testbench drives only public synchronous ports. It uses no `force`, no
hierarchical signal override, and no internal counter/state as an oracle. A
separately coded event-index and one-record-queue reference model consumes the
same sampled inputs and is checked on every sampled edge. Directed checks also
assert exact record fields, event timing, stability, and count boundaries. An
external deterministic LFSR schedule uses `+SEED=20261020`.

The runner refuses any existing output directory, snapshots source bytes before
execution, records each argv/cwd/start time/duration/exit code and raw
stdout/stderr, rejects compile or simulation errors, unexpected warnings,
missing `TB_PASS`/`TB_STATS`, and any `MISMATCH`, requires exact time-zero guard
markers and `Errors: 1, Warnings: 0` for each invalid case, and checks the
original RTL bytes are unchanged after the isolated mutant run.

Exact reproduction command used for the successful run:

```powershell
& 'D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe' -X utf8 `
  'competition/deepeye/tools/control3d/run_pwm_edge_measure.py' `
  --output 'competition/deepeye/evidence/control3d/pwm-edge-measure-20261020-13/author/run-author-20261020-13-b'
```

The runner requires the output not to exist. Repetition must use a fresh
`run-author-*` directory below the owned `author/` evidence root; it must never
overwrite the retained failure or successful run.

## Fresh successful run

Run directory:
`competition/deepeye/evidence/control3d/pwm-edge-measure-20261020-13/author/run-author-20261020-13-b/`

Result: `status=passed`; 7/7 positive configurations passed, 4/4 invalid
configurations were rejected at time zero, and the isolated mutant was rejected.
Runner exit code was 0.

| Config | Groups | Cases | Cycles | Cycle assertions | Records checked | Random cycles |
|---|---:|---:|---:|---:|---:|---:|
| `w2_t1` | 15 | 3 | 20,542 | 226,428 | 62 | 20,000 |
| `w2_t64` smoke | 14 | 3 | 5,482 | 60,621 | 59 | 5,000 |
| `w3_t3` | 15 | 21 | 21,288 | 235,000 | 134 | 20,000 |
| `w4_t32` | 15 | 105 | 26,208 | 289,756 | 470 | 20,000 |
| `w16_t64` | 12 | 0 | 551,987 | 6,072,405 | 47 | 20,000 |
| `w32_t1` smoke | 12 | 0 | 6,473 | 71,664 | 42 | 5,000 |
| `w32_t64` | 12 | 0 | 418,732 | 4,606,585 | 44 | 20,000 |

Aggregate positive-suite totals:

```text
groups=95
cases=132
sampled cycles=1,050,712
per-cycle assertions=11,562,459
directed checks=2,615
records checked=858
records generated=18,333
handshakes=18,298
overflow events=2,625
overrun events=106
deterministic random cycles=110,000
mismatches=0
```

Coverage includes reset/unarmed behavior, all rearm phases, held rearm, tag
latching and flush, STOP/reset/rearm at partial stages and result retirement,
empty/full slot, long backpressure, same-edge consume/refill, consume without a
new candidate, flush discard, constant levels, overflow with ready/stalled old
records, pending-record preservation, overrun/recovery, loss saturation, exact
MAX period, MAX+1 overflow, high/low over-bound partials, and an overflow-edge
fresh rising reused as the next R0.

`COUNT_W=2` exhausts all 3 legal representable period/high pairs. `COUNT_W=3`
exhausts all 21 legal pairs. `COUNT_W=4` exhausts all 105 legal pairs. These are
full representable-pair observations, not generator round trips.

The `COUNT_W=16` run fully observed period `65535` with high values `1` and
`65534`, and observed overflow at elapsed `65536` after old age `65535`. It also
crossed bit15 with periods 32768 and 40000. The `COUNT_W=32` run is deliberately
bounded: it observed periods 32768, 65536, 100000 and 200000. It did not observe
the full `2**32-1` period or a 32-bit count overflow. The 32-bit unsigned width
and no-wrap boundary are structural reasoning, not executed evidence.

Full-width 64-bit tags were exercised in `w2_t64`, `w16_t64`, and `w32_t64`.
Zero tags are legal. `TAG_W=1` minimum and `TAG_W=64` maximum were run.

Invalid configurations:

- `COUNT_W=1, TAG_W=32`: expected guard marker at time 0 ps, rejected.
- `COUNT_W=33, TAG_W=32`: expected guard marker at time 0 ps, rejected.
- `COUNT_W=3, TAG_W=0`: expected guard marker at time 0 ps, rejected.
- `COUNT_W=3, TAG_W=65`: expected guard marker at time 0 ps, rejected.

Each invalid stdout has exactly one expected `** Fatal`, `Time: 0 ps`, and
`Errors: 1, Warnings: 0`; stderr is empty. No TB pass/fail or mismatch marker is
present.

## Mutant control

The runner copied accepted RTL bytes and changed exactly one occurrence:

```text
- slot_period_q <= age_q + 1'b1;
+ slot_period_q <= age_q + 2'd2;
```

The faulty copy is retained as
`mutant/deepeye_pwm_edge_measure_mutant.sv`, SHA256
`c2f6ed0d9e1a85a984ddf24136a71ef6fd5152fb3398a8bd2c39e02fe24a08bf`.
Public-port evidence rejected it with 1,308 mismatches and `TB_FAIL`. The
original RTL SHA256 was identical before and after:
`f285268a83e5853f760c69255ab50af623116493a889637c3186cbd2f9da2187`.

## Accepted source and result hashes

- RTL `deepeye_pwm_edge_measure.sv`: `f285268a83e5853f760c69255ab50af623116493a889637c3186cbd2f9da2187`
- Testbench `tb_pwm_edge_measure.sv`: `d15c25d34707277841074b58da4f54ae2f22f4441573c55282937d9efbb3499f`
- Runner `run_pwm_edge_measure.py`: `17ae98f734badb1cc0a2af649de353a94df9fd50bfdc5a96c1536bd7dd9080e6`
- `result.json`: `e739497e2941b452a2e56f215fb208a5b9db987b7e66fc43a0c0af3b8618d951`
- `manifest.json`: `5341fc92cc6f2912b1d1e27ada52df8b98d7f64741c72781ceeda9e9bee2144b`
- `SHA256SUMS.txt`: `12d26f0dc682ea62bd7ccaf706ae729351a07dabe99d14efff7f0073dc143b35`
- `inputs.json`: `e768d6c3ea0e0214c25b863e9fbd63c32c7cc9c9e9f4e2c2734cafc06dd8f4d8`
- `LOCAL_RETENTION.json`: `456a200c71a170f6da29c97655e2599c738a74dca3ef9ab9b257d4b038508d6b`

The manifest publishes 85 files and separately lists 64 retained generated
ModelSim library/scratch records. Every published SHA256SUMS entry was
recomputed successfully. The top-level `transcript` is ModelSim's default
last-run transcript (the mutant run); per-command `logs/*.stdout.txt` and
`logs/*.stderr.txt` are the authoritative raw command logs.

Key raw log hashes:

| Log | SHA256 |
|---|---|
| `logs/vlog_compile.stdout.txt` | `81331e7659b93a8916fa1c12ad9e22197be4f486a0abce9266c007be4dc2c4b1` |
| `logs/w2_t1.runlog.txt` | `55b248004958746bbd0a617074ae0d8a1a1c256c32f4f9422217769e74d66ece` |
| `logs/w2_t64.runlog.txt` | `02248e9c53ab34d1972a8e09b035da87ff5ab044b54849a83a0fdc5a6fe14be3` |
| `logs/w3_t3.runlog.txt` | `cab2a6d1bf1a2531ee6ecddfc5e9437ddb19ef58cf264ce9ac22a473c432e1b6` |
| `logs/w4_t32.runlog.txt` | `166a5529817ad77a53048c4fe8f59e7c976c2fccf427f0ec69f666a027444083` |
| `logs/w16_t64.runlog.txt` | `016e335c92637de485c477744530299a9797e8ab725a49ff28f8c516f6ed476a` |
| `logs/w32_t1.runlog.txt` | `5264f2cf38388ae5d9d692efc7cae02839ae6e1464fb709ba6c07377d8d0c6b2` |
| `logs/w32_t64.runlog.txt` | `6558e27bc98d7699b12cf8595483e495b5a09fbb3d439aff55b1531397c869e6` |
| `logs/invalid_w3_t0.stdout.txt` | `745899ab1c9092c1855e899ff8459760533871146baf485db8904bcf4563c23f` |
| `logs/mutant_w3_t3.stdout.txt` | `6b6b11a382ed724da9721612838a266056a89029115c19e5491c8cc4c3d3f56c` |

All positive and invalid stderr logs are zero bytes with SHA256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## Preserved failed development run

`author/run-author-20261020-13-a/` is retained unchanged as failure evidence:

- `status=failed`; positives 4/7, invalid guards 3/4, mutant rejected.
- The three `TAG_W=64` positives were rejected because old testbench line 1481
  used an out-of-range part-select into the 32-bit LFSR (`vopt-2697` warning).
- `COUNT_W=3, TAG_W=0` could not reach the parameter guard because old zero
  replication failed elaboration (`vopt-8602`).
- `COUNT_W=3, TAG_W=65` also inherited the part-select warning.
- Run failure hashes: `result.json`
  `2fc466be196f5ec8550f36d5327319c608aee55704b3fe5ab0b877936ed18add`;
  `manifest.json`
  `2fa1209ef2fa4c2d3cc19b5c10f6e8ae679417a2b065744de8ed645b69db02f2`.

The defects were fixed by width-safe literals and a width-safe tag assignment,
then the complete suite was rerun in the fresh passing directory. The failure
directory was not overwritten.

## Limits and non-claims

- No Vivado was invoked. Synthesis, implementation, bitstream, resource, DRC,
  constrained timing, and post-implementation timing are blocked/not run.
- No physical board operation occurred. The board remains A-only.
- No CDC/RDC analysis or asynchronous sampling guarantee is supplied.
- No three-channel same-period capture, source/session/request/control epoch,
  timestamp ordering, freshness, liveness, TTL, profile decoding, curvature,
  motion eligibility, or applied-command binding is supplied.
- No public register/pin/clock-frequency/HWH/BOOT/TRACE ABI is defined.
- `COUNT_W=32` full maximum period and 32-bit overflow were not actually run.
- Both PC_DIRECT and FPGA-output product control chains remain outside this
  primitive and unaccepted here.
- G05/B06/R03 and all 29 formal acceptance cards remain not run/unaccepted.
- Main independent oracle/testbench/evidence review is pending. This document
  does not claim product acceptance or terminal operation completion.

