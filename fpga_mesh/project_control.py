"""Authenticated project front door shared by all local GPT conversations."""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import secrets
from pathlib import Path
from datetime import datetime, timezone
from .child_control import LocalControlServer, LocalControlFileClient
from .protocol import Envelope, MessageKind, SourceKind
from .mesh_tools import MeshDynamicTools
from .official_models import OfficialModelManager


def tool(name, description, properties, required):
    return {'type': 'function', 'name': name, 'description': description,
            'inputSchema': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}}


TASK_FIELDS = {'task_id': {'type': 'string'}, 'task_version': {'type': 'integer', 'minimum': 1},
               'text': {'type': 'string'}, 'model': {'type': 'string'}, 'effort': {'type': 'string'},
               'category': {'type': 'string', 'enum': ['routine', 'execution', 'decision', 'acceptance', 'difficult', 'optimization', 'evaluation']}}
CONTINUITY_TOOLS = [
    tool('fpga_self_check', 'Read persistent continuity incidents, actual watches/receipts and loaded-source fingerprints. No inference, repair creation or message dispatch.', {}, []),
    tool('fpga_continuity_watch', 'Explicitly watch one existing child/main result for one actual recipient. auto_resume opts into one STOP-aware continuation to an existing registered main only; App proxies require their App tools. Does not transfer ownership.', {
        'watch_id': {'type': 'string'}, 'task_id': {'type': 'string'}, 'task_version': {'type': 'integer', 'minimum': 1},
        'source_kind': {'type': 'string', 'enum': ['child', 'main']}, 'source_id': {'type': 'string'},
        'recipient_thread_id': {'type': 'string'}, 'auto_resume': {'type': 'boolean'}},
        ['watch_id', 'task_id', 'task_version', 'source_kind', 'source_id', 'recipient_thread_id']),
    tool('fpga_continuity_receipt', 'Record actual recipient processing of a watched result. Queued or transport ACK is insufficient.', {
        'watch_id': {'type': 'string'}, 'thread_id': {'type': 'string'}, 'turn_id': {'type': 'string'}, 'evidence': {'type': 'string'}},
        ['watch_id', 'thread_id', 'turn_id', 'evidence']),
    tool('fpga_continuity_repair', 'Claim a single bounded repair before authorized App creation, then record created/started/unknown outcome. Requires existing human authorization and actual App capability; this is not a native lease or product appointment. Never repeat execute=false or unknown.', {
        'incident_id': {'type': 'string'}, 'phase': {'type': 'string', 'enum': ['claim', 'created', 'started', 'unknown']},
        'owner_thread_id': {'type': 'string'}, 'thread_id': {'type': 'string'}, 'turn_id': {'type': 'string'}},
        ['incident_id', 'phase', 'owner_thread_id']),
]
SESSION_TOOLS = CONTINUITY_TOOLS + [
    tool('fpga_models_refresh', 'Refresh the official Codex model/effort catalog and native roles. Preserves current tasks, credentials and both execution entrances; makes no inference call. New role definitions apply to newly loaded conversations.', {}, []),
    tool('fpga_session_list', 'Read your project main sessions, allowed models/efforts and quality route without a model call.', {}, []),
    tool('fpga_session_open', 'Create a separate task conversation and queue its work. Choose optional allowed model/effort; critical work requires the quality main route. Repeated same work does not enqueue twice.', TASK_FIELDS, ['task_id', 'task_version', 'text']),
    tool('fpga_session_route', 'Select this task conversation model and reasoning depth for its next turn. Current generation completes with its original model. Critical work cannot be downgraded.', {k: TASK_FIELDS[k] for k in ['task_id', 'model', 'effort', 'category']}, ['task_id', 'model', 'effort', 'category']),
]


