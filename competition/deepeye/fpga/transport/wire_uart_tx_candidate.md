# deepeye_wire_uart_tx candidate

Work `B-WIRE-UART-TX-20261024-30-v1`, task
`DEEPEYE-IMPLEMENTATION-20261014/v1`, operation
`B-DEEPEYE-WIRE-UART-TX-20261024-30`. Contract
`DEEPEYE-HUMAN-LOCK-20261014/revision1` H01-H15, requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen design `1011259415a0916054eb580687612580bc1e5f09`.

This is an internal opaque digital transmit composition. It is not a public
ABI, packet/type allocation, source or BOOT decision, clock/pin/TTL/RS485
approval, wire-compatibility claim, control policy or physical-board result.
`tx`, `de` and `out_count` do not authorize motion or certify a public packet.

## Ports

- Clock/control: `clk`, `rst`, `cancel`.
- External reservation: `cfg_valid`, `cfg_ready`, `cfg_type[7:0]`,
  `cfg_epoch[7:0]`, `cfg_seq[15:0]`, `cfg_tick[31:0]`, `cfg_len[5:0]`.
- Payload: `p_valid`, `p_ready`, `p_data[7:0]`, `p_last`.
- Digital/frame status: `tx`, `de`, `busy`, `receiving`, `faulted`,
  `fault_event`, `fault_code[1:0]`.
- Saturating reservation counters: `stat_admitted`, `stat_sent`,
  `stat_aborted`, each `STAT_W` bits.

No packet register, byte count, ABI selector or debug aperture is added.

## Parameters and guards

- `CLOCK_HZ`: default 100000000; legal 2..2147483647.
- `BAUD`: default 9600; legal 1..`CLOCK_HZ/2`.
- `PRE_CYCLES`: default 0; legal 0..65535.
- `POST_CYCLES`: default 0; legal 0..65535.
- `STAT_W`: default 32; legal 2..32.

All state/count declarations remain legal for invalid overrides. Safe values
are passed to the serializer and complete-frame transmitter. Time zero emits
exactly one top-level fatal diagnostic in this order: `CLOCK_HZ`, `BAUD`,
`PRE_CYCLES`, `POST_CYCLES`, `STAT_W`. Dependency duplicates are suppressed by
the safe parameter handoff.

## Reservation and transfer

`busy` is the registered top reservation and remains high from an admitted
external config through serializer collection, serialized-byte transfer,
complete frame buffering, UART transmission, direction hold and drain
observation. It remains high after any fault until cancel/reset.

`cfg_ready` is high only while there is no reservation, reset/cancel are low,
and both dependency config-ready outputs are high. A top config handshake is
the only event that forwards config to the serializer and increments
`stat_admitted`. No config is admitted on the retirement edge of an old
reservation. An externally held config can be accepted only on a later edge,
after that retirement has become visible.

`p_ready` is high only in the collection state and while the serializer is
receiving. The serializer advertises payload-ready only after the config edge,
so a payload cannot receive credit on the same edge as config. Payload data and
last connect to the serializer without buffering or interpretation.

When serializer output first becomes valid, the wrapper waits for the complete
frame transmitter's config-ready. It then issues one config with the
zero-extended internal `out_count` (14..46). The config handshake registers a
separate transfer permission. No byte is presented on that config edge.

After registration, the combinational transfer path is exactly:

```text
serializer.out_ready = transfer_permission && frame.s_ready
frame.s_valid         = transfer_permission && serializer.out_valid
frame.s_data          = serializer.out_data
frame.s_last          = serializer.out_last
```

The complete-frame transmitter buffers every serialized byte before raising DE
or starting the byte UART. At the accepted final serialized byte the wrapper
clears transfer permission and enters `WAIT_DRAIN`. The serializer cannot
reissue the packet, and no additional packet buffer exists in the wrapper.

`WAIT_DRAIN` retains busy until the first rising edge that observes the frame
transmitter already not busy. That edge increments `stat_sent` and releases the
top reservation. The following edge is the first edge on which a new external
config may handshake. This one-edge post-frame observation is deliberate.

## Reset, cancel and faults

Reset has priority over cancel, which has priority over ordinary operation.
Reset and cancel are passed together to both dependencies. Reset clears the
wrapper counters and flushes the reservation and both dependencies. Cancel
preserves `stat_admitted` and `stat_sent`, flushes one busy reservation, and
increments `stat_aborted` once; a held cancel is counted once. All counters
saturate.

Invalid external length or payload-last poisons the reservation through the
serializer. No frame config or serial start occurs, the serializer fault is
sticky, and the wrapper retains busy until cancel/reset. Serializer fault has
priority over frame fault for `faulted`, `fault_event` and `fault_code`.
Underlying synchronous fault-event pulse semantics are passed through without
a new asynchronous diagnostic gate.

## Author verification scope

The public-port author TB uses Python `struct` plus `binascii.crc_hqx` to make
independent expected packet/CRC bytes. The DUT's serializer state is never used
as the expected byte source. Coverage includes lengths 0..32, every payload
byte value, maximum metadata, input bubbles, held config while busy, illegal
length/last, cancel and reset in collection/transfer/PRE/START/DATA/STOP/POST,
integer and fractional baud, default 100 MHz/9600, PRE/POST timing, held cancel
and `STAT_W=2` saturation. Exact parameter guards are separate negative
simulations.

This evidence does not cover All29, B04, R03, full product, synthesis,
implementation, timing, CDC/RDC, physical board or system behavior.
