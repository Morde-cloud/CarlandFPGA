"""Bounded synthetic host ACK-deadline ledger. It has no send or I/O surface."""

from __future__ import annotations

import hashlib, json, re
from dataclasses import dataclass, field
from typing import Any

U63_MAX = (1 << 63) - 1
MAX_TRANSACTIONS = 16
MAX_ACKS = 8
MAX_CONTEXT_BYTES = 4096
REQUEST_TYPE = 0x0E
PRODUCTION = "PRODUCTION"
SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
_PROFILES = {"FAST_9600": (9600, 3000), "STRESS_300": (300, 12000)}
_REQUEST_KEYS = {
    "session", "request_type", "seq", "cmd_id", "payload_sha256", "transaction_tag",
    "boot_id", "epoch", "first_send_ns", "original_ttl_ms", "profile", "context",
}
_ACK_REQUIRED = {
    "receipt_ns", "phase", "capture_complete", "fault", "remaining_ttl_ms",
}
_ACK_OPTIONAL = {"usb_processing_bound_ns", "clock_error_bound_ns", "raw_header_tick"}
_ACK_EXTRA = _ACK_REQUIRED | _ACK_OPTIONAL
_PHASES = {"ACCEPTED": 0, "APPLIED": 1, "CAPTURED": 2, "REJECTED": 3, "STOPPED": 4}
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class Refused(ValueError):
    def __init__(self, code: str):
        super().__init__(code); self.code = code


def _fail(code: str) -> None:
    raise Refused(code)


def _keys(obj: Any, required: set[str], allowed: set[str], name: str) -> dict[str, Any]:
    if type(obj) is not dict: _fail(f"{name}_TYPE")
    if required - obj.keys(): _fail(f"{name}_MISSING")
    if obj.keys() - allowed: _fail(f"{name}_UNKNOWN_FIELD")
    return obj


def _uint(value: Any, bits: int, name: str) -> int:
    if type(value) is not int: _fail(f"{name}_TYPE")
    if not 0 <= value < (1 << bits): _fail(f"{name}_RANGE")
    return value


def _text(value: Any, name: str, limit: int = 128, empty: bool = False) -> str:
    if type(value) is not str: _fail(f"{name}_TYPE")
    try: size = len(value.encode("utf-8"))
    except UnicodeEncodeError: _fail(f"{name}_ENCODING")
    if (size == 0 and not empty) or size > limit: _fail(f"{name}_LENGTH")
    return value


def _boolean(value: Any, name: str) -> bool:
    if type(value) is not bool: _fail(f"{name}_TYPE")
    return value


def _phase(value: Any) -> str:
    phase = _text(value, "PHASE", 16)
    if phase not in _PHASES: _fail("PHASE_UNSUPPORTED")
    return phase


def _plain(value: Any, depth: int = 0) -> Any:
    if depth > 16: _fail("CONTEXT_DEPTH")
    if value is None or type(value) is bool: return value
    if type(value) is int:
        if not -(1 << 63) <= value <= U63_MAX: _fail("CONTEXT_INTEGER_RANGE")
        return value
    if type(value) is str:
        if len(value) > MAX_CONTEXT_BYTES: _fail("CONTEXT_TEXT_LENGTH")
        return value
    if type(value) is list:
        if len(value) > 64: _fail("CONTEXT_LIST_SIZE")
        return [_plain(item, depth + 1) for item in value]
    if type(value) is dict:
        if len(value) > 64: _fail("CONTEXT_MAP_SIZE")
        out: dict[str, Any] = {}
        for key, item in value.items():
            _text(key, "CONTEXT_KEY"); out[key] = _plain(item, depth + 1)
        return out
    _fail("CONTEXT_PLAIN_JSON_REQUIRED")


def _freeze_context(value: Any) -> tuple[bytes, Any]:
    plain = _plain(value)
    try:
        raw = json.dumps(plain, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError): _fail("CONTEXT_PLAIN_JSON_REQUIRED")
    if len(raw) > MAX_CONTEXT_BYTES: _fail("CONTEXT_BYTES")
    return raw, json.loads(raw)


