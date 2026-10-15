"""Node runtime wiring for a local controller process."""

from __future__ import annotations

import asyncio
import os
import secrets
import sys
import tomllib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .app_server import AppServerClient
from .agent_policy import astra_instructions, child_instructions
from .child_control import ChildCoordinator, LocalControlFileClient, LocalControlServer
from .codex import CodexHomeFactory, CodexHomeSpec
from .controller import Controller
from .dynamic_children import ChildDynamicTools
from .feishu_channel import FeishuNodeService
from .gateway import AppServerGateway, GatewayConfig
from .hardware import HardwareService
from .http_transport import HttpPeer, HttpPeerServer
from .mesh_tools import MeshDynamicTools
from .models_ui import ModelsHttpServer
from .ownership import GitOwnershipLedger
from .pool import InstancePool, ManagedInstance
from .sessions import MainSessionRouter
from .project_control import ProjectActions, ProjectControlServer
from .quota import QuotaMonitor
from .store import SQLiteStore
from .testing import RecordingGateway


@dataclass(frozen=True, slots=True)
class NodeConfig:
    node_id: str
    project_id: str
    state_dir: Path
    mode: str
    hardware_enabled: bool
    peer_urls: dict[str, str]
    shared_secret_env: str
    peer_shared_secret_file: Path | None = None
    deepseek_key_file: Path | None = None
    turn_timeout_seconds: float = 3600.0
    feishu_enabled: bool = False
    feishu_group_id: str = ""
    feishu_astra_app_id: str = ""
    feishu_astra_secret_file: Path | None = None
    feishu_deepseek_app_id: str = ""
    feishu_deepseek_secret_file: Path | None = None
    feishu_allowed_user_ids: tuple[str, ...] = ()
    feishu_local_bot_open_ids: tuple[str, ...] = ()
    coordination_remote_url: str = "https://github.com/carolwjade/CarlandFPGA.git"
    peer_bind_host: str = "127.0.0.1"
    peer_bind_port: int = 8787
    peer_retry_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.turn_timeout_seconds <= 0:
            raise ValueError("turn_timeout_seconds must be positive")
        if self.feishu_enabled and not (
            self.feishu_group_id and self.feishu_astra_app_id
            and self.feishu_astra_secret_file is not None
        ):
            raise ValueError("enabled Feishu needs group ID and Astra app credentials")
        if not 0 <= self.peer_bind_port <= 65535:
            raise ValueError("peer_bind_port must be a TCP port")
        if self.peer_retry_seconds <= 0:
            raise ValueError("peer_retry_seconds must be positive")

    @classmethod
    def load(cls, path: str | Path) -> "NodeConfig":
        config_path = Path(path)
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        node_id = str(data["node_id"])
        if node_id not in {"A", "B", "C"}:
            raise ValueError("node_id must be A, B, or C")
        state_dir = Path(data.get("state_dir", f".local/node-{node_id.lower()}"))
        if not state_dir.is_absolute():
            state_dir = config_path.parent / state_dir
        key_file = data.get("deepseek_key_file")
        if key_file:
            key_file = Path(key_file)
            if not key_file.is_absolute():
                key_file = config_path.parent / key_file
        else:
            key_file = None
        feishu_data = data.get("feishu", {})
        security_data = data.get("security", {})
        secret_file = security_data.get("secret_file")
        if secret_file:
            secret_file = Path(str(secret_file))
            if not secret_file.is_absolute():
                secret_file = config_path.parent / secret_file
        else:
            secret_file = None
        def feishu_path(key: str) -> Path | None:
            value = feishu_data.get(key)
            if not value:
                return None
            result = Path(str(value))
            return result if result.is_absolute() else config_path.parent / result
        return cls(
            node_id=node_id,
            project_id=str(data.get("project_id", "fpga-main")),
            state_dir=state_dir,
            mode=str(data.get("mode", "test_double")),
            hardware_enabled=bool(data.get("hardware_enabled", False)),
            peer_urls={
                str(key): str(value)
                for key, value in data.get("peers", {}).items()
                if value
            },
            shared_secret_env=str(
                security_data.get(
                    "secret_env",
                    "FPGA_MESH_SHARED_SECRET",
                )
            ),
            peer_shared_secret_file=secret_file,
            deepseek_key_file=key_file,
            turn_timeout_seconds=float(data.get("turn_timeout_seconds", 3600)),
            feishu_enabled=bool(feishu_data.get("enabled", False)),
            feishu_group_id=str(feishu_data.get("group_id", "")),
            feishu_astra_app_id=str(feishu_data.get("astra_app_id", "")),
            feishu_astra_secret_file=feishu_path("astra_secret_file"),
            feishu_deepseek_app_id=str(feishu_data.get("deepseek_app_id", "")),
            feishu_deepseek_secret_file=feishu_path("deepseek_secret_file"),
            feishu_allowed_user_ids=tuple(
                str(item) for item in feishu_data.get("allowed_user_ids", [])
            ),
            feishu_local_bot_open_ids=tuple(
                str(item) for item in feishu_data.get("local_bot_open_ids", [])
            ),
            coordination_remote_url=str(data.get("coordination", {}).get(
                "remote_url", "https://github.com/carolwjade/CarlandFPGA.git"
            )),
            peer_bind_host=str(security_data.get("bind_host", "127.0.0.1")),
            peer_bind_port=int(security_data.get("bind_port", 8787)),
            peer_retry_seconds=float(security_data.get("retry_seconds", 30)),
        )


