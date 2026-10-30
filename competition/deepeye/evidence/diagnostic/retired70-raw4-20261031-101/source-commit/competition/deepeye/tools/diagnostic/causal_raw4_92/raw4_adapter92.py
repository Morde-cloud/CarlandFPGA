"""B92 pure counts-only raw4 projection adapter.

This module is a pure computation over explicit fixture input. It does not
read or write files, import the producer, call Root/admission/planner code,
open a device, or grant production authority. The only accepted transport
input is the exact COUNTS-ONLY projection schema below. Root-private float
values are deliberately absent from this schema.
"""
from __future__ import annotations

import hashlib
import json
import re


SCHEMA = "B92_COUNTS_ONLY_PROJECTION_V1"
FIXTURE_KIND = "MODELLED_SHAPES_FROM_PINNED_PUBLIC_CONTRACTS"
PINNED_COMMIT = "4dc91fd24531b3df53fc916e8b7f509ad524592c"
PINNED_TREE = "f48acf33ba4a4a81499826c44851663119dcd17b"
PINNED_BLOB_COUNT = 12
TIME_BASIS = "A_ORIGINAL_NOMINAL_QPC_NS"
PROFILE_ID = "TRACE-PAYLOAD-1US-PRIVATE-v2"
ORIGIN_MODE = "ROOT_RELATIVE_V1"
OUTER_TYPE_PROPOSED = 0xE4
SESSION = 0x92345678
VIEW = 7
E = 0
TAG = 0x00000092
RECEIVER_OFFSET_NS = 200_000_000
MIN_EVALUATION_MARGIN_NS = 1_000_000_000
NS_PER_MS = 1_000_000
U16 = (1 << 16) - 1
U32 = (1 << 32) - 1
U63 = (1 << 63) - 1
MAX_RECORDS = 20
MAX_LANES = 80
SAMPLE_MAX = 4095
VIBRATION_SATURATION_MIN_COUNT = 1295

PROFILE_METADATA = {
    "profile_id": "deepeye_forward_profile_candidate_v1",
    "profile_status": "candidate_only",
    "profile_note": "not_calibrated;not_em_surrogate_v2;not_formally_frozen",
    "source_mode": "twin_fixture",
}

PROJECTION_KEYS = {
    "schema",
    "fixture_kind",
    "pinned_commit",
    "pinned_tree",
    "pinned_blob_count",
    "time_basis",
    "origin_qpc_ns",
    "evaluation_now_qpc_ns",
    "profile",
    "records",
    "fixture_transport_identity",
}

RECORD_KEYS = {
    "adc_tick_ms",
    "em_tick_ms",
    "channel_counts",
    "quality",
    "source_record_sha256",
}

IDENTITY_KEYS = {
    "kind",
    "label",
    "operation_id",
    "kernel_boot_id",
    "session_id",
    "clock_domain_id",
    "transport_receipt_id",
    "source_note",
    "board",
}

FLAG_KEYS = {"valid", "saturated", "held", "source_fault"}


class Rejected(ValueError):
    """Deterministic refusal of invalid projection input or policy."""


def _need(ok, reason):
    if not ok:
        raise Rejected(reason)


def _exact(value, keys, name):
    _need(type(value) is dict and all(type(k) is str for k in value) and set(value) == keys, name)
    return value


def _uint(value, limit, name):
    _need(type(value) is int and 0 <= value <= limit, name)
    return value


def _text(value, name):
    _need(type(value) is str and 1 <= len(value) <= 192 and
          all(32 <= ord(c) <= 126 for c in value), name)
    return value


def _sha(value, digits=64, name="hash"):
    _need(type(value) is str and re.fullmatch("[0-9a-f]{%d}" % digits, value) is not None, name)
    return value


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _plain(value, depth=0, budget=None):
    if budget is None:
        budget = [20000]
    budget[0] -= 1
    _need(depth <= 16 and budget[0] >= 0, "bounded plain data")
    kind = type(value)
    _need(kind in (type(None), bool, int, str, list, dict), "plain JSON types only")
    if kind is str:
        _need(len(value) <= 192, "bounded strings")
    elif kind is list:
        _need(len(value) <= 128, "bounded arrays")
        for item in value:
            _plain(item, depth + 1, budget)
    elif kind is dict:
        _need(len(value) <= 64 and all(type(k) is str for k in value), "plain keys")
        for key, item in value.items():
            _plain(key, depth + 1, budget)
            _plain(item, depth + 1, budget)


