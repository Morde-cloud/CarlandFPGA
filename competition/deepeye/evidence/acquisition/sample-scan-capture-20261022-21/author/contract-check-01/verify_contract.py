from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(r"D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014")
COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
PATH = "docs/competition/deepeye-2026/immutable_scope.json"
EXPECTED = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"

raw = subprocess.check_output(["git", "show", f"{COMMIT}:{PATH}"], cwd=REPO)
doc = json.loads(raw.decode("utf-8"))
requirements = doc["requirements"]
canonical = json.dumps(
    requirements,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
).encode("utf-8")
actual = hashlib.sha256(canonical).hexdigest()
assert actual == EXPECTED, (actual, EXPECTED)
ids = [item["id"] for item in requirements]
assert ids == [f"H{index:02d}" for index in range(1, 16)], ids
Path("requirements.canonical.json").write_bytes(canonical)
for item in requirements:
    print(f"{item['id']}: {item['title']}")
print(f"CONTRACT_PASS id=DEEPEYE-HUMAN-LOCK-20261014 revision=1 commit={COMMIT} requirements={len(requirements)} sha256={actual}")