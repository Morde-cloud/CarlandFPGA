"""Focused, offline tests for fpga_mesh.local_patch_transaction.

Every fixture is created below the process TMP/TEMP directory. The tests use
real filesystem operations and real Windows objects where the host supports
them; monkeypatches are limited to deterministic fault/race injection.
"""
from __future__ import annotations

import ast
import contextlib
import ctypes
import errno
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

WORKTREE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT))
sys.dont_write_bytecode = True

import fpga_mesh.local_patch_transaction as lpt


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def image(payload: bytes) -> dict:
    return {"size": len(payload), "sha256": sha(payload)}


def snapshot_tree(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
        rel = path.relative_to(root).as_posix()
        st = path.stat(follow_symlinks=False)
        if path.is_dir():
            result[rel] = ("dir", st.st_mtime_ns, st.st_ino)
        elif path.is_file():
            payload = path.read_bytes()
            result[rel] = ("file", sha(payload), len(payload), st.st_mtime_ns, st.st_ino)
        else:
            result[rel] = ("other", st.st_mode, st.st_mtime_ns)
    return result


def file_id(path: Path) -> tuple[int, int]:
    st = path.stat(follow_symlinks=False)
    return st.st_dev, st.st_ino


def same_path(left, right) -> bool:
    return (os.path.normcase(os.path.abspath(str(left)))
            == os.path.normcase(os.path.abspath(str(right))))


class Scene:
    def __init__(self, root: Path, operation_id: str = "offline-transaction-v1"):
        self.root = root
        self.target_root = root / "target"
        self.source_root = root / "source"
        self.journal_root = root / "journal"
        self.plan_path = root / "plan.json"
        self.operation_id = operation_id
        for directory in (self.target_root, self.source_root, self.journal_root):
            directory.mkdir(parents=True)
        self.files = []

    def add(self, target: str, pre: bytes, post: bytes, source: str | None = None):
        source = source or f"payload-{len(self.files)}.bin"
        target_path = self.target_root / target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(pre)
        source_path = self.source_root / source
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(post)
        self.files.append({
            "path": target,
            "source": source,
            "preimage": image(pre),
            "postimage": image(post),
            "_pre": pre,
            "_post": post,
            "_target": target_path,
            "_source": source_path,
        })
        return target_path

    def plan(self, **changes) -> dict:
        value = {
            "schema": 1,
            "operation_id": self.operation_id,
            "target_root": str(self.target_root),
            "source_root": str(self.source_root),
            "journal_root": str(self.journal_root),
            "files": [{key: entry[key] for key in
                       ("path", "source", "preimage", "postimage")}
                      for entry in self.files],
        }
        value.update(changes)
        return value

    def write_plan(self, value: dict | bytes | None = None) -> tuple[bytes, str]:
        if value is None:
            raw = json.dumps(self.plan(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        elif isinstance(value, bytes):
            raw = value
        else:
            raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.plan_path.write_bytes(raw)
        return raw, sha(raw)

    @property
    def operation_dir(self) -> Path:
        return self.journal_root / self.operation_id


class LocalPatchTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="local-patch-transaction-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.scenes = 0

    def scene(self, operation_id: str = "offline-transaction-v1") -> Scene:
        self.scenes += 1
        root = self.base / f"scene-{self.scenes}"
        root.mkdir()
        return Scene(root, operation_id)

    def subprocess_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["TMP"] = str(self.base)
        env["TEMP"] = str(self.base)
        return env

    def apply(self, scene: Scene, raw: bytes, digest: str, **kwargs):
        return lpt.apply(scene.plan_path, reviewed_plan_sha256=digest, **kwargs)

    def assert_target_bytes(self, scene: Scene):
        for entry in scene.files:
            self.assertEqual(entry["_target"].read_bytes(), entry["_post"])

    def assert_original_bytes(self, scene: Scene):
        for entry in scene.files:
            self.assertEqual(entry["_target"].read_bytes(), entry["_pre"])

    def assert_preflight_rejected(self, action, pattern: str = ""):
        with self.assertRaises(lpt.ValidationError) as caught:
            action()
        if pattern:
            self.assertRegex(str(caught.exception), pattern)
        return caught.exception

    def journal_events(self, scene: Scene) -> list[dict]:
        path = scene.operation_dir / "events.jsonl"
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        previous = "0" * 64
        for expected, record in enumerate(records, 1):
            self.assertEqual(record["seq"], expected)
            self.assertEqual(record["prev"], previous)
            unsigned = {key: value for key, value in record.items() if key != "checksum"}
            canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode("utf-8")
            self.assertEqual(record["checksum"], sha(canonical))
            previous = record["checksum"]
        return records

    def test_exact_two_and_three_file_success_binary_crlf_and_read_only_inspect(self):
        scene = self.scene()
        scene.add("fpga_mesh/alpha.py", b"old\r\ntext\r\n", b"new\r\npayload\r\n")
        scene.add("fpga_mesh/beta.py", b"\x00old\xff", b"\x00new\xfe\x01")
        scene.add("tests/test_feature.py", b"old = 1\n", b"new = 2\n")
        raw, digest = scene.write_plan()
        before = snapshot_tree(scene.root)

        summary = lpt.dry_run(scene.plan_path, reviewed_plan_sha256=digest)
        self.assertEqual(summary["status"], "valid")
        self.assertTrue(summary["apply_eligible"])
        self.assertFalse(scene.operation_dir.exists())
        self.assertEqual(snapshot_tree(scene.root), before)

        report = self.apply(scene, raw, digest)
        self.assertEqual(report["status"], "applied")
        self.assertTrue(report["success"])
        self.assertTrue(report["all_or_nothing"])
        self.assertFalse(report["uncertain_outcome"])
        self.assertFalse(report["requires_main_review"])
        self.assert_target_bytes(scene)
        self.assertEqual((scene.operation_dir / "approved-plan.json").read_bytes(), raw)
        for index, entry in enumerate(scene.files):
            backup = scene.operation_dir / "backups" / f"{index:04d}.backup"
            self.assertEqual(backup.read_bytes(), entry["_pre"])

        events = self.journal_events(scene)
        self.assertEqual(events[-1]["type"], "terminal")
        self.assertEqual(events[-1]["status"], "applied")
        self.assertEqual(sum(1 for event in events if event["type"] == "applied"), 3)

        after_apply = snapshot_tree(scene.root)
        inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
        self.assertEqual(inspected["status"], "applied")
        self.assertFalse(inspected["requires_main_review"])
        self.assertEqual(inspected["confirmed_writes"], 3)
        self.assertEqual(snapshot_tree(scene.root), after_apply)

    def test_plan_preimage_source_hash_and_size_fail_before_any_write(self):
        cases = ("plan-hash", "preimage", "pre-size", "source")
        for case in cases:
            with self.subTest(case=case):
                scene = self.scene(f"invalid-{case}")
                scene.add("fpga_mesh/alpha.py", b"old\r\n", b"new\r\n")
                value = scene.plan()
                if case == "preimage":
                    value["files"][0]["preimage"]["sha256"] = "1" * 64
                elif case == "pre-size":
                    value["files"][0]["preimage"]["size"] += 1
                elif case == "source":
                    value["files"][0]["postimage"]["sha256"] = "2" * 64
                raw, digest = scene.write_plan(value)
                before = snapshot_tree(scene.root)
                if case == "plan-hash":
                    self.assert_preflight_rejected(
                        lambda: self.apply(scene, raw, "0" * 64), "digest|plan")
                else:
                    self.assert_preflight_rejected(lambda: self.apply(scene, raw, digest))
                self.assertFalse(scene.operation_dir.exists())
                self.assertEqual(snapshot_tree(scene.root), before)

    def test_strict_schema_types_limits_and_unsafe_paths_fail_closed(self):
        scene = self.scene("strict")
        scene.add("fpga_mesh/alpha.py", b"old", b"new")
        scene.add("tests/test_beta.py", b"before", b"after")
        base = scene.plan()
        variants = {}
        value = json.loads(json.dumps(base)); value["unknown"] = 1; variants["unknown-key"] = value
        value = json.loads(json.dumps(base)); value["schema"] = True; variants["bool-schema"] = value
        value = json.loads(json.dumps(base)); value["files"] = []; variants["empty-files"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["postimage"]["size"] = True
        variants["bool-size"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["postimage"]["size"] = lpt.MAX_FILE_BYTES + 1
        variants["oversize"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["preimage"]["extra"] = 1
        variants["image-extra"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["preimage"] = value["files"][0]["postimage"].copy()
        variants["no-op"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "../escape.py"
        variants["traversal"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "fpga_mesh\\alpha.py"
        variants["backslash"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "fpga_mesh/alpha.py:ads"
        variants["ads"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "fpga_mesh/CON.py"
        variants["reserved"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["source"] = "PAYLO~1.BIN"
        variants["short-alias"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["source"] = "payload.bin."
        variants["trailing-dot"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["source"] = "/absolute.bin"
        variants["absolute-source"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "FPGA_MESH/alpha.py"
        variants["case-duplicate"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "fpga_mesh/.hidden.py"
        variants["leading-dot-target"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "fpga_mesh/*.py"
        variants["wildcard-target"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "fpga_mesh/1alpha.py"
        variants["invalid-module-name"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "tests/test-beta.py"
        variants["invalid-test-name"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "fpga_mesh/config.py"
        variants["denied-config"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "fpga_mesh/credentials.py"
        variants["denied-credential"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "fpga_mesh/launcher.py"
        variants["denied-launcher"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "fpga_mesh/owner.py"
        variants["denied-owner"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "fpga_mesh/agents.py"
        variants["denied-agents"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["path"] = "fpga_mesh/database.py"
        variants["denied-database"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["source"] = ".hidden.bin"
        variants["hidden-source"] = value
        value = json.loads(json.dumps(base)); value["files"][0]["source"] = "*.bin"
        variants["wildcard-source"] = value
        for name, variant in variants.items():
            with self.subTest(case=name):
                raw, digest = scene.write_plan(variant)
                before = snapshot_tree(scene.root)
                self.assert_preflight_rejected(lambda: self.apply(scene, raw, digest))
                self.assertFalse(scene.operation_dir.exists())
                self.assertEqual(snapshot_tree(scene.root), before)
        raw = json.dumps(base, separators=(",", ":")).encode("utf-8")
        duplicate = raw.replace(b'"schema":1', b'"schema":1,"schema":1', 1)
        scene.plan_path.write_bytes(duplicate)
        self.assert_preflight_rejected(lambda: self.apply(scene, duplicate, sha(duplicate)),
                                       "duplicate")
        self.assertFalse(scene.operation_dir.exists())

    def test_each_replacement_index_before_and_after_replace_is_honest(self):
        for index in (0, 1):
            for mode in ("before", "after"):
                with self.subTest(index=index, mode=mode):
                    scene = self.scene(f"replace-{index}-{mode}")
                    scene.add("fpga_mesh/alpha.py", b"alpha-old", b"alpha-new")
                    scene.add("tests/test_beta.py", b"beta-old", b"beta-new")
                    raw, digest = scene.write_plan()
                    failed_target = scene.files[index]["_target"]
                    real_replace = os.replace
                    state = {"triggered": False}

                    def injected_replace(source, destination):
                        if (not state["triggered"]
                                and os.path.normcase(os.path.abspath(str(destination)))
                                == os.path.normcase(os.path.abspath(str(failed_target)))):
                            state["triggered"] = True
                            if mode == "before":
                                raise OSError(errno.ENOSPC, "injected ENOSPC before target replace")
                            real_replace(source, destination)
                            raise OSError(errno.EIO, "injected EIO after real target replace")
                        return real_replace(source, destination)

                    with mock.patch.object(lpt.os, "replace", side_effect=injected_replace):
                        report = self.apply(scene, raw, digest)
                    self.assertTrue(state["triggered"])
                    self.assertFalse(report["success"])
                    self.assertEqual(report["status"], "ambiguous")
                    self.assertTrue(report["requires_main_review"])
                    for file_index, entry in enumerate(scene.files):
                        expected = entry["_post"] if (mode == "after" and file_index == index) else entry["_pre"]
                        self.assertEqual(entry["_target"].read_bytes(), expected)
                    inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
                    self.assertEqual(inspected["status"], "ambiguous")
                    self.assertTrue(inspected["requires_main_review"])

    def test_injected_backup_initial_log_payload_and_intent_failures_prevent_target_writes(self):
        cases = ("backup", "initial-log", "payload-temp", "write-intent")
        for case in cases:
            with self.subTest(case=case):
                scene = self.scene(f"fault-{case}")
                scene.add("fpga_mesh/alpha.py", b"old", b"new")
                raw, digest = scene.write_plan()
                before = snapshot_tree(scene.root)
                if case == "backup":
                    real_write = lpt._write_exclusive_file

                    def fail_write(path, payload):
                        if Path(path).parent.name == "backups":
                            raise OSError(errno.ENOSPC, "injected backup ENOSPC")
                        return real_write(path, payload)

                    patcher = mock.patch.object(lpt, "_write_exclusive_file", side_effect=fail_write)
                elif case == "initial-log":
                    real_append = lpt._Journal.append

                    def fail_append(journal, record_type, **fields):
                        if record_type == "plan_bound":
                            journal.healthy = False
                            raise OSError(errno.ENOSPC, "injected initial-log ENOSPC")
                        return real_append(journal, record_type, **fields)

                    patcher = mock.patch.object(lpt._Journal, "append", autospec=True,
                                                side_effect=fail_append)
                elif case == "payload-temp":
                    patcher = mock.patch.object(
                        lpt, "_write_temp_sibling",
                        side_effect=OSError(errno.ENOSPC, "injected payload-temp ENOSPC"))
                else:
                    real_append = lpt._Journal.append

                    def fail_append(journal, record_type, **fields):
                        if record_type == "write_intent":
                            journal.healthy = False
                            raise OSError(errno.ENOSPC, "injected write-intent ENOSPC")
                        return real_append(journal, record_type, **fields)

                    patcher = mock.patch.object(lpt._Journal, "append", autospec=True,
                                                side_effect=fail_append)
                with patcher:
                    report = self.apply(scene, raw, digest)
                self.assertFalse(report["success"])
                self.assertIn(report["status"], {"preparation_failed", "failed_unchanged", "ambiguous"})
                self.assertFalse(report["targets_changed"])
                self.assertEqual(scene.files[0]["_target"].read_bytes(), scene.files[0]["_pre"])
                self.assertTrue(any("injected" in str(item) for item in report["errors"]))
                inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
                self.assertFalse(inspected["mutates_state"])

    def test_postwrite_log_failure_does_not_perform_unjournaled_rollback(self):
        scene = self.scene("postwrite-log")
        scene.add("fpga_mesh/alpha.py", b"old", b"new")
        raw, digest = scene.write_plan()
        real_append = lpt._Journal.append

        def fail_append(journal, record_type, **fields):
            if record_type == "applied":
                journal.healthy = False
                raise OSError(errno.EIO, "injected postwrite-log EIO")
            return real_append(journal, record_type, **fields)

        with mock.patch.object(lpt._Journal, "append", autospec=True, side_effect=fail_append):
            report = self.apply(scene, raw, digest)
        self.assertFalse(report["success"])
        self.assertEqual(report["status"], "ambiguous")
        self.assertEqual(scene.files[0]["_target"].read_bytes(), scene.files[0]["_post"])
        self.assertTrue(report["targets_changed"])
        self.assertTrue(report["requires_main_review"])

    def test_rollback_intent_temp_and_replace_failures_stop_only_unsafe_work(self):
        for case in ("rollback-intent", "rollback-temp", "rollback-replace"):
            with self.subTest(case=case):
                scene = self.scene(f"fault-{case}")
                scene.add("fpga_mesh/alpha.py", b"alpha-old", b"alpha-new")
                scene.add("tests/test_beta.py", b"beta-old", b"beta-new")
                raw, digest = scene.write_plan()
                first_target = scene.files[0]["_target"]
                second_target = scene.files[1]["_target"]
                real_replace = os.replace
                real_temp = lpt._write_temp_sibling
                triggered = {"second": False, "temp_calls": 0}

                def replace_hook(source, destination):
                    destination = os.path.normcase(os.path.abspath(str(destination)))
                    second = os.path.normcase(os.path.abspath(str(second_target)))
                    first = os.path.normcase(os.path.abspath(str(first_target)))
                    if destination == second and not triggered["second"]:
                        triggered["second"] = True
                        raise OSError(errno.ENOSPC, "injected second-target ENOSPC")
                    if (case == "rollback-replace" and destination == first
                            and "local-patch-rollback-" in Path(source).name):
                        raise OSError(errno.EACCES, "injected rollback replace EACCES")
                    return real_replace(source, destination)

                def temp_hook(target, payload, *, tag):
                    triggered["temp_calls"] += 1
                    if case == "rollback-temp" and triggered["temp_calls"] == 3:
                        raise OSError(errno.ENOSPC, "injected rollback-temp ENOSPC")
                    return real_temp(target, payload, tag=tag)

                real_append = lpt._Journal.append

                def append_hook(journal, record_type, **fields):
                    if case == "rollback-intent" and record_type == "rollback_intent":
                        journal.healthy = False
                        raise OSError(errno.EIO, "injected rollback-intent EIO")
                    return real_append(journal, record_type, **fields)

                with mock.patch.object(lpt.os, "replace", side_effect=replace_hook), \
                        mock.patch.object(lpt, "_write_temp_sibling", side_effect=temp_hook), \
                        mock.patch.object(lpt._Journal, "append", autospec=True,
                                          side_effect=append_hook):
                    report = self.apply(scene, raw, digest)
                self.assertTrue(triggered["second"])
                self.assertFalse(report["success"])
                self.assertEqual(report["status"], "ambiguous")
                self.assertEqual(scene.files[0]["_target"].read_bytes(), scene.files[0]["_post"])
                self.assertEqual(scene.files[1]["_target"].read_bytes(), scene.files[1]["_pre"])
                self.assertTrue(report["requires_main_review"])
                self.assertIn("rollback", " ".join(item["phase"] for item in report["errors"]))

    def test_foreign_same_bytes_and_corrupt_backup_are_preserved_during_partial_rollback(self):
        for case in ("foreign-bytes", "same-bytes-foreign", "corrupt-backup"):
            with self.subTest(case=case):
                scene = self.scene(f"rollback-{case}")
                scene.add("fpga_mesh/alpha.py", b"alpha-old", b"alpha-new")
                scene.add("tests/test_beta.py", b"beta-old", b"beta-new")
                raw, digest = scene.write_plan()
                first_target = scene.files[0]["_target"]
                second_target = scene.files[1]["_target"]
                real_replace = os.replace
                real_temp = lpt._write_temp_sibling
                triggered = {"value": False}

                def fail_second_and_modify_first(target, payload, *, tag):
                    target_text = os.path.normcase(os.path.abspath(str(target)))
                    if (target_text == os.path.normcase(os.path.abspath(str(second_target)))
                            and not triggered["value"]):
                        triggered["value"] = True
                        if case == "foreign-bytes":
                            first_target.write_bytes(b"foreign-change")
                        elif case == "same-bytes-foreign":
                            swap = first_target.parent / "foreign-swap.tmp"
                            swap.write_bytes(scene.files[0]["_post"])
                            real_replace(swap, first_target)
                        else:
                            (scene.operation_dir / "backups" / "0000.backup").write_bytes(b"corrupt")
                        raise OSError(errno.ENOSPC, "injected failure after first applied file")
                    return real_temp(target, payload, tag=tag)

                with mock.patch.object(lpt, "_write_temp_sibling",
                                       side_effect=fail_second_and_modify_first):
                    report = self.apply(scene, raw, digest)
                self.assertTrue(triggered["value"])
                self.assertEqual(report["status"], "partial")
                self.assertTrue(report["requires_main_review"])
                self.assertEqual(scene.files[1]["_target"].read_bytes(), scene.files[1]["_pre"])
                if case == "foreign-bytes":
                    self.assertEqual(first_target.read_bytes(), b"foreign-change")
                elif case == "same-bytes-foreign":
                    self.assertEqual(first_target.read_bytes(), scene.files[0]["_post"])
                    events = self.journal_events(scene)
                    applied = next(event for event in events
                                   if event["type"] == "applied" and event["index"] == 0)
                    self.assertNotEqual(file_id(first_target),
                                        (applied["observed_identity"]["device"],
                                         applied["observed_identity"]["file_id"]))
                else:
                    self.assertEqual(first_target.read_bytes(), scene.files[0]["_post"])
                    self.assertEqual((scene.operation_dir / "backups" / "0000.backup").read_bytes(),
                                     b"corrupt")
                inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
                self.assertTrue(inspected["requires_main_review"])
                self.assertFalse(inspected["mutates_state"])

    def test_source_change_after_preflight_never_substitutes_payload_bytes(self):
        scene = self.scene("source-change")
        scene.add("fpga_mesh/alpha.py", b"old", b"approved-new")
        raw, digest = scene.write_plan()
        real_temp = lpt._write_temp_sibling
        changed = {"value": False}

        def change_source_then_write(target, payload, *, tag):
            if not changed["value"]:
                changed["value"] = True
                scene.files[0]["_source"].write_bytes(b"unapproved replacement")
            return real_temp(target, payload, tag=tag)

        with mock.patch.object(lpt, "_write_temp_sibling", side_effect=change_source_then_write):
            report = self.apply(scene, raw, digest)
        self.assertTrue(changed["value"])
        self.assertEqual(report["status"], "applied")
        self.assertEqual(scene.files[0]["_target"].read_bytes(), b"approved-new")
        self.assertEqual(scene.files[0]["_source"].read_bytes(), b"unapproved replacement")

    def test_target_change_before_each_write_preserves_foreign_bytes_and_rolls_back_earlier(self):
        for index in (0, 1):
            with self.subTest(index=index):
                scene = self.scene(f"concurrent-target-{index}")
                scene.add("fpga_mesh/alpha.py", b"alpha-old", b"alpha-new")
                scene.add("tests/test_beta.py", b"beta-old", b"beta-new")
                raw, digest = scene.write_plan()
                real_temp = lpt._write_temp_sibling

                def modify_then_write(target, payload, *, tag):
                    if os.path.normcase(os.path.abspath(str(target))) == os.path.normcase(
                            os.path.abspath(str(scene.files[index]["_target"]))):
                        scene.files[index]["_target"].write_bytes(b"foreign-during-write")
                    return real_temp(target, payload, tag=tag)

                with mock.patch.object(lpt, "_write_temp_sibling", side_effect=modify_then_write):
                    report = self.apply(scene, raw, digest)
                self.assertEqual(report["status"], "ambiguous")
                self.assertEqual(scene.files[index]["_target"].read_bytes(), b"foreign-during-write")
                for file_index in range(2):
                    if file_index != index:
                        self.assertEqual(scene.files[file_index]["_target"].read_bytes(),
                                         scene.files[file_index]["_pre"])

    def test_actual_hardlink_is_rejected(self):
        scene = self.scene("hardlink")
        scene.add("fpga_mesh/alpha.py", b"old", b"new")
        alias = scene.files[0]["_target"].with_name("alpha-alias.py")
        try:
            os.link(scene.files[0]["_target"], alias)
        except OSError as exc:
            self.skipTest(f"hard links unavailable: {exc!r}")
        raw, digest = scene.write_plan()
        self.assert_preflight_rejected(lambda: self.apply(scene, raw, digest), "hard-link")
        self.assertFalse(scene.operation_dir.exists())
        self.assertEqual(scene.files[0]["_target"].read_bytes(), b"old")

    def test_actual_windows_junction_is_rejected(self):
        if os.name != "nt":
            self.skipTest("Windows junction test")
        scene = self.scene("junction")
        external = scene.root / "external-parent"
        external.mkdir()
        (external / "alpha.py").write_bytes(b"old")
        junction = scene.target_root / "fpga_mesh"
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(external)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode:
            self.skipTest(f"junction creation unavailable: {result.stderr or result.stdout}")
        self.addCleanup(lambda: os.rmdir(junction) if os.path.lexists(junction) else None)
        (scene.source_root / "payload.bin").write_bytes(b"new")
        scene.files.append({
            "path": "fpga_mesh/alpha.py", "source": "payload.bin",
            "preimage": image(b"old"), "postimage": image(b"new"),
            "_pre": b"old", "_post": b"new", "_target": junction / "alpha.py",
            "_source": scene.source_root / "payload.bin",
        })
        raw, digest = scene.write_plan()
        self.assert_preflight_rejected(
            lambda: self.apply(scene, raw, digest), "junction|reparse|symlink")
        self.assertFalse(scene.operation_dir.exists())
        self.assertEqual((junction / "alpha.py").read_bytes(), b"old")

    def test_symlink_is_rejected_when_supported(self):
        scene = self.scene("symlink")
        scene.add("fpga_mesh/alpha.py", b"old", b"new")
        outside = scene.root / "outside.py"
        outside.write_bytes(b"old")
        target = scene.files[0]["_target"]
        target.unlink()
        try:
            os.symlink(outside, target)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc!r}")
        raw, digest = scene.write_plan()
        self.assert_preflight_rejected(
            lambda: self.apply(scene, raw, digest), "symlink|reparse|link")
        self.assertFalse(scene.operation_dir.exists())

    def test_nonfinite_json_values_are_rejected_before_journal_creation(self):
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                scene = self.scene(f"nonfinite-{token.replace('-', 'neg')}")
                scene.add("fpga_mesh/alpha.py", b"old", b"new-value")
                value = scene.plan()
                raw = json.dumps(value, allow_nan=True,
                                 separators=(",", ":")).encode("utf-8")
                marker = b'"size":9'
                self.assertIn(marker, raw)
                raw = raw.replace(marker, f'"size":{token}'.encode("utf-8"), 1)
                scene.plan_path.write_bytes(raw)
                before = snapshot_tree(scene.root)
                self.assert_preflight_rejected(
                    lambda: self.apply(scene, raw, sha(raw)), "non-finite")
                self.assertFalse(scene.operation_dir.exists())
                self.assertEqual(snapshot_tree(scene.root), before)

    def test_malformed_operation_ids_are_rejected_before_journal_creation(self):
        bad_ids = ("", "../escape", "a/b", "a\b", "A" * 129, "CON",
                   "name.", "name ", ".hidden", "-leading")
        for bad in bad_ids:
            with self.subTest(operation_id=bad):
                scene = self.scene("operation-id")
                scene.add("fpga_mesh/alpha.py", b"old", b"new")
                value = scene.plan(operation_id=bad)
                raw, digest = scene.write_plan(value)
                before = snapshot_tree(scene.root)
                self.assert_preflight_rejected(
                    lambda: self.apply(scene, raw, digest),
                    "operation_id|safe|malformed")
                self.assertEqual(list(scene.journal_root.iterdir()), [])
                self.assertEqual(snapshot_tree(scene.root), before)

    def test_casefold_duplicate_targets_and_sources_are_rejected_before_journal_creation(self):
        for case in ("target", "source"):
            with self.subTest(case=case):
                scene = self.scene(f"casefold-{case}")
                scene.add("fpga_mesh/alpha.py", b"old", b"new",
                          source="payload-a.bin")
                scene.add("tests/test_beta.py", b"before", b"after",
                          source="payload-b.bin")
                value = scene.plan()
                if case == "target":
                    value["files"][1]["path"] = "fpga_mesh/ALPHA.py"
                else:
                    value["files"][0]["source"] = "Payload.bin"
                    value["files"][1]["source"] = "payload.bin"
                raw, digest = scene.write_plan(value)
                before = snapshot_tree(scene.root)
                self.assert_preflight_rejected(
                    lambda: self.apply(scene, raw, digest),
                    "duplicate target|duplicate source")
                self.assertEqual(list(scene.journal_root.iterdir()), [])
                self.assertEqual(snapshot_tree(scene.root), before)

    def test_invalid_second_preflight_entry_stops_before_journal_and_target_writes(self):
        for case in ("preimage-hash", "source-missing", "target-missing"):
            with self.subTest(case=case):
                scene = self.scene(f"second-entry-{case}")
                scene.add("fpga_mesh/alpha.py", b"alpha-old", b"alpha-new")
                scene.add("tests/test_beta.py", b"beta-old", b"beta-new")
                value = scene.plan()
                if case == "preimage-hash":
                    value["files"][1]["preimage"]["sha256"] = "1" * 64
                raw, digest = scene.write_plan(value)
                if case == "source-missing":
                    scene.files[1]["_source"].unlink()
                elif case == "target-missing":
                    scene.files[1]["_target"].unlink()
                before = snapshot_tree(scene.root)
                self.assert_preflight_rejected(lambda: self.apply(scene, raw, digest))
                self.assertFalse(scene.operation_dir.exists())
                self.assertEqual(scene.files[0]["_target"].read_bytes(), b"alpha-old")
                self.assertEqual(snapshot_tree(scene.root), before)

    def _injected_io_case(self, stage: str, operation: str) -> dict:
        scene = self.scene(f"io-{stage}-{operation}")
        rollback_case = stage in ("rollback_intent", "rollback-temp")
        scene.add("fpga_mesh/alpha.py", b"alpha-old", b"alpha-new")
        if rollback_case:
            scene.add("tests/test_beta.py", b"beta-old", b"beta-new")
        raw, digest = scene.write_plan()
        state = {"active": None, "fired": False, "second_failed": False}
        real_write_file = lpt._write_exclusive_file
        real_append = lpt._Journal.append
        real_create = lpt._Journal.create
        real_os_write = lpt.os.write
        real_fsync = lpt.os.fsync
        real_temp = lpt._write_temp_sibling

        def classify(path):
            path = Path(path)
            if path.parent.name == "backups":
                return "backup"
            if path.name == "approved-plan.json":
                return "approved-plan"
            if ".local-patch-apply-" in path.name:
                return "payload-temp"
            if ".local-patch-rollback-" in path.name:
                return "rollback-temp"
            return "exclusive-file"

        def write_file(path, payload):
            previous = state["active"]
            state["active"] = classify(path)
            try:
                return real_write_file(path, payload)
            finally:
                state["active"] = previous

        def create(journal):
            previous = state["active"]
            state["active"] = "journal-create"
            try:
                return real_create(journal)
            finally:
                state["active"] = previous

        def append(journal, record_type, **fields):
            previous = state["active"]
            state["active"] = record_type
            try:
                return real_append(journal, record_type, **fields)
            finally:
                state["active"] = previous

        def io_hook(*args):
            if not state["fired"] and state["active"] == stage:
                state["fired"] = True
                raise OSError(errno.ENOSPC,
                              f"injected {operation} failure at {stage}")
            if operation == "write":
                return real_os_write(*args)
            return real_fsync(*args)

        def temp_hook(target, payload, *, tag):
            if (tag == "apply" and same_path(target, scene.files[1]["_target"])
                    and not state["second_failed"]):
                state["second_failed"] = True
                raise OSError(errno.ENOSPC, "injected second target payload failure")
            return real_temp(target, payload, tag=tag)

        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(
                lpt, "_write_exclusive_file", side_effect=write_file))
            stack.enter_context(mock.patch.object(
                lpt._Journal, "create", autospec=True, side_effect=create))
            stack.enter_context(mock.patch.object(
                lpt._Journal, "append", autospec=True, side_effect=append))
            stack.enter_context(mock.patch.object(
                lpt.os, operation, side_effect=io_hook))
            if rollback_case:
                stack.enter_context(mock.patch.object(
                    lpt, "_write_temp_sibling", side_effect=temp_hook))
            report = self.apply(scene, raw, digest)
        self.assertTrue(state["fired"])
        if stage == "backup":
            expected_status = "preparation_failed"
        elif stage in ("journal-create", "plan_bound", "write_intent", "applied",
                       "rollback_intent"):
            expected_status = "ambiguous"
        elif stage == "payload-temp":
            expected_status = "failed_unchanged"
        elif stage == "rollback-temp":
            expected_status = "partial"
        else:
            self.fail(f"unknown injected stage {stage}")
        if stage == "applied":
            expected_bytes = [b"alpha-new"]
        elif rollback_case:
            expected_bytes = [b"alpha-new", b"beta-old"]
        else:
            expected_bytes = [b"alpha-old"]
        self.assertEqual(report["status"], expected_status)
        self.assertFalse(report["success"])
        self.assertEqual([entry["_target"].read_bytes() for entry in scene.files],
                         expected_bytes)
        self.assertTrue(any("injected" in str(item) for item in report["errors"]))
        if expected_status in ("partial", "failed_unchanged"):
            self.assertFalse(report["all_or_nothing"])
        inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
        self.assertFalse(inspected["mutates_state"])
        if expected_status in ("ambiguous", "partial"):
            self.assertTrue(inspected["requires_main_review"])
        if stage == "backup":
            events = scene.operation_dir / "events.jsonl"
            self.assertTrue(events.exists())
            os.remove(events)
        return report

    def test_injected_os_write_and_fsync_failures_are_reported_by_boundary(self):
        cases = (
            ("backup", "write"), ("backup", "fsync"),
            ("journal-create", "fsync"),
            ("plan_bound", "write"), ("plan_bound", "fsync"),
            ("payload-temp", "write"), ("payload-temp", "fsync"),
            ("write_intent", "write"), ("write_intent", "fsync"),
            ("applied", "write"), ("applied", "fsync"),
            ("rollback_intent", "write"), ("rollback_intent", "fsync"),
            ("rollback-temp", "write"), ("rollback-temp", "fsync"),
        )
        for stage, operation in cases:
            with self.subTest(stage=stage, operation=operation):
                self._injected_io_case(stage, operation)

    def test_real_journal_corruption_during_apply_is_detected_before_replace(self):
        for mode in ("truncate", "overwrite"):
            with self.subTest(mode=mode):
                scene = self.scene(f"journal-corrupt-{mode}")
                scene.add("fpga_mesh/alpha.py", b"old", b"new")
                raw, digest = scene.write_plan()
                events = scene.operation_dir / "events.jsonl"
                real_temp = lpt._write_temp_sibling
                state = {"done": False}

                def corrupt(target, payload, *, tag):
                    if not state["done"]:
                        state["done"] = True
                        if mode == "truncate":
                            events.write_bytes(b"")
                        else:
                            data = events.read_bytes()
                            needle = b'"type":"plan_bound"'
                            position = data.index(needle) + len(b'"type":"plan_')
                            mutated = bytearray(data)
                            mutated[position] = ord("X")
                            events.write_bytes(bytes(mutated))
                    return real_temp(target, payload, tag=tag)

                with mock.patch.object(lpt, "_write_temp_sibling", side_effect=corrupt):
                    report = self.apply(scene, raw, digest)
                self.assertTrue(state["done"])
                self.assertFalse(report["success"])
                self.assertEqual(report["status"], "ambiguous")
                self.assertEqual(scene.files[0]["_target"].read_bytes(), b"old")
                self.assertTrue(report["requires_main_review"])
                inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
                self.assertEqual(inspected["status"], "ambiguous")
                self.assertFalse(inspected["mutates_state"])

    def test_same_bytes_foreign_replacement_between_replace_and_postcheck_is_not_owned(self):
        scene = self.scene("replace-postcheck-foreign")
        target = scene.add("fpga_mesh/alpha.py", b"old", b"new")
        raw, digest = scene.write_plan()
        real_replace = os.replace
        state = {"done": False}

        def replace_hook(source, destination):
            real_replace(source, destination)
            if not state["done"] and same_path(destination, target):
                state["done"] = True
                swap = target.parent / "foreign-same-bytes.tmp"
                swap.write_bytes(b"new")
                real_replace(swap, target)

        with mock.patch.object(lpt.os, "replace", side_effect=replace_hook):
            report = self.apply(scene, raw, digest)
        self.assertTrue(state["done"])
        self.assertFalse(report["success"])
        self.assertIn(report["status"], {"partial", "ambiguous"})
        self.assertTrue(report["uncertain_outcome"])
        self.assertEqual(target.read_bytes(), b"new")
        events = self.journal_events(scene)
        self.assertFalse(any(event["type"] == "applied" for event in events))
        self.assertTrue(any(event["type"] == "postcheck_failed" for event in events))
        inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
        self.assertIn(inspected["status"], {"partial", "ambiguous"})
        self.assertFalse(inspected["ownership_proven"][0])
        self.assertTrue(inspected["requires_main_review"])

    def test_three_file_partial_rollback_protects_foreign_same_bytes_and_restores_safe_file(self):
        scene = self.scene("three-file-partial")
        scene.add("fpga_mesh/alpha.py", b"alpha-old", b"alpha-new")
        scene.add("tests/test_beta.py", b"beta-old", b"beta-new")
        scene.add("tests/test_gamma.py", b"gamma-old", b"gamma-new")
        raw, digest = scene.write_plan()
        first_target = scene.files[0]["_target"]
        second_target = scene.files[1]["_target"]
        third_target = scene.files[2]["_target"]
        first_original_id = file_id(first_target)
        second_original_id = file_id(second_target)
        real_replace = os.replace
        real_temp = lpt._write_temp_sibling
        state = {"done": False}

        def fail_third(target, payload, *, tag):
            if (tag == "apply" and same_path(target, third_target)
                    and not state["done"]):
                state["done"] = True
                swap = first_target.parent / "foreign-same-bytes.tmp"
                swap.write_bytes(scene.files[0]["_post"])
                real_replace(swap, first_target)
                raise OSError(errno.ENOSPC, "injected third target ENOSPC")
            return real_temp(target, payload, tag=tag)

        with mock.patch.object(lpt, "_write_temp_sibling", side_effect=fail_third):
            report = self.apply(scene, raw, digest)
        self.assertTrue(state["done"])
        self.assertEqual(report["status"], "partial")
        self.assertFalse(report["all_or_nothing"])
        self.assertTrue(report["requires_main_review"])
        self.assertEqual(first_target.read_bytes(), scene.files[0]["_post"])
        self.assertEqual(second_target.read_bytes(), scene.files[1]["_pre"])
        self.assertEqual(third_target.read_bytes(), scene.files[2]["_pre"])
        self.assertNotEqual(file_id(first_target), first_original_id)
        self.assertNotEqual(file_id(second_target), second_original_id)
        events = self.journal_events(scene)
        applied_first = next(event for event in events
                             if event["type"] == "applied" and event["index"] == 0)
        self.assertNotEqual(file_id(first_target),
                            (applied_first["observed_identity"]["device"],
                             applied_first["observed_identity"]["file_id"]))
        inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
        self.assertEqual(inspected["status"], "partial")
        self.assertTrue(inspected["requires_main_review"])
        self.assertEqual(inspected["confirmed_writes"], 2)
        self.assertEqual(inspected["ownership_proven"], [False, True, False])
        results = {(result["index"], result["status"])
                   for result in inspected["rollback_results"]}
        self.assertIn((1, "restored"), results)
        self.assertIn((0, "protected"), results)

    def test_rollback_continues_safe_files_after_one_target_path_conflict(self):
        scene = self.scene("rollback-continue")
        scene.add("fpga_mesh/alpha.py", b"alpha-old", b"alpha-new")
        scene.add("tests/test_beta.py", b"beta-old", b"beta-new")
        scene.add("tests/test_gamma.py", b"gamma-old", b"gamma-new")
        raw, digest = scene.write_plan()
        first_target = scene.files[0]["_target"]
        second_target = scene.files[1]["_target"]
        third_target = scene.files[2]["_target"]
        real_temp = lpt._write_temp_sibling
        state = {"done": False}

        def remove_and_fail(target, payload, *, tag):
            if (tag == "apply" and same_path(target, third_target)
                    and not state["done"]):
                state["done"] = True
                second_target.unlink()
                raise OSError(errno.ENOSPC, "injected third target ENOSPC")
            return real_temp(target, payload, tag=tag)

        with mock.patch.object(lpt, "_write_temp_sibling",
                               side_effect=remove_and_fail):
            report = self.apply(scene, raw, digest)
        self.assertTrue(state["done"])
        self.assertEqual(report["status"], "ambiguous")
        self.assertTrue(report["requires_main_review"])
        self.assertEqual(first_target.read_bytes(), scene.files[0]["_pre"])
        self.assertFalse(second_target.exists())
        self.assertEqual(third_target.read_bytes(), scene.files[2]["_pre"])
        statuses = {item["path"]: item["status"] for item in report["file_statuses"]}
        self.assertEqual(statuses["fpga_mesh/alpha.py"], "rolled_back")
        self.assertEqual(statuses["tests/test_beta.py"], "uncertain_unrolled")
        self.assertEqual(statuses["tests/test_gamma.py"], "not_attempted")
        inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
        self.assertEqual(inspected["status"], "ambiguous")
        self.assertEqual(inspected["ownership_proven"], [True, False, False])
        self.assertTrue(inspected["requires_main_review"])

    def test_journal_root_replacement_after_preflight_is_rejected(self):
        scene = self.scene("journal-root-replacement")
        scene.add("fpga_mesh/alpha.py", b"old", b"new")
        raw, digest = scene.write_plan()
        plan = lpt._read_plan(scene.plan_path, digest)
        preflight = lpt._preflight(plan, scene.plan_path,
                                   reject_existing_journal=True)
        moved = scene.root / "journal-original"
        os.rename(scene.journal_root, moved)
        scene.journal_root.mkdir()
        report = lpt._execute_apply(preflight)
        self.assertFalse(report["success"])
        self.assertEqual(report["status"], "preparation_failed")
        self.assertEqual(scene.files[0]["_target"].read_bytes(), b"old")
        self.assertFalse((scene.journal_root / scene.operation_id).exists())
        self.assertFalse(any(moved.rglob("events.jsonl")))

    def test_preparation_failure_closes_journal_handle(self):
        scene = self.scene("preparation-handle")
        scene.add("fpga_mesh/alpha.py", b"old", b"new")
        raw, digest = scene.write_plan()
        real_write = lpt._write_exclusive_file

        def fail_backup(path, payload):
            if Path(path).parent.name == "backups":
                raise OSError(errno.ENOSPC, "injected backup failure")
            return real_write(path, payload)

        with mock.patch.object(lpt, "_write_exclusive_file",
                               side_effect=fail_backup):
            report = self.apply(scene, raw, digest)
        self.assertEqual(report["status"], "preparation_failed")
        events = scene.operation_dir / "events.jsonl"
        self.assertTrue(events.exists())
        os.remove(events)
        self.assertFalse(events.exists())

    def test_abandoned_mutex_is_failed_closed_and_released_across_processes(self):
        if os.name != "nt":
            self.skipTest("Windows mutex test")
        scene = self.scene("abandoned-mutex")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool,
                                          ctypes.c_wchar_p)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel32.CloseHandle.restype = ctypes.c_bool
        mutex_name = lpt._mutex_name(*file_id(scene.target_root))
        retained = kernel32.CreateMutexW(None, False, mutex_name)
        if not retained:
            self.skipTest(f"retained mutex creation failed: {ctypes.get_last_error()}")
        self.addCleanup(lambda: kernel32.CloseHandle(retained))
        holder_code = f"""
import os, sys
from pathlib import Path
sys.path.insert(0, {str(WORKTREE_ROOT)!r})
import fpga_mesh.local_patch_transaction as lpt
mutex = lpt._TargetMutex(Path(sys.argv[1]))
mutex.__enter__()
Path(sys.argv[2]).write_text('ready', encoding='ascii')
os._exit(73)
"""
        ready = scene.root / "holder-ready.txt"
        holder = subprocess.Popen(
            [sys.executable, "-B", "-c", holder_code,
             str(scene.target_root), str(ready)],
            cwd=str(WORKTREE_ROOT), env=self.subprocess_env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            deadline = time.monotonic() + 10
            while not ready.exists():
                if holder.poll() is not None:
                    stdout, stderr = holder.communicate(timeout=1)
                    self.fail(f"abandoned-mutex holder exited {holder.returncode}: {stdout} {stderr}")
                if time.monotonic() >= deadline:
                    self.fail("abandoned-mutex holder did not become ready")
                time.sleep(0.05)
            self.assertEqual(holder.wait(timeout=10), 73)
        finally:
            if holder.poll() is None:
                holder.terminate()
                try:
                    holder.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    holder.kill()
                    holder.wait(timeout=5)
            if holder.stdout is not None:
                holder.stdout.close()
            if holder.stderr is not None:
                holder.stderr.close()
        with self.assertRaises(lpt.MutexAbandonedError):
            lpt._TargetMutex(scene.target_root).__enter__()
        probe_code = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(WORKTREE_ROOT)!r})
import fpga_mesh.local_patch_transaction as lpt
mutex = lpt._TargetMutex(Path(sys.argv[1]))
try:
    mutex.__enter__()
except lpt.BusyError:
    raise SystemExit(2)
except BaseException as exc:
    print(type(exc).__name__, file=sys.stderr)
    raise SystemExit(3)
mutex.__exit__(None, None, None)
raise SystemExit(0)
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", probe_code, str(scene.target_root)],
            cwd=str(WORKTREE_ROOT), env=self.subprocess_env(),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with lpt._TargetMutex(scene.target_root):
            pass

    def test_root_and_plan_overlap_are_rejected_before_journal_creation(self):
        cases = ("target-source", "source-journal", "journal-ancestor", "plan-in-target")
        for case in cases:
            with self.subTest(case=case):
                scene = self.scene(f"overlap-{case}")
                scene.add("fpga_mesh/alpha.py", b"old", b"new")
                value = scene.plan()
                if case == "target-source":
                    value["source_root"] = str(scene.target_root)
                elif case == "source-journal":
                    value["journal_root"] = str(scene.source_root)
                elif case == "journal-ancestor":
                    value["journal_root"] = str(scene.root)
                else:
                    scene.plan_path = scene.target_root / "plan.json"
                raw, digest = scene.write_plan(value)
                self.assert_preflight_rejected(lambda: self.apply(scene, raw, digest))
                self.assertFalse(scene.operation_dir.exists())

    def test_target_parent_substitution_by_real_junction_is_detected(self):
        if os.name != "nt":
            self.skipTest("Windows junction test")
        scene = self.scene("parent-junction")
        target = scene.add("fpga_mesh/alpha.py", b"old", b"new")
        raw, digest = scene.write_plan()
        parent = target.parent
        moved = scene.target_root / "fpga_mesh-original"
        external = scene.root / "external-target-parent"
        external.mkdir()
        real_temp = lpt._write_temp_sibling
        substituted = {"value": False}

        def substitute_parent(target_path, payload, *, tag):
            if not substituted["value"]:
                substituted["value"] = True
                os.rename(parent, moved)
                result = subprocess.run(
                    ["cmd.exe", "/d", "/c", "mklink", "/J", str(parent), str(external)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
                if result.returncode:
                    os.rename(moved, parent)
                    raise OSError(errno.EIO, "junction injection unavailable")
            return real_temp(target_path, payload, tag=tag)

        try:
            with mock.patch.object(lpt, "_write_temp_sibling", side_effect=substitute_parent):
                report = self.apply(scene, raw, digest)
        finally:
            if os.path.lexists(parent) and (parent.is_symlink() or
                                            getattr(parent, "is_junction", lambda: False)()):
                os.rmdir(parent)
            if moved.exists() and not parent.exists():
                os.rename(moved, parent)
        self.assertTrue(substituted["value"])
        self.assertFalse(report["success"])
        self.assertTrue(report["requires_main_review"])
        self.assertEqual((scene.target_root / "fpga_mesh" / "alpha.py").read_bytes(), b"old")
        self.assertFalse((external / "alpha.py").exists())

    def test_real_windows_share_lock_prevents_replacement_and_preserves_os_error(self):
        if os.name != "nt":
            self.skipTest("Windows sharing test")
        scene = self.scene("sharing-lock")
        target = scene.add("fpga_mesh/alpha.py", b"old", b"new")
        raw, digest = scene.write_plan()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = (
            ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p)
        kernel32.CreateFileW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        generic_read = 0x80000000
        share_read_write = 0x00000001 | 0x00000002
        open_existing = 3
        handle = kernel32.CreateFileW(str(target), generic_read, share_read_write,
                                      None, open_existing, 0, None)
        if handle == ctypes.c_void_p(-1).value:
            self.skipTest(f"CreateFileW failed: Windows error {ctypes.get_last_error()}")
        try:
            report = self.apply(scene, raw, digest)
        finally:
            kernel32.CloseHandle(handle)
        self.assertFalse(report["success"])
        self.assertEqual(target.read_bytes(), b"old")
        windows_errors = [entry.get("winerror") for entry in report["errors"]]
        self.assertTrue(set(windows_errors) & {5, 32}, windows_errors)
        self.assertTrue(report["requires_main_review"])

    def test_existing_empty_completed_and_different_plan_journals_refuse_replay(self):
        empty_scene = self.scene("journal-empty")
        empty_scene.add("fpga_mesh/alpha.py", b"old", b"new")
        empty_scene.operation_dir.mkdir()
        raw, digest = empty_scene.write_plan()
        with self.assertRaises(lpt.JournalExistsError):
            self.apply(empty_scene, raw, digest)
        self.assertEqual(empty_scene.files[0]["_target"].read_bytes(), b"old")

        completed = self.scene("journal-complete")
        completed.add("fpga_mesh/alpha.py", b"old", b"new")
        raw, digest = completed.write_plan()
        first = self.apply(completed, raw, digest)
        self.assertEqual(first["status"], "applied")
        with self.assertRaises(lpt.JournalExistsError):
            self.apply(completed, raw, digest)

        completed.add("tests/test_second.py", b"before", b"after")
        value = completed.plan()
        raw, digest = completed.write_plan(value)
        with self.assertRaises(lpt.JournalExistsError):
            self.apply(completed, raw, digest)
        self.assertEqual(completed.files[1]["_target"].read_bytes(), b"before")

    def test_torn_journal_inspection_is_ambiguous_and_never_mutates(self):
        scene = self.scene("torn-journal")
        scene.add("fpga_mesh/alpha.py", b"old", b"new")
        raw, digest = scene.write_plan()
        report = self.apply(scene, raw, digest)
        self.assertEqual(report["status"], "applied")
        events = scene.operation_dir / "events.jsonl"
        with events.open("ab") as stream:
            stream.write(b'{"seq":')
            stream.flush()
            os.fsync(stream.fileno())
        before = snapshot_tree(scene.root)
        inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
        self.assertEqual(inspected["status"], "ambiguous")
        self.assertTrue(inspected["torn_final_record"])
        self.assertTrue(inspected["requires_main_review"])
        self.assertFalse(inspected["mutates_state"])
        self.assertEqual(snapshot_tree(scene.root), before)
        with self.assertRaises(lpt.JournalExistsError):
            self.apply(scene, raw, digest)
        self.assertEqual(scene.files[0]["_target"].read_bytes(), b"new")

    def test_module_has_no_cli_and_imports_no_live_entrypoints(self):
        source_path = Path(lpt.__file__)
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    self.fail("module must not use relative imports")
                if node.module:
                    imported.add(node.module.split(".", 1)[0])
        self.assertFalse(any(name == "fpga_mesh" for name in imported), imported)
        self.assertNotIn("argparse", imported)
        self.assertNotIn('if __name__ == "__main__"', source)
        self.assertFalse(hasattr(lpt, "main"))

    def test_simultaneous_apply_with_different_journal_root_gets_real_busy_lock(self):
        scene = self.scene("mutex-contention")
        scene.add("fpga_mesh/alpha.py", b"old", b"new")
        holder_code = f"""
import sys, time
from pathlib import Path
sys.path.insert(0, {str(WORKTREE_ROOT)!r})
import fpga_mesh.local_patch_transaction as lpt
mutex = lpt._TargetMutex(Path(sys.argv[1]))
mutex.__enter__()
Path(sys.argv[2]).write_text('ready', encoding='ascii')
time.sleep(30)
"""
        ready = scene.root / "holder-ready.txt"
        process = subprocess.Popen(
            [sys.executable, "-B", "-c", holder_code, str(scene.target_root), str(ready)],
            cwd=str(WORKTREE_ROOT), env=self.subprocess_env(), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            deadline = time.monotonic() + 10
            while not ready.exists():
                if process.poll() is not None:
                    stdout, stderr = process.communicate(timeout=1)
                    self.fail(f"mutex holder exited {process.returncode}: {stdout} {stderr}")
                if time.monotonic() >= deadline:
                    self.fail("mutex holder did not become ready")
                time.sleep(0.05)
            alternative = scene.root / "alternative-journal"
            alternative.mkdir()
            value = scene.plan()
            value["journal_root"] = str(alternative)
            raw, digest = scene.write_plan(value)
            before = snapshot_tree(scene.root)
            with self.assertRaises(lpt.BusyError):
                self.apply(scene, raw, digest)
            self.assertFalse((alternative / scene.operation_id).exists())
            self.assertEqual(snapshot_tree(scene.root), before)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()

    def test_real_process_crash_after_replace_is_inspected_and_not_replayed(self):
        scene = self.scene("crash-boundary")
        target = scene.add("fpga_mesh/alpha.py", b"old", b"new")
        raw, digest = scene.write_plan()
        child_code = f"""
import os, sys
from pathlib import Path
sys.path.insert(0, {str(WORKTREE_ROOT)!r})
import fpga_mesh.local_patch_transaction as lpt
target = os.path.normcase(os.path.abspath(sys.argv[3]))
real_replace = lpt.os.replace
def crash_after_replace(source, destination):
    real_replace(source, destination)
    if os.path.normcase(os.path.abspath(str(destination))) == target:
        os._exit(91)
    return None
lpt.os.replace = crash_after_replace
report = lpt.apply(Path(sys.argv[1]), reviewed_plan_sha256=sys.argv[2])
print(report)
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", child_code, str(scene.plan_path), digest, str(target)],
            cwd=str(WORKTREE_ROOT), env=self.subprocess_env(), capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertEqual(result.returncode, 91, result.stdout + result.stderr)
        self.assertEqual(target.read_bytes(), b"new")
        events = self.journal_events(scene)
        self.assertFalse(any(event["type"] == "terminal" for event in events))
        self.assertEqual(sum(1 for event in events if event["type"] == "write_intent"), 1)
        self.assertFalse(any(event["type"] == "applied" for event in events))
        before_inspect = snapshot_tree(scene.root)
        inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
        self.assertEqual(inspected["status"], "ambiguous")
        self.assertTrue(inspected["chain_valid"])
        self.assertIsNone(inspected["terminal"])
        self.assertEqual(inspected["confirmed_writes"], 0)
        self.assertEqual(len(inspected["unresolved_write_intents"]), 1)
        self.assertFalse(inspected["ownership_proven"][0])
        self.assertTrue(inspected["requires_main_review"])
        self.assertFalse(inspected["mutates_state"])
        self.assertEqual(snapshot_tree(scene.root), before_inspect)
        before_replay = snapshot_tree(scene.root)
        with self.assertRaises((lpt.JournalExistsError, lpt.MutexAbandonedError)):
            self.apply(scene, raw, digest)
        self.assertEqual(snapshot_tree(scene.root), before_replay)

    def test_inspection_requires_restored_identity_after_same_bytes_foreign_replacement(self):
        scene = self.scene("postrollback-foreign-identity")
        alpha = scene.add("fpga_mesh/alpha.py", b"old-alpha", b"new-alpha")
        beta = scene.add("fpga_mesh/beta.py", b"old-beta", b"new-beta")
        raw, digest = scene.write_plan()
        write_temp = lpt._write_temp_sibling

        def fail_second_temporary(target, payload, *, tag):
            if Path(target) == beta and tag == "apply":
                raise OSError(errno.ENOSPC, "injected second-file temporary failure")
            return write_temp(target, payload, tag=tag)

        with mock.patch.object(lpt, "_write_temp_sibling", side_effect=fail_second_temporary):
            report = self.apply(scene, raw, digest)
        self.assertEqual(report["status"], "rolled_back")
        clean = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
        self.assertFalse(clean["requires_main_review"])
        restored_identity = file_id(alpha)
        foreign = scene.root / "foreign-same-preimage.bin"
        foreign.write_bytes(b"old-alpha")
        os.replace(foreign, alpha)
        foreign_identity = file_id(alpha)
        self.assertNotEqual(foreign_identity, restored_identity)

        before_inspect = snapshot_tree(scene.root)
        inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
        self.assertEqual(inspected["status"], "review_required")
        self.assertTrue(inspected["requires_main_review"])
        self.assertFalse(inspected["ownership_proven"][0])
        self.assertEqual(file_id(alpha), foreign_identity)
        self.assertEqual(alpha.read_bytes(), b"old-alpha")
        self.assertEqual(snapshot_tree(scene.root), before_inspect)

    def test_restore_temporary_tampering_is_rejected_before_target_replace(self):
        scene = self.scene("tampered-restore-temporary")
        alpha = scene.add("fpga_mesh/alpha.py", b"old-alpha", b"new-alpha")
        beta = scene.add("fpga_mesh/beta.py", b"old-beta", b"new-beta")
        raw, digest = scene.write_plan()
        write_temp = lpt._write_temp_sibling

        def tamper_restore(target, payload, *, tag):
            if Path(target) == beta and tag == "apply":
                raise OSError(errno.ENOSPC, "injected second-file temporary failure")
            temporary, observation = write_temp(target, payload, tag=tag)
            if tag == "rollback":
                temporary.write_bytes(b"bad-alpha")
            return temporary, observation

        with mock.patch.object(lpt, "_write_temp_sibling", side_effect=tamper_restore):
            report = self.apply(scene, raw, digest)
        self.assertFalse(report["success"])
        self.assertTrue(report["requires_main_review"])
        self.assertEqual(alpha.read_bytes(), b"new-alpha")
        self.assertEqual(beta.read_bytes(), b"old-beta")

    def test_same_bytes_foreign_replacement_during_rollback_is_not_owned(self):
        scene = self.scene("foreign-during-rollback")
        alpha = scene.add("fpga_mesh/alpha.py", b"old-alpha", b"new-alpha")
        beta = scene.add("fpga_mesh/beta.py", b"old-beta", b"new-beta")
        raw, digest = scene.write_plan()
        write_temp = lpt._write_temp_sibling
        replace = os.replace
        foreign_identity = []

        def fail_second(target, payload, *, tag):
            if Path(target) == beta and tag == "apply":
                raise OSError(errno.ENOSPC, "injected second-file temporary failure")
            return write_temp(target, payload, tag=tag)

        def replace_then_foreign(source, destination):
            result = replace(source, destination)
            if ".local-patch-rollback-" in Path(source).name:
                foreign = scene.root / "same-preimage-foreign.bin"
                foreign.write_bytes(b"old-alpha")
                replace(foreign, alpha)
                foreign_identity.append(file_id(alpha))
            return result

        with mock.patch.object(lpt, "_write_temp_sibling", side_effect=fail_second), \
                mock.patch.object(lpt.os, "replace", side_effect=replace_then_foreign):
            report = self.apply(scene, raw, digest)
        self.assertEqual(report["status"], "ambiguous")
        self.assertTrue(report["requires_main_review"])
        self.assertEqual(file_id(alpha), foreign_identity[0])
        inspected = lpt.inspect(scene.plan_path, reviewed_plan_sha256=digest)
        self.assertTrue(inspected["requires_main_review"])
        self.assertFalse(inspected["ownership_proven"][0])

    def test_journal_corruption_after_write_intent_prevents_target_replace(self):
        scene = self.scene("corrupt-after-intent")
        target = scene.add("fpga_mesh/alpha.py", b"old-alpha", b"new-alpha")
        raw, digest = scene.write_plan()
        append = lpt._Journal.append

        def corrupt_after_intent(journal, kind, **fields):
            result = append(journal, kind, **fields)
            if kind == "write_intent":
                with journal.path.open("r+b") as stream:
                    stream.write(b"CORRUPT")
            return result

        with mock.patch.object(lpt._Journal, "append", new=corrupt_after_intent):
            report = self.apply(scene, raw, digest)
        self.assertFalse(report["success"])
        self.assertTrue(report["requires_main_review"])
        self.assertEqual(target.read_bytes(), b"old-alpha")
