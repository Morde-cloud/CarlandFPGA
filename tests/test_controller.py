import asyncio
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fpga_mesh.controller import ActionResult, Controller
from fpga_mesh.protocol import Envelope, MessageKind, SourceKind, task_id_from_message
from fpga_mesh.store import SQLiteStore


def instruction(message_id: str = "msg-1", text: str = "work") -> Envelope:
    return Envelope(
        message_id=message_id,
        project_id="fpga-main",
        sender="human-1",
        recipient="A/Astra-A",
        task_id=task_id_from_message("group-1", "om_123"),
        task_version=1,
        sent_at=datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc),
        kind=MessageKind.HUMAN_INSTRUCTION,
        source=SourceKind.HUMAN,
        payload={"text": text},
        platform_group_id="group-1",
        platform_message_id="om_123",
    )


def stop_instruction() -> Envelope:
    return Envelope(
        message_id="stop-1",
        project_id="fpga-main",
        sender="human-1",
        recipient="*",
        task_id=task_id_from_message("group-1", "om_stop"),
        task_version=1,
        sent_at=datetime(2026, 9, 30, 8, 1, tzinfo=timezone.utc),
        kind=MessageKind.STOP_REQUEST,
        source=SourceKind.HUMAN,
        payload={"scope": "all"},
        platform_group_id="group-1",
        platform_message_id="om_stop",
    )


def resume_instruction(sent_at: datetime) -> Envelope:
    return Envelope(
        message_id=f"resume-{sent_at.isoformat()}",
        project_id="fpga-main",
        sender="human-1",
        recipient="*",
        task_id=task_id_from_message("group-1", "om_resume"),
        task_version=1,
        sent_at=sent_at,
        kind=MessageKind.RESUME_REQUEST,
        source=SourceKind.HUMAN,
        payload={"scope": "all"},
        platform_group_id="group-1",
        platform_message_id=f"om_resume_{sent_at.isoformat()}",
    )


class FakeGateway:
    def __init__(self, fail_first: bool = False, delay: float = 0.0):
        self.calls = []
        self.fail_first = fail_first
        self.delay = delay

    async def handle(self, message: Envelope):
        self.calls.append(message.message_id)
        if self.fail_first:
            self.fail_first = False
            raise RuntimeError("temporary failure")
        if self.delay:
            await asyncio.sleep(self.delay)
        return ActionResult(accepted=True, output={"message_id": message.message_id})


class ControllerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "state.sqlite"
        self.store = SQLiteStore(self.db_path)
        self.gateway = FakeGateway()
        self.controller = Controller(self.store, self.gateway)

    async def asyncTearDown(self):
        await self.controller.stop()
        self.store.close()
        self.tmp.cleanup()

    async def test_duplicate_platform_event_causes_one_model_call(self):
        first = instruction("internal-1")
        duplicate = replace(
            first,
            message_id="internal-2",
            platform_event_id="event-2",
        )
        await self.controller.offer(first)
        await self.controller.offer(duplicate)
        await self.controller.run_until_idle()
        self.assertEqual(self.gateway.calls, ["internal-1"])

    async def test_queued_human_instruction_runs_before_peer_report(self):
        report = replace(
            instruction("peer-first"), source=SourceKind.ASTRA,
            kind=MessageKind.AGENT_REPORT, sender="B/Astra-B",
            platform_group_id=None, platform_message_id=None,
        )
        await self.controller.offer(report)
        await self.controller.offer(instruction("human-second"))
        await self.controller.run_until_idle()
        self.assertEqual(self.gateway.calls, ["human-second", "peer-first"])

    async def test_newer_human_task_revision_waits_for_active_peer_turn(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()
        release = asyncio.Event()

        class BlockingGateway:
            def __init__(self):
                self.calls = []

            async def handle(self, message):
                self.calls.append(message.message_id)
                if message.message_id == "peer-active":
                    started.set()
                    try:
                        await release.wait()
                    except asyncio.CancelledError:
                        cancelled.set()
                        raise
                return ActionResult(accepted=True)

        gateway = BlockingGateway()
        controller = Controller(self.store, gateway)
        report = replace(
            instruction("peer-active"), source=SourceKind.ASTRA,
            kind=MessageKind.AGENT_REPORT, sender="B/Astra-B",
            platform_group_id=None, platform_message_id=None,
        )
        await controller.offer(report)
        await controller.start()
        try:
            await asyncio.wait_for(started.wait(), 1)
            await controller.offer(replace(instruction("human-urgent"), task_version=2))
            await asyncio.sleep(0)
            self.assertFalse(cancelled.is_set())
            self.assertEqual(gateway.calls, ["peer-active"])
            release.set()
            async def human_processed():
                while "human-urgent" not in gateway.calls:
                    await asyncio.sleep(0.01)
            await asyncio.wait_for(human_processed(), 1)
            self.assertEqual(gateway.calls[:2], ["peer-active", "human-urgent"])
        finally:
            release.set()
            await controller.stop()

    async def test_idle_wait_makes_no_model_calls(self):
        await self.controller.offer(instruction())
        await self.controller.run_until_idle()
        calls = list(self.gateway.calls)
        await self.controller.wait_for_work(timeout=0.05)
        self.assertEqual(self.gateway.calls, calls)

    async def test_completed_human_turn_is_handed_to_persistent_report_callback(self):
        reports = []
        controller = Controller(
            self.store, self.gateway,
            on_result=lambda message, result: reports.append(
                (message.message_id, result.output["message_id"])
            ),
        )
        await controller.offer(instruction("new-instruction"))
        await controller.run_until_idle()
        self.assertEqual(reports, [("new-instruction", "new-instruction")])

    async def test_stop_request_blocks_new_dispatch_immediately(self):
        await self.controller.offer(stop_instruction())
        await self.controller.run_until_idle()
        await self.controller.offer(instruction("later", "new task"))
        await self.controller.run_until_idle()
        self.assertEqual(self.gateway.calls, [])
        self.assertTrue(self.controller.dispatch_blocked)

    async def test_only_a_later_resume_can_release_a_human_pause(self):
        stop = stop_instruction()
        await self.controller.offer(stop)
        await self.controller.run_until_idle()

        early = resume_instruction(stop.sent_at - timedelta(minutes=1))
        await self.controller.offer(early)
        await self.controller.run_until_idle()
        self.assertTrue(self.controller.dispatch_blocked)

        later = resume_instruction(stop.sent_at + timedelta(minutes=1))
        await self.controller.offer(later)
        await self.controller.run_until_idle()
        self.assertFalse(self.controller.dispatch_blocked)

    async def test_failure_is_retried_after_restart_without_duplicate_processing(self):
        failing_gateway = FakeGateway(fail_first=True)
        controller = Controller(self.store, failing_gateway)
        await controller.offer(instruction("internal-1"))
        await controller.run_until_idle()
        self.assertEqual(failing_gateway.calls, ["internal-1"])
        self.assertEqual(len(self.store.pending_inbound()), 0)

        restart_gateway = FakeGateway()
        restarted = Controller(self.store, restart_gateway)
        await restarted.run_until_idle()
        self.assertEqual(restart_gateway.calls, [])
        self.store.mark_inbound_failed(
            "internal-1", "retry window elapsed",
            retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        await restarted.run_until_idle()
        self.assertEqual(restart_gateway.calls, ["internal-1"])
        self.assertEqual(self.store.pending_inbound(), [])

    async def test_pause_survives_restart_and_blocks_existing_work(self):
        await self.controller.offer(stop_instruction())
        await self.controller.offer(instruction("queued-during-pause"))
        restarted_gateway = FakeGateway()
        restarted = Controller(self.store, restarted_gateway)
        self.assertTrue(restarted.dispatch_blocked)
        await restarted.run_until_idle()
        self.assertEqual(restarted_gateway.calls, [])
        await restarted.offer(resume_instruction(
            stop_instruction().sent_at + timedelta(minutes=2)))
        await restarted.run_until_idle()
        self.assertEqual(restarted_gateway.calls, ["queued-during-pause"])

    async def test_short_wait_returns_when_event_arrives(self):
        async def deliver():
            await asyncio.sleep(0.02)
            await self.controller.offer(instruction())

        task = asyncio.create_task(deliver())
        received = await self.controller.wait_for_work(timeout=0.5)
        self.assertTrue(received)
        await task

    async def test_controller_does_not_wake_on_expired_message(self):
        expired = replace(
            instruction("expired"),
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        await self.controller.offer(expired)
        await self.controller.run_until_idle()
        self.assertEqual(self.gateway.calls, [])

    async def test_failed_human_version_callback_is_retried_from_persisted_inbox(self):
        attempts = []

        def update_version(message):
            attempts.append(message.task_version)
            if len(attempts) == 1:
                raise RuntimeError("child database temporarily locked")

        controller = Controller(self.store, self.gateway,
                                on_human_instruction=update_version)
        with self.assertRaisesRegex(RuntimeError, "temporarily locked"):
            await controller.offer(instruction("version-retry"))
        self.assertEqual(len(self.store.pending_inbound(
            now=datetime.now(timezone.utc) + timedelta(minutes=1))), 1)
        self.store.mark_inbound_failed(
            "version-retry", "retry window elapsed",
            retry_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        await controller.run_until_idle()
        self.assertEqual(attempts, [1, 1])
        self.assertEqual(self.gateway.calls, ["version-retry"])
        self.assertEqual(self.store.pending_inbound(), [])

    async def test_queued_edited_message_supersedes_older_revision(self):
        first = instruction("v1", "old direction")
        second = replace(first, message_id="v2", task_version=2,
                         revision=2, payload={"text": "new direction"})
        await self.controller.offer(first)
        await self.controller.offer(second)
        await self.controller.run_until_idle()
        self.assertEqual(self.gateway.calls, ["v2"])
        self.assertEqual(self.store.pending_inbound(), [])

    async def test_unassigned_shared_task_waits_for_confirmed_owner(self):
        claims = []
        async def claim(message):
            claims.append(message.task_id)
            return True
        controller = Controller(self.store, self.gateway, claim_ownership=claim)
        shared = replace(instruction("shared"),
                         payload={"text": "shared work", "ownership_required": True})
        await controller.offer(shared)
        await controller.run_until_idle()
        self.assertEqual(claims, [shared.task_id])
        self.assertEqual(self.gateway.calls, ["shared"])

    async def test_unconfirmed_or_other_owner_never_dispatches_shared_task(self):
        shared = replace(instruction("shared"),
                         payload={"text": "shared work", "ownership_required": True})
        controller = Controller(self.store, self.gateway,
                                claim_ownership=lambda _: None)
        await controller.offer(shared)
        await controller.run_until_idle()
        self.assertEqual(self.gateway.calls, [])
        self.assertEqual(len(self.store.pending_inbound(
            now=datetime.now(timezone.utc) + timedelta(minutes=2))), 1)


if __name__ == "__main__":
    unittest.main()
