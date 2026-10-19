# Operation09 worker completion summary

Task DEEPEYE-IMPLEMENTATION-20261014/v1; main work
B-STREAM-RESET-INTEGRATION-20261018-09-v1; operation
B-DEEPEYE-STREAM-RESET-20261018-09. Worker: sole ordinary DeepSeek Flash/max
execution worker. Contract DEEPEYE-HUMAN-LOCK-20261014/revision1, H01-H15,
commit `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, independently recomputed
requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen design `1011259415a0916054eb580687612580bc1e5f09`; encoder base
`1c8ce8433b2adf5b50947b124f7397c603f7a978`.

Status: implementation and simulation verification complete for this bounded
increment. Final run is PASS. Whole-card/product acceptance is not passed.

## Deliverable hashes

These are SHA256 values of the actual final files:

```
c8f8c0d99769efc64a91402ee23e7157368ff90ec765db5c413f02546715fff4  competition/deepeye/fpga/stream/deepeye_block_stream.sv
8ad916887b0fb448b4e9a1ac6475a0368daeafe761e8de7140f13ad06cf8e7c2  competition/deepeye/tests/stream/tb_block_stream.sv
c9ed6752d607c99e9678881d8ab77d0cfde887d2d9b10f3f74ffa62b1b5d4872  competition/deepeye/tools/stream/run_block_stream.py
870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5  competition/deepeye/fpga/codec/deepeye_block_encoder.sv
2e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5  competition/deepeye/golden/codec/codec_reference.py
012a946647a3e967f1978946e648a36a1da36d696af6b95a3a4330a1e2732070  main_stream_spec.md
```

The core is read-only and is instantiated unchanged. The golden and main spec
bytes are pinned by the runner and copied into the final evidence export.

## Final execution

Python is 3.12.9. ModelSim is Model Technology ModelSim SE-64 10.7, compiler
and simulator dated 2017.12. Final output directory contains spaces:

`attempt-11-final-space-path/run output with spaces`

Concrete runner arguments, captured in
`attempt-11-final-space-path/runner.command.txt`, are equivalent to:

```
$py = D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe
$runner = competition/deepeye/tools/stream/run_block_stream.py
$core = competition/deepeye/fpga/codec/deepeye_block_encoder.sv
$wrapper = competition/deepeye/fpga/stream/deepeye_block_stream.sv
$tb = competition/deepeye/tests/stream/tb_block_stream.sv
$golden = competition/deepeye/golden/codec/codec_reference.py
$spec = D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/stream-reset-integration-20261018-09/main_stream_spec.md
$out = competition/deepeye/evidence/stream/stream-reset-20261018-09/worker/attempt-11-final-space-path/run output with spaces
$owned = competition/deepeye/evidence/stream/stream-reset-20261018-09/worker
& $py -B -X utf8 $runner --core $core --wrapper $wrapper --tb $tb --golden $golden --spec $spec --output $out --owned-root $owned --vlib D:/modelsim1/win64/vlib.exe --vlog D:/modelsim1/win64/vlog.exe --vsim D:/modelsim1/win64/vsim.exe
```

Actual simulator commands were recorded by the runner:

```
D:/modelsim1/win64/vsim.exe -version
D:/modelsim1/win64/vlib.exe work
D:/modelsim1/win64/vlog.exe -sv -work work <export>/deepeye_block_encoder.sv <export>/deepeye_block_stream.sv <export>/tb_block_stream.sv
D:/modelsim1/win64/vsim.exe -c -do <output>/run.do -l <output>/vsim.log tb_block_stream
```

All four tool executions returned exit 0, did not time out, and had empty
vlog/vsim stderr logs. The top-level runner returned exit 0. Compile reported
zero errors and zero warnings. The required positive markers `TB_DONE` and
`TB_END pass` are present, no negative diagnostic marker is present, and the
runner parsed the expected coverage and completion markers.

Result:

```
status=PASS cases=54 checks=1353306 failure=none
TB_SUMMARY cases=54 pass=54 fail=0 checks=1353306 cfg_hs=101 sample_hs=2794 meta_hs=92 data_hs=2401 ok=77 error=12 whitebox=9
TB_END pass
TB_DONE
Errors: 0, Warnings: 0
```

The published SHA256SUMS contains 23 entries, all independently rehashed with
zero mismatches. It excludes work-library artifacts and raw waveforms.

## Actual case inventory

The complete per-case list is also captured in
`attempt-11-final-space-path/case_inventory.txt`; all 54 cases are PASS.

Golden-driven vector sweep cases:

`VECTOR_0`, `VECTOR_1`, `VECTOR_2`, `VECTOR_3`, `VECTOR_4`, `VECTOR_5`,
`VECTOR_6`, `VECTOR_7`, `VECTOR_8`, `VECTOR_9`, `VECTOR_10`, `VECTOR_11`,
`VECTOR_12`, `VECTOR_13`, `VECTOR_14`, `VECTOR_15`, `VECTOR_16`, `VECTOR_17`,
`VECTOR_18`, `VECTOR_19`, `VECTOR_20`, `VECTOR_21`, `VECTOR_22`, `VECTOR_23`,
`VECTOR_24`, `VECTOR_25`, `VECTOR_26`, `VECTOR_27`, `VECTOR_28`, `VECTOR_29`,
`VECTOR_30`, `VECTOR_31`, `VECTOR_32`, `VECTOR_33`, `VECTOR_34`.

Directed and adversarial cases:

`TWO_BLOCK_FILL_AND_ENCODE`, `FILL_WHILE_FIRST_BYTE_STALLED`,
`QUEUE_FULL_BACKPRESSURE`, `BACK_TO_BACK_POINTER_WRAP`,
`ERROR_SUCCESS_ORDER`, `NO_HANDSHAKE_WITHOUT_READY`,
`SIMULTANEOUS_ALLOCATE_RETIRE`, `META_FIRST_MIDDLE_FINAL_BYTE_STALLS`,
`RESET_PARTIAL_INPUT_RECOVERY`, `CANCEL_PARTIAL_INPUT_RECOVERY`,
`HELD_CANCEL_COUNTS_ONCE`, `CANCEL_DURING_CORE_FEED`,
`RESET_DURING_METADATA_STALL`, `CANCEL_DURING_METADATA_STALL`,
`CANCEL_FIRST_BYTE_STALL`, `CANCEL_MIDDLE_BYTE_STALL`,
`CANCEL_FINAL_BYTE_COMPETITION`, `WHITEBOX_COUNTER_SATURATION`,
`RANDOMIZED_VALID_READY`.

The 35 golden vectors contain 13 RAW and 22 Rice outputs, five N1 and nine N128
cases, all E=0/1/2/4/8 values, padding, duplicate tags in directed cases, and
payload sizes through 256 bytes. Observed coverage includes 4096 queue-full
backpressure cycles, 1000 metadata-stall cycles, 1500 byte-stall cycles, 12
back-to-back blocks, pointer wrap, all error forms, every required reset/cancel
phase, fresh recovery, allocate/retire competition and nine explicitly
separated whitebox counter-boundary checks. The seeded randomized case supplied
21,298 schedule cycles, 517 observed ready-stall cycles and 748 random valid-gap
cycles; it is deterministic fault-oriented coverage, not a statistical proof.

## Fail-closed runner checks

`runner-guards-final` records three native stderr captures and exit codes:

```
pre-existing output       exit=2  ERROR output already exists: ...
aliased input paths       exit=2  ERROR aliased input paths
output outside own root   exit=2  ERROR output outside owned root
```

No simulator started for those rejected invocations. The normal final run
exercised the same runner with spaces in the output path and a flat input
export.

## Preserved attempts

Failures were retained in distinct directories; no failed attempt was
overwritten or relabeled:

```
attempt-01-wrapper-syntax          compile/syntax staging, not an integration result
attempt-02-integration             FAIL, vsim exit 12 from the absolute work-library invocation
attempt-03-integration             FAIL, vsim exit 12 after missing event-counter declarations
attempt-04-integration             FAIL, exposed fill_slot_q selection defect before sealing
attempt-05-integration             FAIL, testbench final assertion contradicted post-reset state
attempt-06-integration             FAIL, parser missed the simulator's # prefix though cases passed
attempt-07-integration             PASS, pre-randomized final integration
attempt-08-space-path              PASS, pre-randomized space-path run
attempt-09-random-schedule         FAIL, new case ended without clean reset and tripped final_stats_zero
attempt-10-random-schedule-clean   PASS, 54 cases after the randomized-schedule addition
attempt-11-final-space-path        PASS, final current-source run with spaces
```

The RTL defect in attempt04 was fixed in the wrapper by latching the allocated
fill slot and using it for all sample storage/sealing. The attempt09 failure
was a checker cleanup defect, not a data mismatch; all randomized blocks and
payloads matched. Attempts 10 and 11 validate the corrected tests.

## Raw evidence

Final raw evidence root:

`attempt-11-final-space-path/run output with spaces`

Key files and SHA256:

```
a24bc789325460603df8073e4818d6dd30633a6d5a68ba92048fad5e0b795408  vsim.combined.log
12e21b886dd3f542a4717b39e9e5a9d7fa43783d18f12d4f6c5ef21db5049f39  vsim.log
3d86fb5ff396c23e734ebb51720131dc00c37b8f0c901505416cad1356ee7f96  vsim.stdout.log
4d928cd91b0fb32be8327a4b6f2327a4ffe830fc320c361ebe02bc14082e3b80  vlog.stdout.log
68964a09257980c917b9d6d2da28be34ecc0ce9c4921777f689c9467703bad27  modelsim_version.txt
b56474d3c2c06bdc5fd2566119425226e7627b1a4e0d77c4acf5202fef0797c0  public_events.log
c81c24a3e5180a573fc92e609efacb3eaa29ef9c1d4082b4b28ceb6f23fe52fd  run_summary.json
e4d699e69028943a8371d4e54ccbfd680db8a5272f1f24dc31aec47ea7f7a25f  tool_runs.json
```

The output's `SHA256SUMS.txt` and `publish_manifest.json` list all publishable
local evidence. Work-library products and `.wlf`/`.vst` files are intentionally
excluded. Raw logs remain local under the owned worker root for main curation.

## Limits and outstanding work

No blocker remains for this bounded simulation increment. The following are
explicitly not passed or claimed:

- No synthesis, implementation, timing, resource, power or CDC/RDC result.
- No physical-board, whole-card, system, B01/B03 or full product acceptance.
- No TRACE/public ABI/register map, BOOT/tick source, session/authentication or
  motion-authority result. The two-slot store-and-forward wrapper is internal.
- The randomized schedule is fixed-seed directed coverage, not exhaustive or
  statistical proof.
- Synchronous reset/cancel requires the external consumer to discard any
  partially consumed frame.
- Whitebox counter deposits are separated from blackbox stream evidence.
- Only machine A may operate the physical PYNQ-Z2 board and report board
  measurements.

All H01-H15 requirements remain binding. This increment establishes only the
specified ordered two-slot stream/reset integration candidate in simulation.
