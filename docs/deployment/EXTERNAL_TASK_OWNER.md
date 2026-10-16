# Explicit App ownership and durable delivery obligations

Work `B-DIRECTOR-OWNER-GUARD-20261016-v1`, task
`B-RUNTIME-CONTINUITY-20261016/v1`, extends PR29's source-only repair.
This change does not create a live ownership declaration, change a product
session, deploy a service or send an App message.

## Why A27 needs adaptation

A27 at `1533d91dc62471acc6cc388cdc8ec53dc09f9ba7` checks an explicit
`external-task-owners.json` before mesh routing. Its rejection is a generic
`RuntimeError`. Copying only that check into B would enter the existing gateway's
generic error handler and mark unsent work `failed`. B instead preserves an
unsent message as an external delivery obligation, while keeping the historical
failed/ambiguous messages terminal. A27's role/model changes and retired-director
declaration are not part of this patch.

## Declaration and message handling

The optional declaration lives beside `main_sessions.sqlite`, keyed by task ID.
An entry contains `owner_kind: "desktop"`, `thread_id` and a positive integer
`task_version`. The recipient and version must exactly match the existing
registered session and incoming message. This prevents a declaration from
silently appointing a new product main. A27's older two-field declaration is
held for reconciliation until an explicit version is supplied; it is not
silently interpreted as the current version.

Absent file or absent task leaves existing routing unchanged. An invalid entry
holds only its own task. A globally unreadable, malformed or duplicate-key JSON
file prevents scope identification, so all new unsent work is held fail-closed
until the configuration is reconciled. A missing or invalid recipient is recorded
as unknown, never invented. File contents are local declarations, not authority
to create chats, move owners or change credentials.

Checks run before preparing a client, at awaited routing boundaries and before
work send, including when the mesh has already loaded the thread. The controller
does not advance child task versions for a human revision routed to an external
owner; the actual App main must consume that revision under the existing policy.
Human STOP remains immediate and precedes both dispatch and receipt advancement.
Declarations must be changed under coordinated admission control: these checks
are not an OS lock against a concurrent uncoordinated file editor or App writer.

For an unsent external message, one transaction in `main_sessions.sqlite` saves
its full original envelope, exact recipient/version, per-entry declaration hash,
reason and `pending` delivery state, and records `main_runs.delivery_pending`.
Only after that commit may the inbox dispatch row be marked processed. Processed
means transferred to durable delivery bookkeeping; it does not mean delivered,
executed or accepted by the App. The controller suppresses ordinary result/report
callbacks for this path and continues other independently executable tasks
without a node-wide cooldown. Two or more messages retain separate obligations.

A crash between the delivery commit and inbox consumption reuses the saved
record. Restart or declaration removal never automatically replays that message.
Existing completed, failed, interrupted, running/ambiguous or externally consumed
messages cannot become new mesh work. This patch does not reinterpret the two
real `thread/resume ... already has an active writer` failures from October 16.

## Inspection and reported receipts

`fpga_external_deliveries` (local action `external_deliveries`) lists obligations
and reported receipts. `fpga_self_check` includes the same records. `main_wait`
returns `delivery_pending` promptly rather than holding a caller indefinitely.
It is a delivery boundary, not a successful work result.

The read-only continuity collector tolerates older ledgers without the new table.
Pending entries appear as `external_delivery_pending` incidents with their saved
recipient and reason, including after the inbox row was consumed. They are App
handoff obligations, not terminal model results or grounds to create another
repair chat. Existing opt-in watches cannot enqueue another mesh notification
for a declared external owner or task with pending external delivery. Startup
source fingerprints also cover `sessions.py` and `update.py`; these fingerprints
compare disk bytes at startup with current disk bytes, not proof of a live reload.

The existing authorized App caller must inspect the original envelope, STOP,
current ownership and actual App activity before doing any delivery. There is
no new App send/wake mechanism, model polling or inference router here. If a
send's outcome is unknown, inspect actual App history; this ledger does not
authorize retrying a potentially delivered message.

Before any App send, the authorized caller must use `fpga_external_transition`
(local action `external_transition`) with `action=attempt`, a stable operation ID,
the saved message/task/version/recipient, the registered main's thread ID and
review evidence/reason. The transaction saves `delivery_unknown` before sending
could occur. Only the first call returns `execute=true`; an identical repeated
call returns false, a different payload under the same operation ID conflicts,
and a second attempt is forbidden. This is bookkeeping under existing authority,
not new permission to send. Recheck STOP and actual App activity before acting.
The local front door also rejects an attempt superseded by a newer persisted
human task version, even while the original session version is still unchanged.
The tool itself never sends or wakes a chat. A crash after the claim is an unknown
outcome even if the caller believes it probably did not send.

