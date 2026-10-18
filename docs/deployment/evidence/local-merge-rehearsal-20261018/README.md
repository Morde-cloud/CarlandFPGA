# B local merge rehearsal — offline only

Operation `B-LOCAL-MERGE-REHEARSAL-20261018-v1`, task `B-RUNTIME-CONTINUITY-20261016/v1`.

Fresh B copies of `app_server.py`, `controller.py`, `gateway.py` and `runtime.py` were reviewed against the genuine `920ab357ee77f96b8751a593407eb329affc3dcb` base and fixed candidate `abb3ec996e24ca0e91a2063b943f2e736282fdab`. Each exact live-to-candidate patch passed `git apply --check`, was applied only to its live copy in a private stage, and produced the exact candidate bytes. All 125 staged candidate source/test/deployment files were hash-checked again after testing. No original worktree or live runtime source was edited.

The final combination passed 183 related tests with exit 0 (13.055 seconds unittest time; 13.672 seconds process time), without skips. The selection covers immutable runtime cache and integrity deferral, ordinary followup/STOP behavior, gateway no-replay and owner delivery, runtime/continuity lifecycle, and the two retained SDK isolation regressions. This is a new run on the combined stage, not reuse of old pass counts and not full-project discovery. Original asyncio slow-task diagnostic output remains in the raw log.

Import receipts cover the test process and both fresh Python subprocesses: 43 project modules in the test process and four in each child. Every observed `fpga_mesh`/`tests` module resolves inside stage and matches the candidate inventory. The test runner used `-I`, explicitly inserted stage, and set child-process paths to stage plus a small provenance hook. This rules out accidental testing of live-root or repair-worktree source in the observed processes.

B's complete local AGENTS bytes were preserved privately in the snapshot and stage and rechecked against the live file. Neither those bytes nor their private preservation hash is included in these public artifacts or a ZIP. No new ZIP was produced. The original task launcher, task definition, credentials, configuration, SQL and services were not changed.

The unchanged updater still rejects the five live conflicts. A read-only `plan_update` on the genuine historical `3c7ccdc` archive reproduced `AGENTS.md` plus the four runtime files; that archive was neither modified nor represented as a new candidate package. This rehearsal adds no preserve disposition, accepted-preimage whitelist or force path to the installer. The current App/child inventory contains active work and supplies no maintenance clearance.

The four-file patch alone is not a complete installation set. Six additional runtime dependencies differ meaningfully: `child_control.py`, new `continuity.py`, `distribution.py`, `project_control.py`, `sessions.py`, and `update.py`. `dependency-plan.json` records all 50 runtime modules and their observed disposition. Their historical archive preimage eligibility is evidence, not permission to install them now. A fresh, explicit installation ownership plan must also address the already-reviewed task-preservation deploy files, related tests and any other package changes.

`INSTALLATION_NEXT.md` is a proposal for another reviewed work assignment. No maintenance window, live patch execution, service restart, board operation or new source correction was authorized or performed here. Coordinator acceptance of this new rehearsal remains separate from the previous task-preservation acceptance.

H01-H15 remain fixed under `DEEPEYE-HUMAN-LOCK-20261014/revision1`, requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`; contract commit `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, design freeze `1011259415a0916054eb580687612580bc1e5f09`. Only A operates the board.
