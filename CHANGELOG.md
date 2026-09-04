# Changelog

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
