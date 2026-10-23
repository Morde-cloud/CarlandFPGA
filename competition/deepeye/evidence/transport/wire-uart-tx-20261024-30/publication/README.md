# B-DEEPEYE-WIRE-UART-TX-20261024-30

Single-reservation opaque packet serializer to complete-frame UART composition. Main acceptance is limited to same-clock digital behavior at the exact source hashes in SOURCE_BINDING.json. The frozen absolute-clock oracle covers every bit boundary, whole frame, DE release and retirement; no output edge is used as the time origin.

Reproduce tools/transport/main_verify_wire_uart_tx.py with --rtl, --dependencies, --tb, --vectors from archived main/vectors-* and a fresh --out. Read main/final-audit-01/RESULT.json and main/classifier-order-01/RESULT.json. Original author and main harness/parser failures remain archived; synthetic parser qualification is distinct from actual ModelSim runs.

No public semantic ABI, BOOT/TTL/clock/source/motion authority or physical link result. All29 formal and hardware/system gates remain not_run. H01-H15 fixed contract canonical c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804; board A-only.
