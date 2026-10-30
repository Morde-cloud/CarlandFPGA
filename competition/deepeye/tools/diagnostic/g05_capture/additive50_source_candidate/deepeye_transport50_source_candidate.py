"""Unexecuted source proposal; default off; no control or planner invocation.

Private outer type E4 / payload revision2 proposes Root-origin-relative1us.
Legacy type7/type8 and revision1 input are rejected. Only the pinned existing
code-section parser is reused internally, after explicit complete bindings.
JSON consistency is not authentication. Root must supply actual retained data.
No function in this file was imported or called during source preparation.
"""
from __future__ import annotations
import binascii
import copy
import hashlib
import importlib.util
import json
import re
import struct
from pathlib import Path

PROFILE_ID = "TRACE-PAYLOAD-1US-PRIVATE-v2"
ORIGIN_MODE = "ROOT_RELATIVE_V1"
OUTER_TYPE_PROPOSED = 0xE4
DECODER_PATH = "competition/deepeye/golden/codec/trace_candidate.py"
DECODER_SHA256 = "a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642"
C29_SOURCE = "2210ca5f32e4e806651a6b06d0e2d9710d78e773"
C29_PATH = "handoffs/c/C-DEEPEYE-PRIVATE-RAW4-PLANNER-ABI-20261029-29/private_raw4_planner_abi_v1.py"
U63 = (1 << 63) - 1
U32 = (1 << 32) - 1
FLAG_KEYS = {"valid", "saturated", "held", "source_fault"}

class Rejected(ValueError):
    pass

def _need(ok, reason):
    if not ok:
        raise Rejected(reason)

def _uint(value, limit, name):
    _need(type(value) is int and 0 <= value <= limit, name)
    return value

def _text(value, name):
    _need(type(value) is str and 1 <= len(value) <= 192 and
          all(32 <= ord(c) <= 126 for c in value), name)
    return value

def _obj(value, keys, name):
    _need(type(value) is dict and all(type(k) is str for k in value) and
          set(value) == keys, name)
    return value

def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def _sha(value, n=64):
    _need(type(value) is str and re.fullmatch("[0-9a-f]{%d}" % n, value), "hash")
    return value

def _stop(reason):
    return {"status": "STOP", "input_status": reason, "core_ran": False,
            "authorization": "none", "source_only": True, "command": None}

def _plain(value, depth=0, budget=None):
    # Reject subclasses before deepcopy or user operators could execute.
    if budget is None:
        budget = [2048]
    budget[0] -= 1
    _need(depth <= 12 and budget[0] >= 0, "bounded plain data")
    kind = type(value)
    _need(kind in (type(None), bool, int, str, list, dict), "plain JSON types only")
    if kind is str:
        _need(len(value) <= 192, "bounded strings")
    elif kind is list:
        _need(len(value) <= 32, "bounded arrays")
        for item in value:
            _plain(item, depth+1, budget)
    elif kind is dict:
        _need(len(value) <= 32 and all(type(k) is str for k in value), "plain keys")
        for key, item in value.items():
            _plain(key, depth+1, budget)
            _plain(item, depth+1, budget)

def _identity(value):
    strings = {"operation_id", "kernel_boot_id", "session_id", "clock_domain_id"}
    hashes = {"request_hash", "build_manifest_sha256", "source_record_sha256", "capture_sha256"}
    integers = {"tag", "generation", "trigger_id", "request_seq", "capture_seq", "source_admission_index"}
    _obj(value, strings | hashes | integers | {"tested_commit"}, "full source identity")
    for name in strings:
        _text(value[name], name)
    for name in hashes:
        _sha(value[name])
    _sha(value["tested_commit"], 40)
    for name in integers:
        _uint(value[name], U32, name)
    _need(value["tag"] > 0 and value["generation"] > 0 and value["request_seq"] > 0,
          "nonzero original tag/generation/request")
    return copy.deepcopy(value)

