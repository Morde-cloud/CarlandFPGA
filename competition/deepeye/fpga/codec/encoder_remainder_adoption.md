# Remainder reconstruction adoption

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-ENCODER-REMAINDER-ADOPTION-20261024-37-v1`, operation
`B-DEEPEYE-ENCODER-REMAINDER-ADOPTION-20261024-37`.
Quality main `01a13b55-095b-7461-8dd5-5476a130bd82` owns the decision,
independent integrated comparison, OOC work and acceptance.

Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01–H15, remains fixed at
commit `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, canonical requirements
SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen design is `1011259415a0916054eb580687612580bc1e5f09`. Preserve full
game-grade 3D, volume collisions, free camera/editing, blue/red gates, hidden
truth, causal observations, substantive PC AI and both control chains. A alone
operates physical hardware. All 29 formal acceptance cards remain `not_run`.

The main-approved op36 reconstruction is adopted in `deepeye_block_encoder`
with the original module name and ports. Production bytes are exactly the
main's `EXPECTED_PRODUCTION_ENCODER.sv`, SHA256
`4cb79428ef89096742e293516c4696caf985048d8185f531fe92eaa485c8d532`.
The previous production source was SHA256
`870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5`.
Its exact snapshot and old/new diff are preserved in the author evidence
directory before application. The author applies this fixed design without
further optimization or changes to stream/queue/wrapper, ABI or testbench.

For `n=x-p+E`, `d=2E+1`, the restoring divider's absolute remainder becomes
`r_euclid=d-r_abs` only for negative nonmultiples. The main-derived identity
`p+floor(n/d)*d=x+E-r_euclid` replaces the multiplier reconstruction.
A synchronous 16-bit register captures each accepted nonfirst sample. The
divider, quotient/ZigZag, saturation, FSM cycles, metadata and Rice/RAW choice
retain the accepted op36 behavior.

The author runner compiles the exact production file unchanged under its real
module identifier, plus unchanged published op36 candidate and TB filenames.
It explicitly reuses the published op36 fixture generator, golden reference
and strict repaired `check_saved_run` function. It regenerates and verifies the
same original fixture bytes and checks all 297 valid cases, six invalid cases,
24 reset/cancel interruptions and 24 recoveries, including stalls, RAW/Rice,
all allowed E values and count bounds. This is reused bounded coverage.
The candidate comparator shares the adopted arithmetic; the main's separate
frozen-old-chain integrated proof provides independent comparison.

The runner binds dependencies to exact op36 Git bytes, snapshots all compiled
inputs, and records before/after hashes, actual tool versions, commands, PIDs,
stdout/stderr, exit codes and full strict trace reconciliation. Terminal
missing/duplicate/truncation probes reuse the same qualified checker. No main
oracle or main cases are imported. The trace omits candidate metadata/data,
configuration payload and `s_last`, so offline checking cannot reconstruct
those unrecorded signals.

Run with a fresh owned output directory:

```powershell
& D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 competition/deepeye/tools/codec/run_encoder_remainder_adoption.py --output competition/deepeye/evidence/codec/encoder-remainder-adoption-20261024-37/author/attempt-01 --modelsim-home D:/modelsim1/win64 --thread-id 01a16a34-b419-7942-9a7b-2b033142446b --turn-id 01a16a5d-732e-7753-b8cb-2a95f0b75e43 --job-id child-d3e4efec61394705a4d0bf0f15248044
```

Preserve failed attempts; at most two bounded fixes are authorized. Implemented
source and author software results are separate from integrated-wrapper,
OOC/implementation, timing closure, CDC, physical-board, system and formal
acceptance. The author does not run Vivado or publish this change.
