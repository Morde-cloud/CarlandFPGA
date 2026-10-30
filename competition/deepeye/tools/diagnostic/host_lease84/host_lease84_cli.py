"""Strict bounded file CLI for the pure host-lease structural ledger."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).resolve().parents[1] / "host_lease83"
sys.path.insert(0, str(SOURCE))
import host_lease83 as host_lease

INPUT_SCHEMA = "host_lease84/cli-input/v1"
OUTPUT_SCHEMA = "host_lease84/cli-output/v1"
MAX_INPUT_BYTES = 64 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_OPERATIONS = 16
_TOP_KEYS = {"schema", "mode", "operations"}
_COMMON = {"sent": False, "packet_created": False, "physical_acceptance": False,
           "action_authorized": False}


class InputRefused(ValueError):
    def __init__(self, code: str):
        super().__init__(code); self.code = code


def _refuse(code: str) -> None:
    raise InputRefused(code)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result: _refuse("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _no_float(value: str) -> None:
    _refuse("FLOAT_FORBIDDEN")


def _no_constant(value: str) -> None:
    _refuse("NONFINITE_FORBIDDEN")


def _parse(raw: bytes) -> Any:
    try:
        text = raw.decode("utf-8")
        value = json.loads(text, object_pairs_hook=_pairs, parse_float=_no_float,
                           parse_constant=_no_constant)
        _check_unicode(value)
        return value
    except InputRefused:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        _refuse("STRICT_JSON_REQUIRED")


def _check_unicode(value: Any) -> None:
    if type(value) is str:
        try: value.encode("utf-8")
        except UnicodeEncodeError: _refuse("UNICODE_ENCODING")
    elif type(value) is list:
        for item in value: _check_unicode(item)
    elif type(value) is dict:
        for key, item in value.items():
            _check_unicode(key); _check_unicode(item)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _keys(obj: Any, required: set[str], allowed: set[str], name: str) -> dict[str, Any]:
    if type(obj) is not dict: _refuse(f"{name}_TYPE")
    if required - obj.keys(): _refuse(f"{name}_MISSING")
    if obj.keys() - allowed: _refuse(f"{name}_UNKNOWN_FIELD")
    return obj


def _text(value: Any, name: str) -> str:
    if type(value) is not str or not value or len(value.encode("utf-8")) > 128:
        _refuse(f"{name}_TYPE_OR_LENGTH")
    return value


def _operation_name(value: Any) -> str:
    if type(value) is dict and type(value.get("op")) is str:
        try:
            if len(value["op"].encode("utf-8")) <= 128: return value["op"]
        except UnicodeEncodeError:
            pass
    return "<invalid>"


def _operation(value: Any, ledger: host_lease.HostLeaseLedger) -> dict[str, Any]:
    name = _operation_name(value)
    if name == "register":
        body = _keys(value, {"op", "request"}, {"op", "request"}, "OPERATION")
        return ledger.register(body["request"])
    if name == "ack":
        body = _keys(value, {"op", "ack"}, {"op", "ack"}, "OPERATION")
        return ledger.ack(body["ack"])
    if name == "evaluate_deadline":
        body = _keys(value, {"op", "request", "now_ns"},
                     {"op", "request", "now_ns"}, "OPERATION")
        return ledger.evaluate_deadline(body["request"], body["now_ns"])
    if name == "terminate":
        body = _keys(value, {"op", "request", "at_ns", "reason"},
                     {"op", "request", "at_ns", "reason", "newer_boot_id", "newer_epoch"},
                     "OPERATION")
        return ledger.terminate(body["request"], at_ns=body["at_ns"], reason=body["reason"],
                                newer_boot_id=body.get("newer_boot_id"),
                                newer_epoch=body.get("newer_epoch"))
    if name == "disable":
        _keys(value, {"op"}, {"op"}, "OPERATION")
        ledger.disable()
        return {"mode": ledger.mode, "enabled": ledger.enabled,
                **_COMMON, "status": "DISABLED"}
    _refuse("OPERATION_UNSUPPORTED")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _input_info(path: str | None, raw: bytes | None, parsed: Any = None) -> dict[str, Any]:
    info: dict[str, Any] = {"path": path, "raw_bytes": None, "raw_sha256": None,
                            "canonical_bytes": None, "canonical_sha256": None}
    if raw is not None:
        info.update({"raw_bytes": len(raw), "raw_sha256": _sha(raw)})
    if parsed is not None:
        canonical = _canonical(parsed)
        info.update({"canonical_bytes": len(canonical),
                     "canonical_sha256": _sha(canonical)})
    return info


def _finish(mode: str, status: str, exit_code: int, input_info: dict[str, Any],
            operations: list[dict[str, Any]], code: str | None = None) -> tuple[bytes, int]:
    core: dict[str, Any] = {
        "schema": OUTPUT_SCHEMA, "mode": mode, "status": status, "exit_code": exit_code,
        "input": input_info, "operations": operations,
        "output_contract": {"raw_stdout_hash_recorded_by_caller": True,
                            "max_output_bytes": MAX_OUTPUT_BYTES},
        "authority": {"send": False, "callback": False, "network": False,
                      "hardware": False, "clock_read": False, "action_authorized": False},
    }
    if code is not None: core["code"] = code
    payload = _canonical(core)
    core["payload_canonical"] = {"bytes": len(payload), "sha256": _sha(payload)}
    output = _canonical(core) + b"\n"
    if len(output) > MAX_OUTPUT_BYTES:
        return _finish("PRODUCTION", "REFUSED", 2, input_info,
                       [], "OUTPUT_LIMIT_EXCEEDED")
    return output, exit_code


def _refusal(path: str | None, raw: bytes | None, code: str,
             parsed: Any = None) -> tuple[bytes, int]:
    return _finish("PRODUCTION", "REFUSED", 2, _input_info(path, raw, parsed), [], code)


def execute(raw: bytes, input_path: str | None = None) -> tuple[bytes, int]:
    if len(raw) > MAX_INPUT_BYTES:
        return _refusal(input_path, None, "INPUT_TOO_LARGE")
    try:
        parsed = _parse(raw)
        info = _input_info(input_path, raw, parsed)
        body = _keys(parsed, {"schema", "operations"}, _TOP_KEYS, "INPUT")
        if body["schema"] != INPUT_SCHEMA: _refuse("INPUT_SCHEMA_UNSUPPORTED")
        mode = body.get("mode", host_lease.PRODUCTION)
        if type(mode) is not str: _refuse("MODE_TYPE")
        if mode not in (host_lease.PRODUCTION, host_lease.SYNTHETIC_FIXTURE):
            _refuse("MODE_UNSUPPORTED")
        values = body["operations"]
        if type(values) is not list or not 1 <= len(values) <= MAX_OPERATIONS:
            _refuse("OPERATIONS_COUNT")
        ledger = host_lease.HostLeaseLedger(mode=mode)
    except (InputRefused, host_lease.Refused) as exc:
        parsed_value = parsed if "parsed" in locals() else None
        return _refusal(input_path, raw, exc.code, parsed_value)

    records: list[dict[str, Any]] = []
    refused: str | None = None
    for index, value in enumerate(values):
        name = _operation_name(value)
        try:
            result = _operation(value, ledger)
        except (InputRefused, host_lease.Refused) as exc:
            result = {"status": "REFUSED", "code": exc.code, **_COMMON}
            refused = exc.code
        result_bytes = _canonical(result)
        records.append({"index": index, "operation": name, "result": result,
                        "result_canonical_bytes": len(result_bytes),
                        "result_canonical_sha256": _sha(result_bytes)})
        if refused is not None: break

    if refused is not None:
        return _finish(mode, "REFUSED", 2, info, records, refused)
    final_status = records[-1]["result"].get("status")
    if final_status == "LEASE":
        return _finish(mode, "POSITIVE", 0, info, records)
    status = "INPUT_UNAVAILABLE" if any(
        item["result"].get("status") == "INPUT_UNAVAILABLE" for item in records
    ) else "NO_POSITIVE_RESULT"
    return _finish(mode, status, 3, info, records)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    if len(args) != 2:
        output, code = _refusal(None, None, "INPUT_PATH_ARGUMENT_REQUIRED")
    else:
        path = Path(args[1])
        try:
            size = path.stat().st_size
        except OSError:
            output, code = _refusal(str(path), None, "INPUT_READ_ERROR")
        else:
            if size > MAX_INPUT_BYTES:
                info = {"path": str(path), "raw_bytes": size, "raw_sha256": None,
                        "canonical_bytes": None, "canonical_sha256": None}
                output, code = _finish("PRODUCTION", "REFUSED", 2, info, [],
                                       "INPUT_TOO_LARGE")
            else:
                try:
                    raw = path.read_bytes()
                except OSError:
                    output, code = _refusal(str(path), None, "INPUT_READ_ERROR")
                else:
                    output, code = execute(raw, str(path))
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()
    return code


__all__ = ["execute", "main", "InputRefused", "MAX_INPUT_BYTES", "MAX_OUTPUT_BYTES"]


if __name__ == "__main__":
    raise SystemExit(main())
