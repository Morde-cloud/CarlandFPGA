# B07 offline register transaction worker result

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`.
Work `B-REGISTER-TRANSACTION-20261019-10-v1`.
Operation `B-DEEPEYE-REGISTER-TRANSACTION-20261019-10`.
Status: bounded offline implementation complete; independent acceptance is
owned by the main.

## Verified inputs

All pinned inputs match `STARTED.json` and the requirements-only canonical
hash.  H01-H15 are present in order.

* Requirements canonical SHA256:
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`
* Lock commit `f5989cd5defce561f9ba98e6b18fc2682945f0a2`
* Design commit `1011259415a0916054eb580687612580bc1e5f09`
* Base commit `433db2a82854a669778eb8c3cd35c309623a087e`
* B07 owner-decision input
  `5cb049b28da33eea74e8a30365962d731b3f2d198065086daab1998ff747e116`
* B07 descriptor `73e288e65cb4116292cc81f8e623321b83836de6659d8607296b6ac70c815466`
* B07 document `097b00653d06c87925f0b7fe9f0431ceb2d8fd4d4fa4845876b52bd69afe3eac`
* B07 examples `25ea5ad889f3ea6b3b8a521aa4b45f4a337589209633615126aa53a3bd9394af`

`pin_verification.json` contains the full comparison.  Commit IDs are
recorded deployment pins; no Git command was executed by this worker.

## Artifacts

| Artifact | SHA256 | Bytes | Lines |
| --- | --- | --- | --- |
| `register_transaction_reference.py` | `b5e4ee6cdbde370a5b837b6f16b7c4d9962f4a0899092f4d267609baa887ac1a` | 46823 | 1180 |
| `test_register_transaction.py` | `39eb1832fb5171ee9f58af37e46d4903ac3b49b7834e25f798cb06894f2023b1` | 50085 | 1191 |
| `REGISTER_TRANSACTION_REFERENCE.md` | `2131534dc1e8d4d0fdf06c5f92c4ab1d47feebb94caa9632ba12efbfe11f5c80` | 22565 | 382 |
| `STARTED.json` | `2ac05e1d24e95922d939d6de5513d5ea74f3dc2dd3b9558b7aeb8d608bf5be6c` | 3399 | 66 |
| `run_offline_tests.py` | `c41621593448572c94e56e8dc82c288674de48bd5e4aa8635468b071c69deb43` | 2213 | 78 |
| `collect_evidence.py` | `f791b413ac99f32f0434297677d4a41585e985e73cb6aaa7c9cd1f7a2f2c1eb2` | 6456 | 201 |

`artifact_hashes.json` also records the raw log hashes and sizes.
`final_manifest.json` records every source, result and raw-log hash; it
explicitly excludes itself from self-hashing.

## Test result

Command, run from the worktree root with the required interpreter:

```
D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 -m unittest discover -s competition/deepeye/tests/control -p test_register_transaction.py -v
```

Result: `Ran 70 tests`, `OK`, return code `0`, no failures or errors.
`stdout.bin` is empty (`0` bytes); `unittest -v` reports on stderr
(`9826` bytes, SHA256
`0392cbc85fa390e7c8b52e16daca8c4e74bccfa7c6f29673bd51fde704e494a6`).
Both streams were captured as raw bytes by `run_offline_tests.py`; the exact
command and Python version are in `logs/run_metadata.json`.

The suite covers constructor/authority invariants, domain and context
validation, anti-reuse, all bus/access classes, STOP priority, shadow
atomicity, CONFIG apply/duplicate/conflict/boundary/epoch behavior, queue
saturation, capture tickets and value validation, wire/tick high-water marks,
exact bank encoding from the bound context, LATCH/RELEASE, all specified
coherence revocations, interleaved-read rejection, detached results, reset and
replay prevention.

## Defects and audit notes

* `D1` fixed earlier in the task: a latch state attribute shadowed the latch
  method and produced `TypeError: 'NoneType' object is not callable`; the
  method is now `_latch_snapshot`.  The original traceback was not persisted
  in `worker/`; the current suite exercises LATCH, RELEASE and conflict paths.
* `D2` fixed during evidence capture: the collector's status regex assumed
  LF-only output and misclassified a passing CRLF unittest run as `FAILED`.
  The collector was corrected and rerun; it exits `0` with status `OK`.
* The flagged `complete_capture`/coherent-latch concern was audited.  There is
  no public path to complete a capture without a preceding `begin_capture`,
  and `begin_capture` revokes the latch and clears tickets before issuing its
  ticket.  No source change was needed; the lifecycle test covers it.
* Historical latch `ratio_valid` is not observable after revocation because
  the latch object is dropped; `gain_ratio_valid` and status bit 9 clear and
  the bank bytes remain historical/invalid.  No source change was needed.

## Unresolved semantics

The reference document lists these as fixture choices or A-owned questions.
They are not additional freezes.

* Active CONFIG and stopped/enabled state retention across `set_context`
  changes.
* Capture while stopped or fault-latched; only ENABLE is fault-gated.
* Proactive discard of a generation-bound pending CONFIG by `begin_capture`.
* RELEASE invalidating an unlatched publication and pending CONFIG through
  generation advance.
* Ticket consumption by the first completion attempt, including failure.
* Conservative retention of capture high-water marks across `reset`.
* Bit 2 remaining set after coherence revocation until RELEASE/reset.
* Full ABI identity, CONFIG encoding, queue binding, clock units/origin,
  period widths, diagnostic bank, AXI response codes, calibration,
  time-provenance and ACL/runtime proof remain A-owned.
* Reset resume exception for the last active pair with retained high-water
  marks; other used pairs remain barred.

## Scope and prohibitions

This result is offline software evidence only.  No RTL, MMIO, AXI, CDC/RDC,
driver, public-ABI, board, calibration, runtime or product acceptance is
claimed.  `hardware_enable_eligible` and `movement_authorized` remain `False`.
No service, configuration, credential, queue, board, network, Git, message,
delegation or native-chat operation was used.  The pre-existing
`handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json` change was not touched.
There are no blockers; the main owns independent acceptance.
