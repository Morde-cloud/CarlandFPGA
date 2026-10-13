# Base overlay GPIO check: B handoff

Task `BOARD-20261013-A-B`, version `1`; work
`B-base-overlay-boardtest-v1`; hardware operation
`BOARD-20261013-A:B:base-gpio-v1`; requester `B`.
Only A's current Desktop board owner may execute this check. A peer receipt is
not an instruction to start a background board job or repeat a run.

## Acceptance limitation discovered during development

The original v1 criterion requires three rounds of
`[0, 1, 2, 4, 8, 15, 5, 10, 0]`, with every GPIO write followed by an equal
four-bit register read. The check preserves that strict criterion. It must
report failure when nonzero writes read back as zero.

[AMD PG144, GPIOx_DATA](https://docs.amd.com/r/en-US/pg144-axi-gpio/AXI-GPIO-Data-Register-GPIOx_DATA)
specifies that output-configured bits read as zero. Thus a functioning AXI GPIO
output need not satisfy this criterion. Failure of this comparison alone does
not establish a broken LED or failed write. A must resolve this acceptance
limitation before treating this check as a functional LED acceptance test.

[PYNQ v3.0.1 axigpio.py](https://github.com/Xilinx/PYNQ/blob/v3.0.1/pynq/lib/axigpio.py)
also distinguishes these operations:

| Operation | Meaning |
| --- | --- |
| `channel1.setlength(4)` | Sets the Python channel width. |
| `channel1.setdirection("out")` | Selects the Python output API; does not write TRI. |
| `channel1.write(value, 15)` | Updates the output via the GPIO DATA register. |
| `channel1.read()` in output mode | Raises an exception. |
| Output slice `.read()` | Reads the driver's software cache, not the hardware. |
| `leds_gpio.read(0x0)` | Reads the actual DATA register. |
| `leds_gpio.read(0x4)` | Reads TRI, where implemented. |

The script records actual MMIO reads. It neither uses the output cache as
hardware evidence nor claims an optical observation.

## Scope and environment

A reported PYNQ 3.0.1, Python 3.10.4, armv7l, and interpreter
`/usr/local/share/pynq-venv/bin/python3`. Its existing overlay directory is
`/usr/local/share/pynq-venv/lib/python3.10/site-packages/pynq/overlays/base`.
The required files and A-reported SHA-256 values are:

| File | SHA-256 |
| --- | --- |
| `base.bit` | `ecabdcb5d483c75335ab6f043824a2386971c7b0ffd6e3315f24860bf5088eb6` |
| `base.hwh` | `cbd90c84f3a46d1eba95dff7ba7d0079812f7e46641a08e2318c9928cd36ce8f` |

These hashes are checked before loading. The script uses ordinary
`pynq.Overlay` and the `leds_gpio.channel1` driver, avoiding the audio and PMOD
initialization in `BaseOverlay`. It introduces no RTL, external GPIO wiring,
new clocks, or reset logic. Loading the preinstalled bitstream is FPGA
configuration, not synthesis or implementation performed by this task.

The pre-load overlay identity is recorded separately. Cleanup writes the
first post-load DATA snapshot's low four bits and restores the post-load TRI
snapshot in `finally`, attempting both independently even after a test error.
The DATA snapshot does not reveal the output latch value on AXI GPIO outputs;
matching it after cleanup is not proof of restoration of the previous visible
LED state. The script does not restore the pre-load FPGA configuration.
Process termination that prevents Python cleanup cannot guarantee restoration.

## A's single-run procedure

1. Check out the exact full PR head supplied in the handoff. Verify the
   immutable manifest with the installed handoff tool and review the source.
   Its `request.code_commit` names the source/evidence commit; the later PR
   head also contains the manifest. Confirm source bytes agree between them.
2. Resolve the strict-readback limitation above. A independently handles the
   existing board account's permissions and preserves that evidence; the
   script does not request passwords or invoke `sudo`. B never connects to
   the board. Keep other board jobs stopped during this single operation.
3. Transfer only the reviewed script bytes through A's authorized workflow.
   Select a new output path. An existing output file must cause refusal
   before import, download, or GPIO access. Retain stdout/stderr and the
   actual exit code separately. Run the following with A's already-authorized
   board execution context, replacing all three placeholders with the exact
   values in the PR/manifest:

   ```sh
   /usr/local/share/pynq-venv/bin/python3 base_gpio_board_test.py \
     --bitstream /usr/local/share/pynq-venv/lib/python3.10/site-packages/pynq/overlays/base/base.bit \
     --output base-gpio-v1-result.json \
     --operation-id BOARD-20261013-A:B:base-gpio-v1 \
     --request-hash REQUEST_HASH \
     --code-commit SOURCE_COMMIT \
     --tested-commit PR_HEAD_COMMIT
   ```

4. Inspect every sample, exception and restoration field in the JSON. The
   original strict PASS requires all 27 register comparisons and cleanup
   checks to succeed; any mismatch or exception must produce nonzero exit.
   In particular, an all-zero readback must fail the nonzero patterns.
   No result establishes optical LED function.
5. A posts the operation ID, request hash, actual tested head, actual runtime
   versions, command, exit code, JSON/stdout/stderr paths and SHA-256 values
   on the same PR. Failed or blocked runs require explicit recovery decisions;
   do not automatically repeat them or overwrite the first evidence.

## Host verification and evidence

Run from the checkout root with a local Python interpreter:

```text
python -B -m unittest discover -s tests -p test_base_gpio_board_test.py -v
```

All local fake-device tests are `host_mock` evidence. They cannot establish
PL behavior, synthesis, implementation, or board success. The handoff records
`hardware=not_run` until A supplies evidence for the exact reviewed request.
The manifest is generated only after the source and test evidence are
committed; changing any referenced file requires a new operation/manifest.
