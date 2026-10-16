# B snapshot CDC candidate 06 — main design, 2026-10-17

Task DEEPEYE-IMPLEMENTATION-20261014/v1. Work B-SNAPSHOT-CDC-CANDIDATE-20261017-06-v1.
Contract DEEPEYE-HUMAN-LOCK-20261014/r1, H01–H15, requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
Frozen design 1011259415a0916054eb580687612580bc1e5f09.
B product input 860f6f850b19afe8240ea49f66c0acbd879c1ff7.
A dependency 66aa291d7f01cc3cfefb8c30c4e8ad3aec6547bd; public registers not frozen.

This is a proposed generic opaque snapshot transport. It defines no public
register address/bit field, motion authorization, source identity, clock
liveness, timeout, physical I/O or board enable. No existing module is changed.
All H01–H15 remain mandatory. A alone freezes shared ABI and operates hardware.

## Module contract

Synthesizable SystemVerilog module deepeye_snapshot_mailbox, integer WIDTH=256
(legal 1..1024). Ports src_clk, src_reset_n, src_valid, src_ready,
src_data[WIDTH-1:0], src_online, dst_clk, dst_reset_n, dst_valid, dst_ready,
dst_data[WIDTH-1:0], dst_online. Inputs/outputs obvious from names. No other
clock domains or unbounded storage. No vendor simulation dependency.

One outstanding transfer maximum. Source accepts only at src rising edge
with src_valid && src_ready. It captures the entire opaque bus into data_hold
and toggles req. Hold data unchanged until destination consumption is
acknowledged back. Destination synchronizes req through at least two flops,
then captures data_hold into dst_data on a later destination edge when the
request differs from local ack and no valid output is pending. It asserts
dst_valid. Capture and consumption occur on separate destination edges.
Only dst_valid && dst_ready at a destination rising edge consumes and toggles
ack to the pending request value. Ack passes through two source flops.
The source cannot overwrite held data until that acknowledgement returns.
While dst_valid && !dst_ready, dst_valid and dst_data are stable.
dst_data after consumption may retain its last value with dst_valid=0.

Both reset inputs are part of ONE shared flush network:
common_reset_n = src_reset_n & dst_reset_n. Either low asynchronously clears
both halves, all req/ack/valid/payload/arming/up and synchronization state,
including when one or both clocks are stopped. Deassert reset synchronously
inside each clock domain using its own two-flop release synchronizer.
State uses the local synchronized reset, not an unsynchronized reset release.
Use ASYNC_REG attributes for actual synchronizer flops. Local up asserts only
after local release; synchronize peer up. src_online/dst_online indicate
local reset release plus peer up observed, NOT measured clock liveness.

After EVERY reset, source ready remains low until src_valid==0 is observed
on a source rising edge while src_online. Then arm until next reset. A valid
held high through reset is not automatically replayed. This deliberately
requires producer reset recovery to present low before a fresh offer. It is
not an ungated AXI-stream interface. The module cannot know whether an opaque
producer offered authentic/new data after that low; authority remains external.
During normal armed operation standard stable-until-accepted source behavior
allows consecutive offers without requiring a low between them.

Reset discards pending snapshots; preserve explicit accepted/delivered/
reset-discarded accounting in tests. No implicit retry. A stopped destination
clock may allow one outstanding source capture after prior online state, then
backpressures indefinitely. No wall-clock recovery/timeout is promised.
No transaction preservation is promised across independent reset lines:
both reset sources MUST reach the shared reset network in actual integration.
Inputs must meet their local domain timing; arbitrary analog glitches, narrow
reset pulses and metastability are not modeled by digital RTL simulation.

## Physical integration gate

The held multi-bit bus is a bundled-data path, not independent bit synchronizers.
Stable data plus synchronized handshake supplies a digital settling interval;
physical correctness still requires reviewed topology, bus delay/skew bounds,
reset pulse requirements, recovery/removal and CDC/RDC reports after actual
clock/reset integration. No blanket false-path XDC is authorized. No MTBF,
synthesis, implementation, timing closure, B05/R03 or board PASS follows from
these fixtures. Candidate follows the handshake/reset principles described by:
https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Clock-Domain-Crossing
https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Multi-Bit-CDC
https://docs.amd.com/r/2022.1-English/ug949-vivado-design-methodology/Synchronous-Reset-vs.-Asynchronous-Reset
These references are design guidance, not certification of this custom module.

## Execution and evidence

ModelSim SE-64 10.7 is available at D:/modelsim1/win64/{vlib,vlog,vsim}.exe.
Main has actually compiled and simulated tiny positive/negative SV fixtures.
Use subprocess argument arrays, a fresh caller-specified output directory
(refuse pre-existing output before modifying anything), separate work library,
bounded tool timeout, explicit source/TB paths, exact raw stdout/stderr and argv,
tool/source hashes and exit codes. No GUI, service/config changes or downloads.

IMPORTANT discovered runner traps: inline '-do commands' is NOT a macro;
onerror/onbreak are ignored there. Use a real .do FILE, with
onerror {quit -force -code 8} and onbreak {quit -force -code 7}.
Use -voptargs=+acc if examining variables. A one-bit signal examined with
decimal radix is signed -1 at logic1. Tcl puts has no '# ' prefix while HDL
$display does. A zero process exit alone is insufficient: require exact
TB completion marker, no ** Error/** Fatal transcript, valid ledger and
expected counts. Main's corrected macro negative control exits7 at $fatal.
Preserve all failures; never overwrite logs to make a rerun look original.

Create directed and fixed-seed randomized TB cases, actual at least WIDTH=1,
32,256 and1024 elaborations; unrelated clock ratios/phases; destination stalls;
source/destination stopped then resumed; startup skew; source-only and
destination-only resets when idle, request in flight, valid pending or stalled;
reset with clock stopped; held-high valid across reset and explicit low rearm.
Use a bounded external-port scoreboard and explicit reset-drop count. Emit
machine-readable events/summary including accepted and delivered data,
reset flush events and case names. Test source/destination handshakes only,
not internal req/ack as the acceptance oracle. Check stale/phantom/duplicate,
torn data, ordering, payload stability and outstanding<=1. Watchdog timeout
must fail, not pass. Use unique source payload patterns and directed low-width
tests where uniqueness cannot be assumed. A separate main TB will review this.
Do not claim analog metastability testing. Do not alter any historical files.

Report actual status, commands/log hashes and limitations to parent. Do not
spawn children, create threads/leases, use network, commit/push or send messages.
Use [需桌面回合] / [需本人操作] only for concrete blockers with evidence. No
presence reports. Preserve resident controller/queues/credentials/services.
