# Narrow tool-version preflight repair after op21

This proposal confers no execution authority until referenced by the coordinator's final REVISE and repair CONTINUE. Original product director remains DEEPEYE-IMPLEMENTATION-20261014/v1, thread01a13b55-095b-7461-8dd5-5476a130bd82. No second root/native/App worker.

Parent work B-LOCAL-SAMPLE-SCAN-TOOLCHECK-REPAIR-20261022-v1; instruction B-SAMPLE-SCAN-TOOLCHECK-20261022-22-DIRECTOR; new product operation B-DEEPEYE-SAMPLE-SCAN-TOOLCHECK-20261022-22; sole Flash/max author work B-SAMPLE-SCAN-TOOLCHECK-REPAIR-20261022-22-v1.

## Fixed defect and baseline

Baseline op21 headcd007dc8190b7c2d911d2be6c1136aabab3518e5/source52cd7b0795d13316a8106273b182d9c9c8b3f601/request94fcbf9936d1adf13a111d92e6d951bc63693af1c2c1f48f46e631d9e9bdd7c9/manifestaff069fcaf6db3baa7ff9f96b843c76662b83d96b15b46fbe2ec0c13bbe6bb67. Existing runner99748d791432cd0090e92b1e383670200fc3ead59ad3a6795af72f876e6d6b66 has reproducible OP21-TOOLCHECK-ERROR01: version query exit0 plus10.7 banner and explicit Error is accepted, including overall main return0/summary.oktrue. Coordinator owns literal proof under sample-scan-capture-20261022-21/version-controls-01 and version-entry-01. Reuse those failure bytes; do not claim synthetic vendor results are real tool executions.

Keep RTLfc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d, authorTBbf240773bc9a7e15683194e0d7418b1bf07f4e1b6f54267264223e161e47f393, mainTB45dfbdf1bab5b3788cad418ec259ea35028f41146013080620cdbc5c10f4936e and mainverifierf4b4290398df1f4d9a8f2327020fee7fe30f5f7d17e17df9a2338dfdbe7f8d40 read-only. Preserve all prior receipts/handoffs and op21 REVISE. Existing protected codec rawSHA6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8 unchanged.

## Required behavior

Make tool-version preflight fail closed. For each vlog/vsim version invocation, inspect both captured stdout and stderr. Explicit Error/Fatal/Warning diagnostics, malformed/nonzero diagnostic summaries, nonzero exit, timeout or exception cannot yield accepted toolchain metadata or overall run success. Preserve raw bytes, exit/timeout/error and a concise reason. Reject malformed/missing/conflicting or wrong-tool/wrong-version banners; mere substring10.7 is insufficient.

Accept the exact real recorded Model Technology ModelSim SE-64 vlog10.7 Compiler and vsim10.7 Simulator banners, including their actual spacing/date and CRLF form. A healthy version query has no Errors/Warnings summary; do not incorrectly apply a compile classifier that requires one. Permit harmless documented whitespace/prefix normalization without changing the saved raw bytes. The main may choose the narrow parser structure; no general toolchain refactor or new supported vendor/version is authorized.

When any preflight query fails, main returns nonzero and writes failure evidence, and no case compile/simulation is started. Remaining version queries may finish for diagnostics, but no normal case result or aggregate pass can override preflight failure. Existing compile/simulation/guard/mutant/selection behavior must remain unchanged. Scope is only version preflight and its failure propagation; retain hidden-window execution and fresh-output policy.

## Verification and source binding

Before reading the new author patch, the product quality main freezes its own literal preflight matrix and expected outcomes. Cover stdout and stderr diagnostics independently for each queried tool, case variants, malformed/nonzero tallies, healthy CRLF/LF banners, wrong/missing/conflicting tool/version markers, nonzero exit, timeout and exception. Retain the old-source red reproductions and corrected-source results separately. Do not import author tests as the independent oracle.

