"""Build a credential-free teammate ZIP from the committed Git file list."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


_KEY_PATTERN = re.compile(
    rb"(?<![A-Za-z0-9_])sk-[A-Za-z0-9_-]{24,}|-----BEGIN (?:OPENSSH |RSA |EC |DSA |ENCRYPTED )?PRIVATE "
    rb"KEY-----|-----BEGIN PGP PRIVATE " rb"KEY BLOCK-----"
)
_PRIVATE_FILENAMES = {"auth.json", "deepcodex.txt", "id_ed25519", "id_rsa", "id_ecdsa", "id_dsa"}
_PRIVATE_SUFFIXES = ("-secret.txt", ".p12", ".pfx", ".pem", ".key", ".lic")
_CLIENT_DEST = "skills/pynq-z2-single-node/"
_CLIENT_SOURCES = {
    "INSTALL.md": "packaging/pynq-client/INSTALL.md",
    "Install.ps1": "skills/pynq-z2-single-node/Install.ps1",
    "SKILL.md": "packaging/pynq-client/SKILL.md",
    "references/handoff.md": "packaging/pynq-client/references/handoff.md",
    "references/pynq-z2.md": "skills/pynq-z2-single-node/references/pynq-z2.md",
    "references/telemetry-option.md": "skills/pynq-z2-single-node/references/telemetry-option.md",
    "scripts/handoff.py": "skills/pynq-z2-single-node/scripts/handoff.py",
    "scripts/preflight.py": "skills/pynq-z2-single-node/scripts/preflight.py",
}


def select_package_paths(paths: list[str], profile: str) -> list[str]:
    """Keep the machine mesh and the standalone board skill in separate ZIPs."""
    if profile == "pynq-skill":
        return [path for path in paths if path.startswith("skills/pynq-z2-single-node/")]
    if profile == "mesh":
        return [path for path in paths if not (
            path.startswith("skills/pynq-z2-single-node/")
            or path.startswith("docs/deployment/SINGLE_NODE_")
            or path.startswith("docs/deployment/HOST_TOOLCHAIN_")
            or path.startswith("docs/deployment/evidence/pynq-z2-")
            or path.startswith("packaging/pynq-client/")
            or path == "tests/test_pynq_client_distribution.py"
            or path.startswith("tests/test_pynq_z2_")
        )]
    raise ValueError(f"unknown package profile: {profile}")


def build_archive(
    root: Path, paths: list[str], output: Path, *, revision: str = "uncommitted",
    profile: str = "mesh", previous_archives: list[Path] | None = None,
) -> Path:
    root = Path(root).resolve()
    output = Path(output).resolve()
    files = []
    payloads: dict[str, bytes] = {}
    for raw in sorted(set(paths)):
        relative = Path(raw)
        resolved = (root / relative).resolve()
        if (relative.is_absolute() or ".." in relative.parts
                or not resolved.is_relative_to(root)):
            raise ValueError(f"unsafe package path: {raw}")
        normalized = relative.as_posix()
        lowered = [part.casefold() for part in relative.parts]
        if ({".git", ".local", "__pycache__"} & set(lowered)
                or relative.name.casefold() in _PRIVATE_FILENAMES
                or relative.name.casefold().endswith(_PRIVATE_SUFFIXES)):
            raise ValueError(f"private path cannot enter package: {raw}")
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        content = resolved.read_bytes()
        if _KEY_PATTERN.search(content):
            raise ValueError(f"key-like material found in: {raw}")
        payloads[normalized] = content
        files.append({
            "path": normalized, "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    manifest = {
        "project": "CarlandFPGA",
        "profile": profile,
        "revision": revision,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": files,
    }
    if previous_archives:
        if profile != "mesh":
            raise ValueError("in-place updates are only supported for mesh packages")
        # Read actual distributed bytes, including their checkout line endings.
        # No old source or credential is copied into the new ZIP.
        from .update import canonical_hash, read_package
        previous = []
        bases = []
        for path in previous_archives:
            old_manifest, old_payloads = read_package(path, require_update=False)
            selected = select_package_paths(list(old_payloads), "mesh")
            previous.append({name: canonical_hash(old_payloads[name]) for name in selected})
            bases.append({"revision": old_manifest["revision"],
                          "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()})
        before = {
            name: sorted({base[name] for base in previous if name in base})
                  + ([None] if any(name not in base for base in previous) else [])
            for name in payloads
        }
        removed = {}
        for base in previous:
            for name, digest in base.items():
                if name not in payloads:
                    removed.setdefault(name, set()).add(digest)
        manifest["update"] = {
            "schema": 1, "bases": bases, "before": before,
            "removed": {name: sorted(values) for name, values in removed.items()},
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in payloads.items():
            archive.writestr(name, content)
        archive.writestr(
            "MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")
        for entry in files:
            if hashlib.sha256(archive.read(entry["path"])).hexdigest() != entry["sha256"]:
                raise RuntimeError(f"ZIP hash verification failed: {entry['path']}")
    return output


def build_client_archive(
    root: Path, node: str, output: Path, *, revision: str = "uncommitted",
) -> Path:
    """Derive a board-free B/C skill from repository files without editing A's skill."""
    if node not in {"B", "C"}:
        raise ValueError("client node must be B or C")
    root = Path(root).resolve()
    output = Path(output).resolve()
    with tempfile.TemporaryDirectory(prefix="pynq-client-") as temporary:
        staging = Path(temporary)
        for destination, source in _CLIENT_SOURCES.items():
            payload = (root / source).read_bytes()
            if source.startswith("packaging/pynq-client/"):
                if destination == "SKILL.md" and b"@NODE@" not in payload:
                    raise ValueError("client skill template has no node marker")
                payload = (payload.replace(b"@NODE@", node.encode("ascii"))
                          .replace(b"@NODE_LOWER@", node.lower().encode("ascii")))
            target = staging / _CLIENT_DEST / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        role = {"node": node, "board_access": False,
                "handoff": "github_pull_request"}
        role_path = staging / _CLIENT_DEST / "client-role.json"
        role_path.write_text(json.dumps(role, indent=2) + "\n", encoding="utf-8")
        paths = [(_CLIENT_DEST + relative) for relative in _CLIENT_SOURCES]
        paths.append(_CLIENT_DEST + "client-role.json")
        return build_archive(
            staging, paths, output, revision=revision,
            profile=f"pynq-client-{node.lower()}",
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=("mesh", "pynq-skill", "pynq-client-b", "pynq-client-c"), default="mesh")
    parser.add_argument("--previous-archive", type=Path, action="append", default=[],
                        help="Known previously distributed ZIP; repeat for compatibility")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root,
        capture_output=True, text=True, check=True,
    ).stdout
    if dirty.strip():
        raise SystemExit("Commit all source changes before building the package")
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root,
        capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="strict")
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root,
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if args.profile.startswith("pynq-client-"):
        path = build_client_archive(root, args.profile[-1].upper(),
                                    args.output, revision=revision)
        with zipfile.ZipFile(path) as archive:
            file_count = len(archive.namelist()) - 1
    else:
        paths = select_package_paths(
            [name for name in listed.split("\0") if name], args.profile,
        )
        path = build_archive(root, paths, args.output, revision=revision,
                             profile=args.profile, previous_archives=args.previous_archive)
        file_count = len(paths)
    print(json.dumps({
        "archive": str(path), "profile": args.profile,
        "revision": revision, "files": file_count,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
