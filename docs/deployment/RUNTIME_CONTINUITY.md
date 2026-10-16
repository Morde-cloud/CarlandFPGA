# Runtime continuity and explicit recovery

The controller now persists result watches and recovery receipts separately in
`continuity.sqlite`. A completed child or main result used to remain in its
ledger after the interested main had ended its turn. An explicitly registered
watch can now enqueue exactly one continuation to that task's existing main.
App proxies remain a separate capability: this mechanism cannot wake an
arbitrary desktop chat or turn a serial mesh session into an App worker.

The monitor checks on startup, inbound/dispatch boundaries, child changes and
main completion. A 60-second ordinary-program timeout covers elapsed wait
thresholds and resume from sleep. It does not poll a model or emit presence
messages. Queues and unbound reservations become visible after 15 minutes;
running work, explicit STOP and capacity backoff have separate dispositions.
There is no generic elapsed-time failure for long computation. Product progress
and acceptance still require the owner's actual artifacts and evidence.

## Tools and durable transitions

After deploying and loading the new tools, use `fpga_self_check` at entry,
dependency arrival, recovery and before ending a main turn. The same action is
available as `project_cli self_check`. It reports incidents, watches, receipts,
monitor errors and startup source fingerprints. Fingerprints compare startup
disk bytes against current disk bytes; they are not a substitute for an actual
tool smoke test or proof that an older resident loaded a new patch.

Before waiting on an existing job, register `fpga_continuity_watch` with:

```json
{
  "watch_id": "task-v1-work-result",
  "task_id": "existing-task",
  "task_version": 1,
  "source_kind": "child",
  "source_id": "existing-child-job-id",
  "recipient_thread_id": "actual-existing-main-thread-id",
  "auto_resume": true
}
```

`source_kind` can also be `main`, with its existing message ID. Source ownership
and version must match. `auto_resume` defaults to false; opt-in requires the
exact registered main thread and version. For an App proxy, record a watch with
false and use its actual App capability/authorized handoff. A title is never a
route. The same source/recipient cannot be registered under a second watch ID.

States are `waiting -> ready -> enqueued -> consumed`. `ready` proves only that
the original result is terminal, including failed/interrupted results requiring
reconciliation. `enqueued` proves durable inbox acceptance only. `consumed`
requires `fpga_continuity_receipt` with the designated thread, actual turn ID
and processing evidence; this is an explicit reported receipt, not independent
product acceptance. The API rejects a receipt before a result or from the wrong
recipient. Keep the actual turn evidence for independent review.

The continuation contains only IDs and a reconcile/remaining-work instruction,
never the child's instructions or credentials. It is a critical main task and
uses the existing official provider route. It passes through the ordinary
controller, preserving explicit STOP. A stable inbox ID makes recovery from a
crash between inbox acceptance and journal update idempotent. Failed/unknown
tool operations are never replayed by this component. Historical tasks are not
automatically subscribed. Unconsumed results produce no unlimited followups.

## Bounded repair chats

An authorized main with the actual App `create_thread` tool may first call
`fpga_continuity_repair` with the incident ID, `phase=claim` and its actual owner
thread. Only `execute=true` permits one creation attempt under existing human
authorization. Reuse an already active repair chat. Define stable task/version,
work IDs and non-overlapping ownership before creation. Native execution still
requires reserve, binding and child self-validation; a repair claim grants none
of those privileges and never appoints a product director.

Persist `phase=created` with the returned ready thread ID, then `phase=started`
with an actual start turn receipt. A queued client ID, transport ACK or parent
binding cannot supply that receipt. After a crash/unknown creation outcome,
record `phase=unknown`, inspect App inventory/evidence, and never call create
again from that claim. Even a repeated claim after restart returns
`execute=false`. STOP, normal active waits, scheduled backoff and resolved
incidents reject repair creation. There is no recursive repair creator or
background model automation. Without App tools, prepare a concrete prompt for
the correct authorized recipient and state that it has not been applied.

## Deployment and local observation

Base: PR28 head `6b0cdaf4bee8d4e41680738155a6015799e7cbad`, preserving PR18.
The B root also contains the existing silent-presence guard omitted from PR28;
this branch preserves that guard and its tests. Do not overwrite the dirty root
with the branch wholesale. Compare original bytes, prepare exact owned changes,
retain config/credentials/task definitions/ledgers, and use the existing
`assert_idle` and atomic `stop_idle_node` admission fence before deployment.
Reserved jobs and unknown native stop outcomes block deployment. Never cancel
them merely to make an update possible. Use the existing updater and committed
distribution tooling when packaging; do not rerun onboarding.

For one observation while deployment is blocked, run from this source worktree:

```powershell
& <existing-python> -m fpga_mesh.continuity --state-dir <existing-state-dir> --journal <own-evidence-dir>/observation.sqlite
```

This opens execution ledgers read-only and writes only the chosen evidence
journal. It does not install resident hooks, send messages or create chats.
Missing/corrupt sources fail visibly; it does not create missing execution DBs.

## B evidence and current limits, 2026-10-16

Task `B-RUNTIME-CONTINUITY-20261016/v1`; dedicated repair thread
`01a14296-5b5e-7681-b339-d59c4596175b`. The unique product director remains
`01a13b55-095b-7461-8dd5-5476a130bd82`; its acknowledged App proxy remains
`01a1403c-f38c-7a22-84f0-3a8f7103652c`. The latter ended at 00:37 Beijing time,
before three worker reservations at 01:45 and the director ACK at 01:55. At this
inspection the workers were still reserved/unbound. Current B resident PID42680
predates PR28's final protection; root app_server/gateway bytes still differ.
Deployment was rejected before any stop, preserving these existing jobs.

The existing scheduled task uses LogonTrigger/InteractiveToken and IgnoreNew.
The host recorded four sleep/resume cycles. The current process was created
after the two evening cycles and remained present after the two morning cycles;
this supports morning resume recovery, not unattended boot support. No reboot/logoff experiment,
power policy change or update disabling is part of this repair. Keep the
original task/launcher and singleton locks. If genuinely down after login,
verify state and use one start of the existing task, then read actual health;
do not start a parallel supervisor. Pre-login boot recovery remains unverified.

Private evidence is under the B `runtime-continuity-20261016` evidence directory.
An actual native inspection result reached the active repair parent, was read
and recorded as consumed, and produced the exact proxy handoff prompt. This is
an active-turn path; automatic wake of the desktop proxy after its turn ended
is still unverified. Simulation/test-double routing is reported separately.

Preserve DEEPEYE-HUMAN-LOCK-20261014 revision1, H01–H15, pinned contract commit
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`, canonical requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, and design
freeze `1011259415a0916054eb580687612580bc1e5f09`. Only A operates the physical
board. Runtime/source tests do not establish FPGA or product acceptance.

Official API lifecycle reference: [Codex App Server](https://learn.chatgpt.com/docs/app-server).
Thread resume and turn start are distinct operations; a terminal turn event
does not by itself provide an always-running desktop wake mechanism.