class ProjectActions:
    def __init__(self, runtime):
        self.runtime = runtime
        self.changed = runtime.main_sessions.changed
        self.models = OfficialModelManager(
            getattr(getattr(runtime.astra_gateway, 'config', None), 'codex_home', Path.home() / '.codex'),
            runtime.config.state_dir,
        )
        saved = self.models.snapshot()
        if saved.get('quality_model'):
            runtime.main_sessions.quality_model = saved['quality_model']

    @staticmethod
    def specs():
        return SESSION_TOOLS

    async def call(self, name, args):
        action = {'fpga_session_list': 'session_list', 'fpga_session_open': 'main_submit',
                  'fpga_session_route': 'session_route', 'fpga_models_refresh': 'models_refresh'}.get(name, name)
        r = self.runtime
        if action in {'fpga_self_check', 'self_check', 'fpga_continuity_watch', 'continuity_watch',
                      'fpga_continuity_receipt', 'continuity_receipt', 'fpga_continuity_repair', 'continuity_repair'}:
            monitor = r.continuity
            snapshot = monitor.check()
            operation = action.removeprefix('fpga_')
            if operation == 'self_check':
                return {**monitor.journal.status(), 'observed_at': snapshot['observed_at'],
                        'loaded_source_hashes': monitor.loaded_hashes, 'monitor_error': monitor.error}
            if operation == 'continuity_watch':
                sources = snapshot['jobs'] if args['source_kind'] == 'child' else snapshot['runs']
                key = 'job_id' if args['source_kind'] == 'child' else 'message_id'
                if not any(x[key] == args['source_id'] and x['task_id'] == args['task_id'] and
                           x.get('task_version') == args['task_version'] for x in sources):
                    raise ValueError('watch requires an existing source belonging to this task')
                if args.get('auto_resume') and not any(x['task_id'] == args['task_id'] and
                        x['task_version'] == args['task_version'] and x['thread_id'] == args['recipient_thread_id']
                        for x in snapshot['sessions']):
                    raise ValueError('automatic continuation requires exact existing main route/version')
                result = monitor.journal.watch(**args)
            elif operation == 'continuity_receipt':
                result = monitor.journal.receipt(**args)
            else:
                result = monitor.journal.repair(**args, paused=r.controller.dispatch_blocked)
            monitor.notify()
            return result
        if action == 'models_list':
            return self.models.snapshot()
        if action == 'models_refresh':
            if r.config.mode == 'test_double':
                raise RuntimeError('official model updates require app-server mode')
            return await self.models.refresh(r.main_sessions)
        if action in {spec['name'] for spec in MeshDynamicTools.main_specs()}:
            return await r.mesh_tools.call(action, args)
        if action == 'health':
            return {**r.snapshot(), 'pid': os.getpid(), 'identities': {'main': f'Astra-{r.config.node_id}', 'deepseek': f'DeepSeek-{r.config.node_id}'}, 'main_sessions': r.main_sessions.sessions()}
        if action in {'session_list', 'session_route', 'main_submit'}:
            gateway = r.astra_gateway
            client = await gateway._ensure_client() if hasattr(gateway, '_ensure_client') else None
            if action == 'session_list':
                catalog = await r.main_sessions.catalog(client) if client else {}
                return {'sessions': r.main_sessions.sessions(), 'allowed_models': catalog,
                        'quality_route': r.main_sessions.best() if catalog else None}
            if action == 'session_route':
                if client is None:
                    raise RuntimeError('model routes require app-server mode')
                return await r.main_sessions.schedule_route(client, **args)
            task_id = str(args['task_id']).strip()
            version = int(args['task_version'])
            text = str(args['text']).strip()
            if not task_id or not text or version < 1:
                raise ValueError('task id, positive version and text are required')
            category = args.get('category')
            body = {'task_id': task_id, 'task_version': version, 'text': text, 'category': category}
            digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            message_id = f'main:{digest}'
            prior = r.main_sessions.result(message_id)
            if prior is not None:
                return {'message_id': message_id, 'queued': False, 'task_id': task_id,
                        'session': r.main_sessions.session(task_id), 'identity': f'Astra-{r.config.node_id}'}
            session = None
            if client:
                session = await r.main_sessions.open_session(client, task_id=task_id, task_version=version, text=text,
                    cwd=gateway.config.cwd, model=args.get('model'), effort=args.get('effort'), category=category,
                    config=gateway.thread_config_factory() if gateway.thread_config_factory else None,
                    dynamic_tools=gateway.dynamic_tools, developer_instructions=gateway.developer_instructions)
                if not session['created'] and args.get('model'):
                    await r.main_sessions.schedule_route(client, task_id=task_id, model=args['model'], effort=args['effort'], category=category or 'execution')
            message = Envelope(message_id=message_id, project_id=r.config.project_id,
                sender=f'{r.config.node_id}/Astra-{r.config.node_id}', recipient=f'{r.config.node_id}/Astra-{r.config.node_id}',
                task_id=task_id, task_version=version, sent_at=datetime.now(timezone.utc),
                kind=MessageKind.AGENT_REPORT, source=SourceKind.ASTRA, payload={'text': text, **({'category': category} if category else {})})
            if r.main_sessions.result(message_id) is None:
                r.main_sessions.record(message_id, task_id, 'queued')
            queued = await r.controller.offer(message)
            return {'message_id': message_id, 'queued': queued, 'task_id': task_id,
                    'session': session, 'identity': f'Astra-{r.config.node_id}'}
        if action == 'main_result':
            return r.main_sessions.result(str(args['message_id']))
        if action == 'main_wait':
            timeout = float(args.get('timeout_seconds', 60))
            if timeout <= 0 or timeout > 3600:
                raise ValueError('timeout must be between 0 and 3600 seconds')
            async def wait():
                while True:
                    self.changed.clear()
                    result = r.main_sessions.result(str(args['message_id']))
                    if result is None:
                        raise KeyError('unknown main message')
                    if result['status'] in {'completed', 'failed', 'interrupted'}:
                        return result
                    await self.changed.wait()
            try:
                return await asyncio.wait_for(wait(), timeout=timeout)
            except asyncio.TimeoutError:
                return r.main_sessions.result(str(args['message_id']))
        # Both GPT native and DeepSeek entrances reach the same child ledger.
        client = LocalControlFileClient(r.config.state_dir / 'child-control.json')
        return await client.call(action, args)


class ProjectControlServer(LocalControlServer):
    def __init__(self, actions, *, discovery_path):
        super().__init__(None, token=secrets.token_urlsafe(32), discovery_path=discovery_path)
        self.actions = actions

    async def _handle(self, reader, writer):
        try:
            request = json.loads(await reader.readline())
            if not secrets.compare_digest(str(request.get('token', '')), self.token):
                raise PermissionError('invalid project control token')
            args = request.get('arguments') or {}
            if not isinstance(args, dict):
                raise ValueError('arguments must be an object')
            result = await self.actions.call(str(request.get('action', '')), args)
            response = {'result': result}
        except Exception as exc:
            response = {'error': {'type': type(exc).__name__, 'message': str(exc)[:300]}}
        try:
            writer.write((json.dumps(response, ensure_ascii=False) + '\n').encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
