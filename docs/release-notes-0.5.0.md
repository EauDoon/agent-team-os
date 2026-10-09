# Agent Team 0.5.0

This release separates the wire format and tool pack from the coordination
protocol and ships the validator hardening accumulated since 0.4.0. Python 3.11
or later and the standard library suffice.

## Wire format and tool pack, not protocol

- The shipped `SKILL.md` and `README.md` no longer assert a specific
  delegation gate, stop-condition rule, audit taxonomy, or finding
  classification. The coordination protocol itself is part of the host
  runtime that consumes this skill. This package ships the contract layer and
  the tooling, not the protocol.
- The named-role table and the seven-step workflow diagram are gone from the
  README. The role-brief schema still accepts any non-empty role string, and
  the host runtime decides which role names are valid for a given task. The
  five role names that appeared in earlier versions remain as examples in
  `templates/role-brief.md`, `examples/routing-scenarios.md`, and the
  conformance cases; new templates and examples are not required to use them.
- The six-field role brief, the connect spec, the dependency-light validators,
  the deterministic package builder, the SHA-256 verification step, the
  calibrated evaluation harness, and the connect conformance suite are
  unchanged. No schema version bumped. No wire format changed.
- Install snippet, package archive name (`agent-team-0.5.0.zip`), repository
  map, and this release notes file are updated for the version bump.

## Hardening carried from 0.4.0 unreleased

These items were accumulated against `main` after the 0.4.0 version bump (0.2.0 through 0.4.0 were never tagged) and were not
published as a release. They are validator, builder, and CI hardening only;
they do not change the contract layer.

- The release workflow runs the rubric case suite before the package is built,
  so a tag cannot publish when the shipped cases have drifted from
  `evals/tasks.json`.
- The contract checker rejects whitespace-only strings where `minLength` would
  otherwise have counted them as nonempty, duplicate JSON object keys in
  repository JSON, whitespace-only rubric task IDs, and connect conformance
  cases whose declared `expect` is neither `valid` nor `invalid`.
- The validator reports schema keywords the bundled validator cannot enforce
  and local schema references that do not resolve, before any document is
  checked.
- The version table in `schemas/VERSIONS.md` is checked against the shipped
  schemas, the documented package archive name is checked in every shipped
  document, and the `validate` Makefile target stops running the contract
  check twice.
- `evals/runner.py` and the `evals/cases/` fixtures ship in the package
  manifest. The bounded rubric case suite runs in CI.
- v0.2 packet closure links required evidence claims and audit results to an
  expected output revision, with exact-byte receipt verification. A fully
  synthetic operator walkthrough and extracted-package regressions cover
  incomplete, altered, stale, and replayed records. v0.1 behavior is
  preserved.

## Limitations carried forward

- The skill is an instruction layer, not an execution engine, storage system,
  authorization mechanism, or isolation boundary.
- Output quality remains limited by the supplied evidence, available tools,
  model behavior, and enforced permissions.
- Delegation adds overhead when roles overlap or the task is too small.
- Task-scoped roles do not provide durable identity, memory, authority, or
  trust across requests.
- Human judgment remains necessary before consequential use.
- The shipped schemas accept any non-empty role name. Hosts must define and
  enforce their own role vocabulary.

## Authorship

EauDoon directed, reviewed, and takes responsibility for the result. This
public package uses synthetic scenarios. See `PROVENANCE.md` for the complete
creation record.