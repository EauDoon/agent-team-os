# Release notes for 0.1.1

Patch release that hardens the public contract, the local checks, and the
release pipeline. No change to the coordination instructions or the role
brief contract.

## Changes

- Corrected the `$id` host in `schemas/role-brief.schema.json` and
  `evals/result.schema.json` from the stale `oonyl.github.io` to
  `EauDoon.github.io` to match the current repository owner.
- Hardened `scripts/validate.py`:
  - The link checker now rejects relative links that escape the repository root
    (for example via `..`), not only missing files.
  - Added a manifest check that confirms every entry in
    `package-manifest.json` resolves to a file inside the repository and has no
    path traversal.
- Made the contract checks deterministic on the hosted runner by using
  `python3` in `.github/workflows/ci.yml`.
- Added `.github/workflows/release.yml`, which builds the installable package
  and publishes a GitHub Release with the ZIP and its SHA-256 checksum when a
  `v*` tag is pushed.

## Verification

- `python3 scripts/validate.py` passes all checks.
- `python3 scripts/package.py --output dist` produces
  `agent-team-0.1.1.zip` and `agent-team-0.1.1.zip.sha256`.
- `sha256sum -c` confirms the archive against the checksum.

Recheck the package checksum after any later byte or metadata change.
