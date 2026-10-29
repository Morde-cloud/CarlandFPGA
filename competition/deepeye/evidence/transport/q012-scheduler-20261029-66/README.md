# B bounded Q0/Q1/Q2 descriptor scheduler (66)

Source `0d8397f2af048f59e9b1a261cc80a0671d0942dd`, RTL SHA256 `d7cfe903ca6bb904fbf21f5207eac694638741f02bd48dd0ff3785becf97e740`.

The new single-clock core has three bounded FIFOs, explicit full backpressure, a stable offered head, credit deduction on handshake, packet-service fairness, explicit flush and saturated counters. Descriptor bits are opaque. Queue heads include held offers. Reset clears state/counters; flush cancels unsent queued/offered descriptors. Mask/enable gate new offers; they do not cancel held offers. Credit load is refused while an offer is held. Already accepted downstream data cannot be recalled.

The quality main froze an independent oracle before executing the author RTL. It found an idle invalid-cost `in_ready` mismatch at cycle 2867. The adopted source fixes only that raw-format predicate. The unchanged oracle then compared 71,650 public-port samples: 7,165 cycles, two samples per cycle, DEPTH 1/2/3/4 with STAT_W 8 and DEPTH 4 with STAT_W 2. A real RTL configuration mutation (MAX_Q0_BURST 999 versus expected 3) fails at cycle 52. Tool exit 0 alone is not acceptance.

Original author source f426c9fa... and its six-case pass, two harness repairs, manual attempts and main failed run remain in the raw bundle. The author six-case pass does not qualify the adopted source. All main vendor Jobs reached terminal, empty and closed states. This is bounded simulation evidence, with no formal or arbitrary-parameter proof.

This core does not implement wire serialization, public BOOT/calendar semantics, source eligibility, TTL, complete measured wire cost or wall-clock delay guarantees. Callers must supply those separately. B04/root-card, synthesis, implementation, CDC, board, system latency and full H12 acceptance remain not_run. Runtime authorization is none.

Reconstruction: concatenate raw/raw-evidence.tar.gz.partNNN in numeric order, verify BUNDLE_INDEX.json, then read the gzip tar. It preserves original commands, vectors, traces, negative controls, process receipts and failure history without vendor compiled libraries. Paths in original commands are provenance and must be remapped to a new owned directory before any separately authorized reproduction.
