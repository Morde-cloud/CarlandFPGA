# B register semantics candidate 07 — requires A approval

Task DEEPEYE-IMPLEMENTATION-20261014/v1. Work
B-REGISTER-SEMANTICS-CANDIDATE-20261017-07-v1. Planned operation
B-DEEPEYE-REGISTER-PROPOSAL-20261017-07. Main01a13b55-095b-7461-8dd5-5476a130bd82.
Current product head1bfea106cf23cd8eb3406996799f9d31a3fbc4a1.
H01-H15 DEEPEYE-HUMAN-LOCK-20261014/r1 requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
design1011259415a0916054eb580687612580bc1e5f09. A alone hardware, A freezes ABI.

This addresses A's explicit request for register bitfield/reset/access proposals.
Create separate candidate JSON/Markdown under golden/control; do not alter the
historical register_candidate_inventory.json, golden capture model, A registers,
frozen taskbook or the published mailbox. This is a design artifact, not a new
driver/RTL implementation, HWH claim, control authority or product acceptance.
No Flash/native job is required for the main's critical design decisions.

## Evidence read

A input66aa291d7f01cc3cfefb8c30c4e8ad3aec6547bd; registers.csv SHA256
fd3d69509776829a4e33ea4f1a6ce8b39679bd101080b33dc2ff1df38c0a4f33.
All29 offsets/names/widths/status/authority rows are preserved verbatim. A file
currently has no public bit/reset/access semantics; every numeric bit proposal
below is B-designed and requires A approval. Existing B inventory intentionally
leaves these unknown; it remains unchanged and truthful for its old operation.

Frozen taskbook_final.md section7: CTRL powers up disabled, STOP dominates,
CLEAR_FAULT and ENABLE separate; CONFIG applies atomically at a block boundary;
HWH is the sole actual address authority and only a matched NEW overlay may be
used. measured_ratio is the PGA's independent before/after ADC calibration,
not compression ratio or imaginary MCP6S21 SO readback. GAIN_ACK ratio is Q8.8
in the inherited layout. Pinned A interface gain codes are {0:1,1:2,2:4,4:8}.
A capture_quality bits0..3 are yaw/pitch/speed/all_periods_valid; higher wire
bits zero. Wire capture_seq is16bits, unlike B local batch_seq32; no silent
truncation. A fault bits0..7 and exact enum files remain the source authority.

## Proposed fields (all words32bit, unlisted bits reserved-zero)

00 identification: RO A-assigned full32, reset unknown until matched HWH/RTL.
04 abi_version: RO full32, candidate reset3 reflecting ABI3; actual read still
requires matched image and cannot be asserted from this proposal.
08 control: write-one commands STOP bit0, CLEAR_FAULT1, ENABLE2,
SNAPSHOT_LATCH3, SNAPSHOT_RELEASE4; read0/reset0. See command priority below.
0c status: live bits stopped0, fault_latched1, snapshot_latched2,
snapshot_coherent3, snapshot_available4, cdc_busy5, cdc_online6,
config_dirty7, config_pending8, gain_ratio_valid9, enabled10;
fault_flags23:16 copies A fault bit meanings. Reset0x00000001. Reserved11:15,
24:31. Coherence and gain validity describe the current latched bank; no bit
alone proves source authority or physical acquisition.
10 shadow_configuration: threshold15:0, apply_block23:16; reset0, shadow RW.
14 apply_request: CONFIG request_seq15:0, full-word write command, read0/reset0;
requested epoch is NOT caller-authored. This proposes CONFIG-only staging,
not a new path for motion commands. A must approve this register's purpose.
18 sample_rate: rate_code7:0, shadow RW/reset0; meaning/allowed values A-owned.
1c error_bound: E7:0 (actual E in {0,1,2,4,8}), shadow RW/reset0.
20 profile: sensor_profile_id7:0, shadow RW/reset0; exact allowed enum A-owned;
zero reset means unconfigured even if an eventual enum uses numeric0.
24 queue_status: used_entries15:0, capacity_entries31:16, live RO/reset0.
Which scheduler queue and exact entry unit/capacity require A binding; never
assert a measured/implemented capacity. Require0<=used<=capacity<=65535; a queue
that cannot fit needs an A-approved wider representation. Never wrap or silently
claim a capacity of65535. Actual overflow accounting uses the separate counters.
28 overflow_merge: overflow_events15:0, merged_events31:16; RO/reset0,
independent saturating16 counters; attribution policy requires A scheduler.
2c reserved: NO READ OR WRITE, including zero-strobe access; no probe.
30 applied_yaw: captured_yaw_q signed32, sign-extended int16, +/-15000; RO bank/reset0.
34 applied_speed: captured_speed_code7:0,0..20; RO bank/reset0.
38 applied_request: motion request_seq15:0/control_epoch23:16/request_type31:24.
Type0x0e for valid motion capture; zero reset is invalid, not an applied request.
CONFIG and physical GAIN do not fabricate a motion capture stamp in this word.
3c session: snapshot_session32, RO bank/reset0; compare with separately
authenticated active A session, not only the register itself.
40 sample_tick_word0: sample_tick low32;44 sample_tick_word1: high32. RO bank/reset0.
Proposed uint64 observation/acquisition counter; exact source/units/binding to
last_observed_sequence remain A-owned. Never substitute send/host receipt time.
Current ADC source bounds are narrower; uint64 examples do not extend that source.
48 capture_period0: yaw_capture_period low32;4c capture_period1: high32.
RO bank/reset0; paired uint64 period is a B proposal, NOT existing A semantics.
64/68 pitch/speed period use32 bits. Tick clock, range and these asymmetries
must be explicitly accepted by A. No implicit high-count or edge-tick alias.
50 capture_sequence: wire_capture_seq15:0; high16zero; RO bank/reset0-invalid.
Reject values>65535 in this projection and require a new session before wrap.
Local32bit batch_seq is a separate key until A supplies an explicit association.
54 capture_quality: bits0yaw_valid/1pitch_valid/2speed_valid/3all_periods_valid;
bits4..31zero. RO bank/reset0. Must also pass live coherent/session/profile gates.
58 gain: applied_gain_code7:0 in {0,1,2,4}; RO bank/reset0. Command code is not
physical SPI readback; valid ratio needs independent ADC calibration evidence.
5c measured_ratio: measured_ratio_q8_8 low16; RO bank/reset0-invalid. Invalid,
near-zero denominator or stale calibration clears status.gain_ratio_valid;
zero numeric word alone is never a valid physical measurement.
60 applied_pitch: captured_pitch_q signed32 as yaw; RO bank/reset0.
64 pitch_capture_period: full32 RO bank/reset0.
68 speed_capture_period: full32 RO bank/reset0.
6c motion_profile_id: low8 RO bank/reset0-unconfigured, exact A enum.
70 last_observed_sequence: low16, high16zero RO bank/reset0-invalid; no silent
truncation or fabricated source association.

