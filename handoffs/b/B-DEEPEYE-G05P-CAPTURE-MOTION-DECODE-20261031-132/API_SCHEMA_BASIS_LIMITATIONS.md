# B132 G05P capture decoder: API, schema, source basis and limitations

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; work/operation
`B-DEEPEYE-G05P-CAPTURE-MOTION-DECODE-20261031-132`.

Status: **SOURCE_ONLY_NOT_EXECUTED**. No candidate import, compile, test, model,
simulator, board, network, peer, service or SQL execution was performed by the
author. Only AST parsing of the new Python source and JSON parsing of the new
fixture were performed. No product acceptance, H01-H15 acceptance, timing claim,
electrical-loopback claim or motion authority is made.

The immutable contract remains H01-H15 at
`DEEPEYE-HUMAN-LOCK-20261014/revision1`, contract pin
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
The final design remains `1011259415a0916054eb580687612580bc1e5f09`.
Final 100 MHz, `1%`/`100 ms`, original 29 cards, both H12 paths, full game 3D/UI
and all hidden-layout/causal/online-decision requirements remain unchanged and
unaccepted. This 50 MHz decoder is diagnostic evidence only.

## Selected source identity

The held `competition/deepeye/fpga/diagnostic/functional50_build98/closure_template.json`
is explicitly an unfrozen template. The separately frozen
`.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-74/build116-prelaunch/FROZEN_CLOSURE.json`
is `FROZEN_MAIN_REVIEWED`, source commit
`9e068bd3dbfa5e2d02c4a7c2bcfe6b733ac0e1da`, and selects the additive-50 RTL below.
The published worktree head `dd52028af809363bd445fae8e7b4cf10ec7753ad`
contains byte-identical selected files and Git blobs. No build116 result, bitstream,
HWH, timing closure or board run is inferred from this source identity.
The implementation worktree HEAD observed read-only for this task was
`bea8689c4ad8e968c900ec2a9fa5647d8401ae33`; the selected local files also match
the recorded frozen blobs byte for byte.

## Exact 32-word layout

All words are 32-bit. Multiword integers are little-word ordered. The capture
record contains no top-level layout word and no full 256-bit run or 128-bit nonce.

| Word | Meaning | Width / interpretation | RTL basis |
|---:|---|---|---|
| 0 | capture sequence | uint32, 1..2^32-2 | `deepeye_g05_axi_50mhz_candidate.sv:220`, read at `:275-276` |
| 1 | command ID | uint32, nonzero | `:220`; command identity from `:73-79` |
| 2 | transport tag | uint32 | `:220` |
| 3 | `speed[15:8]`, `profile[7:0]` | two uint8; upper 16 must be zero | `:222` |
| 4 | `yaw_q[15:0]`, `pitch_q[31:16]` | two signed int16 bit patterns | `:223` |
| 5 | original TTL milliseconds | uint16; upper 16 must be zero | `:223` |
| 6..7 | actual applied tick | uint64 low word first, 50 MHz local cycle | `:224`; engine `:405-409` |
| 8..9 | original deadline tick | uint64 low word first | `:225`; engine `:408` |
| 10..11 | latest joined-record result tick | uint64 low word first; not host time | `:226`; engine `:383-387` |
| 12 | yaw period | uint32 sampled ticks | `:228`; engine `:31-33` |
| 13 | pitch period | uint32 sampled ticks | `:228` |
| 14 | speed period | uint32 sampled ticks | `:228` |
| 15 | yaw high | uint32 sampled ticks | `:229` |
| 16 | pitch high | uint32 sampled ticks | `:229` |
| 17 | speed high | uint32 sampled ticks | `:229` |
| 18..19 | yaw start witness | uint64 low/high, upper high word zero | `:230-231`; engine `:102-110` |
| 20..21 | pitch start witness | uint64 low/high, upper high word zero | `:230-231` |
| 22..23 | speed start witness | uint64 low/high, upper high word zero | `:230-231` |
| 24..25 | yaw end witness | uint64 low/high, upper high word zero | `:232-233` |
| 26..27 | pitch end witness | uint64 low/high, upper high word zero | `:232-233` |
| 28..29 | speed end witness | uint64 low/high, upper high word zero | `:232-233` |
| 30 | session | `identity[12]`, nonzero uint32 | `:235` |
| 31 | magic | `0x47303550` (`G05P`) | `:235`; magic constants `:29-30` |