def _request(obj: Any, extra: set[str] = frozenset()) -> dict[str, Any]:
    source = _keys(obj, _REQUEST_KEYS, _REQUEST_KEYS | extra, "REQUEST")
    request_type = _uint(source["request_type"], 8, "REQUEST_TYPE")
    if request_type != REQUEST_TYPE: _fail("REQUEST_TYPE_UNSUPPORTED")
    seq = _uint(source["seq"], 16, "SEQ")
    if _uint(source["cmd_id"], 16, "CMD_ID") != seq: _fail("CMD_ID_MISMATCH")
    payload = _text(source["payload_sha256"], "PAYLOAD_SHA256", 64)
    if _HEX64.fullmatch(payload) is None: _fail("PAYLOAD_SHA256_FORMAT")
    profile = _text(source["profile"], "PROFILE", 16)
    if profile not in _PROFILES: _fail("PROFILE_UNSUPPORTED")
    ttl = _uint(source["original_ttl_ms"], 32, "ORIGINAL_TTL")
    if not 1 <= ttl <= _PROFILES[profile][1]: _fail("ORIGINAL_TTL_RANGE")
    context_bytes, context = _freeze_context(source["context"])
    return {
        "session": _text(source["session"], "SESSION"), "request_type": request_type,
        "seq": seq, "cmd_id": seq, "payload_sha256": payload,
        "transaction_tag": _text(source["transaction_tag"], "TRANSACTION_TAG"),
        "boot_id": _text(source["boot_id"], "BOOT_ID"),
        "epoch": _uint(source["epoch"], 63, "EPOCH"),
        "first_send_ns": _uint(source["first_send_ns"], 63, "FIRST_SEND_NS"),
        "original_ttl_ms": ttl, "profile": profile,
        "context": context, "context_bytes": context_bytes,
    }


def _same(left: dict[str, Any], right: dict[str, Any]) -> bool:
    fields = ("session", "request_type", "seq", "cmd_id", "payload_sha256", "transaction_tag",
              "boot_id", "epoch", "first_send_ns", "original_ttl_ms", "profile")
    return all(left[name] == right[name] for name in fields) and left["context_bytes"] == right["context_bytes"]


def _optional_uint(obj: dict[str, Any], name: str, bits: int) -> int | None:
    value = obj.get(name)
    return None if value is None else _uint(value, bits, name)


