# A review of B block encoder and stream/reset candidates

Tested PR30 head: `433db2a82854a669778eb8c3cd35c309623a087e`.
Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; original A Desktop generation2.
H01-H15 / `DEEPEYE-HUMAN-LOCK-20261014/revision1` and requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804` unchanged.

No blocking defect was found in the reviewed internal single-clock digital
candidate scope. A accepts the two modules as independently rerun simulation
references for subsequent integration/build work, not B01/B03 completion,
public TRACE/register/BOOT authority, hardware or formal product acceptance.

## Source and exact artifact identity

- Operation `B-DEEPEYE-BLOCK-ENCODER-20261018-08`: request
  `1d9241391495c931a925203b8b9efb2f7e2cf31256042aae997c009b2e186440`, source
  `4d244c5b4ed282dfa4ee610e6a2fa7b4d9ca4c40`, manifest
  `854f092b0d79c014bbd8669ae407d88c0375933b0c672f494f964b6ad2c414ab`.
  All310 declared artifact bytes match source and tested-head Git blobs.
- Operation `B-DEEPEYE-STREAM-RESET-20261018-09`: request
  `34ee72df3b3b2dee80402865d79dcdc1084b128ed3ae41487bca073b1261d126`, source
  `1c3fc4d0f0a5b1390787cc8c44ac34b055aa9818`, manifest
  `e6149beab779f6df7db1e8f780ef1c2d1ad5e555b780684500ba82cce37766a3`.
  All250 declared artifact bytes match source and tested-head Git blobs.

Canonical request hashes and both standard handoff verifications passed. A's
Windows checkout converted operation08 metadata to CRLF; the initial byte check
correctly failed. Current and prior Git blobs match the original manifest pin.
The successful checks and simulations use explicit Git-blob exports inside this
review's owned repository directory. No peer source, manifest or failure log
was rewritten. `input-verification.json` records every file, including local
checkout differences. The shared core remains exactly
`870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5`; wrapper is
`c8f8c0d99769efc64a91402ee23e7157368ff90ec765db5c413f02546715fff4`.

## Actual A execution

ModelSim SE-64 **2020.4**, compiler/simulator 2020.10, running the exact submitted
RTL and peer independent public-port testbenches/checkers. These are A reruns of
the peer's independent suites, not newly authored A oracles. vlib/vlog/vsim all
exit0; compilation and simulation report zero errors and warnings.

| Suite | Actual A result |
| --- | --- |
| Encoder ports | 1559 transactions:1493 successes,26 errors,40 aborts and40 recoveries;69312 successful-block samples,90653 complete payload bytes; all N1..128/E0,1,2,4,8; selected k0..14;81264 stability checks over3184107 cycles |
| Stream ports | 374 admissions:290 complete outputs,31 errors,53 flushed blocks;14011 samples,13100 observed bytes;25377 stability checks over540297 cycles;22 config/retire and26 sample/retire overlaps |

The encoder monitor also counts partial aborted traffic separately (73207 total
accepted samples and90663 observed bytes). Five stream counter seeds are
whitebox saturation diagnostics, not independently acquired stream evidence.
Port logs are byte-identical to the corresponding pinned B logs despite the
different simulator version: encoder SHA256
`17f1ee44b29092a734e264fece0e7b81ac1ce251cee9ec050254132a24f16dbd`, stream SHA256
`ab0c0f9c03b9327e380f07fd7f68f2a6e51d3cc41c25198e0a72ea37529e0d1c`.

The first A invocation failed at vlog because this older vendor tool encoded the
Chinese checkout path incorrectly and could not open its work-library database.
No simulation pass was claimed for that attempt. The next invocation uses a
new ASCII junction pointing exclusively to the same owned evidence directory;
source and build bytes remain physically inside the repository. No drive map,
global tool setting, credentials or service changed. Both attempts and raw tool
stdout/stderr remain preserved. Encoder invocation directly uses the original
case generator/checker plus equivalent compiler/simulator commands to avoid its
CLI's junction-resolving path conversion; original submitted source is unchanged.

## Review conclusion and next dependency

The two-slot wrapper preserves admission order, seals invalid count/E/last
transactions, derives actual core input from the sealed slot, and does not
retire a successful slot before final payload handshake. Allocation/retirement
update occupancy together; separate fill-slot identity addresses the old SR01
case. Reset takes priority, cancel gates external transfers and reaches the
real core, and abort accounting uses pre-flush occupancy. Tests cover the
concurrent cases and inspect actual public-port output, not only exit status.

This is internal MSB-first block data. Public TRACE's layout, metadata and cost
selection still need a separate approved adapter. Both endpoints must observe
the same synchronous reset/cancel and discard partial frames. There is no
asynchronous emergency-stop, stopped-clock, CDC/RDC or authenticated epoch
claim. Neither digital cycle counts nor software hashes prove physical timing,
compression bandwidth, synthesis resources or board behavior. B's prior mutant
and portable-worker evidence was hash verified but not newly rerun on A.

Continue the already authorized register transaction FSM and independent raw
diagnostic bank/HWH proposal in their two distinct stages; do not touch0x2c or
reuse an unverified overlay. The existing TRACE05/REGISTER07 bounded offline
decisions remain unchanged. Actual runtime, full ABI, all29 cards/R03, both
control paths, game/UI/AI and physical-board acceptance remain open/not_run.
