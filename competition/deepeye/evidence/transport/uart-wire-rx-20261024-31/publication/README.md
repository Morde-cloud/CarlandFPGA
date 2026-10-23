# B-DEEPEYE-UART-WIRE-RX-20261024-31

UART-to-opaque-parser candidate using unchanged pinned UART RX/parser/CRC. Main acceptance covers exact same-clock digital bytes and loss/discard histories only. Every independent reference sample uses absolute half-bit deadlines; main parser helper is pinned and included as transitive source.

Reproduce tools/transport/main_verify_uart_wire_rx.py with --rtl, --dependencies, --tb, --vectors from archived main/vectors-* and fresh --out. Read main/final-audit-01/RESULT.json and runner-qualification-repair1-01. The original illegalwidth and log-parser failures are retained separately. Simulation used immutable working-repair snapshots; final terminal bytes were independently matched.

No wall-time timeout, authentication or physical clock/source/BOOT/TTL/motion grant. All29/fullproduct/hardware gates remain not_run; A-onlyboard. H01-H15 canonical c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 unchanged.
