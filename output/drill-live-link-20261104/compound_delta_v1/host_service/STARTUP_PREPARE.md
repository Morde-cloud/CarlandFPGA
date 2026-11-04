# Explicit per-run startup preparation

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-A171-STARTUP-HOST-SEAM-20261104-503`. H01–H15 revision 2 requirements SHA256
`2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d`.

Use the existing sole UART owner, after a new unique Root/B transfer attach:

```python
prepared = client.startup_prepare(
    run_id=1793772501, initial_speed_permille=880, move_ms=500)
```

`client` may be the already-attached `ProductUartService`, `SessionClient`, or
`SshClientAdapter` with its existing `keepalive=False` SSH client. The existing
stdio RPC also accepts `op="startup_prepare"`, `run_id`,
`initial_speed_permille`, and optional `move_ms`, with the same
`session/request_id/expires_ms` envelope. No extra thread or UART owner exists.
There is no service-side sleep, simulated clock rebasing, automatic ARM or
source lease renewal. The Root owns the one-second monotonic wait after the
actual prepare reply, continues sensing/stop handling during that wait, and
starts virtual movement and the real op6 on the same later valid admission.

The MCU accepts op8 only while actually unarmed/OFF with fresh healthy feedback.
It queues one finite dual-axis move to absolute command zero using the saved
raw references 2088/1961. It stores the requested normalized initial speed in a
separate preset slot. Current compound speed remains 0 and motor PWM remains
0. `prepared_speed_permille` in the JSON reply describes the accepted request's
preset target; it is neither executed PWM nor measured RPM. The unchanged raw
32-byte UART ACK is included as `uart_ack_hex`. Its actual raw feedback is
preserved and `uart_ack_is_not_arrival=True` remains explicit.

The first actual op6 must reference the prepared run and starts from the
current speed 0. For example, preparing 880 and then sending the first real
speed delta +880 produces command speed 880 and PWM 690, without double
accumulation. A normal ARM or pause/resume does not issue another op8 or home.
STOP/error cancels local prepared-active state; the prepared-run high-water
identity remains so an old preparation cannot be replayed. Timeouts and unknown
outcomes latch failure and use the existing single terminal STOP path.

## Wire op8

All integers use little endian. Existing op1–7 and ACK layouts are unchanged.

| Bytes | Meaning |
| --- | --- |
| 0–3 | `d3 4c 01 08` |
| 4–7 | positive monotonic wire sequence |
| 8 | original source: PC_DIRECT=1 / FPGA_OUTPUT=2 / MANUAL=3 |
| 9 | VALID=1 |
| 10–13 | zero |
| 14–15 | initial normalized speed preset 0…1000 |
| 16–17 | zero |
| 18–19 | finite servo move time 100…1000 ms, default 500 |
| 20–23 | zero; not a real AI/common command |
| 24–27 | positive new run ID |
| 28–29 | zero; no motor lease |
| 30–31 | CRC16-CCITT-FALSE over bytes 0–29 |

Vector seq302/sourceFPGA_OUTPUT/run1793772501/preset880/move500:

```text
d34c01082e01000002010000000070030000f40100000000d5cbea6a00008d5b
```

Stage the changed files and all unchanged baseline dependencies into a **new**
runtime directory. Do not overwrite the old A1271/1344 runtime bytes. Updated
`SOURCE_PINS.json`, in-code dependency pins and stdio service pin must agree.
The local source layout stores unchanged dependencies in
`output/drill-live-link-20261104/baseline_mtr4/` and
`output/drill-live-link-20261104/drill_live_link/`; delivered runtimes put those
under `host_service/baseline_mtr4/` and `host_service/drill_live_link/`.

Focused software check: `python -B startup_prepare_test.py` in that staged
layout. Its synthetic UART checks are software evidence, never physical
readiness, measured arrival, full-route success, or formal product acceptance.
