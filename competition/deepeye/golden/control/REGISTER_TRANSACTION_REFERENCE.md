# B07 offline register transaction reference

Task `DEEPEYE-IMPLEMENTATION-20261014` / version `1`.
Work `B-REGISTER-TRANSACTION-20261019-10-v1`.
Operation `B-DEEPEYE-REGISTER-TRANSACTION-20261019-10`.
Base `433db2a82854a669778eb8c3cd35c309623a087e`.

Contract `DEEPEYE-HUMAN-LOCK-20261014` revision 1, H01-H15.
Requirements-only canonical SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Lock commit `f5989cd5defce561f9ba98e6b18fc2682945f0a2`.
Design commit `1011259415a0916054eb580687612580bc1e5f09`.
B07 owner-decision input SHA256
`5cb049b28da33eea74e8a30365962d731b3f2d198065086daab1998ff747e116`.

## Scope and non-claims

`register_transaction_reference.py` is a deterministic, offline Python
transaction reference for the reviewed B07 candidate register layout.  It
preserves the 29 source rows, access classes, reset proposals and
command-priority rules from the B07 descriptor.  It is not RTL, a CDC/RDC
model, an AXI/WSTRB implementation, a driver, a public register ABI, a board
result, a calibration or physical-measurement authority, or acceptance
evidence.  A alone owns the final ABI and the physical board.

`hardware_enable_eligible` and `movement_authorized` are always `False`,
including for explicitly named software fixtures.  No default real domain is
provided.  There is no service, credential, network, queue, board or
controller dependency.

The reviewed B07 layout is the baseline.  API details below are B fixture
proposals pending A's complete ABI freeze; they add no authority and do not
change A's decisions.  The unresolved items are listed explicitly at the end
of this document rather than silently filled.

## Module and API

The module exports `RegisterTransactionModel`, `CaptureTicket`,
`RegisterTransactionError`, the task/source constants and the authority
constants.  `RegisterTransactionError` subclasses `ValueError` and carries a
fixture-local `.code` string.  Rejections never expose partial accepted state.

`RegisterTransactionModel(domain=None)` creates an unconfigured model when
`domain` is `None`.  Its public methods are:

| Method | Result and rule |
| --- | --- |
| `write(addr, data, wstrb=15)` | Returns `None`. Validates address and access first, then integer type/range for data and strobe. A known writable register with `wstrb=0` is a no-op after validation. STOP side effects precede a reserved-bit error. |
| `read(addr)` | Returns an `int`. Write-only command registers return `0`. `0x2c` always rejects. No read is a command acknowledgement. |
| `reset()` | Returns `None`. Counts as a reset event, advances the internal generation, clears active/shadow/pending state, gates, CDC flags, queue counters, snapshot bank/latch and tickets, and retains anti-reuse pair/high-water tracking. |
| `set_context(context)` | Returns `None` or rejects. Stores an immutable tuple. An identical context is a no-op. Any change revokes pending CONFIG, capture tickets and latch coherence. |
| `set_fixture_gates(enable, recovery)` | Returns `None`. Requires exact `bool` values. These are software fixture gates only. |
| `set_cdc(online, busy)` | Returns `None`. Requires exact `bool` values. Loss of online-and-not-busy eligibility revokes current publication, latch coherence, tickets and, when snapshot state existed, pending CONFIG. |
| `set_queue(used, overflow_increment=0, merged_increment=0)` | Returns `None`. Requires a fixture domain. Counters saturate at 16 bits. |
| `raise_fault(flags)` | Returns `None`. Latches a u8 fault code, forces stopped/disabled and revokes CONFIG history and snapshot state. |
| `block_boundary(block)` | Returns `None`. Publishes a matching pending CONFIG once, or does nothing when no matching pending request exists. A matching but stale request is discarded and rejected. |
| `begin_capture(batch_seq)` | Returns a model-owned opaque `CaptureTicket`. Requires domain, context, active complete CONFIG and eligible CDC. |
| `complete_capture(ticket, values)` | Returns `None` or rejects. Validates the ticket and all values before any bank update. |
| `read_snapshot(interleave=None)` | Returns a detached dictionary or rejects. Requires a coherent current latch. `interleave(offset, model)` is a test hook called after each bank word read. |
| `inspect()` | Returns detached diagnostic dictionaries. It is not a command acknowledgement and cannot grant authority. |

