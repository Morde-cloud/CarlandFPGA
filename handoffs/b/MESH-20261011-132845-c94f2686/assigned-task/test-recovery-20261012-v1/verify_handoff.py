"""Read-only check of assignment identity, immutable evidence and source Git blobs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = HERE.parents[4]


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(data):
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def request_hash(path, key):
    obj = json.loads(path.read_text(encoding="utf-8"))
    expected = obj.pop(key)
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    require(hashlib.sha256(raw).hexdigest() == expected, "request hash mismatch")
    return expected


def main():
    wrapper = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    require(wrapper["original_request_hash"] == request_hash(
        BASE / "recovery-20261012-v1/assignment.json", "request_hash"), "original identity")
    require(wrapper["predecessor_request_hash"] == request_hash(
        BASE / "recovery-20261012-v1/recovery-request.json", "recovery_request_hash"), "predecessor identity")
    require(wrapper["recovery_request_hash"] == request_hash(
        HERE / "request.json", "recovery_request_hash"), "current identity")
    for name, record in wrapper["manifest_files"].items():
        path = (ROOT / name).resolve()
        require(path.is_relative_to(HERE), "manifest file outside recovery")
        require(digest(path.read_bytes()) == record, "manifest bytes mismatch: " + name)
    spec = importlib.util.spec_from_file_location(
        "client_handoff", ROOT / "skills/pynq-z2-single-node/scripts/handoff.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    evidence = helper.verify_manifest(ROOT, HERE / "evidence-manifest.json")
    require(evidence["request_hash"] == wrapper["evidence_request_hash"], "evidence request mismatch")
    require(evidence["request"]["code_commit"] == wrapper["source_commit"], "source SHA mismatch")
    for key in ("operation_id", "task_id", "task_version"):
        require(evidence["request"][key] == wrapper[key], key + " mismatch")
    require(evidence["stages"]["hardware"]["status"] == "not_run", "hardware status mismatch")
    for name, record in evidence["files"].items():
        require((ROOT / name).resolve().is_relative_to(BASE), "artifact outside ownership")
        raw = subprocess.run(["git", "show", wrapper["source_commit"] + ":" + name],
                             cwd=ROOT, check=True, capture_output=True).stdout
        require(digest(raw) == record, "source Git blob mismatch: " + name)
    print(json.dumps({"valid": True, "source_commit": wrapper["source_commit"],
                      "files_checked": len(evidence["files"]),
                      "original_request_hash": wrapper["original_request_hash"],
                      "recovery_request_hash": wrapper["recovery_request_hash"]}, sort_keys=True))


if __name__ == "__main__":
    main()
