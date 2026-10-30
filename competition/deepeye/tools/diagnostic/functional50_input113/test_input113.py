"""Focused future-execution tests for the B117 pure input normalizer. No pytest."""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import copy
import hashlib
import json
from pathlib import Path
import time

from input113 import Refused, normalize_external_original_scan_v1, physical_start

TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
REQ_SHA = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
MAX63 = (1 << 63) - 1
SOURCE = b"B117\x00synthetic-source\xff" + bytes(range(32))
COMPANIONS = (b"B117-companion-0\x00", b"B117-companion-1\x01", b"B117-companion-2\x02", b"B117-companion-3\x03")
CLOCK = "B117_SYNTHETIC_CLOCK_01"
ORIGIN = 1_000_000_000
ACQ_TICK = 2
ACQ_REM = 300
ACQ = ORIGIN + ACQ_TICK * 1000 + ACQ_REM
SRC_TICK = 1
SRC_REM = 200
SRC = ORIGIN + SRC_TICK * 1000 + SRC_REM
RECEIVER = 1_010_000_000
EVALUATION = 1_050_000_000
BUILD = "0123456789abcdef" * 2
COMMIT = "0123456789abcdef0123456789abcdef01234567"
EXPECTED_CASES = 34
MAX_REQUEST_BYTES = 262144
MAX_SOURCE_BYTES = 1048576
MAX_COMPANION_BYTES = 262144
MAX_UINT32 = (1 << 32) - 1
MAX_RESULT_BYTES = 4 * 1024 * 1024 - 1
MAX_RUNTIME_MS = 60000
MAX_CASE_MESSAGE_CHARS = 512


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _lane(channel, raw, quality, valid, held, fault, frame, saturated=False):
    staged = (1 if valid else 0) + (2 if saturated else 0) + (4 if held else 0) + (8 if fault else 0)
    return {
        "channel": channel,
        "raw_sample_uint16": raw,
        "root_quality_uint16": quality,
        "mapped_flags": {"valid": valid, "saturated": saturated, "held": held, "source_fault": fault},
        "staged_quality_uint4": staged,
        "acquisition_qpc_ns": ACQ,
        "acquisition_tick_us": ACQ_TICK,
        "acquisition_remainder_ns": ACQ_REM,
        "source_qpc_ns": SRC if valid else None,
        "source_tick_us": SRC_TICK if valid else None,
        "source_remainder_ns": SRC_REM if valid else None,
        "session": 77,
        "index": 101 + channel,
        "view": 3,
        "frame_seq": frame,
    }


def base_request():
    companions = []
    for index, body in enumerate(COMPANIONS):
        companions.append({"channel": index, "format_label": f"B117_SYNTHETIC_COMPANION_{index}",
                           "bytes": len(body), "sha256": _sha(body)})
    return {
        "schema": "B113_EXTERNAL_ORIGINAL_SCAN_REQUEST_V1",
        "task": {"task_id": TASK_ID, "task_version": 1,
                 "work_id": "B117-SYNTHETIC-WORK", "requirements_sha256": REQ_SHA},
        "source_provenance": {"class": "SYNTHETIC_TEST", "declared_by": "B117-synthetic-caller",
                              "source_note": "new caller-owned synthetic bytes; not an A acquisition",
                              "mapping_state": "B_NEUTRAL_AWAITING_A_MAPPING"},
        "source_payload": {"format_label": "B117_SYNTHETIC_SOURCE_V1",
                           "bytes": len(SOURCE), "sha256": _sha(SOURCE)},
        "scan": {"scan_id_uint63": 1700000000000000001, "origin_qpc_ns": ORIGIN,
                 "acquisition_qpc_ns": ACQ, "clock_domain_id": CLOCK,
                 "lanes": [
                     _lane(0, 0, 65000, True, True, False, 10),
                     _lane(1, 4095, 1, True, True, False, 11),
                     _lane(2, 65535, 0, True, True, True, 12),
                     _lane(3, None, 65535, False, False, True, 13),
                 ]},
        "lineage": {"operation_id": "B117-SYNTHETIC-OP", "request_id": "B117-SYNTHETIC-REQ",
                    "request_hash": "d4" * 32, "tested_commit": COMMIT, "build_id_hex128": BUILD,
                    "boot_id": "B117-SYNTHETIC-BOOT", "session_id": 77, "tag": 9,
                    "trigger_id": 20, "generation": 3, "request_seq": 4, "capture_seq": 5},
        "association": {"profile_id": "B117_SYNTHETIC_PROFILE", "binding_receipt_id": "B117_SYNTHETIC_BIND",
                        "e": 0, "source_context_sha256": "a1" * 32,
                        "timestamp_record_sha256": "b2" * 32, "quality_record_sha256": "c3" * 32,
                        "receiver_qpc_ns": RECEIVER, "evaluation_now_qpc_ns": EVALUATION,
                        "evaluation_clock_id": CLOCK, "receiver_clock_id": CLOCK,
                        "freshness_limit_ns": 100000000},
        "companions": companions,
    }


