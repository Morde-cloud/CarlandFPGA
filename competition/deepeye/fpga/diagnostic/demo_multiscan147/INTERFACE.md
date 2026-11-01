# Proposed `deepeye_demo_multiscan147` interface

Status: **SOURCE_ONLY / UNEXECUTED diagnostic proposal**. The parent main owns
architecture and acceptance. Machine A owns any build, AXI map, pins, board or
physical use. This file defines only the pure-data RTL seam implemented by
`deepeye_demo_multiscan147.sv`.

The exact 50 MHz / 1 Mbaud point is diagnostic, not the final 100 MHz gate.
No source field below is an authentication result, Root receipt, current-clock
proof or motion authorization.

## Parameters

|Name|Default|Constraint|
|---|---:|---|
|`CLOCK_HZ`|`50000000`|Must be exactly 50,000,000. Wrong values gate the path and trip a simulation-time guard.|
|`BAUD`|`1000000`|Must be exactly 1,000,000. 8N1. `tx` idles high.|
|`STAT_W`|`32`|Passed to the unchanged UART/transport statistics cores; this wrapper does not expose those counters.|

## Ports

### Clock, reset and owner control

|Port|Dir|Width|Meaning|
|---|---|---:|---|
|`clk`|in|1|50 MHz source clock.|
|`rst`|in|1|Synchronous active-high reset; flushes local state and all reused downstream state.|
|`cancel`|in|1|Synchronous active-high abort. No automatic replay.|
|`enable`|in|1|Owner enable. Withdrawal aborts accepted work. Restoring enable does not ARM.|
|`arm`|in|1|Rising-edge request. One accepted edge captures the complete batch configuration. Held ARM is not a second arm.|
|`arm_ready`|out|1|High only when a fresh ARM can be accepted.|
|`armed`|out|1|Configuration is latched and input acceptance is active.|
|`batch_done`|out|1|Set only after four successful frame retirements. No automatic rearm.|
|`busy`|out|1|Collector, egress or output work is active/offered.|
|`quiescent`|out|1|No local batch work remains. Quiescence is not success, authentication or physical STOP.|

`arm` is sampled only on a low-to-high edge. If `arm_ready` is low, that request
has no effect. Configuration inputs are ignored until an accepted ARM.

### Owner configuration, captured once

|Port|Dir|Width|Range / rule|
|---|---|---:|---|
|`cfg_session`|in|32|Copied exactly into all four TRACE payloads.|
|`cfg_epoch`|in|8|Copied exactly into the wire header and payload.|
|`cfg_base_frame_seq`|in|16|Must be `<= 0xfffc`; frame sequences are `base + 0..3` and must not wrap.|
|`cfg_origin_qpc_ns`|in|63|Unsigned QPC origin. Full value remains in the needed companion association; it is not authenticated.|
|`cfg_tag`|in|32|Must be nonzero. Input scan tag and aggregate tag must equal it. The tag is association metadata, not a wire authentication token.|

A failed metadata ARM sets `refused` with code 10 or 11. It emits no frame.
A later valid ARM may start a new batch after any explicit cleanup required by
the failure mode.

### Ordered raw scan input

The producer presents exactly 12 records for this diagnostic batch: three
four-lane scans in order. One valid/ready handshake carries one lane.

|Port|Dir|Width|Contract|
|---|---|---:|---|
|`s_valid`|in|1|Producer data valid until `s_ready`.|
|`s_ready`|out|1|High only when the collector is ready and wrapper-level status/tag/scan-QPC gates pass. The unchanged aggregate is the sole storage/acceptance authority and may still refuse a presented channel/sequence/quality/stride violation; such a record is never stored or relabelled.|
|`s_channel`|in|2|Expected lane number `0,1,2,3` in each scan. Wrong order is refused by the collector.|
|`s_data`|in|16|Original uint16 value, copied unchanged. Zero is a valid value.|
|`s_acq_qpc_ns`|in|64|Original acquisition QPC. Bit 63 must be zero. All four lanes in one scan must carry the same value.|
|`s_quality`|in|8|Opaque caller-supplied quality byte. Must be constant per channel across the three scans. It is not encoded by this wire path.|
|`s_tag`|in|32|Must be nonzero and equal `cfg_tag`.|
|`s_native_first_seq`|in|32|First native sequence for this scan. Scan 0 supplies the batch base. The 12-record progression is the base plus `0..11`, without uint32 wrap.|
|`s_native_last_seq`|in|32|Must equal `native_first_seq + 3` without wrap.|
|`s_semantics_valid`|in|1|Caller-supplied declaration. Must be 1 for acceptance. It is not authentication.|
|`s_fresh`|in|1|Must be 1 for acceptance. Freshness is not inferred or transported on the wire.|
|`s_sample_valid`|in|1|Must be 1 for acceptance.|
|`s_held`|in|1|Must be 0. Held input is refused; it is never rewritten as fresh.|
|`s_saturated`|in|1|Must be 0. Saturation is refused; it is not silently cleared.|
|`s_source_fault`|in|1|Must be 0. A source fault is refused; it is not silently cleared.|

