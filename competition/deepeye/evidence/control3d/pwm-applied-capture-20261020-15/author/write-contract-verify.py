import subprocess, json, hashlib, pathlib, datetime
root = pathlib.Path(".").resolve()
rev = "f5989cd5defce561f9ba98e6b18fc2682945f0a2:docs/competition/deepeye-2026/immutable_scope.json"
blob = subprocess.check_output(["git", "cat-file", "blob", rev], cwd=root)
cur = (root / "docs/competition/deepeye-2026/immutable_scope.json").read_bytes()
d = json.loads(blob)
r = d["requirements"]
canon = json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
computed = hashlib.sha256(canon).hexdigest()
expected = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
out = {
    "contract_id": "DEEPEYE-HUMAN-LOCK-20261014",
    "contract_revision": 1,
    "pin": "f5989cd5defce561f9ba98e6b18fc2682945f0a2",
    "expected_requirements_sha256": expected,
    "computed_requirements_sha256": computed,
    "match": computed == expected,
    "pinned_blob_equals_worktree": blob == cur,
    "pinned_blob_sha256": hashlib.sha256(blob).hexdigest(),
    "worktree_file_sha256": hashlib.sha256(cur).hexdigest(),
    "requirement_ids": [x["id"] for x in r],
    "method": "json.dumps(requirements, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode('utf-8')",
    "checked_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}
p = root / "competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author/CONTRACT_HASH_VERIFY.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
