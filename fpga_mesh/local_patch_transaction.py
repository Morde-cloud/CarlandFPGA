"""Bounded, offline transaction core for replacing existing project files.

This module is deliberately standalone. It does not import or call the live
updater, service, controller, SQL ledgers, admission fence, launcher or stop
logic, and it has no command-line entry point. It is not a deployment API.

The public surface is ``dry_run``, ``apply`` and ``inspect``. Apply is
Windows-only because durable exclusivity is provided by a named OS mutex.
The caller supplies an out-of-band SHA256 of the exact raw plan bytes.

Durability boundary: file writes are flushed and fsynced, and journal records
are fsynced one record at a time. Windows does not expose portable directory
fsync or arbitrary power-loss atomicity, and this module does not preserve
ACLs or metadata. It replaces existing regular files only.
"""
from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import ntpath
import os
import posixpath
import re
import stat
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = 1
MAX_FILES = 64
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_PLAN_BYTES = 1024 * 1024
MAX_JOURNAL_BYTES = 16 * 1024 * 1024
MAX_OPERATION_ID_CHARS = 128

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_OPERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RESERVED_NAMES = {
    "con", "prn", "aux", "nul", "conin$", "conout$",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}
_DENIED_TARGET_TOKENS = (
    "auth", "credential", "secret", "config", "state", "launch",
    "owner", "deploy", "agents", "database",
)
_TARGET_MODULE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.py$")
_TARGET_TEST_NAME = re.compile(r"^test_[A-Za-z0-9_]+\.py$")
_REPARSE_POINT = 0x0400
_GENESIS = "0" * 64


class PatchTransactionError(RuntimeError):
    """Base class for transaction failures outside ordinary runtime reports."""


class ValidationError(PatchTransactionError, ValueError):
    """The plan, a path, an input image or the journal request is invalid."""


class PlanHashMismatch(ValidationError):
    """The out-of-band reviewed plan digest does not bind the raw plan bytes."""


class JournalExistsError(ValidationError):
    """The operation journal already exists and is never reused."""


class BusyError(PatchTransactionError):
    """Another cooperating apply holds the target-specific named mutex."""


class MutexAbandonedError(BusyError):
    """The previous mutex owner terminated without releasing the OS object."""


class ExclusivityError(PatchTransactionError):
    """The OS exclusivity primitive could not be created or used safely."""


class UnsupportedPlatformError(PatchTransactionError):
    """Applying is unavailable because the required OS mutex is unavailable."""


class ConcurrentChangeError(RuntimeError):
    """A target, parent or identity prerequisite changed during the operation."""


@dataclass(frozen=True)
class _PlanFile:
    path: str
    source: str
    pre_size: int
    pre_sha256: str
    post_size: int
    post_sha256: str


@dataclass(frozen=True)
class _Plan:
    raw: bytes
    sha256: str
    operation_id: str
    target_root_text: str
    source_root_text: str
    journal_root_text: str
    files: tuple[_PlanFile, ...]


@dataclass(frozen=True)
class _RootInfo:
    text: str
    path: Path
    device: int
    file_id: int

    @property
    def identity(self) -> tuple[int, int]:
        return self.device, self.file_id


@dataclass(frozen=True)
class _ObservedFile:
    path: Path
    data: bytes
    sha256: str
    size: int
    device: int
    file_id: int
    mtime_ns: int
    nlink: int

    @property
    def identity(self) -> tuple[int, int]:
        return self.device, self.file_id

    def summary(self) -> dict[str, int | str]:
        return {"device": self.device, "file_id": self.file_id,
                "size": self.size, "sha256": self.sha256}


@dataclass
class _FilePreflight:
    plan: _PlanFile
    target: Path
    source: Path
    target_parent: Path
    target_parent_identity: tuple[int, int]
    target_observation: _ObservedFile
    immutable_payload: bytes
    source_observation: _ObservedFile
    backup_path: Path | None = None
    backup_observation: _ObservedFile | None = None


@dataclass(frozen=True)
class _Preflight:
    plan: _Plan
    target_root: _RootInfo
    source_root: _RootInfo
    journal_root: _RootInfo
    journal_path: Path
    target_directories: dict[Path, tuple[int, int]]
    files: tuple[_FilePreflight, ...]
    journal_exists: bool = False


@dataclass
class _KnownWrite:
    index: int
    plan_file: _PlanFile
    target: Path
    temporary: Path
    temporary_observation: _ObservedFile
    observation: _ObservedFile | None = None


@dataclass
class _Preparation:
    journal: _Journal | None = None
    operation_identity: tuple[int, int] | None = None
    backups_identity: tuple[int, int] | None = None
    prepared: bool = False


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _as_text_path(value: Any, label: str) -> str:
    try:
        text = os.fspath(value)
    except TypeError as exc:
        raise ValidationError(f"{label} must be a filesystem path") from exc
    if not isinstance(text, str):
        raise ValidationError(f"{label} must be a text filesystem path")
    if not text:
        raise ValidationError(f"{label} must not be empty")
    return text


def _reject_control_and_surrogates(text: str, label: str) -> None:
    if any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise ValidationError(f"{label} contains a control character")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in text):
        raise ValidationError(f"{label} contains an unpaired surrogate")


def _bad_component(part: str) -> bool:
    if not part or part in (".", ".."):
        return True
    if part.endswith((" ", ".")) or "~" in part:
        return True
    if part.split(".")[0].casefold() in _RESERVED_NAMES:
        return True
    return False


def _canonical_root_text(value: Any, label: str) -> str:
    text = _as_text_path(value, label)
    _reject_control_and_surrogates(text, label)
    if any(char in '*?<>|"' for char in text):
        raise ValidationError(f"{label} contains a wildcard or reserved character")
    if unicodedata.normalize("NFC", text) != text:
        raise ValidationError(f"{label} is not canonical Unicode")
    if os.name == "nt":
        if text.startswith(("\\\\", "//")):
            raise ValidationError(f"{label} cannot be a UNC/device path")
        normalized = text.replace("/", "\\")
        if len(normalized) < 3 or normalized[1:2] != ":" or not normalized[0].isalpha():
            raise ValidationError(f"{label} must be an absolute local drive path")
        if ":" in normalized[2:]:
            raise ValidationError(f"{label} cannot contain an alternate data stream")
        if ntpath.normpath(normalized) != normalized:
            raise ValidationError(f"{label} is not a canonical absolute path")
        remainder = normalized[3:]
        if remainder and any(_bad_component(part) for part in remainder.split("\\")):
            raise ValidationError(f"{label} contains an unsafe path component")
        return normalized
    if not text.startswith("/") or text.startswith("//"):
        raise ValidationError(f"{label} must be an absolute local path")
    if posixpath.normpath(text) != text:
        raise ValidationError(f"{label} is not a canonical absolute path")
    if any(_bad_component(part) for part in text.split("/") if part):
        raise ValidationError(f"{label} contains an unsafe path component")
    return text


def _safe_relative(value: Any, *, target: bool) -> str:
    if not isinstance(value, str):
        raise ValidationError("plan paths must be strings")
    _reject_control_and_surrogates(value, "plan path")
    if not value or len(value) > 240:
        raise ValidationError("plan path has an invalid length")
    if unicodedata.normalize("NFC", value) != value:
        raise ValidationError("plan path is not canonical Unicode")
    if "\\" in value or ":" in value or value.startswith("/") or value.endswith("/"):
        raise ValidationError(f"unsafe plan path: {value!r}")
    if any(char in '*?<>|"' for char in value):
        raise ValidationError(f"plan path contains a wildcard or reserved character: {value!r}")
    parts = value.split("/")
    if any(_bad_component(part) for part in parts):
        raise ValidationError(f"unsafe plan path component: {value!r}")
    if any(part.startswith(".") for part in parts):
        raise ValidationError(f"plan path contains a hidden component: {value!r}")
    if target:
        if len(parts) != 2:
            raise ValidationError("target path must be one filename under an allowed directory")
        directory, name = parts
        if directory not in ("fpga_mesh", "tests"):
            raise ValidationError("target directory is not an allowed project source directory")
        if not name or not name.isascii():
            raise ValidationError("target filename must be plain ASCII")
        if directory == "fpga_mesh" and not _TARGET_MODULE_NAME.fullmatch(name):
            raise ValidationError("fpga_mesh target must be an identifier-like .py file")
        if directory == "tests" and not _TARGET_TEST_NAME.fullmatch(name):
            raise ValidationError("tests target must match test_*.py with an identifier-like name")
        folded = value.casefold()
        if any(token in folded for token in _DENIED_TARGET_TOKENS):
            raise ValidationError("target name is conservatively denied")
    return value