class NodeRuntime:
    def __init__(self, config: NodeConfig):
        self.config = config
        self.store = SQLiteStore(config.state_dir / "state.sqlite")
        self.main_sessions = MainSessionRouter(config.state_dir / 'main_sessions.sqlite')
        self._recording_gateways: list[RecordingGateway] = []
        self.dynamic_children = ChildDynamicTools(LocalControlFileClient(
            config.state_dir / "child-control.json",
        ))
        self.astra_gateway = self._build_astra_gateway()
        self.ownership = (
            GitOwnershipLedger(
                remote_url=config.coordination_remote_url,
                scratch_root=config.state_dir / "coordination-scratch",
            ) if config.feishu_enabled else None
        )
        self.controller = Controller(
            self.store, self.astra_gateway,
            on_human_instruction=self._on_human_instruction,
            on_result=self._on_result,
            claim_ownership=self._claim_ownership,
        )
        self.feishu: FeishuNodeService | None = (
            FeishuNodeService(
                node_id=config.node_id, project_id=config.project_id,
                group_id=config.feishu_group_id,
                astra_app_id=config.feishu_astra_app_id,
                astra_secret_file=config.feishu_astra_secret_file,
                deepseek_app_id=config.feishu_deepseek_app_id,
                deepseek_secret_file=config.feishu_deepseek_secret_file,
                controller=self.controller, store=self.store,
                allowed_sender_ids=(
                    set(config.feishu_allowed_user_ids)
                    if config.feishu_allowed_user_ids else None
                ),
                local_bot_open_ids=set(config.feishu_local_bot_open_ids),
                job_lookup=lambda job_id: self.children.job(job_id),
            ) if config.feishu_enabled else None
        )
        self._feishu_task: asyncio.Task | None = None
        self._feishu_stop = asyncio.Event()
        self.feishu_error: str | None = None
        self._quota_monitor = QuotaMonitor()
        self._quota_task: asyncio.Task | None = None
        self._quota_stop = asyncio.Event()
        self.quota_error: str | None = None
        self.pool = InstancePool(
            node_id=config.node_id,
            gateway=None,
            gateway_factory=(
                self._make_recording_child_gateway
                if config.mode == "test_double"
                else self._make_child_gateway
            ),
            home_factory=CodexHomeFactory(config.state_dir / "homes"),
            state_path=config.state_dir / "pool.json",
        )
        self.children = ChildCoordinator(
            node_id=config.node_id,
            project_id=config.project_id,
            pool=self.pool,
            state_path=config.state_dir / "child_jobs.sqlite",
        )
        self.child_control = LocalControlServer(
            self.children, token=secrets.token_urlsafe(32),
            discovery_path=config.state_dir / "child-control.json",
        )
        self.project_actions = ProjectActions(self)
        self.main_control = ProjectControlServer(self.project_actions, discovery_path=config.state_dir / 'main-control.json')
        self.models_ui = ModelsHttpServer(self.project_actions, discovery_path=config.state_dir / 'model-manager.json')
        self.hardware = (
            HardwareService(config.state_dir / "hardware.sqlite")
            if config.hardware_enabled
            else None
        )
        self.peer: HttpPeer | None = None
        self.peer_server: HttpPeerServer | None = None
        self._peer_retry_task: asyncio.Task | None = None
        self._peer_stop = asyncio.Event()
        self.peer_error: str | None = None
        self._peer_presence: dict[str, bool | None] = {
            peer_id: None for peer_id in config.peer_urls
        }
        shared_secret = os.environ.get(config.shared_secret_env, "").strip()
        if not shared_secret and config.peer_shared_secret_file is not None:
            shared_secret = config.peer_shared_secret_file.read_text(
                encoding="utf-8-sig",
            ).strip()
        if shared_secret:
            self.peer = HttpPeer(
                node_id=config.node_id,
                project_id=config.project_id,
                store=self.store,
                controller=self.controller,
                peer_urls=config.peer_urls,
                shared_secret=shared_secret,
            )
            self.peer_server = HttpPeerServer(
                self.peer,
                shared_secret=shared_secret,
                host=config.peer_bind_host, port=config.peer_bind_port,
            )
        self.mesh_tools = MeshDynamicTools(
            node_id=config.node_id, project_id=config.project_id,
            child_tools=self.dynamic_children, children=self.children,
            store=self.store, peer=self.peer, feishu=self.feishu,
        )
        if isinstance(self.astra_gateway, AppServerGateway):
            self.astra_gateway.dynamic_tools = self.mesh_tools.specs() + self.project_actions.specs()
            self.astra_gateway.dynamic_tool_handler = self._call_main_tool
        self.started = False

    async def start(self) -> None:
        try:
            # Retire old idle defaults; allocations now occur only for assignments.
            await self.pool.scale_to(0)
            await self.child_control.start()
            await self.main_control.start()
            await self.models_ui.start()
            if self.peer_server is not None:
                await self.peer_server.start()
                self._peer_stop.clear()
                self._peer_retry_task = asyncio.create_task(
                    self._run_peer_retry(), name=f"fpga-peer-{self.config.node_id}",
                )
            await self.controller.start()
            if self.feishu is not None:
                self._feishu_stop.clear()
                self._feishu_task = asyncio.create_task(
                    self._run_feishu(), name=f"fpga-feishu-{self.config.node_id}",
                )
                if isinstance(self.astra_gateway, AppServerGateway):
                    self._quota_stop.clear()
                    self._quota_task = asyncio.create_task(
                        self._run_quota_monitor(),
                        name=f"fpga-quota-{self.config.node_id}",
                    )
            self.started = True
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        self.started = False
        self._peer_stop.set()
        if self._peer_retry_task is not None:
            self._peer_retry_task.cancel()
            try:
                await self._peer_retry_task
            except asyncio.CancelledError:
                pass
            self._peer_retry_task = None
        self._feishu_stop.set()
        self._quota_stop.set()
        if self._quota_task is not None:
            self._quota_task.cancel()
            try:
                await self._quota_task
            except asyncio.CancelledError:
                pass
            self._quota_task = None
        if self._feishu_task is not None:
            self._feishu_task.cancel()
            try:
                await self._feishu_task
            except asyncio.CancelledError:
                pass
            self._feishu_task = None
        if self.feishu is not None:
            await self.feishu.stop()
        await self.controller.stop()
        await self.models_ui.close()
        await self.child_control.close()
        await self.main_control.close()
        await self.children.close()
        await self.pool.close()
        if isinstance(self.astra_gateway, AppServerGateway):
            await self.astra_gateway.close()
        if self.peer_server is not None:
            await self.peer_server.close()
        if self.hardware is not None:
            self.hardware.close()
        self.store.close()
        self.main_sessions.close()

    def snapshot(self) -> dict[str, Any]:
        return {
            "node_id": self.config.node_id,
            "project_id": self.config.project_id,
            "mode": self.config.mode,
            "started": self.started,
            "pool": self.pool.snapshot(),
            "child_jobs": self.children.status()["jobs"],
            "pending_inbound": len(self.store.pending_inbound()),
            "pending_outbox": len(self.store.pending_outbound()),
            "idle_model_calls": sum(
                len(gateway.calls) for gateway in self._recording_gateways
            ),
            "network_enabled": self.peer is not None,
            "peer_listen_port": (
                self.peer_server.port if self.peer_server and self.started else None
            ),
            "peer_error": self.peer_error,
            "peer_presence": dict(self._peer_presence),
            "feishu_enabled": self.feishu is not None,
            "feishu_connected": bool(self.feishu and self.feishu.connected),
            "feishu_error": self.feishu_error,
            "quota_error": self.quota_error,
            "hardware_enabled": self.hardware is not None,
            "hardware_queue": self.hardware.queue() if self.hardware else [],
        }

    def astra_tool_config(self) -> dict[str, Any]:
        if self.child_control.port is None:
            raise RuntimeError("child control is not started")
        project_root = Path(__file__).resolve().parent.parent
        # The resident has no interactive approval UI. Match this node's
        # authorized local execution profile instead of inheriting a desktop
        # on-request setting and silently waiting for an absent approver.
        return {"approval_policy": "never", "sandbox_mode": "danger-full-access",
                "mcp_servers": {"fpga_children": {
            "command": sys.executable,
            "args": ["-m", "fpga_mesh.mcp_children"],
            "env": {
                "FPGA_CHILD_CONTROL_FILE": str(
                    self.config.state_dir / "child-control.json"
                ),
                "PYTHONPATH": str(project_root),
            },
            "startup_timeout_sec": 20,
            "tool_timeout_sec": 3600,
        }}}

    def _build_astra_gateway(self):
        if self.config.mode == "test_double":
            gateway = RecordingGateway()
            self._recording_gateways.append(gateway)
            return gateway
        return AppServerGateway(
            GatewayConfig(
                node_id=self.config.node_id,
                role="astra",
                model="gpt-6-astra",
                provider="openai",
                reasoning_effort="max",
                cwd=str(Path.cwd()),
                codex_home=str(Path.home() / ".codex"),
            ),
            client_factory=lambda: AppServerClient.start_stdio(
                codex_home=Path.home() / ".codex",
                client_version="0.159.0",
                role="astra",
                runtime_cache_dir=self.config.state_dir / "codex-runtime",
            ),
            thread_config_factory=self.astra_tool_config,
            dynamic_tools=self.dynamic_children.specs(),
            dynamic_tool_handler=self.dynamic_children.call,
            developer_instructions=astra_instructions(self.config.node_id),
            session_router=self.main_sessions,
            timeout_seconds=self.config.turn_timeout_seconds,
        )

    def _make_child_gateway(self, instance: ManagedInstance):
        gateway = AppServerGateway(
            GatewayConfig(
                node_id=self.config.node_id,
                role="deepseek_child",
                model=instance.model,
                provider="deepseek",
                reasoning_effort=instance.reasoning_effort,
                cwd=str(Path.cwd()),
                codex_home=instance.codex_home,
            ),
            client_factory=lambda: AppServerClient.start_stdio(
                codex_home=instance.codex_home,
                client_version="0.159.0",
                role="deepseek_child",
                extra_env=self._child_secret_env(),
                runtime_cache_dir=self.config.state_dir / "codex-runtime",
            ),
            developer_instructions=child_instructions(self.config.node_id),
            # This Windows host's managed executor rejects shell creation in
            # workspace-write. Match the authorized local execution profile;
            # assignment ownership and main/child role boundaries still apply.
            thread_config_factory=lambda: {'approval_policy': 'never', 'sandbox_mode': 'danger-full-access'},
            timeout_seconds=self.config.turn_timeout_seconds,
        )
        return gateway

    def _child_secret_env(self) -> dict[str, str]:
        if self.config.deepseek_key_file is None:
            return {}
        key = self.config.deepseek_key_file.read_text(encoding="utf-8-sig").strip()
        if not key.startswith("sk-") or "\n" in key or "\r" in key:
            raise RuntimeError("DeepSeek key file is invalid")
        return {"DEEPSEEK_API_KEY": key}

    def _make_recording_child_gateway(self, instance: ManagedInstance):
        gateway = RecordingGateway()
        self._recording_gateways.append(gateway)
        return gateway

    def _on_human_instruction(self, message) -> None:
        self.children.update_task_version(
            message.task_id, message.task_version,
        )

    async def _claim_ownership(self, message) -> bool | None:
        if self.ownership is None:
            return None
        owner = await self.ownership.claim(
            task_id=message.task_id,
            source_message_id=message.platform_message_id or message.message_id,
            node_id=self.config.node_id,
        )
        if owner is None:
            return None
        if owner != self.config.node_id:
            return False
        if self.feishu is not None:
            self.store.enqueue_group_report(
                f"claim:{message.task_id}",
                f"Astra-{owner} 已认领共享任务 {message.task_id}。",
            )
            self.feishu.notify_report()
        return True

    def _on_result(self, message, result) -> None:
        if not result.output.get('recovery_required'):
            self.main_sessions.record(message.message_id, message.task_id, 'completed' if result.accepted else 'failed', result=result.output)
        self.project_actions.changed.set()
        from .protocol import MessageKind, SourceKind
        if (self.feishu is None or message.source != SourceKind.HUMAN
                or message.kind != MessageKind.HUMAN_INSTRUCTION):
            return
        content = str(result.output.get("text", "")).strip()
        if not content:
            return
        report = f"Astra-{self.config.node_id} · {message.task_id}\n{content[:4000]}"
        self.store.enqueue_group_report(
            f"result:{message.message_id}:{message.task_version}", report,
        )
        self.feishu.notify_report()

    async def _call_main_tool(self, name, arguments):
        if name in {spec['name'] for spec in self.project_actions.specs()}:
            return await self.project_actions.call(name, arguments)
        return await self.mesh_tools.call(name, arguments)

    async def _run_feishu(self) -> None:
        assert self.feishu is not None
        while not self._feishu_stop.is_set():
            try:
                await self.feishu.start()
                self.feishu_error = None
                await self._feishu_stop.wait()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - preserve local work if IM is down
                self.feishu_error = type(exc).__name__
                try:
                    await asyncio.wait_for(self._feishu_stop.wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass
            finally:
                await self.feishu.stop()

    async def _run_peer_retry(self) -> None:
        assert self.peer is not None
        while not self._peer_stop.is_set():
            try:
                await self.peer.flush()
                for peer_id in self.config.peer_urls:
                    self._note_peer_status(
                        peer_id, await self.peer.check(peer_id),
                    )
                self.peer_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - outbox stays durable
                self.peer_error = type(exc).__name__
            try:
                await asyncio.wait_for(
                    self._peer_stop.wait(), timeout=self.config.peer_retry_seconds,
                )
            except asyncio.TimeoutError:
                pass

    def _note_peer_status(self, peer_id: str, online: bool) -> None:
        previous = self._peer_presence.get(peer_id)
        self._peer_presence[peer_id] = online
        if previous is online or self.feishu is None:
            return
        status = "上线" if online else "离线"
        self.store.enqueue_group_report(
            f"peer:{self.config.node_id}:{peer_id}:{uuid.uuid4().hex}",
            f"Astra-{self.config.node_id} 观察到 Astra-{peer_id} {status}。"
            + ("可继续交换任务和实测结果。" if online else
               "本机继续独立推进；发给该节点的消息会排队补发。"),
        )
        self.feishu.notify_report()

    def _observe_quota(self, response: dict) -> None:
        state = self._quota_monitor.observe(
            response, node_id=self.config.node_id,
            now=datetime.now(timezone.utc),
        )
        if self.feishu is None:
            return
        for alert in state.alerts:
            operation_id = (
                f"quota:{self.config.node_id}:{alert.bucket_id}:"
                f"{alert.window}:{alert.threshold}:{alert.resets_at}"
            )
            self.store.enqueue_group_report(
                operation_id,
                f"Astra-{self.config.node_id} 额度预警：{alert.message}；"
                f"重置时间 {alert.resets_at or '未知'}。本机继续处理可执行工作。",
            )
            self.feishu.notify_report()

    async def _run_quota_monitor(self) -> None:
        assert isinstance(self.astra_gateway, AppServerGateway)
        while not self._quota_stop.is_set():
            try:
                response = await self.astra_gateway.read_rate_limits()
                self._observe_quota(response)
                self.quota_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - quota is observability only
                self.quota_error = type(exc).__name__
            try:
                await asyncio.wait_for(self._quota_stop.wait(), timeout=300)
            except asyncio.TimeoutError:
                pass
