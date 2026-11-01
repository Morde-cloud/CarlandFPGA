# B157 slot-gate first-controls test plan

Status: `SOURCE_ONLY_NOT_RUN`.
Work: `B-B04-SLOT89-FIRST-CONTROLS-20261101-157`.
This plan is a review artifact. It is not a simulation result, completion
evidence, product acceptance, physical-board evidence, or a timing claim.

## Boundary and pins

The directed testbench is
`tb_deepeye_b04_slot89_first_controls157.sv`. It drives only the public ports of
the unchanged Slot89 candidate and observes only public outputs. It does not
force internal nodes, call a host callback, or infer a hidden physical path.

Source pins used by the testbench:

- Candidate: `calendar_gate89/deepeye_nominal_uplink_slot_gate_candidate.sv`,
  29104 bytes, SHA-256
  `7bd31aa2fd99b27093a00b2771d535e896f29e726e414748ac61f81c004616c1`.
- Original Q012 scheduler:
  `competition/deepeye/fpga/transport/deepeye_q012_scheduler.sv`, 11386 bytes,
  SHA-256 `d7cfe903ca6bb904fbf21f5207eac694638741f02bd48dd0ff3785becf97e740`.
- Manual oracles: `calendar_gate89/vectors_UNEXECUTED.json`, 26675 bytes,
  SHA-256 `26d5bc0ff2f841afa2eddf1a6465e96113b5f225b16e9f62e710dd8ddc825030`.
- Candidate README: 8960 bytes, SHA-256
  `3a4341c0f33a460383f7118b4bcdb8b169eb2f6ee66e52bd5b1ae7a6794e775a`.
- Canonical requirements (H01-H15, sorted compact UTF-8): SHA-256
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
- Contract pin: `f5989cd5defce561f9ba98e6b18fc2682945f0a2`; frozen design
  `1011259415a0916054eb580687612580bc1e5f09`.
- Synthetic profile pin: SHA-256
  `b7abdd50d04337c4526ae43de6912c9b7f05e9803e79a519dd4fd7528edc3b46`;
  its source is the Slot89 software candidate, not an admitted profile, and
  `hardware_enable_eligible=false`.

All `now_ns`, token IDs, descriptors, grants, hashes and profile values are
synthetic digital test inputs. They are not an A grant, a current producer,
BOOT authentication, a profile admission, capture proof, or measured wire
timing.

## Execution contract

The parent may later run exactly one finite group from this directory:

```
vsim -c -do run_tb.do
```

The command file compiles, in order:

1. `../../transport/deepeye_q012_scheduler.sv`
2. `../calendar_gate89/deepeye_nominal_uplink_slot_gate_candidate.sv`
3. `./tb_deepeye_b04_slot89_first_controls157.sv`

It removes stale `work157` and status output, runs one `run -all`, requires
the exact marker
`TEST_PASS completed=1 checked_cases=46 manual_cases=47 review_only_skipped=1`,
and exits nonzero on compile, simulation, timeout, missing status, or failure.
The TB itself has a 20,000-posedge global cycle cap and finite handshake
loops; no test waits forever for ready. Inputs are stable at the preceding
negative edge and handshakes are sampled at positive edges.

## Case partition

The 47 manual IDs have 46 executable public-interface cases and one
deliberately excluded review-only case. The excluded case is listed separately
below; it is not counted as checked and is not represented as executed.

