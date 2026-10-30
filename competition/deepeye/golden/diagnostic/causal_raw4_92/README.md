# B92 causal raw4 fixture-to-UART diagnostic

This directory contains regression checks for the NEW executable B92 slice. The
transport fixture is `MODELLED_SHAPES_FROM_PINNED_PUBLIC_CONTRACTS`: it is not
the unavailable A privacy-whitelisted 20 records, not a Root/admission/BOOT
capture, and not a physical ADC measurement.

The implementation reuses the unchanged B74 synthetic top, raw scan capture,
lane stream, one payload/TRACE encoder, serializer and UART. It adds only a new
bench. The 50 MHz clock and 5 Mbaud fixture settings are accelerated digital
parameters, not physical timing acceptance. Invalid C3 lanes occupy the capture
word with local padding zero but carry `valid=false`; the quality-only frame
must contain zero code/anchor bytes and decode to `None`. A valid C3 zero is a
real zero value and must decode to `0`.

## Fixture shape

- 20 ADC ticks at 0..190 ms in 10 ms steps.
- EM acquisitions at 0, 50, 100 and 150 ms; other EM lanes are held.
- C3 is null for records 0..8 and valid zero for records 9..19.
- Global quality values are 7, 15, 1799 and 1807.
- Expected lanes: 80 total, 9 null, 11 valid C3 zero, 23 fresh valid and 48
  held valid.
- Main reference wire size is 3038 bytes. It is an expectation only; the runner
  records and explains the measured bytes without forcing a match.

Every frame uses the existing singleton E0 fallback with count 1 and zero
strides because the mixed null/held batch is not eligible for the B77
fresh-only uniform-quality triplet path. All valid points are mathematically
stale at the supplied evaluation time. `current_source_eligible` remains false;
actual Root, native EM receipt, admission, BOOT, physical capture and action
evidence remain unavailable.

## Commands

Run pure checks:

```powershell
& D:\pynq\CarlandFPGA\.local\venv\Scripts\python.exe -B -m unittest -v competition\deepeye\golden\diagnostic\causal_raw4_92\test_raw4_92.py
```

Materialize the labelled fixture and its private source-shape validation file:

```powershell
& D:\pynq\CarlandFPGA\.local\venv\Scripts\python.exe -B competition\deepeye\tools\diagnostic\causal_raw4_92\prepare_fixture92.py --out <new-directory>
```

Run one fresh bounded whole-Job ModelSim evidence attempt:

```powershell
& D:\pynq\CarlandFPGA\.local\venv\Scripts\python.exe -B competition\deepeye\tools\diagnostic\causal_raw4_92\run_raw4_92.py --out <new-evidence-directory>
```

The runner verifies the pinned H01-H15 requirements hash, exact source before
and after, suspended launch and Job attachment before resume, per-command and
whole-Job limits, finite cycle completion, UART-versus-serializer bytes, real
strict decoder output, cancel partial refusal, and every negative control. It
counts each mandatory companion byte as well as all UART bytes. It does not
accept a public 150 B, 8 s, compression-ratio or 100 ms gate from UART
measurements alone.

This bounded fixture result cannot establish full H12, all 29 requirements,
physical 100 MHz timing, board behavior, current source freshness or production
readiness. Production remains closed and no source is eligible without a new
qualified input operation.