`hardware_enable_eligible` and `movement_authorized` are read-only properties
that always return `False`.  All returned dictionaries, tuples and ticket
objects are detached or opaque; caller mutation of an input container cannot
change model state.

## Fixture domain

`domain` is either `None` or an exact mapping with exactly these keys:

| Key | Rule |
| --- | --- |
| `fixture_id` | Non-empty string. |
| `identity` | u32 software identity. |
| `rate_codes` | Non-empty unique list/tuple of u8 values. |
| `sensor_profiles` | Non-empty unique list/tuple of u8 values. |
| `motion_profiles` | Non-empty unique list/tuple of u8 values. |
| `apply_blocks` | Non-empty unique list/tuple of u8 values. |
| `queue_capacity` | u16. |
| `clock_id` | Non-empty fixture string. |

Numeric zero is allowed inside a fixture list when explicitly supplied.  The
reset profile value zero remains unconfigured until an explicit complete
CONFIG apply.  A validated immutable copy is stored; changing the caller's
containers does not alter the model.  Every domain is a named software
fixture, not a real device identity.

## Context and anti-reuse

`context` is an exact mapping with exactly these keys:

| Key | Rule |
| --- | --- |
| `session` | u32. |
| `boot_digest` | Exactly 64 lowercase hexadecimal characters. |
| `config_epoch` | u8. |
| `control_epoch` | u8. |
| `request_seq` | u16. |

The `(session, boot_digest)` pair is the anti-reuse identity.  At most 64
distinct pairs are retained.  A pair that was previously used cannot be
re-entered after leaving it; exhaustion fails closed.  Within one pair,
`config_epoch`, `control_epoch` and `request_seq` must not decrease.
`request_seq` may restart only when `control_epoch` increases.  No wire-width
wrap is accepted.

`set_context` revokes and discards pending CONFIG, outstanding capture tickets
and latch coherence on any change.  A rollback is rejected without mutation.
The internal generation is a monotonic Python integer; it is never reset by
`reset()` and never projected to wire bits.

The model owns CONFIG epoch progression: one successful block-boundary apply
increments `config_epoch` once.  Apply at epoch 255 is rejected.  The apply
request contains no caller-authored epoch field.  This progression is a
fixture proposal pending A's complete ABI approval.

## Bus, addresses and status

Only the 29 aligned 32-bit rows at `0x00..0x70` exist.  Unknown, unaligned,
negative and oversized addresses, writes to read-only registers, and any
access to `0x2c` reject.  `0x2c` rejects even with `WSTRB=0`.

