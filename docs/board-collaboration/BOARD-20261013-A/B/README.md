# Base overlay AXI BRAM test: B handoff v2

Task `BOARD-20261013-A-B`, version `2`; work
`B-base-overlay-bramtest-v2`; hardware operation
`BOARD-20261013-A:B:base-bram-v2-reset-origin-r1`; requester `B`.

This revision clarifies reset observation provenance. The earlier
`base-bram-v2` operation and manifest are retained at PR head
`748ede5c0844c5c8a1dc4d251ff29de52c9bb07f` as history. Use the new
`base-bram-v2-reset-origin-r1/manifest.json` and its accompanying PR head.

This is the sole current test. A explicitly replaced GPIO readback acceptance
with AXI BRAM testing. `v1-superseded.json`, `v1-gpio-design.md` and
`api-reference.txt` preserve the earlier investigation; their GPIO procedure
is superseded and must not be executed for this handoff. The old local GPIO
source/test drafts are preserved locally but are not v2 test artifacts.

## Test and restoration contract

The script loads the existing `base.bit` once using ordinary `pynq.Overlay`.
It resolves `iop_pmoda/mb_bram_ctrl` from `overlay.ip_dict`, validates its AXI
BRAM VLNV, physical base `0x40000000` and 64 KiB range, and constructs `MMIO`
from the observed metadata. A mismatch aborts; there is no guessed-address
fallback. Only 16 aligned 32-bit words at offsets `0xFC00` through `0xFC3C`
are tested, corresponding to physical addresses `0x4000FC00`–`0x4000FC3C`.

The reset index comes from
`overlay.gpio_dict["mb_iop_pmoda_reset"]["index"]`, then
`pynq.GPIO.get_gpio_pin(index)` resolves the Linux GPIO number. The script
validates A's confirmed metadata index `0`, captures reset direction/value
through that GPIO's sysfs files, asserts reset
high, and verifies it before accessing BRAM. It avoids `GPIO(..., "out")`
initialization and `.read()` because the PYNQ constructor changes direction
and the output API forbids reads. If the GPIO was not exported, only that
resolved line is exported and its export state is restored afterward.

A's read-only check mapped index `0` to Linux GPIO `960` and found it not
exported. The script still resolves the pin through the library at runtime;
`960` is not a guessed address. In that case `initial_reset` records the value
and direction observed **after this run exports the GPIO**, identified by
`observation_point=post_load_post_export_sysfs_observation`. It explicitly
sets `pre_export_output_latch_known=false`: the previously unexported output
latch value was not visible. Cleanup restores this observed value/direction,
then unexports the line. For an already exported line, the observation point
is `post_load_existing_export_sysfs_observation`. The `exported` field records
whether the line was exported before snapshot preparation.

With MicroBlaze held in reset, all 16 original words are read before any test
write. Each batch writes all 16 words, then reads all 16 through MMIO. These
eight batches repeat three times, yielding **384 comparisons**:

| Batch | Word `i`, for `i=0..15` |
| --- | --- |
| Zero | `0x00000000` |
| Ones | `0xFFFFFFFF` |
| Alternating 55 | `0x55555555` |
| Alternating AA | `0xAAAAAAAA` |
| Index tagged | `0xA5A50000 \| i` |
| Index inverted | `(~(0xA5A50000 \| i)) & 0xFFFFFFFF` |
| Walking one | `1 << i` |
| Deterministic random | 16 consecutive `getrandbits(32)` calls on one `Random(0x20261013)` instance; the same vector in each round |

Each sample records its expected and observed values, round, batch, word
index, offset and physical source. Software caches are not measurements.
Reset remains asserted during all snapshots, writes, reads and BRAM cleanup.
`finally` attempts restoration of every captured word and checks all 16 by
MMIO before restoring the initial reset state. If BRAM restoration cannot be
verified, reset stays asserted and the report explicitly records the withheld
reset restoration and failure for A's recovery decision. If reset cannot be held high,
BRAM restoration is not attempted concurrently with a running MicroBlaze;
the report records the failure. Errors, mismatches, interruption, and cleanup
failures cause nonzero exit. Forced termination or power loss can prevent
Python cleanup; inspect the actual restoration report rather than assuming it
succeeded. The pre-load FPGA configuration is not restored.