`LATCH` copies the eligible record only while `latch_valid` is allowed; another
LATCH cannot overwrite it. Readback is gated by `latch_valid` and `live`
(`:218-240`, `:275-276`). The status/latch protocol and all 32 words must be
obtained from the actual register bank; returning expected bytes is not a capture.

## Input schema

Top-level request object, exact keys:

```json
{
  "schema": "B132_G05P_CAPTURE_DECODE_REQUEST_V1",
  "layout": 2,
  "raw_words": [32 integers],
  "original_record": null
}
```

`layout` may be `null` only to mark layout as unproven. A non-null value other
than 2 is refused. The capture itself carries magic but not layout.

`original_record` is either `null` or this exact object:

```json
{
  "schema": "B132_ORIGINAL_RECORD_V1",
  "identity_words": [13 integers],
  "status_before": 21,
  "status_after": 53,
  "fault_before": 0,
  "fault_after": 0,
  "command_id": 1,
  "transport_tag": 4097,
  "decision": {
    "yaw_q": 100,
    "pitch_q": -200,
    "profile": 1,
    "speed": 20,
    "ttl_ms": 100
  },
  "applied_tick": 1000000,
  "deadline_tick": 6000000,
  "result_tick": 4000000,
  "capture_seq": 1,
  "previous_capture_seq": 0,
  "previous_command_id": 0,
  "operation_id": "bounded caller label"
}
```

The last three fields are optional. `null` means no original-record correlation;
it is distinct from an object with missing fields, which is refused. The original
record is caller-supplied and mechanically compared. It is not authenticated.

Status checks use the actual bit map: bit0 bound, bit1 retired-or-halted, bit2
running, bit3 pending, bit4 latest eligible, bit5 latch valid, bit6 inflight.
The `status_before` observation is the pre-LATCH state and must show bit4, with
bit5 clear. The `status_after` observation is the post-LATCH state and must show
bit5. Both must show bound and running, with retired, pending and inflight clear;
reserved bits 7..31 must be zero. This mirrors the RTL LATCH gate
`latest_eligible && !latch_valid` and readback gate `latch_valid && live`
(`deepeye_g05_axi_50mhz_candidate.sv:78-80,144-145,218-240,275-276`). Both fault
words must be zero. These checks correlate the available records; they do not
authorize movement.

The held AXI README labels bit5 as `latch_eligible`; the selected RTL itself
drives that bit as `(latch_valid && live)`. Decoder semantics follow the selected
RTL bytes, not the older prose label.

## Output schema and statuses

The result schema is `B132_G05P_CAPTURE_DECODE_RESULT_V1`.

| Status | Meaning |
|---|---|
| `DECODED_PARTIAL_ASSOCIATION` | capture self-checks pass, layout=2, and all supplied original-record fields match; full run/nonce binding remains impossible from this capture |
| `DECODED_FACTS_ONLY` | capture/layout facts decoded but original-record correlation is null or layout is unproven; no full association claim |
| `INPUT_REJECTED` | malformed/oversized request shape, type or 32-word cardinality; available raw input is preserved |
| `REFUSED_CAPTURE` | numeric capture is structurally or mapper-inconsistent; raw input is preserved |
| `REFUSED_ASSOCIATION` | self-consistent capture contradicts the supplied original record; raw words and the independently decoded facts are preserved |
| `REFUSED_LAYOUT_MISMATCH` | caller asserted a layout other than 2 |

Every result has `motion_authority=false`, `formal_acceptance=false`,
`actor_or_custody_authenticated=false`,
`electrical_loopback=UNVERIFIED`, `active_kinematics=NOT_DERIVED` and
`world_frame_transform=NOT_PROVIDED`. No operator STOP packet or substitute
command is emitted on refusal.

The successful result separates:

