# Physical integration remains a separate gate

This note records the main's design review context, not a simulation result.
Candidate 06 transports one opaque bus by a request/acknowledgement handshake.
The custom module is not the AMD XPM primitive and inherits no vendor waiver.

AMD's [7-series XPM_CDC_HANDSHAKE reference](https://docs.amd.com/r/2022.2-English/ug953-vivado-7series-libraries/XPM_CDC_HANDSHAKE)
describes destination capture acknowledgement and completion of the source
handshake before another transfer. It also identifies a CDC-15 warning for its
controlled bus. A warning class alone is not proof that this custom path is safe.

AMD's [CE-controlled CDC guidance](https://docs.amd.com/r/2024.1-English/ug906-vivado-design-analysis/CE-Controlled-CDC)
requires the designer to constrain data-crossing latency. Its
[bus-skew handshake example](https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/set_bus_skew-Example-One)
relates the bus skew bound to control synchronization stages and includes a
separate maximum data delay. These are structural principles. Example numeric
constraints do not establish a bound for the proposed B module.

For this candidate, actual integration must name source/destination clocks and
reset nets; prove that both reset inputs reach the shared asynchronous flush;
verify reset pulse width and synchronized release; identify every synchronizer
and held-data launch/capture register; derive delay/skew limits from the actual
control pipeline and clock bounds; verify that exceptions do not mask those
limits; inspect synthesis, placement, CDC/RDC and timing reports. No blanket
asynchronous clock exception is supplied here. Simulation cannot establish
metastability MTBF, physical reset recovery/removal or routed timing.

The opaque mailbox does not itself make yaw/pitch/speed capture simultaneous,
authenticate a source/session, reject old motion requests, enforce STOP timing,
detect a stopped clock or assign public register fields. Those properties need
the existing B capture model, A authority and their reviewed RTL integration.
WIDTH=256 tests alone do not bind the earlier eight-word software fixture to
public register addresses, endian order or access semantics.

H01–H15 DEEPEYE-HUMAN-LOCK-20261014/r1 requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
design1011259415a0916054eb580687612580bc1e5f09 unchanged. A alone hardware.
