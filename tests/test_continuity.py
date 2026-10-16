"""Continuity-repair regression tests for the runtime-continuity worktree.

Scope (offline and deterministic; every database lives under a
TemporaryDirectory, no model/network/Feishu/GitHub/hardware/deployment state):
  * fpga_mesh/continuity.py: read-only ledger collection, explicit watches,
    incident classification, one-shot repair claims, durable receipts and the
    STOP-aware single continuation dispatch.
  * Runtime hooks: NodeRuntime wiring of ContinuityMonitor, start/stop
    lifecycle, snapshot diagnostics, controller/child activity notifications.
  * ProjectActions front door: fpga_self_check, fpga_continuity_watch,
    fpga_continuity_receipt, fpga_continuity_repair.

Deliberately verified here:
  * A persisted terminal result reaches the exact existing recipient inbox as
    one deterministic continuation turn, settled by an actual receipt.
  * Crash/restart before the journal state commit re-offers the same envelope
    id without a duplicate inbox row or a second turn.
  * Human STOP and snapshot pause block dispatch; resume re-enables it.
  * Unknown repair outcomes are terminal and never re-claimed; normal
    active/backoff waiting and human pauses are not repair faults.
  * Reserved-unbound threshold, source/task/version conflicts and loaded-vs-disk
    source drift are reported explicitly.
  * A terminal child is reconciled, never replayed; the service keeps running
    and source ledgers stay byte-identical after a read-only cycle.

Observing is not permission to replay: these tests assert absence of replay,
not its existence.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT))
sys.dont_write_bytecode = True

import fpga_mesh
from fpga_mesh.child_control import ChildCoordinator, LocalControlFileClient
from fpga_mesh.continuity import ContinuityJournal, ContinuityMonitor, collect, source_hashes
from fpga_mesh.protocol import Envelope, MessageKind, SourceKind
from fpga_mesh.runtime import NodeConfig, NodeRuntime
from fpga_mesh.sessions import MainSessionRouter, now as now_text
from fpga_mesh.store import SQLiteStore

LEDGERS = ('state.sqlite', 'main_sessions.sqlite', 'child_jobs.sqlite')
SOURCE_MODULES = {'runtime.py', 'controller.py', 'gateway.py', 'app_server.py',
                  'child_control.py', 'project_control.py', 'continuity.py', 'sessions.py', 'update.py'}


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def utc():
    return datetime.now(timezone.utc)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def continuation_message_id(watch_id: str) -> str:
    return 'continuity:' + hashlib.sha256(watch_id.encode()).hexdigest()


def peer_report(message_id: str, *, task_id: str = 't', version: int = 1) -> Envelope:
    return Envelope(message_id=message_id, project_id='fpga-main', sender='DeepSeek-B',
                    recipient='B/Astra-B', task_id=task_id, task_version=version,
                    sent_at=utc(), kind=MessageKind.AGENT_REPORT, source=SourceKind.DEEPSEEK_POOL,
                    payload={'text': message_id})


def human_control(message_id: str, kind: MessageKind, *, sent_at: datetime, scope: str = 'all') -> Envelope:
    return Envelope(message_id=message_id, project_id='fpga-main', sender='human',
                    recipient='B/Astra-B', task_id='human-task', task_version=1, sent_at=sent_at,
                    kind=kind, source=SourceKind.HUMAN, payload={'scope': scope})


def snapshot(now: datetime, **overrides) -> dict:
    value = {'observed_at': iso(now), 'pending': [], 'pause': {}, 'retry': {},
             'sessions': [], 'runs': [], 'jobs': []}
    value.update(overrides)
    return value


def pending_row(message_id: str, now: datetime, *, age_seconds: float = 3600.0, **extra) -> dict:
    return {'message_id': message_id, 'task_id': 't', 'task_version': 1,
            'received_at': iso(now - timedelta(seconds=age_seconds)),
            'next_attempt_at': None, **extra}


def job_row(job_id: str, now: datetime, *, status: str = 'reserved', task_id: str = 't',
            version: int = 1, agent: str | None = None, age_seconds: float = 7200.0) -> dict:
    stamp = iso(now - timedelta(seconds=age_seconds))
    return {'job_id': job_id, 'task_id': task_id, 'task_version': version, 'work_id': 'w',
            'status': status, 'native_agent_id': agent, 'ownership_json': '[]',
            'created_at': stamp, 'updated_at': stamp}


def run_row(message_id: str, now: datetime, *, status: str = 'completed', task_id: str = 't') -> dict:
    return {'message_id': message_id, 'task_id': task_id, 'task_version': 1, 'status': status,
            'updated_at': iso(now)}


class LedgerCollectionTests(unittest.TestCase):
    """collect() reads the three real ledgers and never writes them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def make_ledgers(self) -> tuple[SQLiteStore, MainSessionRouter, ChildCoordinator]:
        store = SQLiteStore(self.base / 'state.sqlite')
        router = MainSessionRouter(self.base / 'main_sessions.sqlite')
        children = ChildCoordinator(node_id='B', project_id='fpga-main', pool=None,
                                    state_path=self.base / 'child_jobs.sqlite')
        return store, router, children

    def test_collect_reads_existing_ledgers_and_feeds_real_incidents(self):
        store, router, children = self.make_ledgers()
        journal = ContinuityJournal(self.base / 'continuity.sqlite')
        self.addCleanup(journal.close)
        try:
            store.accept_inbound(peer_report('pending-1'))
            router.db.execute('INSERT INTO main_sessions VALUES (?,?,?,?,?,?,?,?,?)',
                              ('t', 'thread-1', 1, 'gpt-6-astra', 'ultra', 'execution', 'title',
                               None, now_text()))
            router.db.commit()
            router.record('run-1', 't', 'completed', result={'text': 'ok'})
            job = children.native_reserve(task_id='t', task_version=1, text='fixture lease',
                                          work_id='w', ownership=[], reason='fixture native lease')
            detected = collect(self.base)
            self.assertEqual(detected['pause'], {})
            self.assertEqual(detected['retry'], {})
            self.assertEqual([item['message_id'] for item in detected['pending']], ['pending-1'])
            # collect() derives task_id/task_version from the persisted
            # envelope, so a real pending message carries its own task id.
            self.assertEqual(detected['pending'][0]['task_id'], 't')
            self.assertEqual(detected['pending'][0]['task_version'], 1)
            self.assertEqual(detected['sessions'][0]['thread_id'], 'thread-1')
            self.assertEqual(detected['runs'][0]['message_id'], 'run-1')
            self.assertEqual(detected['runs'][0]['status'], 'completed')
            self.assertEqual(detected['jobs'][0]['job_id'], job['job_id'])
            self.assertIsNone(detected['jobs'][0]['native_agent_id'])
            # The same snapshot classifies real rows without writing to them.
            report = journal.observe(detected, threshold=0)
            incidents = {item['incident_id']: item for item in report['incidents']}
            self.assertEqual(incidents['queue_wait:pending-1']['evidence']['disposition'],
                             'needs_inspection')
            unbound = incidents[f"unbound_reservation:{job['job_id']}"]
            self.assertTrue(unbound['active'])
            self.assertEqual(unbound['evidence']['disposition'], 'inspect_existing_app_receipts')
            self.assertEqual(journal.status()['watches'], [])
        finally:
            asyncio.run(children.close())
            router.close()
            store.close()

    def test_read_only_cycle_leaves_source_ledgers_byte_identical(self):
        store, router, children = self.make_ledgers()
        store.accept_inbound(peer_report('pending-1'))
        router.record('run-1', 't', 'completed')
        asyncio.run(children.close())
        router.close()
        store.close()
        before = {name: sha256_file(self.base / name) for name in LEDGERS}
        before_names = {path.name for path in self.base.iterdir()}
        detected = collect(self.base)
        journal = ContinuityJournal(self.base / 'continuity.sqlite')
        try:
            journal.observe(detected, loaded_hashes={'runtime.py': 'loaded'},
                            disk_hashes={'runtime.py': 'disk'}, threshold=0)
            kinds = {item['kind'] for item in journal.status()['incidents']}
            self.assertIn('runtime_source_drift', kinds)
            self.assertIn('queue_wait', kinds)
        finally:
            journal.close()
        after = {name: sha256_file(self.base / name) for name in LEDGERS}
        self.assertEqual(before, after, 'continuity must treat source ledgers as read-only')
        extra = {path.name for path in self.base.iterdir()} - before_names
        # Read-only WAL access may create -shm/-wal sidecars next to an
        # existing ledger; the journal itself is the only new database.
        sidecars = {f'{name}-{suffix}' for name in LEDGERS
                    for suffix in ('wal', 'shm', 'journal')}
        self.assertIn('continuity.sqlite', extra)
        self.assertTrue(extra <= sidecars | {'continuity.sqlite'},
                        f'unexpected files next to the ledgers: {extra - sidecars}')

    def test_source_hashes_cover_the_runtime_modules(self):
        hashes = source_hashes(Path(fpga_mesh.__file__).parent)
        self.assertEqual(set(hashes), SOURCE_MODULES)
        for name, digest in hashes.items():
            with self.subTest(name=name):
                self.assertEqual(len(digest), 64)
                int(digest, 16)

    def test_external_deliveries_are_read_only_and_legacy_absence_is_supported(self):
        store, router, children = self.make_ledgers()
        try:
            message = peer_report('app-wait')
            store.accept_inbound(message)
            router.defer_external(message, {'recipient_thread_id': 'real-app-thread',
                'declaration_hash': 'known-entry', 'reason': 'App recipient required'})
            store.mark_inbound_processed(message.message_id)
            before = router.db.total_changes
            detected = collect(self.base)
            self.assertEqual(detected['pending'], [])
            self.assertEqual(len(detected['external_deliveries']), 1)
            self.assertEqual(detected['external_deliveries'][0]['recipient_thread_id'], 'real-app-thread')
            self.assertEqual(detected['external_deliveries'][0]['reason'], 'App recipient required')
            self.assertEqual(router.db.total_changes, before)
            with router.db:
                router.db.execute('ALTER TABLE external_deliveries DROP COLUMN resolution_json')
            self.assertIsNone(collect(self.base)['external_deliveries'][0]['resolution'])
            # Simulate a legacy schema in this isolated fixture only.
            with router.db:
                router.db.execute('DROP TABLE external_deliveries')
            self.assertEqual(collect(self.base)['external_deliveries'], [])
        finally:
            asyncio.run(children.close())
            router.close()
            store.close()