def encode(request):
    return json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def normalize(request, source=SOURCE, companions=COMPANIONS):
    return normalize_external_original_scan_v1(encode(request), source, companions)


def expect_refused(code, request=None, source=SOURCE, companions=COMPANIONS, raw=None):
    payload = encode(request) if raw is None else raw
    try:
        normalize_external_original_scan_v1(payload, source, companions)
    except Refused as exc:
        if exc.code != code:
            raise AssertionError(f"expected {code}, got {exc.code} at {exc.path}") from exc
        return
    raise AssertionError(f"expected refusal {code}, normalization succeeded")


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def case_base_synthetic_scan():
    request = base_request()
    raw = encode(request)
    result = normalize(request)
    check(result.request_bytes == raw, "request bytes changed")
    check(result.source_bytes == SOURCE, "source bytes changed")
    check(result.companion_bytes == COMPANIONS, "companion bytes changed")
    check(result.source["bytes"] == SOURCE, "source result bytes changed")
    check(result.companions[0]["bytes"] == COMPANIONS[0], "companion result bytes changed")
    check(result.integrity["request_sha256"] == _sha(raw), "request hash mismatch")
    check([lane["raw_sample_uint16"] for lane in result.scan["lanes"]] == [0, 4095, 65535, None],
          "uint16/raw-null preservation mismatch")
    check(result.scan["lanes"][0]["freshness"]["age_ns"] == EVALUATION - SRC, "freshness age mismatch")
    check(result.scan["lanes"][0]["freshness"]["within_declared_100ms"] is True, "fresh base should be within")
    check(result.scan["lanes"][3]["freshness"]["classification"] == "NOT_APPLICABLE_INVALID",
          "invalid freshness classification")
    check(result.mapping["legacy_host103_numeric_compatible"] is False, "65535 must not be legacy-compatible")
    check(result.mapping["legacy_host103_numeric_compatibility_label"] == "NON_AUTHORITY", "legacy label")
    check(result.mapping["staging_shape_ready"] is True,
          "neutral uint16 data shape must remain separate from legacy uint12 compatibility")
    check(result.authority["execution_route"] == "PURE_UNBOUND_DATA", "route mismatch")
    check(result.authority["current_source_eligible"] is False, "current source authority invented")
    check(result.authority["physical_start_authority"] is False, "physical authority invented")
    check(result.authority["product_acceptance"] is False, "product acceptance invented")
    check(result.integrity["clock_domain_authenticated"] is False, "clock gate must remain unauthenticated")
    check(result.provenance["authenticated"] is False, "declared provenance authenticated")


def case_empty_request():
    expect_refused("REQUEST_SIZE", raw=b"")


def case_oversized_request():
    raw = encode(base_request())
    raw = raw + b" " * (262145 - len(raw))
    expect_refused("REQUEST_SIZE", raw=raw)


def case_bom_rejected():
    expect_refused("BOM", raw=b"\xef\xbb\xbf" + encode(base_request()))


def case_invalid_utf8():
    expect_refused("UTF8", raw=encode(base_request()) + b"\xff")


def case_malformed_json():
    expect_refused("JSON_SYNTAX", raw=b"{")
    expect_refused("JSON_INTEGER_RANGE", raw=b'{"n":' + b"9" * 20 + b"}")


def case_depth_limit():
    expect_refused("JSON_DEPTH", raw=b"[" * 13 + b"0" + b"]" * 13)


def case_duplicate_key():
    expect_refused("JSON_DUPLICATE_KEY", raw=b'{"a":0,"a":1}')


def case_float_rejected():
    expect_refused("JSON_FLOAT", raw=b'{"a":1.5}')


def case_nonfinite_rejected():
    expect_refused("JSON_NONFINITE", raw=b'{"a":NaN}')


def case_surrogate_rejected():
    expect_refused("STRING_SURROGATE", raw=b'{"a":"\\ud800"}')


def case_unknown_keys_rejected():
    request = base_request()
    request["verified"] = True
    expect_refused("KEYS", request=request)
    request = base_request()
    request["scan"]["lanes"][0]["current_source_eligible"] = True
    expect_refused("KEYS", request=request)


