"""Durable, event-driven delegation from one Astra to its local child pool."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import posixpath
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from .pool import InstancePool
from .protocol import Envelope, MessageKind, SourceKind

DEEPSEEK_ROUTE = "deepseek"
NATIVE_ROUTE = "gpt_native"
NATIVE_LEASE_SECONDS = 24 * 60 * 60
OWNERSHIP_ALL = "*"

_ADDED_COLUMNS = (
    ("work_id", "TEXT"),
    ("route", "TEXT NOT NULL DEFAULT 'deepseek'"),
    ("request_hash", "TEXT"),
    ("ownership_json", "TEXT"),
    ("lease_token", "TEXT"),
    ("native_agent_id", "TEXT"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ChildCoordinator:
    """The parent chooses assignments; the program waits and records results.

    A job is unique per (task_id, task_version, work_id) across both routes:
    an identical request is collapsed onto the existing job, while a different
    request that reuses the same work id is rejected. Interrupted, failed or
    cancelled jobs are never replayed automatically.
    """

    TERMINAL = frozenset({"completed", "failed", "cancelled", "interrupted"})

    def __init__(
        self, *, node_id: str, project_id: str, pool: InstancePool,
        state_path: str | Path,
    ):
        self.node_id = node_id
        self.project_id = project_id
        self.pool = pool
        path = Path(state_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS child_jobs (
                job_id TEXT PRIMARY KEY,
                instance_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                task_version INTEGER NOT NULL,
                instructions TEXT NOT NULL,
                status TEXT NOT NULL,
                result_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                work_id TEXT,
                route TEXT NOT NULL DEFAULT 'deepseek',
                request_hash TEXT,
                ownership_json TEXT,
                lease_token TEXT,
                native_agent_id TEXT
            );
            CREATE TABLE IF NOT EXISTS task_versions (
                task_id TEXT PRIMARY KEY,
                version INTEGER NOT NULL
            );
            """
        )
        self._migrate()
        # An earlier process may have died while work was reserved, queued or
        # running. Never replay such work without a fresh parent decision.
        self._db.execute(
            "UPDATE child_jobs SET status='interrupted', updated_at=? "
            "WHERE status IN ('reserved', 'queued', 'running')", (_now(),),
        )
        self._db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS child_jobs_work_unique "
            "ON child_jobs(task_id, task_version, work_id)"
        )
        self._db.commit()
        self._running: dict[str, asyncio.Task[None]] = {}
        self._changed = asyncio.Event()
        self.on_activity = lambda: None
        self._allocation_lock = asyncio.Lock()

    def _notify_changed(self):
        self._changed.set()
        self.on_activity()

    def _migrate(self) -> None:
        present = {row["name"] for row in
                   self._db.execute("PRAGMA table_info(child_jobs)")}
        for name, definition in _ADDED_COLUMNS:
            if name not in present:
                self._db.execute(
                    f"ALTER TABLE child_jobs ADD COLUMN {name} {definition}"
                )

    async def delegate(
        self, *, task_id: str, task_version: int, text: str,
        instance_id: str | None = None, auto_expand: bool = True,
        work_id: str | None = None, ownership: list[str] | None = None,
    ) -> dict:
        async with self._allocation_lock:
            return await self._delegate_locked(
                task_id=task_id, task_version=task_version, text=text,
                instance_id=instance_id, auto_expand=auto_expand,
                work_id=work_id, ownership=ownership,
            )

    async def _delegate_locked(
        self, *, task_id: str, task_version: int, text: str,
        instance_id: str | None, auto_expand: bool, work_id: str | None,
        ownership: list[str] | None,
    ) -> dict:
        self._validate_assignment(task_id, task_version, text)
        self._reject_stale(task_id, task_version)
        resolved_work_id = self._resolve_work_id(work_id, text)
        normalized_ownership = self._normalize_ownership(ownership)
        request_hash = self._request_hash(
            task_id, task_version, resolved_work_id, text, normalized_ownership,
        )
        existing = self._existing_assignment(
            task_id, task_version, resolved_work_id,
        )
        if existing is not None:
            return self._duplicate_result(existing, request_hash)
        self._ensure_ownership_free(normalized_ownership)
        if instance_id is None:
            standby = [item for item in self.pool.snapshot()["instances"]
                       if item["state"] == "standby"]
            if not standby and auto_expand:
                await self.pool.ensure_standby(
                    len(self.pool.snapshot()["instances"]) + 1,
                )
                standby = [item for item in self.pool.snapshot()["instances"]
                           if item["state"] == "standby"]
            if not standby:
                raise RuntimeError("no standby child; Astra may scale the pool")
            instance_id = standby[0]["instance_id"]
        else:
            matching = [item for item in self.pool.snapshot()["instances"]
                        if item["instance_id"] == instance_id]
            if not matching or matching[0]["state"] != "standby":
                raise RuntimeError("selected child is not standby")

        self.update_task_version(task_id, task_version)
        job_id = f"child-{uuid4().hex}"
        created_at = _now()
        # Claim the instance before yielding control so concurrent dispatches
        # cannot both select the same standby worker.
        await self.pool.reserve(instance_id)
        try:
            if self._is_stale(task_id, task_version):
                raise ValueError("stale child assignment task_version")
            # A native reservation can arrive while pool allocation yields.
            self._ensure_ownership_free(normalized_ownership)
            with self._db:
                self._db.execute(
                    "INSERT INTO child_jobs ("
                    "job_id, instance_id, task_id, task_version, instructions, "
                    "status, route, work_id, request_hash, ownership_json, "
                    "created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, ?)",
                    (job_id, instance_id, task_id, task_version, text,
                     DEEPSEEK_ROUTE, resolved_work_id, request_hash,
                     json.dumps(normalized_ownership), created_at, created_at),
                )
        except sqlite3.IntegrityError:
            await self.pool.return_to_standby(instance_id)
            raced = self._existing_assignment(
                task_id, task_version, resolved_work_id,
            )
            if raced is not None:
                return self._duplicate_result(raced, request_hash)
            raise
        except Exception:
            await self.pool.return_to_standby(instance_id)
            raise
        self._running[job_id] = asyncio.create_task(
            self._run(job_id, instance_id, task_id, task_version, text),
            name=job_id,
        )
        return {**self.job(job_id), "duplicate": False}
    @staticmethod
    def _validate_assignment(task_id: str, task_version: int, text: str) -> None:
        if (not isinstance(task_id, str) or not task_id.strip()
                or not isinstance(text, str) or not text.strip()
                or task_version < 1):
            raise ValueError(
                "task_id, positive task_version, and text are required"
            )

    def _latest_version(self, task_id: str) -> int | None:
        row = self._db.execute(
            "SELECT version FROM task_versions WHERE task_id=?", (task_id,),
        ).fetchone()
        return int(row["version"]) if row is not None else None

    def _is_stale(self, task_id: str, task_version: int) -> bool:
        latest = self._latest_version(task_id)
        return latest is not None and task_version < latest

    def _reject_stale(self, task_id: str, task_version: int) -> None:
        if self._is_stale(task_id, task_version):
            raise ValueError("stale child assignment task_version")

    @staticmethod
    def _normalize_text(text: str) -> str:
        return text.replace("\r\n", "\n").strip()

    @classmethod
    def _resolve_work_id(cls, work_id: str | None, text: str) -> str:
        if work_id is not None:
            if not isinstance(work_id, str) or not work_id.strip():
                raise ValueError("work_id must be a nonempty string")
            return work_id.strip()
        normalized = cls._normalize_text(text)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _request_hash(
        task_id: str, task_version: int, work_id: str, text: str,
        ownership: list[str],
    ) -> str:
        canonical = json.dumps(
            {
                "task_id": task_id,
                "task_version": task_version,
                "work_id": work_id,
                "text": ChildCoordinator._normalize_text(text),
                "ownership": sorted(ownership),
            },
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_ownership(ownership: list[str] | None) -> list[str]:
        if ownership is None:
            return []
        if isinstance(ownership, (str, bytes)) or not isinstance(
            ownership, (list, tuple, set, frozenset),
        ):
            raise ValueError(
                "ownership must be a list of project-relative paths"
            )
        normalized = []
        for raw in ownership:
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("ownership entries must be nonempty strings")
            item = raw.strip().replace("\\", "/")
            if item == OWNERSHIP_ALL:
                normalized.append(OWNERSHIP_ALL)
                continue
            if item.startswith("/") or re.match(r"^[A-Za-z]:", item):
                raise ValueError(
                    f"ownership path must be project-relative: {raw!r}"
                )
            item = posixpath.normpath(item)
            if item in {"", ".", ".."} or item.startswith("../"):
                raise ValueError(
                    f"ownership path must stay inside the project: {raw!r}"
                )
            normalized.append(item.casefold() if os.name == 'nt' else item)
        return sorted(set(normalized))

    @staticmethod
    def _ownership_overlaps(first: str, second: str) -> bool:
        if os.name == 'nt':
            first, second = first.casefold(), second.casefold()
        if first == OWNERSHIP_ALL or second == OWNERSHIP_ALL:
            return True
        return (first == second
                or first.startswith(second + "/")
                or second.startswith(first + "/"))

    def _ensure_ownership_free(self, ownership: list[str]) -> None:
        if not ownership:
            return
        rows = self._db.execute(
            "SELECT job_id, status, route, error, ownership_json FROM child_jobs "
            "WHERE ownership_json IS NOT NULL AND ownership_json != '[]'"
        ).fetchall()
        for row in rows:
            native_stop_unknown = (row['route'] == NATIVE_ROUTE and
                (row['status'] == 'interrupted' or row['error'] == 'native stop unconfirmed'))
            if row["status"] in self.TERMINAL and not native_stop_unknown:
                continue
            held = json.loads(row["ownership_json"])
            for path in ownership:
                for owner in held:
                    if self._ownership_overlaps(path, owner):
                        raise ValueError(
                            f"ownership conflict: {path!r} overlaps job "
                            f"{row['job_id']} holding {owner!r}"
                        )

    def _existing_assignment(
        self, task_id: str, task_version: int, work_id: str,
    ) -> sqlite3.Row | None:
        return self._db.execute(
            "SELECT * FROM child_jobs WHERE task_id=? AND task_version=? "
            "AND work_id=?",
            (task_id, task_version, work_id),
        ).fetchone()

    def _duplicate_result(self, row: sqlite3.Row, request_hash: str) -> dict:
        if row["request_hash"] != request_hash:
            raise ValueError(
                f"work_id {row['work_id']!r} already belongs to a different "
                f"request ({row['job_id']}); choose another work_id or text"
            )
        return {**self.job(row["job_id"]), "duplicate": True}

    async def scale(self, count: int) -> dict:
        async with self._allocation_lock:
            await self.pool.scale_to(count)
            return self.pool.snapshot()

    def update_task_version(self, task_id: str, version: int) -> None:
        if version < 1:
            raise ValueError("version must be positive")
        with self._db:
            self._db.execute(
                "INSERT INTO task_versions(task_id, version) VALUES (?, ?) "
                "ON CONFLICT(task_id) DO UPDATE SET version=max(version, excluded.version)",
                (task_id, version),
            )
        self._notify_changed()

    def job(self, job_id: str) -> dict:
        row = self._db.execute(
            "SELECT j.*, v.version AS latest_version FROM child_jobs j "
            "LEFT JOIN task_versions v ON v.task_id=j.task_id WHERE j.job_id=?",
            (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown child job: {job_id}")
        return {
            "job_id": row["job_id"],
            "instance_id": row["instance_id"],
            "task_id": row["task_id"],
            "task_version": row["task_version"],
            "route": row["route"] or DEEPSEEK_ROUTE,
            "work_id": row["work_id"],
            "ownership": (json.loads(row["ownership_json"])
                          if row["ownership_json"] else []),
            "native_agent_id": row["native_agent_id"],
            "status": row["status"],
            "terminal": row["status"] in self.TERMINAL,
            "stale": bool(row["latest_version"] and
                          row["latest_version"] > row["task_version"]),
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def status(self) -> dict:
        rows = self._db.execute(
            "SELECT job_id FROM child_jobs ORDER BY created_at, job_id"
        ).fetchall()
        return {"pool": self.pool.snapshot(),
                "jobs": [self.job(row["job_id"]) for row in rows]}

    async def wait(self, job_ids: list[str]) -> list[dict]:
        if not job_ids:
            raise ValueError("at least one job_id is required")
        while True:
            results = [self.job(job_id) for job_id in job_ids]
            if all(item["terminal"] for item in results):
                return results
            self._changed.clear()
            # The event and data are in the same process; check again after
            # clearing to avoid a completion between the check and wait.
            if all(self.job(job_id)["terminal"] for job_id in job_ids):
                continue
            await self._changed.wait()

    async def cancel(self, job_id: str) -> dict:
        job = self.job(job_id)
        task = self._running.get(job_id)
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        elif (job["route"] == NATIVE_ROUTE
              and job["status"] in {"reserved", "running"}):
            # The parent can only record the lease as cancelled; it cannot
            # confirm that a remote native child actually stopped.
            self._record(job_id, "cancelled", error=(
                'native stop unconfirmed' if job['status'] == 'running' else None))
        return self.job(job_id)

    async def cancel_all(self) -> list[dict]:
        return [await self.cancel(job_id) for job_id in list(self._running)]

    async def close(self) -> None:
        await self.cancel_all()
        self._db.close()

    async def _run(
        self, job_id: str, instance_id: str, task_id: str,
        task_version: int, text: str,
    ) -> None:
        self._record(job_id, "running")
        message = Envelope(
            message_id=job_id,
            project_id=self.project_id,
            sender=f"{self.node_id}/Astra-{self.node_id}",
            recipient=f"{self.node_id}/DeepSeek-{self.node_id}",
            task_id=task_id,
            task_version=task_version,
            sent_at=datetime.now(timezone.utc),
            kind=MessageKind.DELEGATION,
            source=SourceKind.ASTRA,
            payload={"text": text},
            correlation_id=job_id,
        )
        try:
            result = await self.pool.wake(instance_id, message)
            self._record(job_id, "completed" if result.accepted else "failed",
                         result=result.output)
        except asyncio.CancelledError:
            self._record(job_id, "cancelled")
            raise
        except Exception as exc:  # noqa: BLE001 - persisted for parent review
            self._record(job_id, "failed", error=f"{type(exc).__name__}: {exc}")
        finally:
            await self.pool.return_to_standby(instance_id)
            self._running.pop(job_id, None)
            self._notify_changed()

    def _record(
        self, job_id: str, status: str, *, result: dict | None = None,
        error: str | None = None,
    ) -> None:
        with self._db:
            self._db.execute(
                "UPDATE child_jobs SET status=?, result_json=?, error=?, "
                "updated_at=? WHERE job_id=?",
                (status, json.dumps(result, ensure_ascii=False) if result is not None
                 else None, error, _now(), job_id),
            )
        self._notify_changed()

    # -- GPT native leases --------------------------------------------------

    def native_reserve(
        self, *, task_id: str, task_version: int, text: str,
        work_id: str | None = None, ownership: list[str] | None = None,
        reason: str,
    ) -> dict:
        """Reserve one shared execution lease for a special GPT-native task.

        DeepSeek Flash at max reasoning stays the priority route; native work
        needs a nonempty reason that justifies the special capability. The
        returned lease token is the only copy the parent gets, and it must be
        handed to the native child that validates and completes the job.
        """
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(
                "native_reserve requires a nonempty reason for the special "
                "GPT native capability"
            )
        self._validate_assignment(task_id, task_version, text)
        self._reject_stale(task_id, task_version)
        resolved_work_id = self._resolve_work_id(work_id, text)
        normalized_ownership = self._normalize_ownership(ownership)
        request_hash = self._request_hash(
            task_id, task_version, resolved_work_id, text, normalized_ownership,
        )
        existing = self._existing_assignment(
            task_id, task_version, resolved_work_id,
        )
        if existing is not None:
            duplicate = self._duplicate_result(existing, request_hash)
            duplicate["lease_token"] = None
            return duplicate
        self._ensure_ownership_free(normalized_ownership)
        self.update_task_version(task_id, task_version)
        job_id = f"child-{uuid4().hex}"
        created_at = _now()
        lease_token = secrets.token_urlsafe(32)
        try:
            with self._db:
                self._db.execute(
                    "INSERT INTO child_jobs ("
                    "job_id, instance_id, task_id, task_version, instructions, "
                    "status, route, work_id, request_hash, ownership_json, "
                    "lease_token, created_at, updated_at) "
                    "VALUES (?, '', ?, ?, ?, 'reserved', ?, ?, ?, ?, ?, ?, ?)",
                    (job_id, task_id, task_version, text, NATIVE_ROUTE,
                     resolved_work_id, request_hash,
                     json.dumps(normalized_ownership), lease_token,
                     created_at, created_at),
                )
        except sqlite3.IntegrityError:
            raced = self._existing_assignment(
                task_id, task_version, resolved_work_id,
            )
            if raced is not None:
                duplicate = self._duplicate_result(raced, request_hash)
                duplicate["lease_token"] = None
                return duplicate
            raise
        self._notify_changed()
        return {**self.job(job_id), "duplicate": False,
                "lease_token": lease_token}

    def native_validate(
        self, *, job_id: str, lease_token: str, agent_id: str | None = None,
    ) -> dict:
        """Check a lease before native work and bind the child agent once."""
        row = self._native_row(job_id)
        self._check_lease(row, lease_token)
        if agent_id is not None and (not isinstance(agent_id, str)
                                     or not agent_id.strip()):
            raise ValueError("agent_id must be a nonempty string")
        bound = row["native_agent_id"]
        if agent_id is not None and bound is not None and bound != agent_id:
            raise ValueError(
                f"native job {job_id} is already bound to another agent id"
            )
        new_agent = agent_id if agent_id is not None else bound
        if new_agent is not None and (row["status"] == "reserved" or new_agent != bound):
            with self._db:
                self._db.execute(
                    "UPDATE child_jobs SET status='running', native_agent_id=?, "
                    "updated_at=? WHERE job_id=?",
                    (new_agent, _now(), job_id),
                )
            self._notify_changed()
            row = self._db.execute(
                "SELECT * FROM child_jobs WHERE job_id=?", (job_id,),
            ).fetchone()
        return {
            "job_id": row["job_id"],
            "task_id": row["task_id"],
            "task_version": row["task_version"],
            "work_id": row["work_id"],
            "route": NATIVE_ROUTE,
            "status": row["status"],
            "native_agent_id": row["native_agent_id"],
            "execution_allowed": row['status'] == 'running' and row['native_agent_id'] is not None,
        }

    def native_complete(
        self, *, job_id: str, lease_token: str, text: str,
        error: str | None = None,
    ) -> dict:
        """Bind the immutable terminal result of a native lease."""
        row = self._native_row(job_id)
        self._check_token(row, lease_token)
        if row['status'] in {'cancelled', 'interrupted'} and error == 'cancelled':
            if not text.strip():
                raise ValueError('actual stop confirmation evidence is required')
            self._record(job_id, 'cancelled', error='native stop confirmed', result={'text': text})
            return self.job(job_id)
        self._reject_stale(row['task_id'], row['task_version'])
        if row["status"] == "completed":
            stored = (json.loads(row["result_json"])
                      if row["result_json"] else {})
            if error is None and stored.get("text") == text:
                return {**self.job(job_id), "duplicate": True}
            raise ValueError(
                f"native job {job_id} is already completed with a different "
                f"result"
            )
        if self._lease_expired(row):
            raise ValueError("native lease expired")
        if row['status'] == 'reserved' and error is None:
            raise ValueError('native_validate with agent_id is required before completion')
        if row["status"] not in {"reserved", "running"}:
            raise ValueError(
                f"native lease is no longer active ({row['status']})"
            )
        if not isinstance(text, str):
            raise ValueError("text must be a string")
        if error is None and not text.strip():
            raise ValueError(
                "text is required for a successful native completion"
            )
        if error is not None and not isinstance(error, str):
            raise ValueError("error must be a string")
        if error is not None:
            self._record(job_id, "failed", error=error)
        else:
            self._record(job_id, "completed", result={
                "text": text,
                "native_agent_id": row["native_agent_id"],
            })
        return {**self.job(job_id), "duplicate": False}

    def _native_row(self, job_id: str) -> sqlite3.Row:
        row = self._db.execute(
            "SELECT * FROM child_jobs WHERE job_id=?", (job_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown child job: {job_id}")
        route = row["route"] or DEEPSEEK_ROUTE
        if route != NATIVE_ROUTE:
            raise ValueError(
                f"native lease route mismatch: job {job_id} belongs to "
                f"route {route!r}"
            )
        return row

    @staticmethod
    def _check_token(row: sqlite3.Row, lease_token: str) -> None:
        stored = row["lease_token"]
        provided = lease_token if isinstance(lease_token, str) else ""
        if not stored or not secrets.compare_digest(
            stored.encode("utf-8"), provided.encode("utf-8"),
        ):
            raise PermissionError("invalid native lease token")

    def _check_lease(self, row: sqlite3.Row, lease_token: str) -> None:
        self._check_token(row, lease_token)
        self._reject_stale(row['task_id'], row['task_version'])
        if row["status"] not in {"reserved", "running"}:
            raise ValueError(
                f"native lease is no longer active ({row['status']})"
            )
        if self._lease_expired(row):
            raise ValueError("native lease expired")

    @staticmethod
    def _lease_expired(row: sqlite3.Row) -> bool:
        try:
            updated = datetime.fromisoformat(
                str(row["updated_at"]).replace("Z", "+00:00")
            )
        except ValueError:
            return False
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - updated
                > timedelta(seconds=NATIVE_LEASE_SECONDS))

class LocalControlServer:
    """Authenticated loopback socket owned by the node process."""

    def __init__(
        self, coordinator: ChildCoordinator, *, token: str,
        discovery_path: str | Path | None = None,
    ):
        if not token:
            raise ValueError("a private control token is required")
        self.coordinator = coordinator
        self.token = token
        self.discovery_path = Path(discovery_path) if discovery_path else None
        self._server: asyncio.AbstractServer | None = None
        self.port: int | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle, host="127.0.0.1", port=0, limit=1 << 20,
        )
        self.port = self._server.sockets[0].getsockname()[1]
        if self.discovery_path is not None:
            self.discovery_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.discovery_path.with_suffix(".tmp")
            temporary.write_text(json.dumps({
                "host": "127.0.0.1", "port": self.port,
                "token": self.token, "pid": os.getpid(),
            }), encoding="utf-8")
            os.replace(temporary, self.discovery_path)

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self.discovery_path is not None and self.discovery_path.exists():
            try:
                current = json.loads(self.discovery_path.read_text(encoding="utf-8"))
                if current.get("token") == self.token:
                    self.discovery_path.unlink()
            except (OSError, ValueError):
                pass

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
    ) -> None:
        try:
            request = json.loads(await reader.readline())
            if not secrets.compare_digest(str(request.get("token", "")), self.token):
                raise PermissionError("invalid local control token")
            action = request.get("action")
            args = request.get("arguments", {})
            if not isinstance(args, dict):
                raise ValueError("arguments must be an object")
            if action == "status":
                result = self.coordinator.status()
            elif action == "scale":
                result = await self.coordinator.scale(int(args["count"]))
            elif action == "delegate":
                result = await self.coordinator.delegate(
                    task_id=str(args["task_id"]),
                    task_version=int(args["task_version"]),
                    text=str(args["text"]),
                    instance_id=args.get("instance_id"),
                    auto_expand=bool(args.get("auto_expand", True)),
                    work_id=args.get("work_id"),
                    ownership=args.get("ownership"),
                )
            elif action == "job":
                result = self.coordinator.job(str(args["job_id"]))
            elif action == "wait":
                result = await self.coordinator.wait(list(args["job_ids"]))
            elif action == "cancel":
                result = await self.coordinator.cancel(str(args["job_id"]))
            elif action == "native_reserve":
                result = self.coordinator.native_reserve(
                    task_id=str(args["task_id"]),
                    task_version=int(args["task_version"]),
                    text=str(args["text"]),
                    work_id=args.get("work_id"),
                    ownership=args.get("ownership"),
                    reason=str(args["reason"]),
                )
            elif action == "native_validate":
                result = self.coordinator.native_validate(
                    job_id=str(args["job_id"]),
                    lease_token=str(args["lease_token"]),
                    agent_id=args.get("agent_id"),
                )
            elif action == "native_complete":
                result = self.coordinator.native_complete(
                    job_id=str(args["job_id"]),
                    lease_token=str(args["lease_token"]),
                    text=str(args["text"]),
                    error=args.get("error"),
                )
            elif action == "task_version":
                self.coordinator.update_task_version(
                    str(args["task_id"]), int(args["version"]),
                )
                result = {"updated": True}
            else:
                raise ValueError("unknown local control action")
            response = {"result": result}
        except Exception as exc:  # noqa: BLE001 - return a bounded protocol error
            response = {"error": {"type": type(exc).__name__,
                                  "message": str(exc)[:300]}}
        try:
            writer.write((json.dumps(response, ensure_ascii=False) + "\n").encode())
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


class LocalControlClient:
    def __init__(self, *, host: str, port: int, token: str):
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("control client may only connect to loopback")
        self.host = host
        self.port = port
        self.token = token

    @classmethod
    def from_discovery_file(cls, path: str | Path) -> "LocalControlClient":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(host=str(data["host"]), port=int(data["port"]),
                   token=str(data["token"]))

    async def call(self, action: str, arguments: dict) -> object:
        reader, writer = await asyncio.open_connection(
            self.host, self.port, limit=1 << 20,
        )
        try:
            payload = {"token": self.token, "action": action,
                       "arguments": arguments}
            writer.write((json.dumps(payload, ensure_ascii=False) + "\n").encode())
            await writer.drain()
            line = await reader.readline()
            if not line:
                raise ConnectionError("local control connection closed")
            response = json.loads(line)
            if "error" in response:
                error = response["error"]
                if error["type"] == "PermissionError":
                    raise PermissionError(error["message"])
                if error["type"] == "KeyError":
                    raise KeyError(error["message"])
                raise RuntimeError(error["message"])
            return response["result"]
        finally:
            writer.close()
            await writer.wait_closed()


class LocalControlFileClient:
    """Resolve the latest loopback endpoint at call time across restarts."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    async def call(self, action: str, arguments: dict) -> object:
        return await LocalControlClient.from_discovery_file(self.path).call(
            action, arguments,
        )
