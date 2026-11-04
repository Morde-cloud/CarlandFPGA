"""COMPOUND_DELTA_V1: one same-round command for two axes and speed.

Pure codec: importing this module opens no file, port, thread or connection.
The MCU owns limit enforcement, accumulated targets, execution and duplicate
rejection. The publisher owns explicit ARM, monotonic run/command/wire sequence
allocation and sending the same legal command round to both destinations.
PWM values are command proxies and never measured RPM.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct

SCHEMA = "COMPOUND_DELTA_V1"
FRAME_SIZE = 32
OP_DELTA = 6
OP_KEEPALIVE = 7
VALID = 1
PAUSE = 2
STOP = 4
SOURCE_TO_CODE = {"PC_DIRECT": 1, "FPGA_OUTPUT": 2, "MANUAL": 3}
SOURCE_BY_CODE = {value: key for key, value in SOURCE_TO_CODE.items()}


class DeltaError(ValueError):
    """The supplied command or frame violates the locked wire schema."""


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise DeltaError(f"{name} must be an integer in {low}..{high}")
    return value


def crc16_ccitt_false(data):
    """poly=0x1021, init=0xffff, refin/refout=false, xorout=0."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise DeltaError("CRC input must be bytes")
    crc = 0xFFFF
    for octet in bytes(data):
        crc ^= octet << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xFFFF
    return crc


@dataclass(frozen=True)
class DeltaCommand:
    seq: int
    source: str
    command_seq: int
    run_id: int
    yaw_delta_cd: int
    pitch_delta_cd: int
    speed_delta_permille: int
    move_ms: int = 500
    lease_ms: int = 300
    flags: int = VALID


@dataclass(frozen=True)
class KeepaliveCommand:
    seq: int
    source: str
    command_seq: int
    run_id: int
    lease_ms: int = 300


def _validate(command):
    for name in ("seq", "command_seq", "run_id"):
        _integer(getattr(command, name), name, 1, 0xFFFFFFFF)
    if type(command.source) is not str or command.source not in SOURCE_TO_CODE:
        raise DeltaError("source must be PC_DIRECT, FPGA_OUTPUT or MANUAL")
    for name in ("yaw_delta_cd", "pitch_delta_cd", "speed_delta_permille"):
        _integer(getattr(command, name), name, -32768, 32767)
    _integer(command.move_ms, "move_ms", 100, 1000)
    _integer(command.lease_ms, "lease_ms", 100, 500)
    _integer(command.flags, "flags", 0, 255)
    if command.flags not in (VALID, VALID | PAUSE, VALID | STOP):
        raise DeltaError("VALID is mandatory; PAUSE and STOP are mutually exclusive")
    if command.flags != VALID and any((command.yaw_delta_cd,
                                      command.pitch_delta_cd,
                                      command.speed_delta_permille)):
        raise DeltaError("PAUSE/STOP require all three deltas to be zero")


def encode_delta(seq, source, command_seq, run_id, yaw_delta_cd, pitch_delta_cd,
                 speed_delta_permille, move_ms=500, lease_ms=300, flags=VALID):
    """Encode the exact32B frame; positive yaw=left, positive pitch=up.

    speed_delta_permille changes the normalized0..1000 command-speed
    accumulator. It is neither a PWM delta nor a measured speed/RPM delta.
    Use encode_keepalive for heartbeats: new wire seq, unchanged real command_seq.
    """
    command = DeltaCommand(seq, source, command_seq, run_id, yaw_delta_cd,
                           pitch_delta_cd, speed_delta_permille, move_ms,
                           lease_ms, flags)
    _validate(command)
    frame = bytearray(FRAME_SIZE)
    frame[:4] = b"\xd3\x4c\x01\x06"
    struct.pack_into("<I", frame, 4, seq)
    frame[8], frame[9] = SOURCE_TO_CODE[source], flags
    struct.pack_into("<hhh", frame, 10, yaw_delta_cd, pitch_delta_cd,
                     speed_delta_permille)
    #16..17 remain zero: no hidden action/direction bits.
    struct.pack_into("<HIIH", frame, 18, move_ms, command_seq, run_id, lease_ms)
    struct.pack_into("<H", frame, 30, crc16_ccitt_false(frame[:30]))
    return bytes(frame)


def decode_delta(frame):
    """Validate bytes and return a frozen DeltaCommand; perform no action."""
    if not isinstance(frame, (bytes, bytearray, memoryview)):
        raise DeltaError("frame must be bytes")
    frame = bytes(frame)
    if len(frame) != FRAME_SIZE:
        raise DeltaError("exactly32 bytes required")
    if frame[:4] != b"\xd3\x4c\x01\x06":
        raise DeltaError("DELTA magic/version/opcode mismatch")
    if crc16_ccitt_false(frame[:30]) != struct.unpack_from("<H", frame, 30)[0]:
        raise DeltaError("CRC mismatch")
    if frame[16:18] != b"\x00\x00":
        raise DeltaError("reserved16..17 must be zero")
    if frame[8] not in SOURCE_BY_CODE:
        raise DeltaError("unknown action source")
    yaw, pitch, speed = struct.unpack_from("<hhh", frame, 10)
    move, command_seq, run_id, lease = struct.unpack_from("<HIIH", frame, 18)
    command = DeltaCommand(struct.unpack_from("<I", frame, 4)[0],
                           SOURCE_BY_CODE[frame[8]], command_seq, run_id,
                           yaw, pitch, speed, move, lease, frame[9])
    _validate(command)
    return command


