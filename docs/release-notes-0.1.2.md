# Release notes for 0.1.2

Patch release that improves test portability and tightens the local contract
check. No change to the coordination instructions or the role brief contract.

## Changes

- Made the test suite portable to Windows. The two symlink-dependent tests now
  probe for symlink support at import time and skip cleanly when the platform
  or the un-elevated test user cannot create symlinks, instead of erroring. The
  platform-independent assertions in those tests still run.
- Tightened the `check_fields` contract check in `scripts/validate.py`. Each of
  the six field names is now recognized only as a label (a markdown heading, a
  `Field:` line, or a table cell) rather than as a bare word, so a prose mention
  no longer satisfies the presence check.

## Verification

- `python3 scripts/validate.py` passes all checks.
- `python3 -m unittest discover -s tests` passes; the symlink-only test is
  skipped on platforms without symlink permission.
- `python3 scripts/package.py --output dist` produces
  `agent-team-0.1.2.zip` and `agent-team-0.1.2.zip.sha256`.
- `sha256sum -c` confirms the archive against the checksum.

Recheck the package checksum after any later byte or metadata change.
