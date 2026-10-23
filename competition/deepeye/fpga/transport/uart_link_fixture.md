# Digital UART link fixture

Work `B-UART-LINK-FIXTURE-20261024-34-v1`, task
`DEEPEYE-IMPLEMENTATION-20261014/v1`, operation
`B-DEEPEYE-UART-LINK-FIXTURE-20261024-34`.

This is a **test-only** ModelSim composition fixture. It joins the frozen
`deepeye_wire_uart_tx` and `deepeye_uart_wire_rx` compositions at their public
digital pins through a testbench-only fault mux. It adds no product RTL,
semantic ABI, packet authorization, transport policy, slot grant, BOOT/source
selection, motion authority, CDC proof, oscillator or baud-tolerance claim, or
physical-board result.

## Contract and immutable source

- Human contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01-H15.
- Canonical `requirements` SHA256:
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
- Frozen design input: `1011259415a0916054eb580687612580bc1e5f09`.
- Exact source snapshot: `bbfb11439b35e0866a6d2486f3857b92ed6cf529`.
- Published PR30 head: `04e3a46eb1169afca0c133815a9b9f3da15d89f5`.
- Scope:
  `.local/deployment/node-b/evidence/uart-link-fixture-20261024-34/SCOPE.md`.

The runner reads all eight RTL modules from the exact Git commit, verifies the
fixed SHA256 of each, and compiles those snapshots. It also verifies that the
eight worktree copies remain unchanged. No frozen RTL is edited.

| Read-only module | SHA256 |
| --- | --- |
| `deepeye_wire_uart_tx.sv` | `4998acb76fed7e53405816c91203bc93df622f05b621da342e1cc8178f51133d` |
| `deepeye_uart_wire_rx.sv` | `b6abab4e1be54ee61bd45e4d7adfcfea8db39f7574d3ce2ae7b7030ff74ade2c` |
| `deepeye_wire_serializer.sv` | `efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885` |
| `deepeye_wire_parser.sv` | `7806c5d08785b96eae3708d9fd6d6002ef82faa4416a1f7244da73bece552649` |
| `deepeye_uart_tx.sv` | `5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47` |
| `deepeye_uart_rx.sv` | `935f5d02008535fd5da75b7dc80696d14b03bd54d85f8b52fbf12c1e0504f08f` |
| `deepeye_uart_frame_tx.sv` | `83261e4c5a317500e224f5cd0e9ce538f067be24d3957dd98c7116425e706be3` |
| `deepeye_crc16_byte.sv` | `8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f` |

## Frozen vector construction

The Python runner builds opaque frame bytes with standard-library `struct` and
`binascii` from the frozen wire layout:

```text
A5 5A 03 type len epoch seq_lo seq_hi
tick_lo tick_8 tick_16 tick_hi payload... crc_lo crc_hi
```

CRC is CRC16/CCITT-FALSE, seed `FFFF`, polynomial `1021`, no reflection and no
xorout, over byte `03` through the final payload byte. The runner independently
cross-checks `binascii.crc_hqx` with a direct bitwise recurrence. TX output is
never used as the expected receive payload.

The primary suite has lengths 0..32 and a deterministic payload stream whose
first 256 payload positions are a permutation of all 256 byte values. Metadata
includes all-zero, all-one and mixed little-endian fields. Every case adds
legal TX config/payload bubbles and an RX output-ready hold before the
descriptor handshake.

## Schedules and cases

All clocks are generated with integer-picosecond half periods and
`timescale 1ps/1ps`. These are finite point schedules, not a measured or
tolerated frequency range.

| Suite | TX schedule | RX schedule | Bounded content |
| --- | --- | --- | --- |
| `default` | 100 MHz point clock, parameters 100000000/9600, PRE=0, POST=0 | 100 MHz point clock, 100000000/9600, phase 2500 ps | two frames total |
| `primary_lengths` | period 10000 ps, parameters 64/4, PRE=2, POST=3 | period 10000 ps, parameters 64/4, phase 2500 ps | lengths 0..32, all byte values, immediate next reservation |
| `rx_early_9900` | period 10000 ps, parameters 64/4, PRE=2, POST=3 | period 9900 ps, parameters 64/4, phase 2500 ps | four valid frames |
| `rx_late_10100` | period 10000 ps, parameters 64/4, PRE=2, POST=3 | period 10100 ps, parameters 64/4, phase 2500 ps | four valid frames |
| `directed_faults` | period 10000 ps, parameters 64/4, PRE=2, POST=3 | period 10000 ps, parameters 64/4, phase 2500 ps | injected faults and recovery |

Directed coverage is:

- one selected payload serial-bit inversion, which must fail CRC;
- one malformed low stop bit, which must raise a framing line error and discard;
- mid-frame TX cancel followed by caller-explicit RX cancel recovery;
- RX cancel during header, payload, and a pending output descriptor;
- output hold long enough for an actual UART overrun, discarding the pending
  candidate;
- a valid candidate retired before a later injected error, proving the earlier
  handshake is not retroactively revoked; and
- a fresh valid frame after every fault.

## Evidence and strictness

`competition/deepeye/tools/transport/run_uart_link_fixture.py` creates a fresh
immutable attempt below the author evidence directory. It records Git source
snapshots and hashes, exact vector bytes, raw commands, stdout/stderr, actual
exit codes, durations, timeouts, ModelSim version, event logs, and a summary.
Failed attempts are retained.

The event log is row-capped and fails closed. It records integer-picosecond TX
line and DE changes, TX config/payload handshakes, RX input-mux edges, RX output
valid/ready/data changes, descriptor handshakes, line/parser errors, public
counter transitions, resets, cancels, and exact clock profiles. The runner
reconstructs every complete TX byte transition from the expected vectors and
the frozen bit-boundary arithmetic, and compares every RX descriptor with the
Python-built input frame. It also exercises negative controls that mutate the
expected wire, output descriptor, and case stream; each mutation must be
rejected by the corresponding validator.

Only actual ModelSim execution is used. The runner does not invoke Vivado,
installers, services, the board, credentials, or peer/group channels.

## Limits

This fixture is author evidence, not independent acceptance. It does not claim
All29, B04, R03, full product, synthesis, implementation, timing closure, CDC,
physical UART, electrical, oscillator tolerance, semantic protocol acceptance,
control authority, or system behavior. Main owns independent fixture review and
acceptance; A alone operates the physical board. Full B04 still requires C's
independent endpoint/scheduling work and A's real I/O and remains `not_run`.
