# Existing-task preservation: offline review scope

Operation `B-PRESERVE-EXISTING-TASK-20261018-v1`, task `B-RUNTIME-CONTINUITY-20261016/v1`.

The old updater could replace an existing node's custom launcher, triggers and settings through `register-autostart.ps1`. The new updater requires the existing root task, validates its current Windows user principal and exact node action paths, saves its full exported XML and launcher bytes, and compares them before stop, before source application, before start and immediately after start. A missing task, mismatch or observed change fails closed. The snapshot is evidence, never an instruction to restore old task state.

Both the installed supervisor module action and the node-specific `.local/deployment/node-<node>/launch-node-<node>.py` action are accepted. Unknown actions, extra flags, duplicate flags, multiple actions and mismatched Python/config/ready/log/workspace paths require separate review. All task principal, action, trigger, setting and description details remain in the original XML. XML string hashes explicitly use UTF-8 without BOM; saved XML uses the declaration's encoding. The launcher hash covers its original bytes.

The unchanged stop helper selects tasks by name. The new guard therefore checks that name across task folders and refuses any duplicate, even when the root task matches; it cannot silently stop another same-name task in a different folder.

The original `--stop-idle` call and its three-ledger admission fence are unchanged. A busy or locked ledger prevents the stop callback. Source-apply failure prevents startup. Startup is attempted once; neither a command error nor a later health error causes retry, re-registration or source replay. A phase/result receipt is left beside the snapshot for reconciliation.

Routing is parsed with Python's TOML parser and only validated: the existing bridge must use the same Python, project root and control file, the expected module arguments and timeouts, and must not be disabled. This updater no longer calls `install_routing`, `register-autostart` or `models_refresh`. It does not modify routing or role files. The existing read-only file-scope audit remains; it grants no cloud scope.

PowerShell fixtures execute copies of the actual updater/helper with synthetic workspace files and stubbed task cmdlets. They cannot demonstrate a real service deployment, actual process lineage, live Feishu recovery or board behavior. Separate focused tests exercise the unchanged real ledger guard against synthetic SQLite databases, with a mocked stop callback. Execution results and exact source identifiers are in the accompanying validation record.

The five changed source/fixture files match their tested and committed bytes exactly. The unchanged admission files were executed from the Windows checkout; validation records both checkout and Git hashes and verifies only CRLF/LF differences. The handoff manifest hashes raw Git artifact bytes. On Windows, verify it from a raw Git export rather than assuming an automatic-CRLF checkout has identical bytes.

Task Scheduler offers no compare-and-start transaction here. Comparisons detect changes at the recorded boundaries; operators must also prevent concurrent task/launcher edits and reconcile actual App writers during a maintenance window. The three ledger locks cover admission through confirmed stop, not arbitrary desktop or administrator edits. This change adds no new permission to deploy.

Five live-source conflicts remain unresolved: `AGENTS.md`, `fpga_mesh/app_server.py`, `fpga_mesh/controller.py`, `fpga_mesh/gateway.py`, and `fpga_mesh/runtime.py`. The live source, custom launcher, service, scheduled task, SQL, credentials, settings and product ownership were not modified in this offline work. The old candidate archive is historical and does not contain this new increment; no updated deployment archive is claimed.

H01-H15 remain fixed under `DEEPEYE-HUMAN-LOCK-20261014/revision1`, requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, contract commit `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, design freeze `1011259415a0916054eb580687612580bc1e5f09`. Only A operates the physical board. This is not product or deployment acceptance.
