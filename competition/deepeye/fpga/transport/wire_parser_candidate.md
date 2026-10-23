# `deepeye_wire_parser` candidate (operation 29)

Task `DEEPEYE-IMPLEMENTATION-20261014/v1`; original work
`B-WIRE-PARSER-20261024-29-v1`; repair
`B-WIRE-PARSER-STATUS-REPAIR-20261024-29-r1`; runner qualification
`B-WIRE-PARSER-RUNNER-QUALIFY-20261024-29-r2`; operation
`B-DEEPEYE-WIRE-PARSER-20261024-29`.

## Authority boundary

This is an author candidate for independent review. `out_valid` means only that
one complete byte sequence has valid magic, version, length, and CRC syntax. It
does not authenticate a sender, establish profile/source/BOOT/TTL permission,
authorize motion, validate packet semantics, or replace the public runtime ABI.
Parsing type, epoch, sequence, and tick as opaque fields also makes no replay or
liveness guarantee. External UART loss/overrun handling is outside this module.

The implementation composes one unchanged, read-only accepted primitive:

- `competition/deepeye/fpga/transport/deepeye_crc16_byte.sv`
- SHA256 `8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f`

## Interface and storage

`STAT_W` is legal from 2 through 32 and defaults to 32. An unsafe width is first
clamped for elaboration and then produces the time-zero fatal message
`deepeye_wire_parser: STAT_W out of range`. All seven counters saturate at the
configured width.

The wire layout is:

```text
A5 5A | 03 | TYPE | LEN(0..32) | EPOCH | SEQ.lo SEQ.hi |
TICK[7:0] TICK[15:8] TICK[23:16] TICK[31:24] |
PAYLOAD[LEN] | CRC.lo CRC.hi
```

CRC is CRC-16/CCITT-FALSE seeded with `FFFF`; its covered bytes start at the
version and include the payload, excluding magic and the two CRC bytes. Received
CRC bytes are compared little-endian. The maximum wire frame is 46 bytes.

One 32-byte payload array is reused as output storage. Byte `i` is exposed at
`out_payload[8*i +: 8]`. Every new `A5` candidate clears all 32 bytes before any
payload can be accepted, so zero-length and short frames always have zero tails.

## State and handshake behavior

- Input advances only with `in_valid && in_ready`.
- `in_ready` is low for reset, cancel, or a pending completed output.
- A completed output remains byte-for-byte stable until `out_ready`.
- A completed slot cannot retire on the same edge that accepts input; input is
  eligible only after the retirement edge.
- `receiving` covers only a partial prefix/candidate, never a pending output.
- Version, length, and CRC failures pulse `error_event` for one ordinary cycle,
  place code 1, 2, or 3 on `error_code`, and clear the code afterwards.
- `receiving`, `error_event`, and `error_code` expose the registered partial
  candidate and error diagnostic until the next rising edge. Asserting cancel
  or reset does not withdraw those diagnostics before that edge; the synchronous
  control clear happens at the edge. Only the valid/ready handshake gates react
  immediately to an asserted abort.
- On an error, only the current rejected byte may become a new `A5` prefix. The
  parser never rescans a rejected buffered candidate.
- Cancel is synchronous and has priority over ordinary parsing. It increments
  `stat_aborted` once only if a partial candidate or completed slot existed,
  clears payload/descriptor/error state, preserves all other counters, and does
  not sample or retire on that edge. Held cancel does not recount.
- Reset has priority over cancel and parsing, and clears all counters and state.
- There is no wall-time timeout; a stalled physical byte stream requires an
  external abort or higher-layer liveness response.

## Author verification

`competition/deepeye/tools/transport/run_wire_parser.py` creates a new attempt
under
`competition/deepeye/evidence/transport/wire-parser-20261024-29/author/attempts/`.
It verifies the pinned human contract and frozen CRC hash, snapshots every
source, generates independent `binascii.crc_hqx` fixtures with a separate
bitwise cross-check, and runs ModelSim SE-64 10.7 with TEMP/TMP/TMPDIR/caches and
simulator cwd inside the attempt. `HOME` is not replaced: the runner preserves
and records the inherited operator `HOME`, while isolating `TEMP`, `TMP`,
`TMPDIR`, `MODELSIM_TMPDIR`, `XDG_CACHE_HOME`, and `PYTHONPYCACHEPREFIX` under
the attempt. The attempt does not claim ownership of all inherited home state.

The directed bench covers all lengths 0 through 32, all 256 payload byte values,
metadata endianness/maxima, 49 independent standard-library CRC frames, noise
and prefix overlap, truncation, version/length/CRC rejection and recovery,
no-buffer-rescan behavior, input/retirement and output stalls, payload zeroing,
every cancel/reset phase through a complete frame, counter saturation, and both
out-of-range width guards. Repair case coverage additionally holds a partial
prefix and each error type across falling-edge cancel/reset, checks the old
counters and synchronous diagnostics immediately before the edge, checks the
edge clear/abort increments, immediately gates `in_ready` and `out_valid`, and
covers completed-slot cancellation, one-cycle pulse clearing, and reset over
cancel priority. The runner requires the complete ordered checkpoint protocol:
each case has exactly one BEGIN, CHECKS, and PASS END row in index order, followed
by one SUMMARY and one ALL_PASS row. Any unknown, malformed, duplicate,
reordered, or extra line carrying the `WIRE_PARSER_` marker family fails. Case
check counts must be positive and sum to the summary total. The current table is
21 cases / 3,258 checks; the historical 18-case / 2,883-check stream is validated
with an explicit historical table rather than the current counts.

Normal runs require exactly one final `Errors: 0, Warnings: 0` tally, reject any
other tally, and reject every `** Error`, `** Warning`, or `** Fatal` diagnostic.
Each width guard requires its exact one `STAT_W out of range` fatal, exactly one
final `Errors: 1, Warnings: 0` tally, no other diagnostic, and no success or
fallback marker. Process timeout and nonzero-exit failures remain fail-closed.
All failed attempts and raw command streams are retained.

ModelSim 10.7 reports a deliberate `$fatal` as `Errors: 1` while still returning
process exit 0 when driven with `-c -do "run -all; quit -f"`. The guard check
therefore requires the exact fatal message, exactly one error, zero warnings,
and exit 0. The restricted guard classifier also rejects extra diagnostics,
duplicate or conflicting tallies, and success/fallback markers.

## Status

All29/B04/R03/full product/synthesis/implementation/timing/CDC_RDC/board/system
are `not_run`. The repair was prompted by a main preinspection oracle failure at
the pre-edge receiving boundary; after the source fix, the author suite was
rerun in full. Main acceptance, mutation/oracle work, publication, and all
physical board work remain outside this author scope. A alone operates the
board.
