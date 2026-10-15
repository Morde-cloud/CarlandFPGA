import tempfile
import unittest
import sys
import os
import asyncio
from unittest.mock import patch
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fpga_mesh.runtime import NodeConfig, NodeRuntime
from fpga_mesh.controller import ActionResult
from fpga_mesh.child_control import LocalControlClient
from fpga_mesh.protocol import Envelope, MessageKind, SourceKind


class NodeRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config_path = self.root / "node-a.toml"
        self.config_path.write_text(
            "\n".join(
                [
                    'node_id = "A"',
                    'project_id = "fpga-main"',
                    'state_dir = "state"',
                    "default_children = 2",
                    'mode = "test_double"',
                    "hardware_enabled = false",
                    "[peers]",
                    'B = ""',
                    'C = ""',
                    "[security]",
                    'secret_env = "FPGA_MESH_SHARED_SECRET"',
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_runtime_ignores_legacy_default_children_and_starts_on_demand(self):
        config = NodeConfig.load(self.config_path)
        runtime = NodeRuntime(config)
        await runtime.start()
        snapshot = runtime.snapshot()
        self.assertEqual(snapshot["node_id"], "A")
        self.assertEqual(len(snapshot["pool"]["instances"]), 0)
        self.assertEqual(snapshot["pending_inbound"], 0)
        self.assertEqual(snapshot["idle_model_calls"], 0)
        await runtime.stop()

    async def test_parent_tool_bridge_reaches_runtime_child_pool(self):
        runtime = NodeRuntime(NodeConfig.load(self.config_path))
        await runtime.start()
        try:
            client = LocalControlClient(
                host="127.0.0.1", port=runtime.child_control.port,
                token=runtime.child_control.token,
            )
            assigned = await client.call("delegate", {
                "task_id": "fpga-test", "task_version": 1,
                "text": "inspect constraints",
            })
            results = await client.call("wait", {"job_ids": [assigned["job_id"]]})
            self.assertEqual(results[0]["status"], "completed")
            self.assertEqual(results[0]["instance_id"], assigned["instance_id"])
            self.assertEqual(runtime.snapshot()["pool"]["standby"], 1)
        finally:
            await runtime.stop()

    async def test_live_parent_config_advertises_local_mcp_and_uses_chatgpt_home(self):
        config = NodeConfig.load(self.config_path)
        runtime = NodeRuntime(config)
        await runtime.start()
        try:
            config_values = runtime.astra_tool_config()
            self.assertEqual(config_values["approval_policy"], "never")
            self.assertEqual(config_values["sandbox_mode"], "danger-full-access")
            mcp = config_values["mcp_servers"]["fpga_children"]
            self.assertEqual(mcp["command"], sys.executable)
            self.assertEqual(mcp["args"], ["-m", "fpga_mesh.mcp_children"])
            self.assertEqual(mcp["env"]["FPGA_CHILD_CONTROL_FILE"],
                             str(config.state_dir / "child-control.json"))
            self.assertNotIn("DEEPSEEK_API_KEY", mcp["env"])
            self.assertEqual(
                {tool["name"] for tool in runtime.dynamic_children.specs()},
                {"fpga_child_status", "fpga_child_scale", "fpga_child_delegate",
                 "fpga_child_wait", "fpga_child_cancel", "fpga_native_reserve",
                 "fpga_native_validate", "fpga_native_complete"},
            )
            self.assertIn(
                "fpga_peer_send",
                {tool["name"] for tool in runtime.mesh_tools.specs()},
            )
        finally:
            await runtime.stop()

    async def test_new_human_task_version_invalidates_old_child_assignment(self):
        runtime = NodeRuntime(NodeConfig.load(self.config_path))
        await runtime.start()
        try:
            first = await runtime.children.delegate(
                task_id="new-plan", task_version=1, text="old work",
            )
            await runtime.children.wait([first["job_id"]])
            await runtime.controller.offer(Envelope(
                message_id="human-new-plan", project_id="fpga-main",
                sender="human", recipient="A/Astra-A",
                task_id="new-plan", task_version=2,
                sent_at=datetime.now(timezone.utc),
                kind=MessageKind.HUMAN_INSTRUCTION,
                source=SourceKind.HUMAN, payload={"text": "new plan"},
            ))
            self.assertTrue(runtime.children.job(first["job_id"])["stale"])
            with self.assertRaisesRegex(ValueError, "stale"):
                await runtime.children.delegate(
                    task_id="new-plan", task_version=1, text="obsolete",
                )
        finally:
            await runtime.stop()

    async def test_real_parent_and_child_have_finite_turn_watchdogs(self):
        config = replace(NodeConfig.load(self.config_path), mode="app_server",
                         turn_timeout_seconds=1800)
        runtime = NodeRuntime(config)
        try:
            self.assertEqual(runtime.astra_gateway.timeout_seconds, 1800)
            await runtime.pool.ensure_standby(1)
            child = runtime.pool.snapshot()["instances"][0]
            gateway = runtime._make_child_gateway(
                runtime.pool._active[child["instance_id"]]
            )
            self.assertEqual(gateway.timeout_seconds, 1800)
            self.assertEqual(gateway.thread_config_factory()['approval_policy'], 'never')
            self.assertEqual(gateway.thread_config_factory()['sandbox_mode'], 'danger-full-access')
        finally:
            await runtime.stop()

    async def test_feishu_config_and_result_queue_do_not_require_network_at_load(self):
        secret_file = self.root / "astra-secret.txt"
        secret_file.write_text("test-secret", encoding="utf-8")
        with self.config_path.open("a", encoding="utf-8") as config:
            config.write(
                '\n[feishu]\nenabled = true\ngroup_id = "oc_team"\n'
                'astra_app_id = "cli_astra_a"\n'
                f'astra_secret_file = "{secret_file.as_posix()}"\n'
                'deepseek_app_id = "cli_deepseek_a"\n'
                'allowed_user_ids = ["ou_member"]\n'
                'local_bot_open_ids = ["ou_astra_a", "ou_deepseek_a"]\n'
            )
        config = NodeConfig.load(self.config_path)
        self.assertTrue(config.feishu_enabled)
        self.assertEqual(config.feishu_group_id, "oc_team")
        runtime = NodeRuntime(config)
        try:
            self.assertIsNotNone(runtime.feishu)
            runtime._on_result(
                Envelope(
                    message_id="human-1", project_id="fpga-main", sender="ou_member",
                    recipient="A/Astra-A", task_id="task-1", task_version=1,
                    sent_at=datetime.now(timezone.utc),
                    kind=MessageKind.HUMAN_INSTRUCTION,
                    source=SourceKind.HUMAN, payload={"text": "work"},
                ),
                ActionResult(accepted=True, output={"text": "done"}),
            )
            self.assertEqual(len(runtime.store.pending_group_reports()), 1)
            self.assertIn("done", runtime.store.pending_group_reports()[0][1])
        finally:
            await runtime.stop()

    async def test_peer_outbox_recovers_when_other_node_comes_online(self):
        base = NodeConfig.load(self.config_path)
        a_config = replace(
            base, node_id="A", state_dir=self.root / "a-state",
            peer_urls={"B": "http://127.0.0.1:9"},
            peer_bind_host="127.0.0.1", peer_bind_port=0,
            peer_retry_seconds=0.02,
        )
        b_config = replace(
            base, node_id="B", state_dir=self.root / "b-state",
            peer_urls={}, peer_bind_host="127.0.0.1",
            peer_bind_port=0, peer_retry_seconds=0.02,
        )
        with patch.dict(os.environ, {"FPGA_MESH_SHARED_SECRET": "test-only-key"}):
            a = NodeRuntime(a_config)
            b = NodeRuntime(b_config)
            await a.start()
            try:
                message = Envelope(
                    message_id="a-to-b", project_id="fpga-main",
                    sender="A/Astra-A", recipient="B/Astra-B",
                    task_id="test-peer", task_version=1,
                    sent_at=datetime.now(timezone.utc),
                    kind=MessageKind.AGENT_REPORT, source=SourceKind.ASTRA,
                    payload={"text": "continue without A"},
                )
                self.assertFalse(await a.peer.send("B", message))
                self.assertEqual(len(a.store.pending_outbound()), 1)
                await b.start()
                a.peer.peer_urls["B"] = f"http://127.0.0.1:{b.peer_server.port}"
                async def delivered():
                    while a.store.pending_outbound():
                        await asyncio.sleep(0.02)
                try:
                    await asyncio.wait_for(delivered(), timeout=8)
                except TimeoutError:
                    self.fail(
                        f"pending={a.store.pending_outbound()} "
                        f"b_pending={b.store.pending_inbound()} "
                        f"peer_error={a.peer_error} b_port={b.peer_server.port}"
                    )
                await b.controller.run_until_idle()
                self.assertIn("a-to-b", b.astra_gateway.calls)
            finally:
                await a.stop()
                await b.stop()

    async def test_peer_secret_file_enables_inbound_service_without_environment_secret(self):
        secret_file = self.root / "mesh-secret.txt"
        secret_file.write_text("test-only-shared-secret", encoding="utf-8")
        config = replace(
            NodeConfig.load(self.config_path),
            peer_shared_secret_file=secret_file, peer_bind_port=0,
        )
        with patch.dict(os.environ, {"FPGA_MESH_SHARED_SECRET": ""}):
            runtime = NodeRuntime(config)
            await runtime.start()
            try:
                self.assertTrue(runtime.snapshot()["network_enabled"])
                self.assertGreater(runtime.snapshot()["peer_listen_port"], 0)
            finally:
                await runtime.stop()

    async def test_quota_warning_is_queued_once_without_a_model_turn(self):
        secret_file = self.root / "astra-secret.txt"
        secret_file.write_text("test-secret", encoding="utf-8")
        config = replace(
            NodeConfig.load(self.config_path),
            feishu_enabled=True, feishu_group_id="oc_team",
            feishu_astra_app_id="cli_astra_a",
            feishu_astra_secret_file=secret_file,
        )
        runtime = NodeRuntime(config)
        try:
            response = {"ordinaryUsageAllowed": True,
                        "rateLimitsByLimitId": {"core": {
                            "limitId": "core", "limitName": "Codex",
                            "spendControlReached": False,
                            "primary": {"usedPercent": 91,
                                        "windowDurationMins": 300,
                                        "resetsAt": 1780000000},
                        }}}
            runtime._observe_quota(response)
            runtime._observe_quota(response)
            reports = runtime.store.pending_group_reports()
            self.assertEqual(len(reports), 2)
            self.assertTrue(all("remaining 9%" in report[1] for report in reports))
            self.assertEqual(runtime.snapshot()["idle_model_calls"], 0)
        finally:
            await runtime.stop()

    async def test_peer_presence_changes_queue_human_status_without_model_turn(self):
        secret_file = self.root / "astra-secret.txt"
        secret_file.write_text("test-secret", encoding="utf-8")
        config = replace(
            NodeConfig.load(self.config_path),
            feishu_enabled=True, feishu_group_id="oc_team",
            feishu_astra_app_id="cli_astra_a",
            feishu_astra_secret_file=secret_file,
            peer_urls={"B": "http://127.0.0.1:8787"},
        )
        runtime = NodeRuntime(config)
        try:
            runtime._note_peer_status("B", True)
            runtime._note_peer_status("B", True)
            runtime._note_peer_status("B", False)
            self.assertEqual(runtime.snapshot()["peer_presence"]["B"], False)
            reports = runtime.store.pending_group_reports()
            self.assertEqual(len(reports), 2)
            self.assertIn("上线", reports[0][1])
            self.assertIn("离线", reports[1][1])
            self.assertEqual(runtime.snapshot()["idle_model_calls"], 0)
        finally:
            await runtime.stop()

    async def test_failed_peer_bind_cleans_child_discovery(self):
        occupied = await asyncio.start_server(
            lambda _reader, _writer: None, "127.0.0.1", 0,
        )
        port = occupied.sockets[0].getsockname()[1]
        config = replace(
            NodeConfig.load(self.config_path),
            peer_bind_port=port,
        )
        try:
            with patch.dict(os.environ, {"FPGA_MESH_SHARED_SECRET": "test-key"}):
                runtime = NodeRuntime(config)
                with self.assertRaises(OSError):
                    await runtime.start()
            self.assertFalse(
                (config.state_dir / "child-control.json").exists()
            )
        finally:
            occupied.close()
            await occupied.wait_closed()


if __name__ == "__main__":
    unittest.main()
