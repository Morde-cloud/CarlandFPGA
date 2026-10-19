# B ordered block-stream integration candidate

`deepeye_block_stream.sv` is a single-clock, two-slot integration wrapper for
the unchanged `deepeye_block_encoder`. It stores one complete raw block while
the older sealed block is fed to and encoded by the core. It is an internal
digital candidate, not TRACE, a public register map/ABI, a BOOT or tick source,
motion authority, B01/B03/full-system acceptance, or a board result.

Task DEEPEYE-IMPLEMENTATION-20261014/v1; operation
B-DEEPEYE-STREAM-RESET-20261018-09. Contract
DEEPEYE-HUMAN-LOCK-20261014/revision1, H01-H15, commit
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen design `1011259415a0916054eb580687612580bc1e5f09`. The core is
instantiated unchanged from operation08 delivery
`1c8ce8433b2adf5b50947b124f7397c603f7a978`, source
`4d244c5b4ed282dfa4ee610e6a2fa7b4d9ca4c40`, RTL SHA256
`870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5`.

## Interface and storage

The source contains the fixed port list: clock/reset/cancel; config
`cfg_*`; samples `s_*`; ordered metadata `meta_*`; payload `m_*`; occupancy
`level`/`filling`; and diagnostic counters `stat_cfg`, `stat_samples`,
`stat_ok`, `stat_error`, `stat_aborted`.

The wrapper owns exactly two raw sample slots of 128 x 16 bits, for 4096 raw
storage bits, plus finite per-slot metadata and control. There is no encoded
payload FIFO, dynamic queue, arithmetic or file IO in the wrapper. The core
and the two whole-block slots bound candidate storage. `cfg_tag` is opaque and
may duplicate; metadata echoes it. Payload is the unchanged internal MSB-first
encoder format, not TRACE.

## Admission, ordering and completion

`cfg_ready` is asserted only when no slot is filling and `level < 2`.
`s_ready` is asserted only while a valid configuration is filling. A config
handshake reserves the tail slot immediately, increments `level` and
`stat_cfg`, and latches count/E/tag. Count 1..128 with E in 0,1,2,4,8 opens the
slot for later sample edges. Invalid count or E seals an error1 slot in the
same admission cycle and accepts no sample. Config and sample cannot handshake
on the same edge from an empty or non-filling state.

Each accepted sample increments `stat_samples` and is stored at its declared
index. The expected `s_last` is generated from the latched count when feeding
the core. An early last or a missing last at the declared final index stores
that accepted offending sample, seals error2, clears `filling`, and rejects
implicit trailing residue until a new config. A partial block may remain open
indefinitely. No timeout drains or synthesizes a last sample. Attempts without
ready are not accepted and do not affect counters.

Only the oldest sealed success slot can start the core. Exact samples are fed
with stable data under core backpressure. Bad blocks never reach the core.
Error and success slots retire in admission order. A slot remains allocated
through its error-metadata handshake or successful final payload-byte
handshake. No cross-block metadata/payload interleaving is possible.

For every nonaborted admission, successful core metadata precedes payload and
has its admitted `cfg_tag`. Error metadata is canonical: original tag, error1 or
error2, and zero count/E/k/bits/bytes, `raw=1`, with no payload. Metadata remains
stable while `meta_valid && !meta_ready`; payload data/last remains stable while
`m_valid && !m_ready`. Success retires only at the accepted final-byte
handshake. An actual core error is forwarded canonically as an error
transaction, although validated sealed inputs should make it unreachable.

## Reset, cancel and counters

Reset and cancel are synchronous active-high inputs, with reset priority.
Either suppresses config/sample/output handshakes immediately. Reset clears
control, slots and all counters. Cancel clears control/slots and adds the
pre-flush `level` to `stat_aborted`, preserving other counters. Its
combinational outputs are gated on that flush edge, so output attempts cannot
handshake. Holding cancel does not repeatedly count a pending occupancy.

`level` includes reserved, partial, queued, encoding and emitting slots and is
limited to 0..2. All five counters saturate at `32'hFFFF_FFFF`. While
unsaturated and between resets, `stat_cfg` equals
`stat_ok + stat_error + stat_aborted + level`. Saturation can lose numeric
accounting but cannot alter data flow. Counters are diagnostic candidate
ports, not a public register bank.

The external consumer must observe the same reset/cancel boundary and discard
a partially consumed frame. No atomic rollback of already consumed bytes,
asynchronous kill, stopped-clock guarantee, CDC/RDC or authenticated epoch is
claimed. RAM contents need not be cleared, but a newly allocated slot writes
every sample location it subsequently feeds.

## Simulation evidence and limits

The checked configuration is ModelSim SE-64 10.7, with vlib/vlog/vsim exit 0,
zero compile errors/warnings and `TB_END pass` plus `TB_DONE`. The final clean
space-path run has 54 cases, 54 passes, 0 failures and 1,353,306 checks. It
covers 35 pinned-golden vectors (N1 and N128, all E, RAW/Rice/padding), 101
config handshakes, 2794 sample handshakes, 92 metadata handshakes and 2401
payload-byte handshakes. Directed cases cover two-slot fill/encode, 4096 cycles
of full-queue backpressure, back-to-back blocks and pointer wraps, ordered
success/errors, simultaneous allocate/retire, 1000-cycle metadata stalls and
1500-cycle byte stalls, all required partial/metadata/byte reset-cancel phases,
held cancel, final-byte competition and fresh recovery. A seeded randomized
schedule contributes 21,298 schedule cycles, 517 observed ready-stall cycles and
748 randomized valid-gap cycles. Nine counter-boundary checks are explicitly
separated as whitebox hierarchical deposits, not blackbox stream evidence.

The CLI `../../tools/stream/run_block_stream.py` requires explicit core,
wrapper, TB, golden, spec, tools, output and owned-root arguments. It pins core
and golden hashes, exports inputs to flat files, preserves command/exit/stdout/
stderr evidence, rejects pre-existing output, aliased inputs and output outside
the owned root, and requires positive completion markers plus absence of
negative markers. Full evidence and raw logs are under
`../../evidence/stream/stream-reset-20261018-09/worker/`.

This increment is simulation-only. No synthesis, implementation, timing,
resource, CDC/RDC, physical-board, whole-card, system, full TRACE, BOOT/tick,
motion or product acceptance is established. Only machine A may operate the
physical board. All H01-H15 requirements remain binding; this candidate is one
bounded integration milestone, not their completion.
