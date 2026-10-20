# Coordinator review of operation 18

Decision: **REVISE the runner qualification**. The delivered runner still accepts failed executions. This review does not establish a functional RTL defect and does not invalidate the separately saved successful RTL traces.

Exact input: PR30 head `6c1dbca6ec15d8bd3c7bc123cf839a2152869a9b`, source/evidence `d80254db6936f53b2f870713b85c523b52af4911`, operation `B-DEEPEYE-FIRST-CAPTURE-DEADLINE-20261021-18`, request `c0a0dc7fb76cb3caab91722bd08778e6af078b50276fa9cc52be006a6355d7e9`. Reviewed runner SHA256 `a78779ae94f72f183eedfb994a8d6f645258d3289881ec2511cf5afe5143d9eb`; its exact bytes are retained in `runner_final_snapshot.py`.

## FC18-P2-01 — Reject unrelated plain errors in guard output

`parse_guard_log`, runner lines 303–378, only collects unrelated errors matching `** Error` or `** Fatal` at lines 348–349. An otherwise valid guard transcript followed by `Error: unrelated load failure` or `Fatal: unrelated runtime failure` passes `qualify_guard_log`. Uppercase `ERROR:` before RUN, between RUN and parameter diagnostic, or before the own fatal also passes.

Evidence: `parser-cases/017-guard-plain-error.log`, SHA256 `491580f641b69360bd924cf0ada4114955c7f0c5a3bff6c6b8020e6beb8bad3a`; `018-guard-plain-fatal.log`, SHA256 `86f6088d87ea1c13bf619dd3b151b1850a0ed1c1919fc0526322f550a185cd32`. See cases 036–038 for the alternate positions. Expected false, actual true. The exact own parameter fatal must remain admissible; its presence must not excuse an unrelated error.

## FC18-P2-02 — Account for error tallies in every qualifier

The normal parser's singular word-boundary regex at lines 209–212 does not match plural `Errors:`. Therefore normal results with `Errors: 1/2/7, Warnings: 0`, including conflicting zero and nonzero summaries, are accepted. Guard output with two or seven errors is also accepted. The mutant parser at lines 491–495 transforms the exact one-own-fatal tally, but other positive tallies pass through to the normal parser and are silently accepted.

Evidence: `007-normal-error-tally-1.log` SHA256 `ed1923fb92ac6e77a4e18710338553ca4bd8c4de3859122a5999c29b3bf96a9f`; `020-guard-error-tally-2.log` SHA256 `426182d5c4a0ca6477584eb59b71ab3b606c9cabf155a53df2140b5863bd0d07`; `032-mutant-error-tally-2.log` SHA256 `694e631a1c0e3859ca087d5bf055698704d361a35f5c7370582f30b365867feb`. Each should reject and actually accepts.

The fix must distinguish normal zero-error execution from the single expected own fatal in a guard or behavioral mutant run. Freeze and document the policy using the actual saved ModelSim format. Multiple stage-local zero summaries are not automatically contradictory; do not reject valid compile/load/simulation combinations merely because the word `Errors` occurs more than once. Extra, malformed or contradictory nonzero error accounting must not become success.

## FC18-P2-03 — Do not mask an unsuccessful selected run with another width's hit

`mutant_cases`, lines 809–818, computes group success as `any(record.ok) and all(record.compile.ok)`. It ignores an unrelated simulation error, abnormal simulator exit, or timeout in another selected width. Thus the runner reports success even though a requested run failed for a reason other than the target mutation.

`probe_aggregation.py` exercised the real aggregation function with local compile/simulation stubs. In each negative case, only cancel-ignored width 2 was altered; the other selected widths remained healthy numeric target hits. The all-good control passed. A foreign `** Error`, exit 17, and a timeout each incorrectly produced overall success: three unexpected accepts out of four cases. See `AGGREGATION_CASES_FROZEN.json`, `AGGREGATION_PROBE_RESULT.json`, and the per-case records under `aggregation-cases/`.

These are **synthetic orchestration probes**, not ModelSim execution or new RTL mutant evidence. A healthy, fully qualified surviving width may be distinguished from an execution failure if the specification only requires one target counterexample per mutation class. Either way, every selected invocation must be accounted for; an unexpected error, timeout, abnormal exit or incomplete transcript must propagate to overall failure.

## Verification method and limits

The coordinator inspected the delivered implementation before designing these probes. Expectations and inputs were saved before each probe execution; no claim is made that the coordinator's new probes were frozen before reading the implementation.

The pure-qualifier probe ran 43 cases, including 11 expected-accept controls. It produced 15 unexpected accepts and zero unexpected rejects. The orchestration probe ran four cases and produced three unexpected accepts. Subprocess creation was disabled in both probes; no vendor tool, network request or product test suite was invoked. Complete input text, output, script bytes and command exit records are preserved alongside this report.

The RTL and the main absolute-edge reference were read. No new RTL bug was established. Saved main results remain 132010 standalone edges and 112 composition edges, with four compiled mutant counterexamples. These are reviewed historical executions, not coordinator reruns. Final width-32 behavior is bounded-prefix evidence only.

The current fresh PR30 readback matches the reviewed head. A comment `6296895679` separately reports bounded acceptance of operation 17; it is not acceptance of operation 18. The coordinator read that comment but did not independently re-download its referenced A artifacts this turn. A-delivered/C-queued transport records are not peer acceptance.

Corrective work must preserve all original operation-18 manifests, receipts, snapshots, successful and failed logs. Publish any fix as a new operation on the same PR30. No RTL, old oracle, timing, synthesis, board or public-interface expansion is authorized by this review.

Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01–H15; requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, contract pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, design `1011259415a0916054eb580687612580bc1e5f09`. All 29 formal cards, G05/B06/R03, board and system remain not_run. Only A may operate the physical board.
