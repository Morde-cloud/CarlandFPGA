import hashlib
import json
import pathlib
from datetime import datetime, timezone

root = pathlib.Path(r"D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014")
author = root / "competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20/author"
manifest_path = author / "EVIDENCE_MANIFEST.json"
sidecar_path = author / "EVIDENCE_MANIFEST.sha256"

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def entry(path, base):
    return {"path": path.relative_to(base).as_posix(), "sha256": sha(path), "bytes": path.stat().st_size}

author_files = {}
for path in sorted(author.rglob("*")):
    if not path.is_file():
        continue
    if path == manifest_path or path == sidecar_path:
        continue
    author_files[path.relative_to(author).as_posix()] = {
        "sha256": sha(path),
        "bytes": path.stat().st_size,
    }

delivered = {}
for rel in [
    "competition/deepeye/fpga/stream/deepeye_encoded_frame_queue.sv",
    "competition/deepeye/fpga/stream/encoded_frame_queue_candidate.md",
    "competition/deepeye/tests/rtl/stream/tb_encoded_frame_queue.sv",
    "competition/deepeye/tools/stream/run_encoded_frame_queue.py",
]:
    path = root / rel
    delivered[rel] = {"sha256": sha(path), "bytes": path.stat().st_size}

pinned = {}
for rel in [
    "competition/deepeye/fpga/codec/deepeye_block_encoder.sv",
    "competition/deepeye/fpga/stream/deepeye_block_stream.sv",
    "handoffs/b/B-DEEPEYE-CODEC-20261016-01/input.json",
]:
    path = root / rel
    pinned[rel] = {"sha256": sha(path), "bytes": path.stat().st_size}

scope_dir = pathlib.Path(r"D:\pynq\CarlandFPGA\.local\deployment\node-b\evidence\encoded-frame-queue-20261022-20\inputs")
scope_inputs = {}
for name in ["IMPLEMENTATION_SCOPE.md", "SCOPE_FROZEN.json", "ASSIGNMENT.json", "COMPLETION_MATRIX.md", "CONTINUE_DECISION.json", "INPUTS_CONSUMED.json", "immutable_scope.json"]:
    path = scope_dir / name
    scope_inputs[name] = {"sha256": sha(path), "bytes": path.stat().st_size}

manifest = {
    "schema": 1,
    "at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "operation_id": "B-DEEPEYE-ENCODED-FRAME-QUEUE-20261022-20",
    "task_id": "DEEPEYE-IMPLEMENTATION-20261014",
    "task_version": 1,
    "work_id": "B-ENCODED-FRAME-QUEUE-RTL-20261022-20-v1",
    "author_evidence_root": str(author),
    "excluded_from_manifest": ["EVIDENCE_MANIFEST.json", "EVIDENCE_MANIFEST.sha256"],
    "author_file_count": len(author_files),
    "author_files": author_files,
    "delivered_sources": delivered,
    "pinned_readonly": pinned,
    "scope_inputs": scope_inputs,
    "final_run": {
        "run_result": author.joinpath("run-final-01/RUN_RESULT.json").relative_to(author).as_posix(),
        "run_result_sha256": sha(author / "run-final-01/RUN_RESULT.json"),
        "artifacts": author.joinpath("run-final-01/ARTIFACTS.json").relative_to(author).as_posix(),
        "artifacts_sha256": sha(author / "run-final-01/ARTIFACTS.json"),
        "artifact_count": len(json.loads((author / "run-final-01/RUN_RESULT.json").read_text(encoding="utf-8"))["artifact_hashes"]),
    },
    "notes": [
        "This manifest covers every file under the author evidence directory except itself and its sidecar.",
        "The sidecar EVIDENCE_MANIFEST.sha256 seals this JSON file.",
        "The final run ARTIFACTS.json contains the per-artifact hash map for run-final-01.",
    ],
}

manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
sidecar_path.write_text(sha(manifest_path) + "  EVIDENCE_MANIFEST.json\n", encoding="utf-8")
print(manifest_path)
print(manifest_path.stat().st_size)
print(sidecar_path.read_text(encoding="utf-8").strip())