# Internal TRACE frame to UART candidate49

This structural composition connects the unchanged45 frame candidate to the
unchanged24 UART transmitter on one clock/reset/cancel. CLOCK_HZ=100000000
and BAUD=9600 are forwarded unchanged; STAT_W is32. Defaults grant no clock,
baud calibration, pinout or performance authority.

Configuration and result handshakes additionally require UART idle. The inner
result remains pending while the last byte is physically transmitting. Local
success means that byte's stop interval completed; it does not mean receiver
acceptance. Errors1..3 emit zero bytes. Existing sticky wire fault ports are
forwarded; their structurally unreachable trigger is not forced for coverage.
Busy is frame_busy OR uart_busy. There is no new FIFO, scheduler or policy.

TX is the direct existing UART output. Reset/cancel masks handshakes immediately
but returns TX high synchronously on the active edge. Both inner stages discard
pending work. Configuration still waits for the42 CLEAR barrier. Already sent
bits, bytes and complete frames cannot be recalled or remotely invalidated.
Recovery regenerates a complete fresh frame. A pending report prevents new
configuration, including the result-consumption edge.

The bounded author tests reuse selected immutable45 payload fixtures, with exact
source/fixture hashes and coverage disclosure. Complete framing/CRC is computed
independently. Public TX and UART-busy histories are checked against mathematical
ceil(k*CLOCK_HZ/BAUD) boundaries, with phase restarted at each byte admission.
Fractional5/2,7/2,16/3, minimum2/1 and actual100000000/9600 are exercised.
The two invalid parameter cases use the actual inherited DUT runtime guards.

The raw public trace has one line per active edge; its one-based record number
is the cycle. Each line contains operation-id, PRE and POST25-bit hex words:
bits0=tx,1=uart_busy,2=busy,3=cfg_ready,4=s_ready,5=result_valid,
6=result_ready,7=rst,8=cancel,9=cfg_valid,10=s_valid,11=s_last,
12=wire_faulted,13=wire_fault_event,14..15=wire_fault_code,
16..18=result_error,19..24=result_bytes. The first PRE can contain unknown
uninitialized register bits and is retained; all POST endpoints must be known.
Operation markers, statistics and actual finish time tie every trace record to
its immutable fixture. Saved-log negatives retain one base plus recipes/hashes.

Work B-TRACE-UART-CANDIDATE-20261024-49-v1, task
DEEPEYE-IMPLEMENTATION-20261014/v1, operation
B-DEEPEYE-TRACE-UART-CANDIDATE-20261024-49. Sole main
01a13b55-095b-7461-8dd5-5476a130bd82 owns independent review and acceptance.
H01-H15 DEEPEYE-HUMAN-LOCK-20261014/revision1, pinned at
f5989cd5defce561f9ba98e6b18fc2682945f0a2, requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.
Frozen design1011259415a0916054eb580687612580bc1e5f09. All29 formal cards,
including B01/B03/B06/R03, remain not_run. A alone operates the physical board.
No production type7 ABI, TRACE admission, source/control authority or motion
grant is enabled. No Vivado or board result is provided by this work.
