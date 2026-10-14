"""Regression for group followups cancelling useful project work."""
import asyncio
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fpga_mesh.controller import ActionResult, Controller
from fpga_mesh.protocol import Envelope, MessageKind, SourceKind
from fpga_mesh.store import SQLiteStore


def event(mid, *, task=None, source=SourceKind.HUMAN, version=1, kind=None, **payload):
    return Envelope(
        message_id=mid, project_id='fpga-main', sender='test', recipient='B/Astra-B',
        task_id=task or mid, task_version=version,
        sent_at=datetime.now(timezone.utc), source=source,
        kind=kind or (MessageKind.HUMAN_INSTRUCTION if source == SourceKind.HUMAN
                      else MessageKind.AGENT_REPORT),
        payload={'text': mid, **payload},
    )


class HeldGateway:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.calls = []
        self.completed = []
        self.interrupted = set()

    async def handle(self, message):
        self.calls.append(message.message_id)
        # Model the existing gateway's durable no-replay guard, not a retry.
        if message.message_id in self.interrupted:
            return ActionResult(False, {'recovery_required': True})
        if message.message_id == 'active':
            self.started.set()
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.interrupted.add(message.message_id)
                self.cancelled.set()
                raise
        self.completed.append(message.message_id)
        return ActionResult(True)


class ContinuityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(Path(self.tmp.name) / 'state.sqlite')
        self.gateway = HeldGateway()
        self.controller = Controller(self.store, self.gateway)
        self.runner = None

    async def asyncTearDown(self):
        self.gateway.release.set()
        if self.runner:
            self.runner.cancel()
            await asyncio.gather(self.runner, return_exceptions=True)
        await self.controller.stop()
        self.store.close()
        self.tmp.cleanup()

    async def start(self, source=SourceKind.ASTRA):
        self.active = event('active', source=source)
        await self.controller.offer(self.active)
        self.runner = asyncio.create_task(self.controller.run_until_idle())
        await asyncio.wait_for(self.gateway.started.wait(), 1)

    async def finish(self):
        self.gateway.release.set()
        await asyncio.wait_for(self.runner, 1)

    async def test_project_resource_followup_does_not_cancel_peer_research(self):
        await self.start()
        await self.controller.offer(event('resource-note', text='物料配件自主规划'))
        await asyncio.sleep(0)
        self.assertFalse(self.gateway.cancelled.is_set())
        await self.finish()
        self.assertEqual(self.gateway.completed, ['active', 'resource-note'])
        self.assertEqual(self.store.pending_inbound(), [])

    async def test_next_human_message_does_not_cancel_current_human_task(self):
        await self.start(SourceKind.HUMAN)
        await self.controller.offer(event('question', text='当前工作进度'))
        await asyncio.sleep(0)
        self.assertFalse(self.gateway.cancelled.is_set())
        await self.finish()
        self.assertEqual(self.gateway.completed, ['active', 'question'])

    async def test_new_human_gets_next_turn_ahead_of_previously_queued_peers(self):
        await self.controller.offer(event('active', source=SourceKind.ASTRA))
        await self.controller.offer(event('older-peer', source=SourceKind.ASTRA))
        self.runner = asyncio.create_task(self.controller.run_until_idle())
        await asyncio.wait_for(self.gateway.started.wait(), 1)
        await self.controller.offer(event('human-next'))
        await self.finish()
        self.assertEqual(self.gateway.completed, ['active', 'human-next', 'older-peer'])

    async def test_effective_stop_cancels_and_persists_trigger_without_replay(self):
        await self.start()
        stop = event('pause', kind=MessageKind.STOP_REQUEST, scope='all')
        await self.controller.offer(stop)
        await asyncio.wait_for(self.gateway.cancelled.wait(), 1)
        await asyncio.wait_for(self.runner, 1)
        await self.controller.run_until_idle()
        self.assertTrue(self.controller.dispatch_blocked)
        self.assertEqual(self.gateway.calls, ['active'])
        rows = self.store._connection.execute('SELECT kind,payload FROM events').fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['kind'], 'dispatch_preempted')
        evidence = json.loads(rows[0]['payload'])
        self.assertEqual(evidence['reason'], 'human_stop')
        self.assertEqual(evidence['trigger_message_id'], 'pause')
        self.assertEqual(evidence['active_message_id'], 'active')

    async def test_newer_same_task_human_revision_interrupts_and_supersedes_peer(self):
        await self.start()
        await self.controller.offer(event('revision', task='active', version=2))
        await asyncio.wait_for(self.gateway.cancelled.wait(), 1)
        await asyncio.wait_for(self.runner, 1)
        await self.controller.run_until_idle()
        self.assertEqual(self.gateway.calls, ['active', 'revision'])
        self.assertEqual(self.gateway.completed, ['revision'])
        self.assertEqual(self.store.pending_inbound(), [])

    async def test_same_version_same_task_followup_queues(self):
        await self.start()
        await self.controller.offer(event('same-task-note', task='active'))
        await asyncio.sleep(0)
        self.assertFalse(self.gateway.cancelled.is_set())
        await self.finish()
        self.assertEqual(self.gateway.completed, ['active', 'same-task-note'])

    async def test_claimed_shared_task_revision_still_supersedes_active_version(self):
        self.controller.claim_ownership = lambda _: True
        self.active = event('active', ownership_required=True)
        await self.controller.offer(self.active)
        self.runner = asyncio.create_task(self.controller.run_until_idle())
        await asyncio.wait_for(self.gateway.started.wait(), 1)
        await self.controller.offer(event('revision', task='active', version=2,
                                          ownership_required=True))
        await asyncio.wait_for(self.gateway.cancelled.wait(), 1)
        await asyncio.wait_for(self.runner, 1)
        await self.controller.run_until_idle()
        self.assertEqual(self.gateway.calls, ['active', 'revision'])

    async def test_expired_stop_has_no_effect_on_active_work(self):
        await self.start()
        stop = replace(event('expired', kind=MessageKind.STOP_REQUEST),
                       expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        await self.controller.offer(stop)
        await asyncio.sleep(0)
        self.assertFalse(self.controller.dispatch_blocked)
        self.assertFalse(self.gateway.cancelled.is_set())
        await self.finish()
        self.assertEqual(self.gateway.completed, ['active'])

    async def test_stale_stop_and_resume_do_not_cancel_active_work(self):
        stop = event('old-stop', kind=MessageKind.STOP_REQUEST, scope='all')
        resume = replace(event('resume', kind=MessageKind.RESUME_REQUEST, scope='all'),
                         sent_at=stop.sent_at + timedelta(seconds=1))
        await self.controller.offer(stop)
        await self.controller.offer(resume)
        await self.controller.run_until_idle()
        await self.start()
        await self.controller.offer(replace(stop, message_id='late-stop'))
        await self.controller.offer(replace(resume, message_id='late-resume'))
        await asyncio.sleep(0)
        self.assertFalse(self.controller.dispatch_blocked)
        self.assertFalse(self.gateway.cancelled.is_set())
        await self.finish()
        self.assertEqual(self.gateway.completed, ['active'])

    async def test_unclaimed_shared_task_does_not_preempt_local_work(self):
        self.controller.claim_ownership = lambda _: False
        await self.start()
        await self.controller.offer(event('shared', ownership_required=True))
        await asyncio.sleep(0)
        self.assertFalse(self.gateway.cancelled.is_set())
        await self.finish()
        self.assertEqual(self.gateway.completed, ['active'])


if __name__ == '__main__':
    unittest.main()
