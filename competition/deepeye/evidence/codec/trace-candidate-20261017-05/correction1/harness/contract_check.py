import hashlib
import json
from pathlib import Path

ROOT = Path(r'D:\pynq\CarlandFPGA')
WT = ROOT / '.local' / 'worktrees' / 'deepeye-implementation-20261014'
EXPECTED = 'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'

contract = json.loads((ROOT / '.local' / 'deployment' / 'node-b' / 'evidence' /
                       'product-restart-20261017' / 'contract-pinned.json')
                      .read_text(encoding='utf-8'))
canonical = json.dumps(contract['requirements'], ensure_ascii=False,
                       sort_keys=True, separators=(',', ':')).encode('utf-8')
computed = hashlib.sha256(canonical).hexdigest()
ids = [item['id'] for item in contract['requirements']]
expected_ids = ['H%02d' % number for number in range(1, 16)]
complete = all(item.get('title') and item.get('must')
               for item in contract['requirements'])

pins = json.loads((ROOT / '.local' / 'deployment' / 'node-b' / 'evidence' /
                   'trace-candidate-20261017' / 'input-pins.json')
                  .read_text(encoding='utf-8'))
pin_report = {}
for relative, expected in pins.items():
    resolved = None
    for base in (ROOT, WT):
        candidate = base / relative
        if candidate.is_file():
            resolved = candidate
            break
    if resolved is None:
        pin_report[relative] = {'expected': expected, 'actual': None,
                                'base': None, 'match': False}
        continue
    actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
    pin_report[relative] = {
        'expected': expected,
        'actual': actual,
        'base': str(resolved.parent.relative_to(resolved.parents[0])) or '.',
        'resolved_under': ('ROOT' if resolved.is_relative_to(ROOT)
                           and not resolved.is_relative_to(WT) else 'WORKTREE'),
        'match': actual == expected,
    }

report = {
    'contract': contract['contract_id'],
    'revision': contract['revision'],
    'requirements_count': len(ids),
    'ids': ids,
    'ids_complete_h01_h15': ids == expected_ids,
    'all_entries_have_title_and_must': complete,
    'expected_sha256': EXPECTED,
    'computed_sha256': computed,
    'canonical_sha256_match': computed == EXPECTED,
    'pins': pin_report,
    'all_pins_match': all(item['match'] for item in pin_report.values()),
}
print(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False))
