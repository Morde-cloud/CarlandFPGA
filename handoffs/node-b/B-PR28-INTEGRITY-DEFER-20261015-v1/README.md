# Preserve untouched work on runtime-integrity failure

Operation `B-PR28-INTEGRITY-DEFER-20261015-v1`; runtime repair task `B-RUNTIME-REPAIR-20261015/v1`.
Source/tested commit `359304b20f43b516ae20aafeb7c24ca6f6bb58e2`; previous reviewed PR28 head `30de232e66b984d13acdcbf7788631ed49be2151`.

A's exact-head review found that a changed or incomplete immutable runtime cache raised an ordinary RuntimeError before any turn request, terminalizing untouched messages. B independently ran A's unchanged offline probe: two messages became failed with zero turn requests. Baseline exit 0 means the defect was reproduced.

The fix introduces RuntimeIntegrityError at cache verification and classifies only initialization-time occurrences as runtime_integrity before-work deferral. The existing controller persists the queued run and node cooldown, so the next untouched message is retained. Validation remains fail-closed; no cache replacement, retry of ambiguous turns, or new inference loop is added. Errors at the turn/start boundary remain terminal and require reconciliation.

B main independently reviewed the complete diff and raw child logs. The final source bytes match Git blobs above and passed 168 software tests (original 161 plus 7 new), Python 3.12.9, exit 0. Exact command, hashes and original streams are in source-validation.json and regression-*.

New tests exercise real pinning over fake executable bytes, Controller, SQLiteStore and MainSessionRouter over temporary databases: corrupt/missing cache, two queued messages, persisted cooldown, reopening both ledgers, explicit fixture repair with mock time, exactly-once untouched work, and rejection of prior failed/interrupted entries. They invoke no real executable/model/network/service. The child first had a request-recording assertion error; its raw failed run is preserved, then its final seven tests passed. The main subsequently strengthened the reopened-router check and normalized the new source to LF before the final 168-test run.

The unchanged A probe intentionally retains its original assertion that messages must be failed. After the fix it exits 1 with AssertionError; fixed-probe-result.json separately verifies its actual output contains two queued/retryable results and zero turn requests. This expected old-assertion failure is not reported as a passing probe process.

Earlier repair records and operations remain unchanged and are scoped to their original commits. The earlier live tool smoke predates the final pre-send running fence and this fix. This handoff does not deploy to B or A: B's busy original service remains PID42680; final reload and fresh exact-version live operation remain pending. No RTL simulation, synthesis, implementation, board or product/system acceptance is claimed.

Implementation task DEEPEYE-IMPLEMENTATION-20261014/v1 and frozen source1011259415a0916054eb580687612580bc1e5f09 are unchanged. Contract DEEPEYE-HUMAN-LOCK-20261014/revision1, H01-H15, fixed requirements SHA256c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804. Physical board A only. Original credentials, queues, service definitions and product writer ownership are preserved.
