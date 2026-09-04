# Changelog

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