def case_task_contract_mismatch():
    request = base_request()
    request["task"]["task_id"] = "DEEPEYE-SYNTHETIC-WRONG"
    expect_refused("TASK_ID", request=request)
    request = base_request()
    request["task"]["task_version"] = 2
    expect_refused("RANGE", request=request)
    request = base_request()
    request["task"]["requirements_sha256"] = "0" * 64
    expect_refused("TASK_REQUIREMENTS", request=request)

def case_source_descriptor_mismatch():
    request = base_request()
    request["source_payload"]["bytes"] += 1
    expect_refused("SOURCE_LENGTH", request=request)
    request = base_request()
    request["source_payload"]["sha256"] = "0" * 64
    expect_refused("SOURCE_SHA", request=request)
    expect_refused("SOURCE_LENGTH", request=base_request(), source=SOURCE + b"x")


def case_companion_descriptor_mismatch():
    request = base_request()
    request["companions"][2]["channel"] = 3
    expect_refused("COMPANION_CHANNEL", request=request)
    request = base_request()
    request["companions"][1]["bytes"] += 1
    expect_refused("COMPANION_LENGTH", request=request)
    request = base_request()
    request["companions"][0]["sha256"] = "0" * 64
    expect_refused("COMPANION_SHA", request=request)
    bodies = (COMPANIONS[0] + b"x", *COMPANIONS[1:])
    expect_refused("COMPANION_LENGTH", request=base_request(), companions=bodies)


def case_body_and_lane_count():
    expect_refused("BODY_COUNT", request=base_request(), companions=COMPANIONS + (b"extra",))
    request = base_request()
    extra = copy.deepcopy(request["scan"]["lanes"][3])
    extra["channel"] = 4
    extra["frame_seq"] = 14
    request["scan"]["lanes"].append(extra)
    expect_refused("LANES_LENGTH", request=request)
    request = base_request()
    request["companions"].pop()
    expect_refused("COMPANIONS_LENGTH", request=request)


def case_total_input_limit():
    source = b"S" * 1048576
    companions = (b"A" * 262144, b"B" * 262144, b"C" * 262144, b"D" * 262144)
    expect_refused("TOTAL_INPUT_SIZE", raw=b"{}", source=source, companions=companions)


def case_clock_gate_before_time_order():
    request = base_request()
    request["association"]["receiver_clock_id"] = "B117_OTHER_CLOCK"
    request["association"]["receiver_qpc_ns"] = ORIGIN - 1
    expect_refused("CLOCK_DOMAIN_MISMATCH", request=request)
    request = base_request()
    request["association"]["evaluation_clock_id"] = "B117_OTHER_CLOCK"
    request["association"]["evaluation_now_qpc_ns"] = 0
    expect_refused("CLOCK_DOMAIN_MISMATCH", request=request)
    request = base_request()
    request["association"]["receiver_qpc_ns"] = ACQ - 1
    expect_refused("TIMESTAMP_ORDER", request=request)
    request = base_request()
    request["association"]["evaluation_now_qpc_ns"] = RECEIVER - 1
    expect_refused("TIMESTAMP_ORDER", request=request)


def case_qpc_equation_and_overflow():
    request = base_request()
    request["scan"]["lanes"][0]["acquisition_remainder_ns"] = 301
    expect_refused("QPC_EQUATION", request=request)
    request = base_request()
    request["scan"]["origin_qpc_ns"] = MAX63 - 500
    request["scan"]["acquisition_qpc_ns"] = MAX63
    for lane in request["scan"]["lanes"]:
        lane["acquisition_qpc_ns"] = MAX63
        lane["acquisition_tick_us"] = 1
        lane["acquisition_remainder_ns"] = 0
    expect_refused("QPC_OVERFLOW", request=request)


def case_source_after_acquisition():
    request = base_request()
    request["scan"]["lanes"][0].update({"source_tick_us": 3, "source_qpc_ns": ORIGIN + 3000,
                                          "source_remainder_ns": 0})
    expect_refused("SOURCE_AFTER_ACQUISITION", request=request)


def case_held_contradiction():
    request = base_request()
    request["scan"]["lanes"][0]["mapped_flags"]["held"] = False
    request["scan"]["lanes"][0]["staged_quality_uint4"] = 1
    expect_refused("HELD_MISMATCH", request=request)


def case_invalid_contradictions():
    request = base_request()
    request["scan"]["lanes"][3]["raw_sample_uint16"] = 0
    expect_refused("INVALID_NULL", request=request)
    request = base_request()
    request["scan"]["lanes"][3].update({"source_qpc_ns": SRC, "source_tick_us": SRC_TICK,
                                          "source_remainder_ns": SRC_REM})
    expect_refused("INVALID_SOURCE", request=request)
    request = base_request()
    request["scan"]["lanes"][3]["mapped_flags"]["held"] = True
    request["scan"]["lanes"][3]["staged_quality_uint4"] = 12
    expect_refused("INVALID_FLAGS", request=request)


