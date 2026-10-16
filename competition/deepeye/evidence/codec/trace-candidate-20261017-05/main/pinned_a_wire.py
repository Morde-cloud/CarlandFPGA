"""Bounded ABI3 framing reference. Valid bytes never authorize motion.

This module has no transport, hardware, model or process side effects. Consumers
must separately enforce BOOT/profile, request identity, observation age, capture,
TTL, motion limits and run state. TRACE stays rejected until its payload freezes.
"""
from dataclasses import dataclass
import struct

MAGIC = b'\xa5\x5a'
VERSION = 3
HEADER = struct.Struct('<2sBBBBHI')
MAX_PAYLOAD = 32
MAX_FRAME = 46
MAX_FEED = 4096
PAYLOAD_LENGTHS = {1:18, 2:6, 3:14, 4:18, 5:10, 6:4, 8:18, 9:18,
                   10:10, 11:18, 12:27, 13:27, 14:16, 15:20, 16:20}


@dataclass(frozen=True)
class Frame:
    type_id: int
    config_epoch: int
    sequence: int
    tick_ms: int
    payload: bytes


def crc16(data: bytes) -> int:
    """CRC16/CCITT-FALSE, independent of the test's binascii implementation."""
    crc = 0xffff
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xffff
    return crc


def _check_type_length(kind: int, length: int, allow_legacy: bool) -> None:
    if kind not in PAYLOAD_LENGTHS:
        raise ValueError('unknown or unfrozen frame type')
    if kind in (3, 4) and not allow_legacy:
        raise ValueError('legacy type requires explicit diagnostic mode')
    if length != PAYLOAD_LENGTHS[kind] or length > MAX_PAYLOAD:
        raise ValueError('invalid payload length')


def encode(frame: Frame, *, allow_legacy_diagnostic: bool = False) -> bytes:
    for value, limit in ((frame.type_id,255),(frame.config_epoch,255),
                         (frame.sequence,65535),(frame.tick_ms,0xffffffff)):
        if type(value) is not int or not 0 <= value <= limit:
            raise ValueError('wire integer outside unsigned range; wrapping is forbidden')
    if not isinstance(frame.payload, bytes):
        raise ValueError('payload must be immutable bytes')
    _check_type_length(frame.type_id, len(frame.payload), allow_legacy_diagnostic)
    body = HEADER.pack(MAGIC, VERSION, frame.type_id, len(frame.payload),
                       frame.config_epoch, frame.sequence, frame.tick_ms) + frame.payload
    return body + struct.pack('<H', crc16(body[2:]))


def decode(packet: bytes, *, allow_legacy_diagnostic: bool = False) -> Frame:
    if not 14 <= len(packet) <= MAX_FRAME:
        raise ValueError('invalid total length')
    magic, version, kind, size, epoch, sequence, tick = HEADER.unpack_from(packet)
    if magic != MAGIC or version != VERSION:
        raise ValueError('wrong magic or ABI version')
    _check_type_length(kind, size, allow_legacy_diagnostic)
    if len(packet) != 14 + size:
        raise ValueError('truncated packet or trailing bytes')
    if crc16(packet[2:-2]) != struct.unpack_from('<H',packet,len(packet)-2)[0]:
        raise ValueError('CRC mismatch')
    return Frame(kind, epoch, sequence, tick, bytes(packet[HEADER.size:-2]))


class FrameDecoder:
    """Incremental bounded scanner. Each feed is at most 4096 bytes.

    Buffer storage never exceeds one maximum-sized candidate. A bad candidate
    discards one byte and rescans, so a valid embedded magic can be recovered.
    Caller supplies monotonic receive timing separately; header time is not age.
    """
    def __init__(self, *, allow_legacy_diagnostic: bool = False):
        self._buffer = bytearray()
        self.allow_legacy_diagnostic = allow_legacy_diagnostic
        self.rejected_candidates = 0
        self.discarded_bytes = 0

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def feed(self, data: bytes) -> list[Frame]:
        if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_FEED:
            raise ValueError('feed requires at most 4096 bytes')
        frames = []
        for byte in data:
            self._buffer.append(byte)
            while self._buffer:
                start = self._buffer.find(MAGIC)
                if start < 0:
                    keep = int(self._buffer[-1] == MAGIC[0])
                    self.discarded_bytes += len(self._buffer) - keep
                    if keep:
                        self._buffer[:] = MAGIC[:1]
                    else:
                        self._buffer.clear()
                    break
                if start:
                    self.discarded_bytes += start
                    del self._buffer[:start]
                if len(self._buffer) < 5:
                    break
                version, kind, size = self._buffer[2:5]
                try:
                    if version != VERSION:
                        raise ValueError('version')
                    _check_type_length(kind, size, self.allow_legacy_diagnostic)
                except ValueError:
                    self._reject_one()
                    continue
                total = 14 + size
                if len(self._buffer) < total:
                    break
                try:
                    frame = decode(bytes(self._buffer[:total]),
                                   allow_legacy_diagnostic=self.allow_legacy_diagnostic)
                except ValueError:
                    self._reject_one()
                    continue
                del self._buffer[:total]
                frames.append(frame)
        return frames

    def _reject_one(self) -> None:
        self.rejected_candidates += 1
        self.discarded_bytes += 1
        del self._buffer[0]