For this diagnostic wrapper only, held/saturated/source-fault records are
unsupported. The unchanged aggregate's broad held encoding is not activated.
All accepted records are therefore fresh, valid, non-held, non-saturated and
non-fault; the downstream constant status flags reflect that acceptance gate,
not newly invented evidence.

### Frame result and backpressure

|Port|Dir|Width|Meaning|
|---|---|---:|---|
|`result_valid`|out|1|One result per channel frame. Held stable while `result_ready` is low.|
|`result_ready`|in|1|Consumer acknowledgement. Deassertion must not be used as an implied success.|
|`result_error`|out|3|Sample only with `result_valid`. Zero means the reused chain reported a successful encoded/transmitted frame. Nonzero is a real downstream error.|
|`result_bytes`|out|6|Sample only with `result_valid`. Count of wire bytes actually admitted to UART for that frame, including the 14-byte outer header/CRC.|
|`frames_retired`|out|3|Successful result handshakes in this batch, 0 through 4.|
|`accepted_lanes`|out|4|Current collector count, not an optimistic handshake count. It reaches 12 when the collector is full and returns to zero when the aggregate disarms after the fourth retirement.|

`result_valid` indicates local frame completion/backpressure, not host receipt,
board freshness, Root acceptance or an ACK/action retirement.

### Refusal and abort status

|Port|Dir|Width|Meaning|
|---|---|---:|---|
|`refused`|out|1|A configuration, input, collector or egress association refusal is present.|
|`refusal_code`|out|4|Reason code below; zero when no refusal. Sticky until reset, explicit cleanup/ARM, or a control action that clears it.|
|`aborted`|out|1|Sticky indication that accepted/in-flight work was discarded by a control abort or downstream internal abort.|
|`abort_code`|out|2|`0=none`, `1=cancel`, `2=enable withdrawal`, `3=downstream/internal abort`. Sticky until reset or a new accepted ARM.|

Refusal codes:

