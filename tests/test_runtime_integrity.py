"""Runtime-integrity fail-closed deferral regression tests (offline only).

Covers the frozen PR28 repair interface:
  * fpga_mesh.app_server.RuntimeIntegrityError for failed immutable cache
    verification, exercised through the real pin_codex_bundle over fake
    executable bytes.
  * AppServerGateway._initialize_client maps that typed error to
    GatewayNotStartedError(reason='runtime_integrity') before any work
    request; a corrupt cache is never replaced.
  * Controller + SQLiteStore + MainSessionRouter over temporary databases:
    durable node-wide cooldown, untouched queued messages, cooldown
    persistence across restart, explicit mock-time advancement after an
    explicit fixture repair runs each untouched message exactly once, and
    historical failed/interrupted ledger ids never restart.
  * RuntimeIntegrityError after client initialization stays terminal and is
    never converted into a retryable deferral.

Deterministic and offline: fake executable bytes only, no subprocesses, no
model, no network, no real sleeps, no service or credential access.
"""

import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

WORKTREE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT))
sys.dont_write_bytecode = True

import fpga_mesh.controller as controller_module
import fpga_mesh.store as store_module
from fpga_mesh.app_server import AppServerClient, RuntimeIntegrityError, pin_codex_bundle
from fpga_mesh.controller import Controller
from fpga_mesh.gateway import AppServerGateway, GatewayConfig, GatewayNotStartedError
from fpga_mesh.protocol import MessageKind, SourceKind
from fpga_mesh.sessions import MainSessionRouter
from fpga_mesh.store import SQLiteStore
from tests.test_app_gateway import FakeSession, completed, message

TASK_ID = 'task-runtime-integrity'
SENT_ONE = datetime(2026, 10, 15, 8, 0, 0, tzinfo=timezone.utc)
SENT_TWO = datetime(2026, 10, 15, 8, 0, 1, tzinfo=timezone.utc)
CORRUPT_BYTES = b'corrupt-cached-runtime'


class IntegritySession(FakeSession):
    """FakeSession serving the verified model catalog for the real router."""

    async def request(self, method, params=None):
        if method == 'model/list':
            return {'data': [{
                'model': 'gpt-6-astra',
                'hidden': False,
                'supportedReasoningEfforts': [
                    {'reasoningEffort': 'max'},
                    {'reasoningEffort': 'ultra'},
                ],
            }]}
        return await super().request(method, params)


def queue_message(message_id, text, *, sent_at):
    return replace(
        message(),
        message_id=message_id,
        sender='DeepSeek-B',
        recipient='B/Astra-B',
        task_id=TASK_ID,
        task_version=1,
        sent_at=sent_at,
        kind=MessageKind.AGENT_REPORT,
        source=SourceKind.ASTRA,
        payload={'text': text},
    )


def gateway_config(base):
    return GatewayConfig(
        node_id='B', role='astra', model='gpt-6-astra', provider='openai',
        reasoning_effort='max', cwd=str(base), codex_home=str(base / 'unused-codex-home'),
    )


@contextmanager
def mock_time(advance_seconds):
    """Explicit mock time advancement for both the controller and the store."""
    offset = timedelta(seconds=advance_seconds)

    class ShiftedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(tz) + offset

    with mock.patch.object(controller_module, 'datetime', ShiftedDateTime), \
            mock.patch.object(store_module, '_utc_now',
                              lambda: datetime.now(timezone.utc) + offset):
        yield offset

class RuntimeIntegrityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self._closers = []

    async def asyncTearDown(self):
        for close in reversed(self._closers):
            close()

    def make_store(self):
        store = SQLiteStore(self.base / 'controller.sqlite')
        self._closers.append(store.close)
        return store

    def make_router(self, name='main-sessions.sqlite'):
        router = MainSessionRouter(self.base / name)
        self._closers.append(router.close)
        return router

    def corrupt_runtime(self):
        """Pin fake executables, then corrupt the immutable cached host."""
        source = self.base / 'desktop-runtime'
        source.mkdir(parents=True, exist_ok=True)
        (source / 'codex.exe').write_bytes(b'fake-offline-codex-executable')
        (source / 'codex-code-mode-host.exe').write_bytes(b'fake-offline-code-mode-host')
        cache = self.base / 'runtime-cache'
        binary = pin_codex_bundle(source / 'codex.exe', cache)
        cached_host = binary.parent / 'codex-code-mode-host.exe'
        original = cached_host.read_bytes()
        cached_host.write_bytes(CORRUPT_BYTES)
        return source, cache, cached_host, original

    def deferring_gateway(self, source, cache, router, attempts):
        def factory():
            attempts.append('factory')
            pin_codex_bundle(source / 'codex.exe', cache)
            raise AssertionError('corrupt cache unexpectedly accepted')
        return AppServerGateway(gateway_config(self.base), client_factory=factory,
                                session_router=router, startup_retry_delays=())

    @staticmethod
    def read_inbound(path):
        connection = sqlite3.connect(path)
        try:
            rows = connection.execute(
                'SELECT message_id, attempts, last_error, next_attempt_at, processed_at '
                'FROM inbound ORDER BY message_id').fetchall()
        finally:
            connection.close()
        return {row[0]: row[1:] for row in rows}

    @staticmethod
    def read_events(path):
        connection = sqlite3.connect(path)
        try:
            rows = connection.execute(
                'SELECT event_id, kind, payload FROM events '
                'ORDER BY created_at, event_id').fetchall()
        finally:
            connection.close()
        return [{'event_id': row[0], 'kind': row[1], 'payload': json.loads(row[2])}
                for row in rows]

    async def test_corrupt_or_missing_cached_runtime_fails_closed_without_replacement(self):
        source = self.base / 'desktop-runtime'
        source.mkdir(parents=True, exist_ok=True)
        (source / 'codex.exe').write_bytes(b'fake-offline-codex-executable')
        (source / 'codex-code-mode-host.exe').write_bytes(b'fake-offline-code-mode-host')
        cache = self.base / 'runtime-cache'
        binary = pin_codex_bundle(source / 'codex.exe', cache)
        cached_host = binary.parent / 'codex-code-mode-host.exe'
        original = cached_host.read_bytes()
        self.assertNotEqual(original, CORRUPT_BYTES)
        self.assertTrue(issubclass(RuntimeIntegrityError, RuntimeError))

        cached_host.write_bytes(CORRUPT_BYTES)
        snapshot = sorted(item.name for item in cache.iterdir())
        for _ in range(2):
            with self.assertRaises(RuntimeIntegrityError) as caught:
                pin_codex_bundle(source / 'codex.exe', cache)
            self.assertIn('incomplete or changed', str(caught.exception))
        self.assertEqual(cached_host.read_bytes(), CORRUPT_BYTES)
        self.assertEqual(sorted(item.name for item in cache.iterdir()), snapshot)

        cached_host.unlink()
        with self.assertRaises(RuntimeIntegrityError):
            pin_codex_bundle(source / 'codex.exe', cache)
        self.assertFalse(cached_host.exists())
        self.assertEqual(sorted(item.name for item in cache.iterdir()), snapshot)

        cached_host.write_bytes(original)
        self.assertEqual(pin_codex_bundle(source / 'codex.exe', cache), binary)

    async def test_gateway_maps_typed_integrity_error_before_any_work(self):
        source, cache, cached_host, _ = self.corrupt_runtime()
        router = self.make_router()
        session = IntegritySession()
        attempts = []
        gateway = self.deferring_gateway(source, cache, router, attempts)
        msg = queue_message('factory-phase', 'factory phase work', sent_at=SENT_ONE)
        with self.assertRaises(GatewayNotStartedError) as caught:
            await gateway.handle(msg)
        self.assertEqual(caught.exception.reason, 'runtime_integrity')
        self.assertTrue(caught.exception.safe_to_retry)
        self.assertEqual(attempts, ['factory'])
        self.assertEqual(router.result('factory-phase')['status'], 'queued')
        self.assertIn('runtime_integrity', router.result('factory-phase')['error'])
        self.assertEqual(session.requests, [])
        self.assertEqual(cached_host.read_bytes(), CORRUPT_BYTES)

        class InitializeIntegritySession(FakeSession):
            async def request(self, method, params=None):
                if method == 'initialize':
                    raise RuntimeIntegrityError('initialize-time integrity failure')
                return await super().request(method, params)

        session2 = InitializeIntegritySession()
        router2 = self.make_router('main-sessions-2.sqlite')
        gateway2 = AppServerGateway(
            gateway_config(self.base),
            client_factory=lambda: AppServerClient(session2, client_version='offline-test'),
            session_router=router2, startup_retry_delays=())
        msg2 = queue_message('initialize-phase', 'initialize phase work', sent_at=SENT_TWO)
        with self.assertRaises(GatewayNotStartedError) as caught2:
            await gateway2.handle(msg2)
        self.assertEqual(caught2.exception.reason, 'runtime_integrity')
        self.assertEqual(router2.result('initialize-phase')['status'], 'queued')
        self.assertFalse(session2.is_alive)
        self.assertNotIn('turn/start', [method for method, _ in session2.requests])

    async def test_deferred_integrity_failure_preserves_other_queued_messages(self):
        source, cache, _, _ = self.corrupt_runtime()
        store = self.make_store()
        router = self.make_router()
        attempts = []
        controller = Controller(
            store, self.deferring_gateway(source, cache, router, attempts))
        await controller.offer(queue_message('queued-1', 'deferred work one', sent_at=SENT_ONE))
        await controller.offer(queue_message('queued-2', 'deferred work two', sent_at=SENT_TWO))
        await controller.run_until_idle()

        self.assertEqual(attempts, ['factory'])
        self.assertEqual(router.result('queued-1')['status'], 'queued')
        self.assertIn('runtime_integrity', router.result('queued-1')['error'])
        self.assertIsNone(router.result('queued-2'))

        pending = {row.message.message_id: row for row in
                   store.pending_inbound(now=datetime.now(timezone.utc) + timedelta(minutes=2))}
        self.assertEqual(set(pending), {'queued-1', 'queued-2'})
        self.assertEqual(pending['queued-1'].attempts, 1)
        self.assertIn('deferred before execution', pending['queued-1'].last_error)
        self.assertIn('runtime_integrity', pending['queued-1'].last_error)
        self.assertEqual(pending['queued-2'].attempts, 0)
        self.assertIsNone(pending['queued-2'].last_error)
        self.assertIsNone(pending['queued-2'].next_attempt_at)
        self.assertIsNone(pending['queued-2'].processed_at)

        cooldown = store.load_gateway_retry()
        self.assertIsNotNone(cooldown)
        self.assertGreater(cooldown, datetime.now(timezone.utc))
        self.assertEqual(cooldown, pending['queued-1'].next_attempt_at)

        deferred_events = [event for event in self.read_events(store.path)
                           if event['kind'] == 'gateway_deferred']
        self.assertEqual(len(deferred_events), 1)
        self.assertEqual(deferred_events[0]['event_id'], 'gateway-deferred:queued-1:0')
        self.assertEqual(deferred_events[0]['payload']['message_id'], 'queued-1')
        self.assertEqual(deferred_events[0]['payload']['reason'], 'runtime_integrity')
        self.assertFalse(deferred_events[0]['payload']['execution_started'])

        await controller.run_until_idle()
        self.assertEqual(attempts, ['factory'])
        self.assertEqual(router.result('queued-1')['status'], 'queued')
        self.assertIsNone(router.result('queued-2'))

    async def test_restart_persists_cooldown_and_keeps_queue_untouched(self):
        source, cache, _, _ = self.corrupt_runtime()
        store = self.make_store()
        router = self.make_router()
        attempts = []
        controller = Controller(
            store, self.deferring_gateway(source, cache, router, attempts))
        await controller.offer(queue_message('cooldown-1', 'deferred one', sent_at=SENT_ONE))
        await controller.offer(queue_message('cooldown-2', 'deferred two', sent_at=SENT_TWO))
        await controller.run_until_idle()
        self.assertEqual(attempts, ['factory'])
        cooldown = store.load_gateway_retry()
        self.assertIsNotNone(cooldown)
        before = self.read_inbound(store.path)
        store.close()
        router.close()
        router = self.make_router()
        self.assertEqual(router.result('cooldown-1')['status'], 'queued')

        restarted_store = SQLiteStore(store.path)
        self._closers.append(restarted_store.close)
        restart_attempts = []
        restarted = Controller(
            restarted_store,
            self.deferring_gateway(source, cache, router, restart_attempts))
        self.assertEqual(restarted._gateway_retry_at, cooldown)
        await restarted.run_until_idle()
        self.assertEqual(restart_attempts, [])
        self.assertEqual(attempts, ['factory'])
        self.assertEqual(self.read_inbound(store.path), before)
        self.assertEqual(router.result('cooldown-1')['status'], 'queued')
        self.assertIsNone(router.result('cooldown-2'))

    async def test_repair_and_mock_time_advance_runs_untouched_work_exactly_once(self):
        source, cache, cached_host, original_host = self.corrupt_runtime()
        store = self.make_store()
        router = self.make_router()
        attempts = []
        controller = Controller(
            store, self.deferring_gateway(source, cache, router, attempts))
        await controller.offer(queue_message('repair-1', 'repaired work one', sent_at=SENT_ONE))
        await controller.offer(queue_message('repair-2', 'repaired work two', sent_at=SENT_TWO))
        await controller.run_until_idle()
        self.assertEqual(attempts, ['factory'])
        self.assertIsNotNone(store.load_gateway_retry())
        store.close()
        router.close()
        router = self.make_router()
        self.assertEqual(router.result('repair-1')['status'], 'queued')

        store = SQLiteStore(store.path)
        self._closers.append(store.close)
        restart_attempts = []
        controller = Controller(
            store, self.deferring_gateway(source, cache, router, restart_attempts))
        await controller.run_until_idle()
        self.assertEqual(restart_attempts, [])
        self.assertEqual(attempts, ['factory'])

        cached_host.write_bytes(original_host)
        session = IntegritySession()
        session.notifications.extend([completed(), completed()])
        final_attempts = []

        def factory():
            final_attempts.append('factory')
            binary_path = pin_codex_bundle(source / 'codex.exe', cache)
            return AppServerClient(session, client_version='offline-test')

        gateway = AppServerGateway(gateway_config(self.base), client_factory=factory,
                                   session_router=router, startup_retry_delays=())
        controller = Controller(store, gateway)
        with mock_time(45):
            await controller.run_until_idle()

        self.assertEqual(final_attempts, ['factory'])
        self.assertEqual(attempts, ['factory'])
        turn_texts = [params['input'][0]['text'] for method, params in session.requests
                      if method == 'turn/start']
        self.assertEqual(len(turn_texts), 2)
        self.assertEqual(sum('repaired work one' in text for text in turn_texts), 1)
        self.assertEqual(sum('repaired work two' in text for text in turn_texts), 1)
        self.assertEqual(router.result('repair-1')['status'], 'completed')
        self.assertEqual(router.result('repair-2')['status'], 'completed')
        self.assertEqual(store.pending_inbound(), [])
        self.assertIsNone(store.load_gateway_retry())

        with mock_time(45):
            await controller.run_until_idle()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(len(final_attempts), 1)
        self.assertEqual(sum(1 for method, _ in session.requests if method == 'turn/start'), 2)

    async def test_failed_and_interrupted_ledger_ids_never_restart_after_repair(self):
        source = self.base / 'desktop-runtime'
        source.mkdir(parents=True, exist_ok=True)
        (source / 'codex.exe').write_bytes(b'fake-offline-codex-executable')
        (source / 'codex-code-mode-host.exe').write_bytes(b'fake-offline-code-mode-host')
        cache = self.base / 'runtime-cache'
        pin_codex_bundle(source / 'codex.exe', cache)
        store = self.make_store()
        router = self.make_router()
        router.record('legacy-failed', TASK_ID, 'failed', error='historical failure')
        router.record('legacy-interrupted', TASK_ID, 'interrupted', error='historical interruption')
        calls = []

        def factory():
            calls.append('factory')
            raise AssertionError('terminal ledger entries must not initialize a client')

        gateway = AppServerGateway(gateway_config(self.base), client_factory=factory,
                                   session_router=router, startup_retry_delays=())
        results = []
        controller = Controller(
            store, gateway,
            on_result=lambda envelope, result: results.append((envelope.message_id, result)))
        await controller.offer(queue_message('legacy-failed', 'must not restart failed', sent_at=SENT_ONE))
        await controller.offer(queue_message('legacy-interrupted', 'must not restart interrupted', sent_at=SENT_TWO))
        await controller.run_until_idle()

        self.assertEqual(calls, [])
        by_id = dict(results)
        self.assertEqual(set(by_id), {'legacy-failed', 'legacy-interrupted'})
        for result in by_id.values():
            self.assertFalse(result.accepted)
            self.assertTrue(result.output['recovery_required'])
        self.assertEqual(by_id['legacy-failed'].output['status'], 'failed')
        self.assertEqual(by_id['legacy-interrupted'].output['status'], 'interrupted')
        self.assertEqual(router.result('legacy-failed')['status'], 'failed')
        self.assertEqual(router.result('legacy-failed')['error'], 'historical failure')
        self.assertEqual(router.result('legacy-interrupted')['status'], 'interrupted')
        self.assertEqual(store.pending_inbound(), [])

        await controller.run_until_idle()
        self.assertEqual(calls, [])

    async def test_post_start_integrity_error_stays_terminal_without_retry(self):
        class PostStartIntegritySession(IntegritySession):
            async def request(self, method, params=None):
                if method == 'turn/start':
                    self.turn_attempts = getattr(self, 'turn_attempts', 0) + 1
                    raise RuntimeIntegrityError('post-start runtime integrity failure')
                return await super().request(method, params)

        source = self.base / 'desktop-runtime'
        source.mkdir(parents=True, exist_ok=True)
        (source / 'codex.exe').write_bytes(b'fake-offline-codex-executable')
        (source / 'codex-code-mode-host.exe').write_bytes(b'fake-offline-code-mode-host')
        cache = self.base / 'runtime-cache'
        pin_codex_bundle(source / 'codex.exe', cache)

        router = self.make_router()
        session = PostStartIntegritySession()
        calls = []

        def factory():
            calls.append('factory')
            return AppServerClient(session, client_version='offline-test')

        gateway = AppServerGateway(gateway_config(self.base), client_factory=factory,
                                   session_router=router, startup_retry_delays=())
        direct = queue_message('direct-post-start', 'work that must not replay', sent_at=SENT_ONE)
        with self.assertRaises(RuntimeIntegrityError) as caught:
            await gateway.handle(direct)
        self.assertNotIsInstance(caught.exception, GatewayNotStartedError)
        self.assertFalse(getattr(caught.exception, 'safe_to_retry', False))
        self.assertEqual(calls, ['factory'])
        self.assertEqual(router.result('direct-post-start')['status'], 'failed')
        self.assertIn('post-start runtime integrity failure',
                      router.result('direct-post-start')['error'])
        self.assertFalse(session.is_alive)
        turn_starts = session.turn_attempts
        self.assertEqual(turn_starts, 1)

        replayed = await gateway.handle(direct)
        self.assertFalse(replayed.accepted)
        self.assertTrue(replayed.output['recovery_required'])
        self.assertEqual(calls, ['factory'])
        self.assertEqual(session.turn_attempts, 1)
        self.assertEqual(router.result('direct-post-start')['status'], 'failed')

        store = self.make_store()
        router2 = self.make_router('main-sessions-2.sqlite')
        session2 = PostStartIntegritySession()
        calls2 = []

        def factory2():
            calls2.append('factory')
            return AppServerClient(session2, client_version='offline-test')

        gateway2 = AppServerGateway(gateway_config(self.base), client_factory=factory2,
                                    session_router=router2, startup_retry_delays=())
        results = []
        controller = Controller(
            store, gateway2,
            on_result=lambda envelope, result: results.append((envelope.message_id, result)))
        await controller.offer(queue_message('controller-post-start', 'controller work', sent_at=SENT_TWO))
        await controller.run_until_idle()
        self.assertEqual(calls2, ['factory'])
        self.assertEqual(router2.result('controller-post-start')['status'], 'failed')
        inbound = self.read_inbound(store.path)['controller-post-start']
        self.assertEqual(inbound[0], 1)
        self.assertIsNotNone(inbound[2])
        self.assertIsNone(inbound[3])
        self.assertEqual([event for event in self.read_events(store.path)
                          if event['kind'] == 'gateway_deferred'], [])
        self.assertEqual(session2.turn_attempts, 1)

        with mock_time(45):
            await controller.run_until_idle()
        self.assertEqual(calls2, ['factory'])
        self.assertEqual(session2.turn_attempts, 1)
        self.assertEqual(router2.result('controller-post-start')['status'], 'failed')
        captured = dict(results)
        self.assertFalse(captured['controller-post-start'].accepted)
        self.assertTrue(captured['controller-post-start'].output['recovery_required'])
        self.assertIsNotNone(self.read_inbound(store.path)['controller-post-start'][3])


if __name__ == '__main__':
    unittest.main()
