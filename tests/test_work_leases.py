"""Cross-route work leases, identity dedup and ownership for ChildCoordinator."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from fpga_mesh.child_cli import parser as cli_parser
from fpga_mesh.child_control import (
    ChildCoordinator,
    LocalControlClient,
    LocalControlServer,
)
from fpga_mesh.codex import CodexHomeFactory
from fpga_mesh.controller import ActionResult
from fpga_mesh.dynamic_children import ChildDynamicTools
from fpga_mesh.mcp_children import TOOLS, McpChildServer
from fpga_mesh.pool import InstancePool

OLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS child_jobs (
    job_id TEXT PRIMARY KEY,
    instance_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    task_version INTEGER NOT NULL,
    instructions TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS task_versions (
    task_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL
);
"""


def normalized_text_hash(text: str) -> str:
    return hashlib.sha256(
        text.replace("\r\n", "\n").strip().encode("utf-8")
    ).hexdigest()


class BlockingGateway:
    """Async recording/blocking execution boundary around the real pool."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.started: asyncio.Queue[str] = asyncio.Queue()
        self.release = asyncio.Event()

    async def handle(self, message):
        self.calls.append(message.message_id)
        await self.started.put(message.message_id)
        await self.release.wait()
        return ActionResult(accepted=True,
                            output={"text": message.payload["text"]})

    async def next_started(self) -> str:
        return await asyncio.wait_for(self.started.get(), 2)


class WorkLeaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.gateway = BlockingGateway()
        self.pool = InstancePool(
            node_id="A", gateway=self.gateway,
            home_factory=CodexHomeFactory(self.root / "homes"),
            state_path=self.root / "pool.json",
        )
        self.coordinator = ChildCoordinator(
            node_id="A", project_id="fpga-main", pool=self.pool,
            state_path=self.root / "jobs.sqlite",
        )

    async def asyncTearDown(self):
        await self.coordinator.close()
        self.temp.cleanup()

    async def test_zero_standby_grows_for_each_actual_job_by_default(self):
        self.assertEqual(len(self.pool.snapshot()["instances"]), 0)
        jobs = [await self.coordinator.delegate(
            task_id="grow", task_version=1, text=f"job {index}",
        ) for index in range(3)]
        for _ in range(3):
            await self.gateway.next_started()
        instances = self.pool.snapshot()["instances"]
        self.assertEqual(len(instances), 3)
        self.assertEqual(len({job["instance_id"] for job in jobs}), 3)
        self.assertEqual(len(self.gateway.calls), 3)
        self.gateway.release.set()
        results = await self.coordinator.wait([job["job_id"] for job in jobs])
        self.assertEqual([item["status"] for item in results],
                         ["completed"] * 3)

    async def test_absent_ownership_is_recorded_as_empty_list(self):
        job = await self.coordinator.delegate(
            task_id="plain", task_version=1, text="plain work",
        )
        self.assertEqual(job["ownership"], [])
        self.assertEqual(job["route"], "deepseek")
        self.assertEqual(job["work_id"], normalized_text_hash("plain work"))
        self.gateway.release.set()
        await self.coordinator.wait([job["job_id"]])
    async def test_exact_work_is_shared_across_routes_without_second_run(self):
        deepseek = await self.coordinator.delegate(
            task_id="shared", task_version=1, work_id="shared-1",
            text="inspect timing", ownership=["docs/timing.md"],
        )
        await self.gateway.next_started()
        duplicate = self.coordinator.native_reserve(
            task_id="shared", task_version=1, work_id="shared-1",
            text="inspect timing", ownership=["docs/timing.md"],
            reason="special capability",
        )
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["job_id"], deepseek["job_id"])
        self.assertIsNone(duplicate["lease_token"])
        self.assertEqual(len(self.gateway.calls), 1)
        self.gateway.release.set()
        await self.coordinator.wait([deepseek["job_id"]])

        native = self.coordinator.native_reserve(
            task_id="shared", task_version=1, work_id="shared-2",
            text="judge the design", reason="only gpt native can judge",
        )
        again = await self.coordinator.delegate(
            task_id="shared", task_version=1, work_id="shared-2",
            text="judge the design",
        )
        self.assertTrue(again["duplicate"])
        self.assertEqual(again["job_id"], native["job_id"])
        self.assertEqual(again["route"], "gpt_native")
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(len(self.pool.snapshot()["instances"]), 1)
        await self.coordinator.cancel(native["job_id"])

    async def test_same_work_id_with_different_request_is_rejected(self):
        first = await self.coordinator.delegate(
            task_id="dup", task_version=1, work_id="dup-1", text="plan A",
            ownership=["fpga_mesh/a.py"],
        )
        await self.gateway.next_started()
        with self.assertRaisesRegex(ValueError, "different request"):
            await self.coordinator.delegate(
                task_id="dup", task_version=1, work_id="dup-1",
                text="plan B",
            )
        with self.assertRaisesRegex(ValueError, "different request"):
            await self.coordinator.delegate(
                task_id="dup", task_version=1, work_id="dup-1",
                text="plan A", ownership=["fpga_mesh/b.py"],
            )
        with self.assertRaisesRegex(ValueError, "different request"):
            self.coordinator.native_reserve(
                task_id="dup", task_version=1, work_id="dup-1",
                text="plan B", reason="special capability",
            )
        self.assertEqual(len(self.coordinator.status()["jobs"]), 1)
        self.assertEqual(len(self.gateway.calls), 1)
        self.gateway.release.set()
        await self.coordinator.wait([first["job_id"]])

    async def test_missing_work_id_hashes_normalized_text(self):
        first = await self.coordinator.delegate(
            task_id="norm", task_version=1, text="  timing  report \r\n",
        )
        second = await self.coordinator.delegate(
            task_id="norm", task_version=1, text="timing  report",
        )
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["job_id"], first["job_id"])
        self.assertEqual(first["work_id"], normalized_text_hash("timing  report"))
        third = await self.coordinator.delegate(
            task_id="norm", task_version=1, text="timing report",
        )
        self.assertFalse(third["duplicate"])
        self.assertNotEqual(third["work_id"], first["work_id"])
        self.gateway.release.set()
        await self.coordinator.wait([first["job_id"], third["job_id"]])

    async def test_stale_task_version_is_rejected_before_any_claim(self):
        job = await self.coordinator.delegate(
            task_id="stale", task_version=1, text="old plan",
        )
        self.gateway.release.set()
        await self.coordinator.wait([job["job_id"]])
        self.coordinator.update_task_version("stale", 2)
        with self.assertRaisesRegex(ValueError, "stale"):
            await self.coordinator.delegate(
                task_id="stale", task_version=1, text="old plan",
            )
        with self.assertRaisesRegex(ValueError, "stale"):
            self.coordinator.native_reserve(
                task_id="stale", task_version=1, text="old plan",
                reason="special capability",
            )
        self.assertEqual(len(self.coordinator.status()["jobs"]), 1)
        self.assertEqual(len(self.gateway.calls), 1)
    async def test_overlapping_ownership_is_rejected_across_routes(self):
        first = await self.coordinator.delegate(
            task_id="own", task_version=1, work_id="own-1", text="edit one",
            ownership=["fpga_mesh/child_control.py"],
        )
        await self.gateway.next_started()
        with self.assertRaisesRegex(ValueError, "ownership"):
            await self.coordinator.delegate(
                task_id="own", task_version=1, work_id="own-2",
                text="edit equal", ownership=["./fpga_mesh/child_control.py"],
            )
        with self.assertRaisesRegex(ValueError, "ownership"):
            await self.coordinator.delegate(
                task_id="own", task_version=1, work_id="own-3",
                text="edit ancestor", ownership=["fpga_mesh"],
            )
        with self.assertRaisesRegex(ValueError, "ownership"):
            self.coordinator.native_reserve(
                task_id="own", task_version=1, work_id="own-4",
                text="native same file",
                ownership=["fpga_mesh\\child_control.py"],
                reason="special capability",
            )
        disjoint = await self.coordinator.delegate(
            task_id="own", task_version=1, work_id="own-5", text="edit sibling",
            ownership=["fpga_mesh/child_cli.py"],
        )
        await self.gateway.next_started()
        self.assertNotEqual(first["job_id"], disjoint["job_id"])
        self.assertEqual(len(self.gateway.calls), 2)
        self.gateway.release.set()
        await self.coordinator.wait([first["job_id"], disjoint["job_id"]])

    async def test_star_ownership_conflicts_with_everything(self):
        star = await self.coordinator.delegate(
            task_id="star", task_version=1, work_id="star-1", text="wide sweep",
            ownership=["*"],
        )
        await self.gateway.next_started()
        with self.assertRaisesRegex(ValueError, "ownership"):
            await self.coordinator.delegate(
                task_id="star", task_version=1, work_id="star-2",
                text="narrow edit", ownership=["src/a.py"],
            )
        self.gateway.release.set()
        await self.coordinator.wait([star["job_id"]])
        allowed = await self.coordinator.delegate(
            task_id="star", task_version=1, work_id="star-3", text="after release",
            ownership=["src/a.py"],
        )
        self.assertFalse(allowed["duplicate"])
        self.gateway.release.set()
        await self.coordinator.wait([allowed["job_id"]])

    async def test_completed_job_releases_ownership_and_repeats_prior_result(self):
        first = await self.coordinator.delegate(
            task_id="rel", task_version=1, work_id="rel-1", text="first pass",
            ownership=["src/a.py"],
        )
        self.gateway.release.set()
        await self.coordinator.wait([first["job_id"]])
        repeat = await self.coordinator.delegate(
            task_id="rel", task_version=1, work_id="rel-1", text="first pass",
            ownership=["src/a.py"],
        )
        self.assertTrue(repeat["duplicate"])
        self.assertEqual(repeat["job_id"], first["job_id"])
        self.assertEqual(repeat["result"]["text"], "first pass")
        self.assertEqual(len(self.gateway.calls), 1)
        overlapping = await self.coordinator.delegate(
            task_id="rel", task_version=1, work_id="rel-2", text="second pass",
            ownership=["src/a.py/deeper.py"],
        )
        self.assertFalse(overlapping["duplicate"])
        self.gateway.release.set()
        await self.coordinator.wait([overlapping["job_id"]])

    async def test_native_reserve_validate_complete_lifecycle(self):
        reserved = self.coordinator.native_reserve(
            task_id="native-1", task_version=1, text="judge this design",
            ownership=["docs/design.md"],
            reason="only the gpt native route can judge this",
        )
        self.assertFalse(reserved["duplicate"])
        self.assertEqual(reserved["status"], "reserved")
        self.assertEqual(reserved["route"], "gpt_native")
        self.assertTrue(reserved["lease_token"])
        self.assertEqual(len(self.pool.snapshot()["instances"]), 0)
        stored = self.coordinator.job(reserved["job_id"])
        self.assertNotIn("lease_token", stored)

        info = self.coordinator.native_validate(
            job_id=reserved["job_id"], lease_token=reserved["lease_token"],
        )
        self.assertEqual(info, {
            "job_id": reserved["job_id"], "task_id": "native-1",
            "task_version": 1, "work_id": reserved["work_id"],
            "route": "gpt_native", "status": "reserved",
            "native_agent_id": None, "execution_allowed": False,
        })
        bound = self.coordinator.native_validate(
            job_id=reserved["job_id"], lease_token=reserved["lease_token"],
            agent_id="native-agent-7",
        )
        self.assertEqual(bound["native_agent_id"], "native-agent-7")
        again = self.coordinator.native_validate(
            job_id=reserved["job_id"], lease_token=reserved["lease_token"],
            agent_id="native-agent-7",
        )
        self.assertEqual(again["native_agent_id"], "native-agent-7")
        with self.assertRaises(ValueError):
            self.coordinator.native_validate(
                job_id=reserved["job_id"], lease_token=reserved["lease_token"],
                agent_id="native-agent-8",
            )
        with self.assertRaises(PermissionError):
            self.coordinator.native_validate(
                job_id=reserved["job_id"],
                lease_token=reserved["lease_token"] + "-wrong",
            )

        completed = self.coordinator.native_complete(
            job_id=reserved["job_id"], lease_token=reserved["lease_token"],
            text="native verdict",
        )
        self.assertFalse(completed["duplicate"])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["result"], {
            "text": "native verdict", "native_agent_id": "native-agent-7",
        })
        repeat = self.coordinator.native_complete(
            job_id=reserved["job_id"], lease_token=reserved["lease_token"],
            text="native verdict",
        )
        self.assertTrue(repeat["duplicate"])
        with self.assertRaises(ValueError):
            self.coordinator.native_complete(
                job_id=reserved["job_id"], lease_token=reserved["lease_token"],
                text="changed verdict",
            )
        with self.assertRaises(ValueError):
            self.coordinator.native_validate(
                job_id=reserved["job_id"], lease_token=reserved["lease_token"],
            )

        direct = self.coordinator.native_reserve(
            task_id="native-2", task_version=1, text="second native task",
            reason="special capability",
        )
        with self.assertRaisesRegex(ValueError, "validate"):
            self.coordinator.native_complete(
                job_id=direct["job_id"], lease_token=direct["lease_token"],
                text="completed without validate",
            )
        self.coordinator.native_validate(
            job_id=direct["job_id"], lease_token=direct["lease_token"],
            agent_id="direct-agent",
        )
        self.coordinator.native_complete(
            job_id=direct["job_id"], lease_token=direct["lease_token"],
            text="validated completion",
        )
        self.assertEqual(
            self.coordinator.job(direct["job_id"])["status"], "completed",
        )

        jobs = self.coordinator.status()["jobs"]
        native = next(item for item in jobs
                      if item["job_id"] == reserved["job_id"])
        self.assertEqual(native["route"], "gpt_native")
        self.assertEqual(native["work_id"], reserved["work_id"])
        self.assertEqual(native["ownership"], ["docs/design.md"])
        self.assertEqual(native["native_agent_id"], "native-agent-7")
        for item in jobs:
            self.assertNotIn("lease_token", item)
            self.assertNotIn("instructions", item)
    async def test_native_reserve_requires_nonempty_reason(self):
        with self.assertRaises(ValueError):
            self.coordinator.native_reserve(
                task_id="reason", task_version=1, text="work", reason="",
            )
        with self.assertRaises(ValueError):
            self.coordinator.native_reserve(
                task_id="reason", task_version=1, text="work", reason="   ",
            )
        self.assertEqual(self.coordinator.status()["jobs"], [])

    async def test_native_validate_rejects_wrong_route_and_expired_lease(self):
        deep = await self.coordinator.delegate(
            task_id="route", task_version=1, text="deep seek work",
        )
        await self.gateway.next_started()
        with self.assertRaisesRegex(ValueError, "route"):
            self.coordinator.native_validate(
                job_id=deep["job_id"], lease_token="synthetic-lease-0001",
            )
        self.gateway.release.set()
        await self.coordinator.wait([deep["job_id"]])

        reserved = self.coordinator.native_reserve(
            task_id="expire", task_version=1, text="native work",
            reason="special capability",
        )
        connection = sqlite3.connect(self.root / "jobs.sqlite")
        with connection:
            connection.execute(
                "UPDATE child_jobs SET created_at=?, updated_at=? WHERE job_id=?",
                ("2000-01-01T00:00:00Z", "2000-01-01T00:00:00Z",
                 reserved["job_id"]),
            )
        connection.close()
        with self.assertRaisesRegex(ValueError, "expired"):
            self.coordinator.native_validate(
                job_id=reserved["job_id"],
                lease_token=reserved["lease_token"],
            )
        with self.assertRaisesRegex(ValueError, "expired"):
            self.coordinator.native_complete(
                job_id=reserved["job_id"],
                lease_token=reserved["lease_token"], text="late result",
            )

    async def test_crash_recovery_interrupts_native_lease_without_replay(self):
        reserved = self.coordinator.native_reserve(
            task_id="crash", task_version=1, text="native work",
            reason="special capability",
        )
        restarted = ChildCoordinator(
            node_id="A", project_id="fpga-main", pool=self.pool,
            state_path=self.root / "jobs.sqlite",
        )
        try:
            job = restarted.job(reserved["job_id"])
            self.assertEqual(job["status"], "interrupted")
            with self.assertRaisesRegex(ValueError, "no longer active"):
                restarted.native_validate(
                    job_id=reserved["job_id"],
                    lease_token=reserved["lease_token"],
                )
            with self.assertRaisesRegex(ValueError, "no longer active"):
                restarted.native_complete(
                    job_id=reserved["job_id"],
                    lease_token=reserved["lease_token"], text="late result",
                )
            repeat = restarted.native_reserve(
                task_id="crash", task_version=1, text="native work",
                reason="special capability",
            )
            self.assertTrue(repeat["duplicate"])
            self.assertIsNone(repeat["lease_token"])
            self.assertEqual(repeat["status"], "interrupted")
            self.assertEqual(len(restarted.status()["jobs"]), 1)
        finally:
            await restarted.close()

    async def test_legacy_database_migrates_and_preserves_rows(self):
        legacy_path = self.root / "legacy.sqlite"
        connection = sqlite3.connect(legacy_path)
        connection.executescript(OLD_SCHEMA)
        connection.execute(
            "INSERT INTO child_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("legacy-1", "deepseek-a-9", "old-task", 1, "old text",
             "completed", json.dumps({"text": "legacy result"}), None,
             "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        connection.execute(
            "INSERT INTO child_jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("legacy-2", "deepseek-a-9", "old-task", 1, "old text 2",
             "running", None, None,
             "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
        )
        connection.commit()
        connection.close()

        legacy = ChildCoordinator(
            node_id="A", project_id="fpga-main", pool=self.pool,
            state_path=legacy_path,
        )
        try:
            columns = {row["name"] for row in legacy._db.execute(
                "PRAGMA table_info(child_jobs)"
            )}
            self.assertLessEqual(
                {"work_id", "route", "request_hash", "ownership_json",
                 "lease_token", "native_agent_id"}, columns,
            )
            old = legacy.job("legacy-1")
            self.assertEqual(old["result"]["text"], "legacy result")
            self.assertEqual(old["route"], "deepseek")
            self.assertEqual(old["ownership"], [])
            self.assertIsNone(old["work_id"])
            self.assertEqual(legacy.job("legacy-2")["status"], "interrupted")
            new_job = await legacy.delegate(
                task_id="new-task", task_version=1, text="new work",
                ownership=["src/new.py"],
            )
            self.assertFalse(new_job["duplicate"])
            self.gateway.release.set()
            await legacy.wait([new_job["job_id"]])
            self.assertEqual(
                legacy.job(new_job["job_id"])["status"], "completed",
            )
        finally:
            await legacy.close()

    async def test_cancelled_deepseek_job_is_not_replayed(self):
        job = await self.coordinator.delegate(
            task_id="cancel", task_version=1, text="stop me",
        )
        await self.gateway.next_started()
        cancelled = await self.coordinator.cancel(job["job_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        repeat = await self.coordinator.delegate(
            task_id="cancel", task_version=1, text="stop me",
        )
        self.assertTrue(repeat["duplicate"])
        self.assertEqual(repeat["job_id"], job["job_id"])
        self.assertEqual(repeat["status"], "cancelled")
        self.assertEqual(len(self.gateway.calls), 1)
        self.assertEqual(self.pool.snapshot()["standby"], 1)

    async def test_cancelled_native_lease_is_terminal_and_not_replayed(self):
        reserved = self.coordinator.native_reserve(
            task_id="cancel-native", task_version=1, text="stop native",
            reason="special capability",
        )
        cancelled = await self.coordinator.cancel(reserved["job_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        with self.assertRaisesRegex(ValueError, "no longer active"):
            self.coordinator.native_validate(
                job_id=reserved["job_id"],
                lease_token=reserved["lease_token"],
            )
        with self.assertRaisesRegex(ValueError, "no longer active"):
            self.coordinator.native_complete(
                job_id=reserved["job_id"],
                lease_token=reserved["lease_token"], text="late result",
            )
        repeat = self.coordinator.native_reserve(
            task_id="cancel-native", task_version=1, text="stop native",
            reason="special capability",
        )
        self.assertTrue(repeat["duplicate"])
        self.assertIsNone(repeat["lease_token"])
        self.assertEqual(len(self.coordinator.status()["jobs"]), 1)
    async def test_route_race_resolves_to_one_job_without_second_run(self):
        original_reserve = self.pool.reserve
        entered = asyncio.Event()
        release_claim = asyncio.Event()

        async def paused_reserve(instance_id):
            entered.set()
            await release_claim.wait()
            await original_reserve(instance_id)

        self.pool.reserve = paused_reserve
        pending = asyncio.create_task(self.coordinator.delegate(
            task_id="race", task_version=1, work_id="race-1",
            text="native or deep",
        ))
        await asyncio.wait_for(entered.wait(), 2)
        native = self.coordinator.native_reserve(
            task_id="race", task_version=1, work_id="race-1",
            text="native or deep", reason="special capability",
        )
        release_claim.set()
        resolved = await asyncio.wait_for(pending, 2)
        self.assertTrue(resolved["duplicate"])
        self.assertEqual(resolved["job_id"], native["job_id"])
        self.assertEqual(len(self.gateway.calls), 0)
        self.assertEqual(self.pool.snapshot()["standby"], 1)

    async def test_native_complete_error_marks_failure_terminal(self):
        reserved = self.coordinator.native_reserve(
            task_id="native-error", task_version=1, text="native work",
            reason="special capability",
        )
        failed = self.coordinator.native_complete(
            job_id=reserved["job_id"], lease_token=reserved["lease_token"],
            text="", error="native child crashed",
        )
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error"], "native child crashed")
        self.assertIsNone(failed["result"])
        with self.assertRaisesRegex(ValueError, "no longer active"):
            self.coordinator.native_validate(
                job_id=reserved["job_id"],
                lease_token=reserved["lease_token"],
            )

    async def test_ownership_must_be_project_relative(self):
        with self.assertRaises(ValueError):
            await self.coordinator.delegate(
                task_id="abs", task_version=1, text="absolute",
                ownership=["C:/tmp/x.py"],
            )
        with self.assertRaises(ValueError):
            await self.coordinator.delegate(
                task_id="abs", task_version=1, text="escaping",
                ownership=["../outside.py"],
            )
        with self.assertRaises(ValueError):
            await self.coordinator.delegate(
                task_id="abs", task_version=1, text="blank",
                ownership=["  "],
            )
        self.assertEqual(self.coordinator.status()["jobs"], [])

    async def test_local_control_actions_native_job_and_delegate_defaults(self):
        server = LocalControlServer(self.coordinator, token="synthetic-token")
        await server.start()
        client = LocalControlClient(host="127.0.0.1", port=server.port,
                                    token="synthetic-token")
        try:
            reserved = await client.call("native_reserve", {
                "task_id": "socket", "task_version": 1,
                "text": "native socket work", "reason": "special capability",
                "ownership": ["docs/ops.md"],
            })
            self.assertEqual(reserved["status"], "reserved")
            self.assertTrue(reserved["lease_token"])
            info = await client.call("native_validate", {
                "job_id": reserved["job_id"],
                "lease_token": reserved["lease_token"],
                "agent_id": "socket-agent",
            })
            self.assertEqual(info["status"], "running")
            completed = await client.call("native_complete", {
                "job_id": reserved["job_id"],
                "lease_token": reserved["lease_token"],
                "text": "socket result",
            })
            self.assertEqual(completed["result"]["text"], "socket result")
            stored = await client.call("job", {"job_id": reserved["job_id"]})
            self.assertEqual(stored["result"]["text"], "socket result")
            self.assertEqual(stored["route"], "gpt_native")

            delegated = await client.call("delegate", {
                "task_id": "socket-deep", "task_version": 1, "text": "grow",
                "work_id": "socket-deep-1", "ownership": ["src/socket.py"],
            })
            self.assertFalse(delegated["duplicate"])
            await self.gateway.next_started()
            self.assertEqual(len(self.pool.snapshot()["instances"]), 1)
            with self.assertRaisesRegex(RuntimeError, "no standby"):
                await client.call("delegate", {
                    "task_id": "socket-deep", "task_version": 1,
                    "text": "no growth", "auto_expand": False,
                })
            self.gateway.release.set()
            results = await client.call("wait", {"job_ids": [delegated["job_id"]]})
            self.assertEqual(results[0]["result"]["text"], "grow")
            status = await client.call("status", {})
            self.assertEqual(status["jobs"][0]["ownership"], ["docs/ops.md"])
            for item in status["jobs"]:
                self.assertNotIn("lease_token", item)
        finally:
            await server.close()

    async def test_mcp_tools_expose_native_actions_without_renaming_children(self):
        names = {tool["name"] for tool in TOOLS}
        self.assertEqual(names, {
            "child_status", "child_scale", "child_delegate", "child_wait",
            "child_cancel", "native_reserve", "native_validate",
            "native_complete",
        })
        delegate_tool = next(tool for tool in TOOLS
                             if tool["name"] == "child_delegate")
        properties = delegate_tool["inputSchema"]["properties"]
        self.assertIn("work_id", properties)
        self.assertIn("ownership", properties)

        class RecordingClient:
            def __init__(self):
                self.calls = []

            async def call(self, action, arguments):
                self.calls.append((action, arguments))
                return {"ok": True}

        client = RecordingClient()
        mcp = McpChildServer(client)
        response = await mcp.process({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "native_reserve", "arguments": {
                "task_id": "t", "task_version": 1, "text": "x",
                "reason": "special capability",
            }},
        })
        self.assertFalse(response["result"]["isError"])
        self.assertEqual(client.calls[-1][0], "native_reserve")

        dynamic = ChildDynamicTools(client)
        spec_names = {spec["name"] for spec in dynamic.specs()}
        self.assertEqual(spec_names, {f"fpga_{name}" for name in names})
        await dynamic.call("fpga_native_validate", {
            "job_id": "j", "lease_token": "lease",
        })
        self.assertEqual(client.calls[-1], (
            "native_validate", {"job_id": "j", "lease_token": "lease"},
        ))
        await dynamic.call("fpga_native_complete", {
            "job_id": "j", "lease_token": "lease", "text": "done",
        })
        self.assertEqual(client.calls[-1][0], "native_complete")

    def test_cli_parses_native_commands_and_defaults_to_expansion(self):
        base = ["--control-file", "control.json"]
        delegate = cli_parser().parse_args(
            base + ["delegate", "--task-id", "t", "--task-version", "1",
                    "--text", "x"]
        )
        self.assertTrue(delegate.auto_expand)
        legacy = cli_parser().parse_args(
            base + ["delegate", "--task-id", "t", "--task-version", "1",
                    "--text", "x", "--auto-expand"]
        )
        self.assertTrue(legacy.auto_expand)
        forwarded = cli_parser().parse_args(
            base + ["delegate", "--task-id", "t", "--task-version", "1",
                    "--text", "x", "--work-id", "w-1",
                    "--ownership", "src/a.py", "--ownership", "docs/b.md"]
        )
        self.assertEqual(forwarded.work_id, "w-1")
        self.assertEqual(forwarded.ownership, ["src/a.py", "docs/b.md"])

        reserved = cli_parser().parse_args(
            base + ["native-reserve", "--task-id", "t", "--task-version", "1",
                    "--work-id", "w-2", "--text", "x",
                    "--reason", "special capability",
                    "--ownership", "docs/c.md"]
        )
        self.assertEqual(reserved.command, "native-reserve")
        self.assertEqual(reserved.work_id, "w-2")
        self.assertEqual(reserved.ownership, ["docs/c.md"])
        validated = cli_parser().parse_args(
            base + ["native-validate", "--job-id", "j", "--lease-token", "L"]
        )
        self.assertIsNone(validated.agent_id)
        leading_dash = cli_parser().parse_args(
            base + ["native-validate", "--job-id", "j", "--lease-token=-synthetic"]
        )
        self.assertEqual(leading_dash.lease_token, "-synthetic")
        bound = cli_parser().parse_args(
            base + ["native-validate", "--job-id", "j", "--lease-token", "L",
                    "--agent-id", "agent-1"]
        )
        self.assertEqual(bound.agent_id, "agent-1")
        completed = cli_parser().parse_args(
            base + ["native-complete", "--job-id", "j", "--lease-token", "L",
                    "--text", "done", "--error", "boom"]
        )
        self.assertEqual(completed.error, "boom")
        job = cli_parser().parse_args(base + ["job", "--job-id", "j"])
        self.assertEqual(job.job_id, "j")

    async def _cli(self, *args):
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "fpga_mesh.child_cli",
            "--control-file", str(self.control_file), *args,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=environment,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), 5)
        self.assertEqual(process.returncode, 0, stderr.decode(errors="replace"))
        return json.loads(stdout.decode("utf-8"))

    async def test_cli_native_flow_and_delegate_defaults(self):
        self.control_file = self.root / "control.json"
        server = LocalControlServer(
            self.coordinator, token="synthetic-cli-token",
            discovery_path=self.control_file,
        )
        await server.start()
        try:
            reserved = await self._cli(
                "native-reserve", "--task-id", "cli-1", "--task-version", "1",
                "--work-id", "cli-1", "--text", "native cli work",
                "--reason", "special capability",
                "--ownership", "docs/cli.md",
            )
            self.assertEqual(reserved["status"], "reserved")
            self.assertTrue(reserved["lease_token"])
            await self._cli(
                "native-validate", "--job-id", reserved["job_id"],
                "--lease-token=" + reserved["lease_token"],
                "--agent-id", "cli-agent",
            )
            completed = await self._cli(
                "native-complete", "--job-id", reserved["job_id"],
                "--lease-token=" + reserved["lease_token"],
                "--text", "cli native result",
            )
            self.assertEqual(completed["result"]["text"], "cli native result")
            stored = await self._cli("job", "--job-id", reserved["job_id"])
            self.assertEqual(stored["native_agent_id"], "cli-agent")
            delegated = await self._cli(
                "delegate", "--task-id", "cli-2", "--task-version", "1",
                "--text", "grow", "--work-id", "cli-2",
                "--ownership", "src/cli.py",
            )
            self.assertFalse(delegated["duplicate"])
            await self.gateway.next_started()
            self.assertEqual(len(self.pool.snapshot()["instances"]), 1)
            self.gateway.release.set()
            results = await self._cli("wait", "--job-id", delegated["job_id"])
            self.assertEqual(results[0]["result"]["text"], "grow")
        finally:
            await server.close()


if __name__ == "__main__":
    unittest.main()
