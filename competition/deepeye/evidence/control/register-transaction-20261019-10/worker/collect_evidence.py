'''Collect source pins, artifact hashes and the captured test summary.'''

import argparse
import datetime
import hashlib
import json
import pathlib
import re
import sys

EXPECTED_REQUIREMENTS = (
    'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
)
EXPECTED_IDS = tuple('H%02d' % index for index in range(1, 16))


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _file_record(path):
    data = path.read_bytes()
    lines = data.count(b'\n')
    if data and not data.endswith(b'\n'):
        lines += 1
    return {
        'path': str(path),
        'bytes': len(data),
        'sha256': _sha256(data),
        'lines': lines,
    }


def _canonical_requirements(scope):
    payload = json.dumps(
        scope['requirements'],
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worktree', required=True)
    parser.add_argument('--worker', required=True)
    args = parser.parse_args()
    worktree = pathlib.Path(args.worktree).resolve()
    worker = pathlib.Path(args.worker).resolve()
    started = json.loads(
        (worker / 'STARTED.json').read_text(encoding='utf-8')
    )
    pin_results = {}
    for name, record in sorted(started['source_pins'].items()):
        path = pathlib.Path(name)
        if not path.is_absolute():
            path = worktree / path
        actual = _file_record(path)['sha256']
        pin_results[name] = {
            'path': str(path),
            'expected_sha256': record['sha256'],
            'actual_sha256': actual,
            'match': actual == record['sha256'],
            'role': record['role'],
        }
    scope_path = (
        worktree / 'docs/competition/deepeye-2026/immutable_scope.json'
    )
    scope = json.loads(scope_path.read_text(encoding='utf-8'))
    requirements_actual = _canonical_requirements(scope)
    ids = tuple(item['id'] for item in scope['requirements'])
    requirements = {
        'expected_sha256': EXPECTED_REQUIREMENTS,
        'actual_sha256': requirements_actual,
        'match': requirements_actual == EXPECTED_REQUIREMENTS,
        'started_pin': started['requirements_sha256'],
        'started_pin_match': (
            started['requirements_sha256'] == EXPECTED_REQUIREMENTS
        ),
        'ids': list(ids),
        'ids_match_h01_h15': ids == EXPECTED_IDS,
        'contract_id': scope.get('contract_id'),
        'revision': scope.get('revision'),
        'declared_requirements_sha256': scope.get(
            'requirements_sha256'
        ),
        'declared_match': (
            scope.get('requirements_sha256') == EXPECTED_REQUIREMENTS
        ),
    }
    commit_pins = {
        'lock_commit': started['lock_commit'],
        'design_commit': started['design_commit'],
        'base_commit': started['base_commit'],
        'verification': (
            'recorded pins; no Git command was executed by this worker'
        ),
    }
    all_files_match = all(
        item['match'] for item in pin_results.values()
    )
    all_match = (
        all_files_match and
        requirements['match'] and
        requirements['started_pin_match'] and
        requirements['ids_match_h01_h15'] and
        requirements['declared_match']
    )
    verification = {
        'verified_at_utc': datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        'requirements': requirements,
        'files': pin_results,
        'commit_pins': commit_pins,
        'all_match': all_match,
    }
    (worker / 'pin_verification.json').write_text(
        json.dumps(verification, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    artifact_paths = {
        'source': (
            worktree /
            'competition/deepeye/golden/control/'
            'register_transaction_reference.py'
        ),
        'tests': (
            worktree /
            'competition/deepeye/tests/control/'
            'test_register_transaction.py'
        ),
        'document': (
            worktree /
            'competition/deepeye/golden/control/'
            'REGISTER_TRANSACTION_REFERENCE.md'
        ),
        'started': worker / 'STARTED.json',
        'runner': worker / 'run_offline_tests.py',
        'collector': worker / 'collect_evidence.py',
    }
    artifacts = {
        name: _file_record(path)
        for name, path in artifact_paths.items()
    }
    log_dir = worker / 'logs'
    log_paths = {
        'stdout.bin': log_dir / 'stdout.bin',
        'stderr.bin': log_dir / 'stderr.bin',
        'run_metadata.json': log_dir / 'run_metadata.json',
        'returncode.txt': log_dir / 'returncode.txt',
    }
    logs = {
        name: _file_record(path)
        for name, path in log_paths.items()
    }
    metadata = json.loads(
        log_paths['run_metadata.json'].read_text(encoding='utf-8')
    )
    combined = (
        log_paths['stdout.bin'].read_bytes() +
        log_paths['stderr.bin'].read_bytes()
    )
    ran_match = re.search(rb'Ran (\d+) tests? in', combined)
    ran = int(ran_match.group(1)) if ran_match else None
    ok = re.search(rb'(?m)^OK\r?$', combined) is not None
    failed = re.search(rb'(?m)^FAILED \(', combined) is not None
    test_source = artifact_paths['tests'].read_text(encoding='utf-8')
    method_count = len(
        re.findall(r'^    def test_', test_source, re.MULTILINE)
    )
    summary = {
        'ran': ran,
        'status': 'OK' if ok and not failed else 'FAILED',
        'returncode': metadata['returncode'],
        'method_count': method_count,
        'count_matches_methods': ran == method_count,
        'stdout_bytes': metadata['stdout_bytes'],
        'stderr_bytes': metadata['stderr_bytes'],
        'duration_seconds': metadata['duration_seconds'],
    }
    artifact_record = {
        'artifacts': artifacts,
        'test_logs': logs,
        'test_summary': summary,
        'run_metadata': metadata,
    }
    (worker / 'artifact_hashes.json').write_text(
        json.dumps(artifact_record, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    print(json.dumps({
        'all_pins_match': all_match,
        'test_summary': summary,
    }, indent=2, sort_keys=True))
    return 0 if all_match and summary['status'] == 'OK' else 1


if __name__ == '__main__':
    raise SystemExit(main())
