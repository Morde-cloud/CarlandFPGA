# Main register transaction review10

The offline model executes B07 bus commands, atomic CONFIG and revoked snapshot
lifecycles. Main rejected the original worker source despite its70 passing tests:
an input Mapping callback could republish a revoked capture. Main also resolved
context/gate/CDC revocation and latched-only ratio validity. Final70 unit tests,
12 independent bus methods and4 adversarial methods pass, including the four-file
portable export. See MAIN_ACCEPTANCE.json and exact raw logs.

Reproduce from the repository root:

```
python -B -X utf8 -m unittest discover -s competition/deepeye/tests/control -p test_register_transaction.py -v
python -B -X utf8 competition/deepeye/evidence/control/register-transaction-20261019-10/main/main_review.py --source competition/deepeye/golden/control/register_transaction_reference.py
python -B -X utf8 competition/deepeye/evidence/control/register-transaction-20261019-10/main/main_adversarial.py --source competition/deepeye/golden/control/register_transaction_reference.py
```

The original worker source/test/document and worker results are historical and
preserved. Their source hashes do not describe the corrected live module. The
original adversarial negative control has9 failures and1 error. The intermediate
two unit failures were obsolete pre-LATCH ratio-valid assertions; both were changed
to require bit9clear before LATCH and set after LATCH. No failed run is relabeled.
Worker-reported earlier D1 traceback was not retained and is not reconstructed.
Actual child/thread/turn identity is in INTEGRATION.json, overriding the parent
thread copied into worker STARTED. Raw worker logs have byte-identical aliases
listed in worker-raw-map.json; private original logs remain untouched.

A-review/comment.json is the actual matching same-PR feedback6261676586.
A_REVIEW_RECONCILED.json records an earlier failed comment read; the later
authenticated comment supersedes that readback status. A's manifest/findings and
two port logs were verified; both logs are byte-identical to B08/B09 fixed blobs.
This is acknowledgment of A's original-suite replay, not a new A oracle or new B
simulation. No hardware acceptance follows.

Complete public register/TRACE/BOOT/clock authority, diagnostic bank/HWH, physical
CDC/RDC, synthesis/timing, acquisition and both live control chains remain open.
Fixture domains, supplied quality/ratio flags and counters are not measured truth.
All29 product cards stay not_run. A alone operates the board. H01-H15 requirements
SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
