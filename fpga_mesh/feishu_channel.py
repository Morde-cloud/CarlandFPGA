"""Real Feishu group ingress for one Astra role.

Only the local Astra app opens a long connection. DeepSeek identities are
outbound-only and are never subscribed to group events by this module.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .protocol import Envelope, MessageKind, SourceKind, task_id_from_message


def _message_uuid(app_id: str, operation_id: str) -> str:
    """A stable, bounded idempotency key accepted by Feishu send APIs."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{app_id}:{operation_id}"))


def _load_default_channel_factory(group_id: str) -> Callable[..., Any]:
    # The SDK captures its WS event loop at import time. Load it on a worker
    # without a running controller loop so SDK shutdown cannot stop our loop.
    try:
        from lark_channel import FeishuChannel, PolicyConfig, SecurityConfig
    except ImportError as exc:
        raise RuntimeError(
            "Feishu requires lark-channel-sdk; install the feishu extra"
        ) from exc
    return lambda **kwargs: FeishuChannel(
        **kwargs,
        policy=PolicyConfig(
            dm_policy="disabled", group_policy="allowlist",
            group_allowlist=[group_id], require_mention=False,
        ),
        security=SecurityConfig(mode="strict"),
    )


class FeishuIngress:
    def __init__(
        self, *, node_id: str, project_id: str, group_id: str,
        app_id: str, controller: Any,
        local_bot_open_ids: set[str] | None = None,
        allowed_sender_ids: set[str] | None = None,
    ) -> None:
        if node_id not in {"A", "B", "C"}:
            raise ValueError("node_id must be A, B, or C")
        if not group_id.startswith("oc_"):
            raise ValueError("Feishu group_id must begin with oc_")
        self.node_id = node_id
        self.project_id = project_id
        self.group_id = group_id
        self.app_id = app_id
        self.controller = controller
        self.local_bot_open_ids = set(local_bot_open_ids or ())
        self.allowed_sender_ids = (
            set(allowed_sender_ids) if allowed_sender_ids is not None else None
        )
        self._highest_revision: dict[str, int] = {}

    async def ingest(self, msg: Any) -> bool:
        if getattr(msg, "chat_id", None) != self.group_id:
            return False
        if getattr(msg, "chat_type", None) not in {"group", "topic"}:
            return False
        if getattr(msg, "sender_type", None) != "user":
            return False
        sender_id = getattr(msg, "sender_id", "")
        if not sender_id or (
            self.allowed_sender_ids is not None
            and sender_id not in self.allowed_sender_ids
        ):
            return False
        # Every human instruction in the designated group reaches Astra.  A
        # mention of another bot does not lower its priority or wake a child.
        text = str(getattr(msg, "body_text", "") or "").strip()
        if not text:
            return False
        platform_message_id = str(getattr(msg, "message_id", "") or "")
        if not platform_message_id:
            return False
        raw = getattr(msg, "raw", None)
        raw = raw if isinstance(raw, dict) else {}
        created_ms = int(getattr(msg, "create_time", 0) or 0)
        revision = max(1, int(raw.get("update_time") or created_ms or 1))
        if revision <= self._highest_revision.get(platform_message_id, 0):
            return False
        command = text.casefold()
        kind = {
            "/fpga pause": MessageKind.STOP_REQUEST,
            "/fpga resume": MessageKind.RESUME_REQUEST,
        }.get(command, MessageKind.HUMAN_INSTRUCTION)
        target_node: str | None = None
        if kind == MessageKind.HUMAN_INSTRUCTION:
            addressed = re.match(
                r"^(?:/fpga\s+([abc])\b|astra-([abc])\s*[:：])",
                text, re.IGNORECASE,
            )
            if addressed:
                target_node = (addressed.group(1) or addressed.group(2)).upper()
            else:
                named = {
                    match.group(1).upper()
                    for mention in getattr(msg, "mentions", ())
                    if getattr(mention, "is_bot", False)
                    for match in [re.fullmatch(
                        r"FPGA\s+(?:Astra|DeepSeek)\s+([ABC])",
                        str(getattr(mention, "name", "") or ""), re.IGNORECASE,
                    )]
                    if match is not None
                }
                if len(named) == 1:
                    target_node = next(iter(named))
                elif getattr(msg, "mentioned_bot", False) or any(
                    getattr(mention, "open_id", None) in self.local_bot_open_ids
                    for mention in getattr(msg, "mentions", ())
                ):
                    target_node = self.node_id
            if target_node is not None and target_node != self.node_id:
                return False
        envelope = Envelope(
            message_id=f"feishu:{self.group_id}:{platform_message_id}:{revision}",
            project_id=self.project_id,
            sender=sender_id,
            recipient=f"{self.node_id}/Astra-{self.node_id}",
            task_id=task_id_from_message(self.group_id, platform_message_id),
            task_version=revision,
            sent_at=datetime.fromtimestamp(
                created_ms / 1000, timezone.utc,
            ) if created_ms else datetime.now(timezone.utc),
            kind=kind,
            source=SourceKind.HUMAN,
            payload={
                "text": text, "scope": "all",
                "ownership_required": (
                    kind == MessageKind.HUMAN_INSTRUCTION
                    and target_node is None
                ),
            },
            revision=revision,
            platform_group_id=self.group_id,
            platform_message_id=platform_message_id,
            platform_event_id=str(raw.get("event_id") or "") or None,
        )
        accepted = await self.controller.offer(envelope)
        if accepted:
            self._highest_revision[platform_message_id] = revision
        return accepted