def _ack(obj: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    _keys(obj, _REQUEST_KEYS | _ACK_REQUIRED, _REQUEST_KEYS | _ACK_EXTRA, "ACK")
    request = _request(obj, _ACK_EXTRA)
    body = {
        "receipt_ns": _uint(obj["receipt_ns"], 63, "RECEIPT_NS"),
        "phase": _phase(obj["phase"]),
        "capture_complete": _boolean(obj["capture_complete"], "CAPTURE_COMPLETE"),
        "fault": _uint(obj["fault"], 32, "FAULT"),
        "remaining_ttl_ms": _uint(obj["remaining_ttl_ms"], 32, "REMAINING_TTL"),
        "usb_processing_bound_ns": _optional_uint(obj, "usb_processing_bound_ns", 63),
        "clock_error_bound_ns": _optional_uint(obj, "clock_error_bound_ns", 63),
        "raw_header_tick": _optional_uint(obj, "raw_header_tick", 64),
    }
    if body["remaining_ttl_ms"] > request["original_ttl_ms"]: _fail("REMAINING_TTL_RANGE")
    return request, body


def _digest(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _add_u63(left: int, right: int) -> int:
    if left < 0 or right < 0 or left > U63_MAX - right: _fail("UINT63_OVERFLOW")
    return left + right


def wire_ns(baud: int) -> int:
    """Exact ceiling for a 34-byte, 10-bit UART frame at 300 or 9600 baud."""
    if type(baud) is not int or baud not in (300, 9600): _fail("BAUD_UNSUPPORTED")
    return (34 * 10 * 1_000_000_000 + baud - 1) // baud


@dataclass
class _Record:
    request: dict[str, Any]
    original_cap_ns: int
    deadline_ns: int | None = None
    terminal: str | None = None
    captured_ok: bool = False
    last_phase: str | None = None
    acks: list[bytes] = field(default_factory=list)
    raw_header_ticks: list[int | None] = field(default_factory=list)


class HostLeaseLedger:
    """Pure detached-fact ledger. Even SYNTHETIC_FIXTURE grants no action."""

    def __init__(self, mode: str = PRODUCTION):
        if type(mode) is not str: _fail("MODE_TYPE")
        if mode not in (PRODUCTION, SYNTHETIC_FIXTURE): _fail("MODE_UNSUPPORTED")
        self.mode = mode; self.enabled = True
        self._records: dict[tuple[str, int, int], _Record] = {}
        self._last_time_ns: int | None = None

    def disable(self) -> None:
        self.enabled = False

    def _live(self) -> bool:
        return self.enabled and self.mode == SYNTHETIC_FIXTURE

    def _time(self, value: int) -> None:
        if self._last_time_ns is not None and value < self._last_time_ns: _fail("TIME_REGRESSION")
        self._last_time_ns = value

    def _find(self, request: dict[str, Any]) -> _Record:
        key = (request["session"], request["request_type"], request["seq"])
        record = self._records.get(key)
        if record is None: _fail("UNKNOWN_TRANSACTION")
        if not _same(record.request, request): _fail("IDENTITY_MISMATCH")
        return record

    def _unavailable_reason(self, record: _Record) -> str | None:
        if record.terminal is not None: return record.terminal
        if self.mode == PRODUCTION: return "PRODUCTION_INPUT_UNAVAILABLE"
        if not self.enabled: return "LEDGER_DISABLED"
        return None

    def _base(self, record: _Record, status: str, reason: str) -> dict[str, Any]:
        return {
            "status": status, "reason": reason, "mode": self.mode, "enabled": self.enabled,
            "session": record.request["session"], "request_type": record.request["request_type"],
            "seq": record.request["seq"], "cmd_id": record.request["cmd_id"],
            "payload_sha256": record.request["payload_sha256"],
            "transaction_tag": record.request["transaction_tag"],
            "boot_id": record.request["boot_id"], "epoch": record.request["epoch"],
            "profile": record.request["profile"], "first_send_ns": record.request["first_send_ns"],
            "original_ttl_ms": record.request["original_ttl_ms"],
            "original_cap_ns": record.original_cap_ns, "deadline_ns": record.deadline_ns,
            "terminal": record.terminal, "ack_count": len(record.acks),
            "last_phase": record.last_phase, "captured_eligible": record.captured_ok,
            "raw_header_ticks": list(record.raw_header_ticks),
            "original_context": json.loads(record.request["context_bytes"]),
            "context_sha256": hashlib.sha256(record.request["context_bytes"]).hexdigest(),
            "sent": False, "packet_created": False, "physical_acceptance": False,
            "action_authorized": False,
            "lease_scope": "SYNTHETIC_STRUCTURAL_ONLY" if status == "LEASE" else None,
        }

    def _registration_result(self, record: _Record, status: str, reason: str) -> dict[str, Any]:
        result = self._base(record, status, reason)
        result["context"] = json.loads(record.request["context_bytes"])
        return result

    def register(self, obj: Any) -> dict[str, Any]:
        request = _request(obj)
        key = (request["session"], request["request_type"], request["seq"])
        record = self._records.get(key)
        if record is not None:
            if not _same(record.request, request): _fail("IDENTITY_MISMATCH")
            if self._last_time_ns is not None: self._expire(record, self._last_time_ns)
            unavailable = self._unavailable_reason(record)
            if unavailable is not None:
                return self._registration_result(record, "INPUT_UNAVAILABLE", unavailable)
            return self._registration_result(record, "DUPLICATE", "IDENTICAL_REGISTRATION")
        if len(self._records) >= MAX_TRANSACTIONS: _fail("TRANSACTION_CAPACITY")
        cap = _add_u63(request["first_send_ns"], request["original_ttl_ms"] * 1_000_000)
        self._time(request["first_send_ns"])
        record = _Record(request=request, original_cap_ns=cap)
        self._records[key] = record
        unavailable = self._unavailable_reason(record)
        if unavailable is not None:
            return self._registration_result(record, "INPUT_UNAVAILABLE", unavailable)
        return self._registration_result(record, "REGISTERED", "IMMUTABLE_ORIGINAL_RETAINED")

    def _expire(self, record: _Record, now_ns: int) -> None:
        if record.terminal is None and (
            now_ns >= record.original_cap_ns
            or (record.deadline_ns is not None and now_ns >= record.deadline_ns)
        ): record.terminal = "EXPIRED"

    def ack(self, obj: Any) -> dict[str, Any]:
        request, body = _ack(obj)
        record = self._find(request)
        if self._last_time_ns is not None: self._expire(record, self._last_time_ns)
        fingerprint = _digest(body)
        if fingerprint in record.acks:
            unavailable = self._unavailable_reason(record)
            if unavailable is not None:
                return self._base(record, "INPUT_UNAVAILABLE", unavailable)
            return self._base(record, "DUPLICATE_ACK", "NO_NEW_FACT")
        unavailable = self._unavailable_reason(record)
        if not self._live() or unavailable is not None:
            return self._base(record, "INPUT_UNAVAILABLE",
                              unavailable or "PRODUCTION_INPUT_UNAVAILABLE")
        if len(record.acks) >= MAX_ACKS: _fail("ACK_CAPACITY")
        receipt = body["receipt_ns"]
        if receipt < request["first_send_ns"]: _fail("TIME_REGRESSION")
        usb_bound, clock_bound = body["usb_processing_bound_ns"], body["clock_error_bound_ns"]
        terminal: str | None = None
        if body["fault"] != 0:
            terminal = "FAULT"
        elif body["phase"] in ("REJECTED", "STOPPED"):
            terminal = body["phase"]
        elif record.captured_ok and body["phase"] == "CAPTURED" and not body["capture_complete"]:
            terminal = "CAPTURE_LOST"
        elif record.captured_ok and _PHASES[body["phase"]] < _PHASES["CAPTURED"]:
            terminal = "PHASE_REGRESSION"
        elif record.captured_ok and (usb_bound is None or clock_bound is None):
            terminal = "BOUNDS_UNAVAILABLE"
        if terminal is not None:
            self._time(receipt)
            record.acks.append(fingerprint)
            record.raw_header_ticks.append(body["raw_header_tick"])
            record.terminal = terminal
            return self._base(record, "INPUT_UNAVAILABLE", terminal)
        if usb_bound is None or clock_bound is None:
            self._time(receipt)
            record.acks.append(fingerprint)
            record.raw_header_ticks.append(body["raw_header_tick"])
            return self._base(record, "INPUT_UNAVAILABLE", "BOUNDS_UNAVAILABLE")
        baud = _PROFILES[record.request["profile"]][0]
        deductions = _add_u63(_add_u63(wire_ns(baud), usb_bound), clock_bound)
        remaining_window = body["remaining_ttl_ms"] * 1_000_000
        residual = remaining_window - deductions if remaining_window > deductions else 0
        receipt_cap = _add_u63(receipt, residual)
        candidate = min(record.original_cap_ns, receipt_cap)
        deadline = candidate if record.deadline_ns is None else min(record.deadline_ns, candidate)
        positive = receipt_cap > receipt
        self._time(receipt)
        record.acks.append(fingerprint)
        record.raw_header_ticks.append(body["raw_header_tick"])
        record.deadline_ns = deadline
        record.last_phase = body["phase"]
        self._expire(record, receipt)
        if record.terminal is not None: return self._base(record, "INPUT_UNAVAILABLE", record.terminal)
        eligible = (body["phase"] == "CAPTURED" and body["capture_complete"] and positive
                    and record.deadline_ns is not None and record.deadline_ns > receipt)
        if eligible: record.captured_ok = True
        if eligible:
            return self._base(record, "INPUT_UNAVAILABLE", "EXPLICIT_DEADLINE_QUERY_REQUIRED")
        if body["phase"] != "CAPTURED": reason = "CAPTURE_PHASE_REQUIRED"
        elif not body["capture_complete"]: reason = "CAPTURE_INCOMPLETE"
        else: reason = "NO_POSITIVE_WINDOW"
        return self._base(record, "INPUT_UNAVAILABLE", reason)

    def evaluate_deadline(self, obj: Any, now_ns: int) -> dict[str, Any]:
        request = _request(obj); record = self._find(request)
        now_ns = _uint(now_ns, 63, "NOW_NS")
        if now_ns < request["first_send_ns"]: _fail("TIME_REGRESSION")
        self._time(now_ns)
        self._expire(record, now_ns)
        unavailable = self._unavailable_reason(record)
        if unavailable is not None:
            return self._base(record, "INPUT_UNAVAILABLE", unavailable)
        if not record.captured_ok or record.deadline_ns is None:
            return self._base(record, "INPUT_UNAVAILABLE", "NO_ELIGIBLE_CAPTURED_ACK")
        if now_ns >= record.deadline_ns:
            self._expire(record, now_ns)
            return self._base(record, "INPUT_UNAVAILABLE", record.terminal)
        result = self._base(record, "LEASE", "SYNTHETIC_STRUCTURAL_ONLY")
        result.update({
            "now_ns": now_ns, "remaining_ns": record.deadline_ns - now_ns,
            "deadline_query": "EXPLICIT_SUPPLIED_ORIGINAL_UINT63_NS",
            "current_capture_freshness": "UNAVAILABLE",
            "measured_clock": "UNAVAILABLE", "ack_authenticity": "UNAVAILABLE",
            "motion_authorized": False,
        })
        return result

    def terminate(self, obj: Any, *, at_ns: int, reason: str,
                  newer_boot_id: str | None = None, newer_epoch: int | None = None) -> dict[str, Any]:
        request = _request(obj); record = self._find(request)
        reason = _text(reason, "TERMINAL_REASON", 32)
        if reason not in ("STOP", "CANCEL", "FAULT", "NEW_BOOT", "EPOCH", "SUPERSEDED"):
            _fail("TERMINAL_REASON_UNSUPPORTED")
        if reason == "NEW_BOOT":
            newer_boot_id = _text(newer_boot_id, "NEW_BOOT_ID")
            if newer_boot_id == request["boot_id"]: _fail("BOOT_NOT_NEWER")
        if reason == "EPOCH":
            epoch = _uint(newer_epoch, 63, "NEW_EPOCH")
            if epoch <= request["epoch"]: _fail("EPOCH_NOT_NEWER")
        at_ns = _uint(at_ns, 63, "TERMINATE_NS")
        if at_ns < request["first_send_ns"]: _fail("TIME_REGRESSION")
        if not self._live(): return self._base(record, "INPUT_UNAVAILABLE", "PRODUCTION_INPUT_UNAVAILABLE")
        self._time(at_ns)
        if record.terminal is None: self._expire(record, at_ns)
        if record.terminal is None: record.terminal = reason
        return self._base(record, "INPUT_UNAVAILABLE", record.terminal)


__all__ = ["HostLeaseLedger", "MAX_ACKS", "MAX_CONTEXT_BYTES", "MAX_TRANSACTIONS",
           "PRODUCTION", "REQUEST_TYPE", "Refused", "SYNTHETIC_FIXTURE", "U63_MAX", "wire_ns"]
