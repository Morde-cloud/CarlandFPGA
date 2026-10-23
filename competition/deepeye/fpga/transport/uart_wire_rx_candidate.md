# `deepeye_uart_wire_rx` candidate

Work: `B-UART-WIRE-RX-20261024-31-v1`  
Task: `DEEPEYE-IMPLEMENTATION-20261014/v1`  
Operation: `B-DEEPEYE-UART-WIRE-RX-20261024-31`

This is an author candidate only. It is opaque same-clock digital receive
composition, not a public ABI, semantic packet/profile/source/BOOT policy,
authentication, replay/liveness policy, physical CDC or electrical proof, or a
board result.

## Frozen inputs

- Scope SHA256: `575bba8abfcacddcd6a445a0d56f0dacdca7e1bf976390b479dbff70c0f55a8b`
- Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, canonical requirements
  SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
- Design: `1011259415a0916054eb580687612580bc1e5f09`.
- `deepeye_uart_rx.sv`: `935f5d02008535fd5da75b7dc80696d14b03bd54d85f8b52fbf12c1e0504f08f`
- `deepeye_wire_parser.sv`: `7806c5d08785b96eae3708d9fd6d6002ef82faa4416a1f7244da73bece552649`
- `deepeye_crc16_byte.sv`: `8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f`

The dependencies are read-only. This composition adds no packet or byte buffer,
state machine, semantic decode, or aggregate counter.

## Interface

Parameters: `CLOCK_HZ` legal 16..2147483647 (default 100000000), `BAUD` legal
1..`CLOCK_HZ/16` (default 9600), and `STAT_W` legal 2..32 (default 32).
Invalid overrides are clamped before dependency elaboration. In particular,
illegal `STAT_W` values below 2 use effective width 2 and values above 32 use
effective width 32, exactly matching the clamped public counter ports while
still firing the own time-zero guard. The module's guards have exact order
`CLOCK_HZ`, `BAUD`, `STAT_W` and prefix `deepeye_uart_wire_rx:`.

Public ports are `clk`, `rst`, `cancel`, `rx_async`, `out_ready`; candidate
outputs `out_valid`, `out_type[7:0]`, `out_epoch[7:0]`, `out_seq[15:0]`,
`out_tick[31:0]`, `out_len[5:0]`, `out_payload[255:0]`; status
`uart_busy`, `receiving`, `line_error_event`, `line_error_bits[2:0]`,
`error_event`, `error_code[1:0]`; and all thirteen named saturating counters.
Counter outputs are direct aliases of the corresponding dependency outputs.

## Composition

`internal_cancel` is `cancel || line_error_event`. The same `rst` and
`internal_cancel` drive both dependencies. UART `out_ready` is parser
`in_ready`; parser `in_valid` and `in_data` are the UART outputs. Parser output
ready is external `out_ready`. `line_error_bits` is
`{overrun, framing, false_start}`, so bit 0 is false start, bit 1 is framing,
and bit 2 is overrun. UART diagnostics are raw registered outputs.

A line error first registered on edge `e` masks candidate and input handshakes
immediately after `e` and synchronously flushes both units on `e+1`. A candidate
already accepted by the parser before that boundary is a prior syntactically
valid candidate and is not retroactively revoked. Parser version/length/CRC
faults remain parser `error_event`/`error_code` outputs and do not invoke the
intra-composition line-error cancel. An external `cancel` held high flushes once;
the UART must subsequently observe line high before a new falling edge starts a
byte. Partial input is not a wall-clock timeout; liveness remains caller-owned.

## Evidence boundary

The author testbench uses public ports only and an independent packet-byte
builder with a direct bitwise CCITT-FALSE recurrence. It checks packet bytes,
all payload values, lane order/endianness, line faults, shared abort, warmup,
the exact error-edge/next-edge boundary, reset/cancel regions, overrun discard,
and counter saturation. Its runner binds the immutable testbench hash, five
fixed suites, every case's exact check count, the complete ordered marker
family, the single final ModelSim diagnostic tally, and the seven exact guard
probes. It preserves fresh raw command streams, source snapshots and hashes.
It is author evidence, not independent acceptance.
Synthesis, implementation, timing, CDC/RDC, board, and full-system results are
`not_run`.
