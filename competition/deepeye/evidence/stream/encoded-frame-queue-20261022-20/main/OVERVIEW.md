# Operation20: bounded encoded-frame storage candidate

The new synchronous queue stores two complete encoded frames in two256-byte
banks. It exposes each frame only after sealing, preserves metadata and byte
order under backpressure, rejects malformed length/last framing into a held
poison reservation, and lets earlier complete frames drain. Reset/cancel and
saturating diagnostic counters follow the frozen pre-edge contract.

Main accepts this internal RTL simulation increment only. The author job
child-a65d74a1ffed41f0a5a81cbb8555e189 actually completed/nonstale; its original
723files and233final-run artifacts were independently rehashed. Author evidence
retains23standalone cases/10949checks, one small-width case/195checks, three
composition cases/1102checks and three exact guards. Earlier author compile/TB
failures remain in author/smoke. Author original218runner checks are historical,
not qualification of the repaired Python runner.

Main actual ModelSim SE-64 10.7 /2017.12 evidence:

- 562178standalone edges, all2048legal framing combinations, all256byte values,
 more than1000wraps, representative malformed descriptors and complete2..16
 early-last positions; zero public-port mismatches.
- 358edges each at STAT_W2and3; actual transaction-path counter saturation.
- 130783new composition edges:14source admissions,11complete retirements,
 93148edges with two complete frames held,93423full-backpressure edges,
 RAW5/Rice7/source-error2/full256-byte3, and three canceled phases.
- Three clean exact guards0/1/33. Initial main guard runs had39missing-port
 warnings each; their original results remain and are superseded by guard*-02.
 The guard top alone changed. The two functional top byte sequences are exact
 matches to their executed snapshots. Current stricter diagnostics reclassify
 the unchanged non-guard logs; those commands did not rerun.
- Two actual compiled mutations: premature metadata and ignored cancellation
 produce11and25numeric mismatches on35frozen edges. The identical healthy
 control passes. All40accepted main tool commands have actual process receipts.

Main found165misaccepts among205frozen synthetic runner probes: foreign
plain/case-varied diagnostics and malformed additional structured records.
Only Python classification and hidden-process launch changed; final RTL/TB are
unchanged. The same205cases now agree exactly, including12real-log controls.
Eight real Python entrypoint processes with explicit synthetic vendor seams
return0,1,1,1,1,1,1,1 and test selected-case failure propagation, timeout,
exit17, missing output and foreign/malformed logs. These are not vendor runs.
Main inspected the runner before freezing the detailed probes and is the repair
implementer/evaluator; independent coordinator acceptance remains pending.

Preserved main preparation issues: first mutation pattern assumedCRLF and
stopped before any mutant write; two relative-path mutation launches failed
before compilation; corrected absolute-path runs are separate. The first
synthetic log harness omitted universal-newline decoding and rejected all12
controls; its original cases/results remain and do not qualify the runner.
The corrected immutable fixture set was frozen before editing author code.

Reproduction is in main/README.md and main/qualify_runner20.py. Run the latter
against the retained immutable fixture set with a fresh --out directory; do
not run --freeze over existing evidence. New entrypoint probes are documented
in main/runner_entrypoint_probe20.py. Private process wrappers use original B
paths; the product main verifier accepts --root. Raw traces are delivered as
lossless gzip envelopes with raw/gzip hashes. Original raw traces, generated
tool libraries and waveform files remain local. LOCAL_ARTIFACTS_EXCLUDED.json
names every omitted file and reason; author723-file manifests describe that
original local audit, not723remotely published files. Exact published selection
is the handoff manifest. No original file was deleted or altered for packing.

The8-root-card matrix is COMPLETION_MATRIX.md. All8659old tracked bytes and
the protected dirty codec input remained unchanged at the precommit audit.
Only six new source/doc/test/tool paths and this new evidence tree are selected.

DEEPEYE-HUMAN-LOCK-20261014/revision1 H01-H15, requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804,
contract pinf5989cd5defce561f9ba98e6b18fc2682945f0a2 and frozen design
1011259415a0916054eb580687612580bc1e5f09 remain unchanged. All29/G05/B06/R03,
full-product simulation, synthesis, implementation, timing, CDC/RDC, board and
system remain not_run. No public TRACE/codec/register/HWH ABI, BOOT/clock,
physical TTL/freshness, ENABLE or motion authority. A alone operates the board.
Full3D/UI/solid collision/free camera/editable/random layout/equal blue-red
gates/full passage/hidden truth/causal observation/substantive online3D PC AI
and both H12 control paths remain mandatory.
