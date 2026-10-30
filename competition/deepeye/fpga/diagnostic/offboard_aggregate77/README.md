# B77 bounded three-scan aggregation

`DEEPEYE-IMPLEMENTATION-20261014/v1`, work/operation
`B-DEEPEYE-OFFBOARD-BOUNDED-AGGREGATION-20261030-77`.
Main design: `resume-74/AGGREGATE77_MAIN_DESIGN.md`. This is new work after
B74 source `4264eb954bb4c26cea80689e5c3bb68b9040b2b3` / evidence head
`d2f3d120c982147fa6a1aaa095a53c2918a4019f`. B74 remains sealed.

## Executable composition

The explicitly named SYNTHETIC fixture instantiates unchanged raw
`buffered_scan_capture -> scan_lane_stream`, then the new twelve-slot
collector and triplet adapter, then unchanged `trace_block_uart_50mhz`
(`payload_1us -> trace_payload_candidate -> one block_encoder -> serializer
-> UART`). No second encoder or already encoded input is present. The three
scans contain twelve original uint16 samples, including values above
32767 and 4095. Each of four frames contains three samples with original
index stride 4. The bounded raw worst case is 25 metadata + 6 code = 31
payload bytes, within the unchanged 32-byte limit.

The collector stores all twelve raw values, original QPCs, opaque qualities
and three original native first/last scan sequence pairs. It enforces lane
order, one nonzero tag, nonwrapping scan/index progression, uint63 original
time, relative uint32 microsecond range, constant per-channel quality and
regular nonzero uint16 microsecond stride. This first contract supports only
fresh, valid data with supplied held=false semantics; source QPC equals each
original acquisition QPC. Unsupported held, changed quality, irregular time
or identity is refused without successful output.

`batch_seal` is the fixture/Root completeness boundary, not authentication:

* Seal during COLLECT refuses code 7, including overlap with the final valid
  lane. Seal and every input handshake are mutually exclusive by contract;
  an overlapped offer is consumed as refusal, not as a successful record.
* Only a later seal in FULL, after twelve accepted records, opens output.
  FULL and all output phases hold input ready low. A thirteenth/new input
  remains upstream and is neither silently dropped nor replayed.
* Each offered triplet stays stable until adapter acceptance. The adapter
  separately handshakes its descriptor, exactly three raw samples and result
  retirement. The collector advances only on retirement and admits no new
  collection until all four results retire and a fresh rearm occurs.
* Cancel flushes collector/adapter/codec/UART and disarms capture. Release
  does not rearm. Explicit fixture rearm also clears upstream queue/lane
  state; no pending old lane is relabelled as new work. Local quiescence is
  not motion STOP, host ACK or world-action retirement. Emitted bytes remain
  emitted and a partial frame is invalid.

Lifecycle repair 3 adds a shared fixture `path_cancel = cancel || !enabled`
to capture/queue/lane/collector/adapter. Gate withdrawal invalidates the old
local data epoch. Restoring enabled alone leaves everything disarmed; after
quiescence and gate restoration the owner must explicitly assert both capture
and collector rearm with a fresh tag. A busy collector rearm keeps REFUSED 9
and combinationally cancels adapter/downstream work on the same edge, before
result/retire can handshake. Capture/lane remnants can remain blocked during
REFUSED 9; they are not a fresh epoch or quiescence. Recovery is explicit
cancel until quiescent, release cancel, then fresh capture+collector rearm/tag.
Do not use collector-only rearm to relabel blocked old input. This is an owner
protocol at a synthetic seam, not authenticated Root control or motion STOP.

Clock 50 MHz / UART 5 Mbaud and fixture enable are explicit synthetic
parameters. No production module or default gate was edited. All fourteen
unchanged dependencies in `dependency_pins.json` were byte-compared with the
fixed B74 source via read-only Git object access, and hashed before/after
execution. Production remains hold/profile/transport/BAUD closed; the
original 100 MHz path is untouched.

## New private host contract

`tools/diagnostic/offboard_aggregate77/multipoint_decoder.py` implements
`B77_THREE_POINT_COMPANION_V1`, profile
`B77-PRIVATE-THREE-FRESH-RELATIVE1US-V1`. The unchanged fixed TRACE decoder
(`a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642`)
alone interprets the code section. Old B74 singleton decoder and wrappers
are unchanged.