## Environment and input identity

A reported PYNQ 3.0.1, Python 3.10.4, armv7l, and interpreter
`/usr/local/share/pynq-venv/bin/python3`. A has verified its authorized root
execution context through a login shell (`sudo bash -lc`), with
`BOARD=Pynq-Z2` and `XILINX_XRT=/usr`. Run from `/tmp` to avoid importing
`/home/xilinx/pynq` instead of the installed venv package. A handles the root
shell; the script does not process credentials. The existing overlay directory is
`/usr/local/share/pynq-venv/lib/python3.10/site-packages/pynq/overlays/base`.

| File | Required SHA-256, reported by A |
| --- | --- |
| `base.bit` | `ecabdcb5d483c75335ab6f043824a2386971c7b0ffd6e3315f24860bf5088eb6` |
| `base.hwh` | `cbd90c84f3a46d1eba95dff7ba7d0079812f7e46641a08e2318c9928cd36ce8f` |

The script checks both files before importing PYNQ/loading the overlay and
records their actual hashes, runtime versions, script hash, and PL identity
before/after loading. A observed null pre-load PL identity; that is recorded
as `unknown`, even though the FPGA manager was operating. There is no new RTL, external wiring, new clock/reset
design, synthesis or implementation in this task. BRAM restoration refers to
the snapshot taken after overlay loading. B performs host mock testing only.

## A's single-run procedure

1. Check out the exact full PR head in the handoff. Verify the immutable
   manifest using `handoff.py verify --root . --manifest <manifest-path>` from
   the installed skill. Confirm the tested script matches its manifest hash
   and the source commit. The later PR head also includes the manifest.
2. A's current Desktop board owner transfers the reviewed script through the
   authorized board workflow. Keep concurrent users of this overlay/BRAM
   stopped. Neither a peer receipt nor this document dispatches an additional
   background hardware job. B never operates the board.
3. Use A's already-authorized execution context and the exact values in the
   manifest/PR. Select a fresh output path and retain stdout, stderr and exit
   code separately. An existing output path is refused before hardware access.

   ```sh
   cd /tmp
   /usr/local/share/pynq-venv/bin/python3 base_bram_board_test.py \
     --bitstream /usr/local/share/pynq-venv/lib/python3.10/site-packages/pynq/overlays/base/base.bit \
     --output base-bram-v2-reset-origin-r1-result.json \
     --operation-id BOARD-20261013-A:B:base-bram-v2-reset-origin-r1 \
     --request-hash REQUEST_HASH \
     --code-commit SOURCE_COMMIT \
     --tested-commit PR_HEAD_COMMIT
   ```

4. PASS requires exit 0, exactly 384 matching MMIO samples, successful
   restoration/readback of all 16 words, restored initial reset state, and no
   errors. Any missing evidence is not PASS. This test establishes neither LED
   optical behavior nor a newly synthesized design.
5. A posts operation ID, request hash, actual tested head, command, exit code,
   runtime versions, JSON/stdout/stderr paths and SHA-256 values on the same
   PR. Failures require an explicit recovery decision; do not overwrite the
   initial output or automatically repeat a board operation.

## Local verification

```text
python -B -m unittest discover -s tests -p test_base_bram_board_test.py -v
```

The current revision passed 22 host tests. `host-tests-reset-origin-r1.txt`
preserves the raw output; `host-verification-reset-origin-r1.json` records the
actual command, runtime and tested source hashes. The test process configured
LF output before execution, and this directory's `.gitattributes` disables
Git text conversion. Earlier logs and manifests retain their original bytes.
Local success means mock software behavior only. The handoff records host mock,
simulation, synthesis, implementation and hardware as separate stages, with
`hardware=not_run` until A provides evidence for this precise request/head.
The manifest is generated after committing source and evidence; modifying
referenced files requires a new operation and manifest.

API references: [PYNQ 3.0.1 GPIO implementation](https://github.com/Xilinx/PYNQ/blob/v3.0.1/pynq/gpio.py),
[PYNQ 3.0.1 MMIO implementation](https://github.com/Xilinx/PYNQ/blob/v3.0.1/pynq/mmio.py),
[Linux GPIO sysfs direction/value semantics](https://docs.kernel.org/userspace-api/gpio/sysfs.html).
