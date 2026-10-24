# Isolated TRACE frame candidate45

Work B-TRACE-FRAME-CANDIDATE-20261024-45-v1 composes the pinned42 payload
timing candidate and opaque28 serializer. Main owns design/evaluation/acceptance.
The top has no parameters and adds no payload storage or second reservation.
Epoch and sequence latch on the actual shared config handshake. Payload42
owns all its original config, sample validation, metadata and error1–3 behavior.
Successful metadata admits one serializer config with type7, latched epoch/seq,
metadata tick and length. Payload feeds the existing serializer; framed bytes
become visible only after the complete payload has been buffered.

Success result0 is held after the final framed-byte retirement and reports
14+payload bytes. It does not represent UART, peer or board acceptance. Error
results1–3 emit no frame. A serializer fault while active enters sticky FAULT
and holds one error4 result until acknowledgement; acknowledgement does not
clear the fault. Only external reset/cancel recovers. This guard cannot be
reached by legal public inputs through the unchanged42/28 pair; author tests
do not force internal state or claim dynamic fault-guard coverage.

Reset/cancel mask all top handshake outputs immediately and discard both
inner states synchronously. New config waits for payload42's CLEAR cycle.
Serializer fault diagnostics are direct aliases, including its registered
fault-event pulse. Previously emitted bytes, including a complete frame emitted
before a later cancellation, cannot be recalled. This module provides no remote
invalidation or rollback guarantee. Header fields are opaque and independent of
session and acquisition index; there is no implicit increment or mapping.

Author validation explicitly reuses published `trace_candidate.encode_payload`
for payload expectations. Header bytes and CRC are formed independently with
standard-library struct and binascii.crc_hqx(seed=0xffff), never serializer RTL
or the golden frame encoder. Raw public pre/post histories retain all inputs,
outputs and handshakes. Reset/cancel timing windows are derived from a saved
successful baseline's public sample/output/result timing and the known payload
length, with that reuse recorded. See author RESULT.json for actual runs,
failure preservation, measured coverage, parser negatives and source/tool pins.
No result is asserted solely by this note.

The frame is an isolated synthetic candidate fixture: A55A, version03, type07,
length, epoch, sequenceLE, tickLow32LE, payload, CRC16LE. Public A type7 remains
disabled and hardware_enable_eligible=false. This work changes no A/public ABI,
profile, sensor, UART, scheduler, acquisition clock, CDC or physical authority.
These sources remain isolated candidates. Separate operation47 records bounded
OOC synthesis diagnostics; no board or timing-closure claim follows.

H01–H15 remain pinned at f5989cd5defce561f9ba98e6b18fc2682945f0a2,
requirements c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
frozen design1011259415a0916054eb580687612580bc1e5f09. Full 3D/UI, solid
collisions, free camera/layouts, gates and complete passage, hidden truth,
causal observations, online 3D PC AI and both control chains remain mandatory.
A alone operates the physical board. All29 formal cards remain not_run.
