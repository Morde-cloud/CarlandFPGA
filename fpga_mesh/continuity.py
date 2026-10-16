"""Durable continuity checks. Observing is never permission to replay work.

Existing ledgers are read-only inputs. This journal stores explicit watches,
receipts and one-shot repair claims; it does not create App chats or restart a
service. Only opt-in watches may enqueue a bounded continuation to an existing
registered main, using the ordinary STOP-aware controller and inbox dedupe.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from .sessions import EXTERNAL_CLOSED


TERMINAL = {'completed', 'failed', 'cancelled', 'interrupted'}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def age(value, now):
    return (datetime.fromisoformat(now.replace('Z', '+00:00')) -
            datetime.fromisoformat(value.replace('Z', '+00:00'))).total_seconds()


def rows(path, sql, *, optional_table=None):
    # Do not instantiate routers/coordinators: their constructors recover jobs.
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        if optional_table and not db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (optional_table,)).fetchone():
            return []
        return [dict(r) for r in db.execute(sql)]


def collect(state):
    state = Path(state)
    inbound = rows(state / 'state.sqlite', 'SELECT message_id,payload,received_at,next_attempt_at,processed_at FROM inbound')
    for item in inbound:
        body = json.loads(item.pop('payload'))
        item.update({k: body.get(k) for k in ('task_id', 'task_version')})
    pending = [item for item in inbound if item.pop('processed_at') is None]
    versions = {item['message_id']: item['task_version'] for item in inbound}
    runs = rows(state / 'main_sessions.sqlite', 'SELECT message_id,task_id,status,updated_at FROM main_runs')
    for item in runs:
        item['task_version'] = versions.get(item['message_id'])
    pause = rows(state / 'state.sqlite', "SELECT payload FROM controller_state WHERE key='human_pause'")
    retry = rows(state / 'state.sqlite', "SELECT payload FROM controller_state WHERE key='gateway_retry'")
    external_columns = {r['name'] for r in rows(state / 'main_sessions.sqlite',
                                              'PRAGMA table_info(external_deliveries)')}
    resolution = 'resolution_json' if 'resolution_json' in external_columns else 'NULL AS resolution_json'
    deliveries = rows(state / 'main_sessions.sqlite',
        'SELECT message_id,task_id,task_version,recipient_thread_id,declaration_hash,reason,status,created_at,'
        + resolution + ' FROM external_deliveries', optional_table='external_deliveries')
    for delivery in deliveries:
        value = delivery.pop('resolution_json')
        delivery['resolution'] = json.loads(value) if value else None
    return {
        'observed_at': utcnow(), 'pending': pending,
        'pause': json.loads(pause[0]['payload']) if pause else {},
        'retry': json.loads(retry[0]['payload']) if retry else {},
        'sessions': rows(state / 'main_sessions.sqlite', 'SELECT task_id,task_version,thread_id FROM main_sessions'),
        'runs': runs,
        'external_deliveries': deliveries,
        'jobs': rows(state / 'child_jobs.sqlite', 'SELECT job_id,task_id,task_version,work_id,status,route,error,native_agent_id,ownership_json,created_at,updated_at FROM child_jobs'),
    }


def source_hashes(root):
    return {name: hashlib.sha256((Path(root) / name).read_bytes()).hexdigest()
            for name in ('runtime.py', 'controller.py', 'gateway.py', 'app_server.py',
                         'child_control.py', 'project_control.py', 'continuity.py', 'sessions.py', 'update.py')}


class ContinuityJournal:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS watches (
                watch_id TEXT PRIMARY KEY, spec TEXT NOT NULL, state TEXT NOT NULL,
                event_status TEXT, message_id TEXT, receipt TEXT, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY, kind TEXT NOT NULL, evidence TEXT NOT NULL,
                first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, active INTEGER NOT NULL,
                repair TEXT);
            CREATE TABLE IF NOT EXISTS monitor_state (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                observed_at TEXT NOT NULL, error TEXT);
        ''')

    def watch(self, *, watch_id, task_id, task_version, source_kind, source_id,
              recipient_thread_id, auto_resume=False):
        if source_kind not in {'child', 'main'} or int(task_version) < 1:
            raise ValueError('positive version and child/main source required')
        spec = dict(task_id=task_id, task_version=task_version, source_kind=source_kind,
                    source_id=source_id, recipient_thread_id=recipient_thread_id,
                    auto_resume=bool(auto_resume))
        if not all(isinstance(x, str) and x.strip() for x in (watch_id, task_id, source_id, recipient_thread_id)):
            raise ValueError('explicit stable identifiers required')
        encoded = json.dumps(spec, sort_keys=True)
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            for row in self.db.execute('SELECT watch_id,spec FROM watches'):
                other = json.loads(row['spec'])
                if row['watch_id'] != watch_id and all(other.get(k) == spec[k] for k in
                        ('task_id', 'task_version', 'source_kind', 'source_id', 'recipient_thread_id')):
                    raise ValueError('source already watched; reuse ' + row['watch_id'])
            prior = self.db.execute('SELECT spec FROM watches WHERE watch_id=?', (watch_id,)).fetchone()
            if prior and prior['spec'] != encoded:
                raise ValueError('watch identity conflict; use a new explicit work id')
            self.db.execute("INSERT OR IGNORE INTO watches VALUES (?,?,'waiting',NULL,NULL,NULL,?)",
                            (watch_id, encoded, utcnow()))
        return self.get_watch(watch_id)

    def get_watch(self, watch_id):
        row = self.db.execute('SELECT * FROM watches WHERE watch_id=?', (watch_id,)).fetchone()
        if not row:
            raise KeyError(watch_id)
        result = dict(row)
        result['spec'] = json.loads(result['spec'])
        result['receipt'] = json.loads(result['receipt']) if result['receipt'] else None
        return result

    def receipt(self, *, watch_id, thread_id, turn_id, evidence):
        watch = self.get_watch(watch_id)
        if watch['state'] not in {'ready', 'enqueued', 'consumed'}:
            raise ValueError('source has not reached a terminal result')
        if thread_id != watch['spec']['recipient_thread_id'] or not turn_id or not evidence:
            raise ValueError('actual designated recipient turn and evidence required')
        receipt = json.dumps(dict(thread_id=thread_id, turn_id=turn_id, evidence=evidence), sort_keys=True)
        if watch['receipt'] and json.dumps(watch['receipt'], sort_keys=True) != receipt:
            raise ValueError('immutable receipt conflict')
        with self.db:
            self.db.execute("UPDATE watches SET state='consumed',receipt=? WHERE watch_id=?", (receipt, watch_id))
        return self.get_watch(watch_id)

    def observe(self, snapshot, *, loaded_hashes=None, disk_hashes=None, threshold=900):
        now = snapshot['observed_at']
        sessions = {s['task_id']: s for s in snapshot['sessions']}
        active = any(r['status'] == 'running' for r in snapshot['runs'])
        paused = bool(snapshot['pause'].get('paused_at'))
        found = []

        def add(kind, key, **evidence):
            found.append((kind + ':' + key, kind, evidence))

        for delivery in snapshot.get('external_deliveries', []):
            if delivery['status'] not in EXTERNAL_CLOSED:
                add('external_delivery_pending', delivery['message_id'], **delivery,
                    disposition='human_paused' if paused else 'app_delivery_unknown'
                    if delivery['status'] == 'delivery_unknown' else 'app_delivery_required')

        for item in snapshot['pending']:
            if age(item['received_at'], now) >= threshold:
                retry_at = snapshot.get('retry', {}).get('retry_at')
                deferred = ((item.get('next_attempt_at') and age(item['next_attempt_at'], now) < 0)
                            or (retry_at and age(retry_at, now) < 0))
                add('queue_wait', item['message_id'], **item,
                    disposition='human_paused' if paused else 'normal_active_wait' if active else
                    'scheduled_backoff' if deferred else 'needs_inspection',
                    recipient_thread_id=sessions.get(item['task_id'], {}).get('thread_id'))
        for job in snapshot['jobs']:
            if job['status'] == 'reserved' and not job['native_agent_id'] and age(job['created_at'], now) >= threshold:
                add('unbound_reservation', job['job_id'], job_id=job['job_id'], task_id=job['task_id'],
                    recipient_thread_id=sessions.get(job['task_id'], {}).get('thread_id'),
                    disposition='human_paused' if paused else 'inspect_existing_app_receipts')
        from .child_control import ChildCoordinator
        writers = [j for j in snapshot['jobs'] if j['status'] in {'reserved', 'queued', 'running'} or
                   (j.get('route') == 'gpt_native' and
                    (j['status'] == 'interrupted' or j.get('error') == 'native stop unconfirmed'))]
        for index, first in enumerate(writers):
            for second in writers[index + 1:]:
                if any(ChildCoordinator._ownership_overlaps(a, b)
                       for a in json.loads(first.get('ownership_json') or '[]')
                       for b in json.loads(second.get('ownership_json') or '[]')):
                    key = ':'.join(sorted((first['job_id'], second['job_id'])))
                    add('writer_overlap', key, jobs=[first['job_id'], second['job_id']],
                        disposition='inspect_ownership_do_not_cancel')
        if loaded_hashes is not None and loaded_hashes != disk_hashes:
            add('runtime_source_drift', 'loaded', loaded=loaded_hashes, disk=disk_hashes,
                disposition='idle_fenced_update_required')
        jobs = {j['job_id']: j for j in snapshot['jobs']}
        runs = {r['message_id']: r for r in snapshot['runs']}
        for row in self.db.execute("SELECT watch_id FROM watches WHERE state!='consumed'").fetchall():
            watch = self.get_watch(row['watch_id']); spec = watch['spec']
            event = (jobs if spec['source_kind'] == 'child' else runs).get(spec['source_id'])
            if not event:
                add('watch_source_missing', watch['watch_id'], source_id=spec['source_id'])
                continue
            if event['task_id'] != spec['task_id'] or event.get('task_version') != spec['task_version']:
                add('watch_source_conflict', watch['watch_id'], source_id=spec['source_id'])
                continue
            if event['status'] not in TERMINAL:
                continue  # No generic "no progress" timeout on normal computation.
            with self.db:
                self.db.execute("UPDATE watches SET state='ready',event_status=? WHERE watch_id=? AND state='waiting'",
                                (event['status'], watch['watch_id']))
            add('result_unconsumed', watch['watch_id'], source_id=spec['source_id'],
                source_status=event['status'], recipient_thread_id=spec['recipient_thread_id'],
                disposition='human_paused' if paused else 'normal_active_wait' if active else
                'reconcile_only' if event['status'] != 'completed' else 'continue_remaining_work')
        with self.db:
            self.db.execute('UPDATE incidents SET active=0')
            for key, kind, evidence in found:
                self.db.execute('''INSERT INTO incidents VALUES (?,?,?,?,?,1,NULL)
                    ON CONFLICT(incident_id) DO UPDATE SET evidence=excluded.evidence,
                    last_seen=excluded.last_seen,active=1''',
                    (key, kind, json.dumps(evidence, sort_keys=True), now, now))
        return self.status()

    def status(self):
        incidents = []
        for row in self.db.execute('SELECT * FROM incidents ORDER BY first_seen,incident_id'):
            value = dict(row)
            for key in ('evidence', 'repair'):
                value[key] = json.loads(value[key]) if value[key] else None
            incidents.append(value)
        monitor = self.db.execute('SELECT observed_at,error FROM monitor_state WHERE singleton=1').fetchone()
        return {'monitor': dict(monitor) if monitor else None,
                'incidents': incidents, 'watches': [self.get_watch(r[0]) for r in
                self.db.execute('SELECT watch_id FROM watches ORDER BY created_at')]}

    def monitor_result(self, error=None):
        with self.db:
            stamp = utcnow()
            self.db.execute('INSERT OR REPLACE INTO monitor_state VALUES (1,?,?)', (stamp, error))
            if error:
                key = 'monitor_error:' + hashlib.sha256(error.encode()).hexdigest()
                self.db.execute('''INSERT INTO incidents VALUES (?,?,?,?,?,1,NULL)
                    ON CONFLICT(incident_id) DO UPDATE SET last_seen=excluded.last_seen,active=1''',
                    (key, 'monitor_error', json.dumps({'error': error, 'disposition': 'needs_inspection'}), stamp, stamp))

    def repair(self, *, incident_id, phase, owner_thread_id, thread_id=None, turn_id=None, paused=False):
        """Claim before App creation. Unknown outcomes are never eligible again.

        The caller must have an authorized App create_thread capability. A claim
        is neither a native execution lease nor a product-director appointment.
        """
        if phase not in {'claim', 'created', 'started', 'unknown'} or not owner_thread_id:
            raise ValueError('valid repair phase and actual owner required')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT * FROM incidents WHERE incident_id=?', (incident_id,)).fetchone()
            if not row:
                raise KeyError(incident_id)
            prior = json.loads(row['repair']) if row['repair'] else None
            if phase == 'claim':
                if prior:
                    return {**prior, 'execute': False}
                disposition = json.loads(row['evidence']).get('disposition')
                if paused or not row['active'] or disposition in {'human_paused', 'normal_active_wait', 'scheduled_backoff', 'app_delivery_required', 'app_delivery_unknown'}:
                    raise ValueError('paused, resolved or normal wait; repair creation forbidden')
                value = {'phase': 'claimed', 'owner_thread_id': owner_thread_id, 'claimed_at': utcnow()}
            else:
                if not prior or prior['owner_thread_id'] != owner_thread_id:
                    raise ValueError('no matching repair owner')
                if phase == 'created' and prior['phase'] == 'claimed' and thread_id:
                    value = {**prior, 'phase': phase, 'thread_id': thread_id}
                elif phase == 'started' and prior['phase'] == 'created' and thread_id == prior['thread_id'] and turn_id:
                    value = {**prior, 'phase': phase, 'turn_id': turn_id}
                elif phase == 'unknown' and prior['phase'] in {'claimed', 'created'}:
                    value = {**prior, 'phase': phase}
                else:
                    raise ValueError('invalid transition; inspect saved outcome, never replay')
            self.db.execute('UPDATE incidents SET repair=? WHERE incident_id=?', (json.dumps(value), incident_id))
        return {**value, 'execute': phase == 'claim'}

    async def dispatch_ready(self, runtime, snapshot):
        from .protocol import Envelope, MessageKind, SourceKind
        if runtime.controller.dispatch_blocked or snapshot['pause'].get('paused_at'):
            return
        sessions = {s['task_id']: s for s in snapshot['sessions']}
        sources = {'child': {j['job_id']: j for j in snapshot['jobs']},
                   'main': {r['message_id']: r for r in snapshot['runs']}}
        for watch in self.status()['watches']:
            spec = watch['spec']; session = sessions.get(spec['task_id'])
            event = sources[spec['source_kind']].get(spec['source_id'])
            owner_check = getattr(getattr(runtime, 'main_sessions', None), 'external_owner', None)
            if (any(d['task_id'] == spec['task_id'] and d['status'] not in EXTERNAL_CLOSED
                    for d in snapshot.get('external_deliveries', [])) or
                    owner_check and owner_check(spec['task_id'], spec['task_version']) is not None):
                continue  # An App obligation is not permission to enqueue another mesh notification.
            if (watch['state'] != 'ready' or not spec['auto_resume'] or not session or
                    session['thread_id'] != spec['recipient_thread_id'] or session['task_version'] != spec['task_version'] or
                    not event or event['task_id'] != spec['task_id'] or event.get('task_version') != spec['task_version'] or
                    event['status'] not in TERMINAL or event['status'] != watch['event_status']):
                continue  # App proxies require App tools; never create a replacement main.
            mid = 'continuity:' + hashlib.sha256(watch['watch_id'].encode()).hexdigest()
            message = Envelope(message_id=mid, project_id=runtime.config.project_id,
                sender=f'{runtime.config.node_id}/Astra-{runtime.config.node_id}',
                recipient=f'{runtime.config.node_id}/Astra-{runtime.config.node_id}',
                task_id=spec['task_id'], task_version=spec['task_version'],
                sent_at=datetime.fromisoformat(watch['created_at']),
                kind=MessageKind.AGENT_REPORT, source=SourceKind.ASTRA,
                payload={'category': 'difficult', 'text': f"Continuity watch {watch['watch_id']}: {spec['source_kind']} {spec['source_id']} "
                         f"has terminal status {watch['event_status']}. Read the persisted result and current human instructions. "
                         'Reconcile unknown/failed actions; do not replay. Continue only authorized remaining work. '
                         'Record continuity_receipt with your actual thread/turn and evidence.'})
            # offer is a durable INSERT OR IGNORE. A crash before the journal
            # update safely reoffers the same envelope ID, never a second turn.
            await runtime.controller.offer(message)
            with self.db:
                self.db.execute("UPDATE watches SET state='enqueued',message_id=? WHERE watch_id=? AND state='ready'", (mid, watch['watch_id']))

    def close(self):
        self.db.close()


class ContinuityMonitor:
    def __init__(self, runtime):
        self.runtime = runtime
        self.journal = ContinuityJournal(runtime.config.state_dir / 'continuity.sqlite')
        self.loaded_hashes = source_hashes(Path(__file__).parent)
        self.wakeup = asyncio.Event()
        self.task = None
        self.error = None

    def notify(self):
        self.wakeup.set()

    def check(self):
        snapshot = collect(self.runtime.config.state_dir)
        self.journal.observe(snapshot, loaded_hashes=self.loaded_hashes,
                             disk_hashes=source_hashes(Path(__file__).parent))
        return snapshot

    async def run(self):
        while True:
            self.wakeup.clear()
            try:
                snapshot = self.check()
                await self.journal.dispatch_ready(self.runtime, snapshot)
                self.error = None
            except Exception as exc:
                # Keep execution available; surface the error, not a healthy lie.
                self.error = type(exc).__name__ + ': ' + str(exc)[:200]
            try:
                self.journal.monitor_result(self.error)
            except sqlite3.Error:
                # A full/unavailable journal is surfaced in live health. Never
                # compensate by modifying execution ledgers or sending notices.
                self.error = self.error or 'continuity journal unavailable'
            try:
                await asyncio.wait_for(self.wakeup.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass  # Age thresholds and host resume; no inference or presence probe.

    def start(self):
        self.task = asyncio.create_task(self.run(), name='fpga-continuity')

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        self.journal.close()


def main():
    """One read-only source snapshot; explicitly chosen observer journal only."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--journal', type=Path, required=True)
    args = parser.parse_args()
    # Never open an execution DB as our writable observer journal.
    if args.journal.resolve().parent == args.state_dir.resolve():
        parser.error('use an evidence directory, not the resident state directory')
    journal = ContinuityJournal(args.journal)
    try:
        result = journal.observe(collect(args.state_dir))
        print(json.dumps(result, ensure_ascii=False))
    finally:
        journal.close()


if __name__ == '__main__':
    main()
