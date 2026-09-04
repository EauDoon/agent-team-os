# Release notes for 0.1.6

Patch release that closes a gap in the local contract checks. No change to the
coordination instructions or the role brief contract.

## Changes

- Added `check_result_conformance` to `scripts/validate.py`. The repository ships
  `evals/result.schema.json` as the versioned result shape, but nothing previously
  verified that `evals/results.v0.1.json` actually conforms to it. The check now
  applies the schema's `const`, `enum`, and `required` constraints (top-level and
  per arm) using only the standard library, with no external schema dependency.
- Added a unit test covering a conforming fixture and one that violates the const,
  enum, per-arm required, and top-level required constraints.

## Verification

- `python3 scripts/validate.py` passes all checks, including the new
  result-conformance checks.
- `python3 -m unittest discover -s tests` passes; the symlink-only test is
  skipped on platforms without symlink permission.
- `python3 scripts/package.py --output dist` produces
  `agent-team-0.1.6.zip` and `agent-team-0.1.6.zip.sha256`.
- `sha256sum -c` confirms the archive against the checksum.

Recheck the package checksum after any later byte or metadata change.
