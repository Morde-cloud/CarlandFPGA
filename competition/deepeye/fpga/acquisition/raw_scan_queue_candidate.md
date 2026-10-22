# Raw scan queue candidate (operation 23)

Status: author candidate under task `DEEPEYE-IMPLEMENTATION-20261014/version1`,
work `B-RAW-SCAN-QUEUE-RTL-20261022-23-v1`. This document and the RTL are
internal design evidence only. They are not a public ABI, register map,
transport schema, timing claim, CDC claim, board result, or product acceptance.

## Fixed human scope

- Contract: `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source
  `f5989cd5defce561f9ba98e6b18fc2682945f0a2`.
- Canonical requirements array SHA256:
  `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`,
  computed with UTF-8, `ensure_ascii=False`, `sort_keys=True`, and separators
  `(',', ':')`.
- Frozen design commit: `1011259415a0916054eb580687612580bc1e5f09`.
- H01-H15 remain in force; this queue increment neither weakens nor satisfies
  their full-system gates. Board work remains A-only.

## Purpose

`deepeye_raw_scan_queue` is a single-clock FIFO of complete opaque four-channel
raw records. It belongs after the existing one-record `deepeye_sample_scan_capture`
slot. The sample-event source has no ready input, so this finite queue absorbs
bounded bursts only; sustained source input during downstream stall can still
cause the collector's explicit overrun/drop. No lossless sustained-rate claim is
made.

Exactly `DEPTH` complete records are stored. There is no extra output slot,
skid buffer, reservation, partial-record store, external address port, or
dynamic storage. Output selection reads the oldest stored record. Memory is
written only on an input handshake.

## Parameters and clamped declarations

Legal ranges are DEPTH1..8, SEQ_W2..32, TICK_W1..64, TAG_W1..64,
STAT_W2..32. Each legal request selects itself; every illegal request uses
the lower declaration fallback1/2/1/1/2 respectively, before the unchanged
own-fatal diagnostic at time zero. Effective constants remain localparams.
This declaration accommodation never makes an illegal request acceptable.

## Ports

All quantities are unsigned. Payload lane packing is:

- `data[16*i +: 16]`, for `i=0..3`, lane 0 least significant.
- `ticks[TICK_W*i +: TICK_W]`, for `i=0..3`, lane 0 least significant.
- `quality[8*i +: 8]`, for `i=0..3`, lane 0 least significant.

The six payload fields (`data`, `ticks`, `quality`, `first_seq`, `last_seq`,
`tag`) are copied without decoding or normalization. No ordinal, tick, quality,
or tag relationship is imposed.

Ports are `clk`, `rst`, `cancel`, `in_valid`, `in_ready`, `in_data`, `in_ticks`,
`in_quality`, `in_first_seq`, `in_last_seq`, `in_tag`, `out_valid`, `out_ready`,
`out_data`, `out_ticks`, `out_quality`, `out_first_seq`, `out_last_seq`,
`out_tag`, `level`, `stat_accepted`, `stat_retired`, and `stat_aborted`.

## Edge semantics

`rst` and `cancel` are synchronous active-high controls; `rst` has priority.
Both combinationally suppress `in_ready` and `out_valid`, so no handshake is
offered during an abort.

- `in_ready = !rst && !cancel && level < DEPTH`.
- `out_valid = !rst && !cancel && level > 0`.
- `rst`: clear occupancy, both pointers, and all three counters.
- `cancel`: no push/pop; add the pre-edge level to `stat_aborted` with
  saturation, clear occupancy and both pointers, and preserve accepted/retired.
- Neither abort: retire the pre-edge oldest record on `out_ready`, append the
  current complete input record on `in_valid && in_ready`, and set
  `level <= level + push - pop`. Counters increment only on actual handshakes.

At old full, input cannot use the slot freed by that same edge's retirement.
At empty, there is no same-edge output bypass. Simultaneous push and pop are
allowed at intermediate occupancy. Payload is stable while `out_valid=1` and
`out_ready=0`; invalid output payload is unspecified. Stale memory bits may
remain after reset/cancel, but occupancy and pointer state never let a flushed
record become valid again.

## Diagnostics

Invalid parameters are rejected by a time-zero `$fatal(1, ...)` in this exact
priority order:

1. `deepeye_raw_scan_queue: DEPTH out of range`
2. `deepeye_raw_scan_queue: SEQ_W out of range`
3. `deepeye_raw_scan_queue: TICK_W out of range`
4. `deepeye_raw_scan_queue: TAG_W out of range`
5. `deepeye_raw_scan_queue: STAT_W out of range`

Counters saturate at `2**STAT_W - 1`. Cancel addition uses an intermediate at
least `max(STAT_W, LEVEL_W)+1` bits wide, so `DEPTH=8`, `STAT_W=2`, old level 8
produces 3 rather than truncating 8. Increment also uses a widened sum. Flow
and stored data remain correct after saturation.

## Evidence boundary

Bounded author checks use real ModelSim SE-64 10.7/2017.12 and are recorded under
`competition/deepeye/evidence/acquisition/raw-scan-queue-20261022-23/author/`.
The independent main model, expected vectors, schedules, and acceptance remain
owned by the product main. Synthesis, implementation, timing, CDC/RDC, board,
all29, B02, B03, G05, B06, R03, and full-system acceptance are not run here.

## Main-authored repair02 evidence validation

After the original author and failed Flash guard-repair assignment, the existing
quality main repaired only the initializer rules and evidence validator under
B-RAW-SCAN-QUEUE-MAIN-RECOVERY-20261022-23-v1. The author TB receives only the
matching declaration corrections; legal stimulus and coverage expectations are
unchanged. Old source snapshots and rejected evidence remain separate.

The standalone runner now requires complete case/width-bound records paired as
pre cycle N / post cycle N+1. It reconstructs a record list and collector event
history from inputs, not ref_* values. Counters follow their distinct reset or
collector-window origins and exact saturation. Unknown registered state before
the first applied reset and invalid payload spellings remain unspecified;
defined positive observations must be known. No X is coerced to zero.

Reported stalls select the longest contiguous nonabort input-idle, consumer-held
nonempty interval. Reported circuits select the longest contiguous nonabort
in_valid/out_ready interval; reference admissions/retirements in exactly that
interval are divided by DEPTH. Earliest interval wins ties. These are selected
segments, not total lifetime stalls/wraps; original4096/1000 minima still apply.
Mutant evidence requires a finite numeric contradiction corroborated in complete
captured ports; positive-history success is not required of an intended mutant.
Synthetic selftest fixtures now contain coherent full histories and remain
explicitly distinct from simulator runs. No private/main oracle is imported.

This remains a local candidate pending independent coordinator review, with no
public ABI, board, source-clock, freshness, DMA/PS or movement authority.

### Repair03 mixed-unknown field encoding

Mixed hexadecimal X/Z encodings must also fit the declared field width in
every known bit. A known set bit in the top nibble's padding is rejected even
when a lower nibble is unknown. Unknown padding itself remains unspecified;
legal inactive/bootstrap words retain their symbolic X/Z values (with the
existing lowercase normalization). This is an encoding check, not a new value
constraint on inactive payloads. Main-owned parser qualification is recorded in
`competition/deepeye/evidence/acquisition/raw-scan-queue-20261022-23/main/repair03/`.
Its saved-transcript and synthetic process-seam results are separate from the
unchanged RTL/TB's original vendor evidence and await coordinator review.
