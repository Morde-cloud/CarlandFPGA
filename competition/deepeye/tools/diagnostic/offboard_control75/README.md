# Private offboard control seam B75

This additive host adapter and finite fixture reuse the existing B73 50 MHz
mapper, capture engine, rearm logic and AXI wrapper without edits. This is a
synthetic consistency/functional interface, with no production issuer, transport
opening, planner, hidden-world input or motion authority. `ControlAdapter()`
always reports `INPUT_UNAVAILABLE`, `command=None`, `core_ran=False`; providing
JSON claims named BOOT/calibration does not change that. The explicit
`synthetic_fixture(context)` path exercises supplied commands only.

Contract DEEPEYE-HUMAN-LOCK-20261014/revision1: H01, H02, H03, H04, H05, H06,
H07, H08, H09, H10, H11, H12, H13, H14, H15 remain mandatory. Requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, pin
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, freeze
`1011259415a0916054eb580687612580bc1e5f09`. Full game-grade 3D/UI, hollow
edge-only cube, volume collisions, free camera/layouts/gates, hidden truth,
causal bounded observations, online 3D decision-making, substantive PC AI and
both complete H12 paths remain required. This work accepts none of those gates.
Original 100 MHz, final 1%/100ms, and R20/R21 failures remain unchanged. Only A
operates the board. No synthesis, route, build, board, SSH or service is run.

## Identity and clocks

The fixed synthetic context schema contains the source73 original identity
fields `operation_id`, `kernel_boot_id`, `session_id`, `clock_domain_id`,
`request_hash`, `build_manifest_sha256`, `source_record_sha256`, `capture_sha256`,
`tested_commit`, `tag`, `generation`, `trigger_id`, `request_seq`, `capture_seq`,
`source_admission_index`, plus full original `epoch` and `action_id` for this
control fixture. Strings and uint63 integers are retained without truncation.
Context properties return detached copies. There is no real Root action issuer
for this schema yet, and matching JSON is not authentication.

Each context receives thirteen separately issued nonzero uint32 words. They are
an injective allocation within this bounded adapter lifetime, not a context hash,
truncation or generation low bits. A separate monotonically issued command ID
and transport tag bind a request to its complete original context. Allocation
does not wrap or silently reuse words. Capacities are 8 context bindings, 16
command records and 16 captures per record. Exhaustion refuses without eviction.
This in-memory fixture has no restart/resume issuer. Restart recovery is
unavailable; a fresh instance is not permission to replay an old side effect.

Original uint63 source/acquisition QPC stays separate from uint64 PL edge ticks.
Queue/send recheck the original source age against 100,000,000ns. Applying-edge
TTL is the engine's actual applying edge plus `ttl_ms * 50000`; a receipt time
never becomes a source time or PL origin. Duplicate application/result/receipt
cannot renew TTL or regress captured state. The source73 structural view from a
`B74_SEMANTIC_FIXTURE_V1` wrapper is retained with its original identity/points,
`STOP`, `core_ran=False` and no command. It cannot release the production gate.

## Executable register/frame mapping

The G05P candidate's real magic/layout are `0x47303550`/2. AXI words are 32 bits,
aligned, full write strobes. This software uses caller-supplied register pairs;
it creates no MMIO/board connection. The synthetic stimulus serializes those
actual pairs as lines `0 address value expected_bresp`, reads as
`1 address 0 expected_rresp`, waits as `2 cycles 0 0`, and a final public PWM
observation as `3 0 0 0`. This file protocol is a test fixture, not a public ABI.

| Register | Actual function |
| --- | --- |
| `0x100..0x130` | thirteen issued identity words; written fresh before BEGIN |
| `0x00c=1` | BEGIN, binding a fresh candidate session |
| `0x200..0x218` | yaw int16 bits, pitch int16 bits, profile uint8, speed uint8, TTL uint16, command ID, transport tag |
| `0x00c=2` | commit request; successful AXI response alone is not engine acceptance |
| `0x008` | bound/retired/running/pending/latest/latch/inflight bits 0..6 |
| `0x014,0x018` | last command ID / active transport tag |
| `0x040..0x04c` | actual applied tick low/high and nonrenewed deadline low/high |
| `0x00c=4` | latch a real eligible capture |
| `0x300..0x37c` | 32-word immutable capture bank |
| `0x00c=5` | release the PL latch; **not** original host receipt ACK |
| `0x00c=3` | digital STOP/retire; terminal fault 6 (expiry is fault 2) |

Capture words 0..5 contain result sequence, command ID, tag, speed/profile,
pitch/yaw and TTL. Words 6..11 hold uint64 apply/deadline/result ticks. Words
12..17 are measured periods and highs; 18..23 and 24..29 are three uint64 start
and end witnesses. Words 30..31 echo issued epoch handle and magic. The adapter
checks actual observed words against the original request and full host binding;
it never substitutes expected words. The bench taps engine accepted/applied
events for observation only and also reads actual public register timestamps,
identity and captures. It drives no internal signals and uses no stubs.

## Lifecycle and retirement

QUEUED and HELD are unsent. `send_once` first sets sticky SEND_UNKNOWN, exclusively
writes and fsyncs its intent, then invokes the supplied side-effect callback.
Intent write failure or callback failure remains unknown; a second send is
refused. A callback return does not assert digital acceptance. Acceptance,
application and capture enter as separate exact downstream facts. The bench's
deliberately duplicated commit is a labelled RTL idempotence probe, not a host
adapter retry policy.

Cancel/new BOOT/epoch invalidate queued, held and downstream eligibility.
Unsent work is cancelled; attempted work becomes STOP_REQUIRED. Exact old-context
digital STOP evidence can reconcile old work after identity invalidation, but
does not establish world-motion STOP. New-context sends remain refused while
invalidated side effects await original retirement. Data-path quiescence has
no role in this proof. A genuine original host receipt and separate original
action retirement record are still needed. Fixture-only typed records test
that seam; no actual A records are generated or authenticated here.

A's aeac source time book still has original ADC ticks 0/470, late EM source age
473,319,100ns and null C3; actual action association/continuous valid span remain
unavailable. This adapter neither invents them nor changes that source clock.

## Focused execution

Run from an isolated source checkout with a fresh evidence directory:

```powershell
python -B -X utf8 competition/deepeye/tools/diagnostic/offboard_control75/run_focused.py --out <new-control-worker-directory> --job-helper D:/pynq/CarlandFPGA/fpga_mesh/windows_job.py
```

The runner snapshots and hashes selected code, verifies frozen dependency pins,
then uses separate Windows Jobs/libraries and 60s command/180s simulation caps,
2MiB live output cap, at most 512 stimulus operations and 6,000,000 simulated
cycles. It preserves versions, argv, raw output, traces, exit codes and terminal
Job accounting/closure. Any failure stops the operation; no retry loop exists.
`bounded_owned.py` is a scoped derivative of the existing Job runner, adding
live bounded output/deadline polling while retaining its Job accounting.

Planned cases are actual normal request→accepted→applied→capture→duplicate→STOP,
wrong identity write rejection and actual short TTL expiry, plus software
wrong identity/stale/duplicate/ACK-lost/new-BOOT/cancel/no-replay/capacity controls.
Separate software and RTL negative cases must exit nonzero. Exact executed
results are in the operation RESULT and raw files, never inferred from this
document. Tests use source snapshots before any later commit; a later commit
is not represented as already tested.
