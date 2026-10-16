import hashlib
import json
import sys
from pathlib import Path
product = Path(sys.argv[1])
pinned = Path(sys.argv[2])
document = json.loads(product.read_bytes())
manual = json.loads(pinned.read_bytes())['vectors']
vectors = document['manual_vectors']['vectors']
assert len(vectors) == len(manual) == 8
same = all(all(entry[key] == manual[i][key] for key in manual[i])
           for i, entry in enumerate(vectors))
extra = sorted(set(vectors[0]) - set(manual[0]))
assert same, 'pinned field values differ'
assert all(sorted(set(entry) - set(manual[0])) == extra for entry in vectors)
recorded = document['manual_vectors']['source_sha256']
pinned_sha = hashlib.sha256(pinned.read_bytes()).hexdigest()
print(json.dumps({
    'pinned_vector_count': 8,
    'all_pinned_fields_equal': same,
    'extra_keys_per_entry': extra,
    'pinned_file_sha256': pinned_sha,
    'recorded_source_sha256': recorded,
    'recorded_matches_pinned_file': recorded == pinned_sha,
    'status': 'PASS'}, indent=1))