- `facts.nominal_command_fields_from_capture`: words 3..5 only.
- `facts.pwm_channels`: measured/sampled period, high, start and end from words
  12..29 only.
- `facts.timestamps`: applied/deadline/result from words 6..11 only.
- `mapped_target_reference`: a sampling envelope derived from measured highs,
  plus one discrete mapper candidate validated against the ROM and an explicit
  integer target-reference conversion block.

Nominal fields are never used to reconstruct a reported measured high, period,
start or end.

## Actual 50 MHz mapping

Constants are from `deepeye_g05_profile_50mhz.sv:8-28` and the selected mapper:

- `CLOCK_HZ=50_000_000`, `TICK_NS=20`, `FRAME_TICKS=1_000_000`.
- `period = 1_000_000` ticks = 20,000,000 ns = 20 ms.
- `yaw_high = 125000 + 8*yaw_q`.
- `pitch_high = 125000 + 8*pitch_q`.
- `speed_high = 25000 + 500*speed_code`.
- `ttl_ticks = ttl_ms * 50000`.
- `NEAR_TOLERANCE_TICKS=1`.
- `profile1 FAST_9600` TTL cap 3000 ms; `profile2 STRESS_300` cap 12000 ms.
- The 42-row curvature ROM is copied exactly from
  `deepeye_g05_curvature_rom_50mhz.svh:2-45`; legality is
  `yaw_q^2 + pitch_q^2 <= curvature_limit[profile,speed]`.

The mapper rejects unknown profiles, axes outside +/-15000, speed above 20,
nonzero axes at speed zero, zero/oversized TTL and curvature above the ROM limit
(`deepeye_g05_command_map_50mhz.sv:27-49`). The decoder applies the same bounded
checks before emitting a mapped interval.

### Sampling and interval rule

The 50 MHz engine accepts an absolute difference of up to one tick between measured counts and mapper targets. The following intervals express this digital compatibility rule. Electrical jitter, cable delay and input calibration require separate measurements.

For a measured high `H` and period `P`, the yaw/pitch reference envelope is
derived from `H-1..H+1` through the inverse of `125000+8*q`, clipped to
`-15000..15000`, and reported in integer nanodegrees per second. One q code is
0.001 degree/s, so one code is 1,000,000 nanodegrees/s and one high tick is
125,000 nanodegrees/s. The pitch interval is not assumed equal to yaw; each lane
is decoded independently.

The speed envelope is derived from the speed high count through the inverse of
`25000+500*speed_code`, clipped to codes 0..20, and reported in integer
nanometres per second. The scalar interpretation is the frozen task-book profile
mapping: FAST is 0.0125 m/s per code (12,500,000 nm/s); STRESS is 0.0001 m/s per
code (100,000 nm/s). One speed high tick is respectively 25,000 or 200 nm/s.

The selected mapper defines high counts against its fixed 1,000,000-tick frame.
The inverse formulas therefore use absolute high counts and do not rescale by an
independently observed period; the period has its own ±1-tick validity check.
This is a target-reference inversion, not an actual angular-rate or actual-speed
measurement.

The decoder also solves the discrete mapper candidate. With a high step of 8 or
500 ticks and near tolerance 1, at most one integer command can satisfy the
measured high. The candidate must equal the capture's nominal command fields and
must satisfy the selected ROM limit. If no unique candidate exists, the decoder
refuses. The reported envelope is a mapper compatibility interval; it is not a
claim that every real-valued point in the envelope is a valid mapper command.

Window timestamps start at rearm. A valid channel has a positive start, a later end and a difference equal to its period. The global result age must cover every local end and precede the original TTL deadline. External input phase is independently observed. Sequence 0xffffffff is the last representable result; a subsequent increment would fault.

## Association limits

The capture embeds session, command ID and transport tag. It does not embed the
256-bit run ID or 128-bit nonce. The result therefore always says
`full_identity_bound_to_capture=false`; those dimensions remain external-only.
On a successful mechanical comparison it also lists the twelve capture-encodable
matching dimensions; that list is not a full-identity or authenticity claim.
This decoder does not establish actor, session custody, receipt authenticity, CRC,
wire framing or original-world causality. Those remain with the separately
retained C42/C48 and A-owned records.

