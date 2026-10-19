# Main WIP observation (not final worker acceptance)

Observed source SHA256 b5e4ee6cdbde370a5b837b6f16b7c4d9962f4a0899092f4d267609baa887ac1a
was copied to wip-main-observation/observed_reference.py while the child retained
its source ownership. No concurrent product edit. The independent probe executed
only that isolated copy;4 test methods exposed9 failures and1 reset-callback error.
Preserve exact stdout/stderr and source. Wait for terminal worker result before
changing its paths; final source may differ.

- RT01: complete_capture validates ticket before accepting a custom Mapping whose
  getter can revoke via STOP/fault/newcapture/context/CDC/reset. It then builds a
  publication using the NEW current generation/context without rechecking the old
  ticket. STOP etc re-publish status.available/ratio-valid; reset causes AttributeError.
  Final acceptance requires rechecking captured context/generation/batch and CDC
  eligibility after all user-controlled extraction/validation, before atomic commit.
- RT02: new session or BOOT keeps enabled and active CONFIG from the old identity.
  Main specification did not spell out every state-clearing action, so this is
  also a main-spec clarification: any context change stops/disables and invalidates
  old gates; session/BOOT/config_epoch changes also clear active CONFIG/staged
  initialization. Request/control-epoch-only changes may retain config data but
  require explicit fresh fixture gate/ENABLE. No inherited real authority.
- RT03: CDC loss with pending CONFIG but no capture state fails to discard pending
  apply. Loss must revoke regardless of whether a snapshot previously existed.
- RT04: withdrawing fixture enable gate leaves enabled=true. Loss must stop/disable,
  revoke capture/pending request and require an explicit subsequent ENABLE.

Additional source-review check: B07 status.gain_ratio_valid describes the latched
bank. complete_capture must keep this bit false until successful LATCH. Capture
quality and independent ratio-valid remain separate. Counter increment API may
be bounded u16 per call (not explicitly prescribed); main saturation test should
use two valid u16 increments rather than assume one oversized increment is accepted.

These are offline fixture correctness findings. No board/runtime or formal card
has been accepted. A owns all public ABI/BOOT/clock/physical gate definitions.
