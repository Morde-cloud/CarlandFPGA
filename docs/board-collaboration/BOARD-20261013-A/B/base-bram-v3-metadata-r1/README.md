# Base overlay AXI BRAM test: B handoff v3 (metadata compatibility)

Task `BOARD-20261013-A-B`, version `3`; work `B-metadata-compat-v3`;
operation `BOARD-20261013-A:B:base-bram-v3-metadata-r1`. Handed off on the
same PR #9 (carolwjade/CarlandFPGA); supersedes v2 reset-origin-r1 for any
further execution. v2's operation, manifest and recorded board result stay
historical and intact; never rerun or replay them.

## Root cause: PYNQ 3.0.1 mem_dict-only lookup

A's recorded v2 board run exited 1 with metadata
`KeyError('iop_pmoda/mb_bram_ctrl')` and zero samples; reset/MMIO were never
reached. PYNQ 3.0.1's embedded `RuntimeMetadataParser` drops from `ip_dict`
every key also present in `mem_dict`, and `MemDictView` labels such PS memory
entries with the synthetic type `DDR4` (XRT memtype label, not the AXI core
VLNV), keeping `fullpath`, `phys_addr` and `addr_range`; XRT merging may add
`base_address` and `size`.
The pinned `base.hwh` maps `iop_pmoda/mb_bram_ctrl` as `MEMORY`, so the fix must not assume an `ip_dict`-only lookup will resolve it.

## Fix: HWH-anchored metadata cross-validation

The v3 script parses the fixed-hash `base.hwh` and requires exactly one
MODULE `FULLNAME`/VLNV match for the target path (AXI BRAM controller) plus
the PS `MEMRANGE` base/range. It then requires the runtime `ip_dict`/
`mem_dict` entry for that fullpath. At least one complete address pair
(`phys_addr`/`addr_range` or `base_address`/`size`) is required; all present
pairs must equal the HWH facts. Missing pairs, partial pairs and conflicting
fields are rejected; addresses are never defaulted or guessed. A wrong or
incomplete HWH fails before Overlay loading. Runtime metadata is validated
before reset or BRAM MMIO access. `MMIO` uses observed validated addresses.

## Test and restoration contract (unchanged)

Only 16 aligned 32-bit words at `0xFC00`-`0xFC3C` (physical `0x4000FC00`-`0x4000FC3C`)
are tested; eight batches x three rounds = 384 MMIO comparisons, then 16 restore comparisons:

| Batch | Word `i`, `i=0..15` |
| --- | --- |
| Zero | `0x00000000` |
| Ones | `0xFFFFFFFF` |
| Alternating 55 | `0x55555555` |
| Alternating AA | `0xAAAAAAAA` |
| Index tagged | `0xA5A50000 \| i` |
| Index inverted | `(~(0xA5A50000 \| i)) & 0xFFFFFFFF` |
| Walking one | `1 << i` |
| Deterministic random | one `Random(0x20261013)` instance, 16 `getrandbits(32)` calls generated once, reused identically in all three rounds |

Reset resolves dynamically via the `gpio_dict` key `mb_iop_pmoda_reset` plus
`pynq.GPIO.get_gpio_pin` (no hardcoded line); its sysfs direction/value
snapshot is observed after this run exports the line when not already
exported (`post_load_post_export_sysfs_observation`,
`pre_export_output_latch_known=false`). Reset stays high across snapshots,
writes, reads and restoration; `finally` restores and MMIO-verifies all 16
words before restoring the observed reset/export state. On failed
verification reset stays high and the withheld restoration is reported; the
pre-load FPGA configuration and original overlay are not restored.

## Environment, identity and single run

Runtime environment, pinned `base.bit`/`base.hwh` SHA-256 checks, root
context (`sudo bash -lc`), cwd `/tmp`, venv Python3
`/usr/local/share/pynq-venv/bin/python3` and the single-run procedure are
unchanged from `../README.md` (Environment and input identity section), except the
new operation ID and fresh output path `base-bram-v3-metadata-r1-result.json`
(an existing path is refused before hardware access). A/root is the sole
physical operator; keep concurrent users of this overlay/BRAM stopped.

