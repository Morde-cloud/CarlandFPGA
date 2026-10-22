# B02 four-channel sample-scan capture: proposed next implementation

This scope has no execution authority until referenced by the coordinator's completed op20 ACCEPT and explicit next CONTINUE decision. Product owner remains DEEPEYE-IMPLEMENTATION-20261014/v1, thread01a13b55-095b-7461-8dd5-5476a130bd82. No new root/native/App worker.

Parent work B-LOCAL-SAMPLE-SCAN-CONTINUE-20261022-v1; instruction B-SAMPLE-SCAN-20261022-21-DIRECTOR; product operation B-DEEPEYE-SAMPLE-SCAN-CAPTURE-20261022-21; sole Flash/max author work B-SAMPLE-SCAN-CAPTURE-RTL-20261022-21-v1.

## Input readiness and actual missing behavior

Frozen design1011259415a0916054eb580687612580bc1e5f09 specifies four channels in uint16 containers and B02 channel order/sample_id/tick/quality/recording. The current tracked RTL contains codec/stream/PWM/capture candidates but no acquisition scan assembler. Implement a real internal four-channel event collector that rejects mixed scans, retains per-channel raw metadata and explicitly accounts for loss under a non-backpressurable input. This is distinct from op20's encoded-byte queue. Do not rerun or extend old codec/PWM/runner operations.

Baseline is op20 head7317b6ac3f8f19059031c46f8c4d2b0f9a8e9c06, source664b9dc2aa22372677b6127699f573ff830f1224, request7e2bae4d3b805f8c84c2454e85c37b6f4bcda8aa3eca7c32448e2b70439c9bfd, manifest4429ece81df20f853ee64199eca9a9abbb9e30c59525f2c70472be782067a6da. All old product files, especially op20 RTL SHA68f9b655794a722a5cb285ac1c87749ea7acea7dcd6c1650536d1f1094c2e76a and protected codec rawSHA6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8, are read-only.

No ADC/XADC device protocol, pins, clock rate, synchronizer, public sample_id/tick/source/quality enum, DMA or PS endpoint is frozen by this module. Four internal channel numbers0..3 identify input positions only, not assigned physical board pins. uint16 storage does not confer16-bit ADC precision. Input ticks and quality bytes are opaque transport values: preserve them exactly, do not infer monotonicity, calibration, liveness, physical sampling time or authority. The local event ordinal described below is not the public ABI sample_id. Physical100Hz/600s/G09/ADC skew and source heartbeat remain later gates.

## Fixed candidate interface

New module `deepeye_sample_scan_capture`, one clock and synchronous active-high rst, stop, rearm. Parameter SEQ_W default32/support2..32; TICK_W default64/support1..64; TAG_W default32/support1..64; STAT_W default32/support2..32. Invalid parameter values must reach the exact module's simulation fatal, with legal declaration widths and synthesis exclusion; compile/tool failure is not parameter acceptance.

Inputs: clk/rst/stop/rearm; rearm_tag[TAG_W-1:0]; sample_strobe; sample_channel[1:0]; sample_data[15:0]; sample_tick[TICK_W-1:0]; sample_quality[7:0]; out_ready.

Outputs: out_valid; out_data[63:0]; out_ticks[4*TICK_W-1:0]; out_quality[31:0]; out_first_seq[SEQ_W-1:0]; out_last_seq[SEQ_W-1:0]; out_tag[TAG_W-1:0]; armed; partial_len[2:0] (only0..3); next_seq[SEQ_W-1:0]; seq_exhausted; order_error_event; overrun_event; seq_exhaust_event; stat_events/stat_scans/stat_retired/stat_discarded_samples/stat_order_errors/stat_overruns, each STAT_W bits.

Channel0 is the least-significant lane of each packed output, channel1 the next, and so on. One output record is atomic; out_valid indicates only a complete record available for transport, never fresh/live/valid physical acquisition or movement permission. Inactive output payload fields are unspecified.

## Abort, window and input-event rules

Priority is rst > stop > rearm > ordinary clock edge. Any asserted rst/stop/rearm qualifies out_valid low immediately, preventing an old-record handshake on that edge. These three inputs ignore sample_strobe on that edge. Reset and stop clear partial and output state, tag, ordinals, diagnostics and counters and leave armed0. Rearm performs the same clear, stores exactly rearm_tag, sets next_seq0 and armed1. Same tag on a later rearm is legal and still flushes every old record/partial. Holding any abort high cannot repeatedly consume data or retain old-window payloads.

In an ordinary edge, one event is observed iff old armed1 and sample_strobe1. There is deliberately no input ready: each asserted strobe at an armed edge is one new event, including consecutive/held strobes. Each event receives the old next_seq and increments stat_events regardless of channel-order outcome or full output slot. Input activity while unarmed is ignored and produces no new capture/loss events. No missing-strobe watchdog or absence timeout is invented.

