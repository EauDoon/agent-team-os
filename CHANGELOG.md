# Changelog

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