def encode_keepalive(seq, source, command_seq, run_id, lease_ms=300):
    """Encode a non-AI heartbeat referencing the last real DELTA round.

    The MCU must require the same source/run/command and an unexpired live
    lease. Host/source validity is still required separately; this codec
    cannot extend an expired AI command or re-ARM/restart motion.
    """
    #Use the unchanged validators for the shared identities and lease only.
    command = DeltaCommand(seq, source, command_seq, run_id, 0, 0, 0,
                           lease_ms=lease_ms)
    _validate(command)
    frame = bytearray(FRAME_SIZE)
    frame[:4] = b"\xd3\x4c\x01\x07"
    struct.pack_into("<I", frame, 4, seq)
    frame[8], frame[9] = SOURCE_TO_CODE[source], VALID
    #10..19 remain zero: no deltas, reserved fields or move duration.
    struct.pack_into("<IIH", frame, 20, command_seq, run_id, lease_ms)
    struct.pack_into("<H", frame, 30, crc16_ccitt_false(frame[:30]))
    return bytes(frame)


def decode_keepalive(frame):
    """Validate opcode7 bytes; no lease renewal or command is performed."""
    if not isinstance(frame, (bytes, bytearray, memoryview)):
        raise DeltaError("frame must be bytes")
    frame = bytes(frame)
    if len(frame) != FRAME_SIZE or frame[:4] != b"\xd3\x4c\x01\x07":
        raise DeltaError("KEEPALIVE size/magic/version/opcode mismatch")
    if crc16_ccitt_false(frame[:30]) != struct.unpack_from("<H", frame, 30)[0]:
        raise DeltaError("CRC mismatch")
    if frame[8] not in SOURCE_BY_CODE or frame[9] != VALID:
        raise DeltaError("KEEPALIVE source/VALID flags mismatch")
    if frame[10:20] != bytes(10):
        raise DeltaError("KEEPALIVE deltas/reserved/move must all be zero")
    command_seq, run_id, lease = struct.unpack_from("<IIH", frame, 20)
    command = KeepaliveCommand(struct.unpack_from("<I", frame, 4)[0],
                               SOURCE_BY_CODE[frame[8]], command_seq, run_id, lease)
    for name in ("seq", "command_seq", "run_id"):
        _integer(getattr(command, name), name, 1, 0xFFFFFFFF)
    _integer(command.lease_ms, "lease_ms", 100, 500)
    return command


def speed_to_pwm(speed_permille):
    """Normalized0..1000 speed -> OFF or250..750 PWM permille, half up."""
    _integer(speed_permille, "speed_permille", 0, 1000)
    return 0 if speed_permille == 0 else 250 + (500 * speed_permille + 500) // 1000


def accumulate_virtual(yaw_cd, pitch_cd, speed_permille, yaw_delta_cd,
                       pitch_delta_cd, speed_delta_permille):
    """Pure virtual-side arithmetic for one already-authorized normal round.

    Returns(yaw_cd,pitch_cd,speed_permille). This helper does not allocate or
    deduplicate command identities, process flags, send bytes or authorize
    motion. Its global envelope is yaw+/-9000, pitch-4500..6800, speed0..1000.
    Actual MCU servo configuration can constrain angles further. Do not use
    these returned commands as measured pose, feedback, RPM or acceptance.
    """
    _integer(yaw_cd, "yaw_cd", -9000, 9000)
    _integer(pitch_cd, "pitch_cd", -4500, 6800)
    _integer(speed_permille, "speed_permille", 0, 1000)
    for name, value in (("yaw_delta_cd", yaw_delta_cd),
                        ("pitch_delta_cd", pitch_delta_cd),
                        ("speed_delta_permille", speed_delta_permille)):
        _integer(value, name, -32768, 32767)
    return (max(-9000, min(9000, yaw_cd + yaw_delta_cd)),
            max(-4500, min(6800, pitch_cd + pitch_delta_cd)),
            max(0, min(1000, speed_permille + speed_delta_permille)))


__all__ = ["SCHEMA", "FRAME_SIZE", "OP_DELTA", "OP_KEEPALIVE", "VALID", "PAUSE", "STOP",
           "SOURCE_TO_CODE", "SOURCE_BY_CODE", "DeltaError", "DeltaCommand", "KeepaliveCommand",
           "crc16_ccitt_false", "encode_delta", "decode_delta",
           "encode_keepalive", "decode_keepalive", "speed_to_pwm", "accumulate_virtual"]