class ObserveAndIncidentTests(unittest.TestCase):
    """Classification semantics of ContinuityJournal.observe()."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.now = utc()
        self.journal = ContinuityJournal(self.base / 'continuity.sqlite')
        self.addCleanup(self.journal.close)

    def incidents(self) -> dict:
        return {item['incident_id']: item for item in self.journal.status()['incidents']}

    def test_external_pending_is_a_handoff_obligation_not_terminal_or_repair(self):
        self.journal.watch(watch_id='external-watch', task_id='t', task_version=1,
            source_kind='main', source_id='app-wait', recipient_thread_id='app', auto_resume=True)
        delivery = {'message_id': 'app-wait', 'task_id': 't', 'task_version': 1,
                    'recipient_thread_id': 'app', 'reason': 'needs App delivery', 'status': 'pending'}
        current = snapshot(self.now, external_deliveries=[delivery], runs=[{
            'message_id': 'app-wait', 'task_id': 't', 'task_version': 1, 'status': 'delivery_pending'}])
        self.journal.observe(current)
        incident = self.incidents()['external_delivery_pending:app-wait']
        self.assertTrue(incident['active'])
        self.assertEqual(incident['evidence']['recipient_thread_id'], 'app')
        self.assertEqual(incident['evidence']['disposition'], 'app_delivery_required')
        self.assertEqual(self.journal.get_watch('external-watch')['state'], 'waiting')
        with self.assertRaises(ValueError):
            self.journal.repair(incident_id=incident['incident_id'], phase='claim', owner_thread_id='main')
        current['external_deliveries'][0]['status'] = 'consumed'
        current['runs'][0]['status'] = 'external_consumed'
        self.journal.observe(current)
        self.assertFalse(self.incidents()[incident['incident_id']]['active'])
        self.assertEqual(self.journal.get_watch('external-watch')['state'], 'waiting')

    def test_explicit_unconsumed_closure_resolves_incident_without_claiming_completion(self):
        delivery = {'message_id': 'withdrawn', 'task_id': 't', 'task_version': 2,
                    'recipient_thread_id': None, 'reason': 'bad declaration', 'status': 'pending',
                    'resolution': None}
        current = snapshot(self.now, external_deliveries=[delivery])
        self.journal.observe(current)
        self.assertTrue(self.incidents()['external_delivery_pending:withdrawn']['active'])
        for status in ('withdrawn_unconsumed', 'superseded_unconsumed'):
            delivery['status'] = status
            delivery['resolution'] = {'reviewer_thread_id': 'main', 'followup_work_id': 'next-work',
                                      'reason': 'confirmed never sent', 'evidence': 'actual review'}
            self.journal.observe(current)
            self.assertFalse(self.incidents()['external_delivery_pending:withdrawn']['active'])
            self.assertEqual(self.journal.status()['watches'], [])

    def test_monitor_failure_survives_recovery_without_repeated_incidents(self):
        self.journal.monitor_result('OperationalError: database unavailable')
        self.journal.monitor_result('OperationalError: database unavailable')
        self.assertEqual(len(self.incidents()), 1)
        self.journal.observe(snapshot(self.now))
        self.journal.monitor_result()
        reopened = ContinuityJournal(self.base / 'continuity.sqlite')
        self.addCleanup(reopened.close)
        status = reopened.status()
        self.assertIsNone(status['monitor']['error'])
        self.assertEqual(len(status['incidents']), 1)
        self.assertFalse(status['incidents'][0]['active'])
        self.assertEqual(status['incidents'][0]['evidence']['error'],
                         'OperationalError: database unavailable')

    def test_terminal_child_marks_watch_ready_with_reconcile_disposition(self):
        self.journal.watch(watch_id='w-failed', task_id='t', task_version=1, source_kind='child',
                           source_id='j1', recipient_thread_id='thread-1', auto_resume=True)
        self.journal.watch(watch_id='w-done', task_id='t', task_version=1, source_kind='child',
                           source_id='j2', recipient_thread_id='thread-1')
        self.journal.observe(snapshot(self.now, jobs=[job_row('j1', self.now, status='failed'),
                                                      job_row('j2', self.now, status='completed')]))
        self.assertEqual(self.journal.get_watch('w-failed')['state'], 'ready')
        self.assertEqual(self.journal.get_watch('w-failed')['event_status'], 'failed')
        self.assertEqual(self.journal.get_watch('w-done')['event_status'], 'completed')
        incidents = self.incidents()
        self.assertEqual(incidents['result_unconsumed:w-failed']['evidence']['disposition'],
                         'reconcile_only')
        self.assertEqual(incidents['result_unconsumed:w-done']['evidence']['disposition'],
                         'continue_remaining_work')
        self.assertTrue(incidents['result_unconsumed:w-failed']['active'])

    def test_nonterminal_source_is_normal_computation_not_a_timeout_incident(self):
        self.journal.watch(watch_id='w-run', task_id='t', task_version=1, source_kind='child',
                           source_id='j1', recipient_thread_id='thread-1', auto_resume=True)
        self.journal.observe(snapshot(self.now, jobs=[
            job_row('j1', self.now, status='running', agent='agent-1', age_seconds=8 * 3600)]))
        watch = self.journal.get_watch('w-run')
        self.assertEqual(watch['state'], 'waiting')
        self.assertIsNone(watch['event_status'])
        self.assertNotIn('result_unconsumed:w-run', self.incidents())

    def test_watch_source_missing_and_task_or_version_conflicts_are_explicit(self):
        self.journal.watch(watch_id='w-missing', task_id='t', task_version=1, source_kind='child',
                           source_id='absent', recipient_thread_id='thread-1')
        self.journal.watch(watch_id='w-task', task_id='t', task_version=1, source_kind='child',
                           source_id='j1', recipient_thread_id='thread-1')
        self.journal.watch(watch_id='w-version', task_id='t', task_version=2, source_kind='child',
                           source_id='j2', recipient_thread_id='thread-1')
        self.journal.observe(snapshot(self.now, jobs=[
            job_row('j1', self.now, task_id='other-task', version=1),
            job_row('j2', self.now, task_id='t', version=1)]))
        incidents = self.incidents()
        self.assertEqual(incidents['watch_source_missing:w-missing']['evidence'],
                         {'source_id': 'absent'})
        for watch_id in ('w-task', 'w-version'):
            with self.subTest(watch=watch_id):
                self.assertIn(f'watch_source_conflict:{watch_id}', incidents)
                self.assertEqual(self.journal.get_watch(watch_id)['state'], 'waiting')

    def test_active_backoff_and_pause_are_not_repair_faults(self):
        self.journal.observe(snapshot(
            self.now, pending=[pending_row('m-active', self.now)],
            runs=[{'message_id': 'r1', 'task_id': 't', 'status': 'running',
                   'updated_at': iso(self.now)}]), threshold=0)
        self.journal.observe(snapshot(
            self.now, pending=[pending_row('m-backoff', self.now,
                                           next_attempt_at=iso(self.now + timedelta(minutes=5)))]),
            threshold=0)
        self.journal.observe(snapshot(
            self.now, pause={'paused_at': iso(self.now)},
            pending=[pending_row('m-paused', self.now)]), threshold=0)
        incidents = self.incidents()
        self.assertEqual(incidents['queue_wait:m-active']['evidence']['disposition'],
                         'normal_active_wait')
        self.assertEqual(incidents['queue_wait:m-backoff']['evidence']['disposition'],
                         'scheduled_backoff')
        self.assertEqual(incidents['queue_wait:m-paused']['evidence']['disposition'], 'human_paused')
        for incident_id in ('queue_wait:m-active', 'queue_wait:m-backoff', 'queue_wait:m-paused'):
            with self.subTest(incident=incident_id):
                with self.assertRaises(ValueError):
                    self.journal.repair(incident_id=incident_id, phase='claim',
                                        owner_thread_id='owner-1')

    def test_reserved_unbound_threshold_and_resolution(self):
        fresh = job_row('j-fresh', self.now, age_seconds=5)
        bound = job_row('j-bound', self.now, agent='agent-1')
        old = job_row('j-old', self.now, age_seconds=2 * 3600)
        self.journal.observe(snapshot(self.now, jobs=[fresh, bound, old]), threshold=900)
        incidents = self.incidents()
        self.assertNotIn('unbound_reservation:j-fresh', incidents)
        self.assertNotIn('unbound_reservation:j-bound', incidents)
        self.assertEqual(incidents['unbound_reservation:j-old']['evidence']['disposition'],
                         'inspect_existing_app_receipts')
        # The reservation resolves once an actual agent binding is observed.
        self.journal.observe(snapshot(self.now, jobs=[{**old, 'status': 'running',
                                                       'native_agent_id': 'agent-2'}]),
                             threshold=900)
        self.assertFalse(self.incidents()['unbound_reservation:j-old']['active'])

    def test_loaded_disk_source_drift_is_reported_as_fenced_update_required(self):
        loaded = {'runtime.py': 'loaded-digest'}
        disk = {'runtime.py': 'disk-digest'}
        self.journal.observe(snapshot(self.now), loaded_hashes=loaded, disk_hashes=disk)
        drift = self.incidents()['runtime_source_drift:loaded']
        self.assertEqual(drift['evidence']['disposition'], 'idle_fenced_update_required')
        self.assertEqual(drift['evidence']['loaded'], loaded)
        self.assertEqual(drift['evidence']['disk'], disk)
        self.journal.observe(snapshot(self.now), loaded_hashes=loaded, disk_hashes=dict(loaded))
        self.assertFalse(self.incidents()['runtime_source_drift:loaded']['active'])

    def test_overlapping_live_writers_are_reported_without_cancelling(self):
        running = {**job_row('j-a', self.now, status='running', agent='agent-1'),
                   'route': 'gpt_native', 'error': None, 'ownership_json': '["src/a.py"]'}
        unconfirmed = {**job_row('j-b', self.now, status='interrupted'),
                       'route': 'gpt_native', 'error': 'native stop unconfirmed',
                       'ownership_json': '["src/a.py"]'}
        disjoint = {**job_row('j-c', self.now, status='running', agent='agent-2'),
                    'route': 'gpt_native', 'error': None, 'ownership_json': '["src/c.py"]'}
        legacy = {**job_row('j-d', self.now, status='interrupted'),
                  'route': 'deepseek', 'error': None, 'ownership_json': '["src/a.py"]'}
        self.journal.observe(snapshot(self.now, jobs=[running, unconfirmed, disjoint, legacy]))
        overlaps = {key: item for key, item in self.incidents().items()
                    if key.startswith('writer_overlap')}
        self.assertEqual(list(overlaps), ['writer_overlap:j-a:j-b'])
        self.assertEqual(overlaps['writer_overlap:j-a:j-b']['evidence']['disposition'],
                         'inspect_ownership_do_not_cancel')
        self.assertEqual(overlaps['writer_overlap:j-a:j-b']['evidence']['jobs'], ['j-a', 'j-b'])

    def test_watch_identity_is_stable_and_conflicts_are_rejected(self):
        created = self.journal.watch(watch_id='w1', task_id='t', task_version=1, source_kind='child',
                                     source_id='j1', recipient_thread_id='thread-1')
        repeated = self.journal.watch(watch_id='w1', task_id='t', task_version=1, source_kind='child',
                                      source_id='j1', recipient_thread_id='thread-1')
        self.assertEqual(created['created_at'], repeated['created_at'])
        self.assertEqual(created['spec'], repeated['spec'])
        with self.assertRaises(ValueError):
            self.journal.watch(watch_id='w1', task_id='t', task_version=2, source_kind='child',
                               source_id='j1', recipient_thread_id='thread-1')
        with self.assertRaises(ValueError):
            self.journal.watch(watch_id='w2', task_id='t', task_version=0, source_kind='child',
                               source_id='j1', recipient_thread_id='thread-1')
        with self.assertRaises(ValueError):
            self.journal.watch(watch_id='w2', task_id='t', task_version=1, source_kind='peer',
                               source_id='j1', recipient_thread_id='thread-1')
        with self.assertRaises(ValueError):
            self.journal.watch(watch_id='  ', task_id='t', task_version=1, source_kind='child',
                               source_id='j1', recipient_thread_id='thread-1')
        # One source tuple is watched once; a second watch must reuse the id.
        with self.assertRaises(ValueError) as caught:
            self.journal.watch(watch_id='w-second', task_id='t', task_version=1,
                               source_kind='child', source_id='j1',
                               recipient_thread_id='thread-1')
        self.assertIn('source already watched; reuse w1', str(caught.exception))
        with self.assertRaises(KeyError):
            self.journal.get_watch('absent')


class RepairClaimTests(unittest.TestCase):
    """One-shot, owner-bound repair claims; unknown outcomes never repeat."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.now = utc()
        self.journal = ContinuityJournal(self.base / 'continuity.sqlite')
        self.addCleanup(self.journal.close)
        self.journal.observe(snapshot(self.now, jobs=[job_row('j-old', self.now, age_seconds=2 * 3600)]),
                             threshold=900)
        self.incident = 'unbound_reservation:j-old'

    def test_claim_created_started_records_the_actual_owner_thread_and_turn(self):
        claim = self.journal.repair(incident_id=self.incident, phase='claim', owner_thread_id='owner-1')
        self.assertTrue(claim['execute'])
        self.assertEqual(claim['phase'], 'claimed')
        created = self.journal.repair(incident_id=self.incident, phase='created',
                                      owner_thread_id='owner-1', thread_id='new-thread')
        self.assertFalse(created['execute'])
        self.assertEqual(created['thread_id'], 'new-thread')
        started = self.journal.repair(incident_id=self.incident, phase='started',
                                      owner_thread_id='owner-1', thread_id='new-thread',
                                      turn_id='turn-9')
        self.assertEqual(started['phase'], 'started')
        self.assertEqual(started['turn_id'], 'turn-9')
        persisted = json.loads(self.journal.db.execute(
            'SELECT repair FROM incidents WHERE incident_id=?', (self.incident,)).fetchone()[0])
        self.assertEqual(persisted['owner_thread_id'], 'owner-1')

    def test_second_claim_returns_the_existing_claim_without_execute(self):
        first = self.journal.repair(incident_id=self.incident, phase='claim', owner_thread_id='owner-1')
        again = self.journal.repair(incident_id=self.incident, phase='claim', owner_thread_id='owner-2')
        self.assertTrue(first['execute'])
        self.assertFalse(again['execute'])
        self.assertEqual(again['owner_thread_id'], 'owner-1')
        self.assertEqual(again['phase'], 'claimed')

    def test_unknown_outcome_is_terminal_and_never_reclaimed_or_replayed(self):
        self.journal.repair(incident_id=self.incident, phase='claim', owner_thread_id='owner-1')
        unknown = self.journal.repair(incident_id=self.incident, phase='unknown',
                                      owner_thread_id='owner-1')
        self.assertEqual(unknown['phase'], 'unknown')
        repeated = self.journal.repair(incident_id=self.incident, phase='claim',
                                       owner_thread_id='owner-8')
        self.assertFalse(repeated['execute'])
        with self.assertRaises(ValueError):
            self.journal.repair(incident_id=self.incident, phase='created',
                                owner_thread_id='owner-1', thread_id='late-thread')
        with self.assertRaises(ValueError):
            self.journal.repair(incident_id=self.incident, phase='started',
                                owner_thread_id='owner-1', thread_id='late-thread',
                                turn_id='turn-late')

    def test_transitions_require_the_same_owner_and_the_exact_created_thread(self):
        self.journal.repair(incident_id=self.incident, phase='claim', owner_thread_id='owner-1')
        with self.assertRaises(ValueError):
            self.journal.repair(incident_id=self.incident, phase='created',
                                owner_thread_id='owner-2', thread_id='new-thread')
        self.journal.repair(incident_id=self.incident, phase='created',
                            owner_thread_id='owner-1', thread_id='new-thread')
        with self.assertRaises(ValueError):
            self.journal.repair(incident_id=self.incident, phase='started',
                                owner_thread_id='owner-1', thread_id='other-thread',
                                turn_id='turn-9')
        self.journal.repair(incident_id=self.incident, phase='started',
                            owner_thread_id='owner-1', thread_id='new-thread', turn_id='turn-9')
        with self.assertRaises(ValueError):
            self.journal.repair(incident_id=self.incident, phase='unknown',
                                owner_thread_id='owner-1')

    def test_claim_rejected_for_pause_normal_wait_and_inactive_incidents(self):
        with self.assertRaises(KeyError):
            self.journal.repair(incident_id='absent', phase='claim', owner_thread_id='owner-1')
        with self.assertRaises(ValueError):
            self.journal.repair(incident_id=self.incident, phase='claim', owner_thread_id='')
        with self.assertRaises(ValueError):
            self.journal.repair(incident_id=self.incident, phase='review', owner_thread_id='owner-1')
        with self.assertRaises(ValueError):
            self.journal.repair(incident_id=self.incident, phase='claim',
                                owner_thread_id='owner-1', paused=True)
        # The incident resolves and loses activity; a later claim is denied.
        self.journal.observe(snapshot(self.now, jobs=[]), threshold=900)
        with self.assertRaises(ValueError):
            self.journal.repair(incident_id=self.incident, phase='claim', owner_thread_id='owner-1')