When an original record is supplied, the decoder checks every field that is
actually encoded in the 32 words: session, command ID, tag, profile/speed,
yaw/pitch, TTL, applied/deadline/result ticks and capture sequence. Optional
previous sequence/command IDs prove strict nonwrapping increase only when the
caller actually supplies them. A missing optional predecessor is reported as
unchecked, not invented.

The input schema retains one full 13-word identity snapshot. It does not itself
prove that a second post-LATCH identity reread was byte-identical; that custody
step remains with the separately retained A/C original-operation procedure. The
decoder never upgrades the supplied snapshot into an authenticated binding.

## Engineering conversion and minimal gap

The selected source maps command fields to PWM counts. The frozen task-book text
defines the scalar target units: yaw/pitch q are 0.001 degree/s per code and the
two speed profiles have the per-code m/s scales above. The decoder therefore
exposes exact target-reference intervals in integer nano-units, with no floating
point rounding.

The machine-readable `mapped_target_reference.engineering_conversion` block fixes
the available target-reference formulas in integer nano-units:

- yaw/pitch: `(sampled_high_ticks - 125000) * 125000` nanodegrees/s;
- FAST_9600 speed: `(sampled_high_ticks - 25000) * 25000` nanometres/s;
- STRESS_300 speed: `(sampled_high_ticks - 25000) * 200` nanometres/s;
- period: `sampled_period_ticks * 20` nanoseconds.

No executable source in the selected package defines a world-frame transform from
the `(yaw,pitch,speed)` target reference to a simulator pose, nor a coordinate
axis/sign convention, integration cadence, acceleration envelope or actual
kinematic response. The result therefore marks the numeric conversion as
`DECODED_TARGET_REFERENCE_NOT_SIMULATOR_POSE`, with
`simulator_pose_transform=MISSING_NORMATIVE_SOURCE` and
`simulator_target_application=NOT_PERFORMED`; the top-level world-frame marker is
also `NOT_PROVIDED`. The minimal next normative gap, if the main selects it later,
is a separate consumer-side mapping from the decoded target reference to the
simulator's documented body/world axes and update loop. It must not be inferred
from PWM counts or from measured ADC/TRACE bytes. No such mapping is claimed
solved here.

## CLI

The decoder has a pure function API (`decode_request`) and a bounded CLI:

```powershell
python -B -X utf8 g05p_capture_decoder132.py --request <request.json> --out <new-absolute-directory>
```

The CLI rejects request files over 262,144 bytes, requires a new absolute output
directory, writes exactly `decode_result.json`, and performs no import-time I/O,
subprocess, board, network, module initialization or old-suite invocation. It
checks request/record cardinality before key traversal; oversized records are
refused as `RECORD_BOUNDS` while the available raw-word bank remains preserved.
Each preserved input section has a 4,096-character canonical-JSON budget; an
over-budget original record is not echoed and is marked
`original_record_preserved=false`. Canonical-size failures, including a
pathological integer that cannot be rendered within Python's integer-string
limit, also fail closed as not preserved. This keeps refusal output finite.
`--out` is never overwritten. The focused test source uses the pure API and a
synthetic 32-word fixture; it is prepared only and is not run by this author.

## Source basis table

All selected files are byte-identical at the frozen source commit and published
worktree head; their Git blobs are recorded in `SOURCE_PIN_MANIFEST.json`. The
line names below are 1-based. In this table, `.../additive50_source_candidate`
expands to
`competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate`;
the frozen-closure row uses the local handoff path recorded verbatim in the
manifest. The manifest, not this abbreviated table, is the exact path/hash index.