next_seq starts at0. The event with ordinal SMAX=2**SEQ_W-1 is processed normally, then sets armed0, seq_exhausted1 and seq_exhaust_event1 and holds next_seq at SMAX. It must never wrap or accept another event until explicit rearm. If that terminal event completes a proper scan, its complete record can be offered or dropped under normal slot rules. If it leaves a partial scan, discard that entire partial immediately and add its length to stat_discarded_samples. Existing complete output remains transportable after exhaustion; future rearm/stop flushes it. SEQ_W2 therefore permits four events0..3, sufficient for exactly one correct scan.

The three event outputs pulse for their respective actual conditions on that ordinary edge and clear on the next ordinary edge without the condition. Order fault and namespace exhaustion can coexist; do not suppress one with a diagnostic priority encoder. seq_exhausted remains sticky until abort/rearm.

## Order-checked scan assembly

Keep one partial scan with at most three sample records plus the currently processed event. A complete scan consists of four consecutive observed events with channels0,1,2,3 in exactly that order. Capture each event's uint16 data, raw tick and raw quality; do not substitute constants, last-known values or the generator's prediction. Capture the start ordinal on channel0; successful completion's end ordinal is exactly start+3 without modular arithmetic.

When partial_len0, channel0 begins a new partial. Channels1/2/3 are orphan events: report one order_error_event, increment stat_order_errors and stat_discarded_samples by1, and remain empty.

When partial_len n in1..3, the expected channel is n. That matching event extends the partial, or completes it at n==3. A different channel causes one order error and discards all n previously collected samples. If the unexpected channel is0, the current event simultaneously becomes the first sample of a fresh scan; discarded_samples adds n, not n+1. Otherwise the current event is also discarded, add n+1 and return empty. A later arrival cannot fill a previously discarded component or combine two scans. Sequence exhaustion is applied after this order processing, so a terminal new channel0 partial is also discarded and counted once.

On every correct completion, increment stat_scans and clear the partial to empty regardless of output availability. Output backpressure never stops order checking or sample-event ordinals.

## Single complete-result slot and accounting

Use exactly one complete-result slot in addition to the bounded partial storage. Handshakes are based on old out_valid/out_ready and abort gating. Old valid&&ready retires the old record and increments stat_retired. A new completed scan on that same edge may replace it; no combinational bypass allows an arriving scan to be consumed on its completion edge. If old slot is empty, fill it. If old slot is full and not retiring, keep its whole payload stable, drop the newly completed four-sample scan, pulse overrun_event, increment stat_overruns and add4 to stat_discarded_samples. A dropped scan must not overwrite any old lane, tick, ordinal or tag.

All counters saturate at2**STAT_W-1 and saturation cannot alter data flow. Additions involving discarded partials, full scans or terminal exhaustion must be widened before saturation; coincident causes add their actual disjoint sample counts once. Between abort/rearm boundaries and before relevant counter saturation, the following conservation identities hold:

- stat_events = 4*(stat_retired + occupied_complete_slot) + partial_len + stat_discarded_samples.
- stat_scans = stat_retired + occupied_complete_slot + stat_overruns.

Slot occupancy is internal state, not the abort-qualified out_valid value while an abort input is high. Do not assert these equations across an abort that clears the window's counters. Stop/rearm discards all old records by ending the window; no cumulative cross-window loss accounting or public session behavior is claimed.

## Independent main acceptance before publication

The original product main freezes a new event-list/scanner model and expected outputs before first reading author RTL. Model events are indexed by accepted strobes and grouped into four consecutive channel events, with a separate one-record transport slot. It must not import author code/test/oracle or use hierarchy force/deposit/seeded counters. Record actual freeze time/hash, then delegate one Flash/max with explicit ownership.

Required public-port evidence:

