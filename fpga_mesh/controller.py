"""Event-driven controller with no idle model polling."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol

from .protocol import Envelope, MessageKind, SourceKind
from .store import SQLiteStore


@dataclass(slots=True)
class ActionResult:
    accepted: bool
    output: dict[str, Any] = field(default_factory=dict)


class ModelGateway(Protocol):
    async def handle(self, message: Envelope) -> ActionResult:
        ...


class Controller:
    """Dispatches only pending messages that require model reasoning."""

    def __init__(
        self, store: SQLiteStore, gateway: ModelGateway,
        on_human_instruction: Callable[[Envelope], None] | None = None,
        on_result: Callable[[Envelope, ActionResult], Any] | None = None,
        claim_ownership: Callable[[Envelope], Any] | None = None,
    ):
        self.store = store
        self.gateway = gateway
        self.on_human_instruction = on_human_instruction
        self.on_result = on_result
        self.claim_ownership = claim_ownership
        self._last_control_at, self._paused_at, self._pause_scope = (
            self.store.load_control_state()
        )
        self.dispatch_blocked = self._paused_at is not None
        self._wakeup = asyncio.Event()
        self._stop = asyncio.Event()
        self._serve_task: asyncio.Task[None] | None = None
        self._active_dispatch: asyncio.Task[ActionResult] | None = None
        self._active_message: Envelope | None = None

    async def offer(self, message: Envelope) -> bool:
        accepted = self.store.accept_inbound(message)
        if not accepted:
            return False
        self._wakeup.set()
        if self._is_expired(message):
            return True
        if (message.source == SourceKind.HUMAN and
                message.kind == MessageKind.HUMAN_INSTRUCTION and
                self.on_human_instruction is not None):
            try:
                self.on_human_instruction(message)
            except Exception as exc:  # noqa: BLE001 - inbox retries version update
                self.store.mark_inbound_failed(
                    message.message_id, f"{type(exc).__name__}: {exc}",
                    retry_at=self._retry_at(0),
                )
                raise
        self._apply_control(message)
        reason = self._preemption_reason(message)
        if reason is not None:
            self._active_dispatch.cancel(reason)
            self.store.append_event(
                f"dispatch-preempt:{self._active_message.message_id}:{message.message_id}",
                "dispatch_preempted",
                {
                    "reason": reason,
                    "active_message_id": self._active_message.message_id,
                    "active_task_id": self._active_message.task_id,
                    "active_task_version": self._active_message.task_version,
                    "trigger_message_id": message.message_id,
                    "trigger_task_version": message.task_version,
                },
            )
        return True

    def _preemption_reason(self, message: Envelope) -> str | None:
        """Human priority orders the next turn; only explicit control supersedes work."""
        if (message.source != SourceKind.HUMAN
                or self._active_dispatch is None
                or self._active_dispatch.done()
                or self._active_message is None):
            return None
        if (message.kind == MessageKind.STOP_REQUEST
                and self.dispatch_blocked
                and self._last_control_at == message.sent_at):
            return "human_stop"
        if (message.kind == MessageKind.HUMAN_INSTRUCTION
                and message.task_id == self._active_message.task_id
                and message.task_version > self._active_message.task_version):
            # The active task has already passed any local ownership gate.
            return "newer_human_task_version"
        return None

    async def run_until_idle(self) -> None:
        observed: set[str] = set()
        while True:
            pending = [
                stored
                for stored in self.store.pending_inbound()
                if stored.message.message_id not in observed
            ]
            if not pending:
                return
            pending.sort(key=lambda item: (
                not self._is_control_message(item.message),
                item.message.source != SourceKind.HUMAN,
                item.message.sent_at,
            ))
            for stored in pending:
                message = stored.message
                observed.add(message.message_id)
                if self._is_expired(message):
                    self.store.mark_inbound_processed(message.message_id)
                    continue
                if self._is_control_message(message):
                    self._apply_control(message)
                    self.store.mark_inbound_processed(message.message_id)
                    continue
                if ((self.store.latest_human_task_version(message.task_id) or 0)
                        > message.task_version):
                    self.store.mark_inbound_processed(message.message_id)
                    continue
                if (message.source == SourceKind.HUMAN and
                        message.kind == MessageKind.HUMAN_INSTRUCTION and
                        self.on_human_instruction is not None):
                    try:
                        # Reapplying is safe and recovers a crash after inbox
                        # persistence but before the child-version write.
                        self.on_human_instruction(message)
                    except Exception as exc:  # noqa: BLE001 - keep inbox pending
                        self.store.mark_inbound_failed(
                            message.message_id,
                            f"{type(exc).__name__}: {exc}",
                            retry_at=self._retry_at(stored.attempts),
                        )
                        continue
                if self.dispatch_blocked:
                    continue
                if (message.source == SourceKind.HUMAN
                        and message.kind == MessageKind.HUMAN_INSTRUCTION
                        and message.payload.get("ownership_required")):
                    try:
                        owner = (self.claim_ownership(message)
                                 if self.claim_ownership is not None else None)
                        owner = await owner if inspect.isawaitable(owner) else owner
                    except Exception as exc:  # noqa: BLE001 - wait for coordination recovery
                        self.store.mark_inbound_failed(
                            message.message_id,
                            f"ownership: {type(exc).__name__}: {exc}",
                            retry_at=self._retry_at(stored.attempts),
                        )
                        continue
                    if owner is False:
                        self.store.mark_inbound_processed(message.message_id)
                        continue
                    if owner is not True:
                        self.store.mark_inbound_failed(
                            message.message_id, "ownership not confirmed",
                            retry_at=self._retry_at(stored.attempts),
                        )
                        continue
                    if self.dispatch_blocked or (
                        (self.store.latest_human_task_version(message.task_id) or 0)
                        > message.task_version
                    ):
                        continue
                try:
                    self._active_message = message
                    self._active_dispatch = asyncio.create_task(
                        self.gateway.handle(message),
                        name=f"fpga-dispatch-{message.message_id}",
                    )
                    result = await self._active_dispatch
                    if self.on_result is not None:
                        callback_result = self.on_result(message, result)
                        if inspect.isawaitable(callback_result):
                            await callback_result
                except asyncio.CancelledError:
                    if asyncio.current_task().cancelling():
                        raise
                    # Preserve interrupted work for the gateway's recovery audit;
                    # never turn an explicit stop into a blind side-effect replay.
                    break
                except Exception as exc:  # noqa: BLE001 - persisted as recovery state
                    self.store.mark_inbound_failed(
                        message.message_id,
                        f"{type(exc).__name__}: {exc}",
                        retry_at=self._retry_at(stored.attempts),
                    )
                    break
                finally:
                    self._active_dispatch = None
                    self._active_message = None
                self.store.mark_inbound_processed(message.message_id)
                # Re-read priorities at the turn boundary. A human followup may
                # have arrived while this old snapshot still contained peers.
                break

    async def wait_for_work(self, timeout: float | None = None) -> bool:
        if self.store.pending_inbound():
            return True
        self._wakeup.clear()
        try:
            await asyncio.wait_for(self._wakeup.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return False
        return True

    async def serve(self) -> None:
        self._stop.clear()
        while not self._stop.is_set():
            await self.run_until_idle()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    async def start(self) -> None:
        if self._serve_task is not None and not self._serve_task.done():
            return
        self._serve_task = asyncio.create_task(self.serve(), name="fpga-mesh-controller")

    async def stop(self) -> None:
        self._stop.set()
        self._wakeup.set()
        if self._serve_task is not None:
            self._serve_task.cancel()
            try:
                await self._serve_task
            except asyncio.CancelledError:
                pass
            self._serve_task = None

    def _is_expired(self, message: Envelope) -> bool:
        return message.expires_at is not None and message.expires_at <= datetime.now(
            timezone.utc
        )

    def _is_control_message(self, message: Envelope) -> bool:
        return (
            message.kind in {MessageKind.STOP_REQUEST, MessageKind.RESUME_REQUEST}
            and message.source == SourceKind.HUMAN
        )

    def _apply_control(self, message: Envelope) -> None:
        if message.source != SourceKind.HUMAN:
            return
        if self._last_control_at is not None:
            if message.sent_at < self._last_control_at:
                return
            if (message.sent_at == self._last_control_at
                    and message.kind != MessageKind.STOP_REQUEST):
                return
        if message.kind == MessageKind.STOP_REQUEST:
            self.dispatch_blocked = True
            self._paused_at = message.sent_at
            self._pause_scope = str(message.payload.get("scope", "all"))
        elif message.kind == MessageKind.RESUME_REQUEST:
            resume_scope = str(message.payload.get("scope", "all"))
            time_is_later = (
                self._paused_at is not None
                and message.sent_at > self._paused_at
            )
            scope_matches = (
                self._pause_scope in {None, "all", resume_scope}
                or resume_scope == "all"
            )
            if time_is_later and scope_matches:
                self.dispatch_blocked = False
                self._paused_at = None
                self._pause_scope = None
        else:
            return
        self._last_control_at = message.sent_at
        self.store.save_control_state(
            self._last_control_at, self._paused_at, self._pause_scope,
        )

    @staticmethod
    def _retry_at(attempts: int) -> datetime:
        seconds = min(3600, 30 * 2 ** min(attempts, 7))
        return datetime.now(timezone.utc) + timedelta(seconds=seconds)
