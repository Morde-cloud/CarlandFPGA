import sys
from difflib import unified_diff
from pathlib import Path

scratch, wt, parent = (Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
pairs = [
    ('trace_candidate.correction.diff',
     scratch / 'trace_candidate.before.py',
     wt / 'competition/deepeye/golden/codec/trace_candidate.py'),
    ('TRACE_CANDIDATE.correction.diff',
     parent / 'rejected-original' / 'TRACE_CANDIDATE.md',
     wt / 'competition/deepeye/golden/codec/TRACE_CANDIDATE.md'),
]
for name, before, after in pairs:
    old = before.read_text(encoding='utf-8').splitlines(keepends=True)
    new = after.read_text(encoding='utf-8').splitlines(keepends=True)
    diff = list(unified_diff(old, new, fromfile=str(before.name),
                             tofile=str(after.name)))
    (scratch / name).write_text(''.join(diff), encoding='utf-8', newline='\n')
    added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
    removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
    print(name, 'added', added, 'removed', removed)
