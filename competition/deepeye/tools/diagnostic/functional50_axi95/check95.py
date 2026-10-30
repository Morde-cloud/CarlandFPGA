"""NEW102 strict recovery checker; main correction, actual AXI/TX/RX/FIFO."""
from __future__ import annotations

import argparse
import binascii
import copy
import hashlib
import importlib.util
import json
import re
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True

W = Path(__file__).resolve().parents[5]
REL = "competition/deepeye/tools/diagnostic/functional50_axi95/"
BENCH_REL = "competition/deepeye/fpga/diagnostic/functional50_axi95/tb_deepeye_trace50_axi95.sv"
HOST_REL = "competition/deepeye/tools/diagnostic/g05_capture/additive50_source_candidate/deepeye_transport50_source_candidate.py"
TRACE_REL = "competition/deepeye/golden/codec/trace_candidate.py"
SCHEMA74_REL = "competition/deepeye/tools/diagnostic/offboard_codec74/semantic_controls.py"

REQUIREMENTS = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
FREEZE = "1011259415a0916054eb580687612580bc1e5f09"
ORIGIN = 27001348289300
EVALUATION_NOW = ORIGIN + 1_200_000_000
RECEIVER = ORIGIN + 200_000_000
SESSION = 0x95345678
VIEW = 0x95
TAG = 0x95
SOURCE_RUNTIME_COMMIT = "4dc91fd24531b3df53fc916e8b7f509ad524592c"
EXPECTED_A18_SHA = "63616e2915edc5a2ef6ed592e8f9830ce77a635aaf883ab964aa4dbd5fd1910c"
EXPECTED_A18_BYTES = 82496
EXPECTED_PINS_SHA = "43aeca421a1c86ddc8f3d2a16558062a92592af8478d9ca2161920d7f2d82d93"
EXPECTED_INDEPENDENT_SHA = "03a3d996ff30d64bda53c71242f8ad3025216fdfbd611e26a6e62fa56f9d0bc4"
EXPECTED_SCOPE_SHA = "6a86000e97d1571c0b7b89b9d3cf7facb11d2b6a06455eb1d53e0637676b6bc4"
EXPECTED_FINAL_DESIGN_SHA = "e8ccda9a704b4a81c99bde69e14ff3f9a23b853bc89000ce6c99b33a97ac5806"
EXPECTED_REVIEW_SHA = "d749473d98e2288a01078dfef8f296c789f203fb65723237b0f6ca1efa6452d0"
EXPECTED_DISPATCH_SHA = "a4d3e9409f1df3227eb61bd59c71ed83098f08d107689fc767cf7eda11b55196"
EXPECTED_RECEIPT_SHA = "8fd27fae2ac9e07687a9d8318086e94a6f9e8e9d6ad5475aa34cb45147fe4b6a"
EXPECTED_HOST_SHA = "1f4da870d9c885a3cc6156c30d2170e21001187392a59a19172c059c9ab0c768"
EXPECTED_TRACE_SHA = "a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642"
EXPECTED_SCHEMA74_SHA = "935e0aac46a52a81999fc25775a9e88c6ed49c204c973aaf4db8a15ff363dba3"
EXPECTED_CORRECTION_SHA = "46aca72f0d4e10fb0bb7858a1328d15e9d7203dff2f5f94753041b39e3bc8396"

SOURCE_PINS = {
    "competition/deepeye/fpga/diagnostic/functional50_board94/deepeye_trace50_axi94.sv": "9697494e1694ba84708b40542fd8b4ee2544bd85bd763b1104e695441d57c6e7",
    "competition/deepeye/fpga/diagnostic/functional50_board94/register_map.json": "3ad9a9c1c6f7d69c173d471bb77ffcc6ead76490598a8da5efa0861600aa0c70",
    "competition/deepeye/fpga/diagnostic/functional50_board94/README.md": "38ac64a6d28d0934c11a6d71706e56fd5638374b944040f85cc62c3448f9aace",
    "competition/deepeye/fpga/diagnostic/functional50_board94/vectors_UNEXECUTED.json": "64318aef4af48bb59d246b56a1d068f06935ef894c3523400448d2e8aa4e1dde",
    "competition/deepeye/fpga/diagnostic/offboard_codec74/deepeye_SYNTHETIC_codec74_fixture.sv": "409ee484113fa4006eb27e12554a4db57708df5e7dadf269548f546d03931a6a",
    "competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_uart_50mhz_candidate.sv": "41ea63819c892ec67fe92d6e9338a771d5f93f60d0976e895f18bc97966283d2",
    "competition/deepeye/fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_payload_1us_candidate.sv": "5ebe65dfe0844aab62365e8664507f153cb75ff47b3c8d4e10f45356e94147a8",
    "competition/deepeye/fpga/codec/deepeye_trace_payload_candidate.sv": "fb64ace453c451838110c81bf6cb4a815a96fb2668e28a306ff699beca5acef6",
    "competition/deepeye/fpga/codec/deepeye_block_encoder.sv": "4cb79428ef89096742e293516c4696caf985048d8185f531fe92eaa485c8d532",
    "competition/deepeye/fpga/acquisition/deepeye_buffered_scan_capture.sv": "c8a540db8122b8f5520582a0f1fa9be0c43cb54a62f03c7c4edc893906f28411",
    "competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv": "fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d",
    "competition/deepeye/fpga/acquisition/deepeye_raw_scan_queue.sv": "630e14803d82b3379517d91626de4ad7e7d3c509ad14363b3164031a5f633ee4",
    "competition/deepeye/fpga/acquisition/deepeye_scan_lane_stream.sv": "b3c9d2024d9325191538cf08fec9a652ff8ff0ae316ec9af96078f85cf5be3cc",
    "competition/deepeye/fpga/transport/deepeye_wire_serializer.sv": "efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885",
    "competition/deepeye/fpga/transport/deepeye_crc16_byte.sv": "8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f",
    "competition/deepeye/fpga/transport/deepeye_uart_tx.sv": "5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47",
    "competition/deepeye/fpga/transport/deepeye_uart_rx.sv": "935f5d02008535fd5da75b7dc80696d14b03bd54d85f8b52fbf12c1e0504f08f",
    HOST_REL: EXPECTED_HOST_SHA,
    TRACE_REL: EXPECTED_TRACE_SHA,
    SCHEMA74_REL: EXPECTED_SCHEMA74_SHA,
}

