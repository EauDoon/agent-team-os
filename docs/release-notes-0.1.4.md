# Release notes for 0.1.4

Patch release that corrects a stale document reference and adds a guard against
this class of drift. No change to the coordination instructions or the role
brief contract.

## Changes

- Corrected a stale reference in the README repository map. It still listed
  `release-notes-v0.1.0.md`, but the earlier release-notes naming unification had
  already renamed that file to `release-notes-0.1.0.md`. The map now lists a real
  file and notes that release notes are versioned, one per release.
- Added `check_release_notes_references` to `scripts/validate.py`. Any concrete
  `release-notes-*.md` filename listed in the README repository map must now exist
  under `docs/`. The repository map is a code block, not a link, so the existing
  link checker would not have caught this drift. Changelog and release notes are
  intentionally not scanned, because they legitimately mention old filenames when
  describing a rename.
- Added a unit test covering a valid and a stale release-notes reference.

## Verification

- `python3 scripts/validate.py` passes all checks, including the new
  `release notes reference exists` check.
- `python3 -m unittest discover -s tests` passes; the symlink-only test is
  skipped on platforms without symlink permission.
- `python3 scripts/package.py --output dist` produces
  `agent-team-0.1.4.zip` and `agent-team-0.1.4.zip.sha256`.
- `sha256sum -c` confirms the archive against the checksum.

Recheck the package checksum after any later byte or metadata change.
