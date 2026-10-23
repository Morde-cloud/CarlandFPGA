# Buffered block-stream composition candidate

Operation: `B-DEEPEYE-BUFFERED-BLOCK-STREAM-20261024-35`  
Task: `DEEPEYE-IMPLEMENTATION-20261014/v1`  
Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01-H15, requirements
SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`  
Frozen design: `1011259415a0916054eb580687612580bc1e5f09`

Status: author candidate only. The main owns independent acceptance. This is not
TRACE packing, a public ABI/register map, QoS, BOOT/tick, an ADC/source-clock
domain bridge, DMA, the full B03 pipeline, or a physical-board result. The <=32
byte TRACE adoption gate remains external and A-owned.

## Fixed dependency pins

All three RTL files below are read-only inputs from Git commit
`bbfb11439b35e0866a6d2486f3857b92ed6cf529`.

| File | SHA256 |
|---|---|
| `fpga/codec/deepeye_block_encoder.sv` | `870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5` |
| `fpga/stream/deepeye_block_stream.sv` | `c8f8c0d99769efc64a91402ee23e7157368ff90ec765db5c413f02546715fff4` |
| `fpga/stream/deepeye_encoded_frame_queue.sv` | `68f9b655794a722a5cb285ac1c87749ea7acea7dcd6c1650536d1f1094c2e76a` |

Published codec references used only to generate expected fixtures:

| File | SHA256 |
|---|---|
| `golden/codec/codec_reference.py` | `2e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5` |
| `golden/codec/known_vectors.json` | `c1eee67b73b8cdd449ac72b2a77c78f714eaf448b1216b16296488881ac10e99` |

The authored testbench does not use DUT output as an oracle. Its expected
payloads are generated from the published codec reference and fixed away from
the DUT.

## Interface and composition

`deepeye_buffered_block_stream` has fixed defaults, no parameters, and no new
storage or sequential state. It instantiates exactly one unmodified
`deepeye_block_stream` and one unmodified `deepeye_encoded_frame_queue` with its
default `STAT_W=32`. The encoder exists only inside `deepeye_block_stream`.

Upstream configuration and sample ports retain the block-stream semantics:
`cfg_valid/ready`, `cfg_count/e/tag`, and `s_valid/ready/data/last`.

The block stream's metadata channel connects directly to the queue's input
metadata channel. Its payload channel connects directly to the queue input byte
channel. The queue output metadata/payload channels and handshakes are exposed
verbatim. The wrapper adds no bypass, bridge, aggregate counter, retry,
auto-abort, fault waiver, or combinational suppression of child error pulses.

The following public diagnostics are direct aliases:

- `stream_level`, `stream_filling`, and all five `stream_stat_*` values from
  `deepeye_block_stream`.
- `queue_level`, `queue_receiving`, `queue_faulted`, `queue_fault_event`,
  `queue_fault_code`, and all five `queue_stat_*` values from
  `deepeye_encoded_frame_queue`.

Raw and encoded stages therefore remain separately observable. No wrapper
counter can credit one admitted block twice.

## Bounded storage

The composition adds no storage of its own. Dependency storage is finite:

- Block-stream raw slots: two banks of 128 x 16 bits = 4096 bits total, plus
  two descriptors (status, error, count, E, and tag).
- Encoder inside the block stream: `x_mem` 128 x 16 bits, `z_mem` 127 x 17
  bits, `byte_mem` 256 x 8 bits, and its finite arithmetic/control registers.
- Encoded-frame queue: two payload banks of 256 x 8 bits = 4096 bits total,
  plus two descriptor records containing status, fault, metadata-done, tag,
  error, count, E, raw, k, valid-bit count, and byte count.

There is no unbounded FIFO and no added packet buffer.

Those payload/sample arrays total 14,447 bits, excluding descriptors, counters,
and arithmetic/control registers. Core arrays duplicate bounded in-flight work;
they are not extra admitted-block capacity. At most four unique blocks can be
resident in the two raw plus two encoded reservations. While an encoded frame
is being received, its raw and encoded reservations refer to the same block.

## Reset, cancel, backpressure, and faults

The shared synchronous active-high `rst` and `cancel` reach both children.
Each child retains its own reset priority and cancel behavior. The wrapper does
not reinterpret either signal.

The queue can hold two complete encoded frames. Its input metadata and payload
ready signals propagate into the block stream, so queue fullness reaches the
frontend through the unchanged two-slot block stream. Accepted older frames may
drain while the queue is faulted; no new queue input is admitted. Fault state
and pulses remain directly visible, and no hidden recovery is introduced.

## Author evidence boundary

The testbench drives only public wrapper ports. It covers valid count limits
1/2/127/128, invalid counts 0/129/255, E values 0/1/2/4/8, unsupported E,
zero/ramp/peak/extreme/noise/RAW-fallback data, duplicate tags, invalid final
strobes, ordered success/error frames, frontend fill against a full stalled
queue, metadata/byte stalls, final-retirement credit boundaries, and reset or
cancel in bounded pipeline states.

ModelSim behavioral simulation is evidence for the authored digital fixture
only. Synthesis, implementation, timing, CDC/RDC signoff, physical board,
All29, B01, B03, B04, B06, R03, full product, and system results remain
`not_run`.

## Recovery and reproduction

The terminal Flash attempt produced three incomplete files, preserved byte for
byte under `author/recovery-inputs/` with its transfer record. The original
wrapper incorrectly assigned both internal ready signals from external ready
inputs as well as connecting the queue outputs. This recovery removes exactly
those two assignments. Only the queue drives `stream_meta_ready` and
`stream_m_ready`. The dependencies remain unchanged.

Run from the existing worktree with the existing Python runtime:

```powershell
& D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -X utf8 tools/stream/run_buffered_block_stream.py --attempt 1
```

Each numbered attempt is created exclusively and never overwritten; only
attempts 1 through 3 are permitted. Vendor processes run hidden, with a
60-second process timeout and a 3,000,000-clock testbench watchdog. Raw stdout,
stderr, exit codes, commands, tool versions, source snapshots, and generated
expectations are retained in the attempt directory.

The fixture uses public ports only. Its expected metadata and bytes reuse the
published codec reference and verify its published hand/noise/step vectors;
this is author reference reuse, not an independent acceptance oracle. Per-cycle
checks verify unique residency, raw/encoded counter conservation, reset/cancel
gating, and stalled outputs. Each admitted block gets an identity separate from
its tag and exactly one output, cancellation, or reset terminal event. Encoding
interruption is located by the sealed raw block, zero queue admissions, and a
fixed early elapsed interval; no private encoder state is inspected.

The queue fault-injection path and counter saturation are not exercised through
this legal producer composition. Direct fault/status aliases are retained; a
faulted dependency requires caller recovery according to its existing contract.
No negative timing finding in separately owned OOC work is repaired or waived
by this behavioral author fixture.