| Offset | Name | Access | Reset | Fields |
| --- | --- | --- | --- | --- |
| `0x00` | identification | RO | domain-dependent | Fixture `identity`; read rejects when no domain exists. |
| `0x04` | abi_version | RO | `3` | Fixture proposal, not a frozen ABI claim. |
| `0x08` | control | WO command | `0` | STOP[0], CLEAR_FAULT[1], ENABLE[2], LATCH[3], RELEASE[4]. Readback `0`. |
| `0x0c` | status | RO live | `0x00000001` | See status table. |
| `0x10` | shadow_configuration | RW shadow | `0` | threshold[15:0], apply_block[23:16]; mask `0x00ffffff`. |
| `0x14` | apply_request | WO command | `0` | request_seq[15:0]; full-word strobe; high 16 bits reserved. Readback `0`. |
| `0x18` | sample_rate | RW shadow | `0` | rate_code[7:0]; mask `0x000000ff`. |
| `0x1c` | error_bound | RW shadow | `0` | E[7:0] in `{0,1,2,4,8}`; mask `0x000000ff`. |
| `0x20` | profile | RW shadow | `0` | sensor_profile[7:0]; mask `0x000000ff`. |
| `0x24` | queue_status | RO live | `0` | used_entries[15:0], capacity_entries[31:16]. |
| `0x28` | overflow_merge | RO live | `0` | overflow_events[15:0], merged_events[31:16]. |
| `0x2c` | reserved | NO ACCESS | n/a | Rejects every read/write, including zero strobe. |
| `0x30` | applied_yaw | RO snapshot | `0` | Signed 32-bit two's-complement yaw. |
| `0x34` | applied_speed | RO snapshot | `0` | speed_code[7:0]. |
| `0x38` | applied_request | RO snapshot | `0` | request_seq[15:0], control_epoch[23:16], request_type[31:24] (`0x0e` for motion). |
| `0x3c` | session | RO snapshot | `0` | Snapshot session. |
| `0x40` | sample_tick_word0 | RO snapshot | `0` | sample_tick low 32 bits. |
| `0x44` | sample_tick_word1 | RO snapshot | `0` | sample_tick high 32 bits. |
| `0x48` | capture_period0 | RO snapshot | `0` | yaw_capture_period low 32 bits. |
| `0x4c` | capture_period1 | RO snapshot | `0` | yaw_capture_period high 32 bits. |
| `0x50` | capture_sequence | RO snapshot | `0` | wire_capture_seq[15:0]. |
| `0x54` | capture_quality | RO snapshot | `0` | yaw_valid[0], pitch_valid[1], speed_valid[2], all_periods_valid[3]. |
| `0x58` | gain | RO snapshot | `0` | applied_gain_code[7:0]. |
| `0x5c` | measured_ratio | RO snapshot | `0` | measured_ratio_q8_8[15:0]. |
| `0x60` | applied_pitch | RO snapshot | `0` | Signed 32-bit two's-complement pitch. |
| `0x64` | pitch_capture_period | RO snapshot | `0` | Full 32-bit pitch period. |
| `0x68` | speed_capture_period | RO snapshot | `0` | Full 32-bit speed period. |
| `0x6c` | motion_profile_id | RO snapshot | `0` | motion_profile_id[7:0]. |
| `0x70` | last_observed_sequence | RO snapshot | `0` | last_observed_sequence[15:0]. |

Status is masked to `0x00ff07ff`.  Initial status is `0x00000001`.

| Bit | Name | Meaning in this fixture |
| --- | --- | --- |
| 0 | stopped | Set by reset, STOP and fault. |
| 1 | fault_latched | Set by `raise_fault`; cleared only by an eligible CLEAR_FAULT. |
| 2 | snapshot_latched | A LATCH has occurred and RELEASE/reset has not cleared it. It can remain set while coherence is invalid. |
| 3 | snapshot_coherent | Current latch is coherent and usable by `read_snapshot`. |
| 4 | snapshot_available | A current eligible publication or coherent latch exists. It is not an authority claim. |
| 5 | cdc_busy | Fixture CDC busy flag. |
| 6 | cdc_online | Fixture CDC online flag. |
| 7 | config_dirty | Staged configuration differs from active, or staged fields exist with no active configuration. |
| 8 | config_pending | A validated CONFIG apply request awaits its block boundary. |
| 9 | gain_ratio_valid | Current coherent latch carries the supplied fixture ratio-valid flag; an unlatched publication leaves this bit clear. |
| 10 | enabled | Fixture ENABLE state. Never a hardware-authority claim. |
| 16..23 | fault_flags | Latched u8 fault code. |

Bits 11..15 and 24..31 are reserved and read as zero.

## Control commands

