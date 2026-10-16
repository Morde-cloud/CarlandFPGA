import hashlib
import shutil
import sys
from pathlib import Path
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
for name in ('trace_candidate_vectors.json', 'trace_candidate_layout.json'):
    shutil.copyfile(src / name, dst / name)
    print(name, hashlib.sha256((dst / name).read_bytes()).hexdigest(),
          (dst / name).stat().st_size)
