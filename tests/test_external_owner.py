"""Behavioral regressions for unsent App work and independent mesh dispatch."""
import asyncio
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fpga_mesh.app_server import AppServerClient
from fpga_mesh.controller import Controller
from fpga_mesh.gateway import AppServerGateway, GatewayConfig
from fpga_mesh.project_control import ProjectActions
from fpga_mesh.protocol import MessageKind
from fpga_mesh.sessions import MainSessionRouter, ExternalOwnerRequired, ExternalDeliveryPending
from fpga_mesh.store import SQLiteStore
from fpga_mesh.update import assert_idle, stop_idle_node
from tests.test_sessions import Wire, event


class ExternalOwnerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.router = MainSessionRouter(self.root / 'main_sessions.sqlite')
        self.store = SQLiteStore(self.root / 'state.sqlite')
        self.wire = Wire()
        self.client = AppServerClient(self.wire, client_version='test')
        self.gateway = AppServerGateway(GatewayConfig(node_id='B', role='astra',
            model='gpt-6-astra', provider='openai', reasoning_effort='ultra',
            cwd=str(self.root), codex_home=str(self.root)),
            client_factory=lambda: self.client, session_router=self.router)
        self.results = []
        self.controller = Controller(self.store, self.gateway,
                                     on_result=lambda message, result: self.results.append(message.task_id))
        self.runtime = SimpleNamespace(main_sessions=self.router, astra_gateway=self.gateway,
            controller=self.controller, config=SimpleNamespace(node_id='B', project_id='fpga-main', state_dir=self.root))
        self.actions = ProjectActions(self.runtime)
        self.register()
        self.declare()

    async def asyncTearDown(self):
        await self.gateway.close()
        self.router.close()
        self.store.close()
        self.tmp.cleanup()

    def register(self, task='app-task', thread='original-director', version=1):
        with self.router.db:
            self.router.db.execute('INSERT INTO main_sessions VALUES (?,?,?,?,?,?,?,?,?)',
                (task, thread, version, 'gpt-6-astra', 'ultra', 'execution', task, None,
                 datetime.now(timezone.utc).isoformat()))

    def declare(self, **changes):
        owner = {'owner_kind': 'desktop', 'thread_id': 'original-director', 'task_version': 1, **changes}
        self.router.external_owners_path.write_text(json.dumps({'app-task': owner}), encoding='utf-8')

    async def defer(self, message=None):
        message = message or event('app-task')
        await self.controller.offer(message)
        await self.controller.run_until_idle()
        return message, self.router.external_delivery(message.message_id)

    def receipt_args(self, message):
        return dict(message_id=message.message_id, task_id='app-task', task_version=1,
                    thread_id='original-director', turn_id='actual-app-turn', evidence='actual consumed receipt path')

    async def test_declared_owner_prevents_any_client_or_work_request(self):
        with patch.object(self.gateway, '_ensure_client', side_effect=AssertionError('client forbidden')):
            message, delivery = await self.defer()
        self.assertEqual(self.wire.requests, [])
        self.assertEqual(delivery['recipient_thread_id'], 'original-director')
        self.assertEqual(delivery['envelope'], json.loads(message.to_json()))
        self.assertEqual(delivery['status'], 'pending')
        self.assertEqual(self.router.result(message.message_id)['status'], 'delivery_pending')
        self.assertEqual(self.store.pending_inbound(), [])
        self.assertEqual(self.results, [])

    async def test_independent_task_runs_without_node_backoff_or_failure(self):
        held = event('app-task')
        other = event('other-task')
        await self.controller.offer(held)
        await self.controller.offer(other)
        await self.controller.run_until_idle()
        self.assertEqual(self.router.result(held.message_id)['status'], 'delivery_pending')
        self.assertEqual(self.router.result(other.message_id)['status'], 'completed')
        self.assertEqual(self.results, ['other-task'])
        self.assertIsNone(self.store.load_gateway_retry())
        self.assertEqual(len([x for x in self.wire.requests if x[0] == 'turn/start']), 1)

    async def test_two_app_messages_survive_restart_and_removal_around_independent_work(self):
        first, independent, second = event('app-task', 'first'), event('independent'), event('app-task', 'second')
        for message in (first, independent, second):
            await self.controller.offer(message)
        await self.controller.run_until_idle()
        deliveries = self.router.external_deliveries()
        self.assertEqual(len(deliveries), 2)
        for message in (first, second):
            saved = self.router.external_delivery(message.message_id)
            self.assertEqual(saved['envelope'], json.loads(message.to_json()))
            self.assertEqual(saved['recipient_thread_id'], 'original-director')
            self.assertEqual(self.router.result(message.message_id)['status'], 'delivery_pending')
        self.assertEqual(self.router.result(independent.message_id)['status'], 'completed')
        self.assertEqual(self.results, ['independent'])
        self.assertFalse(any(method in {'thread/resume', 'turn/start'} and
                             params.get('threadId') == 'original-director'
                             for method, params in self.wire.requests))
        self.assertEqual(len([m for m, _ in self.wire.requests if m == 'turn/start']), 1)
        await self.gateway.close()
        self.router.close()
        self.router = MainSessionRouter(self.root / 'main_sessions.sqlite')
        self.gateway.session_router = self.router
        self.runtime.main_sessions = self.router
        self.router.external_owners_path.unlink()
        before = list(self.wire.requests)
        for message in (first, second):
            with self.assertRaises(ExternalDeliveryPending):
                await self.gateway.handle(message)
        await self.controller.run_until_idle()
        self.assertEqual(self.wire.requests, before)
        self.assertEqual(self.router.external_deliveries(), deliveries)
        self.assertEqual(self.store.pending_inbound(), [])

    async def test_durable_deferral_survives_crash_before_inbox_consumption(self):
        message = event('app-task')
        await self.controller.offer(message)
        with patch.object(self.store, 'mark_inbound_processed', side_effect=RuntimeError('crash')):
            with self.assertRaisesRegex(RuntimeError, 'crash'):
                await self.controller.run_until_idle()
        before = self.router.external_delivery(message.message_id)
        self.assertIsNotNone(before)
        await self.gateway.close()
        self.router.close()
        self.router = MainSessionRouter(self.root / 'main_sessions.sqlite')
        self.gateway.session_router = self.router
        self.runtime.main_sessions = self.router
        self.router.external_owners_path.unlink()
        await self.controller.run_until_idle()
        self.assertEqual(self.router.external_delivery(message.message_id), before)
        self.assertEqual(self.wire.requests, [])
        self.assertEqual(self.store.pending_inbound(), [])

    async def test_failed_interrupted_and_running_are_never_reclassified_or_replayed(self):
        for status in ('failed', 'interrupted', 'running'):
            message = event('app-task', text=status)
            self.router.record(message.message_id, message.task_id, status, error='original evidence')
            before = self.router.result(message.message_id)
            await self.defer(message)
            self.assertEqual(self.router.result(message.message_id), before)
            self.assertIsNone(self.router.external_delivery(message.message_id))
        self.assertEqual(self.wire.requests, [])

    async def test_legacy_or_mismatched_declaration_is_held_for_reconciliation(self):
        for index, changes in enumerate(({'task_version': 2}, {'thread_id': 'wrong-thread'},
                                        {'task_version': None}, {'owner_kind': 'other'})):
            self.declare(**changes)
            message, delivery = await self.defer(event('app-task', text=f'case {index}'))
            self.assertIn('external owner', delivery['reason'])
            self.assertEqual(self.router.result(message.message_id)['status'], 'delivery_pending')
        self.assertEqual(self.wire.requests, [])

    async def test_stale_message_cannot_be_consumed_under_a_newer_owner_version(self):
        message, delivery = await self.defer(replace(event('app-task'), task_version=2))
        self.assertIn('does not match', delivery['reason'])
        with self.assertRaises(ValueError):
            self.router.external_receipt(**{**self.receipt_args(message), 'task_version': 2})

    async def test_external_human_revision_does_not_advance_mesh_child_versions(self):
        applied = []
        self.controller.on_human_instruction = lambda message: applied.append((message.task_id, message.task_version))
        message, _ = await self.defer(replace(event('app-task'), task_version=2))
        self.assertEqual(applied, [])
        self.assertEqual(self.router.session('app-task')['task_version'], 1)
        other = event('other-task')
        await self.controller.offer(other)
        await self.controller.run_until_idle()
        self.assertEqual(applied, [('other-task', 1), ('other-task', 1)])

    async def test_unlisted_task_ignores_an_invalid_other_declaration(self):
        self.declare(owner_kind='broken')
        message = event('unlisted')
        await self.controller.offer(message)
        await self.controller.run_until_idle()
        self.assertEqual(self.router.result(message.message_id)['status'], 'completed')

    async def test_stop_wins_before_deferral_and_independent_execution(self):
        stop = replace(event('control', text='stop'), kind=MessageKind.STOP_REQUEST,
                       sent_at=datetime.now(timezone.utc) + timedelta(seconds=1))
        message = event('app-task')
        await self.controller.offer(message)
        await self.controller.offer(event('other-task'))
        await self.controller.offer(stop)
        await self.controller.run_until_idle()
        self.assertEqual(self.router.external_deliveries(), [])
        self.assertEqual(self.wire.requests, [])
        resume = replace(stop, message_id='resume', kind=MessageKind.RESUME_REQUEST,
                         sent_at=stop.sent_at + timedelta(seconds=1))
        await self.controller.offer(resume)
        await self.controller.run_until_idle()
        self.assertEqual(self.router.result(message.message_id)['status'], 'delivery_pending')
        self.assertEqual(self.results, ['other-task'])

    async def test_project_submit_keeps_stop_aware_inbox_without_client_or_new_session(self):
        before = self.router.session('app-task')
        with patch.object(self.gateway, '_ensure_client', side_effect=AssertionError('client forbidden')):
            result = await self.actions.call('main_submit', dict(task_id='app-task', task_version=1, text='new work'))
        self.assertTrue(result['queued'])
        self.assertFalse(result['execution_started'])
        self.assertEqual(self.router.session('app-task'), before)
        await self.controller.run_until_idle()
        waited = await self.actions.call('main_wait', dict(message_id=result['message_id'], timeout_seconds=1))
        self.assertEqual(waited['status'], 'delivery_pending')

    async def test_submit_owner_race_queues_new_work_without_generic_failure(self):
        self.router.external_owners_path.unlink()
        original = self.gateway._ensure_client
        async def changed():
            client = await original()
            self.declare()
            return client
        with patch.object(self.gateway, '_ensure_client', changed):
            result = await self.actions.call('main_submit', dict(task_id='app-task', task_version=1, text='racing work'))
        self.assertTrue(result['queued'])
        await self.controller.run_until_idle()
        self.assertEqual(self.router.result(result['message_id'])['status'], 'delivery_pending')
        self.assertFalse(any(m in {'thread/resume', 'turn/start'} for m, _ in self.wire.requests))

    async def test_unregistered_declared_task_does_not_create_a_root(self):
        with self.router.db:
            self.router.db.execute("DELETE FROM main_sessions WHERE task_id='app-task'")
        _, delivery = await self.defer()
        self.assertIn('does not match', delivery['reason'])
        self.assertIsNone(self.router.session('app-task'))
        self.assertEqual(self.wire.requests, [])

    async def test_router_entrypoints_and_loaded_thread_are_guarded(self):
        self.router._loaded.add('original-director')
        before = self.router.session('app-task')
        with self.assertRaises(ExternalOwnerRequired):
            await self.router.open_session(self.client, task_id='app-task', task_version=1, text='work', cwd=str(self.root))
        with self.assertRaises(ExternalOwnerRequired):
            await self.router.prepare(self.client, event('app-task'), cwd=str(self.root))
        with self.assertRaises(ExternalOwnerRequired):
            await self.router.schedule_route(self.client, task_id='app-task', model='gpt-6-luna', effort='low')
        with self.assertRaises(ExternalOwnerRequired):
            await self.actions.call('session_route', dict(task_id='app-task', model='gpt-6-luna', effort='low'))
        self.assertEqual(self.router.session('app-task'), before)
        self.assertEqual(self.wire.requests, [])

    async def test_owner_appearing_during_model_lookup_prevents_resume_or_turn(self):
        self.router.external_owners_path.unlink()
        original = self.wire.request
        async def request(method, params=None):
            result = await original(method, params)
            if method == 'model/list':
                self.declare()
            return result
        self.wire.request = request
        message, delivery = await self.defer()
        self.assertIsNotNone(delivery)
        self.assertFalse(any(m in {'thread/start', 'thread/resume', 'turn/start'} for m, _ in self.wire.requests))

    async def test_owner_appearing_after_prepare_prevents_work_send(self):
        self.router.external_owners_path.unlink()
        prepare = self.router.prepare
        async def changed(*args, **kwargs):
            route = await prepare(*args, **kwargs)
            self.declare()
            return route
        with patch.object(self.router, 'prepare', changed):
            _, delivery = await self.defer()
        self.assertIsNotNone(delivery)
        self.assertFalse(any(m == 'turn/start' for m, _ in self.wire.requests))

    async def test_exact_receipt_is_immutable_and_does_not_authorize_replay(self):
        message, _ = await self.defer()
        args = self.receipt_args(message)
        result = await self.actions.call('external_receipt', args)
        self.assertEqual(result['status'], 'consumed')
        self.assertEqual(await self.actions.call('external_receipt', args), result)
        with self.assertRaises(ValueError):
            await self.actions.call('external_receipt', {**args, 'turn_id': 'different'})
        self.router.external_owners_path.unlink()
        await self.gateway.handle(message)
        self.assertEqual(self.wire.requests, [])
        self.assertEqual(self.router.result(message.message_id)['status'], 'external_consumed')

    async def test_receipt_rejects_stop_wrong_owner_version_or_changed_declaration(self):
        message, _ = await self.defer()
        args = self.receipt_args(message)
        for changes in ({'task_version': 2}, {'task_version': True}, {'thread_id': 'other'}, {'turn_id': ''}, {'evidence': ''}):
            with self.assertRaises(ValueError):
                await self.actions.call('external_receipt', {**args, **changes})
        self.controller.dispatch_blocked = True
        with self.assertRaisesRegex(ValueError, 'STOP'):
            await self.actions.call('external_receipt', args)
        self.controller.dispatch_blocked = False
        self.declare(thread_id='other')
        with self.assertRaises(ValueError):
            await self.actions.call('external_receipt', args)
        self.assertEqual(self.router.external_delivery(message.message_id)['status'], 'pending')

    async def test_declaration_removal_never_releases_an_existing_pending_message(self):
        message, delivery = await self.defer()
        self.router.external_owners_path.unlink()
        with self.assertRaises(ExternalDeliveryPending):
            await self.gateway.handle(message)
        self.assertEqual(self.router.external_delivery(message.message_id), delivery)
        self.assertEqual(self.wire.requests, [])

    def config(self):
        path = self.root / 'node.toml'
        path.write_text('node_id="B"\nstate_dir="."\n', encoding='utf-8')
        return path

    async def test_declared_external_writer_blocks_idle_and_stop_with_empty_runs(self):
        self.assertEqual(self.router.db.execute('SELECT count(*) FROM main_runs').fetchone()[0], 0)
        called = []
        for check in (lambda: assert_idle(self.config(), node='B'),
                      lambda: stop_idle_node(self.config(), node='B', stop=lambda: called.append(True))):
            with self.assertRaisesRegex(ValueError, 'external App writers'):
                check()
        self.assertEqual(called, [])

    async def test_pending_delivery_blocks_stop_even_after_owner_file_removed(self):
        await self.defer()
        self.router.external_owners_path.unlink()
        called = []
        with self.assertRaises(ValueError):
            stop_idle_node(self.config(), node='B', stop=lambda: called.append(True))
        self.assertEqual(called, [])

    async def test_corrupt_owner_file_is_held_and_prevents_stop(self):
        self.router.external_owners_path.write_text('{', encoding='utf-8')
        _, delivery = await self.defer()
        self.assertIn('unreadable', delivery['reason'])
        self.assertEqual(self.wire.requests, [])
        with self.assertRaises(ValueError):
            assert_idle(self.config(), node='B')

    async def test_duplicate_declaration_keys_fail_closed(self):
        self.router.external_owners_path.write_text('{"app-task":{},"app-task":{}}', encoding='utf-8')
        _, delivery = await self.defer()
        self.assertIn('unreadable', delivery['reason'])
        self.assertEqual(self.wire.requests, [])

    async def test_consumption_does_not_override_a_still_declared_external_writer(self):
        message, _ = await self.defer()
        await self.actions.call('external_receipt', self.receipt_args(message))
        with self.assertRaisesRegex(ValueError, 'external App writers'):
            assert_idle(self.config(), node='B')


if __name__ == '__main__':
    unittest.main()
