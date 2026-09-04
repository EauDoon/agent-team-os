import json
import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.package import files_for, main as package_main, version_for
from scripts.validate import Checker, _display_path, main as validate_main


def _symlinks_supported() -> bool:
    """Return True when this platform lets the test user create symlinks.

    Windows requires elevation (or developer mode) to create symlinks, so the
    symlink-specific checks are skipped there instead of erroring.
    """
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        target = base / "symlink-target"
        target.write_text("x", encoding="utf-8")
        probe = base / "symlink-probe"
        try:
            probe.symlink_to(target.name)
            return True
        except (OSError, NotImplementedError):
            return False
        finally:
            try:
                probe.unlink()
            except OSError:
                pass


SYMLINKS_SUPPORTED = _symlinks_supported()


class ValidateTests(unittest.TestCase):
    def test_package_version_cannot_escape_artifact_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            version_path = root / "VERSION"
            version_path.write_text("1.2.3\n", encoding="utf-8")
            self.assertEqual(version_for(root), "1.2.3")

            for invalid in (
                "",
                "1.2",
                "01.2.3",
                "1.2.3-alpha",
                "../1.2.3",
                "1.2.3/../../escape",
            ):
                with self.subTest(version=invalid):
                    version_path.write_text(invalid, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "semantic X.Y.Z"):
                        version_for(root)

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
                version = version_for(Path(__file__).resolve().parents[1])
                archive = output / f"agent-team-{version}.zip"
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
        # The release step must require a versioned notes file, not silently fall back to a stale one.
        self.assertIn('NOTES="docs/release-notes-${VERSION}.md"', workflow)
        self.assertNotIn('release-notes-v0.1.0.md', workflow)

    def test_readme_package_commands_track_version(self) -> None:
        checker = Checker(Path(__file__).resolve().parents[1])
        checker.run()
        self.assertIn("README package commands use VERSION", checker.checks)

    def test_release_notes_references_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs" / "release-notes-0.1.0.md").write_text(
                "notes\n", encoding="utf-8"
            )
            (root / "README.md").write_text(
                "good: release-notes-0.1.0.md\nbad: release-notes-v0.1.0.md\n",
                encoding="utf-8",
            )
            checker = Checker(root)
            checker.check_release_notes_references()
            failures = "\n".join(checker.failures)
            self.assertIn("release-notes-v0.1.0.md", failures)
            self.assertNotIn("release-notes-0.1.0.md", failures)

    def test_result_fixture_must_conform_to_schema(self) -> None:
        schema = {
            "required": ["result_version", "status", "arms", "claims"],
            "properties": {
                "result_version": {"const": "agent-team-eval/v0.1"},
                "status": {"enum": ["calibration_fixture", "complete"]},
                "arms": {"items": {"required": ["id", "label", "results"]}},
            },
        }
        good = {
            "result_version": "agent-team-eval/v0.1",
            "status": "calibration_fixture",
            "arms": [{"id": "solo", "label": "s", "results": []}],
            "claims": [],
        }
        checker = Checker(Path("."))
        checker.check_result_conformance(schema, good)
        self.assertEqual(checker.failures, [])

        bad = {k: v for k, v in good.items() if k != "claims"}
        bad["status"] = "not-a-real-status"
        bad["result_version"] = "wrong"
        bad["arms"] = [{"id": "solo"}]
        checker = Checker(Path("."))
        checker.check_result_conformance(schema, bad)
        joined = "\n".join(checker.failures)
        self.assertIn("result.status is a schema-allowed value", joined)
        self.assertIn("result.result_version matches schema const", joined)
        self.assertIn("arm has required key label", joined)
        self.assertIn("result has required key claims", joined)

    def test_link_destination_with_parenthesis_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target(x).md").write_text("ok\n", encoding="utf-8")
            (root / "README.md").write_text(
                "[ok](target(x).md)\n",
                encoding="utf-8",
            )
            checker = Checker(root)
            checker.check_links()
            self.assertEqual(checker.failures, [])
            self.assertTrue(
                any("link exists" in item and "target(x).md" in item for item in checker.checks),
            )

    def test_connect_violations_detects_contract_breaks(self) -> None:
        schema = {
            "required": ["connect_version", "type", "message_id", "correlation_id", "from", "to", "payload"],
            "properties": {
                "connect_version": {"const": "agent-team-connect/v0.1"},
                "type": {"enum": ["request", "response", "handoff", "status", "result"]},
            },
            "$defs": {
                "request": {"required": ["objective", "completion_test"]},
                "handoff": {
                    "properties": {
                        "role_brief": {
                            "required": ["role", "access_scope", "task", "evidence", "output_contract", "stop_condition"]
                        }
                    }
                },
            },
        }
        checker = Checker(Path("."))

        good = {
            "connect_version": "agent-team-connect/v0.1",
            "type": "request",
            "message_id": "m",
            "correlation_id": "c",
            "from": "a",
            "to": "b",
            "payload": {"objective": "o", "completion_test": "t"},
        }
        self.assertEqual(checker.connect_violations(good, schema), [])

        missing_field = {k: v for k, v in good.items() if k != "correlation_id"}
        self.assertIn(
            "missing required field correlation_id",
            checker.connect_violations(missing_field, schema),
        )

        wrong_type = dict(good, type="ping")
        self.assertTrue(
            any(v.startswith("type must be one of") for v in checker.connect_violations(wrong_type, schema))
        )

        missing_payload_key = dict(good, payload={"objective": "o"})
        self.assertIn(
            "payload missing required field completion_test",
            checker.connect_violations(missing_payload_key, schema),
        )

        bad_handoff = {
            "connect_version": "agent-team-connect/v0.1",
            "type": "handoff",
            "message_id": "m",
            "correlation_id": "c",
            "from": "a",
            "to": "b",
            "payload": {"role_brief": {"role": "Scout"}},
        }
        self.assertIn(
            "role_brief missing required field task",
            checker.connect_violations(bad_handoff, schema),
        )

    def test_connect_conformance_suite_outcomes_are_checked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "schemas").mkdir()
            (root / "conformance" / "connect").mkdir(parents=True)
            schema = {
                "required": ["connect_version", "type", "message_id", "correlation_id", "from", "to", "payload"],
                "properties": {
                    "connect_version": {"const": "agent-team-connect/v0.1"},
                    "type": {"enum": ["request", "response", "handoff", "status", "result"]},
                },
                "$defs": {"request": {"required": ["objective", "completion_test"]}},
            }
            (root / "schemas" / "connect.schema.json").write_text(json.dumps(schema), encoding="utf-8")

            def msg(payload):
                return {
                    "connect_version": "agent-team-connect/v0.1",
                    "type": "request",
                    "message_id": "m",
                    "correlation_id": "c",
                    "from": "a",
                    "to": "b",
                    "payload": payload,
                }

            good = msg({"objective": "o", "completion_test": "t"})
            bad = msg({"objective": "o"})
            suite = {
                "cases": [
                    {"name": "good-1", "expect": "valid", "message": good},
                    {"name": "good-2", "expect": "valid", "message": good},
                    {"name": "good-3", "expect": "valid", "message": good},
                    {"name": "bad", "expect": "invalid", "message": bad},
                    {"name": "lying", "expect": "valid", "message": bad},
                ]
            }
            (root / "conformance" / "connect" / "cases.json").write_text(
                json.dumps(suite), encoding="utf-8"
            )
            checker = Checker(root)
            checker.check_connect_conformance()
            joined = "\n".join(checker.failures)
            self.assertIn("connect conformance case lying matches its expectation", joined)
            self.assertNotIn("connect conformance case good-1", joined)
            self.assertNotIn("connect conformance case bad", joined)

    def test_connect_examples_are_valid_messages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "schemas").mkdir()
            schema = {
                "required": ["connect_version", "type", "message_id", "correlation_id", "from", "to", "payload"],
                "properties": {
                    "connect_version": {"const": "agent-team-connect/v0.1"},
                    "type": {"enum": ["request", "response", "handoff", "status", "result"]},
                },
                "$defs": {
                    "request": {"required": ["objective", "completion_test"]},
                    "handoff": {
                        "properties": {
                            "role_brief": {
                                "required": ["role", "access_scope", "task", "evidence", "output_contract", "stop_condition"]
                            }
                        }
                    },
                },
            }
            (root / "schemas" / "connect.schema.json").write_text(json.dumps(schema), encoding="utf-8")

            def msg(payload):
                base = {
                    "connect_version": "agent-team-connect/v0.1",
                    "message_id": "m1",
                    "correlation_id": "c1",
                    "from": "a",
                    "to": "b",
                }
                base.update(payload)
                return base

            valid = msg({"type": "request", "payload": {"objective": "o", "completion_test": "t"}})
            (root / "connect.md").write_text("```json\n" + json.dumps(valid) + "\n```\n", encoding="utf-8")
            checker = Checker(root)
            checker.check_connect_examples()
            self.assertEqual(checker.failures, [])

            broken = msg({"type": "request", "payload": {"objective": "o"}})
            (root / "connect.md").write_text("```json\n" + json.dumps(broken) + "\n```\n", encoding="utf-8")
            checker = Checker(root)
            checker.check_connect_examples()
            self.assertIn(
                "connect example 1 payload missing required field completion_test",
                checker.failures,
            )

    def test_connect_schema_requires_envelope_and_role_brief(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "schemas").mkdir()
            good = {
                "required": ["connect_version", "type", "message_id", "correlation_id", "from", "to", "payload"],
                "properties": {"type": {"enum": ["request", "response", "handoff", "status", "result"]}},
                "$defs": {
                    "handoff": {
                        "properties": {
                            "role_brief": {
                                "required": ["role", "access_scope", "task", "evidence", "output_contract", "stop_condition"]
                            }
                        }
                    }
                },
            }
            (root / "schemas" / "connect.schema.json").write_text(json.dumps(good), encoding="utf-8")
            checker = Checker(root)
            checker.check_connect()
            self.assertEqual(checker.failures, [])

            bad = json.loads(json.dumps(good))
            bad["required"].remove("payload")
            bad["$defs"]["handoff"]["properties"]["role_brief"]["required"] = ["role"]
            (root / "schemas" / "connect.schema.json").write_text(json.dumps(bad), encoding="utf-8")
            checker = Checker(root)
            checker.check_connect()
            joined = "\n".join(checker.failures)
            self.assertIn("connect schema requires the message envelope", joined)
            self.assertIn("connect handoff requires the six role brief fields", joined)

    def test_changelog_top_entry_must_match_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## 0.1.1\n\n- old\n",
                encoding="utf-8",
            )
            checker = Checker(root)
            checker.check_changelog_version("0.1.2")
            self.assertIn("CHANGELOG top entry matches VERSION", checker.failures)

            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## 0.1.2\n\n- new\n\n## 0.1.1\n\n- old\n",
                encoding="utf-8",
            )
            checker = Checker(root)
            checker.check_changelog_version("0.1.2")
            self.assertNotIn("CHANGELOG top entry matches VERSION", checker.failures)
            self.assertIn("CHANGELOG top entry matches VERSION", checker.checks)

            (root / "CHANGELOG.md").write_text("# Changelog\n\nNo version yet.\n",
                                                encoding="utf-8")
            checker = Checker(root)
            checker.check_changelog_version("0.1.2")
            self.assertIn("CHANGELOG top entry matches VERSION", checker.failures)

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

    def test_manifest_surrogate_diagnostic_is_utf8_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = "bad\ud800path"
            (root / "package-manifest.json").write_text(
                json.dumps([entry]), encoding="utf-8",
            )
            checker = Checker(root)
            checker.check_manifest()

            self.assertIn(
                f"manifest entry is a valid repo path: {entry!r}",
                checker.failures,
            )
            for failure in checker.failures:
                failure.encode("utf-8")

            output = io.StringIO()
            with patch(
                "sys.argv",
                ["validate.py", "--repo-root", str(root)],
            ), contextlib.redirect_stdout(output):
                self.assertEqual(validate_main(), 1)
            output.getvalue().encode("utf-8")

    def test_manifest_accepts_valid_supplementary_unicode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = "paired-\U0001f600.txt"
            (root / entry).write_text("valid\n", encoding="utf-8")
            (root / "package-manifest.json").write_text(
                json.dumps([entry]), encoding="utf-8",
            )
            checker = Checker(root)
            checker.check_manifest()

            self.assertIn(f"manifest entry is a repo file: {entry}", checker.checks)
            self.assertEqual(files_for(root), [root / entry])

    def test_path_display_escapes_only_invalid_unicode_scalars(self) -> None:
        root = Path("repo")
        self.assertEqual(
            _display_path(root / "bad\ud800.txt", root),
            r"bad\ud800.txt",
        )
        self.assertEqual(
            _display_path(root / "paired-\U0001f600.txt", root),
            "paired-\U0001f600.txt",
        )

    def test_encoded_parent_escape_is_checked_after_url_decoding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            root = parent / "repo"
            decoy = root / "%2e%2e"
            decoy.mkdir(parents=True)
            (decoy / "outside.md").write_text("decoy\n", encoding="utf-8")
            (parent / "outside.md").write_text("outside\n", encoding="utf-8")
            (root / "README.md").write_text(
                "[outside](%2e%2e/outside.md)\n",
                encoding="utf-8",
            )

            checker = Checker(root)
            checker.check_links()

            self.assertIn(
                "link stays inside repo: README.md -> %2e%2e/outside.md",
                checker.failures,
            )

    def test_unapproved_link_schemes_and_authorities_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text(
                "\n".join(
                    (
                        "[script](javascript:README.md)",
                        "[data](data:README.md)",
                        "[network](//server/share)",
                        "[file](file://server/share)",
                    )
                ),
                encoding="utf-8",
            )

            checker = Checker(root)
            checker.check_links()

            self.assertEqual(len(checker.failures), 4)
            self.assertTrue(any("javascript:README.md" in item for item in checker.failures))
            self.assertTrue(any("data:README.md" in item for item in checker.failures))
            self.assertTrue(any("//server/share" in item for item in checker.failures))
            self.assertTrue(any("file://server/share" in item for item in checker.failures))

    def test_checker_output_handles_surrogate_filename_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "bad\ud800.txt"
            try:
                path.write_text("valid\n", encoding="utf-8")
            except (OSError, UnicodeError):
                self.skipTest("filesystem does not support lone-surrogate filenames")

            output_bytes = io.BytesIO()
            output = io.TextIOWrapper(output_bytes, encoding="utf-8", errors="strict")
            with patch(
                "sys.argv",
                ["validate.py", "--repo-root", str(root)],
            ), contextlib.redirect_stdout(output):
                self.assertEqual(validate_main(), 1)
            output.flush()

            rendered = output_bytes.getvalue().decode("utf-8")
            self.assertIn(r"bad\ud800.txt", rendered)

    def test_unreadable_or_unresolvable_manifest_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "package-manifest.json"
            manifest.write_bytes(b'["\xff"]')
            checker = Checker(root)
            checker.check_manifest()
            self.assertTrue(any("invalid JSON" in item for item in checker.failures))

            loop = root / "loop"
            try:
                loop.symlink_to("loop")
            except (OSError, NotImplementedError):
                return  # symlink creation not permitted; JSON check above already ran
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

    @unittest.skipUnless(
        SYMLINKS_SUPPORTED,
        "symlink creation is not permitted on this platform",
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
