# Scan-record lane serializer candidate44

Task `DEEPEYE-IMPLEMENTATION-20261014/version1`, work
`B-SCAN-LANE-STREAM-20261024-44-v1`, operation
`B-DEEPEYE-SCAN-LANE-STREAM-20261024-44`. Design and independent acceptance
belong to main `01a13b55-095b-7461-8dd5-5476a130bd82`.

`deepeye_scan_lane_stream` holds one complete 448-bit record. It emits four
lanes in channel order 0, 1, 2, 3, copying the respective 16-bit sample,
64-bit tick, and 8-bit quality. It repeats the original 32-bit first/last
sequence bounds and tag on every lane. These fields are opaque. The module
does not calculate per-channel acquisition indices or assign source-clock,
session, epoch, quality or admission meaning.

There is no payload fall-through. An idle-edge input transfer first becomes
lane 0 after that edge. Input readiness while full requires a ready, valid
final output lane. A simultaneous final output and input transfer atomically
replaces the whole slot. Other output transfers advance the two-bit lane;
stalls hold the accepted record despite changes to unaccepted input fields.
`out_last` is true only on valid lane 3. `rst` and `cancel` immediately mask
both endpoints, synchronously discard remaining lanes and restart lane 0.
Invalid payload need not clear. These two controls affect only this module.
Capture stop/rearm and upstream queue cancellation remain independent.

The author runner uses static record-to-four-lane fixtures and an ordered
list of pending expected transactions, checking public ports before and after
every edge. It does not mirror the RTL holding registers. Directed vectors
include zero/max fields, nonmonotonic ticks, first bounds greater than last,
alternating tags, blocked changing inputs, full/empty transitions, final-lane
replacement, and reset/cancel on every lane with and without prior stalls.
The finite seeded mix uses `0x2026102444`.

The small integration instantiates unchanged published39 capture and queue
RTL (head `782ee8883bccd7aadb0343e3da670644d61843f2`, source
`05e70705176f67a92b157c9af985bc1e110a040e`) before the serializer. Its
literal sample/record/lane fixtures check boundary transport and preservation
across capture stop/rearm, serializer cancel and an empty upstream queue
cancel. This reuses 39's capture behavior and is not a new capture proof.

Run from the existing product tree with the repository Python environment:

```text
D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe tools/acquisition/run_scan_lane_stream.py --out evidence/acquisition/scan-lane-stream-20261024-44/author/attempt-01
```

Each attempt must use a fresh output directory and preserve failures. The
runner saves exact input/source/tool hashes, process argv/PID/cwd/exits,
stdout/stderr, native ModelSim transcripts and pre/post raw public-port
traces. Its saved-log checker requires anchored unique ordered statistics
and completion, actual TB finish file/line/time/instance, clean vendor
termination, and numeric equality of every counter with the actual trace
and fixture. Negative cases preserve original inputs plus altered logs or
reconstructable trace mutation recipes. CRLF is accepted. The Unicode path
probe checks saved-log grammar only and does not claim vendor filesystem
portability. Actual author results and limitations remain in the original
author directory; the final main review is described below.

Original author completion status: actual ModelSim standalone (5,287 cycles) and
39-to-44 integration (210 cycles) pass their transaction checks with zero
vendor warnings. The 74 planned saved-log negatives reject, but an additional
finish-provenance audit found six false accepts: duplicate/conflicting
finish, time, end-time or vendor-counter lines inserted before the valid
terminal block. That author assignment ended **failed**. The two bounded repair cycles were
exhausted; no further repair or vendor run was made. The original attempts
and the six actual counterexamples remain under the owned author directory.
The final author report records this blocker rather than promoting the
runner's narrower attempt-03 `pass` to a qualified result.

Main accepted the bounded RTL and repaired qualifier after a separate explicit
44r1 assignment. Only `terminal_stats` and its targeted `qualify` cases changed.
Every reserved finish/time/instance/end/counter token must occur exactly once
at its expected anchored position across the entire transcript. Main reran all
354 frozen repair cases (342 rejected, 12 accepted) and 88 additional cases
(82 rejected, 6 accepted), and verified 230 original plus 618 repair artifacts.
The first repair check exposed four incorrectly constructed no-op negative
fixtures; their bytes match positive baselines and remain preserved. Corrected
fixtures were frozen before the second check; the terminal parser fix did not
change. No vendor run was made for the qualifier repair.

The main reference was frozen before author RTL inspection. Fresh ModelSim10.7
checked 6,585 cycles, 13,170 pre/post rows and 121,907 public fields, including
1,170 accepted records, 4,268 emitted lanes, 412 discarded lanes and 773 final-lane
replacements. Four actual compiled mutants were detected: rotated ticks,
invented sequence increments, lost final-lane replacements and ignored cancel.
There were 20 actual main vendor commands and five simulations. An initial main
CRLF-regex failure was reconciled against those same raw outputs without rerun.
The frozen main reference also checked the author's existing traces; the
39-to-44 boundary carried 13 records, emitted 49 lanes and discarded 3 lanes.
This reuses the original 39 capture proof and is not a new physical capture claim.

The final decision is
`evidence/acquisition/scan-lane-stream-20261024-44/main/qualifier-review-01/RESULT.json`.
The original failed lease/results, six false-accept logs, fixture correction and
main audit-path/CRLF errors remain intact. Exact local transcript grammar does
not authenticate arbitrary logs. Separate operation46 diagnostic OOC is not
included in this software result.

H01-H15 remain fixed under `DEEPEYE-HUMAN-LOCK-20261014/revision1`, pinned at
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen design: `1011259415a0916054eb580687612580bc1e5f09`. All 29 formal
cards remain `not_run`. This candidate has no production ABI, TRACE enable,
BOOT, source authentication or control authority. No synthesis, OOC, timing
closure or board result is provided; only A may operate the physical board.
