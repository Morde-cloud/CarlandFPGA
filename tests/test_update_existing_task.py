"""End-to-end PowerShell fixtures for preserving an existing node task.

These tests copy the real updater/helper scripts into a synthetic package and
execute them in a fresh Windows PowerShell process. ScheduledTasks cmdlets are
shadowed before the updater runs; no real task, service, config or credential is
reachable from the fixture.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).resolve().parent / 'fixtures' / 'update_existing_task'
RUNTIME_DIR = Path(os.environ.get('FPGA_FIXTURE_RUNTIME', str(FIXTURE_DIR / 'runtime')))
SOURCE_UPDATER = REPO / 'deploy' / 'Update-FPGAMesh.ps1'
SOURCE_HELPER = REPO / 'deploy' / 'Preserve-FPGAMeshTask.ps1'
POWERSHELL = shutil.which('powershell.exe') or r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _read_events(path):
    events = []
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


def _count(events, action):
    return sum(1 for event in events if event.get('action') == action)


def _shim_commands(events):
    return [event.get('data', {}).get('argv', []) for event in events
            if event.get('action') == 'python_shim']


def _toml_string(value):
    return json.dumps(str(value))


def _routing_toml(workspace, command, control, args=None, root=None,
                  enabled=True, startup_timeout=20, tool_timeout=3600):
    args = ['-m', 'fpga_mesh.project_mcp'] if args is None else args
    root = workspace if root is None else root
    lines = [
        'model = "fixture-model"',
        '',
        '[mcp_servers.fpga_mesh]',
        'command = ' + _toml_string(command),
        'args = ' + json.dumps(args),
        'enabled = ' + ('true' if enabled else 'false'),
        'startup_timeout_sec = ' + str(startup_timeout),
        'tool_timeout_sec = ' + str(tool_timeout),
        '',
        '[mcp_servers.fpga_mesh.env]',
        'PYTHONPATH = ' + _toml_string(root),
        'FPGA_MAIN_CONTROL_FILE = ' + _toml_string(control),
        '',
    ]
    return '\n'.join(lines)


class ExistingTaskFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name != 'nt':
            raise unittest.SkipTest('Windows ScheduledTasks fixture requires Windows')
        if not SOURCE_UPDATER.is_file():
            raise AssertionError('missing updater: ' + str(SOURCE_UPDATER))
        if not SOURCE_HELPER.is_file():
            raise AssertionError('missing helper: ' + str(SOURCE_HELPER))
        if not Path(POWERSHELL).is_file():
            raise AssertionError('missing powershell.exe: ' + str(POWERSHELL))
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    def _launcher_arguments(self, workspace, config):
        launcher = workspace / '.local' / 'deployment' / 'node-b' / 'launch-node-b.py'
        node_dir = config.parent
        ready = node_dir / 'ready.json'
        log = node_dir / 'service.log'
        return '"{}" --config "{}" --ready-file "{}" --log-file "{}"'.format(
            launcher, config, ready, log)

    def _module_arguments(self, config):
        ready = config.parent / 'ready.json'
        log = config.parent / 'service.log'
        return '-m fpga_mesh.supervisor --config "{}" --ready-file "{}" --log-file "{}"'.format(
            config, ready, log)

    def _run_case(self, *, action_kind='launcher', action_arguments=None,
                  action_transform=None, check_only=False, routing=None,
                  create_config=True, env_overrides=None):
        root = Path(tempfile.mkdtemp(prefix='case-', dir=str(RUNTIME_DIR)))
        if not root.resolve().is_relative_to(RUNTIME_DIR.resolve()):
            raise AssertionError('Fixture cleanup target escaped runtime directory')
        self.addCleanup(shutil.rmtree, root)
        package = root / 'package'
        deploy = package / 'deploy'
        source_pkg = package / 'fpga_mesh'
        workspace = root / 'workspace'
        node_dir = workspace / '.local' / 'deployment' / 'node-b'
        codex_dir = workspace / '.codex'
        agents_dir = codex_dir / 'agents'
        for directory in (deploy, source_pkg, node_dir, agents_dir,
                          workspace / 'bin'):
            directory.mkdir(parents=True, exist_ok=True)

        updater = deploy / 'Update-FPGAMesh.ps1'
        shutil.copy2(SOURCE_UPDATER, updater)
        shutil.copy2(SOURCE_HELPER, deploy / 'Preserve-FPGAMeshTask.ps1')
        (source_pkg / 'update.py').write_text('# fixture updater\n', encoding='utf-8')
        package_file = root / 'package.zip'
        package_file.write_bytes(b'fixture-package')

        config = node_dir / 'node-b.toml'
        config.write_text('node_id = "B"\n', encoding='utf-8')
        node_config_before = config.read_bytes()
        launcher = node_dir / 'launch-node-b.py'
        launcher.write_bytes(b'# fixture launch-node-b.py\nprint("fixture")\n')
        launcher_before = launcher.read_bytes()
        control = workspace / 'main-control.json'
        control.write_text('{"fixture": true}\n', encoding='utf-8')
        shim = workspace / 'bin' / 'python-fixture.ps1'
        shutil.copy2(FIXTURE_DIR / 'PythonShim.ps1', shim)

        roles = {}
        for name in ('default', 'worker', 'explorer'):
            role = agents_dir / (name + '.toml')
            role.write_text('name = "{}"\nfixture = "preserve"\n'.format(name), encoding='utf-8')
            roles[role] = role.read_bytes()

        routing_options = dict(routing or {})
        if create_config:
            if 'raw' in routing_options:
                config_text = routing_options['raw']
            else:
                config_text = _routing_toml(
                    workspace,
                    routing_options.get('command', shim),
                    routing_options.get('control', control),
                    routing_options.get('args'),
                    routing_options.get('root'),
                    routing_options.get('enabled', True),
                    routing_options.get('startup_timeout', 20),
                    routing_options.get('tool_timeout', 3600),
                )
            codex_dir.joinpath('config.toml').write_text(config_text, encoding='utf-8')
        routing_config = codex_dir / 'config.toml'
        routing_config_before = routing_config.read_bytes() if create_config else None

        if action_arguments is None:
            if action_kind == 'module':
                action_arguments = self._module_arguments(config)
            else:
                action_arguments = self._launcher_arguments(workspace, config)
        if action_transform is not None:
            action_arguments = action_transform(action_arguments)

        log_path = root / 'fixture-events.jsonl'
        xml_path = root / 'task-live.xml'
        live_xml_path = root / 'task-mutated.xml'
        env = {key: value for key, value in os.environ.items()
               if not key.startswith('FIXTURE_')}
        env.update({
            'FIXTURE_LOG': str(log_path),
            'FIXTURE_XML_PATH': str(xml_path),
            'FIXTURE_LIVE_XML': str(live_xml_path),
            'FIXTURE_CONTROL_FILE': str(control),
            'FIXTURE_REAL_PYTHON': sys.executable,
            'FIXTURE_ACTION_ARGUMENTS': action_arguments,
            'FIXTURE_LAUNCHER_PATH': str(launcher),
            'FIXTURE_ROUTING_PATH': str(routing_config),
        })
        if env_overrides:
            env.update({key: str(value) for key, value in env_overrides.items()})

        call = [
            str(POWERSHELL), '-NoLogo', '-NoProfile', '-NonInteractive',
            '-ExecutionPolicy', 'Bypass', '-File',
            str(FIXTURE_DIR / 'Invoke-Fixture.ps1'),
            '-Updater', str(updater), '-Node', 'B', '-Workspace', str(workspace),
            '-Package', str(package_file), '-Config', str(config),
            '-Python', str(shim),
        ]
        if check_only:
            call.append('-CheckOnly')
        proc = subprocess.run(
            call, cwd=str(workspace), env=env, capture_output=True, timeout=90,
        )
        raw_stdout, raw_stderr = proc.stdout, proc.stderr
        proc.stdout = raw_stdout.decode('utf-8', 'replace')
        proc.stderr = raw_stderr.decode('utf-8', 'replace')
        events = _read_events(log_path)
        result = {
            'root': root, 'workspace': workspace, 'config': config,
            'launcher': launcher, 'launcher_bytes': launcher_before,
            'roles': roles, 'node_config_before': node_config_before, 'routing_config': routing_config, 'routing_config_before': routing_config_before, 'xml_path': xml_path, 'live_xml_path': live_xml_path,
            'proc': proc, 'events': events, 'log_path': log_path,
            'shim': shim, 'control': control,
        }
        result['xml_text'] = xml_path.read_text(encoding='utf-8-sig') if xml_path.exists() else ''
        result['task_calls'] = {
            name: _count(events, name) for name in (
                'Get-ScheduledTask', 'Export-ScheduledTask', 'Start-ScheduledTask',
                'Stop-ScheduledTask', 'Set-ScheduledTask', 'Register-ScheduledTask',
                'Unregister-ScheduledTask', 'Enable-ScheduledTask', 'Disable-ScheduledTask')
        }
        result['shim_counts'] = {
            name: _count(events, name) for name in (
                'preflight', 'stop_idle', 'apply', 'health', 'scope_audit',
                'forbidden_command', 'routing_forward', 'unknown_command')
        }
        result['shim_commands'] = _shim_commands(events)
        result['forbidden_commands'] = [
            argv for argv in result['shim_commands']
            if any(token in argv for token in ('fpga_mesh.install_routing', 'models_refresh', 'register-autostart'))
        ]
        evidence_root = os.environ.get('FPGA_FIXTURE_EVIDENCE')
        if evidence_root:
            evidence = Path(evidence_root) / root.name
            evidence.mkdir(parents=True, exist_ok=False)
            (evidence / 'stdout.txt').write_bytes(raw_stdout)
            (evidence / 'stderr.txt').write_bytes(raw_stderr)
            if log_path.exists():
                shutil.copyfile(log_path, evidence / 'events.jsonl')
            record = {'test': self.id(), 'command': call, 'exit_code': proc.returncode,
                      'task_calls': result['task_calls'], 'shim_counts': result['shim_counts'],
                      'launcher_before_sha256': _sha256_bytes(launcher_before),
                      'launcher_after_sha256': _sha256_bytes(launcher.read_bytes()),
                      'scenario': env_overrides or {}}
            (evidence / 'command.json').write_bytes((json.dumps(record, indent=2) + '\n').encode())
            for snapshot in self._snapshots(result):
                for name in ('snapshot.json', 'update-result.json'):
                    if (snapshot / name).exists():
                        shutil.copyfile(snapshot / name, evidence / name)
        return result

    def _snapshots(self, result):
        base = result['workspace'] / '.local' / 'update-preservation'
        return sorted(p for p in base.glob('*') if p.is_dir()) if base.is_dir() else []

    def _assert_task_mutators_zero(self, result):
        for name in ('Stop-ScheduledTask', 'Set-ScheduledTask', 'Register-ScheduledTask',
                     'Unregister-ScheduledTask', 'Enable-ScheduledTask', 'Disable-ScheduledTask'):
            self.assertEqual(result['task_calls'][name], 0, name)

    def _assert_no_admission(self, result):
        self._assert_task_mutators_zero(result)
        self.assertEqual(result['shim_counts']['stop_idle'], 0, result['proc'].stderr)
        self.assertEqual(result['shim_counts']['apply'], 0, result['proc'].stderr)
        self.assertEqual(result['shim_counts']['health'], 0)
        self.assertEqual(result['task_calls']['Start-ScheduledTask'], 0)
        self.assertEqual(result['shim_counts']['forbidden_command'], 0)
        self.assertFalse(result['forbidden_commands'])

    def _assert_roles_unchanged(self, result):
        for path, before in result['roles'].items():
            self.assertEqual(path.read_bytes(), before, str(path))

    def _update_result(self, result):
        snapshots = self._snapshots(result)
        self.assertEqual(len(snapshots), 1, result['proc'].stderr)
        path = snapshots[0] / 'update-result.json'
        self.assertTrue(path.is_file(), result['proc'].stderr)
        return json.loads(path.read_text(encoding='utf-8-sig'))

    def _assert_success(self, result):
        self.assertEqual(result['proc'].returncode, 0, result['proc'].stderr + result['proc'].stdout)
        self._assert_task_mutators_zero(result)
        self.assertEqual(result['shim_counts']['stop_idle'], 1)
        self.assertEqual(result['shim_counts']['apply'], 1)
        self.assertEqual(result['shim_counts']['health'], 1)
        self.assertEqual(result['shim_counts']['scope_audit'], 1)
        self.assertEqual(result['task_calls']['Start-ScheduledTask'], 1)
        start = next(event for event in result['events'] if event['action'] == 'Start-ScheduledTask')
        self.assertEqual(start['data'], {'taskName': 'FPGA-Mesh-Node-B', 'taskPath': '\\'})
        self.assertEqual(result['shim_counts']['forbidden_command'], 0)
        self.assertFalse(result['forbidden_commands'])
        self._assert_roles_unchanged(result)
        self.assertEqual(result['config'].read_bytes(), result['node_config_before'])
        self.assertEqual(result['routing_config'].read_bytes(), result['routing_config_before'])

    def test_custom_launcher_task_is_preserved_end_to_end(self):
        result = self._run_case()
        self._assert_success(result)
        snapshots = self._snapshots(result)
        self.assertEqual(len(snapshots), 1, result['proc'].stderr)
        snapshot = snapshots[0]
        self.assertEqual((snapshot / 'task-before.xml').read_text(encoding='utf-8-sig'), result['xml_text'])
        self.assertEqual((snapshot / 'launcher-before.bin').read_bytes(), result['launcher_bytes'])
        self.assertEqual(result['launcher'].read_bytes(), result['launcher_bytes'])
        self.assertFalse(result['live_xml_path'].exists())
        metadata = json.loads((snapshot / 'snapshot.json').read_text(encoding='utf-8-sig'))
        self.assertIn('LogonTrigger', metadata['Triggers'])
        self.assertIn('BootTrigger', metadata['Triggers'])
        self.assertIn('RestartOnFailure', metadata['Settings'])
        self.assertIn('IgnoreNew', metadata['Settings'])
        self.assertIn('FPGA Mesh B controller', metadata['Description'])
        update_result = self._update_result(result)
        self.assertEqual(update_result['status'], 'completed')
        self.assertEqual(update_result['phase'], 'completed')
        self.assertFalse(update_result['automaticReplay'])

    def test_module_action_task_is_preserved_end_to_end(self):
        result = self._run_case(action_kind='module')
        self._assert_success(result)
        snapshots = self._snapshots(result)
        self.assertEqual(len(snapshots), 1, result['proc'].stderr)
        snapshot = snapshots[0]
        self.assertEqual((snapshot / 'task-before.xml').read_text(encoding='utf-8-sig'), result['xml_text'])
        self.assertFalse((snapshot / 'launcher-before.bin').exists())
        self.assertEqual(result['launcher'].read_bytes(), result['launcher_bytes'])
        metadata = json.loads((snapshot / 'snapshot.json').read_text(encoding='utf-8-sig'))
        self.assertIsNone(metadata['LauncherPath'])
        self.assertIn('fpga_mesh.supervisor', metadata['Actions'])
        self.assertIn('LogonTrigger', metadata['Triggers'])
        self.assertIn('BootTrigger', metadata['Triggers'])
        update_result = self._update_result(result)
        self.assertEqual(update_result['status'], 'completed')
        self.assertEqual(update_result['phase'], 'completed')
        self.assertFalse(update_result['automaticReplay'])

    def test_check_only_has_zero_writes_and_zero_mutations(self):
        result = self._run_case(check_only=True)
        self.assertEqual(result['proc'].returncode, 0, result['proc'].stderr + result['proc'].stdout)
        self._assert_task_mutators_zero(result)
        self.assertEqual(result['task_calls']['Start-ScheduledTask'], 0)
        self.assertEqual(result['shim_counts']['stop_idle'], 0)
        self.assertEqual(result['shim_counts']['apply'], 0)
        self.assertEqual(result['shim_counts']['health'], 0)
        self.assertEqual(result['shim_counts']['scope_audit'], 0)
        self.assertEqual(result['shim_counts']['forbidden_command'], 0)
        self.assertFalse(result['forbidden_commands'])
        self.assertEqual(self._snapshots(result), [])
        self.assertEqual(result['launcher'].read_bytes(), result['launcher_bytes'])
        self._assert_roles_unchanged(result)
        self.assertEqual(result['config'].read_bytes(), result['node_config_before'])
        self.assertEqual(result['routing_config'].read_bytes(), result['routing_config_before'])

    def test_invalid_task_inventory_refuses_before_admission(self):
        cases = [
            ('missing-task', {'FIXTURE_TASK_MISSING': '1'}, None),
            ('wrong-task-name', {'FIXTURE_TASK_NAME_MODE': 'wrong'}, None),
            ('wrong-task-path', {'FIXTURE_TASK_PATH_MODE': 'wrong'}, None),
            ('wrong-description', {'FIXTURE_DESCRIPTION_MODE': 'wrong'}, None),
            ('wrong-principal', {'FIXTURE_PRINCIPAL_MODE': 'wrong'}, None),
            ('wrong-action-python', {'FIXTURE_ACTION_EXECUTE_MODE': 'wrong'}, None),
            ('wrong-action-workdir', {'FIXTURE_ACTION_WORKDIR_MODE': 'wrong'}, None),
            ('two-actions', {'FIXTURE_ACTION_COUNT_MODE': 'two'}, None),
            ('empty-action-args', {'FIXTURE_ACTION_ARGUMENTS_MODE': 'empty'}, None),
            ('extra-action-args', {}, lambda value: value + ' --extra value'),
            ('unknown-action-flag', {}, lambda value: value.replace('--ready-file', '--unknown-file')),
            ('duplicate-action-flag', {}, lambda value: value.replace('--log-file', '--config')),
            ('wrong-node-launcher', {}, lambda value: value.replace('launch-node-b.py', 'launch-node-c.py')),
            ('wrong-config', {}, lambda value: value.replace('node-b.toml', 'wrong.toml')),
            ('wrong-ready', {}, lambda value: value.replace('ready.json', 'wrong-ready.json')),
            ('wrong-log', {}, lambda value: value.replace('service.log', 'wrong.log')),
            ('wrong-case-flag', {}, lambda value: value.replace('--config', '--CONFIG')),
        ]
        for name, env, transform in cases:
            with self.subTest(name=name):
                result = self._run_case(env_overrides=env, action_transform=transform)
                self.assertNotEqual(result['proc'].returncode, 0, name)
                self._assert_no_admission(result)
                self.assertFalse([argv for argv in result['shim_commands']
                                  if 'install_routing' in argv or 'models_refresh' in argv or 'register-autostart' in argv])

    def test_invalid_routing_refuses_before_admission(self):
        cases = [
            ('missing-config', None, False),
            ('wrong-python', {'command': r'C:\fixture\wrong-python.ps1'}, True),
            ('wrong-root', {'root': r'C:\fixture\wrong-root'}, True),
            ('wrong-control', {'control': r'C:\fixture\wrong-control.json'}, True),
            ('wrong-args', {'args': ['-m', 'wrong.module']}, True),
            ('disabled', {'enabled': False}, True),
            ('wrong-timeouts', {'startup_timeout': 19, 'tool_timeout': 3599}, True),
            ('malformed', {'raw': '[mcp_servers.fpga_mesh'}, True),
        ]
        for name, routing, create_config in cases:
            with self.subTest(name=name):
                result = self._run_case(routing=routing, create_config=create_config)
                self.assertNotEqual(result['proc'].returncode, 0, name)
                self._assert_no_admission(result)

    def test_duplicate_name_in_other_folder_refuses_before_stop(self):
        result = self._run_case(env_overrides={'FIXTURE_DUPLICATE_TASK': '1'})
        self.assertNotEqual(result['proc'].returncode, 0)
        self._assert_no_admission(result)
        self.assertEqual(self._snapshots(result), [])

    def test_xml_change_on_second_export_refuses_before_stop(self):
        result = self._run_case(env_overrides={'FIXTURE_MUTATE_XML_EXPORT_AT': '2'})
        self.assertNotEqual(result['proc'].returncode, 0)
        self._assert_no_admission(result)
        self.assertTrue(result['live_xml_path'].is_file())
        mutated = result['live_xml_path'].read_text(encoding='utf-8-sig')
        self.assertIn('fixture-xml-mutation', mutated)
        self.assertNotIn('fixture-xml-mutation', result['xml_text'])
        update_result = self._update_result(result)
        self.assertEqual(update_result['status'], 'failed')
        self.assertEqual(update_result['phase'], 'before-stop')
        self.assertEqual(result['launcher'].read_bytes(), result['launcher_bytes'])

    def test_launcher_change_at_stop_refuses_before_apply(self):
        result = self._run_case(env_overrides={'FIXTURE_MUTATE_LAUNCHER_ON': 'stop'})
        self.assertNotEqual(result['proc'].returncode, 0)
        self._assert_task_mutators_zero(result)
        self.assertEqual(result['shim_counts']['stop_idle'], 1)
        self.assertEqual(result['shim_counts']['apply'], 0)
        self.assertEqual(result['shim_counts']['health'], 0)
        self.assertEqual(result['task_calls']['Start-ScheduledTask'], 0)
        self.assertIn(b'fixture launcher mutation at stop', result['launcher'].read_bytes())
        update_result = self._update_result(result)
        self.assertEqual(update_result['status'], 'failed')
        self.assertEqual(update_result['phase'], 'before-source-write')

    def test_xml_changes_before_apply_before_start_and_after_start_are_preserved(self):
        for export_at, applies, starts in ((3, 0, 0), (4, 1, 0), (5, 1, 1)):
            with self.subTest(export_at=export_at):
                result = self._run_case(env_overrides={'FIXTURE_MUTATE_XML_EXPORT_AT': str(export_at)})
                self.assertNotEqual(result['proc'].returncode, 0)
                self._assert_task_mutators_zero(result)
                self.assertEqual(result['shim_counts']['stop_idle'], 1)
                self.assertEqual(result['shim_counts']['apply'], applies)
                self.assertEqual(result['task_calls']['Start-ScheduledTask'], starts)
                self.assertIn('fixture-xml-mutation', result['live_xml_path'].read_text(encoding='utf-8-sig'))
                snapshot = self._snapshots(result)[0]
                self.assertNotIn('fixture-xml-mutation', (snapshot / 'task-before.xml').read_text(encoding='utf-8-sig'))

    def test_launcher_changes_before_stop_and_after_start_are_preserved(self):
        for export_at, applies, starts in ((2, 0, 0), (5, 1, 1)):
            with self.subTest(export_at=export_at):
                result = self._run_case(env_overrides={'FIXTURE_MUTATE_LAUNCHER_EXPORT_AT': str(export_at)})
                self.assertNotEqual(result['proc'].returncode, 0)
                self._assert_task_mutators_zero(result)
                self.assertEqual(result['shim_counts']['stop_idle'], applies)
                self.assertEqual(result['shim_counts']['apply'], applies)
                self.assertEqual(result['task_calls']['Start-ScheduledTask'], starts)
                self.assertNotEqual(result['launcher'].read_bytes(), result['launcher_bytes'])
                self.assertEqual((self._snapshots(result)[0] / 'launcher-before.bin').read_bytes(), result['launcher_bytes'])

    def test_utf16_export_is_saved_as_readable_xml_without_changing_definition(self):
        result = self._run_case(env_overrides={'FIXTURE_XML_UTF16': '1'})
        self._assert_success(result)
        snapshot = self._snapshots(result)[0]
        saved = snapshot / 'task-before.xml'
        self.assertEqual(saved.read_text(encoding='utf-16'), result['xml_text'])
        self.assertTrue(ET.parse(saved).getroot().tag.endswith('Task'))
        metadata = json.loads((snapshot / 'snapshot.json').read_text(encoding='utf-8-sig'))
        exported = result['xml_path'].read_bytes()
        self.assertEqual(metadata['XmlSha256'], _sha256_bytes(exported))

    def test_routing_changes_at_stop_or_apply_prevent_next_mutation(self):
        for boundary, applies in (('stop', 0), ('apply', 1)):
            with self.subTest(boundary=boundary):
                result = self._run_case(env_overrides={'FIXTURE_MUTATE_ROUTING_ON': boundary})
                self.assertNotEqual(result['proc'].returncode, 0)
                self._assert_task_mutators_zero(result)
                self.assertEqual(result['shim_counts']['apply'], applies)
                self.assertEqual(result['task_calls']['Start-ScheduledTask'], 0)
                self.assertIn(b'invalid TOML on purpose', result['routing_config'].read_bytes())
                self._assert_roles_unchanged(result)

    def test_routing_validation_cannot_be_disabled_by_python_optimization(self):
        result = self._run_case(routing={'enabled': False}, env_overrides={'PYTHONOPTIMIZE': '1'})
        self.assertNotEqual(result['proc'].returncode, 0)
        self._assert_no_admission(result)
        self.assertEqual(self._snapshots(result), [])

    def test_launcher_change_at_apply_refuses_before_start(self):
        result = self._run_case(env_overrides={'FIXTURE_MUTATE_LAUNCHER_ON': 'apply'})
        self.assertNotEqual(result['proc'].returncode, 0)
        self._assert_task_mutators_zero(result)
        self.assertEqual(result['shim_counts']['stop_idle'], 1)
        self.assertEqual(result['shim_counts']['apply'], 1)
        self.assertEqual(result['shim_counts']['health'], 0)
        self.assertEqual(result['task_calls']['Start-ScheduledTask'], 0)
        self.assertIn(b'fixture launcher mutation at apply', result['launcher'].read_bytes())
        update_result = self._update_result(result)
        self.assertEqual(update_result['status'], 'failed')
        self.assertEqual(update_result['phase'], 'before-start')

    def test_busy_and_lock_refuse_without_stop_apply_or_start(self):
        cases = [('busy', 'FIXTURE_BUSY', 'busy'), ('locked', 'FIXTURE_LOCKED', 'locked')]
        for name, flag, expected in cases:
            with self.subTest(name=name):
                result = self._run_case(env_overrides={flag: '1'})
                self.assertNotEqual(result['proc'].returncode, 0)
                self._assert_task_mutators_zero(result)
                self.assertEqual(result['shim_counts']['stop_idle'], 1)
                self.assertEqual(result['shim_counts']['apply'], 0)
                self.assertEqual(result['shim_counts']['health'], 0)
                self.assertEqual(result['task_calls']['Start-ScheduledTask'], 0)
                stop_events = [event for event in result['events']
                               if event.get('action') == 'stop_idle']
                self.assertEqual(stop_events[-1]['data']['result'], expected)
                update_result = self._update_result(result)
                self.assertEqual(update_result['status'], 'failed')
                self.assertEqual(update_result['phase'], 'before-stop')

    def test_apply_failure_does_not_start(self):
        result = self._run_case(env_overrides={'FIXTURE_APPLY_FAIL': '1'})
        self.assertNotEqual(result['proc'].returncode, 0)
        self._assert_task_mutators_zero(result)
        self.assertEqual(result['shim_counts']['stop_idle'], 1)
        self.assertEqual(result['shim_counts']['apply'], 1)
        self.assertEqual(result['shim_counts']['health'], 0)
        self.assertEqual(result['task_calls']['Start-ScheduledTask'], 0)
        update_result = self._update_result(result)
        self.assertEqual(update_result['status'], 'failed')
        self.assertEqual(update_result['phase'], 'source-apply')

    def test_start_failure_is_single_attempt_without_apply_replay(self):
        result = self._run_case(env_overrides={'FIXTURE_START_FAIL': '1'})
        self.assertNotEqual(result['proc'].returncode, 0)
        self._assert_task_mutators_zero(result)
        self.assertEqual(result['shim_counts']['stop_idle'], 1)
        self.assertEqual(result['shim_counts']['apply'], 1)
        self.assertEqual(result['shim_counts']['health'], 0)
        self.assertEqual(result['task_calls']['Start-ScheduledTask'], 1)
        self._assert_roles_unchanged(result)
        update_result = self._update_result(result)
        self.assertEqual(update_result['status'], 'failed')
        self.assertEqual(update_result['phase'], 'start-attempt')

    def test_no_forbidden_reinstall_or_role_rewrite_on_success(self):
        result = self._run_case()
        self._assert_success(result)
        commands = result['shim_commands']
        self.assertFalse([argv for argv in commands if 'install_routing' in argv])
        self.assertFalse([argv for argv in commands if 'models_refresh' in argv])
        self.assertFalse([argv for argv in commands if 'register-autostart' in argv])
        self.assertFalse(result['forbidden_commands'])


if __name__ == '__main__':
    unittest.main()