class ReceiptTests(unittest.TestCase):
    """Receipts require the designated recipient thread and a real turn."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.now = utc()
        self.journal = ContinuityJournal(self.base / 'continuity.sqlite')
        self.addCleanup(self.journal.close)
        self.journal.watch(watch_id='w1', task_id='t', task_version=1, source_kind='child',
                           source_id='j1', recipient_thread_id='thread-1', auto_resume=True)

    def test_receipt_requires_terminal_source_actual_thread_and_evidence(self):
        with self.assertRaises(ValueError):
            self.journal.receipt(watch_id='w1', thread_id='thread-1', turn_id='turn-1',
                                 evidence='too early')
        self.journal.observe(snapshot(self.now, jobs=[job_row('j1', self.now, status='completed')]))
        self.assertEqual(self.journal.get_watch('w1')['state'], 'ready')
        with self.assertRaises(ValueError):
            self.journal.receipt(watch_id='w1', thread_id='other-thread', turn_id='turn-1',
                                 evidence='wrong recipient')
        with self.assertRaises(ValueError):
            self.journal.receipt(watch_id='w1', thread_id='thread-1', turn_id='', evidence='no turn')
        with self.assertRaises(ValueError):
            self.journal.receipt(watch_id='w1', thread_id='thread-1', turn_id='turn-1', evidence='')

    def test_receipt_is_immutable_and_consumed_state_survives_reopen(self):
        self.journal.observe(snapshot(self.now, jobs=[job_row('j1', self.now, status='completed')]))
        consumed = self.journal.receipt(watch_id='w1', thread_id='thread-1', turn_id='turn-1',
                                        evidence='read the persisted result')
        self.assertEqual(consumed['state'], 'consumed')
        same = self.journal.receipt(watch_id='w1', thread_id='thread-1', turn_id='turn-1',
                                    evidence='read the persisted result')
        self.assertEqual(same['receipt']['turn_id'], 'turn-1')
        with self.assertRaises(ValueError):
            self.journal.receipt(watch_id='w1', thread_id='thread-1', turn_id='turn-2',
                                 evidence='second turn')
        reopened = ContinuityJournal(self.base / 'continuity.sqlite')
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get_watch('w1')['state'], 'consumed')
        self.assertEqual(reopened.get_watch('w1')['receipt']['evidence'],
                         'read the persisted result')
        reopened.observe(snapshot(self.now, jobs=[job_row('j1', self.now, status='completed')]))
        incidents = {item['incident_id']: item for item in reopened.status()['incidents']}
        self.assertFalse(incidents['result_unconsumed:w1']['active'],
                         'a consumed result must not stay an open incident')


class RuntimeHarness(unittest.IsolatedAsyncioTestCase):
    """Test-double node runtimes on isolated temporary state directories."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.runtimes: list[NodeRuntime] = []

    async def asyncTearDown(self):
        for runtime in reversed(self.runtimes):
            await runtime.stop()
        self.runtimes.clear()

    def new_runtime(self, name: str = 'node', *, node_id: str = 'B') -> NodeRuntime:
        home = self.base / name
        home.mkdir(parents=True, exist_ok=True)
        config_path = home / 'node.toml'
        config_path.write_text(f'node_id="{node_id}"\nstate_dir="state"\nmode="test_double"\n',
                               encoding='utf-8')
        runtime = NodeRuntime(NodeConfig.load(config_path))
        self.runtimes.append(runtime)
        return runtime

    async def stop_runtime(self, runtime: NodeRuntime) -> None:
        self.runtimes.remove(runtime)
        await runtime.stop()

    def assert_isolated(self, runtime: NodeRuntime) -> None:
        root = self.base.resolve()
        self.assertTrue(Path(runtime.config.state_dir).resolve().is_relative_to(root))
        self.assertTrue(runtime.continuity.journal.path.resolve().is_relative_to(root))

    async def finish_turns(self, runtime: NodeRuntime) -> None:
        await runtime.controller.run_until_idle()

    def inbound_count(self, runtime: NodeRuntime, message_id: str) -> int:
        return runtime.store._connection.execute(
            'SELECT COUNT(*) FROM inbound WHERE message_id=?', (message_id,)).fetchone()[0]

    def total_inbound(self, runtime: NodeRuntime) -> int:
        return runtime.store._connection.execute('SELECT COUNT(*) FROM inbound').fetchone()[0]

    def register_main_session(self, runtime: NodeRuntime, task_id: str, thread_id: str,
                              *, version: int = 1) -> None:
        runtime.main_sessions.db.execute(
            'INSERT INTO main_sessions VALUES (?,?,?,?,?,?,?,?,?)',
            (task_id, thread_id, version, 'gpt-6-astra', 'ultra', 'execution', task_id,
             None, now_text()))
        runtime.main_sessions.db.commit()

    def make_child(self, runtime: NodeRuntime, *, task_id: str, version: int = 1,
                   failure: str | None = None) -> dict:
        job = runtime.children.native_reserve(
            task_id=task_id, task_version=version, text='bounded fixture work',
            work_id=f'fixture-work-{version}', ownership=[],
            reason='fixture: native lease needed')
        lease = {'job_id': job['job_id'], 'lease_token': job['lease_token']}
        runtime.children.native_validate(**lease, agent_id='fixture-agent')
        if failure is None:
            runtime.children.native_complete(**lease, text='fixture result')
        else:
            runtime.children.native_complete(**lease, text='', error=failure)
        return runtime.children.job(job['job_id'])

    async def watch(self, runtime: NodeRuntime, **arguments) -> dict:
        return await runtime.project_actions.call('fpga_continuity_watch', arguments)


