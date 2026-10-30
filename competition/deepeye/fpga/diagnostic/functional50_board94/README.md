# deepeye_trace50_axi94 source fixture

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; work
`B-DEEPEYE-TRACE50-AXI-SOURCE-20261030-94`. This directory is a private
diagnostic source proposal, not a production top, public enable, Root
authority, admission policy, calibrated sensor path, board result, or product
acceptance.

Contract: `DEEPEYE-HUMAN-LOCK-20261014`, revision 1, H01-H15. Pinned canonical
requirements hash:
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`
at `f5989cd5defce561f9ba98e6b18fc2682945f0a2`. Taskbook freeze:
`1011259415a0916054eb580687612580bc1e5f09`.

## Status

`SOURCE_ONLY / UNEXECUTED`. No compile, elaboration, import, simulation, test,
synthesis, implementation, bitstream, HWH, timing, board, physical-link, or
host-decoder run is attached. NEW95 focused verification remains necessary.
The four files are source/planning material only.

## Files

- `deepeye_trace50_axi94.sv`: one 32-bit AXI-Lite slave endpoint.
- `register_map.json`: exact offsets, fields, state/fault/status mappings.
- `vectors_UNEXECUTED.json`: intended focused tests with no execution result.
- This README: source boundary and dependency closure.

## Structural boundary

The endpoint uses one nominal 50 MHz PS fabric clock and one 12-bit AXI-Lite
aperture. It contains the unchanged `deepeye_SYNTHETIC_codec74_fixture` at
50 MHz / 1,000,000 baud with `SOURCE_REVIEW_HOLD=0`, and the unchanged
`deepeye_uart_rx` at 50 MHz / 1,000,000 baud. The existing receiver limit is
`CLOCK_HZ/16` (3,125,000 baud at 50 MHz), so 1 Mbaud is eligible; the prior
5 Mbaud receiver setting is not used.

The fixture serializer TX is wired only to this receiver RX. There are no
external UART pins, no regenerated packet, no second encoder, and no CRC repair.
Accepted bytes are actual bytes produced by the unchanged existing single
encoder path. The 4096-byte ring preserves raw byte order and includes byte
value `0x00` without conflating it with empty.

`BUILD_ID[127:0]` defaults to zero. Zero BUILD_ID refuses ARM. A nonzero value
is a build identity input only, not a credential, BOOT proof, or enable token.
Source kind reads as 4 (`SOFTWARE_FIXTURE`).

## AXI behavior

- One independent AW capture slot and one independent W capture slot; neither
  ready output depends combinationally on its valid input.
- One held B response and one held R response. RDATA/RRESP/VALID and BRESP/VALID
  remain stable while stalled.
- Unknown or misaligned reads return `RDATA=0, RRESP=SLVERR`.
- Misaligned, unknown, read-only, unsupported-command, and `WSTRB!=4'hf`
  writes return `BRESP=SLVERR` without endpoint mutation.
- Reads never alter state. The command offset is write-only.
- BREADY/RREADY stalls cannot repeat a command or FIFO effect.

All register offsets, reset values, fields, and effects are normative in
`register_map.json`.

## Command sequencing

Commands are `1 ARM`, `2 PUSH`, `3 BIND`, `4 ACK`, `5 CANCEL`,
`6 CLEAR_FAULT`, `7 CLEAR_FIFO`, `8 POP`, with command high 24 bits zero.

Reset enters CANCEL and holds actual `source_cancel` asserted. ARM is accepted
only from CANCEL with fresh tag/origin staging, a nonzero greater tag, a
uint63 origin, actual core quiescence, idle RX, empty FIFO, no visible/core
result, and no sticky fault. It consumes ARM staging atomically. `source_cancel`
then deasserts; one `capture_rearm` pulse occurs on the next cycle; profile and
transport gates become active only after that settling sequence. CANCEL and
rearm are never asserted on the same edge.

One bounded scan accepts exactly channels 0, 1, 2, 3 in order. Each PUSH needs
fresh sample staging, the expected next channel, one common uint63 tick across
all four lanes, legal low-four-bit quality, and valid reserved-bit encodings.
A valid sample may carry source-fault quality. An invalid sample must carry
raw data `0x0000` as padding. The fourth accepted lane enters CAPTURED; a fifth
PUSH is refused.

There is no automatic retry, fifth lane, second scan, or rearm. A later scan
requires explicit CANCEL, an empty FIFO (drained or explicitly cleared), no
sticky fault, and a fresh greater nonzero tag.

## Association and time reconstruction

BIND is available only after four lanes. It derives tag, sequence 0/3, channel,
and acquisition tick from retained capture rather than caller alternatives.
The staged fields supply fixture-local session/index, source identity, and the
two time decompositions. Exactly one association is held until actual
`assoc_ready` or CANCEL.

For a valid sample, both equalities are checked with widened arithmetic:
`origin_qpc_ns + tick_us*1000 + remainder_ns == qpc_ns`. Acquisition must equal
the retained raw-lane tick; source must equal the staged source QPC. Remainders
must be below 1000 and uint63 high bits must be zero. Source must not exceed
acquisition, and held must equal `source < acquisition`. For an invalid sample,
source QPC, source tick, and source remainder are driven as all-zero wire
placeholders; they are not labelled healthy data.

Session, index, epoch, and sequence are fixture-local values. They do not prove
authentic Root/BOOT identity and are not protected by a secret.

