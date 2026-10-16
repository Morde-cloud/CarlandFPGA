# B control software candidate review

This checkpoint supplies the 29-offset A inventory crosswalk and a three-channel
capture/snapshot behavior candidate. It assigns no public register bits, reset
values, tick-word layout or CDC timing. A owns public ABI freeze. B05/R03/G05 and
simulation/synthesis/implementation/board/system remain not_run.

The main rejected the initial foundation for STOP/forged derived fields/input
aliases/history mutation, then rejected correction02 for overloaded scalar
subclasses and returned snapshots aliasing internal history. Original evidence
and rejection records are retained. Main correction03 requires exact built-in
scalars and returns detached snapshots. Two tests asserting object identity
were changed to require equal values and independent objects; the initial
two-failure log is preserved. Eighty unit tests pass after three added boundary
regressions. Public API isolation is not an arbitrary in-process security wall.

Independent checks: all 30001 yaw codes at seven jitter values (210007 cases),
147 speed cases,24 STOP/order combinations,300 seeded ingress-alias batches,
7 latch revocations,1000 bounded publications and6 scalar/output checks.

Run from the repository root with Python3.12 standard library:
`python -B -X utf8 competition/deepeye/evidence/control/main-review-20261016/independent_review.py --output-root YOUR_NEW_DIRECTORY --expect fixed`

H01-H15 DEEPEYE-HUMAN-LOCK-20261014/revision1 requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
frozen design1011259415a0916054eb580687612580bc1e5f09 unchanged.
