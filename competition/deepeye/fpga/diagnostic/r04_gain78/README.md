# R04 digital SPI stage78

H01-H15/revision1 requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen task1011259415a0916054eb580687612580bc1e5f09, board operator A only.

Source76 was an unexecuted Flash source handoff. The main preserved its exact
three original files/hashes, corrected the documentation's frame concatenation,
qualified input net ports for ModelSim10.7 and gated ready during reset. The
current master's bytes match the NEW78 executed frozen snapshot. The original
76 CONTRACT/vectors retain their historical source-only status; the16 listed
vectors were not run as that original suite. This document reports NEW78 only.

The digital fixture assumes100MHz and observes CS/SCK/SI without an analog
device model or SO signal. Four normal words4000/4001/4002/4004 each produced
16rising SCK edges in MSB order,100clock setup/hold/CS gap and200clock SCK period.
Codes3/5/6/7 produced held refusal results and no CS-low interval. Result slots
held stable, ready stayed low during reset/cancel/disable. Five explicit new
requests were aborted after0/7/16/4/3rising edges by cancel/disable/reset; reset
deliberately destroys the transaction result/tag. No old request auto-replayed.
An intentional wrong pin-byte oracle caused actual native vsim exit4; normal
run exited0. The main independently reconstructed words/timing from saved pins.

Attempt01 failed before the suspended launcher resumed: Path objects could not
be serialized to the helper's JSON. Its truncated metadata is preserved; no
Job/PID accounting is invented. The original unattached Popen was cleaned by
the pinned helper, and process readback found no runner. Explicit repair
converted argv to strings; NEW02 was the first real compilation/simulation.
It exited0/no timeout with whole Job attached-before-resume/terminal/empty/closed.
Commands, tool binaries/versions, source snapshots, negative traces and exits
are in the operation evidence; no later source/evidence commit is claimed run.

These timings are digital engineering assumptions, not3.3V/electrical/settling
validation. A16edge abort may already affect analog gain and remains unknown.
No GPIO/serial completion is a gain measurement. Actual A0/A3 acquisition,
calibration/8levels/5% accuracy, local-overrange arbitration integration, pins,
CDC/RDC/timing closure and physical board remain unaccepted dependencies. Source
80 develops the separate priority seam; it cannot inherit this stage's pass.
No Vivado synthesis/route/build, clocksetter, pin assignment, board/SSH, actual
ADC, Root/planner or product control ran. Original100MHz/fullH12/all29 and all
taskbook error/age requirements remain. R04 is NOT PASSED.
