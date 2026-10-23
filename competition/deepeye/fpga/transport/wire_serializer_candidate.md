# `deepeye_wire_serializer` author candidate

Work `B-WIRE-SERIALIZER-20261024-28-v1`, operation
`B-DEEPEYE-WIRE-SERIALIZER-20261024-28`, under task
`DEEPEYE-IMPLEMENTATION-20261014/v1`.

This is an author implementation candidate. Main owns independent fixtures,
acceptance, integration, and publication. The fixed human contract is
`DEEPEYE-HUMAN-LOCK-20261014/revision1` (H01-H15), requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`;
the frozen design input is `1011259415a0916054eb580687612580bc1e5f09`.

## Interface

`deepeye_wire_serializer` has `STAT_W` default 32 and legal range 2..32.
An illegal value uses a safe internal width clamp only so elaboration can
reach the time-zero fatal message
`deepeye_wire_serializer: STAT_W out of range`.

The module exposes:

- Clock/reset/cancel: `clk`, `rst`, `cancel`.
- Opaque config: `cfg_valid`, `cfg_ready`, `cfg_type[7:0]`,
  `cfg_epoch[7:0]`, `cfg_seq[15:0]`, `cfg_tick[31:0]`, `cfg_len[5:0]`.
- Payload: `p_valid`, `p_ready`, `p_data[7:0]`, `p_last`.
- Serial output: `out_valid`, `out_ready`, `out_data[7:0]`, `out_last`,
  `out_count[5:0]`.
- Status: `busy`, `receiving`, `faulted`, `fault_event`, `fault_code[1:0]`,
  and four `STAT_W`-wide saturating counters.

There is no output-config handshake, public ABI freeze, type interpretation,
profile acceptance, freshness decision, packet authorization, or motion
grant. `out_valid` is only an internal byte-stream indication.

## Accepted frame

One accepted frame is serialized as:

```
A5 5A 03 type len epoch seq_lo seq_hi
tick_lo tick_8 tick_16 tick_hi payload... crc_lo crc_hi
```

The payload length is 0..32. The total byte count is `len + 14`, which fits
in `out_count[5:0]` without a seventh-bit wrap. For a legal length,
`out_count` remains the total while the frame is busy until retirement.
Idle and illegal-length fault states expose zero.

CRC16/CCITT-FALSE is seeded with `0xFFFF` at frame start, uses polynomial
`0x1021`, no reflection and no xorout, and covers byte `03` through the final
payload byte inclusive. Magic bytes and the two CRC bytes are excluded. The
CRC state is updated only when a covered output byte is accepted. The CRC
primitive is instantiated exactly once and is unchanged.

## Lifecycle

- `cfg_ready` is high only while idle, and is gated by `rst` and `cancel`.
- A config is accepted only while idle. All metadata is captured and a legal
  length reserves the single 32-byte payload buffer.
- `len=0` seals immediately and makes output available after the acceptance
  edge. `len=1..32` enters payload collection. `len=33..63` enters fault code
  1, asserts `busy`, emits one `fault_event` pulse, and exposes no output.
- For every payload handshake, `p_last` must equal
  `payload_index == len-1`. A mismatch enters fault code 2, emits one event,
  retains the legal-length total in `out_count`, and exposes no output.
- Fault state is sticky while busy. It is cleared only by synchronous reset
  or cancel. A legal frame produces no fault event.
- `fault_event` directly exposes the registered pulse. Once asserted after a
  fault-detection rising edge, it remains visible through a later
  falling-edge assertion of reset or cancel and is cleared only by the next
  rising edge. Handshake gating remains separate and combinational:
  `cfg_ready`, `p_ready`, and `out_valid` deassert immediately when reset or
  cancel is asserted.
- Output starts after a zero-length config or after the valid final payload
  edge. There is no same-cycle output bypass and no same-cycle config credit
  at final retirement. Output bytes, `out_last`, and `out_count` remain stable
  while `out_ready` is low. `out_last` is asserted only for the final CRC high
  byte.
- On the final output handshake, `stat_sent` saturates and the module returns
  idle. A new config cannot be accepted on that same edge.

## Reset and cancel

Synchronous `rst` has priority over `cancel`, which has priority over ordinary
operation. Reset clears control, fault state, CRC seed, and all counters.
Cancel flushes the reservation, pending payload index, pending output index,
and output count; it counts one abort if and only if the module was busy and
preserves the other counters. Held cancel therefore counts only once. No
output handshake is counted on an abort. A caller must discard any partial
output after cancel.

All counters saturate. Before saturation and absent reset, the intended
invariant is `admitted = sent + aborted + busy`.

## Author verification

`tests/rtl/transport/tb_wire_serializer.sv` observes only public ports and
covers lengths 0..32, all 256 payload byte values, maximum seq/tick and byte
order, zero-length CRC, metadata/output stalls, deterministic bubbles,
payload-last faults, illegal lengths 33 and 63, held-cancel behavior, reset
and cancel in receive/header/payload/CRC/final phases, no-same-edge credit,
reset priority, and `STAT_W=2` counter saturation. Additional public-port
checks hold a just-registered fault event across the following falling edge,
verify unchanged counters and abort-gated handshakes before the next rising
edge, and verify ordinary, cancel, and reset clearing after that edge. Four
fixed packet CRCs are cross-checked against Python `binascii.crc_hqx`.

The main packet reference and CRC sweep use an author MSB-first recurrence
with the same polynomial. They are author cross-checks, not an independent
oracle. Main-owned independent fixtures, mutated RTL acceptance, integration,
and publication remain absent from this candidate.

`tools/transport/run_wire_serializer.py` creates a fresh author-owned attempt,
snapshots the serializer, candidate, testbench, runner, read-only CRC
dependency, scope, and pinned contract, isolates temporary and simulator
directories, executes real ModelSim 10.7, and records raw process evidence.
Its strict parser requires the exact ordered case sequence, per-case counts,
complete stats, zero failures, and zero unexpected diagnostics. The separate
illegal-parameter top checks the required time-zero fatal message.

## Limits

Only the opaque mathematical serialization candidate is claimed. Type,
epoch, seq, and tick are not interpreted. No parser, UART, packet
authorization, freshness, scheduler, physical layer, CDC/RDC, synthesis,
implementation, timing closure, board, system, All29, B04, or R03 result is
claimed here. Main owns independent acceptance; A alone operates the physical
board.
