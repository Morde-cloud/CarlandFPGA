# MTR4 joint UART source audit

Source/file-only; current MCU boot, state, wire continuity and FPGA configuration are unobserved here. Main alone controls hardware and acceptance. H01–H15/revision2 fixed requirements 2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d.

## Command frame (32 bytes)

|Bytes|Encoding|Meaning|
|---|---|---|
|0..1|d3 4c|magic|
|2|1|version|
|3|1ARM / 2POSE / 3STOP / 4STATUS / 5MOTOR|operation|
|4..7|uint32 LE|request seq; host requires1..UINT32_MAX, increasing/no wrap|
|8|1PC_DIRECT / 2FPGA_OUTPUT / 3MANUAL|declared source; not authentication|
|9|zero|reserved|
|10..11|int16 LE centidegrees|POSE yaw -9000..9000; MOTOR zero|
|12..13|int16 LE centidegrees|POSE pitch -4500..6800; MOTOR zero|
|14..15|uint16 LE permille|POSE zero; MOTOR0OFF or250..750|
|16..17|zero|MTR4 forward-only gimbal profile/reserved|
|18..19|uint16 LE ms|POSE finite move100..1000; MOTORlease100..500 (default300)|
|20..23|uint32 LE|POSEsource_seq; MOTORzero|
|24..27|uint32 LE|POSEobservation_seq; MOTORzero|
|28..29|zero|reserved|
|30..31|uint16 LE|CRC16-CCITT-FALSE over bytes0..29; poly1021 initffff no reflection/xorout|

## Reply frame

|Bytes|Meaning|
|---|---|
|0..3|d3 4c 01 80|
|4..7|uint32 LE ECHO request seq, not actual high-water|
|8|armed bool|
|9|0OK 1CRC 2FORMAT 3DISARMED 4RANGE 5REVERSE_WAIT 6SEQUENCE 7WATCHDOG 8SOURCE|
|10..13|int16 LE target yaw/pitch centidegrees; commands not measured angles|
|14..15|uint16 LE requested motor duty permille; not RPM/current|
|16|direction; MTR4 normal profile0|
|17|active declaredsource0/1/2/3|
|18|bit0yawfresh bit1pitchfresh bit2motorcompiled bit3gimbalcompiled|
|19|last servo bus error;0OK/ffunavailable|
|20..23|uint16 LE raw yaw/pitch servo readback;ffff unavailable|
|24..27|uint16 LE yaw/pitch age ms;ffff unavailable, fresh <=1000ms plus flag|
|28..29|uint16 LE saturating servo bus-error count|
|30..31|uint16 LE CRC16 over first30bytes|

## Main decisions before hardware

- Reply seq echoes supplied request: no wire boot UUID or last_seq/high-water field. Do not infer currentseq from reply or historical296.
- Fresh STATUS consumes shared sequence but does not clear prior result or refresh motor deadline. Invalid/stale/nonOK STATUS is not passive: MTR4 wrapper stops motor and calls fc_stop.
- Valid STOP always disarms even with old seq; high-water only advances if greater. STOP is a side effect, not a probe, and does not cancel an already emitted finite servo frame.
- ARM is required before POSE/MOTOR, binds source; non-READY rejects armed state. Change source through explicit stop/new arm, not merely physical UART routing.
- MOTOR checks healthy READY/fresh feedback<=1000ms/source/ARM, own100..500ms lease. POSE updates gimbal watchdog state but does not renew motor deadline; STATUS does neither.
- General ARM/set watchdog500ms remains; motor lease default300ms/keepalive100ms. Host serialized status+arm+pose and status+motor exchanges can starve lease; no auto-rearm/replay.
- Old pc.codec Command/encode_command limits±15deg/300permille and no op5. Reuse its reply decoder/CRC only; current encoders are fpga_link.session.encode and motor_runtime.variable_session.encode_motor.
- motor_control.h comment still says0..300permille, implementation and pinnedMTR4 build specify0OFF/250..750. PROTOCOL.md is also an older profile, not sole current acceptance source.
- observe.js connects debug target, loads symbols, and calls run(false) on halted target both initially and finally. It writes old physical-owner evidence directory. It is not a strictly passive observer and must not be run unchanged by new owner.
- Startup waits3s then actual servo preflight/homing to2088/1961; reset or resume at startup can produce motion without a new UART pose.
- Exact map offers RAM diagnostics: last_seq at free_diagnostics+0, have_seq+37, armed+34, signature+52, state+56; current state can be inspected without guessingseq only if parent verifies vendor read-only attach while running and refuses halted/resume/reset/write. This audit does not establish debugger-connect semantics or current device state.

## Pins and actual map

{
  "PC_UART": "UART1 PB6TX/PB7RX 3.3V logic",
  "servo_bus": "UART0 PA0TX/PA1RX via existingUT01 interface; do not connect servo bus directly toFPGA",
  "motor": "PA12 TIMG0_CCP0; source32MHz/1600counts nominal20kHz, not measured here",
  "FPGA_candidate": "PMODA1/Y18 TX\u2192PB7RX; PMODA2/Y19 RX\u2190PB6TX; PMODA5GND; only historical candidate, A must confirm current product pins/clock/address",
  "wiring_verified_by_this_audit": false
}

{
  "symbols": {
    "free_diagnostics": "0x20200000",
    "motor_diagnostics": "0x202001b0",
    "motor_gpio_output": "0x202001cc",
    "motor_pincm": "0x202001d0",
    "motor_pwm_applied": "0x202001d4",
    "motor_pwm_peak": "0x202001d8",
    "ticks": "0x202001c0"
  },
  "free_size": 172,
  "motor_size": 16,
  "field_offsets": {
    "last_seq": 0,
    "have_seq": 37,
    "armed": 34,
    "signature": 52,
    "state": 56,
    "yaw_raw": 22,
    "pitch_raw": 24,
    "feedback_seen": [
      38,
      39
    ],
    "result": 42,
    "bus_status": 41,
    "sync_frames": 156,
    "configured_min": [
      160,
      162
    ],
    "configured_max": [
      164,
      166
    ]
  },
  "motor_offsets": {
    "deadline_ms": 0,
    "commands": 4,
    "stops": 8,
    "duty": 12,
    "active": 14
  }
}

Exact source hashes and all original build-manifest identities: SOURCE_PINS.json. No firmware, settings, old physical evidence, ports, services or queues modified.
