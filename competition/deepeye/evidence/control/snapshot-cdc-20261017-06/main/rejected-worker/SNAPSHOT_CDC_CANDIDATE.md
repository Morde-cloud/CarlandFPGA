# SNAPSHOT_CDC_CANDIDATE - B bounded snapshot CDC candidate 06

- Work `B-SNAPSHOT-CDC-CANDIDATE-20261017-06-v1`; task `DEEPEYE-IMPLEMENTATION-20261014/v1`.
- Parent spec (exact, read before implementation): `main-candidate-spec.md` SHA256
  `7cf01d1c5428b6173a01f7b58d8168165e38349712b2d763db335c6f1509009f` (verified equal).
- Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01-H15, pinned at commit
  `f5989cd5defce561f9ba98e6b18fc2682945f0a2`; canonical requirements array SHA256
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804` (recomputed equal
  from the pinned JSON in this work, `ensure_ascii=False, sort_keys=True, separators=(',',':')`).
- Frozen design `1011259415a0916054eb580687612580bc1e5f09`. B product input HEAD
  `860f6f850b19afe8240ea49f66c0acbd879c1ff7`. No existing file or module is changed.
- Only A dependency `66aa291d7f01cc3cfefb8c30c4e8ad3aec6547bd`; the public ABI/register map is
  A-owned. This candidate defines no register address/bit field, no motion authorization, no
  source identity, no timeout, no clock-liveness promise, no physical I/O and no board enable,
  and infers no final A-side fields.
- A alone operates the physical board. Everything here is digital simulation evidence only.

## H01-H15 carry (no weakening)

All fifteen requirements were read from the pinned contract and are carried unmodified; this
generic transport fixture adds no product behavior and removes, weakens or re-classifies none.
A verbatim machine-checkable carry is published with the worker evidence as
`h-contract-requirements-canonical.json`, a byte stream that hashes to the fixed expected
requirements SHA256 above, so a reviewer can recompute the value independently. The labels
below are short references only; the binding text is the canonical requirements array.

| ID | reference label (binding text is the canonical array) |
| --- | --- |
| H01 | Game-grade operable 3D application: modeling, rendering, UI interaction |
| H02 | Hollow transparent center cube, edge frame only, 3D volume space kept |
| H03 | Solid drill bit and obstacles with visual models and real volume collision |
| H04 | Interactive free camera usable at run and pause |
| H05 | Free and random placement, editable position/direction/size, water and hard rock kept |
| H06 | Free entry/exit face and in-face position choice, explicit infeasibility feedback |
| H07 | Equal-size blue entry / red exit rings, full-volume passage required |
| H08 | Layout hidden from FPGA and PC algorithms; only causal stepwise observation |
| H09 | Causal sensing grounded in real sensor/drilling references; no truth coordinates |
| H10 | Online 3D joint decision-making with the board in the loop |
| H11 | Substantive PC AI decision responsibility, not decoration |
| H12 | Both PC-direct and PC-to-FPGA via-board control paths kept and evidenced |
| H13 | All of the above are final acceptance items; no schedule/budget/compute weakening |
| H14 | Cross-machine/session carry with fixed versions and hashes; no AI may amend |
| H15 | Only a new explicit human instruction may change the contract; report real blockers |

Identity and acceptance-card coverage checks are not product acceptance; nothing in this
document accepts, satisfies or reopens any H item.

## Module contract (as implemented)

`deepeye_snapshot_mailbox.sv` is a synthesizable SystemVerilog module, `WIDTH` integer default
256, legal range 1..1024.

- Ports: `src_clk, src_reset_n, src_valid, src_ready, src_data[WIDTH-1:0], src_online,
  dst_clk, dst_reset_n, dst_valid, dst_ready, dst_data[WIDTH-1:0], dst_online`. No other clock
  domains, no unbounded storage, no vendor simulation dependency.
- One outstanding snapshot maximum. The source accepts only on a source rising edge with
  `src_valid && src_ready`; it captures the entire opaque bus into `data_hold` and toggles
  `req`. Held data cannot be overwritten until the matching acknowledgement returns.
- The destination synchronizes `req` through two flops, captures `data_hold` on a later
  destination edge when the synchronized request differs from local `ack` while no output is
  pending, then asserts `dst_valid`. Capture and consumption occur on separate destination
  edges.
- Consumption is exactly `dst_valid && dst_ready` on a destination rising edge; `ack` moves to
  the pending synchronized request value and `dst_valid` drops. `ack` passes through two source
  flops; `src_ready = armed && (req == ack_sync[1])`.
- Stall stability: while `dst_valid && !dst_ready`, `dst_valid` and `dst_data` are stable; the
  testbench re-checks this on every destination edge in every case. After consumption
  `dst_data` may retain its last value with `dst_valid = 0`.
- Handshake synchronizer flops carry `(* ASYNC_REG = "TRUE" *)`: `src_rst_sync`, `dst_up_sync`,
  `ack_sync`, `dst_rst_sync`, `src_up_sync`, `req_sync`. The multi-bit held bus is deliberately
  NOT per-bit synchronized (bundled data; see Physical integration gate).

## Reset: asynchronous shared flush, local synchronous release, rearm

- Both reset inputs are one shared flush network: `common_reset_n = src_reset_n & dst_reset_n`.
  Either input low asynchronously clears both halves - synchronizers, `up`, `req`, `ack`,
  `armed`, `data_hold`, `dst_valid` and `dst_data` - including when either or both clocks are
  stopped, because every sequential block uses `negedge common_reset_n`.
- Deassertion is synchronized inside each clock domain by its own two-flop release
  synchronizer (`src_rst_sync`, `dst_rst_sync`); all state uses the local synchronized release,
  never the raw reset. Local `up` asserts only after local release, and each side synchronizes
  the peer `up`. `src_online`/`dst_online` mean local release plus peer-up observed; they are
  NOT measured clock-liveness signals.
- After EVERY reset, the source stays not-ready until `src_valid == 0` is observed on a source
  rising edge while online; only then does it arm until the next reset. A valid held high
  through reset is not automatically replayed (directed case
  `held_high_valid_across_reset`). This deliberately requires producer reset recovery to
  present low before a fresh offer; the module cannot know whether an opaque producer offered
  authentic or new data after that low - authority stays external. During normal armed
  operation, standard stable-until-accepted behavior allows consecutive offers without an
  intervening low.
- Reset discards pending snapshots with explicit accepted/delivered/reset-discarded accounting
  and no implicit retry. A stopped destination clock may allow one outstanding source capture
  after prior online state, then back-pressures indefinitely; no wall-clock recovery or timeout
  is promised. No transaction preservation is promised across independent reset lines: both
  reset sources MUST reach the shared reset network in actual integration.

## Parameter bounds

A `generate` block emits `$error` plus `$fatal(1)` for any `WIDTH` outside 1..1024. Actual
negative runs: `WIDTH=1025` fires the guard and exits 7 with the two diagnostic messages and no
`TB_DONE`; a `WIDTH=0` elaboration probe is a hard tool failure (vopt-8602 zero replication,
exit 12, `Error loading design`, no `TB_DONE`). WIDTH=0 cannot be represented as portable
SystemVerilog declarations/replication, so the same bound is enforced by the tool before the
guard executes; both behaviors are documented limitations, not a claim of a runtime check.
Synthesis-time evaluation of the guard is NOT claimed.

## Testbench, runner and the verification story

- `tests/control/rtl/tb_snapshot_mailbox.sv`: external-port scoreboard only (accept queue
  built from `src_valid && src_ready` at source edges; deliveries checked against the queue),
  phantom/stale/torn/ordering detection, `dst_valid && !dst_ready` stability checker, exact
  ledger accepted == delivered + discarded with flush accounting on every `common_reset_n`
  drop, reset-drop counters, watchdog that fails rather than passes (`+tb_neg_hang` path,
  `TB_WATCHDOG_NS = 1200000`).
- Directed cases and counts (accepted/delivered/discarded, identical at every width):
  `startup` 1/1/0, `payload_stall` 1/1/0, `consecutive` 8/8/0, `dst_clock_stop` 2/2/0,
  `src_clock_stop` 3/3/0, `held_high_valid_across_reset` 1/1/0, `reset_idle` 3/3/0,
  `reset_inflight_request` 2/1/1, `reset_valid_pending_stall` 2/1/1,
  `reset_dst_clock_stopped` 2/1/1, `reset_src_clock_stopped` 2/1/1,
  `reset_dst_only_stalled` 2/1/1, `reset_dst_only_inflight_request` 2/1/1 (destination-only
  reset while a request accepted at the source is still in flight, destination clock stopped);
  plus `random_soak`, 400 fixed-seed steps with resets, clock stops and ready toggles (seed
  `20261017DEE90001`), requiring at least 16 transfers.
- Payload patterns are a generated sequence with consecutive values always different at every
  width (bit 0 toggles), so stale/duplicate/torn deliveries are detectable at all widths,
  including WIDTH=1 where full uniqueness cannot be assumed; the directed suite runs at every
  width. Machine-readable `TB_EVT`/`TB_CASE`/`TB_SUMMARY`/`TB_DONE` lines are emitted and
  cross-checked.
- `tools/control/run_snapshot_cdc.py`: portable fail-closed ModelSim runner. Fresh output
  directory or refuse; argument arrays; bounded timeouts (<= 60 s, default 60); raw
  stdout/stderr, argv, exit codes and sha256 of tools, sources and transcripts; real `.do`
  macro FILES with `onerror {quit -force -code 8}` / `onbreak {quit -force -code 7}` (inline
  `-do` strings are not macros in ModelSim 10.7); no reliance on `$finish`; exact `TB_DONE`
  marker, per-case counts, ledger and event-line counts required; negative controls must fail
  exactly as expected (watchdog hang, WIDTH=1025 bounds, WIDTH=0 probe).
- Actual result (single actual run, ModelSim SE-64 10.7): widths 1, 32, 256 and 1024 each
  elaborated and simulated - per width accepted 68 = delivered 45 + discarded 23 (directed
  31/25/6 plus soak 37/20/17), 70 flush events, 46 source reset drops, 46 destination reset
  drops, 0 TB errors, sim end 18148 ns, exact `TB_DONE`; runner verdict PASS with 169 checks
  and 0 failures. Negative controls: watchdog exit 7 with `** Fatal: TB_WATCHDOG_TIMEOUT` and
  no `TB_DONE`; WIDTH=1025 exit 7 with the guard messages and no `TB_DONE`; WIDTH=0 probe exit
  12 with `** Error` and no `TB_DONE`. Raw logs, argv, command records, `.do` macros and hashes
  are published in `evidence/control/snapshot-cdc-20261017-06/worker/` (manifest.json).

## Physical integration gate (NOT discharged by simulation)

The held multi-bit bus is a bundled-data path, not independent bit synchronizers. Stable data
plus synchronized handshake supplies a digital settling interval, but physical correctness
still requires reviewed topology, bus delay/skew bounds, reset pulse requirements,
recovery/removal analysis and CDC/RDC reports after actual clock/reset integration. Both reset
sources MUST be joined to one shared flush network in integration. No blanket false-path XDC is
authorized. No MTBF, synthesis, implementation, timing closure, B05/R03 or board PASS follows
from these fixtures. Design guidance (not certification of this module):
https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Clock-Domain-Crossing ,
https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Multi-Bit-CDC ,
https://docs.amd.com/r/2022.1-English/ug949-vivado-design-methodology/Synchronous-Reset-vs.-Asynchronous-Reset

## Evidence index and hashes

- `rtl/control/deepeye_snapshot_mailbox.sv` SHA256
  `6d4500f250263f14ec24c6896cb69ad16704dd6c512dd565a1f92e91ccb2cc25`
- `tests/control/rtl/tb_snapshot_mailbox.sv` SHA256
  `ea2511ea1b10c3617cbcb4ba7872ed9cf22ab8aeee2858a1998dc6ab43cbd349`
- `tools/control/run_snapshot_cdc.py` SHA256
  `b6990585af5521d191da1050af70282363fecf74a05f2c22611c2b0173175923`
- ModelSim tools (hash-checked at run time): vlib 10.7, vlog 10.7, vsim 10.7 (SE-64).
- Worker evidence (public, text only): `evidence/control/snapshot-cdc-20261017-06/worker/`
  with `manifest.json`, raw stdout/stderr, `*.command.json` argv/exit/hash records, the seven
  `.do` macros and `events-extract.txt`. Worker-authored augmentations in the same directory:
  `h-contract-requirements-canonical.json` (verbatim canonical byte stream, SHA256
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`),
  `h-contract-verify.json` (independent recomputation record) and `worker-evidence-index.json`
  (sha256 of every file). `manifest.json` itself remains the runner-generated manifest of its
  43 runner artifacts.

## Limitations (do not over-claim)

- Digital RTL simulation only: arbitrary analog glitches, narrow reset pulses and metastability
  are NOT modeled or tested.
- No synthesis, implementation, timing closure, CDC/RDC sign-off, MTBF, B05/R03 or board
  result. The physical integration gate above remains open.
- The reset rearm rule intentionally drops a valid held high through reset; producers must
  present low before a fresh offer. This is not an ungated AXI-stream interface.
- `WIDTH=0` is a hard tool elaboration failure before the guard executes; only the 1025 upper
  bound is observed to fire the guard itself.
- H01-H15 product acceptance is not evaluated here; A alone operates hardware and owns the
  public ABI.

## Reproduction

```
python competition/deepeye/tools/control/run_snapshot_cdc.py \
  --out <fresh-directory> --spec <main-candidate-spec.md> \
  [--public-evidence competition/deepeye/evidence/control/snapshot-cdc-20261017-06/worker]
```

Defaults: widths 1,32,256,1024; ModelSim root `D:/modelsim1/win64`; 60 s per command; refuses
pre-existing output and pre-existing public-evidence file names. Exit 0 = all required runs
passed and every negative control failed as required.
