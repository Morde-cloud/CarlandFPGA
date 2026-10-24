# One-block TRACE payload RTL candidate

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`, work
`B-TRACE-PAYLOAD-RTL-20261024-38-v1`, operation
`B-DEEPEYE-TRACE-PAYLOAD-RTL-20261024-38`. Main
`01a13b55-095b-7461-8dd5-5476a130bd82` owns design and acceptance. Main spec
SHA256 `0545a23843e92f1c7f4bdeec0e268a2cbfb2a246c77c0ee7641db0162a48bc48`;
published base `0885ed48b9edc48be7fd20135e8c141a485218d4`.

Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01–H15, is fixed at
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`; canonical requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen design `1011259415a0916054eb580687612580bc1e5f09` remains unchanged.
Full game-grade 3D/UI, solid collisions, free camera/layouts, equal blue/red
gates and complete passage, hidden truth, causal observations, substantive
online 3D PC AI and both control chains remain mandatory. A alone operates
the physical board. All 29 formal cards remain `not_run`.

The adapter accepts one already selected uniform block with the exact ports
in the main spec. Configuration is latched atomically; the caller supplies
provenance, uniform quality, strides and a held source origin. It does not
split or select blocks. Invalid quality-only blocks accept no sample and do
not configure the inner encoder. Invalid configuration takes error1 priority;
bad sample length/inner error is error2; over-budget payload is error3.
Errors emit one zero-length/zero-tick metadata transaction and no bytes.

The unchanged production core SHA256 is
`4cb79428ef89096742e293516c4696caf985048d8185f531fe92eaa485c8d532`.
Its minimum-significant-bit Rice choice is followed by the specified stored
byte comparison: Rice only if its byte count is strictly below `2*count`.
Original accepted words are retained in a private 128x16 memory, so byte-tie
RAW writes original little-endian values even for E>0. Rice swaps the two
anchor bytes and preserves the remaining MSB-first body and padding.

Index/tick spans use a bounded 24-bit count-minus-one times uint16 stride;
the endpoints are checked in 33/65 bits. Held age uses 65-bit subtraction and
requires source before the first tick. Short ages 1..65535 use two little-
endian bytes; larger ages use an eight-byte absolute origin. Singleton
strides must both be zero. All count/quality/source rules are checked before
the first sample. Metadata length is 21/25 plus a 0/2/8-byte held extension.

A 32x8 private memory contains the full validated payload before successful
metadata is visible. Successful core output is fully drained, including RAW
fallback cases. Declared lengths, final marker and final padding are checked.
Rejects pulse a private synchronous cancel before exposing error metadata.
External synchronous reset/cancel discards the transaction and gates public
handshakes/last low; configuration remains unavailable until both units are
ready. Memories are not cleared and reads follow writes in the transaction.
There is no new asynchronous domain or RTL timeout policy.

The author testbench checks public ports only. Expected bytes explicitly reuse
the pinned `trace_candidate.encode_payload` model and compare the eight
published manual payloads literally. Coverage includes both published byte
ties, E>0 byte-tie originals, all E/quality/channel cases, endian/padding,
41/42 equal-point budget boundary, held ages and origins, maximal widened
endpoints and overflow, malformed configuration/final markers and error
priority, stalls and back-to-back operation. Reset/cancel sweeps are aligned
to configuration/sample/output handshakes, with Rice and RAW transactions,
followed individually by fresh recovery transactions. They exercise phases
without using internal states as an acceptance oracle.

The runner snapshots dependencies and source, preserves exact stimulus, and
records actual commands, PIDs, versions, stdout/stderr, exit codes and hashes.
The complete public trace records all configuration fields, sample/last,
metadata and payload on every post-reset clock. A pure strict parser checks
whole-line unique/order-checked records, continuous fixed-width trace rows,
numeric fixture agreement, all counters, abort recovery and exact simulator
terminal/time/instance/zero diagnostics. Malformed-marker and corrupted-trace
negative probes are saved. Existing or aliased output directories are refused.

```powershell
& D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 competition/deepeye/tools/codec/run_trace_payload_candidate.py --output competition/deepeye/evidence/codec/trace-payload-20261024-38/author/attempt-01 --modelsim-home D:/modelsim1/win64 --thread-id 01a16a34-b419-7942-9a7b-2b033142446b --turn-id 01a16a74-81a4-7973-a589-e6836a661fb1 --job-id child-bb04a8f43c384313bc9da87067a93d1a
```

This is candidate payload evidence only. It supplies no outer frame/CRC/UART,
ABI enable, scheduler, BOOT, acquisition authenticity, clock/TTL or motion
authority. No old data, golden model, public schema or core is modified.
No synthesis, timing closure, CDC, physical, B01/B03/B06/R03 or system
acceptance is claimed. Main performs independent review after the author
result; failed attempts remain preserved, with at most two bounded repairs.
