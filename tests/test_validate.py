import json
import tempfile
import unittest
from pathlib import Path

from scripts.package import files_for
from scripts.validate import Checker


class ValidateTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
