# Main design — bounded uint16 inner-block RTL encoder

Task DEEPEYE-IMPLEMENTATION-20261014/v1; work B-BLOCK-ENCODER-RTL-20261018-08-v1; operation B-DEEPEYE-BLOCK-ENCODER-20261018-08. Base781be78d9da77a75ea711cf690eeea6523733d3a. This is a B-owned synthesizable module, not a new public ABI or final card acceptance.

Before implementation read all H01–H15 at contract f5989cd5defce561f9ba98e6b18fc2682945f0a2 and hash only requirements canonical JSON (ensure_ascii=False,sort_keys=True,separators=(',',':'),UTF8), fixed SHA256c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804. Final design1011259415a0916054eb580687612580bc1e5f09. Preserve full3D/UI/solid collisions/free camera/editing/hidden truth/causal observations/online PC AI/both control paths. Physical board A-only; no service/config/credential/queue changes.

## Read-only exact inputs

- golden/codec/codec_reference.py SHA2562e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5.
- golden/codec/integer_candidate_rules.json SHA256275525f2cf951d196d333171cb777c41aaeeedd5239689fe096f40055b7dbeb8.
- golden/codec/known_vectors.json SHA256c1eee67b73b8cdd449ac72b2a77c78f714eaf448b1216b16296488881ac10e99.
- Paths above relative competition/deepeye. Do not alter these sources or any historical vectors/evidence.

## Scope and algorithm

One outstanding block,1..128 uint16 samples, E actual value in0/1/2/4/8. Exact first sample anchor. D=2E+1; q=floor((x-p+E)/D), y=clamp(p+q*D,0,65535), next p=y. Signed arithmetic must not use truncation for negative nonmultiples. Residual/intermediate widths must cover full extrema. ZigZag z=2q if q>=0 else -2q-1. All16 k values0..15 considered; each quotient z>>k<=31. Pick smallest significant Rice body bit count, lowest k tie; choose RAW original sample words when minimum>=16*(n-1), including n=1 raw tie. No unbounded unary/escape. RAW restores originals, not quantized reconstructions.

Emit exactly existing inner-codec fixture bytes: anchor uint16 **MSB-first**, RAW originals **MSB-first**, Rice quotient zeroes/one/k remainder MSB-first, final low pad bits zero. Metadata carries full significant bit count and byte count. This is intentionally not TRACE payload: TRACE candidate uses little-endian word fields and stored-byte RAW comparison after minimum-bit k selection. Do not silently claim byte-compatible TRACE or add tick/mask/public framing.

Implementation uses only synthesizable finite sequential logic/fixed storage. No real/delay/file IO/DPI/initial stimulus/force in DUT. Prefer bounded serial arithmetic and cost/bit generation instead of giant unrolled combinational networks. Document actual memory/counter widths and processing upper bound. No throughput/resource/timing claim without measurement. Last sample acceptance to metadata valid <=20000 clocks (no reset/cancel), excluding input/output stalls. Output length<=256 bytes; no unknown bits on valid data/metadata in four-state simulation. One clock, no new CDC assumption.

## Exact module ports