|Code|Source|Meaning|
|---:|---|---|
|0|wrapper|No refusal.|
|1|unchanged aggregate|Unsupported semantic/valid/held status.|
|2|unchanged aggregate|Wrong channel or zero/changed tag.|
|3|unchanged aggregate|Native sequence/order/overflow failure.|
|4|unchanged aggregate|uint63, origin or relative-microsecond range failure.|
|5|unchanged aggregate|Per-channel quality changed between scans.|
|6|unchanged aggregate|QPC stride is nonpositive, irregular, non-whole-microsecond or out of the supported range.|
|7|unchanged aggregate|Seal requested before a complete 12-record collection.|
|8|unchanged aggregate|Reserved/unused by this composition.|
|9|unchanged aggregate|Busy collector rearm (not issued by this wrapper's normal one-ARM path).|
|10|wrapper|`cfg_base_frame_seq + 3` would wrap.|
|11|wrapper|Configuration tag is zero.|
|12|wrapper|Input tag does not equal the captured nonzero tag.|
|13|wrapper|Input freshness/semantic/valid/held/saturated/source-fault combination is unsupported.|
|14|wrapper|The four lanes of one scan do not carry the same acquisition QPC.|
|15|wrapper|Egress origin/QPC/quality/frame association failure, or a nonzero reused-chain result error.|

A refused record is never silently dropped and then relabelled as accepted. An
asserted unacceptable record is backpressured and raises refusal. After the
12th accepted record, further `s_valid` remains backpressured; it is not a
replacement record. A partial frame may already have left `tx`; partial output
is invalid and is never replayed or rolled back.

### UART TX and upload RX boundary

|Port|Dir|Width|Meaning|
|---|---|---:|---|
|`tx`|out|1|8N1 UART output at the exact `BAUD` parameter; high when idle.|
|`rx_async`|in|1|Asynchronous serial input to the unchanged pinned `deepeye_uart_rx`. No pin/wire assignment is made here.|
|`up_valid`|out|1|One received byte is offered at the upload boundary.|
|`up_ready`|in|1|Consumer acceptance. The receiver is single-slot; it is not an elastic FIFO.|
|`up_data`|out|8|Received byte, opaque at this interface.|
|`up_busy`|out|1|Receiver is sampling a character.|
|`up_framing_error`|out|1|Pulse for a UART stop/framing failure.|
|`up_overrun`|out|1|Pulse when the single output slot is not retired before a following byte completes.|
|`up_false_start`|out|1|Pulse for a rejected false start.|

The upload path carries no invented companion schema, CRC acceptance, file
structure or host acknowledgement. A host/adaptor must add any framing,
schema validation, buffering and association policy. `cancel` or enable
withdrawal also cancels the receiver, discards its slot and requires the line
to be observed high again before another start. There is no automatic replay.

### Wire mapping produced by the reused chain

The four channel frames are emitted in channel order 0,1,2,3:

- outer wire: magic `a5 5a`, version `03`, type `e4`, length, epoch, sequence,
  relative tick, payload, CRC-16;
- payload revision `02` is the pinned private diagnostic profile emitted by
  the reused 1 us adapter;
- session, channel, native first index, relative first tick, index stride,
  tick stride, count and code bytes come from the selected source contract;
- for an accepted batch, the wrapper supplies index stride 4; it does not
  derive a replacement from a host selector;
- the first index is the original batch base native sequence plus channel;
- the relative tick is computed from the original QPC and captured origin;
  no current-clock rebasing is performed;
- the full uint63 origin, nanosecond remainder, acquisition/source QPC, native
  tag, fresh flag and opaque raw quality are not present in the wire and must
  remain in the companion/source association.

The reused block encoder chooses RAW or Rice. This interface does not force a
mode. The TB measures the selected mode and exact frame byte count on the
later run.

### Lifecycle

1. Reset/hold flushes local and reused state; ARM is ignored.
2. One low-to-high `arm` edge while `arm_ready=1` captures all five
   configuration fields. A bad base sequence/tag is refused with no batch.
3. Exactly 12 acceptable lane handshakes fill the collector in three scans.
   Inputs remain subject to tag/status/QPC/order/sequence/quality/stride checks.
4. Four channel blocks are offered in order to the unchanged TRACE/UART chain.
   Each result is held until `result_ready`; success retires one frame.
5. `batch_done` appears only after four successful retirements. It does not
   rearm; a fresh ARM edge is required for another batch.
6. `cancel` or `enable=0` aborts accepted/in-flight work, reports `aborted`
   with cause 1 or 2, clears the local transaction, and does not replay.
   Refusal can additionally produce cause 3 when the downstream transaction
   is actually aborted.
7. `quiescent` may be true with a refusal present. It is local inactivity, not
   acceptance or physical safety.

### Explicit non-gaps and gaps

Not present by design: no callback/verified-boolean physical path, no
authentication bit, no fabricated current flag, no hardcoded session/epoch/
sequence/tag, no new compressor, no new register address, no board pin.

Still required by the eventual integrator (A owns the choice):

- clock/reset/CDC and UART pin/electrical integration;
- AXI/AXI-Stream/register adapter and host software, with any address map A
  chooses rather than one invented here;
- Host103 `TraceSequence`/pure-staging mapping, if required, plus any A-owned
  producer/custody envelope; none is invented by this block;
- a FIFO or explicit `up_ready` policy for the upload byte stream;
- companion/source-association transport and validation, including origin,
  exact remainder, full QPCs, quality mapping, lineage and operation identity;
- 100 MHz/final timing, board, ADC/BOOT/motion, both H12 paths and all final
  accuracy/latency gates;
- physical START and acceptance by A. This proposal is not a source or build
  permission.
