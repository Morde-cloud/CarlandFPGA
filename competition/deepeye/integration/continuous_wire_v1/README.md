# Continuous wire v1, first B milestone

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work `B-CONTINUOUS-WIRE-v2`.
Scope: human revision2 at817b355887c14cfa9c5d830c8589684f994af082,
requirements SHA256 `2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d`.
Only H07/H10 changed by the published explicit human instruction; the other13
H requirements, both H12 paths and original final quality gates remain.

This adapter implements the actual published Root791 JSONL request shape from
e0b3bd97ebca18647b4fd3599d3646c67feb1d40. It creates no process, socket, SSH,
hardware or native/UI/model instance and grants no motion authority. Root owns
the real load plan, actual13-word identity/journal, transport containment,
source provenance and source/AI/native complete-volume/Root/CAS acceptance.

`Binding(boot_id,build_id,request_hash,session_id)` binds the real selected plan;
public values alone do not authenticate it. `ContinuousWire` is owned by one
IO thread/process. `begin(op,now_ns=...,**fields)` validates and returns an
immutable Ticket.raw; Root calls `mark_sent(ticket,now_ns=...)` immediately
before its actual write attempt, then supplies one full original reply to
`finish(ticket,raw,now_ns=...)`. Parsing/transport uncertainty after a possible
write permanently poisons the object. `fail` records unknown; no reconnect,
resend, guessed COMPLETE or counter reset exists. `abort_unsent` is only for
proven never-attempted writes and burns a non-init request sequence.

The separated transitions do not block on IO. Root may drive them from its
contained IO actor while native motion/AI continue independently; there is one
inflight request because the actual791 server is serial. Root must bound actual
pipe read/write/syscall latency; this class is not an IO watchdog thread.
The request timeout is at most4s; init loading has an independent bounded30s
host allowance. `check_time` rejects monotonic regression, request/link timeout
and the actual command grant's100ms guard. Root must invoke its separate
one-shot owned safety tail/close transport on failure; this adapter performs
no side effects. Normal pending AI/observation never generates artificial STOP.

apply sends quantized direction and speed. Speed0 with zero yaw/pitch is a
resumable pause and still requires real measured zero-speed PWM and a finite
TTL. stop/shutdown are terminal one-shot STOP writes, explicitly not proof of
zero physical PWM. FAST curvature and speed20 are preserved. Only exact build
dc4e89ccf3db18c4f9871575efc399ba permits12000ms; other builds retain3000ms.
Positive/pause replies require full32 unsigned capture words, identity/seq/tag,
50MHz TTL, measured words15..17 ±1tick/period/local edge witnesses and chronology.
Echo metadata alone is rejected. Full13 identity/release raw receipts remain
Root journal obligations: the791 reply does not contain them, so this adapter
cannot independently establish that lifecycle from JSON alone.

Grant mapping never equates board/PC absolute clocks. It uses original local
send lower bound + returned board remaining duration - Root-supplied proven
clock-error upper bound, debiting the whole round trip conservatively. Default
error0 is a synthetic/unit-test convenience, not evidence that real clock error
is zero. Root must supply a justified bound before using any mapped time for
motion; returned DetachedReply has authority='none'.

No task-total timer/command/scan/IO count cap or retained history list exists.
Current ticket/reply counters are bounded. Real uint32 counters, uint16 E4 frame
sequence (four frames/sample,16383 samples) and32-bit microsecond acquisition
fields remain intrinsic exhaustion boundaries. Root must explicitly hand off
to a new owned identity/session before those boundaries, preserving cleanup;
there is no transparent reset or pretending finite hardware is infinite.

`map_quality` explicitly checks original EM/hold/null consistency and maps only
validity/saturation/fault bits into791. Root retains original quality/sample
bytes and accepted pose. C3 null never becomes zero. The first milestone checks
sense metadata and bounded raw four-frame envelope and returns detached bytes;
independent causal E4 CRC/decode/lossless comparison in continuous flow is the
next milestone. The server correlation label is not independent B evidence.

The subsequent pure `e4.E4Stream(binding)` supplies that independent wire check.
Pass the original `Ticket` and `DetachedReply` from `ContinuousWire.finish` to
`accept(ticket, reply)` in the same IO owner, before allowing any observation
consumer or subsequent motion decision. It returns immutable `E4Observation`
with counts (including null), original source fields, request/response/wire
hashes and a detached per-frame byte/bit ledger. Each four-frame batch is checked
against original791 E4 header/revision2/CRC and the read-only golden payload
decoder at Git object aedf2c363d8d4ca69ec8281bf315428619231968 (also exact A e0b3).
All four reconstructed values, quality flags, source index/session and time must
match. Legacy decoded tick_ms names contain microseconds here; explicitly named
request adc_tick_ms/em_tick_ms remain milliseconds. Server decoded JSON must
match the independent reconstruction, including exact bool/int distinctions.

The first hardware result/RX cursor may be nonzero; within and after it, IDs/RX
must be contiguous, tags/source/request sequences monotonic, EM time increasing
and ADC time nondecreasing. Only previous cursors are stored. Bad authorized-owner
acceptance poisons the E4 stream without replay; unauthorized-thread rejection
leaves its state untouched. On E4 rejection Root must retire this adapter pair
and execute its distinct owned safety policy; an already finished protocol ticket
cannot be retroactively failed or resent. Do not continue APPLY on that pair.

`E4Stream` receives no original response envelope or authenticated source. Its
response hash is a correlated label from the protocol layer, not independently
recomputed original response bytes. Root retains those original bytes/binding,
actual accepted-pose source snapshot/digest and numerical causal provenance.
Both parsed records retain authority='none'. The count1 E0 raw/sample/whole-wire
ledger is actual byte accounting; it claims no compression ratio, board run,
source authenticity, throughput or formal100ms qualification.

No board, continuous-motion or formal product acceptance is claimed. This
module must not be hot-swapped into an active A process; A reviews/freezes/
integrates it and supplies real current evidence under the new scope.