class FeishuAppSender:
    """Send with the DeepSeek app's identity without opening an event stream."""

    def __init__(
        self, *, app_id: str, secret_file: Path,
        client_factory: Callable[[str, str], Any] | None = None,
    ) -> None:
        self.app_id = app_id
        self.secret_file = Path(secret_file)
        self.client_factory = client_factory
        self._client: Any | None = None

    async def send(self, group_id: str, text: str, operation_id: str) -> str:
        return await asyncio.to_thread(
            self._send_sync, group_id, text, operation_id,
        )

    def _send_sync(self, group_id: str, text: str, operation_id: str) -> str:
        if not group_id.startswith("oc_") or not text.strip() or not operation_id:
            raise ValueError("invalid Feishu group send request")
        try:
            from lark_channel import Client
            from lark_channel.api.im.v1.model.create_message_request import (
                CreateMessageRequest,
            )
            from lark_channel.api.im.v1.model.create_message_request_body import (
                CreateMessageRequestBody,
            )
        except ImportError as exc:
            raise RuntimeError("DeepSeek Feishu sender requires lark-channel-sdk") from exc
        if self._client is None:
            secret = self.secret_file.read_text(encoding="utf-8-sig").strip()
            if not secret:
                raise ValueError("DeepSeek Feishu app secret file is empty")
            self._client = (
                self.client_factory(self.app_id, secret)
                if self.client_factory is not None else
                Client.builder().app_id(self.app_id).app_secret(secret).build()
            )
        request = CreateMessageRequest.builder().receive_id_type("chat_id").request_body(
            CreateMessageRequestBody.builder()
            .receive_id(group_id)
            .msg_type("text")
            .content(json.dumps({"text": text}, ensure_ascii=False))
            .uuid(_message_uuid(self.app_id, operation_id))
            .build()
        ).build()
        response = self._client.im.v1.message.create(request)
        if not response.success():
            raise RuntimeError(f"Feishu DeepSeek send failed: {response.code}")
        return str(response.data.message_id)