Byte-zero STOP has priority.  If byte 0 is strobed and bit 0 is set, the model
stops, disables, advances the generation and revokes snapshot/latch state,
pending CONFIG and outstanding capture tickets.  No other command executes in
that write.  Defined command bits accompanying STOP are dominated silently.
If any strobed reserved command bit is set, the error is raised only after the
STOP side effects.

Other nonzero commands require `WSTRB=0x0f`, no reserved bits and exactly one
defined command bit.  An all-zero masked command is a no-op.

| Command | Fixture rule |
| --- | --- |
| CLEAR_FAULT | Requires stopped and not enabled, plus the recovery fixture gate. Clears the fault and never enables. |
| ENABLE | Requires domain, context, active complete CONFIG, enable fixture gate, CDC online and not busy, and no latched fault. |
| LATCH | Requires an eligible current publication, no outstanding latch (including an incoherent historical one), matching context/generation, and CDC online and not busy. A second LATCH revokes existing coherence and rejects without replacing the bank. |
| RELEASE | Advances the generation, clears the latch and coherence, discards pending CONFIG, and prevents stale completion resurrection. It does not make any bank word valid. |

## CONFIG shadow, apply and boundary

Shadow writes use byte strobes.  Unstrobed bytes are ignored.  The complete
merged word is validated before an atomic shadow update; a rejected write
leaves the prior shadow word unchanged.  `0x10` masks to 24 bits, and
`0x18`/`0x1c`/`0x20` mask to 8 bits.  Initialization of all four shadow
registers is tracked separately from their reset zero values.  E must be one
of `{0,1,2,4,8}`.  Rate, profile and apply_block values must belong to the
explicit fixture domain.

`apply_request` is a write-triggered full-word command, not a no-op for
sequence zero.  The low 16 bits are the request sequence; the high 16 bits are
reserved.  A request requires all four shadow registers initialized, a
complete valid payload, a domain and context, `config_epoch < 255`, and no
conflicting pending request.  The accepted whole payload and original context
are captured immutably; later shadow writes do not alter the pending payload.

The request sequence is strictly increasing per session/BOOT pair.  An
identical sequence, payload and original context is a duplicate only while
that request is pending or was completed without revocation; a duplicate does
not reapply or renew.  Older or conflicting sequences reject, including after
STOP or reset.  A pending request discarded by revocation cannot be
resurrected by a later matching block boundary.

Only `block_boundary` with the payload's `apply_block` can publish.  The
current context and generation must still match the accepted request.  One
successful boundary publishes all active fields atomically and increments
`config_epoch` once.  Other blocks are no-ops.

## Queue fixture

`set_queue` requires a fixture domain.  `used` must be at most the domain's
`queue_capacity`; each counter is a saturating 16-bit value.  An unconfigured
queue reads zero and `inspect()['queue']['missing_binding']` records the
missing fixture binding.  Queue attribution, entry units and the real
scheduler binding remain A-owned and unconfigured.

## Capture, publication and latch

`begin_capture(batch_seq)` requires a fixture domain, context, active complete
CONFIG and CDC online and not busy.  The u32 local batch sequence is distinct
from the u16 wire sequence and must strictly increase within a pair.  A
successful begin advances the generation and immediately revokes any existing
latch/publication coherence.  It returns an opaque, one-shot ticket bound to
the model instance, immutable context, generation and batch.

`values` is an exact mapping:

| Key | Rule |
| --- | --- |
| `yaw_q`, `pitch_q` | Integers in `[-15000, 15000]`. |
| `speed_code` | Integer in `[0, 20]`. |
| `wire_capture_seq` | u16; strictly increasing within the pair. |
| `sample_tick` | u64; nondecreasing within the pair. |
| `yaw_period` | u64. |
| `pitch_period`, `speed_period` | u32. |
| `quality` | u4. |
| `gain_code` | One of `{0,1,2,4}`. |
| `ratio_q8_8` | u16. |
| `ratio_valid` | Exact `bool`. |
| `motion_profile` | u8 and a member of `domain['motion_profiles']`. |
| `last_observed_sequence` | u16. |

