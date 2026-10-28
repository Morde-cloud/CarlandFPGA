# Private G05 AXI diagnostic candidate

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; work `B-G05-PRIVATE-AXI-20261026-59-v1`.
H01-H15/revision1 requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, frozen design
`1011259415a0916054eb580687612580bc1e5f09` remain unchanged. A alone operates the
physical board. This new candidate has no public BOOT/ENABLE/motion authority,
and cannot substitute for R03, G05, fullH12 or any formal acceptance card.

`deepeye_g05_axi` composes the new strict mapper and external-capture engine.
The production top has no writable period/high-count/TTL-tick bypass. Output
bits are yaw/pitch/speed; inputs are six distinct top-level physical signals,
never internally wired from outputs. Candidate pins follow A
`5c192f34bad064b14e238747c2c569347257a62c` IO-map: outputs W14/Y14/T11 and inputs
V16/W16/V12, bank34 LVCMOS33. Actual board revision/wiring/clock/capture validation
is separate. No J3/I2C signals are allocated.

This document is an interface specification, not an executed validation report.
Use operation manifests for actual source/build/test states.

## AXI transport

32-bit AXI4-Lite, 12-bit byte address, one outstanding read and write response.
AW and W are accepted independently; full WSTRB `0xf` and aligned words only.
R and B remain stable during backpressure. Unknown, unaligned, partial-strobe,
read-only/write-only or state-disallowed accesses return SLVERR. Accepted bus
write is not proof of engine acceptance/application/capture. Reset is active-low
at the AXI interface, synchronous in the common logic domain; use PS reset
controller for correct asynchronous assertion/synchronous release at integration.

The HWH supplies the actual newly built IP/aperture; no old overlay address is
reused. Offset `0x2c` is intentionally unmapped. Clock64 live halfword reads are
diagnostics only and not atomic; the result latch provides coherent timestamps.

|Offset|Access|Meaning|
|---|---|---|
|0x000|RO|Magic `0x47303544`|
|0x004|RO|Private layout revision1|
|0x008|RO|Status: bound0, retired1, engine_running2, pending3, latest_eligible4, latch_eligible5, inflight6|
|0x00c|WO|Control: BEGIN1, COMMIT2, STOP3, LATCH4, ACK5|
|0x010|RO|Engine fault low8; wrapper fault next8 (bad command1, unknown control2)|
|0x014|RO|Last submitted command ID32|
|0x018|RO|Actual active engine tag low32|
|0x01c|RO|Latest engine capture sequence32|
|0x020/024|RO|Live local cycle low/high32, not host time|
|0x028|RO|Fresh identity bitmap bits0..12; command bitmap13..19|
|0x040/044|RO|Actual application tick low/high32|
|0x048/04c|RO|Immutable deadline tick low/high32|
|0x100..11c|RW before BEGIN|Full run_id256, word0 least-significant|
|0x120..12c|RW before BEGIN|Full nonce128, word0 least-significant|
|0x130|RW before BEGIN|Nonzero session32|
|0x200/204|RW live|Yaw/pitch signed16 bit pattern; upper16 must zero|
|0x208|RW live|Transport profile1 FAST or2 STRESS; upper24 zero|
|0x20c|RW live|Speed0..20; upper24 zero|
|0x210|RW live|Positive TTL milliseconds low16; upper16 zero|
|0x214/218|RW live|Nonzero increasing private command ID32 / opaque tag32|
|0x300..37c|RO while latch eligible|32-word immutable result below|

Private command/capture IDs32 are not public wire u16 IDs. An adapter must not
truncate them to claim public interoperability. Identity fields are actual PL
registers, not just host hashes. A waveform itself carries no nonce: temporal
post-application capture and the full operation/session ledger remain required.

## Session, command and stop

After reset, no session/command/output/capture is eligible. Explicitly write all
13 identity words, with nonzero run, nonce and session, then BEGIN. Only one
BEGIN is possible per hardware reset. Identity becomes read-only. The first
valid command locks the transport profile for this session.

