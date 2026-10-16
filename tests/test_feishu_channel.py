import asyncio
import sys
import tempfile
import threading
import unittest
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from fpga_mesh import feishu_channel
from fpga_mesh.feishu_channel import FeishuAppSender, FeishuIngress, FeishuNodeService
from fpga_mesh.protocol import MessageKind, SourceKind
from fpga_mesh.store import SQLiteStore


@dataclass
class FakeMention:
    open_id: str
    is_bot: bool = True


@dataclass
class FakeMessage:
    chat_id: str = "oc_team"
    chat_type: str = "group"
    sender_id: str = "ou_member"
    sender_type: str = "user"
    message_id: str = "om_first"
    create_time: int = 1_780_000_000_000
    body_text: str = "new FPGA task"
    raw: dict = field(default_factory=dict)
    mentions: list = field(default_factory=list)
    mentioned_bot: bool = False


class RecordingController:
    def __init__(self):
        self.messages = []

    async def offer(self, message):
        self.messages.append(message)
        return True


class FakeChannel:
    def __init__(self):
        self.handlers = {}
        self.connected = False
        self.sent = []

    def on(self, event, handler):
        self.handlers[event] = handler

    async def connect_until_ready(self, *, timeout=30):
        self.connected = True

    async def disconnect(self):
        self.connected = False

    async def send(self, to, message, opts=None):
        self.sent.append((to, message, opts))
        return type("Result", (), {"success": True, "message_id": "om_sent"})()


class FeishuIngressTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.controller = RecordingController()
        self.ingress = FeishuIngress(
            node_id="A", project_id="fpga-main", group_id="oc_team",
            app_id="cli_astra_a", controller=self.controller,
            local_bot_open_ids={"ou_astra_a", "ou_deepseek_a"},
            allowed_sender_ids={"ou_member"},
        )

    async def test_group_human_instruction_is_dispatched_once_with_stable_revision(self):
        message = FakeMessage(raw={"update_time": "1780000000000"})
        self.assertTrue(await self.ingress.ingest(message))
        self.assertFalse(await self.ingress.ingest(message))
        self.assertEqual(len(self.controller.messages), 1)
        envelope = self.controller.messages[0]
        self.assertEqual(envelope.source, SourceKind.HUMAN)
        self.assertEqual(envelope.kind, MessageKind.HUMAN_INSTRUCTION)
        self.assertEqual(envelope.platform_group_id, "oc_team")
        self.assertEqual(envelope.payload["text"], "new FPGA task")
        self.assertTrue(envelope.payload["ownership_required"])

    async def test_edits_have_new_revision_and_stable_task_identity(self):
        original = FakeMessage(raw={"update_time": "1780000000000"})
        edited = FakeMessage(body_text="revised task", raw={"update_time": "1780000005000"})
        await self.ingress.ingest(original)
        await self.ingress.ingest(edited)
        self.assertEqual(len(self.controller.messages), 2)
        self.assertEqual(self.controller.messages[0].task_id, self.controller.messages[1].task_id)
        self.assertLess(self.controller.messages[0].revision, self.controller.messages[1].revision)

    async def test_foreign_group_bot_and_unknown_human_are_ignored(self):
        cases = [
            FakeMessage(chat_id="oc_other"),
            FakeMessage(sender_type="app"),
            FakeMessage(sender_id="ou_outsider"),
        ]
        for case in cases:
            self.assertFalse(await self.ingress.ingest(case))
        self.assertEqual(self.controller.messages, [])

    async def test_human_instruction_mentioning_any_bot_still_reaches_astra(self):
        message = FakeMessage(mentions=[FakeMention("ou_astra_b")])
        self.assertTrue(await self.ingress.ingest(message))
        self.assertEqual(self.controller.messages[0].recipient, "A/Astra-A")
        self.assertTrue(self.controller.messages[0].payload["ownership_required"])

    async def test_explicit_node_address_runs_only_on_that_node(self):
        message = FakeMessage(body_text="/fpga B inspect timing")
        self.assertFalse(await self.ingress.ingest(message))
        other_controller = RecordingController()
        other = FeishuIngress(node_id="B", project_id="fpga-main",
                              group_id="oc_team", app_id="cli_astra_b",
                              controller=other_controller)
        self.assertTrue(await other.ingest(message))
        self.assertFalse(other_controller.messages[0].payload["ownership_required"])

    async def test_mention_of_local_child_routes_to_parent_without_waking_child(self):
        message = FakeMessage(mentions=[FakeMention("ou_deepseek_a")])
        self.assertTrue(await self.ingress.ingest(message))
        self.assertEqual(self.controller.messages[0].recipient, "A/Astra-A")

    async def test_pause_command_is_deterministic_control_message(self):
        message = FakeMessage(body_text="/fpga pause")
        await self.ingress.ingest(message)
        self.assertEqual(self.controller.messages[0].kind, MessageKind.STOP_REQUEST)


class FeishuNodeServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_sdk_import_owns_loop_separate_from_controller(self):
        controller_loop = asyncio.get_running_loop()
        controller_thread = threading.get_ident()
        imported_on = []
        sdk_loop = None
        channels = []
        sdk = ModuleType("lark_channel")

        class SDKChannel(FakeChannel):
            def __init__(self, **kwargs):
                super().__init__()
                self.options = kwargs
                channels.append(self)

            async def disconnect(self):
                # Mirror the SDK's shutdown of its captured WS loop.
                if sdk_loop.is_running():
                    sdk_loop.call_soon_threadsafe(sdk_loop.stop)
                await super().disconnect()

        def sdk_attribute(name):
            nonlocal sdk_loop
            if name == "FeishuChannel":
                imported_on.append(threading.get_ident())
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("SDK imported on a running loop")
                if sdk_loop is None:
                    try:
                        sdk_loop = asyncio.get_event_loop()
                    except RuntimeError:
                        sdk_loop = asyncio.new_event_loop()
                return SDKChannel
            if name in {"PolicyConfig", "SecurityConfig"}:
                return lambda **kwargs: kwargs
            raise AttributeError(name)

        sdk.__getattr__ = sdk_attribute
        controller = RecordingController()
        with tempfile.TemporaryDirectory() as tmp:
            secret_file = Path(tmp) / "astra-secret.txt"
            secret_file.write_text("test-secret", encoding="utf-8")
            service = FeishuNodeService(
                node_id="B", project_id="fpga-main", group_id="oc_team",
                astra_app_id="cli_astra_b", astra_secret_file=secret_file,
                controller=controller,
            )
            try:
                with patch.dict(sys.modules, {"lark_channel": sdk}):
                    await service.start()
                    await service.start()
                self.assertTrue(imported_on)
                self.assertTrue(all(t != controller_thread for t in imported_on))
                self.assertIsNot(sdk_loop, controller_loop)
                self.assertEqual(len(channels), 1)
                channel = channels[0]
                self.assertEqual(channel.options["policy"], {
                    "dm_policy": "disabled", "group_policy": "allowlist",
                    "group_allowlist": ["oc_team"], "require_mention": False,
                })
                self.assertEqual(channel.options["security"], {"mode": "strict"})
                self.assertTrue(await channel.handlers["message"](FakeMessage()))
                self.assertEqual(len(controller.messages), 1)
                self.assertEqual(
                    await service.send_as_astra("status", operation_id="op-1"),
                    "om_sent",
                )
            finally:
                await service.stop()
                if sdk_loop is not None:
                    sdk_loop.close()
            await asyncio.sleep(0)
            self.assertTrue(controller_loop.is_running())
            self.assertFalse(channels[0].connected)

    async def test_injected_factory_does_not_load_optional_sdk(self):
        with tempfile.TemporaryDirectory() as tmp:
            secret_file = Path(tmp) / "astra-secret.txt"
            secret_file.write_text("test-secret", encoding="utf-8")
            channel = FakeChannel()
            service = FeishuNodeService(
                node_id="B", project_id="fpga-main", group_id="oc_team",
                astra_app_id="cli_astra_b", astra_secret_file=secret_file,
                controller=RecordingController(), channel_factory=lambda **_: channel,
            )
            with patch.object(
                feishu_channel, "_load_default_channel_factory",
                side_effect=AssertionError("unexpected optional SDK import"),
            ) as load_sdk:
                await service.start()
                await service.stop()
            load_sdk.assert_not_called()
            self.assertFalse(channel.connected)

    async def test_sdk_worker_delivers_message_on_controller_loop(self):
        owner_loop = asyncio.get_running_loop()

        class LoopCheckingController(RecordingController):
            async def offer(self, message):
                if asyncio.get_running_loop() is not owner_loop:
                    raise RuntimeError("controller called from SDK worker loop")
                return await super().offer(message)

        with tempfile.TemporaryDirectory() as tmp:
            secret_file = Path(tmp) / "astra-secret.txt"
            secret_file.write_text("test-secret", encoding="utf-8")
            channel = FakeChannel()
            controller = LoopCheckingController()
            service = FeishuNodeService(
                node_id="A", project_id="fpga-main", group_id="oc_team",
                astra_app_id="cli_astra_a", astra_secret_file=secret_file,
                controller=controller, channel_factory=lambda **_: channel,
            )
            await service.start()
            try:
                accepted = await asyncio.to_thread(
                    lambda: asyncio.run(channel.handlers["message"](FakeMessage()))
                )
                self.assertTrue(accepted)
                self.assertEqual(len(controller.messages), 1)
            finally:
                await service.stop()

    async def test_only_astra_channel_connects_and_sends_to_fixed_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            secret_file = Path(tmp) / "astra-secret.txt"
            secret_file.write_text("test-secret", encoding="utf-8")
            channels = []
            def factory(**kwargs):
                self.assertEqual(kwargs["app_id"], "cli_astra_a")
                self.assertEqual(kwargs["app_secret"], "test-secret")
                channel = FakeChannel()
                channels.append(channel)
                return channel

            service = FeishuNodeService(
                node_id="A", project_id="fpga-main", group_id="oc_team",
                astra_app_id="cli_astra_a", astra_secret_file=secret_file,
                controller=RecordingController(), channel_factory=factory,
            )
            await service.start()
            self.assertEqual(len(channels), 1)
            self.assertTrue(channels[0].connected)
            self.assertIn("message", channels[0].handlers)
            sent = await service.send_as_astra("status", operation_id="status-1")
            self.assertEqual(sent, "om_sent")
            self.assertEqual(channels[0].sent[0][0], "oc_team")
            await service.stop()
            self.assertFalse(channels[0].connected)

    async def test_persisted_report_is_sent_after_channel_connects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret_file = root / "secret.txt"
            secret_file.write_text("test-secret", encoding="utf-8")
            store = SQLiteStore(root / "state.sqlite")
            store.enqueue_group_report("op-1", "Astra-A completed task")
            channel = FakeChannel()
            service = FeishuNodeService(
                node_id="A", project_id="fpga-main", group_id="oc_team",
                astra_app_id="cli_astra_a", astra_secret_file=secret_file,
                controller=RecordingController(), channel_factory=lambda **_: channel,
                store=store,
            )
            await service.start()
            await service.flush_reports()
            self.assertEqual(store.pending_group_reports(), [])
            self.assertEqual(
                channel.sent[0][2]["uuid"],
                str(uuid.uuid5(uuid.NAMESPACE_URL, "cli_astra_a:op-1")),
            )
            await service.stop()
            store.close()

    async def test_failed_report_send_is_retried_without_model_work(self):
        class FlakyChannel(FakeChannel):
            def __init__(self):
                super().__init__()
                self.attempts = 0

            async def send(self, to, message, opts=None):
                self.attempts += 1
                if self.attempts == 1:
                    return type("Result", (), {"success": False, "message_id": None})()
                return await super().send(to, message, opts)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret_file = root / "secret.txt"
            secret_file.write_text("test-secret", encoding="utf-8")
            store = SQLiteStore(root / "state.sqlite")
            try:
                store.enqueue_group_report("op-retry", "retry this")
                channel = FlakyChannel()
                service = FeishuNodeService(
                    node_id="A", project_id="fpga-main", group_id="oc_team",
                    astra_app_id="cli_astra_a", astra_secret_file=secret_file,
                    controller=RecordingController(), channel_factory=lambda **_: channel,
                    store=store, retry_seconds=0.01,
                )
                await service.start()
                async def wait_until_sent():
                    while store.pending_group_reports():
                        await asyncio.sleep(0.01)
                await asyncio.wait_for(wait_until_sent(), timeout=1)
                self.assertEqual(channel.attempts, 2)
                await service.stop()
            finally:
                store.close()

    async def test_send_only_app_builds_real_sdk_request_without_connecting(self):
        with tempfile.TemporaryDirectory() as tmp:
            secret_file = Path(tmp) / "child.txt"
            secret_file.write_text("child-secret", encoding="utf-8")
            requests = []
            class FakeEndpoint:
                def create(self, request):
                    requests.append(request)
                    return type("Response", (), {
                        "success": lambda self: True,
                        "data": type("Data", (), {"message_id": "om_child"})(),
                    })()
            endpoint = FakeEndpoint()
            client = type("Client", (), {"im": type("Im", (), {
                "v1": type("V1", (), {"message": endpoint})(),
            })()})()
            sender = FeishuAppSender(
                app_id="cli_deepseek_a", secret_file=secret_file,
                client_factory=lambda app_id, secret: client,
            )
            sent_id = await sender.send("oc_team", "child result", "op-1")
            self.assertEqual(sent_id, "om_child")
            self.assertEqual(requests[0].receive_id_type, "chat_id")
            self.assertEqual(requests[0].request_body.receive_id, "oc_team")
            self.assertEqual(
                requests[0].request_body.uuid,
                str(uuid.uuid5(uuid.NAMESPACE_URL, "cli_deepseek_a:op-1")),
            )
            self.assertIn("child result", requests[0].request_body.content)

    async def test_deepseek_report_uses_send_only_app_without_group_subscription(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            astra_file = root / "astra.txt"
            child_file = root / "deepseek.txt"
            astra_file.write_text("astra-secret", encoding="utf-8")
            child_file.write_text("child-secret", encoding="utf-8")
            store = SQLiteStore(root / "state.sqlite")
            sent = []
            class FakeSender:
                async def send(self, group_id, text, operation_id):
                    sent.append((group_id, text, operation_id))
                    return "om_child"
            channel = FakeChannel()
            service = FeishuNodeService(
                node_id="A", project_id="fpga-main", group_id="oc_team",
                astra_app_id="cli_astra_a", astra_secret_file=astra_file,
                deepseek_app_id="cli_child_a", deepseek_secret_file=child_file,
                controller=RecordingController(), channel_factory=lambda **_: channel,
                deepseek_sender=FakeSender(), store=store,
            )
            try:
                store.enqueue_group_report("child-op", "child output", role="deepseek")
                await service.start()
                await service.flush_reports()
                self.assertEqual(sent, [("oc_team", "child output", "child-op")])
                self.assertEqual(len(channel.handlers), 1)
                self.assertEqual(store.pending_group_messages(), [])
            finally:
                await service.stop()
                store.close()

    async def test_unconfigured_deepseek_report_does_not_block_astra_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret_file = root / "astra.txt"
            secret_file.write_text("astra-secret", encoding="utf-8")
            store = SQLiteStore(root / "state.sqlite")
            channel = FakeChannel()
            service = FeishuNodeService(
                node_id="A", project_id="fpga-main", group_id="oc_team",
                astra_app_id="cli_astra_a", astra_secret_file=secret_file,
                controller=RecordingController(), channel_factory=lambda **_: channel,
                store=store,
            )
            try:
                store.enqueue_group_report("child-op", "waiting", role="deepseek")
                store.enqueue_group_report("astra-op", "critical update")
                await service.start()
                with self.assertRaisesRegex(RuntimeError, "DeepSeek Feishu sender"):
                    await service.flush_reports()
                self.assertEqual(len(channel.sent), 1)
                self.assertEqual(channel.sent[0][1]["text"], "critical update")
                self.assertEqual(len(store.pending_group_messages()), 1)
                self.assertEqual(store.pending_group_messages()[0][0], "child-op")
            finally:
                await service.stop()
                store.close()

    async def test_stale_child_report_is_cancelled_before_reconnect_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret_file = root / "astra.txt"
            secret_file.write_text("astra-secret", encoding="utf-8")
            store = SQLiteStore(root / "state.sqlite")
            sent = []
            class FakeSender:
                async def send(self, group_id, text, operation_id):
                    sent.append(operation_id)
                    return "om_child"
            service = FeishuNodeService(
                node_id="A", project_id="fpga-main", group_id="oc_team",
                astra_app_id="cli_astra_a", astra_secret_file=secret_file,
                controller=RecordingController(), channel_factory=lambda **_: FakeChannel(),
                deepseek_sender=FakeSender(), store=store,
                job_lookup=lambda job_id: {"job_id": job_id, "stale": True,
                                           "status": "completed"},
            )
            try:
                store.enqueue_group_report("stale-op", "old child output",
                                           role="deepseek", job_id="child-1")
                await service.start()
                await service.flush_reports()
                self.assertEqual(sent, [])
                self.assertEqual(store.pending_group_messages(), [])
                self.assertEqual(store.group_report_status("stale-op"), "cancelled")
            finally:
                await service.stop()
                store.close()


if __name__ == "__main__":
    unittest.main()
