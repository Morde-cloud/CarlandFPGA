# Preserve B's Feishu SDK loop isolation

Operation `B-LOCAL-RUNTIME-COMPAT-20261016-v1`, under
`B-RUNTIME-CONTINUITY-20261016/v1`, ports the known B SDK overlay into the
isolated runtime candidate. It does not deploy that candidate.

The previous candidate imported the optional SDK on the active controller
event loop. The B overlay loads its default channel factory through
`asyncio.to_thread`, so the SDK's import-time loop capture and disconnect do
not own or stop the controller loop. The existing channel factory injection,
allowlist, strict security, message delivery onto the controller loop and
outbox behavior are preserved.

The source and two regression methods are applied as minimal patches, not
whole-file copies from the local workspace. Their source is the preserved
`B-preserve-sdk-overlay-920ab35.zip`, SHA256
`78a71fe2313c19b6db00760b3d592d3b71b2c66c4928477ce0c348cc97b9e25d`.
Both local files match that archive's original bytes. Preimage hashes and
patch verification are recorded alongside the regression evidence.

The two regression methods first fail against the prior candidate, then
exercise worker-thread SDK import, a distinct loop, disconnect safety and
the injected-factory path. Tests use a synthetic SDK/channel and make no
real Feishu requests. Exact-source results are in `source-validation.json`.
They are software evidence, not a live SDK reconnect or deployment result.

Other local conflicts and the custom scheduled-task launcher remain subject
to a separate reviewed preservation plan. No updater, scheduled task, root
source, credential, configuration, SQL, lock or mapping is changed here.
Previous cache, owner and packaging manifests remain immutable.

H01–H15, `DEEPEYE-HUMAN-LOCK-20261014/revision1`, remain unchanged:
requirements SHA256
`c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`.
Only A operates the physical board.