RECORD_KEYS = {"adc_tick_ms", "em_tick_ms", "channel_counts", "channel_values",
               "quality", "profile_id", "profile_note", "profile_status", "source_mode"}


def need(ok, why):
    if not ok:
        raise RuntimeError(why)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return sha(canonical(value))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("non-finite JSON constant " + value)


def load_json_strict(raw):
    need(type(raw) is bytes and not raw.startswith(b"\xef\xbb\xbf"), "strict JSON bytes")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant)
    except Exception as exc:
        raise RuntimeError("strict JSON: " + str(exc)) from exc


def record(path):
    path = Path(path)
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": sha(raw)}


def write_new(path, raw):
    path = Path(path)
    with path.open("xb") as stream:
        stream.write(raw)


def load_module(name, path, pin):
    path = Path(path)
    need(sha(path.read_bytes()) == pin, "unchanged decoder pin " + path.name)
    spec = importlib.util.spec_from_file_location(name, path)
    need(spec is not None and spec.loader is not None, "decoder import spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def derive_flags(quality, counts, em_tick, adc_tick):
    need(type(quality) is int and 0 <= quality <= 0x1FFF, "quality uint13")
    need((quality & 0xE000) == 0 and (quality & 0x0800) == 0,
         "quality reserved bits")
    em_bits = [bool(quality & (1 << i)) for i in range(3)]
    need(all(em_bits) or not any(em_bits), "EM validity all-or-none")
    em_valid = all(em_bits)
    source_fault = bool(quality & 0x1000)
    need(source_fault == (not em_valid), "source-fault inverse EM validity")
    held_bits = [bool(quality & (1 << (8 + i))) for i in range(3)]
    need(all(held_bits) or not any(held_bits), "held bits all-or-none")
    held_em = all(held_bits)
    if em_valid:
        need(type(em_tick) is int and em_tick % 50 == 0 and em_tick <= adc_tick,
             "valid EM tick")
        need(held_em == (em_tick < adc_tick), "held flag matches EM age")
    else:
        need(em_tick is None and not held_em, "invalid EM shape")
    valid = [bool(quality & (1 << i)) for i in range(4)]
    saturated = [bool(quality & (1 << (4 + i))) for i in range(4)]
    held = [held_em if i < 3 else False for i in range(4)]
    derived = []
    for channel in range(4):
        count = counts[channel]
        if not valid[channel]:
            need(count is None and not saturated[channel] and not held[channel],
                 "invalid channel shape")
        else:
            need(type(count) is int and 0 <= count <= 4095, "valid count uint12")
        fault = source_fault if channel < 3 else False
        derived.append((1 if valid[channel] else 0) |
                       (2 if saturated[channel] else 0) |
                       (4 if held[channel] else 0) |
                       (8 if fault else 0))
    return {"valid": valid, "saturated": saturated, "held": held,
            "source_fault": source_fault, "derived": derived}


def validate_record(a18, position, counts, quality, source_count,
                    canonical_bytes, source_sha, completion, finish):
    record_value = a18["records"][position]
    book = a18["original_source_book"]["samples"][position]
    need(set(record_value) == RECORD_KEYS, "A18 record keys")
    need(record_value["channel_counts"] == counts, "A18 counts")
    need(record_value["quality"] == quality, "A18 quality")
    need(record_value["adc_tick_ms"] == position * 10, "A18 ADC tick")
    need(record_value["channel_values"].__class__ is list and
         len(record_value["channel_values"]) == 4, "A18 private value shape")
    for channel, number in enumerate(record_value["channel_values"]):
        need((number is None) == (counts[channel] is None), "A18 null association")
    need(book["payload"] == record_value, "canonical book payload association")
    payload_bytes = bytes.fromhex(book["canonical_source_hex"])
    need(len(payload_bytes) == canonical_bytes, "A18 canonical payload size")
    need(sha(payload_bytes) == source_sha == book["source_sha256"],
         "A18 canonical payload hash")
    need(load_json_strict(payload_bytes) == record_value, "A18 canonical payload JSON")
    need(book["source_count"] == source_count and book["tick_ms"] == position * 10,
         "A18 source count/tick")
    need(book["nominal_qpc_ns"] == ORIGIN + position * 10_000_000,
         "A18 nominal time")
    need(a18["actual_record_end_qpc_ns"][position] == completion,
         "A18 completion fact")
    need(book["finish_qpc_ns"] == finish, "A18 raw finish fact")
    need(book["held_em_association"] ==
         "unavailable;original_native_em_association_not_implemented",
         "missing original EM association retained")
    flags = derive_flags(quality, counts, record_value["em_tick_ms"],
                         record_value["adc_tick_ms"])
    return record_value, book, flags


def split_frames(raw):
    frames = []
    offset = 0
    while offset < len(raw):
        need(len(raw) - offset >= 14, "outer header bound")
        magic, version, kind, payload_len, view, sequence, tick = struct.unpack_from(
            "<2sBBBBHI", raw, offset)
        size = 14 + payload_len
        need(magic == b"\xA5\x5A" and version == 3 and kind == 0xE4 and
             payload_len <= 32 and offset + size <= len(raw), "outer frame shape")
        packet = raw[offset:offset + size]
        need(struct.unpack_from("<H", packet, size - 2)[0] ==
             binascii.crc_hqx(packet[2:-2], 0xFFFF), "outer CRC")
        frames.append(packet)
        offset += size
    need(offset == len(raw), "exact outer frame consumption")
    return frames


def recompute_time_hash(companion):
    binding = companion["binding"]
    profile = companion["profile"]
    profile["timestamp_record_sha256"] = digest({
        "origin_qpc_ns": profile["origin_qpc_ns"],
        "acquisition_qpc_ns": profile["original_acquisition_qpc_ns"],
        "source_qpc_ns": profile["original_source_qpc_ns"],
        "original_values": profile["original_values"],
        "original_indices": profile["original_indices"],
        "source_context_sha256": binding["source_context_sha256"],
    })


def run(out):
    out = Path(out).resolve()
    decoded = out / "decoded"
    decoded.mkdir(exist_ok=False)

    required = {
        "source_before": out / "SOURCE_BEFORE.json",
        "a18": out / "inputs" / "retired-source70.json",
        "pins": out / "inputs" / "PINS.json",
        "independent": out / "inputs" / "A18_INDEPENDENT_DATA.json",
        "scope": out / "inputs" / "immutable_scope_pinned.json",
        "final_design": out / "inputs" / "BOARD50_95_MAIN_FINAL_DESIGN.md",
        "review": out / "inputs" / "BOARD50_95_MAIN_REVIEW.json",
        "dispatch": out / "inputs" / "BOARD50_95R1_DISPATCH_DECISION.json",
        "receipt": out / "inputs" / "BOARD50_95R1_DISPATCH_RECEIPT.json",
        "correction": out / "inputs" / "BOARD50_102_MAIN_QUALITY_CORRECTION.json",
        "original_false_observation": out / "inputs" / "SPEC_OBSERVATION_QUALITY.json",
        "uart": out / "sim" / "uart.hex",
        "pop": out / "sim" / "pop.hex",
        "events": out / "sim" / "events.txt",
        "modelsim": out / "sim" / "modelsim.log",
    }
    for name, path in required.items():
        need(path.is_file(), "required checker input " + name)

    fixed_input_pins = {
        "a18": (EXPECTED_A18_BYTES, EXPECTED_A18_SHA),
        "pins": (3876, EXPECTED_PINS_SHA),
        "independent": (12869, EXPECTED_INDEPENDENT_SHA),
        "scope": (6684, EXPECTED_SCOPE_SHA),
        "final_design": (9240, EXPECTED_FINAL_DESIGN_SHA),
        "review": (7453, EXPECTED_REVIEW_SHA),
        "dispatch": (1212, EXPECTED_DISPATCH_SHA),
        "receipt": (879, EXPECTED_RECEIPT_SHA),
        "correction": (1253, EXPECTED_CORRECTION_SHA),
    }
    for name, (size, pin) in fixed_input_pins.items():
        info = record(required[name])
        need(info["bytes"] == size and info["sha256"] == pin,
             "fixed input pin " + name)

    for relative, pin in SOURCE_PINS.items():
        need(sha((W / relative).read_bytes()) == pin,
             "snapshot source pin " + relative)
    source_before = load_json_strict(required["source_before"].read_bytes())
    for relative, pin in SOURCE_PINS.items():
        entry = source_before.get(relative)
        need(entry is not None and entry["snapshot"]["sha256"] == pin,
             "SOURCE_BEFORE pin " + relative)

    scope = load_json_strict(required["scope"].read_bytes())
    requirements = scope.get("requirements")
    need(type(requirements) is list and len(requirements) == 15,
         "H01-H15 requirement array")
    need([item.get("id") for item in requirements] ==
         ["H%02d" % i for i in range(1, 16)], "H01-H15 identity order")
    need(sha(canonical(requirements)) == REQUIREMENTS,
         "canonical requirements hash")

    correction = load_json_strict(required["correction"].read_bytes())
    need(correction["quality13"] == 1807 and
         correction["correct_derived_quality"] == [5, 5, 5, 1] and
         correction["bit2_of_byte5"] is True and
         all(not f["saturated"] for f in correction["flags"]),
         "main102 exact quality correction")
    # Retain the cancelled worker's false claim only as failure provenance.
    # Never import it as a semantic oracle or require it to be true.
    false_observation_provenance = record(required["original_false_observation"])

    a18 = load_json_strict(required["a18"].read_bytes())
    need(a18["source_origin_qpc_ns"] == ORIGIN, "A18 origin")
    need(a18["requirements_sha256"] == REQUIREMENTS, "A18 requirements pin")
    need(a18["source_commit"] == SOURCE_RUNTIME_COMMIT, "A18 source-runtime commit")
    need(a18["original_source_book"]["schema"] == 1 and
         a18["original_source_book"]["state"] == "RETIRED" and
         a18["original_source_book"]["native_interval_atomic"] is False,
         "A18 schema1 retired non-atomic")
    need(len(a18["records"]) == 20 and
         len(a18["original_source_book"]["samples"]) == 20 and
         len(a18["actual_record_end_qpc_ns"]) == 20, "A18 exact 20 records")
    missing = list(a18["missing_evidence"])
    for item in ("original_EM_scope_call_receipt", "verified_board_BOOT",
                 "original_admission_and_board_capture_times"):
        need(item in missing, "historical evidence remains missing: " + item)

    pins = load_json_strict(required["pins"].read_bytes())
    need(type(pins) is list and len(pins) == 2 and pins[0]["sha256"] == EXPECTED_A18_SHA,
         "A18 PINS list")
    independent = load_json_strict(required["independent"].read_bytes())
    need(independent["original_file_sha256"] == EXPECTED_A18_SHA and
         independent["original_source_origin_qpc_ns"] == ORIGIN,
         "independent A18 pin")
    for index, counts, quality, completion in (
        (0, [3011, 1924, 2002, None], 7, 27001355219600),
        (9, [2982, 2021, 1966, 0], 1807, 27001440690300),
    ):
        row = independent["rows"][index]
        need(row["index"] == index and row["counts"] == counts and
             row["quality"] == quality and
             row["original_record_end_qpc_ns"] == completion,
             "independent A18 row %d" % index)

    rec0, book0, flags0 = validate_record(
        a18, 0, [3011, 1924, 2002, None], 7, 1, 355,
        "4cc106acee6c26a9ec089b6e2c85ddce2b1146a6186637ec2a4cbab8d298c2cd",
        27001355219600, 27001355126400)
    rec9, book9, flags9 = validate_record(
        a18, 9, [2982, 2021, 1966, 0], 1807, 10, 375,
        "90bf38cfd2823c5a426fa2f080e43e24d4df5f14dd2e80365a54cadeea06ad14",
        27001440690300, 27001440598500)
    need(flags0["derived"] == [1, 1, 1, 0], "record0 derived qualities")
    need(flags9["derived"] == [5, 5, 5, 1], "record9 derived qualities")

    lanes = []
    for record_index, first_sequence, tag in ((0, 950, 0x9501), (9, 954, 0x9502)):
        record_value = a18["records"][record_index]
        flags = flags0 if record_index == 0 else flags9
        acquisition = ORIGIN + record_value["adc_tick_ms"] * 1_000_000
        for channel in range(4):
            valid = flags["valid"][channel]
            held = flags["held"][channel]
            if valid and held:
                source = ORIGIN + record_value["em_tick_ms"] * 1_000_000
            else:
                source = acquisition if valid else None
            count = record_value["channel_counts"][channel]
            lanes.append({
                "record_index": record_index,
                "channel": channel,
                "first_index": record_index * 4 + channel,
                "frame_seq": first_sequence + channel,
                "tag": tag,
                "adc_tick_ms": record_value["adc_tick_ms"],
                "em_tick_ms": record_value["em_tick_ms"],
                "acquisition_qpc_ns": acquisition,
                "source_qpc_ns": source,
                "relative_tick_us": record_value["adc_tick_ms"] * 1000,
                "source_tick_us": None if source is None else (source - ORIGIN) // 1000,
                "count": count,
                "valid": valid,
                "saturated": flags["saturated"][channel],
                "held": held,
                "source_fault": flags["source_fault"] if channel < 3 else False,
                "derived_quality": flags["derived"][channel],
                "record_derived_quality": list(flags["derived"]),
                "record_flags": [
                    {"valid": flags["valid"][i],
                     "saturated": flags["saturated"][i],
                     "held": flags["held"][i],
                     "source_fault": flags["source_fault"] if i < 3 else False}
                    for i in range(4)
                ],
                "global_quality": record_value["quality"],
                "source_record_sha256": (book0 if record_index == 0 else book9)["source_sha256"],
                "canonical_source_payload_bytes": len(bytes.fromhex((book0 if record_index == 0 else book9)["canonical_source_hex"])),
                "canonical_source_payload_sha256": (book0 if record_index == 0 else book9)["source_sha256"],
                "canonical_source_bytes": bytes.fromhex((book0 if record_index == 0 else book9)["canonical_source_hex"]),
                "expected_wire_bytes": 35 if not valid else (39 if held else 37),
            })
    need(len(lanes) == 8, "eight fixture lanes")
    need([lane["first_index"] for lane in lanes] ==
         [0, 1, 2, 3, 36, 37, 38, 39], "fixture first indices")

    request_hash = digest({
        "kind": "B95_SELECTED_A18_RECORD_PROJECTION_V1",
        "origin_qpc_ns": ORIGIN,
        "records": [
            {"record_index": 0, "adc_tick_ms": rec0["adc_tick_ms"],
             "em_tick_ms": rec0["em_tick_ms"], "channel_counts": rec0["channel_counts"],
             "quality": rec0["quality"], "canonical_payload_bytes": 355,
             "source_record_sha256": book0["source_sha256"],
             "record_completion_qpc_ns": 27001355219600,
             "raw_finish_qpc_ns": 27001355126400},
            {"record_index": 9, "adc_tick_ms": rec9["adc_tick_ms"],
             "em_tick_ms": rec9["em_tick_ms"], "channel_counts": rec9["channel_counts"],
             "quality": rec9["quality"], "canonical_payload_bytes": 375,
             "source_record_sha256": book9["source_sha256"],
             "record_completion_qpc_ns": 27001440690300,
             "raw_finish_qpc_ns": 27001440598500},
        ],
    })
    capture_hash = digest({"kind": "B95_FIXTURE_CAPTURE_V1", "lanes": [
        {k: v for k, v in lane.items() if k != "canonical_source_bytes"} for lane in lanes]})
    build_manifest_sha256 = sha(required["source_before"].read_bytes())
    identity = {
        "operation_id": "FIXTURE95-RETIRED-A70-AXI-OPERATION",
        "kernel_boot_id": "FIXTURE95-NOT-A-BOOT",
        "session_id": "FIXTURE95-SESSION-95345678",
        "clock_domain_id": "FIXTURE95-A70-NOMINAL-QPC-NS",
        "request_hash": request_hash,
        "build_manifest_sha256": build_manifest_sha256,
        "source_record_sha256": digest([book0["source_sha256"], book9["source_sha256"]]),
        "capture_sha256": capture_hash,
        "tested_commit": SOURCE_RUNTIME_COMMIT,
        "tag": TAG,
        "generation": 1,
        "trigger_id": 95,
        "request_seq": 0x9501,
        "capture_seq": 0x9502,
        "source_admission_index": 0,
    }
    context = digest(identity)
    full_receipt = {
        "commit": pins[0]["commit"],
        "tree": pins[0]["tree"],
        "git_oid": pins[0]["git_oid"],
        "bytes": pins[0]["bytes"],
        "sha256": pins[0]["sha256"],
        "path": pins[0]["path"],
        "original_operation_id": a18["original_operation_id"],
        "source_runtime_commit": a18["source_commit"],
        "origin_qpc_ns": a18["source_origin_qpc_ns"],
        "schema": a18["original_source_book"]["schema"],
        "native_interval_atomic": a18["original_source_book"]["native_interval_atomic"],
        "retired": True,
        "retired_historic_not_current_fresh": a18["retired_historic_not_current_fresh"],
        "missing_evidence": missing,
        "record_completion_qpc_ns": a18["actual_record_end_qpc_ns"],
        "book_records": [
            {
                "source_count": sample["source_count"],
                "nominal_qpc_ns": sample["nominal_qpc_ns"],
                "finish_qpc_ns": sample["finish_qpc_ns"],
                "observed_source_qpc_ns": sample["observed_source_qpc_ns"],
                "opened_qpc_ns": sample["opened_qpc_ns"],
                "adc": sample["adc"],
                "held_em_association": sample["held_em_association"],
                "source_record_sha256": sample["source_sha256"],
            }
            for sample in a18["original_source_book"]["samples"]
        ],
        "original_causal_sha256": a18["original_causal_sha256"],
        "original_result_sha256": a18["original_result_sha256"],
    }

    host = load_module("b95_host", W / HOST_REL, EXPECTED_HOST_SHA)
    trace = load_module("b95_trace", W / TRACE_REL, EXPECTED_TRACE_SHA)
    schema74 = (W / SCHEMA74_REL).read_text(encoding="utf-8")
    for token in ("raw_quality_by_channel", "mapped_flags_by_channel",
                  "timestamp_record_sha256", "quality_record_sha256",
                  "B_PRIVATE_TRANSPORT_BINDING_PROPOSED_V1"):
        need(token in schema74, "B74 schema reference token " + token)

    uart = bytes.fromhex(required["uart"].read_text(encoding="ascii"))
    popped = bytes.fromhex(required["pop"].read_text(encoding="ascii"))
    need(len(uart) == 301 and len(popped) == 300,
         "300 complete UART/POP bytes plus one separately retained cancel prefix")
    need(uart[:300] == popped, "actual complete UART and explicit POP bytes differ")
    need(uart[300:] == b"\xa5", "cancel prefix is actual first magic byte, not a packet")
    write_new(decoded / "cancel-prefix.bin", uart[300:])
    packets = split_frames(popped)
    need(len(packets) == 8, "exact eight actual frames")

    decoder_pins = {"host_sha256": EXPECTED_HOST_SHA, "trace_sha256": EXPECTED_TRACE_SHA,
                    "schema74_sha256": EXPECTED_SCHEMA74_SHA}
    rows = []
    companions = []
    wire_lengths = []
    companion_lengths = []
    populations = {"invalid": 0, "valid_zero": 0, "held": 0, "fresh": 0}
    for index, (packet, lane) in enumerate(zip(packets, lanes)):
        need(len(packet) == lane["expected_wire_bytes"],
             "measured frame length lane %d" % index)
        header = struct.unpack_from("<2sBBBBHI", packet)
        need(header[4] == VIEW and header[5] == lane["frame_seq"] and
             header[6] == lane["relative_tick_us"], "outer fixture identity")
        raw_quality = {str(channel): lane["record_derived_quality"][channel]
                       for channel in range(4)}
        mapped = {str(channel): dict(lane["record_flags"][channel])
                  for channel in range(4)}
        acquisitions = [lane["acquisition_qpc_ns"]]
        sources = [lane["source_qpc_ns"]]
        values = [lane["count"] if lane["valid"] else None]
        indices = [lane["first_index"]]
        timestamp_record = {
            "origin_qpc_ns": ORIGIN,
            "acquisition_qpc_ns": acquisitions,
            "source_qpc_ns": sources,
            "original_values": values,
            "original_indices": indices,
            "source_context_sha256": context,
        }
        quality_record = {
            "raw_quality_by_channel": raw_quality,
            "mapped_flags_by_channel": mapped,
            "source_context_sha256": context,
        }
        binding = {
            "kind": "B_PRIVATE_TRANSPORT_BINDING_PROPOSED_V1",
            "receipt_id": "FIXTURE95-RETIRED-A70-AXI-TRANSPORT",
            "profile_id": "TRACE-PAYLOAD-1US-PRIVATE-v2",
            "session_handle": SESSION,
            "view_handle": VIEW,
            "frame_seq": lane["frame_seq"],
            "e": 0,
            "source_context_sha256": context,
        }
        profile = {
            "profile_id": "TRACE-PAYLOAD-1US-PRIVATE-v2",
            "origin_mode": "ROOT_RELATIVE_V1",
            "origin_receipt_id": "FIXTURE95-ORIGIN-NOT-A-ROOT",
            "origin_qpc_ns": ORIGIN,
            "source_identity": copy.deepcopy(identity),
            "original_acquisition_qpc_ns": acquisitions,
            "original_source_qpc_ns": sources,
            "original_values": values,
            "original_indices": indices,
            "timestamp_record_sha256": digest(timestamp_record),
            "raw_quality_by_channel": raw_quality,
            "mapped_flags_by_channel": mapped,
            "quality_record_sha256": digest(quality_record),
            "receiver_qpc_ns": RECEIVER,
        }
        receipt_record = full_receipt["book_records"][lane["record_index"]]
        companion = {
            "schema": "B95_RETIRED_A70_AXI_COMPANION_V1",
            "evidence_kind": "RETIRED_A70_AXI_TRANSPORT",
            "labels": ["FIXTURE95", "RETIRED_A70_AXI_TRANSPORT"],
            "fixture_only": True,
            "source_runtime_only": True,
            "tested_commit": SOURCE_RUNTIME_COMMIT,
            "tested_commit_scope": "A18 source-runtime label only; not the B execution source",
            "execution_source_pins": {
                "source_manifest_sha256": build_manifest_sha256,
                "source94_sha256": SOURCE_PINS[
                    "competition/deepeye/fpga/diagnostic/functional50_board94/deepeye_trace50_axi94.sv"],
                "tb_sha256": sha((W / BENCH_REL).read_bytes()),
                "checker_sha256": sha(Path(__file__).read_bytes()),
            },
            "authority": {
                "actual_A_Root": "UNAVAILABLE",
                "verified_board_BOOT": "UNAVAILABLE",
                "admission": "UNAVAILABLE",
                "physical_ADC": "UNAVAILABLE",
                "original_EM_scope_receipt": "UNAVAILABLE",
                "action": "UNAVAILABLE",
                "current_source_eligible": False,
                "production_default": "CLOSED",
            },
            "record_index": lane["record_index"],
            "channel": lane["channel"],
            "adc_tick_ms": lane["adc_tick_ms"],
            "em_tick_ms": lane["em_tick_ms"],
            "channel_counts": rec0["channel_counts"] if lane["record_index"] == 0 else rec9["channel_counts"],
            "global_quality_13bits": lane["global_quality"],
            "global_quality_hex": "0x%04x" % lane["global_quality"],
            "raw_quality_by_channel": raw_quality,
            "mapped_flags_by_channel": mapped,
            "derived_quality_uint8": lane["derived_quality"],
            "fixture_first_index": lane["first_index"],
            "frame_seq": lane["frame_seq"],
            "relative_tick_us": lane["relative_tick_us"],
            "remainder_ns": 0,
            "original_acquisition_qpc_ns": lane["acquisition_qpc_ns"],
            "original_source_qpc_ns": lane["source_qpc_ns"],
            "source_tick_us": lane["source_tick_us"],
            "source_remainder_ns": 0 if lane["source_qpc_ns"] is not None else None,
            "source_age_ns": None if lane["source_qpc_ns"] is None else EVALUATION_NOW - lane["source_qpc_ns"],
            "stale_by_evaluation_time": lane["valid"],
            "evaluation_now_qpc_ns": EVALUATION_NOW,
            "evaluation_clock_kind": "FIXTURE_OFFLINE_GE_1S_NOT_CURRENT_CLOCK",
            "receiver_qpc_ns": RECEIVER,
            "receiver_clock_kind": "FIXTURE_RECEIVER_NOT_ACTUAL_TRANSPORT",
            "original_source_record_sha256": lane["source_record_sha256"],
            "original_canonical_source_payload_bytes": len(lane["canonical_source_bytes"]),
            "original_canonical_source_payload_sha256": sha(lane["canonical_source_bytes"]),
            "original_record_completion_qpc_ns": a18["actual_record_end_qpc_ns"][lane["record_index"]],
            "original_raw_finish_qpc_ns": receipt_record["finish_qpc_ns"],
            "retired_record_receipt": receipt_record,
            "retired_source_receipt": full_receipt,
            "historical_source_proof": "MISSING_ORIGINAL_EM_SCOPE_AND_BOOT_RECEIPTS",
            "private_float_values_transported": False,
            "current_source_eligible": False,
            "gate_view": {"status": "STOP", "command": None, "core_ran": False},
            "decoder_pins": decoder_pins,
            "binding": binding,
            "profile": profile,
        }
        companion_raw = canonical(companion)
        write_new(decoded / ("companion%03d.json" % index), companion_raw)
        write_new(decoded / ("frame%03d.bin" % index), packet)
        view = host.decode_transport(packet, binding=binding, profile=profile,
                                     now_qpc_ns=EVALUATION_NOW, enabled=True,
                                     repo_root=W)
        point = view["points"][0]
        raw_trace = trace.decode_payload(bytes([1]) + packet[13:-2],
                                         {"session": SESSION, "config_epoch": VIEW, "e": 0})
        trace_point = raw_trace["points"][0]
        need(view["status"] == "STOP" and view["command"] is None and
             view["core_ran"] is False, "strict decoder STOP/no action")
        need(view["source_identity"] == identity and
             view["frame_sha256"] == sha(packet), "strict source/frame identity")
        need(view["raw_quality_uint8"] == raw_quality, "strict opaque qualities")
        need(raw_trace["count"] == 1 and raw_trace["channel"] == lane["channel"],
             "fixed trace singleton/channel")
        need(trace_point["index"] == lane["first_index"] and
             trace_point["tick_ms"] == lane["relative_tick_us"],
             "fixed trace index/time")
        need(trace_point["value"] == (lane["count"] if lane["valid"] else None),
             "fixed trace original value")
        need(all(trace_point[key] == lane[key]
                 for key in ("valid", "saturated", "held", "source_fault")),
             "fixed trace flags")
        need(trace_point["source_tick_ms"] == lane["source_tick_us"],
             "fixed trace source time")
        need(point["index"] == lane["first_index"] and
             point["relative_tick_us"] == lane["relative_tick_us"] and
             point["remainder_ns"] == 0, "strict acquisition decomposition")
        need(point["original_acquisition_qpc_ns"] == lane["acquisition_qpc_ns"] and
             point["original_source_qpc_ns"] == lane["source_qpc_ns"],
             "strict original uint63 times")
        need(point["decoded_value"] == (lane["count"] if lane["valid"] else None) and
             point["original_value"] == (lane["count"] if lane["valid"] else None),
             "strict actual value")
        need(point["byte_exact_value"] is True and
             view["lossy_decoded_values_match_original"] is True and
             view["c29_uint12_values_possible"] is True, "exact value proof")
        if lane["valid"]:
            need(point["source_age_ns"] == EVALUATION_NOW - lane["source_qpc_ns"] and
                 view["source_age_100ms_met"] is False,
                 "deterministic stale fixture age")
            if lane["channel"] == 3 and lane["count"] == 0:
                populations["valid_zero"] += 1
            elif lane["held"]:
                populations["held"] += 1
            else:
                populations["fresh"] += 1
        else:
            need(point["decoded_value"] is None and point["source_age_ns"] is None,
                 "invalid remains null")
            populations["invalid"] += 1
        wire_lengths.append(len(packet))
        companion_lengths.append(len(companion_raw))
        companions.append(companion)
        rows.append({
            "frame": index,
            "record": lane["record_index"],
            "channel": lane["channel"],
            "frame_seq": lane["frame_seq"],
            "first_index": lane["first_index"],
            "wire_bytes": len(packet),
            "wire_sha256": sha(packet),
            "companion_bytes": len(companion_raw),
            "companion_sha256": sha(companion_raw),
            "global_quality": lane["global_quality"],
            "derived_quality": lane["derived_quality"],
            "decoded": point,
            "source_age_100ms_met": view["source_age_100ms_met"],
            "status": view["status"],
            "command": view["command"],
            "core_ran": view["core_ran"],
            "current_source_eligible": False,
        })
    need(populations == {"invalid": 1, "valid_zero": 1, "held": 3, "fresh": 4},
         "actual decoded populations")
    need(wire_lengths == [37, 37, 37, 35, 39, 39, 39, 37], "actual frame lengths")
    need(sum(wire_lengths) == 300, "actual measured wire byte total")

    controls = []
    disabled = host.decode_transport(b"")
    need(disabled["status"] == "STOP" and disabled["input_status"] == "DISABLED" and
         disabled["command"] is None and disabled["core_ran"] is False,
         "default disabled STOP")
    controls.append({"case": "disabled_default", "result": disabled})
    unavailable = host.decode_transport(b"", enabled=True)
    need(unavailable["status"] == "STOP" and
         unavailable["input_status"] == "INPUT_UNAVAILABLE" and
         unavailable["command"] is None and unavailable["core_ran"] is False,
         "missing input unavailable")
    controls.append({"case": "missing_input", "result": unavailable})

    null_rewrite = copy.deepcopy(companions[3])
    null_rewrite["profile"]["original_values"] = [0]
    recompute_time_hash(null_rewrite)
    try:
        host.decode_transport(packets[3], binding=null_rewrite["binding"],
                              profile=null_rewrite["profile"], now_qpc_ns=EVALUATION_NOW,
                              enabled=True, repo_root=W)
    except host.Rejected as exc:
        need("invalid data remains null" in str(exc), "None-to-zero refusal reason")
        controls.append({"case": "invalid_None_to_zero", "refused": True,
                         "reason": str(exc)})
    else:
        raise RuntimeError("FALSE_ACCEPT invalid None as zero")

    wrong_index = copy.deepcopy(companions[0])
    wrong_index["profile"]["original_indices"] = [1]
    recompute_time_hash(wrong_index)
    try:
        host.decode_transport(packets[0], binding=wrong_index["binding"],
                              profile=wrong_index["profile"], now_qpc_ns=EVALUATION_NOW,
                              enabled=True, repo_root=W)
    except host.Rejected as exc:
        need("index association" in str(exc), "wrong index refusal reason")
        controls.append({"case": "wrong_original_index", "refused": True,
                         "reason": str(exc)})
    else:
        raise RuntimeError("FALSE_ACCEPT wrong original index")

    wrong_sequence = copy.deepcopy(companions[0])
    wrong_sequence["binding"]["frame_seq"] = 949
    try:
        host.decode_transport(packets[0], binding=wrong_sequence["binding"],
                              profile=wrong_sequence["profile"], now_qpc_ns=EVALUATION_NOW,
                              enabled=True, repo_root=W)
    except host.Rejected as exc:
        need("outer identity/length" in str(exc), "wrong binding sequence refusal reason")
        controls.append({"case": "wrong_binding_sequence", "refused": True,
                         "reason": str(exc)})
    else:
        raise RuntimeError("FALSE_ACCEPT wrong binding sequence")

    bad_packet = bytearray(packets[0])
    bad_packet[33:35] = (3012).to_bytes(2, "little")
    bad_packet[-2:] = binascii.crc_hqx(bytes(bad_packet[2:-2]), 0xFFFF).to_bytes(2, "little")
    mismatch = host.decode_transport(bytes(bad_packet), binding=companions[0]["binding"],
                                     profile=companions[0]["profile"],
                                     now_qpc_ns=EVALUATION_NOW, enabled=True, repo_root=W)
    mismatch_point = mismatch["points"][0]
    need(mismatch_point["decoded_value"] == 3012 and
         mismatch_point["original_value"] == 3011 and
         mismatch_point["byte_exact_value"] is False and
         mismatch["lossy_decoded_values_match_original"] is False and
         mismatch["status"] == "STOP" and mismatch["command"] is None,
         "changed wire value is visible but never accepted")
    controls.append({"case": "changed_wire_value", "accepted": False,
                     "decoded_value": mismatch_point["decoded_value"],
                     "original_value": mismatch_point["original_value"]})

    crc_bad = bytearray(packets[0])
    crc_bad[-1] ^= 1
    try:
        host.decode_transport(bytes(crc_bad), binding=companions[0]["binding"],
                              profile=companions[0]["profile"], now_qpc_ns=EVALUATION_NOW,
                              enabled=True, repo_root=W)
    except host.Rejected as exc:
        need("CRC" in str(exc), "CRC refusal reason")
        controls.append({"case": "bad_crc", "refused": True, "reason": str(exc)})
    else:
        raise RuntimeError("FALSE_ACCEPT bad CRC")

    events = required["events"].read_text(encoding="utf-8", errors="strict")
    event_requirements = {
        "zero_build_arm": 1,
        "bus_invalid_routes": 1,
        "incomplete_and_uint63_arm": 1,
        "reset_pending_aw_r": 1,
        "reset_pending_w": 1,
        "reset_pending_b_r": 1,
        "arm_while_active": 1,
        "push_freshness_pad_quality_channel": 1,
        "sample_uint63_highbit": 1,
        "common_tick_and_invalid_lane": 1,
        "fifth_push": 1,
        "incomplete_bind_staging": 1,
        "bind_rem_uint63_source_acq_decomp": 1,
        "reused_frame_sequence": 1,
        "arm_nonempty_after_cancel": 1,
        "stale_arm_tag": 1,
        "held_mismatch": 1,
        "fresh_held_mismatch": 1,
        "held_rdata_under_fifo_change": 1,
        "wrong_and_duplicate_ack": 8,
        "stale_pop_id": 2,
        "duplicate_pop_id": 2,
    }
    for label, count in event_requirements.items():
        actual = events.count("NEGATIVE " + label)
        need(actual == count, "event negative count " + label + "=" + str(actual))
    need("SCAN record=0 wire_bytes=146" in events, "record0 measured event")
    need("SCAN record=9 cumulative_wire_bytes=300" in events, "record9 measured event")
    need("DRAIN count=146" in events and "DRAIN count=154" in events,
         "both explicit FIFO drains")
    need("CLEAR_FIFO discard=1 rx=301 pop=300 result=8" in events,
         "CLEAR_FIFO counter preservation")
    cancel_match = re.search(r"CANCEL_PARTIAL uart=301 partial=(\d+) fifo=1 aborted=(\d+)", events)
    need(cancel_match is not None and int(cancel_match.group(1)) >= 1 and int(cancel_match.group(2)) > 0,
         "actual cancel partial/aborted evidence")
    order_match = re.search(r"BUS_ORDERS aw_first=(\d+) w_first=(\d+)", events)
    need(order_match is not None and int(order_match.group(1)) > 0 and int(order_match.group(2)) > 0,
         "both AXI write orders")
    done_match = re.search(r"DONE cycles=(\d+) uart=301 popped=300 partial=(\d+)", events)
    need(done_match is not None and int(done_match.group(1)) <= 600000 and
         int(done_match.group(2)) >= 1, "finite completion and actual partial")

    result_lines = re.findall(
        r"^RESULT id=(\d+) err=(\d+) bytes=(\d+) start=(\d+) end=(\d+) uart=(\d+)$",
        events, re.MULTILINE)
    need(len(result_lines) == 8, "eight held-result observations")
    start = 0
    for number, line in enumerate(result_lines, 1):
        result_id, error, byte_count, observed_start, end, uart_end = map(int, line)
        need(result_id == number and error == 0 and
             byte_count == wire_lengths[number - 1] and
             observed_start == start and end == start + byte_count and
             uart_end == end, "held result %d fields" % number)
        start = end
    need(start == 300, "held result cumulative wire count")

    modelsim = required["modelsim"].read_text(encoding="utf-8", errors="replace")
    need("B95_DONE" in modelsim and "Errors: 0" in modelsim and
         "** Fatal:" not in modelsim and "** Error:" not in modelsim,
         "ModelSim exact completion")
    vlog_path = out / "commands" / "04-vlog.stdout.bin"
    need(vlog_path.is_file(), "vlog stdout evidence")
    vlog_log = vlog_path.read_text(encoding="utf-8", errors="replace")
    need("Errors: 0" in vlog_log and "** Error:" not in vlog_log,
         "vlog exact compile completion")

    wire_total = sum(wire_lengths)
    companion_total = sum(companion_lengths)
    cost = {
        "wire_bytes": wire_total,
        "all_actual_complete_uart_bytes_including_cancel_prefix": len(uart),
        "cancel_prefix_bytes": len(uart) - wire_total,
        "mandatory_companion_bytes": companion_total,
        "total_serialized_bytes": wire_total + companion_total,
        "source_input_bytes": EXPECTED_A18_BYTES,
        "original_selected_canonical_payload_bytes": 355 + 375,
        "raw_uint16_values_bytes": 14,
        "final_1pct_100ms_gate": "RETAINED_UNMET_NOT_CLAIMED",
        "bandwidth_or_150B_acceptance": "NOT_CLAIMED",
    }
    event_audit = {
        "events_sha256": sha(events.encode("utf-8")),
        "negative_counts": event_requirements,
        "scan": {"record0_wire_bytes": 146, "record9_cumulative_wire_bytes": 300},
        "drains": [146, 154],
        "cancel_partial": {"uart": 301, "partial": int(cancel_match.group(1)),
                           "rx_aborted": int(cancel_match.group(2)), "fifo": 1},
        "axi_write_orders": {"aw_first": int(order_match.group(1)),
                              "w_first": int(order_match.group(2))},
        "result_end": start,
    }
    semantic = {
        "status": "FOCUSED_RUNTIME_CHECKS_COMPLETED_MAIN_REVIEW_PENDING",
        "scope": "actual historical A18 records 0/9 through source94 public AXI, unchanged74 codec/TX, unchanged RX/FIFO, 1 Mbaud digital simulation",
        "task_id": "DEEPEYE-IMPLEMENTATION-20261014",
        "task_version": 1,
        "work_id": "B-DEEPEYE-TRACE50-AXI-RECOVERY-20261031-102",
        "requirements_ids": ["H%02d" % i for i in range(1, 16)],
        "requirements_sha256": REQUIREMENTS,
        "freeze": FREEZE,
        "source_runtime_commit": SOURCE_RUNTIME_COMMIT,
        "tested_commit_scope": "A18 original source-runtime label only; not the B execution source",
        "fixture_labels": ["FIXTURE95", "RETIRED_A70_AXI_TRANSPORT"],
        "frames": 8,
        "frame_lengths": wire_lengths,
        "measured_wire_bytes": wire_total,
        "reference_wire_bytes_by_flags": 300,
        "wire_delta": wire_total - 300,
        "decoded_populations": populations,
        "global_quality_values": [7, 1807],
        "derived_quality_bytes": [[1, 1, 1, 0], [5, 5, 5, 1]],
        "quality_main_correction": correction,
        "cancelled95_false_observation_provenance": false_observation_provenance,
        "origin_qpc_ns": ORIGIN,
        "origin_submicrosecond_ns": ORIGIN % 1000,
        "relative_acquisition_us": [0, 90000],
        "relative_source_us": [0, 50000, 90000],
        "relative_remainder_ns": 0,
        "source_age_100ms_met": False,
        "source_age_label": "DETERMINISTIC_OFFLINE_EVALUATION_GE_1S_NOT_CURRENT_FRESHNESS",
        "current_source_eligible": False,
        "status_all": "STOP",
        "command": None,
        "core_ran": False,
        "cost": cost,
        "decoder_pins": decoder_pins,
        "host_controls": controls,
        "event_audit": event_audit,
        "historical_source_proof": "MISSING_ORIGINAL_EM_SCOPE_AND_BOOT_RECEIPTS",
        "missing_evidence": missing,
        "unrun_scopes": [
            "physical ADC/analog calibration",
            "physical UART/electrical/oscillator tolerance",
            "BOOT/Root/admission/current capture",
            "H12 control-path acceptance",
            "synthesis/implementation/bitstream/HWH/post-route timing",
            "board/SSH/physical operation",
            "CDC/metastability/timing closure",
            "FIFO4096-full and 32-bit counter-wrap defensive branches",
            "complete G05 atomic STOP/all 29 gates",
            "H01-H15 product acceptance",
        ],
    }
    index_value = {
        "status": semantic["status"],
        "frames": rows,
        "measured_wire_bytes": wire_total,
        "mandatory_companion_bytes": companion_total,
        "total_serialized_bytes": wire_total + companion_total,
        "current_source_eligible": False,
    }
    write_new(decoded / "FRAMES_INDEX.json", canonical(index_value))
    write_new(out / "EVENT_AUDIT.json", canonical(event_audit))
    write_new(out / "HOST_CONTROLS.json", canonical(controls))
    write_new(out / "INPUT_VERIFICATION.json", canonical({
        "a18": record(required["a18"]),
        "pins": record(required["pins"]),
        "independent": record(required["independent"]),
        "scope": record(required["scope"]),
        "requirements_sha256": REQUIREMENTS,
        "missing_evidence": missing,
        "record_completion_qpc_ns": [27001355219600, 27001440690300],
        "raw_finish_qpc_ns": [27001355126400, 27001440598500],
        "canonical_payload_bytes": [355, 375],
        "source_record_sha256": [book0["source_sha256"], book9["source_sha256"]],
        "private_float_values_transported": False,
    }))
    write_new(out / "DECODER_PINS.json", canonical(decoder_pins))
    write_new(out / "SEMANTIC_RESULT.json", canonical(semantic))
    print(json.dumps({"status": semantic["status"], "frames": 8,
                      "wire_bytes": wire_total, "companion_bytes": companion_total}))
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(args.out)
    except Exception:
        import traceback
        error = traceback.format_exc()
        print(error, file=sys.stderr)
        out = args.out.resolve()
        if out.exists() and not (out / "CHECK95_FAILURE.json").exists():
            write_new(out / "CHECK95_FAILURE.json", canonical({
                "status": "FAILED_CHECKER_STOP_NO_RETRY",
                "error": error,
            }))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
