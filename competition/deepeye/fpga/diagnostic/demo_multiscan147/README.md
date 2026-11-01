# B147 demo multisample ingress

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-DEEPEYE-DEMO-MULTISCAN-INGRESS-20261101-147`.

Status: **SOURCE_ONLY / UNEXECUTED**. No compile, elaboration, ModelSim run,
Vivado build, board access or physical measurement was performed for this
source. No RAW/Rice frame count, byte count, board sample, deployed-141 result
or final timing result is claimed here. A alone chooses and performs any
physical integration.

- Route labels: `SOFTWARE_FIXTURE/offboard diagnostic source`; the focused
  TB is a not-yet-run pre-synthesis simulation, not a `SOFTWARE_FAKE_CSR`
  execution, board result, deployed-141 result, or production BOOT/ADC/motion/H12
  path.

## Contract and authority

- Human lock: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01-H15.
- Contract pin: `f5989cd5defce561f9ba98e6b18fc2682945f0a2`.
- Recomputed requirements SHA-256:
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
- Frozen design: `1011259415a0916054eb580687612580bc1e5f09`.
- Source head supplied by the B132 PR30 handoff:
  `faeee5f4c5fb1d1fc71a98889379c56ac7f28f09`.
- Actual worktree HEAD at source readiness: `025d27343adfd05a40e6db4075963c138d865d11`
  (a descendant of the selected handoff head; its added paths are non-RTL tools).
- Original29, both H12 paths, full 3D/UI, hidden truth, device-bounded causal
  observation, substantive online PC AI and final 100 MHz / 1% / 100 ms gates
  remain required. This diagnostic source does not implement, replace or claim
  any of those gates.

## Composition

`deepeye_demo_multiscan147.sv` adds only an ARM/config holder and a dynamic
descriptor adapter around unchanged code:

```text
12 externally supplied ordered raw lanes
  -> unchanged deepeye_aggregate12_candidate
  -> four channel blocks, three same-lane samples each
  -> unchanged deepeye_trace_block_uart_50mhz_candidate
       (payload_1us -> trace_payload_candidate -> one block_encoder
        -> wire_serializer -> 8N1 UART)
  -> tx at exactly 50 MHz / 1 Mbaud

