# B06 out-of-context synthesis qualification

This directory prepares bounded evidence for operation
`B-DEEPEYE-OOC-SYNTHESIS-20261024-33`. It does not implement or program a
device and does not grant product acceptance.

## Frozen inputs

- Task: `DEEPEYE-IMPLEMENTATION-20261014/v1`.
- Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1` at commit
  `f5989cd5defce561f9ba98e6b18fc2682945f0a2`; canonical requirements SHA256
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
- Frozen design: `1011259415a0916054eb580687612580bc1e5f09`.
- Source: `bbfb11439b35e0866a6d2486f3857b92ed6cf529`; handoff head
  `04e3a46eb1169afca0c133815a9b9f3da15d89f5`.
- Tool: `D:\pynq\AMD2026\2026.1\Vivado`, wrapper SHA256
  `a5f91ee867cea61be4355caf9f7a784c6c34351c5c1d1618562ddda299e38a8b`,
  executable SHA256
  `3a4e9e3f03d20cd1994dc2eff44566af7a10eaaae04429e9d460bffe3b0e86e4`.
- Part: `xc7z020clg400-1`.

The source inventory is the 18 tracked `*.sv` files below
`competition/deepeye/fpga/` plus the mailbox at
`competition/deepeye/rtl/control/deepeye_snapshot_mailbox.sv`, for 19 files.
The frozen scope names a non-existent
`competition/deepeye/rtl/deepeye_snapshot_mailbox.sv`; the runner records that
discrepancy and resolves the unique tracked mailbox path instead of editing or
moving RTL.

## Clock policy

Seventeen tops receive a 10 ns clock named `clk`.
`deepeye_snapshot_mailbox` receives separate 10 ns clocks on `src_clk` and
`dst_clk`. `deepeye_crc16_byte` is purely combinational: no fabricated clock is
applied. Input/output delays are unknown. Timing and `check_timing` reports are
diagnostic only and do not establish timing closure, calibrated I/O, CDC/RDC
signoff, place, route, a bitstream, or board behavior.

## Runner

Use the project Python environment from a clean product worktree:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:\pynq\CarlandFPGA\.local\venv\Scripts\python.exe -B `
  competition/deepeye/tools/build/run_ooc_qualification.py `
  --source-commit bbfb11439b35e0866a6d2486f3857b92ed6cf529 `
  --tool-root D:\pynq\AMD2026\2026.1\Vivado `
  --output competition/deepeye/evidence/build/ooc-20261024-33/author/<fresh-attempt> `
  --timeout-seconds 900 `
  --author-thread <actual-thread> --author-turn <actual-turn> `
  --parent-thread <main-thread> --parent-turn <main-turn>
```

The output directory must be a fresh child of the operation-author evidence
directory. An existing output is rejected; a failed output remains in place.

The runner reads source bytes with `git show` at the pinned commit and verifies
each Git blob and size. It validates the embedded requirements SHA256, the
design/source/handoff ancestry, the wrapper and executable hashes, the exact
native command path `C:\Windows\System32\cmd.exe`, and the requested part. It
then runs one hidden batch process at a time with `/d /c` and the exact wrapper:

```text
-mode batch -nojournal -nolog -notrace -source <owned-tcl-snapshot>
-tclargs <owned-run-dir> <top> <owned-source-list> <clock-policy>
```

Each top gets a separate process, fresh in-memory project, fresh working
directory, and TEMP/TMP/TMPDIR. `XILINX_LOCAL_USER_DATA` points to that run's
fresh owned `cache` directory; the Tcl compares the normalized environment
value with the exact expected cache before synthesis. `HOME` and the rest of
the inherited environment, including licensing configuration, are preserved.
`general.maxThreads` is set and verified as 2. Timeout is bounded to 1800
seconds. A timeout or failure before synthesis is a stop condition: the runner
does not replay or attach to any process. Ordinary independent top failures
are retained while later tops may proceed.

## Offline classifier checks

The bounded repair adds fabricated, in-memory negative fixtures. They do not
launch Vivado and do not represent successful synthesis:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
D:\pynq\CarlandFPGA\.local\venv\Scripts\python.exe -B -X utf8 `
  competition/deepeye/evidence/build/ooc-20261024-33/author/repair2/offline_classifier_tests.py
```

## Evidence and acceptance boundary

Each attempt contains `PREFLIGHT.json`, exact Git-byte source snapshots,
`SOURCE_MANIFEST.json`, the executed Tcl snapshot, and one `runs/<id>/` tree per
started top. Each run keeps the raw stdout and stderr byte streams, process
lifecycle and PID, exact argv, exit code, warnings/critical warnings, anchored
markers, utilization, timing/check-timing diagnostics, DRC and its violation
count, and a synthesis checkpoint. Required files are hashed; no warning is
suppressed.

A top is marked `artifact_complete` only when its actual process exits zero,
the anchored B06 rows match the one exact marker sequence, every marker field is
unique and structurally valid, source path/index identities match the frozen
snapshot, top/version/part/clocks/periods match, report and checkpoint paths
match, no error lines occur, and all reports plus the checkpoint are nonempty.
`write_checkpoint` uses its installed-help positional `<file>` argument; the
unsupported `-file` form is not used.

Artifact completion is deliberately separate from engineering acceptance.
DRC violation counts, latch/multidriver-related lines, all warnings and critical
warnings remain in `RUN.json` and `DIAGNOSTICS.json`; none are suppressed or
waived. `clean_drc` is reported separately, and timing is
`not_assessed_diagnostic_only`. `artifacts_complete` means all 19 isolated
synthesis artifact checks passed, not that DRC is clean, timing closes, CDC/RDC
is signed off, the combined design implements, or independent acceptance passed.

Never rerun a top merely to obtain a preferred result. Preserve failed attempts.
The runner does not invoke `xsetup`, uninstallers, updaters, MCP services,
hardware servers, place/route, bitstream/HWH generation, or the physical board.

## Main recovery after the first actual synthesis run

The original 19-top main run retained 18 completed synthesis artifacts and one
mailbox launch failure before source loading (`expected=4 actual=5` arguments).
The dual-clock launch token is now `dual_clock`, without a comma; its only mapping
is `src_clk` and `dst_clk`, each constrained to 10 ns for diagnostics. The main
recovery invokes the existing per-top launch/classification functions for that
mailbox only, with the same 19 pinned source snapshots. It does not rerun the 18
completed tops, erase the failure, or claim combined timing/CDC/product acceptance.
