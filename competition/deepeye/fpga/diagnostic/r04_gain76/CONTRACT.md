# MCP6S21 write-only gain-master candidate

Status: `CANDIDATE_SOURCE_ONLY`, `UNEXECUTED`, `R04_NOT_PASSED`. This is a standalone seam, not integration, pinout, clock-setter, synthesis, timing-closure, electrical or board evidence. Product acceptance remains governed by `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01-H15, requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`.

## Vendor facts supplied by the main

The main reported an actual reading of official Microchip DS21117B. This worker did not fetch the network or independently revalidate the PDF. For MCP6S21, the write-only device has no SO. It accepts SPI mode 0: CS low, SCK idle low, SI sampled on SCK rising, MSB first. A normal transfer holds CS low for exactly 16 SCK clocks. The write-gain instruction is `0x40`; data bytes `0x00`, `0x01`, `0x02`, `0x04` select G1, G2, G4, G8. Code 3 denotes G5 and is forbidden here; codes 5, 6, 7 are also refused by this candidate.

The DS21117B limits supplied for review are: CS-high minimum 40 ns, first-SCK setup 40 ns, SCK high/low minimum 40 ns, final edge to CS-high 30 ns, SI setup 40 ns, SI hold 10 ns. These are datasheet table conditions, including the datasheet's higher-voltage/high-rate context, not a 3.3 V measurement. A must validate the actual selected device, supply, level shifting, isolation and PYNQ-Z2 electrical behavior.

## Command and result interface

`cmd_valid && cmd_ready` at a rising clock edge transfers one command. `cmd_ready` requires `enable=1`, `cancel=0`, idle, and an empty result slot. Legal commands pulse `accepted` for one clock after that edge. An illegal code still consumes the transfer so the sender cannot deadlock, but `accepted=0`, CS remains high, no SCK occurs, and the result slot immediately reports `result_error=1` with the supplied tag. Thus handshake, command acceptance and digital completion are distinct.

Only one command may be in flight. `result_valid` is a held result until `result_valid && result_ready` at a clock edge. While `result_valid=1`, `result_error` and `result_tag` remain stable and `cmd_ready=0`; those payload fields are meaningful only while `result_valid=1`. A normal frame closes with `result_valid=1`, `result_error=0`; this means only that the digital frame finished, never that a gain took effect or that an ADC value is ready.

`cancel` and `enable=0` abort an active frame at the next clock edge. They force CS high, SCK low and SI low, pulse `aborted`, create a held error result carrying the accepted tag, then hold CS high for the full guard before another command can be accepted. They do not replay or restart the command. Reset is synchronous and destructive: active reset forces the same safe pins, starts the same CS-high guard and may pulse `aborted`, but it clears the result slot and tag, so no post-reset result identifies the interrupted transaction.

## Candidate timing and frame

For the assumed 100 MHz source clock only, a local divider uses 100 ticks per SCK half period: 1 us low and 1 us high, or 500 kHz SCK. CS setup, final-edge hold and CS-high gap each use 100 ticks. These are conservative engineering assumptions from the main, not a clocksetter decision and not settling evidence.

The frame is `{8'h40, 5'b00000, gain_code}` in MSB-first order. Normal operation produces 16 rising SCK edges, one CS-low interval, and no byte boundary inside it. SI changes only in SCK-low intervals before a rising edge; the final falling edge is followed by at least 100 ticks low before CS rises. The first bit is the zero MSB of `0x40`, pre-driven during CS setup.

An aborted partial frame deliberately prioritizes safe pins over completing a valid 16-clock transfer. The device may ignore it or retain unspecified prior gain; this candidate makes no rollback, retry, analog-unknown-recovery or eventual-gain claim.

## Required dependencies not implemented

R04 requires independent ADC readback after A0 and before A3, plus gain-effect evidence. This module has no ADC path, A0/A3 capture, readback, settling model, calibrated ratio, multi-level sweep or 5% measurement. No 8-level or accuracy result is claimed.

The required local overrange policy (explicitly request G1) is absent. A future owner must provide a priority arbitration seam that issues a new `gain_code=0` command after the current result is drained; this module neither infers overrange nor retries automatically. Fake ADC data and implicit gain changes are prohibited.

Pins, physical CS/SCK/SI mapping, 3.3 V compatibility, bidirectional level shifting, isolation, external gain and reference behavior, device population, reset topology, SDC, CDC, timing closure and board programming remain A-owned or unassigned. No compile, lint, simulation, formal, synthesis, implementation, network, vendor-tool or board action was performed.

## Review boundary

`vectors_UNEXECUTED.json` is a bounded digital test plan only. It records expected interface and pin-edge observations; it contains no execution log, analog expectation, calibration data or pass claim. Main must review this source and separately authorize any simulation or integration work.
