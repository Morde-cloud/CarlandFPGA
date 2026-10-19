# Atomic PWM internal RTL — operation 12

The B main accepts the bounded **digital simulation** of one synchronous,
integer-count, three-channel PWM generator. All channel widths, period and
opaque tag apply together at an old-frame boundary. One pending tuple provides
backpressure; reset/STOP flush it and the active output. A fresh accepted tuple
is required to restart. No semantic movement authority is supplied.

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-ATOMIC-PWM-RTL-20261020-12-v1`, operation
`B-DEEPEYE-PWM-ATOMIC-20261020-12`. Contract
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01-H15, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`;
contract pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, design
`1011259415a0916054eb580687612580bc1e5f09`.

Final RTL SHA256:
`9dc8ecf96e59a2ae8467bda64572f62eb602d52db535733f236f64ff97c43428`.
This differs from the original author RTL only by explicit `synthesis
translate_off/on` exclusion and explanatory comments for the diagnostic guard.
There was no functional RTL correction. No synthesis report exists.

## Independently executed evidence

- `main/run-03/result.json`: ModelSim SE-64 10.7 compile and positive simulations
  exited 0. An independently written absolute-edge interval/deadline oracle
  checked 46,190 sampled edges through public ports. It was frozen before the
  author result and before reading author RTL/model.
- The 2-bit suite covers all 99 legal three-width tuples; 3-bit covers all 1,295.
  These include zero/full duty, period 1 and max-small-period wrap. Adversarial
  schedules cover boundary acceptance versus application, held/busy/invalid
  inputs, STOP/reset overlaps, period changes and tags. Three deterministic
  schedules contribute 18,000 random cycles, not 18,000 independent commands.
- 32-bit cases cover unsigned bit31-set inputs and bounded partial long-period
  observations. They do **not** measure an entire `2^32-1` period.
- `main/run-03/long.stdout.txt`: one complete 2,000,000-interval frame with exact
  high totals 10,000 / 490,000 / 70,000, followed atomically by two period-37
  frames. These raw-count extrema are **not a valid combined motion command**;
  no curvature/profile/clock-rate claim is made.
- Four invalid parameter cases reject with explicit guard markers. ModelSim
  may return process exit 0 after `$fatal`; the runner requires the expected
  fatal content and rejects missing completion markers for positive tests.
- `main/negative_controls.json`: isolated STOP-ignored and pitch-from-yaw
  mutants are both rejected by public-port mismatches. The accepted RTL bytes
  were unchanged. Deliberately faulty copies are test evidence only.
- `main/author-rerun-01/`: the main reran the existing author suite against the
  final RTL: 9 groups passed, 90,644,277 check invocations, four explicit guard
  rejections. This rerun is distinct from the independent oracle and is not
  presented as millions of independent cases.

`main/author_audit.json` verifies all 85 entries in the original local author
manifest plus all 86 SHA256SUMS entries. Compiled ModelSim libraries and
scratch directories remain local; the release manifest enumerates the actual
published source, logs, snapshots and receipts. Raw `.log`/`transcript` bytes
are also provided as `.txt` copies where selected; original private compiler
artifacts are not implied to be available in the PR.

## Preserved failures and provenance

Author runs `-a/-b/-c` retain runner parsing failures concerning CRLF, the
ModelSim `#` prefix, and directed versus random replay counts; `-d` is the
author's passing run. Main `run-01` reached the success marker but its Tcl
`onbreak` policy incorrectly returned 1 for normal `$finish`. Main `run-02`
passed behaviorally with Windows CRLF vector files. Final `run-03` writes the
original frozen LF vector bytes exactly; all three vector hashes match
`main/oracle_frozen.json`, and all three port logs match run-02 byte for byte.
Original files and failed records have not been overwritten.

The coordinator's CONTINUE was actually returned through the original
`main_wait` message. Its nonblocking assertion that frozen G05 lacked atomic
wording is corrected by exact Git line 464 in
`main/inputs/G05_SOURCE_CLARIFICATION.json`; this changes no behavior or public
authority. Queue/tag/handshake details remain B internal candidate choices.

## Reproduce from repository root with available ModelSim

Use explicit paths and a fresh output directory beneath the owned main folder:

```text
python -B competition/deepeye/tools/control3d/main_verify_atomic_pwm.py --rtl competition/deepeye/fpga/control3d/deepeye_atomic_pwm.sv --tb competition/deepeye/tests/rtl/control3d/main_tb_atomic_pwm.sv --tool <ModelSim-bin-directory> --owned-root competition/deepeye/evidence/control3d/pwm-atomic-20261020-12/main --out competition/deepeye/evidence/control3d/pwm-atomic-20261020-12/main/<fresh-name> --long
```

Each run preserves commands, raw stdout/stderr, exit codes, input snapshots,
port traces and SHA256. `run-03/runner.py` is the exact executed main runner.
The author command and exact tools are in `main/author-rerun-01/command_catalog.json`.

## Remaining gates

Synthesis and implementation are **blocked** by missing local Vivado; coding
style review is not a synthesis result. CDC/RDC, physical pin output/capture,
clock accuracy, timing closure, HWH/register integration, BOOT/source/profile,
curvature/TTL/authority, R03, complete G05/B06, both system control chains and
all 29 formal cards remain unaccepted/not_run. STOP is synchronous: no stopped
clock or asynchronous emergency-stop guarantee exists. Only A operates the
physical board. Full H01-H15 3D/UI, hidden truth, causal observations and PC AI
requirements remain mandatory.