1. Exhaustive channel strings of length6 (4096 strings) from a fresh rearm, with literal expected groups/partial/drop counts, plus explicit empty and shorter-prefix controls. Directed repeated channel0, duplicate/missing/swapped channels and a fresh0 recovery demonstrate no mixed scan. Include long no-strobe gaps and consecutive strobes; there is no fabricated timeout.
2. At least two complete scans under each ready pattern, long output stalls, complete-drop, and exact simultaneous retire/refill. Show stable complete payload while stalled and continued front-end event accounting; no same-edge bypass. New independent randomized schedules cover at least20000 edges with errors, stalls and rearm.
3. Every quality byte0..255 in each lane; data0/1/0x7fff/0x8000/0xffff and varied16-bit patterns; ticks that are zero/equal/decreasing, cross bit31/63 and wrap bit patterns are transported unchanged, not interpreted as physical time. TAG_W64 all bits and same-tag repeated rearm must flush old records.
4. Reset/stop/rearm at every partial stage, while old complete is stalled, on retire, on completion and on the final namespace ordinal; highest-priority abort suppresses both input event and output handshake. Check every combination of aborts and held aborts. Two scans sharing a tag cannot resurrect after rearm.
5. Actual SEQ_W2/3/4 exhaustion with terminal event at every partial/order condition, including a complete last scan and simultaneous full-slot drop. Check that armed0 stops input but lets an already complete record retire, next_seq holds SMAX, and rearm restarts0. Run a complete SEQ_W16 window through65536 actual events, crossing32767/32768 and consuming65535 without wrap; remaining32-bit namespace coverage is bounded only.
6. Actual STAT_W2/3 saturation by transactions for every counter, with flow continuing and the conservation identities checked before saturation. Mixed order-error/exhaustion and overrun/exhaustion events must preserve both event flags and exact disjoint loss accounting.
7. Actual exact-own-fatal rejects for SEQ_W1/33, TICK_W0/65, TAG_W0/65 and STAT_W1/33; warning/tool failures are not successful guard cases. At least two isolated compiled RTL mutants must be rejected by concrete numeric public-port counterexamples: one that permits wrong-channel mixing, and one that fails flush or event-ordinal/loss accounting. Include healthy controls with the same stimuli. Do not count compile errors, X-before-reset or timeout as behavioral rejection.

Use actual ModelSim commands/versions/stdout/stderr/exits and exact final source snapshots. Independently review new runner exit/error/guard/selected-case aggregation with small focused failures; do not reopen old runner repair operations. Preserve failures, corrections and ownership deviations. No old vendor suite is rerun to inflate new evidence. Synthesis/implementation/CDC/RDC/full-product/board/system and all29 formal cards remain not_run without their own actual evidence.

## Exact ownership and delivery

Paths relative to existing worktree D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014. Sole author writes only:

1. competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv
2. competition/deepeye/fpga/acquisition/sample_scan_capture_candidate.md
3. competition/deepeye/tests/rtl/acquisition/tb_sample_scan_capture.sv
4. competition/deepeye/tools/acquisition/run_sample_scan_capture.py
5. competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/author/

Product main writes only:

1. competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/main/
2. competition/deepeye/tests/rtl/acquisition/main_tb_sample_scan_capture.sv
3. competition/deepeye/tools/acquisition/main_verify_sample_scan_capture.py
4. handoffs/b/B-DEEPEYE-SAMPLE-SCAN-CAPTURE-20261022-21/
5. D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/sample-scan-capture-20261022-21/

All helpers, generated traces, input freezes and documentation belong below these exact directories; no evidence-root sibling, top-level transcript/cache or unowned temporary file. Check all new paths absent and no active/duplicate assignment before execution. Do not change any old source, test, handoff, .gitattributes or untracked tool. If necessary, an evidence-specific .gitattributes belongs inside new main/ or released author evidence only and must not change shared Git configuration. Main takeover of released author files requires actual terminal receipt and explicit recorded reason.

After actual main review, use a new request/manifest with this operation and publish to existing PR30. Preserve unique raw HTTP requests/responses including errors and verify exact Git blobs/archive; reconcile unknown write outcomes without replay. Do not repeat old publisher/ref/comment/peer actions. Author has no publication/peer/group/board/service/config/credential/SQL/queue authority. Main reports completion/failure/substantive blocker once to coordinator01a154de-abd8-7590-b9a3-2819249458e3 and once to original desktop01a140be-f9d6-7a91-ae65-e07051154b07 through supported App, with precise work/op/commit/request/manifest/evidence paths and hashes. No controller resume/main_submit/main_wait collision route, Goal, timer, model polling or empty READY.

## Human contract

DEEPEYE-HUMAN-LOCK-20261014/revision1, pinf5989cd5defce561f9ba98e6b18fc2682945f0a2; canonical requirements SHA256c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804; design1011259415a0916054eb580687612580bc1e5f09. H01 full game-grade3D/UI; H02 hollow edge-only cube; H03 solid-volume collision; H04 free camera; H05 editable/random water/rock layouts; H06 free entry/exit faces; H07 equal blue/red gates and complete-volume passage; H08 hidden truth; H09 device-bounded causal observation; H10 online3D decisions; H11 substantive PC AI; H12 complete PC_DIRECT and FPGA-output paths; H13 final hard gates; H14 cross-session priority; H15 same-human-only revision. No requirement is weakened. Physical board A-only; all29/G05/B06/R03 and full-product/system gates remain not_run. No public ABI/BOOT/clock/source/physicalTTL/ENABLE/motion grant. Human revoked35/40percent dispatch-stop rules, not actual account limits.
