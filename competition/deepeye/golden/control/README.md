# Candidate control capture/snapshot foundation (B side, candidate only)

Task: `DEEPEYE-IMPLEMENTATION-20261014/v1`
Work: `B-CONTROL-SNAPSHOT-FOUNDATION-20261015-01-v1`
Correction: `B-CONTROL-INGRESS-STOP-CORRECTION-20261016-02-v1`
Contract: `DEEPEYE-HUMAN-LOCK-20261014` revision 1 (H01-H15)
Requirements SHA256: `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`
Lock commit: `f5989cd5defce561f9ba98e6b18fc2682945f0a2`
Design commit: `1011259415a0916054eb580687612580bc1e5f09`
Read-only A pin: `3b4736ff655b7fee35e79a5387f4118d1fff417c`

This directory holds a bounded, deterministic, candidate-only SOFTWARE
behavioral model for three-channel atomic capture, batch binding and snapshot
publication, plus an exact 29-offset register inventory crosswalk. It models
no physical hardware behavior and grants no motion or enable authority.

## What this is not

- Not RTL, synthesis, implementation or board evidence.
- Not a public ABI: no register bit positions, access types, reset values,
  WSTRB semantics, sample-tick word order or capture diagnostic address map
  are assigned. Unknown hardware fields are `null` with explicit reasons.
- Not a CDC/RDC claim: reset/stop/fault are abstract software events.
- Not an enable authorization: `hardware_enable_eligible` is a constant
  `false` and `enable()` only sets a software-local flag.
- The +/-2 tick capture tolerance is a proposed candidate bound, never a
  measured hardware limit; +/-3 is rejected in the candidate model.

## Files

| File | Purpose |
| --- | --- |
| `capture_snapshot_reference.py` | Candidate model, PWM integer math, register inventory, vector generator and `emit`/`check` CLI |
| `register_candidate_inventory.json` | 29 pinned offsets/names/widths/statuses; unknown fields null with reasons; `0x2c` `no_access` |
| `snapshot_vectors.json` | Machine-readable PWM boundary vectors (61) and capture scenarios (36, of which 25 negative) |
| `README.md` | This document |

Tests live at `competition/deepeye/tests/control/test_capture_snapshot.py`.
Evidence lives at `competition/deepeye/evidence/control/snapshot-foundation-01/`.
Correction evidence lives at
`competition/deepeye/evidence/control/capture-correction-02/`.

## Register inventory

The inventory preserves the exact 29 source rows (`registers.csv`) in order:
`0x00` identification, `0x04` abi_version, `0x08` control, `0x0c` status,
`0x10` shadow_configuration, `0x14` apply_request, `0x18` sample_rate,
`0x1c` error_bound, `0x20` profile, `0x24` queue_status, `0x28`
overflow_merge, `0x2c` reserved (no_access), `0x30` applied_yaw, `0x34`
applied_speed, `0x38` applied_request, `0x3c` session, `0x40`
sample_tick_word0, `0x44` sample_tick_word1, `0x48` capture_period0, `0x4c`
capture_period1, `0x50` capture_sequence, `0x54` capture_quality, `0x58`
gain, `0x5c` measured_ratio, `0x60` applied_pitch, `0x64`
pitch_capture_period, `0x68` speed_capture_period, `0x6c` motion_profile_id,
`0x70` last_observed_sequence.

## Deterministic APIs

PWM integer math (all values strict plain ints; bool/float/str rejected):

- `angle_high_ticks(q)`: `10000 + 16 * (q + 15000)` for `q` in `-15000..15000`
- `speed_high_ticks(code)`: `50000 + 1000 * code` for `code` in `0..20`
- `decode_angle_count(high)`, `decode_speed_count(high)`: nearest legal code,
  ties to the lower code, returns `(code, expected_ticks, delta_ticks)`
- `period_valid(period)`: candidate `abs(period - 2000000) <= 2`
- `classify_high_count(channel, high, period=2000000)`: machine-readable
  dict with `accepted`, `candidate_only` and `hardware_enable_eligible=false`

Batch records:

- `BatchKey(session, control_epoch, request_seq, batch_seq)`: immutable;
  candidate widths u32/u8/u16/u32.
- `ChannelEvidence.create(channel, session, control_epoch, request_seq,
  batch_seq, period_ticks, high_ticks)`: immutable validated evidence with
  decoded code, delta, `period_valid`, `within_candidate_tolerance`, `valid`.
  Every construction path re-derives those fields from the raw channel,
  `period_ticks` and `high_ticks` and rejects caller-authored or inconsistent
  values; `submit_evidence` re-validates and stores a detached canonical copy,
  so caller-retained records cannot rewrite model state.

Capture model (`CaptureSnapshotModel`):

- Session/cycle: `begin_session(session)`, `begin_epoch(control_epoch)`,
  `apply_request(request_seq)`.
- Evidence: `submit_evidence(evidence)` returns `stored`,
  `invalid_stored` or `duplicate_ignored`; conflicting duplicates raise
  `BatchConflictError` after revoking eligibility.
- Publication: `publish_snapshot()` returns an immutable `CaptureSnapshot`
  (all three channels, identical batch key, valid period/high counts).
- Events: `stop(reason)`, `reset(reason, scope)` with abstract scope labels
  `fixture`/`authority`/`capture`, `set_fault(bit)`, `clear_fault()`,
  `enable()`. `stop` retires the active request: late capture evidence for it
  is refused and a bare `enable()` cannot republish; a new `apply_request` is
  required.
