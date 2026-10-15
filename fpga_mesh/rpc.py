"""Minimal asynchronous JSON-RPC 2.0 transport used by Codex app-server."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Protocol


class JsonRpcError(RuntimeError):
    def __init__(self, method: str, error: dict[str, Any]):
        self.method = method
        self.code = error.get("code")
        self.message = error.get("message", "JSON-RPC error")
        self.data = error.get("data")
        self.codex_error_info = error.get("codex_error_info", error.get("codexErrorInfo"))
        super().__init__(f"{method}: [{self.code}] {self.message}")


class RequestNotSentError(ConnectionError):
    """The request was rejected locally before any transport write occurred."""


@dataclass(frozen=True, slots=True)
class JsonRpcNotification:
    method: str
    params: dict[str, Any]
    request_id: int | str | None = None


class Transport(Protocol):
    async def send(self, payload: str) -> None:
        ...

    async def recv(self) -> str:
        ...

    async def close(self) -> None:
        ...


class InMemoryTransport:
    """Test transport with explicit client/server queue helpers."""

    def __init__(self) -> None:
        self._client_writes: asyncio.Queue[str] = asyncio.Queue()
        self._server_writes: asyncio.Queue[str] = asyncio.Queue()
        self.closed = False

    async def send(self, payload: str) -> None:
        await self._client_writes.put(payload)

    async def recv(self) -> str:
        return await self._server_writes.get()

    async def close(self) -> None:
        self.closed = True

    async def next_client_message(self) -> str:
        return await self._client_writes.get()

    async def inject_server_message(self, payload: str) -> None:
        await self._server_writes.put(payload)


class JsonRpcSession:
    """Route responses and notifications without coupling to Codex methods."""

    def __init__(self, transport: Transport):
        self.transport = transport
        self._next_id = 1
        self._pending: dict[int | str, tuple[str, asyncio.Future[Any]]] = {}
        self._notifications: asyncio.Queue[JsonRpcNotification] = asyncio.Queue()
        self._closed = False
        self._reader = asyncio.create_task(self._read_loop())

    @property
    def is_alive(self) -> bool:
        return not self._closed and self._reader is not None and not self._reader.done()

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if not self.is_alive:
            raise RequestNotSentError(f"{method}: Codex connection is closed; request not sent")
        request_id = self._next_id
        self._next_id += 1
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = (method, future)
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        try:
            await self.transport.send(json.dumps(payload, ensure_ascii=False))
            return await future
        finally:
            self._pending.pop(request_id, None)
            if not future.done():
                future.cancel()

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        await self.transport.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params or {},
                },
                ensure_ascii=False,
            )
        )

    async def respond(self, request_id: int | str, result: Any) -> None:
        await self.transport.send(json.dumps({
            "jsonrpc": "2.0", "id": request_id, "result": result,
        }, ensure_ascii=False))

    async def reject(self, request_id: int | str, *, code: int = -32601,
                     message: str = "Unsupported server request") -> None:
        await self.transport.send(json.dumps({
            "jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message},
        }, ensure_ascii=False))

    async def next_notification(self) -> JsonRpcNotification:
        return await self._notifications.get()

    async def close(self) -> None:
        self._closed = True
        for _, future in self._pending.values():
            future.cancel()
        self._pending.clear()
        if self._reader is not None:
            self._reader.cancel()
            try:
                await self._reader
            except asyncio.CancelledError:
                pass
            self._reader = None
        await self.transport.close()

    async def _read_loop(self) -> None:
        failure: Exception = ConnectionError("Codex app-server closed the connection")
        try:
            while True:
                payload = await self.transport.recv()
                if not payload:
                    break
                data = json.loads(payload)
                if "id" in data and "method" not in data:
                    request_id = data["id"]
                    entry = self._pending.pop(request_id, None)
                    if entry is None:
                        continue
                    method, future = entry
                    if future.done():
                        continue
                    if "error" in data:
                        future.set_exception(JsonRpcError(method, data["error"]))
                    else:
                        future.set_result(data.get("result"))
                elif "method" in data:
                    await self._notifications.put(
                        JsonRpcNotification(
                            method=data["method"],
                            params=data.get("params") or {},
                            request_id=data.get("id"),
                        )
                    )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface transport failure
            failure = ConnectionError(f"Codex app-server read failed: {exc}")
        finally:
            if not self._closed:
                for _, future in self._pending.values():
                    if not future.done():
                        future.set_exception(failure)
                self._pending.clear()
                self._notifications.put_nowait(JsonRpcNotification(
                    method="error", params={"message": str(failure)},
                ))


class StdioTransport:
    """Async subprocess transport for `codex app-server --stdio`."""

    def __init__(self, command: list[str], *, env: dict[str, str] | None = None):
        self.command = command
        self.env = env
        self.process: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env,
            # Codex tool/thread frames include loaded instructions and may
            # exceed asyncio's 64 KiB default even for a small assignment.
            limit=16 * 1024 * 1024,
        )
        if self.process.stderr is not None:
            self._stderr_task = asyncio.create_task(
                self._drain_stderr(self.process.stderr),
            )

    @staticmethod
    async def _drain_stderr(stream: asyncio.StreamReader) -> None:
        while await stream.read(65536):
            pass

    async def send(self, payload: str) -> None:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("transport is not started")
        async with self._lock:
            self.process.stdin.write((payload + "\n").encode("utf-8"))
            await self.process.stdin.drain()

    async def recv(self) -> str:
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("transport is not started")
        data = await self.process.stdout.readline()
        return data.decode("utf-8").rstrip("\r\n")

    async def close(self) -> None:
        if self.process is None:
            return
        if self.process.stdin is not None:
            self.process.stdin.close()
        if self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        if self._stderr_task is not None:
            await self._stderr_task
            self._stderr_task = None
        self.process = None