Run fresh actual Python entry processes with an explicit synthetic vendor seam: healthy preflight must proceed and succeed on selected known-good fixtures; each bad preflight must return nonzero and prove zero case compile/simulator calls. Keep actual process exit/stdout/stderr and command intents. Exercise normal, invalid guard, healthy guard and numeric mutant positive selected-case controls through synthetic logs without counting them as RTL executions. Preserve every failed preparation/probe.

Use a small focused regression of unchanged compile/simulation/guard/mutant/aggregation semantics and source/AST checks to ensure unrelated case logic did not change. It is unnecessary to rerun old RTL suites. Actual ModelSim execution is limited to fresh read-only vlog -version and vsim -version queries to validate the healthy real format and saved tool provenance; do not run vlog/vsim compile/simulation, re-execute op21/older hardware suites, or regenerate old logs.

After main independent review, publish the changed runner, new tests and new evidence through a new source commit/request/manifest for operation22 on the existing PR30. Old op21 remains reproducible at its exact pinned commit and its old immutable manifest must not be rewritten. New manifest declares the runner change and old RTL read-only dependency, not a new RTL pass. Use unique raw HTTP capture and exact Git/archive readback; unknown writes require reconciliation, never replay. Do not replay any old ref/comment/peer/publisher action.

## Exact ownership

Relative to existing worktree D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014, sole author owns only:

1. competition/deepeye/tools/acquisition/run_sample_scan_capture.py (released existing file, preserve original bytes first).
2. competition/deepeye/tests/acquisition/test_sample_scan_toolcheck.py (new).
3. competition/deepeye/evidence/acquisition/sample-scan-toolcheck-20261022-22/author/ (new).

Product main owns only:

1. competition/deepeye/evidence/acquisition/sample-scan-toolcheck-20261022-22/main/ (all independent helpers/docs/freezes/logs below this).
2. handoffs/b/B-DEEPEYE-SAMPLE-SCAN-TOOLCHECK-20261022-22/ (new).
3. D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/sample-scan-toolcheck-20261022-22/ (new private).

All new paths must be absent, existing runner must match its baseline hash, index must be empty, and no active/duplicate assignment may overlap. Do not modify shared git config, old evidence, original candidate doc, skills/runtime/service/SQL/credentials/queues. Evidence-specific .gitattributes may be added only inside new owned directories if needed. No root transcript/cache or unowned temporary file. Execute Python with -B -X utf8 and keep any test-framework cache/output explicitly within owned evidence. Main takeover of author paths requires actual terminal release and a recorded reason.

Consume the exact REVISE/CONTINUE/scope hashes in the new private CONSUMED.json with actual App thread/turn and baseline/ownership/contract checks, then freeze model and delegate one Flash/max. The prior op21 author was actually completed/nonstale and released its runner; no extra writer may be started. Report actual completion/failure/substantive blocker by supported App once to coordinator01a154de-abd8-7590-b9a3-2819249458e3 and original desktop01a140be-f9d6-7a91-ae65-e07051154b07. Do not use controller resume/main_submit/main_wait collision routing, periodic model polling, Goal, automation or empty READY. No next unrelated increment automatically starts.

## Fixed human contract

H01-H15 DEEPEYE-HUMAN-LOCK-20261014/revision1, pinf5989cd5defce561f9ba98e6b18fc2682945f0a2, requirementsSHA256c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804, design1011259415a0916054eb580687612580bc1e5f09. Full game-grade3D/UI, hollow edge cube, solid collisions, free camera/layout/entry-exit faces, equal gates/full passage, hidden truth, device-bounded causal observations, online3D decision-making, substantive PC AI, both complete H12 paths and final gates remain required; only the same human can revise. All29/B02/G05/B06/R03/fullproduct/synthesis/implementation/timing/CDC_RDC/board/system remain not_run; board A-only. No public ABI/ADC/pin/rate/clock/BOOT/freshness/TTL/ENABLE/motion permission. Human-revoked35/40percent stop thresholds remain revoked; do not assume unlimited capacity.
