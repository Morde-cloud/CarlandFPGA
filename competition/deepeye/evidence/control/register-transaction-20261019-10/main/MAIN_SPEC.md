# B offline register transaction model — main specification

Task DEEPEYE-IMPLEMENTATION-20261014/v1; work B-REGISTER-TRANSACTION-20261019-10-v1.
Operation B-DEEPEYE-REGISTER-TRANSACTION-20261019-10. Base433db2a82854a669778eb8c3cd35c309623a087e.
DEEPEYE-HUMAN-LOCK-20261014/revision1 H01-H15 requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
design1011259415a0916054eb580687612580bc1e5f09. A-only board; A owns final ABI.

Implement an offline Python transition reference, no RTL/MMIO/AXI driver, no
production admission. Hardware_enable_eligible and movement_authorized always
False even in an explicitly named software fixture. No default real domains.
The reviewed REGISTER07 layout/access/reset is unchanged. A's exact decision
4523157db12203d127ceb6ae25f2d187e85c9cc9 is the owner input (private saved doc).
New API design details below are B fixture proposals, not additional A freezes.

## API and fixtures

Use stdlib only. Class RegisterTransactionModel(domain=None); methods write(addr,
data,wstrb=15), read(addr), reset(), set_context(context), set_fixture_gates(enable,
recovery), set_cdc(online,busy), set_queue(used,overflow_increment=0,merged_increment=0),
raise_fault(flags), block_boundary(block), begin_capture(batch_seq),
complete_capture(ticket,values), read_snapshot(interleave=None), inspect().
ValueError or a dedicated subclass for rejected commands. STOP side effects
precede raising reserved-bit error. Return detached dictionaries/immutable values.
No public state containers aliased to caller inputs/outputs. Type-strict integers
(bool is not an integer), reject unknown/missing mapping fields and overflow.

domain is None (unconfigured) or an exact mapping: fixture_id (nonempty string),
identity(u32), rate_codes/sensor_profiles/motion_profiles/apply_blocks (nonempty
unique lists/tuples of u8), queue_capacity(u16), clock_id(nonempty fixture string).
All domains are explicitly software fixtures. Store a validated immutable copy.
Zero may occur in fixture domains; reset profile zero remains unconfigured until
explicit complete CONFIG apply. Changing supplied containers must not alter model.

context exact mapping: session(u32), boot_digest(lowercase64hex), config_epoch(u8),
control_epoch(u8), request_seq(u16). Store detached immutable tuple. set_context
revokes and discards pending config/capture/latch coherence on any change; identical
context is a no-op. A new session or BOOT may not reuse a previously used pair;
bounded retained session/BOOT identities (max64, fail closed when exhausted).
Within a pair, config/control epochs and request sequence must not decrease;
request sequence may restart only when control_epoch increases. No wrap. Internal
generation is monotonic Python integer, never reset by reset(), never projected to
wire bits. Context rollback rejects without reviving state. Config epoch is owned
by this fixture model: successful block apply increments it once; no caller epoch
field in apply_request. Reject apply at epoch255. This epoch progression is a
fixture proposal pending A's complete ABI approval.

set_fixture_gates explicit bools. ENABLE requires domain/context, active complete
config, enable fixture gate, CDC online/nonbusy and no latched fault. CLEAR_FAULT
requires stopped/disabled and recovery fixture gate; it never enables. Reset clears
all storage, gates, active/shadow/pending, CDC flags, queue counters and snapshot,
retains anti-reuse context/session/request high-water tracking and advances generation.
Reset must not allow old ticket or config request replay; real reset/CDC is out of scope.

## Bus/commands/CONFIG

All29 source rows retain offsets; 0x2c NO_ACCESS even WSTRB0. Unknown, unaligned,
negative/oversized addresses and RO writes reject. Reads WO commands return0;
0x00 unknown identity read fails when no domain, ABI word is fixture proposal3.
Status defined bits/mask0x00ff07ff, initial1. No read is command acknowledgment.
Known writable WSTRB0 no-op after address/access/data/strobe validation.
Mask data by strobed bytes. STOP if byte0 strobed and bit0 set: stop+disable,
advance generation, revoke snapshot/pending config/capture, no other command.
If any strobed reserved command bits set, raise only after STOP; combinations of
defined command bits with STOP are dominated, not separately executed.
Other nonzero commands require full strobe and exactly one ofbits1..4. Zero masked
command is no-op. LATCH requires eligible current publication and no existing
latch; conflicting LATCH revokes existing coherence then rejects. RELEASE clears
latch, advances generation and prevents stale completion resurrection.