## Result, cancellation, and raw bytes

BIND records `RX_total_before`. A successful result becomes PS-visible only
when actual core `result_valid` is high, `result_error=0`, RX is idle, and
`RX_total_after == RX_total_before + trace_result_bytes`. The 32-bit addition is
checked for overflow. A nonzero `result_error` is a visible refused result
after RX becomes idle; actual accepted partial bytes stay in the FIFO and
`result_rx_end` records the observed total. A core serializer wire fault is
reported by the unchanged core as `result_error=6` with `result_bytes=0`; this
endpoint retains it as a visible refusal rather than fabricating success.
Excess or missing bytes for a successful result latch a fault and cancel.

`trace_result_bytes` was source-verified as the exact total wire length. In
`.../additive50_source_candidate/rtl/deepeye_trace_block_uart_50mhz_candidate.sv`,
line 202 computes `expected_total_q = 14 + payload_meta_bytes`, and line 213
reports that value as `result_bytes`. The endpoint therefore counts total wire
bytes rather than only payload bytes. This is a source fact, not a measured
timing result.

A visible result is held across AXI stalls. ACK requires the exact fresh
expected result ID and actual core `result_valid`; it pulses
`fixture_result_ready` once. The endpoint then waits for core `result_valid` to
deassert. Four acknowledged results enter COMPLETE and do not auto-CANCEL or
rearm. Duplicate, stale, or wrong ACK IDs leave the result available and do not
pulse the core.

CANCEL always drives actual `source_cancel`, drops profile/transport and
association validity, and invalidates old result/scan capability. It records a
canceled/partial outcome and retains raw FIFO bytes, IDs, and counters. UART RX
itself reports partial-byte aborts through `stat_aborted`; no canceled bytes are
declared a completed packet. CLEAR_FAULT and CLEAR_FIFO apply only in stopped,
quiescent conditions. CLEAR_FIFO counts discarded bytes but does not reset
`RX_total`, `pop_id`, `result_id`, or BUILD_ID.

## Dependency closure

The unchanged recursive RTL closure is pinned here for the later independent
build review. Paths are relative to the implementation worktree.

| bytes | SHA-256 | path |
|---:|---|---|
| 12256 | `409ee484113fa4006eb27e12554a4db57708df5e7dadf269548f546d03931a6a` | `competition/deepeye/fpga/diagnostic/offboard_codec74/deepeye_SYNTHETIC_codec74_fixture.sv` |
| 11766 | `41ea63819c892ec67fe92d6e9338a771d5f93f60d0976e895f18bc97966283d2` | `competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_uart_50mhz_candidate.sv` |
| 10545 | `5ebe65dfe0844aab62365e8664507f153cb75ff47b3c8d4e10f45356e94147a8` | `competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_payload_1us_candidate.sv` |
| 12241 | `fb64ace453c451838110c81bf6cb4a815a96fb2668e28a306ff699beca5acef6` | `competition/deepeye/fpga/codec/deepeye_trace_payload_candidate.sv` |
| 21517 | `4cb79428ef89096742e293516c4696caf985048d8185f531fe92eaa485c8d532` | `competition/deepeye/fpga/codec/deepeye_block_encoder.sv` |
| 3890 | `c8a540db8122b8f5520582a0f1fa9be0c43cb54a62f03c7c4edc893906f28411` | `competition/deepeye/fpga/acquisition/deepeye_buffered_scan_capture.sv` |
| 17174 | `fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d` | `competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv` |
| 6642 | `630e14803d82b3379517d91626de4ad7e7d3c509ad14363b3164031a5f633ee4` | `competition/deepeye/fpga/acquisition/deepeye_raw_scan_queue.sv` |
| 1720 | `b3c9d2024d9325191538cf08fec9a652ff8ff0ae316ec9af96078f85cf5be3cc` | `competition/deepeye/fpga/acquisition/deepeye_scan_lane_stream.sv` |
| 9705 | `efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885` | `competition/deepeye/fpga/transport/deepeye_wire_serializer.sv` |
| 1875 | `8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f` | `competition/deepeye/fpga/transport/deepeye_crc16_byte.sv` |
| 6811 | `5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47` | `competition/deepeye/fpga/transport/deepeye_uart_tx.sv` |
| 11182 | `935f5d02008535fd5da75b7dc80696d14b03bd54d85f8b52fbf12c1e0504f08f` | `competition/deepeye/fpga/transport/deepeye_uart_rx.sv` |

No include or vendor cache is part of this module closure. Expected build
tool/device, BD Tcl, XDC, PS AXI window address assignment, same-run BIT/HWH,
post-route timing, DRC, and artifact hashes are still absent and remain for the
main-selected builder phase.

## Explicit non-claims and next gate

This source does not establish a board image, real production BOOT, UART/RS485
voltage or oscillator tolerance, physical ADC value, ADC calibration, measured
gain, 1800-second behavior, both H12 control paths, all 29 gates, or H01-H15
completion. It does not mutate G05 STOP and does not supply atomic cross-endpoint
STOP. It does not make an external capture or PS timestamp authentic.

`vectors_UNEXECUTED.json` is only a proposed NEW95 test inventory and contains
no measured response. Main-owned review must decide any repair, actual focused
simulation, builder selection, and publication. A alone owns board operation.
