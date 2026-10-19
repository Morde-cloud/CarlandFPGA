# Independent quality-main review criteria

Review code and tests after the sole worker releases ownership. Public acceptance is offline core only.

1. Authority binding: caller-required raw plan SHA, full exact-key schema and digest/size/ID checks. Reject missing reviewed hash, unknown keys, duplicate JSON keys, bool numeric fields and malformed/empty/no-op entries. Test protected targets and source/plan/journal overlap independently.
2. Writes: full validation of all entries precedes any journal/target mutation; every backup is verified before first target replacement. Fixed payload bytes are not replaced by a later source edit. Limits precede large reads.
3. Identity: Windows actual reparse flags/junctions and hardlinks checked, root/parent identity retained, same-bytes foreign replacement is still protected. Case/8.3/ADS/reserved aliases cannot create two plans for one path under different names.
4. Exclusivity: process-level lock uses stable target identity rather than operation or journal-root name. Global mutex failure/abandonment fails closed. Worker must test two DIFFERENT operation and journal roots with same target, not only identical plan retries.
5. Journal WAL ordering: durable plan/backups/prepared before writes; intent before replace; confirmed replace kept in memory before later failures. No target rewrite if required intent cannot persist. Checksum chain detects torn/corrupt evidence. Snapshot inspect remains strictly read-only.
6. Failure state taxonomy: attempted != confirmed; an ambiguous replace must not claim unchanged. postcheck failure with foreign data preserves it. A postwrite journal failure cannot erase a successful replacement from the result. Final report cannot say committed/rolled_back when any path or journal is uncertain.
7. Rollback ownership: safe current path + unchanged root/parent + exact own postimage AND identity + original backup hash; no generic restore on a coincidental digest. Continue safe independent rollbacks where possible; journal failure stops further unjournaled writes. No automatic temp/journal deletion.
8. Crash: real child process exits at a recorded boundary; new apply refuses the old journal regardless of current bytes. Inspect classifies reality without asserting who performed an unresolved write. Same operation ID with altered plan cannot reuse the directory.
9. Windows evidence: hardlinks/junction/share-lock/mutex use real local private fixtures. Symlink privilege failure is an explicit capability limit. ENOSPC, fsync and journal failures are injected faults, not physical disk-full or power-loss claims. Existing APIs/CLIs remain unmodified and uncalled.
10. Delivery: focused tests have exact module import/hash proof and raw logs. No full historical suites. Compare all tracked changes against ownership and all selected live baseline hashes. Commit tested source before constructing operation manifest; verify raw Git artifact bytes. Read actual remote state before any bounded non-force publication; no old action replay.

The main's capability probe independently verified a Global named mutex, real hardlink nlink=2, and a Windows junction reparse flag of 1040. Creating a symbolic link failed for insufficient privilege. This limits an actual-symlink test only; it does not excuse accepting reparse points.

Official implementation references (read 2026-10-18):
- https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createmutexw
- https://learn.microsoft.com/en-us/windows/win32/termserv/kernel-object-namespaces
- https://docs.python.org/3.12/library/os.html#os.fsync

Named mutexes coordinate cooperating processes; default ACL denial must fail closed. They do not prevent arbitrary external writers. File flush/fsync and replace are bounded evidence, not a guarantee of crash-safe directory persistence, arbitrary TOCTOU elimination, ACL preservation, or a safe live maintenance window.
