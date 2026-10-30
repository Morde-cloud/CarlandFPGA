# Compact outer resource envelope 107

Task DEEPEYE-IMPLEMENTATION-20261014/v1, work
`B-DEEPEYE-FUNCTIONAL50-RESOURCE-RECOVERY-20261031-107`. Original105 was actually
cancelled and closed at17:25:01; its late59KB partial source and four patch
probe/temp files remain preserved. No105 STARTED/RESULT/runtime qualification
was observed. Source writing did occur. This new assignment neither reuses
that job nor replays a failed runtime.

Preparation is **SOURCE ONLY**: candidate imports, syntax checks, tests, native
Job creation, process launch and vendor/build/board operations are NOT_RUN until
the main freezes exact sources and explicitly releases first software controls.
The main owns decisions, review, evaluation, acceptance, Git and any later103
build. A26's one build remains unconsumed. No default CLI launches a command.

H01–H15 / DEEPEYE-HUMAN-LOCK-20261014/r1, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, contract pin
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, freeze
`1011259415a0916054eb580687612580bc1e5f09` remain fixed. Full3D/UI, volume
collisions, free layouts/camera/faces, equal gates/complete passage, hidden
truth, causal bounded observations, online3D/PC AI, both complete H12 paths,
all29, original100MHz and final1%/100ms remain required. A alone operates boards.

## API and actual cap semantics

`run_envelope(argv,envelope_dir,build_output_dir,windows_job_path,owned_path,limits)`
accepts an explicit finite argv list, no shell/service/elevation launcher, and
two disjoint repo-contained new paths. It exclusively creates **only** the
envelope directory. The absent build-output target is recorded in its intent;
the unchanged inner builder performs its own exclusive mkdir. This is intent
binding under single-main ownership, not an OS path reservation or lock.
Preexisting paths are refused without modification. No retry or deletion exists.

The pinned unchanged WindowsJob helper
`3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3` and owned
accounting/closure helper
`1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692` remain read-only.
The new outer Job sets ExtendedLimit/class9 flags `0x2208` before launch:
KILL_ON_JOB_CLOSE `0x2000`, JOB_MEMORY `0x200`, ACTIVE_PROCESS `0x8`.
Exact native readback must confirm8GiB Job committed memory and64 active
processes, with no BREAKAWAY/extra flags. This is not an8GiB resident-RAM
guarantee; native allocation limits can make allocation fail without immediately
killing the process. No memory stress test is planned.

The selected build limits dictionary is:

```json
{"mode":"build","wall_seconds":7260,"memory_bytes":8589934592,"active_processes":64,"output_bytes":2147483648,"poll_seconds":1.0,"drain_seconds":5.0,"terminate_seconds":5.0,"launcher_wait_seconds":5.0}
```

The main selected an aggregate nominal7260s budget **including cleanup
reservation**. Live work therefore has7245s from envelope start; the unchanged
inner builder has7200s, leaving45s for startup/postprocessing. Drain, termination
observation and launcher wait each use their cap AND remaining aggregate
budget. Budget exhaustion closes the owned kill-on-close Job and reports
unknown termination unless actual empty state was observed. Elapsed/remaining
time and a nominal-deadline-breached flag are recorded. Host scheduling and
bookkeeping are not an OS-guaranteed hard real-time deadline.
Before calling the unchanged cleanup helper, the outer code reserves bounded
launcher-wait time and allocates helper drain plus termination budgets whose
sum fits the then-remaining amount. A failure reason needs no helper drain;
its available allocation goes to termination observation. Actual allocations
are retained in RESULT rather than independently reusing one remaining value.

Aggregate output is sampled at1s across envelope and build roots. Reparse
points refuse; duplicate file identities count once. The2GiB bound is a sampled
observation with possible writer/sampling/final-bookkeeping overshoot, not an
OS disk quota. The last sampled count and the count before RESULT serialization
are labelled precisely. Nested child Jobs cannot relax parent limits; outer
accounting and parent termination cover the nested descendants.
The final output observation independently sets `final_output_limit_exceeded`;
an exceeded cap forces failed status even if the last monitor sample was below
the cap. RESULT serialization itself can add further explicitly uncounted bytes;
this remains a sampled bound, not an OS disk quota.

## Ownership and terminal evidence

Launch uses CREATE_SUSPENDED, attaches to the new outer Job, then resumes,
with shell=false, no window and binary stdout/stderr. Only newly owned handles
are ever terminated. Launcher exit0 with live descendants is not completion;
the outer loop still observes them, bounded by remaining live time and drain.
Query/output/deadline/launch/attach/nonzero failures terminate only this Job,
observe ActiveProcesses0 within the remaining bound and only then close it.
Attach failure also cleans the original suspended Popen handle. A queried empty
Job alone never proves an unassigned launcher was stopped. CloseHandle's actual
return is recorded, and missing/query-failed/unknown proof cannot become success.

Intent, native cap readback, suspended PID, actual samples/peaks/output counts,
native exit, cleanup/accounting, raw stdout/stderr hashes and RESULT remain even
on owned-output failure. No credentials or environment dump is recorded;
callers must not place secrets in the explicit logged argv. There is no global
service, foreign process lookup, provider change or board connection.

## First software controls — NOT_RUN during preparation

The main will separately release a single attempt of `check_envelope107.py`.
It requires a main `FUNCTIONAL50_107_SOFTWARE_RELEASE_V1` record with actualmain
`01a18824-4172-74e2-a13f-f3e3d1e3ed99`, exactwork/sourcecommit, software_only=true,
vendor_build=false, prepared-input hash and a complete absolute-path→SHA256
`source_files` map. The JSON binds the actual main release; it creates no build
authority itself. Output must be a fresh `.local/v107/<attempt>` directory.

Four harmless cases, in order, use explicit software_test512MiB/8process/1MiB
caps and wall<=15s, with short cleanup/sample bounds recorded percase:

1. Benign launcher exits0 while its nested host uses the pinned inner helper to
   own a finite sleeping leaf. Exact caps, positive committed peaks, outer
   live-descendant samples, inner/outer exit0 and empty-before-close are required.
2. Child exits7; preserve that native exit and prove bounded owned cleanup.
3. Finite writer emits at most2MiB in sixteen sleeping chunks; sampled1MiB
   overflow must stop its Job. No unbounded producer or disk stress.
4. Finite sleep child reaches the actual short live deadline with cleanup
   reserve; record termination/empty/closed proof. No unrelated process kill.

The driver uses one nominal60s software attempt, stops on the first unexpected
failure, never repairs/retries, and records all source before/after hashes,
actual commands/exits, Python version and raw evidence. Software tests do not
execute Vivado, allocate8GiB, exhaust process limits or prove future timing,
BIT/HWH, physical behavior or product acceptance.

The main supplied the primary Win32 API basis (read by main; no network fetch
in this source-only worker): [Extended limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information),
[Basic limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information),
[Nested Jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs),
[SetInformationJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-setinformationjobobject).
