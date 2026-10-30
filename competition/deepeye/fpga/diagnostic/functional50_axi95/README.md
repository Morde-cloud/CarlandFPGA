# NEW102 first public AXI functional attempt

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-DEEPEYE-TRACE50-AXI-RECOVERY-20261031-102`.

The stopped 95 worker's original bench/checker and false quality observation
remain preserved under `resume-74/board95-stopped-original/` and
`board50-worker95/`. No runtime was attributed to that worker. The main's
original record 9 vector `[5,5,5,1]` is correct: global 1807 = 0x070f has no
saturation bits, and local byte 5 has bit 2 (held) set. This fixture corrects
only semantic quality staging and unfinished harness/checker bookkeeping;
source94 and all recursive core/decoder/helper dependencies remain read-only.

The bench drives only public AXI of source94: two exact historical A18 records
0 and 9, independent AW/W orders, held B/R, reset-discarded pending channels,
ARM/PUSH/BIND/ACK sequencing, raw TX sampled independently at 50 MHz/1 Mbaud,
actual unchanged UART RX/FIFO and explicit non-destructive peek/POP. It keeps
invalid null distinct from valid zero, original origin/QPC/time and quality.
The adjacent refusal controls and one later partial-TX cancellation remain
required. The checker uses the unchanged strict host decoder and fixed TRACE
parser, serializes every required companion, and records complete frames and
the separate canceled prefix. It does not copy a codec or call any planner.

Pre-first-run completion repairs include actual registered BVALID waiting,
pending lone-W reset coverage, holding the initial empty-FIFO RDATA while its
first real byte arrives, canonical payload provenance, exact raw code offset,
and separate event captures. None removes a required assertion or changes the
core. The compiler policy is explicitly main-selected `-sv -svinputport=var`,
documented by the installed ModelSim manual; it is not default-policy
portability, synthesis, Vivado, timing or board proof.

`tools/diagnostic/functional50_axi95/run102.py` makes exactly one fresh snapshot
under repository-local `.local/v102/attempt-01/source/` and executes those
copies. The trusted pinned helper uses suspended-create and attaches the
Windows Job before resume. Candidate/checker imports and all native commands
run inside that Job: at most 25 s per command, 120 s for the whole Job, a
polled 8 MiB total attempt output cap and 600,000 HDL clocks. Any runtime failure
is terminal for this assignment: no repair, retry, second attempt or posthoc
candidate execution. No preflight tests are run outside the Job.

The planned first attempt has not been claimed passed by this README. Actual
outcome, exact source/input/tool hashes, commands, exits, raw UART/FIFO prefixes,
semantic artifacts, all companion bytes and Job terminal/empty/closed receipts
are authoritative in `resume-74/board50-worker102/RESULT.json` and its linked
short-path evidence. A later source commit is never labelled as tested.

All inputs are retired schema-1 historical records. Original native EM scope,
Root/BOOT/admission and current-source evidence remain unavailable; offline
age evaluation is at least one second after the batch. Results remain STOP,
command=null, core_ran=false, current_source_eligible=false. FIFO full/counter
exhaustion defensive branches are not forced. No analog/physical UART/board,
CDC metastability, build/BIT/HWH/timing, G05 atomic STOP, both H12 paths, final
1%/100ms, all 29 gates or product acceptance is established. A alone operates
the board; main owns hard decisions, independent review and publication.

H01–H15 retain contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, requirements
SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, freeze
`1011259415a0916054eb580687612580bc1e5f09`. Full 3D/UI, hollow edge cube,
solid collisions, free camera/layout/faces/equal gates/full passage, hidden
causal observations, substantive online 3D PC AI and both complete H12 paths
remain mandatory. No old 74/75/77/92/101 suite is replayed.
