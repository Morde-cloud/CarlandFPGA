# Offline patch transaction core — Node B

This increment adds a standalone Windows file-replacement core and focused fault-injection tests. It addresses the missing transactional primitive identified by the earlier isolated merge rehearsal. It is not connected to the live updater, resident service, task ledger, launchers or installation entrypoints.

- Task: `B-RUNTIME-CONTINUITY-20261016/v1`
- Operation: `B-LOCAL-PATCH-TRANSACTION-OFFLINE-20261018-v1`
- Recovery work: `B-LOCAL-PATCH-TRANSACTION-OFFLINE-RECOVERY-20261019-v1`
- Tested source commit: `501cd7aa8d3700b57e20fee4e93a7c0319a32110`
- Base: `bbb66759dc02f1c02a3c124473d2527a454e5317`
- Acceptance: `QUALITY_MAIN_ACCEPTED_OFFLINE_TRANSACTION_CORE_ONLY`. Coordinator acceptance of this increment has not yet been observed.

## API and bounded behavior

`fpga_mesh.local_patch_transaction` exposes `dry_run`, `apply` and `inspect`; each requires a plan path and the keyword `reviewed_plan_sha256`, which binds the exact raw plan bytes. `dry_run` and `inspect` do not write. `apply` is Windows-only and replaces existing regular files named directly under `fpga_mesh/*.py` or `tests/test_*.py`, subject to a conservative denied-name filter. It cannot add or delete target files. There is no CLI.

The strict version-1 JSON plan contains exactly `schema`, `operation_id`, `target_root`, `source_root`, `journal_root`, and `files`. Each file contains `path`, `source`, `preimage` and `postimage`; each image contains `size` and `sha256`. Roots are existing disjoint local absolute directories; the plan is outside all three. All files must pass validation before any target write. Limits are 64 files, 16 MiB per image, 64 MiB combined pre/post bytes, a 1 MiB plan, and a 16 MiB journal.

The core checks path components, reparse points, hard links, file identities, expected sizes/hashes and duplicate aliases. A target-identity Global Windows mutex serializes cooperating callers. It refuses an existing operation journal. It snapshots approved payload bytes, creates and verifies all backups, appends sequenced hash-chain journal records with fsync, records intent, rechecks prerequisites and replaces through exclusive temporary files in the target directory.

On failure, rollback is limited to verified backups and still-owned postimage identities/bytes. Foreign edits or ambiguous writes are retained for review. Inspection checks evidence and current files without replay, rollback or cleanup. Journals, backups and temporary artifacts remain available.

These checks do not eliminate all arbitrary external races. A hash chain detects damage but is not an authenticated proof against an attacker rewriting the whole chain. File fsync and replacement do not establish power-loss directory durability. ACLs and other metadata are not preserved. A plan hash does not grant installation approval. Live installation still needs a separate reviewed assignment, preconditions, ownership and acceptance.

## Executed validation

Python 3.12.9 on Windows 11. The quality main ran 61 test methods: 37 module tests plus 24 independent acceptance tests. Result: **60 passed, one skipped, no failures or errors**. The skip was actual symbolic-link creation denied by the machine's current privileges. All 86 observed unittest subtest callbacks passed; those are not 86 additional top-level tests. The final unittest duration was 12.338 seconds and the whole process took 13.125 seconds.

Actual Windows hard-link, junction, Global mutex contention/abandonment, sharing-lock and subprocess crash cases were exercised. The sharing-lock run returned native **WinError 5**, retained in `main-run-final/call-observations.jsonl`; the test accepts OS errors 5 or 32 and requires unchanged target bytes. An over-specific receipt assertion expecting only 32 was corrected without changing code/tests or rerunning them; see `ACCEPTANCE_ASSERTION_CORRECTION.json`.

All recorded main-process project imports resolve to the isolated worktree. Spawned test scripts explicitly insert that worktree, but this receipt does not claim a complete per-child import inventory. Nine selected live boundary files matched their private baseline; existing tracked runtime/updater/deployment source files were untouched. The private AGENTS content and its hash are not published.

The DeepSeek worker timed out with no final result or test report. Its partial source/test bytes were preserved privately; after verified terminal failure and ownership release, the quality main completed independent validation and repairs. This is not a successful worker completion and the failed job was not replayed. `FAILED_WORKER_RECEIPT.json` and `RECOVERY_DECISION.json` preserve that distinction.

The main found and fixed four defects, with original failed runs retained:

1. Inspection accepted a foreign replacement with restored bytes after rollback; it now requires the recorded restored identity too.
2. A modified restore temporary could be moved into the target; its size/hash/identity are rechecked immediately before replacement.
3. A same-byte foreign replacement during rollback could be reported as owned restoration; the destination must match the verified restore temporary's identity.
4. Journal corruption after write intent could precede a replacement; the journal path, identity and chain are revalidated before apply/rollback replacements.

`main-run-01` retains the first failure (57 methods, one failure, one skip). `main-run-02` passed 58 methods with one skip. `regressions-before-fix` retains all three later failing tests; `regressions-after-fix` shows all three pass. `main-run-final` is the final 61-method run. Do not substitute earlier results for the final source hashes in `source-binding.json`.

## Reproduction and evidence

Verify the standard handoff manifest against this checkout first:

```powershell
python -X utf8 .agents/skills/fpga-multi-node/scripts/handoff.py verify --root . --manifest handoffs/node-b/B-LOCAL-PATCH-TRANSACTION-OFFLINE-20261018-v1/manifest.json
```

The exact original commands, stdout, stderr, selected test IDs, API observations, results and source hashes are retained. Harnesses are archived verbatim and contain this machine's worktree path. For a new review run, copy `independent_acceptance.py`, `run_focused_tests.py` and `execute_focused.py` to a new private evidence folder. In those copies only, set `WT` in `run_focused_tests.py` and the `cwd` in `execute_focused.py` to an isolated checkout of the tested source commit. Use a fresh run ID and invoke:

```powershell
python -I -B -X utf8 <private-evidence-folder>/execute_focused.py review-run both
```

The runner creates private synthetic targets, payloads and journals; it never needs a production target or resident-service action. Keep new reproduction results separate from this historical evidence. Do not invoke the patch API against the live checkout as a test.

## Requirements and remaining boundary

H01–H15 of `DEEPEYE-HUMAN-LOCK-20261014`, revision 1, remain fixed at commit `f5989cd5defce561f9ba98e6b18fc2682945f0a2`; canonical requirements-array SHA256 is `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`. The final product freeze remains `1011259415a0916054eb580687612580bc1e5f09`. This infrastructure evidence is not product acceptance. A alone operates the physical board. No simulation, synthesis, implementation, board measurement or live deployment was performed for this increment.

`SPEC.md` and the review criteria are historical inputs; their original prospective worker wording is retained. The final state is recorded in `MAIN_ACCEPTANCE.json`, `source-binding.json` and the operation manifest. Publication and main consumption are separately recorded in private handoff receipts after remote readback.
