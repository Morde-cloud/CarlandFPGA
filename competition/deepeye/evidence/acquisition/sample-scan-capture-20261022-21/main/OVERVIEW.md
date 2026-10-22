# Sample-scan capture operation21

This internal one-clock candidate collects four consecutive channel0/1/2/3 events into one atomic output record. It preserves16-bit containers, per-lane opaque ticks/quality and window tags. Wrong order restarts or discards explicitly; a full stalled output drops the new scan without corrupting the old one. Sequence exhaustion processes its terminal event then blocks new input until rearm. Counters saturate without controlling flow.

The final RTL is fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d. Main independently ran165149 frozen edges, eight exact guards and two real compiled mutants through72 actual commands. The earlier18runs at9eadd35c remain separate; the final port clamp required fresh exact-source runs, with identical healthy traces. Mutants yielded11772/44108 differing checked fields, not independent test counts. Main's source-free ledger and inputs were frozen before dispatch;4096 finite strings received a second literal-string audit.

Final author source produced27 cases and820621 core checks. Main rehashed2676 local author files and strictly reclassified its56 saved commands, without claiming a new run. Main found40 false accepts in the final author's runner across92 probes, retained its exact original and repaired only the released runner. Same probes now agree; eight real Python entrypoints with explicitly synthetic vendor seams return0/1/1/1/1/1/1/2. Four actual selected vendor cases exercise the repaired normal/invalid/healthy/mutant paths with10new commands. Main inspected and corrected this runner; an independent coordinator review is still pending.

Reproduce from repository root, selecting a fresh output directory below this main evidence:

```
python -B -X utf8 competition/deepeye/tools/acquisition/main_verify_sample_scan_capture.py --root . --out <fresh-main-output> --case main64 --modelsim D:/modelsim1/win64
```

Other frozen cases:seq2,seq3,seq4,seq16,stat2,stat3,width1. Guards:guard-SEQ_W-1/33,guard-TICK_W-0/65,guard-TAG_W-0/65,guard-STAT_W-1/33 (supply each full case name separately). Exact commands and input hashes are retained per run. Main independent runner source hash f4b4290398df1f4d9a8f2327020fee7fe30f5f7d17e17df9a2338dfdbe7f8d40 is unchanged across these runs. Qualified author runner hash99748d791432cd0090e92b1e383670200fc3ead59ad3a6795af72f876e6d6b66.

Use main/frozen-inputs for original vectors/expected bytes. Raw trace gzip files are lossless, with raw SHA256 and byte count in each RESULT. Generated libraries/waveforms, duplicate expanded run vectors and raw trace equivalents remain local with an explicit omission inventory. Historical author report/manifest hashes refer to their original runner/doc, preserved under main/author-terminal; the new handoff manifest binds final corrected files.

Preserved failures include author smoke/TB/coverage/audit corrections, main's initial Git-normalization assumption, the main candidate-composer function-count failure and dependent absent-file probe, and all original runner red probes. No earlier operation or unknown side effect was replayed. All9829 old tracked raw bytes and the protected codec input are checked separately before commit.

Acceptance is strictly internal digital simulation and Python tooling. Full B02 acquisition/DMA/PS, physical100Hz/600s/G09, public sample_id/ABI/BOOT/clock, measured timing/freshness, ENABLE and motion authority are absent. All29/B02/G05/B06/R03/full-product/synthesis/implementation/timing/CDC_RDC/board/system remain not_run; board A-only.

DEEPEYE-HUMAN-LOCK-20261014/revision1 H01-H15, requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804, design1011259415a0916054eb580687612580bc1e5f09 remain unchanged. Full3D/UI/solid collisions/free camera/editing/equal gates/full passage/hidden truth/causal observations/substantive online3D PC AI and both H12 paths remain required.