| # | Manual oracle ID | TB case | Expected public outcome |
|---:|---|---|---|
| 1 | `F1-NOM-EVENT` | `F1_NOM_EVENT` | bind once; no outer valid before start; exact-start fire; one pulse; fault0; flush delta0 |
| 2 | `F1-NOM-TELEM` | `F1_NOM_TELEM` | same exact-slot outcome for TELEM |
| 3 | `F1-NOM-ACK-PRIMARY` | `F1_NOM_ACK_PRIMARY` | same exact-slot outcome for ACK_PRIMARY |
| 4 | `F1-NOM-STATE3D` | `F1_NOM_STATE3D` | same exact-slot outcome for STATE3D |
| 5 | `F1-NOM-ACK-RETRY` | `F1_NOM_ACK_RETRY` | same exact-slot outcome for ACK_RETRY |
| 6 | `F1-NOM-CONFIG-ACK` | `F1_NOM_CONFIG_ACK` | same exact-slot outcome for CONFIG_ACK |
| 7 | `F1-NOM-EVENT-RETRY` | `F1_NOM_EVENT_RETRY` | same exact-slot outcome for EVENT_RETRY |
| 8 | `F2-NOM-EVENT` | `F2_NOM_EVENT` | STRESS bind once; no early valid; exact fire; pulse1; fault0 |
| 9 | `F2-NOM-TELEM` | `F2_NOM_TELEM` | same STRESS exact-slot outcome for TELEM |
| 10 | `F2-NOM-ACK-PRIMARY` | `F2_NOM_ACK_PRIMARY` | same STRESS exact-slot outcome for ACK_PRIMARY |
| 11 | `F2-NOM-STATE3D` | `F2_NOM_STATE3D` | same STRESS exact-slot outcome for STATE3D |
| 12 | `F2-NOM-ACK-RETRY` | `F2_NOM_ACK_RETRY` | same STRESS exact-slot outcome for ACK_RETRY |
| 13 | `F2-NOM-CONFIG-ACK` | `F2_NOM_CONFIG_ACK` | same STRESS exact-slot outcome for CONFIG_ACK |
| 14 | `F2-NOM-EVENT-RETRY` | `F2_NOM_EVENT_RETRY` | same STRESS exact-slot outcome for EVENT_RETRY |
| 15 | `FIRST-ACK-RETRY-SUPPRESS` | `FIRST_ACK_RETRY_SUPPRESS` | no token ready; fault1/token301; no enqueue or forward |
| 16 | `CONFIG-RETRY-MUTEX` | `CONFIG_RETRY_MUTEX` | second bind refused; fault7/token303; no second enqueue |
| 17 | `ROLE-CLASS-MISMATCH` | `ROLE_CLASS_MISMATCH` | no bind; fault1/token304; no enqueue |
| 18 | `ROLE-COST-MISMATCH` | `ROLE_COST_MISMATCH` | no bind; fault1/token305; no enqueue |
| 19 | `PROFILE-HASH-MISMATCH` | `PROFILE_HASH_MISMATCH` | no bind; fault1/token306; no enqueue |
| 20 | `PROFILE-SWITCH-WITHOUT-RESET` | `PROFILE_SWITCH_WITHOUT_RESET` | second profile bind refused; fault7/token308 |
| 21 | `TOKEN-ID-ZERO` | `TOKEN_ID_ZERO` | no bind; fault1 with token ID 0 |
| 22 | `TOKEN-ID-REPLAY` | `TOKEN_ID_REPLAY` | replay ID refused; fault7/token309; no enqueue |
| 23 | `TOKEN-ID-MSB-SET` | `TOKEN_ID_MSB_SET` | uint63 MSB rejected; fault1; no enqueue |
| 24 | `INGRESS-DESCRIPTOR-MISMATCH` | `INGRESS_DESCRIPTOR_MISMATCH` | bind accepted once; mismatch not ready; fault2/token310; no accept/forward |
| 25 | `HELD-OFFER-GATED-BEFORE-SLOT` | `HELD_OFFER_GATED_BEFORE_SLOT` | outer valid gated before slot; exact fire; pulse1; fault0 |
| 26 | `CANCEL-WITH-HELD-OFFER` | `CANCEL_WITH_HELD_OFFER` | fault5/token312; disarmed; no output; flush delta1; no pulse |
| 27 | `DISABLE-WHILE-ACTIVE` | `DISABLE_WHILE_ACTIVE` | fault5/token313; disarmed; flush delta1; no pulse |
| 28 | `BUSY-ARM-WHILE-TOKEN-LIVE` | `BUSY_ARM_WHILE_TOKEN_LIVE` | fault6/token314; old token not replaced; flush delta1; no pulse |
| 29 | `CLEAR-PRESERVES-CLOSED-WINDOW` | `CLEAR_PRESERVES_CLOSED_WINDOW` | clear requires empty/quiet; no auto-arm; same-origin EVENT refused fault7 |
| 30 | `NEW-WINDOW-AFTER-FAULT-ALLOWED` | `NEW_WINDOW_AFTER_FAULT_ALLOWED` | new aligned origin 10500000000 binds; role mask 0x01; fault0 |
| 31 | `NEW-WINDOW-UNALIGNED` | `NEW_WINDOW_UNALIGNED` | unaligned future origin refused; fault7; no enqueue |
| 32 | `NEW-WINDOW-BEFORE-PRIOR-END` | `NEW_WINDOW_BEFORE_PRIOR_END` | origin before prior end refused; fault7; no enqueue |
| 33 | `DEADLINE-EQUAL-FRAME-END` | `DEADLINE_EQUAL_FRAME_END` | strict `frame_end < deadline` fails; fault1; no enqueue |
| 34 | `WINDOW-END-OVERFLOW-U63` | `WINDOW_END_OVERFLOW_U63` | 65-bit checked sum overflow rejected; fault1 |
| 35 | `LATE-BIND-AT-EXACT-START` | `LATE_BIND_AT_EXACT_START` | bind at exact start refused; fault3; no enqueue |
| 36 | `MISS-AFTER-SLOT-BACKPRESSURE` | `MISS_AFTER_SLOT_BACKPRESSURE` | no fire while backpressured; next sample fault3; flush1; no catch-up |
| 37 | `TIME-REGRESSION-STICKY` | `TIME_REGRESSION_STICKY` | fault4; disarmed; sticky; no auto-rearm; clear then new arm rise works |
| 38 | `TOKEN-VALID-HELD-NO-REPLAY` | `TOKEN_VALID_HELD_NO_REPLAY` | held valid cannot bind again/fault; one sampled low permits the next bind |
| 39 | `RESET-DESTRUCTIVE-UNKNOWN` | `RESET_DESTRUCTIVE_UNKNOWN` | reset clears fault/armed/output/credits/queues/stats; no ACK; same ID may be new context |
| 40 | `CLEAR-REFUSED-WHILE-CORE-NONEMPTY` | `CLEAR_REFUSED_WHILE_CORE_NONEMPTY` | first clear refused and fault stays; after flush/empty second clear succeeds; no auto-arm |
| 41 | `IDLE-CANCEL-DISABLE-NO-FAULT` | `IDLE_CANCEL_DISABLE_NO_FAULT` | idle cancel and enable drop produce no fault, flush, arm, or output |
| 42 | `SAME-ORIGIN-SAME-ROLE-REPLAY` | `SAME_ORIGIN_SAME_ROLE_REPLAY` | different ID but reused EVENT role refused fault7; no enqueue |
| 43 | `SAME-ORIGIN-DIFFERENT-ROLE-ALLOWED` | `SAME_ORIGIN_DIFFERENT_ROLE_ALLOWED` | TELEM binds; used roles 0x01 to 0x03; fault0 |
| 44 | `NEW-WINDOW-CLEARS-ROLE-MASK` | `NEW_WINDOW_CLEARS_ROLE_MASK` | aligned new origin permits previously used EVENT; used roles 0x01 |
| 45 | `RETRY-GRANT-STATE-INVALID` | `RETRY_GRANT_STATE_INVALID` | grant 0x2000 (bit13 without bit15) refused fault1; no enqueue |
| 46 | `UNARMED-TOKEN-BACKPRESSURE` | `UNARMED_TOKEN_BACKPRESSURE` | valid token without arm never ready/binds/faults/enqueues/outputs |

## Review-only skip

| Manual oracle ID | Reason | Execution status |
|---|---|---|
| `HELD-OFFER-MISMATCH-NOT-NATURAL` | The unchanged Q012 cannot naturally emit a mismatched held offer after a successful exact ingress handshake. Exercising it would require forcing an internal node or inventing a non-public stimulus, which this source-only test must not do. | `NOT_RUN`; not counted in the 46 executable cases |

The TB prints exactly this skip marker before the final pass marker:

```
REVIEW_ONLY_SKIP manual_id=HELD-OFFER-MISMATCH-NOT-NATURAL
```

## Evidence and failure behavior

Every completed case emits one `CASE_END` line with its case name, manual ID,
`status=PASS`, detail, accepted/sent/flushed counters and cycle count. Any
failed public observation emits `CASE_END ... status=FAIL`, writes a
`TEST_FAIL` status line while the file is open, and calls `$fatal`.
The `TEST_PASS` line is written only after all cases and both case-count checks
have succeeded. No automatic retries, rebases, or acceptance claims exist.
