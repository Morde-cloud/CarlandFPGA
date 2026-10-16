import hashlib
import sys
from pathlib import Path
gen1, gen2 = Path(sys.argv[1]), Path(sys.argv[2])
names = ('trace_candidate_vectors.json', 'trace_candidate_layout.json')
for name in names:
    a, b = (gen1 / name).read_bytes(), (gen2 / name).read_bytes()
    assert a == b, name
    print(name, 'identical', len(a), hashlib.sha256(a).hexdigest())
print('deterministic_two_fresh_dirs: true')
