#!/usr/bin/env python3
"""Dependency-light checks for the Agent Team public contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


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

    def text(self, relative: str) -> str:
        path = self.root / relative
        self.ok(path.is_file(), f"file exists: {relative}")
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def json_file(self, relative: str) -> object:
        value = None
        try:
            value = json.loads(self.text(relative))
            self.checks.append(f"valid JSON: {relative}")
        except (json.JSONDecodeError, OSError) as exc:
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
        missing = [field for field in FIELDS if not re.search(rf"\b{re.escape(field)}\b", content)]
        self.ok(not missing, f"{label} contains six fields" if not missing else f"{label} missing: {', '.join(missing)}")

    def check_links(self) -> None:
        for path in sorted(self.root.rglob("*.md")):
            if any(part in {".git", "dist"} for part in path.parts):
                continue
            content = path.read_text(encoding="utf-8")
            for raw_target in LINK.findall(content):
                target = raw_target.strip().split()[0].strip("<>")
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                relative = target.split("#", 1)[0]
                if not relative:
                    continue
                candidate = (path.parent / relative).resolve()
                self.ok(candidate.exists(), f"link exists: {path.relative_to(self.root)} -> {target}")

    def run(self) -> None:
        skill = self.text("skill/agent-team-os/SKILL.md")
        readme = self.text("README.md")
        template = self.text("templates/role-brief.md")
        audit = self.text("templates/audit-report.md")
        examples = self.text("examples/routing-scenarios.md")
        self.check_frontmatter(skill)
        self.check_fields("SKILL.md", skill)
        self.check_fields("role brief template", template)
        self.check_fields("routing examples", examples)
        self.ok("## Findings" in audit and "## Recommendation" in audit, "audit report template has findings and recommendation sections")
        self.ok("Agent Team" in readme, "public copy uses Agent Team")
        self.ok('display_name: "Agent Team"' in self.text("skill/agent-team-os/agents/openai.yaml"), "metadata display name uses Agent Team")
        self.ok("all five" not in skill.lower(), "old five-field wording is absent")
        self.ok("Agent Team OS" not in readme, "old public display name is absent")

        schema = self.json_file("schemas/role-brief.schema.json")
        if isinstance(schema, dict):
            required = schema.get("required", [])
            expected = {field.lower().replace(" ", "_") for field in FIELDS}
            self.ok(expected.issubset(set(required)), "role brief schema requires six fields")

        tasks = self.json_file("evals/tasks.json")
        if isinstance(tasks, dict):
            entries = tasks.get("tasks")
            ids = [item.get("id") for item in entries] if isinstance(entries, list) else []
            self.ok(isinstance(entries, list) and 5 <= len(entries) <= 7, "evaluation suite has five to seven tasks")
            self.ok(len(ids) == len(set(ids)) and all(isinstance(item, str) for item in ids), "evaluation task IDs are unique")

        result_schema = self.json_file("evals/result.schema.json")
        result = self.json_file("evals/results.v0.1.json")
        if isinstance(result_schema, dict):
            self.ok(set(result_schema.get("required", [])) >= {"result_version", "status", "arms", "claims"}, "result schema has required envelope")
        if isinstance(result, dict):
            arms = result.get("arms", [])
            arm_ids = [item.get("id") for item in arms] if isinstance(arms, list) else []
            self.ok(result.get("status") == "calibration_fixture", "evaluation result remains an empty calibration fixture")
            self.ok(set(arm_ids) == {"solo", "current"}, "evaluation includes strong solo and current arms")
            self.ok(result.get("claims") == [], "evaluation fixture makes no performance claims")

        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or ".git" in path.parts or "dist" in path.parts:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            self.ok("\u2014" not in content, f"no em dash: {path.relative_to(self.root)}")
            if path.suffix in {".md", ".yaml", ".yml", ".json"}:
                match = UNSAFE.search(content)
                self.ok(match is None, f"no prohibited unsafe structure: {path.relative_to(self.root)}")
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
