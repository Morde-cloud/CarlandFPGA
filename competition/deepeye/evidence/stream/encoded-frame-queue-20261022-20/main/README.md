# Independent encoded-frame queue evidence

Operation `B-DEEPEYE-ENCODED-FRAME-QUEUE-20261022-20`, task
`DEEPEYE-IMPLEMENTATION-20261014/v1`. This directory starts with the main's
accepted-edge/list oracle and vectors, frozen before the sole author dispatch.
The source, vectors and `FROZEN.json` are historical inputs; later validation
must not rewrite them to fit the DUT. `MUTATION_PLAN.json` is a separately timed
extension frozen after dispatch but before reading the new author RTL.

The oracle imports no author module. It models an ordered list of at most two
reserved frames, while the implementation must use two finite 256-byte banks.
All transfers and credits are evaluated from the pre-edge state. Comparisons
cover every public status/counter and every valid metadata/payload field.
Inactive metadata and payload values are excluded; the initial uninitialized
observation before the first synchronous reset edge is excluded explicitly.

The standalone schedule contains 562178 edges, all 2048 legal byte-count/last-bit
framing combinations, all 256 byte values, repeated tags and more than 1000
pointer wraps without an intervening reset. It also exercises faults, full
credit rules, stalls, simultaneous transactions and reset/cancel. Separate
STAT_W=2 and STAT_W=3 schedules drive real transaction paths into saturation.
Default-width coverage is bounded and does not claim 32-bit saturation.

The new composition uses the unchanged op09 raw-block stream, which already
contains the unchanged op08 encoder. An independently expressed integer codec
computes expected RAW/Rice bytes from accepted source samples. The consumer is
held for 100000 edges to require complete encoded storage and backpressure.
Shared cancellation is exercised during input payload, sealed metadata and
output payload, followed by fresh recoveries. This is a new composition test,
not a rerun or enlargement of old test-suite claims.

Read-only composition source pins:

- `fpga/codec/deepeye_block_encoder.sv`: SHA256
  `870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5`.
- `fpga/stream/deepeye_block_stream.sv`: SHA256
  `c8f8c0d99769efc64a91402ee23e7157368ff90ec765db5c413f02546715fff4`.

From the repository root, run the new verifier with a fresh output directory:

```text
python -B competition/deepeye/tools/stream/main_verify_encoded_frame_queue.py --root . --mode standalone --out competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20/main/fresh-standalone
```

Other modes are `sat2`, `sat3`, `composition`, `guard0`, `guard1`, `guard33` and
`mutants`. The last additionally requires an isolated actual mutated DUT via
`--dut` and `--expect-mismatch`. A mutation counts as detected only after real
successful compilation/simulation and a numeric public-port counterexample.
Missing outputs, compile errors, unknown-valued traces and timeouts cannot
qualify as mutation detections. The tool path is explicitly
`D:/modelsim1/win64`; adapt that local installation path when reproducing.

Each actual run preserves exact source/checker snapshots, command arguments,
tool version, process identity, true exit status, raw stdout/stderr and hashes.
Raw trace gzip envelopes preserve the exact uncompressed bytes; both hashes
and uncompressed length are recorded. Raw local traces are retained even when
the Git handoff selects their lossless envelopes. Failed attempts remain
separate from later runs. Final acceptance must refer to explicit result files
and final-source hashes, not to this description or the author's PASS marker.

DEEPEYE-HUMAN-LOCK-20261014/revision1 H01-H15 requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
contract pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, and design
`1011259415a0916054eb580687612580bc1e5f09` remain fixed. This synchronous internal
candidate grants no public wire/register ABI, physical freshness/TTL, BOOT,
clock, ENABLE or motion authority. Synthesis, implementation, CDC/RDC, board,
system and all 29 formal cards remain not_run. Only A operates the board.
