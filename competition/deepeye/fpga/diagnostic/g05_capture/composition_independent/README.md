# Independent real G05 composition controls

Task DEEPEYE-IMPLEMENTATION-20261014/v1; work
B-G05-REAL-COMPOSITION-REVIEW-20261026-59-v1. Main retains acceptance.
H01-H15/revision1 hash
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, contract
f5989cd5defce561f9ba98e6b18fc2682945f0a2 and frozen design
1011259415a0916054eb580687612580bc1e5f09 remain unchanged.

The runner hash-pins all six finalized production source/header files and uses
the real AXI, mapper, engine, atomic PWM and coherent capture. There is no stub,
production parameter change, hierarchical DUT oracle or exhaustion injection.
The fixed PWM period remains2000000 clocks at100MHz. Testbench access is through
the AXI and six external ports; Tcl reads only the bench completion status.

Each case runs separately with a wall limit240seconds and a simulation watchdog
of20million clocks. Directed cases cover identity/staging, first full capture,
continuous sequence/latch/ACK with a held R response, exact and changed command
duplicates, reset/new identity, atomic pending update, pending old-TTL expiry,
same-edge STOP/expiry, profile/combined-curvature/signed-min rejection, missing,
stuck-high, wrong high/period, cross-frame, skew3, distinct-code wrong wiring and
valid skew2/high2 inputs. Counter exhaustion is not claimed from a short run.

External stimuli are explicit simulation fixtures. Normal pins are separately
scheduled copies of public PWM outputs. Fault/tolerance pins use independent
waveform schedules based on the first public output edge, fixed period, known
request mapping and selected skew/high offsets. These are not real board or
physical-skew observations. CSV files retain raw output/input transitions and
every AXI request response, public clock ticks and assertion failures.

The runner requires a unique complete line-anchored PASS and STATS, matching case
and assertion counts, a matching raw END record, exit0 and whole owned Win32 job
terminal proof. Targeted parser negatives include substring markers, duplicate
stats/PASS, inconsistent counts, trailing text, wrong case and fatal-after-PASS.
It also compiles a separate private mutant with speed high base50001 instead of
50000. The same public-port width oracle must detect actual70001 versus70000.
Only the mutant snapshot changes; production files are rehashed afterward.

Run the new `run_composition.py --attempt attempt-NN`; existing attempts are never
reused. All output, source snapshots, versions, commands, PID/job accounting,
stdout/stderr/transcripts and raw CSVs stay under the separately assigned
`composition-independent/` private evidence directory. The already completed
build-prep owned_process helper is reused read-only and hash-pinned. Nothing here
launches Vivado, changes production sources, accesses a board or claims formal
G05/fullH12/B06 acceptance. First failures/timeouts remain evidence; an author
fixture repair requires a new explicit attempt and recorded explanation.