This directory is the v3 handoff. `input.json`/`manifest.json` are built
from the final source commit. Source commit and tested PR head differ because
the manifest is committed afterward. Read exact values from the final PR and
manifest; transfer raw Git blob bytes, since Windows checkout can change LF
to CRLF and invalidate script hashes. Verify the bytes again on A.

```sh
cd /tmp
/usr/local/share/pynq-venv/bin/python3 base_bram_board_test.py \
  --bitstream /usr/local/share/pynq-venv/lib/python3.10/site-packages/pynq/overlays/base/base.bit \
  --output base-bram-v3-metadata-r1-result.json \
  --operation-id BOARD-20261013-A:B:base-bram-v3-metadata-r1 \
  --request-hash REQUEST_HASH --code-commit SOURCE_COMMIT --tested-commit TESTED_HEAD
```

## PASS, evidence and limits

PASS requires exit 0, validated metadata before reset/MMIO, exactly 384
matching MMIO samples, 16 verified restorations, restored observed
reset/export state and no errors; anything else is not PASS. Preserve the
result JSON, stdout/stderr, exit code and SHA-256 evidence against this
operation, request hash and tested head; never overwrite or auto-rerun.
`red-stderr.txt` records the old head failing the memory-only regression
with metadata KeyError and zero reset/MMIO/BRAM access; `red-test.patch`
reconstructs that test from the old head. `green-stderr.txt` records the earlier
27-test checkpoint using a synthetic HWH and the upstream schema model.

A subsequently exported the actual PYNQ 3.0.1 schema and complete HWH in
PR #7 commit `b395767272909229dd3acb289bd71a82ab8c4211`, directory
`docs/board-collaboration/BOARD-20261013-A/A/metadata-v3-readonly-preflight/`.
`A-metadata.json` and `A-hwh-target-details.json` here are byte-identical Git
blobs from that commit. `A-evidence-binding.json` records every source blob
hash and the successful full-HWH identity parse (`/ps7_0`, underscore INSTANCE
linkage). The older `A-existing-hwh-evidence.json` is a historical receipt;
its pending state is superseded by this actual export.

`red-actual-r1-stderr.txt` reproduces the old source's metadata KeyError with
one mocked Overlay load, zero MMIO/reset calls and zero samples, using that
actual schema and all 4,558,197 HWH bytes. `green-actual-r1-stderr.txt` passes
the identical replay with v3. `green-final-stderr.txt` records all **28 tests
passing**, including the actual memory-only schema regression and rejection
of missing/conflicting mappings, wrong ranges, wrong HWH and reset metadata.
The actual-schema replay checks 384 matching samples, 16 restored words,
restored reset and 416 reads/400 writes in the mock backend. A's JSON probe
used `default=str` for the GPIO pins set; only the fixture is reconstructed
with `ast.literal_eval`. Runtime board code still receives its native set.

Reproduce from the repository root (Python 3.10 or later):

```sh
git fetch upstream b395767272909229dd3acb289bd71a82ab8c4211
python docs/board-collaboration/BOARD-20261013-A/B/base-bram-v3-metadata-r1/replay-actual-schema.py --source-commit bb0d302331785defb59fc8d47eeea5d27fb33e81
python docs/board-collaboration/BOARD-20261013-A/B/base-bram-v3-metadata-r1/replay-actual-schema.py
python -m unittest discover -s tests -p test_base_bram_board_test.py -v
```

The old-source command must exit 1; the next two must exit 0. Command and hash
records are in `actual-schema-replay-r1.json` and
`actual-schema-verification.json`. The first replay-harness attempt lacked
`__file__` and failed early; its raw logs are retained but are not the accepted
metadata regression. The corrected r1 replay supplies an exact temporary
old-source file. Production code did not change during this correction.
Python 3.10 syntax passed on host Python 3.12.9. Host evidence is not a board test.
Hardware, simulation,
synthesis and implementation stay `not_run` until A reports against this
exact operation/hash/head. JSON uses LF; subprocess logs retain their original
captured bytes, including host line endings. Git text conversion is disabled
for this directory (`* -text`).