The companion contains the original uint63 origin, original receiver QPC,
complete stable host context, and exactly three records. Every record retains
channel/index, native tag/first/last sequence, original acquisition/source
QPC, exact remainder, opaque uint8 quality, original uint16 value, valid/held
flags and full original per-sample identity. The separate binding contains
profile/session/view/frame sequence/E/channel and the complete companion hash.
Each actually serialized envelope also includes original now-QPC. Hashes
associate these synthetic records; they authenticate no BOOT, ADC or Root
receipt. The actual decoded value comes from RTL bytes and is checked against
the independent original raw input. It is never overwritten with a companion
value. Source age is computed in original ns against the unchanged 100 ms
threshold. Results remain structural STOP/core_ran=false/command=null.

## Actual focused execution

Evidence root:
`.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-74/aggregate-worker/`.
Its `RESULT.json` records selected source/evidence hashes, exact argv/cwd,
tool versions/binary hashes, stdout/stderr, exits and whole-Job closure.

* Attempt 01 compiled without warnings and actually emitted four triplets,
  but overall failed because two runtime port-width warnings violated the
  strict log rule. This failure and its exact source/logs remain preserved.
* Repair 1 added an explicit 10-bit remainder net; modulo 1000 is always
  0..999. Attempt 02 passed all fourteen new RTL modes and twelve actual
  decoder rejection processes. Normal execution: 12 actual input lanes,
  4 collector blocks, 4 three-point frames, 18,396 cycles, 4 retirements,
  16,900 UART backpressure stall cycles; serializer and independently sampled
  external UART match byte-for-byte. The recorded packed block values,
  original QPCs/qualities/native identities are independently compared with
  all twelve original fixture records by the host control.
* Repair 2, found by final review, rejects Python's False==0 at binding E and
  record channel fields using strict integer checks. Attempt 03 ran software
  only over the saved actual attempt 02 bytes: final decoder positive plus
  two additional boolean rejection processes. No RTL was rerun for this
  type-only change. Attempt 02's original twelve negative outcomes retain
  its exact prior decoder hash; attempt 03 pins the final decoder hash.
* Main independently audited the original twelve points/CRC/Rice/RAW/identity
  and byte cost, then found two lifecycle gaps: enabled withdrawal cleared
  only the adapter and could strand WAIT_RETIRE, and busy rearm REFUSED 9
  could leave accepted downstream work running. Repair 3 implements the
  shared cancellation and same-edge invalid-rearm cancellation above.
  Attempt 04 compiled this **changed final HDL source** and ran only the three
  new lifecycle controls below. It did not repeat the closed fourteen-mode
  group or semantic software controls. Those earlier claims remain bound to
  attempt 02/03 snapshots, not to a claimed full rerun on the final source.

Attempts 02, 03 and 04 each exited 0, with unchanged source snapshots, no timeout,
and original suspended Windows Jobs observed terminal and empty before
handle close. Exact pre-commit source snapshots are the execution provenance;
no later source commit is claimed tested. Three deterministic repairs were
used, reaching the main's limit; no additional retry is authorized on failure.

|RTL mode|New focused control|Actual result|
|---|---|---|
|0|Four true triplets, offer/result/UART stalls|173 UART = serializer bytes, 4 retirements|
|1|Per-channel quality changes|Refusal 5 at count 6, zero bytes|
|2|Irregular original ns time|Refusal 6 at count 8, zero bytes|
|3|Held input|Refusal 1, zero bytes|
|4|Changed native tag|Refusal 2 at count 4, zero bytes|
|5|Reset native sequence mid-batch|Refusal 3 at count 4, zero bytes|
|6|Original uint63 overflow|Refusal 4, zero bytes|
|7|Seal incomplete collection|Refusal 7 at count 8, zero bytes|
|8|Seal overlaps last lane|Refusal 7 at count 11, zero bytes|
|9|Thirteenth/new input before and during output|Held until explicit cancel; four prior triplets retire|
|10|Cancel before seal|Zero bytes, empty/disarmed, no automatic replay|
|11|Cancel during UART|3 received bytes + partial fourth symbol, 4 serializer admissions, 1 abort, 0 retirements|
|12|Intentional fixture fatal|Actual native exit 4|
|13|Dedicated runner success|Actual native exit 0|

