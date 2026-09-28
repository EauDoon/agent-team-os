# Changelog

## Unreleased

- Reject a v0.2 refusal whose reason or next step is only whitespace. `minLength`
  counted those strings as nonempty, and the v0.1 contract is unchanged.
- Reject duplicate object keys in repository JSON read by the contract checker.
  The last value used to win, so a repeated schema field could hide the first one.
- Reject a rubric task ID that is only whitespace. A space was truthy, so the
  runner treated it as a real id and reported a case-set mismatch instead.
- Reject duplicate JSON object keys in the rubric and in rubric case files.
  `json.load` kept the last value, so an earlier conflicting field was ignored.
- Check a connect conformance case's declared `violation` against the diagnostics
  the checker actually produced. The v0.2 wrong-version case had named the v0.1
  contract.
- Apply the full result schema when checking `evals/results.v0.1.json`, so an
  extra field or a short `arms` list is rejected instead of reported as conforming.
- Reject a nested schema `$id` that reuses another contract's identity. The
  routing plan's embedded brief no longer claims the role-brief schema URI.
- Treat numerically equal JSON numbers as equal for `const`, `enum`, and
  `uniqueItems`, so `1` and `1.0` are one value while `true` stays distinct.
- Refuse a document that exceeds the contract depth limit inside an `if`
  condition, instead of treating that limit as a failed condition and accepting
  the document through `else`.
- Verify the release archive against the reviewed source before publishing it,
  not only against the checksum written by the same build.
- Declare a unique `$id` on every shipped schema, and check that each one is
  present and unreused.
- Refuse an unreadable or ambiguous `evals/tasks.json` with a one-line reason
  and exit status 2 instead of a traceback, reject a duplicate rubric task ID,
  and cover the runner with unit tests.
- Cover the assertion keywords the shipped schemas rely on and the contract
  checking guide claims: length and size bounds, inclusive numeric limits,
  unique items, `allOf`, the `else` branch and the nesting depth guard.
- Check the documented package archive name in every shipped document, not only
  in the README, so a version bump cannot leave stale commands in the
  verification and walkthrough guides.
- Report a shipped schema keyword the bundled validator cannot enforce, and a
  local schema reference that does not resolve, before any document is checked.
- Check the version table in `schemas/VERSIONS.md` against the shipped schemas,
  so a schema version bump cannot leave the pinned table silently wrong.
- Report a connect conformance case whose `expect` is neither `valid` nor
  `invalid`, instead of reading any other value as `invalid` and reporting a
  match for the opposite of what the case declares.
- Stop the `validate` Makefile target from running the contract check twice and
  printing a duplicate report.
- Ship `evals/runner.py` and the `evals/cases/` fixtures in the package manifest,
  so the released evaluation suite includes the check that keeps it honest.
- Run the bounded rubric case suite in CI, so drift between `evals/tasks.json`
  and the shipped `evals/cases/` fixtures fails the build.
- Derive the CI package verification path from `VERSION` instead of repeating the
  current version, so a version bump cannot leave CI verifying a missing archive.
- Add opt-in v0.2 packet closure linking required evidence claims and audit
  results to an expected output revision, with exact-byte receipt verification.
- Include a fully synthetic operator walkthrough and extracted-package regressions
  for incomplete, altered, stale and replayed records; preserve v0.1 behavior.

## 0.4.0

- Trace blocked work, invalidate dependent acceptance and group readiness by budget.
- Identify downstream rework after plan changes and claim rechecks after evidence changes.
- Review evidence age with an explicit date and route audit queues to owners.
- Copy exact plan briefs and compare handoff/response envelopes while keeping
  recorded response acceptance separate from unverified handoff binding.
- Diagnose per-record packet drift while preserving exact-byte receipt checks.

## 0.3.0

- Author complete briefs and explicit v0.2 handoffs or actionable refusals.
- Inspect dependency readiness, plan changes, evidence impact and audit remediation.
- Export per-task paired evaluation evidence and escaped Markdown reports.
- Check bounded local record packets and preserve exact-byte receipts for drift checks.
- Preserve v0.1 wire compatibility and existing independent evaluation boundaries.

## 0.2.0

- Add local JSON contract checking for authored briefs, messages, routing plans,
  evidence ledgers and audit closure records.
- Enforce the complete shipped connection schema, including nested payloads.
- Add revision-aware handoff, resumption and bounded execution workflows.
- Summarize complete paired evaluation records without performance claims.
- Verify package content against reviewed source before extraction.
- Include operator guidance and checked examples in deterministic packages.

## 0.1.10

- Added a deterministic **capability negotiation** algorithm to `connect.md`
  (the `## Capability negotiation` section): the exact accept/refuse rules, the
  `missing` and `negotiated` set computations, and the edge cases (offered vs
  required, unknown capabilities, reproducible ordering, and required refusal
  reasons).
- Added a versioned **connect conformance suite** at `conformance/connect/`
  (`cases.json` plus a README), in the spirit of `evals/`: named connect messages
  with an expected `valid` or `invalid` outcome.
- Added `check_connect_conformance` to `scripts/validate.py`, which runs the suite
  in CI and asserts each case's actual conformance matches its expectation.
