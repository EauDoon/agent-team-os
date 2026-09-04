#!/usr/bin/env python3
"""Dependency-light checks for the Agent Team public contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit


FIELDS = [
    "Role",
    "Access scope",
    "Task",
    "Evidence",
    "Output contract",
    "Stop condition",
]
UNSAFE = re.compile(
    r"(?i)\b(?:unlimited\s+access|all\s+access|ignore\s+(?:authorization|review)|"
    r"disable\s+(?:audit|safety)|exfiltrat\w*|delete\s+.+without\s+approval)\b"
)
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
BINARY_SUFFIXES = {".bin", ".gif", ".ico", ".jpeg", ".jpg", ".pdf", ".png", ".pyc", ".webp", ".zip"}
EXTERNAL_SCHEMES = {"http", "https", "mailto"}


def _display_path(path: Path, root: Path) -> str:
    """Render a repo-relative path without leaking lone surrogates to output."""
    relative = path.relative_to(root).as_posix()
    return relative.encode("utf-8", errors="backslashreplace").decode("utf-8")


def object_ids(value: object) -> list[object] | None:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        return None
    return [item.get("id") for item in value]


class Checker:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.failures: list[str] = []
        self.checks: list[str] = []

    def ok(self, condition: bool, message: str) -> None:
        if condition:
            self.checks.append(message)
        else:
            self.failures.append(message)

    def read_text(self, path: Path, *, allow_binary: bool = False) -> str | None:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            if allow_binary:
                return None
        except OSError:
            pass
        message = f"readable UTF-8 text: {_display_path(path, self.root)}"
        if message not in self.failures:
            self.failures.append(message)
        return None

    def text(self, relative: str) -> str:
        path = self.root / relative
        exists = path.is_file()
        self.ok(exists, f"file exists: {relative}")
        return (self.read_text(path) or "") if exists else ""

    def json_file(self, relative: str) -> object:
        value = None
        try:
            value = json.loads(self.text(relative))
            self.checks.append(f"valid JSON: {relative}")
        except (json.JSONDecodeError, OSError, UnicodeError) as exc:
            self.failures.append(f"invalid JSON {relative}: {exc}")
        return value

    def check_frontmatter(self, content: str) -> None:
        lines = content.splitlines()
        self.ok(lines[:1] == ["---"], "SKILL.md starts with YAML frontmatter")
        try:
            end = lines.index("---", 1)
        except ValueError:
            end = -1
        self.ok(end > 1, "SKILL.md closes YAML frontmatter")
        values: dict[str, str] = {}
        if end > 1:
            for line in lines[1:end]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    values[key.strip()] = value.strip().strip('"')
        self.ok(values.get("name") == "agent-team-os", "frontmatter keeps technical skill identifier")
        self.ok(bool(values.get("description")), "frontmatter has a description")

    def check_fields(self, label: str, content: str) -> None:
        missing = [
            field
            for field in FIELDS
            if self._field_label(field).search(content) is None
        ]
        self.ok(not missing, f"{label} contains six fields" if not missing else f"{label} missing: {', '.join(missing)}")

    @staticmethod
    def _field_label(field: str) -> "re.Pattern[str]":
        """Match a field as a label, not as a prose mention.

        The six field names appear in three controlled shapes: a markdown
        heading (``## Role``), a ``Field:`` line in the SKILL.md code block, or
        a table cell (``| Role |``). A bare word such as a prose mention of the
        role no longer satisfies the presence check.
        """
        escaped = re.escape(field)
        pattern = (
            r"(?m)(?:^\s*#{1,6}\s+" + escaped + r"\s*$"
            r"|^\s*" + escaped + r":\s"
            r"|\|\s*" + escaped + r"\s*\|)"
        )
        return re.compile(pattern)

    def check_links(self) -> None:
        for path in sorted(self.root.rglob("*.md")):
            if any(part in {".git", "dist"} for part in path.parts):
                continue
            content = self.read_text(path)
            if content is None:
                continue
            display_path = _display_path(path, self.root)
            for raw_target in LINK.findall(content):
                target = raw_target.strip().split()[0].strip("<>")
                try:
                    parsed = urlsplit(target)
                except ValueError:
                    self.ok(False, f"link target is valid: {display_path} -> {target}")
                    continue
                scheme = parsed.scheme.lower()
                if scheme in EXTERNAL_SCHEMES:
                    continue
                if scheme:
                    self.ok(False, f"link scheme is allowed: {display_path} -> {target}")
                    continue
                if parsed.netloc:
                    self.ok(False, f"link has no remote authority: {display_path} -> {target}")
                    continue
                if not parsed.path:
                    continue
                try:
                    relative = unquote(parsed.path, encoding="utf-8", errors="strict")
                except UnicodeDecodeError:
                    self.ok(False, f"link path is UTF-8: {display_path} -> {target}")
                    continue
                try:
                    candidate = (path.parent / relative.replace("\\", "/")).resolve()
                except (OSError, ValueError):
                    self.ok(False, f"link target is valid: {display_path} -> {target}")
                    continue
                root_resolved = self.root.resolve()
                inside_repo = root_resolved in candidate.parents or candidate == root_resolved
                self.ok(
                    inside_repo,
                    f"link stays inside repo: {display_path} -> {target}",
                )
                if not inside_repo:
                    continue
                self.ok(candidate.exists(), f"link exists: {display_path} -> {target}")

    def check_manifest(self) -> None:
        manifest = self.json_file("package-manifest.json")
        if not isinstance(manifest, list) or not manifest:
            self.ok(False, "package-manifest.json is a non-empty string array")
            return
        valid_entries = all(isinstance(item, str) and item for item in manifest)
        self.ok(valid_entries, "package-manifest.json is a non-empty string array")
        if not valid_entries:
            return
        self.ok(len(manifest) == len(set(manifest)), "package-manifest.json has no duplicate entries")
        root_resolved = self.root.resolve()
        for entry in manifest:
            if any(part in {"", ".", ".."} for part in PurePosixPath(entry).parts):
                self.ok(False, f"manifest entry has no path traversal: {entry!r}")
                continue
            try:
                entry.encode("utf-8")
            except UnicodeEncodeError:
                self.ok(False, f"manifest entry is a valid repo path: {entry!r}")
                continue
            try:
                path = root_resolved / entry
                candidate = path.resolve()
                safe = path.is_file() and not path.is_symlink() and root_resolved in candidate.parents
            except (OSError, RuntimeError, UnicodeError, ValueError):
                self.ok(False, f"manifest entry is a valid repo path: {entry!r}")
                continue
            self.ok(
                safe,
                f"manifest entry is a repo file: {entry}",
            )

    def check_changelog_version(self, current: str) -> None:
        """Ensure the newest CHANGELOG entry matches the current VERSION.

        The release process relies on the version being consistent across
        VERSION, the README, the changelog, and the release notes; the README is
        already checked, so the changelog's top entry is checked too.
        """
        changelog = self.text("CHANGELOG.md")
        versions = re.findall(r"(?m)^##\s+(\d+\.\d+\.\d+)\s*$", changelog)
        self.ok(
            bool(versions) and versions[0] == current,
            "CHANGELOG top entry matches VERSION",
        )

    def run(self) -> None:
        skill = self.text("skill/agent-team-os/SKILL.md")
        readme = self.text("README.md")
        template = self.text("templates/role-brief.md")
        audit = self.text("templates/audit-report.md")
        examples = self.text("examples/routing-scenarios.md")
        self.check_frontmatter(skill)
        self.check_manifest()
        self.check_fields("SKILL.md", skill)
        self.check_fields("role brief template", template)
        self.check_fields("routing examples", examples)
        self.ok("## Findings" in audit and "## Recommendation" in audit, "audit report template has findings and recommendation sections")
        self.ok("Agent Team" in readme, "public copy uses Agent Team")
        self.ok('display_name: "Agent Team"' in self.text("skill/agent-team-os/agents/openai.yaml"), "metadata display name uses Agent Team")
        self.ok("all five" not in skill.lower(), "old five-field wording is absent")
        self.ok("Agent Team OS" not in readme, "old public display name is absent")
        version = self.text("VERSION").strip()
        documented_versions = set(re.findall(r"agent-team-(\d+\.\d+\.\d+)\.zip", readme))
        self.ok(documented_versions == {version}, "README package commands use VERSION")
        self.check_changelog_version(version)

        schema = self.json_file("schemas/role-brief.schema.json")
        if isinstance(schema, dict):
            required = schema.get("required", [])
            expected = {field.lower().replace(" ", "_") for field in FIELDS}
            self.ok(expected.issubset(set(required)), "role brief schema requires six fields")

        tasks = self.json_file("evals/tasks.json")
        if isinstance(tasks, dict):
            entries = tasks.get("tasks")
            ids = object_ids(entries)
            self.ok(isinstance(entries, list) and 5 <= len(entries) <= 7, "evaluation suite has five to seven tasks")
            self.ok(ids is not None and all(isinstance(item, str) for item in ids) and len(ids) == len(set(ids)), "evaluation task IDs are unique")

        result_schema = self.json_file("evals/result.schema.json")
        result = self.json_file("evals/results.v0.1.json")
        if isinstance(result_schema, dict):
            self.ok(set(result_schema.get("required", [])) >= {"result_version", "status", "arms", "claims"}, "result schema has required envelope")
        if isinstance(result, dict):
            arms = result.get("arms", [])
            arm_ids = object_ids(arms)
            self.ok(result.get("status") == "calibration_fixture", "evaluation result remains an empty calibration fixture")
            self.ok(arm_ids is not None and all(isinstance(item, str) for item in arm_ids) and set(arm_ids) == {"solo", "current"}, "evaluation includes strong solo and current arms")
            self.ok(result.get("claims") == [], "evaluation fixture makes no performance claims")

        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or ".git" in path.parts or "dist" in path.parts:
                continue
            content = self.read_text(
                path,
                allow_binary=path.suffix.lower() in BINARY_SUFFIXES,
            )
            if content is None:
                continue
            display_path = _display_path(path, self.root)
            self.ok("\u2014" not in content, f"no em dash: {display_path}")
            if path.suffix in {".md", ".yaml", ".yml", ".json"}:
                match = UNSAFE.search(content)
                self.ok(match is None, f"no prohibited unsafe structure: {display_path}")
        self.check_links()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    checker = Checker(args.repo_root.resolve())
    checker.run()
    payload = {"ok": not checker.failures, "checks": checker.checks, "failures": checker.failures}
    if args.as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for item in checker.checks:
            print(f"PASS {item}")
        for item in checker.failures:
            print(f"FAIL {item}")
        print(f"{len(checker.checks)} checks, {len(checker.failures)} failures")
    return 0 if not checker.failures else 1


if __name__ == "__main__":
    sys.exit(main())
