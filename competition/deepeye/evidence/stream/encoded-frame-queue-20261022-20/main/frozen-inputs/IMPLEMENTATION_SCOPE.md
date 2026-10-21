# op20: two-slot encoded-frame queue

Decision owner: B-MAIN-CONTINUATION-20261019/v1. Product owner remains DEEPEYE-IMPLEMENTATION-20261014/v1, App thread 01a13b55-095b-7461-8dd5-5476a130bd82. This is an implementation authorization, not a scope-only waiting assignment.

Parent work: B-LOCAL-ENCODED-FRAME-QUEUE-CONTINUE-20261022-v1.
Instruction operation: B-ENCODED-FRAME-QUEUE-20261022-20-DIRECTOR.
Product operation: B-DEEPEYE-ENCODED-FRAME-QUEUE-20261022-20.
Sole author work: B-ENCODED-FRAME-QUEUE-RTL-20261022-20-v1, one Flash/max assignment.

The coordinate-continuation work keeps its authorized 20261021 ID. The implementation ID uses the current local date, 2026-10-22. Do not create another product root or parallel product executor.

## Real gap and fixed inputs

The op09 completion matrix explicitly identifies encoded-output buffering as the next independent B03 gap. Its RTL has two raw 128-sample slots but no encoded-payload queue: metadata and encoded bytes wait directly on the external consumer, and the raw slot remains allocated until terminal delivery. Implement actual finite storage that can accept two complete encoded frames while the downstream consumer is stalled. This is a B03 increment contributing to B01 integration, with no new public packet format.

Baseline head aef19351f1836b23f9a714bc5626db4eb4df98c5. Read-only inputs:
- competition/deepeye/fpga/codec/deepeye_block_encoder.sv, SHA256 870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5.
- competition/deepeye/fpga/stream/deepeye_block_stream.sv, SHA256 c8f8c0d99769efc64a91402ee23e7157368ff90ec765db5c413f02546715fff4.
- op09 main/completion_matrix.md SHA256 6930c071ab48199dcc2d5d61862194333303f7e4498c922e24f4e6e9fa04f69a.
- Exact frozen taskbook bytes SHA256 7f5c94f7fc73698236be954ae7818266d6dfe8b4949d1752dd045d76f4b71f18, design1011259415a0916054eb580687612580bc1e5f09, B03 plus B01/B02/B04/B05/G01/G05 text.

The codec's maximum internal payload is 256 bytes / 2048 significant bits. Those are internal MSB-first block bytes; no TRACE header, CRC, source/tick/session/profile or public wire adapter is introduced. Op18 already implemented the first-capture deadline and op19 repaired its runner; neither is repeated or modified.

## Exact standalone module contract

Create deepeye_encoded_frame_queue, single clk, synchronous active-high rst and cancel. Exactly two payload banks of 256 x 8 bits and two descriptor records; no dynamic/unbounded storage. Parameter STAT_W defaults32, supports2..32, only controls diagnostic counter width. The public candidate ports below are internal RTL ports, not a common ABI.

Inputs: clk, rst, cancel; in_meta_valid; in_meta_tag[15:0], in_meta_error[1:0], in_meta_count[7:0], in_meta_e[3:0], in_meta_raw, in_meta_k[3:0], in_meta_valid_bits[11:0], in_meta_bytes[8:0]; in_valid, in_data[7:0], in_last; out_meta_ready; out_ready.

Outputs: in_meta_ready, in_ready; out_meta_valid with out_meta_tag/error/count/e/raw/k/valid_bits/bytes of the same widths; out_valid, out_data[7:0], out_last; level[1:0], receiving, faulted, fault_event, fault_code[1:0]; stat_meta, stat_in_bytes, stat_retired, stat_aborted, stat_fault, each STAT_W bits for legal parameters.

All ready/valid handshakes use pre-edge states. rst or cancel gates every ready/valid low, suppressing every transfer on that edge. Reset has priority over cancel. No input-to-output same-edge bypass, no metadata-to-first-payload same-edge acceptance, and no output-metadata-to-first-output-byte same-edge delivery.

Admission: in_meta_ready iff not abort, not faulted, no active input payload, and old level<2. A simultaneous retire does not create admission credit when old level==2; a one-cycle full-queue bubble is allowed and required by this old-state rule. One accepted descriptor immediately reserves the tail slot and increments level/stat_meta. Only one input payload can be open. Duplicate tags are legal and not identities for matching slots.

Descriptor framing validation:
- in_meta_error==0: bytes in1..256 and 8*(bytes-1)<valid_bits<=8*bytes, computed with sufficient unsigned width.
- in_meta_error!=0: bytes==0 and valid_bits==0. This is an upstream error transaction with no payload; seal it immediately and forward the original metadata unchanged.
- Otherwise reserve the slot but latch local fault_code1, faulted1, fault_event1 and increment stat_fault once. Never expose that invalid slot or accept its payload.

