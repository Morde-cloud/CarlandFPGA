# B integer inner-block encoder

`deepeye_block_encoder.sv` implements one buffered uint16 block,1..128 samples,
with E=0/1/2/4/8. It uses the pinned integer reference: closed-loop mathematical
floor quantization, uint16 reconstruction clamp, ZigZag and bounded Rice,
minimum significant-bit cost with lowest-k ties, and original-sample RAW on a
RAW/Rice tie. Each block starts from its own exact anchor.

The output is the **internal MSB-first fixture format**, not a public TRACE
packet. TRACE's little-endian fields, metadata, stored-byte RAW comparison and
scheduling require a separate adapter and A approval. This module grants no
motion authority and does not implement session/clock/source authentication.

## Transaction interface

The exact port declaration is in the source and fixed main design spec in
`../../evidence/codec/block-encoder-20261018-08/main/main_block_encoder_spec.md`.
One cfg_valid/cfg_ready handshake latches count and E. Samples are accepted
later on s_valid/s_ready; s_last must coincide exactly with the declared final
sample. Invalid configuration returns error1, invalid length error2, each with
canonical zero-length metadata and no payload. A successful metadata handshake
precedes the byte stream. RAW uses meta_k=0. Count, E, RAW/k, significant bits
and stored bytes describe the complete output, including the anchor and padding.
There is one outstanding block; no new configuration until completion or abort.
Valid metadata and bytes remain stable while backpressured.

rst/cancel are synchronous active-high, with output handshakes gated while
asserted. They discard pending state/output; memory is not cleared, but all
subsequent reads use indices written by the fresh block. The parent must
synchronize reset sources and discard any partially emitted frame after abort.
No stopped-clock/asynchronous emergency-stop behavior is promised. Missing
input valid or permanently deasserted output ready can stall indefinitely;
no phantom sample or timeout substitutes for an input handshake.

## Bounded arithmetic/storage

Original samples128x16, residuals127x17, packed bytes256x8. Signed difference
uses18bits (x-p+E can exceed65535); divider magnitude/quotient17bits and
remainder6bits,17 shift/subtract steps. Rice cost accumulation13bits covers
all legal block costs. Byte count9bits represents256; significant count12bits
represents2048. The bit writer value is32bits, length6bits and byte fill3bits.
All loops, memories and unary fields are bounded. The source uses no stimulus,
file IO, real arithmetic, delays or DPI; actual synthesis is still unperformed.

Main BE01 corrected the original17-bit writer, which emitted unknown bits for
valid unary runs18..31.52 forced long-unary vectors now cover that gap. The
original rejected source and logs are retained rather than relabeled passed.

## Verification and limits

ModelSim SE-64 10.7: corrected828-case regression/7447 checks and independent
1559-case port review passed. The latter covers69312 successful-block samples,
26 invalid-input transactions,40 aborts/fresh recoveries and81264 stall checks;
expected bytes are independently generated without importing the golden model.
Worst observed last-sample-to-metadata processing latency is2084 clocks; main's
2095-clock measurement includes deliberate header holding. This is a simulated
cycle bound, not a measured100MHz implementation or end-to-end throughput.

The CLI `../../tools/codec/run_block_encoder.py` accepts explicit ModelSim/RTL/
TB/golden/output paths. Six-file export with spaces passed828 cases; preexisting
output and input alias are refused. Pinned golden/vector bytes are verified;
optional mirror-rule bytes are recorded, not a substitute for the golden pin.
Detailed commands, failures, source hashes and raw port logs are in
`../../evidence/codec/block-encoder-20261018-08/main/readme.md`.

Task DEEPEYE-IMPLEMENTATION-20261014/v1, operation
B-DEEPEYE-BLOCK-ENCODER-20261018-08. B01/B03, full streaming/TRACE, R03, synthesis,
implementation, board/system and complete3D/UI/AI acceptance remain open.
H01-H15 contract f5989cd5defce561f9ba98e6b18fc2682945f0a2, requirements
SHA256c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804,
frozen design1011259415a0916054eb580687612580bc1e5f09; only A operates the board.
