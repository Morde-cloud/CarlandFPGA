# Main review: snapshot CDC candidate 06

Operation B-DEEPEYE-SNAPSHOT-CDC-20261017-06, task
DEEPEYE-IMPLEMENTATION-20261014/v1. B main accepts only the isolated digital RTL
candidate. The shared register ABI remains A-owned. B05/R03, synthesis,
implementation, physical CDC/RDC/MTBF, board and system are not_run.

H01-H15 DEEPEYE-HUMAN-LOCK-20261014/r1 requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
design1011259415a0916054eb580687612580bc1e5f09. A alone hardware.

## What is implemented

A one-outstanding opaque snapshot mailbox holds the entire bus until the
destination consumes it and acknowledgement returns. Either reset flushes both
sides, including stopped clocks. Each domain releases its own reset through two
flops. Source must observe valid low while online after reset before rearming.
Online is reset-handshake state, not clock liveness. No public field map,
capture coherence, source authentication, STOP timeout or motion authority is
implemented by this transport. Physical gate is detailed in
main-physical-integration-boundary.md with AMD primary references.

## Independent findings and evidence

SC01: worker source used raw asynchronous reset on all state blocks and only
gated the data path with local release. Its169 checks and main's70000-step
behavioral corpus passed, but this did not meet the specified reset-pin
structure. Main preserved rejected-worker/ and corrected five source/four
destination blocks. Two reset-release synchronizers still receive raw reset.
Source ready and destination capture now explicitly require online state.
Main inspected this structure; no physical failure experiment is claimed.

Corrected source:169 worker checks rerun,169 portable flat-directory checks
with spaces in paths, and seven independent clock/width cases (1,8,16,32,256,
1024 bits;256 twice).70000 external-port steps give534 accepted=500 delivered
+34 reset-discarded,17523 stability checks and42 reset events. Every corrected
port trace matches the corresponding pre-correction trace byte-for-byte.
The main TB uses only ports; its Python queue oracle imports no worker model.
Stress offers include deliberately changing unaccepted data to check captured
payload isolation; they are not claimed as AXI-compliant source traffic.

35 mutations of captured port data are rejected. Actual RTL variants omitting
destination reset or valid-low rearm also fail the independent checker (exit1).
The worker runner separately rejects watchdog, WIDTH1025 and observed ModelSim
WIDTH0 elaboration negatives. Existing-output and input-alias commands exit2
without modifying input or prior evidence. Tool-runner-discovery/ retains an
earlier inline -do trap: fatal/error transcripts returned0. Real .do macros,
explicit completion markers, transcript checks and verified negative exits are
required. A signed one-bit decimal examine result is also not compared to1.

worker/ is the unmodified original worker evidence (46 indexed hashes verified);
main-worker-export/ and main-portable-export/ describe the corrected source.
Original worker runs1-3 remain private historical scratch; its published run4 is
preserved here. Raw commands and hashes accompany every reviewed run. Only fresh
scratch libraries were excluded. CSV/vector gzip files are lossless; their raw
hashes are in case results or raw-compression-index.json. No old logs are relabeled.

## Reproduce from repository root

Use fresh output paths. Default tools are D:/modelsim1/win64; override --tools
on the independent reviewer or --modelsim-root on the worker runner.

```text
python -B -X utf8 competition/deepeye/tools/control/run_snapshot_cdc.py --out .local/new-snapshot-worker
python -B -X utf8 competition/deepeye/evidence/control/snapshot-cdc-20261017-06/main/main_port_review.py --source competition/deepeye/rtl/control/deepeye_snapshot_mailbox.sv --tb competition/deepeye/evidence/control/snapshot-cdc-20261017-06/main/main_port_replay_tb.sv --output .local/new-snapshot-main
python -B -X utf8 competition/deepeye/evidence/control/snapshot-cdc-20261017-06/main/main_checker_negative.py --review competition/deepeye/evidence/control/snapshot-cdc-20261017-06/main/main_port_review.py --results .local/new-snapshot-main --output .local/new-snapshot-checker-negative.json
```

For intentional actual-RTL negatives, replace --source with either
main-negative-missing-destination-reset.sv or main-negative-missing-rearm-low.sv
in this directory and use a fresh output path. Expected reviewer exit1, after
the simulator itself successfully emits a complete port trace. The independent
checker detects the violation. Do not count those exits as passing DUT runs.
Return feedback on PR30 with operation/request_hash/tested_commit/log hashes.
