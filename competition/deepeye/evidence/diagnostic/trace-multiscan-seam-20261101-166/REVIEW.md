# Current TRACE94 and multiscan147 integration conditions

The current A TRACE94/AXI endpoint cannot consume B147 unchanged. A accepts one4-lane scan and binds four count1 singleton frames; B147 accepts12 original records over three scans and emits four count3 blocks with index stride4. Host103 stages the former. Host147 prepares three original bundles and checks supplied bytes; it does not drive AXI or provide physical custody.

This new source review compares exact A commit99f51dd77b78f10b950fb04b6ffc9bcb717d49d0 (TRACE SHA25683b8c4beb48053ebc87ae27992d3b75eaae04562ff9f80c7f705a5f90efa9998) with B head27151ccfa335fabb3f590616d29c47a02cbebe76. Main checked9 categories and36 exact source references; one independent DeepSeek Flash/max worker completed, and main verified all14 source entries, own-file hashes, actual thread/turn terminal state and the cited prior receipts. This is source inspection, not a new runtime test or a product acceptance.

The main conclusions and next owner conditions are in MAIN166_SOURCE_REVIEW.json. MAIN166_ACCEPTANCE.json qualifies the preserved worker report: its suggestion to rewrite SOURCE_PINS.json is not adopted. The original author snapshot remains historical, as already specified by MAIN_REVIEW153; CURRENT_SOURCE_RECEIPT166.json links to the actually tested commit746e296ccfd39d1ba7db1e477879fcc33fabeea9, final freeze152 and current matching RTL bytes. Source-only comments in A files do not establish that A never ran a build. Parent fetched the A files from authenticated GitHub contents at the exact ref and verified Git blob identities; the worker itself only inspected supplied snapshots.

A-owned decisions needed before a B host transaction adapter:

1. Choose the endpoint and version its batch configuration/ARM and12-record staging contract; no new offsets are invented here.
2. Preserve original chronology/origin/native indices. A four-bit mapped status and B147 opaque uint8 quality are distinct; raw quality is absent from the wire and must retain its own companion provenance.
3. Define stable four-result IDs/ACK and exact receive-byte/FIFO custody. The existing A4096-byte FIFO is absent from B147, whose upload is a single ready/valid byte boundary.
4. Select and document TX/RX attachment, backpressure/error handling, cancel/clear and no replay. A currently uses internal UART loopback; that is not an external wire measurement.
5. Supply the selected current driver and source closure, packaged endpoint identity/layout, BUILD_ID and same-run bit/hwh/timing. The current Tcl packages TRACE94 from an external14-file list; adding an engine is not proof that it was built.
6. Provide actual ADC/board/source and C PC-AI/broker interface evidence before motion authority. A alone operates the physical board.

No B RTL, old pins, A source, host103 transaction sequence, queue/lock/service or credentials were modified. No tests, imports, compile, vendor build, MMIO or board action ran in this operation. B141 remains NOT STARTED. Existing B147 ModelSim171-byte/12-point evidence and B16246-case digital controls were previously delivered and were not rerun. No new B-only logic defect with a complete owner-approved interface was established; a transaction adapter remains a concrete next B task once A defines that contract.

All H01-H15/revision1, fixed requirements SHA256c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804, original29 cards, both full H12 routes and final100MHz/1percent/100ms/full3D/UI/PC AI gates remain. B all-complete and formal acceptance are false. The original21:00Shanghai preliminary demo deadline has elapsed without a received actual outcome or new A task in snapshot164; no deadline extension or failure outcome is inferred.
