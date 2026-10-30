# New main-owned build110 call-boundary correction

Task DEEPEYE-IMPLEMENTATION-20261014/v1; actual current main
01a18824-4172-74e2-a13f-f3e3d1e3ed99. Work
B-DEEPEYE-FUNCTIONAL50-BUILDER-CALL-FIX-20261031-110. H01-H15 SHA
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 unchanged.

Main owns only the one call-site change in committed builder98
competition/deepeye/tools/diagnostic/functional50_build98/build_functional50.py
and new private main110 evidence. Original99S and108 actual terminal, no active
worker owns this file. Active host103 worker owns a separate new directory;
its RTL/HWH verifier interfaces remain unchanged and its final pins must use
the newly committed builder revision. No write to failed .local/b103 snapshot.

Actual ONEBUILD103 wrapper exited1 at2026-10-30T17:47:46Z. prepare_inputs copied
and hashed inputs successfully, returned a mapping with inputs/source_root/
tooling_root/launch. build_run passed that mapping to run_vivado, whose first
line performs inputs / 'tooling'. TypeError occurred before load_module could
run, before vivado directory creation and before owned.run_owned invocation.
Raw failure/manifest/outerJob terminal evidence remain unchanged. This is not
a synthesis failure or completed vendor attempt. The one-use wrapper claim
is consumed and cannot be reused; no automatic re-entry/retry is authorized.

Selected correction: pass inputs['inputs'] at the build_run -> run_vivado call.
Keep prepare_inputs API, all helper/security/clock/CDC/timing/parser logic and
sourcepins unchanged. Main independently read both function definitions and
actual persisted LAUNCH_INPUTS/SOURCE_SNAPSHOT_BEFORE/FAILURE. The original
99T114case suite did not cover this end-to-end call boundary; its historical
result stays scoped. Do not rerun the suite or claim this edit was vendor-tested.

Verification for this narrow correction is exact static call/return review,
unchanged remaining bytes and one committed line diff. No synthetic approval
or fake build_run execution, vendor rerun or duplicate4case resource tests.
The next true vendor attempt will validate the corrected boundary after exact
new source/closure/request/manifest/oneuse identity and A recovery scope. Main
will report this concrete failure+fix to A; continue independent A28 host103.
No board/RootBOOT/production/H12/all29/final100MHz/1pct100ms acceptance upgrade.
