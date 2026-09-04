# Release notes for 0.1.7

Patch release that hardens the link checker's own parsing. No change to the
coordination instructions or the role brief contract.

## Changes

- Hardened the link checker's destination parser in `scripts/validate.py`. The
  `LINK` regex previously captured a markdown link destination only up to the first
  `)`, so a destination containing a parenthesis would be truncated and misparsed.
  It now handles one level of balanced parentheses. No existing repository link
  uses a parenthesis, so this is a strict robustness improvement, and it keeps the
  link-escape checks (scheme and authority) operating on the correct target.
- Added a unit test for a link whose destination contains a parenthesis.

## Verification

- `python3 scripts/validate.py` passes all checks; existing link checks are
  unchanged.
- `python3 -m unittest discover -s tests` passes; the symlink-only test is
  skipped on platforms without symlink permission.
- `python3 scripts/package.py --output dist` produces
  `agent-team-0.1.7.zip` and `agent-team-0.1.7.zip.sha256`.
- `sha256sum -c` confirms the archive against the checksum.

Recheck the package checksum after any later byte or metadata change.