rx_async -> unchanged deepeye_uart_rx -> up_valid/up_ready byte boundary
```

There is no second encoder, no new compressor, no fabricated ADC/BOOT/motion
path and no invented board register or pin. `tx` and `rx_async` are separate
logical directions. The focused TB loops `tx` to `rx_async` only inside
simulation.

The input accepts three native four-lane scans (12 records). It requires
ordered channels `0,1,2,3` in each scan, the original native sequence
progression, a common acquisition QPC across the four lanes, exact regular
positive QPC stride, one nonzero tag, and caller-supplied fresh/valid/not-held/
not-saturated/no-fault classification. Unsupported input is backpressured and
refused; it is not corrected or relabelled.

One initial ARM edge captures `session32`, `epoch8`, `base_frame_seq16`,
`origin_qpc63` and `tag32`. The live configuration inputs may change after that
edge and do not affect the batch. Four channel frames are emitted in order. A
successful frame retires only after its result handshake; errors, cancel and
disable do not retire and do not replay.

## Selected test vectors

The focused TB supplies these records (not an old fixture):

|Scan|Lane 0|Lane 1|Lane 2|Lane 3|
|---|---:|---:|---:|---:|
|0|1234|40000|65535|0|
|1|1234|40001|65534|65535|
|2|1234|40002|65533|1|

- Session `0x42a50031`, epoch `0x2d`, wire base sequence `0x1200`,
  tag `0x51`, origin QPC `9007199254740993`.
- Native first/last: `40/43`, `44/47`, `48/51`.
- Scan acquisition QPCs: `9007199254841000`, `9007199255041000`,
  `9007199255241000` (100 us + 7 ns from origin, then 200 us stride).
- Input quality is zero on every lane. It is an opaque input association only.
- Raw zero and one are valid samples and are checked as values, not as nulls.

The TB verifies four frame outcomes, wire sequence, session, first tick, native
first index, index stride 4, tick stride 200 us, count 3, `E=0`, valid/not-sat/
not-held/no-fault flags, CRC, sample values, `result_error`, and `result_bytes`.
It decodes either RAW or Rice according to the actual prefix and logs the
measured mode. A later run alone can establish the actual per-frame modes and
bytes.

The same focused group also checks: configuration immutability after ARM;
`base_frame_seq = 0xffff` refusal with zero bytes; a held input that is
backpressured and refused without an invented flag; and mid-frame cancel and
mid-frame disable with distinct abort causes, no success, no retirement and no
automatic replay.

## Quality and lineage

The accepted B77 aggregate stores the opaque `s_quality[7:0]` and requires it
to stay constant per channel across the three scans. The accepted TRACE
payload has no raw-quality field; the pinned B73/B77 payload adapter's
`blk_raw_quality` input is not encoded. Therefore this source makes no quality
adjustment and claims no wire transport of quality. Quality zero in the test is
not "missing"; the full raw quality byte and its mapping belong in the host
companion/source-association record.

The wire carries a relative uint32 microsecond tick (`100`) and a uint16
stride (`200`). It does not carry the uint63 origin, full acquisition/source
QPC, nanosecond remainder, native tag, fresh flag or opaque quality. Those
must stay in the externally supplied companion association. The adapter
preserves the origin while deriving the relative tick; it does not silently
rebind absolute time to a current clock.

## Files

- `deepeye_demo_multiscan147.sv`: ingress, dynamic descriptor adapter, UART RX
  byte boundary.
- `tb_deepeye_demo_multiscan147.sv`: one focused standalone TB group.
- `INTERFACE.md` and `INTERFACE.json`: exact proposed module boundary and
  rejection semantics.
- `SOURCE_PINS.json`: dependency and authored-file pins.
- `run_tb.do`: ModelSim completion/exit wrapper for the later single run.

## Compile order and later run

Use a fresh output directory outside this source directory. The following
uses a new directory under the worker's owned evidence area; the parent may
substitute its own fresh evidence path. With ModelSim on `PATH`:

```powershell
$ROOT = 'D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014'
$OUT = 'D:/pynq/CarlandFPGA/.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-77/worker147/run-source147-001'
New-Item -ItemType Directory -Force $OUT | Out-Null
Push-Location $OUT
vlib work147
vlog -sv -work work147 `
  "$ROOT/competition/deepeye/fpga/codec/deepeye_block_encoder.sv" `
  "$ROOT/competition/deepeye/fpga/codec/deepeye_trace_payload_candidate.sv" `
  "$ROOT/competition/deepeye/fpga/transport/deepeye_crc16_byte.sv" `
  "$ROOT/competition/deepeye/fpga/transport/deepeye_wire_serializer.sv" `
  "$ROOT/competition/deepeye/fpga/transport/deepeye_uart_tx.sv" `
  "$ROOT/competition/deepeye/fpga/transport/deepeye_uart_rx.sv" `
  "$ROOT/competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_payload_1us_candidate.sv" `
  "$ROOT/competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_uart_50mhz_candidate.sv" `
  "$ROOT/competition/deepeye/fpga/diagnostic/offboard_aggregate77/deepeye_aggregate12_candidate.sv" `
  "$ROOT/competition/deepeye/fpga/diagnostic/demo_multiscan147/deepeye_demo_multiscan147.sv" `
  "$ROOT/competition/deepeye/fpga/diagnostic/demo_multiscan147/tb_deepeye_demo_multiscan147.sv"
vsim -c -voptargs=+acc -onfinish stop `
  -l demo_multiscan147_modelsim.log `
  work147.tb_deepeye_demo_multiscan147 `
  +bytefile=demo_multiscan147_uart_bytes.txt `
  +logfile=demo_multiscan147_tb.log `
  -do "do $ROOT/competition/deepeye/fpga/diagnostic/demo_multiscan147/run_tb.do"
$runExit = $LASTEXITCODE
Pop-Location
exit $runExit
```

`run_tb.do` exits 0 only when the TB's `completed` flag is one. A TB fatal
(including a bound timeout) exits 3; a completed run without the success flag
exits 4. On pass, the byte file contains one `CAPTURE <index> <hex>` line per
actually observed `up_valid/up_ready` byte, and the log contains the decoded
frame records and `TEST_PASS`. The TB is bounded by handshake-specific limits
and a 500,000-clock global timeout.

## Honest gaps for A

This is a pure-data RTL source boundary, not a board or host integration:

- No AXI/AXI-Stream adapter, address map, register offsets, DMA or host driver
  is defined here. A chooses any build/integration.
- No Host103 `TraceSequence`/pure-staging adapter or A-owned producer envelope
  is invented. The implemented result is local frame metadata plus raw UART
  bytes; the host must perform any later schema mapping.
- No pin assignment, PYNQ overlay, bitstream, clock/reset CDC constraints,
  metastability proof, UART electrical qualification or physical FIFO is
  provided. The RX byte boundary is one ready/valid slot; an integrator must
  add buffering and consume `up_ready` or account for `up_overrun`.
- No A-owned exporter/custody schema was announced to this worker, so none is
  invented. The companion/source-association bytes are opaque host-side input
  and are not interpreted or authenticated by this RTL.
- The pinned UART core exposes only its documented digital behavior. No
  hardware-hung-MMIO, baud-tolerance or board-service guarantee is made.
- The 50 MHz diagnostic clock and 1 Mbaud UART are not the final 100 MHz
  timing point. No STA, 1% error bound or 100 ms result is claimed.
- No physical BOOT, ADC, motion, H12, board or deployed-141 evidence is created
  or replaced. The TB is simulation source only and was not run by this worker.
