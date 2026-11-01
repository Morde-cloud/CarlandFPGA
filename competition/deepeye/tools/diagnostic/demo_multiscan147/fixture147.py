"""Produce the retained synthetic original bundles used by the one new RTL/host join."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

ORIGIN = 9007199254740993
SESSION = 0x42a50031
EPOCH = 0x2d
BASE_SEQ = 0x1200
VALUES = ((1234,40000,65535,0), (1234,40001,65534,65535), (1234,40002,65533,1))
REQ = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"


def encoded(obj):
    return json.dumps(obj, separators=(",",":"), sort_keys=True).encode()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def make(count):
    values = VALUES[count]
    tick = 100 + 200*count
    acq = ORIGIN + tick*1000 + 7
    raw = struct.pack("<4H",*values)
    companions = [encoded(dict(synthetic=True, channel=i, value=v, scan=count, clock="SIM-QPC")) for i,v in enumerate(values)]
    lanes = [dict(channel=i, raw_sample_uint16=v, root_quality_uint16=0,
                  mapped_flags=dict(valid=True,saturated=False,held=False,source_fault=False), staged_quality_uint4=1,
                  acquisition_qpc_ns=acq,acquisition_tick_us=tick,acquisition_remainder_ns=7,source_qpc_ns=acq,
                  source_tick_us=tick,source_remainder_ns=7,session=SESSION,index=40+4*count+i,view=EPOCH,
                  frame_seq=BASE_SEQ+4*count+i) for i,v in enumerate(values)]
    req = dict(schema="B113_EXTERNAL_ORIGINAL_SCAN_REQUEST_V1",
               task=dict(task_id="DEEPEYE-IMPLEMENTATION-20261014",task_version=1,work_id="B147-SYNTHETIC",requirements_sha256=REQ),
               source_provenance={"class":"SYNTHETIC_TEST","declared_by":"B147-TB","source_note":"Independent 3x4 literals",
                                  "mapping_state":"B_NEUTRAL_AWAITING_A_MAPPING"},
               source_payload=dict(format_label="SYNTHETIC_LE_4xUINT16",bytes=len(raw),sha256=sha(raw)),
               scan=dict(scan_id_uint63=700+count,origin_qpc_ns=ORIGIN,acquisition_qpc_ns=acq,clock_domain_id="SIM-QPC",lanes=lanes),
               lineage=dict(operation_id="B147-SYNTHETIC",request_id="B147-scan-"+str(count),request_hash=sha(raw),
                            tested_commit="0"*40,build_id_hex128="0"*32,boot_id="SYNTHETIC-NO-BOARD",session_id=SESSION,
                            tag=0x51,trigger_id=80+count,generation=2,request_seq=10+count,capture_seq=20+count),
               association=dict(profile_id="demo147-E0",binding_receipt_id="sim-only",e=0,source_context_sha256=sha(raw),
                                timestamp_record_sha256=sha(str(acq).encode()),quality_record_sha256=sha(bytes(4)),
                                receiver_qpc_ns=acq+1000,evaluation_now_qpc_ns=acq+2000,receiver_clock_id="SIM-QPC",
                                evaluation_clock_id="SIM-QPC",freshness_limit_ns=100000000),
               companions=[dict(channel=i,format_label="SIM_POINT",bytes=len(b),sha256=sha(b)) for i,b in enumerate(companions)])
    return encoded(req),raw,companions


def write(directory):
    directory.mkdir(exist_ok=False)
    for n in range(3):
        p=directory/("scan%d"%n)
        p.mkdir()
        request,source,companions=make(n)
        (p/"request.json").write_bytes(request)
        (p/"source.bin").write_bytes(source)
        for ch,b in enumerate(companions):
            (p/("companion%d.bin"%ch)).write_bytes(b)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",required=True,type=Path)
    write(parser.parse_args().out)

