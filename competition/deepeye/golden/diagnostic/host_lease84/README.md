# Strict host-lease CLI84

`host_lease84_cli.py` is a bounded, file-in/stdout-out front end for the pure
host lease ledger. It supports only `register`, `ack`, `evaluate_deadline`,
`terminate` and `disable`. It performs no clock read, callback, packet send,
network access, board access, Root call or action authorization.

## Invocation

```text
python -B host_lease84_cli.py INPUT.json
```

The input is UTF-8 JSON, at most 64 KiB. Output is canonical UTF-8 JSON plus a
newline, at most 1 MiB. Unknown fields, duplicate JSON keys, floats,
NaN/Infinity, custom values, bool used as an integer, regressing supplied time,
identity changes, capacity overflow and invalid operation shapes are refused.
The parser never repairs or accepts a second value for a duplicate key.

Top-level schema:

```json
{
  "schema": "host_lease84/cli-input/v1",
  "mode": "SYNTHETIC_FIXTURE",
  "operations": [{"op": "register", "request": {}}]
}
```

`mode` is optional and defaults to `PRODUCTION`. Production always returns
`INPUT_UNAVAILABLE`. `SYNTHETIC_FIXTURE` must be explicit. At most 16 operations
are evaluated in order; a refusal stops the batch.

Operation fields are exact:

- `register`: `request`
- `ack`: `ack`
- `evaluate_deadline`: `request`, `now_ns`
- `terminate`: `request`, `at_ns`, `reason`, optionally `newer_boot_id` and
  `newer_epoch`
- `disable`: only `op`

The exact request and ACK schema is defined by `host_lease83.py`. An ACK records
facts but does not itself return a lease. Only an explicit synthetic
`evaluate_deadline` with a caller-supplied original uint63 time can return the
structural `LEASE`.

## Exit and evidence contract

- `2`: refused input or operation.
- `3`: no positive structural result; production and unavailable paths.
- `0`: the final operation is an explicit synthetic structural `LEASE`.

The output includes the original input path, raw byte count/hash, canonical
byte count/hash, full result `original_context`, each operation result's
canonical byte count/hash, and a canonical digest of the pre-receipt output
payload. Raw stdout/stderr bytes and their hashes must be recorded by the
caller's owned-process evidence; a file cannot contain its own final raw hash
without a circular self-reference. The raw input file is retained by the test
harness.

The CLI is not an ACK authenticator, clock measurement, capture-freshness
source, board driver, firmware transport or product acceptance. Synthetic
success does not close B05/G05/full H12/all29 or authorize motion.
