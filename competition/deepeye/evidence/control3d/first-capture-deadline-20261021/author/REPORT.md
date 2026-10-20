# Operation 18 author self-test report

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; work
`B-FIRST-CAPTURE-DEADLINE-RTL-20261021-18-v1`; operation
`B-DEEPEYE-FIRST-CAPTURE-DEADLINE-20261021-18`.

## Conclusion

The candidate module, independent author testbench, strict runner, and portable
runner unittest are present and were executed for real with ModelSim 10.7
SE-64 and Python 3.12.9. The final normal run, the four real RTL mutant runs,
and the 24-case unittest all pass their author-side qualification.

This is **author self-test only**. It is not product acceptance, synthesis,
implementation, timing, CDC/RDC, all29/G05/B06/R03, board, or system
acceptance. The quality main owns the independent acceptance decision.

## Contract and inputs

- Parent main: thread `01a13b55-095b-7461-8dd5-5476a130bd82`, supplied actual
  turn `01a15a57-d30e-75f2-9fa1-fc0d16a995a6`.
- Child: DeepSeek V4.1 Flash/max; factual thread
  `01a15a5f-ed72-7590-99a2-ad1b897cb486`. The local controller did not expose a
  separate child turn id; no child turn id is fabricated in `RESULT.json`.
- Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, pin
  `f5989cd5defce561f9ba98e6b18fc2682945f0a2`.
- H01-H15 were read in full. Canonical requirements SHA256
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`
  (`ensure_ascii=False`, `sort_keys=True`, `separators=(',', ':')`, UTF-8)
  matched the fixed expected value.
- Frozen design `1011259415a0916054eb580687612580bc1e5f09`; baseline worktree
  HEAD `ccf3698cce065e20dbfa24bb6d07a97be7e38de6`.
- `INTERFACE_FREEZE.md` SHA256
  `e42b4b81f8c52016c7b51ff442a712df8625aa0e9587aa5b758cb59267e354e1`.
- `SEMANTIC_REVIEW.md` SHA256
  `bbfb9f7dc238215f1bd9e7a09e8e53a591eeda63cadd3d9e54d9c035eeae7d83`;
  `IMPLEMENTATION_AUTHORIZATION.txt` SHA256
  `b3dcd52ec62ff63ac4b9aefad146136946c66f55bce2d5a13fa5127d23549af7`.
- Protected `handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json` remains
  SHA256 `6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8`.

## Implementation result

`deepeye_first_capture_deadline` implements the frozen public interface:
`clk`, `rst`, `cancel`, `start`, `observed`, `budget_cycles`, the four
registered state levels, and the four registered entry events. `BUDGET_W`
defaults to 32; widths 1..32 are supported.

The implemented priority is:

1. synchronous `rst`/`cancel` clears all state/events;
2. WAIT + `start` rejects with INVALID and does not renew;
3. non-WAIT + positive `start` enters WAIT, latches the budget, emits
   `started_event`, and ignores same-edge `observed`;
4. non-WAIT + zero-budget `start` enters INVALID and replaces an old terminal;
5. WAIT without `start`: `observed` completes; otherwise the final allowed
   edge expires; otherwise WAIT remains;
6. non-WAIT without `start` retains IDLE/terminal and ignores late `observed`.

For start E0 and N>0, the internal countdown starts at N-1, so pre-edge
`observed` is eligible on E0+1..E0+N inclusive. E0+N `observed` wins over
expiry. An E0+N+1 post-NBA record cannot revive a terminal. A held `start` is
sampled every edge; held zero-budget requests emit one rejection event on every
edge. Changing `budget_cycles` while WAIT does not change the latched deadline.

## Test method and coverage

The author TB uses a separately written enum/case reference model and only
public DUT ports. It never reads DUT hierarchy or generates expectations from
DUT outputs. The new B15 composition fixture uses exactly:

```systemverilog
start    = window_started;
observed = out_valid;
cancel   = stop || (cfg_valid && cfg_ready) || pending || !running ||
           !window_active || failure_event || (|raw_fault_events);
