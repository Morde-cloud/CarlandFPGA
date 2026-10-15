import tempfile
import asyncio
import unittest
from pathlib import Path

from fpga_mesh.app_server import AppServerClient
from fpga_mesh.gateway import AppServerGateway, GatewayConfig, GatewayNotStartedError, GatewayTurnFailure
from fpga_mesh.protocol import Envelope, MessageKind, SourceKind
from fpga_mesh.rpc import JsonRpcNotification, JsonRpcError, RequestNotSentError
from datetime import datetime, timezone


class FakeSession:
    def __init__(self):
        self.requests = []
        self.notifications = []
        self.is_alive = True

    async def request(self, method, params=None):
        self.requests.append((method, params or {}))
        if method == "thread/start":
            return {"thread": {"id": "thread-1"}}
        if method == "turn/start":
            return {"turn": {"id": "turn-1"}}
        return {}

    async def notify(self, method, params=None):
        self.requests.append((method, params or {}))

    async def respond(self, request_id, result):
        self.requests.append(("response", {"id": request_id, "result": result}))

    async def reject(self, request_id, *, code=-32601, message="Method not supported"):
        self.requests.append(("rejection", {"id": request_id,
                                            "error": {"code": code, "message": message}}))

    async def next_notification(self):
        return self.notifications.pop(0)

    async def close(self):
        self.is_alive = False
        self.requests.append(("close", {}))


class RecordingRouter:
    """A persistent-run interface stub: execution is exercised through the wire."""

    def __init__(self):
        self.runs = {}

    def result(self, message_id):
        return self.runs.get(message_id)

    def record(self, message_id, task_id, status, *, result=None, error=None):
        self.runs[message_id] = {'status': status, 'result': result, 'error': error}

    async def prepare(self, client, message, **kwargs):
        return {'thread_id': 'thread-1', 'model': 'gpt-6-astra', 'effort': 'max'}

    def reset_connection(self):
        pass


def completed():
    return JsonRpcNotification(method='turn/completed', params={
        'threadId': 'thread-1', 'turn': {
            'id': 'turn-1', 'status': 'completed', 'items': [],
        },
    })


def message() -> Envelope:
    return Envelope(
        message_id="msg-1",
        project_id="fpga-main",
        sender="human-1",
        recipient="A/Astra-A",
        task_id="task-1",
        task_version=1,
        sent_at=datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc),
        kind=MessageKind.HUMAN_INSTRUCTION,
        source=SourceKind.HUMAN,
        payload={"text": "inspect"},
    )


class AppServerGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.session = FakeSession()
        self.client = AppServerClient(self.session, client_version="0.159.0")
        self.config = GatewayConfig(
            node_id="A",
            role="astra",
            model="gpt-6-astra",
            provider="openai",
            reasoning_effort="max",
            cwd=str(Path.cwd()),
            codex_home=str(Path(self.tmp.name)),
        )
        self.gateway = AppServerGateway(
            self.config,
            client_factory=lambda: self.client,
        )

    async def asyncTearDown(self):
        await self.gateway.close()
        self.tmp.cleanup()

    async def test_crash_after_turn_send_cannot_replay_on_restart(self):
        from fpga_mesh.sessions import MainSessionRouter
        import sqlite3
        class ProcessCrash(BaseException):
            pass
        path = Path(self.tmp.name) / 'crash-ledger.sqlite'
        router = MainSessionRouter(path)
        async def prepare(*args, **kwargs):
            return {'thread_id': 'thread-1', 'model': 'gpt-6-astra', 'effort': 'max'}
        router.prepare = prepare
        original = self.session.request
        observed = []
        async def crash_after_send(method, params=None):
            if method == 'turn/start':
                # A separate connection sees only committed durable state.
                db = sqlite3.connect(path)
                try:
                    row = db.execute('SELECT status FROM main_runs WHERE message_id=?', ('msg-1',)).fetchone()
                    observed.append(row[0] if row else None)
                finally:
                    db.close()
                raise ProcessCrash()
            return await original(method, params)
        self.session.request = crash_after_send
        gateway = AppServerGateway(self.config, client_factory=lambda: self.client,
                                   session_router=router)
        with self.assertRaises(ProcessCrash):
            await gateway.handle(message())
        router.db.close()
        restarted = MainSessionRouter(path)
        try:
            self.assertEqual(observed, ['running'])
            self.assertEqual(restarted.result('msg-1')['status'], 'interrupted')
            no_replay = AppServerGateway(self.config, session_router=restarted,
                client_factory=lambda: self.fail('ambiguous work must not restart'))
            result = await no_replay.handle(message())
            self.assertFalse(result.accepted)
            self.assertTrue(result.output['recovery_required'])
        finally:
            restarted.db.close()

    async def test_stalled_quota_read_releases_serial_gateway(self):
        class StalledQuotaSession(FakeSession):
            async def request(self, method, params=None):
                if method == 'account/rateLimits/read':
                    await asyncio.Event().wait()
                return await super().request(method, params)
        session = StalledQuotaSession()
        gateway = AppServerGateway(
            self.config, client_factory=lambda: AppServerClient(session, client_version='test'),
            startup_timeout_seconds=0.01,
        )
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(gateway.read_rate_limits(), 1)
        self.assertFalse(gateway._lock.locked())
        self.assertIsNone(gateway._client)
        self.assertFalse(session.is_alive)

    async def test_no_model_call_until_a_message_is_handled(self):
        self.assertEqual(self.session.requests, [])
        self.session.notifications.append(
            JsonRpcNotification(
                method="turn/completed",
                params={
                    "threadId": "thread-1",
                    "turn": {
                        "id": "turn-1",
                        "status": "completed",
                        "items": [{"type": "agentMessage", "text": "done"}],
                    }
                },
            )
        )
        result = await self.gateway.handle(message())
        self.assertTrue(result.accepted)
        self.assertEqual(result.output["text"], "done")

    async def test_astra_receives_authoritative_task_identity_for_delegation(self):
        self.session.notifications.append(JsonRpcNotification(
            method="turn/completed",
            params={"threadId": "thread-1", "turn": {
                "id": "turn-1", "status": "completed", "items": [],
            }},
        ))
        await self.gateway.handle(message())
        turn = next(params for method, params in self.session.requests
                    if method == "turn/start")
        prompt = turn["input"][0]["text"] if "input" in turn else turn["text"]
        self.assertIn("task_id: task-1", prompt)
        self.assertIn("task_version: 1", prompt)
        self.assertIn("source: human", prompt)
        self.assertIn("inspect", prompt)

    async def test_second_message_reuses_the_same_thread(self):
        self.session.notifications.extend(
            [
                JsonRpcNotification(
                    method="turn/completed",
                    params={"threadId": "thread-1", "turn": {
                        "id": "turn-1", "status": "completed", "items": [],
                    }},
                ),
                JsonRpcNotification(
                    method="turn/completed",
                    params={"threadId": "thread-1", "turn": {
                        "id": "turn-1", "status": "completed", "items": [],
                    }},
                ),
            ]
        )
        await self.gateway.handle(message())
        await self.gateway.handle(message())
        methods = [method for method, _ in self.session.requests]
        self.assertEqual(methods.count("initialize"), 1)
        self.assertEqual(methods.count("thread/start"), 1)
        self.assertEqual(methods.count("turn/start"), 2)

    async def test_child_gateway_uses_provider_and_max_from_config(self):
        config = GatewayConfig(
            node_id="A",
            role="deepseek_child",
            model="deepseek-flash",
            provider="deepseek",
            reasoning_effort="max",
            cwd=str(Path.cwd()),
            codex_home=str(Path(self.tmp.name)),
        )
        gateway = AppServerGateway(config, client_factory=lambda: self.client)
        self.session.notifications.append(
            JsonRpcNotification(
                method="turn/completed",
                params={"threadId": "thread-1", "turn": {
                    "id": "turn-1", "status": "completed", "items": [],
                }},
            )
        )
        await gateway.handle(message())
        turn = [
            params
            for method, params in self.session.requests
            if method == "turn/start"
        ][0]
        self.assertEqual(turn["model"], "deepseek-flash")
        self.assertEqual(turn["effort"], "max")
        await gateway.close()

    async def test_parent_gateway_registers_tool_config_on_thread_start(self):
        tool_config = {"mcp_servers": {"fpga_children": {
            "command": "python", "args": ["-m", "fpga_mesh.mcp_children"],
        }}}
        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            thread_config_factory=lambda: tool_config,
        )
        self.session.notifications.append(
            JsonRpcNotification(method="turn/completed",
                                params={"threadId": "thread-1", "turn": {
                                    "id": "turn-1", "status": "completed", "items": [],
                                }})
        )
        await gateway.handle(message())
        start = [params for method, params in self.session.requests
                 if method == "thread/start"][0]
        self.assertEqual(start["config"], tool_config)
        await gateway.close()

    async def test_parent_gateway_installs_node_policy_on_thread_start(self):
        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            developer_instructions="Astra-A: prioritize humans and verify child work",
        )
        self.session.notifications.append(JsonRpcNotification(
            method="turn/completed",
            params={"threadId": "thread-1", "turn": {
                "id": "turn-1", "status": "completed", "items": [],
            }},
        ))
        await gateway.handle(message())
        start = next(params for method, params in self.session.requests
                     if method == "thread/start")
        self.assertIn("prioritize humans", start["developerInstructions"])
        await gateway.close()

    async def test_failed_turn_is_not_reported_as_accepted(self):
        self.session.notifications.append(JsonRpcNotification(
            method="turn/completed",
            params={"threadId": "thread-1", "turn": {"id": "turn-1", "status": "failed",
                             "error": {"message": "provider rejected request"},
                             "items": []}},
        ))
        with self.assertRaisesRegex(RuntimeError, "provider rejected request"):
            await self.gateway.handle(message())

    async def test_retryable_errors_wait_for_successful_turn_completion(self):
        self.session.notifications.extend([
            JsonRpcNotification(method="error", params={
                "threadId": "thread-1", "turnId": "turn-1",
                "error": {"message": "temporary provider interruption"},
                "willRetry": True,
            }),
            JsonRpcNotification(method="error", params={
                "threadId": "thread-1", "turnId": "turn-1",
                "error": {"message": "retrying stream"}, "willRetry": True,
            }),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed", "items": [
                    {"type": "agentMessage", "phase": "final_answer",
                     "text": "recovered"},
                ]},
            }),
        ])
        result = await self.gateway.handle(message())
        self.assertTrue(result.accepted)
        self.assertEqual(result.output["text"], "recovered")
        self.assertEqual(self.session.notifications, [])

    async def test_terminal_error_surfaces_structured_provider_message(self):
        self.session.notifications.append(JsonRpcNotification(method="error", params={
            "threadId": "thread-1", "turnId": "turn-1",
            "error": {"message": "provider quota exhausted"}, "willRetry": False,
        }))
        with self.assertRaisesRegex(RuntimeError, "provider quota exhausted"):
            await self.gateway.handle(message())

    async def test_errors_from_other_threads_and_turns_do_not_fail_current_work(self):
        self.session.notifications.extend([
            JsonRpcNotification(method="error", params={
                "threadId": "another-thread", "turnId": "turn-1",
                "error": {"message": "another thread failed"}, "willRetry": False,
            }),
            JsonRpcNotification(method="error", params={
                "threadId": "thread-1", "turnId": "an-earlier-turn",
                "error": {"message": "earlier turn failed"}, "willRetry": False,
            }),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed", "items": [
                    {"type": "agentMessage", "text": "current result"},
                ]},
            }),
        ])
        result = await self.gateway.handle(message())
        self.assertEqual(result.output["text"], "current result")

    async def test_completion_requires_matching_thread_and_explicit_turn_id(self):
        self.session.notifications.extend([
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "another-thread",
                "turn": {"id": "turn-1", "status": "completed", "items": [
                    {"type": "agentMessage", "text": "foreign result"},
                ]},
            }),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"status": "completed", "items": [
                    {"type": "agentMessage", "text": "unidentified result"},
                ]},
            }),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed", "items": [
                    {"type": "agentMessage", "text": "current result"},
                ]},
            }),
        ])
        result = await self.gateway.handle(message())
        self.assertEqual(result.output["text"], "current result")

    async def test_transport_error_without_turn_ids_remains_fatal(self):
        self.session.notifications.append(JsonRpcNotification(
            method="error", params={"message": "app-server connection closed"},
        ))
        with self.assertRaisesRegex(RuntimeError, "app-server connection closed"):
            await self.gateway.handle(message())

    async def test_retry_wait_timeout_interrupts_turn_and_closes_client(self):
        events = [JsonRpcNotification(method="error", params={
            "threadId": "thread-1", "turnId": "turn-1",
            "error": {"message": "temporary stream failure"}, "willRetry": True,
        })]

        async def stalled_retry():
            if events:
                return events.pop(0)
            await asyncio.Event().wait()

        self.session.next_notification = stalled_retry
        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client, timeout_seconds=0.01,
        )
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(gateway.handle(message()), 1)
        self.assertIn(("turn/interrupt", {
            "threadId": "thread-1", "turnId": "turn-1",
        }), self.session.requests)
        self.assertIn(("close", {}), self.session.requests)

    async def test_cancel_during_retry_interrupts_turn_and_closes_client(self):
        waiting = asyncio.Event()
        events = [JsonRpcNotification(method="error", params={
            "threadId": "thread-1", "turnId": "turn-1",
            "error": {"message": "temporary stream failure"}, "willRetry": True,
        })]

        async def stalled_retry():
            if events:
                return events.pop(0)
            waiting.set()
            await asyncio.Event().wait()

        self.session.next_notification = stalled_retry
        pending = asyncio.create_task(self.gateway.handle(message()))
        try:
            await asyncio.wait_for(waiting.wait(), 0.2)
        finally:
            pending.cancel()
            try:
                await pending
            except asyncio.CancelledError:
                pass
        self.assertIn(("turn/interrupt", {
            "threadId": "thread-1", "turnId": "turn-1",
        }), self.session.requests)
        self.assertIn(("close", {}), self.session.requests)

    async def test_gateway_uses_final_message_and_skips_old_turn(self):
        self.session.notifications.extend([
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "earlier", "status": "completed", "items": []},
            }),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed", "items": [
                    {"type": "agentMessage", "phase": "commentary", "text": "working"},
                    {"type": "agentMessage", "phase": "final_answer", "text": "done"},
                ]},
            }),
        ])
        result = await self.gateway.handle(message())
        self.assertEqual(result.output["text"], "done")

    async def test_parent_dynamic_tool_call_is_answered_during_turn(self):
        calls = []

        async def handler(name, arguments):
            calls.append((name, arguments))
            return {"standby": 2}

        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            dynamic_tools=[{"type": "function", "name": "fpga_child_status",
                            "description": "status", "inputSchema": {"type": "object"}}],
            dynamic_tool_handler=handler,
        )
        self.session.notifications.extend([
            JsonRpcNotification(method="item/tool/call", request_id=73,
                                params={"threadId": "thread-1", "turnId": "turn-1",
                                        "tool": "fpga_child_status", "arguments": {}}),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed", "items": []},
            }),
        ])
        await gateway.handle(message())
        self.assertEqual(calls, [("fpga_child_status", {})])
        self.assertEqual([params for method, params in self.session.requests
                          if method == "thread/start"][0]["dynamicTools"][0]["name"],
                         "fpga_child_status")
        response = [params for method, params in self.session.requests
                    if method == "response"][0]
        self.assertEqual(response["id"], 73)
        self.assertTrue(response["result"]["success"])
        self.assertIn("standby", response["result"]["contentItems"][0]["text"])
        await gateway.close()

    async def test_non_json_tool_result_returns_failure_response(self):
        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            dynamic_tool_handler=lambda _name, _args: {"bad": {1, 2}},
        )
        self.session.notifications.extend([
            JsonRpcNotification(method="item/tool/call", request_id="tool-1",
                                params={"threadId": "thread-1", "turnId": "turn-1",
                                        "tool": "fpga_child_status", "arguments": {}}),
            JsonRpcNotification(method="turn/completed", params={
                "threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed", "items": []},
            }),
        ])
        await gateway.handle(message())
        response = [params for method, params in self.session.requests
                    if method == "response"][0]
        self.assertEqual(response["id"], "tool-1")
        self.assertFalse(response["result"]["success"])
        await gateway.close()

    async def test_parent_uses_model_selected_effort_for_substantive_turn(self):
        class Selector:
            async def choose(self, client, *, cwd, model, text):
                return "medium"

        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            effort_selector=Selector(),
        )
        self.session.notifications.append(JsonRpcNotification(
            method="turn/completed",
            params={"threadId": "thread-1", "turn": {
                "id": "turn-1", "status": "completed", "items": [],
            }},
        ))
        result = await gateway.handle(message())
        turn = [params for method, params in self.session.requests
                if method == "turn/start"][0]
        self.assertEqual(turn["effort"], "medium")
        self.assertEqual(result.output["reasoning_effort"], "medium")
        await gateway.close()

    async def test_selector_failure_closes_session_before_work_turn(self):
        class Selector:
            async def choose(self, client, *, cwd, model, text):
                raise RuntimeError("selector turn could not be interrupted")

        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            effort_selector=Selector(),
        )
        with self.assertRaisesRegex(RuntimeError, "could not be interrupted"):
            await gateway.handle(message())
        methods = [method for method, _ in self.session.requests]
        self.assertIn("close", methods)
        self.assertNotIn("turn/start", methods)

    async def test_turn_start_without_response_is_bounded_and_session_closed(self):
        original_request = self.session.request

        async def hanging_turn(method, params=None):
            if method == "turn/start":
                await asyncio.Event().wait()
            return await original_request(method, params)

        self.session.request = hanging_turn
        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            timeout_seconds=0.01,
        )
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(gateway.handle(message()), 1)
        self.assertIn(("close", {}), self.session.requests)

    async def test_stalled_completion_and_interrupt_close_session(self):
        original_request = self.session.request

        async def hanging_interrupt(method, params=None):
            if method == "turn/interrupt":
                await asyncio.Event().wait()
            return await original_request(method, params)

        async def no_notifications():
            await asyncio.Event().wait()

        self.session.request = hanging_interrupt
        self.session.next_notification = no_notifications
        gateway = AppServerGateway(
            self.config, client_factory=lambda: self.client,
            timeout_seconds=0.01,
        )
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(gateway.handle(message()), 1)
        self.assertIn(("close", {}), self.session.requests)


    async def test_closed_cached_connection_is_replaced_before_next_work(self):
        replacement = FakeSession()
        replacement.notifications.append(completed())
        clients = iter([self.client, AppServerClient(replacement, client_version='test')])
        gateway = AppServerGateway(self.config, client_factory=lambda: next(clients))
        await gateway._ensure_client()
        self.session.is_alive = False
        result = await gateway.handle(message())
        self.assertTrue(result.accepted)
        self.assertNotIn('turn/start', [m for m, _ in self.session.requests])
        self.assertEqual([m for m, _ in replacement.requests].count('turn/start'), 1)
        await gateway.close()

    async def test_proven_unsent_start_reconnects_and_retries_only_once(self):
        original = self.session.request

        async def rejected_start(method, params=None):
            if method == 'turn/start':
                raise RequestNotSentError('connection already closed; request not sent')
            return await original(method, params)

        self.session.request = rejected_start
        healthy = FakeSession()
        healthy.notifications.append(completed())
        clients = iter([self.client, AppServerClient(healthy, client_version='test')])
        gateway = AppServerGateway(self.config, client_factory=lambda: next(clients),
                                   startup_retry_delays=(0,))
        self.assertTrue((await gateway.handle(message())).accepted)
        self.assertNotIn('turn/start', [m for m, _ in self.session.requests])
        self.assertEqual([m for m, _ in healthy.requests].count('turn/start'), 1)
        await gateway.close()

    async def test_unsent_exhaustion_retains_queued_run_for_controller_backoff(self):
        async def not_sent(method, params=None):
            raise RequestNotSentError('not sent')

        self.session.request = not_sent
        router = RecordingRouter()
        gateway = AppServerGateway(self.config, client_factory=lambda: self.client,
                                   session_router=router, startup_retry_delays=(0,))
        with self.assertRaises(GatewayNotStartedError) as raised:
            await gateway.handle(message())
        self.assertTrue(raised.exception.safe_to_retry)
        self.assertEqual(raised.exception.reason, 'transport_unavailable')
        self.assertGreater(raised.exception.retry_after_seconds, 0)
        self.assertEqual(router.result('msg-1')['status'], 'queued')
        self.assertIn('not started', router.result('msg-1')['error'])
        self.assertIsNone(gateway._client)

    async def test_ambiguous_sent_start_is_never_retried(self):
        original = self.session.request

        async def response_lost(method, params=None):
            if method == 'turn/start':
                self.session.requests.append((method, params or {}))
                raise ConnectionError('response lost after sending')
            return await original(method, params)

        self.session.request = response_lost
        router = RecordingRouter()
        gateway = AppServerGateway(self.config, client_factory=lambda: self.client,
                                   session_router=router, startup_retry_delays=(0, 0))
        with self.assertRaisesRegex(ConnectionError, 'response lost'):
            await gateway.handle(message())
        self.assertEqual([m for m, _ in self.session.requests].count('turn/start'), 1)
        self.assertEqual(router.result('msg-1')['status'], 'failed')
        duplicate = await gateway.handle(message())
        self.assertFalse(duplicate.accepted)
        self.assertTrue(duplicate.output['recovery_required'])
        self.assertIsNone(gateway._client)

    async def test_ambiguous_thread_creation_is_not_repeated(self):
        original = self.session.request

        async def response_lost(method, params=None):
            if method == 'thread/start':
                self.session.requests.append((method, params or {}))
                raise ConnectionError('thread may have been created')
            return await original(method, params)

        self.session.request = response_lost
        gateway = AppServerGateway(self.config, client_factory=lambda: self.client,
                                   startup_retry_delays=(0, 0))
        with self.assertRaisesRegex(ConnectionError, 'may have been created'):
            await gateway.handle(message())
        methods = [m for m, _ in self.session.requests]
        self.assertEqual(methods.count('thread/start'), 1)
        self.assertNotIn('turn/start', methods)

    async def test_explicit_capacity_rejection_retries_same_model(self):
        original = self.session.request

        async def at_capacity(method, params=None):
            if method == 'turn/start':
                self.session.requests.append((method, params or {}))
                raise JsonRpcError(method, {'code': -32000,
                    'message': 'Selected model is at capacity. Please try a different model.'})
            return await original(method, params)

        self.session.request = at_capacity
        healthy = FakeSession()
        healthy.notifications.append(completed())
        clients = iter([self.client, AppServerClient(healthy, client_version='test')])
        gateway = AppServerGateway(self.config, client_factory=lambda: next(clients),
                                   startup_retry_delays=(0,))
        self.assertTrue((await gateway.handle(message())).accepted)
        first = next(p for m, p in self.session.requests if m == 'turn/start')
        second = next(p for m, p in healthy.requests if m == 'turn/start')
        self.assertEqual((first['model'], first['effort']), (second['model'], second['effort']))
        await gateway.close()

    async def test_capacity_exhaustion_is_deferred_but_quota_rejection_is_not(self):
        for detail, expected in [
            ('server_overloaded', GatewayNotStartedError),
            ('account quota exhausted', JsonRpcError),
        ]:
            with self.subTest(detail=detail):
                session = FakeSession()
                original = session.request

                async def rejected(method, params=None):
                    if method == 'turn/start':
                        session.requests.append((method, params or {}))
                        raise JsonRpcError(method, {'code': -32000, 'message': detail})
                    return await original(method, params)

                session.request = rejected
                router = RecordingRouter()
                gateway = AppServerGateway(self.config,
                    client_factory=lambda: AppServerClient(session, client_version='test'),
                    session_router=router, startup_retry_delays=())
                with self.assertRaises(expected):
                    await gateway.handle(message())
                self.assertEqual(router.result('msg-1')['status'],
                                 'queued' if expected is GatewayNotStartedError else 'failed')
                self.assertEqual([m for m, _ in session.requests].count('turn/start'), 1)

    async def test_capacity_error_after_tool_execution_never_replays(self):
        calls = []
        router = RecordingRouter()
        gateway = AppServerGateway(self.config, client_factory=lambda: self.client,
            session_router=router, startup_retry_delays=(0, 0),
            dynamic_tool_handler=lambda name, args: calls.append(name) or {'done': True})
        self.session.notifications.extend([
            JsonRpcNotification(method='item/tool/call', request_id=9, params={
                'threadId': 'thread-1', 'turnId': 'turn-1', 'tool': 'write_output', 'arguments': {},
            }),
            JsonRpcNotification(method='error', params={
                'threadId': 'thread-1', 'turnId': 'turn-1', 'willRetry': False,
                'error': {'message': 'Selected model is at capacity'},
            }),
        ])
        with self.assertRaisesRegex(GatewayTurnFailure, 'at capacity') as raised:
            await gateway.handle(message())
        self.assertEqual(raised.exception.reason, 'server_overloaded')
        self.assertFalse(raised.exception.safe_to_retry)
        self.assertEqual(raised.exception.retry_after_seconds, 30)
        self.assertEqual(calls, ['write_output'])
        self.assertEqual([m for m, _ in self.session.requests].count('turn/start'), 1)
        self.assertEqual(router.result('msg-1')['status'], 'failed')
        self.assertIn('server_overloaded', router.result('msg-1')['error'])
        self.assertIn('not account quota', router.result('msg-1')['error'])
        self.assertIsNone(gateway._client)
        self.assertFalse((await gateway.handle(message())).accepted)
        self.assertEqual(calls, ['write_output'])

    async def test_unknown_approval_request_is_rejected_without_hour_long_wait(self):
        self.session.notifications.append(JsonRpcNotification(
            method='item/commandExecution/requestApproval', request_id=77,
            params={'threadId': 'thread-1', 'turnId': 'turn-1', 'secret': 'must-not-log'},
        ))
        gateway = AppServerGateway(self.config, client_factory=lambda: self.client,
                                   timeout_seconds=3600)
        with self.assertLogs('fpga_mesh.gateway', level='WARNING') as logs:
            with self.assertRaisesRegex(RuntimeError, 'Unsupported app-server request'):
                await asyncio.wait_for(gateway.handle(message()), .5)
        self.assertIn('requestApproval', logs.output[0])
        self.assertIn('thread-1', logs.output[0])
        self.assertNotIn('must-not-log', logs.output[0])
        rejection = next(p for m, p in self.session.requests if m == 'rejection')
        self.assertEqual(rejection['id'], 77)
        self.assertEqual(rejection['error']['code'], -32601)
        self.assertIn('turn/interrupt', [m for m, _ in self.session.requests])
        self.assertIsNone(gateway._client)

    async def test_total_timeout_keeps_interrupted_status_and_nonempty_reason(self):
        async def stall():
            await asyncio.Event().wait()

        self.session.next_notification = stall
        router = RecordingRouter()
        gateway = AppServerGateway(self.config, client_factory=lambda: self.client,
                                   session_router=router, timeout_seconds=.01)
        with self.assertRaisesRegex(asyncio.TimeoutError, 'turn-1 exceeded'):
            await gateway.handle(message())
        record = router.result('msg-1')
        self.assertEqual(record['status'], 'interrupted')
        self.assertIn('no automatic replay', record['error'])
        self.assertFalse((await gateway.handle(message())).accepted)

    async def test_startup_timeout_is_independent_of_long_work_timeout(self):
        original = self.session.request

        async def stall_start(method, params=None):
            if method == 'turn/start':
                self.session.requests.append((method, params or {}))
                await asyncio.Event().wait()
            return await original(method, params)

        self.session.request = stall_start
        gateway = AppServerGateway(self.config, client_factory=lambda: self.client,
                                   timeout_seconds=3600, startup_timeout_seconds=.01)
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(gateway.handle(message()), .5)
        self.assertEqual([m for m, _ in self.session.requests].count('turn/start'), 1)
        self.assertIsNone(gateway._client)

    async def test_active_transport_failure_does_not_poison_next_message(self):
        self.session.notifications.append(JsonRpcNotification(
            method='error', params={'message': 'app-server connection closed'},
        ))
        healthy = FakeSession()
        healthy.notifications.append(completed())
        clients = iter([self.client, AppServerClient(healthy, client_version='test')])
        gateway = AppServerGateway(self.config, client_factory=lambda: next(clients))
        with self.assertRaisesRegex(RuntimeError, 'connection closed'):
            await gateway.handle(message())
        self.assertIsNone(gateway._client)
        self.assertTrue((await gateway.handle(message())).accepted)
        self.assertEqual([m for m, _ in healthy.requests].count('turn/start'), 1)
        await gateway.close()


    async def test_backend_creation_failure_is_deferred_without_starting_work(self):
        def unavailable():
            raise FileNotFoundError('verified Codex executable missing')

        router = RecordingRouter()
        gateway = AppServerGateway(self.config, client_factory=unavailable,
                                   session_router=router, startup_retry_delays=())
        with self.assertRaises(GatewayNotStartedError) as raised:
            await gateway.handle(message())
        self.assertEqual(raised.exception.reason, 'transport_unavailable')
        self.assertEqual(router.result('msg-1')['status'], 'queued')
        self.assertIsNone(gateway._client)

    async def test_initialize_connection_loss_defers_and_closes_failed_client(self):
        async def initialize_lost(method, params=None):
            self.session.requests.append((method, params or {}))
            raise ConnectionError('initialize response lost')

        self.session.request = initialize_lost
        gateway = AppServerGateway(self.config, client_factory=lambda: self.client,
                                   startup_retry_delays=())
        with self.assertRaises(GatewayNotStartedError):
            await gateway.handle(message())
        methods = [m for m, _ in self.session.requests]
        self.assertNotIn('thread/start', methods)
        self.assertNotIn('turn/start', methods)
        self.assertIn('close', methods)
        self.assertIsNone(gateway._client)

    async def test_structured_capacity_notification_is_not_quota_or_retry_permission(self):
        self.session.notifications.append(JsonRpcNotification(method='error', params={
            'threadId': 'thread-1', 'turnId': 'turn-1', 'willRetry': False,
            'error': {'message': 'try again later', 'codexErrorInfo': 'serverOverloaded'},
        }))
        with self.assertRaises(GatewayTurnFailure) as raised:
            await self.gateway.handle(message())
        self.assertEqual(raised.exception.reason, 'server_overloaded')
        self.assertFalse(raised.exception.safe_to_retry)
        self.assertEqual([m for m, _ in self.session.requests].count('turn/start'), 1)

    async def test_capacity_word_in_other_error_does_not_enable_replay(self):
        original = self.session.request

        async def other_error(method, params=None):
            if method == 'turn/start':
                self.session.requests.append((method, params or {}))
                raise JsonRpcError(method, {'code': -32000,
                    'message': 'invalid value: server_overloaded is not a model'})
            return await original(method, params)

        self.session.request = other_error
        gateway = AppServerGateway(self.config, client_factory=lambda: self.client,
                                   startup_retry_delays=(0, 0))
        with self.assertRaises(JsonRpcError):
            await gateway.handle(message())
        self.assertEqual([m for m, _ in self.session.requests].count('turn/start'), 1)

    async def test_structured_capacity_start_rejection_is_deferred(self):
        original = self.session.request

        async def rejected(method, params=None):
            if method == 'turn/start':
                raise JsonRpcError(method, {'code': -32000, 'message': 'retry later',
                    'data': {'codexErrorInfo': 'serverOverloaded'}})
            return await original(method, params)

        self.session.request = rejected
        gateway = AppServerGateway(self.config, client_factory=lambda: self.client,
                                   startup_retry_delays=())
        with self.assertRaises(GatewayNotStartedError) as raised:
            await gateway.handle(message())
        self.assertEqual(raised.exception.reason, 'server_overloaded')


    async def test_initialize_timeout_retains_unstarted_work_for_backoff(self):
        async def initialize_stalled(method, params=None):
            self.session.requests.append((method, params or {}))
            await asyncio.Event().wait()

        self.session.request = initialize_stalled
        router = RecordingRouter()
        gateway = AppServerGateway(self.config, client_factory=lambda: self.client,
            session_router=router, timeout_seconds=3600, startup_timeout_seconds=.01)
        with self.assertRaisesRegex(GatewayNotStartedError, 'initialization timed out'):
            await asyncio.wait_for(gateway.handle(message()), .5)
        self.assertEqual(router.result('msg-1')['status'], 'queued')
        methods = [m for m, _ in self.session.requests]
        self.assertNotIn('thread/start', methods)
        self.assertIn('close', methods)


if __name__ == "__main__":
    unittest.main()
