"""Offline packet-boundary controls for exact C51 source; no Root or actor."""
import argparse
import ast
import binascii
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[3]
ZIP_SHA = "9c5d1e3e86e2bf816541843ff35503c8a64c7b472f4c07efd47e72c4220b9974"
TRANSPORT_SHA = "613b10bd6b9bdc8da6c63aa9bc762df11742f86e39b4e4248f4adef8407385d6"
CODEC_SHA = "a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642"
WIRE_SHA = "7e44cb3115c2b381ac5ebc0f4155e177c6b797e6d495521e86eb76ff673efd72"
REQ = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def crc16(data):
    reg = 0xffff
    for value in data:
        reg ^= value << 8
        for _ in range(8):
            reg = ((reg << 1) ^ (0x1021 if reg & 0x8000 else 0)) & 0xffff
    return reg


def selected_decoder(archive):
    raw = archive.read_bytes()
    assert sha(raw) == ZIP_SHA
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        source = z.read("deps/raw4_proof_v1/transport.py")
    assert sha(source) == TRANSPORT_SHA
    tree = ast.parse(source)
    names = ("Invalid", "need", "digest", "frames")
    nodes = [node for node in tree.body
             if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
    assert tuple(node.name for node in nodes) == names
    selected = ast.Module(body=nodes, type_ignores=[])
    codec_path = ROOT / "golden/codec/trace_candidate.py"
    codec_bytes = codec_path.read_bytes()
    assert sha(codec_bytes) == CODEC_SHA
    spec = importlib.util.spec_from_file_location("_b174_fixed_codec", codec_path)
    codec = importlib.util.module_from_spec(spec)
    exec(compile(codec_bytes, str(codec_path), "exec"), codec.__dict__)
    namespace = dict(struct=struct, binascii=binascii, hashlib=hashlib, CODEC=codec)
    # The four C definitions are unchanged. No C dependency loader, Root,
    # registry, projector, model, actor or execution path is imported.
    exec(compile(selected, "C51.transport.exact_selected_definitions", "exec"), namespace)
    return namespace, codec, sha(ast.dump(selected, include_attributes=True).encode())


def positive_fixture(codec):
    result = []
    values = (0, 4095, 1234, 3456)
    binding = dict(session=0x10203040, config_epoch=0x2d, e=0)
    for channel, value in enumerate(values):
        point = dict(index=7, tick_ms=100, value=value, valid=True,
                     saturated=False, held=False, source_fault=False, source_tick_ms=100)
        original = codec.encode_payload([point], binding, channel)
        assert original[0] == 1 and original[3] == 1
        # Explicit synthetic E4 revision2 relative-microsecond framing.
        # This does not relabel any received/source/board packet.
        payload = bytes([2]) + original[1:]
        header = struct.pack("<2sBBBBHI", b"\xa5\x5a", 3, 0xe4,
                             len(payload), binding["config_epoch"], 0x1230 + channel, 100)
        body = header[2:] + payload
        result.append(header + payload + struct.pack("<H", crc16(body)))
    return b"".join(result), values


def inspect_negative(codec, wire):
    assert len(wire) == 171 and sha(wire) == WIRE_SHA
    pos = 0
    rows = []
    for channel in range(4):
        magic, version, kind, size, epoch, sequence, tick = struct.unpack_from("<2sBBBBHI", wire, pos)
        frame = wire[pos:pos + size + 14]
        assert (magic, version, kind) == (b"\xa5\x5a", 3, 0xe4)
        assert len(frame) == size + 14 and crc16(frame[2:-2]) == int.from_bytes(frame[-2:], "little")
        payload = frame[12:-2]
        assert payload[0] == 2 and payload[3] == 3
        session = int.from_bytes(payload[5:9], "little")
        decoded = codec.decode_payload(bytes([1]) + payload[1:],
                                       dict(session=session, config_epoch=epoch, e=0))
        assert decoded["channel"] == channel and decoded["count"] == 3
        rows.append(dict(channel=channel, count=decoded["count"],
                         values=[p["value"] for p in decoded["points"]],
                         bytes=len(frame), sequence=sequence, tick=tick))
        pos += len(frame)
    assert pos == len(wire)
    assert [r["values"] for r in rows] == [[1234,1234,1234], [40000,40001,40002],
                                           [65535,65534,65533], [0,65535,1]]
    return rows


def run(archive, original_hex, out):
    assert not out.exists()
    namespace, codec, ast_sha = selected_decoder(archive)
    frames = namespace["frames"]
    error = namespace["Invalid"]
    positive, values = positive_fixture(codec)
    accepted = frames(positive)
    assert len(accepted) == 4 and [r["point"]["value"] for r in accepted] == list(values)
    wire = bytes.fromhex(original_hex.read_text(encoding="ascii"))
    original_rows = inspect_negative(codec, wire)
    observed = []
    for name, data in [("B147_COUNT3_UNCHANGED", wire),
                       ("SINGLETON_BAD_CRC", positive[:-1] + bytes([positive[-1] ^ 1]))]:
        try:
            frames(data)
        except error as exc:
            assert str(exc) == "RAW4_CONTRADICTION"
            observed.append(dict(id=name, expected="reject", observed=str(exc)))
        else:
            raise AssertionError(name + " unexpectedly accepted")
    out.mkdir()
    (out / "positive_fixture.hex").write_text(positive.hex() + "\n", encoding="ascii")
    result = dict(work_id="B-C51-MULTISCAN-PACKET-BOUNDARY-20261101-174",
                  task_id="DEEPEYE-IMPLEMENTATION-20261014", task_version=1,
                  requirements_ids=["H%02d" % n for n in range(1,16)], requirements_sha256=REQ,
                  C_head="aa6c5abe20e3e90014e0f7cf7666472272059f3d", C_archive_sha256=ZIP_SHA,
                  C_transport_sha256=TRANSPORT_SHA, selected_ast_sha256=ast_sha, codec_sha256=CODEC_SHA,
                  controls=[dict(id="SINGLETON_SUPPORTED", expected="four values", observed=list(values))] + observed,
                  positive_wire_bytes=len(positive), positive_wire_sha256=sha(positive),
                  B147_original_wire_bytes=len(wire), B147_original_wire_sha256=sha(wire),
                  B147_original_frames=original_rows, new_fixture_is_synthetic=True,
                  scope="Only exact selected C51 packet definitions. No whole C51 projection, Root, model, actor, registry, custody or board executed.",
                  product_compatibility=False, physical_board=False, formal_acceptance=False)
    (out / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps(dict(controls_passed=3, product_compatibility=False, physical_board=False)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c51-zip", type=Path, required=True)
    parser.add_argument("--b147-hex", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.c51_zip, args.b147_hex, args.out)
