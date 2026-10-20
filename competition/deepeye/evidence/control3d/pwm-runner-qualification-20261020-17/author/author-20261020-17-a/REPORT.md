# Operation17 test-author report

Status: **completed** for the assigned test-author work only. This is not product,
runner, formal, board, or system acceptance.

- Task: `DEEPEYE-IMPLEMENTATION-20261014/v1`
- Work: `B-PWM-RUNNER-QUALIFICATION-20261020-17-EXEC-v1`
- Parent operation: `B-DEEPEYE-PWM-RUNNER-QUALIFICATION-20261020-17`
- Owner: quality main `01a13b55-095b-7461-8dd5-5476a130bd82`
- Baseline head: `f7736ac737d1c7b256974beb1574b94096819270`
- Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, pin
  `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, design pin
  `1011259415a0916054eb580687612580bc1e5f09`

## Frozen-input verification

- Recomputed H01-H15 with `ensure_ascii=False`, `sort_keys=True`,
  `separators=(",", ":")`, then UTF-8:
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
  It equals the fixed expected value and all 15 IDs are present.
- `DESIGN.md` SHA256 is
  `c0f6c5875c2a76d331f8695312c32ca18e2ad21cb63d1d040ea561aee7fc1242`.
- Original archived test SHA256 is
  `1483b0ca72cf9d66f3c85eac17f3d81f6fccf51eab21deee0e3431b84620ecf8`;
  original runner SHA256 is
  `b4ac06464af965999d35444f607fa6c7db537b80c340d39cbcc233ee2dce37b0`.
- All 23 original test methods are source-identical to the archived test. Seven
  methods were added, for 30 total.
- Embedded A026/A030/A032 bytes exactly equal the supplied input files and their
  fixed hashes. The inputs were not modified.
- Protected codec input remains
  `6db8fca48b2240807ae7df68dc8aa21501eb1b6ab9e89392c5a9272de1a887f8`.

## Added coverage

- Exact one-diagnostic/one-own-fatal guard shape, order, uniqueness, and unknown
  prefix rejection; optional single literal `# ` and LF/CRLF are accepted.
- Exactly six unique ordered fields; canonical signed/nonnegative ASCII decimal
  grammar; non-ASCII digits, signs, leading zeros, extras, omissions, reordering,
  and an overlong value are rejected before unsafe conversion.
- Conflicting/duplicate diagnostics, duplicate/extra/unrelated Fatal and Error
  records, stderr record crossing, guard-token/reserved-token stderr rejection,
  harmless ordinary stderr metadata, and guard-missing rejection.
- Completed integer exit0/exit1 only; timeout, exception, booleans, floats,
  strings, negative values, and other integers are rejected.
- Healthy guard controls, including negative input widths with independently
  derived clamps to count2/witness2/tag1.
- CODE7 absent for ordinary group0; present exactly once before statistics only
  for dedicated group30/loopback0; rejected for other groups, loopback1,
  failures, post-statistics placement, duplication, malformed fields, and
  missing observations.
- Exact A026 ordinary-group CODE7, A030 extra-Fatal, and A032 prefixed guard
  counterexamples are rejected after repair.

The tests use only public runner entry points and synthetic protocol data. They
do not read the controller, old-suite fixtures, RTL, or board state.

## Final run

- Worktree runner SHA256 at execution:
  `0a6101a263fa3c69a8c1737fe965a255ef15aef3ae177fd98e813661a4be8e05`
- Test SHA256:
  `6cd5ba7f9d0b3ee5fdd188b56cbb564092d2a490a4c7d2e8b0bca8a480bb0082`
- The portable tree contained only runner/test at the required relative paths.
- Command: `python.exe -B -m unittest discover -s tests/control -p
  test_pwm_applied_capture_runner.py -v`
- Exit: `0`; `Ran 30 tests`; `OK`; stdout empty; full unittest stderr preserved.
- Evidence: `runs/post-edit-run-02/`. Runner hash was unchanged before snapshot,
  in the snapshot, and after execution.

Control against the archived original runner `b4ac0646...` with the same final
test bytes exited `1` with 45 assertion failures and one error. The error is the
old unchecked conversion of the overlong numeric field; it is expected-failure
evidence, not a failure of the final runner. Evidence:
`runs/original-runner-final-tests/`.

`verification.stdout.json` reports `all_checks_pass=true`; its command, exit,
stdout, and empty stderr are adjacent to it.

## Boundaries

No ModelSim, Vivado, RTL simulation, synthesis, implementation, board, hardware,
network, service, session, commit, push, or peer/group operation was performed.
Tests patch simulator command execution and invoke only Python stdlib checks.
All 29 formal checks plus G05/B06/R03/board/system remain `not_run`; machine A
alone may operate the board. The main may change the runner after this snapshot;
the bound result applies only to the hashes above and requires a fresh run after
any source change. No desktop or human action is required for this author task.