Asserted quality bits require positive relevant periods; bit 3 requires all
three periods positive.  Ratio validity is independent of capture quality and
of the numeric ratio word: zero alone never proves a valid measurement.  These
are supplied software-fixture values, not physical calibration, time-origin,
ACL or runtime evidence.

The request stamp and session words are built from the bound context, not from
caller value fields:

* `0x38 = request_seq | (control_epoch << 16) | (0x0e << 24)`
* `0x3c = session`

`complete_capture` verifies the model-owned ticket and current
context/generation/batch, validates every value, checks the wire sequence and
sample-tick high-water marks, and only then publishes all 17 bank words in one
operation.  A failed completion leaves the prior bank bytes untouched and
creates no new publication.  The ticket is consumed by the first completion
attempt, including a failing validation attempt.  Duplicate, late, foreign and
fabricated tickets cannot publish.

The bank uses no integer truncation: signed yaw/pitch are stored as 32-bit
two's complement, yaw period and sample tick are split into low/high words,
and pitch/speed periods use their full 32 bits.  Wire sequence, quality, gain,
ratio, motion profile and last-observed sequence occupy their declared low
fields.

`LATCH` freezes the 17 words from one publication, context and generation.
`read_snapshot` checks coherence, current context/generation and the live
session/sequence words before and after every bank read.  An optional
`interleave(offset, model)` hook runs after each read.  Any concurrent
revocation rejects the whole read.  The returned dictionary is detached and
carries explicit `software_fixture: True`,
`hardware_enable_eligible: False` and `movement_authorized: False`.

STOP, fault, context/session/BOOT/epoch change, a new CONFIG request, a new
capture cycle, CDC loss and a conflicting LATCH clear latch coherence and the
ratio-valid status immediately.  Historical bank bytes may remain readable
until RELEASE, but they are never valid.  Status bit 2 remains set until
RELEASE or reset; bit 3 and bit 9 clear with coherence.  RELEASE and reset do
not revive availability.

`reset` zeroes the bank and clears the latch, publication, tickets, gates,
CDC flags, queue counters, shadow and active/pending CONFIG.  It retains the
fixture domain binding and the anti-reuse pair/request tracking and advances
the generation.  An old ticket or old CONFIG request cannot be replayed.

## Fixture choices and unresolved ABI details

The following are explicit fixture choices or unresolved questions.  They are
not additional A decisions and must not be represented as frozen semantics.

1. Main review corrected the original fixture retention: any changed context
   stops/disables and clears fixture enable/recovery gates. A changed session,
   BOOT or CONFIG epoch also discards active CONFIG and shadow initialization.
   A request/control-epoch-only change may retain CONFIG data but requires fresh
   gates and an explicit ENABLE. These conservative fixture rules do not freeze
   the complete public ABI. Identical context remains a no-op.
2. `begin_capture` is gated by active CONFIG and CDC eligibility, not by
   stopped state or a latched fault.  ENABLE remains blocked by a latched
   fault.  Whether diagnostic capture should be blocked by fault/stop is not
   settled by the main specification.
3. `begin_capture` proactively discards a generation-bound pending CONFIG
   request.  A stale request cannot publish at a later boundary; the model
   records it as revoked and does not resurrect it.
4. `RELEASE` advances the generation, so it also invalidates an unlatched
   current publication and any pending CONFIG.  This follows from generation
   binding rather than a separate RELEASE rule.
5. A ticket is consumed by the first `complete_capture` attempt even when
   value, sequence or tick validation fails.  Callers cannot retry the same
   ticket; they must request a new capture cycle.
6. `reset` retains the domain binding, the bounded session/BOOT pair table,
   CONFIG request high-water marks, and, conservatively, the local batch,
   wire sequence and sample-tick high-water marks.  The main specification
   explicitly lists anti-reuse context/session/request retention but not
   capture high-water retention.
