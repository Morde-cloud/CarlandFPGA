# B02 four-channel sample-scan capture author report

Generated: 2026-10-22T05:19:44Z

Status: author implementation and scoped author evidence complete. Independent
product-main acceptance and publication remain pending. This report is not a
product acceptance, board result or publication authorization.

## Identity and authority boundary

- Product/task: `DEEPEYE-IMPLEMENTATION-20261014/v1`
- Product director: thread `01a13b55-095b-7461-8dd5-5476a130bd82`
- Author work: `B-SAMPLE-SCAN-CAPTURE-RTL-20261022-21-v1`
- Product operation: `B-DEEPEYE-SAMPLE-SCAN-CAPTURE-20261022-21`
- Worktree: `D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014`
- Baseline HEAD: `7317b6ac3f8f19059031c46f8c4d2b0f9a8e9c06`
- Frozen design: `1011259415a0916054eb580687612580bc1e5f09`
  (`docs: seal revision1 final taskbook bytes`, tree
  `9d468881b0eda0e3bea7782a33a5527df8f02543`)

The assignment states that op20 ACCEPT and op21 CONTINUE are consumed by the
product main and that an independent main model/input freeze exists. The author
did not read or modify `main/freeze21.py`, `main/frozen-inputs`, `main_tb`, or
`main_verify` files. Main retains all decisions, acceptance and publication.

No board, service, configuration, credentials, queues, leases, SQL, peer or
Feishu action was performed. Nothing was staged, committed or published.

## Human contract verification

Verifier: `contract-check-01/verify_contract.py`, executed with Python `-B -X
utf8`; exit `0`, stdout SHA256
`30fc062a5b220018efd5a665b5bea2f413785f92572c34b21150c22264b08524`,
stderr empty.

- Contract: `DEEPEYE-HUMAN-LOCK-20261014`, revision `1`
- Pin: `f5989cd5defce561f9ba98e6b18fc2682945f0a2`
- Canonical path: `docs/competition/deepeye-2026/immutable_scope.json`
- Requirements array: 15 entries, IDs H01 through H15
- Canonicalization: JSON `ensure_ascii=False`, `sort_keys=True`,
  `separators=(',', ':')`, then UTF-8
- Independently calculated SHA256:
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`
- Fixed expected SHA256 matched exactly.
- Canonical snapshot: `contract-check-01/requirements.canonical.json`, SHA256
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`

All requirements were read and remain preserved:

| ID | Canonical title | Required product obligation |
|---|---|---|
| H01 | 游戏级三维品质 | Full game-grade 3D/UI |
| H02 | 中央边框立方体 | Hollow edge-only cube |
| H03 | 实体钻头和体积碰撞 | Solid-volume collisions |
| H04 | 可交互自由视角 | Free interactive camera |
| H05 | 自由摆放与随机场景 | Editable/random water/rock layouts |
| H06 | 自由选择进入和离开面 | Free entry/exit faces |
| H07 | 蓝红等径门和完整穿越 | Equal blue/red gates and complete-volume passage |
| H08 | 布局对控制系统先隐藏 | Hidden obstacle truth |
| H09 | 因果传感和真实参数依据 | Device-bounded causal observations |
| H10 | 三维在线共同决策 | Online 3D decision-making |
| H11 | PC AI实质参与 | Substantive PC AI |
| H12 | PC直控与经板执行合法 | Complete PC_DIRECT and FPGA-output paths |
| H13 | 最终验收硬门 | Final hard gates |
| H14 | 跨机跨会话最高优先 | Cross-machine/session highest priority |
| H15 | 仅明确人类指令可改 | Same-human-only revision |

No H01-H15 requirement was removed, weakened or reinterpreted by this module.
The module is one small capture component; all product-level obligations remain
open until independently satisfied and accepted.

## Final deliverables

All paths are relative to the worktree. These are the five author-owned paths.

| Path | Bytes | SHA256 |
|---|---:|---|
| `competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv` | 17174 | `fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d` |
| `competition/deepeye/fpga/acquisition/sample_scan_capture_candidate.md` | 6819 | `98c1748815deb873915ce7d85ae59af308467258b7a2dfd767f33ae4ab9f31ac` |
| `competition/deepeye/tests/rtl/acquisition/tb_sample_scan_capture.sv` | 72464 | `bf240773bc9a7e15683194e0d7418b1bf07f4e1b6f54267264223e161e47f393` |
| `competition/deepeye/tools/acquisition/run_sample_scan_capture.py` | 38882 | `fa88d077a0bce30904a35b98cc11d2759a002233022b7bae1739c905334b5333` |
| `competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/author/` | evidence tree | per-file hashes in invocation/case JSON and this report |

The RTL implements the fixed public interface, legal effective declaration
widths for invalid parameters, exact module guard fatals, abort priority,
order-checked four-channel scans, one complete-result slot, raw lane metadata,
event pulses, sticky exhaustion and saturating disjoint accounting. The
candidate document records the same behavior and its explicit non-claims.