def case_valid_null_and_uint16_overflow():
    request = base_request()
    request["scan"]["lanes"][0]["raw_sample_uint16"] = None
    expect_refused("VALID_SAMPLE", request=request)
    request = base_request()
    request["scan"]["lanes"][1]["raw_sample_uint16"] = 65536
    expect_refused("RANGE", request=request)
    request = base_request()
    request["scan"]["lanes"][2]["root_quality_uint16"] = 65536
    expect_refused("RANGE", request=request)


def case_staged_quality_and_flag_types():
    request = base_request()
    request["scan"]["lanes"][0]["staged_quality_uint4"] = 7
    expect_refused("STAGED_QUALITY", request=request)

    request = base_request()
    request["scan"]["lanes"][0]["mapped_flags"]["valid"] = 1
    expect_refused("TYPE", request=request)

    request = base_request()
    request["scan"]["lanes"][0]["staged_quality_uint4"] = 16
    expect_refused("RANGE", request=request)

    request = base_request()
    request["scan"]["lanes"][0]["root_quality_uint16"] = 65535
    result = normalize(request)
    lane = result.scan["lanes"][0]
    check(lane["root_quality_uint16"] == 65535, "opaque quality was changed")
    check(lane["mapped_flags"] == {"valid": True, "saturated": False, "held": True, "source_fault": False},
          "supplied flags were inferred from quality")
    check(lane["staged_quality_uint4"] == 5, "supplied staged bits changed")


def case_frame_sequence_order():
    request = base_request()
    request["scan"]["lanes"][1]["frame_seq"] = 10
    expect_refused("FRAME_ORDER", request=request)

    request = base_request()
    request["scan"]["lanes"][3]["frame_seq"] = 0
    expect_refused("FRAME_ORDER", request=request)

    request = base_request()
    request["scan"]["lanes"][3]["frame_seq"] = 65536
    expect_refused("RANGE", request=request)

    request = base_request()
    for lane, frame in zip(request["scan"]["lanes"], (65532, 65533, 65534, 65535)):
        lane["frame_seq"] = frame
    result = normalize(request)
    check([lane["frame_seq"] for lane in result.scan["lanes"]] == [65532, 65533, 65534, 65535],
          "maximum nonwrapping frame sequence was not preserved")


def case_session_view_common():
    request = base_request()
    request["scan"]["lanes"][2]["session"] = 78
    expect_refused("SESSION_MISMATCH", request=request)

    request = base_request()
    request["lineage"]["session_id"] = 78
    expect_refused("SESSION_MISMATCH", request=request)

    request = base_request()
    request["scan"]["lanes"][1]["view"] = 4
    expect_refused("VIEW_MISMATCH", request=request)

    request = base_request()
    request["lineage"]["session_id"] = MAX_UINT32
    for lane in request["scan"]["lanes"]:
        lane["session"] = MAX_UINT32
        lane["view"] = 255
    result = normalize(request)
    check(all(lane["session"] == MAX_UINT32 for lane in result.scan["lanes"]), "common session not preserved")
    check(all(lane["view"] == 255 for lane in result.scan["lanes"]), "common view not preserved")


def case_zero_tag_and_build_preserved():
    request = base_request()
    request["scan"]["lanes"][2]["raw_sample_uint16"] = 4095
    result = normalize(request)
    check(result.mapping["staging_shape_ready"] is True,
          "nonzero tag/build and uint12-compatible values should be data-shape ready")

    request = base_request()
    request["scan"]["lanes"][2]["raw_sample_uint16"] = 4095
    request["lineage"]["tag"] = 0
    result = normalize(request)
    check(result.lineage["tag"] == 0, "zero tag was not preserved")
    check(result.mapping["staging_shape_ready"] is False, "zero tag admitted staging data shape")

    request = base_request()
    request["scan"]["lanes"][2]["raw_sample_uint16"] = 4095
    request["lineage"]["build_id_hex128"] = "0" * 32
    result = normalize(request)
    check(result.lineage["build_id_hex128"] == "0" * 32, "zero build was not preserved")
    check(result.mapping["staging_shape_ready"] is False, "zero build admitted staging data shape")

    request = base_request()
    request["scan"]["lanes"][2]["raw_sample_uint16"] = 4095
    request["lineage"]["tag"] = 0
    request["lineage"]["build_id_hex128"] = "0" * 32
    result = normalize(request)
    check(result.mapping["staging_shape_ready"] is False, "zero tag/build admitted staging data shape")
    check(result.mapping["staging_shape_label"] == "NEUTRAL_UINT16_DATA_SHAPE_ONLY", "staging label is not bounded")