7. `snapshot_latched` (bit 2) denotes an outstanding latch until RELEASE or
   reset, even after coherence (bit 3) is revoked.  A new LATCH therefore
   rejects while an incoherent historical latch remains; RELEASE is required
   first.  `snapshot_available` (bit 4) is false for that incoherent latch.
8. `snapshot_available` means a current eligible publication or a coherent
   latch.  It is a fixture status bit and never proves source authority.
9. Exact ABI identity, CONFIG domain/context encoding, queue identity/unit/
   capacity, sample and capture clock units/origin, period-width asymmetry,
   the separate local diagnostic bank, AXI response codes, calibration,
   time-provenance and ACL/runtime proof remain A-owned and are not claimed
   here.  The yaw 64-bit versus pitch/speed 32-bit period proposal is still a
   proposal.
10. `rate_codes`, `sensor_profiles`, `motion_profiles`, `error_bound`,
    `gain_code`, `quality` and the request type are exercised as declared
    fixture domains/enums.  They do not establish old hardware semantics or
    real allowed values.
11. The ratio-valid flag, capture quality, identifiers and periods are
    supplied fixture truth.  They are not physical measurements, calibration
    proof, a matched image or a board result.
12. Error `.code` strings (`argument`, `address`, `access`, `domain`,
    `context`, `strobe`, `reserved`, `command`, `shadow`, `apply`, `queue`,
    `state`, `capture`, `ticket`, `snapshot`) are local test taxonomy, not
    AXI response codes or a frozen public error ABI.
13. After `reset`, the last active session/BOOT pair may be resumed with
    nondecreasing epoch/request high-water marks.  Other previously used
    pairs remain barred, and old tickets and CONFIG requests remain rejected.
    This resume exception is a fixture choice; whether reset should also bar
    the last pair is not settled by the main specification.

## Main correction of lifecycle boundaries

The original70 worker tests passed on their recorded source, but the main's
separate input-callback probes reproduced revoked capture resurrection. A custom
Mapping getter can execute STOP, fault, reset, context change, a new capture cycle
or CDC loss during validation. Final code rechecks the issued ticket's original
context, generation, batch and CDC eligibility after extracting all values, before
publishing any bank words or sequence/tick high-water marks. It never stamps an
old capture with a new current generation. Original failing bytes/logs are retained.

Withdrawing an enabled fixture gate stops/disables and revokes pending/capture
state. CDC loss revokes even when no snapshot existed, so a CONFIG pending before
the first capture cannot survive an offline/busy transition. Restoring gates or
CDC never enables automatically. Bit9 ratio validity is set only by a coherent
LATCH, independently from quality bits; two original tests were corrected to this
B07 expectation, with their failed intermediate run and original bytes preserved.

Worker STARTED.thread_id identifies its parent; the actual child identity is in
the main integration receipt. Worker-reported early D1 TypeError traceback was
not retained; no complete provenance claim is made for that earlier failure.

## Offline verification

Run from the worktree root with the project virtual environment:

```
D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 -m unittest discover -s competition/deepeye/tests/control -p test_register_transaction.py -v
```

The suite uses only the standard library and the reference module.  It does
not import the resident controller, private deployment state, a service,
credentials, a board image or a network client.  It covers constructor and
authority invariants, domain/context validation and anti-reuse, every bus and
access class, STOP priority and reserved-bit ordering, shadow atomicity,
CONFIG apply/duplicate/conflict/boundary/epoch behavior, queue saturation,
capture preconditions and ticket lifecycle, value and quality validation,
wire/tick high-water marks, exact bank encoding from bound context, LATCH and
RELEASE liveness, all specified coherence revocations, interleaved-read
rejection, detached results, reset and replay prevention.

The worker evidence directory contains the command, raw binary stdout/stderr,
exit code, source/test/document hashes and the concise result.  All results
are offline software results.  They are not RTL, MMIO, AXI, CDC, board,
calibration, runtime or product acceptance.
