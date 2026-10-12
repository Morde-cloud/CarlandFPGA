#!/usr/bin/env python3
"""Write the fixture files with explicit, byte-exact content.

The literals below are the provenance of every file under fixtures/.
test_canonical_json.py independently restates the same expected bytes and
fails if the on-disk bytes ever diverge.
"""

import pathlib

HERE = pathlib.Path(__file__).resolve().parent

FIXTURES = {
    # Valid: canonical bytes plus exactly one LF.
    "ok_basic.json": b'{"a":1,"b":[true,null]}\n',
    "ok_empty_object.json": b"{}\n",
    "ok_top_level_array.json": b"[1,2,3]\n",
    "ok_nested.json": b'{"a":{},"z":{"b":[1,2,{"c":"d"}]}}\n',
    "ok_unicode_keys.json": (
        '{"z":0,"\u00e9":1,"\u4e2d":2,"\ufffd":3,"\U00010000":4,"\U0001f600":5}\n'.encode(
            "utf-8"
        )
    ),
    "ok_escaped_newline.json": b'{"a":"x\\ny"}\n',
    "ok_numbers.json": b'{"big":123456789012345678901234567890,"f":1.5,"i":-7}\n',
    "ok_no_normalization.json": '{"a":"e\u0301","b":"\u00e9"}\n'.encode("utf-8"),
    # Invalid: one reason each, codes as in canonical_json.py.
    "bad_bom.json": b'\xef\xbb\xbf{"a":1}\n',
    "bad_invalid_utf8.json": b'{"a":"\xff"}\n',
    "bad_duplicate_key.json": b'{"a":1,"a":2}\n',
    "bad_duplicate_key_nested.json": b'{"o":{"k":1,"k":2}}\n',
    "bad_nan.json": b'{"a":NaN}\n',
    "bad_negative_infinity.json": b'[-Infinity]\n',
    "bad_surrogate_value.json": b'{"a":"\\ud800"}\n',
    "bad_surrogate_key.json": b'{"\\udfff":1}\n',
    "bad_not_json.json": b'{"a":1\n',
    "bad_raw_newline_in_string.json": b'{"a":"x\ny"}\n',
    "bad_whitespace_space.json": b'{"a": 1}\n',
    "bad_whitespace_pretty.json": b'{\n  "a": 1\n}\n',
    "bad_missing_terminal_lf.json": b'{"a":1}',
    "bad_doubled_terminal_lf.json": b'{"a":1}\n\n',
    "bad_crlf_terminal.json": b'{"a":1}\r\n',
    "bad_key_order_utf16.json": (
        '{"z":0,"\u00e9":1,"\u4e2d":2,"\U00010000":4,"\ufffd":3,"\U0001f600":5}\n'.encode(
            "utf-8"
        )
    ),
    "bad_escaped_unicode.json": b'{"a":"\\u0041"}\n',
}


def main():
    for name in sorted(FIXTURES):
        path = HERE / name
        path.write_bytes(FIXTURES[name])
        print("%s %d bytes" % (name, len(FIXTURES[name])))


if __name__ == "__main__":
    main()
