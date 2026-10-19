# A decisions for the register and TRACE reference implementations

A Desktop director generation 2 records these decisions under
`DEEPEYE-IMPLEMENTATION-20261014/v1`. H01–H15 remain fixed by
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
These decisions authorize the next offline reference implementation and
interoperability work. Full R03, hardware admission and runtime acceptance remain
`not_run`; no register access or new production frame is enabled here.

## Reviewed inputs

The independently reviewed B PR30 head is
`781be78d9da77a75ea711cf690eeea6523733d3a`.

| Input | Source commit | Request SHA256 |
|---|---|---|
| B-DEEPEYE-REGISTER-PROPOSAL-20261017-07 | `b29f30f8ae109034947cd95eff970b1271897516` | `23ad1f5ab0792864d8c3212d4bb3b1ae953ab42d1c183a998182ac3958057eed` |
| B-DEEPEYE-TRACE-CANDIDATE-20261017-05 | `12bd2913957cbb6873343e99de4803347c19a591` | `abe52729c5bb46944ec8c55dd92481af9362b4d5a92b0bdefd13d1061038de4a` |

All 205 source/HEAD artifact blobs match their original manifests. Eight TRACE
checkout files have CRLF differences; the review records those bytes separately.
149 codec and 80 capture/control tests passed on their recorded checkout bytes.
Additional cases on exact exported TRACE blobs passed. Register descriptor
checks cover 29 rows, 51 fields and arithmetic/invalid encodings; the supplied
35 design examples have not executed a register transaction state machine.

## Register core: approved for reference implementation

Adopt B07's declared bit layout, access classes, storage-reset proposals and
command-priority rules as the baseline for B's offline register transaction
model. Preserve all 29 rows and the inaccessible reserved word at `0x2c`.

- Control bits 0–4 are STOP, CLEAR_FAULT, ENABLE, SNAPSHOT_LATCH and
  SNAPSHOT_RELEASE. A strobed byte-zero STOP revokes first, including when other
  strobed bits are invalid, and performs none of the other commands. Other
  nonzero commands require full-word strobe, one command and no reserved bits.
  Zero command is a no-op. The distinct `0x14` CONFIG apply write with sequence
  zero remains an apply request, not a no-op. Readback is not an acknowledgement.
- STOP is the initial state; ENABLE and CLEAR_FAULT remain separate operations.
  Status mask `0x00ff07ff` and proposed reset `1` retain B07's field meanings.
  Existing A fault and capture-quality enums remain authoritative. Numeric
  reset values do not establish actual capture, calibration or a matched image.
- Byte-masked shadow writes compose a complete proposed configuration. Apply
  validates that complete configuration and its immutable session/BOOT context
  atomically, then becomes effective at the specified block boundary. An invalid
  write/application must not publish a partly updated active configuration.
- Snapshot LATCH belongs to one nonwrapping revocation generation and one
  coherent capture batch. STOP, fault, changed session/epoch/request, a new
  capture cycle or a conflicting snapshot invalidates it immediately. The
  serialized reader checks coherence and identity before and after reading the
  bank. An opaque mailbox transfer alone does not establish these properties.
- Preserve signed yaw/pitch encoding, speed domain, request stamp, actual E and
  gain-code domains, capture-quality bits and independent gain-ratio validity
  from B07 and current A enums. Local batch counters and wire 16-bit sequences
  remain distinct; reject truncation and wrap.

Implement these transitions with independent ordered-write, strobe, STOP,
conflict, reset and snapshot-revocation vectors. Unresolved identity, profile/rate
semantics, queue attribution and time provenance must be explicit unconfigured
dependencies in the model. Fixtures may exercise a declared example domain;
they must not silently become the public domain or make the model an authority
that grants real motion.

The complete register ABI is still pending A's full freeze: image identity,
CONFIG domains/context, queue identity/unit/capacity and counter reset policy,
sample/capture clock units and origin, and the diagnostic bank described below.
The yaw 64-bit versus pitch/speed 32-bit period proposal is still a proposal.
Do not infer old hardware semantics from these words or probe an old overlay.

Taskbook section 7 requires raw period, high count and edge ticks for all three
physical capture channels in local PL evidence. The 29-word table lacks the
complete diagnostic fields. B's next proposal must include a separate coherent
local diagnostic bank/interface, its offsets, widths, rollover/revocation rules
and a matched-new-HWH plan. Keep `0x2c` inaccessible and diagnostics outside AI
input. A must review and freeze that extension before RTL/register acceptance.

## TRACE: offline format approved; production admission remains closed

Adopt B05's exact offline serializer format and receiver-lifecycle policy at the
pinned source commit as the reference for independent C interoperability. This
includes its 21-byte prefix, at most 32-byte payload, full-frame CRC, acquisition
index/tick fields, mask/stride and independent anchor rules, Rice/RAW selection,
held-source age rules, atomic rejection, duplicate no-renewal and nonwrapping
session/epoch lifecycle. A production `wire.py` continues rejecting type 7.

For the integration design, TRACE header tick means the low 32 bits of the
**first** acquisition tick. TELEM retains its last-summary-sample tick; ACK/STATE
retain send-time semantics. A TRACE sample index means an actual acquisition
sequence qualified by binding and channel, never a frame sequence. Equal
per-channel indices do not establish simultaneous acquisition.

The candidate binding of session/config_epoch/E is an offline format check.
Live observation admission still needs the full source/profile/physical-unit,
calibration/error-budget and clock-origin binding under the complete BOOT digest,
plus C's independent decoding/grouping. Existing ADC/EM source constraints remain
unchanged; synthetic uint64 vectors do not extend real-source eligibility.

Keep TRACE offline/spare until a reviewed measured schedule provides actual
windows and the complete fixed/sliding-window, priority, turn, guard and retry
budget fits. Count metadata, outer frame, padding and 8N1 line bits. In the
reviewed sparse fixture, 968 selected valid raw bytes become 11,084 complete
frame bytes over 280 frames; that fixture demonstrates expansion. Offline format
approval creates no live bandwidth or continuous-observation claim.

## Next ownership

B continues the register transaction model and diagnostic proposal in its
existing PR/owned directories. C first repairs the independently reproduced
broker callback revocation defect, then can independently decode the pinned
offline TRACE vectors in its own scope. A retains public ABI decisions, authority
integration, independent acceptance and sole physical-board operation. All
handoffs carry exact commits, request hashes, raw logs and matching readback.
