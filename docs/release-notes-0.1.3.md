# Release notes for 0.1.3

Patch release that closes a gap in the local contract checks. No change to the
coordination instructions or the role brief contract.

## Changes

- Added a `check_changelog_version` contract check in `scripts/validate.py` that
  confirms the newest `## X.Y.Z` entry in `CHANGELOG.md` matches `VERSION`. The
  README package commands were already checked for version consistency, but the
  changelog was not, even though the release process depends on the version being
  consistent across VERSION, the README, the changelog, and the release notes.
- Added a unit test covering a matching top entry, a stale top entry, and a
  changelog with no version entry at all.

## Verification

- `python3 scripts/validate.py` passes all checks, including the new
  `CHANGELOG top entry matches VERSION` check.
- `python3 -m unittest discover -s tests` passes; the symlink-only test is
  skipped on platforms without symlink permission.
- `python3 scripts/package.py --output dist` produces
  `agent-team-0.1.3.zip` and `agent-team-0.1.3.zip.sha256`.
- `sha256sum -c` confirms the archive against the checksum.

Recheck the package checksum after any later byte or metadata change.
