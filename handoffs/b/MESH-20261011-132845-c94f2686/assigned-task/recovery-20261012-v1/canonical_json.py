#!/usr/bin/env python3
r"""Byte-level validator for the project canonical-JSON fixture convention.

This is a Python fixture convention, NOT RFC 8785 (JCS). A file is valid if
and only if its bytes are exactly:

    json.dumps(value, ensure_ascii=False, sort_keys=True,
               separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"

where value is the JSON document parsed from the same bytes with these hard
rejections applied first:

* no BOM: the file must start with strict UTF-8 data, never EF BB BF;
* no duplicate keys in any object, at any nesting depth;
* no non-finite numbers (NaN, Infinity, -Infinity);
* no unpaired surrogate code points in any string (keys or values).

Properties that follow from the definition:

* no Unicode normalization: NFC and NFD sequences stay distinct;
* object keys are sorted by Python string comparison = Unicode code point
  order (astral code points sort after every BMP code point; not UTF-16
  code-unit order, not RFC 8785 ordering);
* separators are "," and ":" with no whitespace between tokens;
* exactly one trailing LF byte; CRLF, a missing terminal LF and a doubled
  terminal LF are invalid;
* escapes are re-encoded by Python: a string spelled "\u0041" is not
  canonical (it re-encodes as "A"), while an escaped newline stays escaped
  ("\n" in the file is the two characters backslash + n);
* numbers are rendered by Python repr: "1.5" stays "1.5", while "1e2" is
  not canonical because it re-encodes as "100.0".

CLI (read-only; never writes to any path):

    python canonical_json.py PATH [PATH ...]

prints one deterministic line per path, in argument order:

    PASS <path>
    FAIL <path> <CODE> <detail>

Exit status: 0 = every path valid, 1 = at least one path invalid,
2 = usage error (no paths given).
"""

from __future__ import annotations

import json
import math
import sys

E_IO = "E_IO"
E_UTF8 = "E_UTF8"
E_BOM = "E_BOM"
E_JSON = "E_JSON"
E_DUPKEY = "E_DUPKEY"
E_NONFINITE = "E_NONFINITE"
E_SURROGATE = "E_SURROGATE"
E_NEWLINE = "E_NEWLINE"
E_CANONICAL = "E_CANONICAL"

BOM_UTF8 = b"\xef\xbb\xbf"
LF = b"\n"

_DUMPS_OPTIONS = {
    "ensure_ascii": False,
    "sort_keys": True,
    "separators": (",", ":"),
    "allow_nan": False,
}


class _DuplicateKeyError(Exception):
    """Raised while parsing when one object repeats a key."""


class _NonFiniteError(Exception):
    """Raised while parsing when a non-finite number appears."""


def _object_pairs_hook(pairs):
    seen = set()
    for key, _value in pairs:
        if key in seen:
            raise _DuplicateKeyError(key)
        seen.add(key)
    return dict(pairs)


def _parse_constant(name):
    raise _NonFiniteError(name)


def _parse_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise _NonFiniteError(text)
    return value


def canonical_body_bytes(value):
    """Canonical JSON payload bytes, without the trailing LF."""
    return json.dumps(value, **_DUMPS_OPTIONS).encode("utf-8")


def canonical_bytes(value):
    """Canonical file bytes for an already parsed value: payload + one LF."""
    return canonical_body_bytes(value) + LF


def find_unpaired_surrogate(value):
    """Return the first unpaired surrogate found in value, else None."""
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            for character in item:
                if 0xD800 <= ord(character) <= 0xDFFF:
                    return character
        elif isinstance(item, dict):
            for key, entry in item.items():
                stack.append(key)
                stack.append(entry)
        elif isinstance(item, list):
            stack.extend(item)
    return None


def _first_difference(actual, expected):
    limit = min(len(actual), len(expected))
    for offset in range(limit):
        if actual[offset] != expected[offset]:
            return offset
    return limit


def validate_bytes(data):
    """Validate raw file bytes; return None or a (CODE, detail) tuple."""
    if data.startswith(BOM_UTF8):
        return (E_BOM, "utf-8 byte order mark at offset 0")

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return (E_UTF8, "invalid utf-8 byte at offset %d" % exc.start)

    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_pairs_hook,
            parse_constant=_parse_constant,
            parse_float=_parse_float,
        )
    except RecursionError:
        return (E_JSON, "json nesting exceeds interpreter limit")
    except _DuplicateKeyError as exc:
        return (E_DUPKEY, "duplicate object key %r" % (exc.args[0],))
    except _NonFiniteError as exc:
        return (E_NONFINITE, "non-finite number %s" % (exc.args[0],))
    except ValueError as exc:
        if isinstance(exc, json.JSONDecodeError):
            return (
                E_JSON,
                "invalid json at line %d column %d: %s"
                % (exc.lineno, exc.colno, exc.msg),
            )
        return (E_JSON, "invalid json: %s" % exc)

    surrogate = find_unpaired_surrogate(value)
    if surrogate is not None:
        return (E_SURROGATE, "unpaired surrogate code point U+%04X" % ord(surrogate))

    try:
        body = canonical_body_bytes(value)
    except RecursionError:
        return (E_JSON, "json nesting exceeds interpreter limit")
    expected = body + LF
    if data == expected:
        return None
    if data == body:
        return (E_NEWLINE, "missing terminal lf")
    if data == body + LF + LF:
        return (E_NEWLINE, "doubled terminal lf")
    if data.endswith(b"\r\n") and data[:-2] == body:
        return (E_NEWLINE, "crlf terminal line ending")

    offset = _first_difference(data, expected)
    return (
        E_CANONICAL,
        "not canonical: first difference at byte offset %d (got %d bytes, expected %d)"
        % (offset, len(data), len(expected)),
    )


def validate_path(path):
    """Read one path (read-only) and validate it."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        return (E_IO, "cannot read file: %s" % (exc.strerror or exc,))
    return validate_bytes(data)


def main(argv=None):
    if argv is None:
        argv = sys.argv
    paths = argv[1:]
    if not paths:
        sys.stderr.buffer.write(b"usage: canonical_json.py PATH [PATH ...]\n")
        sys.stderr.buffer.flush()
        return 2
    failed = False
    out = sys.stdout.buffer
    for path in paths:
        failure = validate_path(path)
        if failure is None:
            line = "PASS %s\n" % path
        else:
            failed = True
            line = "FAIL %s %s %s\n" % (path, failure[0], failure[1])
        out.write(line.encode("utf-8"))
    out.flush()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