## Final actual execution

Primary evidence directory:
`competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/author/final-all-01/`

Exact argv:

```text
D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8
D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/tools/acquisition/run_sample_scan_capture.py
--root D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014
--out D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/author/final-all-01/results
--modelsim D:/modelsim1/win64
--suite all
```

- CWD: `.../author`
- Process exit: `0`
- Runner stdout: `SAMPLE_SCAN_RUN_PASS`, SHA256
  `c653347b0791d35d0b0c4d60db9bd124436b48059bd8ffe401b6657f2090b671`
- Runner stderr: empty, SHA256
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Invocation: `final-all-01/invocation.json`, SHA256
  `9d13342f7c7b5c4269e6238d93a566b70582e1586295f68109fb7e934ca8e6fb`
- Summary: `final-all-01/results/summary.json`, SHA256
  `fe71e75dc89cb94e50f6d846370a019c9d45cc0583bad3f4c3f2f75592b42627`
- Hidden subprocesses: `CREATE_NO_WINDOW=true`

Toolchain actually observed:

```text
Model Technology ModelSim SE-64 vlog 10.7 Compiler 2017.12 Dec  7 2017
Model Technology ModelSim SE-64 vsim 10.7 Simulator 2017.12 Dec  7 2017
Python 3.12.9
```

The runner snapshots RTL and testbench per case, records exact argv/cwd, raw
stdout/stderr bytes and hashes, exit, timeout state and elapsed time, and uses
a fresh absent output directory. It refuses output overwrite and default
selection is the scoped new suites only.

## Final results

`summary.json` reports 27/27 selected cases passing, with no failed, missing or
unexpected cases:

- 16 core public-port simulations, total 820,621 testbench checks, all with
  `SAMPLE_SCAN_PASS`, zero mismatch lines, valid anchored statistics and zero
  errors/warnings.
- 9 guard cases: eight invalid parameter values each reached the actual DUT
  `$fatal` with `Errors: 1, Warnings: 0`; healthy control compiled and ran with
  `GUARD_CONTROL_ALIVE`, `Errors: 0, Warnings: 0`.
- 2 compiled RTL mutants, both rejected by concrete numeric public-port
  counterexamples with zero warnings.

Key core results:

| Case | Checks | Key final facts |
|---|---:|---|
| `directed` | 507 | 8-cycle stall, stable payload, full-scan drop, simultaneous retire/refill, conservation |
| `exhaustive6` | 467525 | all 4,096 six-channel strings; scan/drop/partial totals 48/22656/1728; empty and length-1/2/3 controls |
| `quality_lanes` | 65584 | every quality byte 0..255 in every lane; 4,096 events, 1,024 scans |
| `tag64_flush` | 324 | all-ones/mixed tag bits, bit 63, same-tag rearm flush |
| `abort_matrix` | 2035 | every partial stage and abort kind, stalled-record abort, all held-abort combinations |
| `seq2_conditions` | 463 | four-event terminal window, clean completion, order+exhaust coexistence |
| `seq3_conditions` | 433 | first full record retained after terminal drop, overrun+exhaust coexistence, partial terminal loss |
| `seq4_conditions` | 452 | terminal new-zero partial count and old-record transport |
| `stat2_saturation` | 806 | `STAT_W=2` saturation in each counter, continued flow, model identities across saturated windows |
| `stat3_saturation` | 1417 | `STAT_W=3` saturation in each counter, continued flow |
| `tick16_pack` | 132 | zero/equal/bit-15/full-scale 16-bit ticks transported unchanged |
| `tick1_pack` | 111 | minimum legal tick width and packed lane order |
| `mutant_mix` | 93 | healthy control for wrong-channel mixing stimulus |
| `mutant_loss` | 65 | healthy control for loss undercount stimulus |
| `seq16_window` | 454 | 65,536 actual events, 16,384 scans, crosses 32767/32768, consumes 65535, no wrap |
| `random20k` | 280220 | 20,000 edges; explicit checks confirm rearm, abort, order error, stall and completion presence |

Every simulation's stdout contains exactly one anchored `SAMPLE_SCAN_PASS` and
one complete `SAMPLE_SCAN_STATS` line. Runner classification also checks the
stats case name, numeric fields, conservation identities where unsaturated,
zero errors, zero warnings and zero literal ModelSim error/warning diagnostics.

## Guard and mutant evidence

The eight invalid guard cases and their exact actual DUT fatal bodies were:

- `SEQ_W=1`: `deepeye_sample_scan_capture: SEQ_W out of range`
- `SEQ_W=33`: `deepeye_sample_scan_capture: SEQ_W out of range`
- `TICK_W=0`: `deepeye_sample_scan_capture: TICK_W out of range`
- `TICK_W=65`: `deepeye_sample_scan_capture: TICK_W out of range`
- `TAG_W=0`: `deepeye_sample_scan_capture: TAG_W out of range`
- `TAG_W=65`: `deepeye_sample_scan_capture: TAG_W out of range`
- `STAT_W=1`: `deepeye_sample_scan_capture: STAT_W out of range`
- `STAT_W=33`: `deepeye_sample_scan_capture: STAT_W out of range`