The table above is attempt 02's original source coverage. Attempt 04's new
coverage, with zero compiler/simulator errors or warnings, is:

|RTL mode|Final-source lifecycle control|Actual result|
|---|---|---|
|14|Gate withdrawal in WAIT_RETIRE after downstream descriptor acceptance|Quiescent, abort 1, retirement 0, wire bytes 0|
|15|Gate restore without rearm for 6,000 clocks, then fresh rearm|No replay/armed/result/retirement; explicit tag 18 rearm enters empty collection|
|16|Busy rearm during fourth symbol after 3 received bytes, result ready high|REFUSED 9 retained, serializer 4/received 3/abort 1/retirement 0, no further bytes or success for 6,000 clocks; explicit cancel cleanup|

The UART observer records whether cancellation occurred anywhere within a
symbol, including a one-edge invalid rearm. A canceled partial symbol is not
misreported as a valid byte. Emitted prefixes remain in the evidence.

The twelve strict decoder negatives actually exit 2: CRC, partial frame,
count, metadata, full identity, quality, time, uint63 overflow, nonwrap index,
held record, changed original value and missing record. The two later boolean
negatives also exit 2. The stale source control preserves its original ns
times and reports source_age_100ms_met=false with STOP and no command.
This is focused evidence, not exhaustive branch/CDC/timing/physical proof.

## Complete byte cost

|Channel|Coding|Wire|Mandatory serialized companion|Total bytes|
|---|---|---:|---:|---:|
|0|Rice|42|3696|3738|
|1|Rice|42|3696|3738|
|2|Rice|44|3692|3736|
|3|RAW|45|3694|3739|
|Total||173|14778|14951|

Wire cost is 48 header + 8 CRC + 100 payload metadata + 17 stored code bytes.
It requires 1,730 UART 8N1 bits, excluding the mandatory companion transport.
Companions are actually serialized canonical UTF-8 files and counted in full,
per frame. Their physical transport/rate is not approved or measured. Raw
values alone are 24 bytes; the complete canonical synthetic input fixture is
11,839 bytes, with original context/quality/time/identity included. Neither
denominator establishes a production compression ratio. The complete cost is
14,951 bytes; final 1%/100ms is not met or claimed passed.

## Reproduction and retained gaps

Use existing Python/ModelSim only, under a new explicit operation and a fresh
owned evidence directory:

```powershell
& .local/venv/Scripts/python.exe -B competition/deepeye/tools/diagnostic/offboard_aggregate77/prepare77.py
& .local/venv/Scripts/python.exe -B competition/deepeye/tools/diagnostic/offboard_aggregate77/run77.py --out <fresh-owned-directory>
```

The `--saved-source` option performs only the final strict type/positive
software controls over already saved mode0 bytes. `--lifecycle-only` compiles
the current source and runs only modes 14–16. The runner retains the
pinned suspended-launch whole-Job helper, 30 s command and 180 s Job deadlines,
100,000-clock fixture bounds and a polled 32 MiB cap across all attempt files.
It propagates RTL fatal through an integer completion flag/Tcl macro with
`+acc`; negative CLI exits are checked. No waveform logging is requested.

General held/invalid/changing-quality/irregular aggregation, authenticated
Root inputs, production activation, continuous batch scheduling, stateful
anti-replay, physical companion transport, synthesis/implementation/timing,
real ADC/BOOT/board, ACK/action retirement, both complete H12 paths and every
formal acceptance gate remain open. No planner/C/Root call, board/SSH,
Vivado build, clock setter, collector repin, service/SQL/queue/credential or
Git mutation occurred. A alone operates the physical board. A's stale actual
source/C3=null and R20/R21/original 100 MHz failures are not replaced by this
synthetic evidence.

H01–H15 retain `DEEPEYE-HUMAN-LOCK-20261014/revision1`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, freeze
`1011259415a0916054eb580687612580bc1e5f09`. Full 3D/UI, hollow edge cube,
solid collisions, free camera/layout/faces/equal gates and full passage,
hidden truth, device-bounded causal observations, substantive online 3D PC AI,
both complete H12 paths and all final gates remain required. Parent quality
main/A independently review and own acceptance and Git/PR handoff.
