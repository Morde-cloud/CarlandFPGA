# Reusing the pinned Codex runtime after Desktop cleanup

Work `B28-CACHE-RESOLVER-20261016-v1` extends this repair. On Windows with a
runtime cache configured, the first successful resolver call atomically saves
one selection binding under that cache. Its selector is the normalized absolute
explicit executable path, or the normalized absolute Desktop bundle root for
automatic selection. Every later call reads that exact binding before inspecting
the original installation. It validates the saved manifest byte hash, the existing
content-address key, required executable/host, complete file inventory and all
file hashes. Symlinks, Windows junctions, unsafe manifest paths and malformed
bindings fail with `RuntimeIntegrityError` before creating a transport.

An existing selection remains pinned even when Desktop installs newer bytes.
Corruption never falls through to source discovery, another cache or the shell
shim. Concurrent publication preserves and validates the first complete binding.
Legacy snapshots without a binding are not discovered by scanning: the first
binding still requires the selected original source. With no binding and no
source, the original explicit-path error or automatic shim behavior is preserved.
Choosing a new cache directory is an explicit way to select a newer runtime;
this change does not mutate the running service's configuration.

The local binding detects cleanup and inconsistent/partial state; it is not a
signature against a same-user process rewriting the whole chain. Verification
does not eliminate modification between checking files and launching them.
The tests use non-executable fixture bytes, including second resolution from
a fresh Python process. They establish resolver behavior, not live reconnection
or deployment acceptance. Pre-initialize and after-turn failure handling remains
unchanged, including the prohibition on replaying ambiguous side effects.
