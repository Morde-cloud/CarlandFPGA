# G05 pure SET_TARGET mapper

Assigned slice `B-G05-GUARD-MAPPER-20261026-59-v1` implements only
`deepeye_g05_command_map`. Main owns math decisions, integration, and acceptance.
This module has no clock, session, ENABLE, STOP, BOOT, AXI, capture engine, or
motion authority. Outputs encode target references; A owns world acceleration
and actual angular speed. No synthesis, timing, board, or formal G05 result is
claimed by its local simulation.

The unchanged H01-H15 revision 1 requirements hash is
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, from contract
commit `f5989cd5defce561f9ba98e6b18fc2682945f0a2`; frozen design is
`1011259415a0916054eb580687612580bc1e5f09`. Both PC_DIRECT and FPGA-output paths
remain required. A's enum input SHA256 is
`a52f3631d94d396c7da769f82a09e70d55c765b0c2651de27476e644c486573e`.

Profiles 1/2 select FAST9600/STRESS300. The 42-entry ROM holds
`floor((speed_code*90000/(80*pi))^2)` or the same expression with divisor
10000, for codes 0 through 20. The generator uses exact rational alternating
series and Machin's identity to bound pi outward at 100 decimal places; every
row's lower and upper squared-bound floors must agree. The JSON records the
bounds, both floors, input/source hashes, and proof method. It is regenerated
only when absent; `--check` verifies existing output bytes without replacement.

Reject bits accumulate independently: bit0 unknown numeric profile; bit1 either
signed axis outside [-15000,15000], speed above20, or nonzero axes at zero speed;
bit2 zero TTL or exceeding the selected valid profile's 3000/12000 ms cap; bit3
the 64-bit sum of squared axes exceeds the ROM limit. Unsupported profile/code
has diagnostic limit0. An unsupported profile with positive TTL has no selected
profile cap, and remains rejected by bit0. Thus unsupported selectors may also
assert bit3 when the axes are nonzero. Signed extension precedes multiplication,
so even (-32768,-32768) reports sum2147483648 without overflow.

Only zero rejection bits permit period2000000, yaw/pitch high
`10000+16*(q+15000)`, speed high `50000+1000*code`, TTL ticks `ttl_ms*100000`.
On rejection all five mapping outputs are zero, while sum/limit remain
diagnostic. Ordinary four-state comparisons and an exact `case` are used: X/Z
may propagate to diagnostics/rejection/legality, but cannot grant legal=1 and
the procedural legal branch leaves mapping outputs zero. No simulation-only
X detector is present in hardware.

The new bench observes public ports only and compares all nine outputs to a
separate Python Decimal Gauss-Legendre oracle at 140 and 180 digits. It never
imports the DUT constants. Cases cover all42 profile/codes, TTL0/1/max/max+1,
axis and diagonal curvature boundaries, mixed points, per-axis and combined
range faces, signed extremes, zero-speed restrictions and invalid selectors.
Eighteen X/Z controls check no grant and zero mapping outputs. A second simulator
run deliberately changes expected TTL bit32; its required nonzero exit proves
the comparison/failure path is exercised. ModelSim 10.7 treats `$fatal` as a
finish event, so Tcl checks the bench's completion status at the break and
exits0 only after all checks finish. This bench status is not a DUT-internal
probe. Transcripts and the unique PASS marker are independently checked too.

Run from the repository with its existing Python (example first attempt):

```powershell
& D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014/competition/deepeye/fpga/diagnostic/g05_capture/mapper/run_mapper.py --attempt attempt-01
```

The runner is fixed to these assigned mapper source and private evidence roots;
attempt names must be new. It invokes only this generator/oracle and the existing
`D:/modelsim1/win64` vlib/vlog/vsim. It snapshots sources and inputs, records
commands/PIDs/exits/version output, raw stdout/stderr and simulator transcripts.
Each command launches suspended into a Win32 job before resuming; a real job
accounting query must observe zero active processes before a command succeeds.
Timeouts/ownership failures remain failures after cleanup. The existing read-only
`fpga_mesh/windows_job.py` helper is hash-pinned at
`3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3` and copied into
each evidence attempt; the runner records its environment's inherited ModelSim
configuration path, without changing that installation or printing credentials.
All run-specific generated vectors, work libraries and logs live only under
`.local/deployment/node-b/evidence/g05-capture-20261026-59/mapper/`.
