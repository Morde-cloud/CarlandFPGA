"""Pure byte-to-data normalizer for B117; no I/O or physical authority."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
REQUIREMENTS_SHA256 = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
REQUEST_SCHEMA = "B113_EXTERNAL_ORIGINAL_SCAN_REQUEST_V1"
NORMALIZED_SCHEMA = "B113_NORMALIZED_EXTERNAL_SCAN_V1"
MAX_REQUEST_BYTES = 262144
MAX_SOURCE_BYTES = 1048576
MAX_COMPANION_BYTES = 262144
MAX_COMPANIONS_TOTAL = 1048576
MAX_TOTAL_INPUT_BYTES = 2097152
MAX_JSON_DEPTH = 12
MAX_STRING_BYTES = 1024
MAX_UINT63 = (1 << 63) - 1
MAX_UINT32 = (1 << 32) - 1
MAX_UINT16 = (1 << 16) - 1
FRESHNESS_LIMIT_NS = 100000000
PROVENANCE_CLASSES = ("NEW_ORIGINAL_LIVE_ROOT", "HISTORICAL_ORIGINAL", "SYNTHETIC_TEST")
TOP_KEYS = ("schema", "task", "source_provenance", "source_payload", "scan", "lineage", "association", "companions")
TASK_KEYS = ("task_id", "task_version", "work_id", "requirements_sha256")
PROVENANCE_KEYS = ("class", "declared_by", "source_note", "mapping_state")
SOURCE_KEYS = ("format_label", "bytes", "sha256")
SCAN_KEYS = ("scan_id_uint63", "origin_qpc_ns", "acquisition_qpc_ns", "clock_domain_id", "lanes")
LANE_KEYS = ("channel", "raw_sample_uint16", "root_quality_uint16", "mapped_flags", "staged_quality_uint4",
             "acquisition_qpc_ns", "acquisition_tick_us", "acquisition_remainder_ns",
             "source_qpc_ns", "source_tick_us", "source_remainder_ns", "session", "index", "view", "frame_seq")
FLAG_KEYS = ("valid", "saturated", "held", "source_fault")
LINEAGE_KEYS = ("operation_id", "request_id", "request_hash", "tested_commit", "build_id_hex128", "boot_id",
                "session_id", "tag", "trigger_id", "generation", "request_seq", "capture_seq")
ASSOCIATION_KEYS = ("profile_id", "binding_receipt_id", "e", "source_context_sha256",
                    "timestamp_record_sha256", "quality_record_sha256", "receiver_qpc_ns",
                    "evaluation_now_qpc_ns", "evaluation_clock_id", "receiver_clock_id", "freshness_limit_ns")
COMPANION_KEYS = ("channel", "format_label", "bytes", "sha256")


class Refused(ValueError):
    """Stable, non-echoing refusal with a machine-readable code and JSON path."""

    __slots__ = ("code", "path")

    def __init__(self, code: str, path: str = "$") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}")


@dataclass(frozen=True)
class NormalizedExternalScanV1:
    request_bytes: bytes
    source_bytes: bytes
    companion_bytes: tuple[bytes, bytes, bytes, bytes]
    provenance: dict
    source: dict
    scan: dict
    lineage: dict
    association: dict
    companions: tuple[dict, dict, dict, dict]
    integrity: dict
    mapping: dict
    authority: dict
    execution_route: str

    def to_jsonable(self) -> dict:
        """Return metadata without body bytes; exact bytes remain on the object."""
        return {
            "schema": NORMALIZED_SCHEMA,
            "request_sha256": self.integrity["request_sha256"],
            "provenance": self.provenance,
            "source": {k: v for k, v in self.source.items() if k != "bytes"},
            "scan": self.scan,
            "lineage": self.lineage,
            "association": self.association,
            "companions": tuple({k: v for k, v in item.items() if k != "bytes"} for item in self.companions),
            "integrity": self.integrity,
            "mapping": self.mapping,
            "authority": self.authority,
            "execution_route": self.execution_route,
        }


def physical_start(*args: object, **kwargs: object) -> dict:
    """Always unavailable; supplied objects are intentionally neither inspected nor invoked."""
    return {
        "status": "STOP",
        "provider": "A_ORIGINAL_PROVIDER_UNAVAILABLE",
        "physical_start_authority": False,
        "product_acceptance": False,
    }


def _refuse(code: str, path: str = "$") -> None:
    raise Refused(code, path)


def _obj(value, keys, path):
    if type(value) is not dict:
        _refuse("TYPE", path)
    if len(value) != len(keys) or set(value.keys()) != set(keys):
        _refuse("KEYS", path)
    return value


def _bool(value, path):
    if type(value) is not bool:
        _refuse("TYPE", path)
    return value


def _int(value, low, high, path):
    if type(value) is not int:
        _refuse("TYPE", path)
    if value < low or value > high:
        _refuse("RANGE", path)
    return value


def _text(value, path, minimum=0, maximum=192, ascii_only=False):
    if type(value) is not str:
        _refuse("TYPE", path)
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        _refuse("STRING_SURROGATE", path)
    if size < minimum or size > maximum:
        _refuse("STRING_RANGE", path)
    if ascii_only and any(ord(ch) < 0x20 or ord(ch) > 0x7E for ch in value):
        _refuse("PRINTABLE_ASCII", path)
    return value


def _enum(value, allowed, path):
    if type(value) is not str:
        _refuse("TYPE", path)
    if value not in allowed:
        _refuse("ENUM", path)
    return value


def _sha256(value, path):
    if type(value) is not str:
        _refuse("TYPE", path)
    if len(value) != 64:
        _refuse("SHA256_LENGTH", path)
    if value.lower() != value or any(ch not in "0123456789abcdef" for ch in value):
        _refuse("SHA256_FORMAT", path)
    return value


def _fixed_hex(value, length, path):
    if type(value) is not str:
        _refuse("TYPE", path)
    if len(value) != length:
        _refuse("HEX_LENGTH", path)
    if value.lower() != value or any(ch not in "0123456789abcdef" for ch in value):
        _refuse("HEX_FORMAT", path)
    return value


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            _refuse("JSON_DUPLICATE_KEY")
        value[key] = item
    return value


def _reject_float(token):
    _refuse("JSON_FLOAT")


def _reject_constant(token):
    _refuse("JSON_NONFINITE")


def _parse_integer(token):
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > 19:
        _refuse("JSON_INTEGER_RANGE")
    value = int(token)
    if value < -MAX_UINT63 or value > MAX_UINT63:
        _refuse("JSON_INTEGER_RANGE")
    return value


def _check_depth(text):
    depth = 0
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                _refuse("JSON_DEPTH")
        elif ch in "]}":
            depth -= 1


def _check_string(value, path):
    try:
        raw = value.encode("utf-8")
    except UnicodeEncodeError:
        _refuse("STRING_SURROGATE", path)
    if len(raw) > MAX_STRING_BYTES:
        _refuse("STRING_RANGE", path)


def _validate_tree(value, depth, path):
    if depth > MAX_JSON_DEPTH:
        _refuse("JSON_DEPTH", path)
    if type(value) is dict:
        for key, item in value.items():
            _check_string(key, path + ".*")
            _validate_tree(item, depth + 1, path + ".*")
    elif type(value) is list:
        for item in value:
            _validate_tree(item, depth + 1, path + "[]")
    elif type(value) is str:
        _check_string(value, path)
    elif value is None or type(value) is bool or type(value) is int:
        return
    else:
        _refuse("JSON_TYPE", path)


def _parse_request(request_bytes):
    if len(request_bytes) < 1:
        _refuse("REQUEST_SIZE")
    if len(request_bytes) > MAX_REQUEST_BYTES:
        _refuse("REQUEST_SIZE")
    if request_bytes.startswith(b"\xef\xbb\xbf"):
        _refuse("BOM")
    try:
        text = request_bytes.decode("utf-8")
    except UnicodeDecodeError:
        _refuse("UTF8")
    _check_depth(text)
    try:
        value = json.loads(text, object_pairs_hook=_pairs,
                           parse_float=_reject_float, parse_constant=_reject_constant,
                           parse_int=_parse_integer)
    except Refused:
        raise
    except json.JSONDecodeError:
        _refuse("JSON_SYNTAX")
    except ValueError:
        _refuse("JSON_SYNTAX")
    except RecursionError:
        _refuse("JSON_DEPTH")
    _validate_tree(value, 1, "$")
    return value


def _parse_lane(value, index, path):
    lane = _obj(value, LANE_KEYS, path)
    channel = _int(lane["channel"], 0, MAX_UINT32, path + ".channel")
    if channel != index:
        _refuse("LANE_CHANNEL", path + ".channel")
    raw = lane["raw_sample_uint16"]
    if raw is not None:
        raw = _int(raw, 0, MAX_UINT16, path + ".raw_sample_uint16")
    quality = _int(lane["root_quality_uint16"], 0, MAX_UINT16, path + ".root_quality_uint16")
    flags = _obj(lane["mapped_flags"], FLAG_KEYS, path + ".mapped_flags")
    valid = _bool(flags["valid"], path + ".mapped_flags.valid")
    saturated = _bool(flags["saturated"], path + ".mapped_flags.saturated")
    held = _bool(flags["held"], path + ".mapped_flags.held")
    source_fault = _bool(flags["source_fault"], path + ".mapped_flags.source_fault")
    staged = _int(lane["staged_quality_uint4"], 0, 15, path + ".staged_quality_uint4")
    expected = (1 if valid else 0) + (2 if saturated else 0) + (4 if held else 0) + (8 if source_fault else 0)
    if staged != expected:
        _refuse("STAGED_QUALITY", path + ".staged_quality_uint4")
    acquisition = _int(lane["acquisition_qpc_ns"], 0, MAX_UINT63, path + ".acquisition_qpc_ns")
    acquisition_tick = _int(lane["acquisition_tick_us"], 0, MAX_UINT32, path + ".acquisition_tick_us")
    acquisition_remainder = _int(lane["acquisition_remainder_ns"], 0, 999, path + ".acquisition_remainder_ns")
    source = lane["source_qpc_ns"]
    source_tick = lane["source_tick_us"]
    source_remainder = lane["source_remainder_ns"]
    if source is not None:
        source = _int(source, 0, MAX_UINT63, path + ".source_qpc_ns")
    if source_tick is not None:
        source_tick = _int(source_tick, 0, MAX_UINT32, path + ".source_tick_us")
    if source_remainder is not None:
        source_remainder = _int(source_remainder, 0, 999, path + ".source_remainder_ns")
    session = _int(lane["session"], 0, MAX_UINT32, path + ".session")
    sample_index = _int(lane["index"], 0, MAX_UINT32, path + ".index")
    view = _int(lane["view"], 0, 255, path + ".view")
    frame_seq = _int(lane["frame_seq"], 0, MAX_UINT16, path + ".frame_seq")
    if valid:
        if raw is None:
            _refuse("VALID_SAMPLE", path + ".raw_sample_uint16")
        if source is None or source_tick is None or source_remainder is None:
            _refuse("VALID_SOURCE", path)
    else:
        if raw is not None:
            _refuse("INVALID_NULL", path + ".raw_sample_uint16")
        if source is not None or source_tick is not None or source_remainder is not None:
            _refuse("INVALID_SOURCE", path)
        if saturated or held:
            _refuse("INVALID_FLAGS", path + ".mapped_flags")
    return {
        "channel": channel,
        "raw_sample_uint16": raw,
        "root_quality_uint16": quality,
        "mapped_flags": {"valid": valid, "saturated": saturated, "held": held, "source_fault": source_fault},
        "staged_quality_uint4": staged,
        "acquisition_qpc_ns": acquisition,
        "acquisition_tick_us": acquisition_tick,
        "acquisition_remainder_ns": acquisition_remainder,
        "source_qpc_ns": source,
        "source_tick_us": source_tick,
        "source_remainder_ns": source_remainder,
        "session": session,
        "index": sample_index,
        "view": view,
        "frame_seq": frame_seq,
    }


def _parse_envelope(request, source_bytes, companion_bytes):
    root = _obj(request, TOP_KEYS, "$")
    _enum(root["schema"], (REQUEST_SCHEMA,), "$.schema")
    task = _obj(root["task"], TASK_KEYS, "$.task")
    task_id = _text(task["task_id"], "$.task.task_id", 1, 192, True)
    if task_id != TASK_ID:
        _refuse("TASK_ID", "$.task.task_id")
    version = _int(task["task_version"], TASK_VERSION, TASK_VERSION, "$.task.task_version")
    if version != TASK_VERSION:
        _refuse("TASK_VERSION", "$.task.task_version")
    work_id = _text(task["work_id"], "$.task.work_id", 1, 192, True)
    req_hash = _sha256(task["requirements_sha256"], "$.task.requirements_sha256")
    if req_hash != REQUIREMENTS_SHA256:
        _refuse("TASK_REQUIREMENTS", "$.task.requirements_sha256")

    provenance = _obj(root["source_provenance"], PROVENANCE_KEYS, "$.source_provenance")
    source_class = _enum(provenance["class"], PROVENANCE_CLASSES, "$.source_provenance.class")
    declared_by = _text(provenance["declared_by"], "$.source_provenance.declared_by", 1, 192, True)
    source_note = _text(provenance["source_note"], "$.source_provenance.source_note", 0, 1024, False)
    mapping_state = _enum(provenance["mapping_state"], ("B_NEUTRAL_AWAITING_A_MAPPING",),
                          "$.source_provenance.mapping_state")

    source_desc = _obj(root["source_payload"], SOURCE_KEYS, "$.source_payload")
    source_format = _text(source_desc["format_label"], "$.source_payload.format_label", 1, 192, True)
    declared_source_length = _int(source_desc["bytes"], 1, MAX_SOURCE_BYTES, "$.source_payload.bytes")
    declared_source_sha = _sha256(source_desc["sha256"], "$.source_payload.sha256")
    actual_source_sha = hashlib.sha256(source_bytes).hexdigest()
    if declared_source_length != len(source_bytes):
        _refuse("SOURCE_LENGTH", "$.source_payload.bytes")
    if declared_source_sha != actual_source_sha:
        _refuse("SOURCE_SHA", "$.source_payload.sha256")

    scan_raw = _obj(root["scan"], SCAN_KEYS, "$.scan")
    scan_id = _int(scan_raw["scan_id_uint63"], 0, MAX_UINT63, "$.scan.scan_id_uint63")
    origin = _int(scan_raw["origin_qpc_ns"], 0, MAX_UINT63, "$.scan.origin_qpc_ns")
    acquisition = _int(scan_raw["acquisition_qpc_ns"], 0, MAX_UINT63, "$.scan.acquisition_qpc_ns")
    clock_domain = _text(scan_raw["clock_domain_id"], "$.scan.clock_domain_id", 1, 192, True)
    lane_raw = scan_raw["lanes"]
    if type(lane_raw) is not list:
        _refuse("TYPE", "$.scan.lanes")
    if len(lane_raw) != 4:
        _refuse("LANES_LENGTH", "$.scan.lanes")
    lanes = tuple(_parse_lane(item, index, f"$.scan.lanes[{index}]") for index, item in enumerate(lane_raw))

    lineage_raw = _obj(root["lineage"], LINEAGE_KEYS, "$.lineage")
    operation_id = _text(lineage_raw["operation_id"], "$.lineage.operation_id", 1, 192, True)
    request_id = _text(lineage_raw["request_id"], "$.lineage.request_id", 1, 192, True)
    lineage_request_hash = _sha256(lineage_raw["request_hash"], "$.lineage.request_hash")
    tested_commit = _fixed_hex(lineage_raw["tested_commit"], 40, "$.lineage.tested_commit")
    build_id = _fixed_hex(lineage_raw["build_id_hex128"], 32, "$.lineage.build_id_hex128")
    boot_id = _text(lineage_raw["boot_id"], "$.lineage.boot_id", 1, 192, True)
    session_id = _int(lineage_raw["session_id"], 0, MAX_UINT32, "$.lineage.session_id")
    tag = _int(lineage_raw["tag"], 0, MAX_UINT32, "$.lineage.tag")
    trigger_id = _int(lineage_raw["trigger_id"], 0, MAX_UINT32, "$.lineage.trigger_id")
    generation = _int(lineage_raw["generation"], 0, MAX_UINT32, "$.lineage.generation")
    request_seq = _int(lineage_raw["request_seq"], 0, MAX_UINT32, "$.lineage.request_seq")
    capture_seq = _int(lineage_raw["capture_seq"], 0, MAX_UINT32, "$.lineage.capture_seq")
    lineage = {
        "operation_id": operation_id, "request_id": request_id, "request_hash": lineage_request_hash,
        "tested_commit": tested_commit, "build_id_hex128": build_id, "boot_id": boot_id,
        "session_id": session_id, "tag": tag, "trigger_id": trigger_id, "generation": generation,
        "request_seq": request_seq, "capture_seq": capture_seq,
    }

    assoc_raw = _obj(root["association"], ASSOCIATION_KEYS, "$.association")
    profile_id = _text(assoc_raw["profile_id"], "$.association.profile_id", 1, 192, True)
    binding_receipt_id = _text(assoc_raw["binding_receipt_id"], "$.association.binding_receipt_id", 1, 192, True)
    e_value = _int(assoc_raw["e"], 0, 8, "$.association.e")
    if e_value not in (0, 1, 2, 4, 8):
        _refuse("ASSOCIATION_E", "$.association.e")
    source_context_sha = _sha256(assoc_raw["source_context_sha256"], "$.association.source_context_sha256")
    timestamp_record_sha = _sha256(assoc_raw["timestamp_record_sha256"], "$.association.timestamp_record_sha256")
    quality_record_sha = _sha256(assoc_raw["quality_record_sha256"], "$.association.quality_record_sha256")
    receiver = _int(assoc_raw["receiver_qpc_ns"], 0, MAX_UINT63, "$.association.receiver_qpc_ns")
    evaluation = _int(assoc_raw["evaluation_now_qpc_ns"], 0, MAX_UINT63, "$.association.evaluation_now_qpc_ns")
    evaluation_clock = _text(assoc_raw["evaluation_clock_id"], "$.association.evaluation_clock_id", 1, 192, True)
    receiver_clock = _text(assoc_raw["receiver_clock_id"], "$.association.receiver_clock_id", 1, 192, True)
    freshness_limit = _int(assoc_raw["freshness_limit_ns"], FRESHNESS_LIMIT_NS, FRESHNESS_LIMIT_NS,
                          "$.association.freshness_limit_ns")
    association = {
        "profile_id": profile_id, "binding_receipt_id": binding_receipt_id, "e": e_value,
        "source_context_sha256": source_context_sha, "timestamp_record_sha256": timestamp_record_sha,
        "quality_record_sha256": quality_record_sha, "receiver_qpc_ns": receiver,
        "evaluation_now_qpc_ns": evaluation, "evaluation_clock_id": evaluation_clock,
        "receiver_clock_id": receiver_clock, "freshness_limit_ns": freshness_limit,
    }

    companion_raw = root["companions"]
    if type(companion_raw) is not list:
        _refuse("TYPE", "$.companions")
    if len(companion_raw) != 4:
        _refuse("COMPANIONS_LENGTH", "$.companions")
    companions = []
    for index, (desc_raw, body) in enumerate(zip(companion_raw, companion_bytes)):
        path = f"$.companions[{index}]"
        desc = _obj(desc_raw, COMPANION_KEYS, path)
        channel = _int(desc["channel"], 0, MAX_UINT32, path + ".channel")
        if channel != index:
            _refuse("COMPANION_CHANNEL", path + ".channel")
        format_label = _text(desc["format_label"], path + ".format_label", 1, 192, True)
        length = _int(desc["bytes"], 1, MAX_COMPANION_BYTES, path + ".bytes")
        declared_sha = _sha256(desc["sha256"], path + ".sha256")
        actual_sha = hashlib.sha256(body).hexdigest()
        if length != len(body):
            _refuse("COMPANION_LENGTH", path + ".bytes")
        if declared_sha != actual_sha:
            _refuse("COMPANION_SHA", path + ".sha256")
        companions.append({"channel": channel, "format_label": format_label, "bytes": body,
                           "byte_length": len(body), "declared_sha256": declared_sha,
                           "computed_sha256": actual_sha, "matches": True})

    return {
        "work_id": work_id, "provenance": {"class": source_class, "declared_by": declared_by,
        "source_note": source_note, "mapping_state": mapping_state},
        "source": {"format_label": source_format, "bytes": source_bytes, "byte_length": len(source_bytes),
                   "declared_sha256": declared_source_sha, "computed_sha256": actual_source_sha, "matches": True},
        "scan": {"scan_id_uint63": scan_id, "origin_qpc_ns": origin, "acquisition_qpc_ns": acquisition,
                 "clock_domain_id": clock_domain, "lanes": lanes},
        "lineage": lineage, "association": association, "companions": tuple(companions),
    }


def _qpc_sum(origin, tick_us, remainder_ns, path):
    total = origin + tick_us * 1000 + remainder_ns
    if total > MAX_UINT63:
        _refuse("QPC_OVERFLOW", path)
    return total


def normalize_external_original_scan_v1(request_bytes, source_scan_bytes, companions):
    if type(request_bytes) is not bytes:
        _refuse("REQUEST_TYPE")
    if type(source_scan_bytes) is not bytes:
        _refuse("SOURCE_TYPE")
    if type(companions) not in (tuple, list):
        _refuse("BODY_CONTAINER")
    if len(companions) != 4:
        _refuse("BODY_COUNT")
    if any(type(item) is not bytes for item in companions):
        _refuse("BODY_TYPE")
    if len(source_scan_bytes) < 1 or len(source_scan_bytes) > MAX_SOURCE_BYTES:
        _refuse("SOURCE_SIZE")
    for index, item in enumerate(companions):
        if len(item) < 1 or len(item) > MAX_COMPANION_BYTES:
            _refuse("COMPANION_SIZE", f"$[{index}]")
    total = len(request_bytes) + len(source_scan_bytes) + sum(len(item) for item in companions)
    if total > MAX_TOTAL_INPUT_BYTES:
        _refuse("TOTAL_INPUT_SIZE")
    parsed = _parse_request(request_bytes)
    envelope = _parse_envelope(parsed, source_scan_bytes, tuple(companions))
    scan = envelope["scan"]
    association = envelope["association"]
    lineage = envelope["lineage"]
    clock_domain = scan["clock_domain_id"]
    if association["receiver_clock_id"] != clock_domain:
        _refuse("CLOCK_DOMAIN_MISMATCH", "$.association.receiver_clock_id")
    if association["evaluation_clock_id"] != clock_domain:
        _refuse("CLOCK_DOMAIN_MISMATCH", "$.association.evaluation_clock_id")

    origin = scan["origin_qpc_ns"]
    acquisition = scan["acquisition_qpc_ns"]
    lanes = []
    for index, lane in enumerate(scan["lanes"]):
        path = f"$.scan.lanes[{index}]"
        if lane["acquisition_qpc_ns"] != acquisition:
            _refuse("ACQUISITION_MISMATCH", path + ".acquisition_qpc_ns")
        expected_acquisition = _qpc_sum(origin, lane["acquisition_tick_us"],
                                        lane["acquisition_remainder_ns"], path + ".acquisition_qpc_ns")
        if expected_acquisition != lane["acquisition_qpc_ns"]:
            _refuse("QPC_EQUATION", path + ".acquisition_qpc_ns")
        if lane["source_qpc_ns"] is not None:
            expected_source = _qpc_sum(origin, lane["source_tick_us"],
                                        lane["source_remainder_ns"], path + ".source_qpc_ns")
            if expected_source != lane["source_qpc_ns"]:
                _refuse("QPC_EQUATION", path + ".source_qpc_ns")
            if lane["source_qpc_ns"] > lane["acquisition_qpc_ns"]:
                _refuse("SOURCE_AFTER_ACQUISITION", path + ".source_qpc_ns")
            is_held = lane["source_qpc_ns"] < lane["acquisition_qpc_ns"]
            if lane["mapped_flags"]["held"] != is_held:
                _refuse("HELD_MISMATCH", path + ".mapped_flags.held")
        lanes.append(lane)

    if not (origin <= acquisition <= association["receiver_qpc_ns"] <= association["evaluation_now_qpc_ns"]):
        _refuse("TIMESTAMP_ORDER", "$.association")
    if any(item["session"] != lineage["session_id"] for item in lanes):
        _refuse("SESSION_MISMATCH", "$.lineage.session_id")
    if len({item["view"] for item in lanes}) != 1:
        _refuse("VIEW_MISMATCH", "$.scan.lanes")
    frames = [item["frame_seq"] for item in lanes]
    if not all(frames[index] < frames[index + 1] for index in range(3)):
        _refuse("FRAME_ORDER", "$.scan.lanes")
    evaluation = association["evaluation_now_qpc_ns"]
    freshness_limit = association["freshness_limit_ns"]
    normalized_lanes = []
    for lane in lanes:
        item = dict(lane)
        item["mapped_flags"] = dict(lane["mapped_flags"])
        if lane["mapped_flags"]["valid"]:
            age = evaluation - lane["source_qpc_ns"]
            item["freshness"] = {
                "age_ns": age,
                "freshness_limit_ns": freshness_limit,
                "within_declared_100ms": age <= freshness_limit,
                "classification": "WITHIN_DECLARED_100MS" if age <= freshness_limit else "ABOVE_DECLARED_100MS",
                "clock_domain_id": clock_domain,
                "clock_domain_declared_equal": True,
                "clock_domain_authenticated": False,
                "declared_clock_only": True,
            }
        else:
            item["freshness"] = {
                "age_ns": None,
                "freshness_limit_ns": freshness_limit,
                "within_declared_100ms": None,
                "classification": "NOT_APPLICABLE_INVALID",
                "clock_domain_id": clock_domain,
                "clock_domain_declared_equal": True,
                "clock_domain_authenticated": False,
                "declared_clock_only": True,
            }
        normalized_lanes.append(item)

    companion_digest = hashlib.sha256()
    for body in companions:
        companion_digest.update(len(body).to_bytes(8, "big"))
        companion_digest.update(body)
    association_canonical = json.dumps(association, ensure_ascii=False, sort_keys=True,
                                       separators=(",", ":")).encode("utf-8")
    valid_values = [item["raw_sample_uint16"] for item in lanes if item["mapped_flags"]["valid"]]
    legacy_numeric = all(value <= 4095 for value in valid_values)
    staging_shape = (bool(valid_values) and all(value <= 4095 for value in valid_values)
                     and lineage["tag"] != 0 and lineage["build_id_hex128"] != "0" * 32)
    provenance = dict(envelope["provenance"])
    provenance.update({"authenticated": False, "declared_only": True})
    integrity = {
        "all_declared_lengths_match": True,
        "all_declared_hashes_match": True,
        "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "association_canonical_sha256": hashlib.sha256(association_canonical).hexdigest(),
        "companion_set_sha256": companion_digest.hexdigest(),
        "association_semantics_bound_to_companion_bytes": False,
        "supplied_association_hashes_semantically_verified": False,
        "supplied_lineage_request_hash_verified": False,
        "producer_authenticated": False,
        "boot_authenticated": False,
        "current_source_authenticated": False,
        "clock_domain_authenticated": False,
        "authentication_note": "Hashes and echoed identifiers establish byte consistency only.",
    }
    mapping = {
        "pure_data_accepted": True,
        "raw_uint16_preserved_without_truncation": True,
        "valid_lane_count": len(valid_values),
        "legacy_host103_numeric_compatible": legacy_numeric,
        "legacy_host103_numeric_compatibility_label": "NON_AUTHORITY",
        "host103_fake_plan_eligible": False,
        "legacy_mapping_created": False,
        "source_fault_is_opaque": True,
        "staging_shape_ready": staging_shape,
        "staging_shape_label": "DATA_SHAPE_ONLY",
        "a_mapping_required_before_original_semantic_binding": True,
        "source_numerical_association_verified": False,
    }
    execution_route = "PURE_UNBOUND_DATA"
    authority = {
        "declared_source_provenance": provenance["class"],
        "execution_route": execution_route,
        "producer_authenticated": False,
        "boot_authenticated": False,
        "current_source_eligible": False,
        "physical_start_authority": False,
        "physical_provider": None,
        "loaded_build": False,
        "physical_ready": False,
        "product_acceptance": False,
    }
    scan_out = {
        "scan_id_uint63": scan["scan_id_uint63"],
        "origin_qpc_ns": scan["origin_qpc_ns"],
        "acquisition_qpc_ns": scan["acquisition_qpc_ns"],
        "clock_domain_id": clock_domain,
        "clock_domain_authenticated": False,
        "clock_domain_declared_equal": True,
        "lanes": tuple(normalized_lanes),
    }
    return NormalizedExternalScanV1(
        request_bytes=request_bytes,
        source_bytes=source_scan_bytes,
        companion_bytes=tuple(companions),
        provenance=provenance,
        source=dict(envelope["source"]),
        scan=scan_out,
        lineage=dict(lineage),
        association=dict(association),
        companions=tuple(envelope["companions"]),
        integrity=integrity,
        mapping=mapping,
        authority=authority,
        execution_route=execution_route,
    )


__all__ = [
    "Refused",
    "NormalizedExternalScanV1",
    "normalize_external_original_scan_v1",
    "physical_start",
]
