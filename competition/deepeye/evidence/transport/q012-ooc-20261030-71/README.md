# Q012 standalone OOC synthesis (71)

The accepted descriptor scheduler SHA256 d7cfe903ca6bb904fbf21f5207eac694638741f02bd48dd0ff3785becf97e740 was read from exact committed source d0c9af304d86928af7d947e8ea38977b8b39e9b3. One new owned Vivado2026.1 build synthesized the default parameters (DESC64/CREDIT16/DEPTH4/Q0burst4/nonQ2burst8/STAT32) for xc7z020clg400-1. It exited0 without timeout, with the whole Job observed terminal/empty/closed.

OOC resource use is492LUT (324logic/168memory),223FF,0latch/DSP/BRAM. The standalone netlist has one ZPS7-1 warning because a PS7 is absent in this OOC core. No full-system DRC acceptance follows. All15 original reported files were rehashed, including the preserved local synthesis checkpoint. The selected public bundle excludes that large vendor checkpoint but retains its hash.

The synthesized timing estimate is WNS2.831ns/TNS0 at an internal100MHz clock, with external inputs/outputs unconstrained. This is not placed/routed timing or full-link latency evidence. Operation66's five tested simulation configurations remain their original scope; this default-parameter synthesis does not expand functional simulation coverage.

Raw bundle contains exact source, main authorization, Tcl, commands, actual tool/version log, reports and whole-Job process receipts. Reconstruct by concatenating ordered raw parts and verify BUNDLE_INDEX.json member hashes. The independent source66 simulation/negative controls remain in their original handoff. No wire/calendar/BOOT integration, rootB04, implementation, CDC/formal, board or runtime grant is claimed.
