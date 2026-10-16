"""Codex app-server gateways used only after an actionable event arrives."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal

from .app_server import AppServerClient, RuntimeIntegrityError
from .codex import RouteGuard
from .controller import ActionResult
from .effort import EFFORTS, AstraEffortSelector
from .notifications import notification_matches_turn, terminal_error_message
from .protocol import Envelope
from .rpc import JsonRpcError, RequestNotSentError
from .sessions import ExternalDeliveryPending, ExternalOwnerRequired


LOG = logging.getLogger(__name__)


class GatewayNotStartedError(RuntimeError):
    """A rejected/unsent work request can wait without replaying side effects."""

    safe_to_retry = True
    retry_after_seconds = 30.0

    def __init__(self, reason: str, detail: str):
        self.reason = reason
        super().__init__(f"{reason}: work turn was not started; {detail}")


class GatewayTurnFailure(RuntimeError):
    """A started turn failed: backend cooldown is not permission to replay it."""

    safe_to_retry = False
    retry_after_seconds = 30.0

    def __init__(self, detail: str, *, reason: str = 'turn_failed'):
        self.reason = reason
        super().__init__(detail)


def _is_capacity_error(error) -> bool:
    if isinstance(error, JsonRpcError):
        return (_is_capacity_error(getattr(error, 'codex_error_info', None)) or
                _is_capacity_error(getattr(error, 'data', None)) or
                _is_capacity_error(error.message))
    if isinstance(error, dict):
        info = error.get('codexErrorInfo') or error.get('codex_error_info')
        return info in ('server_overloaded', 'serverOverloaded') or _is_capacity_error(error.get('message'))
    if isinstance(error, str):
        return error.strip().lower().rstrip('.') in {
            'server_overloaded', 'serveroverloaded', 'selected model is at capacity',
            'selected model is at capacity. please try a different model',
        }
    return False


def _capacity_rejection(error: Exception) -> bool:
    # A JSON-RPC error response to turn/start rejects the request. Do not use
    # this rule for a lost response or an error notification after turn start.
    return (isinstance(error, JsonRpcError) and error.method == "turn/start" and
            _is_capacity_error(error))


def _turn_failure(detail: str, error) -> GatewayTurnFailure:
    if _is_capacity_error(error):
        return GatewayTurnFailure(
            "server_overloaded (model capacity, not account quota); "
            f"reconcile the started turn before continuation: {detail}",
            reason='server_overloaded',
        )
    return GatewayTurnFailure(detail)


def _failure_detail(error: Exception) -> str:
    return str(error) or type(error).__name__


@dataclass(frozen=True, slots=True)
class GatewayConfig:
    node_id: str
    role: Literal["astra", "deepseek_child"]
    model: str
    provider: str
    reasoning_effort: str
    cwd: str
    codex_home: str
    client_version: str = "0.159.0"


class AppServerGateway:
    def __init__(
        self,
        config: GatewayConfig,
        *,
        client_factory: Callable[[], AppServerClient | Awaitable[AppServerClient]]
        | None = None,
        thread_config_factory: Callable[[], dict] | None = None,
        dynamic_tools: list[dict] | None = None,
        developer_instructions: str | None = None,
        dynamic_tool_handler: Callable[
            [str, dict], dict | Awaitable[dict]
        ] | None = None,
        effort_selector: AstraEffortSelector | None = None,
        session_router=None,
        timeout_seconds: float | None = 300.0,
        startup_timeout_seconds: float = 60.0,
        startup_retry_delays: tuple[float, ...] = (1.0, 3.0),
    ):
        self.config = config
        self.client_factory = client_factory
        self.thread_config_factory = thread_config_factory
        self.dynamic_tools = dynamic_tools
        self.developer_instructions = developer_instructions
        self.dynamic_tool_handler = dynamic_tool_handler
        self.effort_selector = effort_selector
        self.session_router = session_router
        self.timeout_seconds = timeout_seconds
        if startup_timeout_seconds <= 0 or any(d < 0 for d in startup_retry_delays):
            raise ValueError("startup timeout must be positive and retry delays nonnegative")
        self.startup_timeout_seconds = startup_timeout_seconds
        self.startup_retry_delays = startup_retry_delays
        self._client: AppServerClient | None = None
        self._thread_id: str | None = None
        self._lock = asyncio.Lock()
        self._client_lock = asyncio.Lock()
        self._guard = RouteGuard()
        if config.role == "deepseek_child":
            self._guard.assert_child_request(
                model=config.model,
                provider=config.provider,
                effort=config.reasoning_effort,
            )

    async def handle(self, message: Envelope) -> ActionResult:
        try:
            return await self._handle(message)
        except ExternalOwnerRequired as exc:
            delivery = self.session_router.defer_external(message, exc.owner)
            raise ExternalDeliveryPending(delivery) from exc
        except ExternalDeliveryPending:
            raise
        except asyncio.CancelledError:
            if self.session_router is not None:
                self.session_router.record(message.message_id, message.task_id, 'interrupted', error='turn cancelled')
            raise
        except GatewayNotStartedError as exc:
            if self.session_router is not None:
                self.session_router.record(message.message_id, message.task_id, 'queued', error=str(exc))
            raise
        except asyncio.TimeoutError as exc:
            if self.session_router is not None:
                self.session_router.record(message.message_id, message.task_id, 'interrupted',
                                           error=str(exc) or 'turn timed out; reconciliation required')
            raise
        except Exception as exc:
            if self.session_router is not None:
                self.session_router.record(message.message_id, message.task_id, 'failed', error=_failure_detail(exc))
            raise

    async def _handle(self, message: Envelope) -> ActionResult:
        async with self._lock:
            if self.session_router is not None:
                prior = self.session_router.result(message.message_id)
                if prior and prior['status'] == 'completed':
                    return ActionResult(accepted=True, output=prior['result'])
                if prior and prior['status'] in {'failed', 'interrupted', 'running', 'external_consumed',
                        'external_withdrawn_unconsumed', 'external_superseded_unconsumed'}:
                    return ActionResult(accepted=False, output={
                        'message_id': message.message_id, 'status': prior['status'],
                        'error': prior['error'], 'recovery_required': True,
                        'text': '该消息已有执行、交付或失败记录，已保留原始证据。请由质量主模型检查后创建新的显式任务版本或工作分配；不自动重放。',
                    })
                delivery_reader = getattr(self.session_router, 'external_delivery', None)
                delivery = delivery_reader(message.message_id) if delivery_reader else None
                if delivery is not None:
                    raise ExternalDeliveryPending(delivery)
                if prior and prior['status'] in {'delivery_pending', 'delivery_unknown'}:
                    return ActionResult(False, {'recovery_required': True,
                        'message_id': message.message_id, 'status': prior['status'],
                        'reason': 'external delivery record missing; no automatic replay'})
                self._assert_mesh_owned(message)
            event_text = str(message.payload.get("text", message.message_id))
            prompt = event_text
            if self.config.role == "astra":
                prompt = (
                    "Controller event metadata (authoritative IDs for delegation "
                    "and peer tools):\n"
                    f"project_id: {message.project_id}\n"
                    f"task_id: {message.task_id}\n"
                    f"task_version: {message.task_version}\n"
                    f"message_id: {message.message_id}\n"
                    f"source: {message.source.value}\n"
                    f"kind: {message.kind.value}\n"
                    f"sender: {message.sender}\n"
                    "Event text:\n"
                    f"{event_text}"
                )
            client, started, model, effort = await self._begin_turn(message, event_text, prompt)
            turn_id = started["turn"]["id"]
            try:
                completed = await asyncio.wait_for(
                    self._wait_for_completion(turn_id),
                    timeout=self.timeout_seconds,
                )
            except asyncio.CancelledError:
                await self._abort_turn(client, turn_id)
                raise
            except asyncio.TimeoutError as exc:
                await self._abort_turn(client, turn_id)
                raise asyncio.TimeoutError(
                    f"Codex turn {turn_id} exceeded {self.timeout_seconds}s; "
                    "interrupted and closed; reconciliation required, no automatic replay"
                ) from exc
            except Exception:
                # The work request was accepted. Even transport/capacity errors
                # may follow tool side effects: release this dead connection,
                # but never restart this turn automatically.
                await self._abort_turn(client, turn_id)
                raise
            turn = completed.params.get("turn", {})
            if turn.get("status") != "completed":
                error = turn.get("error") or {}
                detail = (error.get("message") if isinstance(error, dict)
                          else str(error)) or turn.get("status", "unknown")
                await self._discard_client()
                raise _turn_failure(f"Codex turn did not complete: {detail}", error)
            result = ActionResult(
                accepted=True,
                output={
                    "thread_id": self._thread_id,
                    "turn": completed.params.get("turn", {}),
                    "text": self._extract_text(completed.params),
                    "reasoning_effort": effort,
                    "model": model,
                    "provider": self.config.provider,
                },
            )
            if self.session_router is not None:
                self.session_router.record(message.message_id, message.task_id, 'completed', result=result.output)
            return result

    async def _begin_turn(self, message: Envelope, event_text: str, prompt: str):
        """Retry only proven unsent requests or an explicit capacity rejection."""
        for attempt in range(len(self.startup_retry_delays) + 1):
            try:
                self._assert_mesh_owned(message)
                try:
                    client = await self._start_request(self._ensure_client())
                except asyncio.TimeoutError as exc:
                    # No thread/turn request has been made at initialization.
                    raise GatewayNotStartedError(
                        'transport_unavailable', 'app-server initialization timed out',
                    ) from exc
                model, effort = self.config.model, self.config.reasoning_effort
                if self.config.role == "astra" and self.session_router is not None:
                    route = await self._start_request(self.session_router.prepare(
                        client, message, cwd=self.config.cwd,
                        config=(self.thread_config_factory() if self.thread_config_factory else None),
                        dynamic_tools=self.dynamic_tools,
                        developer_instructions=self.developer_instructions,
                    ))
                    self._thread_id = route['thread_id']
                    model, effort = route['model'], route['effort']
                elif self.config.role == "astra" and self.effort_selector is not None:
                    # A selector may itself start a model turn. Its failures are
                    # not eligible for work-request replay.
                    try:
                        chosen = await self.effort_selector.choose(
                            client, cwd=self.config.cwd, model=self.config.model,
                            text=event_text,
                        )
                    except Exception as exc:
                        await self._discard_client()
                        raise RuntimeError(f"effort selector failed: {exc}") from exc
                    effort = chosen if chosen in EFFORTS else "max"
                if self._thread_id is None:
                    response = await self._start_request(client.thread_start(
                        cwd=self.config.cwd,
                        model=self.config.model,
                        model_provider=self.config.provider,
                        config=(self.thread_config_factory() if self.thread_config_factory else None),
                        dynamic_tools=self.dynamic_tools,
                        developer_instructions=self.developer_instructions,
                    ))
                    self._thread_id = response["thread"]["id"]
                # Fence possible side effects durably before the first write.
                # A crash/lost response after send must recover as interrupted,
                # not queued. Only proven unsent/rejected work returns to queued.
                if self.session_router is not None:
                    self._assert_mesh_owned(message)
                    self.session_router.record(message.message_id, message.task_id, 'running')
                started = await self._start_request(client.turn_start(
                    thread_id=self._thread_id, text=prompt, model=model, effort=effort,
                ))
                return client, started, model, effort
            except (RequestNotSentError, JsonRpcError) as exc:
                await self._discard_client()
                if not isinstance(exc, RequestNotSentError) and not _capacity_rejection(exc):
                    raise
                reason = ('transport_unavailable' if isinstance(exc, RequestNotSentError)
                          else 'server_overloaded')
                if attempt == len(self.startup_retry_delays):
                    raise GatewayNotStartedError(reason, str(exc)) from exc
                await asyncio.sleep(self.startup_retry_delays[attempt])
            except BaseException:
                await self._discard_client()
                raise
        raise AssertionError("startup retry loop exhausted without outcome")

    def _assert_mesh_owned(self, message):
        guard = getattr(self.session_router, 'assert_mesh_owned', None)
        if guard is not None:
            guard(message.task_id, message.task_version)

    def external_delivery_expected(self, message: Envelope) -> bool:
        """Keep external human revisions out of mesh child-version side effects."""
        reader = getattr(self.session_router, 'external_delivery', None)
        if reader is not None and reader(message.message_id) is not None:
            return True
        owner = getattr(self.session_router, 'external_owner', None)
        return owner is not None and owner(message.task_id, message.task_version) is not None

    async def _discard_client(self) -> None:
        try:
            await asyncio.shield(self.close())
        except Exception:  # noqa: BLE001 - retain the original failure
            pass

    async def _abort_turn(self, client: AppServerClient, turn_id: str) -> None:
        try:
            await asyncio.wait_for(client.turn_interrupt(
                thread_id=self._thread_id, turn_id=turn_id,
            ), timeout=min(5.0, self.timeout_seconds or 5.0))
        except (Exception, asyncio.CancelledError):
            pass
        await self._discard_client()

    async def close(self) -> None:
        client = self._client
        self._client = None
        self._thread_id = None
        if self.session_router is not None:
            self.session_router.reset_connection()
        if client is not None:
            await client.close()

    async def read_rate_limits(self) -> dict:
        """Read account quota through app-server without starting a model turn."""
        async with self._lock:
            client = await self._start_request(self._ensure_client())
            return await self._start_request(client.account_rate_limits())

    async def _start_request(self, request: Awaitable[dict]) -> dict:
        try:
            return await asyncio.wait_for(request, timeout=min(
                self.startup_timeout_seconds,
                self.timeout_seconds if self.timeout_seconds is not None else float('inf'),
            ))
        except (Exception, asyncio.CancelledError):
            try:
                await asyncio.shield(self.close())
            except Exception:  # noqa: BLE001 - preserve the startup failure
                pass
            raise

    async def _ensure_client(self) -> AppServerClient:
        async with self._client_lock:
            return await self._initialize_client()

    async def _initialize_client(self) -> AppServerClient:
        if self._client is not None:
            if getattr(self._client.session, "is_alive", True):
                return self._client
            await self._discard_client()
        client = None
        try:
            if self.client_factory is not None:
                candidate = self.client_factory()
                client = await candidate if inspect.isawaitable(candidate) else candidate
            else:
                client = await AppServerClient.start_stdio(
                    codex_home=self.config.codex_home,
                    client_version=self.config.client_version,
                    role=self.config.role,
                )
            await client.initialize()
        except BaseException as exc:
            if client is not None:
                try:
                    await asyncio.shield(client.close())
                except Exception:
                    pass
            if isinstance(exc, RuntimeIntegrityError):
                # Immutable-cache validation happens before any work request.
                # Keep untouched inbox work pending under the controller's
                # durable node-wide cooldown; never replace a corrupt cache.
                raise GatewayNotStartedError('runtime_integrity', str(exc)) from exc
            if isinstance(exc, (ConnectionError, OSError)) and not isinstance(exc, RequestNotSentError):
                # initialize has not created or resumed any work thread. A
                # missing binary/dead child must not terminalize the inbox.
                raise GatewayNotStartedError('transport_unavailable', str(exc)) from exc
            raise
        self._client = client
        return client

    async def _wait_for_completion(self, turn_id: str):
        while True:
            notification = await self._client.session.next_notification()
            if notification.method == "item/tool/call":
                await self._handle_dynamic_tool(notification, turn_id)
                continue
            if notification.request_id is not None:
                # Approval/elicitation requests need an explicit response. This
                # unattended gateway never approves operations on a user's behalf.
                detail = f"Unsupported app-server request: {notification.method}"
                LOG.warning("unsupported_app_server_request %s", json.dumps({
                    "request_id": notification.request_id,
                    "method": notification.method,
                    "thread_id": notification.params.get("threadId"),
                    "turn_id": notification.params.get("turnId"),
                }, ensure_ascii=True))
                await self._client.session.reject(
                    notification.request_id, code=-32601, message=detail,
                )
                raise RuntimeError(f"{detail}; request rejected, reconciliation required")
            if notification.method == "error":
                error = terminal_error_message(
                    notification.params, thread_id=self._thread_id, turn_id=turn_id,
                )
                if error is not None:
                    raise _turn_failure(error, notification.params.get("error", notification.params))
                continue
            if (notification.method == "turn/completed" and
                    notification_matches_turn(
                        notification.params, thread_id=self._thread_id,
                        turn_id=turn_id,
                    )):
                return notification

    async def _handle_dynamic_tool(self, request, turn_id: str) -> None:
        if request.request_id is None:
            raise RuntimeError("dynamic tool request omitted its id")
        try:
            if self.dynamic_tool_handler is None:
                raise RuntimeError("dynamic tools are not enabled")
            if (request.params.get("threadId") != self._thread_id or
                    request.params.get("turnId") != turn_id):
                raise RuntimeError("dynamic tool request targeted another turn")
            name = request.params.get("tool")
            arguments = request.params.get("arguments") or {}
            if not isinstance(name, str) or not isinstance(arguments, dict):
                raise ValueError("invalid dynamic tool name or arguments")
            candidate = self.dynamic_tool_handler(name, arguments)
            result = (await candidate if inspect.isawaitable(candidate)
                      else candidate)
            result_text = json.dumps(result, ensure_ascii=True)
            success = True
        except Exception as exc:  # noqa: BLE001 - tool errors return to Astra
            result_text = json.dumps({
                "error": f"{type(exc).__name__}: {exc}",
            }, ensure_ascii=True)
            success = False
        await self._client.session.respond(request.request_id, {
            "contentItems": [{"type": "inputText", "text": result_text}],
            "success": success,
        })

    @staticmethod
    def _extract_text(params: dict) -> str:
        items = params.get("turn", {}).get("items", [])
        messages = [item for item in items if item.get("type") == "agentMessage"]
        for item in reversed(messages):
            if item.get("phase") == "final_answer":
                return str(item.get("text", ""))
        if messages:
            return str(messages[-1].get("text", ""))
        return ""
