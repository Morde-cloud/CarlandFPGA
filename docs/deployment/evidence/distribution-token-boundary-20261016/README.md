# Distribution token boundary correction

Operation: `B-DISTRIBUTION-TOKEN-BOUNDARY-20261016-v1` under
`B-RUNTIME-CONTINUITY-20261016/v1`.

The full committed-file package failed because the credential scanner matched
the interior of task identifiers in the existing `B-INTERRUPT-20261014` evidence
README. The original build failure and a failing regression are preserved.

Add an ASCII identifier left boundary only to the `sk-` token alternative.
Token length and suffix characters are unchanged. The PEM and PGP private-key
alternatives are unchanged and remain independent of this boundary. Files and
historical evidence are neither excluded nor rewritten.

Regression cases cover packaging task identifiers and the original evidence
bytes, rejecting standalone keys and keys after quotes, equals, colon, path
separators and whitespace, rejecting a real key in the same file as a task ID,
and rejecting every supported private-key header even after an identifier.

Validation results and exact source hashes are recorded in this directory and
the operation's separate handoff manifest. They establish package construction
and offline behavior only. Node B's local source conflicts, custom scheduled-task
launcher, actual App writers and admission guards must be reconciled before any
deployment. No service stop or deployment is part of this change.

All H01–H15 in `DEEPEYE-HUMAN-LOCK-20261014`, revision 1, remain intact:
requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Only A operates the physical board.
