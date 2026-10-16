import hashlib
import json
import sys
from pathlib import Path


def digest(path):
    data = Path(path).read_bytes()
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


result = {}
for raw in sys.argv[1:]:
    result[raw] = digest(raw)
print(json.dumps(result, indent=1, sort_keys=True))