def case_provenance_independent_labels():
    for label in ("SYNTHETIC_TEST", "HISTORICAL_ORIGINAL", "NEW_ORIGINAL_LIVE_ROOT"):
        request = base_request()
        request["source_provenance"]["class"] = label
        result = normalize(request)
        check(result.provenance["class"] == label, "declared provenance label was not preserved")
        check(result.provenance["authenticated"] is False, "declared provenance became authenticated")
        check(result.provenance["declared_only"] is True, "declared provenance lost its label")
        check(result.authority["declared_source_provenance"] == label, "authority label mismatch")
        check(result.authority["current_source_eligible"] is False, "label minted current source")
        check(result.authority["producer_authenticated"] is False, "label minted producer authority")
        check(result.authority["boot_authenticated"] is False, "label minted boot authority")
        check(result.authority["physical_start_authority"] is False, "label minted physical authority")
        check(result.authority["product_acceptance"] is False, "label minted product acceptance")
        metadata = result.to_jsonable()
        check(metadata["provenance"]["class"] == label, "metadata omitted declared provenance")
        check(metadata["provenance"]["authenticated"] is False, "metadata authenticated provenance")

    request = base_request()
    request["source_provenance"]["class"] = "UNSUPPORTED_ORIGINAL_LABEL"
    expect_refused("ENUM", request=request)


def case_declared_100ms_boundary():
    request = base_request()
    request["association"]["evaluation_now_qpc_ns"] = SRC + 100000000
    result = normalize(request)
    for lane in result.scan["lanes"][:3]:
        check(lane["freshness"]["age_ns"] == 100000000, "boundary age mismatch")
        check(lane["freshness"]["within_declared_100ms"] is True, "exact 100ms boundary was excluded")
        check(lane["freshness"]["classification"] == "WITHIN_DECLARED_100MS", "boundary class mismatch")
        check(lane["freshness"]["declared_clock_only"] is True, "freshness lost declared-only label")
        check(lane["freshness"]["clock_domain_authenticated"] is False, "freshness authenticated its clock")
    check(result.scan["lanes"][3]["freshness"]["within_declared_100ms"] is None, "invalid lane got freshness")

    request = base_request()
    request["association"]["evaluation_now_qpc_ns"] = SRC + 100000001
    result = normalize(request)
    check(result.scan["lanes"][0]["freshness"]["age_ns"] == 100000001, "above-boundary age mismatch")
    check(result.scan["lanes"][0]["freshness"]["within_declared_100ms"] is False,
          "age above 100ms was accepted")
    check(result.scan["lanes"][0]["freshness"]["classification"] == "ABOVE_DECLARED_100MS",
          "above-boundary class mismatch")

    request = base_request()
    request["association"]["freshness_limit_ns"] = 99999999
    expect_refused("RANGE", request=request)


def case_physical_unavailable():
    class ExplosiveArgument:
        def __getattr__(self, name):
            raise AssertionError("physical_start inspected an argument")

        def __call__(self, *args, **kwargs):
            raise AssertionError("physical_start invoked an argument")

    probe = ExplosiveArgument()
    expected = {
        "status": "STOP",
        "provider": "A_ORIGINAL_PROVIDER_UNAVAILABLE",
        "physical_start_authority": False,
        "product_acceptance": False,
    }
    check(physical_start(probe, verified=True, device=probe, callback=probe) == expected,
          "physical_start did not return the unconditional STOP result")
    check(physical_start() == expected, "physical_start result changed without arguments")


