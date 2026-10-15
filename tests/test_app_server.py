import unittest
import tempfile
from pathlib import Path

from fpga_mesh.app_server import (AppServerClient, build_codex_env,
                                 resolve_codex_command, pin_codex_bundle)


class FakeSession:
    def __init__(self):
        self.requests = []

    async def request(self, method, params=None):
        self.requests.append((method, params or {}))
        return {"ok": method}

    async def notify(self, method, params=None):
        self.requests.append((method, params or {}))

    async def close(self):
        self.requests.append(("close", {}))


class AppServerClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = FakeSession()
        self.client = AppServerClient(self.session, client_version="0.159.0")

    async def test_initialize_declares_client_and_experimental_capability(self):
        await self.client.initialize()
        method, params = self.session.requests[0]
        self.assertEqual(method, "initialize")
        self.assertEqual(params["clientInfo"]["name"], "fpga-mesh")
        self.assertEqual(params["clientInfo"]["version"], "0.159.0")
        self.assertTrue(params["capabilities"]["experimentalApi"])

    async def test_thread_and_turn_keep_model_provider_and_max_effort(self):
        await self.client.thread_start(
            cwd="C:/workspace",
            model="deepseek-flash",
            model_provider="deepseek",
        )
        await self.client.turn_start(
            thread_id="thread-1",
            text="inspect",
            model="deepseek-flash",
            effort="max",
        )

        start_method, start_params = self.session.requests[0]
        turn_method, turn_params = self.session.requests[1]
        self.assertEqual(start_method, "thread/start")
        self.assertEqual(start_params["model"], "deepseek-flash")
        self.assertEqual(start_params["modelProvider"], "deepseek")
        self.assertEqual(turn_method, "turn/start")
        self.assertEqual(turn_params["model"], "deepseek-flash")
        self.assertEqual(turn_params["effort"], "max")
        self.assertEqual(turn_params["input"], [{"type": "text", "text": "inspect"}])

    async def test_rate_limit_read_uses_the_official_method_and_empty_params(self):
        await self.client.account_rate_limits()
        self.assertEqual(
            self.session.requests[0],
            ("account/rateLimits/read", {}),
        )

    async def test_turn_interrupt_targets_the_active_turn(self):
        await self.client.turn_interrupt(thread_id="thread-1", turn_id="turn-1")
        self.assertEqual(self.session.requests[0], (
            "turn/interrupt", {"threadId": "thread-1", "turnId": "turn-1"},
        ))

    async def test_parent_thread_can_register_local_child_tools(self):
        overrides = {"mcp_servers": {"fpga_children": {
            "command": "python", "args": ["-m", "fpga_mesh.mcp_children"],
        }}}
        await self.client.thread_start(
            cwd="C:/workspace", model="gpt-6-astra", model_provider="openai",
            config=overrides,
        )
        self.assertEqual(self.session.requests[0][1]["config"], overrides)

    async def test_parent_thread_can_register_dynamic_tools(self):
        tools = [{"type": "function", "name": "fpga_child_status",
                  "description": "status", "inputSchema": {"type": "object"}}]
        await self.client.thread_start(
            cwd="C:/workspace", model="gpt-6-astra", model_provider="openai",
            dynamic_tools=tools,
        )
        self.assertEqual(self.session.requests[0][1]["dynamicTools"], tools)

    async def test_parent_environment_never_inherits_deepseek_key(self):
        source = {"DEEPSEEK_API_KEY": "a-secret", "OPENAI_API_KEY": "other",
                  "CODEX_API_KEY": "another", "SAFE": "kept"}
        astra = build_codex_env("C:/astra", source=source,
                                role="astra", extra={"CONTROL": "present"})
        child = build_codex_env("C:/child", source=source,
                                role="deepseek_child", extra={"DEEPSEEK_API_KEY": "new"})
        self.assertNotIn("DEEPSEEK_API_KEY", astra)
        self.assertEqual(astra["CONTROL"], "present")
        self.assertEqual(child["DEEPSEEK_API_KEY"], "new")
        self.assertNotIn("OPENAI_API_KEY", child)
        self.assertNotIn("CODEX_API_KEY", child)

    async def test_extra_environment_cannot_reintroduce_cross_role_credentials(self):
        astra = build_codex_env(
            "C:/astra", source={}, role="astra",
            extra={"DEEPSEEK_API_KEY": "forbidden", "CODEX_HOME": "wrong"},
        )
        child = build_codex_env(
            "C:/child", source={}, role="deepseek_child",
            extra={"OPENAI_API_KEY": "forbidden", "CODEX_API_KEY": "forbidden"},
        )
        self.assertNotIn("DEEPSEEK_API_KEY", astra)
        self.assertEqual(astra["CODEX_HOME"], "C:/astra")
        self.assertNotIn("OPENAI_API_KEY", child)
        self.assertNotIn("CODEX_API_KEY", child)

    async def test_old_endpoint_environment_cannot_redirect_official_or_child_routes(self):
        source = {'OPENAI_BASE_URL': 'http://127.0.0.1:12345/v1',
                  'CODEX_BACKEND_BASE_URL': 'http://127.0.0.1:12345', 'SAFE': 'kept'}
        for role in ('astra', 'deepseek_child'):
            env = build_codex_env('home', source=source, role=role,
                                  extra={'CHATGPT_BASE_URL': 'http://127.0.0.1:12345'})
            self.assertNotIn('OPENAI_BASE_URL', env)
            self.assertNotIn('CODEX_BACKEND_BASE_URL', env)
            self.assertNotIn('CHATGPT_BASE_URL', env)
            self.assertEqual(env['SAFE'], 'kept')

    async def test_codex_binary_prefers_bundled_host_over_broken_npm_shim(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "OpenAI" / "Codex" / "bin" / "release"
            bundle.mkdir(parents=True)
            (bundle / "codex.exe").touch()
            (bundle / "codex-code-mode-host.exe").touch()
            command = resolve_codex_command(
                platform="win32", local_appdata=tmp, explicit=None,
            )
            self.assertEqual(command, [str(bundle / "codex.exe"),
                                       "app-server", "--stdio"])

    async def test_pinned_runtime_survives_desktop_bundle_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "desktop"
            source.mkdir()
            (source / "codex.exe").write_bytes(b"official-codex")
            (source / "codex-code-mode-host.exe").write_bytes(b"matching-host")
            (source / "codex-command-runner.exe").write_bytes(b"runner")
            pinned = pin_codex_bundle(source / "codex.exe", Path(tmp) / "state")
            (source / "codex-code-mode-host.exe").unlink()
            self.assertEqual(pinned.read_bytes(), b"official-codex")
            self.assertEqual((pinned.parent / "codex-code-mode-host.exe").read_bytes(), b"matching-host")
            self.assertEqual((pinned.parent / "codex-command-runner.exe").read_bytes(), b"runner")

    async def test_changed_cached_runtime_is_rejected_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "desktop"
            source.mkdir()
            (source / "codex.exe").write_bytes(b"official")
            (source / "codex-code-mode-host.exe").write_bytes(b"host")
            pinned = pin_codex_bundle(source / "codex.exe", Path(tmp) / "state")
            host = pinned.parent / "codex-code-mode-host.exe"
            host.write_bytes(b"damaged")
            with self.assertRaisesRegex(RuntimeError, "incomplete or changed"):
                pin_codex_bundle(source / "codex.exe", Path(tmp) / "state")
            self.assertEqual(host.read_bytes(), b"damaged")


if __name__ == "__main__":
    unittest.main()