## Access, state and coherence proposal

Only a new offline descriptor is produced. There is no register I/O entrypoint.
Addresses aligned32 and exactly in A's29-row inventory. RO writes and reserved/
unknown/unaligned accesses are errors. No numerical AXI response code is frozen.
WSTRB is4bit; known writable-register WSTRB0 is a no-op; address/access checks
still happen first. Shadow data uses byte masks, ignores unstrobed bytes and
validates the complete resulting candidate before an atomic shadow update;
bad E/enum/reserved bits leave shadow unchanged. Config fields remain shadowed
until A validates the complete CONFIG/context and commits at a block boundary.

Command exception for fail-safe STOP: if control byte0 is strobed and bit0 is1,
STOP executes before all other command bits. Full or byte0-only STOP may revoke;
it never clears fault, enables or latches in the same write. Reserved bits in
strobed bytes still produce an error response AFTER revocation; they cannot
create authority. Other commands require WSTRB=15, reserved bits zero and exactly
one command bit; an all-zero command word is a no-op. CLEAR_FAULT|ENABLE is
rejected without enabling/clearing.
CLEAR_FAULT requires stopped/disabled and the A-defined recovery gates; ENABLE
is a distinct command needing matched new HWH/bit, BOOT/session/profile,
calibrated current source/capture and all A-owned authority checks. This artifact
cannot satisfy those gates. Config apply also needs a full-word strobe; identical
request/context/payload duplicates do not reapply/renew, conflicts reject.
Unlike the control command bits, apply_request is write-triggered data: a
full-strobe zero value requests sequence0 if the external context permits it;
it is not a no-op. Its readback0 is not an acknowledgement.

One latched read bank for0x30..0x70. LATCH requires an eligible A-authorized
publication and no outstanding latch; second LATCH rejects. RELEASE clears the
latch. STOP/fault/new request/new session/new epoch/new capture cycle/conflict
revoke coherence immediately; historical bytes may remain readable until RELEASE
but never valid. Reset clears both current bank/latch and all validity; it must
flush both CDC sides. A host reader uses one serialized owner, checks coherent
before/after, reads session/capture_sequence before/after and compares with the
authenticated active context. No wrap/reuse is allowed; untrusted parallel bus
masters and privilege separation remain separate A integration gates.

Internal nonwrapping revocation generation binds pending/latching publications;
late CDC completion after STOP/new request/reset cannot restore eligibility.
The mailbox06 transports opaque bits only and does not implement this generation
check. Numeric0 may be meaningful data; eligibility is always explicit. PC_DIRECT
does not synthesize board motion capture flags. Ratio validity is bound to the
latched eligible calibration publication, not unrelated later live ADC traffic.

## Unresolved A decisions (never silently filled)

