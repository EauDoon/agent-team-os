#!/usr/bin/env python3
"""Dependency-light checks for the Agent Team public contract."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

try:
    from .contracts import KEYWORDS as SCHEMA_KEYWORDS, keyword_value_problems, violations as schema_violations
    from .version import add_version_flag
    from .workflows import BASELINE_CAPABILITIES, negotiate, refusal_text_violations
except ImportError:
    from contracts import KEYWORDS as SCHEMA_KEYWORDS, keyword_value_problems, violations as schema_violations
    from version import add_version_flag
    from workflows import BASELINE_CAPABILITIES, negotiate, refusal_text_violations


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
LINK = re.compile(r"\[[^\]]+\]\(([^()]*(?:\([^()]*\))?[^()]*)\)")
BINARY_SUFFIXES = {".bin", ".gif", ".ico", ".jpeg", ".jpg", ".pdf", ".png", ".pyc", ".webp", ".zip"}
EXTERNAL_SCHEMES = {"http", "https", "mailto"}
# Directory names pruned below the checked root. They hold build output, VCS
# state or local environments, never reviewed source. `__pycache__` is not here:
# a manifest may list a text file under it, and that file must still be read.
IGNORED_DIRS = frozenset({
    ".git", "dist", ".venv", "venv", "node_modules", ".tox",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
})
# Every file under these trees is distributable and must ship in the package.
SHIPPED_TREES = ("conformance", "docs", "evals", "examples", "schemas", "scripts", "skill", "templates")
SHIPPED_ROOT_FILES = (
    "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE", "PROVENANCE.md", "README.md",
    "SECURITY.md", "VERSION", "connect.md", "package-manifest.json",
)


def _display_path(path: Path, root: Path) -> str:
    """Render a repo-relative path without leaking lone surrogates to output."""
    relative = path.relative_to(root).as_posix()
    return relative.encode("utf-8", errors="backslashreplace").decode("utf-8")


def schema_identifiers(node: object, location: str = "$"):
    """Yield each `$id` with its location, including ids nested under `$defs`."""
    if isinstance(node, dict):
        if "$id" in node:
            yield location, node.get("$id")
        for key, value in node.items():
            yield from schema_identifiers(value, f"{location}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from schema_identifiers(value, f"{location}[{index}]")


def _json_object(items):
    """Reject a repeated key instead of keeping the last value."""
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def object_ids(value: object) -> list[object] | None:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        return None
    return [item.get("id") for item in value]


def schema_problems(schema: dict) -> list[str]:
    """Return located keywords the bundled validator cannot enforce.

    ``contracts.violations`` rejects an unsupported keyword only when a check
    actually reaches that subschema, so a misspelled ``requred`` in a branch no
    fixture visits stays silent and the field it should have constrained is
    never constrained. Every subschema is inspected here instead, and every
    local reference is resolved, because an unresolvable one fails only when a
    document happens to traverse it. Keyword values are checked at schema
    positions only, so a property that happens to be named ``type`` is data.
    """
    problems: list[str] = []

    def walk(node: object, location: str) -> None:
        if not isinstance(node, dict):
            return
        for keyword in sorted(set(node) - SCHEMA_KEYWORDS):
            problems.append(f"{location}: unsupported keyword {keyword}")
        for problem in keyword_value_problems(node):
            problems.append(f"{location}: {problem}")
        ref = node.get("$ref")
        if isinstance(ref, str):
            target: object = schema if ref.startswith("#/") else None
            for token in ref[2:].split("/"):
                if not isinstance(target, dict):
                    break
                target = target.get(token.replace("~1", "/").replace("~0", "~"))
            if not isinstance(target, dict):
                problems.append(f"{location}: unresolved local reference {ref}")
        # Only these keywords hold subschemas. Every other value is plain data,
        # such as the field names inside `properties` or the members of `enum`.
        for key, value in node.items():
            if key in ("properties", "$defs") and isinstance(value, dict):
                for name, nested in value.items():
                    walk(nested, f"{location}.{key}.{name}")
            elif key == "allOf" and isinstance(value, list):
                for index, nested in enumerate(value):
                    walk(nested, f"{location}.{key}[{index}]")
            elif key in ("items", "additionalProperties", "if", "then", "else"):
                walk(value, f"{location}.{key}")

    walk(schema, "$")
    return problems


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

    def repo_files(self, suffixes: set[str] | None = None) -> list[Path]:
        """Return checked files under the root, pruning ignored directory names.

        Only names below the root are tested. An ancestor of the root that is
        named ``dist`` or ``.git`` (an extracted package under ``dist/expanded``,
        for example) must not turn every check into a silent pass.
        """
        found: list[Path] = []
        for directory, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [name for name in dirnames if name not in IGNORED_DIRS]
            for name in filenames:
                path = Path(directory) / name
                if suffixes is not None and path.suffix not in suffixes:
                    continue
                if path.is_file():
                    found.append(path)
        return sorted(found)

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
            value = json.loads(self.text(relative), object_pairs_hook=_json_object)
            self.checks.append(f"valid JSON: {relative}")
        except (json.JSONDecodeError, OSError, UnicodeError, ValueError) as exc:
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
    def _field_label(field: str) -> re.Pattern[str]:
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
        for path in self.repo_files({".md"}):
            content = self.read_text(path)
            if content is None:
                continue
            display_path = _display_path(path, self.root)
            for raw_target in LINK.findall(content):
                if not raw_target.strip():
                    self.ok(False, f"link target is not empty: {display_path}")
                    continue
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
                # Non-strict resolution can leave symlink loops unresolved on
                # Python 3.13+. Every manifest member must resolve completely.
                candidate = path.resolve(strict=True)
                safe = path.is_file() and not path.is_symlink() and root_resolved in candidate.parents
            except (OSError, RuntimeError, UnicodeError, ValueError):
                self.ok(False, f"manifest entry is a valid repo path: {entry!r}")
                continue
            self.ok(
                safe,
                f"manifest entry is a repo file: {entry}",
            )

    def check_manifest_completeness(self, version: str) -> None:
        """Require the manifest to ship every distributable file.

        ``check_manifest`` proves only that listed entries exist, so the 0.5.0
        package shipped without its own release notes while the README said
        the validators enforce manifest completeness. Every file under a
        shipped tree, the root documents, and the current release notes must be
        listed. Generated bytecode is never distributable and is skipped.
        """
        manifest = self.json_file("package-manifest.json")
        if not isinstance(manifest, list) or not all(isinstance(item, str) for item in manifest):
            return
        listed = set(manifest)
        for path in self.repo_files():
            relative = _display_path(path, self.root)
            parts = relative.split("/")
            if parts[0] not in SHIPPED_TREES or "__pycache__" in parts or path.suffix in {".pyc", ".pyo"}:
                continue
            self.ok(relative in listed, f"manifest ships {relative}")
        for name in SHIPPED_ROOT_FILES:
            self.ok(name in listed, f"manifest ships {name}")
        notes = f"docs/release-notes-{version}.md"
        exists = (self.root / notes).is_file()
        self.ok(exists, f"current release notes exist: {notes}")
        if exists:
            self.ok(notes in listed, f"current release notes ship in the package: {notes}")
            first = (self.read_text(self.root / notes) or "").splitlines()[:1]
            self.ok(first == [f"# Agent Team {version}"], f"current release notes are titled Agent Team {version}")

    def check_release_notes_references(self) -> None:
        """Verify release-notes filenames listed in the README repository map exist.

        The repository map is a curated list of current files, but it is a code
        block, not a link, so the link checker does not cover it. Any concrete
        release-notes filename it names must exist under ``docs/``. Changelog and
        release notes are intentionally not scanned, because they legitimately
        mention old filenames when describing a rename.
        """
        readme = self.text("README.md")
        ref = re.compile(r"release-notes-[\w.]+\.md")
        for token in sorted(set(ref.findall(readme))):
            self.ok(
                (self.root / "docs" / token).is_file(),
                f"release notes reference exists: README.md -> docs/{token}",
            )

    def check_result_conformance(self, schema: object, result: object) -> None:
        """Check the result fixture conforms to the result schema's constraints.

        The repository ships ``evals/result.schema.json`` as the versioned result
        shape. Const, enum, and required constraints are reported in the original
        messages, and the bundled schema checker applies the rest of the contract,
        including unknown fields and collection bounds.
        """
        if not (isinstance(schema, dict) and isinstance(result, dict)):
            return
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            return
        for key, spec in properties.items():
            if not isinstance(spec, dict):
                continue
            if "const" in spec:
                self.ok(result.get(key) == spec["const"], f"result.{key} matches schema const")
            if "enum" in spec:
                self.ok(result.get(key) in spec["enum"], f"result.{key} is a schema-allowed value")
        for key in schema.get("required", []):
            self.ok(key in result, f"result has required key {key}")
        arms_spec = properties.get("arms")
        arm_required = []
        if isinstance(arms_spec, dict):
            arm_required = arms_spec.get("items", {}).get("required", [])
        for arm in result.get("arms", []):
            for key in arm_required:
                self.ok(isinstance(arm, dict) and key in arm, f"arm has required key {key}")
        # The checks above only cover const, enum, and required. The shipped
        # schema also rejects extra fields, short arms, and wrong nested types.
        try:
            errors = schema_violations(result, schema)
        except ValueError:
            self.ok(False, "schema is usable: evals/result.schema.json")
            return
        for error in errors:
            self.ok(False, f"result conforms to schema: {error}")

    def check_documented_package_name(self, version: str) -> None:
        """Reject a stale package archive name in any document that ships.

        Only the README carried this check, yet the same
        ``agent-team-<version>.zip`` command appears in the package verification
        and closure walkthrough documents, which are themselves packaged. A
        version bump therefore left those two telling an operator to verify an
        archive the builder never produces. Only documents that name an archive
        are asserted, and release notes and the changelog are skipped because
        they name past archives on purpose.
        """
        pattern = re.compile(r"agent-team-(\d+\.\d+\.\d+)\.zip")
        for path in self.repo_files({".md"}):
            relative = _display_path(path, self.root)
            if relative == "CHANGELOG.md" or relative.startswith("docs/release-notes-"):
                continue
            found = set(pattern.findall(self.read_text(path) or ""))
            if found:
                self.ok(found == {version}, f"documented package name uses VERSION: {relative}")

    def check_schema_versions(self) -> None:
        """Verify the pinned version table in schemas/VERSIONS.md against the schemas.

        That file states its version strings are "extracted directly from each
        schema file" and that no version is invented. Nothing compared the table
        with the schemas, so a schema bump left it silently wrong in either
        direction: a stale string, or a schema nobody documented.
        """
        table = self.text("schemas/VERSIONS.md")
        documented = dict(re.findall(r"(?m)^\|\s*`(schemas/[\w.-]+\.json)`\s*\|\s*`([^`]+)`", table))
        shipped = sorted(f"schemas/{path.name}" for path in (self.root / "schemas").glob("*.json"))
        self.ok(sorted(documented) == shipped, "schemas/VERSIONS.md lists every shipped schema")
        for relative in shipped:
            schema = self.json_file(relative)
            if not isinstance(schema, dict):
                continue
            consts = {spec["const"] for spec in schema.get("properties", {}).values()
                      if isinstance(spec, dict) and "const" in spec}
            self.ok(
                documented.get(relative) in consts,
                f"documented schema version matches the schema: {relative}",
            )

    def shipped_schemas(self) -> list[Path]:
        return sorted((self.root / "schemas").glob("*.json")) + sorted((self.root / "evals").glob("*.schema.json"))

    def check_schema_keywords(self) -> None:
        """Report any shipped schema the bundled validator cannot fully enforce.

        The schemas are the machine-readable contract, and the checker
        deliberately refuses to pretend it understands an assertion keyword it
        does not implement. That refusal is per-check, so a schema typo is only
        caught if a fixture happens to reach it. This walks every subschema of
        every shipped schema up front.
        """
        paths = self.shipped_schemas()
        self.ok(bool(paths), "shipped schema documents are present")
        for path in paths:
            relative = path.relative_to(self.root).as_posix()
            schema = self.json_file(relative)
            if not isinstance(schema, dict):
                continue
            problems = schema_problems(schema)
            for problem in problems:
                self.ok(False, f"schema is enforceable: {relative} {problem}")
            self.ok(not problems, f"schema is enforceable: {relative}")

    def check_schema_ids(self) -> None:
        """Require a unique $id on every shipped schema.

        A schema's $id is its identity: it is how the contract is referenced and
        cached. Six of the nine schemas under schemas/ had none, and nothing
        stopped a new schema from reusing an existing $id, which would let two
        different contracts answer to the same name.
        """
        seen: dict[str, str] = {}
        loaded: list[tuple[str, object]] = []
        for path in self.shipped_schemas():
            relative = path.relative_to(self.root).as_posix()
            schema = self.json_file(relative)
            loaded.append((relative, schema))
            identifier = schema.get("$id") if isinstance(schema, dict) else None
            self.ok(isinstance(identifier, str) and identifier.strip(), f"schema declares an $id: {relative}")
            if isinstance(identifier, str) and identifier.strip():
                self.ok(seen.get(identifier, relative) == relative, f"schema $id is unique: {relative}")
                seen.setdefault(identifier, relative)
        # Root identities are claimed first, so a nested copy is the one reported.
        for relative, schema in loaded:
            if not isinstance(schema, dict):
                continue
            for location, nested in schema_identifiers(schema):
                if location == "$":
                    continue
                self.ok(isinstance(nested, str) and nested.strip(), f"schema declares an $id: {relative} {location}")
                if not isinstance(nested, str) or not nested.strip():
                    continue
                self.ok(nested not in seen, f"schema $id is unique: {relative} {location}")
                seen.setdefault(nested, f"{relative} {location}")

    def check_connect(self) -> None:
        """Check the connect schema exposes a complete, versioned message contract.

        The connect spec (connect.md) is machine-readable via
        schemas/connect.schema.json. This verifies the envelope is required, all
        message types are declared, and a handoff reuses the six-field role brief.
        """
        schema = self.json_file("schemas/connect.schema.json")
        if not isinstance(schema, dict):
            return
        envelope = {"connect_version", "type", "message_id", "correlation_id", "from", "to", "payload"}
        self.ok(envelope.issubset(set(schema.get("required", []))), "connect schema requires the message envelope")
        message_types = schema.get("properties", {}).get("type", {}).get("enum", [])
        self.ok(
            {"request", "response", "handoff", "status", "result"}.issubset(set(message_types)),
            "connect schema declares all message types",
        )
        role_brief = schema.get("$defs", {}).get("handoff", {}).get("properties", {}).get("role_brief", {})
        self.ok(
            {field.lower().replace(" ", "_") for field in FIELDS}.issubset(set(role_brief.get("required", []))),
            "connect handoff requires the six role brief fields",
        )

    def connect_violations(self, message: object, schema: dict,
                           schema_relative: str = "schemas/connect.schema.json") -> list[str]:
        """Return human-readable conformance violations for one connect message.

        Reads the constraints from schemas/connect.schema.json so the check stays
        in sync with the contract: the required envelope, const values, the type
        enum, each type's required payload keys, and the handoff role brief
        fields. Uses only the standard library. A schema the bundled checker
        cannot apply is recorded once as a failed check instead of a traceback.
        """
        if not isinstance(message, dict):
            return ["message is not an object"]
        violations: list[str] = []
        properties = schema.get("properties", {})
        const = {
            key: spec["const"]
            for key, spec in properties.items()
            if isinstance(spec, dict) and "const" in spec
        }
        enum = {
            key: spec["enum"]
            for key, spec in properties.items()
            if isinstance(spec, dict) and "enum" in spec
        }
        defs = schema.get("$defs", {})
        message_types = enum.get("type", [])
        payload_required = {t: defs.get(t, {}).get("required", []) for t in message_types}
        role_brief_required = (
            defs.get("handoff", {}).get("properties", {}).get("role_brief", {}).get("required", [])
        )
        for key in schema.get("required", []):
            if key not in message:
                violations.append(f"missing required field {key}")
        for key, value in const.items():
            if key in message and message.get(key) != value:
                violations.append(f"{key} must equal {value}")
        if "type" in enum and message.get("type") not in enum["type"]:
            violations.append(f"type must be one of {sorted(enum['type'])}")
        message_type = message.get("type")
        payload = message.get("payload")
        if isinstance(message_type, str) and message_type in payload_required and isinstance(payload, dict):
            for key in payload_required[message_type]:
                if key not in payload:
                    violations.append(f"payload missing required field {key}")
        if message_type == "handoff" and isinstance(payload, dict):
            role_brief = payload.get("role_brief")
            for key in role_brief_required:
                if not (isinstance(role_brief, dict) and key in role_brief):
                    violations.append(f"role_brief missing required field {key}")
        try:
            violations.extend(schema_violations(message, schema))
        except ValueError:
            unusable = f"schema is usable: {schema_relative}"
            if unusable not in self.failures:
                self.ok(False, unusable)
            violations.append("schema could not be applied")
        violations.extend(refusal_text_violations(message))
        return violations

    def check_connect_examples(self, relative: str = "connect.md",
                               schema_relative: str = "schemas/connect.schema.json") -> None:
        """Verify worked examples against their declared versioned schema."""
        content = self.text(relative)
        if not content:
            return
        schema = self.json_file(schema_relative)
        if not isinstance(schema, dict):
            return
        blocks = re.findall(r"```json\s*(.*?)```", content, flags=re.DOTALL)
        self.ok(bool(blocks), f"{relative} contains worked JSON examples")
        for index, block in enumerate(blocks, 1):
            try:
                msg = json.loads(block, object_pairs_hook=_json_object)
            except (json.JSONDecodeError, ValueError) as exc:
                self.ok(False, f"connect example {index} is valid JSON: {exc}")
                continue
            violations = self.connect_violations(msg, schema, schema_relative)
            if violations:
                for violation in violations:
                    self.ok(False, f"connect example {index} {violation}")
            else:
                self.ok(True, f"connect example {index} conforms to the connect schema")

    def check_connect_conformance(self, relative: str = "conformance/connect/cases.json",
                                  schema_relative: str = "schemas/connect.schema.json") -> None:
        """Run the versioned connect conformance suite and check each outcome.

        conformance/connect/cases.json holds named messages with an expectation of
        valid or invalid. Each message is checked with connect_violations and the
        result must match the expectation, so the suite is machine-verified in CI.
        A case must declare one of the two expectations exactly; an unrecognised
        value is reported rather than read as "invalid".
        """
        suite = self.json_file(relative)
        if not isinstance(suite, dict):
            return
        cases = suite.get("cases")
        self.ok(
            isinstance(cases, list) and len(cases) >= 5,
            "connect conformance suite has at least five cases",
        )
        if not isinstance(cases, list):
            return
        schema = self.json_file(schema_relative)
        if not isinstance(schema, dict):
            return
        names = [case.get("name") for case in cases if isinstance(case, dict)]
        self.ok(
            bool(names)
            and all(isinstance(name, str) for name in names)
            and len(names) == len(set(names)),
            "connect conformance case names are unique",
        )
        for case in cases:
            if not isinstance(case, dict):
                self.ok(False, "connect conformance case is an object")
                continue
            name = case.get("name", "<unnamed>")
            declared = case.get("expect")
            # An unrecognised expectation is a broken case, not an invalid
            # message. Treating it as "invalid" inverts the case and lets it
            # report a pass for the opposite of what it declares. A tuple keeps
            # the comparison total for an unhashable JSON value.
            if declared not in ("valid", "invalid"):
                self.ok(False, f"connect conformance case {name} declares valid or invalid")
                continue
            found = self.connect_violations(case.get("message"), schema, schema_relative)
            conforms = not found
            self.ok(conforms == (declared == "valid"), f"connect conformance case {name} matches its expectation")
            # A declared reason that is not among the diagnostics lets a copied
            # case pass while naming the wrong contract. Absence stays allowed
            # for suites that only declare expect.
            if declared == "invalid" and "violation" in case:
                stated = case.get("violation")
                self.ok(
                    isinstance(stated, str) and any(stated in error for error in found),
                    f"connect conformance case {name} fails for its declared violation",
                )

    def check_negotiation_conformance(self, relative: str = "conformance/negotiation/cases.json") -> None:
        """Run the negotiation suite and hold connect.md to its own rules.

        The negotiation algorithm in connect.md is normative but was prose only,
        so its worked examples drifted from it unnoticed. Each case's expected
        response payload must equal what the reference negotiator computes, the
        specification's capability vocabulary must match the reference baseline,
        and its acceptance and refusal examples must be the rules' replies to its
        request example.
        """
        suite = self.json_file(relative)
        cases = suite.get("cases") if isinstance(suite, dict) else None
        self.ok(isinstance(cases, list) and len(cases) >= 6, "negotiation conformance suite has at least six cases")
        if isinstance(cases, list):
            names = [case.get("name") if isinstance(case, dict) else None for case in cases]
            self.ok(
                bool(names) and all(isinstance(name, str) and name for name in names)
                and len(names) == len(set(names)),
                "negotiation conformance case names are unique",
            )
            for case in cases:
                if not isinstance(case, dict):
                    self.ok(False, "negotiation conformance case is an object")
                    continue
                name = case.get("name", "<unnamed>")
                request = case.get("request")
                version = request.get("connect_version") if isinstance(request, dict) else None
                schema_relative = {
                    "agent-team-connect/v0.1": "schemas/connect.schema.json",
                    "agent-team-connect/v0.2": "schemas/connect-v0.2.schema.json",
                }.get(version, "schemas/connect.schema.json")
                schema = self.json_file(schema_relative)
                if isinstance(schema, dict):
                    self.ok(
                        not self.connect_violations(request, schema, schema_relative),
                        f"negotiation conformance case {name} request conforms",
                    )
                try:
                    computed = negotiate(request, case.get("advertised"))
                except ValueError:
                    computed = None
                self.ok(computed is not None and computed == case.get("expect"),
                        f"negotiation conformance case {name} matches")

        spec = self.text("connect.md")
        section = re.search(r"(?ms)^### Capability vocabulary\s*$(.*?)^##", spec)
        tokens = sorted(re.findall(r"(?m)^- `([a-z0-9-]+)`", section.group(1))) if section else []
        self.ok(tokens == list(BASELINE_CAPABILITIES), "connect.md capability vocabulary matches the reference negotiator")
        examples = {}
        for block in re.findall(r"```json\s*(.*?)```", spec, flags=re.DOTALL):
            try:
                message = json.loads(block, object_pairs_hook=_json_object)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(message, dict) and isinstance(message.get("message_id"), str):
                examples[message["message_id"]] = message
        request = examples.get("msg-0001")
        without_scope = [token for token in BASELINE_CAPABILITIES if token != "bounded-scope"]
        for message_id, advertised in (("msg-0002", list(BASELINE_CAPABILITIES)), ("msg-0006", without_scope)):
            reply = examples.get(message_id)
            try:
                expected = negotiate(request, advertised) if request is not None else None
            except ValueError:
                expected = None
            self.ok(
                expected is not None and isinstance(reply, dict) and reply.get("payload") == expected,
                f"connect example {message_id} follows the negotiation rules",
            )

    def check_skill_references(self) -> None:
        """Hold SKILL.md path references and the skill metadata to the package.

        SKILL.md cites schemas, scripts and suites that an installer looks for
        in the source package, and a renamed or unshipped file left it pointing
        nowhere. Every backticked path is checked, against the source root or
        the skill folder itself, and a cited file must ship. The metadata must
        name the skill and must not advertise coordination, which the skill has
        not done since 0.5.0.
        """
        skill_dir = "skill/agent-team-os"
        skill = self.text(f"{skill_dir}/SKILL.md")
        prose = re.sub(r"(?ms)^```.*?^```", "", skill)
        manifest = self.json_file("package-manifest.json")
        shipped = set(manifest) if isinstance(manifest, list) and all(isinstance(item, str) for item in manifest) else set()
        seen = set()
        for token in re.findall(r"`([^`\n]+)`", prose):
            words = token.split()
            if not words:
                continue
            reference = words[0]
            if not ("/" in reference or reference.endswith((".md", ".json"))):
                continue
            if "<" in reference or reference.startswith("dist/") or reference in seen:
                continue
            seen.add(reference)
            relative = reference.rstrip("/")
            candidates = [relative, f"{skill_dir}/{relative}"]
            found = next((item for item in candidates if (self.root / item).exists()), None)
            self.ok(found is not None, f"SKILL.md reference exists: {reference}")
            if found is not None and (self.root / found).is_file():
                self.ok(found in shipped, f"SKILL.md reference ships in the package: {reference}")
        metadata = self.text(f"{skill_dir}/agents/openai.yaml")
        fields = dict(re.findall(r'(?m)^\s*(short_description|default_prompt):\s*"(.*)"\s*$', metadata))
        self.ok("$agent-team-os" in fields.get("default_prompt", ""), "skill metadata default prompt names $agent-team-os")
        summary = fields.get("short_description", "")
        self.ok(
            bool(summary) and "coordinate" not in summary.lower() and "route" not in summary.lower(),
            "skill metadata does not advertise coordination",
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

    def check_operator_fixtures(self) -> None:
        try:
            from .check import check_document
        except ImportError:
            from check import check_document
        for kind, relative in (
            ('plan', 'templates/routing-plan.json'),
            ('evidence', 'templates/evidence-ledger.json'),
            ('audit', 'templates/audit-closure.json'),
        ):
            document = self.json_file(relative)
            if document is not None:
                try:
                    errors = check_document(kind, document, schema_root=self.root)
                except (OSError, ValueError, RecursionError):
                    errors = ['operator schema is unreadable or unsupported']
                self.ok(not errors, f'operator fixture conforms: {relative}')
                self.failures.extend(f'{relative}: {error}' for error in errors)

    def check_packet_fixture(self) -> None:
        try:
            from .packet import inspect_packet
        except ImportError:
            from packet import inspect_packet
        try:
            result = inspect_packet(self.root / 'templates/operator-packet.json', schema_root=self.root)
            self.ok(result['ok'], 'operator packet references conforming records')
        except (OSError, ValueError, RecursionError, OverflowError):
            self.ok(False, 'operator packet references conforming records')

    def run(self) -> None:
        skill = self.text("skill/agent-team-os/SKILL.md")
        readme = self.text("README.md")
        template = self.text("templates/role-brief.md")
        audit = self.text("templates/audit-report.md")
        examples = self.text("examples/routing-scenarios.md")
        self.check_frontmatter(skill)
        self.check_manifest()
        self.check_skill_references()
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
        self.check_documented_package_name(version)
        self.check_manifest_completeness(version)
        self.check_changelog_version(version)
        self.check_release_notes_references()

        schema = self.json_file("schemas/role-brief.schema.json")
        if isinstance(schema, dict):
            required = schema.get("required", [])
            expected = {field.lower().replace(" ", "_") for field in FIELDS}
            self.ok(expected.issubset(set(required)), "role brief schema requires six fields")
        self.check_schema_versions()
        self.check_schema_keywords()
        self.check_schema_ids()

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
        self.check_result_conformance(result_schema, result)
        self.check_connect()
        self.check_connect_examples()
        self.check_connect_conformance()
        self.check_connect_examples("docs/connect-v0.2.md", "schemas/connect-v0.2.schema.json")
        self.check_connect_conformance("conformance/connect-v0.2/cases.json", "schemas/connect-v0.2.schema.json")
        self.check_negotiation_conformance()
        self.check_operator_fixtures()
        self.check_packet_fixture()
        self.check_text_files()
        self.check_links()

    def check_text_files(self) -> None:
        """Reject an em dash anywhere and unsafe structure in documents and data."""
        for path in self.repo_files():
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_version_flag(parser)
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