def _safe_operation_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError("operation_id must be a string")
    if len(value) > MAX_OPERATION_ID_CHARS or not _OPERATION_ID.fullmatch(value):
        raise ValidationError("operation_id is malformed")
    if value.endswith((".", " ")) or _bad_component(value):
        raise ValidationError("operation_id is not a safe directory name")
    return value


def _check_not_reparse(path: Path) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        raise
    attributes = getattr(info, "st_file_attributes", 0)
    if stat.S_ISLNK(info.st_mode) or attributes & _REPARSE_POINT:
        raise ValidationError(f"path contains a symlink or reparse point: {path}")
    if getattr(path, "is_junction", lambda: False)():
        raise ValidationError(f"path contains a junction: {path}")


def _assert_no_links(path: Path, *, allow_missing: bool = False) -> None:
    path = Path(path)
    if not path.is_absolute():
        raise ValidationError("filesystem paths must be absolute")
    current = Path(path.anchor)
    _check_not_reparse(current)
    for part in path.parts[1:]:
        current = current / part
        try:
            _check_not_reparse(current)
        except FileNotFoundError:
            if allow_missing and current == path:
                return
            raise ValidationError(f"required path component is missing: {current}")


def _validated_existing_root(value: Any, label: str) -> _RootInfo:
    text = _canonical_root_text(value, label)
    path = Path(text)
    try:
        _assert_no_links(path)
        info = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise ValidationError(f"{label} is not an accessible directory: {exc}") from exc
    if not stat.S_ISDIR(info.st_mode):
        raise ValidationError(f"{label} must be an existing directory")
    return _RootInfo(text=text, path=path, device=info.st_dev, file_id=info.st_ino)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValidationError(f"non-finite JSON value is not permitted: {value}")