Shadow0x10 mask0x00ffffff,0x18/1c/20 mask0xff. Validate entire merged word before
atomic update. E actual{0,1,2,4,8}; rate/profile/apply_block need explicit domain.
Track explicit initialization of all4shadow registers separately from reset zeros.
Dirty means staged configuration differs from active (or initial staged fields).
Apply0x14 full-strobe low16 request sequence; sequence0 is real request. Validate
all4 shadow fields initialized and complete, domain/context present, epoch<255,
no conflicting pending request. Capture an immutable whole payload/context.
New request seq strictly greater than previous accepted seq within session/BOOT;
same last seq+payload+original context is duplicate only while original request is
pending or completed without revocation; never reapply/renew. Conflict or older seq
rejects, including after STOP/reset. Keep bounded last request/high-water only.
Staging additional writes after apply does not change pending payload. Specified
apply_block matches block_boundary(block); other blocks no-op; identical context
and generation required before publishing all active fields in one operation.
No pending request after revocation can be resurrected by a matching boundary.

Queue fixture requires domain; used<=capacity and each counter saturates16bits.
Unconfigured queue reads zero but carries explicit missing binding in inspect().

## Snapshot

begin_capture(batch_seq u32) needs domain/context+activeconfig and CDC online;
strictly increasing local batch sequence within session/BOOT, distinct from wire
sequence; advances generation and revokes existing latch immediately. Returns a
model-issued opaque ticket tied to the immutable context/generation/batch. Ticket
is consumed once; late, duplicate, foreign-model, fabricated ticket cannot publish.
complete_capture verifies ticket and current identity, validates all values before
atomic publication. Any failed completion must not expose partial valid fields.

values exact mapping: yaw_q,pitch_q (ints[-15000,15000]); speed_code[0,20];
wire_capture_seq(u16 strictly increasing within session/BOOT); sample_tick(u64,
nondecreasing within same clock/session); yaw_period(u64),pitch_period/speed_period
(u32); quality(u4); gain_code{0,1,2,4}; ratio_q8_8(u16),ratio_valid(bool);
motion_profile(u8 in fixture domain); last_observed_sequence(u16).
Request stamp and session are built from bound context, not caller value fields.
Require positive relevant periods for asserted quality bits; bit3 requires all
three periods positive. Ratio validity independent of capture quality; numeric
zero alone never proves valid measurement. This accepts supplied fixture quality,
not physical measurement; document absent calibration/time/ACL/runtime proof.
Publication exposes bank0x30..70 exactly perB07. LATCH freezes all17 words from one
publication+context+generation; later STOP/fault/contextchange/newcapture/conflict
immediately clears coherence and ratio-valid status. Historical bank bytes may
remain readable until RELEASE, but invalid. Reset zeroes bank. No integer truncation.

read_snapshot checks latch coherence/current context/generation plus session/seq
before and after reading all bank words; optional interleave(offset,model) is a
test hook after each read. Any concurrent revocation rejects whole result. Returned
snapshot is detached and explicitly software fixture. status availability/current
publication must not revive after release/STOP. cdc busy/offline revokes eligibility.

## Execution ownership and evidence

Worker owns only register_transaction_reference.py in golden/control,
test_register_transaction.py in tests/control, REGISTER_TRANSACTION_REFERENCE.md
in golden/control, and evidence/control/register-transaction-20261019-10/worker/.
Do not edit old descriptor/examples/capture/core/stream/evidence or shared A/C files.
Worker retains initial failures, actual command exitcodes/raw binary stdout/stderr,
bounded tests, input/output SHA256 and a concise result. No Git commit/push, no
external communication, service/credential/queue changes, new roots/children/board.
Report [需桌面回合]/[需本人操作] only to main with concrete cause if encountered.
Do not declare acceptance. Main independently verifies key behavior.