def case_output_metadata_and_hashes():
    request = base_request()
    raw = encode(request)
    result = normalize(request)
    metadata = result.to_jsonable()
    check(metadata["schema"] == "B113_NORMALIZED_EXTERNAL_SCAN_V1", "metadata schema mismatch")
    check(metadata["request_sha256"] == _sha(raw), "metadata request hash mismatch")
    check("request_bytes" not in metadata, "metadata exposed request bytes under a wrong key")
    check("bytes" not in metadata["source"], "metadata exposed source bytes")
    check(all("bytes" not in item for item in metadata["companions"]), "metadata exposed companion bytes")
    check(len(metadata["companions"]) == 4, "metadata companion count mismatch")
    check(result.request_bytes == raw, "exact request bytes were not retained")
    check(result.source_bytes == SOURCE, "exact source bytes were not retained")
    check(result.source["bytes"] == SOURCE, "source result omitted exact bytes")
    check(result.companion_bytes == COMPANIONS, "exact companion bytes were not retained")
    check(all(item["bytes"] == body for item, body in zip(result.companions, COMPANIONS)),
          "companion result omitted exact bytes")

    companion_digest = hashlib.sha256()
    for body in COMPANIONS:
        companion_digest.update(len(body).to_bytes(8, "big"))
        companion_digest.update(body)
    canonical = json.dumps(result.association, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    check(metadata["integrity"]["request_sha256"] == _sha(raw), "integrity request hash mismatch")
    check(metadata["integrity"]["association_canonical_sha256"] == _sha(canonical),
          "association canonical hash mismatch")
    check(metadata["integrity"]["companion_set_sha256"] == companion_digest.hexdigest(),
          "companion set hash mismatch")
    check(metadata["integrity"]["supplied_association_hashes_semantically_verified"] is False,
          "opaque association hashes became verified")
    check(metadata["integrity"]["supplied_lineage_request_hash_verified"] is False,
          "opaque lineage request hash became verified")
    check(metadata["mapping"]["legacy_mapping_created"] is False, "legacy mapping was created")
    check(metadata["mapping"]["source_numerical_association_verified"] is False,
          "numerical association became verified")
    check(metadata["authority"]["execution_route"] == "PURE_UNBOUND_DATA", "execution route mismatch")
    json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def case_boundary_widths_and_lengths():
    request = base_request()
    raw = encode(request)
    check(len(raw) <= MAX_REQUEST_BYTES, "base request unexpectedly exceeds its boundary")
    padded = raw + b" " * (MAX_REQUEST_BYTES - len(raw))
    result = normalize_external_original_scan_v1(padded, SOURCE, COMPANIONS)
    check(result.request_bytes == padded, "exact maximum-size request bytes were not retained")
    check(len(result.request_bytes) == MAX_REQUEST_BYTES, "maximum request boundary mismatch")

    small_source = b"Z"
    request = base_request()
    request["source_payload"]["bytes"] = len(small_source)
    request["source_payload"]["sha256"] = _sha(small_source)
    result = normalize(request, source=small_source)
    check(result.source_bytes == small_source, "minimum source bytes were not retained")

    large_source = b"Q" * MAX_SOURCE_BYTES
    request = base_request()
    request["source_payload"]["bytes"] = len(large_source)
    request["source_payload"]["sha256"] = _sha(large_source)
    result = normalize(request, source=large_source)
    check(result.source_bytes == large_source, "maximum source bytes were not retained")
    check(len(result.source_bytes) == MAX_SOURCE_BYTES, "maximum source boundary mismatch")

    large_companions = tuple(bytes((65 + index,)) * MAX_COMPANION_BYTES for index in range(4))
    request = base_request()
    for descriptor, body in zip(request["companions"], large_companions):
        descriptor["bytes"] = len(body)
        descriptor["sha256"] = _sha(body)
    result = normalize(request, companions=large_companions)
    check(result.companion_bytes == large_companions, "maximum companion bytes were not retained")
    check(all(len(body) == MAX_COMPANION_BYTES for body in result.companion_bytes),
          "maximum companion boundary mismatch")

    request = base_request()
    request["scan"]["scan_id_uint63"] = MAX63
    request["lineage"].update({"session_id": MAX_UINT32, "tag": MAX_UINT32,
                               "trigger_id": MAX_UINT32, "generation": MAX_UINT32,
                               "request_seq": MAX_UINT32, "capture_seq": MAX_UINT32})
    for lane, frame in zip(request["scan"]["lanes"], (65532, 65533, 65534, 65535)):
        lane["session"] = MAX_UINT32
        lane["index"] = MAX_UINT32
        lane["view"] = 255
        lane["frame_seq"] = frame
    result = normalize(request)
    check(result.scan["scan_id_uint63"] == MAX63, "uint63 scan id boundary mismatch")
    check(result.lineage["tag"] == MAX_UINT32, "uint32 tag boundary mismatch")
    check(all(lane["index"] == MAX_UINT32 for lane in result.scan["lanes"]),
          "uint32 lane index boundary mismatch")

    expect_refused("SOURCE_SIZE", source=b"X" * (MAX_SOURCE_BYTES + 1))
    oversized_companions = (b"X" * (MAX_COMPANION_BYTES + 1), *COMPANIONS[1:])
    expect_refused("COMPANION_SIZE", companions=oversized_companions)


def case_deterministic_refusal_no_echo():
    sentinel = "B117_SYNTHETIC_ERROR_SENTINEL_7c1e"
    request = base_request()
    request["source_provenance"]["class"] = sentinel
    observed = []
    for _ in range(2):
        try:
            normalize(request)
        except Refused as exc:
            check(isinstance(exc, ValueError), "Refused is not a ValueError")
            check(exc.code == "ENUM", "enum refusal code mismatch")
            check(exc.path == "$.source_provenance.class", "enum refusal path mismatch")
            check(sentinel not in str(exc), "refusal echoed caller-controlled value")
            observed.append((exc.code, exc.path, str(exc)))
        else:
            raise AssertionError("invalid enum was accepted")
    check(observed[0] == observed[1], "equivalent refusals were nondeterministic")

    malformed = b'{"' + sentinel.encode("ascii") + b'":'
    observed = []
    for _ in range(2):
        try:
            normalize_external_original_scan_v1(malformed, SOURCE, COMPANIONS)
        except Refused as exc:
            check(exc.code == "JSON_SYNTAX", "malformed JSON refusal code mismatch")
            check(exc.path == "$", "malformed JSON refusal path mismatch")
            check(sentinel not in str(exc), "JSON refusal echoed caller-controlled text")
            observed.append((exc.code, exc.path, str(exc)))
        else:
            raise AssertionError("malformed JSON was accepted")
    check(observed[0] == observed[1], "equivalent JSON refusals were nondeterministic")


def case_main_contract_boundaries():
    request = base_request()
    raw = encode(request)
    result = normalize_external_original_scan_v1(
        request_bytes=raw, source_scan_bytes=SOURCE, companion_bytes=COMPANIONS)
    check(result.request_bytes == raw and result.companion_bytes == COMPANIONS,
          "documented keyword call changed original bytes")
    expect_refused("JSON_INTEGER_RANGE", raw=b'{"n":' + b"9" * 5000 + b"}")
    expect_refused("JSON_INTEGER_RANGE", raw=b'{"n":9223372036854775808}')

    request = base_request()
    request["scan"]["origin_qpc_ns"] = MAX63 - 999
    request["scan"]["acquisition_qpc_ns"] = MAX63
    request["association"].update(receiver_qpc_ns=MAX63, evaluation_now_qpc_ns=MAX63)
    for lane in request["scan"]["lanes"]:
        lane.update(acquisition_qpc_ns=MAX63, acquisition_tick_us=0, acquisition_remainder_ns=999)
        if lane["mapped_flags"]["valid"]:
            lane.update(source_qpc_ns=MAX63, source_tick_us=0, source_remainder_ns=999)
            lane["mapped_flags"]["held"] = False
            lane["staged_quality_uint4"] &= ~4
    result = normalize(request)
    check(result.scan["acquisition_qpc_ns"] == MAX63 and
          result.scan["lanes"][0]["freshness"]["age_ns"] == 0, "uint63 maximum exact time changed")

    request = base_request()
    for lane in request["scan"]["lanes"]:
        lane.update(raw_sample_uint16=None, source_qpc_ns=None, source_tick_us=None,
                    source_remainder_ns=None, staged_quality_uint4=8)
        lane["mapped_flags"] = dict(valid=False, saturated=False, held=False, source_fault=True)
    result = normalize(request)
    check(result.mapping["valid_lane_count"] == 0 and result.mapping["staging_shape_ready"] is True,
          "all-invalid neutral record was misclassified as malformed")
    check(all(lane["raw_sample_uint16"] is None and lane["freshness"]["age_ns"] is None
              for lane in result.scan["lanes"]), "invalid record gained data or age")
    check(result.authority["physical_start_authority"] is False, "data shape enabled physical authority")


CASES = (
    ("base_synthetic_scan", case_base_synthetic_scan),
    ("empty_request", case_empty_request),
    ("oversized_request", case_oversized_request),
    ("bom_rejected", case_bom_rejected),
    ("invalid_utf8", case_invalid_utf8),
    ("malformed_json", case_malformed_json),
    ("depth_limit", case_depth_limit),
    ("duplicate_key", case_duplicate_key),
    ("float_rejected", case_float_rejected),
    ("nonfinite_rejected", case_nonfinite_rejected),
    ("surrogate_rejected", case_surrogate_rejected),
    ("unknown_keys_rejected", case_unknown_keys_rejected),
    ("task_contract_mismatch", case_task_contract_mismatch),
    ("source_descriptor_mismatch", case_source_descriptor_mismatch),
    ("companion_descriptor_mismatch", case_companion_descriptor_mismatch),
    ("body_and_lane_count", case_body_and_lane_count),
    ("total_input_limit", case_total_input_limit),
    ("clock_gate_before_time_order", case_clock_gate_before_time_order),
    ("qpc_equation_and_overflow", case_qpc_equation_and_overflow),
    ("source_after_acquisition", case_source_after_acquisition),
    ("held_contradiction", case_held_contradiction),
    ("invalid_contradictions", case_invalid_contradictions),
    ("valid_null_and_uint16_overflow", case_valid_null_and_uint16_overflow),
    ("staged_quality_and_flag_types", case_staged_quality_and_flag_types),
    ("frame_sequence_order", case_frame_sequence_order),
    ("session_view_common", case_session_view_common),
    ("zero_tag_and_build_preserved", case_zero_tag_and_build_preserved),
    ("provenance_independent_labels", case_provenance_independent_labels),
    ("declared_100ms_boundary", case_declared_100ms_boundary),
    ("physical_unavailable", case_physical_unavailable),
    ("output_metadata_and_hashes", case_output_metadata_and_hashes),
    ("boundary_widths_and_lengths", case_boundary_widths_and_lengths),
    ("deterministic_refusal_no_echo", case_deterministic_refusal_no_echo),
    ("main_contract_boundaries", case_main_contract_boundaries),
)


def _bounded_error(exc):
    text = f"{type(exc).__name__}: {exc}".replace("\r", "\\r").replace("\n", "\\n")
    if len(text) > MAX_CASE_MESSAGE_CHARS:
        text = text[:MAX_CASE_MESSAGE_CHARS - 3] + "..."
    return text


def _encode_result(result):
    return (json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) +
            "\n").encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the B117 focused software-only input tests.")
    parser.add_argument("--output", required=True, type=Path,
                        help="fresh directory that will exclusively receive RESULT.json")
    args = parser.parse_args(argv)

    if len(CASES) != EXPECTED_CASES:
        sys.stderr.write("SETUP_REFUSED: CASE_COUNT\n")
        return 2

    output = args.output
    try:
        output.mkdir(mode=0o700, parents=False, exist_ok=False)
    except FileExistsError:
        sys.stderr.write("OUTPUT_REFUSED: EXISTS\n")
        return 2
    except OSError as exc:
        sys.stderr.write(f"OUTPUT_REFUSED: {type(exc).__name__}\n")
        return 2

    started_ns = time.monotonic_ns()
    case_results = []
    passed = 0
    for name, case in CASES:
        case_started_ns = time.monotonic_ns()
        try:
            case()
        except Exception as exc:
            status = "FAIL"
            message = _bounded_error(exc)
        else:
            status = "PASS"
            message = "ok"
            passed += 1
        duration_ms = (time.monotonic_ns() - case_started_ns) // 1_000_000
        case_results.append({"name": name, "status": status, "message": message,
                             "duration_ms": duration_ms})

    elapsed_ms = (time.monotonic_ns() - started_ns) // 1_000_000
    failed = len(case_results) - passed
    timed_out = elapsed_ms > MAX_RUNTIME_MS
    exit_status = 1 if failed or timed_out else 0
    result = {
        "schema": "B117_FOCUSED_TEST_RESULT_V1",
        "task_id": TASK_ID,
        "requirements_sha256": REQ_SHA,
        "execution_phase": "ACTUAL_FOCUSED_SOFTWARE_EXECUTION",
        "software_only": True,
        "physical_authority": False,
        "product_acceptance": False,
        "cases_expected": EXPECTED_CASES,
        "cases_run": len(case_results),
        "cases_passed": passed,
        "cases_failed": failed,
        "elapsed_ms": elapsed_ms,
        "runtime_limit_ms": MAX_RUNTIME_MS,
        "timed_out": timed_out,
        "outcome": "PASS" if exit_status == 0 else ("TIMEOUT" if timed_out else "FAIL"),
        "exit_status": exit_status,
        "case_results": case_results,
    }
    payload = _encode_result(result)
    if len(payload) >= MAX_RESULT_BYTES:
        exit_status = 2
        result["exit_status"] = exit_status
        result["outcome"] = "RESULT_SIZE_BOUND"
        result["case_results"] = [{"name": item["name"], "status": item["status"]}
                                  for item in case_results]
        payload = _encode_result(result)
        if len(payload) >= MAX_RESULT_BYTES:
            payload = _encode_result({
                "schema": "B117_FOCUSED_TEST_RESULT_V1",
                "exit_status": 2,
                "outcome": "RESULT_SIZE_BOUND",
                "cases_expected": EXPECTED_CASES,
            })

    target = output / "RESULT.json"
    try:
        with target.open("xb") as handle:
            handle.write(payload)
    except FileExistsError:
        sys.stderr.write("OUTPUT_REFUSED: RESULT_EXISTS\n")
        return 2
    except OSError as exc:
        sys.stderr.write(f"OUTPUT_REFUSED: {type(exc).__name__}\n")
        return 2

    print(f"B117_FOCUSED_CASES passed={passed} failed={failed} "
          f"timed_out={str(timed_out).lower()} exit_status={exit_status}")
    return exit_status


if __name__ == "__main__":
    raise SystemExit(main())
