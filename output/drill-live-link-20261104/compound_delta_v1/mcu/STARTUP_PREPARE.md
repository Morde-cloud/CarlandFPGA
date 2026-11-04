# Explicit startup preparation (A171/A172)

`startup_prepare(run_id, initial_speed_permille, move_ms=500)` uses opcode8.
It queues one finite two-servo SYNC WRITE to original calibrated targets
2088/1961 (command angles0/0), while leaving the motor OFF and unarmed.
Boot only reads existing configuration/feedback; it no longer automatically
moves to home. Ordinary ARM, pause and resume never recenter the servos.

The accepted initial speed is stored in `MotorRuntime.prepared_speed_permille`,
separate from executed `speed_norm`, which remains0. The first genuine op6
uses its existing real source/run/admission and accumulates from0. Preparing
does not ARM, renew a motor lease, revive a source, or issue an AI command.
The prepared run must be strictly newer than both previously prepared and
executed runs; a duplicate is refused without repeating home. STOP, failure
or the physical stop button cancels the pending preparation and retains its
run highwater. Already transmitted finite servo motion is not reversed by STOP.

Wire format remains32B/CRC16-CCITT-FALSE, little endian:

|Offset|Value|
|---|---|
|0..3|`d3 4c 01 08`|
|4..7|monotonic nonzero wire sequence|
|8|existing source1/2/3|
|9|VALID1|
|10..13|zero|
|14..15|initial normalized command speed0..1000|
|16..17|zero|
|18..19|move duration100..1000ms|
|20..23|zero (no common AI command consumed)|
|24..27|nonzero run ID|
|28..29|zero (no lease)|
|30..31|CRC over0..29|

The unchanged status ACK binds the exact sequence/result to accepted request
bytes. It reports target angles0/0, actual raw servo feedback, PWM0 and unarmed;
it does not assert measured home arrival or measured speed. Host preset fields
are explicitly accepted command targets. Positive action still comes only from
the subsequent real op6; its value need not equal a stale precomputed preset.

A owns the monotonic1s gate after the real prepare ACK, continuing SENSE and
STOP handling. A starts software and MCU from the same fresh real admission
after that gate. B does not send a fixture or wait inside the MCU control loop.
The1ms nonblocking PC reply pacing and all source/lease/CRC/limit checks remain.

H01–H15/rev2 requirements SHA256:
`2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d`.
Local checks and deployment do not establish full route, dual H12 or all29 acceptance.