The remaining descriptor fields are stored and transported unchanged. This queue does not validate the codec mathematics, count/E/k meaning, padding content, public message type or tag freshness. In standalone framing tests even a one-byte descriptor is legitimate; the unchanged encoder's ordinary minimum is larger. Do not claim arbitrary framing-test descriptors are valid codec commands.

Payload: in_ready iff not abort/faulted and an admitted valid success descriptor is still receiving. No payload is accepted on the descriptor-admission edge. Each accepted byte increments stat_in_bytes, including a byte that reveals a framing fault. At accepted byte index i, in_last must equal (i==latched_bytes-1). Any early last or missing last at the declared final byte latches local fault_code2, faulted1, pulses fault_event once and increments stat_fault once. The reservation remains allocated and unsealed. No out-of-bounds write or implicit trailing drain/re-synchronization is permitted; accepted indices are always0..255. Only a correctly marked final accepted byte seals a successful slot. Silence or stalled valid is not a timeout.

Store-and-forward visibility: the head descriptor becomes eligible for out_meta_valid only after its slot has sealed. Thus no byte or metadata from an incomplete/bad frame can reach the consumer. A success frame's metadata handshake precedes its output payload; an upstream-error frame retires on its metadata handshake and never emits a payload. Success retires on the final payload handshake. Output last is generated from the sealed byte length. Head metadata and payload remain stable while their respective valid is asserted and ready is low. Do not interleave frames, overwrite old slots, skip errors or combine equal tags. Ring pointers and bank identity must work across repeated wraps and simultaneous admission/retirement or sealing/retirement.

Fault behavior: faulted is sticky until rst/cancel. It disables only new input admission/payload. Earlier sealed frames may still drain in order; fault detection does not retroactively cancel a transfer already made on that edge. The bad reserved slot never appears at output and is retained until explicit cancellation. No later input can be accepted, so no trailing bytes are guessed to be another frame. receiving is high only for an active, nonfaulted success payload; it is low after seal or local fault. fault_code=0 means no local fault,1 invalid descriptor framing,2 TLAST/length mismatch;3 reserved. fault_event is registered one cycle for the newly detected fault, then clears; repeated rejected inputs do not generate new faults. These local diagnostic codes grant no public enum or motion authority.

Cancel: discard every allocated slot, including earlier sealed output, partial output and a poisoned reservation; add pre-edge level to stat_aborted with saturation. Preserve stat_meta/stat_in_bytes/stat_retired/stat_fault, clear local fault state and all control/pointers. Held cancel cannot count an old slot twice. Reset clears both data-flow control and all counters. Payload RAM need not be cleared, but subsequent reads must refer only to bytes written into a newly admitted and fully sealed frame. Downstream and upstream must observe the same cancel/reset boundary and discard partially transferred frames; already consumed output bytes cannot be rolled back. This is not an asynchronous kill, stopped-clock guarantee or CDC/RDC proof.

Counters saturate at 2**STAT_W-1, and saturation must not affect data flow. stat_retired counts complete outgoing transactions (including upstream-error metadata), not descriptor handshakes alone for successful payload frames. stat_fault counts newly latched local framing faults. Before any relevant counter saturates and between resets, stat_meta == stat_retired + stat_aborted + level. Use small legal STAT_W values for actual public-port saturation tests; no hierarchy force/deposit as acceptance evidence. Parameter guards for0,1,33 must produce the module's exact own fatal in simulation; compile/elaboration/tool errors are not accepted parameter rejection. Guard diagnostics must be excluded from synthesis explicitly.

## Main independent acceptance before publication

Before reading author RTL, the original product quality main freezes an independently written queue/accepted-edge model, input schedule and expected outputs. Its model uses accepted descriptors and byte lists, not the author's implementation or output as the oracle. Preserve that freeze and its hash. Only public ports may be observed; no force, memory peek or seeded counters.

Required evidence:
- Every legal bytes1..256 and every last-byte significant-bit remainder1..8 (2048 framing combinations), all256 byte values, duplicate/ABA tags and differing opaque metadata; distinguish framing fixtures from legal codec commands.
- Source errors1/2 with zero-length payload, including two consecutive error transactions and errors before/after success. Standalone injected nonzero error3 also exercises opaque forwarding;3 is not assigned by op09 and this test does not assign it a producer/public meaning. Invalid byte lengths0/257/511, zero/inconsistent/too-large valid_bits and nonzero-error/nonzero-payload descriptors must latch fault1 without output.
- Early last at every position for lengths2..16, and early/missing last at representative boundary lengths including1/2/255/256. Confirm offending-byte count and poisoned reservation, trailing valid rejection, older sealed-frame draining, explicit cancellation and fresh recovery.
- Long independent metadata and payload stalls; queue full; input bubbles; no same-edge bypass; simultaneous allocate/retire and seal/retire; at least1000 ring wraps with varied lengths and tags. Stable payload/metadata checked throughout valid stalls.
- rst/cancel in empty, after metadata, each representative partial-fill stage, at final input byte, before/after output metadata and during output payload including last edge; held cancel; simultaneous fault/output-retire; no old bytes/tag after abort. Check reset priority and both small STAT_W saturation boundaries via real transactions.
- A new bounded composition fixture instantiating the exact unchanged op09 stream (which already instantiates the pinned op08 encoder) and this queue. Do not add a duplicate encoder in series. Show two complete encoded frames can be retained while consumer metadata is stalled, allowing upstream terminal delivery into the queue; prove backpressure when those two slots are allocated. Include fresh RAW/Rice, errors, duplicate tags, cancellation and a full256-byte encoded payload. Use newly selected inputs and independently computed expected internal bytes; do not rerun old op08/09 suites or claim a new public codec format.
- At least two independently chosen isolated RTL mutations, such as early publication of an incomplete frame and failed cancel invalidation, must compile/run and be rejected by concrete public-port counterexamples. A compile failure, X-before-reset, parser failure or timeout is not a behavioral mutant kill.

