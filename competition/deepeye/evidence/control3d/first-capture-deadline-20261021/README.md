# First-capture deadline candidate — operation18

This same-clock monitor observes the first record during E0+1 through E0+N inclusive. Reset/cancel clears all state; WAIT plus start rejects without renewal; zero-budget requests reject even from a terminal state. Same-edge start/observed does not complete. A last-edge pre-edge observation wins over expiry. Late observations cannot revive a terminal result.

The literal B15 public-port fixture verifies N3 completion at row7 and N2 expiry at row6, quiet input expiry, retained records under backpressure, and the pre-handshake/post-fault distinction. It adds no product STOP/PWM wiring or public ABI.

Main froze its absolute-edge oracle, 6618 scenarios/132010 standalone edges, 7 scenarios/112 composition edges and expected values before author dispatch. Exact source `860010695ef248467e518605dbecf0482e9a2e6b9a1f0b9d30c6e3e730047fae` passes all of them. Four independently compiled RTL mutations produce numeric public-port mismatches: 103 off-by-one, 230 ignored-cancel, 33 late-revival, 43 renewal. All compiler/simulator processes exit0; the oracle fails as expected. This is distinct from the author's 3715 scenarios/916438 assertions and twelve compiled mutant runs.

Main rejected 20 parser misaccept fixtures (9 normal/guard, 11 mutant), saved the original source, waited for actual terminal release, and repaired the runner. All61 independent parser expectations now match.33 unit methods and33 minimal portable methods pass;23 original methods are unchanged. The original incomplete/unmatched mutant accepting fixture is now a rejection;9 additional regression methods were added. Genuine normal/guard logs and all21 original final author simulation cases remain accepted. Three fresh selected cases exercise fixed source snapshot compilation. The `author/` report and candidate document describe the original author results; this README and `main/ACCEPTANCE.json` describe the final reviewed runner.

The final parser requires exact framing, ordered unique RUN/SCENARIO/SUMMARY/FINISH, positive required groups and consistent counts. Mutant qualification requires complete numeric public-port mismatches, matching scenario failures/summary/own-fatal and no X or load-error substitution. CLI empty/unknown/duplicate selections fail before creating a run. ModelSim10.7's actual `$fatal` exit0 is retained and qualified by exact guard diagnostics. Commands combine stdout/stderr in author runner logs; main independent runs preserve separate streams.

Reproduce from repository root:

```powershell
python -B competition/deepeye/tests/control/test_first_capture_deadline_runner.py -v
python -B competition/deepeye/tools/control3d/main_verify_first_capture_deadline.py --root . --out <new-directory>
python -B competition/deepeye/tools/control3d/run_first_capture_deadline.py --source-root . --run-root <another-new-directory>
```

ModelSim defaults to `D:/modelsim1/win64`; pass the author runner's `--modelsim-dir` for another installation. Main verifier currently uses that same explicit local path. Frozen vectors and TBs are in `main/frozen`; each real main run has COMMANDS/RESULT/INPUTS and raw stdout/stderr/transcript. Author387 indexed artifacts plus original reports, preflight failures and source snapshots are retained. Main real tests first ran against copied RTL while author closeout continued; final terminal source hashes match. Main took over runner/test only after actual completed/nonstale release. Main authored the runner repair, so its new runner tests are not claimed as a separate implementer's review.

All 5094 existing tracked files, old08–17 evidence and protected codec bytes remain unchanged. New synthesis/implementation are blocked/not_run without Vivado. Width32 tests are bounded prefixes. No physicalTTL, source/freshness, clock/BOOT, TRACE/register/HWH, ENABLE, CDC/RDC or motion authority is granted. All29/G05/B06/R03/board/system remainnot_run; only A operates hardware. The reviewed old A OOC applies to the original three RTL files, not this module.

DEEPEYE-IMPLEMENTATION-20261014/v1; DEEPEYE-HUMAN-LOCK-20261014/revision1 H01–H15 requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, pin `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, design `1011259415a0916054eb580687612580bc1e5f09` remain fixed. Full3D/UI/solid collision/free camera/layout/equal gates/full passage/hidden truth/causal sensing/substantive online3D PC AI and both H12 chains remain mandatory.
