# Independent block encoder RTL evidence

Operation B-DEEPEYE-BLOCK-ENCODER-20261018-08, task DEEPEYE-IMPLEMENTATION-20261014/v1.
Main accepts only the isolated single-clock digital RTL candidate. B01/B03 and
the overall B responsibilities remain incomplete. No A/C source or public ABI
is changed. Physical board remains A-only.

Final RTL SHA256 870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5.
`main_acceptance.json` binds final RTL, runner, independent monitor/checker,
raw ports, portable reproduction and the historical rejected source.

- Corrected regression:828/828 cases,7447 checks, max2084 clocks from last
  sample to metadata; expected bytes derive from the pinned Python reference.
- Independent public-port review:1559 transactions,1493 successes,26 rejected
  inputs,40 aborted blocks and40 fresh-block recoveries;69312 successful-block
  samples and90653 complete payload bytes. All N1..128 and E0/1/2/4/8, observed
  selected k0..14,52 forced quotient17/18/30/31 cases.3184107 simulated cycles
  and81264 stalled-output stability checks. Oracle imports no worker/golden code.
- Six-file flat export in a directory with spaces reproduced828 cases. Existing
  output and input-alias output attempts exit2; all original bytes unchanged.
-35 corrupted port logs and4 defective RTL variants were rejected. Mutants are
  derived from the preliminary32-bit fix (`diagnostic-width32.sv`); final RTL
  differs only comments and has byte-identical positive port trace. The result
  records this exact boundary. Deterministic corrupted copies remain private;
  their hashes and generator are supplied, along with original port log.

BE01: original17-bit writer indexed beyond its width for selected unary runs
above17. Main reproduced unknown valid output on128 samples (64zero then64nine,
E0/k0/quotient18), although the worker's original776 tests passed. Original source
and failed main logs are retained. The corrected32-bit register makes every
legal up-to31-zero run defined. This was an actual defect correction, not a
claim that golden software or public TRACE layout changed.

Reproduce from repository root (Python standard library, actual ModelSim10.7):

```text
python -B -X utf8 competition/deepeye/evidence/codec/block-encoder-20261018-08/main/main_encoder_review.py --rtl competition/deepeye/fpga/codec/deepeye_block_encoder.sv --tb competition/deepeye/evidence/codec/block-encoder-20261018-08/main/main_encoder_port_tb.sv --modelsim-home PATH_TO_MODELSIM_ROOT --output NEW_DIRECTORY
python -B -X utf8 competition/deepeye/tools/codec/run_block_encoder.py --modelsim-home PATH_TO_MODELSIM_WIN64 --rtl competition/deepeye/fpga/codec/deepeye_block_encoder.sv --tb competition/deepeye/tests/codec/rtl/tb_block_encoder.sv --golden competition/deepeye/golden/codec/codec_reference.py --output ANOTHER_NEW_DIRECTORY
```

Raw `.log` and ModelSim `transcript` bytes are copied unchanged into `.txt`
aliases to bypass repository ignores; `../raw_log_map.json` records the mapping.
Commands retain their actual original paths. Source/fixture inputs are provided.
Original worker artifact hashes include43 files including local compiled
libraries; main checked all43. Compiled vendor libraries remain local; they are
not a synthesized FPGA design. Historical attempts are not overwritten.

All statistics above are digital simulation/software evidence. No synthesis,
implementation/timing, ADC/physical IO, bandwidth, board or full game/AI claim.
H01-H15 contract f5989cd5defce561f9ba98e6b18fc2682945f0a2,
requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804,
frozen design1011259415a0916054eb580687612580bc1e5f09 unchanged.