Run actual ModelSim with tool versions, argv, immutable input snapshots, raw stdout/stderr, true exit status, input/output traces and result counts. No synthetic process seam may stand in for this round's RTL execution. Main separately reviews runner strictness: abnormal exits/timeouts/missing output/unrelated errors/nonzero error tallies cannot pass, and one successful selected case cannot hide another failed case. Scope this qualification to the new runner; do not reopen or rerun the closed old runner suites. Preserve every failed attempt and correction. Evidence-derived views must not replace original raw bytes.

Main verifies the real standalone and composition results, exact final RTL source identity, counterexamples and all delivered artifacts. Synthesis/implementation remain blocked/not_run without a real tool run; no inherited A OOC result covers this new module. All29/G05/B06/R03/board/system remain not_run.

## Frozen ownership and execution route

All paths relative to D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014. Author exclusive writes:
1. competition/deepeye/fpga/stream/deepeye_encoded_frame_queue.sv
2. competition/deepeye/fpga/stream/encoded_frame_queue_candidate.md
3. competition/deepeye/tests/rtl/stream/tb_encoded_frame_queue.sv
4. competition/deepeye/tools/stream/run_encoded_frame_queue.py
5. competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20/author/

Product main exclusive writes:
1. competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20/main/
2. competition/deepeye/tests/rtl/stream/main_tb_encoded_frame_queue.sv
3. competition/deepeye/tools/stream/main_verify_encoded_frame_queue.py
4. handoffs/b/B-DEEPEYE-ENCODED-FRAME-QUEUE-20261022-20/
5. D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/encoded-frame-queue-20261022-20/

Put the updated eight-card completion matrix in the new main evidence directory; do not edit old immutable matrices. Any additional helper/vector belongs inside its assigned evidence directory. No top-level scratch, cache/transcript or unowned helper writes. Author has no commit/push/peer/group/credential/board/service/config/SQL/queue authority. Product main may take over released author files only after a recorded actual terminal and explicit reason; no concurrent editing.

This binding scope grants CONTINUE for exactly one implementation. Product main must record actual consumption, current task/thread/turn, input pins, pre-author oracle and non-overlapping ownership before one Flash/max assignment, then implement, independently verify and publish the new operation to existing PR30. No intermediate scope-awaiting-continue pause is required if these invariants hold. If exact fresh evidence reveals a material incompatibility, report that concrete issue rather than silently weakening scope or repeating a failed side effect.

Use current normal-TLS REST delivery, unique original request/response records including errors, one new operation/request/manifest and exact head/blob/archive readback. Reconcile unknown write outcomes; do not replay old publication or peer outboxes. Preserve protected codec input.json SHA256 6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8 and all existing untracked tools. No merge/deployment/service/config/credentials/SQL changes.

On actual completion/failure/substantive blocking event, send the exact result index once through supported App to coordinator01a154de-abd8-7590-b9a3-2819249458e3 and once to retained desktop01a140be-f9d6-7a91-ae65-e07051154b07, with work/op, real thread/turn, commit/request/manifest, paths/hashes and honest limits. The coordinator independently reviews and continues the next input-ready step on real events; no repeated human continue is required. No controller main_submit/resume/main_wait collision route, Goal, automation, model polling or READY broadcast.

## Mandatory contract

DEEPEYE-HUMAN-LOCK-20261014/revision1, pin f5989cd5defce561f9ba98e6b18fc2682945f0a2, requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804, design1011259415a0916054eb580687612580bc1e5f09.
H01 full game-grade3D/UI; H02 hollow edge-only cube; H03 solid-volume collision; H04 free camera; H05 editable/random water/rock layouts; H06 free entry/exit faces; H07 equal blue/red gates and full-volume passage; H08 hidden layout truth; H09 device-bounded causal observations; H10 online3D decisions; H11 substantive PC AI; H12 PC_DIRECT and FPGA-output paths; H13 all final hard gates; H14 cross-session priority; H15 only the same human may revise. No requirement may be weakened. Physical board A-only. Human revoked35/40percent dispatch-stop rules, not account limits. Preserve genuine blocker evidence and continue independent work.
