# Encoded-frame queue author evidence (op20)

Terminal author evidence for work
`B-ENCODED-FRAME-QUEUE-RTL-20261022-20-v1`, task
`DEEPEYE-IMPLEMENTATION-20261014/v1`, operation
`B-DEEPEYE-ENCODED-FRAME-QUEUE-20261022-20`.

- Role: sole ordinary DeepSeek V4.1 Flash/max author; not product main.
- Instance: `deepseek-b-46`; job
  `child-a65d74a1ffed41f0a5a81cbb8555e189`; thread
  `01a15f69-4aad-7b03-94a4-605daf72edba`; turn unknown and recorded as
  `null`.
- Baseline and actual head:
  `aef19351f1836b23f9a714bc5626db4eb4df98c5`.
- Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, pin
  `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`
  (H01-H15 reverified from the pinned commit), design
  `1011259415a0916054eb580687612580bc1e5f09`.
- Scope inputs: `IMPLEMENTATION_SCOPE.md`
  `49e80bffd951d90798a60478e1eaf1df7ce71f5834f529f2f0d01b975c91cd48`,
  `SCOPE_FROZEN.json`
  `7a825bb6c11b66326d4e800c294641d0fab8ac2541bea8926cdcffdc1d1b6de9`.
- Pre-dispatch main freeze: descriptor/byte-list model and
  `562178+358+358` input edges, freeze SHA256
  `bb9d82c145dd68324d1d0a2907336b488d1ee370a9977435c29c4570b3cd4249`.
  The author did not read or import the main oracle/vectors.

## Outcome

The candidate `deepeye_encoded_frame_queue` is implemented and passes the
author-directed ModelSim suites. It has exactly two `256 x 8` payload banks and
two descriptor records, pre-edge ready/valid, old-level admission, no
same-edge bypass, seal-before-visible output, poisoned reservations,
input-only sticky faults, older sealed output draining, synchronous shared
reset/cancel and saturating `STAT_W` counters.

The final actual run is
`run-final-01/RUN_RESULT.json`, SHA256
`b7ff221457005f407eac32e037d288c43ee4a1db56aae289d29d65aae7669a23`.
Runner exit was 0, status PASS, 218 runner checks passed, 0 failed, 233
artifacts recorded. Its exhaustive artifact map is
`run-final-01/ARTIFACTS.json` (SHA256
`dbd5123cb6e185d28cc9d8a80c203144b01566804da43c217c7b37e5d20f7fa3`).

| Suite | Cases | TB checks | vlib/vlog/vsim exit | Result |
|---|---:|---:|---|---|
| standalone | 23 | 10,949 | 0/0/0 | PASS |
| small `STAT_W=2` | 1 | 195 | 0/0/0 | PASS |
| compose | 3 | 1,102 | 0/0/0 | PASS |
| guard 0 | guard | fatal/1 | 0/0/0 | PASS (exact own fatal) |
| guard 1 | guard | fatal/1 | 0/0/0 | PASS (exact own fatal) |
| guard 33 | guard | fatal/1 | 0/0/0 | PASS (exact own fatal) |

The three guard runs emitted exactly
`DEEPEYE_ENCODED_FRAME_QUEUE_INVALID_PARAM STAT_W=0`, `=1` and `=33`
respectively, with `Errors: 1, Warnings: 0`, no unrelated error or warning,
no timeout and no PASS claim. `vsim` returned exit 0 in this ModelSim 10.7
environment; that observed behavior is required by the runner and documented
as a tool-specific assumption.

Toolchain used and recorded: ModelSim SE-64 10.7 Simulator/Compiler 2017.12,
`D:/modelsim1/win64/vsim.exe` and `vlog.exe`.

## Delivered files and hashes

- RTL `competition/deepeye/fpga/stream/deepeye_encoded_frame_queue.sv`:
  `68f9b655794a722a5cb285ac1c87749ea7acea7dcd6c1650536d1f1094c2e76a`
  (16,640 bytes).
