# Changelog

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
