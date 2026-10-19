# Quality-main specification: offline patch transaction core

Task B-RUNTIME-CONTINUITY-20261016/v1. Work/operation B-LOCAL-PATCH-TRANSACTION-OFFLINE-20261018-v1.
Base bbb66759dc02f1c02a3c124473d2527a454e5317. Owner repair chat 01a14296-5b5e-7681-b339-d59c4596175b. This is an offline infrastructure increment, not a product task or a deployment permission.

## Ownership and immutable requirements

Main private root: D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/runtime-continuity-20261016/local-patch-transaction-offline-20261018/.
One Flash worker may write ONLY:
- D:/pynq/CarlandFPGA/.local/worktrees/runtime-continuity-20261016/fpga_mesh/local_patch_transaction.py
- D:/pynq/CarlandFPGA/.local/worktrees/runtime-continuity-20261016/tests/test_local_patch_transaction.py
- D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/runtime-continuity-20261016/local-patch-transaction-offline-20261018/worker/
The main writes specification, independent acceptance scripts/logs and later public evidence/handoff. The main will not edit the two source files until worker completion and ownership release. No other fpga_mesh/deploy source changes. No package or old evidence rewrite.

Every participant reads AGENTS, B standing orders and the installed B/C fpga-multi-node skill/role. Recompute all H01-H15 from pinned f5989cd5defce561f9ba98e6b18fc2682945f0a2, requirements-only canonical JSON (ensure_ascii=False, sort_keys=True, separators=(',', ':')), expected c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804. Freeze1011259415a0916054eb580687612580bc1e5f09. A alone operates boards. No contract changes. Main owns acceptance. Worker reports real blockers to main with [需桌面回合] or [需本人操作] and stable IDs; no independent messages/presence, no credential/service/SQL changes.

## Chosen minimum complete scope

Standalone standard-library module, no CLI and no integration/import of update, runtime, service, ledger, credential or launcher code. Existing updater refusal and admission fences remain untouched. It replaces EXISTING regular code files only: no add/delete, no directory creation inside target, no metadata/ACL-preservation claim. This deliberately bounds the offline transaction; a future installer must separately review new-file dependencies and metadata semantics.

