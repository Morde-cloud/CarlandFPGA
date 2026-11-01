# Nominal uplink slot gate candidate

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-B04-UPLINK-SLOT-GATE-SOURCE-20261030-89`.

Status: `SOURCE_COMPLETE_UNEXECUTED`. This directory is a software source
candidate only. It was not compiled, imported, simulated, synthesized, timed,
or run. `vectors_UNEXECUTED.json` contains manual oracles, not observed PASSes.

## Boundary

`deepeye_nominal_uplink_slot_gate_candidate.sv` is a finite SystemVerilog
wrapper around the existing, unchanged Q012 scheduler. It adds one-token
nominal slot admission, exact descriptor ownership, arithmetic time checks,
sticky fault handling, and gating of both Q012 ingress and its held output.

The original Q012 source is not copied or edited. Compile the original file
and this wrapper together, with `deepeye_q012_scheduler` visible:

- `competition/deepeye/fpga/transport/deepeye_q012_scheduler.sv`
- bytes: 11386
- SHA-256: `d7cfe903ca6bb904fbf21f5207eac694638741f02bd48dd0ff3785becf97e740`

The wrapper uses Q012 defaults explicitly: 64-bit descriptor, 16-bit credit,
depth 4, and 32-bit statistics. The unchanged Q012 remains the only queue and
arbiter. There is no second queue, eviction path, retry engine, or scheduler in
this candidate.

## Selected interface behavior

- One active token and at most one queued descriptor are allowed.
- Bind is accepted only after an explicit arm rising edge while enabled, after
  a sampled `token_valid=0`, and with Q012 empty and downstream quiescent.
- Binding latches the profile, role, exact descriptor, class, cost, start time,
  and token identity, then consumes `used_roles` and the monotonic token ID.
- Credits are loaded once, after binding, through Q012 `credit_load_*`; the
  loaded value is exactly `token_cost`. Ingress is not enabled until that
  handshake is complete.
- Exactly one ingress descriptor may handshake. Its 64-bit descriptor, 2-bit
  class, and 16-bit cost must equal the bound values. A mismatch while a token
  is active is `FAULT_IDENTITY`; inactive ingress is never accepted.
- Q012 may select and hold an offer before its slot. The wrapper forces outer
  `out_valid=0` until the exact slot. A held offer must still match all bound
  descriptor/class/cost fields, or `FAULT_IDENTITY` is latched and Q012 is
  flushed.
- A fire requires `now_ns == start`, a quiescent downstream, `out_ready=1`,
  enabled/armed state, no cancel, no sticky fault, and the exact held offer.
  No late catch-up is permitted. At `now_ns > start` without fire, or at
  `start` when no exact offer is ready, the sticky MISSED_SLOT fault occurs.
- `forward_pulse` means only that the one descriptor handshake left this
  wrapper. It is not packet completion, UART byte completion, host ACK,
  controller success, or an action/safety result.

## Nominal uplink roles and exact costs

These local role IDs are not a new wire ABI. No downlink CONTROL or CONFIG
frame is emitted by this PL uplink gate.

| ID | role | class | cost | FAST offset ns | STRESS offset ns |
|---:|---|---:|---:|---:|---:|
| 1 | EVENT | 0 | 20 | 0 | 0 |
| 2 | TELEM | 1 | 32 | 35000000 | 700000000 |
| 3 | ACK_PRIMARY | 0 | 34 | 255000000 | 3100000000 |
| 4 | STATE3D | 1 | 34 | 305000000 | 4300000000 |
| 5 | ACK_RETRY | 0 | 34 | 410000000 | 6550000000 |
| 6 | CONFIG_ACK | 0 | 32 | 405000000 | 6550000000 |
| 7 | EVENT_RETRY | 0 | 20 | 365000000 | 5500000000 |

`EVENT_RETRY` is uplink even though it reuses the base `retry_control` slot
name. The downlink CONTROL/CONFIG bytes are never charged as B uplink here.
No Q2/TRACE opportunity is invented from unused roles.

Profile 1 is FAST: 9600 baud, 10 line bits/byte, 500000000 ns window, and
40000000 ns guard. Profile 2 is STRESS: 300 baud, 10 line bits/byte,
8000000000 ns window, and 200000000 ns guard. `wire_ns` is the exact ceiling
constant for `cost*10*1000000000/baud`.

Grant mask bits below 13 must be clear. Bit 13 requires bit 15 set and bit 14
clear. ACK_PRIMARY requires bit 15. ACK_RETRY requires bits 15+13, bit 14
clear, and `first_ack_ok=0`. CONFIG_ACK requires bit 14 with bit 13 clear.
EVENT_RETRY requires bits 13 and 14 clear. ACK_RETRY, CONFIG_ACK, and
EVENT_RETRY are mutually exclusive in one window in either arrival order.
`first_ack_ok` is a pre-bind planning input, not evidence of an actual ACK.
Changing an admitted plan requires cancel/bind-again behavior; it is not an ACK.

## Time, window, identity, and faults

All supplied time and ID fields are nominal uint63 values carried in 64 bits.
Any MSB set is rejected. Sums use checked 65-bit intermediates and may not
exceed `2^63-1`.

For a selected row:

- `start_ns = window_origin_ns + role_offset_ns`
- `wire_ns = ceil(cost * 10 * 1000000000 / baud)`
- `frame_end_ns = start_ns + wire_ns`
- `window_end_ns = window_origin_ns + window_ns`
- bind requires `now_ns < start_ns`
- bind requires strict `frame_end_ns < deadline_ns`
- bind requires `frame_end_ns + guard_ns <= window_end_ns`

The deadline is never extended. A same-origin bind reuses `used_roles`. A new
origin must be at least the prior window end, within uint63, aligned to an
integer multiple of the same profile window, and cannot change profile before
reset. A new origin clears only the role mask. IDs must be nonzero and strictly
greater than the last bound ID; there is no wrap.

Once a fault or cancel/disable destroys an admitted context, the same window
cannot bind again. Only a strictly new, valid window may bind after clear.
Sticky fault codes are:

| code | meaning |
|---:|---|
| 1 | TOKEN_INVALID |
| 2 | IDENTITY |
| 3 | MISSED_SLOT |
| 4 | TIME_REGRESSION |
| 5 | CANCELLED_OR_DISABLED |
| 6 | BUSY_ARM |
| 7 | REPLAY_OR_WINDOW |

A fault disarms, invalidates the token, forces outer ingress and output invalid,
and holds Q012 flush. Q012 flushes all classes and its held offer on the next
synchronous flush edge; `flushed_count` is the public, saturating Q012 count.
No retry, auto-arm, or stale-valid replay is generated.

`clear_fault` is accepted only when no token is active, `token_valid=0`, Q012 is
empty, and downstream is quiescent. It clears the sticky state but does not arm,
does not restore a consumed ID/role, and does not reopen a closed window.
Arm is edge-sensitive: after reset, fault clear, or any re-arm, drive `arm` low
for a sampled cycle and then raise it. A level left high is not a new edge.

Reset is state-destructive. It clears identity, role/window context, Q012
contents, credits, and Q012 statistics. It generates no ACK and cannot recover
unknown or already-forwarded work. The external host must treat outcomes as
UNKNOWN and obtain a new authoritative BOOT.

## Explicit non-goals and unsupported paths

- No physical GAIN command, analog gain effect, PC_DIRECT mode, or mapping of
  either to HIL STATE3D is implemented or claimed.
- No downlink CONTROL/CONFIG emission, UART serializer, USB timing closure,
  partial-byte retirement, packet ACK, or host application completion is here.
- No ADC, calibration, thresholding, measurement, pin assignment, clock
  constraint, 100 MHz target, synthesis result, timing result, or board result
  is provided.
- No BOOT authentication, Root/C/world authority, grant authenticity, trusted
  time source, profile admission, capture proof, or cross-node wire evidence is
  provided.
- No old failed suite is rerun and no historical nonzero is promoted.

## Profile identity limitation

The exact canonical A-profile pin accepted by this candidate is 14212 bytes,
SHA-256 `b7abdd50d04337c4526ae43de6912c9b7f05e9803e79a519dd4fd7528edc3b46`,
computed after excluding only top-level `host_inference`. The source document
is `software_candidate_runtime_not_run` and has
`hardware_enable_eligible=false`.

Its 35 null leaves still include frame-layout/interface digests, four channel
quantity/unit/conversion/calibration sets, acquisition-profile calibration and
shared-scaling links, and USB/frame-serial/clock/rate/tick/dispatch/holdover
identities. Equality of this hash therefore proves none of those measurements,
BOOT authenticity, payload content, grants, clocks, capture, or real wire timing.

The immutable H01-H15 requirements hash is
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804` at pin
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`; frozen implementation source is
`1011259415a0916054eb580687612580bc1e5f09`. This candidate neither weakens nor
accepts those product requirements.

## Unexecuted vectors

`vectors_UNEXECUTED.json` records 47 distinct manual scenarios with integer ns
fixtures, exact timing rows, and expected source-level outcomes. They cover all
14 FAST/STRESS nominal role rows, first-ACK suppression, config/retry exclusion,
role/class/cost/hash checks, ingress and held-offer matching, arm/cancel/disable,
clear/reset, future-window alignment, ID monotonicity, uint63 overflow, late
bind, backpressure timeout, and replay prohibition. Nothing in that file is an
executed result or a formal/simulation PASS.
