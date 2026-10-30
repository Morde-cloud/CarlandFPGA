# NEW106 saved-104 checker recovery

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-DEEPEYE-TRACE50-SAVED104-SEMANTICS-20261031-106`.

This is new software verification of sealed 104 evidence. Original 104 RTL
execution commit is `7ab2614a3996e51983b81856cfc5bb9fcb026ba0`; its overall
status remains failed. There is no new ModelSim compile/simulation, tool
version run, Git command, board operation or old-runner execution.

`check106.py` starts from exact frozen 104 checker
`0643c60bbd9e21b8b81490974fb92804af67d2b3defd2475af5a29bdba16d5a7`.
The main selected one population correction: valid zero is also valid fresh,
so an independent held/fresh condition follows the valid-zero count. Expected
counts remain invalid 1, valid-zero 1, held 3, fresh 4. Added invariants require
invalid+held+fresh=8 and valid-zero<=fresh. All original values, null/zero,
quality, exact ns times, CRC, source bindings, STOP and negative controls stay.

The new checker reconstructs eight artifacts from copied original raw bytes;
it never copies old decoded outputs into the new output. It reads sealed old
artifacts by audited hash for comparison. The main explicitly refined the
initial byte-identity request: the ONLY permitted companion difference is
`execution_source_pins.checker_sha256`, which honestly identifies the actual
new 106 checker. Every other companion field and every wire byte must match.
Costs are recomputed from actually serialized new bytes, not assumed equal
because SHA strings have equal widths. New checker commit/hash/report scope
are separate from the original 104 RTL execution context.

The original `SOURCE_BEFORE.json` and `MAIN_FREEZE.json` are copied byte-exact.
An additional 106 copy map and new source/reference before/after manifests
record which saved paths were read. Old native commands/exits are retained as
reused evidence, never represented as newly executed commands. Original 104
checker failure and the main identity-transcription correction remain visible.

Preparation ends at CODE_READY. The main must freeze the four new files and
issue explicit START before the single attempt. `run106.py --freeze FILE
--runtime-start FILE` verifies that START binds the freeze. Only corrected
`check106.py` executes as a child of the trusted suspended-launch Windows Job:
25 s command deadline, 120 s whole Job and a polled 8 MiB output cap. Any
unexpected failure stops without repair, retry or posthoc candidate execution.
Actual result and Job terminal/empty/closed proof are written under
`resume-74/board50-worker106/` and `.local/v106/attempt-01/`.

Until that attempt completes, no pass is claimed here. Even successful saved
software checks establish no authenticated ADC/BOOT/Root/admission/native EM
or current capture, no physical link/board/timing/BIT/HWH, no motion/ACK/action
retirement, neither complete H12 path, final 1%/100ms or product acceptance.
STOP/core_ran=false/command=null/current_source_eligible=false remain. A alone
operates the board; main independently reviews and owns Git/publication.

H01–H15 retain `DEEPEYE-HUMAN-LOCK-20261014/revision1`, requirements hash
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, taskbook freeze
`1011259415a0916054eb580687612580bc1e5f09`. Full 3D/UI, hollow edge cube,
solid collisions, free camera/layout/faces/equal gates/full passage, hidden
causal observations, substantive online 3D PC AI and both full H12 paths
remain mandatory.
