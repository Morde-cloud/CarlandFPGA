"""Validate this planning supplement against the downloaded A baseline, not hardware."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[5]

def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8-sig'))

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def main():
    plan = read('a_execution_baseline.json')
    followup = read('b_tasks.json')
    audit = read('source_audit.json')
    history = read('history_preserved.json')
    assert sha((ROOT / 'a_execution_baseline.json').read_bytes()) == 'de1df0a14d00362e00b6691d26b6ac884730fc600f9aee19a40ac3cd442b73ee'
    expected = {key for key, value in plan['tasks'].items() if value['owner'] == 'B'}
    assert expected == set(followup['tasks']) == {'B01', 'B02', 'B03', 'B04', 'B05', 'B06'}
    assert len(plan['tasks']) == 20
    seen, visiting = set(), set()
    def visit(key):
        assert key in plan['tasks'], key
        assert key not in visiting, key
        if key in seen:
            return
        visiting.add(key)
        for dependency in plan['tasks'][key]['dependencies']:
            visit(dependency)
        visiting.remove(key)
        seen.add(key)
    for key in plan['tasks']:
        visit(key)
    allowed_prefixes = ('fpga/', 'golden/codec/', 'tests/rtl/', 'evidence/rtl/')
    allowed_tools = {'tools/verify_codec.py', 'tools/run_rtl.py', 'tools/verify_link.py', 'tools/check_build.py'}
    for key, value in followup['tasks'].items():
        baseline = plan['tasks'][key]
        for field in ('owner', 'stage', 'dependencies', 'status'):
            assert value[field] == baseline[field], (key, field)
        assert value['status'] == 'not_run'
        assert value['board_operator'] == 'A'
        assert value['execution_performed_this_followup'] is False
        assert value['commands_to_implement'] and value['acceptance']
        for path in value['owned_paths']:
            assert path in allowed_tools or path.startswith(allowed_prefixes), path
    for entry in history['files']:
        raw = (REPO / entry['path']).read_bytes()
        assert len(raw) == entry['bytes'] and sha(raw) == entry['sha256'], entry['path']
    source_by_path = {(s['label'], s['path']): s for s in audit['sources']}
    a = source_by_path[('a17', 'docs/competition/deepeye-2026/taskbook_v3.md')]
    assert a['commit'] == followup['baseline_commit']
    assert a['sha256'] == followup['baseline_taskbook_sha256']
    matches = [s for s in audit['sources'] if s['manifest_check'] == 'matched']
    assert all(s['sha256'] == s['published_manifest_sha256'] for s in matches)
    for key in expected:
        assert key in (ROOT / 'B_TASKBOOK.md').read_text(encoding='utf-8')
    result = {
        'scope': 'Planning consistency and historical-byte preservation only. Source download checks are recorded evidence; this command is offline.',
        'status': 'passed',
        'baseline_tasks': len(seen), 'b_tasks': len(expected),
        'dependencies_owner_stage_match': True, 'dag_acyclic': True,
        'prior_b_files_unchanged': len(history['files']),
        'recorded_source_downloads': len(audit['sources']),
        'recorded_manifest_matches': len(matches),
        'product_stages': {k: 'not_run' for k in ['rtl_simulation','synthesis','implementation','board','model','system']},
        'probabilistic_verifier_calls': 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