- Reads: `begin_frozen_read()` returns a `FrozenRead` with latched `words`,
  `coherent`, `latched_current` and `batch_key`; `words_consistent(words)`
  detects torn/mixed tuples; `latest_published()` returns immutable history.
- Observations: `eligibility`, `stopped`, `enabled`, `faults`,
  `pending_channels`, `pending_key`, `last_batch_seq`, `history_len`,
  `published_count`, `hardware_enable_eligible` (always false).

`CandidateRegisterFile` is a candidate-local shadow over exactly the 29
offsets: unwritten values are `None`, `0x2c` raises
`ReservedRegisterAccessError` for reads and writes, partial write strobes
raise `ValidationError` (WSTRB semantics pending A freeze), and out-of-map
offsets raise `ValidationError`.

## Candidate semantics (software choices, not frozen public rules)

- Batch key is exactly `(session, control_epoch, request_seq, batch_seq)`;
  yaw, pitch and speed evidence must share one identical key, all three
  channels must be present and valid before a snapshot publishes.
- A newer `batch_seq` starts a fresh pending batch; an older partial batch is
  discarded and can never publish. Old pitch is never merged with new yaw.
- Identical duplicate evidence for a key is idempotent; conflicting duplicate
  evidence (same key and channel, different period/high counts) permanently
  invalidates captured eligibility for that batch. The immutable historical
  snapshot object itself is never mutated.
- Missing or invalid channel evidence revokes visible captured eligibility
  (a stale snapshot is never silently reused).
- Reset/STOP/fault invalidate pending state and visible eligibility; a latched
  frozen read may keep its old bytes only as explicitly INVALID
  (`coherent == false`). After reset or fault a genuinely newer session and a
  new enable are required; old keys cannot restore eligibility.
- STOP and a new control epoch retire the active request. Late valid evidence
  for a retired request is refused (`ForeignEvidenceError`), cannot repopulate
  pending state and cannot restore captured eligibility, including after a
  bare `enable()`; neither a new epoch nor a new session silently reuses the
  retired request, and only a new `apply_request` re-arms capture.
- Publication is refused while STOP is latched or software enable is absent
  (`PublishNotReadyError`); a published snapshot is rebuilt from detached
  model-owned primitives and its batch key is re-validated on access, so a
  caller-retained evidence record, key or returned key copy can never rewrite
  pending or historical state.
- Frozen-read coherence tracks captured eligibility: `coherent` is True only
  while the latched bytes were latched from current published eligibility and
  no revocation has happened since. STOP, reset, fault, conflict, a new
  session, a new epoch, a new applied request, a new capture cycle (including
  invalid or delayed evidence) and invalid current-channel evidence all turn
  outstanding latches to explicit INVALID (`coherent == false`) while their
  bytes stay readable as stale history. Shadow register writes never disturb
  a latch, and a fresh latch from a new publication is coherent again.
- STOP dominates apply; `clear_fault` and `enable` are separate stopped-state
  transitions and neither grants hardware authority.
- Candidate session/epoch/request/batch sequences are monotonic and
  non-wrapping; replays and regressions raise `SequenceViolationError` and
  wrap points require a new session. State is bounded: one pending batch
  (at most three channels), one latest snapshot plus an 8-entry recent
  history, fixed counters - no unlimited tombstones.

The capture word view used for atomic-read tests is candidate-local
(`session, control_epoch, request_seq, batch_seq, yaw+15000, pitch+15000,
speed_code, quality`); it is not a public address map and asserts no
sample-tick word order.

## Commands

From the worktree root `D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014`:

```
D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 competition/deepeye/golden/control/capture_snapshot_reference.py emit --inventory competition/deepeye/golden/control/register_candidate_inventory.json --vectors competition/deepeye/golden/control/snapshot_vectors.json
D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 competition/deepeye/golden/control/capture_snapshot_reference.py check --inventory competition/deepeye/golden/control/register_candidate_inventory.json --vectors competition/deepeye/golden/control/snapshot_vectors.json
D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 -m unittest discover -s competition/deepeye/tests/control -p test_capture_snapshot.py -v
```

## Missing dependencies (explicit, unresolved)

1. R03: public control/status/config register bit numbering, access types and
   reset values (A freeze).
2. R03: WSTRB byte-enable semantics for partial-word writes.
3. R03: sample-tick word order and multiword read atomicity (0x40/0x44).
4. R03: capture diagnostic address map and per-channel word mapping.
5. CDC/RDC: physical reset/handshake and first-snapshot implementation.
6. A: matched HWH/bit artifact and real per-register reset values.
7. R03/G05/HIL: calibrated physical PWM timing and measured IO capture bounds.

## Claims

Main boundary correction `B-CONTROL-MAIN-BOUNDARY-20261016-03` rejects integer
and string subclasses at scalar ingress; overloaded arithmetic cannot make a
zero period valid. Both `publish_snapshot()` and `latest_published()` return
detached records, so mutating a returned object cannot rewrite internal history
or subsequent frozen reads. These are API data-boundary guarantees, not a
security boundary against arbitrary code inside the same Python process.
The main preserved the prior failing source and reproduction logs separately.

No acceptance, board, CDC/RDC, ABI, timing, compression or latency claim is
made. Simulation/synthesis/implementation/board/system stages remain
`not_run`. B05/G05/R03 acceptance is not claimed and hardware ENABLE is never
eligible from anything in this directory.
