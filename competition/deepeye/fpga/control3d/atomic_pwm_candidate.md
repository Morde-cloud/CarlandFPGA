# Internal atomic three-channel PWM candidate

## Status and provenance

This directory contains one bounded internal synchronous count-generation
primitive, `deepeye_atomic_pwm`. The B main independently verified its internal
digital behavior after adding explicit synthesis exclusion around the diagnostic
parameter guard. It remains an internal candidate, not a public interface or a
board result. See the [main review](../../evidence/control3d/pwm-atomic-20261020-12/README.md).

| Field | Value |
|---|---|
| Task | `DEEPEYE-IMPLEMENTATION-20261014/v1` |
| Work | `B-ATOMIC-PWM-RTL-20261020-12-v1` |
| Product operation | `B-DEEPEYE-PWM-ATOMIC-20261020-12` |
| Contract | `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01-H15 |
| Requirements SHA256 | `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804` |
| Contract pin | `f5989cd5defce561f9ba98e6b18fc2682945f0a2` |
| Frozen design | `1011259415a0916054eb580687612580bc1e5f09` |
| Normative scope SHA256 | `04851894139aebc6c6c0a740d9e1d8d6a732333da98f7da3f6a2ed635c3bb87c` |
| Frozen scope JSON SHA256 | `7d23a7a1023379bed18b81b794ab4cfaf364d7e1652511a3f382bdce2ec6d95c` |
| Coordinator decision SHA256 | `75b72a4279e36b7f9ff29ae9fa4738e6aa238665cb735ee82296e6c81d86e288` |

Frozen taskbook line 464 requires atomic three-channel frame-boundary updates.
The queue, interface and old-state scheduling rules here are B internal design
choices for this bounded increment; they do not freeze a public ABI. The exact
source clarification and original scope-review decision remain preserved.

The increment implements only three registered PWM outputs and their internal
configuration queue. It defines no register address, pin, clock frequency,
public ABI, capture engine, mailbox, motion mapping, stop authority, CDC/RDC
contract, synthesis result or physical-board result.

## Parameters and interface

`COUNT_W` defaults to 32 and supports 2 through 32. `TAG_W` defaults to 32 and
supports 1 through 64. Out-of-range combinations are rejected by a
simulation-only elaboration guard. All signals are synchronous to the rising
edge of `clk`; `rst` and `stop` are synchronous active-high controls.

| Signal | Direction | Width | Meaning |
|---|---|---|---|
| `clk` | input | 1 | Sampling/generation clock |
| `rst` | input | 1 | Synchronous flush, highest priority |
| `stop` | input | 1 | Synchronous flush, highest priority |
| `cfg_valid` | input | 1 | Request qualifier for one complete tuple |
| `cfg_ready` | output | 1 | `!rst && !stop && !pending` |
| `cfg_period` | input | `COUNT_W` | Unsigned frame period |
| `cfg_high_yaw` | input | `COUNT_W` | Unsigned yaw high interval |
| `cfg_high_pitch` | input | `COUNT_W` | Unsigned pitch high interval |
| `cfg_high_speed` | input | `COUNT_W` | Unsigned speed high interval |
| `cfg_tag` | input | `TAG_W` | Atomic request tag |
| `accepted` | output | 1 | Registered legal-transfer pulse |
| `rejected` | output | 1 | Registered invalid-transfer pulse |
| `applied` | output | 1 | Registered pending-to-active pulse |
| `frame_start` | output | 1 | Registered frame boundary pulse |
| `running` | output | 1 | A valid tuple is active |
| `pending` | output | 1 | One complete replacement tuple is queued |
| `pwm` | output | 3 | Registered levels; bit 0 yaw, bit 1 pitch, bit 2 speed |
| `active_period` | output | `COUNT_W` | Active frame period |
| `active_high_yaw` | output | `COUNT_W` | Active yaw high count |
| `active_high_pitch` | output | `COUNT_W` | Active pitch high count |
| `active_high_speed` | output | `COUNT_W` | Active speed high count |
| `active_tag` | output | `TAG_W` | Active request tag |

Output pulses describe the edge just sampled and remain asserted for one
visible cycle. Adjacent events may therefore appear high on adjacent cycles.

## Behavior

1. `rst` or `stop` on an edge overrides every handshake, pending application,
   frame boundary and invalid request. It clears `running`, `pending`, all
   active and pending metadata, the phase and all registered pulses, and forces
   `pwm` to zero. Deassertion alone does not resume old output; a fresh legal
   tuple is required.
2. `cfg_ready` is high exactly when `!rst && !stop && !pending`. It does not
   depend on `cfg_valid` or payload values.
3. A transfer exists only when `cfg_valid && cfg_ready` on an edge. It is legal
   when `cfg_period >= 1` and every unsigned high count is at most
   `cfg_period`. A legal request snapshots period, all three high counts and tag
   together and pulses `accepted`. An illegal request pulses `rejected` and
   mutates neither active nor pending state. A held request while not ready has
   no effect and is not rejected.
4. A pre-existing pending tuple applies when idle or when
   `phase + 1 == active_period` at an ordinary edge. Application atomically
   copies the entire tuple, clears pending, sets phase to zero, sets `running`,
   pulses `applied` and `frame_start`, and drives each PWM bit from its new
   `high != 0` value.
5. An applying edge cannot accept a replacement because its pending pre-state
   forces `cfg_ready` low. There is no same-edge bypass; the intentional
   one-edge backpressure bubble removes replacement overwrite ambiguity.
6. If idle with no old pending tuple, a newly accepted request only queues.
   Outputs remain low until the following edge applies it. While running, a
   request accepted at a normal frame boundary begins another complete old
   frame and applies at the following boundary.
7. On a start/applied edge phase is zero. Ordinary edges advance the phase
   until `period - 1`; the next edge starts another frame. Each channel is high
   for exactly its first `high` intervals of the frame. Counts zero and period
   are legal endpoints. `period == 1` creates a frame boundary every edge.
8. Registered PWM comparison uses the next phase interval. The counter is not
   advanced or compared against `period - 1` while idle. There is no public
   internal-counter force, and no count frequency is assumed.
9. Unsupported parameter elaborations execute a simulation-only `$fatal` at
   time zero. The guard is absent for supported parameters; it creates no
   hardware initial state, delay, latch or multiple driver.

## Reproduction

The final author run used:

```text
Python: D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8
vlib:   D:/modelsim1/win64/vlib.exe
vlog:   D:/modelsim1/win64/vlog.exe
vsim:   D:/modelsim1/win64/vsim.exe
seed:   123456789
```

Run the explicit-path, fail-closed runner with a new `--output` beneath the
owned evidence directory:

```powershell
& D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 `
  competition/deepeye/tools/control3d/run_atomic_pwm.py `
  --owned-root competition/deepeye/evidence/control3d/pwm-atomic-20261020-12/author `
  --output competition/deepeye/evidence/control3d/pwm-atomic-20261020-12/author/<fresh-name> `
  --rtl competition/deepeye/fpga/control3d/deepeye_atomic_pwm.sv `
  --testbench competition/deepeye/tests/rtl/control3d/tb_atomic_pwm.sv `
  --vlib D:/modelsim1/win64/vlib.exe `
  --vlog D:/modelsim1/win64/vlog.exe `
  --vsim D:/modelsim1/win64/vsim.exe `
  --seed 123456789
```

