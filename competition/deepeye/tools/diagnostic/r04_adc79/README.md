# R04 independent ADC pair seam, main81

Task DEEPEYE-IMPLEMENTATION-20261014/v1; H01-H15/revision1 SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
A alone board. ActualADC/calibration/settling/gain measurement unavailable;
R04/all formal gates remain UNSATISFIED. This pure file evaluator opens no
physical driver, callback, network, clock, Root source, planner or command path.

The default production_entry returns INPUT_UNAVAILABLE with no ratio/command.
The explicit SYNTHETIC_FIXTURE entry accepts plain bounded JSON text only,
max65536input bytes and16total records. Floats/NaN/duplicate keys/custom objects,
unknown root/record fields, bool-as-int, uint63 overflow and invalid timestamps
are refused. Complete legal missing samples/receipt/calibration/currentQPC
return unavailable. Every supplied independently decidable duplicate, context,
clock, capacity and order contradiction is checked before missing returns.

Schema deepeye.r04_adc_pair.v1 requires schema/mode/calibration/digital_receipt/
baseline_before/after/now_qpc_ns. All times are original uint63 nanoseconds,
qpc_hz must explicitly be1000000000 and clock IDs must match. The evaluator
creates no timestamp/origin. A source is eligible only at original now-source
<=100000000ns; acquisition freshness alone is insufficient. Future and regressed
acquisitions are refused. Each baseline record precedes the original digital
completion; after records follow it. That supplied receipt is a digital fact,
never authentication, observed analog settling or actual gain application.

Each original record carries sample_id/acquisition_qpc/source_qpc/context,
channel_indices=[0,1,2,3],four raw uint16 channels,opaque uint8 quality and a
separate explicit boolean quality_eligible. No arbitrary quality-bit semantics
or uint12 clipping is invented. Context requires uint63 tag/epoch and original
text boot_id/source_id/clock_id; all supplied bounded additional full context
fields, strings and large integers are retained and compared exactly. JSON
matching, tags and hashes cannot authenticate a Root or physical source.

Explicit synthetic calibration carries an ID, full_scale_code and A0/A3 offsets.
No real full scale or offset is assumed. A0 is the post-PGA channel, A3 the
independent pre-PGA input. Raw saturation/ineligible quality/nonpositive
corrected denominator cannot make a ratio. The20%-80% goal applies only to raw
A0 AFTER adjustment, relative to the supplied full scale. A3 and the baseline
may legitimately lie below20% when gain is needed. Exact corrected-code integer
numerator/denominator is returned; no command gain substitutes for measurement.
The deterministic selection is last baseline/first after; all input records
remain in the canonical ledger. The entire original canonical input, serialized
byte length and SHA are retained/counted, including context/calibration/receipt.

NEW81 preserved original79 unexecuted source and repaired context text retention,
original-now freshness, opaque-quality classification, missing-evidence order
and the misplaced range target. Eighteen NEW software controls passed; four
NEW CLI processes produced actual exits0/2/3/3 (synthetic ratio/refusal/stale/
production unavailable). Each bounded Job was terminal/empty/closed. The main
checked actual serialized input hashes, raw16/QPC>2^53/full context preservation
and the exact example32768/8192 ratio. No old79 suite was run; source execution
is pinned to exact precommit snapshots, never to a later commit.

cli_adc_pair.py --input fixture.json --output result.json writes exclusively;
exit0 means SYNTHETIC_RATIO_AVAILABLE only, exit2 REFUSED, exit3 unavailable.
--production remains unavailable. measured_gain_actual=null,
physical_acceptance=false and commands_emitted=false in every result. No physical
voltage,8levels/5%,live SPI/ADC or real Root ACK is supplied. Integrating this seam
with an original A-owned acquisition/calibration owner needs a new operation.
