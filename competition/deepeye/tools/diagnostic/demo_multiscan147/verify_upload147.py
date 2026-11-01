"""Check actual captured byte stream using independent values and focused refusal controls."""
import argparse
import copy
import json
from pathlib import Path

from fixture147 import BASE_SEQ, VALUES, write
from host147 import decode_upload, read_originals


def verify(wire, directory):
    directory.mkdir(exist_ok=False)
    write(directory/"originals")
    originals = read_originals(directory/"originals")
    result = decode_upload(originals, BASE_SEQ, wire)
    (directory/"wire.bin").write_bytes(wire)
    (directory/"decoded.json").write_text(json.dumps(result,indent=2), encoding="utf8")
    got = [[frame["points"][i]["decoded_value"] for frame in result["frames"]] for i in range(3)]
    assert got == list(map(list,VALUES)) and result["max_absolute_error"] == 0
    modes = [f["mode"] for f in result["frames"]]
    assert "rice" in modes and "raw" in modes and sum(f["wire_bytes"] for f in result["frames"]) == len(wire)
    assert sum(f["ledger"]["selected_raw_bytes"] for f in result["frames"]) == 24
    first_size = result["frames"][0]["wire_bytes"]
    second_size = result["frames"][1]["wire_bytes"]
    corrupt = bytearray(wire)
    corrupt[20] ^= 1
    cases = {}
    for label, packet in (("crc", bytes(corrupt)), ("truncated",wire[:-1]),
                          ("swapped",wire[first_size:first_size+second_size]+wire[:first_size]+wire[first_size+second_size:])):
        try:
            decode_upload(originals,BASE_SEQ,packet)
        except ValueError as exc:
            cases[label] = str(exc)
        else:
            raise AssertionError("accepted " + label)
    # A structurally valid receipt whose decoded value differs remains visible as an error.
    # Change a caller-declared lane and matching source/companion bytes coherently.
    from fixture147 import encoded, sha
    import struct
    altered=copy.deepcopy(originals)
    req,raw,comp=altered[0]
    doc=json.loads(req)
    doc["scan"]["lanes"][0]["raw_sample_uint16"]=1235
    raw=struct.pack("<4H",1235,*VALUES[0][1:])
    doc["source_payload"]["sha256"]=sha(raw)
    comp=list(comp)
    cd=json.loads(comp[0]);cd["value"]=1235;comp[0]=encoded(cd)
    doc["companions"][0].update(sha256=sha(comp[0]),bytes=len(comp[0]))
    doc["association"]["source_context_sha256"]=sha(raw)
    altered[0]=(encoded(doc),raw,tuple(comp))
    mismatch=decode_upload(altered,BASE_SEQ,wire)
    assert not mismatch["sample_exact"] and mismatch["max_absolute_error"]==1
    assert mismatch["frames"][0]["points"][0]["decoded_value"]==1234
    (directory/"declared_mismatch.json").write_text(json.dumps(mismatch,indent=2),encoding="utf8")
    summary=dict(input="synthetic 3 scans x 4 uint16",modes=modes,points=got,negative=cases,
                 max_abs_error=result["max_absolute_error"],mismatch_detected=mismatch["max_absolute_error"],
                 raw_value_bytes=24,wire_bytes=len(wire),stored_code_bytes=result["stored_code_bytes"],
                 simulator_only=True,board=False)
    (directory/"checks.json").write_text(json.dumps(summary,indent=2),encoding="utf8")
    return summary


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--wire",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    with a.wire.open("rb") as f:
        wire=f.read(185)
    print(json.dumps(verify(wire,a.out)))

