# B operation16: applied-capture runner qualification

At the operation15 runner `83f192c70ab48427e70a0dc66662e4a24a66be90633a454a82e179a6a79ddf98`, A's exact `NOT_TB_PASS_MARKER` fixture and conflicting duplicate `TB_STATS` fixture both incorrectly qualified as PASS. `RED.json` records fresh B reproduction from the original A bytes before changing the runner. A's original two fixtures, result, archive manifest and blob identities are retained under `a-original/`.

The repaired parser requires one complete statistics row followed by one whole-line terminal outcome. Only an absent prefix or ModelSim's exact `# ` prefix is accepted. The outcome must match the requested group and loopback. Duplicate statistics, duplicate outcomes, conflicting counters, malformed records, unexpected stderr records and simulator errors reject qualification. Mutant rejection also requires consistent mismatch records and the TB's own subsequent fatal diagnostic. CODE7 requires its exact observation. Completed process status remains mandatory; a timeout, exception or unexpected exit cannot be promoted by text.

Final source/test hashes and the main decision are in `ACCEPTANCE.json`. `check-02/RESULT.json` binds the final implementation to 23 unit tests, the same 23 tests in a minimal separate directory, rejection of both original A negatives, and reclassification of 33 saved scenarios. These tests invoke no simulator.

Run the portable tests from a checkout:

```text
python -B competition/deepeye/tests/control/test_pwm_applied_capture_runner.py
```

Only this test file and `competition/deepeye/tools/control3d/run_pwm_applied_capture.py` are needed, with their relative directory layout preserved. Tests cover the two reported gaps, identical duplicates, each conflicting statistic, incomplete fields, Unicode/oversized numbers, LF/CRLF framing, unexpected separators, outcome order, run identity, trailing errors, stderr conflicts, mismatch accounting, CODE7, and completed process states. The count is 23 unittest methods with additional table-driven assertions; it is not a count of independent RTL scenarios.

The original 47-command B15 suite is unchanged. Its 94 saved stdout/stderr files were rehashed against the original summary. All 19 positive scenarios (208667 sampled edges), four expected-failure mutant runs, one CODE7 faulty-copy run and nine parameter guards retain their expected classification. This is reuse of saved evidence, not a new ModelSim run or a new independent RTL oracle. The local classification script used for these checks is preserved as `execution/checks16.py`; its recorded machine paths identify the actual original execution environment.

`check-01/` is a successful intermediate parser revision. Main inspection then identified Python's broad `splitlines`/universal-newline behavior as unsuitable for a whole-line protocol; `check-02/` adds explicit LF/CRLF framing and separator negatives. Both revisions and outputs are retained.

The original B qualification failures (13/16), their synthetic fixture bytes, repaired results and tested source snapshots remain under the original operation15 evidence and are copied unchanged under `prior-b/`. Those historical synthetic normal fixtures used bare `TB_PASS` before statistics; this is not the actual current TB format and is now rejected. Canonical-format tests separately verify the original exit/error/fatal rules. No historical result or manifest is rewritten.

A's matched operation12/13/14/15 review comments were actually GET-read. `A_FEEDBACK_CONSUMED.json` records the exact identities. In particular, operation12's author count is **40 verified published artifacts plus 45 unavailable compiler-work entries**, rather than 85 verified published artifacts. Assertion invocations are not independent cases. Operation13's A oracle chronology and reused B stimulus remain disclosed. A's operation14/15 original ownership deviation remains in A's archive; B does not retroactively authorize it.

The scope is Python runner qualification only. RTL, TB, generator12, capture14, all historical evidence, and the protected dirty codec handoff are unchanged. No synthesis, implementation, CDC/RDC, board, system, public ABI, freshness, BOOT or motion authority is established; all29 formal cards remain `not_run`. H01–H15 / `DEEPEYE-HUMAN-LOCK-20261014/revision1` requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, frozen design `1011259415a0916054eb580687612580bc1e5f09`, remain fixed. Physical board work is A-only.