class ContinuationDispatchTests(RuntimeHarness):
    """Persisted result -> exact recipient inbox -> one turn -> receipt."""

    async def test_external_owner_or_delivery_suppresses_another_mesh_notification(self):
        runtime = self.new_runtime('external-boundary')
        self.register_main_session(runtime, 't', 'app-thread')
        job = self.make_child(runtime, task_id='t')
        runtime.continuity.journal.watch(watch_id='external-child', task_id='t', task_version=1,
            source_kind='child', source_id=job['job_id'], recipient_thread_id='app-thread', auto_resume=True)
        declaration = runtime.main_sessions.external_owners_path
        declaration.write_text(json.dumps({'t': {'owner_kind': 'desktop',
            'thread_id': 'app-thread', 'task_version': 1}}), encoding='utf-8')
        report = runtime.continuity.check()
        self.assertEqual(runtime.continuity.journal.get_watch('external-child')['state'], 'ready')
        await runtime.continuity.journal.dispatch_ready(runtime, report)
        self.assertEqual(self.total_inbound(runtime), 0)
        owner = runtime.main_sessions.external_owner('t', 1)
        message = peer_report('saved-app-delivery')
        runtime.store.accept_inbound(message)
        runtime.main_sessions.defer_external(message, owner)
        runtime.store.mark_inbound_processed(message.message_id)
        declaration.unlink()
        report = runtime.continuity.check()
        await runtime.continuity.journal.dispatch_ready(runtime, report)
        self.assertEqual(self.total_inbound(runtime), 1, 'pending App delivery must not create another notification')
        self.assertEqual(runtime.astra_gateway.calls, [])
        self_check = await runtime.project_actions.call('fpga_self_check', {})
        self.assertEqual(self_check['external_deliveries'][0]['recipient_thread_id'], 'app-thread')
        self.assertTrue(any(i['kind'] == 'external_delivery_pending' and i['active']
                            for i in self_check['incidents']))

    async def test_persisted_main_result_reaches_exact_inbox_as_one_turn_and_receipt(self):
        runtime = self.new_runtime('round-trip')
        self.assert_isolated(runtime)
        submitted = await runtime.project_actions.call(
            'main_submit', {'task_id': 'demo-task', 'task_version': 1, 'text': 'do the thing'})
        await self.finish_turns(runtime)
        self.assertEqual(runtime.main_sessions.result(submitted['message_id'])['status'],
                         'completed')
        self.register_main_session(runtime, 'demo-task', 'thread-demo')
        watch = await self.watch(
            runtime, watch_id='watch-main-1', task_id='demo-task', task_version=1,
            source_kind='main', source_id=submitted['message_id'],
            recipient_thread_id='thread-demo', auto_resume=True)
        self.assertEqual(watch['state'], 'waiting')
        sessions_before = runtime.main_sessions.sessions()
        report = runtime.continuity.check()
        self.assertEqual(runtime.continuity.journal.get_watch('watch-main-1')['state'], 'ready')
        incidents = {item['incident_id']: item
                     for item in runtime.continuity.journal.status()['incidents']}
        self.assertEqual(incidents['result_unconsumed:watch-main-1']['evidence']['disposition'],
                         'continue_remaining_work')
        await runtime.continuity.journal.dispatch_ready(runtime, report)
        mid = continuation_message_id('watch-main-1')
        watch = runtime.continuity.journal.get_watch('watch-main-1')
        self.assertEqual((watch['state'], watch['message_id']), ('enqueued', mid))
        await self.finish_turns(runtime)
        self.assertEqual(runtime.astra_gateway.calls, [submitted['message_id'], mid],
                         'the continuation must run exactly one turn')
        self.assertEqual(self.inbound_count(runtime, mid), 1)
        processed = runtime.store._connection.execute(
            'SELECT processed_at FROM inbound WHERE message_id=?', (mid,)).fetchone()[0]
        self.assertIsNotNone(processed)
        payload = json.loads(runtime.store._connection.execute(
            'SELECT payload FROM inbound WHERE message_id=?', (mid,)).fetchone()[0])
        text = payload['payload']['text']
        self.assertIn('do not replay', text)
        self.assertIn('Record continuity_receipt', text)
        self.assertEqual(runtime.main_sessions.sessions(), sessions_before,
                         'continuity must never create a replacement main')
        # A second observe/dispatch cycle adds nothing.
        report = runtime.continuity.check()
        await runtime.continuity.journal.dispatch_ready(runtime, report)
        await self.finish_turns(runtime)
        self.assertEqual(runtime.astra_gateway.calls, [submitted['message_id'], mid])
        with self.assertRaises(ValueError):
            await runtime.project_actions.call('fpga_continuity_receipt', {
                'watch_id': 'watch-main-1', 'thread_id': 'wrong-thread', 'turn_id': 'turn-1',
                'evidence': 'wrong recipient must not settle the watch'})
        receipt = await runtime.project_actions.call('fpga_continuity_receipt', {
            'watch_id': 'watch-main-1', 'thread_id': 'thread-demo', 'turn_id': 'turn-1',
            'evidence': 'read the persisted run result and continued remaining work'})
        self.assertEqual(receipt['state'], 'consumed')
        self.assertEqual(receipt['receipt']['thread_id'], 'thread-demo')
        reopened = ContinuityJournal(Path(runtime.config.state_dir) / 'continuity.sqlite')
        try:
            self.assertEqual(reopened.get_watch('watch-main-1')['state'], 'consumed')
            reopened.observe(collect(runtime.config.state_dir))
            incidents = {item['incident_id']: item for item in reopened.status()['incidents']}
            self.assertFalse(incidents['result_unconsumed:watch-main-1']['active'])
        finally:
            reopened.close()

    async def test_terminal_failed_child_is_reconciled_without_replay(self):
        runtime = self.new_runtime('child-reconcile')
        self.assert_isolated(runtime)
        job = self.make_child(runtime, task_id='child-task', failure='fixture failure')
        self.assertEqual(job['status'], 'failed')
        self.register_main_session(runtime, 'child-task', 'thread-child')
        await self.watch(runtime, watch_id='watch-child-1', task_id='child-task', task_version=1,
                         source_kind='child', source_id=job['job_id'],
                         recipient_thread_id='thread-child', auto_resume=True)
        before = runtime.children.job(job['job_id'])
        report = runtime.continuity.check()
        incidents = {item['incident_id']: item
                     for item in runtime.continuity.journal.status()['incidents']}
        self.assertEqual(incidents['result_unconsumed:watch-child-1']['evidence']['disposition'],
                         'reconcile_only')
        await runtime.continuity.journal.dispatch_ready(runtime, report)
        mid = continuation_message_id('watch-child-1')
        await self.finish_turns(runtime)
        self.assertEqual(runtime.astra_gateway.calls, [mid])
        payload = json.loads(runtime.store._connection.execute(
            'SELECT payload FROM inbound WHERE message_id=?', (mid,)).fetchone()[0])
        self.assertIn('Reconcile unknown/failed actions; do not replay.',
                      payload['payload']['text'])
        self.assertEqual(payload['kind'], MessageKind.AGENT_REPORT.value)
        self.assertEqual(payload['source'], SourceKind.ASTRA.value)
        self.assertEqual(payload['recipient'], 'B/Astra-B')
        self.assertEqual(payload['task_id'], 'child-task')
        self.assertEqual(runtime.children.job(job['job_id']), before,
                         'watching a terminal child must not replay or rewrite the job')
        self.assertEqual(len(runtime.children.status()['jobs']), 1)
        receipt = runtime.continuity.journal.receipt(
            watch_id='watch-child-1', thread_id='thread-child', turn_id='turn-child-1',
            evidence='reconciled the failed child without replay')
        self.assertEqual(receipt['state'], 'consumed')

    async def test_stop_and_snapshot_pause_block_dispatch_until_resume(self):
        runtime = self.new_runtime('stop-resume')
        job = self.make_child(runtime, task_id='child-task')
        self.register_main_session(runtime, 'child-task', 'thread-child')
        await self.watch(runtime, watch_id='watch-child-1', task_id='child-task', task_version=1,
                         source_kind='child', source_id=job['job_id'],
                         recipient_thread_id='thread-child', auto_resume=True)
        mid = continuation_message_id('watch-child-1')
        report = runtime.continuity.check()
        self.assertEqual(runtime.continuity.journal.get_watch('watch-child-1')['state'], 'ready')
        # A pause recorded in the snapshot alone must block the offer.
        paused = {**report, 'pause': {'paused_at': iso(utc())}}
        await runtime.continuity.journal.dispatch_ready(runtime, paused)
        self.assertEqual(runtime.continuity.journal.get_watch('watch-child-1')['state'], 'ready')
        self.assertEqual(self.inbound_count(runtime, mid), 0)
        # An effective human STOP blocks through the controller as well.
        stop = human_control('stop-1', MessageKind.STOP_REQUEST, sent_at=utc())
        await runtime.controller.offer(stop)
        self.assertTrue(runtime.controller.dispatch_blocked)
        await runtime.continuity.journal.dispatch_ready(runtime, runtime.continuity.check())
        self.assertEqual(runtime.continuity.journal.get_watch('watch-child-1')['state'], 'ready')
        self.assertEqual(self.inbound_count(runtime, mid), 0)
        # Resume re-enables exactly one continuation.
        resume = human_control('resume-1', MessageKind.RESUME_REQUEST,
                               sent_at=stop.sent_at + timedelta(seconds=5))
        await runtime.controller.offer(resume)
        self.assertFalse(runtime.controller.dispatch_blocked)
        await runtime.controller.run_until_idle()
        await runtime.continuity.journal.dispatch_ready(runtime, runtime.continuity.check())
        self.assertEqual(runtime.continuity.journal.get_watch('watch-child-1')['message_id'], mid)
        await self.finish_turns(runtime)
        self.assertEqual(runtime.astra_gateway.calls, [mid])
        self.assertEqual(self.inbound_count(runtime, mid), 1)

    async def test_auto_resume_requires_exact_session_opt_in(self):
        runtime = self.new_runtime('exact-recipient')
        first = self.make_child(runtime, task_id='child-task', version=1)
        second = self.make_child(runtime, task_id='child-task', version=2)
        self.register_main_session(runtime, 'child-task', 'thread-v2', version=2)
        journal = runtime.continuity.journal
        journal.watch(watch_id='w-no-auto', task_id='child-task', task_version=2,
                      source_kind='child', source_id=second['job_id'],
                      recipient_thread_id='unused-thread', auto_resume=False)
        journal.watch(watch_id='w-thread', task_id='child-task', task_version=2,
                      source_kind='child', source_id=second['job_id'],
                      recipient_thread_id='other-thread', auto_resume=True)
        journal.watch(watch_id='w-version', task_id='child-task', task_version=1,
                      source_kind='child', source_id=first['job_id'],
                      recipient_thread_id='thread-v2', auto_resume=True)
        report = runtime.continuity.check()
        await journal.dispatch_ready(runtime, report)
        await self.finish_turns(runtime)
        for watch_id in ('w-no-auto', 'w-thread', 'w-version'):
            with self.subTest(watch=watch_id):
                watch = journal.get_watch(watch_id)
                self.assertEqual(watch['state'], 'ready', 'a ready watch awaits an exact match')
                self.assertIsNone(watch['message_id'])
        self.assertEqual(self.total_inbound(runtime), 0)
        self.assertEqual(runtime.astra_gateway.calls, [])
        # The exact existing route/version is the only thing that dispatches.
        journal.watch(watch_id='w-exact', task_id='child-task', task_version=2,
                      source_kind='child', source_id=second['job_id'],
                      recipient_thread_id='thread-v2', auto_resume=True)
        report = runtime.continuity.check()
        await journal.dispatch_ready(runtime, report)
        await self.finish_turns(runtime)
        self.assertEqual(runtime.astra_gateway.calls, [continuation_message_id('w-exact')])
        self.assertEqual(self.inbound_count(runtime, continuation_message_id('w-exact')), 1)

    async def test_crash_before_state_commit_reoffers_without_second_turn(self):
        first = self.new_runtime('restart')
        self.assert_isolated(first)
        job = self.make_child(first, task_id='child-task')
        self.register_main_session(first, 'child-task', 'thread-child')
        await self.watch(first, watch_id='watch-child-1', task_id='child-task', task_version=1,
                         source_kind='child', source_id=job['job_id'],
                         recipient_thread_id='thread-child', auto_resume=True)
        mid = continuation_message_id('watch-child-1')
        report = first.continuity.check()
        await first.continuity.journal.dispatch_ready(first, report)
        self.assertEqual(self.inbound_count(first, mid), 1)
        self.assertEqual(first.astra_gateway.calls, [], 'crash happens before the turn runs')
        # Crash point: the inbox write is durable but the journal state commit
        # is lost, so the watch is still ready on restart.
        first.continuity.journal.db.execute(
            "UPDATE watches SET state='ready', message_id=NULL WHERE watch_id='watch-child-1'")
        first.continuity.journal.db.commit()
        await self.stop_runtime(first)
        second = self.new_runtime('restart')
        self.assert_isolated(second)
        report = second.continuity.check()
        watch = second.continuity.journal.get_watch('watch-child-1')
        self.assertEqual((watch['state'], watch['event_status']), ('ready', 'completed'))
        await second.continuity.journal.dispatch_ready(second, report)
        duplicate = peer_report(mid, task_id='child-task')
        self.assertFalse(await second.controller.offer(duplicate),
                         'the identical envelope id must be deduplicated by the inbox')
        await self.finish_turns(second)
        self.assertEqual(second.astra_gateway.calls, [mid],
                         'the untouched pending message runs exactly one turn after restart')
        self.assertEqual(self.inbound_count(second, mid), 1)
        watch = second.continuity.journal.get_watch('watch-child-1')
        self.assertEqual((watch['state'], watch['message_id']), ('enqueued', mid))
        self.assertEqual(second.main_sessions.result(mid)['status'], 'completed')
        # Further cycles must not enqueue anything new.
        report = second.continuity.check()
        await second.continuity.journal.dispatch_ready(second, report)
        await self.finish_turns(second)
        self.assertEqual(second.astra_gateway.calls, [mid])
        self.assertEqual(self.inbound_count(second, mid), 1)


