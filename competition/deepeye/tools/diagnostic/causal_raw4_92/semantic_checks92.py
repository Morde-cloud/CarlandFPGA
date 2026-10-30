"""B92 actual UART bytes through the unchanged strict semantic decoder.

Positive mode decodes every actual mode0 frame and serializes every mandatory
companion. Negative mode exercises the decoder's existing strict boundaries.
No Root, admission, planner, board, network or production path is called.
"""
from __future__ import annotations

import argparse
import binascii
import copy
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import raw4_adapter92 as adapter


W = Path(r"D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
HOST = W / ("competition/deepeye/tools/diagnostic/g05_capture/additive50_source_candidate/"
            "deepeye_transport50_source_candidate.py")
TRACE = W / "competition/deepeye/golden/codec/trace_candidate.py"
FIXTURE_KIND = adapter.FIXTURE_KIND


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return adapter.canonical(value)


def digest(value):
    return adapter.digest(value)


def load_host():
    spec = importlib.util.spec_from_file_location("b92_existing_host", HOST)
    if spec is None or spec.loader is None:
        raise RuntimeError("existing host decoder could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_trace_decoder():
    raw = TRACE.read_bytes()
    if sha(raw) != "a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642":
        raise RuntimeError("pinned TRACE decoder hash mismatch")
    spec = importlib.util.spec_from_file_location("b92_pinned_trace", TRACE)
    if spec is None or spec.loader is None:
        raise RuntimeError("pinned TRACE decoder could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def decoder_pins():
    host_raw = HOST.read_bytes()
    trace_raw = TRACE.read_bytes()
    return {
        "host_path": str(HOST),
        "host_sha256": sha(host_raw),
        "trace_path": str(TRACE),
        "trace_sha256": sha(trace_raw),
        "trace_expected_sha256": "a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642",
    }


def read_hex(path):
    text = Path(path).read_text(encoding="ascii")
    return bytes.fromhex("".join(text.split()))


def split_frames(raw):
    frames = []
    offset = 0
    while offset < len(raw):
        if len(raw) - offset < 14:
            raise ValueError("truncated outer header at byte %d" % offset)
        magic, version, kind, length, view, seq, tick_low = struct.unpack_from(
            "<2sBBBBHI", raw, offset)
        if magic != b"\xA5\x5A" or version != 3 or kind != 0xE4:
            raise ValueError("bad outer header at byte %d" % offset)
        if length > 32:
            raise ValueError("outer payload length above 32 at byte %d" % offset)
        size = 14 + length
        if offset + size > len(raw):
            raise ValueError("truncated frame at byte %d" % offset)
        frames.append(raw[offset:offset + size])
        offset += size
    return frames


def complete_frames_prefix(raw):
    """Parse complete frames and preserve earlier frames before a trailing partial."""
    frames = []
    offset = 0
    while offset < len(raw):
        if len(raw) - offset < 14:
            break
        magic, version, kind, length, view, seq, tick_low = struct.unpack_from(
            "<2sBBBBHI", raw, offset)
        if magic != b"\xA5\x5A" or version != 3 or kind != 0xE4:
            raise ValueError("bad outer header at byte %d" % offset)
        if length > 32:
            raise ValueError("outer payload length above 32 at byte %d" % offset)
        size = 14 + length
        if offset + size > len(raw):
            break
        frames.append(raw[offset:offset + size])
        offset += size
    return frames, offset


def frame_header(packet):
    return struct.unpack_from("<2sBBBBHI", packet, 0)


def refresh_timestamp(companion):
    binding = companion["binding"]
    profile = companion["profile"]
    record = {
        "origin_qpc_ns": profile["origin_qpc_ns"],
        "acquisition_qpc_ns": profile["original_acquisition_qpc_ns"],
        "source_qpc_ns": profile["original_source_qpc_ns"],
        "original_values": profile["original_values"],
        "original_indices": profile["original_indices"],
        "source_context_sha256": binding["source_context_sha256"],
    }
    profile["timestamp_record_sha256"] = digest(record)


def refresh_quality(companion):
    binding = companion["binding"]
    profile = companion["profile"]
    record = {
        "raw_quality_by_channel": profile["raw_quality_by_channel"],
        "mapped_flags_by_channel": profile["mapped_flags_by_channel"],
        "source_context_sha256": binding["source_context_sha256"],
    }
    profile["quality_record_sha256"] = digest(record)


def recalc_crc(packet):
    packet = bytearray(packet)
    packet[-2:] = binascii.crc_hqx(bytes(packet[2:-2]), 0xFFFF).to_bytes(2, "little")
    return bytes(packet)


def decode(host, packet, companion):
    return host.decode_transport(
        packet,
        binding=companion["binding"],
        profile=companion["profile"],
        now_qpc_ns=companion["evaluation_now_qpc_ns"],
        enabled=True,
        repo_root=W,
    )


def model_for(projection_path, build_manifest_sha256):
    projection = adapter.load_json_strict(Path(projection_path).read_bytes())
    return adapter.derive_model(projection, build_manifest_sha256=build_manifest_sha256)


def positive(simdir, projection_path, out, build_manifest_sha256):
    simdir = Path(simdir)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "wire").mkdir()
    (out / "companions").mkdir()
    host = load_host()
    trace_decoder = load_trace_decoder()
    if host.DECODER_SHA256 != sha(TRACE.read_bytes()):
        raise RuntimeError("pinned trace decoder hash mismatch")
    pins = decoder_pins()
    model = model_for(projection_path, build_manifest_sha256)
    summary = adapter.expected_summary(model)
    uart = read_hex(simdir / "mode0/uart.hex")
    serial = read_hex(simdir / "mode0/serializer.hex")
    if uart != serial:
        raise RuntimeError("external UART line differs from accepted serializer bytes")
    frames = split_frames(uart)
    if len(frames) != summary["frames"]:
        raise RuntimeError("frame count %d != %d" % (len(frames), summary["frames"]))
    entries = []
    wire_lengths = []
    companion_lengths = []
    invalid_count = 0
    zero_count = 0
    fresh_count = 0
    held_count = 0
    for index, (frame, lane) in enumerate(zip(frames, model["lanes"])):
        companion = adapter.companion_for_lane(model, lane, decoder_pins=pins)
        companion_raw = canonical(companion)
        wire_rel = "wire/frame%03d.bin" % index
        companion_rel = "companions/frame%03d.json" % index
        (out / wire_rel).write_bytes(frame)
        (out / companion_rel).write_bytes(companion_raw)
        wire_lengths.append(len(frame))
        companion_lengths.append(len(companion_raw))
        magic, version, kind, length, view, seq, tick_low = frame_header(frame)
        if magic != b"\xA5\x5A" or version != 3 or kind != 0xE4:
            raise RuntimeError("bad header in frame %d" % index)
        if view != adapter.VIEW or seq != lane["frame_seq"]:
            raise RuntimeError("outer view/sequence mismatch in frame %d" % index)
        if tick_low != (lane["first_tick_us"] & 0xFFFFFFFF):
            raise RuntimeError("outer tick field mismatch in frame %d" % index)
        payload = frame[12:-2]
        revision, settings, quality_byte, count, bits, session, first_index, first_tick = struct.unpack_from(
            "<BBBBBIIQ", payload, 0)
        if revision != 2 or session != adapter.SESSION or count != 1:
            raise RuntimeError("payload prefix mismatch in frame %d" % index)
        if (quality_byte & 0x03) != lane["channel"]:
            raise RuntimeError("payload channel mismatch in frame %d" % index)
        if first_index != lane["acquisition_index"] or first_tick != lane["first_tick_us"]:
            raise RuntimeError("payload acquisition identity mismatch in frame %d" % index)
        if (settings & 0x07) != 0:
            raise RuntimeError("payload E code is not E0 in frame %d" % index)
        metadata = 21 + (2 if lane["held"] else 0)
        code_bytes = len(payload) - metadata
        # The main's 3038-byte value and each per-lane size are expectations,
        # not pass conditions. Keep the measured wire bytes and report a delta.
        if not lane["valid_sample"]:
            if bits != 0 or code_bytes != 0:
                raise RuntimeError("quality-only null frame carries code in frame %d" % index)
        else:
            if bits < 16 or code_bytes != 2:
                raise RuntimeError("valid frame code section mismatch in frame %d" % index)
        view_record = decode(host, frame, companion)
        point = view_record["points"][0]
        legacy = trace_decoder.decode_payload(
            bytes([1]) + payload[1:],
            {"session": companion["binding"]["session_handle"],
             "config_epoch": view, "e": companion["binding"]["e"]})
        if legacy["count"] != 1 or len(legacy["points"]) != 1:
            raise RuntimeError("raw decoder point count mismatch in frame %d" % index)
        raw_point = legacy["points"][0]
        if view_record["status"] != "STOP" or view_record["core_ran"] is not False:
            raise RuntimeError("decoder is not structural STOP in frame %d" % index)
        if view_record["command"] is not None:
            raise RuntimeError("decoder returned a command in frame %d" % index)
        if view_record["source_identity"] != model["identity"]:
            raise RuntimeError("source identity mismatch in frame %d" % index)
        if view_record["raw_quality_uint8"] != {
                str(i): lane["record_derived_bytes"][i] for i in range(4)}:
            raise RuntimeError("raw quality mismatch in frame %d" % index)
        if point["index"] != lane["acquisition_index"]:
            raise RuntimeError("decoded acquisition index mismatch in frame %d" % index)
        if point["relative_tick_us"] != lane["first_tick_us"]:
            raise RuntimeError("decoded relative tick mismatch in frame %d" % index)
        if point["remainder_ns"] != lane["first_remainder_ns"]:
            raise RuntimeError("decoded remainder mismatch in frame %d" % index)
        if point["original_acquisition_qpc_ns"] != lane["acquisition_qpc_ns"]:
            raise RuntimeError("decoded acquisition time mismatch in frame %d" % index)
        flags = lane["record_flags"][lane["channel"]]
        for key in ("valid", "saturated", "held", "source_fault"):
            if raw_point[key] != flags[key]:
                raise RuntimeError("decoded flag %s mismatch in frame %d" % (key, index))
        if raw_point["value"] != lane["count"] if lane["valid_sample"] else raw_point["value"] is not None:
            raise RuntimeError("raw decoder value presence mismatch in frame %d" % index)
        if raw_point["source_tick_ms"] != (None if lane["source_qpc_ns"] is None else
                                           (lane["source_qpc_ns"] - model["origin_qpc_ns"]) // 1000):
            raise RuntimeError("raw decoder source tick mismatch in frame %d" % index)
        if lane["valid_sample"]:
            if point["decoded_value"] != lane["count"]:
                raise RuntimeError("decoded value mismatch in frame %d" % index)
            if point["original_value"] != lane["count"] or point["byte_exact_value"] is not True:
                raise RuntimeError("original value comparison mismatch in frame %d" % index)
            if point["source_age_ns"] != (companion["evaluation_now_qpc_ns"] -
                                          lane["source_qpc_ns"]):
                raise RuntimeError("decoded source age mismatch in frame %d" % index)
            if point["source_age_ns"] <= 100_000_000:
                raise RuntimeError("valid fixture point was relabelled fresh in frame %d" % index)
            if view_record["source_age_100ms_met"] is not False:
                raise RuntimeError("stale valid point claimed 100ms met in frame %d" % index)
            if point["original_source_qpc_ns"] != lane["source_qpc_ns"]:
                raise RuntimeError("decoded source time mismatch in frame %d" % index)
            if raw_point["source_tick_ms"] != (lane["source_qpc_ns"] - model["origin_qpc_ns"]) // 1000:
                raise RuntimeError("decoded source tick mismatch in frame %d" % index)
        else:
            invalid_count += 1
            if point["decoded_value"] is not None or point["original_value"] is not None:
                raise RuntimeError("null frame decoded as data in frame %d" % index)
            if point["source_age_ns"] is not None or point["original_source_qpc_ns"] is not None:
                raise RuntimeError("null frame carried source time in frame %d" % index)
            if point["byte_exact_value"] is not True:
                raise RuntimeError("null byte-exact comparison failed in frame %d" % index)
        if view_record["lossy_decoded_values_match_original"] is not True:
            raise RuntimeError("lossy comparison failed in frame %d" % index)
        if view_record["c29_uint12_values_possible"] is not True:
            raise RuntimeError("uint12 possibility failed in frame %d" % index)
        if view_record["frame_sha256"] != sha(frame):
            raise RuntimeError("frame hash mismatch in frame %d" % index)
        if companion["global_quality_13bits"] != lane["quality13_uint16"]:
            raise RuntimeError("global quality mismatch in frame %d" % index)
        if companion["capture"]["first_seq"] != lane["capture_first_seq"] or \
                companion["capture"]["last_seq"] != lane["capture_last_seq"]:
            raise RuntimeError("capture association mismatch in frame %d" % index)
        if companion["original_source_record_sha256"] != lane["source_record_sha256"]:
            raise RuntimeError("source record hash mismatch in frame %d" % index)
        if lane["channel"] == 3 and lane["valid_sample"] and lane["count"] == 0:
            zero_count += 1
        if lane["valid_sample"] and not lane["held"]:
            fresh_count += 1
        if lane["valid_sample"] and lane["held"]:
            held_count += 1
        entries.append({
            "frame_index": index,
            "record_index": lane["record_index"],
            "channel": lane["channel"],
            "frame_seq": lane["frame_seq"],
            "wire_path": wire_rel,
            "wire_bytes": len(frame),
            "wire_sha256": sha(frame),
            "wire_hex": frame.hex(),
            "companion_path": companion_rel,
            "companion_bytes": len(companion_raw),
            "companion_sha256": sha(companion_raw),
            "global_quality_13bits": lane["quality13_uint16"],
            "derived_quality_uint8": lane["derived_quality_uint8"],
            "flags": flags,
            "decoded_value": point["decoded_value"],
            "original_value": point["original_value"],
            "source_age_ns": point["source_age_ns"],
            "stale_by_evaluation_time": lane["stale_by_evaluation_time"],
            "acquisition_index": lane["acquisition_index"],
            "original_acquisition_qpc_ns": lane["acquisition_qpc_ns"],
            "original_source_qpc_ns": lane["source_qpc_ns"],
            "original_source_record_sha256": lane["source_record_sha256"],
            "current_source_eligible": False,
        })
    counts = {
        "invalid_frames": invalid_count,
        "valid_c3_zero_frames": zero_count,
        "fresh_valid_frames": fresh_count,
        "held_valid_frames": held_count,
    }
    for key, expected in (("invalid_frames", 9), ("valid_c3_zero_frames", 11),
                          ("fresh_valid_frames", 23), ("held_valid_frames", 48)):
        if counts[key] != expected:
            raise RuntimeError("%s %d != %d" % (key, counts[key], expected))
    cost = adapter.cost_summary(model, wire_lengths, companion_lengths)
    actual_wire = cost["wire_bytes"]
    reference_wire = summary["reference_wire_bytes"]
    explanation = ("actual equals the main 3038B expectation" if actual_wire == reference_wire else
                   "actual differs from the main expectation; per-frame sizes are retained without forcing output")
    result = {
        "schema": "B92_SEMANTIC_POSITIVE_V1",
        "evidence_kind": FIXTURE_KIND,
        "frames": len(entries),
        "counts": counts,
        "global_quality_values": sorted({entry["global_quality_13bits"] for entry in entries}),
        "actual_wire_bytes": actual_wire,
        "reference_wire_bytes": reference_wire,
        "wire_delta": actual_wire - reference_wire,
        "wire_explanation": explanation,
        "uart_equals_serializer": True,
        "all_invalid_decoded_none": True,
        "all_valid_c3_zero_decoded_zero": True,
        "all_valid_points_stale": True,
        "cost": cost,
        "decoder_pins": pins,
        "source_identity_is_fixture_namespace": True,
        "authentication": "NOT_ESTABLISHED_BY_JSON_OR_HASHES",
        "authority": {
            "actual_A_Root": "UNAVAILABLE",
            "native_em_receipt": "UNAVAILABLE",
            "admission": "UNAVAILABLE",
            "boot": "UNAVAILABLE",
            "physical_capture": "UNAVAILABLE",
            "action": "UNAVAILABLE",
            "current_source_eligible": False,
        },
        "production_default": "CLOSED",
        "aggregation": "B77 fresh-only uniform-quality triplet eligibility not used; explicit singleton E0 fallback",
        "public_budget": "no 150B/8s/compression-ratio acceptance claimed",
        "acceptance": "bounded fixture slice only; parent/A independent audit required",
    }
    (out / "FRAMES_INDEX.json").write_bytes(
        json.dumps(entries, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8") + b"\n")
    (out / "SEMANTIC_RESULT.json").write_bytes(canonical(result) + b"\n")
    print(json.dumps({
        "status": "bounded_fixture_semantic_positive_passed",
        "frames": result["frames"],
        "actual_wire_bytes": actual_wire,
        "counts": counts,
        "result": str(out / "SEMANTIC_RESULT.json"),
    }, ensure_ascii=False, sort_keys=True))
    return 0


EXPECTED_ANY = {
    "crc": ("CRC",),
    "partial": ("outer identity/length", "frame length", "CRC", "payload", "bounded packet"),
    "identity": ("full identity binding",),
    "quality_flags": ("Root quality mapping mismatch",),
    "time": ("exact original acquisition association",),
    "u63_overflow": ("original acquisition QPC", "bounded packet"),
    "nonwrap": ("local transport sequence",),
    "wrong_index": ("original index association",),
    "relative_overflow": ("relative1us acquisition tick", "relative view count/tick", "bounded packet"),
    "null_to_zero": ("invalid data remains null",),
    "zero_to_null": ("Root quality mapping mismatch",),
    "false_fresh_held": ("Root quality mapping mismatch",),
    "refreshed_source": ("held ordering", "held/fresh source association"),
    "quality_byte": ("raw uint8 quality",),
    "zero_source": ("retained source origin",),
    "wrong_view": ("outer identity/length",),
    "wrong_e": ("E",),
    "cancel_partial": ("frame length", "CRC", "payload", "bounded packet"),
}


def choose_lane(model, predicate):
    for lane in model["lanes"]:
        if predicate(lane):
            return lane
    raise RuntimeError("required fixture lane not found")


def negative(case, simdir, projection_path, build_manifest_sha256, partial_dir):
    if case not in EXPECTED_ANY:
        raise RuntimeError("unknown negative case")
    simdir = Path(simdir)
    model = model_for(projection_path, build_manifest_sha256)
    pins = decoder_pins()
    host = load_host()
    invalid_lane = choose_lane(model, lambda lane: not lane["valid_sample"] and lane["channel"] == 3)
    zero_lane = choose_lane(model, lambda lane: lane["valid_sample"] and lane["channel"] == 3 and
                            lane["count"] == 0 and not lane["held"])
    held_lane = choose_lane(model, lambda lane: lane["valid_sample"] and lane["held"])
    frames = split_frames(read_hex(simdir / "mode0/uart.hex"))
    lane = invalid_lane if case == "null_to_zero" else (
        zero_lane if case in ("zero_to_null", "wrong_e") else held_lane)
    if case == "cancel_partial":
        if partial_dir is None:
            raise RuntimeError("cancel_partial requires partial directory")
        partial_dir = Path(partial_dir)
        events = (partial_dir / "events.txt").read_text(encoding="utf-8")
        cancel_line = [line for line in events.splitlines() if line.startswith("CANCEL_PARTIAL ")]
        if len(cancel_line) != 1:
            raise RuntimeError("mode2 CANCEL_PARTIAL event missing")
        parts = cancel_line[0].split()
        serial_at_cancel = int(parts[2])
        serial_raw = read_hex(partial_dir / "serializer.hex")
        uart_raw = read_hex(partial_dir / "uart.hex")
        complete, offset = complete_frames_prefix(serial_raw)
        if len(complete) != 24:
            raise RuntimeError("mode2 did not retain 24 complete pre-cancel frames")
        serial_base = offset
        if serial_base > serial_at_cancel:
            raise RuntimeError("serializer cancellation count precedes pre-cancel base")
        partial_serial = serial_raw[serial_base:serial_at_cancel]
        partial_uart = uart_raw[serial_base:]
        if not partial_serial or len(partial_serial) >= 39:
            raise RuntimeError("mode2 partial held frame length is not partial")
        if len(partial_uart) > len(partial_serial) or partial_serial[:len(partial_uart)] != partial_uart:
            raise RuntimeError("mode2 UART bytes are not the completed prefix of serializer bytes")
        lane = choose_lane(model, lambda item: item["record_index"] == 6 and item["channel"] == 0)
        companion = adapter.companion_for_lane(model, lane, decoder_pins=pins)
        try:
            decode(host, partial_serial, companion)
        except (ValueError, AssertionError) as exc:
            reason = str(exc)
            print(json.dumps({
                "expected_rejection": case,
                "error_type": type(exc).__name__,
                "reason": reason,
                "partial_serializer_bytes": len(partial_serial),
                "partial_uart_bytes": len(partial_uart),
                "serial_base": serial_base,
                "serial_at_cancel": serial_at_cancel,
            }, ensure_ascii=False, sort_keys=True))
            return 2
        print(json.dumps({"FALSE_ACCEPT": case}, ensure_ascii=False, sort_keys=True))
        return 0
    packet = frames[lane["frame_seq"]]
    companion = adapter.companion_for_lane(model, lane, decoder_pins=pins)
    companion = copy.deepcopy(companion)
    mutated = packet
    if case == "crc":
        mutated = packet[:-1] + bytes([packet[-1] ^ 1])
    elif case == "partial":
        mutated = packet[:-3]
    elif case == "identity":
        companion["binding"]["source_context_sha256"] = "0" * 64
    elif case == "quality_flags":
        companion["profile"]["mapped_flags_by_channel"][str(lane["channel"])]["held"] = False
        refresh_quality(companion)
    elif case == "time":
        companion["profile"]["original_acquisition_qpc_ns"][0] += 1000
        refresh_timestamp(companion)
    elif case == "u63_overflow":
        companion["profile"]["original_acquisition_qpc_ns"][0] = 1 << 63
        refresh_timestamp(companion)
    elif case == "nonwrap":
        companion["binding"]["frame_seq"] = 65536
    elif case == "wrong_index":
        companion["profile"]["original_indices"][0] += 1
        refresh_timestamp(companion)
    elif case == "relative_overflow":
        mutated = bytearray(packet)
        mutated[25:33] = (1 << 32).to_bytes(8, "little")
        mutated = recalc_crc(bytes(mutated))
    elif case == "null_to_zero":
        companion["profile"]["original_values"] = [0]
        refresh_timestamp(companion)
    elif case == "zero_to_null":
        companion["profile"]["mapped_flags_by_channel"][str(lane["channel"])]["valid"] = False
        refresh_quality(companion)
    elif case == "false_fresh_held":
        companion["profile"]["mapped_flags_by_channel"][str(lane["channel"])]["held"] = False
        refresh_quality(companion)
    elif case == "refreshed_source":
        companion["profile"]["original_source_qpc_ns"][0] = lane["acquisition_qpc_ns"]
        refresh_timestamp(companion)
    elif case == "quality_byte":
        companion["profile"]["raw_quality_by_channel"][str(lane["channel"])] = 256
        refresh_quality(companion)
    elif case == "zero_source":
        companion["profile"]["original_source_qpc_ns"][0] = None
        refresh_timestamp(companion)
    elif case == "wrong_view":
        companion["binding"]["view_handle"] = adapter.VIEW + 1
    elif case == "wrong_e":
        companion["binding"]["e"] = 1
    else:
        raise RuntimeError("unhandled negative case")
    try:
        decode(host, mutated, companion)
    except (ValueError, AssertionError) as exc:
        reason = str(exc)
        if not any(token in reason for token in EXPECTED_ANY[case]):
            print(json.dumps({"unexpected_rejection": case, "reason": reason},
                             ensure_ascii=False, sort_keys=True))
            return 3
        print(json.dumps({"expected_rejection": case,
                          "error_type": type(exc).__name__,
                          "reason": reason}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps({"FALSE_ACCEPT": case}, ensure_ascii=False, sort_keys=True))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--simdir", type=Path, required=True)
    parser.add_argument("--projection", type=Path, required=True)
    parser.add_argument("--build-manifest-sha256", required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--negative", choices=sorted(EXPECTED_ANY))
    parser.add_argument("--partial-dir", type=Path)
    args = parser.parse_args(argv)
    if args.negative:
        return negative(args.negative, args.simdir, args.projection,
                        args.build_manifest_sha256, args.partial_dir)
    if args.out is None:
        parser.error("--out is required for positive mode")
    return positive(args.simdir, args.projection, args.out, args.build_manifest_sha256)


if __name__ == "__main__":
    raise SystemExit(main())
