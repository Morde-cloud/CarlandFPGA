# B56 original synthesis journal supplement

Task DEEPEYE-IMPLEMENTATION-20261014/v1; work B-B56-JOURNAL-SUPPLEMENT-20261026-58-v1. This is a new local byte supplement for
A comment6394985024 on PR30. Main01a13b55-095b-7461-8dd5-5476a130bd82
retains decisions, acceptance and publication. The original archive, manifest,
bit/HWH and README are retained byte-for-byte.

The existing publication-v2 archive actually contains **74** `56/r5/` regular
files. Its SELECTED_RECEIVER_FILES.json lists **80** files. The disclosed
board JPEG exclusion accounts for one; five original synthesis `vivado.jou`
files were also omitted. The original README and RAW_INDEX summary claiming
79 already-published receiver files were therefore incorrect. Their original
bytes remain unchanged as historical evidence.

This supplement adds those **five original files**, totaling **7,366 bytes**.
The reconciled receiver set is **74 current + 5 supplied = 79**, with the
3,840,574-byte board JPEG still excluded. The existing archive remains at74;
79 describes the union when this new supplement is applied. No new archive,
build, simulation, regenerated journal or board result is claimed.

| Original synthesis run/journal | Bytes | SHA256 |
| --- | ---: | --- |
| `private_diag_axi_gp0_imp_auto_pc_0_synth_1/vivado.jou` | 1546 | `a86df8afd74a7c3c341c77ed8ea860c33a4a2ab00c649affee754a77996daa71` |
| `private_diag_private_diag_0_0_synth_1/vivado.jou` | 1511 | `467d0cd87200e97b5c2603105585d03a82fab5fc6e50af307cfa93799b14b99b` |
| `private_diag_ps7_0_0_synth_1/vivado.jou` | 1448 | `75f29f28c1f43c2aacab3c75c335f08e52e45512d26ce65e0841ef17c6637787` |
| `private_diag_rst_fclk0_0_synth_1/vivado.jou` | 1476 | `5e8a51b93bfbbbb70f2355e1711f58e41c79ae181c8b10ce283d8684329da855` |
| `synth_1/vivado.jou` | 1385 | `3700587b416503e8e12720ea7f846945d3bdc0a1430e71e44ddcd9d86cb53fe2` |

Each file is placed under its exact `56/r5/project/private_diag.runs/...`
receiver path. INDEX.json records the original absolute/relative path,
canonical manifest entry, receiver path, size and SHA256. The original root
is `D:/pynq/CarlandFPGA/.local/b56/competition/deepeye/evidence/diagnostic/r5`. All five original bytefiles match both the
canonical build manifest SHA256 `e906b1517d328e05b123346ea71c0c5c7c6552be7baa31dde2eb42833f0ef13a` and the80-entry selection.
No missing journal was regenerated.

The bounded audit verified all2304 regular members against the original raw
index, the nine ordered archive parts against their recorded hashes and whole
gzip, the74 actual receiver entries against the80-entry selection, and the
five original journals against the canonical manifest. It performed reads,
hashes and copies into new directories only. Actual command/stdout/stderr,
process exit and before/after original hashes are preserved privately at
`.local/deployment/node-b/evidence/b56-journal-supplement-20261026-58/`.
This supplement contains exactly five journal files, INDEX.json and this
README; the index/README are not additional receiver payload files.

Parent operation B-DEEPEYE-PRIVATE-PL-DIAGNOSTIC-20261025-56, request
`d0600ae268ac1e870bd257257a85e4fda1e022aa41c51cc48465f051dad8d36a`,
tested head `20321845e0913151c1ad879908cb9f8af76ac052`, source
`222546acbb66bcd5ebde7d8cbe55c929173ae9b4` remain the original bindings.
No previous build failures, warnings or acceptance limits are rewritten.
This corrects evidence completeness and makes no new runtime acceptance claim.

DEEPEYE-HUMAN-LOCK-20261014/revision1 H01–H15 and requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, frozen design `1011259415a0916054eb580687612580bc1e5f09`, remain unchanged.
Only A operates the physical board. FullH12/all29/R03 acceptance is outside
this supplement; no service, credential, queue, peer/group, Git commit,
publication or other-agent action was performed.
