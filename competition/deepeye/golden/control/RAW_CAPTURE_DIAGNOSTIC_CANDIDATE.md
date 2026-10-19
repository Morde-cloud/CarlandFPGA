# Separate local raw-capture diagnostic bank candidate 11

This is a B design proposal under DEEPEYE-IMPLEMENTATION-20261014/v1, not an
implemented register bank or HWH. A must review/freeze it before RTL or register
acceptance. H01-H15 DEEPEYE-HUMAN-LOCK-20261014/revision1 remain pinned at
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804; frozen design
1011259415a0916054eb580687612580bc1e5f09. A alone operates the board.

## Proposed local aperture

Use a distinct read-only 256-byte aperture in a NEW matched overlay. There is no
absolute base address or invented HWH instance name. A's HWH is the eventual
address authority. Core REGISTER07 remains unchanged, including inaccessible
0x2c. This separate bank also rejects 0x2c, its listed holes, misalignment, unknown
offsets and every write (including zero-strobe writes). No address is a probe.

Header offsets are identification0x00, ABI0x04, size0x08, state0x0c,
generation64 at0x10/14, local batch32 at0x18, separately mapped wire sequence16
at0x1c, session32 at0x20, motion request stamp32 at0x24, config epoch8 at0x28,
sample tick64 at0x30/34, capture-clock binding tag32 at0x38 and source binding
tag32 at0x3c. ID/ABI require A assignment. Tags are registry references under the
complete authenticated BOOT digest, never standalone authentication or a truncated
digest. Unknown tags, missing mappings or mismatched context make the bank invalid.

Channel slices start0x40/80/c0 for yaw/pitch/speed, each64 bytes. In each slice,
period64 is+0x00/04, high-count64+0x08/0c, rise0 tick64+0x10/14, fall tick64+0x18/1c,
rise1 tick64+0x20/24, channel edge-cycle sequence32+0x28 and flags8+0x30.
Each pair is low word then high word; exact JSON includes all51 accessible words.
Offsets+0x2c/34/38/3c are inaccessible. All three channels have equal widths.
The old core yaw64/pitch32/speed32 proposal remains unchanged and is not silently
reinterpreted: if a diagnostic period cannot fit a core projection, that projection
must reject/invalidate rather than truncate. Raw diagnostic values never enter AI.

## Coherence and lifecycle

Core SNAPSHOT_LATCH requests one common atomic capture batch and revocation
generation for BOTH banks. The new bank cannot independently mark itself coherent.
One serialized diagnostic reader checks status, generation, session, config/control
epoch, motion request, local batch and separate wire association before and after
all reads. Check the same identities against authenticated external BOOT/context.
Reject the entire observation if any word/identity changes or any check fails;
do not combine channel fragments from multiple batches. This is an interface
proposal; operation10's offline reference does not implement this extra bank.

STOP, any fault, source/clock/session/epoch/request change, new capture cycle,
conflicting LATCH, reset, CDC offline/busy/discard or generation exhaustion revokes
both banks. RELEASE discards both. Late CDC completion cannot resurrect either.
Synchronous reset/discard must be observed by producer, mailbox and consumer;
the existing stream partial-frame discard rule remains unchanged. No async reset,
stopped-clock recovery, CDC/RDC or real timing proof follows from this document.
Historical bytes may remain readable after revocation until RELEASE, but coherent
and all validity bits are cleared. Reset clears storage/validity; it cannot establish
calibration or image identity. Internal generation is never reused. This u64
projection fails closed at exhaustion; reset/new image requires a fresh externally
authenticated lifecycle identity, not recycling old tickets with generation0.

Each channel has its own edge-cycle sequence; equality across channels does not
mean simultaneous edges. A batch records one completed cycle per physical channel
under a common context. Sequence32, local batch32, wire sequence16 and generation64
are distinct; an explicit A mapping is required. Exhaustion blocks publication
before wrap; no masking/truncation. Diagnostic ticks are capture-clock counts,
not host time, UART send time or acquisition sample ticks. Frequency, origin,
clock-domain mapping, maximum permitted skew/age and calibration remain A inputs.

For a channel marked valid, require0<=rise0<fall<rise1<=2**64-1,
period=rise1-rise0 and high_count=fall-rise0 with0<high_count<period.
No modular subtraction across rollover. Absent/glitch/timeout/overflow/order-error
flags clear channel validity and prevent a coherent all-valid publication. Flags
are bit0valid,1missing-rise0,2missing-fall,3missing-rise1,4counter-overflow,
5edge-order-error,6timeout,7glitch; reserved bits zero. Valid plus any error is
invalid. Raw rejected counts may be retained for local diagnostics with explicit
invalid flags. No raw counts can substitute for measured physical capture quality.
Independent PGA ratio validity remains in the core bank and is not derived here.

## Matched-new-HWH plan (unexecuted)

1. A approves offsets, ID/ABI, full BOOT/source/clock mapping, queue/counter/reset
   policy and read privilege. B can then implement RTL and address decoder.
2. Integrate a distinct diagnostic IP/aperture into a new build. Generate bit/HWH
   together from one full source commit and record their SHA256 plus tool version,
   top/XDC, IP parameters, address segment and synthesis/implementation/timing/CDC
   reports. No old overlay register reads/writes, and never0x2c.
3. Independently parse that actual HWH: require unique expected IP identity and
   minimum256-byte non-overlapping range, exact bus/data widths, clock/reset
   bindings and build identity match. Missing/stale/ambiguous/wrong HWH rejects
   before MMIO construction. Mock fixtures do not prove parser compatibility.
4. A alone may authorize/load the matched build and test real three-channel edge
   captures, cross-word/cross-bank tearing, STOP/reset/discard, rollover and stale
   completions. Pin operation/request/tested commit and preserve actual raw logs.
   No board request is issued by this proposal.
5. Keep raw bank access in the privileged local diagnostic process; no AI model,
   observation IPC/TRACE serializer or untrusted UI control receives these counts
   or source-private metadata. A owns ACL/transport integration and verifies it.

Current validation is descriptor arithmetic and synthetic edge examples only.
All formal29 cards, RTL/simulation/synthesis/implementation/board/system remain
not_run. This does not replace TRACE/public ABI, BOOT/clock or CDC/RDC acceptance.