After actual consumption, `fpga_external_receipt` (local action
`external_receipt`) accepts `message_id`, `task_id`, `task_version`, `thread_id`,
`turn_id` and `evidence`. It requires the saved exact task/version/recipient and
unchanged valid declaration, rejects STOP, and makes the first receipt immutable.
The state becomes `external_consumed`, not a fabricated mesh turn completion.
The receipt is the caller's reported evidence; the API cannot authenticate an
App turn or prove a product result. Main review still checks the actual history.

## Explicit reconciliation of never-delivered obligations

The published v1 source `f26caaeea99fde4378f9a8d12e38aa97ef15eac7` had a P2
recovery dead end: a corrupt declaration saved null recipient/hash, or a mismatched
version saved incompatible identity, and correcting the declaration could never
satisfy receipt matching. The v1 manifest and 130-test logs remain historical
evidence, not acceptance of that defect. The v2 operation adds this explicit path.

For a `pending` record with no recorded delivery attempt or receipt and a matching
`delivery_pending` main result, the quality main may call the same transition
API with `action=withdraw` or `supersede`. It must supply a unique operation ID,
the **original saved** task/version/recipient (including null when originally
unknown), `confirmed_not_sent=true`, actual review `evidence`, a specific `reason`,
and a `followup_work_id`. The reviewer thread must match the registered task main.
An erroneously held task that has no registered session requires an explicitly
identified existing registered reviewing main; this never creates or assigns a
new main. The reviewer and followup work are retained as the responsibility for
the decision and remaining work. The authenticated caller is still responsible
for checking human authority and actual App history; these strings are reported
evidence, not independently authenticated proof that no App tool was used.

Withdrawal records `withdrawn_unconsumed`. Supersession additionally requires a
distinct, complete `external_delivery` successor that is still pending and has
never been attempted, under the same task at the same or a newer version. Its
saved envelope must match its record; an orphan queued `main_runs` row is
insufficient. The result is `superseded_unconsumed`. Both retain the original envelope,
recipient, bad declaration hash/reason and complete resolution record. Neither
can be receipted as consumed or replayed by mesh, and neither sends the successor.
The same operation/payload is idempotent; altered payloads, STOP, wrong identity,
missing review/responsibility, failed/ambiguous/executed work and any prior delivery
attempt are rejected. Fixing/removing a declaration is not itself reconciliation.

Self-check shows the explicit closure and retained responsibility, without
reporting model completion or scheduling a notification. The closed obligation
ceases to block the ledger idle check; a pending successor, unknown attempt or
still-declared external writer continues to block. Withdrawal is never a shortcut
around actual App writer inspection or a way to discard unfinished responsibility.

## Safe deployment boundary

`assert_idle` and `stop_idle_node` reject any nonempty/invalid external-owner
declaration and any pending/unknown external delivery, including with empty `main_runs`.
The latter check is inside the existing SQLite admission fence; the declaration
is checked again after the fence is acquired. A consumed receipt does not release
a still-declared external writer.

These checks do not discover unregistered App writers. Before stopping or
updating, the authorized coordinator must inspect actual App threads and worker
receipts, establish that all writers have finished, resolve unknown operations,
and prevent concurrent new App work/declaration edits. It must also satisfy the
original ledger/admission checks. An empty `main_runs` table, missing declaration,
completed model turn or health response alone is insufficient. Do not delete a
declaration, cancel jobs, clear locks or rewrite SQL merely to pass the guard.

Current B has the original live service and product App entry; this patch is not
loaded and cannot prevent their writer collision yet. Safe coordinated deployment
and an explicit reviewed declaration remain separate decisions. No permanent
role migration, unattended App wake, service reload or board acceptance is claimed.

Software tests use isolated fixture DBs and fake app-server transports. They
cover independent tasks, multiple pending messages, crash/restart, no replay,
STOP, version/recipient mismatches, routing races, actual-receipt fields and idle
rejection. Raw exact-commit logs and manifest accompany the source handoff.

Preserve `DEEPEYE-HUMAN-LOCK-20261014/revision1` H01–H15, pinned contract commit
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Only A operates the physical board.