class FeishuNodeService:
    """Connect the node's Astra app and send group reports as that app."""

    def __init__(
        self, *, node_id: str, project_id: str, group_id: str,
        astra_app_id: str, astra_secret_file: Path, controller: Any,
        local_bot_open_ids: set[str] | None = None,
        allowed_sender_ids: set[str] | None = None,
        channel_factory: Callable[..., Any] | None = None,
        store: Any | None = None,
        retry_seconds: float = 30.0,
        deepseek_app_id: str = "",
        deepseek_secret_file: Path | None = None,
        deepseek_sender: Any | None = None,
        job_lookup: Callable[[str], dict] | None = None,
    ) -> None:
        self.group_id = group_id
        self.astra_app_id = astra_app_id
        self.astra_secret_file = Path(astra_secret_file)
        self.ingress = FeishuIngress(
            node_id=node_id, project_id=project_id, group_id=group_id,
            app_id=astra_app_id, controller=controller,
            local_bot_open_ids=local_bot_open_ids,
            allowed_sender_ids=allowed_sender_ids,
        )
        self.channel_factory = channel_factory
        self.store = store
        self.job_lookup = job_lookup
        self.deepseek_sender = deepseek_sender or (
            FeishuAppSender(
                app_id=deepseek_app_id, secret_file=deepseek_secret_file,
            ) if deepseek_app_id and deepseek_secret_file else None
        )
        if retry_seconds <= 0:
            raise ValueError("retry_seconds must be positive")
        self.retry_seconds = retry_seconds
        self.channel: Any | None = None
        self.connected = False
        self.last_error: str | None = None
        self._flush_lock = asyncio.Lock()
        self._outbox_event = asyncio.Event()
        self._outbox_task: asyncio.Task | None = None

    async def start(self) -> None:
        if self.connected:
            return
        secret = self.astra_secret_file.read_text(encoding="utf-8-sig").strip()
        if not secret:
            raise ValueError("Astra Feishu app secret file is empty")
        if self.channel_factory is None:
            self.channel_factory = await asyncio.to_thread(
                _load_default_channel_factory, self.group_id,
            )
        channel = self.channel_factory(app_id=self.astra_app_id, app_secret=secret)
        controller_loop = asyncio.get_running_loop()

        async def deliver_message(msg: Any) -> bool:
            # The SDK dispatches WS events from its own event-loop thread.
            # Controller, child coordinator and SQLite state belong to the
            # runtime loop and must never be called on that SDK thread.
            if asyncio.get_running_loop() is controller_loop:
                return await self.ingress.ingest(msg)
            if not controller_loop.is_running():
                return False
            delivery = asyncio.run_coroutine_threadsafe(
                self.ingress.ingest(msg), controller_loop,
            )
            return await asyncio.wrap_future(delivery)

        channel.on("message", deliver_message)
        await channel.connect_until_ready(timeout=30)
        self.channel = channel
        self.connected = True
        if self.store is not None:
            self._outbox_task = asyncio.create_task(self._run_outbox())
            self._outbox_event.set()

    async def stop(self) -> None:
        if self._outbox_task is not None:
            self._outbox_task.cancel()
            try:
                await self._outbox_task
            except asyncio.CancelledError:
                pass
            self._outbox_task = None
        channel = self.channel
        self.channel = None
        self.connected = False
        if channel is not None:
            await channel.disconnect()

    async def send_as_astra(self, text: str, *, operation_id: str) -> str:
        if not self.connected or self.channel is None:
            raise RuntimeError("Feishu Astra channel is not connected")
        if not text.strip():
            raise ValueError("group message must not be empty")
        result = await self.channel.send(
            self.group_id, {"text": text},
            {"uuid": _message_uuid(self.astra_app_id, operation_id)},
        )
        if not result.success:
            raise RuntimeError("Feishu message send failed")
        return str(result.message_id or "")

    async def flush_reports(self) -> None:
        if self.store is None or not self.connected:
            return
        async with self._flush_lock:
            first_error: Exception | None = None
            for operation_id, text, role in self.store.pending_group_messages():
                try:
                    job_id = self.store.group_report_job(operation_id)
                    if job_id:
                        if self.job_lookup is None:
                            raise RuntimeError("child job lookup is not configured")
                        job = self.job_lookup(job_id)
                        if job["stale"] or job["status"] != "completed":
                            self.store.cancel_group_report(operation_id)
                            continue
                    if role == "deepseek":
                        if self.deepseek_sender is None:
                            raise RuntimeError("DeepSeek Feishu sender is not configured")
                        sent_id = await self.deepseek_sender.send(
                            self.group_id, text, operation_id,
                        )
                    else:
                        sent_id = await self.send_as_astra(
                            text, operation_id=operation_id,
                        )
                    self.store.ack_group_report(operation_id, sent_id)
                except Exception as exc:  # noqa: BLE001 - retain failed item
                    if first_error is None:
                        first_error = exc
            if first_error is not None:
                raise first_error

    def notify_report(self) -> None:
        self._outbox_event.set()

    async def _run_outbox(self) -> None:
        while self.connected:
            self._outbox_event.clear()
            try:
                await self.flush_reports()
                self.last_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - retain pending reports
                self.last_error = type(exc).__name__
            try:
                await asyncio.wait_for(
                    self._outbox_event.wait(), timeout=self.retry_seconds,
                )
            except asyncio.TimeoutError:
                pass
