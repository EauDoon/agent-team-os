# Release notes for 0.1.5

Patch release that makes the packaged artifact byte-for-byte deterministic across
platforms. No change to the coordination instructions or the role brief contract.

## Changes

- Added a `.gitattributes` that forces LF line endings (`eol=lf`) for all text
  files and marks binary assets as binary.
- Why: `scripts/package.py` packages the working-tree bytes. On a machine whose
  Git converts line endings to CRLF (for example a Windows checkout with
  `core.autocrlf=true`), the produced archive and its SHA-256 differed from the
  Linux CI build. That would make the README's "verify the checksum before
  copying" step fail for no real reason. Forcing LF in the working tree makes the
  packaged artifact identical on every platform.

## Verification

- With the attribute in place, a freshly checked-out working tree is LF, and
  packaging it yields the same SHA-256 as packaging the committed (LF) bytes.
- `python3 scripts/validate.py` passes all checks.
- `python3 -m unittest discover -s tests` passes; the symlink-only test is
  skipped on platforms without symlink permission.
- `python3 scripts/package.py --output dist` produces
  `agent-team-0.1.5.zip` and `agent-team-0.1.5.zip.sha256`.
- `sha256sum -c` confirms the archive against the checksum.

Note: if your working tree was checked out before this change, an in-place
`git checkout -- .` will not rewrite files Git already considers equivalent. To
pick up LF line endings, either make a fresh clone or remove and re-check out the
files, for example `git rm -rf --quiet . && git reset --hard HEAD`.
