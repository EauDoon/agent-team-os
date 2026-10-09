# Schema versions

This file pins the version metadata for each JSON Schema under `schemas/`.
The package-level version lives in `VERSION` at the repo root and is the
single source of truth for the package release. Every consumer reads it
through `scripts/version.py` (`package_version()`), which requires one strict
UTF-8 `X.Y.Z` line: the CLIs' `--version`, the package builder and verifier,
the evaluation report, the Makefile and CI.

The version strings below are extracted directly from each schema file
(`connect_version`, `audit_version`, `ledger_version`, `packet_version`,
`receipt_version`, `role_brief_version`, `plan_version`) or from the
filename where the schema declares no inline version metadata. No
versions are invented.

## Schemas

| Schema file | Version metadata |
| --- | --- |
| `schemas/audit-closure.schema.json` | `agent-team-audit/v0.1` (`audit_version` const) |
| `schemas/connect.schema.json` | `agent-team-connect/v0.1` (`connect_version` const) |
| `schemas/connect-v0.2.schema.json` | `agent-team-connect/v0.2` (`connect_version` const; filename also carries `v0.2`) |
| `schemas/evidence-ledger.schema.json` | `agent-team-evidence/v0.1` (`ledger_version` const) |
| `schemas/packet.schema.json` | `agent-team-packet/v0.1` (`packet_version` const) |
| `schemas/packet-v0.2.schema.json` | `agent-team-packet/v0.2` (`packet_version` const; required closure policy) |
| `schemas/packet-receipt.schema.json` | `agent-team-packet-receipt/v0.1` (`receipt_version` const) |
| `schemas/role-brief.schema.json` | `agent-team-role-brief/v0.1` (`role_brief_version` const) |
| `schemas/routing-plan.schema.json` | `agent-team-plan/v0.1` (`plan_version` const) |

## Notes

- `VERSION` is intentionally left untouched here. `scripts/version.py` reads
  it and rejects anything but a single bare `X.Y.Z` line, so the file must
  stay that way. Schema versions therefore live alongside the schemas in this
  `schemas/VERSIONS.md` file instead.
- Every schema in `schemas/` carries an inline version const, so there
  are no `unspecified` entries. If a future schema lands without one,
  list it as `version: unspecified` rather than guessing.
