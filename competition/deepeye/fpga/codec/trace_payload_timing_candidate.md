# Staged preflight TRACE payload candidate

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`, work
`B-TRACE-PAYLOAD-PIPELINE-20261024-42-v1`, operation
`B-DEEPEYE-TRACE-PAYLOAD-PIPELINE-20261024-42`. Main
`01a13b55-095b-7461-8dd5-5476a130bd82` owns the optimization design,
independent review and acceptance. Main42 spec SHA256 is
`1db67ba822c5daeec8cb664d6fda49b8e9fb0a9ef78d4c717b8dde57af4a2bfd`.

Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01–H15, remains fixed at
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`; canonical requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen design `1011259415a0916054eb580687612580bc1e5f09` remains mandatory,
including full 3D/UI, solid collisions, free camera/layouts, equal gates and
full passage, hidden truth, causal observations, online 3D PC AI and both
control chains. A alone operates physical hardware. All 29 formal cards are
`not_run`.

The separate module `deepeye_trace_payload_timing_candidate` derives from
published original38 SHA256
`fb64ace453c451838110c81bf6cb4a815a96fb2668e28a306ff699beca5acef6`.
Its port header, payload layout, errors, byte choice, sample retention,
core drain/discard, reset/cancel priority and output backpressure are kept.
The published candidate and core are unchanged. This candidate is not adopted.

Only main-selected preflight staging changes the datapath. States 0–10 keep
their encoding, with `SPAN=11` and `ENDPOINT=12` in the existing four bits.
The accepted configuration enters SPAN. That edge registers the original
24-bit count-minus-one times stride products, 65-bit age, and basic-bad flag
covering count/E/strides/quality/source checks without endpoint carry. The
ENDPOINT edge registers 33/65-bit endpoint carry flags from those registered
products, holding products/age/basic-bad unchanged. CHECK consumes basic-bad,
the endpoint flags for count>1 and registered age. All added registers reset
or cancel synchronously. No core configuration/sample or metadata output is
allowed during these three preflight states. The successful configuration
path has exactly two additional internal cycles; cycle equivalence is not
claimed. The remaining FSM and value datapath match original38 exactly.

The author runner explicitly reuses original38 fixture/model coverage,
including the eight published manual byte vectors, RAW/Rice, byte ties and
E>0 originals, endian/padding, quality/held-age/overflow/budget and errors.
The new public-port TB additionally asserts preflight gating and adds an
immediate post-configuration abort for the SPAN edge. Existing configuration
offsets cover ENDPOINT and CHECK. Both reset and cancel on each edge are
followed by fresh recovery. No internal DUT states are acceptance oracles.
Full public trace, strict numeric/counter/order/terminal reconciliation and
saved negative parser probes remain in use; vectors are reused evidence.

```powershell
& D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 competition/deepeye/tools/codec/run_trace_payload_timing_candidate.py --output competition/deepeye/evidence/codec/trace-payload-pipeline-20261024-42/author/functional-01 --modelsim-home D:/modelsim1/win64 --thread-id 01a16a34-b419-7942-9a7b-2b033142446b --turn-id 01a16d02-c5c3-7d13-b6a0-33fbef8a6a1b --job-id child-603a06058b8f4c2585bed67111a5aa87
```

Only after functional success is exactly one separate candidate Vivado OOC
invocation authorized, using unchanged pinned Tcl, two exact RTL snapshots,
xc7z020clg400-1, two threads and a diagnostic 10 ns clock in fresh `.local/b42`.
No old40 run is repeated. Actual commands/PIDs/exits, source/tool/report/DCP
hashes and every warning are preserved. Negative WNS and I/O timing gaps are
retained. The main independently reopens and compares the DCP later; no
automatic timing repair, further OOC run or timing waiver is authorized.

This remains a candidate: no public TRACE ABI/type7 enable, BOOT, source
clock/authentication, motion authority, implementation, place/route,
bitstream, CDC/RDC, board, full B01/B06/R03 or system acceptance is supplied.
