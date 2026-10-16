# B register proposal07 review

This is a declarative candidate for A approval, not an MMIO driver, RTL register
bank or public ABI freeze. All29 A source offsets/names/widths/status/authority
rows remain verbatim. B proposes51 explicitly typed fields, reset/access/byte
write rules, separated STOP/clear/enable commands, CONFIG staging and revoked
multiword snapshot coherence.35 hand-derived examples are design expectations;
no proposed state machine was executed. Static review confirms29 rows/51 fields,
19 literal/arithmetic examples and4 rejected field encodings. Those counts are
not runtime/RTL tests or B05/R03 acceptance.

H01-H15 DEEPEYE-HUMAN-LOCK-20261014/r1 requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804;
design1011259415a0916054eb580687612580bc1e5f09. A input
66aa291d7f01cc3cfefb8c30c4e8ad3aec6547bd, exact pins in input-pins.json.
A alone actual board/HWH access; these artifacts open no register interface.

The snapshot mailbox06 and earlier capture model/inventory remain byte-identical.
Its physical CDC/RDC gates are unchanged. The register proposal requires more
than opaque transport: internal revocation generation, A-authenticated contexts,
serialized readers and rejection of late retired CDC results remain integration
requirements. ENABLE cannot bypass A BOOT, profile, source, clock or capture
validation. Reserved0x2c remains inaccessible, including zero-strobe accesses.
The fail-safe STOP byte-strobe/error priority is an explicit B proposal for A
to accept or replace, not an inferred existing register rule.

The gain code map and Q8.8 ratio derive from exact A wire inputs. Ratio requires
independent before/after ADC calibration; it is neither compression ratio nor
MCP6S21 SO readback. Wire capture/observation16bit values are not silently
truncated from local batch32. Missing raw high-count/edge-tick diagnostics,
queue attribution, identity/reset, configuration domains and tick provenance
remain specific A decisions. Do not consume those domains as frozen enums.

## Reproduce static review from repository root

Use a fresh output path; this command performs no bus/hardware access.

```text
python -B -X utf8 competition/deepeye/evidence/control/register-proposal-20261017-07/review_descriptor.py --descriptor competition/deepeye/golden/control/register_semantics_candidate.json --examples competition/deepeye/golden/control/register_semantics_examples.json --register-source competition/deepeye/evidence/control/register-proposal-20261017-07/inputs/registers.csv --interface competition/deepeye/evidence/control/register-proposal-20261017-07/inputs/interface.json --enums competition/deepeye/evidence/control/register-proposal-20261017-07/inputs/enums.json --output .local/new-register-proposal-review.json
```

See golden/control/REGISTER_SEMANTICS_CANDIDATE.md and the machine-readable JSON
for the full proposed command ordering, byte masks, reset invalidity and latch
rules. Physical and product stages remain not_run. Return review on PR30 with
operation/request_hash/tested_commit and specific accepted/rejected proposals.