module deepeye_block_encoder:
- input logic clk, rst, cancel. rst and cancel synchronous active-high, sampled at posedge; they take priority over all handshakes, flush an unfinished block and pending output. Ready/valid outputs gated low while either asserted. No stopped-clock or asynchronous emergency-stop guarantee. Reset/cancel source synchronization and consumers discarding an already partially emitted frame are integration duties.
- input logic cfg_valid; output logic cfg_ready; input logic [7:0] cfg_count; input logic [3:0] cfg_e. One configuration handshake at idle starts a block; no sample accepted in same cycle. Invalid count0/129..255 or E outside set returns error metadata, no sample/payload consumed. Held cfg_valid uses ordinary ready/valid semantics; any future handshake is a new explicit transaction, no authority implied.
- input logic s_valid; output logic s_ready; input logic [15:0] s_data; input logic s_last. Handshakes only after valid config. Exactly cfg_count samples required; s_last must be1 iff this is the last expected sample. Early or missing last causes length error, discards this block, emits no payload. While not ready all sample inputs ignored. Waiting for absent valid input is allowed; no timeout pretending lost input has arrived.
- output logic meta_valid; input logic meta_ready; output logic [1:0] meta_error (0 success,1 invalid config,2 length error;3 reserved); output logic [7:0] meta_count; output logic [3:0] meta_e; output logic meta_raw; output logic [3:0] meta_k; output logic [11:0] meta_valid_bits; output logic [8:0] meta_bytes.
- Successful metadata exactly corresponds to the block; RAW meta_k=0 (consumer maps this canonical internal value to fixture null). Error metadata: count/e/k/bits/bytes all0, raw=1, stable error. No payload for error; meta handshake returns idle. Success meta handshake precedes any payload valid.
- output logic m_valid; input logic m_ready; output logic [7:0] m_data; output logic m_last. Exactly meta_bytes payload handshakes, last only final byte. All valid metadata/data stable under backpressure. No new config until last output handshake (or error metadata handshake). Reset/cancel can abort any phase, then a fresh config can run; no stale tail/predictor/metadata from discarded transaction.

No additional top-level ports/parameters required. Use conventional logic declarations compatible ModelSim SE-64 10.7 and synthesis tools. All storage finite, reinitialization must not leak prior values; clearing memory itself is unnecessary if valid indices are correctly bounded.

## Ownership and execution

Only these new product paths in existing worktree D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014:
1. competition/deepeye/fpga/codec/deepeye_block_encoder.sv
2. competition/deepeye/fpga/codec/BLOCK_ENCODER_CANDIDATE.md
3. competition/deepeye/tests/codec/rtl/tb_block_encoder.sv
4. competition/deepeye/tools/codec/run_block_encoder.py
5. competition/deepeye/evidence/codec/block-encoder-20261018-08/worker/ (new raw logs, fixtures, commands, hashes; no main-owned evidence)

Root git is unrelated runtime repair; never write there except explicit owned paths. No git commit/push/PR, new threads/agents, peer/group, service or board calls. Do not write sibling private scratch paths. Put disposable compilation files beneath owned worker evidence directory and list original commands; only portable evidence enters final handoff. Preserve failed attempts under unique attempt subdirectories. Stop and report genuine unavailable-tool/ownership blockers without silently abandoning.

Python D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8. ModelSim D:/modelsim1/win64/{vlib,vlog,vsim}.exe discovered. CLI runner must accept explicit --modelsim-home, --rtl, --tb, --golden, --output so flat exported inputs/directories with spaces work without node-private files. Existing output must be refused; never overwrite input or old logs. Defaults may derive repo paths from own script location, but portable CLI must not rely on private controller files.

Use a real .do script with onerror quit nonzero and onbreak quit nonzero; inline -do strings can fail to execute those as macros. Require an actual completion marker plus inspected compiler/simulator results; a process exit0 alone is insufficient. Save stdout/stderr separately, actual version, argv/cwd/exit, raw port output and hashes. Do not normalize raw bytes. Do not rerun historical software suites; this assignment tests the new DUT.

## Completion criteria

Demonstrate new actual RTL simulation vs pinned golden for legal N1..128 and all5 E values, static/ramp/peak/extrema/noise, RAW/Rice, k ties, floor-negative cases, padding and independent consecutive blocks. Cover input gaps and metadata/data stalls, invalid E/count/last, reset/cancel in load/compute/meta/data, and next fresh block recovery. Bounded watchdog; no phantom handshakes/output, no overflow, no data change while stalled. Produce a machine-readable per-block record with inputs and observed metadata/output bytes, and handshake/error/reset counters so main can independently replay. Include negative/error tests, not only encode/decode using the same implementation. Worker may use pinned golden for expected bytes; main will independently evaluate arithmetic and raw port evidence. No board/B01/full-stream/synthesis/implementation/system PASS. Report exact changed files/hashes, actual commands/results, failures and unresolved gates to this main. Use [需桌面回合] or [需本人操作] only for a real corresponding blocker; do not self-escalate or message others.
