"""Strict codec for the physical display link v1.

The wire format and field meanings are defined by
``output/drill-demo-code-20261025/PROTOCOL.md``.  This module deliberately
rejects ambiguous JSON and lossy integer coercions; callers cannot silently
turn booleans, strings, NaN, or infinity into wire fields.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping


FRAME_SIZE = 32
MAGIC = b"\xD3\x4C"
VERSION = 1
REPLY_TYPE = 0x80

OP_ARM = 1
OP_SET = 2
OP_STOP = 3
OP_STATUS = 4

OP_TO_TYPE = {
    "arm": OP_ARM,
    "set": OP_SET,
    "stop": OP_STOP,
    "status": OP_STATUS,
}

SOURCE_TO_CODE = {
    "PC_DIRECT": 1,
    "FPGA_OUTPUT": 2,
    "MANUAL": 3,
}
SOURCE_BY_CODE = {value: key for key, value in SOURCE_TO_CODE.items()}

RESULT_NAMES = {
    0: "OK",
    1: "CRC",
    2: "FORMAT",
    3: "DISARMED",
    4: "RANGE",
    5: "REVERSE_WAIT",
    6: "SEQUENCE",
    7: "WATCHDOG",
    8: "SOURCE",
}

ANGLE_LIMIT_CD = 1500
DUTY_LIMIT_PERMILLE = 300
MOVE_TIME_MIN_MS = 100
MOVE_TIME_MAX_MS = 1000
UINT32_MAX = 0xFFFFFFFF
UNAVAILABLE_U16 = 0xFFFF
FRESH_FEEDBACK_MAX_AGE_MS = 1000


class CodecError(ValueError):
    """A JSON command or wire frame violates the fixed protocol."""


def crc16_ccitt_false(data: bytes | bytearray | memoryview) -> int:
    """Return CRC16-CCITT-FALSE (poly 0x1021, init 0xffff, no reflection)."""

    crc = 0xFFFF
    for octet in bytes(data):
        crc ^= octet << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _require_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CodecError(f"{field} must be an integer; bool is not accepted")
    if value < minimum or value > maximum:
        raise CodecError(f"{field} must be in [{minimum}, {maximum}]")
    return value


def degrees_to_centidegrees(value: Any, field: str = "angle") -> int:
    """Convert finite degrees to int16 centidegrees with half-up rounding."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CodecError(f"{field} must be a finite number of degrees")
    if isinstance(value, float) and not math.isfinite(value):
        raise CodecError(f"{field} must be finite")
    try:
        degrees = Decimal(str(value)) if isinstance(value, float) else Decimal(value)
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise CodecError(f"{field} is not a valid number") from exc
    if degrees < -Decimal(ANGLE_LIMIT_CD) / 100 or degrees > Decimal(ANGLE_LIMIT_CD) / 100:
        raise CodecError(f"{field} must be within +/-{ANGLE_LIMIT_CD / 100:g} degrees")
    centidegrees = (degrees * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(centidegrees)


def centidegrees_to_degrees(value: int) -> float:
    return value / 100.0


@dataclass(frozen=True, slots=True)
class Command:
    """Validated PC-side command before a protocol sequence is assigned."""

    op: str
    source: str
    yaw_cd: int = 0
    pitch_cd: int = 0
    duty_permille: int = 0
    direction: int = 0
    move_ms: int = 0
    source_seq: int = 0
    observation_seq: int = 0

    def __post_init__(self) -> None:
        if self.op not in OP_TO_TYPE:
            raise CodecError("op must be one of arm, set, stop, status")
        if self.source not in SOURCE_TO_CODE:
            raise CodecError("source must be PC_DIRECT, FPGA_OUTPUT, or MANUAL")

        if self.op == "set":
            _require_int(self.yaw_cd, "yaw_cd", -ANGLE_LIMIT_CD, ANGLE_LIMIT_CD)
            _require_int(self.pitch_cd, "pitch_cd", -ANGLE_LIMIT_CD, ANGLE_LIMIT_CD)
            _require_int(self.duty_permille, "duty_permille", 0, DUTY_LIMIT_PERMILLE)
            _require_int(self.direction, "direction", 0, 1)
            _require_int(self.move_ms, "move_ms", MOVE_TIME_MIN_MS, MOVE_TIME_MAX_MS)
            _require_int(self.source_seq, "source_seq", 0, UINT32_MAX)
            _require_int(self.observation_seq, "observation_seq", 0, UINT32_MAX)
            return

        for field in (
            "yaw_cd",
            "pitch_cd",
            "duty_permille",
            "direction",
            "move_ms",
            "source_seq",
            "observation_seq",
        ):
            if getattr(self, field) != 0:
                raise CodecError(f"{field} must be zero for {self.op}")

    def request_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {"op": self.op, "source": self.source}
        if self.op == "set":
            record.update(
                {
                    "yaw_deg": centidegrees_to_degrees(self.yaw_cd),
                    "pitch_deg": centidegrees_to_degrees(self.pitch_cd),
                    "duty_permille": self.duty_permille,
                    "direction": "forward" if self.direction == 0 else "reverse",
                    "move_ms": self.move_ms,
                    "source_seq": self.source_seq,
                    "observation_seq": self.observation_seq,
                }
            )
        return record


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CodecError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise CodecError(f"non-finite JSON number is not accepted: {value}")


def _json_loads(text: str) -> Any:
    try:
        return json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except CodecError:
        raise
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise CodecError("input line must contain exactly one JSON object") from exc


def parse_command_object(value: Any) -> Command:
    """Validate one decoded JSON object and return a normalized command."""

    if not isinstance(value, Mapping):
        raise CodecError("input must be a JSON object")
    if any(not isinstance(key, str) for key in value):
        raise CodecError("JSON object keys must be strings")

    common = {"op", "source"}
    set_fields = {
        "yaw_deg",
        "pitch_deg",
        "duty_permille",
        "direction",
        "move_ms",
        "source_seq",
        "observation_seq",
    }
    op = value.get("op")
    if op not in OP_TO_TYPE:
        raise CodecError("op must be one of arm, set, stop, status")

    required = common | (set_fields if op == "set" else set())
    unknown = set(value) - required
    missing = required - set(value)
    if unknown:
        raise CodecError("unknown key(s): " + ", ".join(sorted(unknown)))
    if missing:
        raise CodecError("missing key(s): " + ", ".join(sorted(missing)))

    source = value["source"]
    if not isinstance(source, str) or source not in SOURCE_TO_CODE:
        raise CodecError("source must be PC_DIRECT, FPGA_OUTPUT, or MANUAL")
    if op != "set":
        return Command(op=op, source=source)

    return Command(
        op="set",
        source=source,
        yaw_cd=degrees_to_centidegrees(value["yaw_deg"], "yaw_deg"),
        pitch_cd=degrees_to_centidegrees(value["pitch_deg"], "pitch_deg"),
        duty_permille=_require_int(
            value["duty_permille"], "duty_permille", 0, DUTY_LIMIT_PERMILLE
        ),
        direction=_require_int(value["direction"], "direction", 0, 1),
        move_ms=_require_int(
            value["move_ms"], "move_ms", MOVE_TIME_MIN_MS, MOVE_TIME_MAX_MS
        ),
        source_seq=_require_int(value["source_seq"], "source_seq", 0, UINT32_MAX),
        observation_seq=_require_int(
            value["observation_seq"], "observation_seq", 0, UINT32_MAX
        ),
    )


def parse_command_line(line: bytes | str) -> Command:
    """Parse one UTF-8 JSON line into a strictly validated command."""

    if isinstance(line, bytes):
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CodecError("input line is not valid UTF-8") from exc
    elif isinstance(line, str):
        text = line
    else:
        raise CodecError("input line must be bytes or str")
    if not text.strip():
        raise CodecError("empty input line")
    return parse_command_object(_json_loads(text))


def encode_command(command: Command, seq: int) -> bytes:
    """Encode a validated command and its newly assigned uint32 sequence."""

    if not isinstance(command, Command):
        raise CodecError("command must be a Command")
    _require_int(seq, "seq", 1, UINT32_MAX)

    frame = bytearray(FRAME_SIZE)
    frame[0:2] = MAGIC
    frame[2] = VERSION
    frame[3] = OP_TO_TYPE[command.op]
    struct.pack_into("<I", frame, 4, seq)
    frame[8] = SOURCE_TO_CODE[command.source]
    if command.op == "set":
        struct.pack_into("<h", frame, 10, command.yaw_cd)
        struct.pack_into("<h", frame, 12, command.pitch_cd)
        struct.pack_into("<H", frame, 14, command.duty_permille)
        frame[16] = command.direction
        struct.pack_into("<H", frame, 18, command.move_ms)
        struct.pack_into("<I", frame, 20, command.source_seq)
        struct.pack_into("<I", frame, 24, command.observation_seq)
    struct.pack_into("<H", frame, 30, crc16_ccitt_false(frame[:30]))
    return bytes(frame)


@dataclass(frozen=True, slots=True)
class Feedback:
    raw_position: int | None
    age_ms: int | None
    fresh: bool


@dataclass(frozen=True, slots=True)
class Reply:
    seq: int
    armed: bool
    result_code: int
    result: str
    target_yaw_cd: int
    target_pitch_cd: int
    requested_duty_permille: int
    direction: int
    active_source_code: int
    active_source: str | None
    motor_output_compiled_enabled: bool
    gimbal_output_compiled_enabled: bool
    last_joho_error: int | None
    yaw_feedback: Feedback
    pitch_feedback: Feedback
    servo_error_count: int


def _feedback(raw: int, age: int, fresh_bit: bool) -> Feedback:
    if raw == UNAVAILABLE_U16 or age == UNAVAILABLE_U16:
        return Feedback(raw_position=None, age_ms=None, fresh=False)
    fresh = bool(fresh_bit) and age <= FRESH_FEEDBACK_MAX_AGE_MS
    return Feedback(raw_position=raw, age_ms=age, fresh=fresh)


def decode_reply(frame: bytes | bytearray | memoryview) -> Reply:
    """Decode one exact 32-byte reply frame, rejecting malformed fields."""

    if not isinstance(frame, (bytes, bytearray, memoryview)):
        raise CodecError("reply frame must be bytes-like")
    data = bytes(frame)
    if len(data) != FRAME_SIZE:
        raise CodecError(f"reply frame must be exactly {FRAME_SIZE} bytes")
    if data[0:2] != MAGIC:
        raise CodecError("reply magic does not match d3 4c")
    if data[2] != VERSION:
        raise CodecError("reply version must be 1")
    if data[3] != REPLY_TYPE:
        raise CodecError("reply type must be 0x80")
    expected_crc = struct.unpack_from("<H", data, 30)[0]
    actual_crc = crc16_ccitt_false(data[:30])
    if actual_crc != expected_crc:
        raise CodecError("reply CRC does not match")

    armed_byte = data[8]
    if armed_byte not in (0, 1):
        raise CodecError("reply armed flag must be 0 or 1")
    result_code = data[9]
    if result_code not in RESULT_NAMES:
        raise CodecError(f"unknown reply result code: {result_code}")
    direction = data[16]
    if direction not in (0, 1):
        raise CodecError("reply direction must be 0 or 1")
    active_source_code = data[17]
    if active_source_code not in (0, *SOURCE_BY_CODE):
        raise CodecError("unknown reply active source")
    flags = data[18]
    if flags & 0xF0:
        raise CodecError("reply contains unknown flag bits")

    yaw_raw = struct.unpack_from("<H", data, 20)[0]
    pitch_raw = struct.unpack_from("<H", data, 22)[0]
    yaw_age = struct.unpack_from("<H", data, 24)[0]
    pitch_age = struct.unpack_from("<H", data, 26)[0]

    return Reply(
        seq=struct.unpack_from("<I", data, 4)[0],
        armed=bool(armed_byte),
        result_code=result_code,
        result=RESULT_NAMES[result_code],
        target_yaw_cd=struct.unpack_from("<h", data, 10)[0],
        target_pitch_cd=struct.unpack_from("<h", data, 12)[0],
        requested_duty_permille=struct.unpack_from("<H", data, 14)[0],
        direction=direction,
        active_source_code=active_source_code,
        active_source=SOURCE_BY_CODE.get(active_source_code),
        motor_output_compiled_enabled=bool(flags & 0x04),
        gimbal_output_compiled_enabled=bool(flags & 0x08),
        last_joho_error=None if data[19] == 0xFF else data[19],
        yaw_feedback=_feedback(yaw_raw, yaw_age, bool(flags & 0x01)),
        pitch_feedback=_feedback(pitch_raw, pitch_age, bool(flags & 0x02)),
        servo_error_count=struct.unpack_from("<H", data, 28)[0],
    )


__all__ = [
    "ANGLE_LIMIT_CD",
    "Command",
    "CodecError",
    "DUTY_LIMIT_PERMILLE",
    "FRAME_SIZE",
    "Feedback",
    "MAGIC",
    "OP_TO_TYPE",
    "REPLY_TYPE",
    "RESULT_NAMES",
    "Reply",
    "SOURCE_TO_CODE",
    "VERSION",
    "centidegrees_to_degrees",
    "crc16_ccitt_false",
    "decode_reply",
    "degrees_to_centidegrees",
    "encode_command",
    "parse_command_line",
    "parse_command_object",
]
