# New affected controls for main-selected129

No tests executed in work128. Entry `test_adapter128.py --out <abs-new-dir>`.
The main owns the first freeze/command and existing108 supervisor limits:
15s nominal (12s live +1/1/1 cleanup),512MiB committed, native16/sample16,
1MiB sampled output,0.05s monitor. No custom runner or source-owned run folder.

1. Arbitrary external data with no104 kind/provenance; raw bytes, opaque uint16
   quality and the input113 normalized entry; no injected fake/current fields.
2. Pre-write uint16>4095, held same-microsecond, E/time/quality/session/sequence,
   canonical-build-prefix and request mismatches; complete refusal bytes.
3. Variable numerical scans including valid zero and all-invalid; existing codec
   generated control frames; exact four-frame/value/CRC/result-ID and companion
   correlation; missing/extra/bad magic/bad CRC/mismatched companion refusals.
4. New intent/observation API through one scan and one exact collection; consumed
   start/collect/CANCEL, ordered command counts and TRACE-only relative intents.
5. Dirty/identity/counter-headroom preflight refusal with zero writes and no
   owned cleanup/collection.
6. Unknown attempted ARM, unattempted ARM, read error, unknown POP; explicit
   ownership, retained pending byte, no replay and at most one owned CANCEL.
7. Stable operation/call identity, mismatched receipt not consumed, no duplicate
   accepted receipt or start replay.
8. Finite progress/CSR/write/evidence/time budgets at this interface; bounded
   stalled transcript and pre-effect deadline refusal.

Test transcripts produce data responses only, not RTL/MMIO/physical evidence.
They do not import Host103 or input113's old test suite. The unchanged normalizer
and codec are runtime dependencies, not old-group replay. All individual group
results and failures persist; no automatic retry of failed groups. A partial
test process killed by the supervisor is not a passing RESULT.