class RuntimeHookAndFrontDoorTests(RuntimeHarness):
    """Runtime lifecycle wiring and the ProjectActions continuity tools."""

    async def test_runtime_wires_monitor_lifecycle_and_snapshot(self):
        runtime = self.new_runtime('hooks')
        self.assert_isolated(runtime)
        self.assertIsInstance(runtime.continuity, ContinuityMonitor)
        self.assertEqual(runtime.controller.on_activity, runtime.continuity.notify)
        self.assertEqual(runtime.children.on_activity, runtime.continuity.notify)
        self.assertFalse(runtime.snapshot()['started'])
        self.assertIsNone(runtime.snapshot()['continuity_error'])
        self.assertEqual(set(runtime.snapshot()['loaded_source_hashes']), SOURCE_MODULES)
        self.assertIsNone(runtime.continuity.task)
        await runtime.start()
        self.assertTrue(runtime.started)
        self.assertIsNotNone(runtime.continuity.task)
        self.assertFalse(runtime.continuity.task.done())
        # Loaded-vs-disk drift is observable through the real monitor.
        runtime.continuity.loaded_hashes = {
            **runtime.continuity.loaded_hashes, 'runtime.py': '0' * 64}
        self_check = await runtime.project_actions.call('fpga_self_check', {})
        self.assertIsNone(self_check['monitor_error'])
        self.assertEqual(set(self_check['loaded_source_hashes']), SOURCE_MODULES)
        drift = [item for item in self_check['incidents']
                 if item['incident_id'] == 'runtime_source_drift:loaded']
        self.assertEqual(len(drift), 1)
        self.assertTrue(drift[0]['active'])
        self.assertEqual(drift[0]['evidence']['disposition'], 'idle_fenced_update_required')
        self.assertNotEqual(drift[0]['evidence']['loaded'], drift[0]['evidence']['disk'])
        await self.stop_runtime(runtime)
        self.assertIsNone(runtime.continuity.task)
        self.assertFalse(runtime.started)

    async def test_front_door_exposes_continuity_tools_and_rejects_wrong_requests(self):
        runtime = self.new_runtime('front-door')
        self.assert_isolated(runtime)
        self_check = await runtime.project_actions.call('fpga_self_check', {})
        self.assertEqual(self_check['watches'], [])
        self.assertEqual(self_check['incidents'], [])
        self.assertIn('observed_at', self_check)
        with self.assertRaises(ValueError):
            await self.watch(runtime, watch_id='w1', task_id='t', task_version=1,
                             source_kind='child', source_id='absent',
                             recipient_thread_id='thread-1')
        job = self.make_child(runtime, task_id='t')
        with self.assertRaises(ValueError):
            await self.watch(runtime, watch_id='w2', task_id='other-task', task_version=1,
                             source_kind='child', source_id=job['job_id'],
                             recipient_thread_id='thread-1')
        with self.assertRaises(ValueError) as caught:
            await self.watch(runtime, watch_id='w3', task_id='t', task_version=1,
                             source_kind='child', source_id=job['job_id'],
                             recipient_thread_id='thread-1', auto_resume=True)
        self.assertIn('exact existing main route/version', str(caught.exception))
        accepted = await self.watch(runtime, watch_id='w4', task_id='t', task_version=1,
                                    source_kind='child', source_id=job['job_id'],
                                    recipient_thread_id='thread-1')
        self.assertEqual(accepted['state'], 'waiting')
        self.assertEqual([item['watch_id'] for item in
                          (await runtime.project_actions.call('fpga_self_check', {}))['watches']],
                         ['w4'])
        # A repair claim is refused while the controller is explicitly stopped.
        seed = peer_report('seed-1')
        runtime.store.accept_inbound(seed)
        runtime.store._connection.execute(
            'UPDATE inbound SET received_at=? WHERE message_id=?',
            (iso(utc() - timedelta(hours=1)), seed.message_id))
        runtime.store._connection.commit()
        stop = human_control('stop-1', MessageKind.STOP_REQUEST, sent_at=utc())
        await runtime.controller.offer(stop)
        with self.assertRaises(ValueError):
            await runtime.project_actions.call('fpga_continuity_repair', {
                'incident_id': 'queue_wait:seed-1', 'phase': 'claim',
                'owner_thread_id': 'owner-1'})
        resume = human_control('resume-1', MessageKind.RESUME_REQUEST,
                               sent_at=stop.sent_at + timedelta(seconds=5))
        await runtime.controller.offer(resume)
        self.assertFalse(runtime.controller.dispatch_blocked)
        claim = await runtime.project_actions.call('fpga_continuity_repair', {
            'incident_id': 'queue_wait:seed-1', 'phase': 'claim', 'owner_thread_id': 'owner-1'})
        self.assertTrue(claim['execute'])
        self_check = await runtime.project_actions.call('fpga_self_check', {})
        claimed = {item['incident_id']: item for item in self_check['incidents']}['queue_wait:seed-1']
        self.assertEqual(claimed['repair']['phase'], 'claimed')

    async def test_started_service_cycle_keeps_service_up_and_ledger_untouched(self):
        runtime = self.new_runtime('service')
        self.assert_isolated(runtime)
        stopped = []
        original_stop = runtime.stop

        async def spy_stop():
            stopped.append('stop')
            await original_stop()

        runtime.stop = spy_stop
        await runtime.start()
        job = self.make_child(runtime, task_id='child-task')
        self.register_main_session(runtime, 'child-task', 'thread-child')
        await self.watch(runtime, watch_id='watch-child-1', task_id='child-task',
                         task_version=1, source_kind='child', source_id=job['job_id'],
                         recipient_thread_id='thread-child', auto_resume=True)
        before_job = runtime.children.job(job['job_id'])
        before_bytes = sha256_file(Path(runtime.config.state_dir) / 'child_jobs.sqlite')
        mid = continuation_message_id('watch-child-1')
        runtime.continuity.notify()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 10.0
        while runtime.main_sessions.result(mid) is None and loop.time() < deadline:
            await asyncio.sleep(0.05)
        self.assertEqual(runtime.main_sessions.result(mid)['status'], 'completed')
        self.assertEqual(runtime.astra_gateway.calls.count(mid), 1)
        self.assertEqual(self.inbound_count(runtime, mid), 1)
        self.assertTrue(runtime.started, 'continuity must not stop the service')
        self.assertEqual(stopped, [])
        self.assertIsNone(runtime.continuity.error)
        client = LocalControlFileClient(Path(runtime.config.state_dir) / 'main-control.json')
        health = await client.call('health', {})
        self.assertTrue(health['started'])
        self.assertEqual(runtime.children.job(job['job_id']), before_job)
        self.assertEqual(sha256_file(Path(runtime.config.state_dir) / 'child_jobs.sqlite'),
                         before_bytes, 'the watched child ledger must not be rewritten')
        runtime.stop = original_stop


if __name__ == '__main__':
    unittest.main()
