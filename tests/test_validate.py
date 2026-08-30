import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.package import files_for, main as package_main
from scripts.validate import Checker


class ValidateTests(unittest.TestCase):
    def test_invalid_rebuild_preserves_previous_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            (root / "scripts").mkdir(parents=True)
            shutil.copy2(
                Path(__file__).resolve().parents[1] / "scripts/package.py",
                root / "scripts/package.py",
            )
            (root / "VERSION").write_text("0.1.1\n", encoding="utf-8")
            (root / "payload.txt").write_text("release content\n", encoding="utf-8")
            manifest = root / "package-manifest.json"
            manifest.write_text(json.dumps(["payload.txt"]), encoding="utf-8")
            output = root / "dist"
            command = [
                sys.executable,
                str(root / "scripts/package.py"),
                "--output",
                str(output),
            ]

            first = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            archive = output / "agent-team-0.1.1.zip"
            checksum = archive.with_suffix(".zip.sha256")
            previous = archive.read_bytes(), checksum.read_bytes()

            manifest.write_text(json.dumps(["missing.txt"]), encoding="utf-8")
            failed = subprocess.run(command, capture_output=True, text=True, check=False)

            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual((archive.read_bytes(), checksum.read_bytes()), previous)

    def test_second_promotion_failure_restores_release_pair(self) -> None:
        for archive_existed, checksum_existed in (
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ):
            with self.subTest(
                archive_existed=archive_existed,
                checksum_existed=checksum_existed,
            ), tempfile.TemporaryDirectory() as directory:
                output = Path(directory)
                archive = output / "agent-team-0.1.1.zip"
                checksum = archive.with_suffix(".zip.sha256")
                old_archive = b"previous archive bytes\n"
                old_checksum = b"previous checksum bytes\n"
                if archive_existed:
                    archive.write_bytes(old_archive)
                if checksum_existed:
                    checksum.write_bytes(old_checksum)

                original_replace = Path.replace
                checksum_failure_raised = False

                def fail_checksum_once(source: Path, target: Path) -> Path:
                    nonlocal checksum_failure_raised
                    if Path(target) == checksum and not checksum_failure_raised:
                        checksum_failure_raised = True
                        raise PermissionError("checksum is locked")
                    return original_replace(source, target)

                with patch(
                    "sys.argv",
                    ["package.py", "--output", str(output)],
                ), patch.object(
                    Path,
                    "replace",
                    autospec=True,
                    side_effect=fail_checksum_once,
                ):
                    with self.assertRaisesRegex(PermissionError, "checksum is locked"):
                        package_main()

                self.assertTrue(checksum_failure_raised)
                self.assertEqual(archive.exists(), archive_existed)
                self.assertEqual(checksum.exists(), checksum_existed)
                if archive_existed:
                    self.assertEqual(archive.read_bytes(), old_archive)
                if checksum_existed:
                    self.assertEqual(checksum.read_bytes(), old_checksum)
                expected = {
                    path.name
                    for path, existed in (
                        (archive, archive_existed),
                        (checksum, checksum_existed),
                    )
                    if existed
                }
                self.assertEqual({path.name for path in output.iterdir()}, expected)

    def test_release_validates_before_packaging(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/release.yml").read_text(encoding="utf-8")
        package = workflow.index("python3 scripts/package.py --output dist")
        self.assertLess(workflow.index("python3 scripts/validate.py"), package)
        self.assertLess(workflow.index("python3 -m unittest discover -s tests -v"), package)

    def test_readme_package_commands_track_version(self) -> None:
        checker = Checker(Path(__file__).resolve().parents[1])
        checker.run()
        self.assertIn("README package commands use VERSION", checker.checks)

    def test_checksum_write_supports_legacy_pathlib(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("sys.argv", ["package.py", "--output", directory]), patch.object(
                Path,
                "write_text",
                side_effect=TypeError("newline is unsupported"),
            ):
                self.assertEqual(package_main(), 0)

            archive = next(Path(directory).glob("*.zip"))
            checksum = archive.with_suffix(archive.suffix + ".sha256").read_bytes()
            self.assertTrue(checksum.endswith(f"  {archive.name}\n".encode("ascii")))

    def test_malformed_evaluation_entries_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evals = root / "evals"
            evals.mkdir()
            (evals / "tasks.json").write_text(
                json.dumps({"tasks": ["bad", {}, {}, {}, {}]}),
                encoding="utf-8",
            )
            (evals / "results.v0.1.json").write_text(
                json.dumps({"status": "calibration_fixture", "arms": [{"id": []}], "claims": []}),
                encoding="utf-8",
            )
            checker = Checker(root)
            checker.run()
            self.assertIn("evaluation task IDs are unique", checker.failures)
            self.assertIn("evaluation includes strong solo and current arms", checker.failures)

    def test_malformed_manifest_entry_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "package-manifest.json"
            for value, failure in (
                (None, "package-manifest.json is a non-empty string array"),
                ("bad\0path", "manifest entry is a valid repo path"),
                ("bad\ud800path", "manifest entry is a valid repo path"),
            ):
                with self.subTest(value=repr(value)):
                    manifest.write_text(json.dumps([value]), encoding="utf-8")
                    checker = Checker(root)
                    checker.check_manifest()
                    self.assertTrue(any(failure in item for item in checker.failures))
                    with self.assertRaises(ValueError):
                        files_for(root)

    def test_unreadable_or_unresolvable_manifest_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "package-manifest.json"
            manifest.write_bytes(b'["\xff"]')
            checker = Checker(root)
            checker.check_manifest()
            self.assertTrue(any("invalid JSON" in item for item in checker.failures))

            loop = root / "loop"
            loop.symlink_to("loop")
            manifest.write_text(json.dumps(["loop"]), encoding="utf-8")
            checker = Checker(root)
            checker.check_manifest()
            self.assertTrue(any("valid repo path" in item for item in checker.failures))
            with self.assertRaises(ValueError):
                files_for(root)

    def test_unreadable_required_text_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_bytes(b"\xff")

            checker = Checker(root)
            checker.run()
            self.assertIn("readable UTF-8 text: README.md", checker.failures)

    def test_unreadable_optional_packaged_text_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / "__pycache__" / "optional-policy.yaml"
            policy.parent.mkdir()
            policy.write_bytes(b"\xff")
            (root / "package-manifest.json").write_text(
                json.dumps([policy.relative_to(root).as_posix()]),
                encoding="utf-8",
            )
            self.assertEqual(files_for(root), [policy])

            checker = Checker(root)
            checker.run()
            self.assertIn(
                "readable UTF-8 text: __pycache__/optional-policy.yaml",
                checker.failures,
            )

    def test_generated_python_bytecode_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "validate.pyc").write_bytes(b"\xff")

            checker = Checker(root)
            checker.run()
            self.assertFalse(
                any("__pycache__" in failure for failure in checker.failures),
            )

    def test_manifest_symlink_is_reported_before_packaging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target.txt").write_text("fixture\n", encoding="utf-8")
            (root / "link.txt").symlink_to("target.txt")
            (root / "package-manifest.json").write_text('["link.txt"]', encoding="utf-8")

            checker = Checker(root)
            checker.check_manifest()
            self.assertTrue(any("repo file" in item for item in checker.failures))
            with self.assertRaises(ValueError):
                files_for(root)


if __name__ == "__main__":
    unittest.main()