Exact identity/reset implementation; access/bit proposal approval; chosen queue
and accounting units; all config/profile/rate enum domains and apply context;
capture/sample tick sources and widths;16bit wire capture/observation association;
physical PGA calibration/quality gates; full multiword/CDC revocation integration.
The29 offsets cannot, by this proposal alone, expose all three raw high counts
and every edge tick required by the taskbook. A must define an additional local
diagnostic bank/interface in a matched new HWH; do NOT steal reserved0x2c or
invent an AI side-channel. These missing diagnostics remain explicit blockers.

Validation for this phase is descriptor consistency and hand-derived field
examples, not runtime/RTL simulation. All product gates remain unaccepted.

## Machine-readable descriptor crosswalk

| Offset | Source name | Proposed access | Proposed reset | Defined fields |
|---|---|---|---|---|
| 0x00 | identification | RO_OWNER | A-dependent | identification[31:0] |
| 0x04 | abi_version | RO_OWNER | 0x00000003 | abi_version[31:0] |
| 0x08 | control | WO_CONTROL_COMMAND | 0x00000000 | STOP[0:0], CLEAR_FAULT[1:1], ENABLE[2:2], SNAPSHOT_LATCH[3:3], SNAPSHOT_RELEASE[4:4] |
| 0x0c | status | RO_LIVE | 0x00000001 | stopped[0:0], fault_latched[1:1], snapshot_latched[2:2], snapshot_coherent[3:3], snapshot_available[4:4], cdc_busy[5:5], cdc_online[6:6], config_dirty[7:7], config_pending[8:8], gain_ratio_valid[9:9], enabled[10:10], fault_flags[23:16] |
| 0x10 | shadow_configuration | RW_SHADOW | 0x00000000 | threshold[15:0], apply_block[23:16] |
| 0x14 | apply_request | WO_CONFIG_APPLY | 0x00000000 | request_seq[15:0] |
| 0x18 | sample_rate | RW_SHADOW | 0x00000000 | rate_code[7:0] |
| 0x1c | error_bound | RW_SHADOW | 0x00000000 | E[7:0] |
| 0x20 | profile | RW_SHADOW | 0x00000000 | sensor_profile_id[7:0] |
| 0x24 | queue_status | RO_LIVE | 0x00000000 | used_entries[15:0], capacity_entries[31:16] |
| 0x28 | overflow_merge | RO_LIVE | 0x00000000 | overflow_events[15:0], merged_events[31:16] |
| 0x2c | reserved | NO_ACCESS | A-dependent | no access |
| 0x30 | applied_yaw | RO_SNAPSHOT | 0x00000000 | captured_yaw_q[31:0] |
| 0x34 | applied_speed | RO_SNAPSHOT | 0x00000000 | captured_speed_code[7:0] |
| 0x38 | applied_request | RO_SNAPSHOT | 0x00000000 | request_seq[15:0], control_epoch[23:16], request_type[31:24] |
| 0x3c | session | RO_SNAPSHOT | 0x00000000 | snapshot_session[31:0] |
| 0x40 | sample_tick_word0 | RO_SNAPSHOT | 0x00000000 | sample_tick_low32[31:0] |
| 0x44 | sample_tick_word1 | RO_SNAPSHOT | 0x00000000 | sample_tick_high32[31:0] |
| 0x48 | capture_period0 | RO_SNAPSHOT | 0x00000000 | yaw_capture_period_low32[31:0] |
| 0x4c | capture_period1 | RO_SNAPSHOT | 0x00000000 | yaw_capture_period_high32[31:0] |
| 0x50 | capture_sequence | RO_SNAPSHOT | 0x00000000 | wire_capture_seq[15:0] |
| 0x54 | capture_quality | RO_SNAPSHOT | 0x00000000 | yaw_valid[0:0], pitch_valid[1:1], speed_valid[2:2], all_periods_valid[3:3] |
| 0x58 | gain | RO_SNAPSHOT | 0x00000000 | applied_gain_code[7:0] |
| 0x5c | measured_ratio | RO_SNAPSHOT | 0x00000000 | measured_ratio_q8_8[15:0] |
| 0x60 | applied_pitch | RO_SNAPSHOT | 0x00000000 | captured_pitch_q[31:0] |
| 0x64 | pitch_capture_period | RO_SNAPSHOT | 0x00000000 | pitch_capture_period[31:0] |
| 0x68 | speed_capture_period | RO_SNAPSHOT | 0x00000000 | speed_capture_period[31:0] |
| 0x6c | motion_profile_id | RO_SNAPSHOT | 0x00000000 | motion_profile_id[7:0] |
| 0x70 | last_observed_sequence | RO_SNAPSHOT | 0x00000000 | last_observed_sequence[15:0] |

See `register_semantics_candidate.json` for all source rows and exact masks, and `register_semantics_examples.json` for35 hand-derived examples. These examples are design expectations, not a tested register implementation. Input pins and structural audit are under `evidence/control/register-proposal-20261017-07/`. Original inventory/model, previous CDC candidate and all A files remain unchanged.