Each compiled with `Errors: 0, Warnings: 0`, then emitted exactly one
line-anchored module fatal and no healthy marker. `guard_healthy` exercised the
same compiled module with legal parameters and emitted `GUARD_CONTROL_ALIVE`
with zero errors/warnings.

Mutant 1 changes the matching-channel condition to unconditional mixing.
It produced the required concrete mismatches
`mutant_mix_scans expected=0 actual=1` and
`mutant_mix_valid expected=0 actual=1` (plus 15 additional public mismatches).

Mutant 2 removes the current unexpected sample from the loss increment. It
produced `mutant_loss_discarded expected=2 actual=1` and
`stat_discarded expected=2 actual=1`.

Both mutants compiled successfully and failed only at public-port behavioral
checks with anchored testbench fatal, nonzero testbench errors, nonzero
simulator summary errors, no pass marker and zero warnings.

## Independent author-side reviews

1. `focused-review-01`: imported the runner without ModelSim execution or
   filesystem side effects, tested 78 pure classifier/selection/aggregation
   assertions and negative fixtures. Exit `0`; stdout
   `RUNNER_HELPER_REVIEW_PASS checks=78`, SHA256
   `b4548d80274ad6c4334448560b304b90599ad6b2b47a52d7486a0fdee77f983d`.
2. `exhaustive-math-01`: independent enumeration of all 4,096 six-channel
   strings reproduced `scans=48`, `discarded=22656`, `order_errors=18432`,
   `partial_end=1728`, plus empty and shorter-prefix controls. Exit `0`;
   stdout SHA256
   `4b1412c214022ec6eb084f938c8245e2e898d0fe5e48ce93f8e6d3c3efa5b8f0`.
3. `final-audit-03`: independently audited all 27 final case JSON files and
   raw transcripts, current RTL/TB hashes, exact classifications, tool version,
   hidden-process setting and zero compile/simulation warnings. Exit `0`;
   stdout
   `FINAL_AUTHOR_AUDIT_PASS cases=27 core=16 guards=9 mutants=2 ...`, SHA256
   `93f2c31faa1113086d144e6453b92c0e848b28098166d73a1a83bab25c854eb1`.

## Preserved failures and corrections

No failed attempt was overwritten:

- `core-01` preserved three initial test-oracle errors. Two sequence cases
  incorrectly expected same-edge consumption of a just-completed record,
  contrary to the required no-bypass rule; one `STAT_W=2` case compared
  saturated public counters to unbounded totals. Assertions were corrected to
  check occupancy plus next-edge retirement and to use the model only for
  unbounded flow after saturation.
- `coverage-recheck-01` preserved two overreaching new assertions. One expected
  a terminal empty-to-channel-0 start to be an order error; it is a legal new
  partial and is then discarded by exhaustion. One expected this fixed random
  seed to produce an overrun although it produced the required rearm, abort,
  error, stall and completion coverage. Only those incorrect expectations were
  removed; mixed event-flag cases and directed overrun coverage remain.
- `final-audit-01` and `final-audit-02` preserve auditor-script failures caused
  by a missing optional `# ` prefix and then missing CRLF normalization. The
  corrected `final-audit-03` passed.
- Earlier smoke directories preserve parameter-width development findings,
  guard-bench warning discovery, exact DUT fatal evidence, and the ModelSim
  wrapper exit-code quirk. They were not used to replace the final run.

## Ownership and repository hygiene

The author wrote only the five assigned paths. No evidence-root sibling,
top-level transcript, unowned helper, shared `.gitattributes`, main directory
content, root cache or `__pycache__` was created. Python ran with `-B`.
All helper scripts, snapshots, patches and ModelSim work libraries are under
the assigned author evidence directory.

A pre-existing worktree modification was present at
`handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json`; the author did not modify
it. No old source, test, handoff, runner, product file or main-owned file was
edited. No commit or staging operation was performed.

## Not run and limitations

`not_run` without separate actual evidence: synthesis, implementation, timing,
resource analysis, CDC/RDC, physical ADC/XADC protocol or pins, clock-rate and
source-heartbeat integration, DMA/PS endpoint, public `sample_id`, full product
or system integration, all 29 formal cards/G05/B06/R03, and physical board
measurement. Machine A alone may operate the board.

ModelSim evidence is from this node B environment only. No simulator or board
result from another node is claimed. The local event ordinal is not a public
ABI sample ID. The opaque tick and quality values imply no physical time,
calibration, liveness or authority. `out_valid` implies transport availability
only, never fresh physical acquisition or movement permission.

## Main handoff

Independent product-main acceptance remains required. It should use the final
source hashes above, the fresh `final-all-01` evidence, and its own separately
owned model/freeze. The main may publish only after its actual acceptance and
manifest work under the authorized operation. The author makes no publication,
peer, group, board, service or credential claim.
