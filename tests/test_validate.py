import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.package import files_for, main as package_main
from scripts.validate import Checker


class ValidateTests(unittest.TestCase):
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
