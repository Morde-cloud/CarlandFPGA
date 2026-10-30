# Host ACK deadline seam (source83, repaired under functional84)

Source for `DEEPEYE-IMPLEMENTATION-20261014/v1`, work
`B-HOST-ACK-DEADLINE-FUNCTIONAL-20261030-84`. H01-H15 remain pinned by revision
1 requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
`host_lease83.py` is a pure detached numeric state ledger. It contains no packet
builder, send/retry callback, socket, clock reader, board, Root, planner, motion
or action-retirement path.

## Production boundary

`HostLeaseLedger()` defaults to `PRODUCTION`; every otherwise valid
registration, ACK, termination or deadline query remains `INPUT_UNAVAILABLE`.
Explicit `SYNTHETIC_FIXTURE` evaluates only caller-supplied detached facts. Its
`LEASE` result is a structural deadline result, not current capture freshness,
measured host time, ACK authenticity, motion authorization or product
acceptance. The module never reads a clock.

## Record schema

A request contains `session`, `request_type=0x0e`, `seq`, `cmd_id==seq`,
lowercase 64-hex `payload_sha256`, `transaction_tag`, `boot_id`, uint63 `epoch`,
uint63 `first_send_ns`, `original_ttl_ms`, `profile`, and a bounded plain-JSON
`context` retaining exact original text and uint63/QPC values. `FAST_9600`
permits TTL 1..3000 ms and `STRESS_300` permits 1..12000 ms. Canonical UTF-8
context is at most 4096 bytes.

An ACK repeats every immutable request field and requires `receipt_ns`, textual
`phase`, `capture_complete`, `fault` and `remaining_ttl_ms`. Missing required
ACK fields are `Refused`; they are never raw `KeyError`s. Optional timing bounds
and `raw_header_tick` may be absent. Absent USB or clock bounds produce
`BOUNDS_UNAVAILABLE`; they are never defaulted to zero. Every supplied raw
header tick is retained separately and is not converted into a clock origin.

Only `ACCEPTED`, `APPLIED`, `CAPTURED`, `REJECTED` and `STOPPED` are accepted as
phase labels. No numeric phase ABI is invented. `REJECTED` and `STOPPED` are
terminal. Once an eligible captured fact exists, incomplete capture, backward
phase, or loss of previously supplied bounds permanently terminates as
`CAPTURE_LOST`, `PHASE_REGRESSION` or `BOUNDS_UNAVAILABLE`. Missing bounds before
the first eligible captured fact may later become available.

## Deadline math

```text
wire_ns(baud)  = ceil(34*10*1_000_000_000 / baud)
               = 1_133_333_334 ns at 300, 35_416_667 ns at 9600
original_cap   = first_send_ns + original_ttl_ms*1_000_000
deductions     = wire_ns + usb_processing_bound_ns + clock_error_bound_ns
receipt_cap    = receipt_ns + max(0, remaining_ttl_ms*1_000_000 - deductions)
candidate      = min(original_cap, receipt_cap)
deadline       = min(prior_deadline, candidate)
```

Every addition is checked uint63 arithmetic; overflow is refused. An 8 s late
ACK under a 12 s original TTL preserves the original cap. Later ACKs can only
shorten an existing deadline. Limits are 16 retained transactions and 8 distinct
ACK facts per transaction, with no eviction, wrap or reset.

## Query and terminal rules

`register` and `ack` never return positive eligibility. `ack` records the fact
and, when eligible, returns `EXPLICIT_DEADLINE_QUERY_REQUIRED`. The caller must
invoke `evaluate_deadline(original_request, now_ns)` with an explicitly supplied
original uint63 nanosecond value. That query validates exact identity and types
even while disabled, refuses time regression, and expires at
`now_ns >= min(original_cap, deadline)`. It never renews a deadline.

Before a duplicate ACK shortcut, expiry is evaluated using the latest already
observed original time. Repeated old ACKs cannot become eligible or clear a
terminal. Cancel, fault, expiry, new BOOT, newer epoch and supersession remain
permanent. Consistent later facts may be retained but cannot revive state.

Every result keeps `sent=false`, `packet_created=false`,
`physical_acceptance=false` and `action_authorized=false`. This source does not
close B05/G05, complete H12, authenticate capture/ACK, or provide physical or
formal product acceptance.

## Controls

`test_host_lease83.py` contains the 18 original controls updated for the
explicit-query contract plus focused controls for missing fields, disabled-query
validation, boundary expiry, permanent capture/phase/bounds loss, checked sums,
raw header ticks, phase labels, duplicate-after-expiry, supersession and disable.
Execution evidence belongs under the work84 private evidence directory; this
README is not a PASS claim.