| Source | Lines used | Bytes | SHA256 |
|---|---:|---:|---|
| `.../additive50_source_candidate/rtl/deepeye_g05_axi_50mhz_candidate.sv` | 29-30, 43-107, 122-140, 160-165, 218-247, 256-276 | 16077 | `99cdb09399466966458343351d0d941191f34cc9af6f9808c5fb3cc58086ea5a` |
| `.../additive50_source_candidate/rtl/deepeye_g05_capture_engine_50mhz.sv` | 59-124, 129-223, 226-264, 282-325, 367-409, 461-579 | 33796 | `fcdb04d1e307506328c205154730e1cf8c5bff2efe72727a46a2f3f4b856ed8a` |
| `.../additive50_source_candidate/rtl/deepeye_g05_command_map_50mhz.sv` | 27-49 | 2377 | `8df580388e85a59a43a0eaaae697534123a6e128fdb4675098e7173bda60a6a1` |
| `.../additive50_source_candidate/rtl/deepeye_g05_profile_50mhz.sv` | 8-28 | 1794 | `8ec9bf0415e2ce5e87d2a793260bf635664f16584e2cb842df1fefba75e64307` |
| `.../additive50_source_candidate/rtl/deepeye_g05_curvature_rom_50mhz.svh` | 2-45 | 1960 | `d462859e6893cd90fb33ad9ddd481aaa7ee46937ba3d197431f81b602357a83c` |
| `competition/deepeye/fpga/control3d/deepeye_pwm_coherent_capture.sv` | 19-25, 107-124, 141-202, 218-242, 253-317 | 17155 | `4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456` |
| `competition/deepeye/fpga/diagnostic/g05_capture/axi/README.md` | 38-57, 100-126 | 7995 | `7523fa6ec76ce99483585457e60e158487c49c12fca2fa2fafa093b9a6e2a3ca` |
| `competition/deepeye/tools/diagnostic/offboard_control75/control_adapter.py` | 244-260 | 17616 | `725c375b1e30b725b83bdabd12891d98b7a09241b645b1b8c463a518ba797b7d` |
| `competition/deepeye/fpga/diagnostic/functional50_build98/closure_template.json` | 1-45 | 12963 | `d102e8670706e6d7cf0891f3e8beaf94c7710e3d1adc58d507362a6dfb3af12a` |
| `.../resume-74/build116-prelaunch/FROZEN_CLOSURE.json` | selected source/tooling fields | 16804 | `69fd26244a109d5668bf0a526d1b458bbcdc59715bf0bb68bce96c45eca7bf0b` |
| `docs/competition/deepeye-2026/taskbook_final.md` @ `101125941...` | 138, 140 | 109430 | `7f5c94f7fc73698236be954ae7818266d6dfe8b4949d1752dd045d76f4b71f18` |
| `docs/competition/deepeye-2026/immutable_scope.json` @ `f5989cd...` | `requirements` only for hash | 6684 | `6a86000e97d1571c0b7b89b9d3cf7facb11d2b6a06455eb1d53e0637676b6bc4` |
| `docs/competition/deepeye-2026/immutable_scope.md` @ `f5989cd...` | H01-H15 | 6139 | `27c5bf0b194036cf4300dbec371b6abba42bc5fda604da0e6e06284e4c5a2ddd` |

The source authorities are the frozen closure and selected package. The A53/A60
inbox text was read from
`.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-76/NEW_TASK_INBOX.json`
(SHA256 `4a8fb2df5551c7cc13bc3bd407f690c660dbaf433884cf60089e65b23e2abb85`)
and is an assignment reference, not a byte-authenticated board record.

## Test plan and execution budget

`test_g05p_capture_decoder132.py` contains only new focused tests: the synthetic
32-word hand-calculated fixture, null/zero distinction, raw cardinality, magic,
period/high/witness tolerance, start/end span limits, witness zero-extension,
profile/TTL/ROM bounds, identity/session/tag, pre/post-LATCH status flags,
sequence/wrap, bounded original-record handling, cycle boundaries, association
mismatch and mapper interval boundaries. Every fixture value is synthetic; no
board, TRACE/ADC, AI command or product result is implied. `TEST_PLAN.md` records
the commands for the main/reviewer to run later.

Estimated later pure-test budget (not an actual measurement): one Python process,
under 64 MiB resident memory, under 2 seconds wall time, no subprocess, no
network, no board, no vendor tool. The estimate is not test evidence.
