"""Persistent task conversations and validated OpenAI model/effort routing."""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

EFFORT_ORDER = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')
CRITICAL = frozenset({'decision', 'acceptance', 'difficult', 'optimization', 'evaluation'})
KINDS = CRITICAL | {'execution', 'routine'}
IMPORTANT = re.compile(r'决策|验收|重难|关键|评估|优化|设计|架构|(?:\b)(?:decision|acceptance|difficult|critical|optimization|evaluate|review|architecture|cdc|rdc)(?:\b)', re.I)
ROUTINE = re.compile(r'^\s*(?:Reply (?:with )?(?:exactly|only) [\w. -]+\.?|只回复\s*\S+|仅回复\s*\S+)\s*$', re.I)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExternalOwnerRequired(RuntimeError):
    """A declared owner prevents this mesh caller from sending work."""

    def __init__(self, owner: dict):
        self.owner = owner
        super().__init__(owner['reason'])


class ExternalDeliveryPending(RuntimeError):
    """Work is durably held for its App recipient; no work turn was sent."""

    def __init__(self, delivery: dict):
        self.delivery = delivery
        super().__init__(delivery['reason'])


class MainSessionRouter:
    def __init__(self, path: str | Path, *, quality_model: str = 'gpt-6-astra'):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.external_owners_path = path.parent / 'external-task-owners.json'
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS main_sessions (
                task_id TEXT PRIMARY KEY, thread_id TEXT UNIQUE NOT NULL,
                task_version INTEGER NOT NULL, model TEXT NOT NULL, effort TEXT NOT NULL,
                category TEXT NOT NULL, title TEXT NOT NULL, pending_json TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS main_runs (
                message_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                status TEXT NOT NULL, result_json TEXT, error TEXT, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS external_deliveries (
                message_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                task_version INTEGER NOT NULL, recipient_thread_id TEXT,
                declaration_hash TEXT, reason TEXT NOT NULL,
                envelope_json TEXT NOT NULL, status TEXT NOT NULL,
                receipt_json TEXT, created_at TEXT NOT NULL
            );
        ''')
        self.db.execute("UPDATE main_runs SET status='interrupted' WHERE status='running'")
        self.db.commit()
        self.quality_model = quality_model
        self._models: dict[str, tuple[str, ...]] = {}
        self._loaded: set[str] = set()
        self._allocation = asyncio.Lock()
        self._catalog_lock = asyncio.Lock()
        self.changed = asyncio.Event()

    def external_owner(self, task_id: str, task_version: int | None = None) -> dict | None:
        """Read only an explicit declaration. Never infer ownership from a lock."""
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate external owner key')
                result[key] = value
            return result
        try:
            owners = json.loads(self.external_owners_path.read_text(encoding='utf-8'), object_pairs_hook=unique)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:
            return {'reason': f'external owner declaration unreadable: {type(exc).__name__}',
                    'recipient_thread_id': None, 'declaration_hash': None, 'valid': False}
        if not isinstance(owners, dict):
            return {'reason': 'external owner declarations must be keyed by task ID',
                    'recipient_thread_id': None, 'declaration_hash': None, 'valid': False}
        if task_id not in owners:
            return None
        owner = owners[task_id]
        digest = hashlib.sha256(json.dumps(owner, ensure_ascii=False, sort_keys=True,
                                          separators=(',', ':')).encode('utf-8')).hexdigest()
        recipient = owner.get('thread_id') if isinstance(owner, dict) else None
        valid = (isinstance(owner, dict) and owner.get('owner_kind') == 'desktop'
                 and isinstance(recipient, str) and bool(recipient.strip())
                 and type(owner.get('task_version')) is int and owner['task_version'] > 0)
        row = self.session(task_id)
        reason = 'external owner declaration requires desktop owner, thread and positive task_version'
        if valid:
            valid = bool(row and row['thread_id'] == recipient and
                         row['task_version'] == owner['task_version'] and
                         (task_version is None or type(task_version) is int and
                          task_version == owner['task_version']))
            reason = ('use the existing App recipient; mesh work was not sent' if valid else
                      'external owner/task version does not match the registered session and message')
        return {'recipient_thread_id': recipient if isinstance(recipient, str) else None,
                'declaration_hash': digest, 'valid': valid, 'reason': reason}

    def assert_mesh_owned(self, task_id: str, task_version: int | None = None) -> None:
        owner = self.external_owner(task_id, task_version)
        if owner is not None:
            raise ExternalOwnerRequired(owner)

    def external_delivery(self, message_id: str) -> dict | None:
        row = self.db.execute('SELECT * FROM external_deliveries WHERE message_id=?',
                              (message_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result['envelope'] = json.loads(result.pop('envelope_json'))
        receipt = result.pop('receipt_json')
        result['receipt'] = json.loads(receipt) if receipt else None
        return result

    def external_deliveries(self) -> list[dict]:
        return [self.external_delivery(row[0]) for row in self.db.execute(
            'SELECT message_id FROM external_deliveries ORDER BY created_at,message_id')]

    def defer_external(self, message, owner: dict) -> dict:
        """Commit the full unsent envelope before the controller consumes its inbox row."""
        existing = self.external_delivery(message.message_id)
        if existing is not None:
            if existing['envelope'] != json.loads(message.to_json()):
                raise ValueError('external delivery message ID has different content')
            return existing
        prior = self.result(message.message_id)
        if prior and prior['status'] != 'queued':
            raise ValueError('cannot defer previously executed or ambiguous work')
        with self.db:
            self.db.execute('INSERT INTO external_deliveries VALUES (?,?,?,?,?,?,?,?,?,?)', (
                message.message_id, message.task_id, message.task_version,
                owner['recipient_thread_id'], owner['declaration_hash'], owner['reason'],
                message.to_json(), 'pending', None, now()))
            self.db.execute('INSERT INTO main_runs VALUES (?,?,?,?,?,?) ON CONFLICT(message_id) '
                            'DO UPDATE SET status=excluded.status,result_json=excluded.result_json,'
                            'error=excluded.error,updated_at=excluded.updated_at', (
                message.message_id, message.task_id, 'delivery_pending',
                json.dumps({'recipient_thread_id': owner['recipient_thread_id'],
                            'reason': owner['reason'], 'execution_started': False}), None, now()))
        self.changed.set()
        return self.external_delivery(message.message_id)

    def external_receipt(self, *, message_id: str, task_id: str, task_version: int,
                         thread_id: str, turn_id: str, evidence: str) -> dict:
        if type(task_version) is not int or task_version < 1:
            raise ValueError('positive integer receipt task_version required')
        delivery = self.external_delivery(message_id)
        if delivery is None:
            raise KeyError('unknown external delivery')
        if (delivery['task_id'], delivery['task_version'], delivery['recipient_thread_id']) != (
                task_id, task_version, thread_id):
            raise ValueError('receipt must match the saved task/version/recipient')
        if not isinstance(turn_id, str) or not turn_id.strip() or not isinstance(evidence, str) or not evidence.strip():
            raise ValueError('actual App turn and consumption evidence required')
        receipt = {'thread_id': thread_id, 'turn_id': turn_id, 'evidence': evidence}
        if delivery['receipt'] is not None:
            if delivery['receipt'] != receipt:
                raise ValueError('external receipt is immutable')
            return delivery
        owner = self.external_owner(task_id, task_version)
        if not owner or not owner['valid'] or owner['declaration_hash'] != delivery['declaration_hash']:
            raise ValueError('ownership changed; explicitly reconcile the saved delivery')
        with self.db:
            self.db.execute("UPDATE external_deliveries SET status='consumed',receipt_json=? WHERE message_id=?",
                            (json.dumps(receipt), message_id))
            self.db.execute("UPDATE main_runs SET status='external_consumed',result_json=?,updated_at=? WHERE message_id=? AND status='delivery_pending'",
                            (json.dumps(receipt), now(), message_id))
        self.changed.set()
        return self.external_delivery(message_id)

    async def catalog(self, client, *, refresh: bool = False) -> dict[str, tuple[str, ...]]:
        async with self._catalog_lock:
            if self._models and not refresh:
                return self._models
            models = {}
            cursor = None
            seen = set()
            while True:
                args = {'includeHidden': False}
                if cursor:
                    args['cursor'] = cursor
                result = await client.session.request('model/list', args)
                for item in result.get('data', []):
                    model = item.get('model') or item.get('id')
                    if not isinstance(model, str) or not re.fullmatch(r'[a-zA-Z0-9_.-]+', model) or item.get('hidden'):
                        continue
                    efforts = tuple(e.get('reasoningEffort') if isinstance(e, dict) else e
                                    for e in item.get('supportedReasoningEfforts', []))
                    efforts = tuple(e for e in efforts if e in EFFORT_ORDER)
                    if efforts:
                        models[model] = efforts
                cursor = result.get('nextCursor')
                if not cursor:
                    break
                if cursor in seen:
                    raise RuntimeError('Official model pagination repeated a cursor')
                seen.add(cursor)
            if not models:
                raise RuntimeError('No verified GPT models/efforts are available')
            self._models = models
            return self._models

    def best(self) -> tuple[str, str]:
        choices = (self.quality_model, 'gpt-6-astra', 'gpt-6.1-sol', 'gpt-6-sol')
        model = next((m for m in choices if m in self._models), next(iter(self._models)))
        return model, max(self._models[model], key=EFFORT_ORDER.index)

    def guard(self, model: str, effort: str, category: str) -> None:
        if category not in KINDS:
            raise ValueError('unknown work category')
        if model not in self._models or effort not in self._models[model]:
            raise ValueError('model/effort is not in the verified GPT catalog')
        if category in CRITICAL and (model, effort) != self.best():
            raise ValueError('critical work requires the quality main model at highest effort')

    async def choose(self, client, text: str, category: str | None = None) -> dict:
        await self.catalog(client)
        if category is not None and category not in KINDS:
            raise ValueError('unknown work category')
        important = IMPORTANT.search(text) is not None or category in CRITICAL
        if not important and ROUTINE.fullmatch(text):
            model = next((m for m in ('gpt-6-luna', 'gpt-5.6-luna', 'gpt-6.1-sol') if m in self._models), self.best()[0])
            effort = min(self._models[model], key=EFFORT_ORDER.index)
            return {'model': model, 'effort': effort, 'category': 'routine'}
        model, effort = self.best()
        return {'model': model, 'effort': effort,
                'category': category if category in CRITICAL else 'difficult'}

    def session(self, task_id: str) -> dict | None:
        row = self.db.execute('SELECT * FROM main_sessions WHERE task_id=?', (task_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result.pop('pending_json', None)
        return result

    def sessions(self) -> list[dict]:
        return [self.session(r['task_id']) for r in self.db.execute('SELECT task_id FROM main_sessions ORDER BY updated_at')]

    async def schedule_route(self, client, *, task_id: str, model: str, effort: str, category: str = 'execution') -> dict:
        self.assert_mesh_owned(task_id)
        await self.catalog(client)
        self.assert_mesh_owned(task_id)
        self.guard(model, effort, category)
        if self.session(task_id) is None:
            raise KeyError('main task session is not registered')
        route = {'model': model, 'effort': effort, 'category': category}
        with self.db:
            self.db.execute('UPDATE main_sessions SET pending_json=?, updated_at=? WHERE task_id=?', (json.dumps(route), now(), task_id))
        return {'task_id': task_id, **route, 'applies': 'next_turn'}

    async def open_session(self, client, *, task_id: str, task_version: int, text: str, cwd: str,
                           model: str | None = None, effort: str | None = None,
                           category: str | None = None, config=None, dynamic_tools=None,
                           developer_instructions=None) -> dict:
        if not task_id.strip() or task_version < 1 or not text.strip():
            raise ValueError('task_id, positive version and text are required')
        async with self._allocation:
            self.assert_mesh_owned(task_id, task_version)
            existing = self.session(task_id)
            if existing:
                return {**existing, 'created': False}
            route = await self.choose(client, text, category)
            self.assert_mesh_owned(task_id, task_version)
            if model is not None or effort is not None:
                if model is None or effort is None:
                    raise ValueError('model and effort must be specified together')
                # Explicit execution routes are permitted; critical categories never downgrade.
                route = {'model': model, 'effort': effort, 'category': category or 'execution'}
                self.guard(**route)
                if IMPORTANT.search(text) and (model, effort) != self.best():
                    raise ValueError('critical task text cannot be downgraded')
            thread_config = dict(config or {})
            thread_config['model_reasoning_effort'] = route['effort']
            started = await client.thread_start(cwd=cwd, model=route['model'], model_provider='openai',
                config=thread_config, dynamic_tools=dynamic_tools, developer_instructions=developer_instructions)
            thread_id = started['thread']['id']
            title = f'{task_id}: {text.splitlines()[0][:60]}'
            # Title is cosmetic; old clients may not support naming.
            try:
                await client.session.request('thread/name/set', {'threadId': thread_id, 'name': title})
            except Exception:
                pass
            with self.db:
                self.db.execute('INSERT INTO main_sessions VALUES (?,?,?,?,?,?,?,?,?)',
                    (task_id, thread_id, task_version, route['model'], route['effort'], route['category'], title,
                     json.dumps(route) if model is not None else None, now()))
            self._loaded.add(thread_id)
            return {**self.session(task_id), 'created': True}

    async def prepare(self, client, message, *, cwd, config=None, dynamic_tools=None, developer_instructions=None) -> dict:
        self.assert_mesh_owned(message.task_id, message.task_version)
        text = str(message.payload.get('text', message.message_id))
        row = await self.open_session(client, task_id=message.task_id, task_version=message.task_version,
            text=text, cwd=cwd, category=message.payload.get('category'), config=config,
            dynamic_tools=dynamic_tools, developer_instructions=developer_instructions)
        if message.task_version < row['task_version']:
            raise ValueError('stale main task version')
        chosen = await self.choose(client, text, message.payload.get('category'))
        self.assert_mesh_owned(message.task_id, message.task_version)
        pending = self.db.execute('SELECT pending_json FROM main_sessions WHERE task_id=?', (message.task_id,)).fetchone()[0]
        if pending and not IMPORTANT.search(text) and message.payload.get('category') not in CRITICAL:
            chosen = json.loads(pending)
            self.guard(**chosen)
        if row['thread_id'] not in self._loaded:
            await client.session.request('thread/resume', {
                'threadId': row['thread_id'], 'cwd': cwd, 'model': chosen['model'], 'modelProvider': 'openai',
                'config': {**(config or {}), 'model_reasoning_effort': chosen['effort']},
                'developerInstructions': developer_instructions,
            })
            self._loaded.add(row['thread_id'])
        self.assert_mesh_owned(message.task_id, message.task_version)
        with self.db:
            self.db.execute('UPDATE main_sessions SET task_version=?,model=?,effort=?,category=?,pending_json=NULL,updated_at=? WHERE task_id=?',
                (message.task_version, chosen['model'], chosen['effort'], chosen['category'], now(), message.task_id))
        return self.session(message.task_id)

    def result(self, message_id: str) -> dict | None:
        row = self.db.execute('SELECT * FROM main_runs WHERE message_id=?', (message_id,)).fetchone()
        if not row:
            return None
        return {'message_id': message_id, 'task_id': row['task_id'], 'status': row['status'],
                'result': json.loads(row['result_json']) if row['result_json'] else None, 'error': row['error']}

    def record(self, message_id: str, task_id: str, status: str, *, result=None, error=None) -> None:
        with self.db:
            self.db.execute('INSERT INTO main_runs VALUES (?,?,?,?,?,?) ON CONFLICT(message_id) DO UPDATE SET status=excluded.status,result_json=excluded.result_json,error=excluded.error,updated_at=excluded.updated_at',
                (message_id, task_id, status, json.dumps(result, ensure_ascii=False) if result is not None else None, error, now()))
        self.changed.set()

    def reset_connection(self) -> None:
        self._loaded.clear()
        self._models.clear()

    def close(self) -> None:
        self.db.close()