- Refactored the connect checks around a reusable `connect_violations` helper so
  the `connect.md` worked examples and the conformance suite share one code path.
- Packaged the new suite and added unit tests for `connect_violations` and the
  conformance outcome check.

## 0.1.9

- Added `check_connect_examples` to `scripts/validate.py`. The worked examples in
  `connect.md` are now extracted from their fenced json blocks and verified as
  valid, conforming connect messages: the envelope is required, `connect_version`
  matches the schema const, the `type` is a known message type, each payload has
  its schema-required keys, and a handoff's `role_brief` has the six fields. The
  constraints are read from `schemas/connect.schema.json`, so the check stays in
  sync with the contract. The spec's examples are now machine-verified in CI
  instead of being only illustrative.
- Added a unit test covering a conforming example and one with a missing
  payload field.

## 0.1.8

- Added `connect.md`, a versioned agent-interoperability specification for how an
  external agent or system connects to an `agent-team-os` Orchestrator. It defines
  the message envelope, capability discovery and negotiation, the message types
  (request, response, handoff, status, result), status and gap semantics, the
  security boundaries, versioning rules, and structured rejection behavior, with
  worked examples. It is a specification and protocol, not a runtime.
- Added `schemas/connect.schema.json`, the machine-readable connect message
  contract. The `handoff` payload reuses the six-field role brief.
- Added `check_connect` to `scripts/validate.py` to verify the connect schema
  requires the message envelope, declares all message types, and reuses the
  six-field role brief in a handoff. Added a unit test.
- Packaged both files and documented the spec in the README.

## 0.1.7

- Hardened the link checker's destination parser in `scripts/validate.py`. The
  `LINK` regex previously captured a link destination up to the first `)`, so a
  destination containing a parenthesis was misparsed. It now handles one level of
  balanced parentheses. No existing repository link uses a parenthesis, so this is
  a strict robustness improvement, and it keeps the link-escape checks operating
  on the correct target.
- Added a unit test for a link whose destination contains a parenthesis.

## 0.1.6

- Added `check_result_conformance` to `scripts/validate.py`. The repository ships
  `evals/result.schema.json` as the versioned result shape, but nothing previously
  verified that `evals/results.v0.1.json` actually conforms to it. The check now
  applies the schema's `const`, `enum`, and `required` constraints (top-level and
  per arm) using only the standard library.
- Added a unit test covering a conforming fixture and one that violates the
  const, enum, per-arm required, and top-level required constraints.

## 0.1.5

- Added a `.gitattributes` that forces LF line endings (`eol=lf`) for all text
  files and marks binary assets as binary. `scripts/package.py` packages the
  working-tree bytes, so on a machine whose Git converts to CRLF the archive
  (and its SHA-256) differed from the Linux CI build, which would make the
  README's "verify the checksum" step spuriously fail. Normalizing to LF makes
  the packaged artifact byte-for-byte identical on every platform.

## 0.1.4

- Corrected a stale reference in the README repository map: it still listed
  `release-notes-v0.1.0.md`, which the release-notes naming unification had
  already renamed to `release-notes-0.1.0.md`. The map now lists a real file and
  notes that release notes are versioned, one per release.
- Added `check_release_notes_references` to `scripts/validate.py`: any concrete
  `release-notes-*.md` filename referenced in a markdown file must exist under
  `docs/`. The repository map is a code block, not a link, so the link checker
  would not have caught this kind of drift.
- Added a unit test for a valid and a stale release-notes reference.

## 0.1.3

- Added a `check_changelog_version` contract check in `scripts/validate.py`
  that confirms the newest `## X.Y.Z` entry in `CHANGELOG.md` matches `VERSION`.
  The README was already checked for version consistency; the changelog was not,
  even though the release process depends on it.
- Added a unit test covering a matching top entry, a stale top entry, and a
  changelog with no version entry.

## 0.1.2

- Made the test suite portable to Windows: the symlink-dependent checks now
  probe for symlink support and skip gracefully when the platform (or the
  un-elevated test user) cannot create symlinks, instead of erroring. The
  platform-independent assertions in those tests still run.
- Tightened the `check_fields` contract check in `scripts/validate.py` to
  recognize each of the six field names only as a label (a markdown heading,
  a `Field:` line, or a table cell) rather than as a bare word, so a prose
  mention no longer satisfies the presence check.

## 0.1.1

- Corrected the `$id` host in both schemas from the stale `oonyl.github.io` to
  `EauDoon.github.io`.
- Hardened `scripts/validate.py`: the link checker now rejects links that escape
  the repository root, and a new manifest check confirms every
  `package-manifest.json` entry resolves to a file inside the repository.
- Switched `.github/workflows/ci.yml` to `python3` for deterministic runs on the
  hosted runner.
- Added `.github/workflows/release.yml`, which builds the installable package and
  publishes a GitHub Release with the ZIP and SHA-256 checksum on a `v*` tag.

## 0.1.0

- Corrected the role brief contract to six fields.
- Added reusable role brief and audit report templates.
- Added a machine-readable role brief schema and dependency-light validator.
- Added bounded evaluation fixtures with a strong solo baseline and an empty,
  versioned result record.
- Added deterministic packaging and checksum generation.
- Added CI and PowerShell or Bash installation guidance.
