# Private G05 triple-output / external-capture diagnostic

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`. H01–H15 remain fixed by
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, frozen design
`1011259415a0916054eb580687612580bc1e5f09`.

This new diagnostic implements a private PS/AXI transaction path to three
atomically applied PWM outputs and three separately synchronized external input
pins. It does not implement public BOOT, source freshness, game motion authority,
physical instrument calibration, R03 or either complete H12 control chain.
Only A may operate the physical board. Existing control3d primitives are reused
without changes. The old diagnostic, address `0x2c`, and existing overlays are
outside this interface.

## Composition

| Component | Responsibility |
| --- | --- |
| `mapper/` | Fixed integer profile, postquantized combined curvature, PWM counts and TTL conversion |
| `engine/` | Atomic triple application, original applied-cycle TTL, three external synchronizers, continuous complete-period joins, terminal STOP/fault |
| `axi/` | One full immutable run/nonce/session identity per reset, monotonic command IDs, staging and immutable host record latch |
| `independent/` | Earlier AXI-only review with stubbed mapper/engine; no actual waveform claim |
| `composition_independent/` | Independent real-composition public-port review; consult its actual result before claiming success |
| `build/` | Explicitly authorized new project/package, narrow verified CDC exceptions and paired bit/HWH preparation |
| `../../../tools/diagnostic/g05_capture/` | Pure host protocol validation, offline register preparation and bounded collector work |

The mapper uses a 100MHz digital-clock candidate and a fixed 2,000,000-cycle
PWM period. Angular highs are `250000 + 16*q` for signed quantized yaw/pitch;
speed high is `50000 + 1000*speed_code`. Both axes share the exact 64-bit
combined-curvature limit; invalid inputs are rejected rather than clipped.
TTL milliseconds convert to 100,000 ticks and start at the actual PL application
edge. The old deadline remains effective while a new command is pending.
Duplicate command identity and bytes do not renew that deadline or reapply PWM.
Read [mapper details](mapper/README.md) and [AXI register semantics](axi/README.md)
for the complete encodings and reset/STOP behavior.

Each external input has its own three-stage `ASYNC_REG` chain and capture
instance. No internal PWM feedback net is part of the design. A simulated
external connection in a testbench is a digital fixture, not proof of wiring,
metastability behavior, physical skew or measured frequency. The accepted
private candidate tolerates at most two ticks of period/high deviation and
cross-channel start/end skew. First and ongoing capture watchdogs are bounded;
missing, incompatible or mixed-frame records cause terminal failure.

The current engine rearms at actual application `A+7`. For a successful join,
`joined_event-A = max(raw_end_witnesses)+8`. Host validation enforces the
necessary lower bound. This equation describes this logic revision and its
relative witnesses; it is not a host/PL clock mapping or physical delay bound.

## Identity and host observation

Run ID is 256 bits, nonce 128 bits and session 32 bits. All are nonzero and bound
once per hardware reset. Command ID is a nonzero, strictly increasing 32-bit
integer; tag is an opaque 32-bit value. IDs do not wrap. The selected profile is
locked after the first command. Reset retires the old device state; a new A
operation must choose a fresh full identity. These checks do not cryptographically
authenticate a caller or establish cross-reset BOOT provenance.

The host explicitly latches one complete 32-word record, checks status/fault,
all 13 identity words, command identity and immutable payload before and after
reading, validates raw counts/witnesses, then acknowledges the held record.
New captures cannot overwrite a held record. STOP, expiry and fault invalidate
eligibility; an already issued AXI read response remains stable for protocol
completion and must not be treated as fresh after that invalidation.
All decoded outputs retain `movement_authorized=false`.

## Build and A handoff boundary

The six candidate PL pins come from A's pinned PMODB map: yaw/pitch/speed
outputs W14/Y14/T11 and distinct capture inputs V16/W16/V12, bank34 LVCMOS33.
No J3, analog or RS485 allocation is inferred. Actual board revision, wiring,
electrical suitability, external propagation and physical skew remain A inputs.

Default build-tool mode only prepares and validates its inputs. A full B build
requires a separate exact main source acceptance, new operation/output directory,
six-file source/hash map, build-tool pins and exact three-stage CDC bindings.
At synthesis the tool verifies actual FF pins, chain connectivity, clock and
`ASYNC_REG` properties before excluding only the external input to its first
stage D pin. Later stages remain timed. It supplies no invented IO delays.

Only an actual completed run can supply its new bitstream, matching HWH,
discovered AXI base, reports, original journals and manifest. HWH structure,
internal timing and digital simulation do not establish full external timing.
The A collector must verify the exact new package before runtime import or MMIO,
use a new explicit A operation, preserve all original failures, and issue bounded
STOP cleanup after MMIO exists. No old failed/unknown operation is replayed.

As this source checkpoint is being assembled, real-composition qualification,
full Vivado execution and collector review remain separate pending steps.
Their final raw manifests and handoff identify what actually completed.
All formal cards remain incomplete until their original task-book criteria are met.