def _load_fixed_decoder(repo_root):
    # Definition only. This source-only task never invokes this loader.
    root = Path(repo_root).resolve()
    path = root / DECODER_PATH
    raw = path.read_bytes()
    _need(hashlib.sha256(raw).hexdigest() == DECODER_SHA256, "fixed decoder hash")
    spec = importlib.util.spec_from_file_location("_fixed_trace_code_section", path)
    _need(spec is not None and spec.loader is not None, "fixed decoder spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def decode_transport(packet, *, binding=None, profile=None, now_qpc_ns=None,
                     enabled=False, repo_root=None):
    """Proposed semantic transport view, always STOP/no planner/no movement.

    Root-only receipts below are newly proposed companion records, not extra
    fields injected into the strict C29 ABI. No labels authenticate a source.
    Full original timestamps and values are required, including middle samples.
    """
    _need(type(enabled) is bool, "enabled bool")
    _need(type(packet) is bytes and len(packet) <= 46, "bounded packet bytes")
    if not enabled:
        return _stop("DISABLED")
    if binding is None or profile is None or now_qpc_ns is None or repo_root is None:
        return _stop("INPUT_UNAVAILABLE")
    _plain(binding)
    _plain(profile)
    binding = copy.deepcopy(_obj(binding, {
        "kind", "receipt_id", "profile_id", "session_handle", "view_handle",
        "frame_seq", "e", "source_context_sha256"}, "private transport binding"))
    _need(binding["kind"] == "B_PRIVATE_TRANSPORT_BINDING_PROPOSED_V1" and
          binding["profile_id"] == PROFILE_ID, "private binding version")
    _text(binding["receipt_id"], "binding receipt")
    session = _uint(binding["session_handle"], U32, "issued session handle")
    view = _uint(binding["view_handle"], 255, "issued private view handle")
    sequence = _uint(binding["frame_seq"], 65535, "local transport sequence")
    e = _uint(binding["e"], 8, "E")
    _need(e in (0, 1, 2, 4, 8), "E domain")
    profile = copy.deepcopy(_obj(profile, {
        "profile_id", "origin_mode", "origin_receipt_id", "origin_qpc_ns",
        "source_identity", "original_acquisition_qpc_ns", "original_source_qpc_ns",
        "original_values", "original_indices", "timestamp_record_sha256", "raw_quality_by_channel",
        "mapped_flags_by_channel", "quality_record_sha256", "receiver_qpc_ns"}, "profile"))
    _need(profile["profile_id"] == PROFILE_ID and profile["origin_mode"] == ORIGIN_MODE,
          "explicit relative1us profile")
    _text(profile["origin_receipt_id"], "original fixed Root origin receipt")
    origin = _uint(profile["origin_qpc_ns"], U63, "original Root origin QPC")
    identity = _identity(profile["source_identity"])
    _need(_digest(identity) == _sha(binding["source_context_sha256"]), "full identity binding")
    acquisitions = profile["original_acquisition_qpc_ns"]
    sources = profile["original_source_qpc_ns"]
    values = profile["original_values"]
    indices = profile["original_indices"]
    # Minimum top emits one selected lane per frame. Multi-point identity and
    # block aggregation need a separately reviewed contract; do not imply it.
    _need(type(acquisitions) is list and len(acquisitions) == 1 and
          type(sources) is list and type(values) is list and
          type(indices) is list and len(sources) == len(values) == len(indices) == 1,
          "minimum singleton original records")
    for index in indices:
        _uint(index, U32, "original acquisition index")
    for qpc in acquisitions:
        _uint(qpc, U63, "original acquisition QPC")
    for qpc in sources:
        if qpc is not None:
            _uint(qpc, U63, "original source QPC")
    for value in values:
        if value is not None:
            _uint(value, 65535, "original raw uint16")
    time_record = {"origin_qpc_ns": origin, "acquisition_qpc_ns": acquisitions,
                   "source_qpc_ns": sources, "original_values": values, "original_indices": indices,
                   "source_context_sha256": binding["source_context_sha256"]}
    _need(_digest(time_record) == _sha(profile["timestamp_record_sha256"]), "retained original record hash")
    raw_quality = _obj(profile["raw_quality_by_channel"], {"0", "1", "2", "3"}, "opaque qualities")
    mapped = _obj(profile["mapped_flags_by_channel"], {"0", "1", "2", "3"}, "Root quality mapping")
    for channel in raw_quality:
        _uint(raw_quality[channel], 255, "raw uint8 quality")
        flags = _obj(mapped[channel], FLAG_KEYS, "mapped flags")
        _need(all(type(v) is bool for v in flags.values()), "mapped flags bool")
    quality_record = {"raw_quality_by_channel": raw_quality, "mapped_flags_by_channel": mapped,
                      "source_context_sha256": binding["source_context_sha256"]}
    _need(_digest(quality_record) == _sha(profile["quality_record_sha256"]), "Root quality record hash")
    receiver = _uint(profile["receiver_qpc_ns"], U63, "receiver QPC")
    now = _uint(now_qpc_ns, U63, "now QPC")
    _need(origin <= min(acquisitions) and max(acquisitions) <= receiver <= now,
          "original clock ordering; no receiver-as-acquisition substitution")
    _need(35 <= len(packet) <= 46, "frame length")
    magic, version, kind, length, frame_view, frame_seq, tick_low = struct.unpack_from("<2sBBBBHI", packet)
    _need(magic == b"\xA5\x5A" and version == 3 and kind == OUTER_TYPE_PROPOSED,
          "private outer type E4; reject legacy7/FORCE8")
    _need(length <= 32 and len(packet) == 14 + length and frame_view == view and frame_seq == sequence,
          "outer identity/length")
    _need(struct.unpack_from("<H", packet, len(packet)-2)[0] ==
          binascii.crc_hqx(packet[2:-2], 0xFFFF), "CRC")
    payload = packet[12:-2]
    _need(payload[0] == 2, "explicit payload revision2")
    decoder = _load_fixed_decoder(repo_root)
    # This local copy reuses only the fixed parser for unchanged coding fields.
    legacy = decoder.decode_payload(bytes([1]) + payload[1:],
                                    {"session": session, "config_epoch": view, "e": e})
    _need(legacy["count"] == len(acquisitions) and legacy["first_tick_ms"] <= U32 and
          legacy["first_tick_ms"] == tick_low, "relative view count/tick")
    points = []
    for i, point in enumerate(legacy["points"]):
        tick = _uint(point["tick_ms"], U32, "relative1us acquisition tick")
        qpc = acquisitions[i]
        _need(point["index"] == indices[i], "original index association, not frame sequence")
        _need(qpc >= origin and (qpc-origin)//1000 == tick, "exact original acquisition association")
        flags = mapped[str(legacy["channel"])]
        _need(all(point[k] == flags[k] for k in FLAG_KEYS), "Root quality mapping mismatch")
        source = sources[i]
        if point["valid"]:
            _need(source is not None and origin <= source <= qpc, "retained source origin")
            _need((source-origin)//1000 == point["source_tick_ms"], "held/fresh source association")
            _need((source < qpc) == point["held"], "held ordering")
        else:
            _need(source is None and values[i] is None, "invalid data remains null")
        points.append({"index": point["index"], "relative_tick_us": tick,
                       "original_acquisition_qpc_ns": qpc, "remainder_ns": (qpc-origin)%1000,
                       "original_source_qpc_ns": source, "decoded_value": point["value"],
                       "original_value": values[i], "byte_exact_value": point["value"] == values[i],
                       "source_age_ns": None if source is None else now-source})
    ages_ok = all(p["source_age_ns"] is None or p["source_age_ns"] <= 100_000_000 for p in points)
    return {**_stop("TRANSPORT_STRUCTURAL_ONLY"), "profile_id": PROFILE_ID,
            "points": points, "source_identity": identity, "raw_quality_uint8": raw_quality,
            "source_age_100ms_met": ages_ok, "c29_uint12_values_possible":
            all(v is None or v <= 4095 for v in values),
            "lossy_decoded_values_match_original": all(p["byte_exact_value"] for p in points),
            "frame_sha256": hashlib.sha256(packet).hexdigest(),
            "binding_receipt_id": binding["receipt_id"],
            "authentication": "NOT_ESTABLISHED_BY_JSON_OR_HASHES",
            "C29": {"source": C29_SOURCE, "path": C29_PATH,
                    "boundary": "Root must supply the exact original C29 candidate/receipt; never invoked here"}}

def select_control_route(*, requested_route):
    _need(requested_route in ("PC_DIRECT", "FPGA_G05"), "requested control path")
    return {**_stop("SOURCE_ONLY_NO_CONTROL_RELEASE"), "requested_route": requested_route,
            "route": "NONE"}
