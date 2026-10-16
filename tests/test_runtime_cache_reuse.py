import os
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fpga_mesh.app_server import (AppServerClient, RuntimeIntegrityError,
                                 resolve_codex_command, pin_codex_bundle)


class RuntimeCacheReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "OpenAI" / "Codex" / "bin" / "release"
        self.source.mkdir(parents=True)
        (self.source / "codex.exe").write_bytes(b"official-test-fixture")
        (self.source / "codex-code-mode-host.exe").write_bytes(b"matching-host")
        (self.source / "resources").mkdir()
        (self.source / "resources" / "data.bin").write_bytes(b"resource")
        self.cache = self.root / "cache"
        self.env = patch.dict(os.environ, {"FPGA_MESH_CODEX_BINARY": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def resolve(self, mode):
        return resolve_codex_command(
            platform="win32", local_appdata=self.root,
            explicit=self.source / "codex.exe" if mode == "explicit" else None,
            runtime_cache_dir=self.cache,
        )

    def test_second_resolve_after_host_cleanup(self):
        for mode in ("explicit", "auto"):
            with self.subTest(mode=mode):
                (self.source / "codex-code-mode-host.exe").write_bytes(b"matching-host")
                first = self.resolve(mode)
                (self.source / "codex-code-mode-host.exe").unlink()
                self.assertEqual(self.resolve(mode), first)

    def test_second_resolve_after_entire_source_cleanup(self):
        first = {mode: self.resolve(mode) for mode in ("explicit", "auto")}
        shutil.rmtree(self.source)
        for mode, command in first.items():
            with self.subTest(mode=mode):
                self.assertEqual(self.resolve(mode), command)
                self.assertEqual(Path(command[0]).read_bytes(), b"official-test-fixture")

    def test_binding_survives_a_fresh_python_process(self):
        first = {mode: self.resolve(mode) for mode in ("explicit", "auto")}
        shutil.rmtree(self.source)
        for mode, command in first.items():
            args = {"platform": "win32", "local_appdata": str(self.root),
                    "runtime_cache_dir": str(self.cache),
                    "explicit": str(self.source / "codex.exe") if mode == "explicit" else None}
            result = subprocess.run(
                [sys.executable, "-X", "utf8", "-c", "import json,sys; from fpga_mesh.app_server import "
                 "resolve_codex_command; print(json.dumps(resolve_codex_command(**json.loads(sys.argv[1]))))",
                 json.dumps(args)], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout), command)

    def test_bound_resolution_does_not_inspect_original_source(self):
        expected = {mode: self.resolve(mode) for mode in ("explicit", "auto")}
        is_file = Path.is_file
        def guarded(path):
            if path == self.source or self.source in path.parents:
                self.fail("Bound resolver inspected the old source")
            return is_file(path)
        with patch.object(Path, "is_file", guarded), \
                patch.object(Path, "glob", side_effect=AssertionError("source discovery forbidden")):
            for mode, command in expected.items():
                self.assertEqual(self.resolve(mode), command)

    def test_binding_is_sticky_when_desktop_changes(self):
        first = {mode: self.resolve(mode) for mode in ("explicit", "auto")}
        (self.source / "codex.exe").write_bytes(b"new-desktop-version")
        for mode, command in first.items():
            self.assertEqual(self.resolve(mode), command)
        self.assertEqual(len(list(self.cache.glob("selection-*.json"))), 2)

    def test_corrupt_payload_rejects_without_source_or_shim_fallback(self):
        for mode in ("explicit", "auto"):
            command = self.resolve(mode)
        host = Path(command[0]).parent / "codex-code-mode-host.exe"
        host.write_bytes(b"corrupt")
        for mode in ("explicit", "auto"):
            with self.subTest(mode=mode), self.assertRaises(RuntimeIntegrityError):
                self.resolve(mode)
        self.assertEqual(host.read_bytes(), b"corrupt")
        self.assertEqual((self.source / host.name).read_bytes(), b"matching-host")

    def test_missing_snapshot_rejects_even_if_other_valid_cache_exists(self):
        command = self.resolve("auto")
        (self.source / "codex.exe").write_bytes(b"different-version")
        other = pin_codex_bundle(self.source / "codex.exe", self.cache)
        shutil.rmtree(Path(command[0]).parent)
        shutil.rmtree(self.source)
        with self.assertRaises(RuntimeIntegrityError):
            self.resolve("auto")
        self.assertTrue(other.is_file())

    def test_unbound_selector_cannot_discover_another_cache(self):
        self.resolve("explicit")
        shutil.rmtree(self.source)
        self.assertEqual(self.resolve("auto")[0], "cmd.exe")
        with self.assertRaises(FileNotFoundError):
            resolve_codex_command(platform="win32", explicit=self.root / "other.exe",
                                  runtime_cache_dir=self.cache)

    def test_cache_inventory_and_manifest_revalidate_on_every_call(self):
        command = self.resolve("explicit")
        directory = Path(command[0]).parent
        manifest = directory / "mesh-runtime-manifest.json"
        host = directory / "codex-code-mode-host.exe"
        original_manifest, original_host = manifest.read_bytes(), host.read_bytes()
        mutations = (lambda: host.unlink(),
                     lambda: manifest.unlink(),
                     lambda: manifest.write_text("{", encoding="utf-8"),
                     lambda: (directory / "unexpected.dll").write_bytes(b"extra"))
        for mutation in mutations:
            manifest.write_bytes(original_manifest)
            host.write_bytes(original_host)
            mutation()
            with self.assertRaises(RuntimeIntegrityError):
                self.resolve("explicit")

    def test_manifest_cannot_be_rewritten_to_accept_changed_payload(self):
        command = self.resolve("explicit")
        directory = Path(command[0]).parent
        manifest = directory / "mesh-runtime-manifest.json"
        host = directory / "codex-code-mode-host.exe"
        host.write_bytes(b"changed")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["files"][host.name] = hashlib.sha256(b"changed").hexdigest()
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeIntegrityError, "saved selection"):
            self.resolve("explicit")

    def test_invalid_bindings_reject_without_repinning(self):
        self.resolve("explicit")
        binding = next(self.cache.glob("selection-*.json"))
        value = json.loads(binding.read_text(encoding="utf-8"))
        mutations = ["{", "[]", '{"version":1,"version":1}',
                     json.dumps({**value, "selector": {"mode": "other", "path": "other"}}),
                     json.dumps({**value, "cache_key": "../outside"}),
                     json.dumps({**value, "manifest_sha256": "0" * 64})]
        mutations += [json.dumps({**value, "binary": name})
                      for name in ("../codex.exe", "C:codex.exe", "x\\codex.exe", ".", None)]
        for malformed in mutations:
            with self.subTest(binding=malformed):
                binding.write_text(malformed, encoding="utf-8")
                with self.assertRaises(RuntimeIntegrityError):
                    self.resolve("explicit")
                self.assertEqual(binding.read_text(encoding="utf-8"), malformed)

    def test_content_key_and_path_checks_remain_required_when_manifest_hash_matches(self):
        command = self.resolve("explicit")
        manifest = Path(command[0]).parent / "mesh-runtime-manifest.json"
        binding = next(self.cache.glob("selection-*.json"))
        original = json.loads(manifest.read_text(encoding="utf-8"))
        bound = json.loads(binding.read_text(encoding="utf-8"))
        for name in ("../outside", "resources/../outside", "C:outside", "safe.bin"):
            data = {**original, "files": {**original["files"], name: "0" * 64}}
            manifest.write_text(json.dumps(data), encoding="utf-8")
            binding.write_text(json.dumps({**bound, "manifest_sha256":
                hashlib.sha256(manifest.read_bytes()).hexdigest()}), encoding="utf-8")
            with self.assertRaises(RuntimeIntegrityError):
                self.resolve("explicit")

    def test_failed_copy_never_publishes_a_binding(self):
        with patch("fpga_mesh.app_server.shutil.copy2", side_effect=OSError("copy interrupted")):
            with self.assertRaises(OSError):
                self.resolve("explicit")
        self.assertFalse(list(self.cache.glob("selection-*.json")))
        self.assertTrue(list(self.cache.glob("preparing-*")))
        self.assertTrue(Path(self.resolve("explicit")[0]).is_file())

    def test_existing_binding_wins_atomic_publication_race(self):
        command = self.resolve("explicit")
        binding = next(self.cache.glob("selection-*.json"))
        original = binding.read_bytes()
        # The initial lookup races with another launcher's successful publication.
        from fpga_mesh import app_server
        read = app_server._bound_runtime
        with patch.object(app_server, "_bound_runtime", side_effect=[None, read(self.cache,
                json.loads(original)["selector"])]):
            self.assertEqual(self.resolve("explicit"), command)
        self.assertEqual(binding.read_bytes(), original)
        self.assertFalse(list(self.cache.glob("selection-pending-*")))

    @unittest.skipUnless(os.name == "nt", "Windows junction regression")
    def test_junction_in_cached_tree_rejected(self):
        command = self.resolve("explicit")
        resources = Path(command[0]).parent / "resources"
        resources.rename(resources.with_name("original-resources"))
        # Paths are known temporary fixtures; no deletion is composed across shells.
        result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(resources),
                                 str(self.source / "resources")], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.addCleanup(resources.rmdir)
        with self.assertRaisesRegex(RuntimeIntegrityError, "link"):
            self.resolve("explicit")

    def test_non_windows_and_no_cache_keep_existing_selection_behavior(self):
        self.assertEqual(resolve_codex_command(platform="linux", runtime_cache_dir=self.cache),
                         ["codex", "app-server", "--stdio"])
        binary = self.source / "codex.exe"
        self.assertEqual(resolve_codex_command(platform="win32", explicit=binary)[0], str(binary))
        self.assertFalse(self.cache.exists())


class RuntimeCacheLaunchTests(unittest.IsolatedAsyncioTestCase):
    async def test_integrity_failure_prevents_transport_creation(self):
        with patch("fpga_mesh.app_server.resolve_codex_command",
                   side_effect=RuntimeIntegrityError("broken binding")), \
                patch("fpga_mesh.app_server.StdioTransport") as transport:
            with self.assertRaises(RuntimeIntegrityError):
                await AppServerClient.start_stdio(codex_home="unused", client_version="test")
            transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