def load_json_strict(raw):
    _need(type(raw) is bytes and len(raw) <= 262144, "bounded UTF-8 JSON bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Rejected("UTF-8 decode failed: %s" % exc) from exc

    def reject_constant(token):
        raise Rejected("non-finite JSON constant: %s" % token)

    def pairs_hook(pairs):
        result = {}
        for key, value in pairs:
            _need(key not in result, "duplicate JSON key: %s" % key)
            result[key] = value
        return result

    try:
        return json.loads(text, parse_constant=reject_constant, object_pairs_hook=pairs_hook)
    except Rejected:
        raise
    except Exception as exc:
        raise Rejected("malformed JSON: %s" % exc) from exc


def _checked_add(value, delta, name):
    _need(0 <= delta <= U63 and value <= U63 - delta, name)
    return value + delta


def _validate_record_quality(record, position):
    quality = _uint(record["quality"], 0x1FFF, "record quality")
    counts = record["channel_counts"]
    _need(type(counts) is list and len(counts) == 4, "four channel counts")
    _need((quality & 0xE000) == 0, "quality bits 13..15 must be zero")
    _need((quality & 0x0800) == 0, "quality bit 11 is not a channel bit and must be zero")
    em_bits = [bool(quality & (1 << i)) for i in range(3)]
    _need(all(em_bits) or not any(em_bits), "EM validity must be all-or-none")
    em_valid = bool(em_bits[0])
    source_fault = bool(quality & 0x1000)
    _need(source_fault == (not em_valid), "source_fault must match invalid EM")
    held_bits = [bool(quality & (1 << (8 + i))) for i in range(3)]
    _need(all(held_bits) or not any(held_bits), "held EM bits must agree")
    held_em = bool(held_bits[0])
    em_tick = record["em_tick_ms"]
    if em_valid:
        _uint(em_tick, 0x7FFFFFFF, "em_tick_ms")
        _need(em_tick % 50 == 0, "em_tick_ms must be on the 50ms grid")
        _need(em_tick <= record["adc_tick_ms"], "EM time cannot be later than ADC")
        _need(held_em == (em_tick < record["adc_tick_ms"]), "held bits must match original EM time")
    else:
        _need(em_tick is None, "invalid EM must carry null em_tick_ms")
        _need(not held_em, "invalid EM cannot be held")
    valid = [bool(quality & (1 << i)) for i in range(4)]
    saturated = [bool(quality & (1 << (4 + i))) for i in range(4)]
    held = [held_em if i < 3 else False for i in range(4)]
    derived = []
    for channel in range(4):
        count = counts[channel]
        if not valid[channel]:
            _need(count is None, "invalid channel must carry null count")
            _need(not saturated[channel], "invalid channel cannot be saturated")
            _need(not held[channel], "invalid channel cannot be held")
        else:
            _uint(count, SAMPLE_MAX, "channel count")
            if saturated[channel] and channel < 3:
                _need(count in (0, SAMPLE_MAX), "saturated EM must be an endpoint")
            if saturated[channel] and channel == 3:
                _need(count >= VIBRATION_SATURATION_MIN_COUNT,
                      "saturated vibration RMS is below the pinned lower bound")
        fault = source_fault if channel < 3 else False
        derived.append((1 if valid[channel] else 0) |
                       (2 if saturated[channel] else 0) |
                       (4 if held[channel] else 0) |
                       (8 if fault else 0))
    return {
        "valid": valid,
        "saturated": saturated,
        "held": held,
        "em_valid": em_valid,
        "source_fault": source_fault,
        "held_em": held_em,
        "derived_bytes": derived,
    }



RETIRED_KIND = "RETIRED_A70_TRANSPORT_FIXTURE"
RETIRED_COMMIT = "d0185d335747acb26439f40a8ce945f7f4eaa9af"
RETIRED_TREE = "d2e6533d93efcc09e8dd1341e6cc5d741fe965a5"
RETIRED_SHA = "63616e2915edc5a2ef6ed592e8f9830ce77a635aaf883ab964aa4dbd5fd1910c"
RETIRED_ORIGIN = 27001348289300
RETIRED_SESSION = 0x97345678
RETIRED_VIEW = 9
RETIRED_TAG = 0x97
RETIRED_RECEIPT_SHA = '2386711ede83b59f9e384bd57f5d0ad80e26e3ab53745691f1995e91d57912c0'
RETIRED_RECORDS_SHA = '5db4288646077ed124a1cb6e7919c2dc8ac72d486e1e0fd7dcd863066d54811a'
RETIRED_RECEIPT_KEYS = {'record_completion_qpc_ns', 'original_operation_id', 'source_runtime_commit', 'retired', 'tree', 'git_oid', 'origin_qpc_ns', 'schema', 'missing_evidence', 'book_records', 'native_interval_atomic', 'sha256', 'bytes', 'commit'}

def fixture_parameters(projection):
    if projection["fixture_kind"] == RETIRED_KIND:
        return RETIRED_SESSION, RETIRED_VIEW, RETIRED_TAG, 97
    return SESSION, VIEW, TAG, 92

def _validate_retired(projection):
    receipt = _exact(projection["retired_source_receipt"], RETIRED_RECEIPT_KEYS, "retired receipt keys")
    _need(projection["origin_qpc_ns"] == RETIRED_ORIGIN, "original retired origin")
    _need(len(projection["records"]) == 20, "exact retired 20 records")
    _need(digest(projection["records"]) == RETIRED_RECORDS_SHA, "original retired counts/time/quality/hash contradiction")
    _need(digest(receipt) == RETIRED_RECEIPT_SHA, "original retired receipt contradiction")
    previous = 0
    for i, end in enumerate(receipt["record_completion_qpc_ns"]):
        _uint(end, U63, "retired completion uint63")
        _need(end >= RETIRED_ORIGIN + i * 10 * NS_PER_MS and end >= previous,
              "retired completion ordering")
        previous = end
    for key in ("operation_id", "session_id", "transport_receipt_id"):
        _need(projection["fixture_transport_identity"][key].startswith("FIXTURE-RETIRED97-"),
              "explicit retired fixture namespace")

def transport_input(projection=None, *, fixture_mode=None, build_manifest_sha256=None):
    """Default closed; only explicit offline fixture modes may derive a model."""
    if projection is None or fixture_mode is None:
        return {"status": "STOP", "input_status": "INPUT_UNAVAILABLE", "command": None,
                "core_ran": False, "current_source_eligible": False}
    _need(fixture_mode in (FIXTURE_KIND, RETIRED_KIND), "explicit fixture mode")
    _need(projection.get("fixture_kind") == fixture_mode, "fixture mode mismatch")
    return derive_model(projection, build_manifest_sha256=build_manifest_sha256)

def validate_projection(projection):
    _plain(projection)
    _need(type(projection) is dict, "projection keys")
    retired = projection.get("fixture_kind") == RETIRED_KIND
    _exact(projection, PROJECTION_KEYS | ({"retired_source_receipt"} if retired else set()), "projection keys")
    _need(projection["schema"] == SCHEMA, "projection schema")
    _need(projection["fixture_kind"] in (FIXTURE_KIND, RETIRED_KIND), "explicit fixture kind")
    _need(projection["pinned_commit"] == (RETIRED_COMMIT if retired else PINNED_COMMIT), "pinned source commit")
    _need(projection["pinned_tree"] == (RETIRED_TREE if retired else PINNED_TREE), "pinned source tree")
    _need(projection["pinned_blob_count"] == (2 if retired else PINNED_BLOB_COUNT) and
          type(projection["pinned_blob_count"]) is int, "pinned blob count")
    _need(projection["time_basis"] == TIME_BASIS, "nominal time basis")
    origin = _uint(projection["origin_qpc_ns"], U63, "original uint63 origin")
    now = _uint(projection["evaluation_now_qpc_ns"], U63, "evaluation now")
    profile = _exact(projection["profile"], set(PROFILE_METADATA), "profile keys")
    for key, expected in PROFILE_METADATA.items():
        _need(profile[key] == expected, "pinned profile metadata")
    identity = _exact(projection["fixture_transport_identity"], IDENTITY_KEYS,
                      "fixture transport identity keys")
    _need(identity["kind"] == "B92_FIXTURE_TRANSPORT_IDENTITY_V1", "fixture identity kind")
    _need(identity["label"] == projection["fixture_kind"], "fixture identity label")
    _need(identity["kernel_boot_id"] == projection["fixture_kind"],
          "fixture kernel label")
    _need(identity["clock_domain_id"] == "A_ORIGINAL_NOMINAL_QPC_NS-FIXTURE",
          "fixture clock-domain label")
    _need(identity["operation_id"].startswith("FIXTURE-"), "fixture operation id cannot claim A authority")
    _need(identity["session_id"].startswith("FIXTURE-"), "fixture session id cannot claim A authority")
    _need(identity["transport_receipt_id"].startswith("FIXTURE-"),
          "fixture transport receipt cannot claim A authority")
    for key in ("operation_id", "kernel_boot_id", "session_id", "clock_domain_id",
                "transport_receipt_id", "source_note", "board"):
        _text(identity[key], "fixture identity text")
    _need("A Root" not in identity["source_note"] or "not" in identity["source_note"].lower(),
          "source note must not claim A Root")
    records = projection["records"]
    _need(type(records) is list and 1 <= len(records) <= MAX_RECORDS, "record count 1..20")
    if retired:
        _validate_retired(projection)
    previous_em = None
    previous_em_valid = False
    previous_counts = None
    previous_sat_em = None
    c3_seen_valid = False
    seen_hashes = set()
    normalized = []
    for position, record in enumerate(records):
        _exact(record, RECORD_KEYS, "record keys")
        adc = _uint(record["adc_tick_ms"], 0x7FFFFFFF, "adc_tick_ms")
        _need(adc == position * 10, "ADC ticks must start at 0 and increase by exactly 10ms")
        _sha(record["source_record_sha256"], 64, "original source-record hash")
        _need(record["source_record_sha256"] not in seen_hashes, "duplicate source record")
        seen_hashes.add(record["source_record_sha256"])
        checked = _validate_record_quality(record, position)
        c3_valid = checked["valid"][3]
        if c3_seen_valid:
            _need(c3_valid, "C3 validity cannot return to invalid after a valid prefix")
        if c3_valid:
            c3_seen_valid = True
            _need(adc >= 90, "C3 cannot be valid before the pinned 90ms startup origin")
        em = record["em_tick_ms"]
        if checked["em_valid"]:
            if previous_em is None:
                _need(em == adc, "first valid EM must appear in its own ADC slot")
            elif em != previous_em:
                _need(em > previous_em, "EM time cannot reverse or backfill")
                _need(em == adc, "new EM acquisition must first appear in its own ADC slot")
            else:
                _need(previous_em_valid, "invalidated EM cannot revive as held data")
                _need(record["channel_counts"][:3] == previous_counts,
                      "held EM counts must be unchanged")
                _need([bool(record["quality"] & (1 << (4 + i))) for i in range(3)] == previous_sat_em,
                      "held EM saturation must be unchanged")
            previous_em = em
            previous_em_valid = True
            previous_counts = list(record["channel_counts"][:3])
            previous_sat_em = [bool(record["quality"] & (1 << (4 + i))) for i in range(3)]
        else:
            previous_em_valid = False
            previous_counts = None
            previous_sat_em = None
        normalized.append({**record, "checked": checked})
    last_adc = records[-1]["adc_tick_ms"]
    minimum_now = _checked_add(_checked_add(origin, last_adc * NS_PER_MS, "acquisition time"),
                               MIN_EVALUATION_MARGIN_NS, "evaluation margin")
    _need(now >= minimum_now, "evaluation now must be at least 1s after the source batch")
    receiver = _checked_add(origin, RECEIVER_OFFSET_NS, "receiver time")
    _need(receiver >= origin + last_adc * NS_PER_MS, "receiver must not precede the last acquisition")
    _need(receiver <= now, "receiver must not be after evaluation now")
    return {
        "projection": projection,
        "origin_qpc_ns": origin,
        "evaluation_now_qpc_ns": now,
        "receiver_qpc_ns": receiver,
        "records": normalized,
    }


def _derive_identity(projection, lanes, build_manifest_sha256):
    _sha(build_manifest_sha256, 64, "build/source manifest hash")
    session, view, tag, trigger = fixture_parameters(projection)
    fixture_identity = projection["fixture_transport_identity"]
    if projection["fixture_kind"] == FIXTURE_KIND:
        # Preserve the original modelled mode's identity normalization exactly.
        fixture_identity = {
            "operation_id": "FIXTURE-RAW4-92-NOT-A-ROOT",
            "kernel_boot_id": FIXTURE_KIND,
            "session_id": "FIXTURE-SESSION-92",
            "clock_domain_id": "A_ORIGINAL_NOMINAL_QPC_NS-FIXTURE",
        }
    projection_sha = digest(projection)
    capture_sha = sha256_bytes(canonical({"kind": "B92_FIXTURE_CAPTURE_V1", "lanes": lanes}))
    identity = {
        "operation_id": fixture_identity["operation_id"],
        "kernel_boot_id": fixture_identity["kernel_boot_id"],
        "session_id": fixture_identity["session_id"],
        "clock_domain_id": fixture_identity["clock_domain_id"],
        "request_hash": projection_sha,
        "build_manifest_sha256": build_manifest_sha256,
        "source_record_sha256": projection_sha,
        "capture_sha256": capture_sha,
        "tested_commit": PINNED_COMMIT,
        "tag": tag,
        "generation": 1,
        "trigger_id": trigger,
        "request_seq": 1,
        "capture_seq": 0,
        "source_admission_index": 0,
    }
    return identity


def derive_model(projection, *, build_manifest_sha256):
    checked = validate_projection(projection)
    session, view, tag, trigger = fixture_parameters(projection)
    origin = checked["origin_qpc_ns"]
    now = checked["evaluation_now_qpc_ns"]
    receiver = checked["receiver_qpc_ns"]
    lanes = []
    for position, record in enumerate(checked["records"]):
        adc = record["adc_tick_ms"]
        em = record["em_tick_ms"]
        acquisition = _checked_add(origin, adc * NS_PER_MS, "acquisition time")
        first_tick_us = adc * 1000
        for channel in range(4):
            flags = record["checked"]
            valid = flags["valid"][channel]
            saturated = flags["saturated"][channel]
            held = flags["held"][channel]
            fault = flags["source_fault"] if channel < 3 else False
            count = record["channel_counts"][channel]
            if valid:
                source = _checked_add(origin, em * NS_PER_MS, "EM source time") if held else acquisition
            else:
                source = None
            source_tick_us = None if source is None else (source - origin) // 1000
            source_remainder = None if source is None else (source - origin) % 1000
            _need(source_remainder in (None, 0), "fixture source time must be integral microseconds")
            frame_seq = position * 4 + channel
            expected_wire = 35 if not valid else (39 if held else 37)
            stale = None if not valid else (now - source > 100_000_000)
            lanes.append({
                "record_index": position,
                "channel": channel,
                "adc_tick_ms": adc,
                "em_tick_ms": em,
                "channel_counts": list(record["channel_counts"]),
                "quality13_uint16": record["quality"],
                "source_record_sha256": record["source_record_sha256"],
                "valid_sample": valid,
                "saturated": saturated,
                "held": held,
                "source_fault": fault,
                "derived_quality_uint8": flags["derived_bytes"][channel],
                "record_derived_bytes": list(flags["derived_bytes"]),
                "record_flags": [
                    {
                        "valid": flags["valid"][i],
                        "saturated": flags["saturated"][i],
                        "held": flags["held"][i],
                        "source_fault": flags["source_fault"] if i < 3 else False,
                    }
                    for i in range(4)
                ],
                "count": count,
                "expected_value": count if valid else None,
                "acquisition_index": adc // 10,
                "acquisition_qpc_ns": acquisition,
                "source_qpc_ns": source,
                "first_tick_us": first_tick_us,
                "first_remainder_ns": 0,
                "source_tick_us": source_tick_us,
                "source_remainder_ns": source_remainder,
                "frame_seq": frame_seq,
                "assoc_seq": frame_seq,
                "assoc_epoch": view,
                "assoc_session": session,
                "assoc_tag": tag,
                "assoc_e": E,
                "assoc_count": 1,
                "capture_first_seq": position * 4,
                "capture_last_seq": position * 4 + 3,
                "capture_tag": tag,
                "sample_data": count if valid else 0,
                "sample_quality": flags["derived_bytes"][channel],
                "expected_wire_bytes": expected_wire,
                "stale_by_evaluation_time": stale,
            })
    identity = _derive_identity(projection, lanes, build_manifest_sha256)
    identity_sha = digest(identity)
    binding_base = {
        "kind": "B_PRIVATE_TRANSPORT_BINDING_PROPOSED_V1",
        "receipt_id": (projection["fixture_transport_identity"]["transport_receipt_id"]
                       if projection["fixture_kind"] == RETIRED_KIND else "FIXTURE-TRANSPORT-92"),
        "profile_id": PROFILE_ID,
        "session_handle": session,
        "view_handle": view,
        "e": E,
        "source_context_sha256": identity_sha,
    }
    for lane in lanes:
        if lane["valid_sample"]:
            _need(lane["stale_by_evaluation_time"] is True,
                  "every valid fixture point must be stale at the supplied evaluation time")
    return {
        "projection": projection,
        "projection_sha256": digest(projection),
        "origin_qpc_ns": origin,
        "evaluation_now_qpc_ns": now,
        "receiver_qpc_ns": receiver,
        "records": checked["records"],
        "lanes": lanes,
        "identity": identity,
        "identity_sha256": identity_sha,
        "binding_base": binding_base,
    }


def companion_for_lane(model, lane, *, decoder_pins):
    projection = model["projection"]
    identity = model["identity"]
    binding = dict(model["binding_base"])
    binding["frame_seq"] = lane["frame_seq"]
    raw_quality = {str(i): lane["record_derived_bytes"][i] for i in range(4)}
    mapped = {str(i): dict(lane["record_flags"][i]) for i in range(4)}
    values = [lane["count"] if lane["valid_sample"] else None]
    sources = [lane["source_qpc_ns"]]
    acquisitions = [lane["acquisition_qpc_ns"]]
    indices = [lane["acquisition_index"]]
    timestamp_record = {
        "origin_qpc_ns": model["origin_qpc_ns"],
        "acquisition_qpc_ns": acquisitions,
        "source_qpc_ns": sources,
        "original_values": values,
        "original_indices": indices,
        "source_context_sha256": binding["source_context_sha256"],
    }
    quality_record = {
        "raw_quality_by_channel": raw_quality,
        "mapped_flags_by_channel": mapped,
        "source_context_sha256": binding["source_context_sha256"],
    }
    profile = {
        "profile_id": PROFILE_ID,
        "origin_mode": ORIGIN_MODE,
        "origin_receipt_id": "FIXTURE-ORIGIN-NOT-A-ROOT",
        "origin_qpc_ns": model["origin_qpc_ns"],
        "source_identity": identity,
        "original_acquisition_qpc_ns": acquisitions,
        "original_source_qpc_ns": sources,
        "original_values": values,
        "original_indices": indices,
        "timestamp_record_sha256": digest(timestamp_record),
        "raw_quality_by_channel": raw_quality,
        "mapped_flags_by_channel": mapped,
        "quality_record_sha256": digest(quality_record),
        "receiver_qpc_ns": model["receiver_qpc_ns"],
    }
    companion = {
        "schema": "B92_RAW4_COMPANION_V1",
        "evidence_kind": projection["fixture_kind"],
        "fixture_transport_identity": projection["fixture_transport_identity"],
        "authority": {
            "actual_A_Root": "UNAVAILABLE",
            "native_em_receipt": "UNAVAILABLE",
            "admission": "UNAVAILABLE",
            "boot": "UNAVAILABLE",
            "physical_capture": "UNAVAILABLE",
            "action": "UNAVAILABLE",
            "current_source_eligible": False,
            "production_default": "CLOSED",
        },
        "record_index": lane["record_index"],
        "channel": lane["channel"],
        "adc_tick_ms": lane["adc_tick_ms"],
        "em_tick_ms": lane["em_tick_ms"],
        "channel_counts": lane["channel_counts"],
        "global_quality_13bits": lane["quality13_uint16"],
        "global_quality_hex": "0x%04x" % lane["quality13_uint16"],
        "derived_quality_uint8": lane["derived_quality_uint8"],
        "derived_flags": lane["record_flags"][lane["channel"]],
        "capture": {
            "first_seq": lane["capture_first_seq"],
            "last_seq": lane["capture_last_seq"],
            "tag": lane["capture_tag"],
            "channel": lane["channel"],
            "sample_data_word": lane["sample_data"],
            "sample_quality_uint8": lane["sample_quality"],
            "note": "null capture word is local padding; valid=false is authoritative",
        },
        "original_source_record_sha256": lane["source_record_sha256"],
        "projection_sha256": model["projection_sha256"],
        "frame_seq": lane["frame_seq"],
        "acquisition_index": lane["acquisition_index"],
        "original_acquisition_qpc_ns": lane["acquisition_qpc_ns"],
        "original_source_qpc_ns": lane["source_qpc_ns"],
        "relative_tick_us": lane["first_tick_us"],
        "remainder_ns": lane["first_remainder_ns"],
        "source_tick_us": lane["source_tick_us"],
        "source_remainder_ns": lane["source_remainder_ns"],
        "time_basis": TIME_BASIS,
        "evaluation_now_qpc_ns": model["evaluation_now_qpc_ns"],
        "expected_value": lane["expected_value"],
        "expected_wire_bytes": lane["expected_wire_bytes"],
        "stale_by_evaluation_time": lane["stale_by_evaluation_time"],
        "source_age_ns": None if lane["source_qpc_ns"] is None else
        (model["evaluation_now_qpc_ns"] - lane["source_qpc_ns"]),
        "current_source_eligible": False,
        "singleton_fallback": {
            "used": True,
            "reason": "mixed null/held global batch is ineligible for B77 fresh-only uniform-quality triplets",
            "count": 1,
            "e": E,
            "index_stride": 0,
            "tick_stride_us": 0,
        },
        "decoder_pins": decoder_pins,
        "binding": binding,
        "profile": profile,
    }
    if projection["fixture_kind"] == RETIRED_KIND:
        receipt = projection["retired_source_receipt"]
        companion["retired_source_receipt"] = receipt
        companion["retired_record_receipt"] = receipt["book_records"][lane["record_index"]]
        companion["original_record_completion_qpc_ns"] = receipt["record_completion_qpc_ns"][lane["record_index"]]
        companion["evaluation_clock_kind"] = "FIXTURE_EVALUATION_NOT_ACTUAL_CURRENT_CLOCK"
        companion["receiver_clock_kind"] = "FIXTURE_RECEIVER_NOT_ACTUAL_TRANSPORT_RECEIPT"
        companion["identity_kind"] = "FIXTURE_ONLY_NOT_ORIGINAL_ROOT_BOOT_CAPTURE_ADMISSION"
    return companion


def expected_summary(model):
    lanes = model["lanes"]
    invalid = sum(1 for lane in lanes if not lane["valid_sample"])
    c3_zero = sum(1 for lane in lanes if lane["valid_sample"] and
                   lane["channel"] == 3 and lane["count"] == 0)
    fresh = sum(1 for lane in lanes if lane["valid_sample"] and not lane["held"])
    held = sum(1 for lane in lanes if lane["valid_sample"] and lane["held"])
    wire = sum(lane["expected_wire_bytes"] for lane in lanes)
    return {
        "records": len(model["records"]),
        "frames": len(lanes),
        "invalid_frames": invalid,
        "valid_c3_zero_frames": c3_zero,
        "fresh_valid_frames": fresh,
        "held_valid_frames": held,
        "reference_wire_bytes": wire,
        "reference_formula": "23*37 + 48*39 + 9*35",
        "global_quality_values": sorted({lane["quality13_uint16"] for lane in lanes}),
    }


def cost_summary(model, wire_bytes_by_frame, companion_bytes_by_frame):
    _need(len(wire_bytes_by_frame) == len(model["lanes"]), "wire cost length")
    _need(len(companion_bytes_by_frame) == len(model["lanes"]), "companion cost length")
    wire = sum(wire_bytes_by_frame)
    companion = sum(companion_bytes_by_frame)
    code = sum(0 if not lane["valid_sample"] else 2 for lane in model["lanes"])
    raw_values = sum(0 if not lane["valid_sample"] else 2 for lane in model["lanes"])
    metadata = wire - code
    return {
        "wire_bytes": wire,
        "mandatory_companion_bytes": companion,
        "total_serialized_bytes": wire + companion,
        "payload_code_bytes": code,
        "payload_metadata_and_outer_bytes": metadata,
        "raw_value_only_bytes": raw_values,
        "projection_counts_only_canonical_bytes": len(canonical(model["projection"])),
        "complete_lane_projection_canonical_bytes": len(canonical({
            "kind": "B92_COMPLETE_LANE_PROJECTION_V1", "lanes": model["lanes"]})),
        "fixed_compression_ratio_gate": "NONE",
        "public_150b_or_8s_budget": "NOT_ACCEPTED",
    }


def check_projection_file(path):
    projection = load_json_strict(path.read_bytes())
    validate_projection(projection)
    return projection
