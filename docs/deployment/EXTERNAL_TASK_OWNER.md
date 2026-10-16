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

After actual consumption, `fpga_external_receipt` (local action
`external_receipt`) accepts `message_id`, `task_id`, `task_version`, `thread_id`,
`turn_id` and `evidence`. It requires the saved exact task/version/recipient and
unchanged valid declaration, rejects STOP, and makes the first receipt immutable.
The state becomes `external_consumed`, not a fabricated mesh turn completion.
The receipt is the caller's reported evidence; the API cannot authenticate an
App turn or prove a product result. Main review still checks the actual history.

## Safe deployment boundary

`assert_idle` and `stop_idle_node` reject any nonempty/invalid external-owner
declaration and any pending external delivery, including with empty `main_runs`.
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