def _strict_json(raw: bytes, label: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{label} is not strict UTF-8") from exc
    decoder = json.JSONDecoder(object_pairs_hook=_unique_object,
                               parse_constant=_reject_json_constant)
    try:
        value, end = decoder.raw_decode(text)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            raise
        raise ValidationError(f"{label} is not valid strict JSON") from exc
    if text[end:].strip():
        raise ValidationError(f"{label} has trailing data")
    return value


def _exact_keys(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    if set(value) != keys:
        raise ValidationError(f"{label} has missing or unknown keys")
    return value


def _nonnegative_int(value: Any, label: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{label} must be an integer")
    if value < 0:
        raise ValidationError(f"{label} must be nonnegative")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{label} exceeds the bounded maximum")
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise ValidationError(f"{label} must be lower-case SHA256 hex")
    return value


def _parse_image(value: Any, label: str) -> tuple[int, str]:
    image = _exact_keys(value, {"size", "sha256"}, label)
    size = _nonnegative_int(image["size"], f"{label}.size", maximum=MAX_FILE_BYTES)
    return size, _digest(image["sha256"], f"{label}.sha256")


def _parse_plan(raw: bytes, reviewed_plan_sha256: str) -> _Plan:
    digest = _digest(reviewed_plan_sha256, "reviewed_plan_sha256")
    actual = _sha256(raw)
    if actual != digest:
        raise PlanHashMismatch("out-of-band reviewed plan digest does not match raw plan bytes")
    value = _strict_json(raw, "plan")
    plan = _exact_keys(value, {
        "schema", "operation_id", "target_root", "source_root", "journal_root", "files",
    }, "plan")
    schema = _nonnegative_int(plan["schema"], "plan.schema")
    if schema != SCHEMA:
        raise ValidationError("unsupported plan schema")
    operation_id = _safe_operation_id(plan["operation_id"])
    target_root = _canonical_root_text(plan["target_root"], "target_root")
    source_root = _canonical_root_text(plan["source_root"], "source_root")
    journal_root = _canonical_root_text(plan["journal_root"], "journal_root")
    entries = plan["files"]
    if not isinstance(entries, list) or not entries:
        raise ValidationError("plan.files must be a nonempty list")
    if len(entries) > MAX_FILES:
        raise ValidationError("plan.files exceeds the entry limit")
    files: list[_PlanFile] = []
    seen_targets: set[str] = set()
    seen_sources: set[str] = set()
    total = 0
    for index, item in enumerate(entries):
        entry = _exact_keys(item, {"path", "source", "preimage", "postimage"},
                            f"plan.files[{index}]")
        path = _safe_relative(entry["path"], target=True)
        source = _safe_relative(entry["source"], target=False)
        pre_size, pre_sha = _parse_image(entry["preimage"], f"plan.files[{index}].preimage")
        post_size, post_sha = _parse_image(entry["postimage"], f"plan.files[{index}].postimage")
        target_key = path.casefold()
        source_key = source.casefold()
        if target_key in seen_targets:
            raise ValidationError("duplicate target path (case-insensitive)")
        if source_key in seen_sources:
            raise ValidationError("duplicate source path (case-insensitive)")
        seen_targets.add(target_key)
        seen_sources.add(source_key)
        if pre_size == post_size and pre_sha == post_sha:
            raise ValidationError("no-op file entry is not permitted")
        total += pre_size + post_size
        if total > MAX_TOTAL_BYTES:
            raise ValidationError("plan image total exceeds the bounded maximum")
        files.append(_PlanFile(path, source, pre_size, pre_sha, post_size, post_sha))
    return _Plan(raw=raw, sha256=actual, operation_id=operation_id,
                 target_root_text=target_root, source_root_text=source_root,
                 journal_root_text=journal_root, files=tuple(files))


def _canonical_file_text(value: Any, label: str) -> str:
    return _canonical_root_text(value, label)


def _read_file_snapshot(path: Path, *, exact_size: int | None,
                        maximum: int, label: str) -> _ObservedFile:
    path = Path(path)
    _assert_no_links(path)
    try:
        before = os.stat(path, follow_symlinks=False)
    except FileNotFoundError as exc:
        raise ValidationError(f"{label} does not exist: {path}") from exc
    if not stat.S_ISREG(before.st_mode):
        raise ValidationError(f"{label} must be an existing regular file")
    if before.st_nlink != 1:
        raise ValidationError(f"{label} must not be hard-linked")
    if exact_size is not None and before.st_size != exact_size:
        raise ValidationError(f"{label} size does not match the plan")
    if before.st_size > maximum:
        raise ValidationError(f"{label} exceeds the bounded file size")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValidationError(f"{label} could not be opened safely: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ConcurrentChangeError(f"{label} identity changed before open")
        if opened.st_nlink != 1 or not stat.S_ISREG(opened.st_mode):
            raise ValidationError(f"{label} is not a single-link regular file")
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if len(data) > maximum:
        raise ValidationError(f"{label} exceeds the bounded file size")
    if len(data) != opened.st_size or opened.st_size != after.st_size:
        raise ConcurrentChangeError(f"{label} changed size while being read")
    if (opened.st_dev, opened.st_ino, opened.st_mtime_ns, opened.st_ctime_ns) != (
            after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns):
        raise ConcurrentChangeError(f"{label} changed while being read")
    try:
        final = os.stat(path, follow_symlinks=False)
    except FileNotFoundError as exc:
        raise ConcurrentChangeError(f"{label} disappeared while being read") from exc
    if (final.st_dev, final.st_ino) != (opened.st_dev, opened.st_ino):
        raise ConcurrentChangeError(f"{label} path identity changed while being read")
    if exact_size is not None and len(data) != exact_size:
        raise ValidationError(f"{label} size does not match the plan")
    return _ObservedFile(path=path, data=data, sha256=_sha256(data), size=len(data),
                         device=after.st_dev, file_id=after.st_ino,
                         mtime_ns=after.st_mtime_ns, nlink=after.st_nlink)


def _read_plan(plan_path: Any, reviewed_plan_sha256: Any) -> _Plan:
    text = _canonical_file_text(plan_path, "plan_path")
    path = Path(text)
    _assert_no_links(path)
    snapshot = _read_file_snapshot(path, exact_size=None, maximum=MAX_PLAN_BYTES,
                                   label="plan file")
    return _parse_plan(snapshot.data, _digest(reviewed_plan_sha256,
                                               "reviewed_plan_sha256"))


def _same_or_descendant(child: Path, parent: Path) -> bool:
    child_text = os.path.normcase(os.path.abspath(str(child)))
    parent_text = os.path.normcase(os.path.abspath(str(parent)))
    if child_text == parent_text:
        return True
    try:
        common = os.path.commonpath((child_text, parent_text))
    except ValueError:
        return False
    return os.path.normcase(common) == parent_text


def _resolve_roots(plan: _Plan, plan_path: Path) -> tuple[_RootInfo, _RootInfo, _RootInfo]:
    target = _validated_existing_root(plan.target_root_text, "target_root")
    source = _validated_existing_root(plan.source_root_text, "source_root")
    journal = _validated_existing_root(plan.journal_root_text, "journal_root")
    roots = (target, source, journal)
    for left_index, left in enumerate(roots):
        for right in roots[left_index + 1:]:
            if (left.identity == right.identity or _same_or_descendant(left.path, right.path)
                    or _same_or_descendant(right.path, left.path)):
                raise ValidationError("target/source/journal roots must be disjoint")
    for root in roots:
        if _same_or_descendant(plan_path, root.path):
            raise ValidationError("plan_path must lie outside all plan roots")
    return target, source, journal


def _target_directories(preflight_files: Iterable[_FilePreflight]) -> dict[Path, tuple[int, int]]:
    result: dict[Path, tuple[int, int]] = {}
    for item in preflight_files:
        parent = item.target_parent
        if parent not in result:
            result[parent] = item.target_parent_identity
    return result


def _preflight(plan: _Plan, plan_path: Path, *, reject_existing_journal: bool) -> _Preflight:
    target_root, source_root, journal_root = _resolve_roots(plan, plan_path)
    plan_snapshot = _read_file_snapshot(Path(_canonical_file_text(plan_path, "plan_path")),
                                        exact_size=None, maximum=MAX_PLAN_BYTES,
                                        label="plan file")
    if plan_snapshot.data != plan.raw or plan_snapshot.sha256 != plan.sha256:
        raise ConcurrentChangeError("plan file changed after binding")
    journal_path = journal_root.path / plan.operation_id
    _assert_no_links(journal_path, allow_missing=True)
    journal_exists = os.path.lexists(journal_path)
    if journal_exists and reject_existing_journal:
        raise JournalExistsError("the operation journal already exists and is never reused")
    identities: dict[tuple[int, int], str] = {
        (plan_snapshot.device, plan_snapshot.file_id): "plan file",
    }
    files: list[_FilePreflight] = []
    for entry in plan.files:
        target = target_root.path / Path(entry.path)
        source = source_root.path / Path(entry.source)
        parent = target.parent
        _assert_no_links(parent)
        parent_info = os.stat(parent, follow_symlinks=False)
        if not stat.S_ISDIR(parent_info.st_mode):
            raise ValidationError(f"target parent is not a directory: {parent}")
        target_observation = _read_file_snapshot(
            target, exact_size=entry.pre_size, maximum=MAX_FILE_BYTES, label=f"target {entry.path}")
        if target_observation.sha256 != entry.pre_sha256:
            raise ValidationError(f"target preimage hash mismatch: {entry.path}")
        source_observation = _read_file_snapshot(
            source, exact_size=entry.post_size, maximum=MAX_FILE_BYTES,
            label=f"source {entry.source}")
        if source_observation.sha256 != entry.post_sha256:
            raise ValidationError(f"source/postimage hash mismatch: {entry.source}")
        for identity, description in (
                (target_observation.identity, f"target {entry.path}"),
                (source_observation.identity, f"source {entry.source}")):
            prior = identities.get(identity)
            if prior is not None:
                raise ValidationError(
                    f"file identity alias between {prior} and {description}")
            identities[identity] = description
        files.append(_FilePreflight(
            plan=entry, target=target, source=source, target_parent=parent,
            target_parent_identity=(parent_info.st_dev, parent_info.st_ino),
            target_observation=target_observation,
            immutable_payload=source_observation.data,
            source_observation=source_observation))
    return _Preflight(plan=plan, target_root=target_root, source_root=source_root,
                      journal_root=journal_root, journal_path=journal_path,
                      target_directories=_target_directories(files), files=tuple(files),
                      journal_exists=journal_exists)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError(errno.EIO, "short write")
        view = view[written:]


def _exclusive_flags() -> int:
    return (os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))


def _write_exclusive_file(path: Path, payload: bytes) -> _ObservedFile:
    path = Path(path)
    _assert_no_links(path, allow_missing=True)
    descriptor = os.open(path, _exclusive_flags(), 0o600)
    try:
        _write_all(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    observed = _read_file_snapshot(path, exact_size=len(payload),
                                   maximum=max(MAX_FILE_BYTES, len(payload)),
                                   label=f"written journal file {path.name}")
    if observed.sha256 != _sha256(payload):
        raise OSError(errno.EIO, f"written file hash mismatch: {path.name}")
    return observed


def _write_temp_sibling(target: Path, payload: bytes, *, tag: str) -> tuple[Path, _ObservedFile]:
    target = Path(target)
    _assert_no_links(target.parent)
    name = f".{target.name}.local-patch-{tag}-{uuid.uuid4().hex}.tmp"
    temporary = target.parent / name
    if os.path.lexists(temporary):
        raise FileExistsError(errno.EEXIST, "generated temporary path already exists", temporary)
    observed = _write_exclusive_file(temporary, payload)
    return temporary, observed


def _mutex_name(device: int, file_id: int) -> str:
    key = _sha256(f"{device}:{file_id}".encode("ascii"))[:32]
    return f"Global\\CarlandFPGA.local-patch.{key}"


class _TargetMutex:
    """Target-directory scoped, nonblocking Windows named mutex."""

    _WAIT_OBJECT_0 = 0x00000000
    _WAIT_ABANDONED = 0x00000080
    _WAIT_TIMEOUT = 0x00000102

    def __init__(self, target: Path | _RootInfo | tuple[int, int]):
        if isinstance(target, _RootInfo):
            identity = target.identity
        elif isinstance(target, tuple):
            identity = target
        else:
            info = os.stat(Path(target), follow_symlinks=False)
            identity = (info.st_dev, info.st_ino)
        self.identity = identity
        self.name = _mutex_name(*identity)
        self._kernel32 = None
        self._handle = None
        self._acquired = False

    def __enter__(self) -> "_TargetMutex":
        if os.name != "nt":
            raise UnsupportedPlatformError("apply requires Windows named-mutex exclusivity")
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
            kernel32.WaitForSingleObject.restype = ctypes.c_ulong
            kernel32.ReleaseMutex.argtypes = (ctypes.c_void_p,)
            kernel32.ReleaseMutex.restype = ctypes.c_bool
            kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
            kernel32.CloseHandle.restype = ctypes.c_bool
        except (AttributeError, OSError) as exc:
            raise ExclusivityError("Windows named mutex API is unavailable") from exc
        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            error = ctypes.get_last_error()
            raise ExclusivityError(f"CreateMutexW failed with Windows error {error}")
        self._kernel32 = kernel32
        self._handle = handle
        result = kernel32.WaitForSingleObject(handle, 0)
        if result == self._WAIT_ABANDONED:
            released = kernel32.ReleaseMutex(handle)
            kernel32.CloseHandle(handle)
            self._handle = None
            if not released:
                raise ExclusivityError("abandoned target mutex could not be released safely")
            raise MutexAbandonedError("target mutex was abandoned; reconciliation is required")
        if result == self._WAIT_TIMEOUT:
            kernel32.CloseHandle(handle)
            self._handle = None
            raise BusyError("another apply holds the target-specific mutex")
        if result != self._WAIT_OBJECT_0:
            error = ctypes.get_last_error()
            kernel32.CloseHandle(handle)
            self._handle = None
            raise ExclusivityError(f"WaitForSingleObject failed with {result}/{error}")
        self._acquired = True
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        failure = None
        if self._handle is not None and self._kernel32 is not None:
            if self._acquired and not self._kernel32.ReleaseMutex(self._handle):
                failure = ExclusivityError("ReleaseMutex failed for an owned mutex")
            self._acquired = False
            if not self._kernel32.CloseHandle(self._handle):
                failure = failure or ExclusivityError("CloseHandle failed for the target mutex")
            self._handle = None
        if failure is not None and exc_type is None:
            raise failure
        return False


class _Journal:
    """Append-only, checksummed and fsynced JSONL event chain."""

    def __init__(self, path: Path, operation_id: str, plan_sha256: str):
        self.path = Path(path)
        self.operation_id = operation_id
        self.plan_sha256 = plan_sha256
        self.descriptor: int | None = None
        self.identity: tuple[int, int] | None = None
        self.offset = 0
        self.sequence = 0
        self.previous = _GENESIS
        self.healthy = False
        self.last_error: str | None = None

    def create(self) -> None:
        _assert_no_links(self.path, allow_missing=True)
        descriptor = os.open(self.path, _exclusive_flags(), 0o600)
        try:
            os.fsync(descriptor)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise OSError(errno.EIO, "journal file is not a single-link regular file")
        except BaseException:
            os.close(descriptor)
            raise
        self.descriptor = descriptor
        self.identity = (info.st_dev, info.st_ino)
        self.offset = 0
        self.healthy = True

    def _validate_existing_chain(self) -> None:
        try:
            _assert_no_links(self.path)
            info = os.stat(self.path, follow_symlinks=False)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or self.identity is None
                    or (info.st_dev, info.st_ino) != self.identity
                    or info.st_size != self.offset):
                raise ConcurrentChangeError("journal path, identity or size changed")
            if self.sequence:
                events, problems, torn = _read_journal_events(self.path)
                if (problems or torn or len(events) != self.sequence
                        or events[-1].get("checksum") != self.previous):
                    raise ConcurrentChangeError("journal chain changed on disk")
        except BaseException as exc:
            self.healthy = False
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise

    def append(self, record_type: str, **fields: Any) -> dict[str, Any]:
        if self.descriptor is None or not self.healthy:
            raise OSError(errno.EIO, "journal is not healthy")
        self._validate_existing_chain()
        record: dict[str, Any] = {
            "seq": self.sequence + 1,
            "type": record_type,
            "prev": self.previous,
            "at": _utc_now(),
        }
        record.update(fields)
        unsigned = json.dumps(record, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")).encode("utf-8")
        record["checksum"] = _sha256(unsigned)
        line = json.dumps(record, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8") + b"\n"
        try:
            _write_all(self.descriptor, line)
            os.fsync(self.descriptor)
        except BaseException as exc:
            self.healthy = False
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise
        self.offset += len(line)
        self.sequence = record["seq"]
        self.previous = record["checksum"]
        return record

    def close(self) -> None:
        if self.descriptor is not None:
            descriptor = self.descriptor
            self.descriptor = None
            os.close(descriptor)


def _error_record(phase: str, exc: BaseException) -> dict[str, Any]:
    result: dict[str, Any] = {
        "phase": phase,
        "type": type(exc).__name__,
        "message": str(exc)[:500],
    }
    if isinstance(exc, OSError):
        result["errno"] = exc.errno
        result["winerror"] = getattr(exc, "winerror", None)
        result["filename"] = str(exc.filename)[:500] if exc.filename else None
    return result


def _assert_target_layout(preflight: _Preflight, item: _FilePreflight) -> None:
    root = preflight.target_root.path
    _assert_no_links(root)
    info = os.stat(root, follow_symlinks=False)
    if (info.st_dev, info.st_ino) != preflight.target_root.identity:
        raise ConcurrentChangeError("target root identity changed")
    parent = item.target_parent
    _assert_no_links(parent)
    parent_info = os.stat(parent, follow_symlinks=False)
    if (parent_info.st_dev, parent_info.st_ino) != item.target_parent_identity:
        raise ConcurrentChangeError("target parent identity changed")
    _assert_no_links(item.target)


def _assert_journal_root(preflight: _Preflight) -> None:
    root = preflight.journal_root.path
    _assert_no_links(root)
    info = os.stat(root, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        raise ConcurrentChangeError("journal root is no longer a directory")
    if (info.st_dev, info.st_ino) != preflight.journal_root.identity:
        raise ConcurrentChangeError("journal root identity changed")


def _assert_journal_layout(preflight: _Preflight, operation_identity: tuple[int, int] | None,
                           backups_identity: tuple[int, int] | None) -> None:
    _assert_journal_root(preflight)
    operation = preflight.journal_path
    _assert_no_links(operation)
    if operation_identity is not None:
        operation_info = os.stat(operation, follow_symlinks=False)
        if (operation_info.st_dev, operation_info.st_ino) != operation_identity:
            raise ConcurrentChangeError("journal operation identity changed")
    if backups_identity is not None:
        backups = operation / "backups"
        _assert_no_links(backups)
        backups_info = os.stat(backups, follow_symlinks=False)
        if (backups_info.st_dev, backups_info.st_ino) != backups_identity:
            raise ConcurrentChangeError("journal backup-directory identity changed")


def _observe_exact_target(item: _FilePreflight, expected_size: int,
                          expected_sha256: str, expected_identity: tuple[int, int] | None,
                          label: str) -> _ObservedFile:
    try:
        observed = _read_file_snapshot(item.target, exact_size=expected_size,
                                       maximum=MAX_FILE_BYTES, label=label)
    except ValidationError as exc:
        raise ConcurrentChangeError(str(exc)) from exc
    if observed.sha256 != expected_sha256:
        raise ConcurrentChangeError(f"{label} bytes changed")
    if expected_identity is not None and observed.identity != expected_identity:
        raise ConcurrentChangeError(f"{label} file identity changed")
    return observed


def _file_summary(item: _FilePreflight, index: int) -> dict[str, Any]:
    return {
        "index": index,
        "path": item.plan.path,
        "source": item.plan.source,
        "preimage": {"size": item.plan.pre_size, "sha256": item.plan.pre_sha256},
        "postimage": {"size": item.plan.post_size, "sha256": item.plan.post_sha256},
    }


def dry_run(plan_path: Any, *, reviewed_plan_sha256: str) -> dict[str, Any]:
    """Validate and read the complete bounded plan without writing anything."""
    plan = _read_plan(plan_path, reviewed_plan_sha256)
    preflight = _preflight(plan, Path(_canonical_file_text(plan_path, "plan_path")),
                           reject_existing_journal=False)
    status = "blocked" if preflight.journal_exists else "valid"
    return {
        "schema": SCHEMA,
        "status": status,
        "apply_eligible": not preflight.journal_exists,
        "operation_id": plan.operation_id,
        "reviewed_plan_sha256": plan.sha256,
        "journal_path": str(preflight.journal_path),
        "journal_present": preflight.journal_exists,
        "files": [_file_summary(item, index) for index, item in enumerate(preflight.files)],
        "limits": {"files": MAX_FILES, "file_bytes": MAX_FILE_BYTES,
                   "total_bytes": MAX_TOTAL_BYTES},
        "payload_snapshot": "immutable_preflight_bytes",
        "writes": False,
    }


def _prepare_transaction(preflight: _Preflight, preparation: _Preparation) -> None:
    _assert_journal_root(preflight)
    operation = preflight.journal_path
    try:
        os.mkdir(operation)
    except FileExistsError as exc:
        raise JournalExistsError("the operation journal already exists") from exc
    _assert_no_links(operation)
    operation_info = os.stat(operation, follow_symlinks=False)
    preparation.operation_identity = (operation_info.st_dev, operation_info.st_ino)
    _assert_journal_layout(preflight, preparation.operation_identity, None)
    approved_plan = operation / "approved-plan.json"
    _write_exclusive_file(approved_plan, preflight.plan.raw)
    _assert_journal_layout(preflight, preparation.operation_identity, None)
    journal = _Journal(operation / "events.jsonl", preflight.plan.operation_id,
                       preflight.plan.sha256)
    preparation.journal = journal
    _assert_journal_layout(preflight, preparation.operation_identity, None)
    journal.create()
    journal.append(
        "plan_bound",
        operation_id=preflight.plan.operation_id,
        plan_sha256=preflight.plan.sha256,
        approved_plan="approved-plan.json",
        operation_dir_identity={"device": operation_info.st_dev,
                                "file_id": operation_info.st_ino},
    )
    _assert_journal_layout(preflight, preparation.operation_identity, None)
    backups = operation / "backups"
    os.mkdir(backups)
    _assert_no_links(backups)
    backups_info = os.stat(backups, follow_symlinks=False)
    preparation.backups_identity = (backups_info.st_dev, backups_info.st_ino)
    for index, item in enumerate(preflight.files):
        _assert_target_layout(preflight, item)
        _assert_journal_layout(preflight, preparation.operation_identity,
                               preparation.backups_identity)
        original = _observe_exact_target(
            item, item.plan.pre_size, item.plan.pre_sha256,
            item.target_observation.identity, "target preimage before backup")
        backup = backups / f"{index:04d}.backup"
        backup_observation = _write_exclusive_file(backup, original.data)
        if (backup_observation.sha256 != item.plan.pre_sha256
                or backup_observation.size != item.plan.pre_size):
            raise OSError(errno.EIO, "backup verification failed")
        item.backup_path = backup
        item.backup_observation = backup_observation
        journal.append(
            "backup_saved",
            index=index,
            path=item.plan.path,
            backup=f"backups/{backup.name}",
            size=backup_observation.size,
            sha256=backup_observation.sha256,
            identity={"device": backup_observation.device,
                      "file_id": backup_observation.file_id},
        )
    _assert_journal_layout(preflight, preparation.operation_identity,
                           preparation.backups_identity)
    journal.append(
        "prepared",
        operation_id=preflight.plan.operation_id,
        plan_sha256=preflight.plan.sha256,
        target_root=str(preflight.target_root.path),
        source_root=str(preflight.source_root.path),
        journal_root=str(preflight.journal_root.path),
        files=[_file_summary_fields(item.plan) for item in preflight.files],
        payload_snapshot="immutable_preflight_bytes",
    )
    preparation.prepared = True


def _record_uncertain_write(journal: _Journal | None, index: int, item: _FilePreflight,
                            temporary: Path, exc: BaseException) -> None:
    if journal is None or not journal.healthy:
        return
    try:
        journal.append("write_uncertain", index=index, path=item.plan.path,
                       temporary=temporary.name, error=_error_record("target_replace", exc))
    except Exception:
        pass


def _perform_writes(preflight: _Preflight, preparation: _Preparation,
                    statuses: dict[str, str], errors: list[dict[str, Any]],
                    uncertain: list[dict[str, Any]],
                    known: list[_KnownWrite]) -> None:
    journal = preparation.journal
    assert journal is not None
    for index, item in enumerate(preflight.files):
        _assert_target_layout(preflight, item)
        _assert_journal_layout(preflight, preparation.operation_identity,
                               preparation.backups_identity)
        _observe_exact_target(item, item.plan.pre_size, item.plan.pre_sha256,
                              item.target_observation.identity,
                              "target preimage before payload temporary")
        temporary, temporary_observation = _write_temp_sibling(
            item.target, item.immutable_payload, tag="apply")
        if (temporary_observation.sha256 != item.plan.post_sha256
                or temporary_observation.size != item.plan.post_size):
            raise OSError(errno.EIO, "payload temporary verification failed")
        _assert_journal_layout(preflight, preparation.operation_identity,
                               preparation.backups_identity)
        journal.append(
            "write_intent",
            index=index,
            path=item.plan.path,
            temporary=temporary.name,
            preimage={"size": item.plan.pre_size, "sha256": item.plan.pre_sha256},
            postimage={"size": item.plan.post_size, "sha256": item.plan.post_sha256},
            expected_preimage_identity={"device": item.target_observation.device,
                                        "file_id": item.target_observation.file_id},
        )
        _assert_target_layout(preflight, item)
        _observe_exact_target(item, item.plan.pre_size, item.plan.pre_sha256,
                              item.target_observation.identity,
                              "target preimage immediately before replace")
        temporary_now = _read_file_snapshot(
            temporary, exact_size=item.plan.post_size, maximum=MAX_FILE_BYTES,
            label="payload temporary immediately before replace")
        if (temporary_now.sha256 != item.plan.post_sha256
                or temporary_now.identity != temporary_observation.identity):
            raise ConcurrentChangeError("payload temporary changed before replacement")
        _assert_journal_layout(preflight, preparation.operation_identity,
                               preparation.backups_identity)
        journal._validate_existing_chain()
        try:
            os.replace(temporary, item.target)
        except BaseException as exc:
            uncertain.append({"index": index, "path": item.plan.path,
                              "phase": "target_replace", "error": _error_record("target_replace", exc)})
            _record_uncertain_write(journal, index, item, temporary, exc)
            statuses[item.plan.path] = "write_uncertain"
            raise
        known_write = _KnownWrite(
            index=index, plan_file=item.plan, target=item.target, temporary=temporary,
            temporary_observation=temporary_observation)
        known.append(known_write)
        try:
            observed = _read_file_snapshot(item.target, exact_size=item.plan.post_size,
                                           maximum=MAX_FILE_BYTES,
                                           label=f"target postimage {item.plan.path}")
        except Exception as exc:
            uncertain.append({"index": index, "path": item.plan.path,
                              "phase": "postcheck_failed",
                              "error": _error_record("postreplace_observe", exc)})
            if journal.healthy:
                try:
                    journal.append("postcheck_failed", index=index, path=item.plan.path,
                                   observed_identity=None, observed_sha256=None,
                                   error=_error_record("postreplace_observe", exc))
                except Exception:
                    pass
            raise
        if (observed.sha256 != item.plan.post_sha256
                or observed.identity != temporary_observation.identity):
            uncertain.append({
                "index": index, "path": item.plan.path, "phase": "postcheck_failed",
                "observed_identity": {"device": observed.device,
                                      "file_id": observed.file_id},
                "expected_identity": {"device": temporary_observation.device,
                                      "file_id": temporary_observation.file_id},
            })
            statuses[item.plan.path] = "postcheck_failed"
            journal.append("postcheck_failed", index=index, path=item.plan.path,
                           observed_sha256=observed.sha256,
                           observed_identity={"device": observed.device,
                                              "file_id": observed.file_id},
                           expected_identity={"device": temporary_observation.device,
                                              "file_id": temporary_observation.file_id})
            raise ConcurrentChangeError(
                "target postimage hash or identity verification failed")
        known_write.observation = observed
        statuses[item.plan.path] = "applied"
        journal.append(
            "applied",
            index=index,
            path=item.plan.path,
            observed_sha256=observed.sha256,
            observed_size=observed.size,
            observed_identity={"device": observed.device, "file_id": observed.file_id},
        )
    for write in known:
        item = preflight.files[write.index]
        _assert_target_layout(preflight, item)
        _observe_exact_target(item, item.plan.post_size, item.plan.post_sha256,
                              write.temporary_observation.identity,
                              "final target postimage")


def _append_terminal(journal: _Journal | None, status: str,
                     statuses: dict[str, str], errors: list[dict[str, Any]],
                     **extra: Any) -> bool:
    if journal is None or not journal.healthy:
        return False
    try:
        journal.append("terminal", status=status,
                       targets=[{"path": path, "status": value}
                                for path, value in sorted(statuses.items())],
                       errors=errors, **extra)
        return True
    except Exception as exc:
        journal.healthy = False
        journal.last_error = f"{type(exc).__name__}: {exc}"
        return False


def _record_rollback_result(journal: _Journal | None, index: int,
                            item: _FilePreflight, status: str,
                            **fields: Any) -> bool:
    if journal is None or not journal.healthy:
        return False
    try:
        journal.append("rollback_result", index=index, path=item.plan.path,
                       status=status, **fields)
        return True
    except Exception as exc:
        journal.healthy = False
        journal.last_error = f"{type(exc).__name__}: {exc}"
        return False


def _rollback(preflight: _Preflight, preparation: _Preparation,
              known: list[_KnownWrite], statuses: dict[str, str],
              errors: list[dict[str, Any]]) -> None:
    journal = preparation.journal
    unreconciled = False
    for write in reversed(known):
        item = preflight.files[write.index]
        if unreconciled or journal is None or not journal.healthy:
            statuses[item.plan.path] = "uncertain_unrolled"
            continue
        try:
            _assert_journal_layout(preflight, preparation.operation_identity,
                                   preparation.backups_identity)
        except Exception as exc:
            errors.append(_error_record("rollback_journal_layout", exc))
            statuses[item.plan.path] = "uncertain_unrolled"
            unreconciled = True
            continue
        try:
            _assert_target_layout(preflight, item)
        except Exception as exc:
            errors.append(_error_record("rollback_path_check", exc))
            statuses[item.plan.path] = "uncertain_unrolled"
            _record_rollback_result(
                journal, write.index, item, "protected",
                reason="target path identity is no longer safe",
                error=_error_record("rollback_path_check", exc))
            continue
        if item.backup_path is None or item.backup_observation is None:
            statuses[item.plan.path] = "protected_backup_corrupt"
            _record_rollback_result(journal, write.index, item, "protected",
                                    reason="backup metadata is missing")
            continue
        try:
            backup = _read_file_snapshot(item.backup_path,
                                         exact_size=item.plan.pre_size,
                                         maximum=MAX_FILE_BYTES,
                                         label="rollback backup")
        except Exception as exc:
            errors.append(_error_record("rollback_backup_read", exc))
            statuses[item.plan.path] = "protected_backup_corrupt"
            _record_rollback_result(journal, write.index, item, "protected",
                                    reason="backup is unreadable or corrupted",
                                    error=_error_record("rollback_backup_read", exc))
            continue
        if (backup.sha256 != item.plan.pre_sha256
                or backup.identity != item.backup_observation.identity):
            statuses[item.plan.path] = "protected_backup_corrupt"
            _record_rollback_result(journal, write.index, item, "protected",
                                    reason="backup bytes or identity changed")
            continue
        expected_identity = write.temporary_observation.identity
        try:
            _observe_exact_target(item, item.plan.post_size, item.plan.post_sha256,
                                  expected_identity,
                                  "own postimage before rollback")
        except Exception as exc:
            errors.append(_error_record("rollback_ownership_check", exc))
            statuses[item.plan.path] = "protected_foreign_change"
            _record_rollback_result(journal, write.index, item, "protected",
                                    reason="target no longer matches this operation's postimage",
                                    error=_error_record("rollback_ownership_check", exc))
            continue
        try:
            journal.append("rollback_intent", index=write.index,
                           path=item.plan.path,
                           expected_postimage_identity={"device": expected_identity[0],
                                                        "file_id": expected_identity[1]},
                           restore_sha256=item.plan.pre_sha256)
        except Exception as exc:
            errors.append(_error_record("rollback_intent", exc))
            statuses[item.plan.path] = "uncertain_unrolled"
            unreconciled = True
            continue
        try:
            temporary, temporary_observation = _write_temp_sibling(
                item.target, backup.data, tag="rollback")
            if (temporary_observation.sha256 != item.plan.pre_sha256
                    or temporary_observation.size != item.plan.pre_size):
                raise OSError(errno.EIO, "rollback temporary verification failed")
        except Exception as exc:
            errors.append(_error_record("rollback_temporary", exc))
            statuses[item.plan.path] = "rollback_failed"
            _record_rollback_result(journal, write.index, item, "failed",
                                    error=_error_record("rollback_temporary", exc))
            continue
        try:
            _assert_target_layout(preflight, item)
            _observe_exact_target(item, item.plan.post_size, item.plan.post_sha256,
                                  expected_identity,
                                  "own postimage immediately before rollback replace")
        except Exception as exc:
            errors.append(_error_record("rollback_recheck", exc))
            statuses[item.plan.path] = "protected_foreign_change"
            _record_rollback_result(journal, write.index, item, "protected",
                                    reason="target changed immediately before rollback",
                                    error=_error_record("rollback_recheck", exc))
            continue
        try:
            temporary_now = _read_file_snapshot(
                temporary, exact_size=item.plan.pre_size, maximum=MAX_FILE_BYTES,
                label="restore temporary immediately before replace")
            if (temporary_now.sha256 != item.plan.pre_sha256
                    or temporary_now.identity != temporary_observation.identity):
                raise ConcurrentChangeError("restore temporary changed before replacement")
        except Exception as exc:
            errors.append(_error_record("rollback_temporary_recheck", exc))
            statuses[item.plan.path] = "rollback_failed"
            _record_rollback_result(journal, write.index, item, "failed",
                                    error=_error_record("rollback_temporary_recheck", exc))
            continue
        try:
            _assert_journal_layout(preflight, preparation.operation_identity,
                                   preparation.backups_identity)
            journal._validate_existing_chain()
        except Exception as exc:
            errors.append(_error_record("rollback_journal_recheck", exc))
            statuses[item.plan.path] = "uncertain_unrolled"
            unreconciled = True
            continue
        try:
            os.replace(temporary, item.target)
        except BaseException as exc:
            errors.append(_error_record("rollback_replace", exc))
            statuses[item.plan.path] = "rollback_uncertain"
            _record_rollback_result(journal, write.index, item, "uncertain",
                                    error=_error_record("rollback_replace", exc))
            if not isinstance(exc, Exception):
                raise
            continue
        try:
            restored = _read_file_snapshot(item.target,
                                           exact_size=item.plan.pre_size,
                                           maximum=MAX_FILE_BYTES,
                                           label="restored target preimage")
            if (restored.sha256 != item.plan.pre_sha256
                    or restored.identity != temporary_observation.identity):
                raise ConcurrentChangeError("restored target bytes or identity changed")
        except Exception as exc:
            errors.append(_error_record("rollback_postcheck", exc))
            statuses[item.plan.path] = "rollback_uncertain"
            _record_rollback_result(journal, write.index, item, "uncertain",
                                    error=_error_record("rollback_postcheck", exc))
            continue
        statuses[item.plan.path] = "rolled_back"
        _record_rollback_result(journal, write.index, item, "restored",
                                restored_sha256=restored.sha256,
                                restored_size=restored.size,
                                restored_identity={"device": restored.device,
                                                   "file_id": restored.file_id})


def _classify_target_path(target: Path, entry: _PlanFile) -> dict[str, Any]:
    if not os.path.lexists(target):
        return {"path": entry.path, "classification": "missing"}
    try:
        observed = _read_file_snapshot(target, exact_size=None,
                                       maximum=MAX_FILE_BYTES,
                                       label=f"inspection target {entry.path}")
    except Exception as exc:
        return {"path": entry.path, "classification": "unreadable",
                "error": _error_record("current_target_read", exc)}
    if observed.sha256 == entry.pre_sha256:
        classification = "preimage"
    elif observed.sha256 == entry.post_sha256:
        classification = "postimage"
    else:
        classification = "other"
    return {"path": entry.path, "classification": classification,
            "size": observed.size, "sha256": observed.sha256,
            "identity": {"device": observed.device, "file_id": observed.file_id}}


def _current_target_state(item: _FilePreflight) -> dict[str, Any]:
    return _classify_target_path(item.target, item.plan)


_EVENT_TYPES = {
    "plan_bound", "backup_saved", "prepared", "write_intent", "applied",
    "write_uncertain", "postcheck_failed", "rollback_intent", "rollback_result",
    "terminal", "aborted",
}


def _read_journal_events(path: Path) -> tuple[list[dict[str, Any]], list[str], bool]:
    problems: list[str] = []
    try:
        snapshot = _read_file_snapshot(path, exact_size=None,
                                       maximum=MAX_JOURNAL_BYTES, label="journal events")
    except Exception as exc:
        return [], [f"journal events are unreadable: {type(exc).__name__}: {exc}"], False
    raw = snapshot.data
    if not raw:
        return [], ["journal events file is empty"], False
    torn = not raw.endswith(b"\n")
    lines = raw.splitlines()
    if torn and lines and lines[-1]:
        problems.append("journal has a torn final record")
    events: list[dict[str, Any]] = []
    previous = _GENESIS
    for position, line in enumerate(lines, 1):
        if not line:
            problems.append(f"journal line {position} is empty")
            break
        try:
            record = _strict_json(line, f"journal line {position}")
            if not isinstance(record, dict):
                raise ValidationError("journal record must be an object")
            required = {"seq", "type", "prev", "at", "checksum"}
            if not required.issubset(record):
                raise ValidationError("journal record lacks required fields")
            if isinstance(record["seq"], bool) or not isinstance(record["seq"], int):
                raise ValidationError("journal seq is not an integer")
            if record["seq"] != position:
                raise ValidationError("journal sequence is not contiguous")
            if record["type"] not in _EVENT_TYPES:
                raise ValidationError("unknown journal record type")
            if record["prev"] != previous:
                raise ValidationError("journal previous-event digest mismatch")
            checksum = _digest(record["checksum"], "journal checksum")
            unsigned = {key: value for key, value in record.items() if key != "checksum"}
            canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode("utf-8")
            if _sha256(canonical) != checksum:
                raise ValidationError("journal record checksum mismatch")
        except Exception as exc:
            problems.append(f"journal line {position} is invalid: {type(exc).__name__}: {exc}")
            break
        events.append(record)
        previous = checksum
    return events, problems, torn


def _inspection_base(plan: _Plan, journal_path: Path, present: bool) -> dict[str, Any]:
    targets = []
    for entry in plan.files:
        target = Path(plan.target_root_text) / Path(entry.path)
        targets.append(_classify_target_path(target, entry))
    return {
        "schema": SCHEMA,
        "operation_id": plan.operation_id,
        "plan_sha256": plan.sha256,
        "reviewed_plan_sha256": plan.sha256,
        "journal_path": str(journal_path),
        "journal_present": present,
        "status": "absent" if not present else "ambiguous",
        "evidence_valid": False,
        "chain_valid": False,
        "torn_final_record": False,
        "plan_storage_valid": False,
        "terminal": None,
        "files": targets,
        "backups": [],
        "write_intents": [],
        "confirmed_writes": 0,
        "write_uncertainties": [],
        "rollback_results": [],
        "unresolved_write_intents": [],
        "requires_main_review": False if not present else True,
        "mutates_state": False,
        "recovery_actions": False,
    }


def _event_index(record: dict[str, Any], expected_type: str, count: int,
                 problems: list[str]) -> int | None:
    value = record.get("index")
    if isinstance(value, bool) or not isinstance(value, int):
        problems.append(f"{expected_type} event has an invalid index")
        return None
    if value < 0 or value >= count:
        problems.append(f"{expected_type} event index is out of range")
        return None
    return value


def _file_summary_fields(entry: _PlanFile) -> dict[str, Any]:
    return {
        "path": entry.path,
        "source": entry.source,
        "preimage": {"size": entry.pre_size, "sha256": entry.pre_sha256},
        "postimage": {"size": entry.post_size, "sha256": entry.post_sha256},
    }


def _verify_inspected_backup(operation: Path, entry: _PlanFile,
                             record: dict[str, Any], problems: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"path": entry.path, "valid": False}
    relative = record.get("backup")
    if not isinstance(relative, str) or not relative.startswith("backups/"):
        problems.append(f"backup record for {entry.path} has an unsafe relative name")
        return result
    name = relative.split("/", 1)[1]
    if "/" in name or "\\" in name or ":" in name or name in (".", ".."):
        problems.append(f"backup record for {entry.path} has an unsafe name")
        return result
    backup = operation / "backups" / name
    try:
        _assert_no_links(backup)
        observed = _read_file_snapshot(backup, exact_size=entry.pre_size,
                                       maximum=MAX_FILE_BYTES,
                                       label=f"inspection backup {entry.path}")
        identity = record.get("identity")
        identity_ok = (isinstance(identity, dict)
                       and identity.get("device") == observed.device
                       and identity.get("file_id") == observed.file_id)
        valid = observed.sha256 == entry.pre_sha256 and identity_ok
        result.update({
            "backup": relative,
            "size": observed.size,
            "sha256": observed.sha256,
            "identity": {"device": observed.device, "file_id": observed.file_id},
            "valid": valid,
        })
        if not valid:
            problems.append(f"backup bytes or identity changed for {entry.path}")
    except Exception as exc:
        problems.append(f"backup is unreadable for {entry.path}: {type(exc).__name__}: {exc}")
        result["error"] = _error_record("inspection_backup", exc)
    return result


def _identity_matches(value: Any, state: dict[str, Any]) -> bool:
    identity = state.get("identity")
    return (isinstance(value, dict) and isinstance(identity, dict)
            and value.get("device") == identity.get("device")
            and value.get("file_id") == identity.get("file_id"))


def _inspect_present(plan: _Plan, operation: Path,
                     initial_problems: list[str] | None = None) -> dict[str, Any]:
    report = _inspection_base(plan, operation, True)
    problems = list(initial_problems or [])
    approved_path = operation / "approved-plan.json"
    try:
        _assert_no_links(operation)
        info = os.stat(operation, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode):
            raise ValidationError("operation journal is not a directory")
        approved = _read_file_snapshot(approved_path, exact_size=None,
                                       maximum=MAX_PLAN_BYTES,
                                       label="approved plan storage")
        report["plan_storage_valid"] = approved.data == plan.raw and approved.sha256 == plan.sha256
        if not report["plan_storage_valid"]:
            problems.append("stored approved plan bytes do not match the reviewed plan")
    except Exception as exc:
        problems.append(f"journal operation or stored plan is unreadable: {type(exc).__name__}: {exc}")
    events, event_problems, torn = _read_journal_events(operation / "events.jsonl")
    problems.extend(event_problems)
    report["torn_final_record"] = torn
    report["chain_valid"] = not event_problems and bool(events)

    plan_bound: dict[str, Any] | None = None
    prepared: dict[str, Any] | None = None
    terminal: dict[str, Any] | None = None
    backup_records: dict[int, dict[str, Any]] = {}
    intents: dict[int, dict[str, Any]] = {}
    applied: dict[int, dict[str, Any]] = {}
    uncertainties: list[dict[str, Any]] = []
    rollback_results: dict[int, list[dict[str, Any]]] = {}
    for position, record in enumerate(events):
        record_type = record["type"]
        if record_type == "terminal" and position != len(events) - 1:
            problems.append("terminal record is not the final journal event")
        if record_type in {"write_intent", "applied", "write_uncertain",
                           "postcheck_failed", "rollback_intent", "rollback_result",
                           "backup_saved"}:
            index = _event_index(record, record_type, len(plan.files), problems)
            if index is None:
                continue
            if record.get("path") != plan.files[index].path:
                problems.append(f"{record_type} path does not match plan index {index}")
            if record_type == "backup_saved":
                if index in backup_records:
                    problems.append(f"duplicate backup_saved event for index {index}")
                backup_records[index] = record
            elif record_type == "write_intent":
                if index in intents:
                    problems.append(f"duplicate write_intent event for index {index}")
                intents[index] = record
            elif record_type == "applied":
                if index in applied:
                    problems.append(f"duplicate applied event for index {index}")
                applied[index] = record
            elif record_type == "write_uncertain":
                uncertainties.append(record)
            elif record_type == "postcheck_failed":
                uncertainties.append(record)
            elif record_type == "rollback_result":
                rollback_results.setdefault(index, []).append(record)
        elif record_type == "plan_bound":
            if position != 0 or plan_bound is not None:
                problems.append("plan_bound must be the unique first event")
            plan_bound = record
            if record.get("operation_id") != plan.operation_id:
                problems.append("plan_bound operation_id does not match the plan")
            if record.get("plan_sha256") != plan.sha256:
                problems.append("plan_bound plan digest does not match the plan")
        elif record_type == "prepared":
            if prepared is not None:
                problems.append("duplicate prepared event")
            prepared = record
        elif record_type == "terminal":
            if terminal is not None:
                problems.append("duplicate terminal event")
            terminal = record
    if plan_bound is None:
        problems.append("journal has no plan_bound event")
    else:
        bound_identity = plan_bound.get("operation_dir_identity")
        try:
            operation_info = os.stat(operation, follow_symlinks=False)
        except OSError as exc:
            problems.append(
                f"journal operation directory is unreadable: {type(exc).__name__}: {exc}")
        else:
            if (not isinstance(bound_identity, dict)
                    or bound_identity.get("device") != operation_info.st_dev
                    or bound_identity.get("file_id") != operation_info.st_ino):
                problems.append("journal operation directory identity changed")
    if prepared is None:
        problems.append("journal has no prepared event")
    else:
        prepared_files = prepared.get("files")
        expected_files = [_file_summary_fields(entry) for entry in plan.files]
        if prepared_files != expected_files:
            problems.append("prepared file list does not exactly match the plan")
        if prepared.get("plan_sha256") != plan.sha256:
            problems.append("prepared plan digest does not match the plan")
        if prepared.get("operation_id") != plan.operation_id:
            problems.append("prepared operation_id does not match the plan")
        if prepared.get("target_root") != plan.target_root_text:
            problems.append("prepared target_root does not match the plan")
        if prepared.get("source_root") != plan.source_root_text:
            problems.append("prepared source_root does not match the plan")
        if prepared.get("journal_root") != plan.journal_root_text:
            problems.append("prepared journal_root does not match the plan")
    if terminal is None:
        problems.append("journal has no terminal event")
    elif terminal.get("status") not in {
            "applied", "rolled_back", "partial", "preparation_failed",
            "failed_unchanged", "ambiguous", "aborted"}:
        problems.append("terminal status is unknown")
    for index in range(len(plan.files)):
        if index not in backup_records:
            problems.append(f"journal lacks backup_saved for index {index}")

    backups = [_verify_inspected_backup(operation, entry, backup_records[index], problems)
               for index, entry in enumerate(plan.files) if index in backup_records]
    report["backups"] = backups
    report["write_intents"] = [intents[index] for index in sorted(intents)]
    report["confirmed_writes"] = sum(1 for record in applied.values()
                                     if record.get("observed_identity") is not None)
    report["write_uncertainties"] = uncertainties
    report["rollback_results"] = [result for index in sorted(rollback_results)
                                  for result in rollback_results[index]]
    report["terminal"] = terminal
    current = report["files"]
    unresolved: list[dict[str, Any]] = []
    ownership_proven: list[bool] = []
    for index, entry in enumerate(plan.files):
        state = current[index]
        intent = intents.get(index)
        applied_record = applied.get(index)
        uncertain_for_index = any(record.get("index") == index for record in uncertainties)
        if intent is not None and applied_record is None and not uncertain_for_index:
            unresolved.append({"index": index, "path": entry.path})
        proven = False
        if applied_record is not None:
            if (state.get("classification") == "postimage"
                    and _identity_matches(applied_record.get("observed_identity"), state)):
                proven = True
        for result in rollback_results.get(index, []):
            if (result.get("status") == "restored"
                    and state.get("classification") == "preimage"
                    and _identity_matches(result.get("restored_identity"), state)):
                proven = True
        ownership_proven.append(proven)
    report["unresolved_write_intents"] = unresolved
    report["ownership_proven"] = ownership_proven

    report["evidence_problems"] = problems
    evidence_valid = not problems and not torn and bool(events) and terminal is not None
    report["evidence_valid"] = evidence_valid
    terminal_status = terminal.get("status") if terminal else None
    clean_applied = (terminal_status == "applied" and evidence_valid
                     and report["confirmed_writes"] == len(plan.files)
                     and all(state.get("classification") == "postimage" for state in current)
                     and all(ownership_proven) and not uncertainties)
    clean_rolled_back = (terminal_status == "rolled_back" and evidence_valid
                         and all(state.get("classification") == "preimage" for state in current)
                         and all(any(result.get("status") == "restored"
                                     and _identity_matches(result.get("restored_identity"),
                                                           current[index])
                                     for result in rollback_results.get(index, []))
                                 for index in applied)
                         and all(_identity_matches(result.get("restored_identity"),
                                                   current[index])
                                 for index, results in rollback_results.items()
                                 for result in results if result.get("status") == "restored"))
    clean_failed = (terminal_status in {"preparation_failed", "failed_unchanged"}
                    and evidence_valid
                    and not applied
                    and all(state.get("classification") == "preimage" for state in current))
    if not evidence_valid:
        status = "ambiguous"
    elif clean_applied:
        status = "applied"
    elif clean_rolled_back:
        status = "rolled_back"
    elif clean_failed:
        status = terminal_status
    elif terminal_status is None:
        status = "incomplete"
    elif terminal_status in {"applied", "rolled_back", "preparation_failed",
                             "failed_unchanged"}:
        status = "review_required"
    elif terminal_status == "partial":
        status = "partial"
    else:
        status = "ambiguous"
    report["status"] = status
    report["requires_main_review"] = status not in {
        "applied", "rolled_back", "preparation_failed", "failed_unchanged",
    }
    return report


def inspect(plan_path: Any, *, reviewed_plan_sha256: str) -> dict[str, Any]:
    """Return read-only recovery facts for the exact planned journal."""
    plan = _read_plan(plan_path, reviewed_plan_sha256)
    bound_plan_path = Path(_canonical_file_text(plan_path, "plan_path"))
    operation = Path(plan.journal_root_text) / plan.operation_id
    initial_problems: list[str] = []
    try:
        _resolve_roots(plan, bound_plan_path)
    except Exception as exc:
        initial_problems.append(
            f"reviewed plan roots are not currently safe: {type(exc).__name__}: {exc}")
    present = os.path.lexists(operation)
    if not present:
        report = _inspection_base(plan, operation, False)
        if initial_problems:
            report["status"] = "ambiguous"
            report["requires_main_review"] = True
            report["evidence_problems"] = initial_problems
        return report
    try:
        return _inspect_present(plan, operation, initial_problems)
    except Exception as exc:
        report = _inspection_base(plan, operation, True)
        report["status"] = "ambiguous"
        report["requires_main_review"] = True
        report["evidence_problems"] = initial_problems + [
            f"inspection failed: {type(exc).__name__}: {exc}",
        ]
        return report






_UNCERTAIN_STATUSES = {
    "write_uncertain", "rollback_uncertain", "uncertain_unrolled", "postcheck_failed",
}
_PARTIAL_STATUSES = {
    "applied", "protected_foreign_change", "protected_backup_corrupt", "rollback_failed",
}


def _build_apply_report(preflight: _Preflight, statuses: dict[str, str],
                        errors: list[dict[str, Any]], uncertain: list[dict[str, Any]],
                        requested_status: str, terminal_written: bool,
                        journal_healthy: bool) -> dict[str, Any]:
    targets = [_current_target_state(item) for item in preflight.files]
    status = requested_status
    if status == "applied":
        if not terminal_written or any(entry["classification"] != "postimage" for entry in targets):
            status = "ambiguous"
    elif status == "rolled_back":
        if any(entry["classification"] != "preimage" for entry in targets):
            status = "ambiguous"
    elif status == "failed_unchanged":
        if any(entry["classification"] != "preimage" for entry in targets):
            status = "ambiguous"
    if not terminal_written and status not in ("preparation_failed",):
        status = "ambiguous"
    targets_changed = any(entry["classification"] != "preimage" for entry in targets)
    uncertainty = any(value in _UNCERTAIN_STATUSES for value in statuses.values())
    uncertainty = uncertainty or bool(uncertain) or status == "ambiguous"
    requires_review = status not in ("applied", "rolled_back") or not terminal_written
    if status == "applied" and not journal_healthy:
        requires_review = True
    counts: dict[str, int] = {}
    for value in statuses.values():
        counts[value] = counts.get(value, 0) + 1
    return {
        "schema": SCHEMA,
        "status": status,
        "success": status == "applied",
        "all_or_nothing": (status in ("applied", "rolled_back")
                          and terminal_written and not uncertainty),
        "operation_id": preflight.plan.operation_id,
        "plan_sha256": preflight.plan.sha256,
        "reviewed_plan_sha256": preflight.plan.sha256,
        "journal_path": str(preflight.journal_path),
        "journal_healthy": journal_healthy,
        "terminal_written": terminal_written,
        "evidence_complete": terminal_written and journal_healthy,
        "file_statuses": [{"path": path, "status": value}
                          for path, value in sorted(statuses.items())],
        "status_counts": counts,
        "targets": targets,
        "targets_changed": targets_changed,
        "uncertain_writes": uncertain,
        "uncertain_outcome": uncertainty,
        "requires_main_review": requires_review,
        "errors": errors,
        "payload_snapshot": "immutable_preflight_bytes",
    }


def _execute_apply(preflight: _Preflight) -> dict[str, Any]:
    statuses = {item.plan.path: "not_attempted" for item in preflight.files}
    errors: list[dict[str, Any]] = []
    uncertain: list[dict[str, Any]] = []
    known: list[_KnownWrite] = []
    preparation = _Preparation()
    terminal_written = False
    requested_status = "preparation_failed"
    try:
        try:
            _prepare_transaction(preflight, preparation)
        except Exception as exc:
            errors.append(_error_record("preparation", exc))
            terminal_written = _append_terminal(
                preparation.journal, "preparation_failed", statuses, errors,
                targets_changed=False)
            if preparation.journal is not None and not terminal_written:
                requested_status = "ambiguous"
            return _build_apply_report(
                preflight, statuses, errors, uncertain, requested_status,
                terminal_written, bool(preparation.journal and preparation.journal.healthy))
        try:
            _perform_writes(preflight, preparation, statuses, errors, uncertain, known)
            terminal_written = _append_terminal(
                preparation.journal, "applied", statuses, errors,
                applied_files=len(known))
            if not terminal_written:
                raise OSError(errno.EIO, "applied terminal journal record was not durable")
            requested_status = "applied"
            return _build_apply_report(
                preflight, statuses, errors, uncertain, requested_status,
                terminal_written, bool(preparation.journal and preparation.journal.healthy))
        except Exception as exc:
            errors.append(_error_record("execution", exc))
            _rollback(preflight, preparation, known, statuses, errors)
            uncertain_now = any(value in _UNCERTAIN_STATUSES for value in statuses.values())
            partial_now = any(value in _PARTIAL_STATUSES for value in statuses.values())
            if uncertain_now:
                requested_status = "ambiguous"
            elif partial_now:
                requested_status = "partial"
            elif known and all(statuses[write.plan_file.path] == "rolled_back" for write in known):
                requested_status = "rolled_back"
            else:
                requested_status = "failed_unchanged"
            terminal_written = _append_terminal(
                preparation.journal, requested_status, statuses, errors,
                uncertain_writes=uncertain)
            return _build_apply_report(
                preflight, statuses, errors, uncertain, requested_status,
                terminal_written, bool(preparation.journal and preparation.journal.healthy))
        except BaseException as exc:
            errors.append(_error_record("aborted", exc))
            if preparation.journal is not None and preparation.journal.healthy:
                _append_terminal(preparation.journal, "aborted", statuses, errors,
                                 uncertain_writes=uncertain)
            raise
    finally:
        if preparation.journal is not None:
            preparation.journal.close()


def apply(plan_path: Any, *, reviewed_plan_sha256: str) -> dict[str, Any]:
    """Apply a fully preflighted plan while reporting every runtime outcome."""
    if os.name != "nt":
        raise UnsupportedPlatformError("apply is fail-closed outside Windows")
    plan = _read_plan(plan_path, reviewed_plan_sha256)
    bound_plan_path = Path(_canonical_file_text(plan_path, "plan_path"))
    initial_target, _source, _journal = _resolve_roots(plan, bound_plan_path)
    with _TargetMutex(initial_target):
        preflight = _preflight(plan, bound_plan_path, reject_existing_journal=True)
        if preflight.target_root.identity != initial_target.identity:
            raise ConcurrentChangeError("target root changed while acquiring exclusivity")
        return _execute_apply(preflight)