Allowed target names are plain ASCII project source paths in fpga_mesh/*.py or tests/test_*.py (one filename directly under that directory), with a conservative deny rule for config/credential/secret/auth/state/launcher/ownership names. AGENTS, .git/.local/.codex, configuration, credentials, database/state, launchers, owner declarations and all deploy paths are rejected, even if a supplied digest matches. Source payload paths may be regular binary files under their own separate source root; no production files are copied into the test target.

Public API:
- dry_run(plan_path, *, reviewed_plan_sha256) -> structured validation summary; no filesystem writes anywhere.
- apply(plan_path, *, reviewed_plan_sha256) -> structured success/failure/rollback report. Preflight rejection raises a clear validation/busy exception before target writes. Runtime failure reports real partial/ambiguous outcomes; no automatic retry.
- inspect(plan_path, *, reviewed_plan_sha256) -> read-only recovery facts for the exact planned journal. It never mutates, resumes, retries or rolls back. Malformed/torn/unreadable evidence produces an explicit ambiguous report, not success.
Names may differ slightly only if documented in worker report; keep the interface small.

The caller's REQUIRED reviewed_plan_sha256 is an out-of-band raw-plan-byte SHA256, never inferred from the plan. This is a binding/check, not proof that a human approved installation. Parse strict UTF-8 JSON, reject duplicate keys, unknown keys/schema, non-finite values, bool-as-size/schema, empty lists and malformed digests/operation IDs. Persist exact approved plan bytes. Plan fields:
schema=1, operation_id, target_root, source_root, journal_root, files=[{path, source, preimage:{size,sha256}, postimage:{size,sha256}}].
All fields required, all sizes nonnegative integers; all digests lower-case 64 hex. Reject no-op pre==post entries. Explicit path roots must be absolute existing local directories. The journal directory for this operation is journal_root/operation_id, never reused. For predictable evidence and memory bounds set documented conservative limits (e.g. max 64 entries, 16 MiB per file, 64 MiB total); reject over-limit before reading huge data.

## Path and identity checks

Reject traversal, noncanonical/dot paths, absolute payload/target paths, backslashes/colon/ADS, Windows device names, trailing dots/spaces, control chars, casefold duplicate targets/sources and 8.3 aliases. Reject every symlink/junction/reparse point encountered in plan, roots, intermediate components, target, source, journal files and temporary paths. Inspect lstat/file attributes, not resolve alone. Reject hard-linked files (st_nlink != 1) and identity aliases across plan/source/target files. Refuse target/source/journal root equality or ancestor overlap, including case/identity aliases; plan_path lies outside all three roots. Roots must be canonical existing paths, not UNC/device forms; do not silently normalize an alias into authorization.

Revalidate relevant roots/components/identities before every target/backup/journal operation. Maintain the target root identity captured at preflight. Treat a changed parent/root as conflict; do not follow it during rollback or inspection. Journal integrity, path safety and backup hashes are prerequisites for any rollback. These are detection/recheck safeguards, not an OS-level compare-and-swap against a hostile arbitrary concurrent writer.

## Exclusivity and preflight

On Windows use an OS named mutex keyed by stable target directory identity (volume/device + inode/file ID), shared by all cooperating calls even with different operation/journal roots. Use a nonblocking wait; busy => no journal or target writes. Global namespace is preferable; permission/API failure must fail closed, never weaken exclusivity. Abandoned mutex => explicit reconciliation, no apply. Close/release owned handles reliably. A non-Windows implementation may fail closed for apply while retaining validation/inspection, or provide equally explicit supported locking; do not silently pretend Windows behavior on another platform.

Under exclusivity validate the entire plan and all pre/post bytes before creating an operation journal or touching any target. Dry-run is read-only and does not grant later apply permission; apply always repeats validation. Existing operation journal => refuse, including completed/failed/crashed states and changed plan with same operation ID. Different reviewed operations are distinct decisions, not automatic recovery.

Read fixed payload bytes with exact SHA256/size, preserving CRLF/binary bytes (no canonical line-ending hash). Capture file identity and bound reads. Recheck each preimage immediately before backup and again immediately before replacement. A source changed after its approved bytes have been loaded may not substitute different bytes. Source/plan/root aliases and changes must be rejected or handled with a clearly fixed immutable payload snapshot.

## Durable journal and application

Create the new journal directory exclusively only after the complete preflight. Save original plan and ALL preimage backups before the first target replacement. Use exclusive creation, file flush + os.fsync, then verify backup bytes/hashes. A failure writing any backup/initial journal leaves every target unchanged. Keep evidence, do not delete a failed operation directory and retry it.

Use append-only ordered JSONL journal events with sequence and previous-event digest + record checksum, flush/fsync on every durable record; a partial/torn final record is explicitly detectable by inspect. Record prepared, per-file write intent (including temporary name), applied with observed identity/hash, rollback intent/result, terminal result. A state snapshot is optional, not a substitute for a durable write-ahead record. Persist a write intent BEFORE each target replacement. Failure to persist the required intent means do not perform that write.

Write payload to an exclusively created sibling temporary file, flush/fsync, verify its bytes/identity, recheck the target's exact preimage and identity, then os.replace. Recheck resulting target bytes/hash and identity. Register known successful replacement in memory immediately after os.replace returns, before later injectable failures/journal writes. No content or secrets in error messages/journal beyond the explicit non-secret plan/hashes; no private production bytes in fixtures.

Record known writes separately from attempted/uncertain replacements. An exception that leaves it unclear whether replacement occurred is ambiguous and may not be silently called unchanged or rolled back as proven ownership. A normal returned replace followed by postcheck/journal failure still belongs to this operation, subject to rollback checks. Unexpected BaseException/process exit leaves evidence for inspect; do not convert it into automatic resume.

File fsync is an attempt to persist data, not a guarantee of directory-entry durability, arbitrary power-loss atomicity or ACL preservation on Windows. Document this boundary. No service restart functionality exists.

## Rollback and recovery

On an ordinary caught failure, consider known successful replacements in reverse order. Roll back only if the current target still matches BOTH this operation's recorded postimage bytes/hash and identity, with safe unchanged parent/root components. Any foreign edit (including a same-bytes replacement with different file identity), unreadable target, changed link/root, missing file or corrupt backup is preserved and reported as protected/ambiguous. Verify original backup bytes before use. Restore via a separately fsynced sibling temporary file and os.replace with a durable rollback intent; recheck before replacing and verify afterward.

If journaling has failed and a rollback intent cannot be made durable, do not perform an unjournaled rollback: report partial/ambiguous and preserve remaining bytes. A rollback write failure must not prevent independently safe remaining rollback attempts unless the shared journal/path prerequisite is lost. Report exact rolled_back/protected/failed/uncertain paths; never return successful_all_or_nothing if any target is unknown. Retain backups/journal/temp artifacts for diagnosis; no sweeping cleanup or deletion of foreign-modified temporary files. Existing journal always prevents a new apply even after a successful automatic rollback.

Inspect validates exact plan binding, safe journal paths and event hash chain, backup identity/hash and current targets without writing. Include terminal record if valid, each target's current classification (preimage/postimage/other/missing/unreadable), evidence of write intents and confirmed writes, unresolved/partial records and an explicit requires_main_review flag. A digest match alone never proves that this process performed an interrupted write. No resume/retry/restore entrypoint.

## Acceptance matrix (main decides)

Tests use only private fixture directories (set TMP/TEMP beneath worker/ or main private root), and real filesystem operations. No site root, existing worktree sources, scheduled tasks, service control, live SQL, board or network fixtures. Worker may run only its module's focused tests. Preserve all failing/corrected outputs.

Required scenarios:
1. Exact two/three-file success, CRLF and binary payload bytes, backup/plan/journal checks, dry-run and inspect file-tree byte/mtime snapshot unchanged.
2. Invalid final entry/preimage/source/plan hash/size stops before ANY target or journal write; strict schema, duplicate-key/bool/oversize/empty/no-op rejection.
3. Every replacement index fails before replace and after replace; returned success followed by failure is rolled back when safe. Simulated OSError after a real replacement must remain honest about uncertain ownership.
4. Inject ENOSPC/write/flush/fsync failures on backups, initial log, payload temp, write intent, postwrite log and rollback intent/temp/replace; distinguish injected faults from physical disk tests.
5. Concurrent target modification after full preflight/before each write; foreign changes after earlier applied write; same-bytes foreign replacement; corrupted backup; source/parent/root substitution. Preserve foreign bytes and report partial/ambiguous honestly.
6. Existing journal (empty/complete/failed/torn), repeated operation ID with same/different plan and simultaneous new applies (including different journal roots, same target) fail closed; use real subprocess lock contention and a real crash os._exit at a write boundary, then read-only inspect and refused replay.
7. Traversal, absolute escapes, ADS, Windows reserved/trailing/case aliases, overlap among plan/source/journal/target, actual hard link, actual Windows junction and symlink where supported. Record unsupported OS capability skips with exact cause; use available junction creation as a real Windows test, not only monkeypatched flags.
8. Real Windows file sharing or read-only-target replacement failure; retain the exact OS error. Mocks/hooks are only fault injection on private fixtures, not evidence of live installation.
9. Partial rollback with one protected or failed file and safe restoration of another; corrupt/torn journal inspection cannot mutate or claim clean completion. Check file IDs and bytes, not only the returned status.
10. Module imports no live entrypoints and previous updater/admission code remains unchanged. Only necessary focused combination checks after independent review; no historical full test reruns.

Worker deliver source, tests, raw command/version/logs, summary mapping scenario->test, limitations and actual output hashes; mark ownership released. Main independently reads code, runs focused tests with import provenance, exercises any missing adversarial scenarios and decides acceptance. Runtime/OS failure injection is not deployment approval. Product operation09 continues independently.
