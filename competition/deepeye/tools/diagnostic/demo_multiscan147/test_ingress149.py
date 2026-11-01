"""Independent first controls of the new three-originals intake; never run an old suite."""
import argparse
import json
from pathlib import Path

from fixture147 import BASE_SEQ, VALUES, encoded, make, write
from host147 import prepare_batch, read_originals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    out = parser.parse_args().out
    out.mkdir(exist_ok=False)
    write(out/"originals")
    original = read_originals(out/"originals")
    batch = prepare_batch(original, BASE_SEQ)
    assert [row["value"] for row in batch["rows"]] == [v for scan in VALUES for v in scan]
    assert [row["index"] for row in batch["rows"]] == list(range(40,52))
    assert batch["tick_stride_us"] == 200 and all(row["remainder_ns"]==7 for row in batch["rows"])
    (out/"batch.json").write_text(json.dumps(batch,indent=2),encoding="utf8")
    checks = {}
    for label in ("mixed_boot","scope_E","sequence","quality_width","changed_source_bytes","sequence_wrap","missing_scan"):
        inputs = list(original)
        seq = BASE_SEQ
        request, source, companions = inputs[1]
        obj = json.loads(request)
        if label=="mixed_boot": obj["lineage"]["boot_id"] += "-different"
        elif label=="scope_E": obj["association"]["e"] = 2
        elif label=="sequence": obj["scan"]["lanes"][2]["index"] += 17
        elif label=="quality_width": obj["scan"]["lanes"][0]["root_quality_uint16"] = 256
        elif label=="changed_source_bytes": source = source[::-1]
        elif label=="sequence_wrap": seq = 65534
        inputs[1] = encoded(obj), source, companions
        if label=="missing_scan": inputs.pop()
        try:
            prepare_batch(inputs,seq)
        except (ValueError,RuntimeError) as exc:
            checks[label]=str(exc)
        else:
            raise AssertionError(label)
    assert len(checks)==7
    (out/"intake_checks.json").write_text(json.dumps(checks,indent=2),encoding="utf8")
    print(json.dumps(dict(status="passed",valid_rows=12,refusals=checks,synthetic=True)))


if __name__=="__main__":
    main()