- Candidate documentation
  `competition/deepeye/fpga/stream/encoded_frame_queue_candidate.md`:
  `351c63f5c442fc927139d8cbaffc40625a84a5efcda60b2270e034f3a9c790f5`
  (10,100 bytes).
- Testbench `competition/deepeye/tests/rtl/stream/tb_encoded_frame_queue.sv`:
  `cca5d51e34caa64b2c7d80b6d7f8c36c4aa729d0905981beb4c0afbae50455ef`
  (92,362 bytes).
- Strict runner
  `competition/deepeye/tools/stream/run_encoded_frame_queue.py`:
  `0d48490c3c096eb9e421450c39222461acd3add536127f7a5e3f3e452560116d`
  (34,279 bytes).
- `STARTED.json`:
  `69f3105d6c0f1f58f00f4d2457ec9a7b095b136314b87e82b51155a1bbeeb6db`.
- `RESULT.json`: listed in `EVIDENCE_MANIFEST.json` after sealing.

Pinned inputs verified unchanged by the runner:

- `competition/deepeye/fpga/codec/deepeye_block_encoder.sv`:
  `870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5`.
- `competition/deepeye/fpga/stream/deepeye_block_stream.sv`:
  `c8f8c0d99769efc64a91402ee23e7157368ff90ec765db5c413f02546715fff4`.
- Protected codec `handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json`:
  `6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8`.

## Preserved attempts

No failed attempt was overwritten. The `smoke/` directory preserves:

- `main-001`: testbench compile correction (5 compile errors).
- `main-002`: 6 cases, 4 pass, 2 fail, 3 TB check failures.
- `main-003`: intermediate 6/6 pass, 6,885 checks.
- `main-004`: 13 cases, 9 pass, 4 fail, 32 TB check failures.
- `main-005`: intermediate 13/13 pass, 9,962 checks.
- `main-006`: intermediate 23/23 pass, 10,949 checks.
- `small-001`: `STAT_W=2` sampling failure, 2 TB failures.
- `small-002` and `small-003`: 1/1 pass, 195 checks.
- `compose-001`: fixture defects, 3/3 cases fail, 22 TB check failures.
- `compose-002`: 3/3 pass, 1,102 checks.
- `guard-0`, `guard-1`, `guard-33`: smoke exact-fatals.
- `guard-composecheck-001`: compile-only check after the composition module
  was added.
- `runner-smoke-01`: runner ordinary and guard branches, 91 artifacts.

These paths and every file hash are listed in `EVIDENCE_MANIFEST.json`;
`EVIDENCE_MANIFEST.sha256` seals that manifest.

## Coverage and limits

Author coverage includes reset/idle, single and two-deep frames, same-edge
races, no old-level credit at full, representative framing boundaries,
early/missing last, invalid descriptors, upstream errors 1/2 and opaque 3,
fault with older draining, duplicate/ABA tags, multiple cancel points, reset
priority, simultaneous allocate/retire and seal/retire, limited pointer wrap,
`STAT_W=2` saturation, the two-slot composition with raw/Rice/error/cancel and
a full 256-byte payload, and guards 0/1/33.

The author does not claim exhaustive 2048 framing, all 256 byte values, at
least 1000 wraps, every early-last position, cancel exactly on the final input
byte or output-last edge, or independent mutant kills. The product main owns
those independent acceptance items, the frozen descriptor/byte model and final
product acceptance. This work is not self-accepted.

Simulation, synthesis, implementation, timing, board and system remain
distinct. No synthesis, implementation, timing, board or system result exists
for this new module. All29/G05/B06/R03/board/system remain `not_run`; only A
may operate the physical board.

## Terminal actions

No commit, push, PR, peer/group message, Feishu presence broadcast, credential,
service, configuration, SQL, queue or physical-board action was performed.
No main oracle or vectors were read or imported. This is the terminal author
evidence for exactly this single assignment; no replacement job or old
operation replay is requested.