Write all seven command words before each COMMIT; all must be fresh since the
previous accepted COMMIT or duplicate. Strict mapping includes signed range,
64-bit combined curvature and exact candidate PWM/TTL conversion. New command
ID must increase without wrap. The same ID and identical complete payload/tag
returns factual transport success without a new cfg pulse, reapplication,
capture rearm or TTL extension. Old ID or changed duplicate stops and retires
the session. Exact duplicate of an expired/retired command cannot reactivate.
New COMMIT while pending/inflight or a latch is held returns SLVERR; restaging
alone never changes the active command. A held latch must be ACKed first.

The old TTL remains in effect while a new command waits for the atomic frame
boundary. Expiry wins over application. New TTL starts at the actual simultaneous
output transition. A command shorter than the first full capture interval can
expire without yielding a valid result; it is not silently lengthened.

STOP is accepted even before BEGIN. STOP, bad command, capture fault, TTL expiry
or overflow retires the session. There is no CLEAR/RESUME write. New work requires
hardware reset and a new A operation/run/nonce; resetting volatile state is not
proof against cross-reset replay. Never automatically replay a failed or unknown
board operation. An AXI STOP processed on one edge reaches the synchronous engine
on the next edge. Actual engine stop/expiry bounds require exact-source tests.

## Coherent result read protocol

The engine continuously observes three independent synchronized external pins.
Its bounded latest mailbox can advance independently of host speed. LATCH copies
one entire eligible record; another LATCH cannot overwrite it. Monitoring and
TTL continue while held. ACK only clears the latch and never extends TTL.

|Word index|Value|
|---|---|
|0,1,2|Capture sequence, command ID, opaque tag|
|3|Profile bits0..7, speed8..15, upper16zero|
|4|Yaw signed16 low / pitch signed16 high|
|5|Original TTLms low16|
|6..7|Actual applied cycle64, little-word order|
|8..9|Original deadline cycle64|
|10..11|Latest joined-record event cycle64 (not acquisition/host time)|
|12..14|Raw yaw/pitch/speed periods32|
|15..17|Raw yaw/pitch/speed highs32|
|18..23|Raw start witnesses64 for yaw/pitch/speed|
|24..29|Raw end witnesses64 for yaw/pitch/speed|
|30,31|Session32 / magic|

Read live status and full immutable identity, issue LATCH, read all32 words,
then reread status, full identity, command and latch sequence. Require same live
session/command/latch and no fault before accepting. Capture sequence may advance
in the underlying latest mailbox while the held latch remains stable; compare
the held record sequence, not the latest engine sequence at0x01c. Decode measured
high counts independently, then compare requested codes and period tolerance.

STOP/expiry/fault/reset invalidates latest and latch eligibility. An already
issued AXI R response still stays stable under backpressure; it cannot remain
eligible merely because its bytes were returned. The second live status check
and A's external operation/generation ledger are mandatory. No result or flag
here establishes source freshness, physical calibration or motion permission.


## Main R13 unqualified payload preparation

R12 route still failed WNS-2.671ns/TNS-3634.927ns (1982 endpoints), hold+.034ns.
Its worst path ends at the cfg_ttl bank CE after external-capture fault and
COMMIT admission logic. R13 prepares cfg_period/highs/ttl/tag every clock in a
separate resettable bank. Complete legal COMMIT, cfg_valid, inflight, identity,
STOP and every control-state update remain unchanged. On each COMMIT edge,
both implementations snapshot exactly the same pre-edge mapper/staging bytes;
the engine samples them on the next cfg_valid edge. Unqualified private bank
contents may differ and are never a public observation, fault source or TTL
renewal. Engine pending/active snapshots remain immutable. No stage, latency
or protocol permission is added; independent public-port equivalence and
actual route remain required. The mapper and engine sources are unchanged.