The runner rejects an existing output, aliased inputs, paths outside the
declared owned root, tool/source failures, missing markers, nonzero errors or
warnings, malformed replay evidence and incomplete parameter guards. ModelSim
10.7 can return process exit code 0 after `$fatal`, so parameter-guard
acceptance checks the explicit time-zero marker instead of trusting that code.

## Original author evidence (before main diagnostic-guard exclusion)

Final passing run:

`competition/deepeye/evidence/control3d/pwm-atomic-20261020-12/author/run-author-20261020-12-d/`

| Artifact | SHA256 |
|---|---|
| Original RTL snapshot `main/author_final/deepeye_atomic_pwm.sv` | `c7af3a96554d927e724e7cf2e41c460affe4e551eae4cb2bf41134335cd498d7` |
| Testbench `tb_atomic_pwm.sv` | `fb54036dfa496fab1bde085234708897798e68c2b526a39b95f0f7e0882d12c9` |
| Runner `run_atomic_pwm.py` | `864e7bb6a471db36534757f938697bc28601ba867582a0506855f0123485f4b5` |
| Replay `replay_events.log` | `8f1ca2c0b5d5b01a0b69ecf609da263c780e32449558aeb1aebd58127510cdfc` |
| Evidence manifest | `9dc0dbd1e46d2d11045a21a2562ba2ece9a86b9f44d8a8db85bc50fae9bcca74` |

ModelSim SE-64 reported `vlog 10.7` and `vsim 10.7`. `vlib -version` is not a
supported version query in this installation and returns usage; the runner
therefore records the `vlib` binary hash and exercises the actual compile.

The main simulation completed with:

```text
cases=9 pass=9 fail=0 checks=90644277
default_frames=491 w2_frames=5739 tag64_frames=491
accepted=409 rejected=74 applied=401 aborted=140
boundary=8 invalid=8 held=3 overlaps=7 period=2 tag=3 bypass=1
w2=99 tag64=4 highbit=2 long=2000000 random=12000 busy=11584
```

The replay stores 12,000 random STEP vectors between explicit begin/end
markers, plus six directed reset vectors. The four invalid parameter cases
`(COUNT_W,TAG_W) = (1,32), (33,32), (32,0), (32,65)` each reported
`ATOMIC_PWM_UNSUPPORTED_PARAMETERS` at time zero. Raw stdout, stderr, exit
codes, command records, tool hashes, source snapshots and a top-level
`SHA256SUMS.txt` are in the passing run directory.

Fail-closed CLI probes are recorded in
`competition/deepeye/evidence/control3d/pwm-atomic-20261020-12/author/runner_negative_controls-1.txt`.
Preserved earlier author-run failures exercised only harness assumptions:
CRLF-tolerant summary parsing, ModelSim's `#` prefix on the clean errors line,
and distinguishing 12,000 random replay vectors from the six directed vectors.
Each was corrected in the runner and rerun under a new directory; no failed
directory was overwritten.

## Limits

- The original results above are author simulation. The separate main review
  accepts only the internal digital simulation behavior of the final bytes.
- All 29 formal cards remain `not_run`.
- No Vivado run, synthesis, implementation, timing closure, utilization, CDC/RDC,
  on-board execution, measurement or physical loopback was performed.
- Physical-board operation remains A-only.
- The 32-bit high-bit counts are bounded public-port observations; they do not
  claim a full `2^32`-period test.
- The 2,000,000-tick frame is a simulation case, not a clock-frequency,
  scheduling, product timing or hardware guarantee.
- Nothing here grants a public register, pin, capture, motion or stop authority.
