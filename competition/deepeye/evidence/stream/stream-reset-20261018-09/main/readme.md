# Operation09 independent stream/reset evidence

Main accepts only a two-slot internal digital stream candidate. B01/B03, public
TRACE/register/BOOT/source-clock bindings and full hardware/system remain open.
The core is unchanged at SHA256870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5.

`MAIN_ACCEPTANCE.json` binds exact final sources and tests. Independent actual
ports:374 admissions,290 successful outputs,31 errors,53 flush-aborts;14011
accepted samples,13100 observed payload bytes;540297 cycles and25377 stall
stability checks.22 config/retirement and26 sample/retirement overlaps occurred.
All E values, N1/N128 and repeated queue-pointer wrap are covered. Five counter
seeds are explicitly whitebox diagnostics; ordinary behavior is independently
reconstructed from port handshakes. The oracle imports no worker/golden code.
Four actually compiled/simulated defective wrappers and27 corrupted logs were
rejected. Corrupted log copies remain private; their deterministic generator,
original positive log, exact mutations and hashes are supplied.

Main reran54 integration cases/1353306 checks using six flat inputs with spaces
and the corrected runner. Old runner non-UTF8 output/timeout bytes were changed
by decoding/re-encoding; corrected raw capture preserves them. A mistaken
initial main assertion about ASCII timeout output is separately preserved and
corrected. SR01 fill-slot defect was fixed by the worker before final submission;
main's original failing snapshot and diagnostic fix are retained separately.

Portable reproduction from any directory, with explicit local tool/input paths:
```text
python -B -X utf8 RUN_BLOCK_STREAM.py --core CORE.sv --wrapper WRAPPER.sv --tb TB.sv --golden CODEC_REFERENCE.py --spec MAIN_STREAM_SPEC.md --output NEW_OUTPUT --owned-root ALLOWED_OUTPUT_PARENT --vlib PATH_TO_VLIB --vlog PATH_TO_VLOG --vsim PATH_TO_VSIM --timeout 60
python -B -X utf8 main_stream_review.py --check independent_ports/ports.txt
```
For an independent simulator replay on another checkout, import the supplied
`main_stream_review.py`, set its `CORE` and `TOOLS` Path variables to the actual
core and ModelSim win64 directory, and call `run(new_output_path, wrapper_path)`.
`H` is automatically this evidence directory containing `main_stream_ports.sv`.
The preserved original runner invocation/commands contain the true B paths.

`raw_log_map.json` lists exact-byte aliases of ignored log files. Historical
worker stdout/stderr text and combined marker views are explicitly labeled as
derived; they are not misrepresented as original pipe bytes. Main independent
tool captures, corrected portable tool captures and direct simulator event
files preserve raw bytes. Selected final/failed worker records are supplied;
all other historical attempts and compiled ModelSim work libraries stay local.
No compiled vendor library or waveform is a synthesized FPGA result.

External consumers must observe the same synchronous reset/cancel boundary and
discard a partial frame. No rollback of consumed bytes, stopped-clock guarantee,
CDC/RDC, timing, physical throughput or board/system acceptance is claimed.
Current remaining B work is in `completion_matrix.md`. H01-H15/frozen design and
physical-board A-only rule remain unchanged.
