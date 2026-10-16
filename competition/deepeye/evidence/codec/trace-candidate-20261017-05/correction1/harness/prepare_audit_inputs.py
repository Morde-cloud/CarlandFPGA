import json
import sys
from pathlib import Path
product = Path(sys.argv[1])
pinned = Path(sys.argv[2])
out = Path(sys.argv[3])
document = json.loads(product.read_bytes())
manual = json.loads(pinned.read_bytes())
copy = {'vectors': document['manual_vectors']['vectors']}
(out / 'audit-manual-product-copy.json').write_text(
    json.dumps(copy, indent=1) + '\n', encoding='utf-8')
normalized = json.loads(product.read_bytes())
normalized['manual_vectors']['vectors'] = manual['vectors']
(out / 'audit-vectors-normalized.json').write_text(
    json.dumps(normalized, indent=1) + '\n', encoding='utf-8')
print('prepared audit inputs in', out)