```

`rst` is shared; `out_ready` is not in `cancel` or `observed`. `sample_levels`
is a separately driven literal waveform.

Final normal run: `run-normal-final-01` (root under `author/`), exit 0:

| case | width | scenarios | checks | failures |
|---|---:|---:|---:|---:|
| standalone | 1 | 125 | 59688 | 0 |
| standalone | 2 | 163 | 62055 | 0 |
| standalone | 3 | 287 | 73305 | 0 |
| standalone | 4 | 727 | 137997 | 0 |
| standalone | 5 | 2375 | 565173 | 0 |
| bounded prefix | 32 | 31 | 17559 | 0 |
| composition | 4 | 7 | 661 | 0 |
| guard | 0 | exact expected fatal | n/a | 0 |
| guard | 33 | exact expected fatal | n/a | 0 |

Directed small-width coverage includes 765 observation positions (every
budget 1..2^W-1 for W=1..5, positions 0..N+1), 765 cancel positions, 765 reset
positions, 708 repeated-start positions, 40 priority scenarios, 10 held-start
scenarios, 10 terminal scenarios, 114 latched-budget scenarios, and 500
deterministic random scenarios. Each has a unique scenario id. The final totals
are 3715 scenarios and 916438 checks.

The literal P2/H1 trace has real waveform results: N3 completes on row7
(E0+3); N2 expires on row6 (E0+2); row7 pre-edge `out_valid` is the first
eligible record. The second trace retains the row6 record with `out_ready=0`
at row7, transports it at row8 pre-edge, and produces a post-edge subset-rise
raw fault at row8. Completed status is still observed at row8 post-NBA; it is
not retrospectively revoked. At row9 the public fault cancellation clears the
terminal state. Quiet B15, STOP, new configuration, and ineligible-application
`failure_event` cases also pass.

## Real RTL mutants

Four copies of the new module were created under the author evidence root and
actually compiled and simulated at widths 1, 2, and 3. Every copy compiled
successfully and was rejected by public-port behavior:

| mutant | widths | CHECK_FAIL counts |
|---|---|---|
| deadline-off-by-one | 1,2,3 | 1623, 1250, 1086 |
| repeat-start-renewal | 1,2,3 | 2687, 3335, 3561 |
| cancel-ignored | 1,2,3 | 392, 784, 1123 |
| late-observed-resurrection | 1,2,3 | 6156, 4733, 4395 |

Final mutant run: `run-mutants-final-01`, exit 0. No compile failure, X-only
initialization, or parser injection is counted as a hit.

## Runner and unittest

The runner snapshots exact source bytes, argv, tool versions, and UTC
timestamps before execution; every case gets a new working directory and
unique logs. ModelSim/Python children use `CREATE_NO_WINDOW` and explicit
timeouts. The strict parser requires one RUN/SUMMARY/FINISH, unique scenario
ids, complete/consistent group counts, matching scenario/check totals, PASS,
expected exit, no timeout, no unrelated Fatal/Error, and no pseudo prefix.
Guard qualification requires the exact `BUDGET_W=<original> SAFE_BUDGET_W=<clamped>`
diagnostic, the exact fatal text, no live marker, and the actual ModelSim exit
0. A valid-width fake guard is rejected.

`unit-final-01` executed 24 standard-library unittest cases with exit 0:
genuine normal width1 transcript acceptance, genuine guard0/guard33
acceptance, fake guard, wrong diagnostic, duplicate/conflicting summary,
duplicate finish/scenario, missing finish, unrelated fatal/error, pseudo
prefix, group/count mismatch, expected/non-expected exit, and real subprocess
timeout. The unit test does not depend on old private evidence or controller
layout.

## Actual failures and fixes

All preflight logs are retained under `author/`; no failed side effect was
replayed or silently discarded.

- `preflight-01`: compile failed because the default source root duplicated
  `competition/deepeye`; fixed the runner default to the worktree root.
- `preflight-02`: `ref` is a SystemVerilog keyword; renamed the reference
  instance to `ref_model`.
- `preflight-03`: width1 metadata used non-representable budgets 2/3; the
  priority/held/terminal budgets were parameterized to the DUT width.
- `preflight-04`: width1 standalone passed after those fixes.
- `preflight-05`: composition expected `failure_event` one edge early and
  assumed WAIT at row7 although the legal row7 `observed` completes; corrected
  the TB to the actual public pre/post rows. The N3/N2 traces already passed.
- `preflight-06`: backpressure row7/row8 completion expectation still assumed
  a later completion; corrected to completed at row7, retained at row8, and
  cancelled at row9.
- `preflight-07`: composition passed.
- `preflight-08`: width32 budget1 produced a duplicate scenario id; guard
  parser/exit assumptions conflicted with ModelSim's `$fatal` exit behavior.
  Deduplicated the prefix positions; the guard-exit probe demonstrated exit 0
  for all probed completion forms, so guard qualification was corrected to
  exact diagnostics plus actual exit 0.
- `preflight-09`: all normal cases passed; a stale zero-exit guard rejection
  reason was removed in the final runner.
- `preflight-mut-01`: all four mutants were behaviorally rejected.
- Final `run-normal-final-01`, `run-mutants-final-01`, and `unit-final-01`:
  all expected checks pass.

## Limitations and non-claims

- New synthesis and implementation are `blocked`/`not_run`: no Vivado is
  installed on this machine. No timing, utilization, DRC, CDC/RDC, placement,
  routing, bitstream, or complete-system result is claimed.
- The old A OOC result applies to the old three RTL only and is not inherited
  by this new module.
- Width32 is a bounded prefix, not a complete 2^32 traversal.
- `all29`, `G05`, `B06`, `R03`, physical board, and complete system are
  `not_run`. Only machine A may operate the board.
- No physical TTL, clock rate, source authentication, BOOT, register/TRACE/HWH,
  `0x2c`, ABI, profile, curvature, final authority, CDC/RDC, motion authority,
  or STOP/PWM/ENABLE connection is introduced.
- H01-H15 remain fully preserved: 3D/UI, solid collisions, free camera/layout,
  equal blue/red gates and full passage, hidden truth, causal observations,
  substantive PC AI, and both H12 control paths are not weakened or made
  optional.
- ModelSim 10.7 returns exit 0 for `$fatal`; this is recorded as a tool fact,
  not presented as a nonzero error exit.

## Evidence index

- Final normal manifest: `author/run-normal-final-01/RUN_MANIFEST.json`,
  SHA256 `3b3fe16f87c4f8e1323ee9775d2a07106ad3c5fdcaf63349cad6cc13dbe0a8c9`.
- Final mutant manifest: `author/run-mutants-final-01/RUN_MANIFEST.json`,
  SHA256 `3e9137607568fd5725fb5703a26dc25f80c03e9217c8951b0636c0887b84a871`.
- Final unit manifest: `author/unit-final-01/UNIT_MANIFEST.json`,
  SHA256 `30e8ba0c2591542e659cd2accd1b6667cf61b6a51df6e4fe43994a0220519510`;
  unittest log SHA256
  `5a645ec9ede2abfef71ba8ca53c9840182f29cde9dc30607be016aa0e1cc589e`.
- Guard exit probe: `author/guard-exit-probe-02/PROBE_META.json`,
  SHA256 `fc92058ec278dd1d33051bcd1974adefdf473e3fcd76cddad9d70690432d5a78`.
  Probe-02 snapshotted sources and versions before its compile and three hidden
  simulations; probe-01 remains as the earlier preserved diagnostic.
- Full raw-log index: `author/EVIDENCE_INDEX.json`, SHA256
  `6be0efecc1c201cdda4ab5b9113eb9585a2736f6a251698436a3b38d66157e3f`
  (387 entries; RESULT/REPORT/INDEX are excluded from the index to avoid
  self-reference).

## Exact source hashes

| path | SHA256 |
|---|---|
| `competition/deepeye/fpga/control3d/deepeye_first_capture_deadline.sv` | `860010695ef248467e518605dbecf0482e9a2e6b9a1f0b9d30c6e3e730047fae` |
| `competition/deepeye/fpga/control3d/first_capture_deadline_candidate.md` | `2461dd979fe1da20728006102f329c131cf7833a4a58f6f5a5a16389543ad593` |
| `competition/deepeye/tests/control/tb_first_capture_deadline.sv` | `73fede9faf1b2067e3179291d63f0f70c653555a42195d418facd4bdf1917ab0` |
| `competition/deepeye/tools/control3d/run_first_capture_deadline.py` | `b7dea7fb82236a6e8fa8a3b959fb26835d6d35e0557d7fda9eaaca44cf9fd7fc` |
| `competition/deepeye/tests/control/test_first_capture_deadline_runner.py` | `7e2951f08ee076fdef8c89c5131230342da37e4e46b2b119e043514836cf63dd` |

## Ownership release

Author write ownership covers only the five files above and the
`author/` evidence subtree. The main-owned
`main_verify_first_capture_deadline.py`, `main/`, `README.md`, and operation
handoff paths were not touched. The author task terminal-reports to Astra-B
main thread `01a13b55-095b-7461-8dd5-5476a130bd82` and releases author write
ownership after this report. Any later main repair of an author file requires a
persisted takeover basis.
