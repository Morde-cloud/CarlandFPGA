# R04 local-overrange safety-arbiter candidate

Status: `CANDIDATE_SOURCE_ONLY`, `UNEXECUTED`, `R04_NOT_PASSED`. This is a
standalone seam, not integration, simulation evidence, pinout, timing closure,
ADC/calibration evidence, or a physical-safety claim. It directly instantiates
the adopted `r04_gain76/deepeye_mcp6s21_write_candidate.sv` unchanged and adds
no encoder. Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01-H15,
requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`.

## Interface and ownership

`enable`, `cancel`, `rst`, and `arm` control admission. `arm` is accepted only
on a 0-to-1 pulse after reset/disable/cancel. `cancel`, `disable`, and `reset`
assert the master cancel input; enable recovery never auto-arms.

`reserved_safety_tag` is latched by a successful arm. A host handshake is
`host_valid && host_ready`; accepted host tags must be nonzero and different
from the latched safety tag. Gain legality remains the original r04_gain76
master's decision: this wrapper does not add an encoder or silently remap gain.

The host result is one fixed held slot: `host_result_valid/ready/error/tag`.
The safety result is a separate fixed held slot:
`safety_result_valid/ready/error/tag`. Neither slot is a queue, evicts, or
overwrites; payloads are meaningful only while `valid=1`. A full host slot
forbids another host request but does not block safety fallback. Results never
become gain measurements.

## Overrange policy

`overrange` is only a candidate seam for an externally decided ADC hardware
flag; this source does not infer threshold, calibration, fake ADC data, or a
stimulus change. The first asserted cycle sets `inhibit` and combinationally
blocks a same-cycle host handshake. If a host frame is already in flight, the
wrapper cancels it and waits for the original tag's digital terminal result,
then stores that result in the host slot and drains the master result.

After the original transaction is terminal and the master is ready, one new
explicit `gain_code=0` (G1) command is sent with the reserved safety tag; this path
has priority over host traffic. Sustained overrange never repeats fallback.
Returning `overrange` low does not clear `inhibit`. A later rising `arm` pulse
clears it only when overrange is low, the master is idle, and both result slots
are drained. There is no automatic retry or replay of an old host request.

## Digital result meaning

`error=0` means only that the 16-edge digital frame completed. `error=1` means
the command was refused or aborted, or its digital transaction ended in error.
An abort after some edges may already have affected analog state; the resulting
gain is unknown. Neither result proves CS/register state, settling, `RESULT`, or
that a real gain took effect. R04's actual ADC, calibration, 8-level sweep,
5% analog accuracy, settling and physical evidence remain unsatisfied.

## Identity and terminal faults

`sticky_fault` latches and blocks all restarts for a reserved tag of zero, a
tag that changes after arm, a host attempt using the reserved tag, a mismatch
between a master result tag and the recorded owner/tag, or an unsolicited master
result. No success result is fabricated on a mismatch. Reset clears this stored
fault but does not acknowledge or recover an interrupted analog state.

A valid reserved safety tag has not been supplied by the product/protocol
owner. **Blocker:** until one is assigned, zero or colliding identities are not
usable; production integration must remain disabled (`enable=0`, unarmed).

## Reset, assumptions, and evidence

Reset is synchronous and destroys wrapper slots/context exactly as the 76 master
semantics destroy its result. There is no post-reset ACK. Host software must
separately retain a persistent UNKNOWN state for a reset or aborted transaction.

The assumed clock is 100 MHz only because the adopted 76 candidate assumes it;
this wrapper does not create a clock constraint or alter its divider. `overrange`
is assumed synchronous to `clk`; no CDC proof is provided. `spi_cs_n`, `spi_sck`
and `spi_si` are bare candidate ports with no pins, level shifting, isolation,
clocksetter, 100 MHz timing, final 1% / 100 ms target, full H12, or all-29-card
acceptance. All H01-H15 requirements and acceptance remain unchanged.

`vectors_UNEXECUTED.json` records manual expectations only. No compile, simulation,
test, import, synthesis, implementation, board, ADC, or network action was performed; main review required.
