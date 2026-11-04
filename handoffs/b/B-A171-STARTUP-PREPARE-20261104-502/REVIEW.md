# Explicit startup preparation for the joint demonstration

At a new run, the previous interface could not preset speed without immediately
driving the motor. Source `4f925582a5cfb82e619021ded5effa036d8d000a` adds one explicit opcode8
and the existing sole-owner `startup_prepare(run_id, initial_speed_permille,
move_ms=500)` RPC. It queues a finite servo move to original references2088/1961,
stores speed separately, and remains unarmed/PWM0/current normalized speed0.
Boot observes without automatic homing. Normal ARM/pause/resume does not home.
STOP cancels; duplicate/unknown requests are never automatically replayed.

A owns the monotonic1s wait after the actual prepare ACK and continues SENSE/STOP.
Only a later real same-round admission starts Native and op6. ACK preset fields
are accepted targets, not measured arrival, executed PWM, or measured RPM.
The first real+880 remains880/PWM690 rather than accumulating the preset twice.
Existing CRC/sequence/source/lease/limits and1ms nonblocking replies remain.

Actual local checks:16 compiler/test commands exit0, legacy C37, pacer C38,
startup C24, real Python encoding accepted by C27, boot8 synthetic preflight
responses without motion, and12 host/RPC/strict-pinning cases exit0. Initial
test import/fixture and a compile warning are retained, not overwritten.

Actual one-time MCU deployment507 exited0 with SDK shutdown and CPU RUN;
13624 programmed bytes read back SHA1b9c6dcf1bb159b53d2feac0b227be4c7eeab10228f39d61747344b2d4837ea6.
Motor OFF, fresh raw feedback, original calibration and no boot servo writes were
observed. B sent no op8 or motion fixture. New opcode8 physical acceptance is
pending A1392; these local checks and deployment do not establish it.

A1711344 closure was independently checked against514 original CRC frames:
257TX45..301 matched257RX,180 real common rounds; STOP301 ACKOFF/next302.
Original unknown44 stays unknown. PS actors empty/original lock released,
MCU service exit0/joined/streams closed. G05 null stop_response is not a fabricated
RPC ACK: original terminal tail proves closed/not-unknown; the879MB whole stream
is not claimed hashed.1392 canonical1189B request preimage was independently
verified. New unique transfer509 and observation508 are delivered to A; old499
is consumed. After transfer B has no MCU/SWD/UART ownership.

H01–H15/rev2 `2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d`
and both H12/full29/full-route gates remain. Basic linkage confirmation does not
claim full-route or formal acceptance. The verifier is entirely offline.
