"""Bounded binary-frame transports for simulation and the explicit COM port.

The simulator path launches only the executable named by ``--sim-exe``.  The
serial path imports pyserial only after all hardware gates have passed and it
opens exactly the one COM port supplied by the operator.  No code here scans,
guesses, or probes ports.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Empty, Full, Queue
from typing import Any

from .codec import FRAME_SIZE


BAUD_RATE = 115200
_PORT_PATTERN = re.compile(r"COM(?:[1-9][0-9]{0,3})")
_INBOX_LIMIT = 64
_MAX_HARDWARE_PROFILE_BYTES = 64 * 1024


class TransportError(RuntimeError):
    """The configured simulation or serial transport cannot continue."""


class HardwareProfileError(ValueError):
    """The hardware confirmation profile is absent, invalid, or not explicit."""


class _Failure:
    __slots__ = ("message",)

    def __init__(self, message: str) -> None:
        self.message = message


_CLOSED = object()


class _FrameInbox:
    def __init__(self) -> None:
        self._queue: Queue[bytes | _Failure | object] = Queue(maxsize=_INBOX_LIMIT)
        self._closed = threading.Event()
        self._terminal_error: str | None = None
        self._terminal_lock = threading.Lock()

    def put_frame(self, frame: bytes) -> None:
        self._put(frame)

    def put_failure(self, message: str) -> None:
        with self._terminal_lock:
            if self._terminal_error is None:
                self._terminal_error = message
        self._put(_Failure(message))

    def _put(self, item: bytes | _Failure | object) -> None:
        while not self._closed.is_set():
            try:
                self._queue.put(item, timeout=0.25)
                return
            except Full:
                continue

    def read(self, timeout: float) -> bytes | None:
        with self._terminal_lock:
            terminal = self._terminal_error
        if terminal is not None and self._queue.empty():
            raise TransportError(terminal)
        try:
            item = self._queue.get(timeout=max(0.0, timeout))
        except Empty:
            return None
        if item is _CLOSED:
            return None
        if isinstance(item, _Failure):
            raise TransportError(item.message)
        if not isinstance(item, bytes):
            raise TransportError("internal frame queue corruption")
        return item

    def close(self) -> None:
        self._closed.set()
        try:
            self._queue.put_nowait(_CLOSED)
        except Full:
            pass


class _BaseTransport:
    mode = "unknown"
    simulation = False
    hardware_confirmed = False

    def __init__(self) -> None:
        self._inbox = _FrameInbox()
        self._closing = threading.Event()
        self._reader: threading.Thread | None = None
        self._opened = False
        self._write_lock = threading.Lock()

    def description(self) -> dict[str, Any]:
        return {
            "transport": self.mode,
            "simulation": self.simulation,
            "hardware_confirmed": self.hardware_confirmed,
        }

    def _start_reader(self, target: Any) -> None:
        self._reader = threading.Thread(
            target=target,
            name=f"{self.mode}-frame-reader",
            daemon=True,
        )
        self._reader.start()

    def _join_reader(self) -> None:
        reader = self._reader
        if reader is not None and reader is not threading.current_thread():
            reader.join(timeout=1.0)

    def read_frame(self, timeout: float) -> bytes | None:
        if not self._opened:
            raise TransportError("transport is not open")
        return self._inbox.read(timeout)

    def write_frame(self, frame: bytes) -> None:
        raise NotImplementedError

    def open(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class SimulatorTransport(_BaseTransport):
    """Child-process transport whose stdin/stdout carry raw 32-byte frames."""

    mode = "simulation"
    simulation = True
    hardware_confirmed = False

    def __init__(self, executable: str | Path) -> None:
        super().__init__()
        self.executable = Path(executable).expanduser()
        if not self.executable.is_file():
            raise TransportError(f"simulator executable is not a file: {self.executable}")
        if self.executable.suffix.lower() == ".py":
            self._argv = [sys.executable, "-B", str(self.executable)]
        else:
            self._argv = [str(self.executable)]
        self._process: subprocess.Popen[bytes] | None = None

    def description(self) -> dict[str, Any]:
        record = super().description()
        record["sim_exe"] = str(self.executable)
        return record

    def open(self) -> None:
        if self._opened:
            raise TransportError("simulator transport is already open")
        try:
            self._process = subprocess.Popen(
                self._argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=None,
                bufsize=0,
            )
        except OSError as exc:
            raise TransportError(f"cannot start simulator: {exc}") from exc
        self._opened = True
        self._start_reader(self._read_loop)

    def _read_exact_frame(self) -> bytes | None:
        assert self._process is not None and self._process.stdout is not None
        data = bytearray()
        while len(data) < FRAME_SIZE:
            chunk = self._process.stdout.read(FRAME_SIZE - len(data))
            if not chunk:
                if data:
                    raise TransportError("simulator sent a truncated 32-byte frame")
                return None
            data.extend(chunk)
        return bytes(data)

    def _read_loop(self) -> None:
        try:
            while not self._closing.is_set():
                frame = self._read_exact_frame()
                if frame is None:
                    if not self._closing.is_set():
                        self._inbox.put_failure("simulator closed its output stream")
                    return
                self._inbox.put_frame(frame)
        except Exception as exc:
            if not self._closing.is_set():
                self._inbox.put_failure(f"simulator read failed: {exc}")

    def write_frame(self, frame: bytes) -> None:
        if not self._opened or self._process is None or self._process.stdin is None:
            raise TransportError("simulator transport is not open")
        if len(frame) != FRAME_SIZE:
            raise TransportError(f"frame must be exactly {FRAME_SIZE} bytes")
        try:
            with self._write_lock:
                view = memoryview(frame)
                while view:
                    written = self._process.stdin.write(view)
                    if not written:
                        raise TransportError("simulator stdin accepted no bytes")
                    view = view[written:]
                self._process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise TransportError(f"simulator write failed: {exc}") from exc

    def close(self) -> None:
        if self._closing.is_set():
            return
        self._closing.set()
        process = self._process
        if process is not None:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    try:
                        process.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        pass
        self._inbox.close()
        self._join_reader()
        if process is not None and process.stdout is not None:
            reader = self._reader
            if reader is None or not reader.is_alive():
                try:
                    process.stdout.close()
                except (OSError, ValueError):
                    pass
        self._opened = False


class SerialTransport(_BaseTransport):
    """Explicit-port pyserial transport; pyserial is imported only on open."""

    mode = "serial"
    simulation = False
    hardware_confirmed = False

    def __init__(self, port: str, *, hardware_confirmed: bool = False) -> None:
        super().__init__()
        validate_port_name(port)
        if hardware_confirmed is not True:
            raise TransportError("serial transport requires hardware_confirmed=true")
        self.port = port
        self.hardware_confirmed = True
        self._serial: Any = None

    def description(self) -> dict[str, Any]:
        record = super().description()
        record["port"] = self.port
        record["baudrate"] = BAUD_RATE
        return record

    def open(self) -> None:
        if self._opened:
            raise TransportError("serial transport is already open")
        try:
            import serial as pyserial
        except ImportError as exc:
            raise TransportError(
                "pyserial is required for --port; install pc/requirements.txt"
            ) from exc
        try:
            self._serial = pyserial.Serial(
                port=self.port,
                baudrate=BAUD_RATE,
                bytesize=pyserial.EIGHTBITS,
                parity=pyserial.PARITY_NONE,
                stopbits=pyserial.STOPBITS_ONE,
                timeout=0.1,
                write_timeout=0.5,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False,
            )
        except Exception as exc:
            raise TransportError(f"cannot open explicit port {self.port}: {exc}") from exc
        self._opened = True
        self._start_reader(self._read_loop)

    def _read_loop(self) -> None:
        buffer = bytearray()
        last_byte_at = 0.0
        try:
            while not self._closing.is_set():
                chunk = self._serial.read(FRAME_SIZE - len(buffer))
                if chunk:
                    buffer.extend(chunk)
                    last_byte_at = time.monotonic()
                    if len(buffer) == FRAME_SIZE:
                        self._inbox.put_frame(bytes(buffer))
                        buffer.clear()
                        last_byte_at = 0.0
                    continue
                if buffer and last_byte_at and (time.monotonic() - last_byte_at) > 1.0:
                    raise TransportError("serial port left a partial 32-byte frame")
        except Exception as exc:
            if not self._closing.is_set():
                self._inbox.put_failure(f"serial read failed: {exc}")

    def write_frame(self, frame: bytes) -> None:
        if not self._opened or self._serial is None:
            raise TransportError("serial transport is not open")
        if len(frame) != FRAME_SIZE:
            raise TransportError(f"frame must be exactly {FRAME_SIZE} bytes")
        try:
            with self._write_lock:
                written = self._serial.write(frame)
                if written != len(frame):
                    raise TransportError("serial port accepted only part of a frame")
                self._serial.flush()
        except TransportError:
            raise
        except Exception as exc:
            raise TransportError(f"serial write failed: {exc}") from exc

    def close(self) -> None:
        if self._closing.is_set():
            return
        self._closing.set()
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:
                pass
        self._inbox.close()
        self._join_reader()
        self._opened = False


def validate_port_name(port: str) -> str:
    if not isinstance(port, str) or not _PORT_PATTERN.fullmatch(port):
        raise TransportError("port must be an explicit COMn name, for example COM3")
    return port


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise HardwareProfileError(f"duplicate hardware profile key: {key}")
        result[key] = value
    return result


def _reject_profile_constant(token: str) -> None:
    raise HardwareProfileError(f"non-finite profile value: {token}")


def load_hardware_profile(path: str | Path) -> dict[str, Any]:
    """Load the explicit hardware gate; extra/unknown keys are rejected."""

    profile_path = Path(path).expanduser()
    if not profile_path.is_file():
        raise HardwareProfileError(f"hardware profile is not a file: {profile_path}")
    try:
        raw = profile_path.read_bytes()
    except OSError as exc:
        raise HardwareProfileError(f"cannot read hardware profile: {exc}") from exc
    if len(raw) > _MAX_HARDWARE_PROFILE_BYTES:
        raise HardwareProfileError("hardware profile is larger than 64 KiB")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_profile_constant,
        )
    except HardwareProfileError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HardwareProfileError("hardware profile must be one UTF-8 JSON object") from exc
    if not isinstance(value, dict):
        raise HardwareProfileError("hardware profile must be a JSON object")
    unknown = set(value) - {"hardware_confirmed"}
    if unknown:
        raise HardwareProfileError(
            "unknown hardware profile key(s): " + ", ".join(sorted(unknown))
        )
    if value.get("hardware_confirmed") is not True:
        raise HardwareProfileError("hardware_confirmed must be the JSON boolean true")
    return value


__all__ = [
    "BAUD_RATE",
    "HardwareProfileError",
    "SerialTransport",
    "SimulatorTransport",
    "TransportError",
    "load_hardware_profile",
    "validate_port_name",
]
