"""Three original scans -> ingress operands; four actual TRACE frames -> UI observations."""
import argparse
import binascii
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
INPUT = ("tools/diagnostic/functional50_input113/input113.py",
         "95b46940767d3be4dbe3d885a4852119161ea5e4567ab3bda51798c39109ea49")
CODEC = ("golden/codec/trace_candidate.py",
         "a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642")
HEADER = struct.Struct("<2sBBBBHI")
FRESH = dict(valid=True, held=False, saturated=False, source_fault=False)


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def digest(data):
    return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=2)
def _pinned(specification):
    rel, expected = specification
    path = ROOT / rel
    raw = path.read_bytes()
    require(digest(raw) == expected, "dependency differs from source pin")
    name = "_demo147_" + path.stem
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def prepare_batch(originals, base_frame_seq):
    """Validate three original byte bundles at use, keeping source data independent of wire bytes."""
    require(type(originals) in (tuple, list) and len(originals) == 3, "three original scan bundles required")
    require(type(base_frame_seq) is int and 0 <= base_frame_seq <= 65532, "frame sequence would wrap")
    scans = []
    for bundle in originals:
        require(type(bundle) in (tuple, list) and len(bundle) == 3, "scan requires request, source and companions")
        scans.append(_pinned(INPUT).normalize_external_original_scan_v1(*bundle))
    first = scans[0]
    origin = first.scan["origin_qpc_ns"]
    clock = first.scan["clock_domain_id"]
    epoch = first.scan["lanes"][0]["view"]
    session = first.lineage["session_id"]
    start = first.scan["lanes"][0]["index"]
    require(session and first.lineage["tag"] and start <= 0xffffffff - 11, "invalid session/tag/index namespace")
    delta = scans[1].scan["acquisition_qpc_ns"] - first.scan["acquisition_qpc_ns"]
    require(1000 <= delta <= 65535000 and delta % 1000 == 0, "unsupported microsecond stride")
    stable = ("operation_id", "boot_id", "session_id", "tag", "tested_commit", "build_id_hex128")
    rows, receipts = [], []
    for n, scan in enumerate(scans):
        require(all(scan.lineage[k] == first.lineage[k] for k in stable), "batch lineage changed")
        require(scan.provenance["class"] == first.provenance["class"], "source class changed")
        require(scan.scan["clock_domain_id"] == clock and scan.scan["origin_qpc_ns"] == origin, "clock/origin changed")
        require(scan.association["e"] == 0, "current hardware batch specifies E=0")
        require(scan.scan["acquisition_qpc_ns"] == first.scan["acquisition_qpc_ns"] + n * delta, "irregular acquisition time")
        if n:
            require(scan.scan["scan_id_uint63"] > scans[n-1].scan["scan_id_uint63"] and
                    scan.lineage["capture_seq"] > scans[n-1].lineage["capture_seq"], "reused or unordered source scan")
        receipts.append(dict(lineage=scan.lineage, scan_id=scan.scan["scan_id_uint63"], provenance=scan.provenance,
                             request_sha256=digest(scan.request_bytes), source_sha256=digest(scan.source_bytes),
                             companion_sha256=[digest(b) for b in scan.companion_bytes],
                             retained_bytes=len(scan.request_bytes)+len(scan.source_bytes)+sum(map(len,scan.companion_bytes))))
        for ch, lane in enumerate(scan.scan["lanes"]):
            require(lane["channel"] == ch and lane["index"] == start + 4*n + ch and lane["view"] == epoch, "lane/sequence/view mismatch")
            require(lane["mapped_flags"] == FRESH and lane["source_qpc_ns"] == lane["acquisition_qpc_ns"], "unsupported flagged or held sample")
            quality = lane["root_quality_uint16"]
            require(quality <= 255 and quality == first.scan["lanes"][ch]["root_quality_uint16"], "changing or unrepresentable opaque quality")
            require(lane["acquisition_tick_us"] <= 0xffffffff, "relative clock exceeds wire width")
            rows.append(dict(channel=ch, index=lane["index"], value=lane["raw_sample_uint16"], raw_quality=quality,
                             mapped_flags=lane["mapped_flags"], native_first_seq=start+4*n, native_last_seq=start+4*n+3,
                             acquisition_qpc_ns=lane["acquisition_qpc_ns"], source_qpc_ns=lane["source_qpc_ns"],
                             tick_us=lane["acquisition_tick_us"], remainder_ns=lane["acquisition_remainder_ns"],
                             original_frame_seq=lane["frame_seq"], scan=n))
    return dict(session=session, epoch=epoch, base_frame_seq=base_frame_seq, tag=first.lineage["tag"],
                origin_qpc_ns=origin, clock_domain_id=clock, tick_stride_us=delta//1000, rows=rows, originals=receipts)


def decode_upload(originals, base_frame_seq, wire):
    """Check the actual uploaded bytes and report measurements even when valid E=0 values differ."""
    require(type(wire) is bytes and 4 * 39 <= len(wire) <= 4 * 46, "invalid four-frame wire length")
    batch = prepare_batch(originals, base_frame_seq)
    frames = []
    pos = 0
    for ch in range(4):
        require(pos + HEADER.size <= len(wire), "truncated header")
        magic, ver, kind, size, epoch, seq, tick = HEADER.unpack_from(wire, pos)
        require((magic, ver, kind) == (b"\xa5\x5a", 3, 0xe4) and 25 <= size <= 32, "invalid TRACE envelope")
        packet = wire[pos:pos + size + 14]
        require(len(packet) == size + 14, "truncated TRACE frame")
        require(binascii.crc_hqx(packet[2:-2], 0xffff) == int.from_bytes(packet[-2:], "little"), "CRC mismatch")
        require(epoch == batch["epoch"] and seq == base_frame_seq + ch, "unexpected frame sequence/epoch")
        payload = packet[12:-2]
        require(payload[0] == 2, "expected 1us layout revision 2")
        parsed = _pinned(CODEC).decode_payload(b"\x01" + payload[1:], dict(session=batch["session"], config_epoch=epoch, e=0))
        require(parsed["channel"] == ch and parsed["count"] == 3 and parsed["index_stride"] == 4 and
                parsed["tick_stride_ms"] == batch["tick_stride_us"] and parsed["first_tick_ms"] == tick,
                "channel or sample window mismatch")
        require({k:parsed[k] for k in FRESH} == FRESH, "invalid uploaded quality flags")
        points = []
        for row, point in zip(batch["rows"][ch::4], parsed["points"], strict=True):
            require(point["index"] == row["index"] and point["tick_ms"] == row["tick_us"] == point["source_tick_ms"],
                    "sample identity/time mismatch")
            points.append(dict(**row, decoded_value=point["value"], error=point["value"]-row["value"]))
        frames.append(dict(frame_seq=seq, channel=ch, mode=parsed["mode"], points=points, ledger=parsed["ledger"],
                           k=parsed["k"], frame_sha256=digest(packet), wire_bytes=len(packet)))
        pos += len(packet)
    require(pos == len(wire), "trailing UART data")
    errors = [p["error"] for frame in frames for p in frame["points"]]
    codes = sum(frame["ledger"]["stored_code_bytes"] for frame in frames)
    return dict(frames=frames, originals=batch["originals"], input_points=12,
                declared_source_class=batch["originals"][0]["provenance"]["class"], wire_sha256=digest(wire),
                raw_value_bytes=24, stored_code_bytes=codes, coding_bytes_saved=24-codes, wire_bytes=len(wire),
                wire_bytes_minus_raw=len(wire)-24, uart_8n1_bits=len(wire)*10,
                retained_original_bytes=sum(s["retained_bytes"] for s in batch["originals"]),
                max_absolute_error=max(map(abs,errors)), sample_exact=not any(errors), e_configured=0,
                source_authentication="external", clock_domain_id=batch["clock_domain_id"],
                motion_authority=False, board_verified=False)


def _read(path, limit):
    with path.open("rb") as f:
        data = f.read(limit+1)
    require(0 < len(data) <= limit, "empty or oversized " + path.name)
    return data


def read_originals(directory):
    batches = []
    for n in range(3):
        root = directory / ("scan%d" % n)
        batches.append((_read(root/"request.json",262144),_read(root/"source.bin",1048576),
                        tuple(_read(root/("companion%d.bin"%c),262144) for c in range(4))))
    return batches


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--originals", type=Path, required=True)
    cli.add_argument("--base-seq", type=lambda x:int(x,0), required=True)
    cli.add_argument("--wire",type=Path,help="actual concatenation of four uploaded packets; omit to prepare ingress operands")
    cli.add_argument("--out",type=Path,required=True)
    args = cli.parse_args()
    originals = read_originals(args.originals)
    result = (prepare_batch(originals,args.base_seq) if args.wire is None
              else decode_upload(originals,args.base_seq,_read(args.wire,184)))
    with args.out.open("x",encoding="utf8") as f:
        json.dump(result,f,indent=2,ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    main()

