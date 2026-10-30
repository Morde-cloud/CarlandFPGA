# B74 bounded synthetic executable data path

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, operation
`B-DEEPEYE-OFFBOARD-CODEC-EXECUTABLE-20261030-74`. A09 supersedes A07's
withdrawn encoder selection. Reuses B73/source
`0a35e06248073564baab65706c6c30d89069db54`, PR30 head
`d201499c513cf7172bd121c0e874fce3991bb175`.

The separate `deepeye_SYNTHETIC_codec74_fixture` copies the existing top's
data wiring and association predicate, omits G05, and exposes explicit fixture
profile/transport/result-ready gates. Its clock 50 MHz/baud 5 M are simulation
parameters only. It instantiates the existing buffered raw scan capture,
scan lane stream, raw block payload adapter, **one** TRACE inner encoder,
wire serializer and UART. There is no alternative encoder, double encoding,
production `force`, planner invocation, clock setting, pin assignment or board
operation. The production top retains hold 1/profile 0/transport 0/BAUD 0.

The only edits to existing files are explicit `input wire logic` net
declarations in the owned top and UART wrapper, required by ModelSim 10.7 with
`default_nettype none`. Widths, directions, logic, parameters and gates are
unchanged. The original host semantic decoder and payload adapter are unchanged.
The default closed full production top was not simulated or released.

## Actual evidence

Local evidence root:
`.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-74/codec-worker/`.
See its `RESULT.json` for exact selected source hashes, tool hashes/versions,
commands, stdout/stderr, exits and Windows Job receipts.

* `attempt-04/mode0/`: actual four singleton frames from the same labelled
  `SYNTHETIC_raw4.json` raw batch. Independent sampling of the external UART
  line equals accepted serializer bytes. Four result stalls hold valid/data;
  a wrong source tag stalls and preserves the raw lane. Mode0 completed
  15,546 cycles and 150 bytes, but the overall attempt failed runner
  qualification and remains failed.
* `attempt-06/semantic/`: software-only positive execution over those saved
  actual bytes. Four `B74_SEMANTIC_FIXTURE_V1` records wrap the existing strict
  decoder view without renaming fields. Each includes exact wire hex/hash,
  actually serialized canonical companion bytes/hash/length, original input
  file/hash and decoder pins. Actual `decoded_value` values 32769, 65280, 4096,
  65535 match independent original uint16 inputs. Original uint63 QPC above
  2^53, fixed origin, remainder 123/130/137/144 ns, opaque quality 128/254/85/163,
  source/trigger/sample identity and held source time are retained. The
  decoder still returns structural STOP/core_ran=false/command=null.
* `attempt-07/`: only previously unexecuted modes 1–3, dedicated runner
  failure/success controls and ten decoder rejection CLI processes. No
  repeated mode0. Cancel produces 5 received bytes, 6 serializer admissions,
  one transaction abort, 514 UART backpressure cycles with byte stability,
  and local empty/disarmed quiescence; release does not rearm/replay. Relative
  uint32 tick and uint63 source overflow each refuse with result error 4,
  refusal code 4 and zero wire bytes. Intentional RTL fatal exits 4; the separate
  no-codec success exits 0. CRC, partial frame, full identity, opaque quality
  overflow, flags mismatch, exact time, uint63 QPC, sequence nonwrap, index
  mismatch and relative overflow each actually exit 2.

Attempts 06 and 07 each exit 0 with their own exact before/after source snapshots
unchanged, no timeout and whole Windows Job observed empty/terminal before
handle close. Execution preceded any later source commit: **no later commit
is claimed tested**. Mode0's exact source is attempt04's snapshot; subsequent
bench completion/exit/stall-check refinements are in attempt07's snapshot.
Only the negative branches of the semantic test driver changed after 06;
its positive path and the existing semantic decoder did not change.

Failures 01–05, every raw log and explicit repair decision remain preserved.
01 was input-net compile failure.02/03 were a bench negedge polling bug that
missed an already accepted descriptor's ready pulse;03 added diagnosis only.
04/05 emitted the complete raw frames but failed Tcl completion qualification.
The remaining runner uses an integer completed flag, visible with `+acc`,
and a Tcl macro that propagates fatal failure. None of these overall failed
attempts is relabelled passed.

## Full serialized cost

|Channel|Wire bytes|Mandatory companion bytes|Total|
|---|---:|---:|---:|
|0|37|1970|2007|
|1|37|1970|2007|
|2 held|39|1969|2008|
|3|37|1970|2007|
|Total|150|7879|8029|

The 150 wire bytes include 48 outer header + 8 CRC + 86 payload metadata + 8 raw code
bytes. The companions carry all required opaque quality, full identity and
original ns timing/bindings, and are counted per frame without deduplication.
UART's 150 bytes alone require 1500 bits under 8N1. No physical serialization
format/rate is approved for the companions; 8029 is the serialized byte cost,
not a physical latency measurement. The eight original raw value bytes are
not a complete source-record denominator. This fixture does not meet or claim
the final 1%/100ms compression target.

## Reproduction under a new explicitly authorized operation

Use the repository's existing Python and ModelSim installation; no install or
service is needed. `prepare_fixture.py` regenerates the labelled test fixture
and bench from the top's data wiring and `tb_body.sv.inc`. The runner's `full`
phase compiles the new fixture and runs the small focused set. A `positive`
phase uses previously saved mode0 bytes; `remaining` runs only modes 1–5 plus
semantic negatives while reusing mode0 input hashes. Outputs must be a fresh,
owned repository evidence directory; never reuse an old attempt directory.

```powershell
& .local/venv/Scripts/python.exe -B competition/deepeye/tools/diagnostic/offboard_codec74/prepare_fixture.py
& .local/venv/Scripts/python.exe -B competition/deepeye/tools/diagnostic/offboard_codec74/run_codec74.py --out <fresh-owned-directory>
```

The actual commands and original cwd are recorded in each attempt's
`commands/*.json`. Native commands descend from the existing pinned suspended
Windows Job helper. Each command has 30 s, the whole Job 180 s, command records and
stdout/stderr a 16 MiB limit, and each fixture 100,000 clocks maximum. Waveform
logging is not requested. Whole-Job cleanup/terminal accounting is retained
even for failures. The output cap is polled during commands and does not cap
source snapshots or simulator library/WLF files; those are bounded here by
the small fixed source set and finite simulation. Saved actual file sizes
are in the final evidence manifest.

## Remaining boundaries

This is synthetic software/RTL evidence only. JSON labels/hashes are no source
authentication, actual ADC, BOOT, calibration or Root action/receipt proof.
Original source age is evaluated in exact ns; the stale control reports
149999877 ns/100ms=false with STOP and no command. A companion value mismatch
leaves actual decoded 32769 separate from original 1 and reports false match.
This helper does not establish a new stateful multi-frame anti-replay receiver.
Mandatory context transport, genuine aggregation, production activation,
synthesis/implementation/timing, shared bandwidth, full host control/retirement
and both complete H12 modes remain separate work/acceptance. A alone operates
the board. No R20/R21/original 100MHz failure or formal gate is weakened.

H01–H15 retain `DEEPEYE-HUMAN-LOCK-20261014/revision1`, pin
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, canonical requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
freeze `1011259415a0916054eb580687612580bc1e5f09`. Full 3D/UI, hollow edge cube,
solid collisions, free camera/layout/faces/equal gates and complete passage,
hidden truth, device-bounded causal observations, online 3D/substantive PC AI,
both H12 paths and every final formal gate remain required. Parent quality
main/A perform independent acceptance and Git/PR handoff.
