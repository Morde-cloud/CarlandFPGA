# Remainder reconstruction candidate

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-ENCODER-REMAINDER-CANDIDATE-20261024-36-v1`, operation
`B-DEEPEYE-ENCODER-REMAINDER-20261024-36`. Quality main
`01a13b55-095b-7461-8dd5-5476a130bd82` owns design, evaluation and acceptance.
Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, H01–H15, pinned at
`f5989cd5defce561f9ba98e6b18fc2682945f0a2`; canonical requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Frozen design `1011259415a0916054eb580687612580bc1e5f09` is preserved.

This is a separate candidate module with the original public port list.
It implements exactly the quality main's reconstruction identity. The original
core, stream/wrapper35, reference, shared schemas and ABI are unchanged.
No production adoption, resource reduction or synthesized timing improvement
is asserted. A alone operates physical hardware.

Let `n = x-p+E`, `d = 2E+1`, `a = abs(n)`. The unchanged restoring divider
returns `div_quot = floor(a/d)` and `r_abs = a % d`. For a negative numerator
with nonzero remainder, Euclidean remainder is `d-r_abs`; otherwise it is
`r_abs`. Hence `n = q*d+r_euclid`, where `q=floor(n/d)`, and therefore
`p+q*d = x+E-r_euclid`. The unchanged 25-bit signed clamp produces the same
predictor. Quotient rounding, ZigZag, Rice/RAW choice, metadata, RAM access,
divider and all FSM transitions/cycles are inherited unchanged.

The new 16-bit `cur_sample` register captures only an accepted, correctly
framed nonfirst sample in `ST_LOAD`, beside `cur_idx` and `div_neg/div_mag`.
It is cleared synchronously under the existing `rst || cancel` priority and
holds otherwise. Reconstruction never reads live `s_data` or sample RAM.
The removed multiplier is replaced with signed 25-bit arithmetic on explicitly
zero-extended `cur_sample`, `E` and a 6-bit Euclidean remainder.

For uint16 `x,p`, `n` lies in `[E-65535,E+65535]`, fitting signed 18 bits;
`abs(n) <= 65543` fits 17 bits. Allowed `E` is exactly `{0,1,2,4,8}`,
`d` is 1 through 17, and the remainder is 0 through 16. Reconstruction before
clamping lies in `[x-E,x+E]`, contained in `[-8,65543]`, safely within signed
25 bits. Existing `q_bits` and `z_calc` are unchanged.

The author runner enumerates every reachable numerator for all five E values
and tests distinct feasible predictor endpoints/midpoint with valid samples.
It independently checks integer quotient rounding, the identity, signed
25-bit representation and the original clamp. This is not an enumeration of
all uint16 sample/predictor pairs. Actual counts are saved in `arithmetic.json`.

ModelSim compares the two modules at public ports every post-reset cycle,
masking metadata/data only when their valid signals are low. Golden completed
transactions include counts 1/2/127/128, extrema, positive/negative transitions,
negative divisible/nonzero remainders, deterministic random blocks, ramps,
RAW/Rice, producer gaps, all four interface stalls, malformed configuration
and sample framing. Reset and cancel each interrupt 12 handshake-derived
stages, followed by an independently specified two-byte recovery fixture.
There are no hierarchical DUT assertions. A changing unaccepted `s_data`
checks that reconstruction uses the captured sample.

Payload and metadata fixtures explicitly reuse published
`golden/codec/codec_reference.py`, SHA256
`2e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5`.
This shared reference and the original-core miter may share bugs; the main
must independently review. No main oracle is imported.

Run from the existing worktree, with a fresh output directory inside author:

```powershell
& D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -B -X utf8 competition/deepeye/tools/codec/run_encoder_remainder_candidate.py --modelsim-home D:/modelsim1/win64 --output competition/deepeye/evidence/codec/encoder-remainder-20261024-36/author/attempt-01 --thread-id 01a16a34-b419-7942-9a7b-2b033142446b --turn-id 01a16a34-b53d-7cf2-b12a-3b044fc08392
```

The runner refuses existing output directories, snapshots inputs, records
argument arrays, versions, raw stdout/stderr, exit codes and artifact hashes.
Failed attempts must remain intact; at most three meaningful repairs are
authorized. Results are author-only bounded software/RTL evidence. All 29
formal gates, B01/B03/B06/R03, synthesis/implementation, timing closure,
CDC, physical board, system and final acceptance remain `not_run`.
