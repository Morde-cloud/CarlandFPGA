import subprocess, json, hashlib, pathlib
root = pathlib.Path(r"D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014")
rev = "f5989cd5defce561f9ba98e6b18fc2682945f0a2:docs/competition/deepeye-2026/immutable_scope.json"
blob = subprocess.check_output(["git","cat-file","blob",rev], cwd=root)
cur = (root/"docs/competition/deepeye-2026/immutable_scope.json").read_bytes()
print("blob_bytes",len(blob),"cur_bytes",len(cur),"same",blob==cur)
for label,data in (("pinned",blob),("current",cur)):
    d=json.loads(data)
    r=d["requirements"]
    canon=json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
    canon_ascii=json.dumps(r,ensure_ascii=True,sort_keys=True,separators=(",",":")).encode("utf-8")
    whole=json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode("utf-8")
    print(label,"req",hashlib.sha256(canon).hexdigest(),"ascii",hashlib.sha256(canon_ascii).hexdigest(),"whole",hashlib.sha256(whole).hexdigest())
    print(label,"ids",[x["id"] for x in r],"titles",[x["title"] for x in r][:2])
if blob!=cur:
    import difflib
    a=blob.decode("utf-8").splitlines(); b=cur.decode("utf-8").splitlines()
    print("\n".join(list(difflib.unified_diff(a,b,fromfile="pinned",tofile="current"))[:80]))
