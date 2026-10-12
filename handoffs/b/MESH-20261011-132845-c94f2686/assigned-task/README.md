# Bounded fixture validator: canonical-JSON byte convention

- operation_id: `MESH-20261011-132845-c94f2686:B:git-handoff-v1`
- assignment request_hash: `d48ba6f3c27522978a8a93716b967ab93f7a0820b37657481f7d380dda047d0f`
- scope: bounded fixture-validator deliverable only. One isolated worktree, no
  commit/push, no network, no board access, no production-source changes.

## Convention (a Python fixture convention, NOT RFC 8785)

A JSON fixture file is valid if and only if its bytes are exactly

    json.dumps(value, ensure_ascii=False, sort_keys=True,
               separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"

where `value` is the document parsed from those same bytes after these hard
rejections:

1. strict UTF-8, no BOM: a leading `EF BB BF` is invalid, not ignored;
2. no duplicate keys in any object, at any nesting depth;
3. no `NaN`, `Infinity` or `-Infinity`;
4. no unpaired surrogate code points in any string, key or value.

Consequences enforced byte for byte:

- No Unicode normalization: NFC and NFD sequences stay distinct.
- Keys are sorted by Python `str` comparison, i.e. by Unicode code points.
  Astral code points sort after every BMP code point (U+FFFD before U+10000),
  which is not UTF-16 code-unit order and not RFC 8785 order.
- No whitespace between tokens; only `,` and `:` separators.
- Exactly one trailing LF. CRLF, a missing LF and a doubled LF are invalid.
- Escapes are re-encoded by Python: `"\u0041"` is not canonical because it
  re-encodes as `"A"`, while an escaped newline inside a JSON string stays
  escaped (the file holds the two characters backslash + `n`).
- Numbers are Python `repr` text: `1.5` stays `1.5`; `1e2` is not canonical
  because it re-encodes as `100.0`.
- Non-ASCII characters are emitted as raw UTF-8 bytes (`ensure_ascii=False`).

This convention is intentionally simple for repository fixtures. It is not
RFC 8785 (JSON Canonicalization Scheme): RFC 8785 orders keys by UTF-16 code
units and uses ECMAScript number serialization. Do not cite this validator as
JCS conformance.

## Files

| path | role |
| --- | --- |
| `canonical_json.py` | read-only stdlib validator: importable API + CLI |
| `test_canonical_json.py` | unittest suite; expected bytes stated explicitly |
| `fixtures/generate_fixtures.py` | writes fixtures from explicit byte literals |
| `fixtures/*.json` | 8 valid + 17 invalid byte-exact fixtures |
| `run_evidence.py` | captures raw evidence into `logs/` |
| `logs/*.txt` | raw subprocess stdout/stderr + evidence summary |
| `.gitattributes` | `-text` for `fixtures/*` and `logs/*`, so git never converts them |
| `.gitignore` | ignores `__pycache__/` runtime artifacts |

## CLI

    python canonical_json.py PATH [PATH ...]

- one line per path, in argument order: `PASS <path>` or `FAIL <path> <CODE> <detail>`
- exit 0: all valid; exit 1: at least one invalid; exit 2: no paths given
- read-only: opens each path with mode `rb`; never writes or creates files

Codes: `E_IO`, `E_UTF8`, `E_BOM`, `E_JSON`, `E_DUPKEY`, `E_NONFINITE`,
`E_SURROGATE`, `E_NEWLINE`, `E_CANONICAL`.

## Fixtures

Valid (canonical bytes plus exactly one LF):

| fixture | covers |
| --- | --- |
| `fixtures/ok_basic.json` | object, array, booleans, null |
| `fixtures/ok_empty_object.json` | empty object |
| `fixtures/ok_top_level_array.json` | array root |
| `fixtures/ok_nested.json` | nested objects/arrays sorted at every depth |
| `fixtures/ok_unicode_keys.json` | key order z < e-acute < CJK < U+FFFD < U+10000 < U+1F600 |
| `fixtures/ok_escaped_newline.json` | escaped backslash-n inside a string stays escaped |
| `fixtures/ok_numbers.json` | 30-digit int, float 1.5, negative int in Python repr form |
| `fixtures/ok_no_normalization.json` | NFD and NFC bytes kept distinct |

Invalid (each rejects for exactly one reason):

| fixture | code | reason |
| --- | --- | --- |
| `fixtures/bad_bom.json` | `E_BOM` | UTF-8 BOM prefix |
| `fixtures/bad_invalid_utf8.json` | `E_UTF8` | stray byte 0xFF |
| `fixtures/bad_duplicate_key.json` | `E_DUPKEY` | repeated key "a" |
| `fixtures/bad_duplicate_key_nested.json` | `E_DUPKEY` | repeated key in a nested object |
| `fixtures/bad_nan.json` | `E_NONFINITE` | NaN |
| `fixtures/bad_negative_infinity.json` | `E_NONFINITE` | -Infinity |
| `fixtures/bad_surrogate_value.json` | `E_SURROGATE` | lone high-surrogate escape |
| `fixtures/bad_surrogate_key.json` | `E_SURROGATE` | lone low-surrogate key escape |
| `fixtures/bad_not_json.json` | `E_JSON` | truncated document |
| `fixtures/bad_raw_newline_in_string.json` | `E_JSON` | raw LF inside a JSON string |
| `fixtures/bad_whitespace_space.json` | `E_CANONICAL` | space after the colon |
| `fixtures/bad_whitespace_pretty.json` | `E_CANONICAL` | pretty-printed, indented |
| `fixtures/bad_missing_terminal_lf.json` | `E_NEWLINE` | no trailing LF |
| `fixtures/bad_doubled_terminal_lf.json` | `E_NEWLINE` | two trailing LFs |
| `fixtures/bad_crlf_terminal.json` | `E_NEWLINE` | CRLF terminator |
| `fixtures/bad_key_order_utf16.json` | `E_CANONICAL` | UTF-16 code-unit order instead of code point order |
| `fixtures/bad_escaped_unicode.json` | `E_CANONICAL` | A spelled as backslash-u-0041 |

## How to run

    set PYTHONUTF8=1
    D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe fixtures/generate_fixtures.py
    D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe -m unittest -v test_canonical_json
    D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe canonical_json.py fixtures/ok_basic.json fixtures/bad_crlf_terminal.json
    D:/pynq/CarlandFPGA/.local/venv/Scripts/python.exe run_evidence.py

The third command prints one PASS line and one FAIL line and exits 1; that is
the expected successful negative case, not a failed run.

## Evidence captured

`logs/evidence_summary.txt` records, for every captured subprocess, the exact
argv, cwd, exit code, expected exit code, match flag, and the byte count and
sha256 of the raw `logs/<run>.stdout.txt` / `logs/<run>.stderr.txt` files. It
also lists sha256 hashes of every deliverable and fixture byte-for-byte.
`logs/tool_version.txt` is the interpreter probe (version, executable,
platform, utf8_mode, filesystem encoding).

`cli_all_invalid` and `cli_mixed` are expected to exit 1: the validator is
supposed to reject those files. Problems are flagged by `matched=no` and a
nonzero `mismatches=` count. The unittest wall-clock line makes
`logs/unittest.stderr.txt` time-dependent; the validator PASS/FAIL stdout is
fully deterministic.

Captured on: Windows, Python 3.12.9 from the project venv, `PYTHONUTF8=1`.
