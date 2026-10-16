import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from fpga_mesh.distribution import build_archive, select_package_paths


class DistributionTests(unittest.TestCase):
    def test_task_identifiers_and_historical_evidence_remain_packageable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            # Construct the identifier so this regression file also remains
            # packageable with the old scanner while reproducing its failure.
            content = ("task-" + "a1" * 12 + "\n").encode("ascii")
            (root / "receipt.txt").write_bytes(content)
            output = root / "receipt.zip"
            build_archive(root, ["receipt.txt"], output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read("receipt.txt"), content)
            repository = Path(__file__).resolve().parents[1]
            historical = "docs/deployment/evidence/B-INTERRUPT-20261014/README.md"
            build_archive(repository, [historical], root / "historical.zip")
            with zipfile.ZipFile(root / "historical.zip") as archive:
                self.assertEqual(archive.read(historical),
                                 (repository / historical).read_bytes())

    def test_standalone_keys_and_separator_prefixed_keys_are_rejected(self):
        key = "sk-" + "a" * 40
        prefixes = ("", " ", "\n", '"', "'", "=", ":", "/", "\\", "-", "(", "中文")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for prefix in prefixes:
                with self.subTest(prefix=prefix):
                    (root / "receipt.txt").write_text(prefix + key, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "key-like"):
                        build_archive(root, ["receipt.txt"], root / "bad.zip")

    def test_task_identifier_does_not_exempt_real_key_in_same_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "receipt.txt").write_text(
                "task-" + "a1" * 12 + "\napi_key=" + "sk-" + "b" * 40,
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "key-like"):
                build_archive(root, ["receipt.txt"], root / "bad.zip")

    def test_all_supported_private_key_headers_remain_rejected(self):
        kinds = ("", "OPENSSH ", "RSA ", "EC ", "DSA ", "ENCRYPTED ", "PGP ")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for kind in kinds:
                with self.subTest(kind=kind):
                    suffix = "KEY BLOCK-----" if kind == "PGP " else "KEY-----"
                    # A neighboring identifier must not scope the PEM/PGP
                    # alternatives under the new sk-token boundary.
                    content = "identifier-----BEGIN " + kind + "PRIVATE " + suffix
                    (root / "receipt.txt").write_text(content, encoding="ascii")
                    with self.assertRaisesRegex(ValueError, "key-like"):
                        build_archive(root, ["receipt.txt"], root / "bad.zip")

    def test_mesh_archive_can_include_its_own_distribution_module(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(__file__).resolve().parents[1]
            output = Path(temp) / "mesh-module.zip"
            build_archive(root, ["fpga_mesh/distribution.py"], output)
            with zipfile.ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                self.assertIn("fpga_mesh/distribution.py", archive.namelist())

    def test_mesh_and_single_node_skill_are_separate_packages(self):
        tracked = [
            "README.md", "deploy/Join-FPGAMesh.ps1",
            "docs/deployment/OPERATIONS.md",
            "docs/deployment/SINGLE_NODE_PYNQ_Z2.md",
            "docs/deployment/HOST_TOOLCHAIN_2026-10-08.md",
            "docs/deployment/evidence/pynq-z2-live-2026-10-09/result.json",
            "skills/pynq-z2-single-node/SKILL.md",
            "skills/pynq-z2-single-node/scripts/preflight.py",
            "packaging/pynq-client/SKILL.md",
            "tests/test_pynq_z2_board_run.py",
            "tests/test_pynq_client_distribution.py",
        ]
        self.assertEqual(select_package_paths(tracked, "mesh"), [
            "README.md", "deploy/Join-FPGAMesh.ps1",
            "docs/deployment/OPERATIONS.md",
        ])
        self.assertEqual(select_package_paths(tracked, "pynq-skill"), [
            "skills/pynq-z2-single-node/SKILL.md",
            "skills/pynq-z2-single-node/scripts/preflight.py",
        ])

    def test_unknown_package_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "profile"):
            select_package_paths(["README.md"], "everything")

    def test_archive_contains_only_selected_source_and_verifiable_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "deploy").mkdir()
            (root / "deploy" / "Join.ps1").write_text("Write-Host ready", encoding="utf-8")
            (root / ".local").mkdir()
            (root / ".local" / "secret.txt").write_text("private", encoding="utf-8")
            target = root / "team.zip"
            build_archive(root, ["deploy/Join.ps1"], target, revision="test-rev")
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(sorted(archive.namelist()),
                                 ["MANIFEST.json", "deploy/Join.ps1"])
                manifest = json.loads(archive.read("MANIFEST.json"))
                entry = manifest["files"][0]
                self.assertEqual(entry["sha256"], hashlib.sha256(
                    archive.read("deploy/Join.ps1")
                ).hexdigest())
                self.assertEqual(manifest["revision"], "test-rev")

    def test_secret_path_or_key_material_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".local").mkdir()
            (root / ".local" / "secret.txt").write_text("private", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_archive(root, [".local/secret.txt"], root / "bad.zip")
            (root / "key.txt").write_text("sk-" + "a" * 40, encoding="utf-8")
            with self.assertRaises(ValueError):
                build_archive(root, ["key.txt"], root / "bad.zip")
            (root / "ssh-private.txt").write_text(
                "-----BEGIN " + "OPENSSH PRIVATE KEY-----\nprivate material\n"
                "-----END " + "OPENSSH PRIVATE KEY-----\n", encoding="ascii"
            )
            with self.assertRaisesRegex(ValueError, "key|private"):
                build_archive(root, ["ssh-private.txt"], root / "bad.zip")
            (root / "id_ed25519").write_text("opaque private bytes", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "private"):
                build_archive(root, ["id_ed25519"], root / "bad.zip")
            (root / "pgp-private.txt").write_text(
                "-----BEGIN PGP PRIVATE " + "KEY BLOCK-----\nprivate material\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "key-like"):
                build_archive(root, ["pgp-private.txt"], root / "bad.zip")
